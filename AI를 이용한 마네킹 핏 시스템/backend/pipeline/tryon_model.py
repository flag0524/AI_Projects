"""..."""
from __future__ import annotations
from pathlib import Path
from typing import Optional

import numpy as np
import torch
from PIL import Image
from loguru import logger

from config import settings
from pipeline.fit_engine import FitParams


class TryOnModel:
    _instance: Optional["TryOnModel"] = None
    _pipe = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    # ─────────────────────────────────────────────
    # 모델 로드
    # ─────────────────────────────────────────────

    def _load(self):
        if self._pipe is not None:
            return
        logger.info(f"IDM-VTON 로딩 중... device={settings.device}")
        try:
            self._pipe = self._load_pipeline()
            logger.info("IDM-VTON 로드 완료")
        except Exception as e:
            logger.warning(f"IDM-VTON 로드 실패({e}) — stub 모드로 동작합니다")
            self._pipe = "stub"

    def _load_pipeline(self):
        from diffusers import AutoPipelineForInpainting
        from huggingface_hub import snapshot_download

        model_path = settings.model_cache_dir / "IDM-VTON"
        if not model_path.exists():
            logger.info("모델 다운로드 중 (첫 실행 시 시간 소요)...")
            snapshot_download(
                repo_id=settings.idm_vton_model_id,
                local_dir=str(model_path),
            )

        pipe = AutoPipelineForInpainting.from_pretrained(
            str(model_path),
            torch_dtype=torch.float16 if settings.device == "cuda" else torch.float32,
            custom_pipeline="pipeline_stable_diffusion_xl_tryon",
            trust_remote_code=True,
        )

        # LoRA 가중치 자동 로드
        lora_path = Path("finetune/output/lora_weights")
        if lora_path.exists():
            logger.info(f"LoRA 가중치 로드: {lora_path}")
            try:
                from peft import PeftModel
                pipe.unet = PeftModel.from_pretrained(pipe.unet, str(lora_path))
                logger.info("LoRA 적용 완료")
            except Exception as e:
                logger.warning(f"LoRA 로드 실패 — 기본 모델 사용: {e}")

        pipe = pipe.to(settings.device)
        if settings.device == "cuda":
            pipe.enable_model_cpu_offload()
            try:
                pipe.enable_xformers_memory_efficient_attention()
                logger.info("xformers 메모리 최적화 활성화")
            except Exception:
                pass

        return pipe

    # ─────────────────────────────────────────────
    # 추론
    # ─────────────────────────────────────────────

    def infer(
        self,
        mannequin_img: Image.Image,
        garment_img: Image.Image,
        pose_data: dict,
        garment_data: dict,
        fit_params: FitParams,
        seed: int = 42,
        num_steps: int = 30,
        guidance_scale: float = 2.0,
        agnostic_map: Optional[Image.Image] = None,   # M1: body_parsing에서 생성
    ) -> Image.Image:
        """..."""
        self._load()

        if self._pipe == "stub":
            return self._lightweight_pipeline(mannequin_img, garment_img, pose_data, fit_params)

        generator = torch.Generator(device=settings.device).manual_seed(seed)

        # agnostic mask: L 모드 (흰=교체, 검=유지)
        if agnostic_map is not None:
            # RGB agnostic -> 회색 영역(128)을 마스크로 변환
            ag_arr = np.array(agnostic_map.convert("L"))
            mask_arr = ((ag_arr > 100) & (ag_arr < 160)).astype(np.uint8) * 255
            inpaint_mask = Image.fromarray(mask_arr, mode="L")
            person_input = agnostic_map
        else:
            inpaint_mask = self._make_agnostic_mask(
                mannequin_img, pose_data, garment_data["category"]
            )
            person_input = mannequin_img

        # 핏 파라미터 기반 동적 프롬프트 및 가이던스 최적화
        fit_desc = "tight-fitting" if fit_params.ease_ratio < 0.05 else \
                   "regular fit" if fit_params.ease_ratio < 0.15 else "oversized loose fit"
        
        # 여유율이 클수록 guidance를 낮춰 자연스러운 주름(drape) 유도
        adjusted_guidance = max(1.5, guidance_scale - fit_params.ease_ratio * 0.5)

        result = self._pipe(
            prompt=(
                f"a mannequin wearing the {fit_desc} garment, "
                f"high quality fabric drape, professional studio lighting, "
                "white background, highly detailed texture, 8k uhd"
            ),
            negative_prompt=(
                "deformed, blurry, bad anatomy, extra limbs, low quality, "
                "watermark, text, duplicate"
            ),
            image=person_input,
            mask_image=inpaint_mask,
            garment_image=garment_img,
            pose_image=pose_data["pose_map"],
            num_inference_steps=num_steps,
            guidance_scale=adjusted_guidance,
            generator=generator,
            width=768,
            height=1024,
        ).images[0]

        return result

    # ─────────────────────────────────────────────
    # 내부 헬퍼
    # ─────────────────────────────────────────────

    @staticmethod
    def _make_agnostic_mask(
        mannequin: Image.Image,
        pose_data: dict,
        category: str,
    ) -> Image.Image:
        """..."""
        w, h = mannequin.size
        kp = pose_data["keypoints"]
        mask = np.zeros((h, w), dtype=np.uint8)

        if category in ("top", "dress"):
            top_y = int(kp[1, 1]) if kp[1, 2] > 0.3 else int(h * 0.12)
            bot_y = int((kp[8, 1] + kp[11, 1]) / 2) if kp[8, 2] > 0.3 else int(h * 0.55)
            lx = int(kp[5, 0]) if kp[5, 2] > 0.3 else int(w * 0.35)
            rx = int(kp[2, 0]) if kp[2, 2] > 0.3 else int(w * 0.65)
            pad = int(w * 0.04)
            mask[top_y:bot_y, max(0, lx - pad):min(w, rx + pad)] = 255

        if category in ("bottom", "dress"):
            top_y = int((kp[8, 1] + kp[11, 1]) / 2) if kp[8, 2] > 0.3 else int(h * 0.52)
            bot_y = int((kp[10, 1] + kp[13, 1]) / 2) if kp[10, 2] > 0.3 else int(h * 0.90)
            lx = int(kp[11, 0]) if kp[11, 2] > 0.3 else int(w * 0.38)
            rx = int(kp[8, 0]) if kp[8, 2] > 0.3 else int(w * 0.62)
            pad = int(w * 0.04)
            mask[top_y:bot_y, max(0, lx - pad):min(w, rx + pad)] = 255

        return Image.fromarray(mask, mode="L")

    def _lightweight_pipeline(self, mannequin: Image.Image, garment: Image.Image, pose_data: dict, fit_params: FitParams) -> Image.Image:
        """
        RECONSTRUCTION_REPORT 기반의 경량 재구축 파이프라인
        """
        logger.info("🚀 보고서 기반 경량 파이프라인 가동")
        from pipeline.postprocess import PostProcessor
        
        # 1. Garment Normalization & Pose-based Warping
        res_w, res_h = mannequin.size
        garment = garment.convert("RGBA")
        
        # [추가] 의류 이미지 방향 보정 (가로가 더 길면 90도 회전)
        if garment.width > garment.height:
            garment = garment.rotate(90, expand=True)
            logger.info("의류 이미지 자동 회전 적용 (가로 $\rightarrow$ 세로)")

        kp = pose_data["keypoints"]
        
        # 어깨 너비 및 위치 계산
        shoulder_w = abs(kp[2][0] - kp[5][0]) if kp[2][2] > 0.3 and kp[5][2] > 0.3 else res_w * 0.4
        
        # FitEngine의 warping_strength 반영 (옷의 크기 조절)
        target_w = int(shoulder_w * (1.1 + fit_params.ease_ratio)) 
        aspect_ratio = garment.height / garment.width
        target_h = int(target_w * aspect_ratio)
        
        # 길이 비율(length_ratio) 반영
        target_h = int(res_h * fit_params.length_ratio)
        target_w = int(target_h / aspect_ratio)
        
        garment = garment.resize((target_w, target_h), Image.LANCZOS)
        
        center_x = (kp[2][0] + kp[5][0]) // 2 if kp[2][2] > 0.3 and kp[5][2] > 0.3 else res_w // 2
        center_y = (kp[2][1] + kp[5][1]) // 2 if kp[2][2] > 0.3 and kp[5][2] > 0.3 else res_h // 3
        
        offset_x = center_x - target_w // 2
        offset_y = center_y - target_h // 10
        
        # 2. 입체적 합성 및 마스킹
        result_rgba = mannequin.copy().convert("RGBA")
        temp_canvas = Image.new("RGBA", (res_w, res_h), (0, 0, 0, 0))
        
        # 의류 마스크 생성 및 부드러운 처리
        mask = garment.split()[3]
        mask = mask.filter(ImageFilter.GaussianBlur(radius=3))
        garment.putalpha(mask)
        
        # [추가] 입체감을 위한 가상 그림자 레이어 생성
        shadow_garment = garment.copy()
        # 밝기를 낮춰 그림자 효과 생성
        from PIL import ImageEnhance
        enhancer = ImageEnhance.Brightness(shadow_garment)
        shadow_garment = enhancer.enhance(0.7) 
        
        # 그림자를 약간 우측 하단으로 밀어 배치하여 입체감 부여
        temp_canvas.paste(shadow_garment, (offset_x + 5, offset_y + 5))
        temp_canvas.paste(garment, (offset_x, offset_y))
        
        combined = Image.alpha_composite(result_rgba, temp_canvas).convert("RGB")
        
        # 3. Post-processing (보고서 핵심 기능)
        pp = PostProcessor()
        final_result = pp.apply(combined, mask=mask)
        
        return final_result
