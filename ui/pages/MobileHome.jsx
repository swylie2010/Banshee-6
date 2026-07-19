/* ui/pages/MobileHome.jsx
 * Phone landing: one scrollable column you thumb down. Desktop is unaffected —
 * this only renders below the mobile breakpoint (App decides). Top: symbol
 * search, macro regime strip, gridbot hero. Bottom: watchlist rows, news
 * headlines, and a more-tools row. */

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

/* Single watchlist row — symbol left (bold, ellipsis-truncated so a long/odd
 * ticker never overflows the column), verdict + RSI/edge right in the verdict
 * color. Whole row is tappable → opens that symbol's full-screen detail. */
function MHWatchlistRow({ asset, onOpenSymbol }) {
  const c = window.verdictColors(asset?.verdict);
  const metric = typeof asset?.rsi === "number" ? `RSI ${asset.rsi}`
    : typeof asset?.edge === "number" ? `E${asset.edge}` : "—";
  return (
    <div
      onClick={() => onOpenSymbol(asset.sym)}
      role="button" tabIndex={0}
      style={{
        display: "flex", justifyContent: "space-between", alignItems: "center",
        minHeight: 44, padding: "0 10px", cursor: "pointer",
        background: "var(--bg-2)", border: "1px solid var(--line)", borderRadius: 8,
        marginBottom: 4,
      }}
    >
      <span className="mono" style={{
        fontSize: 14, fontWeight: 700, color: "var(--ink)", minWidth: 0, marginRight: 10,
        overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
      }}>{asset?.sym || "—"}</span>
      <span className="mono" style={{
        fontSize: 12, flexShrink: 0, display: "flex", gap: 8, alignItems: "center",
      }}>
        <span style={{ color: c.fg, fontWeight: 700 }}>{asset?.verdict || "—"}</span>
        <span style={{ color: "var(--ink-3)" }}>{metric}</span>
      </span>
    </div>
  );
}

/* Watchlist rows — mirrors how Sidebar derives its symbol list from the
 * active watchlist (app.jsx:252-259), since MobileHome only receives the
 * `watchlist` id, not the array of lists (that's why `watchlists` was added
 * to the mobile app.jsx call site). Guarded end to end: an unknown/renamed
 * watchlist id or a missing radar entry must never throw. */
function MHWatchlist({ watchlists, watchlist, radarData, onOpenSymbol }) {
  const wl = (watchlists || []).find(w => w.id === watchlist);
  const symAssets = (wl?.syms || []).map(s => {
    const key = window.canonSym(s);
    const base = window.resolveBaseAsset(key);
    return { ...window.mergeRadar(base, radarData?.[key]), sym: key };
  }).filter(Boolean);

  return (
    <MHSection label="WATCHLIST">
      {symAssets.length === 0 ? (
        <div className="mono" style={{ fontSize: 12, color: "var(--ink-3)", padding: "8px 2px" }}>
          — no symbols —
        </div>
      ) : (
        symAssets.map(a => <MHWatchlistRow key={a.sym} asset={a} onOpenSymbol={onOpenSymbol} />)
      )}
    </MHSection>
  );
}

/* News — same Predator Briefing NewsPage reads (ui/pages/NewsPage.jsx:120),
 * flattened to the first few headlines. Fetches on mount with a
 * cancelled-flag cleanup; a fetch failure degrades to null → no items → the
 * whole section is omitted (never an empty box). */
function MHNews() {
  const [news, setNews] = React.useState(null);

  React.useEffect(() => {
    let cancelled = false;
    window.API.fetchPredatorBriefing()
      .then(b => { if (!cancelled) setNews(b); })
      .catch(() => { if (!cancelled) setNews(null); });
    return () => { cancelled = true; };
  }, []);

  const items = [...(news?.watchlist_events || []), ...(news?.discovered_signals || [])];
  if (items.length === 0) return null;

  return (
    <MHSection label="NEWS">
      {items.slice(0, 3).map((it, i) => {
        const headline = it?.headline || "—";
        const body = (
          <div className="mono" style={{ fontSize: 13, fontWeight: 600, color: "var(--ink)", lineHeight: 1.4 }}>
            {headline}
          </div>
        );
        return (
          <div key={i} style={{
            padding: "8px 2px", borderBottom: i < items.slice(0, 3).length - 1 ? "1px solid var(--line)" : "none",
          }}>
            {it?.url
              ? <a href={it.url} target="_blank" rel="noreferrer" style={{ textDecoration: "none" }}>{body}</a>
              : body}
            {it?.source && (
              <div className="mono" style={{ fontSize: 12, color: "var(--ink-4)", marginTop: 3 }}>{it.source}</div>
            )}
          </div>
        );
      })}
    </MHSection>
  );
}

/* More tools — the phone-safe subset of the desktop sidebar's NAVIGATE list
 * (app.jsx:428-438), using the same page ids so onNav (App's setPage) routes
 * identically. */
function MHMore({ onNav }) {
  const TOOLS = [
    { id: "options",     label: "OPTIONS",        icon: "◆" },
    { id: "news",        label: "PREDATOR NEWS",  icon: "◉" },
    { id: "observatory", label: "OBSERVATORY",    icon: "✧" },
    { id: "risk",        label: "RISK DESK",      icon: "⚖" },
    { id: "journal",     label: "TRADE JOURNAL",  icon: "◎" },
  ];
  return (
    <MHSection label="MORE">
      {TOOLS.map(t => (
        <div
          key={t.id}
          onClick={() => onNav(t.id)}
          role="button" tabIndex={0}
          style={{
            display: "flex", alignItems: "center", gap: 10,
            minHeight: 44, padding: "0 10px", cursor: "pointer",
            background: "var(--bg-2)", border: "1px solid var(--line)", borderRadius: 8,
            marginBottom: 4,
          }}
        >
          <span className="mono" style={{ fontSize: 14, color: "var(--ink-3)" }}>{t.icon}</span>
          <span className="mono" style={{ fontSize: 13, color: "var(--ink)", letterSpacing: "0.08em", fontWeight: 600 }}>
            {t.label}
          </span>
        </div>
      ))}
    </MHSection>
  );
}

function MobileHome({ macroData, radarData, snapshot, watchlist, watchlists, onOpenSymbol, onSearch, onNav }) {
  return (
    <div style={{
      height: "100%", overflowY: "auto", WebkitOverflowScrolling: "touch",
      background: "var(--bg-0)", padding: "10px 12px 40px",
    }}>
      <MHSearch onSearch={onSearch} />
      <MHMacroStrip macroData={macroData} onNav={onNav} />
      <MHGridbotHero onNav={onNav} />
      <MHWatchlist watchlists={watchlists} watchlist={watchlist} radarData={radarData} onOpenSymbol={onOpenSymbol} />
      <MHNews />
      <MHMore onNav={onNav} />
    </div>
  );
}

export default MobileHome;
