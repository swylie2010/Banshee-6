# GH Pine Script Generator — Design Spec
**Date:** 2026-05-29  
**Feature:** Banshee Phase 7 #11 — Pine Script generator for Geo Harmonic circles  
**Status:** Approved

---

## Goal

Banshee computes Fibonacci arc circles in normalized log space. This feature generates a paste-ready Pine Script v5 indicator that draws those same circles directly on a TradingView 1D chart as polylines — no manual placement required.

Division of labor: Banshee is the brain (math + coordinates), Pine Script is the renderer (visual).

---

## Architecture

Four files change:

| File | Change |
|---|---|
| `geometric_harmonic.py` | Add `generate_pine_script(result, symbol)` → `str` |
| `banshee_core.py` | Add `GET /geo-harmonic/pine?symbol=X` endpoint |
| `mcp_server.py` | Add `generate_gh_pine(symbol)` MCP tool |
| `ui/app.jsx` | Add "PINE" button on GH tab; render copyable code block |

No new files. No changes to `run()` output schema.

---

## `generate_pine_script(result: dict, symbol: str = "") -> str`

Location: `geometric_harmonic.py`, alongside `run()` and `format_human()`.

**Inputs** (all from existing `run()` result — no new fields needed):
- `result["sc_macro"]` → `SC_MACRO` constant
- `result["radius_endpoint"]["bar"]` → `T_NOW` (used to compute `bars_ago = T_NOW - cx_bar`)
- `result["gh_circles"]` → list of `{cx_bar, center_price, r_base, origin, label}` per circle
- `result["anchors"]` → ATL/ATH dates for header comment only

**Returns:** A complete Pine Script v5 string, ready to paste into TradingView's Pine Editor.

---

## Pine Script Structure

```
//@version=5
indicator("Banshee GH — {symbol}", overlay=true, max_polylines_count=100)
// Generated: {date} | 1D CHART ONLY | Log scale
// ATL: {date} @ {price} | ATH: {date} @ {price}

// ── Hardcoded parameters ───────────────────────────────────────────────────
SC_MACRO = {sc_macro}
FIB_LEVELS = array.from(0.382, 0.500, 0.618, 0.786, 1.000, 1.618)

// ── Circle definitions ─────────────────────────────────────────────────────
// Each row: [bars_ago, center_price, r_base, is_floor, is_macro, label]
// (all values baked in from Banshee run)

if barstate.islast
    // For each circle × each Fib level:
    //   1. Compute cy_norm = log(center_price) / SC_MACRO
    //   2. r_fib = r_base × fib
    //   3. For theta in 0..2π (60 steps):
    //        x_abs  = bar_index - bars_ago + r_fib × cos(theta)
    //        y_norm = cy_norm + r_fib × sin(theta)
    //        price  = exp(y_norm × SC_MACRO)
    //        if x_abs >= 0: add chart.point.from_index(int(x_abs), price)
    //   4. polyline.new(points, curved=false, line_color=color, line_width=1)
```

**Fib levels:** 6 levels — `0.382, 0.500, 0.618, 0.786, 1.000, 1.618`

**Circle count:** Up to 8 (ATL + ATH + 6 local ZigZag pivots). 8 × 6 = 48 polylines max — within TV's 100-polyline limit.

**Points per arc:** 60 — smooth enough, minimal performance cost.

**Color scheme:**
- Macro floor (ATL-anchored): teal, full opacity
- Macro ceiling (ATH-anchored): red, full opacity
- Local floor pivots: teal, 60% opacity
- Local ceiling pivots: red, 60% opacity

**Guard:** Skip any polyline point where `x_abs < 0` (before chart history start). This prevents runtime errors on assets with short TV history.

**Constraint:** Script only renders correctly on a **1D chart**. The header comment and a `runtime.error` guard (checking `timeframe.period != "D"`) will warn the user if they load it on a wrong timeframe.

---

## Endpoint

```
GET /geo-harmonic/pine?symbol=BTC%2FUSD&arithmetic_mid=false
```

Response:
```json
{
  "symbol": "BTC/USD",
  "pine_script": "//@version=5\n..."
}
```

Implementation: calls `run()` (reusing existing daily OHLCV fetch logic) then `generate_pine_script()`. Mirrors the existing `/geo-harmonic` endpoint pattern.

---

## MCP Tool

```python
@mcp.tool()
def generate_gh_pine(symbol: str, arithmetic_mid: bool = False) -> str:
    """
    Generate a paste-ready Pine Script v5 indicator that draws Banshee's
    Geo Harmonic Fibonacci arc circles on a TradingView 1D chart.
    Returns the full Pine Script as a string.
    """
```

Calls the `/geo-harmonic/pine` Core endpoint internally (same pattern as other MCP tools).

---

## UI Change

**Location:** `ui/app.jsx`, GH tab inside `AnalysisPage`

**Trigger:** "PINE" button (amber, same style as AI analysis buttons) placed below the existing GH zone table.

**Behavior:**
1. Click → POST to `/geo-harmonic/pine?symbol={sym}`
2. While loading: button shows "PINE ◇ loading…"
3. On success: a `<pre>` code block appears below the button containing the full script
4. A "Copy" button copies the script to clipboard
5. Script persists until the user changes symbol (same pattern as AI briefing panels)

---

## Error Handling

- `run()` returns `{"error": "..."}` → `generate_pine_script()` returns a Pine Script that shows a `runtime.error()` label with the message
- Empty `gh_circles` list → same error path
- Endpoint fails → UI shows inline error message (same pattern as other fetch failures)

---

## What This Is Not

- Not a real-time updating indicator — the values are baked in at generation time. Re-run Banshee and re-paste when prices move significantly.
- Not for sub-daily charts — the bar-index math assumes 1D spacing.
- Not configurable via Pine Script `input()` — all params are hardcoded for paste-and-run simplicity.
