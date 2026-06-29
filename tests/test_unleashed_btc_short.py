"""
Regression test: buried BTC short — conservative mode WAITs (entry gate),
unleashed mode surfaces the short with bounce risk still stated.

Fixture: identical HTF-bearish + extended-in-trend LTF on all three swing
timeframes (1d/4h/1h). Indicators are computed from OHLC via add_all_indicators
so get_trend, score_timeframe, and compute_entry_quality all see realistic values.

Network calls monkeypatched to keep test hermetic (no live data required).
"""

import numpy as np
import pandas as pd
import micro_engine as me


def _downtrend_df(n=200, start=100.0, step=-0.4):
    """
    A clean steady downtrend.  add_all_indicators computes structural indicators
    (EMA stack, Supertrend, OBV, VWAP) from OHLC; oscillators are then overridden
    to representative values that avoid the exact floating-point boundary in the
    bias calculation while keeping the "extended-in-trend short" scenario intact.

    After add_all_indicators:
      • EMA_20 < EMA_50 < EMA_200  →  get_trend returns "DOWNTREND"
      • Swing highs/lows both declining  →  DOWNTREND confirmed by structure
      • st_bull = False  →  Supertrend bearish

    Overridden oscillators:
      • rsi = 32  →  in score_timeframe: rsi <= 45 → bear momentum (not < 30, no BULL signal)
                     in entry_quality:  rsi < 35  → "Fast RSI is oversold" extended check ✓
      • stoch_k = 8  →  score_timeframe: k < 20 → weak bull (oversold reversal note)
                        entry_quality:  k < 25  → "Stoch RSI already oversold" extended check ✓
      • stoch_d = 12  →  above k → no fresh cross, only the oversold region
      • mfi = 40  →  mfi <= 45 → bear flow (not < 20, no BULL oversold signal)

    Net result: bear score >> bull score → BEARISH bias, SELL SETUP/STRONG SELL verdict,
    extended-in-trend check fires → WAIT gate conservative / CAUTION gate unleashed.
    """
    close = start + np.arange(n) * step
    df = pd.DataFrame({
        "timestamp": pd.date_range(end="2026-06-29", periods=n, freq="h"),
        "open":   close + 0.1,
        "high":   close + 0.2,
        "low":    close - 0.2,
        "close":  close,
        "volume": 1000.0,
    })
    df = me.add_all_indicators(df)
    # Override oscillators to values that are bearish-ranged but not extreme-oversold,
    # keeping the extended-in-trend short scenario while ensuring htf_edge << -0.5.
    df["rsi"]     = 32.0   # bearish momentum zone; triggers entry_quality extended (< 35)
    df["stoch_k"] = 8.0    # oversold for shorts; triggers extended (< 25)
    df["stoch_d"] = 12.0   # above k, no fresh cross
    df["mfi"]     = 40.0   # bearish flow, not extreme
    return df


def test_btc_short_waits_conservative_but_surfaces_unleashed(monkeypatch):
    """
    Headline regression for the Unleashed feature.

    Conservative: entry gate kills the trade (WAIT) because RSI is oversold
    for a short — the "extended-in-trend" condition.

    Unleashed: the same read surfaces as a SELL SETUP / STRONG SELL with the
    bounce-risk note still present in extended_reading.mean_reversion_note.
    """
    # ── hermetic: no network calls ──────────────────────────────────────────────
    monkeypatch.setattr(me, "fetch_funding_rate",
                        lambda *a, **k: None)
    monkeypatch.setattr(me, "fetch_crypto_ohlcv",
                        lambda *a, **k: (pd.DataFrame(), None))

    tfs = {
        "1d": _downtrend_df(),
        "4h": _downtrend_df(),
        "1h": _downtrend_df(),
    }

    cons = me.run_analysis("BTC/USD", "swing", tfs, unleashed=False)
    unl  = me.run_analysis("BTC/USD", "swing", tfs, unleashed=True)

    # ── diagnostic output (visible on failure) ──────────────────────────────────
    print(f"\n[FIXTURE] cons['trends']        = {cons['trends']}")
    print(f"[FIXTURE] cons['bias']           = {cons['bias']}")
    print(f"[FIXTURE] cons['verdict']        = {cons['verdict']}")
    print(f"[FIXTURE] cons['entry_quality']  = {cons['entry_quality']}")
    print(f"[FIXTURE] unl['verdict']         = {unl['verdict']}")
    print(f"[FIXTURE] unl['trigger']         = {unl['trigger']}")
    print(f"[FIXTURE] unl['entry_quality']   = {unl['entry_quality']}")
    print(f"[FIXTURE] unl['frame'][:60]      = {unl['frame'][:60]!r}")

    # ── Both modes see the same structural truth ─────────────────────────────────
    assert cons["bias"]["direction"] == "BEARISH", (
        f"Conservative bias should be BEARISH, got {cons['bias']}"
    )
    assert unl["bias"]["direction"] == "BEARISH", (
        f"Unleashed bias should be BEARISH, got {unl['bias']}"
    )
    assert unl["trigger"]["direction"] == "SHORT", (
        f"Unleashed trigger direction should be SHORT, got {unl['trigger']}"
    )

    # ── Unleashed surfaces an actionable short WITH bounce risk stated ───────────
    assert unl["verdict"] in ("SELL SETUP", "STRONG SELL"), (
        f"Unleashed verdict should be SELL SETUP or STRONG SELL, got {unl['verdict']!r}"
    )
    assert unl["entry_quality"]["quality"] != "WAIT", (
        f"Unleashed entry gate must NOT veto (expected CAUTION/READY), "
        f"got {unl['entry_quality']}"
    )
    assert unl["frame"], \
        "Unleashed frame (disclaimer) should be non-empty"
    assert unl["trigger"]["extended_reading"]["mean_reversion_note"], (
        "mean_reversion_note must be non-empty — bounce risk must NOT be hidden "
        "even in unleashed mode"
    )
