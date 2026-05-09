"""
geometric_harmonic.py — Geometric Harmonic Engine for Banshee Pro
=================================================================
Multi-scalar Fibonacci arc analysis with DBSCAN confluence clustering.

Given OHLCV data (with ATR), computes:
  - Macro Fibonacci arcs anchored at absolute ATL and ATH
  - Local Fibonacci arcs anchored at ZigZag pivots (144/233/377 bars)
  - Circle-circle intersection singularities (hot zones)
  - DBSCAN-clustered, weighted price levels with directional bias + source confluence

Phase 2 additions:
  - radius_endpoint: shared midpoint anchor (√(ATH×ATL)) surfaced as date + price
  - bias: floor/ceiling/mixed tag per hot zone (ATH-sourced=ceiling, ATL-sourced=floor)
  - arithmetic_mid: toggle to use (ATH+ATL)/2 instead of √(ATH×ATL) as radius endpoint
  - multi_window: run all 3 ZigZag windows; hot zones require 2+ distinct source confluence

Design spec: ~/AntiEverything/Banshee_Pro_4/ACTIVE_TASK.md (Geometric Harmonic section)
"""

import numpy as np
import pandas as pd

try:
    from sklearn.cluster import DBSCAN
    _HAS_SKLEARN = True
except ImportError:
    _HAS_SKLEARN = False

FIB_RATIOS    = [0.236, 0.382, 0.500, 0.618, 0.786, 1.000, 1.272, 1.618, 2.000, 2.618]
LOCAL_WINDOWS = [144, 233, 377]


# ── Helpers ────────────────────────────────────────────────────────────────────

def _zigzag_pivots(df: pd.DataFrame, n: int) -> dict:
    """Highest high and lowest low in the last n bars (or whole df if shorter)."""
    window = df.iloc[-n:] if len(df) >= n else df
    hi_iloc = int(window["high"].values.argmax())
    lo_iloc = int(window["low"].values.argmin())
    hi_abs  = window.index[hi_iloc]
    lo_abs  = window.index[lo_iloc]
    ts_col  = "timestamp"
    return {
        "high": {
            "bar":   int(hi_abs),
            "price": float(window.loc[hi_abs, "high"]),
            "ts":    str(df.loc[hi_abs, ts_col]) if ts_col in df.columns else str(hi_abs),
        },
        "low": {
            "bar":   int(lo_abs),
            "price": float(window.loc[lo_abs, "low"]),
            "ts":    str(df.loc[lo_abs, ts_col]) if ts_col in df.columns else str(lo_abs),
        },
    }


def _arc_at_x(cx: float, cy: float, r: float, x: float) -> list:
    """Y-values where circle (cx, cy, r) crosses the vertical line x = x."""
    disc = r * r - (x - cx) ** 2
    if disc < 0:
        return []
    sq = float(np.sqrt(max(disc, 0.0)))
    return [cy - sq, cy + sq] if sq > 1e-10 else [cy]


def _circle_intersections(cx1, cy1, r1, cx2, cy2, r2) -> list:
    """Return 0, 1, or 2 intersection points of two circles (standard derivation)."""
    d = float(np.hypot(cx2 - cx1, cy2 - cy1))
    if d < 1e-12 or d > r1 + r2 + 1e-9 or d < abs(r1 - r2) - 1e-9:
        return []
    a  = (r1 * r1 - r2 * r2 + d * d) / (2.0 * d)
    h2 = r1 * r1 - a * a
    if h2 < 0:
        return []
    h  = float(np.sqrt(max(h2, 0.0)))
    mx = cx1 + a * (cx2 - cx1) / d
    my = cy1 + a * (cy2 - cy1) / d
    if h < 1e-10:
        return [(mx, my)]
    dx = h * (cy2 - cy1) / d
    dy = h * (cx2 - cx1) / d
    return [(mx + dx, my - dy), (mx - dx, my + dy)]


def _simple_cluster(all_points: list, eps: float) -> list:
    """Greedy fallback clustering when sklearn is unavailable."""
    buckets: list = []
    for pt in all_points:
        merged = False
        for b in buckets:
            if abs(pt["price"] - np.mean([x["price"] for x in b])) <= eps:
                b.append(pt)
                merged = True
                break
        if not merged:
            buckets.append([pt])
    return [b for b in buckets if len(b) >= 2]


# ── Public API ─────────────────────────────────────────────────────────────────

def run(df: pd.DataFrame, n_local: int = 233,
        arithmetic_mid: bool = False, multi_window: bool = True) -> dict:
    """
    Run geometric harmonic analysis on a daily OHLCV DataFrame.

    Args:
        df:             DataFrame with columns: timestamp, open, high, low, close[, atr]
        n_local:        Active local ZigZag window when multi_window=False (144|233|377)
        arithmetic_mid: Use (ATH+ATL)/2 as radius endpoint instead of √(ATH×ATL)
        multi_window:   Run all 3 ZigZag windows; surface only levels confirmed by 2+ sources

    Returns dict with:
        current_price, sc_macro, anchors, radius_endpoint,
        arc_levels_at_now, hot_zones (with bias + sources),
        zigzag, total_circles, total_singularities
    """
    if df is None or df.empty:
        return {"error": "No data"}
    required = {"high", "low", "close"}
    if not required.issubset(df.columns):
        return {"error": f"Missing columns: {required - set(df.columns)}"}

    df     = df.reset_index(drop=True)
    n_bars = len(df)
    T_now  = n_bars - 1

    # ── 1. Macro anchors (absolute ATL / ATH) ─────────────────────────────────
    T_atl = int(df["low"].idxmin())
    T_ath = int(df["high"].idxmax())
    P_atl = float(df.loc[T_atl, "low"])
    P_ath = float(df.loc[T_ath, "high"])

    if P_atl <= 0 or P_ath <= P_atl or T_ath == T_atl:
        return {"error": "Degenerate ATH/ATL (price ≤ 0 or anchors on same bar)"}

    ln_atl   = np.log(P_atl)
    ln_ath   = np.log(P_ath)
    sc_macro = (ln_ath - ln_atl) / float(abs(T_ath - T_atl))

    def ny(p: float) -> float:
        return float(np.log(max(p, 1e-12)) / sc_macro)

    def dp(y: float) -> float:
        return float(np.exp(y * sc_macro))

    P_now = float(df["close"].iloc[-1])

    # Shared radius endpoint — geometric mean (default) or arithmetic midpoint
    mid_x = float(T_now)
    if arithmetic_mid:
        mid_y = ny((P_ath + P_atl) / 2.0)
    else:
        mid_y = (ny(P_ath) + ny(P_atl)) / 2.0   # = ln(√(ATH×ATL)) / sc_macro
    mid_price = dp(mid_y)

    # Price sanity bounds
    p_lo = P_atl * 0.3
    p_hi = P_ath * 3.0

    # ── 2. Build circles ──────────────────────────────────────────────────────
    circles: list = []

    def _add(cx: float, cy: float, label: str, ctype: str, origin: str, source: str):
        R_base = float(np.hypot(mid_x - cx, mid_y - cy))
        if R_base < 1e-6:
            return
        circles.append({
            "cx":     cx,
            "cy":     cy,
            "radii":  [f * R_base for f in FIB_RATIOS],
            "label":  label,
            "type":   ctype,
            "origin": origin,   # "floor" | "ceiling"
            "source": source,   # "macro_atl" | "macro_ath" | "local_144" | ...
        })

    _add(float(T_atl), ny(P_atl), "ATL", "macro", "floor",   "macro_atl")
    _add(float(T_ath), ny(P_ath), "ATH", "macro", "ceiling", "macro_ath")

    # ── 3. Local ZigZag anchors ───────────────────────────────────────────────
    active_n       = n_local if n_local in LOCAL_WINDOWS else 233
    windows_to_add = LOCAL_WINDOWS if multi_window else [active_n]

    zigzag_records: list = []
    for n in LOCAL_WINDOWS:
        pivots = _zigzag_pivots(df, n)
        for side in ("high", "low"):
            p        = pivots[side]
            is_active = True if multi_window else (n == active_n)
            zigzag_records.append({
                "bar":    p["bar"],
                "price":  p["price"],
                "type":   side,
                "window": n,
                "active": is_active,
                "ts":     p.get("ts", ""),
            })
            if n in windows_to_add:
                origin = "ceiling" if side == "high" else "floor"
                _add(float(p["bar"]), ny(p["price"]),
                     f"Local{n}_{side}", f"local_{side}",
                     origin, f"local_{n}")

    if len(circles) < 2:
        return {"error": "Not enough valid circle anchors"}

    # ── 4. Arc cross-sections at T_now ────────────────────────────────────────
    arc_levels: list = []
    for c in circles:
        cx, cy = c["cx"], c["cy"]
        for i, r in enumerate(c["radii"]):
            for y in _arc_at_x(cx, cy, r, float(T_now)):
                price = dp(y)
                if p_lo <= price <= p_hi:
                    arc_levels.append({
                        "price":    round(price, 6),
                        "type":     c["type"],
                        "label":    c["label"],
                        "fib":      FIB_RATIOS[i],
                        "dist_pct": round((price - P_now) / P_now * 100, 2),
                        "bias":     c["origin"],
                        "source":   c["source"],
                    })

    # ── 5. Circle-circle singularities (intersections) ────────────────────────
    raw_singularities: list = []
    nc = len(circles)
    for i in range(nc):
        for j in range(i + 1, nc):
            c1, c2 = circles[i], circles[j]
            t1, t2 = c1["type"], c2["type"]
            both_macro = ("macro" in t1) and ("macro" in t2)
            one_macro  = ("macro" in t1) or  ("macro" in t2)
            weight = 3 if both_macro else (2 if one_macro else 1)
            wlabel = ("Macro-Macro"  if both_macro
                      else "Macro-Local" if one_macro
                      else "Local-Local")
            sing_bias = c1["origin"] if c1["origin"] == c2["origin"] else "mixed"
            for ri, r1 in enumerate(c1["radii"]):
                for rj, r2 in enumerate(c2["radii"]):
                    pts = _circle_intersections(c1["cx"], c1["cy"], r1,
                                                c2["cx"], c2["cy"], r2)
                    for (px, py) in pts:
                        price = dp(py)
                        if p_lo <= price <= p_hi:
                            raw_singularities.append({
                                "bar":          round(px, 1),
                                "price":        round(price, 6),
                                "weight":       weight,
                                "weight_label": wlabel,
                                "fibs":         [FIB_RATIOS[ri], FIB_RATIOS[rj]],
                                "labels":       [c1["label"], c2["label"]],
                                "dist_pct":     round((price - P_now) / P_now * 100, 2),
                                "bias":         sing_bias,
                                "sources":      {c1["source"], c2["source"]},
                            })

    # ── 6. DBSCAN clustering on arc_levels + singularities ────────────────────
    all_points = (
        [{"price": a["price"], "weight": 1.5 if "macro" in a["type"] else 0.8,
          "bias": a["bias"], "sources": {a["source"]}}
         for a in arc_levels]
        + [{"price": s["price"], "weight": float(s["weight"]),
            "bias": s["bias"], "sources": s["sources"]}
           for s in raw_singularities]
    )

    hot_zones: list = []
    if all_points:
        eps = max(P_now * 0.005, 1e-6)

        if _HAS_SKLEARN and len(all_points) >= 2:
            prices_arr = np.array([[p["price"]] for p in all_points])
            db_labels  = DBSCAN(eps=eps, min_samples=2).fit(prices_arr).labels_
            cluster_map: dict = {}
            for idx, lbl in enumerate(db_labels):
                if lbl >= 0:
                    cluster_map.setdefault(int(lbl), []).append(all_points[idx])
            clusters = list(cluster_map.values())
        else:
            clusters = _simple_cluster(all_points, eps)

        for items in clusters:
            ps  = [it["price"]  for it in items]
            ws  = [it["weight"] for it in items]
            ctr = float(np.average(ps, weights=ws))

            all_sources = set().union(*[it["sources"] for it in items])

            # Multi-window confluence filter: skip zones confirmed by only 1 source
            if multi_window and len(all_sources) < 2:
                continue

            # Directional bias: weighted majority vote (65% threshold)
            floor_w = sum(ws[k] for k, it in enumerate(items) if it["bias"] == "floor")
            ceil_w  = sum(ws[k] for k, it in enumerate(items) if it["bias"] == "ceiling")
            biased  = floor_w + ceil_w
            if biased == 0 or (floor_w / biased < 0.65 and ceil_w / biased < 0.65):
                bias = "mixed"
            elif floor_w >= ceil_w:
                bias = "floor"
            else:
                bias = "ceiling"

            hot_zones.append({
                "price":    round(ctr, 6),
                "weight":   round(sum(ws), 2),
                "count":    len(items),
                "dist_pct": round((ctr - P_now) / P_now * 100, 2),
                "bias":     bias,
                "sources":  sorted(all_sources),
            })
        hot_zones.sort(key=lambda z: z["weight"], reverse=True)

    # ── 7. Anchor timestamps ──────────────────────────────────────────────────
    ts_col = "timestamp"
    ts_atl = str(df.loc[T_atl, ts_col]) if ts_col in df.columns else str(T_atl)
    ts_ath = str(df.loc[T_ath, ts_col]) if ts_col in df.columns else str(T_ath)
    ts_now = str(df[ts_col].iloc[-1])   if ts_col in df.columns else str(T_now)

    return {
        "current_price":       P_now,
        "sc_macro":            round(sc_macro, 8),
        "anchors": {
            "ATL": {"bar": T_atl, "price": P_atl, "ts": ts_atl},
            "ATH": {"bar": T_ath, "price": P_ath, "ts": ts_ath},
        },
        "radius_endpoint": {
            "bar":    T_now,
            "price":  round(mid_price, 6),
            "ts":     ts_now[:10],
            "method": "arithmetic" if arithmetic_mid else "geometric",
        },
        "arc_levels_at_now":   sorted(arc_levels, key=lambda a: abs(a["dist_pct"]))[:24],
        "hot_zones":           hot_zones[:15],
        "zigzag":              zigzag_records,
        "total_circles":       len(circles),
        "total_singularities": len(raw_singularities),
        "n_local":             active_n,
        "multi_window":        multi_window,
        "arithmetic_mid":      arithmetic_mid,
    }


def format_human(result: dict, symbol: str = "") -> str:
    """Format geo-harmonic result as a compact human-readable string for MCP/AI."""
    if "error" in result:
        return f"GEO HARMONIC ERROR: {result['error']}"

    sym   = f"[{symbol}] " if symbol else ""
    price = result.get("current_price", 0)
    mw    = result.get("multi_window", False)
    re    = result.get("radius_endpoint", {})

    mode_str = ("Multi-window (all 144/233/377 bars)" if mw
                else f"Single window ({result.get('n_local', 233)} bars)")

    lines = [
        f"=== {sym}Geometric Harmonic Analysis ===",
        f"Current price: {price:,.4f}  |  Sc_macro: {result.get('sc_macro', 0):.6f}",
        f"Mode: {mode_str}",
        "",
        "── Macro Anchors ──",
    ]
    for key, a in result.get("anchors", {}).items():
        lines.append(f"  {key}: {a['price']:,.4f}  (bar {a['bar']}, {a['ts'][:10]})")

    if re:
        method = re.get("method", "geometric")
        lines.append(
            f"  Radius endpoint ({method}): {re['price']:,.4f}  "
            f"({re.get('ts', '')} — use as TradingView circle anchor)"
        )

    bias_sym = {"floor": "▼ floor", "ceiling": "▲ ceiling", "mixed": "◈ mixed"}
    lines += ["", f"── Hot Zones (top {min(10, len(result.get('hot_zones', [])))} ranked) ──"]
    for i, hz in enumerate(result.get("hot_zones", [])[:10], 1):
        d    = hz["dist_pct"]
        dirn = "above" if d > 0 else "below"
        bs   = bias_sym.get(hz.get("bias", "mixed"), "◈ mixed")
        srcs = ", ".join(hz.get("sources", []))
        lines.append(
            f"  {i:2d}. {hz['price']:>12,.4f}  ({abs(d):.2f}% {dirn})"
            f"  w={hz['weight']:.1f}  n={hz['count']}  {bs}  [{srcs}]"
        )

    lines += ["", "── ZigZag Pivots ──"]
    for z in result.get("zigzag", []):
        if z.get("active"):
            t = "H" if z["type"] == "high" else "L"
            lines.append(
                f"  [{t}·{z['window']}] {z['price']:>12,.4f}"
                f"  bar {z['bar']}  ({z['ts'][:10]})"
            )

    lines += [
        "",
        f"Arc levels at current bar: {len(result.get('arc_levels_at_now', []))}",
        f"Total singularities: {result.get('total_singularities', 0)}",
        f"Circles: {result.get('total_circles', 0)}",
    ]
    return "\n".join(lines)
