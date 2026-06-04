"""
IDM-VTON LoRA 파인튜닝 학습 스크립트.

실행:
  accelerate launch finetune/scripts/train_lora.py \
    --config finetune/configs/lora_config.yaml

필수 패키지:
  pip install peft accelerate diffusers transformers omegaconf tensorboard

학습 데이터: finetune/scripts/prepare_dataset.py 로 준비
"""
from __future__ import annotations
import os
import json
import random
import math
from pathlib import Path

import numpy as np
import torch
import yaml
from PIL import Image
from torch.utils.data import Dataset, DataLoader
from loguru import logger

# 학습 시작 전 GPU 메모리 확인
def check_gpu():
    if not torch.cuda.is_available():
        logger.warning("CUDA GPU가 없습니다. CPU 학습은 매우 느립니다.")
        return
    for i in range(torch.cuda.device_count()):
        props = torch.cuda.get_device_properties(i)
        vram = props.total_memory / 1024**3
        logger.info(f"GPU {i}: {props.name} ({vram:.1f} GB VRAM)")
        if vram < 10:
            logger.warning(f"VRAM이 {vram:.1f}GB로 부족할 수 있습니다. 최소 12GB 권장.")


# ─────────────────────────────────────────────
# 데이터셋
# ─────────────────────────────────────────────

class TryOnDataset(Dataset):
    """
    IDM-VTON 학습용 데이터셋.

    각 샘플:
      - mannequin_img  : 마네킹 이미지 (person-agnostic)
      - garment_img    : 의류 이미지
      - result_img     : 정답 이미지 (GT)
      - pose_map       : 포즈 스켈레톤 이미지
      - agnostic_mask  : 교체 영역 마스크
    """

    def __init__(self, data_dir: str, image_size: tuple, augment: bool = True):
        self.data_dir   = Path(data_dir)
        self.image_size = image_size   # (W, H)
        self.augment    = augment
        self.ids = sorted(
            p.stem for p in (self.data_dir / "mannequin").glob("*.jpg")
        )
        logger.info(f"데이터셋 로드: {len(self.ids)}개 ({data_dir})")

    def __len__(self):
        return len(self.ids)

    def _load(self, path: Path) -> Image.Image:
        return Image.open(path).convert("RGB").resize(self.image_size, Image.LANCZOS)

    def _load_mask(self, path: Path) -> Image.Image:
        return Image.open(path).convert("L").resize(self.image_size, Image.NEAREST)

    def _augment(self, imgs: list[Image.Image]) -> list[Image.Image]:
        """색상 지터 증강 (수평 플립 제외 — 의류 비대칭 보존)."""
        from torchvision import transforms
        jitter = transforms.ColorJitter(brightness=0.1, contrast=0.1, saturation=0.05)
        return [jitter(img) for img in imgs]

    def __getitem__(self, idx: int) -> dict:
        pid = self.ids[idx]
        W, H = self.image_size

        mannequin = self._load(self.data_dir / "mannequin" / f"{pid}.jpg")
        garment   = self._load(self.data_dir / "garment"   / f"{pid}.jpg")
        result    = self._load(self.data_dir / "result"    / f"{pid}.jpg")

        pose_path = self.data_dir / "masks" / f"{pid}_pose.png"
        pose_map  = self._load(pose_path) if pose_path.exists() else Image.new("RGB", (W, H))

        mask_path = self.data_dir / "masks" / f"{pid}_upper.png"
        agnostic_mask = self._load_mask(mask_path) if mask_path.exists() else Image.new("L", (W, H), 255)

        # person-agnostic: 의류 영역 회색으로 채우기
        agnostic_img = mannequin.copy()
        mask_np = np.array(agnostic_mask) > 127
        agnostic_arr = np.array(agnostic_img)
        agnostic_arr[mask_np] = [128, 128, 128]
        agnostic_img = Image.fromarray(agnostic_arr)

        # 증강
        if self.augment:
            mannequin, garment, result, agnostic_img = self._augment(
                [mannequin, garment, result, agnostic_img]
            )

        # Tensor 변환 [-1, 1]
        def to_tensor(img):
            arr = np.array(img).astype(np.float32) / 127.5 - 1.0
            return torch.from_numpy(arr).permute(2, 0, 1)

        def mask_to_tensor(img):
            arr = np.array(img).astype(np.float32) / 255.0
            return torch.from_numpy(arr).unsqueeze(0)

        return {
            "mannequin":     to_tensor(mannequin),
            "garment":       to_tensor(garment),
            "result":        to_tensor(result),
            "pose_map":      to_tensor(pose_map),
            "agnostic":      to_tensor(agnostic_img),
            "agnostic_mask": mask_to_tensor(agnostic_mask),
            "id":            pid,
        }


# ─────────────────────────────────────────────
# 학습 루프
# ─────────────────────────────────────────────

def train(config_path: str):
    import argparse
    from accelerate import Accelerator
    from diffusers import AutoencoderKL, UNet2DConditionModel, DDPMScheduler
    from diffusers.optimization import get_scheduler
    from peft import LoraConfig, get_peft_model
    from transformers import CLIPTextModel, CLIPTokenizer

    with open(config_path) as f:
        cfg = yaml.safe_load(f)

    tc   = cfg["training"]
    lc   = cfg["lora"]
    dc   = cfg["data"]
    loss_weights = cfg.get("loss", {})

    check_gpu()

    accelerator = Accelerator(
        mixed_precision=tc["mixed_precision"],
        gradient_accumulation_steps=tc["gradient_accumulation_steps"],
        log_with=cfg["logging"]["report_to"],
        project_dir=cfg["logging"]["log_dir"],
    )

    logger.info(f"Accelerator: {accelerator.device}")

    # ── 모델 로드 ────────────────────────────────────────────────────────
    model_id = cfg["model"]["base_model"]
    tokenizer   = CLIPTokenizer.from_pretrained(model_id, subfolder="tokenizer")
    text_encoder = CLIPTextModel.from_pretrained(model_id, subfolder="text_encoder")
    vae          = AutoencoderKL.from_pretrained(model_id, subfolder="vae")
    unet         = UNet2DConditionModel.from_pretrained(model_id, subfolder="unet")
    noise_sched  = DDPMScheduler.from_pretrained(model_id, subfolder="scheduler")

    # VAE, text_encoder는 동결
    vae.requires_grad_(False)
    text_encoder.requires_grad_(False)

    # ── LoRA 적용 ────────────────────────────────────────────────────────
    lora_cfg = LoraConfig(
        r=lc["rank"],
        lora_alpha=lc["alpha"],
        target_modules=lc["target_modules"],
        lora_dropout=lc["dropout"],
        bias="none",
    )
    unet = get_peft_model(unet, lora_cfg)
    unet.print_trainable_parameters()

    if tc.get("gradient_checkpointing"):
        unet.enable_gradient_checkpointing()

    # ── 데이터 ──────────────────────────────────────────────────────────
    W, H = dc["image_size"]
    train_ds = TryOnDataset(
        Path(dc["dataset_dir"]) / "train",
        image_size=(W, H),
        augment=True,
    )
    val_ds = TryOnDataset(
        Path(dc["dataset_dir"]) / "val",
        image_size=(W, H),
        augment=False,
    )
    train_dl = DataLoader(train_ds, batch_size=tc["batch_size"], shuffle=True,  num_workers=2, pin_memory=True)
    val_dl   = DataLoader(val_ds,   batch_size=1,                shuffle=False, num_workers=1)

    # ── 옵티마이저 ───────────────────────────────────────────────────────
    optimizer = torch.optim.AdamW(
        filter(lambda p: p.requires_grad, unet.parameters()),
        lr=tc["learning_rate"],
        betas=(0.9, 0.999),
        weight_decay=1e-2,
    )
    num_update_steps = math.ceil(len(train_dl) / tc["gradient_accumulation_steps"]) * tc["num_epochs"]
    lr_scheduler = get_scheduler(
        tc["lr_scheduler"],
        optimizer=optimizer,
        num_warmup_steps=tc["lr_warmup_steps"],
        num_training_steps=num_update_steps,
    )

    # ── Accelerator prepare ──────────────────────────────────────────────
    unet, optimizer, train_dl, lr_scheduler = accelerator.prepare(
        unet, optimizer, train_dl, lr_scheduler
    )
    vae          = vae.to(accelerator.device)
    text_encoder = text_encoder.to(accelerator.device)

    # 고정 프롬프트 임베딩 (IDM-VTON 학습 방식)
    prompt = "a photo of a mannequin wearing the garment"
    text_inputs = tokenizer(prompt, padding="max_length", max_length=77,
                            truncation=True, return_tensors="pt").to(accelerator.device)
    with torch.no_grad():
        text_embeds = text_encoder(**text_inputs).last_hidden_state

    # ── 학습 ─────────────────────────────────────────────────────────────
    output_dir = Path(tc["output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)

    global_step = 0
    logger.info(f"학습 시작: {tc['num_epochs']} epochs, {num_update_steps} steps")

    for epoch in range(tc["num_epochs"]):
        unet.train()
        epoch_loss = 0.0

        for batch in train_dl:
            with accelerator.accumulate(unet):
                # VAE 인코딩
                with torch.no_grad():
                    result_latents  = vae.encode(batch["result"].to(vae.dtype)).latent_dist.sample() * vae.config.scaling_factor
                    garment_latents = vae.encode(batch["garment"].to(vae.dtype)).latent_dist.sample() * vae.config.scaling_factor
                    agnostic_latents = vae.encode(batch["agnostic"].to(vae.dtype)).latent_dist.sample() * vae.config.scaling_factor

                # 노이즈 추가
                noise = torch.randn_like(result_latents)
                bsz = result_latents.shape[0]
                timesteps = torch.randint(0, noise_sched.config.num_train_timesteps,
                                          (bsz,), device=result_latents.device).long()
                noisy_latents = noise_sched.add_noise(result_latents, noise, timesteps)

                # UNet 입력: noisy_latents + agnostic + mask + garment 채널 concat
                mask_latent = torch.nn.functional.interpolate(
                    batch["agnostic_mask"].to(result_latents.device),
                    size=noisy_latents.shape[-2:],
                )
                model_input = torch.cat(
                    [noisy_latents, mask_latent, agnostic_latents, garment_latents], dim=1
                )

                # 텍스트 임베딩 확장
                te = text_embeds.expand(bsz, -1, -1)

                # 예측
                noise_pred = unet(model_input, timesteps, encoder_hidden_states=te).sample

                # 손실 (reconstruction)
                loss = torch.nn.functional.mse_loss(noise_pred, noise, reduction="mean")

                # 의류 일관성 보조 손실 (가중치 0.3)
                if loss_weights.get("garment_consistency", 0) > 0:
                    with torch.no_grad():
                        pred_denoised = (noisy_latents - noise_sched.alphas_cumprod[timesteps].sqrt().view(-1,1,1,1) * noise_pred) \
                                        / (1 - noise_sched.alphas_cumprod[timesteps]).sqrt().view(-1,1,1,1)
                    consistency = torch.nn.functional.mse_loss(
                        pred_denoised[:, :4], garment_latents, reduction="mean"
                    )
                    loss = loss + loss_weights["garment_consistency"] * consistency

                accelerator.backward(loss)
                if accelerator.sync_gradients:
                    accelerator.clip_grad_norm_(unet.parameters(), tc["max_grad_norm"])
                optimizer.step()
                lr_scheduler.step()
                optimizer.zero_grad()

            epoch_loss += loss.item()
            global_step += 1

            if global_step % cfg["logging"]["log_steps"] == 0:
                avg = epoch_loss / max(global_step, 1)
                logger.info(f"step={global_step} loss={loss.item():.4f} avg={avg:.4f}")

            # 체크포인트 저장
            if global_step % tc["save_steps"] == 0 and accelerator.is_main_process:
                ckpt_dir = output_dir / f"checkpoint-{global_step}"
                accelerator.save_state(str(ckpt_dir))
                logger.info(f"체크포인트 저장: {ckpt_dir}")

        logger.info(f"Epoch {epoch+1}/{tc['num_epochs']} 완료")

    # ── 최종 LoRA 가중치 저장 ────────────────────────────────────────────
    if accelerator.is_main_process:
        unwrapped = accelerator.unwrap_model(unet)
        unwrapped.save_pretrained(str(output_dir / "lora_weights"))
        logger.info(f"LoRA 가중치 저장: {output_dir / 'lora_weights'}")

    accelerator.end_training()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="finetune/configs/lora_config.yaml")
    args = parser.parse_args()
    train(args.config)
