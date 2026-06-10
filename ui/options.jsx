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

function OptCard({ data, teach, onRunWheel, onSeeWheels, runError }) {
  const P = OPT_PALETTE;
  const c = data.candidate, t = data.translation;
  const premium = Math.round(c.mid * 100);
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
        <button onClick={onSeeWheels} style={{
          background: 'transparent', border: 'none', cursor: 'pointer', padding: 0,
          fontFamily: 'monospace', fontSize: 12, letterSpacing: '0.12em', textTransform: 'uppercase',
          fontWeight: 700, color: P.mintDeep }}>
          MY SIMULATED WHEELS →
        </button>
      </div>
      <OptError msg={runError} />
    </div>
  );
}

/* currency formatter — null-safe; returns null so callers can omit a row */
function optMoney(v) {
  if (v == null || isNaN(v)) return null;
  const sign = v < 0 ? '-' : '';
  return `${sign}$${Math.abs(v).toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
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
    </div>
  );
}

/* The safety rules as dials at SAFE — each teaches its rule and (statically)
   what loosening it would cost. The runnable calm/crash sim is Spec 2. */
function OptControlPanel({ data }) {
  const P = OPT_PALETTE;
  const [openKey, setOpenKey] = React.useState(null);
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
              <div style={{ marginTop: 6 }}>
                <button onClick={() => setOpenKey(openKey === d.key ? null : d.key)} style={{
                  background: 'transparent', border: 'none', cursor: 'pointer', padding: 0,
                  fontFamily: 'monospace', fontSize: 12, fontWeight: 700, color: P.amber }}>
                  {openKey === d.key ? '▾ what loosening this costs' : '› what loosening this costs'}
                </button>
                {openKey === d.key && (
                  <div style={{ fontSize: 13, color: '#6b5118', lineHeight: 1.6, marginTop: 5,
                    background: P.amberBg, border: `1px solid ${P.amberLine}`, borderRadius: 6, padding: '9px 12px' }}>
                    🔥 {d.loosen}
                  </div>
                )}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

/* Compose-your-own option → Banshee grades it rule-by-rule (the inverse search). */
function OptGrader() {
  const P = OPT_PALETTE;
  const [spec, setSpec] = React.useState({ underlying: 'SPY', strike: '', dte: '42', cash_backed: true, account_size: '' });
  const [res, setRes] = React.useState(null);
  const [busy, setBusy] = React.useState(false);
  const [err, setErr] = React.useState(null);
  const lab = { fontSize: 12, letterSpacing: '0.14em', textTransform: 'uppercase', fontWeight: 700 };
  const inp = { fontFamily: 'monospace', fontSize: 13, padding: '6px 9px', background: P.card,
    color: P.ink, border: `1px solid ${P.line}`, borderRadius: 6 };

  const grade = async () => {
    setBusy(true); setErr(null); setRes(null);
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
        </div>
      )}
    </div>
  );
}

function OptionsPage({ onBack }) {
  const P = OPT_PALETTE;
  const [data, setData] = React.useState(null);
  const [loading, setLoading] = React.useState(true);
  const [acct, setAcct] = React.useState(() => localStorage.getItem('banshee_options_acct') || '');
  const [optView, setOptView] = React.useState("calm");   // "calm" | "list" | "tracker"
  const [wheel, setWheel] = React.useState(null);
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

  return shell(
    <>
      <button onClick={onBack} style={{ background: 'transparent', border: 'none', cursor: 'pointer', padding: 0,
        fontFamily: 'monospace', fontSize: 13, letterSpacing: '0.12em', textTransform: 'uppercase', color: '#FF6D00', fontWeight: 700, marginBottom: 16 }}>← BACK</button>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 14, flexWrap: 'wrap' }}>
        <div style={{ ...lab, fontSize: 12, letterSpacing: '0.18em', color: P.mintDeep }}>◆ OPTIONS · ONE CONSERVATIVE PLAY, EXPLAINED</div>
        <TeachToggle on={teach} setOn={setTeach} />
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

      {!loading && data && data.candidate && (
        <>
          <OptCard data={data} teach={teach} onRunWheel={runWheel} onSeeWheels={() => setOptView("list")} runError={runError} />
          <OptControlPanel data={data} />
          <OptGrader />
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
    </>
  );
}

window.OptionsPage = OptionsPage;
