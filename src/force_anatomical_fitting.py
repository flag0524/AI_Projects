import logging
from pathlib import Path
from PIL import Image, ImageEnhance, ImageFilter
import numpy as np
import cv2

def render_anatomical_fitting():
    print("[INFO] 신체 구조 기반 정밀 사이즈 교정 렌더링을 시작합니다...")
    
    # 1. 경로 설정
    mannequin_path = Path(r"d:\blandu_project\input\raw_photos\마네킨 컷.png")
    top_path = Path(r"d:\blandu_project\input\raw_photos\ITEM-001.png")
    bottom_path = Path(r"d:\blandu_project\input\raw_photos\ITEM-002.png")
    output_path = Path(r"d:\blandu_project\output\hybrid\ANATOMICAL_FIT_LOOK.jpg")
    
    if not mannequin_path.exists() or not top_path.exists() or not bottom_path.exists():
        print("[ERROR] 리소스 파일이 부족합니다.")
        return

    # 2. 베이스 마네킹 로드 및 정규화
    canvas = Image.open(mannequin_path).convert("RGBA")
    canvas = canvas.resize((600, 800), Image.Resampling.LANCZOS)
    
    # 3. 상의(ITEM-001) 신체 맞춤 교정
    top_img = Image.open(top_path).convert("RGBA")
    tw, th = top_img.size
    # [교정] 마네킹 어깨 끝단에 맞춘 정밀 너비 (기존보다 더 타이트하게 조정)
    t_scale = 305 / tw 
    top_img = top_img.resize((int(tw * t_scale), int(th * t_scale)), Image.Resampling.LANCZOS)
    
    t_offset_x = (600 - top_img.width) // 2
    t_offset_y = 115 # 넥라인을 실제 신체 위치로 하향 조정
    canvas.paste(top_img, (t_offset_x, t_offset_y), top_img)
    
    # 4. 하의(ITEM-002) 신체 맞춤 교정
    bottom_img = Image.open(bottom_path).convert("RGBA")
    bw, bh = bottom_img.size
    # [교정] 골반 너비에 맞춘 정밀 스케일링 (허리 핏을 잡기 위해 조정)
    b_scale = 300 / bw
    bottom_img = bottom_img.resize((int(bw * b_scale), int(bh * b_scale)), Image.Resampling.LANCZOS)
    
    b_offset_x = (600 - bottom_img.width) // 2
    # [교정] 상의 밑단과 하의 허리선이 겹치지 않고 자연스럽게 연결되는 지점
    b_offset_y = 385 
    canvas.paste(bottom_img, (b_offset_x, b_offset_y), bottom_img)
    
    # 5. 자연스러운 합성 및 톤 보정
    result = canvas.convert("RGB")
    img_array = np.array(result)
    
    # 톤 밸런스: 마네킹과 옷의 경계선을 부드럽게 처리하여 일체감 부여
    img_array = cv2.cvtColor(img_array, cv2.COLOR_RGB2LAB)
    l, a, b = cv2.split(img_array)
    l = cv2.equalizeHist(l)
    l = cv2.addWeighted(l, 0.2, l, 0.8, 0) 
    img_array = cv2.merge([l, a, b])
    img_array = cv2.cvtColor(img_array, cv2.COLOR_LAB2RGB)
    
    result = Image.fromarray(img_array.astype('uint8'))
    
    # 최종 룩북 퀄리티 업
    result = ImageEnhance.Contrast(result).enhance(1.1)
    result = ImageEnhance.Sharpness(result).enhance(1.1)
    result = result.filter(ImageFilter.SMOOTH)
    
    # 6. 저장
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result.save(output_path, "JPEG", quality=98)
    print(f"[FINISH] 신체 맞춤 정밀 착장 완료: {output_path}")

if __name__ == "__main__":
    render_anatomical_fitting()