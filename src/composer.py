"""
composer.py — 마네킹 착장 합성 모듈
배경이 제거된 의류 이미지를 마네킹 템플릿 위에 레이어 순서대로 합성합니다.
원본 픽셀을 변형하지 않으며, 위치와 크기 조정(리사이즈)만 수행합니다.
"""
from pathlib import Path
import json

from PIL import Image
from loguru import logger

from config import (
    MANNEQUIN_TEMPLATES,
    ZONES_FILE,
    BACKGROUNDS_DIR,
    RESAMPLE_FILTER,
)
from bg_remover import remove_background


# 좌표 스펙 캐시
_zones: dict | None = None

def _load_zones() -> dict:
    global _zones
    if _zones is None:
        with open(ZONES_FILE, encoding="utf-8") as f:
            _zones = json.load(f)
    return _zones


def compose_single(
    item_code: str,
    image_path: Path,
    category: str,
    mannequin_view: str = "front",
    background_name: str = "bg_white",
    output_size: tuple[int, int] = (800, 1200),
) -> Image.Image | None:
    """
    단일 상품을 마네킹 위에 합성합니다.

    Args:
        item_code:       품번 (로그용)
        image_path:      원본 상품 이미지 경로
        category:        카테고리 (아우터/상의/하의/원피스 등)
        mannequin_view:  front / side / back
        background_name: 배경 파일명 (확장자 제외)
        output_size:     출력 이미지 크기 (width, height)

    Returns:
        PIL.Image (RGB) 또는 None (실패 시)
    """
    # 1. 배경 이미지 준비
    canvas = _load_background(background_name, output_size)

    # 2. 마네킹 템플릿 로드
    mannequin = _load_mannequin(mannequin_view, output_size)
    if mannequin is None:
        return None

    # 3. 배경 제거
    cloth_rgba = remove_background(image_path)
    if cloth_rgba is None:
        logger.error(f"{item_code}: 배경 제거 실패")
        return None

    # 4. 마네킹 위 합성
    zones = _load_zones()
    zone = _get_zone(zones, category)
    canvas = _paste_cloth_on_mannequin(canvas, mannequin, cloth_rgba, zone, output_size)

    return canvas


def compose_codi(
    codi_items: list[dict],
    mannequin_view: str = "front",
    background_name: str = "bg_studio",
    output_size: tuple[int, int] = (800, 1200),
) -> Image.Image | None:
    """
    코디 세트 (여러 아이템)를 레이어 순서대로 마네킹 위에 합성합니다.

    Args:
        codi_items: codi_mapper.resolve_codi_images() 반환값
                    [{"item_code", "category", "layer", "path", "product"}, ...]
                    layer 오름차순으로 정렬되어 있어야 함
    """
    # 1. 배경 준비
    canvas = _load_background(background_name, output_size)

    # 2. 마네킹 로드
    mannequin = _load_mannequin(mannequin_view, output_size)
    if mannequin is None:
        return None

    # 3. 마네킹을 캔버스에 먼저 붙임
    canvas_rgba = canvas.convert("RGBA")
    mannequin_resized = mannequin.resize(output_size, Image.LANCZOS)
    canvas_rgba.paste(mannequin_resized, (0, 0), mannequin_resized)

    zones = _load_zones()

    # 4. 레이어 순서대로 의류 합성
    for item in codi_items:
        cloth_rgba = remove_background(item["path"])
        if cloth_rgba is None:
            logger.warning(f"코디 합성 중 건너뜀: {item['item_code']}")
            continue

        zone = _get_zone(zones, item["category"])
        cloth_placed = _fit_cloth_to_zone(cloth_rgba, zone, output_size)
        canvas_rgba.paste(cloth_placed, (0, 0), cloth_placed)
        logger.debug(f"  레이어 합성: {item['item_code']} ({item['category']})")

    return canvas_rgba.convert("RGB")


# ──────────────────────────────────────────────────────────────
# 내부 헬퍼 함수
# ──────────────────────────────────────────────────────────────

def _load_background(name: str, size: tuple[int, int]) -> Image.Image:
    """배경 이미지를 로드하고 지정 크기로 리사이즈합니다."""
    for ext in [".png", ".jpg", ".jpeg"]:
        p = BACKGROUNDS_DIR / f"{name}{ext}"
        if p.exists():
            bg = Image.open(p).convert("RGBA")
            return bg.resize(size, Image.LANCZOS)

    # 배경 파일이 없으면 흰 배경 생성
    logger.debug(f"배경 파일 '{name}' 없음 → 흰 배경 사용")
    return Image.new("RGBA", size, (255, 255, 255, 255))


def _load_mannequin(view: str, size: tuple[int, int]) -> Image.Image | None:
    """마네킹 템플릿을 로드합니다."""
    template_path = MANNEQUIN_TEMPLATES.get(view)
    if template_path is None or not template_path.exists():
        logger.critical(f"마네킹 템플릿 없음: {view} → {template_path}")
        logger.critical("templates/ 폴더에 mannequin_front.png 등을 추가하세요.")
        return None
    mannequin = Image.open(template_path).convert("RGBA")
    return mannequin.resize(size, Image.LANCZOS)


def _get_zone(zones: dict, category: str) -> dict:
    """카테고리에 맞는 착장 좌표 존을 반환합니다."""
    zone_data = zones.get("zones", {})
    if category in zone_data:
        return zone_data[category]
    # 카테고리 매핑 실패 시 기본값
    logger.warning(f"카테고리 '{category}' 좌표 정의 없음 → '상의' 기본값 사용")
    return zone_data.get("상의", {"bbox": [155, 75, 645, 560], "pivot": "top_center"})


def _fit_cloth_to_zone(
    cloth_rgba: Image.Image,
    zone: dict,
    canvas_size: tuple[int, int],
) -> Image.Image:
    """
    의류 이미지를 존(bbox) 영역에 맞게 리사이즈하고
    전체 캔버스 크기의 투명 레이어에 배치합니다.
    """
    bbox = zone["bbox"]  # [x_left, y_top, x_right, y_bottom]
    x1, y1, x2, y2 = bbox
    zone_w = x2 - x1
    zone_h = y2 - y1

    # 비율 유지 리사이즈 (존 영역을 넘지 않게)
    cloth_w, cloth_h = cloth_rgba.size
    scale = min(zone_w / cloth_w, zone_h / cloth_h)
    new_w = int(cloth_w * scale)
    new_h = int(cloth_h * scale)

    resample = getattr(Image, RESAMPLE_FILTER, Image.LANCZOS)
    cloth_resized = cloth_rgba.resize((new_w, new_h), resample)

    # pivot 기준으로 배치 위치 계산
    pivot = zone.get("pivot", "top_center")
    if pivot == "top_center":
        paste_x = x1 + (zone_w - new_w) // 2
        paste_y = y1
    elif pivot == "center":
        paste_x = x1 + (zone_w - new_w) // 2
        paste_y = y1 + (zone_h - new_h) // 2
    else:
        paste_x = x1
        paste_y = y1

    # 전체 캔버스 크기 투명 레이어에 배치
    layer = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
    layer.paste(cloth_resized, (paste_x, paste_y), cloth_resized)
    return layer


def _paste_cloth_on_mannequin(
    canvas: Image.Image,
    mannequin: Image.Image,
    cloth_rgba: Image.Image,
    zone: dict,
    output_size: tuple[int, int],
) -> Image.Image:
    """단일 아이템 합성: 배경 → 의류 → 마네킹 순으로 레이어링"""
    canvas_rgba = canvas.convert("RGBA")

    # 의류 레이어
    cloth_layer = _fit_cloth_to_zone(cloth_rgba, zone, output_size)
    canvas_rgba.paste(cloth_layer, (0, 0), cloth_layer)

    # 마네킹 레이어 (의류 위에)
    canvas_rgba.paste(mannequin, (0, 0), mannequin)

    return canvas_rgba.convert("RGB")
