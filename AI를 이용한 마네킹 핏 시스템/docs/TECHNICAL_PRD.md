# Technical PRD — AI 마네킹 핏(가상 피팅) 시스템

| 항목 | 내용 |
|---|---|
| 문서 버전 | v1.4 |
| 작성일 | 2026-05-29 |
| 최종 수정 | 2026-06-02 |
| 상태 | In Progress |
| 상위 문서 | `PRD.md` |
| 기술 방향 | Diffusion 기반 Virtual Try-On + CV 워핑 경량 엔진 |

---

## 1. 목적 및 범위

`PRD.md`에서 정의한 제품 요구사항을 구현하기 위한 기술 설계서. 마네킹 이미지와 의류 이미지를 입력받아, 사이즈·체형을 반영한 가상 피팅 결과를 생성하는 파이프라인의 아키텍처, 모델, 데이터 흐름, API, 인프라를 정의한다.

v1.2에서 추가: 의류 카테고리 재정의, 엔진 티어 자동 선택, CPU/저VRAM 경량 엔진.
v1.3에서 추가: 일반의상 상의/하의 분리 업로드 존, 자동 레이어링 전환 로직.
v1.4에서 추가/수정: 전처리 리사이즈(확대 포함) 버그 수정, 포즈 재추정 좌표 정합, Tier 3 해부학적 의류 배치 + 거치대 제외, 핏 엔진 cm 환산 버그 수정, postprocess 후처리 통합, 종합 품질점수, 인프로세스/Celery 경로 일치, 저VRAM GPU 제약 명시.

---

## 2. 의류 카테고리 체계 (v1.3)

```
의류 종류
├── 일반의상 (general)
│   ├── 상의 업로드 존  (내부: top)  — T셔츠, 셔츠, 재킷, 코트 등
│   ├── 하의 업로드 존  (내부: bottom) — 바지, 스커트, 레깅스 등
│   └── 상의+하의 동시  (내부: layered) — 자동 레이어링 파이프라인
├── 원피스 (dress) — 단일 업로드 존
│   └── 원피스, 점프수트, 미니/맥시 드레스
└── 기타 악세서리 (accessory) — 단일 업로드 존
    ├── 머리: 모자, 헤어밴드
    ├── 목: 스카프, 목걸이
    ├── 허리: 벨트
    └── 전신: 가방, 백팩
```

**프론트엔드 업로드 로직 (일반의상):**

```
일반의상 선택
  ├── 상의만 업로드   → category=top, 단일 피팅
  ├── 하의만 업로드   → category=bottom, 단일 피팅
  └── 상의+하의 모두  → 자동으로 submitLayered() 호출 → 레이어링 파이프라인
```

**카테고리별 처리 차이:**
- 일반의상(단일)·원피스: 포즈 추정 → 체형 정합 → Diffusion/CV 합성
- 일반의상(레이어링): 상의 합성 → 중간 결과 → 하의 합성 순차 처리
- 악세서리: 포즈 추정 → 키포인트 기반 위치 결정 → 오버레이 합성 (핏 엔진 스킵)

---

## 3. 엔진 티어 자동 선택 (v1.2 신규)

```
[engine_selector.py]
    │
    ├── GPU VRAM ≥ 8GB  → Tier 1: IDM-VTON (최고 품질)
    ├── GPU VRAM 2~8GB  → Tier 2: SD 1.5 경량 인페인팅 (중간 품질)
    └── CPU / VRAM <2GB → Tier 3: CV 워핑 합성 (빠른 결과)
```

`.env`에서 `ENGINE_TIER=0`(자동) 또는 `1/2/3`(수동 고정).

> **⚠️ 저VRAM GPU 실측 제약 (v1.4)**
> 자동감지는 VRAM ≥2GB를 Tier 2로 분류하지만, **실측상 VRAM 2GB(예: NVIDIA MX450)에서는 SD 1.5(Tier 2)·IDM-VTON(Tier 1) 모두 구동 불가**하다. 대형 UNet 적재 시 프로세스가 세그폴트로 종료된다(VRAM 부족 + 드라이버/런타임 불안정). 안정 동작을 위해 이런 환경에서는 `ENGINE_TIER=3`으로 고정한다.
> - **Tier 2 안정 권장 VRAM: 4GB+**, Tier 1: 12GB+ (CPU offload 시 8GB).
> - 엔진 로드 실패는 try/except로 Tier 3 폴백되지만, **세그폴트는 폴백 불가**(프로세스 종료)이므로 수동 고정이 필요하다.
>
> **Tier 2 SD1.5 한계**: 현재 구현은 텍스트 프롬프트("a mannequin wearing a {category}") 기반 인페인팅으로, **업로드한 의류 이미지를 재현하지 않는다**(일반적 의류를 생성). 사용자 의류를 그대로 입히려면 IP-Adapter 등 이미지 조건부 도입 필요(M3 과제).

### Tier 1 — IDM-VTON

- 모델: `yisol/IDM-VTON` (HuggingFace)
- 입력: agnostic map + pose map + garment image + fit control params
- VRAM: 약 12GB (fp16), CPU offload 시 8GB
- 생성 시간: GPU P95 ≤ 15초

### Tier 2 — SD 1.5 경량 인페인팅

- 모델: `runwayml/stable-diffusion-inpainting`
- 해상도: 512×512 (결과 후 원본 크기로 업스케일)
- 최적화: fp16 + `enable_model_cpu_offload()` + `enable_attention_slicing()`
- VRAM: 약 2~4GB
- 생성 시간: GPU P95 ≤ 30초

### Tier 3 — CV 워핑 합성 (GPU 불필요)

- 딥러닝 모델 없음. OpenCV만 사용.
- 처리 순서:
  1. 마스크 BBox 추출 (키포인트 기반)
  2. 의류 → BBox affine 리사이즈 (여유율 반영)
  3. 색상 히스토그램 매칭 (조명 보정)
  4. GaussianBlur 페더링 마스크 블렌딩
- 악세서리: 키포인트 기반 위치 결정 → 알파 블렌딩
- 생성 시간: CPU P95 ≤ 5초
- 품질: 워핑 수준 (Diffusion 대비 낮음, 미리보기·저사양 용도)

---

## 4. 시스템 아키텍처

```
[Client/Web — React + Vite]
    │  마네킹 + 의류 + 카테고리(라디오) + 사이즈
    ▼
[FastAPI BFF] ── 인증/검증 ──► [Object Storage (원본 이미지)]
    │  Celery task.apply_async(queue="tryon")
    ▼
[Redis Broker] ──► [Celery Worker (GPU/CPU)]
                          │
        ┌─────────────────┼──────────────────────────────────┐
        ▼                 ▼                                   ▼
 [전처리]          [포즈·체형 추정]                   [의류 파싱/마스킹]
 preprocess.py     pose_estimation.py                garment_parsing.py
                   body_parsing.py
        └─────────────────┼──────────────────────────────────┘
                          ▼
               [엔진 선택기 — engine_selector.py]
                 Tier 1 / 2 / 3 자동 결정
                          ▼
              ┌───────────┴────────────┐
        [tryon_model.py]     [lightweight_engine.py]
        IDM-VTON (T1)        SD1.5 (T2) / CV 워핑 (T3)
              └───────────┬────────────┘
                          ▼
               [사이즈·체형 정합 — fit_engine.py]
               (악세서리 카테고리는 스킵)
                          ▼
               [디테일 보존 검증 — detail_verification.py]
               DINOv2 → CLIP → SSIM (임계 미만 시 재생성)
                          ▼
              [결과 Storage] ──► [Polling] ──► Client
```

---

## 5. 처리 파이프라인 (상세)

### 5.1 입력 전처리 (`preprocess.py`)

- EXIF 회전 보정, RGB 변환
- 배경 제거 (옵션): `rembg` 기반
- 의류 자동 정렬: PCA 주축 기반 회전 + 종횡비 보정
- 포즈 정규화: 어깨 수평 정렬(1차 포즈 기준)
- **크기 표준화 (v1.4 수정)**: 하드웨어별 처리 해상도(`detect_hardware().process_size`, 예 1024×1365)에 **종횡비 유지하며 확대·축소 모두 적용**하여 캔버스를 채운다.
  - ⚠️ 기존에는 PIL `thumbnail()`(축소 전용)을 사용해, 처리 해상도보다 작은 원본이 캔버스 하단에 작게 깔리고 전경 마스크·합성이 전부 어긋났음 → 비율 리사이즈(확대 포함)로 수정.
- **포즈 좌표 정합 (v1.4)**: 전처리 후 마네킹이 리사이즈되므로, 엔진 입력 좌표계와 일치시키기 위해 **전처리된 마네킹에 대해 포즈를 재추정**한다(원본 좌표 사용 시 의류가 엉뚱한 높이에 배치되는 문제 방지).

### 5.2 마네킹 포즈 & 체형 추정 (`pose_estimation.py`)

우선순위:
1. **DWPose** (`controlnet_aux`): 키포인트 18개 직접 추출 + pose_map 생성
2. **MediaPipe Pose**: COCO-18 변환 폴백
3. **표준 마네킹 기본값**: 정면 서 있는 포즈 폴백

출력: `pose_map` (RGB), `body_measurements` (상대 비율), `keypoints` (18×3)

### 5.3 신체 파싱 (`body_parsing.py`)

- Segformer(`mattmdjaga/segformer_b2_clothes`) 또는 색상 기반 폴백
- 출력 마스크: upper / lower / arms / legs / face / hair
- `make_agnostic_map()`: 교체 대상 영역을 회색(128)으로 채운 person-agnostic 이미지

### 5.4 의류 파싱 (`garment_parsing.py`)

- 흰 배경 기준 전경 마스크 → morphological 정제
- 카테고리별 랜드마크(상의: 어깨선, 하의: 허리선) 추출

### 5.5 핏 엔진 (`fit_engine.py`)

악세서리 카테고리는 즉시 기본값 반환. 나머지:

- 여유율(ease) = 의류 둘레 − 신체 둘레
- 길이 랜드마크: 총장/키 비율 → 옷자락 위치
- 포즈 기반 동적 계산: 체형 분류(slim/normal/plus), 어깨·몸통 기울기 → 드레이프·워핑 강도 보정
- FitParams: ease_ratio, drape_intensity, length_ratio, warping_strength, body_type, pose_angle_correction
- ⚠️ **cm 환산 버그 수정 (v1.4)**: 정규화 신체 비율→cm 변환 시 기준키(`ref_height_cm`)를 이중 적용해 둘레가 수천 cm로 폭주하던 문제 해결(여유율/핏 라벨 오류 유발). `scale = ref_height_cm / 정규화키` 한 번만 곱하도록 정정.

### 5.6 엔진 추론

**Tier 1 (`tryon_model.py`)**
- IDM-VTON: agnostic_map + pose_map + garment + fit_params → RGB 결과
- LoRA 가중치 자동 로드 (`finetune/output/lora_weights` 존재 시)

**Tier 2 (`lightweight_engine.py` — SD 1.5)**
- 512×512 인페인팅 → 원본 크기 업스케일
- CPU offload + attention slicing 사용 (안정 동작 VRAM 4GB+ 권장)
- 한계: 텍스트 프롬프트 기반 — 업로드 의류 미재현(§3 참조)

**Tier 3 (`lightweight_engine.py` — shape-aware CV 워핑, v1.4 정정)**
- 전경 분리: `rembg`(U2Net) 우선, 실패 시 테두리 flood-fill 폴백 → 최대 연결성분
- **옷 입는 폼 추출**: 행별 너비 프로파일에서 최대 너비의 35% 이상 영역만 사용 → **얇은 거치대/드레스폼 스탠드 봉 제외**
- **해부학적 세로 배치 (실루엣 bbox 비율 기준)**: 어깨 0.10 / 엉덩이 0.50 / 무릎 0.72 / 발목 0.95
  - 상의 = 어깨~엉덩이, 하의 = 엉덩이~발목, 원피스 = 어깨~무릎
  - (Tier 3에는 신뢰할 포즈 모델이 없어 실루엣 비율을 1차 기준으로 사용 — 폴백 키포인트가 프레임 기준이라 figure 위치와 어긋나는 문제 회피)
- **shape-aware 워핑**: 의류를 각 출력 행의 실제 신체 너비로 리샘플 → 어깨·허리 굴곡을 따름(여유율 반영)
- 색 보존 + 마네킹 국부 음영만 미세 적용, GaussianBlur 페더링 블렌딩, 폼 영역으로 크롭(스탠드 제외)
- 악세서리: 키포인트 기반 위치 결정 + 알파 블렌딩

### 5.6a 후처리 (`postprocess.py`, v1.4 신규 통합)

엔진 합성 결과 전체에 적용 (인프로세스·Celery 경로 공통):
- 노이즈 제거(GaussianBlur), 색감 조화(HSV 밝기 보정), 선명도(언샤프 마스킹)
- 경계 블렌딩은 **비파괴**로 구현(차원 일치 시에만, 배경을 검게 만들지 않음)
- 단일 피팅 경로는 의류 크기 마스크를 넘기지 않음(차원 불일치/배경 손상 방지)

### 5.7 디테일 보존 검증 (`detail_verification.py`)

- 종합 품질 점수(0~100) 반환: 디테일 보존/경계/색감/주름 가중합 + 상태 분류
- 외부 모델(DINOv2/Segformer) 미가용(오프라인/SSL) 시 SSIM·색상 기반으로 안전 폴백
- ⚠️ v1.4: 반환 타입이 dict(종합 점수)로 변경됨에 따라, 추론 경로의 단순 `score < 0.80` 비교(float 가정)는 제거. 현재 인프로세스·Celery 경로는 후처리 후 바로 저장하며 자동 재생성 게이트는 비활성(품질점수는 리포트·로깅용).

---

## 6. 카테고리별 악세서리 배치 로직 (Tier 3)

```python
# 악세서리 비율로 위치 결정 (휴리스틱)
if acc_ratio < 0.5:   # 가로형 → 벨트/스카프 → 허리 위치
if acc_ratio > 1.5:   # 세로형 → 가방 → 옆구리
else:                 # 정방형 → 모자 → 머리 위
```

---

## 7. API 설계

### 7.1 Job 생성

```
POST /api/v1/tryon
Content-Type: multipart/form-data

fields:
  mannequin_image : file
  garment_image   : file
  category        : "top" | "bottom" | "dress" | "accessory"
  garment_size    : JSON (cm, 선택)
  fit_mode        : "auto" | "tight" | "regular" | "loose"
  num_candidates  : int (1~4)
  remove_background: bool
  seed            : int (선택)

→ 202 { "job_id": "uuid", "status": "queued" }
```

### 7.2 상태 조회

```
GET /api/v1/tryon/{job_id}
→ {
    "job_id", "status": "queued|processing|succeeded|failed",
    "step": "포즈·체형 추정",   // 진행 중 단계
    "progress": 35,             // 0~100
    "results": [ { "image_url", "seed", "fit_report": { ... } } ],
    "error": null
  }
```

### 7.3 레이어링

```
POST /api/v1/tryon/layered
  mannequin_image, top_image(+size), bottom_image(+size), fit_mode, seed
→ 202 { "job_id" }
```

### 7.4 취소

```
DELETE /api/v1/tryon/{job_id}
→ { "job_id", "cancelled": true }
```

### 7.5 오류 코드

| 코드 | 의미 |
|---|---|
| 400 | 입력 검증 실패 |
| 409 | 치수-체형 불일치 경고 |
| 422 | 처리 불가 이미지 |
| 501 | 해당 기능 미지원 (레이어링 등) |
| 500 | 내부 오류 |

---

## 8. 모델 & 라이브러리 스택

| 단계 | Tier 1 | Tier 2 | Tier 3 |
|---|---|---|---|
| Try-On 생성 | IDM-VTON (diffusers) | SD 1.5 Inpainting | — |
| 배경 제거 | SAM / rembg | rembg | rembg |
| 포즈 추정 | DWPose → MediaPipe | DWPose → MediaPipe | MediaPipe → fallback |
| 신체 파싱 | Segformer | Segformer | 색상 기반 |
| 의류 합성 | Diffusion | Diffusion(텍스트 프롬프트) | shape-aware CV 워핑 |
| 후처리 | postprocess | postprocess | postprocess |
| 디테일 검증 | DINOv2 / CLIP | CLIP / SSIM | SSIM(폴백) |
| 업스케일 | Real-ESRGAN | Lanczos | — |

---

## 9. 인프라 & 배포

```yaml
# docker-compose.yml 서비스
redis:    Redis 7 브로커/백엔드
backend:  FastAPI (uvicorn)
worker:   Celery Worker --concurrency=1 --pool=solo
frontend: React (Nginx)
```

- GPU 워커: NVIDIA Container Toolkit, `deploy.resources.reservations.devices`
- CPU 전용: `ENGINE_TIER=3` 설정, GPU 예약 블록 제거
- 스토리지: `storage/uploads` / `storage/results` 볼륨 마운트
- LoRA: `finetune/output/lora_weights` 마운트 → 서버 재시작 시 자동 로드

---

## 10. 설정 파일 (`.env`)

```env
DEVICE=cpu           # cuda | cpu
ENGINE_TIER=3        # 0=자동감지, 1=IDM-VTON, 2=SD1.5, 3=CV워핑
REDIS_URL=redis://localhost:6379/0
DEFAULT_NUM_STEPS=30
DEFAULT_GUIDANCE_SCALE=2.0
MAX_CANDIDATES=4

# 후처리 토글 / 품질 (postprocess.py)
ENABLE_POSTPROCESS=true
ENABLE_BLEND=true
ENABLE_COLOR_HARMONY=true
ENABLE_DENOISE=true
ENABLE_SHARPENING=true
QUALITY_THRESHOLD=70
SEGMENTATION_MODEL=yolov8l-seg
```

> 현재 검증 환경(MX450 2GB)에서는 `ENGINE_TIER=3` 고정. 8GB+ GPU 환경으로 이전 시 `ENGINE_TIER=0`(자동)·`DEVICE=cuda`로 변경하면 Tier 1/2 활성화.
>
> **오프라인/사내망 SSL 주의**: `huggingface_hub`(requests/certifi)가 SSL 인증서 검증에 실패할 수 있음(사내 SSL 가로채기). `pip install pip-system-certs`로 Windows 인증서 저장소를 사용하게 하면 해결됨.

---

## 11. 성능 목표

| 항목 | Tier 1 | Tier 2 | Tier 3 |
|---|---|---|---|
| 단일 생성 지연(P95) | ≤ 15s | ≤ 30s | ≤ 5s |
| 필요 VRAM | ≥ 8GB | 2~8GB | 불필요 |
| CLIP-I 유사도 | ≥ 0.85 | ≥ 0.75 | ≥ 0.60 |
| 배치 처리량 | ≥ 4 req/min/GPU | ≥ 2 req/min/GPU | ≥ 12 req/min/CPU |

---

## 12. 품질·검증 전략

- **오프라인 평가**: SSIM/LPIPS, FID, CLIP-I, DINOv2, MOS (인간 평가)
- **정합 로직 단위 테스트**: 여유율 경계, 길이 매핑, 악세서리 위치 케이스
- **티어 회귀 테스트**: 동일 입력에 대한 Tier 1/2/3 품질 비교
- **가드레일**: 치수 불일치 경고, 콘텐츠 안전 필터, VRAM 부족 시 자동 다운그레이드

---

## 13. 단계별 구현 현황

| 단계 | 기술 산출물 | 상태 |
|---|---|---|
| M0 | 단일 카테고리 PoC, 수동 마스크 | ✅ |
| M1 | 포즈 자동화, 정합 엔진, Celery, 레이어링, 파인튜닝 | ✅ |
| M2 | 카테고리 재정의, 경량 엔진 Tier 2/3, 악세서리 합성 | ✅ |
| M2.1 | 일반의상 상의/하의 분리 업로드, 자동 레이어링 전환 | ✅ |
| M2.2 | 실사 피팅 정확도 개선: 전처리 리사이즈(확대) 버그, 포즈 좌표 정합, 해부학 배치+거치대 제외, cm 환산 버그, postprocess 통합, 인프로세스/Celery 일치 | ✅ |
| M3 | TensorRT, 오토스케일, 배치, Real-ESRGAN, **Tier 2 의류 조건부(IP-Adapter)** | 예정 |

---

## 14. 기술 리스크 & 대응

| 리스크 | 대응 |
|---|---|
| IDM-VTON 라이선스 제약 | 상업용 가능 모델 확인 후 LoRA 파인튜닝으로 대체 |
| Tier 3 품질 한계 | 결과 화면에 티어 정보 표시, GPU 업그레이드 안내 |
| **저VRAM GPU(2GB)에서 디퓨전 세그폴트** | `ENGINE_TIER=3` 수동 고정(세그폴트는 try/except 폴백 불가). Tier 2는 4GB+, Tier 1은 12GB+ 권장 |
| **드레스폼(토르소) 마네킹 하의 미배치** | 다리 없는 폼은 하의 입힐 신체 부재 — 상의/원피스·전신 마네킹 권장 |
| **작은 입력 이미지** | 전처리에서 확대 포함 비율 리사이즈로 캔버스 채움(v1.4 수정 완료) |
| 악세서리 위치 오배치 | 키포인트 신뢰도 < 0.3 시 화면 중앙 배치 fallback |
| 체형 추정 오차 | 캘리브레이션 + 사용자 보정 입력 허용 |
| GPU 비용 | 배치·양자화·warm pool, 수요 기반 스케일 |

---

## 15. 오픈 이슈

- SMPL 3D 정합 도입 여부 (정확도↑ vs 복잡도↑).
- 악세서리 세부 분류 자동 감지 (모자/가방/벨트 자동 구분).
- 다양한 포즈(측면, 앉은 자세) 지원을 위한 학습 데이터 확보.
- 온프레미스 GPU vs 클라우드 비용·지연 트레이드오프.
