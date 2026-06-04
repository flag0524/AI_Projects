"""
AI 마네킹 핏 시스템 — FastAPI 백엔드 (M1)
Celery Worker 없을 때 BackgroundTasks 자동 폴백
"""
import asyncio
import json
import uuid
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, UploadFile, Form, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
import aiofiles
from PIL import Image
from loguru import logger

from config import settings
from schemas import (
    GarmentSize, Category, FitMode,
    JobStatus, JobResponse, FitReport, ResultItem,
)

app = FastAPI(title="AI 마네킹 핏 시스템", version="0.2.1-M1")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/results", StaticFiles(directory=str(settings.result_dir)), name="results")
app.mount("/uploads", StaticFiles(directory=str(settings.upload_dir)), name="uploads")

# 인메모리 Job 저장소 (폴백 모드)
_jobs: dict[str, dict] = {}


# ─────────────────────────────────────────────
# Celery 가용 여부 감지
# ─────────────────────────────────────────────

def _celery_available() -> bool:
    """Celery 사용 가능 여부.

    아래 3가지가 모두 충족될 때만 True (하나라도 안 되면 인프로세스 모드로 폴백):
      1) celery 패키지 설치됨
      2) Redis 포트 연결 가능
      3) 활성 Celery 워커가 응답함
    """
    import socket, re

    # 1) celery 패키지 설치 여부
    try:
        import celery  # noqa: F401
    except Exception:
        return False

    # 2) Redis 포트 연결 가능 여부 (빠른 실패)
    try:
        m = re.search(r'redis://([^:/]+):(\d+)', settings.redis_url)
        host = m.group(1) if m else "localhost"
        port = int(m.group(2)) if m else 6379
        with socket.create_connection((host, port), timeout=0.5):
            pass
    except Exception:
        return False

    # 3) 활성 워커 존재 여부
    try:
        from workers.celery_app import celery_app
        return bool(celery_app.control.ping(timeout=0.5))
    except Exception:
        return False


# ─────────────────────────────────────────────
# 헬퍼
# ─────────────────────────────────────────────

async def save_upload(file: UploadFile, dest_dir: Path) -> Path:
    suffix = Path(file.filename or "image.jpg").suffix.lower()
    if suffix not in {".jpg", ".jpeg", ".png", ".webp"}:
        raise HTTPException(status_code=400, detail=f"지원하지 않는 이미지 형식: {suffix}")
    dest = dest_dir / f"{uuid.uuid4()}{suffix}"
    async with aiofiles.open(dest, "wb") as f:
        content = await file.read()
        if len(content) > settings.max_image_size_mb * 1024 * 1024:
            raise HTTPException(status_code=400, detail="이미지 크기 초과 (최대 20MB)")
        await f.write(content)
    return dest


def _celery_state_to_job(task_result) -> dict:
    state = task_result.state
    if state in ("PENDING", "SENT"):
        return {"job_id": task_result.id, "status": JobStatus.queued,      "results": [], "error": None}
    if state == "STARTED":
        return {"job_id": task_result.id, "status": JobStatus.processing,  "results": [], "error": None}
    if state == "PROGRESS":
        meta = task_result.info or {}
        return {"job_id": task_result.id, "status": JobStatus.processing,  "results": [], "error": None,
                "step": meta.get("step"), "progress": meta.get("progress")}
    if state == "SUCCESS":
        result = task_result.result or {}
        return {"job_id": task_result.id, "status": JobStatus.succeeded,
                "results": result.get("results", []), "error": None}
    if state == "FAILURE":
        err = str(task_result.info) if task_result.info else "알 수 없는 오류"
        return {"job_id": task_result.id, "status": JobStatus.failed,      "results": [], "error": err}
    return     {"job_id": task_result.id, "status": JobStatus.processing,  "results": [], "error": None}


# ─────────────────────────────────────────────
# 폴백: 인프로세스 실행 (Celery 없을 때)
# ─────────────────────────────────────────────

async def _run_inprocess(job_id: str, mannequin_path: Path, garment_path: Path,
                          category: str, gs_dict: Optional[dict],
                          fit_mode: str, num_candidates: int,
                          remove_background: bool, seed: Optional[int]):
    _jobs[job_id] = {"job_id": job_id, "status": JobStatus.processing,
                     "results": [], "error": None, "step": "시작", "progress": 5}
    try:
        from pipeline.preprocess import preprocess_images
        from pipeline.pose_estimation import estimate_pose
        from pipeline.garment_parsing import parse_garment
        from pipeline.body_parsing import parse_body, make_agnostic_map
        from pipeline.fit_engine import FitEngine, FitParams, FitReport
        from pipeline.engine_selector import get_engine
        from pipeline.detail_verification import verify_detail
        from pipeline.postprocess import postprocess

        cat = Category(category)
        fm  = FitMode(fit_mode)
        gs  = GarmentSize(**gs_dict) if gs_dict else None
        base_seed = seed or 42

        tier_override = settings.engine_tier if settings.engine_tier > 0 else None
        model, tier = await asyncio.to_thread(get_engine, tier_override)
        _jobs[job_id].update(step=f"엔진 준비 (Tier {tier})", progress=10)

        # 1차 포즈 추정 (원본) — 전처리의 어깨 수평 정렬에만 사용
        mannequin_raw = await asyncio.to_thread(
            lambda: Image.open(mannequin_path).convert("RGB"))
        pose_raw = await asyncio.to_thread(estimate_pose, mannequin_raw)

        # 포즈 데이터와 함께 전처리 (마네킹이 처리 해상도로 리사이즈됨)
        mannequin_img, garment_img, preprocess_meta = await asyncio.to_thread(
            preprocess_images, mannequin_path, garment_path, remove_background, pose_raw)

        # 2차 포즈 추정 — 전처리된 마네킹 좌표계로 재추정 (엔진 입력과 일치).
        # 리사이즈로 인한 좌표 불일치(의류가 엉뚱한 높이에 배치되는 문제)를 방지.
        pose_data = await asyncio.to_thread(estimate_pose, mannequin_img)
        _jobs[job_id].update(step="포즈·체형 추정", progress=20)

        body_data = await asyncio.to_thread(parse_body, mannequin_img)
        _jobs[job_id].update(step="의류 파싱", progress=35)

        garment_data = await asyncio.to_thread(parse_garment, garment_img, cat)

        if cat == Category.accessory:
            fit_params = FitParams()
            fit_report = FitReport(fit_label="악세서리", estimated=True)
        else:
            fit_engine = FitEngine(cat)
            # 포즈 데이터를 포함하여 동적 핏 계산
            fit_params, fit_report = fit_engine.compute(
                gs, pose_data["body_measurements"], fm, pose_data=pose_data)
        _jobs[job_id].update(step="핏 계산", progress=45)

        agnostic = await asyncio.to_thread(
            make_agnostic_map, mannequin_img, body_data["masks"], cat.value, pose_data["keypoints"])

        results = []
        for i in range(min(num_candidates, settings.max_candidates)):
            _jobs[job_id].update(step=f"이미지 생성 ({i+1}/{num_candidates})", progress=50 + 35 * i // max(num_candidates, 1))
            s = base_seed + i
            result_img = await asyncio.to_thread(
                model.infer,
                mannequin_img=mannequin_img, garment_img=garment_img,
                pose_data=pose_data, garment_data=garment_data,
                fit_params=fit_params, seed=s,
                num_steps=settings.default_num_steps,
                guidance_scale=settings.default_guidance_scale,
                agnostic_map=agnostic,
            )
            
            # 포스트프로세싱 적용 (합성 결과 전체에 색감·노이즈·선명도 보정)
            # mask는 전달하지 않음: 엔진이 이미 의류를 마네킹에 합성·페더링했고,
            # 의류 크기 마스크를 넘기면 차원 불일치/배경 손상이 발생한다.
            result_img = await asyncio.to_thread(
                postprocess,
                result_img,
                None,
                None,
                enable_color_harmony=True,
                enable_denoise=True,
            )
            
            result_path = settings.result_dir / f"{job_id}_{i}.png"
            await asyncio.to_thread(result_img.save, str(result_path))
            results.append(ResultItem(
                image_url=f"/results/{result_path.name}",
                seed=s, fit_report=fit_report,
            ).model_dump())

        _jobs[job_id].update(status=JobStatus.succeeded, results=results,
                              step="완료", progress=100, error=None)
        logger.info(f"[{job_id}] 인프로세스 완료")

    except Exception as e:
        logger.exception(f"[{job_id}] 인프로세스 오류: {e}")
        _jobs[job_id].update(status=JobStatus.failed, error=str(e))



async def _run_layered_inprocess(job_id: str, mannequin_path: Path,
                                  top_path: Path, bottom_path: Path,
                                  top_size_json: Optional[str], bottom_size_json: Optional[str],
                                  fit_mode: str, seed: int, remove_background: bool):
    _jobs[job_id] = {"job_id": job_id, "status": JobStatus.processing,
                     "results": [], "error": None, "step": "레이어링 시작", "progress": 5}
    try:
        from pipeline.layering import run_layered

        top_size    = GarmentSize(**json.loads(top_size_json))    if top_size_json    else None
        bottom_size = GarmentSize(**json.loads(bottom_size_json)) if bottom_size_json else None

        results, report = await asyncio.to_thread(
            run_layered,
            mannequin_path=mannequin_path, top_path=top_path, bottom_path=bottom_path,
            top_size=top_size, bottom_size=bottom_size,
            fit_mode=FitMode(fit_mode), seed=seed,
            num_steps=settings.default_num_steps,
            guidance_scale=settings.default_guidance_scale,
            remove_background=remove_background,
            result_dir=settings.result_dir, job_id=job_id,
        )
        # run_layered가 이미 model_dump()된 dict 리스트를 반환하므로 그대로 사용
        _jobs[job_id].update(status=JobStatus.succeeded,
                              results=results,
                              step="완료", progress=100, error=None)
    except Exception as e:
        logger.exception(f"[{job_id}] 레이어링 오류: {e}")
        _jobs[job_id].update(status=JobStatus.failed, error=str(e))


# ─────────────────────────────────────────────
# 엔드포인트
# ─────────────────────────────────────────────

@app.get("/health")
def health():
    worker_ok = _celery_available()
    try:
        from pipeline.hardware import detect_hardware
        hw = detect_hardware()
    except Exception:
        hw = {}
    return {
        "status": "ok",
        "device": settings.device,
        "engine_tier": settings.engine_tier,
        "worker": worker_ok,
        "mode": "celery" if worker_ok else "inprocess",
        "hardware": hw,
    }


@app.on_event("startup")
def _log_hardware():
    try:
        from pipeline.hardware import log_summary
        log_summary()
    except Exception as e:
        logger.warning(f"하드웨어 요약 로깅 실패: {e}")


@app.post("/api/v1/tryon", status_code=202)
async def create_tryon_job(
    background_tasks: BackgroundTasks,
    mannequin_image: UploadFile = File(...),
    garment_image: UploadFile = File(...),
    category: Category = Form(...),
    garment_size: Optional[str] = Form(None),
    fit_mode: FitMode = Form(FitMode.auto),
    num_candidates: int = Form(1),
    remove_background: bool = Form(False),
    upscale: bool = Form(False),
    seed: Optional[int] = Form(None),
):
    mannequin_path = await save_upload(mannequin_image, settings.upload_dir)
    garment_path   = await save_upload(garment_image,   settings.upload_dir)

    gs_dict = None
    if garment_size:
        try:
            gs_dict = json.loads(garment_size)
            GarmentSize(**gs_dict)
        except Exception:
            raise HTTPException(status_code=400, detail="garment_size JSON 형식 오류")

    job_id = str(uuid.uuid4())

    if _celery_available():
        # Celery 모드
        from workers.tasks import tryon_task
        task = tryon_task.apply_async(
            kwargs={
                "job_id": job_id, "mannequin_path": str(mannequin_path),
                "garment_path": str(garment_path), "category": category.value,
                "garment_size_json": json.dumps(gs_dict) if gs_dict else None,
                "fit_mode": fit_mode.value,
                "num_candidates": min(num_candidates, settings.max_candidates),
                "remove_background": remove_background, "seed": seed,
                "num_steps": settings.default_num_steps,
                "guidance_scale": settings.default_guidance_scale,
            },
            queue="tryon",
        )
        job_id = task.id
        _jobs[job_id] = {"_celery": True}
    else:
        # 인프로세스 폴백
        logger.info(f"[{job_id}] Celery 없음 — 인프로세스 모드로 실행")
        background_tasks.add_task(
            _run_inprocess, job_id, mannequin_path, garment_path,
            category.value, gs_dict, fit_mode.value,
            min(num_candidates, settings.max_candidates),
            remove_background, seed,
        )

    return {"job_id": job_id, "status": "queued"}


@app.get("/api/v1/tryon/{job_id}")
def get_job(job_id: str):
    job = _jobs.get(job_id)

    # Celery 모드
    if job and job.get("_celery"):
        from workers.celery_app import celery_app
        from celery.result import AsyncResult
        return _celery_state_to_job(AsyncResult(job_id, app=celery_app))

    # 인프로세스 모드
    if job:
        return job

    # Celery에서 조회 시도 (worker가 나중에 붙은 경우)
    try:
        from workers.celery_app import celery_app
        from celery.result import AsyncResult
        return _celery_state_to_job(AsyncResult(job_id, app=celery_app))
    except Exception:
        raise HTTPException(status_code=404, detail="Job을 찾을 수 없습니다.")


@app.post("/api/v1/tryon/layered", status_code=202)
async def create_layered_job(
    background_tasks: BackgroundTasks,
    mannequin_image: UploadFile = File(...),
    top_image: UploadFile = File(...),
    bottom_image: UploadFile = File(...),
    top_size: Optional[str] = Form(None),
    bottom_size: Optional[str] = Form(None),
    fit_mode: FitMode = Form(FitMode.auto),
    remove_background: bool = Form(False),
    seed: Optional[int] = Form(None),
):
    mannequin_path = await save_upload(mannequin_image, settings.upload_dir)
    top_path       = await save_upload(top_image,       settings.upload_dir)
    bottom_path    = await save_upload(bottom_image,    settings.upload_dir)

    job_id = str(uuid.uuid4())

    if _celery_available():
        from workers.tasks import layered_task
        task = layered_task.apply_async(
            kwargs={
                "job_id": job_id, "mannequin_path": str(mannequin_path),
                "top_path": str(top_path), "bottom_path": str(bottom_path),
                "top_size_json": top_size, "bottom_size_json": bottom_size,
                "fit_mode": fit_mode.value, "seed": seed or 42,
                "num_steps": settings.default_num_steps,
                "guidance_scale": settings.default_guidance_scale,
                "remove_background": remove_background,
            },
            queue="tryon",
        )
        job_id = task.id
        _jobs[job_id] = {"_celery": True}
    else:
        logger.info(f"[{job_id}] 레이어링 인프로세스 모드")
        background_tasks.add_task(
            _run_layered_inprocess, job_id, mannequin_path, top_path, bottom_path,
            top_size, bottom_size, fit_mode.value, seed or 42, remove_background,
        )

    return {"job_id": job_id, "status": "queued"}


@app.delete("/api/v1/tryon/{job_id}")
def cancel_job(job_id: str):
    if job_id in _jobs:
        _jobs[job_id]["status"] = JobStatus.failed
        _jobs[job_id]["error"] = "사용자 취소"
    try:
        from workers.celery_app import celery_app
        celery_app.control.revoke(job_id, terminate=True, signal="SIGTERM")
    except Exception:
        pass
    return {"job_id": job_id, "cancelled": True}
