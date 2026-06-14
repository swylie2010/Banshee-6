/* JournalPage — paper trade log & outcome tracking (Page 7) */
const { useState, useEffect } = React;

/* ── helpers & constants (no closure deps) */
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

export default JournalPage;
