from PIL import Image
from backend.utils.image_utils import resize_with_padding, TARGET_SIZE


def preprocess(img: Image.Image) -> tuple[Image.Image, tuple]:
    """이미지를 512×512로 리사이즈하고 패딩 정보를 반환."""
    resized, bbox = resize_with_padding(img, TARGET_SIZE)
    return resized, bbox
