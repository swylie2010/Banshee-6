"""
xabcd_scanner.py — XABCD Harmonic Pattern Scanner for Banshee Pro
==================================================================
Detects Gartley, Bat, Alternate Bat, Butterfly, Crab, Deep Crab, Shark, and 5-0
patterns in daily OHLCV data.

Method:
  1. Build an alternating swing high/low sequence via percentage-reversal ZigZag.
  2. For every consecutive 5-point group (X, A, B, C, D), compute leg ratios and
     validate against Scott Carney's Fibonacci ratio tables (±5% tolerance).
  3. Also scan the most recent 4-point groups for *forming* patterns (D not yet
     printed) and compute the Potential Reversal Zone (PRZ) where D is expected.

Ratio columns (per pattern definition):
  AB/XA  — how far B retraces the XA leg
  BC/AB  — how far C retraces the AB leg
  XD/XA  — how far D falls from A relative to XA (the PRZ anchor ratio)
            values > 1 mean D extends past X (Butterfly, Crab)
  CD/BC  — how far D extends/retraces the BC leg
"""

import numpy as np
import pandas as pd

_TOL = 0.05  # ±5% tolerance applied to every ratio bound

# (name, ab_xa, bc_ab, xd_xa, cd_bc)  — None skips that check
_PATTERNS = [
    ("Gartley",       (0.618, 0.618), (0.382, 0.886), (0.786, 0.786), (1.130, 1.618)),
    ("Bat",           (0.382, 0.500), (0.382, 0.886), (0.886, 0.886), (1.618, 2.618)),
    ("Alternate Bat", (0.382, 0.382), (0.382, 0.886), (1.130, 1.130), (2.000, 3.618)),
    ("Butterfly",     (0.786, 0.786), (0.382, 0.886), (1.270, 1.618), (1.618, 2.618)),
    ("Crab",          (0.382, 0.618), (0.382, 0.886), (1.618, 1.618), (2.240, 3.618)),
    ("Deep Crab",     (0.886, 0.886), (0.382, 0.886), (1.618, 1.618), (2.000, 3.618)),
    # Shark: large BC extension past A; D retraces near XA. AB/XA skipped (uses OX leg).
    ("Shark",         None,           (1.130, 1.618), (0.886, 1.130), (1.618, 2.240)),
    # 5-0: B and C are extensions; D at 50% retrace of BC. XD/XA not used.
    ("5-0",           (1.130, 1.618), (1.618, 2.240), None,           (0.500, 0.500)),
]


# ── Helpers ────────────────────────────────────────────────────────────────────

def _in_range(val: float, bounds: tuple, tol: float = _TOL) -> bool:
    lo, hi = bounds
    return lo * (1.0 - tol) <= val <= hi * (1.0 + tol)


def _confidence(ratios: dict, pat: tuple) -> float:
    """Score 0–1: weighted average of how centred each ratio is within its valid range."""
    _, ab_xa, bc_ab, xd_xa, cd_bc = pat
    scores = []
    for key, bounds in [("ab_xa", ab_xa), ("bc_ab", bc_ab), ("xd_xa", xd_xa), ("cd_bc", cd_bc)]:
        if bounds is None or key not in ratios:
            continue
        val = ratios[key]
        mid = (bounds[0] + bounds[1]) / 2.0
        half = max((bounds[1] - bounds[0]) / 2.0 + mid * _TOL, 1e-9)
        scores.append(max(0.0, 1.0 - abs(val - mid) / half))
    return round(float(np.mean(scores)) if scores else 0.0, 3)


def _prz_range(X_p: float, A_p: float, xd_xa: tuple) -> tuple:
    """
    Compute the price range [lo, hi] where D must land for a given XD/XA ratio.
    For bullish (A > X): D = A - ratio * XA (larger ratio → lower D).
    For bearish (A < X): D = A + ratio * XA.
    """
    xa = abs(A_p - X_p)
    lo_r = xd_xa[0] * (1.0 - _TOL)
    hi_r = xd_xa[1] * (1.0 + _TOL)
    if A_p > X_p:  # bullish
        return (A_p - hi_r * xa, A_p - lo_r * xa)
    else:           # bearish
        return (A_p + lo_r * xa, A_p + hi_r * xa)


def _zigzag(df: pd.DataFrame, pct: float) -> list:
    """
    Percentage-reversal ZigZag — price must reverse by pct to lock in a new pivot.
    Returns [[bar_idx, price, 'H'|'L'], ...] in chronological order.
    The final element is always tentative (the current in-progress extreme).
    """
    highs = df["high"].values.astype(float)
    lows  = df["low"].values.astype(float)
    n = len(df)
    pivots: list = []
    if n < 5:
        return pivots

    trend = 0   # 0=initialising, 1=tracking up, -1=tracking down
    up_top = highs[0]; up_bar = 0
    dn_bot = lows[0];  dn_bar = 0

    for i in range(n):
        h, l = highs[i], lows[i]

        if trend == 0:
            if h > up_top: up_top = h; up_bar = i
            if l < dn_bot: dn_bot = l; dn_bar = i
            if dn_bot > 0 and (up_top - dn_bot) / dn_bot >= pct:
                if up_bar > dn_bar:
                    pivots.append([dn_bar, dn_bot, "L"])
                    trend = 1
                else:
                    pivots.append([up_bar, up_top, "H"])
                    trend = -1

        elif trend == 1:
            if h > up_top:
                up_top = h; up_bar = i
            elif up_top > 0 and (up_top - l) / up_top >= pct:
                pivots.append([up_bar, up_top, "H"])
                trend = -1
                dn_bot = l; dn_bar = i

        else:  # trend == -1
            if l < dn_bot:
                dn_bot = l; dn_bar = i
            elif dn_bot > 0 and (h - dn_bot) / dn_bot >= pct:
                pivots.append([dn_bar, dn_bot, "L"])
                trend = 1
                up_top = h; up_bar = i

    # Append the in-progress extreme as a tentative final pivot
    if trend == 1:
        pivots.append([up_bar, float(up_top), "H"])
    elif trend == -1:
        pivots.append([dn_bar, float(dn_bot), "L"])

    return pivots


# ── Public API ─────────────────────────────────────────────────────────────────

def scan(
    df: pd.DataFrame,
    pct: float = 0.03,
    max_confirmed: int = 10,
    max_forming: int = 5,
    confirmed_max_bars_ago: int = 120,
    forming_c_max_bars_ago: int = 60,
    min_confidence: float = 0.35,
) -> dict:
    """
    Scan OHLCV DataFrame for XABCD harmonic patterns.

    Args:
        df:                     Daily OHLCV DataFrame (timestamp, high, low, close).
        pct:                    ZigZag reversal threshold (0.03 = 3%).
        max_confirmed:          Max confirmed patterns to return.
        max_forming:            Max forming patterns to return.
        confirmed_max_bars_ago: Only report confirmed patterns where D is within this many bars.
        forming_c_max_bars_ago: Only report forming patterns where C is this recent.
        min_confidence:         Drop patterns below this confidence score.

    Returns dict with:
        confirmed, forming, zigzag, n_pivots, pct, current_price
    """
    if df is None or df.empty:
        return {"error": "No data"}
    required = {"high", "low", "close"}
    if not required.issubset(df.columns):
        return {"error": f"Missing columns: {required - set(df.columns)}"}

    df = df.reset_index(drop=True)
    n_bars  = len(df)
    P_now   = float(df["close"].iloc[-1])
    ts_col  = "timestamp"

    def _ts(bar: int) -> str:
        if ts_col in df.columns and 0 <= bar < n_bars:
            return str(df.iloc[bar][ts_col])[:10]
        return str(bar)

    pivots = _zigzag(df, pct)
    n_piv  = len(pivots)

    confirmed: list = []
    forming:   list = []

    # ── Confirmed patterns (5-point sequences) ────────────────────────────────
    for i in range(n_piv - 4):
        X, A, B, C, D = pivots[i], pivots[i+1], pivots[i+2], pivots[i+3], pivots[i+4]

        xa = abs(A[1] - X[1])
        ab = abs(B[1] - A[1])
        bc = abs(C[1] - B[1])
        cd = abs(D[1] - C[1])

        if xa < 1e-9 or ab < 1e-9 or bc < 1e-9:
            continue

        ab_xa = ab / xa
        bc_ab = bc / ab
        cd_bc = cd / bc if bc > 1e-9 else 0.0
        xd_xa = abs(D[1] - A[1]) / xa  # distance from A to D, normalised by XA

        d_bars_ago = n_bars - 1 - D[0]
        if d_bars_ago > confirmed_max_bars_ago:
            continue

        direction = "bullish" if X[2] == "L" else "bearish"
        ratios = {"ab_xa": ab_xa, "bc_ab": bc_ab, "cd_bc": cd_bc, "xd_xa": xd_xa}

        for pat in _PATTERNS:
            name, ab_rng, bc_rng, xd_rng, cd_rng = pat
            if ab_rng is not None and not _in_range(ab_xa, ab_rng): continue
            if bc_rng is not None and not _in_range(bc_ab, bc_rng): continue
            if xd_rng is not None and not _in_range(xd_xa, xd_rng): continue
            if cd_rng is not None and not _in_range(cd_bc, cd_rng): continue

            conf = _confidence(ratios, pat)
            if conf < min_confidence:
                continue

            confirmed.append({
                "pattern":    name,
                "direction":  direction,
                "confidence": conf,
                "bars_ago":   d_bars_ago,
                "d_tentative": (i + 4) == (n_piv - 1),
                "points": {
                    "X": {"bar": X[0], "price": round(X[1], 6), "ts": _ts(X[0])},
                    "A": {"bar": A[0], "price": round(A[1], 6), "ts": _ts(A[0])},
                    "B": {"bar": B[0], "price": round(B[1], 6), "ts": _ts(B[0])},
                    "C": {"bar": C[0], "price": round(C[1], 6), "ts": _ts(C[0])},
                    "D": {"bar": D[0], "price": round(D[1], 6), "ts": _ts(D[0])},
                },
                "ratios":   {k: round(v, 4) for k, v in ratios.items()},
                "prz":      round(D[1], 6),
                "dist_pct": round((D[1] - P_now) / P_now * 100, 2),
            })

    # ── Forming patterns (4-point sequences; D not yet printed) ───────────────
    # Check the most recent 4-pivot groups where C is still fresh
    for i in range(max(0, n_piv - 8), n_piv - 3):
        X, A, B, C = pivots[i], pivots[i+1], pivots[i+2], pivots[i+3]

        c_bars_ago = n_bars - 1 - C[0]
        if c_bars_ago > forming_c_max_bars_ago:
            continue

        xa = abs(A[1] - X[1])
        ab = abs(B[1] - A[1])
        bc = abs(C[1] - B[1])
        if xa < 1e-9 or ab < 1e-9 or bc < 1e-9:
            continue

        ab_xa = ab / xa
        bc_ab = bc / ab
        direction = "bullish" if X[2] == "L" else "bearish"
        ratios = {"ab_xa": ab_xa, "bc_ab": bc_ab}

        for pat in _PATTERNS:
            name, ab_rng, bc_rng, xd_rng, cd_rng = pat
            if ab_rng is not None and not _in_range(ab_xa, ab_rng): continue
            if bc_rng is not None and not _in_range(bc_ab, bc_rng): continue

            # Compute PRZ from XD/XA if available; fall back to CD/BC estimate
            prz_lo = prz_hi = None
            if xd_rng is not None:
                prz_lo, prz_hi = _prz_range(X[1], A[1], xd_rng)
            elif cd_rng is not None:
                mid_cd = (cd_rng[0] + cd_rng[1]) / 2.0
                d_est = (C[1] - mid_cd * bc) if direction == "bullish" else (C[1] + mid_cd * bc)
                prz_lo = d_est * (1.0 - _TOL)
                prz_hi = d_est * (1.0 + _TOL)

            conf = _confidence(ratios, pat)
            if conf < min_confidence:
                continue

            prz_mid = round((prz_lo + prz_hi) / 2.0, 6) if prz_lo and prz_hi else None

            forming.append({
                "pattern":    name,
                "direction":  direction,
                "confidence": conf,
                "c_bars_ago": c_bars_ago,
                "points": {
                    "X": {"bar": X[0], "price": round(X[1], 6), "ts": _ts(X[0])},
                    "A": {"bar": A[0], "price": round(A[1], 6), "ts": _ts(A[0])},
                    "B": {"bar": B[0], "price": round(B[1], 6), "ts": _ts(B[0])},
                    "C": {"bar": C[0], "price": round(C[1], 6), "ts": _ts(C[0])},
                },
                "ratios":   {k: round(v, 4) for k, v in ratios.items()},
                "prz_lo":   round(prz_lo, 6) if prz_lo is not None else None,
                "prz_hi":   round(prz_hi, 6) if prz_hi is not None else None,
                "prz_mid":  prz_mid,
                "prz_dist_pct": round((prz_mid - P_now) / P_now * 100, 2) if prz_mid else None,
            })

    # Sort and trim
    confirmed.sort(key=lambda x: (x["bars_ago"], -x["confidence"]))
    confirmed = confirmed[:max_confirmed]

    forming.sort(key=lambda x: (-x["confidence"], x["c_bars_ago"]))
    forming = forming[:max_forming]

    return {
        "confirmed":     confirmed,
        "forming":       forming,
        "zigzag":        [{"bar": p[0], "price": p[1], "type": p[2], "ts": _ts(p[0])}
                          for p in pivots],
        "n_pivots":      n_piv,
        "pct":           pct,
        "current_price": P_now,
    }


def format_human(result: dict, symbol: str = "") -> str:
    """Compact text summary for MCP/AI consumption."""
    if "error" in result:
        return f"XABCD SCANNER ERROR: {result['error']}"

    sym   = f"[{symbol}] " if symbol else ""
    price = result.get("current_price", 0)
    lines = [
        f"=== {sym}XABCD Harmonic Pattern Scan ===",
        f"Current price: {price:,.4f}  |  ZigZag pct: {result.get('pct', 0)*100:.1f}%"
        f"  |  Pivots found: {result.get('n_pivots', 0)}",
    ]

    confirmed = result.get("confirmed", [])
    forming   = result.get("forming",   [])

    dir_sym = {"bullish": "▲", "bearish": "▼"}

    lines.append(f"\n── Confirmed Patterns ({len(confirmed)}) ──")
    if not confirmed:
        lines.append("  None within lookback window.")
    for p in confirmed:
        d = p["prz"]; dist = p["dist_pct"]
        dirn = "above" if dist > 0 else "below"
        tent = " [tentative D]" if p.get("d_tentative") else ""
        lines.append(
            f"  {dir_sym.get(p['direction'], '?')} {p['pattern']:14s} {p['direction']:8s}"
            f"  PRZ={d:>12,.4f}  ({abs(dist):.1f}% {dirn})"
            f"  conf={p['confidence']:.2f}  D was {p['bars_ago']} bars ago{tent}"
        )
        r = p["ratios"]
        lines.append(
            f"    AB/XA={r.get('ab_xa','N/A')}  BC/AB={r.get('bc_ab','N/A')}"
            f"  XD/XA={r.get('xd_xa','N/A')}  CD/BC={r.get('cd_bc','N/A')}"
        )

    lines.append(f"\n── Forming Patterns ({len(forming)}) ──")
    if not forming:
        lines.append("  None in recent swing structure.")
    for p in forming:
        lo, hi, mid = p.get("prz_lo"), p.get("prz_hi"), p.get("prz_mid")
        dist = p.get("prz_dist_pct")
        if lo and hi:
            dirn = "above" if (dist or 0) > 0 else "below"
            prz_str = f"PRZ {lo:,.4f}–{hi:,.4f}  ({abs(dist or 0):.1f}% {dirn})"
        else:
            prz_str = "PRZ unknown"
        lines.append(
            f"  {dir_sym.get(p['direction'], '?')} {p['pattern']:14s} {p['direction']:8s}"
            f"  {prz_str}"
            f"  conf={p['confidence']:.2f}  C was {p['c_bars_ago']} bars ago"
        )
        pts = p["points"]
        lines.append(
            f"    X={pts['X']['price']:,.4f}({pts['X']['ts']})  "
            f"A={pts['A']['price']:,.4f}({pts['A']['ts']})  "
            f"B={pts['B']['price']:,.4f}({pts['B']['ts']})  "
            f"C={pts['C']['price']:,.4f}({pts['C']['ts']})"
        )

    return "\n".join(lines)
