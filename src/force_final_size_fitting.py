import logging
from pathlib import Path
from PIL import Image, ImageEnhance, ImageFilter
import numpy as np
import cv2

def render_final_size_fitting():
    print("[INFO] '마네킨 컷.png' 기반 사이즈 맞춤 정밀 착장을 시작합니다...")
    
    # 1. 경로 설정
    mannequin_path = Path(r"d:\blandu_project\input\raw_photos\마네킨 컷.png")
    top_path = Path(r"d:\blandu_project\input\raw_photos\ITEM-001.png")
    bottom_path = Path(r"d:\blandu_project\input\raw_photos\ITEM-002.png")
    output_path = Path(r"d:\blandu_project\output\hybrid\FINAL_SIZE_FITTING.jpg")
    
    if not mannequin_path.exists() or not top_path.exists() or not bottom_path.exists():
        print("[ERROR] 리소스 파일이 부족합니다.")
        return

    # 2. 베이스 마네킹 로드 및 정규화
    canvas = Image.open(mannequin_path).convert("RGBA")
    canvas = canvas.resize((600, 800), Image.Resampling.LANCZOS)
    
    # 3. 상의(ITEM-001) 사이즈 맞춤 배치
    top_img = Image.open(top_path).convert("RGBA")
    tw, th = top_img.size
    # 마네킹 어깨 너비에 맞춘 정밀 스케일링
    t_scale = 360 / tw 
    top_img = top_img.resize((int(tw * t_scale), int(th * t_scale)), Image.Resampling.LANCZOS)
    
    t_offset_x = (600 - top_img.width) // 2
    t_offset_y = 90 # 넥라인 위치
    canvas.paste(top_img, (t_offset_x, t_offset_y), top_img)
    
    # 4. 하의(ITEM-002) 사이즈 맞춤 배치
    bottom_img = Image.open(bottom_path).convert("RGBA")
    bw, bh = bottom_img.size
    # 와이드 팬츠 핏을 살린 스케일링
    b_scale = 340 / bw
    bottom_img = bottom_img.resize((int(bw * b_scale), int(bh * b_scale)), Image.Resampling.LANCZOS)
    
    b_offset_x = (600 - bottom_img.width) // 2
    # 상의 밑단과 정확히 맞닿는 허리선 위치
    b_offset_y = 370 
    canvas.paste(bottom_img, (b_offset_x, b_offset_y), bottom_img)
    
    # 5. 시각적 완성도 보정 (Final Polish)
    result = canvas.convert("RGB")
    img_array = np.array(result)
    
    # 톤 밸런스 조정: 일체감 부여
    img_array = cv2.cvtColor(img_array, cv2.COLOR_RGB2LAB)
    l, a, b = cv2.split(img_array)
    l = cv2.equalizeHist(l)
    # 원본 마네킹의 밝기 톤과 믹스하여 자연스럽게 처리
    l = cv2.addWeighted(l, 0.3, l, 0.7, 0) 
    img_array = cv2.merge([l, a, b])
    img_array = cv2.cvtColor(img_array, cv2.COLOR_LAB2RGB)
    
    result = Image.fromarray(img_array.astype('uint8'))
    
    # 최종 룩북 퀄리티 보정
    result = ImageEnhance.Contrast(result).enhance(1.1)
    result = ImageEnhance.Sharpness(result).enhance(1.1)
    result = result.filter(ImageFilter.SMOOTH)
    
    # 6. 저장
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result.save(output_path, "JPEG", quality=98)
    print(f"[FINISH] 사이즈 맞춤 착장 완료: {output_path}")

if __name__ == "__main__":
    render_final_size_fitting()