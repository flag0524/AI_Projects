"""레이어링 파이프라인 (상의+하의 정렬 개선)

개선 사항:
- 경계선 자동 감지 및 정렬
- 중복 영역 자연스러운 블렌딩
- 폭 정규화
"""
from __future__ import annotations
from pathlib import Path
import numpy as np
from PIL import Image
from loguru import logger

from pipeline.preprocess import preprocess_images
from pipeline.pose_estimation import estimate_pose
from pipeline.garment_parsing import parse_garment
from pipeline.body_parsing import parse_body, make_agnostic_map
from pipeline.fit_engine import FitEngine
from pipeline.engine_selector import get_engine
from pipeline.detail_verification import verify_detail
from pipeline.postprocess import postprocess
from schemas import Category, FitMode, GarmentSize, FitReport, ResultItem
from config import settings


def _detect_boundary_y(mask: Image.Image, search_direction: str = "down") -> int:
    """의류 경계선 검출 (y 좌표).
    
    인자:
        mask: 의류 마스크
        search_direction: "down" (상단에서 하단 검색) 또는 "up" (하단에서 상단 검색)
    
    반환: 경계선의 y 좌표 (픽셀)
    """
    m = np.array(mask)
    rows = np.any(m > 127, axis=1)
    
    if search_direction == "down":
        # 상단부터 검색하여 의류 시작점 찾기
        row_indices = np.where(rows)[0]
        if len(row_indices) > 0:
            return int(row_indices[0])
    elif search_direction == "up":
        # 하단부터 검색하여 의류 끝점 찾기
        row_indices = np.where(rows)[0]
        if len(row_indices) > 0:
            return int(row_indices[-1])
    
    return -1


def _blend_boundaries_layered(top_img: Image.Image, bottom_img: Image.Image,
                               blend_height: int = 30) -> Image.Image:
    """상의와 하의의 경계를 자연스럽게 블렌딩.
    
    인자:
        top_img: 상의가 합성된 이미지
        bottom_img: 하의가 합성될 이미지
        blend_height: 블렌딩 높이 (픽셀)
    
    반환: 블렌딩된 이미지
    """
    try:
        import cv2
        
        top_array = np.array(top_img, dtype=np.float32)
        bottom_array = np.array(bottom_img, dtype=np.float32)
        
        h, w = top_array.shape[:2]
        
        # 상의의 하단 경계선 추정 (마네킹 중앙 허리 위치)
        blend_y_start = int(h * 0.45)  # 상의 끝나는 부분
        blend_y_end = min(blend_y_start + blend_height, h)
        
        # 블렌딩 가중치 생성 (선형 그래디언트)
        blend_weights = np.linspace(0, 1, blend_y_end - blend_y_start)
        
        result_array = top_array.copy()
        
        for i, y in enumerate(range(blend_y_start, blend_y_end)):
            w_top = 1.0 - blend_weights[i]
            w_bottom = blend_weights[i]
            
            result_array[y, :] = (top_array[y, :] * w_top +
                                   bottom_array[y, :] * w_bottom)
        
        # 하의 부분 추가
        result_array[blend_y_end:, :] = bottom_array[blend_y_end:, :]
        
        result_array = np.clip(result_array, 0, 255).astype(np.uint8)
        return Image.fromarray(result_array, mode="RGB")
    
    except Exception as e:
        logger.warning(f"경계 블렌딩 실패: {e}")
        return bottom_img


def _normalize_width(img: Image.Image, reference_width: int) -> Image.Image:
    """의류 폭 정규화 (가로 스트레칭 보정).
    
    인자:
        img: 정규화할 이미지
        reference_width: 참조 폭
    """
    if img.width == reference_width:
        return img
    
    # 너무 좁거나 넓으면 조정
    if img.width < reference_width * 0.9:
        scale = reference_width / img.width
        new_h = int(img.height * scale)
        img = img.resize((reference_width, new_h), Image.LANCZOS)
    elif img.width > reference_width * 1.1:
        scale = reference_width / img.width
        new_h = int(img.height * scale)
        img = img.resize((reference_width, new_h), Image.LANCZOS)
    
    return img


def run_layered(
    mannequin_path: Path,
    top_path: Path,
    bottom_path: Path,
    top_size: GarmentSize | None,
    bottom_size: GarmentSize | None,
    fit_mode: FitMode,
    seed: int,
    num_steps: int,
    guidance_scale: float,
    remove_background: bool,
    result_dir: Path,
    job_id: str,
) -> tuple[list[ResultItem], FitReport | None]:
    """상의+하의 레이어링 파이프라인.
    
    반환:
        (결과_이미지_목록, 통합_피팅_리포트)
    """
    logger.info(f"[{job_id}] 레이어링 시작")

    # 포즈 추정 먼저
    mannequin_raw = Image.open(mannequin_path).convert("RGB")
    pose_data = estimate_pose(mannequin_raw)
    
    # 전처리 (포즈 데이터 포함)
    mannequin_img, top_img, _ = preprocess_images(
        mannequin_path, top_path, remove_background, pose_data=pose_data)
    _, bottom_img, _ = preprocess_images(
        mannequin_path, bottom_path, remove_background, pose_data=pose_data)

    body_data = parse_body(mannequin_img)

    top_garment = parse_garment(top_img, Category.top)
    bottom_garment = parse_garment(bottom_img, Category.bottom)

    # 핏 계산 (포즈 데이터 포함)
    top_engine = FitEngine(Category.top)
    bottom_engine = FitEngine(Category.bottom)

    top_params, top_report = top_engine.compute(
        top_size, pose_data["body_measurements"], fit_mode, pose_data=pose_data)
    bottom_params, bot_report = bottom_engine.compute(
        bottom_size, pose_data["body_measurements"], fit_mode, pose_data=pose_data)

    tier_override = settings.engine_tier if settings.engine_tier > 0 else None
    model, tier = get_engine(tier_override)
    logger.info(f"[{job_id}] 레이어링 엔진 Tier {tier}")

    # 1단계: 상의 합성
    logger.info(f"[{job_id}] 레이어링 1단계: 상의")
    top_agnostic = make_agnostic_map(
        mannequin_img, body_data["masks"], "top", pose_data["keypoints"]
    )
    mid_img = model.infer(
        mannequin_img=mannequin_img,
        garment_img=top_img,
        pose_data=pose_data,
        garment_data=top_garment,
        fit_params=top_params,
        agnostic_map=top_agnostic,
        seed=seed,
        num_steps=num_steps,
        guidance_scale=guidance_scale,
    )
    
    # 상의 포스트프로세싱
    mid_img = postprocess(
        mid_img, top_garment.get("mask"), mannequin_img,
        enable_blend=True, enable_color_harmony=True,
        enable_denoise=True, enable_sharpening=True
    )

    # 2단계: 하의 합성
    logger.info(f"[{job_id}] 레이어링 2단계: 하의")
    # 중간 결과에서 신체 정보 추출
    mid_body_data = parse_body(mid_img)
    bottom_agnostic = make_agnostic_map(
        mid_img, mid_body_data["masks"], "bottom", pose_data["keypoints"]
    )
    final_img = model.infer(
        mannequin_img=mid_img,
        garment_img=bottom_img,
        pose_data=pose_data,
        garment_data=bottom_garment,
        fit_params=bottom_params,
        agnostic_map=bottom_agnostic,
        seed=seed + 1,
        num_steps=num_steps,
        guidance_scale=guidance_scale,
    )
    
    # 하의 포스트프로세싱
    final_img = postprocess(
        final_img, bottom_garment.get("mask"), mid_img,
        enable_blend=True, enable_color_harmony=True,
        enable_denoise=True, enable_sharpening=True
    )

    # 경계선 추가 블렌딩
    final_img = _blend_boundaries_layered(mid_img, final_img, blend_height=40)

    # 결과 저장
    result_path = result_dir / f"{job_id}_layered.png"
    final_img.save(str(result_path))

    # 통합 피팅 리포트
    combined_report = FitReport(
        chest_ease_cm=top_report.chest_ease_cm if top_report else None,
        waist_ease_cm=bot_report.waist_ease_cm if bot_report else None,
        hip_ease_cm=bot_report.hip_ease_cm if bot_report else None,
        length_landmark=bot_report.length_landmark if bot_report else top_report.length_landmark,
        fit_label="레이어링",
        warnings=((top_report.warnings or []) + (bot_report.warnings or []))
                if top_report and bot_report else [],
    )

    results = [ResultItem(
        image_url=f"/results/{result_path.name}",
        seed=seed,
        fit_report=combined_report,
    ).model_dump()]

    logger.info(f"[{job_id}] 레이어링 완료")
    return results, combined_report
