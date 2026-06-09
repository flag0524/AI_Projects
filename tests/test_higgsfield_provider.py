"""higgsfield_provider 단위 테스트 — REST 격리 계층 모킹."""
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


# ── generate_tryon happy path ─────────────────────────────────
def test_generate_tryon_happy(monkeypatch, with_key, fake_client, img):
    monkeypatch.setattr(hgf, "_submit_job", lambda *a, **k: "job-123")
    monkeypatch.setattr(hgf, "_poll_job", lambda *a, **k: "ref://result")
    monkeypatch.setattr(hgf, "_download", lambda *a, **k: Image.new("RGB", (32, 32), (1, 2, 3)))

    out = hgf.generate_tryon(img, img, "a top", "upper_body")
    assert isinstance(out, Image.Image)
    assert out.mode == "RGB"


# ── generate_tryon_multi (다중 의류 단일-호출) ────────────────────
def test_generate_tryon_multi_happy(monkeypatch, with_key, fake_client, img):
    monkeypatch.setattr(hgf, "_submit_job", lambda *a, **k: "job-1")
    monkeypatch.setattr(hgf, "_poll_job", lambda *a, **k: "ref://r")
    monkeypatch.setattr(hgf, "_download", lambda *a, **k: Image.new("RGB", (8, 8)))

    out = hgf.generate_tryon_multi(
        [(img, "top", "upper_body"), (img, "shorts", "lower_body")], img
    )
    assert isinstance(out, Image.Image)
    assert out.mode == "RGB"


def test_generate_tryon_multi_empty_raises(with_key, img):
    with pytest.raises(hgf.HiggsfieldUnavailable):
        hgf.generate_tryon_multi([], img)


# ── 키 없음 → Unavailable ─────────────────────────────────────
def test_generate_tryon_no_key(monkeypatch, img):
    monkeypatch.setattr(hgf, "API_KEY", "")
    with pytest.raises(hgf.HiggsfieldUnavailable):
        hgf.generate_tryon(img, img)


# ── job 실패 → Unavailable ────────────────────────────────────
def test_generate_tryon_job_failed(monkeypatch, with_key, fake_client, img):
    def _boom(*a, **k):
        raise hgf.HiggsfieldUnavailable("job failed")
    monkeypatch.setattr(hgf, "_submit_job", lambda *a, **k: "job-1")
    monkeypatch.setattr(hgf, "_poll_job", _boom)
    with pytest.raises(hgf.HiggsfieldUnavailable):
        hgf.generate_tryon(img, img)


# ── poll 타임아웃 → Unavailable ───────────────────────────────
def test_generate_tryon_poll_timeout(monkeypatch, with_key, fake_client, img):
    def _timeout(*a, **k):
        raise hgf.HiggsfieldUnavailable("poll timeout")
    monkeypatch.setattr(hgf, "_submit_job", lambda *a, **k: "job-1")
    monkeypatch.setattr(hgf, "_poll_job", _timeout)
    with pytest.raises(hgf.HiggsfieldUnavailable):
        hgf.generate_tryon(img, img)


# ── 402 크레딧 부족 → BillingError (기존 402 경로 재사용) ──────
def test_generate_tryon_billing(monkeypatch, with_key, fake_client, img):
    class FakeResp:
        status_code = 402
        text = "insufficient credit"

    def _402(*a, **k):
        e = Exception("payment required")
        e.response = FakeResp()
        raise e

    monkeypatch.setattr(hgf, "_submit_job", _402)
    with pytest.raises(GenerativeBillingError):
        hgf.generate_tryon(img, img)


# ── 일반 네트워크 오류 → Unavailable ──────────────────────────
def test_generate_tryon_network_error(monkeypatch, with_key, fake_client, img):
    def _err(*a, **k):
        raise RuntimeError("connection reset")
    monkeypatch.setattr(hgf, "_submit_job", _err)
    with pytest.raises(hgf.HiggsfieldUnavailable):
        hgf.generate_tryon(img, img)


# ── REST 격리 계층 (httpx 모킹) ───────────────────────────────
class FakeResp:
    def __init__(self, json_data=None, content=b"", status=200):
        self._json = json_data or {}
        self.content = content
        self.status_code = status

    def raise_for_status(self):
        pass

    def json(self):
        return self._json


class FakeClient:
    """post/get 응답을 큐로 제공하는 더미 httpx 클라이언트."""
    def __init__(self, post_resp=None, get_resps=None):
        self._post = post_resp
        self._gets = list(get_resps or [])

    def post(self, *a, **k):
        return self._post

    def get(self, *a, **k):
        return self._gets.pop(0)


def test_submit_job_parses_id(img):
    c = FakeClient(post_resp=FakeResp({"id": "job-xyz"}))
    assert hgf._submit_job(c, [(img, "a top", "upper_body")], img) == "job-xyz"


def test_submit_job_missing_id_raises(img):
    c = FakeClient(post_resp=FakeResp({"foo": "bar"}))
    with pytest.raises(hgf.HiggsfieldUnavailable):
        hgf._submit_job(c, [(img, "a top", "upper_body")], img)


def test_submit_job_multi_input_images(img):
    """다중 의류: input_images=[model, *garments], 프롬프트에 각 의류 반영."""
    captured = {}

    class CapClient:
        def post(self, path, json):
            captured["json"] = json
            return FakeResp({"id": "j"})

    hgf._submit_job(
        CapClient(),
        [(img, "top", "upper_body"), (img, "shorts", "lower_body")],
        img,
    )
    assert len(captured["json"]["input_images"]) == 3   # model + 2 garments
    assert "the exact top on the upper_body" in captured["json"]["prompt"]
    assert "the exact shorts on the lower_body" in captured["json"]["prompt"]


def test_poll_completed_returns_url(monkeypatch):
    monkeypatch.setattr(hgf.time, "sleep", lambda s: None)
    c = FakeClient(get_resps=[
        FakeResp({"status": "Queued"}),
        FakeResp({"status": "InProgress"}),
        FakeResp({"status": "Completed", "images": [{"url": "https://x/r.png"}]}),
    ])
    assert hgf._poll_job(c, "job-1") == "https://x/r.png"


def test_poll_failed_raises(monkeypatch):
    monkeypatch.setattr(hgf.time, "sleep", lambda s: None)
    c = FakeClient(get_resps=[FakeResp({"status": "Failed"})])
    with pytest.raises(hgf.HiggsfieldUnavailable):
        hgf._poll_job(c, "job-1")


def test_poll_timeout_raises(monkeypatch):
    monkeypatch.setattr(hgf.time, "sleep", lambda s: None)
    monkeypatch.setattr(hgf, "POLL_MAX_ATTEMPTS", 3)
    c = FakeClient(get_resps=[FakeResp({"status": "Queued"})] * 3)
    with pytest.raises(hgf.HiggsfieldUnavailable):
        hgf._poll_job(c, "job-1")


def test_download_returns_image():
    import io as _io
    buf = _io.BytesIO()
    Image.new("RGB", (16, 16), (5, 6, 7)).save(buf, "PNG")
    c = FakeClient(get_resps=[FakeResp(content=buf.getvalue())])
    out = hgf._download(c, "https://x/r.png")
    assert isinstance(out, Image.Image)
