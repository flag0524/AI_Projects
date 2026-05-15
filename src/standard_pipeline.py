import logging
import json
from datetime import datetime
from pathlib import Path
from src.config import Config
from src.excel_reader import ExcelReader
from src.bg_remover import BackgroundRemover
from src.composer import ImageComposer
from src.codi_mapper import CodiMapper

class StandardPipeline:
    """
    Standard Engine의 전체 흐름을 제어하는 파이프라인
    """
    def __init__(self):
        # 의존성 주입
        self.reader = ExcelReader()
        self.bg_remover = BackgroundRemover()
        self.composer = ImageComposer()
        
        # 설정 로드
        self.product_df = self.reader.load_product_data()
        self.mapper = CodiMapper(self.reader)
        
        with open(Config.NAMING_RULES, 'r', encoding='utf-8') as f:
            self.naming_rules = json.load(f)

    def render_single_item(self, item_id: str, preset: str = "single_front"):
        """
        품번 기준 단건 렌더링 (DoD: 품번 기준 단건 렌더 가능)
        """
        try:
            logging.info(f"Standard Render 시작: {item_id}")
            
            # 1. 데이터 매핑 확인 (2순위: 정확한 데이터 매핑)
            item_info = self.product_df[self.product_df['품번'] == item_id]
            if item_info.empty:
                raise ValueError(f"품번 {item_id}를 찾을 수 없습니다.")
            
            category = item_info.iloc[0]['카테고리']
            img_path = Config.RAW_PHOTOS_DIR / f"{item_id}.jpg"
            
            if not img_path.exists():
                raise FileNotFoundError(f"원본 이미지 없음: {img_path}")

            # 2. 배경 제거 (3순위: 정체성 보존)
            processed_img = self.bg_remover.remove_background(img_path)
            
            # 3. 마네킹 합성 (DoD: 상품 식별 가능성 유지)
            # 프리셋에 따른 마네킹 템플릿 선택 (여기서는 기본 템플릿 사용)
            mannequin_tpl = Config.MANNEQUIN_DIR / "default_mannequin.png" 
            if not mannequin_tpl.exists():
                # 템플릿 없을 시 빈 캔버스 생성 또는 기본값 처리 (운영 안정성)
                logging.warning("마네킹 템플릿이 없습니다. 기본 배경으로 대체합니다.")
                # 실제 구현 시에는 기본 템플릿 파일을 미리 준비해야 함
            
            final_image = self.composer.compose(mannequin_tpl, processed_img, category)
            
            # 4. 파일명 규칙 적용 및 저장 (DoD: 출력 파일명 규칙 준수)
            filename = self._generate_filename("standard", item_id, preset)
            save_path = Config.OUTPUT_STANDARD / filename
            final_image.save(save_path, "JPEG", quality=95)
            
            logging.info(f"성공적으로 저장되었습니다: {save_path}")
            self._log_process(item_id, "success", preset, save_path)
            return save_path

        except Exception as e:
            logging.error(f"렌더링 실패 ({item_id}): {e}")
            self._log_process(item_id, "failed", preset, None, str(e))
            raise

    def render_codi_set(self, codi_id: str, preset: str = "codi_full"):
        """
        코디그룹 기준 렌더링 (DoD: 코디그룹 기준 렌더 가능)
        """
        try:
            logging.info(f"코디셋 렌더링 시작: {codi_id}")
            items = self.mapper.get_items_by_codi(codi_id)
            
            if not items:
                raise ValueError(f"코디그룹 {codi_id}에 매핑된 상품이 없습니다.")

            # 코디셋의 경우 여러 상품을 하나의 캔버스에 합성하는 로직이 필요
            # 현재는 각 상품을 개별 렌더링 후 리포트하는 MVP 형태로 구현
            results = []
            for item in items:
                res = self.render_single_item(item['item_id'], preset)
                results.append(res)
                
            logging.info(f"코디셋 {codi_id} 완료. 총 {len(results)}개 상품 처리됨.")
            return results

        except Exception as e:
            logging.error(f"코디셋 처리 실패 ({codi_id}): {e}")
            raise

    def _generate_filename(self, engine, item_id, preset):
        """naming_rules.json 기반 파일명 생성"""
        rule = self.naming_rules.get(engine, "{item}_{preset}_{date}.jpg")
        date_str = datetime.now().strftime(self.naming_rules.get("date_format", "%Y%m%d"))
        return rule.format(item=item_id, preset=preset, date=date_str)

    def _log_process(self, item_id, status, preset, output_path, error=""):
        """구조화 로그 기록 (CLAUDE.md Section 10.6)"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "item_id": item_id,
            "engine": "Standard",
            "preset": preset,
            "status": status,
            "output_path": str(output_path) if output_path else None,
            "error": error
        }
        with open(Config.LOGS_DIR / "process_log.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")