from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    # 서버
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False

    # 스토리지
    upload_dir: Path = Path("storage/uploads")
    result_dir: Path = Path("storage/results")
    max_image_size_mb: int = 20

    # 모델
    device: str = "cuda"           # "cuda" | "cpu"
    idm_vton_model_id: str = "yisol/IDM-VTON"
    model_cache_dir: Path = Path("storage/models")

    # 엔진 티어 (0=자동감지, 1=IDM-VTON, 2=SD1.5경량, 3=CV워핑)
    engine_tier: int = 0

    # 작업 큐
    redis_url: str = "redis://localhost:6379/0"
    job_ttl_seconds: int = 3600   # 결과 보관 1시간

    # 이미지 생성
    default_num_steps: int = 30
    default_guidance_scale: float = 2.0
    max_candidates: int = 4

    # 포스프로세싱
    enable_postprocess: bool = True
    enable_blend: bool = True
    enable_color_harmony: bool = True
    enable_denoise: bool = True
    enable_sharpening: bool = True

    # 자동 검증 및 재시도
    auto_retry_on_low_quality: bool = True
    quality_threshold: int = 70
    max_retries: int = 2

    # YOLOv8 세그멘테이션
    segmentation_model: str = "yolov8l-seg"

    class Config:
        env_file = ".env"


settings = Settings()

# 디렉토리 자동 생성
settings.upload_dir.mkdir(parents=True, exist_ok=True)
settings.result_dir.mkdir(parents=True, exist_ok=True)
settings.model_cache_dir.mkdir(parents=True, exist_ok=True)

