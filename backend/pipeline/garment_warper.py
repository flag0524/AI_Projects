import numpy as np
import cv2
from PIL import Image
from backend.pipeline.segmenter import get_garment_mask, get_garment_bbox


GarmentType = str  # "top" | "bottom" | "dress" | "accessory"


def _compute_control_points(
    src_bbox: tuple, dst_bbox: tuple
) -> tuple[np.ndarray, np.ndarray]:
    """소스/타겟 경계박스로부터 8개 제어점 쌍을 생성."""
    sx1, sy1, sx2, sy2 = src_bbox
    dx1, dy1, dx2, dy2 = dst_bbox

    src_pts = np.float32([
        [sx1, sy1], [(sx1 + sx2) / 2, sy1], [sx2, sy1],
        [sx1, (sy1 + sy2) / 2],              [sx2, (sy1 + sy2) / 2],
        [sx1, sy2], [(sx1 + sx2) / 2, sy2], [sx2, sy2],
    ])
    dst_pts = np.float32([
        [dx1, dy1], [(dx1 + dx2) / 2, dy1], [dx2, dy1],
        [dx1, (dy1 + dy2) / 2],              [dx2, (dy1 + dy2) / 2],
        [dx1, dy2], [(dx1 + dx2) / 2, dy2], [dx2, dy2],
    ])
    return src_pts, dst_pts


def _tps_warp(
    garment: np.ndarray,
    src_pts: np.ndarray,
    dst_pts: np.ndarray,
    canvas_size: int,
) -> np.ndarray:
    """OpenCV TPS 변환으로 의류 이미지를 목표 위치로 와핑."""
    tps = cv2.createThinPlateSplineShapeTransformer()
    src = src_pts.reshape(1, -1, 2)
    dst = dst_pts.reshape(1, -1, 2)
    matches = [cv2.DMatch(i, i, 0) for i in range(len(src_pts))]
    tps.estimateTransformation(dst, src, matches)

    h, w = garment.shape[:2]
    warped = tps.warpImage(garment)
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

    if garment_type == "top":
        dst_region = body_bounds["top"]
    elif garment_type == "bottom":
        dst_region = body_bounds["bottom"]
    elif garment_type == "dress":
        dst_region = body_bounds["full"]
    else:
        dst_region = body_bounds.get("full", (0, 0, canvas_size, canvas_size))

    # 타겟 박스에 여유 마진 적용 (5%)
    margin = int(canvas_size * 0.02)
    dx1 = max(0, dst_region[0] - margin)
    dy1 = max(0, dst_region[1] - margin)
    dx2 = min(canvas_size, dst_region[2] + margin)
    dy2 = min(canvas_size, dst_region[3] + margin)

    src_pts, dst_pts = _compute_control_points(src_bbox, (dx1, dy1, dx2, dy2))
    warped = _tps_warp(garment_arr, src_pts, dst_pts, canvas_size)

    return Image.fromarray(warped, "RGBA")


def fallback_affine_warp(
    garment_img: Image.Image,
    garment_type: GarmentType,
    body_bounds: dict,
    canvas_size: int = 512,
) -> Image.Image:
    """TPS 실패 시 단순 affine 리사이즈 + 배치 폴백."""
    if garment_type == "top":
        dst = body_bounds["top"]
    elif garment_type == "bottom":
        dst = body_bounds["bottom"]
    else:
        dst = body_bounds["full"]

    dx1, dy1, dx2, dy2 = dst
    target_w = max(1, dx2 - dx1)
    target_h = max(1, dy2 - dy1)

    garment_rgba = garment_img.convert("RGBA").resize(
        (target_w, target_h), Image.LANCZOS
    )
    canvas = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
    canvas.paste(garment_rgba, (dx1, dy1), garment_rgba)
    return canvas
