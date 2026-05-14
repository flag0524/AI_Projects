"""
layout_engine.py — 레이아웃 생성 모듈
단품 / 코디 / 룩북 2열 / 카탈로그 카드 레이아웃을 생성합니다.
"""
from pathlib import Path
from datetime import datetime

from PIL import Image, ImageDraw, ImageFont
from loguru import logger

from config import (
    OUTPUT_SINGLE, OUTPUT_CODI, OUTPUT_LOOKBOOK, OUTPUT_CATALOG,
    IMAGE_QUALITY, OUTPUT_DATE_FORMAT,
    CATALOG_FONT_SIZE, CATALOG_PRICE_COLOR, CATALOG_CODE_COLOR,
)


OUTPUT_FOLDER_MAP = {
    "single": OUTPUT_SINGLE,
    "codi":   OUTPUT_CODI,
    "lookbook": OUTPUT_LOOKBOOK,
    "catalog":  OUTPUT_CATALOG,
}


def save_single(
    image: Image.Image,
    identifier: str,
    preset_id: str,
    output_folder: str = "single",
) -> Path:
    """단품 또는 코디 이미지를 저장합니다."""
    date_str = datetime.now().strftime(OUTPUT_DATE_FORMAT)
    filename = f"{identifier}_{preset_id}_{date_str}.jpg"
    out_dir = OUTPUT_FOLDER_MAP.get(output_folder, OUTPUT_SINGLE)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / filename

    _save_jpg(image, out_path)
    logger.info(f"저장 완료: {out_path}")
    return out_path


def build_lookbook_2col(
    image_left: Image.Image,
    image_right: Image.Image,
    output_size: tuple[int, int] = (1600, 1200),
    gap: int = 40,
    background_color: tuple = (245, 245, 245),
) -> Image.Image:
    """
    2열 룩북 레이아웃: 두 이미지를 좌우로 배치합니다.

    Args:
        image_left:  왼쪽 코디 이미지
        image_right: 오른쪽 코디 이미지
        output_size: 출력 크기 (width, height)
        gap:         두 이미지 사이 간격 (px)
        background_color: 배경색 RGB
    """
    total_w, total_h = output_size
    cell_w = (total_w - gap * 3) // 2
    cell_h = total_h - gap * 2

    canvas = Image.new("RGB", output_size, background_color)

    for idx, img in enumerate([image_left, image_right]):
        # 비율 유지 리사이즈
        img_resized = _fit_image(img, (cell_w, cell_h))
        x = gap + idx * (cell_w + gap)
        y = gap + (cell_h - img_resized.size[1]) // 2
        canvas.paste(img_resized, (x, y))

    return canvas


def build_catalog_card(
    image: Image.Image,
    item_code: str,
    item_name: str,
    price: int,
    output_size: tuple[int, int] = (800, 1100),
    padding_bottom: int = 120,
) -> Image.Image:
    """
    카탈로그 카드: 이미지 아래에 품번과 가격 정보를 추가합니다.

    Args:
        image:         마네킹 착장 이미지
        item_code:     품번
        item_name:     품명
        price:         최초판매가
        output_size:   카드 전체 크기
        padding_bottom: 하단 정보 영역 높이 (px)
    """
    card_w, card_h = output_size
    img_h = card_h - padding_bottom

    # 상품 이미지 영역
    canvas = Image.new("RGB", output_size, (255, 255, 255))
    img_resized = _fit_image(image, (card_w, img_h))
    img_x = (card_w - img_resized.width) // 2
    canvas.paste(img_resized, (img_x, 0))

    # 텍스트 정보 영역 (하단)
    draw = ImageDraw.Draw(canvas)

    # 구분선
    line_y = img_h + 15
    draw.line([(40, line_y), (card_w - 40, line_y)], fill=(220, 220, 220), width=1)

    # 폰트 로드 (시스템 폰트 사용, 없으면 기본 폰트)
    font_price = _load_font(CATALOG_FONT_SIZE + 4, bold=True)
    font_code  = _load_font(CATALOG_FONT_SIZE - 4)
    font_name  = _load_font(CATALOG_FONT_SIZE - 2)

    text_y = line_y + 20

    # 품번
    draw.text((40, text_y), item_code, font=font_code, fill=CATALOG_CODE_COLOR)

    # 품명
    draw.text((40, text_y + 28), item_name, font=font_name, fill=(80, 80, 80))

    # 가격 (우측 정렬)
    price_text = f"₩{price:,}"
    bbox = draw.textbbox((0, 0), price_text, font=font_price)
    price_w = bbox[2] - bbox[0]
    draw.text((card_w - 40 - price_w, text_y + 10), price_text,
              font=font_price, fill=CATALOG_PRICE_COLOR)

    return canvas


def _fit_image(img: Image.Image, max_size: tuple[int, int]) -> Image.Image:
    """비율을 유지하면서 max_size 내로 리사이즈합니다."""
    img_copy = img.copy()
    img_copy.thumbnail(max_size, Image.LANCZOS)
    return img_copy


def _save_jpg(image: Image.Image, path: Path):
    """RGB 변환 후 JPEG로 저장합니다."""
    if image.mode != "RGB":
        image = image.convert("RGB")
    image.save(path, format="JPEG", quality=IMAGE_QUALITY, optimize=True)


def _load_font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    """시스템 폰트를 로드합니다. 실패 시 기본 폰트 반환."""
    font_candidates = [
        "C:/Windows/Fonts/malgun.ttf",       # 맑은 고딕 (Windows 한글)
        "C:/Windows/Fonts/malgunbd.ttf",     # 맑은 고딕 Bold
        "C:/Windows/Fonts/NanumGothic.ttf",  # 나눔고딕
        "C:/Windows/Fonts/arial.ttf",
    ]
    for font_path in font_candidates:
        try:
            return ImageFont.truetype(font_path, size)
        except (IOError, OSError):
            continue
    return ImageFont.load_default()
