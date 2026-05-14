# 🧥 BLANCDEW Mannequin Styler (BMS)

> 블랑듀(Blancdew) 여성복 브랜드 — 마네킹 착장 이미지 자동 생성기  
> **핵심 원칙: 촬영 원본 이미지의 디테일을 절대 변형하지 않습니다.**

---

## 📁 폴더 구조

```
d:\blandu_project\
├── CLAUDE.md              ← Claude Code GSD 컨텍스트 (필독)
├── requirements.txt
├── input\
│   ├── raw_photos\        ← 상품 원본 이미지 (품번.jpg)
│   ├── codi_sets\         ← 코디 세트 (C001/, C002/, ...)
│   └── product_data.xlsx  ← 품번 + 최초판매가 데이터
├── templates\
│   ├── mannequin_front.png ← ⚠️ 직접 준비 필요 (투명 배경 PNG)
│   ├── mannequin_back.png
│   └── backgrounds\
├── output\                ← 생성된 이미지 저장 위치
├── src\                   ← 소스 코드
└── specs\                 ← 좌표·프리셋 설정
```

---

## 🚀 빠른 시작

### 1. 환경 설정

```powershell
# 가상환경 활성화
.\.venv\Scripts\Activate.ps1

# 패키지 설치 확인
pip list
```

### 2. 마네킹 템플릿 준비

`templates/` 폴더에 다음 파일을 배치하세요:
- `mannequin_front.png` — 전면 마네킹 (투명 배경 PNG, 800×1200px 권장)
- `mannequin_back.png` — 후면 마네킹 (선택)

> 마네킹 이미지는 저작권 없는 이미지를 구매하거나,  
> 실물 마네킹 촬영 후 배경 제거하여 사용하세요.

### 3. 상품 데이터 입력

```powershell
# 샘플 엑셀 파일 생성 (처음 한 번만)
.\.venv\Scripts\python.exe src/main.py excel-sample
```

생성된 `input/product_data.xlsx`를 열어 실제 상품 데이터를 입력하세요.

### 4. 상품 이미지 배치

```
input/raw_photos/BLD-2401.jpg   ← 품번과 동일한 파일명
input/raw_photos/BLD-2402.jpg
...

input/codi_sets/C001/BLD-2401.jpg   ← 코디 세트 구성
input/codi_sets/C001/BLD-2405.jpg
```

### 5. 매핑 검증

```powershell
.\.venv\Scripts\python.exe src/main.py validate
```

### 6. 이미지 생성

```powershell
# 단품 처리
.\.venv\Scripts\python.exe src/main.py run --item BLD-2401 --preset single_front

# 코디 세트 처리
.\.venv\Scripts\python.exe src/main.py run --codi C001 --preset codi_full

# 전체 일괄 처리
.\.venv\Scripts\python.exe src/main.py run --all --preset single_front

# 카탈로그 카드 (품번+가격 포함)
.\.venv\Scripts\python.exe src/main.py run --item BLD-2401 --preset catalog_card
```

---

## 🎨 연출 프리셋

| 프리셋 ID | 이름 | 크기 | 용도 |
|-----------|------|------|------|
| `single_front` | 단품 정면 | 800×1200 | 쇼핑몰 상품 등록 |
| `single_back` | 단품 후면 | 800×1200 | 뒷면 디테일 확인 |
| `codi_full` | 코디 전체 | 800×1200 | SNS·스타일링 제안 |
| `lookbook_2col` | 룩북 2열 | 1600×1200 | 인쇄용 룩북 |
| `catalog_card` | 카탈로그 카드 | 800×1100 | 영업·바이어용 |

프리셋 전체 목록: `.\.venv\Scripts\python.exe src/main.py presets`

---

## 🛠 기술 스택

| 역할 | 라이브러리 |
|------|-----------|
| 배경 제거 | `rembg` (로컬 AI, 픽셀 보존) |
| 이미지 합성 | `Pillow` + `OpenCV` |
| 엑셀 파싱 | `openpyxl` |
| CLI | `typer` |
| 로깅 | `loguru` (JSONL) |

---

## ⚠️ 주의사항

- **생성형 AI 미사용**: 이미지 합성에 DALL-E, Midjourney 등을 사용하지 않습니다
- **원본 보존**: rembg로 배경만 제거하고 RGB 픽셀은 원본에서 복원합니다
- **첫 실행**: rembg 모델 다운로드 (~200MB)로 시간이 걸릴 수 있습니다

---

## Claude Code 사용 방법

이 프로젝트는 `CLAUDE.md`의 GSD 컨텍스트를 기반으로 Claude Code와 함께 작업합니다.

```bash
# Claude Code CLI에서 프로젝트 디렉토리 열기
cd d:\blandu_project
claude
```

CLAUDE.md에 정의된 GOAL / SIGNAL / DIRECTION을 Claude가 자동으로 읽고  
코드 수정·확장·디버깅을 일관성 있게 처리합니다.
