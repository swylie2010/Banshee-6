#!/usr/bin/env python
"""check_deep.py — fast-vs-deep data diagnostic for the fast-then-complete upgrade.

Hits GET /ohlcv (fast Stage-1 path) and GET /ohlcv?deep=1 (Stage-2 deep poll) for
each symbol and prints, per timeframe, the bar count + last-bar timestamp of each,
plus the verdict the FRONTEND would reach (silent swap / badge / no-op).

The point: the deep upgrade is invisible by design (silent when it helps, inert when
it can't). This makes it visible. Run it any time you wonder "is the deep upgrade
actually doing anything right now, with the providers I have enabled?"

    .venv/Scripts/python check_deep.py                # default symbols
    .venv/Scripts/python check_deep.py BTC/USD AAPL   # your own

Reads the soul token from ~/.banshee_keys.json. Core must be running on :8765.
"""
import sys
import json
import pathlib
import urllib.parse
import urllib.request

BASE = "http://localhost:8765"
DEFAULT_SYMBOLS = ["BTC/USD", "ETH/USD", "AAPL", "SPY"]
SILENT_SWAP_DELTA = 0.005  # matches the frontend threshold in ui/parts.jsx


def _token() -> str:
    return json.loads((pathlib.Path.home() / ".banshee_keys.json").read_text())["banshee_token"]


def _fetch(symbol: str, mode: str, deep: bool, tok: str) -> dict:
    q = urllib.parse.urlencode({"symbol": symbol, "mode": mode, "deep": 1 if deep else 0})
    req = urllib.request.Request(f"{BASE}/ohlcv?{q}", headers={"X-Banshee-Token": tok})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read())


def _summarize(payload: dict) -> dict:
    """tf -> (bar_count, last_timestamp, last_close)."""
    out = {}
    for tf, recs in (payload.get("tfs") or {}).items():
        if recs:
            last = recs[-1]
            out[tf] = (len(recs), str(last.get("timestamp", ""))[:16], last.get("close"))
    return out


def _verdict(fast: tuple, deep: tuple) -> str:
    """Reproduce the frontend's Stage-2 decision so the diagnostic matches real behavior."""
    if not deep:
        return "no deep result -> no-op"
    fb, fl, fc = fast if fast else (0, "-", None)
    db, dl, dc = deep
    deeper = db > fb
    fresher = dl > fl
    if not deeper and not fresher:
        return "same -> no-op"
    delta = abs((dc or 0) - (fc or 0)) / fc if fc else 0
    if delta >= SILENT_SWAP_DELTA:
        return f"BADGE (price delta {delta*100:.2f}%)"
    if deeper:
        return f"SILENT SWAP (+{db - fb} bars)"
    return "fresher-but-not-deeper -> no-op (never shrink)"


def main() -> None:
    symbols = sys.argv[1:] or DEFAULT_SYMBOLS
    tok = _token()
    for symbol in symbols:
        for mode in ("swing", "long"):
            try:
                fast = _summarize(_fetch(symbol, mode, False, tok))
                deep = _summarize(_fetch(symbol, mode, True, tok))
            except Exception as e:  # noqa: BLE001 — diagnostic, surface anything
                print(f"\n{symbol} [{mode}]  ERROR: {e}")
                continue
            print(f"\n=== {symbol}  mode={mode} ===")
            print(f"  {'TF':5} {'FAST bars / last':26} {'DEEP bars / last':26} verdict")
            for tf in sorted(set(fast) | set(deep)):
                f = fast.get(tf)
                d = deep.get(tf)
                fstr = f"{f[0]} / {f[1]}" if f else "- / -"
                dstr = f"{d[0]} / {d[1]}" if d else "- / -"
                print(f"  {tf:5} {fstr:26} {dstr:26} {_verdict(f, d)}")


if __name__ == "__main__":
    main()
