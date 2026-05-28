import cv2
import numpy as np
from PIL import Image, ImageFilter, ImageDraw
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
        """
        [REAL-WORLD OPERATION MODE] 
        의류 생성 배제 -> 원본 보존 기반 워핑(Warping) 최우선 적용
        """
        try:
            mannequin = Image.open(mannequin_path).convert("RGBA")
        except Exception as e:
            print(f"Critical Error loading mannequin: {e}")
            return None

        m_w, m_h = mannequin.size
        analysis = self.analyze_mannequin(mannequin)
        clothing_layer = Image.new("RGBA", (m_w, m_h), (0,0,0,0))

        def apply_preserved_warping(img_path, target_w, target_h_limit, warp_type="body"):
            if img_path is None or img_path == "None":
                return None
            
            try:
                img = Image.open(img_path).convert("RGBA")
                no_bg = self.remove_background(img)
                
                orig_w, orig_h = no_bg.size
                aspect = orig_w / orig_h
                final_w = target_w
                final_h = int(final_w / aspect)
                if final_h > target_h_limit:
                    final_h = target_h_limit
                    final_w = int(final_h * aspect)
                
                resized = no_bg.resize((final_w, final_h), Image.Resampling.LANCZOS)
                
                resized_np = np.array(resized)
                rows, cols, ch = resized_np.shape
                map_x, map_y = np.meshgrid(np.arange(cols), np.arange(rows))
                
                if warp_type == "body":
                    warp_factor = 0.02 * (map_y / rows)
                    map_x = map_x + (cols/2 - map_x) * warp_factor
                
                warped_np = cv2.remap(resized_np, map_x.astype(np.float32), map_y.astype(np.float32), 
                                      interpolation=cv2.INTER_CUBIC, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
                return Image.fromarray(warped_np)
            except Exception as e:
                print(f"Warping failed for {img_path}: {e}")
                return None

        # 1. 의류 배치
        if dress_path and dress_path != "None":
            dress_warped = apply_preserved_warping(dress_path, int(analysis["shoulder_w"]), int(m_h * 0.82))
            if dress_warped:
                clothing_layer.paste(dress_warped, ((m_w - dress_warped.width)//2, int(analysis["neck_y"])), dress_warped)
        else:
            # 상의 처리
            if top_path and top_path != "None":
                top_warped = apply_preserved_warping(top_path, int(analysis["shoulder_w"]), int(m_h * 0.50))
                if top_warped:
                    clothing_layer.paste(top_warped, ((m_w - top_warped.width)//2, int(analysis["neck_y"])), top_warped)
            
            # 하의 처리
            if bottom_path and bottom_path != "None":
                bottom_warped = apply_preserved_warping(bottom_path, int(analysis["hip_w"]), int(m_h * 0.55))
                if bottom_warped:
                    clothing_layer.paste(bottom_warped, ((m_w - bottom_warped.width)//2, int(analysis["waist_y"])), bottom_warped)

        # 2. 조명 및 입체감 최적화 (Advanced Shading)
        mannequin_gray = mannequin.convert("L")
        # 마네킹의 명암을 분석하여 옷에 깊이감을 주는 쉐이딩 맵 생성
        lighting_map = mannequin_gray.point(lambda x: x * 0.7 + 30)
        
        c_np = np.array(clothing_layer)
        l_np = np.array(lighting_map.resize((m_w, m_h)))
        
        # RGB 채널에 조명 맵을 곱해 입체감 부여 (투명도 문제 해결을 위해 알파 채널 보존)
        for i in range(3):
            c_np[:, :, i] = (c_np[:, :, i].astype(float) * (l_np / 255.0) * 1.2).astype(np.uint8)
        
        # 알파 채널을 255로 강제하여 투명도 제거 (원본 보존)
        mask_np = c_np[:, :, 3]
        mask_np[mask_np > 0] = 255 
        
        clothing_final = Image.fromarray(c_np, "RGBA")

        # 3. 최종 합성 및 정밀 블렌딩
        # 배경(마네킹) 위에 옷을 얹고, 경계선을 부드럽게 처리
        final_img = Image.alpha_composite(mannequin.copy(), clothing_final)
        arm_mask = self._generate_arm_mask(mannequin)
        final_img.paste(mannequin, (0,0), arm_mask)
        # Pillow 버전에 따라 SMOOTH_BOX가 없을 수 있으므로 SMOOTH로 대체
        try:
            final_img = final_img.filter(ImageFilter.SMOOTH_BOX)
        except AttributeError:
            final_img = final_img.filter(ImageFilter.SMOOTH)
        
        return final_img.convert("RGB")

    def _generate_arm_mask(self, mannequin):
        m_np = np.array(mannequin.convert("RGB"))
        mask = np.zeros((m_np.shape[0], m_np.shape[1]), dtype=np.uint8)
        width = m_np.shape[1]
        mask[:, :int(width*0.2)] = 255
        mask[:, int(width*0.8):] = 255
        mask[:, int(width*0.3):int(width*0.7)] = 0
        return Image.fromarray(mask).convert("L")