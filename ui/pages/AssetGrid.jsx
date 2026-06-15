/* AssetGrid — watchlist grid + ticker tape */

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

/* ── Asset grid ───────────────────────────────────────────── */
function AssetGrid({ watchlists, watchlist, focusedSym, onOpen, radarData, radarLoading, snapshot = {}, isCustomPreset = false, onPortfolioClick }) {
  const wl = watchlists.find(w => w.id === watchlist);
  const syms = wl.syms;
  const assets = syms
    .map(s => {
      const key    = window.canonSym(s);           // "BTC/USD" → "BTC"; "TAO/USD" → "TAO/USD"
      const cached = snapshot[key];
      const base   = window.resolveBaseAsset(key, snapshot);
      const _dataState = radarData[key] ? "LIVE" : cached ? "CACHED" : "INIT";
      return { ...window.mergeRadar(base, radarData[key]), sym: key, _origSym: s,
               _loading: radarLoading.has(key), _dataState };
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
          {isCustomPreset && (
            <button
              onClick={onPortfolioClick}
              style={{
                background: 'transparent',
                border: '1px solid rgba(244,168,96,0.5)',
                color: '#f4a860',
                borderRadius: 5,
                padding: '3px 10px',
                fontSize: 10,
                letterSpacing: 1,
                cursor: 'pointer',
                fontFamily: 'monospace',
              }}
            >
              PORTFOLIO &#9658;
            </button>
          )}
          <span className="mono" style={{ fontSize: 12, color: "var(--ink-3)", letterSpacing: "0.16em" }}>SORT · EDGE↓</span>
          <span className="mono" style={{ fontSize: 12, color: "var(--ink-3)", letterSpacing: "0.16em" }}>VIEW · GRID</span>
        </div>
      </div>

      <div style={{
        flex: 1, minHeight: 0, overflowY: "auto",
        padding: 14,
        display: "grid",
        gridTemplateColumns: "repeat(auto-fill, minmax(240px, 1fr))",
        gap: 10,
        alignContent: "start",
      }}>
        {assets.map(a => (
          <window.AssetCard key={a._origSym || a.sym} asset={a}
            selected={focusedSym === a.sym}
            onClick={() => onOpen(a.sym)} />
        ))}
      </div>

      <Ticker radarData={radarData} />
    </div>
  );
}

export default AssetGrid;
