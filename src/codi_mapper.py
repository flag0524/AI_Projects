import pandas as pd
import logging
from src.config import Config
from src.excel_reader import ExcelReader

class CodiMapper:
    """
    코디그룹별 상품 매핑 및 경로 관리 모듈
    """
    def __init__(self, reader: ExcelReader):
        self.reader = reader
        self.product_df = reader.product_df

    def get_items_by_codi(self, codi_id: str):
        """
        특정 코디그룹 ID에 속한 모든 상품 정보를 반환
        """
        if self.product_df is None:
            raise ValueError("상품 데이터가 로드되지 않았습니다. ExcelReader를 먼저 실행하세요.")

        # 코디그룹 컬럼에서 해당 ID 필터링
        items = self.product_df[self.product_df['코디그룹'] == codi_id]
        
        if items.empty:
            logging.warning(f"코디그룹 {codi_id}에 해당하는 상품이 없습니다.")
            return []

        # 상품 정보 리스트로 변환 (품번, 경로 등)
        result = []
        for _, row in items.iterrows():
            item_id = row['품번']
            result.append({
                "item_id": item_id,
                "category": row['카테고리'],
                "color": row['색상'],
                "image_path": Config.RAW_PHOTOS_DIR / f"{item_id}.jpg"
            })
        
        return result

    def get_all_codi_groups(self):
        """전체 코디그룹 목록 반환"""
        if self.product_df is None:
            return []
        return self.product_df['코디그룹'].unique().tolist()