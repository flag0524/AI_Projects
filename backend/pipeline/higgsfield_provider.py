"""
Higgsfield 생성형 프로바이더 — try-on 착용 컷 클라우드 API 클라이언트.

설계: docs/superpowers/specs/2026-06-08-higgsfield-provider-design.md

흐름 (비동기 job 모델):
  ┌────────────────────────────────────────────────────────────┐
  │ 1. 의류 + 모델 템플릿 업로드 (REST)                         │
  │ 2. 생성 job 제출 → job_id 수신                              │
  │ 3. 고정 간격(POLL_INTERVAL) 폴링 → 완료/실패/타임아웃      │
  │ 4. 결과 이미지 다운로드 → PIL 반환                          │
  └────────────────────────────────────────────────────────────┘

범위 (eng-review 2026-06-08 확정):
  - 단일 의류만 (순차 체이닝은 NOT in scope — baseline drift 확인됨)
  - 키 없으면 is_available()==False → laongen_engine 캐스케이드 폴백

크레딧 부족(402)은 generative_provider.GenerativeBillingError를 재사용해
기존 402 처리 경로(api/generate.py)와 일관되게 동작한다.

환경변수:
  HIGGSFIELD_API_KEY    : Higgsfield REST 인증 키 (없으면 비활성)
  HIGGSFIELD_API_BASE   : REST 베이스 URL (기본 https://api.higgsfield.ai)
  HIGGSFIELD_TRYON_MODEL: try-on 모델 id (기본 nano-banana-pro)
  HIGGSFIELD_CA_BUNDLE  : 사내 프록시 SSL 가로채기용 루트 CA (.pem/.crt)

REST 스펙 출처 (api.higgsfield.ai 공개 문서):
  - POST /v1/generations  (Bearer 인증, JSON: task/model/prompt/input_image)
  - GET  /v1/generations/{id}  상태 Queued/InProgress/Completed/Failed/NSFW/Cancelled
  - 결과: images[0].url

NOTE [Open Q2 — 부분 확정]:
  전송 계약(엔드포인트/인증/폴링/결과 형태)은 공개 문서로 확정됨.
  단 try-on 특화 매핑 2가지는 **라이브 키로 검증 필요한 가정**:
    (A) try-on 모델 id (HIGGSFIELD_TRYON_MODEL)
    (B) 의류+모델 2장 입력 방식 — 현재 input_images:[model, garment] 가정
  검증 후 _submit_job 의 payload만 조정하면 된다.
"""
import os
import io
import time
import base64
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
API_BASE    = os.environ.get("HIGGSFIELD_API_BASE", "https://api.higgsfield.ai").strip()
TRYON_MODEL = os.environ.get("HIGGSFIELD_TRYON_MODEL", "nano-banana-pro").strip()

# 고정 간격 폴링 (eng-review 성능 결정: 고정 간격 + 최대 타임아웃)
POLL_INTERVAL_SEC = 3
POLL_MAX_ATTEMPTS = 40          # 3s * 40 = 최대 120초

# 의류 타입 → Higgsfield try-on 카테고리 매핑
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


def _client():
    import httpx
    return httpx.Client(
        base_url=API_BASE,
        headers={"Authorization": f"Bearer {API_KEY}"},
        verify=_resolve_verify(),
        timeout=30,
    )


def _pil_to_data_uri(img: Image.Image, fmt: str = "PNG") -> str:
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format=fmt)
    return f"data:image/{fmt.lower()};base64,{base64.b64encode(buf.getvalue()).decode()}"


def _raise_for_billing(status_code: int, body: str):
    """402/크레딧 부족이면 결제 예외(기존 경로와 일관)."""
    if status_code == 402 or "insufficient credit" in body.lower() or "billing" in body.lower():
        raise GenerativeBillingError(
            "Higgsfield 크레딧이 부족합니다. 계정에서 충전 후 다시 시도하세요."
        )


# ── REST 격리 계층 (api.higgsfield.ai 공개 스펙) ────────────────
_DONE_OK   = {"completed"}
_DONE_FAIL = {"failed", "nsfw", "cancelled"}


def _submit_job(client, garment_img: Image.Image, model_template: Image.Image,
                garment_desc: str, category: str) -> str:
    """POST /v1/generations → job_id.

    가정[Open Q2-B]: 의류+모델 2장을 input_images 배열로 전달.
    라이브 검증 후 페이로드 조정.
    """
    payload = {
        "task":  "image-to-image",
        "model": TRYON_MODEL,
        "prompt": (
            f"A full-body fashion photo of a model wearing this exact {garment_desc} "
            f"on the {category}, preserving every garment detail (collar, buttons, "
            f"pattern, texture, hardware). Neutral studio background, front view."
        ),
        "input_images": [
            _pil_to_data_uri(model_template),
            _pil_to_data_uri(garment_img),
        ],
    }
    resp = client.post("/v1/generations", json=payload)
    resp.raise_for_status()
    data = resp.json()
    job_id = data.get("id") or data.get("request_id")
    if not job_id:
        raise HiggsfieldUnavailable(f"job_id 없음: {data}")
    return job_id


def _poll_job(client, job_id: str) -> str:
    """GET /v1/generations/{id} 고정 간격 폴링 → 결과 이미지 URL.

    Completed → URL, Failed/NSFW/Cancelled → Unavailable, 상한 초과 → Unavailable.
    """
    for _ in range(POLL_MAX_ATTEMPTS):
        resp = client.get(f"/v1/generations/{job_id}")
        resp.raise_for_status()
        data   = resp.json()
        status = str(data.get("status", "")).lower()

        if status in _DONE_OK:
            images = data.get("images") or []
            if not images or not images[0].get("url"):
                raise HiggsfieldUnavailable(f"완료됐으나 결과 URL 없음: {data}")
            return images[0]["url"]
        if status in _DONE_FAIL:
            raise HiggsfieldUnavailable(f"job 실패 (status={status})")

        time.sleep(POLL_INTERVAL_SEC)

    raise HiggsfieldUnavailable(
        f"폴링 타임아웃 ({POLL_INTERVAL_SEC * POLL_MAX_ATTEMPTS}초 초과)"
    )


def _download(client, result_ref: str) -> Image.Image:
    """결과 URL → PIL 이미지."""
    resp = client.get(result_ref)
    resp.raise_for_status()
    return Image.open(io.BytesIO(resp.content))


# ── 공개 API ──────────────────────────────────────────────────
def generate_tryon(
    garment_img:    Image.Image,
    model_template: Image.Image,
    garment_desc:   str = "clothing",
    category:       str = "upper_body",
) -> Image.Image:
    """
    Higgsfield로 단일 의류 착용 컷 생성.

    Args:
        garment_img    : 의류 이미지 (단일)
        model_template : 표준 모델 사진
        garment_desc   : 의류 설명 프롬프트
        category       : "upper_body" | "lower_body" | "dresses"

    Returns:
        착용 결과 이미지 (PIL RGB)

    Raises:
        HiggsfieldUnavailable : 키 없음 / job 실패 / 타임아웃 / 네트워크 오류
        GenerativeBillingError: 크레딧 부족 (402)
    """
    if not API_KEY:
        raise HiggsfieldUnavailable("HIGGSFIELD_API_KEY가 설정되지 않았습니다.")

    try:
        import httpx
    except ImportError:
        raise HiggsfieldUnavailable("httpx 패키지가 설치되지 않았습니다.")

    try:
        with _client() as client:
            job_id     = _submit_job(client, garment_img, model_template, garment_desc, category)
            result_ref = _poll_job(client, job_id)
            return _download(client, result_ref).convert("RGB")
    except GenerativeBillingError:
        raise
    except HiggsfieldUnavailable:
        raise
    except Exception as e:
        # httpx HTTPStatusError 등에서 402 감지
        status = getattr(getattr(e, "response", None), "status_code", None)
        body   = getattr(getattr(e, "response", None), "text", "") or str(e)
        if status is not None:
            _raise_for_billing(status, body)
        raise HiggsfieldUnavailable(f"Higgsfield 호출 실패: {e}")
