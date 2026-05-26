import logging
from pathlib import Path
from PIL import Image, ImageEnhance
import numpy as np
import cv2

def render_final_fitting():
    print("[INFO] 마네킹.jpg 기반 정밀 착장 프로세스를 시작합니다...")
    
    # 1. 경로 설정
    mannequin_path = Path(r"d:\blandu_project\input\raw_photos\마네킹.jpg")
    top_path = Path(r"d:\blandu_project\input\raw_photos\ITEM-001.png")
    bottom_path = Path(r"d:\blandu_project\input\raw_photos\ITEM-002.png")
    output_path = Path(r"d:\blandu_project\output\hybrid\FINAL_MANNEQUIN_FITTING.jpg")
    
    if not mannequin_path.exists() or not top_path.exists() or not bottom_path.exists():
        print("[ERROR] 필요한 이미지 파일이 없습니다. 경로를 확인해주세요.")
        return

    # 2. 베이스 마네킹 로드 및 정규화 (512x768)
    canvas = Image.open(mannequin_path).convert("RGBA")
    canvas = canvas.resize((512, 768), Image.Resampling.LANCZOS)
    
    # 3. 상의(ITEM-001) 정밀 착장
    top_img = Image.open(top_path).convert("RGBA")
    tw, th = top_img.size
    # 마네킹 어깨선에 맞춘 최적 비율 계산
    t_scale = 330 / tw 
    top_img = top_img.resize((int(tw * t_scale), int(th * t_scale)), Image.Resampling.LANCZOS)
    
    t_offset_x = (512 - top_img.width) // 2
    t_offset_y = 150 # 마네킹 상체 시작점
    canvas.paste(top_img, (t_offset_x, t_offset_y), top_img)
    
    # 4. 하의(ITEM-002) 정밀 착장
    bottom_img = Image.open(bottom_path).convert("RGBA")
    bw, bh = bottom_img.size
    # 하의 폭을 상의보다 약간 슬림하게 조정하여 핏감 구현
    b_scale = 300 / bw
    bottom_img = bottom_img.resize((int(bw * b_scale), int(bh * b_scale)), Image.Resampling.LANCZOS)
    
    b_offset_x = (512 - bottom_img.width) // 2
    b_offset_y = 380 # 상의 밑단과 맞닿는 허리선 위치
    canvas.paste(bottom_img, (b_offset_x, b_offset_y), bottom_img)
    
    # 5. 최종 톤 및 질감 보정 (Real-Photo Blending)
    result = canvas.convert("RGB")
    img_array = np.array(result)
    img_array = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
    img_array = cv2.cvtColor(img_array, cv2.COLOR_BGR2LAB)
    # 마네킹.jpg의 전반적인 톤에 맞춰 아주 미세하게 명암 조정
    img_array[:, :, 0] = np.clip(img_array[:, :, 0] - 2, 0, 255) 
    img_array = cv2.cvtColor(img_array, cv2.COLOR_LAB2RGB)
    
    result = Image.fromarray(img_array.astype('uint8'))
    # 상품의 선명도를 높이기 위해 대비 강화
    result = ImageEnhance.Contrast(result).enhance(1.1)
    
    # 6. 저장
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result.save(output_path, "JPEG", quality=95)
    print(f"[FINISH] 최종 착장 결과물 저장 완료: {output_path}")

if __name__ == "__main__":
    render_final_fitting()