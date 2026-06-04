import time
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


@router.post("/fit")
async def fit(
    mannequin_image: UploadFile = File(...),
    garment_images: List[UploadFile] = File(...),
    garment_types: List[str] = Form(...),
):
    t0 = time.time()

    # 입력 검증
    if len(garment_images) != len(garment_types):
        raise HTTPException(status_code=422, detail="garment_images와 garment_types 개수가 다릅니다.")
    for gt in garment_types:
        if gt not in ALLOWED_TYPES:
            raise HTTPException(status_code=422, detail=f"허용되지 않는 의류 타입: {gt}")

    try:
        # 마네킹 이미지 처리
        mannequin_bytes = await mannequin_image.read()
        mannequin_pil = bytes_to_pil(mannequin_bytes)
        mannequin_resized, _ = preprocess(mannequin_pil)
        mannequin_nobg = remove_background(mannequin_resized)

        # 포즈 추정
        kpts = estimate_pose(mannequin_nobg)
        if kpts is None:
            # 포즈 감지 실패 시 이미지 전체를 신체 영역으로 간주
            size = 512
            kpts = {
                "left_shoulder": (int(size * 0.3), int(size * 0.15)),
                "right_shoulder": (int(size * 0.7), int(size * 0.15)),
                "left_hip": (int(size * 0.35), int(size * 0.55)),
                "right_hip": (int(size * 0.65), int(size * 0.55)),
                "left_ankle": (int(size * 0.35), int(size * 0.95)),
                "right_ankle": (int(size * 0.65), int(size * 0.95)),
            }
        body_bounds = estimate_body_bounds(kpts)

        # 의류 처리 및 와핑
        warped_garments: dict = {}
        for upload, gtype in zip(garment_images, garment_types):
            garment_bytes = await upload.read()
            garment_pil = bytes_to_pil(garment_bytes)
            garment_resized, _ = preprocess(garment_pil)
            garment_nobg = remove_background(garment_resized)

            try:
                warped = warp_garment(garment_nobg, gtype, body_bounds)
            except Exception:
                warped = fallback_affine_warp(garment_nobg, gtype, body_bounds)
            warped_garments[gtype] = warped

        # 합성
        result_img = compose(mannequin_nobg, warped_garments)

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
