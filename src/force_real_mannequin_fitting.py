import logging
from pathlib import Path
from PIL import Image, ImageEnhance
import numpy as np
import cv2

def render_real_mannequin_fitting():
    print("[INFO] 실제 마네킹 사진 기반 착장 렌더링을 시작합니다...")
    
    # 1. 경로 설정
    mannequin_files = ["마네킨_01.jpg", "마네킨_02.jpg", "마네킨_03.jpg"]
    top_path = Path(r"d:\blandu_project\input\raw_photos\ITEM-001.png")
    bottom_path = Path(r"d:\blandu_project\input\raw_photos\ITEM-002.png")
    output_dir = Path(r"d:\blandu_project\output\hybrid\mannequin_fitting")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    if not top_path.exists() or not bottom_path.exists():
        print("[ERROR] 상품 이미지가 부족합니다.")
        return

    # 2. 상품 이미지 사전 로드 및 최적화
    top_img = Image.open(top_path).convert("RGBA")
    bottom_img = Image.open(bottom_path).convert("RGBA")
    
    # 상의 리사이즈 (마네킹 폭에 맞춤)
    tw, th = top_img.size
    t_scale = 300 / tw
    top_img = top_img.resize((int(tw * t_scale), int(th * t_scale)), Image.Resampling.LANCZOS)
    
    # 하의 리사이즈
    bw, bh = bottom_img.size
    b_scale = 280 / bw
    bottom_img = bottom_img.resize((int(bw * b_scale), int(bh * b_scale)), Image.Resampling.LANCZOS)

    # 3. 각 마네킹 이미지별로 반복 작업
    for m_file in mannequin_files:
        m_path = Path(r"d:\blandu_project\input\raw_photos") / m_file
        if not m_path.exists():
            print(f"[WARNING] 마네킹 파일을 찾을 수 없어 건너뜁니다: {m_file}")
            continue
            
        print(f"[PROCESS] {m_file}에 착장 중...")
        
        # 마네킹 이미지 로드 및 RGBA 변환
        canvas = Image.open(m_path).convert("RGBA")
        canvas = canvas.resize((512, 768), Image.Resampling.LANCZOS)
        
        # 상의 배치 (중앙 상단)
        t_offset_x = (512 - top_img.width) // 2
        t_offset_y = 150 
        canvas.paste(top_img, (t_offset_x, t_offset_y), top_img)
        
        # 하의 배치 (중앙 하단)
        b_offset_x = (512 - bottom_img.width) // 2
        b_offset_y = 380 
        canvas.paste(bottom_img, (b_offset_x, b_offset_y), bottom_img)
        
        # 4. 최종 톤 보정 (마네킹과 상품의 이질감 제거)
        result = canvas.convert("RGB")
        img_array = np.array(result)
        img_array = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
        img_array = cv2.cvtColor(img_array, cv2.COLOR_BGR2LAB)
        img_array[:, :, 0] = np.clip(img_array[:, :, 0] - 5, 0, 255) # 약간의 쿨톤 추가
        img_array = cv2.cvtColor(img_array, cv2.COLOR_LAB2RGB)
        
        result = Image.fromarray(img_array.astype('uint8'))
        result = ImageEnhance.Contrast(result).enhance(1.1)
        
        # 저장
        output_path = output_dir / f"FITTING_{m_file.replace('.jpg', '.jpg')}"
        result.save(output_path, "JPEG", quality=95)
        print(f"[SUCCESS] 저장 완료: {output_path.name}")

    print(f"[FINISH] 모든 마네킹 착장 완료. 저장 위치: {output_dir}")

if __name__ == "__main__":
    render_real_mannequin_fitting()