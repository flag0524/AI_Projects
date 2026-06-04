import cv2
import numpy as np
from PIL import Image, ImageFilter
from loguru import logger

class PostProcessor:
    def __init__(self, enable_blend=True, enable_color_harmony=True, enable_denoise=True):
        self.enable_blend = enable_blend
        self.enable_color_harmony = enable_color_harmony
        self.enable_denoise = enable_denoise

    def apply(self, image: Image.Image, mask: Image.Image = None) -> Image.Image:
        """
        RECONSTRUCTION_REPORT의 포스트프로세싱 파이프라인 적용
        """
        img_np = np.array(image.convert("RGB"))
        
        # 1. 노이즈 제거 (Fast Gaussian Blur) - MX450/CPU 환경 속도 최적화
        if self.enable_denoise:
            img_np = cv2.GaussianBlur(img_np, (5, 5), 0)

        # 2. 색감 조화 (HSV Color Harmony)
        if self.enable_color_harmony:
            hsv = cv2.cvtColor(img_np, cv2.COLOR_RGB2HSV)
            hsv[:, :, 2] = cv2.multiply(hsv[:, :, 2], np.array([1.1]))
            img_np = cv2.cvtColor(hsv, cv2.COLOR_HSV2RGB)

        # 3. 경계 블렌딩 (Mask 기반) — 비파괴: 의류 영역은 선명 유지,
        #    그 외(배경/마네킹)는 약하게 부드럽게만 처리. 차원이 맞을 때만 적용.
        if self.enable_blend and mask is not None:
            mask_np = np.array(mask.convert("L"))
            if mask_np.shape[:2] == img_np.shape[:2]:
                mask_blur = cv2.GaussianBlur(mask_np, (15, 15), 0)[:, :, np.newaxis] / 255.0
                softened = cv2.GaussianBlur(img_np, (0, 0), 2)
                # 마스크=1 → 원본, 마스크=0 → 살짝 흐린 배경 (검게 만들지 않음)
                img_np = (img_np * mask_blur + softened * (1.0 - mask_blur)).astype(np.uint8)

        # 4. 선명도 조정 (Unsharp Masking)
        gaussian = cv2.GaussianBlur(img_np, (0, 0), 3)
        img_np = cv2.addWeighted(img_np, 1.5, gaussian, -0.5, 0)

        return Image.fromarray(img_np)

def postprocess(image, mask=None, background=None, **kwargs):
    """
    layering.py 등에서 호출하는 함수형 인터페이스
    """
    logger.debug("Postprocess 함수 호출됨")
    pp = PostProcessor(
        enable_blend=kwargs.get('enable_blend', True),
        enable_color_harmony=kwargs.get('enable_color_harmony', True),
        enable_denoise=kwargs.get('enable_denoise', True)
    )
    return pp.apply(image, mask=mask)