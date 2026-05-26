# 👔 마네킹 AI 가상 피팅 시스템

고급 배경 제거 및 자동 맞춤 기능을 가진 웹 기반 가상 피팅 시스템입니다.

## 🚀 빠른 시작

### Windows - 가장 간단한 방법 ✨
```bash
# 1. 폴더: D:\blandu_project
# 2. run_server.bat 더블클릭 하기
# 3. 자동으로 브라우저에서 열림!
```

### Linux / macOS
```bash
cd /path/to/blandu_project
chmod +x run_server.sh
./run_server.sh
```

### 수동 실행
```bash
python run_local_server.py
# 브라우저에서 열기: http://127.0.0.1:7860/virtual_fitting_system.html
```

## 📋 시스템 요구사항

- **Python 3.6+** (자동 로컬 서버용)
- **최신 웹 브라우저** (Chrome, Firefox, Safari, Edge)
- **1024×768 이상 화면 해상도**

## 🎯 주요 기능

### ✅ 마네킹 업로드
- PNG, JPG, GIF 등 모든 이미지 형식 지원
- 자동 크기 감지 (고해상도 지원)

### ✅ 의류 이미지 업로드  
- **자동 배경 제거** (CIE 알고리즘)
- 상의, 하의, 원피스 3가지 카테고리

### ✅ 정밀한 조정
- **슬라이더** 제어 (X, Y, Scale)
- **직접 입력** - 정확한 픽셀값 입력
- **빠른 프리셋** (초기화, 중앙 정렬, 자동 맞춤)

### ✅ 고품질 다운로드
- 원본 마네킹 크기로 저장
- PNG 형식 (투명도 유지)

## 💡 사용 방법

1. **마네킹 이미지 업로드** ← 필수
2. **카테고리 선택** (일반의류/원피스)
3. **의류 이미지 업로드**
4. **필요시 미세 조정**
5. **결과 다운로드**

## 🔧 기술 정보

- **배경 제거**: CIE 색상 거리 + 선형 보간
- **이미지 합성**: 6단계 레이어링 (Canvas API)
- **최대 지원 크기**: 10,000×10,000px
- **파일 크기 제한**: 50MB

## 📂 주요 파일

```
D:\blandu_project\
├── virtual_fitting_system.html      ← 메인 애플리케이션
├── run_server.bat                   ← Windows 실행 (더블클릭)
├── run_server.sh                    ← Linux/Mac 실행
├── run_local_server.py              ← Python 서버
└── input/raw_photos/                ← 원본 이미지 폴더
```

## 🐛 문제 해결

### Python이 없을 때
- https://www.python.org/downloads/ 에서 설치
- 설치 시 "Add Python to PATH" 체크

### 포트 7860이 이미 사용 중
- 다른 프로그램 종료하기
- 또는 브라우저에서 직접 HTML 파일 열기

### 배경 제거가 정확하지 않음
- 배경을 더 단색으로 만들기
- 조명 개선하기

## 📝 Blandu Project

This is the main repository for the Blandu project.
