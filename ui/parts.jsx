/* Banshee — HUD parts */
const { useState, useEffect, useRef, useMemo } = React;

/* inject shimmer + flat-dashed styles once */
(function() {
  if (document.getElementById('banshee-card-states')) return;
  const s = document.createElement('style');
  s.id = 'banshee-card-states';
  s.textContent = `
    @keyframes banshee-shimmer {
      0%   { background-position: 200% 0; }
      100% { background-position: -200% 0; }
    }
    .b5-shimmer {
      background: linear-gradient(90deg, var(--bg-3) 25%, var(--bg-4,var(--bg-2)) 50%, var(--bg-3) 75%);
      background-size: 200% 100%;
      animation: banshee-shimmer 1.6s ease-in-out infinite;
    }
  `;
  document.head.appendChild(s);
})();

/* ── OHLCV debounce for custom-symbol sparklines ────────────── */
const _ohlcvCache     = {};  // { [sym]: [{c}...] | 'error' | 'loading' }
const _ohlcvCallbacks = {};  // { [sym]: [fn, ...] }
const _ohlcvQueue     = new Set();
let   _ohlcvTimer     = null;

window._requestOHLCV = function(sym, onResult) {
  if (_ohlcvCache[sym] === 'loading') {
    (_ohlcvCallbacks[sym] = _ohlcvCallbacks[sym] || []).push(onResult);
    return;
  }
  if (_ohlcvCache[sym]) {
    onResult(_ohlcvCache[sym] === 'error' ? [] : _ohlcvCache[sym]);
    return;
  }
  (_ohlcvCallbacks[sym] = _ohlcvCallbacks[sym] || []).push(onResult);
  _ohlcvQueue.add(sym);
  clearTimeout(_ohlcvTimer);
  _ohlcvTimer = setTimeout(async () => {
    const syms = [..._ohlcvQueue];
    _ohlcvQueue.clear();
    for (let i = 0; i < syms.length; i += 4) {
      await Promise.all(syms.slice(i, i + 4).map(async s => {
        _ohlcvCache[s] = 'loading';
        try {
          const pair = window.API.coreSymbol(s);
          const res  = await fetch(`http://localhost:8765/ohlcv?symbol=${encodeURIComponent(pair)}&mode=swing`);
          const data = await res.json();
          const recs = data.tfs?.['1h'];
          _ohlcvCache[s] = recs?.length
            ? recs.slice(-60).map(r => ({ o: r.open, h: r.high, l: r.low, c: r.close }))
            : 'error';
        } catch { _ohlcvCache[s] = 'error'; }
        const cbs = _ohlcvCallbacks[s] || [];
        delete _ohlcvCallbacks[s];
        const result = _ohlcvCache[s] === 'error' ? [] : _ohlcvCache[s];
        cbs.forEach(cb => cb(result));
      }));
    }
  }, 300);
};

/* ── tiny atoms ───────────────────────────────────────────── */

function Tag({ children, color = "var(--ink-3)", bg = "transparent", border, style }) {
  return (
    <span className="mono" style={{
      display: "inline-flex", alignItems: "center", gap: 4,
      fontSize: 13, letterSpacing: "0.14em", textTransform: "uppercase",
      color, padding: "2px 6px", background: bg,
      border: `1px solid ${border || "transparent"}`,
      lineHeight: 1.1, ...style,
    }}>{children}</span>
  );
}

function Dot({ color = "var(--ink-3)", size = 6, blink = false }) {
  return (
    <span className={blink ? "blink" : ""} style={{
      display: "inline-block", width: size, height: size,
      background: color, borderRadius: 999, boxShadow: `0 0 8px ${color}`,
      flex: "0 0 auto",
    }} />
  );
}

function Label({ children, color = "var(--ink-3)" }) {
  return (
    <div className="mono" style={{
      fontSize: 13, letterSpacing: "0.18em", textTransform: "uppercase",
      color, lineHeight: 1,
    }}>{children}</div>
  );
}

/* ── corner ticks (Star Trek HUD touch) ───────────────────── */
function CornerTicks({ color = "var(--line-2)" }) {
  const arm = 8;
  const s = { position: "absolute", width: arm, height: arm, borderColor: color };
  return (
    <>
      <span style={{ ...s, top: 0, left: 0, borderTop: "1px solid", borderLeft: "1px solid" }} />
      <span style={{ ...s, top: 0, right: 0, borderTop: "1px solid", borderRight: "1px solid" }} />
      <span style={{ ...s, bottom: 0, left: 0, borderBottom: "1px solid", borderLeft: "1px solid" }} />
      <span style={{ ...s, bottom: 0, right: 0, borderBottom: "1px solid", borderRight: "1px solid" }} />
    </>
  );
}

/* ── verdict color helpers ────────────────────────────────── */
function verdictColors(v) {
  if (v === "BUY")  return { fg: "var(--buy)",  bg: "rgba(94,234,212,0.08)",  glow: "var(--buy-glow)" };
  if (v === "SELL") return { fg: "var(--sell)", bg: "rgba(239,68,68,0.08)",   glow: "var(--sell-glow)" };
  return                  { fg: "var(--wait)", bg: "rgba(245,158,11,0.06)",  glow: "var(--wait-glow)" };
}

/* ── Edge ring (0-100 score) ──────────────────────────────── */
function EdgeRing({ value = 0, size = 56, color = "var(--cyan)", label = "EDGE" }) {
  const r = size / 2 - 5;
  const c = 2 * Math.PI * r;
  const off = c * (1 - value / 100);
  return (
    <div style={{ position: "relative", width: size, height: size, flex: "0 0 auto" }}>
      <svg width={size} height={size}>
        <circle cx={size/2} cy={size/2} r={r} fill="none" stroke="var(--line)" strokeWidth="2" />
        <circle cx={size/2} cy={size/2} r={r} fill="none" stroke={color} strokeWidth="2"
          strokeDasharray={c} strokeDashoffset={off} strokeLinecap="butt"
          transform={`rotate(-90 ${size/2} ${size/2})`}
          style={{ filter: `drop-shadow(0 0 4px ${color})` }} />
        {/* tick marks */}
        {Array.from({length: 20}).map((_, i) => {
          const a = (i / 20) * Math.PI * 2 - Math.PI / 2;
          const x1 = size/2 + Math.cos(a) * (r + 3);
          const y1 = size/2 + Math.sin(a) * (r + 3);
          const x2 = size/2 + Math.cos(a) * (r + 6);
          const y2 = size/2 + Math.sin(a) * (r + 6);
          return <line key={i} x1={x1} y1={y1} x2={x2} y2={y2} stroke="var(--line-2)" strokeWidth="1" />;
        })}
      </svg>
      <div style={{
        position: "absolute", inset: 0, display: "flex", flexDirection: "column",
        alignItems: "center", justifyContent: "center", gap: 1,
      }}>
        <div className="num" style={{ fontSize: 16, fontWeight: 600, color: "var(--ink)", lineHeight: 1 }}>{value}</div>
        <div className="mono" style={{ fontSize: 11, letterSpacing: "0.18em", color: "var(--ink-3)" }}>{label}</div>
      </div>
    </div>
  );
}

/* ── Sparkline ─────────────────────────────────────────────── */
function Spark({ candles, color = "var(--ink-2)", w = 160, h = 36, fill = true }) {
  if (!candles || !candles.length) return null;
  const closes = candles.map(c => c.c);
  const min = Math.min(...closes), max = Math.max(...closes);
  const rng = (max - min) || 1;
  const pts = closes.map((v, i) => {
    const x = (i / (closes.length - 1)) * w;
    const y = h - ((v - min) / rng) * (h - 4) - 2;
    return [x, y];
  });
  const d = pts.map(([x,y], i) => (i ? `L${x.toFixed(1)} ${y.toFixed(1)}` : `M${x.toFixed(1)} ${y.toFixed(1)}`)).join(" ");
  const fillD = `${d} L${w} ${h} L0 ${h} Z`;
  return (
    <svg width={w} height={h} style={{ display: "block" }}>
      {fill && <path d={fillD} fill={color} opacity="0.08" />}
      <path d={d} fill="none" stroke={color} strokeWidth="1.25" />
    </svg>
  );
}

function FlatDashedLine({ h = 36 }) {
  return (
    <svg width="100%" height={h} style={{ display: "block" }}>
      <line x1="4" y1={h / 2} x2="96%" y2={h / 2}
        stroke="var(--line-2)" strokeWidth="1" strokeDasharray="4 4" />
    </svg>
  );
}

/* ── Segmented battery / power bar (macro warning) ────────── */
function PowerBar({ value = 0, segments = 30, height = 24, label = "MACRO WARN" }) {
  const filled = Math.round((value / 100) * segments);
  const segColor = (i) => {
    const ratio = i / segments;
    if (ratio < 0.4)  return "var(--buy)";
    if (ratio < 0.7)  return "var(--wait)";
    return "var(--sell)";
  };
  const status =
    value < 30 ? { tx: "CALM",       c: "var(--buy)" } :
    value < 55 ? { tx: "NEUTRAL",    c: "var(--ink-2)" } :
    value < 75 ? { tx: "ELEVATED",   c: "var(--wait)" } :
                  { tx: "CRITICAL",   c: "var(--sell)" };
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 14, width: "100%" }}>
      <div style={{ display: "flex", flexDirection: "column", gap: 4, minWidth: 130 }}>
        <Label>{label}</Label>
        <div style={{ display: "flex", alignItems: "baseline", gap: 6 }}>
          <span className="num" style={{ fontSize: 20, color: status.c, fontWeight: 600, lineHeight: 1 }}>{value}</span>
          <span className="mono" style={{ fontSize: 12, color: "var(--ink-3)", letterSpacing: "0.16em" }}>/100</span>
          <span className="mono" style={{ fontSize: 13, color: status.c, letterSpacing: "0.18em", marginLeft: 6 }}>{status.tx}</span>
        </div>
      </div>
      <div style={{ flex: 1, display: "flex", gap: 2, height, alignItems: "stretch" }}>
        {Array.from({ length: segments }).map((_, i) => {
          const on = i < filled;
          return (
            <div key={i} style={{
              flex: 1,
              background: on ? segColor(i) : "rgba(255,255,255,0.04)",
              boxShadow: on ? `0 0 6px ${segColor(i)}80` : "none",
              clipPath: "polygon(2px 0, 100% 0, calc(100% - 2px) 100%, 0 100%)",
              opacity: on ? 1 : 0.5,
              transition: "all 200ms",
            }} />
          );
        })}
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 2, alignItems: "flex-end", minWidth: 96 }}>
        <Label>SIGNAL</Label>
        <div style={{ display: "inline-flex", gap: 6, alignItems: "center" }}>
          <Dot color={status.c} blink={value >= 75} />
          <span className="mono" style={{ fontSize: 13, color: status.c, letterSpacing: "0.14em" }}>
            {value >= 75 ? "ALERT" : value >= 55 ? "CAUTION" : "STABLE"}
          </span>
        </div>
      </div>
    </div>
  );
}

/* ── Mini bar gauge for sub-metrics ────────────────────────── */
function MiniBar({ value, max = 100, color = "var(--cyan)", w = 70 }) {
  const pct = Math.min(100, (value / max) * 100);
  return (
    <div style={{ width: w, height: 4, background: "var(--bg-3)", position: "relative", overflow: "hidden" }}>
      <div style={{
        width: pct + "%", height: "100%", background: color,
        boxShadow: `0 0 6px ${color}`,
      }} />
    </div>
  );
}

/* ── Asset card ────────────────────────────────────────────── */
function AssetCard({ asset, onClick, selected }) {
  const dataState = asset._dataState || "LIVE";
  const isInit    = dataState === "INIT";
  const isCached  = dataState === "CACHED";
  const isLive    = dataState === "LIVE";

  const c = isInit
    ? { fg: "var(--line-2)", bg: "transparent", glow: "transparent" }
    : verdictColors(asset.verdict);

  const knownCandles = useMemo(
    () => window.ASSETS.find(a => a.sym === asset.sym)
      ? window.buildCandles(asset.sym, "1H", 60) : null,
    [asset.sym]
  );
  const [customCandles, setCustomCandles] = useState(null);
  useEffect(() => {
    if (knownCandles === null && customCandles === null && !isInit) {
      window._requestOHLCV(asset.sym, (candles) => setCustomCandles(candles));
    }
  }, [asset.sym, isInit]);

  const candles = knownCandles ?? customCandles ?? [];
  const up = (asset.chg ?? 0) >= 0;

  /* badge label + color */
  const badgeLabel = isInit ? "◇ INIT" : isCached ? "◈ CACHED" : "◆ LIVE";
  const badgeColor = isInit
    ? "var(--ink-4)"
    : isCached
      ? "var(--wait)"
      : "var(--buy)";

  return (
    <button
      onClick={onClick}
      style={{
        position: "relative", textAlign: "left",
        background: "linear-gradient(180deg, var(--bg-2), var(--bg-1))",
        border: `1px solid ${selected ? c.fg : "var(--line)"}`,
        padding: 0, cursor: "pointer",
        transition: "border-color 200ms",
        boxShadow: selected ? `0 0 0 1px ${c.fg} inset, 0 0 24px ${c.glow}` : "none",
        overflow: "hidden",
      }}
      onMouseEnter={(e) => { if (!selected) e.currentTarget.style.borderColor = "var(--line-2)"; }}
      onMouseLeave={(e) => { if (!selected) e.currentTarget.style.borderColor = "var(--line)"; }}
    >
      {/* top stripe */}
      <div style={{
        height: 3, width: "100%",
        background: isInit
          ? "var(--line)"
          : `linear-gradient(90deg, ${c.fg}, ${c.fg}30 60%, transparent)`,
      }} />

      <div style={{ padding: "10px 12px 12px 12px", display: "flex", flexDirection: "column", gap: 10 }}>
        {/* header row */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 8 }}>
          <div style={{ minWidth: 0 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <div className="mono" style={{ fontSize: 14, fontWeight: 600, color: "var(--ink)", letterSpacing: "0.04em" }}>
                {asset.sym}
              </div>
              <Tag border="var(--line)" style={{ fontSize: 11 }}>{asset.cls}</Tag>
            </div>
            <div style={{ fontSize: 13, color: "var(--ink-3)", marginTop: 2, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
              {asset.name} · {asset.pair || asset.sym}
            </div>
          </div>
          <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 2 }}>
            <div className="num" style={{ fontSize: 16, fontWeight: 600, color: isInit ? "var(--ink-4)" : "var(--ink)", lineHeight: 1 }}>
              {isInit ? "—"
                : asset.price < 10   ? asset.price.toFixed(3)
                : asset.price < 100  ? asset.price.toFixed(2)
                : asset.price.toLocaleString(undefined, { maximumFractionDigits: 2 })}
            </div>
            {!isInit && (
              <div className="num" style={{ fontSize: 13, color: up ? "var(--buy)" : "var(--sell)", lineHeight: 1 }}>
                {up ? "+" : ""}{(asset.chg ?? 0).toFixed(2)}%
              </div>
            )}
            <div className="mono" style={{ fontSize: 11, letterSpacing: "0.14em", color: badgeColor, lineHeight: 1 }}>
              {badgeLabel}
            </div>
          </div>
        </div>

        {/* spark area */}
        <div style={{ position: "relative", height: 36 }}>
          {isInit
            ? <div className="b5-shimmer" style={{ height: 36 }} />
            : (candles.length > 0 && isLive)
              ? <Spark candles={candles} color={up ? "var(--buy)" : "var(--sell)"} w={400} h={36} />
              : <FlatDashedLine />
          }
        </div>

        {/* verdict + edge row */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 10 }}>
          {isInit ? (
            <div style={{
              display: "flex", alignItems: "center", gap: 8,
              padding: "5px 10px",
              background: "transparent",
              border: "1px dashed var(--line-2)",
              clipPath: "polygon(6px 0, 100% 0, calc(100% - 6px) 100%, 0 100%)",
            }}>
              <span className="mono" style={{ fontSize: 12, color: "var(--ink-3)", letterSpacing: "0.14em" }}>
                — PENDING —
              </span>
            </div>
          ) : (
            <div style={{
              display: "flex", alignItems: "center", gap: 8,
              padding: "5px 10px",
              background: c.bg,
              border: `1px solid ${c.fg}40`,
              clipPath: "polygon(6px 0, 100% 0, calc(100% - 6px) 100%, 0 100%)",
            }}>
              <Dot color={c.fg} blink={asset.verdict !== "WAIT"} size={5} />
              <span className="mono" style={{ fontSize: 13, color: c.fg, fontWeight: 600, letterSpacing: "0.16em" }}>
                {asset.verdict}
              </span>
            </div>
          )}
          <EdgeRing
            value={isInit ? 0 : asset.edge}
            size={48}
            color={isInit ? "var(--line-2)" : c.fg}
            label={isInit ? "?" : "EDGE"}
          />
        </div>

        {/* footer metrics */}
        <div style={{
          display: "grid", gridTemplateColumns: "1fr 1fr", gap: "6px 10px",
          paddingTop: 8, borderTop: "1px dashed var(--line)",
          opacity: isInit ? 0.4 : 1,
        }}>
          <div style={{ display: "flex", flexDirection: "column", gap: 3 }}>
            <Label>BIAS</Label>
            <div className="mono" style={{ fontSize: 13, color: "var(--ink-2)", letterSpacing: "0.08em" }}>
              {isInit ? "—" : asset.bias}
            </div>
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 3, alignItems: "flex-end" }}>
            <Label>RSI</Label>
            <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
              {!isInit && <MiniBar value={asset.rsi} color={asset.rsi > 70 ? "var(--sell)" : asset.rsi < 30 ? "var(--buy)" : "var(--cyan)"} w={42} />}
              <span className="num" style={{ fontSize: 13, color: "var(--ink-2)" }}>
                {isInit ? "—" : asset.rsi}
              </span>
            </div>
          </div>
        </div>
      </div>
    </button>
  );
}

/* ── SMC overlay primitives for Lightweight Charts ─────────── */

class SMCZoneRenderer {
  constructor(source) { this._source = source; }

  draw(target) {
    const series = this._source._series;
    const chart  = this._source._chart;
    if (!series) return;
    const zones = this._source._zones;
    if (!zones.length) return;

    target.useBitmapCoordinateSpace((scope) => {
      const ctx = scope.context;
      const { verticalPixelRatio: vr, horizontalPixelRatio: hr, bitmapSize } = scope;
      const bw = bitmapSize.width;
      const bh = bitmapSize.height;
      ctx.save();

      const currentPrice     = this._source._currentPrice;
      const lensMode         = this._source._lensMode;
      const currentTimestamp = this._source._currentTimestamp; // Unix int (seconds)
      const activeOnly       = this._source._activeOnly;

      /* ISO-string zone timestamp → bitmap x pixel */
      const tScale = chart ? chart.timeScale() : null;
      function txToX(tsStr) {
        if (!tsStr || !tScale) return null;
        const unix = Math.floor(new Date(tsStr).getTime() / 1000);
        if (!Number.isFinite(unix)) return null;
        const coord = tScale.timeToCoordinate(unix);
        return coord === null || !Number.isFinite(coord) ? null : Math.round(coord * hr);
      }

      for (const z of zones) {
        /* skip ghost zones when activeOnly override is on */
        if (z.ghost && activeOnly) continue;

        const rawTop = series.priceToCoordinate(z.top);
        const rawBot = series.priceToCoordinate(z.bottom);
        if (rawTop === null && rawBot === null) continue;
        const topPx = Math.max(0, Math.min(rawTop ?? 0, rawBot ?? bh / vr) * vr);
        const botPx = Math.min(bh, Math.max(rawTop ?? 0, rawBot ?? bh / vr) * vr);
        const h = Math.max(1, botPx - topPx);

        /* ── Time-bounded x coordinates ──────────────────────────────── */
        const xLeftRaw = z.timestamp ? txToX(z.timestamp) : null;
        const xLeft    = xLeftRaw !== null ? Math.max(0, xLeftRaw) : 0;

        let xRight;
        if (z.end_timestamp) {
          /* mitigated zone: cap at the mitigation candle */
          const x = txToX(z.end_timestamp);
          xRight = x !== null ? Math.min(bw, x) : bw;
        } else if (currentTimestamp && tScale) {
          /* active zone: extend to the current (last loaded) candle */
          const coord = tScale.timeToCoordinate(currentTimestamp);
          const x     = coord !== null ? Math.round(coord * hr) : null;
          xRight = x !== null ? Math.min(bw, x) : bw;
        } else {
          xRight = bw;
        }

        if (xLeft >= xRight) continue; /* entirely off screen or zero-width */
        const w = xRight - xLeft;

        /* Dynamic visual weight (distance-from-price dimming, non-ghost zones only) */
        let dynMult = 1.0;
        if (!z.ghost && lensMode !== 4 && currentPrice && currentPrice > 0) {
          const mid = (z.top + z.bottom) / 2;
          const pct = Math.abs(mid - currentPrice) / currentPrice;
          if (pct > 0.03) dynMult = 0.35;
        }

        /* Spec color system — direct hex, no CSS vars */
        const OB_FILL   = { bullish: "#1565C0", bearish: "#B71C1C" };
        const OB_BORDER = { bullish: "#42A5F5", bearish: "#EF5350" };
        const FVG_COLOR = { bullish: "#00BCD4", bearish: "#F44336" };

        const fillBase = z.isFVG
          ? (FVG_COLOR[z.kind] || "#00BCD4")
          : (z.status === "degraded" ? "#607D8B" : (OB_FILL[z.kind] || "#1565C0"));

        const bordBase = z.isFVG ? fillBase
          : z.inducement_swept       ? "#00E676"
          : z.has_pending_inducement ? "#FFB300"
          : (OB_BORDER[z.kind] || "#42A5F5");

        const statusMult = z.isFVG ? 1.0
          : z.status === "degraded" ? 0.50
          : z.status === "touched"  ? 0.75
          : 1.0;

        /* Ghost zones: fixed opacity, bypass multipliers for exact values */
        let fillAlp, bordAlp, useDash;
        if (z.ghost) {
          fillAlp = 0.12;
          bordAlp = 0.30;
          useDash = true;
        } else {
          fillAlp = z.isFVG
            ? (z.status === "partial" ? 0.25 : 0.55)
            : (z.dashed ? 0.06 : 0.22);
          bordAlp = z.dashed ? 0.28 : 0.75;
          useDash = z.dashed || false;
        }

        /* Ghost: raw alpha → hex. Active: multiplied alpha → hex. */
        const toFill = z.ghost
          ? (a) => Math.round(a * 255).toString(16).padStart(2, "0")
          : (a) => Math.round(a * z.opacity * statusMult * dynMult * 255).toString(16).padStart(2, "0");
        const toBord = z.ghost
          ? (a) => Math.round(a * 255).toString(16).padStart(2, "0")
          : (a) => Math.round(a * z.opacity * statusMult * dynMult * 255).toString(16).padStart(2, "0");

        ctx.fillStyle = fillBase + toFill(fillAlp);
        ctx.fillRect(xLeft, topPx, w, h);

        if (w > hr && h > vr) {
          ctx.strokeStyle = bordBase + toBord(bordAlp);
          ctx.lineWidth   = (z.inducement_swept || z.has_pending_inducement ? 2 : 1) * hr;
          ctx.setLineDash(useDash ? [4 * hr, 4 * hr] : []);
          ctx.strokeRect(xLeft + 0.5 * hr, topPx + 0.5 * vr, w - hr, h - vr);
          ctx.setLineDash([]);
        }

        /* FVG formation tick — vertical anchor line at creation candle (active FVGs only) */
        if (z.isFVG && !z.ghost && z.timestamp && chart) {
          const xFvg = txToX(z.timestamp);
          if (xFvg !== null && xFvg >= xLeft && xFvg <= xRight) {
            ctx.strokeStyle = fillBase + "dd";
            ctx.lineWidth   = 2 * hr;
            ctx.setLineDash([]);
            ctx.beginPath();
            ctx.moveTo(xFvg, topPx);
            ctx.lineTo(xFvg, botPx);
            ctx.stroke();
            ctx.font      = `bold ${Math.max(11, Math.round(8 * Math.min(vr, hr)))}px 'JetBrains Mono', monospace`;
            ctx.fillStyle = fillBase + "cc";
            ctx.textAlign = "center";
            if (z.kind === "bullish") {
              ctx.fillText("FVG▲", xFvg, topPx - 4 * vr);
            } else {
              ctx.fillText("FVG▼", xFvg, botPx + 10 * vr);
            }
          }
        }

        /* Session weight badges + ★ HTF confluence (active OBs only, aligned to zone right edge) */
        if (!z.isFVG && !z.ghost && h > 12 * vr) {
          const sw      = z.session_weight || 1.0;
          const hasConf = Array.isArray(z.htf_confluence) && z.htf_confluence.length > 0;

          let badge = "", badgeColor = "";
          if (sw >= 2.0)      { badge = "⚡"; badgeColor = "#FFD600"; }
          else if (sw >= 1.5) { badge = "◈"; badgeColor = "#FF8F00"; }
          else if (sw < 1.0)  { badge = "·"; badgeColor = "#607D8B"; }

          const fSize = Math.max(11, Math.round(10 * Math.min(vr, hr)));
          const baseX = xRight - 5 * hr; /* follow the zone's right edge, not canvas right */
          const baseY = topPx + 12 * vr;
          let curX    = baseX;

          ctx.textAlign = "right";
          if (badge) {
            ctx.font      = `${fSize}px sans-serif`;
            ctx.fillStyle = badgeColor + Math.round(z.opacity * dynMult * 220).toString(16).padStart(2, "0");
            ctx.fillText(badge, curX, baseY);
            curX -= 14 * hr;
          }
          if (hasConf) {
            ctx.font      = `bold ${fSize}px sans-serif`;
            ctx.fillStyle = "#FFFFFF" + Math.round(z.opacity * dynMult * 220).toString(16).padStart(2, "0");
            ctx.fillText("★", curX, baseY);
          }
        }
      }
      ctx.restore();
    });
  }
}

class SMCZonePaneView {
  constructor(source) { this._renderer = new SMCZoneRenderer(source); }
  renderer() { return this._renderer; }
  zOrder()   { return "bottom"; }
}

class SMCZonePrimitive {
  constructor(zones, chart, lensMode = 1, currentPrice = null, currentTimestamp = null, activeOnly = false) {
    this._zones            = zones;
    this._chart            = chart || null;
    this._lensMode         = lensMode;
    this._currentPrice     = currentPrice;
    this._currentTimestamp = currentTimestamp;
    this._activeOnly       = activeOnly;
    this._series           = null;
    this._paneViews        = [new SMCZonePaneView(this)];
  }
  attached({ series }) { this._series = series; }
  detached()           { this._series = null; }
  updateAllViews()     {}
  paneViews()          { return this._paneViews; }
}

/* parse /smc/json response into a flat zones array */
function smcToZones(smcData) {
  if (!smcData || smcData.error || !smcData.ltf_smc) return [];
  const ltf   = smcData.ltf_smc;
  const zones = [];

  for (const ob of (ltf.order_blocks || [])) {
    const isGhost = ["mitigated", "sapped", "invalidated"].includes(ob.status);
    zones.push({
      type:                   "ob",
      kind:                   ob.kind,
      top:                    ob.zone_top,
      bottom:                 ob.zone_bottom,
      status:                 ob.status || "active",
      has_pending_inducement: ob.has_pending_inducement || false,
      inducement_swept:       ob.inducement_swept       || false,
      gate_passed:            ob.gate_passed !== false,
      dashed:                 !ob.gate_passed,
      opacity:                ob.gate_passed ? 1.0 : 0.45,
      isFVG:                  false,
      session_weight:         ob.session_weight         || 1.0,
      htf_confluence:         ob.htf_confluence         || [],
      touch_count:            ob.touch_count            || 0,
      timestamp:              ob.timestamp              || null,
      end_timestamp:          ob.end_timestamp          || null,
      ghost:                  isGhost,
    });
  }

  for (const fvg of (ltf.fvgs || [])) {
    const isGhost = fvg.status === "mitigated";
    zones.push({
      type:           "fvg",
      kind:           fvg.kind,
      top:            fvg.top,
      bottom:         fvg.bottom,
      status:         fvg.status,
      timestamp:      fvg.timestamp     || null,
      end_timestamp:  fvg.end_timestamp || null,
      ghost:          isGhost,
      dashed:         false,
      opacity:        1.0,
      isFVG:          true,
      htf_confluence: fvg.htf_confluence || [],
      fill_pct:       typeof fvg.fill_pct === "number" ? fvg.fill_pct
                      : (fvg.status === "partial" ? 40 : 0),
    });
  }

  return zones;
}

/* ── SMC marker primitives (swing labels, BOS/CHoCH) ────── */

class SMCMarkersRenderer {
  constructor(source) { this._source = source; }

  draw(target) {
    const series = this._source._series;
    const chart  = this._source._chart;
    const swings = this._source._swings;
    const events = this._source._events;
    if (!series || !chart) return;

    target.useBitmapCoordinateSpace((scope) => {
      const ctx = scope.context;
      const { verticalPixelRatio: vr, horizontalPixelRatio: hr, bitmapSize } = scope;
      const bw  = bitmapSize.width;
      const bh  = bitmapSize.height;
      const ts  = chart.timeScale();
      ctx.save();

      function txToX(tsStr) {
        if (!tsStr || !ts) return null;
        const unix = Math.floor(new Date(tsStr).getTime() / 1000);
        if (!Number.isFinite(unix)) return null;
        const coord = ts.timeToCoordinate(unix);
        return coord === null || !Number.isFinite(coord) ? null : Math.round(coord * hr);
      }
      function priceToY(p) {
        const coord = series.priceToCoordinate(p);
        return coord === null ? null : Math.round(coord * vr);
      }

      /* Swing labels — 16px triangles, spec colors */
      const lensMode     = this._source._lensMode;
      const currentPrice = this._source._currentPrice;
      ctx.font = `${Math.max(11, Math.round(9 * hr))}px 'JetBrains Mono', monospace`;
      ctx.textAlign = "center";
      for (const sw of swings) {
        const x = txToX(sw.timestamp);
        const y = priceToY(sw.price);
        if (x === null || y === null) continue;
        const isHigh = sw.swing_type === "high";
        const base   = isHigh ? "#FF6D00" : "#2979FF";
        const label  = sw.label || (isHigh ? "H" : "L");
        const triSize = 8 * Math.min(vr, hr);

        let markerAlpha = "cc";
        if (currentPrice && sw.price) {
          const hot = Math.abs(sw.price - currentPrice) / currentPrice <= 0.03;
          if (!hot) markerAlpha = "55";
        }

        ctx.fillStyle = base + markerAlpha;
        ctx.beginPath();
        if (isHigh) {
          ctx.moveTo(x, y - triSize);
          ctx.lineTo(x - triSize, y);
          ctx.lineTo(x + triSize, y);
        } else {
          ctx.moveTo(x, y + triSize);
          ctx.lineTo(x - triSize, y);
          ctx.lineTo(x + triSize, y);
        }
        ctx.fill();
        ctx.font = `${Math.max(11, Math.round(9 * hr))}px 'JetBrains Mono', monospace`;
        ctx.fillStyle = base + markerAlpha;
        if (isHigh) ctx.fillText(label, x, y - triSize - 4 * vr);
        else        ctx.fillText(label, x, y + triSize + 10 * vr);
      }

      /* BOS / CHoCH event markers — colored boxes in BATTLEFIELD, text elsewhere */
      const isBattlefield = lensMode === 2;
      for (const ev of events) {
        const x = txToX(ev.timestamp);
        const y = priceToY(ev.price);
        if (x === null || y === null) continue;
        const isBull = ev.event_type.includes("BULL");
        const isBOS  = ev.event_type.startsWith("BOS");

        const base = isBOS
          ? (isBull ? "#00E676" : "#FF1744")
          : (isBull ? "#69F0AE" : "#FF5252");

        const lbl = `${isBOS ? "BOS" : "CHoCH"} ${isBull ? "▲" : "▼"}`;
        const fSize = Math.round(9 * hr);

        ctx.strokeStyle = base + "66";
        ctx.lineWidth   = 1 * hr;
        ctx.setLineDash(isBOS ? [4 * hr, 3 * hr] : [2 * hr, 3 * hr]);
        ctx.beginPath();
        ctx.moveTo(x - 12 * hr, y);
        ctx.lineTo(x + 12 * hr, y);
        ctx.stroke();
        ctx.setLineDash([]);

        ctx.font = `bold ${fSize}px 'JetBrains Mono', monospace`;
        if (isBattlefield) {
          const metrics = ctx.measureText(lbl);
          const padX = 4 * hr, padY = 3 * vr;
          const bxW = metrics.width + padX * 2;
          const bxH = fSize + padY * 2;
          const bxX = Math.max(2 * hr, Math.min(x + 4 * hr, bw - bxW - 2 * hr));
          const bxY = Math.max(2 * vr, Math.min(y - bxH - 2 * vr, bh - bxH - 2 * vr));
          ctx.fillStyle = base + "cc";
          ctx.fillRect(bxX, bxY, bxW, bxH);
          ctx.fillStyle = "#000000ee";
          ctx.textAlign = "left";
          ctx.fillText(lbl, bxX + padX, bxY + bxH - padY - 1 * vr);
        } else {
          const txtW = ctx.measureText(lbl).width;
          const txtX = Math.max(2 * hr, Math.min(x + 4 * hr, bw - txtW - 2 * hr));
          const txtY = Math.max(fSize + 2 * vr, Math.min(y - 5 * vr, bh - 2 * vr));
          ctx.fillStyle = base + "dd";
          ctx.textAlign = "left";
          ctx.fillText(lbl, txtX, txtY);
        }
      }

      ctx.restore();
    });
  }
}

class SMCMarkersPaneView {
  constructor(source) { this._renderer = new SMCMarkersRenderer(source); }
  renderer() { return this._renderer; }
  zOrder()   { return "top"; }
}

class SMCMarkersPrimitive {
  constructor(swings, events, chart, lensMode = 1, currentPrice = null) {
    this._swings       = swings;
    this._events       = events;
    this._chart        = chart;
    this._lensMode     = lensMode;
    this._currentPrice = currentPrice;
    this._series       = null;
    this._paneViews    = [new SMCMarkersPaneView(this)];
  }
  attached({ series }) { this._series = series; }
  detached()           { this._series = null; }
  updateAllViews()     {}
  paneViews()          { return this._paneViews; }
}

function smcToMarkers(smcData) {
  if (!smcData || smcData.error || !smcData.ltf_smc) return { swings: [], events: [] };
  const ltf    = smcData.ltf_smc;
  const highs  = (ltf.swing_highs || []).slice(-8);
  const lows   = (ltf.swing_lows  || []).slice(-8);
  const swings = [...highs, ...lows]
    .filter(s => s.label)
    .sort((a, b) => a.idx - b.idx)
    .slice(-14);
  const events = (ltf.structure_events || []).slice(-6);
  return { swings, events };
}

/* ── XABCD harmonic overlay primitives ───────────────────── */

class XABCDRenderer {
  constructor(source) { this._source = source; }

  draw(target) {
    const series   = this._source._series;
    const chart    = this._source._chart;
    const patterns = this._source._patterns;
    if (!series || !chart || !patterns.length) return;

    target.useBitmapCoordinateSpace((scope) => {
      const ctx = scope.context;
      const { verticalPixelRatio: vr, horizontalPixelRatio: hr, bitmapSize } = scope;
      const bw = bitmapSize.width;
      ctx.save();

      const ts = chart.timeScale();

      /* "YYYY-MM-DD" → bitmap X coordinate (null if off-screen) */
      function txToX(tsStr) {
        const unix = Math.floor(new Date(tsStr).getTime() / 1000);
        const coord = ts.timeToCoordinate(unix);
        return coord === null ? null : Math.round(coord * hr);
      }
      function priceToY(p) {
        const coord = series.priceToCoordinate(p);
        return coord === null ? null : Math.round(coord * vr);
      }

      for (const pat of patterns) {
        const isForming = pat.type === "forming";
        const bull      = pat.direction === "bullish";
        const base      = bull ? "#5eead4" : "#ef4444";
        const pointKeys = isForming ? ["X","A","B","C"] : ["X","A","B","C","D"];

        /* collect pixel coordinates for each point */
        const coords = pointKeys.map(k => {
          const pt = pat.points[k];
          if (!pt) return null;
          return { key: k, x: txToX(pt.ts), y: priceToY(pt.price), price: pt.price };
        }).filter(Boolean);

        /* leg polyline */
        ctx.strokeStyle = base + (isForming ? "88" : "cc");
        ctx.lineWidth   = 1.5 * hr;
        if (isForming) ctx.setLineDash([5 * hr, 4 * hr]);
        ctx.beginPath();
        let started = false;
        for (const { x, y } of coords) {
          if (x === null || y === null) { started = false; continue; }
          if (!started) { ctx.moveTo(x, y); started = true; }
          else ctx.lineTo(x, y);
        }
        ctx.stroke();
        ctx.setLineDash([]);

        /* PRZ rendering */
        if (isForming && pat.przLo != null && pat.przHi != null) {
          /* shaded band */
          const y1 = priceToY(pat.przHi);
          const y2 = priceToY(pat.przLo);
          if (y1 !== null && y2 !== null) {
            const top = Math.min(y1, y2);
            const h   = Math.max(2, Math.abs(y2 - y1));
            ctx.fillStyle   = base + "28";
            ctx.fillRect(0, top, bw, h);
            ctx.strokeStyle = base + "66";
            ctx.lineWidth   = 1 * hr;
            ctx.strokeRect(0.5, top + 0.5, bw - 1, h - 1);
          }
        } else if (!isForming && pat.prz != null) {
          /* dotted horizontal line at D */
          const y = priceToY(pat.prz);
          if (y !== null) {
            ctx.strokeStyle = base + "88";
            ctx.lineWidth   = 1 * hr;
            ctx.setLineDash([4 * hr, 4 * hr]);
            ctx.beginPath();
            ctx.moveTo(0, y);
            ctx.lineTo(bw, y);
            ctx.stroke();
            ctx.setLineDash([]);
          }
        }

        /* point labels */
        ctx.font      = `${Math.round(9 * hr)}px 'JetBrains Mono', monospace`;
        ctx.fillStyle = base + "cc";
        for (const { key, x, y } of coords) {
          if (x === null || y === null) continue;
          ctx.fillText(key, x + 3 * hr, y - 5 * vr);
        }
      }

      ctx.restore();
    });
  }
}

class XABCDPaneView {
  constructor(source) { this._renderer = new XABCDRenderer(source); }
  renderer() { return this._renderer; }
  zOrder()   { return "top"; }
}

class XABCDPrimitive {
  constructor(patterns, chart) {
    this._patterns  = patterns;
    this._chart     = chart;
    this._series    = null;
    this._paneViews = [new XABCDPaneView(this)];
  }
  attached({ series }) { this._series = series; }
  detached()           { this._series = null; }
  updateAllViews()     {}
  paneViews()          { return this._paneViews; }
}

/* parse /xabcd response into normalised pattern array */
function xabcdToPatterns(data) {
  if (!data || data.error) return [];
  const out = [];
  for (const p of (data.confirmed || [])) {
    out.push({
      type: "confirmed", patternName: p.pattern, direction: p.direction,
      confidence: p.confidence, points: p.points,
      prz: p.prz, przLo: null, przHi: null,
    });
  }
  for (const p of (data.forming || [])) {
    out.push({
      type: "forming", patternName: p.pattern, direction: p.direction,
      confidence: p.confidence, points: p.points,
      prz: p.prz_mid, przLo: p.prz_lo, przHi: p.prz_hi,
    });
  }
  return out;
}

/* ── Geo Harmonic arc overlay primitives ─────────────────── */

class GHArcRenderer {
  constructor(source) { this._source = source; }

  draw(target) {
    const series  = this._source._series;
    const chart   = this._source._chart;
    const circles = this._source._circles;
    const scMacro = this._source._scMacro;
    if (!series || !chart || !circles.length) return;

    target.useBitmapCoordinateSpace((scope) => {
      const ctx = scope.context;
      const { verticalPixelRatio: vr, horizontalPixelRatio: hr, bitmapSize } = scope;
      ctx.save();

      const ts = chart.timeScale();

      /* pixels-per-bar at current zoom (bitmap coords) */
      const visRange = ts.getVisibleLogicalRange();
      if (!visRange) { ctx.restore(); return; }
      const pxPerBar = bitmapSize.width / (visRange.to - visRange.from);

      /* pixels per one log-norm unit — one unit = sc_macro in log-price */
      const refP  = series.priceToCoordinate(circles[0].center_price);
      const refPU = series.priceToCoordinate(circles[0].center_price * Math.exp(scMacro));
      if (refP === null || refPU === null) { ctx.restore(); return; }
      const pxPerLogNorm = Math.abs((refPU - refP) * vr);

      const BIAS_COLOR  = { floor: "#5eead4", ceiling: "#ef4444", mixed: "#f59e0b" };
      const RENDER_FIBS = [0.382, 0.500, 0.618, 0.786, 1.000, 1.618];

      for (const c of circles) {
        const cxCSS = ts.logicalToCoordinate(c.cx_bar);
        const cyCSS = series.priceToCoordinate(c.center_price);
        if (cxCSS === null || cyCSS === null) continue;
        const cx_px = cxCSS * hr;
        const cy_px = cyCSS * vr;
        const base  = BIAS_COLOR[c.origin] || "#f59e0b";

        for (const fib of RENDER_FIBS) {
          const r     = c.r_base * fib;
          const rx_px = r * pxPerBar;
          const ry_px = r * pxPerLogNorm;
          if (rx_px < 0.5 || ry_px < 0.5) continue;

          const alpha = fib >= 0.99 ? "cc" : fib >= 0.75 ? "77" : fib >= 0.59 ? "99" : fib >= 0.49 ? "66" : "44";
          const lw    = (fib >= 0.99 ? 2 : fib >= 0.59 ? 1.5 : 1) * hr;

          ctx.strokeStyle = base + alpha;
          ctx.lineWidth   = lw;
          ctx.beginPath();
          ctx.ellipse(cx_px, cy_px, rx_px, ry_px, 0, 0, 2 * Math.PI);
          ctx.stroke();
        }
      }

      ctx.restore();
    });
  }
}

class GHArcPaneView {
  constructor(source) { this._renderer = new GHArcRenderer(source); }
  renderer() { return this._renderer; }
  zOrder()   { return "top"; }
}

class GHArcPrimitive {
  constructor(circles, scMacro, chart) {
    this._circles  = circles;
    this._scMacro  = scMacro;
    this._chart    = chart;
    this._series   = null;
    this._paneViews = [new GHArcPaneView(this)];
  }
  attached({ series }) { this._series = series; }
  detached()           { this._series = null; }
  updateAllViews()     {}
  paneViews()          { return this._paneViews; }
}

/* ── Candlestick chart — Lightweight Charts ───────────────── */
/* ── Premium / Discount / OTE background zones ──────────────── */

class SMCPDZoneRenderer {
  constructor(source) { this._source = source; }
  draw(target) {
    const series = this._source._series;
    const pd     = this._source._pd;
    if (!series || !pd) return;
    target.useBitmapCoordinateSpace((scope) => {
      const ctx = scope.context;
      const { verticalPixelRatio: vr, bitmapSize } = scope;
      const bw = bitmapSize.width;
      const bh = bitmapSize.height;
      ctx.save();
      const py = (p) => {
        const c = series.priceToCoordinate(p);
        return c === null ? null : Math.round(c * vr);
      };

      /* Only paint inside the current dealing range (range_low → range_high).
         Without this clip, the premium zone would cover the entire chart above EQ,
         which on a long-term BTC chart is the whole canvas. */
      const eqY  = py(pd.discount_top);
      const rhY  = pd.range_high ? py(pd.range_high) : null;
      const rlY  = pd.range_low  ? py(pd.range_low)  : null;
      if (eqY !== null && rhY !== null && rlY !== null) {
        const topClip = Math.max(0,  Math.min(rhY, bh));   /* range_high on screen */
        const botClip = Math.max(0,  Math.min(rlY, bh));   /* range_low  on screen */
        const midClip = Math.max(0,  Math.min(eqY, bh));   /* equilibrium on screen */

        /* premium = top half of dealing range — vivid gradient, hot at ceiling */
        if (topClip < midClip) {
          const premGrad = ctx.createLinearGradient(0, topClip, 0, midClip);
          premGrad.addColorStop(0,   "rgba(220,0,0,0.45)");
          premGrad.addColorStop(0.4, "rgba(200,0,0,0.28)");
          premGrad.addColorStop(1,   "rgba(160,0,0,0.06)");
          ctx.fillStyle = premGrad;
          ctx.fillRect(0, topClip, bw, midClip - topClip);
          /* PREMIUM label — just inside the ceiling */
          ctx.font      = `bold ${Math.max(11, Math.round(10 * Math.min(vr, hr)))}px 'JetBrains Mono', monospace`;
          ctx.fillStyle = "rgba(255,80,80,0.9)";
          ctx.textAlign = "right";
          ctx.fillText("▲ PREMIUM  SELL ZONE", bw - 8 * hr, topClip + 14 * vr);
        }

        /* discount = bottom half of dealing range — cool green, soft */
        if (midClip < botClip) {
          const discGrad = ctx.createLinearGradient(0, midClip, 0, botClip);
          discGrad.addColorStop(0,   "rgba(0,150,80,0.05)");
          discGrad.addColorStop(0.6, "rgba(0,180,80,0.18)");
          discGrad.addColorStop(1,   "rgba(0,200,80,0.30)");
          ctx.fillStyle = discGrad;
          ctx.fillRect(0, midClip, bw, botClip - midClip);
          /* DISCOUNT label — just above range_low */
          ctx.font      = `bold ${Math.max(11, Math.round(10 * Math.min(vr, hr)))}px 'JetBrains Mono', monospace`;
          ctx.fillStyle = "rgba(60,220,120,0.85)";
          ctx.textAlign = "right";
          ctx.fillText("▼ DISCOUNT  BUY ZONE", bw - 8 * hr, botClip - 6 * vr);
        }

        /* equilibrium dotted line + label */
        if (midClip >= 0 && midClip <= bh) {
          ctx.strokeStyle = "#9ca3af50";
          ctx.lineWidth   = 1 * vr;
          ctx.setLineDash([4, 4]);
          ctx.beginPath();
          ctx.moveTo(0, midClip);
          ctx.lineTo(bw, midClip);
          ctx.stroke();
          ctx.setLineDash([]);
          ctx.font      = `${Math.max(11, Math.round(8 * Math.min(vr, hr)))}px 'JetBrains Mono', monospace`;
          ctx.fillStyle = "#9ca3af70";
          ctx.textAlign = "right";
          ctx.fillText("EQ", bw - 8 * hr, midClip - 3 * vr);
        }
      }
      /* OTE handled as price lines outside this renderer — no fill here */
      ctx.restore();
    });
  }
}
class SMCPDPaneView {
  constructor(source) { this._renderer = new SMCPDZoneRenderer(source); }
  renderer() { return this._renderer; }
  zOrder()   { return "normal"; }
}
class SMCPDPrimitive {
  constructor(pd) {
    this._pd        = pd;
    this._series    = null;
    this._paneViews = [new SMCPDPaneView(this)];
  }
  attached({ series }) { this._series = series; }
  detached()           { this._series = null; }
  updateAllViews()     {}
  paneViews()          { return this._paneViews; }
}
function smcToPDZone(smcData) {
  return smcData?.ltf_smc?.pd_zones || null;
}

/* ── SMC Legend — standalone panel, placed below the chart ──── */
function SMCLegend() {
  const rows = [
    { swatch: "#3b82f6", swatchStyle: {}, label: "Bullish Order Block (OB ▲)", desc: "Last bearish candle before an upward institutional displacement. Blue box. Price returning here = institutional buy zone." },
    { swatch: "#ef4444", swatchStyle: {}, label: "Bearish Order Block (OB ▼)", desc: "Last bullish candle before a downward institutional displacement. Red box. Price returning here = institutional sell zone." },
    { swatch: "#5eead4", swatchStyle: { opacity: 0.7 }, label: "Bullish FVG (teal)", desc: "Three-candle upward imbalance — price moved too fast to fill both sides. Acts as support on retrace." },
    { swatch: "#ef4444", swatchStyle: { opacity: 0.5 }, label: "Bearish FVG (red)", desc: "Three-candle downward imbalance. Acts as resistance on retrace." },
    { icon: "⚡", iconColor: "#22c55e", bordColor: "#22c55e", label: "Green border — Inducement Swept", desc: "The liquidity trap in front of this OB has fired. Smart money collected stops. This OB is now actionable — highest conviction entry." },
    { icon: "⌛", iconColor: "#f59e0b", bordColor: "#f59e0b", label: "Amber border — Inducement Pending", desc: "An unswept EQH or EQL sits between price and this OB. The trap is set but hasn't fired yet. Watch this level — don't enter early." },
    { icon: "◑", iconColor: "#9ca3af", label: "Touched", desc: "A wick entered the OB zone on a first touch. The zone is still valid but has been tested once. Slightly reduced conviction." },
    { icon: "⚠", iconColor: "#f59e0b", label: "Degraded", desc: "A candle body closed past the 50% midpoint of the OB. Institutions partially failed to defend. Lower confidence — treat as support only." },
    { icon: "╌╌", iconColor: "#6c7889", label: "Dashed border — Candidate OB", desc: "Order block with no inducement detected in front of it. It may itself be the trap that smart money uses to collect retail orders. Exercise caution." },
    { bandColor: "#ef4444", bandOpacity: 0.5, label: "Premium Zone (red gradient)", desc: "Price is in the top half of the current dealing range. Smart money is positioned to sell here. Do NOT chase longs in premium." },
    { bandColor: "#22c55e", bandOpacity: 0.4, label: "Discount Zone (green gradient)", desc: "Price is in the bottom half of the dealing range. Smart money prefers to buy here. Long setups in discount have the highest probability." },
    { icon: "╌╌", iconColor: "#f59e0b", label: "OTE 62% / OTE 79% (amber dashed)", desc: "Optimal Trade Entry — the golden pocket. 61.8%–79% Fibonacci retracement into the dealing range. Look for OBs inside this band." },
    { icon: "─ ─", iconColor: "#9ca3af", label: "Equilibrium (dotted grey)", desc: "The 50% midpoint of the current dealing range. Neither premium nor discount — price can go either way here." },
    { heading: "STRUCTURE & LIQUIDITY" },
    { icon: "▼", iconColor: "#FF6D00", label: "Swing High — HH / LH (orange ▼)", desc: "Higher High or Lower High swing label. Orange triangles mark structural highs. HH = bullish structure continuation. LH = weakening structure." },
    { icon: "▲", iconColor: "#2979FF", label: "Swing Low — HL / LL (blue ▲)", desc: "Higher Low or Lower Low swing label. Blue triangles mark structural lows. HL = bullish structure continuation. LL = bearish structure." },
    { icon: "BOS", iconColor: "#00E676", label: "BOS ▲ — Break of Structure (bullish)", desc: "Price broke above the previous swing high, confirming a bullish trend continuation. Solid green tick mark." },
    { icon: "BOS", iconColor: "#FF1744", label: "BOS ▼ — Break of Structure (bearish)", desc: "Price broke below the previous swing low, confirming a bearish trend continuation. Solid red tick mark." },
    { icon: "CHoCH", iconColor: "#69F0AE", label: "CHoCH ▲ — Change of Character (bull)", desc: "First break of structure against the prevailing trend to the upside. Possible trend reversal — not confirmed until a second BOS." },
    { icon: "CHoCH", iconColor: "#FF5252", label: "CHoCH ▼ — Change of Character (bear)", desc: "First break of structure against the prevailing trend to the downside. Possible trend reversal — not confirmed until a second BOS." },
    { icon: "─ ─", iconColor: "#ef4444", label: "EQH — Equal Highs (red dotted)", desc: "Two or more equal swing highs create a pool of resting sell-stop orders above. Smart money may target this liquidity before reversing." },
    { icon: "─ ─", iconColor: "#5eead4", label: "EQL — Equal Lows (teal dotted)", desc: "Two or more equal swing lows create a pool of resting buy-stop orders below. Smart money may sweep this liquidity before reversing." },
    { heading: "HTF KEY LEVELS" },
    { icon: "───", iconColor: "#FFD600", label: "Yearly / Monthly (gold solid)", desc: "Annual or monthly open/close level from htf_levels.json. Highest timeframe confluence — treat as major support/resistance." },
    { icon: "───", iconColor: "#CE93D8", label: "Market Maker (purple solid)", desc: "Weekly or market-maker-derived level. Mid-tier HTF confluence. Often the location of large institutional order flow." },
    { icon: "╌╌╌", iconColor: "#26C6DA", label: "VWAP (teal dashed)", desc: "Volume Weighted Average Price level. Acts as a fair value magnet. Price above VWAP = bullish; below = bearish." },
    { icon: "╌╌╌", iconColor: "#90A4AE", label: "Elliott Wave (steel dashed)", desc: "Elliott Wave derived level from htf_levels.json. Lower confidence but useful for wave count confluence." },
  ];

  return (
    <div style={{ padding: "10px 14px 6px 14px" }}>
      <div style={{ background: "var(--bg-2)", border: "1px solid var(--line)", padding: "14px 20px" }}>
        <div className="mono" style={{ fontSize: 12, letterSpacing: "0.18em", color: "var(--ink)", marginBottom: 14 }}>
          SMC CHART KEY
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px 28px" }}>
          {rows.map((r, i) => r.heading ? (
            <div key={i} style={{ gridColumn: "1 / -1", borderTop: "1px solid var(--line)", paddingTop: 10, marginTop: 2 }}>
              <span className="mono" style={{ fontSize: 11, letterSpacing: "0.18em", color: "var(--ink-3)" }}>{r.heading}</span>
            </div>
          ) : (
            <div key={i} style={{ display: "flex", gap: 10, alignItems: "flex-start" }}>
              <div style={{ flexShrink: 0, width: 28, paddingTop: 2, textAlign: "center" }}>
                {r.swatch ? (
                  <div style={{
                    width: 18, height: 18, borderRadius: 2,
                    background: r.swatch, opacity: r.swatchStyle?.opacity ?? 1,
                    border: r.bordColor ? `2px solid ${r.bordColor}` : "none",
                    margin: "0 auto",
                  }} />
                ) : r.bandColor ? (
                  <div style={{
                    width: 28, height: 12, borderRadius: 2,
                    background: r.bandColor, opacity: r.bandOpacity ?? 0.4,
                    margin: "3px auto 0",
                  }} />
                ) : (
                  <span style={{ fontSize: r.icon.length > 2 ? 11 : 16, color: r.iconColor, lineHeight: 1, fontFamily: "'JetBrains Mono', monospace" }}>{r.icon}</span>
                )}
              </div>
              <div>
                <div className="mono" style={{ fontSize: 12, fontWeight: 700, color: r.iconColor || r.bordColor || "#c8d4e0", letterSpacing: "0.04em", marginBottom: 2 }}>
                  {r.label}
                </div>
                <div style={{ fontSize: 11, color: "var(--ink-2)", lineHeight: 1.5, fontFamily: "'JetBrains Mono', monospace" }}>
                  {r.desc}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function filterZonesForLens(zones, lensMode, currentPrice) {
  if (lensMode === 1) return zones; // ALL — active + ghost visible

  if (lensMode === 2) return []; // BATTLEFIELD — no zone boxes (BOS/CHoCH markers only)

  if (lensMode === 3) {
    // FOOTPRINTS: active FVGs + inducement-pending OBs; no ghost zones
    return zones.filter(z => {
      if (z.ghost) return false;
      if (z.type === "fvg") return true;
      if (z.type === "ob") return z.has_pending_inducement || !z.gate_passed;
      return false;
    });
  }

  if (lensMode === 4) {
    // SNIPER: gate-passed active OBs only; no ghost zones
    const obs = zones.filter(z => z.type === "ob" && z.gate_passed && !z.ghost);
    if (!currentPrice || !obs.length) return obs;
    let bestIdx = 0, bestDist = Infinity;
    obs.forEach((z, i) => {
      const dist = Math.abs(((z.top + z.bottom) / 2) - currentPrice);
      if (dist < bestDist) { bestDist = dist; bestIdx = i; }
    });
    return obs.map((z, i) => ({ ...z, opacity: i === bestIdx ? 1.0 : 0.40 }));
  }

  return zones;
}

function Chart({ symbol, tf, height = 360, accent = "var(--cyan)", smcData = null, smcLoading = false, ghData = null, ghLoading = false, xabcdData = null, xabcdLoading = false, showSMC = true, setShowSMC = () => {}, showGH = true, setShowGH = () => {}, showXABCD = true, setShowXABCD = () => {}, showEMA = true, setShowEMA = () => {}, showVWAP = true, setShowVWAP = () => {}, showStoch = false, setShowStoch = () => {}, lensMode = 1, currentPrice = null, activeOnly = false, onHover = null }) {
  const containerRef  = useRef(null);
  const chartRef      = useRef(null);
  const seriesRef     = useRef(null);
  const primitiveRef      = useRef(null);
  const pdPrimRef         = useRef(null);
  const smcMarkersPrimRef = useRef(null);
  const xabcdPrimRef      = useRef(null);
  const ghPrimRef         = useRef(null);
  const htfLinesRef       = useRef([]);
  const ghLinesRef        = useRef([]);
  const eqlLinesRef       = useRef([]);
  const ema50SeriesRef  = useRef(null);
  const ema200SeriesRef = useRef(null);
  const vwapSeriesRef   = useRef(null);
  const stochKSeriesRef     = useRef(null);
  const stochDSeriesRef     = useRef(null);
  const stochContainerRef   = useRef(null);
  const stochChartRef       = useRef(null);
  const syncingRef          = useRef(false);
  const oteLinesRef       = useRef([]);
  const smcDataRef        = useRef(null);
  const htfLevelDataRef   = useRef([]);
  const eqlDataRef        = useRef([]);
  const lensModeRef       = useRef(lensMode);
  const currentPriceRef   = useRef(currentPrice);
  const lastCandleTimeRef = useRef(null);
  const activeOnlyRef     = useRef(activeOnly);
  const zonesForHoverRef  = useRef([]);
  const swingsForHoverRef = useRef([]);
  const eventsForHoverRef = useRef([]);
  const [dataSource,  setDataSource]  = useState("…");
  const [diagMsg,     setDiagMsg]     = useState("");
  const [opacityMult, setOpacityMult] = useState(1.0);
  const [indicatorData, setIndicatorData] = useState(null);
  const [stochHeight, setStochHeight] = useState(100);
  const stochDragRef = useRef({ dragging: false, startY: 0, startH: 0 });

  const ACCENT_MAP = {
    "--buy":     "#5eead4",
    "--sell":    "#ef4444",
    "--wait":    "#f59e0b",
    "--cyan":    "#38bdf8",
    "--magenta": "#c084fc",
  };
  function resolveColor(cssVar) {
    if (!cssVar.startsWith("var(")) return cssVar;
    return ACCENT_MAP[cssVar.slice(4, -1)] || "#38bdf8";
  }

  function htfLineStyle(lvl) {
    const t = (lvl.level_type || "other");
    if (t === "yearly_monthly") return {
      color: "#FFD60099", lineWidth: 2,
      lineStyle: LightweightCharts.LineStyle.Solid
    };
    if (t === "market_maker")   return {
      color: "#CE93D888", lineWidth: 1.5,
      lineStyle: LightweightCharts.LineStyle.Solid
    };
    if (t === "vwap")           return {
      color: "#26C6DA88", lineWidth: 1,
      lineStyle: LightweightCharts.LineStyle.Dashed
    };
    if (t === "elliott_wave")   return {
      color: "#90A4AE88", lineWidth: 1,
      lineStyle: LightweightCharts.LineStyle.Dashed
    };
    return { color: "#90A4AE55", lineWidth: 1, lineStyle: LightweightCharts.LineStyle.Dotted };
  }

  function findHoveredElement(mouseX, mouseY) {
    const chart  = chartRef.current;
    const series = seriesRef.current;
    if (!chart || !series || !smcDataRef.current) return null;

    const price = series.coordinateToPrice(mouseY);
    if (price === null || price === undefined) return null;

    /* Check OBs and FVGs */
    const rawZones = zonesForHoverRef.current;
    let visZones = filterZonesForLens(rawZones, lensModeRef.current, currentPriceRef.current);
    if (activeOnlyRef.current) visZones = visZones.filter(z => !z.ghost);
    for (const z of visZones) {
      if (price >= z.bottom && price <= z.top) {
        return { elementType: z.type === "fvg" ? "fvg" : "ob", ...z };
      }
    }

    /* Check HTF lines (within 0.3% of price) */
    const htfTol = Math.abs(price) * 0.003;
    for (const lvl of htfLevelDataRef.current) {
      if (Math.abs((lvl.price || 0) - price) < htfTol) {
        return { elementType: "htf", ...lvl };
      }
    }

    /* Check EQH/EQL (within 0.2%) */
    const eqlTol = Math.abs(price) * 0.002;
    for (const pool of eqlDataRef.current) {
      if (Math.abs((pool.level || 0) - price) < eqlTol) {
        return { elementType: pool.kind === "eqh" ? "eqh" : "eql", price: pool.level, kind: pool.kind };
      }
    }

    /* Check swing markers (within 0.5%) */
    const swings = swingsForHoverRef.current;
    const swingTol = Math.abs(price) * 0.005;
    for (const sw of swings) {
      if (Math.abs(sw.price - price) < swingTol) {
        return { elementType: "swing", ...sw };
      }
    }

    /* Check BOS/CHoCH structure events (within 0.3%) */
    const bosTol = Math.abs(price) * 0.003;
    for (const ev of eventsForHoverRef.current) {
      if (Math.abs((ev.price || 0) - price) < bosTol) {
        const isBOS  = (ev.event_type || "").startsWith("BOS");
        const isBull = (ev.event_type || "").includes("BULL");
        return {
          elementType: isBOS ? "bos" : "choch",
          event_type:  ev.event_type,
          price:       ev.price,
          timestamp:   ev.timestamp,
          isBull,
          isBOS,
        };
      }
    }

    return null;
  }

  lensModeRef.current     = lensMode;
  currentPriceRef.current = currentPrice;
  activeOnlyRef.current   = activeOnly;

  /* create chart once on mount */
  useEffect(() => {
    if (!containerRef.current) { setDiagMsg("no container"); return; }
    if (!window.LightweightCharts) { setDiagMsg("LW Charts not loaded"); return; }
    if (!window.API)              { setDiagMsg("api.js not loaded");    return; }
    const accentHex = resolveColor(accent);

    const chart = LightweightCharts.createChart(containerRef.current, {
      width:  containerRef.current.clientWidth,
      height: height,
      layout: {
        background: { color: "transparent" },
        textColor:  "#6c7889",
        fontFamily: "'JetBrains Mono', monospace",
        fontSize:   11,
      },
      grid: {
        vertLines: { color: "#1c2433", style: LightweightCharts.LineStyle.Dashed },
        horzLines: { color: "#1c2433", style: LightweightCharts.LineStyle.Dashed },
      },
      crosshair: {
        mode: LightweightCharts.CrosshairMode.Normal,
        vertLine: { color: accentHex + "60", labelBackgroundColor: "#0d1118" },
        horzLine: { color: accentHex + "60", labelBackgroundColor: "#0d1118" },
      },
      rightPriceScale: { borderColor: "#1c2433", textColor: "#6c7889" },
      timeScale: {
        borderColor:    "#1c2433",
        timeVisible:    true,
        secondsVisible: false,
      },
      handleScroll: true,
      handleScale:  true,
    });

    const series = chart.addCandlestickSeries({
      upColor:         "#5eead4",
      downColor:       "#ef4444",
      borderUpColor:   "#5eead4",
      borderDownColor: "#ef4444",
      wickUpColor:     "#5eead4",
      wickDownColor:   "#ef4444",
    });

    chartRef.current  = chart;
    seriesRef.current = series;

    let cachedRect = null;

    const ro = new ResizeObserver(() => {
      if (containerRef.current && chartRef.current)
        chartRef.current.applyOptions({ width: containerRef.current.clientWidth });
      cachedRect = null;
    });
    ro.observe(containerRef.current);

    /* hover hit-testing */
    const container = containerRef.current;
    function onMouseMove(e) {
      if (!onHover) return;
      if (!cachedRect) cachedRect = container.getBoundingClientRect();
      const x = e.clientX - cachedRect.left;
      const y = e.clientY - cachedRect.top;
      const el = findHoveredElement(x, y);
      onHover(el);
    }
    function onMouseLeave() {
      if (onHover) onHover(null);
    }
    function onScroll() { cachedRect = null; }
    container.addEventListener("mousemove", onMouseMove);
    container.addEventListener("mouseleave", onMouseLeave);
    window.addEventListener("scroll", onScroll, true);

    return () => {
      container.removeEventListener("mousemove", onMouseMove);
      container.removeEventListener("mouseleave", onMouseLeave);
      window.removeEventListener("scroll", onScroll, true);
      ro.disconnect();
      if (primitiveRef.current) {
        try { series.detachPrimitive(primitiveRef.current); } catch {}
        primitiveRef.current = null;
      }
      if (pdPrimRef.current) {
        try { series.detachPrimitive(pdPrimRef.current); } catch {}
        pdPrimRef.current = null;
      }
      if (smcMarkersPrimRef.current) {
        try { series.detachPrimitive(smcMarkersPrimRef.current); } catch {}
        smcMarkersPrimRef.current = null;
      }
      if (xabcdPrimRef.current) {
        try { series.detachPrimitive(xabcdPrimRef.current); } catch {}
        xabcdPrimRef.current = null;
      }
      htfLinesRef.current = [];
      ghLinesRef.current  = [];
      eqlLinesRef.current = [];
      oteLinesRef.current = [];
      ema50SeriesRef.current  = null;
      ema200SeriesRef.current = null;
      vwapSeriesRef.current   = null;
      stochKSeriesRef.current = null;
      stochDSeriesRef.current = null;
      if (stochChartRef.current) { stochChartRef.current.remove(); stochChartRef.current = null; }
      chart.remove();
      chartRef.current  = null;
      seriesRef.current = null;
    };
  }, [height]);

  /* reload data when symbol or tf changes */
  useEffect(() => {
    if (!seriesRef.current) return;
    let cancelled = false;
    setDataSource("…");

    setIndicatorData(null);
    window.API.fetchOHLCV(symbol, tf).then(({ candles, indicators, source }) => {
      if (cancelled || !seriesRef.current || !candles.length) return;
      seriesRef.current.setData(candles);
      lastCandleTimeRef.current = candles[candles.length - 1].time; // Unix int seconds
      chartRef.current.timeScale().fitContent();
      setDataSource(source);
      setIndicatorData(indicators || null);
    });

    return () => { cancelled = true; };
  }, [symbol, tf]);

  /* SMC overlay — attach/detach zone primitive when data or toggle changes */
  useEffect(() => {
    const series = seriesRef.current;
    if (!series) return;

    smcDataRef.current      = smcData;
    htfLevelDataRef.current = (smcData?.flat_levels || []);
    eqlDataRef.current      = (smcData?.ltf_smc?.liquidity_pools || []).filter(p => !p.swept && p.level);
    zonesForHoverRef.current  = smcToZones(smcData || {});
    swingsForHoverRef.current = smcToMarkers(smcData || {}).swings;
    eventsForHoverRef.current = smcToMarkers(smcData || {}).events;

    /* tear down whatever was attached before */
    if (primitiveRef.current) {
      try { series.detachPrimitive(primitiveRef.current); } catch {}
      primitiveRef.current = null;
    }
    if (pdPrimRef.current) {
      try { series.detachPrimitive(pdPrimRef.current); } catch {}
      pdPrimRef.current = null;
    }
    if (smcMarkersPrimRef.current) {
      try { series.detachPrimitive(smcMarkersPrimRef.current); } catch {}
      smcMarkersPrimRef.current = null;
    }
    htfLinesRef.current.forEach(l => { try { series.removePriceLine(l); } catch {} });
    htfLinesRef.current = [];
    eqlLinesRef.current.forEach(l => { try { series.removePriceLine(l); } catch {} });
    eqlLinesRef.current = [];
    oteLinesRef.current.forEach(l => { try { series.removePriceLine(l); } catch {} });
    oteLinesRef.current = [];

    if (!showSMC || !smcData || smcData.error) return;

    /* per-lens layer visibility flags */
    const showPD      = lensMode === 1 || lensMode === 2;
    const showOTE     = lensMode === 1 || lensMode === 2 || lensMode === 4;
    const showHTF     = lensMode === 1 || lensMode === 2;
    const showMarkers = lensMode === 1 || lensMode === 2;
    const showEQL     = true; // all lenses show EQL — spec requires it for BATTLEFIELD and SNIPER

    /* PD zone background — premium/discount/OTE */
    if (showPD) {
      const pdZone = smcToPDZone(smcData);
      if (pdZone) {
        const pdPrim = new SMCPDPrimitive(pdZone);
        try { series.attachPrimitive(pdPrim); pdPrimRef.current = pdPrim; } catch {}
      }
    }

    const rawZones = smcToZones(smcData);
    const zones = filterZonesForLens(rawZones, lensMode, currentPrice).map(z => ({ ...z, opacity: z.opacity * opacityMult }));
    if (zones.length) {
      const prim = new SMCZonePrimitive(
        zones,
        chartRef.current,
        lensMode,
        currentPrice,
        lastCandleTimeRef.current,  // 5th param: Unix int for active zone right edge
        activeOnly,                  // 6th param: override to hide ghost zones
      );
      try {
        series.attachPrimitive(prim);
        primitiveRef.current = prim;
      } catch (e) {
        console.warn("[SMC] primitive attach failed:", e);
      }
    }

    /* HTF key levels — 4 colors by level_type */
    if (showHTF) {
      const newLines = [];
      for (const lvl of (smcData.flat_levels || []).slice(0, 25)) {
        if (!lvl.price || isNaN(lvl.price)) continue;
        const style = htfLineStyle(lvl);
        try {
          newLines.push(series.createPriceLine({
            price:            lvl.price,
            color:            style.color,
            lineWidth:        style.lineWidth,
            lineStyle:        style.lineStyle,
            axisLabelVisible: false,
            title:            "",
          }));
        } catch {}
      }
      htfLinesRef.current = newLines;
    }

    /* SMC markers: swing labels + BOS/CHoCH */
    if (showMarkers && chartRef.current) {
      const { swings, events } = smcToMarkers(smcData);
      if (swings.length || events.length) {
        const mkPrim = new SMCMarkersPrimitive(swings, events, chartRef.current, lensMode, currentPrice);
        try { series.attachPrimitive(mkPrim); smcMarkersPrimRef.current = mkPrim; } catch {}
      }
    }

    /* OTE golden pocket — two labeled price lines */
    if (showOTE) {
      const pd = smcData.ltf_smc?.pd_zones;
      if (pd?.ote_top && pd?.ote_bottom) {
        const oteLines = [];
        try {
          oteLines.push(series.createPriceLine({
            price:            pd.ote_top,
            color:            "#f59e0b99",
            lineWidth:        1,
            lineStyle:        LightweightCharts.LineStyle.Dashed,
            axisLabelVisible: true,
            title:            "OTE 62%",
          }));
          oteLines.push(series.createPriceLine({
            price:            pd.ote_bottom,
            color:            "#f59e0b99",
            lineWidth:        1,
            lineStyle:        LightweightCharts.LineStyle.Dashed,
            axisLabelVisible: true,
            title:            "OTE 79%",
          }));
        } catch {}
        oteLinesRef.current = oteLines;
      }
    }

    /* EQH/EQL unswept pools as dotted price lines */
    if (showEQL) {
      const newEqlLines = [];
      for (const pool of (smcData.ltf_smc?.liquidity_pools || [])) {
        if (pool.swept || !pool.level || isNaN(pool.level)) continue;
        try {
          newEqlLines.push(series.createPriceLine({
            price:            pool.level,
            color:            pool.kind === "eqh" ? "#FF174455" : "#00E67655",
            lineWidth:        1.5,
            lineStyle:        LightweightCharts.LineStyle.Dashed,
            axisLabelVisible: false,
            title:            "",
          }));
        } catch {}
      }
      eqlLinesRef.current = newEqlLines;
    }

    return () => {
      if (primitiveRef.current && seriesRef.current) {
        try { seriesRef.current.detachPrimitive(primitiveRef.current); } catch {}
        primitiveRef.current = null;
      }
      if (pdPrimRef.current && seriesRef.current) {
        try { seriesRef.current.detachPrimitive(pdPrimRef.current); } catch {}
        pdPrimRef.current = null;
      }
      if (smcMarkersPrimRef.current && seriesRef.current) {
        try { seriesRef.current.detachPrimitive(smcMarkersPrimRef.current); } catch {}
        smcMarkersPrimRef.current = null;
      }
      htfLinesRef.current.forEach(l => {
        if (seriesRef.current) { try { seriesRef.current.removePriceLine(l); } catch {} }
      });
      htfLinesRef.current = [];
      eqlLinesRef.current.forEach(l => {
        if (seriesRef.current) { try { seriesRef.current.removePriceLine(l); } catch {} }
      });
      eqlLinesRef.current = [];
      oteLinesRef.current.forEach(l => {
        if (seriesRef.current) { try { seriesRef.current.removePriceLine(l); } catch {} }
      });
      oteLinesRef.current = [];
    };
  }, [smcData, showSMC, opacityMult, lensMode, currentPrice, activeOnly]);

  /* GH overlay — arc primitives drawn on canvas */
  useEffect(() => {
    const series = seriesRef.current;
    const chart  = chartRef.current;
    if (!series || !chart) return;

    /* clear any legacy price lines */
    ghLinesRef.current.forEach(l => { try { series.removePriceLine(l); } catch {} });
    ghLinesRef.current = [];

    /* detach existing arc primitive */
    if (ghPrimRef.current) {
      try { series.detachPrimitive(ghPrimRef.current); } catch {}
      ghPrimRef.current = null;
    }

    if (!showGH || !ghData || ghData.error) return;

    const circles = ghData.gh_circles || [];
    const scMacro = ghData.sc_macro   || 0;
    if (!circles.length || !scMacro) return;

    const prim = new GHArcPrimitive(circles, scMacro, chart);
    try {
      series.attachPrimitive(prim);
      ghPrimRef.current = prim;
    } catch (e) {
      console.warn("[GH Arc] primitive attach failed:", e);
    }

    return () => {
      if (ghPrimRef.current && seriesRef.current) {
        try { seriesRef.current.detachPrimitive(ghPrimRef.current); } catch {}
        ghPrimRef.current = null;
      }
    };
  }, [ghData, showGH]);

  /* XABCD overlay — attach/detach pattern primitive when data or toggle changes */
  useEffect(() => {
    const series = seriesRef.current;
    const chart  = chartRef.current;
    if (!series || !chart) return;

    if (xabcdPrimRef.current) {
      try { series.detachPrimitive(xabcdPrimRef.current); } catch {}
      xabcdPrimRef.current = null;
    }

    if (!showXABCD || !xabcdData || xabcdData.error) return;

    const patterns = xabcdToPatterns(xabcdData);
    if (!patterns.length) return;

    const prim = new XABCDPrimitive(patterns, chart);
    try {
      series.attachPrimitive(prim);
      xabcdPrimRef.current = prim;
    } catch (e) {
      console.warn("[XABCD] primitive attach failed:", e);
    }

    return () => {
      if (xabcdPrimRef.current && seriesRef.current) {
        try { seriesRef.current.detachPrimitive(xabcdPrimRef.current); } catch {}
        xabcdPrimRef.current = null;
      }
    };
  }, [xabcdData, showXABCD]);

  /* EMA 50/200 overlays — create/destroy on data or toggle change */
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;
    if (ema50SeriesRef.current)  { try { chart.removeSeries(ema50SeriesRef.current);  } catch(e){} ema50SeriesRef.current  = null; }
    if (ema200SeriesRef.current) { try { chart.removeSeries(ema200SeriesRef.current); } catch(e){} ema200SeriesRef.current = null; }
    if (!showEMA || !indicatorData?.ema50?.length) return;
    const s50 = chart.addLineSeries({ color: '#42A5F5', lineWidth: 1.5, priceLineVisible: false, lastValueVisible: false });
    s50.setData(indicatorData.ema50);
    ema50SeriesRef.current = s50;
    const s200 = chart.addLineSeries({ color: '#EF5350', lineWidth: 1.5, priceLineVisible: false, lastValueVisible: false });
    s200.setData(indicatorData.ema200);
    ema200SeriesRef.current = s200;
  }, [indicatorData, showEMA]);

  /* VWAP overlay — create/destroy on data or toggle change */
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;
    if (vwapSeriesRef.current) { try { chart.removeSeries(vwapSeriesRef.current); } catch(e){} vwapSeriesRef.current = null; }
    if (!showVWAP || !indicatorData?.vwap?.length) return;
    const s = chart.addLineSeries({ color: '#AB47BC', lineWidth: 1.5, lineStyle: 2, priceLineVisible: false, lastValueVisible: false });
    s.setData(indicatorData.vwap);
    vwapSeriesRef.current = s;
  }, [indicatorData, showVWAP]);

  /* drag-to-resize Stoch pane */
  useEffect(() => {
    function onMouseMove(e) {
      if (!stochDragRef.current.dragging) return;
      const dy = stochDragRef.current.startY - e.clientY;
      const newH = Math.max(60, Math.min(300, stochDragRef.current.startH + dy));
      setStochHeight(newH);
    }
    function onMouseUp() { stochDragRef.current.dragging = false; }
    window.addEventListener("mousemove", onMouseMove);
    window.addEventListener("mouseup", onMouseUp);
    return () => {
      window.removeEventListener("mousemove", onMouseMove);
      window.removeEventListener("mouseup", onMouseUp);
    };
  }, []);

  /* sync main chart height when stoch pane appears/resizes */
  useEffect(() => {
    if (!chartRef.current) return;
    const HANDLE = 6;
    const mainH = (showStoch && indicatorData?.stochK?.length)
      ? Math.max(80, height - stochHeight - HANDLE)
      : height;
    chartRef.current.applyOptions({ height: mainH });
  }, [showStoch, stochHeight, indicatorData, height]);

  /* Stoch RSI sub-pane — separate LW Charts instance, synced to main chart */
  useEffect(() => {
    const container = stochContainerRef.current;
    if (!container) return;

    // --- teardown any existing stoch chart ---
    stochKSeriesRef.current = null;
    stochDSeriesRef.current = null;
    if (stochChartRef.current) { stochChartRef.current.remove(); stochChartRef.current = null; }

    if (!showStoch || !indicatorData?.stochK?.length || !chartRef.current) return;

    // --- create chart ---
    const sc = window.LightweightCharts.createChart(container, {
      autoSize: true,
      layout: { background: { color: '#06080c' }, textColor: '#4a5364' },
      grid: { vertLines: { color: '#0e1420' }, horzLines: { color: '#0e1420' } },
      rightPriceScale: { visible: true, borderVisible: false, scaleMargins: { top: 0.05, bottom: 0.05 } },
      timeScale: { visible: false },
      crosshair: { mode: window.LightweightCharts.CrosshairMode.Normal },
      handleScale: { mouseWheel: false, pinch: false, axisPressedMouseMove: false },
    });
    stochChartRef.current = sc;

    // --- %K line (pinned 0-100 via autoscaleInfoProvider) ---
    const sK = sc.addLineSeries({
      color: '#42A5F5', lineWidth: 1.5,
      priceLineVisible: false, lastValueVisible: false,
      autoscaleInfoProvider: () => ({ priceRange: { minValue: 0, maxValue: 100 } }),
    });
    sK.setData(indicatorData.stochK);
    stochKSeriesRef.current = sK;

    // --- %D line (dashed) ---
    const sD = sc.addLineSeries({
      color: '#EF5350', lineWidth: 1.5, lineStyle: 2,
      priceLineVisible: false, lastValueVisible: false,
    });
    sD.setData(indicatorData.stochD);
    stochDSeriesRef.current = sD;

    // --- 20 / 80 reference lines ---
    sK.createPriceLine({ price: 80, color: '#3a4560', lineWidth: 1, lineStyle: 2, axisLabelVisible: true, title: '' });
    sK.createPriceLine({ price: 20, color: '#3a4560', lineWidth: 1, lineStyle: 2, axisLabelVisible: true, title: '' });

    // --- time-scale sync (bidirectional) ---
    const handleMainRange = range => {
      if (syncingRef.current || !range) return;
      syncingRef.current = true;
      sc.timeScale().setVisibleLogicalRange(range);
      syncingRef.current = false;
    };
    chartRef.current.timeScale().subscribeVisibleLogicalRangeChange(handleMainRange);

    const handleStochRange = range => {
      if (syncingRef.current || !range) return;
      syncingRef.current = true;
      chartRef.current?.timeScale().setVisibleLogicalRange(range);
      syncingRef.current = false;
    };
    sc.timeScale().subscribeVisibleLogicalRangeChange(handleStochRange);

    // --- crosshair sync (main → Stoch, vertical line only) ---
    const handleCrosshair = param => {
      if (param.time) {
        sc.setCrosshairPosition(50, param.time, sK);
      } else {
        sc.clearCrosshairPosition();
      }
    };
    chartRef.current.subscribeCrosshairMove(handleCrosshair);

    // --- initial range sync so Stoch starts aligned ---
    const currentRange = chartRef.current.timeScale().getVisibleLogicalRange();
    if (currentRange) sc.timeScale().setVisibleLogicalRange(currentRange);

    return () => {
      chartRef.current?.timeScale().unsubscribeVisibleLogicalRangeChange(handleMainRange);
      sc.timeScale().unsubscribeVisibleLogicalRangeChange(handleStochRange);
      chartRef.current?.unsubscribeCrosshairMove(handleCrosshair);
      stochKSeriesRef.current = null;
      stochDSeriesRef.current = null;
      if (stochChartRef.current) { stochChartRef.current.remove(); stochChartRef.current = null; }
    };
  }, [indicatorData, showStoch]);

  /* derive badge text */
  const smcBadge = smcLoading ? "SMC ◇"
    : smcData?.error            ? "SMC ⚠"
    : smcData                   ? (showSMC ? "SMC ◆" : "SMC ○")
    : null;

  const ghBadge = ghLoading ? "GH ◇"
    : ghData?.error ? "GH ⚠"
    : ghData        ? (showGH ? "GH ◆" : "GH ○")
    : null;

  const xabcdBadge = xabcdLoading ? "XABCD ◇"
    : xabcdData?.error ? "XABCD ⚠"
    : xabcdData        ? (showXABCD ? "XABCD ◆" : "XABCD ○")
    : null;

  const stochVisible = showStoch && !!(indicatorData?.stochK?.length);
  const HANDLE_H = 6;
  const mainChartH = stochVisible ? Math.max(80, height - stochHeight - HANDLE_H) : height;

  return (
    <div style={{ display: "flex", flexDirection: "column", width: "100%", height }}>
    <div style={{ position: "relative", width: "100%", height: mainChartH }}>
      <div ref={containerRef} style={{ width: "100%", height: "100%" }} />
      {/* candle data badge */}
      <div className="mono" style={{
        position: "absolute", top: 6, left: 8,
        fontSize: 12, letterSpacing: "0.16em", pointerEvents: "none",
        background: "rgba(6,8,12,0.7)", padding: "2px 6px",
        color: dataSource === "live" ? "#5eead4" : dataSource === "mock" ? "#f59e0b" : "#4a5364",
      }}>
        {diagMsg
          ? "⚠ " + diagMsg
          : dataSource === "live" ? "◆ LIVE"
          : dataSource === "mock" ? "◇ MOCK"
          : "◇ LOADING…"}
      </div>
      {/* SMC toggle */}
      {smcBadge && (
        <button
          onClick={() => !smcLoading && setShowSMC(v => !v)}
          className="mono"
          style={{
            position: "absolute", top: 24, left: 8, zIndex: 10,
            fontSize: 12, letterSpacing: "0.14em",
            background: showSMC && smcData && !smcData.error ? "rgba(56,189,248,0.15)" : "rgba(6,8,12,0.7)",
            border: `1px solid ${showSMC && smcData && !smcData.error ? "#38bdf8" : "#2a3346"}`,
            color: smcLoading ? "#f59e0b"
              : smcData?.error ? "#ef4444"
              : showSMC       ? "#38bdf8" : "#4a5364",
            padding: "2px 7px",
            cursor: smcLoading ? "default" : "pointer",
          }}>
          {smcBadge}
        </button>
      )}
      {/* GH toggle — stacked below SMC badge */}
      {ghBadge && (
        <button
          onClick={() => !ghLoading && setShowGH(v => !v)}
          className="mono"
          style={{
            position: "absolute", top: 42, left: 8, zIndex: 10,
            fontSize: 12, letterSpacing: "0.14em",
            background: showGH && ghData && !ghData.error ? "rgba(192,132,252,0.15)" : "rgba(6,8,12,0.7)",
            border: `1px solid ${showGH && ghData && !ghData.error ? "#c084fc" : "#2a3346"}`,
            color: ghLoading ? "#f59e0b"
              : ghData?.error ? "#ef4444"
              : showGH        ? "#c084fc" : "#4a5364",
            padding: "2px 7px",
            cursor: ghLoading ? "default" : "pointer",
          }}>
          {ghBadge}
        </button>
      )}
      {/* XABCD toggle — stacked below GH badge */}
      {xabcdBadge && (
        <button
          onClick={() => !xabcdLoading && setShowXABCD(v => !v)}
          className="mono"
          style={{
            position: "absolute", top: 60, left: 8, zIndex: 10,
            fontSize: 12, letterSpacing: "0.14em",
            background: showXABCD && xabcdData && !xabcdData.error ? "rgba(245,158,11,0.15)" : "rgba(6,8,12,0.7)",
            border: `1px solid ${showXABCD && xabcdData && !xabcdData.error ? "#f59e0b" : "#2a3346"}`,
            color: xabcdLoading ? "#f59e0b"
              : xabcdData?.error ? "#ef4444"
              : showXABCD        ? "#f59e0b" : "#4a5364",
            padding: "2px 7px",
            cursor: xabcdLoading ? "default" : "pointer",
          }}>
          {xabcdBadge}
        </button>
      )}
      {/* Opacity cycle — below XABCD, only when SMC is active */}
      {showSMC && smcData && !smcData.error && (
        <button
          onClick={() => setOpacityMult(m => m >= 1.0 ? 0.4 : m < 0.55 ? 0.7 : 1.0)}
          className="mono"
          style={{
            position: "absolute", top: 78, left: 8, zIndex: 10,
            fontSize: 12, letterSpacing: "0.14em",
            background: "rgba(6,8,12,0.7)",
            border: "1px solid #2a3346",
            color: opacityMult >= 1.0 ? "#38bdf8" : opacityMult >= 0.65 ? "#6c7889" : "#4a5364",
            padding: "2px 7px",
            cursor: "pointer",
          }}>
          {opacityMult >= 1.0 ? "◉ FULL" : opacityMult >= 0.65 ? "◎ SOFT" : "◌ FAINT"}
        </button>
      )}
      {/* EMA toggle — right side */}
      {indicatorData && (
        <button
          onClick={() => setShowEMA(v => !v)}
          className="mono"
          style={{
            position: "absolute", top: 24, right: 8, zIndex: 10,
            fontSize: 12, letterSpacing: "0.14em",
            background: showEMA ? "rgba(66,165,245,0.15)" : "rgba(6,8,12,0.7)",
            border: `1px solid ${showEMA ? "#42A5F5" : "#2a3346"}`,
            color: showEMA ? "#42A5F5" : "#4a5364",
            padding: "2px 7px", cursor: "pointer",
          }}>
          {showEMA ? "EMA ◆" : "EMA ○"}
        </button>
      )}
      {/* VWAP toggle — right side */}
      {indicatorData && (
        <button
          onClick={() => setShowVWAP(v => !v)}
          className="mono"
          style={{
            position: "absolute", top: 42, right: 8, zIndex: 10,
            fontSize: 12, letterSpacing: "0.14em",
            background: showVWAP ? "rgba(171,71,188,0.15)" : "rgba(6,8,12,0.7)",
            border: `1px solid ${showVWAP ? "#AB47BC" : "#2a3346"}`,
            color: showVWAP ? "#AB47BC" : "#4a5364",
            padding: "2px 7px", cursor: "pointer",
          }}>
          {showVWAP ? "VWAP ◆" : "VWAP ○"}
        </button>
      )}
      {/* STOCH toggle — right side */}
      {indicatorData && (
        <button
          onClick={() => setShowStoch(v => !v)}
          className="mono"
          style={{
            position: "absolute", top: 60, right: 8, zIndex: 10,
            fontSize: 12, letterSpacing: "0.14em",
            background: showStoch ? "rgba(239,83,80,0.15)" : "rgba(6,8,12,0.7)",
            border: `1px solid ${showStoch ? "#EF5350" : "#2a3346"}`,
            color: showStoch ? "#EF5350" : "#4a5364",
            padding: "2px 7px", cursor: "pointer",
          }}>
          {showStoch ? "STOCH ◆" : "STOCH ○"}
        </button>
      )}
    </div>
    {stochVisible && (
      <>
        <div
          onMouseDown={e => {
            stochDragRef.current = { dragging: true, startY: e.clientY, startH: stochHeight };
            e.preventDefault();
          }}
          style={{
            height: HANDLE_H, cursor: "row-resize", flexShrink: 0,
            background: "var(--bg-2)", borderTop: "1px solid var(--line)",
            display: "flex", alignItems: "center", justifyContent: "center",
          }}
        >
          <div style={{ width: 28, height: 2, background: "#2a3346", borderRadius: 1 }} />
        </div>
        <div
          ref={stochContainerRef}
          style={{ width: "100%", height: stochHeight, flexShrink: 0, background: "#06080c" }}
        />
      </>
    )}
    {!stochVisible && <div ref={stochContainerRef} style={{ display: "none" }} />}
    </div>
  );
}

/* ── AlertCard — full-width prominent alert ─────────────────── */
function AlertCard({ level, section, text }) {
  const cfg = {
    danger: { bg: "rgba(239,68,68,0.10)",   border: "#ef4444", icon: "✕", label: "DANGER"  },
    warn:   { bg: "rgba(245,158,11,0.10)",  border: "#f59e0b", icon: "⚠", label: "WARNING" },
    info:   { bg: "rgba(56,189,248,0.10)",  border: "#38bdf8", icon: "◆", label: "NOTICE"  },
    ok:     { bg: "rgba(94,234,212,0.09)",  border: "#5eead4", icon: "✓", label: "CLEAR"   },
  };
  const c = cfg[level] || cfg.info;
  return (
    <div style={{
      display: "flex", alignItems: "stretch",
      background: c.bg,
      borderLeft: `3px solid ${c.border}`,
      border: `1px solid ${c.border}28`,
    }}>
      <div style={{
        padding: "11px 14px", flex: "0 0 86px",
        borderRight: `1px solid ${c.border}22`,
        display: "flex", flexDirection: "column", gap: 3, justifyContent: "center",
      }}>
        <span className="mono" style={{ fontSize: 12, color: c.border, letterSpacing: "0.18em", opacity: 0.75 }}>
          {section}
        </span>
        <span className="mono" style={{ fontSize: 13, color: c.border, fontWeight: 700, letterSpacing: "0.08em" }}>
          {c.icon} {c.label}
        </span>
      </div>
      <div style={{ padding: "11px 16px", display: "flex", alignItems: "center" }}>
        <span style={{ fontSize: 13, color: "#c8d4e0", lineHeight: 1.6, fontFamily: "'JetBrains Mono', monospace", letterSpacing: "0.02em" }}>
          {text}
        </span>
      </div>
    </div>
  );
}

/* ── AlertStrip — renders a list of AlertCards ──────────────── */
function AlertStrip({ warnings }) {
  if (!warnings || !warnings.length) return null;
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 3 }}>
      {warnings.map((w, i) => (
        <AlertCard key={i} level={w.level} section={w.section} text={w.text} />
      ))}
    </div>
  );
}

/* ── RotationSection — sector rotation engine panel ─────────── */
function RotationSection({ data, loading }) {
  const sty = {
    wrap:    { marginBottom: 16 },
    header:  { fontSize: 10, color: "var(--ink-4)", letterSpacing: 1, marginBottom: 8, textTransform: "uppercase" },
    summary: { fontSize: 12, color: "var(--ink)", marginBottom: 12, lineHeight: 1.6 },
    muted:   { fontSize: 12, color: "var(--ink-4)", padding: "12px 0" },
    table:   { width: "100%", borderCollapse: "collapse", fontSize: 11 },
    th:      { textAlign: "left",  padding: "4px 6px", fontWeight: 400, color: "var(--ink-4)",
               borderBottom: "1px solid var(--bg-3)" },
    thR:     { textAlign: "right", padding: "4px 6px", fontWeight: 400, color: "var(--ink-4)",
               borderBottom: "1px solid var(--bg-3)" },
    td:      { padding: "4px 6px" },
    tdR:     { padding: "4px 6px", textAlign: "right" },
    alert:   { marginTop: 12, border: "1px solid var(--amber)", borderRadius: 4,
               padding: "10px 12px", background: "rgba(255,160,0,0.05)" },
    alertHd: { fontSize: 10, color: "var(--amber)", fontWeight: 700, marginBottom: 6, letterSpacing: 1 },
    alertRow:{ fontSize: 11, color: "var(--ink)", marginBottom: 3 },
    alertSub:{ fontSize: 11, color: "var(--ink-4)", marginTop: 8, fontStyle: "italic" },
  };

  if (loading) return (
    <div style={sty.wrap}>
      <div style={sty.header}>SECTOR ROTATION ENGINE</div>
      <div style={sty.muted}>◇ LOADING ROTATION DATA...</div>
    </div>
  );

  if (!data || data.error || !data.sectors?.length) return (
    <div style={sty.wrap}>
      <div style={sty.header}>SECTOR ROTATION ENGINE</div>
      <div style={sty.muted}>Rotation data unavailable.</div>
    </div>
  );

  const { sectors, camd_alerts, macro_env } = data;

  const positive  = sectors.filter(s => s.roc_21 > 0);
  const negative  = sectors.filter(s => s.roc_21 < 0);
  const intoNames = positive.slice(0, 2).map(s => s.name).join(" and ");
  const outNames  = negative.slice(-2).map(s => s.name).reverse().join(" and ");
  let summary;
  if (intoNames && outNames) {
    summary = `Money appears to be flowing INTO ${intoNames}, and OUT OF ${outNames} this month.`;
  } else if (intoNames) {
    summary = `Money appears to be flowing INTO ${intoNames} this month.`;
  } else if (outNames) {
    summary = `Money appears to be flowing OUT OF ${outNames} this month.`;
  } else {
    summary = "Sector flows are mixed with no clear directional trend this month.";
  }

  return (
    <div style={sty.wrap}>
      <div style={sty.header}>SECTOR ROTATION ENGINE</div>
      <div style={sty.summary}>{summary}</div>

      <table style={sty.table}>
        <thead>
          <tr>
            <th style={sty.th}>SECTOR</th>
            <th style={sty.thR}>5D RS</th>
            <th style={sty.thR}>21D RS</th>
            <th style={sty.thR}>FLOW</th>
          </tr>
        </thead>
        <tbody>
          {sectors.map(s => {
            const rowBg = s.roc_21 > 0
              ? "rgba(0,200,100,0.07)"
              : s.roc_21 < 0
              ? "rgba(200,50,50,0.07)"
              : "transparent";
            const r5Arrow = s.roc_5 >= 0 ? "▲" : "▼";
            const r5Color = s.roc_5 >= 0 ? "var(--buy)" : "var(--sell)";
            return (
              <tr key={s.ticker} style={{ background: rowBg, borderBottom: "1px solid rgba(255,255,255,0.03)" }}>
                <td style={{ ...sty.td, color: "var(--ink)" }}>{s.name}</td>
                <td style={{ ...sty.tdR, color: r5Color }}>
                  {r5Arrow}{Math.abs(s.roc_5).toFixed(2)}%
                </td>
                <td style={{ ...sty.tdR, color: s.roc_21 >= 0 ? "var(--buy)" : "var(--sell)" }}>
                  {s.roc_21 >= 0 ? "+" : ""}{s.roc_21.toFixed(2)}%
                </td>
                <td style={sty.tdR}>
                  {s.camd && (
                    <span style={{ color: "var(--buy)", fontSize: 10, fontWeight: 600 }}>◆ CAMD</span>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>

      {camd_alerts?.length > 0 && (
        <div style={sty.alert}>
          <div style={sty.alertHd}>⚡ ROTATION ALERT</div>
          {camd_alerts.map(a => (
            <div key={a.ticker} style={sty.alertRow}>
              {a.ticker} · {a.name} — 21D: {a.roc_21 >= 0 ? "+" : ""}{a.roc_21.toFixed(2)}% · 5D: {a.roc_5 >= 0 ? "+" : ""}{a.roc_5.toFixed(2)}% · Divergence: {a.divergence_strength >= 0 ? "+" : ""}{a.divergence_strength.toFixed(2)}
            </div>
          ))}
          {macro_env?.interpretation && (
            <div style={sty.alertSub}>{macro_env.interpretation}</div>
          )}
        </div>
      )}
    </div>
  );
}

/* ── MacroSensorCard — expandable macro sensor display ───────── */
function MacroSensorCard({ sensorKey, sensor, label, unit = "", explain }) {
  const [expanded, setExpanded] = useState(false);
  if (!sensor) return (
    <div style={{ background: "var(--bg-2)", border: "1px solid var(--line)", padding: "14px 16px", opacity: 0.4 }}>
      <Label style={{ marginBottom: 6 }}>{label}</Label>
      <span className="num" style={{ fontSize: 18, color: "var(--ink-4)" }}>N/A</span>
    </div>
  );

  const val = sensor.value;
  let disp;
  if (Array.isArray(val)) {
    disp = val.slice(0, 2).map(v => v != null ? (parseFloat(v) >= 0 ? "+" : "") + parseFloat(v).toFixed(1) + "%" : "N/A").join(" / ");
  } else if (typeof val === "number") {
    disp = (unit === "%" ? ((val >= 0 ? "+" : "") + val.toFixed(1)) : val.toFixed(2)) + unit;
  } else {
    disp = val ? String(val) : "N/A";
  }

  const critical = sensor.critical;
  const warn = sensor.warning;
  const accentColor = critical ? "#ef4444" : warn ? "#f59e0b" : "#5eead4";
  const bgColor     = critical ? "rgba(239,68,68,0.07)" : warn ? "rgba(245,158,11,0.06)" : "rgba(94,234,212,0.04)";
  const borderColor = critical ? "#ef444440" : warn ? "#f59e0b40" : "var(--line)";
  const status = sensor.status || (critical ? "CRITICAL" : warn ? "WARNING" : "OK");

  return (
    <div
      onClick={() => setExpanded(e => !e)}
      style={{
        background: bgColor,
        border: `1px solid ${borderColor}`,
        borderLeft: `3px solid ${accentColor}`,
        padding: "14px 16px",
        cursor: "pointer",
        transition: "background 120ms",
        userSelect: "none",
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <div>
          <Label style={{ marginBottom: 5 }}>{label}</Label>
          <div className="num" style={{ fontSize: 26, fontWeight: 700, color: accentColor, lineHeight: 1.1 }}>{disp}</div>
          <div className="mono" style={{ fontSize: 12, color: accentColor, letterSpacing: "0.14em", marginTop: 5, opacity: 0.85 }}>{status}</div>
        </div>
        <span className="mono" style={{ fontSize: 12, color: "var(--ink-4)", letterSpacing: "0.1em", paddingTop: 2 }}>
          {expanded ? "▲" : "▼"}
        </span>
      </div>
      {expanded && explain && (
        <div style={{ marginTop: 12, paddingTop: 12, borderTop: "1px solid var(--line)" }}>
          <div style={{ fontSize: 13, color: "var(--ink-2)", lineHeight: 1.65, letterSpacing: "0.02em", fontFamily: "'JetBrains Mono', monospace" }}>
            {explain}
          </div>
        </div>
      )}
    </div>
  );
}

window.Tag = Tag;
window.Dot = Dot;
window.Label = Label;
window.CornerTicks = CornerTicks;
window.verdictColors = verdictColors;
window.EdgeRing = EdgeRing;
window.Spark = Spark;
window.PowerBar = PowerBar;
window.MiniBar = MiniBar;
window.AssetCard = AssetCard;
window.Chart = Chart;
window.SMCZonePrimitive    = SMCZonePrimitive;
window.SMCMarkersPrimitive = SMCMarkersPrimitive;
window.SMCPDPrimitive      = SMCPDPrimitive;
window.SMCLegend           = SMCLegend;
window.smcToZones   = smcToZones;
window.smcToMarkers = smcToMarkers;
window.AlertCard    = AlertCard;
window.AlertStrip   = AlertStrip;
window.MacroSensorCard = MacroSensorCard;
window.RotationSection = RotationSection;

/* ── PresetsModal — manage custom watchlist presets ──────── */
window.PresetsModal = function PresetsModal({ customPresets, saveCustomPresets, watchlist, setWatchlist, onClose }) {
  const [selectedId,  setSelectedId]  = React.useState(customPresets[0]?.id ?? null);
  const [nameVal,     setNameVal]     = React.useState(customPresets[0]?.name ?? '');
  const [addVal,      setAddVal]      = React.useState('');
  const [savedFlash,  setSavedFlash]  = React.useState(false);
  const nameTimer = React.useRef(null);
  const saveTimer = React.useRef(null);

  const selected = customPresets.find(p => p.id === selectedId) ?? null;

  /* sync name input when selection changes */
  React.useEffect(() => {
    setNameVal(selected?.name ?? '');
    setAddVal('');
  }, [selectedId]);

  /* close on Escape */
  React.useEffect(() => {
    const fn = e => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', fn);
    return () => window.removeEventListener('keydown', fn);
  }, []);

  /* clear pending timers on unmount */
  React.useEffect(() => {
    return () => { clearTimeout(nameTimer.current); clearTimeout(saveTimer.current); };
  }, []);

  function selectPreset(id) {
    setSelectedId(id);
    setWatchlist(id);
  }

  function handleNewPreset() {
    const p = { id: 'custom_' + Date.now(), name: '', syms: [] };
    saveCustomPresets([p, ...customPresets]);
    setSelectedId(p.id);
    setWatchlist(p.id);
  }

  function handleSave() {
    saveCustomPresets([...customPresets]);
    setSavedFlash(true);
    clearTimeout(saveTimer.current);
    saveTimer.current = setTimeout(() => setSavedFlash(false), 1500);
  }

  function handleNameChange(val) {
    setNameVal(val);
    clearTimeout(nameTimer.current);
    nameTimer.current = setTimeout(() => {
      saveCustomPresets(customPresets.map(p => p.id === selectedId ? { ...p, name: val } : p));
    }, 400);
  }

  function handleAddTicker() {
    const sym = addVal.trim().toUpperCase();
    if (!sym || !selected || selected.syms.includes(sym)) { setAddVal(''); return; }
    saveCustomPresets(customPresets.map(p =>
      p.id === selectedId ? { ...p, syms: [...p.syms, sym] } : p
    ));
    setAddVal('');
  }

  function handleRemoveTicker(sym) {
    saveCustomPresets(customPresets.map(p =>
      p.id === selectedId ? { ...p, syms: p.syms.filter(s => s !== sym) } : p
    ));
  }

  function handleMoveUp(id) {
    const i = customPresets.findIndex(p => p.id === id);
    if (i <= 0) return;
    const next = [...customPresets];
    [next[i - 1], next[i]] = [next[i], next[i - 1]];
    saveCustomPresets(next);
  }

  function handleMoveDown(id) {
    const i = customPresets.findIndex(p => p.id === id);
    if (i < 0 || i >= customPresets.length - 1) return;
    const next = [...customPresets];
    [next[i], next[i + 1]] = [next[i + 1], next[i]];
    saveCustomPresets(next);
  }

  function handleDelete(id) {
    const i = customPresets.findIndex(p => p.id === id);
    const remaining = customPresets.filter(p => p.id !== id);
    saveCustomPresets(remaining);
    if (selectedId === id) {
      setSelectedId(remaining[Math.min(i, remaining.length - 1)]?.id ?? null);
    }
  }

  const S = {
    backdrop: {
      position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.72)',
      zIndex: 200, display: 'flex', alignItems: 'center', justifyContent: 'center',
    },
    panel: {
      background: 'var(--bg-2)', border: '1px solid var(--line)', borderRadius: 6,
      width: 620, maxHeight: '80vh', display: 'flex', flexDirection: 'column',
      overflow: 'hidden',
    },
    header: {
      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      padding: '12px 16px', borderBottom: '1px solid var(--line)',
    },
    headerLabel: {
      fontFamily: 'var(--mono)', fontSize: 11, letterSpacing: '0.18em',
      color: 'var(--amber)', fontWeight: 600,
    },
    closeBtn: {
      background: 'none', border: 'none', color: 'var(--ink-3)', fontSize: 18,
      cursor: 'pointer', padding: '2px 6px', lineHeight: 1,
    },
    body: { display: 'flex', flex: 1, minHeight: 0 },
    leftCol: {
      width: 220, borderRight: '1px solid var(--line)', display: 'flex',
      flexDirection: 'column', padding: '10px 0',
    },
    newBtn: {
      margin: '0 10px 8px 10px', padding: '5px 0', background: 'transparent',
      border: '1px solid var(--amber)', borderRadius: 3, color: 'var(--amber)',
      fontSize: 10, fontFamily: 'var(--mono)', letterSpacing: '0.14em', cursor: 'pointer',
    },
    presetList: { flex: 1, overflowY: 'auto' },
    presetRow: (isActive) => ({
      display: 'flex', alignItems: 'center', gap: 4, padding: '5px 10px', cursor: 'pointer',
      borderLeft: isActive ? '2px solid var(--amber)' : '2px solid transparent',
      background: isActive ? 'rgba(255,160,0,0.07)' : 'transparent',
    }),
    presetName: (isActive) => ({
      flex: 1, fontFamily: 'var(--mono)', fontSize: 11,
      color: isActive ? 'var(--amber)' : 'var(--ink)', letterSpacing: '0.1em',
      whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
    }),
    iconBtn: {
      background: 'none', border: 'none', color: 'var(--ink-3)', fontSize: 11,
      cursor: 'pointer', padding: '1px 3px', lineHeight: 1,
    },
    dividerRow: {
      display: 'flex', alignItems: 'center', gap: 6, margin: '8px 10px 4px 10px',
    },
    dividerLine: { flex: 1, borderTop: '1px solid var(--line)' },
    dividerLabel: {
      fontFamily: 'var(--mono)', fontSize: 9, color: 'var(--ink-4)', letterSpacing: '0.16em',
    },
    builtinRow: {
      padding: '4px 12px', fontFamily: 'var(--mono)', fontSize: 11,
      color: 'var(--ink-3)', letterSpacing: '0.1em',
    },
    rightCol: { flex: 1, display: 'flex', flexDirection: 'column', padding: 16, gap: 12 },
    placeholder: {
      flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center',
      fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--ink-4)', letterSpacing: '0.12em',
      textAlign: 'center',
    },
    nameInput: {
      background: 'var(--bg-3)', border: '1px solid var(--line)', borderRadius: 3,
      color: 'var(--ink)', fontFamily: 'var(--mono)', fontSize: 12, padding: '6px 10px',
      letterSpacing: '0.12em', outline: 'none', width: '100%', boxSizing: 'border-box',
    },
    chipsWrap: { display: 'flex', flexWrap: 'wrap', gap: 6, minHeight: 34 },
    chip: {
      display: 'flex', alignItems: 'center', gap: 4, padding: '3px 8px',
      background: 'var(--bg-3)', border: '1px solid var(--line)', borderRadius: 12,
      fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--ink)', letterSpacing: '0.1em',
    },
    chipX: {
      background: 'none', border: 'none', color: 'var(--ink-3)', fontSize: 13,
      cursor: 'pointer', padding: 0, lineHeight: 1,
    },
    emptyChips: {
      fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--ink-4)', letterSpacing: '0.1em',
      alignSelf: 'center',
    },
    addRow: { display: 'flex', gap: 8 },
    addInput: {
      flex: 1, background: 'var(--bg-3)', border: '1px solid var(--line)', borderRadius: 3,
      color: 'var(--ink)', fontFamily: 'var(--mono)', fontSize: 11, padding: '5px 10px',
      letterSpacing: '0.12em', outline: 'none',
    },
    addBtn: {
      padding: '5px 12px', background: 'transparent', border: '1px solid var(--ink-3)',
      borderRadius: 3, color: 'var(--ink)', fontFamily: 'var(--mono)', fontSize: 10,
      letterSpacing: '0.14em', cursor: 'pointer',
    },
    saveBtn: {
      marginTop: 10, padding: '7px 0', width: '100%',
      border: 'none', borderRadius: 3,
      fontFamily: 'var(--mono)', fontSize: 11, letterSpacing: '0.14em',
      cursor: 'pointer', fontWeight: 700, transition: 'background 0.2s',
    },
  };

  return (
    <div style={S.backdrop} onClick={e => { if (e.target === e.currentTarget) onClose(); }}>
      <div style={S.panel}>

        {/* Header */}
        <div style={S.header}>
          <span style={S.headerLabel}>MANAGE PRESETS</span>
          <button style={S.closeBtn} onClick={onClose}>×</button>
        </div>

        {/* Body */}
        <div style={S.body}>

          {/* Left column — preset list */}
          <div style={S.leftCol}>
            <button style={S.newBtn} onClick={handleNewPreset}>+ NEW PRESET</button>
            <div style={S.presetList}>
              {customPresets.map((p, i) => (
                <div key={p.id} style={S.presetRow(selectedId === p.id)}
                  onClick={() => selectPreset(p.id)}>
                  <span style={S.presetName(selectedId === p.id)}>
                    {p.id === watchlist ? '◆ ' : ''}{p.name || 'Untitled Preset'}
                  </span>
                  <button style={{...S.iconBtn, opacity: i === 0 ? 0.25 : 1}} title="Move up"
                    onClick={e => { e.stopPropagation(); handleMoveUp(p.id); }}
                    disabled={i === 0}>&#9650;</button>
                  <button style={{...S.iconBtn, opacity: i === customPresets.length - 1 ? 0.25 : 1}} title="Move down"
                    onClick={e => { e.stopPropagation(); handleMoveDown(p.id); }}
                    disabled={i === customPresets.length - 1}>&#9660;</button>
                  <button style={S.iconBtn} title="Delete preset"
                    onClick={e => { e.stopPropagation(); handleDelete(p.id); }}>&#128465;</button>
                </div>
              ))}

              {/* Defaults divider */}
              <div style={S.dividerRow}>
                <div style={S.dividerLine} />
                <span style={S.dividerLabel}>DEFAULTS</span>
                <div style={S.dividerLine} />
              </div>

              {/* Built-ins — read only */}
              {window.WATCHLISTS.map(w => (
                <div key={w.id} style={S.builtinRow}>{w.name}</div>
              ))}
            </div>
          </div>

          {/* Right column — editor */}
          <div style={S.rightCol}>
            {!selected ? (
              <div style={S.placeholder}>
                {customPresets.length === 0
                  ? 'Click + NEW PRESET to get started'
                  : 'Select a preset to edit'}
              </div>
            ) : (
              <>
                <input
                  style={S.nameInput}
                  placeholder="Preset name…"
                  value={nameVal}
                  onChange={e => handleNameChange(e.target.value)}
                />
                <div style={S.chipsWrap}>
                  {selected.syms.length === 0
                    ? <span style={S.emptyChips}>No assets yet — add a ticker below</span>
                    : selected.syms.map(sym => (
                        <div key={sym} style={S.chip}>
                          <span>{sym}</span>
                          <button style={S.chipX} onClick={() => handleRemoveTicker(sym)}>&times;</button>
                        </div>
                      ))
                  }
                </div>
                <div style={S.addRow}>
                  <input
                    style={S.addInput}
                    placeholder="Add ticker (e.g. AAPL, BTC)…"
                    value={addVal}
                    onChange={e => setAddVal(e.target.value)}
                    onKeyDown={e => { if (e.key === 'Enter') handleAddTicker(); }}
                  />
                  <button style={S.addBtn} onClick={handleAddTicker}>ADD</button>
                </div>
                <button
                  style={{...S.saveBtn, background: savedFlash ? 'var(--buy)' : 'var(--amber)', color: savedFlash ? '#fff' : '#000'}}
                  onClick={handleSave}
                >{savedFlash ? '✓ SAVED' : 'SAVE PRESET'}</button>
              </>
            )}
          </div>

        </div>
      </div>
    </div>
  );
};

/* ── PortfolioSetupModal ─────────────────────────────────── */
function PortfolioSetupModal({ preset, existingPortfolio, onSave, onClose }) {
  // Follow the portfolio page's active theme (light = muted lavender, dark = Banshee)
  const PM = (window.portfolioPalette
    ? window.portfolioPalette(localStorage.getItem('banshee_portfolio_theme') || 'light')
    : { bg0:'#c4c3d0', bg1:'#d2d1dd', bg2:'#dcdbe6', line:'#9f9db3', ink:'#191526',
        ink3:'#453f5e', mint:'#1c8a66', rose:'#ab3257', peach:'#b06a1c', gold:'#927014',
        btn:'#5a41a4', btnInk:'#ffffff' });

  const cryptoCls = s => /[\/\-]USDT?$/i.test(String(s)) ? 'CRYPTO' : 'EQUITY';
  const todayISO = () => new Date().toISOString().slice(0, 10);

  // sym -> asset class, preserved from the prior holdings snapshot / preset so the
  // derived snapshot we save keeps sector tags (TECH/FINANCE) alive for the endpoint.
  const clsMap = React.useMemo(() => {
    const m = {};
    (existingPortfolio?.holdings ?? []).forEach(h => { if (h.cls) m[h.sym] = h.cls; });
    (Array.isArray(preset?.symbols) ? preset.symbols : []).forEach(x => {
      if (x.cls && !m[x.sym]) m[x.sym] = x.cls;
    });
    return m;
  }, []);

  // Build the initial editable transaction rows. Precedence:
  //   1. an existing persisted `transactions` array (Phase 2 portfolios)
  //   2. migrate legacy `holdings` -> opening BUY rows (pre-Phase-2 portfolios)
  //   3. brand-new from a preset -> one opening BUY row per watchlist symbol
  function buildInitialTransactions() {
    const toStr = v => (v === null || v === undefined) ? '' : String(v);

    const existingTxns = existingPortfolio?.transactions;
    if (Array.isArray(existingTxns) && existingTxns.length) {
      return existingTxns.map((t, i) => ({
        id:      t.id || `tx_${i}`,
        type:    t.type || 'BUY',
        sym:     t.sym || '',
        shares:  toStr(t.shares),
        price:   toStr(t.price),
        amount:  toStr(t.amount),
        date:    t.date || '',
        opening: !!t.opening,
      }));
    }

    const existingHoldings = existingPortfolio?.holdings ?? [];
    if (existingHoldings.length) {
      const dates = existingHoldings.map(h => h.entry_date).filter(Boolean);
      const earliest = dates.length ? dates.reduce((a, b) => a < b ? a : b) : '';
      return existingHoldings.map((h, i) => ({
        id:      `tx_open_${i}`,
        type:    'BUY',
        sym:     h.sym,
        shares:  toStr(h.shares),
        price:   toStr(h.entry_price),
        amount:  '',
        date:    h.entry_date || earliest,
        opening: true,
      }));
    }

    let syms = [];
    if (Array.isArray(preset?.symbols) && preset.symbols.length) syms = preset.symbols.map(x => x.sym);
    else if (Array.isArray(preset?.syms) && preset.syms.length) syms = preset.syms;
    return syms.map((s, i) => ({
      id: `tx_seed_${i}`, type: 'BUY', sym: s,
      shares: '', price: '', amount: '', date: '', opening: true,
    }));
  }

  const [txns,        setTxns]        = React.useState(buildInitialTransactions);
  const [thesis,      setThesis]      = React.useState(existingPortfolio?.thesis ?? '');
  const [saving,      setSaving]      = React.useState(false);
  const [pendingSync, setPendingSync] = React.useState(null); // { type:'add', sym }
  const [draft,       setDraft]       = React.useState(null);  // new-transaction draft or null
  const idRef = React.useRef(0);
  const newId = () => `tx_new_${idRef.current++}`;

  // Per-row symbol validation: rowId -> { status:'checking'|'ok'|'warn', price, suggestion, reason }
  const [symState, setSymState] = React.useState({});

  async function validateSym(rowId, rawSym) {
    const sym = (rawSym || '').trim();
    if (!sym) {
      setSymState(s => { const n = { ...s }; delete n[rowId]; return n; });
      return;
    }
    setSymState(s => ({ ...s, [rowId]: { status: 'checking' } }));
    const res = await window.API.resolveSymbol(sym);
    setSymState(s => ({
      ...s,
      [rowId]: {
        status: (res.resolved && !res.suggestion) ? 'ok' : 'warn',
        price: res.price, suggestion: res.suggestion, reason: res.reason,
      },
    }));
  }

  function applySuggestion(rowId, suggestion) {
    const up = String(suggestion).toUpperCase();
    updateTxn(rowId, 'sym', up);
    validateSym(rowId, up);
  }

  // Close on Escape — but not while the add-transaction draft is open
  React.useEffect(() => {
    const fn = e => {
      if (e.key !== 'Escape') return;
      if (draft) { setDraft(null); return; }
      onClose();
    };
    window.addEventListener('keydown', fn);
    return () => window.removeEventListener('keydown', fn);
  }, [draft]);

  function getPrice(sym) {
    return window.RADAR_CACHE?.[sym]?.price ?? '';
  }

  const isTrade = t => t.type === 'BUY' || t.type === 'SELL';

  // Date-sorted view (stable by original index; empty dates sort first so
  // unfilled seed/opening rows stay visible at the top).
  const sorted = txns
    .map((t, i) => [t, i])
    .sort((a, b) => (a[0].date || '').localeCompare(b[0].date || '') || a[1] - b[1])
    .map(x => x[0]);

  function updateTxn(id, field, value) {
    setTxns(prev => prev.map(t => t.id === id ? { ...t, [field]: value } : t));
  }

  function deleteTxn(id) {
    setTxns(prev => prev.filter(t => t.id !== id));
    setSymState(s => { const n = { ...s }; delete n[id]; return n; });
  }

  function startAdd() {
    setDraft({ type: 'BUY', sym: '', shares: '', price: '', amount: '', date: todayISO() });
  }

  function commitAdd() {
    if (!draft) return;
    const d = draft;
    const trade = d.type === 'BUY' || d.type === 'SELL';
    // light, non-blocking validation: a trade needs a symbol; cash needs an amount
    if (trade && !d.sym.trim()) return;
    if (!trade && d.amount === '') return;
    const sym = trade ? d.sym.trim().toUpperCase() : '';
    const row = { id: newId(), type: d.type, sym,
                  shares: d.shares, price: d.price, amount: d.amount,
                  date: d.date || todayISO(), opening: false };
    setTxns(prev => [...prev, row]);
    if (row.type === 'BUY' || row.type === 'SELL') validateSym(row.id, row.sym);
    setDraft(null);
    // Watchlist sync: prompt only when a BUY introduces a symbol the preset
    // isn't already watching.
    if (d.type === 'BUY' && sym) {
      const watched = (preset?.symbols ?? []).some(x => x.sym === sym)
                   || (preset?.syms ?? []).some(s => s === sym);
      if (!watched) setPendingSync({ type: 'add', sym });
    }
  }

  async function handleSyncYes() {
    if (!pendingSync) return;
    const { sym } = pendingSync;
    let updatedSymbols = preset.symbols ?? [];
    if (!updatedSymbols.some(s => s.sym === sym)) {
      updatedSymbols = [...updatedSymbols, { sym, cls: cryptoCls(sym) }];
    }
    // Fetch the full presets list, patch the one preset, save the whole list back
    // (POST /presets replaces the entire file).
    try {
      const allPresets = (await window.API.fetchPresets()) ?? [];
      const updated = allPresets.map(p => p.id === preset.id ? { ...p, symbols: updatedSymbols } : p);
      if (!allPresets.some(p => p.id === preset.id)) {
        updated.push({ ...preset, symbols: updatedSymbols });
      }
      await window.API.savePresets(updated);
    } catch (e) {
      console.warn('[PortfolioSetupModal] sync preset:', e.message);
    }
    setPendingSync(null);
  }

  function handleSyncNo() { setPendingSync(null); }

  async function handleAnalyze() {
    setSaving(true);

    // Build the authoritative transactions payload. Skip incomplete rows rather
    // than erroring (a trade needs sym+date; a cash row needs a date).
    const txOut = txns.map(t => {
      const base = { id: t.id, type: t.type, date: t.date || null };
      if (t.opening) base.opening = true;
      if (isTrade(t)) {
        return { ...base,
          sym:    t.sym.trim().toUpperCase(),
          shares: t.shares !== '' ? parseFloat(t.shares) : 0,
          price:  t.price  !== '' ? parseFloat(t.price)  : null };
      }
      return { ...base, amount: t.amount !== '' ? parseFloat(t.amount) : 0 };
    }).filter(t => (t.type === 'BUY' || t.type === 'SELL') ? (t.sym && t.date) : !!t.date);

    // Derived holdings snapshot: net shares per symbol (BUY - SELL), carrying cls
    // so the analysis endpoint's sector-class map survives. Money math always
    // re-derives from `transactions`; this is a denormalized cache only.
    const net = {};
    txOut.forEach(t => {
      if (t.type === 'BUY')  net[t.sym] = (net[t.sym] || 0) + (t.shares || 0);
      if (t.type === 'SELL') net[t.sym] = (net[t.sym] || 0) - (t.shares || 0);
    });
    const holdingsSnap = Object.keys(net)
      .filter(s => net[s] > 1e-9)
      .map(s => ({ sym: s, cls: clsMap[s] || cryptoCls(s), shares: net[s] }));

    const body = {
      preset_id:    preset.id,
      name:         preset.name,
      thesis,
      transactions: txOut,
      holdings:     holdingsSnap,
    };

    try {
      let saved;
      if (existingPortfolio?.id) {
        saved = await window.API.updatePortfolio(existingPortfolio.id, body);
      } else {
        saved = await window.API.createPortfolio(body);
      }
      if (!saved || saved.error || !saved.id) {
        console.warn('[PortfolioSetupModal] save failed:', saved && saved.error);
        setSaving(false);
        return;
      }
      onSave(saved);
    } catch (e) {
      console.warn('[PortfolioSetupModal] save error:', e);
      setSaving(false);
    }
  }

  // Styles
  const S = {
    overlay: { position: 'fixed', inset: 0, background: 'rgba(30,22,64,0.6)',
      display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 2000 },
    box: { background: PM.bg0, borderRadius: 12, padding: 28, width: 760,
      maxWidth: 'calc(100vw - 40px)', maxHeight: '90vh', overflowY: 'auto', color: PM.ink },
    header: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 },
    title: { font: '700 13px/1 monospace', letterSpacing: 2, color: PM.ink },
    closeBtn: { background: 'transparent', border: 'none', color: PM.ink3,
      fontSize: 18, cursor: 'pointer', padding: '0 4px', lineHeight: 1 },
    section: { marginBottom: 20 },
    sectionLabel: { font: '700 11px/1 monospace', letterSpacing: 1, color: PM.ink3,
      marginBottom: 6, display: 'block' },
    textarea: { width: '100%', minHeight: 60, padding: '8px 12px',
      border: `1px solid ${PM.line}`, borderRadius: 8, background: PM.bg2, color: PM.ink,
      fontSize: 12, resize: 'vertical', boxSizing: 'border-box', fontFamily: 'monospace' },
    table: { width: '100%', borderCollapse: 'collapse' },
    th: { font: '700 11px/1 monospace', color: PM.ink3, letterSpacing: 1,
      padding: '4px 8px', textAlign: 'left', borderBottom: `1px solid ${PM.line}` },
    td: { padding: '4px 8px', verticalAlign: 'middle' },
    typeText: { font: '700 11px/1 monospace', letterSpacing: 0.5 },
    openTag: { font: '700 9px/1 monospace', color: PM.ink3, marginLeft: 6,
      border: `1px solid ${PM.line}`, borderRadius: 4, padding: '1px 4px', letterSpacing: 0.5 },
    muted: { font: '12px/1 monospace', color: PM.ink3 },
    input: { padding: '4px 8px', border: `1px solid ${PM.line}`, borderRadius: 6,
      background: PM.bg1, color: PM.ink, fontSize: 12, width: '100%',
      boxSizing: 'border-box', fontFamily: 'monospace' },
    select: { padding: '4px 8px', border: `1px solid ${PM.line}`, borderRadius: 6,
      background: PM.bg1, color: PM.ink, fontSize: 12, fontFamily: 'monospace' },
    deleteBtn: { color: PM.rose, cursor: 'pointer', padding: '0 6px',
      background: 'transparent', border: 'none', fontSize: 14, lineHeight: 1 },
    addRowBtn: { background: 'transparent', border: `1px dashed ${PM.line}`,
      color: PM.ink3, borderRadius: 6, padding: '4px 12px', font: '12px monospace',
      cursor: 'pointer', marginTop: 8 },
    draftRow: { background: PM.bg2, borderRadius: 8, padding: 12, marginTop: 8,
      display: 'flex', flexWrap: 'wrap', gap: 8, alignItems: 'center' },
    draftAddBtn: { background: PM.btn, color: PM.btnInk, border: 'none', borderRadius: 6,
      padding: '5px 14px', font: '700 11px monospace', cursor: 'pointer' },
    draftCancelBtn: { background: 'transparent', border: `1px solid ${PM.line}`, color: PM.ink3,
      borderRadius: 6, padding: '5px 12px', font: '11px monospace', cursor: 'pointer' },
    footer: { display: 'flex', justifyContent: 'flex-end', gap: 10, marginTop: 24,
      paddingTop: 16, borderTop: `1px solid ${PM.line}` },
    cancelBtn: { background: 'transparent', border: `1px solid ${PM.line}`, color: PM.ink3,
      borderRadius: 6, padding: '8px 14px', font: '12px monospace', cursor: 'pointer' },
    analyzeBtn: { background: PM.btn, color: PM.btnInk, border: 'none', borderRadius: 6,
      padding: '8px 20px', font: '700 12px monospace', cursor: 'pointer', opacity: saving ? 0.6 : 1 },
    syncBanner: { position: 'sticky', bottom: 0, background: PM.gold, color: PM.ink,
      borderRadius: 8, padding: '10px 16px', marginTop: 12, font: '12px monospace',
      display: 'flex', alignItems: 'center', gap: 12 },
    syncBannerText: { flex: 1, fontSize: 12, fontFamily: 'monospace' },
    syncBtn: { background: PM.ink, color: PM.bg0, border: 'none', borderRadius: 4,
      padding: '4px 10px', font: '700 11px monospace', cursor: 'pointer' },
    syncBtnNo: { background: 'transparent', border: `1px solid ${PM.ink}`, color: PM.ink,
      borderRadius: 4, padding: '4px 10px', font: '11px monospace', cursor: 'pointer' },
  };

  const TYPES = ['BUY', 'SELL', 'DEPOSIT', 'WITHDRAW'];

  return (
    <div style={S.overlay} onClick={e => { if (e.target === e.currentTarget) onClose(); }}>
      <div style={S.box}>

        {/* Header */}
        <div style={S.header}>
          <span style={S.title}>PORTFOLIO SETUP — {preset.name}</span>
          <button style={S.closeBtn} onClick={onClose} title="Close">✕</button>
        </div>

        {/* Investment Thesis — this is what the AI reacts to */}
        <div style={S.section}>
          <span style={S.sectionLabel}>YOUR GOAL / THESIS — ◈ THE AI WEIGHS IN ON THIS</span>
          <textarea
            style={S.textarea}
            value={thesis}
            onChange={e => setThesis(e.target.value)}
            placeholder="e.g. I want to 4x these over the next year by buying the dip. (The AI grades whether your holdings actually support this.)"
          />
        </div>

        {/* Transaction Ledger */}
        <div style={S.section}>
          <span style={S.sectionLabel}>TRANSACTION LEDGER — BUY / SELL / DEPOSIT / WITHDRAW</span>
          <table style={S.table}>
            <thead>
              <tr>
                <th style={{ ...S.th, width: 130 }}>DATE</th>
                <th style={{ ...S.th, width: 90 }}>TYPE</th>
                <th style={S.th}>SYM</th>
                <th style={{ ...S.th, width: 90 }}>SHARES</th>
                <th style={{ ...S.th, width: 120 }}>PRICE / AMT</th>
                <th style={{ ...S.th, width: 32 }}></th>
              </tr>
            </thead>
            <tbody>
              {sorted.map(t => (
                <tr key={t.id}>
                  <td style={S.td}>
                    <input
                      style={S.input}
                      type="date"
                      max="2100-12-31"
                      value={/^\d{4}-\d{2}-\d{2}$/.test(t.date || '') ? t.date : ''}
                      onChange={e => updateTxn(t.id, 'date', e.target.value)}
                    />
                  </td>
                  <td style={S.td}>
                    <span style={{ ...S.typeText,
                      color: t.type === 'BUY' ? PM.mint : t.type === 'SELL' ? PM.rose : PM.ink3 }}>
                      {t.type}
                    </span>
                    {t.opening && <span style={S.openTag} title="opening balance">OPEN</span>}
                  </td>
                  <td style={S.td}>
                    {isTrade(t) ? (
                      <div>
                        <input style={S.input} type="text" value={t.sym}
                          onChange={e => updateTxn(t.id, 'sym', e.target.value.toUpperCase())}
                          onBlur={e => validateSym(t.id, e.target.value)}
                          placeholder="SYM" />
                        {symState[t.id] && symState[t.id].status !== 'checking' && (
                          symState[t.id].status === 'ok'
                            ? <div style={{ font: '10px/1.4 monospace', color: PM.mint, marginTop: 2 }}>✓ resolves</div>
                            : <div style={{ font: '10px/1.4 monospace', color: PM.peach, marginTop: 2 }}>
                                ⚠ {symState[t.id].reason === 'crypto_ambiguity'
                                      ? `${t.sym} is a stock`
                                      : `couldn't price ${t.sym}`}
                                {symState[t.id].suggestion && (
                                  <> — <span style={{ color: PM.btn, cursor: 'pointer', textDecoration: 'underline' }}
                                         onClick={() => applySuggestion(t.id, symState[t.id].suggestion)}>
                                       use {symState[t.id].suggestion}</span></>
                                )}
                              </div>
                        )}
                        {symState[t.id] && symState[t.id].status === 'checking' && (
                          <div style={{ font: '10px/1.4 monospace', color: PM.ink3, marginTop: 2 }}>…</div>
                        )}
                      </div>
                    ) : <span style={S.muted}>—</span>}
                  </td>
                  <td style={S.td}>
                    {isTrade(t)
                      ? <input style={S.input} type="number" min="0" value={t.shares}
                          onChange={e => updateTxn(t.id, 'shares', e.target.value)} placeholder="0" />
                      : <span style={S.muted}>—</span>}
                  </td>
                  <td style={S.td}>
                    {isTrade(t)
                      ? <input style={S.input} type="number" min="0" value={t.price}
                          onChange={e => updateTxn(t.id, 'price', e.target.value)}
                          placeholder={getPrice(t.sym) ? String(getPrice(t.sym)) : 'price'} />
                      : <input style={S.input} type="number" min="0" value={t.amount}
                          onChange={e => updateTxn(t.id, 'amount', e.target.value)} placeholder="$ amount" />}
                  </td>
                  <td style={S.td}>
                    <button style={S.deleteBtn} onClick={() => deleteTxn(t.id)} title="Remove transaction">×</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {/* Add-transaction draft */}
          {draft ? (
            <div style={S.draftRow}>
              <select style={S.select} value={draft.type}
                onChange={e => setDraft({ ...draft, type: e.target.value })}>
                {TYPES.map(ty => <option key={ty} value={ty}>{ty}</option>)}
              </select>
              <input style={{ ...S.input, width: 120 }} type="date" max="2100-12-31"
                value={draft.date}
                onChange={e => setDraft({ ...draft, date: e.target.value })} />
              {(draft.type === 'BUY' || draft.type === 'SELL') ? (
                <>
                  <input style={{ ...S.input, width: 90 }} type="text" autoFocus
                    value={draft.sym} placeholder="SYM"
                    onChange={e => setDraft({ ...draft, sym: e.target.value.toUpperCase() })}
                    onKeyDown={e => { if (e.key === 'Enter') commitAdd(); }} />
                  <input style={{ ...S.input, width: 80 }} type="number" min="0"
                    value={draft.shares} placeholder="shares"
                    onChange={e => setDraft({ ...draft, shares: e.target.value })}
                    onKeyDown={e => { if (e.key === 'Enter') commitAdd(); }} />
                  <input style={{ ...S.input, width: 90 }} type="number" min="0"
                    value={draft.price} placeholder="price"
                    onChange={e => setDraft({ ...draft, price: e.target.value })}
                    onKeyDown={e => { if (e.key === 'Enter') commitAdd(); }} />
                </>
              ) : (
                <input style={{ ...S.input, width: 120 }} type="number" min="0" autoFocus
                  value={draft.amount} placeholder="$ amount"
                  onChange={e => setDraft({ ...draft, amount: e.target.value })}
                  onKeyDown={e => { if (e.key === 'Enter') commitAdd(); }} />
              )}
              <button style={S.draftAddBtn} onClick={commitAdd}>ADD</button>
              <button style={S.draftCancelBtn} onClick={() => setDraft(null)}>CANCEL</button>
            </div>
          ) : (
            <button style={S.addRowBtn} onClick={startAdd}>+ ADD TRANSACTION</button>
          )}
        </div>

        {/* Sync Prompt Banner */}
        {pendingSync && (
          <div style={S.syncBanner}>
            <span style={S.syncBannerText}>
              Add {pendingSync.sym} to the {preset.name} watchlist too?
            </span>
            <button style={S.syncBtn} onClick={handleSyncYes}>YES</button>
            <button style={S.syncBtnNo} onClick={handleSyncNo}>NO</button>
          </div>
        )}

        {/* Footer */}
        <div style={S.footer}>
          <button style={S.cancelBtn} onClick={onClose}>CANCEL</button>
          <button style={S.analyzeBtn} onClick={handleAnalyze} disabled={saving}>
            {saving ? 'SAVING…' : 'ANALYZE ▸'}
          </button>
        </div>

      </div>
    </div>
  );
}
window.PortfolioSetupModal = PortfolioSetupModal;

/* ── PIN Lock Screen ─────────────────────────────────────── */
window.PinLockScreen = function PinLockScreen({ onUnlock }) {
  const [digits, setDigits] = React.useState('');
  const [error,  setError]  = React.useState(false);

  const storedRef = React.useRef(localStorage.getItem('banshee_pin') || '');
  const errorTimer = React.useRef(null);

  const handleDigit = (d) => {
    clearTimeout(errorTimer.current);
    if (digits.length >= 4) return;
    const next = digits + d;
    setDigits(next);
    setError(false);
    if (next.length === 4) {
      if (next === storedRef.current) {
        onUnlock();
      } else {
        errorTimer.current = setTimeout(() => { setDigits(''); setError(true); }, 300);
      }
    }
  };

  const handleBackspace = () => { clearTimeout(errorTimer.current); setDigits(d => d.slice(0, -1)); setError(false); };

  return (
    <div style={{ position: "fixed", inset: 0, background: "var(--bg-0)",
      display: "flex", flexDirection: "column", alignItems: "center",
      justifyContent: "center", zIndex: 9999 }}>
      <div className="mono" style={{ fontSize: 14, letterSpacing: "0.3em", color: "var(--ink-4)", marginBottom: 32 }}>
        ◉ BANSHEE 5
      </div>
      {/* Dots */}
      <div style={{ display: "flex", gap: 14, marginBottom: 24 }}>
        {[0,1,2,3].map(i => (
          <div key={i} style={{ width: 14, height: 14, borderRadius: "50%",
            background: i < digits.length ? (error ? "var(--sell)" : "var(--amber)") : "var(--bg-3)",
            border: `1px solid ${error ? "var(--sell)" : "var(--line)"}`,
            transition: "background 0.15s" }} />
        ))}
      </div>
      {error && <div className="mono" style={{ fontSize: 11, color: "var(--sell)", marginBottom: 14, letterSpacing: "0.12em" }}>INCORRECT PIN</div>}
      {/* Numpad */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 64px)", gap: 8 }}>
        {['1','2','3','4','5','6','7','8','9','','0','⌫'].map((d, i) => (
          <button key={i} onClick={() => d === '⌫' ? handleBackspace() : d && handleDigit(d)}
            disabled={!d && d !== '0'}
            style={{ height: 56, borderRadius: 6, border: "1px solid var(--line)",
              background: d ? "var(--bg-2)" : "transparent",
              color: "var(--ink)", fontFamily: "monospace", fontSize: 18,
              cursor: d ? "pointer" : "default", opacity: d ? 1 : 0 }}>
            {d}
          </button>
        ))}
      </div>
    </div>
  );
};

/* ── Shared helpers (moved from app.jsx) ─────────────────── */
function MetricTile({ k, v, suffix = "", color = "var(--cyan)", bar = null, text = false }) {
  return (
    <div style={{
      background: "var(--bg-2)", border: "1px solid var(--line)",
      padding: "10px 12px",
      display: "flex", flexDirection: "column", gap: 6,
      position: "relative",
    }}>
      <window.Label>{k}</window.Label>
      <div style={{ display: "flex", alignItems: "baseline", gap: 4 }}>
        {text ? (
          <span className="mono" style={{ fontSize: 14, color, fontWeight: 600, letterSpacing: "0.08em" }}>{v}</span>
        ) : (
          <>
            <span className="num" style={{ fontSize: 18, color, fontWeight: 600, lineHeight: 1 }}>{v}</span>
            <span className="mono" style={{ fontSize: 12, color: "var(--ink-3)", letterSpacing: "0.12em" }}>{suffix}</span>
          </>
        )}
      </div>
      {bar !== null && <window.MiniBar value={bar} color={color} w={140} />}
    </div>
  );
}

function Level({ k, v, c }) {
  return (
    <div style={{
      display: "flex", justifyContent: "space-between", alignItems: "center",
      padding: "6px 10px", background: "var(--bg-1)",
      borderLeft: `2px solid ${c}`,
    }}>
      <span className="mono" style={{ fontSize: 12, color: "var(--ink-3)", letterSpacing: "0.18em" }}>{k}</span>
      <span className="num" style={{ fontSize: 14, color: c, fontWeight: 600 }}>{v}</span>
    </div>
  );
}

function KV({ k, v, c }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 3 }}>
      <window.Label>{k}</window.Label>
      <span className="num" style={{ fontSize: 14, color: c, fontWeight: 600 }}>{v}</span>
    </div>
  );
}

function DeepDiveCard({ icon, title, sub, accent, onDeepDive }) {
  const [hov, setHov] = useState(false);
  return (
    <div style={{ position: "relative" }}>
      <button onClick={onDeepDive}
        onMouseEnter={() => setHov(true)}
        onMouseLeave={() => setHov(false)}
        style={{
          width: "100%",
          display: "flex", alignItems: "center", gap: 10,
          padding: "10px 14px",
          background: hov ? `${accent}12` : "var(--bg-2)",
          border: `1px solid ${hov ? accent : "var(--line)"}`,
          cursor: "pointer", textAlign: "left",
          transition: "all 140ms",
          position: "relative",
        }}>
        <span style={{ fontSize: 15, color: accent, lineHeight: 1, flexShrink: 0 }}>{icon}</span>
        <div style={{ display: "flex", flexDirection: "column", gap: 1, minWidth: 0 }}>
          <span className="mono" style={{ fontSize: 13, fontWeight: 700, color: "var(--ink)", letterSpacing: "0.1em" }}>{title}</span>
          <span className="mono" style={{ fontSize: 11, color: "var(--ink-4)", letterSpacing: "0.1em" }}>DEEP DIVE →</span>
        </div>
      </button>
      {hov && sub && (
        <div style={{
          position: "absolute", bottom: "calc(100% + 6px)", left: 0, right: 0, zIndex: 50,
          background: "var(--bg-2)", border: `1px solid ${accent}40`,
          padding: "10px 12px", pointerEvents: "none",
          boxShadow: "0 8px 24px rgba(0,0,0,0.6)",
        }}>
          <span className="mono" style={{ fontSize: 12, color: "var(--ink-3)", lineHeight: 1.6, letterSpacing: "0.06em" }}>{sub}</span>
        </div>
      )}
    </div>
  );
}

function HoverContextCard({ el, lensMode }) {
  const LENS_NAME = ["", "ALL", "BATTLEFIELD", "FOOTPRINTS", "SNIPER"];
  const LENS_DESC = [
    "",
    "Full overview — everything with dynamic weight applied.",
    "Structure only — trend narrative, swing highs/lows, BOS/CHoCH.",
    "X-Ray — FVGs and liquidity magnets. Where did price move too fast?",
    "Targeting — highest-conviction OB only. Where do I enter?",
  ];

  function fmtPrice(p) {
    if (!p && p !== 0) return "—";
    return p < 100 ? p.toFixed(4) : p.toLocaleString(undefined, { maximumFractionDigits: 0 });
  }

  const cardStyle = {
    width: 220,
    flexShrink: 0,
    alignSelf: "flex-start",
    background: "#0a0f18",
    border: "1px solid #1c2433",
    borderRadius: 4,
    fontFamily: "'JetBrains Mono', monospace",
    fontSize: 12,
    color: "#c8d4e0",
  };
  const sectionStyle = { padding: "8px 10px", borderBottom: "1px solid #1c2433" };
  const labelStyle   = { fontSize: 12, color: "#6c7889", letterSpacing: "0.08em", textTransform: "uppercase", marginBottom: 3 };
  const valueStyle   = { fontSize: 12, color: "#c8d4e0" };

  /* Empty state */
  if (!el) {
    return (
      <div style={cardStyle}>
        <div style={sectionStyle}>
          <div style={labelStyle}>Active Lens</div>
          <div style={{ ...valueStyle, fontWeight: 700, color: "#38bdf8" }}>{LENS_NAME[lensMode] || "—"}</div>
        </div>
        <div style={{ padding: "8px 10px" }}>
          <div style={{ ...valueStyle, color: "#6c7889", lineHeight: 1.6 }}>
            {LENS_DESC[lensMode] || "Hover over any chart element to inspect it."}
          </div>
        </div>
      </div>
    );
  }

  /* Order Block */
  if (el.elementType === "ob") {
    const sw      = el.session_weight || 1.0;
    const badge   = sw >= 2.0 ? "⚡ Silver Bullet ×2.0" : sw >= 1.5 ? "◈ Killzone ×1.5" : sw < 1.0 ? "Low conviction" : "Regular session";
    const hasConf = Array.isArray(el.htf_confluence) && el.htf_confluence.length > 0;
    const accentColor = el.kind === "bullish" ? "#42A5F5" : "#EF5350";
    const explainByLens = {
      1: `A ${el.kind} Order Block is a range where institutions placed a large directional order. Price tends to react when it returns here.`,
      2: `${el.kind === "bullish" ? "Buy" : "Sell"} wall. Price broke out of this zone — expect a reaction if it comes back.`,
      3: el.has_pending_inducement ? "Inducement-pending OB — a nearby liquidity pool hasn't been swept yet. Smart money may push through it before reversing here." : "Candidate OB — not yet confirmed by inducement sweep.",
      4: `Prime entry zone. ${el.kind === "bullish" ? "Enter long" : "Enter short"} inside this range. Stop beyond the far edge.`,
    };
    return (
      <div style={cardStyle}>
        <div style={{ ...sectionStyle, borderLeft: `3px solid ${accentColor}` }}>
          <div style={{ fontWeight: 700, fontSize: 12, color: accentColor }}>
            {el.kind === "bullish" ? "▲" : "▼"} {el.kind.toUpperCase()} ORDER BLOCK
          </div>
          <div style={{ marginTop: 3, color: "#FFD600", fontSize: 12 }}>
            {badge}{hasConf ? "  ★ HTF" : ""}
          </div>
        </div>
        <div style={sectionStyle}>
          <div style={{ display: "flex", gap: 10, marginBottom: 4 }}>
            <div><div style={labelStyle}>State</div><div style={valueStyle}>{el.status}</div></div>
            <div><div style={labelStyle}>Zone</div><div style={valueStyle}>{fmtPrice(el.bottom)} – {fmtPrice(el.top)}</div></div>
          </div>
          {el.touch_count > 0 && <div><div style={labelStyle}>Touches</div><div style={valueStyle}>{el.touch_count}</div></div>}
        </div>
        <div style={{ ...sectionStyle, borderBottom: "none" }}>
          <div style={{ ...valueStyle, color: "#8899aa", lineHeight: 1.6 }}>
            {explainByLens[lensMode] || explainByLens[1]}
          </div>
        </div>
        <div style={{ padding: "6px 10px", color: "#6c7889", fontSize: 12 }}>
          Watch: {el.kind === "bullish" ? `bullish close above ${fmtPrice(el.top)}` : `bearish close below ${fmtPrice(el.bottom)}`}
        </div>
      </div>
    );
  }

  /* Fair Value Gap */
  if (el.elementType === "fvg") {
    const accentColor = el.kind === "bullish" ? "#00BCD4" : "#F44336";
    return (
      <div style={cardStyle}>
        <div style={{ ...sectionStyle, borderLeft: `3px solid ${accentColor}` }}>
          <div style={{ fontWeight: 700, fontSize: 12, color: accentColor }}>
            {el.kind === "bullish" ? "▲" : "▼"} FAIR VALUE GAP
          </div>
          <div style={{ marginTop: 2, fontSize: 12, color: "#6c7889" }}>
            {el.status}{el.fill_pct > 0 ? ` · ${el.fill_pct}% filled` : ""}
          </div>
        </div>
        <div style={sectionStyle}>
          <div style={labelStyle}>Price Range</div>
          <div style={valueStyle}>{fmtPrice(el.bottom)} – {fmtPrice(el.top)}</div>
        </div>
        <div style={{ padding: "8px 10px" }}>
          <div style={{ ...valueStyle, color: "#8899aa", lineHeight: 1.6 }}>
            Gap where price moved too fast to find two-sided auction. Unmitigated FVGs act as magnets — price tends to return to fill them before continuing.
          </div>
        </div>
      </div>
    );
  }

  /* HTF Reference Line */
  if (el.elementType === "htf") {
    const typeNames  = { yearly_monthly: "Yearly / Monthly Open", market_maker: "Market Maker PD/PW Level", vwap: "VWAP Zone", elliott_wave: "Elliott Wave Pivot", other: "HTF Level" };
    const typeColors = { yearly_monthly: "#FFD600", market_maker: "#CE93D8", vwap: "#26C6DA", elliott_wave: "#90A4AE", other: "#90A4AE" };
    const t = el.level_type || "other";
    return (
      <div style={cardStyle}>
        <div style={{ ...sectionStyle, borderLeft: `3px solid ${typeColors[t]}` }}>
          <div style={{ fontWeight: 700, fontSize: 12, color: typeColors[t] }}>{typeNames[t]}</div>
        </div>
        <div style={sectionStyle}>
          <div style={labelStyle}>Price</div>
          <div style={valueStyle}>{fmtPrice(el.price)}</div>
          {el.name && <div style={{ ...labelStyle, marginTop: 4 }}>{el.name.replace(/\./g, " › ")}</div>}
        </div>
        <div style={{ padding: "8px 10px" }}>
          <div style={{ ...valueStyle, color: "#8899aa", lineHeight: 1.6 }}>
            Named institutional reference level. Confluence with an OB or FVG at this price raises conviction.
          </div>
        </div>
      </div>
    );
  }

  /* EQH / EQL */
  if (el.elementType === "eqh" || el.elementType === "eql") {
    const isHigh     = el.elementType === "eqh";
    const accentColor = isHigh ? "#FF1744" : "#00E676";
    return (
      <div style={cardStyle}>
        <div style={{ ...sectionStyle, borderLeft: `3px solid ${accentColor}` }}>
          <div style={{ fontWeight: 700, fontSize: 12, color: accentColor }}>
            {isHigh ? "EQH — Equal Highs" : "EQL — Equal Lows"}
          </div>
        </div>
        <div style={sectionStyle}>
          <div style={labelStyle}>Level</div>
          <div style={valueStyle}>{fmtPrice(el.price)}</div>
        </div>
        <div style={{ padding: "8px 10px" }}>
          <div style={{ ...valueStyle, color: "#8899aa", lineHeight: 1.6 }}>
            {isHigh
              ? "Clustered sell stops above equal highs. A sweep here traps breakout longs and may precede a sharp reversal down."
              : "Clustered buy stops below equal lows. A sweep here traps breakout shorts and may precede a sharp reversal up."}
          </div>
        </div>
      </div>
    );
  }

  /* Swing marker */
  if (el.elementType === "swing") {
    const lbl     = el.label || (el.swing_type === "high" ? "H" : "L");
    const isHigh  = el.swing_type === "high";
    const accentColor = isHigh ? "#FF6D00" : "#2979FF";
    const meanings = {
      HH: "Higher High — trend is bullish, momentum intact.",
      LH: "Lower High — rally failing, bearish pressure building.",
      HL: "Higher Low — pullback held above last low, bullish structure.",
      LL: "Lower Low — trend is bearish, no support holding.",
    };
    return (
      <div style={cardStyle}>
        <div style={{ ...sectionStyle, borderLeft: `3px solid ${accentColor}` }}>
          <div style={{ fontWeight: 700, fontSize: 12, color: accentColor }}>
            {lbl} — {isHigh ? "Swing High" : "Swing Low"}
          </div>
        </div>
        <div style={sectionStyle}>
          <div style={labelStyle}>Price</div>
          <div style={valueStyle}>{fmtPrice(el.price)}</div>
        </div>
        <div style={{ padding: "8px 10px" }}>
          <div style={{ ...valueStyle, color: "#8899aa", lineHeight: 1.6 }}>
            {meanings[lbl] || (isHigh ? "Swing High — potential supply zone above." : "Swing Low — potential demand zone below.")}
          </div>
        </div>
      </div>
    );
  }

  /* BOS / CHoCH */
  if (el.elementType === "bos" || el.elementType === "choch") {
    const isBull      = el.isBull;
    const isBOS       = el.isBOS;
    const accentColor = isBOS
      ? (isBull ? "#00E676" : "#FF1744")
      : (isBull ? "#69F0AE" : "#FF5252");
    const label = `${isBOS ? "BOS" : "CHoCH"} ${isBull ? "▲" : "▼"}`;
    const explainBOS   = isBull
      ? "Bullish Break of Structure — a swing high was breached. Structure is now officially bullish. Watch for a pullback into the nearest OB before continuation."
      : "Bearish Break of Structure — a swing low was breached. Structure is now officially bearish. Watch for a retrace into the nearest OB before continuation.";
    const explainCHoCH = isBull
      ? "Change of Character — first bullish break after a downtrend. Potential trend reversal. Needs follow-through above the prior swing high to confirm."
      : "Change of Character — first bearish break after an uptrend. Potential trend reversal. Needs follow-through below the prior swing low to confirm.";
    return (
      <div style={cardStyle}>
        <div style={{ ...sectionStyle, borderLeft: `3px solid ${accentColor}` }}>
          <div style={{ fontWeight: 700, fontSize: 12, color: accentColor }}>{label}</div>
          <div style={{ marginTop: 2, fontSize: 12, color: "#6c7889" }}>{isBOS ? "Break of Structure" : "Change of Character"}</div>
        </div>
        <div style={sectionStyle}>
          <div style={labelStyle}>Break Level</div>
          <div style={valueStyle}>{fmtPrice(el.price)}</div>
        </div>
        <div style={{ padding: "8px 10px" }}>
          <div style={{ ...valueStyle, color: "#8899aa", lineHeight: 1.6 }}>
            {isBOS ? explainBOS : explainCHoCH}
          </div>
        </div>
      </div>
    );
  }

  return null;
}

function NumInput({ label, value, onChange, step = 1 }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
      <div className="mono" style={{ fontSize: 12, color: "var(--ink-4)", letterSpacing: "0.14em" }}>{label}</div>
      <input
        type="number" step={step}
        value={value}
        onChange={e => onChange(parseFloat(e.target.value) || 0)}
        className="mono"
        style={{ background: "var(--bg-3)", border: "1px solid var(--line-2)", color: "var(--ink)", padding: "7px 10px", fontSize: 12, letterSpacing: "0.06em", outline: "none", width: "100%" }}
      />
    </div>
  );
}

window.MetricTile       = MetricTile;
window.Level            = Level;
window.KV               = KV;
window.DeepDiveCard     = DeepDiveCard;
window.HoverContextCard = HoverContextCard;
window.NumInput         = NumInput;

/* ── Risk Disclaimer Modal ───────────────────────────────────── */
window.DisclaimerModal = function DisclaimerModal({ onAccept }) {
  return (
    <div style={{
      position: "fixed", inset: 0, zIndex: 9999,
      background: "var(--bg-1)",
      display: "flex", alignItems: "center", justifyContent: "center",
    }}>
      <div style={{
        maxWidth: 520, width: "90%",
        padding: "36px 40px",
        border: "1px solid var(--sell)",
        background: "var(--bg-2)",
        fontFamily: "monospace",
      }}>
        <div style={{
          color: "var(--sell)", fontSize: 13, fontWeight: "bold",
          letterSpacing: "0.1em", marginBottom: 20,
        }}>
          ⚠ EXPERIMENTAL SOFTWARE
        </div>
        <p style={{ color: "var(--ink)", fontSize: 12, lineHeight: 1.7, marginBottom: 16 }}>
          BANSHEE PRO is experimental software intended for personal use, education,
          and paper trading only. It is not financial advice. The authors accept no
          responsibility for any financial losses. Past signals do not predict future results.
        </p>
        <p style={{ color: "var(--ink)", fontSize: 12, lineHeight: 1.7, marginBottom: 28 }}>
          By continuing, you acknowledge this software carries no warranty and you
          trade entirely at your own risk.
        </p>
        <button
          onClick={onAccept}
          style={{
            background: "#FF6D00", color: "#000", border: "none",
            padding: "10px 24px", fontSize: 12, fontFamily: "monospace",
            fontWeight: "bold", letterSpacing: "0.08em", cursor: "pointer",
            width: "100%",
          }}
        >
          I UNDERSTAND — CONTINUE
        </button>
      </div>
    </div>
  );
};
