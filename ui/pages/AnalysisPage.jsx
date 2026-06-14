const { useState, useEffect, useRef } = React;

function computeWarnings(smcData, ghData, xabcdData, asset) {
  const warnings = [];
  const price = asset?.price;
  if (!price) return warnings;

  if (smcData && !smcData.error && smcData.ltf_smc) {
    const ltf = smcData.ltf_smc;
    const alignment = smcData.alignment || "";

    if (alignment.includes("CONFLICTED")) {
      const m = alignment.match(/HTF (\w+) vs LTF (\w+)/);
      warnings.push({ section: "SMC", level: "danger",
        text: m ? `HTF ${m[1]} vs LTF ${m[2]} — reduce size or stand by`
                : "HTF/LTF structure conflict — reduce size or stand by" });
    }

    const events = ltf.structure_events || [];
    const lastEvt = events.length ? events[events.length - 1] : null;
    if (lastEvt?.event_type?.startsWith("CHoCH")) {
      const chDir = lastEvt.event_type === "CHoCH_BULL" ? "bullish" : "bearish";
      warnings.push({ section: "SMC", level: "warn",
        text: `CHoCH ${chDir} — possible reversal, await retest before entry` });
    } else if (lastEvt?.event_type?.startsWith("BOS")) {
      const isBull = lastEvt.event_type === "BOS_BULL";
      const activeOBsCheck = (ltf.order_blocks || []).filter(ob => ob.status !== "mitigated");
      const nearRetest = activeOBsCheck.filter(ob =>
        isBull
          ? ob.kind === "bull" && ob.gate_passed && ob.zone_top >= price * 0.96
          : ob.kind === "bear" && ob.gate_passed && ob.zone_bottom <= price * 1.04
      );
      if (nearRetest.length === 0) {
        warnings.push({ section: "SMC", level: "warn",
          text: "BOS printed but no OB retest nearby — late entry, wait for pullback" });
      }
    }

    const activeOBs = (ltf.order_blocks || []).filter(ob => ob.status !== "mitigated");
    const gated = activeOBs.filter(ob => ob.gate_passed);
    const cands  = activeOBs.filter(ob => !ob.gate_passed);
    if (activeOBs.length > 0 && gated.length === 0) {
      warnings.push({ section: "SMC", level: "warn",
        text: `All ${cands.length} active OBs are candidates (no EQL gate) — weak confluence` });
    }

    const pools = ltf.liquidity_pools || [];
    const eqhAbove = pools.filter(p => !p.swept && p.kind === "eqh" && p.level > price);
    if (eqhAbove.length > 0) {
      const nearest = Math.min(...eqhAbove.map(p => p.level));
      const pct = ((nearest / price - 1) * 100).toFixed(1);
      const fmtP = v => v < 10 ? v.toFixed(3) : v >= 1000 ? v.toLocaleString(undefined,{maximumFractionDigits:0}) : v.toFixed(2);
      warnings.push({ section: "SMC", level: "warn",
        text: `EQH at ${fmtP(nearest)} (+${pct}%) — sell-stop cluster above` });
    }
    const eqlBelow = pools.filter(p => !p.swept && p.kind === "eql" && p.level < price);
    if (eqlBelow.length > 0) {
      const nearest = Math.max(...eqlBelow.map(p => p.level));
      const pct = ((1 - nearest / price) * 100).toFixed(1);
      const fmtP = v => v < 10 ? v.toFixed(3) : v >= 1000 ? v.toLocaleString(undefined,{maximumFractionDigits:0}) : v.toFixed(2);
      warnings.push({ section: "SMC", level: "warn",
        text: `EQL at ${fmtP(nearest)} (-${pct}%) — buy-stop pool below` });
    }

    if (!alignment.includes("CONFLICTED") && gated.length >= 2 && ltf.current_state !== "UNDEFINED") {
      warnings.push({ section: "SMC", level: "ok",
        text: `Clean ${ltf.current_state} structure · ${gated.length} confirmed OBs — quality setup` });
    }
  }

  if (ghData && !ghData.error && Array.isArray(ghData.hot_zones) && ghData.hot_zones.length) {
    const zones = ghData.hot_zones;
    const above = zones.filter(z => z.price > price);
    const below = zones.filter(z => z.price < price);
    const atZone = zones.find(z => Math.abs(z.price - price) / price < 0.005);
    const ceilAbove = above.filter(z => z.bias === "ceiling");
    const floorBelow = below.filter(z => z.bias === "floor");

    if (atZone) {
      warnings.push({ section: "GH", level: "info",
        text: `Price at GH ${atZone.bias} zone — high-confluence reaction expected` });
    }
    if (ceilAbove.length >= 2) {
      warnings.push({ section: "GH", level: "warn",
        text: `${ceilAbove.length} of ${above.length} arcs above price are ceiling-biased — resistance wall` });
    }
    if (below.length > 0 && floorBelow.length === 0) {
      warnings.push({ section: "GH", level: "warn",
        text: "No GH floor support below current price — structural vacuum" });
    } else if (floorBelow.length >= 2) {
      warnings.push({ section: "GH", level: "ok",
        text: `${floorBelow.length} GH floor levels confirmed below — arc support` });
    }
    if (ghData.radius_endpoint?.price) {
      const re = ghData.radius_endpoint.price;
      if (Math.abs(re - price) / price < 0.025) {
        const fmtP = v => v < 10 ? v.toFixed(3) : v >= 1000 ? v.toLocaleString(undefined,{maximumFractionDigits:0}) : v.toFixed(2);
        warnings.push({ section: "GH", level: "info",
          text: `GH geometric midpoint at ${fmtP(re)} — macro pivot zone` });
      }
    }
  }

  if (xabcdData && !xabcdData.error) {
    const confirmed = xabcdData.confirmed || [];
    const forming   = xabcdData.forming   || [];
    const verdict   = asset?.verdict;

    const inPRZ = [
      ...confirmed.filter(p => p.prz != null && Math.abs(p.prz - price) / price < 0.02),
      ...forming.filter(p => p.prz_lo != null && p.prz_hi != null && price >= p.prz_lo * 0.98 && price <= p.prz_hi * 1.02),
    ];
    if (inPRZ.length > 0) {
      const names = [...new Set(inPRZ.map(p => p.pattern))].join(", ");
      warnings.push({ section: "NEX", level: "info",
        text: `XABCD PRZ active: ${names} — harmonic reaction zone` });
    }

    const aligned = confirmed.filter(p =>
      (verdict === "BUY" && p.direction === "bullish") ||
      (verdict === "SELL" && p.direction === "bearish")
    );
    if (aligned.length > 0) {
      warnings.push({ section: "NEX", level: "ok",
        text: `${aligned.map(p => p.pattern).join(", ")} confirmed — aligns with ${verdict}` });
    }

    const opposing = confirmed.filter(p =>
      (verdict === "BUY" && p.direction === "bearish") ||
      (verdict === "SELL" && p.direction === "bullish")
    );
    if (opposing.length > 0) {
      warnings.push({ section: "NEX", level: "danger",
        text: `${opposing.map(p => p.pattern).join(", ")} opposes ${verdict} verdict — pattern conflict` });
    }
  }

  if (asset) {
    if (asset.edge > 70 && (asset.rsi > 75 || asset.rsi < 25)) {
      warnings.push({ section: "NEX", level: "warn",
        text: `Edge ${asset.edge} but RSI ${asset.rsi} is extreme — await pullback before entry` });
    }
    const biasUp   = asset.bias?.includes("↑");
    const biasDown = asset.bias?.includes("↓");
    if (asset.verdict === "BUY" && biasDown) {
      warnings.push({ section: "NEX", level: "warn",
        text: `Micro bias ${asset.bias} conflicts with BUY signal — timing mismatch` });
    } else if (asset.verdict === "SELL" && biasUp) {
      warnings.push({ section: "NEX", level: "warn",
        text: `Micro bias ${asset.bias} conflicts with SELL signal — timing mismatch` });
    }

    const ltfState   = smcData?.ltf_smc?.current_state;
    const smcClean   = smcData && !smcData.alignment?.includes("CONFLICTED");
    const hasFloorGH = ghData?.hot_zones?.some(z => z.price < price && z.bias === "floor");
    if (asset.verdict === "BUY" && ltfState === "BULLISH" && biasUp && smcClean && hasFloorGH) {
      warnings.push({ section: "NEX", level: "ok",
        text: "SMC + GH + Verdict + Bias aligned bullish — multi-layer premium long" });
    } else if (asset.verdict === "SELL" && ltfState === "BEARISH" && biasDown && smcClean) {
      warnings.push({ section: "NEX", level: "ok",
        text: "SMC + Verdict + Bias aligned bearish — multi-layer premium short" });
    }
  }

  return warnings;
}

/* ── AnalysisPage — deep dive with tabs (Page 3) ────────────── */
const ANALYSIS_TABS = [
  { id: "smc",   label: "SMC STRUCTURE",  accent: "var(--cyan)",    hex: "#38bdf8" },
  { id: "gh",    label: "GEO HARMONIC",   accent: "var(--magenta)", hex: "#c084fc" },
  { id: "nexus", label: "NEXUS",          accent: "var(--amber)",   hex: "#f59e0b" },
];

function AnalysisPage({ asset, macroWarning, initialTab, onBack, manualStories = [] }) {
  const [tab, setTab] = useState(initialTab || "smc");
  const [tf, setTf] = useState("1H");
  const activeTabCfg = ANALYSIS_TABS.find(t => t.id === tab);

  const [smcData, setSmcData]       = useState(null);
  const [smcLoading, setSmcLoading] = useState(false);
  const [ghData, setGhData]         = useState(null);
  const [ghLoading, setGhLoading]   = useState(false);
  const [pineScript, setPineScript]   = useState(null);
  const [pineLoading, setPineLoading] = useState(false);
  const [pineError, setPineError]     = useState(null);
  const [pineOpen, setPineOpen]       = useState(false);
  const [xabcdData, setXabcdData]   = useState(null);
  const [xabcdLoading, setXabcdLoading] = useState(false);
  const [showEMA,   setShowEMA]   = useState(true);
  const [showVWAP,  setShowVWAP]  = useState(true);
  const [showStoch, setShowStoch] = useState(false);
  const [aiText, setAiText]   = useState(null);
  const [aiLoading, setAiLoading] = useState(false);
  const [aiError, setAiError]   = useState(null);
  const aiAbortRef = useRef(null);
  const [lensMode, setLensMode] = useState(1);
  const [activeOnly, setActiveOnly] = useState(false);
  const [hoveredElement, setHoveredElement] = useState(null);
  const [legendOpen, setLegendOpen] = useState(false);
  const [nexusTf, setNexusTf] = useState("1D");

  function cancelAI() {
    if (aiAbortRef.current) { aiAbortRef.current.abort(); aiAbortRef.current = null; }
  }

  /* reset all on symbol change */
  useEffect(() => {
    cancelAI();
    setSmcData(null); setGhData(null); setXabcdData(null);
    setPineScript(null); setPineLoading(false); setPineError(null);
    setAiText(null); setAiLoading(false); setAiError(null);
    setLensMode(1);
    setActiveOnly(false);
    setHoveredElement(null);
    setPineOpen(false);
  }, [asset.sym]);

  /* reset AI on tab change */
  useEffect(() => {
    cancelAI();
    setAiText(null); setAiLoading(false); setAiError(null);
  }, [tab]);

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

  /* load SMC for smc + nexus tabs */
  useEffect(() => {
    if (tab !== "smc" && tab !== "nexus") return;
    setSmcData(null); setSmcLoading(true);
    let cancelled = false;
    window.API.fetchSMC(asset.sym, tf).then(data => {
      if (!cancelled) { setSmcData(data); setSmcLoading(false); }
    });
    return () => { cancelled = true; };
  }, [asset.sym, tf, tab]);

  /* load GH for gh + nexus tabs */
  useEffect(() => {
    if (tab !== "gh" && tab !== "nexus") return;
    if (ghData && !ghData.error) return;
    setGhLoading(true);
    let cancelled = false;
    window.API.fetchGH(asset.sym).then(data => {
      if (!cancelled) { setGhData(data); setGhLoading(false); }
    });
    return () => { cancelled = true; };
  }, [asset.sym, tab]);

  /* load XABCD for gh + nexus tabs */
  useEffect(() => {
    if (tab !== "gh" && tab !== "nexus") return;
    if (xabcdData && !xabcdData.error) return;
    setXabcdLoading(true);
    let cancelled = false;
    window.API.fetchXABCD(asset.sym).then(data => {
      if (!cancelled) { setXabcdData(data); setXabcdLoading(false); }
    });
    return () => { cancelled = true; };
  }, [asset.sym, tab]);

  function handleFetchAI() {
    cancelAI();
    const controller = new AbortController();
    aiAbortRef.current = controller;
    setAiLoading(true); setAiText(null); setAiError(null);
    window.API.fetchAIBriefing(asset.sym, "swing", tab, controller.signal, manualStories).then(r => {
      if (r.aborted) return;
      aiAbortRef.current = null;
      setAiLoading(false);
      if (r.error) setAiError(r.error);
      else setAiText(r.text);
    });
  }

  const c = window.verdictColors(asset.verdict);
  const macroVal = macroWarning ?? window.MACRO.warning;
  const up = asset.chg >= 0;
  const fmt = v => v < 10 ? v.toFixed(3) : v < 1000 ? v.toFixed(2) : v.toLocaleString(undefined, { maximumFractionDigits: 2 });

  const showSMC   = tab === "smc";
  const showGH    = tab === "gh";
  const showXABCD = tab === "gh";

  const allWarnings = computeWarnings(smcData, ghData, xabcdData, asset);

  /* nexus calcs for trade panel */
  const dir = asset.verdict === "SELL" ? -1 : 1;
  const atr = asset.atr || 0;
  const nexusMode = nexusTf === "1H" ? "sniper" : nexusTf === "4H" ? "swing" : "long";
  const nexusMult = { sniper: 0.4, swing: 1.2, long: 3.0 }[nexusMode];
  const nexusHold = { sniper: "≤4h", swing: "3-10d", long: "1-3mo" }[nexusMode];
  const entry = asset.price;
  const stop  = asset.price - dir * atr * nexusMult;
  const tp1   = asset.price + dir * atr * nexusMult * 1.5;
  const tp2   = asset.price + dir * atr * nexusMult * 2.5;
  const rr    = (Math.abs(tp1 - entry) / (Math.abs(entry - stop) || 1)).toFixed(2);
  const action = asset.verdict === "SELL" ? "SHORT" : asset.verdict === "BUY" ? "LONG" : "STAND-BY";

  const TF_LIST = ["1H", "4H", "1D"];

  return (
    <div style={{ position: "absolute", inset: 0, background: "rgba(6,8,12,0.97)", backdropFilter: "blur(6px)", display: "flex", flexDirection: "column", zIndex: 30, animation: "fadeIn 200ms ease", overflowY: "auto" }}>

      {/* header with tabs */}
      <div style={{ height: 52, flex: "0 0 auto", borderBottom: "1px solid var(--line)", display: "flex", alignItems: "stretch", background: "var(--bg-2)" }}>
        <div style={{ display: "flex", alignItems: "center", padding: "0 16px", borderRight: "1px solid var(--line)" }}>
          <button onClick={onBack} style={{ display: "flex", alignItems: "center", gap: 6, padding: "6px 10px", background: "transparent", border: "1px solid var(--line-2)", color: "#FF6D00", cursor: "pointer" }}>
            <svg width="10" height="10" viewBox="0 0 10 10"><path d="M7 1 L3 5 L7 9" stroke="currentColor" strokeWidth="1.5" fill="none"/></svg>
            <span className="mono" style={{ fontSize: 13, letterSpacing: "0.16em" }}>{asset.sym}</span>
          </button>
        </div>

        <div style={{ display: "flex", alignItems: "stretch" }}>
          {ANALYSIS_TABS.map(t => {
            const active = tab === t.id;
            return (
              <button key={t.id} onClick={() => setTab(t.id)}
                style={{
                  padding: "0 22px",
                  background: active ? `${t.hex}14` : "transparent",
                  border: "none",
                  borderBottom: active ? `2px solid ${t.accent}` : "2px solid transparent",
                  color: active ? t.accent : "var(--ink)",
                  cursor: "pointer",
                  fontFamily: "'JetBrains Mono', monospace",
                  fontSize: 13, fontWeight: active ? 700 : 400,
                  letterSpacing: "0.16em",
                  transition: "all 140ms",
                }}>
                {t.label}
              </button>
            );
          })}
        </div>

        <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 14, padding: "0 18px", borderLeft: "1px solid var(--line)" }}>
          <span className="num" style={{ fontSize: 18, fontWeight: 600, color: "var(--ink)" }}>{fmt(asset.price)}</span>
          <span className="num" style={{ fontSize: 12, color: up ? "var(--buy)" : "var(--sell)" }}>{up ? "▲" : "▼"} {Math.abs(asset.chg).toFixed(2)}%</span>
          <div style={{ padding: "4px 10px", display: "flex", alignItems: "center", gap: 6, background: c.bg, border: `1px solid ${c.fg}50` }}>
            <window.Dot color={c.fg} size={5} blink={asset.verdict !== "WAIT"} />
            <span className="mono" style={{ fontSize: 13, color: c.fg, fontWeight: 600, letterSpacing: "0.14em" }}>{asset.verdict}</span>
          </div>
        </div>
      </div>

      {/* scrollable content */}
      <div style={{ flex: 1, minHeight: 0, overflowY: "auto" }}>

        {/* SMC + GH tabs: chart + alert strip + AI panel */}
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
                      <span className="mono" style={{ fontSize: 13, fontWeight: 600, letterSpacing: "0.1em" }}>{t}</span>
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
                            <span className="mono" style={{ fontSize: 13, fontWeight: 600, letterSpacing: "0.1em" }}>{label}</span>
                          </button>
                        );
                      })}
                    </div>
                    <button
                      onClick={() => setActiveOnly(a => !a)}
                      style={{
                        padding: "5px 10px",
                        background: activeOnly ? "#26a69a" : "transparent",
                        color: activeOnly ? "var(--bg-0)" : "#26a69a",
                        border: "1px solid #26a69a55",
                        cursor: "pointer",
                        marginLeft: 4,
                      }}
                    >
                      <span className="mono" style={{ fontSize: 13, fontWeight: 600, letterSpacing: "0.1em" }}>
                        ACTIVE {activeOnly ? "◆" : "○"}
                      </span>
                    </button>
                  </div>
                );
              })()}
            </div>
          </div>
        )}

        {tab !== "nexus" && (
          <div style={{ padding: "0 14px" }}>
            <div style={{ display: "flex", gap: 10, alignItems: "flex-start" }}>
              <div style={{ flex: 1, background: "var(--bg-2)", border: "1px solid var(--line)", padding: 10 }}>
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
                  activeOnly={activeOnly}
                  onHover={setHoveredElement} />
              </div>
              {tab === "smc" && (
                <window.HoverContextCard el={hoveredElement} lensMode={lensMode} />
              )}
            </div>
          </div>
        )}

        {/* SMC key — collapsible legend below chart on SMC tab */}
        {tab === "smc" && smcData && !smcData.error && (
          <div style={{ padding: "10px 14px 0 14px" }}>
            <button onClick={() => setLegendOpen(o => !o)} style={{
              width: "100%", display: "flex", alignItems: "center", justifyContent: "space-between",
              padding: "7px 14px", background: "var(--bg-2)", border: "1px solid var(--line)",
              color: "var(--ink)", cursor: "pointer",
            }}>
              <span className="mono" style={{ fontSize: 11, letterSpacing: "0.18em" }}>SMC LEGEND</span>
              <span style={{ fontSize: 11 }}>{legendOpen ? "▲" : "▼"}</span>
            </button>
            {legendOpen && <window.SMCLegend />}
          </div>
        )}

        {/* GH tab: circle coordinate table for TV Fib Circles placement */}
        {tab === "gh" && ghData && !ghData.error && Array.isArray(ghData.gh_circles) && ghData.gh_circles.length > 0 && (
          <div style={{ padding: "14px 14px 0 14px" }}>
            <div style={{ background: "var(--bg-2)", border: "1px solid var(--line)", borderLeft: "3px solid var(--magenta)" }}>
              <div style={{ padding: "10px 16px", borderBottom: "1px solid var(--line)" }}>
                <window.Label color="var(--magenta)">CIRCLE COORDINATES · TV FIB CIRCLES</window.Label>
                <div className="mono" style={{ fontSize: 12, color: "var(--ink-4)", marginTop: 4, letterSpacing: "0.08em" }}>
                  Place 2 concurrent Fib Circles in TradingView: one ATL → Radius Endpoint, one ATH → Radius Endpoint
                </div>
              </div>
              <div style={{ padding: "10px 16px", overflowX: "auto" }}>
                <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12, fontFamily: "'JetBrains Mono', monospace" }}>
                  <thead>
                    <tr style={{ borderBottom: "1px solid var(--line-2)" }}>
                      {["CIRCLE", "ORIGIN", "ANCHOR DATE", "ANCHOR PRICE", "RADIUS ENDPOINT DATE", "RADIUS ENDPOINT PRICE"].map(h => (
                        <th key={h} style={{ padding: "4px 10px", textAlign: "left", color: "var(--ink-4)", letterSpacing: "0.1em", fontWeight: 700, whiteSpace: "nowrap" }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {ghData.gh_circles.map((c, i) => (
                      <tr key={i} style={{ borderBottom: "1px solid var(--bg-3)" }}>
                        <td style={{ padding: "5px 10px", color: "var(--ink)", letterSpacing: "0.06em" }}>{c.label}</td>
                        <td style={{ padding: "5px 10px", color: c.origin === "floor" ? "var(--buy)" : "var(--sell)", letterSpacing: "0.06em" }}>
                          {c.origin === "floor" ? "▲ FLOOR" : "▼ CEIL"}
                        </td>
                        <td style={{ padding: "5px 10px", color: "var(--cyan)", letterSpacing: "0.06em" }}>{c.cx_ts || "—"}</td>
                        <td style={{ padding: "5px 10px", color: "var(--ink-2)", letterSpacing: "0.06em" }}>{c.center_price?.toLocaleString()}</td>
                        <td style={{ padding: "5px 10px", color: "var(--ink-2)", letterSpacing: "0.06em" }}>{ghData.radius_endpoint?.ts || "—"}</td>
                        <td style={{ padding: "5px 10px", color: "var(--ink-2)", letterSpacing: "0.06em" }}>{ghData.radius_endpoint?.price?.toLocaleString()}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* NEXUS tab: compact chart + trade rec side by side */}
        {tab === "nexus" && (
          <div style={{ padding: "14px 14px 0 14px" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 10, padding: "6px 10px", background: "var(--bg-2)", border: "1px solid var(--line)" }}>
              <window.Label>TF</window.Label>
              <div style={{ display: "flex", gap: 0, border: "1px solid var(--line-2)" }}>
                {TF_LIST.map((t, i) => {
                  const active = nexusTf === t;
                  return (
                    <button key={t} onClick={() => setNexusTf(t)} style={{ padding: "5px 12px", background: active ? activeTabCfg.accent : "transparent", color: active ? "var(--bg-0)" : "var(--ink-2)", border: "none", borderLeft: i ? "1px solid var(--line-2)" : "none", cursor: "pointer" }}>
                      <span className="mono" style={{ fontSize: 13, fontWeight: 600, letterSpacing: "0.1em" }}>{t}</span>
                    </button>
                  );
                })}
              </div>
            </div>
          </div>
        )}
        {tab === "nexus" && (
          <div style={{ padding: "0 14px 0 14px", display: "grid", gridTemplateColumns: "1fr 300px", gap: 12 }}>
            <div style={{ background: "var(--bg-2)", border: "1px solid var(--line)", padding: 10 }}>
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
            </div>
            <aside style={{ background: "var(--bg-2)", border: "1px solid var(--line)", display: "flex", flexDirection: "column", position: "relative", overflow: "hidden" }}>
              <window.CornerTicks color={c.fg} />
              <div style={{ padding: "10px 12px", borderBottom: "1px solid var(--line)", background: `linear-gradient(180deg, ${c.bg}, transparent)` }}>
                <window.Label color={c.fg} style={{ marginBottom: 4 }}>TRADE SETUP</window.Label>
                <div style={{ display: "flex", alignItems: "baseline", gap: 10 }}>
                  <span className="mono" style={{ fontSize: 20, fontWeight: 700, color: c.fg, letterSpacing: "0.1em" }}>{action}</span>
                  <span className="mono" style={{ fontSize: 11, color: "var(--ink-3)", letterSpacing: "0.14em" }}>{nexusMode.toUpperCase()}</span>
                </div>
              </div>
              <div style={{ padding: "10px 12px", display: "flex", flexDirection: "column", gap: 6, borderBottom: "1px solid var(--line)" }}>
                <window.Level k="ENTRY"    v={fmt(entry)} c="var(--cyan)" />
                <window.Level k="STOP"     v={fmt(stop)}  c="var(--sell)" />
                <window.Level k="TARGET 1" v={fmt(tp1)}   c="var(--buy)" />
                <window.Level k="TARGET 2" v={fmt(tp2)}   c="var(--buy)" />
              </div>
              <div style={{ padding: "10px 12px", display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, flex: 1 }}>
                <window.KV k="R:R"  v={rr}               c="var(--ink)" />
                <window.KV k="HOLD" v={nexusHold}         c="var(--ink-2)" />
                <window.KV k="BIAS" v={asset.bias}        c={c.fg} />
                <window.KV k="EDGE" v={`${asset.edge}/100`} c={c.fg} />
              </div>
            </aside>
          </div>
        )}

        {/* Nexus metrics bar */}
        {tab === "nexus" && (
          <div style={{ padding: "10px 14px 0 14px", display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 8 }}>
            <window.MetricTile k="EDGE SCORE" v={asset.edge} suffix="/100" color={c.fg} bar={asset.edge} />
            <window.MetricTile k="RSI(14)" v={asset.rsi} suffix="" color="var(--cyan)" bar={asset.rsi} />
            <window.MetricTile k="ATR" v={asset.atr} suffix="" color="var(--magenta)" />
            <window.MetricTile k="VOL · 24H" v={asset.vol} suffix="x" color="var(--amber)" />
            <window.MetricTile k="BIAS" v={asset.bias} suffix="" color={c.fg} text />
          </div>
        )}

        {/* Alert strip */}
        {allWarnings.length > 0 && (
          <div style={{ padding: "14px 14px 0 14px" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8 }}>
              <window.Label>ALERTS & EXCEPTIONS</window.Label>
              <span className="mono" style={{ fontSize: 12, color: "var(--ink-4)", letterSpacing: "0.14em" }}>{allWarnings.length} ACTIVE</span>
            </div>
            <window.AlertStrip warnings={allWarnings} />
          </div>
        )}

        {/* AI Analysis panel */}
        <div style={{ padding: "14px 14px 0 14px" }}>
          <div style={{ background: "var(--bg-2)", border: `1px solid ${activeTabCfg.hex}30`, borderLeft: `3px solid ${activeTabCfg.accent}` }}>
            <div style={{ padding: "14px 18px", borderBottom: "1px solid var(--line)", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
              <div>
                <window.Label color={activeTabCfg.accent}>AI ANALYSIS</window.Label>
                <div className="mono" style={{ fontSize: 13, color: "var(--ink-2)", marginTop: 4, letterSpacing: "0.1em" }}>
                  {activeTabCfg.label} · {asset.sym}
                </div>
              </div>
              <button onClick={handleFetchAI} disabled={aiLoading}
                style={{
                  padding: "9px 18px",
                  background: aiText ? "rgba(245,158,11,0.1)" : "transparent",
                  border: `1px solid ${aiText ? "var(--amber)" : "var(--line-2)"}`,
                  color: aiLoading ? "var(--wait)" : "var(--amber)",
                  cursor: aiLoading ? "default" : "pointer",
                  fontFamily: "'JetBrains Mono', monospace",
                  fontSize: 13, letterSpacing: "0.16em", fontWeight: 700,
                }}>
                {aiLoading ? "◇ ANALYZING…" : aiText ? "◆ REFRESH" : "◆ GENERATE BRIEFING"}
              </button>
            </div>
            <div style={{ padding: "16px 18px", minHeight: 80 }}>
              {aiError && <div style={{ fontSize: 13, color: "var(--sell)", letterSpacing: "0.06em", marginBottom: 8 }}>⚠ {aiError}</div>}
              {aiText ? (
                <div style={{ fontSize: 12, color: "var(--ink-2)", lineHeight: 1.75, whiteSpace: "pre-wrap", fontFamily: "'JetBrains Mono', monospace", letterSpacing: "0.02em" }}>
                  {aiText}
                </div>
              ) : !aiLoading ? (
                <div style={{ fontSize: 13, color: "var(--ink-4)", fontFamily: "'JetBrains Mono', monospace", letterSpacing: "0.08em", lineHeight: 1.6 }}>
                  Click GENERATE BRIEFING for a focused {activeTabCfg.label} analysis from Banshee's AI co-pilot. Incorporates live overlay data, alerts, and macro context.
                </div>
              ) : (
                <div style={{ fontSize: 13, color: "var(--wait)", fontFamily: "'JetBrains Mono', monospace", letterSpacing: "0.08em" }} className="blink">
                  ◇ Synthesizing {activeTabCfg.label} context…
                </div>
              )}
            </div>
          </div>
        </div>

        {/* GH tab: Pine Script generator panel (collapsible, below AI analysis) */}
        {tab === "gh" && (
          <div style={{ padding: "14px 14px 20px 14px" }}>
            <div style={{ background: "var(--bg-2)", border: "1px solid var(--line)", borderLeft: "3px solid var(--amber)" }}>
              <div style={{ padding: "12px 16px", borderBottom: pineOpen ? "1px solid var(--line)" : "none", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                <button onClick={() => setPineOpen(o => !o)}
                  style={{ background: "none", border: "none", padding: 0, cursor: "pointer", display: "flex", alignItems: "center", gap: 8 }}>
                  <window.Label color="var(--amber)">PINE SCRIPT GENERATOR</window.Label>
                  <span className="mono" style={{ fontSize: 11, color: "var(--amber)", letterSpacing: "0.1em" }}>{pineOpen ? "▲" : "▼"}</span>
                </button>
                {pineOpen && (
                  <button
                    onClick={() => {
                      if (pineLoading) return;
                      setPineLoading(true); setPineError(null); setPineScript(null);
                      window.API.fetchGHPine(asset.sym)
                        .then(d => {
                          if (d.error) { setPineError(d.error); }
                          else { setPineScript(d.pine_script); }
                        })
                        .catch(e => setPineError(e.message))
                        .finally(() => setPineLoading(false));
                    }}
                    disabled={pineLoading}
                    style={{
                      padding: "7px 16px",
                      background: pineScript ? "rgba(245,158,11,0.1)" : "transparent",
                      border: "1px solid " + (pineScript ? "var(--amber)" : "var(--line-2)"),
                      color: pineLoading ? "var(--wait)" : "var(--amber)",
                      cursor: pineLoading ? "default" : "pointer",
                      fontFamily: "'JetBrains Mono', monospace",
                      fontSize: 12, letterSpacing: "0.16em", fontWeight: 700,
                    }}>
                    {pineLoading ? "◇ GENERATING…" : pineScript ? "◆ REGENERATE" : "◆ GENERATE PINE SCRIPT"}
                  </button>
                )}
              </div>
              {pineOpen && (pineScript || pineError) && (
                <div style={{ padding: "12px 16px" }}>
                  {pineError && (
                    <div style={{ fontSize: 12, color: "var(--sell)", letterSpacing: "0.06em" }}>⚠ {pineError}</div>
                  )}
                  {pineScript && (
                    <div>
                      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8 }}>
                        <span className="mono" style={{ fontSize: 11, color: "var(--ink-4)", letterSpacing: "0.1em" }}>
                          PASTE INTO TRADINGVIEW PINE EDITOR · 1D CHART ONLY
                        </span>
                        <button
                          onClick={() => navigator.clipboard.writeText(pineScript)}
                          style={{
                            padding: "4px 12px",
                            background: "var(--bg-3)",
                            border: "1px solid var(--line-2)",
                            color: "var(--ink-2)",
                            cursor: "pointer",
                            fontFamily: "'JetBrains Mono', monospace",
                            fontSize: 11, letterSpacing: "0.12em",
                          }}>
                          COPY
                        </button>
                      </div>
                      <pre style={{
                        margin: 0, padding: "10px 12px",
                        background: "var(--bg-3)", border: "1px solid var(--line-2)",
                        fontSize: 11, color: "var(--ink-2)",
                        fontFamily: "'JetBrains Mono', monospace",
                        lineHeight: 1.6, overflowX: "auto",
                        maxHeight: 280, overflowY: "auto", whiteSpace: "pre",
                      }}>
                        {pineScript}
                      </pre>
                    </div>
                  )}
                </div>
              )}
              {pineOpen && !pineScript && !pineError && !pineLoading && (
                <div style={{ padding: "12px 16px" }}>
                  <div style={{ fontSize: 12, color: "var(--ink-4)", fontFamily: "'JetBrains Mono', monospace", letterSpacing: "0.08em" }}>
                    Generates a paste-ready Pine Script v5 with all GH circles as polylines. 1D chart only.
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Bottom padding for non-GH tabs */}
        {tab !== "gh" && <div style={{ paddingBottom: 20 }} />}
      </div>
    </div>
  );
}

export default AnalysisPage;
