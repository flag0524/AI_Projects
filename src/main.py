import argparse
import logging
import sys
from src.config import Config

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(Config.LOGS_DIR / "system.log", encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

def main():
    parser = argparse.ArgumentParser(description="BVSS - Blandu Visual Synthesis System")
    parser.add_argument("command", choices=["validate-input", "render-standard", "render-hybrid", "batch-process", "run-qc"], help="실행할 명령어")
    parser.add_argument("--item", type=str, help="대상 품번")
    parser.add_argument("--codi", type=str, help="대상 코디그룹")
    parser.add_argument("--preset", type=str, default="single_front", help="적용 프리셋")
    parser.add_argument("--muse", type=str, help="하이브리드 뮤즈 ID")
    parser.add_argument("--mode", type=str, help="배치 처리 모드")
    parser.add_argument("--target", type=str, help="QC 대상")
    parser.add_argument("--missing-only", action="store_true", help="누락 파일만 검사")
    parser.add_argument("--dry-run", action="store_true", help="실제 생성 없이 시뮬레이션")

    args = parser.parse_args()

    if args.command == "validate-input":
        from src.excel_reader import ExcelReader
        from src.validator import InputValidator
        logging.info("입력 데이터 검증 시작...")
        reader = ExcelReader()
        try:
            reader.load_product_data()
            validator = InputValidator(reader)
            result = validator.validate_all(missing_only=args.missing_only)
            print(f"\n--- Validation Result ---\nTotal: {result['total_items']}\nValid: {result['valid_count']}\nMissing: {result['missing_count']}")
            if result['missing_count'] > 0:
                print(f"Check report at: {Config.OUTPUT_QC / 'input_validation_report.json'}")
        except Exception as e:
            logging.error(f"Validation failed: {e}")

    elif args.command == "render-standard":
        from src.standard_pipeline import StandardPipeline
        logging.info("Standard Engine 렌더링 시작...")
        pipeline = StandardPipeline()
        pipeline.setup()
        
        if args.item:
            success = pipeline.render_item(args.item, preset=args.preset, dry_run=args.dry_run)
            if success:
                print(f"✅ {args.item} 렌더링 성공!")
            else:
                print(f"❌ {args.item} 렌더링 실패.")
        elif args.codi:
            results = pipeline.render_codi_set(args.codi, args.preset)
            success_count = len([r for r in results if r["status"] == "success"])
            print(f"✅ 코디그룹 {args.codi} 처리 완료: {success_count}/{len(results)} 성공")
        else:
            logging.error("품번(--item) 또는 코디그룹(--codi)을 지정해야 합니다.")

    elif args.command == "render-hybrid":
        logging.info("Hybrid Engine 렌더링 요청됨.")
        print("Hybrid Engine은 Phase 4에서 구현될 예정입니다.")

    elif args.command == "batch-process":
        logging.info("배치 프로세스 요청됨.")
        print("Batch Process는 Phase 6에서 구현될 예정입니다.")

    elif args.command == "run-qc":
        logging.info("QC 파이프라인 요청됨.")
        print("QC Pipeline은 Phase 5에서 구현될 예정입니다.")

if __name__ == "__main__":
    main()