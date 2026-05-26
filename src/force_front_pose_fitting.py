import logging
from pathlib import Path
from PIL import Image, ImageEnhance, ImageFilter
import numpy as np
import cv2

def render_front_pose_fitting():
    print("[INFO] 정면 포즈 최적화 및 대칭 정밀 착장을 시작합니다...")
    
    # 1. 경로 설정
    mannequin_path = Path(r"d:\blandu_project\input\raw_photos\마네킨 컷.png")
    top_path = Path(r"d:\blandu_project\input\raw_photos\ITEM-001.png")
    bottom_path = Path(r"d:\blandu_project\input\raw_photos\ITEM-002.png")
    output_path = Path(r"d:\blandu_project\output\hybrid\FRONT_Symmetry_FITTING.jpg")
    
    if not mannequin_path.exists() or not top_path.exists() or not bottom_path.exists():
        print("[ERROR] 리소스 파일이 부족합니다.")
        return

    # 2. 베이스 마네킹 로드 (정면 기준 정규화)
    canvas = Image.open(mannequin_path).convert("RGBA")
    canvas = canvas.resize((600, 800), Image.Resampling.LANCZOS)
    
    # 3. 상의(ITEM-001) 정면 대칭 착장
    top_img = Image.open(top_path).convert("RGBA")
    tw, th = top_img.size
    # 정면 포즈에서 가장 깔끔하게 떨어지는 어깨 너비 설정 (310px)
    t_scale = 310 / tw 
    top_img = top_img.resize((int(tw * t_scale), int(th * t_scale)), Image.Resampling.LANCZOS)
    
    # 완벽한 중앙 정렬 계산
    t_offset_x = (600 - top_img.width) // 2
    t_offset_y = 110 # 정면 넥라인 최적 위치
    canvas.paste(top_img, (t_offset_x, t_offset_y), top_img)
    
    # 4. 하의(ITEM-002) 정면 대칭 착장
    bottom_img = Image.open(bottom_path).convert("RGBA")
    bw, bh = bottom_img.size
    # 정면에서 와이드 핏이 가장 정갈하게 보이는 너비 설정 (310px)
    b_scale = 310 / bw
    bottom_img = bottom_img.resize((int(bw * b_scale), int(bh * b_scale)), Image.Resampling.LANCZOS)
    
    # 완벽한 중앙 정렬 계산
    b_offset_x = (600 - bottom_img.width) // 2
    b_offset_y = 390 # 상의 밑단과 정면에서 자연스럽게 연결되는 지점
    canvas.paste(bottom_img, (b_offset_x, b_offset_y), bottom_img)
    
    # 5. 정면 룩북 퀄리티 보정 (Clean-Cut Finish)
    result = canvas.convert("RGB")
    img_array = np.array(result)
    
    # 정면 사진의 깔끔함을 위해 톤을 일정하게 정리
    img_array = cv2.cvtColor(img_array, cv2.COLOR_RGB2LAB)
    l, a, b = cv2.split(img_array)
    # 과도한 대비보다는 부드러운 톤 매칭 적용
    l = cv2.addWeighted(l, 0.8, l, 0.2, 0) 
    img_array = cv2.merge([l, a, b])
    img_array = cv2.cvtColor(img_array, cv2.COLOR_LAB2RGB)
    
    result = Image.fromarray(img_array.astype('uint8'))
    
    # 최종 룩북 마무리 (Contrast & Sharpness)
    result = ImageEnhance.Contrast(result).enhance(1.08)
    result = ImageEnhance.Sharpness(result).enhance(1.1)
    result = result.filter(ImageFilter.SMOOTH)
    
    # 6. 저장
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result.save(output_path, "JPEG", quality=98)
    print(f"[FINISH] 정면 포즈 대칭 착장 완료: {output_path}")

if __name__ == "__main__":
    render_front_pose_fitting()