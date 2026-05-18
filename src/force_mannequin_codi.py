import logging
from pathlib import Path
from PIL import Image, ImageDraw, ImageEnhance
import numpy as np
import cv2

def render_mannequin_codi():
    print("[INFO] 마네킹 기반 상/하의 착장 렌더링을 시작합니다...")
    
    # 1. 경로 설정
    top_path = Path(r"d:\blandu_project\input\raw_photos\ITEM-001.png")
    bottom_path = Path(r"d:\blandu_project\input\raw_photos\ITEM-002.png")
    output_path = Path(r"d:\blandu_project\output\hybrid\MANNEQUIN_CODI_001_002.jpg")
    
    if not top_path.exists() or not bottom_path.exists():
        print(f"[ERROR] 상품 이미지가 부족합니다.")
        return

    # 2. 프리미엄 배경 생성 (Urban Mood)
    canvas = Image.new('RGB', (512, 768))
    top_color, bottom_color = (60, 60, 70), (30, 30, 40)
    for y in range(768):
        ratio = y / 768
        color = tuple(int(top_color[i] * (1 - ratio) + bottom_color[i] * ratio) for i in range(3))
        for x in range(512):
            canvas.putpixel((x, y), color)

    canvas_rgba = canvas.convert("RGBA")

    # 3. 마네킹 실루엣 생성 (상품 배치 가이드)
    # 실제 마네킹 이미지 대신, 시각적 완성도를 위해 부드러운 쉐도우 실루엣을 그립니다.
    overlay = Image.new('RGBA', (512, 768), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    # 상체 실루엣 (타원형)
    draw.ellipse([150, 120, 360, 400], fill=(100, 100, 110, 100))
    # 하체 실루엣 (타원형)
    draw.ellipse([160, 380, 350, 700], fill=(100, 100, 110, 100))
    canvas_rgba = Image.alpha_composite(canvas_rgba, overlay)

    # 4. 상의(ITEM-001) 착장
    top_img = Image.open(top_path).convert("RGBA")
    tw, th = top_img.size
    t_scale = 320 / tw
    top_img = top_img.resize((int(tw * t_scale), int(th * t_scale)), Image.Resampling.LANCZOS)
    
    t_offset_x = (512 - top_img.width) // 2
    t_offset_y = 130 
    canvas_rgba.paste(top_img, (t_offset_x, t_offset_y), top_img)

    # 5. 하의(ITEM-002) 착장
    bottom_img = Image.open(bottom_path).convert("RGBA")
    bw, bh = bottom_img.size
    b_scale = 300 / bw
    bottom_img = bottom_img.resize((int(bw * b_scale), int(bh * b_scale)), Image.Resampling.LANCZOS)
    
    b_offset_x = (512 - bottom_img.width) // 2
    b_offset_y = 370 # 상의와 겹치도록 약간 위로 배치
    canvas_rgba.paste(bottom_img, (b_offset_x, b_offset_y), bottom_img)

    # 6. 최종 톤 보정 (마네킹-상품 일체감 부여)
    result = canvas_rgba.convert("RGB")
    img_array = np.array(result)
    img_array = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
    img_array = cv2.cvtColor(img_array, cv2.COLOR_BGR2LAB)
    img_array[:, :, 0] = np.clip(img_array[:, :, 0] - 10, 0, 255) 
    img_array = cv2.cvtColor(img_array, cv2.COLOR_LAB2RGB)
    
    result = Image.fromarray(img_array.astype('uint8'))
    result = ImageEnhance.Contrast(result).enhance(1.2)

    # 7. 저장
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result.save(output_path, "JPEG", quality=95)
    print(f"[FINISH] 마네킹 착장 결과물 저장 완료: {output_path}")

if __name__ == "__main__":
    render_mannequin_codi()