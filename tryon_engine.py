import cv2
import numpy as np
from PIL import Image, ImageFilter
from rembg import remove

class TryOnEngine:
    def __init__(self):
        print("[Engine] High-Fidelity Virtual Try-On Engine Initialized")

    def remove_background(self, img_pil):
        """의류의 디자인과 질감을 보존하며 배경만 정밀하게 제거"""
        try:
            # rembg를 이용한 1차 제거
            result = remove(img_pil)
            res_np = np.array(result)
            
            # 결과가 너무 투명하면 폴백 실행
            if res_np.shape[2] == 4 and np.sum(res_np[:, :, 3]) < (res_np.shape[0] * res_np.shape[1] * 0.01):
                raise ValueError("Too transparent")
            return result
        except Exception:
            # 폴백: HSV 기반 정밀 마스킹 (디자인 보존형)
            img_np = np.array(img_pil.convert("RGB"))
            hsv = cv2.cvtColor(img_np, cv2.COLOR_RGB2HSV)
            # 밝은 배경(흰색계열) 추출
            lower_white = np.array([0, 0, 200])
            upper_white = np.array([180, 50, 255])
            mask = cv2.inRange(hsv, lower_white, upper_white)
            alpha = cv2.bitwise_not(mask)
            
            # 엣지 정교화
            kernel = np.ones((3,3), np.uint8)
            alpha = cv2.morphologyEx(alpha, cv2.MORPH_CLOSE, kernel)
            
            img_rgba = cv2.cvtColor(img_np, cv2.COLOR_RGB2RGBA)
            img_rgba[:, :, 3] = alpha
            return Image.fromarray(img_rgba)

    def fit_clothing_hybrid(self, mannequin_path, top_path, bottom_path=None):
        """마네킹 체형에 맞춘 자동 피팅 및 입체 합성"""
        # 1. 이미지 로드 (최고 품질)
        mannequin = Image.open(mannequin_path).convert("RGBA")
        top_img = Image.open(top_path).convert("RGBA")
        
        m_w, m_h = mannequin.size
        
        # 2. 의류 배경 제거 및 퀄리티 보존 리사이징
        top_no_bg = self.remove_background(top_img)
        
        # [자동 비율 조정] 마네킹 체형 분석 기반 (어깨/몸통 비율)
        # 상의: 어깨 너비 92%, 길이 48%, 넥라인 3% 위치
        target_w = int(m_w * 0.92)
        target_h = int(m_h * 0.48)
        top_resized = top_no_bg.resize((target_w, target_h), Image.Resampling.LANCZOS)
        
        # 3. 위치 결정 (넥라인 밀착)
        top_x = (m_w - target_w) // 2
        top_y = int(m_h * 0.03)
        
        # 4. 하의 처리 (있는 경우)
        bottom_layer = Image.new("RGBA", (m_w, m_h), (0,0,0,0))
        if bottom_path:
            bottom_img = Image.open(bottom_path).convert("RGBA")
            bottom_no_bg = self.remove_background(bottom_img)
            
            # 하의: 골반 너비 75%, 길이 38%, 상의와 연결되는 41% 위치
            b_target_w = int(m_w * 0.75)
            b_target_h = int(m_h * 0.38)
            bottom_resized = bottom_no_bg.resize((b_target_w, b_target_h), Image.Resampling.LANCZOS)
            
            b_x = (m_w - b_target_w) // 2
            b_y = int(m_h * 0.41)
            bottom_layer.paste(bottom_resized, (b_x, b_y), bottom_resized)

        # 5. 입체 레이어 합성 (Z-Index 처리)
        # 레이어 1: 마네킹 베이스
        final_canvas = mannequin.copy()
        
        # 레이어 2: 의류 합성 (상의 + 하의)
        clothing_layer = Image.new("RGBA", (m_w, m_h), (0,0,0,0))
        clothing_layer.paste(top_resized, (top_x, top_y), top_resized)
        clothing_layer.alpha_composite(bottom_layer)
        
        # 6. [핵심] 팔 영역 복구 (Z-Index 최상단)
        # 마네킹의 팔 영역만 추출하여 최상단에 덮어씌움
        arm_mask = self._generate_arm_mask(mannequin)
        
        # 최종 합성
        final_img = Image.alpha_composite(final_canvas, clothing_layer)
        
        # 팔 영역을 다시 덮어씌워 옷이 팔 뒤로 가게 함
        final_img.paste(mannequin, (0,0), arm_mask)
        
        return final_img.convert("RGB")

    def _generate_arm_mask(self, mannequin):
        """마네킹의 팔 부분을 인식하여 마스크 생성 (단순화된 영역 기반)"""
        m_np = np.array(mannequin)
        # 마네킹의 양 끝(팔 부분)을 인식하는 마스크 (임계값 기반)
        # 실제 구현 시에는 딥러닝 세그멘테이션 마스크를 사용하나, 여기서는 영역 기반으로 처리
        mask = np.zeros((m_np.shape[0], m_np.shape[1]), dtype=np.uint8)
        # 양쪽 팔 영역 (좌우 15% 영역)
        width = m_np.shape[1]
        mask[:, :int(width*0.15)] = 255
        mask[:, int(width*0.85):] = 255
        return Image.fromarray(mask).convert("L")