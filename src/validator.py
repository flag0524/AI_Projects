import logging
import json
from pathlib import Path
from src.config import Config
from src.excel_reader import ExcelReader

class InputValidator:
    """
    입력 데이터 및 이미지 파일의 정합성을 검증하는 모듈
    """
    def __init__(self, reader: ExcelReader):
        self.reader = reader

    def validate_all(self, missing_only=False):
        """
        전체 상품 데이터와 이미지 파일의 일치 여부 및 명명 규칙 검사
        """
        if self.reader.product_df is None:
            logging.error("검증 실패: 상품 데이터가 로드되지 않았습니다.")
            return {"status": "error", "message": "No data loaded"}

        df = self.reader.product_df
        total_count = len(df)
        missing_files = []
        naming_errors = []
        valid_files = []

        logging.info(f"입력 데이터 검증 시작 (총 {total_count}건)...")

        # 1. 엑셀 기준 파일 존재 및 명명 규칙 검사
        for _, row in df.iterrows():
            item_id = str(row['품번']).strip()
            expected_name = f"{item_id}.jpg"
            img_path = Config.RAW_PHOTOS_DIR / expected_name
            
            if not img_path.exists():
                missing_files.append({
                    "item_id": item_id,
                    "expected_path": str(img_path),
                    "error_code": "E1",
                    "reason": "FILE_NOT_FOUND"
                })
                continue
            
            # 실제 파일명과 기대 파일명 대조 (대소문자 및 공백 엄격 검사)
            if img_path.name != expected_name:
                naming_errors.append({
                    "item_id": item_id,
                    "actual_name": img_path.name,
                    "expected_name": expected_name,
                    "error_code": "E2",
                    "reason": "NAMING_RULE_VIOLATION"
                })
                continue

            valid_files.append(item_id)

        # 2. Orphan Image 검사 (엑셀에 없는 파일이 폴더에 존재하는 경우)
        all_files = list(Config.RAW_PHOTOS_DIR.glob("*.jpg"))
        excel_item_ids = set(df['품번'].astype(str).str.strip().tolist())
        
        orphan_files = []
        for f in all_files:
            item_id_from_file = f.stem # .jpg 제외 파일명
            if item_id_from_file not in excel_item_ids:
                orphan_files.append({
                    "filename": f.name,
                    "error_code": "E3",
                    "reason": "ORPHAN_IMAGE"
                })

        # 결과 리포트 생성
        report = {
            "total_items": total_count,
            "valid_count": len(valid_files),
            "missing_count": len(missing_files),
            "naming_error_count": len(naming_errors),
            "orphan_count": len(orphan_files),
            "missing_list": missing_files,
            "naming_error_list": naming_errors,
            "orphan_list": orphan_files
        }

        if len(missing_files) > 0 or len(naming_errors) > 0:
            logging.error(f"검증 완료: 누락 {len(missing_files)}건, 명명오류 {len(naming_errors)}건 발생.")
            self._save_full_report(report)
        else:
            logging.info("검증 완료: 모든 데이터와 파일이 정책에 맞게 준비되었습니다.")

        return report if not missing_only else {"missing": missing_files, "naming_errors": naming_errors}

    def _save_full_report(self, report):
        """전체 검증 리포트를 JSON 파일로 저장"""
        report_path = Config.OUTPUT_QC / "input_validation_report.json"
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=4, ensure_ascii=False)
        logging.info(f"상세 검증 리포트가 생성되었습니다: {report_path}")

    def _save_missing_report(self, missing_list):
        """누락 리스트를 JSON 파일로 저장"""
        report_path = Config.OUTPUT_QC / "missing_files_report.json"
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(missing_list, f, indent=4, ensure_ascii=False)
        logging.info(f"누락 리포트가 생성되었습니다: {report_path}")