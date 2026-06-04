# 파인튜닝 데이터셋 구조

## raw 데이터 준비

`finetune/dataset/raw/` 폴더에 아래 형식으로 파일을 넣으세요.

```
raw/
  001_mannequin.jpg       ← 의류를 착용한 마네킹 이미지 (GT)
  001_garment.jpg         ← 동일 의류 단독 이미지 (흰 배경 또는 누끼)
  001_meta.json           ← (선택) 치수 메타데이터
  002_mannequin.jpg
  002_garment.jpg
  ...
```

## meta.json 예시

```json
{
  "category": "top",
  "size": {
    "unit": "cm",
    "total_length": 65,
    "chest": 96,
    "shoulder": 42
  }
}
```

## 권장 데이터 수량

| 목적 | 최소 | 권장 |
|------|------|------|
| 기본 파인튜닝 | 200쌍 | 500쌍 이상 |
| 카테고리별 특화 | 100쌍/카테고리 | 300쌍/카테고리 |

## 데이터 준비 실행

```bash
python finetune/scripts/prepare_dataset.py \
  --raw_dir finetune/dataset/raw \
  --out_dir finetune/dataset \
  --split 0.9
```

## 학습 실행

```bash
# 단일 GPU
accelerate launch finetune/scripts/train_lora.py \
  --config finetune/configs/lora_config.yaml

# 멀티 GPU
accelerate config  # 먼저 설정
accelerate launch --multi_gpu finetune/scripts/train_lora.py \
  --config finetune/configs/lora_config.yaml
```

## 평가

```bash
python finetune/scripts/evaluate.py \
  --lora_dir finetune/output/lora_weights \
  --data_dir finetune/dataset/val
```
