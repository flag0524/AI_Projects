"""
의류 레이어를 마네킹 원본 위에 자연스럽게 합성하는 모듈 (v4).

원칙:
  1. 마네킹 원본 픽셀 절대 수정 금지
  2. 의류는 몸체 실루엣 안에서만 보이도록 소프트 클리핑
  3. 가장자리 다단계 페더링으로 자연스러운 경계
  4. 상의·하의 허리 연결은 상의가 하의를 덮도록 (자연스러운 레이어링)
"""
import numpy as np
import cv2
from PIL import Image

LAYER_ORDER = ["dress", "bottom", "top", "accessory"]


def _feather_alpha(arr: np.ndarray, radius: int = 8) -> np.ndarray:
    """알파 채널을 침식 + 블러로 부드럽게."""
    a      = arr[:, :, 3].copy().astype(np.float32)
    k      = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    a      = cv2.erode(a, k, iterations=1)
    ksize  = radius * 2 + 1
    a      = cv2.GaussianBlur(a, (ksize, ksize), radius * 0.35)
    result = arr.copy()
    result[:, :, 3] = np.clip(a, 0, 255).astype(np.uint8)
    return result


def _soft_clip_to_body(garment: np.ndarray, body_mask: np.ndarray,
                       strength: float = 0.65) -> np.ndarray:
    """
    몸체 마스크 외부로 나간 의류 픽셀을 부드럽게 제거.
    strength 0 = 클리핑 없음, 1 = 완전 클리핑.
    """
    body_f   = body_mask.astype(np.float32) / 255.0
    blurred  = cv2.GaussianBlur(body_f, (31, 31), 10)
    clip_map = body_f * strength + blurred * (1.0 - strength)
    clip_map = np.clip(clip_map, 0, 1)
    result   = garment.copy().astype(np.float32)
    result[:, :, 3] *= clip_map
    return np.clip(result, 0, 255).astype(np.uint8)


def _add_edge_shadow(garment: np.ndarray, radius: int = 10,
                     intensity: float = 0.12) -> np.ndarray:
    """의류 가장자리 drop shadow (의류 레이어 자체에 포함)."""
    mask    = garment[:, :, 3]
    k       = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (radius, radius))
    dilated = cv2.dilate(mask, k, iterations=1)
    zone    = cv2.subtract(dilated, mask)
    blur    = cv2.GaussianBlur(zone.astype(np.float32), (radius | 1, radius | 1), 0)
    alpha   = blur / 255.0 * intensity
    result  = garment.copy().astype(np.float32)
    empty   = garment[:, :, 3] < 20
    result[:, :, 3] += np.where(empty, alpha * 255, 0)
    return np.clip(result, 0, 255).astype(np.uint8)


def _add_inner_depth(garment: np.ndarray, radius: int = 20,
                     intensity: float = 0.18) -> np.ndarray:
    """의류 내부 가장자리를 어둡게 — 몸에 감싸인 입체감."""
    mask  = garment[:, :, 3]
    dist  = cv2.distanceTransform(mask, cv2.DIST_L2, 5)
    zone  = np.clip(dist / radius, 0, 1)
    shade = (1.0 - zone) * intensity  # 경계 근처 더 어두움

    result = garment.copy().astype(np.float32)
    mf     = (mask > 20).astype(np.float32)
    for c in range(3):
        result[:, :, c] = np.where(mf > 0,
                                   np.clip(result[:, :, c] * (1 - shade), 0, 255),
                                   result[:, :, c])
    return result.astype(np.uint8)


def _alpha_blend(base: np.ndarray, over: np.ndarray) -> np.ndarray:
    """RGBA(또는 BGRA) 사전 곱셈 알파 블렌딩."""
    b   = base.astype(np.float64) / 255.0
    o   = over.astype(np.float64) / 255.0
    ao  = o[:, :, 3:4]
    ab  = b[:, :, 3:4]
    oa  = ao + ab * (1.0 - ao)
    sf  = np.where(oa > 1e-6, oa, 1e-6)
    rgb = (o[:, :, :3] * ao + b[:, :, :3] * ab * (1.0 - ao)) / sf
    return np.clip(np.concatenate([rgb, oa], axis=2) * 255, 0, 255).astype(np.uint8)


def _waist_junction(canvas: np.ndarray,
                    top_arr: np.ndarray,
                    bot_arr: np.ndarray,
                    overlap: int = 30) -> np.ndarray:
    """
    상의 하단 ↔ 하의 상단 연결부:
    상의 하단이 하의 상단을 자연스럽게 덮도록 추가 블렌딩.
    """
    result   = canvas.copy()
    h        = canvas.shape[0]
    top_rows = np.where(top_arr[:, :, 3].max(axis=1) > 20)[0]
    bot_rows = np.where(bot_arr[:, :, 3].max(axis=1) > 20)[0]
    if len(top_rows) == 0 or len(bot_rows) == 0:
        return result

    ty = int(top_rows[-1])
    by = int(bot_rows[0])
    y1 = max(0, min(ty, by) - overlap // 2)
    y2 = min(h, max(ty, by) + overlap)
    if y2 <= y1:
        return result

    # 연결부 상의 쪽을 살짝 어둡게 — 하의가 아래 있는 느낌
    fade = np.linspace(1.0, 0.88, y2 - y1, dtype=np.float32).reshape(-1, 1, 1)
    reg  = result[y1:y2].astype(np.float32)
    reg[:, :, :3] = np.clip(reg[:, :, :3] * fade, 0, 255)
    result[y1:y2] = reg.astype(np.uint8)
    return result


def compose(
    mannequin:       Image.Image,
    warped_garments: dict,
    mannequin_nobg:  Image.Image = None,
) -> Image.Image:
    """
    마네킹 원본 위에 와핑된 의류를 자연스럽게 합성.

    Parameters
    ----------
    mannequin       : 원본 마네킹 이미지 (RGBA, 512×512)
    warped_garments : {garment_type: PIL.Image} — scanline_warp 결과
    mannequin_nobg  : 배경제거본 — 몸체 클리핑용
    """
    # ── 원본 마네킹을 변경 없이 캔버스로 사용 ─────────────────
    mann_rgba = np.array(mannequin.convert("RGBA"))
    canvas    = mann_rgba.copy()  # RGBA

    # ── 몸체 마스크 ────────────────────────────────────────────
    body_mask = None
    if mannequin_nobg is not None:
        nb = np.array(mannequin_nobg.convert("RGBA"))[:, :, 3]
        _, body_mask = cv2.threshold(nb, 20, 255, cv2.THRESH_BINARY)
        body_mask = cv2.morphologyEx(
            body_mask, cv2.MORPH_CLOSE,
            cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (13, 13))
        )

    # ── 의류 RGBA 배열 준비 ────────────────────────────────────
    g_arrs: dict[str, np.ndarray] = {}
    for gtype in LAYER_ORDER:
        if gtype not in warped_garments:
            continue
        g_arrs[gtype] = np.array(warped_garments[gtype].convert("RGBA"))

    # ── 레이어별 합성 ──────────────────────────────────────────
    for gtype in LAYER_ORDER:
        if gtype not in g_arrs:
            continue
        g = g_arrs[gtype].copy()

        # 1) 몸체 실루엣 소프트 클리핑
        if body_mask is not None:
            g = _soft_clip_to_body(g, body_mask, strength=0.65)

        # 2) 내부 깊이 그림자 (입체감)
        g = _add_inner_depth(g, radius=22, intensity=0.15)

        # 3) 가장자리 drop shadow
        g = _add_edge_shadow(g, radius=10, intensity=0.12)

        # 4) 경계 페더링
        g = _feather_alpha(g, radius=8)

        # 5) 캔버스에 알파 블렌딩
        canvas = _alpha_blend(canvas, g)

    # ── 상의·하의 허리 연결 ────────────────────────────────────
    if "top" in g_arrs and "bottom" in g_arrs:
        canvas = _waist_junction(canvas, g_arrs["top"], g_arrs["bottom"], overlap=30)

    # ── 최종 RGB 변환 + 미세 선명도 ───────────────────────────
    result_rgb = cv2.cvtColor(canvas, cv2.COLOR_RGBA2BGR)
    blur       = cv2.GaussianBlur(result_rgb, (0, 0), 0.7)
    result_rgb = cv2.addWeighted(result_rgb, 1.12, blur, -0.12, 0)

    return Image.fromarray(cv2.cvtColor(result_rgb, cv2.COLOR_BGR2RGB), "RGB")
