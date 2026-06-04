from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os

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
