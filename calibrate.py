#!/usr/bin/env python3
"""
calibrate.py — Banshee Pro Indicator Calibration Health Check
==============================================================
Computes current indicator values for a symbol/mode and optionally
compares against a saved baseline (TV ground truth or prior Banshee run).

Usage:
    python calibrate.py NVDA long_term           # show current values; compare if baseline exists
    python calibrate.py BTC/USD swing            # same for BTC swing
    python calibrate.py NVDA long_term --save    # save current values as new baseline

Baseline files live in:  tv_extract/calibration/{SYMBOL}_{MODE}_baseline.json
Replace the 'values' block with TV ground truth (from data_get_study_values via MCP)
to get a meaningful signal-vs-noise comparison.

Drift thresholds (established 2026-04-25, NVDA 1W vs TradingView):
  RSI       ≤ 5.0 pts absolute     (observed: 2.78pt from yfinance vs TV)
  Stoch K   ≤ 5.0 pts absolute     (observed: ~1pt)
  Stoch D   ≤ 12.0 pts absolute    (amplified K drift through 2 smoothing layers)
  MACD      ≤ 15% relative         (observed: pixel-perfect)
  VWAP      ≤ 1.5% relative        (observed: 0.3pt)
  EMA 50/200 ≤ 0.5% relative       (should be very tight)
"""

from __future__ import annotations

# Suppress Streamlit "No runtime found" noise before any imports trigger it
import os
os.environ.setdefault("STREAMLIT_LOG_LEVEL", "error")
import logging
import warnings
logging.getLogger("streamlit").setLevel(logging.ERROR)
warnings.filterwarnings("ignore", module="streamlit")

import argparse
import json
import math
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# micro_engine → shared_data → st.cache_data emits "No runtime" noise during both
# import and runtime. Redirect stderr to devnull and leave it open — Streamlit's
# logger holds a reference so closing it causes write errors.
_stderr_real = sys.stderr
sys.stderr    = open(os.devnull, "w")   # kept open intentionally; GC'd at exit
import micro_engine
sys.stderr = _stderr_real

# ─── CONFIG ───────────────────────────────────────────────────────────────────

CALIBRATION_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "tv_extract", "calibration"
)

FIELDS = [
    "close", "rsi", "stoch_k", "stoch_d",
    "macd", "macd_signal", "macd_hist",
    "vwap", "ema_50", "ema_200", "atr",
]

LABELS = {
    "close":       "Close Price",
    "rsi":         "RSI (14)",
    "stoch_k":     "Stoch K",
    "stoch_d":     "Stoch D",
    "macd":        "MACD",
    "macd_signal": "MACD Signal",
    "macd_hist":   "MACD Hist",
    "vwap":        "VWAP",
    "ema_50":      "EMA 50",
    "ema_200":     "EMA 200",
    "atr":         "ATR (14)",
}

# (kind, limit) — "abs" = absolute points, "rel" = relative fraction
THRESHOLDS: dict[str, tuple[str, float]] = {
    "rsi":         ("abs", 5.0),
    "stoch_k":     ("abs", 5.0),
    "stoch_d":     ("abs", 12.0),
    "macd":        ("rel", 0.15),
    "macd_signal": ("rel", 0.15),
    "macd_hist":   ("rel", 0.25),
    "vwap":        ("rel", 0.015),
    "ema_50":      ("rel", 0.005),
    "ema_200":     ("rel", 0.005),
    "close":       ("rel", 0.002),
}


# ─── DATA EXTRACTION ──────────────────────────────────────────────────────────

def _extract(symbol: str, mode: str) -> tuple[dict, str | None]:
    """
    Load data via micro_engine and extract last-bar indicator values
    for the primary (slow) timeframe of the given mode.

    Returns ({timeframe, symbol, mode, values}, error_str | None).
    """
    tfs = micro_engine.load_and_prepare(symbol, mode)
    if not tfs or "error" in tfs:
        msg = tfs.get("error", "no data returned") if tfs else "load_and_prepare returned None"
        return {}, f"Data load failed: {msg}"

    tf_keys = micro_engine.MODE_CONFIG.get(mode, {}).get("timeframes", [])
    if not tf_keys:
        return {}, f"No timeframes configured for mode '{mode}'"

    primary_tf = tf_keys[0]
    df = tfs.get(primary_tf)
    if df is None or df.empty:
        return {}, f"No data for primary timeframe {primary_tf}"

    last   = df.iloc[-1]
    values = {}
    for field in FIELDS:
        v = last.get(field)
        if v is not None and not (isinstance(v, float) and math.isnan(v)):
            values[field] = round(float(v), 4)

    return {
        "symbol":    symbol,
        "mode":      mode,
        "timeframe": primary_tf,
        "values":    values,
    }, None


# ─── BASELINE I/O ─────────────────────────────────────────────────────────────

def _baseline_path(symbol: str, mode: str) -> str:
    safe = symbol.upper().replace("/", "").replace("-", "")
    return os.path.join(CALIBRATION_DIR, f"{safe}_{mode}_baseline.json")


def _load_baseline(symbol: str, mode: str) -> dict | None:
    path = _baseline_path(symbol, mode)
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _save_baseline(symbol: str, mode: str, data: dict) -> str:
    os.makedirs(CALIBRATION_DIR, exist_ok=True)
    path = _baseline_path(symbol, mode)
    payload = {
        "symbol":    symbol,
        "mode":      mode,
        "timeframe": data["timeframe"],
        "saved_at":  datetime.now(timezone.utc).isoformat(),
        "note":      (
            "Values computed by Banshee. To use TV ground truth: open TradingView, "
            "run data_get_study_values via MCP, paste the values here."
        ),
        "values": data["values"],
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    return path


# ─── COMPARISON LOGIC ─────────────────────────────────────────────────────────

def _check(field: str, banshee: float, baseline: float) -> tuple[str, float]:
    """Return ('OK  '|'WARN'|'INFO', signed_delta)."""
    thresh = THRESHOLDS.get(field)
    delta  = banshee - baseline

    if thresh is None:
        return "INFO", delta

    kind, limit = thresh
    if kind == "abs":
        flag = "OK  " if abs(delta) <= limit else "WARN"
    else:
        if baseline == 0:
            return "INFO", delta
        flag = "OK  " if abs(delta) / abs(baseline) <= limit else "WARN"

    return flag, delta


# ─── DISPLAY ──────────────────────────────────────────────────────────────────

def _print_solo(data: dict) -> None:
    sym, mode, tf = data["symbol"], data["mode"], data["timeframe"]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    print(f"\n{'=' * 56}")
    print(f"  Banshee Calibration  {sym}  {mode}  ({tf})")
    print(f"  {now}")
    print(f"{'=' * 56}")
    print(f"  {'Metric':<18}  {'Banshee':>14}")
    print(f"  {'-' * 18}  {'-' * 14}")
    for field in FIELDS:
        v = data["values"].get(field)
        if v is None:
            continue
        print(f"  {LABELS[field]:<18}  {v:>14.4f}")
    print(f"{'=' * 56}")
    print(f"  No baseline found. Run --save to store these values,")
    print(f"  then replace 'values' with TV ground truth to enable")
    print(f"  drift detection on future runs.\n")


def _print_comparison(data: dict, baseline: dict) -> None:
    sym, mode, tf = data["symbol"], data["mode"], data["timeframe"]
    b_vals    = data["values"]
    ref_vals  = baseline.get("values", {})
    ref_date  = baseline.get("saved_at", "?")[:10]
    now       = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    warns = 0
    rows  = []
    for field in FIELDS:
        bv = b_vals.get(field)
        if bv is None:
            continue
        rv = ref_vals.get(field)
        if rv is not None:
            flag, delta = _check(field, bv, float(rv))
            if "WARN" in flag:
                warns += 1
            sign = "+" if delta >= 0 else ""
            rows.append((LABELS[field], bv, float(rv), f"{sign}{delta:.4f}", flag))
        else:
            rows.append((LABELS[field], bv, None, "—", "INFO"))

    print(f"\n{'=' * 74}")
    print(f"  Banshee Calibration  {sym}  {mode}  ({tf})")
    print(f"  Banshee: {now}   Baseline: {ref_date}")
    print(f"{'=' * 74}")
    print(f"  {'Metric':<18}  {'Banshee':>12}  {'Baseline':>12}  {'Delta':>10}  Status")
    print(f"  {'-' * 18}  {'-' * 12}  {'-' * 12}  {'-' * 10}  {'-' * 6}")
    for label, bv, rv, delta_s, flag in rows:
        rv_s = f"{rv:.4f}" if rv is not None else "—"
        print(f"  {label:<18}  {bv:>12.4f}  {rv_s:>12}  {delta_s:>10}  {flag}")
    print(f"{'=' * 74}")

    if warns == 0:
        print(f"  RESULT: ALL OK — all indicators within drift thresholds")
    else:
        print(f"  RESULT: {warns} WARNING(s) — review drift; check data source or parameter alignment")
    print()


# ─── ENTRY POINT ──────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Banshee Pro — indicator calibration health check",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python calibrate.py NVDA long_term\n"
            "  python calibrate.py BTC/USD swing\n"
            "  python calibrate.py NVDA long_term --save\n"
        ),
    )
    parser.add_argument("symbol", help="Ticker, e.g. NVDA, BTC/USD, SPY")
    parser.add_argument("mode",   help="long_term | swing | sniper")
    parser.add_argument("--save", action="store_true",
                        help="Save current Banshee values as the new baseline")
    args = parser.parse_args()

    mode = args.mode.lower()
    valid_modes = list(micro_engine.MODE_CONFIG.keys())
    if mode not in valid_modes:
        print(f"ERROR: Unknown mode '{mode}'. Valid: {', '.join(valid_modes)}")
        sys.exit(1)

    print(f"  Fetching {args.symbol} {mode}...", end=" ", flush=True)
    data, err = _extract(args.symbol, mode)
    if err:
        print(f"\nERROR: {err}")
        sys.exit(1)
    print("done")

    if args.save:
        path = _save_baseline(args.symbol, mode, data)
        print(f"  Baseline saved: {path}")
        print(f"  Edit the file to replace 'values' with TV ground truth.\n")

    baseline = _load_baseline(args.symbol, mode)
    if baseline:
        _print_comparison(data, baseline)
    else:
        _print_solo(data)


if __name__ == "__main__":
    main()
