import logging
import json
from pathlib import Path
from PIL import Image
from src.config import Config

class ImageComposer:
    """
    배경 제거된 상품 이미지를 마네킹 템플릿 위에 정밀하게 합성하는 모듈
    """
    def __init__(self):
        self.zones = self._load_zones()

    def _load_zones(self):
        with open(Config.SPECS_DIR / "mannequin_zones.json", 'r', encoding='utf-8') as f:
            return json.load(f)

    def compose(self, mannequin_path: Path, product_image: Image.Image, category: str) -> Image.Image:
        """
        마네킹 이미지 위에 상품 이미지를 카테고리별 좌표에 맞춰 합성
        """
        try:
            # 1. 마네킹 템플릿 로드
            canvas = Image.open(mannequin_path).convert("RGBA")
            
            # 2. 카테고리별 좌표 정보 가져오기
            zone = self.zones["categories"].get(category.upper())
            if not zone:
                logging.warning(f"정의되지 않은 카테고리 {category}. 기본 좌표를 사용합니다.")
                zone = self.zones["categories"]["TOP"]

            # 3. 상품 이미지 리사이즈 (3순위: 리사이즈는 허용하되 왜곡은 금지)
            # 원본 비율을 유지하며 scale 적용
            target_w = int(canvas.width * zone["scale"])
            aspect_ratio = product_image.height / product_image.width
            target_h = int(target_w * aspect_ratio)
            
            product_resized = product_image.resize((target_w, target_h), Image.Resampling.LANCZOS)
            
            # 4. 합성 위치 계산 (중앙 정렬 + offset)
            pos_x = zone["position"][0] - (target_w // 2) + zone["offset_x"]
            pos_y = zone["position"][1] - (target_h // 2) + zone["offset_y"]
            
            # 5. 알파 채널을 이용한 합성 (Paste)
            canvas.paste(product_resized, (int(pos_x), int(pos_y)), product_resized)
            
            return canvas.convert("RGB") # 최종 결과물은 JPG 저장을 위해 RGB 변환
            
        except Exception as e:
            logging.error(f"합성 중 오류 발생: {e}")
            raise