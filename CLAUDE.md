# BLANCDEW Mannequin Styler (BMS) — Claude Code Context

## GOAL

블랑듀(Blancdew) 여성복 브랜드의 스마트폰 촬영 상품 이미지를 **마네킹 착장 이미지**로
자동 변환하는 파이프라인을 구축한다.

타겟: 30~40대 여성 고객  
목적: 온라인 쇼핑몰·룩북·카탈로그용 상품 이미지 생산 자동화

### 핵심 요구사항
1. 원본 이미지 픽셀을 **절대 변형하지 않는다** — 색상, 질감, 패턴, 봉제선 100% 보존
2. **생성형 AI(DALL-E, Midjourney, Stable Diffusion 등)를 이미지 합성에 사용하지 않는다**
3. 코디 일련번호(C001~Cnnn)를 기준으로 세트 이미지를 구성한다
4. 4가지 연출 프리셋(단품/코디/룩북/카탈로그)을 지원한다
5. 처리된 모든 작업은 로그에 기록한다

---

## SIGNAL

### 입력 데이터 구조

```
input/
  raw_photos/         ← 스마트폰 촬영 원본 (품번.jpg 형식)
    BLD-2401.jpg
    BLD-2402.jpg
    ...

  codi_sets/          ← 코디 세트 폴더 (코디번호/품번.jpg 형식)
    C001/
      BLD-2401.jpg    ← 상의
      BLD-2405.jpg    ← 하의
    C002/
      ...

  product_data.xlsx   ← 품번, 품명, 카테고리, 최초판매가, 색상, 시즌, 코디그룹
```

### 엑셀 컬럼 구조

| 컬럼 | 타입 | 설명 |
|------|------|------|
| 품번 | String | 파일명과 동일 (예: BLD-2401) |
| 품명 | String | 상품명 |
| 카테고리 | String | 아우터/상의/하의/원피스 — 착장 레이어 순서 결정 |
| 최초판매가 | Integer | 카탈로그 워터마크용 |
| 색상 | String | 참고 정보 |
| 시즌 | String | 참고 정보 |
| 코디그룹 | String | 쉼표 구분 다중 허용 (예: C001,C003) |

### 마네킹 템플릿

```
templates/
  mannequin_front.png   ← 전면 (투명 배경 PNG)
  mannequin_side.png    ← 측면
  mannequin_back.png    ← 후면
  backgrounds/
    bg_white.png
    bg_studio.png
    bg_lifestyle.jpg
```

### 좌표 및 프리셋 스펙

```
specs/
  mannequin_zones.json  ← 카테고리별 착장 영역 좌표 (bbox, anchor, pivot)
  render_presets.json   ← 연출 프리셋 4종 정의
```

---

## DIRECTION

### 코드 작성 원칙

1. **이미지 합성 시 원본 픽셀을 그대로 사용** — 리사이즈(LANCZOS)만 허용, 색상 보정 금지
2. **배경 제거는 rembg 라이브러리만 사용** — 외부 API 호출 금지
3. **생성형 AI API 호출 코드를 작성하지 않는다** (OpenAI, Anthropic 이미지 생성 API 포함)
4. 카테고리별 착장 레이어 순서: `원피스/dress` → 또는 `하의 → 상의 → 아우터` (하→상 순)
5. 좌표 값은 `specs/mannequin_zones.json`에서만 읽는다 — 하드코딩 금지
6. 설정 값은 `src/config.py`에서만 읽는다

### 파일명 규칙

```
원본 입력:  [품번].jpg                          → BLD-2401.jpg
단품 출력:  [품번]_[프리셋ID]_[YYYYMMDD].jpg    → BLD-2401_single_front_20240512.jpg
코디 출력:  [코디번호]_[프리셋ID]_[YYYYMMDD].jpg → C001_codi_full_20240512.jpg
```

### 오류 처리 규칙

- 엑셀에 없는 품번 파일 → WARNING 로그 기록 후 건너뜀 (중단하지 않음)
- 배경 제거 실패 → ERROR 로그 기록 후 해당 이미지 건너뜀
- 마네킹 템플릿 없음 → 프로그램 시작 시 즉시 중단 (CRITICAL)
- 출력 폴더 없음 → 자동 생성

### 로그 형식 (JSONL)

```jsonl
{"ts": "2024-05-12T14:30:00", "level": "INFO", "item": "BLD-2401", "preset": "single_front", "status": "ok", "output": "output/single/BLD-2401_single_front_20240512.jpg"}
{"ts": "2024-05-12T14:30:01", "level": "WARNING", "item": "BLD-9999", "reason": "not_in_excel"}
```

### CLI 사용법

```bash
# 단품 처리
python src/main.py run --item BLD-2401 --preset single_front

# 코디 세트 처리
python src/main.py run --codi C001 --preset codi_full

# 전체 일괄 처리
python src/main.py run --all --preset single_front

# 가능한 프리셋 목록 확인
python src/main.py presets

# 처리 결과 요약 확인
python src/main.py report
```

---

## 프로젝트 구조 참고

```
d:\blandu_project\
├── CLAUDE.md                ← 이 파일 (GSD 컨텍스트)
├── requirements.txt
├── input\
│   ├── raw_photos\          ← 원본 이미지
│   ├── codi_sets\           ← 코디 세트
│   └── product_data.xlsx
├── templates\               ← 마네킹 PNG 템플릿
│   └── backgrounds\
├── output\
│   ├── single\
│   ├── codi\
│   ├── lookbook\
│   └── catalog\
├── src\
│   ├── main.py
│   ├── config.py
│   ├── bg_remover.py
│   ├── composer.py
│   ├── codi_mapper.py
│   ├── excel_reader.py
│   └── layout_engine.py
├── specs\
│   ├── mannequin_zones.json
│   └── render_presets.json
└── logs\
    └── process_log.jsonl
```
