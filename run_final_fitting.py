import os
import glob
from tryon_engine import TryOnEngine

def main():
    engine = TryOnEngine()
    
    # 1. 마네킹 이미지 찾기 (파일명 상관없이 폴더 내 첫 번째 png 파일 선택)
    mannequin_files = glob.glob("input/raw_photos/*.png")
    # ITEM-001, ITEM-002가 아닌 파일을 마네킹으로 간주
    mannequin_path = None
    for f in mannequin_files:
        if "ITEM" not in os.path.basename(f):
            mannequin_path = f
            break
    
    if not mannequin_path:
        print("Error: 마네킹 이미지를 찾을 수 없습니다.")
        return

    top_path = "input/raw_photos/ITEM-001.png"
    bottom_path = "input/raw_photos/ITEM-002.png"
    output_path = "output/hybrid/FINAL_NATURAL_FIT.png"
    
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    print(f"Processing natural fitting...")
    print(f"Using mannequin: {mannequin_path}")
    
    try:
        result_img = engine.fit_clothing_hybrid(mannequin_path, top_path, bottom_path)
        result_img.save(output_path)
        print(f"Success: {output_path}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()