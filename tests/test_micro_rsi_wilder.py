"""test_micro_rsi_wilder.py — RSI uses Wilder's smoothing, not Cutler's.

Banshee used to average gains/losses with a plain rolling mean (Cutler's RSI),
which reads a few points off from TradingView and every other chart (which use
Wilder's smoothing). That made Banshee "look wrong" on a sanity-check glance.
This locks in Wilder so a future edit can't silently regress to Cutler's.
"""
import numpy as np
import pandas as pd

import micro_engine as me


def _price_frame(closes):
    n = len(closes)
    return pd.DataFrame({
        "open":   closes,
        "high":   [c * 1.001 for c in closes],
        "low":    [c * 0.999 for c in closes],
        "close":  closes,
        "volume": [1000.0] * n,
    })


def _wilder_rsi(closes, period):
    s = pd.Series(closes, dtype=float)
    delta = s.diff()
    gain = delta.where(delta > 0, 0.0).ewm(alpha=1 / period, adjust=False).mean()
    loss = (-delta.where(delta < 0, 0.0)).ewm(alpha=1 / period, adjust=False).mean()
    return 100 - (100 / (1 + gain / loss.replace(0, np.nan)))


def _cutlers_rsi(closes, period):
    s = pd.Series(closes, dtype=float)
    delta = s.diff()
    gain = delta.where(delta > 0, 0.0).rolling(period).mean()
    loss = (-delta.where(delta < 0, 0.0)).rolling(period).mean()
    return 100 - (100 / (1 + gain / loss.replace(0, np.nan)))


# A noisy-but-trending series so Wilder and Cutler's genuinely diverge.
_CLOSES = [100 + i * 0.7 + (3 if i % 3 == 0 else -2) for i in range(60)]


def test_rsi_matches_wilder_not_cutlers():
    df = me.add_all_indicators(_price_frame(_CLOSES))
    got = df["rsi"].iloc[-1]

    wilder = _wilder_rsi(_CLOSES, me.RSI_PERIOD).iloc[-1]
    cutlers = _cutlers_rsi(_CLOSES, me.RSI_PERIOD).iloc[-1]

    # Engine must track Wilder...
    assert abs(got - wilder) < 1e-6, f"expected Wilder {wilder}, got {got}"
    # ...and the two methods must actually differ here, or the test proves nothing.
    assert abs(wilder - cutlers) > 0.5, "series doesn't separate the two methods"


def test_rsi_bounded_and_directional():
    # Strong trend with genuine small pullbacks every 5th bar (real series
    # always have some down-ticks; a perfectly monotonic series → loss=0 → NaN).
    up_closes, down_closes = [], []
    pu = pd_ = 100.0
    for i in range(60):
        pu += -0.5 if i % 5 == 4 else 1.0
        pd_ += 0.5 if i % 5 == 4 else -1.0
        up_closes.append(pu)
        down_closes.append(pd_)
    up = me.add_all_indicators(_price_frame(up_closes))
    down = me.add_all_indicators(_price_frame(down_closes))
    rsi_up = up["rsi"].iloc[-1]
    rsi_down = down["rsi"].iloc[-1]
    assert 0 <= rsi_up <= 100 and 0 <= rsi_down <= 100
    assert rsi_up > 70, f"steady uptrend should be overbought, got {rsi_up}"
    assert rsi_down < 30, f"steady downtrend should be oversold, got {rsi_down}"
