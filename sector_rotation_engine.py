"""
sector_rotation_engine.py — Banshee 5 Sector Rotation Engine

Tracks institutional capital flows across the 10 S&P 500 sector SPDRs
using Comparative Relative Strength (CRS) and Rate of Change (ROC) math.

Data-source agnostic: run() accepts a pre-fetched DataFrame and never
calls yfinance directly. The caller provides the closes.
"""

import sys
import pandas as pd
import numpy as np
from datetime import datetime, timezone
from cache_utils import ttl_cache

SECTORS = {
    "XLK":  "Technology",
    "XLY":  "Consumer Discretionary",
    "XLI":  "Industrials",
    "XLB":  "Materials",
    "XLE":  "Energy",
    "XLF":  "Financials",
    "XLV":  "Healthcare",
    "XLP":  "Consumer Staples",
    "XLU":  "Utilities",
    "XLRE": "Real Estate",
}

_ERROR_SHAPE = {
    "error": "Insufficient data",
    "sectors": [],
    "camd_alerts": [],
    "spy_roc_21": None,
    "macro_env": None,
}


def run(closes_df: pd.DataFrame, fred_key=None) -> dict:
    """
    Compute sector rotation metrics from a pre-fetched closes DataFrame.

    Args:
        closes_df: DataFrame with DatetimeIndex and columns for SPY + all 10
                   sector SPDRs. Needs at least 22 trading-day rows.
        fred_key:  Optional FRED API key. If None, macro_env is omitted.

    Returns:
        dict with keys: timestamp, spy_roc_21, sectors, camd_alerts, macro_env.
        On insufficient data, returns _ERROR_SHAPE with an "error" key.
    """
    closes = closes_df.dropna(how="all").copy()

    if len(closes) < 22 or "SPY" not in closes.columns:
        return dict(_ERROR_SHAPE)

    spy = closes["SPY"]

    # SPY 21-day absolute momentum — gate for CAMD detection
    spy_roc_21 = float((spy.iloc[-1] - spy.iloc[-22]) / spy.iloc[-22] * 100)

    sectors_out = []
    for ticker, name in SECTORS.items():
        if ticker not in closes.columns:
            continue

        sector_prices = closes[ticker]
        crs = sector_prices / spy  # Comparative Relative Strength

        # Rate of Change on the CRS ratio
        roc_21 = float((crs.iloc[-1] - crs.iloc[-22]) / crs.iloc[-22] * 100)
        roc_5  = float((crs.iloc[-1] - crs.iloc[-6])  / crs.iloc[-6]  * 100)

        # CAMD: sector outperforming AND SPY flat-or-falling
        camd = bool(roc_21 > 0 and roc_5 > 0 and spy_roc_21 <= 0)

        sectors_out.append({
            "ticker": ticker,
            "name":   name,
            "roc_5":  round(roc_5,  2),
            "roc_21": round(roc_21, 2),
            "camd":   camd,
        })

    sectors_out.sort(key=lambda s: s["roc_21"], reverse=True)

    camd_alerts = [
        {
            "ticker":              s["ticker"],
            "name":                s["name"],
            "roc_5":               s["roc_5"],
            "roc_21":              s["roc_21"],
            "divergence_strength": round(s["roc_21"] - spy_roc_21, 2),
        }
        for s in sectors_out if s["camd"]
    ]
    camd_alerts.sort(key=lambda a: a["divergence_strength"], reverse=True)

    macro_env = _get_macro_env(fred_key) if fred_key else None

    return {
        "timestamp":   datetime.now(timezone.utc).isoformat(),
        "spy_roc_21":  round(spy_roc_21, 2),
        "sectors":     sectors_out,
        "camd_alerts": camd_alerts,
        "macro_env":   macro_env,
    }


@ttl_cache(ttl=14400)
def _get_macro_env(fred_key) -> dict:
    """
    Fetch copper/gold ratio + 10Y yield from FRED. Cached 4 hours.
    Returns None silently on any failure (FRED key absent, network error, etc.).
    """
    if not fred_key:
        return None
    try:
        from fredapi import Fred

        fred  = Fred(api_key=fred_key)
        end   = pd.Timestamp.now()
        start = end - pd.Timedelta(days=90)

        copper = fred.get_series("PCOPPUSDM",        observation_start=start, observation_end=end).dropna()
        gold   = fred.get_series("GOLDAMGBD228NLBM", observation_start=start, observation_end=end).dropna()
        dgs10  = fred.get_series("DGS10",            observation_start=start, observation_end=end).dropna()

        if copper.empty or gold.empty or dgs10.empty:
            return None

        # Align monthly copper to daily gold via forward-fill
        combined = pd.DataFrame({"copper": copper, "gold": gold}).ffill().dropna()
        if len(combined) < 2:
            return None

        lookback = min(22, len(combined) - 1)
        cg_now   = combined["copper"].iloc[-1] / combined["gold"].iloc[-1]
        cg_prev  = combined["copper"].iloc[-lookback] / combined["gold"].iloc[-lookback]
        cg_trend = cg_now - cg_prev

        y_lookback  = min(22, len(dgs10) - 1)
        yield_now   = float(dgs10.iloc[-1])
        yield_prev  = float(dgs10.iloc[-y_lookback])
        yield_trend = yield_now - yield_prev

        if cg_trend > 0 and yield_trend > 0:
            interp = "Risk-On Expansion: Rising Copper/Gold ratio and rising yields indicate cyclical growth."
        elif cg_trend < 0 and yield_trend < 0:
            interp = "Risk-Off Contraction: Falling Copper/Gold ratio and falling yields indicate defensive positioning."
        elif cg_trend > 0 and yield_trend <= 0:
            interp = "Divergence Warning: Copper/Gold ratio rising but yields falling. Expect yield capitulation upwards."
        else:
            interp = "Divergence Warning: Copper/Gold ratio falling but yields rising. Expect yield capitulation downwards."

        return {
            "copper_gold_ratio": round(float(cg_now), 6),
            "ten_year_yield":    round(yield_now, 3),
            "interpretation":    interp,
        }
    except Exception as e:
        print(f"[sector_rotation] FRED fetch failed: {e}", file=sys.stderr)
        return None
