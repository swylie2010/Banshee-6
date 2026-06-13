"""routes/admin.py — settings, predator, AI briefing, presets, system."""

import json
import threading
import os as _os

from fastapi import APIRouter, Body, HTTPException
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel

import banshee_ai
import micro_engine
import predator_engine
import sector_rotation_engine
import smc_engine
from core_state import (
    MODE_ALIASES,
    _PRESETS_PATH,
    _load_macro_cache,
    _log_error,
    check_ai_budget,
)
from shared_data import load_providers, save_providers, fetch_sector_closes

router = APIRouter()


# ─────────────────────────────────────────────────────────────────────────────
# Pydantic models
# ─────────────────────────────────────────────────────────────────────────────

class SettingsBody(BaseModel):
    settings: dict


class PredatorConfigBody(BaseModel):
    config: dict


class PredatorRunRequest(BaseModel):
    watchlist: list[str] = []
    force: bool = False
    manual_stories: list = []


class AIBriefingRequest(BaseModel):
    symbol: str
    mode: str = "swing"
    manual_stories: list = []
    tab: str = "nexus"  # "nexus" | "smc" | "gh"


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _mask(v: str) -> str:
    if isinstance(v, str) and len(v) > 4:
        return "•••••" + v[-4:]
    return v


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


# ─────────────────────────────────────────────────────────────────────────────
# HEALTH CHECK
# ─────────────────────────────────────────────────────────────────────────────

from core_state import _ts

@router.get("/health")
def health():
    return {"status": "ok", "ts": _ts()}


# ─────────────────────────────────────────────────────────────────────────────
# SETTINGS — read/write ~/.banshee_keys.json
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/settings")
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


@router.post("/settings")
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


@router.post("/settings/test")
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
            import requests as _req, urllib.parse as _up, socket as _sock, ipaddress as _ip
            base = (url or "http://localhost:11434").rstrip("/")
            _host = _up.urlparse(base).hostname or ""
            try:
                _addr = _ip.ip_address(_sock.gethostbyname(_host))
                if _addr.is_private or _addr.is_loopback or _addr.is_link_local:
                    if _host not in ("localhost", "127.0.0.1"):
                        return JSONResponse(content={"status": "error", "message": "URL resolves to a private/internal address"})
            except Exception:
                pass
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
# PREDATOR
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/predator/briefing")
def route_predator_briefing():
    """Latest Daily Predator briefing JSON."""
    briefing = predator_engine.load_latest_briefing()
    return JSONResponse(content=briefing or {})


@router.get("/predator/config")
def route_predator_config_get():
    """Current Predator configuration."""
    return JSONResponse(content=predator_engine.load_predator_config())


@router.post("/predator/config")
def route_predator_config_save(body: PredatorConfigBody):
    """Save Predator configuration."""
    predator_engine.save_predator_config(body.config)
    return {"status": "saved"}


@router.post("/predator/run")
def route_predator_run(req: PredatorRunRequest):
    """Trigger a Daily Predator cycle."""
    check_ai_budget()
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
        _log_error("predator/run", e)
        return JSONResponse(content={"error": "internal error"}, status_code=500)


# ─────────────────────────────────────────────────────────────────────────────
# AI BRIEFING
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/ai/briefing", response_class=PlainTextResponse)
def route_ai_briefing(req: AIBriefingRequest):
    """Generate an AI synthesis briefing for the React UI tabs."""
    check_ai_budget()
    # Lazy import to avoid circular dependency
    from routes.analysis import get_ohlcv_cached as _get_ohlcv_cached, _fetch_smc_df
    from routes.macro import get_sensors as _get_sensors
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
# ROUTE 13 — Watchlist Presets
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/presets")
def route_presets_get():
    return {"presets": _load_presets()}


@router.post("/presets")
def route_presets_save(body: dict = Body(...)):
    presets = body.get("presets", [])
    if not isinstance(presets, list):
        raise HTTPException(status_code=422, detail="presets must be a list")
    _save_presets(presets)
    return {"saved": len(presets)}


# ─────────────────────────────────────────────────────────────────────────────
# SHUTDOWN
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/shutdown")
def route_shutdown():
    """Terminate Core (and the whole Banshee stack) cleanly. Response fires before exit."""
    import threading, os as _os
    def _exit():
        import time; time.sleep(0.4)
        _os._exit(0)
    threading.Thread(target=_exit, daemon=True).start()
    return {"status": "shutting_down"}
