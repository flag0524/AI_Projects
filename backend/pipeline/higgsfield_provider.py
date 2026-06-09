"""
Higgsfield 생성형 프로바이더 — MCP 서버 채널 try-on 클라이언트.

설계: docs/superpowers/specs/2026-06-08-higgsfield-provider-design.md

전송 채널 (2026-06-09 결정):
  프로덕션 REST 호스트(api.higgsfield.ai)가 522로 미동작하여, 동작하는 유일
  채널인 **MCP 서버**(https://mcp.higgsfield.ai/mcp, JSON-RPC over streamable
  HTTP, Bearer 인증)를 직접 호출한다. 스펙 잠긴 전제 2를 뒤집는 결정이나,
  전제 2의 가정(working REST 존재)이 실측으로 거짓이었다.

흐름 (scripts/hgf_mcp_probe.py로 검증된 호출 형태):
  ┌────────────────────────────────────────────────────────────┐
  │ initialize → notifications/initialized                      │
  │ media_upload(presigned) → PUT bytes → media_confirm         │
  │ generate_image(model, prompt, medias[{value,role}])         │
  │ job_display 폴링(results[0].status) → rawUrl 다운로드        │
  └────────────────────────────────────────────────────────────┘

범위:
  - 다중 의류 단일-호출 입력 (medias:[model, *garments]).
    2026-06-09 검증: 단일-호출 다중입력은 Leffa 순차 체이닝의 drift를 우회.
    generate_tryon(단일)은 하위 호환 래퍼로 유지.
  - 키 없으면 is_available()==False → laongen_engine 캐스케이드 폴백.

크레딧 부족은 generative_provider.GenerativeBillingError를 재사용해 기존 402
처리 경로(api/generate.py)와 일관되게 동작한다.

환경변수:
  HIGGSFIELD_API_KEY    : MCP Bearer 토큰 (없으면 비활성)
  HIGGSFIELD_MCP_URL    : MCP 엔드포인트 (기본 https://mcp.higgsfield.ai/mcp)
  HIGGSFIELD_TRYON_MODEL: 생성 모델 id (기본 nano_banana_pro)
  HIGGSFIELD_CA_BUNDLE  : 사내 프록시 SSL 가로채기용 루트 CA (.pem/.crt)
"""
import os
import io
import json
import time
from PIL import Image

# generative_provider의 결제 예외를 재사용 (402 경로 일관성)
from backend.pipeline.generative_provider import GenerativeBillingError

# Windows 시스템 인증서로 SSL 가로채기 환경 통과
try:
    import truststore
    truststore.inject_into_ssl()
except Exception:
    pass


class HiggsfieldUnavailable(Exception):
    """Higgsfield 백엔드 사용 불가 (키 없음, 네트워크/job 실패, 타임아웃)."""
    pass


# ── 설정 ──────────────────────────────────────────────────────
API_KEY     = os.environ.get("HIGGSFIELD_API_KEY", "").strip()
MCP_URL     = os.environ.get("HIGGSFIELD_MCP_URL", "https://mcp.higgsfield.ai/mcp").strip()
TRYON_MODEL = os.environ.get("HIGGSFIELD_TRYON_MODEL", "nano_banana_pro").strip()
ASPECT      = "2:3"

# 고정 간격 폴링 (eng-review 성능 결정: 고정 간격 + 최대 타임아웃)
POLL_INTERVAL_SEC = 3
POLL_MAX_ATTEMPTS = 40          # 3s * 40 = 최대 120초

# job 완료/실패 상태
_DONE_OK   = {"completed"}
_DONE_FAIL = {"failed", "nsfw", "canceled", "cancelled"}

# 의류 타입 → try-on 카테고리 매핑 (프롬프트 문구용)
CATEGORY_MAP = {
    "top":       "upper_body",
    "bottom":    "lower_body",
    "dress":     "dresses",
    "accessory": "upper_body",
}


def to_category(garment_type: str) -> str:
    return CATEGORY_MAP.get(garment_type, "upper_body")


def is_available() -> bool:
    """키 존재 + httpx 설치 여부로 가용성 판단."""
    if not API_KEY:
        return False
    try:
        import httpx  # noqa: F401
    except ImportError:
        return False
    return True


def _resolve_verify():
    """
    TLS 검증 인증서 결정:
      1. HIGGSFIELD_CA_BUNDLE (사내 루트 CA)
      2. certifi 기본 번들
    항상 인증서 검증 수행 (보안 유지).
    """
    ca = os.environ.get("HIGGSFIELD_CA_BUNDLE", "").strip()
    if ca and os.path.exists(ca):
        return ca
    try:
        import certifi
        return certifi.where()
    except Exception:
        return True


def _headers() -> dict:
    return {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "Authorization": f"Bearer {API_KEY}",
    }


def _client():
    import httpx
    return httpx.Client(verify=_resolve_verify(), timeout=60)


# ── MCP JSON-RPC 격리 계층 ─────────────────────────────────────
def _parse_sse(text: str) -> dict:
    """streamable-HTTP 응답(SSE 또는 JSON)에서 JSON-RPC 페이로드 추출."""
    if not text:
        return {}
    for line in text.splitlines():
        if line.startswith("data:"):
            return json.loads(line[5:].strip())
    try:
        return json.loads(text)
    except Exception:
        return {}


def _rpc(client, method: str, params=None, rid=None) -> dict:
    body = {"jsonrpc": "2.0", "method": method}
    if rid is not None:
        body["id"] = rid
    if params is not None:
        body["params"] = params
    resp = client.post(MCP_URL, headers=_headers(), json=body)
    resp.raise_for_status()
    return _parse_sse(resp.text)


def _session(client):
    """initialize + initialized 핸드셰이크."""
    _rpc(client, "initialize", {
        "protocolVersion": "2024-11-05",
        "capabilities": {},
        "clientInfo": {"name": "laongen", "version": "1.0"},
    }, rid=1)
    _rpc(client, "notifications/initialized")


def _tool(client, name: str, args: dict, rid: int) -> dict:
    """tools/call → structuredContent. isError면 예외(크레딧 부족은 BillingError)."""
    data = _rpc(client, "tools/call", {"name": name, "arguments": args}, rid)
    res  = data.get("result", {})
    if res.get("isError"):
        sc   = res.get("structuredContent") or {}
        body = json.dumps(sc) + json.dumps(res.get("content", ""))
        if sc.get("recovery_tool") == "show_plans_and_credits" or \
           "insufficient" in body.lower() or "credit" in body.lower():
            raise GenerativeBillingError(
                "Higgsfield 크레딧이 부족합니다. 계정에서 충전 후 다시 시도하세요."
            )
        raise HiggsfieldUnavailable(f"{name} 실패: {sc or res.get('content')}")
    return res.get("structuredContent") or {}


# ── try-on 플로우 단계 ─────────────────────────────────────────
def _upload(client, images: list) -> list:
    """images: [(PIL, content_type, filename)] → [media_id].

    media_upload(presigned) → 각 upload_url에 PUT → media_confirm.
    """
    import httpx

    files = [{"filename": fn, "content_type": ct} for _, ct, fn in images]
    up = _tool(client, "media_upload", {"files": files}, rid=2)
    uploads = up.get("uploads") or []
    if len(uploads) != len(images):
        raise HiggsfieldUnavailable(f"media_upload 응답 불일치: {up}")

    for u, (img, ct, _fn) in zip(uploads, images):
        buf = io.BytesIO()
        img.convert("RGB").save(buf, format="PNG" if ct == "image/png" else "JPEG")
        r = httpx.put(u["upload_url"], headers={"Content-Type": u["content_type"]},
                      content=buf.getvalue(), timeout=60, verify=_resolve_verify())
        r.raise_for_status()

    ids = [u["media_id"] for u in uploads]
    _tool(client, "media_confirm", {"type": "image", "media_ids": ids}, rid=3)
    return ids


def _build_prompt(items: list, subject: str = "model") -> str:
    """items: [(garment_desc, category), ...] → try-on 프롬프트.

    subject: "model"(실제 모델) | "mannequin"(드레스폼 마네킹 디스플레이).
    """
    worn = "; ".join(f"the exact {desc} on the {cat}" for desc, cat in items)
    if subject == "mannequin":
        scene = (
            f"Professional retail product display photograph of the EXACT same "
            f"headless tailor's dress-form mannequin from the first reference image "
            f"(keep it a mannequin display — no head, no skin, no face), dressed in "
            f"{worn}"
        )
    else:
        scene = (
            f"Full-body fashion photo of the model from the first reference image "
            f"wearing {worn}"
        )
    return (
        f"{scene}, preserving every garment detail (collar, buttons, pattern, "
        f"texture, hardware). Neutral studio background, front view, photorealistic."
    )


def _generate(client, media_ids: list, prompt: str) -> str:
    """generate_image → job_id."""
    gen = _tool(client, "generate_image", {"params": {
        "model": TRYON_MODEL,
        "prompt": prompt,
        "aspect_ratio": ASPECT,
        "medias": [{"value": mid, "role": "image"} for mid in media_ids],
    }}, rid=4)
    results = gen.get("results") or []
    if not results or not results[0].get("id"):
        raise HiggsfieldUnavailable(f"generate_image 결과 없음: {gen}")
    return results[0]["id"]


def _poll(client, job_id: str) -> str:
    """job_display 고정 간격 폴링 → 결과 이미지 URL."""
    for _ in range(POLL_MAX_ATTEMPTS):
        disp    = _tool(client, "job_display", {"id": job_id}, rid=5)
        results = disp.get("results") or []
        status  = str(results[0].get("status", "")).lower() if results else ""

        if status in _DONE_OK:
            res = (results[0].get("results") or {})
            url = res.get("rawUrl") or res.get("minUrl")
            if not url:
                raise HiggsfieldUnavailable(f"완료됐으나 결과 URL 없음: {disp}")
            return url
        if status in _DONE_FAIL:
            raise HiggsfieldUnavailable(f"job 실패 (status={status})")

        time.sleep(POLL_INTERVAL_SEC)

    raise HiggsfieldUnavailable(
        f"폴링 타임아웃 ({POLL_INTERVAL_SEC * POLL_MAX_ATTEMPTS}초 초과)"
    )


def _download(url: str) -> Image.Image:
    """결과 URL(공개 CDN) → PIL 이미지."""
    import httpx
    resp = httpx.get(url, timeout=60, verify=_resolve_verify())
    resp.raise_for_status()
    return Image.open(io.BytesIO(resp.content))


# ── 공개 API ──────────────────────────────────────────────────
def generate_tryon_multi(
    garments:       list,
    model_template: Image.Image,
    subject:        str = "model",
) -> Image.Image:
    """
    Higgsfield(MCP)로 다중 의류 풀코디 착용 컷 생성 (단일-호출 다중입력).

    2026-06-09 검증: 모델+의류 N장을 한 번에 입력하면 Leffa 순차 체이닝의
    drift 없이 풀코디가 보존된다(설계 문서 Open Q1).

    Args:
        garments       : [(garment_img, garment_desc, category), ...]
        model_template : 기준 figure 사진 (실제 모델 또는 마네킹)
        subject        : "model"(실제 모델) | "mannequin"(드레스폼 디스플레이)

    Returns:
        착용 결과 이미지 (PIL RGB)

    Raises:
        HiggsfieldUnavailable : 키 없음 / 입력 없음 / job 실패 / 타임아웃 / 네트워크 오류
        GenerativeBillingError: 크레딧 부족
    """
    if not API_KEY:
        raise HiggsfieldUnavailable("HIGGSFIELD_API_KEY가 설정되지 않았습니다.")
    if not garments:
        raise HiggsfieldUnavailable("의류 입력이 비어 있습니다.")

    try:
        import httpx  # noqa: F401
    except ImportError:
        raise HiggsfieldUnavailable("httpx 패키지가 설치되지 않았습니다.")

    # 업로드 순서 = [기준 figure, *의류], 프롬프트의 "first reference image"가 figure
    images = [(model_template.convert("RGB"), "image/jpeg", "figure.jpg")]
    items  = []
    for i, (g, desc, cat) in enumerate(garments):
        images.append((g.convert("RGB"), "image/png", f"garment{i}.png"))
        items.append((desc, cat))

    try:
        with _client() as client:
            _session(client)
            media_ids = _upload(client, images)
            job_id    = _generate(client, media_ids, _build_prompt(items, subject))
            url       = _poll(client, job_id)
            return _download(url).convert("RGB")
    except GenerativeBillingError:
        raise
    except HiggsfieldUnavailable:
        raise
    except Exception as e:
        status = getattr(getattr(e, "response", None), "status_code", None)
        if status == 402:
            raise GenerativeBillingError("Higgsfield 크레딧이 부족합니다.")
        raise HiggsfieldUnavailable(f"Higgsfield(MCP) 호출 실패: {e}")


def generate_tryon(
    garment_img:    Image.Image,
    model_template: Image.Image,
    garment_desc:   str = "clothing",
    category:       str = "upper_body",
) -> Image.Image:
    """단일 의류 착용 컷 생성 (generate_tryon_multi의 하위 호환 래퍼)."""
    return generate_tryon_multi([(garment_img, garment_desc, category)], model_template)
