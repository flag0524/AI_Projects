"""
LaonGEN 생성 엔드포인트 (비동기 job 모델).

마네킹/옷걸이 제품 사진만으로 자연스러운 모델 착용 컷 생성.

Higgsfield 등 생성형 백엔드는 생성에 30~50초+ 소요되므로(2026-06-08 실측),
동기 HTTP 응답은 프록시·게이트웨이 타임아웃에 걸린다. 따라서 비동기 job 모델:

  POST /api/v1/generate            → {job_id, status:"processing"}
  GET  /api/v1/generate/result/{id} → 진행중/완료/실패

job 상태는 in-memory dict에 보관한다. 제약: **uvicorn 단일 워커 필수**
(`--workers 1`). 멀티워커/재시작 내구성은 NOT in scope (설계 문서 참조).

응답(완료):
  {
    "status": "completed",
    "method": "higgsfield" | "hf" | "generative" | "procedural",
    "result_image_base64": "...",
    "processing_time_ms": 1234
  }
"""
import time
import uuid
import threading
from typing import List, Optional
from fastapi import APIRouter, File, Form, UploadFile, HTTPException
from fastapi.responses import JSONResponse

from backend.utils.image_utils import bytes_to_pil, pil_to_base64
from backend.pipeline.laongen_engine import generate_model_shot
from backend.pipeline import generative_provider as gen

router  = APIRouter()
ALLOWED = {"top", "bottom", "dress", "accessory"}

# ── in-memory job 저장소 (단일 워커 전제) ───────────────────────
# job_id -> {status, method?, result_b64?, processing_time_ms?, error?, billing?}
_JOBS: dict = {}
_JOBS_LOCK = threading.Lock()


def _set_job(job_id: str, **fields):
    with _JOBS_LOCK:
        _JOBS.setdefault(job_id, {}).update(fields)


def _get_job(job_id: str):
    with _JOBS_LOCK:
        job = _JOBS.get(job_id)
        return dict(job) if job else None


@router.get("/generate/status")
def status():
    """생성형 백엔드 가용 여부 확인."""
    from backend.pipeline import hf_provider as hf
    from backend.pipeline import higgsfield_provider as hgf
    import os

    hf_ok   = hf.is_available()
    rep_ok  = gen.is_available()
    hgf_ok  = hgf.is_available()
    backend = os.environ.get("GEN_BACKEND", "hf").strip().lower()

    if backend in ("higgsfield", "auto") and hgf_ok:
        active = "higgsfield"
    elif backend in ("hf", "auto") and hf_ok:
        active = f"huggingface/{hf.HF_SPACE}"
    elif rep_ok:
        active = "replicate/idm-vton"
    else:
        active = "procedural-fallback"

    return {
        "generative_available": hgf_ok or hf_ok or rep_ok,
        "active_backend":        active,
        "higgsfield_available":  hgf_ok,
        "hf_available":          hf_ok,
        "replicate_available":   rep_ok,
    }


def _run_job(job_id, garments, template, mannequin, subject):
    """백그라운드 스레드: 블로킹 생성을 실행하고 job 상태 갱신."""
    t0 = time.time()
    try:
        result_img, method = generate_model_shot(
            garments       = garments,
            model_template = template,
            mannequin_img  = mannequin,
            subject        = subject,
        )
        _set_job(
            job_id,
            status              = "completed",
            method              = method,
            result_image_base64 = pil_to_base64(result_img, "PNG"),
            processing_time_ms  = int((time.time() - t0) * 1000),
        )
    except gen.GenerativeBillingError as e:
        _set_job(job_id, status="failed", error=str(e), billing=True)
    except Exception as e:
        _set_job(job_id, status="failed", error=f"생성 중 오류: {e}")


@router.post("/generate")
async def generate(
    garment_images:  List[UploadFile]       = File(...),
    garment_types:   List[str]              = Form(...),
    model_template_image:  Optional[UploadFile] = File(None),
    mannequin_image: Optional[UploadFile]   = File(None),
    subject:         str                    = Form("model"),
):
    if len(garment_images) != len(garment_types):
        raise HTTPException(422, "garment_images와 garment_types 개수가 다릅니다.")
    for gt in garment_types:
        if gt not in ALLOWED:
            raise HTTPException(422, f"허용되지 않는 의류 타입: {gt}")
    if subject not in ("model", "mannequin"):
        raise HTTPException(422, f"허용되지 않는 subject: {subject}")

    # 입력은 요청 컨텍스트에서 읽어야 하므로 여기서 PIL로 디코드
    garments = []
    for upload, gtype in zip(garment_images, garment_types):
        data = await upload.read()
        garments.append((bytes_to_pil(data), gtype))

    template = bytes_to_pil(await model_template_image.read()) if model_template_image else None
    mannequin = bytes_to_pil(await mannequin_image.read()) if mannequin_image else None

    job_id = str(uuid.uuid4())
    _set_job(job_id, status="processing")
    threading.Thread(
        target=_run_job,
        args=(job_id, garments, template, mannequin, subject),
        daemon=True,
    ).start()

    return JSONResponse({"job_id": job_id, "status": "processing"}, status_code=202)


@router.get("/generate/result/{job_id}")
def result(job_id: str):
    job = _get_job(job_id)
    if job is None:
        raise HTTPException(404, "존재하지 않는 job_id입니다. (서버 재시작 시 in-memory job 유실)")

    if job["status"] == "processing":
        return JSONResponse({"status": "processing"}, status_code=200)

    if job["status"] == "failed":
        if job.get("billing"):
            raise HTTPException(402, job.get("error", "크레딧 부족"))
        raise HTTPException(500, job.get("error", "생성 실패"))

    return JSONResponse({
        "status":               "completed",
        "method":               job["method"],
        "result_image_base64":  job["result_image_base64"],
        "processing_time_ms":   job["processing_time_ms"],
    })
