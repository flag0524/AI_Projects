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
        [Standard 결과물] -> [ControlNet 형태 고정] -> [Muse 무드 주입] -> [최종 제안 컷]
        """
        import torch
        import numpy as np
        import cv2
        from PIL import Image

        try:
            logging.info(f"Hybrid Render 시작: {item_id} with {muse_id}")
            
            # 1. Standard Engine 결과물 로드 (정확성의 기반)
            standard_img = self._get_standard_result(item_id)
            if standard_img is None:
                raise FileNotFoundError(f"Standard Engine 결과물이 없습니다: {item_id}")

            # 2. 뮤즈 프로필 로드 (설득력의 기반)
            muse = self.muse_profiles.get(muse_id)
            if not muse:
                raise ValueError(f"존재하지 않는 뮤즈 ID입니다: {muse_id}")

            # 3. ControlNet을 위한 Canny Edge 추출 (상품 실루엣 고정)
            # 원본의 형태를 100% 유지하기 위해 엣지 맵을 생성합니다.
            img_array = np.array(standard_img)
            canny_img = cv2.Canny(img_array, 100, 200)
            canny_img = Image.fromarray(canny_img).convert("RGB")

            # 4. 프롬프트 조합 (뮤즈 개별 프롬프트 + 글로벌 브랜드 무드)
            prompt = f"{muse['visual_prompts']}, {self.global_mood}"
            negative_prompt = muse.get('negative_prompts', "low quality, blurry, distorted")

            # 5. AI 추론 실행 (Inference)
            # ControlNet이 Canny 맵을 가이드로 사용하여 상품 형태를 유지한 채 뮤즈를 생성합니다.
            result_img = self.pipeline(
                prompt=prompt,
                negative_prompt=negative_prompt,
                image=canny_img,
                num_inference_steps=30,
                guidance_scale=7.5
            ).images[0]

            # 6. 최종 결과 저장
            output_filename = f"{item_id}_{muse_id}_{preset}.jpg"
            output_path = Config.OUTPUT_HYBRID / output_filename
            result_img.save(output_path, "JPEG", quality=95)
            
            logging.info(f"Hybrid Render 성공: {output_path}")
            return output_path

        except Exception as e:
            logging.error(f"Hybrid Render 실패 ({item_id}): {e}")
            raise

    def _get_standard_result(self, item_id):
        """Standard Engine의 결과물을 찾아 반환하는 헬퍼 메서드"""
        # output/standard 폴더에서 해당 품번의 최신 파일을 탐색
        pass