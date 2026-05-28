import os
from pathlib import Path
from PIL import Image
import numpy as np
from tryon_engine import TryOnEngine

def main():
    engine = TryOnEngine()
    
    base_dir = Path("input/raw_photos")
    mannequin_path = base_dir / "마네킹.png"
    top_path = base_dir / "ITEM-001.png"
    bottom_path = base_dir / "ITEM-002.png"
    output_dir = Path("output/hybrid")
    output_path = output_dir / "FINAL_NATURAL_FIT.png"
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    if not mannequin_path.exists():
        print(f"Error: 마네킹 파일을 찾을 수 없습니다: {mannequin_path}")
        return

    print(f"Processing natural fitting...")
    
    try:
        # 1. 배경 제거 단계 테스트 및 저장
        print("Step 1: Removing background from clothing...")
        top_img = Image.open(str(top_path))
        bottom_img = Image.open(str(bottom_path))
        
        top_no_bg = engine.remove_background(top_img)
        bottom_no_bg = engine.remove_background(bottom_img)
        
        top_no_bg.save(str(output_dir / "debug_top_no_bg.png"))
        bottom_no_bg.save(str(output_dir / "debug_bottom_no_bg.png"))
        
        # 2. 하이브리드 피팅 실행
        print("Step 2: Fitting clothing to mannequin...")
        result_img = engine.fit_clothing_hybrid(str(mannequin_path), str(top_path), str(bottom_path))
        result_img.save(str(output_path))
        print(f"Success: Final image saved to {output_path}")
        
    except Exception as e:
        print(f"Critical Error during fitting: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()