"""Tests for sector_rotation_engine.run()."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pandas as pd
import pytest
import sector_rotation_engine as sre

_TICKERS = ["SPY","XLK","XLY","XLI","XLB","XLE","XLF","XLV","XLP","XLU","XLRE"]
_SECTOR_NAMES = {
    "XLK":"Technology","XLY":"Consumer Discretionary","XLI":"Industrials",
    "XLB":"Materials","XLE":"Energy","XLF":"Financials","XLV":"Healthcare",
    "XLP":"Consumer Staples","XLU":"Utilities","XLRE":"Real Estate",
}


def _make_closes(n=30, spy_flat=True):
    """
    Synthetic closes DataFrame.
    - SPY: flat at 100 (spy_flat=True) or growing 90→100 (spy_flat=False)
    - XLU: growing 90→110 (roc_21 > 0, roc_5 > 0)
    - XLK: shrinking 110→90 (roc_21 < 0)
    - All others: flat at 100
    """
    dates = pd.bdate_range("2026-01-01", periods=n)
    data = {}
    if spy_flat:
        data["SPY"] = [100.0] * n
    else:
        data["SPY"] = [90.0 + 10.0 * i / (n - 1) for i in range(n)]
    data["XLU"]  = [90.0 + 20.0 * i / (n - 1) for i in range(n)]
    data["XLK"]  = [110.0 - 20.0 * i / (n - 1) for i in range(n)]
    for t in ["XLY","XLI","XLB","XLE","XLF","XLV","XLP","XLRE"]:
        data[t] = [100.0] * n
    return pd.DataFrame(data, index=dates)


def test_output_keys_present():
    result = sre.run(_make_closes(), fred_key=None)
    assert "sectors" in result
    assert "camd_alerts" in result
    assert "spy_roc_21" in result
    assert "macro_env" in result
    assert result["macro_env"] is None  # no FRED key


def test_all_ten_sectors_present():
    result = sre.run(_make_closes(), fred_key=None)
    tickers = [s["ticker"] for s in result["sectors"]]
    for t in _SECTOR_NAMES:
        assert t in tickers, f"{t} missing from sectors"


def test_sector_fields_present():
    result = sre.run(_make_closes(), fred_key=None)
    for s in result["sectors"]:
        assert "ticker" in s
        assert "name" in s
        assert "roc_5" in s
        assert "roc_21" in s
        assert "camd" in s


def test_sectors_sorted_by_roc21_descending():
    result = sre.run(_make_closes(), fred_key=None)
    rocs = [s["roc_21"] for s in result["sectors"]]
    assert rocs == sorted(rocs, reverse=True)


def test_xlu_has_positive_roc21():
    result = sre.run(_make_closes(), fred_key=None)
    xlu = next(s for s in result["sectors"] if s["ticker"] == "XLU")
    assert xlu["roc_21"] > 0


def test_xlk_has_negative_roc21():
    result = sre.run(_make_closes(), fred_key=None)
    xlk = next(s for s in result["sectors"] if s["ticker"] == "XLK")
    assert xlk["roc_21"] < 0


def test_camd_fires_when_spy_flat_and_sector_outperforms():
    # SPY flat (roc_21 = 0 ≤ 0), XLU outperforming → CAMD = True
    result = sre.run(_make_closes(spy_flat=True), fred_key=None)
    xlu = next(s for s in result["sectors"] if s["ticker"] == "XLU")
    assert xlu["camd"] is True
    assert any(a["ticker"] == "XLU" for a in result["camd_alerts"])


def test_camd_does_not_fire_when_spy_rising():
    # SPY growing 90→100 (spy_roc_21 > 0) → CAMD never fires regardless of sector
    result = sre.run(_make_closes(spy_flat=False), fred_key=None)
    assert all(not s["camd"] for s in result["sectors"])
    assert result["camd_alerts"] == []


def test_insufficient_data_returns_error_shape():
    tiny = _make_closes(n=10)
    result = sre.run(tiny, fred_key=None)
    assert "error" in result
    assert result["sectors"] == []
    assert result["camd_alerts"] == []
    assert result["spy_roc_21"] is None


def test_camd_alerts_sorted_by_divergence_strength():
    result = sre.run(_make_closes(), fred_key=None)
    strengths = [a["divergence_strength"] for a in result["camd_alerts"]]
    assert strengths == sorted(strengths, reverse=True)


def test_sector_names_match():
    result = sre.run(_make_closes(), fred_key=None)
    for s in result["sectors"]:
        assert s["name"] == _SECTOR_NAMES[s["ticker"]]
