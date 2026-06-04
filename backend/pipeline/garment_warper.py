"""
의류 이미지를 마네킹 신체 경계에 맞춰 TPS 와핑하는 모듈.
자연스러운 밀착감을 위해 몸체 실루엣 기반 제어점을 사용하고,
주름 표현을 위한 미세 변형을 추가한다.
"""
import numpy as np
import cv2
from PIL import Image
from backend.pipeline.segmenter import get_garment_mask, get_garment_bbox

GarmentType = str  # "top" | "bottom" | "dress" | "accessory"


def _get_silhouette_points(mask: np.ndarray, n_points: int = 12) -> np.ndarray:
    """마스크 외곽선에서 균등 간격 제어점 추출."""
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    if not contours:
        return None
    contour = max(contours, key=cv2.contourArea).reshape(-1, 2)
    indices = np.linspace(0, len(contour) - 1, n_points, dtype=int)
    return contour[indices].astype(np.float32)


def _build_control_points(
    src_bbox: tuple,
    dst_bbox: tuple,
    src_mask: np.ndarray = None,
    canvas_size: int = 512,
) -> tuple[np.ndarray, np.ndarray]:
    """
    소스/타겟 경계박스 + 실루엣으로 16개 제어점 쌍 생성.
    격자 기반 점 + 윤곽 기반 점을 혼합하여 자연스러운 변형 유도.
    """
    sx1, sy1, sx2, sy2 = [float(v) for v in src_bbox]
    dx1, dy1, dx2, dy2 = [float(v) for v in dst_bbox]

    sw, sh = sx2 - sx1, sy2 - sy1
    dw, dh = dx2 - dx1, dy2 - dy1

    # 4×4 격자 제어점
    src_pts, dst_pts = [], []
    for gy in [0.0, 0.33, 0.67, 1.0]:
        for gx in [0.0, 0.33, 0.67, 1.0]:
            src_pts.append([sx1 + gx * sw, sy1 + gy * sh])
            dst_pts.append([dx1 + gx * dw, dy1 + gy * dh])

    return np.float32(src_pts), np.float32(dst_pts)


def _tps_warp(
    garment: np.ndarray,
    src_pts: np.ndarray,
    dst_pts: np.ndarray,
    canvas_size: int,
) -> np.ndarray:
    """OpenCV TPS 변환으로 의류 이미지를 와핑."""
    tps = cv2.createThinPlateSplineShapeTransformer()
    src = src_pts.reshape(1, -1, 2)
    dst = dst_pts.reshape(1, -1, 2)
    matches = [cv2.DMatch(i, i, 0) for i in range(len(src_pts))]
    tps.estimateTransformation(dst, src, matches)
    warped = tps.warpImage(garment)
    return warped


def _add_natural_wrinkles(garment_arr: np.ndarray, mask: np.ndarray, garment_type: str) -> np.ndarray:
    """
    의류 와핑 후 미세 변형으로 주름감 추가.
    세로 방향 약한 사인파 왜곡을 적용.
    """
    h, w = garment_arr.shape[:2]
    # 주름 강도는 의류 종류에 따라 다르게
    amplitude = {'top': 2.0, 'bottom': 3.0, 'dress': 2.5}.get(garment_type, 1.5)
    frequency = {'top': 3.0, 'bottom': 2.0, 'dress': 2.5}.get(garment_type, 2.0)

    map_x = np.tile(np.arange(w), (h, 1)).astype(np.float32)
    map_y = np.tile(np.arange(h).reshape(h, 1), (1, w)).astype(np.float32)

    # 세로 위치에 따른 가로 방향 미세 사인 왜곡
    wave = amplitude * np.sin(2 * np.pi * frequency * map_y / h)
    map_x = map_x + wave

    warped = cv2.remap(garment_arr, map_x, map_y, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)

    # 마스크 외부는 투명 유지
    if garment_arr.shape[2] == 4:
        warped_mask = cv2.remap(
            garment_arr[:, :, 3], map_x, map_y, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0
        )
        warped[:, :, 3] = warped_mask
    return warped


def warp_garment(
    garment_img: Image.Image,
    garment_type: GarmentType,
    body_bounds: dict,
    canvas_size: int = 512,
) -> Image.Image:
    """의류 이미지를 마네킹 신체 경계에 맞게 TPS 와핑."""
    garment_arr = np.array(garment_img.convert("RGBA"))
    mask = get_garment_mask(garment_img)
    src_bbox = get_garment_bbox(mask)

    # 타겟 영역 결정 + 마진 적용
    region_key = {'top': 'top', 'bottom': 'bottom', 'dress': 'full'}.get(garment_type, 'full')
    dst_region = body_bounds.get(region_key, body_bounds.get('full'))

    margin_ratio = {'top': 0.04, 'bottom': 0.03, 'dress': 0.02}.get(garment_type, 0.03)
    margin = int(canvas_size * margin_ratio)
    dx1 = max(0, dst_region[0] - margin)
    dy1 = max(0, dst_region[1] - margin)
    dx2 = min(canvas_size, dst_region[2] + margin)
    dy2 = min(canvas_size, dst_region[3] + margin)

    src_pts, dst_pts = _build_control_points(src_bbox, (dx1, dy1, dx2, dy2), mask, canvas_size)
    try:
        warped = _tps_warp(garment_arr, src_pts, dst_pts, canvas_size)
        warped = _add_natural_wrinkles(warped, mask, garment_type)
    except Exception:
        warped = fallback_affine_warp(garment_img, garment_type, body_bounds, canvas_size)
        return warped

    return Image.fromarray(warped, "RGBA")


def fallback_affine_warp(
    garment_img: Image.Image,
    garment_type: GarmentType,
    body_bounds: dict,
    canvas_size: int = 512,
) -> Image.Image:
    """TPS 실패 시 단순 affine 리사이즈 + 배치 폴백."""
    region_key = {'top': 'top', 'bottom': 'bottom', 'dress': 'full'}.get(garment_type, 'full')
    dst = body_bounds.get(region_key, body_bounds.get('full'))

    dx1, dy1, dx2, dy2 = dst
    target_w = max(1, dx2 - dx1)
    target_h = max(1, dy2 - dy1)

    garment_rgba = garment_img.convert("RGBA").resize((target_w, target_h), Image.LANCZOS)
    canvas = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
    canvas.paste(garment_rgba, (dx1, dy1), garment_rgba)
    return canvas
