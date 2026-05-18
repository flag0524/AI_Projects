import logging
import json
from datetime import datetime
from pathlib import Path
from src.config import Config
from src.excel_reader import ExcelReader
from src.validator import InputValidator
from src.bg_remover import BackgroundRemover
from src.composer import ImageComposer

class StandardPipeline:
    """
    Standard Engine의 전체 프로세스를 제어하는 파이프라인
    [데이터 로드 -> 배경 제거 -> 합성 -> 저장]
    """
    def __init__(self):
        self.reader = ExcelReader()
        self.validator = None # load_product_data 후 초기화
        self.bg_remover = BackgroundRemover()
        self.composer = ImageComposer()

    def setup(self):
        """파이프라인 실행 전 필수 데이터 로드 및 검증"""
        self.reader.load_product_data()
        self.validator = InputValidator(self.reader)

    def render_item(self, item_id: str, preset: str = "single_front", dry_run=False):
        """
        단일 품번 기준 렌더링 프로세스 (DoD: 단건 렌더 가능)
        """
        try:
            logging.info(f"Standard Render 시작: {item_id} (Preset: {preset})")

            # 1. 데이터 확인 (2순위: 정확한 매핑)
            product_info = self.reader.product_df[self.reader.product_df['품번'] == item_id]
            if product_info.empty:
                raise ValueError(f"품번 {item_id}에 해당하는 데이터가 엑셀에 없습니다.")
            
            category = product_info.iloc[0]['카테고리']
            img_path_jpg = Config.RAW_PHOTOS_DIR / f"{item_id}.jpg"
            img_path_png = Config.RAW_PHOTOS_DIR / f"{item_id}.png"

            if img_path_jpg.exists():
                img_path = img_path_jpg
            elif img_path_png.exists():
                img_path = img_path_png
            else:
                raise FileNotFoundError(f"이미지 파일이 없습니다 (jpg/png 모두 없음): {item_id}")

            if dry_run:
                logging.info(f"[Dry-Run] {item_id} 렌더링 예정: {category} -> {preset}")
                return True

            # 2. 배경 제거 (3순위: 시각 정체성 보존)
            product_rgba = self.bg_remover.remove_background(img_path)

            # 3. 마네킹 합성 (DoD: 상품 식별 가능성 유지)
            # 현재는 기본 마네킹 템플릿 하나를 사용 (추후 preset별 템플릿 확장 가능)
            mannequin_template = Config.MANNEQUIN_DIR / "default_mannequin.png"
            if not mannequin_template.exists():
                # 템플릿이 없을 경우를 대비해 빈 캔버스 생성 또는 에러 처리
                raise FileNotFoundError(f"마네킹 템플릿 파일이 없습니다: {mannequin_template}")

            final_image = self.composer.compose(mannequin_template, product_rgba, category)

            # 4. 저장 및 파일명 규칙 적용 (DoD: 파일명 규칙 준수)
            date_str = datetime.now().strftime("%Y%m%d")
            output_filename = f"{item_id}_{preset}_{date_str}.jpg"
            output_path = Config.OUTPUT_STANDARD / output_filename
            
            final_image.save(output_path, "JPEG", quality=95)
            
            # 5. 로그 기록 (DoD: 로그 기록 정상)
            self._log_process(item_id, preset, "SUCCESS", str(output_path))
            logging.info(f"렌더링 완료: {output_path}")
            
            return True

        except Exception as e:
            logging.error(f"Standard Render 실패 ({item_id}): {e}")
            self._log_process(item_id, preset, "FAILED", reason=str(e))
            return False

    def _log_process(self, item_id, preset, status, output_path=None, reason=None):
        """구조화된 로그 기록 (CLAUDE.md Section 10.6 준수)"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "item_id": item_id,
            "engine": "Standard",
            "preset": preset,
            "status": status,
            "output_path": output_path,
            "error_message": reason
        }
        with open(Config.LOGS_DIR / "process_log.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")