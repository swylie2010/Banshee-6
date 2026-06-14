const { useState, useEffect } = React;

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
  const [val, setVal] = useState('');
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

  useEffect(load, []);

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

export default NewsPage;
