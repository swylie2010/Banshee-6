/* Banshee — Portfolio Analysis Page (Ice Cream Palette) */

const PM = {
  bg0:   '#fdf8ff',
  bg1:   '#f5f0ff',
  bg2:   '#ece5ff',
  bg3:   '#e0d8f8',
  line:  '#c8bce8',
  ink:   '#1e1640',
  ink2:  '#42368a',
  ink3:  '#7a6fb0',
  ink4:  '#a898cc',
  mint:  '#5dd6b4',
  rose:  '#f080a0',
  peach: '#f4a860',
  lav:   '#c4a8f8',
  gold:  '#e8b840',
};

/* ── GradeCircle ──────────────────────────────────────────────── */
function GradeCircle({ grade, score }) {
  return (
    <div style={{
      width: 60, height: 60, borderRadius: '50%',
      border: `2px solid ${PM.gold}`,
      boxShadow: '0 0 16px rgba(232,184,64,0.4)',
      background: 'radial-gradient(circle, #fffbe8, #fdf8ff)',
      display: 'flex', flexDirection: 'column',
      alignItems: 'center', justifyContent: 'center',
      flexShrink: 0,
    }}>
      <span style={{ fontSize: 20, fontWeight: 700, color: PM.gold, lineHeight: 1 }}>{grade}</span>
      {score > 0 && (
        <span style={{ fontSize: 9, color: PM.ink4, marginTop: 2 }}>{score}</span>
      )}
    </div>
  );
}

/* ── KPIBlock ─────────────────────────────────────────────────── */
function KPIBlock({ label, value, sub }) {
  return (
    <div>
      <div style={{ fontSize: 9, color: PM.ink4, letterSpacing: 1, textTransform: 'uppercase', marginBottom: 2 }}>{label}</div>
      <div style={{ fontSize: 14, fontWeight: 700, color: PM.ink }}>{value}</div>
      {sub && <div style={{ fontSize: 9, color: PM.ink3 }}>{sub}</div>}
    </div>
  );
}

/* ── RiskScorecard ────────────────────────────────────────────── */
function RiskScorecard({ analysis }) {
  const alpha   = analysis?.alpha;
  const beta    = analysis?.beta;
  const sharpe  = analysis?.sharpe;
  const maxDd   = analysis?.max_drawdown;

  function Cell({ accent, label, value, note }) {
    return (
      <div style={{
        background: PM.bg2,
        borderRadius: 8,
        padding: '10px 12px',
        borderTop: `3px solid ${accent}`,
      }}>
        <div style={{ fontSize: 9, color: PM.ink4, letterSpacing: 1, marginBottom: 4 }}>{label}</div>
        <div style={{ fontSize: 16, fontWeight: 700, color: value != null ? accent : PM.ink4 }}>
          {value != null ? value : '—'}
        </div>
        {note && <div style={{ fontSize: 9, color: PM.ink3, marginTop: 2 }}>{note}</div>}
      </div>
    );
  }

  const alphaVal = alpha != null
    ? { display: `${alpha >= 0 ? '+' : ''}${(alpha * 100).toFixed(1)}%`, color: alpha >= 0 ? PM.mint : PM.rose }
    : null;

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
      <div style={{
        background: PM.bg2, borderRadius: 8, padding: '10px 12px',
        borderTop: `3px solid ${PM.mint}`,
      }}>
        <div style={{ fontSize: 9, color: PM.ink4, letterSpacing: 1, marginBottom: 4 }}>ALPHA</div>
        <div style={{ fontSize: 16, fontWeight: 700, color: alpha != null ? (alpha >= 0 ? PM.mint : PM.rose) : PM.ink4 }}>
          {alpha != null ? `${alpha >= 0 ? '+' : ''}${(alpha * 100).toFixed(1)}%` : '—'}
        </div>
        <div style={{ fontSize: 9, color: PM.ink3, marginTop: 2 }}>vs benchmark</div>
      </div>

      <Cell
        accent={PM.lav}
        label="BETA"
        value={beta != null ? beta.toFixed(2) : null}
        note={beta != null ? (beta < 1 ? 'low market sensitivity' : beta > 1.2 ? 'high sensitivity' : 'market-correlated') : null}
      />
      <Cell
        accent={PM.lav}
        label="SHARPE"
        value={sharpe != null ? sharpe.toFixed(2) : null}
        note={sharpe != null ? (sharpe >= 1.5 ? 'excellent' : sharpe >= 1 ? 'good' : 'below avg') : null}
      />
      <Cell
        accent={PM.peach}
        label="MAX DRAWDOWN"
        value={maxDd != null ? `${(maxDd * 100).toFixed(1)}%` : null}
        note={maxDd != null ? (Math.abs(maxDd) < 0.05 ? 'contained' : Math.abs(maxDd) < 0.15 ? 'moderate' : 'significant') : null}
      />
    </div>
  );
}

/* ── HoldingsTable ────────────────────────────────────────────── */
function HoldingsTable({ weights }) {
  if (!weights || weights.length === 0) {
    return <div style={{ fontSize: 11, color: PM.ink4, padding: '20px 0', textAlign: 'center' }}>No holdings data</div>;
  }

  const thStyle = {
    fontSize: 9, color: PM.ink2, letterSpacing: 1,
    padding: '6px 8px', textAlign: 'left',
    background: PM.bg2, fontWeight: 700,
  };
  const tdStyle = (i) => ({
    fontSize: 11, color: PM.ink,
    padding: '5px 8px',
    background: i % 2 === 0 ? PM.bg0 : PM.bg1,
    borderBottom: `1px solid ${PM.line}`,
  });

  return (
    <div style={{ overflowX: 'auto' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11 }}>
        <thead>
          <tr>
            {['SYM', 'SHARES', 'VALUE', 'WEIGHT', 'DRIFT', 'ALPHA'].map(col => (
              <th key={col} style={thStyle}>{col}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {weights.map((w, i) => (
            <tr key={w.sym || i}>
              <td style={{ ...tdStyle(i), fontWeight: 700, color: PM.ink2 }}>{w.sym ?? '—'}</td>
              <td style={tdStyle(i)}>{w.shares != null ? w.shares : '—'}</td>
              <td style={tdStyle(i)}>{w.value != null ? `$${Number(w.value).toLocaleString('en-US', { maximumFractionDigits: 0 })}` : '—'}</td>
              <td style={tdStyle(i)}>{w.weight != null ? `${(w.weight * 100).toFixed(1)}%` : '—'}</td>
              <td style={{ ...tdStyle(i), color: PM.ink4 }}>—</td>
              <td style={{ ...tdStyle(i), color: PM.ink4 }}>—</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/* ── SectorBars ───────────────────────────────────────────────── */
function SectorBars({ weights }) {
  if (!weights || weights.length === 0) {
    return <div style={{ fontSize: 11, color: PM.ink4, padding: '20px 0', textAlign: 'center' }}>No sector data</div>;
  }

  const CLS_COLORS = {
    EQUITY:  PM.mint,
    CRYPTO:  PM.peach,
    TECH:    PM.lav,
    FINANCE: PM.gold,
  };

  // Group by cls, sum weights
  const grouped = {};
  weights.forEach(w => {
    const cls = (w.cls || 'OTHER').toUpperCase();
    grouped[cls] = (grouped[cls] || 0) + (w.weight || 0);
  });

  const entries = Object.entries(grouped).sort((a, b) => b[1] - a[1]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      {entries.map(([cls, pct]) => {
        const color = CLS_COLORS[cls] || PM.ink4;
        const pctNum = Math.min(100, Math.round(pct * 100));
        const signal = pctNum > 50 ? '↑ IN' : pctNum > 25 ? '→ neutral' : '↓ UW';
        return (
          <div key={cls}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
              <span style={{ fontSize: 10, color: PM.ink2, fontWeight: 700, letterSpacing: 1 }}>{cls}</span>
              <span style={{ fontSize: 10, color: PM.ink3 }}>{pctNum}% <span style={{ color }}>{signal}</span></span>
            </div>
            <div style={{
              height: 18,
              borderRadius: 8,
              background: `linear-gradient(90deg, ${color} ${pctNum}%, ${PM.bg3} ${pctNum}%)`,
            }} />
          </div>
        );
      })}
    </div>
  );
}

/* ── GradeHistoryBars ─────────────────────────────────────────── */
function GradeHistoryBars({ gradeHistory }) {
  if (!gradeHistory || gradeHistory.length === 0) return null;

  function gradeColor(g) {
    if (!g) return PM.ink4;
    const upper = g.toUpperCase();
    if (upper.startsWith('A')) return PM.mint;
    if (upper.startsWith('B')) return PM.lav;
    if (upper.startsWith('C')) return PM.peach;
    return PM.rose;
  }

  function gradeScore(g) {
    if (!g) return 0;
    const base = { A: 95, B: 80, C: 65, D: 50, F: 30 };
    const letter = g[0].toUpperCase();
    const mod = g.includes('+') ? 5 : g.includes('-') ? -5 : 0;
    return (base[letter] || 50) + mod;
  }

  const maxScore = Math.max(...gradeHistory.map(h => gradeScore(h.grade)));
  const lastIdx = gradeHistory.length - 1;

  return (
    <div style={{ display: 'flex', alignItems: 'flex-end', gap: 12, overflowX: 'auto', paddingBottom: 4 }}>
      {gradeHistory.map((h, i) => {
        const score = gradeScore(h.grade);
        const height = Math.max(20, Math.round((score / maxScore) * 0.6 * 80 + 20));
        const color = gradeColor(h.grade);
        const isCurrent = i === lastIdx;
        return (
          <div key={i} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4, minWidth: 40 }}>
            {isCurrent && (
              <span style={{ fontSize: 10, color: PM.gold }}>★</span>
            )}
            <div style={{
              width: 32, height,
              background: color,
              borderRadius: 4,
              opacity: isCurrent ? 1 : 0.6,
              border: isCurrent ? `2px solid ${PM.gold}` : '2px solid transparent',
            }} />
            <div style={{ fontSize: 9, color: PM.ink3, textAlign: 'center' }}>
              {h.month && <div>{h.month}</div>}
              <div style={{ fontWeight: 700, color }}>{h.grade ?? '—'}</div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

/* ── PortfolioPage ────────────────────────────────────────────── */
function PortfolioPage({ portfolioId, portfolio: initialPortfolio, onBack }) {
  const [analysis, setAnalysis] = React.useState(null);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState(null);
  const [portfolio, setPortfolio] = React.useState(initialPortfolio);

  React.useEffect(() => {
    window.API.fetchPortfolioAnalysis(portfolioId)
      .then(data => {
        if (data.error) { setError(data.error); }
        else { setAnalysis(data); }
        setLoading(false);
      })
      .catch(e => { setError(e.message); setLoading(false); });
  }, [portfolioId]);

  if (loading) return (
    <div style={{ background: PM.bg0, minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <span style={{ color: PM.lav, fontSize: 13, fontFamily: 'monospace', letterSpacing: 2 }}>ANALYZING PORTFOLIO...</span>
    </div>
  );
  if (error) return (
    <div style={{ background: PM.bg0, minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <span style={{ color: PM.rose, fontSize: 12, fontFamily: 'monospace' }}>{error}</span>
    </div>
  );

  const grade       = analysis?.grade ?? '—';
  const score       = analysis?.score ?? 0;
  const totalValue  = analysis?.total_value ?? 0;
  const twrr        = analysis?.twrr;
  const sharpe      = analysis?.sharpe;
  const maxDd       = analysis?.max_drawdown;
  const aiReview    = analysis?.ai_review;
  const thesis      = portfolio?.thesis;
  const name        = portfolio?.name ?? 'Portfolio';
  const weights     = analysis?.weights ?? [];
  const gradeHistory = analysis?.grade_history ?? portfolio?.grade_history ?? [];

  return (
    <div style={{ background: PM.bg0, minHeight: '100vh', color: PM.ink, fontFamily: 'monospace', padding: '20px 24px', overflowY: 'auto' }}>

      {/* ── Header ── */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 20, marginBottom: 20 }}>
        <button onClick={onBack} style={{ background: 'transparent', border: 'none', color: PM.ink3, cursor: 'pointer', fontSize: 12, letterSpacing: 1, padding: 0 }}>← BACK</button>
        <GradeCircle grade={grade} score={score} />
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 14, fontWeight: 700, color: PM.ink, marginBottom: 6 }}>{name}</div>
          <div style={{ display: 'flex', gap: 20, flexWrap: 'wrap' }}>
            <KPIBlock label="TOTAL VALUE" value={`$${totalValue.toLocaleString('en-US', { maximumFractionDigits: 0 })}`} />
            {twrr != null && <KPIBlock label="TWRR" value={`${(twrr * 100).toFixed(1)}%`} sub="vs benchmark" />}
            {sharpe != null && <KPIBlock label="SHARPE" value={sharpe.toFixed(2)} />}
            {maxDd != null && <KPIBlock label="MAX DD" value={`${(maxDd * 100).toFixed(1)}%`} />}
          </div>
        </div>
      </div>

      {/* ── AI Banner ── */}
      {aiReview && (
        <div style={{ background: 'linear-gradient(135deg, #f0eaff, #e8f4ff)', border: `1px solid ${PM.lav}`, borderRadius: 10, padding: '14px 18px', marginBottom: 20 }}>
          <div style={{ display: 'flex', gap: 10, alignItems: 'flex-start' }}>
            <span style={{ color: PM.lav, fontSize: 14, flexShrink: 0 }}>◈</span>
            <div>
              <div style={{ fontSize: 12, color: PM.ink, lineHeight: 1.6, marginBottom: thesis ? 8 : 0 }}>
                {aiReview.primary_observation}
              </div>
              {thesis && (
                <div style={{ fontSize: 11, color: PM.ink3, borderLeft: `3px solid ${PM.lav}`, paddingLeft: 10, fontStyle: 'italic' }}>
                  "{thesis}"
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ── Level 2: Returns + Risk Scorecard ── */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 16 }}>
        <div style={{ background: PM.bg1, border: `1px solid ${PM.line}`, borderRadius: 10, padding: 16 }}>
          <div style={{ fontSize: 10, color: PM.ink3, letterSpacing: 1, marginBottom: 10 }}>CUMULATIVE RETURNS</div>
          {window.LightweightCharts
            ? <div id="portfolio-chart" style={{ height: 180 }} />
            : <div style={{ height: 180, background: PM.bg2, borderRadius: 8, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <span style={{ fontSize: 10, color: PM.ink4, letterSpacing: 1 }}>RETURNS CHART — COMING SOON</span>
              </div>
          }
        </div>
        <div style={{ background: PM.bg1, border: `1px solid ${PM.line}`, borderRadius: 10, padding: 16 }}>
          <div style={{ fontSize: 10, color: PM.ink3, letterSpacing: 1, marginBottom: 10 }}>RISK SCORECARD</div>
          <RiskScorecard analysis={analysis} />
        </div>
      </div>

      {/* ── Level 3: Holdings + Sector Bars ── */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 16 }}>
        <div style={{ background: PM.bg1, border: `1px solid ${PM.line}`, borderRadius: 10, padding: 16 }}>
          <div style={{ fontSize: 10, color: PM.ink3, letterSpacing: 1, marginBottom: 10 }}>HOLDINGS</div>
          <HoldingsTable weights={weights} />
        </div>
        <div style={{ background: PM.bg1, border: `1px solid ${PM.line}`, borderRadius: 10, padding: 16 }}>
          <div style={{ fontSize: 10, color: PM.ink3, letterSpacing: 1, marginBottom: 10 }}>SECTOR ALLOCATION</div>
          <SectorBars weights={weights} />
        </div>
      </div>

      {/* ── Level 4: Grade History ── */}
      {gradeHistory.length > 0 && (
        <div style={{ background: PM.bg1, border: `1px solid ${PM.line}`, borderRadius: 10, padding: 16 }}>
          <div style={{ fontSize: 10, color: PM.ink3, letterSpacing: 1, marginBottom: 12 }}>GRADE HISTORY</div>
          <GradeHistoryBars gradeHistory={gradeHistory} />
        </div>
      )}

    </div>
  );
}

window.PortfolioPage = PortfolioPage;
