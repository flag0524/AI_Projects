@echo off
chcp 65001 >nul
echo.
echo ============================================================
echo 마네킹 AI 가상 피팅 시스템 - 로컬 서버 시작
echo ============================================================
echo.

REM 현재 디렉토리로 이동
cd /d "%~dp0"

REM Python 설치 확인
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python이 설치되지 않았습니다.
    echo.
    echo 해결 방법:
    echo 1. Python 설치: https://www.python.org/downloads/
    echo 2. 설치 시 "Add Python to PATH" 체크
    echo 3. 설치 후 이 파일을 다시 실행하세요.
    echo.
    pause
    exit /b 1
)

echo 📂 디렉토리: %cd%
echo 🌐 URL: http://127.0.0.1:7860/virtual_fitting_system.html
echo 🔌 포트: 7860
echo.
echo 💡 팁:
echo    - 브라우저가 자동으로 열립니다.
echo    - Ctrl+C를 눌러 서버 종료
echo.
echo ============================================================
echo.

REM Python 서버 실행
python run_local_server.py

pause
