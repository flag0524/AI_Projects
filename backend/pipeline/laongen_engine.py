"""
LaonGEN 하이브리드 엔진.

마네킹/옷걸이 제품 사진 → 자연스러운 모델 착용 컷.

흐름:
  ┌─────────────────────────────────────────────────────────┐
  │ 1. 전처리 (로컬, 무료)                                   │
  │    - 제품 사진에서 의류만 깨끗하게 분리 (rembg)          │
  │    - 옷걸이/마네킹 잔여물 제거                           │
  ├─────────────────────────────────────────────────────────┤
  │ 2. 생성 (클라우드 try-on diffusion)                     │
  │    - 표준 모델 템플릿 + 분리된 의류 → 착용 컷           │
  │    - 여러 의류는 순차 try-on (상의 → 하의)              │
  ├─────────────────────────────────────────────────────────┤
  │ 3. 폴백 (API 불가 시)                                   │
  │    - 기존 절차적 합성 파이프라인으로 전환               │
  └─────────────────────────────────────────────────────────┘
"""
import os
import numpy as np
import cv2
from PIL import Image

from backend.pipeline.bg_remover import remove_background
from backend.pipeline.preprocessor import preprocess
from backend.pipeline import generative_provider as gen
from backend.pipeline import hf_provider as hf
from backend.pipeline import higgsfield_provider as hgf
from backend.pipeline.generative_provider import GenerativeBillingError
from backend.pipeline.body_analyzer import get_mask_from_image, detect_body_regions
from backend.pipeline.garment_warper import warp_garment, fallback_affine_warp
from backend.pipeline.composer import compose

# 기본 모델 템플릿 경로 (저장소 번들)
_TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "..", "assets", "templates")
_DEFAULT_TEMPLATE = os.path.join(_TEMPLATE_DIR, "model_neutral.jpg")


# ── 1. 전처리: 의류 깔끔 분리 ──────────────────────────────────
def isolate_garment(product_img: Image.Image, size: int = 768) -> Image.Image:
    """
    제품 사진(마네킹/옷걸이 착용)에서 의류만 분리.
    배경 제거 후 최대 연결 요소만 남겨 옷걸이/잔여물 제거.
    """
    resized, _ = preprocess(product_img.convert("RGBA"))
    nobg       = remove_background(resized)

    arr   = np.array(nobg.convert("RGBA"))
    alpha = arr[:, :, 3]
    _, mask = cv2.threshold(alpha, 30, 255, cv2.THRESH_BINARY)

    # 최대 연결 요소만 유지 (옷걸이 고리 등 작은 조각 제거)
    n, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    if n > 1:
        largest = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
        clean   = np.where(labels == largest, 255, 0).astype(np.uint8)
        clean   = cv2.morphologyEx(
            clean, cv2.MORPH_CLOSE,
            cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))
        )
        arr[:, :, 3] = clean

    return Image.fromarray(arr, "RGBA")


# ── 2. 모델 템플릿 ─────────────────────────────────────────────
def make_default_model_template(size: int = 768) -> Image.Image:
    """
    기본 모델 템플릿 반환.
    저장소 번들 모델 사진이 있으면 사용, 없으면 중립 배경.
    """
    if os.path.exists(_DEFAULT_TEMPLATE):
        return Image.open(_DEFAULT_TEMPLATE).convert("RGB")
    return Image.new("RGB", (size, size), (235, 232, 228))


# ── 3. 하이브리드 생성 ─────────────────────────────────────────
def generate_model_shot(
    garments:       list[tuple[Image.Image, str]],
    model_template: Image.Image = None,
    mannequin_img:  Image.Image = None,
    subject:        str = "model",
) -> tuple[Image.Image, str]:
    """
    의류 목록으로 모델 착용 컷 생성.

    Args:
        garments       : [(의류 이미지, 타입), ...]
        model_template : 기준 figure 사진 (없으면 기본 모델 템플릿)
        mannequin_img  : 폴백용 마네킹 이미지
        subject        : "model"(실제 모델) | "mannequin"(마네킹 디스플레이).
                         생성형 백엔드 프롬프트에만 영향, 폴백은 무관.

    Returns:
        (결과 이미지, 사용된 방식 "higgsfield" | "hf" | "generative" | "procedural")

    백엔드 캐스케이드 (GEN_BACKEND):
      - "auto" / "higgsfield" : higgsfield → hf → replicate → 절차적
      - "hf"                  : hf → 절차적
      - "replicate"           : replicate → 절차적
    각 백엔드가 Unavailable이면 다음으로 폴백. 크레딧 부족(BillingError)은
    폴백하지 않고 그대로 전파 (api/generate.py가 402 처리).
    """
    # 상의를 먼저, 하의를 마지막에 적용.
    # (상의가 길게 내려와도 하의 try-on이 마지막에 허리 아래를 덮어 보정)
    order    = {"top": 0, "dress": 1, "bottom": 2, "accessory": 3}
    ordered  = sorted(garments, key=lambda x: order.get(x[1], 9))
    backend  = os.environ.get("GEN_BACKEND", "hf").strip().lower()

    chain = _CHAINS.get(backend, _CHAINS["hf"])

    # 마네킹은 Higgsfield만 입힐 수 있다 (Leffa/Replicate는 인체 필요 → 항상 실패).
    # 불필요한(유료 포함) 시도를 건너뛰고 바로 절차적 폴백으로 가도록 체인 제한.
    if subject == "mannequin":
        chain = [c for c in chain if c == "higgsfield"]

    for name in chain:
        is_avail, runner, exc_types, method = _RUNNERS[name]
        if not is_avail():
            continue
        try:
            return runner(ordered, model_template, subject), method
        except GenerativeBillingError:
            raise                       # 크레딧 부족은 폴백 금지, 그대로 전파
        except exc_types:
            continue                    # 다음 백엔드로 캐스케이드

    # 절차적 폴백 (모든 생성형 불가 시)
    return _procedural_fallback(garments, mannequin_img), "procedural"


# ── 백엔드 러너 ────────────────────────────────────────────────
def _run_higgsfield(ordered, model_template, subject="model"):
    """Higgsfield: 다중 의류 단일-호출 풀코디 (2026-06-09 검증: 순차 drift 우회).

    subject="mannequin"이면 model_template(마네킹)을 입힌 디스플레이 컷 생성.
    """
    figure   = (model_template or make_default_model_template()).convert("RGB")
    garments = [
        (garment_img.convert("RGB"), _desc(gtype), hgf.to_category(gtype))
        for garment_img, gtype in ordered
    ]
    return hgf.generate_tryon_multi(garments, figure, subject=subject)


def _run_hf(ordered, model_template, subject="model"):
    """HF Leffa/IDM-VTON: 흰 배경 제품 사진 직접 처리 (분리 불필요), 순차 적용.

    Leffa는 인체(DensePose) 필요 — subject는 무시(마네킹은 생성 실패→캐스케이드).
    """
    current = (model_template or make_default_model_template()).convert("RGB")
    for garment_img, gtype in ordered:
        current = hf.generate_tryon(
            human_img    = current,
            garment_img  = garment_img.convert("RGB"),
            garment_type = gtype,
            garment_des  = _desc(gtype),
        )
    return current


def _run_replicate(ordered, model_template, subject="model"):
    """Replicate IDM-VTON: 의류 분리 후 순차 적용 (subject 무시)."""
    current = model_template or make_default_model_template()
    for garment_img, gtype in ordered:
        isolated = isolate_garment(garment_img)
        current  = gen.generate_tryon(
            garment_img    = isolated,
            model_template = current,
            garment_desc   = _desc(gtype),
            category       = gen.to_category(gtype),
        )
    return current


# (is_available, runner, 폴백 트리거 예외, method 라벨)
# is_available은 lambda로 감싸 런타임 조회 (테스트 monkeypatch 가능)
_RUNNERS = {
    "higgsfield": (lambda: hgf.is_available(), _run_higgsfield, (hgf.HiggsfieldUnavailable,), "higgsfield"),
    "hf":         (lambda: hf.is_available(),  _run_hf,         (hf.HFUnavailable,),          "hf"),
    "replicate":  (lambda: gen.is_available(), _run_replicate,  (gen.GenerativeUnavailable,), "generative"),
}

_CHAINS = {
    "auto":       ["higgsfield", "hf", "replicate"],
    "higgsfield": ["higgsfield", "hf", "replicate"],
    "hf":         ["hf"],
    "replicate":  ["replicate"],
}


def _desc(garment_type: str) -> str:
    return {
        "top":       "a stylish top garment",
        "bottom":    "a pair of pants",
        "dress":     "a dress",
        "accessory": "an accessory",
    }.get(garment_type, "a clothing item")


def _procedural_fallback(
    garments:      list[tuple[Image.Image, str]],
    mannequin_img: Image.Image,
) -> Image.Image:
    """API 불가 시 기존 절차적 합성."""
    if mannequin_img is None:
        # 마네킹이 없으면 첫 의류를 그대로 반환
        return garments[0][0].convert("RGB") if garments else make_default_model_template()

    mann_base, _ = preprocess(mannequin_img.convert("RGBA"))
    mann_nobg    = remove_background(mann_base)
    body_mask    = get_mask_from_image(mann_nobg)
    body_regions = detect_body_regions(body_mask)

    warped = {}
    for garment_img, gtype in garments:
        g_resized, _ = preprocess(garment_img.convert("RGBA"))
        g_nobg       = remove_background(g_resized)
        try:
            w = warp_garment(g_nobg, gtype, body_regions,
                             mannequin_nobg=mann_nobg, body_mask=body_mask)
        except Exception:
            w = fallback_affine_warp(g_nobg, gtype, body_regions)
        warped[gtype] = w

    return compose(mann_base, warped, mann_nobg)
