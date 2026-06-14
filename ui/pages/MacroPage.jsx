const { useState } = React;

/* ── MacroPage — full macro environment view (Page 4) ──────── */
const MACRO_SENSOR_ROWS = [
  [
    { key: "vix",    label: "VIX FEAR",           unit: "" },
    { key: "skew",   label: "TAIL RISK SKEW",      unit: "" },
    { key: "bonds",  label: "BONDS 5D (TLT)",      unit: "%" },
    { key: "credit", label: "CREDIT STRESS (HYG)", unit: "%" },
  ],
  [
    { key: "dxy",     label: "DXY DOLLAR 5D",       unit: "%" },
    { key: "curve",   label: "YIELD CURVE 10Y-3M",  unit: "%" },
    { key: "btc",     label: "BTC 7D CANARY",       unit: "%" },
    { key: "eth_btc", label: "ETH/BTC CRYPTO RISK", unit: "%" },
  ],
  [
    { key: "xle",    label: "XLE DEFENSIVE ROT.", unit: "%" },
    { key: "copper", label: "COPPER 5D",          unit: "%" },
    { key: "gold",   label: "GOLD 5D (GLD)",      unit: "%" },
  ],
  [
    { key: "liquidity", label: "FED LIQUIDITY 60D", unit: "%" },
    { key: "rotation",  label: "SECTOR ROTATION",   unit: "%" },
  ],
];

const SENSOR_EXPLAIN = {
  vix:     "CBOE Volatility Index — market fear gauge. Below 20 = calm, 20–30 = elevated, above 30 = fear/panic. Sudden spikes signal institutional hedging. A slow grind above 25 is a regime shift signal, not a buy signal.",
  skew:    "CBOE SKEW Index — tail-risk demand. Above 130 = market buying crash protection. High SKEW with low VIX is the most dangerous combination — institutions paying for crash protection while retail is complacent. Preceded COVID crash, 2018 Q4, and 2022 drawdown.",
  bonds:   "TLT 5-Day (long-duration Treasury ETF) — rate pressure proxy. Falling TLT = rising yields = tighter financial conditions. Fast drops pressure growth and tech. Bonds AND stocks selling off simultaneously = inflation panic or rare Treasury supply crisis.",
  credit:  "HYG 5-Day — high-yield bond credit stress. HYG lagging Treasuries = credit stress building. Credit markets price risk before equity markets do — often leads equity drawdowns by 1–3 weeks.",
  dxy:     "USD Index 5-Day — dollar momentum. Strengthening USD = global liquidity squeeze. Dollar debt is priced globally — when it rises, everyone holding dollar-denominated debt feels the squeeze simultaneously. A surging DXY is a macro headwind.",
  curve:   "10Y–3M Yield Spread — yield curve slope. Positive = normal (lenders rewarded for time). Inversion = recession predictor 12–18 months ahead. Has preceded every US recession since the 1960s. Re-steepening after inversion often coincides with recession actually beginning.",
  btc:     "Bitcoin 7-Day — crypto risk canary. BTC drops >5% over 7 days signal broad risk-off in digital assets. BTC moves 24/7 with no circuit breakers — often leads TradFi risk-off by 1–3 weeks. Treat as global liquidity sensor, not crypto-specific noise.",
  eth_btc: "ETH vs BTC 7-Day Relative — risk appetite within crypto. ETH outperforming BTC = risk-on, altcoin season. ETH lagging = BTC dominance rising, defensive rotation. Leading indicator for altcoin headwinds even if BTC is stable.",
  xle:     "XLE Energy Sector vs SPY — defensive rotation signal. Energy outpacing the broad market = rotation into hard assets — classic late-cycle or stagflation signal. Institutions repositioning into commodity-linked inflation hedges.",
  copper:    "Copper 5-Day — global growth proxy ('Dr. Copper'). Used in virtually every industrial and construction process. Below -3% over 5 days signals contracting global economic activity. Leading indicator for earnings revisions and GDP downgrades.",
  gold:      "GLD 5-Day — safe-haven demand signal. Gold rising fast (>1% over 5 days) indicates institutional flight to safety. Unlike stocks, gold has no counterparty risk — it is the asset of last resort in geopolitical crises, currency collapses, and sovereign debt panics. Gold AND crypto both rising = broad risk-off rotation. Gold rising while equities hold = defensive hedging, not full panic.",
  liquidity: "Federal Reserve Balance Sheet 60-Day Change — net liquidity injection or drain. When the Fed's balance sheet shrinks below -2% over 60 days, it is actively removing dollars from the financial system, tightening conditions across all risk assets simultaneously. Most dangerous when combined with rising rates — a double liquidity drain. Requires a FRED API key in Settings to activate.",
  rotation:  "Sector Rotation Signal — Utilities (XLU), Financials (XLF), Technology (XLK), Energy (XLE) vs broad market (SPY) over 5 days. Utilities outrunning SPY (DEFENSIVE FLIGHT) = late-cycle fear trade — institutions hiding in regulated, dividend-paying assets. Technology outrunning SPY (RISK-ON) = growth expectations intact, beta-chasing phase. MIXED = rotational churn, no clear institutional thesis forming. The first defensive shift almost always shows up in XLU.",
};

function MacroPage({ macroData, onBack, manualStories = [] }) {
  const [aiText, setAiText]       = useState(null);
  const [aiLoading, setAiLoading] = useState(false);
  const [aiError, setAiError]     = useState(null);
  const [rotationData,    setRotationData]    = useState(null);
  const [rotationLoading, setRotationLoading] = useState(true);

  const sensors = macroData?.sensors;
  const macroTop = macroData ? window.sensorsToTopBar(macroData) : window.MACRO;
  const riskScore = typeof sensors?.risk_score === "number" ? sensors.risk_score : 0;
  const riskColor = riskScore > 70 ? "var(--sell)" : riskScore > 40 ? "var(--wait)" : "var(--buy)";
  const contradictions = sensors?.contradictions || [];

  React.useEffect(() => {
    window.API.fetchRotation()
      .then(d  => { setRotationData(d);    setRotationLoading(false); })
      .catch(() =>                          setRotationLoading(false));
  }, []);

  function handleMacroAI() {
    setAiLoading(true); setAiText(null); setAiError(null);
    window.API.fetchAIBriefing("MACRO", "swing", "macro", null, manualStories).then(r => {
      setAiLoading(false);
      if (r.error) setAiError(r.error);
      else setAiText(r.text);
    });
  }

  return (
    <div style={{ position: "absolute", inset: 0, background: "var(--bg-1)", display: "flex", flexDirection: "column", zIndex: 30, animation: "fadeIn 200ms ease" }}>

      {/* sticky header */}
      <div style={{ height: 52, padding: "0 18px", flex: "0 0 auto", borderBottom: "1px solid var(--line)", display: "flex", alignItems: "center", gap: 18, background: "var(--bg-2)", position: "sticky", top: 0, zIndex: 5 }}>
        <button onClick={onBack} style={{ display: "flex", alignItems: "center", gap: 6, padding: "6px 10px", background: "transparent", border: "1px solid var(--line-2)", color: "#FF6D00", cursor: "pointer" }}>
          <svg width="10" height="10" viewBox="0 0 10 10"><path d="M7 1 L3 5 L7 9" stroke="currentColor" strokeWidth="1.5" fill="none"/></svg>
          <span className="mono" style={{ fontSize: 13, letterSpacing: "0.16em" }}>BACK</span>
        </button>
        <span className="mono" style={{ fontSize: 14, fontWeight: 700, letterSpacing: "0.18em", color: "var(--ink)" }}>MACRO WEATHER</span>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <window.Dot color={macroTop.regimeColor} blink />
          <span className="mono" style={{ fontSize: 12, color: macroTop.regimeColor, fontWeight: 600, letterSpacing: "0.14em" }}>
            {macroTop.regime}
          </span>
        </div>
        <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 8 }}>
          <span className="mono" style={{ fontSize: 12, color: "var(--ink-3)", letterSpacing: "0.14em" }}>RISK SCORE</span>
          <span className="num" style={{ fontSize: 18, color: riskColor, fontWeight: 700 }}>{Math.round(riskScore)}</span>
          <span className="mono" style={{ fontSize: 12, color: "var(--ink-4)" }}>/100</span>
        </div>
      </div>

      {/* scrollable content */}
      <div style={{ flex: 1, overflowY: "auto", padding: "18px 18px 24px 18px", display: "flex", flexDirection: "column", gap: 20 }}>

        {/* risk bar */}
        <div style={{ background: "var(--bg-2)", border: "1px solid var(--line)", padding: "16px 20px" }}>
          <window.PowerBar value={riskScore} segments={40} />
        </div>

        {/* kill switch banner if needed */}
        {sensors?.kill_switch_fired && (
          <window.AlertCard level="danger" section="KILL SW" text={`KILL SWITCH FIRED — ${sensors.positions_closed || 0} position(s) auto-closed · Domino phase: ${sensors.domino_phase || '?'} · ${sensors.fired_at ? sensors.fired_at.slice(0,16).replace('T',' ') + ' UTC' : ''}`} />
        )}

        {/* contradiction pattern alerts */}
        {contradictions.length > 0 && (
          <div>
            <div style={{ marginBottom: 10 }}>
              <window.Label>PATTERN ALERTS · {contradictions.length} DETECTED</window.Label>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
              {contradictions.map((ca, i) => (
                <window.AlertCard key={i}
                  level={ca.severity === "HIGH" ? "danger" : "warn"}
                  section="MACRO"
                  text={`[${ca.severity}] ${ca.name} — ${ca.description}`} />
              ))}
            </div>
          </div>
        )}

        {/* sensor card grid rows */}
        {MACRO_SENSOR_ROWS.map((row, ri) => (
          <div key={ri} style={{ display: "grid", gridTemplateColumns: `repeat(${row.length}, 1fr)`, gap: 10 }}>
            {row.map(sc => (
              <window.MacroSensorCard
                key={sc.key}
                sensorKey={sc.key}
                sensor={sensors?.[sc.key]}
                label={sc.label}
                unit={sc.unit}
                explain={SENSOR_EXPLAIN[sc.key]} />
            ))}
          </div>
        ))}

        <window.RotationSection data={rotationData} loading={rotationLoading} />

        {/* AI macro commentary */}
        <div style={{ background: "var(--bg-2)", border: "1px solid rgba(56,189,248,0.2)", borderLeft: "3px solid var(--cyan)" }}>
          <div style={{ padding: "14px 18px", borderBottom: "1px solid var(--line)", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <div>
              <window.Label color="var(--amber)">AI MACRO COMMENTARY</window.Label>
              <div className="mono" style={{ fontSize: 13, color: "var(--ink-2)", marginTop: 4, letterSpacing: "0.08em" }}>
                Regime analysis · Sensor synthesis · Risk assessment
              </div>
            </div>
            <button onClick={handleMacroAI} disabled={aiLoading}
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
            {aiError && <div style={{ fontSize: 13, color: "var(--sell)", marginBottom: 8 }}>⚠ {aiError}</div>}
            {aiText ? (
              <div style={{ fontSize: 12, color: "var(--ink-2)", lineHeight: 1.75, whiteSpace: "pre-wrap", fontFamily: "'JetBrains Mono', monospace", letterSpacing: "0.02em" }}>
                {aiText}
              </div>
            ) : !aiLoading ? (
              <div style={{ fontSize: 13, color: "var(--ink-4)", fontFamily: "'JetBrains Mono', monospace", letterSpacing: "0.08em", lineHeight: 1.6 }}>
                Click GENERATE BRIEFING for an AI macro regime analysis based on all current sensor readings.
              </div>
            ) : (
              <div style={{ fontSize: 13, color: "var(--wait)", fontFamily: "'JetBrains Mono', monospace", letterSpacing: "0.08em" }} className="blink">
                ◇ Synthesizing macro environment…
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default MacroPage;
