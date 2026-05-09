"""
run_batch.py — Headless MTF Batch Backtest Runner
==================================================
Runs every symbol × mode × lookback × entry-mode combination through
Banshee's real MTF backtest engine, saves results to strategies.json,
and prints a ranked summary table.

Usage:
    python run_batch.py              # run everything in CONFIG below
    python run_batch.py --dry-run    # print the run plan without executing
    python run_batch.py --fresh      # ignore existing results, re-run all
    python run_batch.py --only BTC   # only run symbols containing "BTC"

Resume-safe: already-saved runs are skipped unless --fresh is passed.

Results are saved as  [BATCH] <symbol> <mode> <lookback> <entry_mode>
in strategies.json, identical to a manual Streamlit save.
"""

from __future__ import annotations

import io
import os
import sys
import time
import argparse
import itertools


def _notify_done(succeeded: int, total: int, elapsed_min: float, errors: list):
    """Pop a Windows message box and play a sound when the batch finishes."""
    try:
        import winsound
        winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
    except Exception:
        pass
    try:
        import ctypes
        if errors:
            msg   = f"Batch finished in {elapsed_min:.1f} min\n{succeeded}/{total} succeeded — {len(errors)} error(s)\n\nCheck the terminal for details."
            title = "Banshee Pro — Batch Done (with errors)"
            icon  = 0x30   # MB_ICONWARNING
        else:
            msg   = f"All {succeeded} runs completed in {elapsed_min:.1f} min\n\nResults saved to strategies.json."
            title = "Banshee Pro — Batch Done ✓"
            icon  = 0x40   # MB_ICONINFORMATION
        ctypes.windll.user32.MessageBoxW(0, msg, title, icon | 0x1000)  # 0x1000 = always on top
    except Exception:
        pass

# Force UTF-8 output on Windows (error strings from backtest engine may contain unicode)
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ─── CONFIG — edit this block to control what runs ───────────────────────────

SYMBOLS = [
    # Crypto — BTC
    "BTC/USD",
    # Crypto — Altcoins (use /USDT for Binance priority; /USD as fallback)
    "ETH/USD",
    "SOL/USD",
    "SOL/USDT",
    # Gold proxy
    "PAXG/USD",
    # Equities
    "SPY",
    "NVDA",
]

# Focused subset for VIX-gate validation — only symbols where raw shorts showed
# meaningful signal (BTC 2y bear capture, PAXG trending, ETH borderline)
VIX_GATE_SYMBOLS = [
    "BTC/USD",
    "ETH/USD",
    "PAXG/USD",
]

MODES = [
    "swing",       # 1d / 4h / 1h
    "long_term",   # 1wk / 1d / 4h
    "sniper",      # 4h / 1h / 15m  (needs Binance/Alpaca for crypto; yf 15m capped at 60d)
]

LOOKBACKS = [
    "2 years",
    "5 years",
]

# Each dict is one "entry mode" variant — all three are always run per symbol×mode×lookback
ENTRY_MODES = [
    {
        "label":            "confirmed+pre",
        "include_presignal": True,
        "presignal_only":    False,
        "position_mgmt":     False,
        "allow_shorts":      False,
    },
    {
        "label":            "confirmed+pre+mgmt",
        "include_presignal": True,
        "presignal_only":    False,
        "position_mgmt":     True,
        "allow_shorts":      False,
    },
    {
        "label":            "presignal_only",
        "include_presignal": False,
        "presignal_only":    True,
        "position_mgmt":     False,
        "allow_shorts":      False,
    },
    {
        "label":            "presignal_only+mgmt",
        "include_presignal": False,
        "presignal_only":    True,
        "position_mgmt":     True,
        "allow_shorts":      False,
    },
    # Short-side variants — same long entry rules + short entries on bearish signals
    {
        "label":            "confirmed+pre+shorts",
        "include_presignal": True,
        "presignal_only":    False,
        "position_mgmt":     False,
        "allow_shorts":      True,
    },
    {
        "label":            "confirmed+pre+shorts+mgmt",
        "include_presignal": True,
        "presignal_only":    False,
        "position_mgmt":     True,
        "allow_shorts":      True,
    },
]

# VIX-gated short variants — only fire shorts when VIX ≥ threshold.
# Run via: python run_batch.py --vix-gate
VIX_GATE_ENTRY_MODES = [
    {
        "label":            "confirmed+pre+shorts+vix20",
        "include_presignal": True,
        "presignal_only":    False,
        "position_mgmt":     False,
        "allow_shorts":      True,
        "vix_short_gate":    20.0,
    },
    {
        "label":            "confirmed+pre+shorts+vix20+mgmt",
        "include_presignal": True,
        "presignal_only":    False,
        "position_mgmt":     True,
        "allow_shorts":      True,
        "vix_short_gate":    20.0,
    },
    {
        "label":            "confirmed+pre+shorts+vix25",
        "include_presignal": True,
        "presignal_only":    False,
        "position_mgmt":     False,
        "allow_shorts":      True,
        "vix_short_gate":    25.0,
    },
    {
        "label":            "confirmed+pre+shorts+vix25+mgmt",
        "include_presignal": True,
        "presignal_only":    False,
        "position_mgmt":     True,
        "allow_shorts":      True,
        "vix_short_gate":    25.0,
    },
    {
        "label":            "confirmed+pre+shorts+vix30",
        "include_presignal": True,
        "presignal_only":    False,
        "position_mgmt":     False,
        "allow_shorts":      True,
        "vix_short_gate":    30.0,
    },
    {
        "label":            "confirmed+pre+shorts+vix30+mgmt",
        "include_presignal": True,
        "presignal_only":    False,
        "position_mgmt":     True,
        "allow_shorts":      True,
        "vix_short_gate":    30.0,
    },
]

# ─── Helpers ──────────────────────────────────────────────────────────────────

def _run_key(symbol, mode, lookback, entry_label):
    """The strategies.json key for one combination."""
    lb_short = lookback.replace(" years", "y").replace(" year", "y").replace(" months", "mo")
    return f"[BATCH] {symbol} {mode} {lb_short} {entry_label}"


def _load_existing_keys():
    """Return the set of strategy names already in strategies.json."""
    from strategy_lab import _load_strategies
    return set(_load_strategies().keys())


def _build_plan(symbols, entry_modes=None, only_filter=None):
    """Return list of (key, symbol, mode, lookback, entry_mode) tuples."""
    if entry_modes is None:
        entry_modes = ENTRY_MODES
    combos = list(itertools.product(symbols, MODES, LOOKBACKS, entry_modes))
    plan = []
    for sym, mode, lb, em in combos:
        if only_filter and only_filter.lower() not in sym.lower():
            continue
        key = _run_key(sym, mode, lb, em["label"])
        plan.append((key, sym, mode, lb, em))
    return plan


def _fmt_stats(stats: dict) -> str:
    """One-line stats summary."""
    return (
        f"ret={stats.get('total_return','?'):>7}  "
        f"B&H={stats.get('bnh_return','?'):>7}  "
        f"α={stats.get('alpha','?'):>7}  "
        f"sharpe={stats.get('sharpe','?'):>5}  "
        f"dd={stats.get('max_dd','?'):>7}  "
        f"wr={stats.get('win_rate','?'):>6}  "
        f"trades={stats.get('n_trades','?'):>4}"
    )


def _ranked_summary(results: list[tuple[str, dict]]):
    """Print all completed runs sorted by Sharpe (best first)."""
    done = [(key, r) for key, r in results if r.get("status") == "done"]
    if not done:
        print("\n  (no successful runs to rank)")
        return

    def _sharpe_key(item):
        s = item[1].get("stats", {}).get("sharpe", "0")
        try:
            return float(s)
        except ValueError:
            return -999.0

    done.sort(key=_sharpe_key, reverse=True)

    print(f"\n{'─' * 80}")
    print(f"  RANKED RESULTS — {len(done)} runs (by Sharpe)")
    print(f"{'─' * 80}")
    for rank, (key, r) in enumerate(done, 1):
        stats = r.get("stats", {})
        print(f"  {rank:>3}. {_fmt_stats(stats)}")
        print(f"       {key}")
    print(f"{'─' * 80}")


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Banshee Pro — headless MTF batch runner")
    parser.add_argument("--dry-run",  action="store_true", help="Show plan without running")
    parser.add_argument("--fresh",    action="store_true", help="Re-run even if result exists")
    parser.add_argument("--only",     type=str,  default=None, help="Filter: only symbols containing this string")
    parser.add_argument("--vix-gate", action="store_true", help="Run VIX-gated shorts subset (BTC/ETH/PAXG only)")
    args = parser.parse_args()

    if args.vix_gate:
        symbols     = VIX_GATE_SYMBOLS
        entry_modes = VIX_GATE_ENTRY_MODES
        run_label   = "VIX-gate"
    else:
        symbols     = SYMBOLS
        entry_modes = ENTRY_MODES
        run_label   = "full"

    plan = _build_plan(symbols, entry_modes=entry_modes, only_filter=args.only)

    if not plan:
        print("No runs match the current config/filter. Nothing to do.")
        sys.exit(0)

    print(f"\nBanshee Pro — MTF Batch Runner  [{run_label}]")
    print(f"  Total combinations : {len(plan)}")
    print(f"  Symbols            : {', '.join(symbols)}")
    print(f"  Modes              : {', '.join(MODES)}")
    print(f"  Lookbacks          : {', '.join(LOOKBACKS)}")
    print(f"  Entry modes        : {len(entry_modes)} variants per combo")
    if args.only:
        print(f"  Filter             : --only {args.only}")
    if args.dry_run:
        print(f"\n  --dry-run: listing planned runs and exiting\n")
        for i, (key, sym, mode, lb, em) in enumerate(plan, 1):
            print(f"  {i:>4}. {key}")
        sys.exit(0)

    # Determine which runs to skip
    existing = set() if args.fresh else _load_existing_keys()
    to_run   = [(key, sym, mode, lb, em) for key, sym, mode, lb, em in plan
                if key not in existing]
    skipped  = len(plan) - len(to_run)

    if skipped:
        print(f"  Skipping {skipped} already-saved runs (use --fresh to override)")
    print(f"  Running {len(to_run)} combinations\n")

    if not to_run:
        print("All runs already saved. Use --fresh to re-run.")
        sys.exit(0)

    # Import the backtest engine (Streamlit import is harmless headlessly)
    from strategy_lab import _run_mtf_backtest, _save_strategy

    results: list[tuple[str, dict]] = []
    errors:  list[tuple[str, str]]  = []
    total   = len(to_run)
    t_start = time.time()

    for idx, (key, symbol, mode, lookback, em) in enumerate(to_run, 1):
        pct  = idx / total * 100
        line = (f"[{idx:>{len(str(total))}}/{total}]  "
                f"{symbol:<12}  {mode:<10}  {lookback:<8}  {em['label']:<24}")
        print(f"  {line}", end="  ", flush=True)

        t0 = time.time()
        try:
            result = _run_mtf_backtest(
                symbol       = symbol,
                mode         = mode,
                lookback     = lookback,
                include_presignal = em["include_presignal"],
                presignal_only    = em["presignal_only"],
                position_mgmt     = em["position_mgmt"],
                allow_shorts      = em.get("allow_shorts", False),
                vix_short_gate    = em.get("vix_short_gate", None),
            )
        except Exception as e:
            elapsed = time.time() - t0
            msg = f"{type(e).__name__}: {e}"
            print(f"ERROR  ({elapsed:.0f}s)  {msg}")
            errors.append((key, msg))
            results.append((key, {"status": "error", "error": msg}))
            continue

        elapsed = time.time() - t0

        if result.get("status") == "error":
            err = result.get("error", "unknown error")
            print(f"SKIP   ({elapsed:.0f}s)  {err}")
            errors.append((key, err))
            results.append((key, result))
            continue

        stats = result.get("stats", {})
        print(
            f"done   ({elapsed:.0f}s)  "
            f"ret={stats.get('total_return','?'):>7}  "
            f"sharpe={stats.get('sharpe','?'):>5}  "
            f"trades={stats.get('n_trades','?'):>4}"
        )

        # Save immediately (don't wait for all to finish — resume-safe)
        _save_strategy(key, {
            **result,
            "symbol":   symbol,
            "mode":     mode,
            "lookback": lookback,
            "type":     "batch",
        })
        results.append((key, result))

    # ── Final summary ─────────────────────────────────────────────────────────
    total_time = time.time() - t_start
    succeeded  = sum(1 for _, r in results if r.get("status") == "done")

    print(f"\n{'═' * 60}")
    print(f"  BATCH COMPLETE in {total_time/60:.1f} min")
    print(f"  {succeeded}/{len(to_run)} runs succeeded")
    if errors:
        print(f"  {len(errors)} errors:")
        for key, msg in errors:
            print(f"    ✗ {key}")
            print(f"      {msg}")
    print(f"{'═' * 60}")

    _ranked_summary(results)
    _notify_done(succeeded, len(to_run), total_time / 60, errors)


if __name__ == "__main__":
    main()
