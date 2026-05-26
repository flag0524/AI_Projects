from tryon_engine import TryOnEngine
import os

def main():
    engine = TryOnEngine()
    mannequin_path = "input/raw_photos/마네킨 컷.png"
    top_path = "input/raw_photos/ITEM-001.png"
    bottom_path = "input/raw_photos/ITEM-002.png"
    output_path = "output/hybrid/FINAL_NATURAL_FIT.png"
    
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    print("Processing natural fitting...")
    try:
        result_img = engine.fit_clothing_hybrid(mannequin_path, top_path, bottom_path)
        result_img.save(output_path)
        print(f"Success: {output_path}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()