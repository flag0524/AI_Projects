"""..."""
from __future__ import annotations
import numpy as np
from PIL import Image
from loguru import logger

TARGET_W, TARGET_H = 768, 1024

SKELETON_PAIRS = [
    (0, 1), (1, 2), (2, 3), (3, 4),
    (1, 5), (5, 6), (6, 7),
    (1, 8), (8, 9), (9, 10),
    (1, 11), (11, 12), (12, 13),
    (0, 14), (14, 16), (0, 15), (15, 17),
    (2, 8), (5, 11),
]

COCO_COLORS = [
    (255, 0, 0), (255, 85, 0), (255, 170, 0), (255, 255, 0),
    (170, 255, 0), (85, 255, 0), (0, 255, 0), (0, 255, 85),
    (0, 255, 170), (0, 255, 255), (0, 170, 255), (0, 85, 255),
    (0, 0, 255), (85, 0, 255), (170, 0, 255), (255, 0, 255),
    (255, 0, 170), (255, 0, 85),
]


def _render_skeleton(keypoints: np.ndarray, w: int, h: int) -> Image.Image:
    from PIL import ImageDraw
    canvas = Image.new("RGB", (w, h), (0, 0, 0))
    draw = ImageDraw.Draw(canvas)

    for i, (a, b) in enumerate(SKELETON_PAIRS):
        if keypoints[a, 2] > 0.3 and keypoints[b, 2] > 0.3:
            draw.line(
                [(int(keypoints[a, 0]), int(keypoints[a, 1])),
                 (int(keypoints[b, 0]), int(keypoints[b, 1]))],
                fill=COCO_COLORS[i % len(COCO_COLORS)], width=4,
            )
    for i, (x, y, c) in enumerate(keypoints):
        if c > 0.3:
            r = 5
            draw.ellipse([(x-r, y-r), (x+r, y+r)], fill=COCO_COLORS[i % len(COCO_COLORS)])

    return canvas


def _extract_measurements(kp: np.ndarray, w: int, h: int) -> dict:
    def dist(a: int, b: int) -> float:
        if kp[a, 2] < 0.3 or kp[b, 2] < 0.3:
            return 0.0
        return float(np.linalg.norm(kp[a, :2] - kp[b, :2]))

    shoulder_w = dist(2, 5) / w
    # 어깨 기반 둘레 추정 (타원 둘레 근사: π × (a+b)/2, a=너비/2, b=깊이≈너비×0.4)
    chest_est  = shoulder_w * np.pi * 0.7
    waist_est  = shoulder_w * np.pi * 0.55
    hip_est    = shoulder_w * np.pi * 0.75
    torso_h    = dist(1, 8) / h

    ankle_y = max(kp[10, 1] if kp[10, 2] > 0.3 else 0,
                  kp[13, 1] if kp[13, 2] > 0.3 else 0)
    head_y  = kp[0, 1] if kp[0, 2] > 0.3 else 0
    total_h = abs(ankle_y - head_y) / h if ankle_y and head_y else 0.85

    return {
        "shoulder_width":      round(shoulder_w, 4),
        "chest_circumference": round(chest_est, 4),
        "waist_circumference": round(waist_est, 4),
        "hip_circumference":   round(hip_est, 4),
        "torso_height":        round(torso_h, 4),
        "total_height":        round(total_h, 4),
    }


# ─────────────────────────────────────────────
# 1. DWPose (controlnet_aux)
# ─────────────────────────────────────────────

def _try_dwpose(image: Image.Image, w: int, h: int) -> tuple[np.ndarray | None, Image.Image | None]:
    """..."""
    try:
        from controlnet_aux import DWposeDetector
        import json

        detector = DWposeDetector()

        # controlnet_aux ≥0.0.7: return_pil=False 옵션으로 raw output 가능
        # 버전에 따라 API가 다르므로 두 경로 모두 시도
        try:
            # raw dict 출력 시도
            raw = detector(image, include_body=True, include_hand=False,
                           include_face=False, return_pil=False)
            pose_img = detector(image, include_body=True, include_hand=False, include_face=False)

            bodies = raw.get("bodies", {})
            candidate = np.array(bodies.get("candidate", []))  # (N, 2) normalized
            subset   = np.array(bodies.get("subset", []))      # (1, 18)

            if candidate.size > 0 and subset.size > 0:
                kp = np.zeros((18, 3), dtype=np.float32)
                for i in range(18):
                    idx = int(subset[0, i])
                    if idx >= 0 and idx < len(candidate):
                        kp[i] = [candidate[idx, 0] * w, candidate[idx, 1] * h, 1.0]
                    else:
                        kp[i, 2] = 0.0
                logger.info("DWPose 키포인트 추출 성공")
                pose_map = pose_img if isinstance(pose_img, Image.Image) else Image.fromarray(np.array(pose_img))
                return kp, pose_map.resize((w, h))

        except TypeError:
            # 구버전: pose_map만 반환, 키포인트 미지원 -> MediaPipe로 키포인트 보완
            pose_map = detector(image, include_body=True, include_hand=False, include_face=False)
            logger.info("DWPose pose_map 생성 (키포인트는 MediaPipe 보완)")
            pose_map = pose_map.resize((w, h)) if isinstance(pose_map, Image.Image) else Image.fromarray(np.array(pose_map)).resize((w, h))
            return None, pose_map

    except Exception as e:
        logger.debug(f"DWPose 불가: {e}")
        return None, None


# ─────────────────────────────────────────────
# 2. MediaPipe Pose (COCO-18 변환)
# ─────────────────────────────────────────────

def _try_mediapipe(img_np: np.ndarray, w: int, h: int) -> np.ndarray | None:
    try:
        import mediapipe as mp
        mp_pose = mp.solutions.pose

        with mp_pose.Pose(static_image_mode=True, model_complexity=2,
                          enable_segmentation=False) as pose:
            result = pose.process(img_np)
            if not result.pose_landmarks:
                return None

            lm = result.pose_landmarks.landmark
            # MediaPipe 33개 -> COCO 18개 근사 매핑
            # -1: neck = mid(11,12) 계산
            mp_idx = [0, -1, 12, 14, 16, 11, 13, 15,
                      24, 26, 28, 23, 25, 27, 5, 2, 8, 7]
            kp = np.zeros((18, 3), dtype=np.float32)
            for i, mi in enumerate(mp_idx):
                if mi == -1:
                    kp[i] = [
                        (lm[11].x + lm[12].x) / 2 * w,
                        (lm[11].y + lm[12].y) / 2 * h,
                        (lm[11].visibility + lm[12].visibility) / 2,
                    ]
                else:
                    kp[i] = [lm[mi].x * w, lm[mi].y * h, lm[mi].visibility]

        logger.info("MediaPipe 포즈 추정 성공")
        return kp

    except Exception as e:
        logger.debug(f"MediaPipe 불가: {e}")
        return None


# ─────────────────────────────────────────────
# 3. 폴백 — 정면 서 있는 표준 마네킹
# ─────────────────────────────────────────────

def _fallback_keypoints(w: int, h: int) -> np.ndarray:
    norm = np.array([
        [.50, .08, 1.0], [.50, .14, 1.0], [.62, .18, 1.0], [.70, .34, 1.0],
        [.72, .50, 1.0], [.38, .18, 1.0], [.30, .34, 1.0], [.28, .50, 1.0],
        [.58, .52, 1.0], [.57, .72, 1.0], [.56, .92, 1.0], [.42, .52, 1.0],
        [.43, .72, 1.0], [.44, .92, 1.0], [.53, .06, 0.8], [.47, .06, 0.8],
        [.56, .07, 0.5], [.44, .07, 0.5],
    ], dtype=np.float32)
    norm[:, 0] *= w
    norm[:, 1] *= h
    return norm


# ─────────────────────────────────────────────
# 공개 인터페이스
# ─────────────────────────────────────────────

def estimate_pose(image: Image.Image) -> dict:
    """..."""
    w, h = image.size
    img_np = np.array(image)

    # 1) DWPose 시도
    kp, pose_map = _try_dwpose(image, w, h)

    # 2) 키포인트 없으면 MediaPipe 보완
    if kp is None:
        kp = _try_mediapipe(img_np, w, h)

    # 3) 전부 실패 시 폴백
    if kp is None:
        logger.warning("포즈 추정 실패 — 표준 마네킹 기본값 사용")
        kp = _fallback_keypoints(w, h)

    # pose_map 없으면 자체 렌더링
    if pose_map is None:
        pose_map = _render_skeleton(kp, w, h)

    measurements = _extract_measurements(kp, w, h)
    logger.debug(f"체형 추정: {measurements}")

    return {
        "pose_map": pose_map,
        "body_measurements": measurements,
        "keypoints": kp,
    }
