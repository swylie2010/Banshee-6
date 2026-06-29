"""routes/macro.py — macro weather, sensors, rotation, regime."""
from datetime import datetime, timezone

from fastapi import APIRouter
from fastapi.encoders import jsonable_encoder
from fastapi.responses import PlainTextResponse, JSONResponse

from core_state import (
    _sanitize, _cache_header, _cache_age_min,
    _load_macro_cache, _save_macro_cache,
    _log_error,
)
from shared_data import load_providers, fetch_sector_closes
from knowledge_graph import get_regime_weights
import macro_engine
import sector_rotation_engine
import predator_engine

router = APIRouter()


def get_sensors() -> tuple:
    """Public — also imported by background kill-switch job in banshee_core.py.
    Return (sensors_dict, source). Reads cache or fetches live."""
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


# ─────────────────────────────────────────────────────────────────────────────
# ROUTE 1 — Macro Weather
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/macro/weather", response_class=PlainTextResponse)
def route_macro_weather():
    sensors, source = get_sensors()

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

@router.get("/intel", response_class=PlainTextResponse)
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

@router.get("/regime", response_class=PlainTextResponse)
def route_regime():
    sensors, source = get_sensors()

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
# JSON ROUTES — Streamlit UI consumers
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/macro/sensors")
def route_macro_sensors():
    """Full sensors dict as JSON — used by Macro Weather and Nexus tabs."""
    sensors, source = get_sensors()
    return JSONResponse(content=jsonable_encoder({
        "sensors":      _sanitize(sensors),
        "source":       source,
        "cache_age_min": _cache_age_min() if source == "cache" else 0,
    }))


@router.get("/macro/corr")
def route_macro_corr():
    """Asset correlation matrix for the Macro Weather tab."""
    corr_df = macro_engine.get_correlation_matrix()
    if corr_df is None:
        return JSONResponse(content={"error": "unavailable", "data": None})
    return JSONResponse(content={"data": corr_df.round(2).to_dict()})


@router.get("/macro/intel")
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


@router.get("/rotation")
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
            return {"error": "Data unavailable",
                    "user_message": "Sector rotation needs market data — enable a data provider in Settings → Data Sources",
                    "sectors": [], "camd_alerts": [],
                    "spy_roc_21": None, "macro_env": None, "timestamp": None}
        return sector_rotation_engine.run(closes, fred_key)
    except Exception as e:
        _log_error("rotation", e)
        return {"error": "internal error", "sectors": [], "camd_alerts": [],
                "spy_roc_21": None, "macro_env": None, "timestamp": None}
