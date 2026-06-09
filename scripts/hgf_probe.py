"""Higgsfield REST 라이브 프로브 — 인증/엔드포인트 유효성 + try-on 매핑 확인.

키를 in-process로만 주입 (영구 저장 안 함). 실제 외부 호출.
"""
import os
import sys
from pathlib import Path

KEY = sys.argv[1] if len(sys.argv) > 1 else ""
os.environ["HIGGSFIELD_API_KEY"] = KEY

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import httpx

BASE = "https://api.higgsfield.ai"
H = {"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}

print("== 1) 가벼운 인증 프로브: POST /v1/generations (최소 payload) ==")
try:
    r = httpx.post(f"{BASE}/v1/generations", headers=H,
                   json={"task": "text-to-image", "model": "nano-banana-pro",
                         "prompt": "ping", "width": 256, "height": 256},
                   timeout=30)
    print("status:", r.status_code)
    print("body  :", r.text[:1500])
except Exception as e:
    print("ERROR:", type(e).__name__, e)
