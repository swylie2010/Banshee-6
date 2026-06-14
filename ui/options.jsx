/* Banshee — Options "The Calm Room" (Phase 1, The Wheel)
 * Banshee's native chassis (monospace, uppercase micro-labels, bordered cards)
 * recolored mint. Scoped palette only — does not touch the rest of the app.
 * Font floor on this page is 12px (one above the app's 11 floor). */

const OPT_PALETTE = {
  mint: '#1F9D6E', mintDeep: '#147A55', mintSoft: '#D5EEE2', wall: '#E7F4EE',
  card: '#F4FBF7', bg2: '#DCF0E7', bg3: '#CDE8DC', ink: '#16352A', ink3: '#5C7A6D',
  ink4: '#7C9789', line: '#BCDFCF', amber: '#9A6A18', amberBg: '#F6EBCF', amberLine: '#E4CE94',
};

/* Quick plain-language glossary — shown on hover so a learner doesn't lose focus. */
const TERM_DEFS = {
  cash: "Cash-secured: you set aside the full cash to buy the shares if you're assigned, so you never borrow. The amount = strike × 100.",
  delta: "Delta: a quick read on the chance you'll be forced to buy the shares. The options chain lists it per contract; Banshee also computes it from price, strike, days left, and volatility. ~0.25 ≈ a 25% chance of assignment.",
  dte: "Days to expiry (DTE): calendar days until the contract expires. Banshee targets 35–45, where time-decay works hardest in your favor.",
  oi: "Open interest: how many of this exact contract are currently held across the market. Higher = easier to get in and out at a fair price. It comes straight from the options chain.",
  ivr: "IV rank: how rich this premium is versus the underlying's own recent volatility, 0–100. High = unusually pricey (often a known event looming). Banshee estimates it here, flagged 'est.'.",
  underlying: "Underlying: the fund or stock the option is written on. Banshee sticks to broad funds (SPY/QQQ/IWM/DIA) that can't gap violently on a single headline.",
  size: "Trade size: this trade's collateral as a share of your whole account. Banshee's rule: never more than 5% in one trade, so a single surprise can't sink you.",
  premium: "Premium: the cash the buyer pays you up front to take on the obligation. It's the contract's mid price × 100 shares.",
};

/* A jargon term with a dotted underline; hover shows its quick definition. */
function TermInfo({ termKey, label, style }) {
  const P = OPT_PALETTE;
  const [hov, setHov] = React.useState(false);
  const def = TERM_DEFS[termKey];
  if (!def) return <b style={style}>{label}</b>;
  return (
    <span style={{ position: 'relative', display: 'inline-block' }}
      onMouseEnter={() => setHov(true)} onMouseLeave={() => setHov(false)}>
      <b style={{ borderBottom: `1px dotted ${P.ink4}`, cursor: 'help', ...style }}>{label}</b>
      {hov && (
        <span style={{ position: 'absolute', top: '100%', left: 0, zIndex: 60, width: 250, marginTop: 5,
          background: P.card, color: P.ink, border: `1px solid ${P.mint}`, borderRadius: 8,
          padding: '9px 12px', fontSize: 12, lineHeight: 1.5, fontWeight: 400, textTransform: 'none',
          letterSpacing: 'normal', boxShadow: '0 6px 18px rgba(20,60,40,0.18)' }}>
          {def}
        </span>
      )}
    </span>
  );
}

/* Global "teach me" preference — default ON for a first-time user. */
function useTeachMode() {
  const [on, setOn] = React.useState(() => {
    const v = localStorage.getItem('banshee_options_teach');
    return v === null ? true : v === '1';
  });
  const set = React.useCallback((next) => {
    setOn(next);
    localStorage.setItem('banshee_options_teach', next ? '1' : '0');
  }, []);
  return [on, set];
}

/* The page-level toggle pill. */
function TeachToggle({ on, setOn }) {
  const P = OPT_PALETTE;
  return (
    <button onClick={() => setOn(!on)} style={{
      background: on ? P.mintSoft : 'transparent', color: on ? P.mintDeep : P.ink4,
      border: `1px solid ${on ? P.mint : P.line}`, borderRadius: 20, cursor: 'pointer',
      fontFamily: 'monospace', fontSize: 12, letterSpacing: '0.08em', textTransform: 'uppercase',
      fontWeight: 700, padding: '5px 13px' }}>
      {on ? '◆ TEACH ME · ON' : '○ TEACH ME · OFF'}
    </button>
  );
}

/* A collapsible teaching block. Hidden entirely when `teach` is off, unless the
   user has individually opened it. `alwaysShow` keeps it visible regardless
   (used for risk — the downside is never optional). */
/* A collapsible teaching block. Hidden (shown as a one-line opener) when `teach`
   is off, unless the user individually opened it. `alwaysShow` forces it visible
   regardless of the toggle (used for risk — the downside is never optional). */
function Teach({ teach, title, alwaysShow, children }) {
  const P = OPT_PALETTE;
  const [openOverride, setOpenOverride] = React.useState(null); // null = follow global
  const open = alwaysShow || (openOverride === null ? teach : openOverride);
  if (!open) {
    return (
      <button onClick={() => setOpenOverride(true)} style={{
        background: 'transparent', border: 'none', cursor: 'pointer', padding: '4px 0',
        fontFamily: 'monospace', fontSize: 12, letterSpacing: '0.1em', textTransform: 'uppercase',
        fontWeight: 700, color: P.mintDeep, display: 'block' }}>
        › {title}
      </button>
    );
  }
  return (
    <div style={{ borderLeft: `3px solid ${P.mint}`, background: P.mintSoft,
      borderRadius: '0 8px 8px 0', padding: '12px 15px', margin: '10px 0' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span style={{ fontSize: 12, letterSpacing: '0.12em', textTransform: 'uppercase',
          fontWeight: 700, color: P.mintDeep }}>◆ {title}</span>
        {!alwaysShow && (
          <button onClick={() => setOpenOverride(false)} title="Collapse" style={{
            background: 'transparent', border: 'none', cursor: 'pointer', color: P.ink4,
            fontFamily: 'monospace', fontSize: 12 }}>▾</button>
        )}
      </div>
      <div style={{ marginTop: 8, fontSize: 14, lineHeight: 1.65, color: '#234034' }}>{children}</div>
    </div>
  );
}

function OptWhy({ guardrails }) {
  const P = OPT_PALETTE;
  const [open, setOpen] = React.useState(false);
  if (!guardrails || !guardrails.length) return null;
  return (
    <div style={{ marginTop: 15, paddingTop: 12, borderTop: `1px solid ${P.line}` }}>
      <button onClick={() => setOpen(o => !o)} style={{
        background: 'transparent', border: 'none', cursor: 'pointer', padding: 0,
        fontFamily: 'monospace', fontSize: 12, letterSpacing: '0.12em', textTransform: 'uppercase',
        fontWeight: 700, color: P.mintDeep }}>
        {open ? '▾  WHY THIS ONE CLEARED THE RULES' : '›  SEE WHY THIS ONE CLEARED THE RULES'}
      </button>
      {open && (
        <div style={{ marginTop: 10, display: 'flex', flexDirection: 'column', gap: 8 }}>
          {guardrails.map(g => (
            <div key={g.key} style={{ display: 'flex', gap: 9, fontSize: 13, color: P.ink, lineHeight: 1.5 }}>
              <span style={{ color: g.passed ? P.mint : P.amber, flexShrink: 0 }}>{g.passed ? '✓' : '⚠'}</span>
              <span>{g.plain}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

/* shared mint button (primary action) */
function OptButton({ label, onClick, disabled }) {
  const P = OPT_PALETTE;
  return (
    <button onClick={onClick} disabled={disabled} style={{
      background: disabled ? P.bg3 : P.mint, color: disabled ? P.ink4 : '#fff',
      border: `1px solid ${disabled ? P.line : P.mintDeep}`, borderRadius: 7,
      cursor: disabled ? 'default' : 'pointer', padding: '9px 16px',
      fontFamily: 'monospace', fontSize: 12, letterSpacing: '0.1em', textTransform: 'uppercase',
      fontWeight: 700 }}>
      {label}
    </button>
  );
}

/* inline error line — actionable, never blank (see feedback_actionable_errors) */
function OptError({ msg }) {
  const P = OPT_PALETTE;
  if (!msg) return null;
  return (
    <div style={{ marginTop: 10, background: P.amberBg, border: `1px solid ${P.amberLine}`,
      borderRadius: 7, padding: '9px 13px', fontSize: 13, color: P.amber, lineHeight: 1.5 }}>
      ⚠ {msg}
    </div>
  );
}

/* Static "you are here" Wheel map — both branches visible before committing. */
function WheelJourney({ underlying, dte }) {
  const P = OPT_PALETTE;
  const node = (text, here) => (
    <span style={{ border: `1px solid ${here ? P.mint : P.line}`, borderRadius: 20,
      padding: '5px 11px', fontSize: 12, whiteSpace: 'nowrap',
      background: here ? P.mintSoft : P.card, color: here ? P.ink : P.ink3,
      fontWeight: here ? 700 : 400 }}>{text}</span>
  );
  const arrow = <span style={{ color: P.ink4 }}>→</span>;
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6, fontSize: 12 }}>
      <div style={{ display: 'flex', gap: 6, alignItems: 'center', flexWrap: 'wrap' }}>
        {node(`① Sell put, collect premium`, true)} {arrow} {node(`in ${dte} days…`)}
      </div>
      <div style={{ display: 'flex', gap: 6, alignItems: 'center', flexWrap: 'wrap', paddingLeft: 18 }}>
        <span style={{ color: P.mintDeep, fontSize: 11 }}>└ stays above ▸</span>
        {node('keep the premium')} <span style={{ color: P.ink4 }}>↺ start again</span>
      </div>
      <div style={{ display: 'flex', gap: 6, alignItems: 'center', flexWrap: 'wrap', paddingLeft: 18 }}>
        <span style={{ color: P.amber, fontSize: 11 }}>└ drops below ▸</span>
        {node(`own 100 ${underlying} shares`)} {arrow} {node('② sell a call')} {arrow}
        <span style={{ color: P.ink4 }}>called away ↺</span>
      </div>
    </div>
  );
}

function OptCard({ data, teach, onRunWheel, onSeeWheels, onPaperTrade, runError }) {
  const P = OPT_PALETTE;
  const c = data.candidate, t = data.translation;
  const premium = Math.round(c.mid * 100);
  const [showPaperConfirm, setShowPaperConfirm] = React.useState(false);
  const [paperBusy, setPaperBusy] = React.useState(false);
  const [paperErr, setPaperErr] = React.useState(null);

  const handlePaperConfirm = async () => {
    setPaperBusy(true); setPaperErr(null);
    try {
      const w = await window.API.createPaperWheel({
        candidate_snapshot: c,
        underlying: c.underlying,
        name: c.underlying + ' Paper Wheel',
      });
      setShowPaperConfirm(false);
      onPaperTrade(w.id);
    } catch (e) {
      setPaperErr(e?.detail || e?.error || "Couldn't start paper trade — try again.");
    }
    setPaperBusy(false);
  };
  const num = (label, value, termKey) => (
    <div style={{ padding: '12px 20px 4px 0' }}>
      <div style={{ fontSize: 12, letterSpacing: '0.14em', textTransform: 'uppercase', fontWeight: 700, color: P.ink4 }}>
        {termKey ? <TermInfo termKey={termKey} label={label} style={{ fontSize: 12, letterSpacing: '0.14em', textTransform: 'uppercase', fontWeight: 700, color: P.ink4 }} /> : label}
      </div>
      <div style={{ fontSize: 19, fontWeight: 700, marginTop: 3, color: P.ink }}>{value}</div>
    </div>
  );
  return (
    <div style={{ background: P.card, border: `1px solid ${P.line}`, borderRadius: 10, padding: '18px 20px', maxWidth: 620 }}>
      <span style={{ display: 'inline-block', fontSize: 12, letterSpacing: '0.14em', textTransform: 'uppercase',
        fontWeight: 700, color: P.mintDeep, border: `1px solid ${P.mint}`, borderRadius: 5, padding: '3px 9px' }}>
        ◆ CASH-SECURED PUT · {c.underlying}
      </span>
      <div style={{ fontSize: 18, fontWeight: 700, margin: '13px 0 12px', color: P.ink }}>
        Get paid ${premium.toLocaleString()} now to promise to buy {c.underlying} at ${c.strike.toLocaleString()} — and here's the obligation that comes with it.
      </div>
      <div style={{ fontSize: 12, letterSpacing: '0.14em', textTransform: 'uppercase', fontWeight: 700, color: P.ink4, marginBottom: 6 }}>In plain English</div>
      <div style={{ fontSize: 14, lineHeight: 1.7, color: '#234034', background: P.mintSoft,
        borderLeft: `3px solid ${P.mint}`, padding: '12px 15px', borderRadius: '0 6px 6px 0' }}>{t.plain_english}</div>
      <div style={{ display: 'flex', flexWrap: 'wrap', margin: '16px 0 2px', borderTop: `1px solid ${P.line}` }}>
        {num('You collect', `$${premium.toLocaleString()}`, 'premium')}
        {num('Cash set aside', `$${c.collateral.toLocaleString()}`)}
        {num('Breakeven', `$${c.breakeven.toLocaleString()}`)}
        {num('Odds you keep it', `${Math.round(c.prob_keep * 100)}%`)}
        {num('Days', `${c.dte}`)}
        {num('Safety', `✓ Δ${Math.abs(c.delta).toFixed(2)}${c.ivr_estimate != null ? ` · IVR ${Math.round(c.ivr_estimate)} est.` : ''}`)}
      </div>
      <Teach teach={teach} title="What 'cash set aside' really means">
        That ${c.collateral.toLocaleString()} isn't a fee — it's the <b>whole price of the shares you're promising to buy</b>.
        You keep it in cash, ready. That cash <b>is</b> the obligation; the 5% rule just says it can't be more than a small
        slice of your account, so one surprise can't sink you.
      </Teach>

      <div style={{ marginTop: 14 }}>
        <div style={{ fontSize: 12, letterSpacing: '0.14em', textTransform: 'uppercase', fontWeight: 700, color: P.ink4, marginBottom: 8 }}>The whole journey — you are here</div>
        <WheelJourney underlying={c.underlying} dte={c.dte} />
      </div>

      <div style={{ marginTop: 14, background: P.amberBg, border: `1px solid ${P.amberLine}`,
        borderRadius: 8, padding: '12px 15px' }}>
        <div style={{ fontSize: 12, letterSpacing: '0.14em', textTransform: 'uppercase', fontWeight: 700, color: P.amber }}>What could go wrong — the honest worst case</div>
        <div style={{ fontSize: 13, color: '#6b5118', lineHeight: 1.7, marginTop: 5 }}>
          If {c.underlying} falls hard, you're obligated to buy 100 shares at ${c.strike.toLocaleString()} = <b>${c.collateral.toLocaleString()}</b> committed,
          possibly worth less than you paid. You'd then sell calls to claw it back — but that cash is tied up and the
          position can sit underwater for a while. This is the real risk you're paid ${premium.toLocaleString()} to take.
        </div>
      </div>
      {c.sizing && (
        <div style={{ fontSize: 13, color: c.sizing.within_5pct ? P.mintDeep : P.amber, marginTop: 6 }}>
          ≈ {c.sizing.pct}% of your ${c.sizing.account_size.toLocaleString()} account {c.sizing.within_5pct ? '✓' : '— above the 5% guideline'}
        </div>
      )}
      <div style={{ marginTop: 14, fontSize: 13, color: P.ink3, lineHeight: 1.6, display: 'flex', gap: 8 }}>
        <span style={{ color: P.mint }}>●</span><span>{t.guidance}</span>
      </div>
      <OptWhy guardrails={data.guardrails} />
      <div style={{ marginTop: 16, paddingTop: 14, borderTop: `1px solid ${P.line}`, display: 'flex', flexWrap: 'wrap', gap: 14, alignItems: 'center' }}>
        <OptButton label="RUN THIS AS A SIMULATED WHEEL →" onClick={() => onRunWheel(c)} />
        <OptButton label="PAPER TRADE THIS →" onClick={() => { setShowPaperConfirm(true); setPaperErr(null); }} />
        <button onClick={onSeeWheels} style={{
          background: 'transparent', border: 'none', cursor: 'pointer', padding: 0,
          fontFamily: 'monospace', fontSize: 12, letterSpacing: '0.12em', textTransform: 'uppercase',
          fontWeight: 700, color: P.mintDeep }}>
          MY SIMULATED WHEELS →
        </button>
      </div>
      <OptError msg={runError} />
      {showPaperConfirm && (
        <PaperTradeConfirm
          candidate={c}
          onConfirm={handlePaperConfirm}
          onCancel={() => { setShowPaperConfirm(false); setPaperErr(null); }}
          busy={paperBusy}
          err={paperErr}
        />
      )}
    </div>
  );
}

/* currency formatter — null-safe; returns null so callers can omit a row */
function optMoney(v) {
  if (v == null || isNaN(v)) return null;
  const sign = v < 0 ? '-' : '';
  return `${sign}$${Math.abs(v).toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
}

/* Displays the outcome of a single deterministic scenario run. */
function ScenarioCard({ run, label }) {
  const P = OPT_PALETTE;
  if (!run || run.error) return (
    <div style={{ background: P.amberBg, border: `1px solid ${P.amberLine}`, borderRadius: 8,
      padding: '10px 13px', fontSize: 13, color: P.amber }}>⚠ {run?.error || 'Scenario unavailable.'}</div>
  );
  const pnlColor = run.pnl >= 0 ? P.mint : P.amber;
  const outcomeLabel = { expired_worthless: 'EXPIRED — KEPT PREMIUM', assigned: 'ASSIGNED — OWN SHARES',
    margin_call: 'MARGIN CALL', error: 'ERROR' }[run.outcome] || run.outcome?.toUpperCase();
  return (
    <div style={{ background: P.card, border: `1px solid ${run.pnl >= 0 ? P.mint : P.amberLine}`,
      borderRadius: 8, padding: '12px 14px', flex: 1 }}>
      {label && <div style={{ fontSize: 11, letterSpacing: '0.12em', textTransform: 'uppercase',
        fontWeight: 700, color: P.ink4, marginBottom: 5 }}>{label}</div>}
      <div style={{ fontSize: 12, fontWeight: 700, color: pnlColor, marginBottom: 6 }}>{outcomeLabel}</div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px 22px', fontSize: 13 }}>
        <span><span style={{ color: P.ink4 }}>P&L </span><b style={{ color: pnlColor }}>{run.pnl >= 0 ? '+' : ''}${Math.round(run.pnl).toLocaleString()}</b></span>
        <span><span style={{ color: P.ink4 }}>Premium </span>${Math.round(run.premium_collected || 0).toLocaleString()}</span>
        <span><span style={{ color: P.ink4 }}>Cash tied up </span>${Math.round(run.cash_tied_up || 0).toLocaleString()}</span>
        {run.net_cost_basis != null && <span><span style={{ color: P.ink4 }}>Cost basis </span>${run.net_cost_basis.toFixed(2)}/sh</span>}
        {run.margin_required != null && <span><span style={{ color: P.amber }}>Margin posted </span>${Math.round(run.margin_required).toLocaleString()}</span>}
      </div>
      {run.plain && <div style={{ marginTop: 7, fontSize: 12, color: P.ink3, lineHeight: 1.5 }}>{run.plain}</div>}
    </div>
  );
}

/* Amber AI narration block with a load button. */
function AiNarration({ label, fetchFn, cacheKey }) {
  const P = OPT_PALETTE;
  const [text, setText] = React.useState(null);
  const [busy, setBusy] = React.useState(false);

  React.useEffect(() => { setText(null); }, [cacheKey]);

  const load = async () => {
    setBusy(true);
    const r = await fetchFn();
    setText(r?.text || 'Narration unavailable.');
    setBusy(false);
  };

  if (text) return (
    <div style={{ background: P.amberBg, border: `1px solid ${P.amberLine}`, borderRadius: 8,
      padding: '11px 14px', fontSize: 13, color: '#6b5118', lineHeight: 1.65, marginTop: 10 }}>
      <div style={{ fontSize: 11, letterSpacing: '0.12em', textTransform: 'uppercase', fontWeight: 700,
        color: P.amber, marginBottom: 5 }}>◆ {label}</div>
      {text}
    </div>
  );
  return (
    <button onClick={load} disabled={busy} style={{
      marginTop: 10, background: busy ? P.amberBg : 'transparent',
      border: `1px solid ${P.amberLine}`, borderRadius: 6, cursor: busy ? 'default' : 'pointer',
      fontFamily: 'monospace', fontSize: 12, letterSpacing: '0.1em', textTransform: 'uppercase',
      fontWeight: 700, color: P.amber, padding: '6px 13px' }}>
      {busy ? '◇ ASKING THE AI…' : `◆ ${label} →`}
    </button>
  );
}

/* Learning lab panel shown after a wheel cycle completes (state==CASH, cycles>0).
   Lets the user: get an AI recap, try different numbers, compare two runs. */
function WheelRecapPanel({ wheel, st }) {
  const P = OPT_PALETTE;
  const snap = wheel.candidate_snapshot || {};
  const [termPrice, setTermPrice] = React.useState('');
  const [altSpec, setAltSpec] = React.useState({
    strike: snap.strike || '', mid: snap.mid || '', cash_backed: true });
  React.useEffect(() => {
    const s = wheel.candidate_snapshot || {};
    setAltSpec({ strike: s.strike || '', mid: s.mid || '', cash_backed: true });
  }, [wheel.id]);
  const [runA, setRunA] = React.useState(null);
  const [runB, setRunB] = React.useState(null);
  const [busy, setBusy] = React.useState(false);
  const [err, setErr] = React.useState(null);

  const lab = { fontSize: 12, letterSpacing: '0.14em', textTransform: 'uppercase', fontWeight: 700 };
  const inp = { fontFamily: 'monospace', fontSize: 13, padding: '5px 8px', background: P.card,
    color: P.ink, border: `1px solid ${P.line}`, borderRadius: 6 };

  const runOriginal = async () => {
    const price = parseFloat(termPrice);
    if (!snap.strike || !snap.mid || isNaN(price)) {
      setErr('Enter a terminal price to run the scenario.'); return;
    }
    setBusy(true); setErr(null);
    const specA = { strike: parseFloat(snap.strike), mid: parseFloat(snap.mid),
                    cash_backed: true, underlying: wheel.underlying || 'SPY' };
    const r = await window.API.runScenario(specA, price);
    if (r.error) setErr(r.error); else setRunA(r);
    setBusy(false);
  };

  const runAlt = async () => {
    const price = parseFloat(termPrice);
    if (isNaN(price) || !altSpec.strike || !altSpec.mid) {
      setErr('Fill in all fields to run the comparison.'); return;
    }
    setBusy(true); setErr(null);
    const specB = { strike: parseFloat(altSpec.strike), mid: parseFloat(altSpec.mid),
                    cash_backed: altSpec.cash_backed, underlying: wheel.underlying || 'SPY' };
    const r = await window.API.runScenario(specB, price);
    if (r.error) setErr(r.error); else setRunB(r);
    setBusy(false);
  };

  return (
    <div style={{ marginTop: 24, borderTop: `2px solid ${P.mint}`, paddingTop: 16 }}>
      <div style={{ ...lab, color: P.mintDeep, marginBottom: 4 }}>◆ LEARNING LAB — WHAT IF?</div>
      <div style={{ fontSize: 13, color: P.ink3, lineHeight: 1.6, marginBottom: 12 }}>
        Enter the terminal price (where the underlying actually was at expiry) to see the scenario.
        Then try different numbers and compare.
      </div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, alignItems: 'flex-end', marginBottom: 12 }}>
        <div>
          <div style={{ ...lab, color: P.ink4, marginBottom: 4 }}>Terminal price at expiry</div>
          <input value={termPrice} placeholder="e.g. 476"
            onChange={e => setTermPrice(e.target.value.replace(/[^0-9.]/g, ''))}
            style={{ ...inp, width: 100 }} />
        </div>
        <OptButton label={busy ? 'RUNNING…' : 'RUN ORIGINAL →'} disabled={busy} onClick={runOriginal} />
      </div>
      <OptError msg={err} />

      {runA && (
        <>
          <ScenarioCard run={runA} label="Original — what your wheel would have done" />
          <AiNarration label="AI RECAP" fetchFn={() => window.API.learnRecap(runA)} cacheKey={runA?.outcome + runA?.pnl} />

          <div style={{ marginTop: 18, borderTop: `1px solid ${P.line}`, paddingTop: 14 }}>
            <div style={{ ...lab, color: P.ink4, marginBottom: 8 }}>Try with different numbers</div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, alignItems: 'flex-end' }}>
              <div>
                <div style={{ ...lab, color: P.ink4, marginBottom: 4, fontSize: 11 }}>Strike</div>
                <input value={altSpec.strike} onChange={e => setAltSpec({ ...altSpec, strike: e.target.value })}
                  style={{ ...inp, width: 80 }} />
              </div>
              <div>
                <div style={{ ...lab, color: P.ink4, marginBottom: 4, fontSize: 11 }}>Premium (mid)</div>
                <input value={altSpec.mid} onChange={e => setAltSpec({ ...altSpec, mid: e.target.value })}
                  style={{ ...inp, width: 70 }} />
              </div>
              <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, color: P.ink }}>
                <input type="checkbox" checked={altSpec.cash_backed}
                  onChange={e => setAltSpec({ ...altSpec, cash_backed: e.target.checked })} />
                cash-backed
              </label>
              <OptButton label={busy ? 'RUNNING…' : 'COMPARE →'} disabled={busy} onClick={runAlt} />
            </div>
          </div>

          {runB && (
            <div style={{ marginTop: 12 }}>
              <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
                <ScenarioCard run={runA} label="Original" />
                <ScenarioCard run={runB} label="Your variant" />
              </div>
              <AiNarration label="AI COMPARE"
                fetchFn={() => window.API.learnCompare(runA, runB)} cacheKey={runA?.pnl + '|' + runB?.pnl} />
            </div>
          )}
        </>
      )}
    </div>
  );
}

/* ── Simulated Wheel: list view ───────────────────────────────────────────── */
function WheelList({ onOpened, onBack }) {
  const P = OPT_PALETTE;
  const [rows, setRows] = React.useState(null);   // null = loading
  const [err, setErr] = React.useState(null);

  const refresh = React.useCallback(() => {
    window.API.listWheels().then(r => {
      if (r && r.error) { setErr(r.error); setRows([]); }
      else { setErr(null); setRows(Array.isArray(r) ? r : (r.wheels || [])); }
    });
  }, []);
  React.useEffect(() => { refresh(); }, [refresh]);

  const lab = { fontSize: 12, letterSpacing: '0.14em', textTransform: 'uppercase', fontWeight: 700 };
  const del = async (e, id) => {
    e.stopPropagation();
    const r = await window.API.deleteWheel(id);
    if (r && r.error) setErr(r.error); else refresh();
  };
  const open = async (id) => {
    setErr("");
    const w = await window.API.getWheel(id);
    if (w && !w.error) onOpened(w);
    else setErr((w && w.error) || "Could not open that wheel — try again.");
  };

  return (
    <div>
      <button onClick={onBack} style={{ background: 'transparent', border: 'none', cursor: 'pointer', padding: 0,
        fontFamily: 'monospace', fontSize: 13, letterSpacing: '0.12em', textTransform: 'uppercase', color: '#FF6D00', fontWeight: 700, marginBottom: 16 }}>← BACK</button>
      <div style={{ ...lab, fontSize: 12, letterSpacing: '0.18em', color: P.mintDeep }}>◆ MY SIMULATED WHEELS</div>
      <div style={{ fontSize: 23, fontWeight: 700, margin: '7px 0 16px' }}>Your practice wheels</div>
      <OptError msg={err} />
      {rows === null && <div style={{ fontSize: 14, color: P.ink3, letterSpacing: '0.1em', marginTop: 12 }}>◇ LOADING…</div>}
      {rows !== null && rows.length === 0 && (
        <div style={{ marginTop: 12, fontSize: 14, color: P.ink3, lineHeight: 1.6 }}>
          No simulated wheels yet — start one from a candidate.
        </div>
      )}
      {rows !== null && rows.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginTop: 12, maxWidth: 700 }}>
          {rows.map(w => {
            const st = w.state || {};
            const tot = st.totals || {};
            return (
              <div key={w.id} onClick={() => open(w.id)} style={{
                background: P.card, border: `1px solid ${P.line}`, borderRadius: 9, padding: '13px 16px',
                cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 16 }}>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 15, fontWeight: 700, color: P.ink }}>{w.underlying || w.name || w.id}</div>
                  <div style={{ ...lab, fontSize: 12, color: P.ink4, marginTop: 3 }}>
                    {(st.state || '—')} · {tot.cycles_completed || 0} CYCLES · {optMoney(tot.premium_collected) || '$0'} PREMIUM
                  </div>
                </div>
                <button onClick={(e) => del(e, w.id)} title="Delete this wheel" style={{
                  background: 'transparent', border: `1px solid ${P.line}`, borderRadius: 6, cursor: 'pointer',
                  color: P.amber, fontFamily: 'monospace', fontSize: 12, padding: '4px 9px', flexShrink: 0 }}>
                  DELETE
                </button>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

/* ── Simulated Wheel: tracker view ────────────────────────────────────────── */
function WheelTracker({ wheel, setWheel, onBack }) {
  const P = OPT_PALETTE;
  const [err, setErr] = React.useState(null);
  const [busy, setBusy] = React.useState(false);
  const [expiryPrice, setExpiryPrice] = React.useState('');

  const st = wheel.state || {};
  const nm = st.next_move || {};
  const lab = { fontSize: 12, letterSpacing: '0.14em', textTransform: 'uppercase', fontWeight: 700 };

  const post = async (event) => {
    setBusy(true); setErr(null);
    const r = await window.API.postWheelEvent(wheel.id, event);
    setBusy(false);
    if (r && r.error) setErr(r.error);
    else { setWheel(r); setExpiryPrice(''); }
  };

  /* FSM strip */
  const chips = [
    { key: 'CASH', label: 'CASH' },
    { key: 'CSP', label: 'CSP' },
    { key: 'SHARES', label: 'SHARES' },
    { key: 'CC', label: 'CC' },
  ];
  const activeChip = st.state === 'CSP_OPEN' ? 'CSP' : st.state === 'CC_OPEN' ? 'CC' : st.state;

  /* totals row */
  const tot = st.totals || {};
  const totalCells = [
    ['Premium collected', optMoney(tot.premium_collected) || '$0'],
    ['Net cost basis', optMoney(tot.net_cost_basis)],   // omitted if null
    ['Realized P/L', optMoney(tot.realized_pnl) || '$0'],
    ['Cycles', String(tot.cycles_completed || 0)],
  ].filter(([, v]) => v != null);

  /* action area — switch on next_move.action */
  const cand = wheel.candidate_snapshot || {};
  const pend = st.pending_decision || {};
  const pos = st.position || {};
  const scc = wheel.suggested_cc || {};

  let actionArea = null;
  if (nm.action === 'SELL_CSP') {
    actionArea = (
      <OptButton label="SELL THE CASH-SECURED PUT" disabled={busy} onClick={() => post({
        type: 'SOLD_CSP', strike: cand.strike, expiry: cand.expiry, dte: cand.dte, mid: cand.mid, delta: cand.delta,
      })} />
    );
  } else if (nm.action === 'SELL_CC') {
    actionArea = (
      <div>
        {scc.plain && <div style={{ fontSize: 14, lineHeight: 1.7, color: '#234034', background: P.mintSoft,
          borderLeft: `3px solid ${P.mint}`, padding: '12px 15px', borderRadius: '0 6px 6px 0', marginBottom: 12 }}>{scc.plain}</div>}
        {scc.strike
          ? <OptButton label="SELL THE COVERED CALL" disabled={busy} onClick={() => post({
              type: 'SOLD_CC', strike: scc.strike, mid: scc.mid, dte: scc.dte, expiry: '',
            })} />
          : <OptError msg="Couldn't estimate a covered call right now — try again in a moment." />}
      </div>
    );
  } else if (nm.action === 'CHECKPOINT') {
    actionArea = (
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12 }}>
        {(pend.options || []).map(opt => (
          <OptButton key={opt.event} label={opt.label} disabled={busy} onClick={() => post({
            type: opt.event, leg: pend.leg, est_close_cost: pend.est_close_cost,
          })} />
        ))}
      </div>
    );
  } else if (nm.action === 'RESOLVE_EXPIRY') {
    const resolve = () => {
      const price = parseFloat(expiryPrice);
      if (isNaN(price)) { setErr('Enter a numeric price at expiry to resolve.'); return; }
      const leg = pos.leg;
      const strike = pos.strike;
      let event;
      if (leg === 'csp') {
        event = price >= strike
          ? { type: 'EXPIRED_WORTHLESS', leg: 'csp', expiry_price: price }
          : { type: 'ASSIGNED', strike, expiry_price: price };
      } else {
        event = price <= strike
          ? { type: 'EXPIRED_WORTHLESS', leg: 'cc', expiry_price: price }
          : { type: 'CALLED_AWAY', strike, expiry_price: price };
      }
      post(event);
    };
    actionArea = (
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, alignItems: 'center' }}>
        <label style={{ ...lab, color: P.ink4 }}>Price at expiry</label>
        <input value={expiryPrice} placeholder="e.g. 95"
          onChange={e => setExpiryPrice(e.target.value.replace(/[^0-9.]/g, ''))}
          style={{ fontFamily: 'monospace', fontSize: 13, padding: '7px 9px', width: 110,
            background: P.card, color: P.ink, border: `1px solid ${P.line}`, borderRadius: 6 }} />
        <OptButton label="RESOLVE" disabled={busy} onClick={resolve} />
      </div>
    );
  }

  return (
    <div style={{ maxWidth: 720 }}>
      <button onClick={onBack} style={{ background: 'transparent', border: 'none', cursor: 'pointer', padding: 0,
        fontFamily: 'monospace', fontSize: 13, letterSpacing: '0.12em', textTransform: 'uppercase', color: '#FF6D00', fontWeight: 700, marginBottom: 16 }}>← BACK</button>
      <div style={{ ...lab, fontSize: 12, letterSpacing: '0.18em', color: P.mintDeep }}>◆ SIMULATED WHEEL · {wheel.underlying || wheel.name}</div>

      {/* FSM strip */}
      <div style={{ display: 'flex', gap: 6, margin: '14px 0 18px' }}>
        {chips.map((ch, i) => {
          const on = ch.key === activeChip;
          return (
            <React.Fragment key={ch.key}>
              <span style={{ ...lab, fontSize: 12, padding: '6px 12px', borderRadius: 6,
                background: on ? P.mint : P.bg2, color: on ? '#fff' : P.ink4,
                border: `1px solid ${on ? P.mintDeep : P.line}` }}>{ch.label}</span>
              {i < chips.length - 1 && <span style={{ color: P.ink4, alignSelf: 'center' }}>·</span>}
            </React.Fragment>
          );
        })}
      </div>

      {/* YOUR NEXT MOVE */}
      <div style={{ background: P.card, border: `1px solid ${P.line}`, borderRadius: 10, padding: '16px 18px' }}>
        <div style={{ ...lab, fontSize: 12, color: P.ink4 }}>Your next move</div>
        <div style={{ fontSize: 19, fontWeight: 700, margin: '6px 0 4px', color: P.ink }}>{nm.label || '—'}</div>
        {nm.plain && <div style={{ fontSize: 14, color: P.ink3, lineHeight: 1.65 }}>{nm.plain}</div>}
        <div style={{ marginTop: 14 }}>{actionArea}</div>
        <OptError msg={err} />
      </div>

      {/* Totals row */}
      <div style={{ display: 'flex', flexWrap: 'wrap', marginTop: 16, borderTop: `1px solid ${P.line}` }}>
        {totalCells.map(([label, value]) => (
          <div key={label} style={{ padding: '12px 24px 4px 0' }}>
            <div style={{ ...lab, fontSize: 12, color: P.ink4 }}>{label}</div>
            <div style={{ fontSize: 19, fontWeight: 700, marginTop: 3, color: P.ink }}>{value}</div>
          </div>
        ))}
      </div>

      {/* History */}
      {st.history && st.history.length > 0 && (
        <div style={{ marginTop: 20 }}>
          <div style={{ ...lab, fontSize: 12, color: P.ink4, marginBottom: 8 }}>History</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 7 }}>
            {st.history.map((h, i) => (
              <div key={i} style={{ display: 'flex', gap: 9, fontSize: 13, color: P.ink, lineHeight: 1.5 }}>
                <span style={{ color: P.mint, flexShrink: 0 }}>●</span><span>{h}</span>
              </div>
            ))}
          </div>
        </div>
      )}
      {/* Learning lab — appears after at least one cycle completes */}
      {st.totals && st.totals.cycles_completed > 0 && st.state === 'CASH' && (
        <WheelRecapPanel wheel={wheel} st={st} />
      )}
    </div>
  );
}

/* ── Paper Wheel helpers ──────────────────────────────────────────────────── */

function _alertReason(r) {
  if (r === "order_pending") return "order expired or canceled — resubmit?";
  if (r === "checkpoint_due") return "≤21 DTE — time to evaluate";
  if (r === "expiry_due") return "expiry today — take action";
  if (r === "expired") return "position closed — review outcome";
  return r || "needs attention";
}

/* Alert strip — polls /paper-wheels/alerts every 60 s; shown above candidate card. */
function PaperAlertStrip({ onGoToWheel }) {
  const P = OPT_PALETTE;
  const [alerts, setAlerts] = React.useState([]);
  React.useEffect(() => {
    const load = () => window.API.getPaperWheelAlerts().then(d => setAlerts(Array.isArray(d) ? d : (d.alerts || []))).catch(() => {});
    load();
    const t = setInterval(load, 60000);
    return () => clearInterval(t);
  }, []);
  if (!alerts.length) return null;
  return (
    <div style={{ background: 'var(--sell, #E05252)', color: '#fff', padding: '8px 16px',
                  marginBottom: 12, borderRadius: 4, fontSize: 12 }}>
      {alerts.map(w => (
        <div key={w.id} style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <span>{w.underlying} paper wheel — {_alertReason(w.attention_reason)}</span>
          <button onClick={() => onGoToWheel(w.id)}
                  style={{ background: 'none', border: '1px solid #fff',
                           color: '#fff', cursor: 'pointer', padding: '1px 8px',
                           borderRadius: 3, fontSize: 11 }}>
            GO TO WHEEL →
          </button>
        </div>
      ))}
    </div>
  );
}

/* Paper track record + locked live-mode teaser. Reads wheels already fetched by PaperWheelList. */
function LiveGateTeaser({ wheels, loading }) {
  const P = OPT_PALETTE;
  const [livePanel, setLivePanel] = React.useState(false);
  if (loading || !wheels) return null;

  const totalCycles = wheels.reduce((s, w) => s + ((w.state?.totals?.cycles_completed) || 0), 0);
  const netPnl      = wheels.reduce((s, w) => s + ((w.state?.totals?.realized_pnl)      || 0), 0);
  const active      = wheels.filter(w => w.state?.state !== 'CASH').length;

  const pnlColor = netPnl > 0 ? P.mint : netPnl < 0 ? P.amber : P.ink3;
  const pnlStr   = netPnl === 0 ? '—' : `${netPnl >= 0 ? '+' : ''}$${Math.abs(netPnl).toFixed(2)}`;

  const tile = (label, value, color) =>
    React.createElement('div', {
      key: label,
      style: {
        flex: 1, background: P.bg2, border: `1px solid ${P.line}`,
        borderRadius: 6, padding: '10px 14px',
      },
    },
      React.createElement('div', {
        style: { fontSize: 9, letterSpacing: '0.16em', color: P.ink3, marginBottom: 4,
                 textTransform: 'uppercase' },
      }, label),
      React.createElement('div', {
        style: { fontSize: 18, fontWeight: 700, color },
      }, value),
    );

  return React.createElement('div', { style: { marginTop: 28 } },
    React.createElement('div', {
      style: { fontSize: 10, letterSpacing: '0.16em', textTransform: 'uppercase',
               color: P.ink3, marginBottom: 10 },
    }, 'PAPER TRACK RECORD'),
    React.createElement('div', { style: { display: 'flex', gap: 10, marginBottom: 16 } },
      tile('CYCLES',  totalCycles, P.ink),
      tile('NET P&L', pnlStr,      pnlColor),
      tile('ACTIVE',  active,      P.ink),
    ),
    React.createElement('div', {
      onClick: () => setLivePanel(true),
      style: {
        background: P.bg2, border: `1px solid ${P.line}`, borderRadius: 6,
        padding: '12px 16px', cursor: 'pointer',
      },
    },
      React.createElement('div', {
        style: { fontSize: 11, fontWeight: 700, color: P.ink2, marginBottom: 5,
                 letterSpacing: '0.08em', textTransform: 'uppercase' },
      }, '◈ LIVE MODE'),
      React.createElement('div', {
        style: { fontSize: 11, color: P.ink3, lineHeight: 1.6 },
      }, 'Ready to trade with real capital? Tap to learn more.'),
    ),
    livePanel && React.createElement('div', {
      style: {
        marginTop: 10, background: P.bg2, border: `1px solid ${P.line}`,
        borderRadius: 6, padding: '14px 16px',
      },
    },
      React.createElement('div', { style: { display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' } },
        React.createElement('div', null,
          React.createElement('div', {
            style: { fontSize: 13, fontWeight: 700, color: P.ink, letterSpacing: '0.08em', marginBottom: 6 },
          }, 'Live options trading is not enabled.'),
          React.createElement('div', {
            style: { fontSize: 11, color: P.ink3, letterSpacing: '0.06em', lineHeight: 1.6 },
          }, 'This feature is intentionally disabled in this build.'),
        ),
        React.createElement('button', {
          onClick: (e) => { e.stopPropagation(); setLivePanel(false); },
          style: { background: 'none', border: 'none', color: P.ink3, cursor: 'pointer',
                   fontSize: 16, padding: '0 0 0 12px', lineHeight: 1 },
        }, '✕'),
      ),
    ),
  );
}

/* Paper wheel list view — shows all paper trades with FSM state + live P&L. */
function PaperWheelList({ onSelect, onNew, onBack }) {
  const P = OPT_PALETTE;
  const [wheels, setWheels] = React.useState([]);
  const [loading, setLoading] = React.useState(true);
  const [err, setErr] = React.useState(null);
  const lab = { fontSize: 12, letterSpacing: '0.14em', textTransform: 'uppercase', fontWeight: 700 };

  React.useEffect(() => {
    window.API.listPaperWheels()
      .then(d => { setWheels(d.wheels || []); setLoading(false); })
      .catch(e => { setErr(e?.detail || e?.error || 'Could not load paper trades.'); setLoading(false); });
  }, []);

  const del = async (e, id) => {
    e.stopPropagation();
    try {
      await window.API.deletePaperWheel(id);
      setWheels(ws => ws.filter(w => w.id !== id));
    } catch (ex) {
      setErr(ex?.detail || ex?.error || 'Delete failed.');
    }
  };

  return (
    <div>
      <button onClick={onBack} style={{ background: 'transparent', border: 'none', cursor: 'pointer', padding: 0,
        fontFamily: 'monospace', fontSize: 13, letterSpacing: '0.12em', textTransform: 'uppercase',
        color: '#FF6D00', fontWeight: 700, marginBottom: 16 }}>← BACK</button>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <span style={{ ...lab, fontSize: 12, letterSpacing: '0.18em', color: P.mintDeep }}>◆ PAPER TRADES</span>
        <button onClick={onNew}
                style={{ background: P.mint, color: '#fff', border: 'none',
                         padding: '4px 12px', borderRadius: 4, cursor: 'pointer',
                         fontFamily: 'monospace', fontSize: 11, letterSpacing: '0.08em',
                         textTransform: 'uppercase', fontWeight: 700 }}>
          + NEW
        </button>
      </div>
      <OptError msg={err} />
      {loading && <div style={{ color: P.ink3, opacity: 0.5, fontSize: 12 }}>Loading…</div>}
      {!loading && !wheels.length && (
        <div style={{ color: P.ink3, opacity: 0.5, fontSize: 12 }}>
          No paper trades yet. Use "PAPER TRADE THIS →" on a CSP candidate.
        </div>
      )}
      {wheels.map(w => {
        const state = w.state?.state || 'CASH';
        const pnl = w.live?.unrealized_pl;
        return (
          <div key={w.id} onClick={() => onSelect(w.id)}
               style={{ padding: '10px 14px', marginBottom: 6, borderRadius: 4,
                        background: P.card, border: `1px solid ${P.line}`, cursor: 'pointer',
                        display: 'flex', justifyContent: 'space-between',
                        alignItems: 'center', gap: 12 }}>
            <div>
              <span style={{ fontWeight: 700, fontSize: 13, color: P.ink }}>{w.underlying}</span>
              <span style={{ color: P.ink3, fontSize: 11, marginLeft: 8 }}>{state}</span>
              {w.needs_attention && (
                <span style={{ background: P.amber, color: '#fff',
                               fontSize: 10, padding: '1px 6px', borderRadius: 10,
                               marginLeft: 8 }}>!</span>
              )}
            </div>
            <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
              {pnl != null && (
                <span style={{ color: pnl >= 0 ? P.mint : P.amber,
                               fontSize: 12, fontWeight: 600 }}>
                  {pnl >= 0 ? '+' : ''}{pnl.toFixed(2)}
                </span>
              )}
              <button onClick={(e) => del(e, w.id)} style={{
                background: 'transparent', border: `1px solid ${P.line}`, borderRadius: 4,
                cursor: 'pointer', color: P.amber, fontFamily: 'monospace', fontSize: 11, padding: '3px 8px' }}>
                DELETE
              </button>
            </div>
          </div>
        );
      })}
      {React.createElement(LiveGateTeaser, { wheels, loading })}
    </div>
  );
}

/* Inline confirmation panel shown inside OptCard before creating a paper wheel. */
function PaperTradeConfirm({ candidate, onConfirm, onCancel, busy, err }) {
  const P = OPT_PALETTE;
  const c = candidate;
  const mid = c.mid || 0;
  const premium = Math.round(mid * 100);
  const lab = { fontSize: 12, letterSpacing: '0.14em', textTransform: 'uppercase', fontWeight: 700 };
  return (
    <div style={{ marginTop: 12, background: P.mintSoft, border: `1px solid ${P.mint}`,
                  borderRadius: 8, padding: '14px 16px' }}>
      <div style={{ ...lab, color: P.mintDeep, marginBottom: 8 }}>◆ CONFIRM PAPER TRADE</div>
      <div style={{ fontSize: 13, color: P.ink, lineHeight: 1.65, marginBottom: 10 }}>
        <b>Order spec:</b> SELL TO OPEN · {c.underlying} {c.expiry} ${c.strike} PUT ·
        1 contract (100 shares obligation) · limit ${mid.toFixed(2)} (mid)
      </div>
      <div style={{ background: P.amberBg, border: `1px solid ${P.amberLine}`,
                    borderRadius: 6, padding: '10px 13px', fontSize: 13, color: '#6b5118', lineHeight: 1.6 }}>
        You are committing to buy 100 shares of <b>{c.underlying}</b> at <b>${c.strike}</b> for
        a <b>${premium.toLocaleString()}</b> premium. This order will be submitted to your
        Alpaca paper account.
      </div>
      <div style={{ marginTop: 12, display: 'flex', gap: 10 }}>
        <OptButton label={busy ? 'SUBMITTING…' : 'CONFIRM — SUBMIT TO ALPACA PAPER'} disabled={busy} onClick={onConfirm} />
        <button onClick={onCancel} style={{ background: 'transparent', border: `1px solid ${P.line}`,
          borderRadius: 6, cursor: 'pointer', padding: '8px 14px', fontFamily: 'monospace',
          fontSize: 12, color: P.ink4, letterSpacing: '0.1em', textTransform: 'uppercase', fontWeight: 700 }}>
          CANCEL
        </button>
      </div>
      <OptError msg={err} />
    </div>
  );
}

/* Paper Wheel tracker — live Alpaca paper panel + FSM strip + CC selection + manual events. */
function PaperWheelTracker({ wheelId, onBack }) {
  const P = OPT_PALETTE;
  const [wheel, setWheel] = React.useState(null);
  const [loading, setLoading] = React.useState(true);
  const [err, setErr] = React.useState(null);
  const [busy, setBusy] = React.useState(false);
  const [calls, setCalls] = React.useState(null);
  const [callsErr, setCallsErr] = React.useState(null);
  const [selectedCall, setSelectedCall] = React.useState(null);
  const [ccConfirm, setCcConfirm] = React.useState(false);
  const [ccBusy, setCcBusy] = React.useState(false);
  const [ccErr, setCcErr] = React.useState(null);
  const [manualOpen, setManualOpen] = React.useState(false);

  const lab = { fontSize: 12, letterSpacing: '0.14em', textTransform: 'uppercase', fontWeight: 700 };

  const reload = React.useCallback(() => {
    window.API.getPaperWheel(wheelId)
      .then(w => { setWheel(w); setLoading(false); })
      .catch(e => { setErr(e?.detail || e?.error || 'Could not load paper wheel.'); setLoading(false); });
  }, [wheelId]);

  React.useEffect(() => { reload(); }, [reload]);

  const postEvent = async (event) => {
    setBusy(true); setErr(null);
    try {
      const w = await window.API.postPaperWheelEvent(wheelId, event);
      setWheel(w);
    } catch (e) {
      setErr(e?.detail || e?.error || 'Event failed — try again.');
    }
    setBusy(false);
  };

  const loadCalls = async () => {
    setCallsErr(null);
    try {
      const d = await window.API.getPaperWheelCalls(wheelId);
      setCalls(d.calls || d || []);
    } catch (e) {
      setCallsErr(e?.detail || e?.error || 'Could not fetch calls chain.');
    }
  };

  const submitCC = async () => {
    if (!selectedCall) return;
    setCcBusy(true); setCcErr(null);
    try {
      const w = await window.API.submitPaperCC(wheelId, {
        strike: selectedCall.strike,
        expiry: selectedCall.expiry,
        mid: selectedCall.mid,
        delta: selectedCall.delta,
        dte: selectedCall.dte,
      });
      setWheel(w);
      setCcConfirm(false);
      setSelectedCall(null);
      setCalls(null);
    } catch (e) {
      setCcErr(e?.detail || e?.error || 'CC submission failed — try again.');
    }
    setCcBusy(false);
  };

  if (loading) return (
    <div style={{ color: P.ink3, fontSize: 13, letterSpacing: '0.1em' }}>◇ LOADING…</div>
  );

  if (!wheel) return (
    <div>
      <button onClick={onBack} style={{ background: 'transparent', border: 'none', cursor: 'pointer', padding: 0,
        fontFamily: 'monospace', fontSize: 13, letterSpacing: '0.12em', textTransform: 'uppercase',
        color: '#FF6D00', fontWeight: 700, marginBottom: 16 }}>← BACK</button>
      <OptError msg={err || 'Paper wheel not found.'} />
    </div>
  );

  const st = wheel.state || {};
  const live = wheel.live || {};
  const state = st.state || 'CASH';
  const pendingFill = wheel.pending_fill === true;

  /* FSM strip — same chip pattern as WheelTracker */
  const chips = [
    { key: 'CASH', label: 'CASH' },
    { key: 'CSP_OPEN', label: 'CSP OPEN' },
    { key: 'SHARES', label: 'SHARES' },
    { key: 'CC_OPEN', label: 'CC OPEN' },
  ];

  /* last-polled freshness */
  const lastPolledAge = () => {
    if (!live.last_polled) return null;
    const mins = Math.round((Date.now() - new Date(live.last_polled).getTime()) / 60000);
    return mins;
  };
  const age = lastPolledAge();
  const stale = age != null && age > 10;

  /* manual event options */
  const MANUAL_EVENTS = [
    { event: 'CHECKPOINT_HELD', label: 'CHECKPOINT HELD' },
    { event: 'EXPIRED_WORTHLESS', label: 'EXPIRED WORTHLESS' },
    { event: 'ASSIGNED', label: 'ASSIGNED (CSP)' },
    { event: 'CALLED_AWAY', label: 'CALLED AWAY (CC)' },
  ];

  return (
    <div style={{ maxWidth: 720 }}>
      <button onClick={onBack} style={{ background: 'transparent', border: 'none', cursor: 'pointer', padding: 0,
        fontFamily: 'monospace', fontSize: 13, letterSpacing: '0.12em', textTransform: 'uppercase',
        color: '#FF6D00', fontWeight: 700, marginBottom: 16 }}>← BACK</button>
      <div style={{ ...lab, fontSize: 12, letterSpacing: '0.18em', color: P.mintDeep }}>◆ PAPER WHEEL · {wheel.underlying}</div>

      {/* LIVE ALPACA PAPER panel */}
      <div style={{ background: P.card, border: `1px solid ${P.line}`, borderRadius: 10, padding: '16px 18px', marginTop: 14 }}>
        <div style={{ ...lab, fontSize: 12, color: P.ink4, marginBottom: 10 }}>LIVE ALPACA PAPER</div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px 28px' }}>
          {live.unrealized_pl != null && (
            <div>
              <div style={{ ...lab, fontSize: 11, color: P.ink4 }}>Unrealized P&L</div>
              <div style={{ fontSize: 18, fontWeight: 700, color: live.unrealized_pl >= 0 ? P.mint : P.amber }}>
                {live.unrealized_pl >= 0 ? '+' : ''}${live.unrealized_pl.toFixed(2)}
              </div>
            </div>
          )}
          {live.current_price != null && (
            <div>
              <div style={{ ...lab, fontSize: 11, color: P.ink4 }}>Current Option Price</div>
              <div style={{ fontSize: 18, fontWeight: 700, color: P.ink }}>${live.current_price.toFixed(2)}</div>
            </div>
          )}
          {live.dte != null && (
            <div>
              <div style={{ ...lab, fontSize: 11, color: P.ink4 }}>DTE</div>
              <div style={{ fontSize: 18, fontWeight: 700, color: P.ink }}>{live.dte}</div>
            </div>
          )}
        </div>
        {age != null && (
          <div style={{ fontSize: 11, color: stale ? P.amber : P.ink4, marginTop: 8 }}>
            Last updated {age === 0 ? 'just now' : `${age} min ago`}
            {stale && ' — may be stale'}
          </div>
        )}
      </div>

      {/* FSM strip */}
      <div style={{ display: 'flex', gap: 6, margin: '14px 0 4px' }}>
        {chips.map((ch, i) => {
          const on = ch.key === state;
          return (
            <React.Fragment key={ch.key}>
              <span style={{ ...lab, fontSize: 12, padding: '6px 10px', borderRadius: 6,
                background: on ? P.mint : P.bg2, color: on ? '#fff' : P.ink4,
                border: `1px solid ${on ? P.mintDeep : P.line}` }}>{ch.label}</span>
              {i < chips.length - 1 && <span style={{ color: P.ink4, alignSelf: 'center' }}>▸</span>}
            </React.Fragment>
          );
        })}
      </div>

      {/* Pending fill banner */}
      {pendingFill && (
        <div style={{ marginTop: 14, background: P.amberBg, border: `1px solid ${P.amberLine}`,
                      borderRadius: 8, padding: '12px 15px' }}>
          <div style={{ ...lab, fontSize: 12, color: P.amber }}>ORDER SUBMITTED — WAITING FOR FILL</div>
          {age != null && (
            <div style={{ fontSize: 12, color: '#6b5118', marginTop: 4 }}>
              Last polled {age === 0 ? 'just now' : `${age} min ago`}
            </div>
          )}
        </div>
      )}

      {/* CC selection flow when state === SHARES */}
      {!pendingFill && state === 'SHARES' && (
        <div style={{ marginTop: 16, background: P.card, border: `1px solid ${P.line}`, borderRadius: 10, padding: '16px 18px' }}>
          <div style={{ ...lab, fontSize: 12, color: P.ink4, marginBottom: 8 }}>SELECT A COVERED CALL TO SELL</div>
          {!calls && !callsErr && (
            <OptButton label="LOAD CALLS CHAIN" disabled={busy} onClick={loadCalls} />
          )}
          {callsErr && <OptError msg={callsErr} />}
          {calls && calls.length === 0 && (
            <div style={{ fontSize: 12, color: P.ink3 }}>No calls available right now.</div>
          )}
          {calls && calls.length > 0 && !ccConfirm && (
            <div>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
                <thead>
                  <tr>
                    {['Strike', 'Mid', 'Delta', 'DTE', ''].map(h => (
                      <th key={h} style={{ ...lab, fontSize: 11, color: P.ink4, textAlign: 'left',
                                           padding: '4px 8px', borderBottom: `1px solid ${P.line}` }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {calls.map((c, i) => {
                    const sel = selectedCall && selectedCall.strike === c.strike && selectedCall.expiry === c.expiry;
                    return (
                      <tr key={i} onClick={() => setSelectedCall(c)}
                          style={{ background: sel ? P.mintSoft : 'transparent', cursor: 'pointer' }}>
                        <td style={{ padding: '6px 8px', color: P.ink, fontWeight: sel ? 700 : 400 }}>${c.strike}</td>
                        <td style={{ padding: '6px 8px', color: P.ink }}>${c.mid?.toFixed(2)}</td>
                        <td style={{ padding: '6px 8px', color: P.ink }}>{c.delta?.toFixed(2)}</td>
                        <td style={{ padding: '6px 8px', color: P.ink }}>{c.dte}</td>
                        <td style={{ padding: '6px 8px' }}>
                          {sel && (
                            <button onClick={(e) => { e.stopPropagation(); setCcConfirm(true); }}
                                    style={{ background: P.mint, color: '#fff', border: 'none', cursor: 'pointer',
                                             padding: '3px 10px', borderRadius: 4, fontFamily: 'monospace',
                                             fontSize: 11, fontWeight: 700, letterSpacing: '0.08em' }}>
                              SELECT →
                            </button>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
          {ccConfirm && selectedCall && (
            <div style={{ marginTop: 10, background: P.mintSoft, border: `1px solid ${P.mint}`,
                          borderRadius: 8, padding: '12px 14px' }}>
              <div style={{ ...lab, fontSize: 12, color: P.mintDeep, marginBottom: 6 }}>CONFIRM COVERED CALL</div>
              <div style={{ fontSize: 13, color: P.ink, lineHeight: 1.6, marginBottom: 8 }}>
                SELL TO OPEN · {wheel.underlying} {selectedCall.expiry} ${selectedCall.strike} CALL ·
                1 contract · limit ${selectedCall.mid?.toFixed(2)} (mid) · {selectedCall.dte} DTE
              </div>
              <div style={{ display: 'flex', gap: 10 }}>
                <OptButton label={ccBusy ? 'SUBMITTING…' : 'SUBMIT CC TO ALPACA PAPER'} disabled={ccBusy} onClick={submitCC} />
                <button onClick={() => { setCcConfirm(false); setSelectedCall(null); }}
                        style={{ background: 'transparent', border: `1px solid ${P.line}`, borderRadius: 6,
                                 cursor: 'pointer', padding: '8px 14px', fontFamily: 'monospace',
                                 fontSize: 12, color: P.ink4, letterSpacing: '0.1em', textTransform: 'uppercase', fontWeight: 700 }}>
                  CANCEL
                </button>
              </div>
              <OptError msg={ccErr} />
            </div>
          )}
        </div>
      )}

      <OptError msg={err} />

      {/* Manual events expander */}
      <div style={{ marginTop: 16, borderTop: `1px solid ${P.line}`, paddingTop: 12 }}>
        <button onClick={() => setManualOpen(o => !o)} style={{
          background: 'transparent', border: 'none', cursor: 'pointer', padding: 0,
          fontFamily: 'monospace', fontSize: 12, letterSpacing: '0.1em', textTransform: 'uppercase',
          fontWeight: 700, color: P.ink4 }}>
          {manualOpen ? '▾ RECORD MANUAL EVENT' : '› RECORD MANUAL EVENT'}
        </button>
        {manualOpen && (
          <div style={{ marginTop: 10, display: 'flex', flexWrap: 'wrap', gap: 8 }}>
            {MANUAL_EVENTS.map(me => (
              <button key={me.event} disabled={busy} onClick={() => postEvent(me.event)}
                      style={{ background: P.card, border: `1px solid ${P.line}`, borderRadius: 6,
                               cursor: busy ? 'default' : 'pointer', padding: '6px 13px',
                               fontFamily: 'monospace', fontSize: 11, color: P.ink,
                               letterSpacing: '0.08em', textTransform: 'uppercase', fontWeight: 700 }}>
                {me.label}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

/* Runs calm+crash scenarios for one danger lever and shows side-by-side + AI compare. */
function DangerLeverPanel({ leverKey, candidate }) {
  // NOTE: lever constants (0.85/0.62/×2.5/5) are duplicated in options_engine.py danger_lever_scenarios().
  // Keep the two in sync if you change the numbers here.
  const P = OPT_PALETTE;
  const [results, setResults] = React.useState(null);
  const [busy, setBusy] = React.useState(false);
  const [err, setErr] = React.useState(null);

  const run = async () => {
    setBusy(true); setErr(null);
    const baseSpec = {
      strike: candidate.strike, mid: candidate.mid,
      cash_backed: true, underlying: candidate.underlying, dte: candidate.dte,
    };
    const spot = (candidate.collateral / 100) || candidate.strike;
    let recklessSpec, calmPrice, crashPrice, label, description;
    if (leverKey === 'cash') {
      recklessSpec = { ...baseSpec, cash_backed: false };
      calmPrice = candidate.strike + 2;
      crashPrice = Math.round(candidate.strike * 0.85 * 100) / 100;
      label = 'Skip the cash backing (naked / on margin)';
      description = 'Same trade, no cash set aside. Only 20% margin covers you.';
    } else if (leverKey === 'delta') {
      const atmStrike = Math.round(spot * 0.99 * 100) / 100;
      recklessSpec = { ...baseSpec, strike: atmStrike, mid: Math.round(candidate.mid * 2.5 * 100) / 100 };
      calmPrice = Math.round(spot * 1.02 * 100) / 100;
      crashPrice = Math.round(spot * 0.85 * 100) / 100;
      label = 'Chase higher assignment odds (near-ATM strike)';
      description = `Move the strike to $${atmStrike.toLocaleString()} — near the money.`;
    } else if (leverKey === 'underlying') {
      recklessSpec = { ...baseSpec, underlying: 'SINGLE STOCK', mid: Math.round(candidate.mid * 2.0 * 100) / 100 };
      calmPrice = candidate.strike + 2;
      crashPrice = Math.round(candidate.strike * 0.62 * 100) / 100;
      label = 'Sell against a single volatile stock';
      description = 'Same structure on a single name — with a 40% gap risk.';
    } else if (leverKey === 'size') {
      recklessSpec = { ...baseSpec, contracts: 5 };
      calmPrice = candidate.strike + 2;
      crashPrice = Math.round(candidate.strike * 0.85 * 100) / 100;
      label = 'Bet bigger (5 contracts instead of 1)';
      description = '5× the contracts — same per-contract math, 5× the capital and damage.';
    } else {
      setErr('Unknown lever'); setBusy(false); return;
    }

    let safeCalm, safeCrash, recklessCalm, recklessCrash;
    try {
      [safeCalm, safeCrash, recklessCalm, recklessCrash] = await Promise.all([
        window.API.runScenario(baseSpec, calmPrice),
        window.API.runScenario(baseSpec, crashPrice),
        window.API.runScenario(recklessSpec, calmPrice),
        window.API.runScenario(recklessSpec, crashPrice),
      ]);
    } catch (e) {
      setErr('Scenario failed — check the backend is running.');
      setBusy(false);
      return;
    }
    const firstErr = [safeCalm, safeCrash, recklessCalm, recklessCrash].find(r => r?.error);
    if (firstErr) { setErr(firstErr.error || 'Scenario unavailable.'); setBusy(false); return; }
    setResults({ label, description, safeCalm, safeCrash, recklessCalm, recklessCrash, baseSpec, recklessSpec, calmPrice, crashPrice });
    setBusy(false);
  };

  if (!results) return (
    <div style={{ marginTop: 6 }}>
      <button onClick={run} disabled={busy} style={{
        background: busy ? P.amberBg : 'transparent', border: `1px solid ${P.amberLine}`,
        borderRadius: 6, cursor: busy ? 'default' : 'pointer', fontFamily: 'monospace',
        fontSize: 12, fontWeight: 700, color: P.amber, padding: '5px 11px',
        letterSpacing: '0.1em', textTransform: 'uppercase' }}>
        {busy ? '◇ RUNNING SCENARIOS…' : '🔥 SHOW ME WHAT THIS COSTS →'}
      </button>
      <OptError msg={err} />
    </div>
  );

  const col = { display: 'flex', flexDirection: 'column', gap: 6, flex: 1, minWidth: 0 };
  const sec = (title) => (
    <div style={{ fontSize: 11, letterSpacing: '0.12em', textTransform: 'uppercase',
      fontWeight: 700, color: P.ink4, margin: '10px 0 4px' }}>{title}</div>
  );
  return (
    <div style={{ marginTop: 10, background: P.amberBg, border: `1px solid ${P.amberLine}`,
      borderRadius: 8, padding: '12px 14px' }}>
      <div style={{ fontSize: 12, fontWeight: 700, color: P.amber, marginBottom: 4 }}>{results.label}</div>
      <div style={{ fontSize: 13, color: '#6b5118', marginBottom: 10 }}>{results.description}</div>
      {sec('CALM MONTH (+2% — option expires safely for both)')}
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        <div style={col}><ScenarioCard run={results.safeCalm} label="Safe (current Banshee pick)" /></div>
        <div style={col}><ScenarioCard run={results.recklessCalm} label="Reckless (lever pulled)" /></div>
      </div>
      {sec('CRASH MONTH (the tail that matters)')}
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        <div style={col}><ScenarioCard run={results.safeCrash} label="Safe (current Banshee pick)" /></div>
        <div style={col}><ScenarioCard run={results.recklessCrash} label="Reckless (lever pulled)" /></div>
      </div>
      <AiNarration label="AI — WHY THIS RULE EXISTS"
        fetchFn={() => window.API.learnCompare(results.safeCrash, results.recklessCrash)}
        cacheKey={leverKey} />
      <button onClick={() => setResults(null)} style={{
        marginTop: 10, background: 'transparent', border: 'none', cursor: 'pointer',
        fontFamily: 'monospace', fontSize: 12, color: P.amber, padding: 0 }}>✕ close</button>
    </div>
  );
}

/* The safety rules as dials at SAFE — each teaches its rule and shows what
   loosening it would cost (via the live calm/crash DangerLeverPanel below each dial). */
function OptControlPanel({ data }) {
  const P = OPT_PALETTE;
  const c = data.candidate || {};
  const ivr = c.ivr_estimate;
  const dials = [
    { key: 'cash', label: 'Cash backing (cash-secured)', val: 'fully cash-secured',
      why: 'The full purchase price sits in cash, ready.',
      loosen: 'Sell it "naked" on margin: same income, none locked up — until a crash you can\'t cover triggers a margin call.' },
    { key: 'delta', label: 'Assignment odds (delta)', val: `${Math.abs(c.delta).toFixed(2)} (~${Math.round(c.prob_keep * 100)}% expires)`,
      why: 'Low odds you\'re forced to buy.',
      loosen: 'Chase a higher delta for fatter premium and you\'re assigned far more often — buying stock, not collecting income.' },
    { key: 'underlying', label: 'What you sell against (underlying)', val: `broad fund (${c.underlying})`,
      why: 'A whole-market basket can\'t gap 30% overnight.',
      loosen: 'A single hot name pays more because it can crater on one earnings report.' },
    { key: 'size', label: 'Trade size (% of account)', val: c.sizing ? `${c.sizing.pct}% of account` : '≤ 5% of account',
      why: 'One bad trade can\'t sink you.',
      loosen: 'Bet bigger and one assignment ties up everything — no dry powder, stuck holding for months.' },
    { key: 'dte', label: 'Time to expiry (DTE)', val: `${c.dte} days`,
      why: '35–45 days is where time-decay works hardest for you.', loosen: null },
    { key: 'oi', label: 'Liquidity (open interest)', val: (c.open_interest || 0).toLocaleString(),
      why: 'Enough traders that you can exit at a fair price.', loosen: null },
    { key: 'ivr', label: 'Premium richness (IV rank, est.)', val: ivr != null ? `~${Math.round(ivr)} est.` : 'n/a',
      why: 'Pay is worth the risk only when premium is rich; below the line, the Wheel waits — which is why some days Banshee returns nothing, and that\'s correct.', loosen: null },
  ];
  const lab = { fontSize: 12, letterSpacing: '0.14em', textTransform: 'uppercase', fontWeight: 700 };
  return (
    <div style={{ marginTop: 22, maxWidth: 620 }}>
      <div style={{ ...lab, color: P.mintDeep, marginBottom: 4 }}>◆ THE SAFETY RULES THAT FOUND THIS</div>
      <div style={{ fontSize: 13, color: P.ink3, lineHeight: 1.6, marginBottom: 12 }}>
        Each rule is a dial set to <b>SAFE</b>. Together they <b>are</b> the option above. The safe move is just every dial left.
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {dials.map(d => (
          <div key={d.key} style={{ border: `1px solid ${P.line}`, borderRadius: 9, padding: '11px 14px', background: P.card }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 10 }}>
              <TermInfo termKey={d.key} label={d.label} style={{ fontSize: 13, fontWeight: 700, color: P.ink }} />
              <span style={{ fontSize: 11, color: P.mintDeep, border: `1px solid ${P.mint}`, borderRadius: 5, padding: '2px 8px', whiteSpace: 'nowrap' }}>SAFE · {d.val}</span>
            </div>
            <div style={{ fontSize: 13, color: P.ink3, lineHeight: 1.55, marginTop: 6 }}>{d.why}</div>
            {d.loosen && (
              <DangerLeverPanel leverKey={d.key} candidate={data.candidate} />
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

/* Compose-your-own option → Banshee grades it rule-by-rule (the inverse search). */
function OptGrader({ candidate }) {
  const P = OPT_PALETTE;
  const [spec, setSpec] = React.useState({ underlying: 'SPY', strike: '', dte: '42', cash_backed: true, account_size: '' });
  const [res, setRes] = React.useState(null);
  const [busy, setBusy] = React.useState(false);
  const [err, setErr] = React.useState(null);
  const [fireRun, setFireRun] = React.useState(null);
  const [fireBusy, setFireBusy] = React.useState(false);
  const lab = { fontSize: 12, letterSpacing: '0.14em', textTransform: 'uppercase', fontWeight: 700 };
  const inp = { fontFamily: 'monospace', fontSize: 13, padding: '6px 9px', background: P.card,
    color: P.ink, border: `1px solid ${P.line}`, borderRadius: 6 };

  const grade = async () => {
    setBusy(true); setErr(null); setRes(null); setFireRun(null);
    const payload = {
      underlying: (spec.underlying || '').toUpperCase().trim(),
      strike: parseFloat(spec.strike),
      dte: parseInt(spec.dte, 10),
      cash_backed: spec.cash_backed,
      account_size: spec.account_size ? parseFloat(spec.account_size) : null,
    };
    const r = await window.API.gradeOption(payload);
    setBusy(false);
    if (r && r.error) setErr(r.error); else setRes(r);
  };

  const lightFire = async () => {
    if (!res || !(res.strike > 0)) return;
    setFireBusy(true); setFireRun(null);
    const crashTerminal = Math.round(res.strike * 0.85 * 100) / 100;
    const failSpec = {
      strike: res.strike, mid: res.mid || 2.0,
      cash_backed: spec.cash_backed, underlying: res.underlying,
    };
    const run = await window.API.runScenario(failSpec, crashTerminal);
    if (run.error) setErr(run.error);
    else setFireRun(run);
    setFireBusy(false);
  };

  return (
    <div style={{ marginTop: 22, maxWidth: 620, borderTop: `1px solid ${P.line}`, paddingTop: 18 }}>
      <div style={{ ...lab, color: P.mintDeep }}>◆ MODEL YOUR OWN OPTION</div>
      <div style={{ fontSize: 13, color: P.ink3, lineHeight: 1.6, margin: '5px 0 12px' }}>
        You're going to want to try something. Compose it here and Banshee grades it against the same rules —
        no money, no broker, just an honest verdict. You choose.
      </div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, alignItems: 'flex-end' }}>
        <div><div style={{ ...lab, color: P.ink4, marginBottom: 4 }}>Sell against</div>
          <input value={spec.underlying} onChange={e => setSpec({ ...spec, underlying: e.target.value })} style={{ ...inp, width: 90 }} /></div>
        <div><div style={{ ...lab, color: P.ink4, marginBottom: 4 }}>Strike</div>
          <input value={spec.strike} placeholder="480" onChange={e => setSpec({ ...spec, strike: e.target.value.replace(/[^0-9.]/g, '') })} style={{ ...inp, width: 80 }} /></div>
        <div><div style={{ ...lab, color: P.ink4, marginBottom: 4 }}>Days to expiry</div>
          <input value={spec.dte} onChange={e => setSpec({ ...spec, dte: e.target.value.replace(/[^0-9]/g, '') })} style={{ ...inp, width: 70 }} /></div>
        <div><div style={{ ...lab, color: P.ink4, marginBottom: 4 }}>Account</div>
          <input value={spec.account_size} placeholder="optional" onChange={e => setSpec({ ...spec, account_size: e.target.value.replace(/[^0-9]/g, '') })} style={{ ...inp, width: 100 }} /></div>
        <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, color: P.ink, cursor: 'pointer' }}>
          <input type="checkbox" checked={spec.cash_backed} onChange={e => setSpec({ ...spec, cash_backed: e.target.checked })} />
          cash-backed
        </label>
        <OptButton label={busy ? 'GRADING…' : 'GRADE IT'} disabled={busy} onClick={grade} />
      </div>
      <OptError msg={err} />
      {res && (
        <div style={{ marginTop: 14 }}>
          <div style={{ fontSize: 15, fontWeight: 700,
            color: res.passes_all ? P.mintDeep : (res.failed.length ? P.amber : P.ink3) }}>
            {res.passes_all
              ? '✓ This clears every one of Banshee\'s standards.'
              : (res.failed.length
                  ? `⚠ This breaks ${res.failed.length} rule${res.failed.length > 1 ? 's' : ''} — here's what you'd be taking on.`
                  : 'Couldn\'t fully check this yet — add your account size to grade trade size.')}
          </div>
          {res.data_quality && res.data_quality.strike_gap > 0 && (
            <div style={{ fontSize: 12, color: P.ink4, fontStyle: 'italic', marginTop: 5 }}>
              Estimated from the nearest listed strike ${Number(res.data_quality.nearest_listed_strike).toLocaleString()} (your strike is ${Number(res.data_quality.strike_gap).toLocaleString()} away) — the further off, the rougher the read.
            </div>
          )}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 7, marginTop: 10 }}>
            {res.rules.map(r => (
              <div key={r.key} style={{ display: 'flex', gap: 9, fontSize: 13, lineHeight: 1.55,
                color: r.passed === false ? '#6b5118' : P.ink }}>
                <span style={{ flexShrink: 0, color: r.passed === false ? P.amber : (r.passed === true ? P.mint : P.ink4) }}>
                  {r.passed === false ? '🔥' : (r.passed === true ? '✓' : '–')}
                </span>
                <span><TermInfo termKey={r.key} label={r.label} />: {r.value}. {r.passed === false ? r.risk_if_broken : r.why}</span>
              </div>
            ))}
          </div>
          {/* Light the fire — only shown when rules are broken */}
          {res.failed && res.failed.length > 0 && (
            <div style={{ marginTop: 14, paddingTop: 12, borderTop: `1px solid ${P.amberLine}` }}>
              {!fireRun && (
                <button onClick={lightFire} disabled={fireBusy} style={{
                  background: fireBusy ? P.amberBg : 'transparent',
                  border: `1px solid ${P.amberLine}`, borderRadius: 6,
                  cursor: fireBusy ? 'default' : 'pointer', fontFamily: 'monospace',
                  fontSize: 12, fontWeight: 700, color: P.amber, padding: '6px 13px',
                  letterSpacing: '0.1em', textTransform: 'uppercase' }}>
                  {fireBusy ? '◇ SIMULATING…' : '🔥 LIGHT THE FIRE — SHOW ME WHAT THIS COSTS'}
                </button>
              )}
              {fireRun && (
                <>
                  <div style={{ fontSize: 12, letterSpacing: '0.12em', textTransform: 'uppercase',
                    fontWeight: 700, color: P.amber, marginBottom: 6 }}>
                    CRASH SCENARIO (−15% below your strike):
                  </div>
                  <ScenarioCard run={fireRun} />
                  <AiNarration label="AI — WHY THESE RULES EXIST"
                    fetchFn={() => window.API.learnWhyNot(res, fireRun)}
                    cacheKey={fireRun.outcome + fireRun.pnl} />
                  <button onClick={() => { setFireRun(null); }} style={{
                    marginTop: 8, background: 'transparent', border: 'none', cursor: 'pointer',
                    fontFamily: 'monospace', fontSize: 12, color: P.amber, padding: 0 }}>
                    ✕ hide simulation
                  </button>
                </>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

const TIER_CAPITAL = { starter: 2500, building: 27500, established: 87500, institutional: 200000 };
const TIER_LABELS = [
  { key: 'starter',      label: 'Under $5k',  sub: 'Getting Started' },
  { key: 'building',     label: '$5k–$50k',   sub: 'Building'        },
  { key: 'established',  label: '$50k–$125k', sub: 'Established'     },
  { key: 'institutional',label: '$125k+',      sub: 'Institutional'   },
];
const TIER_DEFAULT_TRACK = { starter: 'spreads', building: 'spreads', established: 'wheel', institutional: 'wheel' };

function CapitalTierSelector({ tier, onTier }) {
  const P = OPT_PALETTE;
  return (
    <div style={{ marginBottom: 20 }}>
      <div style={{ fontSize: 11, fontFamily: 'JetBrains Mono, monospace', color: P.ink4, letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: 8 }}>
        YOUR CAPITAL TIER
      </div>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        {TIER_LABELS.map(t => (
          <button key={t.key} onClick={() => onTier(t.key)}
            style={{ padding: '8px 14px', border: `1px solid ${tier === t.key ? P.mint : P.line}`,
              background: tier === t.key ? P.mintSoft : P.card, color: tier === t.key ? P.mintDeep : P.ink3,
              cursor: 'pointer', borderRadius: 2, fontFamily: 'JetBrains Mono, monospace', fontSize: 11 }}>
            <div style={{ fontWeight: 600 }}>{t.label}</div>
            <div style={{ fontSize: 10, color: tier === t.key ? P.mintDeep : P.ink4 }}>{t.sub}</div>
          </button>
        ))}
      </div>
    </div>
  );
}

function InstitutionalFramingPanel({ tier }) {
  const P = OPT_PALETTE;
  const spyEstimate = 530;
  const cspCollateral = spyEstimate * 100;
  const spreadBpr = 350;
  const ratio = Math.round(cspCollateral / spreadBpr);
  return (
    <div style={{ background: P.wall, border: `1px solid ${P.line}`, padding: '14px 16px', marginBottom: 20, borderRadius: 2 }}>
      <div style={{ fontSize: 11, fontFamily: 'JetBrains Mono, monospace', color: P.ink4, textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 10 }}>
        TWO WAYS TO TRADE OPTIONS ON THE SAME UNDERLYING
      </div>
      <div style={{ display: 'flex', gap: 24, flexWrap: 'wrap' }}>
        <div>
          <div style={{ fontSize: 10, color: P.ink4, fontFamily: 'JetBrains Mono, monospace', textTransform: 'uppercase', marginBottom: 4 }}>Cash-Secured Put (The Wheel)</div>
          <div style={{ fontSize: 20, fontWeight: 700, color: P.ink, fontFamily: 'JetBrains Mono, monospace' }}>${cspCollateral.toLocaleString()}</div>
          <div style={{ fontSize: 11, color: P.ink3 }}>collateral per contract on SPY</div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', color: P.ink4, fontSize: 18 }}>vs</div>
        <div>
          <div style={{ fontSize: 10, color: P.ink4, fontFamily: 'JetBrains Mono, monospace', textTransform: 'uppercase', marginBottom: 4 }}>Bull Put Spread (Credit Spreads)</div>
          <div style={{ fontSize: 20, fontWeight: 700, color: P.mint, fontFamily: 'JetBrains Mono, monospace' }}>${spreadBpr}</div>
          <div style={{ fontSize: 11, color: P.ink3 }}>BPR — same thesis, defined risk</div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center' }}>
          <div style={{ background: P.mintSoft, border: `1px solid ${P.mint}`, padding: '6px 12px', borderRadius: 2 }}>
            <div style={{ fontSize: 11, color: P.mintDeep, fontFamily: 'JetBrains Mono, monospace' }}>{ratio}× less capital tied up</div>
          </div>
        </div>
      </div>
    </div>
  );
}

function TrackForkCards({ tier, activeTrack, onTrack }) {
  const P = OPT_PALETTE;
  const defaultTrack = TIER_DEFAULT_TRACK[tier] || 'spreads';
  const cards = [
    { key: 'wheel',   label: 'The Wheel',     desc: 'Conservative · Cash-secured · ETFs only · Full capital required' },
    { key: 'spreads', label: 'Credit Spreads', desc: 'Defined-risk · Stocks + ETFs · Accessible capital' },
  ];
  return (
    <div style={{ display: 'flex', gap: 12, marginBottom: 24, flexWrap: 'wrap' }}>
      {cards.map(c => {
        const highlight = activeTrack === c.key || (!activeTrack && defaultTrack === c.key);
        return (
          <div key={c.key} onClick={() => onTrack(c.key)}
            style={{ flex: 1, minWidth: 180, padding: '14px 16px', cursor: 'pointer',
              border: `2px solid ${highlight ? P.mint : P.line}`,
              background: highlight ? P.mintSoft : P.card, borderRadius: 2 }}>
            <div style={{ fontWeight: 700, color: highlight ? P.mintDeep : P.ink, marginBottom: 4, fontSize: 13 }}>{c.label}</div>
            <div style={{ fontSize: 11, color: highlight ? P.mintDeep : P.ink3, lineHeight: 1.4 }}>{c.desc}</div>
          </div>
        );
      })}
    </div>
  );
}

function SpreadCalmRoom({ tier, universe, onOpenSim }) {
  const { useState, useEffect } = React;
  const P = OPT_PALETTE;
  const [candidate, setCandidate] = React.useState(null);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    const uParam = universe.length ? '&universe=' + encodeURIComponent(universe.join(',')) : '';
    fetch(`/options/spread-candidate?tier=${tier}${uParam}`, {
      headers: { 'X-Banshee-Token': window.__BANSHEE_TOKEN || '' }
    })
      .then(r => r.json())
      .then(d => { setCandidate(d.candidate || null); setLoading(false); })
      .catch(e => { setError(e.message); setLoading(false); });
  }, [tier, universe.join(',')]);

  if (loading) return React.createElement('div', { style: { color: P.ink3, fontSize: 12, padding: 20 } }, 'Scanning universe...');
  if (error) return React.createElement('div', { style: { color: '#ef4444', fontSize: 12, padding: 20 } }, 'Error: ' + error);

  if (!candidate) return (
    <div style={{ padding: '20px 0', color: P.ink3, fontSize: 12, lineHeight: 1.6 }}>
      <div style={{ marginBottom: 8, fontFamily: 'JetBrains Mono, monospace', color: P.ink }}>Nothing in your universe passes all filters today.</div>
      <div>If there is a specific asset you want to investigate, add it to your universe and take it to the Grader — it will show you exactly where it stands.</div>
    </div>
  );

  const c = candidate;
  const cspCollateral = c.short_strike * 100;
  const rows = [
    ['Strategy', 'Bull Put Spread — ' + c.underlying + ' ' + c.expiration],
    ['Short Strike', '$' + c.short_strike.toFixed(2)],
    ['Long Strike', '$' + c.long_strike.toFixed(2)],
    ['Width', '$' + (c.short_strike - c.long_strike).toFixed(2)],
    ['Net Credit', '$' + c.net_credit.toFixed(2) + ' / share ($' + (c.net_credit * 100).toFixed(0) + ' total)'],
    ['BPR (Max Loss)', '$' + c.bpr.toFixed(0)],
    ['ROC', (c.roc * 100).toFixed(1) + '%'],
    ['Breakeven', '$' + c.breakeven.toFixed(2)],
    ['DTE', c.dte + ' days'],
    ['IVR', c.ivr.toFixed(0)],
  ];

  return (
    <div style={{ background: P.card, border: '1px solid ' + P.line, padding: 16, borderRadius: 2 }}>
      <div style={{ fontSize: 11, fontFamily: 'JetBrains Mono, monospace', color: P.ink4, textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 12 }}>TODAY'S CANDIDATE</div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '4px 16px', marginBottom: 16 }}>
        {rows.map(([k, v]) => (
          <div key={k} style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid ' + P.wall, padding: '4px 0' }}>
            <span style={{ fontSize: 11, color: P.ink3, fontFamily: 'JetBrains Mono, monospace' }}>{k}</span>
            <span style={{ fontSize: 11, color: P.ink, fontFamily: 'JetBrains Mono, monospace', fontWeight: 600 }}>{v}</span>
          </div>
        ))}
      </div>
      <div style={{ background: P.mintSoft, border: '1px solid ' + P.mint, padding: '8px 12px', fontSize: 11, color: P.mintDeep, marginBottom: 16, lineHeight: 1.5 }}>
        This ties up <strong>${c.bpr.toFixed(0)}</strong>. A cash-secured put on {c.underlying} at the same strike would tie up <strong>${cspCollateral.toLocaleString()}</strong>.
      </div>
      <div style={{ marginBottom: 12 }}>
        <div style={{ fontSize: 11, color: P.ink4, fontFamily: 'JetBrains Mono, monospace', textTransform: 'uppercase', marginBottom: 6 }}>RULES PASSED</div>
        {(c.rules_passed || []).map(r => (
          <div key={r} style={{ fontSize: 11, color: P.mint, marginBottom: 2 }}>{'✓ ' + r}</div>
        ))}
      </div>
      <button onClick={() => onOpenSim(c)}
        style={{ padding: '8px 16px', background: P.mint, color: '#fff', border: 'none', cursor: 'pointer', fontFamily: 'JetBrains Mono, monospace', fontSize: 11 }}>
        OPEN IN SIM →
      </button>
    </div>
  );
}

function SpreadUniverseManager({ universe, onUniverse }) {
  const [input, setInput] = React.useState('');
  const P = OPT_PALETTE;

  const add = () => {
    const t = input.trim().toUpperCase();
    if (t && !universe.includes(t)) {
      onUniverse([...universe, t]);
    }
    setInput('');
  };

  const remove = (t) => onUniverse(universe.filter(x => x !== t));

  return (
    <div style={{ marginTop: 16 }}>
      <div style={{ fontSize: 11, fontFamily: 'JetBrains Mono, monospace', color: P.ink4, textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 8 }}>
        YOUR SPREAD UNIVERSE
      </div>
      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 8 }}>
        {universe.map(t => (
          <div key={t} style={{ display: 'flex', alignItems: 'center', gap: 4, background: P.bg2, border: '1px solid ' + P.line, padding: '3px 8px', borderRadius: 2 }}>
            <span style={{ fontSize: 11, fontFamily: 'JetBrains Mono, monospace', color: P.ink }}>{t}</span>
            <span onClick={() => remove(t)} style={{ cursor: 'pointer', color: P.ink4, fontSize: 13, lineHeight: 1 }}>×</span>
          </div>
        ))}
      </div>
      <div style={{ display: 'flex', gap: 6 }}>
        <input value={input} onChange={e => setInput(e.target.value.toUpperCase())}
          onKeyDown={e => e.key === 'Enter' && add()}
          placeholder="TICKER"
          style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 11, padding: '5px 8px', border: '1px solid ' + P.line, background: P.wall, color: P.ink, width: 90 }} />
        <button onClick={add}
          style={{ padding: '5px 12px', background: P.mint, color: '#fff', border: 'none', cursor: 'pointer', fontFamily: 'JetBrains Mono, monospace', fontSize: 11 }}>
          ADD
        </button>
      </div>
    </div>
  );
}

function SpreadSim({ candidate, spreadId, onBack }) {
  const { useState, useEffect } = React;
  const P = OPT_PALETTE;

  const SELL_COLOR = '#E05252';
  const AT_RISK_COLOR = '#E07A2A';

  const STATUS_COLORS = {
    SPREAD_OPEN: P.mint,
    AT_RISK: AT_RISK_COLOR,
    EXPIRED: '#5B9BD5',
    CLOSED: P.ink4,
    IDLE: P.ink4,
  };

  function daysUntil(isoDate) {
    if (!isoDate) return null;
    var today = new Date(); today.setHours(0,0,0,0);
    var exp = new Date(isoDate); exp.setHours(0,0,0,0);
    return Math.round((exp - today) / 86400000);
  }

  const [state, setState] = useState(null);
  const [activeSpreadId, setActiveSpreadId] = useState(spreadId || null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [priceInput, setPriceInput] = useState('');
  const [closeInput, setCloseInput] = useState('');
  const [actionBusy, setActionBusy] = useState(false);
  const [actionError, setActionError] = useState(null);

  const TOKEN_HEADER = { 'X-Banshee-Token': window.__BANSHEE_TOKEN || '' };

  function loadSpread(id) {
    setLoading(true);
    setError(null);
    fetch('/paper-spreads/' + id, { headers: TOKEN_HEADER })
      .then(function(r) { return r.json(); })
      .then(function(d) { setState(d.state); setLoading(false); })
      .catch(function(e) { setError(e.message); setLoading(false); });
  }

  useEffect(function() {
    if (activeSpreadId) {
      loadSpread(activeSpreadId);
    } else if (candidate) {
      setLoading(true);
      setError(null);
      fetch('/paper-spreads', {
        method: 'POST',
        headers: Object.assign({ 'Content-Type': 'application/json' }, TOKEN_HEADER),
        body: JSON.stringify({
          symbol: candidate.underlying,
          short_strike: candidate.short_strike,
          long_strike: candidate.long_strike,
          credit: candidate.net_credit,
          expiration: candidate.expiration,
        }),
      })
        .then(function(r) { return r.json(); })
        .then(function(d) {
          setActiveSpreadId(d.id);
          setState(d.state);
          setLoading(false);
        })
        .catch(function(e) { setError(e.message); setLoading(false); });
    } else {
      setLoading(false);
    }
  }, []);

  function postEvent(eventType, data, onDone) {
    if (!activeSpreadId) return;
    setActionBusy(true);
    setActionError(null);
    fetch('/paper-spreads/' + activeSpreadId + '/event', {
      method: 'POST',
      headers: Object.assign({ 'Content-Type': 'application/json' }, TOKEN_HEADER),
      body: JSON.stringify({ event_type: eventType, data: data }),
    })
      .then(function(r) { return r.json(); })
      .then(function(d) {
        setState(d.state);
        setActionBusy(false);
        if (onDone) onDone();
      })
      .catch(function(e) { setActionError(e.message); setActionBusy(false); });
  }

  var monoFont = 'JetBrains Mono, monospace';
  var cardStyle = { background: P.bg2, border: '1px solid ' + P.line, borderRadius: 12, padding: 20, marginBottom: 16 };
  var labelStyle = { fontSize: 11, fontFamily: monoFont, color: P.ink4, textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 8 };

  if (loading) return (
    <div style={{ padding: 20, color: P.ink4, fontFamily: monoFont, fontSize: 12 }}>Opening spread...</div>
  );

  if (error) return (
    <div style={{ padding: 20 }}>
      {onBack && (
        <button onClick={onBack} style={{ background: 'transparent', border: 'none', cursor: 'pointer', padding: 0,
          fontFamily: monoFont, fontSize: 13, letterSpacing: '0.12em', textTransform: 'uppercase', color: '#FF6D00', fontWeight: 700, marginBottom: 16 }}>
          ← BACK
        </button>
      )}
      <div style={{ color: SELL_COLOR, fontSize: 12, fontFamily: monoFont }}>Error: {error}</div>
    </div>
  );

  if (!activeSpreadId && !candidate) return (
    <div style={{ padding: 20 }}>
      {onBack && (
        <button onClick={onBack} style={{ background: 'transparent', border: 'none', cursor: 'pointer', padding: 0,
          fontFamily: monoFont, fontSize: 13, letterSpacing: '0.12em', textTransform: 'uppercase', color: '#FF6D00', fontWeight: 700, marginBottom: 16 }}>
          ← BACK
        </button>
      )}
      <div style={{ color: P.ink4, fontSize: 12, fontFamily: monoFont }}>No position selected.</div>
    </div>
  );

  if (!state) return (
    <div style={{ padding: 20, color: P.ink4, fontFamily: monoFont, fontSize: 12 }}>No data available.</div>
  );

  var status = state.status || 'IDLE';
  var statusColor = STATUS_COLORS[status] || P.ink4;
  var currentPrice = state.current_price != null ? state.current_price : null;
  var shortStrike = state.short_strike != null ? state.short_strike : null;
  var buffer = (currentPrice != null && shortStrike != null) ? (currentPrice - shortStrike) : null;
  var underlying = state.symbol || (candidate ? candidate.underlying : null);
  var expiration = state.expiration || null;
  var dte = daysUntil(expiration);

  var credit = state.credit != null ? state.credit : 0;
  var maxProfit = credit * 100;
  var unrealizedPnl = state.unrealized_pnl != null ? state.unrealized_pnl : null;
  var realizedPnl = state.realized_pnl != null ? state.realized_pnl : null;
  var isClosed = status === 'EXPIRED' || status === 'CLOSED';
  var activePnl = isClosed ? realizedPnl : unrealizedPnl;
  var showBar = status !== 'IDLE';
  var pnlPositive = activePnl != null && activePnl >= 0;

  var barFillPct = 0;
  if (showBar && activePnl != null && maxProfit > 0) {
    if (pnlPositive) {
      barFillPct = Math.min(100, (activePnl / maxProfit) * 100);
    } else {
      var maxLoss = (shortStrike != null && state.long_strike != null)
        ? (shortStrike - state.long_strike) * 100 - maxProfit
        : maxProfit;
      barFillPct = maxLoss > 0 ? Math.min(100, (Math.abs(activePnl) / maxLoss) * 100) : 0;
    }
  }

  var barFillColor = pnlPositive ? P.mint : SELL_COLOR;

  var pnlLabel = '';
  if (showBar && activePnl != null) {
    if (pnlPositive) {
      var pct = maxProfit > 0 ? ((activePnl / maxProfit) * 100).toFixed(1) : '0.0';
      pnlLabel = '+$' + activePnl.toFixed(2) + ' of $' + maxProfit.toFixed(2) + ' max profit (' + pct + '%)';
    } else {
      var maxLossAmt = (shortStrike != null && state.long_strike != null)
        ? (shortStrike - state.long_strike) * 100 - maxProfit
        : maxProfit;
      var lossPct = maxLossAmt > 0 ? ((Math.abs(activePnl) / maxLossAmt) * 100).toFixed(1) : '0.0';
      pnlLabel = '−$' + Math.abs(activePnl).toFixed(2) + ' unrealized (' + lossPct + '% of max loss)';
    }
  }

  var isActionable = status === 'SPREAD_OPEN' || status === 'AT_RISK';

  var events = state.events || [];
  var eventsDesc = events.slice().reverse();

  return (
    <div style={{ maxWidth: 680 }}>
      {onBack && (
        <button onClick={onBack} style={{ background: 'transparent', border: 'none', cursor: 'pointer', padding: 0,
          fontFamily: monoFont, fontSize: 13, letterSpacing: '0.12em', textTransform: 'uppercase', color: '#FF6D00', fontWeight: 700, marginBottom: 16 }}>
          ← BACK
        </button>
      )}

      {/* Status + Strike Proximity */}
      <div style={cardStyle}>
        <div style={labelStyle}>POSITION STATUS</div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 14 }}>
          <span style={{ background: statusColor, color: '#fff', fontFamily: monoFont, fontSize: 11,
            fontWeight: 700, letterSpacing: '0.1em', padding: '3px 10px', borderRadius: 4 }}>
            {status}
          </span>
        </div>
        <div style={{ fontFamily: monoFont, fontSize: 12, color: P.ink, lineHeight: 1.8 }}>
          <span>{underlying != null ? underlying : '—'}</span>
          {' '}
          <span style={{ fontWeight: 700 }}>{currentPrice != null ? '$' + currentPrice.toFixed(2) : '—'}</span>
          {' — Short strike '}
          <span style={{ fontWeight: 700 }}>{shortStrike != null ? '$' + shortStrike.toFixed(2) : '—'}</span>
          {' — '}
          <span style={{ color: buffer != null && buffer >= 0 ? P.mint : SELL_COLOR, fontWeight: 700 }}>
            {buffer != null ? buffer.toFixed(2) : '—'}
          </span>
          {' buffer'}
        </div>
      </div>

      {/* P&L Bar */}
      {showBar && (
        <div style={cardStyle}>
          <div style={labelStyle}>P&L</div>
          <div style={{ fontFamily: monoFont, fontSize: 12, color: pnlPositive ? P.mint : SELL_COLOR, marginBottom: 8 }}>
            {pnlLabel || '—'}
          </div>
          <div style={{ background: P.bg3, borderRadius: 4, height: 12, overflow: 'hidden' }}>
            <div style={{ width: barFillPct + '%', height: '100%', background: barFillColor, borderRadius: 4, transition: 'width 0.3s' }} />
          </div>
        </div>
      )}

      {/* DTE Countdown */}
      <div style={cardStyle}>
        <div style={labelStyle}>EXPIRATION</div>
        {dte === 0
          ? <div style={{ fontFamily: monoFont, fontSize: 12, color: AT_RISK_COLOR }}>Expiration today. Broker auto-close window: ~3:15 PM ET.</div>
          : <div style={{ fontFamily: monoFont, fontSize: 12, color: P.ink }}>
              {dte != null ? dte + ' days remaining' : '—'}
              {expiration ? ' (' + expiration + ')' : ''}
            </div>
        }
      </div>

      {/* Action Buttons */}
      {isActionable && (
        <div style={cardStyle}>
          <div style={labelStyle}>ACTIONS</div>
          {actionError && (
            <div style={{ fontFamily: monoFont, fontSize: 11, color: SELL_COLOR, marginBottom: 10 }}>
              {'Error: ' + actionError}
            </div>
          )}

          {/* UPDATE PRICE */}
          <div style={{ marginBottom: 14 }}>
            <div style={{ fontSize: 11, fontFamily: monoFont, color: P.ink4, textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 6 }}>Update current price</div>
            <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              <input
                type="number"
                step="0.01"
                value={priceInput}
                onChange={function(e) { setPriceInput(e.target.value); }}
                placeholder="e.g. 485.50"
                style={{ fontFamily: monoFont, fontSize: 12, padding: '5px 8px', border: '1px solid ' + P.line,
                  background: P.wall || P.bg3, color: P.ink, width: 120 }}
              />
              <button
                disabled={actionBusy || !priceInput}
                onClick={function() {
                  var val = parseFloat(priceInput);
                  if (isNaN(val)) return;
                  postEvent('PRICE_UPDATE', { current_underlying_price: val }, function() { setPriceInput(''); });
                }}
                style={{ padding: '5px 14px', background: P.mint, color: '#fff', border: 'none', cursor: 'pointer',
                  fontFamily: monoFont, fontSize: 11, opacity: (actionBusy || !priceInput) ? 0.5 : 1 }}>
                UPDATE
              </button>
            </div>
          </div>

          {/* EXPIRE WORTHLESS */}
          <div style={{ marginBottom: 14 }}>
            <div style={{ fontSize: 11, fontFamily: monoFont, color: P.ink4, textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 6 }}>Expired worthless</div>
            <button
              disabled={actionBusy}
              onClick={function() { postEvent('EXPIRE_WORTHLESS', {}); }}
              style={{ padding: '5px 14px', background: P.bg3, color: P.ink, border: '1px solid ' + P.line, cursor: 'pointer',
                fontFamily: monoFont, fontSize: 11, opacity: actionBusy ? 0.5 : 1 }}>
              EXPIRED WORTHLESS
            </button>
          </div>

          {/* CLOSE SPREAD */}
          <div>
            <div style={{ fontSize: 11, fontFamily: monoFont, color: P.ink4, textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 6 }}>Close spread (cost to buy back)</div>
            <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              <input
                type="number"
                step="0.01"
                value={closeInput}
                onChange={function(e) { setCloseInput(e.target.value); }}
                placeholder="e.g. 0.15"
                style={{ fontFamily: monoFont, fontSize: 12, padding: '5px 8px', border: '1px solid ' + P.line,
                  background: P.wall || P.bg3, color: P.ink, width: 120 }}
              />
              <button
                disabled={actionBusy || !closeInput}
                onClick={function() {
                  var closeCost = parseFloat(closeInput);
                  if (isNaN(closeCost)) return;
                  postEvent('CLOSE_SPREAD', { close_cost: closeCost, realized_pnl: (credit - closeCost) * 100 }, function() { setCloseInput(''); });
                }}
                style={{ padding: '5px 14px', background: P.bg3, color: P.ink, border: '1px solid ' + P.line, cursor: 'pointer',
                  fontFamily: monoFont, fontSize: 11, opacity: (actionBusy || !closeInput) ? 0.5 : 1 }}>
                CLOSE
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Event Log */}
      <div style={cardStyle}>
        <div style={labelStyle}>EVENT LOG</div>
        {eventsDesc.length === 0
          ? <div style={{ fontFamily: monoFont, fontSize: 12, color: P.ink4 }}>No events yet.</div>
          : eventsDesc.map(function(ev, i) {
              var dataStr = ev.data && Object.keys(ev.data).length > 0
                ? Object.entries(ev.data).map(function(pair) { return pair[0] + ': ' + pair[1]; }).join(' | ')
                : '';
              return (
                <div key={i} style={{ borderBottom: i < eventsDesc.length - 1 ? '1px solid ' + P.line : 'none',
                  padding: '8px 0', display: 'flex', gap: 12 }}>
                  <span style={{ fontFamily: monoFont, fontSize: 11, color: P.ink4, flexShrink: 0 }}>
                    {ev.timestamp ? ev.timestamp.slice(0, 19).replace('T', ' ') : '—'}
                  </span>
                  <span style={{ fontFamily: monoFont, fontSize: 11, color: P.mint, fontWeight: 700, flexShrink: 0 }}>
                    {ev.event_type}
                  </span>
                  {dataStr && (
                    <span style={{ fontFamily: monoFont, fontSize: 11, color: P.ink }}>
                      {dataStr}
                    </span>
                  )}
                </div>
              );
            })
        }
      </div>
    </div>
  );
}

function SpreadGrader({ tier }) {
  const { useState } = React;
  const P = OPT_PALETTE;

  const TIERS = ['starter', 'building', 'established', 'institutional'];

  const [symbol, setSymbol] = useState('');
  const [shortStrike, setShortStrike] = useState('');
  const [longStrike, setLongStrike] = useState('');
  const [netCredit, setNetCredit] = useState('');
  const [expiration, setExpiration] = useState('');
  const [capitalTier, setCapitalTier] = useState(tier || 'starter');
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const inputStyle = {
    background: P.bg3,
    border: '1px solid ' + P.line,
    color: P.ink,
    borderRadius: 6,
    padding: '6px 10px',
    outline: 'none',
    width: '100%',
    boxSizing: 'border-box',
    fontFamily: 'JetBrains Mono, monospace',
    fontSize: 12,
  };

  const labelStyle = {
    display: 'block',
    fontSize: 10,
    letterSpacing: '0.08em',
    color: P.ink4,
    marginBottom: 4,
    fontFamily: 'JetBrains Mono, monospace',
  };

  const handleGrade = async () => {
    setError(null);
    if (!symbol || !shortStrike || !longStrike || !netCredit || !expiration || !capitalTier) {
      setError('All fields are required.');
      return;
    }
    const ss = parseFloat(shortStrike);
    const ls = parseFloat(longStrike);
    if (isNaN(ss) || isNaN(ls)) {
      setError('Strike prices must be numbers.');
      return;
    }
    if (ls >= ss) {
      setError('Long strike must be below short strike.');
      return;
    }
    setLoading(true);
    try {
      const resp = await fetch('/options/grade-spread', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Banshee-Token': window.__BANSHEE_TOKEN || '',
        },
        body: JSON.stringify({
          symbol: symbol.toUpperCase(),
          short_strike: ss,
          long_strike: ls,
          net_credit: parseFloat(netCredit),
          expiration: expiration,
          capital_tier: capitalTier,
        }),
      });
      if (!resp.ok) {
        const txt = await resp.text();
        throw new Error(txt || resp.statusText);
      }
      const data = await resp.json();
      setResults(data);
    } catch (e) {
      setError(e.message || 'Request failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ background: P.bg2, border: '1px solid ' + P.line, borderRadius: 12, padding: 20 }}>
      <div style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 11, letterSpacing: '0.08em', color: P.ink4, marginBottom: 16 }}>
        GRADE A SPREAD
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 12 }}>
        <div>
          <label style={labelStyle}>UNDERLYING</label>
          <input
            style={inputStyle}
            type="text"
            value={symbol}
            onChange={e => setSymbol(e.target.value.toUpperCase())}
            placeholder="e.g. NVDA"
          />
        </div>
        <div>
          <label style={labelStyle}>EXPIRATION DATE</label>
          <input
            style={inputStyle}
            type="date"
            value={expiration}
            onChange={e => setExpiration(e.target.value)}
          />
        </div>
        <div>
          <label style={labelStyle}>SHORT PUT STRIKE</label>
          <input
            style={inputStyle}
            type="number"
            value={shortStrike}
            onChange={e => setShortStrike(e.target.value)}
            placeholder="e.g. 800"
          />
        </div>
        <div>
          <label style={labelStyle}>LONG PUT STRIKE (below short)</label>
          <input
            style={inputStyle}
            type="number"
            value={longStrike}
            onChange={e => setLongStrike(e.target.value)}
            placeholder="e.g. 795"
          />
        </div>
        <div>
          <label style={labelStyle}>NET CREDIT / SHARE ($)</label>
          <input
            style={inputStyle}
            type="number"
            step="0.01"
            value={netCredit}
            onChange={e => setNetCredit(e.target.value)}
            placeholder="e.g. 1.50"
          />
        </div>
        <div>
          <label style={labelStyle}>CAPITAL TIER</label>
          <select
            style={Object.assign({}, inputStyle, { cursor: 'pointer' })}
            value={capitalTier}
            onChange={e => setCapitalTier(e.target.value)}
          >
            {TIERS.map(t => (
              <option key={t} value={t}>{t}</option>
            ))}
          </select>
        </div>
      </div>

      <button
        onClick={handleGrade}
        disabled={loading}
        style={{
          background: loading ? P.ink4 : P.mint,
          border: 'none',
          color: '#fff',
          borderRadius: 6,
          padding: '8px 20px',
          fontFamily: 'JetBrains Mono, monospace',
          fontSize: 11,
          letterSpacing: '0.1em',
          cursor: loading ? 'default' : 'pointer',
          marginBottom: 16,
        }}
      >
        {loading ? 'GRADING...' : 'GRADE SPREAD'}
      </button>

      {error && (
        <div style={{ color: '#D94A4A', fontSize: 12, fontFamily: 'JetBrains Mono, monospace', marginBottom: 12 }}>
          {error}
        </div>
      )}

      {results && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {results.map((r, i) => (
            <div key={i} style={{
              background: P.card,
              border: '1px solid ' + P.line,
              borderRadius: 8,
              padding: '8px 12px',
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{
                  fontSize: 13,
                  color: r.passed ? P.mint : '#D94A4A',
                  fontWeight: 700,
                }}>
                  {r.passed ? '✓' : '✗'}
                </span>
                <span style={{
                  fontFamily: 'JetBrains Mono, monospace',
                  fontSize: 12,
                  color: P.ink,
                }}>
                  {r.rule}
                </span>
              </div>
              {!r.passed && r.reason && (
                <div style={{
                  fontFamily: 'JetBrains Mono, monospace',
                  fontSize: 10,
                  color: P.ink4,
                  marginTop: 4,
                  paddingLeft: 21,
                }}>
                  {r.reason}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {!results && !loading && !error && (
        <div style={{ color: P.ink4, fontSize: 11, fontFamily: 'JetBrains Mono, monospace' }}>
          Fill in the fields above and click GRADE SPREAD to see results.
        </div>
      )}
    </div>
  );
}

function SpreadTrack({ tier }) {
  const { useState } = React;
  const P = OPT_PALETTE;
  const [universe, setUniverse] = useState(
    () => JSON.parse(localStorage.getItem('banshee_spread_universe') || '[]')
  );
  const [simCandidate, setSimCandidate] = useState(null);
  const [view, setView] = useState('calm');

  const handleUniverse = (u) => {
    setUniverse(u);
    localStorage.setItem('banshee_spread_universe', JSON.stringify(u));
  };

  return (
    <div>
      <div style={{ display: 'flex', gap: 12, marginBottom: 20, borderBottom: '1px solid ' + P.line, paddingBottom: 12 }}>
        {[['calm', 'CALM ROOM'], ['sim', 'SIM'], ['grader', 'GRADER']].map(([k, label]) => (
          <button key={k} onClick={() => setView(k)}
            style={{ background: 'none', border: 'none', cursor: 'pointer', padding: '4px 0',
              fontFamily: 'JetBrains Mono, monospace', fontSize: 11, letterSpacing: '0.08em',
              color: view === k ? P.mint : P.ink4,
              borderBottom: view === k ? '2px solid ' + P.mint : '2px solid transparent' }}>
            {label}
          </button>
        ))}
      </div>
      {view === 'calm' && (
        <div>
          <SpreadCalmRoom tier={tier} universe={universe} onOpenSim={c => { setSimCandidate(c); setView('sim'); }} />
          <SpreadUniverseManager universe={universe} onUniverse={handleUniverse} />
        </div>
      )}
      {view === 'sim' && <SpreadSim candidate={simCandidate} spreadId={null} onBack={() => setView('calm')} />}
      {view === 'grader' && <SpreadGrader tier={tier} />}
    </div>
  );
}

function OptionsPage({ onBack }) {
  const P = OPT_PALETTE;
  const [tier, setTier] = React.useState(
    () => localStorage.getItem('banshee_capital_tier') || 'starter'
  );
  const [activeTrack, setActiveTrack] = React.useState(null);

  const handleTier = (t) => {
    setTier(t);
    localStorage.setItem('banshee_capital_tier', t);
    setActiveTrack(null);
  };
  const handleTrack = (t) => setActiveTrack(t);
  const resolvedTrack = activeTrack || TIER_DEFAULT_TRACK[tier] || 'spreads';

  const [data, setData] = React.useState(null);
  const [loading, setLoading] = React.useState(true);
  const [acct, setAcct] = React.useState(() => localStorage.getItem('banshee_options_acct') || '');
  // optView: "calm" | "list" | "tracker" | "paperList" | "paperTracker"
  const [optView, setOptView] = React.useState("calm");
  const [wheel, setWheel] = React.useState(null);
  const [selectedPaperWheelId, setSelectedPaperWheelId] = React.useState(null);
  const [runError, setRunError] = React.useState(null);
  const [teach, setTeach] = useTeachMode();

  const runWheel = React.useCallback(async (candidate) => {
    setRunError(null);
    const w = await window.API.createWheel({
      candidate_snapshot: candidate,
      underlying: candidate.underlying,
      name: candidate.underlying + " Wheel",
    });
    if (w && !w.error) { setWheel(w); setOptView("tracker"); }
    else { setRunError((w && w.error) || "Couldn't start the simulated wheel — try again."); }
  }, []);

  const goToPaperWheel = React.useCallback((id) => {
    setSelectedPaperWheelId(id);
    setOptView("paperTracker");
  }, []);

  const load = React.useCallback(() => {
    setLoading(true);
    window.API.fetchOptionsCandidate(acct || null)
      .then(d => { setData(d); setLoading(false); })
      .catch(() => { setData({ candidate: null, error_note: "Options scan unavailable — try again in a moment." }); setLoading(false); });
  }, [acct]);
  React.useEffect(() => { load(); }, []);   // initial scan only; acct re-scan is manual via blur

  const lab = { fontSize: 12, letterSpacing: '0.14em', textTransform: 'uppercase', fontWeight: 700 };
  const shell = (children) => (
    <div style={{ position: 'absolute', inset: 0, zIndex: 30, overflowY: 'auto',
      background: P.wall, color: P.ink, fontFamily: 'monospace', padding: '22px 28px' }}>
      <div style={{ maxWidth: 760, margin: '0 auto' }}>{children}</div>
    </div>
  );

  if (optView === "list") {
    return shell(<WheelList onOpened={(w) => { setWheel(w); setOptView("tracker"); }} onBack={() => setOptView("calm")} />);
  }
  if (optView === "tracker" && wheel) {
    return shell(<WheelTracker wheel={wheel} setWheel={setWheel} onBack={() => setOptView("list")} />);
  }
  if (optView === "paperList") {
    return shell(
      <PaperWheelList
        onSelect={goToPaperWheel}
        onNew={() => setOptView("calm")}
        onBack={() => setOptView("calm")}
      />
    );
  }
  if (optView === "paperTracker" && selectedPaperWheelId) {
    return shell(
      <PaperWheelTracker
        wheelId={selectedPaperWheelId}
        onBack={() => setOptView("paperList")}
      />
    );
  }

  return shell(
    <>
      <CapitalTierSelector tier={tier} onTier={handleTier} />
      <InstitutionalFramingPanel tier={tier} />
      <TrackForkCards tier={tier} activeTrack={activeTrack} onTrack={handleTrack} />
      {resolvedTrack === 'wheel' && (
      <div>
      <button onClick={onBack} style={{ background: 'transparent', border: 'none', cursor: 'pointer', padding: 0,
        fontFamily: 'monospace', fontSize: 13, letterSpacing: '0.12em', textTransform: 'uppercase', color: '#FF6D00', fontWeight: 700, marginBottom: 16 }}>← BACK</button>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 14, flexWrap: 'wrap' }}>
        <div style={{ ...lab, fontSize: 12, letterSpacing: '0.18em', color: P.mintDeep }}>◆ OPTIONS · ONE CONSERVATIVE PLAY, EXPLAINED</div>
        <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
          <button onClick={() => setOptView("paperList")} style={{
            background: 'transparent', border: `1px solid ${P.mint}`, borderRadius: 5,
            cursor: 'pointer', fontFamily: 'monospace', fontSize: 12, letterSpacing: '0.08em',
            textTransform: 'uppercase', fontWeight: 700, color: P.mintDeep, padding: '5px 12px' }}>
            PAPER TRADES →
          </button>
          <TeachToggle on={teach} setOn={setTeach} />
        </div>
      </div>
      <div style={{ fontSize: 23, fontWeight: 700, margin: '7px 0 6px' }}>First, what an option actually is.</div>
      <Teach teach={teach} title="What an option is">
        An option is a contract between two people about a price in the future. One side <b>pays cash now</b> for
        the right to buy or sell at a set price; the other side <b>collects that cash</b> and takes on the matching
        obligation. This page puts you on the cash-collecting side of the most conservative version of that deal —
        and explains every part as you go. It isn't a product or free income: it's a real trade with a real upside
        and a real obligation, and the goal is that you can explain both before you'd ever consider doing it.
      </Teach>
      <div style={{ fontSize: 14, color: P.ink3, lineHeight: 1.65, maxWidth: 600, margin: '10px 0 18px' }}>
        Banshee doesn't pick for you — it <b>searches</b> the broad-fund options and shows you the ones that clear
        every safety rule. What you do next is your call.
      </div>

      <div style={{ marginBottom: 16 }}>
        <label style={{ ...lab, color: P.ink4, marginRight: 8 }}>Account size (optional)</label>
        <input value={acct} placeholder="e.g. 200000"
          onChange={e => setAcct(e.target.value.replace(/[^0-9]/g, ''))}
          onBlur={() => { localStorage.setItem('banshee_options_acct', acct); load(); }}
          style={{ fontFamily: 'monospace', fontSize: 13, padding: '5px 9px', width: 130,
            background: P.card, color: P.ink, border: `1px solid ${P.line}`, borderRadius: 6 }} />
      </div>

      {loading && <div style={{ fontSize: 14, color: P.ink3, letterSpacing: '0.1em' }}>◇ SCANNING THE WHEEL UNIVERSE…</div>}

      <PaperAlertStrip onGoToWheel={goToPaperWheel} />

      {!loading && data && data.candidate && (
        <>
          <OptCard data={data} teach={teach} onRunWheel={runWheel} onSeeWheels={() => setOptView("list")} onPaperTrade={goToPaperWheel} runError={runError} />
          <OptControlPanel data={data} />
          <OptGrader candidate={data.candidate} />
          {data.low_iv_warning && (
            <div style={{ marginTop: 16, maxWidth: 620, background: P.amberBg, border: `1px solid ${P.amberLine}`,
              borderRadius: 8, padding: '12px 15px', display: 'flex', gap: 9 }}>
              <span style={{ color: P.amber, fontSize: 16 }}>⚠</span>
              <div>
                <div style={{ ...lab, fontSize: 12, color: P.amber }}>When premium looks too good</div>
                <div style={{ fontSize: 13, color: '#6b5118', lineHeight: 1.6, marginTop: 3 }}>
                  This premium is unusually rich right now — that often means a known event is near (earnings, Fed, CPI). Fat premium is pay for that risk, not free money. The Wheel usually waits until after.
                </div>
              </div>
            </div>
          )}
          {data.partial_failures && data.partial_failures.length > 0 && (
            <div style={{ marginTop: 12, fontSize: 13, color: P.ink3, fontStyle: 'italic' }}>
              Couldn't read {data.partial_failures.join(', ')} this scan; showing the best of what loaded.
            </div>
          )}
        </>
      )}

      {!loading && data && !data.candidate && (
        <>
          {data.account_too_small ? (
            <div style={{ maxWidth: 620, background: P.amberBg, border: `1px solid ${P.amberLine}`,
              borderRadius: 10, padding: '16px 18px' }}>
              <div style={{ ...lab, fontSize: 12, color: P.amber }}>This isn't for you yet — and that's okay</div>
              <div style={{ fontSize: 15, fontWeight: 700, color: '#6b5118', margin: '8px 0 6px' }}>
                With ${Number(data.account_too_small.account_size).toLocaleString()} on hand, no Wheel-grade trade fits your 5% safety limit.
              </div>
              <div style={{ fontSize: 14, color: '#6b5118', lineHeight: 1.7 }}>
                A cash-secured put means setting aside the <b>whole</b> price of the shares you'd be promising to buy —
                the cheapest qualifying one here needs about <b>${Number(data.account_too_small.cheapest_collateral).toLocaleString()}</b> in cash.
                Banshee's 5%-per-trade rule means one trade can't use more than <b>${Number(data.account_too_small.max_per_trade).toLocaleString()}</b> of your account.
                To run these broad funds safely, you'd want an account around <b>${Number(data.account_too_small.min_account_for_5pct).toLocaleString()}</b> — or wait for a cheaper qualifying fund.
              </div>
            </div>
          ) : (
            <div style={{ maxWidth: 620, background: P.card, border: `1px solid ${P.line}`, borderRadius: 10, padding: '16px 18px', fontSize: 14, color: P.ink3, lineHeight: 1.6 }}>
              {data.error_note || "No Wheel-grade setups right now — premiums are too thin to justify the risk. That's the system protecting you, not a bug."}
            </div>
          )}
          <button onClick={() => setOptView("list")} style={{
            marginTop: 14, background: 'transparent', border: 'none', cursor: 'pointer', padding: 0,
            fontFamily: 'monospace', fontSize: 12, letterSpacing: '0.12em', textTransform: 'uppercase',
            fontWeight: 700, color: P.mintDeep }}>
            MY SIMULATED WHEELS →
          </button>
        </>
      )}
      </div>
      )}
      {resolvedTrack === 'spreads' && (
        <SpreadTrack tier={tier} />
      )}
    </>
  );
}

window.OptionsPage = OptionsPage;
