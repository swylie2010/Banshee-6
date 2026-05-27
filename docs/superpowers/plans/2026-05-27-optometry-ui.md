# Optometry UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add four named SMC lenses (ALL / BATTLEFIELD / FOOTPRINTS / SNIPER) to the AnalysisPage SMC tab — hotkeys 1–4, buttons on the TF bar, each lens filtering the six chart layer groups to answer one focused question.

**Architecture:** `lensMode` state (1–4) lives in `AnalysisPage` and is passed as a prop to `Chart`. The existing SMC `useEffect` teardown/reattach cycle handles lens switching automatically when `lensMode` is added to its dependency array. Filtering happens inside the effect before each primitive is attached.

**Tech Stack:** Vanilla React (Babel CDN), Lightweight Charts v4.2, no build step.

---

## File Map

| File | Change |
|---|---|
| `ui/app.jsx` | Add `lensMode` state; reset on asset change; lens buttons on TF bar (SMC tab only); keydown listener; pass `lensMode` to `Chart` |
| `ui/parts.jsx` | Add `lensMode` prop to `Chart`; add `filterZonesForLens()` helper; add layer visibility flags; apply filtering in SMC `useEffect`; add `lensMode` to effect deps |

No other files are touched.

---

## Task 1: AnalysisPage — lens state, buttons, keyboard

**Files:**
- Modify: `ui/app.jsx` — `AnalysisPage` function (starts line 1030)

No automated test infrastructure exists for this CDN app. Each task ends with a manual verification checklist instead of a test run.

- [ ] **Step 1: Add `lensMode` state and reset it on asset change**

In `AnalysisPage`, add state after the existing state declarations (after line 1043), and add it to the asset-change reset effect:

```jsx
// after:  const aiAbortRef = useRef(null);
const [lensMode, setLensMode] = useState(1);
```

In the existing `useEffect(() => { ... }, [asset.sym])` (the "reset all on symbol change" block at line 1051), add the reset:

```jsx
useEffect(() => {
  cancelAI();
  setSmcData(null); setGhData(null); setXabcdData(null);
  setAiText(null); setAiLoading(false); setAiError(null);
  setLensMode(1);
}, [asset.sym]);
```

- [ ] **Step 2: Add keydown listener for hotkeys 1–4**

Add this `useEffect` immediately after the "reset AI on tab change" effect (after line 1061):

```jsx
/* lens hotkeys 1–4 — active only on SMC tab */
useEffect(() => {
  if (tab !== "smc") return;
  function onKey(e) {
    if (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA") return;
    if (e.key === "1") setLensMode(1);
    else if (e.key === "2") setLensMode(2);
    else if (e.key === "3") setLensMode(3);
    else if (e.key === "4") setLensMode(4);
  }
  window.addEventListener("keydown", onKey);
  return () => window.removeEventListener("keydown", onKey);
}, [tab]);
```

- [ ] **Step 3: Replace the TF bar JSX to add lens buttons**

Find this block (lines 1184–1200):

```jsx
{tab !== "nexus" && (
  <div style={{ padding: "12px 14px 0 14px" }}>
    <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8, padding: "6px 10px", background: "var(--bg-2)", border: "1px solid var(--line)", display: "inline-flex" }}>
      <window.Label>TF</window.Label>
      <div style={{ display: "flex", gap: 0, border: "1px solid var(--line-2)" }}>
        {TF_LIST.map((t, i) => {
          const active = tf === t;
          return (
            <button key={t} onClick={() => setTf(t)} style={{ padding: "5px 12px", background: active ? activeTabCfg.accent : "transparent", color: active ? "var(--bg-0)" : "var(--ink-2)", border: "none", borderLeft: i ? "1px solid var(--line-2)" : "none", cursor: "pointer" }}>
              <span className="mono" style={{ fontSize: 10, fontWeight: 600, letterSpacing: "0.1em" }}>{t}</span>
            </button>
          );
        })}
      </div>
    </div>
  </div>
)}
```

Replace with:

```jsx
{tab !== "nexus" && (
  <div style={{ padding: "12px 14px 0 14px" }}>
    <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8, padding: "6px 10px", background: "var(--bg-2)", border: "1px solid var(--line)" }}>
      {/* TF selector — left side */}
      <window.Label>TF</window.Label>
      <div style={{ display: "flex", gap: 0, border: "1px solid var(--line-2)" }}>
        {TF_LIST.map((t, i) => {
          const active = tf === t;
          return (
            <button key={t} onClick={() => setTf(t)} style={{ padding: "5px 12px", background: active ? activeTabCfg.accent : "transparent", color: active ? "var(--bg-0)" : "var(--ink-2)", border: "none", borderLeft: i ? "1px solid var(--line-2)" : "none", cursor: "pointer" }}>
              <span className="mono" style={{ fontSize: 10, fontWeight: 600, letterSpacing: "0.1em" }}>{t}</span>
            </button>
          );
        })}
      </div>
      {/* Lens selector — right side, SMC tab only */}
      {tab === "smc" && (() => {
        const LENSES = [
          { mode: 1, label: "ALL" },
          { mode: 2, label: "BATTLEFIELD" },
          { mode: 3, label: "FOOTPRINTS" },
          { mode: 4, label: "SNIPER" },
        ];
        return (
          <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 6 }}>
            <window.Label>LENS</window.Label>
            <div style={{ display: "flex", gap: 0, border: "1px solid var(--line-2)" }}>
              {LENSES.map(({ mode, label }, i) => {
                const active = lensMode === mode;
                return (
                  <button key={mode} onClick={() => setLensMode(mode)}
                    style={{ padding: "5px 12px", background: active ? "var(--cyan)" : "transparent", color: active ? "var(--bg-0)" : "var(--ink-2)", border: "none", borderLeft: i ? "1px solid var(--line-2)" : "none", cursor: "pointer" }}>
                    <span className="mono" style={{ fontSize: 10, fontWeight: 600, letterSpacing: "0.1em" }}>{label}</span>
                  </button>
                );
              })}
            </div>
          </div>
        );
      })()}
    </div>
  </div>
)}
```

- [ ] **Step 4: Pass `lensMode` to `Chart`**

Find the Chart usage (lines 1205–1211):

```jsx
<window.Chart symbol={asset.sym} tf={tf} height={420} accent={activeTabCfg.accent}
  smcData={smcData} smcLoading={smcLoading}
  ghData={ghData} ghLoading={ghLoading}
  xabcdData={xabcdData} xabcdLoading={xabcdLoading}
  showSMC={showSMC} setShowSMC={() => {}}
  showGH={showGH} setShowGH={() => {}}
  showXABCD={showXABCD} setShowXABCD={() => {}} />
```

Add `lensMode`:

```jsx
<window.Chart symbol={asset.sym} tf={tf} height={420} accent={activeTabCfg.accent}
  smcData={smcData} smcLoading={smcLoading}
  ghData={ghData} ghLoading={ghLoading}
  xabcdData={xabcdData} xabcdLoading={xabcdLoading}
  showSMC={showSMC} setShowSMC={() => {}}
  showGH={showGH} setShowGH={() => {}}
  showXABCD={showXABCD} setShowXABCD={() => {}}
  lensMode={lensMode} />
```

- [ ] **Step 5: Commit**

```bash
cd ~/AntiEverything/Banshee_5
git add ui/app.jsx
git commit -m "feat: add lensMode state, lens buttons, and hotkeys to AnalysisPage"
```

- [ ] **Step 6: Manual verification**

Restart Core (`launch_banshee.bat`), open `http://localhost:8765/ui/`, navigate to any asset → SMC tab.

- [ ] TF bar shows: `[ TF ] [1H][4H][1D]` on the left, `[ LENS ] [ALL][BATTLEFIELD][FOOTPRINTS][SNIPER]` on the right
- [ ] Active lens highlighted in cyan
- [ ] Pressing `1`/`2`/`3`/`4` switches the active lens button
- [ ] Lens buttons do NOT appear on GH or NEXUS tabs
- [ ] Switching to a different asset resets lens to ALL (L1)
- [ ] Pressing `1`–`4` while on GH tab does nothing

---

## Task 2: Chart — lensMode prop + SMC layer filtering

**Files:**
- Modify: `ui/parts.jsx` — `Chart` function (starts line 981) and `smcToZones` area

- [ ] **Step 1: Add `lensMode` prop to Chart signature**

Find line 981:

```jsx
function Chart({ symbol, tf, height = 360, accent = "var(--cyan)", smcData = null, smcLoading = false, ghData = null, ghLoading = false, xabcdData = null, xabcdLoading = false, showSMC = true, setShowSMC = () => {}, showGH = true, setShowGH = () => {}, showXABCD = true, setShowXABCD = () => {} }) {
```

Replace with:

```jsx
function Chart({ symbol, tf, height = 360, accent = "var(--cyan)", smcData = null, smcLoading = false, ghData = null, ghLoading = false, xabcdData = null, xabcdLoading = false, showSMC = true, setShowSMC = () => {}, showGH = true, setShowGH = () => {}, showXABCD = true, setShowXABCD = () => {}, lensMode = 1 }) {
```

- [ ] **Step 2: Add `filterZonesForLens` helper just before the `Chart` function**

Insert this function immediately before `function Chart(` (before line 981):

```jsx
function filterZonesForLens(zones, lensMode) {
  if (lensMode === 1) return zones; // ALL — no filter

  if (lensMode === 2) return []; // BATTLEFIELD — no OBs or FVGs

  if (lensMode === 3) {
    // FOOTPRINTS: FVGs + inducement-pending OBs + candidate OBs
    return zones.filter(z => {
      if (z.type === "fvg") return true;
      if (z.type === "ob") return z.has_pending_inducement || !z.gate_passed;
      return false;
    });
  }

  if (lensMode === 4) {
    // SNIPER: OBs only (no FVGs), with opacity tiers
    return zones
      .filter(z => z.type === "ob" && z.gate_passed) // exclude FVGs + candidates
      .map(z => {
        if (z.inducement_swept) return z; // full opacity as-is
        if (z.has_pending_inducement || z.status === "active") return { ...z, opacity: 0.40 };
        if (z.status === "touched" || z.status === "degraded")  return { ...z, opacity: 0.20 };
        return z;
      });
  }

  return zones; // fallback
}
```

- [ ] **Step 3: Add layer visibility flags and apply zone filter in the SMC `useEffect`**

Find the section inside the SMC `useEffect` that begins after the `if (!showSMC || !smcData || smcData.error) return;` guard (line 1132). Replace the entire body from that guard down to (but not including) the `return () => {` cleanup block with the following:

```jsx
    if (!showSMC || !smcData || smcData.error) return;

    /* per-lens layer visibility flags */
    const showPD      = lensMode === 1 || lensMode === 2;
    const showOTE     = lensMode === 1 || lensMode === 2 || lensMode === 4;
    const showHTF     = lensMode === 1 || lensMode === 2;
    const showMarkers = lensMode === 1 || lensMode === 2;
    const showEQL     = lensMode === 1 || lensMode === 3;

    /* PD zone background — premium/discount/OTE */
    if (showPD) {
      const pdZone = smcToPDZone(smcData);
      if (pdZone) {
        const pdPrim = new SMCPDPrimitive(pdZone);
        try { series.attachPrimitive(pdPrim); pdPrimRef.current = pdPrim; } catch {}
      }
    }

    const rawZones = smcToZones(smcData);
    const zones = filterZonesForLens(rawZones, lensMode).map(z => ({ ...z, opacity: z.opacity * opacityMult }));
    if (zones.length) {
      const prim = new SMCZonePrimitive(zones, chartRef.current);
      try {
        series.attachPrimitive(prim);
        primitiveRef.current = prim;
      } catch (e) {
        console.warn("[SMC] primitive attach failed:", e);
      }
    }

    /* HTF key levels as dotted price lines */
    if (showHTF) {
      const newLines = [];
      for (const lvl of (smcData.flat_levels || []).slice(0, 25)) {
        if (!lvl.price || isNaN(lvl.price)) continue;
        try {
          newLines.push(series.createPriceLine({
            price: lvl.price,
            color: "#f59e0b55",
            lineWidth: 1,
            lineStyle: LightweightCharts.LineStyle.Dotted,
            axisLabelVisible: false,
            title: "",
          }));
        } catch {}
      }
      htfLinesRef.current = newLines;
    }

    /* SMC markers: swing labels + BOS/CHoCH */
    if (showMarkers && chartRef.current) {
      const { swings, events } = smcToMarkers(smcData);
      if (swings.length || events.length) {
        const mkPrim = new SMCMarkersPrimitive(swings, events, chartRef.current);
        try { series.attachPrimitive(mkPrim); smcMarkersPrimRef.current = mkPrim; } catch {}
      }
    }

    /* OTE golden pocket — two labeled price lines */
    if (showOTE) {
      const pd = smcData.ltf_smc?.pd_zones;
      if (pd?.ote_top && pd?.ote_bottom) {
        const oteLines = [];
        try {
          oteLines.push(series.createPriceLine({
            price:            pd.ote_top,
            color:            "#f59e0b99",
            lineWidth:        1,
            lineStyle:        LightweightCharts.LineStyle.Dashed,
            axisLabelVisible: true,
            title:            "OTE 62%",
          }));
          oteLines.push(series.createPriceLine({
            price:            pd.ote_bottom,
            color:            "#f59e0b99",
            lineWidth:        1,
            lineStyle:        LightweightCharts.LineStyle.Dashed,
            axisLabelVisible: true,
            title:            "OTE 79%",
          }));
        } catch {}
        oteLinesRef.current = oteLines;
      }
    }

    /* EQH/EQL unswept pools as dotted price lines */
    if (showEQL) {
      const newEqlLines = [];
      for (const pool of (smcData.ltf_smc?.liquidity_pools || [])) {
        if (pool.swept || !pool.level || isNaN(pool.level)) continue;
        try {
          newEqlLines.push(series.createPriceLine({
            price:            pool.level,
            color:            pool.kind === "eqh" ? "#ef444460" : "#5eead460",
            lineWidth:        1,
            lineStyle:        LightweightCharts.LineStyle.Dotted,
            axisLabelVisible: false,
            title:            "",
          }));
        } catch {}
      }
      eqlLinesRef.current = newEqlLines;
    }
```

- [ ] **Step 4: Add `lensMode` to the SMC `useEffect` dependency array**

Find the closing dependency array of the SMC `useEffect` (line 1246):

```jsx
  }, [smcData, showSMC, opacityMult]);
```

Replace with:

```jsx
  }, [smcData, showSMC, opacityMult, lensMode]);
```

- [ ] **Step 5: Commit**

```bash
cd ~/AntiEverything/Banshee_5
git add ui/parts.jsx
git commit -m "feat: add lens filtering to Chart SMC overlay (Optometry UI)"
```

- [ ] **Step 6: Manual verification**

Hard-refresh (`Ctrl+Shift+R`) in the browser, navigate to any asset → SMC tab.

**L1 ALL (default):**
- [ ] Everything renders as before — PD background, OBs, FVGs, swing markers, HTF levels, OTE lines, EQL pools

**L2 BATTLEFIELD:**
- [ ] PD premium/discount gradients visible
- [ ] OTE 62%/79% price lines visible on right axis
- [ ] HTF dotted amber levels visible
- [ ] Swing markers (HH/HL triangles, BOS/CHoCH labels) visible
- [ ] No OBs, no FVGs, no EQL pools

**L3 FOOTPRINTS:**
- [ ] FVGs visible at full opacity
- [ ] Inducement-pending OBs (amber ⌛ border) visible
- [ ] Candidate OBs (dashed border) visible
- [ ] No PD background, no OTE lines, no HTF levels, no swing markers
- [ ] EQL/EQH pools visible

**L4 SNIPER:**
- [ ] Inducement-swept OBs (green ⚡ border) visible at full opacity
- [ ] Active + pending-inducement OBs visible but clearly dimmed (~40%)
- [ ] Touched/degraded OBs barely visible (~20%)
- [ ] Candidate OBs (gate_passed=false) not shown
- [ ] OTE 62%/79% lines visible
- [ ] No FVGs, no PD background, no HTF levels, no swing markers, no EQL pools

**Hotkeys:**
- [ ] Press `2` → switches to BATTLEFIELD, chart updates immediately
- [ ] Press `4` → switches to SNIPER, chart updates immediately
- [ ] Press `1` → back to ALL
