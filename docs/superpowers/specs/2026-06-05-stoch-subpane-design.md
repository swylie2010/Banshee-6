# Stoch RSI Sub-Pane Fix — Design Spec
**Date:** 2026-06-05  
**Status:** Approved

## Problem

The current Stoch RSI implementation uses LW Charts' `pane: 1` option, which splits the total chart `height` equally between the candlestick pane and the Stoch pane. At 420px total, both panes get 210px — cramped for candles, oversized for an oscillator. At 260px (Nexus), it becomes unusable.

## Solution

Render the Stoch RSI as a separate fixed-height (100px) LW Charts instance below the main chart, with synchronized time-scale and crosshair. This is the same approach TradingView uses for its sub-indicator panels.

## Scope

- **AnalysisPage chart** (420px) — fix applies  
- **Nexus tab chart** (260px) — fix applies  
- **AssetHub mini-chart** (300px) — excluded; `showStoch={false}` is hardcoded there and the sub-pane will never appear

## Layout

The `Chart` component's return changes from a single `position: relative` div to a flex column wrapper:

```
┌────────────────────────────────────────┐  ← position: relative (overlay buttons live here)
│  Main LW chart  (containerRef)         │  height prop — 420px or 260px, unchanged
└────────────────────────────────────────┘
┌────────────────────────────────────────┐  ← only rendered when showStoch && data present
│  Stoch sub-chart  (stochContainerRef)  │  100px fixed
│  %K (blue) · %D (red dashed)           │
│  20 / 80 reference lines (dim)         │
└────────────────────────────────────────┘
```

- The `height` prop continues to describe the main candle area only — callers don't change.
- The Stoch div uses `display: none` when toggled off so it collapses with no empty gap.
- The overlay buttons (SMC/GH/XABCD/EMA/VWAP/STOCH toggles) remain absolutely positioned over the main chart area.

## New Refs

| Ref | Purpose |
|---|---|
| `stochContainerRef` | DOM div the second LW Charts instance mounts into |
| `stochChartRef` | The second LW Charts instance |
| `stochKSeriesRef` | %K line series (moves from `chartRef` to `stochChartRef`) |
| `stochDSeriesRef` | %D line series (moves from `chartRef` to `stochChartRef`) |
| `syncingRef` | Boolean guard to prevent echo loops during time-scale sync |
| `mainRangeUnsubRef` | Unsubscribe fn for main chart's `subscribeVisibleLogicalRangeChange` |
| `stochRangeUnsubRef` | Unsubscribe fn for Stoch chart's `subscribeVisibleLogicalRangeChange` |
| `mainCrosshairUnsubRef` | Unsubscribe fn for main chart's crosshair `subscribeCrosshairMove` |

## Stoch Chart Lifecycle

Runs on `[indicatorData, showStoch]` — same trigger as the current Stoch effect.

1. If `stochChartRef.current` exists → call `.remove()`, null out all Stoch refs, unsubscribe sync listeners
2. If `!showStoch || !indicatorData?.stochK?.length` → return (sub-chart stays absent)
3. Create a new LW Charts instance on `stochContainerRef.current`:
   - Dark background matching main chart (`#06080C`)
   - Right price scale: visible, no border label
   - Time scale: `visible: false` (no date row, but scrolling still works)
   - Grid lines: same dim styling as main chart
4. Add %K line series: `color: '#42A5F5'`, `lineWidth: 1.5`, `priceLineVisible: false`, `lastValueVisible: false`. Use `autoscaleInfoProvider` to pin the price axis to exactly 0–100 regardless of current data range, so the 20/80 reference lines always appear in the right relative position.
5. Add %D line series: `color: '#EF5350'`, `lineWidth: 1.5`, `lineStyle: 2` (dashed), same options
6. Add 20 and 80 as `createPriceLine` calls: `color: '#2a3346'`, `lineStyle: 2`, `lineWidth: 1`, `axisLabelVisible: true`
7. Set data on both series from `indicatorData.stochK` / `indicatorData.stochD`
8. Wire time-scale sync and crosshair sync (see below)

## Sync: Time-Scale (Bidirectional)

```
main.timeScale().subscribeVisibleLogicalRangeChange(range => {
  if (syncingRef.current) return;
  syncingRef.current = true;
  stochChartRef.current?.timeScale().setVisibleLogicalRange(range);
  syncingRef.current = false;
});

stoch.timeScale().subscribeVisibleLogicalRangeChange(range => {
  if (syncingRef.current) return;
  syncingRef.current = true;
  chartRef.current?.timeScale().setVisibleLogicalRange(range);
  syncingRef.current = false;
});
```

Both subscriptions are stored in refs (`mainRangeUnsubRef`, `stochRangeUnsubRef`) and called during cleanup.

## Sync: Crosshair (Main → Stoch only)

```
main.subscribeCrosshairMove(param => {
  if (!stochChartRef.current || !stochKSeriesRef.current) return;
  if (param.time) {
    stochChartRef.current.setCrosshairPosition(50, param.time, stochKSeriesRef.current); // 50 = dummy price; only the vertical line (time sync) matters
  } else {
    stochChartRef.current.clearCrosshairPosition();
  }
});
```

- One-directional: main → Stoch. Hovering inside the Stoch pane is not a primary use case.
- This is additive — the existing `subscribeCrosshairMove` used for `HoverContextCard` hit-testing is unaffected.
- Subscription stored in `mainCrosshairUnsubRef` and called during cleanup.

## Cleanup

The main chart's existing cleanup effect (on unmount / symbol+tf change) is extended to also destroy `stochChartRef` and call all stored unsubscribe functions before nulling the refs.

## What Doesn't Change

- `indicatorData` fetch in `api.js` — `stochK`/`stochD` already returned alongside candles
- All three call sites in `app.jsx` — `showStoch`/`setShowStoch` props already exist
- STOCH toggle button position (top-right of main chart) — still controls sub-chart visibility
- AssetHub mini-chart — `showStoch={false}` hardcoded, sub-chart never renders
