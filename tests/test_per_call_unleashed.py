import core_state as cs
from routes import analysis


def test_effective_unleashed_param_overrides_global():
    cs.save_unleashed({"enabled": False})              # global OFF
    assert analysis._effective_unleashed(True) is True   # per-call override wins
    assert analysis._effective_unleashed(False) is False
    assert analysis._effective_unleashed(None) is False  # None ⇒ read global
    assert cs.load_unleashed()["enabled"] is False        # global never mutated


def test_effective_unleashed_reads_global_when_none():
    cs.save_unleashed({"enabled": True})
    assert analysis._effective_unleashed(None) is True
    cs.save_unleashed({"enabled": False})                 # restore
