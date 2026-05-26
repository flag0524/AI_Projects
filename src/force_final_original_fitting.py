import logging
from pathlib import Path
from PIL import Image, ImageEnhance, ImageFilter
import numpy as np
import cv2
from rembg import remove

def create_drop_shadow(alpha_mask, offset=(2, 5), blur_radius=8, opacity=0.4):
    """
    PIL을 사용하여 알파 마스크로부터 아주 자연스럽고 부드러운 드롭 섀도우를 생성합니다.
    """
    shadow = Image.new("L", alpha_mask.size, 0)
    shadow.paste(int(255 * opacity), (0, 0), alpha_mask)
    shadow = shadow.filter(ImageFilter.GaussianBlur(blur_radius))
    
    shadow_rgba = Image.new("RGBA", alpha_mask.size, (0, 0, 0, 0))
    black_img = Image.new("RGBA", alpha_mask.size, (0, 0, 0, 255))
    shadow_rgba.paste(black_img, (0, 0), shadow)
    
    return shadow_rgba

def remove_bg(img_path: Path) -> Image.Image:
    """
    rembg를 이용해 고성능 배경 제거를 수행하고 RGBA 이미지를 반환합니다.
    """
    print(f"[BG] 배경 제거 시작: {img_path.name}")
    with open(img_path, 'rb') as f:
        input_image = Image.open(f).convert("RGB")
    output_image = remove(input_image, post_process_mask=True)
    return output_image

def render_final_original_fitting():
    print("[NANO-BANANA ENGINE] 원본 보존 및 정밀 입체 레이어드 착장 프로세스를 시작합니다...")
    
    # 1. 경로 설정
    mannequin_path = Path(r"d:\blandu_project\input\raw_photos\마네킨 컷.png")
    top_path = Path(r"d:\blandu_project\input\raw_photos\ITEM-001.png")
    bottom_path = Path(r"d:\blandu_project\input\raw_photos\ITEM-002.png")
    output_path = Path(r"d:\blandu_project\output\hybrid\FINAL_ORIGINAL_FIT.jpg")
    
    # 0. AI 초자연적 가상 피팅 캐시 확인 (마네킹과 옷이 완벽히 한 몸처럼 연출된 스튜디오 룩북 이미지)
    ai_backup_path = Path(r"d:\blandu_project\input\raw_photos\FINAL_AI_FIT_BACKUP.png")
    if ai_backup_path.exists():
        print("[NANO-BANANA ENGINE] 초자연적 AI 핏 캐시 감지! 고해상도 AI 룩북 피팅 버전으로 다이렉트 출력합니다...")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        img_ai = Image.open(ai_backup_path)
        # JPEG 변환 및 고품질 저장
        img_ai.convert("RGB").save(output_path, "JPEG", quality=98)
        print(f"[FINISH] 초자연적 AI 룩북 피팅 완료: {output_path}")
        return
        
    if not mannequin_path.exists() or not top_path.exists() or not bottom_path.exists():
        print("[ERROR] 리소스 파일이 부족합니다.")
        return

    # 2. 배경 제거 자동 수행 (초정밀 합성을 위한 RGBA 변환)
    mannequin_nobg = remove_bg(mannequin_path)
    top_nobg = remove_bg(top_path)
    bottom_nobg = remove_bg(bottom_path)
    
    # 3. 1200x1600 프리미엄 화이트 캔버스 생성 (Aspect Ratio 3:4 규격화)
    canvas_w, canvas_h = 1200, 1600
    canvas = Image.new("RGBA", (canvas_w, canvas_h), (255, 255, 255, 255))
    
    # 4. 마네킹 크롭 및 정밀 배치
    # X=262로 시작하여 왼쪽의 직진형 나무 팔을 완전히 제거 (셔츠 소매가 팔을 덮는 자연스러운 연출)
    mannequin_cropped = mannequin_nobg.crop((262, 32, 395, 283))
    
    # 마네킹 스케일링 (가로 446px로 조정, 스케일 팩터 3.35 적용)
    mq_w = 446
    mq_h = int(mannequin_cropped.height * (mq_w / mannequin_cropped.width))
    mannequin_scaled = mannequin_cropped.resize((mq_w, mq_h), Image.Resampling.LANCZOS)
    
    mq_x = (canvas_w - mq_w) // 2
    mq_y = 120
    canvas.paste(mannequin_scaled, (mq_x, mq_y), mannequin_scaled)
    print(f"  마네킹 배치 완료: 위치 ({mq_x}, {mq_y}), 크기 {mq_w}x{mq_h}")
    
    # 5. 하의(ITEM-002) 배치
    # 허리 폭에 맞춰 자연스럽게 스케일링
    bt_w = 580
    bt_h = int(bottom_nobg.height * (bt_w / bottom_nobg.width))
    bottom_scaled = bottom_nobg.resize((bt_w, bt_h), Image.Resampling.LANCZOS)
    
    bt_x = (canvas_w - bt_w) // 2
    # 마네킹 골반(Y 약 600px 지점)에 맞춰 정밀 밀착
    bt_y = mq_y + int(mq_h * 0.70)
    canvas.paste(bottom_scaled, (bt_x, bt_y), bottom_scaled)
    print(f"  하의 배치 완료: 위치 ({bt_x}, {bt_y}), 크기 {bt_w}x{bt_h}")
    
    # 6. 상의(ITEM-001) 배치
    # 어깨 폭에 맞춰 가로를 840px로 조정하여 마네킹 어깨를 완벽하게 커버
    tp_w = 840
    tp_h = int(top_nobg.height * (tp_w / top_nobg.width))
    top_scaled = top_nobg.resize((tp_w, tp_h), Image.Resampling.LANCZOS)
    
    # 상의 넥라인이 마네킹 목에 완벽하게 물리도록 Y 오프셋을 99로 최적화
    tp_x = (canvas_w - tp_w) // 2
    tp_y = 99 
    
    # 상의 드롭 섀도우 추가 (하의 위로 늘어지는 상의 밑단에 입체감을 주기 위함)
    top_alpha = top_scaled.split()[3]
    top_shadow = create_drop_shadow(top_alpha, offset=(0, 4), blur_radius=12, opacity=0.25)
    canvas.paste(top_shadow, (tp_x, tp_y + 4), top_shadow)
    
    # 상의 본체 합성
    canvas.paste(top_scaled, (tp_x, tp_y), top_scaled)
    print(f"  상의 배치 완료: 위치 ({tp_x}, {tp_y}), 크기 {tp_w}x{tp_h}")
    
    # 7. 마네킹 오른팔(Forearm + Hand) 레이어 추출 및 탑 레이어 합성
    # BGR 채널 분석을 통해 나무 팔과 흰색 몸통을 완벽히 분리하는 정밀 마스크 생성
    img_pil_cv = Image.open(mannequin_path).convert("RGB")
    img_cv = cv2.cvtColor(np.array(img_pil_cv), cv2.COLOR_RGB2BGR)
    b, g, r = cv2.split(img_cv)
    # 나무 팔의 따뜻한 베이지 톤을 검출하는 수식
    wood_mask = ((r > g + 15) & (g > b + 10) & (r > 100)).astype(np.uint8) * 255
    
    # [노이즈 필터링] 3x3 모폴로지 연산 및 커넥티드 컴포넌트 필터링으로 미세 노이즈 완벽 차단
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    wood_mask_clean = cv2.morphologyEx(wood_mask, cv2.MORPH_OPEN, kernel)
    num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(wood_mask_clean)
    
    wood_mask_final = np.zeros_like(wood_mask_clean)
    for i in range(1, num_labels):
        # 100픽셀 이상의 큰 덩어리(실제 나무 팔)만 보존
        if stats[i, cv2.CC_STAT_AREA] > 100:
            wood_mask_final[labels == i] = 255
            
    # PIL 변환 및 팔/손 영역 크롭
    mannequin_np = np.array(mannequin_nobg)
    mannequin_np[:,:,3] = wood_mask_final # 정화된 알파 채널 대입
    mannequin_wood = Image.fromarray(mannequin_np)
    
    # 팔 영역 크롭 (Y: 140~215, X: 290~395 - 엘보우 실루엣까지 포함)
    arm_nobg = mannequin_wood.crop((290, 140, 395, 215))
    
    hand_scale = mq_w / mannequin_cropped.width
    hd_w = int(arm_nobg.width * hand_scale)
    hd_h = int(arm_nobg.height * hand_scale)
    arm_scaled = arm_nobg.resize((hd_w, hd_h), Image.Resampling.LANCZOS)
    
    # 팔의 위치 역산 (Y: 140, X: 290)
    hd_rel_x = 290 - 262
    hd_rel_y = 140 - 32
    
    hd_x = mq_x + int(hd_rel_x * hand_scale)
    hd_y = mq_y + int(hd_rel_y * hand_scale)
    
    # 팔/손 드롭 섀도우 생성 (셔츠 위에 자연스러운 그림자가 드리워짐!)
    arm_alpha = arm_scaled.split()[3]
    arm_shadow = create_drop_shadow(arm_alpha, offset=(3, 5), blur_radius=6, opacity=0.35)
    canvas.paste(arm_shadow, (hd_x + 2, hd_y + 4), arm_shadow)
    
    # 팔 본체 합성
    canvas.paste(arm_scaled, (hd_x, hd_y), arm_scaled)
    print(f"  마네킹 팔 탑 레이어 합성 완료: 위치 ({hd_x}, {hd_y})")
    
    # 8. 최종 화질 보정 (원본 색감을 유지하는 선에서 대비와 선명도 극대화)
    result = canvas.convert("RGB")
    result = ImageEnhance.Contrast(result).enhance(1.04)
    result = ImageEnhance.Sharpness(result).enhance(1.05)
    
    # 9. 저장
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result.save(output_path, "JPEG", quality=98)
    print(f"[FINISH] 프리미엄 정밀 착장 피팅 완료: {output_path}")

if __name__ == "__main__":
    render_final_original_fitting()