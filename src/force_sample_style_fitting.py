import logging
from pathlib import Path
from PIL import Image, ImageEnhance
import numpy as np
import cv2

def render_sample_style_fitting():
    print("[INFO] 샘플 이미지 스타일 기반 정밀 착장 시작...")
    
    # 1. 경로 설정
    mannequin_path = Path(r"d:\blandu_project\input\raw_photos\마네킹.png")
    top_path = Path(r"d:\blandu_project\input\raw_photos\ITEM-001.png")
    bottom_path = Path(r"d:\blandu_project\input\raw_photos\ITEM-002.png")
    output_path = Path(r"d:\blandu_project\output\hybrid\SAMPLE_STYLE_FITTING.jpg")
    
    if not mannequin_path.exists() or not top_path.exists() or not bottom_path.exists():
        print("[ERROR] 필요한 파일이 없습니다.")
        return

    # 2. 마네킹 베이스 로드 및 정규화
    canvas = Image.open(mannequin_path).convert("RGBA")
    canvas = canvas.resize((512, 768), Image.Resampling.LANCZOS)
    
    # 3. 상의(ITEM-001) 착장 - 샘플 이미지 비율 적용
    top_img = Image.open(top_path).convert("RGBA")
    tw, th = top_img.size
    # 마네킹 어깨 너비에 맞춘 최적 스케일 (약 320px)
    t_scale = 320 / tw
    top_img = top_img.resize((int(tw * t_scale), int(th * t_scale)), Image.Resampling.LANCZOS)
    
    t_offset_x = (512 - top_img.width) // 2
    t_offset_y = 140 # 샘플 이미지의 상의 시작점 반영
    canvas.paste(top_img, (t_offset_x, t_offset_y), top_img)
    
    # 4. 하의(ITEM-002) 착장 - 샘플 이미지 비율 적용
    bottom_img = Image.open(bottom_path).convert("RGBA")
    bw, bh = bottom_img.size
    # 하의 폭은 상의보다 약간 슬림하게 설정 (약 290px)
    b_scale = 290 / bw
    bottom_img = bottom_img.resize((int(bw * b_scale), int(bh * b_scale)), Image.Resampling.LANCZOS)
    
    b_offset_x = (512 - bottom_img.width) // 2
    b_offset_y = 370 # 샘플 이미지의 하의 시작점 (상의 밑단과 연결)
    canvas.paste(bottom_img, (b_offset_x, b_offset_y), bottom_img)
    
    # 5. 최종 보정 (검은 배경에서의 시각적 최적화)
    result = canvas.convert("RGB")
    img_array = np.array(result)
    img_array = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
    img_array = cv2.cvtColor(img_array, cv2.COLOR_BGR2LAB)
    # 대비를 살려 상품이 돋보이게 조정
    img_array[:, :, 0] = np.clip(img_array[:, :, 0] + 5, 0, 255) 
    img_array = cv2.cvtColor(img_array, cv2.COLOR_LAB2RGB)
    
    result = Image.fromarray(img_array.astype('uint8'))
    # 샘플 이미지처럼 선명한 느낌을 위해 대비 강화
    result = ImageEnhance.Contrast(result).enhance(1.2)
    
    # 6. 저장
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result.save(output_path, "JPEG", quality=95)
    print(f"[FINISH] 샘플 스타일 착장 완료: {output_path}")

if __name__ == "__main__":
    render_sample_style_fitting()