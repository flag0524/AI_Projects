@echo off
echo [마네킹 피팅 시스템] 백엔드 서버 시작...
cd /d D:\blandu_project
pip install -r backend\requirements.txt
python -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
pause
