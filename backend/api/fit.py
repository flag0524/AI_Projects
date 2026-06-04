import time
import numpy as np
from typing import List
from fastapi import APIRouter, File, Form, UploadFile, HTTPException
from fastapi.responses import JSONResponse

from backend.utils.image_utils import bytes_to_pil, pil_to_base64
from backend.pipeline.preprocessor import preprocess
from backend.pipeline.bg_remover import remove_background
from backend.pipeline.pose_estimator import estimate_pose, estimate_body_bounds
from backend.pipeline.garment_warper import warp_garment, fallback_affine_warp
from backend.pipeline.composer import compose

router = APIRouter()
ALLOWED_TYPES = {"top", "bottom", "dress", "accessory"}


def _detect_body_bounds_from_mask(mannequin_nobg, size: int = 512) -> dict | None:
    arr   = np.array(mannequin_nobg)
    alpha = arr[:, :, 3] if arr.shape[2] == 4 else np.ones((size, size), np.uint8) * 255
    rows  = np.where(alpha.max(axis=1) > 30)[0]
    cols  = np.where(alpha.max(axis=0) > 30)[0]
    if len(rows) == 0 or len(cols) == 0:
        return None

    body_top   = int(rows[0]);  body_bottom = int(rows[-1])
    body_left  = int(cols[0]);  body_right  = int(cols[-1])
    bw = body_right - body_left
    bh = body_bottom - body_top

    shoulder_y = body_top + int(bh * 0.18)
    hip_y      = body_top + int(bh * 0.55)
    ankle_y    = body_top + int(bh * 0.95)

    return {
        "left_shoulder":  (body_left  + int(bw * 0.10), shoulder_y),
        "right_shoulder": (body_right - int(bw * 0.10), shoulder_y),
        "left_hip":       (body_left  + int(bw * 0.18), hip_y),
        "right_hip":      (body_right - int(bw * 0.18), hip_y),
        "left_ankle":     (body_left  + int(bw * 0.22), ankle_y),
        "right_ankle":    (body_right - int(bw * 0.22), ankle_y),
    }


@router.post("/fit")
async def fit(
    mannequin_image:  UploadFile        = File(...),
    garment_images:   List[UploadFile]  = File(...),
    garment_types:    List[str]         = Form(...),
):
    t0 = time.time()

    if len(garment_images) != len(garment_types):
        raise HTTPException(422, "garment_images와 garment_types 개수가 다릅니다.")
    for gt in garment_types:
        if gt not in ALLOWED_TYPES:
            raise HTTPException(422, f"허용되지 않는 의류 타입: {gt}")

    try:
        size = 512

        # ── 마네킹 ──────────────────────────────────────────────────────
        mann_bytes    = await mannequin_image.read()
        mann_pil      = bytes_to_pil(mann_bytes)
        mann_base, _  = preprocess(mann_pil)        # 원본 (합성 베이스)
        mann_nobg     = remove_background(mann_base) # 배경제거본 (분석·와핑용)

        # ── 신체 경계 추정 ───────────────────────────────────────────────
        kpts = estimate_pose(mann_nobg)
        if kpts is None:
            kpts = _detect_body_bounds_from_mask(mann_nobg, size)
        if kpts is None:
            kpts = {
                "left_shoulder":  (int(size * 0.28), int(size * 0.16)),
                "right_shoulder": (int(size * 0.72), int(size * 0.16)),
                "left_hip":       (int(size * 0.33), int(size * 0.54)),
                "right_hip":      (int(size * 0.67), int(size * 0.54)),
                "left_ankle":     (int(size * 0.33), int(size * 0.94)),
                "right_ankle":    (int(size * 0.67), int(size * 0.94)),
            }
        body_bounds = estimate_body_bounds(kpts)

        # ── 의류 와핑 ────────────────────────────────────────────────────
        warped_garments: dict = {}
        for upload, gtype in zip(garment_images, garment_types):
            g_bytes         = await upload.read()
            g_pil           = bytes_to_pil(g_bytes)
            g_resized, _    = preprocess(g_pil)
            g_nobg          = remove_background(g_resized)

            try:
                # 몸체 윤곽 기반 와핑 (mannequin_nobg 전달)
                warped = warp_garment(
                    g_nobg, gtype, body_bounds,
                    mannequin_nobg=mann_nobg
                )
            except Exception:
                warped = fallback_affine_warp(g_nobg, gtype, body_bounds)

            warped_garments[gtype] = warped

        # ── 합성 ─────────────────────────────────────────────────────────
        result_img = compose(mann_base, warped_garments, mann_nobg)

        ms = int((time.time() - t0) * 1000)
        return JSONResponse({
            "status":               "success",
            "fitted_image_base64":  pil_to_base64(result_img, "PNG"),
            "processing_time_ms":   ms,
        })

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"처리 중 오류: {str(e)}")
