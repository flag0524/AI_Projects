"""
데이터셋 준비 스크립트.

예상 입력 구조:
  finetune/dataset/raw/
    ├── {id}_mannequin.jpg      # 마네킹 이미지 (의류 착용)
    ├── {id}_garment.jpg        # 동일 의류 누끼 이미지
    └── {id}_meta.json          # 치수 메타데이터 (선택)

출력 구조:
  finetune/dataset/train/
    ├── mannequin/{id}.jpg
    ├── garment/{id}.jpg
    ├── result/{id}.jpg         # = mannequin (GT)
    ├── keypoints/{id}.json
    └── masks/{id}_*.png

실행:
  python finetune/scripts/prepare_dataset.py \
    --raw_dir finetune/dataset/raw \
    --out_dir finetune/dataset \
    --split 0.9
"""
import argparse
import json
import random
import shutil
from pathlib import Path

import numpy as np
from PIL import Image
from loguru import logger


def process_pair(mannequin_path: Path, garment_path: Path, out_dir: Path, pair_id: str):
    """마네킹-의류 쌍 전처리 및 어노테이션 생성."""
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend"))

    from pipeline.preprocess import preprocess_images, TARGET_W, TARGET_H
    from pipeline.pose_estimation import estimate_pose
    from pipeline.body_parsing import parse_body
    from pipeline.garment_parsing import parse_garment
    from schemas import Category

    mannequin_img, garment_img = preprocess_images(mannequin_path, garment_path, remove_background=False)

    # 저장
    mannequin_img.save(out_dir / "mannequin" / f"{pair_id}.jpg", quality=95)
    garment_img.save(out_dir / "garment"   / f"{pair_id}.jpg", quality=95)
    mannequin_img.save(out_dir / "result"   / f"{pair_id}.jpg", quality=95)  # GT=원본

    # 키포인트
    pose_data = estimate_pose(mannequin_img)
    kp_dict = {
        "keypoints": pose_data["keypoints"].tolist(),
        "body_measurements": pose_data["body_measurements"],
    }
    with open(out_dir / "keypoints" / f"{pair_id}.json", "w") as f:
        json.dump(kp_dict, f, ensure_ascii=False)

    # 신체 마스크
    body_data = parse_body(mannequin_img)
    for name, mask in body_data["masks"].items():
        mask.save(out_dir / "masks" / f"{pair_id}_{name}.png")

    # pose map 저장
    pose_data["pose_map"].save(out_dir / "masks" / f"{pair_id}_pose.png")

    logger.info(f"  처리 완료: {pair_id}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw_dir",  default="finetune/dataset/raw")
    parser.add_argument("--out_dir",  default="finetune/dataset")
    parser.add_argument("--split",    type=float, default=0.9)
    parser.add_argument("--shuffle",  action="store_true", default=True)
    args = parser.parse_args()

    raw_dir = Path(args.raw_dir)
    out_dir = Path(args.out_dir)

    mannequin_files = sorted(raw_dir.glob("*_mannequin.*"))
    logger.info(f"총 {len(mannequin_files)}개 페어 발견")

    if not mannequin_files:
        logger.error("raw_dir에 {id}_mannequin.jpg 파일이 없습니다.")
        return

    if args.shuffle:
        random.shuffle(mannequin_files)

    n_train = int(len(mannequin_files) * args.split)
    splits = {"train": mannequin_files[:n_train], "val": mannequin_files[n_train:]}

    for split, files in splits.items():
        split_dir = out_dir / split
        for sub in ["mannequin", "garment", "result", "keypoints", "masks"]:
            (split_dir / sub).mkdir(parents=True, exist_ok=True)

        logger.info(f"\n[{split}] {len(files)}개")
        for mf in files:
            pair_id = mf.stem.replace("_mannequin", "")
            gf_candidates = list(raw_dir.glob(f"{pair_id}_garment.*"))
            if not gf_candidates:
                logger.warning(f"  의류 이미지 없음: {pair_id}")
                continue
            try:
                process_pair(mf, gf_candidates[0], split_dir, pair_id)
            except Exception as e:
                logger.error(f"  실패 {pair_id}: {e}")

    logger.info("\n데이터셋 준비 완료")


if __name__ == "__main__":
    main()
