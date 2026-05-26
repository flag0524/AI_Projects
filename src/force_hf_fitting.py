import logging
from pathlib import Path
from PIL import Image, ImageEnhance, ImageFilter, ImageOps
import numpy as np
import cv2

def render_hf_fitting():
    print("[S-TIER] 원본 보존 하이-피델리티 착장 엔진 가동...")
    
    # 1. 경로 설정
    mannequin_path = Path(r"d:\blandu_project\input\raw_photos\마네킨 컷2.png")
    top_path = Path(r"d:\blandu_project\input\raw_photos\ITEM-001.png")
    bottom_path = Path(r"d:\blandu_project\input\raw_photos\ITEM-002.png")
    output_path = Path(r"d:\blandu_project\output\hybrid\HF_NATURAL_FIT.jpg")
    
    if not mannequin_path.exists() or not top_path.exists() or not bottom_path.exists():
        print("[ERROR] 리소스 파일이 부족합니다.")
        return

    # 2. 베이스 마네킹 로드 (원본 해상도 유지)
    canvas = Image.open(mannequin_path).convert("RGBA")
    cw, ch = canvas.size
    
    # 3. 상의(ITEM-001) - 원본 텍스처 보존 및 정밀 스케일링
    top_img = Image.open(top_path).convert("RGBA")
    tw, th = top_img.size
    # 마네킹의 실제 어깨 너비 비율을 계산하여 스케일링 (원본 훼손 최소화)
    t_target_w = cw * 0.55 # 마네킹 너비의 약 55%를 상의 너비로 설정
    t_scale = t_target_w / tw
    top_img = top_img.resize((int(tw * t_scale), int(th * t_scale)), Image.Resampling.LANCZOS)
    
    t_offset_x = (cw - top_img.width) // 2
    t_offset_y = int(ch * 0.12) # 상단에서 12% 지점에 배치
    canvas.paste(top_img, (t_offset_x, t_offset_y), top_img)
    
    # 4. 하의(ITEM-002) - 원본 텍스처 보존 및 정밀 스케일링
    bottom_img = Image.open(bottom_path).convert("RGBA")
    bw, bh = bottom_img.size
    b_target_w = cw * 0.58 # 하의는 약간 더 넓게 설정하여 와이드 핏 구현
    b_scale = b_target_w / bw
    bottom_img = bottom_img.resize((int(bw * b_scale), int(bh * b_scale)), Image.Resampling.LANCZOS)
    
    b_offset_x = (cw - bottom_img.width) // 2
    b_offset_y = int(ch * 0.45) # 상의 밑단과 자연스럽게 연결되는 지점
    canvas.paste(bottom_img, (b_offset_x, b_offset_y), bottom_img)
    
    # 5. [Core] 자연스러운 융합 처리 (Blending & Shadow)
    result = canvas.convert("RGB")
    img_array = np.array(result)
    
    # 톤 밸런스 조정: 전체적으로 부드러운 화이트 톤으로 통합
    img_array = cv2.cvtColor(img_array, cv2.COLOR_RGB2LAB)
    l, a, b = cv2.split(img_array)
    
    # 대비를 낮추고 밝기를 미세하게 올려 '쨍한' 합성 느낌 제거
    l = cv2.convertScaleAbs(l, alpha=0.95, beta=10)
    
    img_array = cv2.merge([l, a, b])
    img_array = cv2.cvtColor(img_array, cv2.COLOR_LAB2RGB)
    result = Image.fromarray(img_array.astype('uint8'))
    
    # 6. 최종 룩북 마무리 (Soft-Focus)
    result = ImageEnhance.Contrast(result).enhance(1.02)
    # 아주 미세한 가우시안 블러로 픽셀 경계를 뭉개어 자연스럽게 연결
    result = result.filter(ImageFilter.GaussianBlur(radius=0.3))
    
    # 7. 최고 품질 저장
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result.save(output_path, "JPEG", quality=100, subsampling=0)
    print(f"[FINISH] 하이-피델리티 자연 착장 완료: {output_path}")

if __name__ == "__main__":
    render_hf_fitting()