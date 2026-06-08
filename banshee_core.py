"""
banshee_core.py — Banshee 5 Core Server
============================================
FastAPI server on port 8765. Owns all engine calls and the unified cache.
Runs 24/7 independently of Streamlit or MCP clients.

Start via launch_banshee.bat (which runs this in the background before Streamlit).
The MCP server (mcp_server.py) proxies every tool call to this server via HTTP.

Text endpoints (/macro/weather, /radar human, etc.) return plain text for MCP consumers.
JSON endpoints (/macro/sensors, /ohlcv, /smc/json, /predator/*, /ai/briefing) return JSON for the Streamlit UI.
"""

import os
import sys
import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np
import pandas as pd
import uvicorn
from fastapi import Body, FastAPI, HTTPException, Query
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# ── Portability fix ───────────────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import macro_engine
import micro_engine
import banshee_ai
import risk_engine
import smc_engine
import predator_engine
import sector_rotation_engine
from shared_data import load_providers, fetch_crypto_ohlcv, fetch_sector_closes
from knowledge_graph import get_regime_weights

app = FastAPI(title="Banshee Core", version="5.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8765",
        "http://127.0.0.1:8765",
    ],
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type"],
)

_UI_DIR = Path(__file__).parent / "ui"
if _UI_DIR.exists():
    app.mount("/ui", StaticFiles(directory=str(_UI_DIR), html=True), name="ui")


def _sanitize(obj):
    """Recursively convert numpy/pandas/non-JSON types to Python natives so jsonable_encoder doesn't 500."""
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize(v) for v in obj]
    if isinstance(obj, pd.DataFrame):
        return _df_to_records(obj)
    if isinstance(obj, pd.Series):
        return [_sanitize(v) for v in obj.tolist()]
    if isinstance(obj, np.bool_):
        return bool(obj)
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        v = float(obj)
        return None if (v != v) else v  # NaN != NaN is the NaN check
    if isinstance(obj, float) and obj != obj:
        return None  # plain Python NaN
    if isinstance(obj, np.datetime64):
        return str(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    return obj

# ── Constants ─────────────────────────────────────────────────────────────────
PORT              = 8765
_MACRO_CACHE_FILE = Path.home() / ".banshee_macro_cache.json"
_CACHE_TTL        = 15 * 60   # seconds
_STRATEGIES_FILE  = os.path.join(os.path.dirname(os.path.abspath(__file__)), "strategies.json")

MODE_ALIASES = {
    "active":    "swing",
    "position":  "long_term",
    "long_term": "long_term",
    "swing":     "swing",
    "sniper":    "sniper",
}

_OHLCV_TTL   = 5 * 60   # 5 minutes — shared symbol cache across UI + MCP calls
_OHLCV_CACHE: dict = {}  # (symbol_upper, mode) → {"tfs": dict, "ts": float}

# Response-level cache for slow compute endpoints (radar analysis, SMC engine)
# Key: str cache key  →  {"ts": float, "body": str}
_RESP_TTL   = 3 * 60   # 3 minutes
_RESP_CACHE: dict = {}

_KILL_SWITCH_FILE = Path.home() / ".banshee_kill_switch.json"


def _load_kill_switch_state() -> dict:
    try:
        if _KILL_SWITCH_FILE.exists():
            return json.loads(_KILL_SWITCH_FILE.read_text())
    except Exception:
        pass
    return {"fired": False, "fired_at": None, "positions_closed": [], "domino_phase": 0, "regime": ""}


def _save_kill_switch_state(state: dict):
    try:
        _KILL_SWITCH_FILE.write_text(json.dumps(state, indent=2))
    except Exception:
        pass


# ── Cache helpers ─────────────────────────────────────────────────────────────

def _ts() -> str:
    return datetime.now(timezone.utc).strftime("Data as of %Y-%m-%d %H:%M UTC")

def _cache_age_min() -> int | None:
    try:
        if not _MACRO_CACHE_FILE.exists():
            return None
        age = datetime.now(timezone.utc).timestamp() - _MACRO_CACHE_FILE.stat().st_mtime
        return max(0, int(age / 60))
    except Exception:
        return None

def _cache_header(source: str) -> str:
    if source == "cache":
        age = _cache_age_min()
        age_str = f"{age} min ago" if age is not None else "age unknown"
        return f"Data as of now  [macro cached {age_str} — max 15 min delay]"
    return _ts() + "  [live]"

def _load_macro_cache() -> dict | None:
    try:
        if not _MACRO_CACHE_FILE.exists():
            return None
        age = datetime.now(timezone.utc).timestamp() - _MACRO_CACHE_FILE.stat().st_mtime
        if age > _CACHE_TTL:
            return None
        with open(_MACRO_CACHE_FILE) as f:
            return json.load(f)
    except Exception:
        return None

def _save_macro_cache(mac_data: dict, news_lines: list, events: list):
    try:
        payload = {"mac_data": mac_data, "news_lines": news_lines, "events": events}
        with open(_MACRO_CACHE_FILE, "w") as f:
            json.dump(payload, f)
    except Exception:
        pass

def _get_sensors() -> tuple[dict, str]:
    """Return (sensors_dict, source). Reads cache or fetches live."""
    cached = _load_macro_cache()
    if cached and "mac_data" in cached:
        return cached["mac_data"], "cache"
    providers = load_providers()
    fred_key  = providers.get("FRED_API", {}).get("key")
    flight    = macro_engine.get_flight_data()
    _, liq_chg = macro_engine.get_fed_liquidity(fred_key)
    sensors   = macro_engine.compute_sensors(flight, liq_chg)
    cached2   = _load_macro_cache()
    _save_macro_cache(sensors,
                      cached2.get("news_lines", []) if cached2 else [],
                      cached2.get("events",     []) if cached2 else [])
    return sensors, "live"

def _get_ohlcv_cached(symbol: str, mode: str) -> dict:
    """Fetch TF DataFrames with a 5-minute in-memory cache."""
    key   = (symbol.upper(), mode)
    entry = _OHLCV_CACHE.get(key)
    now   = datetime.now(timezone.utc).timestamp()
    if entry and (now - entry["ts"]) < _OHLCV_TTL:
        return entry["tfs"]
    tfs = micro_engine.load_and_prepare(symbol, mode)
    if tfs and "error" not in tfs:
        _OHLCV_CACHE[key] = {"tfs": tfs, "ts": now}
    return tfs

def _df_to_records(df) -> list:
    """Serialize a DataFrame to JSON-safe records list."""
    if df is None or (hasattr(df, "empty") and df.empty):
        return []
    return json.loads(df.to_json(orient="records", date_format="iso"))


# ── Shared helpers ────────────────────────────────────────────────────────────

def _extract_raw(tfs: dict, mode: str) -> dict:
    tf_keys = micro_engine.MODE_CONFIG.get(mode, {}).get("timeframes", [])
    labels  = ["slow", "mid", "fast"]
    fields  = ["close", "rsi", "stoch_k", "stoch_d", "macd", "macd_signal",
               "macd_hist", "vwap", "ema_50", "ema_200", "atr"]
    result  = {}
    for label, tf in zip(labels, tf_keys):
        df = tfs.get(tf)
        if df is None or df.empty:
            continue
        last = df.iloc[-1]
        result[f"{label}_{tf}"] = {
            k: (None if (v is None or (isinstance(v, float) and np.isnan(v)))
                else round(float(v), 4))
            for k, v in ((f, last.get(f)) for f in fields)
            if v is not None
        }
    return result

def _fetch_smc_df(symbol: str, tf: str):
    if "/" in symbol:
        return fetch_crypto_ohlcv(symbol, tf, limit=300)
    return micro_engine.fetch_stock(symbol, tf)

def _smc_summary(label: str, tf: str, data: dict, df) -> str:
    price   = float(df["close"].iloc[-1])
    state   = data.get("current_state", "UNDEFINED")
    pd_z    = data.get("pd_zones")
    fvgs    = data.get("fvgs", [])
    active  = sum(1 for f in fvgs if f["status"] == "active")
    partial = sum(1 for f in fvgs if f["status"] == "partial")
    events  = data.get("structure_events", [])
    lines   = [
        f"{label} ({tf}): {state}  |  Price: {price:,.2f}",
        f"  Structure events: {len(events)}  |  FVGs: {active} active, {partial} partial",
    ]
    if pd_z:
        lines.append(
            f"  Dealing Range: {pd_z['range_low']:,.2f}–{pd_z['range_high']:,.2f}  "
            f"EQ: {pd_z['equilibrium']:,.2f}  "
            f"OTE: {pd_z['ote_bottom']:,.2f}–{pd_z['ote_top']:,.2f}"
        )
    if events:
        lines.append("  Last event: " + events[-1]["event_type"] +
                     f" @ {events[-1]['price']:,.2f}")
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# ROUTE 1 — Macro Weather
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/macro/weather", response_class=PlainTextResponse)
def route_macro_weather():
    sensors, source = _get_sensors()

    lines = [
        _cache_header(source),
        f"MACRO REGIME: {sensors['regime']}",
        f"SYSTEMIC RISK SCORE: {sensors['risk_score']}/100",
        f"ACTIVE WARNINGS: {sensors['warning_count']}",
        "",
        "SENSOR DETAILS:",
    ]
    for name, s in sensors.items():
        if isinstance(s, dict) and "status" in s:
            flag = "WARN" if s.get("warning") else "OK  "
            lines.append(f"  [{flag}] {name.upper()}: {s['status']} — {s.get('sub', '')}")

    contradictions = sensors.get("contradictions", [])
    if contradictions:
        lines += ["", "CONTRADICTION PATTERNS (gradient signals below headline thresholds):"]
        for c in contradictions:
            lines.append(f"  [{c['severity']}] {c['name']}: {c['description']}")

    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# ROUTE 2 — Market Intel
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/intel", response_class=PlainTextResponse)
def route_intel():
    briefing  = predator_engine.load_latest_briefing()
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    if briefing and briefing.get("date") == today_str:
        out_parts = [
            f"DAILY PREDATOR BRIEFING — {briefing['date']} (generated {briefing.get('generated_at','')[:16]} UTC)",
            f"MACRO TONE: {briefing.get('macro_tone','NEUTRAL')} | RISK LEVEL: {briefing.get('risk_level',3)}/5",
            f"TOP STORY: {briefing.get('top_story','')}",
            "",
        ]
        wl = briefing.get("watchlist_events", [])
        if wl:
            out_parts.append(f"WATCHLIST EVENTS ({len(wl)}):")
            for ev in wl:
                score = ev.get("impact_score", 0)
                hl    = ev.get("headline") or ev.get("title", "")
                lede  = ev.get("lede", "")
                syms  = ev.get("symbols", [])
                sym_s = f" [{', '.join(syms)}]" if syms else ""
                out_parts.append(f"  [{score}/10]{sym_s} {hl}")
                if lede:
                    out_parts.append(f"    → {lede}")
            out_parts.append("")

        ds = briefing.get("discovered_signals", [])
        if ds:
            out_parts.append(f"DISCOVERED SIGNALS ({len(ds)}):")
            for ev in ds:
                score  = ev.get("impact_score", 0)
                hl     = ev.get("headline") or ev.get("title", "")
                reason = ev.get("reason_flagged") or ev.get("lede", "")
                out_parts.append(f"  [{score}/10] {hl}")
                if reason:
                    out_parts.append(f"    → {reason}")
            out_parts.append("")

        fu = briefing.get("yesterday_followups", [])
        if fu:
            out_parts.append(f"YESTERDAY FOLLOWUPS ({len(fu)}):")
            for item in fu:
                status = item.get("status", "").upper()
                orig   = item.get("original", "")
                update = item.get("update", "")
                out_parts.append(f"  [{status}] {orig}")
                if update:
                    out_parts.append(f"    → {update}")

        counts = briefing.get("event_counts", {})
        out_parts.append(
            f"\nPipeline: {counts.get('watchlist_intake',0)} watchlist + "
            f"{counts.get('discovered_intake',0)} discovered events "
            f"({counts.get('rejected',0)} filtered out)"
        )
        return "\n".join(out_parts)

    stories, events = macro_engine.get_intel_feeds(dismissed_tuple=())
    if not stories:
        return "No recent intel feeds available. Run the Daily Predator from the Market Intel tab for a structured briefing."

    lines = macro_engine.build_news_prompt_lines(stories)
    out = "CURRENT FINANCIAL HEADLINES (no Daily Predator briefing for today — run it from Market Intel tab):\n"
    out += "\n".join(lines)
    if events:
        out += f"\n\nEVENT KEYWORDS DETECTED: {', '.join(events)}"
    return out


# ─────────────────────────────────────────────────────────────────────────────
# ROUTE 3 — Regime (lightweight go/no-go)
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/regime", response_class=PlainTextResponse)
def route_regime():
    sensors, source = _get_sensors()

    bucket, _ = get_regime_weights(sensors)
    regime        = sensors.get("regime", "UNKNOWN")
    risk_score    = sensors.get("risk_score", 0)
    warnings      = sensors.get("warning_count", 0)
    contradictions = sensors.get("contradictions", [])

    lines = [
        _cache_header(source),
        f"REGIME BUCKET: {bucket}",
        f"REGIME: {regime}",
        f"RISK SCORE: {risk_score}/100",
        f"ACTIVE WARNINGS: {warnings}",
    ]
    if contradictions:
        lines.append("CONTRADICTIONS: " + ", ".join(c.get("name", "") for c in contradictions))

    if bucket == "FEAR":
        lines.append("GUIDANCE: High systemic stress — consider reducing size or standing aside.")
    elif bucket == "CAUTION":
        lines.append("GUIDANCE: Early warning signs active — trade only high-conviction setups, tighten stops.")
    elif bucket == "TRENDING":
        lines.append("GUIDANCE: Clean macro backdrop — full sizing on quality setups.")
    else:
        lines.append("GUIDANCE: No strong macro signal — normal sizing, stay selective.")

    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# ROUTE 4 — Watchlist
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/watchlist", response_class=PlainTextResponse)
def route_watchlist():
    cfg         = predator_engine.load_predator_config()
    watchlist   = cfg.get("watchlist", [])
    custom_kw   = cfg.get("custom_keywords", [])
    sensitivity = cfg.get("sensitivity", 3)

    lines = [
        _ts(),
        f"WATCHLIST ({len(watchlist)} symbols): {', '.join(watchlist) if watchlist else 'empty'}",
        f"PREDATOR SENSITIVITY: {sensitivity}/5",
    ]
    if custom_kw:
        lines.append(f"CUSTOM KEYWORDS: {', '.join(custom_kw)}")
    lines.append("")
    lines.append("SUGGESTED NEXT STEP: call scan_assets with these symbols to get a ranked technical overview.")
    return "\n".join(lines)


def _compute_bias(trends: dict) -> str:
    vals = list(trends.values())
    bull = sum(1 for v in vals if v == "BULLISH")
    bear = sum(1 for v in vals if v == "BEARISH")
    if bull >= 3: return "↑ STRONG"
    if bull == 2: return "↑ MILD"
    if bear >= 3: return "↓ STRONG"
    if bear == 2: return "↓ MILD"
    return "→ FLAT"


# ─────────────────────────────────────────────────────────────────────────────
# ROUTE 5 — Asset Radar (single symbol)
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/radar", response_class=PlainTextResponse)
def route_radar(
    symbol: str = Query(...),
    mode: str = Query("swing"),
    output_mode: str = Query("human"),
):
    mode  = MODE_ALIASES.get(mode.lower(), "swing")
    _rkey = f"radar:{symbol.upper()}:{mode}"
    _entry = _RESP_CACHE.get(_rkey)
    if _entry and (time.time() - _entry["ts"]) < _RESP_TTL:
        res    = _entry["res"]
        tfs    = _get_ohlcv_cached(symbol, mode)   # already warm in OHLCV cache
        cached = _load_macro_cache()
        source = "cache"
    else:
        tfs = _get_ohlcv_cached(symbol, mode)
        if not tfs or "error" in tfs:
            return f"Error loading data for {symbol}. Check the ticker format."
        cached        = _load_macro_cache()
        radar_sensors = cached["mac_data"] if cached and "mac_data" in cached else None
        res = micro_engine.run_analysis(symbol, mode, tfs, sensors=radar_sensors)
        if "error" in res:
            return f"Analysis error for {symbol}: {res['error']}"
        _RESP_CACHE[_rkey] = {"ts": time.time(), "res": res}
        source = "cache" if (cached and "mac_data" in cached) else "live"

    eq      = res.get("entry_quality", {})
    funding = res.get("funding_rate", {})
    atr     = res.get("atr_plan", {})

    # output_mode=full: full structured JSON for the Streamlit UI
    if output_mode == "full":
        return JSONResponse(content=jsonable_encoder(_sanitize({
            "symbol":               symbol,
            "mode":                 mode,
            "timestamp":            datetime.now(timezone.utc).isoformat(),
            "cache_age_min":        _cache_age_min() if source == "cache" else 0,
            "verdict":              res["verdict"],
            "edge":                 res["edge"],
            "price":                res["price"],
            "rsi":                  res.get("rsi", 50),
            "chg_pct":              res.get("chg_pct", 0.0),
            "bias":                 _compute_bias(res.get("trends", {})),
            "pre_signal":           res.get("pre_signal"),
            "setup_name":           res.get("setup_name"),
            "regime_bucket":        res.get("regime_bucket", "NEUTRAL"),
            "session_weight":       res.get("session_weight", 1.0),
            "entry_quality":        res.get("entry_quality", {}),
            "volume":               res.get("volume", "UNKNOWN"),
            "asset_class":          res.get("asset_class", "default"),
            "asset_class_confirmed":res.get("asset_class_confirmed", False),
            "stop_multiplier":      res.get("stop_multiplier", 1.5),
            "target_multiplier":    res.get("target_multiplier", 3.0),
            "chandelier_exit":      res.get("chandelier_exit", False),
            "eth_btc_gate_enabled": res.get("eth_btc_gate_enabled", False),
            "eth_btc_regime":       res.get("eth_btc_regime"),
            "atr_plan":             res.get("atr_plan"),
            "signals":              res.get("signals", {}),
            "asymmetry":            res.get("asymmetry", {}),
            "asset_safety":         res.get("asset_safety", {}),
            "warnings":             res.get("warnings", {}),
            "funding_rate":         res.get("funding_rate", {}),
            "risk_score":           res.get("risk_score"),
        })))

    if output_mode == "agent":
        return json.dumps({
            "symbol":        symbol,
            "mode":          mode,
            "timestamp":     datetime.now(timezone.utc).isoformat(),
            "cache_age_min": _cache_age_min() if source == "cache" else 0,
            "price":         res["price"],
            "verdict":       res["verdict"],
            "edge":          res["edge"],
            "pre_signal":    res.get("pre_signal"),
            "entry_quality": eq.get("quality"),
            "volume":        res.get("volume"),
            "profile": {
                "asset_class": res.get("asset_class", "default"),
                "confirmed":   res.get("asset_class_confirmed", False),
                "stop_mult":   res.get("stop_multiplier", 1.5),
                "target_mult": res.get("target_multiplier", 3.0),
                "chandelier":  res.get("chandelier_exit", False),
                "eth_btc_gate":   res.get("eth_btc_gate_enabled", False),
                "eth_btc_regime": res.get("eth_btc_regime"),
            },
            "atr_plan": {
                "stop_long":    atr.get("stop_long"),
                "target_long":  atr.get("target_long"),
                "stop_short":   atr.get("stop_short"),
                "target_short": atr.get("target_short"),
                "risk_reward":  atr.get("risk_reward"),
            } if atr else None,
            "raw_indicators": _extract_raw(tfs, mode),
        }, indent=2)

    pre_signal = res.get("pre_signal")
    lines = [
        _cache_header(source),
        f"ASSET: {symbol}  |  PRICE: ${res['price']:.4f}",
        f"VERDICT: {res['verdict']}  |  EDGE SCORE: {res['edge']}",
    ]
    if pre_signal:
        lines.append(f"⚡ {pre_signal} — Early signal detected before full trend confirmation.")

    _ac      = res.get("asset_class", "default")
    _ac_conf = res.get("asset_class_confirmed", False)
    _stop_m  = res.get("stop_multiplier",   1.5)
    _tgt_m   = res.get("target_multiplier", 3.0)
    _chndlr  = res.get("chandelier_exit",   False)
    _gate_on = res.get("eth_btc_gate_enabled", False)
    _gate_rgm= res.get("eth_btc_regime")
    _ac_label= f"{_ac}  ({'confirmed' if _ac_conf else 'suggested'})"
    lines += [
        f"PROFILE:  {_ac_label}",
        f"  Risk model: Stop {_stop_m}× ATR  |  Target {_tgt_m}× ATR  |  Chandelier: {'ON' if _chndlr else 'OFF'}",
    ]
    if _gate_on:
        _gate_str = f"ACTIVE — ETH/BTC regime: {_gate_rgm}" if _gate_rgm else "ACTIVE — regime not yet evaluated"
        lines.append(f"  ETH/BTC Gate: {_gate_str}")
    lines += [
        f"ENTRY QUALITY: {eq.get('quality', 'UNKNOWN')}",
        f"VOLUME PRESSURE: {res.get('volume', 'UNKNOWN')}",
    ]

    if eq.get("reasons"):
        lines.append("TIMING NOTES: " + " | ".join(eq["reasons"]))
    if funding.get("available"):
        lines.append(f"FUNDING RATE: {funding.get('risk_label')} ({funding.get('rate_pct')}%)")

    if atr and res["verdict"] in ("STRONG BUY", "BUY SETUP", "STRONG SELL", "SELL SETUP"):
        is_long = "BUY" in res["verdict"]
        lines += [
            "",
            "ATR TRADE PLAN:",
            f"  Entry:  ${res['price']:.4f}",
            f"  Stop:   ${atr.get('stop_long' if is_long else 'stop_short', 0):.4f}",
            f"  Target: ${atr.get('target_long' if is_long else 'target_short', 0):.4f}",
            f"  R:R     1 : {atr.get('risk_reward', 0):.1f}  {atr.get('rr_quality', '')}",
        ]

    lines += ["", "SIGNAL BREAKDOWN:"]
    for tf_label, breakdown in res.get("signals", {}).items():
        lines.append(f"\n  [{tf_label}]")
        for item in breakdown:
            lines.append(f"    {item['indicator']} ({item['state']}): {item['explanation']}")

    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# ROUTE 6 — Asset Scanner (watchlist)
# ─────────────────────────────────────────────────────────────────────────────

class ScanRequest(BaseModel):
    symbols: list[str]
    mode: str = "swing"
    output_mode: str = "human"


@app.post("/scan", response_class=PlainTextResponse)
def route_scan(req: ScanRequest):
    mode = MODE_ALIASES.get(req.mode.lower(), "swing")

    cached = _load_macro_cache()
    scan_sensors = cached["mac_data"] if cached and "mac_data" in cached else None

    def _analyze_one(raw_sym: str):
        sym = raw_sym.strip().upper()
        try:
            tfs = micro_engine.load_and_prepare(sym, mode)
            if not tfs or "error" in tfs:
                return None, f"{sym}: failed to load data"
            res = micro_engine.run_analysis(sym, mode, tfs, sensors=scan_sensors)
            if "error" in res:
                return None, f"{sym}: {res['error']}"
            return {
                "symbol":               sym,
                "verdict":              res["verdict"],
                "pre_signal":           res.get("pre_signal"),
                "edge":                 res["edge"],
                "price":                res["price"],
                "entry_quality":        res.get("entry_quality", {}).get("quality", "UNKNOWN"),
                "volume":               res.get("volume", "UNKNOWN"),
                "warnings":             [k for k, v in res.get("warnings", {}).items() if v],
                "asset_class":          res.get("asset_class", "default"),
                "asset_class_confirmed":res.get("asset_class_confirmed", False),
                "eth_btc_gate_enabled": res.get("eth_btc_gate_enabled", False),
                "eth_btc_regime":       res.get("eth_btc_regime"),
                "stop_multiplier":      res.get("stop_multiplier",   1.5),
                "target_multiplier":    res.get("target_multiplier", 3.0),
                "chandelier_exit":      res.get("chandelier_exit",   False),
            }, None
        except Exception as e:
            return None, f"{sym}: {e}"

    results, errors = [], []
    with ThreadPoolExecutor(max_workers=min(8, len(req.symbols))) as pool:
        futures = {pool.submit(_analyze_one, s): s for s in req.symbols}
        for future in as_completed(futures):
            result, error = future.result()
            if error:
                errors.append(error)
            elif result:
                results.append(result)

    results.sort(key=lambda x: abs(x["edge"]), reverse=True)

    if req.output_mode == "agent":
        return json.dumps({
            "mode":          mode,
            "timestamp":     datetime.now(timezone.utc).isoformat(),
            "cache_age_min": _cache_age_min() if scan_sensors else 0,
            "scanned":       len(req.symbols),
            "results": [
                {
                    "symbol":        r["symbol"],
                    "verdict":       r["verdict"],
                    "edge":          r["edge"],
                    "price":         r["price"],
                    "pre_signal":    r.get("pre_signal"),
                    "entry_quality": r["entry_quality"],
                    "volume":        r["volume"],
                    "profile": {
                        "asset_class": r.get("asset_class", "default"),
                        "confirmed":   r.get("asset_class_confirmed", False),
                        "stop_mult":   r.get("stop_multiplier", 1.5),
                        "target_mult": r.get("target_multiplier", 3.0),
                        "chandelier":  r.get("chandelier_exit", False),
                        "eth_btc_gate":   r.get("eth_btc_gate_enabled", False),
                        "eth_btc_regime": r.get("eth_btc_regime"),
                    },
                    "warnings": r["warnings"],
                }
                for r in results
            ],
            "errors": errors,
        }, indent=2)

    lines = [
        _cache_header("cache" if scan_sensors else "live"),
        f"SCAN RESULTS — Mode: {mode} | Scanned: {len(req.symbols)} | Found: {len(results)}",
        "",
        f"{'#':<3} {'SYMBOL':<12} {'VERDICT':<14} {'EDGE':>5} {'PRICE':>12} {'ENTRY':<10} {'VOLUME'}",
        "-" * 70,
    ]
    for i, r in enumerate(results, 1):
        warn_flag = " ⚠" if r["warnings"] else ""
        pre_flag  = " ⚡" if r.get("pre_signal") else ""
        lines.append(
            f"{i:<3} {r['symbol']:<12} {r['verdict']:<14} {r['edge']:>5} "
            f"${r['price']:>10.4f} {r['entry_quality']:<10} {r['volume']}{warn_flag}{pre_flag}"
        )
        if r.get("pre_signal"):
            lines.append(f"    ↳ ⚡ {r['pre_signal']}")
        _ac    = r.get("asset_class", "default")
        _conf  = "" if r.get("asset_class_confirmed") else "?"
        _stop  = r.get("stop_multiplier",   1.5)
        _tgt   = r.get("target_multiplier", 3.0)
        _chand = "chand" if r.get("chandelier_exit") else ""
        _risk  = f"stop {_stop}×  tgt {_tgt}×  {_chand}".strip()
        lines.append(f"    ↳ profile: {_ac}{_conf}  [{_risk}]")
        if r.get("eth_btc_gate_enabled"):
            _rgm = r.get("eth_btc_regime") or "not evaluated"
            lines.append(f"    ↳ ETH/BTC gate ON — regime: {_rgm}")
        for w in r["warnings"]:
            lines.append(f"    ↳ WARNING: {w}")

    if errors:
        lines += ["", "ERRORS:"]
        for e in errors:
            lines.append(f"  ! {e}")

    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# ROUTE 7 — Banshee Nexus
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/nexus", response_class=PlainTextResponse)
def route_nexus(
    symbol: str = Query(...),
    mode: str = Query("swing"),
    use_ai: bool = Query(True),
    output_mode: str = Query("human"),
):
    mode           = MODE_ALIASES.get(mode.lower(), "swing")
    mac_data, _src = _get_sensors()
    cached         = _load_macro_cache()
    news_lines     = cached.get("news_lines", []) if cached else []
    events         = cached.get("events",     []) if cached else []

    predator_brief = predator_engine.load_latest_briefing()
    predator_lines = predator_engine.get_briefing_for_nexus(predator_brief)
    if predator_lines:
        news_lines = [predator_lines] + news_lines

    mic_tfs = _get_ohlcv_cached(symbol, mode)
    if not mic_tfs or "error" in mic_tfs:
        return f"Error: Failed to load data for {symbol}."
    domino_phase = mac_data.get("domino_phase", 0)
    mic_data = micro_engine.run_analysis(symbol, mode, mic_tfs, domino_phase=domino_phase, sensors=mac_data)
    if "error" in mic_data:
        return f"Micro analysis error: {mic_data['error']}"

    if output_mode == "agent":
        eq     = mic_data.get("entry_quality", {})
        safety = mic_data.get("asset_safety", {})
        asym   = mic_data.get("asymmetry", {})
        atr    = mic_data.get("atr_plan", {})
        return json.dumps({
            "symbol":    symbol,
            "mode":      mode,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "macro": {
                "regime":         mac_data.get("regime"),
                "risk_score":     mac_data.get("risk_score"),
                "warning_count":  mac_data.get("warning_count"),
                "domino_phase":   mac_data.get("domino_phase"),
                "contradictions": mac_data.get("contradictions", []),
            },
            "micro": {
                "verdict":         mic_data.get("verdict"),
                "edge":            mic_data.get("edge"),
                "pre_signal":      mic_data.get("pre_signal"),
                "price":           mic_data.get("price"),
                "setup":           mic_data.get("setup_name"),
                "entry_quality":   eq.get("quality"),
                "volume":          mic_data.get("volume"),
                "asymmetry_score": asym.get("score"),
                "asymmetry_label": asym.get("label"),
                "asset_safety":    safety.get("category"),
                "atr_stop_long":   atr.get("stop_long"),
                "atr_target_long": atr.get("target_long"),
                "atr_stop_short":  atr.get("stop_short"),
                "atr_target_short":atr.get("target_short"),
                "risk_reward":     atr.get("risk_reward"),
            },
            "events": events,
        }, indent=2)

    eq     = mic_data.get("entry_quality", {})
    safety = mic_data.get("asset_safety", {})
    asym   = mic_data.get("asymmetry", {})
    out = "\n".join([
        "═" * 60,
        f"  BANSHEE NEXUS — {symbol}",
        "═" * 60,
        f"MACRO REGIME:  {mac_data['regime']}  (Risk Score: {mac_data.get('risk_score', 0)}/100)",
        f"DOMINO PHASE:  {domino_phase}  ({mac_data.get('domino_state', {}).get('state_str', '')})",
        f"MACRO WARNINGS: {mac_data['warning_count']} active",
        "",
        f"MICRO VERDICT: {mic_data['verdict']}  (Edge: {mic_data['edge']})",
        *([ f"⚡ {mic_data['pre_signal']} — Early signal detected before full trend confirmation." ]
          if mic_data.get("pre_signal") else []),
        f"SETUP:         {mic_data.get('setup_name', 'N/A')}",
        f"ENTRY QUALITY: {eq.get('quality', 'UNKNOWN')}",
        f"PRICE:         ${mic_data['price']:.4f}",
        f"ASSET CLASS:   {safety.get('category', 'Unknown')}  — {safety.get('rationale', '')}",
        f"ASYMMETRY:     {asym.get('score', 0)}/100  [{asym.get('label', '')}]",
    ])
    if events:
        out += f"\nEVENT CATALYSTS: {', '.join(events)}"
    if asym.get("reasons"):
        out += "\nASYMMETRY REASONS: " + " | ".join(asym["reasons"])
    contradictions = mac_data.get("contradictions", [])
    if contradictions:
        out += "\n\nCONTRADICTION PATTERNS DETECTED:"
        for c in contradictions:
            out += f"\n  [{c['severity']}] {c['name']}: {c['description']}"

    cfg = providers.get("AI_API")
    if use_ai and cfg and cfg.get("key"):
        prompt   = banshee_ai.build_banshee_prompt(
            mac_data, mic_data, news_lines, manual_stories=[], include_macro=True
        )
        briefing = banshee_ai.call_ai_briefing(cfg, prompt)
        out += f"\n\n{'─' * 60}\nAI BRIEFING ({cfg.get('type', 'AI')} / {cfg.get('model', '')}):\n{'─' * 60}\n{briefing}"
    elif use_ai:
        out += (
            "\n\n[AI BRIEFING UNAVAILABLE]\n"
            "No AI key configured in ~/.banshee_keys.json.\n"
            "Open the Banshee Pro Streamlit UI and save a Claude or Gemini key in the sidebar."
        )

    return out


# ─────────────────────────────────────────────────────────────────────────────
# ROUTE 8 — Execution Plan
# ─────────────────────────────────────────────────────────────────────────────

class ExecutionPlanRequest(BaseModel):
    account_size: float
    risk_percent: float
    entry_price: float
    stop_loss: float
    smc_conflicted: bool = False
    output_mode: str = "text"


@app.post("/execution-plan")
def route_execution_plan(req: ExecutionPlanRequest):
    plan = risk_engine.calculate_execution_plan(
        req.account_size, req.risk_percent, req.entry_price, req.stop_loss,
        smc_conflicted=req.smc_conflicted,
    )
    if "error" in plan:
        if req.output_mode == "json":
            return JSONResponse(content={"error": plan["error"]}, status_code=400)
        return PlainTextResponse(f"RISK ENGINE ERROR: {plan['error']}")

    if req.output_mode == "json":
        return JSONResponse(content=_sanitize(plan))

    direction = "LONG" if plan["is_long"] else "SHORT"
    lines = [
        "═" * 50,
        "  EXECUTION PLAN",
        "═" * 50,
    ]
    if plan.get("confidence_note"):
        lines += [
            f"  ⚠  CONFIDENCE WARNING",
            "═" * 50,
            f"  {plan['confidence_note']}",
            "═" * 50,
        ]
    lines += [
        f"DIRECTION:      {direction}",
        f"ENTRY:          ${plan['entry_price']:,.4f}",
        f"STOP-LOSS:      ${plan['stop_loss']:,.4f}",
        f"ACCOUNT SIZE:   ${plan['account_size']:,.2f}",
        f"RISK ({plan['risk_percent']}%):     ${plan['max_risk_dollars']:,.2f}",
        "",
        f"POSITION SIZE:  {plan['position_size']:,.4f} units{'  [50% — SMC CONFLICTED]' if plan.get('smc_conflicted') else ''}",
        f"POSITION VALUE: ${plan['position_value']:,.2f}",
        "",
        "CAPITAL EFFICIENCY (Margin Required):",
    ]
    for row in plan["capital_efficiency"]:
        lines.append(f"  {row['leverage']:>3}x leverage → ${row['margin_required']:,.2f}")
    lines += ["", "EXIT TARGETS (R-Multiples):"]
    for tgt in plan["targets"]:
        lines.append(
            f"  {tgt['r_multiple']}R → ${tgt['price']:,.4f}  "
            f"(+${tgt['profit']:,.2f} profit)"
        )
    return PlainTextResponse("\n".join(lines))


# ─────────────────────────────────────────────────────────────────────────────
# ROUTE 9 — Strategy Results
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/strategies", response_class=PlainTextResponse)
def route_strategies(name: str = Query("")):
    if not os.path.exists(_STRATEGIES_FILE):
        return "No strategies saved yet. Run backtests in the Strategy Lab and save them first."
    try:
        with open(_STRATEGIES_FILE, "r", encoding="utf-8") as f:
            strategies = json.load(f)
    except Exception as e:
        return f"Error reading strategies.json: {e}"
    if not strategies:
        return "strategies.json is empty — no saved strategies found."

    if not name or name in ("*", "all"):
        lines = [_ts(), f"SAVED STRATEGIES ({len(strategies)} total)", "=" * 60, ""]
        for sname, s in strategies.items():
            stats  = s.get("stats", {})
            lines += [
                f"NAME:   {sname}",
                f"TYPE:   {s.get('type','custom')}  |  SYMBOL: {s.get('symbol','—')}  |  TF: {s.get('timeframe','—')}  |  LOOKBACK: {s.get('lookback','—')}",
                f"STATS:  Return {stats.get('total_return','—')}  |  Sharpe {stats.get('sharpe','—')}  "
                f"|  MaxDD {stats.get('max_dd','—')}  |  WinRate {stats.get('win_rate','—')}  "
                f"|  Trades {stats.get('n_trades','—')}",
                f"SAVED:  {s.get('saved_at','—')}",
                "",
            ]
        lines.append('To get full details, call: get_strategy_results("strategy name")')
        return "\n".join(lines)

    if name not in strategies:
        match = next((k for k in strategies if k.lower() == name.lower()), None)
        if match:
            name = match
        else:
            available = ", ".join(f'"{k}"' for k in list(strategies.keys())[:10])
            suffix = " …" if len(strategies) > 10 else ""
            return f'Strategy "{name}" not found.\nAvailable: {available}{suffix}'

    s     = strategies[name]
    stats = s.get("stats", {})
    lines = [
        _ts(), "═" * 60, f"  STRATEGY: {name}", "═" * 60,
        f"TYPE:      {s.get('type','custom')}",
        f"SYMBOL:    {s.get('symbol','—')}",
        f"TIMEFRAME: {s.get('timeframe','—')}",
        f"LOOKBACK:  {s.get('lookback','—')}",
        f"SAVED AT:  {s.get('saved_at','—')}",
    ]
    conditions = s.get("conditions", [])
    if conditions:
        lines += ["", "ENTRY CONDITIONS (all must be true simultaneously):"]
        for i, cond in enumerate(conditions, 1):
            if isinstance(cond, str):
                lines.append(f"  {i}. {cond}")
            else:
                val_str = f" → {cond['value']}" if cond.get("value") is not None else ""
                lines.append(f"  {i}. {cond['indicator']} — {cond['condition']}{val_str}")
        lines.append(f"EXIT METHOD: {s.get('exit_mode','—')}")
        if s.get("stop_pct") is not None:
            lines.append(f"  Stop: {s['stop_pct']}%  |  Target: {s.get('target_pct','—')}%")

    if stats:
        lines += [
            "", "BACKTEST PERFORMANCE:",
            f"  Total Return: {stats.get('total_return','—')}",
            f"  Sharpe Ratio: {stats.get('sharpe','—')}",
            f"  Max Drawdown: {stats.get('max_dd','—')}",
            f"  Win Rate:     {stats.get('win_rate','—')}",
            f"  # Trades:     {stats.get('n_trades','—')}",
        ]
    else:
        lines += ["", "No performance stats recorded for this strategy."]

    lines += ["", "AGENT EVALUATION NOTES:"]
    try:
        ret_val = float(stats.get("total_return", "0").replace("%","").replace("+",""))
    except Exception:
        ret_val = None
    try:
        sharpe_val = float(stats.get("sharpe", "0"))
    except Exception:
        sharpe_val = None
    try:
        wr_val = float(stats.get("win_rate", "0").replace("%","").replace("+",""))
    except Exception:
        wr_val = None
    try:
        nt_val = int(stats.get("n_trades", "0"))
    except Exception:
        nt_val = None

    if ret_val is None or sharpe_val is None:
        verdict, apply_live = "INCONCLUSIVE — stats missing or unparseable.", False
    elif nt_val is not None and nt_val < 10:
        verdict, apply_live = "TOO FEW TRADES — sample size too small to trust the edge.", False
    elif ret_val > 0 and sharpe_val >= 1.0:
        verdict, apply_live = "STRONG EDGE — positive return with solid risk-adjusted performance.", True
    elif ret_val > 0 and sharpe_val > 0:
        verdict, apply_live = "MARGINAL EDGE — positive return but risk-adjusted performance is weak. Use smaller size.", False
    else:
        verdict, apply_live = "NO EDGE — negative return. Do not apply to live trading.", False

    lines += [
        f"  VERDICT:       {verdict}",
        f"  APPLY TO LIVE: {'YES' if apply_live else 'NO'}",
    ]
    if wr_val is not None:
        lines.append(f"  WIN RATE NOTE: {'Above 50% — wins more often than it loses.' if wr_val >= 50 else 'Below 50% — relies on big winners to overcome frequent small losses.'}")
    if conditions:
        lines.append(f"  CONDITION COUNT: {len(conditions)} — {'tight filter' if len(conditions) >= 3 else 'loose filter'}")

    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# ROUTE 10 — SMC Structure
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/smc", response_class=PlainTextResponse)
def route_smc(
    symbol: str = Query(...),
    ltf: str = Query("4h"),
    htf: str = Query("1d"),
    use_ai: bool = Query(True),
):
    _rkey  = f"smc:{symbol.upper()}:{ltf}:{htf}:{use_ai}"
    _entry = _RESP_CACHE.get(_rkey)
    if _entry and (time.time() - _entry["ts"]) < _RESP_TTL:
        return _entry["body"]

    ltf_df, ltf_err = _fetch_smc_df(symbol, ltf)
    if ltf_err or ltf_df is None or (hasattr(ltf_df, "empty") and ltf_df.empty):
        return f"Failed to load {symbol} {ltf}: {ltf_err or 'empty'}"
    ltf_data = smc_engine.run(ltf_df)
    if "error" in ltf_data:
        return f"SMC engine error ({ltf}): {ltf_data['error']}"

    if htf == ltf:
        htf_df, htf_data = ltf_df, ltf_data
    else:
        htf_df, htf_err = _fetch_smc_df(symbol, htf)
        if htf_err or htf_df is None or (hasattr(htf_df, "empty") and htf_df.empty):
            return f"Failed to load {symbol} {htf}: {htf_err or 'empty'}"
        htf_data = smc_engine.run(htf_df)
        if "error" in htf_data:
            return f"SMC engine error ({htf}): {htf_data['error']}"

    htf_state = htf_data.get("current_state", "UNDEFINED")
    ltf_state = ltf_data.get("current_state", "UNDEFINED")
    alignment = (
        f"ALIGNED ({htf_state})" if htf_state == ltf_state and htf_state != "UNDEFINED"
        else f"CONFLICTED — HTF {htf_state} vs LTF {ltf_state}"
        if htf_state != "UNDEFINED" and ltf_state != "UNDEFINED"
        else "INSUFFICIENT DATA"
    )

    out = "\n".join([
        _ts(),
        f"SMC STRUCTURE — {symbol}",
        "=" * 50,
        _smc_summary("HTF", htf, htf_data, htf_df),
        "",
        _smc_summary("LTF", ltf, ltf_data, ltf_df),
        "",
        f"ALIGNMENT: {alignment}",
    ])

    providers = load_providers()
    ai_cfg    = providers.get("AI_API", {})
    if use_ai and ai_cfg and ai_cfg.get("key"):
        narrative = banshee_ai.smc_analysis(
            symbol=symbol,
            htf_tf=htf, htf_df=htf_df, htf_smc=htf_data,
            ltf_tf=ltf, ltf_df=ltf_df, ltf_smc=ltf_data,
            cfg=ai_cfg,
        )
        out += f"\n\n{'─' * 50}\nAI STRUCTURE NARRATIVE:\n{'─' * 50}\n{narrative}"
    elif use_ai:
        out += "\n\n[AI NARRATIVE UNAVAILABLE — no AI key configured]"

    _RESP_CACHE[_rkey] = {"ts": time.time(), "body": out}
    return out


# ─────────────────────────────────────────────────────────────────────────────
# ROUTE 11.5 — Kill Switch
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/kill-switch/check")
def route_kill_switch_check():
    """
    Check the domino phase. If CRACK DETECTED (phase >= 2) and open positions exist,
    close them all with exit_reason='kill_switch_crack' and record the event.
    Safe to call repeatedly — idempotent when no open trades remain.
    """
    import paper_trader
    sensors, _source = _get_sensors()
    domino_phase = sensors.get("domino_phase", 0)
    regime       = sensors.get("regime", "UNKNOWN")

    if domino_phase < 2:
        _save_kill_switch_state({
            "fired": False, "fired_at": None,
            "positions_closed": [], "domino_phase": domino_phase, "regime": regime,
        })
        return JSONResponse(content={
            "fired": False,
            "domino_phase": domino_phase,
            "regime": regime,
            "positions_closed": [],
            "message": f"Domino phase {domino_phase} — regime safe, kill switch not triggered.",
        })

    note   = f"Kill switch: CRACK DETECTED (domino_phase={domino_phase})"
    closed = paper_trader.close_all_open_trades(note=note)

    if closed:
        state = {
            "fired":            True,
            "fired_at":         datetime.now(timezone.utc).isoformat(),
            "positions_closed": closed,
            "domino_phase":     domino_phase,
            "regime":           regime,
        }
        _save_kill_switch_state(state)
        msg = f"KILL SWITCH FIRED — closed {len(closed)} position(s). CRACK DETECTED (domino_phase={domino_phase})."
    else:
        msg = f"CRACK DETECTED (domino_phase={domino_phase}) but no open positions to close."

    return JSONResponse(content={
        "fired":            len(closed) > 0,
        "domino_phase":     domino_phase,
        "regime":           regime,
        "positions_closed": closed,
        "message":          msg,
    })


@app.get("/kill-switch/status")
def route_kill_switch_status():
    """Return last kill switch state from disk — no action taken."""
    return JSONResponse(content=_load_kill_switch_state())


# ─────────────────────────────────────────────────────────────────────────────
# HEALTH CHECK
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "ts": _ts()}


# ─────────────────────────────────────────────────────────────────────────────
# SETTINGS — read/write ~/.banshee_keys.json
# ─────────────────────────────────────────────────────────────────────────────

def _mask(v: str) -> str:
    if isinstance(v, str) and len(v) > 4:
        return "•••••" + v[-4:]
    return v

@app.get("/settings")
def route_settings_get():
    providers = load_providers()
    masked = {}
    for section, val in providers.items():
        if isinstance(val, dict):
            masked[section] = {
                k: (_mask(v) if k in ("key", "secret") else v)
                for k, v in val.items()
            }
        else:
            masked[section] = val
    return JSONResponse(content=masked)

class SettingsBody(BaseModel):
    settings: dict

@app.post("/settings")
def route_settings_save(body: SettingsBody):
    existing = load_providers()
    def _merge(old: dict, new: dict) -> dict:
        result = dict(old)
        for k, v in new.items():
            if isinstance(v, str) and v.startswith("•••••"):
                pass  # keep existing masked value
            else:
                result[k] = v
        return result
    merged = dict(existing)
    for section, val in body.settings.items():
        if isinstance(val, dict) and section in existing and isinstance(existing[section], dict):
            merged[section] = _merge(existing[section], val)
        else:
            merged[section] = val
    from shared_data import save_providers
    save_providers(merged)
    return {"status": "saved"}

@app.post("/settings/test")
def route_settings_test(body: SettingsBody):
    ai_cfg   = body.settings.get("AI_API", {})
    provider = ai_cfg.get("type", "").lower()
    key      = ai_cfg.get("key", "")
    model    = ai_cfg.get("model", "")
    url      = ai_cfg.get("url", "")
    if isinstance(key, str) and key.startswith("•••••"):
        key = load_providers().get("AI_API", {}).get("key", "")
    try:
        if provider == "gemini":
            import google.generativeai as genai
            genai.configure(api_key=key)
            resp = genai.GenerativeModel(model or "gemini-2.5-flash").generate_content("Say OK in 3 words")
            return {"status": "ok", "message": resp.text.strip()[:120]}
        elif provider == "anthropic":
            import anthropic as _anthropic
            client = _anthropic.Anthropic(api_key=key)
            msg = client.messages.create(
                model=model or "claude-sonnet-4-6",
                max_tokens=16,
                messages=[{"role": "user", "content": "Say OK in 3 words"}],
            )
            return {"status": "ok", "message": msg.content[0].text.strip()}
        elif provider == "openai":
            import openai as _openai
            client = _openai.OpenAI(api_key=key)
            resp = client.chat.completions.create(
                model=model or "gpt-4o-mini",
                messages=[{"role": "user", "content": "Say OK in 3 words"}],
                max_tokens=16,
            )
            return {"status": "ok", "message": resp.choices[0].message.content.strip()}
        elif provider in ("ollama", "custom"):
            import requests as _req
            base = (url or "http://localhost:11434").rstrip("/")
            r = _req.post(f"{base}/api/generate",
                          json={"model": model, "prompt": "Say OK", "stream": False},
                          timeout=10)
            r.raise_for_status()
            return {"status": "ok", "message": r.json().get("response", "")[:120]}
        else:
            return JSONResponse(content={"status": "error", "message": f"Unknown provider: {provider}"})
    except Exception as exc:
        return JSONResponse(content={"status": "error", "message": str(exc)[:200]})


# ─────────────────────────────────────────────────────────────────────────────
# JSON ROUTES — Streamlit UI consumers
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/macro/sensors")
def route_macro_sensors():
    """Full sensors dict as JSON — used by Macro Weather and Nexus tabs."""
    sensors, source = _get_sensors()
    return JSONResponse(content=jsonable_encoder({
        "sensors":      _sanitize(sensors),
        "source":       source,
        "cache_age_min": _cache_age_min() if source == "cache" else 0,
    }))


@app.get("/macro/corr")
def route_macro_corr():
    """Asset correlation matrix for the Macro Weather tab."""
    corr_df = macro_engine.get_correlation_matrix()
    if corr_df is None:
        return JSONResponse(content={"error": "unavailable", "data": None})
    return JSONResponse(content={"data": corr_df.round(2).to_dict()})


@app.get("/macro/intel")
def route_macro_intel():
    """Raw intel stories + events. UI filters dismissed locally."""
    cached = _load_macro_cache()
    if cached and "news_lines" in cached:
        news_lines = cached["news_lines"]
        events     = cached.get("events", [])
        source     = "cache"
    else:
        news_lines, events, source = [], [], "empty"

    try:
        stories, live_events = macro_engine.get_intel_feeds(dismissed_tuple=())
        if not events:
            events = live_events
    except Exception:
        stories = []

    serialized = []
    for s in stories:
        safe = {k: v for k, v in s.items() if not isinstance(v, (bytes, type(None).__class__.__mro__[-1]))}
        safe["age_hours"] = float(safe.get("age_hours", 0))
        serialized.append(safe)

    return JSONResponse(content={
        "stories":    serialized,
        "events":     events,
        "news_lines": news_lines,
        "source":     source,
    })


@app.get("/rotation")
def route_rotation():
    """
    Sector rotation payload: CRS/ROC metrics for all 10 sector SPDRs vs SPY.
    Cached via fetch_sector_closes() (4h TTL in shared_data).
    Returns graceful error shape on data failure — never raises.
    """
    providers = load_providers()
    fred_key  = providers.get("FRED_API", {}).get("key")
    try:
        closes = fetch_sector_closes()
        if closes.empty:
            return {"error": "Data unavailable", "sectors": [], "camd_alerts": [],
                    "spy_roc_21": None, "macro_env": None, "timestamp": None}
        return sector_rotation_engine.run(closes, fred_key)
    except Exception as e:
        return {"error": str(e), "sectors": [], "camd_alerts": [],
                "spy_roc_21": None, "macro_env": None, "timestamp": None}


@app.get("/ohlcv")
def route_ohlcv(
    symbol: str = Query(...),
    mode: str = Query("swing"),
):
    """OHLCV + indicator DataFrames for all mode TFs — used by UI chart rendering."""
    mode = MODE_ALIASES.get(mode.lower(), "swing")
    tfs  = _get_ohlcv_cached(symbol, mode)
    if not tfs or "error" in tfs:
        return JSONResponse(content={"error": f"failed to load {symbol}", "tfs": {}})
    result = {}
    for tf_key, df in tfs.items():
        if isinstance(df, pd.DataFrame) and not df.empty:
            result[tf_key] = _df_to_records(df)
    return JSONResponse(content={"symbol": symbol, "mode": mode, "tfs": result})


@app.get("/smc/json")
def route_smc_json(
    symbol: str = Query(...),
    ltf: str = Query("4h"),
    htf: str = Query(""),
    use_ai: bool = Query(False),
):
    """Full SMC data dicts + serialised DataFrames for the Structure Map tab."""
    ltf_df, ltf_err = _fetch_smc_df(symbol, ltf)
    if ltf_err or ltf_df is None or (hasattr(ltf_df, "empty") and ltf_df.empty):
        return JSONResponse(content={"error": f"LTF load failed: {ltf_err or 'empty'}"})

    ltf_smc = smc_engine.run(ltf_df)
    if "error" in ltf_smc:
        return JSONResponse(content={"error": f"SMC engine ({ltf}): {ltf_smc['error']}"})

    _htf_all     = smc_engine.load_htf_levels()
    _sym_key     = symbol.split("/")[0].upper()
    asset_levels = _htf_all.get(_sym_key)
    flat_levels  = smc_engine.flatten_levels(asset_levels) if asset_levels else []
    if asset_levels:
        smc_engine.tag_htf_confluence(ltf_smc, asset_levels)

    htf_smc = None
    htf_df  = None
    if htf and htf != ltf:
        htf_df_raw, htf_err = _fetch_smc_df(symbol, htf)
        if not htf_err and htf_df_raw is not None:
            htf_smc = smc_engine.run(htf_df_raw)
            if "error" in htf_smc:
                htf_smc = None
            else:
                htf_df = htf_df_raw

    ai_narrative = None
    if use_ai and htf_smc is not None and htf_df is not None:
        providers = load_providers()
        ai_cfg    = providers.get("AI_API", {})
        if ai_cfg.get("key"):
            try:
                ai_narrative = banshee_ai.smc_analysis(
                    symbol=symbol,
                    htf_tf=htf, htf_df=htf_df, htf_smc=htf_smc,
                    ltf_tf=ltf, ltf_df=ltf_df, ltf_smc=ltf_smc,
                    cfg=ai_cfg, flat_levels=flat_levels,
                )
            except Exception as e:
                ai_narrative = f"AI error: {e}"

    htf_state = htf_smc.get("current_state", "UNDEFINED") if htf_smc else None
    ltf_state = ltf_smc.get("current_state", "UNDEFINED")
    if htf_state:
        alignment = (f"ALIGNED ({htf_state})" if htf_state == ltf_state
                     else f"CONFLICTED — HTF {htf_state} vs LTF {ltf_state}")
    else:
        alignment = f"LTF only: {ltf_state}"

    return JSONResponse(content=jsonable_encoder(_sanitize({
        "symbol":       symbol,
        "ltf":          ltf,
        "htf":          htf or None,
        "ltf_smc":      ltf_smc,
        "htf_smc":      htf_smc,
        "ltf_df":       _df_to_records(ltf_df),
        "htf_df":       _df_to_records(htf_df) if htf_df is not None else [],
        "asset_levels": asset_levels,
        "flat_levels":  flat_levels,
        "alignment":    alignment,
        "ai_narrative": ai_narrative,
    })))


@app.get("/predator/briefing")
def route_predator_briefing():
    """Latest Daily Predator briefing JSON."""
    briefing = predator_engine.load_latest_briefing()
    return JSONResponse(content=briefing or {})


@app.get("/predator/config")
def route_predator_config_get():
    """Current Predator configuration."""
    return JSONResponse(content=predator_engine.load_predator_config())


class PredatorConfigBody(BaseModel):
    config: dict


@app.post("/predator/config")
def route_predator_config_save(body: PredatorConfigBody):
    """Save Predator configuration."""
    predator_engine.save_predator_config(body.config)
    return {"status": "saved"}


class PredatorRunRequest(BaseModel):
    watchlist: list[str] = []
    force: bool = False
    manual_stories: list = []


@app.post("/predator/run")
def route_predator_run(req: PredatorRunRequest):
    """Trigger a Daily Predator cycle."""
    providers = load_providers()
    ai_cfg    = providers.get("AI_API")
    if not ai_cfg or not ai_cfg.get("key"):
        return JSONResponse(content={"error": "No AI key configured"}, status_code=400)
    try:
        briefing = predator_engine.run_daily_cycle(
            ai_cfg, watchlist_symbols=req.watchlist, force=req.force,
            manual_stories=req.manual_stories
        )
        return JSONResponse(content=briefing or {})
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)


class AIBriefingRequest(BaseModel):
    symbol: str
    mode: str = "swing"
    manual_stories: list = []
    tab: str = "nexus"  # "nexus" | "smc" | "gh"


@app.post("/ai/briefing", response_class=PlainTextResponse)
def route_ai_briefing(req: AIBriefingRequest):
    """Generate an AI synthesis briefing for the React UI tabs."""
    mode = MODE_ALIASES.get(req.mode.lower(), "swing")

    providers = load_providers()
    cfg       = providers.get("AI_API")
    if not cfg or not cfg.get("key"):
        return "No AI key configured. Add one in ⚙️ Settings."

    # ── Macro tab: macro-environment-only briefing, no OHLCV needed ───────────
    if req.tab == "macro":
        mac_data, _src = _get_sensors()
        cached         = _load_macro_cache()
        news_lines     = cached.get("news_lines", []) if cached else []
        predator_brief = predator_engine.load_latest_briefing()
        predator_lines = predator_engine.get_briefing_for_nexus(predator_brief)
        if predator_lines:
            news_lines = [predator_lines] + news_lines
        # Build rotation context (non-blocking — fails silently)
        rotation_ctx = ""
        try:
            closes = fetch_sector_closes()
            if not closes.empty:
                rot = sector_rotation_engine.run(closes, providers.get("FRED_API", {}).get("key"))
                if rot.get("sectors"):
                    top  = [s for s in rot["sectors"] if s["roc_21"] > 0][:3]
                    bot  = [s for s in rot["sectors"] if s["roc_21"] < 0][-2:]
                    top_lines = [
                        f"{s['name']} ({s['roc_21']:+.1f}% 21D RS{' CAMD' if s['camd'] else ''})"
                        for s in top
                    ]
                    rotation_ctx = "Top flow: " + ", ".join(top_lines)
                    if bot:
                        rotation_ctx += "\nWeakest: " + ", ".join(
                            f"{s['name']} ({s['roc_21']:+.1f}% 21D RS)" for s in bot
                        )
                    if rot.get("macro_env") and rot["macro_env"].get("interpretation"):
                        rotation_ctx += f"\n{rot['macro_env']['interpretation']}"
        except Exception:
            pass

        prompt = banshee_ai.build_macro_prompt(mac_data, news_lines, rotation_context=rotation_ctx)
        return banshee_ai.call_ai(cfg, prompt)

    # ── SMC tab: dedicated dual-TF pathway (same engine as V4 Streamlit) ──────
    if req.tab == "smc":
        htf_tf = "1d" if mode == "swing" else "4h"
        ltf_tf = "4h" if mode == "swing" else "1h"

        ltf_df, ltf_err = _fetch_smc_df(req.symbol, ltf_tf)
        if ltf_err or ltf_df is None or (hasattr(ltf_df, "empty") and ltf_df.empty):
            return f"SMC data unavailable ({ltf_tf}): {ltf_err or 'empty'}"
        ltf_smc = smc_engine.run(ltf_df)
        if "error" in ltf_smc:
            return f"SMC engine error ({ltf_tf}): {ltf_smc['error']}"

        htf_df, htf_err = _fetch_smc_df(req.symbol, htf_tf)
        if htf_err or htf_df is None or (hasattr(htf_df, "empty") and htf_df.empty):
            return f"SMC data unavailable ({htf_tf}): {htf_err or 'empty'}"
        htf_smc = smc_engine.run(htf_df)
        if "error" in htf_smc:
            return f"SMC engine error ({htf_tf}): {htf_smc['error']}"

        _htf_all     = smc_engine.load_htf_levels()
        _sym_key     = req.symbol.split("/")[0].upper()
        asset_levels = _htf_all.get(_sym_key)
        flat_levels  = smc_engine.flatten_levels(asset_levels) if asset_levels else []

        return banshee_ai.smc_analysis(
            symbol=req.symbol,
            htf_tf=htf_tf, htf_df=htf_df, htf_smc=htf_smc,
            ltf_tf=ltf_tf, ltf_df=ltf_df, ltf_smc=ltf_smc,
            cfg=cfg, flat_levels=flat_levels,
        )

    # ── GH + Nexus tabs: macro/micro synthesis pathway ────────────────────────
    mac_data, _src = _get_sensors()
    cached         = _load_macro_cache()
    news_lines     = cached.get("news_lines", []) if cached else []

    predator_brief = predator_engine.load_latest_briefing()
    predator_lines = predator_engine.get_briefing_for_nexus(predator_brief)
    if predator_lines:
        news_lines = [predator_lines] + news_lines

    tfs = _get_ohlcv_cached(req.symbol, mode)
    if not tfs or "error" in tfs:
        return f"Error: Failed to load data for {req.symbol}."

    mic_data = micro_engine.run_analysis(
        req.symbol, mode, tfs,
        domino_phase=mac_data.get("domino_phase", 0),
        sensors=mac_data,
    )
    if "error" in mic_data:
        return f"Micro analysis error: {mic_data['error']}"

    # GH always needs 1d data — fetch separately when not present (e.g. sniper mode)
    def _get_1d_df():
        df = tfs.get("1d")
        if df is not None and not df.empty:
            return df
        df2, _ = _fetch_smc_df(req.symbol, "1d")
        return df2

    geo_harmonic_context = ""
    try:
        import geometric_harmonic as gh
        _bias_sym = {"floor": "▲", "ceiling": "▼", "mixed": "◈"}
        _gh_df = _get_1d_df()
        if _gh_df is not None and not _gh_df.empty:
            _gh_result = gh.run(_gh_df, multi_window=True)
            _zones = _gh_result.get("hot_zones", [])[:5]
            if _zones:
                _gh_lines = []
                for z in _zones:
                    _tier = "macro" if any("macro" in s for s in z.get("sources", [])) else "local"
                    _bs   = _bias_sym.get(z.get("bias", "mixed"), "◈")
                    _gh_lines.append(
                        f"  {_bs} ${z['price']:,.2f}  dist {z['dist_pct']:+.1f}%"
                        f"  [{_tier}]  sources: {', '.join(z.get('sources', []))}"
                    )
                geo_harmonic_context = (
                    "Top Geo Harmonic Hot Zones (ranked by confluence weight):\n"
                    + "\n".join(_gh_lines)
                )
    except Exception:
        pass

    if req.tab == "gh":
        try:
            import xabcd_scanner as _xabcd
            _xabcd_df = _get_1d_df()
            if _xabcd_df is not None and not _xabcd_df.empty:
                _patterns = _xabcd.scan(_xabcd_df)
                if _patterns:
                    _lines = []
                    for p in _patterns[:4]:
                        status = "CONFIRMED" if p.get("confirmed") else "FORMING"
                        _lines.append(
                            f"  {p['pattern']} ({status}) — PRZ: ${p.get('prz_lo', 0):,.2f}–${p.get('prz_hi', 0):,.2f}"
                        )
                    xabcd_context = "XABCD Harmonic Patterns:\n" + "\n".join(_lines)
                    geo_harmonic_context = (geo_harmonic_context + "\n\n" + xabcd_context).strip()
        except Exception:
            pass

    prompt = banshee_ai.build_banshee_prompt(
        mac_data, mic_data, news_lines, req.manual_stories, include_macro=True,
        geo_harmonic_context=geo_harmonic_context, tab=req.tab,
    )
    return banshee_ai.call_ai_briefing(cfg, prompt)


# ─────────────────────────────────────────────────────────────────────────────
# ROUTE 11 — Journal: annotate / set outcome / signal log
# ─────────────────────────────────────────────────────────────────────────────

class JournalOpenRequest(BaseModel):
    symbol: str
    direction: str          # "long" or "short"
    entry_price: float
    stop_price: float
    target_price: float
    position_usd: float = 5000.0
    verdict: str = ""
    regime: str = ""
    macro_regime: str = ""
    edge: str = ""
    mode: str = ""
    notes: str = ""


class JournalCloseRequest(BaseModel):
    trade_id: int
    exit_price: float
    notes: str = ""
    exit_reason: str | None = None


class JournalSyncAlpacaRequest(BaseModel):
    pass


class JournalAnnotateRequest(BaseModel):
    trade_id: int
    note: str = ""
    signal_correct: bool | None = None
    exit_reason: str | None = None


@app.post("/journal/open")
def route_journal_open(body: JournalOpenRequest):
    """Open a new paper trade. Called by agent after synthesize_nexus + build_execution_plan."""
    import paper_trader
    direction = body.direction.lower()
    if direction not in ("long", "short"):
        return JSONResponse(content={"error": "direction must be 'long' or 'short'"}, status_code=400)

    banshee_ctx = {
        "verdict":      body.verdict,
        "regime":       body.regime,
        "macro_regime": body.macro_regime,
        "edge":         body.edge,
        "mode":         body.mode,
    }
    result = paper_trader.place_paper_trade(
        symbol=body.symbol.upper(),
        direction=direction,
        entry_price=body.entry_price,
        stop_price=body.stop_price,
        target_price=body.target_price,
        banshee_context=banshee_ctx,
        position_usd=body.position_usd,
    )
    if body.notes and result.get("trade_id"):
        paper_trader.annotate_trade(result["trade_id"], body.notes)
    return result


@app.post("/journal/close")
def route_journal_close(body: JournalCloseRequest):
    """Close a specific open trade by ID. Routes through Core so Streamlit never writes directly."""
    import paper_trader
    ok = paper_trader.close_trade(
        trade_id=body.trade_id,
        exit_price=body.exit_price,
        notes=body.notes,
        exit_reason=body.exit_reason,
    )
    if not ok:
        return JSONResponse(content={"error": f"trade {body.trade_id} not found"}, status_code=404)
    return {"status": "closed", "trade_id": body.trade_id}


@app.post("/journal/sync-alpaca")
def route_journal_sync_alpaca():
    """Sync open trade levels against Alpaca positions. Returns number of trades updated."""
    import paper_trader
    n = paper_trader.sync_alpaca_status()
    return {"updated": n}


@app.post("/journal/annotate")
def route_journal_annotate(body: JournalAnnotateRequest):
    """
    Swiss-army journal update: append a note, set signal_correct, or set exit_reason.
    All fields are optional — pass whichever you want to update.
    Works on open and closed trades.
    """
    import paper_trader
    if not body.note and body.signal_correct is None and body.exit_reason is None:
        return JSONResponse(content={"error": "provide at least one of: note, signal_correct, exit_reason"}, status_code=400)

    ok = paper_trader.set_signal_outcome(
        trade_id=body.trade_id,
        signal_correct=body.signal_correct,
        exit_reason=body.exit_reason,
        note=body.note,
    )
    if not ok:
        return JSONResponse(content={"error": f"trade {body.trade_id} not found"}, status_code=404)
    return {"status": "updated", "trade_id": body.trade_id}


@app.get("/journal/signal-log")
def route_journal_signal_log():
    """
    Return all trades annotated with signal_correct and/or exit_reason,
    plus aggregate stats broken down by regime and exit_reason.
    """
    import paper_trader
    all_trades = paper_trader.get_all_trades()

    # Split into judged (signal_correct set) and full closed set
    judged   = [t for t in all_trades if t.get("signal_correct") is not None]
    correct  = [t for t in judged     if t.get("signal_correct") is True]
    closed   = [t for t in all_trades if t.get("status") == "closed"]

    # Regime breakdown — signal correct rate per regime
    regime_stats: dict = {}
    for t in judged:
        r = t.get("regime") or "unknown"
        bucket = regime_stats.setdefault(r, {"judged": 0, "correct": 0})
        bucket["judged"] += 1
        if t.get("signal_correct"):
            bucket["correct"] += 1
    for r, b in regime_stats.items():
        b["correct_rate_pct"] = round(b["correct"] / b["judged"] * 100, 1) if b["judged"] else None

    # Exit reason breakdown
    exit_counts: dict = {}
    for t in closed:
        reason = t.get("exit_reason") or "unset"
        exit_counts[reason] = exit_counts.get(reason, 0) + 1

    return JSONResponse(content={
        "total_trades":     len(all_trades),
        "judged_trades":    len(judged),
        "signal_correct_rate_pct": round(len(correct) / len(judged) * 100, 1) if judged else None,
        "regime_breakdown": regime_stats,
        "exit_reason_breakdown": exit_counts,
        "judged_trade_list": judged,
    })


@app.get("/journal/feedback-synthesis")
def route_journal_feedback_synthesis():
    """
    Autonomous Agent Step 3: AI synthesis cross-referencing judged closed trades with the
    Daily Predator briefing active on each trade's exit day.

    Returns a narrative identifying regime patterns, briefing-vs-outcome correlations,
    and suggested rule adjustments.
    """
    import paper_trader
    import banshee_ai
    import predator_engine

    all_trades    = paper_trader.get_all_trades()
    judged_closed = [
        t for t in all_trades
        if t.get("status") == "closed" and t.get("signal_correct") is not None
    ]

    if not judged_closed:
        return JSONResponse(content={
            "narrative":         "No judged closed trades yet. Use /journal/annotate to record signal outcomes.",
            "trade_count":       0,
            "briefings_matched": 0,
            "trades_analyzed":   0,
        })

    # Index all briefings by date
    briefings_by_date: dict = {}
    if os.path.exists(predator_engine.BRIEFINGS_PATH):
        with open(predator_engine.BRIEFINGS_PATH, "r", encoding="utf-8") as _f:
            for _line in _f:
                stripped = _line.strip()
                if stripped:
                    try:
                        b = json.loads(stripped)
                        briefings_by_date[b["date"]] = b
                    except Exception:
                        pass

    # Build per-trade context blocks (cap at last 30)
    trade_blocks = []
    matched = 0
    for t in judged_closed[-30:]:
        exit_date = (t.get("exit_time") or "")[:10]
        briefing  = briefings_by_date.get(exit_date)
        if briefing:
            matched += 1

        sc    = "CORRECT" if t.get("signal_correct") else "WRONG"
        block = (
            f"Trade #{t['id']} | {t.get('symbol','?')} {t.get('direction','?')} | "
            f"Regime: {t.get('regime','unknown')} | PnL: {t.get('pnl_pct','?')}% | "
            f"Exit: {t.get('exit_reason') or 'unset'} | Signal: {sc}"
        )
        if briefing:
            wl_headlines = "; ".join(
                ev.get("headline", "") for ev in briefing.get("watchlist_events", [])[:3]
            )
            block += (
                f"\n  Predator ({exit_date}): tone={briefing.get('macro_tone','?')} "
                f"risk={briefing.get('risk_level','?')}/5 | {briefing.get('top_story','')}"
            )
            if wl_headlines:
                block += f"\n  Watchlist events: {wl_headlines}"
        else:
            block += f"\n  Predator ({exit_date}): no briefing on file"

        trade_blocks.append(block)

    prompt = f"""AUTONOMOUS AGENT FEEDBACK SYNTHESIS — Trade Outcome vs Predator Intelligence

Analyzing {len(judged_closed)} judged closed trades. {matched} had a Predator briefing on the exit day.

TRADE LOG:
{chr(10).join(trade_blocks)}

QUESTIONS TO ANSWER:
1. REGIME PATTERNS: In which regimes is Banshee directionally correct even when trades don't profit? Where is it systematically wrong?
2. PREDATOR CORRELATION: On days when trades stopped out, what did the Predator say? Was the macro_tone and risk_level consistent with the loss?
3. BLIND SPOTS: Was Banshee trading against the macro briefing on any losing trades? Give specific examples using trade IDs.
4. ADJUSTMENTS: What 2-3 concrete rule changes would improve signal quality? Be specific (e.g., "avoid longs when risk_level >= 4 and macro_tone is BEARISH").

Keep your response to 400 words. Be direct. Use trade IDs and regime names to back up every claim."""

    providers = load_providers()
    ai_cfg    = providers.get("AI_API", {})

    if not ai_cfg.get("key"):
        return JSONResponse(content={
            "narrative":         "AI not configured — set AI_API key in providers.",
            "trade_count":       len(judged_closed),
            "briefings_matched": matched,
            "trades_analyzed":   len(trade_blocks),
        })

    system = (
        "You are Banshee Pro's Autonomous Agent, its self-correction engine. "
        "Your job is to identify systematic errors in trade signals by cross-referencing "
        "trade outcomes with macro intelligence briefings. "
        "Be specific: name regimes, cite trade IDs, and propose actionable rule changes. "
        "No hedging. Every sentence should inform a concrete rule improvement."
    )

    narrative = banshee_ai.call_ai(ai_cfg, prompt, system_prompt_override=system)

    return JSONResponse(content={
        "narrative":         narrative,
        "trade_count":       len(judged_closed),
        "briefings_matched": matched,
        "trades_analyzed":   len(trade_blocks),
    })


# ─────────────────────────────────────────────────────────────────────────────
# ROUTE — Strategy data (React Signal Lab)
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/strategies/data")
def route_strategies_data():
    """Return strategies.json as a JSON object for the React Signal Lab page."""
    if not os.path.exists(_STRATEGIES_FILE):
        return {}
    try:
        with open(_STRATEGIES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


# ─────────────────────────────────────────────────────────────────────────────
# ROUTE — Journal trades (React Trade Journal)
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/journal/trades")
def route_journal_trades():
    """Return all trades + stats for the React Trade Journal page."""
    import paper_trader
    return {
        "trades": paper_trader.get_all_trades(),
        "stats":  paper_trader.get_stats(),
    }


class JournalUpdateOutcomeRequest(BaseModel):
    trade_id: int
    signal_correct: str | None = None  # UI sends "yes"/"no"/"partial"/null
    exit_reason: str | None = None
    note: str = ""


@app.post("/journal/update-outcome")
def route_journal_update_outcome(body: JournalUpdateOutcomeRequest):
    """Set signal quality fields on a trade (open or closed)."""
    import paper_trader
    # Map string values from UI to bool/None/passthrough for set_signal_outcome
    sc = body.signal_correct
    if sc == "yes":
        sc_val = True
    elif sc == "no":
        sc_val = False
    else:
        sc_val = sc  # "partial" or None pass through as-is
    ok = paper_trader.set_signal_outcome(
        trade_id=body.trade_id,
        signal_correct=sc_val,
        exit_reason=body.exit_reason,
        note=body.note,
    )
    if not ok:
        return JSONResponse(
            content={"error": f"trade {body.trade_id} not found"}, status_code=404
        )
    return {"status": "updated", "trade_id": body.trade_id}


class JournalUpdateLevelsRequest(BaseModel):
    trade_id: int
    stop_price: float | None = None
    target_price: float | None = None


@app.post("/journal/update-levels")
def route_journal_update_levels(body: JournalUpdateLevelsRequest):
    """Update stop and target price on an open trade."""
    import paper_trader
    ok = paper_trader.update_trade_levels(
        trade_id=body.trade_id,
        stop_price=body.stop_price,
        target_price=body.target_price,
    )
    if not ok:
        return JSONResponse(
            content={"error": f"trade {body.trade_id} not found"}, status_code=404
        )
    return {"status": "updated", "trade_id": body.trade_id}


# ─────────────────────────────────────────────────────────────────────────────
# ROUTE 12 — Geometric Harmonic Arc Analysis
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/geo-harmonic")
def route_geo_harmonic(
    symbol:         str  = Query(...),
    n_local:        int  = Query(233),
    tf:             str  = Query("1d"),
    arithmetic_mid: bool = Query(False),
    multi_window:   bool = Query(True),
):
    """
    Geometric Harmonic analysis — macro/local Fibonacci arcs + DBSCAN hot zones.
    Uses the daily DataFrame (all available history) for ATH/ATL macro anchors.
    multi_window=True (default) runs all 3 ZigZag windows and requires 2+ source confluence.
    arithmetic_mid=True uses (ATH+ATL)/2 instead of √(ATH×ATL) as the radius endpoint.
    Returns ranked hot-zone price levels (with bias + sources) for TradingView circle placement.
    """
    import geometric_harmonic as gh
    _ghkey = f"gh:{symbol.upper()}:{tf}:{n_local}:{arithmetic_mid}:{multi_window}"
    _entry = _RESP_CACHE.get(_ghkey)
    if _entry and (time.time() - _entry["ts"]) < _RESP_TTL:
        return JSONResponse(content=_entry["res"])
    tfs = _get_ohlcv_cached(symbol, "swing")
    if not tfs or "error" in tfs:
        return JSONResponse(content={"error": f"Failed to load data for {symbol}"})
    df = tfs.get(tf)
    if df is None or (hasattr(df, "empty") and df.empty):
        valid = [k for k, v in tfs.items() if isinstance(v, pd.DataFrame) and not v.empty]
        if not valid:
            return JSONResponse(content={"error": f"No data for {symbol}"})
        df = tfs[valid[0]]
    result = gh.run(df, n_local=n_local, arithmetic_mid=arithmetic_mid,
                    multi_window=multi_window)
    if "error" not in result:
        _RESP_CACHE[_ghkey] = {"ts": time.time(), "res": result}
    return JSONResponse(content=result)


@app.get("/geo-harmonic/pine")
def route_geo_harmonic_pine(
    symbol:         str  = Query(...),
    arithmetic_mid: bool = Query(False),
    multi_window:   bool = Query(True),
):
    """
    Generate a paste-ready Pine Script v5 indicator for GH circles.
    Returns {"symbol": ..., "pine_script": "..."}.
    Paste the pine_script into TradingView's Pine Editor on a 1D chart.
    """
    import geometric_harmonic as gh
    tfs = _get_ohlcv_cached(symbol, "swing")
    if not tfs or "error" in tfs:
        return JSONResponse(content={"error": f"Failed to load data for {symbol}"})
    df = tfs.get("1d")
    if df is None or (hasattr(df, "empty") and df.empty):
        valid = [k for k, v in tfs.items() if isinstance(v, pd.DataFrame) and not v.empty]
        if not valid:
            return JSONResponse(content={"error": f"No data for {symbol}"})
        df = tfs[valid[0]]
    result = gh.run(df, arithmetic_mid=arithmetic_mid, multi_window=multi_window)
    if "error" in result:
        return JSONResponse(content={"error": result["error"]})
    pine = gh.generate_pine_script(result, symbol=symbol)
    return JSONResponse(content={"symbol": symbol, "pine_script": pine})


@app.get("/xabcd")
def route_xabcd(
    symbol: str  = Query(...),
    tf:     str  = Query("1d"),
    pct:    float = Query(0.03),
):
    """
    XABCD Harmonic Pattern Scanner — Gartley, Bat, Butterfly, Crab, Shark, 5-0.
    Uses percentage-reversal ZigZag (pct=0.03 default) on the daily timeframe.
    Returns confirmed patterns (D formed) and forming patterns (PRZ projected).
    """
    import xabcd_scanner as xs
    _xkey = f"xabcd:{symbol.upper()}:{tf}:{pct}"
    _entry = _RESP_CACHE.get(_xkey)
    if _entry and (time.time() - _entry["ts"]) < _RESP_TTL:
        return JSONResponse(content=_entry["res"])
    tfs = _get_ohlcv_cached(symbol, "swing")
    if not tfs or "error" in tfs:
        return JSONResponse(content={"error": f"Failed to load data for {symbol}"})
    df = tfs.get(tf)
    if df is None or (hasattr(df, "empty") and df.empty):
        valid = [k for k, v in tfs.items() if isinstance(v, pd.DataFrame) and not v.empty]
        if not valid:
            return JSONResponse(content={"error": f"No data for {symbol}"})
        df = tfs[valid[0]]
    result = xs.scan(df, pct=pct)
    if "error" not in result:
        _RESP_CACHE[_xkey] = {"ts": time.time(), "res": result}
    return JSONResponse(content=result)


# ─────────────────────────────────────────────────────────────────────────────
# BACKGROUND SCHEDULER — macro refresh, paper trade sync, Predator daily
# Moved here from app.py so it runs 24/7 with Core regardless of UI state.
# ─────────────────────────────────────────────────────────────────────────────

def _bg_refresh_macro():
    try:
        providers = load_providers()
        fred_key  = providers.get("FRED_API", {}).get("key")
        flight            = macro_engine.get_flight_data()
        _, liq_chg        = macro_engine.get_fed_liquidity(fred_key)
        sensors           = macro_engine.compute_sensors(flight, liq_chg)
        stories, events   = macro_engine.get_intel_feeds(dismissed_tuple=())
        news_lines        = macro_engine.build_news_prompt_lines(stories)
        _save_macro_cache(sensors, news_lines, events)
    except Exception:
        pass


def _bg_sync_paper_trades():
    try:
        import paper_trader
        paper_trader.sync_alpaca_status()
    except Exception:
        pass


def _bg_check_kill_switch():
    try:
        import paper_trader as _pt
        sensors, _ = _get_sensors()
        domino_phase = sensors.get("domino_phase", 0)
        regime       = sensors.get("regime", "UNKNOWN")
        if domino_phase >= 2:
            closed = _pt.close_all_open_trades(
                note=f"Kill switch (background): CRACK DETECTED (domino_phase={domino_phase})"
            )
            if closed:
                _save_kill_switch_state({
                    "fired":            True,
                    "fired_at":         datetime.now(timezone.utc).isoformat(),
                    "positions_closed": closed,
                    "domino_phase":     domino_phase,
                    "regime":           regime,
                })
        else:
            _save_kill_switch_state({
                "fired": False, "fired_at": None,
                "positions_closed": [], "domino_phase": domino_phase, "regime": regime,
            })
    except Exception:
        pass


def _bg_predator_daily():
    try:
        if predator_engine.today_briefing_exists():
            return
        providers = load_providers()
        ai_cfg    = providers.get("AI_API")
        if not ai_cfg or not ai_cfg.get("key"):
            return
        pred_cfg  = predator_engine.load_predator_config()
        predator_engine.run_daily_cycle(ai_cfg, watchlist_symbols=pred_cfg.get("watchlist", []), force=False)
    except Exception:
        pass


_PREWARM_SYMS = [
    "BTC/USD","ETH/USD","SOL/USD","XRP/USD","BNB/USD","DOGE/USD","ADA/USD",
    "AVAX/USD","DOT/USD","MATIC/USD","LINK/USD","UNI/USD","ATOM/USD",
    "LTC/USD","BCH/USD","NEAR/USD","HBAR/USD","XLM/USD","TAO/USD","HYPE/USD",
]

def _bg_prewarm_ohlcv():
    """Fetch OHLCV for all watchlist symbols on startup so the UI loads instantly."""
    import time as _time
    for sym in _PREWARM_SYMS:
        try:
            _get_ohlcv_cached(sym, "swing")
            _time.sleep(0.3)   # gentle pacing — avoid exchange rate limits
        except Exception:
            pass


try:
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.cron import CronTrigger as _CronTrigger

    _bg_scheduler = BackgroundScheduler(daemon=True)
    from datetime import datetime as _dt, timedelta as _td
    _bg_scheduler.add_job(_bg_prewarm_ohlcv, "date", run_date=_dt.now() + _td(seconds=5), id="core_prewarm")
    _bg_scheduler.add_job(_bg_refresh_macro,       "interval", minutes=15, id="core_macro_heartbeat")
    _bg_scheduler.add_job(_bg_sync_paper_trades,   "interval", minutes=15, id="core_paper_sync")
    _bg_scheduler.add_job(_bg_check_kill_switch,   "interval", minutes=15, id="core_kill_switch")

    _pred_cfg_init = predator_engine.load_predator_config()
    _sched_time    = _pred_cfg_init.get("schedule_time", "08:00")
    try:
        _ph, _pm = [int(x) for x in _sched_time.split(":")]
    except Exception:
        _ph, _pm = 8, 0
    _bg_scheduler.add_job(_bg_predator_daily, _CronTrigger(hour=_ph, minute=_pm), id="core_predator_daily")
    _bg_scheduler.start()
except ImportError:
    pass  # APScheduler optional; heartbeats disabled if not installed


# ─────────────────────────────────────────────────────────────────────────────
# SHUTDOWN
# ─────────────────────────────────────────────────────────────────────────────

# ─────────────────────────────────────────────────────────────────────────────
# ROUTE 13 — Watchlist Presets
# ─────────────────────────────────────────────────────────────────────────────

_PRESETS_PATH = Path(__file__).parent / "banshee_presets.json"

def _load_presets() -> list:
    try:
        data = json.loads(_PRESETS_PATH.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return data
        # migrate old dict format {name: [syms]} → new array format
        return [{"id": k, "name": k, "syms": v} for k, v in data.items()]
    except Exception:
        return []

def _save_presets(presets: list):
    _PRESETS_PATH.write_text(json.dumps(presets, indent=2), encoding="utf-8")

@app.get("/presets")
def route_presets_get():
    return {"presets": _load_presets()}

@app.post("/presets")
def route_presets_save(body: dict = Body(...)):
    presets = body.get("presets", [])
    if not isinstance(presets, list):
        raise HTTPException(status_code=422, detail="presets must be a list")
    _save_presets(presets)
    return {"saved": len(presets)}


# ─────────────────────────────────────────────────────────────────────────────
# ROUTE 14 — Portfolio CRUD
# ─────────────────────────────────────────────────────────────────────────────

_PORTFOLIO_PATH = Path(__file__).parent / "banshee_portfolio.json"

def _load_portfolios() -> dict:
    if _PORTFOLIO_PATH.exists():
        try:
            return json.loads(_PORTFOLIO_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"portfolios": []}

def _save_portfolios(data: dict) -> None:
    _PORTFOLIO_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")

@app.get("/portfolios")
def get_portfolios():
    return _load_portfolios()

@app.post("/portfolios")
def create_portfolio(body: dict = Body(...)):
    data = _load_portfolios()
    portfolio = {
        "id": str(uuid.uuid4()),
        "preset_id": body.get("preset_id", ""),
        "name": body.get("name", "My Portfolio"),
        "thesis": body.get("thesis", ""),
        "holdings": body.get("holdings", []),
        "grade_history": [],
    }
    data["portfolios"].append(portfolio)
    _save_portfolios(data)
    return portfolio

@app.put("/portfolios/{portfolio_id}")
def update_portfolio(portfolio_id: str, body: dict = Body(...)):
    data = _load_portfolios()
    for p in data["portfolios"]:
        if p["id"] == portfolio_id:
            if "holdings" in body:
                p["holdings"] = body["holdings"]
            if "thesis" in body:
                p["thesis"] = body["thesis"]
            if "name" in body:
                p["name"] = body["name"]
            _save_portfolios(data)
            return p
    return JSONResponse(status_code=404, content={"error": "Portfolio not found"})


def fetch_all_radar_for_syms(syms: list) -> dict:
    """Fetch radar data for a list of symbols. Returns {sym: radar_result}."""
    cached_macro = _load_macro_cache()
    radar_sensors = cached_macro["mac_data"] if cached_macro and "mac_data" in cached_macro else None
    result = {}
    for sym in syms:
        try:
            tfs = _get_ohlcv_cached(sym, "swing")
            if not tfs or "error" in tfs:
                continue
            r = micro_engine.run_analysis(sym, "swing", tfs, sensors=radar_sensors)
            if "error" not in r:
                result[sym] = r
        except Exception:
            pass
    return result


def _join_names(names: list) -> str:
    """'A' / 'A and B' — plain-English join for at most two names."""
    if not names:
        return ""
    return names[0] if len(names) == 1 else " and ".join(names[:2])


def _build_rotation_note(fred_key):
    """Plain-English market sector-rotation note for the Portfolio page.

    Pure information — where market money is flowing right now — NOT a grade
    input and not a judgment on the user's basket. Mirrors the /rotation data
    path. Returns None on any failure (the UI just omits the section)."""
    try:
        closes = fetch_sector_closes()
        if closes.empty:
            return None
        rot = sector_rotation_engine.run(closes, fred_key)
        sectors = rot.get("sectors") or []
        if not sectors:
            return None
        # sectors arrive sorted by 21-day relative strength, strongest first.
        inflows  = [s for s in sectors if s["roc_21"] > 0][:3]
        outflows = [s for s in reversed(sectors) if s["roc_21"] < 0][:3]
        parts = []
        if inflows:
            parts.append("into "  + _join_names([s["name"] for s in inflows]))
        if outflows:
            parts.append("out of " + _join_names([s["name"] for s in outflows]))
        summary = ("Money is rotating " + ", ".join(parts) + ".") if parts \
                  else "Sector flows are mixed — no clear rotation right now."
        return {
            "summary":        summary,
            "inflows":        [{"name": s["name"], "roc_21": s["roc_21"]} for s in inflows],
            "outflows":       [{"name": s["name"], "roc_21": s["roc_21"]} for s in outflows],
            "interpretation": (rot.get("macro_env") or {}).get("interpretation"),
            "spy_roc_21":     rot.get("spy_roc_21"),
        }
    except Exception as e:
        print(f"[portfolio] rotation note failed: {e}", file=sys.stderr)
        return None


@app.get("/portfolios/{portfolio_id}/analysis")
def get_portfolio_analysis(portfolio_id: str):
    import yfinance as yf

    data = _load_portfolios()
    portfolio = next((p for p in data["portfolios"] if p["id"] == portfolio_id), None)
    if not portfolio:
        return JSONResponse(status_code=404, content={"error": "Portfolio not found"})

    holdings = portfolio.get("holdings", [])
    if not holdings:
        return JSONResponse(status_code=400, content={"error": "Portfolio has no holdings"})

    syms = [h["sym"] for h in holdings]

    # yfinance uses "BTC-USD" for crypto pairs, not "BTC/USD" (the app's display form)
    def _yf_symbol(s):
        s = str(s)
        return s.replace("/", "-") if "/" in s else s

    def _cls_for(h):
        c = h.get("cls")
        if c and c != "EQUITY":
            return c
        s = str(h["sym"])
        return "CRYPTO" if ("/" in s or s.upper().endswith("-USD")) else (c or "EQUITY")

    yf_map = {h["sym"]: _yf_symbol(h["sym"]) for h in holdings}

    # Fetch current prices from yfinance — include sector ETFs + SPY for blended benchmark
    sector_etfs = ["XLK", "XLF", "IBIT", "XLC", "XLE", "XLV", "XLY", "XLU", "SPY"]
    all_syms = list(dict.fromkeys(list(yf_map.values()) + sector_etfs))  # dedupe, preserve order
    try:
        tickers = yf.download(all_syms, period="1y", progress=False, auto_adjust=True)
        closes = tickers["Close"] if isinstance(tickers.columns, pd.MultiIndex) else tickers
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": f"Price fetch failed: {e}"})

    # Banshee's own radar prices assets that Yahoo can't (TAO/USD, SUI/USD are
    # absent from yfinance — "possibly delisted"). Fetch once; use it as a price
    # fallback here and for momentum scoring below.
    radar_data = fetch_all_radar_for_syms(syms)

    # Build holdings rows: price from yfinance close, falling back to radar price.
    holdings_rows = []
    for h in holdings:
        sym = h["sym"]
        yfs = yf_map[sym]
        last = closes[yfs].iloc[-1] if yfs in closes.columns else None
        current_price = float(last) if last is not None and not pd.isna(last) else 0.0
        if current_price <= 0:
            rp = radar_data.get(sym, {}).get("price")
            if isinstance(rp, (int, float)) and rp > 0:
                current_price = float(rp)
        holdings_rows.append({
            "sym": sym,
            "shares": h.get("shares", 0) or 0,
            "entry_price": h.get("entry_price"),
            "entry_date": h.get("entry_date"),
            "current_price": current_price,
            "cls": _cls_for(h),
        })

    total_value  = sum(r["shares"] * r["current_price"] for r in holdings_rows)
    equal_weight = total_value <= 0   # no share counts entered → analyse as an equal-weight basket

    import portfolio_engine as pe

    # Build the REAL weighted daily-return series from the holdings' price history,
    # so Sharpe / drawdown / alpha / beta reflect this portfolio (not a synthetic
    # scaling of the benchmark). weight_of() returns each holding's weight.
    def _weighted_returns(weight_of):
        series = None
        for r in holdings_rows:
            w = weight_of(r)
            if w <= 0:
                continue
            col = yf_map.get(r["sym"])
            if col and col in closes.columns:
                ret = closes[col].pct_change().fillna(0) * w
                series = ret if series is None else series.add(ret, fill_value=0)
        return series.dropna() if series is not None else None

    if equal_weight:
        # Equal-weight basket: 1/N each. No dollar value, but real return-based
        # risk metrics + momentum (radar edge) + sector alignment still grade it.
        n = len(holdings_rows) or 1
        weights = [{
            "sym": r["sym"], "shares": 0, "weight": round(1.0 / n, 4),
            "value": 0, "cls": r["cls"],
        } for r in holdings_rows]
        sector_weights = {}
        for r in holdings_rows:
            sector_weights[r["cls"]] = sector_weights.get(r["cls"], 0) + (1.0 / n)
        benchmark_returns = pe.build_blended_benchmark(sector_weights, closes)
        port_returns = _weighted_returns(lambda r: 1.0 / n)
        rm = pe.risk_metrics(port_returns, benchmark_returns)
        engine_result = {
            "sharpe": rm["sharpe"], "alpha": rm["alpha"], "beta": rm["beta"],
            "max_drawdown": rm["max_drawdown"], "twrr": None, "total_value": 0,
            "weights": weights, "equal_weight": True,
        }
    else:
        holdings_df = pd.DataFrame(holdings_rows)
        # Group by cls, use cls as sector proxy
        sector_weights = {}
        for r in holdings_rows:
            w = (r["shares"] * r["current_price"]) / total_value
            sector_weights[r["cls"]] = sector_weights.get(r["cls"], 0) + w
        benchmark_returns = pe.build_blended_benchmark(sector_weights, closes)
        port_returns = _weighted_returns(lambda r: (r["shares"] * r["current_price"]) / total_value)
        engine_result = pe.run(holdings_df, benchmark_returns, portfolio_returns=port_returns)
        if "error" in engine_result:
            return JSONResponse(status_code=400, content=engine_result)

    # Normalise the engine's raw `edge` (unbounded bull−bear, can be negative) to
    # the 0-100 scale score_portfolio expects — same mapping the UI uses.
    for _sym, _r in radar_data.items():
        if isinstance(_r, dict) and isinstance(_r.get("edge"), (int, float)):
            _r["edge"] = max(0.0, min(100.0, round(50 + _r["edge"] * 2.5, 1)))

    # Score the portfolio — BASKET HEALTH = current momentum + trailing-year real
    # risk. Sector alignment is NOT a grade input; it's surfaced separately below
    # as an informational market-rotation note.
    scored = pe.score_portfolio(engine_result, radar_data)

    # Market rotation note — informational context only (where market money is
    # flowing), never a judgment on the basket. Gracefully absent for all-crypto
    # books, since sector rotation is an equity-sector concept.
    rotation_note = None
    if any(r.get("cls") != "CRYPTO" for r in holdings_rows):
        rotation_note = _build_rotation_note(
            load_providers().get("FRED_API", {}).get("key"))

    # Cumulative return series (real weighted history) for the Returns chart
    returns_series = []
    if port_returns is not None and len(port_returns) > 0:
        cum = (1 + port_returns).cumprod() - 1
        for ts, v in cum.items():
            try:
                returns_series.append({
                    "time":  pd.Timestamp(ts).strftime("%Y-%m-%d"),
                    "value": round(float(v) * 100, 2),
                })
            except Exception:
                pass

    # Performance vs S&P 500 — two honest lenses:
    #   recent  : the current basket vs SPY over the last ~21 trading days
    #   overall : your actual return since entry vs SPY over each holding's own
    #             holding period (needs entry_price + entry_date) — this is what
    #             makes entry dates meaningful.
    performance = {}
    spy = closes["SPY"] if "SPY" in closes.columns else None
    try:
        if spy is not None and port_returns is not None and len(port_returns) > 5:
            spy_ret = spy.pct_change().reindex(port_returns.index).fillna(0)
            n = min(21, len(port_returns))
            p = float((1 + port_returns.tail(n)).prod() - 1) * 100
            b = float((1 + spy_ret.tail(n)).prod() - 1) * 100
            performance["recent"] = {"days": int(n), "portfolio": round(p, 1),
                                     "benchmark": round(b, 1), "vs_benchmark": round(p - b, 1)}
    except Exception:
        pass
    try:
        # Holdings with a usable entry price + date (tolerate bad dates per-row).
        dated = []
        for r in holdings_rows:
            ep, ed = r.get("entry_price"), r.get("entry_date")
            if not (ep and ep > 0 and ed and r["current_price"] > 0):
                continue
            try:
                dated.append((r, pd.Timestamp(ed)))
            except Exception:
                continue
        if dated and total_value > 0:
            # Entries can predate the 1y window (e.g. a 2022 dip buy) — fetch SPY
            # history back to the earliest entry so the benchmark spans the real period.
            start = (min(ts for _, ts in dated) - pd.Timedelta(days=5)).strftime("%Y-%m-%d")
            spy_hist = yf.download("SPY", start=start, progress=False, auto_adjust=True)
            spy_long = spy_hist["Close"] if "Close" in spy_hist else None
            if isinstance(spy_long, pd.DataFrame):
                spy_long = spy_long.iloc[:, 0]
            if spy_long is not None and len(spy_long):
                spy_now = float(spy_long.iloc[-1])
                ov_you = ov_spy = ov_w = 0.0
                for r, ts in dated:
                    after = spy_long[spy_long.index >= ts]
                    if not len(after):
                        continue
                    w = (r["shares"] * r["current_price"]) / total_value
                    ov_you += (r["current_price"] / r["entry_price"] - 1) * w
                    ov_spy += (spy_now / float(after.iloc[0]) - 1) * w
                    ov_w += w
                if ov_w > 0:
                    py, bm = ov_you / ov_w * 100, ov_spy / ov_w * 100
                    performance["overall"] = {"portfolio": round(py, 1), "benchmark": round(bm, 1),
                                              "vs_benchmark": round(py - bm, 1), "coverage": round(ov_w, 3)}
    except Exception:
        pass

    # Build full result
    result = {
        **engine_result,
        **scored,
        "returns_series": returns_series,
        "performance": performance or None,
        "rotation": rotation_note,
        "portfolio_id": portfolio_id,
        "name": portfolio.get("name", ""),
    }

    # Grade history snapshot (monthly)
    from datetime import date
    today = date.today()
    month_key = today.strftime("%Y-%m")
    grade_history = portfolio.get("grade_history", [])
    existing = next((g for g in grade_history if g["date"].startswith(month_key)), None)
    if existing is None:
        grade_history.append({"date": today.strftime("%Y-%m-01"), "month": today.strftime("%b '%y"), "grade": scored["grade"], "score": scored["score"]})
    elif scored["score"] > existing["score"]:
        existing["grade"] = scored["grade"]
        existing["score"] = scored["score"]
        if "month" not in existing:
            existing["month"] = today.strftime("%b '%y")
    portfolio["grade_history"] = grade_history
    _save_portfolios(data)
    result["grade_history"] = grade_history

    # AI commentary
    try:
        providers = load_providers()
        ai_cfg = providers.get("AI_API", {})
        if ai_cfg and ai_cfg.get("key"):
            review = banshee_ai.portfolio_review(ai_cfg, portfolio, result)
            result["ai_review"] = review.dict()
        else:
            result["ai_review"] = None
    except Exception:
        result["ai_review"] = None

    return _sanitize(result)


@app.post("/shutdown")
def route_shutdown():
    """Terminate Core (and the whole Banshee stack) cleanly. Response fires before exit."""
    import threading, os as _os
    def _exit():
        import time; time.sleep(0.4)
        _os._exit(0)
    threading.Thread(target=_exit, daemon=True).start()
    return {"status": "shutting_down"}


# ─────────────────────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print(f"Banshee Core starting on http://127.0.0.1:{PORT}")
    uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="warning")
