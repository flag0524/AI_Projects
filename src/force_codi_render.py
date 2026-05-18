import logging
from pathlib import Path
from PIL import Image, ImageEnhance
import numpy as np
import cv2

def force_codi_render():
    print("[INFO] 상의(ITEM-001) + 하의(ITEM-002) 코디네이션 렌더링을 시작합니다...")
    
    # 1. 경로 설정
    top_path = Path(r"d:\blandu_project\input\raw_photos\ITEM-001.png")
    bottom_path = Path(r"d:\blandu_project\input\raw_photos\ITEM-002.png")
    output_path = Path(r"d:\blandu_project\output\hybrid\CODI_001_002_muse_lookbook.jpg")
    
    if not top_path.exists() or not bottom_path.exists():
        print(f"[ERROR] 상품 이미지가 부족합니다. (상의: {top_path.exists()}, 하의: {bottom_path.exists()})")
        return

    # 2. 이미지 로드 및 RGBA 변환
    top_img = Image.open(top_path).convert("RGBA")
    bottom_img = Image.open(bottom_path).convert("RGBA")
    print(f"[SUCCESS] 상품 이미지 로드 완료: {top_path.name}, {bottom_path.name}")

    # 3. 프리미엄 그라데이션 배경 생성 (Urban Chic 무드)
    bg = Image.new('RGB', (512, 768))
    top_color = (60, 60, 70) 
    bottom_color = (30, 30, 40)
    for y in range(768):
        ratio = y / 768
        color = tuple(int(top_color[i] * (1 - ratio) + bottom_color[i] * ratio) for i in range(3))
        for x in range(512):
            bg.putpixel((x, y), color)

    bg_rgba = bg.convert("RGBA")

    # 4. 상의(TOP) 배치 및 리사이즈
    tw, th = top_img.size
    t_scale = 350 / tw
    t_new_size = (int(tw * t_scale), int(th * t_scale))
    top_img = top_img.resize(t_new_size, Image.Resampling.LANCZOS)
    
    t_offset_x = (512 - t_new_size[0]) // 2
    t_offset_y = 120 # 상체 위치
    bg_rgba.paste(top_img, (t_offset_x, t_offset_y), top_img)

    # 5. 하의(BOTTOM) 배치 및 리사이즈
    bw, bh = bottom_img.size
    b_scale = 350 / bw
    b_new_size = (int(bw * b_scale), int(bh * b_scale))
    bottom_img = bottom_img.resize(b_new_size, Image.Resampling.LANCZOS)
    
    b_offset_x = (512 - b_new_size[0]) // 2
    b_offset_y = 380 # 하체 위치 (상의 아래로 배치)
    bg_rgba.paste(bottom_img, (b_offset_x, b_offset_y), bottom_img)

    # 6. 최종 이미지 보정 (필터 및 대비)
    result = bg_rgba.convert("RGB")
    img_array = np.array(result)
    img_array = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
    img_array = cv2.cvtColor(img_array, cv2.COLOR_BGR2LAB)
    img_array[:, :, 0] = np.clip(img_array[:, :, 0] - 15, 0, 255) 
    img_array = cv2.cvtColor(img_array, cv2.COLOR_LAB2RGB)
    
    result = Image.fromarray(img_array.astype('uint8'))
    enhancer = ImageEnhance.Contrast(result)
    result = enhancer.enhance(1.2)

    # 7. 저장
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result.save(output_path, "JPEG", quality=95)
    print(f"[FINISH] 코디네이션 결과물 저장 완료: {output_path}")

if __name__ == "__main__":
    force_codi_render()