"""test_thin_history_analysis.py — a thin-history symbol must degrade, never crash.

Real incident: looking up SPCX (a thinly-traded ETF) in the search box did
NOTHING — no chart, no error, total silence. Root cause: its data feed returns
only ~22 daily bars, which is under the 30-bar floor in add_all_indicators, so
that step returns the frame WITHOUT the swing_high/swing_low and EMA columns.
Two downstream consumers (find_sr_levels, score_timeframe) then read those
columns unconditionally and raised KeyError -> the /radar route 500'd -> the
search box swallowed the 500 as "symbol not found" and rendered a blank.

The engine must instead compute whatever the data supports and clearly FLAG the
limited history — a silent blank makes Banshee look broken. These tests lock
that in: they reproduce the exact missing-column shape and assert no crash.
"""
import pandas as pd

import micro_engine as me


def _price_frame(closes):
    """Bare OHLCV frame — the shape a provider returns before indicators are added."""
    n = len(closes)
    return pd.DataFrame({
        "open":   closes,
        "high":   [c * 1.01 for c in closes],
        "low":    [c * 0.99 for c in closes],
        "close":  closes,
        "volume": [1000.0] * n,
    })


# 22 bars — mirrors SPCX's daily feed, under the 30-bar indicator floor.
_THIN = [100 + i * 0.5 for i in range(22)]
# 60 bars — comfortably above the floor, so the full indicator set is built.
_FULL = [100 + i * 0.7 + (3 if i % 3 == 0 else -2) for i in range(60)]


def test_thin_frame_really_lacks_indicator_columns():
    """Anchor: a <30-bar frame genuinely comes back column-less. If this ever
    changes, the crash tests below could pass for the wrong reason."""
    thin = me.add_all_indicators(_price_frame(_THIN))
    assert "swing_high" not in thin.columns
    assert "ema_20" not in thin.columns


def test_find_sr_levels_survives_missing_swing_columns():
    """Falls back to price-derived (psychological) levels — no KeyError."""
    thin = me.add_all_indicators(_price_frame(_THIN))
    support, resistance = me.find_sr_levels(thin, price=110.0)
    assert isinstance(support, list) and isinstance(resistance, list)


def test_score_timeframe_survives_missing_indicator_columns():
    """A thin timeframe contributes a neutral score, never a crash."""
    thin = me.add_all_indicators(_price_frame(_THIN))
    assert me.score_timeframe(thin, profile=None) == (0, 0, [])


def test_run_analysis_degrades_on_thin_slow_timeframe():
    """The real repro: a thin slow TF alongside healthy mid/fast TFs must yield
    a verdict PLUS an honest limited-history flag — never an exception, never an
    empty read. The flag makes the degradation legible to a UI or AI consumer."""
    tfs = {
        "1d": me.add_all_indicators(_price_frame(_THIN)),   # thin, column-less
        "4h": me.add_all_indicators(_price_frame(_FULL)),   # healthy
        "1h": me.add_all_indicators(_price_frame(_FULL)),   # healthy
    }
    res = me.run_analysis("TESTX", "swing", tfs, sensors=None, unleashed=False)
    assert "error" not in res
    assert res.get("verdict")
    assert res["warnings"].get("limited_history")
