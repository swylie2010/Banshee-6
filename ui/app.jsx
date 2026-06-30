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
import NewsPage from './pages/NewsPage.jsx';
import ManualPage from './pages/ManualPage.jsx';
import ObservatoryPage from './pages/ObservatoryPage.jsx';

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
function TopBar({ onToggleSidebar, sidebarOpen, macro, onMacro, unleashed, onToggleUnleashed }) {
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

      {/* Unleashed toggle — near MACRO button */}
      <window.UnleashedToggle enabled={unleashed} onToggle={onToggleUnleashed} />

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
function Sidebar({ open, watchlists, watchlist, setWatchlist, focusedSym, setFocusedSym, radarData, onSearch, onSettings, onMacro, onNews, onLab, onRisk, onJournal, onManual, onOptions, onGridbot, onObservatory, currentPage, onPresetsOpen }) {
  const [searchVal, setSearchVal] = useState("");
  const [shutdownState, setShutdownState] = useState("idle"); // idle | gridbot_warn | confirm | done
  const [gridbotSym, setGridbotSym] = React.useState(null);
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
            { id: "gridbot",  label: "GRIDBOT",        icon: "⊞" },
            { id: "observatory", label: "OBSERVATORY", icon: "◈" },
            { id: "lab",      label: "SIGNAL LAB",     icon: "◬" },
            { id: "settings", label: "SETTINGS",       icon: "⚙" },
            { id: "manual",   label: "MANUAL",         icon: "◌" },
          ].map(({ id, label, icon }) => {
            const active = currentPage === id;
            const HANDLERS = { macro: onMacro, news: onNews, lab: onLab, risk: onRisk, journal: onJournal, settings: onSettings, manual: onManual, options: onOptions, gridbot: onGridbot, observatory: onObservatory };
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
              onClick={async () => {
                try {
                  const gb = await window.API.getPaperGridbot();
                  if (gb && gb.state && gb.state.status === "active") {
                    setGridbotSym(gb.grid.sym);
                    setShutdownState("gridbot_warn");
                  } else {
                    setShutdownState("confirm");
                  }
                } catch (_) {
                  setShutdownState("confirm");
                }
              }}
              style={{ background: "transparent", border: "1px solid var(--sell)", color: "var(--sell)", cursor: "pointer", padding: "5px 10px", fontFamily: "var(--mono)", fontSize: 11, letterSpacing: "0.14em", width: "100%" }}
            >⏻ STOP BANSHEE</button>
          )}
          {shutdownState === "gridbot_warn" && (
            <div>
              <div style={{
                background: "rgba(245,158,11,0.08)", border: "1px solid rgba(245,158,11,0.3)",
                borderRadius: 4, padding: "8px 10px", marginBottom: 8,
                fontSize: 11, color: "var(--amber)", lineHeight: 1.55,
              }}>
                ⚠ Active grid on {gridbotSym} — fills stop when Core shuts down. The grid resumes polling on restart.
              </div>
              <div style={{ display: "flex", gap: 6 }}>
                <button
                  onClick={async () => { await window.API.shutdownBanshee(); setShutdownState("done"); }}
                  style={{ flex: 1, background: "var(--sell)", border: "none", color: "#fff", cursor: "pointer", padding: "6px 0", fontFamily: "var(--mono)", fontSize: 11, fontWeight: 700, letterSpacing: "0.14em" }}
                >SHUT DOWN</button>
                <button
                  onClick={() => setShutdownState("idle")}
                  style={{ flex: 1, background: "transparent", border: "1px solid var(--line-2)", color: "var(--ink-3)", cursor: "pointer", padding: "6px 0", fontFamily: "var(--mono)", fontSize: 11, letterSpacing: "0.1em" }}
                >CANCEL</button>
              </div>
            </div>
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
window.canonSym = canonSym;
window.resolveBaseAsset = resolveBaseAsset;
window.mergeRadar = mergeRadar;

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

  /* ── Unleashed mode state ─────────────────────────────────── */
  const [unleashed, setUnleashedState] = React.useState(false);
  React.useEffect(() => {
    window.API.fetchUnleashed().then(s => setUnleashedState(!!s.enabled));
  }, []);

  const toggleUnleashed = async (next) => {
    const res = await window.API.setUnleashed(next);
    const on = !!res.enabled;
    setUnleashedState(on);
    if (on) {
      /* Play the entry tone once when toggling ON.
       * Steve: swap ui/unleashed-entry.wav for your real sound — it's a one-file replace. */
      try {
        new Audio("/ui/unleashed-entry.wav").play().catch(() => {});
      } catch (_) {}
    }
  };

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
        if (["macro", "settings", "lab", "journal", "manual", "news", "portfolio", "options", "gridbot", "observatory"].includes(page)) { setPage("grid"); return; }
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
    else if (["macro", "settings", "lab", "journal", "manual", "news", "portfolio", "options", "gridbot", "observatory"].includes(page)) setPage("grid");
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
    <div className={unleashed ? "unleashed" : ""}
         style={{ height: "100vh", display: "flex", flexDirection: "column", overflow: "hidden" }}>
      {!disclaimerAccepted
        ? <window.DisclaimerModal onAccept={() => {
            localStorage.setItem('banshee_disclaimer_accepted', 'true');
            setDisclaimerAccepted(true);
          }} />
        : pinLocked && <window.PinLockScreen onUnlock={() => setPinLocked(false)} />
      }
      <window.UnleashedBanner show={unleashed} />
      <TopBar
        onToggleSidebar={() => setSidebarOpen(o => !o)}
        sidebarOpen={sidebarOpen}
        macro={topBarMacro}
        onMacro={() => setPage("macro")}
        unleashed={unleashed}
        onToggleUnleashed={toggleUnleashed}
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
          onGridbot={() => setPage("gridbot")}
          onObservatory={() => setPage("observatory")}
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
        {page === "gridbot" && (
          <window.GridbotPage onBack={() => setPage("grid")} />
        )}
        {page === "observatory" && (
          <ObservatoryPage onBack={() => setPage("grid")} />
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
