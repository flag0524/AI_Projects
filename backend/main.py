import os

# ── .env 로드 (라우터 import 전에 실행) ────────────────────────
def _load_dotenv():
    """프로젝트 루트의 .env를 읽어 환경변수로 주입 (외부 의존성 없음)."""
    root = os.path.dirname(os.path.dirname(__file__))
    path = os.path.join(root, ".env")
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key, val = key.strip(), val.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = val

_load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.api.fit import router as fit_router
from backend.api.generate import router as generate_router

app = FastAPI(
    title="LaonGEN — 마네킹 피팅 & 모델 컷 생성",
    description="마네킹/옷걸이 제품 사진으로 자연스러운 모델 착용 컷을 생성하는 하이브리드 시스템",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(fit_router, prefix="/api/v1")
app.include_router(generate_router, prefix="/api/v1")

output_dir = os.path.join(os.path.dirname(__file__), "..", "output")
os.makedirs(output_dir, exist_ok=True)


@app.get("/health")
def health():
    return {"status": "ok"}
