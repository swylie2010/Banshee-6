/* Banshee — main app */
const { useState, useEffect, useMemo, useRef } = React;
import AssetGrid from './pages/AssetGrid.jsx';
import AssetHub from './pages/AssetHub.jsx';
import AnalysisPage from './pages/AnalysisPage.jsx';

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
        return { k: label, v: fmt(n), st: sensor.critical ? "stressed" : sensor.warning ? "elevated" : "calm" };
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
      position: "relative", zIndex: 40,
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
            color: "#FF6D00",
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
            <span className="mono" style={{ fontSize: 12, color: "var(--cyan)", letterSpacing: "0.18em" }}>v6.0</span>
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
          const c = f.st === "calm" ? "var(--buy)" : f.st === "elevated" ? "var(--wait)" : f.st === "stressed" ? "var(--sell)" : "var(--ink-2)";
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
                <window.Label color={f.st === "stressed" ? "var(--sell)" : f.st === "elevated" ? "var(--wait)" : undefined}>{f.k}</window.Label>
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
function Sidebar({ open, watchlists, watchlist, setWatchlist, focusedSym, setFocusedSym, radarData, onSearch, onSettings, onMacro, onNews, onLab, onRisk, onJournal, onManual, onOptions, currentPage, onPresetsOpen }) {
  const [searchVal, setSearchVal] = useState("");
  const [shutdownState, setShutdownState] = useState("idle"); // idle | confirm | done
  const wl = watchlists.find(w => w.id === watchlist);
  const symAssets = wl.syms
    .map(s => {
      const key  = canonSym(s);
      const base = resolveBaseAsset(key);
      return { ...mergeRadar(base, radarData[key]), sym: key, _origSym: s };
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
      position: "relative", zIndex: 35,
    }}>
      <div style={{ minWidth: 240, display: "flex", flexDirection: "column", height: "100%", overflowY: "auto" }}>
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
          <button
            onClick={onPresetsOpen}
            style={{
              marginTop: 6,
              marginBottom: 2,
              width: "100%",
              padding: "5px 0",
              background: "transparent",
              border: "1px solid var(--amber)",
              borderRadius: 3,
              color: "var(--amber)",
              fontSize: 10,
              fontFamily: "var(--mono)",
              letterSpacing: "0.14em",
              cursor: "pointer",
            }}
          >
            CUSTOM PRESETS
          </button>
          <div style={{ display: "flex", flexDirection: "column", gap: 2, marginTop: 8, maxHeight: 168, overflowY: "auto" }}>
            {watchlists.map(w => {
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
          flex: 1, minHeight: 96, overflowY: "auto",
          display: "flex", flexDirection: "column", gap: 4,
        }}>
          {symAssets.map(a => {
            const c = window.verdictColors(a.verdict);
            const active = focusedSym === a.sym;
            return (
              <button key={a._origSym || a.sym}
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
        <div style={{ borderTop: "1px solid var(--line)", padding: "8px 10px", display: "flex", flexDirection: "column", gap: 2, flexShrink: 0 }}>
          <div className="mono" style={{ fontSize: 11, color: "var(--ink-4)", letterSpacing: "0.18em", padding: "2px 4px 6px 4px" }}>NAVIGATE</div>
          {[
            { id: "macro",    label: "MACRO WEATHER",  icon: "◈" },
            { id: "news",     label: "PREDATOR NEWS",  icon: "◉" },
            { id: "risk",     label: "RISK DESK",      icon: "⚖" },
            { id: "journal",  label: "TRADE JOURNAL",  icon: "◎" },
            { id: "options",  label: "OPTIONS",        icon: "◆" },
            { id: "lab",      label: "SIGNAL LAB",     icon: "◬" },
            { id: "settings", label: "SETTINGS",       icon: "⚙" },
            { id: "manual",   label: "MANUAL",         icon: "◌" },
          ].map(({ id, label, icon }) => {
            const active = currentPage === id;
            const HANDLERS = { macro: onMacro, news: onNews, lab: onLab, risk: onRisk, journal: onJournal, settings: onSettings, manual: onManual, options: onOptions };
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

        {/* power-off */}
        <div style={{ padding: "8px 14px", borderTop: "1px solid var(--line)", flexShrink: 0 }}>
          {shutdownState === "idle" && (
            <button
              onClick={() => setShutdownState("confirm")}
              style={{ background: "transparent", border: "1px solid var(--sell)", color: "var(--sell)", cursor: "pointer", padding: "5px 10px", fontFamily: "var(--mono)", fontSize: 11, letterSpacing: "0.14em", width: "100%" }}
            >⏻ STOP BANSHEE</button>
          )}
          {shutdownState === "confirm" && (
            <div>
              <div className="mono" style={{ fontSize: 11, color: "var(--ink-2)", letterSpacing: "0.08em", marginBottom: 8 }}>Stop the Banshee server?</div>
              <div style={{ display: "flex", gap: 6 }}>
                <button
                  onClick={async () => { await window.API.shutdownBanshee(); setShutdownState("done"); }}
                  style={{ flex: 1, background: "var(--sell)", border: "none", color: "#fff", cursor: "pointer", padding: "6px 0", fontFamily: "var(--mono)", fontSize: 11, fontWeight: 700, letterSpacing: "0.14em" }}
                >CONFIRM</button>
                <button
                  onClick={() => setShutdownState("idle")}
                  style={{ flex: 1, background: "transparent", border: "1px solid var(--line-2)", color: "var(--ink-3)", cursor: "pointer", padding: "6px 0", fontFamily: "var(--mono)", fontSize: 11, letterSpacing: "0.14em" }}
                >CANCEL</button>
              </div>
            </div>
          )}
          {shutdownState === "done" && (
            <div className="mono" style={{ fontSize: 11, color: "var(--ink-3)", letterSpacing: "0.08em", lineHeight: 1.5 }}>◇ Banshee stopped — you can close this tab.</div>
          )}
        </div>

        {/* footer */}
        <div style={{
          padding: "10px 14px",
          borderTop: "1px solid var(--line)",
          display: "flex", justifyContent: "space-between", alignItems: "center",
          flexShrink: 0,
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
    _live:          true,
    price:          typeof live.price   === "number" ? live.price   : base.price,
    chg:            typeof live.chg_pct === "number" ? live.chg_pct : base.chg,
    verdict:        live.verdict ?? base.verdict,
    edge:           typeof live.edge    === "number" ? normaliseEdge(live.edge) : base.edge,
    bias:           live.bias    ?? base.bias,
    rsi:            typeof live.rsi     === "number" ? Math.round(live.rsi) : base.rsi,
    atr:            live.atr_plan?.atr  ?? base.atr,
    volume:         live.volume         ?? base.volume,
    session_weight: typeof live.session_weight === "number" ? live.session_weight : base.session_weight,
  };
}

/* Resolve a user/preset symbol string to a known asset in window.ASSETS.
 * Matches (in priority order): exact sym, pair ("BTC/USD"→BTC), exact name,
 * then name-prefix ("Bitcoin"/"Apple"→ticker). Returns null if unknown.
 * The trailing "/USD" is the user's "force crypto" disambiguator — preserved,
 * never used to reject a match. */
function resolveKnownAsset(input) {
  if (!input) return null;
  const up = String(input).trim().toUpperCase();
  return window.ASSETS.find(a => a.sym.toUpperCase() === up)
      || window.ASSETS.find(a => (a.pair || "").toUpperCase() === up)
      || window.ASSETS.find(a => a.name.toUpperCase() === up)
      || (up.length >= 3 ? window.ASSETS.find(a => a.name.toUpperCase().startsWith(up)) : null)
      || null;
}

/* Canonical radar/lookup key for a stored symbol: the known asset's sym when
 * recognised (so we reuse data already fetched for the default 20), else the
 * stored string itself (custom symbols are fetched + keyed as-is). */
function canonSym(stored) {
  const known = resolveKnownAsset(stored);
  return known ? known.sym : stored;
}

/* Build a base asset object for any canonical key — the known asset when
 * recognised, otherwise a stub seeded from the cached snapshot. */
function resolveBaseAsset(key, snapshot = {}) {
  const known = window.ASSETS.find(a => a.sym === key) || resolveKnownAsset(key);
  if (known) return { ...known, sym: key };
  const cached   = snapshot[key] || {};
  const isCrypto = /[\/\-]USDT?$/i.test(key);
  const display  = key.replace(/[\/\-]USDT?$/i, "");
  return {
    sym: key, pair: key,
    name:    cached.name    || display,
    cls:     cached.cls     || (isCrypto ? "CRYPTO" : "EQUITY"),
    price:   cached.price   || 0,
    chg:     cached.chg     || 0,
    edge:    cached.edge    || 50,
    verdict: cached.verdict || "WAIT",
    bias:    cached.bias    || "→ FLAT",
    vol: 1, rsi: cached.rsi || 50, atr: 1,
  };
}
/* ── SettingsPage ──────────────────────────────────────────── */
const AI_PROVIDERS = ["Gemini", "OpenAI", "Anthropic", "Ollama", "Custom"];

const MCP_CONFIG_SNIPPET = `{
  "mcpServers": {
    "banshee-pro": {
      "command": "python",
      "args": ["C:/Users/swyli/AntiEverything/Banshee_6/mcp_server.py"]
    }
  }
}`;

const MCP_TOOLS = [
  ["get_regime",            "lightweight regime bucket + go/no-go (fast, cached)"],
  ["get_macro_weather",     "global macro environment — VIX, yield curve, liquidity"],
  ["get_watchlist",         "user's saved symbol list — call before scan_assets"],
  ["get_asset_radar",       "full multi-timeframe technical analysis for one asset"],
  ["get_smc_structure",     "SMC structure map — swings, BOS/CHoCH, FVGs, order blocks"],
  ["scan_assets",           "ranked scan across a list of symbols"],
  ["synthesize_nexus",      "top-down macro + micro + news AI briefing"],
  ["build_execution_plan",  "position sizing and R-target execution plan"],
  ["read_market_intel",     "daily Predator briefing or RSS fallback"],
  ["get_strategy_results",  "retrieve saved Strategy Lab backtests"],
  ["open_paper_trade",      "open a new paper trade"],
  ["check_kill_switch",     "close all positions if CRACK DETECTED (domino ≥ 2)"],
  ["log_signal_outcome",    "record exit reason or note on any trade"],
  ["get_signal_log",        "retrieve judged trades + regime/exit-reason stats"],
];

function MCPConnectionBlock() {
  const [copied, setCopied] = useState(false);

  function handleCopy() {
    navigator.clipboard.writeText(MCP_CONFIG_SNIPPET).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }

  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20 }}>
      <div>
        <div style={{ marginBottom: 8, display: "flex", alignItems: "center", gap: 12 }}>
          <window.Label>CLAUDE CONFIG SNIPPET</window.Label>
          <span className="mono" style={{ fontSize: 11, color: "var(--ink-4)", letterSpacing: "0.12em" }}>
            paste into ~/.claude/.mcp.json → mcpServers
          </span>
        </div>
        <pre style={{
          background: "var(--bg-3)", border: "1px solid var(--line-2)",
          padding: "12px 14px", margin: 0,
          fontFamily: "'JetBrains Mono', monospace", fontSize: 12,
          color: "var(--cyan)", letterSpacing: "0.05em", lineHeight: 1.7,
          overflowX: "auto", whiteSpace: "pre",
        }}>
          {MCP_CONFIG_SNIPPET}
        </pre>
        <div style={{ marginTop: 10, display: "flex", alignItems: "center", gap: 14 }}>
          <button onClick={handleCopy} style={{
            padding: "7px 18px",
            background: copied ? "rgba(52,211,153,0.12)" : "rgba(56,189,248,0.1)",
            color: copied ? "var(--buy)" : "var(--cyan)",
            border: `1px solid ${copied ? "var(--buy)" : "var(--cyan)"}`,
            cursor: "pointer",
            fontFamily: "'JetBrains Mono', monospace", fontSize: 13, fontWeight: 700, letterSpacing: "0.18em",
          }}>
            {copied ? "✓ COPIED" : "COPY"}
          </button>
          <span className="mono" style={{ fontSize: 11, color: "var(--ink-4)", letterSpacing: "0.1em" }}>
            Core must be running on :8765 before MCP tools respond
          </span>
        </div>
      </div>
      <div>
        <div style={{ marginBottom: 8 }}><window.Label>AVAILABLE TOOLS</window.Label></div>
        <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          {MCP_TOOLS.map(([name, desc]) => (
            <div key={name} style={{ display: "flex", gap: 10, alignItems: "baseline" }}>
              <span className="mono" style={{ fontSize: 12, color: "var(--cyan)", letterSpacing: "0.06em", flexShrink: 0, minWidth: 190 }}>
                {name}
              </span>
              <span className="mono" style={{ fontSize: 11, color: "var(--ink-3)", letterSpacing: "0.08em", lineHeight: 1.5 }}>
                {desc}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

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

function PinSettings() {
  const [enabled, setEnabled] = React.useState(localStorage.getItem('banshee_pin_enabled') === 'true');
  const [pin,     setPin]     = React.useState(localStorage.getItem('banshee_pin') || '');
  const [newPin,  setNewPin]  = React.useState('');
  const [saved,   setSaved]   = React.useState(false);

  const toggleEnable = () => {
    const next = !enabled;
    setEnabled(next);
    localStorage.setItem('banshee_pin_enabled', String(next));
  };

  const savePin = () => {
    if (newPin.length !== 4 || !/^\d{4}$/.test(newPin)) return;
    localStorage.setItem('banshee_pin', newPin);
    setPin(newPin);
    setNewPin('');
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  const inputStyle = {
    background: "var(--bg-3)", border: "1px solid var(--line)", color: "var(--ink)",
    fontFamily: "monospace", fontSize: 13, padding: "6px 10px",
    borderRadius: 3, outline: "none", width: 80, letterSpacing: "0.2em"
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <label style={{ display: "flex", alignItems: "center", gap: 10, cursor: "pointer" }}>
        <input type="checkbox" checked={enabled} onChange={toggleEnable} />
        <span className="mono" style={{ fontSize: 12, color: "var(--ink-3)", letterSpacing: "0.08em" }}>
          Require PIN on launch
        </span>
      </label>
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <input
          type="password"
          maxLength={4}
          value={newPin}
          onChange={e => setNewPin(e.target.value.replace(/\D/g, '').slice(0, 4))}
          placeholder={pin ? '••••' : '4 digits'}
          style={inputStyle}
        />
        <button onClick={savePin} disabled={newPin.length !== 4}
          style={{ fontFamily: "inherit", fontSize: 11, letterSpacing: "0.1em",
            background: saved ? "var(--buy)" : "var(--bg-3)",
            color: saved ? "#000" : "var(--ink)", border: "1px solid var(--line)",
            padding: "6px 14px", borderRadius: 3, cursor: "pointer" }}>
          {saved ? "✓ SAVED" : "SET PIN"}
        </button>
      </div>
      {enabled && !pin && (
        <div className="mono" style={{ fontSize: 11, color: "var(--amber)" }}>
          Set a PIN above to activate the lock
        </div>
      )}
      {pin && (
        <div className="mono" style={{ fontSize: 11, color: "var(--ink-4)" }}>
          PIN is set · {enabled ? "Lock active on next launch" : "Lock disabled"}
        </div>
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
  const [aiCtxWindow, setAiCtxWindow] = useState(32768);
  const [allowAiRescue, setAllowAiRescue]   = useState(true);
  const [apiSaveStatus, setApiSaveStatus]   = useState(null);
  const [aiSaveStatus, setAiSaveStatus]     = useState(null);
  const [rescueSaveStatus, setRescueSaveStatus] = useState(null);
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
      setAiCtxWindow(ai.context_window || 32768);
      setAllowAiRescue(data.allow_ai_data_rescue !== false);
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
      AI_API: { type: aiType, key: aiKey, model: aiModel, url: aiUrl, context_window: aiCtxWindow },
    });
    setAiSaveStatus(result.status === "saved" ? "saved" : "error: " + (result.message || "?"));
    setTimeout(() => setAiSaveStatus(null), 3000);
  }

  async function saveDataRecovery() {
    setRescueSaveStatus("saving");
    const result = await window.API.saveSettings({ allow_ai_data_rescue: allowAiRescue });
    setRescueSaveStatus(result.status === "saved" ? "saved" : "error: " + (result.message || "?"));
    setTimeout(() => setRescueSaveStatus(null), 3000);
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
        <button onClick={onBack} style={{ display: "flex", alignItems: "center", gap: 6, padding: "6px 10px", background: "transparent", border: "1px solid var(--line-2)", color: "#FF6D00", cursor: "pointer" }}>
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
            {aiType === "Ollama" && (
              <SettingsField label="CONTEXT WINDOW" hint="tokens — 32768 for Gemma 4, min supported">
                <input
                  type="number" min="32768" step="1024"
                  value={aiCtxWindow} onChange={e => setAiCtxWindow(parseInt(e.target.value) || 32768)}
                  style={INPUT_STYLE}
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

        {/* DATA RECOVERY */}
        <SettingsSection title="▸ DATA RECOVERY">
          <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "8px 0" }}>
            <input
              type="checkbox"
              id="ai-rescue-toggle"
              checked={allowAiRescue}
              onChange={e => setAllowAiRescue(e.target.checked)}
              style={{ accentColor: "#FF6D00", width: 16, height: 16, cursor: "pointer" }}
            />
            <label
              htmlFor="ai-rescue-toggle"
              style={{ color: "var(--ink)", fontSize: 12, fontFamily: "monospace", cursor: "pointer" }}
            >
              ALLOW AI TO SELF-HEAL DATA FORMAT CHANGES
            </label>
          </div>
          <div style={{ color: "var(--ink-3)", fontSize: 11, marginTop: 4 }}>
            When yfinance returns unexpected column names, calls your AI to remap them.
            Disable to prevent unintended AI usage during data outages.
          </div>
          <SaveRow onSave={saveDataRecovery} status={rescueSaveStatus} />
        </SettingsSection>

        {/* PIN LOCK */}
        <SettingsSection title="▸ PIN LOCK">
          <PinSettings />
        </SettingsSection>

        {/* MCP CONNECTION — full width */}
        <div style={{ gridColumn: "1 / -1" }}>
          <SettingsSection title="▸ MCP CONNECTION">
            <MCPConnectionBlock />
          </SettingsSection>
        </div>

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

function MacroPage({ macroData, onBack, manualStories = [] }) {
  const [aiText, setAiText]       = useState(null);
  const [aiLoading, setAiLoading] = useState(false);
  const [aiError, setAiError]     = useState(null);
  const [rotationData,    setRotationData]    = useState(null);
  const [rotationLoading, setRotationLoading] = useState(true);

  const sensors = macroData?.sensors;
  const macroTop = macroData ? sensorsToTopBar(macroData) : window.MACRO;
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
          <button onClick={onBack} style={{ background: "none", border: "none", color: "#FF6D00", cursor: "pointer", fontSize: 16, padding: 0 }}>←</button>
          <div>
            <div className="mono" style={{ fontSize: 13, fontWeight: 700, letterSpacing: "0.18em", color: "var(--ink)" }}>◬ SIGNAL LAB</div>
            <div className="mono" style={{ fontSize: 13, color: "var(--ink-4)", letterSpacing: "0.1em", marginTop: 2 }}>Saved backtest results</div>
          </div>
        </div>
      </div>

      <div style={{ padding: "16px 24px", flex: 1 }}>
        {loading ? (
          <div className="mono" style={{ color: "var(--ink-4)", fontSize: 13 }}>◇ Loading…</div>
        ) : entries.length === 0 ? (
          <div style={{ textAlign: "center", padding: "60px 0" }}>
            <div className="mono" style={{ color: "var(--ink-4)", fontSize: 12 }}>No saved backtest results yet.</div>
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

/* ── RiskDeskPage — reactive position sizing calculator (Page 6) */
function RiskDeskPage({ seedAsset, simulateMode, onBack }) {
  const [account,      setAccount]      = useState(10000);
  const [riskPct,      setRiskPct]      = useState(1.0);
  const [entry,        setEntry]        = useState(0);
  const [stop,         setStop]         = useState(0);
  const [conflicted,   setConflicted]   = useState(false);
  const [plan,         setPlan]         = useState(null);
  const [calculating,  setCalculating]  = useState(false);
  const [calcError,    setCalcError]    = useState(null);
  const [searchSym,    setSearchSym]    = useState("");
  const [searchLoading, setSearchLoading] = useState(false);
  const [searchError,  setSearchError]  = useState(null);
  const [activeSeed,   setActiveSeed]   = useState(null); // { sym, verdict, edge } for paper trade
  const [paperStatus,  setPaperStatus]  = useState("idle"); // "idle"|"loading"|"success"|"error"
  const [paperError,   setPaperError]   = useState(null);

  /* auto-populate from seedAsset on mount */
  useEffect(() => {
    if (!seedAsset) return;
    const v   = seedAsset.verdict || "";
    const atr = seedAsset.atr_plan;
    setEntry(seedAsset.price || 0);
    if (atr && v.includes("BUY")  && atr.stop_long)  setStop(parseFloat(Number(atr.stop_long).toFixed(4)));
    else if (atr && v.includes("SELL") && atr.stop_short) setStop(parseFloat(Number(atr.stop_short).toFixed(4)));
    else {
      const dir = v.includes("SELL") ? -1 : 1;
      setStop(parseFloat((seedAsset.price - dir * (seedAsset.atr || 0) * 1.2).toFixed(4)));
    }
    setActiveSeed({ sym: seedAsset.sym, verdict: v, edge: String(seedAsset.edge ?? "") });
  }, []); // mount only — seedAsset is a snapshot, not live

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

  async function handleSearch() {
    const sym = searchSym.trim().toUpperCase();
    if (!sym) return;
    setSearchLoading(true);
    setSearchError(null);
    const res = await window.API.fetchRadar(sym, "swing");
    setSearchLoading(false);
    if (!res || res.error || typeof res.price !== "number") {
      setSearchError(`Symbol "${sym}" not found`);
      return;
    }
    const v   = res.verdict || "";
    const atr = res.atr_plan;
    setEntry(res.price || 0);
    if (atr && v.includes("BUY")  && atr.stop_long)  setStop(parseFloat(Number(atr.stop_long).toFixed(4)));
    else if (atr && v.includes("SELL") && atr.stop_short) setStop(parseFloat(Number(atr.stop_short).toFixed(4)));
    else {
      const dir = v.includes("SELL") ? -1 : 1;
      setStop(parseFloat((res.price - dir * (res.atr_plan?.atr || 0) * 1.2).toFixed(4)));
    }
    setPlan(null); // force recalculate
    setActiveSeed({ sym, verdict: v, edge: String(res.edge ?? "") });
  }

  async function handlePaperTrade() {
    if (!activeSeed?.sym || !entry || !stop) return;
    const isL = entry > stop;
    const targetPrice = entry + (isL ? 1 : -1) * Math.abs(entry - stop) * 1.5;
    setPaperStatus("loading");
    setPaperError(null);
    const result = await window.API.journalOpen({
      symbol:       activeSeed.sym,
      direction:    isL ? "long" : "short",
      entry_price:  entry,
      stop_price:   stop,
      target_price: targetPrice,
      position_usd: plan?.position_value ?? 1000,
      verdict:      activeSeed.verdict,
      edge:         activeSeed.edge,
      mode:         "swing",
      notes:        "Simulated from Risk Desk",
    });
    if (result?.error) {
      setPaperStatus("error");
      setPaperError(result.error);
    } else {
      setPaperStatus("success");
    }
  }

  useEffect(() => {
    if (paperStatus !== "success") return;
    const id = setTimeout(() => onBack(), 1500);
    return () => clearTimeout(id);
  }, [paperStatus]);

  const isLong      = plan?.is_long ?? (entry > stop);
  const dirColor    = isLong ? "var(--buy)" : "var(--sell)";
  const conflictClr = "var(--sell)";

  return (
    <div style={{ position: "absolute", inset: 0, background: "var(--bg-0)", zIndex: 20, overflowY: "auto", display: "flex", flexDirection: "column" }}>
      {/* header */}
      <div style={{ padding: "18px 24px 14px", borderBottom: "1px solid var(--line)", display: "flex", alignItems: "center", gap: 16, flexShrink: 0 }}>
        <button onClick={onBack} style={{ background: "none", border: "none", color: "#FF6D00", cursor: "pointer", fontSize: 16, padding: 0 }}>←</button>
        <div>
          <div className="mono" style={{ fontSize: 13, fontWeight: 700, letterSpacing: "0.18em", color: "var(--ink)" }}>⚖ RISK DESK</div>
          <div className="mono" style={{ fontSize: 13, color: "var(--ink-4)", letterSpacing: "0.1em", marginTop: 2 }}>
            Position size · Margin · R-multiples{activeSeed ? ` · ${activeSeed.sym}` : ""}
          </div>
        </div>
      </div>

      {simulateMode && activeSeed && (
        <div className="mono" style={{ padding: "8px 24px", background: "rgba(0,229,255,0.06)", borderBottom: "1px solid var(--cyan)", fontSize: 13, color: "var(--cyan)", letterSpacing: "0.14em" }}>
          ◇ SIMULATION MODE · {activeSeed.sym}
        </div>
      )}

      <div style={{ padding: "20px 24px", flex: 1 }}>
        {/* search box */}
        <div style={{ display: "flex", gap: 8, marginBottom: 16, alignItems: "center" }}>
          <input
            type="text"
            value={searchSym}
            onChange={e => setSearchSym(e.target.value)}
            onKeyDown={e => e.key === "Enter" && handleSearch()}
            placeholder="Type symbol (e.g. NVDA, BTC) and press Enter"
            className="mono"
            style={{ flex: 1, background: "var(--bg-1)", border: "1px solid var(--line-2)", color: "var(--ink)", padding: "8px 12px", fontSize: 13, letterSpacing: "0.08em", outline: "none" }}
          />
          <button
            onClick={handleSearch}
            disabled={searchLoading}
            className="mono"
            style={{ padding: "8px 16px", background: "var(--cyan)", color: "var(--bg-0)", border: "none", cursor: searchLoading ? "wait" : "pointer", fontWeight: 700, letterSpacing: "0.14em", opacity: searchLoading ? 0.6 : 1 }}
          >
            {searchLoading ? "…" : "LOAD"}
          </button>
        </div>
        {searchError && (
          <div className="mono" style={{ fontSize: 13, color: "var(--sell)", marginBottom: 12 }}>{searchError}</div>
        )}
        {activeSeed && (
          <div className="mono" style={{ fontSize: 12, color: "var(--ink-4)", letterSpacing: "0.1em", marginBottom: 12 }}>
            ◆ {activeSeed.sym} · {activeSeed.verdict || "–"} · Edge {activeSeed.edge}
          </div>
        )}
        {/* inputs */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 16, marginBottom: 16 }}>
          <window.NumInput label="ACCOUNT SIZE ($)" value={account} onChange={setAccount} step={100} />
          <window.NumInput label="RISK PER TRADE (%)" value={riskPct} onChange={setRiskPct} step={0.1} />
          <window.NumInput label="ENTRY PRICE ($)" value={entry} onChange={setEntry} step={0.01} />
          <window.NumInput label="STOP-LOSS PRICE ($)" value={stop} onChange={setStop} step={0.01} />
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

      {simulateMode && (
        <div style={{ padding: "16px 24px", borderTop: "1px solid var(--line)", flex: "0 0 auto", background: "var(--bg-1)" }}>
          {paperStatus === "success" ? (
            <div className="mono" style={{ textAlign: "center", fontSize: 14, color: "var(--buy)", letterSpacing: "0.14em" }}>◆ PAPER TRADE LOGGED</div>
          ) : (
            <>
              <button
                onClick={handlePaperTrade}
                disabled={paperStatus === "loading" || !activeSeed?.sym || !entry || !stop}
                className="mono"
                style={{ width: "100%", padding: "14px", background: isLong ? "var(--buy)" : "var(--sell)", color: "var(--bg-0)", border: "none", cursor: (paperStatus === "loading" || !activeSeed?.sym) ? "not-allowed" : "pointer", fontWeight: 700, fontSize: 14, letterSpacing: "0.2em", opacity: (paperStatus === "loading" || !activeSeed?.sym) ? 0.5 : 1 }}
              >
                {paperStatus === "loading" ? "◇ LOGGING…" : "◆ PAPER TRADE"}
              </button>
              {paperStatus === "error" && (
                <div className="mono" style={{ fontSize: 12, color: "var(--sell)", marginTop: 8, textAlign: "center" }}>{paperError}</div>
              )}
            </>
          )}
        </div>
      )}
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
  const openTrades   = trades.filter(t => !t.closed_at).reverse();
  const closedTrades = trades.filter(t =>  t.closed_at).reverse();

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
          <button onClick={onBack} style={{ background: "none", border: "none", color: "#FF6D00", cursor: "pointer", fontSize: 16, padding: 0 }}>←</button>
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
      {url
        ? <a href={url} target="_blank" rel="noreferrer" style={{ textDecoration: "none" }}>
            <div className="mono" style={{ fontSize: 13, fontWeight: 700, color: "var(--ink)", marginBottom: 4, cursor: "pointer" }}
              onMouseEnter={e => e.currentTarget.style.color = "var(--cyan)"}
              onMouseLeave={e => e.currentTarget.style.color = "var(--ink)"}>
              {headline}
            </div>
          </a>
        : <div className="mono" style={{ fontSize: 13, fontWeight: 700, color: "var(--ink)", marginBottom: 4 }}>{headline}</div>
      }
      <div className="mono" style={{ fontSize: 12, color: "var(--ink-3)", lineHeight: 1.5, marginBottom: 8,
        display: "-webkit-box", WebkitLineClamp: 3, WebkitBoxOrient: "vertical", overflow: "hidden" }}>
        {lede}
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
        <span className="mono" style={{ fontSize: 11, background: "var(--bg-3)", color: url ? "var(--ink-3)" : "var(--ink-4)",
          padding: "1px 6px", borderRadius: 3, border: "1px solid var(--line)" }}>{source}</span>
        <span className="mono" style={{ fontSize: 11, background: impactBg, color: "#fff",
          padding: "1px 6px", borderRadius: 3 }}>{impact_score}/10</span>
        {symbols.map(s => (
          <span key={s} className="mono" style={{ fontSize: 11, color: "var(--ink-4)",
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
        <span className="mono" style={{ fontSize: 11, background: pillColor, color: "#fff",
          padding: "1px 7px", borderRadius: 3, textTransform: "uppercase", letterSpacing: "0.1em" }}>
          {status || "?"}
        </span>
        <span className="mono" style={{ fontSize: 12, fontWeight: 700, color: "var(--ink)" }}>{original}</span>
      </div>
      <div className="mono" style={{ fontSize: 12, color: "var(--ink-3)", lineHeight: 1.5 }}>{update}</div>
    </div>
  );
}

/* ── StoryInput / StoryPanel — session-level injected constraint UI ─────── */
function StoryInput({ onAdd }) {
  const [val, setVal] = React.useState('');
  const submit = () => {
    const trimmed = val.trim();
    if (!trimmed) return;
    onAdd(trimmed);
    setVal('');
  };
  return (
    <div style={{ display: "flex", gap: 6 }}>
      <input
        type="text"
        value={val}
        onChange={e => setVal(e.target.value)}
        onKeyDown={e => e.key === "Enter" && submit()}
        placeholder="e.g. Avoid NVIDIA — earnings risk"
        style={{ flex: 1, background: "var(--bg-3)", border: "1px solid var(--line)",
          color: "var(--ink)", fontFamily: "monospace", fontSize: 11,
          padding: "5px 8px", borderRadius: 3, outline: "none" }}
      />
      <button onClick={submit}
        style={{ fontFamily: "inherit", fontSize: 11, letterSpacing: "0.1em",
          background: "var(--amber)", color: "#000", border: "none",
          padding: "5px 12px", borderRadius: 3, cursor: "pointer" }}>
        + ADD
      </button>
    </div>
  );
}

function StoryPanel({ manualStories, setManualStories }) {
  return (
    <div style={{ marginBottom: 14, background: "var(--bg-2)", border: "1px solid var(--line)", borderRadius: 4, padding: "12px 14px" }}>
      <div className="mono" style={{ fontSize: 11, letterSpacing: "0.18em", color: "var(--ink-4)", marginBottom: 8 }}>
        INJECTED CONSTRAINTS <span style={{ color: "var(--amber)" }}>· Highest priority context for every AI briefing</span>
      </div>
      <StoryInput onAdd={story => setManualStories(prev => [...prev, story])} />
      {manualStories.length > 0 && (
        <div style={{ marginTop: 8, display: "flex", flexDirection: "column", gap: 4 }}>
          {manualStories.map((s, i) => (
            <div key={s} style={{ display: "flex", alignItems: "flex-start", gap: 8,
              background: "var(--bg-3)", padding: "6px 10px", borderRadius: 3,
              borderLeft: "2px solid var(--amber)" }}>
              <span className="mono" style={{ fontSize: 11, color: "var(--ink)", flex: 1, lineHeight: 1.5 }}>{s}</span>
              <button onClick={() => setManualStories(prev => prev.filter((_, j) => j !== i))}
                style={{ background: "none", border: "none", color: "var(--sell)", cursor: "pointer",
                  fontSize: 14, padding: 0, lineHeight: 1, flexShrink: 0 }}>×</button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

/* ── NewsPage — Daily Predator intelligence briefing (Page 9) ───────────── */
function NewsPage({ onBack, manualStories = [], setManualStories }) {
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
    const result = await window.API.runPredator(true, manualStories);
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
      {count != null && <span style={{ background: "var(--bg-3)", padding: "0 6px", borderRadius: 3, fontSize: 11 }}>{count}</span>}
      {extra && <span style={{ color: "var(--amber)" }}>{extra}</span>}
    </div>
  );

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", background: "var(--bg-1)", color: "var(--ink)", overflow: "hidden" }}>
      {/* Back nav */}
      <div style={{ padding: "18px 24px 14px", borderBottom: "1px solid var(--line)", display: "flex", alignItems: "center", gap: 16, flexShrink: 0 }}>
        <button onClick={onBack} style={{ background: "none", border: "none", color: "#FF6D00", cursor: "pointer", fontSize: 16, padding: 0 }}>←</button>
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
          <div style={{ marginTop: 40 }}>
            <StoryPanel manualStories={manualStories} setManualStories={setManualStories} />
            <div style={{ textAlign: "center" }}>
            <div className="mono" style={{ fontSize: 13, color: "var(--ink-4)", marginBottom: 16 }}>No briefing yet for today.</div>
            <button onClick={handleRun} disabled={running}
              style={{ fontFamily: "inherit", fontSize: 12, letterSpacing: "0.12em", background: "var(--amber)",
                color: "#000", border: "none", padding: "8px 18px", borderRadius: 4, cursor: "pointer" }}>
              {running ? "◌ RUNNING PIPELINE…" : "▶ RUN DAILY PREDATOR"}
            </button>
            {running && <div className="mono" style={{ fontSize: 11, color: "var(--ink-4)", marginTop: 8 }}>This takes 2–3 minutes</div>}
            {runError && <div className="mono" style={{ fontSize: 11, color: "var(--sell)", marginTop: 8 }}>{runError}</div>}
            </div>
          </div>
        ) : (
          <>
            {/* Masthead */}
            <div style={{ textAlign: "center", marginBottom: 18, paddingBottom: 14, borderBottom: "1px solid var(--line)" }}>
              <div className="mono" style={{ fontSize: 18, fontWeight: 700, letterSpacing: "0.3em", color: "var(--ink)" }}>THE DAILY PREDATOR</div>
              <div className="mono" style={{ fontSize: 11, color: "var(--ink-4)", marginTop: 4, letterSpacing: "0.1em" }}>
                {briefing.date} · Powered by Banshee 6
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
                <div className="mono" style={{ fontSize: 11, letterSpacing: "0.18em", color: "var(--amber)", marginBottom: 6 }}>TOP STORY</div>
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

            {/* Injected context panel */}
            <StoryPanel manualStories={manualStories} setManualStories={setManualStories} />

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

/* ── ManualPage helpers ─────────────────────────────────────── */
function ManLensCard({ num, name, accent, question, shows, use }) {
  return (
    <div style={{ background: "var(--bg-3)", border: "1px solid var(--line)", borderLeft: `3px solid ${accent}`, padding: "12px 14px" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8 }}>
        <span className="mono" style={{ background: accent, color: "var(--bg-0)", fontSize: 13, fontWeight: 700, width: 22, height: 22, display: "inline-flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>{num}</span>
        <span className="mono" style={{ fontSize: 14, fontWeight: 700, letterSpacing: "0.14em", color: accent }}>{name}</span>
        <span className="mono" style={{ fontSize: 12, color: "var(--ink-4)", marginLeft: "auto" }}>KEY {num}</span>
      </div>
      <div className="mono" style={{ fontSize: 12, color: "var(--amber)", letterSpacing: "0.04em", fontStyle: "italic", marginBottom: 8 }}>"{question}"</div>
      <div style={{ fontSize: 13, color: "var(--ink-2)", lineHeight: 1.65, marginBottom: 6 }}><span style={{ color: "var(--ink-3)", fontWeight: 600 }}>Shows: </span>{shows}</div>
      <div style={{ fontSize: 13, color: "var(--ink-2)", lineHeight: 1.65 }}><span style={{ color: "var(--ink-3)", fontWeight: 600 }}>Use when: </span>{use}</div>
    </div>
  );
}
function ManConcept({ name, accent, encoding, children }) {
  return (
    <div style={{ borderLeft: `3px solid ${accent || "var(--line-2)"}`, paddingLeft: 12, marginBottom: 16 }}>
      <div className="mono" style={{ fontSize: 13, fontWeight: 700, color: accent || "var(--ink)", letterSpacing: "0.08em", marginBottom: 4 }}>{name}</div>
      <div style={{ fontSize: 13, color: "var(--ink-2)", lineHeight: 1.65, marginBottom: encoding ? 5 : 0 }}>{children}</div>
      {encoding && <div className="mono" style={{ fontSize: 12, color: "var(--ink-4)", letterSpacing: "0.04em" }}>{encoding}</div>}
    </div>
  );
}
function ManStep({ n, title, children }) {
  return (
    <div style={{ display: "flex", gap: 12, marginBottom: 14 }}>
      <span className="mono" style={{ fontSize: 13, fontWeight: 700, color: "var(--cyan)", minWidth: 20, paddingTop: 1, flexShrink: 0 }}>{n}.</span>
      <div>
        <div className="mono" style={{ fontSize: 13, fontWeight: 700, color: "var(--ink)", letterSpacing: "0.08em", marginBottom: 3 }}>{title}</div>
        <div style={{ fontSize: 13, color: "var(--ink-2)", lineHeight: 1.65 }}>{children}</div>
      </div>
    </div>
  );
}
function ManSectionHdr({ title, accent, sub }) {
  return (
    <div style={{ padding: "10px 16px", borderBottom: "1px solid var(--line)", borderLeft: `3px solid ${accent}`, display: "flex", alignItems: "center", gap: 8 }}>
      <span className="mono" style={{ fontSize: 12, fontWeight: 700, letterSpacing: "0.18em", color: accent }}>{title}</span>
      {sub && <span className="mono" style={{ fontSize: 12, color: "var(--ink-4)", marginLeft: "auto" }}>{sub}</span>}
    </div>
  );
}

/* ── ManualPage — in-app reference guide (Page 8) ──────────── */
function ManualPage({ onBack }) {
  const CARD = { background: "var(--bg-2)", border: "1px solid var(--line)" };
  const XABCD_PATTERNS = [
    ["GARTLEY",   "0.618 XA",       "0.382–0.886 AB", "0.786 XA"],
    ["BAT",       "0.382–0.5 XA",   "0.382–0.886 AB", "0.886 XA"],
    ["ALT BAT",   "0.382 XA",       "0.382–0.886 AB", "1.13 XA"],
    ["BUTTERFLY", "0.786 XA",       "0.382–0.886 AB", "1.272–1.618 XA"],
    ["CRAB",      "0.382–0.618 XA", "0.382–0.886 AB", "1.618 XA"],
    ["DEEP CRAB", "0.886 XA",       "0.382–0.886 AB", "1.618 XA"],
    ["SHARK",     "0.446–0.618 XA", "1.13–1.618 BC",  "0.886–1.13 OX"],
    ["5-0",       "BC extension",   "1.618–2.24 AB",  "0.5 BC"],
  ];
  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", background: "var(--bg-1)", color: "var(--ink)", overflow: "hidden" }}>

      {/* Header */}
      <div style={{ padding: "18px 24px 14px", borderBottom: "1px solid var(--line)", display: "flex", alignItems: "center", gap: 16, flexShrink: 0 }}>
        <button onClick={onBack} style={{ background: "none", border: "none", color: "#FF6D00", cursor: "pointer", fontSize: 16, padding: 0 }}>←</button>
        <div>
          <div className="mono" style={{ fontSize: 13, fontWeight: 700, letterSpacing: "0.18em", color: "var(--ink)" }}>◌ MANUAL</div>
          <div className="mono" style={{ fontSize: 12, color: "var(--ink-4)", letterSpacing: "0.1em", marginTop: 2 }}>Lenses · Setup workflow · Risk Desk · SMC concepts · GH arcs · XABCD</div>
        </div>
      </div>

      {/* Scrollable content */}
      <div style={{ flex: 1, overflowY: "auto", padding: "20px 24px", display: "flex", flexDirection: "column", gap: 20 }}>

        {/* THE FOUR LENSES */}
        <div style={CARD}>
          <ManSectionHdr title="THE FOUR LENSES" accent="var(--cyan)" sub="SMC ANALYSIS · HOTKEYS 1–4" />
          <div style={{ padding: "14px 16px", display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
            <ManLensCard num={1} name="ALL" accent="var(--ink-2)"
              question="What's the full picture?"
              shows="Everything: OBs, FVGs, HTF reference lines, swing markers, EQH/EQL liquidity, PD background. Dynamic weight applied — elements near current price are brighter."
              use="Getting oriented on a new asset. Warning: visual density is high. Always switch to a focused lens before making any decisions." />
            <ManLensCard num={2} name="BATTLEFIELD" accent="var(--cyan)"
              question="Should I be long or short?"
              shows="Trend structure only — swing high/low markers, BOS and CHoCH event boxes, HTF reference levels, premium/discount gradient, OTE price lines. No OBs or FVGs."
              use="First step every session. Read the structural narrative before you look at entry zones. A bullish structure means you're hunting longs; bearish means shorts." />
            <ManLensCard num={3} name="FOOTPRINTS" accent="var(--magenta)"
              question="Where did institutions leave a mess?"
              shows="FVGs (imbalances price must return to fill), EQH/EQL liquidity pools (retail stop clusters), and pending-inducement OBs (traps not yet fired)."
              use="Finding magnets and traps. Pair with BATTLEFIELD context: a bullish FVG in the discount zone is a buy target; an EQL just below your OB is the trigger that must fire first." />
            <ManLensCard num={4} name="SNIPER" accent="var(--amber)"
              question="Where exactly do I pull the trigger?"
              shows="Inducement-swept OBs (full opacity — ready to enter), untagged OBs (40%), touched/degraded OBs (20%). OTE lines remain. Everything else hidden."
              use="Final step before entry. If nothing appears on SNIPER, there is no high-conviction setup on this timeframe. That is useful information — don't force a trade." />
          </div>
        </div>

        {/* SETUP WORKFLOW */}
        <div style={CARD}>
          <ManSectionHdr title="SETUP WORKFLOW" accent="var(--amber)" sub="8 STEPS · IN ORDER" />
          <div style={{ padding: "14px 16px" }}>
            <ManStep n={1} title="READ STRUCTURE STATE">
              The sidebar shows BULLISH / BEARISH / UNDEFINED — the state machine's verdict from the swing sequence. This is your filter for everything downstream. An UNDEFINED state means no clear trend; only take high-confluence setups.
            </ManStep>
            <ManStep n={2} title="BATTLEFIELD CHECK  (key 2)">
              Confirm the swing sequence visually. HH/HL chain = bullish. LH/LL = bearish. If you see a CHoCH in your direction, structure may be flipping — wait for a follow-through BOS before switching bias. Don't anticipate what isn't confirmed yet.
            </ManStep>
            <ManStep n={3} title="ZONE CHECK — PREMIUM OR DISCOUNT?">
              {"Green background = discount (below 50%). Red = premium (above 50%). The OTE band (amber lines, 61–79%) is the ideal pullback zone. Long setups belong in discount or OTE. Short setups in premium. If price is at EQ, wait for it to commit to a side."}
            </ManStep>
            <ManStep n={4} title="FOOTPRINTS CHECK  (key 3)">
              {"Are there FVGs or EQH/EQL in your target zone? A bullish FVG in the discount zone is a price magnet — expect a return before continuation. An EQL just below your OB is inducement that must be swept before the OB is actionable."}
            </ManStep>
            <ManStep n={5} title="SNIPER — FIND THE OB  (key 4)">
              {"⚡ Green border = inducement swept → enter at the OB zone. ⌛ Amber border = trap set but not fired → watch, don't enter yet. No border = lower conviction. Skip degraded or sapped OBs — they failed to hold."}
            </ManStep>
            <ManStep n={6} title="HTF ALIGNMENT">
              Run the same check on a higher timeframe (e.g. 1D when you're on 4H). A bullish 4H setup inside a bearish 1D structure is counter-trend — lower size or skip. HTF and LTF agreement is the conviction multiplier.
            </ManStep>
            <ManStep n={7} title="SESSION WEIGHT CHECK">
              {"OBs formed or approached during ⚡ Silver Bullet windows (03–04, 10–11, 14–15 EST) carry 2× weight. ◈ London/NY Killzones carry 1.5×. Asian range (20:00–00:00) carries 0.5× — entries here are lower probability. The badge on each OB tells you its session weight."}
            </ManStep>
            <ManStep n={8} title="AI BRIEFING — CROSS-CHECK YOUR READ">
              Read the SMC Analysis brief to catch what you missed. If the AI read contradicts your interpretation, investigate — the engine may be seeing structure you skipped, or it may be wrong. Either way, the discrepancy is worth understanding before you commit size.
            </ManStep>
          </div>
        </div>

        {/* RISK DESK + SIMULATE */}
        <div style={CARD}>
          <ManSectionHdr title="RISK DESK + SIMULATE" accent="var(--amber)" sub="SIDEBAR · ⚖ RISK DESK  ·  ASSET HUB · SIMULATE / EXECUTE" />
          <div style={{ padding: "14px 16px" }}>
            <div style={{ fontSize: 13, color: "var(--ink-2)", lineHeight: 1.7, marginBottom: 14 }}>
              Risk Desk is a pure position-sizing calculator — it never places real orders. Enter your account size, risk %, entry price, and stop price to get position size, leverage table, and R-multiple exit targets. Simulate logs a paper trade to the journal without touching a broker.
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14, marginBottom: 14 }}>
              <div style={{ borderLeft: "3px solid var(--amber)", paddingLeft: 12 }}>
                <div className="mono" style={{ fontSize: 12, fontWeight: 700, color: "var(--amber)", letterSpacing: "0.08em", marginBottom: 4 }}>FROM AN ASSET — TWO PATHS</div>
                <div style={{ fontSize: 13, color: "var(--ink-2)", lineHeight: 1.65 }}>
                  <strong style={{ color: "var(--ink)" }}>SIMULATE NOW</strong> — logs a $1,000 paper trade directly from AssetHub values (entry, ATR stop, 1.5R target). Fastest path. Use it when you've already validated the setup and just want a journal entry.<br/><br/>
                  <strong style={{ color: "var(--ink)" }}>OPEN RISK DESK</strong> — navigates to Risk Desk pre-filled with the current asset's price and ATR-derived stop. Adjust account size or risk % before confirming. Use it when you want to size carefully.
                </div>
              </div>
              <div style={{ borderLeft: "3px solid var(--cyan)", paddingLeft: 12 }}>
                <div className="mono" style={{ fontSize: 12, fontWeight: 700, color: "var(--cyan)", letterSpacing: "0.08em", marginBottom: 4 }}>STANDALONE — SEARCH BOX</div>
                <div style={{ fontSize: 13, color: "var(--ink-2)", lineHeight: 1.65 }}>
                  Open Risk Desk from the sidebar without an asset selected. Type any ticker (e.g. NVDA, BTC) and hit Enter — it fetches live price and stop from Core and auto-fills the calculator. Account size and risk % are preserved across searches, so you can compare position sizes across assets without re-entering your portfolio settings.
                </div>
              </div>
            </div>
            <div style={{ background: "var(--bg-3)", border: "1px solid var(--line)", padding: "10px 14px", marginBottom: 12 }}>
              <div className="mono" style={{ fontSize: 12, color: "var(--ink-3)", letterSpacing: "0.1em", marginBottom: 8 }}>SIMULATE MODE (from OPEN RISK DESK)</div>
              <div style={{ fontSize: 13, color: "var(--ink-2)", lineHeight: 1.75 }}>
                A cyan <strong style={{ color: "var(--cyan)" }}>◇ SIMULATION MODE · {"{SYM}"}</strong> banner appears at the top. At the bottom, a full-width <strong style={{ color: "var(--ink)" }}>◆ PAPER TRADE</strong> button (buy/sell color) posts to the Trade Journal using Risk Desk's current position size, entry, stop, and a computed 1.5R target. On success: "◆ PAPER TRADE LOGGED" → auto-navigates back to the asset view after 1.5s.
              </div>
            </div>
            <div className="mono" style={{ fontSize: 12, color: "var(--ink-4)", letterSpacing: "0.06em", lineHeight: 1.7 }}>
              EXECUTE button — visible but intentionally not wired to a broker. Clicking it shows a message: "Direct broker execution is not enabled. Use Simulate to log paper trades in the journal." This is a deliberate architectural decision — no live order execution in Banshee.  ·  SMC CONFLICTED checkbox halves position size when HTF and LTF structure disagree.
            </div>
          </div>
        </div>

        {/* SMC CONCEPTS GLOSSARY */}
        <div style={CARD}>
          <ManSectionHdr title="SMC CONCEPTS" accent="var(--ink-2)" sub="REFERENCE GLOSSARY" />
          <div style={{ padding: "14px 16px", display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0 32px" }}>
            <ManConcept name="SWING POINTS" accent="var(--ink-2)"
              encoding="▲ Orange triangle = swing high  ·  ▼ Blue triangle = swing low">
              5-candle fractal: a swing high is a candle whose high exceeds the 2 candles on each side. Foundation of all downstream structure — OBs, BOS, CHoCH, and inducement all derive from these pivots. The labels (HH, LH, HL, LL) tell you the structural sequence.
            </ManConcept>
            <ManConcept name="BOS — BREAK OF STRUCTURE" accent="var(--buy)"
              encoding="Green box (bull) or red box (bear) label at the break level">
              A prior swing point breached by a body close with ≥1.5× ATR displacement. Confirms trend direction. Bullish BOS = uptrend active. Bearish BOS = downtrend active. Displacement requirement filters slow drifts — only genuine institutional delivery qualifies.
            </ManConcept>
            <ManConcept name="CHoCH — CHANGE OF CHARACTER" accent="#69F0AE"
              encoding="Lighter green/red box — visually distinct from BOS">
              Protected level (last swing in the opposite direction) breached without displacement. First sign of a trend flip. CHoCH is a warning, not a signal — wait for follow-through BOS before switching bias. One CHoCH can be noise; two usually isn't.
            </ManConcept>
            <ManConcept name="ORDER BLOCK (OB)" accent="#42A5F5"
              encoding="▲ Deep blue box (bull)  ·  ▼ Deep crimson box (bear)">
              Last opposite-color candle before a displacement wave that contains an FVG. The candle where institutions placed their entries before the big move. Price returning here is price returning to the institutional footprint. Validity requires an FVG within 5 candles of the displacement.
            </ManConcept>
            <ManConcept name="OB STATUS LIFECYCLE" accent="var(--ink-3)"
              encoding="active → touched ◑ → degraded ⚠ → sapped / invalidated">
              {"Active: untouched. Touched ◑: wick entered, still valid. Degraded ⚠: body closed past 50% mean — partial defense failure, reduced conviction. Sapped: wick swept through distal boundary — hollow, skip. Invalidated: body closed through distal — destroyed, no longer on chart."}
            </ManConcept>
            <ManConcept name="FAIR VALUE GAP (FVG)" accent="#00BCD4"
              encoding="▲ Teal box (bull)  ·  ▼ Red box (bear)  ·  FVG▲/▼ tick marker at center">
              3-candle imbalance: candle 1's high and candle 3's low don't overlap (bullish), or candle 1's low and candle 3's high don't overlap (bearish). Price moved too fast for fair two-sided auction. Unmitigated FVGs act as price magnets — expect a return visit before continuation.
            </ManConcept>
            <ManConcept name="PREMIUM / DISCOUNT / OTE" accent="var(--ink-3)"
              encoding="Green background = discount  ·  Red = premium  ·  Amber lines = OTE (61–79%)  ·  Gray dashed = EQ">
              The dealing range spans from last swing high to last swing low. Midpoint = EQ (equilibrium). Smart money buys in discount, sells in premium. The OTE band (61.8–79% retracement of the dealing range) is where the best long pullback entries cluster — deep enough to be real, not so deep it breaks structure.
            </ManConcept>
            <ManConcept name="EQH / EQL — LIQUIDITY POOLS" accent="#FF1744"
              encoding="Red dashed line = EQH (sell stops above)  ·  Teal dashed line = EQL (buy stops below)">
              Two swings at nearly identical price levels. Retail traders park stop-losses just beyond these, thinking they're double-top resistance or double-bottom support. Institutions drive price through to harvest that liquidity, then reverse. EQH/EQL are trap detectors and exit targets — not entries.
            </ManConcept>
            <ManConcept name="INDUCEMENT" accent="var(--amber)"
              encoding="⌛ Amber OB border = trap set, waiting  ·  ⚡ Green border = trap fired, OB actionable">
              An EQH or EQL sitting between current price and an Order Block. The liquidity trap smart money must sweep on the way to the OB. The SMC golden rule: an OB without inducement in front of it may itself be the trap — retail orders placed there will get taken out. Wait for the sweep.
            </ManConcept>
            <ManConcept name="SESSION WEIGHTS" accent="var(--ink-3)"
              encoding="⚡ Silver Bullet badge (2×)  ·  ◈ Killzone badge (1.5×)  ·  · dot = low conviction (<1×)  ·  ★ = HTF confluence">
              {"ICT theory: institutional participation varies by session. Silver Bullet windows (03–04, 10–11, 14–15 EST) = 2× weight. London/NY Killzones (02–05, 07–10) = 1.5×. Asian range (20–00) = 0.5×. An OB formed or approached during a high-weight window has higher delivery probability."}
            </ManConcept>
          </div>
        </div>

        {/* GEO HARMONIC ARCS */}
        <div style={CARD}>
          <ManSectionHdr title="GEO HARMONIC ARCS" accent="var(--magenta)" sub="GH TAB" />
          <div style={{ padding: "14px 16px" }}>
            <div style={{ fontSize: 13, color: "var(--ink-2)", lineHeight: 1.7, marginBottom: 14 }}>
              Geometric circles drawn in log-price space, anchored to the absolute ATH and ATL (macro circles) and to ZigZag swing pivots (local circles, 3 window sizes). Where circles from different sources converge = a <strong style={{ color: "var(--ink)" }}>hot zone</strong> — a price level that independent geometric frameworks agree on.
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14, marginBottom: 14 }}>
              <div style={{ borderLeft: "3px solid #00BCD4", paddingLeft: 12 }}>
                <div className="mono" style={{ fontSize: 12, fontWeight: 700, color: "#00BCD4", letterSpacing: "0.08em", marginBottom: 4 }}>TEAL LINES — FLOOR ZONES</div>
                <div style={{ fontSize: 13, color: "var(--ink-2)", lineHeight: 1.65 }}>Demand-anchored circles originating from the absolute ATL. Geometric support levels — where price has historically found buyers in log-price geometry. Price approaching from above may react here.</div>
              </div>
              <div style={{ borderLeft: "3px solid #F44336", paddingLeft: 12 }}>
                <div className="mono" style={{ fontSize: 12, fontWeight: 700, color: "#F44336", letterSpacing: "0.08em", marginBottom: 4 }}>RED LINES — CEILING ZONES</div>
                <div style={{ fontSize: 13, color: "var(--ink-2)", lineHeight: 1.65 }}>Supply-anchored circles originating from the absolute ATH. Geometric resistance — where price has historically found sellers. Price approaching from below may stall or reverse here.</div>
              </div>
            </div>
            <div style={{ background: "var(--bg-3)", border: "1px solid var(--line)", padding: "10px 14px", marginBottom: 12 }}>
              <div className="mono" style={{ fontSize: 12, color: "var(--ink-3)", letterSpacing: "0.1em", marginBottom: 8 }}>HOW TO USE GH IN A WORKFLOW</div>
              <div style={{ fontSize: 13, color: "var(--ink-2)", lineHeight: 1.75 }}>
                <strong style={{ color: "var(--ink-3)" }}>1.</strong> Check the GH tab hot zones table — note any floor/ceiling levels within 3–5% of current price.<br/>
                <strong style={{ color: "var(--ink-3)" }}>2.</strong> Switch to the SMC tab. If a hot zone aligns with an OB or FVG, that's geometric confluence — conviction goes up.<br/>
                <strong style={{ color: "var(--ink-3)" }}>3.</strong> Use the Pine Script button (GH tab, bottom panel, collapsed by default) to export arcs to TradingView. Paste directly into the TV Pine editor to see the circles on your live chart.
              </div>
            </div>
            <div className="mono" style={{ fontSize: 12, color: "var(--ink-4)", letterSpacing: "0.06em", lineHeight: 1.7 }}>
              6 Fibonacci levels per circle: 23.6% · 38.2% · 50% · 61.8% · 78.6% · 100%  ·  Hot zones = DBSCAN clusters where 2+ distinct source circles agree on a price level. The more source types agreeing (macro-macro &gt; macro-local &gt; local-local), the stronger the level.
            </div>
          </div>
        </div>

        {/* XABCD PATTERNS */}
        <div style={{ ...CARD, marginBottom: 20 }}>
          <ManSectionHdr title="XABCD HARMONIC PATTERNS" accent="var(--amber)" sub="GH TAB · XABCD SECTION" />
          <div style={{ padding: "14px 16px" }}>
            <div style={{ fontSize: 13, color: "var(--ink-2)", lineHeight: 1.7, marginBottom: 14 }}>
              Harmonic patterns identify high-probability turning points using Fibonacci ratios between 5 price pivots: X → A → B → C → D. The <strong style={{ color: "var(--ink)" }}>D point</strong> is the potential entry — the <strong style={{ color: "var(--ink)" }}>Potential Reversal Zone (PRZ)</strong>. All leg ratios must fall within tolerance for a valid pattern.
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 8, marginBottom: 14 }}>
              {XABCD_PATTERNS.map(([name, b, c, d]) => (
                <div key={name} style={{ background: "var(--bg-3)", border: "1px solid var(--line)", padding: "8px 10px" }}>
                  <div className="mono" style={{ fontSize: 12, fontWeight: 700, color: "var(--amber)", letterSpacing: "0.06em", marginBottom: 5 }}>{name}</div>
                  <div className="mono" style={{ fontSize: 12, color: "var(--ink-4)", lineHeight: 1.7 }}>
                    B: {b}<br/>C: {c}<br/>D: {d}
                  </div>
                </div>
              ))}
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
              <div style={{ borderLeft: "3px solid var(--ink-3)", paddingLeft: 12 }}>
                <div className="mono" style={{ fontSize: 12, color: "var(--ink-3)", letterSpacing: "0.08em", marginBottom: 5 }}>CHART SYMBOLS</div>
                <div style={{ fontSize: 13, color: "var(--ink-2)", lineHeight: 1.65 }}>
                  Solid lines = confirmed pattern (D leg complete). Dashed lines = forming (D not yet reached). Shaded band at D = the PRZ range where reversal is expected. X A B C D labels drawn on chart at each pivot.
                </div>
              </div>
              <div style={{ borderLeft: "3px solid var(--amber)", paddingLeft: 12 }}>
                <div className="mono" style={{ fontSize: 12, color: "var(--amber)", letterSpacing: "0.08em", marginBottom: 5 }}>CONFLUENCE RULE</div>
                <div style={{ fontSize: 13, color: "var(--ink-2)", lineHeight: 1.65 }}>
                  Standalone XABCD is lower conviction. Highest probability when the D PRZ overlaps an SMC OB, HTF reference level, or GH hot zone. Use XABCD to narrow the entry window within a zone — not as a replacement for structure analysis.
                </div>
              </div>
            </div>
          </div>
        </div>

      </div>
    </div>
  );
}

/* ── Watchlist custom presets helpers ─────────────────────── */
/* read-once migration source — never written back to localStorage */
function _migratePresetsFromLocalStorage() {
  try {
    const raw = localStorage.getItem('banshee_custom_presets');
    return raw ? JSON.parse(raw) : [];
  } catch { return []; }
}

/* ── App ───────────────────────────────────────────────────── */
function App() {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [watchlist, setWatchlist]     = useState("all");
  const [customPresets, setCustomPresets] = React.useState([]);
  const [presetsOpen, setPresetsOpen]     = React.useState(false);
  const [focusedSym, setFocusedSym]   = useState(null);
  const [openSym, setOpenSym]         = useState(null);
  const [page, setPage]               = useState("grid");   // "grid" | "hub" | "analysis" | "macro" | "settings" | "lab" | "risk" | "journal" | "manual"
  const [analysisTab, setAnalysisTab] = useState("smc");
  const [radarData, setRadarData]     = useState({});
  const [snapshot, setSnapshot] = useState(() => {
    try { return JSON.parse(localStorage.getItem('banshee_snapshot') || '{}'); }
    catch { return {}; }
  });
  const [radarLoading, setRadarLoading] = useState(() => new Set(window.ASSETS.map(a => a.sym)));
  const [macroData, setMacroData]     = useState(null);
  const [customAsset, setCustomAsset] = useState(null);
  const [riskSeedAsset, setRiskSeedAsset] = useState(null);
  const [simulateMode,  setSimulateMode]  = useState(false);
  const [manualStories, setManualStories] = useState([]);
  const [disclaimerAccepted, setDisclaimerAccepted] = React.useState(
    () => localStorage.getItem('banshee_disclaimer_accepted') === 'true'
  );
  const [pinLocked, setPinLocked] = React.useState(() =>
    localStorage.getItem('banshee_pin_enabled') === 'true' &&
    !!localStorage.getItem('banshee_pin')
  );
  const [portfolioSetupOpen, setPortfolioSetupOpen] = React.useState(false);
  const [activePortfolio, setActivePortfolio] = React.useState(null);
  const [currentPortfolioId, setCurrentPortfolioId] = React.useState(null);
  const [pfNonce, setPfNonce] = React.useState(0);   // bumped on save → forces PortfolioPage re-fetch

  const watchlists = React.useMemo(
    () => [...customPresets, ...window.WATCHLISTS],
    [customPresets]
  );

  const isCustomPreset = customPresets.some(p => p.id === watchlist);

  /* load presets from Core on mount; migrate from localStorage if Core returns empty */
  React.useEffect(() => {
    (async () => {
      const serverPresets = await window.API.fetchPresets();
      if (serverPresets === null) return; // Core unavailable — keep state as-is
      if (serverPresets.length > 0) {
        setCustomPresets(serverPresets);
      } else {
        const migrated = _migratePresetsFromLocalStorage();
        if (migrated.length > 0) {
          setCustomPresets(migrated);
          await window.API.savePresets(migrated); // persist to disk
          localStorage.removeItem('banshee_custom_presets');
        }
      }
    })();
  }, []);

  function saveCustomPresets(presets) {
    setCustomPresets(presets);
    window.API.savePresets(presets);
  }

  React.useEffect(() => {
    const allIds = new Set([
      ...customPresets.map(p => p.id),
      ...window.WATCHLISTS.map(w => w.id),
    ]);
    if (!allIds.has(watchlist)) setWatchlist('all');
  }, [customPresets, watchlist]);

  /* keyboard nav */
  useEffect(() => {
    function handleKey(e) {
      if (e.key === "Escape") {
        if (page === "analysis") { setPage("hub"); return; }
        if (page === "hub")      { setOpenSym(null); setCustomAsset(null); setPage("grid"); return; }
        if (page === "risk") { setSimulateMode(false); setPage(simulateMode ? "hub" : "grid"); return; }
        if (["macro", "settings", "lab", "journal", "manual", "news", "portfolio", "options"].includes(page)) { setPage("grid"); return; }
      }
      if ((e.key === "ArrowUp" || e.key === "ArrowDown") && page === "hub" && openSym) {
        e.preventDefault();
        const wl = watchlists.find(w => w.id === watchlist);
        if (!wl) return;
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
  }, [page, openSym, watchlist, watchlists]);

  // Entering any non-grid space (a full page OR an asset view) withdraws the
  // sidebar so the new view gets the full screen; returning to the grid restores
  // it. Only fires on a page CHANGE, so manual toggling within a space is respected.
  useEffect(() => { setSidebarOpen(page === "grid"); }, [page]);

  /* symbol search via sidebar */
  async function handleSymbolSearch(sym) {
    /* resolve names/pairs to a known ticker first: "BITCOIN"/"BTC/USD"/"APPLE"
     * all open the matching default asset directly. */
    const known = resolveKnownAsset(sym);
    if (known) {
      setFocusedSym(known.sym); setOpenSym(known.sym); setPage("hub"); setCustomAsset(null);
      return;
    }
    /* unknown ticker — fetch radar as typed (keeps the user's "/USD" suffix,
     * which forces crypto resolution on the backend, e.g. HYPE/USD ≠ HYPE stock). */
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
        if (res && !res.error) {
          setRadarData(prev => ({ ...prev, [a.sym]: res }));
          setSnapshot(prev => {
            const entry = {
              price:   typeof res.price   === "number" ? res.price   : prev[a.sym]?.price,
              chg:     typeof res.chg_pct === "number" ? res.chg_pct : prev[a.sym]?.chg,
              edge:    typeof res.edge    === "number" ? Math.round(normaliseEdge(res.edge)) : prev[a.sym]?.edge,
              verdict: res.verdict ?? prev[a.sym]?.verdict,
              bias:    res.bias    ?? prev[a.sym]?.bias,
              rsi:     typeof res.rsi === "number" ? Math.round(res.rsi) : prev[a.sym]?.rsi,
              name:    a.name,
              cls:     a.cls,
            };
            const next = { ...prev, [a.sym]: entry };
            try { localStorage.setItem('banshee_snapshot', JSON.stringify(next)); } catch {}
            return next;
          });
        }
        setRadarLoading(prev => { const s = new Set(prev); s.delete(a.sym); return s; });
      });
    });
  }, []);

  /* fetch radar for custom watchlist symbols not covered by the default ASSETS
   * loop above (e.g. "TAO/USD", "PAXG/USD"). Keyed by canonical symbol; known
   * assets are skipped because the mount effect already fetched them. Runs when
   * the active watchlist or preset list changes. */
  useEffect(() => {
    const wl = watchlists.find(w => w.id === watchlist);
    if (!wl) return;
    const knownSyms = new Set(window.ASSETS.map(a => a.sym));
    const pending = [...new Set(wl.syms.map(canonSym))]
      .filter(key => !knownSyms.has(key) && !radarData[key] && !RADAR_SKIP.has(key));
    if (!pending.length) return;
    setRadarLoading(prev => { const s = new Set(prev); pending.forEach(k => s.add(k)); return s; });
    pending.forEach(key => {
      window.API.fetchRadar(key, "swing").then(res => {
        if (res && !res.error) {
          setRadarData(prev => ({ ...prev, [key]: res }));
          setSnapshot(prev => {
            const isCrypto = /[\/\-]USDT?$/i.test(key);
            const entry = {
              price:   typeof res.price   === "number" ? res.price   : prev[key]?.price,
              chg:     typeof res.chg_pct === "number" ? res.chg_pct : prev[key]?.chg,
              edge:    typeof res.edge    === "number" ? Math.round(normaliseEdge(res.edge)) : prev[key]?.edge,
              verdict: res.verdict ?? prev[key]?.verdict,
              bias:    res.bias    ?? prev[key]?.bias,
              rsi:     typeof res.rsi === "number" ? Math.round(res.rsi) : prev[key]?.rsi,
              name:    prev[key]?.name || key.replace(/[\/\-]USDT?$/i, ""),
              cls:     prev[key]?.cls  || (isCrypto ? "CRYPTO" : "EQUITY"),
            };
            const next = { ...prev, [key]: entry };
            try { localStorage.setItem('banshee_snapshot', JSON.stringify(next)); } catch {}
            return next;
          });
        }
        setRadarLoading(prev => { const s = new Set(prev); s.delete(key); return s; });
      });
    });
  }, [watchlist, watchlists]);

  const handlePortfolioClick = async () => {
    const data = await window.API.fetchPortfolios();
    const existing = (data.portfolios || []).find(p => p.preset_id === watchlist);
    if (existing) {
      setActivePortfolio(existing);
      setCurrentPortfolioId(existing.id);
      setPage('portfolio');
    } else {
      setActivePortfolio(null);
      setPortfolioSetupOpen(true);
    }
  };

  function openAsset(sym) {
    setFocusedSym(sym); setOpenSym(sym); setPage("hub");
  }
  function goDeepDive(tab) {
    setAnalysisTab(tab); setPage("analysis");
  }
  function goBack() {
    if (page === "analysis") setPage("hub");
    else if (page === "hub") { setOpenSym(null); setCustomAsset(null); setPage("grid"); }
    else if (page === "risk") { setSimulateMode(false); setPage(simulateMode ? "hub" : "grid"); }
    else if (["macro", "settings", "lab", "journal", "manual", "news", "portfolio", "options"].includes(page)) setPage("grid");
  }

  const liveAsset = openSym
    ? (customAsset?.sym === openSym
        ? customAsset
        : mergeRadar(resolveBaseAsset(openSym, snapshot), radarData[openSym]))
    : null;

  function handleGoRisk(simulate = false) {
    const seed = liveAsset
      ? { ...liveAsset, atr_plan: radarData[openSym]?.atr_plan ?? null }
      : null;
    setRiskSeedAsset(seed);
    setSimulateMode(simulate);
    setPage("risk");
  }

  const topBarMacro = sensorsToTopBar(macroData);

  return (
    <div style={{ height: "100vh", display: "flex", flexDirection: "column", overflow: "hidden" }}>
      {!disclaimerAccepted
        ? <window.DisclaimerModal onAccept={() => {
            localStorage.setItem('banshee_disclaimer_accepted', 'true');
            setDisclaimerAccepted(true);
          }} />
        : pinLocked && <window.PinLockScreen onUnlock={() => setPinLocked(false)} />
      }
      <TopBar
        onToggleSidebar={() => setSidebarOpen(o => !o)}
        sidebarOpen={sidebarOpen}
        macro={topBarMacro}
        onMacro={() => setPage("macro")}
      />
      <div style={{ flex: 1, minHeight: 0, display: "flex", position: "relative" }}>
        <Sidebar
          open={sidebarOpen}
          watchlists={watchlists}
          watchlist={watchlist} setWatchlist={setWatchlist}
          focusedSym={focusedSym}
          radarData={radarData}
          setFocusedSym={openAsset}
          onSearch={handleSymbolSearch}
          onSettings={() => setPage("settings")}
          onMacro={() => setPage("macro")}
          onNews={() => setPage("news")}
          onLab={() => setPage("lab")}
          onRisk={() => handleGoRisk(false)}
          onJournal={() => setPage("journal")}
          onManual={() => setPage("manual")}
          onOptions={() => setPage("options")}
          currentPage={page}
          onPresetsOpen={() => setPresetsOpen(true)}
        />
        <AssetGrid
          watchlists={watchlists}
          watchlist={watchlist}
          focusedSym={focusedSym}
          onOpen={openAsset}
          radarData={radarData}
          radarLoading={radarLoading}
          snapshot={snapshot}
          isCustomPreset={isCustomPreset}
          onPortfolioClick={handlePortfolioClick}
        />
        {page === "hub" && liveAsset && (
          <AssetHub
            asset={liveAsset}
            macroWarning={topBarMacro.warning}
            onBack={goBack}
            onDeepDive={goDeepDive}
            onGoRiskSimulate={() => handleGoRisk(true)}
          />
        )}
        {page === "analysis" && liveAsset && (
          <AnalysisPage
            asset={liveAsset}
            macroWarning={topBarMacro.warning}
            initialTab={analysisTab}
            onBack={goBack}
            manualStories={manualStories}
          />
        )}
        {page === "macro" && (
          <MacroPage macroData={macroData} onBack={goBack} manualStories={manualStories} />
        )}
        {page === "settings" && (
          <SettingsPage onBack={goBack} />
        )}
        {page === "lab" && (
          <LabPage onBack={goBack} />
        )}
        {page === "risk" && (
          <RiskDeskPage seedAsset={riskSeedAsset} simulateMode={simulateMode} onBack={goBack} />
        )}
        {page === "journal" && (
          <JournalPage radarData={radarData} onBack={goBack} />
        )}
        {page === "manual" && (
          <ManualPage onBack={goBack} />
        )}
        {page === "news" && (
          <NewsPage onBack={goBack} manualStories={manualStories} setManualStories={setManualStories} />
        )}
        {page === "portfolio" && (
          <window.PortfolioPage
            key={`${currentPortfolioId}:${pfNonce}`}
            portfolioId={currentPortfolioId}
            portfolio={activePortfolio}
            onBack={() => setPage('grid')}
            onEditHoldings={() => setPortfolioSetupOpen(true)}
          />
        )}
        {page === "options" && (
          <window.OptionsPage onBack={() => setPage("grid")} />
        )}
        {presetsOpen && (
          <window.PresetsModal
            customPresets={customPresets}
            saveCustomPresets={saveCustomPresets}
            watchlist={watchlist}
            setWatchlist={setWatchlist}
            onClose={() => setPresetsOpen(false)}
          />
        )}
        {portfolioSetupOpen && (
          <window.PortfolioSetupModal
            preset={customPresets.find(p => p.id === watchlist)}
            existingPortfolio={activePortfolio}
            onSave={(portfolio) => {
              if (!portfolio || portfolio.error || !portfolio.id) return;
              setActivePortfolio(portfolio);
              setCurrentPortfolioId(portfolio.id);
              setPfNonce(n => n + 1);          // force a fresh analysis fetch even if id is unchanged
              setPortfolioSetupOpen(false);
              setPage('portfolio');
            }}
            onClose={() => setPortfolioSetupOpen(false)}
          />
        )}
      </div>
    </div>
  );
}

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(<App />);
