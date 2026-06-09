"""
Leffa baseline fidelity 테스트 (Higgsfield 복구 전 임시 baseline).

input/real/{top,bottom,mannequin}.png 를 기존 hf_provider(Leffa)로 돌려
모델 착용 컷을 생성한다. Higgsfield 복구 시 동일 입력으로 나란히 비교.

케이스:
  1. top 단일      → 착용 컷
  2. top→bottom 순차 → drift 케이스 (eng-review 이슈 2)
"""
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# .env 로드
for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())

os.environ["GEN_BACKEND"] = "hf"

from PIL import Image
from backend.pipeline import hf_provider as hf
from backend.pipeline.laongen_engine import generate_model_shot

IN = ROOT / "input" / "real"
OUT = ROOT / "input" / "real" / "baseline_out"
OUT.mkdir(exist_ok=True)

print("HF available:", hf.is_available(), "| space:", hf.HF_SPACE)

top = Image.open(IN / "top.png")
bottom = Image.open(IN / "bottom.png")

# 케이스 1: top 단일
t0 = time.time()
img1, method1 = generate_model_shot([(top, "top")])
img1.save(OUT / "case1_top_only.png")
print(f"[case1] method={method1} {int((time.time()-t0)*1000)}ms -> case1_top_only.png")

# 케이스 2: top -> bottom 순차 (drift 확인)
t0 = time.time()
img2, method2 = generate_model_shot([(top, "top"), (bottom, "bottom")])
img2.save(OUT / "case2_top_bottom.png")
print(f"[case2] method={method2} {int((time.time()-t0)*1000)}ms -> case2_top_bottom.png")

print("DONE")
