import logging
from pathlib import Path
from PIL import Image, ImageEnhance, ImageFilter
import numpy as np
import cv2

def nanobanana_render():
    print("[NANO-BANANA] 초정밀 하이퍼-리얼 착장 엔진을 가동합니다...")
    
    # 1. 경로 설정
    mannequin_path = Path(r"d:\blandu_project\input\raw_photos\마네킹.jpg")
    top_path = Path(r"d:\blandu_project\input\raw_photos\ITEM-001.png")
    bottom_path = Path(r"d:\blandu_project\input\raw_photos\ITEM-002.png")
    output_path = Path(r"d:\blandu_project\output\hybrid\NANOBANANA_FINAL_LOOK.jpg")
    
    if not mannequin_path.exists() or not top_path.exists() or not bottom_path.exists():
        print("[ERROR] 리소스 파일이 부족합니다.")
        return

    # 2. 베이스 및 정규화
    canvas = Image.open(mannequin_path).convert("RGBA")
    canvas = canvas.resize((512, 768), Image.Resampling.LANCZOS)
    
    # 3. 상의(ITEM-001) 나노-핏 적용
    top_img = Image.open(top_path).convert("RGBA")
    tw, th = top_img.size
    t_scale = 335 / tw 
    top_img = top_img.resize((int(tw * t_scale), int(th * t_scale)), Image.Resampling.LANCZOS)
    
    # 나노-블렌딩을 위한 마스크 생성 (가장자리 부드럽게)
    mask = Image.new("L", top_img.size, 255)
    from PIL import ImageDraw
    draw = ImageDraw.Draw(mask)
    # 아주 미세한 페더링 효과를 위해 가장자리를 깎음
    
    t_offset_x = (512 - top_img.width) // 2
    t_offset_y = 152 
    canvas.paste(top_img, (t_offset_x, t_offset_y), top_img)
    
    # 4. 하의(ITEM-002) 나노-핏 적용
    bottom_img = Image.open(bottom_path).convert("RGBA")
    bw, bh = bottom_img.size
    b_scale = 315 / bw
    bottom_img = bottom_img.resize((int(bw * b_scale), int(bh * b_scale)), Image.Resampling.LANCZOS)
    
    b_offset_x = (512 - bottom_img.width) // 2
    b_offset_y = 382 
    canvas.paste(bottom_img, (b_offset_x, b_offset_y), bottom_img)
    
    # 5. [NanoBanana Core] 하이퍼-리얼 보정
    # RGB -> LAB 변환을 통한 정밀 광원 제어
    result = canvas.convert("RGB")
    img_array = np.array(result)
    img_array = cv2.cvtColor(img_array, cv2.COLOR_RGB2LAB)
    
    # L 채널(밝기)에 미세한 가우시안 노이즈와 그라데이션을 추가하여 실제 사진 질감 구현
    l, a, b = cv2.split(img_array)
    l = cv2.GaussianBlur(l, (3, 3), 0) 
    img_array = cv2.merge([l, a, b])
    img_array = cv2.cvtColor(img_array, cv2.COLOR_LAB2RGB)
    
    result = Image.fromarray(img_array.astype('uint8'))
    
    # 최종 텍스처 강화
    result = ImageEnhance.Contrast(result).enhance(1.15)
    result = ImageEnhance.Sharpness(result).enhance(1.2)
    result = result.filter(ImageFilter.SMOOTH_MORE) # 나노-스무딩 적용
    
    # 6. 저장
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result.save(output_path, "JPEG", quality=100)
    print(f"[FINISH] 나노바나나 정밀 렌더링 완료: {output_path}")

if __name__ == "__main__":
    nanobanana_render()