"""..."""
from __future__ import annotations
from pathlib import Path
from typing import Optional

import numpy as np
from PIL import Image, ImageFilter, ImageEnhance
from loguru import logger

from pipeline.fit_engine import FitParams

# ── rembg(ML 배경 제거) 세션 캐시 ──────────────────────────────────────
_REMBG_SESSION = "uninit"  # "uninit"=미시도, None=사용불가, 그 외=세션객체


def _rembg_mask(img_rgb: np.ndarray):
    """rembg(U2Net, CPU)로 전경 알파 마스크(255) 추출. 미설치/실패 시 None."""
    global _REMBG_SESSION
    try:
        if _REMBG_SESSION == "uninit":
            from rembg import new_session
            _REMBG_SESSION = new_session("u2net")
            logger.info("rembg 세션 초기화 완료 (U2Net, CPU)")
        if _REMBG_SESSION is None:
            return None
        from rembg import remove
        out = remove(img_rgb, session=_REMBG_SESSION)
        if out.ndim == 3 and out.shape[2] == 4:
            return (out[:, :, 3] > 30).astype(np.uint8) * 255
        return None
    except Exception as e:
        logger.debug(f"rembg 사용 불가({e}) — CV 폴백")
        _REMBG_SESSION = None
        return None


# ─────────────────────────────────────────────
# Tier 2 — SD 1.5 경량 인페인팅
# ─────────────────────────────────────────────

class _SD15InpaintEngine:
    _pipe = None

    def _load(self):
        if self._pipe is not None:
            return
        import torch
        from diffusers import StableDiffusionInpaintPipeline

        logger.info("SD 1.5 인페인팅 로딩 (Tier 2)...")
        self._pipe = StableDiffusionInpaintPipeline.from_pretrained(
            "runwayml/stable-diffusion-inpainting",
            torch_dtype=torch.float16,
            safety_checker=None,
        )
        self._pipe.enable_model_cpu_offload()   # VRAM 절약
        self._pipe.enable_attention_slicing()    # 메모리 분할
        try:
            self._pipe.enable_xformers_memory_efficient_attention()
        except Exception:
            pass
        logger.info("SD 1.5 로드 완료")

    def infer(
        self,
        mannequin_img: Image.Image,
        garment_img: Image.Image,
        agnostic_mask: Image.Image,
        category: str,
        fit_params: FitParams,
        seed: int,
        num_steps: int = 20,
    ) -> Image.Image:
        self._load()

        import torch
        gen = torch.Generator("cpu").manual_seed(seed)

        # 해상도를 512×512로 낮춰 VRAM 절약 (결과 후 원본 크기로 업스케일)
        W, H = 512, 512
        person_small  = mannequin_img.resize((W, H), Image.LANCZOS)
        garment_small = garment_img.resize((W, H), Image.LANCZOS)
        mask_small    = agnostic_mask.resize((W, H), Image.NEAREST)

        prompt = (
            f"a mannequin wearing a {category}, "
            "studio lighting, white background, photorealistic"
        )
        neg = "deformed, blurry, low quality, cartoon"

        result_small = self._pipe(
            prompt=prompt,
            negative_prompt=neg,
            image=person_small,
            mask_image=mask_small,
            num_inference_steps=num_steps,
            guidance_scale=7.5,
            generator=gen,
            width=W,
            height=H,
        ).images[0]

        # 원본 해상도로 복원
        result = result_small.resize(mannequin_img.size, Image.LANCZOS)
        return result


# ─────────────────────────────────────────────
# Tier 3 — OpenCV TPS 워핑 + 알파 블렌딩
# ─────────────────────────────────────────────

class _CVWarpEngine:
    """..."""

    def infer(
        self,
        mannequin_img: Image.Image,
        garment_img: Image.Image,
        agnostic_mask: Image.Image,
        category: str,
        fit_params: FitParams,
        keypoints: np.ndarray,
        seed: int,
    ) -> Image.Image:
        import cv2

        mannequin_np = np.array(mannequin_img)
        garment_np   = np.array(garment_img.convert("RGB"))
        mask_np      = np.array(agnostic_mask.convert("L"))

        if category == "accessory":
            return self._composite_accessory(
                mannequin_np, garment_np, keypoints
            )

        return self._warp_and_blend(
            mannequin_np, garment_np, category, fit_params, keypoints
        )

    # ── 의류 워핑 ──────────────────────────────────────────────────────

    def _warp_and_blend(
        self,
        mannequin: np.ndarray,
        garment: np.ndarray,
        category: str,
        fit_params: FitParams,
        keypoints: np.ndarray,
    ) -> Image.Image:
        """키포인트로 잡은 신체 영역에 의류를 배치하고 색을 보존해 합성한다."""
        import cv2

        H, W = mannequin.shape[:2]

        # ── 1) 마네킹 실루엣 마스크 (모서리 배경 flood-fill 제거) ────────
        body_mask = self._foreground_mask(mannequin)

        # ── 2) 실루엣에서 '옷 입는 폼'(어깨~몸통/다리)만 추출 ────────────
        #     얇은 거치대/스탠드(드레스폼 받침봉)는 최대 너비 대비 가늘어 제외한다.
        widths = (body_mask > 127).sum(axis=1).astype(np.int32)
        rows = np.where(widths > 0)[0]
        if len(rows) >= H * 0.05:
            form_top = int(rows.min())
            maxw = int(widths.max())
            wide = np.where(widths >= max(1, int(0.35 * maxw)))[0]
            form_bot = int(wide.max()) if len(wide) else int(rows.max())
        else:
            form_top, form_bot = int(H * 0.10), int(H * 0.95)
        span = max(1, form_bot - form_top)

        # ── 3) 해부학적 기준선: 실루엣 bbox 기준 (인체 표준 비율) ────────
        #     Tier 3에는 신뢰할 포즈 모델이 없어(폴백 키포인트는 프레임 기준이라
        #     figure 위치와 어긋남) 실루엣 bbox에 표준 비율을 적용하는 것이 견고하다.
        #     키포인트가 '실루엣 내부'에 있고 신뢰도가 높을 때만 우선 사용.
        shoulder_y = form_top + span * 0.10
        hip_y      = form_top + span * 0.50
        knee_y     = form_top + span * 0.72
        ankle_y    = form_top + span * 0.95

        # ── 4) 카테고리별 세로 영역 (해부학적 범위) ─────────────────────
        if category == "bottom":
            top_y, bot_y = hip_y, ankle_y
        elif category == "dress":
            top_y, bot_y = shoulder_y, max(knee_y, (hip_y + ankle_y) / 2)
        else:  # top — 어깨에서 엉덩이까지만 (다리 침범 방지)
            top_y, bot_y = shoulder_y, hip_y + (hip_y - shoulder_y) * 0.12

        # 길이 보정 (옷자락 위치)
        bot_y += (bot_y - top_y) * (fit_params.length_ratio - 0.5) * 0.2
        top_y = int(max(0, min(H - 2, top_y)))
        bot_y = int(max(top_y + 2, min(H, bot_y)))
        # 결과 크롭용 관심영역(폼/의류 범위, 스탠드 제외)
        self._roi_y = (max(0, min(top_y, form_top)), min(H, max(bot_y, form_bot)))

        # ── 4) 의류를 배경에서 분리하고 자기 bbox로 크롭 ────────────────
        #     흰 옷도 보존되도록 모서리 flood-fill 기반 전경 분리 사용
        g_alpha = self._foreground_mask(garment)
        gy, gx = np.where(g_alpha > 127)
        if len(gy) == 0:
            return Image.fromarray(mannequin)
        gy0, gy1, gx0, gx1 = gy.min(), gy.max(), gx.min(), gx.max()
        g_crop  = garment[gy0:gy1 + 1, gx0:gx1 + 1]
        ga_crop = g_alpha[gy0:gy1 + 1, gx0:gx1 + 1]

        # ── 5) 의류 비율을 유지한 채 토르소 영역에 맞춰 스케일·배치 ───────
        #     행별 풀너비 stretch는 옷이 '천으로 감싼' 듯 어색해지므로 지양하고,
        #     원본 의류의 칼라·소매·단추·주름 등 형태를 보존한 채 배치한다.
        ease = max(0.0, float(fit_params.ease_ratio))
        region_h = bot_y - top_y

        # 의류 폭은 '몸통(torso) 너비'를 기준으로 한다.
        #     전체 구간 최대폭은 옆으로 벌어진 팔/손까지 포함돼 옷이 가로로 늘어난다.
        #     영역 대부분의 행에서 채워지는 '세로 기둥'(=몸통)만 컬럼 커버리지로 추출하고,
        #     비스듬히 가로지르는 팔(컬럼별 커버리지 낮음)은 배제한다.
        sub = body_mask[top_y:bot_y] > 127
        col_cov = sub.mean(axis=0)
        torso_cols = np.where(col_cov >= 0.70)[0]
        if len(torso_cols) < 2:
            torso_cols = np.where(col_cov >= 0.50)[0]
        if len(torso_cols) < 2:
            xs_any = np.where(sub.any(axis=0))[0]
            if len(xs_any) < 2:
                return Image.fromarray(mannequin)
            torso_cols = xs_any
        bx0, bx1 = int(torso_cols.min()), int(torso_cols.max())
        body_w  = max(2, bx1 - bx0)
        body_cx = (bx0 + bx1) // 2

        gch, gcw = ga_crop.shape
        target_w = int(body_w * (1.04 + 0.30 * ease))     # 신체 너비 + 약간의 여유
        scale    = target_w / gcw
        target_h = int(gch * scale)
        # 의류가 토르소 영역을 충분히 덮도록 최소 높이 보정 (상단만 덮이는 현상 방지)
        min_h = int(region_h * 0.90)
        if target_h < min_h:
            scale = min_h / gch
            target_h, target_w = min_h, int(gcw * scale)
        max_h = int(region_h * 1.12)
        if target_h > max_h:                               # 영역보다 길면 높이 기준 스케일
            scale = max_h / gch
            target_h, target_w = max_h, int(gcw * scale)
        target_w, target_h = max(2, target_w), max(2, target_h)

        g_rs = cv2.resize(g_crop,  (target_w, target_h), interpolation=cv2.INTER_LINEAR)
        a_rs = cv2.resize(ga_crop, (target_w, target_h), interpolation=cv2.INTER_LINEAR)

        # 가로 중앙=몸 중심, 세로 상단=영역 시작에 배치
        px0, py0 = body_cx - target_w // 2, top_y
        dx0, dy0 = max(0, px0), max(0, py0)
        dx1, dy1 = min(W, px0 + target_w), min(H, py0 + target_h)
        if dx1 <= dx0 or dy1 <= dy0:
            return Image.fromarray(mannequin)
        sx0, sy0 = dx0 - px0, dy0 - py0
        warp_rgb = np.zeros((H, W, 3), np.uint8)
        warped_a = np.zeros((H, W), np.uint8)
        warp_rgb[dy0:dy1, dx0:dx1] = g_rs[sy0:sy0 + (dy1 - dy0), sx0:sx0 + (dx1 - dx0)]
        warped_a[dy0:dy1, dx0:dx1] = a_rs[sy0:sy0 + (dy1 - dy0), sx0:sx0 + (dx1 - dx0)]

        # 의류를 마네킹 실루엣 안으로 제한 (배경/허공 삐져나감 방지)
        warped_a = np.minimum(warped_a, body_mask)
        if int(warped_a.max()) == 0:
            return Image.fromarray(mannequin)

        # 가장자리 페더링
        feather = cv2.GaussianBlur(warped_a.astype(np.float32), (0, 0), sigmaX=2.0) / 255.0
        feather = np.clip(feather, 0.0, 1.0)

        # ── 6) 색 보존 + 마네킹 국부 음영 미세 적용 ─────────────────────
        g_shaded = self._apply_shading(warp_rgb, mannequin)

        # ── 7) 합성 ────────────────────────────────────────────────────
        result = mannequin.astype(np.float32)
        f = feather[:, :, np.newaxis]
        result = g_shaded.astype(np.float32) * f + result * (1.0 - f)
        result = np.clip(result, 0, 255).astype(np.uint8)

        # 폼/의류 영역으로 크롭 → 스탠드 제외, 결과가 화면에 꽉 차게
        return self._crop_to_subject(result, body_mask, getattr(self, "_roi_y", None))

    @staticmethod
    def _crop_to_subject(img: np.ndarray, mask: np.ndarray,
                         y_range=None, margin: float = 0.06) -> Image.Image:
        """실루엣 bbox에 여백을 더해 크롭. y_range가 주어지면 그 세로 구간만 사용(스탠드 배제)."""
        H, W = img.shape[:2]
        m = mask
        if y_range is not None:
            y_lo, y_hi = int(y_range[0]), int(y_range[1])
            m = np.zeros_like(mask)
            m[y_lo:y_hi] = mask[y_lo:y_hi]
        ys, xs = np.where(m > 127)
        if len(ys) == 0:
            return Image.fromarray(img)
        bh, bw = int(ys.max() - ys.min()), int(xs.max() - xs.min())
        my, mx = int(bh * margin), int(bw * margin)
        y0 = max(0, int(ys.min()) - my); y1 = min(H, int(ys.max()) + my)
        x0 = max(0, int(xs.min()) - mx); x1 = min(W, int(xs.max()) + mx)
        return Image.fromarray(img[y0:y1, x0:x1])

    # ── 악세서리 합성 ──────────────────────────────────────────────────

    def _composite_accessory(
        self,
        mannequin: np.ndarray,
        accessory: np.ndarray,
        keypoints: np.ndarray,
    ) -> Image.Image:
        """..."""
        import cv2

        H, W = mannequin.shape[:2]
        kp = keypoints  # (18, 3)

        # 악세서리 크기: 마네킹 너비의 35% 기준
        acc_w = int(W * 0.35)
        acc_h = int(acc_w * accessory.shape[0] / max(accessory.shape[1], 1))
        accessory_resized = cv2.resize(accessory, (acc_w, acc_h), interpolation=cv2.INTER_LANCZOS4)

        # 위치 결정 (비율로 휴리스틱)
        # 악세서리 세로 비율이 0.5 이하이면 상단 배치(모자 계열), 이상이면 중단(가방 계열)
        acc_ratio = accessory.shape[0] / max(accessory.shape[1], 1)
        if acc_ratio < 0.5:
            # 가로형: 벨트/스카프 — 허리 위치
            center_x = W // 2
            hip_y = int((kp[8, 1] + kp[11, 1]) / 2) if kp[8, 2] > 0.3 else int(H * 0.52)
            cx, cy = center_x, hip_y
        elif acc_ratio > 1.5:
            # 세로형: 가방 — 옆구리
            cx = int(kp[2, 0]) + int(W * 0.1) if kp[2, 2] > 0.3 else int(W * 0.75)
            cy = int((kp[8, 1] + kp[1, 1]) / 2) if kp[8, 2] > 0.3 else int(H * 0.4)
        else:
            # 정방형: 모자 — 머리 위
            cx = W // 2
            head_y = int(kp[0, 1]) if kp[0, 2] > 0.3 else int(H * 0.08)
            cy = max(acc_h // 2, head_y - int(acc_h * 0.3))

        x0 = max(0, cx - acc_w // 2)
        y0 = max(0, cy - acc_h // 2)
        x1 = min(W, x0 + acc_w)
        y1 = min(H, y0 + acc_h)
        acc_crop_w, acc_crop_h = x1 - x0, y1 - y0
        if acc_crop_w <= 0 or acc_crop_h <= 0:
            return Image.fromarray(mannequin)

        acc_patch = accessory_resized[:acc_crop_h, :acc_crop_w]

        # 배경 제거 시도 (흰 배경 가정)
        alpha = self._make_alpha(acc_patch)

        result = mannequin.copy().astype(np.float32)
        roi = result[y0:y1, x0:x1]
        a = alpha[:, :, np.newaxis]
        blended = acc_patch.astype(np.float32) * a + roi * (1 - a)
        result[y0:y1, x0:x1] = blended

        return Image.fromarray(result.astype(np.uint8))

    # ── 유틸 ──────────────────────────────────────────────────────────

    @staticmethod
    def _foreground_mask(img: np.ndarray, tol: int = 14) -> np.ndarray:
        """전경 마스크(255). rembg(ML) 우선, 실패 시 테두리 flood-fill 폴백.

        rembg는 사진 자체의 배경(회색 등)·흰 옷도 깔끔히 분리해 사이즈 정합을 보장한다.
        """
        import cv2
        h, w = img.shape[:2]

        # 1) rembg 우선 — 사진 배경/흰옷에 강함
        m = _rembg_mask(img)
        if m is not None and int((m > 0).sum()) > 0.01 * h * w:
            fg = m
        else:
            # 2) 폴백: 테두리 전체를 시드로 균일 배경 flood-fill (비균일 배경 대응)
            bgr = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
            ff_mask = np.zeros((h + 2, w + 2), np.uint8)
            flags = 4 | (255 << 8) | cv2.FLOODFILL_MASK_ONLY | cv2.FLOODFILL_FIXED_RANGE
            lo = up = (tol, tol, tol)
            step = max(1, min(h, w) // 50)
            seeds = ([(x, 0) for x in range(0, w, step)] +
                     [(x, h - 1) for x in range(0, w, step)] +
                     [(0, y) for y in range(0, h, step)] +
                     [(w - 1, y) for y in range(0, h, step)])
            for sx, sy in seeds:
                if ff_mask[sy + 1, sx + 1] == 0:
                    cv2.floodFill(bgr.copy(), ff_mask, (sx, sy), 0, lo, up, flags)
            fg = ((ff_mask[1:-1, 1:-1] == 0).astype(np.uint8)) * 255

        # 정리 + 최대 연결 성분
        k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        fg = cv2.morphologyEx(fg, cv2.MORPH_OPEN, k, iterations=1)
        fg = cv2.morphologyEx(fg, cv2.MORPH_CLOSE, k, iterations=3)
        n, labels, stats, _ = cv2.connectedComponentsWithStats((fg > 0).astype(np.uint8), 8)
        if n > 1:
            largest = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
            fg = (labels == largest).astype(np.uint8) * 255
        return fg

    @staticmethod
    def _apply_shading(garment: np.ndarray, body_region: np.ndarray) -> np.ndarray:
        """의류의 색(색상·채도)은 보존하고, 마네킹의 국부 명암만 미세하게 입힌다."""
        import cv2
        g = garment.astype(np.float32)
        bg = cv2.cvtColor(body_region, cv2.COLOR_RGB2GRAY).astype(np.float32)
        # 평균 대비 상대 밝기 → 0.88~1.12 범위로만 변조 (과한 변색 방지)
        shade = bg / (bg.mean() + 1e-6)
        shade = np.clip(shade, 0.88, 1.12)
        shade = cv2.GaussianBlur(shade, (0, 0), sigmaX=5.0)
        return np.clip(g * shade[:, :, np.newaxis], 0, 255).astype(np.uint8)

    @staticmethod
    def _make_alpha(img: np.ndarray, white_thresh: int = 240) -> np.ndarray:
        """..."""
        gray = 0.299 * img[:, :, 0] + 0.587 * img[:, :, 1] + 0.114 * img[:, :, 2]
        alpha = (gray < white_thresh).astype(np.float32)
        import cv2
        alpha = cv2.GaussianBlur(alpha, (5, 5), 0)
        return alpha


# ─────────────────────────────────────────────
# 공개 인터페이스
# ─────────────────────────────────────────────

class LightweightEngine:
    """..."""

    def __init__(self, mode: str = "cv_warp"):
        self.mode = mode
        if mode == "sd_inpaint":
            self._engine = _SD15InpaintEngine()
        else:
            self._engine = _CVWarpEngine()
        logger.info(f"LightweightEngine 초기화: mode={mode}")

    def infer(
        self,
        mannequin_img: Image.Image,
        garment_img: Image.Image,
        pose_data: dict,
        garment_data: dict,
        fit_params: FitParams,
        seed: int = 42,
        num_steps: int = 20,
        guidance_scale: float = 7.5,
        agnostic_map: Optional[Image.Image] = None,
    ) -> Image.Image:

        category = garment_data.get("category", "top")

        # agnostic_map -> L 마스크 변환
        if agnostic_map is not None:
            ag = np.array(agnostic_map.convert("L"))
            mask_arr = ((ag > 100) & (ag < 160)).astype(np.uint8) * 255
            mask = Image.fromarray(mask_arr, mode="L")
        else:
            mask = Image.new("L", mannequin_img.size, 255)

        if self.mode == "sd_inpaint":
            return self._engine.infer(
                mannequin_img, garment_img, mask,
                category, fit_params, seed, num_steps,
            )
        else:
            return self._engine.infer(
                mannequin_img, garment_img, mask,
                category, fit_params,
                pose_data.get("keypoints", np.zeros((18, 3))),
                seed,
            )
