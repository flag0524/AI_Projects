import mediapipe as mp
import numpy as np
from PIL import Image

mp_pose = mp.solutions.pose


KEYPOINTS = {
    "left_shoulder": 11,
    "right_shoulder": 12,
    "left_elbow": 13,
    "right_elbow": 14,
    "left_wrist": 15,
    "right_wrist": 16,
    "left_hip": 23,
    "right_hip": 24,
    "left_knee": 25,
    "right_knee": 26,
    "left_ankle": 27,
    "right_ankle": 28,
}


def estimate_pose(img: Image.Image) -> dict[str, tuple[int, int]] | None:
    """관절 키포인트를 픽셀 좌표로 반환. 감지 실패 시 None."""
    rgb = np.array(img.convert("RGB"))
    h, w = rgb.shape[:2]

    with mp_pose.Pose(
        static_image_mode=True,
        model_complexity=1,
        min_detection_confidence=0.3,
    ) as pose:
        results = pose.process(rgb)

    if not results.pose_landmarks:
        return None

    lm = results.pose_landmarks.landmark
    kpts = {}
    for name, idx in KEYPOINTS.items():
        x = int(lm[idx].x * w)
        y = int(lm[idx].y * h)
        kpts[name] = (x, y)
    return kpts


def estimate_body_bounds(kpts: dict) -> dict:
    """키포인트로부터 상체/하체 경계 박스를 추정."""
    ls, rs = kpts["left_shoulder"], kpts["right_shoulder"]
    lh, rh = kpts["left_hip"], kpts["right_hip"]
    la, ra = kpts.get("left_ankle", lh), kpts.get("right_ankle", rh)

    shoulder_y = min(ls[1], rs[1])
    hip_y = max(lh[1], rh[1])
    ankle_y = max(la[1], ra[1])
    left_x = min(ls[0], lh[0])
    right_x = max(rs[0], rh[0])

    return {
        "top": (left_x, shoulder_y, right_x, hip_y),
        "bottom": (left_x, hip_y, right_x, ankle_y),
        "full": (left_x, shoulder_y, right_x, ankle_y),
        "shoulder_width": abs(rs[0] - ls[0]),
        "torso_height": abs(hip_y - shoulder_y),
        "leg_height": abs(ankle_y - hip_y),
    }
