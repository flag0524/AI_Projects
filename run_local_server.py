#!/usr/bin/env python3
"""
마네킹 AI 가상 피팅 시스템 - 로컬 웹 서버
포트 7860에서 실행됩니다.
"""

import http.server
import socketserver
import os
import sys
import webbrowser
from pathlib import Path

PORT = 7860
DIRECTORY = str(Path(__file__).parent)

class MyHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

    def end_headers(self):
        # 캐시 방지
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Expires', '0')
        super().end_headers()

    def log_message(self, format, *args):
        # 로그 포맷 개선
        if '200' in str(args) or '304' in str(args):
            # 성공 로그는 간단하게
            sys.stderr.write(f"[✓] {args[0]}\n")
        else:
            # 에러는 강조
            sys.stderr.write(f"[!] {self.client_address[0]} - {format % args}\n")

def run_server():
    try:
        with socketserver.TCPServer(("", PORT), MyHTTPRequestHandler) as httpd:
            print("=" * 60)
            print("🚀 마네킹 AI 가상 피팅 시스템 - 로컬 서버")
            print("=" * 60)
            print(f"\n📂 디렉토리: {DIRECTORY}")
            print(f"🌐 URL: http://127.0.0.1:{PORT}/virtual_fitting_system.html")
            print(f"🔌 포트: {PORT}")
            print("\n💡 팁:")
            print("   - 브라우저에서 위의 URL을 열기")
            print("   - Ctrl+C를 눌러 서버 종료")
            print("\n" + "=" * 60 + "\n")

            # 자동으로 브라우저 열기
            webbrowser.open(f'http://127.0.0.1:{PORT}/virtual_fitting_system.html')

            httpd.serve_forever()
    except OSError as e:
        if e.errno == 48 or e.errno == 98:  # Address already in use
            print(f"❌ 포트 {PORT}가 이미 사용 중입니다.")
            print(f"   다른 프로그램을 종료하거나 다른 포트를 사용하세요.")
        else:
            print(f"❌ 오류: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n\n👋 서버가 종료되었습니다.")
        sys.exit(0)

if __name__ == '__main__':
    run_server()
