"""
마네킹 원본 위에 의류를 자연스럽게 합성하는 모듈.

개선 사항 (v3):
  - 마네킹 몸체 실루엣 기반 소프트 클리핑 — 몸 밖으로 삐져나온 의류 부드럽게 제거
  - 상의-하의 자연스러운 오버랩 (허리 접힘 표현)
  - 의류 가장자리 다단계 페더링
  - 원본 마네킹 픽셀 무수정 보장
"""
import numpy as np
import cv2
from PIL import Image
from backend.pipeline.shadow_generator import generate_inner_shadow, generate_fold_highlights

LAYER_ORDER = ["dress", "bottom", "top", "accessory"]


def _smooth_alpha(garment: np.ndarray, feather: int = 10) -> np.ndarray:
    """의류 알파 채널 침식 + 블러 페더링."""
    alpha   = garment[:, :, 3].copy()
    kernel  = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    alpha   = cv2.erode(alpha, kernel, iterations=1)
    ksize   = feather * 2 + 1
    alpha   = cv2.GaussianBlur(alpha.astype(np.float32), (ksize, ksize), feather * 0.4)
    result  = garment.copy()
    result[:, :, 3] = np.clip(alpha, 0, 255).astype(np.uint8)
    return result


def _body_soft_clip(garment: np.ndarray, body_mask: np.ndarray, strength: float = 0.80) -> np.ndarray:
    """
    몸체 실루엣 기반 소프트 클리핑.
    몸 영역 내부는 온전히, 외부로 나간 부분은 알파를 점진적으로 감소.
    strength: 0=클리핑 없음, 1=완전 클리핑
    """
    body_f   = np.clip(body_mask.astype(np.float32) / 255.0, 0, 1)

    # 몸 경계 외부를 부드러운 그라디언트로
    blurred  = cv2.GaussianBlur(body_f, (31, 31), 10)
    # strength만큼만 클리핑 (너무 강하면 옷 끝이 잘려 어색)
    clip_map = body_f * strength + blurred * (1 - strength)
    clip_map = np.clip(clip_map, 0, 1)

    result   = garment.copy().astype(np.float32)
    result[:, :, 3] = result[:, :, 3] * clip_map
    return np.clip(result, 0, 255).astype(np.uint8)


def _alpha_blend(base: np.ndarray, overlay: np.ndarray) -> np.ndarray:
    b    = base.astype(np.float64) / 255.0
    o    = overlay.astype(np.float64) / 255.0
    ao   = o[:, :, 3:4]
    ab   = b[:, :, 3:4]
    out_a = ao + ab * (1 - ao)
    safe  = np.where(out_a > 1e-6, out_a, 1e-6)
    rgb   = (o[:, :, :3] * ao + b[:, :, :3] * ab * (1 - ao)) / safe
    return np.clip(np.concatenate([rgb, out_a], axis=2) * 255, 0, 255).astype(np.uint8)


def _add_worn_shadow(garment: np.ndarray, radius: int = 12, intensity: float = 0.15) -> np.ndarray:
    """의류 가장자리 drop shadow (마네킹 원본 미수정)."""
    mask     = garment[:, :, 3]
    kernel   = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (radius, radius))
    dilated  = cv2.dilate(mask, kernel, iterations=1)
    zone     = cv2.subtract(dilated, mask)
    blur     = cv2.GaussianBlur(zone.astype(np.float32), (radius | 1, radius | 1), 0)
    alpha    = blur / 255.0 * intensity

    result   = garment.copy().astype(np.float32)
    no_gar   = garment[:, :, 3] < 30
    result[:, :, 0] = np.where(no_gar, 0, result[:, :, 0])
    result[:, :, 1] = np.where(no_gar, 0, result[:, :, 1])
    result[:, :, 2] = np.where(no_gar, 0, result[:, :, 2])
    result[:, :, 3] = np.clip(result[:, :, 3] + np.where(no_gar, alpha * 255, 0), 0, 255)
    return result.astype(np.uint8)


def _blend_waist_junction(
    canvas: np.ndarray,
    top_arr: np.ndarray,
    bot_arr: np.ndarray,
    overlap_px: int = 28,
) -> np.ndarray:
    """상의 하단이 하의 상단 위에 자연스럽게 겹치도록 추가 합성."""
    h      = canvas.shape[0]
    result = canvas.copy()

    top_rows = np.where(top_arr[:, :, 3].max(axis=1) > 20)[0]
    bot_rows = np.where(bot_arr[:, :, 3].max(axis=1) > 20)[0]
    if len(top_rows) == 0 or len(bot_rows) == 0:
        return result

    top_y = int(top_rows[-1])
    bot_y = int(bot_rows[0])

    # 허리 접힘 영역
    y1 = max(0, min(top_y, bot_y) - overlap_px)
    y2 = min(h, max(top_y, bot_y) + overlap_px // 2)
    if y2 <= y1:
        return result

    # 상의 하단 부분을 살짝 어둡게 — 겹쳐진 느낌
    fade = np.linspace(1.0, 0.90, y2 - y1).reshape(-1, 1, 1).astype(np.float32)
    region = result[y1:y2].astype(np.float32)
    region[:, :, :3] = np.clip(region[:, :, :3] * fade, 0, 255)
    result[y1:y2] = region.astype(np.uint8)
    return result


def compose(
    mannequin: Image.Image,
    warped_garments: dict,
    mannequin_nobg: Image.Image = None,
) -> Image.Image:
    """
    원본 마네킹 보존하면서 의류를 착용한 것처럼 합성.
    mannequin_nobg가 있으면 몸체 실루엣 클리핑 적용.
    """
    # 원본 마네킹 → BGRA 캔버스 (픽셀 직접 수정 없음)
    mann_rgba = np.array(mannequin.convert("RGBA"))
    canvas    = cv2.cvtColor(mann_rgba, cv2.COLOR_RGBA2BGRA)

    # 몸체 마스크 (소프트 클리핑용)
    body_mask = None
    if mannequin_nobg is not None:
        nb_arr    = np.array(mannequin_nobg.convert("RGBA"))
        body_mask = nb_arr[:, :, 3]

    # 의류 BGRA 변환
    garment_arrs: dict[str, np.ndarray] = {}
    for gtype in LAYER_ORDER:
        if gtype not in warped_garments:
            continue
        arr  = np.array(warped_garments[gtype].convert("RGBA"))
        garment_arrs[gtype] = cv2.cvtColor(arr, cv2.COLOR_RGBA2BGRA)

    # 레이어별 합성
    for gtype in LAYER_ORDER:
        if gtype not in garment_arrs:
            continue
        g    = garment_arrs[gtype].copy()
        mask = g[:, :, 3]

        # 1) 몸체 실루엣 소프트 클리핑 (몸 밖으로 삐져나온 의류 제거)
        if body_mask is not None:
            g = _body_soft_clip(g, body_mask, strength=0.75)

        # 2) 주름·하이라이트
        g = generate_fold_highlights(g, g[:, :, 3], intensity=0.07)

        # 3) 내부 그림자 (입체감)
        inner = generate_inner_shadow(g[:, :, 3], shadow_radius=22, shadow_intensity=0.22)
        gf    = g.astype(np.float32) / 255.0
        inf_  = inner.astype(np.float32) / 255.0
        sa    = inf_[:, :, 3:4]
        gf[:, :, :3] = gf[:, :, :3] * (1 - sa) + inf_[:, :, :3] * sa
        g = (gf * 255).astype(np.uint8)

        # 4) drop shadow (의류 레이어 자체에 포함)
        g = _add_worn_shadow(g, radius=12, intensity=0.15)

        # 5) 경계 페더링
        g = _smooth_alpha(g, feather=9)

        # 6) 알파 블렌딩
        canvas = _alpha_blend(canvas, g)

    # 상의-하의 허리 연결
    if "top" in garment_arrs and "bottom" in garment_arrs:
        canvas = _blend_waist_junction(
            canvas, garment_arrs["top"], garment_arrs["bottom"], overlap_px=28
        )

    # 최종 RGB 출력 + 미세 선명도
    result = cv2.cvtColor(canvas, cv2.COLOR_BGRA2BGR)
    blur   = cv2.GaussianBlur(result, (0, 0), 0.8)
    result = cv2.addWeighted(result, 1.15, blur, -0.15, 0)

    return Image.fromarray(cv2.cvtColor(result, cv2.COLOR_BGR2RGB), "RGB")
