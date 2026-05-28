from ai_vton_engine import SOTA_VTON_Engine
from pathlib import Path

def main():
    engine = SOTA_VTON_Engine()
    
    # 입력 경로 설정
    base_dir = Path('d:/blandu_project/input/raw_photos')
    mannequin_path = base_dir / "mannequin.png"
    top_path = base_dir / "top.png"
    
    if not mannequin_path.exists() or not top_path.exists():
        print("Error: Input images not found. Please check the path.")
        return

    # AI 파이프라인 실행
    result = engine.run_pipeline(str(mannequin_path), str(top_path))
    
    # 결과 저장
    output_path = Path('d:/blandu_project/output/hybrid/AI_SOTA_FIT.png')
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result.save(output_path)
    print(f"Success! Final result saved to: {output_path}")

if __name__ == "__main__":
    main()