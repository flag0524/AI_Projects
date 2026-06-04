"""
마네킹 몸체 마스크를 정밀 분석하는 모듈.

MediaPipe 대신 픽셀 마스크 기반으로 해부학적 경계를 직접 추출한다.
마네킹은 사람이 아니라 MediaPipe 감지율이 낮으므로 이 모듈이 더 신뢰성 있다.
"""
import numpy as np
import cv2
from PIL import Image


def refine_mask(mask: np.ndarray) -> np.ndarray:
    """마네킹 마스크의 구멍을 메우고 노이즈를 제거."""
    closed  = cv2.morphologyEx(mask, cv2.MORPH_CLOSE,
                               cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15)))
    cleaned = cv2.morphologyEx(closed, cv2.MORPH_OPEN,
                               cv2.getStructuringElement(cv2.MORPH_ELLIPSE,  (5,  5)))
    return cleaned


def get_mask_from_image(img: Image.Image) -> np.ndarray:
    """RGBA 이미지에서 알파 채널 기반 마스크 반환 (정제 포함)."""
    arr   = np.array(img.convert("RGBA"))
    alpha = arr[:, :, 3]
    _, m  = cv2.threshold(alpha, 20, 255, cv2.THRESH_BINARY)
    return refine_mask(m)


def get_body_profile(mask: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """
    마스크의 각 행에서 좌·우 경계 x 좌표 배열 반환.
    shape: (H,), (H,)
    """
    h, w   = mask.shape
    lefts  = np.full(h, w // 2, dtype=np.float32)
    rights = np.full(h, w // 2, dtype=np.float32)
    for y in range(h):
        nz = np.where(mask[y, :] > 30)[0]
        if len(nz) >= 2:
            lefts[y]  = float(nz[0])
            rights[y] = float(nz[-1])
    return lefts, rights


def detect_body_regions(mask: np.ndarray) -> dict:
    """
    마스크에서 해부학적 영역을 픽셀 단위로 감지.
    - shoulder_y: 몸체가 시작하는 행 (가장 위)
    - hip_y     : 몸체 너비가 가장 넓어지는 행 (엉덩이)
    - ankle_y   : 몸체가 끝나는 행 (가장 아래)
    - body_cx   : 몸체 중앙 x
    """
    h, w   = mask.shape
    lefts, rights = get_body_profile(mask)
    widths = rights - lefts

    # 마스크가 존재하는 행 범위
    active_rows = np.where(widths > 10)[0]
    if len(active_rows) < 4:
        return _default_regions(h, w)

    top_y    = int(active_rows[0])
    bottom_y = int(active_rows[-1])
    body_h   = bottom_y - top_y

    # 상체 구간에서 너비 변화를 분석하여 허리/엉덩이 위치 감지
    upper_half = active_rows[active_rows < top_y + body_h * 0.65]
    if len(upper_half) > 0:
        # 너비가 가장 좁아지는 구간 = 허리
        waist_idx  = upper_half[np.argmin(widths[upper_half])]
        waist_y    = int(waist_idx)
    else:
        waist_y = top_y + int(body_h * 0.50)

    # 허리 아래에서 너비가 가장 넓은 구간 = 엉덩이
    lower_half = active_rows[(active_rows > waist_y) & (active_rows < top_y + body_h * 0.75)]
    if len(lower_half) > 0:
        hip_idx = lower_half[np.argmax(widths[lower_half])]
        hip_y   = int(hip_idx)
    else:
        hip_y = top_y + int(body_h * 0.58)

    shoulder_y = top_y + int(body_h * 0.08)  # 어깨는 상단에서 약간 아래
    ankle_y    = bottom_y

    # 각 구간 중앙 x
    body_cx = float(np.mean((lefts[active_rows] + rights[active_rows]) / 2))

    # 어깨 너비 (상단 10% 구간에서 평균 너비)
    shoulder_region = active_rows[active_rows < top_y + body_h * 0.20]
    shoulder_w = float(np.mean(widths[shoulder_region])) if len(shoulder_region) > 0 else 100.0

    return {
        "top_y":       top_y,
        "shoulder_y":  shoulder_y,
        "waist_y":     waist_y,
        "hip_y":       hip_y,
        "ankle_y":     ankle_y,
        "body_cx":     body_cx,
        "shoulder_w":  shoulder_w,
        # body_bounds 호환 포맷
        "top":    (int(body_cx - shoulder_w * 0.65), shoulder_y,
                   int(body_cx + shoulder_w * 0.65), hip_y),
        "bottom": (int(body_cx - shoulder_w * 0.70), hip_y,
                   int(body_cx + shoulder_w * 0.70), ankle_y),
        "full":   (int(body_cx - shoulder_w * 0.70), shoulder_y,
                   int(body_cx + shoulder_w * 0.70), ankle_y),
        # pose_estimator 호환 키포인트
        "left_shoulder":  (int(body_cx - shoulder_w * 0.50), shoulder_y),
        "right_shoulder": (int(body_cx + shoulder_w * 0.50), shoulder_y),
        "left_hip":       (int(lefts[hip_y])  if hip_y < h else int(body_cx - 60), hip_y),
        "right_hip":      (int(rights[hip_y]) if hip_y < h else int(body_cx + 60), hip_y),
        "left_ankle":     (int(body_cx - 40), ankle_y),
        "right_ankle":    (int(body_cx + 40), ankle_y),
    }


def _default_regions(h: int, w: int) -> dict:
    cx = w // 2
    return {
        "top_y": int(h * 0.08),   "shoulder_y": int(h * 0.12),
        "waist_y": int(h * 0.50), "hip_y": int(h * 0.58),
        "ankle_y": int(h * 0.95), "body_cx": float(cx),
        "shoulder_w": float(w * 0.38),
        "top":    (int(cx - w*0.22), int(h*0.12), int(cx + w*0.22), int(h*0.55)),
        "bottom": (int(cx - w*0.22), int(h*0.55), int(cx + w*0.22), int(h*0.95)),
        "full":   (int(cx - w*0.22), int(h*0.12), int(cx + w*0.22), int(h*0.95)),
        "left_shoulder":  (int(cx - w*0.22), int(h*0.12)),
        "right_shoulder": (int(cx + w*0.22), int(h*0.12)),
        "left_hip":  (int(cx - w*0.20), int(h*0.58)),
        "right_hip": (int(cx + w*0.20), int(h*0.58)),
        "left_ankle":  (int(cx - w*0.12), int(h*0.95)),
        "right_ankle": (int(cx + w*0.12), int(h*0.95)),
    }
