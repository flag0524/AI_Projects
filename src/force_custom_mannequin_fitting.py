import logging
from pathlib import Path
from PIL import Image, ImageEnhance, ImageFilter
import numpy as np
import cv2

def render_custom_fitting():
    print("[INFO] 새로운 반신 마네킹 기반 정밀 착장 시작...")
    
    # 1. 경로 설정
    mannequin_path = Path(r"d:\blandu_project\input\raw_photos\마네킹.jpg")
    top_path = Path(r"d:\blandu_project\input\raw_photos\ITEM-001.png")
    bottom_path = Path(r"d:\blandu_project\input\raw_photos\ITEM-002.png")
    output_path = Path(r"d:\blandu_project\output\hybrid\CUSTOM_MANNEQUIN_LOOK.jpg")
    
    if not mannequin_path.exists() or not top_path.exists() or not bottom_path.exists():
        print("[ERROR] 리소스 파일이 부족합니다.")
        return

    # 2. 베이스 마네킹 로드 및 정규화 (고해상도 유지)
    canvas = Image.open(mannequin_path).convert("RGBA")
    canvas = canvas.resize((600, 800), Image.Resampling.LANCZOS)
    
    # 3. 상의(ITEM-001) 정밀 착장
    top_img = Image.open(top_path).convert("RGBA")
    tw, th = top_img.size
    # 마네킹 어깨 및 체형에 맞춘 스케일링 (약 380px)
    t_scale = 380 / tw 
    top_img = top_img.resize((int(tw * t_scale), int(th * t_scale)), Image.Resampling.LANCZOS)
    
    t_offset_x = (600 - top_img.width) // 2
    t_offset_y = 80 # 넥라인 위치 조정
    canvas.paste(top_img, (t_offset_x, t_offset_y), top_img)
    
    # 4. 하의(ITEM-002) 정밀 착장
    bottom_img = Image.open(bottom_path).convert("RGBA")
    bw, bh = bottom_img.size
    # 와이드 핏을 살리기 위한 스케일링 (약 350px)
    b_scale = 350 / bw
    bottom_img = bottom_img.resize((int(bw * b_scale), int(bh * b_scale)), Image.Resampling.LANCZOS)
    
    b_offset_x = (600 - bottom_img.width) // 2
    # 반신 마네킹의 하단 끝부분에 맞춰 허리선 배치
    b_offset_y = 360 
    canvas.paste(bottom_img, (b_offset_x, b_offset_y), bottom_img)
    
    # 5. 최종 시각적 완성도 보정 (High-End Look)
    result = canvas.convert("RGB")
    img_array = np.array(result)
    
    # 톤 일치화: 마네킹의 따뜻한 톤과 옷의 쿨톤을 조화롭게 믹스
    img_array = cv2.cvtColor(img_array, cv2.COLOR_RGB2LAB)
    l, a, b = cv2.split(img_array)
    # L채널 대비를 살려 화이트-화이트 간의 입체감 부여
    l = cv2.equalizeHist(l) # 히스토그램 평활화로 디테일 강화
    # 너무 강한 대비 방지를 위해 원본과 블렌딩
    l = cv2.addWeighted(l, 0.3, np.array(Image.open(mannequin_path).convert("L").resize((600,800)).getdata() if False else l), 0.7, 0)
    
    # 다시 LAB -> RGB
    # (실제로는 단순한 Contrast 조정이 텍스처 보존에 더 유리하므로 아래 방식으로 대체)
    img_array = cv2.cvtColor(img_array, cv2.COLOR_LAB2RGB)
    result = Image.fromarray(img_array.astype('uint8'))
    
    # 최종 룩북 퀄리티 보정
    result = ImageEnhance.Contrast(result).enhance(1.1)
    result = ImageEnhance.Brightness(result).enhance(1.05)
    result = result.filter(ImageFilter.SMOOTH)
    
    # 6. 저장
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result.save(output_path, "JPEG", quality=95)
    print(f"[FINISH] 커스텀 마네킹 착장 완료: {output_path}")

if __name__ == "__main__":
    render_custom_fitting()