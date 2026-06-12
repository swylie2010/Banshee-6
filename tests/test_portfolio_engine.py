"""Tests for portfolio_engine.py"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import pandas as pd
import numpy as np
import portfolio_engine as pe


# ── score_to_grade ──────────────────────────────────────────────
def test_grade_a_plus():
    assert pe.score_to_grade(95) == "A+"

def test_grade_b_plus():
    assert pe.score_to_grade(82) == "B+"

def test_grade_c_minus():
    assert pe.score_to_grade(55) == "C-"

def test_grade_f():
    assert pe.score_to_grade(30) == "F"

def test_grade_boundary_exact_b():
    assert pe.score_to_grade(75) == "B"

def test_grade_boundary_one_below_b():
    assert pe.score_to_grade(74.9) == "B-"


# ── run() ───────────────────────────────────────────────────────
def _make_holdings(with_entry=False):
    data = {
        "sym":           ["AAPL", "NVDA"],
        "shares":        [10,      5     ],
        "entry_price":   [155.0,   None  ] if with_entry else [None, None],
        "entry_date":    ["2024-01-15", None] if with_entry else [None, None],
        "current_price": [187.42, 875.40],
        "cls":           ["EQUITY", "EQUITY"],
    }
    return pd.DataFrame(data)

def test_run_computes_total_value():
    df = _make_holdings()
    result = pe.run(df, pd.Series(dtype=float))
    assert abs(result["total_value"] - (10 * 187.42 + 5 * 875.40)) < 0.01

def test_run_weights_sum_to_one():
    df = _make_holdings()
    result = pe.run(df, pd.Series(dtype=float))
    total_w = sum(r["weight"] for r in result["weights"])
    assert abs(total_w - 1.0) < 0.001

def test_run_twrr_with_entry_data():
    df = _make_holdings(with_entry=True)
    result = pe.run(df, pd.Series(dtype=float))
    assert result["twrr"] is not None
    assert result["twrr"] > 0  # AAPL went from 155 to 187.42 = positive

def test_run_no_entry_data_gives_no_twrr():
    df = _make_holdings(with_entry=False)
    result = pe.run(df, pd.Series(dtype=float))
    assert result["twrr"] is None

def test_run_zero_value_returns_error():
    df = pd.DataFrame({
        "sym": ["BTC"], "shares": [0], "entry_price": [None],
        "entry_date": [None], "current_price": [50000], "cls": ["CRYPTO"],
    })
    try:
        result = pe.run(df, pd.Series(dtype=float))
        assert "error" in result, "Expected 'error' key in result dict for zero-value portfolio"
    except (ValueError, ZeroDivisionError):
        pass  # engine raising is also acceptable behavior


# ── build_blended_benchmark() ───────────────────────────────────
def test_build_blended_empty_closes_returns_empty():
    result = pe.build_blended_benchmark({"TECH": 1.0}, pd.DataFrame())
    assert result.empty

def test_build_blended_known_sector():
    dates = pd.date_range("2024-01-01", periods=10, freq="D")
    closes = pd.DataFrame({"XLK": [100, 101, 102, 103, 104, 105, 106, 107, 108, 109]}, index=dates)
    result = pe.build_blended_benchmark({"TECH": 1.0}, closes)
    assert len(result) > 0, "build_blended_benchmark returned empty series"
    assert all(0.0 <= v < 0.02 for v in result)  # all non-negative, <2% per day

def test_build_blended_unmapped_sector_falls_back_to_spy():
    dates = pd.date_range("2024-01-01", periods=10, freq="D")
    closes = pd.DataFrame({"SPY": [400, 401, 402, 403, 404, 405, 406, 407, 408, 409]}, index=dates)
    result = pe.build_blended_benchmark({"UNKNOWN_SECTOR": 1.0}, closes)
    assert not result.empty


# ── score_portfolio() ───────────────────────────────────────────
def _make_engine_result():
    return {
        "sharpe": None,
        "total_value": 10000,
        "weights": [
            {"sym": "AAPL", "weight": 0.6, "value": 6000, "cls": "EQUITY"},
            {"sym": "BTC",  "weight": 0.4, "value": 4000, "cls": "CRYPTO"},
        ]
    }

def test_score_no_sharpe_is_momentum_only():
    result = pe.score_portfolio(
        _make_engine_result(),
        radar_data={"AAPL": {"edge": 80}, "BTC": {"edge": 60}},
    )
    # momentum = 80*0.6 + 60*0.4 = 72, no sharpe → grade is pure basket momentum
    assert abs(result["score"] - 72.0) < 0.5
    assert result["grade"] == "B-"
    assert result["risk_score"] is None
    # sector alignment is no longer a grade input
    assert "alignment_score" not in result

def test_score_with_sharpe_uses_momentum_60_risk_40():
    er = _make_engine_result()
    er["sharpe"] = 1.5  # normalised = 75
    result = pe.score_portfolio(
        er,
        radar_data={"AAPL": {"edge": 80}, "BTC": {"edge": 60}},
    )
    # momentum=72*0.60=43.2, risk=75*0.40=30.0 → 73.2
    assert abs(result["score"] - 73.2) < 1.0
    assert result["risk_score"] == 75.0

def test_score_missing_radar_defaults_to_50_edge():
    result = pe.score_portfolio(
        _make_engine_result(),
        radar_data={},  # no radar data
    )
    # both assets default to edge=50, no sharpe → score ~50
    assert 45 <= result["score"] <= 55

def test_score_perfect_portfolio():
    er = _make_engine_result()
    er["sharpe"] = 2.0
    result = pe.score_portfolio(
        er,
        radar_data={"AAPL": {"edge": 100}, "BTC": {"edge": 100}},
    )
    assert abs(result["score"] - 100.0) < 0.01
    assert result["grade"] == "A+"


def test_run_portfolio_analysis_returns_required_keys():
    """run_portfolio_analysis must return a dict with the expected top-level keys."""
    import portfolio_engine as pe
    portfolio = {
        "id": "test",
        "name": "Test",
        "holdings": [{"sym": "SPY", "cls": "EQUITY", "shares": 1}],
        "transactions": [
            {"type": "BUY", "sym": "SPY", "shares": 1, "price": 400.0, "date": "2024-01-02"}
        ],
    }
    result = pe.run_portfolio_analysis(portfolio, "2025-01-01")
    for key in ("holdings", "sector_weights", "risk", "grade", "performance"):
        assert key in result, f"Missing key: {key}"
