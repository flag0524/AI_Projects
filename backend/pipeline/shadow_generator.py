"""
의류 내부 그림자와 깊이감을 생성하는 모듈.
옷 가장자리에서 안쪽으로 그라디언트 그림자를 만들어 입체감을 부여한다.
"""
import numpy as np
import cv2


def generate_inner_shadow(
    mask: np.ndarray,
    shadow_radius: int = 30,
    shadow_intensity: float = 0.35,
    shadow_color: tuple = (20, 20, 20),
) -> np.ndarray:
    """
    마스크 내부 가장자리에 그림자 레이어(RGBA)를 생성.
    마스크 경계 → 안쪽으로 어두워지는 그라디언트.
    """
    # 거리 변환: 경계에서 내부까지의 거리
    dist = cv2.distanceTransform(mask, cv2.DIST_L2, 5)
    # shadow_radius 이내만 그림자 영역
    shadow_zone = np.clip(dist / shadow_radius, 0, 1)
    # 경계 근처일수록 강한 그림자 (1 - zone)
    shadow_alpha = (1.0 - shadow_zone) * shadow_intensity

    h, w = mask.shape
    shadow = np.zeros((h, w, 4), dtype=np.uint8)
    shadow[:, :, 0] = shadow_color[2]  # B
    shadow[:, :, 1] = shadow_color[1]  # G
    shadow[:, :, 2] = shadow_color[0]  # R
    shadow[:, :, 3] = (shadow_alpha * 255).astype(np.uint8)
    return shadow


def generate_fold_highlights(
    garment_arr: np.ndarray,
    mask: np.ndarray,
    intensity: float = 0.12,
) -> np.ndarray:
    """
    옷감 질감을 살리는 미세한 하이라이트 레이어 생성.
    세로 방향 그라디언트를 이용해 상단은 밝게, 하단은 어둡게.
    """
    h, w = garment_arr.shape[:2]
    gradient = np.linspace(1.0 + intensity, 1.0 - intensity, h).reshape(h, 1)
    gradient = np.tile(gradient, (1, w))

    result = garment_arr.copy().astype(np.float32)
    for c in range(3):
        result[:, :, c] = np.clip(result[:, :, c] * gradient, 0, 255)

    # 마스크 외부는 원본 유지
    mask_3d = mask[:, :, np.newaxis] / 255.0
    result[:, :, :3] = result[:, :, :3] * mask_3d + garment_arr[:, :, :3].astype(np.float32) * (1 - mask_3d)
    return result.astype(np.uint8)


def apply_garment_shadow_on_body(
    body_arr: np.ndarray,
    garment_mask: np.ndarray,
    shadow_radius: int = 15,
    shadow_intensity: float = 0.25,
) -> np.ndarray:
    """
    의류 아래에 마네킹 몸체에 드리우는 그림자 (drop shadow).
    의류 가장자리 → 바깥쪽으로 퍼지는 그림자를 마네킹 이미지에 합성.
    """
    # 마스크를 살짝 팽창시켜 drop shadow 영역 생성
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (shadow_radius, shadow_radius))
    dilated = cv2.dilate(garment_mask, kernel, iterations=1)
    drop_zone = cv2.subtract(dilated, garment_mask)

    # 블러로 부드럽게
    drop_blurred = cv2.GaussianBlur(drop_zone, (shadow_radius | 1, shadow_radius | 1), 0)
    drop_alpha = drop_blurred.astype(np.float32) / 255.0 * shadow_intensity

    result = body_arr.copy().astype(np.float32)
    for c in range(3):
        result[:, :, c] = result[:, :, c] * (1 - drop_alpha)
    return np.clip(result, 0, 255).astype(np.uint8)
