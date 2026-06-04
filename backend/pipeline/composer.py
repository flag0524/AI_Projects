import numpy as np
import cv2
from PIL import Image, ImageFilter

LAYER_ORDER = ["dress", "bottom", "top", "accessory"]


def _feather_mask(mask: np.ndarray, radius: int = 8) -> np.ndarray:
    """마스크 경계를 Gaussian 블러로 부드럽게."""
    blurred = cv2.GaussianBlur(mask.astype(np.float32), (radius * 2 + 1, radius * 2 + 1), 0)
    return np.clip(blurred, 0, 255).astype(np.uint8)


def _alpha_blend(base: np.ndarray, overlay: np.ndarray) -> np.ndarray:
    """RGBA 레이어 두 장을 알파 블렌딩."""
    base_f = base.astype(np.float32) / 255.0
    over_f = overlay.astype(np.float32) / 255.0

    a_over = over_f[:, :, 3:4]
    a_base = base_f[:, :, 3:4]

    out_a = a_over + a_base * (1 - a_over)
    out_a_safe = np.where(out_a > 0, out_a, 1e-6)

    out_rgb = (over_f[:, :, :3] * a_over + base_f[:, :, :3] * a_base * (1 - a_over)) / out_a_safe
    out = np.concatenate([out_rgb, out_a], axis=2)
    return np.clip(out * 255, 0, 255).astype(np.uint8)


def compose(
    mannequin: Image.Image,
    warped_garments: dict[str, Image.Image],
) -> Image.Image:
    """마네킹 위에 의류 레이어들을 순서대로 합성."""
    base = np.array(mannequin.convert("RGBA"))

    for gtype in LAYER_ORDER:
        if gtype not in warped_garments:
            continue
        garment_arr = np.array(warped_garments[gtype].convert("RGBA"))

        # 의류 마스크 경계 페더링
        alpha = garment_arr[:, :, 3].copy()
        alpha = _feather_mask(alpha, radius=6)
        garment_arr[:, :, 3] = alpha

        base = _alpha_blend(base, garment_arr)

    result = Image.fromarray(base, "RGBA")

    # 최종 흰 배경 합성
    white_bg = Image.new("RGBA", result.size, (255, 255, 255, 255))
    white_bg.paste(result, mask=result.split()[3])
    return white_bg.convert("RGB")
