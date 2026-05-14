"""
BMS (BLANCDEW Mannequin Styler) — 중앙 설정 파일
모든 경로, 상수, 설정값은 이 파일에서만 정의합니다.
"""
from pathlib import Path

# ────────────────────────────────────────────────────────────────
# 기본 경로
# ────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent.parent  # d:\blandu_project

INPUT_DIR        = BASE_DIR / "input"
RAW_PHOTOS_DIR   = INPUT_DIR / "raw_photos"
CODI_SETS_DIR    = INPUT_DIR / "codi_sets"
PRODUCT_EXCEL    = INPUT_DIR / "product_data.xlsx"

TEMPLATES_DIR    = BASE_DIR / "templates"
BACKGROUNDS_DIR  = TEMPLATES_DIR / "backgrounds"

OUTPUT_DIR       = BASE_DIR / "output"
OUTPUT_SINGLE    = OUTPUT_DIR / "single"
OUTPUT_CODI      = OUTPUT_DIR / "codi"
OUTPUT_LOOKBOOK  = OUTPUT_DIR / "lookbook"
OUTPUT_CATALOG   = OUTPUT_DIR / "catalog"

SPECS_DIR        = BASE_DIR / "specs"
ZONES_FILE       = SPECS_DIR / "mannequin_zones.json"
PRESETS_FILE     = SPECS_DIR / "render_presets.json"

LOGS_DIR         = BASE_DIR / "logs"
LOG_FILE         = LOGS_DIR / "process_log.jsonl"

# ────────────────────────────────────────────────────────────────
# 마네킹 템플릿 파일
# ────────────────────────────────────────────────────────────────
MANNEQUIN_TEMPLATES = {
    "front": TEMPLATES_DIR / "mannequin_front.png",
    "side":  TEMPLATES_DIR / "mannequin_side.png",
    "back":  TEMPLATES_DIR / "mannequin_back.png",
}

# ────────────────────────────────────────────────────────────────
# 품번 파일명 패턴 (정규식)
# 실제 품번 형식에 맞게 수정하세요
# 예) BLD-2401 형식 → r"^[A-Z]{2,4}-\d{4}$"
# ────────────────────────────────────────────────────────────────
ITEM_CODE_PATTERN = r"^[A-Z]{2,4}-\d{3,5}$"

# ────────────────────────────────────────────────────────────────
# 이미지 처리 설정
# ────────────────────────────────────────────────────────────────
IMAGE_QUALITY    = 95          # JPEG 저장 품질 (0~100, 95 권장)
RESAMPLE_FILTER  = "LANCZOS"   # 리사이즈 필터 (품질 최우선)
BG_REMOVE_MODEL  = "u2net"     # rembg 모델 (u2net: 범용, u2net_cloth: 의류 특화)

# 카테고리별 착장 레이어 순서 (숫자가 클수록 위에 합성)
LAYER_ORDER = {
    "원피스": 1,
    "dress": 1,
    "하의": 2,
    "skirt": 2,
    "pants": 2,
    "상의": 3,
    "top": 3,
    "blouse": 3,
    "아우터": 4,
    "outer": 4,
    "jacket": 4,
    "coat": 4,
}

# ────────────────────────────────────────────────────────────────
# 출력 설정
# ────────────────────────────────────────────────────────────────
OUTPUT_DATE_FORMAT = "%Y%m%d"   # 파일명에 사용할 날짜 형식

# 카탈로그 워터마크 설정
CATALOG_FONT_SIZE   = 28
CATALOG_PRICE_COLOR = (50, 50, 50)     # 다크 그레이
CATALOG_CODE_COLOR  = (120, 120, 120)  # 라이트 그레이

# ────────────────────────────────────────────────────────────────
# 엑셀 컬럼명 매핑 (엑셀 헤더와 다를 경우 이 곳에서 수정)
# ────────────────────────────────────────────────────────────────
EXCEL_COLUMNS = {
    "item_code":    "품번",
    "item_name":    "품명",
    "category":     "카테고리",
    "price":        "최초판매가",
    "color":        "색상",
    "season":       "시즌",
    "codi_group":   "코디그룹",
}
