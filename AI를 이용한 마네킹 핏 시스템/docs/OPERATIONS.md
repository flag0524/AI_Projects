# 운영 매뉴얼 — AI 마네킹 핏 시스템

마네킹 이미지와 의류(상의·하의·원피스) 이미지를 업로드하면 사이즈와 체형을 반영해 가상 피팅 결과를 생성하는 시스템의 운영 가이드입니다. 설치·구동·모니터링·장애 대응·백업·파인튜닝까지 일상 운영에 필요한 절차를 다룹니다.

대상 독자: 시스템을 배포하고 운영하는 담당자. 제품 기획·기술 설계 배경은 `docs/PRD.md`와 `docs/TECHNICAL_PRD.md`를, 빠른 시작은 루트 `README.md`를 참고하세요.

---

## 1. 시스템 구성

서비스는 4개의 프로세스로 구성됩니다.

| 구성요소 | 역할 | 포트 | 비고 |
|----------|------|------|------|
| `frontend` | React(Vite) UI, nginx 서빙 | 3000 | 사용자 업로드·결과 표시 |
| `backend` | FastAPI API 서버 | 8000 | Job 생성·상태 조회, 정적 결과 서빙 |
| `worker` | Celery 워커 (GPU 추론) | — | 피팅 파이프라인 실행, `concurrency=1` |
| `redis` | 브로커 + 결과 백엔드 | 6379 | Job 큐·진행상태 저장 |

처리 흐름은 다음과 같습니다. 프론트엔드가 `POST /api/v1/tryon`으로 이미지와 파라미터를 전송하면 백엔드가 파일을 저장하고 Celery 작업을 큐(`tryon`)에 넣습니다. 워커가 작업을 꺼내 전처리 → 포즈·체형 추정 → 의류 파싱 → 핏 엔진(여유율 계산) → IDM-VTON 추론 순으로 실행하고, 진행률을 Redis에 기록합니다. 프론트엔드는 `GET /api/v1/tryon/{job_id}`를 폴링하여 상태와 결과 이미지를 표시합니다.

GPU 작업 충돌을 막기 위해 워커는 의도적으로 동시성 1(`--concurrency=1 --pool=solo`, `worker_prefetch_multiplier=1`)로 고정되어 있습니다. 처리량을 늘리려면 워커를 늘리는 것이 아니라 GPU별로 워커 컨테이너를 분리해야 합니다.

---

## 2. 사전 요구사항

- CUDA 지원 GPU (VRAM 12GB 이상 권장)
- Docker + NVIDIA Container Toolkit (GPU 패스스루)
- Docker 없이 직접 실행 시: Python 3.10+, Node 20+, Redis

GPU가 없는 환경에서는 IDM-VTON 로드에 실패하면 자동으로 Stub 모드로 동작하여 의류를 마네킹 위에 반투명 합성한 테스트 이미지를 반환합니다. 기능 검증·UI 테스트 용도로만 사용하고 실제 결과 품질 평가에는 쓰지 마세요.

---

## 3. 배포 및 기동

### 3.1 Docker Compose (권장)

```bash
cd "D:\fashon_tryon\AI를 이용한 마네킹 핏 시스템"
docker compose up --build -d
```

기동 후 접속 경로:

- UI: http://localhost:3000
- API 상태: http://localhost:8000/health

`docker-compose.yml`에서 `backend`와 `worker` 모두 `DEVICE=cuda`, `REDIS_URL=redis://redis:6379/0`으로 설정되어 있고 NVIDIA GPU 1개를 예약합니다. `backend/storage`와 `finetune` 디렉토리가 볼륨으로 마운트되어 업로드·결과 이미지와 LoRA 가중치가 호스트에 보존됩니다.

### 3.2 직접 실행 (Docker 없이)

Redis를 먼저 띄운 뒤, 백엔드·워커·프론트엔드를 각각 별도 터미널에서 실행합니다.

```bash
# Redis
redis-server

# 백엔드 (터미널 1)
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000

# 워커 (터미널 2)
cd backend
source .venv/bin/activate
celery -A workers.celery_app worker --loglevel=info -Q tryon --concurrency=1 --pool=solo

# 프론트엔드 (터미널 3)
cd frontend
npm install
npm run dev
```

> 백엔드만 띄우고 워커를 띄우지 않으면 Job이 `queued` 상태에서 멈춥니다. 워커가 반드시 함께 떠 있어야 처리됩니다.

### 3.3 환경 설정

설정값은 `backend/config.py`의 기본값에 `backend/.env`가 덮어씁니다. 주요 항목:

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `DEVICE` | `cuda` | `cuda` 또는 `cpu`. GPU 없으면 `cpu`로 설정해 Stub 모드 사용 |
| `REDIS_URL` | `redis://localhost:6379/0` | 브로커·결과 백엔드 |
| `MAX_IMAGE_SIZE_MB` | 20 | 업로드 최대 크기 |
| `JOB_TTL_SECONDS` | 3600 | 결과·작업 보관 시간(1시간) |
| `DEFAULT_NUM_STEPS` | 30 | 추론 스텝 수 |
| `DEFAULT_GUIDANCE_SCALE` | 2.0 | 가이던스 스케일 |
| `MAX_CANDIDATES` | 4 | 1회 생성 최대 후보 수 |

`upload_dir`, `result_dir`, `model_cache_dir`는 기동 시 자동 생성됩니다.

---

## 4. 정상 동작 확인

배포 후 아래를 순서대로 확인합니다.

1. `curl http://localhost:8000/health` → 200 응답
2. UI(3000)에서 마네킹·의류 이미지 업로드, 카테고리 선택(`top`/`bottom`/`dress`) 후 생성 요청
3. 워커 로그에서 단계별 진행률 출력 확인 (`[job_id] step (pct%)`)
4. 결과 이미지가 `backend/storage/results`에 생성되고 UI 그리드에 표시되는지 확인

API로 직접 검증할 경우:

```bash
# Job 생성
curl -X POST http://localhost:8000/api/v1/tryon \
  -F "mannequin_image=@mannequin.jpg" \
  -F "garment_image=@garment.jpg" \
  -F "category=top" \
  -F "fit_mode=auto"

# 상태 조회 (반환된 job_id 사용)
curl http://localhost:8000/api/v1/tryon/{job_id}
```

지원 이미지 형식은 `.jpg`, `.jpeg`, `.png`, `.webp`이며 20MB를 초과하면 거부됩니다. Job 상태는 `queued → started/progress → completed/failed`로 진행합니다.

---

## 5. 일상 운영

### 5.1 모니터링 포인트

- **워커 큐 적체**: Redis `tryon` 큐 길이. 동시성 1이므로 요청이 몰리면 대기가 길어집니다. 큐 길이를 주기적으로 확인하세요.
- **GPU 사용률/VRAM**: `nvidia-smi`로 OOM 여부 확인. 후보 수(`num_candidates`)나 스텝 수가 높으면 VRAM 압박이 커집니다.
- **디스크**: `backend/storage/uploads`, `backend/storage/results` 증가. 결과는 TTL(기본 1시간) 이후 만료되지만 업로드 원본 파일은 자동 삭제되지 않으므로 누적됩니다.
- **로그**: 백엔드·워커는 loguru로 콘솔 로그를 남깁니다. Docker 환경에서는 `docker compose logs -f worker`로 추적합니다.

### 5.2 스토리지 정리

업로드 폴더는 자동 정리되지 않습니다. 주기적으로 오래된 파일을 삭제하세요.

```bash
# 7일 이상 된 업로드 원본 정리 (예시)
find backend/storage/uploads -type f -mtime +7 -delete
```

결과 이미지는 `JOB_TTL_SECONDS` 만료 후 Redis 메타가 사라지지만 파일 자체는 남을 수 있으므로 동일하게 정리 대상에 포함합니다.

### 5.3 재기동·업데이트

```bash
docker compose pull            # 이미지 갱신 시
docker compose up --build -d   # 재빌드 후 재기동
docker compose restart worker  # 워커만 재기동
```

`task_acks_late=True`로 설정되어 있어 워커가 작업 중 죽어도 작업이 재배달됩니다. 다만 GPU 추론이 멱등하지 않을 수 있으니 재기동 중 진행 중이던 Job은 결과를 다시 확인하세요. `max_retries=2`, 재시도 지연 5초가 설정되어 있습니다.

---

## 6. 장애 대응

| 증상 | 원인 추정 | 조치 |
|------|-----------|------|
| Job이 계속 `queued` | 워커 미기동 또는 Redis 연결 실패 | 워커 프로세스/컨테이너 상태와 `REDIS_URL` 확인 |
| `failed` 다발, 로그에 CUDA OOM | VRAM 부족 | `num_candidates`·`DEFAULT_NUM_STEPS` 축소, 다른 GPU 프로세스 종료 |
| 결과가 반투명 합성 이미지 | Stub 모드 동작 (모델 로드 실패) | `DEVICE=cuda` 확인, GPU·드라이버·모델 캐시 점검 |
| 업로드 400 에러 | 미지원 형식 또는 20MB 초과 | 형식·용량 확인 |
| 결과 이미지 404 | TTL 만료 후 조회 | `JOB_TTL_SECONDS` 내에 조회하거나 재생성 |
| 첫 요청이 매우 느림 | 모델 최초 다운로드·로드 | `storage/models` 캐시 워밍업 후 재시도 |

워커가 떠 있는데도 처리가 안 되면 `redis-cli ping`(PONG 확인), `docker compose ps`로 컨테이너 상태, 그리고 워커 로그를 순서대로 점검합니다.

---

## 7. 백업

영속화 대상은 호스트에 마운트된 두 경로입니다.

- `backend/storage/` — 업로드·결과·모델 캐시
- `finetune/` — LoRA 가중치 및 데이터셋

모델 캐시(`storage/models`)는 재다운로드가 가능하므로 백업 우선순위가 낮습니다. 반면 `finetune/output`의 학습된 LoRA 가중치는 재현 비용이 크므로 반드시 백업하세요. Redis는 휘발성 작업 상태만 담고 있어 백업 대상이 아닙니다.

---

## 8. 파인튜닝 운영

모든 명령은 프로젝트 루트에서 실행합니다.

```cmd
cd "D:\fashon_tryon\AI를 이용한 마네킹 핏 시스템"

:: 1. 데이터셋 준비 (raw 폴더에 {id}_mannequin.jpg / {id}_garment.jpg)
python finetune/scripts/prepare_dataset.py --raw_dir finetune/dataset/raw

:: 2. 학습
accelerate launch finetune/scripts/train_lora.py --config finetune/configs/lora_config.yaml

:: 3. 평가
python finetune/scripts/evaluate.py --lora_dir finetune/output/lora_weights --data_dir finetune/dataset/val
```

학습된 가중치는 `finetune/output`에 저장되며, Docker Compose에서 `finetune` 디렉토리가 백엔드·워커에 마운트되므로 워커 재기동 시 반영됩니다. raw 데이터 형식은 `finetune/dataset/README.md`를 참고하세요.

---

## 9. API 레퍼런스 (운영 점검용)

| 메서드 | 경로 | 설명 |
|--------|------|------|
| POST | `/api/v1/tryon` | 피팅 Job 생성 (multipart) |
| GET | `/api/v1/tryon/{job_id}` | Job 상태·결과 조회 |
| POST | `/api/v1/tryon/layered` | 상의+하의 레이어링 |
| GET | `/health` | 서버 상태 확인 |
| GET | `/results/{file}` | 결과 이미지 정적 서빙 |
| GET | `/uploads/{file}` | 업로드 이미지 정적 서빙 |

`POST /api/v1/tryon` 주요 폼 필드: `mannequin_image`(필수), `garment_image`(필수), `category`(`top`/`bottom`/`dress`, 필수), `garment_size`(치수 JSON, 선택), `fit_mode`(`auto`/`tight`/`regular`/`loose`, 선택), `num_candidates`(1~4, 선택), `remove_background`(선택).

`garment_size` 예시:

```json
{ "unit": "cm", "total_length": 65, "chest": 96, "shoulder": 42, "sleeve": 60 }
```

---

## 10. 점검 체크리스트

일일 점검: `/health` 응답, 워커 컨테이너 상태, GPU VRAM 여유, 디스크 사용량.

주간 점검: `storage/uploads` 정리, 결과 폴더 용량 확인, 로그 내 반복 오류 패턴 확인, `finetune/output` 백업 상태.

배포 시: 이미지 재빌드 후 `/health` 및 샘플 Job 1건 end-to-end 확인, 워커 로그에서 단계별 진행률 정상 출력 확인.
