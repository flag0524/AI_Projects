"""
마네킹 피팅 API 엔드포인트.

파이프라인:
  1. 마네킹 전처리 (원본 보존)
  2. 배경 제거 → body_analyzer로 해부학적 영역 정밀 감지
  3. 의류별 scanline warp → 몸체 윤곽에 맞게 감싸기
  4. 레이어 합성 (원본 마네킹 위에만)
"""
import time
import numpy as np
from typing import List
from fastapi import APIRouter, File, Form, UploadFile, HTTPException
from fastapi.responses import JSONResponse

from backend.utils.image_utils import bytes_to_pil, pil_to_base64
from backend.pipeline.preprocessor import preprocess
from backend.pipeline.bg_remover import remove_background
from backend.pipeline.body_analyzer import get_mask_from_image, detect_body_regions
from backend.pipeline.garment_warper import warp_garment, fallback_affine_warp
from backend.pipeline.composer import compose

router      = APIRouter()
ALLOWED     = {"top", "bottom", "dress", "accessory"}


@router.post("/fit")
async def fit(
    mannequin_image: UploadFile       = File(...),
    garment_images:  List[UploadFile] = File(...),
    garment_types:   List[str]        = Form(...),
):
    t0 = time.time()

    # ── 입력 검증 ─────────────────────────────────────────────
    if len(garment_images) != len(garment_types):
        raise HTTPException(422, "garment_images와 garment_types 개수가 다릅니다.")
    for gt in garment_types:
        if gt not in ALLOWED:
            raise HTTPException(422, f"허용되지 않는 의류 타입: {gt}")

    try:
        # ── 마네킹 처리 ───────────────────────────────────────
        mann_bytes   = await mannequin_image.read()
        mann_pil     = bytes_to_pil(mann_bytes)

        # 합성 베이스: 리사이즈만 (원본 보존)
        mann_base, _ = preprocess(mann_pil)

        # 배경 제거본: 분석·와핑용 (화면에 표시 안 됨)
        mann_nobg    = remove_background(mann_base)

        # ── 몸체 영역 정밀 감지 ───────────────────────────────
        body_mask    = get_mask_from_image(mann_nobg)
        body_regions = detect_body_regions(body_mask)

        # ── 의류 처리 ─────────────────────────────────────────
        warped_garments: dict = {}
        for upload, gtype in zip(garment_images, garment_types):
            g_bytes      = await upload.read()
            g_pil        = bytes_to_pil(g_bytes)
            g_resized, _ = preprocess(g_pil)
            g_nobg       = remove_background(g_resized)

            try:
                warped = warp_garment(
                    g_nobg,
                    gtype,
                    body_regions,
                    canvas_size    = 512,
                    mannequin_nobg = mann_nobg,
                    body_mask      = body_mask,
                )
            except Exception as e:
                # 폴백: 단순 리사이즈
                warped = fallback_affine_warp(g_nobg, gtype, body_regions)

            warped_garments[gtype] = warped

        # ── 합성 ──────────────────────────────────────────────
        result_img = compose(mann_base, warped_garments, mann_nobg)

        ms = int((time.time() - t0) * 1000)
        return JSONResponse({
            "status":              "success",
            "fitted_image_base64": pil_to_base64(result_img, "PNG"),
            "processing_time_ms":  ms,
        })

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"처리 중 오류: {str(e)}")
