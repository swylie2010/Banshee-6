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


def test_normalize_puts_nan_volume_no_crash():
    df = pd.DataFrame([
        {"strike": 95.0, "bid": 1.10, "ask": 1.30, "impliedVolatility": 0.25,
         "openInterest": 4000, "volume": float("nan")},
    ])
    out = od.normalize_puts(df, spot=100.0, expiry="2026-07-17", today="2026-06-09")
    assert len(out) == 1
    assert out[0]["volume"] == 0           # NaN coerced, no crash


def test_normalize_puts_nan_iv_skipped():
    df = pd.DataFrame([
        {"strike": 95.0, "bid": 1.10, "ask": 1.30, "impliedVolatility": float("nan"), "openInterest": 4000},
    ])
    out = od.normalize_puts(df, spot=100.0, expiry="2026-07-17", today="2026-06-09")
    assert out == []                        # NaN IV row dropped


def test_normalize_puts_missing_iv_skipped():
    df = pd.DataFrame([{"strike": 95.0, "bid": 1.10, "ask": 1.30, "openInterest": 4000}])
    out = od.normalize_puts(df, spot=100.0, expiry="2026-07-17", today="2026-06-09")
    assert out == []                        # no IV column -> dropped


def test_dte_tolerates_time_suffix():
    df = pd.DataFrame([{"strike": 95.0, "bid": 1.1, "ask": 1.3, "impliedVolatility": 0.25, "openInterest": 4000}])
    out = od.normalize_puts(df, spot=100.0, expiry="2026-07-17T00:00:00", today="2026-06-09")
    assert out[0]["dte"] == 38


def test_fetch_earnings_date_returns_date():
    from unittest.mock import patch, MagicMock
    from datetime import date
    mock_ticker = MagicMock()
    mock_ticker.calendar = {"Earnings Date": [date(2026, 7, 18)]}
    with patch("yfinance.Ticker", return_value=mock_ticker):
        result = od.fetch_earnings_date("AAPL")
    assert result == date(2026, 7, 18)


def test_fetch_earnings_date_returns_none_on_error():
    from unittest.mock import patch, MagicMock
    mock_ticker = MagicMock()
    mock_ticker.calendar = None
    with patch("yfinance.Ticker", return_value=mock_ticker):
        result = od.fetch_earnings_date("AAPL")
    assert result is None
