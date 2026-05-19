from pathlib import Path
from PIL import Image, ImageEnhance
import numpy as np
import cv2

def render_precision_fitting():
    print("[INFO] 참고 이미지 기반 정밀 착장 렌더링을 시작합니다...")
    
    # 1. 경로 설정
    mannequin_path = Path(r"d:\blandu_project\input\raw_photos\마네킨_01.jpg")
    top_path = Path(r"d:\blandu_project\input\raw_photos\ITEM-001.png")
    bottom_path = Path(r"d:\blandu_project\input\raw_photos\ITEM-002.png")
    output_path = Path(r"d:\blandu_project\output\hybrid\PRECISION_FITTING_01.jpg")
    
    if not mannequin_path.exists() or not top_path.exists() or not bottom_path.exists():
        print("[ERROR] 필요한 이미지 파일이 없습니다.")
        return

    # 2. 베이스 마네킹 로드 및 정규화
    canvas = Image.open(mannequin_path).convert("RGBA")
    canvas = canvas.resize((512, 768), Image.Resampling.LANCZOS)
    
    # 3. 상의(ITEM-001) 정밀 배치
    top_img = Image.open(top_path).convert("RGBA")
    tw, th = top_img.size
    # 참고 이미지 분석: 상의 폭은 마네킹 어깨 너비에 맞춤 (약 340px)
    t_scale = 340 / tw
    top_img = top_img.resize((int(tw * t_scale), int(th * t_scale)), Image.Resampling.LANCZOS)
    
    t_offset_x = (512 - top_img.width) // 2
    t_offset_y = 160 # 참고 이미지의 넥라인/어깨 위치 반영
    canvas.paste(top_img, (t_offset_x, t_offset_y), top_img)
    
    # 4. 하의(ITEM-002) 정밀 배치
    bottom_img = Image.open(bottom_path).convert("RGBA")
    bw, bh = bottom_img.size
    # 참고 이미지 분석: 하의 폭은 상의보다 약간 좁거나 비슷함 (약 310px)
    b_scale = 310 / bw
    bottom_img = bottom_img.resize((int(bw * b_scale), int(bh * b_scale)), Image.Resampling.LANCZOS)
    
    b_offset_x = (512 - bottom_img.width) // 2
    # 상의 밑단과 자연스럽게 연결되는 허리선 위치 (Y=390~410)
    b_offset_y = 390 
    canvas.paste(bottom_img, (b_offset_x, b_offset_y), bottom_img)
    
    # 5. 최종 시각적 보정 (Natural Blending)
    result = canvas.convert("RGB")
    img_array = np.array(result)
    img_array = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
    img_array = cv2.cvtColor(img_array, cv2.COLOR_BGR2LAB)
    # 너무 튀지 않도록 아주 미세한 톤 조정
    img_array[:, :, 0] = np.clip(img_array[:, :, 0] - 3, 0, 255) 
    img_array = cv2.cvtColor(img_array, cv2.COLOR_LAB2RGB)
    
    result = Image.fromarray(img_array.astype('uint8'))
    # 대비를 약간 높여 상품의 질감을 살림
    result = ImageEnhance.Contrast(result).enhance(1.1)
    
    # 6. 저장
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result.save(output_path, "JPEG", quality=95)
    print(f"[FINISH] 정밀 착장 결과물 저장 완료: {output_path}")

if __name__ == "__main__":
    render_precision_fitting()