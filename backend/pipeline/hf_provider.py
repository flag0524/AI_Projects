"""
LaonGEN 무료 생성형 백엔드 — HuggingFace Spaces (gradio_client).

기본 백엔드: franciszzj/Leffa
  - 상의(upper_body) / 하의(lower_body) / 원피스(dresses) 모두 지원
  - 무료 (HF 토큰의 ZeroGPU 할당량 사용)
  - viton_hd / dress_code 모델 선택 가능

대체 백엔드: yisol/IDM-VTON (상의 전용, 익명 가능)

환경변수:
  HF_TRYON_SPACE : 사용할 Space ID (기본 franciszzj/Leffa)
  HF_TOKEN       : HuggingFace 토큰 (ZeroGPU 할당량용, 무료 발급)
"""
import os
import tempfile
from PIL import Image

# Windows 시스템 인증서로 SSL 가로채기 환경 통과
try:
    import truststore
    truststore.inject_into_ssl()
except Exception:
    pass


class HFUnavailable(Exception):
    """HuggingFace Space 호출 불가."""
    pass


HF_SPACE = os.environ.get("HF_TRYON_SPACE", "franciszzj/Leffa").strip()
HF_TOKEN = os.environ.get("HF_TOKEN", "").strip() or None

# 의류 타입 → Leffa vt_garment_type 매핑
_LEFFA_CATEGORY = {
    "top":       "upper_body",
    "bottom":    "lower_body",
    "dress":     "dresses",
    "accessory": "upper_body",
}

_client = None  # 지연 초기화 캐시


def is_available() -> bool:
    """gradio_client 설치 + 토큰 존재 여부로 가용성 판단."""
    try:
        import gradio_client  # noqa: F401
    except ImportError:
        return False
    # Leffa 등 ZeroGPU Space는 토큰 필요
    return bool(HF_TOKEN) or HF_SPACE == "yisol/IDM-VTON"


def _get_client():
    global _client
    if _client is not None:
        return _client
    try:
        from gradio_client import Client
        if HF_TOKEN:
            try:
                _client = Client(HF_SPACE, token=HF_TOKEN)
            except TypeError:
                _client = Client(HF_SPACE, hf_token=HF_TOKEN)
        else:
            _client = Client(HF_SPACE)
        return _client
    except Exception as e:
        raise HFUnavailable(f"HF Space 연결 실패({HF_SPACE}): {e}")


def _save_temp(img: Image.Image) -> str:
    f = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    img.convert("RGB").save(f.name, "PNG")
    f.close()
    return f.name


def _extract_path(result):
    """gradio 반환값에서 이미지 파일 경로 추출."""
    g = result[0] if isinstance(result, (list, tuple)) else result
    return g["path"] if isinstance(g, dict) else g


def generate_tryon(
    human_img:    Image.Image,
    garment_img:  Image.Image,
    garment_type: str = "top",
    garment_des:  str = "clothing",
    step:         int = 30,
    scale:        float = 2.5,
    seed:         int = 42,
) -> Image.Image:
    """
    Leffa(또는 IDM-VTON)로 try-on 생성.

    Args:
        human_img    : 사람 이미지 (의류를 입힐 대상)
        garment_img  : 입힐 의류 이미지
        garment_type : "top" | "bottom" | "dress" | "accessory"
        garment_des  : 의류 설명 (IDM-VTON에서 사용)

    Returns:
        착용 결과 이미지 (PIL RGB)

    Raises:
        HFUnavailable: Space 연결/호출 실패
    """
    try:
        from gradio_client import handle_file
    except ImportError:
        raise HFUnavailable("gradio_client가 설치되지 않았습니다.")

    client     = _get_client()
    human_path = _save_temp(human_img)
    garm_path  = _save_temp(garment_img)

    try:
        if HF_SPACE == "yisol/IDM-VTON":
            # IDM-VTON: 상의 전용
            result = client.predict(
                {"background": handle_file(human_path), "layers": [], "composite": None},
                handle_file(garm_path),
                garment_des, True, False, step, seed,
                api_name="/tryon",
            )
        else:
            # Leffa: 상의/하의/원피스 지원
            category = _LEFFA_CATEGORY.get(garment_type, "upper_body")
            # viton_hd 모델이 일반 모델 사진에 가장 안정적으로 적용됨
            # (dress_code는 DressCode 도메인 전용이라 일반 템플릿엔 미적용 빈번)
            model_type = "viton_hd"
            result = client.predict(
                handle_file(human_path),   # src_image_path
                handle_file(garm_path),    # ref_image_path
                False,                     # ref_acceleration
                step,                      # step
                scale,                     # scale
                seed,                      # seed
                model_type,                # vt_model_type
                category,                  # vt_garment_type
                False,                     # vt_repaint
                api_name="/leffa_predict_vt",
            )
        return Image.open(_extract_path(result)).convert("RGB")
    except Exception as e:
        raise HFUnavailable(f"HF try-on 호출 실패({HF_SPACE}): {e}")
    finally:
        for p in (human_path, garm_path):
            try:
                os.unlink(p)
            except Exception:
                pass
