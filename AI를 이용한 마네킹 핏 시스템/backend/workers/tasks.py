"""
Celery 작업 정의.

작업 진행 상태는 Redis에 직접 기록 (Celery meta + 커스텀 키).
API 서버는 /api/v1/tryon/{job_id} 로 상태를 폴링.
"""
from __future__ import annotations
import json
from pathlib import Path

from celery import current_task
from loguru import logger

from workers.celery_app import celery_app
from config import settings
from schemas import (
    Category, FitMode, GarmentSize, FitReport, JobStatus, ResultItem,
)


def _set_progress(job_id: str, step: str, pct: int):
    """Redis에 세부 진행 상태 기록 (폴링 시 progress 필드로 반환)."""
    current_task.update_state(
        state="PROGRESS",
        meta={"job_id": job_id, "step": step, "progress": pct},
    )
    logger.info(f"[{job_id}] {step} ({pct}%)")


@celery_app.task(bind=True, name="workers.tasks.tryon_task")
def tryon_task(
    self,
    job_id: str,
    mannequin_path: str,
    garment_path: str,
    category: str,
    garment_size_json: str | None,
    fit_mode: str,
    num_candidates: int,
    remove_background: bool,
    seed: int | None,
    num_steps: int,
    guidance_scale: float,
) -> dict:
    """단일 카테고리 Try-On 작업."""
    try:
        from pipeline.preprocess import preprocess_images
        from pipeline.pose_estimation import estimate_pose
        from pipeline.garment_parsing import parse_garment
        from pipeline.body_parsing import parse_body, make_agnostic_map
        from pipeline.fit_engine import FitEngine
        from pipeline.engine_selector import get_engine
        from pipeline.postprocess import postprocess
        from PIL import Image

        cat = Category(category)
        fm  = FitMode(fit_mode)
        gs  = GarmentSize(**json.loads(garment_size_json)) if garment_size_json else None
        base_seed = seed or 42

        # 엔진 선택 (config.engine_tier=0 이면 자동 감지)
        tier_override = settings.engine_tier if settings.engine_tier > 0 else None
        model, tier = get_engine(tier_override)
        _set_progress(job_id, f"엔진 준비 (Tier {tier})", 3)

        _set_progress(job_id, "전처리", 5)
        # 1차 포즈 추정(원본) — 전처리의 어깨 수평 정렬용
        mannequin_raw = Image.open(mannequin_path).convert("RGB")
        pose_raw = estimate_pose(mannequin_raw)
        mannequin_img, garment_img, _meta = preprocess_images(
            Path(mannequin_path), Path(garment_path), remove_background, pose_raw
        )

        _set_progress(job_id, "포즈·체형 추정", 20)
        # 2차 포즈 추정 — 전처리된 마네킹 좌표계로 재추정 (엔진 입력과 일치)
        pose_data = estimate_pose(mannequin_img)
        body_data = parse_body(mannequin_img)

        _set_progress(job_id, "의류 파싱", 35)
        garment_data = parse_garment(garment_img, cat)

        _set_progress(job_id, "핏 계산", 45)
        # 악세서리는 핏 엔진 스킵 (사이즈 정합 불필요)
        if cat == Category.accessory:
            from pipeline.fit_engine import FitParams, FitReport
            fit_params = FitParams()
            fit_report = FitReport(fit_label="악세서리", estimated=True)
        else:
            fit_engine = FitEngine(cat)
            fit_params, fit_report = fit_engine.compute(
                gs, pose_data["body_measurements"], fm, pose_data=pose_data)

        agnostic = make_agnostic_map(
            mannequin_img, body_data["masks"], cat.value, pose_data["keypoints"]
        )
        results = []
        step_per = (90 - 50) // max(num_candidates, 1)

        for i in range(num_candidates):
            _set_progress(job_id, f"이미지 생성 ({i+1}/{num_candidates})", 50 + step_per * i)
            s = base_seed + i
            result_img = model.infer(
                mannequin_img=mannequin_img,
                garment_img=garment_img,
                pose_data=pose_data,
                garment_data=garment_data,
                fit_params=fit_params,
                agnostic_map=agnostic,
                seed=s,
                num_steps=num_steps,
                guidance_scale=guidance_scale,
            )

            # 포스트프로세싱 (색감·노이즈·선명도 보정). mask는 전달하지 않음
            # — 엔진이 이미 합성·페더링했고 의류 크기 마스크는 차원 불일치를 유발.
            result_img = postprocess(
                result_img, None, None,
                enable_color_harmony=True, enable_denoise=True,
            )

            result_path = settings.result_dir / f"{job_id}_{i}.png"
            result_img.save(str(result_path))

            results.append(ResultItem(
                image_url=f"/results/{result_path.name}",
                seed=s,
                fit_report=fit_report,
            ).model_dump())

        _set_progress(job_id, "완료", 100)
        return {
            "job_id": job_id,
            "status": JobStatus.succeeded,
            "results": results,
            "error": None,
        }

    except Exception as exc:
        logger.exception(f"[{job_id}] 작업 실패: {exc}")
        self.update_state(state="FAILURE", meta={"exc": str(exc)})
        raise


@celery_app.task(bind=True, name="workers.tasks.layered_task")
def layered_task(
    self,
    job_id: str,
    mannequin_path: str,
    top_path: str,
    bottom_path: str,
    top_size_json: str | None,
    bottom_size_json: str | None,
    fit_mode: str,
    seed: int,
    num_steps: int,
    guidance_scale: float,
    remove_background: bool,
) -> dict:
    """상의 + 하의 레이어링 작업."""
    try:
        from pipeline.layering import run_layered

        _set_progress(job_id, "레이어링 시작", 5)

        top_size    = GarmentSize(**json.loads(top_size_json))    if top_size_json    else None
        bottom_size = GarmentSize(**json.loads(bottom_size_json)) if bottom_size_json else None

        results, report = run_layered(
            mannequin_path=Path(mannequin_path),
            top_path=Path(top_path),
            bottom_path=Path(bottom_path),
            top_size=top_size,
            bottom_size=bottom_size,
            fit_mode=FitMode(fit_mode),
            seed=seed,
            num_steps=num_steps,
            guidance_scale=guidance_scale,
            remove_background=remove_background,
            result_dir=settings.result_dir,
            job_id=job_id,
        )

        _set_progress(job_id, "완료", 100)
        # run_layered가 이미 model_dump()된 dict 리스트를 반환하므로 그대로 사용
        return {
            "job_id": job_id,
            "status": JobStatus.succeeded,
            "results": results,
            "error": None,
        }

    except Exception as exc:
        logger.exception(f"[{job_id}] 레이어링 실패: {exc}")
        self.update_state(state="FAILURE", meta={"exc": str(exc)})
        raise
