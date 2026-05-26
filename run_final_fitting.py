import os
from pathlib import Path
from tryon_engine import TryOnEngine

def main():
    engine = TryOnEngine()
    
    # pathlib를 사용하여 한글 경로 및 유니코드 처리
    base_dir = Path("input/raw_photos")
    mannequin_path = base_dir / "마네킹.png"
    top_path = base_dir / "ITEM-001.png"
    bottom_path = base_dir / "ITEM-002.png"
    output_path = Path("output/hybrid/FINAL_NATURAL_FIT.png")
    
    # 출력 폴더 생성
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # 경로 존재 확인
    if not mannequin_path.exists():
        print(f"Error: 마네킹 파일을 찾을 수 없습니다: {mannequin_path}")
        return

    print(f"Processing natural fitting...")
    print(f"Using mannequin: {mannequin_path}")
    
    try:
        # 경로 객체를 문자열로 변환하여 전달
        result_img = engine.fit_clothing_hybrid(str(mannequin_path), str(top_path), str(bottom_path))
        result_img.save(str(output_path))
        print(f"Success: {output_path}")
    except Exception as e:
        print(f"Error during fitting: {e}")

if __name__ == "__main__":
    main()