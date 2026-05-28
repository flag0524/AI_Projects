import os
import glob
from pathlib import Path
from PIL import Image
import numpy as np
from tryon_engine import TryOnEngine

def find_file_by_keyword(directory, keyword):
    """한글 깨짐 문제를 방지하기 위해 키워드로 파일을 검색"""
    files = glob.glob(f"{directory}/*.png")
    for f in files:
        if keyword in os.fsdecode(f):
            return Path(f)
    return None

def main():
    engine = TryOnEngine()
    base_dir = "input/raw_photos"
    
    # 키워드 기반 파일 찾기 (한글 인코딩 문제 해결)
    # 파일 존재 여부 확인 및 강제 매칭 로직
    all_files = list(Path(base_dir).glob("*.png"))
    print(f"Available files: {[f.name for f in all_files]}")
    
    mannequin_path = next((f for f in all_files if "mannequin" in f.name.lower() or "마네킹" in f.name), None)
    top_path = next((f for f in all_files if "top" in f.name.lower() or "ITEM-001" in f.name), None)
    bottom_path = next((f for f in all_files if "bottom" in f.name.lower() or "ITEM-002" in f.name), None)
    
    if not mannequin_path:
        print("Error: 마네킹 이미지를 찾을 수 없습니다.")
        return
    
    output_dir = Path("output/hybrid")
    output_path = output_dir / "FINAL_NATURAL_FIT.png"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    if not mannequin_path:
        print("Error: 마네킹 이미지를 찾을 수 없습니다.")
        return

    print(f"Processing high-fidelity fitting...")
    print(f"Mannequin: {mannequin_path}")
    print(f"Top: {top_path}")
    print(f"Bottom: {bottom_path}")
    
    try:
        # 하이브리드 피팅 실행 (INPUT SPEC 반영)
        result_img = engine.fit_clothing_hybrid(str(mannequin_path), str(top_path), str(bottom_path))
        result_img.save(str(output_path))
        print(f"Success: Final image saved to {output_path}")
        
    except Exception as e:
        print(f"Critical Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()