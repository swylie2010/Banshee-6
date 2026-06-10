/* Banshee — Options "The Calm Room" (Phase 1, The Wheel)
 * Banshee's native chassis (monospace, uppercase micro-labels, bordered cards)
 * recolored mint. Scoped palette only — does not touch the rest of the app.
 * Font floor on this page is 12px (one above the app's 11 floor). */

const OPT_PALETTE = {
  mint: '#1F9D6E', mintDeep: '#147A55', mintSoft: '#D5EEE2', wall: '#E7F4EE',
  card: '#F4FBF7', bg2: '#DCF0E7', bg3: '#CDE8DC', ink: '#16352A', ink3: '#5C7A6D',
  ink4: '#7C9789', line: '#BCDFCF', amber: '#9A6A18', amberBg: '#F6EBCF', amberLine: '#E4CE94',
};

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

function OptCard({ data, onRunWheel, onSeeWheels, runError }) {
  const P = OPT_PALETTE;
  const c = data.candidate, t = data.translation;
  const premium = Math.round(c.mid * 100);
  const num = (label, value) => (
    <div style={{ padding: '12px 20px 4px 0' }}>
      <div style={{ fontSize: 12, letterSpacing: '0.14em', textTransform: 'uppercase', fontWeight: 700, color: P.ink4 }}>{label}</div>
      <div style={{ fontSize: 19, fontWeight: 700, marginTop: 3, color: P.ink }}>{value}</div>
    </div>
  );
  return (
    <div style={{ background: P.card, border: `1px solid ${P.line}`, borderRadius: 10, padding: '18px 20px', maxWidth: 620 }}>
      <span style={{ display: 'inline-block', fontSize: 12, letterSpacing: '0.14em', textTransform: 'uppercase',
        fontWeight: 700, color: P.mintDeep, border: `1px solid ${P.mint}`, borderRadius: 5, padding: '3px 9px' }}>
        ◆ CASH-SECURED PUT · {c.underlying}
      </span>
      <div style={{ fontSize: 18, fontWeight: 700, margin: '13px 0 12px', color: P.ink }}>{t.headline}</div>
      <div style={{ fontSize: 12, letterSpacing: '0.14em', textTransform: 'uppercase', fontWeight: 700, color: P.ink4, marginBottom: 6 }}>In plain English</div>
      <div style={{ fontSize: 14, lineHeight: 1.7, color: '#234034', background: P.mintSoft,
        borderLeft: `3px solid ${P.mint}`, padding: '12px 15px', borderRadius: '0 6px 6px 0' }}>{t.plain_english}</div>
      <div style={{ display: 'flex', flexWrap: 'wrap', margin: '16px 0 2px', borderTop: `1px solid ${P.line}` }}>
        {num('You collect', `$${premium.toLocaleString()}`)}
        {num('Cash set aside', `$${c.collateral.toLocaleString()}`)}
        {num('Breakeven', `$${c.breakeven.toLocaleString()}`)}
        {num('Odds you keep it', `${Math.round(c.prob_keep * 100)}%`)}
        {num('Days', `${c.dte}`)}
        {num('Safety', `✓ Δ${Math.abs(c.delta).toFixed(2)}${c.ivr_estimate != null ? ` · IVR ${Math.round(c.ivr_estimate)} est.` : ''}`)}
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

function OptionsPage({ onBack }) {
  const P = OPT_PALETTE;
  const [data, setData] = React.useState(null);
  const [loading, setLoading] = React.useState(true);
  const [acct, setAcct] = React.useState(() => localStorage.getItem('banshee_options_acct') || '');
  const [optView, setOptView] = React.useState("calm");   // "calm" | "list" | "tracker"
  const [wheel, setWheel] = React.useState(null);
  const [runError, setRunError] = React.useState(null);

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
      <div style={{ ...lab, fontSize: 12, letterSpacing: '0.18em', color: P.mintDeep }}>◆ THE WHEEL · A CALM WAY TO EARN INCOME</div>
      <div style={{ fontSize: 23, fontWeight: 700, margin: '7px 0 4px' }}>Here's one good move to consider</div>
      <div style={{ fontSize: 14, color: P.ink3, lineHeight: 1.65, maxWidth: 580, marginBottom: 18 }}>
        The Wheel pays you to offer to buy a solid fund at a discount. Banshee only surfaces a move once it clears every safety rule — nothing to hunt for.
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
          <OptCard data={data} onRunWheel={runWheel} onSeeWheels={() => setOptView("list")} runError={runError} />
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
          <div style={{ maxWidth: 620, background: P.card, border: `1px solid ${P.line}`, borderRadius: 10, padding: '16px 18px', fontSize: 14, color: P.ink3, lineHeight: 1.6 }}>
            {data.error_note || "No Wheel-grade setups right now — premiums are too thin to justify the risk. That's the system protecting you, not a bug."}
          </div>
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
