/* ObservatoryPage — audit log viewer + trend dashboard */
const { useState, useEffect, useRef } = React;

const TOOLS = [
  "", "get_macro_weather", "read_market_intel", "get_regime", "get_watchlist",
  "get_asset_radar", "scan_assets", "synthesize_nexus", "build_execution_plan",
  "get_smc_structure", "open_paper_trade", "log_signal_outcome", "check_kill_switch",
  "get_signal_log", "get_feedback_synthesis", "get_geo_harmonic",
  "scan_xabcd", "get_options_candidate", "get_paper_wheels", "open_paper_wheel",
  "analyze_gridbot", "deploy_paper_gridbot", "get_paper_gridbot", "stop_paper_gridbot",
  "get_audit_log", "get_audit_summary",
];

function fmtTs(ts) {
  if (!ts) return "—";
  try {
    const d = new Date(ts);
    const pad = n => String(n).padStart(2, "0");
    return `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
  } catch { return ts; }
}

function StatusDot({ passed }) {
  const color = passed ? "var(--buy)" : "var(--sell)";
  return (
    <span style={{
      display: "inline-block", width: 8, height: 8, borderRadius: "50%",
      background: color, marginRight: 6, flexShrink: 0,
    }} />
  );
}

function EntryRow({ entry }) {
  const [open, setOpen] = useState(false);
  const passed = entry.validation?.passed !== false;
  return (
    <div style={{
      borderBottom: "1px solid var(--line)",
      background: open ? "rgba(255,255,255,0.02)" : "transparent",
    }}>
      <button
        onClick={() => setOpen(o => !o)}
        style={{
          width: "100%", display: "flex", alignItems: "center", gap: 10,
          padding: "8px 14px", background: "transparent", border: "none",
          cursor: "pointer", textAlign: "left",
        }}
      >
        <StatusDot passed={passed} />
        <span className="mono" style={{ fontSize: 14, color: "var(--ink-2)", width: 180, flexShrink: 0 }}>
          {fmtTs(entry.ts)}
        </span>
        <span className="mono" style={{ fontSize: 14, color: "var(--cyan)", flex: 1 }}>
          {entry.tool}
        </span>
        <span className="mono" style={{ fontSize: 14, color: "var(--ink-3)", width: 60, textAlign: "right", flexShrink: 0 }}>
          {entry.outcome?.duration_ms != null ? `${entry.outcome.duration_ms}ms` : "—"}
        </span>
        <span className="mono" style={{
          fontSize: 14, color: passed ? "var(--buy)" : "var(--sell)",
          width: 60, textAlign: "right", flexShrink: 0,
        }}>
          {entry.outcome?.status || "—"}
        </span>
      </button>
      {open && (
        <div style={{ padding: "8px 14px 14px 38px" }}>
          <pre style={{
            fontFamily: "var(--mono)", fontSize: 13, color: "var(--ink-2)",
            background: "var(--bg-1)", border: "1px solid var(--line)",
            borderRadius: 4, padding: 10, margin: 0,
            whiteSpace: "pre-wrap", wordBreak: "break-all",
            maxHeight: 300, overflowY: "auto",
          }}>
            {JSON.stringify(entry, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}

function StatBox({ label, value, color }) {
  return (
    <div style={{
      background: "var(--bg-1)", border: "1px solid var(--line)",
      borderRadius: 6, padding: "12px 16px", flex: 1, minWidth: 120,
    }}>
      <div className="mono" style={{ fontSize: 14, color: "var(--ink-3)", letterSpacing: "0.12em", marginBottom: 6 }}>{label}</div>
      <div className="num" style={{ fontSize: 22, color: color || "var(--ink)", fontWeight: 700 }}>{value}</div>
    </div>
  );
}

function SimpleBar({ label, value, max, color }) {
  const pct = max > 0 ? Math.round((value / max) * 100) : 0;
  return (
    <div style={{ marginBottom: 8 }}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
        <span className="mono" style={{ fontSize: 14, color: "var(--ink-2)" }}>{label}</span>
        <span className="num" style={{ fontSize: 14, color: "var(--ink-2)" }}>{value}</span>
      </div>
      <div style={{ height: 6, background: "var(--bg-1)", borderRadius: 3, overflow: "hidden" }}>
        <div style={{ height: "100%", width: `${pct}%`, background: color || "var(--cyan)", borderRadius: 3 }} />
      </div>
    </div>
  );
}

export default function ObservatoryPage({ onBack }) {
  const [entries, setEntries] = useState([]);
  const [total, setTotal] = useState(0);
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [summaryLoading, setSummaryLoading] = useState(true);
  const [error, setError] = useState(null);
  const [filterTool, setFilterTool] = useState("");
  const [filterStatus, setFilterStatus] = useState("");  // "" | "passed" | "failed"
  const [summaryDays, setSummaryDays] = useState(7);
  const [offset, setOffset] = useState(0);
  const LIMIT = 50;
  const refreshRef = useRef(null);

  const loadEntries = async () => {
    setLoading(true);
    try {
      const params = { limit: LIMIT, offset };
      if (filterTool) params.tool = filterTool;
      const data = await window.API.fetchAuditEntries(params);
      if (data.error) { setError(data.error); return; }
      let list = data.entries || [];
      if (filterStatus === "passed") list = list.filter(e => e.validation?.passed !== false);
      if (filterStatus === "failed") list = list.filter(e => e.validation?.passed === false);
      setEntries(list);
      setTotal(data.total || 0);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const loadSummary = async () => {
    setSummaryLoading(true);
    try {
      const data = await window.API.fetchAuditSummary(summaryDays);
      if (!data.error) setSummary(data);
    } finally {
      setSummaryLoading(false);
    }
  };

  useEffect(() => {
    loadEntries();
    loadSummary();
    refreshRef.current = setInterval(loadEntries, 30000);
    return () => clearInterval(refreshRef.current);
  }, [filterTool, filterStatus, summaryDays, offset]);

  useEffect(() => {
    const handler = e => {
      if (e.key === "Escape") onBack?.();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onBack]);

  const toolCounts = summary?.calls?.by_tool || {};
  const maxToolCount = Math.max(...Object.values(toolCounts), 1);
  const signalDist = summary?.signal_distribution || {};
  const failureRate = summary?.calls?.validation_failure_rate ?? 0;

  return (
    <div style={{
      position: "absolute", inset: 0,
      background: "var(--bg-2)",
      display: "flex", flexDirection: "column",
      overflow: "hidden", zIndex: 10,
    }}>
      {/* Header */}
      <div style={{
        height: 48, flexShrink: 0,
        borderBottom: "1px solid var(--line)",
        background: "var(--bg-1)",
        display: "flex", alignItems: "center", padding: "0 16px", gap: 12,
      }}>
        <button
          onClick={onBack}
          style={{
            background: "transparent", border: "1px solid var(--line)",
            color: "var(--ink-3)", cursor: "pointer", padding: "4px 10px",
            fontFamily: "var(--mono)", fontSize: 14, letterSpacing: "0.1em",
          }}
        >← BACK</button>
        <span className="mono" style={{ fontSize: 15, fontWeight: 700, color: "var(--ink)", letterSpacing: "0.16em" }}>
          OBSERVATORY
        </span>
        <span className="mono" style={{ fontSize: 14, color: "var(--ink-4)" }}>
          behavioral audit log
        </span>
        <div style={{ flex: 1 }} />
        <button
          onClick={() => { loadEntries(); loadSummary(); }}
          style={{
            background: "transparent", border: "1px solid var(--line)",
            color: "var(--cyan)", cursor: "pointer", padding: "4px 10px",
            fontFamily: "var(--mono)", fontSize: 14, letterSpacing: "0.1em",
          }}
        >↻ REFRESH</button>
      </div>

      {/* Scrollable body */}
      <div style={{ flex: 1, overflowY: "auto", padding: 16, display: "flex", flexDirection: "column", gap: 20 }}>

        {/* Trend Dashboard */}
        <div style={{
          background: "var(--bg-1)", border: "1px solid var(--line)", borderRadius: 6, padding: 16,
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 14 }}>
            <span className="mono" style={{ fontSize: 14, color: "var(--ink-2)", fontWeight: 600, letterSpacing: "0.12em" }}>
              TREND DASHBOARD
            </span>
            {[7, 30, 90].map(d => (
              <button key={d} onClick={() => setSummaryDays(d)} style={{
                background: summaryDays === d ? "var(--buy-faint, rgba(56,189,248,0.12))" : "transparent",
                border: `1px solid ${summaryDays === d ? "var(--cyan)" : "var(--line)"}`,
                color: summaryDays === d ? "var(--cyan)" : "var(--ink-3)",
                cursor: "pointer", padding: "3px 10px",
                fontFamily: "var(--mono)", fontSize: 14,
              }}>{d}D</button>
            ))}
          </div>

          {summaryLoading && (
            <div className="mono" style={{ fontSize: 14, color: "var(--ink-4)" }}>Loading...</div>
          )}

          {summary && !summaryLoading && (
            <>
              {/* Stat boxes */}
              <div style={{ display: "flex", gap: 12, flexWrap: "wrap", marginBottom: 16 }}>
                <StatBox label="TOTAL CALLS" value={summary.calls?.total ?? 0} color="var(--ink)" />
                <StatBox
                  label="FAILURE RATE"
                  value={`${(failureRate * 100).toFixed(1)}%`}
                  color={failureRate > 0.1 ? "var(--sell)" : "var(--buy)"}
                />
                <StatBox label="AVG LATENCY" value={`${summary.avg_latency_ms ?? 0}ms`} color="var(--ink-2)" />
                <StatBox label="TOP TICKER" value={summary.top_tickers?.[0] || "—"} color="var(--cyan)" />
              </div>

              {/* Daily call volume bar chart — pure CSS flex bars */}
              {Object.keys(summary.calls?.per_day || {}).length > 0 && (
                <div style={{ marginBottom: 16 }}>
                  <div className="mono" style={{ fontSize: 14, color: "var(--ink-4)", letterSpacing: "0.12em", marginBottom: 8 }}>
                    CALL VOLUME — LAST {summaryDays} DAYS
                  </div>
                  {/* scroll wrapper (plain div) containing inner flex row */}
                  <div style={{ overflowX: "auto" }}>
                    <div style={{ display: "flex", alignItems: "flex-end", gap: 3, height: 60, minWidth: "100%" }}>
                      {Object.entries(summary.calls.per_day).map(([day, count]) => {
                        const maxDay = Math.max(...Object.values(summary.calls.per_day), 1);
                        const barH = Math.max(4, Math.round((count / maxDay) * 44));
                        return (
                          <div key={day} title={`${day}: ${count} calls`}
                            style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", gap: 2, cursor: "default" }}>
                            <div style={{ width: "100%", height: barH, background: "var(--cyan)", borderRadius: "2px 2px 0 0", opacity: 0.65 }} />
                            <span className="num" style={{ fontSize: 14, color: "var(--ink-4)" }}>{count}</span>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                </div>
              )}

              {/* Three-column grid: tool usage, top violations, signal distribution */}
              {/* scroll wrapper to avoid grid+overflow trap */}
              <div style={{ overflowX: "auto" }}>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 16, minWidth: 480 }}>
                  {/* Tool usage */}
                  <div>
                    <div className="mono" style={{ fontSize: 14, color: "var(--ink-4)", letterSpacing: "0.12em", marginBottom: 10 }}>
                      TOOL USAGE
                    </div>
                    {Object.entries(toolCounts).slice(0, 8).map(([tool, count]) => (
                      <SimpleBar key={tool} label={tool} value={count} max={maxToolCount} color="var(--cyan)" />
                    ))}
                    {Object.keys(toolCounts).length === 0 && (
                      <div className="mono" style={{ fontSize: 14, color: "var(--ink-4)" }}>No data yet</div>
                    )}
                  </div>

                  {/* Top violations */}
                  <div>
                    <div className="mono" style={{ fontSize: 14, color: "var(--ink-4)", letterSpacing: "0.12em", marginBottom: 10 }}>
                      TOP VIOLATIONS
                    </div>
                    {(summary.top_violations || []).slice(0, 8).map(v => (
                      <SimpleBar key={v.rule} label={v.rule} value={v.count}
                                 max={summary.top_violations[0]?.count || 1} color="var(--sell)" />
                    ))}
                    {(summary.top_violations || []).length === 0 && (
                      <div className="mono" style={{ fontSize: 14, color: "var(--buy)" }}>No violations</div>
                    )}
                  </div>

                  {/* Signal distribution */}
                  <div>
                    <div className="mono" style={{ fontSize: 14, color: "var(--ink-4)", letterSpacing: "0.12em", marginBottom: 10 }}>
                      SIGNAL DISTRIBUTION
                    </div>
                    {Object.entries(signalDist).map(([sig, pct]) => (
                      <div key={sig} style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
                        <span className="mono" style={{ fontSize: 14, color: "var(--ink-2)" }}>{sig}</span>
                        <span className="num" style={{ fontSize: 14, color: "var(--ink-2)" }}>{(pct * 100).toFixed(1)}%</span>
                      </div>
                    ))}
                    {Object.keys(signalDist).length === 0 && (
                      <div className="mono" style={{ fontSize: 14, color: "var(--ink-4)" }}>No signal data yet</div>
                    )}

                    {/* Top tickers */}
                    {(summary.top_tickers || []).length > 0 && (
                      <>
                        <div className="mono" style={{ fontSize: 14, color: "var(--ink-4)", letterSpacing: "0.12em", marginTop: 14, marginBottom: 8 }}>
                          TOP TICKERS
                        </div>
                        {(summary.top_tickers || []).slice(0, 5).map((t, i) => (
                          <div key={t} style={{ display: "flex", gap: 8, marginBottom: 4 }}>
                            <span className="mono" style={{ fontSize: 14, color: "var(--ink-4)", width: 20 }}>{i+1}.</span>
                            <span className="mono" style={{ fontSize: 14, color: "var(--cyan)" }}>{t}</span>
                          </div>
                        ))}
                      </>
                    )}
                  </div>
                </div>
              </div>
            </>
          )}
        </div>

        {/* Log Viewer */}
        <div style={{ background: "var(--bg-1)", border: "1px solid var(--line)", borderRadius: 6 }}>
          {/* Filter bar */}
          <div style={{
            padding: "10px 14px", borderBottom: "1px solid var(--line)",
            display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap",
          }}>
            <span className="mono" style={{ fontSize: 14, color: "var(--ink-2)", fontWeight: 600, letterSpacing: "0.12em" }}>
              AUDIT LOG
            </span>
            <span className="mono" style={{ fontSize: 14, color: "var(--ink-4)" }}>
              {total} entries total
            </span>
            <div style={{ flex: 1 }} />
            <select
              value={filterTool}
              onChange={e => { setFilterTool(e.target.value); setOffset(0); }}
              style={{
                background: "var(--bg-2)", border: "1px solid var(--line)",
                color: "var(--ink-2)", fontFamily: "var(--mono)", fontSize: 14,
                padding: "4px 8px", cursor: "pointer",
              }}
            >
              {TOOLS.map(t => <option key={t} value={t}>{t || "All tools"}</option>)}
            </select>
            <select
              value={filterStatus}
              onChange={e => { setFilterStatus(e.target.value); setOffset(0); }}
              style={{
                background: "var(--bg-2)", border: "1px solid var(--line)",
                color: "var(--ink-2)", fontFamily: "var(--mono)", fontSize: 14,
                padding: "4px 8px", cursor: "pointer",
              }}
            >
              <option value="">All status</option>
              <option value="passed">Passed</option>
              <option value="failed">Failed</option>
            </select>
          </div>

          {/* Status filter info notice */}
          {filterStatus !== "" && (
            <div style={{
              padding: "8px 14px", borderBottom: "1px solid var(--line)",
              fontSize: 14, color: "var(--ink)", opacity: 0.6,
            }}>
              Filtering by status applies to this page only. Use pagination to see more entries.
            </div>
          )}

          {/* Entries */}
          {loading && (
            <div className="mono" style={{ padding: 20, fontSize: 14, color: "var(--ink-4)" }}>Loading...</div>
          )}
          {error && (
            <div className="mono" style={{ padding: 20, fontSize: 14, color: "var(--sell)" }}>{error}</div>
          )}
          {!loading && !error && entries.length === 0 && (
            <div className="mono" style={{ padding: 20, fontSize: 14, color: "var(--ink-4)" }}>
              No audit entries yet. Use any Banshee MCP tool to generate entries.
            </div>
          )}
          {!loading && !error && entries.map(e => (
            <EntryRow key={e.id} entry={e} />
          ))}

          {/* Pagination */}
          {total > LIMIT && (
            <div style={{
              padding: "10px 14px", borderTop: "1px solid var(--line)",
              display: "flex", alignItems: "center", gap: 10,
            }}>
              <button
                onClick={() => setOffset(Math.max(0, offset - LIMIT))}
                disabled={offset === 0}
                style={{
                  background: "transparent", border: "1px solid var(--line)",
                  color: offset === 0 ? "var(--ink-4)" : "var(--ink-2)",
                  cursor: offset === 0 ? "default" : "pointer",
                  padding: "4px 10px", fontFamily: "var(--mono)", fontSize: 14,
                }}
              >← PREV</button>
              <span className="mono" style={{ fontSize: 14, color: "var(--ink-3)" }}>
                {offset + 1}–{Math.min(offset + LIMIT, total)} of {total}
              </span>
              <button
                onClick={() => setOffset(offset + LIMIT)}
                disabled={offset + LIMIT >= total}
                style={{
                  background: "transparent", border: "1px solid var(--line)",
                  color: offset + LIMIT >= total ? "var(--ink-4)" : "var(--ink-2)",
                  cursor: offset + LIMIT >= total ? "default" : "pointer",
                  padding: "4px 10px", fontFamily: "var(--mono)", fontSize: 14,
                }}
              >NEXT →</button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
