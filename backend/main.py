from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os

from backend.api.fit import router as fit_router

app = FastAPI(
    title="마네킹 피팅 시스템",
    description="마네킹 이미지에 의류를 자연스럽게 합성하는 가상 피팅 API",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(fit_router, prefix="/api/v1")

output_dir = os.path.join(os.path.dirname(__file__), "..", "output")
os.makedirs(output_dir, exist_ok=True)


@app.get("/health")
def health():
    return {"status": "ok"}
