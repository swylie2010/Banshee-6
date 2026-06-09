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
