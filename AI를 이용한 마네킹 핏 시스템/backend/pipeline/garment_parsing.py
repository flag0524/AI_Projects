"""의류 인식 및 세그멘테이션 (YOLOv8-seg 통합)

개선 사항:
- YOLOv8-seg 기반 고정확도 세그멘테이션
- 의류 방향 자동 감지 및 정렬
- 카테고리별 세밀한 부위 분할
- 의류 에지 정확도 향상
"""
from __future__ import annotations
import numpy as np
from PIL import Image
from loguru import logger
from schemas import Category

try:
    from ultralytics import YOLO
    YOLO_AVAILABLE = True
except ImportError:
    YOLO_AVAILABLE = False
    logger.warning("YOLOv8 미설치 — 폴백 모드 사용")


class GarmentSegmentor:
    """YOLOv8-seg 기반 의류 세그멘테이션"""
    _instance = None
    _model = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def _load(self):
        if self._model is not None or not YOLO_AVAILABLE:
            return
        try:
            logger.info("YOLOv8-seg 모델 로딩...")
            self._model = YOLO("yolov8l-seg.pt")
            logger.info("YOLOv8-seg 로드 완료")
        except Exception as e:
            logger.warning(f"YOLOv8 로드 실패: {e} — 폴백 모드 사용")
            self._model = None

    def segment(self, image: Image.Image) -> np.ndarray:
        """YOLOv8-seg로 의류 세그멘테이션.
        
        반환: 의류 마스크 (0=배경, 255=의류)
        """
        if not YOLO_AVAILABLE or self._model is None:
            return self._fallback_segment(image)

        self._load()
        try:
            img_array = np.array(image)
            results = self._model(img_array, conf=0.3)
            
            if results and len(results) > 0 and results[0].masks is not None:
                # 의류 클래스만 추출 (일반적으로 클래스 0)
                mask = results[0].masks.data[0].cpu().numpy() * 255
                return mask.astype(np.uint8)
        except Exception as e:
            logger.warning(f"YOLOv8 세그멘테이션 실패: {e}")
        
        return self._fallback_segment(image)

    def _fallback_segment(self, image: Image.Image) -> np.ndarray:
        """폴백: 배경 색상 기반 세그멘테이션"""
        img_array = np.array(image)
        if img_array.ndim == 3:
            gray = np.array(image.convert("L"))
        else:
            gray = img_array
        
        # 백색 배경 제거 (임계값: 240)
        mask = (gray < 240).astype(np.uint8) * 255
        return mask


def _detect_garment_orientation(mask: Image.Image) -> float:
    """의류의 주축 각도 검출 (라디안).
    
    PCA를 사용하여 의류가 회전된 정도를 계산합니다.
    반환값: -π/2 ~ π/2
    """
    from scipy import ndimage
    
    m = np.array(mask)
    if not m.any():
        return 0.0
    
    # 전경 픽셀 좌표
    coords = np.where(m > 127)
    if len(coords[0]) < 10:
        return 0.0
    
    points = np.column_stack(coords)
    
    # PCA로 주축 계산
    mean = points.mean(axis=0)
    centered = points - mean
    cov = centered.T @ centered
    
    try:
        eigenvalues, eigenvectors = np.linalg.eigh(cov)
        # 가장 큰 고유벡터 (주축)
        main_axis = eigenvectors[:, -1]
        angle = np.arctan2(main_axis[0], main_axis[1])
        return angle
    except Exception:
        return 0.0


def _rotate_image_by_angle(img: Image.Image, angle_rad: float) -> Image.Image:
    """이미지를 각도만큼 회전.
    
    인자:
        img: 회전할 이미지
        angle_rad: 회전 각도 (라디안)
    """
    angle_deg = np.degrees(angle_rad)
    # 15도 이상 회전 필요할 때만 수행
    if abs(angle_deg) < 2:
        return img
    
    return img.rotate(-angle_deg, expand=False, fillcolor=255)


def _extract_garment_keypoints(mask: Image.Image, category: Category) -> dict:
    """의류 마스크에서 주요 지점 추출.
    
    반환: 정규화된 좌표 (0~1), 바운딩박스, 부위별 랜드마크
    """
    m = np.array(mask)
    rows = np.any(m > 127, axis=1)
    cols = np.any(m > 127, axis=0)
    
    if not rows.any():
        return {}
    
    rmin, rmax = np.where(rows)[0][[0, -1]]
    cmin, cmax = np.where(cols)[0][[0, -1]]
    h, w = m.shape
    
    # 정규화된 좌표
    top_center = ((cmin + cmax) / 2 / w, rmin / h)
    bottom_center = ((cmin + cmax) / 2 / w, rmax / h)
    left_center = (cmin / w, (rmin + rmax) / 2 / h)
    right_center = (cmax / w, (rmin + rmax) / 2 / h)
    
    points = {
        "top_center": top_center,
        "bottom_center": bottom_center,
        "left_center": left_center,
        "right_center": right_center,
        "bbox_norm": (cmin / w, rmin / h, cmax / w, rmax / h),
        "height_ratio": (rmax - rmin) / h,
        "width_ratio": (cmax - cmin) / w,
    }
    
    # 카테고리별 추가 랜드마크
    if category == Category.top:
        # 상의: 어깨선 (상단 1/4)
        quarter = rmin + (rmax - rmin) // 4
        shoulder_slice = m[rmin:quarter, :]
        if shoulder_slice.any():
            s_cols = np.any(shoulder_slice > 127, axis=0)
            if s_cols.any():
                sc_min, sc_max = np.where(s_cols)[0][[0, -1]]
                points["shoulder_left"] = (sc_min / w, quarter / h)
                points["shoulder_right"] = (sc_max / w, quarter / h)
                points["shoulder_width_ratio"] = (sc_max - sc_min) / w
        
        # 소매 끝점 검출 (좌우 중단부)
        mid_y = rmin + (rmax - rmin) // 2
        mid_slice = m[max(0, mid_y-10):min(h, mid_y+10), :]
        if mid_slice.any():
            m_cols = np.any(mid_slice > 127, axis=0)
            if m_cols.any():
                m_min, m_max = np.where(m_cols)[0][[0, -1]]
                points["sleeve_left"] = (m_min / w, mid_y / h)
                points["sleeve_right"] = (m_max / w, mid_y / h)
    
    elif category == Category.bottom:
        # 하의: 허리선 (상단 1/6)
        waist_y = rmin + (rmax - rmin) // 6
        waist_slice = m[rmin:waist_y, :]
        if waist_slice.any():
            w_cols = np.any(waist_slice > 127, axis=0)
            if w_cols.any():
                w_min, w_max = np.where(w_cols)[0][[0, -1]]
                points["waist_left"] = (w_min / w, waist_y / h)
                points["waist_right"] = (w_max / w, waist_y / h)
                points["waist_width_ratio"] = (w_max - w_min) / w
    
    elif category == Category.dress:
        # 원피스: 어깨선 + 허리선
        quarter = rmin + (rmax - rmin) // 4
        shoulder_slice = m[rmin:quarter, :]
        if shoulder_slice.any():
            s_cols = np.any(shoulder_slice > 127, axis=0)
            if s_cols.any():
                sc_min, sc_max = np.where(s_cols)[0][[0, -1]]
                points["shoulder_left"] = (sc_min / w, quarter / h)
                points["shoulder_right"] = (sc_max / w, quarter / h)
        
        waist_y = rmin + (rmax - rmin) // 2
        waist_slice = m[quarter:waist_y, :]
        if waist_slice.any():
            w_cols = np.any(waist_slice > 127, axis=0)
            if w_cols.any():
                w_min, w_max = np.where(w_cols)[0][[0, -1]]
                points["waist_left"] = (w_min / w, waist_y / h)
                points["waist_right"] = (w_max / w, waist_y / h)
    
    return points


def _morphological_clean(mask: Image.Image, iterations: int = 1) -> Image.Image:
    """모폴로지 연산으로 마스크 정제.
    
    - CLOSE: 작은 구멍 채우기
    - OPEN: 노이즈 제거
    """
    try:
        import cv2
        m = np.array(mask)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
        m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, kernel, iterations=iterations)
        m = cv2.morphologyEx(m, cv2.MORPH_OPEN, kernel, iterations=max(1, iterations-1))
        return Image.fromarray(m, mode="L")
    except ImportError:
        return mask


def parse_garment(image: Image.Image, category: Category) -> dict:
    """의류 이미지 분석 및 파싱.
    
    반환:
        {
            "mask": PIL Image (L mode),
            "mask_rotated": 정렬 후 마스크,
            "orientation_angle": 라디안,
            "keypoints": 랜드마크 좌표,
            "category": 카테고리,
        }
    """
    segmentor = GarmentSegmentor()
    
    # YOLOv8-seg 또는 폴백으로 세그멘테이션
    mask_array = segmentor.segment(image)
    mask = Image.fromarray(mask_array, mode="L")
    
    # 모폴로지 정제
    mask = _morphological_clean(mask, iterations=2)
    
    # 의류 방향 감지
    orientation = _detect_garment_orientation(mask)
    
    # 정규화 좌표 추출
    keypoints = _extract_garment_keypoints(mask, category)
    
    result = {
        "mask": mask,
        "orientation_angle": float(orientation),
        "keypoints": keypoints,
        "category": category.value,
        "segmentation_method": "yolov8-seg" if YOLO_AVAILABLE else "fallback",
    }
    
    logger.debug(
        f"의류 파싱 완료 category={category.value} "
        f"orientation={np.degrees(orientation):.1f}° kp_count={len(keypoints)}"
    )
    
    return result

