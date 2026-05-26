import os
from pathlib import Path

class Config:
    # Base Path
    BASE_DIR = Path(__file__).parent.parent
    
    # Input Paths
    RAW_PHOTOS_DIR = BASE_DIR / "input" / "raw_photos"
    CODI_SETS_DIR = BASE_DIR / "input" / "codi_sets"
    PRODUCT_DATA_FILE = BASE_DIR / "input" / "product_data.xlsx"
    STYLE_TAGS_FILE = BASE_DIR / "input" / "style_tags.xlsx"
    
    # Template Paths
    MANNEQUIN_DIR = BASE_DIR / "templates" / "mannequin"
    HYBRID_MODELS_DIR = BASE_DIR / "templates" / "hybrid_models"
    POSES_DIR = BASE_DIR / "templates" / "poses"
    BACKGROUNDS_DIR = BASE_DIR / "templates" / "backgrounds"
    
    # Specs Paths
    SPECS_DIR = BASE_DIR / "specs"
    COLOR_LOCK_RULES = SPECS_DIR / "color_lock_rules.json"
    NAMING_RULES = SPECS_DIR / "naming_rules.json"
    QUALITY_THRESHOLDS = SPECS_DIR / "quality_thresholds.json"
    
    # Output Paths
    OUTPUT_STANDARD = BASE_DIR / "output" / "standard"
    OUTPUT_HYBRID = BASE_DIR / "output" / "hybrid"
    OUTPUT_QC = BASE_DIR / "output" / "qc_reports"
    
    # Log Paths
    LOGS_DIR = BASE_DIR / "logs"
    PROCESS_LOG = LOGS_DIR / "process_log.jsonl"
    HYBRID_LOG = LOGS_DIR / "hybrid_log.jsonl"
    QC_LOG = LOGS_DIR / "qc_log.jsonl"
    ERROR_LOG = LOGS_DIR / "error_log.jsonl"

    @classmethod
    def ensure_dirs(cls):
        """필요한 모든 디렉토리가 존재하는지 확인하고 생성"""
        dirs = [
            cls.RAW_PHOTOS_DIR, cls.CODI_SETS_DIR, cls.MANNEQUIN_DIR,
            cls.HYBRID_MODELS_DIR, cls.POSES_DIR, cls.BACKGROUNDS_DIR,
            cls.SPECS_DIR, cls.OUTPUT_STANDARD, cls.OUTPUT_HYBRID,
            cls.OUTPUT_QC, cls.LOGS_DIR
        ]
        for d in dirs:
            d.mkdir(parents=True, exist_ok=True)