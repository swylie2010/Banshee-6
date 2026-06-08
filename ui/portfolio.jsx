/* Banshee — Portfolio Analysis Page
 * Two themes: LIGHT (muted lavender-gray, easy on dark-adapted eyes) and
 * DARK (standard Banshee colors). Toggle in the header; choice persists.
 * Font floor is 11px everywhere — the smallest type on the page. */

const PORTFOLIO_THEMES = {
  light: {
    bg0:   '#c4c3d0',  // page background (toned down from the old bright ice-cream)
    bg1:   '#d2d1dd',  // cards — lifted off the page
    bg2:   '#dcdbe6',  // input fields / cells — lightest
    bg3:   '#b1b0c1',  // bar tracks / recessed
    line:  '#9f9db3',  // borders, readable on bg0
    ink:   '#191526',  // primary text — near-black
    ink2:  '#322d4a',  // secondary
    ink3:  '#453f5e',  // tertiary
    ink4:  '#534d72',  // quaternary (smallest notes) — still clearly readable
    mint:  '#1c8a66',  // positive
    rose:  '#ab3257',  // negative
    peach: '#b06a1c',  // accent / crypto
    lav:   '#5a41a4',  // accent
    gold:  '#927014',  // grade ring
    btn:   '#5a41a4',  // filled action button
    btnInk:'#ffffff',  // text on filled button
    aiBanner: 'linear-gradient(135deg, #d6cdec, #cdd9ec)',
  },
  dark: {
    bg0:   '#0b0e14',
    bg1:   '#141922',
    bg2:   '#1c2230',
    bg3:   '#283143',
    line:  '#313b4d',
    ink:   '#e8eef6',
    ink2:  '#bcc8d8',
    ink3:  '#8a99ab',
    ink4:  '#647284',
    mint:  '#34d39e',
    rose:  '#f0646e',
    peach: '#f0a860',
    lav:   '#a98cf2',
    gold:  '#e8c84a',
    btn:   '#6a5aa8',
    btnInk:'#ffffff',
    aiBanner: 'linear-gradient(135deg, #1b1630, #142030)',
  },
};

function portfolioPalette(theme) {
  return PORTFOLIO_THEMES[theme] || PORTFOLIO_THEMES.light;
}
window.portfolioPalette = portfolioPalette;

const PaletteCtx = React.createContext(PORTFOLIO_THEMES.light);
const usePalette = () => React.useContext(PaletteCtx);

/* ── GradeCircle ──────────────────────────────────────────────── */
function GradeCircle({ grade, score }) {
  const pm = usePalette();
  return (
    <div style={{
      width: 60, height: 60, borderRadius: '50%',
      border: `2px solid ${pm.gold}`,
      boxShadow: `0 0 16px ${pm.gold}55`,
      background: `radial-gradient(circle, ${pm.bg2}, ${pm.bg0})`,
      display: 'flex', flexDirection: 'column',
      alignItems: 'center', justifyContent: 'center',
      flexShrink: 0,
    }}>
      <span style={{ fontSize: 20, fontWeight: 700, color: pm.gold, lineHeight: 1 }}>{grade}</span>
      {score > 0 && (
        <span style={{ fontSize: 11, color: pm.ink4, marginTop: 3 }}>{score}</span>
      )}
    </div>
  );
}

/* ── KPIBlock ─────────────────────────────────────────────────── */
function KPIBlock({ label, value, sub }) {
  const pm = usePalette();
  return (
    <div>
      <div style={{ fontSize: 11, color: pm.ink4, letterSpacing: 1, textTransform: 'uppercase', marginBottom: 2 }}>{label}</div>
      <div style={{ fontSize: 15, fontWeight: 700, color: pm.ink }}>{value}</div>
      {sub && <div style={{ fontSize: 11, color: pm.ink3 }}>{sub}</div>}
    </div>
  );
}

/* ── GradeBreakdown — explains how the letter grade was computed ── */
function GradeBreakdown({ analysis }) {
  const pm = usePalette();
  const m = analysis?.momentum_score;
  const r = analysis?.risk_score;
  const hasRisk = r != null;
  const twrr = analysis?.twrr;

  const rows = [
    { label: 'MOMENTUM', weight: hasRisk ? 60 : 100, score: m,
      note: 'Current technical strength/bias of your holdings (from the radar). Higher = more assets trending up now.' },
  ];
  if (hasRisk) rows.push({ label: 'RISK-ADJUSTED RETURN', weight: 40, score: r,
    note: "From the basket's 1-year Sharpe ratio (return vs. volatility). Negative trailing-year performance drives this toward 0 — regardless of your entry prices." });

  const barColor = (s) => s == null ? pm.ink4 : s >= 70 ? pm.mint : s >= 40 ? pm.peach : pm.rose;

  // Plain-English headline: name the single biggest drag (ignoring the inert placeholder).
  const real = [{ label: 'momentum', s: m }].concat(hasRisk ? [{ label: 'risk', s: r }] : []).filter(x => x.s != null);
  const weak = real.length ? real.reduce((acc, x) => x.s < acc.s ? x : acc) : null;
  let headline = `This is a ${analysis?.grade ?? '—'}.`;
  if (weak) {
    headline = weak.label === 'risk'
      ? `Why the ${analysis?.grade ?? ''}: risk-adjusted return is low (${Math.round(weak.s)}/100) — the basket's gain-vs-volatility over the past year is negative.`
      : `Why the ${analysis?.grade ?? ''}: momentum is the main drag (${Math.round(weak.s)}/100) — fewer holdings trending up right now.`;
  }

  return (
    <div style={{ background: pm.bg2, border: `1px solid ${pm.line}`, borderRadius: 8, padding: '12px 16px', marginBottom: 16 }}>
      <div style={{ fontSize: 12, color: pm.ink, lineHeight: 1.55, marginBottom: 12, fontWeight: 700 }}>{headline}</div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        {rows.map(row => (
          <div key={row.label}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 3 }}>
              <span style={{ fontSize: 11, color: pm.ink2, fontWeight: 700, letterSpacing: 1 }}>
                {row.label} <span style={{ color: pm.ink4, fontWeight: 400 }}>· {row.weight}% of grade</span>
              </span>
              <span style={{ fontSize: 12, fontWeight: 700, color: barColor(row.score) }}>
                {row.score != null ? `${Math.round(row.score)}/100` : '—'}
              </span>
            </div>
            <div style={{ height: 6, borderRadius: 4, background: pm.bg3, marginBottom: 4 }}>
              <div style={{ height: 6, borderRadius: 4, width: `${Math.max(0, Math.min(100, row.score || 0))}%`, background: barColor(row.score) }} />
            </div>
            <div style={{ fontSize: 11, color: pm.ink3, lineHeight: 1.5 }}>{row.note}</div>
          </div>
        ))}
      </div>
      <div style={{ marginTop: 12, paddingTop: 10, borderTop: `1px solid ${pm.line}`, fontSize: 11, color: pm.ink3, lineHeight: 1.55 }}>
        <span style={{ color: pm.peach, fontWeight: 700 }}>⚠ Note: </span>
        This grade measures the basket&rsquo;s <b style={{ color: pm.ink2 }}>trailing-year market behavior and current momentum</b> — it does <b style={{ color: pm.ink2 }}>not</b> credit your entry timing.
        {twrr != null && ` Your +${(twrr*100).toFixed(0)}% return on entries isn't reflected here.`} Adding entry dates won&rsquo;t change it.
      </div>
    </div>
  );
}

/* ── PerformancePanel — relative strength vs the S&P, short & long ── */
function PerformancePanel({ performance }) {
  const pm = usePalette();
  if (!performance || (!performance.recent && !performance.overall)) return null;

  function Row({ label, span, you, spy, vs }) {
    const ahead = vs != null && vs >= 0;
    return (
      <div style={{ display: 'flex', alignItems: 'center', gap: 14, flexWrap: 'wrap', padding: '7px 0', borderTop: `1px solid ${pm.line}66` }}>
        <div style={{ minWidth: 96 }}>
          <div style={{ fontSize: 11, color: pm.ink2, fontWeight: 700, letterSpacing: 1 }}>{label}</div>
          <div style={{ fontSize: 11, color: pm.ink4 }}>{span}</div>
        </div>
        <div style={{ display: 'flex', gap: 18, alignItems: 'baseline', flex: 1 }}>
          <div><span style={{ fontSize: 11, color: pm.ink4 }}>{'YOU '}</span><span style={{ fontSize: 14, fontWeight: 700, color: you >= 0 ? pm.mint : pm.rose }}>{you >= 0 ? '+' : ''}{you}%</span></div>
          <div><span style={{ fontSize: 11, color: pm.ink4 }}>{'S&P '}</span><span style={{ fontSize: 14, fontWeight: 700, color: spy >= 0 ? pm.mint : pm.rose }}>{spy >= 0 ? '+' : ''}{spy}%</span></div>
        </div>
        {vs != null && (
          <div style={{ fontSize: 12, fontWeight: 700, color: ahead ? pm.mint : pm.rose, whiteSpace: 'nowrap' }}>
            {ahead ? '▲ ahead ' : '▼ behind '}{Math.abs(vs)}%
          </div>
        )}
      </div>
    );
  }

  return (
    <div style={{ background: pm.bg1, border: `1px solid ${pm.line}`, borderRadius: 10, padding: '10px 16px 12px', marginBottom: 16 }}>
      <div style={{ fontSize: 11, color: pm.ink3, letterSpacing: 1, marginBottom: 2, fontWeight: 700 }}>{'PERFORMANCE vs S&P 500'}</div>
      {performance.overall
        ? <Row label="OVERALL"
            span={`since your entries${performance.overall.coverage != null && performance.overall.coverage < 0.9 ? ` · ${Math.round(performance.overall.coverage * 100)}% of book dated` : ''}`}
            you={performance.overall.portfolio} spy={performance.overall.benchmark} vs={performance.overall.vs_benchmark} />
        : <div style={{ fontSize: 11, color: pm.ink4, padding: '7px 0', borderTop: `1px solid ${pm.line}66`, lineHeight: 1.5 }}>
            Add entry <b style={{ color: pm.ink3 }}>dates</b> in Edit Holdings to compare your returns against the S&P over your actual holding period.
          </div>}
      {performance.recent && <Row label="RECENT" span={`last ~${performance.recent.days} days · basket`} you={performance.recent.portfolio} spy={performance.recent.benchmark} vs={performance.recent.vs_benchmark} />}
    </div>
  );
}

/* ── RiskScorecard ────────────────────────────────────────────── */
function RiskScorecard({ analysis }) {
  const pm = usePalette();
  const alpha   = analysis?.alpha;
  const beta    = analysis?.beta;
  const sharpe  = analysis?.sharpe;
  const maxDd   = analysis?.max_drawdown;

  function Cell({ accent, label, value, note }) {
    return (
      <div style={{
        background: pm.bg2,
        borderRadius: 8,
        padding: '10px 12px',
        borderTop: `3px solid ${accent}`,
      }}>
        <div style={{ fontSize: 11, color: pm.ink4, letterSpacing: 1, marginBottom: 4 }}>{label}</div>
        <div style={{ fontSize: 16, fontWeight: 700, color: value != null ? accent : pm.ink4 }}>
          {value != null ? value : '—'}
        </div>
        {note && <div style={{ fontSize: 11, color: pm.ink3, marginTop: 2 }}>{note}</div>}
      </div>
    );
  }

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
      <div style={{
        background: pm.bg2, borderRadius: 8, padding: '10px 12px',
        borderTop: `3px solid ${pm.mint}`,
      }}>
        <div style={{ fontSize: 11, color: pm.ink4, letterSpacing: 1, marginBottom: 4 }}>ALPHA</div>
        <div style={{ fontSize: 16, fontWeight: 700, color: alpha != null ? (alpha >= 0 ? pm.mint : pm.rose) : pm.ink4 }}>
          {alpha != null ? `${alpha >= 0 ? '+' : ''}${(alpha * 100).toFixed(1)}%` : '—'}
        </div>
        <div style={{ fontSize: 11, color: pm.ink3, marginTop: 2 }}>vs benchmark</div>
      </div>

      <Cell
        accent={pm.lav}
        label="BETA"
        value={beta != null ? beta.toFixed(2) : null}
        note={beta != null ? (beta < 1 ? 'low market sensitivity' : beta > 1.2 ? 'high sensitivity' : 'market-correlated') : null}
      />
      <Cell
        accent={pm.lav}
        label="SHARPE"
        value={sharpe != null ? sharpe.toFixed(2) : null}
        note={sharpe != null ? (sharpe >= 1.5 ? 'excellent' : sharpe >= 1 ? 'good' : 'below avg') : null}
      />
      <Cell
        accent={pm.peach}
        label="MAX DRAWDOWN"
        value={maxDd != null ? `${(maxDd * 100).toFixed(1)}%` : null}
        note={maxDd != null ? (Math.abs(maxDd) < 0.05 ? 'contained' : Math.abs(maxDd) < 0.15 ? 'moderate' : 'significant') : null}
      />
    </div>
  );
}

/* ── HoldingsTable ────────────────────────────────────────────── */
function HoldingsTable({ weights }) {
  const pm = usePalette();
  if (!weights || weights.length === 0) {
    return <div style={{ fontSize: 11, color: pm.ink4, padding: '20px 0', textAlign: 'center' }}>No holdings data</div>;
  }

  const thStyle = {
    fontSize: 11, color: pm.ink2, letterSpacing: 1,
    padding: '6px 8px', textAlign: 'left',
    background: pm.bg2, fontWeight: 700,
  };
  const tdStyle = (i) => ({
    fontSize: 12, color: pm.ink,
    padding: '5px 8px',
    background: i % 2 === 0 ? pm.bg0 : pm.bg1,
    borderBottom: `1px solid ${pm.line}`,
  });

  return (
    <div style={{ overflowX: 'auto' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
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
              <td style={{ ...tdStyle(i), fontWeight: 700, color: pm.ink2 }}>{w.sym ?? '—'}</td>
              <td style={tdStyle(i)}>{w.shares != null && w.shares !== 0 ? w.shares : '—'}</td>
              <td style={tdStyle(i)}>{w.value ? `$${Number(w.value).toLocaleString('en-US', { maximumFractionDigits: 0 })}` : '—'}</td>
              <td style={tdStyle(i)}>{w.weight != null ? `${(w.weight * 100).toFixed(1)}%` : '—'}</td>
              <td style={{ ...tdStyle(i), color: pm.ink4 }}>—</td>
              <td style={{ ...tdStyle(i), color: pm.ink4 }}>—</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/* ── SectorBars ───────────────────────────────────────────────── */
function SectorBars({ weights }) {
  const pm = usePalette();
  if (!weights || weights.length === 0) {
    return <div style={{ fontSize: 11, color: pm.ink4, padding: '20px 0', textAlign: 'center' }}>No sector data</div>;
  }

  const CLS_COLORS = {
    EQUITY:  pm.mint,
    CRYPTO:  pm.peach,
    TECH:    pm.lav,
    FINANCE: pm.gold,
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
        const color = CLS_COLORS[cls] || pm.ink4;
        const pctNum = Math.min(100, Math.round(pct * 100));
        const signal = pctNum > 50 ? '↑ IN' : pctNum > 25 ? '→ neutral' : '↓ UW';
        return (
          <div key={cls}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
              <span style={{ fontSize: 11, color: pm.ink2, fontWeight: 700, letterSpacing: 1 }}>{cls}</span>
              <span style={{ fontSize: 11, color: pm.ink3 }}>{pctNum}% <span style={{ color }}>{signal}</span></span>
            </div>
            <div style={{
              height: 18,
              borderRadius: 8,
              background: `linear-gradient(90deg, ${color} ${pctNum}%, ${pm.bg3} ${pctNum}%)`,
            }} />
          </div>
        );
      })}
    </div>
  );
}

/* ── GradeHistoryBars ─────────────────────────────────────────── */
function GradeHistoryBars({ gradeHistory }) {
  const pm = usePalette();
  if (!gradeHistory || gradeHistory.length === 0) return null;

  function gradeColor(g) {
    if (!g) return pm.ink4;
    const upper = g.toUpperCase();
    if (upper.startsWith('A')) return pm.mint;
    if (upper.startsWith('B')) return pm.lav;
    if (upper.startsWith('C')) return pm.peach;
    return pm.rose;
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
              <span style={{ fontSize: 12, color: pm.gold }}>★</span>
            )}
            <div style={{
              width: 32, height,
              background: color,
              borderRadius: 4,
              opacity: isCurrent ? 1 : 0.6,
              border: isCurrent ? `2px solid ${pm.gold}` : '2px solid transparent',
            }} />
            <div style={{ fontSize: 11, color: pm.ink3, textAlign: 'center' }}>
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
function overlayStyle(pm) {
  return {
    position: 'absolute', inset: 0, zIndex: 30, overflowY: 'auto',
    background: pm.bg0, color: pm.ink, fontFamily: 'monospace',
  };
}

function ThemeToggle({ theme, onToggle }) {
  const pm = usePalette();
  return (
    <button onClick={onToggle} title={theme === 'light' ? 'Switch to dark theme' : 'Switch to light theme'}
      style={{
        background: 'transparent', border: `1px solid ${pm.line}`, color: pm.ink2,
        borderRadius: 6, padding: '5px 10px', fontSize: 13, cursor: 'pointer',
        fontFamily: 'monospace', flexShrink: 0, lineHeight: 1,
      }}>
      {theme === 'light' ? '☾' : '☀'}
    </button>
  );
}

/* ── MarketRotation — informational note on where market money is flowing.
   Pure context, NEVER a grade input. The backend returns null for all-crypto
   baskets (sector rotation is an equity concept) or when data is unavailable,
   so this renders nothing in those cases. ── */
function MarketRotation({ rotation }) {
  const pm = usePalette();
  if (!rotation || !rotation.summary) return null;
  const { summary, inflows = [], outflows = [], interpretation } = rotation;

  const Chip = ({ name, roc, up }) => (
    <span style={{ display: 'inline-flex', alignItems: 'baseline', gap: 5, fontSize: 11,
      background: pm.bg3, borderRadius: 12, padding: '3px 9px',
      border: `1px solid ${(up ? pm.mint : pm.rose)}44` }}>
      <span style={{ color: up ? pm.mint : pm.rose, fontWeight: 700 }}>{up ? '↑' : '↓'} {name}</span>
      <span style={{ color: pm.ink4 }}>{roc > 0 ? '+' : ''}{roc}%</span>
    </span>
  );

  const hasChips = inflows.length > 0 || outflows.length > 0;
  return (
    <div style={{ background: pm.bg2, border: `1px solid ${pm.line}`, borderRadius: 8, padding: '12px 16px', marginBottom: 16 }}>
      <div style={{ fontSize: 11, color: pm.ink4, letterSpacing: 1, fontWeight: 700, marginBottom: 8 }}>
        MARKET ROTATION <span style={{ color: pm.ink4, fontWeight: 400 }}>· context, not part of your grade</span>
      </div>
      <div style={{ fontSize: 13, color: pm.ink, fontWeight: 700, lineHeight: 1.5, marginBottom: hasChips ? 10 : 0 }}>{summary}</div>
      {hasChips && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 7, marginBottom: interpretation ? 10 : 0 }}>
          {inflows.map(s => <Chip key={'in' + s.name} name={s.name} roc={s.roc_21} up />)}
          {outflows.map(s => <Chip key={'out' + s.name} name={s.name} roc={s.roc_21} up={false} />)}
        </div>
      )}
      {interpretation && (
        <div style={{ fontSize: 11, color: pm.ink3, fontStyle: 'italic', lineHeight: 1.5, borderLeft: `3px solid ${pm.lav}`, paddingLeft: 10 }}>{interpretation}</div>
      )}
    </div>
  );
}

function PortfolioPage({ portfolioId, portfolio: initialPortfolio, onBack, onEditHoldings }) {
  const [analysis, setAnalysis] = React.useState(null);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState(null);
  const [portfolio, setPortfolio] = React.useState(initialPortfolio);
  const [theme, setTheme] = React.useState(() => localStorage.getItem('banshee_portfolio_theme') || 'light');
  const [gradeOpen, setGradeOpen] = React.useState(false);

  const pm = portfolioPalette(theme);

  function toggleTheme() {
    setTheme(t => {
      const next = t === 'light' ? 'dark' : 'light';
      try { localStorage.setItem('banshee_portfolio_theme', next); } catch {}
      return next;
    });
  }

  React.useEffect(() => {
    window.API.fetchPortfolioAnalysis(portfolioId)
      .then(data => {
        if (data.error) { setError(data.error); }
        else { setAnalysis(data); }
        setLoading(false);
      })
      .catch(e => { setError(e.message); setLoading(false); });
  }, [portfolioId]);

  /* Draw the cumulative-return line in #portfolio-chart (theme-aware). */
  React.useEffect(() => {
    const series = analysis && analysis.returns_series;
    if (!window.LightweightCharts || !series || !series.length) return;
    const el = document.getElementById('portfolio-chart');
    if (!el) return;
    el.innerHTML = '';
    let chart;
    try {
      chart = window.LightweightCharts.createChart(el, {
        width: el.clientWidth || 320, height: 180,
        layout: { background: { color: 'transparent' }, textColor: pm.ink3, fontFamily: 'monospace', fontSize: 11 },
        grid: { vertLines: { color: pm.line + '33' }, horzLines: { color: pm.line + '33' } },
        rightPriceScale: { borderColor: pm.line },
        timeScale: { borderColor: pm.line, timeVisible: false },
        localization: { priceFormatter: (v) => (v >= 0 ? '+' : '') + v.toFixed(0) + '%' },
        handleScroll: false, handleScale: false,
      });
      const area = chart.addAreaSeries({
        lineColor: pm.lav, topColor: pm.lav + '55', bottomColor: pm.lav + '08', lineWidth: 2,
      });
      area.setData(series);
      chart.timeScale().fitContent();
    } catch (e) { /* chart lib hiccup — leave the placeholder */ return; }
    const onResize = () => { if (el.clientWidth) chart.applyOptions({ width: el.clientWidth }); };
    window.addEventListener('resize', onResize);
    return () => { window.removeEventListener('resize', onResize); try { chart.remove(); } catch (e) {} };
  }, [analysis, theme]);

  /* A low grade should explain itself — auto-open the breakdown for D/F. */
  React.useEffect(() => {
    if (analysis && /^[DF]/i.test(analysis.grade || '')) setGradeOpen(true);
  }, [analysis]);

  if (loading) return (
    <PaletteCtx.Provider value={pm}>
      <div style={{ ...overlayStyle(pm), display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <span style={{ color: pm.lav, fontSize: 13, fontFamily: 'monospace', letterSpacing: 2 }}>ANALYZING PORTFOLIO...</span>
      </div>
    </PaletteCtx.Provider>
  );
  if (error) return (
    <PaletteCtx.Provider value={pm}>
      <div style={{ ...overlayStyle(pm), display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 16, padding: 24 }}>
        <button onClick={onBack} style={{ position: 'absolute', top: 20, left: 24, background: 'transparent', border: 'none', color: pm.ink3, cursor: 'pointer', fontSize: 12, letterSpacing: 1, padding: 0 }}>← BACK</button>
        <div style={{ fontSize: 13, color: pm.ink2, fontWeight: 700, letterSpacing: 1 }}>COULDN'T LOAD THIS PORTFOLIO</div>
        <div style={{ fontSize: 11, color: pm.ink3, maxWidth: 360, textAlign: 'center', lineHeight: 1.6 }}>
          {/HTTP 4|no holdings|value is zero/i.test(error)
            ? 'This portfolio has no holdings yet. Add the assets you want to track to see its analysis.'
            : error}
        </div>
        {onEditHoldings && (
          <button onClick={onEditHoldings} style={{ background: pm.btn, border: 'none', color: pm.btnInk, borderRadius: 8, padding: '8px 18px', fontSize: 12, fontWeight: 700, letterSpacing: 1, cursor: 'pointer', fontFamily: 'monospace' }}>
            + ADD HOLDINGS
          </button>
        )}
      </div>
    </PaletteCtx.Provider>
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

  const isEqualWeight = !!analysis?.equal_weight;

  // Ledger-derived money fields (Phase 1 portfolio history)
  const cash           = analysis?.cash;
  const realizedPnl    = analysis?.realized_pnl;
  const totalReturn    = analysis?.total_return;          // net return on money in
  const ledgerWarnings = analysis?.ledger_warnings ?? [];
  const fmtMoney = (v) => `$${Number(v).toLocaleString('en-US', { maximumFractionDigits: 0 })}`;

  const cardStyle = { background: pm.bg1, border: `1px solid ${pm.line}`, borderRadius: 10, padding: 16 };
  const cardLabel = { fontSize: 11, color: pm.ink3, letterSpacing: 1, marginBottom: 10 };

  return (
    <PaletteCtx.Provider value={pm}>
    <div style={{ ...overlayStyle(pm), padding: '20px 24px' }}>

      {/* ── Header ── */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 20, marginBottom: 14 }}>
        <button onClick={onBack} style={{ background: 'transparent', border: 'none', color: pm.ink3, cursor: 'pointer', fontSize: 12, letterSpacing: 1, padding: 0 }}>← BACK</button>
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 3, flexShrink: 0 }}>
          <GradeCircle grade={grade} score={score} />
          <span style={{ fontSize: 11, color: pm.ink4, letterSpacing: 1, whiteSpace: 'nowrap' }}>BASKET HEALTH</span>
          <button onClick={() => setGradeOpen(o => !o)}
            style={{ background: 'transparent', border: 'none', color: pm.ink3, fontSize: 11, letterSpacing: 0.5, cursor: 'pointer', fontFamily: 'monospace', whiteSpace: 'nowrap', padding: 0 }}>
            WHY? {gradeOpen ? '▴' : '▾'}
          </button>
        </div>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 15, fontWeight: 700, color: pm.ink, marginBottom: 6 }}>{name}</div>
          <div style={{ display: 'flex', gap: 20, flexWrap: 'wrap' }}>
            {!isEqualWeight && <KPIBlock label="TOTAL VALUE" value={fmtMoney(totalValue)} />}
            {totalReturn != null && <KPIBlock label="NET RETURN" value={`${(totalReturn * 100).toFixed(1)}%`} sub="on money in" />}
            {twrr != null && <KPIBlock label="UNREALIZED" value={`${(twrr * 100).toFixed(1)}%`} sub="vs avg cost" />}
            {realizedPnl != null && realizedPnl !== 0 && <KPIBlock label="REALIZED" value={`${realizedPnl >= 0 ? '+' : ''}${fmtMoney(realizedPnl)}`} sub="closed P&L" />}
            {cash != null && cash !== 0 && <KPIBlock label="CASH" value={fmtMoney(cash)} />}
            {sharpe != null && <KPIBlock label="SHARPE" value={sharpe.toFixed(2)} />}
            {maxDd != null && <KPIBlock label="MAX DD" value={`${(maxDd * 100).toFixed(1)}%`} />}
          </div>
        </div>
        <ThemeToggle theme={theme} onToggle={toggleTheme} />
        {onEditHoldings && (
          <button onClick={onEditHoldings} style={{ background: 'transparent', border: `1px solid ${pm.line}`, color: pm.ink2, borderRadius: 6, padding: '5px 12px', fontSize: 11, letterSpacing: 1, cursor: 'pointer', fontFamily: 'monospace', flexShrink: 0 }}>
            ✎ EDIT HOLDINGS
          </button>
        )}
      </div>

      {/* ── Ledger warnings (quiet hint, e.g. negative cash) ── */}
      {ledgerWarnings.length > 0 && (
        <div style={{ fontSize: 11, color: pm.ink3, fontStyle: 'italic', marginBottom: 10, lineHeight: 1.5 }}>
          {ledgerWarnings.map((w, i) => <div key={i}>⚠ {w}</div>)}
        </div>
      )}

      {/* ── Grade breakdown (why this grade?) ── */}
      {gradeOpen && <GradeBreakdown analysis={analysis} />}

      {/* ── Performance vs S&P (recent + overall) ── */}
      <PerformancePanel performance={analysis?.performance} />

      {/* ── Equal-weight basket note (quiet, only when no share counts entered) ── */}
      {isEqualWeight && (
        <div style={{ background: pm.bg2, borderRadius: 8, padding: '8px 14px', marginBottom: 16, display: 'flex', alignItems: 'center', gap: 8, fontSize: 11, color: pm.ink3 }}>
          <span style={{ color: pm.peach }}>◷</span>
          <span>Showing an <b style={{ color: pm.ink2 }}>equal-weight basket</b> view. Add share counts via Edit Holdings for exact value &amp; returns.</span>
        </div>
      )}

      {/* ── AI Banner — balanced read: what it IS, what's working, what's at risk ── */}
      {aiReview && (
        <div style={{ background: pm.aiBanner, border: `1px solid ${pm.lav}`, borderRadius: 10, padding: '14px 18px', marginBottom: 20 }}>
          <div style={{ display: 'flex', gap: 10, alignItems: 'flex-start' }}>
            <span style={{ color: pm.lav, fontSize: 14, flexShrink: 0, marginTop: 1 }}>◈</span>
            <div style={{ flex: 1, minWidth: 0 }}>
              {/* What the portfolio IS */}
              {aiReview.primary_observation && (
                <div style={{ fontSize: 12, color: pm.ink, lineHeight: 1.6, marginBottom: 10 }}>
                  {aiReview.primary_observation}
                </div>
              )}

              {/* Working / Risks — two balanced columns */}
              {(aiReview.whats_working || aiReview.key_risks) && (
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 10 }}>
                  {aiReview.whats_working && (
                    <div style={{ borderLeft: `3px solid ${pm.mint}`, paddingLeft: 10 }}>
                      <div style={{ fontSize: 11, color: pm.mint, letterSpacing: 1, fontWeight: 700, marginBottom: 3 }}>✓ WORKING</div>
                      <div style={{ fontSize: 11, color: pm.ink2, lineHeight: 1.55 }}>{aiReview.whats_working}</div>
                    </div>
                  )}
                  {aiReview.key_risks && (
                    <div style={{ borderLeft: `3px solid ${pm.peach}`, paddingLeft: 10 }}>
                      <div style={{ fontSize: 11, color: pm.peach, letterSpacing: 1, fontWeight: 700, marginBottom: 3 }}>▲ RISKS</div>
                      <div style={{ fontSize: 11, color: pm.ink2, lineHeight: 1.55 }}>{aiReview.key_risks}</div>
                    </div>
                  )}
                </div>
              )}

              {/* vs benchmark */}
              {aiReview.goals_alignment && (
                <div style={{ fontSize: 11, color: pm.ink3, lineHeight: 1.55, marginBottom: 10 }}>
                  <span style={{ color: pm.ink4, letterSpacing: 1 }}>VS BENCHMARK · </span>{aiReview.goals_alignment}
                </div>
              )}

              {/* Thesis evaluation + the quoted goal */}
              {aiReview.thesis_alignment_note && (
                <div style={{ fontSize: 12, color: pm.ink2, lineHeight: 1.6, marginBottom: thesis ? 6 : 0 }}>
                  {aiReview.thesis_alignment_note}
                </div>
              )}
              {thesis && (
                <div style={{ fontSize: 11, color: pm.ink3, borderLeft: `3px solid ${pm.lav}`, paddingLeft: 10, fontStyle: 'italic', marginBottom: 10 }}>
                  "{thesis}"
                </div>
              )}

              {/* Framed guesses at the investor's "why" */}
              {aiReview.possible_intents && aiReview.possible_intents.length > 0 && (
                <div style={{ marginBottom: (aiReview.asset_breakdown && aiReview.asset_breakdown.length) ? 10 : 0 }}>
                  <div style={{ fontSize: 11, color: pm.lav, letterSpacing: 1, fontWeight: 700, marginBottom: 4 }}>
                    {'◈ A FEW GUESSES AT YOUR "WHY" — am I warm?'}
                  </div>
                  <ul style={{ margin: 0, paddingLeft: 16, display: 'flex', flexDirection: 'column', gap: 3 }}>
                    {aiReview.possible_intents.map((g, i) => (
                      <li key={i} style={{ fontSize: 11, color: pm.ink2, lineHeight: 1.5 }}>{g}</li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Per-holding chips, colored by sentiment (note on hover) */}
              {aiReview.asset_breakdown && aiReview.asset_breakdown.length > 0 && (
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 2 }}>
                  {aiReview.asset_breakdown.map((a, i) => {
                    const sc = a.sentiment === 'positive' ? pm.mint : a.sentiment === 'negative' ? pm.rose : pm.ink4;
                    return (
                      <span key={a.sym || i} title={a.note || ''}
                        style={{ fontSize: 11, color: sc, border: `1px solid ${sc}`, borderRadius: 5, padding: '2px 7px', cursor: 'help', whiteSpace: 'nowrap' }}>
                        {a.sym}
                      </span>
                    );
                  })}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ── Level 2: Returns + Risk Scorecard ── */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 16 }}>
        <div style={cardStyle}>
          <div style={cardLabel}>CUMULATIVE RETURNS</div>
          {window.LightweightCharts && analysis?.returns_series?.length
            ? <div id="portfolio-chart" style={{ height: 180 }} />
            : <div style={{ height: 180, background: pm.bg2, borderRadius: 8, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <span style={{ fontSize: 11, color: pm.ink4, letterSpacing: 1 }}>
                  {analysis?.returns_series && !analysis.returns_series.length ? 'NOT ENOUGH PRICE HISTORY' : 'RETURNS CHART UNAVAILABLE'}
                </span>
              </div>
          }
        </div>
        <div style={cardStyle}>
          <div style={cardLabel}>RISK SCORECARD</div>
          <RiskScorecard analysis={analysis} />
        </div>
      </div>

      {/* ── Level 3: Holdings + Sector Bars ── */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 16 }}>
        <div style={cardStyle}>
          <div style={cardLabel}>HOLDINGS</div>
          <HoldingsTable weights={weights} />
        </div>
        <div style={cardStyle}>
          <div style={cardLabel}>SECTOR ALLOCATION</div>
          <SectorBars weights={weights} />
        </div>
      </div>

      {/* ── Market rotation note (informational, not graded) ── */}
      <MarketRotation rotation={analysis?.rotation} />

      {/* ── Level 4: Grade History ── */}
      {gradeHistory.length > 0 && (
        <div style={cardStyle}>
          <div style={{ ...cardLabel, marginBottom: 12 }}>GRADE HISTORY</div>
          <GradeHistoryBars gradeHistory={gradeHistory} />
        </div>
      )}

    </div>
    </PaletteCtx.Provider>
  );
}

window.PortfolioPage = PortfolioPage;
