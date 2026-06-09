"""Tests for options_data.py — the yfinance->contract adapter (pure mapping)."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pandas as pd
import options_data as od


def test_normalize_puts_standard_yfinance_columns():
    df = pd.DataFrame([
        {"strike": 95.0, "bid": 1.10, "ask": 1.30, "impliedVolatility": 0.25,
         "openInterest": 4000, "volume": 220},
    ])
    out = od.normalize_puts(df, spot=100.0, expiry="2026-07-17", today="2026-06-09")
    c = out[0]
    assert c["type"] == "put"
    assert c["strike"] == 95.0
    assert c["iv"] == 0.25
    assert c["open_interest"] == 4000
    assert c["mid"] == 1.20                  # (1.10 + 1.30) / 2
    assert c["dte"] == 38                     # 2026-06-09 -> 2026-07-17


def test_normalize_puts_tolerates_renamed_reordered_columns():
    # a different source: different names, different order
    df = pd.DataFrame([
        {"oi": 4000, "implied_vol": 0.25, "ask": 1.30, "strike": 95.0, "bid": 1.10},
    ])
    out = od.normalize_puts(df, spot=100.0, expiry="2026-07-17", today="2026-06-09")
    c = out[0]
    assert c["iv"] == 0.25 and c["open_interest"] == 4000 and c["strike"] == 95.0


def test_normalize_puts_skips_rows_missing_required_fields():
    df = pd.DataFrame([
        {"strike": 95.0, "bid": 1.10, "ask": 1.30, "impliedVolatility": 0.25, "openInterest": 4000},
        {"bid": 1.0, "ask": 1.2},   # no strike -> skipped
    ])
    out = od.normalize_puts(df, spot=100.0, expiry="2026-07-17", today="2026-06-09")
    assert len(out) == 1
