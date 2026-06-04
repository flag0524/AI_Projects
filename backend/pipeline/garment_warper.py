"""
의류를 마네킹 몸체 윤곽에 자연스럽게 감싸는 와핑 모듈.

핵심 원리:
  - 마네킹 배경제거본의 알파 채널로 실제 몸체 윤곽선을 추출
  - 옷의 좌/우/중앙 가장자리를 몸체 윤곽에 맞게 TPS 변형
  - 원통형 입체감 셰이딩으로 몸에 감싸진 느낌 부여
  - 중력/자연 드레이핑 효과 추가
"""
import numpy as np
import cv2
from PIL import Image
from backend.pipeline.segmenter import get_garment_mask, get_garment_bbox

GarmentType = str


# ─────────────────────────────────────────────────────────────
# 몸체 윤곽 추출
# ─────────────────────────────────────────────────────────────
def extract_body_edges(mannequin_mask: np.ndarray, y1: int, y2: int, n: int = 16):
    """
    마네킹 마스크에서 높이별 좌·우 윤곽 x 좌표를 샘플링.
    n개의 균등 높이에서 몸체의 왼쪽·오른쪽 경계를 반환.
    """
    ys     = np.linspace(y1, y2, n, dtype=int)
    h, w   = mannequin_mask.shape
    lefts  = []
    rights = []
    for y in ys:
        y = int(np.clip(y, 0, h - 1))
        row = mannequin_mask[y, :]
        nz  = np.where(row > 30)[0]
        if len(nz) >= 2:
            lefts.append(int(nz[0]))
            rights.append(int(nz[-1]))
        else:
            mid = w // 2
            span = (y2 - y1) // 4 if y2 > y1 else 50
            lefts.append(mid - span)
            rights.append(mid + span)
    return ys, np.array(lefts), np.array(rights)


def extract_garment_edges(garment_mask: np.ndarray, sy1: int, sy2: int, n: int = 16):
    """의류 마스크에서 높이별 좌·우 윤곽 x 좌표를 샘플링."""
    ys     = np.linspace(sy1, sy2, n, dtype=int)
    h, w   = garment_mask.shape
    lefts  = []
    rights = []
    for y in ys:
        y = int(np.clip(y, 0, h - 1))
        row = garment_mask[y, :]
        nz  = np.where(row > 30)[0]
        if len(nz) >= 2:
            lefts.append(int(nz[0]))
            rights.append(int(nz[-1]))
        else:
            lefts.append(w // 4)
            rights.append(w * 3 // 4)
    return ys, np.array(lefts), np.array(rights)


# ─────────────────────────────────────────────────────────────
# 원통형 입체감 셰이딩
# ─────────────────────────────────────────────────────────────
def apply_cylindrical_shading(
    garment_arr: np.ndarray,
    mask: np.ndarray,
    body_bounds: dict,
    garment_type: str,
) -> np.ndarray:
    """
    원통형 몸체에 감싸진 느낌의 조명 그라디언트 적용.
    중앙 가장 밝고, 좌우 가장자리로 갈수록 어두워짐.
    """
    h, w  = garment_arr.shape[:2]
    ls    = body_bounds.get("left_shoulder",  (w * 0.3, h * 0.2))
    rs    = body_bounds.get("right_shoulder", (w * 0.7, h * 0.2))
    cx    = (ls[0] + rs[0]) / 2.0
    half  = max(abs(rs[0] - ls[0]) / 2.0, 60)

    # x 방향 코사인 그라디언트
    xs       = np.tile(np.arange(w, dtype=np.float32), (h, 1))
    dist_x   = np.clip(np.abs(xs - cx) / half, 0, 1)
    shade_x  = np.cos(dist_x * np.pi / 2) * 0.14 + 0.86   # 0.86 ~ 1.00

    # y 방향 그라디언트 (상단·하단 약간 어둡게 — 접힘 느낌)
    mask_rows = np.where(mask.max(axis=1) > 30)[0]
    if len(mask_rows) > 1:
        gy1, gy2 = mask_rows[0], mask_rows[-1]
        gh       = max(gy2 - gy1, 1)
        ys       = np.tile(np.arange(h, dtype=np.float32).reshape(h, 1), (1, w))
        y_norm   = np.clip((ys - gy1) / gh, 0, 1)
        shade_y  = np.sin(y_norm * np.pi) * 0.10 + 0.90    # 0.90 ~ 1.00
    else:
        shade_y = np.ones((h, w), np.float32)

    shading  = (shade_x * shade_y).astype(np.float32)
    mask_f   = (mask > 30).astype(np.float32)

    result   = garment_arr.copy().astype(np.float32)
    for c in range(3):
        result[:, :, c] = np.where(
            mask_f > 0,
            np.clip(result[:, :, c] * shading, 0, 255),
            result[:, :, c],
        )
    return result.astype(np.uint8)


# ─────────────────────────────────────────────────────────────
# 몸체 윤곽 기반 TPS 와핑
# ─────────────────────────────────────────────────────────────
def _tps_warp(garment: np.ndarray, src_pts: np.ndarray, dst_pts: np.ndarray) -> np.ndarray:
    tps     = cv2.createThinPlateSplineShapeTransformer()
    src_r   = src_pts.reshape(1, -1, 2)
    dst_r   = dst_pts.reshape(1, -1, 2)
    matches = [cv2.DMatch(i, i, 0) for i in range(len(src_pts))]
    tps.estimateTransformation(dst_r, src_r, matches)
    return tps.warpImage(garment)


def warp_to_body_contour(
    garment_img: Image.Image,
    mannequin_nobg: Image.Image,
    garment_type: GarmentType,
    body_bounds: dict,
    canvas_size: int = 512,
) -> Image.Image:
    """
    마네킹 몸체 윤곽에 의류 실루엣을 맞춰 와핑.
    옷이 몸에 '감싸진' 자연스러운 착용감을 만든다.
    """
    garment_arr  = np.array(garment_img.convert("RGBA"))
    garment_mask = garment_arr[:, :, 3]
    src_bbox     = get_garment_bbox(garment_mask)

    # 마네킹 마스크 추출
    mann_arr  = np.array(mannequin_nobg.convert("RGBA"))
    mann_mask = mann_arr[:, :, 3]

    # 타겟 영역 결정
    region_key = {"top": "top", "bottom": "bottom", "dress": "full"}.get(garment_type, "full")
    dst        = body_bounds.get(region_key, body_bounds.get("full", (0, 0, canvas_size, canvas_size)))
    dx1, dy1, dx2, dy2 = [int(v) for v in dst]

    margin = int(canvas_size * 0.03)
    dx1 = max(0,           dx1 - margin)
    dy1 = max(0,           dy1 - margin)
    dx2 = min(canvas_size, dx2 + margin)
    dy2 = min(canvas_size, dy2 + margin)

    n   = 14   # 샘플 포인트 수
    sx1, sy1, sx2, sy2 = [int(v) for v in src_bbox]

    # 몸체 윤곽 샘플링
    body_ys, body_l, body_r = extract_body_edges(mann_mask, dy1, dy2, n)

    # 의류 윤곽 샘플링
    gar_ys,  gar_l,  gar_r  = extract_garment_edges(garment_mask, sy1, sy2, n)

    # 제어점 구성: 좌 / 중 / 우
    src_pts, dst_pts = [], []
    for i in range(n):
        gy     = float(gar_ys[i])
        dy_val = float(body_ys[i])
        g_cx   = (gar_l[i]  + gar_r[i])  / 2.0
        b_cx   = (body_l[i] + body_r[i]) / 2.0

        # 좌 가장자리
        src_pts.append([float(gar_l[i]),  gy])
        dst_pts.append([float(body_l[i]), dy_val])

        # 우 가장자리
        src_pts.append([float(gar_r[i]),  gy])
        dst_pts.append([float(body_r[i]), dy_val])

        # 중앙
        src_pts.append([g_cx, gy])
        dst_pts.append([b_cx, dy_val])

        # 좌¼, 우¼ (곡률 보간)
        src_pts.append([(gar_l[i]  * 3 + gar_r[i])  / 4.0, gy])
        dst_pts.append([(body_l[i] * 3 + body_r[i]) / 4.0, dy_val])
        src_pts.append([(gar_l[i]  + gar_r[i]  * 3) / 4.0, gy])
        dst_pts.append([(body_l[i] + body_r[i] * 3) / 4.0, dy_val])

    try:
        warped = _tps_warp(garment_arr, np.float32(src_pts), np.float32(dst_pts))
    except Exception:
        # TPS 실패 시 affine 폴백
        return fallback_affine_warp(garment_img, garment_type, body_bounds, canvas_size)

    # 원통형 셰이딩 적용 (착용감)
    warped_mask = warped[:, :, 3]
    warped = apply_cylindrical_shading(warped, warped_mask, body_bounds, garment_type)

    return Image.fromarray(warped, "RGBA")


# ─────────────────────────────────────────────────────────────
# 기존 호환 함수 (mannequin_nobg 없을 때 폴백)
# ─────────────────────────────────────────────────────────────
def warp_garment(
    garment_img: Image.Image,
    garment_type: GarmentType,
    body_bounds: dict,
    canvas_size: int = 512,
    mannequin_nobg: Image.Image = None,
) -> Image.Image:
    """
    mannequin_nobg가 있으면 몸체 윤곽 와핑, 없으면 affine 폴백.
    """
    if mannequin_nobg is not None:
        try:
            return warp_to_body_contour(
                garment_img, mannequin_nobg, garment_type, body_bounds, canvas_size
            )
        except Exception:
            pass
    return fallback_affine_warp(garment_img, garment_type, body_bounds, canvas_size)


def fallback_affine_warp(
    garment_img: Image.Image,
    garment_type: GarmentType,
    body_bounds: dict,
    canvas_size: int = 512,
) -> Image.Image:
    region_key = {"top": "top", "bottom": "bottom", "dress": "full"}.get(garment_type, "full")
    dst        = body_bounds.get(region_key, body_bounds.get("full", (0, 0, canvas_size, canvas_size)))
    dx1, dy1, dx2, dy2 = [int(v) for v in dst]

    tw = max(1, dx2 - dx1)
    th = max(1, dy2 - dy1)

    garment_rgba = garment_img.convert("RGBA").resize((tw, th), Image.LANCZOS)
    canvas       = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
    canvas.paste(garment_rgba, (dx1, dy1), garment_rgba)
    return canvas
