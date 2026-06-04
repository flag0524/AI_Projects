"""핏 엔진 — 포즈 기반 동적 파라미터 계산

개선 사항:
- 포즈 각도 분석으로 신체 기울기 감지
- 체형 분류 (슬림, 정상, 플러스)
- 카테고리별 템플릿 기반 적응형 계산
- 의류 타입별 핏 보정
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
import numpy as np
from loguru import logger

from schemas import Category, FitMode, GarmentSize, FitReport

# 악세서리는 핏 계산 불필요 — 호출 시 즉시 반환
_ACCESSORY_PARAMS = None

# ── 표준 마네킹 치수 (cm, 여성 표준 마네킹 기준) ──────────────────────────
STANDARD_MANNEQUIN_CM = {
    "chest": 82.0,
    "waist": 62.0,
    "hip": 90.0,
    "shoulder": 38.0,
    "height": 170.0,
}

# 카테고리별 피팅 기준 부위
CATEGORY_ANCHOR = {
    Category.top:    ["shoulder", "chest", "total_length"],
    Category.bottom: ["waist", "hip", "total_length"],
    Category.dress:  ["shoulder", "chest", "waist", "total_length"],
}

# 체형 분류 기준 (BMI-like)
def _classify_body_type(measurements: dict) -> str:
    """체형 분류 (슬림, 정상, 플러스).
    
    인자:
        measurements: {"chest_circumference": 0.5, "waist_circumference": 0.4, ...}
    """
    chest = measurements.get("chest_circumference", 0.483)
    waist = measurements.get("waist_circumference", 0.365)
    hip = measurements.get("hip_circumference", 0.529)
    
    # 정규화된 값이므로 0.4~0.6 범위를 정상으로 가정
    avg_ratio = (chest + waist + hip) / 3
    
    if avg_ratio < 0.45:
        return "slim"
    elif avg_ratio > 0.55:
        return "plus"
    else:
        return "normal"


def _calculate_pose_angle(keypoints: np.ndarray) -> dict:
    """포즈에서 신체 각도 계산.
    
    반환:
        {
            "shoulder_tilt": 어깨 기울기 (라디안),
            "torso_lean": 몸통 기울기,
            "pose_confidence": 신뢰도 (0~1)
        }
    """
    try:
        # COCO 포즈: 2=R shoulder, 5=L shoulder, 1=neck, 8=R hip, 11=L hip
        angles = {}
        confidence = 0.0
        
        if keypoints[2, 2] > 0.3 and keypoints[5, 2] > 0.3:
            # 어깨 기울기
            dy = keypoints[2, 1] - keypoints[5, 1]
            dx = keypoints[2, 0] - keypoints[5, 0]
            angles["shoulder_tilt"] = np.arctan2(dy, dx)
            confidence += 0.5
        
        if keypoints[1, 2] > 0.3 and keypoints[8, 2] > 0.3:
            # 몸통 기울기 (목 -> 오른쪽 엉덩이)
            dy = keypoints[8, 1] - keypoints[1, 1]
            dx = keypoints[8, 0] - keypoints[1, 0]
            angles["torso_lean"] = np.arctan2(dy, dx)
            confidence += 0.5
        
        return {
            "shoulder_tilt": angles.get("shoulder_tilt", 0.0),
            "torso_lean": angles.get("torso_lean", 0.0),
            "pose_confidence": confidence,
        }
    except Exception:
        return {
            "shoulder_tilt": 0.0,
            "torso_lean": 0.0,
            "pose_confidence": 0.0,
        }


# 여유율 -> 핏 라벨 (개선된 버전)
def _ease_label(ease_cm: float) -> str:
    """여유율을 핏 라벨로 변환."""
    if ease_cm < -2:
        return "극타이트핏"
    elif ease_cm < 4:
        return "타이트핏"
    elif ease_cm < 10:
        return "레귤러핏"
    elif ease_cm < 18:
        return "루즈핏"
    else:
        return "오버핏"


# 길이 랜드마크 (개선된 버전)
def _length_landmark(total_length_cm: float, height_cm: float = 170.0) -> str:
    """길이를 랜드마크로 변환."""
    ratio = total_length_cm / height_cm
    if ratio < 0.30:
        return "배꼽위"
    elif ratio < 0.38:
        return "허리"
    elif ratio < 0.48:
        return "엉덩이"
    elif ratio < 0.58:
        return "허벅지"
    elif ratio < 0.68:
        return "무릎"
    elif ratio < 0.80:
        return "종아리"
    else:
        return "발목"


@dataclass
class FitParams:
    """피팅 파라미터 (확장된 버전).
    
    속성:
        ease_ratio: 여유율 (상대값, 0=레귤러, -0.1~0.4)
        drape_intensity: 드레이프 강도 (0~1)
        length_ratio: 옷자락 위치 (0~1)
        warping_strength: 워핑 강도 (0.8~1.3)
        body_type: 체형 분류 (slim/normal/plus)
        pose_angle_correction: 포즈 보정 각도 (라디안)
    """
    ease_ratio: float = 0.0
    drape_intensity: float = 0.5
    length_ratio: float = 0.5
    warping_strength: float = 1.0
    body_type: str = "normal"
    pose_angle_correction: float = 0.0


class FitEngine:
    """포즈 기반 동적 핏 엔진."""
    
    def __init__(self, category: Category):
        self.category = category

    def compute(
        self,
        garment_size: Optional[GarmentSize],
        body_measurements: dict,
        fit_mode: FitMode,
        pose_data: Optional[dict] = None,
    ) -> tuple[FitParams, FitReport]:
        """피팅 파라미터 계산.
        
        인자:
            garment_size: 의류 치수
            body_measurements: 신체 측정값 (정규화)
            fit_mode: 핏 모드
            pose_data: 포즈 데이터 (optional, 포즈 기반 보정에 사용)
        """
        if self.category == Category.accessory:
            return FitParams(), FitReport(fit_label="악세서리", estimated=True)

        # 마네킹 체형 (상대값 → cm)
        body = self._relative_to_cm(body_measurements)
        
        # 체형 분류
        body_type = _classify_body_type(body_measurements)
        
        # 포즈 분석 (있으면)
        pose_angles = {}
        if pose_data and "keypoints" in pose_data:
            pose_angles = _calculate_pose_angle(pose_data["keypoints"])
        
        # 모드별 기본 여유율
        MODE_EASE = {FitMode.tight: 2.0, FitMode.regular: 8.0, FitMode.loose: 15.0}
        default_ease = MODE_EASE.get(fit_mode, 8.0)
        
        # 체형에 따른 여유율 조정
        body_type_adjustment = {
            "slim": 0.0,      # 기본값
            "normal": 2.0,    # +2cm
            "plus": 4.0,      # +4cm
        }
        default_ease += body_type_adjustment.get(body_type, 0.0)

        g = self._normalize_units(garment_size) if garment_size is not None else {}

        def garment_val(part: str) -> tuple[float, bool]:
            v = g.get(part)
            if v:
                return v, False
            return body.get(part, 0.0) + default_ease, True

        chest_g, est_c = garment_val("chest")
        waist_g, est_w = garment_val("waist")
        hip_g, est_h = garment_val("hip")
        estimated = garment_size is None or est_c or est_w or est_h

        chest_ease = chest_g - body.get("chest", 0.0)
        waist_ease = waist_g - body.get("waist", 0.0)
        hip_ease = hip_g - body.get("hip", 0.0)

        total_len = (g.get("total_length")
                     or {"top": 65, "bottom": 95, "dress": 105}.get(self.category.value, 65))
        height_cm = 170.0

        # 카테고리별 대표 여유율
        primary_ease = waist_ease if self.category == Category.bottom else chest_ease
        fit_label = _ease_label(primary_ease)
        landmark = _length_landmark(total_len, height_cm)

        ref = body.get("chest", 82.0) or 82.0
        ease_ratio = max(min(primary_ease / max(ref, 1.0), 0.4), -0.1)
        
        # 포즈 기반 드레이프 강도 조정
        drape = {FitMode.tight: 0.2, FitMode.regular: 0.5, FitMode.loose: 0.85}.get(fit_mode, 0.5)
        if primary_ease >= 18:
            drape = max(drape, 0.85)
        
        # 포즈가 기울어있으면 드레이프 강도 증가
        if pose_angles and pose_angles.get("pose_confidence", 0) > 0:
            shoulder_tilt = abs(pose_angles.get("shoulder_tilt", 0.0))
            if shoulder_tilt > 0.1:  # 5도 이상
                drape += 0.1 * shoulder_tilt
        
        length_ratio = max(min(total_len / height_cm, 0.95), 0.1)

        # 워핑 강도 계산 (체형 기반)
        size_diff_ratio = primary_ease / max(ref, 1.0)
        warping_strength = 1.0 + (size_diff_ratio * 0.5)
        warping_strength = max(0.8, min(warping_strength, 1.3))
        
        # 포즈 기반 워핑 강도 보정
        if pose_angles and pose_angles.get("pose_confidence", 0) > 0:
            torso_lean = abs(pose_angles.get("torso_lean", 0.0))
            if torso_lean > 0.1:
                warping_strength *= (1.0 + 0.1 * torso_lean)

        params = FitParams(
            ease_ratio=ease_ratio,
            drape_intensity=min(drape, 1.0),
            length_ratio=length_ratio,
            warping_strength=warping_strength,
            body_type=body_type,
            pose_angle_correction=pose_angles.get("shoulder_tilt", 0.0),
        )
        
        report = FitReport(
            chest_ease_cm=round(chest_ease, 1),
            waist_ease_cm=round(waist_ease, 1),
            hip_ease_cm=round(hip_ease, 1),
            length_landmark=landmark,
            fit_label=fit_label,
            estimated=estimated,
            warnings=self._generate_warnings(primary_ease, body_type, fit_mode),
        )
        
        logger.debug(
            f"핏 계산: label={fit_label} body_type={body_type} "
            f"chest_ease={chest_ease:.1f} pose_confidence={pose_angles.get('pose_confidence', 0):.1f}"
        )
        
        return params, report

    def _generate_warnings(self, ease_cm: float, body_type: str, fit_mode: FitMode) -> list[str]:
        """피팅 경고 메시지 생성."""
        warnings = []
        
        if ease_cm < -5 and fit_mode != FitMode.tight:
            warnings.append("매우 팽팽할 수 있습니다")
        elif ease_cm > 25 and fit_mode != FitMode.loose:
            warnings.append("과도하게 헐거울 수 있습니다")
        
        if body_type == "plus" and fit_mode == FitMode.tight:
            warnings.append("체형 대비 핏이 타이트할 수 있습니다")
        
        return warnings


    @staticmethod
    def _normalize_units(gs: GarmentSize) -> dict:
        """..."""
        factor = 2.54 if gs.unit == "in" else 1.0
        return {
            "chest":        (gs.chest or 0) * factor or None,
            "waist":        (gs.waist or 0) * factor or None,
            "hip":          (gs.hip or 0) * factor or None,
            "shoulder":     (gs.shoulder or 0) * factor or None,
            "total_length": (gs.total_length or 0) * factor or None,
            "sleeve":       (gs.sleeve or 0) * factor or None,
        }

    @staticmethod
    def _relative_to_cm(body: dict, ref_height_cm: float = 170.0) -> dict:
        """..."""
        # 측정값은 이미지 대비 정규화된 비율(total_height≈0.85, *_circumference≈0.2~0.5).
        # scale = 실제키(cm) / 정규화키 → 비율을 cm로 환산. (ref_height_cm 이중곱 제거)
        h = body.get("total_height", 1.0) or 1.0
        scale = ref_height_cm / max(h, 0.01)
        return {
            "chest":    body.get("chest_circumference", 0.483) * scale,
            "waist":    body.get("waist_circumference", 0.365) * scale,
            "hip":      body.get("hip_circumference", 0.529) * scale,
            "shoulder": body.get("shoulder_width", 0.224) * scale,
        }
