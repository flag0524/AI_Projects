"""
마네킹 원본 이미지를 훼손하지 않고, 의류 레이어만 자연스럽게 올리는 합성 모듈.

원칙:
  - 합성 베이스(mannequin)는 픽셀 변경 없이 그대로 사용
  - 의류에만 그림자·하이라이트·페더링 처리
  - drop shadow는 의류 레이어 자체에 포함 (마네킹 원본에 직접 칠하지 않음)
"""
import numpy as np
import cv2
from PIL import Image
from backend.pipeline.shadow_generator import (
    generate_inner_shadow,
    generate_fold_highlights,
)

LAYER_ORDER = ["dress", "bottom", "top", "accessory"]


def _feather_mask(mask: np.ndarray, radius: int = 12) -> np.ndarray:
    ksize = radius * 2 + 1
    blurred = cv2.GaussianBlur(mask.astype(np.float32), (ksize, ksize), radius * 0.4)
    return np.clip(blurred, 0, 255).astype(np.uint8)


def _smooth_garment_boundary(garment_arr: np.ndarray, feather_px: int = 12) -> np.ndarray:
    """의류 외곽 알파 채널을 침식+블러로 매끄럽게."""
    alpha = garment_arr[:, :, 3].copy()
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    alpha = cv2.erode(alpha, kernel, iterations=1)
    ksize = feather_px * 2 + 1
    alpha = cv2.GaussianBlur(alpha.astype(np.float32), (ksize, ksize), feather_px * 0.4)
    result = garment_arr.copy()
    result[:, :, 3] = np.clip(alpha, 0, 255).astype(np.uint8)
    return result


def _add_drop_shadow_to_garment(garment_bgra: np.ndarray, radius: int = 14, intensity: float = 0.22) -> np.ndarray:
    """
    의류 레이어 아래에 drop shadow를 포함시킨다.
    마네킹 원본에 직접 그리는 대신, 의류 BGRA 뒤에 shadow 레이어를 합산.
    """
    mask = garment_bgra[:, :, 3]
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (radius, radius))
    dilated = cv2.dilate(mask, kernel, iterations=1)
    shadow_zone = cv2.subtract(dilated, mask)
    shadow_blur = cv2.GaussianBlur(shadow_zone.astype(np.float32), (radius | 1, radius | 1), 0)
    shadow_alpha = shadow_blur / 255.0 * intensity

    result = garment_bgra.copy().astype(np.float32)
    # shadow를 의류 알파에 더해 자연스럽게 마네킹 위에 어둠을 드리움
    shadow_contribution = shadow_alpha * 255
    # 의류가 없는 영역에만 shadow alpha 추가
    no_garment = (garment_bgra[:, :, 3] < 30)
    result[:, :, 0] = np.where(no_garment, 0, result[:, :, 0])
    result[:, :, 1] = np.where(no_garment, 0, result[:, :, 1])
    result[:, :, 2] = np.where(no_garment, 0, result[:, :, 2])
    result[:, :, 3] = np.clip(
        result[:, :, 3] + np.where(no_garment, shadow_contribution, 0),
        0, 255
    )
    return result.astype(np.uint8)


def _alpha_blend_rgba(base: np.ndarray, overlay: np.ndarray) -> np.ndarray:
    """BGRA 두 레이어 사전 곱셈 알파 블렌딩 (base는 수정되지 않는 픽셀 유지)."""
    b = base.astype(np.float64) / 255.0
    o = overlay.astype(np.float64) / 255.0
    a_o = o[:, :, 3:4]
    a_b = b[:, :, 3:4]
    out_a = a_o + a_b * (1.0 - a_o)
    safe = np.where(out_a > 1e-6, out_a, 1e-6)
    out_rgb = (o[:, :, :3] * a_o + b[:, :, :3] * a_b * (1.0 - a_o)) / safe
    return np.clip(np.concatenate([out_rgb, out_a], axis=2) * 255, 0, 255).astype(np.uint8)


def _blend_junction(canvas: np.ndarray, top_arr: np.ndarray, bottom_arr: np.ndarray, overlap_px: int = 20) -> np.ndarray:
    """상의-하의 연결부 오버랩 처리."""
    h = canvas.shape[0]
    result = canvas.copy()

    top_rows = np.where(top_arr[:, :, 3].max(axis=1) > 30)[0]
    bot_rows = np.where(bottom_arr[:, :, 3].max(axis=1) > 30)[0]
    if len(top_rows) == 0 or len(bot_rows) == 0:
        return result

    top_bottom_y = int(top_rows[-1])
    bot_top_y    = int(bot_rows[0])
    y1 = max(0, min(top_bottom_y, bot_top_y) - overlap_px)
    y2 = min(h, max(top_bottom_y, bot_top_y) + overlap_px)
    if y2 <= y1:
        return result

    region = result[y1:y2].astype(np.float32)
    fade = np.linspace(0.92, 1.0, y2 - y1).reshape(-1, 1, 1)
    region[:, :, :3] = np.clip(region[:, :, :3] * fade, 0, 255)
    result[y1:y2] = region.astype(np.uint8)
    return result


def compose(
    mannequin: Image.Image,
    warped_garments: dict[str, Image.Image],
) -> Image.Image:
    """
    원본 마네킹 이미지를 훼손하지 않고 의류만 자연스럽게 합성.
    mannequin 이미지의 픽셀은 직접 수정하지 않음.
    """
    # ── 원본 마네킹을 BGRA 캔버스로 변환 (픽셀 수정 없음) ────────────────
    mannequin_rgba = np.array(mannequin.convert("RGBA"))
    mannequin_bgra = cv2.cvtColor(mannequin_rgba, cv2.COLOR_RGBA2BGRA)
    canvas = mannequin_bgra.copy()   # 이 canvas 위에만 의류를 올림

    # ── 의류 레이어 전처리 ────────────────────────────────────────────────
    garment_arrs: dict[str, np.ndarray] = {}
    for gtype in LAYER_ORDER:
        if gtype not in warped_garments:
            continue
        arr_rgba = np.array(warped_garments[gtype].convert("RGBA"))
        arr_bgra = cv2.cvtColor(arr_rgba, cv2.COLOR_RGBA2BGRA)
        garment_arrs[gtype] = arr_bgra

    # ── 레이어별 합성 ─────────────────────────────────────────────────────
    for gtype in LAYER_ORDER:
        if gtype not in garment_arrs:
            continue
        g = garment_arrs[gtype].copy()
        mask = g[:, :, 3]

        # 1) 주름/하이라이트 (의류 자체에만)
        g = generate_fold_highlights(g, mask, intensity=0.08)

        # 2) 내부 그림자 (의류 자체에만, 마네킹 무관)
        inner = generate_inner_shadow(mask, shadow_radius=24, shadow_intensity=0.25)
        g_f = g.astype(np.float32) / 255.0
        i_f = inner.astype(np.float32) / 255.0
        sa  = i_f[:, :, 3:4]
        g_f[:, :, :3] = g_f[:, :, :3] * (1 - sa) + i_f[:, :, :3] * sa
        g = (g_f * 255).astype(np.uint8)

        # 3) drop shadow를 의류 레이어 자체에 포함 (마네킹 원본 미수정)
        g = _add_drop_shadow_to_garment(g, radius=14, intensity=0.18)

        # 4) 경계 페더링
        g = _smooth_garment_boundary(g, feather_px=10)

        # 5) 알파 블렌딩으로 canvas에 합성
        canvas = _alpha_blend_rgba(canvas, g)

    # ── 상의-하의 연결부 처리 ─────────────────────────────────────────────
    if "top" in garment_arrs and "bottom" in garment_arrs:
        canvas = _blend_junction(canvas, garment_arrs["top"], garment_arrs["bottom"], overlap_px=20)

    # ── 최종 출력: RGB 변환 ───────────────────────────────────────────────
    result_rgb = cv2.cvtColor(canvas, cv2.COLOR_BGRA2RGB)

    # 의류 영역에만 미세 선명도 향상 (언샤프 마스킹)
    blurred = cv2.GaussianBlur(result_rgb, (0, 0), 1.0)
    result_rgb = cv2.addWeighted(result_rgb, 1.2, blurred, -0.2, 0)

    return Image.fromarray(result_rgb, "RGB")
