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
    """배경 제거된 마네킹 알파 채널로 신체 경계 추정."""
    arr = np.array(mannequin_nobg)
    alpha = arr[:, :, 3] if arr.shape[2] == 4 else np.ones((size, size), dtype=np.uint8) * 255
    rows = np.where(alpha.max(axis=1) > 30)[0]
    cols = np.where(alpha.max(axis=0) > 30)[0]
    if len(rows) == 0 or len(cols) == 0:
        return None

    body_top    = int(rows[0])
    body_bottom = int(rows[-1])
    body_left   = int(cols[0])
    body_right  = int(cols[-1])
    body_w = body_right - body_left
    body_h = body_bottom - body_top

    shoulder_y = body_top + int(body_h * 0.18)
    hip_y      = body_top + int(body_h * 0.55)
    ankle_y    = body_top + int(body_h * 0.95)
    s_inset    = int(body_w * 0.10)

    return {
        "left_shoulder":  (body_left  + s_inset,           shoulder_y),
        "right_shoulder": (body_right - s_inset,           shoulder_y),
        "left_hip":       (body_left  + int(body_w * 0.20), hip_y),
        "right_hip":      (body_right - int(body_w * 0.20), hip_y),
        "left_ankle":     (body_left  + int(body_w * 0.25), ankle_y),
        "right_ankle":    (body_right - int(body_w * 0.25), ankle_y),
    }


@router.post("/fit")
async def fit(
    mannequin_image: UploadFile = File(...),
    garment_images: List[UploadFile] = File(...),
    garment_types: List[str] = Form(...),
):
    t0 = time.time()

    if len(garment_images) != len(garment_types):
        raise HTTPException(status_code=422, detail="garment_images와 garment_types 개수가 다릅니다.")
    for gt in garment_types:
        if gt not in ALLOWED_TYPES:
            raise HTTPException(status_code=422, detail=f"허용되지 않는 의류 타입: {gt}")

    try:
        size = 512

        # ── 마네킹: 원본 보존 ─────────────────────────────────────────────
        mannequin_bytes = await mannequin_image.read()
        mannequin_pil   = bytes_to_pil(mannequin_bytes)

        # 합성 베이스: 리사이즈만 한 원본 (배경 제거 X)
        mannequin_base, _ = preprocess(mannequin_pil)   # RGBA, 512×512

        # 포즈 추정용: 배경 제거본 사용 (화면에 표시되지 않음)
        mannequin_nobg = remove_background(mannequin_base)

        # ── 신체 경계 추정 ────────────────────────────────────────────────
        kpts = estimate_pose(mannequin_nobg)
        if kpts is None:
            kpts = _detect_body_bounds_from_mask(mannequin_nobg, size)
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

        # ── 의류: 배경 제거 → 와핑 ───────────────────────────────────────
        warped_garments: dict = {}
        for upload, gtype in zip(garment_images, garment_types):
            garment_bytes  = await upload.read()
            garment_pil    = bytes_to_pil(garment_bytes)
            garment_resized, _ = preprocess(garment_pil)
            garment_nobg   = remove_background(garment_resized)

            try:
                warped = warp_garment(garment_nobg, gtype, body_bounds)
            except Exception:
                warped = fallback_affine_warp(garment_nobg, gtype, body_bounds)
            warped_garments[gtype] = warped

        # ── 합성: 원본 마네킹 위에 의류만 올림 ───────────────────────────
        result_img = compose(mannequin_base, warped_garments)

        processing_ms = int((time.time() - t0) * 1000)
        return JSONResponse({
            "status": "success",
            "fitted_image_base64": pil_to_base64(result_img, "PNG"),
            "processing_time_ms": processing_ms,
        })

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"처리 중 오류 발생: {str(e)}")
