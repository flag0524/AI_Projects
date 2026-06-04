import numpy as np
from PIL import Image
import cv2
import io
import base64


TARGET_SIZE = 512


def pil_to_cv2(img: Image.Image) -> np.ndarray:
    arr = np.array(img.convert("RGB"))
    return cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)


def cv2_to_pil(img: np.ndarray) -> Image.Image:
    if img.shape[2] == 4:
        return Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGRA2RGBA))
    return Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))


def bytes_to_pil(data: bytes) -> Image.Image:
    return Image.open(io.BytesIO(data)).convert("RGBA")


def pil_to_base64(img: Image.Image, fmt: str = "PNG") -> str:
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    encoded = base64.b64encode(buf.getvalue()).decode()
    return f"data:image/{fmt.lower()};base64,{encoded}"


def resize_with_padding(img: Image.Image, size: int = TARGET_SIZE) -> Image.Image:
    """비율을 유지하며 size×size 캔버스에 중앙 배치."""
    img = img.convert("RGBA")
    w, h = img.size
    scale = size / max(w, h)
    new_w, new_h = int(w * scale), int(h * scale)
    img = img.resize((new_w, new_h), Image.LANCZOS)
    canvas = Image.new("RGBA", (size, size), (255, 255, 255, 0))
    offset_x = (size - new_w) // 2
    offset_y = (size - new_h) // 2
    canvas.paste(img, (offset_x, offset_y), img)
    return canvas, (offset_x, offset_y, new_w, new_h)
