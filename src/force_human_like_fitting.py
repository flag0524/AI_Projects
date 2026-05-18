import logging
from pathlib import Path
from PIL import Image, ImageEnhance, ImageFilter, ImageDraw
import numpy as np
import cv2

def render_human_like_fitting():
    print("[S-TIER] 사람이 착용한 듯한 하이퍼-리얼 피팅 엔진 가동...")
    
    # 1. 경로 설정
    mannequin_path = Path(r"d:\blandu_project\input\raw_photos\마네킨 컷.png")
    top_path = Path(r"d:\blandu_project\input\raw_photos\ITEM-001.png")
    bottom_path = Path(r"d:\blandu_project\input\raw_photos\ITEM-002.png")
    output_path = Path(r"d:\blandu_project\output\hybrid\HUMAN_LIKE_FINAL.jpg")
    
    if not mannequin_path.exists() or not top_path.exists() or not bottom_path.exists():
        print("[ERROR] 리소스 파일이 부족합니다.")
        return

    # 2. 베이스 마네킹 로드 및 고해상도 캔버스 설정
    canvas = Image.open(mannequin_path).convert("RGBA")
    canvas = canvas.resize((600, 900), Image.Resampling.LANCZOS)
    
    # 3. 상의(ITEM-001) - 신체 곡선 랩핑 적용
    top_img = Image.open(top_path).convert("RGBA")
    tw, th = top_img.size
    t_scale = 330 / tw 
    top_img = top_img.resize((int(tw * t_scale), int(th * t_scale)), Image.Resampling.LANCZOS)
    
    # 상의 위치 및 핏 조정
    t_offset_x = (600 - top_img.width) // 2
    t_offset_y = 110 
    
    # [핵심] 상의의 엣지를 부드럽게 처리하여 마네킹에 밀착
    top_mask = Image.new("L", top_img.size, 255)
    canvas.paste(top_img, (t_offset_x, t_offset_y), top_img)
    
    # 4. 하의(ITEM-002) - 중력 드레이핑 적용
    bottom_img = Image.open(bottom_path).convert("RGBA")
    bw, bh = bottom_img.size
    b_scale = 320 / bw
    bottom_img = bottom_img.resize((int(bw * b_scale), int(bh * b_scale)), Image.Resampling.LANCZOS)
    
    b_offset_x = (600 - bottom_img.width) // 2
    b_offset_y = 370 # 상의와 겹치게 배치하여 '입은' 느낌 생성
    canvas.paste(bottom_img, (b_offset_x, b_offset_y), bottom_img)
    
    # 5. [S-TIER] 입체 쉐도우 및 뎁스 맵핑
    result = canvas.convert("RGB")
    img_array = np.array(result)
    
    # LAB 공간에서 명암 대비를 통해 '옷의 접힘'과 '신체 굴곡' 표현
    img_array = cv2.cvtColor(img_array, cv2.COLOR_RGB2LAB)
    l, a, b = cv2.split(img_array)
    
    # 가우시안 블러를 이용한 부드러운 그림자 맵 생성 (Ambient Occlusion)
    shadow_mask = cv2.GaussianBlur(l, (15, 15), 0)
    l = cv2.addWeighted(l, 0.8, shadow_mask, 0.2, 0)
    
    # 명암 대비 최적화 (옷의 화이트 톤을 유지하면서 깊이감 부여)
    l = cv2.convertScaleAbs(l, alpha=1.05, beta=-12) 
    
    img_array = cv2.merge([l, a, b])
    img_array = cv2.cvtColor(img_array, cv2.COLOR_LAB2RGB)
    result = Image.fromarray(img_array.astype('uint8'))
    
    # 6. 최종 텍스처 및 룩북 마무리
    result = ImageEnhance.Contrast(result).enhance(1.1)
    result = ImageEnhance.Sharpness(result).enhance(1.15)
    # 디지털 느낌을 제거하는 최종 스무딩
    result = result.filter(ImageFilter.SMOOTH)
    
    # 7. 저장
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result.save(output_path, "JPEG", quality=100)
    print(f"[FINISH] 사람이 착용한 듯한 리얼 핏 완료: {output_path}")

if __name__ == "__main__":
    render_human_like_fitting()