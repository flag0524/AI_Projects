"""..."""
from __future__ import annotations
from pathlib import Path
import numpy as np
from PIL import Image
from loguru import logger

# LIP 클래스 -> 실용 그룹 매핑
UPPER_CLASSES  = {4, 5, 6}
LOWER_CLASSES  = {8, 9}
ARM_CLASSES    = {12}
LEG_CLASSES    = {11}
FACE_CLASSES   = {3}
HAIR_CLASSES   = {2}


def _schp_parse(image: Image.Image) -> np.ndarray | None:
    """..."""
    try:
        # SCHP HuggingFace 버전 (schp-pascal-person-part 등)
        from transformers import SegformerImageProcessor, SegformerForSemanticSegmentation
        import torch

        model_id = "mattmdjaga/segformer_b2_clothes"
        processor = SegformerImageProcessor.from_pretrained(model_id)
        model = SegformerForSemanticSegmentation.from_pretrained(model_id)
        model.eval()

        inputs = processor(images=image, return_tensors="pt")
        with torch.no_grad():
            logits = model(**inputs).logits  # (1, C, H/4, W/4)

        seg = logits.argmax(dim=1).squeeze().numpy().astype(np.uint8)
        # 원본 크기로 업샘플
        seg_img = Image.fromarray(seg).resize(image.size, Image.NEAREST)
        return np.array(seg_img)

    except Exception as e:
        logger.debug(f"SCHP/Segformer 불가: {e}")
        return None


def _simple_parse(image: Image.Image) -> np.ndarray:
    """..."""
    img = np.array(image).astype(np.float32)
    h, w = img.shape[:2]
    seg = np.zeros((h, w), dtype=np.uint8)

    # 피부색 (R>G>B, R>120)
    r, g, b = img[..., 0], img[..., 1], img[..., 2]
    skin = (r > 120) & (r > g) & (r > b) & ((r - g) > 10)

    # 밝기 기반: 어두우면 의류 영역
    gray = 0.299 * r + 0.587 * g + 0.114 * b
    dark = gray < 180

    # 상단 1/3: 상의 영역
    upper_region = np.zeros_like(dark, dtype=bool)
    upper_region[:h // 3 * 2, :] = True
    seg[dark & upper_region & ~skin] = 4   # Upper-clothes

    # 하단 1/3: 하의 영역
    lower_region = ~upper_region
    seg[dark & lower_region & ~skin] = 8   # Pants

    # 피부
    seg[skin] = 12  # Arms (근사)

    return seg


def parse_body(image: Image.Image) -> dict:
    """..."""
    seg = _schp_parse(image)
    if seg is None:
        logger.warning("SCHP 미설치 — 간단한 색상 파싱으로 폴백")
        seg = _simple_parse(image)

    def class_mask(classes: set) -> Image.Image:
        m = np.zeros_like(seg, dtype=np.uint8)
        for c in classes:
            m[seg == c] = 255
        return Image.fromarray(m, mode="L")

    masks = {
        "upper": class_mask(UPPER_CLASSES),
        "lower": class_mask(LOWER_CLASSES),
        "arms":  class_mask(ARM_CLASSES),
        "legs":  class_mask(LEG_CLASSES),
        "face":  class_mask(FACE_CLASSES),
        "hair":  class_mask(HAIR_CLASSES),
    }
    logger.debug("신체 파싱 완료")
    return {"seg_map": seg, "masks": masks}


def make_agnostic_map(
    mannequin: Image.Image,
    body_masks: dict,
    category: str,
    keypoints: np.ndarray,
) -> Image.Image:
    """..."""
    import cv2

    result = np.array(mannequin.copy())
    h, w = result.shape[:2]

    # 교체할 마스크 결정
    erase_masks = []
    if category in ("top", "dress"):
        erase_masks.append(np.array(body_masks["upper"]))
        erase_masks.append(np.array(body_masks["arms"]))
    if category in ("bottom", "dress"):
        erase_masks.append(np.array(body_masks["lower"]))
        erase_masks.append(np.array(body_masks["legs"]))

    if not erase_masks:
        return mannequin

    combined = np.zeros((h, w), dtype=np.uint8)
    for m in erase_masks:
        combined = np.maximum(combined, m)

    # 키포인트 기반으로 영역 확장 (마스크가 너무 작을 때 보정)
    kp = keypoints
    if category in ("top", "dress") and combined[:h//2].sum() < 1000:
        # 어깨~허리 BBox로 최소 영역 보장
        top_y = max(0, int(kp[1, 1]) - 10) if kp[1, 2] > 0.3 else h // 8
        bot_y = int((kp[8, 1] + kp[11, 1]) / 2) if kp[8, 2] > 0.3 else h // 2
        lx = max(0, int(kp[5, 0]) - 20) if kp[5, 2] > 0.3 else w // 3
        rx = min(w, int(kp[2, 0]) + 20) if kp[2, 2] > 0.3 else w * 2 // 3
        combined[top_y:bot_y, lx:rx] = 255

    # 팽창으로 경계 부드럽게
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15))
    combined = cv2.dilate(combined, kernel, iterations=1)

    # 회색으로 채우기
    result[combined > 127] = [128, 128, 128]

    return Image.fromarray(result)
