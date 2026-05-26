from tryon_engine import TryOnEngine
import os

def verify():
    engine = TryOnEngine()
    
    # 테스트 경로 설정
    mannequin_path = "input/raw_photos/마네킨 컷.png"
    top_path = "input/raw_photos/ITEM-001.png"
    
    if not os.path.exists(mannequin_path):
        print(f"Error: {mannequin_path} not found")
        return

    print("[INFO] Starting verification: Hybrid Fitting Engine Test...")
    try:
        result = engine.fit_clothing_hybrid(mannequin_path, top_path=top_path)
        
        # 결과 저장
        os.makedirs("output/hybrid", exist_ok=True)
        save_path = "output/hybrid/VERIFICATION_RESULT.png"
        result.save(save_path)
        print(f"✅ 검증 완료! 결과 저장됨: {save_path}")
    except Exception as e:
        print(f"❌ 검증 실패: {e}")

if __name__ == "__main__":
    verify()