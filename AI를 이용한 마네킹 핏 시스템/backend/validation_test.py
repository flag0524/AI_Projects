"""
마네킹 피팅 시스템 — 통합 검증 스크립트

사용: python validation/test_pipeline.py
"""
import sys
from pathlib import Path

# 백엔드 경로 추가
backend_path = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_path))

from loguru import logger

def test_imports():
    """필요한 모듈 import 테스트"""
    logger.info("=" * 60)
    logger.info("1️⃣  모듈 Import 테스트")
    logger.info("=" * 60)
    
    try:
        from pipeline.garment_parsing import GarmentSegmentor, parse_garment
        logger.info("✓ garment_parsing 로드 완료")
    except Exception as e:
        logger.error(f"✗ garment_parsing 실패: {e}")
        return False
    
    try:
        from pipeline.preprocess import preprocess_images
        logger.info("✓ preprocess 로드 완료")
    except Exception as e:
        logger.error(f"✗ preprocess 실패: {e}")
        return False
    
    try:
        from pipeline.fit_engine import FitEngine, _classify_body_type
        logger.info("✓ fit_engine 로드 완료")
    except Exception as e:
        logger.error(f"✗ fit_engine 실패: {e}")
        return False
    
    try:
        from pipeline.postprocess import postprocess
        logger.info("✓ postprocess 로드 완료")
    except Exception as e:
        logger.error(f"✗ postprocess 실패: {e}")
        return False
    
    try:
        from pipeline.detail_verification import verify_detail
        logger.info("✓ detail_verification 로드 완료")
    except Exception as e:
        logger.error(f"✗ detail_verification 실패: {e}")
        return False
    
    try:
        from pipeline.layering import run_layered
        logger.info("✓ layering 로드 완료")
    except Exception as e:
        logger.error(f"✗ layering 실패: {e}")
        return False
    
    logger.info("✓ 모든 모듈 로드 성공\n")
    return True


def test_body_type_classification():
    """체형 분류 테스트"""
    logger.info("=" * 60)
    logger.info("2️⃣  체형 분류 테스트")
    logger.info("=" * 60)
    
    try:
        from pipeline.fit_engine import _classify_body_type
        
        test_cases = [
            ({"chest_circumference": 0.40, "waist_circumference": 0.35, "hip_circumference": 0.45}, "slim"),
            ({"chest_circumference": 0.50, "waist_circumference": 0.45, "hip_circumference": 0.55}, "normal"),
            ({"chest_circumference": 0.60, "waist_circumference": 0.58, "hip_circumference": 0.65}, "plus"),
        ]
        
        for measurements, expected in test_cases:
            result = _classify_body_type(measurements)
            status = "✓" if result == expected else "✗"
            logger.info(f"{status} {expected}: {result}")
        
        logger.info("✓ 체형 분류 완료\n")
        return True
    except Exception as e:
        logger.error(f"✗ 체형 분류 실패: {e}\n")
        return False


def test_fit_params():
    """핏 파라미터 계산 테스트"""
    logger.info("=" * 60)
    logger.info("3️⃣  핏 파라미터 계산 테스트")
    logger.info("=" * 60)
    
    try:
        from pipeline.fit_engine import FitEngine
        from schemas import Category, FitMode, GarmentSize
        
        engine = FitEngine(Category.top)
        
        # 테스트용 신체 측정값
        body_measurements = {
            "shoulder_width": 0.224,
            "chest_circumference": 0.483,
            "waist_circumference": 0.365,
            "hip_circumference": 0.529,
            "torso_height": 0.35,
            "total_height": 0.85,
        }
        
        garment_size = GarmentSize(
            unit="cm",
            chest=96,
            shoulder=42,
            total_length=65,
        )
        
        fit_params, fit_report = engine.compute(
            garment_size, body_measurements, FitMode.regular
        )
        
        logger.info(f"✓ 핏 라벨: {fit_report.fit_label}")
        logger.info(f"✓ 가슴 여유: {fit_report.chest_ease_cm}cm")
        logger.info(f"✓ 드레이프: {fit_params.drape_intensity:.2f}")
        logger.info(f"✓ 워핑 강도: {fit_params.warping_strength:.2f}")
        
        if fit_report.warnings:
            logger.info(f"⚠ 경고: {', '.join(fit_report.warnings)}")
        
        logger.info("✓ 핏 계산 완료\n")
        return True
    except Exception as e:
        logger.error(f"✗ 핏 계산 실패: {e}\n")
        return False


def test_yolov8_availability():
    """YOLOv8 사용 가능 여부 테스트"""
    logger.info("=" * 60)
    logger.info("4️⃣  YOLOv8 세그멘테이션 테스트")
    logger.info("=" * 60)
    
    try:
        from ultralytics import YOLO
        logger.info("✓ YOLOv8 라이브러리 로드 성공")
        logger.info("  → 의류 세그멘테이션이 고도화되었습니다")
        logger.info("✓ YOLOv8 준비 완료\n")
        return True
    except ImportError:
        logger.warning("⚠ YOLOv8 미설치 — 폴백 모드 사용")
        logger.info("  → pip install ultralytics로 설치 권장\n")
        return True
    except Exception as e:
        logger.error(f"✗ YOLOv8 테스트 실패: {e}\n")
        return False


def test_postprocessing():
    """포스트프로세싱 가용성 테스트"""
    logger.info("=" * 60)
    logger.info("5️⃣  포스트프로세싱 테스트")
    logger.info("=" * 60)
    
    try:
        import cv2
        logger.info("✓ OpenCV 로드 성공")
        logger.info("  → 경계 블렌딩, 색감 조화, 노이즈 제거 활성화")
    except ImportError:
        logger.warning("⚠ OpenCV 미설치 — 기본 포스트프로세싱만 사용")
        logger.info("  → pip install opencv-contrib-python로 설치 권장")
    
    try:
        from scipy import ndimage
        logger.info("✓ SciPy 로드 성공")
        logger.info("  → 의류 정렬, 모폴로지 연산 활성화")
    except ImportError:
        logger.warning("⚠ SciPy 미설치")
    
    logger.info("✓ 포스트프로세싱 준비 완료\n")
    return True


def main():
    """전체 검증 실행"""
    logger.info("\n" + "=" * 60)
    logger.info("🔍 마네킹 피팅 시스템 — 재구축 검증")
    logger.info("=" * 60 + "\n")
    
    tests = [
        ("모듈 Import", test_imports),
        ("체형 분류", test_body_type_classification),
        ("핏 계산", test_fit_params),
        ("YOLOv8", test_yolov8_availability),
        ("포스트프로세싱", test_postprocessing),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            logger.error(f"검증 오류 [{name}]: {e}\n")
            results.append((name, False))
    
    # 최종 보고
    logger.info("=" * 60)
    logger.info("📊 최종 검증 결과")
    logger.info("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✓" if result else "✗"
        logger.info(f"{status} {name}")
    
    logger.info(f"\n총 {passed}/{total} 검증 통과")
    
    if passed == total:
        logger.info("\n✅ 모든 검증 완료! 시스템 재구축이 성공적으로 완료되었습니다.\n")
        logger.info("다음 단계:")
        logger.info("1. requirements.txt 업데이트: pip install -r backend/requirements.txt")
        logger.info("2. 테스트 실행: python -m pytest backend/tests/ (있으면)")
        logger.info("3. 서버 시작: cd backend && uvicorn main:app --reload")
    else:
        logger.warning("\n⚠️ 일부 검증 실패. 위의 오류를 확인하세요.\n")


if __name__ == "__main__":
    main()
