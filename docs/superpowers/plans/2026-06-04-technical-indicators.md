# Technical Indicators Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add EMA 50/200, VWAP, and Stoch RSI overlays to the Banshee 5 chart — on both AssetHub and AnalysisPage (all tabs including Nexus).

**Architecture:** Indicator data is already computed by `micro_engine.py` and serialized in the `/ohlcv` response. `api.js` extends `fetchOHLCV` to extract indicator arrays from the same records. The Chart component (`parts.jsx`) stores them as internal state and renders them via three new `useEffect` hooks (same create/destroy pattern as SMC/GH/XABCD). Toggle states (showEMA, showVWAP, showStoch) live in parent components and are passed as props.

**Tech Stack:** LightweightCharts 4.2.0 (standalone CDN), React 18 (Babel standalone), existing FastAPI Core at `:8765`

---

## File Map

| File | Change |
|---|---|
| `ui/api.js` | Add `toIndicatorSeries()`, extend `fetchOHLCV` return shape |
| `ui/parts.jsx` | Add 5 series refs, `indicatorData` state, 3 indicator useEffects, 3 toggle props + buttons |
| `ui/app.jsx` | Add 3 toggle useState pairs to `AssetHub`, 3 to `AnalysisPage`; pass as props |

No backend changes. No new endpoints. No new npm dependencies.

---

## Task 1: Extend `api.js` — indicator extraction

**Files:**
- Modify: `ui/api.js:33-73`

- [ ] **Step 1: Add `toIndicatorSeries` helper after `toLWCandles` (after line 45)**

Insert after the closing `}` of `toLWCandles` (after line 45):

```js
/* extract a named indicator column from Core OHLCV records → LW Charts {time,value} format */
function toIndicatorSeries(records, field) {
  return records
    .filter(r => r.timestamp && r[field] != null && !isNaN(r[field]))
    .map(r => ({ time: Math.floor(new Date(r.timestamp).getTime() / 1000), value: r[field] }))
    .sort((a, b) => a.time - b.time);
}
```

- [ ] **Step 2: Update the live return in `fetchOHLCV` (line 59)**

Replace:
```js
    return { candles: toLWCandles(records), source: "live" };
```
With:
```js
    return {
      candles: toLWCandles(records),
      indicators: {
        ema50:  toIndicatorSeries(records, 'ema_50'),
        ema200: toIndicatorSeries(records, 'ema_200'),
        vwap:   toIndicatorSeries(records, 'vwap'),
        stochK: toIndicatorSeries(records, 'stoch_k'),
        stochD: toIndicatorSeries(records, 'stoch_d'),
      },
      source: "live",
    };
```

- [ ] **Step 3: Update the mock fallback return (line 71)**

Replace:
```js
    return { candles, source: "mock" };
```
With:
```js
    return { candles, indicators: null, source: "mock" };
```

- [ ] **Step 4: Verify in browser console**

Open `http://localhost:8765/ui/`, open DevTools → Console, paste:
```js
window.API.fetchOHLCV("BTC", "1H").then(r => console.log(Object.keys(r.indicators || {})))
```
Expected output: `['ema50', 'ema200', 'vwap', 'stochK', 'stochD']`

- [ ] **Step 5: Commit**

```bash
git add ui/api.js
git commit -m "feat: extract indicator series from OHLCV response in api.js"
```

---

## Task 2: Add `indicatorData` state + series refs + extend fetch useEffect in `Chart` (`parts.jsx`)

**Files:**
- Modify: `ui/parts.jsx:1088-1330`

- [ ] **Step 1: Add 5 series refs after existing refs (after line 1100)**

After `const eqlLinesRef = useRef([]);` (line 1100), add:
```js
  const ema50SeriesRef  = useRef(null);
  const ema200SeriesRef = useRef(null);
  const vwapSeriesRef   = useRef(null);
  const stochKSeriesRef = useRef(null);
  const stochDSeriesRef = useRef(null);
```

- [ ] **Step 2: Add `indicatorData` state after `opacityMult` state (after line 1111)**

After `const [opacityMult, setOpacityMult] = useState(1.0);`, add:
```js
  const [indicatorData, setIndicatorData] = useState(null);
```

- [ ] **Step 3: Null out indicator series refs in chart cleanup (line 1306–1312 block)**

Add inside the `return () => { ... }` cleanup block, after `oteLinesRef.current = [];` (line 1309) and before `chart.remove()`:
```js
      ema50SeriesRef.current  = null;
      ema200SeriesRef.current = null;
      vwapSeriesRef.current   = null;
      stochKSeriesRef.current = null;
      stochDSeriesRef.current = null;
```

- [ ] **Step 4: Extend the fetchOHLCV useEffect to capture indicators (line 1322)**

Replace:
```js
    window.API.fetchOHLCV(symbol, tf).then(({ candles, source }) => {
      if (cancelled || !seriesRef.current || !candles.length) return;
      seriesRef.current.setData(candles);
      chartRef.current.timeScale().fitContent();
      setDataSource(source);
    });
```
With:
```js
    setIndicatorData(null);
    window.API.fetchOHLCV(symbol, tf).then(({ candles, indicators, source }) => {
      if (cancelled || !seriesRef.current || !candles.length) return;
      seriesRef.current.setData(candles);
      chartRef.current.timeScale().fitContent();
      setDataSource(source);
      setIndicatorData(indicators || null);
    });
```

- [ ] **Step 5: Confirm no console errors**

Reload `http://localhost:8765/ui/`, open an asset. Console should be clean — no new errors.

- [ ] **Step 6: Commit**

```bash
git add ui/parts.jsx
git commit -m "feat: add indicatorData state and series refs to Chart component"
```

---

## Task 3: Add toggle props + buttons to `Chart` (`parts.jsx`)

**Files:**
- Modify: `ui/parts.jsx:1088` (Chart signature) and `ui/parts.jsx:1637–1672` (toggle button block)

_Props must be on the signature before the useEffects in Task 4 reference them._

- [ ] **Step 1: Add 6 new props to the Chart function signature (line 1088)**

Replace the existing signature:
```js
function Chart({ symbol, tf, height = 360, accent = "var(--cyan)", smcData = null, smcLoading = false, ghData = null, ghLoading = false, xabcdData = null, xabcdLoading = false, showSMC = true, setShowSMC = () => {}, showGH = true, setShowGH = () => {}, showXABCD = true, setShowXABCD = () => {}, lensMode = 1, currentPrice = null, onHover = null }) {
```
With:
```js
function Chart({ symbol, tf, height = 360, accent = "var(--cyan)", smcData = null, smcLoading = false, ghData = null, ghLoading = false, xabcdData = null, xabcdLoading = false, showSMC = true, setShowSMC = () => {}, showGH = true, setShowGH = () => {}, showXABCD = true, setShowXABCD = () => {}, showEMA = true, setShowEMA = () => {}, showVWAP = true, setShowVWAP = () => {}, showStoch = false, setShowStoch = () => {}, lensMode = 1, currentPrice = null, onHover = null }) {
```

- [ ] **Step 2: Add three indicator toggle buttons on the RIGHT side of the chart**

After the opacity cycle button block (after the closing `)}` of the opacity button, before `</div>` at line 1673), add:

```js
      {/* EMA toggle — right side, top 24 */}
      {indicatorData && (
        <button
          onClick={() => setShowEMA(v => !v)}
          className="mono"
          style={{
            position: "absolute", top: 24, right: 8, zIndex: 10,
            fontSize: 12, letterSpacing: "0.14em",
            background: showEMA ? "rgba(66,165,245,0.15)" : "rgba(6,8,12,0.7)",
            border: `1px solid ${showEMA ? "#42A5F5" : "#2a3346"}`,
            color: showEMA ? "#42A5F5" : "#4a5364",
            padding: "2px 7px", cursor: "pointer",
          }}>
          {showEMA ? "EMA ◆" : "EMA ○"}
        </button>
      )}
      {/* VWAP toggle — right side, top 42 */}
      {indicatorData && (
        <button
          onClick={() => setShowVWAP(v => !v)}
          className="mono"
          style={{
            position: "absolute", top: 42, right: 8, zIndex: 10,
            fontSize: 12, letterSpacing: "0.14em",
            background: showVWAP ? "rgba(171,71,188,0.15)" : "rgba(6,8,12,0.7)",
            border: `1px solid ${showVWAP ? "#AB47BC" : "#2a3346"}`,
            color: showVWAP ? "#AB47BC" : "#4a5364",
            padding: "2px 7px", cursor: "pointer",
          }}>
          {showVWAP ? "VWAP ◆" : "VWAP ○"}
        </button>
      )}
      {/* STOCH toggle — right side, top 60 */}
      {indicatorData && (
        <button
          onClick={() => setShowStoch(v => !v)}
          className="mono"
          style={{
            position: "absolute", top: 60, right: 8, zIndex: 10,
            fontSize: 12, letterSpacing: "0.14em",
            background: showStoch ? "rgba(239,83,80,0.15)" : "rgba(6,8,12,0.7)",
            border: `1px solid ${showStoch ? "#EF5350" : "#2a3346"}`,
            color: showStoch ? "#EF5350" : "#4a5364",
            padding: "2px 7px", cursor: "pointer",
          }}>
          {showStoch ? "STOCH ◆" : "STOCH ○"}
        </button>
      )}
```

- [ ] **Step 3: Commit**

```bash
git add ui/parts.jsx
git commit -m "feat: add indicator props and toggle buttons to Chart component"
```

---

## Task 4: Add EMA, VWAP, and Stoch useEffects to `Chart` (`parts.jsx`)

**Files:**
- Modify: `ui/parts.jsx` — insert three useEffects after the XABCD useEffect (after line 1565)

- [ ] **Step 1: Add EMA useEffect after XABCD useEffect (after the `}, [xabcdData, showXABCD]);` line)**

```js
  /* EMA 50/200 overlays — create/destroy on data or toggle change */
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;
    if (ema50SeriesRef.current)  { try { chart.removeSeries(ema50SeriesRef.current);  } catch(e){} ema50SeriesRef.current  = null; }
    if (ema200SeriesRef.current) { try { chart.removeSeries(ema200SeriesRef.current); } catch(e){} ema200SeriesRef.current = null; }
    if (!showEMA || !indicatorData?.ema50?.length) return;
    const s50 = chart.addLineSeries({ color: '#42A5F5', lineWidth: 1.5, priceLineVisible: false, lastValueVisible: false });
    s50.setData(indicatorData.ema50);
    ema50SeriesRef.current = s50;
    const s200 = chart.addLineSeries({ color: '#EF5350', lineWidth: 1.5, priceLineVisible: false, lastValueVisible: false });
    s200.setData(indicatorData.ema200);
    ema200SeriesRef.current = s200;
  }, [indicatorData, showEMA]);
```

- [ ] **Step 2: Add VWAP useEffect immediately after the EMA useEffect**

```js
  /* VWAP overlay — create/destroy on data or toggle change */
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;
    if (vwapSeriesRef.current) { try { chart.removeSeries(vwapSeriesRef.current); } catch(e){} vwapSeriesRef.current = null; }
    if (!showVWAP || !indicatorData?.vwap?.length) return;
    const s = chart.addLineSeries({ color: '#AB47BC', lineWidth: 1.5, lineStyle: 2, priceLineVisible: false, lastValueVisible: false });
    s.setData(indicatorData.vwap);
    vwapSeriesRef.current = s;
  }, [indicatorData, showVWAP]);
```

- [ ] **Step 3: Add Stoch useEffect immediately after the VWAP useEffect**

```js
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

- [ ] **Step 4: Verify in browser**

Reload the page, open an asset on AnalysisPage. EMA 50 (blue) and EMA 200 (red) should appear on the chart with toggle buttons on the right. Console should be clean — no errors.

- [ ] **Step 5: Commit**

```bash
git add ui/parts.jsx
git commit -m "feat: add EMA/VWAP/Stoch useEffects to Chart component"
```

---

## Task 5: Wire up `AssetHub` chart in `app.jsx`

**Files:**
- Modify: `ui/app.jsx:863-870` (AssetHub useState block) and `ui/app.jsx:997-1003` (Chart props)

- [ ] **Step 1: Add 3 toggle states to `AssetHub` (after line 869, after `const [execPanel, setExecPanel] = useState(false);`)**

```js
  const [showEMA,   setShowEMA]   = useState(true);
  const [showVWAP,  setShowVWAP]  = useState(true);
  const [showStoch, setShowStoch] = useState(false);
```

- [ ] **Step 2: Pass indicator props to the AssetHub Chart (lines 997–1003)**

Replace:
```js
            <window.Chart symbol={asset.sym} tf={tf} height={300} accent={c.fg}
              smcData={null} smcLoading={false}
              ghData={null} ghLoading={false}
              xabcdData={null} xabcdLoading={false}
              showSMC={false} setShowSMC={() => {}}
              showGH={false} setShowGH={() => {}}
              showXABCD={false} setShowXABCD={() => {}} />
```
With:
```js
            <window.Chart symbol={asset.sym} tf={tf} height={300} accent={c.fg}
              smcData={null} smcLoading={false}
              ghData={null} ghLoading={false}
              xabcdData={null} xabcdLoading={false}
              showSMC={false} setShowSMC={() => {}}
              showGH={false} setShowGH={() => {}}
              showXABCD={false} setShowXABCD={() => {}}
              showEMA={showEMA} setShowEMA={setShowEMA}
              showVWAP={showVWAP} setShowVWAP={setShowVWAP}
              showStoch={showStoch} setShowStoch={setShowStoch} />
```

- [ ] **Step 3: Verify in browser**

Reload, open an asset in AssetHub. You should see EMA ◆ and VWAP ◆ buttons on the right side of the chart (blue and purple). EMA 50 (blue line) and EMA 200 (red line) should be visible on the candlestick chart. Toggle them — they should appear/disappear. Click STOCH ○ — a sub-pane should appear below the candles with two lines.

- [ ] **Step 4: Commit**

```bash
git add ui/app.jsx
git commit -m "feat: wire indicator toggles to AssetHub chart"
```

---

## Task 6: Wire up `AnalysisPage` charts in `app.jsx`

**Files:**
- Modify: `ui/app.jsx:1380-1394` (AnalysisPage useState block) and `ui/app.jsx:1611-1620` + `ui/app.jsx:1704-1710` (Chart props)

- [ ] **Step 1: Add 3 toggle states to `AnalysisPage` (after line 1394, after the `xabcdLoading` state)**

```js
  const [showEMA,   setShowEMA]   = useState(true);
  const [showVWAP,  setShowVWAP]  = useState(true);
  const [showStoch, setShowStoch] = useState(false);
```

- [ ] **Step 2: Pass indicator props to the SMC/GH tab chart (lines 1611–1620)**

Replace:
```js
                <window.Chart symbol={asset.sym} tf={tf} height={420} accent={activeTabCfg.accent}
                  smcData={smcData} smcLoading={smcLoading}
                  ghData={ghData} ghLoading={ghLoading}
                  xabcdData={xabcdData} xabcdLoading={xabcdLoading}
                  showSMC={showSMC} setShowSMC={() => {}}
                  showGH={showGH} setShowGH={() => {}}
                  showXABCD={showXABCD} setShowXABCD={() => {}}
                  lensMode={lensMode}
                  currentPrice={asset.price}
                  onHover={setHoveredElement} />
```
With:
```js
                <window.Chart symbol={asset.sym} tf={tf} height={420} accent={activeTabCfg.accent}
                  smcData={smcData} smcLoading={smcLoading}
                  ghData={ghData} ghLoading={ghLoading}
                  xabcdData={xabcdData} xabcdLoading={xabcdLoading}
                  showSMC={showSMC} setShowSMC={() => {}}
                  showGH={showGH} setShowGH={() => {}}
                  showXABCD={showXABCD} setShowXABCD={() => {}}
                  showEMA={showEMA} setShowEMA={setShowEMA}
                  showVWAP={showVWAP} setShowVWAP={setShowVWAP}
                  showStoch={showStoch} setShowStoch={setShowStoch}
                  lensMode={lensMode}
                  currentPrice={asset.price}
                  onHover={setHoveredElement} />
```

- [ ] **Step 3: Pass indicator props to the Nexus tab chart (lines 1704–1710)**

Replace:
```js
              <window.Chart symbol={asset.sym} tf={nexusTf} height={260} accent={c.fg}
                smcData={null} smcLoading={false}
                ghData={null} ghLoading={false}
                xabcdData={null} xabcdLoading={false}
                showSMC={false} setShowSMC={() => {}}
                showGH={false} setShowGH={() => {}}
                showXABCD={false} setShowXABCD={() => {}} />
```
With:
```js
              <window.Chart symbol={asset.sym} tf={nexusTf} height={260} accent={c.fg}
                smcData={null} smcLoading={false}
                ghData={null} ghLoading={false}
                xabcdData={null} xabcdLoading={false}
                showSMC={false} setShowSMC={() => {}}
                showGH={false} setShowGH={() => {}}
                showXABCD={false} setShowXABCD={() => {}}
                showEMA={showEMA} setShowEMA={setShowEMA}
                showVWAP={showVWAP} setShowVWAP={setShowVWAP}
                showStoch={showStoch} setShowStoch={setShowStoch} />
```

- [ ] **Step 4: Verify in browser — AnalysisPage**

Open an asset → Analysis page (SMC tab). EMA 50 (blue) and EMA 200 (red) should be visible on the chart, with EMA ◆ and VWAP ◆ buttons on the right. Switch to GH tab — indicators should persist. Switch to Nexus tab — indicators should also be visible. Toggle states should survive tab switches (shared useState in AnalysisPage).

- [ ] **Step 5: Commit**

```bash
git add ui/app.jsx
git commit -m "feat: wire indicator toggles to AnalysisPage charts (SMC/GH/Nexus)"
```

---

## Task 7: Regression check

**Files:** None modified

- [ ] **Step 1: Run existing Python tests**

```bash
cd ~/AntiEverything/Banshee_5
python -m pytest test_banshee.py -v
```
Expected: all tests pass (no backend changes were made)

- [ ] **Step 2: Browser smoke test — SMC overlays still work**

Open an asset → Analysis page → SMC tab. Toggle SMC ◆ off and on — zones, BOS/CHoCH, and swing markers should appear/disappear correctly. Confirm the new EMA/VWAP lines sit beneath SMC overlays (z-order correct).

- [ ] **Step 3: Browser smoke test — Stoch sub-pane**

Toggle STOCH ○ on — a sub-pane appears below candles with %K (blue) and %D (red dashed). Toggle off — sub-pane disappears. Change symbol — Stoch sub-pane reappears if still toggled on, with new data.

- [ ] **Step 4: Browser smoke test — mock fallback**

Stop Core (`Ctrl+C`), reload the UI. Chart falls back to mock candles. Indicator buttons should not appear (since `indicatorData` will be `null` from the mock path). No console errors.

- [ ] **Step 5: Restart Core and final commit**

```bash
git add .
git commit -m "feat: technical indicators complete — EMA 50/200, VWAP, Stoch RSI on AssetHub and AnalysisPage"
```
