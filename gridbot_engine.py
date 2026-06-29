"""gridbot_engine.py — Banshee Gridbot Calculator
Implements the 4-phase gridbot analysis framework from the research doc:
  Phase 1 — Regime filtration (MA120 slope, RSI, ATR)
  Phase 2 — Topology routing + dynamic parameterization
  Phase 3 — Capital plan (soft martingale)
  Phase 4 — Defensive constraints (disaster stop, churning check)
"""

import math
import pandas as pd
import numpy as np


# ── Symbol mapping ─────────────────────────────────────────────────────────────

_CRYPTO = {
    "BTC","ETH","SOL","BNB","ADA","AVAX","DOT","MATIC","LINK","UNI",
    "ATOM","LTC","BCH","XLM","ALGO","TAO","SUI","APT","OP","ARB",
    "NEAR","FTM","DOGE","SHIB","PAXG","HYPE","HBAR","AAVE","CRV","XRP",
}

def _to_yf_sym(sym: str) -> str:
    sym = sym.upper().strip()
    if "/" in sym:
        return sym.replace("/", "-")
    base = sym.split("-")[0]
    if base in _CRYPTO and "-" not in sym:
        return f"{sym}-USD"
    return sym


# ── Technical indicators ───────────────────────────────────────────────────────

def _rsi(close: pd.Series, period: int = 14) -> float:
    if len(close) < period + 1:
        return 50.0
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, float("nan"))
    rsi_s = 100 - (100 / (1 + rs))
    vals = rsi_s.dropna()
    return float(vals.iloc[-1]) if not vals.empty else 50.0


def _atr(hist: pd.DataFrame, period: int = 14) -> float:
    high = hist["High"]
    low  = hist["Low"]
    close = hist["Close"]
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low  - prev_close).abs(),
    ], axis=1).max(axis=1)
    atr_s = tr.rolling(period).mean()
    vals = atr_s.dropna()
    return float(vals.iloc[-1]) if not vals.empty else float((high - low).mean())


def _ma_slope_pct(close: pd.Series, ma_period: int = 120, lookback: int = 5) -> float:
    """% change in MA over `lookback` bars."""
    ma = close.rolling(ma_period).mean().dropna()
    if len(ma) <= lookback:
        return 0.0
    now   = float(ma.iloc[-1])
    prior = float(ma.iloc[-(lookback + 1)])
    return ((now - prior) / prior) * 100 if prior > 0 else 0.0


def _bollinger(close: pd.Series, period: int = 20, mult: float = 2.0):
    if len(close) < period:
        mid = float(close.mean())
        std = float(close.std())
    else:
        roll = close.rolling(period)
        mid  = float(roll.mean().dropna().iloc[-1])
        std  = float(roll.std().dropna().iloc[-1])
    return mid - mult * std, mid + mult * std


# ── Main analysis ──────────────────────────────────────────────────────────────

def analyze_gridbot(sym: str, capital: float, grid_count: int, fee_pct: float,
                    range_min: float | None = None, range_max: float | None = None) -> dict:
    """Run the 4-phase Banshee gridbot analysis. Returns a dict."""
    import data_providers
    yf_sym = _to_yf_sym(sym)
    raw = data_providers.fetch_ohlcv(yf_sym, "1d", limit=180)

    if raw is None or raw.empty or len(raw) < 20:
        return {"error": f"No price data found for '{sym}'. Check the ticker symbol (e.g. BTC, ETH, SPY, QQQ)."}

    # Rename to capitalized columns — rest of engine uses hist["Close"], hist["High"], hist["Low"]
    hist = raw.rename(columns={
        "open": "Open", "high": "High", "low": "Low",
        "close": "Close", "volume": "Volume",
    }).set_index("timestamp")

    close   = hist["Close"]
    current = float(close.iloc[-1])
    atr14   = _atr(hist, 14)

    # ── Phase 1: Regime filtration ─────────────────────────────────────────────
    slope   = _ma_slope_pct(close, 120, 5)
    rsi_val = _rsi(close, 14)

    if abs(slope) > 3.0:
        eligible = False
        reason = (
            f"Strong trend detected — MA120 moved {slope:+.1f}% in 5 days. "
            "Gridbots need sideways markets. Wait for the slope to flatten."
        )
    elif rsi_val > 75:
        eligible = False
        reason = (
            f"Overbought (RSI {rsi_val:.1f}). Momentum is extreme — wait for "
            "the RSI to cool below 70 before deploying a grid."
        )
    elif rsi_val < 25:
        eligible = False
        reason = (
            f"Oversold (RSI {rsi_val:.1f}). A falling knife cuts through grids. "
            "Wait for a base to form (RSI > 30) before deploying."
        )
    else:
        eligible = True
        reason = (
            f"Asset is oscillating — MA120 slope {slope:+.1f}%, RSI {rsi_val:.1f}. "
            "Conditions favor grid deployment."
        )

    # ── Phase 2: Topology + bounds ─────────────────────────────────────────────
    bb_lo, bb_hi = _bollinger(close, 20, 2.0)
    high30 = float(hist["High"].tail(30).max())
    low30  = float(hist["Low"].tail(30).min())

    if range_min is not None and range_max is not None and float(range_min) > 0 and float(range_max) > float(range_min):
        upper = float(range_max)
        lower = float(range_min)
    else:
        upper = min(bb_hi, high30)
        lower = max(bb_lo, low30)
        if upper <= lower or upper <= 0:
            upper = high30
            lower = low30

    range_pct = ((upper - lower) / lower) * 100 if lower > 0 else 0.0
    topology  = "geometric" if range_pct > 15 else "arithmetic"

    n = max(2, grid_count)
    spacing_abs = None
    ratio       = None

    if topology == "arithmetic":
        spacing_abs = (upper - lower) / n
        # Anti-churning floor
        min_fee_spacing = (2.5 * fee_pct / 100) * current
        min_atr_spacing = atr14 * 0.5
        spacing_abs = max(spacing_abs, min_fee_spacing, min_atr_spacing)
        n = max(2, int((upper - lower) / spacing_abs))
        spacing_abs = (upper - lower) / n
        spacing_pct = (spacing_abs / current) * 100 if current > 0 else 0.0
    else:
        ratio = (upper / lower) ** (1.0 / n)
        spacing_pct = (ratio - 1.0) * 100
        min_fee_pct = 2.5 * fee_pct
        if spacing_pct < min_fee_pct:
            ratio = 1.0 + min_fee_pct / 100
            spacing_pct = min_fee_pct
            n = max(2, int(math.log(upper / lower) / math.log(ratio)))

    churning = spacing_pct < (2.5 * fee_pct)

    # ── Grid levels ─────────────────────────────────────────────────────────────
    levels = []
    REF_THRESH = spacing_abs * 0.1 if spacing_abs else current * 0.005
    for i in range(n + 1):
        if topology == "arithmetic":
            price = lower + i * spacing_abs
        else:
            price = lower * (ratio ** i)

        dist = abs(price - current)
        if dist < REF_THRESH:
            ltype = "REF"
        elif price < current:
            ltype = "BUY"
        else:
            ltype = "SELL"

        if topology == "arithmetic":
            profit = max(0.0, spacing_abs - 2 * (fee_pct / 100) * price)
            lvl = {"index": i, "price": round(price, 6), "type": ltype, "profit_per_cycle": round(profit, 4)}
        else:
            profit_pct = max(0.0, (ratio - 1.0) - 2 * (fee_pct / 100)) * 100
            lvl = {"index": i, "price": round(price, 6), "type": ltype, "profit_pct_per_cycle": round(profit_pct, 4)}

        levels.append(lvl)

    # ── Phase 3: Capital plan (soft martingale) ─────────────────────────────────
    anchor   = round(capital * 0.5, 2)
    grid_cap = round(capital * 0.5, 2)

    # linspace(1.0, 3.0, n+1) — level 0 (inner) gets 1×, level n (outer) gets 3×
    total_levels = len(levels)
    if total_levels > 1:
        weights = [1.0 + (3.0 - 1.0) * i / (total_levels - 1) for i in range(total_levels)]
    else:
        weights = [2.0]
    total_w = sum(weights)
    cap_per_level = [round(grid_cap * w / total_w, 2) for w in weights]

    for lvl in levels:
        lvl["capital_allocated"] = cap_per_level[lvl["index"]] if lvl["index"] < len(cap_per_level) else 0.0

    # ── Phase 4: Risk guardrails ────────────────────────────────────────────────
    disaster_stop = lower - 1.5 * atr14

    # Simplified max drawdown: grid capital deployed at average of current & lower
    avg_buy = (current + lower) / 2.0 if current > lower else lower
    if avg_buy > 0 and current > 0:
        shares = grid_cap / avg_buy
        value_at_lower = shares * lower
        float_loss = grid_cap - value_at_lower
        max_dd_pct = (float_loss / capital) * 100
    else:
        max_dd_pct = 0.0

    return {
        "sym": sym,
        "current_price": round(current, 6),
        "regime": {
            "eligible": eligible,
            "ma120_slope_pct": round(slope, 2),
            "rsi": round(rsi_val, 1),
            "atr14": round(atr14, 6),
            "reason": reason,
        },
        "topology": topology,
        "grid": {
            "upper": round(upper, 6),
            "lower": round(lower, 6),
            "range_pct": round(range_pct, 2),
            "count": n,
            "spacing_abs": round(spacing_abs, 6) if spacing_abs is not None else None,
            "spacing_pct": round(spacing_pct, 4),
            "ratio": round(ratio, 8) if ratio is not None else None,
        },
        "levels": levels,
        "capital_plan": {
            "total": capital,
            "anchor": anchor,
            "grid_distributed": grid_cap,
            "weights": [round(w, 3) for w in weights],
            "capital_per_level": cap_per_level,
        },
        "risk": {
            "disaster_stop": round(disaster_stop, 6),
            "max_drawdown_pct": round(max_dd_pct, 1),
            "churning_warning": churning,
            "spacing_pct": round(spacing_pct, 4),
            "min_fee_spacing_pct": round(2.5 * fee_pct, 4),
        },
    }
