"""higgsfield_provider 단위 테스트 — MCP JSON-RPC 격리 계층 모킹."""
import json
import contextlib

import pytest
from PIL import Image

from backend.pipeline import higgsfield_provider as hgf
from backend.pipeline.generative_provider import GenerativeBillingError


@pytest.fixture
def with_key(monkeypatch):
    monkeypatch.setattr(hgf, "API_KEY", "test-key")


@pytest.fixture
def fake_client(monkeypatch):
    """_client()를 더미 컨텍스트 매니저로 교체 (실제 httpx 호출 차단)."""
    @contextlib.contextmanager
    def _dummy():
        yield object()
    monkeypatch.setattr(hgf, "_client", _dummy)


def _sse(payload: dict) -> str:
    return f"event: message\ndata: {json.dumps(payload)}\n\n"


class FakeResp:
    def __init__(self, text="", status=200):
        self.text = text
        self.status_code = status

    def raise_for_status(self):
        pass


class FakeClient:
    """post 응답을 큐로 제공하는 더미 streamable-HTTP 클라이언트."""
    def __init__(self, responses):
        self._resp = list(responses)

    def post(self, *a, **k):
        return self._resp.pop(0)


# ── is_available ──────────────────────────────────────────────
def test_is_available_with_key(monkeypatch):
    monkeypatch.setattr(hgf, "API_KEY", "k")
    assert hgf.is_available() is True


def test_is_available_no_key(monkeypatch):
    monkeypatch.setattr(hgf, "API_KEY", "")
    assert hgf.is_available() is False


# ── 카테고리 매핑 ─────────────────────────────────────────────
@pytest.mark.parametrize("gtype,expected", [
    ("top", "upper_body"),
    ("bottom", "lower_body"),
    ("dress", "dresses"),
    ("accessory", "upper_body"),
    ("unknown", "upper_body"),
])
def test_to_category(gtype, expected):
    assert hgf.to_category(gtype) == expected


# ── _parse_sse: SSE / plain JSON ──────────────────────────────
def test_parse_sse_event_stream():
    assert hgf._parse_sse(_sse({"result": {"ok": 1}})) == {"result": {"ok": 1}}


def test_parse_sse_plain_json():
    assert hgf._parse_sse('{"a": 2}') == {"a": 2}


def test_parse_sse_empty():
    assert hgf._parse_sse("") == {}


# ── _tool: 성공 / isError / 크레딧 부족 ───────────────────────
def test_tool_returns_structured_content():
    c = FakeClient([FakeResp(_sse({"result": {"structuredContent": {"v": 9}}}))])
    assert hgf._tool(c, "x", {}, 1) == {"v": 9}


def test_tool_error_raises_unavailable():
    c = FakeClient([FakeResp(_sse({"result": {"isError": True,
                                              "structuredContent": {"error": "boom"}}}))])
    with pytest.raises(hgf.HiggsfieldUnavailable):
        hgf._tool(c, "x", {}, 1)


def test_tool_credit_error_raises_billing():
    c = FakeClient([FakeResp(_sse({"result": {
        "isError": True,
        "structuredContent": {"recovery_tool": "show_plans_and_credits"},
    }}))])
    with pytest.raises(GenerativeBillingError):
        hgf._tool(c, "generate_image", {}, 1)


# ── _generate: job_id 파싱 ────────────────────────────────────
def test_generate_parses_job_id(monkeypatch):
    monkeypatch.setattr(hgf, "_tool", lambda *a, **k: {"results": [{"id": "job-9", "status": "pending"}]})
    assert hgf._generate(object(), ["m"], "p") == "job-9"


def test_generate_missing_id_raises(monkeypatch):
    monkeypatch.setattr(hgf, "_tool", lambda *a, **k: {"results": []})
    with pytest.raises(hgf.HiggsfieldUnavailable):
        hgf._generate(object(), ["m"], "p")


# ── _poll: completed / failed / timeout ───────────────────────
def test_poll_completed_returns_url(monkeypatch):
    monkeypatch.setattr(hgf.time, "sleep", lambda s: None)
    seq = [
        {"results": [{"status": "in_progress"}]},
        {"results": [{"status": "completed", "results": {"rawUrl": "https://x/r.png"}}]},
    ]
    monkeypatch.setattr(hgf, "_tool", lambda *a, **k: seq.pop(0))
    assert hgf._poll(object(), "job-1") == "https://x/r.png"


def test_poll_failed_raises(monkeypatch):
    monkeypatch.setattr(hgf.time, "sleep", lambda s: None)
    monkeypatch.setattr(hgf, "_tool", lambda *a, **k: {"results": [{"status": "failed"}]})
    with pytest.raises(hgf.HiggsfieldUnavailable):
        hgf._poll(object(), "job-1")


def test_poll_timeout_raises(monkeypatch):
    monkeypatch.setattr(hgf.time, "sleep", lambda s: None)
    monkeypatch.setattr(hgf, "POLL_MAX_ATTEMPTS", 3)
    monkeypatch.setattr(hgf, "_tool", lambda *a, **k: {"results": [{"status": "queued"}]})
    with pytest.raises(hgf.HiggsfieldUnavailable):
        hgf._poll(object(), "job-1")


# ── _build_prompt ─────────────────────────────────────────────
def test_build_prompt_includes_all_garments():
    p = hgf._build_prompt([("top", "upper_body"), ("shorts", "lower_body")])
    assert "the exact top on the upper_body" in p
    assert "the exact shorts on the lower_body" in p


# ── generate_tryon_multi happy (플로우 단계 모킹) ──────────────
def _patch_flow(monkeypatch, **over):
    monkeypatch.setattr(hgf, "_session", over.get("session", lambda c: None))
    monkeypatch.setattr(hgf, "_upload", over.get("upload", lambda c, imgs: ["m", "g0"]))
    monkeypatch.setattr(hgf, "_generate", over.get("generate", lambda c, ids, p: "job-1"))
    monkeypatch.setattr(hgf, "_poll", over.get("poll", lambda c, j: "https://x/r.png"))
    monkeypatch.setattr(hgf, "_download", over.get("download", lambda u: Image.new("RGB", (8, 8))))


def test_generate_tryon_multi_happy(monkeypatch, with_key, fake_client, img):
    _patch_flow(monkeypatch)
    out = hgf.generate_tryon_multi(
        [(img, "top", "upper_body"), (img, "shorts", "lower_body")], img
    )
    assert isinstance(out, Image.Image)
    assert out.mode == "RGB"


def test_generate_tryon_single_wrapper(monkeypatch, with_key, fake_client, img):
    captured = {}

    def _upload(c, images):
        captured["n"] = len(images)   # model + 1 garment = 2
        return ["m", "g0"]
    _patch_flow(monkeypatch, upload=_upload)
    out = hgf.generate_tryon(img, img, "a top", "upper_body")
    assert isinstance(out, Image.Image)
    assert captured["n"] == 2


def test_generate_tryon_multi_uploads_model_plus_garments(monkeypatch, with_key, fake_client, img):
    captured = {}

    def _upload(c, images):
        captured["n"] = len(images)
        return ["m"] + [f"g{i}" for i in range(len(images) - 1)]
    _patch_flow(monkeypatch, upload=_upload)
    hgf.generate_tryon_multi([(img, "top", "upper_body"), (img, "shorts", "lower_body")], img)
    assert captured["n"] == 3          # model + 2 garments


def test_generate_tryon_no_key(monkeypatch, img):
    monkeypatch.setattr(hgf, "API_KEY", "")
    with pytest.raises(hgf.HiggsfieldUnavailable):
        hgf.generate_tryon(img, img)


def test_generate_tryon_multi_empty_raises(with_key, img):
    with pytest.raises(hgf.HiggsfieldUnavailable):
        hgf.generate_tryon_multi([], img)


def test_generate_tryon_billing_propagates(monkeypatch, with_key, fake_client, img):
    def _bill(c, images):
        raise GenerativeBillingError("no credit")
    _patch_flow(monkeypatch, upload=_bill)
    with pytest.raises(GenerativeBillingError):
        hgf.generate_tryon(img, img)


def test_generate_tryon_unavailable_propagates(monkeypatch, with_key, fake_client, img):
    def _boom(c, images):
        raise hgf.HiggsfieldUnavailable("upload down")
    _patch_flow(monkeypatch, upload=_boom)
    with pytest.raises(hgf.HiggsfieldUnavailable):
        hgf.generate_tryon(img, img)
