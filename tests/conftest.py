"""pytest 공통 설정 — 프로젝트 루트를 import 경로에 추가 + 이미지 픽스처."""
import sys
from pathlib import Path

import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture
def img():
    """작은 더미 RGB 이미지."""
    return Image.new("RGB", (64, 64), (200, 200, 200))


@pytest.fixture
def png_bytes(img):
    import io
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()
