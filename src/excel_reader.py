import pandas as pd
from src.config import Config
import logging

class ExcelReader:
    """
    상품 데이터 및 스타일 태그 엑셀 파일을 읽고 검증하는 모듈
    """
    def __init__(self):
        self.product_df = None
        self.style_df = None

    def load_product_data(self):
        """상품 원본 데이터 로드 및 필수 컬럼 검증"""
        try:
            if not Config.PRODUCT_DATA_FILE.exists():
                raise FileNotFoundError(f"상품 데이터 파일이 없습니다: {Config.PRODUCT_DATA_FILE}")
            
            df = pd.read_excel(Config.PRODUCT_DATA_FILE)
            required_cols = ['품번', '품명', '카테고리', '가격', '색상', '코디그룹']
            
            # 필수 컬럼 검증
            missing_cols = [col for col in required_cols if col not in df.columns]
            if missing_cols:
                raise ValueError(f"엑셀 파일에 필수 컬럼이 누락되었습니다: {missing_cols}")
            
            self.product_df = df
            logging.info(f"상품 데이터 로드 완료: {len(df)}건")
            return self.product_df
        except Exception as e:
            logging.error(f"상품 데이터 로드 중 오류 발생: {e}")
            raise

    def load_style_tags(self):
        """스타일 태그 데이터 로드"""
        try:
            if not Config.STYLE_TAGS_FILE.exists():
                logging.warning(f"스타일 태그 파일이 없습니다. 기본 설정을 사용합니다: {Config.STYLE_TAGS_FILE}")
                return None
            
            df = pd.read_excel(Config.STYLE_TAGS_FILE)
            self.style_df = df
            logging.info(f"스타일 태그 데이터 로드 완료: {len(df)}건")
            return self.style_df
        except Exception as e:
            logging.error(f"스타일 태그 로드 중 오류 발생: {e}")
            return None