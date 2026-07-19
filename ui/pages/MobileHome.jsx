/* ui/pages/MobileHome.jsx
 * Phone landing: one scrollable column you thumb down. Desktop is unaffected —
 * this only renders below the mobile breakpoint (App decides). This task fills
 * the top: symbol search, macro regime strip, gridbot hero. Watchlist/news/more
 * come in a later task (YAGNI — do not add them here). */

/* Section label wrapper — every home section gets one for consistent rhythm. */
function MHSection({ label, children }) {
  return (
    <div style={{ marginBottom: 12 }}>
      {label && <div className="mono" style={{ fontSize: 12, letterSpacing: ".14em",
        color: "var(--ink-4)", margin: "4px 2px 6px" }}>{label}</div>}
      {children}
    </div>
  );
}

/* Local $ formatter — gbFmtDollar lives in gridbot.jsx and isn't exported/global. */
function fmtUsd(n) {
  const v = Number(n) || 0;
  return (v >= 0 ? "+$" : "−$") + Math.abs(v).toFixed(2);
}

/* Symbol search — mirrors desktop sidebar behavior (app.jsx:274-303): onSearch
 * returns "" on success or an error message on failure; keep the typed text on
 * failure so the user can fix a typo, clear it on success. */
function MHSearch({ onSearch }) {
  const [val, setVal] = React.useState("");
  const [error, setError] = React.useState("");

  const submit = async e => {
    e.preventDefault();
    const sym = val.trim().toUpperCase();
    if (!sym) return;
    setError("");
    const err = await onSearch(sym);
    if (err) setError(err);
    else { setError(""); setVal(""); }
  };

  return (
    <MHSection>
      <form onSubmit={submit} style={{ display: "flex", gap: 8 }}>
        <input
          value={val}
          onChange={e => { setVal(e.target.value); if (error) setError(""); }}
          placeholder="TICKER…"
          maxLength={12}
          style={{
            flex: 1,
            minWidth: 0,
            minHeight: 44,
            background: "var(--bg-2)", border: "1px solid var(--line-2)",
            color: "var(--ink)", padding: "0 12px",
            fontFamily: "'JetBrains Mono', monospace", fontSize: 16,
            letterSpacing: "0.06em", outline: "none", borderRadius: 6,
          }}
        />
        <button type="submit" style={{
          minHeight: 44, minWidth: 60,
          background: "var(--cyan)", color: "var(--bg-0)",
          border: "none", cursor: "pointer", borderRadius: 6,
          fontFamily: "'JetBrains Mono', monospace",
          fontSize: 14, fontWeight: 700, letterSpacing: "0.14em",
        }}>GO</button>
      </form>
      {error && (
        <div className="mono" style={{
          marginTop: 6, color: "var(--amber)", fontSize: 12, lineHeight: 1.4,
        }}>{error}</div>
      )}
    </MHSection>
  );
}

/* Macro regime strip — reads the same shape TopBar/MacroPage consume via
 * window.sensorsToTopBar, which already falls back to "—" internally. */
function MHMacroStrip({ macroData, onNav }) {
  const tb = window.sensorsToTopBar ? window.sensorsToTopBar(macroData) : null;
  const regime = tb?.regime ?? "—";
  const regimeColor = tb?.regimeColor ?? "var(--ink-3)";
  const vix = tb?.flags?.find(f => f.k === "VIX")?.v ?? "—";

  return (
    <MHSection>
      <div
        onClick={() => onNav("macro")}
        role="button" tabIndex={0}
        style={{
          minHeight: 44, cursor: "pointer",
          background: "var(--bg-2)", border: "1px solid var(--line)", borderRadius: 9,
          padding: "8px 12px",
        }}
      >
        <div className="mono" style={{ fontSize: 12, letterSpacing: ".14em", color: "var(--ink-4)" }}>
          MACRO · REGIME
        </div>
        <div className="num" style={{ fontSize: 14, fontWeight: 700, color: regimeColor, marginTop: 2 }}>
          {regime} <span style={{ color: "var(--ink-3)", fontWeight: 400, fontSize: 12 }}>· VIX {vix}</span>
        </div>
      </div>
    </MHSection>
  );
}

/* Gridbot hero — the emotional center of the phone home. Fetches live paper
 * gridbot state on mount. null (no active grid, incl. 404) → "Gridbot idle",
 * never a blank card. Every field is optional-chained: a partial payload from
 * a flaky mobile connection must never throw or blank the card. */
function MHGridbotHero({ onNav }) {
  const [gb, setGb] = React.useState(undefined); // undefined = loading, null = idle/error

  React.useEffect(() => {
    let cancelled = false;
    window.API.getPaperGridbot()
      .then(d => { if (!cancelled) setGb(d); })
      .catch(() => { if (!cancelled) setGb(null); });
    return () => { cancelled = true; };
  }, []);

  const grid = gb?.grid;
  const state = gb?.state;
  const idle = gb === null || gb === undefined || !grid || !state;

  const pnl = state?.realized_pnl;
  const pnlColor = (Number(pnl) || 0) >= 0 ? "var(--buy)" : "var(--sell)";
  const holding = (state?.slots || []).filter(s => s?.status === "holding").length;
  const cycles = state?.cycle_count ?? 0;

  return (
    <MHSection>
      <div
        onClick={() => onNav("gridbot")}
        role="button" tabIndex={0}
        style={{
          minHeight: 72, cursor: "pointer",
          background: "linear-gradient(180deg, var(--bg-2), var(--bg-1))",
          border: "1px solid var(--buy)", borderRadius: 11,
          padding: "12px 14px",
        }}
      >
        <div className="mono" style={{ fontSize: 12, letterSpacing: ".16em", color: "var(--buy)", marginBottom: 2 }}>
          ◆ GRIDBOT{grid?.sym ? ` · ${grid.sym}` : ""}
        </div>
        {idle ? (
          <div style={{ fontSize: 14, color: "var(--ink-3)", marginTop: 4 }}>Gridbot idle</div>
        ) : (
          <>
            <div className="num" style={{ fontSize: 22, fontWeight: 800, color: "var(--ink)", lineHeight: 1.1 }}>
              <span style={{ color: pnlColor }}>{fmtUsd(pnl)}</span>{" "}
              <span style={{ fontSize: 12, color: "var(--buy)", fontWeight: 600, letterSpacing: ".04em" }}>
                REALIZED P&amp;L
              </span>
            </div>
            <div style={{ fontSize: 12, color: "var(--ink-3)", marginTop: 3 }}>
              {cycles} cycles · {holding} holding
            </div>
          </>
        )}
      </div>
    </MHSection>
  );
}

function MobileHome({ macroData, radarData, snapshot, watchlist, onOpenSymbol, onSearch, onNav }) {
  return (
    <div style={{
      height: "100%", overflowY: "auto", WebkitOverflowScrolling: "touch",
      background: "var(--bg-0)", padding: "10px 12px 40px",
    }}>
      <MHSearch onSearch={onSearch} />
      <MHMacroStrip macroData={macroData} onNav={onNav} />
      <MHGridbotHero onNav={onNav} />
      <div className="mono" style={{ fontSize: 12, color: "var(--ink-3)" }}>
        More sections coming (watchlist, news)
      </div>
    </div>
  );
}

export default MobileHome;
