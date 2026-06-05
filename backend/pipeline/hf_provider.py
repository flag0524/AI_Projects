"""
LaonGEN 무료 생성형 백엔드 — HuggingFace Spaces (gradio_client).

공개 IDM-VTON Space(yisol/IDM-VTON)를 무료로 호출하여
마네킹/모델 이미지에 의류를 입힌 try-on 결과를 생성한다.

- 결제 불필요 (완전 무료)
- Space가 잠들어 있으면 첫 호출 시 웨이크업 대기 발생 가능
- 큐 대기 시간 변동 있음

환경변수:
  HF_TRYON_SPACE : 사용할 Space ID (기본 yisol/IDM-VTON)
  HF_TOKEN       : (선택) 비공개 Space 또는 레이트리밋 완화용 토큰
"""
import os
import io
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


HF_SPACE = os.environ.get("HF_TRYON_SPACE", "yisol/IDM-VTON").strip()
HF_TOKEN = os.environ.get("HF_TOKEN", "").strip() or None

_client = None  # 지연 초기화 캐시


def is_available() -> bool:
    """gradio_client 설치 여부로 가용성 판단 (Space는 공개라 키 불필요)."""
    try:
        import gradio_client  # noqa: F401
        return True
    except ImportError:
        return False


def _get_client():
    global _client
    if _client is not None:
        return _client
    try:
        from gradio_client import Client
        # gradio_client 버전별 토큰 인자명 차이 대응 (token / hf_token)
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
    """PIL 이미지를 임시 PNG로 저장하고 경로 반환."""
    f = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    img.convert("RGB").save(f.name, "PNG")
    f.close()
    return f.name


def generate_tryon(
    human_img:    Image.Image,
    garment_img:  Image.Image,
    garment_des:  str = "clothing",
    denoise_steps: int = 30,
    seed:         int = 42,
    auto_mask:    bool = True,
    crop:         bool = False,
) -> Image.Image:
    """
    IDM-VTON Space로 try-on 생성.

    Args:
        human_img   : 사람/마네킹 이미지 (의류를 입힐 대상)
        garment_img : 입힐 의류 이미지 (배경 제거 권장)
        garment_des : 의류 텍스트 설명
        denoise_steps, seed, auto_mask, crop : 모델 파라미터

    Returns:
        착용 결과 이미지 (PIL RGB)

    Raises:
        HFUnavailable: Space 연결/호출 실패
    """
    try:
        from gradio_client import handle_file
    except ImportError:
        raise HFUnavailable("gradio_client가 설치되지 않았습니다.")

    client = _get_client()

    human_path = _save_temp(human_img)
    garm_path  = _save_temp(garment_img)

    try:
        result = client.predict(
            {
                "background": handle_file(human_path),
                "layers":     [],
                "composite":  None,
            },
            handle_file(garm_path),
            garment_des,
            auto_mask,
            crop,
            denoise_steps,
            seed,
            api_name="/tryon",
        )
        # result = (output_path, masked_path)
        output_path = result[0] if isinstance(result, (list, tuple)) else result
        return Image.open(output_path).convert("RGB")
    except Exception as e:
        raise HFUnavailable(f"HF try-on 호출 실패: {e}")
    finally:
        for p in (human_path, garm_path):
            try:
                os.unlink(p)
            except Exception:
                pass
