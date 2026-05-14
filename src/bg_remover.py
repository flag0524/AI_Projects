"""
bg_remover.py — 배경 제거 모듈
rembg 라이브러리를 사용하여 상품 이미지에서 배경을 제거합니다.
원본 픽셀은 절대 변형하지 않습니다. (알파채널 추가만 허용)
"""
from pathlib import Path
from io import BytesIO

from PIL import Image
from loguru import logger

try:
    from rembg import remove, new_session
    REMBG_AVAILABLE = True
except ImportError:
    REMBG_AVAILABLE = False
    logger.warning("rembg가 설치되지 않았습니다. pip install rembg 후 재실행하세요.")

from config import BG_REMOVE_MODEL


# 모델 세션을 전역으로 한 번만 로드 (속도 최적화)
_session = None

def _get_session():
    global _session
    if _session is None and REMBG_AVAILABLE:
        logger.info(f"rembg 모델 로딩 중: {BG_REMOVE_MODEL}")
        _session = new_session(BG_REMOVE_MODEL)
    return _session


def remove_background(image_path: Path) -> Image.Image | None:
    """
    이미지에서 배경을 제거하고 RGBA PIL 이미지를 반환합니다.

    원칙: 원본 픽셀(RGB)은 변형하지 않음. 알파(투명도) 채널만 추가.

    Args:
        image_path: 원본 이미지 파일 경로

    Returns:
        RGBA PIL.Image (배경=투명, 의류=원본 픽셀 유지)
        실패 시 None 반환
    """
    if not REMBG_AVAILABLE:
        logger.error("rembg 사용 불가 — 설치 후 재실행하세요.")
        return None

    if not image_path.exists():
        logger.error(f"이미지 파일 없음: {image_path}")
        return None

    try:
        # 원본 이미지 로드
        original = Image.open(image_path).convert("RGBA")

        # rembg로 배경 제거 (PIL Image → bytes → remove → PIL Image)
        buf_in = BytesIO()
        original.save(buf_in, format="PNG")
        buf_in.seek(0)

        session = _get_session()
        buf_out = BytesIO(remove(buf_in.read(), session=session))
        result = Image.open(buf_out).convert("RGBA")

        # ─── 원본 RGB 보존 검증 ───
        # rembg가 RGB를 건드리지 않았는지 확인하기 위해
        # 알파>0인 픽셀의 RGB를 원본에서 복원 (완전 보존 보장)
        result = _restore_original_rgb(original, result)

        # 품질 검사
        coverage = _check_coverage(result)
        if coverage < 0.05:
            logger.warning(f"배경 제거 품질 낮음 ({coverage:.1%}): {image_path.name}")
        else:
            logger.debug(f"배경 제거 완료 {image_path.name} (커버리지: {coverage:.1%})")

        return result

    except Exception as e:
        logger.error(f"배경 제거 실패 [{image_path.name}]: {e}")
        return None


def _restore_original_rgb(original: Image.Image, mask_result: Image.Image) -> Image.Image:
    """
    rembg 결과의 알파 마스크를 유지하면서 RGB는 원본 이미지로 완전 복원합니다.
    이것이 '이미지 디테일 불변 원칙'의 핵심입니다.
    """
    import numpy as np

    orig_arr   = np.array(original.convert("RGBA"))    # 원본 RGBA
    result_arr = np.array(mask_result.convert("RGBA"))  # rembg 결과 RGBA

    # 크기가 다를 경우 맞춤
    if orig_arr.shape != result_arr.shape:
        mask_result = mask_result.resize(original.size, Image.LANCZOS)
        result_arr  = np.array(mask_result.convert("RGBA"))

    # 알파 채널만 rembg 결과를 사용, RGB는 원본 그대로
    combined = orig_arr.copy()
    combined[:, :, 3] = result_arr[:, :, 3]  # 알파만 교체

    return Image.fromarray(combined.astype("uint8"), "RGBA")


def _check_coverage(img: Image.Image) -> float:
    """알파>0인 픽셀 비율을 반환합니다. (의류가 차지하는 면적)"""
    import numpy as np
    arr = np.array(img)
    total = arr.shape[0] * arr.shape[1]
    foreground = (arr[:, :, 3] > 10).sum()
    return foreground / total if total > 0 else 0.0


def save_transparent(img: Image.Image, output_path: Path) -> bool:
    """투명 배경 PNG로 저장합니다."""
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        img.save(output_path, format="PNG", optimize=False)
        return True
    except Exception as e:
        logger.error(f"투명 PNG 저장 실패 [{output_path}]: {e}")
        return False
