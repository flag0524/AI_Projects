"""
마네킹 이미지 위에 의류 레이어를 자연스럽게 합성하는 모듈.

개선 사항:
- 의류 내부 그림자로 입체감 부여
- 마네킹 몸체에 drop shadow 적용
- 상의/하의 연결부 자연스러운 오버랩 처리
- 가장자리 Gaussian 페더링 강화
- 색상 조화(color harmonization)로 조명 일관성 유지
"""
import numpy as np
import cv2
from PIL import Image
from backend.pipeline.shadow_generator import (
    generate_inner_shadow,
    generate_fold_highlights,
    apply_garment_shadow_on_body,
)
from backend.pipeline.segmenter import get_garment_mask

# 레이어 합성 순서: 뒤 → 앞
LAYER_ORDER = ["dress", "bottom", "top", "accessory"]


def _feather_mask(mask: np.ndarray, radius: int = 12) -> np.ndarray:
    """마스크 경계를 Gaussian 블러로 부드럽게 (반경 강화)."""
    ksize = radius * 2 + 1
    blurred = cv2.GaussianBlur(mask.astype(np.float32), (ksize, ksize), radius * 0.5)
    return np.clip(blurred, 0, 255).astype(np.uint8)


def _alpha_blend(base: np.ndarray, overlay: np.ndarray) -> np.ndarray:
    """RGBA 레이어 두 장을 사전 곱셈 알파 블렌딩."""
    base_f = base.astype(np.float64) / 255.0
    over_f = overlay.astype(np.float64) / 255.0

    a_over = over_f[:, :, 3:4]
    a_base = base_f[:, :, 3:4]
    out_a = a_over + a_base * (1.0 - a_over)
    out_a_safe = np.where(out_a > 1e-6, out_a, 1e-6)
    out_rgb = (over_f[:, :, :3] * a_over + base_f[:, :, :3] * a_base * (1.0 - a_over)) / out_a_safe
    out = np.concatenate([out_rgb, out_a], axis=2)
    return np.clip(out * 255, 0, 255).astype(np.uint8)


def _color_match(src: np.ndarray, ref: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """
    의류(src)의 색온도를 마네킹 배경(ref) 조명에 맞게 미세 보정.
    랩(Lab) 색공간에서 평균 밝기 차이만 조정 (색상 왜곡 방지).
    """
    if mask.sum() < 100:
        return src
    src_lab = cv2.cvtColor(src[:, :, :3], cv2.COLOR_BGR2Lab).astype(np.float32)
    ref_lab = cv2.cvtColor(ref[:, :, :3], cv2.COLOR_BGR2Lab).astype(np.float32)

    m = mask > 10
    if m.sum() < 10:
        return src

    # L 채널 평균 차이만 보정 (±15 제한)
    delta_L = float(np.clip(
        ref_lab[:, :, 0][m].mean() - src_lab[:, :, 0][m].mean(),
        -15, 15
    )) * 0.3  # 30%만 보정 (과보정 방지)

    result = src.copy()
    src_lab[:, :, 0] = np.clip(src_lab[:, :, 0] + delta_L, 0, 255)
    corrected_bgr = cv2.cvtColor(src_lab.astype(np.uint8), cv2.COLOR_Lab2BGR)
    result[:, :, :3] = np.where(
        m[:, :, np.newaxis], corrected_bgr, src[:, :, :3]
    )
    return result


def _smooth_garment_boundary(garment_arr: np.ndarray, feather_px: int = 14) -> np.ndarray:
    """
    의류 외곽 경계를 다단계 블러로 매끄럽게 처리.
    단순 Gaussian 대신 알파 채널에 bilateral-like 페더링 적용.
    """
    alpha = garment_arr[:, :, 3].copy()

    # 1단계: 모폴로지 침식으로 날카로운 픽셀 제거
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    alpha_eroded = cv2.erode(alpha, kernel, iterations=1)

    # 2단계: 강한 Gaussian 블러
    alpha_blurred = cv2.GaussianBlur(alpha_eroded.astype(np.float32),
                                      (feather_px * 2 + 1, feather_px * 2 + 1),
                                      feather_px * 0.4)
    result = garment_arr.copy()
    result[:, :, 3] = np.clip(alpha_blurred, 0, 255).astype(np.uint8)
    return result


def _blend_garment_junction(
    canvas: np.ndarray,
    top_arr: np.ndarray,
    bottom_arr: np.ndarray,
    overlap_px: int = 20,
) -> np.ndarray:
    """
    상의-하의 연결부를 자연스럽게 오버랩 처리.
    상의 하단과 하의 상단 사이 그라디언트 블렌딩.
    """
    h, w = canvas.shape[:2]
    result = canvas.copy()

    # 상의 하단 경계 찾기
    top_alpha = top_arr[:, :, 3]
    top_rows = np.where(top_alpha.max(axis=1) > 30)[0]
    if len(top_rows) == 0:
        return result
    top_bottom_y = int(top_rows[-1])

    # 하의 상단 경계 찾기
    bot_alpha = bottom_arr[:, :, 3]
    bot_rows = np.where(bot_alpha.max(axis=1) > 30)[0]
    if len(bot_rows) == 0:
        return result
    bot_top_y = int(bot_rows[0])

    # 연결부 영역에 추가 블렌딩
    y1 = max(0, min(top_bottom_y, bot_top_y) - overlap_px)
    y2 = min(h, max(top_bottom_y, bot_top_y) + overlap_px)
    if y2 <= y1:
        return result

    # 연결부 알파 강화
    region = result[y1:y2].copy().astype(np.float32)
    boost = np.linspace(0.9, 1.0, y2 - y1).reshape(-1, 1, 1)
    region[:, :, :3] = np.clip(region[:, :, :3] * boost, 0, 255)
    result[y1:y2] = region.astype(np.uint8)
    return result


def compose(
    mannequin: Image.Image,
    warped_garments: dict[str, Image.Image],
) -> Image.Image:
    """마네킹 위에 의류 레이어들을 자연스럽게 합성."""
    # 마네킹을 BGR로 처리 (OpenCV 기반 그림자 적용 위해)
    mannequin_rgba = np.array(mannequin.convert("RGBA"))
    mannequin_bgr = cv2.cvtColor(mannequin_rgba[:, :, :3], cv2.COLOR_RGB2BGR)
    canvas_bgr = mannequin_bgr.copy()

    garment_arrs = {}
    for gtype in LAYER_ORDER:
        if gtype not in warped_garments:
            continue
        arr = np.array(warped_garments[gtype].convert("RGBA"))
        # RGBA → BGRA
        arr_bgra = cv2.cvtColor(arr, cv2.COLOR_RGBA2BGRA)
        garment_arrs[gtype] = arr_bgra

    # 1단계: 마네킹 몸체에 각 의류의 drop shadow 적용
    for gtype in LAYER_ORDER:
        if gtype not in garment_arrs:
            continue
        mask = garment_arrs[gtype][:, :, 3]
        canvas_bgr = apply_garment_shadow_on_body(
            canvas_bgr, mask,
            shadow_radius=18,
            shadow_intensity=0.20,
        )

    # 2단계: canvas를 BGRA로 변환 후 레이어별 합성
    canvas_bgra = cv2.cvtColor(canvas_bgr, cv2.COLOR_BGR2BGRA)
    canvas_bgra[:, :, 3] = mannequin_rgba[:, :, 3]

    for gtype in LAYER_ORDER:
        if gtype not in garment_arrs:
            continue
        garment_bgra = garment_arrs[gtype].copy()
        mask = garment_bgra[:, :, 3]

        # 색상 조화: 마네킹 조명에 맞게 미세 보정
        garment_bgra = _color_match(garment_bgra, canvas_bgr, mask)

        # 주름/하이라이트 적용
        garment_bgra = generate_fold_highlights(garment_bgra, mask, intensity=0.10)

        # 내부 그림자로 입체감
        inner_shadow = generate_inner_shadow(
            mask,
            shadow_radius=28,
            shadow_intensity=0.30,
        )
        # 내부 그림자를 의류 위에 블렌딩
        garment_f = garment_bgra.astype(np.float32) / 255.0
        shadow_f = inner_shadow.astype(np.float32) / 255.0
        sa = shadow_f[:, :, 3:4]
        garment_f[:, :, :3] = garment_f[:, :, :3] * (1 - sa) + shadow_f[:, :, :3] * sa
        garment_bgra = (garment_f * 255).astype(np.uint8)

        # 경계 페더링 (다단계)
        garment_bgra = _smooth_garment_boundary(garment_bgra, feather_px=12)

        # 알파 블렌딩으로 canvas에 합성
        canvas_bgra = _alpha_blend(canvas_bgra, garment_bgra)

    # 3단계: 상의-하의 연결부 자연스럽게 처리
    if "top" in garment_arrs and "bottom" in garment_arrs:
        canvas_bgra = _blend_garment_junction(
            canvas_bgra,
            garment_arrs["top"],
            garment_arrs["bottom"],
            overlap_px=25,
        )

    # 4단계: 최종 이미지 후처리
    result_bgr = cv2.cvtColor(canvas_bgra, cv2.COLOR_BGRA2BGR)

    # 미세 선명도 향상 (언샤프 마스킹)
    blurred = cv2.GaussianBlur(result_bgr, (0, 0), 1.2)
    result_bgr = cv2.addWeighted(result_bgr, 1.3, blurred, -0.3, 0)

    # 전체 대비 미세 조정
    result_bgr = cv2.convertScaleAbs(result_bgr, alpha=1.03, beta=3)

    result_rgb = cv2.cvtColor(result_bgr, cv2.COLOR_BGR2RGB)
    return Image.fromarray(result_rgb, "RGB")
