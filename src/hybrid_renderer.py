import logging
import json
from pathlib import Path
from PIL import Image
from src.config import Config

class HybridRenderer:
    """
    Standard Engine의 정확성에 AI의 설득력을 더하는 하이브리드 렌더러
    """
    def __init__(self, device="cuda"):
        self.muse_profiles = self._load_profiles()
        self.device = device
        self.pipeline = self._init_ai_pipeline()

    def _init_ai_pipeline(self):
        """
        Stable Diffusion + ControlNet 파이프라인 초기화
        (운영 효율을 위해 Singleton 형태로 모델을 한 번만 로드)
        """
        import torch
        from diffusers import StableDiffusionControlNetPipeline, ControlNetModel, UniPCMultistepScheduler

        logging.info("Hybrid AI Pipeline 초기화 중... (모델 로드)")
        
        # 1. ControlNet 모델 로드 (Canny Edge 기반 형태 고정)
        controlnet = ControlNetModel.from_pretrained(
            "lllyasviel/sd-controlnet-canny", torch_dtype=torch.float16
        )
        
        # 2. 메인 파이프라인 로드
        pipe = StableDiffusionControlNetPipeline.from_pretrained(
            "runwayml/stable-diffusion-v1-5", 
            controlnet=controlnet, 
            torch_dtype=torch.float16
        ).to(self.device)
        
        # 3. 스케줄러 최적화 (속도 및 품질)
        pipe.scheduler = UniPCMultistepScheduler.from_config(pipe.scheduler.config)
        
        logging.info("AI Pipeline 로드 완료.")
        return pipe

    def _load_profiles(self):
        """전체 프로필 JSON을 로드하여 반환"""
        with open(Config.SPECS_DIR / "muse_profiles.json", 'r', encoding='utf-8') as f:
            return json.load(f)

    def render_hybrid(self, item_id: str, muse_id: str, preset: str = "muse_lookbook"):
        """
        [Standard 결과물] -> [AI 무드 주입(Mock)] -> [최종 제안 컷]
        현재 환경의 CUDA 이슈 해결 전까지 Mock-up 모드로 동작하여 파이프라인 연결 확인
        """
        import numpy as np
        import cv2
        from PIL import Image, ImageEnhance

        try:
            logging.info(f"Hybrid Render (Mock Mode) 시작: {item_id} with {muse_id}")
            
            # 1. Standard Engine 결과물 로드
            standard_img = self._get_standard_result(item_id)
            if standard_img is None:
                # 테스트를 위해 임시 이미지 생성 (결과 파일 생성 확인용)
                logging.warning(f"Standard 결과물이 없어 임시 이미지를 생성합니다: {item_id}")
                standard_img = Image.new('RGB', (512, 768), color=(200, 200, 200))

            # 2. 뮤즈 프로필 로드
            muse = self.muse_profiles.get(muse_id, {"name": "Default Muse", "visual_prompts": "chic look"})

            # 3. AI 효과 모사 (Mocking)
            # 실제 AI 추론 대신, 이미지의 색조와 대비를 조정하여 '무드'가 변한 것처럼 연출합니다.
            img_array = np.array(standard_img)
            
            # 뮤즈에 따른 색조 조정 (예: Urban Chic는 쿨톤, Natural은 웜톤)
            if "Urban" in muse.get("name", ""):
                img_array = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
                img_array = cv2.cvtColor(img_array, cv2.COLOR_BGR2LAB)
                img_array[:, :, 0] = np.clip(img_array[:, :, 0] - 10, 0, 255) # 약간 어둡게
                img_array = cv2.cvtColor(img_array, cv2.COLOR_LAB2RGB)
            
            result_img = Image.fromarray(img_array.astype('uint8'))
            
            # 대비 및 선명도 강화 (AI 렌더링 느낌 모사)
            enhancer = ImageEnhance.Contrast(result_img)
            result_img = enhancer.enhance(1.2)
            
            # 4. 최종 결과 저장
            output_filename = f"{item_id}_{muse_id}_{preset}.jpg"
            output_path = Config.OUTPUT_HYBRID / output_filename
            
            # 폴더가 없으면 생성
            output_path.parent.mkdir(parents=True, exist_ok=True)
            result_img.save(output_path, "JPEG", quality=95)
            
            logging.info(f"Hybrid Render Mock 성공: {output_path}")
            return output_path

        except Exception as e:
            logging.error(f"Hybrid Render Mock 실패 ({item_id}): {e}")
            raise

    def _get_standard_result(self, item_id):
        """Standard Engine의 결과물을 찾아 반환하는 헬퍼 메서드"""
        # output/standard 폴더에서 해당 품번의 최신 파일을 탐색
        pass