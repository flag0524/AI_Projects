import cv2
import numpy as np
from PIL import Image
from rembg import remove
import io

class TryOnEngine:
    def __init__(self):
        # 나무 팔 영역 검출을 위한 HSV 범위 (나무 색상: 갈색/황토색 계열)
        # 실제 이미지에 따라 튜닝이 필요할 수 있습니다.
        # 나무 팔 색상 범위 확장 (밝은 베이지 ~ 어두운 갈색)
        self.lower_wood = np.array([0, 30, 50]) 
        self.upper_wood = np.array([40, 255, 255])

    def remove_background(self, img_pil):
        """의류 이미지의 배경을 제거합니다."""
        try:
            # rembg를 사용하여 배경 제거
            result = remove(img_pil)
            return result
        except Exception as e:
            print(f"Background removal failed: {e}")
            # 폴백: 흰색 배경을 투명하게 처리
            img_np = np.array(img_pil.convert("RGB"))
            mask = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
            _, alpha = cv2.threshold(mask, 240, 255, cv2.THRESH_BINARY_INV)
            
            img_rgba = cv2.cvtColor(img_np, cv2.COLOR_RGB2RGBA)
            img_rgba[:, :, 3] = alpha
            return Image.fromarray(cv2.cvtColor(img_rgba, cv2.COLOR_RGBA2RGB)) # 단순화하여 반환

    def segment_arms(self, mannequin_img_pil):
        """마네킹 이미지에서 나무 팔 영역의 마스크를 생성합니다."""
        img_np = np.array(mannequin_img_pil.convert("RGB"))
        hsv = cv2.cvtColor(img_np, cv2.COLOR_RGB2HSV)
        
        # 나무 색상 범위 마스크 생성
        mask = cv2.inRange(hsv, self.lower_wood, self.upper_wood)
        
        # 노이즈 제거를 위한 모폴로지 연산
        kernel = np.ones((5,5), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        mask = cv2.GaussianBlur(mask, (5, 5), 0)
        
        return mask

    def fit_clothing_hybrid(self, mannequin_path, top_path=None, bottom_path=None):
        """하이브리드 방식으로 옷을 피팅합니다."""
        # 1. 이미지 로드
        mannequin = Image.open(mannequin_path).convert("RGBA")
        m_np = np.array(mannequin)
        h, w, _ = m_np.shape

        # 나무 팔 마스크 생성
        arm_mask = self.segment_arms(mannequin)
        arm_mask_normalized = arm_mask.astype(float) / 255.0
        arm_mask_rgba = np.stack([arm_mask_normalized]*3, axis=-1)

        final_img = m_np.copy()

        # 상/하의 처리 루프
        items = [("top", top_path), ("bottom", bottom_path)]
        for type, path in items:
            if path is None: continue
            
            item_img = Image.open(path).convert("RGBA")
            item_no_bg = self.remove_background(item_img)
            item_np = np.array(item_no_bg)

            # [튜닝] 마네킹 체형에 맞춘 정밀 비율 조정
            if type == "top":
                # [초정밀 튜닝] 상의: 넥라인을 더 높이고 어깨 너비를 극대화하여 체형에 맞춤
                target_w = int(w * 0.92)  # 어깨 끝까지 완전히 확장
                target_h = int(h * 0.48)  # 상의 길이를 조절하여 하의와 연결 최적화
                start_y = int(h * 0.03)   # 넥라인을 목선에 완전히 밀착
            else:
                # [초정밀 튜닝] 하의: 상의 하단과 자연스럽게 겹치도록 Y축 상향 및 폭 확장
                target_w = int(w * 0.75)  # 골반 라인에 맞게 더 확장
                target_h = int(h * 0.38)
                start_y = int(h * 0.41)   # 상의와 더 밀착시켜 빈틈 제거
            
            start_x = (w - target_w) // 2
            item_resized = cv2.resize(item_np, (target_w, target_h), interpolation=cv2.INTER_AREA)
            
            # 합성 영역 슬라이싱
            end_y = start_y + target_h
            if end_y > h: end_y = h
            
            crop_h = end_y - start_y
            item_crop = item_resized[0:crop_h, 0:target_w]
            
            # 알파 블렌딩 합성 (채널 수 일치 작업)
            overlay_rgba = item_crop.astype(float) / 255.0
            overlay_rgb = overlay_rgba[:, :, :3]
            alpha = overlay_rgba[:, :, 3:4]
            
            # base 영역을 RGB로 가져옴 (final_img가 RGBA일 수 있으므로 슬라이싱 후 처리)
            base_region = final_img[start_y:end_y, start_x:start_x+target_w]
            base_rgb = base_region[:, :, :3].astype(float) / 255.0
            
            # RGB 블렌딩 계산
            blended_rgb = (overlay_rgb * alpha + base_rgb * (1 - alpha))
            
            # 결과물을 다시 uint8로 변환하여 RGB 채널에 할당
            final_img[start_y:end_y, start_x:start_x+target_w, :3] = (blended_rgb * 255).astype(np.uint8)

        # 마지막 단계: 나무 팔 영역을 다시 덮어씌워 보존 (Z-index 처리)
        # 원본 마네킹의 팔 영역을 최종 이미지 위에 다시 올림
        final_img = final_img.astype(float) / 255.0
        mannequin_base = np.array(mannequin).astype(float) / 255.0
        
        # 팔 마스크가 있는 부분만 원본으로 교체 (RGB 채널만 처리)
        final_img_rgb = final_img[:, :, :3]
        mannequin_base_rgb = mannequin_base[:, :, :3]
        
        # 마스크 적용 (RGB 3채널에 대해)
        final_rgb = np.where(arm_mask_rgba == 1.0, mannequin_base_rgb, final_img_rgb)
        
        return Image.fromarray((final_rgb * 255).astype(np.uint8))

# AI 엔진 템플릿 (IDM-VTON 등)
def fit_clothing_ai(mannequin_img, clothing_img):
    # 실제 구현 시 diffusers 및 torch 모델 로드 필요
    # 현재는 CPU 환경이므로 구조적 템플릿만 제공
    print("AI Engine is not available in CPU mode. Falling back to Hybrid.")
    return None