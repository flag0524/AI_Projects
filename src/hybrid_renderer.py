import logging
import json
import sys
import os
from pathlib import Path
import numpy as np
import cv2
from PIL import Image, ImageEnhance
from src.config import Config

class HybridRenderer:
    """
    [운영 무기 - Mock 버전]
    CUDA 환경 이슈 해결 전까지 AI 모델 로딩을 완전히 배제하고 
    이미지 프로세싱을 통해 파이프라인 연결과 파일 생성을 증명합니다.
    """
    def __init__(self, device=None):
        # AI 모델 로딩 부분을 완전히 삭제하여 CUDA AssertionError를 원천 차단
        self.device = "cpu"
        logging.info(f"Hybrid Renderer (MOCK MODE) 초기화 완료. Device: {self.device}")
        
        self.profiles_data = self._load_profiles()
        self.muse_profiles = self.profiles_data.get("muses", {})
        self.global_mood = self.profiles_data.get("global_brand_mood", "Minimal, Modern")
        self.pipeline = None # 모델 로드 안 함

    def _load_profiles(self):
        with open(Config.SPECS_DIR / "muse_profiles.json", 'r', encoding='utf-8') as f:
            return json.load(f)

    def render_hybrid(self, item_id: str, muse_id: str, preset: str = "muse_lookbook"):
        try:
            logging.info(f"Hybrid Render (Mock) 시작: {item_id} with {muse_id}")
            
            # 1. Standard Engine 결과물 로드
            standard_img = self._get_standard_result(item_id)
            if standard_img is None:
                logging.warning(f"Standard 결과물이 없어 임시 이미지를 생성합니다: {item_id}")
                standard_img = Image.new('RGB', (512, 768), color=(200, 200, 200))

            # 2. 뮤즈 프로필 로드
            muse = self.muse_profiles.get(muse_id, {"name": "Default Muse", "visual_prompts": "chic look"})

            # 3. AI 효과 모사 (Mocking)
            img_array = np.array(standard_img)
            
            # 뮤즈 무드 반영 (색조 조정)
            if "Urban" in muse.get("name", ""):
                img_array = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
                img_array = cv2.cvtColor(img_array, cv2.COLOR_BGR2LAB)
                img_array[:, :, 0] = np.clip(img_array[:, :, 0] - 15, 0, 255) 
                img_array = cv2.cvtColor(img_array, cv2.COLOR_LAB2RGB)
            
            result_img = Image.fromarray(img_array.astype('uint8'))
            enhancer = ImageEnhance.Contrast(result_img)
            result_img = enhancer.enhance(1.2)
            
            # 4. 최종 결과 저장
            output_filename = f"{item_id}_{muse_id}_{preset}.jpg"
            output_path = Config.OUTPUT_HYBRID / output_filename
            output_path.parent.mkdir(parents=True, exist_ok=True)
            result_img.save(output_path, "JPEG", quality=95)
            
            logging.info(f"Hybrid Render Mock 성공: {output_path}")
            return output_path

        except Exception as e:
            logging.error(f"Hybrid Render Mock 실패 ({item_id}): {e}")
            raise

    def _get_standard_result(self, item_id):
        # output/standard 폴더에서 해당 품번의 파일을 찾음
        standard_dir = Config.OUTPUT_STANDARD
        if not standard_dir.exists():
            return None
        
        for file in standard_dir.glob(f"{item_id}*.jpg"):
            return Image.open(file).convert("RGB")
        return None