"""
LaonGEN 생성형 프로바이더 — try-on diffusion 클라우드 API 클라이언트.

지원 백엔드:
  - Replicate (IDM-VTON, CatVTON 등 호스팅 모델)
  - 환경변수 REPLICATE_API_TOKEN 으로 인증

마네킹/옷걸이 제품 사진을 실제 모델 착용 컷으로 변환하는 흐름:
  1. 분리된 의류 이미지(garment) 준비
  2. 표준 모델 템플릿(human) 이미지 준비
  3. try-on diffusion 호출 → 자연스러운 착용 컷 생성

API 키가 없으면 GenerativeUnavailable 예외를 던져 절차적 폴백을 유도한다.
"""
import os
import io
import base64
import time
from PIL import Image


class GenerativeUnavailable(Exception):
    """생성형 백엔드를 사용할 수 없을 때 (키 없음, 네트워크 오류 등)."""
    pass


# ── 설정 ──────────────────────────────────────────────────────
REPLICATE_TOKEN = os.environ.get("REPLICATE_API_TOKEN", "").strip()

# IDM-VTON: 사람 이미지 + 의류 이미지 → 착용 결과
# https://replicate.com/cuuupid/idm-vton
IDM_VTON_VERSION = "cuuupid/idm-vton:c871bb9b046607b680449ecbae55fd8c6d945e0a1948644bf2361b3d021d3ff4"


def is_available() -> bool:
    """생성형 백엔드 사용 가능 여부."""
    return bool(REPLICATE_TOKEN)


def _pil_to_data_uri(img: Image.Image, fmt: str = "PNG") -> str:
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format=fmt)
    b64 = base64.b64encode(buf.getvalue()).decode()
    return f"data:image/{fmt.lower()};base64,{b64}"


def generate_tryon(
    garment_img:    Image.Image,
    model_template: Image.Image,
    garment_desc:   str = "clothing",
    category:       str = "upper_body",
    timeout_sec:    int = 90,
) -> Image.Image:
    """
    try-on diffusion으로 모델 착용 컷 생성.

    Args:
        garment_img    : 배경 제거된 의류 이미지 (RGB/RGBA)
        model_template : 표준 모델 사진 (중립 포즈, 정면)
        garment_desc   : 의류 설명 텍스트 프롬프트
        category       : "upper_body" | "lower_body" | "dresses"
        timeout_sec    : 최대 대기 시간

    Returns:
        생성된 착용 컷 (PIL RGB)

    Raises:
        GenerativeUnavailable: 키 없음 또는 호출 실패
    """
    if not REPLICATE_TOKEN:
        raise GenerativeUnavailable("REPLICATE_API_TOKEN 환경변수가 설정되지 않았습니다.")

    try:
        import replicate
    except ImportError:
        raise GenerativeUnavailable("replicate 패키지가 설치되지 않았습니다. (pip install replicate)")

    try:
        client = replicate.Client(api_token=REPLICATE_TOKEN)
        output = client.run(
            IDM_VTON_VERSION,
            input={
                "human_img":   _pil_to_data_uri(model_template),
                "garm_img":    _pil_to_data_uri(garment_img),
                "garment_des": garment_desc,
                "category":    category,
                "crop":        False,
                "seed":        42,
                "steps":       30,
            },
        )

        # output은 URL 또는 FileOutput
        result_url = str(output[0]) if isinstance(output, (list, tuple)) else str(output)

        import urllib.request
        with urllib.request.urlopen(result_url, timeout=timeout_sec) as resp:
            data = resp.read()
        return Image.open(io.BytesIO(data)).convert("RGB")

    except Exception as e:
        raise GenerativeUnavailable(f"생성형 API 호출 실패: {e}")


# ── 의류 타입 → IDM-VTON 카테고리 매핑 ──────────────────────────
CATEGORY_MAP = {
    "top":       "upper_body",
    "bottom":    "lower_body",
    "dress":     "dresses",
    "accessory": "upper_body",
}


def to_category(garment_type: str) -> str:
    return CATEGORY_MAP.get(garment_type, "upper_body")
