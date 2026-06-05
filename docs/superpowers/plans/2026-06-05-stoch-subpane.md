# Stoch RSI Sub-Pane Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the `pane: 1` Stoch RSI split with a separate fixed-height LW Charts instance below the main chart, synchronized on time-scale and crosshair.

**Architecture:** All changes are inside the `Chart` function in `ui/parts.jsx`. The return JSX becomes a flex column: main chart wrapper (unchanged height) + a 100px `stochContainerRef` div below. The Stoch useEffect creates/destroys a second LW Charts instance in that div; two new handlers sync the time-scale bidirectionally and the crosshair one-way (main → Stoch). The main chart cleanup is extended to also destroy `stochChartRef`.

**Tech Stack:** LightweightCharts v4 (CDN, `window.LightweightCharts`), React (Babel standalone)

---

### Task 1: Add new refs and restructure Chart return

**Files:**
- Modify: `ui/parts.jsx:1100-1104` (refs block)
- Modify: `ui/parts.jsx:1637-1639` (return opening)
- Modify: `ui/parts.jsx:1773-1776` (return closing)

- [ ] **Step 1: Add new refs after the existing stochDSeriesRef (line ~1104)**

Find this block:
```jsx
const stochKSeriesRef = useRef(null);
const stochDSeriesRef = useRef(null);
```

Replace with:
```jsx
const stochKSeriesRef     = useRef(null);
const stochDSeriesRef     = useRef(null);
const stochContainerRef   = useRef(null);
const stochChartRef       = useRef(null);
const syncingRef          = useRef(false);
```

- [ ] **Step 2: Restructure the Chart return to a flex column**

Find the current return opening (line ~1637):
```jsx
  return (
    <div style={{ position: "relative", width: "100%", height }}>
      <div ref={containerRef} style={{ width: "100%", height: "100%" }} />
```

Replace with:
```jsx
  return (
    <div style={{ display: "flex", flexDirection: "column", width: "100%" }}>
    <div style={{ position: "relative", width: "100%", height }}>
      <div ref={containerRef} style={{ width: "100%", height: "100%" }} />
```

- [ ] **Step 3: Add the Stoch container div and close the new outer wrapper**

Find the current closing tag (line ~1775):
```jsx
    </div>
  );
}
```

Replace with:
```jsx
    </div>
    <div
      ref={stochContainerRef}
      style={{
        width: "100%",
        height: 100,
        display: showStoch && indicatorData?.stochK?.length ? "block" : "none",
        background: "#06080c",
      }}
    />
    </div>
  );
}
```

- [ ] **Step 4: Verify the layout renders correctly**

Start Banshee (`launch_banshee.bat`), open `http://localhost:8765/ui/`, navigate to any asset's AnalysisPage. Toggle STOCH on. Confirm:
- A dark 100px band appears below the main chart
- No chart renders inside it yet (that's the next task)
- Toggling STOCH off makes the band disappear with no empty gap

- [ ] **Step 5: Commit**

```bash
cd ~/AntiEverything/Banshee_5
git add ui/parts.jsx
git commit -m "feat: stoch subpane layout skeleton - flex column + stochContainerRef div"
```

---

### Task 2: Rewrite the Stoch useEffect

**Files:**
- Modify: `ui/parts.jsx:1606-1619` (existing Stoch effect — full replacement)

- [ ] **Step 1: Replace the existing Stoch effect**

Find the existing effect (lines ~1606-1619):
```jsx
  /* Stoch RSI sub-pane — create/destroy on data or toggle change */
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;
    if (stochKSeriesRef.current) { try { chart.removeSeries(stochKSeriesRef.current); } catch(e){} stochKSeriesRef.current = null; }
    if (stochDSeriesRef.current) { try { chart.removeSeries(stochDSeriesRef.current); } catch(e){} stochDSeriesRef.current = null; }
    if (!showStoch || !indicatorData?.stochK?.length) return;
    const sK = chart.addLineSeries({ pane: 1, color: '#42A5F5', lineWidth: 1.5, priceLineVisible: false, lastValueVisible: false });
    sK.setData(indicatorData.stochK);
    stochKSeriesRef.current = sK;
    const sD = chart.addLineSeries({ pane: 1, color: '#EF5350', lineWidth: 1.5, lineStyle: 2, priceLineVisible: false, lastValueVisible: false });
    sD.setData(indicatorData.stochD);
    stochDSeriesRef.current = sD;
  }, [indicatorData, showStoch]);
```

Replace with:
```jsx
  /* Stoch RSI sub-pane — separate LW Charts instance, synced to main chart */
  useEffect(() => {
    const container = stochContainerRef.current;
    if (!container) return;

    // --- teardown any existing stoch chart ---
    stochKSeriesRef.current = null;
    stochDSeriesRef.current = null;
    if (stochChartRef.current) { stochChartRef.current.remove(); stochChartRef.current = null; }

    if (!showStoch || !indicatorData?.stochK?.length || !chartRef.current) return;

    // --- create chart ---
    const sc = window.LightweightCharts.createChart(container, {
      autoSize: true,
      layout: { background: { color: '#06080c' }, textColor: '#4a5364' },
      grid: { vertLines: { color: '#0e1420' }, horzLines: { color: '#0e1420' } },
      rightPriceScale: { visible: true, borderVisible: false, scaleMargins: { top: 0.05, bottom: 0.05 } },
      timeScale: { visible: false },
      crosshair: { mode: window.LightweightCharts.CrosshairMode.Normal },
      handleScale: { mouseWheel: false, pinch: false, axisPressedMouseMove: false },
    });
    stochChartRef.current = sc;

    // --- %K line (pinned 0-100 via autoscaleInfoProvider) ---
    const sK = sc.addLineSeries({
      color: '#42A5F5', lineWidth: 1.5,
      priceLineVisible: false, lastValueVisible: false,
      autoscaleInfoProvider: () => ({ priceRange: { minValue: 0, maxValue: 100 } }),
    });
    sK.setData(indicatorData.stochK);
    stochKSeriesRef.current = sK;

    // --- %D line (dashed) ---
    const sD = sc.addLineSeries({
      color: '#EF5350', lineWidth: 1.5, lineStyle: 2,
      priceLineVisible: false, lastValueVisible: false,
    });
    sD.setData(indicatorData.stochD);
    stochDSeriesRef.current = sD;

    // --- 20 / 80 reference lines ---
    sK.createPriceLine({ price: 80, color: '#3a4560', lineWidth: 1, lineStyle: 2, axisLabelVisible: true, title: '' });
    sK.createPriceLine({ price: 20, color: '#3a4560', lineWidth: 1, lineStyle: 2, axisLabelVisible: true, title: '' });

    // --- time-scale sync (bidirectional) ---
    const handleMainRange = range => {
      if (syncingRef.current || !range) return;
      syncingRef.current = true;
      sc.timeScale().setVisibleLogicalRange(range);
      syncingRef.current = false;
    };
    chartRef.current.timeScale().subscribeVisibleLogicalRangeChange(handleMainRange);

    const handleStochRange = range => {
      if (syncingRef.current || !range) return;
      syncingRef.current = true;
      chartRef.current?.timeScale().setVisibleLogicalRange(range);
      syncingRef.current = false;
    };
    sc.timeScale().subscribeVisibleLogicalRangeChange(handleStochRange);

    // --- crosshair sync (main → Stoch, vertical line only) ---
    const handleCrosshair = param => {
      if (!stochChartRef.current || !stochKSeriesRef.current) return;
      if (param.time) {
        stochChartRef.current.setCrosshairPosition(50, param.time, stochKSeriesRef.current);
      } else {
        stochChartRef.current.clearCrosshairPosition();
      }
    };
    chartRef.current.subscribeCrosshairMove(handleCrosshair);

    // --- initial range sync so Stoch starts aligned ---
    const currentRange = chartRef.current.timeScale().getVisibleLogicalRange();
    if (currentRange) sc.timeScale().setVisibleLogicalRange(currentRange);

    return () => {
      chartRef.current?.timeScale().unsubscribeVisibleLogicalRangeChange(handleMainRange);
      sc.timeScale().unsubscribeVisibleLogicalRangeChange(handleStochRange);
      chartRef.current?.unsubscribeCrosshairMove(handleCrosshair);
      stochKSeriesRef.current = null;
      stochDSeriesRef.current = null;
      if (stochChartRef.current) { stochChartRef.current.remove(); stochChartRef.current = null; }
    };
  }, [indicatorData, showStoch]);
```

- [ ] **Step 2: Verify Stoch chart renders correctly**

In the browser, navigate to an asset AnalysisPage and toggle STOCH on. Confirm:
- The 100px pane shows blue %K and red dashed %D lines
- Values are in the 0–100 range (not 0–95000 or similar)
- Faint dashed lines appear at 20 and 80
- Toggle STOCH off → pane collapses; toggle back on → chart reappears cleanly

- [ ] **Step 3: Verify time-scale sync**

With STOCH on, scroll/zoom the main chart. Confirm the Stoch pane scrolls in lockstep. Change symbol or timeframe, confirm no console errors.

- [ ] **Step 4: Verify crosshair sync**

Hover over candles in the main chart. Confirm a vertical crosshair line appears in the Stoch pane at the same time position.

- [ ] **Step 5: Commit**

```bash
cd ~/AntiEverything/Banshee_5
git add ui/parts.jsx
git commit -m "feat: stoch RSI as separate LW Charts instance with time-scale and crosshair sync"
```

---

### Task 3: Extend main chart cleanup to guard stochChartRef

**Files:**
- Modify: `ui/parts.jsx:1316-1323` (main chart cleanup block)

This ensures the Stoch chart is always destroyed when the main chart tears down (symbol/tf change, height change, unmount), guarding against any ordering edge cases.

- [ ] **Step 1: Add stochChartRef cleanup to the main chart teardown**

Find these lines in the main chart cleanup (inside the `useEffect(() => { ... }, [height])` return):
```jsx
      stochKSeriesRef.current = null;
      stochDSeriesRef.current = null;
      chart.remove();
      chartRef.current  = null;
      seriesRef.current = null;
```

Replace with:
```jsx
      stochKSeriesRef.current = null;
      stochDSeriesRef.current = null;
      if (stochChartRef.current) { stochChartRef.current.remove(); stochChartRef.current = null; }
      chart.remove();
      chartRef.current  = null;
      seriesRef.current = null;
```

- [ ] **Step 2: Verify no double-destroy errors on navigation**

In the browser: open AnalysisPage, toggle STOCH on, then click a different asset. Check the browser console for any LW Charts errors about removing an already-removed chart. There should be none.

Also verify: STOCH state correctly resets when switching assets (new asset starts with Stoch off because `indicatorData` is set to null during load and `showStoch` state persists — that's correct behavior).

- [ ] **Step 3: Commit**

```bash
cd ~/AntiEverything/Banshee_5
git add ui/parts.jsx
git commit -m "fix: destroy stochChartRef in main chart cleanup to prevent leaks on navigation"
```

---

### Task 4: Verify Nexus tab + final smoke test

**Files:** No code changes — verification only.

- [ ] **Step 1: Test AnalysisPage (420px chart)**

Navigate to any asset → AnalysisPage → SMC tab. Toggle STOCH on. Confirm:
- Stoch pane appears below the 420px chart
- Total page layout is not broken (chart + aside still side by side, no overflow)
- Toggle STOCH off: gap collapses cleanly

- [ ] **Step 2: Test Nexus tab (260px chart)**

Navigate to an asset → AnalysisPage → Nexus tab. Toggle STOCH on. Confirm the Stoch pane appears below the smaller 260px chart without layout issues.

- [ ] **Step 3: Confirm AssetHub mini-chart is unaffected**

Navigate to AssetHub. Confirm the 300px mini-chart shows no Stoch pane and the STOCH toggle button is absent (it's hidden when `indicatorData` is null, which it is on AssetHub since `showStoch={false}` is hardcoded there and no indicator data is fetched for that chart... actually verify by visual inspection — no extra band below the mini-chart).

- [ ] **Step 4: Test edge cases**

- Toggle STOCH on → switch timeframe → verify Stoch pane reappears in sync with new data
- Toggle STOCH on → navigate away from AnalysisPage entirely → navigate back → verify clean state
- Toggle STOCH off → on → off rapidly → no console errors

- [ ] **Step 5: Update ACTIVE_TASK.md**

In `~/AntiEverything/Banshee_5/ACTIVE_TASK.md`, mark the Stoch sub-pane fix as `[x]` complete and set next task.

- [ ] **Step 6: Final commit**

```bash
cd ~/AntiEverything/Banshee_5
git add ACTIVE_TASK.md
git commit -m "docs: mark stoch subpane fix complete in ACTIVE_TASK.md"
```
