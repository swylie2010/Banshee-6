"""
structure_map.py — Banshee Pro Structure Map Tab
=================================================
Phase 1: Candlestick chart with SMC swing point markers and BOS/CHoCH overlays.

This tab is intentionally independent of the sidebar symbol cache.
It has its own symbol and timeframe selectors so you can look at any
asset at any resolution without disrupting the rest of Banshee.
"""

import json
import requests
import pandas as pd
import streamlit as st
import plotly.graph_objects as go

from shared_data import load_providers

# ── Core HTTP helpers (mirror of app.py) ──────────────────────────
CORE_URL = "http://127.0.0.1:8765"

def _core_get(path: str, timeout: int = 30, **params):
    try:
        r = requests.get(f"{CORE_URL}{path}", params=params, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None

def _records_to_df(records: list) -> pd.DataFrame:
    if not records:
        return pd.DataFrame()
    return pd.DataFrame(records)


def _session_label(weight: float) -> str:
    """Human-readable name for a session weight value."""
    if weight >= 2.0: return "Silver Bullet"
    if weight >= 1.5: return "Killzone"
    if weight >= 1.0: return "Regular"
    if weight >= 0.8: return "London Close"
    return "Asian Range"


# ─── HTF AUTO-PAIR ─────────────────────────────────────────────────────────────
# For each chart timeframe, the default "higher" timeframe used for AI context.
# The user can override via the selector.
_HTF_DEFAULT = {
    "15m": "1h",
    "1h":  "4h",
    "4h":  "1d",
    "1d":  "1wk",
    "1wk": "1wk",
}


# ─── DATA FETCHING ─────────────────────────────────────────────────────────────

def _fetch_data(symbol: str, timeframe: str):
    """
    Fetch OHLCV data via Core's /smc/json endpoint (LTF only).
    Returns (df, error_string | None).
    """
    resp = _core_get("/smc/json", symbol=symbol, ltf=timeframe, timeout=30)
    if resp is None:
        return None, "Core unavailable"
    if "error" in resp:
        return None, resp["error"]
    records = resp.get("ltf_df", [])
    df = _records_to_df(records)
    if df.empty:
        return None, "empty response"
    return df, None


# ─── CHART BUILDER ─────────────────────────────────────────────────────────────

def _build_chart(df: pd.DataFrame, smc_data: dict,
                 show_swings: bool, show_bos: bool,
                 show_fvg: bool = True, show_fvg_mitigated: bool = False,
                 show_pd: bool = True,
                 show_ob: bool = True, show_liq: bool = True,
                 focus: bool = False, focus_n: int = 4,
                 asset_levels: dict = None,
                 flat_levels: list = None,
                 uirevision_key: str = "",
                 window_n: int = 80) -> go.Figure:
    """
    Build a Plotly candlestick chart with SMC overlays.

    Visual encoding:
      Swing Highs → orange downward triangles at the wick tip, labelled HH/LH
      Swing Lows  → blue upward triangles at the wick tip, labelled HL/LL
      BOS         → dashed horizontal line (green = bullish, red = bearish)
      CHoCH       → dotted horizontal line (same colour convention)
      FVG active  → semi-transparent rectangle (green=bullish, red=bearish)
      FVG partial → same colour, lighter opacity
      FVG mitig.  → very faint grey rectangle (hidden by default)
      P/D zones   → background shading: green=discount, red=premium, amber=OTE band
      Equilibrium → thin dashed line at 50% of dealing range

    focus / focus_n:
      When focus=True, only the most recent focus_n swing highs and focus_n swing lows
      are rendered, along with any structure events that fall within that window.
      FVGs and P/D zones are NOT affected by Focus Mode — they render based on
      their own status.
    """
    fig = go.Figure()

    # ── Candlestick base ──────────────────────────────────────────────────────
    ts_col = df["timestamp"] if "timestamp" in df.columns else df.index
    fig.add_trace(go.Candlestick(
        x=ts_col,
        open=df["open"],
        high=df["high"],
        low=df["low"],
        close=df["close"],
        increasing_line_color="#2e7d32",
        decreasing_line_color="#c62828",
        increasing_fillcolor="#81c784",
        decreasing_fillcolor="#ef9a9a",
        name="Price",
        showlegend=False,
    ))

    # ── Apply focus filter ────────────────────────────────────────────────────
    # Pull full lists first; trim them if Focus Mode is on.
    swing_highs = smc_data.get("swing_highs", [])
    swing_lows  = smc_data.get("swing_lows",  [])
    events      = smc_data.get("structure_events", [])

    if focus:
        swing_highs = swing_highs[-focus_n:] if swing_highs else []
        swing_lows  = swing_lows[-focus_n:]  if swing_lows  else []
        # Hide structure events that predate the oldest kept swing so lines
        # don't trail in from ancient history off the left edge.
        all_kept    = swing_highs + swing_lows
        cutoff_idx  = min((s["idx"] for s in all_kept), default=0)
        events      = [e for e in events if e["idx"] >= cutoff_idx]

    # ── Swing point markers ───────────────────────────────────────────────────
    if show_swings:
        if swing_highs:
            sh_x  = [ts_col.iloc[s["idx"]] for s in swing_highs]
            sh_y  = [s["price"] * 1.0012 for s in swing_highs]   # nudge above wick
            sh_lbl = [s.get("label") or "" for s in swing_highs]
            fig.add_trace(go.Scatter(
                x=sh_x, y=sh_y,
                mode="markers+text",
                marker=dict(symbol="triangle-down", size=11, color="#e65100",
                            line=dict(width=1, color="#bf360c")),
                text=sh_lbl,
                textposition="top center",
                textfont=dict(size=9, color="#e65100"),
                name="Swing High",
                showlegend=True,
            ))

        if swing_lows:
            sl_x   = [ts_col.iloc[s["idx"]] for s in swing_lows]
            sl_y   = [s["price"] * 0.9988 for s in swing_lows]   # nudge below wick
            sl_lbl = [s.get("label") or "" for s in swing_lows]
            fig.add_trace(go.Scatter(
                x=sl_x, y=sl_y,
                mode="markers+text",
                marker=dict(symbol="triangle-up", size=11, color="#0277bd",
                            line=dict(width=1, color="#01579b")),
                text=sl_lbl,
                textposition="bottom center",
                textfont=dict(size=9, color="#0277bd"),
                name="Swing Low",
                showlegend=True,
            ))

    # ── BOS / CHoCH overlays ──────────────────────────────────────────────────
    if show_bos:
        last_ts = ts_col.iloc[-1]

        for ev in events:
            idx      = ev["idx"]
            ev_ts    = ts_col.iloc[idx]
            ev_price = ev["price"]
            etype    = ev["event_type"]          # e.g. "BOS_BULL"

            is_bull = etype.endswith("BULL")
            is_bos  = etype.startswith("BOS")

            line_color = "#2e7d32" if is_bull else "#c62828"
            line_dash  = "dash" if is_bos else "dot"
            label_text = etype.replace("_", " ")

            # Horizontal line from the event candle to the right edge of the chart
            fig.add_shape(
                type="line",
                x0=ev_ts, x1=last_ts,
                y0=ev_price, y1=ev_price,
                line=dict(color=line_color, width=1.5, dash=line_dash),
            )

            # Small annotation just above/below the broken level
            fig.add_annotation(
                x=ev_ts,
                y=ev_price,
                text=label_text,
                showarrow=False,
                font=dict(size=9, color=line_color, family="monospace"),
                bgcolor="rgba(255,255,255,0.75)",
                bordercolor=line_color,
                borderwidth=1,
                borderpad=2,
                xanchor="left",
                yanchor="bottom",
            )

    # ── Fair Value Gaps ───────────────────────────────────────────────────────
    if show_fvg:
        fvgs = smc_data.get("fvgs", [])
        for fvg in fvgs:
            status = fvg["status"]

            # Skip mitigated FVGs unless the user asked to see them
            if status == "mitigated" and not show_fvg_mitigated:
                continue

            # x-span: from creation candle to mitigation candle (or right edge)
            x0 = ts_col.iloc[fvg["idx"]] if fvg["idx"] < len(ts_col) else ts_col.iloc[-1]
            if status == "mitigated" and fvg["mitigated_at"] is not None:
                mat = fvg["mitigated_at"]
                x1 = ts_col.iloc[mat] if mat < len(ts_col) else ts_col.iloc[-1]
            else:
                x1 = ts_col.iloc[-1]

            # Colour and opacity by kind + status
            if status == "mitigated":
                fill_color   = "rgba(160,160,160,0.10)"
                border_color = "rgba(160,160,160,0.25)"
            elif fvg["kind"] == "bullish":
                fill_color   = "rgba(46,125,50,0.18)"  if status == "active" else "rgba(46,125,50,0.10)"
                border_color = "rgba(46,125,50,0.50)"  if status == "active" else "rgba(46,125,50,0.30)"
            else:  # bearish
                fill_color   = "rgba(198,40,40,0.18)"  if status == "active" else "rgba(198,40,40,0.10)"
                border_color = "rgba(198,40,40,0.50)"  if status == "active" else "rgba(198,40,40,0.30)"

            fig.add_shape(
                type="rect",
                x0=x0, x1=x1,
                y0=fvg["bottom"], y1=fvg["top"],
                fillcolor=fill_color,
                line=dict(color=border_color, width=1),
                layer="below",
            )

            # Label only active / partial FVGs at creation x
            if status != "mitigated":
                label = ("FVG ▲" if fvg["kind"] == "bullish" else "FVG ▼")
                lcolor = "#2e7d32" if fvg["kind"] == "bullish" else "#c62828"
                fig.add_annotation(
                    x=x0,
                    y=fvg["top"] if fvg["kind"] == "bullish" else fvg["bottom"],
                    text=label + (" ◑" if status == "partial" else ""),
                    showarrow=False,
                    font=dict(size=8, color=lcolor, family="monospace"),
                    bgcolor="rgba(255,255,255,0.70)",
                    bordercolor=lcolor,
                    borderwidth=1,
                    borderpad=2,
                    xanchor="left",
                    yanchor="bottom" if fvg["kind"] == "bullish" else "top",
                )

    # ── Premium / Discount zones ──────────────────────────────────────────────
    if show_pd:
        pd_zones = smc_data.get("pd_zones")
        if pd_zones:
            eq        = pd_zones["equilibrium"]
            r_high    = pd_zones["range_high"]
            r_low     = pd_zones["range_low"]
            ote_top   = pd_zones["ote_top"]
            ote_bot   = pd_zones["ote_bottom"]
            state_pd  = pd_zones["state"]
            x_left    = ts_col.iloc[0]
            x_right   = ts_col.iloc[-1]

            if state_pd == "BULLISH":
                # Discount (green) = below equilibrium, Premium (red) = above
                fig.add_shape(type="rect", x0=x_left, x1=x_right,
                              y0=r_low, y1=eq,
                              fillcolor="rgba(46,125,50,0.06)",
                              line=dict(width=0), layer="below")
                fig.add_shape(type="rect", x0=x_left, x1=x_right,
                              y0=eq, y1=r_high,
                              fillcolor="rgba(198,40,40,0.06)",
                              line=dict(width=0), layer="below")
                # OTE band (amber) sits in discount zone
                fig.add_shape(type="rect", x0=x_left, x1=x_right,
                              y0=ote_bot, y1=ote_top,
                              fillcolor="rgba(245,124,0,0.12)",
                              line=dict(color="rgba(245,124,0,0.40)", width=1, dash="dot"),
                              layer="below")
            else:  # BEARISH
                fig.add_shape(type="rect", x0=x_left, x1=x_right,
                              y0=r_low, y1=eq,
                              fillcolor="rgba(198,40,40,0.06)",
                              line=dict(width=0), layer="below")
                fig.add_shape(type="rect", x0=x_left, x1=x_right,
                              y0=eq, y1=r_high,
                              fillcolor="rgba(46,125,50,0.06)",
                              line=dict(width=0), layer="below")
                # OTE band (amber) sits in premium zone
                fig.add_shape(type="rect", x0=x_left, x1=x_right,
                              y0=ote_bot, y1=ote_top,
                              fillcolor="rgba(245,124,0,0.12)",
                              line=dict(color="rgba(245,124,0,0.40)", width=1, dash="dot"),
                              layer="below")

            # Equilibrium line
            fig.add_shape(type="line", x0=x_left, x1=x_right,
                          y0=eq, y1=eq,
                          line=dict(color="rgba(120,120,120,0.60)", width=1.5, dash="dash"))
            fig.add_annotation(
                x=x_right, y=eq,
                text="EQ",
                showarrow=False,
                font=dict(size=9, color="rgba(80,80,80,0.90)", family="monospace"),
                bgcolor="rgba(255,255,255,0.75)",
                xanchor="right",
                yanchor="bottom",
            )

            # OTE label
            ote_mid = (ote_top + ote_bot) / 2
            ote_label = "OTE" + (" Disc." if state_pd == "BULLISH" else " Prem.")
            fig.add_annotation(
                x=x_right, y=ote_mid,
                text=ote_label,
                showarrow=False,
                font=dict(size=9, color="rgba(180,90,0,0.90)", family="monospace"),
                bgcolor="rgba(255,255,255,0.75)",
                xanchor="right",
                yanchor="middle",
            )

    # ── Order Blocks ─────────────────────────────────────────────────────────
    if show_ob:
        obs = smc_data.get("order_blocks", [])
        for ob in obs:
            status       = ob["status"]
            is_candidate = not ob.get("gate_passed", True)
            if status == "invalidated":
                continue   # don't render destroyed blocks
            if status == "sapped":
                continue   # wick-swept OBs are hollow — skip rendering

            ob_idx = ob["idx"]
            if ob_idx >= len(ts_col):
                continue

            x0 = ts_col.iloc[ob_idx]
            x1 = ts_col.iloc[-1]   # extend to right edge (open block)

            zt = ob["zone_top"]
            zb = ob["zone_bottom"]
            mt = ob["mean_threshold"]

            # Colour + opacity by kind + status
            if ob["kind"] == "bullish":
                base_fill   = "rgba(13,110,253,{a})"    # blue
                base_border = "rgba(13,110,253,{b})"
                label_color = "#0d6efd"
            else:
                base_fill   = "rgba(220,53,69,{a})"     # red
                base_border = "rgba(220,53,69,{b})"
                label_color = "#dc3545"

            if is_candidate:
                # Inactive/unconsolidated: muted fill, dashed border, grey label.
                opacity_fill   = 0.04
                opacity_border = 0.25
                fill_color     = base_fill.replace("{a}", str(opacity_fill))
                border_color   = base_border.replace("{b}", str(opacity_border))
                label_color    = "#888888"
            else:
                opacity_fill, opacity_border = {
                    "active":   (0.15, 0.55),
                    "touched":  (0.12, 0.45),
                    "degraded": (0.07, 0.28),
                }.get(status, (0.07, 0.28))

                fill_color   = base_fill.replace("{a}", str(opacity_fill))
                border_color = base_border.replace("{b}", str(opacity_border))

                # Inducement state overrides the border and label colour so qualifying
                # OBs stand out without adding extra shapes to an already busy chart.
                if ob.get("inducement_swept"):
                    border_color = "rgba(0,200,100,0.90)"   # green  — trap fired, actionable
                    label_color  = "#00c864"
                elif ob.get("has_pending_inducement"):
                    border_color = "rgba(255,193,7,0.90)"   # amber  — trap set, watching
                    label_color  = "#e6a800"

            # Main zone rectangle
            fig.add_shape(
                type="rect",
                x0=x0, x1=x1,
                y0=zb, y1=zt,
                fillcolor=fill_color,
                line=dict(color=border_color, width=1, dash="dash") if is_candidate
                     else dict(color=border_color, width=1),
                layer="below",
            )

            # Mean threshold dashed line inside the zone
            fig.add_shape(
                type="line",
                x0=x0, x1=x1,
                y0=mt, y1=mt,
                line=dict(color=border_color, width=1, dash="dot"),
            )

            # Label at the left edge of the zone
            kind_arrow = "▲" if ob["kind"] == "bullish" else "▼"
            if is_candidate:
                label_text = f"OB? {kind_arrow}"
            else:
                status_tag     = {"touched": " ◑", "degraded": " ⚠"}.get(status, "")
                inducement_tag = (" ⚡" if ob.get("inducement_swept")
                                  else " ⌛" if ob.get("has_pending_inducement")
                                  else "")
                sw      = ob.get("session_weight", 1.0)
                sw_tag  = f" ×{sw}" if sw != 1.0 else ""
                poi_tag = " ★" if ob.get("htf_confluence") else ""
                label_text = f"OB {kind_arrow}{status_tag}{inducement_tag}{sw_tag}{poi_tag}"
            fig.add_annotation(
                x=x0,
                y=zt if ob["kind"] == "bearish" else zb,
                text=label_text,
                showarrow=False,
                font=dict(size=8, color=label_color, family="monospace"),
                bgcolor="rgba(255,255,255,0.75)",
                bordercolor=label_color,
                borderwidth=1,
                borderpad=2,
                xanchor="left",
                yanchor="top" if ob["kind"] == "bearish" else "bottom",
            )

    # ── Equal Highs / Equal Lows ──────────────────────────────────────────────
    if show_liq:
        pools = smc_data.get("liquidity_pools", [])
        for pool in pools:
            if pool["swept"]:
                continue   # consumed liquidity is no longer relevant

            # Draw from the second swing point to the right edge
            idx_2 = pool["idx_2"]
            if idx_2 >= len(ts_col):
                continue

            x0  = ts_col.iloc[idx_2]
            x1  = ts_col.iloc[-1]
            lvl = pool["level"]

            is_eqh = pool["kind"] == "eqh"
            color  = "rgba(198,40,40,0.70)"  if is_eqh else "rgba(46,125,50,0.70)"
            label  = "EQH" if is_eqh else "EQL"
            y_anch = "bottom" if is_eqh else "top"

            fig.add_shape(
                type="line",
                x0=x0, x1=x1,
                y0=lvl, y1=lvl,
                line=dict(color=color, width=1.5, dash="dash"),
            )
            fig.add_annotation(
                x=x1,
                y=lvl,
                text=label,
                showarrow=False,
                font=dict(size=8, color=color, family="monospace"),
                bgcolor="rgba(255,255,255,0.75)",
                bordercolor=color,
                borderwidth=1,
                borderpad=2,
                xanchor="right",
                yanchor=y_anch,
            )

    # ── Named HTF Reference Levels ───────────────────────────────────────────
    if flat_levels is None and asset_levels:
        # Legacy fallback — only hit if called directly without Core-supplied flat_levels
        try:
            import smc_engine as _smc
            flat_levels = _smc.flatten_levels(asset_levels)
        except Exception:
            flat_levels = []
    if flat_levels:
        for lv in flat_levels:
            name  = lv["name"]
            price = lv["price"]
            if "opens" in name:
                lv_color = "rgba(218,165,32,0.80)"    # gold
            elif "market_maker" in name:
                lv_color = "rgba(148,0,211,0.72)"     # purple
            elif "vwap" in name:
                lv_color = "rgba(0,150,136,0.75)"     # teal
            else:
                lv_color = "rgba(90,90,115,0.55)"     # steel gray (Elliott Wave)
            short_name = name.rsplit(".", 1)[-1].replace("_", " ")
            fig.add_shape(
                type="line",
                x0=ts_col.iloc[0], x1=ts_col.iloc[-1],
                y0=price, y1=price,
                line=dict(color=lv_color, width=0.8, dash="longdash"),
            )
            fig.add_annotation(
                x=ts_col.iloc[-1], y=price,
                text=f"{short_name} {price:,.2f}",
                showarrow=False,
                font=dict(size=7, color=lv_color, family="monospace"),
                bgcolor="rgba(255,255,255,0.65)",
                bordercolor=lv_color,
                borderwidth=1,
                borderpad=2,
                xanchor="right",
                yanchor="middle",
            )

    # ── Layout ────────────────────────────────────────────────────────────────
    state       = smc_data.get("current_state", "UNDEFINED")
    state_badge = {"BULLISH": "🟢 BULLISH", "BEARISH": "🔴 BEARISH",
                   "UNDEFINED": "⚪ UNDEFINED"}.get(state, "⚪ UNDEFINED")

    # Default visible window — last N candles; user pans left for full history
    _win_start = ts_col.iloc[-window_n] if len(ts_col) > window_n else ts_col.iloc[0]

    fig.update_layout(
        title=dict(
            text=f"SMC Structure — {state_badge}",
            font=dict(size=15, color="#003366"),
        ),
        paper_bgcolor="#f0f7ff",
        plot_bgcolor="#f8fbff",
        uirevision=uirevision_key,          # preserve zoom/pan across Streamlit rerenders
        xaxis=dict(
            rangeslider=dict(visible=True, thickness=0.06),  # time overview bar at bottom
            range=[_win_start, ts_col.iloc[-1]],             # default: last 80 candles
            gridcolor="#dce9f7",
            showgrid=True,
            type="date",
        ),
        yaxis=dict(
            gridcolor="#dce9f7",
            showgrid=True,
            side="right",
            fixedrange=False,               # drag on price axis to zoom vertically
        ),
        legend=dict(
            orientation="h",
            y=1.06,
            x=0,
            font=dict(size=11),
        ),
        height=780,
        margin=dict(l=10, r=10, t=60, b=60),  # extra bottom for rangeslider
        hovermode="x",                          # tooltip per trace, not full-width block
    )

    return fig


# ─── LEGEND HELPER ────────────────────────────────────────────────────────────

def _legend_row(swatch_html: str, label: str, desc: str):
    st.markdown(
        f'<div style="display:flex;align-items:flex-start;gap:10px;margin-bottom:9px;">'
        f'{swatch_html}'
        f'<div style="font-size:0.87em;color:#0a192f;line-height:1.45;">'
        f'<strong style="color:#003366;">{label}</strong> — {desc}</div></div>',
        unsafe_allow_html=True,
    )

def _swatch(bg, border):
    return (f'<div style="width:22px;height:22px;min-width:22px;border-radius:4px;'
            f'background:{bg};border:{border};margin-top:1px;"></div>')

def _line_swatch(color):
    return (f'<div style="width:34px;min-width:34px;height:3px;border-radius:2px;'
            f'background:{color};margin-top:11px;"></div>')

def _dot_swatch(color):
    return (f'<div style="width:34px;min-width:34px;height:0;'
            f'border-top:3px dotted {color};margin-top:11px;"></div>')

def _legend_heading(title: str):
    st.markdown(
        f'<div style="font-weight:800;color:#003366;font-size:0.92em;'
        f'border-bottom:1px solid #cce0ff;padding-bottom:3px;margin:14px 0 8px 0;">'
        f'{title}</div>',
        unsafe_allow_html=True,
    )


# ─── MAIN RENDER FUNCTION ──────────────────────────────────────────────────────

def render_structure_map():
    """
    Called from app.py when the user selects the 🗺️ Structure Map nav item.
    Phase 1: swing points + BOS/CHoCH on a single timeframe chart.
    """
    st.markdown("## 🗺️ Structure Map")
    st.caption(
        "Phase 3 — swing points, BOS/CHoCH, FVGs, P/D zones, and cross-timeframe AI narrative."
    )

    # ── Controls row 1: symbol / LTF / HTF / load / analyze ──────────────────
    def _commit_symbol():
        val = st.session_state.get("smc_symbol_input", "").strip().upper()
        if val:
            st.session_state["smc_symbol"] = val
            st.session_state.pop("smc_narrative", None)

    c1, c2, c3, c4, c5 = st.columns([3, 1, 1, 1, 1])

    with c1:
        symbol = st.text_input(
            "Symbol",
            value=st.session_state.get("smc_symbol", "BTC/USD"),
            placeholder="BTC/USD, NVDA, SPY…",
            label_visibility="collapsed",
            key="smc_symbol_input",
            on_change=_commit_symbol,
        )
        st.caption("Symbol")

    with c2:
        timeframe = st.selectbox(
            "LTF",
            ["15m", "1h", "4h", "1d", "1wk"],
            index=2,   # default: 4h
            label_visibility="collapsed",
            key="smc_tf",
        )
        st.caption("LTF (chart)")

    with c3:
        # Default HTF based on selected LTF; user can override
        default_htf      = _HTF_DEFAULT.get(timeframe, "1d")
        htf_options      = ["15m", "1h", "4h", "1d", "1wk"]
        default_htf_idx  = htf_options.index(default_htf)
        htf_tf = st.selectbox(
            "HTF",
            htf_options,
            index=default_htf_idx,
            label_visibility="collapsed",
            key="smc_htf",
        )
        st.caption("HTF (AI context)")

    with c4:
        load_clicked = st.button("⟳ Load", width="stretch", key="smc_load")

    with c5:
        analyze_clicked = st.button("🤖 Analyze", width="stretch", key="smc_analyze",
                                    help="Run AI cross-timeframe SMC analysis")

    # ── Controls row 2: layer toggles ─────────────────────────────────────────
    t1, t2, t3, t4, t5, t6, t7, t8 = st.columns(8)
    with t1:
        show_swings = st.checkbox("Swings", value=True, key="smc_show_swings")
    with t2:
        show_bos = st.checkbox("BOS / CHoCH", value=True, key="smc_show_bos")
    with t3:
        show_fvg = st.checkbox("FVGs", value=True, key="smc_show_fvg",
                               help="Fair Value Gaps — active and partially mitigated")
    with t4:
        show_fvg_mitigated = st.checkbox("Mitig. FVGs", value=False, key="smc_show_fvg_mit",
                                         help="Also show fully mitigated FVGs (very faint)")
    with t5:
        show_pd = st.checkbox("P/D Zones", value=True, key="smc_show_pd",
                              help="Premium/Discount zone shading + OTE band + equilibrium line")
    with t6:
        show_ob = st.checkbox("Order Blocks", value=True, key="smc_show_ob",
                              help="Order Block zones — institutional entry/exit footprints")
    with t7:
        show_liq = st.checkbox("EQH/EQL", value=True, key="smc_show_liq",
                               help="Equal Highs / Equal Lows — resting liquidity pools")
    with t8:
        focus_mode = st.checkbox("Focus", value=False, key="smc_focus",
                                 help="Show only the most recent N swings")

    # Focus slider — only shown when Focus is ticked
    focus_n = 4
    if focus_mode:
        focus_n = st.slider(
            "Swings to show (per type)",
            min_value=2, max_value=10, value=4, step=1,
            key="smc_focus_n",
            help="e.g. 4 = last 4 swing highs + last 4 swing lows",
        )

    # Commit the symbol on load click
    if load_clicked:
        st.session_state["smc_symbol"] = symbol.strip().upper()
        st.session_state.pop("smc_narrative", None)   # clear stale narrative on reload
        st.rerun()

    active_sym = st.session_state.get("smc_symbol", "BTC/USD")
    active_tf  = st.session_state.get("smc_tf", "4h")
    active_htf = st.session_state.get("smc_htf", _HTF_DEFAULT.get(active_tf, "1d"))

    # ── Fetch LTF data + run SMC via Core ─────────────────────────────────────
    with st.spinner(f"Loading {active_sym} {active_tf}…"):
        _smc_resp = _core_get("/smc/json", symbol=active_sym, ltf=active_tf, timeout=30)

    if _smc_resp is None or "error" in (_smc_resp or {}):
        st.error(f"Could not load data for **{active_sym}**: {(_smc_resp or {}).get('error', 'Core unavailable')}")
        return

    df       = _records_to_df(_smc_resp.get("ltf_df", []))
    smc_data = _smc_resp.get("ltf_smc", {})

    if df.empty or "error" in smc_data:
        st.error(f"SMC engine error: {smc_data.get('error', 'empty data')}")
        return

    asset_levels = _smc_resp.get("asset_levels")
    flat_levels  = _smc_resp.get("flat_levels", [])

    # ── Chart ─────────────────────────────────────────────────────────────────
    fig = _build_chart(df, smc_data, show_swings, show_bos,
                       show_fvg=show_fvg, show_fvg_mitigated=show_fvg_mitigated,
                       show_pd=show_pd,
                       show_ob=show_ob, show_liq=show_liq,
                       focus=focus_mode, focus_n=focus_n,
                       asset_levels=asset_levels, flat_levels=flat_levels,
                       uirevision_key=f"{active_sym}_{active_tf}",
                       window_n=80)
    st.plotly_chart(fig, use_container_width=True)

    # ── Stats strip ───────────────────────────────────────────────────────────
    s1, s2, s3, s4, s5, s6, s7, s8, s9 = st.columns(9)
    s1.metric("Candles",          len(df))
    s2.metric("Swing Highs",      len(smc_data["swing_highs"]))
    s3.metric("Swing Lows",       len(smc_data["swing_lows"]))
    s4.metric("Structure Events", len(smc_data["structure_events"]))

    fvgs          = smc_data.get("fvgs", [])
    fvg_active    = sum(1 for f in fvgs if f["status"] == "active")
    fvg_partial   = sum(1 for f in fvgs if f["status"] == "partial")
    s5.metric("FVGs Active",  fvg_active)
    s6.metric("FVGs Partial", fvg_partial)

    obs         = smc_data.get("order_blocks", [])
    obs_active  = sum(1 for o in obs if o["status"] in ("active", "touched"))
    s7.metric("OBs Active", obs_active)

    pools       = smc_data.get("liquidity_pools", [])
    pools_live  = sum(1 for p in pools if not p["swept"])
    s8.metric("EQH/EQL", pools_live)

    state = smc_data.get("current_state", "UNDEFINED")
    state_display = {"BULLISH": "🟢 Bullish", "BEARISH": "🔴 Bearish",
                     "UNDEFINED": "⚪ Undefined"}.get(state, state)
    s9.metric("Structure", state_display)

    # P/D zone info bar
    pd_zones = smc_data.get("pd_zones")
    if pd_zones and show_pd:
        eq   = pd_zones["equilibrium"]
        rh   = pd_zones["range_high"]
        rl   = pd_zones["range_low"]
        st.caption(
            f"**Dealing Range:** {rl:,.2f} – {rh:,.2f}  |  "
            f"**EQ:** {eq:,.2f}  |  "
            f"**OTE:** {pd_zones['ote_bottom']:,.2f} – {pd_zones['ote_top']:,.2f}"
        )

    # ── Session weight info bar ───────────────────────────────────────────────
    cur_sw    = smc_data.get("current_session_weight", 1.0)
    cur_sname = _session_label(cur_sw)
    sw_color  = {"Silver Bullet": "🟡", "Killzone": "🟠",
                 "Regular": "⚪", "London Close": "🔵", "Asian Range": "🔴"}.get(cur_sname, "⚪")
    sw_advice = {
        "Silver Bullet": "Highest-probability delivery window — setups here carry maximum weight.",
        "Killzone":      "Institutional participation is elevated — good window for entries.",
        "Regular":       "Standard session — signals apply at face value.",
        "London Close":  "Reduced conviction — liquidity thins as London exits.",
        "Asian Range":   "Low-conviction chop zone — OBs formed here carry half weight.",
    }.get(cur_sname, "")
    st.caption(f"{sw_color} **Current Session: {cur_sname}** (×{cur_sw}) — {sw_advice}")

    st.divider()

    # ── Chart Legend ──────────────────────────────────────────────────────────
    with st.expander("📖 Chart Legend — what does everything mean?", expanded=False):
        col_l, col_r = st.columns(2)

        with col_l:
            _legend_heading("Candlesticks")
            _legend_row(
                _swatch("#81c784", "2px solid #2e7d32"),
                "Green candle",
                "price closed higher than it opened (bullish bar)",
            )
            _legend_row(
                _swatch("#ef9a9a", "2px solid #c62828"),
                "Red candle",
                "price closed lower than it opened (bearish bar)",
            )

            _legend_heading("Swing Markers (triangles on the chart)")
            _legend_row(
                _swatch("#e65100", "2px solid #bf360c"),
                "Orange ▼ = Swing High",
                "a local peak where price reversed downward.<br>"
                "<em>HH</em> = Higher High (uptrend) &nbsp;·&nbsp; "
                "<em>LH</em> = Lower High (downtrend) &nbsp;·&nbsp; "
                "<em>SH</em> = any swing high",
            )
            _legend_row(
                _swatch("#0277bd", "2px solid #01579b"),
                "Blue ▲ = Swing Low",
                "a local trough where price reversed upward.<br>"
                "<em>HL</em> = Higher Low (uptrend) &nbsp;·&nbsp; "
                "<em>LL</em> = Lower Low (downtrend) &nbsp;·&nbsp; "
                "<em>SL</em> = any swing low",
            )

            _legend_heading("Structure Lines (BOS / CHoCH)")
            _legend_row(
                _line_swatch("#2e7d32"),
                "Green dashed = BOS BULL",
                "Break of Structure — bullish. Price broke above a prior swing high. Upward momentum confirmed.",
            )
            _legend_row(
                _line_swatch("#c62828"),
                "Red dashed = BOS BEAR",
                "Break of Structure — bearish. Price broke below a prior swing low. Downward momentum confirmed.",
            )
            _legend_row(
                _dot_swatch("#2e7d32"),
                "Green dotted = CHoCH BULL",
                "Change of Character — first sign structure is flipping from bearish to bullish. Watch for follow-through.",
            )
            _legend_row(
                _dot_swatch("#c62828"),
                "Red dotted = CHoCH BEAR",
                "Change of Character — first sign structure is flipping from bullish to bearish.",
            )

        with col_r:
            _legend_heading("Background Shading (Premium / Discount Zones)")
            _legend_row(
                _swatch("rgba(46,125,50,0.30)", "1px solid rgba(46,125,50,0.55)"),
                "Light green background = Discount zone",
                "price is below the range midpoint. Where smart money looks to <em>buy</em>. Good area for long entries.",
            )
            _legend_row(
                _swatch("rgba(198,40,40,0.25)", "1px solid rgba(198,40,40,0.55)"),
                "Light red/pink background = Premium zone",
                "price is above the range midpoint. Where smart money looks to <em>sell</em>. Avoid chasing longs up here.",
            )
            _legend_row(
                _swatch("rgba(245,124,0,0.35)", "1px dashed rgba(245,124,0,0.75)"),
                "Amber band = OTE (Optimal Trade Entry)",
                "the 61.8–78.6% Fibonacci retracement sweet spot. Deep enough to be a real pullback, "
                "not so deep it breaks structure. Best entries cluster here.",
            )
            _legend_row(
                _dot_swatch("rgba(100,100,100,0.65)"),
                "Gray dashed line = EQ (Equilibrium)",
                "exact 50% midpoint of the current dealing range. Below EQ = discount, above EQ = premium.",
            )

            _legend_heading("Colored Rectangles — Fair Value Gaps (FVG)")
            _legend_row(
                _swatch("rgba(46,125,50,0.30)", "1px solid rgba(46,125,50,0.65)"),
                "Green box = Bullish FVG (FVG ▲)",
                "price moved up so fast it left an unfilled gap. Price often returns to fill it before "
                "continuing higher. Acts as support. <em>◑ = partially filled</em>",
            )
            _legend_row(
                _swatch("rgba(198,40,40,0.28)", "1px solid rgba(198,40,40,0.65)"),
                "Red box = Bearish FVG (FVG ▼)",
                "same idea on a down move. Acts as resistance. Price often pulls back up to fill it "
                "before continuing lower.",
            )

            _legend_heading("Colored Rectangles — Order Blocks (OB)")
            _legend_row(
                _swatch("rgba(13,110,253,0.28)", "1px solid rgba(13,110,253,0.65)"),
                "Blue box = Bullish OB (OB ▲)",
                "the last bearish candle before a strong move up — where institutions placed large buy "
                "orders. Key support zone. <em>◑ = touched &nbsp;·&nbsp; ⚠ = weakening</em>",
            )
            _legend_row(
                _swatch("rgba(220,53,69,0.28)", "1px solid rgba(220,53,69,0.65)"),
                "Red box = Bearish OB (OB ▼)",
                "the last bullish candle before a strong move down — where institutions placed large "
                "sell orders. Key resistance zone.",
            )
            _legend_row(
                _swatch("rgba(13,110,253,0.15)", "2px solid rgba(0,200,100,0.90)"),
                "Green border = OB ⚡ (inducement swept)",
                "an unswept EQH/EQL trap that sat in front of this OB has since been swept. "
                "The retail trap has fired — this OB is now actionable.",
            )
            _legend_row(
                _swatch("rgba(13,110,253,0.15)", "2px solid rgba(255,193,7,0.90)"),
                "Amber border = OB ⌛ (inducement pending)",
                "an unswept EQH/EQL trap sits between current price and this OB. "
                "Smart money has a reason to drive price here — trap is set but hasn't fired yet. "
                "Watch, don't enter.",
            )

            _legend_heading("OB Session Weight Tags")
            _legend_row(
                _swatch("rgba(255,193,7,0.30)", "1px solid rgba(255,193,7,0.80)"),
                "×2.0 = Silver Bullet",
                "OB formed during 03:00–04:00, 10:00–11:00, or 14:00–15:00 EST — the ICT highest-probability delivery windows. Strongest conviction.",
            )
            _legend_row(
                _swatch("rgba(255,140,0,0.25)", "1px solid rgba(255,140,0,0.70)"),
                "×1.5 = Killzone",
                "London (02–05 EST) or NY (07–10 EST) open killzone. Elevated institutional participation.",
            )
            _legend_row(
                _swatch("rgba(100,100,100,0.15)", "1px solid rgba(100,100,100,0.40)"),
                "No tag = Regular (×1.0)",
                "Standard session hours — no weight bonus or penalty.",
            )
            _legend_row(
                _swatch("rgba(198,40,40,0.15)", "1px solid rgba(198,40,40,0.40)"),
                "×0.8 / ×0.5 = London Close / Asian",
                "Reduced conviction. London Close (10–12 EST) = thinning liquidity. Asian Range (20:00+ EST) = low-conviction chop. OBs formed here carry less weight.",
            )

            _legend_row(
                _swatch("rgba(13,110,253,0.15)", "2px solid rgba(13,110,253,0.65)"),
                "★ = HTF Confluence (institutional POI confirmed)",
                "an Order Block whose zone overlaps a named reference level from TradingView "
                "(yearly open, market maker PD/PW, VWAP zone, or Elliott Wave pivot). "
                "Two independent methods pointing to the same price — raises conviction.",
            )

            _legend_heading("Named HTF Reference Lines")
            _legend_row(
                _line_swatch("rgba(218,165,32,0.80)"),
                "Gold dashed = Yearly / Monthly Open",
                "key annual and monthly reference prices extracted from TradingView. Yearly open = bull/bear divider for the year.",
            )
            _legend_row(
                _line_swatch("rgba(148,0,211,0.72)"),
                "Purple dashed = Market Maker PD/PW Levels",
                "ICT Previous Day / Week High and Low. Major institutional reference levels that update daily/weekly.",
            )
            _legend_row(
                _line_swatch("rgba(0,150,136,0.75)"),
                "Teal dashed = VWAP Zone",
                "VWAP Supply &amp; Demand zone boundary extracted from TradingView.",
            )
            _legend_row(
                _line_swatch("rgba(90,90,115,0.55)"),
                "Steel gray dashed = Elliott Wave Level",
                "Impulse top, wave pivots, and Fibonacci correction targets. Note: predictive targets expire when the wave completes.",
            )

            _legend_heading("Liquidity Lines (EQH / EQL)")
            _legend_row(
                _line_swatch("#c62828"),
                "Red dashed = EQH (Equal Highs)",
                "two+ swing highs at the same level. Stop-losses are clustered just above here. "
                "Smart money often sweeps this before reversing down.",
            )
            _legend_row(
                _line_swatch("#2e7d32"),
                "Green dashed = EQL (Equal Lows)",
                "two+ swing lows at the same level. Stop-losses cluster just below here. "
                "A sweep of EQL often precedes a strong reversal upward.",
            )

    # ── AI Narrative (Phase 3) ────────────────────────────────────────────────
    st.markdown("### 🤖 SMC Cross-Timeframe Analysis")
    st.caption(f"AI reads current {active_htf} HTF + {active_tf} LTF structure and narrates in plain English.")

    run_analysis = st.button(
        "🤖 Analyze Structure",
        key="smc_analyze_bottom",
        use_container_width=True,
        type="primary",
    ) or analyze_clicked

    if run_analysis:
        providers = load_providers()
        ai_cfg    = providers.get("AI_API", {})
        if not ai_cfg.get("key"):
            st.warning("No AI key configured. Set one in ⚙️ Settings.")
        else:
            with st.spinner(f"Loading HTF ({active_htf}) + analyzing structure…"):
                _ai_resp = _core_get(
                    "/smc/json",
                    symbol=active_sym, ltf=active_tf,
                    htf=active_htf if active_htf != active_tf else "",
                    use_ai="true",
                    timeout=90,
                )
            if _ai_resp and not _ai_resp.get("error"):
                narrative = _ai_resp.get("ai_narrative") or "AI narrative not returned."
                st.session_state["smc_narrative"]     = narrative
                st.session_state["smc_narrative_for"] = f"{active_sym} {active_htf}/{active_tf}"
            else:
                st.error(f"AI analysis failed: {(_ai_resp or {}).get('error', 'Core unavailable')}")

    # Display stored narrative (persists across rerenders until next Load)
    narrative = st.session_state.get("smc_narrative")
    if narrative:
        label = st.session_state.get("smc_narrative_for", "")
        st.caption(f"Last analysis: **{label}**")
        st.markdown(narrative)
