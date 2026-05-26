"""
마네킹 정밀 착장 v4
- 상의 너비: 마네킹 가슴 너비 × 1.25 (소매 조금만 나오게)
- 상의 높이: 비율 유지
- 하의 너비/높이: 독립 리사이즈 → 마네킹 허리~발목에 딱 맞게
"""
from pathlib import Path
from PIL import Image, ImageEnhance, ImageFilter
import numpy as np
import io

RAW     = Path(r"d:\blandu_project\input\raw_photos")
OUT_DIR = Path(r"d:\blandu_project\output\hybrid")
OUT     = OUT_DIR / "PRECISION_FITTING_TOTAL_LOOK.jpg"

def remove_bg(path: Path) -> Image.Image:
    from rembg import remove
    out = remove(path.read_bytes(), post_process_mask=True)
    return Image.open(io.BytesIO(out)).convert("RGBA")

def row_span(arr, y):
    """y행에서 alpha>10 픽셀의 (left, right, width, center) 반환"""
    cols = np.where(arr[y, :, 3] > 10)[0]
    if len(cols) == 0:
        return 0, 0, 0, 0
    return int(cols[0]), int(cols[-1]), int(cols[-1]-cols[0]), int((cols[0]+cols[-1])//2)

def fit():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # ── 1. 마네킹 ──────────────────────────────────────
    print("[1/4] 마네킹 배경 제거...")
    m_rgba = remove_bg(RAW / "마네킹.jpg")
    mw, mh = m_rgba.size
    TH, TW = 1200, int(mw * 1200 / mh)          # 670×1200
    m_rgba = m_rgba.resize((TW, TH), Image.Resampling.LANCZOS)
    arr = np.array(m_rgba)

    # 실측 랜드마크 (670×1200 기준)
    # y=0.28(어깨 248px/cx320), y=0.35(가슴 297px/cx332)
    # y=0.42(허리 251px/cx304), y=0.48(힙 203px), y=0.90(발목)
    y_neck     = int(TH * 0.12)   # 144  목 아래
    y_shoulder = int(TH * 0.28)   # 336  어깨
    y_chest    = int(TH * 0.35)   # 420  최대 가슴
    y_waist    = int(TH * 0.42)   # 504  허리
    y_hip      = int(TH * 0.48)   # 576  힙
    y_ankle    = int(TH * 0.90)   # 1080 발목

    _, _, shoulder_w, shoulder_cx = row_span(arr, y_shoulder)
    _, _, chest_w,   chest_cx    = row_span(arr, y_chest)
    _, _, waist_w,   waist_cx    = row_span(arr, y_waist)
    _, _, hip_w,     hip_cx      = row_span(arr, y_hip)

    print(f"  어깨:{shoulder_w}px(cx={shoulder_cx})  가슴:{chest_w}px(cx={chest_cx})")
    print(f"  허리:{waist_w}px(cx={waist_cx})  힙:{hip_w}px")

    # 착장 기준 center: 상의=chest_cx, 하의=waist_cx
    top_cx = chest_cx
    bot_cx = waist_cx

    # ── 2. 상의 ─────────────────────────────────────────
    print("[2/4] 상의 배경 제거...")
    top_rgba = remove_bg(RAW / "ITEM-001.png")
    tw, th = top_rgba.size  # 3000×4000

    # 상의 목표 너비: 어깨(248) × 1.60 → 긴소매가 팔을 덮도록
    # 높이도 독립 조정: 목(y_neck)~허리(y_waist) 길이에 맞춤
    target_top_w = int(shoulder_w * 1.60)   # 248 × 1.60 ≈ 397px
    target_top_h = y_waist - y_neck + int((y_waist - y_neck) * 0.25)  # 허리보다 25% 아래까지 (페플럼)
    top_resized  = top_rgba.resize(
        (target_top_w, target_top_h), Image.Resampling.LANCZOS
    )
    print(f"  상의 리사이즈: {top_resized.size}")

    # 상의 위치: 목(y_neck)에 칼라 상단 정렬
    top_paste_x = top_cx - top_resized.width  // 2
    top_paste_y = y_neck

    # ── 3. 하의 ─────────────────────────────────────────
    print("[3/4] 하의 배경 제거...")
    bot_rgba = remove_bg(RAW / "ITEM-002.png")
    bw, bh = bot_rgba.size  # 600×800

    # 하의: 너비·높이 독립 리사이즈
    #   너비 목표 = 힙(203) × 1.70 (와이드 팬츠)
    #   높이 목표 = 상의 하단(페플럼 끝)~발목
    pant_top_y    = top_paste_y + int(target_top_h * 0.80)  # 상의 80% 지점(벨트 아래)부터
    pant_target_w = int(hip_w * 1.70)                        # ≈ 345px
    pant_target_h = y_ankle - pant_top_y                     # 발목까지

    bot_resized = bot_rgba.resize(
        (pant_target_w, pant_target_h), Image.Resampling.LANCZOS
    )
    print(f"  하의 리사이즈: {bot_resized.size}")

    # 하의 위치: 상의 벨트 라인 아래에 딱 붙여서 공백 없애기
    bot_paste_x = bot_cx - bot_resized.width  // 2
    bot_paste_y = pant_top_y

    # ── 4. 합성 ─────────────────────────────────────────
    print("[4/4] 합성...")
    canvas = Image.new("RGBA", (TW, TH), (255, 255, 255, 255))
    canvas.alpha_composite(m_rgba)                                       # 마네킹
    canvas.alpha_composite(bot_resized, dest=(bot_paste_x, bot_paste_y)) # 하의
    canvas.alpha_composite(top_resized, dest=(top_paste_x, top_paste_y)) # 상의

    result = canvas.convert("RGB")
    result = ImageEnhance.Contrast(result).enhance(1.07)
    result = ImageEnhance.Sharpness(result).enhance(1.1)
    result.save(OUT, "JPEG", quality=97)
    print(f"[DONE] 저장: {OUT}")

if __name__ == "__main__":
    fit()
