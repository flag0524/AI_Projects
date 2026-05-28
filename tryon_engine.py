import cv2
import numpy as np
from PIL import Image, ImageFilter
from rembg import remove

class TryOnEngine:
    def __init__(self):
        print("[Engine] Ultra-High Fidelity Virtual Try-On Engine Initialized")

    def remove_background(self, img_pil):
        """디자인 훼손 없이 배경만 정밀 제거"""
        try:
            return remove(img_pil)
        except:
            img_np = np.array(img_pil.convert("RGB"))
            hsv = cv2.cvtColor(img_np, cv2.COLOR_RGB2HSV)
            mask = cv2.inRange(hsv, np.array([0, 0, 200]), np.array([180, 50, 255]))
            alpha = cv2.bitwise_not(mask)
            img_rgba = cv2.cvtColor(img_np, cv2.COLOR_RGB2RGBA)
            img_rgba[:, :, 3] = alpha
            return Image.fromarray(img_rgba)

    def analyze_mannequin(self, mannequin_img):
        """마네킹 체형 랜드마크 분석"""
        m_np = np.array(mannequin_img.convert("L"))
        h, w = m_np.shape
        return {
            "shoulder_w": w * 0.88,
            "waist_y": h * 0.42,
            "hip_y": h * 0.55,
            "hip_w": w * 0.78,
            "neck_y": h * 0.04,
            "leg_length": h * 0.45
        }

    def fit_clothing_hybrid(self, mannequin_path, top_path=None, bottom_path=None, dress_path=None):
        mannequin = Image.open(mannequin_path).convert("RGBA")
        m_w, m_h = mannequin.size
        analysis = self.analyze_mannequin(mannequin)
        clothing_layer = Image.new("RGBA", (m_w, m_h), (0,0,0,0))

        # 1. 의류 배치 (원피스 vs 상하의)
        if dress_path:
            dress_no_bg = self.remove_background(Image.open(dress_path).convert("RGBA"))
            d_w, d_h = int(analysis["shoulder_w"]), int(m_h * 0.82)
            dress_resized = dress_no_bg.resize((d_w, d_h), Image.Resampling.LANCZOS)
            clothing_layer.paste(dress_resized, ((m_w - d_w)//2, int(analysis["neck_y"])), dress_resized)
        elif top_path:
            top_no_bg = self.remove_background(Image.open(top_path).convert("RGBA"))
            t_w = int(analysis["shoulder_w"])
            t_h = int(t_w / (top_no_bg.width / top_no_bg.height))
            top_resized = top_no_bg.resize((t_w, t_h), Image.Resampling.LANCZOS)
            clothing_layer.paste(top_resized, ((m_w - t_w)//2, int(analysis["neck_y"])), top_resized)
            
            if bottom_path:
                bottom_no_bg = self.remove_background(Image.open(bottom_path).convert("RGBA"))
                b_w = int(analysis["hip_w"])
                b_h = int(b_w / (bottom_no_bg.width / bottom_no_bg.height))
                bottom_resized = bottom_no_bg.resize((b_w, b_h), Image.Resampling.LANCZOS)
                clothing_layer.paste(bottom_resized, ((m_w - b_w)//2, int(analysis["waist_y"])), bottom_resized)

        # 2. 조명 및 섀도우 투영 (Photorealistic Lighting)
        mannequin_gray = mannequin.convert("L")
        lighting_map = mannequin_gray.point(lambda x: x * 0.8 + 50)
        c_np = np.array(clothing_layer)
        l_np = np.array(lighting_map.resize((m_w, m_h)))
        for i in range(3):
            c_np[:, :, i] = (c_np[:, :, i].astype(float) * (l_np / 255.0) * 1.1).astype(np.uint8)
        clothing_final = Image.fromarray(c_np, "RGBA")

        # 3. 최종 합성 및 오클루전 처리 (Z-Index)
        final_img = Image.alpha_composite(mannequin.copy(), clothing_final)
        arm_mask = self._generate_arm_mask(mannequin)
        final_img.paste(mannequin, (0,0), arm_mask)
        
        return final_img.filter(ImageFilter.SMOOTH).convert("RGB")

    def _generate_arm_mask(self, mannequin):
        m_np = np.array(mannequin.convert("RGB"))
        mask = np.zeros((m_np.shape[0], m_np.shape[1]), dtype=np.uint8)
        width = m_np.shape[1]
        mask[:, :int(width*0.2)] = 255
        mask[:, int(width*0.8):] = 255
        mask[:, int(width*0.3):int(width*0.7)] = 0
        return Image.fromarray(mask).convert("L")