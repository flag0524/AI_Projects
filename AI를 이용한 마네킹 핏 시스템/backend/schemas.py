from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class Category(str, Enum):
    top       = "top"
    bottom    = "bottom"
    dress     = "dress"
    accessory = "accessory"


class FitMode(str, Enum):
    auto = "auto"
    tight = "tight"
    regular = "regular"
    loose = "loose"


class GarmentSize(BaseModel):
    unit: str = "cm"                          # "cm" | "in"
    total_length: Optional[float] = None      # 총장 (상의/원피스/하의)
    chest: Optional[float] = None             # 가슴 둘레
    shoulder: Optional[float] = None          # 어깨 너비
    sleeve: Optional[float] = None            # 소매 길이
    waist: Optional[float] = None             # 허리 둘레
    hip: Optional[float] = None               # 엉덩이 둘레
    inseam: Optional[float] = None            # 인심 (하의)


class TryOnOptions(BaseModel):
    remove_background: bool = False
    upscale: bool = False
    seed: Optional[int] = None


class TryOnRequest(BaseModel):
    category: Category
    garment_size: Optional[GarmentSize] = None
    fit_mode: FitMode = FitMode.auto
    num_candidates: int = Field(default=1, ge=1, le=4)
    options: TryOnOptions = TryOnOptions()


# ---------- 응답 ----------

class JobStatus(str, Enum):
    queued = "queued"
    processing = "processing"
    succeeded = "succeeded"
    failed = "failed"


class FitReport(BaseModel):
    chest_ease_cm: Optional[float] = None
    waist_ease_cm: Optional[float] = None
    hip_ease_cm: Optional[float] = None
    length_landmark: Optional[str] = None     # e.g. "hip", "thigh", "knee"
    fit_label: Optional[str] = None           # "루즈핏", "레귤러핏" 등
    warnings: list[str] = []
    estimated: bool = False                   # 치수 추정값 사용 여부


class ResultItem(BaseModel):
    image_url: str
    seed: int
    fit_report: FitReport


class JobResponse(BaseModel):
    job_id: str
    status: JobStatus
    results: list[ResultItem] = []
    error: Optional[str] = None
