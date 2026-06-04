@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ===== AI 마네킹 핏 시스템 시작 =====
echo.

set "PY=python"
where python >nul 2>nul || set "PY=py -3"

cd /d "%~dp0backend"
if not exist ".venv\Scripts\python.exe" %PY% -m venv .venv
set "VPY=.venv\Scripts\python.exe"

echo [백엔드] 패키지 설치/확인 중... (최초 1회 수 분 소요)
"%VPY%" -m pip install --upgrade pip -q
"%VPY%" -m pip install fastapi uvicorn[standard] aiofiles python-multipart pydantic pydantic-settings loguru pillow numpy opencv-python-headless scipy scikit-image rembg onnxruntime -q

echo [백엔드] FastAPI 서버 시작 (포트 8000)...
start "Backend" cmd /k ""%VPY%" -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload"

cd /d "%~dp0frontend"
echo [프론트] 의존성 설치 + 개발 서버 시작 (포트 3000)...
start "Frontend" cmd /k "npm install && npm run dev"

echo.
echo ============================================
echo   브라우저:  http://localhost:3000
echo   API 문서:  http://localhost:8000/docs
echo ============================================
echo  - CPU(Tier 3) 모드, Redis 불필요(인프로세스).
echo  - 종료하려면 Backend / Frontend 창을 닫으세요.
pause
