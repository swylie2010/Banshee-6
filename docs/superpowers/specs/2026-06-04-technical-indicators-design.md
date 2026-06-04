# Technical Indicators on Chart — Design Spec
_Date: 2026-06-04_

## Overview

Restore EMA 50/200, VWAP, and Stoch RSI overlays on the Banshee 5 React chart. These existed in V4 (Streamlit/Plotly). All indicator data is already computed by `micro_engine.py` and already included in the `/ohlcv` response — the frontend is simply not extracting or rendering it yet.

Applies to: **both** the AssetHub main chart and the Nexus tab chart.

---

## Architecture

Three-layer change — no backend modifications required.

### Layer 1: Data extraction (`api.js`)

`fetchOHLCV` already receives raw records containing `ema_50`, `ema_200`, `vwap`, `stoch_k`, `stoch_d` columns. `toLWCandles()` currently discards them.

Add `toIndicatorSeries(records, field)` helper — filters nulls/NaN, maps to LW Charts `{ time, value }` format, sorts by time. Pure column extraction; no knowledge of data source.

Extend `fetchOHLCV` return shape (backwards-compatible — callers that only use `candles` are unaffected):

```js
{
  candles: [...],           // existing
  indicators: {             // new
    ema50:  [{ time, value }, ...],
    ema200: [{ time, value }, ...],
    vwap:   [{ time, value }, ...],
    stochK: [{ time, value }, ...],
    stochD: [{ time, value }, ...],
  },
  source: "live" | "mock"  // existing
}
```

Mock fallback returns `indicators: null`. Chart handles null by skipping all indicator rendering.

**Source-agnostic note:** `toIndicatorSeries` reads column names only — no yfinance dependency. When `shared_data.py` gains a pluggable fetcher layer for custom data sources, indicators ride along automatically as long as the fetcher produces a standard OHLCV+volume DataFrame that `micro_engine.py` can process.

---

### Layer 2: Chart component (`parts.jsx`)

**New props:**
```
indicatorData        — { ema50, ema200, vwap, stochK, stochD } | null
showEMA / setShowEMA
showVWAP / setShowVWAP
showStoch / setShowStoch
```

**Series management — three new `useEffect` hooks** (same create/destroy pattern as SMC/GH/XABCD):

| Effect deps | Pane | Series | Color |
|---|---|---|---|
| `[indicatorData, showEMA]` | 0 (main) | EMA 50 line | `#42A5F5` blue |
| `[indicatorData, showEMA]` | 0 (main) | EMA 200 line | `#EF5350` red |
| `[indicatorData, showVWAP]` | 0 (main) | VWAP dashed line | `#AB47BC` purple, `lineStyle: 2` |
| `[indicatorData, showStoch]` | 1 (sub-pane) | Stoch %K line | `#42A5F5` blue |
| `[indicatorData, showStoch]` | 1 (sub-pane) | Stoch %D dashed | `#EF5350` red, `lineStyle: 2` |

Sub-pane created via `pane: 1` on `addLineSeries()` — supported in LW Charts v4.2. Pane appears only when Stoch is toggled on; disappears when toggled off (series removed).

**Toggle buttons** — three new badges in the existing SMC/GH/XABCD toggle row:
- `EMA ◆` / `EMA ○`
- `VWAP ◆` / `VWAP ○`
- `STOCH ◆` / `STOCH ○`

Same styling as existing overlay toggles (same font, same active/inactive color logic).

**Default states:** EMA on, VWAP on, Stoch off. Stoch is opt-in because the sub-pane reduces candle chart height.

---

### Layer 3: Parent wiring (`app.jsx`)

Both AssetHub and Nexus already call `fetchOHLCV` for candles. Change: destructure `indicators` from the same response and store in `indicatorData` state alongside existing candle state. No new fetches, no new triggers — `indicatorData` updates automatically on any symbol/TF change that already triggers a candle refetch.

Each chart instance (AssetHub, Nexus) maintains **independent** toggle state — toggling Stoch on Nexus does not affect AssetHub and vice versa. This is the correct behavior: a trader may want Stoch visible during deep analysis but not on the quick asset view.

---

## What is NOT changing

- `micro_engine.py` — no changes. EMA/VWAP/StochRSI already computed.
- `banshee_core.py` — no changes. `/ohlcv` already serializes full DataFrame.
- SMC / GH / XABCD overlays — untouched. Purely additive change.

---

## Indicator notes

- **EMA 50 / EMA 200** — computed as standard exponential moving averages on `close`. The cross between them is the primary read (50 above 200 = uptrend structure).
- **VWAP** — rolling 20-period volume-weighted average price. Acts as fair-value anchor. Price above = bullish bias; below = bearish.
- **Stoch RSI** — RSI smoothed through a Stochastic formula. Outputs %K (fast) and %D (slow, signal). Same as V4. Range 0–100; >80 = overbought, <20 = oversold.

---

## Estimated scope

~60 lines of new code across three files. No backend work. No new dependencies.

| File | Change |
|---|---|
| `ui/api.js` | +`toIndicatorSeries()`, extend `fetchOHLCV` return |
| `ui/parts.jsx` | +6 new props, +3 useEffects, +3 toggle buttons |
| `ui/app.jsx` | +`indicatorData` state × 2 charts, +toggle states × 2 × 3 |
