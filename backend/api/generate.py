"""
LaonGEN 생성 엔드포인트.

마네킹/옷걸이 제품 사진만으로 자연스러운 모델 착용 컷 생성.

POST /api/v1/generate
  - garment_images[] : 제품 사진 (마네킹/옷걸이 착용, jpg/png)
  - garment_types[]  : top | bottom | dress | accessory
  - model_template   : (선택) 표준 모델 사진
  - mannequin_image  : (선택) 절차적 폴백용 마네킹

응답:
  {
    "status": "success",
    "method": "generative" | "procedural",
    "result_image_base64": "...",
    "processing_time_ms": 1234
  }
"""
import time
from typing import List, Optional
from fastapi import APIRouter, File, Form, UploadFile, HTTPException
from fastapi.responses import JSONResponse

from backend.utils.image_utils import bytes_to_pil, pil_to_base64
from backend.pipeline.laongen_engine import generate_model_shot
from backend.pipeline import generative_provider as gen

router  = APIRouter()
ALLOWED = {"top", "bottom", "dress", "accessory"}


@router.get("/generate/status")
def status():
    """생성형 백엔드 가용 여부 확인."""
    from backend.pipeline import hf_provider as hf
    import os

    hf_ok    = hf.is_available()
    rep_ok   = gen.is_available()
    backend  = os.environ.get("GEN_BACKEND", "hf").strip().lower()

    if backend in ("hf", "auto") and hf_ok:
        active = f"huggingface/{hf.HF_SPACE}"
    elif rep_ok:
        active = "replicate/idm-vton"
    else:
        active = "procedural-fallback"

    return {
        "generative_available": hf_ok or rep_ok,
        "active_backend":        active,
        "hf_available":          hf_ok,
        "replicate_available":   rep_ok,
    }


@router.post("/generate")
async def generate(
    garment_images:  List[UploadFile]       = File(...),
    garment_types:   List[str]              = Form(...),
    model_template_image:  Optional[UploadFile] = File(None),
    mannequin_image: Optional[UploadFile]   = File(None),
):
    t0 = time.time()

    if len(garment_images) != len(garment_types):
        raise HTTPException(422, "garment_images와 garment_types 개수가 다릅니다.")
    for gt in garment_types:
        if gt not in ALLOWED:
            raise HTTPException(422, f"허용되지 않는 의류 타입: {gt}")

    try:
        # 의류 로드
        garments = []
        for upload, gtype in zip(garment_images, garment_types):
            data = await upload.read()
            garments.append((bytes_to_pil(data), gtype))

        # 선택 입력
        template = None
        if model_template_image is not None:
            template = bytes_to_pil(await model_template_image.read())

        mannequin = None
        if mannequin_image is not None:
            mannequin = bytes_to_pil(await mannequin_image.read())

        # 하이브리드 생성
        result_img, method = generate_model_shot(
            garments       = garments,
            model_template = template,
            mannequin_img  = mannequin,
        )

        ms = int((time.time() - t0) * 1000)
        return JSONResponse({
            "status":               "success",
            "method":               method,
            "result_image_base64":  pil_to_base64(result_img, "PNG"),
            "processing_time_ms":   ms,
        })

    except gen.GenerativeBillingError as e:
        # 402: 크레딧 부족 — 결제 안내
        raise HTTPException(402, str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"생성 중 오류: {str(e)}")
