import logging
from pathlib import Path
from PIL import Image, ImageEnhance
import numpy as np
import cv2

def render_texture_preserved():
    print("[INFO] 원본 디자인 및 텍스처 보존 모드로 렌더링을 시작합니다...")
    
    # 1. 경로 설정
    mannequin_path = Path(r"d:\blandu_project\input\raw_photos\마네킹.jpg")
    top_path = Path(r"d:\blandu_project\input\raw_photos\ITEM-001.png")
    bottom_path = Path(r"d:\blandu_project\input\raw_photos\ITEM-002.png")
    output_path = Path(r"d:\blandu_project\output\hybrid\TEXTURE_PRESERVED_LOOK.jpg")
    
    if not mannequin_path.exists() or not top_path.exists() or not bottom_path.exists():
        print("[ERROR] 필요한 이미지 파일이 없습니다.")
        return

    # 2. 마네킹 베이스 로드 (512x768) - 원본 텍스처 보존을 위해 RGBA 유지
    canvas = Image.open(mannequin_path).convert("RGBA")
    canvas = canvas.resize((512, 768), Image.Resampling.LANCZOS)
    
    # 3. 상의(ITEM-001) 착장 - 텍스처 보존 최우선
    top_img = Image.open(top_path).convert("RGBA")
    tw, th = top_img.size
    # 정밀 스케일링: 텍스처 뭉침 방지를 위해 계산된 비율 적용
    t_scale = 335 / tw 
    top_img = top_img.resize((int(tw * t_scale), int(th * t_scale)), Image.Resampling.LANCZOS)
    
    t_offset_x = (512 - top_img.width) // 2
    t_offset_y = 152 
    # 마스크 없이 원본 알파 채널 그대로 합성하여 엣지 텍스처 보존
    canvas.paste(top_img, (t_offset_x, t_offset_y), top_img)
    
    # 4. 하의(ITEM-002) 착장 - 텍스처 보존 최우선
    bottom_img = Image.open(bottom_path).convert("RGBA")
    bw, bh = bottom_img.size
    b_scale = 315 / bw
    bottom_img = bottom_img.resize((int(bw * b_scale), int(bh * b_scale)), Image.Resampling.LANCZOS)
    
    b_offset_x = (512 - bottom_img.width) // 2
    b_offset_y = 382 
    canvas.paste(bottom_img, (b_offset_x, b_offset_y), bottom_img)
    
    # 5. 최소한의 톤 보정 (텍스처 파괴 방지)
    # LAB 변환 없이 단순 RGB 밝기 조정만 수행하여 색상 왜곡 방지
    result = canvas.convert("RGB")
    
    # 텍스처를 살리기 위해 Contrast를 아주 미세하게만 조정 (1.05)
    result = ImageEnhance.Contrast(result).enhance(1.05)
    
    # 6. 최고 품질 저장 (JPEG Artifacts 방지)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result.save(output_path, "JPEG", quality=100, subsampling=0)
    print(f"[FINISH] 텍스처 보존 결과물 저장 완료: {output_path}")

if __name__ == "__main__":
    render_texture_preserved()