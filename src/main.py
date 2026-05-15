import argparse
import sys
import logging
from src.config import Config

# 로깅 설정 (CLAUDE.md Section 10.6 준수)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(Config.LOGS_DIR / "cli_main.log"),
        logging.StreamHandler(sys.stdout)
    ]
)

def main():
    parser = argparse.ArgumentParser(description="BLANCDEW Visual Styling System (BVSS) CLI")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # 1. Render Standard
    std_parser = subparsers.add_parser("render-standard", help="Generate standard mannequin images")
    std_parser.add_argument("--item", type=str, help="Product ID (품번)")
    std_parser.add_argument("--codi", type=str, help="Coordination ID (코디그룹)")
    std_parser.add_argument("--preset", type=str, default="single_front", help="Render preset")
    std_parser.add_argument("--dry-run", action="store_true", help="Simulate process without actual rendering")

    # 2. Render Hybrid
    hyb_parser = subparsers.add_parser("render-hybrid", help="Generate hybrid style images")
    hyb_parser.add_argument("--item", type=str, help="Product ID (품번)")
    hyb_parser.add_argument("--codi", type=str, help="Coordination ID (코디그룹)")
    hyb_parser.add_argument("--muse", type=str, required=True, help="Muse ID")
    hyb_parser.add_argument("--preset", type=str, default="studio_front", help="Render preset")
    hyb_parser.add_argument("--dry-run", action="store_true", help="Simulate process without actual rendering")

    # 3. Batch Process
    batch_parser = subparsers.add_parser("batch-process", help="Batch process images")
    batch_parser.add_argument("--mode", choices=["std", "hyb"], required=True, help="Engine mode")
    batch_parser.add_argument("--preset", type=str, required=True, help="Render preset")
    batch_parser.add_argument("--all", action="store_true", help="Process all items in product_data.xlsx")
    batch_parser.add_argument("--report", action="store_true", help="Generate failure report")

    # 4. QC
    qc_parser = subparsers.add_parser("run-qc", help="Run Quality Control checks")
    qc_parser.add_argument("--target", choices=["std", "hyb"], required=True, help="Target engine")
    qc_parser.add_argument("--latest", action="store_true", help="Check only the most recent outputs")
    qc_parser.add_argument("--report", action="store_true", help="Save QC results to file")

    # 5. Validate Input
    val_parser = subparsers.add_parser("validate-input", help="Validate input data and images")
    val_parser.add_argument("--check-all", action="store_true", help="Check all data integrity")
    val_parser.add_argument("--missing-only", action="store_true", help="Report only missing files")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    # 명령어 분기 처리 (각 모듈의 파이프라인으로 연결)
    logging.info(f"Executing command: {args.command} with args: {vars(args)}")
    
    from src.excel_reader import ExcelReader
    from src.validator import InputValidator
    from src.codi_mapper import CodiMapper

    from src.standard_pipeline import StandardPipeline

    if args.command == "render-standard":
        pipeline = StandardPipeline()
        if args.item:
            pipeline.render_single_item(args.item, args.preset)
        elif args.codi:
            pipeline.render_codi_set(args.codi, args.preset)
        else:
            logging.error("품번(--item) 또는 코디그룹(--codi) 중 하나를 지정해야 합니다.")
    elif args.command == "render-hybrid":
    elif args.command == "batch-process":
        # TODO: batch logic 연결
        logging.info(f"Batch Processing... Mode: {args.mode}")
    elif args.command == "run-qc":
        # TODO: qc_pipeline.py 연결
        logging.info(f"Running QC... Target: {args.target}")
    elif args.command == "validate-input":
        reader = ExcelReader()
        try:
            reader.load_product_data()
            validator = InputValidator(reader)
            result = validator.validate_all(missing_only=args.missing_only)
            print(f"\n--- Validation Result ---\nTotal: {result['total_items']}\nValid: {result['valid_count']}\nMissing: {result['missing_count']}")
            if result['missing_count'] > 0:
                print(f"Check report at: {Config.OUTPUT_QC / 'missing_files_report.json'}")
        except Exception as e:
            logging.error(f"Validation failed: {e}")

if __name__ == "__main__":
    Config.ensure_dirs()
    main()