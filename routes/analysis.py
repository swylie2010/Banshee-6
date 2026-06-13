"""routes/analysis.py — radar, SMC, geo-harmonic, analysis tools."""

import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from fastapi import APIRouter, HTTPException, Query
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel

from core_state import (
    _sanitize, _df_to_records, MODE_ALIASES,
    _OHLCV_CACHE, _OHLCV_TTL,
    _RESP_CACHE, _RESP_TTL,
    _STRATEGIES_FILE,
    _ts, _cache_age_min, _cache_header,
    _load_macro_cache,
    check_ai_budget,
)
from shared_data import load_providers, fetch_crypto_ohlcv
import micro_engine
import smc_engine
import risk_engine
import banshee_ai
import predator_engine

router = APIRouter()


# ─────────────────────────────────────────────────────────────────────────────
# Private / shared helpers
# ─────────────────────────────────────────────────────────────────────────────

def get_ohlcv_cached(symbol: str, mode: str) -> dict:
    """Fetch TF DataFrames with a 5-minute in-memory cache.
    Public name — imported by banshee_core's background prewarm job."""
    key   = (symbol.upper(), mode)
    entry = _OHLCV_CACHE.get(key)
    now   = datetime.now(timezone.utc).timestamp()
    if entry and (now - entry["ts"]) < _OHLCV_TTL:
        return entry["tfs"]
    tfs = micro_engine.load_and_prepare(symbol, mode)
    if tfs and "error" not in tfs:
        _OHLCV_CACHE[key] = {"tfs": tfs, "ts": now}
    return tfs


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
# Symbol resolver helpers
# ─────────────────────────────────────────────────────────────────────────────

def _norm_symbol(raw):
    """Trim/upcase and convert a display pair to yfinance form (BTC/USD -> BTC-USD)."""
    s = str(raw or "").strip().upper()
    return s.replace("/", "-") if "/" in s else s


def _validate_symbol(sym: str) -> None:
    """Raise HTTP 400 if the normalized symbol is too long or contains invalid characters.
    Call this AFTER _norm_symbol so the check is against the canonical form.
    Valid chars after normalization: A-Z, 0-9, hyphen (-), dot (.)
    Max length: 10 characters (covers BTC-USD=7, BRK-B=5, etc.)
    """
    import re
    if len(sym) > 10:
        raise HTTPException(
            status_code=400,
            detail={"error": f"Symbol '{sym}' is too long (max 10 characters after normalization)"},
        )
    if not re.fullmatch(r"[A-Z0-9\-\.]+", sym):
        raise HTTPException(
            status_code=400,
            detail={"error": f"Symbol '{sym}' contains invalid characters (allowed: A-Z 0-9 - .)"},
        )


def _suggest_symbol(raw):
    """Dot->dash fix (replaces any dot with a dash: BRK.b -> BRK-B). Safe because a suggestion only surfaces when it actually prices. None if no dot."""
    s = str(raw or "").strip().upper()
    return s.replace(".", "-") if "." in s else None


def _crypto_pair_candidate(raw):
    """A bare alpha ticker may be a crypto pair the user meant (BTC -> BTC/USD)."""
    s = str(raw or "").strip().upper()
    return f"{s}/USD" if (s.isalpha() and 2 <= len(s) <= 5) else None


def _resolves(sym, price_of):
    p = price_of(_norm_symbol(sym))
    return bool(p and p > 0)


def _resolve_one(raw, price_of):
    """Resolve a user-entered symbol. `price_of(normalized_sym) -> float|None`.

    Returns a dict the UI consumes:
      resolved   : did the normalized input price?
      normalized : the form actually looked up (or None for empty input)
      price      : last price if resolved, else None
      suggestion : a DIFFERENT symbol (display form) the user likely meant, or None
      reason     : 'unresolved' (input didn't price; suggestion is a fix that does)
                   | 'crypto_ambiguity' (input priced as a stock but X/USD also prices)
                   | None
    """
    norm = _norm_symbol(raw)
    price = price_of(norm) if norm else None
    resolved = bool(price and price > 0)
    suggestion = reason = None

    if not resolved:
        # offer the first fix-up that actually prices: dot->dash, then X/USD
        for cand in (_suggest_symbol(raw), _crypto_pair_candidate(raw)):
            if cand and _resolves(cand, price_of):
                suggestion, reason = cand, "unresolved"
                break
    else:
        # resolved, but a bare ticker that also exists as a coin is ambiguous
        pair = _crypto_pair_candidate(raw)
        if pair and _resolves(pair, price_of):
            suggestion, reason = pair, "crypto_ambiguity"

    return {
        "input": str(raw),
        "resolved": resolved,
        "normalized": norm or None,
        "price": round(float(price), 4) if resolved else None,
        "suggestion": suggestion,
        "reason": reason,
    }


def _live_price(sym):
    """Last price for a NORMALIZED symbol. Tries yfinance first (equities + major
    crypto in -USD form); for crypto pairs Yahoo can't serve (TAO-USD, SUI-USD)
    falls back to Banshee's radar path — the same fallback the analysis endpoint
    uses. Returns float|None. The only impure part of the resolver."""
    s = str(sym or "").strip().upper()
    if not s:
        return None
    try:
        import yfinance as yf
        h = yf.Ticker(s).history(period="5d")
        if len(h):
            last = float(h["Close"].iloc[-1])
            if last > 0:
                return last
    except Exception:
        pass
    # crypto Yahoo can't price -> radar (display form uses '/')
    if s.endswith("-USD") or "/" in s:
        pair = s.replace("-", "/")
        try:
            rd = fetch_all_radar_for_syms([pair])
            p = rd.get(pair, {}).get("price")
            if isinstance(p, (int, float)) and p > 0:
                return float(p)
        except Exception:
            pass
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Pydantic models
# ─────────────────────────────────────────────────────────────────────────────

class ScanRequest(BaseModel):
    symbols: list[str]
    mode: str = "swing"
    output_mode: str = "human"


class ExecutionPlanRequest(BaseModel):
    account_size: float
    risk_percent: float
    entry_price: float
    stop_loss: float
    smc_conflicted: bool = False
    output_mode: str = "text"


# ─────────────────────────────────────────────────────────────────────────────
# Shared utility
# ─────────────────────────────────────────────────────────────────────────────

def fetch_all_radar_for_syms(syms: list) -> dict:
    """Fetch radar data for a list of symbols. Returns {sym: radar_result}."""
    cached_macro = _load_macro_cache()
    radar_sensors = cached_macro["mac_data"] if cached_macro and "mac_data" in cached_macro else None
    result = {}
    for sym in syms:
        try:
            tfs = get_ohlcv_cached(sym, "swing")
            if not tfs or "error" in tfs:
                continue
            r = micro_engine.run_analysis(sym, "swing", tfs, sensors=radar_sensors)
            if "error" not in r:
                result[sym] = r
        except Exception:
            pass
    return result


# ─────────────────────────────────────────────────────────────────────────────
# ROUTE — Watchlist
# ─────────────────────────────────────────────────────────────────────────────

def _compute_bias(trends: dict) -> str:
    vals = list(trends.values())
    bull = sum(1 for v in vals if v == "BULLISH")
    bear = sum(1 for v in vals if v == "BEARISH")
    if bull >= 3: return "↑ STRONG"
    if bull == 2: return "↑ MILD"
    if bear >= 3: return "↓ STRONG"
    if bear == 2: return "↓ MILD"
    return "→ FLAT"


@router.get("/watchlist", response_class=PlainTextResponse)
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


# ─────────────────────────────────────────────────────────────────────────────
# ROUTE — Asset Radar (single symbol)
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/radar", response_class=PlainTextResponse)
def route_radar(
    symbol: str = Query(...),
    mode: str = Query("swing"),
    output_mode: str = Query("human"),
):
    symbol = _norm_symbol(symbol)
    _validate_symbol(symbol)
    mode  = MODE_ALIASES.get(mode.lower(), "swing")
    _rkey = f"radar:{symbol.upper()}:{mode}"
    _entry = _RESP_CACHE.get(_rkey)
    if _entry and (time.time() - _entry["ts"]) < _RESP_TTL:
        res    = _entry["res"]
        tfs    = get_ohlcv_cached(symbol, mode)   # already warm in OHLCV cache
        cached = _load_macro_cache()
        source = "cache"
    else:
        tfs = get_ohlcv_cached(symbol, mode)
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
# ROUTE — Asset Scanner (watchlist)
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/scan", response_class=PlainTextResponse)
def route_scan(req: ScanRequest):
    mode = MODE_ALIASES.get(req.mode.lower(), "swing")

    cached = _load_macro_cache()
    scan_sensors = cached["mac_data"] if cached and "mac_data" in cached else None

    def _analyze_one(raw_sym: str):
        sym = _norm_symbol(raw_sym)
        try:
            _validate_symbol(sym)
        except HTTPException as exc:
            return None, f"{sym}: {exc.detail.get('error', 'invalid symbol')}"
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
# ROUTE — Banshee Nexus
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/nexus", response_class=PlainTextResponse)
def route_nexus(
    symbol: str = Query(...),
    mode: str = Query("swing"),
    use_ai: bool = Query(True),
    output_mode: str = Query("human"),
):
    symbol = _norm_symbol(symbol)
    _validate_symbol(symbol)
    from routes.macro import get_sensors as _get_sensors
    mode           = MODE_ALIASES.get(mode.lower(), "swing")
    mac_data, _src = _get_sensors()
    cached         = _load_macro_cache()
    news_lines     = cached.get("news_lines", []) if cached else []
    events         = cached.get("events",     []) if cached else []

    predator_brief = predator_engine.load_latest_briefing()
    predator_lines = predator_engine.get_briefing_for_nexus(predator_brief)
    if predator_lines:
        news_lines = [predator_lines] + news_lines

    mic_tfs = get_ohlcv_cached(symbol, mode)
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

    providers = load_providers()
    cfg = providers.get("AI_API")
    if use_ai and cfg and cfg.get("key"):
        check_ai_budget()
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
# ROUTE — Execution Plan
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/execution-plan")
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
# ROUTE — Strategy Results
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/strategies", response_class=PlainTextResponse)
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
# ROUTE — Strategy data (React Signal Lab)
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/strategies/data")
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
# ROUTE — OHLCV
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/ohlcv")
def route_ohlcv(
    symbol: str = Query(...),
    mode: str = Query("swing"),
):
    """OHLCV + indicator DataFrames for all mode TFs — used by UI chart rendering."""
    mode = MODE_ALIASES.get(mode.lower(), "swing")
    tfs  = get_ohlcv_cached(symbol, mode)
    if not tfs or "error" in tfs:
        return JSONResponse(content={"error": f"failed to load {symbol}", "tfs": {}})
    result = {}
    for tf_key, df in tfs.items():
        if isinstance(df, pd.DataFrame) and not df.empty:
            result[tf_key] = _df_to_records(df)
    return JSONResponse(content={"symbol": symbol, "mode": mode, "tfs": result})


# ─────────────────────────────────────────────────────────────────────────────
# ROUTE — SMC Structure
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/smc", response_class=PlainTextResponse)
def route_smc(
    symbol: str = Query(...),
    ltf: str = Query("4h"),
    htf: str = Query("1d"),
    use_ai: bool = Query(True),
):
    symbol = _norm_symbol(symbol)
    _validate_symbol(symbol)
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
# ROUTE — SMC JSON
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/smc/json")
def route_smc_json(
    symbol: str = Query(...),
    ltf: str = Query("4h"),
    htf: str = Query(""),
    use_ai: bool = Query(False),
):
    """Full SMC data dicts + serialised DataFrames for the Structure Map tab."""
    symbol = _norm_symbol(symbol)
    _validate_symbol(symbol)
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


# ─────────────────────────────────────────────────────────────────────────────
# ROUTE — Geometric Harmonic Arc Analysis
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/geo-harmonic")
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
    tfs = get_ohlcv_cached(symbol, "swing")
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


# ─────────────────────────────────────────────────────────────────────────────
# ROUTE — Geometric Harmonic Pine Script
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/geo-harmonic/pine")
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
    tfs = get_ohlcv_cached(symbol, "swing")
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


# ─────────────────────────────────────────────────────────────────────────────
# ROUTE — XABCD Harmonic Pattern Scanner
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/xabcd")
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
    tfs = get_ohlcv_cached(symbol, "swing")
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
# ROUTE — Symbol Resolver
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/resolve-symbol")
def resolve_symbol(sym: str):
    """Entry-time symbol validation for the portfolio ledger editor."""
    return _resolve_one(sym, _live_price)
