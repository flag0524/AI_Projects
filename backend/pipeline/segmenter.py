import numpy as np
import cv2
from PIL import Image


def get_body_mask(img: Image.Image) -> np.ndarray:
    """RGBA 이미지에서 알파 채널 기반 신체 마스크(0/255)를 반환."""
    arr = np.array(img.convert("RGBA"))
    alpha = arr[:, :, 3]
    _, mask = cv2.threshold(alpha, 10, 255, cv2.THRESH_BINARY)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
    return mask


def get_garment_mask(img: Image.Image) -> np.ndarray:
    """의류 RGBA 이미지에서 의류 마스크(0/255)를 반환."""
    arr = np.array(img.convert("RGBA"))
    alpha = arr[:, :, 3]
    _, mask = cv2.threshold(alpha, 10, 255, cv2.THRESH_BINARY)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=1)
    return mask


def get_garment_bbox(mask: np.ndarray) -> tuple[int, int, int, int]:
    """의류 마스크에서 바운딩 박스 (x1, y1, x2, y2) 추출."""
    coords = cv2.findNonZero(mask)
    if coords is None:
        h, w = mask.shape
        return (0, 0, w, h)
    x, y, bw, bh = cv2.boundingRect(coords)
    return (x, y, x + bw, y + bh)
