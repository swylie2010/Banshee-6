/* Banshee — main app */
const { useState, useEffect, useMemo, useRef } = React;
import AssetGrid from './pages/AssetGrid.jsx';
import AssetHub from './pages/AssetHub.jsx';
import AnalysisPage from './pages/AnalysisPage.jsx';
import SettingsPage from './pages/SettingsPage.jsx';
import MacroPage from './pages/MacroPage.jsx';
import LabPage from './pages/LabPage.jsx';
import RiskDeskPage from './pages/RiskDeskPage.jsx';
import JournalPage from './pages/JournalPage.jsx';

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
window.sensorsToTopBar = sensorsToTopBar;

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
