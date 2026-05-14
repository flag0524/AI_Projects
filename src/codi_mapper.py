"""
codi_mapper.py — 코디 세트 매핑 모듈
input/codi_sets/ 폴더를 스캔하여
{코디번호: [품번, ...]} 형태의 딕셔너리를 반환합니다.
"""
from pathlib import Path
from loguru import logger
from config import CODI_SETS_DIR, RAW_PHOTOS_DIR, LAYER_ORDER


def load_codi_sets() -> dict[str, list[str]]:
    """
    input/codi_sets/ 폴더 구조를 스캔하여 코디 매핑을 반환합니다.

    폴더 구조 예시:
        input/codi_sets/C001/BLD-2401.jpg
        input/codi_sets/C001/BLD-2405.jpg

    Returns:
        {
            "C001": ["BLD-2401", "BLD-2405"],
            "C002": ["BLD-2403", "BLD-2404"],
            ...
        }
    """
    if not CODI_SETS_DIR.exists():
        logger.error(f"코디 세트 폴더 없음: {CODI_SETS_DIR}")
        return {}

    codi_map: dict[str, list[str]] = {}

    for codi_dir in sorted(CODI_SETS_DIR.iterdir()):
        if not codi_dir.is_dir():
            continue

        codi_id = codi_dir.name  # 예: C001
        item_codes = []

        for img_file in sorted(codi_dir.glob("*.jpg")):
            item_codes.append(img_file.stem)
        for img_file in sorted(codi_dir.glob("*.png")):
            item_codes.append(img_file.stem)
        for img_file in sorted(codi_dir.glob("*.jpeg")):
            item_codes.append(img_file.stem)

        if item_codes:
            codi_map[codi_id] = item_codes
            logger.debug(f"코디 {codi_id}: {item_codes}")
        else:
            logger.warning(f"코디 폴더 {codi_id}: 이미지 파일 없음")

    logger.info(f"코디 세트 로드 완료: {len(codi_map)}개 코디")
    return codi_map


def resolve_codi_images(
    codi_id: str,
    codi_map: dict[str, list[str]],
    products: dict[str, dict],
) -> list[dict]:
    """
    코디 ID에 해당하는 이미지 경로 목록을 레이어 순서로 정렬하여 반환합니다.

    Returns:
        [
            {"item_code": "BLD-2402", "category": "하의",  "layer": 2, "path": Path(...)},
            {"item_code": "BLD-2401", "category": "아우터", "layer": 4, "path": Path(...)},
            ...
        ]  ← layer 오름차순 정렬 (하의 → 상의 → 아우터 순으로 합성)
    """
    if codi_id not in codi_map:
        logger.error(f"코디 {codi_id}를 찾을 수 없습니다.")
        return []

    resolved = []
    for item_code in codi_map[codi_id]:
        # 이미지 파일 경로 탐색 (raw_photos 우선, codi_sets 폴더도 확인)
        img_path = _find_image(item_code, codi_id)
        if img_path is None:
            logger.warning(f"코디 {codi_id}: {item_code} 이미지 파일 없음 → 건너뜀")
            continue

        # 카테고리 정보 가져오기
        product_info = products.get(item_code, {})
        category = product_info.get("category", "")
        layer = _get_layer(category)

        resolved.append({
            "item_code": item_code,
            "category":  category,
            "layer":     layer,
            "path":      img_path,
            "product":   product_info,
        })

    # 레이어 순서로 정렬 (낮은 레이어가 먼저 합성 → 아래에 깔림)
    resolved.sort(key=lambda x: x["layer"])
    return resolved


def _find_image(item_code: str, codi_id: str) -> Path | None:
    """품번으로 이미지 파일 경로를 탐색합니다. raw_photos → codi_sets 순으로 탐색."""
    for ext in [".jpg", ".jpeg", ".png"]:
        # 1순위: raw_photos 폴더
        p = RAW_PHOTOS_DIR / f"{item_code}{ext}"
        if p.exists():
            return p
        # 2순위: codi_sets/코디ID 폴더
        p = CODI_SETS_DIR / codi_id / f"{item_code}{ext}"
        if p.exists():
            return p
    return None


def _get_layer(category: str) -> int:
    """카테고리명으로 레이어 순서를 반환합니다. 매핑되지 않으면 기본값 3."""
    return LAYER_ORDER.get(category, 3)
