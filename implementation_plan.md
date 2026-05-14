# 블랑듀 (Blancdew) — 마네킹 착장 이미지 생성기 기획안

> **브랜드**: 블랑듀 (Blancdew) | 여성복 | 30~40대 타겟  
> **프로젝트명**: BLANCDEW Mannequin Styler (BMS)  
> **개발 환경**: Claude Code (CLI) + Python  
> **컨텍스트 엔지니어링**: GSD (Goal → Signal → Direction) 방식 적용

---

## 🎯 프로젝트 핵심 목표

| 목표 | 설명 |
|------|------|
| **이미지 충실도 유지** | 촬영한 상품 원본 이미지의 디테일(색상·질감·패턴·봉제선)을 **절대 변형하지 않음** |
| **코디 자동화** | 품번 + 코디 일련번호 기반으로 세트 코디 이미지를 자동 합성 |
| **다양한 연출** | 단품 / 코디 세트 / 배경 연출 / 룩북 레이아웃 등 다중 출력 형식 지원 |
| **Claude Code 기반** | AI 오케스트레이션 + 이미지 합성 파이프라인을 Claude Code로 완전 자동화 |

---

## ⚠️ 핵심 기술 제약 — "이미지 디테일 불변 원칙"

> [!CAUTION]
> ChatGPT, DALL-E, Midjourney 등의 **생성형 AI 이미지 합성을 절대 사용하지 않습니다.**  
> 이유: 생성형 AI는 매번 픽셀 단위로 결과물이 달라져 상품 디테일이 왜곡됩니다.

### ✅ 채택 방식: 픽셀 레벨 이미지 합성 (Compositing)

```
원본 촬영 이미지 → 배경 제거(Rembg) → 마네킹 템플릿 위 합성(Pillow/OpenCV)
                     ↑                       ↑
              100% 픽셀 보존             위치·크기 조정만
```

- **배경 제거**: `rembg` 라이브러리 (딥러닝 기반, 경계선 정밀 처리)
- **합성 엔진**: `Pillow` + `OpenCV` (픽셀 합성, 색상 보정 없음)
- **AI 역할**: Claude는 이미지를 **생성하지 않고**, 워크플로 오케스트레이션 + 품번/코디 매핑만 담당

---

## 📁 폴더 구조 설계

```
d:\blandu_project\
│
├── CLAUDE.md                    ← Claude Code 프로젝트 컨텍스트 (GSD 핵심)
│
├── input\
│   ├── raw_photos\              ← 스마트폰 촬영 원본 이미지
│   │   ├── BLD-2401.jpg         ← 품번 기반 파일명
│   │   ├── BLD-2402.jpg
│   │   └── ...
│   ├── codi_sets\               ← 코디 세트 폴더
│   │   ├── C001\                ← 코디 일련번호
│   │   │   ├── BLD-2401.jpg
│   │   │   └── BLD-2405.jpg
│   │   ├── C002\
│   │   └── ...
│   └── product_data.xlsx        ← 품번 + 최초판매가 데이터
│
├── templates\
│   ├── mannequin_front.png      ← 마네킹 템플릿 (전면, 배경 없음)
│   ├── mannequin_side.png       ← 마네킹 템플릿 (측면)
│   ├── mannequin_back.png       ← 마네킹 템플릿 (후면)
│   └── backgrounds\
│       ├── bg_white.png
│       ├── bg_studio.png
│       └── bg_lifestyle.jpg
│
├── output\
│   ├── single\                  ← 단품 마네킹 이미지
│   │   ├── BLD-2401_front.jpg
│   │   └── BLD-2401_back.jpg
│   ├── codi\                    ← 코디 세트 이미지
│   │   ├── C001_full.jpg
│   │   └── C002_full.jpg
│   ├── lookbook\                ← 룩북 레이아웃 (다중 컷)
│   └── catalog\                 ← 카탈로그용 (품번+가격 워터마크)
│
├── src\
│   ├── main.py                  ← 메인 실행 파일
│   ├── bg_remover.py            ← 배경 제거 모듈
│   ├── composer.py              ← 이미지 합성 모듈
│   ├── codi_mapper.py           ← 코디 세트 매핑 모듈
│   ├── excel_reader.py          ← 엑셀 데이터 파싱
│   ├── layout_engine.py         ← 다양한 레이아웃 생성
│   └── config.py                ← 설정값 중앙 관리
│
├── specs\
│   ├── mannequin_zones.json     ← 마네킹 착장 영역 좌표 정의
│   └── render_presets.json      ← 연출 프리셋 정의
│
└── logs\
    └── process_log.jsonl        ← 처리 이력 로그
```

---

## 📊 엑셀 데이터 스키마 (`product_data.xlsx`)

| 컬럼명 | 타입 | 예시 | 설명 |
|--------|------|------|------|
| `품번` | String | BLD-2401 | 파일명과 동일하게 매핑 |
| `품명` | String | 린넨 재킷 | 상품명 |
| `카테고리` | String | 아우터 | 착장 레이어 결정에 사용 |
| `최초판매가` | Integer | 89000 | 카탈로그 출력용 |
| `색상` | String | 아이보리 | 색상 태그 |
| `시즌` | String | 2024SS | 시즌 분류 |
| `코디그룹` | String | C001 | 코디 일련번호 (복수 가능, 쉼표 구분) |

---

## 🧠 GSD 컨텍스트 엔지니어링 설계

### CLAUDE.md 전체 구조

```
GOAL (목표)
  └─ 이 프로젝트가 무엇을 달성하려 하는가

SIGNAL (신호/데이터 구조)  
  └─ 어떤 입력 데이터가 존재하고 어떤 구조를 갖는가

DIRECTION (방향/규칙)
  └─ Claude가 반드시 따라야 할 원칙과 제약
```

### GOAL 섹션 예시

```markdown
## GOAL
블랑듀(Blancdew) 여성복 브랜드의 상품 이미지를 마네킹 착장 이미지로
자동 변환하는 파이프라인을 구축한다.

핵심 요구사항:
- 원본 이미지 픽셀을 절대 변형하지 않는다
- 생성형 AI(DALL-E, Midjourney 등)를 이미지 합성에 사용하지 않는다
- 코디 일련번호(C001~Cnnn)를 기준으로 세트 이미지를 구성한다
```

### SIGNAL 섹션 예시

```markdown
## SIGNAL
- input/raw_photos/ : 품번.jpg 형식의 상품 원본 이미지
- input/codi_sets/  : 코디번호 폴더 → 해당 품번 이미지들
- input/product_data.xlsx : 품번, 최초판매가, 카테고리 매핑
- templates/        : 마네킹 PNG 템플릿 (투명 배경)
- specs/mannequin_zones.json : 상의/하의/아우터 착장 좌표
```

### DIRECTION 섹션 예시

```markdown
## DIRECTION
1. 이미지 합성 시 원본 픽셀을 그대로 사용 (리사이즈만 허용)
2. 배경 제거는 rembg 라이브러리만 사용
3. 생성형 AI API 호출 코드를 작성하지 않는다
4. 출력 파일명 규칙: [품번 또는 코디번호]_[연출타입]_[날짜].jpg
5. 모든 처리 결과는 logs/process_log.jsonl에 기록
6. 엑셀 데이터가 없는 품번은 WARNING 로그 후 건너뜀
```

---

## 🔧 핵심 기술 스택

| 역할 | 라이브러리 | 이유 |
|------|-----------|------|
| 배경 제거 | `rembg` | 정밀한 의류 경계 추출, 로컬 실행 |
| 이미지 합성 | `Pillow (PIL)` | 픽셀 레벨 합성, 원본 보존 |
| 이미지 처리 | `OpenCV` | 마스크 정밀화, 경계 블렌딩 |
| 엑셀 파싱 | `openpyxl` | product_data.xlsx 읽기 |
| 설정 관리 | `pydantic` | 타입 안전한 설정 |
| CLI 인터페이스 | `typer` | Claude Code 명령어 연동 |
| 로깅 | `loguru` | JSONL 구조화 로그 |

---

## 🎨 연출(렌더) 프리셋 종류

```json
// specs/render_presets.json
{
  "presets": [
    {
      "id": "single_front",
      "name": "단품 정면",
      "description": "단일 상품 마네킹 정면 착장",
      "mannequin": "front",
      "background": "white",
      "output_size": [800, 1200],
      "watermark": false
    },
    {
      "id": "codi_full",
      "name": "코디 전체",
      "description": "코디 세트 전체 착장 (상하의 포함)",
      "mannequin": "front",
      "background": "studio",
      "output_size": [800, 1200],
      "watermark": false
    },
    {
      "id": "lookbook_2col",
      "name": "룩북 2열",
      "description": "2개 코디를 나란히 배치한 룩북",
      "layout": "2column",
      "background": "lifestyle",
      "output_size": [1600, 1200]
    },
    {
      "id": "catalog_card",
      "name": "카탈로그 카드",
      "description": "품번 + 최초판매가 워터마크 포함",
      "mannequin": "front",
      "background": "white",
      "watermark": true,
      "output_size": [800, 1100]
    }
  ]
}
```

---

## 🏗️ Claude Code 구현 단계 (Phase Plan)

### Phase 1 — 기반 환경 구축 (1~2일)
- [ ] `d:\blandu_project` 폴더 구조 생성
- [ ] Python 가상환경 + 라이브러리 설치
- [ ] `CLAUDE.md` GSD 컨텍스트 문서 작성
- [ ] `config.py` 경로·설정값 정의
- [ ] `specs/mannequin_zones.json` 좌표 정의

### Phase 2 — 데이터 파이프라인 (2~3일)
- [ ] `excel_reader.py`: product_data.xlsx 파싱 + 유효성 검사
- [ ] `codi_mapper.py`: 코디 폴더 스캔 → 품번-코디번호 매핑 딕셔너리
- [ ] 파일명 규칙 검증기 (품번 패턴 BLD-XXXX 체크)

### Phase 3 — 이미지 처리 엔진 (3~4일)
- [ ] `bg_remover.py`: rembg 배경 제거 + 마스크 정밀화
- [ ] `composer.py`: 마네킹 템플릿 위 의류 합성
  - 카테고리별 착장 레이어 순서 (속옷 → 하의 → 상의 → 아우터)
  - 리사이즈 + 위치 조정 (좌표는 mannequin_zones.json 참조)
- [ ] `layout_engine.py`: 단품 / 코디 / 룩북 / 카탈로그 레이아웃

### Phase 4 — CLI 인터페이스 + 로깅 (1~2일)
- [ ] `main.py`: typer 기반 CLI 명령어 구현
  ```
  python main.py run --codi C001 --preset codi_full
  python main.py run --all --preset single_front
  python main.py run --item BLD-2401 --preset catalog_card
  ```
- [ ] 처리 진행률 표시 (tqdm)
- [ ] `logs/process_log.jsonl` 기록

### Phase 5 — 검증 + 품질 개선 (2~3일)
- [ ] 배경 제거 품질 테스트 (의류 소재별: 니트, 시폰, 데님)
- [ ] 마네킹 합성 위치 미세 조정
- [ ] 일괄 처리 80장 테스트 실행
- [ ] 출력 이미지 품질 리뷰

---

## 📋 마네킹 착장 좌표 정의 방식

```json
// specs/mannequin_zones.json
{
  "mannequin_size": [800, 1200],
  "zones": {
    "top": {
      "anchor": "shoulder",
      "bbox": [150, 80, 650, 520],
      "pivot": "top_center"
    },
    "bottom": {
      "anchor": "waist",
      "bbox": [200, 500, 600, 1100],
      "pivot": "top_center"
    },
    "outer": {
      "anchor": "shoulder",
      "bbox": [120, 70, 680, 540],
      "pivot": "top_center",
      "layer": "top"
    },
    "dress": {
      "anchor": "shoulder",
      "bbox": [150, 80, 650, 1100],
      "pivot": "top_center"
    }
  }
}
```

---

## 📌 파일명 명명 규칙 정의

### 원본 이미지 파일명
```
[품번].jpg
예) BLD-2401.jpg, BLD-2402.jpg
```

### 코디 세트 폴더명
```
input/codi_sets/[코디일련번호]/
예) input/codi_sets/C001/   ← BLD-2401.jpg + BLD-2405.jpg 포함
```

### 출력 이미지 파일명
```
[품번 또는 코디번호]_[프리셋ID]_[YYYYMMDD].jpg
예) BLD-2401_single_front_20240512.jpg
    C001_codi_full_20240512.jpg
    C001_lookbook_2col_20240512.jpg
```

---

## 🔍 검증 계획

### 자동 검증
- `rembg` 배경 제거 후 알파채널 픽셀 커버리지 체크 (≥90%)
- 출력 이미지 해상도 확인 (프리셋 사이즈와 일치 여부)
- 엑셀 품번 ↔ 파일명 100% 매핑 검증 리포트 출력

### 수동 검증
- 배경 제거 샘플 10장 육안 확인 (특히 레이스·쉬폰·투명 소재)
- 마네킹 착장 자연스러움 확인
- 코디 세트 상하의 레이어 순서 확인

---

## ❓ 사용자 확인이 필요한 사항

> [!IMPORTANT]
> **마네킹 템플릿 준비**: 마네킹 PNG 파일(투명 배경)을 직접 준비하셔야 합니다.  
> 또는 저작권 없는 마네킹 이미지를 구매하거나, 실물 마네킹 촬영 후 배경 제거하여 사용.

> [!IMPORTANT]
> **품번 형식 확인**: 예시로 `BLD-2401` 형식을 사용했습니다.  
> 실제 품번 형식이 다르면 알려주세요 (예: `BD24-001`, `2024W-001` 등).

> [!NOTE]
> **Phase 1부터 순차적으로 진행**: Claude Code 세션에서 CLAUDE.md를 먼저 작성한 후,  
> 각 Phase를 명령어로 지시하는 방식으로 진행합니다.

> [!NOTE]
> **rembg 로컬 실행**: 인터넷 없이 로컬에서 완전 동작합니다.  
> 첫 실행 시 AI 모델 다운로드(약 200MB)가 필요합니다.
