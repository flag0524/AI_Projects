"""..."""
from __future__ import annotations
import numpy as np
from PIL import Image
from loguru import logger

THRESHOLD = 0.80


def _cosine_sim(a: np.ndarray, b: np.ndarray) -> float:
    na = np.linalg.norm(a)
    nb = np.linalg.norm(b)
    if na < 1e-8 or nb < 1e-8:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


def _dinov2_sim(img_a: Image.Image, img_b: Image.Image) -> float | None:
    try:
        import torch
        from transformers import AutoImageProcessor, AutoModel

        model_id = "facebook/dinov2-base"
        processor = AutoImageProcessor.from_pretrained(model_id)
        model = AutoModel.from_pretrained(model_id)
        model.eval()

        inputs = processor(images=[img_a, img_b], return_tensors="pt")
        with torch.no_grad():
            out = model(**inputs)
        feats = out.last_hidden_state[:, 0, :].numpy()  # CLS 토큰
        return _cosine_sim(feats[0], feats[1])

    except Exception as e:
        logger.debug(f"DINOv2 불가: {e}")
        return None


def _clip_sim(img_a: Image.Image, img_b: Image.Image) -> float | None:
    try:
        import torch
        import clip as clip_lib

        device = "cuda" if __import__("torch").cuda.is_available() else "cpu"
        model, preprocess = clip_lib.load("ViT-B/32", device=device)
        model.eval()

        ta = preprocess(img_a).unsqueeze(0).to(device)
        tb = preprocess(img_b).unsqueeze(0).to(device)

        with torch.no_grad():
            fa = model.encode_image(ta).cpu().numpy()[0]
            fb = model.encode_image(tb).cpu().numpy()[0]

        return _cosine_sim(fa, fb)

    except Exception as e:
        logger.debug(f"CLIP 불가: {e}")
        return None


def _ssim_sim(img_a: Image.Image, img_b: Image.Image) -> float:
    """..."""
    try:
        from skimage.metrics import structural_similarity as ssim
        import numpy as np

        size = (224, 224)
        a = np.array(img_a.resize(size).convert("L"))
        b = np.array(img_b.resize(size).convert("L"))
        score, _ = ssim(a, b, full=True)
        return float(score)
    except Exception:
        # skimage 없으면 단순 픽셀 MAE
        a = np.array(img_a.resize((224, 224))).astype(float)
        b = np.array(img_b.resize((224, 224))).astype(float)
        mae = np.mean(np.abs(a - b)) / 255.0
        return float(1.0 - mae)


def _crop_garment_region(img: Image.Image) -> Image.Image:
    """..."""
    w, h = img.size
    return img.crop((w // 5, h // 10, w * 4 // 5, h * 6 // 10))


def _calculate_quality_score(result_img: Image.Image, garment_img: Image.Image,
                             result_crop: Image.Image) -> dict:
    """종합 품질 점수 계산 (0~100).
    
    반환:
        {
            "overall": 종합 점수,
            "detail_preservation": 디테일 보존,
            "boundary_quality": 경계선 품질,
            "color_harmony": 색감 조화,
            "wrinkle_definition": 주름 선명도,
        }
    """
    scores = {}
    
    # 1. 디테일 보존도
    detail_score = _dinov2_sim(garment_img, result_crop)
    if detail_score is None:
        detail_score = _clip_sim(garment_img, result_crop)
    if detail_score is None:
        detail_score = _ssim_sim(garment_img, result_crop)
    scores["detail_preservation"] = (detail_score or 0.5) * 100
    
    # 2. 경계선 품질 (엣지 선명도)
    try:
        import cv2
        img_array = np.array(result_img)
        gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
        edges = cv2.Canny(gray, 50, 150)
        edge_density = np.count_nonzero(edges) / edges.size
        # 경계가 명확할수록 높은 점수 (5~20% 사이가 정상)
        boundary_score = 100 if 0.05 <= edge_density <= 0.2 else 60
        scores["boundary_quality"] = boundary_score
    except Exception:
        scores["boundary_quality"] = 75
    
    # 3. 색감 조화 (HSV 색상 일관성)
    try:
        import cv2
        result_hsv = cv2.cvtColor(np.array(result_img), cv2.COLOR_RGB2HSV)
        garment_hsv = cv2.cvtColor(np.array(garment_img), cv2.COLOR_RGB2HSV)
        
        # 평균 색상 비교
        result_h_mean = result_hsv[:, :, 0].mean()
        garment_h_mean = garment_hsv[:, :, 0].mean()
        h_diff = min(abs(result_h_mean - garment_h_mean), 180)
        
        # 최대 차이 180도이므로, 30도 이내이면 좋음
        color_score = 100 - (h_diff / 180 * 100)
        scores["color_harmony"] = max(50, color_score)
    except Exception:
        scores["color_harmony"] = 75
    
    # 4. 주름 선명도 (라플라시안 분산)
    try:
        import cv2
        result_gray = cv2.cvtColor(np.array(result_img), cv2.COLOR_RGB2GRAY)
        laplacian = cv2.Laplacian(result_gray, cv2.CV_64F)
        wrinkle_score = min(100, np.var(laplacian) / 100)
        scores["wrinkle_definition"] = wrinkle_score
    except Exception:
        scores["wrinkle_definition"] = 75
    
    # 종합 점수 (가중치 평균)
    weights = {
        "detail_preservation": 0.3,
        "boundary_quality": 0.25,
        "color_harmony": 0.2,
        "wrinkle_definition": 0.25,
    }
    
    overall = sum(scores.get(k, 75) * w for k, w in weights.items())
    scores["overall"] = round(overall)
    
    return scores


def verify_detail(
    garment_img: Image.Image,
    result_img: Image.Image,
) -> dict:
    """상세 검증 수행.
    
    반환:
        {
            "scores": 품질 점수들,
            "status": "양호" | "경고" | "부적절",
            "recommendations": 개선 권고사항 리스트
        }
    """
    result_crop = _crop_garment_region(result_img)
    scores = _calculate_quality_score(result_img, garment_img, result_crop)
    
    overall = scores["overall"]
    
    # 상태 결정
    if overall >= 75:
        status = "양호"
    elif overall >= 60:
        status = "경고"
    else:
        status = "부적절"
    
    # 권고사항 생성
    recommendations = []
    if scores["detail_preservation"] < 70:
        recommendations.append("의류 디테일이 불분명함 — 해상도 증가 또는 가이던스 스케일 조정 필요")
    if scores["boundary_quality"] < 70:
        recommendations.append("경계선이 부자연스러움 — 포스트프로세싱 블렌딩 강도 증가")
    if scores["color_harmony"] < 70:
        recommendations.append("색감이 어울리지 않음 — 의류 색 보정 또는 마네킹 조명 확인")
    if scores["wrinkle_definition"] < 60:
        recommendations.append("주름이 부자연스러움 — 드레이프 강도 조정")
    
    logger.info(
        f"상세 검증 완료: overall={overall} status={status} "
        f"detail={scores['detail_preservation']:.0f} "
        f"boundary={scores['boundary_quality']:.0f}"
    )
    
    return {
        "scores": scores,
        "status": status,
        "recommendations": recommendations,
    }


def batch_verify(
    garment_img: Image.Image,
    result_imgs: list[Image.Image],
) -> list[dict]:
    """배치 검증."""
    return [verify_detail(garment_img, r) for r in result_imgs]
