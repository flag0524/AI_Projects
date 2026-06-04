#!/usr/bin/env bash
# ============================================================
# 클라우드 GPU 1클릭 셋업 — AI 마네킹 핏 (Tier 1: IDM-VTON)
# 대상: Ubuntu 22.04 + NVIDIA GPU (VRAM 12GB+) + CUDA 드라이버
#       (RunPod / Vast.ai / Lambda / 자체 GPU 서버)
# 사용:  bash deploy/cloud-gpu/setup_gpu.sh
# ============================================================
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
echo "▶ 프로젝트 루트: $ROOT"

# ── 0) GPU 확인 ─────────────────────────────────────────────
if ! command -v nvidia-smi >/dev/null 2>&1; then
  echo "✗ nvidia-smi 없음 — GPU/드라이버가 있는 인스턴스에서 실행하세요." >&2
  exit 1
fi
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
VRAM_MB=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits | head -1 | tr -d ' ')
if [ "${VRAM_MB:-0}" -lt 11000 ]; then
  echo "⚠ VRAM ${VRAM_MB}MB — IDM-VTON(Tier1)은 12GB+ 권장. CPU offload로도 8GB 필요."
fi

# ── 1) 시스템 패키지 ────────────────────────────────────────
echo "▶ 시스템 패키지 설치..."
sudo apt-get update -y
sudo apt-get install -y python3-venv python3-pip git \
  libglib2.0-0 libsm6 libxext6 libxrender-dev libgl1-mesa-glx

# ── 2) 백엔드 가상환경 + 의존성 ─────────────────────────────
cd "$ROOT/backend"
python3 -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
pip install --upgrade pip
# CUDA 12.1 빌드 torch (베이스 이미지에 없을 때만)
pip install torch==2.3.0 torchvision==0.18.0 --index-url https://download.pytorch.org/whl/cu121
pip install -r requirements.txt
# 사내망/SSL 인증서 이슈 대비 (선택)
pip install pip-system-certs || true
# 메모리 최적화 (있으면 가속)
pip install xformers==0.0.26.post1 || echo "xformers 설치 생략(선택)"

# ── 3) GPU 환경설정 적용 ────────────────────────────────────
cp "$ROOT/deploy/cloud-gpu/.env.gpu" "$ROOT/backend/.env"
echo "▶ backend/.env 를 GPU(Tier1)용으로 설정함"

# ── 4) IDM-VTON 모델 사전 다운로드 (첫 추론 지연 방지) ──────
echo "▶ IDM-VTON 모델 다운로드 (수 GB, 시간 소요)..."
python - <<'PY'
from huggingface_hub import snapshot_download
import os
mid = os.environ.get("IDM_VTON_MODEL_ID", "yisol/IDM-VTON")
p = snapshot_download(repo_id=mid, local_dir="storage/models/IDM-VTON")
print("모델 위치:", p)
PY

# ── 5) 서버 기동 ────────────────────────────────────────────
echo "▶ 백엔드 기동 (포트 8000)"
echo "   GPU 단일이면 Redis/Celery 없이 인프로세스 모드로 동작합니다."
nohup uvicorn main:app --host 0.0.0.0 --port 8000 > uvicorn.log 2>&1 &
sleep 8
echo "── /health ──"
curl -s http://localhost:8000/health || true
echo
echo "✅ 완료. 확인:"
echo "   - API:   http://<인스턴스IP>:8000/docs"
echo "   - health 의 engine_tier 가 1, mode 가 inprocess/celery 인지 확인"
echo "   - 프론트는 frontend/ 에서 'VITE_API_BASE=http://<IP>:8000 npm run dev' 또는 nginx 배포"
