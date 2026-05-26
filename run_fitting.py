from tryon_engine import TryOnEngine
from PIL import Image
import os

def main():
    # 엔진 초기화
    engine = TryOnEngine()
    
    # 파일 경로 설정
    mannequin_path = "input/raw_photos/마네킨 컷.png"
    top_path = "input/raw_photos/ITEM-001.png"
    bottom_path = "input/raw_photos/ITEM-002.png"
    output_path = "output/hybrid/FINAL_FITTING_RESULT.png"
    
    # 출력 폴더 생성
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    print(f"[INFO] 합성 시작...")
    print(f" - 마네킹: {mannequin_path}")
    print(f" - 상의: {top_path}")
    print(f" - 하의: {bottom_path}")
    
    try:
        # 하이브리드 피팅 엔진 실행 (튜닝된 좌표/비율 적용됨)
        result_img = engine.fit_clothing_hybrid(mannequin_path, top_path, bottom_path)
        
        # 결과 저장
        result_img.save(output_path)
        print(f"✅ 합성 완료! 결과가 저장되었습니다: {output_path}")
        
    except Exception as e:
        print(f"❌ 합성 중 오류 발생: {e}")

if __name__ == "__main__":
    main()