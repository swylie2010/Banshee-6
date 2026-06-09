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

function OptCard({ data }) {
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
    </div>
  );
}

function OptionsPage({ onBack }) {
  const P = OPT_PALETTE;
  const [data, setData] = React.useState(null);
  const [loading, setLoading] = React.useState(true);
  const [acct, setAcct] = React.useState(() => localStorage.getItem('banshee_options_acct') || '');

  const load = React.useCallback(() => {
    setLoading(true);
    window.API.fetchOptionsCandidate(acct || null)
      .then(d => { setData(d); setLoading(false); })
      .catch(() => { setData({ candidate: null, error_note: "Options scan unavailable — try again in a moment." }); setLoading(false); });
  }, [acct]);
  React.useEffect(() => { load(); }, []);   // initial scan only; acct re-scan is manual via blur

  const lab = { fontSize: 12, letterSpacing: '0.14em', textTransform: 'uppercase', fontWeight: 700 };
  return (
    <div style={{ position: 'absolute', inset: 0, zIndex: 30, overflowY: 'auto',
      background: P.wall, color: P.ink, fontFamily: 'monospace', padding: '22px 28px' }}>
      <div style={{ maxWidth: 760, margin: '0 auto' }}>
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
          <OptCard data={data} />
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
        <div style={{ maxWidth: 620, background: P.card, border: `1px solid ${P.line}`, borderRadius: 10, padding: '16px 18px', fontSize: 14, color: P.ink3, lineHeight: 1.6 }}>
          {data.error_note || "No Wheel-grade setups right now — premiums are too thin to justify the risk. That's the system protecting you, not a bug."}
        </div>
      )}
      </div>
    </div>
  );
}

window.OptionsPage = OptionsPage;
