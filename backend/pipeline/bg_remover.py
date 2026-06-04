from PIL import Image
from rembg import remove


def remove_background(img: Image.Image) -> Image.Image:
    """U²-Net 기반 배경 제거. 출력은 RGBA."""
    return remove(img)
