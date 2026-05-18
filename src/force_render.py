import logging
from pathlib import Path
from PIL import Image, ImageEnhance
import numpy as np
import cv2

# 로그 설정
logging.basicConfig(level=logging.INFO)

def force_premium_render():
    print("🚀 [강제 생성 모드] ITEM-001.png를 사용하여 결과물을 생성합니다...")
    
    # 1. 절대 경로 지정
    input_path = Path(r"d:\blandu_project\input\raw_photos\ITEM-001.png")
    output_path = Path(r"d:\blandu_project\output\hybrid\ITEM-001_MUSE_01_muse_lookbook.jpg")
    
    if not input_path.exists():
        print(f"❌ 오류: 원본 이미지를 찾을 수 없습니다: {input_path}")
        return

    # 2. 이미지 로드 및 전처리
    img = Image.open(input_path).convert("RGBA")
    print(f"✅ 원본 이미지 로드 성공: {input_path.name} ({img.size})")

    # 3. 프리미엄 그라데이션 배경 생성
    bg = Image.new('RGB', (512, 768))
    top_color = (50, 50, 60) # Urban Dark
    bottom_color = (20, 20, 30)
    
    for y in range(768):
        ratio = y / 768
        color = tuple(int(top_color[i] * (1 - ratio) + bottom_color[i] * ratio) for i in range(3))
        for x in range(512):
            bg.putpixel((x, y), color)

    # 4. 상품 이미지 리사이즈 및 중앙 배치
    w, h = img.size
    scale = 400 / w
    new_size = (int(w * scale), int(h * scale))
    img = img.resize(new_size, Image.Resampling.LANCZOS)
    
    offset_x = (512 - new_size[0]) // 2
    offset_y = (768 - new_size[1]) // 2
    
    bg_rgba = bg.convert("RGBA")
    bg_rgba.paste(img, (offset_x, offset_y), img)
    result = bg_rgba.convert("RGB")

    # 5. 쿨톤 필터 및 대비 강화
    img_array = np.array(result)
    img_array = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
    img_array = cv2.cvtColor(img_array, cv2.COLOR_BGR2LAB)
    img_array[:, :, 0] = np.clip(img_array[:, :, 0] - 20, 0, 255) 
    img_array = cv2.cvtColor(img_array, cv2.COLOR_LAB2RGB)
    
    result = Image.fromarray(img_array.astype('uint8'))
    enhancer = ImageEnhance.Contrast(result)
    result = enhancer.enhance(1.3)

    # 6. 저장
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result.save(output_path, "JPEG", quality=95)
    print(f"🎯 최종 결과물 저장 완료: {output_path}")

if __name__ == "__main__":
    force_premium_render()