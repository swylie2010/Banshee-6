/* RiskDeskPage — reactive position sizing calculator (Page 6) */
const { useState, useEffect } = React;

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

export default RiskDeskPage;
