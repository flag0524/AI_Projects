import logging
from pathlib import Path
from PIL import Image, ImageEnhance, ImageFilter
import numpy as np
import cv2

def render_final_original_fitting():
    print("[INFO] 원본 보존 및 정밀 착장 프로세스를 시작합니다...")
    
    # 1. 경로 설정
    mannequin_path = Path(r"d:\blandu_project\input\raw_photos\마네킨 컷.png")
    top_path = Path(r"d:\blandu_project\input\raw_photos\ITEM-001.png")
    bottom_path = Path(r"d:\blandu_project\input\raw_photos\ITEM-002.png")
    output_path = Path(r"d:\blandu_project\output\hybrid\FINAL_ORIGINAL_FIT.jpg")
    
    if not mannequin_path.exists() or not top_path.exists() or not bottom_path.exists():
        print("[ERROR] 리소스 파일이 부족합니다.")
        return

    # 2. 베이스 마네킹 로드 (600x800 표준화)
    canvas = Image.open(mannequin_path).convert("RGBA")
    canvas = canvas.resize((600, 800), Image.Resampling.LANCZOS)
    
    # 3. 상의(ITEM-001) - 원본 유지 및 정밀 배치
    top_img = Image.open(top_path).convert("RGBA")
    tw, th = top_img.size
    # 마네킹 어깨 너비에 맞춘 최적 스케일 (원본 텍스처 보존)
    t_scale = 320 / tw 
    top_img = top_img.resize((int(tw * t_scale), int(th * t_scale)), Image.Resampling.LANCZOS)
    
    t_offset_x = (600 - top_img.width) // 2
    t_offset_y = 110 # 넥라인 정밀 위치
    canvas.paste(top_img, (t_offset_x, t_offset_y), top_img)
    
    # 4. 하의(ITEM-002) - 원본 유지 및 정밀 배치
    bottom_img = Image.open(bottom_path).convert("RGBA")
    bw, bh = bottom_img.size
    # 하의의 와이드 핏을 살리면서 마네킹 너비에 맞춤
    b_scale = 320 / bw
    bottom_img = bottom_img.resize((int(bw * b_scale), int(bh * b_scale)), Image.Resampling.LANCZOS)
    
    b_offset_x = (600 - bottom_img.width) // 2
    # 상의와 하의가 만나는 허리선 정밀 위치 (Y=380)
    b_offset_y = 380 
    canvas.paste(bottom_img, (b_offset_x, b_offset_y), bottom_img)
    
    # 5. 최종 톤 정돈 (최소한의 보정으로 원본 유지)
    result = canvas.convert("RGB")
    
    # 원본의 색감을 해치지 않는 선에서 대비만 아주 미세하게 조정
    result = ImageEnhance.Contrast(result).enhance(1.05)
    # 디지털 엣지를 부드럽게 하여 합성 느낌 제거
    result = result.filter(ImageFilter.SMOOTH_MORE)
    
    # 6. 최고 품질 저장
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result.save(output_path, "JPEG", quality=100, subsampling=0)
    print(f"[FINISH] 원본 보존 정밀 착장 완료: {output_path}")

if __name__ == "__main__":
    render_final_original_fitting()