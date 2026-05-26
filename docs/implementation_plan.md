# 마네킹 AI 가상 피팅 시스템 구현 계획서

본 계획서는 마네킹 이미지에 상의 및 하의 의류를 피팅하고, 마네킹 고유의 나무 팔 형태를 원본 그대로 보존하기 위한 Gradio 기반 로컬 애플리케이션 구현 세부 방안을 제시합니다.

## 사용자 검토 필요 사항

> [!IMPORTANT]
> **GPU 환경 제한 사항**: 현재 개발 환경은 CPU 전용 Python 환경(`CUDA available: False`)입니다. 따라서 애플리케이션은 이미지 합성, 배경 제거, 색상 기반 팔 마스킹을 수행하는 **하이브리드 엔진 (클래식 OpenCV/Pillow)**을 기본값으로 사용하도록 구성됩니다. GPU 가속이 가능한 머신에서 실행할 때 활성화할 수 있는 **AI 피팅 엔진 (IDM-VTON)**의 코드 구조 및 모델 설정도 함께 구현됩니다.

> [!NOTE]
> 의류 이미지의 배경을 제거하기 위해 `rembg` 라이브러리를 활용하거나, 네트워크 연결이 없는 환경을 대비해 흰색 색상값을 투명하게 처리하는 자체 폴백 알고리즘을 사용합니다. 마네킹의 나무 팔 영역은 HSV 색상 영역 임계값 필터링을 사용하여 정밀하게 분할한 뒤 옷 위에 얹어지도록 처리합니다.

## 제안된 변경 사항

다음과 같은 구조로 프로젝트를 구성합니다.
- `tryon_engine.py`: 배경 제거, 팔 영역 분할, 크기 조절 및 합성 기능 담당 (CPU 하이브리드 엔진 및 AI 모델 템플릿 포함)
- `app.py`: Gradio 기반 웹 사용자 인터페이스 (GUI)
- `requirements.txt`: 프로젝트 의존성 라이브러리 목록

---

### 구성 컴포넌트

#### [NEW] [tryon_engine.py](file:///d:/blandu_project/tryon_engine.py)
이 모듈은 다음 기능을 포함합니다:
- `remove_background(img)`: `rembg`를 사용해 의류 배경을 제거하며, 실패 시 흰색 배경 투명화 처리로 폴백합니다.
- `segment_arms(mannequin_img)`: HSV 색상 영역을 분석하여 마네킹의 나무 팔 영역을 검출하고 이진 마스크를 생성합니다.
- `fit_clothing_hybrid(...)`: 상/하의 크기 및 위치 조정(Scale/Translation)을 처리하고 팔 마스크를 오버레이하여 최종 이미지를 합성합니다.
- `fit_clothing_ai(...)`: IDM-VTON을 구동하기 위한 PyTorch/Diffusers 기반 구현 템 템플릿입니다.

#### [NEW] [app.py](file:///d:/blandu_project/app.py)
이 모듈은 Gradio 인터페이스를 제공합니다:
- 마네킹, 상의, 하의 이미지 업로드 기능.
- 피팅 모드(전체, 상의만, 하의만) 및 엔진 선택(하이브리드 vs AI) 옵션 제공.
- 실시간 결과물 이미지 미리보기 및 다운로드 기능.

#### [NEW] [requirements.txt](file:///d:/blandu_project/requirements.txt)
- 프로젝트 실행에 필요한 패키지 목록: `gradio`, `opencv-python`, `pillow`, `numpy`, `rembg`

---

## 검증 계획

### 자동화 테스트
- `tryon_engine.py`를 테스트 모드로 실행하여 샘플 이미지(`마네킨6.png`, `ITEM-001.png`, `ITEM-002.png`)를 병합하고 최종 합성 결과물이 생성되는지 확인합니다.
- HSV 마스킹 함수가 나무 팔 영역을 정확히 검출하는지 시각화 테스트합니다.

### 수동 검증
- `python app.py` 명령어로 웹서버를 실행하고 브라우저로 접속하여 이미지 업로드 및 피팅 작동 여부를 확인합니다.
