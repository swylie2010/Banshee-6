/* Banshee — main app */
const { useState, useEffect, useMemo, useRef } = React;

/* convert /macro/sensors response → TopBar-compatible shape */
function sensorsToTopBar(data) {
  try {
    if (!data || !data.sensors) return window.MACRO;
    const s = data.sensors;

    function fmtFlag(key, label, fmt) {
      try {
        const sensor = s[key];
        if (!sensor || sensor.value == null) return { k: label, v: "—", st: "unknown" };
        const raw = Array.isArray(sensor.value) ? sensor.value[0] : sensor.value;
        const n = Number(raw);
        if (!isFinite(n)) return { k: label, v: "—", st: "unknown" };
        return { k: label, v: fmt(n), st: sensor.warning ? "elevated" : "calm" };
      } catch { return { k: label, v: "—", st: "unknown" }; }
    }

    const pct = v => (v >= 0 ? "+" : "") + v.toFixed(1) + "%";
    const flags = [
      fmtFlag("vix",     "VIX",      v => v.toFixed(1)),
      fmtFlag("skew",    "SKEW",     v => v.toFixed(0)),
      fmtFlag("bonds",   "BONDS 5D", pct),
      fmtFlag("credit",  "CREDIT",   pct),
      fmtFlag("dxy",     "DXY 5D",   pct),
      fmtFlag("curve",   "CURVE",    v => v.toFixed(2) + "%"),
      fmtFlag("btc",     "BTC 7D",   pct),
      fmtFlag("eth_btc", "ETH/BTC",  pct),
      fmtFlag("xle",     "XLE",      pct),
    ].filter(Boolean);

    const regimeShort = s.domino_phase === 0 ? "ALL CLEAR"
      : s.domino_state_str || (s.regime || "").split(/\s[—\-]\s/)[0] || "CAUTION";
    const regimeColor = s.regime_level === "green" ? "var(--buy)"
      : s.regime_level === "yellow" ? "var(--wait)" : "var(--sell)";

    return {
      regime:      regimeShort,
      regimeColor: regimeColor,
      cycleDay:    window.MACRO.cycleDay,
      warning:     typeof s.risk_score === "number" ? s.risk_score : window.MACRO.warning,
      flags:       flags.length ? flags : window.MACRO.flags,
    };
  } catch (e) {
    console.warn("[topbar] sensorsToTopBar error:", e);
    return window.MACRO;
  }
}

/* ── TopBar flag explanations ──────────────────────────────── */
const MACRO_EXPLAIN = {
  "VIX":      { full: "CBOE Volatility Index",         desc: "Market fear gauge. <20 = calm, 20–30 = elevated, >30 = fear/panic. Sudden spikes signal institutional hedging or a risk-off event." },
  "SKEW":     { full: "CBOE SKEW Index",               desc: "Tail-risk demand. >130 = market buying crash protection. High SKEW with low VIX = hidden complacency — dangerous divergence." },
  "BONDS 5D": { full: "TLT 5-Day Change (Bond Price)", desc: "Proxy for long-duration rate pressure. Falling TLT = rising yields = tighter financial conditions. Fast drops put pressure on growth and tech equities." },
  "CREDIT":   { full: "HYG 5-Day Change",              desc: "High-yield bond momentum. HYG lagging treasuries = credit stress building. Often leads equity drawdowns by 1–3 weeks." },
  "DXY 5D":   { full: "USD Index 5-Day Change",        desc: "Dollar momentum. Strengthening USD pressures risk assets, commodities, and crypto. Inverse correlation — a rising DXY is a headwind." },
  "CURVE":    { full: "10Y–3M Yield Spread",           desc: "Yield curve slope. Positive = normal. Inversion = recession predictor 12–18 months ahead. Re-steepening after inversion = recession beginning." },
  "BTC 7D":   { full: "Bitcoin 7-Day Performance",     desc: "Crypto risk canary. BTC dropping >5% over 7 days signals broad risk-off in digital assets and often leads altcoin drawdowns." },
  "ETH/BTC":  { full: "ETH vs BTC 7-Day Relative",    desc: "Risk appetite within crypto. ETH outperforming BTC = risk-on, altcoin season. ETH lagging = BTC dominance rising, defensive rotation within crypto." },
  "XLE":      { full: "Energy Sector 5-Day Perf.",     desc: "Defensive rotation signal. Energy outpacing the broad market = rotation into hard assets — often precedes or accompanies equity weakness." },
};

/* ── MacroPage sensor explanations (verbose, expandable) ──── */
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

/* ── Top bar ───────────────────────────────────────────────── */
function TopBar({ onToggleSidebar, sidebarOpen, macro, onMacro }) {
  const [time, setTime] = useState(new Date());
  const [activeFlag, setActiveFlag] = useState(null);
  useEffect(() => {
    const id = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(id);
  }, []);
  const t = time.toLocaleTimeString("en-US", { hour12: false });

  const m = macro || window.MACRO;
  return (
    <div style={{
      height: 52,
      borderBottom: "1px solid var(--line)",
      background: "linear-gradient(180deg, var(--bg-2), var(--bg-1))",
      display: "flex", alignItems: "stretch",
      flex: "0 0 auto",
      position: "relative", zIndex: 5,
    }}>
      {/* logo block */}
      <div style={{
        width: 200, padding: "0 16px",
        display: "flex", alignItems: "center", gap: 10,
        borderRight: "1px solid var(--line)",
        background: "linear-gradient(180deg, rgba(56,189,248,0.06), transparent)",
      }}>
        <button onClick={onToggleSidebar}
          aria-label="toggle sidebar"
          style={{
            width: 24, height: 24, padding: 0,
            background: "transparent",
            border: "1px solid var(--line-2)",
            color: "var(--ink-2)",
            cursor: "pointer",
            display: "flex", alignItems: "center", justifyContent: "center",
          }}>
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
            <path d={sidebarOpen ? "M9 3 L4 7 L9 11" : "M5 3 L10 7 L5 11"} stroke="currentColor" strokeWidth="1.5" />
          </svg>
        </button>
        <div style={{ display: "flex", flexDirection: "column", gap: 1 }}>
          <div style={{ display: "flex", alignItems: "baseline", gap: 6 }}>
            <span className="mono" style={{
              fontSize: 16, fontWeight: 700, letterSpacing: "0.16em", color: "var(--ink)",
            }}>BANSHEE</span>
            <span className="mono" style={{ fontSize: 12, color: "var(--cyan)", letterSpacing: "0.18em" }}>v5.0</span>
          </div>
          <div className="mono" style={{ fontSize: 11, color: "var(--ink-3)", letterSpacing: "0.18em" }}>
            MACRO TRADING TERMINAL
          </div>
        </div>
      </div>

      {/* regime block */}
      <div style={{
        padding: "0 18px",
        display: "flex", alignItems: "center", gap: 14,
        borderRight: "1px solid var(--line)",
      }}>
        <div style={{ display: "flex", flexDirection: "column", gap: 3 }}>
          <window.Label>REGIME</window.Label>
          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <window.Dot color={m.regimeColor || "var(--buy)"} blink />
            <span className="mono" style={{ fontSize: 13, color: m.regimeColor || "var(--buy)", fontWeight: 600, letterSpacing: "0.14em" }}>
              {m.regime}
            </span>
          </div>
        </div>
        <div style={{ width: 1, height: 28, background: "var(--line)" }} />
        <div style={{ display: "flex", flexDirection: "column", gap: 3 }}>
          <window.Label>CYCLE</window.Label>
          <span className="num" style={{ fontSize: 13, color: "var(--ink-2)" }}>D{m.cycleDay}</span>
        </div>
      </div>

      {/* macro flags strip */}
      <div style={{
        flex: 1, display: "flex", alignItems: "center", overflow: "visible",
        padding: "0 14px", gap: 4,
      }}
        onClick={e => { if (e.target === e.currentTarget) setActiveFlag(null); }}
      >
        {m.flags.map((f, i) => {
          const c = f.st === "calm" ? "var(--buy)" : f.st === "elevated" ? "var(--wait)" : "var(--ink-2)";
          const isActive = activeFlag === f.k;
          const explain  = MACRO_EXPLAIN[f.k];
          return (
            <div key={i} style={{ position: "relative" }}>
              <button
                onClick={() => setActiveFlag(isActive ? null : f.k)}
                style={{
                  display: "flex", flexDirection: "column", gap: 3,
                  background: isActive ? "rgba(56,189,248,0.08)" : "transparent",
                  border: `1px solid ${isActive ? "var(--line-2)" : "transparent"}`,
                  padding: "6px 10px", cursor: "pointer",
                }}>
                <window.Label>{f.k}</window.Label>
                <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                  <window.Dot color={c} size={5} />
                  <span className="num" style={{ fontSize: 12, color: "var(--ink)" }}>{f.v}</span>
                </div>
              </button>
              {isActive && explain && (
                <div style={{
                  position: "absolute", top: "calc(100% + 4px)", left: 0, zIndex: 100,
                  background: "var(--bg-2)", border: "1px solid var(--line-2)",
                  padding: "12px 14px", width: 260,
                  boxShadow: "0 8px 32px rgba(0,0,0,0.7)",
                  pointerEvents: "none",
                }}>
                  <div className="mono" style={{ fontSize: 12, color: "var(--cyan)", letterSpacing: "0.18em", marginBottom: 8 }}>
                    {explain.full}
                  </div>
                  <div style={{ fontSize: 13, color: "var(--ink-2)", lineHeight: 1.6 }}>
                    {explain.desc}
                  </div>
                  <div className="mono" style={{ fontSize: 12, color: "var(--ink-4)", letterSpacing: "0.14em", marginTop: 8 }}>
                    CURRENT · <span style={{ color: c }}>{f.v}</span>
                    {" — "}<span style={{ color: c }}>{f.st.toUpperCase()}</span>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* MACRO page button */}
      <button
        onClick={onMacro}
        className="mono"
        style={{
          padding: "0 18px", height: "100%",
          background: "transparent",
          border: "none",
          borderLeft: "1px solid var(--line)",
          color: "var(--ink-3)",
          cursor: "pointer",
          fontSize: 13, letterSpacing: "0.18em", fontWeight: 600,
          transition: "color 120ms, background 120ms",
        }}
        onMouseEnter={e => { e.currentTarget.style.color = "var(--cyan)"; e.currentTarget.style.background = "rgba(56,189,248,0.05)"; }}
        onMouseLeave={e => { e.currentTarget.style.color = "var(--ink-3)"; e.currentTarget.style.background = "transparent"; }}
      >
        MACRO ↗
      </button>

      {/* clock */}
      <div style={{
        padding: "0 18px",
        display: "flex", alignItems: "center", gap: 14,
        borderLeft: "1px solid var(--line)",
        minWidth: 200,
      }}>
        <div style={{ display: "flex", flexDirection: "column", gap: 3, alignItems: "flex-end" }}>
          <window.Label>SESSION · NYSE</window.Label>
          <span className="num" style={{ fontSize: 14, color: "var(--cyan)", letterSpacing: "0.06em" }}>{t}</span>
        </div>
        <window.Dot color="var(--buy)" blink size={7} />
      </div>
    </div>
  );
}

/* ── Sidebar ───────────────────────────────────────────────── */
function Sidebar({ open, watchlist, setWatchlist, focusedSym, setFocusedSym, radarData, onSearch, onSettings, onMacro, onNews, onLab, onRisk, onJournal, onManual, currentPage }) {
  const [searchVal, setSearchVal] = useState("");
  const wl = window.WATCHLISTS.find(w => w.id === watchlist);
  const symAssets = wl.syms
    .map(s => {
      const base = window.ASSETS.find(a => a.sym === s);
      return base ? mergeRadar(base, radarData[s]) : null;
    })
    .filter(Boolean);

  return (
    <aside style={{
      width: open ? 240 : 0,
      flex: "0 0 auto",
      background: "linear-gradient(180deg, var(--bg-2), var(--bg-1))",
      borderRight: "1px solid var(--line)",
      transition: "width 220ms cubic-bezier(0.7, 0, 0.3, 1)",
      overflow: "hidden",
      display: "flex", flexDirection: "column",
      position: "relative", zIndex: 4,
    }}>
      <div style={{ minWidth: 240, display: "flex", flexDirection: "column", height: "100%" }}>
        {/* symbol search */}
        <div style={{ padding: "10px 14px", borderBottom: "1px solid var(--line)" }}>
          <window.Label style={{ marginBottom: 6 }}>LOOK UP SYMBOL</window.Label>
          <form
            onSubmit={e => {
              e.preventDefault();
              const sym = searchVal.trim().toUpperCase();
              if (sym) { onSearch(sym); setSearchVal(""); }
            }}
            style={{ display: "flex", gap: 6, marginTop: 6 }}
          >
            <input
              value={searchVal}
              onChange={e => setSearchVal(e.target.value)}
              placeholder="TICKER…"
              maxLength={12}
              style={{
                flex: 1,
                background: "var(--bg-3)", border: "1px solid var(--line-2)",
                color: "var(--ink)", padding: "5px 8px",
                fontFamily: "'JetBrains Mono', monospace", fontSize: 13,
                letterSpacing: "0.08em", outline: "none",
              }}
            />
            <button type="submit" style={{
              padding: "5px 10px",
              background: "var(--cyan)", color: "var(--bg-0)",
              border: "none", cursor: "pointer",
              fontFamily: "'JetBrains Mono', monospace",
              fontSize: 13, fontWeight: 700, letterSpacing: "0.14em",
            }}>GO</button>
          </form>
        </div>

        {/* watchlist selector */}
        <div style={{
          padding: "14px 14px 10px 14px",
          borderBottom: "1px solid var(--line)",
        }}>
          <window.Label>WATCHLIST</window.Label>
          <div style={{ display: "flex", flexDirection: "column", gap: 2, marginTop: 8 }}>
            {window.WATCHLISTS.map(w => {
              const active = w.id === watchlist;
              return (
                <button key={w.id} onClick={() => setWatchlist(w.id)}
                  style={{
                    display: "flex", alignItems: "center", gap: 8,
                    padding: "6px 8px",
                    background: active ? "rgba(56,189,248,0.08)" : "transparent",
                    border: "none",
                    borderLeft: `2px solid ${active ? "var(--cyan)" : "transparent"}`,
                    cursor: "pointer", textAlign: "left",
                  }}>
                  <span className="mono" style={{
                    fontSize: 11, color: active ? "var(--cyan)" : "var(--ink-4)", letterSpacing: "0.18em",
                  }}>{w.tag}</span>
                  <span className="mono" style={{
                    fontSize: 13, color: active ? "var(--ink)" : "var(--ink-2)", letterSpacing: "0.1em",
                    fontWeight: active ? 600 : 400,
                  }}>{w.name}</span>
                  <span className="num" style={{
                    marginLeft: "auto", fontSize: 13,
                    color: active ? "var(--cyan)" : "var(--ink-3)",
                  }}>{w.syms.length}</span>
                </button>
              );
            })}
          </div>
        </div>

        {/* symbol pills */}
        <div style={{ padding: "12px 14px 8px 14px", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <window.Label>SYMBOLS · {symAssets.length}</window.Label>
          <span className="mono" style={{ fontSize: 11, color: "var(--ink-4)", letterSpacing: "0.16em" }}>{wl.tag}</span>
        </div>
        <div style={{
          padding: "0 14px 14px 14px",
          flex: 1, overflowY: "auto",
          display: "flex", flexDirection: "column", gap: 4,
        }}>
          {symAssets.map(a => {
            const c = window.verdictColors(a.verdict);
            const active = focusedSym === a.sym;
            return (
              <button key={a.sym}
                onClick={() => setFocusedSym(a.sym)}
                style={{
                  display: "grid", gridTemplateColumns: "auto 1fr auto",
                  alignItems: "center", gap: 8,
                  padding: "7px 9px",
                  background: active ? "rgba(56,189,248,0.06)" : "var(--bg-3)",
                  border: `1px solid ${active ? "var(--cyan)" : "var(--line)"}`,
                  cursor: "pointer", textAlign: "left",
                  transition: "all 120ms",
                }}
                onMouseEnter={e => { if (!active) e.currentTarget.style.borderColor = "var(--line-2)"; }}
                onMouseLeave={e => { if (!active) e.currentTarget.style.borderColor = "var(--line)"; }}
              >
                <window.Dot color={c.fg} size={6} />
                <div style={{ display: "flex", flexDirection: "column", gap: 1, minWidth: 0 }}>
                  <span className="mono" style={{ fontSize: 13, color: "var(--ink)", fontWeight: 600, letterSpacing: "0.04em" }}>
                    {a.sym}
                  </span>
                  <span className="mono" style={{ fontSize: 11, color: "var(--ink-3)", letterSpacing: "0.12em" }}>
                    {a.cls} · E{a.edge}
                  </span>
                </div>
                <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 1 }}>
                  <span className="num" style={{ fontSize: 13, color: "var(--ink-2)" }}>
                    {a.price < 100 ? a.price.toFixed(2) : a.price.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                  </span>
                  <span className="num" style={{ fontSize: 12, color: a.chg >= 0 ? "var(--buy)" : "var(--sell)" }}>
                    {a.chg >= 0 ? "+" : ""}{a.chg.toFixed(2)}%
                  </span>
                </div>
              </button>
            );
          })}
        </div>

        {/* nav buttons */}
        <div style={{ borderTop: "1px solid var(--line)", padding: "8px 10px", display: "flex", flexDirection: "column", gap: 2 }}>
          <div className="mono" style={{ fontSize: 11, color: "var(--ink-4)", letterSpacing: "0.18em", padding: "2px 4px 6px 4px" }}>NAVIGATE</div>
          {[
            { id: "macro",    label: "MACRO WEATHER",  icon: "◈" },
            { id: "news",     label: "PREDATOR NEWS",  icon: "◉" },
            { id: "risk",     label: "RISK DESK",      icon: "⚖" },
            { id: "journal",  label: "TRADE JOURNAL",  icon: "◎" },
            { id: "lab",      label: "SIGNAL LAB",     icon: "◬" },
            { id: "settings", label: "SETTINGS",       icon: "⚙" },
            { id: "manual",   label: "MANUAL",         icon: "◌" },
          ].map(({ id, label, icon }) => {
            const active = currentPage === id;
            const HANDLERS = { macro: onMacro, news: onNews, lab: onLab, risk: onRisk, journal: onJournal, settings: onSettings, manual: onManual };
            const handler = HANDLERS[id];
            return (
              <button key={id} onClick={handler}
                style={{
                  display: "flex", alignItems: "center", gap: 8,
                  padding: "7px 8px",
                  background: active ? "rgba(56,189,248,0.08)" : "transparent",
                  border: "none",
                  borderLeft: `2px solid ${active ? "var(--cyan)" : "transparent"}`,
                  cursor: "pointer", textAlign: "left",
                  transition: "all 120ms",
                }}
                onMouseEnter={e => { if (!active) { e.currentTarget.style.background = "rgba(255,255,255,0.03)"; e.currentTarget.style.borderLeftColor = "var(--line-2)"; }}}
                onMouseLeave={e => { if (!active) { e.currentTarget.style.background = "transparent"; e.currentTarget.style.borderLeftColor = "transparent"; }}}
              >
                <span className="mono" style={{ fontSize: 13, color: active ? "var(--cyan)" : "var(--ink-3)" }}>{icon}</span>
                <span className="mono" style={{ fontSize: 13, color: active ? "var(--ink)" : "var(--ink-2)", letterSpacing: "0.1em", fontWeight: active ? 600 : 400 }}>{label}</span>
              </button>
            );
          })}
        </div>

        {/* footer */}
        <div style={{
          padding: "10px 14px",
          borderTop: "1px solid var(--line)",
          display: "flex", justifyContent: "space-between", alignItems: "center",
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <window.Dot color="var(--buy)" blink />
            <span className="mono" style={{ fontSize: 12, color: "var(--ink-3)", letterSpacing: "0.16em" }}>
              FEED · LIVE
            </span>
          </div>
          <span className="mono" style={{ fontSize: 12, color: "var(--ink-4)", letterSpacing: "0.16em" }}>
            42ms
          </span>
        </div>
      </div>
    </aside>
  );
}

/* normalise raw engine edge (bull_score − bear_score, unbounded) → 0–100 */
function normaliseEdge(raw) {
  return Math.max(0, Math.min(100, Math.round(50 + raw * 2.5)));
}

/* merge live radar payload into a base asset object */
function mergeRadar(base, live) {
  if (!live) return base;
  return {
    ...base,
    _live:   true,
    price:   typeof live.price   === "number" ? live.price   : base.price,
    chg:     typeof live.chg_pct === "number" ? live.chg_pct : base.chg,
    verdict: live.verdict ?? base.verdict,
    edge:    typeof live.edge    === "number" ? normaliseEdge(live.edge) : base.edge,
    bias:    live.bias    ?? base.bias,
    rsi:     typeof live.rsi     === "number" ? Math.round(live.rsi) : base.rsi,
    atr:     live.atr_plan?.atr  ?? base.atr,
  };
}

/* ── Asset grid ───────────────────────────────────────────── */
function AssetGrid({ watchlist, focusedSym, onOpen, radarData, radarLoading }) {
  const wl = window.WATCHLISTS.find(w => w.id === watchlist);
  const syms = wl.syms;
  const assets = syms
    .map(s => {
      const base = window.ASSETS.find(a => a.sym === s);
      if (!base) return null;
      return { ...mergeRadar(base, radarData[s]), _loading: radarLoading.has(s) };
    })
    .filter(Boolean);

  const buy  = assets.filter(a => a.verdict === "BUY").length;
  const sell = assets.filter(a => a.verdict === "SELL").length;
  const wait = assets.filter(a => a.verdict === "WAIT").length;

  return (
    <div style={{ display: "flex", flexDirection: "column", flex: 1, minWidth: 0, minHeight: 0 }}>
      <div style={{
        height: 40, padding: "0 16px",
        borderBottom: "1px solid var(--line)",
        display: "flex", alignItems: "center", gap: 22,
        background: "var(--bg-1)",
        flex: "0 0 auto",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <span className="mono" style={{ fontSize: 13, color: "var(--ink)", fontWeight: 600, letterSpacing: "0.16em" }}>
            {wl.name}
          </span>
          <span className="mono" style={{ fontSize: 12, color: "var(--ink-4)", letterSpacing: "0.18em" }}>· {wl.tag}</span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
          {[["BUY", buy, "var(--buy)"], ["SELL", sell, "var(--sell)"], ["WAIT", wait, "var(--wait)"]].map(([lbl, n, c]) => (
            <div key={lbl} style={{ display: "flex", alignItems: "center", gap: 5 }}>
              <window.Dot color={c} size={5} />
              <span className="mono" style={{ fontSize: 13, color: "var(--ink-2)", letterSpacing: "0.14em" }}>{lbl} · {n}</span>
            </div>
          ))}
        </div>
        <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 12 }}>
          <span className="mono" style={{ fontSize: 12, color: "var(--ink-3)", letterSpacing: "0.16em" }}>SORT · EDGE↓</span>
          <span className="mono" style={{ fontSize: 12, color: "var(--ink-3)", letterSpacing: "0.16em" }}>VIEW · GRID</span>
        </div>
      </div>

      <div style={{
        flex: 1, overflowY: "auto",
        padding: 14,
        display: "grid",
        gridTemplateColumns: "repeat(auto-fill, minmax(240px, 1fr))",
        gap: 10,
        alignContent: "start",
      }}>
        {assets.map(a => (
          <window.AssetCard key={a.sym} asset={a}
            selected={focusedSym === a.sym}
            onClick={() => onOpen(a.sym)} />
        ))}
      </div>

      <Ticker radarData={radarData} />
    </div>
  );
}

/* ── Ticker tape ──────────────────────────────────────────── */
function Ticker({ radarData = {} }) {
  const liveAssets = window.ASSETS.map(a => {
    const r = radarData[a.sym];
    return {
      sym:   a.sym,
      price: (r && typeof r.price   === "number") ? r.price   : a.price,
      chg:   (r && typeof r.chg_pct === "number") ? r.chg_pct : a.chg,
      live:  !!(r && typeof r.price === "number"),
    };
  });
  const items = [...liveAssets, ...liveAssets];
  const anyLive = liveAssets.some(a => a.live);

  return (
    <div style={{
      height: 30, borderTop: "1px solid var(--line)",
      background: "var(--bg-2)",
      display: "flex", alignItems: "center",
      overflow: "hidden", flex: "0 0 auto",
      position: "relative",
    }}>
      <div style={{
        padding: "0 12px", height: "100%",
        display: "flex", alignItems: "center",
        background: anyLive ? "var(--cyan)" : "var(--bg-3)", color: "var(--bg-0)",
        flex: "0 0 auto",
        clipPath: "polygon(0 0, calc(100% - 12px) 0, 100% 100%, 0 100%)",
        paddingRight: 22,
      }}>
        <span className="mono" style={{ fontSize: 13, fontWeight: 700, letterSpacing: "0.18em", color: anyLive ? "var(--bg-0)" : "var(--ink-3)" }}>
          {anyLive ? "◆ TAPE · LIVE" : "◇ TAPE · MOCK"}
        </span>
      </div>
      <div style={{ flex: 1, overflow: "hidden", position: "relative" }}>
        <div className="marquee-track" style={{
          display: "inline-flex", gap: 28, whiteSpace: "nowrap", paddingLeft: 20,
        }}>
          {items.map((a, i) => (
            <span key={i} style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
              <span className="mono" style={{ fontSize: 13, color: a.live ? "var(--ink)" : "var(--ink-4)", letterSpacing: "0.1em" }}>{a.sym}</span>
              <span className="num" style={{ fontSize: 13, color: "var(--ink)" }}>
                {a.price < 100 ? a.price.toFixed(2) : a.price.toLocaleString(undefined, { maximumFractionDigits: 0 })}
              </span>
              <span className="num" style={{ fontSize: 13, color: a.chg >= 0 ? "var(--buy)" : "var(--sell)" }}>
                {a.chg >= 0 ? "▲" : "▼"} {Math.abs(a.chg).toFixed(2)}%
              </span>
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}

/* ── Shared mode/TF constants ────────────────────────────── */
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

/* ── Shared sub-components ───────────────────────────────── */
function Stat({ k, v, c = "var(--ink)" }) {
  return (
    <div style={{ display: "flex", alignItems: "baseline", gap: 5 }}>
      <span className="mono" style={{ fontSize: 12, color: "var(--ink-3)", letterSpacing: "0.18em" }}>{k}</span>
      <span className="num" style={{ fontSize: 13, color: c }}>{v}</span>
    </div>
  );
}

function MetricTile({ k, v, suffix = "", color = "var(--cyan)", bar = null, text = false }) {
  return (
    <div style={{
      background: "var(--bg-2)", border: "1px solid var(--line)",
      padding: "10px 12px",
      display: "flex", flexDirection: "column", gap: 6,
      position: "relative",
    }}>
      <window.Label>{k}</window.Label>
      <div style={{ display: "flex", alignItems: "baseline", gap: 4 }}>
        {text ? (
          <span className="mono" style={{ fontSize: 14, color, fontWeight: 600, letterSpacing: "0.08em" }}>{v}</span>
        ) : (
          <>
            <span className="num" style={{ fontSize: 18, color, fontWeight: 600, lineHeight: 1 }}>{v}</span>
            <span className="mono" style={{ fontSize: 12, color: "var(--ink-3)", letterSpacing: "0.12em" }}>{suffix}</span>
          </>
        )}
      </div>
      {bar !== null && <window.MiniBar value={bar} color={color} w={140} />}
    </div>
  );
}

function Level({ k, v, c }) {
  return (
    <div style={{
      display: "flex", justifyContent: "space-between", alignItems: "center",
      padding: "6px 10px", background: "var(--bg-1)",
      borderLeft: `2px solid ${c}`,
    }}>
      <span className="mono" style={{ fontSize: 12, color: "var(--ink-3)", letterSpacing: "0.18em" }}>{k}</span>
      <span className="num" style={{ fontSize: 14, color: c, fontWeight: 600 }}>{v}</span>
    </div>
  );
}

function KV({ k, v, c }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 3 }}>
      <window.Label>{k}</window.Label>
      <span className="num" style={{ fontSize: 14, color: c, fontWeight: 600 }}>{v}</span>
    </div>
  );
}

/* ── Warning / exception logic ────────────────────────────── */
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

/* ── DeepDiveCard — compact nav button on AssetHub ──────────── */
function DeepDiveCard({ icon, title, sub, accent, onDeepDive }) {
  const [hov, setHov] = useState(false);
  return (
    <div style={{ position: "relative" }}>
      <button onClick={onDeepDive}
        onMouseEnter={() => setHov(true)}
        onMouseLeave={() => setHov(false)}
        style={{
          width: "100%",
          display: "flex", alignItems: "center", gap: 10,
          padding: "10px 14px",
          background: hov ? `${accent}12` : "var(--bg-2)",
          border: `1px solid ${hov ? accent : "var(--line)"}`,
          cursor: "pointer", textAlign: "left",
          transition: "all 140ms",
          position: "relative",
        }}>
        <span style={{ fontSize: 15, color: accent, lineHeight: 1, flexShrink: 0 }}>{icon}</span>
        <div style={{ display: "flex", flexDirection: "column", gap: 1, minWidth: 0 }}>
          <span className="mono" style={{ fontSize: 13, fontWeight: 700, color: "var(--ink)", letterSpacing: "0.1em" }}>{title}</span>
          <span className="mono" style={{ fontSize: 11, color: "var(--ink-4)", letterSpacing: "0.1em" }}>DEEP DIVE →</span>
        </div>
      </button>
      {hov && sub && (
        <div style={{
          position: "absolute", bottom: "calc(100% + 6px)", left: 0, right: 0, zIndex: 50,
          background: "var(--bg-2)", border: `1px solid ${accent}40`,
          padding: "10px 12px", pointerEvents: "none",
          boxShadow: "0 8px 24px rgba(0,0,0,0.6)",
        }}>
          <span className="mono" style={{ fontSize: 12, color: "var(--ink-3)", lineHeight: 1.6, letterSpacing: "0.06em" }}>{sub}</span>
        </div>
      )}
    </div>
  );
}

/* ── AssetHub — standard overview (Page 2) ─────────────────── */
function AssetHub({ asset, onBack, macroWarning, onDeepDive }) {
  const [mode, setMode] = useState("swing");
  const [tf, setTf] = useState("1H");
  useEffect(() => { setTf(MODE_TF[mode][1] || MODE_TF[mode][0]); }, [mode]);

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

  return (
    <div style={{ position: "absolute", inset: 0, background: "rgba(6,8,12,0.97)", backdropFilter: "blur(6px)", display: "flex", flexDirection: "column", zIndex: 30, animation: "fadeIn 200ms ease" }}>
      <style>{`@keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }`}</style>

      {/* header */}
      <div style={{ height: 56, padding: "0 18px", flex: "0 0 auto", borderBottom: "1px solid var(--line)", display: "flex", alignItems: "center", gap: 18, background: "var(--bg-2)" }}>
        <button onClick={onBack} style={{ display: "flex", alignItems: "center", gap: 6, padding: "6px 10px", background: "transparent", border: "1px solid var(--line-2)", color: "var(--ink-2)", cursor: "pointer", clipPath: "polygon(8px 0, 100% 0, calc(100% - 8px) 100%, 0 100%)" }}>
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

      {/* main grid: chart left, trade rec right */}
      <div style={{ flex: 1, minHeight: 0, display: "grid", gridTemplateColumns: "minmax(0, 1fr) 300px", gap: 12, padding: "12px 12px 0 12px" }}>

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

          <div style={{ position: "relative", flex: 1, minHeight: 0, background: "var(--bg-2)", border: "1px solid var(--line)", padding: 10 }}>
            <window.Chart symbol={asset.sym} tf={tf} height={300} accent={c.fg}
              smcData={null} smcLoading={false}
              ghData={null} ghLoading={false}
              xabcdData={null} xabcdLoading={false}
              showSMC={false} setShowSMC={() => {}}
              showGH={false} setShowGH={() => {}}
              showXABCD={false} setShowXABCD={() => {}} />
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 8, flex: "0 0 auto" }}>
            <MetricTile k="EDGE SCORE" v={asset.edge} suffix="/100" color={c.fg} bar={asset.edge} />
            <MetricTile k="RSI(14)" v={asset.rsi} suffix="" color="var(--cyan)" bar={asset.rsi} />
            <MetricTile k="ATR" v={asset.atr} suffix="" color="var(--magenta)" />
            <MetricTile k="VOL · 24H" v={asset.vol} suffix="x" color="var(--amber)" />
            <MetricTile k="BIAS" v={asset.bias} suffix="" color={c.fg} text />
          </div>
        </div>

        {/* right: trade recommendation */}
        <aside style={{ background: "var(--bg-2)", border: "1px solid var(--line)", display: "flex", flexDirection: "column", position: "relative", overflow: "hidden", minHeight: 0 }}>
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
            <Level k="ENTRY" v={fmt(entry)} c="var(--cyan)" />
            <Level k="STOP" v={fmt(stop)} c="var(--sell)" />
            <Level k="TARGET 1" v={fmt(tp1)} c="var(--buy)" />
            <Level k="TARGET 2" v={fmt(tp2)} c="var(--buy)" />
          </div>
          <div style={{ padding: "12px 14px", display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, borderBottom: "1px solid var(--line)", flex: "0 0 auto" }}>
            <KV k="R:R" v={rr} c="var(--ink)" />
            <KV k="SIZE" v={sizeR} c="var(--ink)" />
            <KV k="CONFIDENCE" v={`${conf}%`} c={c.fg} />
            <KV k="HOLD" v={mode === "sniper" ? "≤4h" : mode === "swing" ? "3-10d" : "1-3mo"} c="var(--ink-2)" />
          </div>
          <div style={{ padding: "12px 14px", display: "flex", flexDirection: "column", gap: 6, flex: 1, minHeight: 0, overflowY: "auto" }}>
            <window.Label>SIGNAL CHECKLIST</window.Label>
            {[
              { ok: asset.edge > 60,                   t: `Edge ≥ 60 (cur ${asset.edge})` },
              { ok: asset.rsi > 30 && asset.rsi < 70,  t: `RSI in band (cur ${asset.rsi})` },
              { ok: dir > 0,                            t: "Trend with macro regime" },
              { ok: macroVal < 70,                      t: `Macro warn safe (${macroVal})` },
              { ok: asset.vol < 1.5,                    t: `Volatility manageable (${asset.vol}x)` },
              { ok: true,                               t: "Liquidity sufficient · L1 spread tight" },
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
            <button style={{ padding: "10px 12px", background: c.fg, color: "var(--bg-0)", border: "none", cursor: "pointer", fontWeight: 700, letterSpacing: "0.16em", clipPath: "polygon(8px 0, 100% 0, calc(100% - 8px) 100%, 0 100%)" }} className="mono">EXECUTE</button>
            <button style={{ padding: "10px 12px", background: "transparent", color: "var(--ink-2)", border: "1px solid var(--line-2)", cursor: "pointer", fontWeight: 600, letterSpacing: "0.16em", clipPath: "polygon(8px 0, 100% 0, calc(100% - 8px) 100%, 0 100%)" }} className="mono">SIMULATE</button>
          </div>
        </aside>
      </div>

      {/* deep dive navigation cards */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 8, padding: "8px 12px 10px 12px", flex: "0 0 auto" }}>
        <DeepDiveCard icon="◈" title="SMC STRUCTURE" sub="Order blocks · FVGs · BOS/CHoCH · Liquidity pools · HTF/LTF alignment" accent="var(--cyan)" onDeepDive={() => onDeepDive("smc")} />
        <DeepDiveCard icon="◎" title="GEO HARMONIC" sub="Fibonacci arc intersections · XABCD patterns · PRZ zones · Fib cycles" accent="var(--magenta)" onDeepDive={() => onDeepDive("gh")} />
        <DeepDiveCard icon="◆" title="NEXUS SYNTHESIS" sub="Full AI briefing · Cross-system confluence · Trade signal synthesis" accent="var(--amber)" onDeepDive={() => onDeepDive("nexus")} />
      </div>
    </div>
  );
}

/* ── AnalysisPage — deep dive with tabs (Page 3) ────────────── */
const ANALYSIS_TABS = [
  { id: "smc",   label: "SMC STRUCTURE",  accent: "var(--cyan)",    hex: "#38bdf8" },
  { id: "gh",    label: "GEO HARMONIC",   accent: "var(--magenta)", hex: "#c084fc" },
  { id: "nexus", label: "NEXUS",          accent: "var(--amber)",   hex: "#f59e0b" },
];

function AnalysisPage({ asset, macroWarning, initialTab, onBack }) {
  const [tab, setTab] = useState(initialTab || "smc");
  const [tf, setTf] = useState("1H");
  const activeTabCfg = ANALYSIS_TABS.find(t => t.id === tab);

  const [smcData, setSmcData]       = useState(null);
  const [smcLoading, setSmcLoading] = useState(false);
  const [ghData, setGhData]         = useState(null);
  const [ghLoading, setGhLoading]   = useState(false);
  const [xabcdData, setXabcdData]   = useState(null);
  const [xabcdLoading, setXabcdLoading] = useState(false);
  const [aiText, setAiText]   = useState(null);
  const [aiLoading, setAiLoading] = useState(false);
  const [aiError, setAiError]   = useState(null);
  const aiAbortRef = useRef(null);
  const [lensMode, setLensMode] = useState(1);

  function cancelAI() {
    if (aiAbortRef.current) { aiAbortRef.current.abort(); aiAbortRef.current = null; }
  }

  /* reset all on symbol change */
  useEffect(() => {
    cancelAI();
    setSmcData(null); setGhData(null); setXabcdData(null);
    setAiText(null); setAiLoading(false); setAiError(null);
    setLensMode(1);
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
    window.API.fetchAIBriefing(asset.sym, "swing", tab, controller.signal).then(r => {
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
  const entry = asset.price;
  const stop  = asset.price - dir * atr * 1.2;
  const tp1   = asset.price + dir * atr * 1.8;
  const tp2   = asset.price + dir * atr * 3.0;
  const rr    = (Math.abs(tp1 - entry) / (Math.abs(entry - stop) || 1)).toFixed(2);
  const action = asset.verdict === "SELL" ? "SHORT" : asset.verdict === "BUY" ? "LONG" : "STAND-BY";

  const TF_LIST = ["1H", "4H", "1D"];

  return (
    <div style={{ position: "absolute", inset: 0, background: "rgba(6,8,12,0.97)", backdropFilter: "blur(6px)", display: "flex", flexDirection: "column", zIndex: 30, animation: "fadeIn 200ms ease" }}>

      {/* header with tabs */}
      <div style={{ height: 52, flex: "0 0 auto", borderBottom: "1px solid var(--line)", display: "flex", alignItems: "stretch", background: "var(--bg-2)" }}>
        <div style={{ display: "flex", alignItems: "center", padding: "0 16px", borderRight: "1px solid var(--line)" }}>
          <button onClick={onBack} style={{ display: "flex", alignItems: "center", gap: 6, padding: "6px 10px", background: "transparent", border: "1px solid var(--line-2)", color: "var(--ink-2)", cursor: "pointer" }}>
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
                  color: active ? t.accent : "var(--ink-4)",
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
                  </div>
                );
              })()}
            </div>
          </div>
        )}

        {tab !== "nexus" && (
          <div style={{ padding: "0 14px" }}>
            <div style={{ background: "var(--bg-2)", border: "1px solid var(--line)", padding: 10 }}>
              <window.Chart symbol={asset.sym} tf={tf} height={420} accent={activeTabCfg.accent}
                smcData={smcData} smcLoading={smcLoading}
                ghData={ghData} ghLoading={ghLoading}
                xabcdData={xabcdData} xabcdLoading={xabcdLoading}
                showSMC={showSMC} setShowSMC={() => {}}
                showGH={showGH} setShowGH={() => {}}
                showXABCD={showXABCD} setShowXABCD={() => {}}
                lensMode={lensMode} />
            </div>
          </div>
        )}

        {/* SMC key — full legend below chart on SMC tab */}
        {tab === "smc" && smcData && !smcData.error && <window.SMCLegend />}

        {/* NEXUS tab: compact chart + trade rec side by side */}
        {tab === "nexus" && (
          <div style={{ padding: "14px 14px 0 14px", display: "grid", gridTemplateColumns: "1fr 300px", gap: 12 }}>
            <div style={{ background: "var(--bg-2)", border: "1px solid var(--line)", padding: 10 }}>
              <window.Chart symbol={asset.sym} tf="1D" height={260} accent={c.fg}
                smcData={null} smcLoading={false}
                ghData={null} ghLoading={false}
                xabcdData={null} xabcdLoading={false}
                showSMC={false} setShowSMC={() => {}}
                showGH={false} setShowGH={() => {}}
                showXABCD={false} setShowXABCD={() => {}} />
            </div>
            <aside style={{ background: "var(--bg-2)", border: "1px solid var(--line)", display: "flex", flexDirection: "column", position: "relative", overflow: "hidden" }}>
              <window.CornerTicks color={c.fg} />
              <div style={{ padding: "10px 12px", borderBottom: "1px solid var(--line)", background: `linear-gradient(180deg, ${c.bg}, transparent)` }}>
                <window.Label color={c.fg} style={{ marginBottom: 4 }}>TRADE SETUP</window.Label>
                <span className="mono" style={{ fontSize: 20, fontWeight: 700, color: c.fg, letterSpacing: "0.1em" }}>{action}</span>
              </div>
              <div style={{ padding: "10px 12px", display: "flex", flexDirection: "column", gap: 6, borderBottom: "1px solid var(--line)" }}>
                <Level k="ENTRY"    v={fmt(entry)} c="var(--cyan)" />
                <Level k="STOP"     v={fmt(stop)}  c="var(--sell)" />
                <Level k="TARGET 1" v={fmt(tp1)}   c="var(--buy)" />
                <Level k="TARGET 2" v={fmt(tp2)}   c="var(--buy)" />
              </div>
              <div style={{ padding: "10px 12px", display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, flex: 1 }}>
                <KV k="R:R" v={rr} c="var(--ink)" />
                <KV k="EDGE" v={`${asset.edge}/100`} c={c.fg} />
                <KV k="RSI" v={asset.rsi} c="var(--cyan)" />
                <KV k="BIAS" v={asset.bias} c={c.fg} />
              </div>
            </aside>
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
        <div style={{ padding: "14px 14px 20px 14px" }}>
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
      </div>
    </div>
  );
}

/* ── SettingsPage ──────────────────────────────────────────── */
const AI_PROVIDERS = ["Gemini", "OpenAI", "Anthropic", "Ollama", "Custom"];

const INPUT_STYLE = {
  width: "100%", boxSizing: "border-box",
  background: "var(--bg-3)", border: "1px solid var(--line-2)",
  color: "var(--ink)", padding: "7px 10px",
  fontFamily: "'JetBrains Mono', monospace", fontSize: 13,
  letterSpacing: "0.06em", outline: "none",
};

const SELECT_STYLE = {
  ...INPUT_STYLE,
  cursor: "pointer",
  appearance: "none", WebkitAppearance: "none",
  backgroundImage: "url(\"data:image/svg+xml,%3Csvg width='10' height='6' viewBox='0 0 10 6' fill='none' xmlns='http://www.w3.org/2000/svg'%3E%3Cpath d='M1 1L5 5L9 1' stroke='%2394a3b8' stroke-width='1.5'/%3E%3C/svg%3E\")",
  backgroundRepeat: "no-repeat", backgroundPosition: "right 10px center",
  paddingRight: 30,
};

function SettingsSection({ title, children }) {
  return (
    <div style={{ background: "var(--bg-2)", border: "1px solid var(--line)", padding: "20px 24px" }}>
      <div className="mono" style={{ fontSize: 12, color: "var(--cyan)", letterSpacing: "0.22em", fontWeight: 700, marginBottom: 18 }}>
        {title}
      </div>
      {children}
    </div>
  );
}

function SettingsField({ label, hint, children }) {
  return (
    <div style={{ marginBottom: 16 }}>
      <div style={{ display: "flex", alignItems: "baseline", gap: 10, marginBottom: 6 }}>
        <window.Label>{label}</window.Label>
        {hint && <span className="mono" style={{ fontSize: 11, color: "var(--ink-4)", letterSpacing: "0.12em" }}>{hint}</span>}
      </div>
      {children}
    </div>
  );
}

function SaveRow({ onSave, status }) {
  const color = status === "saved" ? "var(--buy)" : status === "error" ? "var(--sell)" : "var(--ink-3)";
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 12, marginTop: 8 }}>
      <button onClick={onSave} style={{
        padding: "7px 18px", background: "var(--cyan)", color: "var(--bg-0)",
        border: "none", cursor: "pointer",
        fontFamily: "'JetBrains Mono', monospace", fontSize: 13, fontWeight: 700, letterSpacing: "0.18em",
      }}>SAVE</button>
      {status && (
        <span className="mono" style={{ fontSize: 13, color, letterSpacing: "0.14em" }}>
          {status === "saved" ? "✓ SAVED" : status === "saving" ? "SAVING…" : `✗ ${status}`}
        </span>
      )}
    </div>
  );
}

function SettingsPage({ onBack }) {
  const [loaded, setLoaded]         = useState(false);
  const [fredKey, setFredKey]       = useState("");
  const [alpacaKey, setAlpacaKey]   = useState("");
  const [alpacaSec, setAlpacaSec]   = useState("");
  const [aiType, setAiType]         = useState("Gemini");
  const [aiKey, setAiKey]           = useState("");
  const [aiModel, setAiModel]       = useState("");
  const [aiUrl, setAiUrl]           = useState("");
  const [apiSaveStatus, setApiSaveStatus]   = useState(null);
  const [aiSaveStatus, setAiSaveStatus]     = useState(null);
  const [testStatus, setTestStatus]         = useState(null);
  const [testing, setTesting]               = useState(false);

  useEffect(() => {
    window.API.fetchSettings().then(data => {
      if (!data) { setLoaded(true); return; }
      setFredKey(data.FRED_API?.key || "");
      setAlpacaKey(data.ALPACA_KEY?.key || "");
      setAlpacaSec(data.ALPACA_SECRET?.key || "");
      const ai = data.AI_API || {};
      setAiType(ai.type || "Gemini");
      setAiKey(ai.key || "");
      setAiModel(ai.model || "");
      setAiUrl(ai.url || "");
      setLoaded(true);
    });
  }, []);

  async function saveAPIKeys() {
    setApiSaveStatus("saving");
    const result = await window.API.saveSettings({
      FRED_API:      { key: fredKey },
      ALPACA_KEY:    { key: alpacaKey },
      ALPACA_SECRET: { key: alpacaSec },
    });
    setApiSaveStatus(result.status === "saved" ? "saved" : "error: " + (result.message || "?"));
    setTimeout(() => setApiSaveStatus(null), 3000);
  }

  async function saveAIBrain() {
    setAiSaveStatus("saving");
    const result = await window.API.saveSettings({
      AI_API: { type: aiType, key: aiKey, model: aiModel, url: aiUrl },
    });
    setAiSaveStatus(result.status === "saved" ? "saved" : "error: " + (result.message || "?"));
    setTimeout(() => setAiSaveStatus(null), 3000);
  }

  async function handleTest() {
    setTesting(true); setTestStatus(null);
    const result = await window.API.testAIConnection({ type: aiType, key: aiKey, model: aiModel, url: aiUrl });
    setTesting(false);
    setTestStatus(result);
  }

  const needsUrl = aiType === "Ollama" || aiType === "Custom";

  const DEFAULT_MODELS = {
    Gemini:    "gemini-2.5-flash",
    OpenAI:    "gpt-4o-mini",
    Anthropic: "claude-sonnet-4-6",
    Ollama:    "llama3",
    Custom:    "",
  };

  return (
    <div style={{ position: "absolute", inset: 0, background: "var(--bg-1)", display: "flex", flexDirection: "column", zIndex: 30, animation: "fadeIn 200ms ease" }}>

      {/* header */}
      <div style={{ height: 52, padding: "0 18px", flex: "0 0 auto", borderBottom: "1px solid var(--line)", display: "flex", alignItems: "center", gap: 18, background: "var(--bg-2)" }}>
        <button onClick={onBack} style={{ display: "flex", alignItems: "center", gap: 6, padding: "6px 10px", background: "transparent", border: "1px solid var(--line-2)", color: "var(--ink-2)", cursor: "pointer" }}>
          <svg width="10" height="10" viewBox="0 0 10 10"><path d="M7 1 L3 5 L7 9" stroke="currentColor" strokeWidth="1.5" fill="none"/></svg>
          <span className="mono" style={{ fontSize: 13, letterSpacing: "0.16em" }}>BACK</span>
        </button>
        <span className="mono" style={{ fontSize: 14, fontWeight: 700, letterSpacing: "0.18em", color: "var(--ink)" }}>SETTINGS</span>
        <span className="mono" style={{ fontSize: 12, color: "var(--ink-4)", letterSpacing: "0.14em" }}>BANSHEE 5 CONFIGURATION</span>
      </div>

      {/* scrollable content */}
      <div style={{ flex: 1, overflowY: "auto", padding: "24px", display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20, alignContent: "start" }}>

        {/* API KEYS */}
        <SettingsSection title="▸ API KEYS">
          {!loaded ? (
            <span className="mono" style={{ fontSize: 13, color: "var(--ink-4)" }}>LOADING…</span>
          ) : (<>
            <SettingsField label="FRED API KEY" hint="macroeconomic data">
              <input
                value={fredKey} onChange={e => setFredKey(e.target.value)}
                placeholder="paste key here…" style={INPUT_STYLE}
              />
            </SettingsField>
            <SettingsField label="ALPACA API KEY" hint="equity feeds + paper trading">
              <input
                value={alpacaKey} onChange={e => setAlpacaKey(e.target.value)}
                placeholder="paste key here…" style={INPUT_STYLE}
              />
            </SettingsField>
            <SettingsField label="ALPACA SECRET">
              <input
                type="password"
                value={alpacaSec} onChange={e => setAlpacaSec(e.target.value)}
                placeholder="paste secret here…" style={INPUT_STYLE}
              />
            </SettingsField>
            <div style={{ padding: "10px 12px", background: "rgba(56,189,248,0.04)", border: "1px solid var(--line)", marginBottom: 16 }}>
              <span className="mono" style={{ fontSize: 12, color: "var(--ink-3)", letterSpacing: "0.12em", lineHeight: 1.6 }}>
                CRYPTO FEEDS — auto via CCXT (no key needed)<br/>
                EQUITY FEEDS — via Alpaca key above<br/>
                MACRO — via FRED key above
              </span>
            </div>
            <SaveRow onSave={saveAPIKeys} status={apiSaveStatus} />
          </>)}
        </SettingsSection>

        {/* AI BRAIN */}
        <SettingsSection title="▸ AI BRAIN">
          {!loaded ? (
            <span className="mono" style={{ fontSize: 13, color: "var(--ink-4)" }}>LOADING…</span>
          ) : (<>
            <SettingsField label="PROVIDER">
              <select value={aiType} onChange={e => { setAiType(e.target.value); setAiModel(DEFAULT_MODELS[e.target.value] || ""); }} style={SELECT_STYLE}>
                {AI_PROVIDERS.map(p => <option key={p} value={p}>{p}</option>)}
              </select>
            </SettingsField>
            <SettingsField label="MODEL NAME">
              <input
                value={aiModel} onChange={e => setAiModel(e.target.value)}
                placeholder={DEFAULT_MODELS[aiType] || "model name…"} style={INPUT_STYLE}
              />
            </SettingsField>
            <SettingsField label="API KEY" hint={aiType === "Ollama" ? "not required for local" : ""}>
              <input
                type="password"
                value={aiKey} onChange={e => setAiKey(e.target.value)}
                placeholder={aiType === "Ollama" ? "not needed for local Ollama" : "paste API key here…"}
                disabled={aiType === "Ollama"}
                style={{ ...INPUT_STYLE, opacity: aiType === "Ollama" ? 0.4 : 1 }}
              />
            </SettingsField>
            {needsUrl && (
              <SettingsField label="BASE URL" hint="e.g. http://100.x.x.x:11434 for Tailscale">
                <input
                  value={aiUrl} onChange={e => setAiUrl(e.target.value)}
                  placeholder="http://localhost:11434" style={INPUT_STYLE}
                />
              </SettingsField>
            )}

            {/* test connection */}
            <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 16 }}>
              <button onClick={handleTest} disabled={testing} style={{
                padding: "7px 18px",
                background: testing ? "var(--bg-3)" : "rgba(56,189,248,0.12)",
                color: testing ? "var(--ink-4)" : "var(--cyan)",
                border: "1px solid var(--cyan)", cursor: testing ? "default" : "pointer",
                fontFamily: "'JetBrains Mono', monospace", fontSize: 13, fontWeight: 700, letterSpacing: "0.18em",
              }}>
                {testing ? "TESTING…" : "TEST CONNECTION"}
              </button>
              {testStatus && (
                <span className="mono" style={{
                  fontSize: 13, letterSpacing: "0.1em",
                  color: testStatus.status === "ok" ? "var(--buy)" : "var(--sell)",
                }}>
                  {testStatus.status === "ok" ? `✓ OK — ${testStatus.message}` : `✗ ${testStatus.message}`}
                </span>
              )}
            </div>

            <SaveRow onSave={saveAIBrain} status={aiSaveStatus} />
          </>)}
        </SettingsSection>

      </div>
    </div>
  );
}

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

function MacroPage({ macroData, onBack }) {
  const [aiText, setAiText]       = useState(null);
  const [aiLoading, setAiLoading] = useState(false);
  const [aiError, setAiError]     = useState(null);

  const sensors = macroData?.sensors;
  const macroTop = macroData ? sensorsToTopBar(macroData) : window.MACRO;
  const riskScore = typeof sensors?.risk_score === "number" ? sensors.risk_score : 0;
  const riskColor = riskScore > 70 ? "var(--sell)" : riskScore > 40 ? "var(--wait)" : "var(--buy)";
  const contradictions = sensors?.contradictions || [];

  function handleMacroAI() {
    setAiLoading(true); setAiText(null); setAiError(null);
    window.API.fetchAIBriefing("MACRO", "swing", "macro").then(r => {
      setAiLoading(false);
      if (r.error) setAiError(r.error);
      else setAiText(r.text);
    });
  }

  return (
    <div style={{ position: "absolute", inset: 0, background: "var(--bg-1)", display: "flex", flexDirection: "column", zIndex: 30, animation: "fadeIn 200ms ease" }}>

      {/* sticky header */}
      <div style={{ height: 52, padding: "0 18px", flex: "0 0 auto", borderBottom: "1px solid var(--line)", display: "flex", alignItems: "center", gap: 18, background: "var(--bg-2)", position: "sticky", top: 0, zIndex: 5 }}>
        <button onClick={onBack} style={{ display: "flex", alignItems: "center", gap: 6, padding: "6px 10px", background: "transparent", border: "1px solid var(--line-2)", color: "var(--ink-2)", cursor: "pointer" }}>
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

/* ── LabPage — saved backtest results viewer (Page 5) ──────── */
function LabPage({ onBack }) {
  const [strategies, setStrategies] = useState({});
  const [loading, setLoading]       = useState(true);
  const [symFilter, setSymFilter]   = useState("");
  const [typeFilter, setTypeFilter] = useState("All");
  const [hideThin, setHideThin]     = useState(true);
  const [selected, setSelected]     = useState(null);

  useEffect(() => {
    window.API.fetchStrategies().then(data => {
      setStrategies(data || {});
      setLoading(false);
    });
  }, []);

  const entries = Object.entries(strategies);

  const types = ["All", ...new Set(entries.map(([, d]) => d.type || "custom"))];

  const filtered = entries.filter(([name, d]) => {
    if (symFilter && !(d.symbol || "").toLowerCase().includes(symFilter.toLowerCase())) return false;
    if (typeFilter !== "All" && (d.type || "custom") !== typeFilter) return false;
    if (hideThin) {
      const n = parseInt(d.stats?.n_trades ?? d.n_trades ?? "0", 10);
      if (n < 15) return false;
    }
    return true;
  });

  function colorVal(val) {
    if (typeof val === "string" && val.startsWith("+")) return "var(--buy)";
    if (typeof val === "string" && val.startsWith("-")) return "var(--sell)";
    return "var(--ink-2)";
  }

  const selData = selected ? strategies[selected] : null;
  const selStats = selData?.stats || {};

  const COL_STYLE = { fontFamily: "'JetBrains Mono', monospace", fontSize: 13, letterSpacing: "0.06em", padding: "5px 10px", borderBottom: "1px solid var(--line)" };
  const HDR_STYLE = { ...COL_STYLE, fontSize: 12, color: "var(--ink-4)", letterSpacing: "0.14em", textTransform: "uppercase" };

  return (
    <div style={{ position: "absolute", inset: 0, background: "var(--bg-0)", zIndex: 20, overflowY: "auto", display: "flex", flexDirection: "column" }}>
      {/* header */}
      <div style={{ padding: "18px 24px 14px", borderBottom: "1px solid var(--line)", display: "flex", alignItems: "center", justifyContent: "space-between", flexShrink: 0 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          <button onClick={onBack} style={{ background: "none", border: "none", color: "var(--ink-3)", cursor: "pointer", fontSize: 16, padding: 0 }}>←</button>
          <div>
            <div className="mono" style={{ fontSize: 13, fontWeight: 700, letterSpacing: "0.18em", color: "var(--ink)" }}>◬ SIGNAL LAB</div>
            <div className="mono" style={{ fontSize: 13, color: "var(--ink-4)", letterSpacing: "0.1em", marginTop: 2 }}>Saved backtest results · Run new tests in Strategy Lab</div>
          </div>
        </div>
        <button
          onClick={() => window.open("http://localhost:8501", "_blank")}
          className="mono"
          style={{ padding: "8px 16px", background: "rgba(245,158,11,0.1)", border: "1px solid var(--amber)", color: "var(--amber)", cursor: "pointer", fontSize: 13, letterSpacing: "0.14em", fontWeight: 700 }}
        >
          OPEN STRATEGY LAB →
        </button>
      </div>

      <div style={{ padding: "16px 24px", flex: 1 }}>
        {loading ? (
          <div className="mono" style={{ color: "var(--ink-4)", fontSize: 13 }}>◇ Loading…</div>
        ) : entries.length === 0 ? (
          <div style={{ textAlign: "center", padding: "60px 0" }}>
            <div className="mono" style={{ color: "var(--ink-4)", fontSize: 12, marginBottom: 16 }}>No saved backtest results yet.</div>
            <button onClick={() => window.open("http://localhost:8501", "_blank")} className="mono"
              style={{ padding: "9px 18px", background: "rgba(245,158,11,0.1)", border: "1px solid var(--amber)", color: "var(--amber)", cursor: "pointer", fontSize: 13, letterSpacing: "0.14em", fontWeight: 700 }}>
              OPEN STRATEGY LAB →
            </button>
          </div>
        ) : (
          <>
            {/* filters */}
            <div style={{ display: "flex", gap: 12, marginBottom: 16, alignItems: "center" }}>
              <input value={symFilter} onChange={e => setSymFilter(e.target.value)} placeholder="Filter symbol…"
                className="mono"
                style={{ background: "var(--bg-3)", border: "1px solid var(--line-2)", color: "var(--ink)", padding: "5px 10px", fontSize: 13, letterSpacing: "0.08em", outline: "none", width: 140 }} />
              <select value={typeFilter} onChange={e => setTypeFilter(e.target.value)}
                className="mono"
                style={{ background: "var(--bg-3)", border: "1px solid var(--line-2)", color: "var(--ink)", padding: "5px 10px", fontSize: 13, letterSpacing: "0.08em", outline: "none" }}>
                {types.map(t => <option key={t}>{t}</option>)}
              </select>
              <label className="mono" style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 13, color: "var(--ink-3)", cursor: "pointer" }}>
                <input type="checkbox" checked={hideThin} onChange={e => setHideThin(e.target.checked)} />
                Hide thin samples (&lt;15 trades)
              </label>
              <span className="mono" style={{ fontSize: 13, color: "var(--ink-4)" }}>{filtered.length} result(s)</span>
            </div>

            {/* table */}
            <div style={{ border: "1px solid var(--line)", marginBottom: 20, overflowX: "auto" }}>
              <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr 1fr 1fr 1fr 1fr 1fr 1fr 1fr", minWidth: 700 }}>
                {["Name","Symbol","TF","Return","Win Rate","Sharpe","Max DD","Trades","Saved"].map(h => (
                  <div key={h} style={HDR_STYLE}>{h}</div>
                ))}
                {filtered.map(([name, d]) => {
                  const s = d.stats || {};
                  const ret = s.total_return ?? d.total_return ?? "—";
                  const isActive = selected === name;
                  return (
                    <React.Fragment key={name}>
                      <div onClick={() => setSelected(isActive ? null : name)} style={{ ...COL_STYLE, color: isActive ? "var(--cyan)" : "var(--ink)", cursor: "pointer", background: isActive ? "rgba(56,189,248,0.06)" : "transparent" }}>{name}</div>
                      <div style={{ ...COL_STYLE, color: "var(--ink-2)" }}>{d.symbol || "—"}</div>
                      <div style={{ ...COL_STYLE, color: "var(--ink-2)" }}>{d.timeframe || "—"}</div>
                      <div style={{ ...COL_STYLE, color: colorVal(String(ret)) }}>{ret}</div>
                      <div style={{ ...COL_STYLE, color: colorVal(String(s.win_rate ?? "—")) }}>{s.win_rate ?? "—"}</div>
                      <div style={{ ...COL_STYLE, color: "var(--ink-2)" }}>{s.sharpe ?? "—"}</div>
                      <div style={{ ...COL_STYLE, color: colorVal(String(s.max_dd ?? "—")) }}>{s.max_dd ?? "—"}</div>
                      <div style={{ ...COL_STYLE, color: "var(--ink-2)" }}>{s.n_trades ?? "—"}</div>
                      <div style={{ ...COL_STYLE, color: "var(--ink-4)" }}>{d.saved_at || "—"}</div>
                    </React.Fragment>
                  );
                })}
              </div>
            </div>

            {/* inspect panel */}
            {selData && (
              <div style={{ background: "var(--bg-2)", border: "1px solid var(--line)", padding: 18 }}>
                <div className="mono" style={{ fontSize: 13, color: "var(--cyan)", letterSpacing: "0.14em", marginBottom: 12 }}>{selected}</div>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 8, marginBottom: 12 }}>
                  {[
                    ["Return",   String(selStats.total_return ?? selData.total_return ?? "—")],
                    ["vs B&H",   String(selStats.bnh_return ?? "—")],
                    ["Alpha",    String(selStats.alpha ?? "—")],
                    ["Win Rate", String(selStats.win_rate ?? "—")],
                    ["Trades",   String(selStats.n_trades ?? "—")],
                    ["Max DD",   String(selStats.max_dd ?? "—")],
                    ["Sharpe",   String(selStats.sharpe ?? "—")],
                    ["Pre-Sig",  String(selStats.presignal_count ?? "—")],
                  ].map(([k, v]) => (
                    <div key={k} style={{ background: "var(--bg-3)", padding: "8px 12px" }}>
                      <div className="mono" style={{ fontSize: 12, color: "var(--ink-4)", letterSpacing: "0.12em" }}>{k}</div>
                      <div className="mono" style={{ fontSize: 13, color: colorVal(v), fontWeight: 700, marginTop: 2 }}>{v}</div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

// Temporary stubs — will be replaced by Tasks 5-6
/* ── NumInput — labeled number input used by RiskDeskPage */
function NumInput({ label, value, onChange, step = 1 }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
      <div className="mono" style={{ fontSize: 12, color: "var(--ink-4)", letterSpacing: "0.14em" }}>{label}</div>
      <input
        type="number" step={step}
        value={value}
        onChange={e => onChange(parseFloat(e.target.value) || 0)}
        className="mono"
        style={{ background: "var(--bg-3)", border: "1px solid var(--line-2)", color: "var(--ink)", padding: "7px 10px", fontSize: 12, letterSpacing: "0.06em", outline: "none", width: "100%" }}
      />
    </div>
  );
}

/* ── RiskDeskPage — reactive position sizing calculator (Page 6) */
function RiskDeskPage({ openSym, radarData, onBack }) {
  const [account,    setAccount]    = useState(10000);
  const [riskPct,    setRiskPct]    = useState(1.0);
  const [entry,      setEntry]      = useState(0);
  const [stop,       setStop]       = useState(0);
  const [conflicted, setConflicted] = useState(false);
  const [plan,       setPlan]       = useState(null);
  const [calculating, setCalculating] = useState(false);
  const [calcError,  setCalcError]  = useState(null);

  /* auto-populate from focused symbol on mount */
  useEffect(() => {
    if (!openSym || !radarData[openSym]) return;
    const r   = radarData[openSym];
    const atr = r.atr_plan;
    const v   = r.verdict || "";
    setEntry(r.price || 0);
    if (atr && v.includes("BUY")  && atr.stop_long)  setStop(parseFloat(Number(atr.stop_long).toFixed(4)));
    else if (atr && v.includes("SELL") && atr.stop_short) setStop(parseFloat(Number(atr.stop_short).toFixed(4)));
    else if (r.price) setStop(parseFloat((r.price * 0.95).toFixed(4)));
  }, []); // mount only

  /* debounced recalculation */
  useEffect(() => {
    if (!entry || !stop || Math.abs(entry - stop) < 0.0001) return;
    setCalculating(true);
    const id = setTimeout(() => {
      window.API.fetchExecutionPlan({ account_size: account, risk_percent: riskPct, entry_price: entry, stop_loss: stop, smc_conflicted: conflicted })
        .then(p => {
          setCalculating(false);
          if (p && !p.error) { setPlan(p); setCalcError(null); }
          else { setPlan(null); setCalcError(p?.error || "Calculation failed"); }
        })
        .catch(() => { setCalculating(false); setPlan(null); setCalcError("Network error"); });
    }, 300);
    return () => clearTimeout(id);
  }, [account, riskPct, entry, stop, conflicted]);

  const isLong      = plan?.is_long ?? (entry > stop);
  const dirColor    = isLong ? "var(--buy)" : "var(--sell)";
  const conflictClr = "var(--sell)";

  return (
    <div style={{ position: "absolute", inset: 0, background: "var(--bg-0)", zIndex: 20, overflowY: "auto", display: "flex", flexDirection: "column" }}>
      {/* header */}
      <div style={{ padding: "18px 24px 14px", borderBottom: "1px solid var(--line)", display: "flex", alignItems: "center", gap: 16, flexShrink: 0 }}>
        <button onClick={onBack} style={{ background: "none", border: "none", color: "var(--ink-3)", cursor: "pointer", fontSize: 16, padding: 0 }}>←</button>
        <div>
          <div className="mono" style={{ fontSize: 13, fontWeight: 700, letterSpacing: "0.18em", color: "var(--ink)" }}>⚖ RISK DESK</div>
          <div className="mono" style={{ fontSize: 13, color: "var(--ink-4)", letterSpacing: "0.1em", marginTop: 2 }}>
            Position size · Margin · R-multiples{openSym ? ` · Auto-filled from ${openSym}` : ""}
          </div>
        </div>
      </div>

      <div style={{ padding: "20px 24px", flex: 1 }}>
        {/* inputs */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 16, marginBottom: 16 }}>
          <NumInput label="ACCOUNT SIZE ($)" value={account} onChange={setAccount} step={100} />
          <NumInput label="RISK PER TRADE (%)" value={riskPct} onChange={setRiskPct} step={0.1} />
          <NumInput label="ENTRY PRICE ($)" value={entry} onChange={setEntry} step={0.01} />
          <NumInput label="STOP-LOSS PRICE ($)" value={stop} onChange={setStop} step={0.01} />
        </div>

        {/* conflicted checkbox */}
        <label className="mono" style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13, color: conflicted ? conflictClr : "var(--ink-3)", cursor: "pointer", marginBottom: 20 }}>
          <input type="checkbox" checked={conflicted} onChange={e => setConflicted(e.target.checked)} />
          ⚠ SMC CONFLICTED — halve position size (HTF/LTF structure disagrees)
        </label>

        {calcError && (
          <div style={{ color: "var(--sell)", fontSize: 13, padding: "4px 0" }}>
            {calcError}
          </div>
        )}

        {/* calculating state */}
        {calculating && (
          <div className="mono blink" style={{ fontSize: 13, color: "var(--wait)", marginBottom: 16, letterSpacing: "0.1em" }}>◇ CALCULATING…</div>
        )}

        {/* results */}
        {plan && !calculating ? (
          <>
            {plan.confidence_note && (
              <div style={{ background: "rgba(239,68,68,0.08)", border: "1px solid var(--sell)", padding: "10px 16px", marginBottom: 16 }}>
                <span className="mono" style={{ fontSize: 13, color: "var(--sell)" }}>⚠ {plan.confidence_note}</span>
              </div>
            )}
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 16 }}>
              {/* panel 1: position size */}
              <div style={{ background: "var(--bg-2)", border: `2px solid ${conflicted ? conflictClr : dirColor}`, padding: 20 }}>
                <div className="mono" style={{ fontSize: 12, color: "var(--ink-4)", letterSpacing: "0.16em", marginBottom: 8 }}>
                  {conflicted ? "UNITS TO BUY — 50% (CONFLICTED)" : "UNITS TO BUY"}
                </div>
                <div className="mono" style={{ fontSize: 28, fontWeight: 800, color: conflicted ? conflictClr : dirColor }}>
                  {Number(plan.position_size).toLocaleString(undefined, { maximumFractionDigits: 4 })}
                </div>
                <div className="mono" style={{ fontSize: 13, color: "var(--ink-2)", marginTop: 8 }}>
                  Risking: ${Number(plan.max_risk_dollars).toLocaleString(undefined, { maximumFractionDigits: 2 })}
                </div>
                <div className="mono" style={{ fontSize: 13, color: "var(--ink-4)", marginTop: 4 }}>
                  Position value: ${Number(plan.position_value).toLocaleString(undefined, { maximumFractionDigits: 2 })}
                </div>
              </div>

              {/* panel 2: capital efficiency */}
              <div style={{ background: "var(--bg-2)", border: "1px solid var(--line)", padding: 20 }}>
                <div className="mono" style={{ fontSize: 12, color: "var(--ink-4)", letterSpacing: "0.16em", marginBottom: 12 }}>CAPITAL EFFICIENCY</div>
                <table style={{ width: "100%", borderCollapse: "collapse" }}>
                  <thead>
                    <tr>
                      <th className="mono" style={{ fontSize: 12, color: "var(--ink-4)", textAlign: "left", paddingBottom: 6, letterSpacing: "0.1em" }}>LEVERAGE</th>
                      <th className="mono" style={{ fontSize: 12, color: "var(--ink-4)", textAlign: "right", paddingBottom: 6, letterSpacing: "0.1em" }}>MARGIN REQ.</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(plan.capital_efficiency || []).map(row => (
                      <tr key={row.leverage} style={{ borderTop: "1px solid var(--line)" }}>
                        <td className="mono" style={{ fontSize: 13, color: "var(--ink)", padding: "5px 0", fontWeight: 700 }}>{row.leverage}x</td>
                        <td className="mono" style={{ fontSize: 13, color: "var(--ink-2)", textAlign: "right", padding: "5px 0" }}>
                          ${Number(row.margin_required).toLocaleString(undefined, { maximumFractionDigits: 2 })}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* panel 3: exit targets */}
              <div style={{ background: "var(--bg-2)", border: "1px solid var(--line)", padding: 20 }}>
                <div className="mono" style={{ fontSize: 12, color: "var(--ink-4)", letterSpacing: "0.16em", marginBottom: 12 }}>EXIT TARGETS</div>
                <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                  {(plan.targets || []).map(tgt => (
                    <div key={tgt.r_multiple} style={{ background: isLong ? "rgba(34,197,94,0.06)" : "rgba(239,68,68,0.06)", border: `1px solid ${dirColor}`, padding: "10px 14px", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                      <div>
                        <div className="mono" style={{ fontSize: 12, color: dirColor, letterSpacing: "0.12em", fontWeight: 700 }}>{tgt.r_multiple}:1 REWARD</div>
                        <div className="mono" style={{ fontSize: 13, color: dirColor, marginTop: 2 }}>+${Number(tgt.profit).toLocaleString(undefined, { maximumFractionDigits: 2 })}</div>
                      </div>
                      <div className="mono" style={{ fontSize: 16, fontWeight: 800, color: dirColor }}>
                        ${Number(tgt.price).toLocaleString(undefined, { maximumFractionDigits: 4 })}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </>
        ) : !calculating && !plan ? (
          <div className="mono" style={{ fontSize: 13, color: "var(--ink-4)", letterSpacing: "0.08em" }}>
            Enter trade parameters above to calculate position size.
          </div>
        ) : null}
      </div>
    </div>
  );
}
/* ── JournalPage helpers & constants (module-level, no closure deps) */
function fmtDatetime(ts) {
  if (!ts) return "—";
  const d = new Date(ts);
  if (isNaN(d)) return ts;
  const pad = n => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}
function fmtDate(ts) {
  if (!ts) return "—";
  const d = new Date(ts);
  if (isNaN(d)) return ts;
  const pad = n => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())}`;
}
const EXIT_REASONS = ["", "target_hit", "stop_hit", "manual_exit", "time_exit", "signal_reversal"];
const DIR_OPTIONS  = ["", "yes", "no", "partial"];

/* ── JournalPage — paper trade log & outcome tracking (Page 7) */
function JournalPage({ radarData, onBack }) {
  const [trades,         setTrades]         = useState([]);
  const [stats,          setStats]          = useState({});
  const [loading,        setLoading]        = useState(true);
  const [error,          setError]          = useState(null);
  const [expandedOpen,   setExpandedOpen]   = useState(new Set());
  const [expandedClosed, setExpandedClosed] = useState(new Set());
  const [editLevels,     setEditLevels]     = useState({});   // { [trade_id]: { stop: "", target: "" } }
  const [closeForm,      setCloseForm]      = useState({});   // { [trade_id]: { exitPrice: "", exitReason: "", notes: "" } }
  const [outcomeForm,    setOutcomeForm]     = useState({});  // { [trade_id]: { directionVal: "", exitReason: "", noteVal: "" } }
  const [feedbackResult, setFeedbackResult] = useState(null);
  const [feedbackLoading, setFeedbackLoading] = useState(false);
  const [syncing,        setSyncing]        = useState(false);

  /* load trades on mount */
  const loadTrades = React.useCallback(async () => {
    setLoading(true);
    try {
      const data = await window.API.fetchTrades();
      if (data && !data.error) {
        setTrades(data.trades || []);
        setStats(data.stats || {});
      } else {
        setError(data?.error || "Failed to load");
      }
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []); // state setters are stable, empty deps is correct

  useEffect(() => { loadTrades(); }, []);

  /* split trades */
  const openTrades   = trades.filter(t => !t.closed_at);
  const closedTrades = trades.filter(t =>  t.closed_at);

  /* toggle helpers */
  function toggleOpen(id) {
    setExpandedOpen(prev => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  }
  function toggleClosed(id) {
    setExpandedClosed(prev => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
        /* initialise outcome form from trade data */
        const t = closedTrades.find(x => x.id === id);
        if (t && !outcomeForm[id]) {
          const lastNote = (t.annotations && t.annotations.length > 0)
            ? t.annotations[t.annotations.length - 1].note
            : "";
          setOutcomeForm(prev => ({
            ...prev,
            [id]: {
              directionVal: t.signal_correct || "",
              exitReason:   t.exit_reason    || "",
              noteVal:      lastNote,
            }
          }));
        }
      }
      return next;
    });
  }

  /* live unrealised P&L for an open trade */
  function calcUnrealisedPnl(t) {
    const baseSym = t.symbol ? t.symbol.split("/")[0] : "";
    const rd = radarData[baseSym];
    const currentPrice = rd?.price;
    if (!currentPrice || !t.entry_price) return null;
    const isLong = t.direction && t.direction.toUpperCase().includes("BUY");
    const pnl = isLong
      ? (currentPrice - t.entry_price) / t.entry_price * 100
      : (t.entry_price - currentPrice) / t.entry_price * 100;
    return pnl;
  }

  /* compute R:R for a trade */
  function calcRR(t) {
    if (!t.entry_price || !t.stop_price || !t.target_price) return null;
    const isLong = t.direction && t.direction.toUpperCase().includes("BUY");
    const reward = isLong ? (t.target_price - t.entry_price) : (t.entry_price - t.target_price);
    const risk   = isLong ? (t.entry_price  - t.stop_price)  : (t.stop_price  - t.entry_price);
    if (risk <= 0) return null;
    return (reward / risk).toFixed(2);
  }

  /* style constants */
  const cardStyle = {
    background: "var(--bg-2)",
    border: "1px solid var(--line)",
    borderRadius: 8,
    marginBottom: 10,
    overflow: "hidden",
  };
  const sectionHeaderStyle = {
    fontSize: 13,
    color: "var(--ink-3)",
    letterSpacing: "0.14em",
    fontVariant: "small-caps",
    marginBottom: 10,
    marginTop: 20,
  };
  const metricTileStyle = {
    background: "var(--bg-3)",
    border: "1px solid var(--line)",
    borderRadius: 6,
    padding: "10px 16px",
    textAlign: "center",
    flex: 1,
  };
  const amberBtn = {
    background: "var(--amber)",
    color: "#000",
    fontWeight: 700,
    border: "none",
    cursor: "pointer",
    padding: "6px 14px",
    fontSize: 13,
    borderRadius: 4,
    letterSpacing: "0.08em",
  };
  const redBtn = {
    background: "var(--sell)",
    color: "#fff",
    fontWeight: 700,
    border: "none",
    cursor: "pointer",
    padding: "6px 14px",
    fontSize: 13,
    borderRadius: 4,
    letterSpacing: "0.08em",
  };
  const inputStyle = {
    background: "var(--bg-3)",
    border: "1px solid var(--line-2)",
    color: "var(--ink)",
    padding: "6px 10px",
    fontSize: 13,
    outline: "none",
    width: "100%",
    boxSizing: "border-box",
  };
  const selectStyle = { ...inputStyle, cursor: "pointer" };

  /* ── RENDER ─────────────────────────────────────── */
  if (loading) {
    return (
      <div style={{ position: "absolute", inset: 0, background: "var(--bg-0)", zIndex: 20, display: "flex", alignItems: "center", justifyContent: "center" }}>
        <span className="mono blink" style={{ color: "var(--ink-4)", letterSpacing: "0.1em" }}>◇ LOADING…</span>
      </div>
    );
  }

  return (
    <div style={{ position: "absolute", inset: 0, background: "var(--bg-0)", zIndex: 20, overflowY: "auto", display: "flex", flexDirection: "column" }}>
      {/* header */}
      <div style={{ padding: "18px 24px 14px", borderBottom: "1px solid var(--line)", display: "flex", alignItems: "center", justifyContent: "space-between", flexShrink: 0 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          <button onClick={onBack} style={{ background: "none", border: "none", color: "var(--ink-3)", cursor: "pointer", fontSize: 16, padding: 0 }}>←</button>
          <div>
            <div className="mono" style={{ fontSize: 13, fontWeight: 700, letterSpacing: "0.18em", color: "var(--ink)" }}>◎ TRADE JOURNAL</div>
            <div className="mono" style={{ fontSize: 13, color: "var(--ink-4)", letterSpacing: "0.1em", marginTop: 2 }}>Paper trade log · Outcome tracking</div>
          </div>
        </div>
        <button
          style={amberBtn}
          disabled={syncing}
          onClick={() => {
            setSyncing(true);
            window.API.syncAlpaca().then(() => { setSyncing(false); loadTrades(); }).catch(() => setSyncing(false));
          }}
        >
          {syncing ? "SYNCING…" : "SYNC ALPACA"}
        </button>
      </div>

      <div style={{ padding: "20px 24px", flex: 1 }}>
        {/* error state */}
        {error && (
          <div className="mono" style={{ color: "var(--sell)", fontSize: 13, marginBottom: 16 }}>
            ⚠ {error} — <span style={{ cursor: "pointer", textDecoration: "underline" }} onClick={loadTrades}>retry</span>
          </div>
        )}

        {/* stats bar — only when closed trades exist */}
        {stats.total > 0 && (
          <div style={{ display: "flex", gap: 10, marginBottom: 20 }}>
            <div style={metricTileStyle}>
              <div className="mono" style={{ fontSize: 12, color: "var(--ink-4)", letterSpacing: "0.12em", marginBottom: 4 }}>CLOSED TRADES</div>
              <div className="mono" style={{ fontSize: 16, fontWeight: 700, color: "var(--ink)" }}>{stats.total ?? "—"}</div>
            </div>
            <div style={metricTileStyle}>
              <div className="mono" style={{ fontSize: 12, color: "var(--ink-4)", letterSpacing: "0.12em", marginBottom: 4 }}>WIN RATE</div>
              <div className="mono" style={{ fontSize: 16, fontWeight: 700, color: "var(--ink)" }}>
                {stats.win_rate != null ? (stats.win_rate * 100).toFixed(0) + "%" : "—"}
              </div>
            </div>
            <div style={metricTileStyle}>
              <div className="mono" style={{ fontSize: 12, color: "var(--ink-4)", letterSpacing: "0.12em", marginBottom: 4 }}>AVG P&amp;L</div>
              <div className="mono" style={{ fontSize: 16, fontWeight: 700, color: stats.avg_pnl != null ? (stats.avg_pnl >= 0 ? "var(--buy)" : "var(--sell)") : "var(--ink-4)" }}>
                {stats.avg_pnl != null ? stats.avg_pnl.toFixed(1) + "%" : "—"}
              </div>
            </div>
            <div style={metricTileStyle}>
              <div className="mono" style={{ fontSize: 12, color: "var(--ink-4)", letterSpacing: "0.12em", marginBottom: 4 }}>BEST</div>
              <div className="mono" style={{ fontSize: 16, fontWeight: 700, color: "var(--buy)" }}>
                {stats.best != null ? stats.best.toFixed(1) + "%" : "—"}
              </div>
            </div>
            <div style={metricTileStyle}>
              <div className="mono" style={{ fontSize: 12, color: "var(--ink-4)", letterSpacing: "0.12em", marginBottom: 4 }}>WORST</div>
              <div className="mono" style={{ fontSize: 16, fontWeight: 700, color: "var(--sell)" }}>
                {stats.worst != null ? stats.worst.toFixed(1) + "%" : "—"}
              </div>
            </div>
          </div>
        )}

        {/* ── OPEN POSITIONS ─────────────────────────── */}
        {openTrades.length > 0 && (
          <>
            <div className="mono" style={sectionHeaderStyle}>
              ◆ OPEN POSITIONS <span style={{ color: "var(--amber)" }}>({openTrades.length})</span>
            </div>
            {openTrades.map(t => {
              const isExpanded = expandedOpen.has(t.id);
              const pnl = calcUnrealisedPnl(t);
              const pnlColor = pnl == null ? "var(--ink-4)" : pnl >= 0 ? "var(--buy)" : "var(--sell)";
              const pnlText  = pnl == null ? "—" : (pnl >= 0 ? "+" : "") + pnl.toFixed(2) + "%";
              const dirColor = t.direction && t.direction.toUpperCase().includes("BUY") ? "var(--buy)" : "var(--sell)";
              const isLong   = t.direction && t.direction.toUpperCase().includes("BUY");
              const baseSym  = t.symbol ? t.symbol.split("/")[0] : "";
              const currentPrice = radarData[baseSym]?.price;
              const el = editLevels[t.id] || { stop: "", target: "" };
              const cf = closeForm[t.id]  || { exitPrice: "", exitReason: "", notes: "" };

              return (
                <div key={t.id} style={cardStyle}>
                  {/* collapsed header row */}
                  <div
                    onClick={() => toggleOpen(t.id)}
                    style={{ padding: "12px 16px", cursor: "pointer", display: "flex", alignItems: "center", gap: 12, userSelect: "none" }}
                  >
                    <span className="mono" style={{ fontSize: 13, fontWeight: 700, color: "var(--ink)", minWidth: 60 }}>{t.symbol}</span>
                    <span className="mono" style={{ fontSize: 13, fontWeight: 700, color: dirColor, background: `${dirColor}22`, padding: "2px 7px", borderRadius: 3 }}>
                      {t.direction ? t.direction.toUpperCase() : "—"}
                    </span>
                    <span className="mono" style={{ fontSize: 13, color: "var(--ink-3)", flex: 1 }}>{t.verdict || ""}</span>
                    <span className="mono" style={{ fontSize: 13, color: "var(--ink-4)" }}>{fmtDatetime(t.opened_at || t.created_at)}</span>
                    <span className="mono" style={{ fontSize: 12, fontWeight: 700, color: pnlColor, minWidth: 64, textAlign: "right" }}>{pnlText}</span>
                    <span style={{ color: "var(--ink-4)", fontSize: 12 }}>{isExpanded ? "▲" : "▼"}</span>
                  </div>

                  {/* expanded content */}
                  {isExpanded && (
                    <div style={{ padding: "0 16px 16px", borderTop: "1px solid var(--line)" }}>
                      {/* metrics row */}
                      <div style={{ display: "flex", gap: 10, marginTop: 14, marginBottom: 16 }}>
                        {[
                          { label: "ENTRY",   val: t.entry_price  != null ? t.entry_price.toFixed(4)  : "—" },
                          { label: "CURRENT", val: currentPrice   != null ? currentPrice.toFixed(4)   : "—" },
                          { label: "STOP",    val: t.stop_price   != null ? t.stop_price.toFixed(4)   : "—" },
                          { label: "TARGET",  val: t.target_price != null ? t.target_price.toFixed(4) : "—" },
                          { label: "R:R",     val: calcRR(t) ?? "—" },
                        ].map(m => (
                          <div key={m.label} style={{ ...metricTileStyle, flex: 1 }}>
                            <div className="mono" style={{ fontSize: 12, color: "var(--ink-4)", letterSpacing: "0.12em", marginBottom: 4 }}>{m.label}</div>
                            <div className="mono" style={{ fontSize: 13, fontWeight: 700, color: "var(--ink)" }}>{m.val}</div>
                          </div>
                        ))}
                      </div>

                      {/* edit levels form */}
                      <div style={{ background: "var(--bg-3)", border: "1px solid var(--line)", borderRadius: 6, padding: "12px 14px", marginBottom: 12 }}>
                        <div className="mono" style={{ fontSize: 12, color: "var(--ink-4)", letterSpacing: "0.12em", marginBottom: 10 }}>EDIT LEVELS</div>
                        <div style={{ display: "flex", gap: 10, alignItems: "flex-end" }}>
                          <div style={{ flex: 1 }}>
                            <div className="mono" style={{ fontSize: 12, color: "var(--ink-4)", marginBottom: 4 }}>NEW STOP</div>
                            <input
                              type="number"
                              step="any"
                              value={el.stop}
                              onChange={e => setEditLevels(prev => {
                                const cur = prev[t.id] || { stop: "", target: "" };
                                return { ...prev, [t.id]: { ...cur, stop: e.target.value } };
                              })}
                              className="mono"
                              style={inputStyle}
                              placeholder={t.stop_price != null ? String(t.stop_price) : ""}
                            />
                          </div>
                          <div style={{ flex: 1 }}>
                            <div className="mono" style={{ fontSize: 12, color: "var(--ink-4)", marginBottom: 4 }}>NEW TARGET</div>
                            <input
                              type="number"
                              step="any"
                              value={el.target}
                              onChange={e => setEditLevels(prev => {
                                const cur = prev[t.id] || { stop: "", target: "" };
                                return { ...prev, [t.id]: { ...cur, target: e.target.value } };
                              })}
                              className="mono"
                              style={inputStyle}
                              placeholder={t.target_price != null ? String(t.target_price) : ""}
                            />
                          </div>
                          <button
                            style={amberBtn}
                            onClick={() => {
                              const payload = { trade_id: t.id };
                              if (el.stop   !== "") payload.stop_price   = parseFloat(el.stop);
                              if (el.target !== "") payload.target_price = parseFloat(el.target);
                              window.API.updateLevels(payload).then(res => {
                                if (!res.error) loadTrades();
                              });
                            }}
                          >UPDATE LEVELS</button>
                        </div>
                      </div>

                      {/* close trade form */}
                      <div style={{ background: "rgba(239,68,68,0.05)", border: "1px solid var(--sell)", borderRadius: 6, padding: "12px 14px" }}>
                        <div className="mono" style={{ fontSize: 12, color: "var(--sell)", letterSpacing: "0.12em", marginBottom: 10 }}>CLOSE TRADE</div>
                        <div style={{ display: "flex", gap: 10, alignItems: "flex-start", flexWrap: "wrap" }}>
                          <div style={{ minWidth: 120 }}>
                            <div className="mono" style={{ fontSize: 12, color: "var(--ink-4)", marginBottom: 4 }}>EXIT PRICE</div>
                            <input
                              type="number"
                              step="any"
                              value={cf.exitPrice}
                              onChange={e => setCloseForm(prev => {
                                const cur = prev[t.id] || { exitPrice: "", exitReason: "", notes: "" };
                                return { ...prev, [t.id]: { ...cur, exitPrice: e.target.value } };
                              })}
                              className="mono"
                              style={inputStyle}
                            />
                          </div>
                          <div style={{ minWidth: 150 }}>
                            <div className="mono" style={{ fontSize: 12, color: "var(--ink-4)", marginBottom: 4 }}>EXIT REASON</div>
                            <select
                              value={cf.exitReason}
                              onChange={e => setCloseForm(prev => {
                                const cur = prev[t.id] || { exitPrice: "", exitReason: "", notes: "" };
                                return { ...prev, [t.id]: { ...cur, exitReason: e.target.value } };
                              })}
                              className="mono"
                              style={selectStyle}
                            >
                              {EXIT_REASONS.map(r => <option key={r} value={r}>{r || "— select —"}</option>)}
                            </select>
                          </div>
                          <div style={{ flex: 1, minWidth: 160 }}>
                            <div className="mono" style={{ fontSize: 12, color: "var(--ink-4)", marginBottom: 4 }}>NOTES</div>
                            <textarea
                              rows={2}
                              value={cf.notes}
                              onChange={e => setCloseForm(prev => {
                                const cur = prev[t.id] || { exitPrice: "", exitReason: "", notes: "" };
                                return { ...prev, [t.id]: { ...cur, notes: e.target.value } };
                              })}
                              className="mono"
                              style={{ ...inputStyle, resize: "vertical" }}
                            />
                          </div>
                          <div style={{ display: "flex", alignItems: "flex-end" }}>
                            <button
                              style={redBtn}
                              onClick={() => {
                                if (!cf.exitPrice) return;
                                window.API.closeTrade({
                                  trade_id: t.id,
                                  exit_price: parseFloat(cf.exitPrice),
                                  exit_reason: cf.exitReason || null,
                                  notes: cf.notes || "",
                                }).then(res => { if (!res.error) loadTrades(); });
                              }}
                            >CLOSE TRADE</button>
                          </div>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </>
        )}

        {/* ── CLOSED TRADES ──────────────────────────── */}
        {closedTrades.length > 0 && (
          <>
            <div className="mono" style={{ ...sectionHeaderStyle, marginTop: openTrades.length > 0 ? 28 : 20 }}>
              ◆ CLOSED TRADES <span style={{ color: "var(--amber)" }}>({closedTrades.length})</span>
            </div>
            {closedTrades.map(t => {
              const isExpanded = expandedClosed.has(t.id);
              const pnlPct = t.pnl_percent;
              const pnlColor = pnlPct == null ? "var(--ink-4)" : pnlPct >= 0 ? "var(--buy)" : "var(--sell)";
              const pnlText  = pnlPct != null ? ((pnlPct >= 0 ? "+" : "") + pnlPct.toFixed(2) + "%") : "—";
              const icon     = pnlPct != null && pnlPct >= 0 ? "▲" : "▼";
              const dirColor = t.direction && t.direction.toUpperCase().includes("BUY") ? "var(--buy)" : "var(--sell)";
              const of_ = outcomeForm[t.id] || { directionVal: t.signal_correct || "", exitReason: t.exit_reason || "", noteVal: "" };

              return (
                <div key={t.id} style={cardStyle}>
                  {/* collapsed row */}
                  <div
                    onClick={() => toggleClosed(t.id)}
                    style={{ padding: "10px 16px", cursor: "pointer", display: "flex", alignItems: "center", gap: 12, userSelect: "none" }}
                  >
                    <span className="mono" style={{ fontSize: 13, color: pnlColor }}>{icon}</span>
                    <span className="mono" style={{ fontSize: 13, fontWeight: 700, color: "var(--ink)", minWidth: 60 }}>{t.symbol}</span>
                    <span className="mono" style={{ fontSize: 13, fontWeight: 700, color: dirColor, background: `${dirColor}22`, padding: "2px 7px", borderRadius: 3 }}>
                      {t.direction ? t.direction.toUpperCase() : "—"}
                    </span>
                    <span className="mono" style={{ fontSize: 12, fontWeight: 700, color: pnlColor, flex: 1 }}>{pnlText}</span>
                    <span className="mono" style={{ fontSize: 13, color: "var(--ink-4)" }}>{fmtDate(t.closed_at)}</span>
                    <span style={{ color: "var(--ink-4)", fontSize: 12 }}>{isExpanded ? "▲" : "▼"}</span>
                  </div>

                  {/* expanded content */}
                  {isExpanded && (
                    <div style={{ padding: "0 16px 16px", borderTop: "1px solid var(--line)" }}>
                      {/* entry/exit/stop/target metrics */}
                      <div style={{ display: "flex", gap: 10, marginTop: 14, marginBottom: 14 }}>
                        {[
                          { label: "ENTRY",  val: t.entry_price  != null ? t.entry_price.toFixed(4)  : "—" },
                          { label: "EXIT",   val: t.exit_price   != null ? t.exit_price.toFixed(4)   : "—" },
                          { label: "STOP",   val: t.stop_price   != null ? t.stop_price.toFixed(4)   : "—" },
                          { label: "TARGET", val: t.target_price != null ? t.target_price.toFixed(4) : "—" },
                        ].map(m => (
                          <div key={m.label} style={{ ...metricTileStyle, flex: 1 }}>
                            <div className="mono" style={{ fontSize: 12, color: "var(--ink-4)", letterSpacing: "0.12em", marginBottom: 4 }}>{m.label}</div>
                            <div className="mono" style={{ fontSize: 13, fontWeight: 700, color: "var(--ink)" }}>{m.val}</div>
                          </div>
                        ))}
                      </div>

                      {/* P&L metrics */}
                      <div style={{ display: "flex", gap: 10, marginBottom: 14 }}>
                        <div style={{ ...metricTileStyle, flex: 1 }}>
                          <div className="mono" style={{ fontSize: 12, color: "var(--ink-4)", letterSpacing: "0.12em", marginBottom: 4 }}>P&amp;L %</div>
                          <div className="mono" style={{ fontSize: 15, fontWeight: 700, color: pnlColor }}>{pnlText}</div>
                        </div>
                        {t.pnl_dollars != null && (
                          <div style={{ ...metricTileStyle, flex: 1 }}>
                            <div className="mono" style={{ fontSize: 12, color: "var(--ink-4)", letterSpacing: "0.12em", marginBottom: 4 }}>P&amp;L $</div>
                            <div className="mono" style={{ fontSize: 15, fontWeight: 700, color: pnlColor }}>
                              {t.pnl_dollars >= 0 ? "+" : ""}${t.pnl_dollars.toFixed(2)}
                            </div>
                          </div>
                        )}
                      </div>

                      {/* context row */}
                      {(t.regime || t.macro_bias || t.edge_type || t.signal_mode) && (
                        <div style={{ display: "flex", gap: 16, marginBottom: 14, flexWrap: "wrap" }}>
                          {[
                            { label: "REGIME", val: t.regime       || "—" },
                            { label: "MACRO",  val: t.macro_bias   || "—" },
                            { label: "EDGE",   val: t.edge_type    || "—" },
                            { label: "MODE",   val: t.signal_mode  || "—" },
                          ].map(ctx => (
                            <div key={ctx.label}>
                              <span className="mono" style={{ fontSize: 12, color: "var(--ink-4)", letterSpacing: "0.1em" }}>{ctx.label}: </span>
                              <span className="mono" style={{ fontSize: 13, color: "var(--ink-2)" }}>{ctx.val}</span>
                            </div>
                          ))}
                        </div>
                      )}

                      {/* outcome quality sub-panel */}
                      <div style={{ background: "var(--bg-3)", border: "1px solid var(--line)", borderRadius: 6, padding: "12px 14px", marginBottom: 10 }}>
                        <div className="mono" style={{ fontSize: 12, color: "var(--amber)", letterSpacing: "0.14em", marginBottom: 12 }}>OUTCOME QUALITY</div>
                        <div style={{ display: "flex", gap: 10, flexWrap: "wrap", marginBottom: 10 }}>
                          <div style={{ flex: 1, minWidth: 150 }}>
                            <div className="mono" style={{ fontSize: 12, color: "var(--ink-4)", marginBottom: 4 }}>WAS DIRECTION CORRECT?</div>
                            <select
                              value={of_.directionVal}
                              onChange={e => setOutcomeForm(prev => {
                                const cur = prev[t.id] || { directionVal: "", exitReason: "", noteVal: "" };
                                return { ...prev, [t.id]: { ...cur, directionVal: e.target.value } };
                              })}
                              className="mono"
                              style={selectStyle}
                            >
                              {DIR_OPTIONS.map(o => <option key={o} value={o}>{o || "— select —"}</option>)}
                            </select>
                          </div>
                          <div style={{ flex: 1, minWidth: 150 }}>
                            <div className="mono" style={{ fontSize: 12, color: "var(--ink-4)", marginBottom: 4 }}>EXIT REASON</div>
                            <select
                              value={of_.exitReason}
                              onChange={e => setOutcomeForm(prev => {
                                const cur = prev[t.id] || { directionVal: "", exitReason: "", noteVal: "" };
                                return { ...prev, [t.id]: { ...cur, exitReason: e.target.value } };
                              })}
                              className="mono"
                              style={selectStyle}
                            >
                              {EXIT_REASONS.map(r => <option key={r} value={r}>{r || "— select —"}</option>)}
                            </select>
                          </div>
                        </div>
                        <div style={{ marginBottom: 10 }}>
                          <div className="mono" style={{ fontSize: 12, color: "var(--ink-4)", marginBottom: 4 }}>ANNOTATION NOTES</div>
                          <textarea
                            rows={2}
                            value={of_.noteVal}
                            onChange={e => setOutcomeForm(prev => {
                              const cur = prev[t.id] || { directionVal: "", exitReason: "", noteVal: "" };
                              return { ...prev, [t.id]: { ...cur, noteVal: e.target.value } };
                            })}
                            className="mono"
                            style={{ ...inputStyle, resize: "vertical" }}
                          />
                        </div>
                        <button
                          style={amberBtn}
                          onClick={() => {
                            window.API.updateOutcome({
                              trade_id:       t.id,
                              signal_correct: of_.directionVal || null,
                              exit_reason:    of_.exitReason   || null,
                              note:           of_.noteVal      || null,
                            }).then(res => { if (!res.error) loadTrades(); });
                          }}
                        >SAVE OUTCOME</button>
                      </div>

                      {/* annotation log */}
                      {t.annotations && t.annotations.length > 0 && (
                        <div style={{ marginTop: 8 }}>
                          <div className="mono" style={{ fontSize: 12, color: "var(--ink-4)", letterSpacing: "0.12em", marginBottom: 6 }}>ANNOTATION LOG</div>
                          {t.annotations.map((ann, i) => (
                            <div key={i} style={{ borderLeft: "2px solid var(--line)", paddingLeft: 10, marginBottom: 6 }}>
                              <div className="mono" style={{ fontSize: 12, color: "var(--ink-4)", marginBottom: 2 }}>{fmtDatetime(ann.timestamp)}</div>
                              <div className="mono" style={{ fontSize: 13, color: "var(--ink-2)" }}>{ann.note}</div>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </>
        )}

        {/* no trades state */}
        {!loading && trades.length === 0 && !error && (
          <div className="mono" style={{ color: "var(--ink-4)", fontSize: 13, textAlign: "center", marginTop: 60, letterSpacing: "0.08em" }}>
            No trades logged yet. Open a paper trade from the analysis view.
          </div>
        )}

        {/* ── FEEDBACK ANALYSIS ──────────────────────── */}
        <hr style={{ borderColor: "var(--line)", margin: "24px 0", borderStyle: "solid", borderWidth: "1px 0 0 0" }} />
        <div className="mono" style={{ ...sectionHeaderStyle, marginTop: 0 }}>
          ◆ FEEDBACK ANALYSIS
        </div>
        <button
          style={amberBtn}
          disabled={feedbackLoading}
          onClick={() => {
            setFeedbackLoading(true);
            window.API.fetchFeedbackSynthesis().then(res => {
              setFeedbackResult(res);
              setFeedbackLoading(false);
            }).catch(() => setFeedbackLoading(false));
          }}
        >
          {feedbackLoading ? "ANALYZING…" : "RUN FEEDBACK ANALYSIS"}
        </button>

        {feedbackLoading && (
          <div className="mono blink" style={{ fontSize: 13, color: "var(--ink-4)", marginTop: 12, letterSpacing: "0.1em" }}>◇ LOADING…</div>
        )}

        {feedbackResult && !feedbackLoading && (
          <div style={{ marginTop: 16 }}>
            {/* feedback metrics */}
            {(feedbackResult.judged_trades != null || feedbackResult.briefings_matched != null || feedbackResult.trades_analyzed != null) && (
              <div style={{ display: "flex", gap: 10, marginBottom: 16 }}>
                <div style={metricTileStyle}>
                  <div className="mono" style={{ fontSize: 12, color: "var(--ink-4)", letterSpacing: "0.12em", marginBottom: 4 }}>JUDGED TRADES</div>
                  <div className="mono" style={{ fontSize: 16, fontWeight: 700, color: "var(--ink)" }}>{feedbackResult.judged_trades ?? "—"}</div>
                </div>
                <div style={metricTileStyle}>
                  <div className="mono" style={{ fontSize: 12, color: "var(--ink-4)", letterSpacing: "0.12em", marginBottom: 4 }}>BRIEFINGS MATCHED</div>
                  <div className="mono" style={{ fontSize: 16, fontWeight: 700, color: "var(--ink)" }}>{feedbackResult.briefings_matched ?? "—"}</div>
                </div>
                <div style={metricTileStyle}>
                  <div className="mono" style={{ fontSize: 12, color: "var(--ink-4)", letterSpacing: "0.12em", marginBottom: 4 }}>TRADES ANALYZED</div>
                  <div className="mono" style={{ fontSize: 16, fontWeight: 700, color: "var(--ink)" }}>{feedbackResult.trades_analyzed ?? "—"}</div>
                </div>
              </div>
            )}
            {/* narrative */}
            {(feedbackResult.narrative || feedbackResult.synthesis) && (
              <pre className="mono" style={{
                background: "var(--bg-2)",
                border: "1px solid var(--line)",
                borderRadius: 6,
                padding: "14px 16px",
                fontSize: 13,
                color: "var(--ink-2)",
                whiteSpace: "pre-wrap",
                wordBreak: "break-word",
                margin: 0,
              }}>
                {feedbackResult.narrative || feedbackResult.synthesis}
              </pre>
            )}
            {feedbackResult.error && (
              <div className="mono" style={{ color: "var(--sell)", fontSize: 13, marginTop: 8 }}>⚠ {feedbackResult.error}</div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

/* ── PredatorCard — story card for watchlist events & discovered signals ── */
function PredatorCard({ headline, lede, source, url, impact_score, symbols = [], accentColor }) {
  const impactBg = impact_score >= 8 ? "var(--sell)" : impact_score >= 5 ? "var(--amber)" : "var(--ink-4)";
  return (
    <div style={{ borderLeft: `3px solid ${accentColor}`, background: "var(--bg-2)", padding: "10px 14px", marginBottom: 8, borderRadius: "0 4px 4px 0" }}>
      <div className="mono" style={{ fontSize: 13, fontWeight: 700, color: "var(--ink)", marginBottom: 4 }}>{headline}</div>
      <div className="mono" style={{ fontSize: 12, color: "var(--ink-3)", lineHeight: 1.5, marginBottom: 8,
        display: "-webkit-box", WebkitLineClamp: 3, WebkitBoxOrient: "vertical", overflow: "hidden" }}>
        {lede}
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
        {url
          ? <a href={url} target="_blank" rel="noreferrer" className="mono"
              style={{ fontSize: 11, background: "var(--bg-3)", color: "var(--ink-3)", padding: "1px 6px",
                borderRadius: 3, textDecoration: "none", border: "1px solid var(--line)" }}>
              {source}
            </a>
          : <span className="mono" style={{ fontSize: 11, background: "var(--bg-3)", color: "var(--ink-4)",
              padding: "1px 6px", borderRadius: 3, border: "1px solid var(--line)" }}>{source}</span>
        }
        <span className="mono" style={{ fontSize: 11, background: impactBg, color: "#fff",
          padding: "1px 6px", borderRadius: 3 }}>{impact_score}/10</span>
        {symbols.map(s => (
          <span key={s} className="mono" style={{ fontSize: 10, color: "var(--ink-4)",
            background: "var(--bg-3)", padding: "1px 5px", borderRadius: 3 }}>{s}</span>
        ))}
      </div>
    </div>
  );
}

/* ── FollowupCard — compact card for yesterday's followup items ─────────── */
function FollowupCard({ original, status, update }) {
  const STATUS_COLOR = { escalated: "var(--sell)", resolved: "var(--buy)", developing: "var(--amber)", new: "var(--cyan, #00e5ff)" };
  const pillColor = STATUS_COLOR[(status || "").toLowerCase()] || "var(--ink-4)";
  return (
    <div style={{ background: "var(--bg-2)", borderLeft: "3px solid var(--line)", padding: "8px 14px", marginBottom: 6, borderRadius: "0 4px 4px 0" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
        <span className="mono" style={{ fontSize: 10, background: pillColor, color: "#fff",
          padding: "1px 7px", borderRadius: 3, textTransform: "uppercase", letterSpacing: "0.1em" }}>
          {status || "?"}
        </span>
        <span className="mono" style={{ fontSize: 12, fontWeight: 700, color: "var(--ink)" }}>{original}</span>
      </div>
      <div className="mono" style={{ fontSize: 12, color: "var(--ink-3)", lineHeight: 1.5 }}>{update}</div>
    </div>
  );
}

/* ── NewsPage — Daily Predator intelligence briefing (Page 9) ───────────── */
function NewsPage({ onBack }) {
  const [briefing, setBriefing]   = useState(null);
  const [loading, setLoading]     = useState(true);
  const [running, setRunning]     = useState(false);
  const [runError, setRunError]   = useState(null);
  const [expanded, setExpanded]   = useState(false);

  const load = () => {
    setLoading(true);
    window.API.fetchPredatorBriefing().then(b => { setBriefing(b); setLoading(false); });
  };

  React.useEffect(load, []);

  const handleRun = async () => {
    setRunning(true); setRunError(null);
    const result = await window.API.runPredator(true);
    setRunning(false);
    if (!result) { setRunError("Pipeline failed — check Core logs."); return; }
    setBriefing(result);
  };

  const ageLabel = () => {
    if (!briefing?.generated_at) return "No briefing today — run the pipeline";
    const diffMs = Date.now() - new Date(briefing.generated_at).getTime();
    const h = Math.floor(diffMs / 3600000);
    const m = Math.floor((diffMs % 3600000) / 60000);
    return h > 0 ? `Generated ${h}h ${m}m ago` : `Generated ${m}m ago`;
  };

  const TONE_COLOR = { BULLISH: "var(--buy)", BEARISH: "var(--sell)", NEUTRAL: "var(--ink-4)", MIXED: "var(--amber)" };
  const toneColor = TONE_COLOR[briefing?.macro_tone] || "var(--ink-4)";

  const riskDots = (level) => {
    const colors = ["#4caf50","#8bc34a","var(--amber)","#ff9800","var(--sell)"];
    return Array.from({ length: 5 }, (_, i) => (
      <span key={i} style={{ color: i < level ? colors[Math.min(level - 1, 4)] : "var(--line)", fontSize: 12 }}>●</span>
    ));
  };

  const SectionHeader = ({ label, count, extra }) => (
    <div className="mono" style={{ fontSize: 11, letterSpacing: "0.18em", color: "var(--ink-4)",
      borderBottom: "1px solid var(--line)", paddingBottom: 6, marginBottom: 10, marginTop: 20,
      display: "flex", alignItems: "center", gap: 8 }}>
      {label}
      {count != null && <span style={{ background: "var(--bg-3)", padding: "0 6px", borderRadius: 3, fontSize: 10 }}>{count}</span>}
      {extra && <span style={{ color: "var(--amber)" }}>{extra}</span>}
    </div>
  );

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", background: "var(--bg-1)", color: "var(--ink)", overflow: "hidden" }}>
      {/* Back nav */}
      <div style={{ padding: "18px 24px 14px", borderBottom: "1px solid var(--line)", display: "flex", alignItems: "center", gap: 16, flexShrink: 0 }}>
        <button onClick={onBack} style={{ background: "none", border: "none", color: "var(--ink-3)", cursor: "pointer", fontSize: 16, padding: 0 }}>←</button>
        <div>
          <div className="mono" style={{ fontSize: 13, fontWeight: 700, letterSpacing: "0.18em", color: "var(--ink)" }}>◉ PREDATOR NEWS</div>
          <div className="mono" style={{ fontSize: 12, color: "var(--ink-4)", letterSpacing: "0.1em", marginTop: 2 }}>Daily intelligence briefing · Market signals · Discovered catalysts</div>
        </div>
      </div>

      {/* Scrollable body */}
      <div style={{ flex: 1, overflowY: "auto", padding: "20px 24px" }}>
        {loading ? (
          <div className="mono" style={{ fontSize: 12, color: "var(--ink-4)", textAlign: "center", marginTop: 40 }}>◌ LOADING BRIEFING…</div>
        ) : !briefing ? (
          /* Empty state */
          <div style={{ textAlign: "center", marginTop: 60 }}>
            <div className="mono" style={{ fontSize: 13, color: "var(--ink-4)", marginBottom: 16 }}>No briefing yet for today.</div>
            <button onClick={handleRun} disabled={running}
              style={{ fontFamily: "inherit", fontSize: 12, letterSpacing: "0.12em", background: "var(--amber)",
                color: "#000", border: "none", padding: "8px 18px", borderRadius: 4, cursor: "pointer" }}>
              {running ? "◌ RUNNING PIPELINE…" : "▶ RUN DAILY PREDATOR"}
            </button>
            {running && <div className="mono" style={{ fontSize: 11, color: "var(--ink-4)", marginTop: 8 }}>This takes 2–3 minutes</div>}
            {runError && <div className="mono" style={{ fontSize: 11, color: "var(--sell)", marginTop: 8 }}>{runError}</div>}
          </div>
        ) : (
          <>
            {/* Masthead */}
            <div style={{ textAlign: "center", marginBottom: 18, paddingBottom: 14, borderBottom: "1px solid var(--line)" }}>
              <div className="mono" style={{ fontSize: 18, fontWeight: 700, letterSpacing: "0.3em", color: "var(--ink)" }}>THE DAILY PREDATOR</div>
              <div className="mono" style={{ fontSize: 11, color: "var(--ink-4)", marginTop: 4, letterSpacing: "0.1em" }}>
                {briefing.date} · Powered by Banshee 5
              </div>
              <div style={{ display: "flex", justifyContent: "center", alignItems: "center", gap: 12, marginTop: 8 }}>
                <span className="mono" style={{ fontSize: 11, background: toneColor, color: "#fff",
                  padding: "2px 8px", borderRadius: 3 }}>{briefing.macro_tone || "NEUTRAL"}</span>
                <span style={{ display: "flex", gap: 3 }}>{riskDots(briefing.risk_level || 3)}</span>
              </div>
            </div>

            {/* Top Story */}
            {briefing.top_story && (
              <div style={{ background: "var(--bg-2)", borderLeft: "3px solid var(--amber)",
                padding: "12px 16px", borderRadius: "0 4px 4px 0", marginBottom: 14 }}>
                <div className="mono" style={{ fontSize: 10, letterSpacing: "0.18em", color: "var(--amber)", marginBottom: 6 }}>TOP STORY</div>
                <div className="mono" style={{ fontSize: 14, color: "var(--ink)", lineHeight: 1.6 }}>{briefing.top_story}</div>
              </div>
            )}

            {/* Collapsible full briefing */}
            {briefing.ai_narrative && (
              <div style={{ marginBottom: 14 }}>
                <button onClick={() => setExpanded(e => !e)}
                  style={{ background: "none", border: "1px solid var(--line)", color: "var(--ink-3)", cursor: "pointer",
                    fontFamily: "inherit", fontSize: 11, letterSpacing: "0.12em", padding: "4px 10px", borderRadius: 3 }}>
                  {expanded ? "▲ COLLAPSE" : "▼ EXPAND FULL BRIEFING"}
                </button>
                {expanded && (
                  <div style={{ marginTop: 8, background: "var(--bg-2)", padding: "12px 14px", borderRadius: 4,
                    maxHeight: 300, overflowY: "auto", fontSize: 12, lineHeight: 1.7,
                    color: "var(--ink-3)", whiteSpace: "pre-wrap", fontFamily: "monospace" }}>
                    {briefing.ai_narrative}
                  </div>
                )}
              </div>
            )}

            {/* Action bar */}
            <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 20,
              padding: "10px 14px", background: "var(--bg-2)", borderRadius: 4, flexWrap: "wrap" }}>
              <button onClick={handleRun} disabled={running}
                style={{ fontFamily: "inherit", fontSize: 11, letterSpacing: "0.12em",
                  background: "var(--amber)", color: "#000",
                  border: "none", padding: "6px 14px", borderRadius: 3, cursor: running ? "default" : "pointer" }}>
                {running ? "◌ RUNNING PIPELINE…" : "▶ RUN DAILY PREDATOR"}
              </button>
              <span className="mono" style={{ fontSize: 11, color: "var(--ink-4)" }}>{ageLabel()}</span>
              {running && <span className="mono" style={{ fontSize: 11, color: "var(--ink-4)" }}>This takes 2–3 minutes</span>}
              {runError && <span className="mono" style={{ fontSize: 11, color: "var(--sell)" }}>{runError}</span>}
            </div>

            {/* Watchlist Events */}
            {(briefing.watchlist_events || []).length > 0 && (
              <>
                <SectionHeader label="WATCHLIST EVENTS" count={briefing.watchlist_events.length} />
                {briefing.watchlist_events.map((ev, i) => (
                  <PredatorCard key={i} {...ev} accentColor="var(--buy)" symbols={ev.symbols || []} />
                ))}
              </>
            )}

            {/* Discovered Signals */}
            {(briefing.discovered_signals || []).length > 0 && (
              <>
                <SectionHeader label="DISCOVERED SIGNALS" count={briefing.discovered_signals.length} extra="◉ DISCOVER" />
                {briefing.discovered_signals.map((ev, i) => (
                  <PredatorCard key={i} {...ev} accentColor="var(--amber)" symbols={ev.symbols || []} />
                ))}
              </>
            )}

            {/* Yesterday Followups */}
            {(briefing.yesterday_followups || []).length > 0 && (
              <>
                <SectionHeader label="YESTERDAY — FOLLOWUPS" count={briefing.yesterday_followups.length} />
                {briefing.yesterday_followups.map((fu, i) => (
                  <FollowupCard key={i} {...fu} />
                ))}
              </>
            )}
          </>
        )}
      </div>
    </div>
  );
}

/* ── ManualPage — in-app reference guide (Page 8) ──────────── */
function ManualPage({ onBack }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", background: "var(--bg)", color: "var(--ink)", overflow: "hidden" }}>
      <div style={{ padding: "18px 24px 14px", borderBottom: "1px solid var(--line)", display: "flex", alignItems: "center", gap: 16, flexShrink: 0 }}>
        <button onClick={onBack} style={{ background: "none", border: "none", color: "var(--ink-3)", cursor: "pointer", fontSize: 16, padding: 0 }}>←</button>
        <div>
          <div className="mono" style={{ fontSize: 13, fontWeight: 700, letterSpacing: "0.18em", color: "var(--ink)" }}>◌ MANUAL</div>
          <div className="mono" style={{ fontSize: 13, color: "var(--ink-4)", letterSpacing: "0.1em", marginTop: 2 }}>How to read overlays · SMC lenses · Glossary · System guide</div>
        </div>
      </div>
      <div style={{ flex: 1, overflowY: "auto", padding: "32px 24px" }}>
        <div className="mono" style={{ fontSize: 13, color: "var(--ink-4)", letterSpacing: "0.12em", textAlign: "center", marginTop: 40 }}>
          ◌ MANUAL — COMING SOON
        </div>
        <div className="mono" style={{ fontSize: 13, color: "var(--ink-5)", letterSpacing: "0.08em", textAlign: "center", marginTop: 12, lineHeight: 1.8 }}>
          This page will cover the SMC Optometry lenses · GH arc reading<br/>
          XABCD patterns · macro sensors · signal checklist · glossary
        </div>
      </div>
    </div>
  );
}

/* ── App ───────────────────────────────────────────────────── */
function App() {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [watchlist, setWatchlist]     = useState("all");
  const [focusedSym, setFocusedSym]   = useState(null);
  const [openSym, setOpenSym]         = useState(null);
  const [page, setPage]               = useState("grid");   // "grid" | "hub" | "analysis" | "macro" | "settings" | "lab" | "risk" | "journal" | "manual"
  const [analysisTab, setAnalysisTab] = useState("smc");
  const [radarData, setRadarData]     = useState({});
  const [radarLoading, setRadarLoading] = useState(() => new Set(window.ASSETS.map(a => a.sym)));
  const [macroData, setMacroData]     = useState(null);
  const [customAsset, setCustomAsset] = useState(null);

  /* keyboard nav */
  useEffect(() => {
    function handleKey(e) {
      if (e.key === "Escape") {
        if (page === "analysis") { setPage("hub"); return; }
        if (page === "hub")      { setOpenSym(null); setCustomAsset(null); setPage("grid"); return; }
        if (["macro", "settings", "lab", "risk", "journal", "manual"].includes(page)) { setPage("grid"); return; }
      }
      if ((e.key === "ArrowUp" || e.key === "ArrowDown") && page === "hub" && openSym) {
        e.preventDefault();
        const wl = window.WATCHLISTS.find(w => w.id === watchlist);
        const syms = wl.syms;
        const idx = syms.indexOf(openSym);
        if (idx === -1) return;
        const next = e.key === "ArrowDown"
          ? syms[(idx + 1) % syms.length]
          : syms[(idx - 1 + syms.length) % syms.length];
        setFocusedSym(next); setOpenSym(next); setCustomAsset(null);
      }
    }
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [page, openSym, watchlist]);

  /* symbol search via sidebar */
  async function handleSymbolSearch(sym) {
    const existing = window.ASSETS.find(a => a.sym === sym);
    if (existing) {
      setFocusedSym(sym); setOpenSym(sym); setPage("hub"); setCustomAsset(null);
      return;
    }
    const res = await window.API.fetchRadar(sym, "swing");
    if (res && !res.error && typeof res.price === "number") {
      const asset = {
        sym, pair: window.API.coreSymbol(sym), name: sym, cls: "CUSTOM",
        price:   res.price,
        chg:     typeof res.chg_pct === "number" ? res.chg_pct : 0,
        verdict: res.verdict ?? "WAIT",
        edge:    normaliseEdge(typeof res.edge === "number" ? res.edge : 0),
        bias:    res.bias ?? "→ FLAT",
        rsi:     typeof res.rsi === "number" ? Math.round(res.rsi) : 50,
        atr:     res.atr_plan?.atr ?? 0,
        vol:     1, _live: true,
      };
      setCustomAsset(asset); setFocusedSym(sym); setOpenSym(sym); setPage("hub");
    } else {
      console.warn(`[search] symbol not found: ${sym}`);
    }
  }

  /* fetch macro on mount */
  useEffect(() => {
    window.API.fetchMacro().then(data => { if (data) setMacroData(data); });
  }, []);

  /* fetch radar for all assets on mount */
  const RADAR_SKIP = new Set(["VIX","DXY","TLT"]);
  useEffect(() => {
    window.ASSETS.forEach(a => {
      if (RADAR_SKIP.has(a.sym)) {
        setRadarLoading(prev => { const s = new Set(prev); s.delete(a.sym); return s; });
        return;
      }
      window.API.fetchRadar(a.sym, "swing").then(res => {
        if (res && !res.error) setRadarData(prev => ({ ...prev, [a.sym]: res }));
        setRadarLoading(prev => { const s = new Set(prev); s.delete(a.sym); return s; });
      });
    });
  }, []);

  function openAsset(sym) {
    setFocusedSym(sym); setOpenSym(sym); setPage("hub");
  }
  function goDeepDive(tab) {
    setAnalysisTab(tab); setPage("analysis");
  }
  function goBack() {
    if (page === "analysis") setPage("hub");
    else if (page === "hub") { setOpenSym(null); setCustomAsset(null); setPage("grid"); }
    else if (["macro", "settings", "lab", "risk", "journal", "manual"].includes(page)) setPage("grid");
  }

  const liveAsset = openSym
    ? (customAsset?.sym === openSym
        ? customAsset
        : mergeRadar(window.ASSETS.find(a => a.sym === openSym), radarData[openSym]))
    : null;
  const topBarMacro = sensorsToTopBar(macroData);

  return (
    <div style={{ height: "100vh", display: "flex", flexDirection: "column", overflow: "hidden" }}>
      <TopBar
        onToggleSidebar={() => setSidebarOpen(o => !o)}
        sidebarOpen={sidebarOpen}
        macro={topBarMacro}
        onMacro={() => setPage("macro")}
      />
      <div style={{ flex: 1, minHeight: 0, display: "flex", position: "relative" }}>
        <Sidebar
          open={sidebarOpen}
          watchlist={watchlist} setWatchlist={setWatchlist}
          focusedSym={focusedSym}
          radarData={radarData}
          setFocusedSym={openAsset}
          onSearch={handleSymbolSearch}
          onSettings={() => setPage("settings")}
          onMacro={() => setPage("macro")}
          onNews={() => {}}
          onLab={() => setPage("lab")}
          onRisk={() => setPage("risk")}
          onJournal={() => setPage("journal")}
          onManual={() => setPage("manual")}
          currentPage={page}
        />
        <AssetGrid
          watchlist={watchlist}
          focusedSym={focusedSym}
          onOpen={openAsset}
          radarData={radarData}
          radarLoading={radarLoading}
        />
        {page === "hub" && liveAsset && (
          <AssetHub
            asset={liveAsset}
            macroWarning={topBarMacro.warning}
            onBack={goBack}
            onDeepDive={goDeepDive}
          />
        )}
        {page === "analysis" && liveAsset && (
          <AnalysisPage
            asset={liveAsset}
            macroWarning={topBarMacro.warning}
            initialTab={analysisTab}
            onBack={goBack}
          />
        )}
        {page === "macro" && (
          <MacroPage macroData={macroData} onBack={goBack} />
        )}
        {page === "settings" && (
          <SettingsPage onBack={goBack} />
        )}
        {page === "lab" && (
          <LabPage onBack={goBack} />
        )}
        {page === "risk" && (
          <RiskDeskPage openSym={openSym} radarData={radarData} onBack={goBack} />
        )}
        {page === "journal" && (
          <JournalPage radarData={radarData} onBack={goBack} />
        )}
        {page === "manual" && (
          <ManualPage onBack={goBack} />
        )}
      </div>
    </div>
  );
}

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(<App />);
