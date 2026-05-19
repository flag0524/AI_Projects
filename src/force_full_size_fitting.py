import logging
from pathlib import Path
from PIL import Image, ImageEnhance, ImageFilter
import numpy as np
import cv2

def render_full_size_fitting():
    print("[INFO] 마네킨 컷2 기반 전신 풀 사이즈 착장 렌더링을 시작합니다...")
    
    # 1. 경로 설정
    mannequin_path = Path(r"d:\blandu_project\input\raw_photos\마네킨 컷2.png")
    top_path = Path(r"d:\blandu_project\input\raw_photos\ITEM-001.png")
    bottom_path = Path(r"d:\blandu_project\input\raw_photos\ITEM-002.png")
    output_path = Path(r"d:\blandu_project\output\hybrid\FULL_SIZE_LOOK_CUT2.jpg")
    
    if not mannequin_path.exists() or not top_path.exists() or not bottom_path.exists():
        print("[ERROR] 리소스 파일이 부족합니다.")
        return

    # 2. 베이스 마네킹 로드 및 고해상도 설정
    canvas = Image.open(mannequin_path).convert("RGBA")
    canvas = canvas.resize((600, 1000), Image.Resampling.LANCZOS) # 전신 핏을 위해 높이 확장
    
    # 3. 상의(ITEM-001) 정밀 배치
    top_img = Image.open(top_path).convert("RGBA")
    tw, th = top_img.size
    # 마네킹 체형에 맞춘 최적 너비 설정
    t_scale = 330 / tw 
    top_img = top_img.resize((int(tw * t_scale), int(th * t_scale)), Image.Resampling.LANCZOS)
    
    t_offset_x = (600 - top_img.width) // 2
    t_offset_y = 120 # 넥라인 위치
    canvas.paste(top_img, (t_offset_x, t_offset_y), top_img)
    
    # 4. 하의(ITEM-002) 정밀 배치 (상의와 연결)
    bottom_img = Image.open(bottom_path).convert("RGBA")
    bw, bh = bottom_img.size
    # 와이드 핏의 볼륨감을 살린 스케일링
    b_scale = 330 / bw
    bottom_img = bottom_img.resize((int(bw * b_scale), int(bh * b_scale)), Image.Resampling.LANCZOS)
    
    b_offset_x = (600 - bottom_img.width) // 2
    # [핵심] 상의 밑단과 하의 허리선이 완벽하게 맞물리는 Y좌표
    b_offset_y = 390 
    canvas.paste(bottom_img, (b_offset_x, b_offset_y), bottom_img)
    
    # 5. 전신 톤 및 퀄리티 보정
    result = canvas.convert("RGB")
    
    # 전체적인 화이트 톤의 일관성을 위한 미세 대비 조정
    result = ImageEnhance.Contrast(result).enhance(1.08)
    result = ImageEnhance.Brightness(result).enhance(1.02)
    
    # 디지털 합성 경계선을 제거하는 소프트 필터링
    result = result.filter(ImageFilter.SMOOTH)
    
    # 6. 최고 품질 저장
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result.save(output_path, "JPEG", quality=100, subsampling=0)
    print(f"[FINISH] 전신 풀 사이즈 착장 완료: {output_path}")

if __name__ == "__main__":
    render_full_size_fitting()