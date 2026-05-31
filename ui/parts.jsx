/* Banshee — HUD parts */
const { useState, useEffect, useRef, useMemo } = React;

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
  const c = verdictColors(asset.verdict);
  const candles = useMemo(() => window.buildCandles(asset.sym, "1H", 60), [asset.sym]);
  const up = asset.chg >= 0;
  const loading = asset._loading;

  return (
    <button
      onClick={onClick}
      style={{
        position: "relative",
        textAlign: "left",
        background: "linear-gradient(180deg, var(--bg-2), var(--bg-1))",
        border: `1px solid ${selected ? c.fg : "var(--line)"}`,
        padding: 0,
        cursor: "pointer",
        transition: "border-color 200ms, transform 120ms",
        boxShadow: selected ? `0 0 0 1px ${c.fg} inset, 0 0 24px ${c.glow}` : "none",
        overflow: "hidden",
      }}
      onMouseEnter={(e) => { if (!selected) e.currentTarget.style.borderColor = "var(--line-2)"; }}
      onMouseLeave={(e) => { if (!selected) e.currentTarget.style.borderColor = "var(--line)"; }}
    >
      {/* top stripe */}
      <div style={{
        height: 3, width: "100%",
        background: loading
          ? "linear-gradient(90deg, var(--line-2), var(--line) 60%, transparent)"
          : `linear-gradient(90deg, ${c.fg}, ${c.fg}30 60%, transparent)`,
      }} />

      {loading && (
        <div style={{
          position: "absolute", inset: 0, zIndex: 2, pointerEvents: "none",
          background: "rgba(6,8,12,0.35)",
          display: "flex", alignItems: "flex-end", justifyContent: "flex-end",
          padding: "6px 8px",
        }}>
          <span className="mono blink" style={{
            fontSize: 11, letterSpacing: "0.18em", color: "var(--ink-3)",
          }}>◇ LOADING…</span>
        </div>
      )}

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
              {asset.name} · {asset.pair}
            </div>
          </div>
          <div style={{
            display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 1,
          }}>
            <div className="num" style={{ fontSize: 16, fontWeight: 600, color: "var(--ink)", lineHeight: 1 }}>
              {asset.price < 10 ? asset.price.toFixed(3) :
               asset.price < 100 ? asset.price.toFixed(2) :
               asset.price.toLocaleString(undefined, { maximumFractionDigits: 2 })}
            </div>
            <div className="num" style={{ fontSize: 13, color: up ? "var(--buy)" : "var(--sell)", lineHeight: 1 }}>
              {up ? "+" : ""}{asset.chg.toFixed(2)}%
            </div>
          </div>
        </div>

        {/* spark */}
        <div style={{ position: "relative", height: 36 }}>
          <Spark candles={candles} color={up ? "var(--buy)" : "var(--sell)"} w={400} h={36} />
        </div>

        {/* verdict + edge row */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 10 }}>
          <div style={{
            display: "flex", alignItems: "center", gap: 8,
            padding: "5px 10px",
            background: c.bg,
            border: `1px solid ${c.fg}40`,
            clipPath: "polygon(6px 0, 100% 0, calc(100% - 6px) 100%, 0 100%)",
          }}>
            <Dot color={c.fg} blink={asset.verdict !== "WAIT"} size={5} />
            <span className="mono" style={{
              fontSize: 13, color: c.fg, fontWeight: 600,
              letterSpacing: "0.16em",
            }}>{asset.verdict}</span>
          </div>
          <EdgeRing value={asset.edge} size={48} color={c.fg} />
        </div>

        {/* footer metrics */}
        <div style={{
          display: "grid", gridTemplateColumns: "1fr 1fr",
          gap: "6px 10px",
          paddingTop: 8, borderTop: "1px dashed var(--line)",
        }}>
          <div style={{ display: "flex", flexDirection: "column", gap: 3 }}>
            <Label>BIAS</Label>
            <div className="mono" style={{ fontSize: 13, color: "var(--ink-2)", letterSpacing: "0.08em" }}>
              {asset.bias}
            </div>
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 3, alignItems: "flex-end" }}>
            <Label>RSI</Label>
            <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <MiniBar value={asset.rsi} color={asset.rsi > 70 ? "var(--sell)" : asset.rsi < 30 ? "var(--buy)" : "var(--cyan)"} w={42} />
              <span className="num" style={{ fontSize: 13, color: "var(--ink-2)" }}>{asset.rsi}</span>
            </div>
          </div>
        </div>
      </div>

      {/* HUD ID + data source badge */}
      <div className="mono" style={{
        position: "absolute", top: 8, right: 8, fontSize: 11,
        letterSpacing: "0.18em", color: asset._live ? "var(--buy)" : "var(--ink-4)",
      }}>
        {asset._live ? "◆ LIVE" : `◢ ${String(Math.abs(asset.sym.charCodeAt(0) * 7 % 999)).padStart(3,"0")}`}
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

      for (const z of zones) {
        const rawTop = series.priceToCoordinate(z.top);
        const rawBot = series.priceToCoordinate(z.bottom);
        if (rawTop === null && rawBot === null) continue;
        const topPx = Math.max(0, Math.min(rawTop ?? 0, rawBot ?? bh / vr) * vr);
        const botPx = Math.min(bh, Math.max(rawTop ?? 0, rawBot ?? bh / vr) * vr);
        const h = Math.max(1, botPx - topPx);

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

        const fillAlp = z.isFVG
          ? (z.status === "partial" ? 0.25 : 0.55)
          : (z.dashed ? 0.06 : 0.22);
        const bordAlp = z.dashed ? 0.28 : 0.75;
        const toFill  = (a) => Math.round(a * z.opacity * statusMult * 255).toString(16).padStart(2, "0");
        const toBord  = (a) => Math.round(a * z.opacity * statusMult * 255).toString(16).padStart(2, "0");

        ctx.fillStyle = fillBase + toFill(fillAlp);
        ctx.fillRect(0, topPx, bw, h);

        ctx.strokeStyle = bordBase + toBord(bordAlp);
        ctx.lineWidth   = (z.inducement_swept || z.has_pending_inducement ? 2 : 1) * hr;
        if (z.dashed) ctx.setLineDash([4 * hr, 4 * hr]);
        ctx.strokeRect(0.5 * hr, topPx + 0.5 * vr, bw - hr, h - vr);
        ctx.setLineDash([]);

        /* FVG formation timestamp — vertical anchor line where the gap opened */
        if (z.isFVG && z.timestamp && chart) {
          const unix = Math.floor(new Date(z.timestamp).getTime() / 1000);
          const xCoord = chart.timeScale().timeToCoordinate(unix);
          if (xCoord !== null) {
            const xPx = Math.round(xCoord * hr);
            ctx.strokeStyle = fillBase + "dd";
            ctx.lineWidth   = 2 * hr;
            ctx.setLineDash([]);
            ctx.beginPath();
            ctx.moveTo(xPx, topPx);
            ctx.lineTo(xPx, botPx);
            ctx.stroke();
            /* small label "FVG" above/below the tick */
            ctx.font      = `bold ${Math.round(8 * Math.min(vr, hr))}px 'JetBrains Mono', monospace`;
            ctx.fillStyle = fillBase + "cc";
            ctx.textAlign = "center";
            if (z.kind === "bullish") {
              ctx.fillText("FVG▲", xPx, topPx - 4 * vr);
            } else {
              ctx.fillText("FVG▼", xPx, botPx + 10 * vr);
            }
          }
        }

        /* Session weight badges + ★ HTF confluence (OBs only) */
        if (!z.isFVG && h > 12 * vr) {
          const sw  = z.session_weight || 1.0;
          const hasConf = Array.isArray(z.htf_confluence) && z.htf_confluence.length > 0;

          let badge = "", badgeColor = "";
          if (sw >= 2.0)      { badge = "⚡"; badgeColor = "#FFD600"; }
          else if (sw >= 1.5) { badge = "◈"; badgeColor = "#FF8F00"; }
          else if (sw < 1.0)  { badge = "·"; badgeColor = "#607D8B"; }

          const fSize = Math.round(10 * Math.min(vr, hr));
          const baseX = bw - 5 * hr;
          const baseY = topPx + 12 * vr;
          let curX = baseX;

          ctx.textAlign = "right";
          if (badge) {
            ctx.font      = `${fSize}px sans-serif`;
            ctx.fillStyle = badgeColor + Math.round(z.opacity * 220).toString(16).padStart(2, "0");
            ctx.fillText(badge, curX, baseY);
            curX -= 14 * hr;
          }
          if (hasConf) {
            ctx.font      = `bold ${fSize}px sans-serif`;
            ctx.fillStyle = "#FFFFFF" + Math.round(z.opacity * 220).toString(16).padStart(2, "0");
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
  constructor(zones, chart) {
    this._zones     = zones;
    this._chart     = chart || null;
    this._series    = null;
    this._paneViews = [new SMCZonePaneView(this)];
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
    if (["mitigated", "sapped", "invalidated"].includes(ob.status)) continue;
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
    });
  }

  for (const fvg of (ltf.fvgs || [])) {
    if (fvg.status === "filled") continue;
    zones.push({
      type:           "fvg",
      kind:           fvg.kind,
      top:            fvg.top,
      bottom:         fvg.bottom,
      status:         fvg.status,
      timestamp:      fvg.timestamp     || null,
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
      const { verticalPixelRatio: vr, horizontalPixelRatio: hr } = scope;
      const ts  = chart.timeScale();
      ctx.save();

      function txToX(tsStr) {
        const unix = Math.floor(new Date(tsStr).getTime() / 1000);
        const coord = ts.timeToCoordinate(unix);
        return coord === null ? null : Math.round(coord * hr);
      }
      function priceToY(p) {
        const coord = series.priceToCoordinate(p);
        return coord === null ? null : Math.round(coord * vr);
      }

      /* swing labels */
      ctx.font = `${Math.round(8 * hr)}px 'JetBrains Mono', monospace`;
      ctx.textAlign = "center";
      for (const sw of swings) {
        const x = txToX(sw.timestamp);
        const y = priceToY(sw.price);
        if (x === null || y === null) continue;
        const isHigh   = sw.swing_type === "high";
        const base     = isHigh ? "#ef4444" : "#5eead4";
        const label    = sw.label || (isHigh ? "H" : "L");
        const triSize  = 4 * Math.min(vr, hr);
        ctx.fillStyle  = base + "bb";
        if (isHigh) {
          const tipY = y - 10 * vr;
          ctx.beginPath();
          ctx.moveTo(x, tipY);
          ctx.lineTo(x - triSize, tipY - triSize * 1.5);
          ctx.lineTo(x + triSize, tipY - triSize * 1.5);
          ctx.closePath();
          ctx.fill();
          ctx.fillStyle = base + "88";
          ctx.fillText(label, x, tipY - triSize * 1.5 - 3 * vr);
        } else {
          const tipY = y + 10 * vr;
          ctx.beginPath();
          ctx.moveTo(x, tipY);
          ctx.lineTo(x - triSize, tipY + triSize * 1.5);
          ctx.lineTo(x + triSize, tipY + triSize * 1.5);
          ctx.closePath();
          ctx.fill();
          ctx.fillStyle = base + "88";
          ctx.fillText(label, x, tipY + triSize * 1.5 + 9 * vr);
        }
      }

      /* BOS / CHoCH event markers */
      ctx.font = `bold ${Math.round(8 * hr)}px 'JetBrains Mono', monospace`;
      ctx.textAlign = "left";
      for (const ev of events) {
        const x = txToX(ev.timestamp);
        const y = priceToY(ev.price);
        if (x === null || y === null) continue;
        const isBull = ev.event_type.includes("BULL");
        const isBOS  = ev.event_type.startsWith("BOS");
        const base   = isBull ? "#5eead4" : "#ef4444";
        const lbl    = `${isBOS ? "BOS" : "CHoCH"} ${isBull ? "▲" : "▼"}`;
        ctx.fillStyle = base + "dd";
        ctx.fillText(lbl, x + 4 * hr, y - 4 * vr);
        ctx.strokeStyle = base + "55";
        ctx.lineWidth = 1 * hr;
        ctx.setLineDash([3 * hr, 3 * hr]);
        ctx.beginPath();
        ctx.moveTo(x - 10 * hr, y);
        ctx.lineTo(x + 10 * hr, y);
        ctx.stroke();
        ctx.setLineDash([]);
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
  constructor(swings, events, chart) {
    this._swings    = swings;
    this._events    = events;
    this._chart     = chart;
    this._series    = null;
    this._paneViews = [new SMCMarkersPaneView(this)];
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
          ctx.font      = `bold ${Math.round(10 * Math.min(vr, hr))}px 'JetBrains Mono', monospace`;
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
          ctx.font      = `bold ${Math.round(10 * Math.min(vr, hr))}px 'JetBrains Mono', monospace`;
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
          ctx.font      = `${Math.round(8 * Math.min(vr, hr))}px 'JetBrains Mono', monospace`;
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
    { swatch: "#5eead4", swatchStyle: { opacity: 0.7 }, label: "Fair Value Gap (FVG)", desc: "Three-candle imbalance where price moved too fast for fair two-sided trading. Teal = bullish gap (support). Red = bearish gap (resistance)." },
    { icon: "⚡", iconColor: "#22c55e", bordColor: "#22c55e", label: "Green border — Inducement Swept", desc: "The liquidity trap in front of this OB has fired. Smart money collected stops. This OB is now actionable — highest conviction entry." },
    { icon: "⌛", iconColor: "#f59e0b", bordColor: "#f59e0b", label: "Amber border — Inducement Pending", desc: "An unswept EQH or EQL sits between price and this OB. The trap is set but hasn't fired yet. Watch this level — don't enter early." },
    { icon: "◑", iconColor: "#9ca3af", label: "Touched", desc: "A wick entered the OB zone on a first touch. The zone is still valid but has been tested once. Slightly reduced conviction." },
    { icon: "⚠", iconColor: "#f59e0b", label: "Degraded", desc: "A candle body closed past the 50% midpoint of the OB. Institutions partially failed to defend. Lower confidence — treat as support only." },
    { icon: "╌╌", iconColor: "#6c7889", label: "Dashed border — Candidate OB", desc: "Order block with no inducement detected in front of it. It may itself be the trap that smart money uses to collect retail orders. Exercise caution." },
    { bandColor: "#ef4444", bandOpacity: 0.5, label: "Premium Zone — SELL ZONE (red gradient)", desc: "Price is in the top half of the current dealing range. Brightest red = nearest the ceiling (range high). Smart money is positioned to sell here. Do NOT chase longs in premium — if you're already long, this is your target area." },
    { bandColor: "#22c55e", bandOpacity: 0.4, label: "Discount Zone — BUY ZONE (green gradient)", desc: "Price is in the bottom half of the dealing range. Deepest green = nearest the floor (range low). Smart money prefers to buy here. Long setups in discount have the highest probability. Shorts here are counter-trend." },
    { icon: "╌╌", iconColor: "#f59e0b", label: "OTE 62% / OTE 79% (amber dashed lines)", desc: "Optimal Trade Entry — the golden pocket. 61.8% to 79% Fibonacci retracement into the dealing range. Best entries cluster between these two lines. Look for OBs inside this band." },
    { icon: "─ ─", iconColor: "#9ca3af", label: "Equilibrium Line (dotted grey)", desc: "The 50% midpoint of the current dealing range between the last swing high and swing low. Neither premium nor discount — price can go either way here." },
  ];

  return (
    <div style={{ padding: "18px 14px 6px 14px" }}>
      <div style={{ background: "var(--bg-2)", border: "1px solid var(--line)", padding: "18px 20px" }}>
        <div className="mono" style={{ fontSize: 13, letterSpacing: "0.18em", color: "var(--ink-4)", marginBottom: 16 }}>
          SMC CHART KEY
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "14px 28px" }}>
          {rows.map((r, i) => (
            <div key={i} style={{ display: "flex", gap: 12, alignItems: "flex-start" }}>
              {/* swatch / icon */}
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
                  <span style={{ fontSize: 18, color: r.iconColor, lineHeight: 1 }}>{r.icon}</span>
                )}
              </div>
              {/* text */}
              <div>
                <div className="mono" style={{ fontSize: 12, fontWeight: 700, color: r.iconColor || r.bordColor || "#c8d4e0", letterSpacing: "0.04em", marginBottom: 3 }}>
                  {r.label}
                </div>
                <div style={{ fontSize: 12, color: "var(--ink-2)", lineHeight: 1.6, fontFamily: "'JetBrains Mono', monospace" }}>
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

function filterZonesForLens(zones, lensMode) {
  if (lensMode === 1) return zones; // ALL — no filter

  if (lensMode === 2) return []; // BATTLEFIELD — no OBs or FVGs

  if (lensMode === 3) {
    // FOOTPRINTS: FVGs + inducement-pending OBs + candidate OBs
    return zones.filter(z => {
      if (z.type === "fvg") return true;
      if (z.type === "ob") return z.has_pending_inducement || !z.gate_passed;
      return false;
    });
  }

  if (lensMode === 4) {
    // SNIPER: OBs only (no FVGs), with opacity tiers
    return zones
      .filter(z => z.type === "ob" && z.gate_passed) // exclude FVGs + candidates
      .map(z => {
        if (z.inducement_swept) return z; // full opacity as-is
        if (z.has_pending_inducement || z.status === "active") return { ...z, opacity: 0.40 };
        if (z.status === "touched" || z.status === "degraded")  return { ...z, opacity: 0.20 };
        return z;
      });
  }

  return zones; // fallback
}

function Chart({ symbol, tf, height = 360, accent = "var(--cyan)", smcData = null, smcLoading = false, ghData = null, ghLoading = false, xabcdData = null, xabcdLoading = false, showSMC = true, setShowSMC = () => {}, showGH = true, setShowGH = () => {}, showXABCD = true, setShowXABCD = () => {}, lensMode = 1 }) {
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
  const oteLinesRef       = useRef([]);
  const [dataSource,  setDataSource]  = useState("…");
  const [diagMsg,     setDiagMsg]     = useState("");
  const [opacityMult, setOpacityMult] = useState(1.0);

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

    const ro = new ResizeObserver(() => {
      if (containerRef.current && chartRef.current)
        chartRef.current.applyOptions({ width: containerRef.current.clientWidth });
    });
    ro.observe(containerRef.current);

    return () => {
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

    window.API.fetchOHLCV(symbol, tf).then(({ candles, source }) => {
      if (cancelled || !seriesRef.current || !candles.length) return;
      seriesRef.current.setData(candles);
      chartRef.current.timeScale().fitContent();
      setDataSource(source);
    });

    return () => { cancelled = true; };
  }, [symbol, tf]);

  /* SMC overlay — attach/detach zone primitive when data or toggle changes */
  useEffect(() => {
    const series = seriesRef.current;
    if (!series) return;

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
    const zones = filterZonesForLens(rawZones, lensMode).map(z => ({ ...z, opacity: z.opacity * opacityMult }));
    if (zones.length) {
      const prim = new SMCZonePrimitive(zones, chartRef.current);
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
        const mkPrim = new SMCMarkersPrimitive(swings, events, chartRef.current);
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
  }, [smcData, showSMC, opacityMult, lensMode]);

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

  return (
    <div style={{ position: "relative", width: "100%", height }}>
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
        <span className="mono" style={{ fontSize: 11, color: c.border, letterSpacing: "0.18em", opacity: 0.75 }}>
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

  const warn = sensor.warning;
  const accentColor = warn ? "#ef4444" : "#5eead4";
  const status = sensor.status || (warn ? "WARNING" : "OK");

  return (
    <div
      onClick={() => setExpanded(e => !e)}
      style={{
        background: warn ? "rgba(239,68,68,0.07)" : "rgba(94,234,212,0.04)",
        border: `1px solid ${warn ? "#ef444440" : "var(--line)"}`,
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
