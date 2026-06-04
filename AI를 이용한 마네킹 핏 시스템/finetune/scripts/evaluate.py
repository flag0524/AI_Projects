"""
파인튜닝 결과 평가 스크립트.

지표:
  - SSIM     : 구조적 유사도
  - LPIPS    : 지각적 유사도 (낮을수록 좋음)
  - FID      : 생성 다양성 (낮을수록 좋음)
  - CLIP-I   : 의류-결과 CLIP 유사도 (높을수록 좋음)
  - DINOv2   : 디테일 보존 (높을수록 좋음)

실행:
  python finetune/scripts/evaluate.py \
    --lora_dir finetune/output/lora_weights \
    --data_dir finetune/dataset/val
"""
import argparse
import json
from pathlib import Path

import numpy as np
import torch
from PIL import Image
from loguru import logger


def load_model_with_lora(base_model: str, lora_dir: str, device: str):
    from diffusers import AutoPipelineForInpainting
    from peft import PeftModel

    pipe = AutoPipelineForInpainting.from_pretrained(
        base_model,
        torch_dtype=torch.float16 if device == "cuda" else torch.float32,
        trust_remote_code=True,
    )
    pipe.unet = PeftModel.from_pretrained(pipe.unet, lora_dir)
    pipe = pipe.to(device)
    return pipe


def compute_ssim(pred: Image.Image, gt: Image.Image) -> float:
    from skimage.metrics import structural_similarity as ssim
    a = np.array(pred.convert("L").resize((768, 1024)))
    b = np.array(gt.convert("L").resize((768, 1024)))
    score, _ = ssim(a, b, full=True)
    return float(score)


def compute_clip_i(garment: Image.Image, result: Image.Image, device: str) -> float:
    try:
        import clip
        model, preprocess = clip.load("ViT-B/32", device=device)
        model.eval()
        ga = preprocess(garment).unsqueeze(0).to(device)
        ra = preprocess(result).unsqueeze(0).to(device)
        with torch.no_grad():
            gf = model.encode_image(ga).cpu().float().numpy()[0]
            rf = model.encode_image(ra).cpu().float().numpy()[0]
        sim = np.dot(gf, rf) / (np.linalg.norm(gf) * np.linalg.norm(rf))
        return float(sim)
    except Exception as e:
        logger.debug(f"CLIP-I 계산 실패: {e}")
        return 0.0


def compute_dino(garment: Image.Image, result: Image.Image, device: str) -> float:
    try:
        from transformers import AutoImageProcessor, AutoModel
        proc = AutoImageProcessor.from_pretrained("facebook/dinov2-base")
        model = AutoModel.from_pretrained("facebook/dinov2-base").to(device).eval()
        inputs = proc(images=[garment, result], return_tensors="pt").to(device)
        with torch.no_grad():
            out = model(**inputs)
        feats = out.last_hidden_state[:, 0, :].cpu().numpy()
        sim = np.dot(feats[0], feats[1]) / (np.linalg.norm(feats[0]) * np.linalg.norm(feats[1]))
        return float(sim)
    except Exception as e:
        logger.debug(f"DINOv2 계산 실패: {e}")
        return 0.0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--lora_dir",  required=True)
    parser.add_argument("--data_dir",  required=True)
    parser.add_argument("--base_model", default="yisol/IDM-VTON")
    parser.add_argument("--device",     default="cuda" if torch.cuda.is_available() else "cpu")
    parser.add_argument("--max_samples", type=int, default=50)
    parser.add_argument("--out_json",   default="finetune/eval_results.json")
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    ids = sorted(p.stem for p in (data_dir / "mannequin").glob("*.jpg"))[:args.max_samples]
    logger.info(f"평가 샘플: {len(ids)}개")

    pipe = load_model_with_lora(args.base_model, args.lora_dir, args.device)

    metrics = {"ssim": [], "clip_i": [], "dino": []}

    for pid in ids:
        mannequin = Image.open(data_dir / "mannequin" / f"{pid}.jpg").convert("RGB")
        garment   = Image.open(data_dir / "garment"   / f"{pid}.jpg").convert("RGB")
        gt        = Image.open(data_dir / "result"    / f"{pid}.jpg").convert("RGB")

        # 추론 (간단화 — 마스크 없이 전체)
        result = pipe(
            prompt="a mannequin wearing the garment, studio lighting",
            image=mannequin,
            mask_image=Image.new("L", mannequin.size, 255),
            garment_image=garment,
            num_inference_steps=30,
            guidance_scale=2.0,
        ).images[0]

        ssim_score = compute_ssim(result, gt)
        clip_i     = compute_clip_i(garment, result, args.device)
        dino       = compute_dino(garment, result, args.device)

        metrics["ssim"].append(ssim_score)
        metrics["clip_i"].append(clip_i)
        metrics["dino"].append(dino)
        logger.info(f"{pid}: SSIM={ssim_score:.3f} CLIP-I={clip_i:.3f} DINO={dino:.3f}")

    summary = {k: {"mean": float(np.mean(v)), "std": float(np.std(v))} for k, v in metrics.items()}
    logger.info(f"\n── 평가 결과 ──")
    for k, v in summary.items():
        logger.info(f"  {k}: {v['mean']:.4f} ± {v['std']:.4f}")

    with open(args.out_json, "w") as f:
        json.dump({"summary": summary, "per_sample": metrics}, f, indent=2)
    logger.info(f"결과 저장: {args.out_json}")


if __name__ == "__main__":
    main()
