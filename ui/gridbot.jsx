/* Banshee — Gridbot Calculator
 * Educational tool: free gridbot configuration calculator.
 * Shows regime check, grid topology, level-by-level breakdown,
 * capital plan, and risk guardrails for any asset.
 * Uses the main dark chassis — no custom palette. */

/* ── Formatting helpers ────────────────────────────────────────────────────── */
function gbFmtPrice(p) {
  if (p == null || isNaN(p)) return "—";
  if (p < 0.0001) return p.toFixed(8);
  if (p < 0.01)   return p.toFixed(6);
  if (p < 1)      return p.toFixed(4);
  if (p < 100)    return p.toFixed(2);
  return p.toLocaleString(undefined, { maximumFractionDigits: 0 });
}
function gbFmtDollar(n) {
  if (n == null || isNaN(n)) return "—";
  return "$" + Math.abs(n).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}
function gbFmtPct(n, signed = true) {
  if (n == null || isNaN(n)) return "—";
  const s = signed && n >= 0 ? "+" : "";
  return s + n.toFixed(2) + "%";
}

/* ── Section header ────────────────────────────────────────────────────────── */
function GbSection({ label, desc }) {
  return (
    <div style={{ marginBottom: 10 }}>
      <div className="mono" style={{ fontSize: 10, letterSpacing: "0.18em", color: "var(--ink-3)", marginBottom: 4 }}>{label}</div>
      {desc && <div style={{ fontSize: 12, color: "var(--ink-4)", lineHeight: 1.55 }}>{desc}</div>}
    </div>
  );
}

/* ── Stat box ─────────────────────────────────────────────────────────────── */
function GbStat({ label, value, color }) {
  return (
    <div style={{ background: "var(--bg-3)", borderRadius: 4, padding: "8px 10px" }}>
      <div className="mono" style={{ fontSize: 10, color: "var(--ink-4)", letterSpacing: "0.16em", marginBottom: 2 }}>{label}</div>
      <div className="num" style={{ fontSize: 14, color: color || "var(--ink)", fontWeight: 600 }}>{value}</div>
    </div>
  );
}

/* ── Regime check panel ────────────────────────────────────────────────────── */
function GbRegimePanel({ regime }) {
  const ok = regime.eligible;
  const accentColor = ok ? "var(--buy)" : "var(--sell)";
  const borderColor = ok ? "rgba(94,234,212,0.2)" : "rgba(239,68,68,0.2)";

  const slopeColor = Math.abs(regime.ma120_slope_pct) < 1.5
    ? "var(--buy)" : Math.abs(regime.ma120_slope_pct) < 3 ? "var(--wait)" : "var(--sell)";
  const rsiColor = regime.rsi >= 30 && regime.rsi <= 70
    ? "var(--buy)" : regime.rsi > 70 || regime.rsi < 30 ? "var(--sell)" : "var(--wait)";

  return (
    <div style={{ background: "var(--bg-2)", border: `1px solid ${borderColor}`, borderRadius: 6, padding: "14px 16px" }}>
      <GbSection label="REGIME CHECK" desc="Is this asset currently oscillating sideways? Gridbots need ranging conditions — they get crushed by strong trends." />
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 10 }}>
        <span style={{ color: accentColor, fontSize: 22 }}>●</span>
        <span className="mono" style={{ fontSize: 15, fontWeight: 700, color: accentColor, letterSpacing: "0.08em" }}>
          {ok ? "GRID-ELIGIBLE" : "NOT ELIGIBLE"}
        </span>
      </div>
      <div style={{ fontSize: 12, color: "var(--ink-2)", lineHeight: 1.65, marginBottom: 12 }}>
        {regime.reason}
      </div>
      <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
        <GbStat label="MA120 SLOPE (5D)" value={gbFmtPct(regime.ma120_slope_pct)} color={slopeColor} />
        <GbStat label="RSI (14D)"         value={regime.rsi.toFixed(1)}           color={rsiColor} />
        <GbStat label="ATR (14D)"         value={"$" + gbFmtPrice(regime.atr14)}  color="var(--ink-2)" />
      </div>
    </div>
  );
}

/* ── Grid blueprint panel ──────────────────────────────────────────────────── */
function GbBlueprintPanel({ grid, topology, currentPrice }) {
  const isArith = topology === "arithmetic";
  const topoColor = isArith ? "var(--cyan)" : "var(--amber)";
  const topoBg    = isArith ? "rgba(56,189,248,0.08)" : "rgba(245,158,11,0.08)";
  const topoBdr   = isArith ? "rgba(56,189,248,0.25)" : "rgba(245,158,11,0.25)";

  const spacingStr = isArith
    ? "$" + gbFmtPrice(grid.spacing_abs) + " per level"
    : grid.spacing_pct.toFixed(2) + "% per level";
  const topoDesc = isArith
    ? "Equal dollar gaps — every level is " + spacingStr + ". Best for narrow, stable ranges."
    : "Equal percentage gaps — every level is " + spacingStr + ". Best for wide, volatile assets.";

  return (
    <div style={{ background: "var(--bg-2)", border: "1px solid var(--line)", borderRadius: 6, padding: "14px 16px" }}>
      <GbSection label="GRID BLUEPRINT" desc="The mathematical structure of your grid — bounds, spacing, and how many levels." />
      <div style={{ display: "inline-flex", alignItems: "center", gap: 6, padding: "3px 10px", borderRadius: 4, background: topoBg, border: `1px solid ${topoBdr}`, marginBottom: 10 }}>
        <span className="mono" style={{ fontSize: 11, color: topoColor, fontWeight: 700, letterSpacing: "0.12em" }}>
          {isArith ? "ARITHMETIC" : "GEOMETRIC"}
        </span>
      </div>
      <div style={{ fontSize: 12, color: "var(--ink-3)", marginBottom: 12, lineHeight: 1.55 }}>{topoDesc}</div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 8 }}>
        <GbStat label="UPPER BOUND"  value={"$" + gbFmtPrice(grid.upper)} />
        <GbStat label="LOWER BOUND"  value={"$" + gbFmtPrice(grid.lower)} />
        <GbStat label="RANGE"        value={grid.range_pct.toFixed(1) + "%"} />
        <GbStat label="GRID LEVELS"  value={grid.count} />
        <GbStat label="SPACING"      value={spacingStr.replace(" per level", "")} />
        <GbStat label="CURRENT PRICE" value={"$" + gbFmtPrice(currentPrice)} color="var(--ink-2)" />
      </div>
    </div>
  );
}

/* ── Grid levels table ─────────────────────────────────────────────────────── */
function GbLevelsTable({ levels, topology, gridUpper, gridLower }) {
  const rangeSize = gridUpper - gridLower || 1;
  const sorted = [...levels].reverse();

  return (
    <div style={{ background: "var(--bg-2)", border: "1px solid var(--line)", borderRadius: 6, padding: "14px 16px" }}>
      <GbSection label="GRID LEVELS" desc="Every row is a standing limit order. BUY orders wait below market price; SELL orders wait above. The bar shows each level's position in the range." />
      <div style={{ overflowY: "auto", maxHeight: 300, marginTop: 2 }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
          <thead>
            <tr style={{ borderBottom: "1px solid var(--line)" }}>
              {["#", "PRICE", "TYPE", "CAPITAL", topology === "arithmetic" ? "PROFIT/CYCLE" : "PROFIT %/CYCLE", "POSITION"].map(h => (
                <th key={h} className="mono" style={{
                  textAlign: "left", padding: "4px 8px",
                  color: "var(--ink-4)", fontSize: 10, letterSpacing: "0.12em",
                  fontWeight: 400, whiteSpace: "nowrap",
                }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sorted.map(lvl => {
              const isBuy  = lvl.type === "BUY";
              const isRef  = lvl.type === "REF";
              const rowClr = isRef ? "var(--ink)" : isBuy ? "var(--buy)" : "var(--wait)";
              const rowBg  = isRef ? "rgba(255,255,255,0.03)" : "transparent";
              const barPct = ((lvl.price - gridLower) / rangeSize) * 100;
              const profit = topology === "arithmetic"
                ? gbFmtDollar(lvl.profit_per_cycle)
                : (lvl.profit_pct_per_cycle != null ? lvl.profit_pct_per_cycle.toFixed(3) + "%" : "—");

              return (
                <tr key={lvl.index} style={{ borderBottom: "1px solid var(--bg-3)", background: rowBg }}>
                  <td className="num" style={{ padding: "5px 8px", color: "var(--ink-4)", fontSize: 11 }}>{lvl.index}</td>
                  <td className="num" style={{ padding: "5px 8px", color: rowClr, fontWeight: isRef ? 700 : 400 }}>
                    {gbFmtPrice(lvl.price)}
                  </td>
                  <td style={{ padding: "5px 8px" }}>
                    <span className="mono" style={{
                      fontSize: 10, letterSpacing: "0.1em", color: rowClr,
                      background: isRef ? "rgba(255,255,255,0.08)" : isBuy ? "rgba(94,234,212,0.1)" : "rgba(245,158,11,0.1)",
                      padding: "2px 6px", borderRadius: 3,
                    }}>{lvl.type}</span>
                  </td>
                  <td className="num" style={{ padding: "5px 8px", color: "var(--ink-2)" }}>
                    {gbFmtDollar(lvl.capital_allocated)}
                  </td>
                  <td className="num" style={{ padding: "5px 8px", color: "var(--ink-3)" }}>{profit}</td>
                  <td style={{ padding: "5px 12px 5px 8px", width: 90 }}>
                    <div style={{ position: "relative", height: 4, background: "var(--bg-3)", borderRadius: 2 }}>
                      <div style={{
                        position: "absolute",
                        left: Math.max(0, Math.min(100, barPct)) + "%",
                        top: 0, width: 2, height: 4,
                        background: rowClr, borderRadius: 1,
                        transform: "translateX(-50%)",
                      }} />
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

/* ── Capital plan panel ────────────────────────────────────────────────────── */
function GbCapitalPanel({ plan }) {
  const maxW = Math.max(...plan.weights, 1);
  const reversed = [...plan.weights].reverse();
  const reversedCap = [...plan.capital_per_level].reverse();

  return (
    <div style={{ background: "var(--bg-2)", border: "1px solid var(--line)", borderRadius: 6, padding: "14px 16px" }}>
      <GbSection label="CAPITAL PLAN" desc="50% anchors near the current price. The other 50% spreads across grid levels using a soft martingale — deeper levels get more ammo to average down without blowing up." />
      <div style={{ display: "flex", gap: 12, marginBottom: 14, flexWrap: "wrap" }}>
        <div>
          <div className="mono" style={{ fontSize: 10, color: "var(--ink-4)", letterSpacing: "0.16em" }}>ANCHOR</div>
          <div className="num" style={{ fontSize: 15, color: "var(--cyan)", fontWeight: 700 }}>{gbFmtDollar(plan.anchor)}</div>
          <div style={{ fontSize: 11, color: "var(--ink-4)", marginTop: 1 }}>buys base asset at market</div>
        </div>
        <div>
          <div className="mono" style={{ fontSize: 10, color: "var(--ink-4)", letterSpacing: "0.16em" }}>DISTRIBUTED</div>
          <div className="num" style={{ fontSize: 15, color: "var(--ink)", fontWeight: 700 }}>{gbFmtDollar(plan.grid_distributed)}</div>
          <div style={{ fontSize: 11, color: "var(--ink-4)", marginTop: 1 }}>across {plan.weights.length} levels (soft martingale)</div>
        </div>
      </div>
      <div style={{ fontSize: 11, color: "var(--ink-4)", marginBottom: 8 }}>
        Level distribution (top → bottom · outer levels get 3× more capital)
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 3 }}>
        {reversed.map((w, i) => {
          const barW = (w / maxW) * 100;
          const cap  = reversedCap[i];
          return (
            <div key={i} style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <div style={{ flex: 1, position: "relative", height: 7, background: "var(--bg-3)", borderRadius: 2 }}>
                <div style={{ width: barW + "%", height: "100%", background: "rgba(56,189,248,0.3)", borderRadius: 2, transition: "width 300ms" }} />
              </div>
              <div className="num" style={{ fontSize: 10, color: "var(--ink-4)", width: 52, textAlign: "right", flexShrink: 0 }}>
                {gbFmtDollar(cap)}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

/* ── Risk guardrails panel ─────────────────────────────────────────────────── */
function GbRiskPanel({ risk }) {
  const churnOk = !risk.churning_warning;
  const ddClr   = risk.max_drawdown_pct > 20 ? "var(--sell)"
                : risk.max_drawdown_pct > 10 ? "var(--wait)" : "var(--buy)";

  return (
    <div style={{ background: "var(--bg-2)", border: "1px solid var(--line)", borderRadius: 6, padding: "14px 16px" }}>
      <GbSection label="RISK GUARDRAILS" desc="The hard limits that stop a gridbot from losing everything in a crash or from grinding down through fees." />
      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>

        <div style={{ background: "var(--bg-3)", borderRadius: 4, padding: "10px 12px" }}>
          <div className="mono" style={{ fontSize: 10, color: "var(--ink-4)", letterSpacing: "0.16em", marginBottom: 4 }}>
            DISASTER STOP
          </div>
          <div className="num" style={{ fontSize: 14, color: "var(--sell)", fontWeight: 700 }}>
            ${gbFmtPrice(risk.disaster_stop)}
          </div>
          <div style={{ fontSize: 11, color: "var(--ink-4)", marginTop: 3 }}>
            1.5× ATR below lower bound. If breached → switch to DCA accumulation mode.
          </div>
        </div>

        <div style={{ background: "var(--bg-3)", borderRadius: 4, padding: "10px 12px" }}>
          <div className="mono" style={{ fontSize: 10, color: "var(--ink-4)", letterSpacing: "0.16em", marginBottom: 4 }}>
            EST. MAX DRAWDOWN
          </div>
          <div className="num" style={{ fontSize: 14, color: ddClr, fontWeight: 700 }}>
            {risk.max_drawdown_pct.toFixed(1)}%
          </div>
          <div style={{ fontSize: 11, color: "var(--ink-4)", marginTop: 3 }}>
            Estimated unrealized loss if price falls all the way to the lower bound.
          </div>
        </div>

        <div style={{
          background: churnOk ? "var(--bg-3)" : "rgba(239,68,68,0.06)",
          border: churnOk ? "none" : "1px solid rgba(239,68,68,0.2)",
          borderRadius: 4, padding: "10px 12px",
        }}>
          <div className="mono" style={{ fontSize: 10, color: "var(--ink-4)", letterSpacing: "0.16em", marginBottom: 4 }}>
            FEE CHURN CHECK
          </div>
          {churnOk ? (
            <div style={{ display: "flex", alignItems: "flex-start", gap: 6 }}>
              <span style={{ color: "var(--buy)", flexShrink: 0, marginTop: 1 }}>●</span>
              <span style={{ fontSize: 12, color: "var(--buy)", lineHeight: 1.5 }}>
                Grid spacing ({risk.spacing_pct.toFixed(3)}%) clears the 2.5× fee threshold ({risk.min_fee_spacing_pct.toFixed(3)}%). Each cycle is profitable after fees.
              </span>
            </div>
          ) : (
            <div style={{ display: "flex", alignItems: "flex-start", gap: 6 }}>
              <span style={{ color: "var(--sell)", flexShrink: 0, marginTop: 1 }}>●</span>
              <span style={{ fontSize: 12, color: "var(--sell)", lineHeight: 1.5 }}>
                Spacing ({risk.spacing_pct.toFixed(3)}%) is below the fee floor ({risk.min_fee_spacing_pct.toFixed(3)}%). The bot would trade at a loss — widen the grid or use a lower-fee exchange.
              </span>
            </div>
          )}
        </div>

      </div>
    </div>
  );
}

/* ── Main GridbotPage ──────────────────────────────────────────────────────── */
function GridbotPage({ onBack }) {
  const [sym,       setSym]       = React.useState("BTC");
  const [capital,   setCapital]   = React.useState("10000");
  const [gridCount, setGridCount] = React.useState(10);
  const [feePct,    setFeePct]    = React.useState("0.1");
  const [loading,   setLoading]   = React.useState(false);
  const [result,    setResult]    = React.useState(null);
  const [error,     setError]     = React.useState(null);

  const analyze = async () => {
    const cap = parseFloat(capital);
    const fee = parseFloat(feePct);
    if (!sym.trim() || isNaN(cap) || cap <= 0 || isNaN(fee) || fee < 0) return;
    setLoading(true);
    setError(null);
    try {
      const r = await window.API.analyzeGridbot(sym.trim().toUpperCase(), cap, gridCount, fee);
      if (r && r.error) { setError(r.error); setResult(null); }
      else { setResult(r); }
    } catch (e) {
      setError((e && (e.detail || e.error || e.message)) || "Analysis failed — check the backend is running.");
    } finally {
      setLoading(false);
    }
  };

  const inputBase = {
    background: "var(--bg-3)", border: "1px solid var(--line-2)",
    color: "var(--ink)", borderRadius: 4, padding: "7px 10px",
    fontFamily: "inherit", fontSize: 13, outline: "none",
  };

  return (
    <div style={{
      position: "absolute", inset: 0, background: "var(--bg-0)",
      overflowY: "auto", display: "flex", flexDirection: "column",
      zIndex: 100,
    }}>

      {/* ── Header ─────────────────────────────────────────────────────────── */}
      <div style={{
        height: 48, display: "flex", alignItems: "center", gap: 14,
        padding: "0 18px", borderBottom: "1px solid var(--line)",
        background: "var(--bg-1)", flexShrink: 0,
        position: "sticky", top: 0, zIndex: 10,
      }}>
        <button onClick={onBack} style={{
          background: "transparent", border: "1px solid var(--line-2)",
          color: "var(--ink-3)", cursor: "pointer", borderRadius: 4,
          padding: "4px 10px", fontFamily: "inherit", fontSize: 12, letterSpacing: "0.1em",
        }}>← BACK</button>
        <span className="mono" style={{ fontSize: 14, fontWeight: 700, color: "var(--ink)", letterSpacing: "0.1em" }}>
          ⊞ GRIDBOT CALCULATOR
        </span>
        <span className="mono" style={{
          fontSize: 10, color: "var(--bg-0)", background: "var(--cyan)",
          padding: "2px 7px", borderRadius: 3, letterSpacing: "0.14em", fontWeight: 700,
        }}>FREE TOOL</span>
        <span style={{ flex: 1 }} />
        <span className="mono" style={{ fontSize: 11, color: "var(--ink-4)", letterSpacing: "0.12em" }}>
          PRESS ESC TO CLOSE
        </span>
      </div>

      {/* ── Content ────────────────────────────────────────────────────────── */}
      <div style={{ padding: "20px 24px", maxWidth: 920, width: "100%", margin: "0 auto" }}>

        {/* Intro */}
        <div style={{
          background: "var(--bg-2)", border: "1px solid var(--line)", borderRadius: 6,
          padding: "14px 18px", marginBottom: 14,
        }}>
          <div style={{ fontSize: 13, color: "var(--ink-2)", lineHeight: 1.75 }}>
            A <strong style={{ color: "var(--ink)" }}>gridbot</strong> places a ladder of buy and sell orders across a price range, automatically buying dips and selling bounces to earn small, repeated profits from oscillation.{" "}
            They thrive in <strong style={{ color: "var(--buy)" }}>sideways markets</strong> and get hurt by strong trends — so the first step is always checking whether your asset is actually ranging.{" "}
            <span style={{ color: "var(--ink-3)" }}>Commercial gridbot calculators charge for this. We don't.</span>
          </div>
        </div>

        {/* Input form */}
        <div style={{
          background: "var(--bg-2)", border: "1px solid var(--line)", borderRadius: 6,
          padding: "14px 18px", marginBottom: 14,
        }}>
          <div style={{ display: "flex", gap: 12, flexWrap: "wrap", alignItems: "flex-end" }}>

            <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
              <label className="mono" style={{ fontSize: 10, color: "var(--ink-4)", letterSpacing: "0.16em" }}>ASSET</label>
              <input
                value={sym}
                onChange={e => setSym(e.target.value)}
                onKeyDown={e => e.key === "Enter" && analyze()}
                style={{ ...inputBase, width: 88 }}
                placeholder="BTC"
              />
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
              <label className="mono" style={{ fontSize: 10, color: "var(--ink-4)", letterSpacing: "0.16em" }}>CAPITAL ($)</label>
              <input
                value={capital}
                onChange={e => setCapital(e.target.value)}
                onKeyDown={e => e.key === "Enter" && analyze()}
                style={{ ...inputBase, width: 110 }}
                placeholder="10000"
              />
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
              <label className="mono" style={{ fontSize: 10, color: "var(--ink-4)", letterSpacing: "0.16em" }}>GRID LEVELS · {gridCount}</label>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <input
                  type="range" min={3} max={50} value={gridCount}
                  onChange={e => setGridCount(parseInt(e.target.value))}
                  style={{ width: 110, cursor: "pointer", accentColor: "var(--cyan)" }}
                />
                <span className="num" style={{ fontSize: 13, color: "var(--ink-2)", width: 24 }}>{gridCount}</span>
              </div>
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
              <label className="mono" style={{ fontSize: 10, color: "var(--ink-4)", letterSpacing: "0.16em" }}>EXCHANGE FEE %</label>
              <input
                value={feePct}
                onChange={e => setFeePct(e.target.value)}
                onKeyDown={e => e.key === "Enter" && analyze()}
                style={{ ...inputBase, width: 90 }}
                placeholder="0.1"
              />
            </div>

            <button
              onClick={analyze}
              disabled={loading}
              style={{
                background: loading ? "var(--bg-4)" : "var(--cyan)",
                color: loading ? "var(--ink-4)" : "var(--bg-0)",
                border: "none", cursor: loading ? "default" : "pointer",
                borderRadius: 4, padding: "8px 22px",
                fontFamily: "inherit", fontSize: 12, letterSpacing: "0.12em", fontWeight: 700,
                transition: "all 120ms", alignSelf: "flex-end",
              }}
            >
              {loading ? "FETCHING..." : "ANALYZE"}
            </button>

          </div>
          <div style={{ fontSize: 11, color: "var(--ink-4)", marginTop: 10 }}>
            Supports stocks (SPY, QQQ, NVDA) and crypto (BTC, ETH, SOL). Data: 6 months of daily bars via yfinance.
          </div>
        </div>

        {/* Error */}
        {error && (
          <div style={{
            background: "rgba(239,68,68,0.07)", border: "1px solid rgba(239,68,68,0.2)",
            borderRadius: 6, padding: "12px 16px", marginBottom: 14,
            color: "var(--sell)", fontSize: 13, lineHeight: 1.5,
          }}>
            {error}
          </div>
        )}

        {/* Loading */}
        {loading && (
          <div style={{ textAlign: "center", color: "var(--ink-4)", fontSize: 13, padding: "48px 0" }}>
            <div style={{ marginBottom: 8, fontSize: 20 }}>⊞</div>
            Fetching 6 months of daily data for {sym.toUpperCase()}...
            <div style={{ marginTop: 6, color: "var(--ink-4)", fontSize: 11 }}>
              This takes 2–4 seconds — yfinance is fetching from the market data provider.
            </div>
          </div>
        )}

        {/* Results */}
        {result && !loading && (
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>

            {/* Regime */}
            <GbRegimePanel regime={result.regime} />

            {/* Blueprint */}
            <GbBlueprintPanel
              grid={result.grid}
              topology={result.topology}
              currentPrice={result.current_price}
            />

            {/* Grid Levels */}
            <GbLevelsTable
              levels={result.levels}
              topology={result.topology}
              gridUpper={result.grid.upper}
              gridLower={result.grid.lower}
            />

            {/* Capital + Risk side by side */}
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
              <GbCapitalPanel plan={result.capital_plan} />
              <GbRiskPanel    risk={result.risk} />
            </div>

            {/* Footer note */}
            <div style={{
              background: "var(--bg-2)", border: "1px solid var(--line)", borderRadius: 6,
              padding: "12px 16px",
            }}>
              <div style={{ fontSize: 11, color: "var(--ink-4)", lineHeight: 1.7 }}>
                <strong style={{ color: "var(--ink-3)" }}>How to read this:</strong>{" "}
                Banshee calculates — you decide. This tool shows what a gridbot would look like given current market conditions.
                The ELIGIBLE/NOT ELIGIBLE verdict is a flag, not a block. You own the decision.
                Profit estimates assume the price oscillates across the full grid range and do not account for slippage.
                Past volatility does not guarantee future oscillation.
              </div>
            </div>

          </div>
        )}

        {/* Empty state */}
        {!result && !loading && !error && (
          <div style={{ textAlign: "center", color: "var(--ink-4)", fontSize: 13, padding: "48px 0" }}>
            <div style={{ fontSize: 28, marginBottom: 10, color: "var(--ink-4)" }}>⊞</div>
            Enter an asset and click ANALYZE to see your gridbot blueprint.
          </div>
        )}

      </div>
    </div>
  );
}

window.GridbotPage = GridbotPage;
