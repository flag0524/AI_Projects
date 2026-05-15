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
        전체 상품 데이터와 이미지 파일의 일치 여부를 검사
        """
        if self.reader.product_df is None:
            logging.error("검증 실패: 상품 데이터가 로드되지 않았습니다.")
            return {"status": "error", "message": "No data loaded"}

        df = self.reader.product_df
        total_count = len(df)
        missing_files = []
        valid_files = []

        logging.info(f"입력 데이터 검증 시작 (총 {total_count}건)...")

        for _, row in df.iterrows():
            item_id = row['품번']
            img_path = Config.RAW_PHOTOS_DIR / f"{item_id}.jpg"
            
            if not img_path.exists():
                missing_files.append({
                    "item_id": item_id,
                    "expected_path": str(img_path),
                    "reason": "File not found"
                })
            else:
                valid_files.append(item_id)

        # 결과 리포트 생성
        report = {
            "total_items": total_count,
            "valid_count": len(valid_files),
            "missing_count": len(missing_files),
            "missing_list": missing_files
        }

        if len(missing_files) > 0:
            logging.error(f"검증 완료: {len(missing_files)}개의 파일이 누락되었습니다.")
            self._save_missing_report(missing_files)
        else:
            logging.info("검증 완료: 모든 파일이 정상적으로 존재합니다.")

        return report if not missing_only else {"missing": missing_files}

    def _save_missing_report(self, missing_list):
        """누락 리스트를 JSON 파일로 저장"""
        report_path = Config.OUTPUT_QC / "missing_files_report.json"
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(missing_list, f, indent=4, ensure_ascii=False)
        logging.info(f"누락 리포트가 생성되었습니다: {report_path}")