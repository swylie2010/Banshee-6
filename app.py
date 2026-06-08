"""
app.py — Banshee 5 Command Center
======================================
Pure display layer — all engine logic lives in banshee_core.py (port 8765).
This file is an HTTP client: it asks Core for pre-computed data and draws it.
No engine imports. No cache logic. No split-brain.
"""

import os
import json
import requests
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime
from pathlib import Path

from shared_data import load_providers, save_providers

# ── Core HTTP helpers ──────────────────────────────────────────────
CORE_URL = "http://127.0.0.1:8765"

def _core_get(path: str, timeout: int = 30, **params) -> dict | None:
    try:
        r = requests.get(f"{CORE_URL}{path}", params=params, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None

def _core_post(path: str, body: dict, timeout: int = 60) -> dict | None:
    try:
        r = requests.post(f"{CORE_URL}{path}", json=body, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None

def _core_post_text(path: str, body: dict, timeout: int = 90) -> str | None:
    try:
        r = requests.post(f"{CORE_URL}{path}", json=body, timeout=timeout)
        r.raise_for_status()
        return r.text
    except Exception:
        return None

def _core_delete(path: str, timeout: int = 10) -> bool:
    try:
        r = requests.delete(f"{CORE_URL}{path}", timeout=timeout)
        r.raise_for_status()
        return True
    except Exception:
        return False

def _core_online() -> bool:
    try:
        requests.get(f"{CORE_URL}/health", timeout=3)
        return True
    except Exception:
        return False

def _records_to_df(records: list) -> pd.DataFrame:
    """Reconstruct DataFrame from Core JSON records (chart rendering only)."""
    if not records:
        return pd.DataFrame()
    return pd.DataFrame(records)

# Fast TF per mode (replaces micro_engine.MODE_CONFIG access)
_MODE_FAST_TF = {"long_term": "4h", "swing": "1h", "sniper": "15m"}

# ─────────────────────────────────────────────────────────────────
# 1. PAGE SETUP & CSS INJECTION
# ─────────────────────────────────────────────────────────────────
_FAVICON_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Favicon.png")
st.set_page_config(
    page_title="Banshee 5",
    page_icon=_FAVICON_PATH if os.path.exists(_FAVICON_PATH) else "🦅",
    layout="wide",
    initial_sidebar_state="expanded",
)

# High Contrast Light Blue Aesthetic 
st.markdown("""
<style>
    /* Global Background and Fonts */
    html, body, [data-testid="stAppViewContainer"] {
        background-color: #f0f7ff !important;
        color: #0a192f !important;
        font-family: 'Segoe UI', sans-serif;
        font-size: 1.15em; 
    }
    
    [data-testid="stMain"] { background-color: #f0f7ff !important; }
    [data-testid="stSidebar"] { background-color: #ffffff !important; border-right: 2px solid #d4e4f7; }
    
    h1, h2, h3, h4 { color: #003366 !important; font-weight: 800; }
    p, span, div { color: #0a192f; }
    
    /* Contrast fix for Inputs, Selectboxes, and Buttons (No Black/Grey Muds) */
    [data-testid="stSelectbox"] > div[data-baseweb="select"] > div,
    [data-testid="stTextInput"] input,
    textarea {
        background-color: #e3f2fd !important;
        color: #000000 !important;
        border: 2px solid #0277bd !important;
        font-weight: 600;
        font-size: 1.1em;
    }
    [data-testid="baseButton-secondary"] {
        background-color: #e3f2fd !important;
        color: #001a33 !important;
        border: 2px solid #0277bd !important;
        font-weight: bold;
    }

    /* Streamlit top header bar */
    [data-testid="stHeader"] {
        background-color: #e3f2fd !important;
    }
    
    /* Streamlit code blocks and markdown backgrounds */
    code, pre {
        background-color: #e3f2fd !important;
        color: #003366 !important;
        border-radius: 6px;
    }

    /* Fix for expanded selectbox popovers (Streamlit baseweb) */
    [data-baseweb="popover"],
    ul[role="listbox"] {
        background-color: #ffffff !important;
    }
    ul[role="listbox"] li {
        color: #0a192f !important;
        font-weight: bold !important;
    }
    ul[role="listbox"] li[aria-selected="true"] {
        background-color: #cce0ff !important;
        color: #003366 !important;
    }
    ul[role="listbox"] li:hover {
        background-color: #e3f2fd !important;
        color: #003366 !important;
    }

    /* Sensor Cards for Macro */
    .sensor-card {
        background: #ffffff;
        border: 2px solid #cce0ff;
        border-radius: 12px;
        padding: 20px;
        text-align: center;
        margin-bottom: 12px;
        box-shadow: 0 4px 10px rgba(0, 0, 0, 0.05);
    }
    .sensor-card.warning { border-color: #d32f2f; background: #fff5f5; }
    .sensor-card.ok { border-color: #2e7d32; background: #f4fff4; }
    
    .sensor-value { font-family: 'Courier New', monospace; font-size: 2.2em; font-weight: bold; }
    .sensor-label { font-size: 1.1em; color: #003366; margin-top: 8px; font-weight: bold; }
    .sensor-status { font-size: 1.2em; font-weight: bold; margin-top: 6px; }
    
    /* Bright Status Colors */
    .color-green  { color: #2e7d32 !important; }
    .color-yellow { color: #d84315 !important; } 
    .color-red    { color: #d32f2f !important; }
    .color-blue   { color: #0277bd !important; }
    .color-black  { color: #000000 !important; }

    hr { border-color: #cce0ff !important; }

    /* News Badges */
    .badge-source { background: #0277bd; color: #ffffff; border-radius: 4px; padding: 2px 6px; font-size: 0.85em; font-family: monospace; font-weight: bold;}
    .badge-fresh { background: #e8f5e9; color: #2e7d32; border: 1px solid #2e7d32; border-radius: 4px; padding: 2px 6px; font-size: 0.8em; font-weight: bold; }
    .news-title { color: #003366; font-weight: bold; text-decoration: underline; font-size: 1.1em;}
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────
# 2. SESSION STATE
# ─────────────────────────────────────────────────────────────────
if "providers" not in st.session_state:
    st.session_state.providers = load_providers()
if "dismissed" not in st.session_state:
    st.session_state.dismissed = set()
if "manual_stories" not in st.session_state:
    st.session_state.manual_stories = []
if "risk_entry" not in st.session_state:
    st.session_state.risk_entry = 50.0
if "risk_stop" not in st.session_state:
    st.session_state.risk_stop = 45.0
if "risk_account" not in st.session_state:
    st.session_state.risk_account = 10000.0
if "risk_pct" not in st.session_state:
    st.session_state.risk_pct = 1.0
# Session symbol cache
if "active_symbol" not in st.session_state:
    st.session_state.active_symbol = None
if "active_mode" not in st.session_state:
    st.session_state.active_mode = "swing"
if "symbol_cache" not in st.session_state:
    st.session_state.symbol_cache = {}   # { sym: {"tfs": ..., "analysis": ..., "fetched_at": datetime} }
if "macro_cache" not in st.session_state:
    st.session_state.macro_cache = {}   # { "data": ..., "fetched_at": datetime }
# Heartbeat and schedulers now live in banshee_core.py (Core runs 24/7).
# ─────────────────────────────────────────────────────────────────
# 2a. REMOVED — scheduler migrated to banshee_core.py
# ─────────────────────────────────────────────────────────────────


# ─────────────────────────────────────────────────────────────────
# 2b. SESSION HELPERS — all data comes from Core via HTTP
# ─────────────────────────────────────────────────────────────────
def _load_symbol(symbol: str, mode: str):
    """Ask Core for OHLCV + analysis, reconstruct DataFrames, cache in session state."""
    ohlcv_resp = _core_get("/ohlcv", symbol=symbol, mode=mode) or {}
    tfs = {}
    for tf_key, records in ohlcv_resp.get("tfs", {}).items():
        tfs[tf_key] = _records_to_df(records)

    analysis = _core_get("/radar", symbol=symbol, mode=mode, output_mode="full") or {"error": "Core unavailable"}

    st.session_state.symbol_cache[symbol] = {
        "tfs":        tfs,
        "analysis":   analysis,
        "mode":       mode,
        "fetched_at": datetime.now(),
    }
    st.session_state.active_symbol = symbol

def _get_active_data():
    """Return (tfs, analysis) for the active symbol, or (None, None)."""
    sym = st.session_state.active_symbol
    if not sym or sym not in st.session_state.symbol_cache:
        return None, None
    entry = st.session_state.symbol_cache[sym]
    return entry["tfs"], entry["analysis"]

def _reanalyze_active(mode: str):
    """Re-fetch OHLCV + analysis from Core for the active symbol under a new mode."""
    sym = st.session_state.active_symbol
    if sym:
        _load_symbol(sym, mode)

def _get_macro():
    """Return macro sensors dict from Core (session-cached for the page lifetime)."""
    if st.session_state.macro_cache:
        return st.session_state.macro_cache["data"]
    resp = _core_get("/macro/sensors")
    if resp and "sensors" in resp:
        st.session_state.macro_cache = {"data": resp["sensors"], "fetched_at": datetime.now()}
        return resp["sensors"]
    # Fallback: read Core's disk cache directly if Core is temporarily unreachable
    _MACRO_DISK_CACHE = Path.home() / ".banshee_macro_cache.json"
    try:
        if _MACRO_DISK_CACHE.exists():
            return json.loads(_MACRO_DISK_CACHE.read_text(encoding="utf-8")).get("mac_data")
    except Exception:
        pass
    return None

def _force_refresh():
    """Re-fetch all loaded symbols and clear macro session cache."""
    mode = st.session_state.active_mode
    for sym in list(st.session_state.symbol_cache.keys()):
        _load_symbol(sym, mode)
    st.session_state.macro_cache = {}


# ─────────────────────────────────────────────────────────────────
# 3. SIDEBAR NAVIGATION & SETTINGS
# ─────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🦅 BANSHEE PRO 3.0")

    view_mode = st.radio(
        "### NAVIGATOR",
        ["🌦 Macro Weather", "📰 Market Intel", "🎯 Asset Radar", "🧠 Banshee Nexus", "🗺️ Structure Map", "🔮 Geo Harmonic", "🔬 Signal Lab", "⚖️ Risk Desk", "📊 Saved Results", "📒 Trade Journal", "⚙️ Settings", "📖 Manual"],
        index=0
    )
    st.markdown("---")

    # ── Symbol Switcher ───────────────────────────────────────────
    st.markdown("### SYMBOL")
    with st.form("symbol_form", clear_on_submit=True):
        sym_col1, sym_col2 = st.columns([3, 1])
        with sym_col1:
            new_sym = st.text_input("Add Symbol", placeholder="BTC/USD, NVDA…", label_visibility="collapsed")
        with sym_col2:
            load_clicked = st.form_submit_button("Load", use_container_width=True)

    if load_clicked and new_sym.strip():
        with st.spinner(f"Loading {new_sym.strip().upper()}…"):
            _load_symbol(new_sym.strip().upper(), st.session_state.active_mode)
        st.rerun()

    # Loaded symbol pills
    loaded_syms = list(st.session_state.symbol_cache.keys())
    if loaded_syms:
        for sym in loaded_syms:
            is_active = sym == st.session_state.active_symbol
            pill_cols = st.columns([5, 1])
            with pill_cols[0]:
                label = f"**{sym}**" if is_active else sym
                if st.button(label, key=f"sym_{sym}", use_container_width=True):
                    st.session_state.active_symbol = sym
                    st.rerun()
            with pill_cols[1]:
                if st.button("✕", key=f"rem_{sym}"):
                    del st.session_state.symbol_cache[sym]
                    if st.session_state.active_symbol == sym:
                        remaining = [s for s in st.session_state.symbol_cache if s != sym]
                        st.session_state.active_symbol = remaining[0] if remaining else None
                    st.rerun()
    else:
        st.caption("No symbols loaded. Enter a ticker above.")

    st.markdown("---")

    # ── Asset Presets ─────────────────────────────────────────────
    st.markdown("### PRESETS")
    presets_data = _core_get("/presets") or {}
    if presets_data:
        for preset_name, preset_syms in presets_data.items():
            pcols = st.columns([5, 1])
            with pcols[0]:
                if st.button(preset_name, key=f"preset_load_{preset_name}", use_container_width=True,
                             help=", ".join(preset_syms)):
                    with st.spinner(f"Loading {preset_name}…"):
                        for s in preset_syms:
                            _load_symbol(s, st.session_state.active_mode)
                    st.rerun()
            with pcols[1]:
                if st.button("✕", key=f"preset_del_{preset_name}"):
                    _core_delete(f"/presets/{preset_name}")
                    st.rerun()
    else:
        st.caption("No presets saved.")

    with st.expander("＋ Save current as preset"):
        with st.form("preset_save_form", clear_on_submit=True):
            preset_label = st.text_input("Preset name", placeholder="My Crypto")
            save_preset = st.form_submit_button("Save", use_container_width=True)
        if save_preset and preset_label.strip():
            current_syms = list(st.session_state.symbol_cache.keys())
            if current_syms:
                _core_post(f"/presets/{preset_label.strip()}", {"symbols": current_syms})
                st.rerun()
            else:
                st.warning("Load some symbols first.")

    st.markdown("---")

    # ── Global Mode Selector ──────────────────────────────────────
    st.markdown("### MODE")
    ui_mode_map = {"Long Term": "long_term", "Swing": "swing", "Sniper": "sniper"}
    current_ui_mode = {v: k for k, v in ui_mode_map.items()}[st.session_state.active_mode]
    selected_ui_mode = st.radio("Mode", list(ui_mode_map.keys()),
                                index=list(ui_mode_map.keys()).index(current_ui_mode),
                                label_visibility="collapsed")
    new_mode = ui_mode_map[selected_ui_mode]
    if new_mode != st.session_state.active_mode:
        st.session_state.active_mode = new_mode
        _reanalyze_active(new_mode)
        st.rerun()

    st.markdown("---")

    # ── Force Refresh ─────────────────────────────────────────────
    if st.button("🔄 Force Refresh All", use_container_width=True):
        with st.spinner("Refreshing all loaded symbols…"):
            _force_refresh()
        st.rerun()

    st.markdown("---")

    # Quick-status key indicators in sidebar
    fred_configured   = bool(st.session_state.providers.get("FRED_API", {}).get("key"))
    ai_configured     = bool(st.session_state.providers.get("AI_API", {}).get("key"))
    alpaca_configured = bool(st.session_state.providers.get("ALPACA_KEY", {}).get("key"))
    st.markdown(
        f"{'🟢' if fred_configured else '🔴'} FRED API  \n"
        f"{'🟢' if ai_configured else '🔴'} AI Key  \n"
        f"{'🟢' if alpaca_configured else '🔴'} Alpaca  \n"
        f"*Configure in ⚙️ Settings*"
    )

    st.markdown("---")

    # ── Power Off ─────────────────────────────────────────────────
    if not st.session_state.get("confirm_shutdown"):
        if st.button("⏻ Power Off", use_container_width=True):
            st.session_state.confirm_shutdown = True
            st.rerun()
    else:
        st.warning("Shut down Core + UI?")
        col_yes, col_no = st.columns(2)
        with col_yes:
            if st.button("Shut down", use_container_width=True, type="primary"):
                _core_post("/shutdown", {})
                import os as _os
                _os._exit(0)
        with col_no:
            if st.button("Cancel", use_container_width=True):
                st.session_state.confirm_shutdown = False
                st.rerun()


# ─────────────────────────────────────────────────────────────────
# 4. CHART BUILDER (For Light Theme)
# ─────────────────────────────────────────────────────────────────
def make_light_chart(df, title: str) -> go.Figure:
    if df.empty:
        fig = go.Figure()
        fig.update_layout(title=f"{title} — No Data", paper_bgcolor="#ffffff", plot_bgcolor="#ffffff")
        return fig

    plot = df.tail(150).copy()
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.75, 0.25], vertical_spacing=0.04)

    fig.add_trace(go.Candlestick(
        x=plot["timestamp"], open=plot["open"], high=plot["high"], low=plot["low"], close=plot["close"],
        name="Price", increasing_line_color="#2e7d32", decreasing_line_color="#d32f2f"
    ), row=1, col=1)

    if "ema_50" in plot.columns:
        fig.add_trace(go.Scatter(x=plot["timestamp"], y=plot["ema_50"], line=dict(color="#0277bd", width=2, shape='spline'), name="EMA 50"), row=1, col=1)
    if "ema_200" in plot.columns:
        fig.add_trace(go.Scatter(x=plot["timestamp"], y=plot["ema_200"], line=dict(color="#d84315", width=2, shape='spline'), name="EMA 200"), row=1, col=1)
    if "vwap" in plot.columns:
        fig.add_trace(go.Scatter(x=plot["timestamp"], y=plot["vwap"], line=dict(color="#6a1b9a", width=2, dash="dot", shape='spline'), name="VWAP"), row=1, col=1)

    if "stoch_k" in plot.columns:
        fig.add_trace(go.Scatter(x=plot["timestamp"], y=plot["stoch_k"], line=dict(color="#0277bd"), name="%K"), row=2, col=1)
        fig.add_trace(go.Scatter(x=plot["timestamp"], y=plot["stoch_d"], line=dict(color="#d84315", dash="dot"), name="%D"), row=2, col=1)

    fig.update_layout(
        title=dict(text=title, font=dict(color="#003366", size=22)),
        height=600, paper_bgcolor="#ffffff", plot_bgcolor="#f9fcff",
        font=dict(color="#0a192f", size=14), xaxis_rangeslider_visible=False,
        margin=dict(l=40, r=40, t=50, b=30),
    )
    fig.update_xaxes(gridcolor="#e1eeff")
    fig.update_yaxes(gridcolor="#e1eeff")
    return fig


# ─────────────────────────────────────────────────────────────────
# 5. UI VIEWS
# ─────────────────────────────────────────────────────────────────

def _render_signal_breakdown(res: dict):
    """Renders the Wily V5 expanding log of technical signals showing plain english math."""
    with st.expander("🔍 VIEW QUANTITATIVE SIGNAL BREAKDOWN (Indicator Logic)", expanded=False):
        for tf_label, breakdown in res.get("signals", {}).items():
            if not breakdown: continue
            st.markdown(f"#### Timeframe: {tf_label}")
            for item in breakdown:
                col = "green" if "BULL" in item['state'] or "OVERBOUGHT" not in item['state'] and "ACCUMULATION" in item['state'] else "red"
                if "NEUTRAL" in item['state'] or "OVERSOLD" in item['state']: col = "blue"
                
                st.markdown(f"- **{item['indicator']}**: <span style='color:{col}; font-weight:bold;'>{item['state']}</span> — {item['explanation']}</span>", unsafe_allow_html=True)
            st.markdown("---")

def _render_atr_trade_plan(res: dict):
    """Renders the Institutional ATR Trade Plan beneath the Signal Breakdown."""
    atr_plan = res.get("atr_plan")
    verdict = res.get("verdict", "")
    is_bull_verdict = verdict in ("STRONG BUY", "BUY SETUP")
    is_bear_verdict = verdict in ("STRONG SELL", "SELL SETUP")
    
    if atr_plan and (is_bull_verdict or is_bear_verdict):
        atr_val = atr_plan.get("atr", 0)
        rr      = atr_plan.get("risk_reward", 2.0)
        rr_q    = atr_plan.get("rr_quality", "")
        price   = res.get("price", 0)

        if is_bull_verdict:
            stop, target = atr_plan.get("stop_long"), atr_plan.get("target_long")
            stop_lbl, tgt_lbl = "Stop-Loss (Long)", "Target (Long)"
            stop_color, tgt_color = "#d32f2f", "#2e7d32" 
        else:
            stop, target = atr_plan.get("stop_short"), atr_plan.get("target_short")
            stop_lbl, tgt_lbl = "Stop-Loss (Short)", "Target (Short)"
            stop_color, tgt_color = "#2e7d32", "#d32f2f"

        if stop and target:
            rr_color = "#2e7d32" if rr >= 2.0 else "#d84315"
            st.markdown(f"""
            <div style="background:#ffffff; border:2px solid #0277bd; border-radius:10px;
                        padding:16px 20px; margin-top:12px; margin-bottom: 20px; box-shadow: 0 4px 10px rgba(0, 0, 0, 0.05);">
                <div style="font-size:1.1em; font-weight:bold; color:#0277bd; margin-bottom:10px;">
                    📐 ATR-Based Trade Plan
                    <span style="font-size:0.85em; font-weight:normal; color:#0a192f;">
                        (ATR = ${atr_val:,.4f})
                    </span>
                </div>
                <div style="display:flex; gap:30px; flex-wrap:wrap; margin-bottom:8px; font-size: 1.05em;">
                    <span style="color:#0a192f;">Entry:
                        <strong style="color:#000000;">${price:,.4f}</strong>
                    </span>
                    <span style="color:#0a192f;">{stop_lbl}:
                        <strong style="color:{stop_color};">${stop:,.4f}</strong>
                        <span style="font-size:0.85em; color:#0a192f; font-weight: bold;">
                            ({abs(price - stop) / price * 100:.1f}% risk)
                        </span>
                    </span>
                    <span style="color:#0a192f;">{tgt_lbl}:
                        <strong style="color:{tgt_color};">${target:,.4f}</strong>
                        <span style="font-size:0.85em; color:#0a192f; font-weight: bold;">
                            ({abs(target - price) / price * 100:.1f}% reward)
                        </span>
                    </span>
                    <span style="color:#0a192f;">Risk:Reward:
                        <strong style="color:{rr_color};">1 : {rr:.1f} — {rr_q}</strong>
                    </span>
                </div>
                <div style="color:#666; font-size:0.9em;">{atr_plan.get('stop_mode', '1.5× ATR14')} stop · Adjust to nearest key level.{"<br><span style='color:#1565c0; font-weight:600;'>🔔 " + atr_plan.get('chandelier_note', '') + "</span>" if atr_plan.get('chandelier_note') else ""}</div>
            </div>
            """, unsafe_allow_html=True)

            # ── Paper Trade button ────────────────────────────────
            direction = "long" if is_bull_verdict else "short"
            btn_key   = f"paper_{res.get('symbol', 'sym')}_{direction}"
            providers = st.session_state.get("providers", {})
            alpaca_ok = bool(providers.get("ALPACA_KEY", {}).get("key"))
            btn_label = "📋 Paper Trade" if alpaca_ok else "📋 Log Trade (no Alpaca key)"
            if st.button(btn_label, key=btn_key, type="primary"):
                import paper_trader
                _mac = _get_macro() or {}
                context = {
                    "verdict":      verdict,
                    "regime":       res.get("regime_bucket", ""),
                    "macro_regime": _mac.get("regime", ""),
                    "edge":         res.get("edge", ""),
                    "mode":         st.session_state.get("active_mode", ""),
                    "risk_score":   res.get("risk_score"),
                    "symbol":       res.get("symbol", ""),
                }
                result = paper_trader.place_paper_trade(
                    symbol       = res.get("symbol", ""),
                    direction    = direction,
                    entry_price  = price,
                    stop_price   = stop,
                    target_price = target,
                    banshee_context = context,
                )
                if result["status"] == "placed":
                    otype = result.get("order_type", "bracket")
                    if otype == "market_only":
                        st.success(f"Crypto order placed — market only (stop/target tracked in journal). Order {result['order_id'][:8]}…")
                    else:
                        st.success(f"Bracket order placed — order {result['order_id'][:8]}…")
                elif result["status"] == "logged_only":
                    err = result.get("error", "")
                    if "insufficient balance" in str(err) or "balance" in str(err).lower():
                        st.warning(
                            "Logged only — Alpaca paper account balance is $0. "
                            "Go to alpaca.markets → Paper Trading → Reset Account to restore $100k virtual balance."
                        )
                    else:
                        st.warning(f"Logged only (Alpaca error: {err})")

# ─────────────────────────────────────────────────────────────────
# SENSOR CONTEXT — calibration notes for click-to-expand cards
# ─────────────────────────────────────────────────────────────────
SENSOR_CONTEXT = {
    "vix": (
        "VIX is the CBOE Volatility Index — the 'Fear Gauge'. It measures implied volatility "
        "of S&P 500 options over the next 30 days. "
        "<b>Calibration:</b> Below 20 = calm. 20–25 = cautious. Above 25 = warning (active here). "
        "Above 35 = panic. Above 40 = historic fear event. "
        "<b>Context:</b> VIX spikes often accompany market bottoms, not tops — but a slow grind "
        "upward above 25 is a regime shift signal, not a buy signal."
    ),
    "curve": (
        "The yield curve measures the spread between 10-Year and 3-Month US Treasury rates. "
        "<b>Calibration:</b> Positive = normal (lenders rewarded for time). "
        "Negative (inverted) = warning (active here). "
        "Inversion has preceded every US recession since the 1960s, with an average lead of 12–18 months. "
        "<b>Context:</b> The warning fires on first inversion — not on recovery. Recovery (re-steepening) "
        "often coincides with recession actually beginning."
    ),
    "liquidity": (
        "Federal Reserve Net Liquidity tracks the 60-day change in the Fed's balance sheet "
        "(assets minus liabilities to Treasury and reverse repo facilities). "
        "<b>Calibration:</b> Positive = QE/injection. Stable = neutral. Below -2% = warning (active here). "
        "<b>Context:</b> Requires FRED API key. This is the water level in the pool — "
        "every asset class floats higher when the Fed injects and drops when it drains. "
        "Add your free FRED key in ⚙️ Settings."
    ),
    "btc": (
        "Bitcoin 7-Day return acts as a macro risk canary. BTC moves 24/7 with no circuit breakers, "
        "making it the fastest-reacting liquid asset. "
        "<b>Calibration:</b> Below -5% in 7 days = warning (active here). "
        "<b>Context:</b> BTC drops often precede TradFi risk-off by 1–3 weeks. "
        "Do not treat this as crypto-specific noise — it is a global liquidity sensor."
    ),
    "dxy": (
        "DXY 5-Day tracks the US Dollar Index move over the past 5 trading days. "
        "<b>Calibration:</b> Below +2% = stable. Above +2% = warning (active here). "
        "<b>Context:</b> A surging dollar is a global liquidity squeeze. "
        "Dollar debt is priced globally — when the dollar rises, everyone holding dollar-denominated "
        "debt (EM countries, crypto leverage, commodities) feels the squeeze simultaneously."
    ),
    "credit": (
        "Credit Stress compares HYG (high-yield junk bonds) vs IEF (7-10yr Treasuries). "
        "<b>Calibration:</b> HYG outperforming IEF = OK. HYG underperforming = warning (active here). "
        "<b>Context:</b> Credit markets price risk before equity markets do. "
        "When junk bonds sell off relative to safe Treasuries, institutional credit analysts "
        "are pricing in defaults and recession risk that hasn't hit equity headlines yet."
    ),
    "xle": (
        "XLE (Energy Sector ETF) vs SPY Defensive Rotation sensor. "
        "<b>Calibration:</b> XLE outperforming SPY = Safe Harbor (institutional rotation to defensive). "
        "No flight = standard risk-on positioning. "
        "<b>Context:</b> Energy outperforming the broad market in a falling tape indicates "
        "institutions are repositioning into commodity-linked inflation hedges — a classic "
        "late-cycle / early-stagflation signal."
    ),
    "skew": (
        "CBOE SKEW Index measures the implied probability of a tail-risk (black swan) event "
        "based on S&P 500 out-of-the-money put option pricing. "
        "<b>Calibration:</b> Below 130 = normal. 130–145 = elevated (smart money hedging quietly). "
        "Above 145 = Tail Risk warning (active here). "
        "<b>Context:</b> High SKEW with low VIX is the most dangerous combination — "
        "it means institutions are paying for crash protection while retail remains complacent. "
        "This pattern preceded COVID crash, 2018 Q4 selloff, and 2022 drawdown."
    ),
    "copper": (
        "Dr. Copper 5-Day tracks copper futures (HG=F) as a global growth proxy. "
        "<b>Calibration:</b> Below -3% in 5 days = growth warning (active here). -1% to -3% = soft. "
        "<b>Context:</b> Copper is used in virtually every industrial and construction process. "
        "Sustained copper drops signal that economic activity is contracting globally — "
        "this is a leading indicator for earnings revisions and GDP downgrades."
    ),
    "bonds": (
        "TLT (20+ Year Treasury ETF) 5-Day direction. "
        "<b>Calibration:</b> TLT rising = flight to safety (yields falling). "
        "TLT falling = yields rising (inflation/growth expectations or Treasury selling). "
        "<b>Context:</b> In a risk-off environment, capital should flee INTO bonds (TLT up). "
        "If bonds AND stocks are selling off together, it signals either inflation panic or "
        "a rare Treasury supply crisis — the most dangerous macro regime."
    ),
    "rotation": (
        "Sector Rotation tracks whether Utilities (XLU), Financials (XLF), or Tech (XLK) "
        "are outperforming the S&P 500 (SPY). "
        "<b>Calibration:</b> XLU outperforming = Defensive Flight (warning). "
        "XLK outperforming = Risk-On. Mixed = transition. "
        "<b>Context:</b> Sector rotation is one of the most reliable institutional positioning signals. "
        "Money does not leave the market — it rotates. Where it goes tells you what "
        "the institutional consensus thesis is for the next quarter."
    ),
    "gold": (
        "Gold (GLD) 5-Day return as a fear / inflation hedge sensor. "
        "<b>Calibration:</b> Below +1% = neutral. Above +1% = Fear Buying mode. "
        "<b>Context:</b> Gold rising fast means capital is seeking a store of value outside "
        "the financial system. This can be fear-driven (macro stress) or inflation-driven "
        "(currency debasement). Context matters — check if VIX or SKEW confirms the fear signal."
    ),
    "eth_btc": (
        "ETH vs BTC 7-Day Relative Performance — the crypto risk-on/off barometer. "
        "<b>Calibration:</b> ETH lagging BTC by > -5% = BTC Dominance warning (active here). "
        "ETH outperforming BTC by > +3% = ETH Leading (risk appetite in altcoins). "
        "<b>Context:</b> When capital flows to BTC and away from ETH, the crypto market is in "
        "a defensive posture. Institutions and whales rotate into BTC as the 'safe' crypto — "
        "this is an early warning that broad altcoin setups face headwinds even if BTC is stable. "
        "Conversely, ETH leading BTC signals genuine risk appetite: capital is flowing into "
        "higher-beta assets, confirming that long setups across crypto have macro tailwinds."
    ),
}


def render_macro_weather():
    st.markdown("<h1>🌦 Macro Weather</h1>", unsafe_allow_html=True)
    st.markdown("The global macroeconomic environment defines whether it is safe to take aggressive risk.")

    with st.spinner("Scanning global markets..."):
        _mac_resp = _core_get("/macro/sensors", timeout=45)
        if not _mac_resp or "sensors" not in _mac_resp:
            st.error("Banshee Core is offline. Start it via launch_banshee.bat.")
            return
        sensors = _mac_resp["sensors"]

    regime       = sensors.get("regime", "UNKNOWN")
    regime_level = sensors.get("regime_level", 0)
    risk_score   = sensors.get("risk_score", 0)

    # ── Kill Switch Banner ────────────────────────────────────────
    _ks = _core_get("/kill-switch/status", timeout=5)
    if _ks and _ks.get("fired"):
        n_closed  = len(_ks.get("positions_closed", []))
        fired_at  = (_ks.get("fired_at") or "")[:16].replace("T", " ")
        ks_regime = _ks.get("regime", "?")
        ks_phase  = _ks.get("domino_phase", "?")
        st.markdown(f"""
        <div style="background:#b71c1c; color:#fff; border-radius:8px; padding:18px 24px;
                    font-size:1.15em; font-weight:700; margin-bottom:20px; border:3px solid #d32f2f;">
            🚨 KILL SWITCH FIRED — CRACK DETECTED<br>
            <span style="font-size:0.85em; font-weight:400;">
                {n_closed} position(s) auto-closed at {fired_at} UTC &nbsp;·&nbsp;
                Domino phase: {ks_phase} &nbsp;·&nbsp; Regime: {ks_regime}
            </span>
        </div>
        """, unsafe_allow_html=True)

    fig = go.Figure(go.Indicator(
        mode = "gauge+number",
        value = risk_score,
        domain = {'x': [0, 1], 'y': [0, 1]},
        title = {'text': f"<span style='font-size:1.4em; font-weight:800; color:#003366'>{regime}</span>"},
        gauge = {
            'axis': {'range': [None, 100], 'tickwidth': 1, 'tickcolor': "#0a192f"},
            'bar': {'color': "#0a192f"},
            'bgcolor': "#ffffff",
            'borderwidth': 2,
            'bordercolor': "#cce0ff",
            'steps': [
                {'range': [0, 20], 'color': '#e8f5e9'},
                {'range': [20, 45], 'color': '#fff3e0'},
                {'range': [45, 75], 'color': '#ffebee'},
                {'range': [75, 100], 'color': '#ffcdd2'}],
            'threshold': {'line': {'color': "#0277bd", 'width': 4}, 'thickness': 0.75, 'value': risk_score}
        }
    ))
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font={'color': "#0a192f", 'family': "Segoe UI"},
        height=300, margin=dict(l=20, r=20, t=50, b=20)
    )
    st.plotly_chart(fig, use_container_width=True)

    st.markdown(f"""
        <div style="font-size: 1.2em; color: #0a192f; margin-top: 5px; margin-bottom: 30px; text-align: center;">
            Higher Risk Score means higher systemic stress. Wait for clear skies to size up heavily.
        </div>
    """, unsafe_allow_html=True)
    
    # Add CSS for <details> click-to-expand sensor cards
    st.markdown("""
    <style>
    details.sensor-card { cursor: pointer; }
    details.sensor-card summary { list-style: none; }
    details.sensor-card summary::-webkit-details-marker { display: none; }
    details.sensor-card[open] { border-width: 3px; }
    .sensor-context {
        margin-top: 12px;
        padding-top: 12px;
        border-top: 1px solid #cce0ff;
        font-size: 0.88em;
        color: #0a192f;
        line-height: 1.5;
        text-align: left;
    }
    .sensor-context b { color: #003366; }
    </style>
    """, unsafe_allow_html=True)

    def rcard(key, label, unit=""):
        s = sensors.get(key)
        if not s: return
        val = s['value']
        if isinstance(val, (tuple, list)): disp = " / ".join([f"{v:.1f}%" if v else "N/A" for v in val[:2]])
        elif isinstance(val, float): disp = f"{val:.2f}{unit}"
        else: disp = str(val) if val else "N/A"

        warn   = s['warning']
        status = s['status']
        c_class = "warning" if warn else "ok"
        v_class = "color-red" if warn else ("color-yellow" if status in ["SAFE HARBOR", "ELEVATED"] else "color-green")
        context = SENSOR_CONTEXT.get(key, s.get('sub', ''))

        st.markdown(f"""
        <details class="sensor-card {c_class}">
            <summary>
                <div class="sensor-value {v_class}">{disp}</div>
                <div class="sensor-label">{label}</div>
                <div class="sensor-status {v_class}">{status}</div>
                <div style="font-size:0.75em; color:#666; margin-top:4px;">▼ click for context</div>
            </summary>
            <div class="sensor-context">{context}</div>
        </details>
        """, unsafe_allow_html=True)

    c1, c2, c3, c4 = st.columns(4)
    with c1: rcard("vix", "VIX FEAR")
    with c2: rcard("curve", "YIELD CURVE 10Y-3M", "%")
    with c3: rcard("liquidity", "FED LIQUIDITY 60D", "%")
    with c4: rcard("btc", "BTC 7D CANARY", "%")

    c5, c6, c7, c8 = st.columns(4)
    with c5: rcard("dxy", "DXY DOLLAR 5D", "%")
    with c6: rcard("credit", "CREDIT STRESS (HYG/IEF)")
    with c7: rcard("xle", "XLE DEFENSIVE ROTATION")
    with c8: rcard("skew", "TAIL RISK SKEW")

    c9, c10, c11, c12 = st.columns(4)
    with c9: rcard("eth_btc", "ETH/BTC CRYPTO RISK", "%")

    # ── Contradiction Pattern Alerts ──────────────────────────────
    contradictions = sensors.get("contradictions", [])
    if contradictions:
        st.markdown("---")
        st.markdown("### ⚠️ Contradiction Patterns Detected")
        st.markdown(
            "These are gradient signals that fall below individual sensor thresholds but form "
            "a recognizable institutional footprint when combined. The AI briefing factors these in."
        )
        for c in contradictions:
            color = "#7b1fa2" if c["severity"] == "HIGH" else "#e65100"
            bg    = "#f3e5f5" if c["severity"] == "HIGH" else "#fff3e0"
            bd    = "#ce93d8" if c["severity"] == "HIGH" else "#ffcc80"
            st.markdown(f"""
            <div style="background:{bg}; border:2px solid {bd}; border-radius:10px;
                        padding:14px 18px; margin-bottom:10px;">
                <div style="font-weight:800; color:{color}; font-size:1.05em;">
                    [{c['severity']}] {c['name']}
                </div>
                <div style="color:#0a192f; margin-top:6px; line-height:1.5;">
                    {c['description']}
                </div>
            </div>
            """, unsafe_allow_html=True)

    # ── Asset Correlation Matrix (3-month rolling) ────────────────────────────
    st.markdown("---")
    st.markdown("### Asset Correlation (3-Month Rolling)")
    st.caption("How BTC, SPY, DXY, and VIX have moved relative to each other over the past 3 months. "
               "High BTC/SPY correlation means crypto is trading like a risk asset — subject to equity-driven selloffs.")
    _corr_resp = _core_get("/macro/corr")
    corr_data  = _corr_resp.get("data") if _corr_resp else None
    if corr_data:
        corr_df = pd.DataFrame(corr_data)
        def _style_corr(val):
            if val >= 0.7:
                bg = "#c8e6c9"
            elif val >= 0.3:
                bg = "#fff9c4"
            elif val <= -0.3:
                bg = "#ffcdd2"
            else:
                bg = "#f5f5f5"
            return f"background-color: {bg}; color: #0a192f; text-align: center;"

        styled = corr_df.round(2).style.applymap(_style_corr)
        st.dataframe(styled, use_container_width=True)
    else:
        st.caption("Correlation data unavailable.")

def render_asset_radar():
    st.markdown("<h1>🎯 Asset Radar</h1>", unsafe_allow_html=True)

    tfs, res = _get_active_data()
    sym = st.session_state.active_symbol
    mode = st.session_state.active_mode

    if tfs is None or res is None:
        st.info("Load a symbol using the sidebar to begin.")
        return

    if "error" in res:
        st.error(res["error"])
        return

    # Core already applies regime gating when it produces the analysis.
    fetched_at = st.session_state.symbol_cache[sym].get("fetched_at")
    mode_label = {v: k for k, v in {"Long Term": "long_term", "Swing": "swing", "Sniper": "sniper"}.items()}[mode]
    st.caption(f"Showing: **{sym}** · Mode: **{mode_label}** · Fetched: {fetched_at.strftime('%H:%M:%S') if fetched_at else '—'}")

    verd = res["verdict"]
    v_color = "#2e7d32" if "BUY" in verd else ("#d32f2f" if "SELL" in verd else "#d84315")
    v_bg = "#e8f5e9" if "BUY" in verd else ("#ffebee" if "SELL" in verd else "#fff3e0")

    asym = res.get("asymmetry", {})
    asym_html = ""
    if asym and asym.get("score", 0) >= 45:
        asym_html = f"<div style='font-size: 1.1em; color: #6a1b9a; margin-top: 10px; font-weight: bold;'>⚠️ {asym.get('label')} ({asym.get('score')}/100)</div>"

    st.markdown(f"""
    <div style="background:{v_bg}; border:3px solid {v_color}; border-radius:15px; padding:30px; text-align:center; margin-bottom: 20px;">
        <div style="font-size: 2.5em; font-weight: 800; color:{v_color};">{verd}</div>
        <div style="font-size: 1.4em; color: #0a192f; margin-top: 10px;">${res['price']:.4f}</div>
        <div style="font-size: 1.2em; color: #0a192f; margin-top: 5px;">Entry Quality: <span style="font-weight:bold;">{res['entry_quality']['quality']}</span></div>
        {asym_html}
    </div>
    """, unsafe_allow_html=True)

    regime_bucket = res.get("regime_bucket", "NEUTRAL")
    verd = res.get("verdict", "")
    _is_bullish  = "BUY"  in verd
    _is_bearish  = "SELL" in verd
    _is_waiting  = not _is_bullish and not _is_bearish
    _is_strong   = "STRONG" in verd
    _pre_signal  = bool(res.get("pre_signal"))

    def _regime_context(bucket, bullish, bearish, waiting, strong, pre):
        """Return a plain-English sentence connecting regime to the current verdict."""
        if bucket == "FEAR":
            if waiting:
                return ("Supertrend and oscillators are significantly downweighted in this fear regime. "
                        "Your WAIT has macro backing — the hesitation is justified and likely stronger than it reads.")
            elif bullish:
                if strong:
                    return ("Strong bullish reading despite fear-adjusted weights — genuine conviction, "
                            "but macro is hostile. If you trade this, size down and widen your stop.")
                return ("Bullish signals survived downweighted trend-followers — that's a harder bar to clear. "
                        "Still, macro is hostile. Tighter sizing and a close eye on your stop.")
            elif bearish:
                return ("Bearish in a fear regime — macro and micro are aligned. "
                        "Higher-probability short environment, but fear moves are volatile. Manage size.")
        elif bucket == "CAUTION":
            if waiting:
                return ("Supertrend and oscillators are mildly downweighted. "
                        "Your WAIT may partly reflect reduced signal confidence, not just a clean no-setup. "
                        "Don't override it looking for confirmation that isn't there.")
            elif bullish:
                if pre:
                    return ("PRE-SIGNAL in a caution regime — early and in uncertain conditions. "
                            "Watch for the full confirmation before committing size.")
                return ("Bullish in a caution environment. Trend-followers carry slightly less weight here — "
                        "the setup is real but treat it as lower conviction than the score suggests.")
            elif bearish:
                return ("Bearish with caution regime active — macro and micro leaning the same direction. "
                        "Reasonable short environment, but avoid overconfidence.")
        elif bucket == "TRENDING":
            if waiting:
                return ("Trend-following signals are amplified in this clean regime — "
                        "so a WAIT here is a genuine no-setup reading, not a regime artifact. "
                        "The market simply isn't offering a clean entry right now.")
            elif bullish:
                if strong:
                    return ("Strong buy in a trending regime — trend-followers are amplified and aligned. "
                            "This is the highest-quality setup environment. Macro has your back.")
                return ("Bullish in a trending regime. Supertrend and EMA carry extra weight here — "
                        "this setup has a macro tailwind behind it.")
            elif bearish:
                return ("Bearish signal in a trending regime — worth noting that trend-following "
                        "signals are amplified, so a sell here means those signals are genuinely pointing down.")
        else:  # NEUTRAL
            if waiting:
                return "No regime adjustment applied. This WAIT is based on indicators at full default weight — a clean no-setup reading."
            elif bullish:
                return "No regime adjustment. Bullish reading at default weights — take the signal at face value."
            elif bearish:
                return "No regime adjustment. Bearish reading at default weights — take the signal at face value."
        return "Regime context unavailable."

    _REGIME_STYLE = {
        "FEAR":     ("🔴", "#ffebee", "#c62828"),
        "CAUTION":  ("🟡", "#fff8e1", "#f57f17"),
        "TRENDING": ("🟢", "#e8f5e9", "#2e7d32"),
        "NEUTRAL":  ("⚪", "#f5f5f5", "#616161"),
    }
    icon, bg, fg = _REGIME_STYLE.get(regime_bucket, _REGIME_STYLE["NEUTRAL"])
    context_text = _regime_context(regime_bucket, _is_bullish, _is_bearish, _is_waiting, _is_strong, _pre_signal)
    st.markdown(
        f"<div style='background:{bg}; border-radius:8px; padding:10px 14px; "
        f"margin-bottom:12px; font-size:0.9em; color:{fg};'>"
        f"{icon} <b>Regime Gating: {regime_bucket}</b> — {context_text}"
        f"</div>",
        unsafe_allow_html=True,
    )

    # ── Asset Class Badge + Confirmation Prompt ───────────────────────────────
    from asset_profiles import ASSET_CLASS_LABELS, KNOWN_ASSET_CLASSES
    _ac       = res.get("asset_class", "default")
    _ac_label = ASSET_CLASS_LABELS.get(_ac, "⚪ Default")
    _confirmed = res.get("asset_class_confirmed", False)
    _suggested = KNOWN_ASSET_CLASSES.get(sym)   # None if totally unknown

    _badge_color = {
        "crypto_altcoin": "#1565c0", "crypto_btc": "#e65100",
        "gold_proxy":     "#f9a825", "equity":     "#2e7d32",
        "default":        "#616161",
    }.get(_ac, "#616161")

    st.markdown(
        f"<span style='background:{_badge_color}; color:white; padding:3px 10px; "
        f"border-radius:12px; font-size:0.8em; font-weight:600;'>{_ac_label}</span>"
        + ("&nbsp;&nbsp;<span style='font-size:0.78em; color:#888;'>✓ confirmed</span>" if _confirmed
           else "&nbsp;&nbsp;<span style='font-size:0.78em; color:#e65100;'>⚠ auto-suggested — confirm in ⚙️ Settings</span>" if _suggested
           else "&nbsp;&nbsp;<span style='font-size:0.78em; color:#c62828;'>⚠ unknown asset type — set in ⚙️ Settings → Asset Profiles</span>"),
        unsafe_allow_html=True,
    )

    # ETH/BTC regime notice (only shown when gate is active)
    _eb = res.get("eth_btc_regime")
    if _eb == "BTC_DOMINANCE":
        st.warning("🔶 **ETH/BTC Gate: BTC Dominance** — ETH is underperforming Bitcoin. Long signals have been suppressed. Wait for ETH/BTC to reclaim its 50-SMA before going long.")
    elif _eb == "OUTPERFORMING":
        st.success("🔷 **ETH/BTC Gate: ETH Outperforming** — ETH is showing independent strength above its 50-SMA vs BTC. Long setups are authorized.")

    st.markdown("<div style='margin-top:8px;'></div>", unsafe_allow_html=True)

    _render_signal_breakdown(res)
    _render_atr_trade_plan(res)

    fast_tf = _MODE_FAST_TF.get(mode, "1h")
    if fast_tf in tfs and not tfs[fast_tf].empty:
        fig = make_light_chart(tfs[fast_tf], f"{sym} — {fast_tf.upper()} Chart")
        st.plotly_chart(fig, use_container_width=True)

def render_banshee_nexus():
    st.markdown("<h1>🧠 Banshee Nexus</h1>", unsafe_allow_html=True)

    tfs, mic_data = _get_active_data()
    sym = st.session_state.active_symbol
    mode = st.session_state.active_mode

    if tfs is None or mic_data is None:
        st.info("Load a symbol using the sidebar to begin.")
        return

    do_ai = st.checkbox("🔮 Synthesize with AI", value=True)

    # mic_data comes from Core (already has regime gating applied)
    with st.spinner("Loading macro context..."):
        mac_data = _get_macro() or {}

    col_main, col_side = st.columns([7, 3])

    with col_main:
        if "error" in mic_data:
            st.error(mic_data["error"])
        else:
            tf_key = _MODE_FAST_TF.get(mode, "1h")
            if tf_key in tfs and not tfs[tf_key].empty:
                st.plotly_chart(make_light_chart(tfs[tf_key], f"Entry Frame: {tf_key}"), use_container_width=True)

            asym = mic_data.get("asymmetry", {})
            asym_str = f" | **Asymmetry:** {asym.get('score')}/100" if asym and asym.get("score", 0) > 0 else ""

            sw = mic_data.get("session_weight", 1.0)
            sw_labels = {2.0: "Silver Bullet", 1.5: "Killzone", 0.8: "London Close", 0.5: "Asian"}
            sw_name   = sw_labels.get(sw, "Regular")
            sw_str    = f" | **Session:** {sw_name} ×{sw}" if sw != 1.0 else ""

            st.info(f"**Verdict:** {mic_data['verdict']} | **Entry:** {mic_data['entry_quality']['quality']} | **Edge:** {mic_data['edge']}{sw_str}{asym_str}")
            _render_signal_breakdown(mic_data)
            _render_atr_trade_plan(mic_data)

    with col_side:
        st.markdown("### Macro Overlay")
        m_risk = mac_data.get("risk_score", 0)
        fig_nexus = go.Figure(go.Indicator(
            mode = "gauge+number",
            value = m_risk,
            domain = {"x": [0, 1], "y": [0, 1]},
            title = {"text": f"<span style='font-size:1.1em; font-weight:800; color:#003366'>{mac_data.get('regime', '—')}</span>"},
            gauge = {
                "axis": {"range": [None, 100], "tickwidth": 1, "tickcolor": "#0a192f"},
                "bar": {"color": "#0a192f"},
                "bgcolor": "#ffffff",
                "borderwidth": 2,
                "bordercolor": "#cce0ff",
                "steps": [
                    {"range": [0, 20], "color": "#e8f5e9"},
                    {"range": [20, 45], "color": "#fff3e0"},
                    {"range": [45, 75], "color": "#ffebee"},
                    {"range": [75, 100], "color": "#ffcdd2"}],
                "threshold": {"line": {"color": "#0277bd", "width": 3}, "thickness": 0.75, "value": m_risk}
            }
        ))
        fig_nexus.update_layout(
            paper_bgcolor="rgba(0,0,0,0)", font={"color": "#0a192f", "family": "Segoe UI"},
            height=220, margin=dict(l=10, r=10, t=30, b=10)
        )
        st.plotly_chart(fig_nexus, use_container_width=True)

        if do_ai and "error" not in mic_data:
            st.markdown("---")
            st.markdown("### AI Co-Pilot Summary")
            cfg = st.session_state.providers.get("AI_API")
            if not cfg:
                st.warning("Configure your AI API key in ⚙️ Settings.")
            else:
                if st.button("Generate AI Briefing", type="primary", use_container_width=True):
                    with st.spinner(f"Generating Synthesis via {cfg.get('type', 'AI')}..."):
                        response = _core_post_text("/ai/briefing", {
                            "symbol":        sym,
                            "mode":          mode,
                            "manual_stories": st.session_state.manual_stories,
                        })
                        if response:
                            st.markdown(f"<div style='background: #ffffff; border-left: 6px solid #0277bd; padding: 20px; font-size: 1.1em; line-height: 1.6; color: #0a192f; border-radius: 6px; box-shadow: 0 4px 10px rgba(0,0,0,0.05);'>{response.replace(chr(10), '<br>')}</div>", unsafe_allow_html=True)
                        else:
                            st.error("Core could not generate briefing — check AI key in ⚙️ Settings.")

def render_market_intel():
    # ── Newspaper CSS ─────────────────────────────────────────────────────────
    st.markdown("""
    <style>
    .predator-masthead { text-align:center; border-top:4px solid #0a192f; border-bottom:4px solid #0a192f;
        padding:8px 0 6px 0; margin-bottom:4px; }
    .predator-masthead h1 { font-family: 'Georgia', 'Times New Roman', serif !important;
        font-size:2.6em !important; letter-spacing:0.06em; color:#0a192f !important; margin:0; }
    .predator-dateline { text-align:center; font-family:'Georgia',serif; font-size:0.95em;
        color:#444; border-bottom:1px solid #0a192f; padding-bottom:6px; margin-bottom:18px; }
    .predator-top-story { background:#0a192f; color:#f0f7ff; padding:14px 20px; border-radius:4px;
        font-family:'Georgia',serif; font-size:1.15em; line-height:1.5; margin-bottom:16px; }
    .predator-top-story strong { color:#7ec8e3; }
    .predator-section-rule { border:none; border-top:2px solid #0a192f; margin:18px 0 10px 0; }
    .predator-section-head { font-family:'Georgia','Times New Roman',serif; font-size:1.0em;
        font-weight:900; letter-spacing:0.12em; text-transform:uppercase; color:#0a192f;
        border-bottom:1px solid #cce0ff; padding-bottom:4px; margin-bottom:12px; }
    .predator-card { border-left:4px solid #0277bd; background:#ffffff;
        padding:10px 14px; margin-bottom:10px; border-radius:0 4px 4px 0;
        box-shadow:0 1px 4px rgba(0,0,0,0.05); }
    .predator-card-discover { border-left-color:#e65100; }
    .predator-card-followup { border-left-color:#2e7d32; }
    .predator-card h4 { font-family:'Georgia',serif; font-size:1.0em; margin:0 0 4px 0; color:#0a192f; }
    .predator-card .lede { color:#333; font-size:0.95em; line-height:1.45; margin:0 0 6px 0; }
    .predator-card .meta { font-size:0.82em; color:#666; font-family:monospace; }
    .predator-impact { display:inline-block; background:#0a192f; color:#f0f7ff;
        font-size:0.78em; font-weight:700; padding:1px 7px; border-radius:3px; margin-right:6px; }
    .predator-impact-high { background:#c62828; }
    .predator-impact-mid  { background:#e65100; }
    .predator-impact-low  { background:#37474f; }
    .predator-tone-bull   { color:#2e7d32; font-weight:700; }
    .predator-tone-bear   { color:#c62828; font-weight:700; }
    .predator-tone-neutral{ color:#37474f; font-weight:700; }
    .predator-status-pill { display:inline-block; font-size:0.78em; padding:1px 8px;
        border-radius:10px; margin-right:6px; font-weight:600; }
    .pill-escalated { background:#ffcdd2; color:#b71c1c; }
    .pill-resolved  { background:#c8e6c9; color:#1b5e20; }
    .pill-developing{ background:#fff3e0; color:#e65100; }
    </style>
    """, unsafe_allow_html=True)

    # ── Header image ──────────────────────────────────────────────────────────
    header_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Predator Header.png")
    if os.path.exists(header_path):
        st.image(header_path, use_container_width=True)

    # ── Masthead ──────────────────────────────────────────────────────────────
    today_label = datetime.now().strftime("%A, %B %d, %Y").upper()
    st.markdown(f"""
    <div class="predator-masthead"><h1>THE DAILY PREDATOR</h1></div>
    <div class="predator-dateline">{today_label} &nbsp;·&nbsp; Powered by Banshee 5</div>
    """, unsafe_allow_html=True)

    # ── Load existing briefing or show run controls ───────────────────────────
    cfg       = st.session_state.providers.get("AI_API")
    briefing  = _core_get("/predator/briefing") or {}
    today_str = datetime.utcnow().strftime("%Y-%m-%d")
    has_today = bool(briefing.get("date") == today_str)

    col_run, col_status = st.columns([3, 7])
    with col_run:
        run_label = "🔄 Refresh Briefing" if has_today else "▶ Run Daily Predator"
        run_force = has_today
        if st.button(run_label, type="primary", use_container_width=True):
            if not cfg:
                st.warning("Configure your AI API key in ⚙️ Settings first.")
            else:
                watchlist = list(st.session_state.symbol_cache.keys())
                with st.spinner("Stage 1: Intake → Stage 2: Bouncer → Stage 3: Engine..."):
                    result = _core_post("/predator/run", {"watchlist": watchlist, "force": run_force}, timeout=180)
                    if result and "error" not in result:
                        briefing  = result
                        has_today = True
                        st.rerun()
                    else:
                        st.error(f"Pipeline error: {result.get('error', 'unknown') if result else 'Core unreachable'}")
    with col_status:
        if has_today:
            gen_at = briefing.get("generated_at", "")[:16].replace("T", " ")
            counts = briefing.get("event_counts", {})
            tone   = briefing.get("macro_tone", "NEUTRAL")
            risk   = briefing.get("risk_level", 3)
            tone_cls = "predator-tone-bull" if tone == "BULLISH" else ("predator-tone-bear" if tone == "BEARISH" else "predator-tone-neutral")
            risk_bar = "🟩" * risk + "⬜" * (5 - risk)
            st.markdown(
                f"<span style='font-size:0.9em; color:#555;'>Last run: {gen_at} UTC &nbsp;·&nbsp; "
                f"Intake: {counts.get('watchlist_intake',0)}W + {counts.get('discovered_intake',0)}D events "
                f"({counts.get('rejected',0)} filtered) &nbsp;·&nbsp; "
                f"Tone: <span class='{tone_cls}'>{tone}</span> &nbsp;·&nbsp; "
                f"Risk: {risk_bar} {risk}/5</span>",
                unsafe_allow_html=True
            )
        elif not cfg:
            st.caption("No AI key configured — go to ⚙️ Settings to add one, then run the Predator.")
        else:
            st.caption("No briefing yet for today. Click **Run Daily Predator** to generate your first one.")

    st.markdown("<hr class='predator-section-rule'>", unsafe_allow_html=True)

    if not has_today:
        # No briefing — fall back to raw RSS view
        st.markdown("<div class='predator-section-head'>Raw Intel Feed (no briefing yet)</div>", unsafe_allow_html=True)
        with st.spinner("Fetching RSS feeds..."):
            _intel_resp = _core_get("/macro/intel", timeout=45) or {}
            stories = _intel_resp.get("stories", [])
            stories = [s for s in stories if s.get("url", "") not in st.session_state.dismissed]
        for story in stories[:20]:
            age = story.get("age_hours", 0)
            is_fresh = age < 6
            fresh_tag = "<span style='background:#0277bd;color:#fff;font-size:0.75em;padding:1px 6px;border-radius:3px;margin-right:6px;'>FRESH</span>" if is_fresh else ""
            st.markdown(f"""
            <div style="margin-bottom:10px;padding-bottom:10px;border-bottom:1px solid #cce0ff;">
                <span style="font-family:monospace;font-size:0.8em;color:#666;">[{story.get('source', '?')}]</span>
                {fresh_tag}
                <a href="{story.get('url', '#')}" target="_blank"
                   style="color:#0277bd;font-weight:600;text-decoration:none;">{story.get('title', '(no title)')}</a>
                <span style="color:#999;font-size:0.85em;"> &nbsp;{age:.0f}h ago</span>
                <p style="color:#444;font-size:0.9em;margin:3px 0 0 0;">{story.get('summary', '')}</p>
            </div>
            """, unsafe_allow_html=True)
        return

    # ── TOP STORY ─────────────────────────────────────────────────────────────
    top = briefing.get("top_story", "")
    if top:
        st.markdown(
            f"<div class='predator-top-story'><strong>TOP STORY:</strong> {top}</div>",
            unsafe_allow_html=True
        )

    # ── Main 2-column layout ──────────────────────────────────────────────────
    col_left, col_right = st.columns([6, 4])

    def _impact_tag(score: int) -> str:
        cls = "predator-impact-high" if score >= 8 else ("predator-impact-mid" if score >= 5 else "predator-impact-low")
        return f"<span class='predator-impact {cls}'>{score}/10</span>"

    with col_left:
        # ── Watchlist Events ──────────────────────────────────────────────────
        wl = briefing.get("watchlist_events", [])
        st.markdown("<div class='predator-section-head'>Watchlist Events</div>", unsafe_allow_html=True)
        if wl:
            for ev in wl:
                score  = ev.get("impact_score", 0)
                hl     = ev.get("headline") or ev.get("title", "")
                lede   = ev.get("lede", "")
                source = ev.get("source", "")
                syms   = ev.get("symbols", [])
                sym_tag = f"<span style='font-size:0.8em;color:#0277bd;'>{' '.join(syms)}</span> " if syms else ""
                url    = ev.get("url", "")
                title_html = f'<a href="{url}" target="_blank" style="color:#0a192f;text-decoration:none;">{hl}</a>' if url else hl
                st.markdown(f"""
                <div class="predator-card">
                    <h4>{_impact_tag(score)}{sym_tag}{title_html}</h4>
                    <p class="lede">{lede}</p>
                    <span class="meta">[{source}]</span>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.markdown("<p style='color:#888;font-style:italic;'>No watchlist events flagged today.</p>", unsafe_allow_html=True)

        # ── AI Narrative (collapsible) ────────────────────────────────────────
        narrative = briefing.get("ai_narrative", "")
        if narrative:
            with st.expander("📜 Full Analyst Narrative", expanded=False):
                st.markdown(
                    f"<div style='font-family:Georgia,serif;font-size:0.95em;line-height:1.7;color:#222;'>"
                    f"{narrative.replace(chr(10), '<br>')}</div>",
                    unsafe_allow_html=True
                )

    with col_right:
        # ── Discovered Signals ────────────────────────────────────────────────
        ds = briefing.get("discovered_signals", [])
        st.markdown("<div class='predator-section-head'>Discovered Signals</div>", unsafe_allow_html=True)
        if ds:
            for ev in ds:
                score  = ev.get("impact_score", 0)
                hl     = ev.get("headline") or ev.get("title", "")
                lede   = ev.get("lede", "")
                reason = ev.get("reason_flagged", "")
                source = ev.get("source", "")
                url    = ev.get("url", "")
                title_html = f'<a href="{url}" target="_blank" style="color:#0a192f;text-decoration:none;">{hl}</a>' if url else hl
                lede_text = lede or reason
                st.markdown(f"""
                <div class="predator-card predator-card-discover">
                    <h4>{_impact_tag(score)}{title_html}</h4>
                    <p class="lede">{lede_text}</p>
                    <span class="meta">[{source}]</span>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.markdown("<p style='color:#888;font-style:italic;'>Nothing new outside your watchlist today.</p>", unsafe_allow_html=True)

        # ── Yesterday Followups ───────────────────────────────────────────────
        fu = briefing.get("yesterday_followups", [])
        if fu:
            st.markdown("<div class='predator-section-head' style='margin-top:16px;'>Yesterday — Followups</div>", unsafe_allow_html=True)
            for item in fu:
                status = item.get("status", "developing").lower()
                update = item.get("update", "")
                original = item.get("original", "")
                pill_cls = {"escalated": "pill-escalated", "resolved": "pill-resolved"}.get(status, "pill-developing")
                st.markdown(f"""
                <div class="predator-card predator-card-followup">
                    <h4><span class="predator-status-pill {pill_cls}">{status.upper()}</span>{original}</h4>
                    <p class="lede">{update}</p>
                </div>
                """, unsafe_allow_html=True)

    # ── User Story Injection (collapsed by default) ───────────────────────────
    st.markdown("<hr class='predator-section-rule'>", unsafe_allow_html=True)
    with st.expander("✏️  Inject Story into Nexus AI", expanded=False):
        st.markdown("Force the Banshee Nexus AI to factor in a specific headline or URL.")
        inject_text = st.text_area("Story / URL", placeholder="e.g. 'Reuters: Powell announces emergency rate cut.'", height=70, key="predator_inject")
        if st.button("Add to Banshee Collective Memory", key="predator_inject_btn"):
            if inject_text.strip():
                st.session_state.manual_stories.append(inject_text.strip())
                st.success("Appended to global context!")
                st.rerun()
    if st.session_state.manual_stories:
        st.markdown("**Active Injected Constraints:**")
        for i, ms in enumerate(st.session_state.manual_stories):
            c1, c2 = st.columns([12, 1])
            with c1: st.info(f"📍 {ms}")
            with c2:
                if st.button("✕", key=f"del_intel_{i}"):
                    st.session_state.manual_stories.pop(i)
                    st.rerun()

def render_risk_desk():
    st.markdown("<h1>⚖️ Risk Desk</h1>", unsafe_allow_html=True)
    st.markdown("Calculate exact position sizes, margin requirements, and exit targets based on mathematical R-multiples.")

    # Auto-fill from session cache if active symbol has data
    tfs, res = _get_active_data()
    sym = st.session_state.active_symbol
    if res and "error" not in res and sym:
        auto_filled = st.session_state.symbol_cache[sym].get("_risk_autofilled")
        if not auto_filled:
            st.session_state.risk_entry = float(res['price'])
            atr_plan = res.get("atr_plan")
            v = res.get("verdict", "")
            if atr_plan:
                if "BUY" in v and "stop_long" in atr_plan:
                    st.session_state.risk_stop = float(atr_plan["stop_long"])
                elif "SELL" in v and "stop_short" in atr_plan:
                    st.session_state.risk_stop = float(atr_plan["stop_short"])
                else:
                    st.session_state.risk_stop = float(res['price'] * 0.95)
            else:
                st.session_state.risk_stop = float(res['price'] * 0.95)
            st.session_state.symbol_cache[sym]["_risk_autofilled"] = True
        st.caption(f"Auto-filled from session: **{sym}** · Adjust below as needed.")
                
    st.markdown("### Trade Parameters")
    
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        acc = st.number_input("Account Size ($)", value=st.session_state.risk_account, step=100.0, format="%.2f")
    with c2:
        risk = st.number_input("Risk per Trade (%)", value=st.session_state.risk_pct, step=0.1, format="%.2f")
    with c3:
        entry = st.number_input("Entry Price ($)", value=st.session_state.risk_entry, step=0.1, format="%.4f")
    with c4:
        stop = st.number_input("Stop-Loss Price ($)", value=st.session_state.risk_stop, step=0.1, format="%.4f")
        
    st.session_state.risk_account = acc
    st.session_state.risk_pct = risk
    st.session_state.risk_entry = entry
    st.session_state.risk_stop = stop

    smc_conflicted = st.checkbox(
        "⚠️ SMC CONFLICTED — halve position size (HTF/LTF structure disagrees)",
        value=False,
        help="Tick when get_smc_structure returns a CONFLICTED alignment. Reduces conviction to 50% position size.",
    )

    plan = _core_post("/execution-plan", {
        "account_size":   acc,
        "risk_percent":   risk,
        "entry_price":    entry,
        "stop_loss":      stop,
        "smc_conflicted": smc_conflicted,
        "output_mode":    "json",
    }) or {"error": "Core unavailable"}

    if "error" in plan:
        st.warning(plan["error"])
        return

    if plan.get("confidence_note"):
        st.warning(f"**CONFIDENCE WARNING** — {plan['confidence_note']}")

    st.markdown("---")
    res1, res2, res3 = st.columns(3)

    size_label = "Units to Buy (50% — CONFLICTED)" if plan.get("smc_conflicted") else "Units to Buy"
    size_color = "#e65100" if plan.get("smc_conflicted") else "#0277bd"
    size_border = "#e65100" if plan.get("smc_conflicted") else "#0277bd"

    with res1:
        st.markdown("### 1. Position Size")
        st.markdown(f"""
        <div style="background:#ffffff; border:2px solid {size_border}; border-radius:10px; padding:20px; box-shadow: 0 4px 10px rgba(0,0,0,0.05); text-align: center;">
            <div style="font-size:1.1em; font-weight:bold; color:#666; text-transform: uppercase;">{size_label}</div>
            <div style="font-size:2.5em; font-weight:800; color:{size_color};">{plan['position_size']:,.4f}</div>
            <div style="font-size:1.0em; color:#0a192f; margin-top:5px; font-weight: bold;">Risking: ${plan['max_risk_dollars']:,.2f}</div>
            <div style="font-size:0.9em; color:#666;">Position value: ${plan['position_value']:,.2f}</div>
        </div>
        """, unsafe_allow_html=True)

    with res2:
        st.markdown("### 2. Capital Efficiency")
        table_html = "<table style='width:100%; border-collapse: collapse; font-size: 0.95em;'><tr style='border-bottom:1px solid #ccc;'><th style='text-align:left; padding:8px;'>Leverage</th><th style='text-align:right; padding:8px;'>Margin Reqd</th></tr>"
        for row in plan['capital_efficiency']:
            table_html += f"<tr style='border-bottom:1px solid #eee;'><td style='padding:6px; font-weight: bold;'>{row['leverage']}x</td><td style='text-align:right; padding:6px; font-family:monospace; color:#0a192f;'>${row['margin_required']:,.2f}</td></tr>"
        table_html += "</table>"
        st.markdown(f"<div style='background:#ffffff; border:1px solid #ccc; border-radius:10px; padding:15px; box-shadow: 0 4px 10px rgba(0,0,0,0.05);'>{table_html}</div>", unsafe_allow_html=True)
        
    with res3:
        st.markdown("### 3. Exit Strategy")
        for tgt in plan['targets']:
            c_bg = "#e8f5e9" if plan['is_long'] else "#ffebee"
            c_bd = "#2e7d32" if plan['is_long'] else "#d32f2f"
            st.markdown(f"""
            <div style="background:{c_bg}; border:1px solid {c_bd}; border-radius:10px; padding:12px; margin-bottom:10px;">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <div>
                        <div style="font-weight:bold; color:{c_bd}; text-transform: uppercase;">{tgt['r_multiple']}:1 Reward</div>
                        <div style="font-size:0.85em; color:{c_bd};">Profit: ${tgt['profit']:,.2f}</div>
                    </div>
                    <div style="font-size:1.5em; font-weight:bold; color:{c_bd}; font-family:monospace;">${tgt['price']:,.4f}</div>
                </div>
            </div>
            """, unsafe_allow_html=True)


def render_settings():
    import os, json
    st.markdown("<h1>⚙️ Settings</h1>", unsafe_allow_html=True)

    # ── Section 1: API Keys ───────────────────────────────────────
    st.markdown("## 🔑 API Configuration")

    col_f, col_a = st.columns(2)

    with col_f:
        st.markdown("### FRED API Key")
        st.markdown(
            "Free key for Fed liquidity data. Get yours at "
            "[fred.stlouisfed.org](https://fred.stlouisfed.org/docs/api/api_key.html).",
            unsafe_allow_html=True
        )
        fred_key_saved = st.session_state.providers.get("FRED_API", {}).get("key", "")
        with st.form("fred_form"):
            fred_input = st.text_input("FRED Key", value=fred_key_saved, type="password", key="settings_fred")
            if st.form_submit_button("Save FRED Key"):
                st.session_state.providers["FRED_API"] = {"key": fred_input}
                save_providers(st.session_state.providers)
                st.success("FRED key saved.")
                st.rerun()

    with col_a:
        st.markdown("### AI Brain")
        ai_choice_saved = st.session_state.providers.get("AI_API", {}).get("type", "Gemini")
        ai_key_saved    = st.session_state.providers.get("AI_API", {}).get("key", "")
        ai_model_saved  = st.session_state.providers.get("AI_API", {}).get("model", "gemini-2.5-flash")

        with st.form("ai_form"):
            ai_choice   = st.selectbox("Provider", ["Claude", "Gemini"],
                                       index=0 if ai_choice_saved == "Claude" else 1,
                                       key="settings_ai_provider")
            new_ai_key  = st.text_input("AI API Key", value=ai_key_saved, type="password", key="settings_ai_key")
            default_model = "claude-sonnet-4-6" if ai_choice_saved == "Claude" else "gemini-2.5-flash"
            new_ai_model = st.text_input("Model ID", value=ai_model_saved or default_model, key="settings_ai_model")
            if st.form_submit_button("Save AI Config"):
                st.session_state.providers["AI_API"] = {"type": ai_choice, "key": new_ai_key, "model": new_ai_model}
                save_providers(st.session_state.providers)
                st.success("AI config saved.")

    st.markdown("---")

    # ── Alpaca Data / Trading Keys ────────────────────────────────
    st.markdown("## 📈 Alpaca (Stock Data & Trading)")
    st.markdown(
        "Free API keys for stock intraday data (SPY, NVDA, etc.) — bypasses the yfinance 60-day cap. "
        "Same keys will power the Autonomous Agent. Get yours at "
        "[alpaca.markets](https://alpaca.markets/).",
        unsafe_allow_html=True
    )
    with st.form("alpaca_form"):
        col_ak, col_as = st.columns(2)
        with col_ak:
            alpaca_key_saved = st.session_state.providers.get("ALPACA_KEY", {}).get("key", "")
            alpaca_key_input = st.text_input("API Key ID", value=alpaca_key_saved, type="password", key="settings_alpaca_key")
        with col_as:
            alpaca_secret_saved = st.session_state.providers.get("ALPACA_SECRET", {}).get("key", "")
            alpaca_secret_input = st.text_input("Secret Key", value=alpaca_secret_saved, type="password", key="settings_alpaca_secret")
        if st.form_submit_button("Save Alpaca Keys"):
            st.session_state.providers["ALPACA_KEY"]    = {"key": alpaca_key_input}
            st.session_state.providers["ALPACA_SECRET"] = {"key": alpaca_secret_input}
            save_providers(st.session_state.providers)
            st.success("Alpaca keys saved.")
            st.rerun()

    st.markdown("---")

    # ── Section 2: MCP Setup Snippet ─────────────────────────────
    st.markdown("## 🔌 MCP Server Setup")
    st.markdown(
        "Copy this config into **`~/.claude/.mcp.json`** (and **`~/.mcp.json`** for some clients). "
        "The path is auto-detected from this machine."
    )
    mcp_server_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mcp_server.py")
    mcp_path_fwd    = mcp_server_path.replace("\\", "/")
    mcp_snippet     = json.dumps({
        "mcpServers": {
            "banshee-pro": {
                "command": "python",
                "args": [mcp_path_fwd]
            }
        }
    }, indent=2)
    st.code(mcp_snippet, language="json")
    st.caption(f"Detected path: `{mcp_path_fwd}`")

    st.markdown("---")

    # ── Section 3: Diagnostics ────────────────────────────────────
    st.markdown("## 🩺 System Diagnostics")
    if st.button("Run Health Check", type="primary"):
        results = []

        # Module imports
        for mod in ["macro_engine", "micro_engine", "banshee_ai", "risk_engine", "knowledge_graph", "shared_data"]:
            try:
                __import__(mod)
                results.append(("✅", mod, "importable"))
            except Exception as e:
                results.append(("❌", mod, str(e)))

        # FRED reachability
        fred_key = st.session_state.providers.get("FRED_API", {}).get("key")
        if fred_key:
            try:
                import requests
                r = requests.get(
                    "https://api.stlouisfed.org/fred/series",
                    params={"series_id": "DFF", "api_key": fred_key, "file_type": "json"},
                    timeout=5
                )
                if r.status_code == 200:
                    results.append(("✅", "FRED API", "reachable and key valid"))
                else:
                    results.append(("❌", "FRED API", f"HTTP {r.status_code}"))
            except Exception as e:
                results.append(("❌", "FRED API", str(e)))
        else:
            results.append(("⚠️", "FRED API", "no key configured — Fed liquidity sensor disabled"))

        # AI key presence
        ai_cfg = st.session_state.providers.get("AI_API", {})
        if ai_cfg.get("key"):
            results.append(("✅", f"AI Key ({ai_cfg.get('type', 'Unknown')})", "configured"))
        else:
            results.append(("⚠️", "AI Key", "not configured — Nexus AI briefing disabled"))

        # MCP server file exists
        mcp_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mcp_server.py")
        if os.path.exists(mcp_file):
            results.append(("✅", "mcp_server.py", "found"))
        else:
            results.append(("❌", "mcp_server.py", "not found at expected path"))

        for icon, name, detail in results:
            color = "#2e7d32" if icon == "✅" else ("#e65100" if icon == "⚠️" else "#d32f2f")
            st.markdown(
                f"<div style='padding:6px 10px; margin-bottom:6px; background:#f9fcff; "
                f"border-left:4px solid {color}; border-radius:4px; font-family:monospace;'>"
                f"{icon} <b>{name}</b> — {detail}</div>",
                unsafe_allow_html=True
            )

    st.markdown("---")

    # ── Section 4: Asset Profiles ─────────────────────────────────────────────
    st.markdown("## 🎛️ Asset Profiles")
    st.markdown(
        "Per-asset indicator weights calibrated from Discovery Mode results. "
        "Each weight scales how loudly that indicator speaks in live verdicts. "
        "Default (no profile) = all indicators at their standard weights, identical to pre-profile Banshee."
    )

    from asset_profiles import (get_profile, get_effective_profile, save_profile, reset_profile,
                                DEFAULT_INDICATORS, load_profiles,
                                ASSET_CLASS_OPTIONS, ASSET_CLASS_LABELS,
                                get_suggested_asset_class, ASSET_CLASS_PRESETS)

    # Symbol selector — default to the active symbol if loaded, otherwise let user type
    active_sym = st.session_state.get("active_symbol", "")
    all_saved  = list(load_profiles().keys())
    profile_sym = st.text_input(
        "Symbol to edit",
        value=active_sym,
        placeholder="BTC/USD, SPY, NVDA …",
        key="settings_profile_sym",
    ).strip().upper()

    if not profile_sym:
        st.caption("Enter a symbol above to view and edit its profile.")
    else:
        profile     = get_effective_profile(profile_sym)   # includes preset layer
        indicators  = profile["indicators"]
        is_saved    = profile_sym in all_saved

        if is_saved and profile.get("promoted_from"):
            st.caption(f"Profile source: {profile['promoted_from']}  ·  Last saved: {profile.get('updated_at', '—')}")
        elif is_saved:
            st.caption(f"Custom profile  ·  Last saved: {profile.get('updated_at', '—')}")
        else:
            suggested = get_suggested_asset_class(profile_sym)
            if suggested:
                st.info(f"No saved profile — auto-suggested type: **{ASSET_CLASS_LABELS[suggested]}**. "
                        f"Confirm by selecting below and saving.")
            else:
                st.caption("No saved profile — showing default weights. Changes here will create a custom profile.")

        # ── Asset Type ────────────────────────────────────────────────────────
        st.markdown("**Asset Type**")
        current_class = profile.get("asset_class", "default")
        new_asset_class = st.selectbox(
            "Asset Type",
            options=ASSET_CLASS_OPTIONS,
            index=ASSET_CLASS_OPTIONS.index(current_class) if current_class in ASSET_CLASS_OPTIONS else 0,
            format_func=lambda k: ASSET_CLASS_LABELS[k],
            key="settings_asset_class",
            label_visibility="collapsed",
            help=(
                "Sets the behavioral preset for this asset. "
                "🔷 Altcoin = ETH/BTC gate, 2.5× ATR stops, MFI/Fisher boosted. "
                "🟡 Gold Proxy = EMA/MACD boosted, wider stops. "
                "🟠 BTC = OBV-leading boosted, 2× ATR stops. "
                "📈 Equity = default weights, tight stops. "
                "⚪ Default = original Banshee behaviour."
            ),
        )

        # Show preset summary when class changes or is non-default
        if new_asset_class != "default":
            p = ASSET_CLASS_PRESETS[new_asset_class]
            rm = p["risk_model"]
            flags = []
            if p.get("eth_btc_gate"):  flags.append("ETH/BTC gate")
            if p.get("volume_gate"):   flags.append("volume gate")
            if rm.get("chandelier_exit"): flags.append("chandelier exit")
            st.caption(
                f"Preset: stop {rm['stop_multiplier']}× ATR · target {rm['target_multiplier']}× ATR · "
                + (", ".join(flags) if flags else "no special gates")
            )

        # ── Risk Model ────────────────────────────────────────────────────────
        st.markdown("**Risk Model**")
        st.caption("Override the preset stop/target multipliers for this symbol.")
        rm_saved = profile.get("risk_model", {})
        c_stop, c_tgt = st.columns(2)
        with c_stop:
            new_stop_mult = st.number_input(
                "Stop multiplier (× ATR14)",
                min_value=0.5, max_value=6.0, step=0.25,
                value=float(rm_saved.get("stop_multiplier", 1.5)),
                key="settings_stop_mult",
            )
        with c_tgt:
            new_tgt_mult = st.number_input(
                "Target multiplier (× ATR14)",
                min_value=1.0, max_value=12.0, step=0.5,
                value=float(rm_saved.get("target_multiplier", 3.0)),
                key="settings_tgt_mult",
            )
        new_chandelier = st.checkbox(
            "Chandelier Exit — trail stop to highest high − stop mult × ATR",
            value=bool(rm_saved.get("chandelier_exit", False)),
            key="settings_chandelier",
        )
        rr_preview = round(new_tgt_mult / new_stop_mult, 2) if new_stop_mult > 0 else 0
        st.caption(f"R:R preview: 1 : {rr_preview:.1f}")

        # ── Volume gate toggle ────────────────────────────────────────────────
        new_vgate = st.checkbox(
            "Volume Gate — suppress momentum signals on low-volume bars",
            value=profile.get("volume_gate", False),
            key="settings_vgate",
            help="When ON: RSI, Stoch RSI, MACD, OBV signals are ignored on bars where volume < 20-period average.",
        )

        # ── Indicator weight sliders + enabled toggles ────────────────────────
        st.markdown("**Indicator Weights**")
        st.caption("Weight = loudness in score_timeframe(). 0.0 = disabled, 1.0 = normal, 3.0 = shout. "
                   "Preset values are pre-filled; adjust to override.")

        new_indicators = {}
        cols_per_row   = 2
        ind_keys       = list(DEFAULT_INDICATORS.keys())
        for row_start in range(0, len(ind_keys), cols_per_row):
            row_keys = ind_keys[row_start : row_start + cols_per_row]
            cols     = st.columns(cols_per_row)
            for col, key in zip(cols, row_keys):
                ind     = indicators[key]
                label   = ind.get("label", key)
                note    = ind.get("note", "")
                with col:
                    enabled = st.checkbox(
                        f"**{label}**",
                        value=ind.get("enabled", True),
                        key=f"settings_ind_en_{key}",
                        help=note,
                    )
                    weight = st.slider(
                        "Weight",
                        min_value=0.0,
                        max_value=4.0,
                        value=float(ind.get("weight", 1.0)),
                        step=0.25,
                        key=f"settings_ind_w_{key}",
                        disabled=not enabled,
                    )
                    new_indicators[key] = {**ind, "enabled": enabled, "weight": weight}

        c_save, c_reset = st.columns([1, 1])
        with c_save:
            if st.button("💾 Save Profile", key="settings_save_profile", type="primary"):
                new_profile = {
                    **profile,
                    "asset_class":  new_asset_class,
                    "volume_gate":  new_vgate,
                    "risk_model":   {
                        "stop_multiplier":   new_stop_mult,
                        "target_multiplier": new_tgt_mult,
                        "chandelier_exit":   new_chandelier,
                    },
                    "indicators":   new_indicators,
                }
                save_profile(profile_sym, new_profile)
                st.success(f"Profile saved for **{profile_sym}**.")
                st.rerun()
        with c_reset:
            if is_saved and st.button("🔄 Reset to Defaults", key="settings_reset_profile"):
                reset_profile(profile_sym)
                st.success(f"Profile for **{profile_sym}** reset to defaults.")
                st.rerun()

    st.markdown("---")

    # ── Section 5: Daily Predator ─────────────────────────────────────────────
    st.markdown("## 📰 Daily Predator")
    st.markdown(
        "Configure the automated intelligence pipeline. "
        "Tier 1 filters for your watchlist. Tier 2 discovers what you're not watching."
    )

    pred_cfg = _core_get("/predator/config") or {}

    st.markdown("### Watchlist")
    st.caption("Assets the Bouncer uses to derive keywords for Tier 1 filtering.")
    wl_raw = st.text_area(
        "Watchlist (one symbol per line)",
        value="\n".join(pred_cfg.get("watchlist", [])),
        height=100,
        key="pred_watchlist",
        help="E.g. BTC/USD, ETH/USD, SPY, NVDA"
    )

    st.markdown("### Custom Keywords")
    st.caption("Extra words that auto-pass Tier 1 regardless of watchlist. Comma-separated.")
    ck_raw = st.text_input(
        "Keywords",
        value=", ".join(pred_cfg.get("custom_keywords", [])),
        key="pred_custom_kw",
        placeholder="e.g. jerome powell, blackrock, sui foundation"
    )

    st.markdown("### Discovery Sensitivity")
    st.caption("1 = watchlist only. 3 = standard (EVENT_TRIGGERS + flags). 5 = everything significant.")
    sensitivity = st.slider(
        "Sensitivity", min_value=1, max_value=5,
        value=pred_cfg.get("discovery_sensitivity", 3),
        step=1, key="pred_sensitivity",
    )

    with st.expander("⚙️ Advanced Thresholds", expanded=False):
        thresh = pred_cfg.get("significance_thresholds", {})
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            treasury_thr = st.number_input("Treasury Drain %", value=float(thresh.get("treasury_drain_pct", 2.0)), step=0.5, key="pred_treasury_thr")
        with c2:
            unlock_thr = st.number_input("Token Unlock % Supply", value=float(thresh.get("token_unlock_supply_pct", 10.0)), step=1.0, key="pred_unlock_thr")
        with c3:
            insider_thr = st.number_input("Insider Buy ($)", value=float(thresh.get("insider_buy_usd", 500000)), step=100000.0, format="%.0f", key="pred_insider_thr")
        with c4:
            github_thr = st.number_input("Dev Velocity Swing %", value=float(thresh.get("github_velocity_pct", 50.0)), step=5.0, key="pred_github_thr",
                                         help="Flag GitHub commit count if it changes ±this% week-over-week")

    st.markdown("### Enabled Sources")
    src_opts = [
        "rss", "sec_8k", "sec_form4", "defillama",
        "treasury_tga", "github_commits", "snapshot_dao",
    ]
    src_labels = {
        "rss":            "RSS Feeds",
        "sec_8k":         "SEC 8-K Filings",
        "sec_form4":      "SEC Form 4 (Insiders)",
        "defillama":      "DeFiLlama Token Unlocks",
        "treasury_tga":   "US Treasury TGA",
        "github_commits": "GitHub Dev Velocity",
        "snapshot_dao":   "Snapshot DAO Governance",
    }
    enabled_src = []
    src_cols = st.columns(4)
    for i, src in enumerate(src_opts):
        with src_cols[i % 4]:
            if st.checkbox(src_labels[src], value=src in pred_cfg.get("enabled_sources", src_opts), key=f"pred_src_{src}"):
                enabled_src.append(src)

    st.markdown("### Auto-Schedule")
    st.caption(
        "Core runs the Predator automatically once per day via APScheduler. "
        "Skips silently if a briefing already exists for today. "
        "Restart Core (re-run launch_banshee.bat) after changing the time."
    )
    last_brief = _core_get("/predator/briefing") or {}
    last_date  = last_brief.get("date", "")
    last_gen   = (last_brief.get("generated_at") or "")[:16]
    if last_date:
        st.info(f"Last briefing: **{last_date}** — generated {last_gen} UTC")
    else:
        st.info("No briefing on record yet. Core will run the first one at the scheduled time.")

    sa, sb = st.columns([1, 3])
    with sa:
        schedule_time = st.text_input(
            "Daily run time (HH:MM UTC)",
            value=pred_cfg.get("schedule_time", "08:00"),
            key="pred_schedule_time",
            placeholder="08:00",
        )
    with sb:
        st.caption("")   # vertical alignment spacer
        st.caption(f"Currently scheduled: **{pred_cfg.get('schedule_time', '08:00')} UTC daily**. "
                   "Change takes effect after Core restart.")

    if st.button("💾 Save Predator Config", type="primary", key="pred_save"):
        new_wl  = [s.strip().upper() for s in wl_raw.splitlines() if s.strip()]
        new_ck  = [k.strip().lower() for k in ck_raw.split(",") if k.strip()]
        sched   = schedule_time.strip() or "08:00"
        new_cfg = {
            **pred_cfg,
            "watchlist":            new_wl,
            "custom_keywords":      new_ck,
            "discovery_sensitivity": sensitivity,
            "enabled_sources":      enabled_src,
            "schedule_time":        sched,
            "significance_thresholds": {
                "treasury_drain_pct":      treasury_thr,
                "token_unlock_supply_pct": unlock_thr,
                "insider_buy_usd":         insider_thr,
                "github_velocity_pct":     github_thr,
            },
        }
        _core_post("/predator/config", {"config": new_cfg})
        st.success(f"Predator config saved. Auto-run set to {sched} UTC (restart Core to apply new time).")


def render_strategy_lab():
    import strategy_lab
    strategy_lab.render()


def render_trade_journal():
    import paper_trader
    from datetime import datetime as _dt
    st.markdown("## 📒 Trade Journal")
    st.caption("Forward signal log — every paper trade Banshee triggered, with full context.")

    # ── Sync Alpaca status ──────────────────────────────────────────
    col_sync, col_space = st.columns([1, 4])
    with col_sync:
        if st.button("🔄 Sync Alpaca", type="primary"):
            result = _core_post("/journal/sync-alpaca", {})
            n = result.get("updated", 0) if result else 0
            st.success(f"Updated {n} trade(s)." if n else "Nothing new to sync.")

    # ── Stats ───────────────────────────────────────────────────────
    stats = paper_trader.get_stats()
    if stats["total"] > 0:
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Closed Trades", stats["total"])
        c2.metric("Win Rate",      f"{stats['win_rate']}%")
        c3.metric("Avg P&L",       f"{stats['avg_pnl']:+.2f}%")
        c4.metric("Best",          f"{stats['best']:+.2f}%")
        c5.metric("Worst",         f"{stats['worst']:+.2f}%")
        st.markdown("---")

    all_trades = paper_trader.get_all_trades()
    if not all_trades:
        st.info("No paper trades yet. Hit **Paper Trade** on any BUY SETUP or STRONG BUY in the Asset Radar.")
        return

    # ── Open trades ─────────────────────────────────────────────────
    open_trades = [t for t in all_trades if t.get("status") in ("open", "logged_only")]
    if open_trades:
        st.markdown("### Open Positions")

        # Fetch live prices once for all open symbols
        live_prices: dict = {}
        price_fetched_at = _dt.now().strftime("%H:%M")
        for t in open_trades:
            sym = t["symbol"]
            if sym not in live_prices:
                live_prices[sym] = paper_trader.get_current_price(sym)

        for t in reversed(open_trades):
            ts        = _dt.fromisoformat(t["timestamp"])
            ts_short  = ts.strftime("%b %d, %H:%M")
            direction = t.get("direction", "long")
            entry     = float(t["entry_price"])
            current   = live_prices.get(t["symbol"])

            if current is not None:
                upnl = ((current - entry) / entry * 100) if direction == "long" \
                       else ((entry - current) / entry * 100)
                pnl_icon      = "🟢" if upnl > 0 else ("🔴" if upnl < 0 else "⚪")
                expander_label = (
                    f"{pnl_icon} {t['symbol']} {t['direction'].upper()} — "
                    f"{t['verdict']} — {ts_short} — {upnl:+.2f}%"
                )
            else:
                upnl           = None
                expander_label = f"📊 {t['symbol']} {t['direction'].upper()} — {t['verdict']} — {ts_short}"

            with st.expander(expander_label):
                st.caption(f"📅 Entered: {ts.strftime('%A, %B %d %Y at %H:%M')}")

                if current is not None:
                    stop   = float(t["stop_price"])
                    target = float(t["target_price"])
                    to_stop   = abs(current - stop)   / current * 100
                    to_target = abs(target - current) / current * 100
                    c1, c2, c3, c4, c5 = st.columns(5)
                    c1.metric("Entry",  f"${entry:,.4f}")
                    c2.metric("Now",    f"${current:,.4f}", delta=f"{upnl:+.2f}%")
                    c3.metric("Stop",   f"${stop:,.4f}",   delta=f"{to_stop:.1f}% away",   delta_color="off")
                    c4.metric("Target", f"${target:,.4f}", delta=f"{to_target:.1f}% away", delta_color="off")
                    c5.metric("R:R",    f"1:{t['rr']}")
                    st.caption(f"Live price as of {price_fetched_at} · ~15 min delay · Sync Alpaca to check levels")
                else:
                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("Entry",  f"${entry:,.4f}")
                    c2.metric("Stop",   f"${t['stop_price']:,.4f}")
                    c3.metric("Target", f"${t['target_price']:,.4f}")
                    c4.metric("R:R",    f"1:{t['rr']}")
                    st.caption("Live price unavailable — check manually")

                st.caption(
                    f"Regime: {t.get('regime','-')}  |  Macro: {t.get('macro_regime','-')}  |  "
                    f"Edge: {t.get('edge','-')}  |  Mode: {t.get('mode','-')}"
                )
                if t.get("alpaca_order_id"):
                    st.caption(f"Alpaca order: {t['alpaca_order_id']}")
                if t.get("alpaca_error"):
                    st.caption(f"Note: {t['alpaca_error']}")

                # Edit levels | Close trade
                form_col1, form_col2 = st.columns(2)
                with form_col1:
                    with st.form(key=f"edit_{t['id']}"):
                        st.caption("Adjust stop / target")
                        new_stop   = st.number_input("Stop",   value=float(t["stop_price"]),   format="%.4f", key=f"stop_{t['id']}")
                        new_target = st.number_input("Target", value=float(t["target_price"]), format="%.4f", key=f"tgt_{t['id']}")
                        if st.form_submit_button("Update Levels", use_container_width=True):
                            paper_trader.update_trade_levels(t["id"], new_stop, new_target)
                            st.rerun()
                with form_col2:
                    with st.form(key=f"close_{t['id']}"):
                        st.caption("Manual close")
                        exit_px = st.number_input("Exit price",
                                                  value=float(current if current else entry),
                                                  format="%.4f")
                        close_reason = st.selectbox(
                            "Exit reason",
                            options=["", "target_hit", "stop_hit", "manual_close",
                                     "wick_not_triggered", "conviction_changed",
                                     "forced_liquidation", "other"],
                            key=f"cr_{t['id']}",
                        )
                        notes   = st.text_input("Notes (optional)")
                        if st.form_submit_button("Close Trade", use_container_width=True):
                            _core_post("/journal/close", {
                                "trade_id":   t["id"],
                                "exit_price": exit_px,
                                "notes":      notes,
                                "exit_reason": close_reason if close_reason else None,
                            })
                            st.rerun()

    # ── Closed trades ───────────────────────────────────────────────
    closed_trades = [t for t in all_trades if t.get("status") == "closed"]
    if closed_trades:
        st.markdown("### Closed Trades")
        for t in reversed(closed_trades):
            pnl    = t.get("pnl_pct", 0) or 0
            icon   = "🟢" if pnl > 0 else ("🔴" if pnl < 0 else "⚪")
            ts     = _dt.fromisoformat(t["timestamp"])
            ts_fmt = ts.strftime("%b %d, %H:%M")
            label  = f"{icon} {t['symbol']} {t['direction'].upper()} — {t['verdict']} — {pnl:+.2f}% — {ts_fmt}"
            with st.expander(label):
                st.caption(f"📅 Entered: {ts.strftime('%A, %B %d %Y at %H:%M')}")
                c1, c2, c3, c4, c5 = st.columns(5)
                c1.metric("Entry",  f"${t['entry_price']:,.4f}")
                c2.metric("Exit",   f"${t.get('exit_price', 0):,.4f}")
                c3.metric("Stop",   f"${t['stop_price']:,.4f}")
                c4.metric("Target", f"${t['target_price']:,.4f}")
                c5.metric("P&L",    f"{pnl:+.2f}%")
                if t.get("exit_time"):
                    exit_ts = _dt.fromisoformat(t["exit_time"])
                    st.caption(f"📅 Closed: {exit_ts.strftime('%A, %B %d %Y at %H:%M')}")
                st.caption(
                    f"Regime: {t.get('regime','-')}  |  Macro: {t.get('macro_regime','-')}  |  "
                    f"Edge: {t.get('edge','-')}  |  Mode: {t.get('mode','-')}"
                )
                if t.get("notes"):
                    st.caption(f"Notes: {t['notes']}")

                # Outcome quality panel
                sc_icon  = "✓" if t.get("signal_correct") is True else ("✗" if t.get("signal_correct") is False else "?")
                er_label = t.get("exit_reason") or "unset"
                ann_n    = len(t.get("annotations", []))
                with st.expander(f"Outcome Quality  [{sc_icon}] exit:{er_label}  annotations:{ann_n}"):
                    with st.form(key=f"outcome_{t['id']}"):
                        q_cols = st.columns(2)
                        with q_cols[0]:
                            sc_options = {
                                "Not judged": None,
                                "✓ Direction correct": True,
                                "✗ Direction wrong":   False,
                            }
                            current_sc = t.get("signal_correct")
                            default_sc = (
                                "✓ Direction correct" if current_sc is True
                                else "✗ Direction wrong" if current_sc is False
                                else "Not judged"
                            )
                            sc_choice = st.selectbox(
                                "Was Banshee's direction correct?",
                                list(sc_options.keys()),
                                index=list(sc_options.keys()).index(default_sc),
                                key=f"sc_{t['id']}",
                            )
                        with q_cols[1]:
                            er_choices = ["(keep current)", "target_hit", "stop_hit",
                                          "manual_close", "wick_not_triggered",
                                          "conviction_changed", "forced_liquidation", "other"]
                            er_choice = st.selectbox(
                                "Exit reason",
                                er_choices,
                                index=(er_choices.index(er_label)
                                       if er_label in er_choices else 0),
                                key=f"er_{t['id']}",
                            )
                        ann_note = st.text_input("Add annotation note (optional)", key=f"ann_{t['id']}")
                        if st.form_submit_button("Save Outcome", use_container_width=True):
                            paper_trader.set_signal_outcome(
                                t["id"],
                                signal_correct=sc_options[sc_choice],
                                exit_reason=(None if er_choice == "(keep current)"
                                             else er_choice),
                                note=ann_note,
                            )
                            st.rerun()
                    if t.get("annotations"):
                        st.caption("Annotation log:")
                        for ann in t["annotations"]:
                            st.caption(f"  {ann['ts']} — {ann['note']}")

    # ── Feedback Analysis ─────────────────────────────────────────
    st.markdown("---")
    st.markdown("### 🧠 Autonomous Agent Feedback Analysis")
    st.caption("AI synthesis of judged closed trades vs Predator briefings — identifies regime blind spots and rule improvements.")
    if st.button("Run Feedback Analysis", type="primary"):
        with st.spinner("Autonomous Agent analyzing trade history..."):
            resp = _core_get("/journal/feedback-synthesis", timeout=90)
        if resp:
            m1, m2, m3 = st.columns(3)
            m1.metric("Judged Trades",     resp.get("trade_count", 0))
            m2.metric("Briefings Matched", resp.get("briefings_matched", 0))
            m3.metric("Trades Analyzed",   resp.get("trades_analyzed", 0))
            st.markdown(resp.get("narrative", "No narrative returned."))
        else:
            st.error("Core unavailable — start Banshee Core and try again.")


def _render_visual_guide():
    """Three-panel visual explainer for the Geo Harmonic + XABCD tab."""
    import plotly.graph_objects as go
    import numpy as np

    dark_bg = "#0e1117"
    grid_c  = "#1a1f2e"
    text_c  = "#e0e0e0"

    # ── Panel 1: Fibonacci Circles → Hot Zones ────────────────────────────────
    st.markdown("#### ① Fibonacci Circles — Where Arcs Cross = Hot Zone")

    fig1 = go.Figure()
    atl_cx, atl_cy = 10, 15
    ath_cx, ath_cy = 115, 92

    for fib, w, dash, show in [(0.618, 0.8, "dot", False), (1.0, 1.8, "solid", True),
                                (1.272, 0.8, "dot", False), (1.618, 0.8, "dot", False)]:
        theta = np.linspace(0.08, 1.42, 100)
        R = fib * 88
        x = atl_cx + R * np.cos(theta)
        y = atl_cy + R * np.sin(theta)
        m = (x >= 0) & (x <= 128) & (y >= 0) & (y <= 105)
        fig1.add_trace(go.Scatter(x=x[m], y=y[m], mode="lines",
            line=dict(color="#1e88e5", width=w, dash=dash),
            opacity=0.75 if dash == "solid" else 0.38,
            showlegend=show, name="ATL arcs (blue)"))

    for fib, w, dash, show in [(0.618, 0.8, "dot", False), (1.0, 1.8, "solid", True),
                                (1.272, 0.8, "dot", False), (1.618, 0.8, "dot", False)]:
        theta = np.linspace(np.pi + 0.08, np.pi * 1.5 - 0.05, 100)
        R = fib * 68
        x = ath_cx + R * np.cos(theta)
        y = ath_cy + R * np.sin(theta)
        m = (x >= 0) & (x <= 128) & (y >= 0) & (y <= 105)
        fig1.add_trace(go.Scatter(x=x[m], y=y[m], mode="lines",
            line=dict(color="#e53935", width=w, dash=dash),
            opacity=0.75 if dash == "solid" else 0.38,
            showlegend=show, name="ATH arcs (red)"))

    for p, hx in [(47, 72), (63, 83), (79, 94)]:
        fig1.add_hrect(y0=p-2.5, y1=p+2.5, fillcolor="#ff9800", opacity=0.18, line_width=0)
    fig1.add_trace(go.Scatter(x=[72, 83, 94], y=[47, 63, 79],
        mode="markers+text",
        marker=dict(color="#ff9800", size=13, symbol="circle",
                    line=dict(color="#fff3e0", width=1.2)),
        text=["Hot Zone", "Hot Zone", "Hot Zone"],
        textposition="middle right", textfont=dict(color="#ff9800", size=8),
        showlegend=True, name="Hot Zones"))

    fig1.add_vline(x=120, line_color="#66bb6a", line_width=1.8, line_dash="dash")
    fig1.add_annotation(x=120, y=102, text="TODAY", font=dict(color="#66bb6a", size=8),
                        showarrow=False, yanchor="bottom", xanchor="center")

    fig1.add_trace(go.Scatter(x=[atl_cx], y=[atl_cy], mode="markers+text",
        marker=dict(color="#1e88e5", size=11, symbol="circle"),
        text=["All-Time Low"], textposition="top right",
        textfont=dict(color="#90caf9", size=9), showlegend=False))
    fig1.add_trace(go.Scatter(x=[ath_cx], y=[ath_cy], mode="markers+text",
        marker=dict(color="#e53935", size=11, symbol="circle"),
        text=["All-Time High"], textposition="bottom left",
        textfont=dict(color="#ef9a9a", size=9), showlegend=False))

    fig1.update_layout(height=255, paper_bgcolor=dark_bg, plot_bgcolor=dark_bg,
        font=dict(color=text_c, size=10),
        xaxis=dict(visible=False, range=[-5, 132]),
        yaxis=dict(title="Price", gridcolor=grid_c, showgrid=True, range=[0, 108],
                   tickfont=dict(size=8)),
        legend=dict(orientation="h", y=-0.18, x=0, font=dict(size=9)),
        margin=dict(l=40, r=15, t=8, b=48))
    st.plotly_chart(fig1, use_container_width=True)
    st.caption(
        "**Blue arcs** expand outward from the all-time low. **Red arcs** expand from the all-time high. "
        "Banshee draws multiple arcs from each anchor — one per Fibonacci ratio (0.618, 1.0, 1.272, 1.618…). "
        "Where a blue arc and a red arc cross at the same price = a **Hot Zone** (orange dot). "
        "The more arcs that stack on a single price level, the stronger that zone's gravitational pull on price."
    )

    # ── Panel 2: XABCD pattern shapes ────────────────────────────────────────
    st.markdown("#### ② XABCD Patterns — The Five-Point Zigzag")

    col_bull, col_bear = st.columns(2)

    def _leg_label(fig, x0, y0, x1, y1, txt, color):
        fig.add_annotation(x=(x0+x1)/2, y=(y0+y1)/2, text=txt, showarrow=False,
            font=dict(color=color, size=7), bgcolor=dark_bg, opacity=0.9)

    with col_bull:
        fb = go.Figure()
        bx = [0, 2, 4, 6, 8]
        by = [100, 200, 138.2, 169.1, 121.4]
        fb.add_trace(go.Scatter(x=bx, y=by, mode="lines+markers+text",
            line=dict(color="#4caf50", width=2.5),
            marker=dict(color="#4caf50", size=9),
            text=["X", "A", "B", "C", "D"],
            textposition=["bottom right","top right","bottom center","top center","bottom center"],
            textfont=dict(color="#fff", size=13, family="Arial Black"),
            showlegend=False))
        fb.add_hrect(y0=113, y1=130, fillcolor="#4caf50", opacity=0.15, line_width=0)
        fb.add_annotation(x=9.1, y=121, text="PRZ\n(watch here)",
            font=dict(color="#4caf50", size=8), showarrow=False, xanchor="left")
        _leg_label(fb, 0,100, 2,200, "XA — base leg", "#90caf9")
        _leg_label(fb, 2,200, 4,138.2, "AB = 61.8% of XA", "#90caf9")
        _leg_label(fb, 4,138.2, 6,169.1, "BC = 50% of AB", "#90caf9")
        _leg_label(fb, 6,169.1, 8,121.4, "CD = 127% of BC", "#90caf9")
        fb.add_annotation(x=4, y=107, text="XD/XA = 78.6%  (the PRZ key)",
            showarrow=False, font=dict(color="#ffd54f", size=8))
        fb.update_layout(
            title=dict(text="Bullish — price reverses UP at D", font=dict(color="#4caf50", size=11)),
            height=300, paper_bgcolor=dark_bg, plot_bgcolor=dark_bg,
            font=dict(color=text_c),
            xaxis=dict(visible=False, range=[-0.5, 10.5]),
            yaxis=dict(visible=False, range=[88, 215]),
            margin=dict(l=5, r=85, t=32, b=5))
        st.plotly_chart(fb, use_container_width=True)

    with col_bear:
        fbe = go.Figure()
        bex = [0, 2, 4, 6, 8]
        bey = [200, 100, 161.8, 130.9, 178.6]
        fbe.add_trace(go.Scatter(x=bex, y=bey, mode="lines+markers+text",
            line=dict(color="#ef5350", width=2.5),
            marker=dict(color="#ef5350", size=9),
            text=["X", "A", "B", "C", "D"],
            textposition=["top right","bottom right","top center","bottom center","top center"],
            textfont=dict(color="#fff", size=13, family="Arial Black"),
            showlegend=False))
        fbe.add_hrect(y0=172, y1=186, fillcolor="#ef5350", opacity=0.15, line_width=0)
        fbe.add_annotation(x=9.1, y=179, text="PRZ\n(watch here)",
            font=dict(color="#ef5350", size=8), showarrow=False, xanchor="left")
        _leg_label(fbe, 0,200, 2,100, "XA — base leg", "#ef9a9a")
        _leg_label(fbe, 2,100, 4,161.8, "AB = 61.8% of XA", "#ef9a9a")
        _leg_label(fbe, 4,161.8, 6,130.9, "BC = 50% of AB", "#ef9a9a")
        _leg_label(fbe, 6,130.9, 8,178.6, "CD = 127% of BC", "#ef9a9a")
        fbe.add_annotation(x=4, y=193, text="XD/XA = 78.6%  (the PRZ key)",
            showarrow=False, font=dict(color="#ffd54f", size=8))
        fbe.update_layout(
            title=dict(text="Bearish — price reverses DOWN at D", font=dict(color="#ef5350", size=11)),
            height=300, paper_bgcolor=dark_bg, plot_bgcolor=dark_bg,
            font=dict(color=text_c),
            xaxis=dict(visible=False, range=[-0.5, 10.5]),
            yaxis=dict(visible=False, range=[88, 215]),
            margin=dict(l=5, r=85, t=32, b=5))
        st.plotly_chart(fbe, use_container_width=True)

    st.caption(
        "Price makes a specific 5-point zigzag labeled X → A → B → C → D. "
        "Each leg must be a precise Fibonacci fraction of the one before it (ratios labeled above). "
        "When all ratios check out, point **D** is the **Potential Reversal Zone (PRZ)** — "
        "the price where the whole geometric structure says 'this is where the next move starts.' "
        "The scanner on this page does this math automatically across all recent swings."
    )

    # ── Panel 3: The connection ───────────────────────────────────────────────
    st.markdown("#### ③ When Both Systems Agree — The High-Conviction Setup")

    fig3 = go.Figure()
    t = np.arange(0, 20)
    bg_price = np.array([
        155,158,162,170,175,168,160,165,158,152,
        155,150,145,148,140,135,138,150,160,168
    ], dtype=float)
    fig3.add_trace(go.Scatter(x=t, y=bg_price, mode="lines",
        line=dict(color="#546e7a", width=1.2), showlegend=False, opacity=0.5))

    fig3.add_hrect(y0=133, y1=142, fillcolor="#ff9800", opacity=0.22, line_width=0)
    fig3.add_annotation(x=19.4, y=137.5, text="Hot Zone (circles engine)",
        font=dict(color="#ff9800", size=8), showarrow=False, xanchor="right")

    xa_x = [3, 6, 9, 12, 15]
    xa_y = [175.0, 152.0, 165.0, 148.0, 137.0]
    fig3.add_trace(go.Scatter(x=xa_x, y=xa_y, mode="lines+markers+text",
        line=dict(color="#4caf50", width=2.5),
        marker=dict(color="#4caf50", size=9),
        text=["X","A","B","C","D"],
        textposition=["top right","bottom center","top center","bottom center","bottom center"],
        textfont=dict(color="#fff", size=11, family="Arial Black"),
        showlegend=True, name="XABCD Pattern"))

    fig3.add_trace(go.Scatter(x=[15,16,17,18,19], y=[137,148,157,163,168],
        mode="lines", line=dict(color="#4caf50", width=2, dash="dash"),
        showlegend=True, name="Expected reversal"))

    fig3.add_trace(go.Scatter(x=[15], y=[137], mode="markers",
        marker=dict(color="#ffd54f", size=18, symbol="star",
                    line=dict(color="#ff9800", width=2)),
        showlegend=True, name="D inside Hot Zone"))

    fig3.add_annotation(x=15, y=126,
        text="D lands inside the Hot Zone\n→ Two systems agree\n→ Highest conviction",
        showarrow=True, arrowhead=2, arrowcolor="#ffd54f", arrowwidth=1.5,
        ax=0, ay=30,
        font=dict(color="#ffd54f", size=9), bgcolor="#1a1f2e",
        bordercolor="#ffd54f", borderwidth=1, borderpad=4)

    fig3.update_layout(height=285, paper_bgcolor=dark_bg, plot_bgcolor=dark_bg,
        font=dict(color=text_c, size=10),
        xaxis=dict(visible=False, range=[-0.5, 21]),
        yaxis=dict(visible=False, range=[118, 183]),
        legend=dict(orientation="h", y=-0.22, x=0, font=dict(size=9)),
        margin=dict(l=10, r=10, t=8, b=55))
    st.plotly_chart(fig3, use_container_width=True)
    st.caption(
        "The Fibonacci Circle engine and the XABCD scanner know nothing about each other — "
        "they run completely independently. "
        "When point D of a harmonic pattern falls inside a hot zone, "
        "two separate geometric systems are pointing at the exact same price. "
        "That agreement is rare. When it happens, it's the highest-conviction reversal signal this page can produce."
    )

    st.markdown(
        "> **How to use this page:** Analyze a symbol → check the **Hot Zones table** for magnetic price levels → "
        "check the **XABCD section** for forming patterns → if a forming pattern's PRZ overlaps a hot zone, "
        "that's your setup. Bring in SMC context (order blocks, FVGs) to confirm entry."
    )


def render_geo_harmonic():
    """Geometric Harmonic Arc Analysis tab — Fibonacci circle hot zones."""
    import plotly.graph_objects as go

    st.markdown("<h1>🔮 Geometric Harmonic</h1>", unsafe_allow_html=True)
    st.caption(
        "Multi-scalar Fibonacci arcs anchored at macro ATL/ATH + local ZigZag pivots. "
        "DBSCAN-clustered intersection points reveal TradingView circle anchor coordinates."
    )

    with st.expander("📚 Visual Guide — How This Works (start here)", expanded=False):
        _render_visual_guide()

    # ── Controls (form — Enter key submits) ───────────────────────────────────
    _active_sym_default = st.session_state.get("active_symbol") or ""
    with st.form("gh_form"):
        col_sym, col_run = st.columns([5, 1])
        with col_sym:
            gh_symbol = st.text_input(
                "Symbol", value=_active_sym_default,
                placeholder="BTC/USD, NVDA, GC=F…",
                label_visibility="collapsed",
            )
        with col_run:
            gh_run = st.form_submit_button("Analyze", use_container_width=True)

        col_multi, col_arith, col_n = st.columns([2, 2, 2])
        with col_multi:
            gh_multi = st.checkbox(
                "Multi-window (144/233/377)", value=True,
                help="Run all 3 ZigZag windows; surface only levels confirmed by 2+ sources",
            )
        with col_arith:
            gh_arith = st.checkbox(
                "Arithmetic midpoint", value=False,
                help="Use (ATH+ATL)/2 instead of √(ATH×ATL) as radius endpoint",
            )
        with col_n:
            gh_n = st.selectbox(
                "Fallback window (bars)", [144, 233, 377], index=1,
                help="ZigZag lookback — only used when Multi-window is off",
            )

    # Auto-trigger when sidebar symbol differs from what's currently displayed
    _active_sym_now = (st.session_state.get("active_symbol") or "").strip().upper()
    _gh_sym_used    = st.session_state.get("gh_symbol_used", "")
    _auto_trigger   = bool(_active_sym_now and _active_sym_now != _gh_sym_used and not gh_run)

    # Determine which symbol to analyze and which settings to use
    if gh_run and gh_symbol.strip():
        _analyze_sym = gh_symbol.strip().upper()
        _use_multi   = gh_multi
        _use_arith   = gh_arith
        _use_n       = gh_n
    elif _auto_trigger:
        _analyze_sym = _active_sym_now
        _use_multi   = st.session_state.get("gh_last_multi", True)
        _use_arith   = st.session_state.get("gh_last_arith", False)
        _use_n       = st.session_state.get("gh_last_n", 233)
    else:
        _analyze_sym = None

    if not _analyze_sym and not st.session_state.get("gh_result"):
        st.info("Enter a symbol above (or load one from the sidebar) and press Enter or click Analyze.")
        return

    if _analyze_sym:
        with st.spinner(f"Computing geometric harmonics for {_analyze_sym}…"):
            resp = _core_get("/geo-harmonic", symbol=_analyze_sym, n_local=_use_n,
                             multi_window=_use_multi, arithmetic_mid=_use_arith)
            # Populate symbol_cache if needed so the chart renders without a separate sidebar load
            _cache = st.session_state.get("symbol_cache", {})
            if _analyze_sym not in _cache or not _cache[_analyze_sym].get("tfs"):
                _load_symbol(_analyze_sym, st.session_state.get("active_mode", "swing"))
        if resp is None:
            st.error("Core unavailable — start Banshee Core first.")
            return
        st.session_state["gh_result"]      = resp
        st.session_state["gh_symbol_used"] = _analyze_sym
        st.session_state["gh_last_multi"]  = _use_multi
        st.session_state["gh_last_arith"]  = _use_arith
        st.session_state["gh_last_n"]      = _use_n

    result   = st.session_state.get("gh_result")
    sym_used = st.session_state.get("gh_symbol_used", "")

    if not result:
        return

    if "error" in result:
        st.error(f"Engine error: {result['error']}")
        return

    # ── Summary metrics ────────────────────────────────────────────────────────
    price       = result.get("current_price", 0)
    sc_macro    = result.get("sc_macro", 0)
    anchors     = result.get("anchors", {})
    hot_zones   = result.get("hot_zones", [])
    arc_levels  = result.get("arc_levels_at_now", [])
    zigzag      = result.get("zigzag", [])
    n_circles   = result.get("total_circles", 0)
    n_sing      = result.get("total_singularities", 0)
    n_local_used = result.get("n_local", gh_n)

    atl          = anchors.get("ATL", {})
    ath          = anchors.get("ATH", {})
    radius_ep    = result.get("radius_endpoint", {})
    is_multi     = result.get("multi_window", False)
    is_arith     = result.get("arithmetic_mid", False)

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Current Price", f"{price:,.4f}")
    m2.metric("ATL Anchor", f"{atl.get('price', 0):,.4f}", delta=f"{atl.get('ts','')[:10]}")
    m3.metric("ATH Anchor", f"{ath.get('price', 0):,.4f}", delta=f"{ath.get('ts','')[:10]}")
    m4.metric("Sc (macro)", f"{sc_macro:.6f}", help="Log-price units per bar — the geometric squaring constant")
    m5.metric(
        f"Radius endpoint ({'arith' if is_arith else 'geo'})",
        f"{radius_ep.get('price', 0):,.4f}",
        delta=radius_ep.get("ts", ""),
        help="Shared circle anchor (√(ATH×ATL) or midpoint) — paste as TradingView circle endpoint",
    )

    mode_label = "Multi-window (144/233/377)" if is_multi else f"{n_local_used} bars"
    st.markdown(
        f"<small>Circles: **{n_circles}** &nbsp;|&nbsp; "
        f"Raw singularities: **{n_sing}** &nbsp;|&nbsp; "
        f"Hot zones (clustered): **{len(hot_zones)}** &nbsp;|&nbsp; "
        f"Arc levels at now: **{len(arc_levels)}** &nbsp;|&nbsp; "
        f"Mode: **{mode_label}**</small>",
        unsafe_allow_html=True,
    )

    # ── Callouts ──────────────────────────────────────────────────────────────
    _callouts = []

    # Price proximity — within 2.5% of a hot zone
    for _i, _hz in enumerate(hot_zones[:10], 1):
        _pct = abs(_hz["dist_pct"])
        if _pct <= 2.5:
            _dirn = "above" if _hz["dist_pct"] > 0 else "below"
            _kind = {"floor": "support", "ceiling": "resistance", "mixed": "inflection"}.get(
                _hz.get("bias", "mixed"), "inflection")
            _callouts.append(("warn",
                f"Price within {_pct:.1f}% of zone #{_i} — "
                f"{_kind} {_dirn} at {_hz['price']:,.4f}"))

    # Macro-Macro tier present (weight ≥ 8)
    _mm = [hz for hz in hot_zones if hz["weight"] >= 8]
    if _mm:
        _mm_prices = " / ".join(f"{hz['price']:,.4f}" for hz in _mm[:2])
        _callouts.append(("info",
            f"Macro-Macro tier at {_mm_prices} — ATL × ATH arcs converge here, "
            "highest structural conviction"))

    # Clean air gap straddling current price (> 6%)
    _sz = sorted(hot_zones[:10], key=lambda z: z["price"])
    for _k in range(len(_sz) - 1):
        _lo_z, _hi_z = _sz[_k], _sz[_k + 1]
        if _lo_z["price"] < price < _hi_z["price"]:
            _gap_pct = (_hi_z["price"] - _lo_z["price"]) / price * 100
            if _gap_pct > 6:
                _callouts.append(("info",
                    f"Clean air between {_lo_z['price']:,.4f} – {_hi_z['price']:,.4f} "
                    f"({_gap_pct:.1f}% wide) — expect faster movement within this band"))
            break

    # Bias dominance in top 5
    _top5 = hot_zones[:5]
    _ceils = sum(1 for z in _top5 if z.get("bias") == "ceiling")
    _floors = sum(1 for z in _top5 if z.get("bias") == "floor")
    if _ceils >= 4:
        _callouts.append(("warn",
            f"{_ceils}/5 highest-weight zones are ceiling-biased — "
            "structural resistance dominates this range"))
    elif _floors >= 4:
        _callouts.append(("info",
            f"{_floors}/5 highest-weight zones are floor-biased — "
            "structural support dominates this range"))

    # All zones above or all below (unusual)
    _above = [z for z in hot_zones[:10] if z["dist_pct"] > 0]
    _below = [z for z in hot_zones[:10] if z["dist_pct"] <= 0]
    if not _above and _below:
        _callouts.append(("warn",
            "Price is above all detected hot zones — no structural overhead detected"))
    elif not _below and _above:
        _callouts.append(("warn",
            "Price is below all detected hot zones — no structural support floor detected"))

    if _callouts:
        for _lvl, _msg in _callouts:
            if _lvl == "warn":
                st.warning(_msg, icon="⚠")
            else:
                st.info(_msg, icon="ℹ")

    # ── Chart ──────────────────────────────────────────────────────────────────
    # Use daily OHLCV from session_state if available, otherwise show levels only
    tfs_cache = st.session_state.get("symbol_cache", {}).get(sym_used, {}).get("tfs", {})
    df_chart  = tfs_cache.get("1d") if tfs_cache else None

    fig = go.Figure()

    if df_chart is not None and not df_chart.empty:
        # Show last 300 bars max
        df_plot = df_chart.tail(300).copy()
        ts_col  = df_plot["timestamp"] if "timestamp" in df_plot.columns else df_plot.index

        fig.add_trace(go.Candlestick(
            x=ts_col,
            open=df_plot["open"],
            high=df_plot["high"],
            low=df_plot["low"],
            close=df_plot["close"],
            increasing_line_color="#2e7d32",
            decreasing_line_color="#c62828",
            increasing_fillcolor="#81c784",
            decreasing_fillcolor="#ef9a9a",
            name="Price",
            showlegend=False,
        ))

        # ZigZag pivot markers (active window only)
        active_zz = [z for z in zigzag if z.get("active")]
        zz_highs  = [z for z in active_zz if z["type"] == "high"]
        zz_lows   = [z for z in active_zz if z["type"] == "low"]

        if zz_highs:
            # Map bar indices to timestamps
            zz_h_ts  = []
            zz_h_pr  = []
            for z in zz_highs:
                bar_i = z["bar"]
                if 0 <= bar_i < len(df_chart):
                    ts_val = (df_chart["timestamp"].iloc[bar_i]
                              if "timestamp" in df_chart.columns
                              else df_chart.index[bar_i])
                    if ts_val in (ts_col.values if hasattr(ts_col, "values") else list(ts_col)):
                        zz_h_ts.append(ts_val)
                        zz_h_pr.append(z["price"] * 1.002)
            if zz_h_ts:
                fig.add_trace(go.Scatter(
                    x=zz_h_ts, y=zz_h_pr,
                    mode="markers+text",
                    marker=dict(symbol="triangle-down", size=12, color="#ff6f00"),
                    text=[f"ZH {n_local_used}"] * len(zz_h_ts),
                    textposition="top center",
                    textfont=dict(size=8, color="#ff6f00"),
                    name=f"ZigZag High ({n_local_used})",
                ))

        if zz_lows:
            zz_l_ts  = []
            zz_l_pr  = []
            for z in zz_lows:
                bar_i = z["bar"]
                if 0 <= bar_i < len(df_chart):
                    ts_val = (df_chart["timestamp"].iloc[bar_i]
                              if "timestamp" in df_chart.columns
                              else df_chart.index[bar_i])
                    if ts_val in (ts_col.values if hasattr(ts_col, "values") else list(ts_col)):
                        zz_l_ts.append(ts_val)
                        zz_l_pr.append(z["price"] * 0.998)
            if zz_l_ts:
                fig.add_trace(go.Scatter(
                    x=zz_l_ts, y=zz_l_pr,
                    mode="markers+text",
                    marker=dict(symbol="triangle-up", size=12, color="#1565c0"),
                    text=[f"ZL {n_local_used}"] * len(zz_l_ts),
                    textposition="bottom center",
                    textfont=dict(size=8, color="#1565c0"),
                    name=f"ZigZag Low ({n_local_used})",
                ))

        x_range = [ts_col.iloc[0], ts_col.iloc[-1]]
    else:
        # No OHLCV — just use a numeric x-axis
        x_range = [0, 1]
        st.info(
            f"Load **{sym_used}** from the sidebar first to see the candlestick chart. "
            "Hot zones are shown below regardless."
        )

    # Hot zone horizontal lines (top 10)
    _weight_color = lambda w: (
        "#f44336" if w >= 8 else
        "#ff9800" if w >= 5 else
        "#ffc107" if w >= 3 else
        "#78909c"
    )
    _weight_label = lambda w: (
        "[III] Macro-Macro" if w >= 8 else
        "[II] Macro-Local"  if w >= 5 else
        "[I] Local-Local"   if w >= 3 else
        "Arc level"
    )

    _bias_sym = {"floor": "▼", "ceiling": "▲", "mixed": "◈"}
    for hz in hot_zones[:10]:
        color = _weight_color(hz["weight"])
        d     = hz["dist_pct"]
        bs    = _bias_sym.get(hz.get("bias", "mixed"), "◈")
        label = f"{bs} {hz['price']:,.4f} ({'+' if d >= 0 else ''}{d:.1f}%)"
        if df_chart is not None and not df_chart.empty:
            fig.add_hline(
                y=hz["price"],
                line_color=color,
                line_width=1.4,
                line_dash="dot",
                annotation_text=label,
                annotation_position="right",
                annotation_font=dict(size=9, color=color),
            )
        else:
            fig.add_shape(
                type="line", x0=0, x1=1, y0=hz["price"], y1=hz["price"],
                line=dict(color=color, width=1.4, dash="dot"),
            )

    fig.update_layout(
        height=520,
        paper_bgcolor="#0e1117",
        plot_bgcolor="#0e1117",
        font=dict(color="#e0e0e0", size=11),
        xaxis=dict(
            gridcolor="#1e2130", showgrid=True,
            rangeslider=dict(visible=False),
        ),
        yaxis=dict(gridcolor="#1e2130", showgrid=True),
        legend=dict(orientation="h", y=1.04, x=0),
        margin=dict(l=0, r=60, t=30, b=0),
        title=dict(text=f"{sym_used} — Geometric Harmonic Hot Zones", font=dict(size=14)),
    )

    st.plotly_chart(fig, use_container_width=True)

    # ── Hot Zones table ────────────────────────────────────────────────────────
    st.markdown("### Hot Zones (Ranked by Confluence Weight)")
    if hot_zones:
        _bsym = {"floor": "▼ floor", "ceiling": "▲ ceiling", "mixed": "◈ mixed"}
        hz_rows = []
        for i, hz in enumerate(hot_zones, 1):
            d    = hz["dist_pct"]
            wlbl = _weight_label(hz["weight"])
            srcs = ", ".join(hz.get("sources", []))
            hz_rows.append({
                "#":          i,
                "Price":      f"{hz['price']:,.4f}",
                "Distance":   f"{'+' if d >= 0 else ''}{d:.2f}%",
                "Bias":       _bsym.get(hz.get("bias", "mixed"), "◈ mixed"),
                "Weight":     hz["weight"],
                "Confluence": hz["count"],
                "Tier":       wlbl,
                "Sources":    srcs,
            })
        import pandas as _pd
        hz_df = _pd.DataFrame(hz_rows).set_index("#")
        st.dataframe(hz_df, use_container_width=True)
    else:
        st.info("No clustered hot zones found — try disabling Multi-window or a symbol with more history.")

    # ── Arc levels & ZigZag detail ─────────────────────────────────────────────
    with st.expander("Arc Levels at Current Bar", expanded=False):
        if arc_levels:
            _bsym2 = {"floor": "▼", "ceiling": "▲", "mixed": "◈"}
            al_rows = []
            for a in arc_levels[:20]:
                d = a["dist_pct"]
                al_rows.append({
                    "Price":    f"{a['price']:,.4f}",
                    "Distance": f"{'+' if d >= 0 else ''}{d:.2f}%",
                    "Bias":     _bsym2.get(a.get("bias", "mixed"), "◈"),
                    "Type":     a["type"],
                    "Source":   a["label"],
                    "Fib":      a["fib"],
                })
            import pandas as _pd2
            st.dataframe(_pd2.DataFrame(al_rows), use_container_width=True)
        else:
            st.write("No arc levels within price bounds.")

    with st.expander("ZigZag Pivots", expanded=False):
        if zigzag:
            zz_rows = []
            for z in zigzag:
                zz_rows.append({
                    "Window":  z["window"],
                    "Type":    z["type"].upper(),
                    "Price":   f"{z['price']:,.4f}",
                    "Bar":     z["bar"],
                    "Date":    z["ts"][:10],
                    "Active":  "✓" if z.get("active") else "",
                })
            import pandas as _pd3
            st.dataframe(_pd3.DataFrame(zz_rows), use_container_width=True)
        else:
            st.write("No ZigZag pivots computed.")

    # ── TradingView anchor guide ───────────────────────────────────────────────
    st.markdown("---")
    st.markdown("**TradingView Circle Coordinates**")
    st.caption(
        "Fibonacci Circles tool: set Circle A at ATL, Circle B at ATH. "
        "The shared endpoint (radius endpoint above) is where both circles meet today — "
        "paste that date + price as the endpoint for each circle."
    )
    anchor_col1, anchor_col2, anchor_col3 = st.columns(3)
    with anchor_col1:
        st.markdown(
            f"**Circle A — ATL (bottom-up)**  \n"
            f"Date: `{atl.get('ts','')[:10]}`  \n"
            f"Price: `{atl.get('price', 0):,.4f}`"
        )
    with anchor_col2:
        st.markdown(
            f"**Circle B — ATH (top-down)**  \n"
            f"Date: `{ath.get('ts','')[:10]}`  \n"
            f"Price: `{ath.get('price', 0):,.4f}`"
        )
    with anchor_col3:
        _re = result.get("radius_endpoint", {})
        st.markdown(
            f"**Shared endpoint ({_re.get('method','geo')})**  \n"
            f"Date: `{_re.get('ts','')}`  \n"
            f"Price: `{_re.get('price', 0):,.4f}`"
        )

    # ── XABCD Harmonic Pattern Scanner ────────────────────────────────────────
    st.markdown("---")
    st.markdown("### XABCD Harmonic Patterns")
    st.caption(
        "Gartley · Bat · Butterfly · Crab · Shark · 5-0 — scanned via percentage-reversal "
        "ZigZag + Fibonacci ratio validation (±5% tolerance)."
    )

    with st.form("xabcd_form"):
        xc1, xc2 = st.columns([3, 1])
        with xc1:
            xabcd_pct = st.slider(
                "ZigZag reversal %", min_value=1, max_value=10, value=3,
                help="Minimum % reversal to lock in a new swing pivot (3% = default for daily crypto)",
            )
        with xc2:
            xabcd_run = st.form_submit_button("Scan Patterns", use_container_width=True)

    # Auto-trigger when symbol changes (reuse the sym_used from geo-harmonic)
    _xabcd_sym_used = st.session_state.get("xabcd_symbol_used", "")
    _xabcd_auto     = bool(sym_used and sym_used != _xabcd_sym_used)

    if xabcd_run or _xabcd_auto:
        _scan_pct = xabcd_pct / 100.0
        with st.spinner(f"Scanning XABCD patterns for {sym_used}…"):
            xabcd_resp = _core_get("/xabcd", symbol=sym_used, pct=_scan_pct)
        if xabcd_resp is None:
            st.error("Core unavailable — start Banshee Core first.")
        elif "error" in xabcd_resp:
            st.error(f"XABCD scan error: {xabcd_resp['error']}")
        else:
            st.session_state["xabcd_result"]      = xabcd_resp
            st.session_state["xabcd_symbol_used"] = sym_used
            st.session_state["xabcd_pct_used"]    = _scan_pct

    xabcd_result = st.session_state.get("xabcd_result")

    if xabcd_result and not xabcd_result.get("error"):
        xabcd_confirmed = xabcd_result.get("confirmed", [])
        xabcd_forming   = xabcd_result.get("forming",   [])
        xabcd_npiv      = xabcd_result.get("n_pivots",  0)
        xabcd_pct_used  = st.session_state.get("xabcd_pct_used", 0.03)

        st.markdown(
            f"<small>ZigZag pivots found: **{xabcd_npiv}** &nbsp;|&nbsp; "
            f"Confirmed: **{len(xabcd_confirmed)}** &nbsp;|&nbsp; "
            f"Forming: **{len(xabcd_forming)}** &nbsp;|&nbsp; "
            f"Threshold: **{xabcd_pct_used*100:.1f}%**</small>",
            unsafe_allow_html=True,
        )

        # Forming patterns — highlighted callouts
        if xabcd_forming:
            st.markdown("**Forming Patterns (watch for D)**")
            for fp in xabcd_forming:
                dirn_icon = "▲" if fp["direction"] == "bullish" else "▼"
                lo, hi    = fp.get("prz_lo"), fp.get("prz_hi")
                prz_str   = (f"{lo:,.4f} – {hi:,.4f}" if lo and hi else "PRZ unknown")
                dist      = fp.get("prz_dist_pct")
                dist_str  = f" ({'+' if (dist or 0) >= 0 else ''}{dist:.1f}% from current)" if dist is not None else ""
                st.info(
                    f"{dirn_icon} **{fp['pattern']}** ({fp['direction']}) — "
                    f"PRZ: **{prz_str}**{dist_str}  |  "
                    f"conf={fp['confidence']:.2f}  |  C was {fp['c_bars_ago']} bars ago  \n"
                    f"X={fp['points']['X']['price']:,.4f}  "
                    f"A={fp['points']['A']['price']:,.4f}  "
                    f"B={fp['points']['B']['price']:,.4f}  "
                    f"C={fp['points']['C']['price']:,.4f}",
                    icon="🎯",
                )

        # Confirmed patterns — table
        if xabcd_confirmed:
            st.markdown("**Confirmed Patterns**")
            import pandas as _pd_xabcd
            xabcd_rows = []
            for cp in xabcd_confirmed:
                d_pt  = cp["points"]["D"]
                r     = cp["ratios"]
                tent  = " ⏳" if cp.get("d_tentative") else ""
                dist  = cp["dist_pct"]
                xabcd_rows.append({
                    "Pattern":    cp["pattern"] + tent,
                    "Direction":  ("▲ bullish" if cp["direction"] == "bullish" else "▼ bearish"),
                    "PRZ (D)":    f"{cp['prz']:,.4f}",
                    "Dist %":     f"{'+' if dist >= 0 else ''}{dist:.1f}%",
                    "Bars Ago":   cp["bars_ago"],
                    "Confidence": cp["confidence"],
                    "AB/XA":      r.get("ab_xa", "—"),
                    "BC/AB":      r.get("bc_ab", "—"),
                    "XD/XA":      r.get("xd_xa", "—"),
                    "CD/BC":      r.get("cd_bc", "—"),
                    "D Date":     d_pt["ts"],
                })
            xabcd_df = _pd_xabcd.DataFrame(xabcd_rows)
            st.dataframe(xabcd_df, use_container_width=True, hide_index=True)
        elif not xabcd_forming:
            st.info(
                "No harmonic patterns detected in the recent swing structure. "
                "Try lowering the ZigZag % to find more pivots, or the asset "
                "may not be in a harmonic configuration currently.",
                icon="ℹ",
            )

    elif not xabcd_result:
        st.caption("Click **Scan Patterns** above — or it auto-runs when you analyze a new symbol.")

    # ── Legend ─────────────────────────────────────────────────────────────────
    with st.expander("How to read this table", expanded=False):
        st.markdown("""
**Bias symbols**

| Symbol | Meaning |
|--------|---------|
| ▲ ceiling | ATH-sourced resistance. Price may reject on approach from below. |
| ▼ floor | ATL-sourced support. Price may find buyers here. |
| ◈ mixed | ATH and ATL arcs agree on price, disagree on direction. Watch for price action confirmation — these are often the most interesting inflection zones. |

**Tiers**

| Tier | What it means | When to weight it |
|------|---------------|-------------------|
| Macro-Macro | ATL circle × ATH circle crossing | Rarest. Both macro anchors confirm the same level. Treat as structurally significant even without other confluence. |
| Macro-Local | Macro anchor × recent swing pivot | Strong. Two independent timeframes agreeing on a price. |
| Local-Local | Two ZigZag windows agree | Structural, but lower conviction. Confirm with SMC before acting. |

**Columns**

- **Weight** — sum of all contributing signal strengths at this cluster. Higher weight = more arcs and intersections stacking at this price.
- **n** — number of independent signals within 0.5% of this level. Think of it as how many different arguments land on the same number.
- **Sources** — which circle anchors contributed. `macro_atl`/`macro_ath` = absolute history arcs. `local_144/233/377` = recent swing-pivot arcs by lookback window.

*These are mathematical confluences, not trade signals. Most useful when price is approaching a level — the arc shape tells you whether it's arriving from the expected direction.*
""")



def render_manual():
    import os
    st.markdown("<h1>📖 Banshee Pro Manual</h1>", unsafe_allow_html=True)
    manual_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "MANUAL.md")
    playbook_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "PLAYBOOK.md")
    tab_manual, tab_playbook = st.tabs(["📘 User Manual", "📊 Signal Playbook"])
    with tab_manual:
        if os.path.exists(manual_path):
            with open(manual_path, "r", encoding="utf-8") as f:
                st.markdown(f.read())
        else:
            st.error(f"MANUAL.md not found at {manual_path}")
    with tab_playbook:
        if os.path.exists(playbook_path):
            with open(playbook_path, "r", encoding="utf-8") as f:
                st.markdown(f.read())
        else:
            st.error(f"PLAYBOOK.md not found at {playbook_path}")


# ─────────────────────────────────────────────────────────────────
# 6. ROUTER
# ─────────────────────────────────────────────────────────────────
if view_mode == "🌦 Macro Weather":
    render_macro_weather()
elif view_mode == "🎯 Asset Radar":
    render_asset_radar()
elif view_mode == "🧠 Banshee Nexus":
    render_banshee_nexus()
elif view_mode == "📰 Market Intel":
    render_market_intel()
elif view_mode == "⚖️ Risk Desk":
    render_risk_desk()
elif view_mode == "🔬 Signal Lab":
    render_strategy_lab()
elif view_mode == "📊 Saved Results":
    import strategy_lab as _sl
    _sl.render_saved_results()
elif view_mode == "📒 Trade Journal":
    render_trade_journal()
elif view_mode == "🗺️ Structure Map":
    import structure_map as _sm
    _sm.render_structure_map()
elif view_mode == "🔮 Geo Harmonic":
    render_geo_harmonic()
elif view_mode == "📖 Manual":
    render_manual()
else:
    render_settings()
