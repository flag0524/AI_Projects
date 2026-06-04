# 클라우드 GPU 배포 — Tier 1 (IDM-VTON) 사진급 가상 피팅

CPU/저VRAM 노트북에서는 디퓨전 기반 피팅이 불가능하다(2GB GPU에서 적재 세그폴트 확인됨).
**진짜 자연스러운 착용 핏**(옷이 몸을 감싸고 주름·그림자가 생성되는)을 얻으려면 **GPU VRAM 12GB+** 환경에서 **Tier 1: IDM-VTON**을 사용해야 한다. 이 폴더는 그 배포를 위한 패키지다.

---

## 1. 무엇이 다른가 (Tier 1 vs Tier 3)

| | Tier 3 (현 노트북/CPU) | Tier 1 (클라우드 GPU) |
|---|---|---|
| 방식 | 평면 의류 사진을 부위에 스케일·합성 | 디퓨전 생성 — 옷이 체형을 **감싸고** 주름·그림자 생성 |
| 의류 재현 | 원본 사진 그대로 배치 | 의류 디테일을 학습적으로 **입힘** |
| 결과 | 미리보기 수준 | **사진급** |
| 필요 | 없음 | **GPU VRAM 12GB+** (CPU offload 시 ~8GB) |

---

## 2. 권장 인스턴스

| 제공자 | 추천 GPU | 대략 비용 |
|---|---|---|
| **RunPod** (권장) | RTX 3090/4090 (24GB), A5000(24GB) | ~$0.3–0.5/시간 |
| Vast.ai | RTX 3090/4090 | ~$0.2–0.4/시간 |
| Lambda / Paperspace | A10(24GB), A100 | 변동 |
| Google Colab Pro | T4(16GB)/L4/A100 | 구독 |

> 최소 16GB(T4)에서도 동작 가능하나, **24GB(3090/4090)** 가 여유롭고 빠르다.

---

## 3. 배포 방법 A — RunPod/Vast (CUDA 템플릿, 1클릭 스크립트)

GPU 인스턴스(예: RunPod "PyTorch 2.x / CUDA 12.1" 템플릿)를 띄운 뒤:

```bash
# 1) 코드 업로드 (git 또는 scp). 예: git
git clone <이 저장소 URL> mannequin-fit
cd mannequin-fit

# 2) 1클릭 셋업 (의존성 + 모델 다운로드 + 서버 기동)
bash deploy/cloud-gpu/setup_gpu.sh
```

스크립트가 자동으로:
1. 시스템 라이브러리 설치
2. `backend/.venv` + CUDA torch + requirements 설치
3. `deploy/cloud-gpu/.env.gpu` → `backend/.env` 적용 (`DEVICE=cuda`, `ENGINE_TIER=1`)
4. IDM-VTON 모델 사전 다운로드
5. `uvicorn` 기동 (포트 8000)

확인:
```bash
curl http://localhost:8000/health
# engine_tier:1, hardware.cuda:true 이면 정상
```
RunPod이면 8000 포트를 **HTTP 노출(Expose)** 설정 → 발급된 URL의 `/docs` 로 접속.

---

## 4. 배포 방법 B — Docker Compose (GPU 서버 + NVIDIA Toolkit)

자체 GPU 서버(도커 + NVIDIA Container Toolkit 설치됨)라면 루트의 `docker-compose.yml`이 이미 GPU 예약을 포함한다:

```bash
# backend/.env 를 GPU용으로
cp deploy/cloud-gpu/.env.gpu backend/.env

docker compose up --build
# frontend: http://<서버IP>:3000  /  backend: :8000
```

`docker-compose.yml`의 `backend`·`worker`는 `DEVICE=cuda` + `deploy.resources...devices: [gpu]` 로 GPU를 사용한다.

---

## 5. 배포 방법 C — Google Colab (간단 체험)

Colab(런타임 → GPU)에서:

```python
!git clone <저장소 URL> mf && cd mf/backend && \
 pip install -q -r requirements.txt && \
 pip install -q pip-system-certs
import os; os.environ["DEVICE"]="cuda"; os.environ["ENGINE_TIER"]="1"
# 백엔드 실행 + ngrok/cloudflared 로 외부 노출하거나, 노트북 내에서 직접 파이프라인 호출
```
> Colab은 세션이 끊기면 초기화되므로 상시 서비스보다 **체험·검증용**에 적합.

---

## 6. 프론트엔드 연결

- 같은 인스턴스에서 `frontend/`를 빌드/서빙하면 `vite.config.js` 프록시(`/api → :8000`)로 동작.
- 분리 배포 시: 프론트의 API base를 백엔드 URL로 지정하고 CORS는 백엔드가 이미 `*` 허용.

---

## 7. 검증 (end-to-end)

```bash
curl -s -X POST http://localhost:8000/api/v1/tryon \
  -F mannequin_image=@mannequin.jpg \
  -F garment_image=@garment.jpg \
  -F category=top -F remove_background=true
# → {"job_id": "...", "status":"queued"}
curl -s http://localhost:8000/api/v1/tryon/<job_id>
# status: succeeded, results[].image_url 확인
```
첫 추론은 모델 워밍업으로 느릴 수 있고(수십 초), 이후 GPU에서 P95 ≤ 15초.

---

## 8. 중요 참고 (IDM-VTON 통합)

- `backend/pipeline/tryon_model.py`는 `AutoPipelineForInpainting` + 커스텀 파이프라인(`pipeline_stable_diffusion_xl_tryon`)으로 IDM-VTON을 로드한다. **모델 로드 실패 시 자동으로 stub(경량 합성)로 폴백**하므로 서버가 죽지는 않는다 — `/health`·로그로 실제 Tier 1 적재 여부를 반드시 확인할 것.
- 만약 커스텀 파이프라인 로드가 환경에서 실패하면, **공식 IDM-VTON** 구현을 따르도록 조정이 필요할 수 있다:
  - 공식 레포: `https://github.com/yisol/IDM-VTON`
  - HF 모델: `https://huggingface.co/yisol/IDM-VTON`
  - 공식 추론 코드는 garment-UNet + image encoder를 직접 구성한다. 필요 시 `tryon_model.py._load_pipeline()`를 공식 코드 기준으로 교체한다.
- **라이선스**: IDM-VTON은 연구용 라이선스다. 상업적 사용 전 라이선스를 확인하고, 필요 시 `finetune/`의 LoRA 파이프라인으로 상업용 가능 베이스 모델에 학습해 대체한다.

---

## 9. 비용 절약 팁

- 작업이 없을 때 인스턴스를 **정지/종료**(시간당 과금).
- 모델 가중치는 **네트워크 볼륨**에 캐시 → 재기동 시 재다운로드 방지(`storage/models` 마운트).
- 배치 추론·`num_candidates` 조절로 GPU 활용률 ↑.

---

## 10. 노트북(현 환경)으로 되돌리기

GPU 작업이 끝나고 로컬 CPU로 돌아오면 `backend/.env`를 원복:
```
DEVICE=cpu
ENGINE_TIER=3
```
