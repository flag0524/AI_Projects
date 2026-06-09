"""laongen_engine 캐스케이드 폴백 테스트.

핵심: higgsfield → hf → replicate → 절차적 순서, 그리고
[CRITICAL 회귀] higgsfield 실패 시 기존 hf 경로가 그대로 동작하는지.
"""
import pytest
from PIL import Image

from backend.pipeline import laongen_engine as eng
from backend.pipeline import higgsfield_provider as hgf
from backend.pipeline import hf_provider as hf
from backend.pipeline import generative_provider as gen


@pytest.fixture
def garments(img):
    return [(img, "top")]


@pytest.fixture(autouse=True)
def backend_auto(monkeypatch):
    """GEN_BACKEND=auto → higgsfield→hf→replicate 체인."""
    monkeypatch.setenv("GEN_BACKEND", "auto")


def _avail(monkeypatch, hgf_ok, hf_ok, rep_ok):
    monkeypatch.setattr(hgf, "is_available", lambda: hgf_ok)
    monkeypatch.setattr(hf, "is_available", lambda: hf_ok)
    monkeypatch.setattr(gen, "is_available", lambda: rep_ok)


def test_higgsfield_success(monkeypatch, garments):
    _avail(monkeypatch, True, True, True)
    monkeypatch.setattr(hgf, "generate_tryon_multi", lambda *a, **k: Image.new("RGB", (8, 8)))
    _, method = eng.generate_model_shot(garments)
    assert method == "higgsfield"


def test_higgsfield_fail_falls_to_hf(monkeypatch, garments):
    """[CRITICAL 회귀] higgsfield 실패 → HF 폴백. 기존 동작 보존 증명."""
    _avail(monkeypatch, True, True, True)

    def _boom(*a, **k):
        raise hgf.HiggsfieldUnavailable("down")
    monkeypatch.setattr(hgf, "generate_tryon_multi", _boom)
    monkeypatch.setattr(hf, "generate_tryon", lambda **k: Image.new("RGB", (8, 8)))

    _, method = eng.generate_model_shot(garments)
    assert method == "hf"


def test_hf_fail_falls_to_replicate(monkeypatch, garments):
    _avail(monkeypatch, True, True, True)
    monkeypatch.setattr(hgf, "generate_tryon_multi", lambda *a, **k: (_ for _ in ()).throw(hgf.HiggsfieldUnavailable()))
    monkeypatch.setattr(hf, "generate_tryon", lambda **k: (_ for _ in ()).throw(hf.HFUnavailable()))
    monkeypatch.setattr(gen, "generate_tryon", lambda **k: Image.new("RGB", (8, 8)))
    _, method = eng.generate_model_shot(garments)
    assert method == "generative"


def test_all_fail_falls_to_procedural(monkeypatch, garments, img):
    """전 백엔드 불가 → 절차적 폴백."""
    _avail(monkeypatch, False, False, False)
    # 마네킹 없음 → 첫 의류 반환 (procedural)
    _, method = eng.generate_model_shot(garments, mannequin_img=None)
    assert method == "procedural"


def test_billing_error_not_swallowed(monkeypatch, garments):
    """크레딧 부족은 폴백하지 않고 전파 (api가 402 처리)."""
    _avail(monkeypatch, True, True, True)

    def _bill(*a, **k):
        raise gen.GenerativeBillingError("no credit")
    monkeypatch.setattr(hgf, "generate_tryon_multi", _bill)
    with pytest.raises(gen.GenerativeBillingError):
        eng.generate_model_shot(garments)


def test_higgsfield_multi_single_call(monkeypatch, img):
    """다중 의류 단일-호출: 2벌이어도 generate_tryon_multi 1회, 2벌 모두 전달."""
    _avail(monkeypatch, True, False, False)
    calls = []

    def _cap(garments, model, subject="model"):
        calls.append(garments)
        return Image.new("RGB", (8, 8))
    monkeypatch.setattr(hgf, "generate_tryon_multi", _cap)
    eng.generate_model_shot([(img, "top"), (img, "bottom")])
    assert len(calls) == 1            # 단일 호출
    assert len(calls[0]) == 2         # 2벌 모두 한 호출에 전달


def test_subject_mannequin_forwarded_to_higgsfield(monkeypatch, img):
    """마네킹 모드: subject='mannequin'이 higgsfield 러너까지 전달된다."""
    _avail(monkeypatch, True, False, False)
    seen = {}

    def _cap(garments, model, subject="model"):
        seen["subject"] = subject
        return Image.new("RGB", (8, 8))
    monkeypatch.setattr(hgf, "generate_tryon_multi", _cap)
    eng.generate_model_shot([(img, "top")], subject="mannequin")
    assert seen["subject"] == "mannequin"


def test_backend_hf_does_not_use_higgsfield(monkeypatch, garments):
    """GEN_BACKEND=hf → higgsfield 건너뜀 (기존 동작 보존)."""
    monkeypatch.setenv("GEN_BACKEND", "hf")
    _avail(monkeypatch, True, True, True)
    monkeypatch.setattr(hgf, "generate_tryon_multi",
                        lambda *a, **k: pytest.fail("hf 모드에서 higgsfield 호출되면 안 됨"))
    monkeypatch.setattr(hf, "generate_tryon", lambda **k: Image.new("RGB", (8, 8)))
    _, method = eng.generate_model_shot(garments)
    assert method == "hf"
