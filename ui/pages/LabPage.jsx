/* ── LabPage — saved backtest results viewer (Page 5) ──────── */
const { useState, useEffect } = React;

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

export default LabPage;
