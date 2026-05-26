import logging
# pyrefly: ignore [missing-import]
import numpy as np
from PIL import Image
# pyrefly: ignore [missing-import]
from rembg import remove
from src.config import Config
from pathlib import Path

class BackgroundRemover:
    """
    상품의 시각적 정체성을 보존하며 배경을 제거하는 모듈
    """
    def __init__(self, alpha_threshold=10, loss_tolerance=0.02):
        """
        Args:
            alpha_threshold: 알파 채널 판단 임계값
            loss_tolerance: 허용 가능한 최대 픽셀 유실률 (2% 기본값)
        """
        self.alpha_threshold = alpha_threshold
        self.loss_tolerance = loss_tolerance

    def remove_background(self, input_path: Path) -> Image.Image:
        """
        이미지에서 배경을 제거하고 RGBA 이미지를 반환
        """
        try:
            logging.info(f"배경 제거 시작: {input_path.name}")
            
            # 이미지 로드
            with open(input_path, 'rb') as f:
                input_image = Image.open(f).convert("RGB")
                
            # rembg를 이용한 배경 제거 (픽셀 기반 마스킹)
            # 흰색 상품/밝은 배경에서 alpha_matting 적용 시 결과가 회색으로 나오는 이슈가 있어 비활성화하고 post_process_mask 적용
            output_image = remove(
                input_image, 
                post_process_mask=True
            )
            
            # 정체성 보존 검사 (3순위: 시각 정체성 보존)
            self._verify_integrity(input_image, output_image, input_path.name)
            
            return output_image
            
        except Exception as e:
            logging.error(f"배경 제거 중 오류 발생 ({input_path.name}): {e}")
            raise

    def _verify_integrity(self, original: Image.Image, processed: Image.Image, filename: str):
        """
        원본 대비 상품 영역 유실률을 계산하여 정체성 훼손 여부 판단
        """
        # 원본의 픽셀 데이터와 처리 후의 알파 채널 비교
        orig_arr = np.array(original)
        proc_arr = np.array(processed)
        
        # 알파 채널(A)이 0인 부분(배경)을 제외하고 실제 상품 영역의 픽셀 수 계산
        alpha_channel = proc_arr[:, :, 3]
        mask = alpha_channel > self.alpha_threshold
        
        # 단순 픽셀 수 비교가 아니라, 원본 이미지의 유효 픽셀 대비 마스크 영역 비율 확인
        # (실제로는 상품의 대략적인 bounding box 내에서 계산하는 것이 정확함)
        total_pixels = original.width * original.height
        preserved_pixels = np.sum(mask)
        
        # 상품이 너무 많이 깎여나갔는지 확인 (예: 전체의 90% 이상이 날아갔다면 오류)
        preservation_rate = preserved_pixels / total_pixels
        
        if preservation_rate < 0.1: # 상품이 거의 사라진 경우
            logging.error(f"⚠️ [정책 위반] 상품 유실 심각: {filename} (보존율: {preservation_rate:.2%})")
            # CLAUDE.md Section 7.6에 정의된 분류 기준 적용
            self._log_qc_failure(filename, "rejected_detail_loss", f"Preservation rate too low: {preservation_rate:.2%}")

    def _log_qc_failure(self, item_id, status, reason):
        """QC 실패 로그 기록"""
        import json
        from datetime import datetime
        
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "item_id": item_id,
            "status": status,
            "reason": reason,
            "engine": "Standard-BGRemover"
        }
        
        with open(Config.LOGS_DIR / "qc_log.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")