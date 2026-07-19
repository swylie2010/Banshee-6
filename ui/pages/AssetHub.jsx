const { useState, useEffect, useRef } = React;

const MODES = [
  { id: "sniper", name: "SNIPER",    sub: "15m–1H intraday" },
  { id: "swing",  name: "SWING",     sub: "1H–1D positional" },
  { id: "long",   name: "LONG TERM", sub: "1W–1M secular" },
];
const MODE_TF = {
  sniper: ["15m","1H"],
  swing:  ["1H","4H","1D"],
  long:   ["1D","1W"],
};

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

/* ── AssetHub — standard overview (Page 2) ─────────────────── */
function AssetHub({ asset, onBack, macroWarning, onDeepDive, onGoRiskSimulate }) {
  const isMobile = window.useIsMobile();
  const [mode, setMode] = useState("swing");
  const [tf, setTf] = useState("1H");
  const [simPanel, setSimPanel]   = useState(false);
  const [simStatus, setSimStatus] = useState("idle"); // "idle"|"loading"|"success"|"error"
  const [simError,  setSimError]  = useState(null);
  const [execPanel, setExecPanel] = useState(false);
  const [showEMA,   setShowEMA]   = useState(true);
  const [showVWAP,  setShowVWAP]  = useState(true);
  const [showStoch, setShowStoch] = useState(false);
  const panelRef = useRef(null);
  useEffect(() => { setTf(MODE_TF[mode][1] || MODE_TF[mode][0]); }, [mode]);
  useEffect(() => {
    if (!simPanel && !execPanel) return;
    function handler(e) {
      if (panelRef.current && !panelRef.current.contains(e.target)) {
        setSimPanel(false);
        setExecPanel(false);
      }
    }
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [simPanel, execPanel]);

  const c = window.verdictColors(asset.verdict);
  const macroVal = macroWarning ?? window.MACRO.warning;
  const up = asset.chg >= 0;
  const dir = asset.verdict === "SELL" ? -1 : 1;
  const atr = asset.atr || 0;
  const sniperMult = { sniper: 0.4, swing: 1.2, long: 3.0 }[mode];
  const entry = asset.price;
  const stop  = asset.price - dir * atr * sniperMult;
  const tp1   = asset.price + dir * atr * sniperMult * 1.5;
  const tp2   = asset.price + dir * atr * sniperMult * 2.5;
  const rrNum = Math.abs(tp1 - entry) / (Math.abs(entry - stop) || 1);
  const rr    = rrNum.toFixed(2);
  const fmt = v => v < 10 ? v.toFixed(3) : v < 1000 ? v.toFixed(2) : v.toLocaleString(undefined, { maximumFractionDigits: 2 });
  const action = asset.verdict === "SELL" ? "SHORT" : asset.verdict === "BUY" ? "LONG" : "STAND-BY";
  const conf = Math.round(asset.edge * (1 - Math.abs(50 - asset.rsi) / 100));
  const horizon = { sniper: "minutes — hours", swing: "days — weeks", long: "weeks — months" }[mode];
  const sizeR = { sniper: "0.5R", swing: "1.0R", long: "1.5R" }[mode];

  async function handleSimulateNow() {
    setSimStatus("loading");
    setSimError(null);
    const isL = dir > 0;
    const result = await window.API.journalOpen({
      symbol:       asset.sym,
      direction:    isL ? "long" : "short",
      entry_price:  entry,
      stop_price:   stop,
      target_price: tp1,
      position_usd: 1000,
      verdict:      asset.verdict,
      edge:         String(asset.edge ?? ""),
      mode:         mode,
      notes:        "Quick simulate from AssetHub",
    });
    if (result?.error) {
      setSimStatus("error");
      setSimError(result.error);
    } else {
      setSimStatus("success");
    }
  }

  useEffect(() => {
    if (simStatus !== "success") return;
    const id = setTimeout(() => { setSimPanel(false); setSimStatus("idle"); }, 2000);
    return () => clearTimeout(id);
  }, [simStatus]);

  return (
    <div style={{ position: "absolute", inset: 0, background: "rgba(6,8,12,0.97)", backdropFilter: "blur(6px)", display: "flex", flexDirection: "column", zIndex: 30, animation: "fadeIn 200ms ease" }}>
      <style>{`@keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }`}</style>

      {/* header */}
      <div style={{ height: isMobile ? "auto" : 56, minHeight: isMobile ? 56 : undefined, padding: isMobile ? "8px 10px" : "0 18px", flex: "0 0 auto", borderBottom: "1px solid var(--line)", display: "flex", alignItems: "center", flexWrap: isMobile ? "wrap" : "nowrap", gap: isMobile ? 10 : 18, background: "var(--bg-2)" }}>
        <button onClick={onBack} style={{ display: "flex", alignItems: "center", gap: 6, padding: "6px 10px", background: "transparent", border: "1px solid var(--line-2)", color: "#FF6D00", cursor: "pointer", clipPath: "polygon(8px 0, 100% 0, calc(100% - 8px) 100%, 0 100%)" }}>
          <svg width="10" height="10" viewBox="0 0 10 10"><path d="M7 1 L3 5 L7 9" stroke="currentColor" strokeWidth="1.5" fill="none"/></svg>
          <span className="mono" style={{ fontSize: 13, letterSpacing: "0.16em" }}>GRID</span>
        </button>
        <div style={{ width: 1, height: 28, background: "var(--line)" }} />
        <div style={{ display: "flex", alignItems: "baseline", gap: 10 }}>
          <span className="mono" style={{ fontSize: 22, fontWeight: 700, letterSpacing: "0.06em", color: "var(--ink)" }}>{asset.sym}</span>
          <span className="mono" style={{ fontSize: 13, color: "var(--ink-3)", letterSpacing: "0.12em" }}>{asset.name} · {asset.pair}</span>
          <window.Tag border="var(--line-2)" style={{ fontSize: 12 }}>{asset.cls}</window.Tag>
        </div>
        <div style={{ display: "flex", alignItems: "baseline", gap: 8, marginLeft: "auto" }}>
          <span className="num" style={{ fontSize: 24, fontWeight: 600, color: "var(--ink)", lineHeight: 1 }}>{fmt(asset.price)}</span>
          <span className="num" style={{ fontSize: 14, color: up ? "var(--buy)" : "var(--sell)" }}>{up ? "▲" : "▼"} {Math.abs(asset.chg).toFixed(2)}%</span>
        </div>
        <div style={{ padding: "6px 12px", display: "flex", alignItems: "center", gap: 8, background: c.bg, border: `1px solid ${c.fg}50`, clipPath: "polygon(8px 0, 100% 0, calc(100% - 8px) 100%, 0 100%)" }}>
          <window.Dot color={c.fg} blink={asset.verdict !== "WAIT"} />
          <span className="mono" style={{ fontSize: 12, color: c.fg, fontWeight: 600, letterSpacing: "0.18em" }}>VERDICT · {asset.verdict}</span>
        </div>
      </div>

      {/* macro bar */}
      <div style={{ padding: "10px 18px", borderBottom: "1px solid var(--line)", background: "var(--bg-1)", flex: "0 0 auto" }}>
        <window.PowerBar value={macroVal} segments={36} />
      </div>

      {/* data-quality caveats (thin history, blank timeframes, extreme momentum).
          A silent read on a newly-listed ticker looks like confidence it doesn't
          have — surface the flags the engine already computed. */}
      {(() => {
        const cards = window.radarDataCards(asset.warnings);
        return cards.length ? (
          <div style={{ padding: "10px 18px 0 18px", flex: "0 0 auto" }}>
            <window.AlertStrip warnings={cards} />
          </div>
        ) : null;
      })()}

      {/* main grid: chart left, trade rec right */}
      <div style={{
        flex: 1,
        minHeight: isMobile ? undefined : 0,
        display: "grid",
        gridTemplateColumns: isMobile ? "1fr" : "minmax(0, 1fr) 300px",
        gap: 12,
        padding: "12px 12px 0 12px",
        overflowY: isMobile ? "auto" : "visible",
        WebkitOverflowScrolling: isMobile ? "touch" : undefined,
      }}>

        {/* left: mode/TF + chart + metrics */}
        <div style={{ display: "flex", flexDirection: "column", gap: 10, minWidth: 0 }}>
          <div style={{ padding: "8px 12px", background: "var(--bg-2)", border: "1px solid var(--line)", display: "flex", alignItems: "center", gap: 14, flex: "0 0 auto" }}>
            <window.Label>MODE</window.Label>
            <div style={{ display: "flex", gap: 0, border: "1px solid var(--line-2)" }}>
              {MODES.map((m, i) => {
                const active = mode === m.id;
                return (
                  <button key={m.id} onClick={() => setMode(m.id)} style={{ padding: "7px 14px", background: active ? "var(--cyan)" : "transparent", color: active ? "var(--bg-0)" : "var(--ink-2)", border: "none", borderLeft: i ? "1px solid var(--line-2)" : "none", cursor: "pointer", display: "flex", flexDirection: "column", gap: 2, alignItems: "flex-start" }}>
                    <span className="mono" style={{ fontSize: 13, fontWeight: 700, letterSpacing: "0.16em" }}>{m.name}</span>
                    <span className="mono" style={{ fontSize: 11, opacity: 0.7, letterSpacing: "0.1em" }}>{m.sub}</span>
                  </button>
                );
              })}
            </div>
            <div style={{ flex: 1 }} />
            <window.Label>TF</window.Label>
            <div style={{ display: "flex", gap: 0, border: "1px solid var(--line-2)" }}>
              {window.TIMEFRAMES.map((t, i) => {
                const enabled = MODE_TF[mode].includes(t);
                const active = tf === t;
                return (
                  <button key={t} onClick={() => enabled && setTf(t)} disabled={!enabled} style={{ padding: "6px 10px", background: active ? "var(--cyan)" : "transparent", color: active ? "var(--bg-0)" : enabled ? "var(--ink-2)" : "var(--ink-4)", border: "none", borderLeft: i ? "1px solid var(--line-2)" : "none", cursor: enabled ? "pointer" : "not-allowed", opacity: enabled ? 1 : 0.4 }}>
                    <span className="mono" style={{ fontSize: 13, fontWeight: 600, letterSpacing: "0.1em" }}>{t}</span>
                  </button>
                );
              })}
            </div>
          </div>

          <div style={{ position: "relative", ...(isMobile ? { flex: "0 0 auto", height: 300 } : { flex: 1, minHeight: 0 }), background: "var(--bg-2)", border: "1px solid var(--line)", padding: 10 }}>
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
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 8, flex: "0 0 auto" }}>
            <window.MetricTile k="EDGE SCORE" v={asset.edge} suffix="/100" color={c.fg} bar={asset.edge} />
            <window.MetricTile k="RSI(14)" v={asset.rsi} suffix="" color="var(--cyan)" bar={asset.rsi} />
            <window.MetricTile k="ATR" v={asset.atr} suffix="" color="var(--magenta)" />
            <window.MetricTile k="VOL · 24H" v={asset.vol} suffix="x" color="var(--amber)" />
            <window.MetricTile k="BIAS" v={asset.bias} suffix="" color={c.fg} text />
          </div>
        </div>

        {/* right: trade recommendation */}
        <aside style={{ background: "var(--bg-2)", border: "1px solid var(--line)", display: "flex", flexDirection: "column", position: "relative", ...(isMobile ? { overflow: "visible" } : { overflow: "hidden", minHeight: 0 }) }}>
          <window.CornerTicks color={c.fg} />
          <div style={{ padding: "12px 14px", borderBottom: "1px solid var(--line)", background: `linear-gradient(180deg, ${c.bg}, transparent)`, flex: "0 0 auto" }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 4 }}>
              <window.Label color={c.fg}>TRADE RECOMMENDATION</window.Label>
              <window.Tag border={`${c.fg}40`} color={c.fg} style={{ fontSize: 11 }}>{mode.toUpperCase()}</window.Tag>
            </div>
            <div style={{ display: "flex", alignItems: "baseline", gap: 8 }}>
              <span className="mono" style={{ fontSize: 22, fontWeight: 700, color: c.fg, letterSpacing: "0.1em" }}>{action}</span>
              <span className="mono" style={{ fontSize: 13, color: "var(--ink-3)", letterSpacing: "0.14em" }}>· {horizon}</span>
            </div>
          </div>
          <div style={{ padding: "12px 14px", display: "flex", flexDirection: "column", gap: 8, borderBottom: "1px solid var(--line)", flex: "0 0 auto" }}>
            <window.Level k="ENTRY" v={fmt(entry)} c="var(--cyan)" />
            <window.Level k="STOP" v={fmt(stop)} c="var(--sell)" />
            <window.Level k="TARGET 1" v={fmt(tp1)} c="var(--buy)" />
            <window.Level k="TARGET 2" v={fmt(tp2)} c="var(--buy)" />
          </div>
          <div style={{ padding: "12px 14px", display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, borderBottom: "1px solid var(--line)", flex: "0 0 auto" }}>
            <window.KV k="R:R" v={rr} c="var(--ink)" />
            <window.KV k="SIZE" v={sizeR} c="var(--ink)" />
            <window.KV k="CONFIDENCE" v={`${conf}%`} c={c.fg} />
            <window.KV k="HOLD" v={mode === "sniper" ? "≤4h" : mode === "swing" ? "3-10d" : "1-3mo"} c="var(--ink-2)" />
          </div>
          <div style={{ padding: "12px 14px", display: "flex", flexDirection: "column", gap: 6, flex: 1, minHeight: 0, overflowY: "auto" }}>
            <window.Label>SIGNAL CHECKLIST</window.Label>
            {[
              { ok: asset.edge > 60,                   t: `Edge ≥ 60 (cur ${asset.edge})` },
              { ok: asset.rsi > 30 && asset.rsi < 70,  t: `RSI in band (cur ${asset.rsi})` },
              { ok: (asset.bias?.includes("↑") && dir > 0) || (asset.bias?.includes("↓") && dir < 0) || asset.bias?.includes("→"), t: `Bias aligns verdict (${asset.bias ?? "—"})` },
              { ok: macroVal < 70,                      t: `Macro risk safe (${macroVal})` },
              { ok: !asset.volume?.includes("SELLING"), t: `Volume: ${asset.volume ?? "—"}` },
              { ok: (asset.session_weight ?? 1) >= 0.7, t: `Session weight (${(asset.session_weight ?? 1).toFixed(2)}x)` },
            ].map((row, i) => (
              <div key={i} style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <span style={{ width: 14, height: 14, display: "inline-flex", alignItems: "center", justifyContent: "center", border: `1px solid ${row.ok ? "var(--buy)" : "var(--ink-4)"}`, color: row.ok ? "var(--buy)" : "var(--ink-4)", fontSize: 12 }}>
                  {row.ok ? "✓" : "·"}
                </span>
                <span className="mono" style={{ fontSize: 13, color: row.ok ? "var(--ink)" : "var(--ink-3)", letterSpacing: "0.06em" }}>{row.t}</span>
              </div>
            ))}
          </div>
          <div style={{ padding: 12, display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, borderTop: "1px solid var(--line)", background: "var(--bg-1)", flex: "0 0 auto" }}>
            <button
              onClick={() => { setExecPanel(true); setSimPanel(false); }}
              style={{ padding: "10px 12px", background: c.fg, color: "var(--bg-0)", border: "none", cursor: "pointer", fontWeight: 700, letterSpacing: "0.16em", clipPath: "polygon(8px 0, 100% 0, calc(100% - 8px) 100%, 0 100%)" }}
              className="mono"
            >EXECUTE</button>
            <button
              onClick={() => { setSimPanel(true); setExecPanel(false); setSimStatus("idle"); setSimError(null); }}
              style={{ padding: "10px 12px", background: "transparent", color: "var(--ink-2)", border: "1px solid var(--line-2)", cursor: "pointer", fontWeight: 600, letterSpacing: "0.16em", clipPath: "polygon(8px 0, 100% 0, calc(100% - 8px) 100%, 0 100%)" }}
              className="mono"
            >SIMULATE</button>
          </div>

          {/* Simulate confirmation panel */}
          {simPanel && (
            <div ref={panelRef} style={{ position: "absolute", bottom: 0, left: 0, right: 0, padding: "14px 16px", borderTop: "1px solid var(--line)", background: "var(--bg-1)", zIndex: 5 }}>
              {simStatus === "success" ? (
                <div className="mono" style={{ textAlign: "center", fontSize: 13, color: "var(--buy)", letterSpacing: "0.12em", padding: "8px 0" }}>◆ Paper trade logged</div>
              ) : (
                <>
                  <div className="mono" style={{ fontSize: 13, color: "var(--ink)", fontWeight: 600, letterSpacing: "0.12em", marginBottom: 6 }}>
                    SIMULATE TRADE FOR {asset.sym}?
                  </div>
                  <div className="mono" style={{ fontSize: 12, color: "var(--ink-3)", letterSpacing: "0.08em", marginBottom: 10 }}>
                    Entry {fmt(entry)} · Stop {fmt(stop)} · $1,000
                  </div>
                  {simStatus === "error" && (
                    <div className="mono" style={{ fontSize: 12, color: "var(--sell)", marginBottom: 8 }}>{simError}</div>
                  )}
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
                    <button
                      onClick={handleSimulateNow}
                      disabled={simStatus === "loading"}
                      className="mono"
                      style={{ padding: "9px 10px", background: "var(--cyan)", color: "var(--bg-0)", border: "none", cursor: simStatus === "loading" ? "wait" : "pointer", fontWeight: 700, fontSize: 12, letterSpacing: "0.14em", opacity: simStatus === "loading" ? 0.6 : 1 }}
                    >
                      {simStatus === "loading" ? "◇ LOGGING…" : "SIMULATE NOW"}
                    </button>
                    <button
                      onClick={() => { setSimPanel(false); if (onGoRiskSimulate) onGoRiskSimulate(); }}
                      className="mono"
                      style={{ padding: "9px 10px", background: "transparent", color: "var(--ink-2)", border: "1px solid var(--line-2)", cursor: "pointer", fontWeight: 600, fontSize: 12, letterSpacing: "0.12em" }}
                    >
                      OPEN RISK DESK
                    </button>
                  </div>
                </>
              )}
            </div>
          )}

          {/* Execute not-enabled message */}
          {execPanel && !simPanel && (
            <div ref={panelRef} style={{ position: "absolute", bottom: 0, left: 0, right: 0, padding: "14px 16px", borderTop: "1px solid var(--line)", background: "var(--bg-1)", zIndex: 5 }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                <div>
                  <div className="mono" style={{ fontSize: 13, color: "var(--ink)", marginBottom: 6, letterSpacing: "0.08em" }}>
                    Direct broker execution is not enabled.
                  </div>
                  <div className="mono" style={{ fontSize: 12, color: "var(--ink-3)", letterSpacing: "0.06em" }}>
                    Use Simulate to log paper trades in the journal.
                  </div>
                </div>
                <button
                  onClick={() => setExecPanel(false)}
                  style={{ background: "none", border: "none", color: "var(--ink-3)", cursor: "pointer", fontSize: 16, padding: "0 0 0 12px", lineHeight: 1 }}
                >✕</button>
              </div>
            </div>
          )}
        </aside>
      </div>

      {/* deep dive navigation cards */}
      <div style={{ display: "grid", gridTemplateColumns: isMobile ? "1fr" : "1fr 1fr 1fr", gap: 8, padding: "8px 12px 10px 12px", flex: "0 0 auto" }}>
        <window.DeepDiveCard icon="◈" title="SMC STRUCTURE" sub="Order blocks · FVGs · BOS/CHoCH · Liquidity pools · HTF/LTF alignment" accent="var(--cyan)" onDeepDive={() => onDeepDive("smc")} />
        <window.DeepDiveCard icon="◎" title="GEO HARMONIC" sub="Fibonacci arc intersections · XABCD patterns · PRZ zones · Fib cycles" accent="var(--magenta)" onDeepDive={() => onDeepDive("gh")} />
        <window.DeepDiveCard icon="◆" title="NEXUS SYNTHESIS" sub="Full AI briefing · Cross-system confluence · Trade signal synthesis" accent="var(--amber)" onDeepDive={() => onDeepDive("nexus")} />
      </div>
    </div>
  );
}

export default AssetHub;
