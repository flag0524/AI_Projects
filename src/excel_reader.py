"""
excel_reader.py — product_data.xlsx 파싱 모듈
품번, 품명, 카테고리, 최초판매가, 색상, 시즌, 코디그룹을 읽어
딕셔너리로 반환합니다.
"""
from pathlib import Path
import openpyxl
from loguru import logger
from config import PRODUCT_EXCEL, EXCEL_COLUMNS


def load_product_data() -> dict[str, dict]:
    """
    product_data.xlsx를 읽어 {품번: 상품정보dict} 형태로 반환합니다.

    Returns:
        {
            "BLD-2401": {
                "item_code": "BLD-2401",
                "item_name": "린넨 오버핏 재킷",
                "category": "아우터",
                "price": 89000,
                "color": "아이보리",
                "season": "2024SS",
                "codi_groups": ["C001"],
            },
            ...
        }
    """
    if not PRODUCT_EXCEL.exists():
        logger.critical(f"엑셀 파일을 찾을 수 없습니다: {PRODUCT_EXCEL}")
        raise FileNotFoundError(f"product_data.xlsx 없음: {PRODUCT_EXCEL}")

    wb = openpyxl.load_workbook(PRODUCT_EXCEL, read_only=True, data_only=True)

    # 첫 번째 시트 사용 (시트명 무관)
    ws = wb.worksheets[0]
    rows = list(ws.iter_rows(values_only=True))

    if not rows:
        logger.critical("엑셀 파일이 비어 있습니다.")
        raise ValueError("엑셀 파일이 비어 있습니다.")

    # ─── 헤더 파싱 ───
    header_row = [str(h).strip() if h is not None else "" for h in rows[0]]
    col_map = _build_col_map(header_row)

    # ─── 데이터 파싱 ───
    products: dict[str, dict] = {}
    col = EXCEL_COLUMNS  # 컬럼명 별칭

    for row_idx, row in enumerate(rows[1:], start=2):
        item_code = _get_cell(row, col_map, col["item_code"])
        if not item_code:
            continue  # 빈 행 건너뜀

        item_code = str(item_code).strip()

        # 코디그룹은 쉼표 구분 리스트로 변환
        codi_raw = _get_cell(row, col_map, col["codi_group"])
        codi_groups = (
            [g.strip() for g in str(codi_raw).split(",") if g.strip()]
            if codi_raw
            else []
        )

        price_raw = _get_cell(row, col_map, col["price"])
        try:
            price = int(str(price_raw).replace(",", "").replace("원", "").strip())
        except (ValueError, TypeError):
            price = 0
            logger.warning(f"Row {row_idx}: 가격 파싱 실패 [{price_raw}] → 0으로 설정")

        products[item_code] = {
            "item_code":   item_code,
            "item_name":   _get_cell(row, col_map, col["item_name"]) or "",
            "category":    _get_cell(row, col_map, col["category"]) or "",
            "price":       price,
            "color":       _get_cell(row, col_map, col["color"]) or "",
            "season":      _get_cell(row, col_map, col["season"]) or "",
            "codi_groups": codi_groups,
        }

    wb.close()
    logger.info(f"엑셀 로드 완료: {len(products)}개 상품")
    return products


def _build_col_map(header_row: list[str]) -> dict[str, int]:
    """헤더명 → 컬럼 인덱스 매핑 딕셔너리 생성"""
    col_map = {}
    for idx, h in enumerate(header_row):
        col_map[h] = idx
    return col_map


def _get_cell(row: tuple, col_map: dict, col_name: str):
    """컬럼명으로 셀 값 추출. 없으면 None 반환."""
    idx = col_map.get(col_name)
    if idx is None:
        return None
    if idx >= len(row):
        return None
    val = row[idx]
    return str(val).strip() if val is not None else None


def validate_mapping(products: dict, raw_photo_dir: Path) -> dict[str, list]:
    """
    엑셀 품번 ↔ 실제 파일 매핑 검증.
    Returns: {"matched": [...], "excel_only": [...], "file_only": [...]}
    """
    excel_codes = set(products.keys())
    file_codes = {
        f.stem for f in raw_photo_dir.glob("*.jpg")
    } | {
        f.stem for f in raw_photo_dir.glob("*.png")
    }

    matched    = sorted(excel_codes & file_codes)
    excel_only = sorted(excel_codes - file_codes)  # 엑셀에만 있음 (파일 없음)
    file_only  = sorted(file_codes - excel_codes)  # 파일만 있음 (엑셀 없음)

    if excel_only:
        logger.warning(f"엑셀에 있으나 이미지 파일 없음: {excel_only}")
    if file_only:
        logger.warning(f"이미지 파일이 있으나 엑셀에 없음: {file_only}")
    logger.info(f"매핑 검증: 매칭 {len(matched)}개 / 엑셀전용 {len(excel_only)}개 / 파일전용 {len(file_only)}개")

    return {"matched": matched, "excel_only": excel_only, "file_only": file_only}
