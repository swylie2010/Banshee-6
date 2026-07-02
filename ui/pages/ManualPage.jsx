/* ── ManualPage helpers ─────────────────────────────────────── */
function ManLensCard({ num, name, accent, question, shows, use }) {
  return (
    <div style={{ background: "var(--bg-3)", border: "1px solid var(--line)", borderLeft: `3px solid ${accent}`, padding: "12px 14px" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8 }}>
        <span className="mono" style={{ background: accent, color: "var(--bg-0)", fontSize: 13, fontWeight: 700, width: 22, height: 22, display: "inline-flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>{num}</span>
        <span className="mono" style={{ fontSize: 14, fontWeight: 700, letterSpacing: "0.14em", color: accent }}>{name}</span>
        <span className="mono" style={{ fontSize: 12, color: "var(--ink-4)", marginLeft: "auto" }}>KEY {num}</span>
      </div>
      <div className="mono" style={{ fontSize: 12, color: "var(--amber)", letterSpacing: "0.04em", fontStyle: "italic", marginBottom: 8 }}>"{question}"</div>
      <div style={{ fontSize: 13, color: "var(--ink-2)", lineHeight: 1.65, marginBottom: 6 }}><span style={{ color: "var(--ink-3)", fontWeight: 600 }}>Shows: </span>{shows}</div>
      <div style={{ fontSize: 13, color: "var(--ink-2)", lineHeight: 1.65 }}><span style={{ color: "var(--ink-3)", fontWeight: 600 }}>Use when: </span>{use}</div>
    </div>
  );
}
function ManConcept({ name, accent, encoding, children }) {
  return (
    <div style={{ borderLeft: `3px solid ${accent || "var(--line-2)"}`, paddingLeft: 12, marginBottom: 16 }}>
      <div className="mono" style={{ fontSize: 13, fontWeight: 700, color: accent || "var(--ink)", letterSpacing: "0.08em", marginBottom: 4 }}>{name}</div>
      <div style={{ fontSize: 13, color: "var(--ink-2)", lineHeight: 1.65, marginBottom: encoding ? 5 : 0 }}>{children}</div>
      {encoding && <div className="mono" style={{ fontSize: 12, color: "var(--ink-4)", letterSpacing: "0.04em" }}>{encoding}</div>}
    </div>
  );
}
function ManStep({ n, title, children }) {
  return (
    <div style={{ display: "flex", gap: 12, marginBottom: 14 }}>
      <span className="mono" style={{ fontSize: 13, fontWeight: 700, color: "var(--cyan)", minWidth: 20, paddingTop: 1, flexShrink: 0 }}>{n}.</span>
      <div>
        <div className="mono" style={{ fontSize: 13, fontWeight: 700, color: "var(--ink)", letterSpacing: "0.08em", marginBottom: 3 }}>{title}</div>
        <div style={{ fontSize: 13, color: "var(--ink-2)", lineHeight: 1.65 }}>{children}</div>
      </div>
    </div>
  );
}
function ManSectionHdr({ title, accent, sub }) {
  return (
    <div style={{ padding: "10px 16px", borderBottom: "1px solid var(--line)", borderLeft: `3px solid ${accent}`, display: "flex", alignItems: "center", gap: 8 }}>
      <span className="mono" style={{ fontSize: 12, fontWeight: 700, letterSpacing: "0.18em", color: accent }}>{title}</span>
      {sub && <span className="mono" style={{ fontSize: 12, color: "var(--ink-4)", marginLeft: "auto" }}>{sub}</span>}
    </div>
  );
}

/* ── ManualPage — in-app reference guide (Page 8) ──────────── */
function ManualPage({ onBack }) {
  const CARD = { background: "var(--bg-2)", border: "1px solid var(--line)" };
  const XABCD_PATTERNS = [
    ["GARTLEY",   "0.618 XA",       "0.382–0.886 AB", "0.786 XA"],
    ["BAT",       "0.382–0.5 XA",   "0.382–0.886 AB", "0.886 XA"],
    ["ALT BAT",   "0.382 XA",       "0.382–0.886 AB", "1.13 XA"],
    ["BUTTERFLY", "0.786 XA",       "0.382–0.886 AB", "1.272–1.618 XA"],
    ["CRAB",      "0.382–0.618 XA", "0.382–0.886 AB", "1.618 XA"],
    ["DEEP CRAB", "0.886 XA",       "0.382–0.886 AB", "1.618 XA"],
    ["SHARK",     "0.446–0.618 XA", "1.13–1.618 BC",  "0.886–1.13 OX"],
    ["5-0",       "BC extension",   "1.618–2.24 AB",  "0.5 BC"],
  ];
  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", background: "var(--bg-1)", color: "var(--ink)", overflow: "hidden" }}>

      {/* Header */}
      <div style={{ padding: "18px 24px 14px", borderBottom: "1px solid var(--line)", display: "flex", alignItems: "center", gap: 16, flexShrink: 0 }}>
        <button onClick={onBack} style={{ background: "none", border: "none", color: "#FF6D00", cursor: "pointer", fontSize: 16, padding: 0 }}>←</button>
        <div>
          <div className="mono" style={{ fontSize: 13, fontWeight: 700, letterSpacing: "0.18em", color: "var(--ink)" }}>◌ MANUAL</div>
          <div className="mono" style={{ fontSize: 12, color: "var(--ink-4)", letterSpacing: "0.1em", marginTop: 2 }}>Lenses · Setup workflow · Risk Desk · SMC concepts · GH arcs · XABCD</div>
        </div>
      </div>

      {/* Scrollable content */}
      <div style={{ flex: 1, overflowY: "auto", padding: "20px 24px", display: "flex", flexDirection: "column", gap: 20 }}>

        {/* THE FOUR LENSES */}
        <div style={CARD}>
          <ManSectionHdr title="THE FOUR LENSES" accent="var(--cyan)" sub="SMC ANALYSIS · HOTKEYS 1–4" />
          <div style={{ padding: "14px 16px", display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
            <ManLensCard num={1} name="ALL" accent="var(--ink-2)"
              question="What's the full picture?"
              shows="Everything: OBs, FVGs, HTF reference lines, swing markers, EQH/EQL liquidity, PD background. Dynamic weight applied — elements near current price are brighter."
              use="Getting oriented on a new asset. Warning: visual density is high. Always switch to a focused lens before making any decisions." />
            <ManLensCard num={2} name="BATTLEFIELD" accent="var(--cyan)"
              question="Should I be long or short?"
              shows="Trend structure only — swing high/low markers, BOS and CHoCH event boxes, HTF reference levels, premium/discount gradient, OTE price lines. No OBs or FVGs."
              use="First step every session. Read the structural narrative before you look at entry zones. A bullish structure means you're hunting longs; bearish means shorts." />
            <ManLensCard num={3} name="FOOTPRINTS" accent="var(--magenta)"
              question="Where did institutions leave a mess?"
              shows="FVGs (imbalances price must return to fill), EQH/EQL liquidity pools (retail stop clusters), and pending-inducement OBs (traps not yet fired)."
              use="Finding magnets and traps. Pair with BATTLEFIELD context: a bullish FVG in the discount zone is a buy target; an EQL just below your OB is the trigger that must fire first." />
            <ManLensCard num={4} name="SNIPER" accent="var(--amber)"
              question="Where exactly do I pull the trigger?"
              shows="Inducement-swept OBs (full opacity — ready to enter), untagged OBs (40%), touched/degraded OBs (20%). OTE lines remain. Everything else hidden."
              use="Final step before entry. If nothing appears on SNIPER, there is no high-conviction setup on this timeframe. That is useful information — don't force a trade." />
          </div>
        </div>

        {/* SETUP WORKFLOW */}
        <div style={CARD}>
          <ManSectionHdr title="SETUP WORKFLOW" accent="var(--amber)" sub="8 STEPS · IN ORDER" />
          <div style={{ padding: "14px 16px" }}>
            <ManStep n={1} title="READ STRUCTURE STATE">
              The sidebar shows BULLISH / BEARISH / UNDEFINED — the state machine's verdict from the swing sequence. This is your filter for everything downstream. An UNDEFINED state means no clear trend; only take high-confluence setups.
            </ManStep>
            <ManStep n={2} title="BATTLEFIELD CHECK  (key 2)">
              Confirm the swing sequence visually. HH/HL chain = bullish. LH/LL = bearish. If you see a CHoCH in your direction, structure may be flipping — wait for a follow-through BOS before switching bias. Don't anticipate what isn't confirmed yet.
            </ManStep>
            <ManStep n={3} title="ZONE CHECK — PREMIUM OR DISCOUNT?">
              {"Green background = discount (below 50%). Red = premium (above 50%). The OTE band (amber lines, 61–79%) is the ideal pullback zone. Long setups belong in discount or OTE. Short setups in premium. If price is at EQ, wait for it to commit to a side."}
            </ManStep>
            <ManStep n={4} title="FOOTPRINTS CHECK  (key 3)">
              {"Are there FVGs or EQH/EQL in your target zone? A bullish FVG in the discount zone is a price magnet — expect a return before continuation. An EQL just below your OB is inducement that must be swept before the OB is actionable."}
            </ManStep>
            <ManStep n={5} title="SNIPER — FIND THE OB  (key 4)">
              {"⚡ Green border = inducement swept → enter at the OB zone. ⌛ Amber border = trap set but not fired → watch, don't enter yet. No border = lower conviction. Skip degraded or sapped OBs — they failed to hold."}
            </ManStep>
            <ManStep n={6} title="HTF ALIGNMENT">
              Run the same check on a higher timeframe (e.g. 1D when you're on 4H). A bullish 4H setup inside a bearish 1D structure is counter-trend — lower size or skip. HTF and LTF agreement is the conviction multiplier.
            </ManStep>
            <ManStep n={7} title="SESSION WEIGHT CHECK">
              {"OBs formed or approached during ⚡ Silver Bullet windows (03–04, 10–11, 14–15 EST) carry 2× weight. ◈ London/NY Killzones carry 1.5×. Asian range (20:00–00:00) carries 0.5× — entries here are lower probability. The badge on each OB tells you its session weight."}
            </ManStep>
            <ManStep n={8} title="AI BRIEFING — CROSS-CHECK YOUR READ">
              Read the SMC Analysis brief to catch what you missed. If the AI read contradicts your interpretation, investigate — the engine may be seeing structure you skipped, or it may be wrong. Either way, the discrepancy is worth understanding before you commit size.
            </ManStep>
          </div>
        </div>

        {/* RISK DESK + SIMULATE */}
        <div style={CARD}>
          <ManSectionHdr title="RISK DESK + SIMULATE" accent="var(--amber)" sub="SIDEBAR · ⚖ RISK DESK  ·  ASSET HUB · SIMULATE / EXECUTE" />
          <div style={{ padding: "14px 16px" }}>
            <div style={{ fontSize: 13, color: "var(--ink-2)", lineHeight: 1.7, marginBottom: 14 }}>
              Risk Desk is a pure position-sizing calculator — it never places real orders. Enter your account size, risk %, entry price, and stop price to get position size, leverage table, and R-multiple exit targets. Simulate logs a paper trade to the journal without touching a broker.
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14, marginBottom: 14 }}>
              <div style={{ borderLeft: "3px solid var(--amber)", paddingLeft: 12 }}>
                <div className="mono" style={{ fontSize: 12, fontWeight: 700, color: "var(--amber)", letterSpacing: "0.08em", marginBottom: 4 }}>FROM AN ASSET — TWO PATHS</div>
                <div style={{ fontSize: 13, color: "var(--ink-2)", lineHeight: 1.65 }}>
                  <strong style={{ color: "var(--ink)" }}>SIMULATE NOW</strong> — logs a $1,000 paper trade directly from AssetHub values (entry, ATR stop, 1.5R target). Fastest path. Use it when you've already validated the setup and just want a journal entry.<br/><br/>
                  <strong style={{ color: "var(--ink)" }}>OPEN RISK DESK</strong> — navigates to Risk Desk pre-filled with the current asset's price and ATR-derived stop. Adjust account size or risk % before confirming. Use it when you want to size carefully.
                </div>
              </div>
              <div style={{ borderLeft: "3px solid var(--cyan)", paddingLeft: 12 }}>
                <div className="mono" style={{ fontSize: 12, fontWeight: 700, color: "var(--cyan)", letterSpacing: "0.08em", marginBottom: 4 }}>STANDALONE — SEARCH BOX</div>
                <div style={{ fontSize: 13, color: "var(--ink-2)", lineHeight: 1.65 }}>
                  Open Risk Desk from the sidebar without an asset selected. Type any ticker (e.g. NVDA, BTC) and hit Enter — it fetches live price and stop from Core and auto-fills the calculator. Account size and risk % are preserved across searches, so you can compare position sizes across assets without re-entering your portfolio settings.
                </div>
              </div>
            </div>
            <div style={{ background: "var(--bg-3)", border: "1px solid var(--line)", padding: "10px 14px", marginBottom: 12 }}>
              <div className="mono" style={{ fontSize: 12, color: "var(--ink-3)", letterSpacing: "0.1em", marginBottom: 8 }}>SIMULATE MODE (from OPEN RISK DESK)</div>
              <div style={{ fontSize: 13, color: "var(--ink-2)", lineHeight: 1.75 }}>
                A cyan <strong style={{ color: "var(--cyan)" }}>◇ SIMULATION MODE · {"{SYM}"}</strong> banner appears at the top. At the bottom, a full-width <strong style={{ color: "var(--ink)" }}>◆ PAPER TRADE</strong> button (buy/sell color) posts to the Trade Journal using Risk Desk's current position size, entry, stop, and a computed 1.5R target. On success: "◆ PAPER TRADE LOGGED" → auto-navigates back to the asset view after 1.5s.
              </div>
            </div>
            <div className="mono" style={{ fontSize: 12, color: "var(--ink-4)", letterSpacing: "0.06em", lineHeight: 1.7 }}>
              EXECUTE button — visible but intentionally not wired to a broker. Clicking it shows a message: "Direct broker execution is not enabled. Use Simulate to log paper trades in the journal." This is a deliberate architectural decision — no live order execution in Banshee.  ·  SMC CONFLICTED checkbox halves position size when HTF and LTF structure disagree.
            </div>
          </div>
        </div>

        {/* SMC CONCEPTS GLOSSARY */}
        <div style={CARD}>
          <ManSectionHdr title="SMC CONCEPTS" accent="var(--ink-2)" sub="REFERENCE GLOSSARY" />
          <div style={{ padding: "14px 16px", display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0 32px" }}>
            <ManConcept name="SWING POINTS" accent="var(--ink-2)"
              encoding="▲ Orange triangle = swing high  ·  ▼ Blue triangle = swing low">
              5-candle fractal: a swing high is a candle whose high exceeds the 2 candles on each side. Foundation of all downstream structure — OBs, BOS, CHoCH, and inducement all derive from these pivots. The labels (HH, LH, HL, LL) tell you the structural sequence.
            </ManConcept>
            <ManConcept name="BOS — BREAK OF STRUCTURE" accent="var(--buy)"
              encoding="Green box (bull) or red box (bear) label at the break level">
              A prior swing point breached by a body close with ≥1.5× ATR displacement. Confirms trend direction. Bullish BOS = uptrend active. Bearish BOS = downtrend active. Displacement requirement filters slow drifts — only genuine institutional delivery qualifies.
            </ManConcept>
            <ManConcept name="CHoCH — CHANGE OF CHARACTER" accent="#69F0AE"
              encoding="Lighter green/red box — visually distinct from BOS">
              Protected level (last swing in the opposite direction) breached without displacement. First sign of a trend flip. CHoCH is a warning, not a signal — wait for follow-through BOS before switching bias. One CHoCH can be noise; two usually isn't.
            </ManConcept>
            <ManConcept name="ORDER BLOCK (OB)" accent="#42A5F5"
              encoding="▲ Deep blue box (bull)  ·  ▼ Deep crimson box (bear)">
              Last opposite-color candle before a displacement wave that contains an FVG. The candle where institutions placed their entries before the big move. Price returning here is price returning to the institutional footprint. Validity requires an FVG within 5 candles of the displacement.
            </ManConcept>
            <ManConcept name="OB STATUS LIFECYCLE" accent="var(--ink-3)"
              encoding="active → touched ◑ → degraded ⚠ → sapped / invalidated">
              {"Active: untouched. Touched ◑: wick entered, still valid. Degraded ⚠: body closed past 50% mean — partial defense failure, reduced conviction. Sapped: wick swept through distal boundary — hollow, skip. Invalidated: body closed through distal — destroyed, no longer on chart."}
            </ManConcept>
            <ManConcept name="FAIR VALUE GAP (FVG)" accent="#00BCD4"
              encoding="▲ Teal box (bull)  ·  ▼ Red box (bear)  ·  FVG▲/▼ tick marker at center">
              3-candle imbalance: candle 1's high and candle 3's low don't overlap (bullish), or candle 1's low and candle 3's high don't overlap (bearish). Price moved too fast for fair two-sided auction. Unmitigated FVGs act as price magnets — expect a return visit before continuation.
            </ManConcept>
            <ManConcept name="PREMIUM / DISCOUNT / OTE" accent="var(--ink-3)"
              encoding="Green background = discount  ·  Red = premium  ·  Amber lines = OTE (61–79%)  ·  Gray dashed = EQ">
              The dealing range spans from last swing high to last swing low. Midpoint = EQ (equilibrium). Smart money buys in discount, sells in premium. The OTE band (61.8–79% retracement of the dealing range) is where the best long pullback entries cluster — deep enough to be real, not so deep it breaks structure.
            </ManConcept>
            <ManConcept name="EQH / EQL — LIQUIDITY POOLS" accent="#FF1744"
              encoding="Red dashed line = EQH (sell stops above)  ·  Teal dashed line = EQL (buy stops below)">
              Two swings at nearly identical price levels. Retail traders park stop-losses just beyond these, thinking they're double-top resistance or double-bottom support. Institutions drive price through to harvest that liquidity, then reverse. EQH/EQL are trap detectors and exit targets — not entries.
            </ManConcept>
            <ManConcept name="INDUCEMENT" accent="var(--amber)"
              encoding="⌛ Amber OB border = trap set, waiting  ·  ⚡ Green border = trap fired, OB actionable">
              An EQH or EQL sitting between current price and an Order Block. The liquidity trap smart money must sweep on the way to the OB. The SMC golden rule: an OB without inducement in front of it may itself be the trap — retail orders placed there will get taken out. Wait for the sweep.
            </ManConcept>
            <ManConcept name="SESSION WEIGHTS" accent="var(--ink-3)"
              encoding="⚡ Silver Bullet badge (2×)  ·  ◈ Killzone badge (1.5×)  ·  · dot = low conviction (<1×)  ·  ★ = HTF confluence">
              {"ICT theory: institutional participation varies by session. Silver Bullet windows (03–04, 10–11, 14–15 EST) = 2× weight. London/NY Killzones (02–05, 07–10) = 1.5×. Asian range (20–00) = 0.5×. An OB formed or approached during a high-weight window has higher delivery probability."}
            </ManConcept>
          </div>
        </div>

        {/* GEO HARMONIC ARCS */}
        <div style={CARD}>
          <ManSectionHdr title="GEO HARMONIC ARCS" accent="var(--magenta)" sub="GH TAB" />
          <div style={{ padding: "14px 16px" }}>
            <div style={{ fontSize: 13, color: "var(--ink-2)", lineHeight: 1.7, marginBottom: 14 }}>
              Geometric circles drawn in log-price space, anchored to the absolute ATH and ATL (macro circles) and to ZigZag swing pivots (local circles, 3 window sizes). Where circles from different sources converge = a <strong style={{ color: "var(--ink)" }}>hot zone</strong> — a price level that independent geometric frameworks agree on.
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14, marginBottom: 14 }}>
              <div style={{ borderLeft: "3px solid #00BCD4", paddingLeft: 12 }}>
                <div className="mono" style={{ fontSize: 12, fontWeight: 700, color: "#00BCD4", letterSpacing: "0.08em", marginBottom: 4 }}>TEAL LINES — FLOOR ZONES</div>
                <div style={{ fontSize: 13, color: "var(--ink-2)", lineHeight: 1.65 }}>Demand-anchored circles originating from the absolute ATL. Geometric support levels — where price has historically found buyers in log-price geometry. Price approaching from above may react here.</div>
              </div>
              <div style={{ borderLeft: "3px solid #F44336", paddingLeft: 12 }}>
                <div className="mono" style={{ fontSize: 12, fontWeight: 700, color: "#F44336", letterSpacing: "0.08em", marginBottom: 4 }}>RED LINES — CEILING ZONES</div>
                <div style={{ fontSize: 13, color: "var(--ink-2)", lineHeight: 1.65 }}>Supply-anchored circles originating from the absolute ATH. Geometric resistance — where price has historically found sellers. Price approaching from below may stall or reverse here.</div>
              </div>
            </div>
            <div style={{ background: "var(--bg-3)", border: "1px solid var(--line)", padding: "10px 14px", marginBottom: 12 }}>
              <div className="mono" style={{ fontSize: 12, color: "var(--ink-3)", letterSpacing: "0.1em", marginBottom: 8 }}>HOW TO USE GH IN A WORKFLOW</div>
              <div style={{ fontSize: 13, color: "var(--ink-2)", lineHeight: 1.75 }}>
                <strong style={{ color: "var(--ink-3)" }}>1.</strong> Check the GH tab hot zones table — note any floor/ceiling levels within 3–5% of current price.<br/>
                <strong style={{ color: "var(--ink-3)" }}>2.</strong> Switch to the SMC tab. If a hot zone aligns with an OB or FVG, that's geometric confluence — conviction goes up.<br/>
                <strong style={{ color: "var(--ink-3)" }}>3.</strong> Use the GH tab's circle-coordinate table (center date/price + shared endpoint) to plot the levels by hand in TradingView with its native Fib Circle tool — anchor each circle on its High/Low row and drag the radius out to the Endpoint.
              </div>
            </div>
            <div className="mono" style={{ fontSize: 12, color: "var(--ink-4)", letterSpacing: "0.06em", lineHeight: 1.7 }}>
              6 Fibonacci levels per circle: 23.6% · 38.2% · 50% · 61.8% · 78.6% · 100%  ·  Hot zones = DBSCAN clusters where 2+ distinct source circles agree on a price level. The more source types agreeing (macro-macro &gt; macro-local &gt; local-local), the stronger the level.
            </div>
          </div>
        </div>

        {/* UNLEASHED PROMPT PROFILES */}
        <div style={CARD}>
          <ManSectionHdr title="UNLEASHED PROMPT PROFILES" accent="var(--sell)" sub="SETTINGS · UNLEASHED PROMPT PROFILES" />
          <div style={{ padding: "14px 16px" }}>
            <div style={{ fontSize: 13, color: "var(--ink-2)", lineHeight: 1.7, marginBottom: 14 }}>
              Prompt Profiles let you shape how Banshee's AI talks — but only inside Unleashed mode. Standard Banshee always runs the safe base prompt, which you cannot change here; that safety never goes away. You edit two independent surfaces: <strong style={{ color: "var(--ink)" }}>NEXUS</strong> (the synthesis — macro + micro + news) and <strong style={{ color: "var(--ink)" }}>SMC</strong> (market structure — order blocks, FVGs, BOS/CHoCH). SMC feeds Nexus, so an SMC edit propagates upward into the synthesis too. The news-injection guard (Banshee's defense against manipulative headlines) is always on and can't be edited away.
            </div>
            <div style={{ background: "var(--bg-3)", border: "1px solid var(--line)", padding: "10px 14px", marginBottom: 12 }}>
              <div className="mono" style={{ fontSize: 12, color: "var(--ink-3)", letterSpacing: "0.1em", marginBottom: 8 }}>TWO MODES PER SURFACE</div>
              <div style={{ fontSize: 13, color: "var(--ink-2)", lineHeight: 1.75 }}>
                <strong style={{ color: "var(--ink)" }}>Nudge (add on top)</strong> appends your text after the base prompt — safe, small, additive. <strong style={{ color: "var(--ink)" }}>Rewrite (replace)</strong> edits a copy of the base prompt that replaces it — more power, and it can change the output format. Switching a surface to Rewrite seeds the box with a copy of the base, so you're never staring at a blank editor (and <em>Reset to base copy</em> restores it). Each panel's <em>Show base prompt</em> toggle reveals the current base read-only — that panel is the canonical wording of what you're adding to.
              </div>
            </div>
            <div className="mono" style={{ fontSize: 12, color: "var(--ink-4)", letterSpacing: "0.06em", lineHeight: 1.7 }}>
              Settings → Unleashed Prompt Profiles. Save As to make your own profile, edit either surface, Set Active, then flip Unleashed ON — the RED frame names the live profile. The locked Default is your one-click undo: switch back to it anytime; it can never be edited or deleted. Keep the spirit of Unleashed: surface short-term possibilities and STATE THE RISK; never instruct an execution. The wilder the prompt, the more you should sanity-check the output.
            </div>
          </div>
        </div>

        {/* XABCD PATTERNS */}
        <div style={{ ...CARD, marginBottom: 20 }}>
          <ManSectionHdr title="XABCD HARMONIC PATTERNS" accent="var(--amber)" sub="GH TAB · XABCD SECTION" />
          <div style={{ padding: "14px 16px" }}>
            <div style={{ fontSize: 13, color: "var(--ink-2)", lineHeight: 1.7, marginBottom: 14 }}>
              Harmonic patterns identify high-probability turning points using Fibonacci ratios between 5 price pivots: X → A → B → C → D. The <strong style={{ color: "var(--ink)" }}>D point</strong> is the potential entry — the <strong style={{ color: "var(--ink)" }}>Potential Reversal Zone (PRZ)</strong>. All leg ratios must fall within tolerance for a valid pattern.
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 8, marginBottom: 14 }}>
              {XABCD_PATTERNS.map(([name, b, c, d]) => (
                <div key={name} style={{ background: "var(--bg-3)", border: "1px solid var(--line)", padding: "8px 10px" }}>
                  <div className="mono" style={{ fontSize: 12, fontWeight: 700, color: "var(--amber)", letterSpacing: "0.06em", marginBottom: 5 }}>{name}</div>
                  <div className="mono" style={{ fontSize: 12, color: "var(--ink-4)", lineHeight: 1.7 }}>
                    B: {b}<br/>C: {c}<br/>D: {d}
                  </div>
                </div>
              ))}
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
              <div style={{ borderLeft: "3px solid var(--ink-3)", paddingLeft: 12 }}>
                <div className="mono" style={{ fontSize: 12, color: "var(--ink-3)", letterSpacing: "0.08em", marginBottom: 5 }}>CHART SYMBOLS</div>
                <div style={{ fontSize: 13, color: "var(--ink-2)", lineHeight: 1.65 }}>
                  Solid lines = confirmed pattern (D leg complete). Dashed lines = forming (D not yet reached). Shaded band at D = the PRZ range where reversal is expected. X A B C D labels drawn on chart at each pivot.
                </div>
              </div>
              <div style={{ borderLeft: "3px solid var(--amber)", paddingLeft: 12 }}>
                <div className="mono" style={{ fontSize: 12, color: "var(--amber)", letterSpacing: "0.08em", marginBottom: 5 }}>CONFLUENCE RULE</div>
                <div style={{ fontSize: 13, color: "var(--ink-2)", lineHeight: 1.65 }}>
                  Standalone XABCD is lower conviction. Highest probability when the D PRZ overlaps an SMC OB, HTF reference level, or GH hot zone. Use XABCD to narrow the entry window within a zone — not as a replacement for structure analysis.
                </div>
              </div>
            </div>
          </div>
        </div>

      </div>
    </div>
  );
}

export default ManualPage;
