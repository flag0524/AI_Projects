"""..."""
from __future__ import annotations
from loguru import logger


def detect_tier() -> int:
    """현재 PC 사양(하드웨어 감지)에 따라 권장 엔진 티어를 반환."""
    try:
        from pipeline.hardware import detect_hardware
        h = detect_hardware()
        logger.info(
            f"엔진 감지: GPU {h['gpu_name'] or '없음'} "
            f"(VRAM {h['vram_gb']}GB) → Tier {h['recommended_tier']}"
        )
        return h["recommended_tier"]
    except Exception as e:
        logger.warning(f"하드웨어 감지 실패({e}) -> Tier 3")
        return 3


def get_engine(tier: int | None = None):
    """..."""
    if tier is None:
        tier = detect_tier()

    # Tier 1/2 는 무거운 의존성(torch/diffusers·GPU)이 필요하다.
    # 설치/하드웨어가 없으면 크래시 대신 Tier 3(CV 워핑)로 자동 폴백한다.
    if tier == 1:
        try:
            from pipeline.tryon_model import TryOnModel
            return TryOnModel(), 1
        except Exception as e:
            logger.warning(f"Tier 1(IDM-VTON) 사용 불가({e}) → Tier 3로 폴백")
            tier = 3

    if tier == 2:
        try:
            import torch  # noqa: F401  (없으면 추론 전에 미리 폴백)
            from pipeline.lightweight_engine import LightweightEngine
            return LightweightEngine(mode="sd_inpaint"), 2
        except Exception as e:
            logger.warning(f"Tier 2(SD1.5) 사용 불가({e}) → Tier 3로 폴백")
            tier = 3

    from pipeline.lightweight_engine import LightweightEngine
    return LightweightEngine(mode="cv_warp"), 3
