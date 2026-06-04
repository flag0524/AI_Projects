# AI 마네킹 핏 시스템

마네킹 + 의류 이미지를 업로드하면 사이즈·체형을 반영해 가상 피팅 결과를 생성합니다.

## 빠른 시작 (로컬 GPU)

### 필수 환경

- CUDA 지원 GPU (VRAM 12GB 이상 권장)
- Docker + NVIDIA Container Toolkit
- 또는: Python 3.10+, Node 20+

---

### Docker로 실행

```bash
# 저장소 클론 후 프로젝트 폴더로 이동
docker compose up --build
```

브라우저에서 http://localhost:3000 접속

---

### 클라우드 GPU — 사진급 Tier 1 (IDM-VTON)

CPU/저VRAM(예: 2GB) 환경에서는 디퓨전 피팅이 불가능하다. 옷이 체형을 감싸고 주름·그림자까지 생성되는 **사진급 결과**는 GPU VRAM 12GB+ 에서 **Tier 1(IDM-VTON)** 으로만 가능하다.

RunPod/Vast/자체 GPU 서버에서:

```bash
bash deploy/cloud-gpu/setup_gpu.sh   # 의존성+모델+서버 1클릭
```

상세 가이드: [`deploy/cloud-gpu/README.md`](deploy/cloud-gpu/README.md)

---

### 직접 실행 (Docker 없이)

**백엔드**

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

**프론트엔드** (별도 터미널)

```bash
cd frontend
npm install
npm run dev
```

브라우저에서 http://localhost:3000 접속

---

### GPU 없이 테스트 (CPU/Stub 모드)

`.env` 파일을 `backend/` 안에 만들고 아래 내용 입력:

```
DEVICE=cpu
```

GPU가 없으면 IDM-VTON 로드에 실패하고 자동으로 Stub 모드로 동작합니다.
Stub 모드에서는 의류를 마네킹 위에 반투명 합성한 테스트 이미지를 반환합니다.

---

## 파일 구조

```
├── backend/
│   ├── main.py               # FastAPI 앱 진입점
│   ├── config.py             # 환경 설정
│   ├── schemas.py            # 요청/응답 모델
│   ├── pipeline/
│   │   ├── preprocess.py     # 이미지 전처리 (EXIF, 리사이즈, 배경 제거)
│   │   ├── pose_estimation.py# 포즈·체형 추정 (DWPose / MediaPipe)
│   │   ├── garment_parsing.py# 의류 마스킹·키포인트
│   │   ├── fit_engine.py     # 사이즈-체형 정합 (여유율 계산)
│   │   └── tryon_model.py    # IDM-VTON 래퍼
│   └── storage/              # 업로드·결과 이미지 저장
│
├── frontend/
│   └── src/
│       ├── App.jsx           # 메인 화면
│       ├── hooks/useTryOn.js # 생성 요청·폴링 로직
│       └── components/
│           ├── ImageDropZone.jsx  # 드래그&드롭 업로드
│           ├── SizeInputPanel.jsx # 카테고리별 치수 입력
│           ├── FitReportCard.jsx  # 핏 분석 결과 카드
│           └── ResultGrid.jsx     # 결과 이미지 그리드
│
└── docker-compose.yml
```

---

## API 요약

| 메서드 | 경로 | 설명 |
|--------|------|------|
| POST | `/api/v1/tryon` | 피팅 Job 생성 (multipart) |
| GET  | `/api/v1/tryon/{job_id}` | Job 상태·결과 조회 |
| POST | `/api/v1/tryon/layered` | 상의+하의 레이어링 (M1 예정) |
| GET  | `/health` | 서버 상태 확인 |

---

## 주요 파라미터

**POST /api/v1/tryon** 폼 필드:

| 필드 | 필수 | 설명 |
|------|------|------|
| `mannequin_image` | ✅ | 마네킹 이미지 파일 |
| `garment_image` | ✅ | 의류 이미지 파일 |
| `category` | ✅ | `top` / `bottom` / `dress` |
| `garment_size` | 선택 | 치수 JSON (cm) |
| `fit_mode` | 선택 | `auto` / `tight` / `regular` / `loose` |
| `num_candidates` | 선택 | 생성 후보 수 (1~4, 기본 1) |
| `remove_background` | 선택 | 의류 배경 자동 제거 여부 |

**garment_size JSON 예시:**
```json
{
  "unit": "cm",
  "total_length": 65,
  "chest": 96,
  "shoulder": 42,
  "sleeve": 60
}
```

---

## 파인튜닝

> **주의:** 모든 명령은 프로젝트 루트(`AI를 이용한 마네킹 핏 시스템\`)에서 실행해야 합니다.

```cmd
cd "D:\fashon_tryon\AI를 이용한 마네킹 핏 시스템"

:: 1. 데이터셋 준비 (raw 폴더에 {id}_mannequin.jpg / {id}_garment.jpg 넣은 후)
python finetune/scripts/prepare_dataset.py --raw_dir finetune/dataset/raw

:: 2. 학습
accelerate launch finetune/scripts/train_lora.py --config finetune/configs/lora_config.yaml

:: 3. 평가
python finetune/scripts/evaluate.py --lora_dir finetune/output/lora_weights --data_dir finetune/dataset/val
```

raw 데이터 형식은 `finetune/dataset/README.md` 참고.

---

## 개발 로드맵

| 단계 | 상태 | 내용 |
|------|------|------|
| M0 PoC | ✅ 완료 | 단일 카테고리, IDM-VTON, 기본 핏 엔진 |
| M1 MVP | ✅ 완료 | 레이어링, 포즈 자동화, Celery 큐, 파인튜닝 설정 |
| M2 | 예정 | TensorRT 최적화, 배치 처리, 업스케일 |
| M3 | 예정 | 오토스케일, 히스토리, 배경 교체 |
