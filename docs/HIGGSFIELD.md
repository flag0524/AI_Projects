# Higgsfield 프로바이더 런북

설계: [2026-06-08-higgsfield-provider-design.md](superpowers/specs/2026-06-08-higgsfield-provider-design.md)

## 개요

Higgsfield는 기존 Leffa/IDM-VTON 위에 추가된 **세 번째 생성형 프로바이더**다
(교체 아님, 확장). 모델 + 의류(다중 가능) → 착용 컷을 **단일-호출 다중입력**으로
생성한다 (순차 체이닝 drift 우회, 설계 문서 Open Q1).

## 전송 채널 (MCP)

프로덕션 REST 호스트(api.higgsfield.ai)가 522로 미동작하여, 전송은 **MCP 서버**
(`https://mcp.higgsfield.ai/mcp`, JSON-RPC over streamable HTTP, Bearer 인증)를
직접 호출한다. 흐름: `initialize` → `media_upload`(presigned)→PUT→`media_confirm`
→ `generate_image`(medias) → `job_display` 폴링 → 결과 URL 다운로드.
(라이브 검증 스크립트: `scripts/hgf_mcp_probe.py`)

## 설정

`.env` (`.env.example` 참고):

```
GEN_BACKEND=higgsfield
HIGGSFIELD_API_KEY=<동작하는 Higgsfield 계정 MCP Bearer 토큰>
HIGGSFIELD_MCP_URL=https://mcp.higgsfield.ai/mcp
HIGGSFIELD_TRYON_MODEL=nano_banana_pro
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

## 미해결 (동작 토큰 필요)

MCP 전송 계약/호출 형태는 `scripts/hgf_mcp_probe.py`로 확정됐고 프로바이더는
이를 구현 + mock 테스트로 고정. 단 **라이브 end-to-end 검증은 동작하는 계정
토큰 확보 후로 보류**:
- 제공된 `daea0198…` 토큰은 MCP 핸드셰이크만 통과하고 balance/media_upload/
  generate/show_generations **전부 실패**(계정 컨텍스트 없음, 2026-06-09).
- 동작 토큰 확보 시: `HIGGSFIELD_API_KEY` 설정 →
  `python scripts/hgf_mcp_probe.py <token>` 로 1회 실호출 검증 후 활성.

## fidelity 참고

Leffa baseline (`scripts/fidelity_baseline.py`, `input/real/baseline_out/`):
- 단일 의류: fidelity 양호
- 순차 2벌: drift 실패

Higgsfield 단일-호출 다중입력(MCP, nano_banana_pro)은 2026-06-09 풀코디 보존
성공 (`output/fullcoordi_higgsfield.png`) — 순차 drift 우회 확인.

## 테스트

```
python -m pytest tests/
```
