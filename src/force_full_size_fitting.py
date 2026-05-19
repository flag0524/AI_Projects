import cv2
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter
from pathlib import Path
from rembg import remove

def create_drop_shadow(alpha_mask, offset=(0, 6), blur_radius=12, opacity=0.3):
    """
    Generate a smooth, natural drop shadow from an alpha mask.
    """
    shadow = Image.new("L", alpha_mask.size, 0)
    shadow.paste(int(255 * opacity), (0, 0), alpha_mask)
    shadow = shadow.filter(ImageFilter.GaussianBlur(blur_radius))
    
    shadow_rgba = Image.new("RGBA", alpha_mask.size, (0, 0, 0, 0))
    black_img = Image.new("RGBA", alpha_mask.size, (0, 0, 0, 255))
    shadow_rgba.paste(black_img, (0, 0), shadow)
    
    offset_shadow = Image.new("RGBA", alpha_mask.size, (0, 0, 0, 0))
    offset_shadow.paste(shadow_rgba, offset)
    return offset_shadow

def remove_bg(img_path: Path) -> Image.Image:
    print(f"[BG] Removing background: {img_path.name}")
    with open(img_path, 'rb') as f:
        img = Image.open(f).convert("RGB")
    return remove(img, post_process_mask=True)

def render_full_size_fitting():
    print("[BLANDU PREMIUM] Starting smooth-tailored premium cuff-aligned natural fitting on Cut 2...")
    
    # 1. Paths
    mannequin_path = Path(r"d:\blandu_project\input\raw_photos\마네킨 컷2.png")
    top_path = Path(r"d:\blandu_project\input\raw_photos\ITEM-001.png")
    bottom_path = Path(r"d:\blandu_project\input\raw_photos\ITEM-002.png")
    output_path = Path(r"d:\blandu_project\output\hybrid\FULL_SIZE_LOOK_CUT2.jpg")
    
    if not mannequin_path.exists() or not top_path.exists() or not bottom_path.exists():
        print("[ERROR] Resource files are missing.")
        return
    
    # 2. Remove backgrounds using AI (rembg)
    mq_nobg = remove_bg(mannequin_path)
    top_nobg = remove_bg(top_path)
    bottom_nobg = remove_bg(bottom_path)
    
    # 3. Crop to exact foreground bounding boxes
    mq_bbox = mq_nobg.split()[-1].getbbox()
    top_bbox = top_nobg.split()[-1].getbbox()
    bottom_bbox = bottom_nobg.split()[-1].getbbox()
    
    mq_cropped = mq_nobg.crop(mq_bbox)
    top_cropped = top_nobg.crop(top_bbox)
    bottom_cropped = bottom_nobg.crop(bottom_bbox)
    
    # 4. Canvas setup (Premium 1200x1600 standard)
    canvas_w, canvas_h = 1200, 1600
    canvas = Image.new("RGBA", (canvas_w, canvas_h), (255, 255, 255, 255))
    
    # 5. Extract wood mask to isolate arms and hands
    mq_np = np.array(mq_cropped)
    r, g, b, alpha = cv2.split(mq_np)
    wood_mask = ((r > g + 12) & (g > b + 8) & (r > 90)).astype(np.uint8) * 255
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    wood_mask_clean = cv2.morphologyEx(wood_mask, cv2.MORPH_OPEN, kernel)
    
    # PREMIUM SURGICAL ARM ERASING (100% Protected Central Body)
    # Erase ONLY in outer side columns (x < 33 or x > 120) and below shoulders (y > 119).
    # This prevents any wooden-arm ghosting while keeping head/neck/torso 100% untouched and smooth!
    mq_armless_np = mq_np.copy()
    h_mq, w_mq, c_mq = mq_armless_np.shape
    for y in range(119, h_mq):
        for x in range(w_mq):
            if (x < 33 or x > 120) and wood_mask_clean[y, x] > 0:
                mq_armless_np[y, x, 3] = 0
    
    mq_armless = Image.fromarray(mq_armless_np)
    
    # Scale and position the armless mannequin base on the canvas
    mq_h = 1400
    mq_w = int(mq_cropped.width * (mq_h / mq_cropped.height))
    mq_scaled = mq_armless.resize((mq_w, mq_h), Image.Resampling.LANCZOS)
    
    mq_x = (canvas_w - mq_w) // 2
    mq_y = 100
    
    # Paste armless mannequin on canvas (Layer 1)
    canvas.paste(mq_scaled, (mq_x, mq_y), mq_scaled)
    print(f"Placed Armless Mannequin at ({mq_x}, {mq_y}) with size {mq_w}x{mq_h}")
    
    scale_factor = mq_h / mq_cropped.height
    
    # Create the wood layer with transparent background for the hands overlay
    mq_wood_np = mq_np.copy()
    mq_wood_np[:, :, 3] = cv2.bitwise_and(alpha, wood_mask_clean)
    mq_wood = Image.fromarray(mq_wood_np)
    mq_wood_scaled = mq_wood.resize((mq_w, mq_h), Image.Resampling.LANCZOS)
    
    # Extract left hand and right hand separately from scaled wood layer
    center_x = mq_w // 2
    
    # Left hand (screen-left)
    left_hand_crop = mq_wood_scaled.crop((0, 560, center_x, 780))
    left_hand_bbox = left_hand_crop.split()[-1].getbbox()
    if left_hand_bbox:
        left_hand_tight = left_hand_crop.crop(left_hand_bbox)
    else:
        left_hand_tight = left_hand_crop
    left_hand_tight = left_hand_tight.rotate(-15, resample=Image.Resampling.BICUBIC, expand=True)
        
    # Right hand (screen-right)
    right_hand_crop = mq_wood_scaled.crop((center_x, 560, mq_w, 780))
    right_hand_bbox = right_hand_crop.split()[-1].getbbox()
    if right_hand_bbox:
        right_hand_tight = right_hand_crop.crop(right_hand_bbox)
    else:
        right_hand_tight = right_hand_crop
    right_hand_tight = right_hand_tight.rotate(15, resample=Image.Resampling.BICUBIC, expand=True)
    
    # 7. Scale and Position Shirt (ITEM-001) - PERFECT SNUG TORSO FIT
    tp_w = 460
    tp_h = int(top_cropped.height * (tp_w / top_cropped.width))
    top_scaled = top_cropped.resize((tp_w, tp_h), Image.Resampling.LANCZOS)
    
    tp_x = (canvas_w - tp_w) // 2
    canvas_shoulder_y = mq_y + int(67 * scale_factor)
    tp_y = canvas_shoulder_y + int(15 * scale_factor) 
    
    # Precise hand cuff opening positions scaled dynamically to new shirt width
    left_cuff_rel = (int(15 * tp_w / 520), int(534 * tp_w / 520))
    right_cuff_rel = (int(505 * tp_w / 520), int(542 * tp_w / 520))
    
    left_cuff_x = tp_x + left_cuff_rel[0]
    left_cuff_y = tp_y + left_cuff_rel[1]
    
    right_cuff_x = tp_x + right_cuff_rel[0]
    right_cuff_y = tp_y + right_cuff_rel[1]
    
    print(f"Canvas Left Cuff: ({left_cuff_x}, {left_cuff_y})")
    print(f"Canvas Right Cuff: ({right_cuff_x}, {right_cuff_y})")
    
    # 8. Scale and Position Pants (ITEM-002) - TAILORED TROUSERS
    shirt_belt_y = tp_y + int(tp_h * 0.64)
    
    bt_w = 320
    bt_h = int(bottom_cropped.height * (bt_w / bottom_cropped.width))
    bottom_scaled = bottom_cropped.resize((bt_w, bt_h), Image.Resampling.LANCZOS)
    
    bt_x = (canvas_w - bt_w) // 2
    bt_y = shirt_belt_y - int(10 * scale_factor) 
    
    # 9. Synthesize in precise 3D Layers
    # Layer 2: Paste rotated hands UNDER the clothes so the sleeve cuffs naturally overlap the wrists!
    # Left hand
    lh_w, lh_h = left_hand_tight.size
    lh_x = left_cuff_x - lh_w // 2 + 10
    lh_y = left_cuff_y - 30 
    canvas.paste(left_hand_tight, (lh_x, lh_y), left_hand_tight)
    
    # Right hand
    rh_w, rh_h = right_hand_tight.size
    rh_x = right_cuff_x - rh_w // 2 - 10
    rh_y = right_cuff_y - 30 
    canvas.paste(right_hand_tight, (rh_x, rh_y), right_hand_tight)
    
    # Layer 3: Pants Drop Shadow
    bottom_alpha = bottom_scaled.split()[3]
    bottom_shadow = create_drop_shadow(bottom_alpha, offset=(0, 6), blur_radius=12, opacity=0.15)
    canvas.paste(bottom_shadow, (bt_x, bt_y), bottom_shadow)
    
    # Layer 4: Pants
    canvas.paste(bottom_scaled, (bt_x, bt_y), bottom_scaled)
    
    # Layer 5: Shirt Drop Shadow
    top_shadow = create_drop_shadow(top_scaled.split()[3], offset=(0, 5), blur_radius=10, opacity=0.20)
    canvas.paste(top_shadow, (tp_x, tp_y), top_shadow)
    
    # Layer 6: Shirt
    canvas.paste(top_scaled, (tp_x, tp_y), top_scaled)
    
    print("Synthesized angled hands sticking out of snug cuffs with sleeve overlapping wrists.")
    
    # 10. High-end Post-Processing
    result = canvas.convert("RGB")
    result = ImageEnhance.Contrast(result).enhance(1.04)
    result = ImageEnhance.Brightness(result).enhance(1.01)
    result = ImageEnhance.Sharpness(result).enhance(1.04)
    
    # Save output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result.save(output_path, "JPEG", quality=98)
    print(f"[FINISH] Smooth tailored natural fitting completed successfully: {output_path}")

if __name__ == "__main__":
    render_full_size_fitting()