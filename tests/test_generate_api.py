"""generate API 테스트 — 비동기 job 모델 + status 플래그."""
import time

import pytest
from PIL import Image
from starlette.testclient import TestClient

from backend.api import generate as gen_api
from backend.pipeline import higgsfield_provider as hgf
from backend.pipeline import hf_provider as hf
from backend.pipeline import generative_provider as gen


@pytest.fixture
def app():
    from fastapi import FastAPI
    a = FastAPI()
    a.include_router(gen_api.router, prefix="/api/v1")
    return a


@pytest.fixture
def client(app):
    return TestClient(app)


def _files(png_bytes):
    return [("garment_images", ("top.png", png_bytes, "image/png"))]


def _poll(client, job_id, tries=40):
    for _ in range(tries):
        r = client.get(f"/api/v1/generate/result/{job_id}")
        if r.status_code != 200 or r.json().get("status") != "processing":
            return r
        time.sleep(0.05)
    return r


# ── POST → job_id (202) ───────────────────────────────────────
def test_post_returns_job_id(monkeypatch, client, png_bytes):
    monkeypatch.setattr(gen_api, "generate_model_shot",
                        lambda **k: (Image.new("RGB", (8, 8)), "higgsfield"))
    r = client.post("/api/v1/generate",
                    files=_files(png_bytes), data={"garment_types": "top"})
    assert r.status_code == 202
    assert "job_id" in r.json()
    assert r.json()["status"] == "processing"


# ── GET result → completed ────────────────────────────────────
def test_result_completed(monkeypatch, client, png_bytes):
    monkeypatch.setattr(gen_api, "generate_model_shot",
                        lambda **k: (Image.new("RGB", (8, 8)), "higgsfield"))
    job_id = client.post("/api/v1/generate",
                         files=_files(png_bytes), data={"garment_types": "top"}).json()["job_id"]
    r = _poll(client, job_id)
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "completed"
    assert body["method"] == "higgsfield"
    assert body["result_image_base64"]


# ── GET result → 404 unknown job ──────────────────────────────
def test_result_unknown_job(client):
    r = client.get("/api/v1/generate/result/does-not-exist")
    assert r.status_code == 404


# ── 실패 job → 500 / billing → 402 ────────────────────────────
def test_result_billing_402(monkeypatch, client, png_bytes):
    def _bill(**k):
        raise gen.GenerativeBillingError("no credit")
    monkeypatch.setattr(gen_api, "generate_model_shot", _bill)
    job_id = client.post("/api/v1/generate",
                         files=_files(png_bytes), data={"garment_types": "top"}).json()["job_id"]
    r = _poll(client, job_id)
    assert r.status_code == 402


# ── 잘못된 의류 타입 → 422 ────────────────────────────────────
def test_invalid_garment_type(client, png_bytes):
    r = client.post("/api/v1/generate",
                    files=_files(png_bytes), data={"garment_types": "hat"})
    assert r.status_code == 422


# ── status 플래그 ─────────────────────────────────────────────
def test_status_higgsfield_flag(monkeypatch, client):
    monkeypatch.setattr(hgf, "is_available", lambda: True)
    monkeypatch.setattr(hf, "is_available", lambda: False)
    monkeypatch.setattr(gen, "is_available", lambda: False)
    monkeypatch.setenv("GEN_BACKEND", "higgsfield")
    body = client.get("/api/v1/generate/status").json()
    assert body["higgsfield_available"] is True
    assert body["active_backend"] == "higgsfield"
    assert body["generative_available"] is True
