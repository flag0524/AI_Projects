# Higgsfield 프로바이더 런북

설계: [2026-06-08-higgsfield-provider-design.md](superpowers/specs/2026-06-08-higgsfield-provider-design.md)

## 개요

Higgsfield는 기존 Leffa/IDM-VTON 위에 추가된 **세 번째 생성형 프로바이더**다
(교체 아님, 확장). 단일 의류 → 모델 착용 컷을 생성한다.

## 설정

`.env` (`.env.example` 참고):

```
GEN_BACKEND=higgsfield
HIGGSFIELD_API_KEY=<cloud.higgsfield.ai 에서 발급>
HIGGSFIELD_API_BASE=https://api.higgsfield.ai
HIGGSFIELD_TRYON_MODEL=nano-banana-pro
```

키가 없으면 `is_available()==False` → HF/Replicate/절차적으로 자동 폴백.

## 실행 (중요: 단일 워커)

비동기 job 상태는 **in-memory dict**에 저장된다. 멀티워커/재시작 시 job 조회가
조용히 실패하므로 **반드시 단일 워커로 실행**:

```
uvicorn backend.main:app --workers 1
```

(멀티워커 내구성 = SQLite/Redis 영속화는 NOT in scope. 설계 문서 참조.)

## API (비동기)

```
POST /api/v1/generate              → 202 {job_id, status:"processing"}
GET  /api/v1/generate/result/{id}  → processing | completed | 402(크레딧) | 404 | 500
GET  /api/v1/generate/status       → 백엔드 가용성 + active_backend
```

생성은 30~50초+ 소요(실측). POST는 즉시 job_id 반환, GET으로 폴링.

## 캐스케이드

`GEN_BACKEND=higgsfield`(또는 `auto`): higgsfield → hf → replicate → 절차적.
어느 백엔드가 Unavailable이면 다음으로 폴백. 크레딧 부족(402)은 폴백하지 않고
전파.

## 미해결 (라이브 키 필요)

`higgsfield_provider.py`의 `_submit_job` payload 2가지는 **가정**이며
라이브 키로 검증 필요:
- try-on 모델 id (`HIGGSFIELD_TRYON_MODEL`)
- 의류+모델 2장 입력 방식 (현재 `input_images:[model, garment]`)

전송 계약(POST /v1/generations, Bearer, GET 폴링, images[0].url)은 공개 문서로
확정됨.

## fidelity 참고

Leffa baseline (`scripts/fidelity_baseline.py`, `input/real/baseline_out/`):
- 단일 의류: fidelity 양호
- 순차 2벌: drift 실패 → **단일 의류만 지원**

Higgsfield 복구 시 Nano Banana Pro 단일 의류를 baseline과 비교 예정.

## 테스트

```
python -m pytest tests/
```
