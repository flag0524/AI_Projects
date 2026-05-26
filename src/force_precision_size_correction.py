import logging
from pathlib import Path
from PIL import Image, ImageEnhance, ImageFilter
import numpy as np
import cv2

def render_precision_correction():
    print("[INFO] 마네킹 체형 맞춤형 사이즈 정밀 교정을 시작합니다...")
    
    # 1. 경로 설정
    mannequin_path = Path(r"d:\blandu_project\input\raw_photos\마네킨 컷.png")
    top_path = Path(r"d:\blandu_project\input\raw_photos\ITEM-001.png")
    bottom_path = Path(r"d:\blandu_project\input\raw_photos\ITEM-002.png")
    output_path = Path(r"d:\blandu_project\output\hybrid\PRECISION_SIZE_FITTING.jpg")
    
    if not mannequin_path.exists() or not top_path.exists() or not bottom_path.exists():
        print("[ERROR] 리소스 파일이 부족합니다.")
        return

    # 2. 베이스 마네킹 로드 및 정규화
    canvas = Image.open(mannequin_path).convert("RGBA")
    canvas = canvas.resize((600, 800), Image.Resampling.LANCZOS)
    
    # 3. 상의(ITEM-001) 사이즈 정밀 교정
    top_img = Image.open(top_path).convert("RGBA")
    tw, th = top_img.size
    # [교정] 마네킹의 실제 어깨 너비에 더 밀착된 스케일 적용 (340px -> 320px로 슬림화)
    t_scale = 320 / tw 
    top_img = top_img.resize((int(tw * t_scale), int(th * t_scale)), Image.Resampling.LANCZOS)
    
    t_offset_x = (600 - top_img.width) // 2
    t_offset_y = 105 # 넥라인을 약간 내려 실제 착용 위치로 조정
    canvas.paste(top_img, (t_offset_x, t_offset_y), top_img)
    
    # 4. 하의(ITEM-002) 사이즈 정밀 교정
    bottom_img = Image.open(bottom_path).convert("RGBA")
    bw, bh = bottom_img.size
    # [교정] 허리 부분은 마네킹에 맞추고, 전체적인 핏은 와이드하게 유지 (320px)
    b_scale = 320 / bw
    bottom_img = bottom_img.resize((int(bw * b_scale), int(bh * b_scale)), Image.Resampling.LANCZOS)
    
    b_offset_x = (600 - bottom_img.width) // 2
    # [교정] 상의 밑단과 겹치거나 뜨지 않도록 허리선 위치 정밀 조정
    b_offset_y = 385 
    canvas.paste(bottom_img, (b_offset_x, b_offset_y), bottom_img)
    
    # 5. 자연스러운 합성 보정 (Blending)
    result = canvas.convert("RGB")
    img_array = np.array(result)
    
    # 톤 밸런스: 마네킹과 옷의 경계선을 부드럽게 처리
    img_array = cv2.cvtColor(img_array, cv2.COLOR_RGB2LAB)
    l, a, b = cv2.split(img_array)
    l = cv2.equalizeHist(l)
    l = cv2.addWeighted(l, 0.2, l, 0.8, 0) 
    img_array = cv2.merge([l, a, b])
    img_array = cv2.cvtColor(img_array, cv2.COLOR_LAB2RGB)
    
    result = Image.fromarray(img_array.astype('uint8'))
    
    # 최종 퀄리티 업 (Contrast & Sharpness)
    result = ImageEnhance.Contrast(result).enhance(1.1)
    result = ImageEnhance.Sharpness(result).enhance(1.1)
    result = result.filter(ImageFilter.SMOOTH)
    
    # 6. 저장
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result.save(output_path, "JPEG", quality=98)
    print(f"[FINISH] 사이즈 정밀 교정 완료: {output_path}")

if __name__ == "__main__":
    render_precision_correction()