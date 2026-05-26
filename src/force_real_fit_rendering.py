import logging
from pathlib import Path
from PIL import Image, ImageEnhance, ImageFilter
import numpy as np
import cv2

def render_real_fit():
    print("[INFO] 오버핏-슬림마네킹 최적화 리얼 착장 엔진을 가동합니다...")
    
    # 1. 경로 설정
    mannequin_path = Path(r"d:\blandu_project\input\raw_photos\마네킨 컷.png")
    top_path = Path(r"d:\blandu_project\input\raw_photos\ITEM-001.png")
    bottom_path = Path(r"d:\blandu_project\input\raw_photos\ITEM-002.png")
    output_path = Path(r"d:\blandu_project\output\hybrid\REAL_FIT_LOOK.jpg")
    
    if not mannequin_path.exists() or not top_path.exists() or not bottom_path.exists():
        print("[ERROR] 리소스 파일이 부족합니다.")
        return

    # 2. 베이스 마네킹 로드 및 정규화
    canvas = Image.open(mannequin_path).convert("RGBA")
    canvas = canvas.resize((600, 800), Image.Resampling.LANCZOS)
    
    # 3. 상의(ITEM-001) 리얼-핏 교정
    top_img = Image.open(top_path).convert("RGBA")
    tw, th = top_img.size
    # [교정] 오버핏 느낌을 살리되 마네킹을 덮지 않는 최적 너비 (330px)
    t_scale = 330 / tw 
    top_img = top_img.resize((int(tw * t_scale), int(th * t_scale)), Image.Resampling.LANCZOS)
    
    t_offset_x = (600 - top_img.width) // 2
    t_offset_y = 100 # 넥라인 정밀 위치
    canvas.paste(top_img, (t_offset_x, t_offset_y), top_img)
    
    # 4. 하의(ITEM-002) 리얼-핏 교정
    bottom_img = Image.open(bottom_path).convert("RGBA")
    bw, bh = bottom_img.size
    # [교정] 허리는 맞추고 하단 와이드 핏을 극대화한 스케일 (320px)
    b_scale = 320 / bw
    bottom_img = bottom_img.resize((int(bw * b_scale), int(bh * b_scale)), Image.Resampling.LANCZOS)
    
    b_offset_x = (600 - bottom_img.width) // 2
    # [교정] 반신 마네킹 하단 끝단에 허리선을 정확히 밀착 (Y=375)
    b_offset_y = 375 
    canvas.paste(bottom_img, (b_offset_x, b_offset_y), bottom_img)
    
    # 5. 입체감 및 톤 보정 (Depth & Tone)
    result = canvas.convert("RGB")
    img_array = np.array(result)
    
    # LAB 색공간에서 미세한 명암 조절로 옷의 굴곡 표현
    img_array = cv2.cvtColor(img_array, cv2.COLOR_RGB2LAB)
    l, a, b = cv2.split(img_array)
    # L채널의 대비를 살짝 높여 화이트-화이트 간의 경계(접힘선)를 명확히 함
    l = cv2.convertScaleAbs(l, alpha=1.1, beta=-5) 
    img_array = cv2.merge([l, a, b])
    img_array = cv2.cvtColor(img_array, cv2.COLOR_LAB2RGB)
    
    result = Image.fromarray(img_array.astype('uint8'))
    
    # 최종 룩북 퀄리티 마무리
    result = ImageEnhance.Contrast(result).enhance(1.1)
    result = ImageEnhance.Sharpness(result).enhance(1.2)
    result = result.filter(ImageFilter.SMOOTH)
    
    # 6. 저장
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result.save(output_path, "JPEG", quality=98)
    print(f"[FINISH] 리얼 착용 핏 렌더링 완료: {output_path}")

if __name__ == "__main__":
    render_real_fit()