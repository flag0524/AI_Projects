import logging
from pathlib import Path
from PIL import Image, ImageEnhance, ImageFilter
import numpy as np
import cv2

def render_white_fitting():
    print("[INFO] 올-화이트 정밀 착장 렌더링을 시작합니다...")
    
    # 1. 경로 설정
    mannequin_path = Path(r"d:\blandu_project\input\raw_photos\마네킹.jpg")
    top_path = Path(r"d:\blandu_project\input\raw_photos\ITEM-001.png")
    bottom_path = Path(r"d:\blandu_project\input\raw_photos\ITEM-002.png")
    output_path = Path(r"d:\blandu_project\output\hybrid\WHITE_TOTAL_LOOK.jpg")
    
    if not mannequin_path.exists() or not top_path.exists() or not bottom_path.exists():
        print("[ERROR] 필요한 파일이 없습니다.")
        return

    # 2. 마네킹 베이스 로드 (512x768)
    canvas = Image.open(mannequin_path).convert("RGBA")
    canvas = canvas.resize((512, 768), Image.Resampling.LANCZOS)
    
    # 3. 상의(ITEM-001) 정밀 착장
    top_img = Image.open(top_path).convert("RGBA")
    tw, th = top_img.size
    # 마네킹 체형에 맞춘 정밀 스케일링
    t_scale = 340 / tw 
    top_img = top_img.resize((int(tw * t_scale), int(th * t_scale)), Image.Resampling.LANCZOS)
    
    t_offset_x = (512 - top_img.width) // 2
    t_offset_y = 155 # 셔츠 넥라인 위치 최적화
    canvas.paste(top_img, (t_offset_x, t_offset_y), top_img)
    
    # 4. 하의(ITEM-002) 정밀 착장
    bottom_img = Image.open(bottom_path).convert("RGBA")
    bw, bh = bottom_img.size
    # 와이드 핏을 살리기 위한 스케일 조정
    b_scale = 320 / bw
    bottom_img = bottom_img.resize((int(bw * b_scale), int(bh * b_scale)), Image.Resampling.LANCZOS)
    
    b_offset_x = (512 - bottom_img.width) // 2
    b_offset_y = 385 # 상의 벨트 라인과 자연스럽게 연결
    canvas.paste(bottom_img, (b_offset_x, b_offset_y), bottom_img)
    
    # 5. 화이트 톤 입체감 보정 (Depth Enhancement)
    result = canvas.convert("RGB")
    img_array = np.array(result)
    
    # 전체적인 대비를 높여 화이트-화이트 간의 경계를 구분
    img_array = cv2.cvtColor(img_array, cv2.COLOR_RGB2LAB)
    img_array[:, :, 0] = np.clip(img_array[:, :, 0] - 5, 0, 255) # 미세한 쉐이딩 추가
    img_array = cv2.cvtColor(img_array, cv2.COLOR_LAB2RGB)
    
    result = Image.fromarray(img_array.astype('uint8'))
    # 선명도 및 대비 강화 (고급 룩북 느낌)
    result = ImageEnhance.Contrast(result).enhance(1.2)
    result = ImageEnhance.Sharpness(result).enhance(1.1)
    
    # 6. 저장
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result.save(output_path, "JPEG", quality=98)
    print(f"[FINISH] 올-화이트 정밀 착장 완료: {output_path}")

if __name__ == "__main__":
    render_white_fitting()