"""
스캔라인 기반 의류 와핑 모듈 (v4 — 완전 재작성)

핵심 알고리즘: 스캔라인 수평 리매핑
  - 각 출력 행(row)을 독립적으로 처리
  - 마네킹 몸체의 해당 행 너비에 맞게 의류 픽셀을 수평 스케일
  - 수직 방향은 의류 높이 → 목표 영역 높이로 균등 매핑
  - TPS보다 훨씬 자연스럽고 빠름, 실패가 없음

착용감 향상:
  - 원통형 조명 (중앙 밝음 → 가장자리 어두움)
  - 상단·하단 미세 어두움 (접힘 느낌)
  - 색상 조화 (마네킹 조명에 맞게 미세 보정)
"""
import numpy as np
import cv2
from PIL import Image
from backend.pipeline.segmenter import get_garment_mask, get_garment_bbox


# ─────────────────────────────────────────────────────────
# 의류 프로파일 추출
# ─────────────────────────────────────────────────────────
def _garment_profile(mask: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    각 행에서 의류 좌·우 경계 및 중앙 x 반환.
    유효하지 않은 행은 인접 행 값으로 보간.
    """
    h, w = mask.shape
    ls   = np.zeros(h, np.float32)
    rs   = np.full(h, float(w), np.float32)
    has  = np.zeros(h, bool)

    for y in range(h):
        nz = np.where(mask[y] > 30)[0]
        if len(nz) >= 2:
            ls[y]  = float(nz[0])
            rs[y]  = float(nz[-1])
            has[y] = True

    # 유효하지 않은 행을 앞뒤 값으로 채움
    if not has.any():
        ls[:] = w * 0.25
        rs[:] = w * 0.75
    else:
        first = int(np.argmax(has))
        last  = int(len(has) - 1 - np.argmax(has[::-1]))
        for y in range(h):
            if not has[y]:
                prev_y = max(first, y - 1)
                next_y = min(last,  y + 1)
                ls[y]  = (ls[prev_y] + ls[next_y]) / 2
                rs[y]  = (rs[prev_y] + rs[next_y]) / 2

    return ls, rs, (ls + rs) / 2.0


# ─────────────────────────────────────────────────────────
# 원통형 입체감 셰이딩
# ─────────────────────────────────────────────────────────
def _apply_shading(garment_arr: np.ndarray, mask: np.ndarray,
                   cx: float, half_w: float) -> np.ndarray:
    """
    원통형 몸체에 감싸인 느낌의 조명 그라디언트.
    • x: 중앙 최고 밝기 → 좌우 가장자리로 cos 감소
    • y: 상·하단 접힘 표현 (sin 그라디언트)
    """
    h, w  = garment_arr.shape[:2]
    xs    = np.tile(np.arange(w, dtype=np.float32), (h, 1))
    dist  = np.clip(np.abs(xs - cx) / max(half_w, 1), 0, 1)
    sx    = np.cos(dist * np.pi / 2) * 0.16 + 0.84   # 0.84 ~ 1.00

    rows  = np.where(mask.max(axis=1) > 30)[0]
    if len(rows) > 1:
        gy1, gy2 = rows[0], rows[-1]
        ys        = np.tile(np.arange(h, dtype=np.float32).reshape(h,1),(1,w))
        yn        = np.clip((ys - gy1) / max(gy2 - gy1, 1), 0, 1)
        sy        = np.sin(yn * np.pi) * 0.10 + 0.90  # 0.90 ~ 1.00
    else:
        sy        = np.ones((h, w), np.float32)

    shading  = (sx * sy).astype(np.float32)
    mf       = (mask > 30).astype(np.float32)
    result   = garment_arr.copy().astype(np.float32)
    for c in range(3):
        result[:,:,c] = np.where(mf > 0,
                                 np.clip(result[:,:,c] * shading, 0, 255),
                                 result[:,:,c])
    return result.astype(np.uint8)


def _color_harmonize(garment_arr: np.ndarray, mask: np.ndarray,
                     target_arr: np.ndarray) -> np.ndarray:
    """
    의류를 마네킹 조명에 맞게 Lab 밝기 기반 미세 보정.
    """
    mf = mask > 30
    if mf.sum() < 50:
        return garment_arr

    g_bgr  = garment_arr[:,:,:3].copy()
    t_bgr  = target_arr[:,:,:3]
    g_lab  = cv2.cvtColor(g_bgr,  cv2.COLOR_BGR2Lab).astype(np.float32)
    t_lab  = cv2.cvtColor(t_bgr,  cv2.COLOR_BGR2Lab).astype(np.float32)

    # 의류 영역 평균 밝기와 타겟 마네킹 전체 밝기 차이만 보정
    t_rows = np.where(target_arr[:,:,3] > 30) if target_arr.shape[2]==4 else (slice(None), slice(None))
    delta  = float(np.clip(
        np.mean(t_lab[:,:,0]) - np.mean(g_lab[:,:,0][mf]),
        -20, 20
    )) * 0.25  # 25%만 보정 (과보정 방지)

    result = garment_arr.copy()
    g_lab[:,:,0] = np.clip(g_lab[:,:,0] + delta, 0, 255)
    corrected = cv2.cvtColor(g_lab.astype(np.uint8), cv2.COLOR_Lab2BGR)
    result[:,:,:3] = np.where(mf[:,:,np.newaxis], corrected, g_bgr)
    return result


# ─────────────────────────────────────────────────────────
# 핵심: 스캔라인 기반 와핑
# ─────────────────────────────────────────────────────────
def scanline_warp(
    garment_arr:  np.ndarray,
    garment_mask: np.ndarray,
    body_mask:    np.ndarray,
    dst_region:   tuple,
    canvas_size:  int = 512,
) -> np.ndarray:
    """
    스캔라인 수평 리매핑 와핑.

    각 출력 행에서:
    1. 마네킹 마스크에서 몸체 너비 [body_l, body_r] 읽기
    2. 비례에 맞는 의류 소스 행 계산
    3. 의류 픽셀을 몸체 너비로 cv2.resize 후 해당 위치에 배치

    결과: 의류가 몸체 윤곽에 정확히 감싸인 이미지
    """
    dx1, dy1, dx2, dy2 = [int(v) for v in dst_region]
    dy1 = max(0, dy1);  dy2 = min(canvas_size, dy2)
    dx1 = max(0, dx1);  dx2 = min(canvas_size, dx2)
    n_dst = dy2 - dy1
    if n_dst <= 0:
        return np.zeros((canvas_size, canvas_size, 4), np.uint8)

    # 의류 유효 범위
    gar_rows = np.where(garment_mask.max(axis=1) > 30)[0]
    if len(gar_rows) < 2:
        return np.zeros((canvas_size, canvas_size, 4), np.uint8)
    gy1, gy2 = int(gar_rows[0]), int(gar_rows[-1])
    n_src = max(gy2 - gy1, 1)

    # 의류 프로파일 (행별 좌·우 경계)
    g_ls, g_rs, _ = _garment_profile(garment_mask)

    # 출력 캔버스
    result = np.zeros((canvas_size, canvas_size, 4), np.uint8)

    for di in range(n_dst):
        dy = dy1 + di
        if dy >= canvas_size:
            break

        # 비례 소스 행
        t  = di / max(n_dst - 1, 1)
        sy = gy1 + int(t * n_src)
        sy = min(sy, garment_arr.shape[0] - 1)

        # ── 몸체 너비 (이 행에서) ──────────────────────────────
        if dy < body_mask.shape[0]:
            bnz = np.where(body_mask[dy] > 30)[0]
            if len(bnz) >= 2:
                bl, br = int(bnz[0]), int(bnz[-1])
            else:
                bl, br = dx1, dx2
        else:
            bl, br = dx1, dx2

        # 몸체가 너무 좁은 경우 스킵
        bw = br - bl
        if bw < 4:
            continue

        # ── 의류 픽셀 추출 ─────────────────────────────────────
        gl = max(0, int(g_ls[sy]))
        gr = min(garment_arr.shape[1] - 1, int(g_rs[sy]))
        gw = gr - gl
        if gw < 2:
            continue

        gar_strip = garment_arr[sy, gl:gr+1]  # (gw, 4)

        # ── 몸체 너비로 수평 스케일 ────────────────────────────
        scaled = cv2.resize(
            gar_strip.reshape(1, -1, 4),
            (bw, 1),
            interpolation=cv2.INTER_LINEAR,
        )[0]  # (bw, 4)

        # ── 결과에 배치 ────────────────────────────────────────
        px1 = max(0, bl)
        px2 = min(canvas_size, br)
        pw  = px2 - px1
        if pw <= 0:
            continue
        result[dy, px1:px2] = scaled[:pw]

    return result


# ─────────────────────────────────────────────────────────
# 공개 API
# ─────────────────────────────────────────────────────────
def warp_garment(
    garment_img:    Image.Image,
    garment_type:   str,
    body_regions:   dict,
    canvas_size:    int          = 512,
    mannequin_nobg: Image.Image  = None,
    body_mask:      np.ndarray   = None,
) -> Image.Image:
    """
    의류 이미지를 마네킹 몸체에 착용된 형태로 변환.

    Args:
        garment_img   : 배경제거된 의류 RGBA 이미지
        garment_type  : "top" | "bottom" | "dress" | "accessory"
        body_regions  : detect_body_regions() 결과 dict
        canvas_size   : 출력 크기
        mannequin_nobg: 배경제거된 마네킹 (body_mask 계산용)
        body_mask     : 직접 전달할 경우 사용 (없으면 mannequin_nobg에서 추출)
    """
    garment_arr  = np.array(garment_img.convert("RGBA"))
    garment_arr  = cv2.cvtColor(garment_arr, cv2.COLOR_RGBA2BGRA)
    garment_mask = get_garment_mask(garment_img)

    # ── 몸체 마스크 준비 ───────────────────────────────────────
    if body_mask is None and mannequin_nobg is not None:
        nb_arr    = np.array(mannequin_nobg.convert("RGBA"))
        body_mask = nb_arr[:, :, 3]
        _, body_mask = cv2.threshold(body_mask, 20, 255, cv2.THRESH_BINARY)
        body_mask = cv2.morphologyEx(body_mask, cv2.MORPH_CLOSE,
                                     cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (11, 11)))

    if body_mask is None:
        body_mask = np.full((canvas_size, canvas_size), 255, np.uint8)

    # ── 목표 영역 결정 ─────────────────────────────────────────
    region_key = {"top": "top", "bottom": "bottom", "dress": "full"}.get(garment_type, "full")
    dst        = body_regions.get(region_key,
                 body_regions.get("full", (0, 0, canvas_size, canvas_size)))

    # ── 스캔라인 와핑 ──────────────────────────────────────────
    warped = scanline_warp(garment_arr, garment_mask, body_mask, dst, canvas_size)

    # BGRA → RGBA
    if warped.shape[2] == 4:
        warped = cv2.cvtColor(warped, cv2.COLOR_BGRA2RGBA)

    # ── 원통형 셰이딩 ──────────────────────────────────────────
    warped_mask = warped[:, :, 3]
    cx   = float(np.mean([dst[0], dst[2]]))
    hw   = float(dst[2] - dst[0]) / 2.0

    warped_bgra = cv2.cvtColor(warped, cv2.COLOR_RGBA2BGRA)
    warped_bgra = _apply_shading(warped_bgra, warped_mask, cx, hw)

    # ── 색상 조화 ──────────────────────────────────────────────
    if mannequin_nobg is not None:
        mann_arr = cv2.cvtColor(np.array(mannequin_nobg.convert("RGBA")),
                                cv2.COLOR_RGBA2BGRA)
        warped_bgra = _color_harmonize(warped_bgra, warped_mask, mann_arr)

    result = cv2.cvtColor(warped_bgra, cv2.COLOR_BGRA2RGBA)
    return Image.fromarray(result, "RGBA")


def fallback_affine_warp(
    garment_img:  Image.Image,
    garment_type: str,
    body_regions: dict,
    canvas_size:  int = 512,
) -> Image.Image:
    """단순 리사이즈 폴백."""
    region_key = {"top": "top", "bottom": "bottom", "dress": "full"}.get(garment_type, "full")
    dst  = body_regions.get(region_key, (0, 0, canvas_size, canvas_size))
    dx1, dy1, dx2, dy2 = [int(v) for v in dst]
    tw   = max(1, dx2 - dx1)
    th   = max(1, dy2 - dy1)
    rgba = garment_img.convert("RGBA").resize((tw, th), Image.LANCZOS)
    c    = Image.new("RGBA", (canvas_size, canvas_size), (0,0,0,0))
    c.paste(rgba, (dx1, dy1), rgba)
    return c
