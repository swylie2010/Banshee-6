"""Tests for options_engine.py — The Wheel (Phase 1, pure)."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import options_engine as oe


def test_put_delta_otm_in_range():
    # OTM put, ~0.24 delta (inside the 20-30 band)
    d = oe.put_delta(spot=100, strike=95, dte=40, iv=0.25)
    assert d is not None and -0.25 < d < -0.22


def test_put_delta_far_otm_small():
    d = oe.put_delta(spot=100, strike=80, dte=40, iv=0.25)
    assert d is not None and abs(d) < 0.10


def test_put_delta_guards_bad_input():
    assert oe.put_delta(spot=0, strike=95, dte=40, iv=0.25) is None
    assert oe.put_delta(spot=100, strike=95, dte=0, iv=0.25) is None
    assert oe.put_delta(spot=100, strike=95, dte=40, iv=0) is None


def test_annualized_yield():
    # 1.20 premium on a 95 strike, 40 days -> 1.2*(365/40)/95
    assert oe.annualized_yield(1.20, 95, 40) == pytest_approx(0.1153)


def test_breakeven():
    assert oe.breakeven(95, 1.20) == 93.8


def test_estimate_ivr_percentile():
    assert oe.estimate_ivr(0.25, [0.1, 0.2, 0.3, 0.4]) == 50.0
    assert oe.estimate_ivr(0.05, [0.1, 0.2, 0.3, 0.4]) == 0.0
    assert oe.estimate_ivr(0.5, [0.1, 0.2, 0.3, 0.4]) == 100.0
    assert oe.estimate_ivr(0.25, []) is None
    assert oe.estimate_ivr(None, [0.1, 0.2]) is None


def test_realized_vol_series_shape():
    closes = [100 + (i % 5) for i in range(60)]   # varying series
    rv = oe.realized_vol_series(closes, window=21)
    assert len(rv) == len(closes) - 1 - 21 + 1
    assert all(v >= 0 for v in rv)


def test_put_delta_monotonic():
    # |put delta| grows as strike rises (OTM -> ATM)
    d80 = oe.put_delta(100, 80, 40, 0.25)
    d90 = oe.put_delta(100, 90, 40, 0.25)
    d100 = oe.put_delta(100, 100, 40, 0.25)
    assert abs(d80) < abs(d90) < abs(d100)


def test_realized_vol_constant_series():
    rv = oe.realized_vol_series([100] * 60, window=21)
    assert rv and all(v == 0.0 for v in rv)


# local approx helper (avoids importing pytest.approx at module top for clarity)
def pytest_approx(x, tol=1e-3):
    import pytest
    return pytest.approx(x, abs=tol)


# ── Task 2: best_candidate ───────────────────────────────────────────────────

def _put(strike, dte, iv, mid, oi):
    return {"type": "put", "strike": strike, "dte": dte, "iv": iv,
            "mid": mid, "open_interest": oi, "expiry": "2026-07-17"}

def _univ(sym, spot, contracts, closes=None, failed=False, name=None):
    return {"sym": sym, "name": name or sym, "spot": spot,
            "contracts": contracts, "closes": closes or [100 + (i % 7) for i in range(80)],
            "failed": failed}


def test_best_candidate_picks_passing_put():
    u = _univ("SPY", 100, [_put(95, 40, 0.25, 1.20, 4000)])
    out = oe.best_candidate([u])
    c = out["candidate"]
    assert c is not None
    assert c["underlying"] == "SPY"
    assert c["collateral"] == 9500.0
    assert c["breakeven"] == 93.8
    assert 0.20 <= abs(c["delta"]) <= 0.30
    assert round(c["prob_keep"], 2) == round(1 - abs(c["delta"]), 2)


def test_best_candidate_excludes_failing_guardrails():
    u = _univ("SPY", 100, [
        _put(95, 20, 0.25, 1.20, 4000),    # DTE too short
        _put(80, 40, 0.25, 0.40, 4000),    # delta too small (far OTM)
        _put(95, 40, 0.25, 1.20, 500),     # OI too low
    ])
    out = oe.best_candidate([u])
    assert out["candidate"] is None
    assert out["universe_scanned"] == ["SPY"]


def test_best_candidate_ranks_by_annualized_yield():
    lo = _put(95, 40, 0.25, 1.00, 4000)
    hi = _put(96, 40, 0.27, 1.60, 4000)
    out = oe.best_candidate([_univ("SPY", 100, [lo, hi])])
    assert out["candidate"]["mid"] == 1.60


def test_best_candidate_low_iv_warning():
    # iv=0.25 but realized vol ~1.25 (closes swing 100/108 each bar)
    # -> IVR estimate = 0.0 (iv below all realized readings) -> warning fires
    u = _univ("SPY", 100, [_put(95, 40, 0.25, 1.20, 4000)],
              closes=[100 + 8 * (i % 2) for i in range(80)])  # high realized vol
    out = oe.best_candidate([u])
    assert out["candidate"] is not None
    assert out["low_iv_warning"] is True


def test_best_candidate_partial_failure_noted():
    good = _univ("SPY", 100, [_put(95, 40, 0.25, 1.20, 4000)])
    bad = _univ("QQQ", 0, [], failed=True)
    out = oe.best_candidate([good, bad])
    assert out["candidate"]["underlying"] == "SPY"
    assert out["partial_failures"] == ["QQQ"]
    assert set(out["universe_scanned"]) == {"SPY", "QQQ"}


def test_best_candidate_sizing_against_account():
    u = _univ("SPY", 100, [_put(95, 40, 0.25, 1.20, 4000)])
    out = oe.best_candidate([u], account_size=200000)   # 9500 / 200000 = 4.75%
    s = out["candidate"]["sizing"]
    assert s["within_5pct"] is True
    assert round(s["pct"], 2) == 4.75


def test_best_candidate_translation_fields():
    out = oe.best_candidate([_univ("SPY", 100, [_put(95, 40, 0.25, 1.20, 4000)])])
    t = out["translation"]
    assert "SPY" in t["headline"]
    assert "insurance" in t["plain_english"]
    assert t["prob_keep"] == out["candidate"]["prob_keep"]


def test_best_candidate_ivr_none_plain_text():
    # short close history -> realized_vol_series == [] -> ivr_estimate None
    out = oe.best_candidate([_univ("SPY", 100, [_put(95, 40, 0.25, 1.20, 4000)], closes=[100, 101])])
    assert out["candidate"]["ivr_estimate"] is None
    assert out["low_iv_warning"] is False
    ivr_row = next(g for g in out["guardrails"] if g["key"] == "ivr")
    assert ivr_row["passed"] is True
    assert ivr_row["value"] == "n/a"
    assert "thin" not in ivr_row["plain"].lower()


def test_best_candidate_oi_boundary_excludes_1000():
    # OI must EXCEED 1000 (strict) — exactly 1000 is rejected
    out = oe.best_candidate([_univ("SPY", 100, [_put(95, 40, 0.25, 1.20, 1000)])])
    assert out["candidate"] is None
