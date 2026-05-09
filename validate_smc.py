#!/usr/bin/env python3
"""
validate_smc.py — Run smc_engine.run() on cached TV OHLCV data and print
a human-readable summary for visual comparison against the TradingView chart.

Usage:
    python validate_smc.py                          # BTC 1D (default)
    python validate_smc.py BTCUSD 4H
    python validate_smc.py NVDA 1D
    python validate_smc.py SPY 4H
"""

import json
import os
import sys
import pandas as pd
from datetime import datetime, timezone

# ── locate TV OHLCV files ─────────────────────────────────────────────────────
BASE  = os.path.dirname(os.path.abspath(__file__))
OHLCV = os.path.join(BASE, "tv_extract", "ohlcv")

sys.path.insert(0, BASE)
import smc_engine


def load_tv_ohlcv(symbol: str, tf: str) -> pd.DataFrame:
    """Find and load the most recent TV OHLCV JSON for symbol+timeframe."""
    candidates = [
        f for f in os.listdir(OHLCV)
        if f.startswith(symbol.upper()) and f"_{tf.upper()}_" in f and f.endswith(".json")
        and "META" not in f
    ]
    if not candidates:
        raise FileNotFoundError(
            f"No TV OHLCV file for {symbol} {tf} in {OHLCV}\n"
            f"Available: {sorted(os.listdir(OHLCV))}"
        )
    candidates.sort(reverse=True)          # latest date first
    path = os.path.join(OHLCV, candidates[0])
    print(f"Loading: {candidates[0]}  ({path})")

    with open(path, encoding="utf-8") as f:
        raw = json.load(f)

    bars = raw["bars"]
    df   = pd.DataFrame(bars)
    df.rename(columns={"time": "timestamp"}, inplace=True)
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="s", utc=True)
    df = df[["timestamp", "open", "high", "low", "close", "volume"]].copy()
    df.reset_index(drop=True, inplace=True)
    return df


def fmt_ts(ts) -> str:
    try:
        return pd.Timestamp(ts).strftime("%Y-%m-%d")
    except Exception:
        return str(ts)


def fmt_price(p: float) -> str:
    return f"{p:,.2f}"


def print_section(title: str) -> None:
    print(f"\n{'-' * 60}")
    print(f"  {title}")
    print(f"{'-' * 60}")


def main() -> None:
    symbol = sys.argv[1] if len(sys.argv) > 1 else "BTCUSD"
    tf     = sys.argv[2] if len(sys.argv) > 2 else "1D"

    df = load_tv_ohlcv(symbol, tf)
    print(f"Bars loaded: {len(df)}   |   Range: {fmt_ts(df['timestamp'].iloc[0])} -> {fmt_ts(df['timestamp'].iloc[-1])}")
    print(f"Last close:  {fmt_price(df['close'].iloc[-1])}")

    result = smc_engine.run(df)
    if "error" in result:
        print(f"\nERROR: {result['error']}")
        sys.exit(1)

    # ── ATR ───────────────────────────────────────────────────────────────────
    atr_val = None
    for v in reversed(result["atr"].values):
        if v == v:   # not NaN
            atr_val = float(v)
            break

    print_section("MARKET STATE")
    print(f"  Current state : {result['current_state']}")
    if atr_val:
        print(f"  ATR (last bar): {fmt_price(atr_val)}")

    # ── Swing summary ─────────────────────────────────────────────────────────
    print_section(f"SWING POINTS  ({len(result['swing_highs'])} highs, {len(result['swing_lows'])} lows)")
    print("  Last 5 swing highs:")
    for sh in result["swing_highs"][-5:]:
        print(f"    {fmt_ts(sh['timestamp'])}  HIGH  {fmt_price(sh['price'])}  [{sh['label']}]")
    print("  Last 5 swing lows:")
    for sl in result["swing_lows"][-5:]:
        print(f"    {fmt_ts(sl['timestamp'])}  LOW   {fmt_price(sl['price'])}  [{sl['label']}]")

    # ── Structure events ──────────────────────────────────────────────────────
    events = result["structure_events"]
    print_section(f"STRUCTURE EVENTS  (total: {len(events)})")
    for ev in events[-10:]:
        print(f"  {fmt_ts(ev['timestamp'])}  {ev['event_type']:<14}  level={fmt_price(ev['price'])}  -> {ev['state_after']}")

    # ── P/D zones ─────────────────────────────────────────────────────────────
    pd_z = result.get("pd_zones")
    if pd_z:
        print_section("PREMIUM / DISCOUNT ZONES")
        print(f"  Dealing range : {fmt_price(pd_z['range_low'])} -> {fmt_price(pd_z['range_high'])}")
        print(f"  Equilibrium   : {fmt_price(pd_z['equilibrium'])}")
        print(f"  OTE zone      : {fmt_price(pd_z['ote_bottom'])} -> {fmt_price(pd_z['ote_top'])}")

    # ── FVGs ──────────────────────────────────────────────────────────────────
    fvgs = result.get("fvgs", [])
    active_fvgs = [f for f in fvgs if f["status"] != "mitigated"]
    print_section(f"FAIR VALUE GAPS  (total: {len(fvgs)}, active/partial: {len(active_fvgs)})")
    for fvg in active_fvgs[-8:]:
        print(f"  {fmt_ts(fvg['timestamp'])}  {fvg['kind']:<8}  {fmt_price(fvg['bottom'])} to {fmt_price(fvg['top'])}  [{fvg['status']}]")

    # ── Order Blocks ───────────────────────────────────────────────────────────
    obs          = result.get("order_blocks", [])
    live_obs      = [o for o in obs if o.get("gate_passed", True)]
    candidate_obs = [o for o in obs if not o.get("gate_passed", True)
                     and o["status"] not in ("sapped", "invalidated")]
    active_live   = [o for o in live_obs if o["status"] in ("active", "touched", "degraded")]

    print_section(f"ORDER BLOCKS -- LIVE  (total: {len(live_obs)}, active/touched/degraded: {len(active_live)})")
    for ob in live_obs[-8:]:
        ind = ""
        if ob.get("inducement_swept"):
            ind = " [IND SWEPT *]"
        elif ob.get("has_pending_inducement"):
            ind = " [IND PENDING]"
        htf = ", ".join(h["name"] for h in ob.get("htf_confluence", []))
        htf_str = f"  HTF: {htf}" if htf else ""
        print(f"  {fmt_ts(ob['timestamp'])}  {ob['kind']:<8}  {fmt_price(ob['zone_bottom'])} to {fmt_price(ob['zone_top'])}  [{ob['status']}]{ind}{htf_str}")

    print_section(f"ORDER BLOCKS -- CANDIDATES  (gate-blocked, no swept inducement: {len(candidate_obs)})")
    if candidate_obs:
        for ob in candidate_obs[-8:]:
            htf = ", ".join(h["name"] for h in ob.get("htf_confluence", []))
            htf_str = f"  HTF: {htf}" if htf else ""
            print(f"  {fmt_ts(ob['timestamp'])}  {ob['kind']:<8}  {fmt_price(ob['zone_bottom'])} to {fmt_price(ob['zone_top'])}  [{ob['status']}]  [INACTIVE/UNCONSOLIDATED]{htf_str}")
    else:
        print("  (none)")

    # ── Liquidity pools ────────────────────────────────────────────────────────
    pools = result.get("liquidity_pools", [])
    live_pools = [p for p in pools if not p["swept"]]
    print_section(f"LIQUIDITY POOLS  (total: {len(pools)}, unswept: {len(live_pools)})")
    for p in live_pools[-8:]:
        print(f"  {p['kind'].upper():<4}  level={fmt_price(p['level'])}  (idx {p['idx_1']} & {p['idx_2']})")

    print(f"\n{'-' * 60}")
    print(f"  Done. Current session weight: {result.get('current_session_weight', '?')}")
    print(f"{'-' * 60}\n")


if __name__ == "__main__":
    main()
