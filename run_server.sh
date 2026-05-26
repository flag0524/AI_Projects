#!/bin/bash

# 마네킹 AI 가상 피팅 시스템 - 로컬 웹 서버 (Linux/Mac)

cd "$(dirname "$0")"

echo ""
echo "============================================================"
echo "마네킹 AI 가상 피팅 시스템 - 로컬 서버 시작"
echo "============================================================"
echo ""

# Python 설치 확인
if ! command -v python3 &> /dev/null; then
    if ! command -v python &> /dev/null; then
        echo "❌ Python이 설치되지 않았습니다."
        echo ""
        echo "설치 방법:"
        echo "  - Ubuntu/Debian: sudo apt-get install python3"
        echo "  - macOS: brew install python3"
        echo "  - CentOS: sudo yum install python3"
        exit 1
    fi
    PYTHON_CMD="python"
else
    PYTHON_CMD="python3"
fi

echo "📂 디렉토리: $(pwd)"
echo "🌐 URL: http://127.0.0.1:7860/virtual_fitting_system.html"
echo "🔌 포트: 7860"
echo ""
echo "💡 팁:"
echo "   - 브라우저에서 위의 URL을 열기"
echo "   - Ctrl+C를 눌러 서버 종료"
echo ""
echo "============================================================"
echo ""

# Python 서버 실행
$PYTHON_CMD run_local_server.py
