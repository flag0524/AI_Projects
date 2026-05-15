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

        for _, row in df.iterrows():
            item_id = str(row['품번']).strip()
            img_path = Config.RAW_PHOTOS_DIR / f"{item_id}.jpg"
            
            # 1. 파일 존재 여부 검사 (2순위: 정확한 매핑)
            if not img_path.exists():
                missing_files.append({
                    "item_id": item_id,
                    "expected_path": str(img_path),
                    "reason": "FILE_NOT_FOUND"
                })
                continue
            
            # 2. 파일명 규칙 검사 (1순위: 정책 위반 방지)
            # 예: 품번이 'BD-001'인데 파일명이 'BD 001.jpg'인 경우 에러
            if not img_path.name == f"{item_id}.jpg":
                naming_errors.append({
                    "item_id": item_id,
                    "actual_name": img_path.name,
                    "expected_name": f"{item_id}.jpg",
                    "reason": "NAMING_RULE_VIOLATION"
                })
                continue

            valid_files.append(item_id)

        # 결과 리포트 생성
        report = {
            "total_items": total_count,
            "valid_count": len(valid_files),
            "missing_count": len(missing_files),
            "naming_error_count": len(naming_errors),
            "missing_list": missing_files,
            "naming_error_list": naming_errors
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