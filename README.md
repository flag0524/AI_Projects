# LaonGEN — 기술 요구사항 문서 (Technical PRD)

**버전:** 2.1.0
**최종 수정:** 2026-06-05
**대상 독자:** 개발자, 운영자

---

## 1. 시스템 아키텍처

```
[React 18 + Vite]  (프론트엔드 :5173)
   │  ① 모드 선택: 모델 컷 생성 / 마네킹 피팅
   │  ② 의류 + (선택)모델 템플릿 업로드
   ▼  multipart/form-data
[FastAPI]          (백엔드 :8000)
   ├─ POST /api/v1/generate    → LaonGEN 생성형 (모델 컷)
   ├─ GET  /api/v1/generate/status
   └─ POST /api/v1/fit         → 절차적 마네킹 피팅 (폴백)
   ▼
[LaonGEN 엔진]  backend/pipeline/laongen_engine.py
   백엔드 우선순위:
     1. HuggingFace Leffa   (무료, 상의+하의)   ← 기본
     2. HuggingFace IDM-VTON(무료, 상의 전용)
     3. Replicate IDM-VTON  (유료)
     4. 절차적 합성          (최종 폴백)
```

---

## 2. 디렉토리 구조

```
backend/
├── main.py                       # FastAPI 앱 + .env 로더 + CORS
├── api/
│   ├── fit.py                    # POST /fit (절차적)
│   └── generate.py               # POST /generate, GET /generate/status
├── pipeline/
│   ├── laongen_engine.py         # 하이브리드 오케스트레이션 (백엔드 선택)
│   ├── hf_provider.py            # HuggingFace Spaces (Leffa/IDM-VTON)
│   ├── generative_provider.py    # Replicate (유료, SSL/결제 처리)
│   ├── preprocessor.py           # 리사이즈 + 패딩
│   ├── bg_remover.py             # rembg 배경 제거
│   ├── body_analyzer.py          # 신체 영역 감지 (절차적용)
│   ├── garment_warper.py         # 스캔라인 와핑 (절차적용)
│   ├── composer.py               # 레이어 합성 (절차적용)
│   ├── segmenter.py / shadow_generator.py
│   └── pose_estimator.py
├── assets/templates/             # 번들 모델 템플릿
│   ├── model_neutral.jpg         # 기본 (정면 중립 포즈)
│   ├── model_fullbody.jpg
│   └── model_female_*.jpg
└── requirements.txt
frontend/
├── src/
│   ├── App.jsx                   # 모드 토글 + 상태 표시
│   ├── api/fitApi.js             # submitGenerate / submitFitting / status
│   └── components/
│       ├── UploadPanel.jsx       # 모드별 입력 (템플릿/마네킹)
│       ├── ResultPanel.jsx
│       ├── LoadingSpinner.jsx
│       └── Icons.jsx
.env                              # HF_TOKEN, HF_TRYON_SPACE 등 (git 제외)
```

---

## 3. 생성형 백엔드 (핵심)

### 3.1 Leffa (기본, 무료)
- **Space:** `franciszzj/Leffa` (HuggingFace, gradio_client)
- **엔드포인트:** `/leffa_predict_vt`
- **카테고리:** `upper_body` / `lower_body` / `dresses` 지원 → 풀코디 가능
- **모델 타입:** 하의는 `dress_code`, 그 외 `viton_hd` 자동 선택
- **인증:** `HF_TOKEN` (무료 발급, ZeroGPU 일일 할당량)
- **순차 처리:** 상의(upper_body) → 하의(lower_body) 순으로 try-on

```python
# hf_provider.py 핵심 호출
client.predict(
    handle_file(human_path),    # src_image_path (모델)
    handle_file(garm_path),     # ref_image_path (의류)
    False, 30, 2.5, 42,         # ref_accel, step, scale, seed
    model_type,                 # viton_hd | dress_code
    category,                   # upper_body | lower_body | dresses
    False,                      # vt_repaint
    api_name="/leffa_predict_vt",
)
```

### 3.2 대체 백엔드
| 백엔드 | 비고 |
|--------|------|
| `yisol/IDM-VTON` | 무료, 익명 가능, **상의 전용** |
| Replicate IDM-VTON | 유료 (크레딧), `REPLICATE_API_TOKEN` |
| 절차적 합성 | GPU/네트워크 불필요, 품질 제한적 |

### 3.3 백엔드 선택 로직 (`GEN_BACKEND` 환경변수)
- `hf` (기본): Leffa → 실패 시 절차적
- `replicate`: Replicate → 실패 시 절차적
- `auto`: HF → Replicate → 절차적

---

## 4. API 명세

### POST /api/v1/generate
```
Content-Type: multipart/form-data
- garment_images[]     : 의류 이미지 (필수, 복수)
- garment_types[]      : top|bottom|dress|accessory (필수, 의류와 동일 개수)
- model_template_image : 모델 템플릿 (선택)
- mannequin_image      : 절차적 폴백용 마네킹 (선택)

200 OK:
{ "status":"success", "method":"hf|generative|procedural",
  "result_image_base64":"data:image/png;base64,...",
  "processing_time_ms": 65000 }

402: 크레딧 부족 (Replicate)   /   422: 입력 검증   /   500: 처리 오류
```

### GET /api/v1/generate/status
```json
{ "generative_available": true,
  "active_backend": "huggingface/franciszzj/Leffa",
  "hf_available": true, "replicate_available": true }
```

---

## 5. 환경 설정 (.env)

```bash
HF_TOKEN=hf_xxxxx                 # HuggingFace 토큰 (무료, ZeroGPU 할당량)
HF_TRYON_SPACE=franciszzj/Leffa   # 사용할 Space (기본 Leffa)
GEN_BACKEND=hf                    # hf | replicate | auto
REPLICATE_API_TOKEN=r8_xxxxx      # (선택) Replicate 유료 백엔드
```
> `.env`, `input/real/`는 `.gitignore`로 제외 (토큰/원본 보호).

---

## 6. 기술 스택

| 레이어 | 기술 |
|--------|------|
| 백엔드 | Python 3.11, FastAPI, Uvicorn |
| 생성형 | gradio_client (HF Spaces: Leffa/IDM-VTON), replicate |
| 이미지 처리 | OpenCV, Pillow, NumPy, SciPy, rembg, mediapipe |
| 프론트엔드 | React 18, Vite, axios |
| 네트워크 | truststore (Windows 시스템 인증서로 SSL 가로채기 환경 통과) |

---

## 7. 알려진 이슈 및 운영 노트

### 7.1 SSL 인증서 (해결됨)
기업 프록시/백신 SSL 가로채기 환경에서 certifi 번들로 TLS 검증 실패 →
`truststore.inject_into_ssl()`로 **Windows 시스템 인증서 저장소** 사용해 해결.

### 7.2 무료 백엔드 가용성 (운영 변동)
조사 시점 기준 무료 하의 지원 Space 현황:
| Space | 하의 | 상태 |
|-------|------|------|
| **Leffa** | ✅ | **정상 (채택)** |
| CatVTON | ✅ | 서버 IndexError (불안정) |
| OOTDiffusion | ✅ | RUNTIME_ERROR (다운) |
| Kolors | ✅ | API 차단 (show_api=False) |
| IDM-VTON | ❌ 상의만 | 정상 |

→ Space 다운 대비 다중 백엔드 폴백 구조 유지.

### 7.3 ZeroGPU 일일 할당량
무료 HF 토큰은 일일 ZeroGPU 한도 존재. 소진 시:
- 약 24시간 후 자동 리셋, 또는
- HF PRO 구독($9/월, 25분/일), 또는
- 다른 HF 토큰 사용.

### 7.4 마네킹 직접 착용 불가 (설계 제약)
try-on AI는 DensePose 기반 인체 감지 필요 → 마네킹(머리/다리 없음)은
`IndexError` 발생. 자연 생성은 **실제 모델 템플릿** 경로만 유효.

---

## 8. 로컬 실행

```bash
# 백엔드
pip install -r backend/requirements.txt
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000

# 프론트엔드
cd frontend && npm install && npm run dev   # http://localhost:5173
```

---

## 9. 검증 방법

```bash
# 상태 확인
curl http://localhost:8000/api/v1/generate/status

# 모델 컷 생성 (상의+하의)
curl -X POST http://localhost:8000/api/v1/generate \
  -F "garment_images=@top.png" -F "garment_types=top" \
  -F "garment_images=@bottom.png" -F "garment_types=bottom"
# → method=hf, 자연스러운 모델 착용 컷 반환 (~60초)
```
