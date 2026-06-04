"""이미지 전처리 (동적 해상도, 의류 정렬, 포즈 정규화)

개선 사항:
- 의류 자동 정렬 (주축 기반 회전)
- 포즈 정규화 (좌우 정렬)
- 동적 해상도 선택
- 의류 스트레칭 보정
"""
from pathlib import Path
import numpy as np
from PIL import Image, ImageOps
from loguru import logger

from pipeline.hardware import detect_hardware

TARGET_W, TARGET_H = 768, 1024


def _target_size() -> tuple[int, int]:
    """현재 PC 사양에 맞는 처리 해상도 (가로, 세로)."""
    try:
        return detect_hardware()["process_size"]
    except Exception:
        return (TARGET_W, TARGET_H)


def _load_and_fix(path: Path) -> Image.Image:
    """이미지 로드 및 방향 보정 (EXIF)."""
    img = Image.open(path)
    img = ImageOps.exif_transpose(img)
    return img.convert("RGB")


def _remove_bg(img: Image.Image) -> Image.Image:
    """배경 제거 (rembg)."""
    try:
        from rembg import remove
        result = remove(img)
        bg = Image.new("RGB", result.size, (255, 255, 255))
        bg.paste(result, mask=result.split()[3])
        return bg
    except ImportError:
        logger.warning("rembg 미설치 — 배경 제거 스킵")
        return img


def _align_garment(garment_img: Image.Image) -> Image.Image:
    """의류 자동 정렬 (PCA 기반 주축 회전).
    
    의류가 수직으로 정렬되도록 회전합니다.
    """
    try:
        from scipy import ndimage
        
        # 마스크 생성
        gray = np.array(garment_img.convert("L"))
        mask = (gray < 240).astype(bool)
        
        if not mask.any():
            return garment_img
        
        # 전경 픽셀 좌표
        coords = np.column_stack(np.where(mask))
        if len(coords) < 10:
            return garment_img
        
        # PCA로 주축 각도 계산
        mean = coords.mean(axis=0)
        centered = coords - mean
        cov = centered.T @ centered
        
        eigenvalues, eigenvectors = np.linalg.eigh(cov)
        main_axis = eigenvectors[:, -1]
        angle_rad = np.arctan2(main_axis[0], main_axis[1])
        angle_deg = np.degrees(angle_rad)
        
        # 15도 이상 회전 필요할 때만 수행
        if abs(angle_deg) > 2:
            logger.debug(f"의류 정렬 수행: {angle_deg:.1f}°")
            garment_img = garment_img.rotate(-angle_deg, expand=False, fillcolor=255)
        
        return garment_img
    except Exception as e:
        logger.warning(f"의류 정렬 실패: {e}")
        return garment_img


def _normalize_pose(mannequin_img: Image.Image, pose_data: dict) -> Image.Image:
    """포즈 정규화 (좌우 정렬).
    
    마네킹의 어깨가 수평이 되도록 정렬합니다.
    """
    try:
        if "keypoints" not in pose_data:
            return mannequin_img
        
        kp = pose_data["keypoints"]
        
        # 어깨 키포인트 (COCO: 2=R shoulder, 5=L shoulder)
        if kp[2, 2] > 0.3 and kp[5, 2] > 0.3:
            shoulder_l = kp[5, :2]
            shoulder_r = kp[2, :2]
            
            dy = shoulder_r[1] - shoulder_l[1]
            dx = shoulder_r[0] - shoulder_l[0]
            
            angle_rad = np.arctan2(dy, dx)
            angle_deg = np.degrees(angle_rad)
            
            if abs(angle_deg) > 2:
                logger.debug(f"포즈 정렬 수행: {angle_deg:.1f}°")
                mannequin_img = mannequin_img.rotate(-angle_deg, expand=False, fillcolor=255)
        
        return mannequin_img
    except Exception as e:
        logger.warning(f"포즈 정렬 실패: {e}")
        return mannequin_img


def _resize_pad(img: Image.Image, w: int = TARGET_W, h: int = TARGET_H, 
                align_bottom: bool = False) -> Image.Image:
    """이미지 리사이징 및 패딩 (종횡비 유지).
    
    인자:
        align_bottom: True이면 하단 정렬, False이면 중앙 정렬
    """
    # 종횡비 유지하며 캔버스에 맞게 스케일 — 축소·확대 모두 허용.
    # (PIL thumbnail()은 축소만 하므로, 타깃보다 작은 원본이 작게 깔리는 문제 방지)
    scale = min(w / img.width, h / img.height)
    new_w = max(1, round(img.width * scale))
    new_h = max(1, round(img.height * scale))
    img = img.resize((new_w, new_h), Image.LANCZOS)

    canvas = Image.new("RGB", (w, h), (255, 255, 255))
    x_offset = (w - new_w) // 2
    y_offset = (h - new_h) if align_bottom else (h - new_h) // 2

    canvas.paste(img, (x_offset, y_offset))
    return canvas


def _stretch_correct(garment_img: Image.Image, target_aspect: float) -> Image.Image:
    """의류 스트레칭 보정 (종횡비 정규화).
    
    의류가 과도하게 확대되거나 축소되지 않도록 보정합니다.
    """
    try:
        current_aspect = garment_img.width / garment_img.height
        aspect_ratio = target_aspect / current_aspect
        
        # 비율이 0.8~1.2 범위 내이면 무시
        if 0.8 <= aspect_ratio <= 1.2:
            return garment_img
        
        # 너무 찌그러진 경우 정정
        if aspect_ratio < 0.8:
            new_width = int(garment_img.width * 1.1)
            garment_img = garment_img.resize((new_width, garment_img.height), Image.LANCZOS)
        elif aspect_ratio > 1.2:
            new_height = int(garment_img.height * 1.1)
            garment_img = garment_img.resize((garment_img.width, new_height), Image.LANCZOS)
        
        logger.debug(f"스트레칭 보정: {aspect_ratio:.2f}")
        return garment_img
    except Exception as e:
        logger.warning(f"스트레칭 보정 실패: {e}")
        return garment_img


def preprocess_images(
    mannequin_path: Path,
    garment_path: Path,
    remove_background: bool = False,
    pose_data: dict = None,
) -> tuple[Image.Image, Image.Image, dict]:
    """이미지 전처리 (고도화된 버전).
    
    반환:
        (처리된_마네킹, 처리된_의류, 전처리_메타데이터)
    """
    mannequin = _load_and_fix(mannequin_path)
    garment = _load_and_fix(garment_path)
    
    meta = {
        "remove_background": remove_background,
        "garment_aligned": False,
        "pose_normalized": False,
    }
    
    if remove_background:
        logger.info("배경 제거 적용")
        garment = _remove_bg(garment)
    
    # 의류 자동 정렬
    garment_original_aspect = garment.width / garment.height
    garment = _align_garment(garment)
    meta["garment_aligned"] = True
    
    # 스트레칭 보정
    garment = _stretch_correct(garment, garment_original_aspect)
    
    # 포즈 정규화 (마네킹)
    if pose_data is not None:
        mannequin = _normalize_pose(mannequin, pose_data)
        meta["pose_normalized"] = True
    
    # 리사이징 및 패딩
    w, h = _target_size()
    mannequin = _resize_pad(mannequin, w=w, h=h, align_bottom=True)
    garment = _resize_pad(garment, w=w, h=h, align_bottom=False)
    
    logger.debug(
        f"전처리 완료 mannequin={mannequin.size} garment={garment.size} "
        f"meta={meta}"
    )
    
    return mannequin, garment, meta

