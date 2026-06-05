# 마네킹 피팅 시스템 — 기술 기획서

**작성일:** 2026-06-04  
**버전:** 1.0.0

> **⚠️ 갱신 안내 (2026-06-05):** 본 문서는 v1.0 절차적 합성 설계를 다룹니다.
> 이후 프로젝트는 **LaonGEN 생성형 모델 컷(v2.x)**으로 발전했습니다.
> 최신 제품/기술 요구사항은 루트의 [`PRD.md`](../../../PRD.md) 및
> [`TECHNICAL_PRD.md`](../../../TECHNICAL_PRD.md)를 참조하세요.
> (절차적 방식은 생성형 백엔드 불가 시 폴백으로 유지됩니다.)

---

## 1. 프로젝트 개요

마네킹 이미지에 의류 이미지를 자동으로 합성하여 자연스러운 가상 피팅 결과를 제공하는 웹 애플리케이션.  
CPU 전용 환경에서 동작하며 품질 우선 접근 방식을 채택한다.

### 목표
- 마네킹 + 의류 이미지 → 자연스러운 피팅 합성 이미지
- 처리 시간: 1~3초 이내 (CPU 512px)
- 지원 의류: 상의 / 하의 / 원피스 / 액세서리

---

## 2. 아키텍처

```
[React 18 + Vite + Tailwind CSS]
         │
         │  HTTP multipart/form-data
         ▼
[FastAPI 서버 :8000]
  POST /api/v1/fit
         │
         ▼
[Processing Pipeline]
  ① Preprocessor   → 512×512 리사이즈 + 패딩
  ② BGRemover      → rembg (U²-Net) 배경 제거
  ③ PoseEstimator  → MediaPipe BlazePose 33 keypoints
  ④ Segmenter      → 알파 마스크 기반 신체 분할
  ⑤ GarmentWarper → TPS (Thin-Plate Spline) 와핑
  ⑥ Composer       → 알파 블렌딩 + Gaussian 페더링
         │
         ▼
[Response: base64 PNG + processing_time_ms]
```

---

## 3. 디렉토리 구조

```
D:\blandu_project\
├── backend/
│   ├── __init__.py
│   ├── main.py                    # FastAPI 앱 + CORS
│   ├── api/fit.py                 # POST /api/v1/fit 엔드포인트
│   ├── pipeline/
│   │   ├── preprocessor.py        # 리사이즈 + 패딩
│   │   ├── bg_remover.py          # rembg 배경 제거
│   │   ├── pose_estimator.py      # MediaPipe 포즈 + 신체 경계
│   │   ├── segmenter.py           # 마스크 추출 + bbox
│   │   ├── garment_warper.py      # TPS 와핑 + affine 폴백
│   │   └── composer.py            # 레이어 알파 합성
│   ├── utils/image_utils.py       # PIL↔CV2 변환, base64
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.jsx                # 메인 레이아웃
│   │   ├── components/
│   │   │   ├── UploadPanel.jsx    # 드래그&드롭 업로드
│   │   │   ├── ResultPanel.jsx    # 결과 미리보기 + 다운로드
│   │   │   └── LoadingSpinner.jsx
│   │   └── api/fitApi.js          # axios API 호출
│   ├── vite.config.js
│   ├── tailwind.config.js
│   └── package.json
├── input/                          # 테스트용 샘플 이미지
├── output/                         # 결과 이미지 저장
└── docs/superpowers/specs/         # 기획서 (현재 파일)
```

---

## 4. UI 레이아웃

```
┌──────────────────────────────────────────────────────┐
│  👗 마네킹 피팅 시스템  │  AI 기반 가상 의류 합성     │
├────────────────────────┬─────────────────────────────┤
│  [1] 이미지 업로드      │  [2] 피팅 결과              │
│                        │                             │
│  마네킹 이미지          │  ┌───────────────────────┐  │
│  ┌──────────────────┐  │  │                       │  │
│  │  드래그 & 드롭   │  │  │   합성된 피팅 이미지   │  │
│  │  또는 클릭       │  │  │                       │  │
│  └──────────────────┘  │  └───────────────────────┘  │
│                        │                             │
│  의류 이미지 [+ 추가]   │  처리 시간: 0.00초          │
│  ┌──────────────────┐  │  [⬇ 다운로드]              │
│  │ [상의▼] [삭제]   │  │                             │
│  │  이미지 드롭존   │  │                             │
│  └──────────────────┘  │                             │
│                        │                             │
│  [피팅 시작]           │                             │
├────────────────────────┴─────────────────────────────┤
│  파이프라인: 🖼전처리 → ✂️배경제거 → 🦴포즈 → ...    │
└──────────────────────────────────────────────────────┘
```

---

## 5. API 명세

### POST /api/v1/fit

**Request (multipart/form-data)**

| 필드 | 타입 | 설명 |
|------|------|------|
| mannequin_image | file | 마네킹 이미지 (jpg/png) |
| garment_images[] | file[] | 의류 이미지 목록 (1~5개) |
| garment_types[] | str[] | top / bottom / dress / accessory |

**Response 200**
```json
{
  "status": "success",
  "fitted_image_base64": "data:image/png;base64,iVBOR...",
  "processing_time_ms": 1842
}
```

**Response 422/500**
```json
{
  "status": "error",
  "detail": "오류 메시지"
}
```

---

## 6. 처리 파이프라인 상세

| 단계 | 모듈 | 기술 | 출력 |
|------|------|------|------|
| ① 전처리 | preprocessor.py | Pillow resize + pad | 512×512 RGBA |
| ② 배경 제거 | bg_remover.py | rembg (U²-Net) | 투명 배경 RGBA |
| ③ 포즈 추정 | pose_estimator.py | MediaPipe BlazePose | 33 keypoints dict |
| ④ 신체 분할 | segmenter.py | alpha channel + morphology | mask + bbox |
| ⑤ 의류 와핑 | garment_warper.py | OpenCV TPS / affine 폴백 | 와핑된 RGBA |
| ⑥ 합성 | composer.py | 알파 블렌딩 + Gaussian 페더링 | RGB 결과 |

---

## 7. 기술 스택

| 레이어 | 기술 |
|--------|------|
| 백엔드 | Python 3.11, FastAPI 0.115, Uvicorn |
| 이미지 처리 | OpenCV 4.10, Pillow 10.4, NumPy 1.26, SciPy 1.13 |
| AI 모델 | rembg 2.0 (U²-Net), MediaPipe 0.10 (BlazePose) |
| 추론 런타임 | ONNX Runtime 1.19 (CPU) |
| 프론트엔드 | React 18, Vite 5, Tailwind CSS 3 |
| HTTP | axios |

---

## 8. 성능 목표

| 지표 | 목표 |
|------|------|
| 단일 요청 처리 시간 | 1~3초 (CPU, 512px) |
| 메모리 사용량 | < 2GB |
| 최대 이미지 크기 | 10MB |
| 최대 의류 개수 | 5개 |

---

## 9. 실행 방법

### 백엔드
```bash
cd D:\blandu_project
pip install -r backend/requirements.txt
python -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

### 프론트엔드
```bash
cd D:\blandu_project\frontend
npm install
npm run dev
```

브라우저에서 `http://localhost:5173` 접속

---

## 10. 로드맵

| 단계 | 내용 |
|------|------|
| v1.0 | 기본 TPS 와핑 + 알파 합성 (현재) |
| v1.1 | Flow 기반 와핑으로 품질 향상 |
| v1.2 | 결과 이력 저장 + 비교 보기 |
| v2.0 | 경량 ONNX 세그멘테이션 모델 통합 |
