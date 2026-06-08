"""
portfolio_engine.py — Banshee 5 Portfolio Analysis Engine

Accepts DataFrames; never calls yfinance directly (adapter pattern).
"""

import numpy as np
import pandas as pd

_SECTOR_ETF_MAP = {
    "TECH":     "XLK",
    "FINANCE":  "XLF",
    "CRYPTO":   "IBIT",
    "COMMS":    "XLC",
    "ENERGY":   "XLE",
    "HEALTH":   "XLV",
    "CONSUMER": "XLY",
    "UTILITY":  "XLU",
}

_GRADE_THRESHOLDS = [
    (95, "A+"), (90, "A"), (85, "A-"),
    (80, "B+"), (75, "B"), (70, "B-"),
    (65, "C+"), (60, "C"), (55, "C-"),
    (50, "D"),  (0,  "F"),
]


def score_to_grade(score: float) -> str:
    """Map 0-100 score to letter grade."""
    for threshold, grade in _GRADE_THRESHOLDS:
        if score >= threshold:
            return grade
    return "F"


def run(holdings: pd.DataFrame, benchmark_returns: pd.Series) -> dict:
    """
    holdings: DataFrame with columns:
        sym (str), shares (float), entry_price (float|None),
        entry_date (str|None), current_price (float), cls (str)
    benchmark_returns: pre-fetched daily returns Series (DatetimeIndex)
    Returns dict with keys: sharpe, alpha, beta, max_drawdown, twrr,
                            total_value, weights (list of dicts)
    """
    df = holdings.copy()
    df["value"]  = df["shares"] * df["current_price"]
    total_value  = df["value"].sum()

    if total_value <= 0:
        return {"error": "zero portfolio value"}

    df["weight"] = df["value"] / total_value

    # TWRR — Modified Dietz (simplified: per-holding return weighted by weight)
    has_entry = df.dropna(subset=["entry_price"])
    twrr = None
    if not has_entry.empty:
        gains = [
            ((row["current_price"] - row["entry_price"]) / row["entry_price"]) * row["weight"]
            for _, row in has_entry.iterrows()
            if row["entry_price"] > 0
        ]
        twrr = round(sum(gains), 4) if gains else None

    # Risk metrics via quantstats (only if benchmark available)
    sharpe = alpha = beta = max_dd = None
    if twrr is not None and not benchmark_returns.empty and len(benchmark_returns) >= 30:
        try:
            import quantstats as qs
            n = len(benchmark_returns)
            # Synthesise daily portfolio returns: scale benchmark by (1 + TWRR/n) per day
            port_returns = benchmark_returns * (1 + twrr / n)
            sharpe = round(float(qs.stats.sharpe(port_returns)), 3)
            max_dd = round(float(qs.stats.max_drawdown(port_returns)), 4)
            alpha, beta = _compute_alpha_beta(port_returns, benchmark_returns)
        except Exception:
            pass

    return {
        "sharpe":       sharpe,
        "alpha":        alpha,
        "beta":         beta,
        "max_drawdown": max_dd,
        "twrr":         twrr,
        "total_value":  round(total_value, 2),
        "weights":      df[["sym", "weight", "value", "cls"]].to_dict("records"),
    }


def _compute_alpha_beta(port: pd.Series, bench: pd.Series) -> tuple:
    aligned = pd.concat([port, bench], axis=1).dropna()
    if len(aligned) < 10:
        return 0.0, 1.0
    y = aligned.iloc[:, 0].values
    x = aligned.iloc[:, 1].values
    beta  = float(np.cov(y, x)[0, 1] / (np.var(x) or 1))
    alpha = float((np.mean(y) - beta * np.mean(x)) * 252)  # annualised
    return round(alpha, 4), round(beta, 3)


def build_blended_benchmark(sector_weights: dict, closes: pd.DataFrame) -> pd.Series:
    """
    sector_weights: { 'TECH': 0.48, 'CRYPTO': 0.38, 'COMMS': 0.14 }
    closes: DataFrame of daily close prices with ETF tickers as columns.
            Caller provides this (fetched via yfinance adapter in shared_data).
    Returns: blended daily returns Series.
    """
    if closes.empty or not sector_weights:
        return pd.Series(dtype=float)

    blended   = pd.Series(0.0, index=closes.index)
    spy_weight = 0.0

    for sector, weight in sector_weights.items():
        etf = _SECTOR_ETF_MAP.get(sector.upper())
        if etf and etf in closes.columns:
            blended += closes[etf].pct_change().fillna(0) * weight
        else:
            spy_weight += weight  # unmapped → proxy to SPY

    if spy_weight > 0 and "SPY" in closes.columns:
        blended += closes["SPY"].pct_change().fillna(0) * spy_weight

    return blended.dropna()


def score_portfolio(
    engine_result: dict,
    radar_data: dict,
    alignment_score: float,
) -> dict:
    """
    engine_result: output of run()
    radar_data: { sym: { edge: float }, ... }  (from /radar endpoint)
    alignment_score: 0.0-100.0, pre-computed by caller from rotation data
    Returns: { score, grade, momentum_score, alignment_score, risk_score }
    """
    weights_list = engine_result.get("weights", [])
    if not weights_list:
        return {"score": 0, "grade": "F", "momentum_score": 0,
                "alignment_score": 0, "risk_score": None}

    # Momentum: weighted average of edge scores
    total_w = sum(row["weight"] for row in weights_list) or 1
    momentum_score = sum(
        radar_data.get(row["sym"], {}).get("edge", 50) * (row["weight"] / total_w)
        for row in weights_list
    )
    momentum_score = min(100, max(0, round(momentum_score, 1)))
    alignment_score = min(100, max(0, round(alignment_score, 1)))

    sharpe = engine_result.get("sharpe")
    has_sharpe = sharpe is not None
    risk_score = None

    if has_sharpe:
        risk_score = min(100, max(0, round((sharpe / 2.0) * 100, 1)))
        score = momentum_score * 0.35 + alignment_score * 0.35 + risk_score * 0.30
    else:
        score = momentum_score * 0.50 + alignment_score * 0.50

    return {
        "score":           round(score, 1),
        "grade":           score_to_grade(score),
        "momentum_score":  momentum_score,
        "alignment_score": alignment_score,
        "risk_score":      risk_score,
    }
