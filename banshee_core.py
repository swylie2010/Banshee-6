"""
banshee_core.py — Banshee 6 Core Server
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
import secrets as _secrets
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
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# ── Portability fix ───────────────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import macro_engine
import banshee_ai
import predator_engine
import sector_rotation_engine
import options_engine
import options_data
import wheel_engine
import alpaca_options
from shared_data import load_providers, save_providers, fetch_sector_closes
from core_state import (
    PORT, MODE_ALIASES,
    _MACRO_CACHE_FILE, _CACHE_TTL,
    _OHLCV_TTL, _OHLCV_CACHE,
    _RESP_TTL, _RESP_CACHE,
    _KILL_SWITCH_FILE,
    _STRATEGIES_FILE, _PRESETS_PATH, _PORTFOLIO_PATH,
    _WHEELS_PATH, _PAPER_WHEELS_PATH,
    _sanitize, _df_to_records, _ts, _cache_age_min, _cache_header,
    _load_macro_cache, _save_macro_cache,
    _load_kill_switch_state, _save_kill_switch_state,
)
from routes.admin import router as _admin_router
from routes.macro import router as _macro_router, get_sensors as _get_sensors
from routes.journal import router as _journal_router
from routes.analysis import (
    router as _analysis_router,
    get_ohlcv_cached as _get_ohlcv_cached,
    fetch_all_radar_for_syms,
    _resolve_one, _norm_symbol, _live_price,
)
from routes.portfolio import router as _portfolio_router

# resolve_symbol defined here (not imported) so tests can monkeypatch bc._live_price
def resolve_symbol(sym: str):
    """Entry-time symbol validation — thin wrapper that tests can monkeypatch via bc._live_price."""
    return _resolve_one(sym, _live_price)

app = FastAPI(title="Banshee Core", version="5.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8765",
        "http://127.0.0.1:8765",
    ],
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type", "X-Banshee-Token"],
)

_UI_DIR = Path(__file__).parent / "ui"
if _UI_DIR.exists():
    app.mount("/ui", StaticFiles(directory=str(_UI_DIR), html=True), name="ui")

_BANSHEE_TOKEN: str = ""


class _TokenGate(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        path = request.url.path
        if path not in {"/health", "/auth/token"} and not path.startswith("/ui"):
            if request.headers.get("x-banshee-token") != _BANSHEE_TOKEN:
                return JSONResponse({"detail": "Unauthorized"}, status_code=401)
        return await call_next(request)


app.add_middleware(_TokenGate)
app.include_router(_admin_router)
app.include_router(_macro_router)
app.include_router(_journal_router)
app.include_router(_analysis_router)
app.include_router(_portfolio_router)


@app.get("/auth/token")
async def route_auth_token():
    return {"token": _BANSHEE_TOKEN}


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


# _get_ohlcv_cached, _extract_raw, _fetch_smc_df, _smc_summary moved to routes/analysis.py
# _get_ohlcv_cached imported above as alias from routes.analysis.get_ohlcv_cached






# ─────────────────────────────────────────────────────────────────────────────
# ROUTES 4–14 moved to routes/analysis.py
# ─────────────────────────────────────────────────────────────────────────────

# Radar, scan, nexus, execution-plan, strategies, SMC routes moved to routes/analysis.py





_OPTIONS_UNIVERSE = [
    {"sym": "SPY", "name": "S&P 500 ETF"},
    {"sym": "QQQ", "name": "Nasdaq-100 ETF"},
    {"sym": "IWM", "name": "Russell 2000 ETF"},
    {"sym": "DIA", "name": "Dow Jones ETF"},
]


@app.get("/options/universe")
def route_options_universe():
    return {"universe": _OPTIONS_UNIVERSE}


_OPTIONS_CACHE = {}          # account_size_key -> (timestamp, sanitized_result)
_OPTIONS_CACHE_TTL = 300     # 5 minutes


@app.get("/options/candidate")
def route_options_candidate(account_size: float = None):
    """Scan the curated Wheel universe for the single best Cash-Secured Put.
    Read-only; never executes. Failures per-underlying are reported, not fatal."""
    _key = float(account_size) if account_size else 0.0
    _hit = _OPTIONS_CACHE.get(_key)
    if _hit and (time.time() - _hit[0]) < _OPTIONS_CACHE_TTL:
        return _hit[1]
    universe_data = []
    for item in _OPTIONS_UNIVERSE:
        sym = item["sym"]
        try:
            contracts, meta = options_data.fetch_chain(sym)
        except Exception as e:
            print(f"[options] chain fetch failed for {sym}: {e}", file=sys.stderr)
            universe_data.append({"sym": sym, "name": item["name"], "spot": None,
                                  "contracts": [], "closes": [], "failed": True})
            continue
        try:
            closes = options_data.fetch_closes(sym)
        except Exception as e:
            print(f"[options] closes fetch failed for {sym}: {e}", file=sys.stderr)
            closes = []
        universe_data.append({
            "sym": sym, "name": item["name"], "spot": meta.get("spot"),
            "contracts": contracts, "closes": closes, "failed": meta.get("spot") is None,
        })
    try:
        result = options_engine.best_candidate(universe_data, account_size=account_size)
    except Exception as e:
        print(f"[options] engine failed: {e}", file=sys.stderr)
        return _sanitize({"candidate": None, "error_note":
                          "Couldn't scan options right now — try again in a moment."})
    sanitized = _sanitize(result)
    _OPTIONS_CACHE[_key] = (time.time(), sanitized)
    return sanitized


@app.post("/options/grade")
def route_options_grade(spec: dict = Body(...)):
    """Grade a user-composed cash-secured put against Banshee's rules (the inverse
    of /options/candidate). Read-only; never executes. Structured errors, never 500
    on bad input."""
    sym = (spec.get("underlying") or "").upper()
    if not sym or spec.get("strike") in (None, "") or spec.get("dte") in (None, ""):
        return JSONResponse(status_code=400, content={"error":
            "Pick something to sell against, a strike price, and days to expiry to grade an option."})
    try:
        contracts, meta = options_data.fetch_chain(sym)
    except Exception as e:
        print(f"[options] grade chain fetch failed for {sym}: {e}", file=sys.stderr)
        return JSONResponse(status_code=404, content={"error":
            f"Couldn't load market data for {sym} — check the symbol and try again."})
    try:
        closes = options_data.fetch_closes(sym)
    except Exception:
        closes = []
    market_ctx = {"spot": meta.get("spot"), "contracts": contracts, "closes": closes}
    try:
        result = options_engine.grade_option(spec, market_ctx)
    except Exception as e:
        print(f"[options] grade engine failed: {e}", file=sys.stderr)
        return JSONResponse(status_code=500, content={"error":
            "Couldn't grade that option right now — try again in a moment."})
    return _sanitize(result)


@app.post("/options/scenario")
def route_options_scenario(body: dict = Body(...)):
    """Deterministic scenario: given a spec and terminal price, return the outcome. No AI."""
    try:
        spec = body.get("spec") or {}
        terminal_price = body.get("terminal_price")
        if not spec or terminal_price is None:
            raise HTTPException(status_code=400,
                detail={"error": "requires spec and terminal_price"})
        tp = float(terminal_price)
        if not (0 < tp < 1e9):
            raise HTTPException(status_code=400,
                detail={"error": "terminal_price must be a finite positive number"})
        return _sanitize(options_engine.run_scenario(spec, tp))
    except HTTPException:
        raise
    except Exception as e:
        print(f"[options/scenario] error: {e}", file=sys.stderr)
        raise HTTPException(status_code=400,
            detail={"error": f"Scenario calculation failed: {e}"})


@app.post("/options/learn/recap")
def route_learn_recap(body: dict = Body(...)):
    """AI plain-English recap of a single scenario run. Returns {text}."""
    run = body.get("run") or {}
    if not run:
        raise HTTPException(status_code=400, detail={"error": "requires run"})
    try:
        providers = load_providers()
        cfg = providers.get("AI_API", {})
        text = banshee_ai.summarize_run(cfg, run)
        return {"text": text}
    except Exception as e:
        print(f"[learn/recap] error: {e}", file=sys.stderr)
        return {"text": f"Narration unavailable — {run.get('plain', 'no summary')} Net P&L: ${run.get('pnl', 0):+,.0f}."}


@app.post("/options/learn/compare")
def route_learn_compare(body: dict = Body(...)):
    """AI comparative narration of two scenario runs. Returns {text}."""
    run_a = body.get("run_a") or {}
    run_b = body.get("run_b") or {}
    if not run_a or not run_b:
        raise HTTPException(status_code=400, detail={"error": "requires run_a and run_b"})
    try:
        providers = load_providers()
        cfg = providers.get("AI_API", {})
        text = banshee_ai.compare_runs(cfg, run_a, run_b)
        return {"text": text}
    except Exception as e:
        print(f"[learn/compare] error: {e}", file=sys.stderr)
        delta = run_b.get("pnl", 0) - run_a.get("pnl", 0)
        return {"text": f"Narration unavailable. Run A: ${run_a.get('pnl', 0):+,.0f}. Run B: ${run_b.get('pnl', 0):+,.0f}. Δ: ${delta:+,.0f}."}


@app.post("/options/learn/why-not")
def route_learn_why_not(body: dict = Body(...)):
    """AI explanation linking a failing grade to its simulated consequence. Returns {text}."""
    graded = body.get("graded") or {}
    run = body.get("run") or {}
    if not graded or not run:
        raise HTTPException(status_code=400, detail={"error": "requires graded and run"})
    try:
        providers = load_providers()
        cfg = providers.get("AI_API", {})
        text = banshee_ai.explain_why_not(cfg, graded, run)
        return {"text": text}
    except Exception as e:
        print(f"[learn/why-not] error: {e}", file=sys.stderr)
        return {"text": f"Narration unavailable. Simulated outcome: {run.get('plain', '')}. P&L: ${run.get('pnl', 0):+,.0f}."}


# /ohlcv, /smc/json, /strategies/data, /geo-harmonic, /geo-harmonic/pine, /xabcd moved to routes/analysis.py


# /smc/json, /strategies/data, /geo-harmonic, /geo-harmonic/pine, /xabcd moved to routes/analysis.py


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


def _bg_poll_paper_wheels():
    """Background job: poll all paper wheels every 5 minutes."""
    try:
        from routes.options import load_paper_wheels, save_paper_wheels
        data = load_paper_wheels()
        import alpaca_options
        if alpaca_options.poll_paper_wheels(data):
            save_paper_wheels(data)
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
    _bg_scheduler.add_job(
        _bg_poll_paper_wheels,
        "interval",
        minutes=5,
        id="paper_wheel_poller",
        replace_existing=True,
    )

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


# Symbol resolution helpers and /resolve-symbol route moved to routes/analysis.py
# Re-exported at module level via import above for test compatibility


# ─────────────────────────────────────────────────────────────────────────────
# ROUTE 14 — Portfolio CRUD helpers
# Route handlers live in routes/portfolio.py; helpers stay here so tests can
# monkeypatch bc._PORTFOLIO_PATH and call bc._load_portfolios() etc. directly.
# ─────────────────────────────────────────────────────────────────────────────

def _load_portfolios() -> dict:
    if _PORTFOLIO_PATH.exists():
        try:
            return json.loads(_PORTFOLIO_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"portfolios": []}


def _save_portfolios(data: dict) -> None:
    _PORTFOLIO_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _ensure_transactions(portfolio: dict, today: str) -> bool:
    """Phase 2: make the persisted ledger authoritative.

    If the portfolio has a non-empty `transactions` array, leave it untouched
    (the ledger is already the source of truth). Otherwise, if it has legacy
    `holdings`, migrate them to opening BUY transactions once. Returns True when
    the portfolio was changed so the caller knows to persist it. Idempotent:
    a second call is a no-op because `transactions` is now present."""
    if portfolio.get("transactions"):
        return False
    holdings = portfolio.get("holdings") or []
    if not holdings:
        return False
    import ledger_engine as _le
    portfolio["transactions"] = _le.holdings_to_transactions(holdings, today)
    return True


def create_portfolio(body: dict):
    data = _load_portfolios()
    portfolio = {
        "id": str(uuid.uuid4()),
        "preset_id": body.get("preset_id", ""),
        "name": body.get("name", "My Portfolio"),
        "thesis": body.get("thesis", ""),
        "transactions": body.get("transactions", []),  # authoritative ledger
        "holdings": body.get("holdings", []),           # derived {sym,cls,shares} snapshot
        "grade_history": [],
    }
    data["portfolios"].append(portfolio)
    _save_portfolios(data)
    return portfolio


def update_portfolio(portfolio_id: str, body: dict):
    data = _load_portfolios()
    for p in data["portfolios"]:
        if p["id"] == portfolio_id:
            if "transactions" in body:
                p["transactions"] = body["transactions"]
            if "holdings" in body:
                p["holdings"] = body["holdings"]
            if "thesis" in body:
                p["thesis"] = body["thesis"]
            if "name" in body:
                p["name"] = body["name"]
            _save_portfolios(data)
            return p
    return JSONResponse(status_code=404, content={"error": "Portfolio not found"})


# ── Simulated Wheel (Options Phase 2) ───────────────────────────
_WHEELS_PATH = Path(__file__).parent / "banshee_wheels.json"


def _load_wheels() -> dict:
    if _WHEELS_PATH.exists():
        try:
            return json.loads(_WHEELS_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"wheels": []}


def _save_wheels(data: dict) -> None:
    _WHEELS_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _wheel_view(wheel: dict, include_cc: bool = True) -> dict:
    """A wheel plus its replayed state. Adds a synthetic CC suggestion while in
    SHARES (estimate — Phase 2 has no live calls feed).
    Pass include_cc=False for list views to skip the per-wheel vol fetch."""
    state = wheel_engine.replay(wheel.get("events", []))
    view = {"id": wheel["id"], "name": wheel.get("name", ""),
            "underlying": wheel.get("underlying", ""), "created": wheel.get("created", ""),
            "candidate_snapshot": wheel.get("candidate_snapshot"),
            "events": wheel.get("events", []), "state": state}
    if include_cc and state.get("state") == "SHARES":
        ncb = (state.get("totals") or {}).get("net_cost_basis")
        annual_vol = None
        try:
            closes = options_data.fetch_closes(wheel.get("underlying", ""))
            rv = options_engine.realized_vol_series(closes)
            annual_vol = rv[-1] if rv else None
        except Exception as e:
            print(f"[wheels] vol fetch failed for {wheel.get('underlying')}: {e}", file=sys.stderr)
        view["suggested_cc"] = wheel_engine.suggest_covered_call(ncb, annual_vol)
    return _sanitize(view)


@app.get("/wheels")
def route_wheels_list():
    data = _load_wheels()
    return {"wheels": [_wheel_view(w, include_cc=False) for w in data.get("wheels", [])]}


@app.post("/wheels")
def route_wheels_create(body: dict = Body(...)):
    from datetime import date as _date
    snap = body.get("candidate_snapshot") or {}
    underlying = body.get("underlying") or snap.get("underlying") or ""
    if not underlying:
        return JSONResponse(status_code=400,
                            content={"error": "A candidate (with an underlying) is required to start a wheel."})
    data = _load_wheels()
    wheel = {
        "id": str(uuid.uuid4()),
        "name": body.get("name") or f"{underlying} Wheel",
        "underlying": underlying,
        "created": _date.today().isoformat(),
        "candidate_snapshot": snap,
        "events": [],
    }
    data["wheels"].append(wheel)
    _save_wheels(data)
    return _wheel_view(wheel)


@app.get("/wheels/{wheel_id}")
def route_wheels_get(wheel_id: str):
    for w in _load_wheels().get("wheels", []):
        if w["id"] == wheel_id:
            return _wheel_view(w)
    return JSONResponse(status_code=404, content={"error": "Wheel not found"})


@app.post("/wheels/{wheel_id}/event")
def route_wheels_event(wheel_id: str, body: dict = Body(...)):
    data = _load_wheels()
    for w in data.get("wheels", []):
        if w["id"] == wheel_id:
            ev = body.get("event")
            new_event = ev if isinstance(ev, dict) and ev else body
            verdict = wheel_engine.validate(w.get("events", []), new_event)
            if not verdict.get("ok"):
                return JSONResponse(status_code=400, content={"error": verdict.get("reason")})
            w.setdefault("events", []).append(new_event)
            _save_wheels(data)
            return _wheel_view(w)
    return JSONResponse(status_code=404, content={"error": "Wheel not found"})


@app.delete("/wheels/{wheel_id}")
def route_wheels_delete(wheel_id: str):
    data = _load_wheels()
    before = len(data.get("wheels", []))
    data["wheels"] = [w for w in data.get("wheels", []) if w["id"] != wheel_id]
    if len(data["wheels"]) == before:
        return JSONResponse(status_code=404, content={"error": "Wheel not found"})
    _save_wheels(data)
    return {"ok": True}


# ── Paper Wheel store ──────────────────────────────────────────────────────────

_PAPER_WHEELS_PATH = Path(__file__).parent / "paper_wheels.json"


def _load_paper_wheels() -> dict:
    if _PAPER_WHEELS_PATH.exists():
        try:
            return json.loads(_PAPER_WHEELS_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"wheels": []}


def _save_paper_wheels(data: dict) -> None:
    _PAPER_WHEELS_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _pending_fill(wheel: dict) -> bool:
    """True when the most recent Alpaca-linked event has fill_price=None."""
    for ev in reversed(wheel.get("events", [])):
        if ev.get("alpaca_order_id"):
            return ev.get("fill_price") is None
    return False


def _paper_wheel_view(wheel: dict) -> dict:
    """Full view: FSM replay + paper-path metadata."""
    state = wheel_engine.replay(wheel.get("events", []))
    return _sanitize({
        "id":                 wheel["id"],
        "name":               wheel.get("name", ""),
        "underlying":         wheel.get("underlying", ""),
        "created":            wheel.get("created", ""),
        "candidate_snapshot": wheel.get("candidate_snapshot"),
        "events":             wheel.get("events", []),
        "state":              state,
        "pending_fill":       _pending_fill(wheel),
        "needs_attention":    wheel.get("needs_attention", False),
        "attention_reason":   wheel.get("attention_reason"),
        "live":               wheel.get("live"),
        "last_polled":        wheel.get("last_polled"),
    })


@app.get("/paper-wheels/alerts")
def route_paper_wheels_alerts():
    data = _load_paper_wheels()
    alerts = [
        {"id": w["id"], "name": w.get("name", ""), "underlying": w.get("underlying", ""),
         "attention_reason": w.get("attention_reason")}
        for w in data.get("wheels", [])
        if w.get("needs_attention")
    ]
    return {"alerts": alerts}


@app.get("/paper-wheels")
def route_paper_wheels_list():
    data = _load_paper_wheels()
    return {"wheels": [_paper_wheel_view(w) for w in data.get("wheels", [])]}


@app.delete("/paper-wheels/{wheel_id}")
def route_paper_wheels_delete(wheel_id: str):
    data = _load_paper_wheels()
    wheel = next((w for w in data.get("wheels", []) if w["id"] == wheel_id), None)
    if not wheel:
        return JSONResponse(status_code=404, content={"error": "Paper wheel not found"})
    for ev in reversed(wheel.get("events", [])):
        if ev.get("alpaca_order_id") and ev.get("fill_price") is None:
            alpaca_options.cancel_order(ev["alpaca_order_id"])
            break
    data["wheels"] = [w for w in data["wheels"] if w["id"] != wheel_id]
    _save_paper_wheels(data)
    return {"ok": True}


@app.post("/paper-wheels")
def route_paper_wheels_create(body: dict = Body(...)):
    from datetime import date as _date
    snap       = body.get("candidate_snapshot") or {}
    candidate  = snap.get("candidate") or snap
    underlying = body.get("underlying") or candidate.get("underlying") or ""
    if not underlying:
        return JSONResponse(status_code=400,
                            content={"error": "A candidate (with an underlying) is required."})

    strike = candidate.get("strike")
    expiry = candidate.get("expiry")
    mid    = candidate.get("mid")
    delta  = candidate.get("delta")
    dte    = candidate.get("dte")
    if not all([strike, expiry, mid]):
        return JSONResponse(status_code=400,
                            content={"error": "Candidate snapshot missing strike, expiry, or mid."})

    occ_symbol = alpaca_options.build_occ_symbol(underlying, expiry, "put", float(strike))
    try:
        order = alpaca_options.place_option_order(occ_symbol, "sell", 1, float(mid))
    except alpaca_options.AlpacaOrderRejectedError as e:
        return JSONResponse(status_code=400, content={
            "error": "alpaca_order_rejected",
            "plain": f"Alpaca rejected the order: {e.reason}. Check your paper account buying power.",
        })
    except alpaca_options.AlpacaUnavailableError:
        return JSONResponse(status_code=503, content={
            "error": "alpaca_unavailable",
            "plain": "Alpaca paper API is not responding. Your wheel record is intact — try again shortly.",
        })

    data = _load_paper_wheels()
    wheel = {
        "id":                 str(uuid.uuid4()),
        "name":               body.get("name") or f"{underlying} Paper Wheel",
        "underlying":         underlying,
        "created":            _date.today().isoformat(),
        "candidate_snapshot": snap,
        "events": [{
            "type": "SOLD_CSP", "strike": float(strike), "expiry": expiry,
            "dte": dte, "mid": float(mid),
            "delta": float(delta) if delta else None,
            "alpaca_order_id": order["order_id"], "fill_price": None,
        }],
        "needs_attention": False, "attention_reason": None,
        "live": None, "last_polled": None,
    }
    data["wheels"].append(wheel)
    _save_paper_wheels(data)
    return _paper_wheel_view(wheel)


@app.get("/paper-wheels/{wheel_id}/calls")
def route_paper_wheel_calls(wheel_id: str):
    data = _load_paper_wheels()
    wheel = next((w for w in data.get("wheels", []) if w["id"] == wheel_id), None)
    if not wheel:
        return JSONResponse(status_code=404, content={"error": "Paper wheel not found"})
    try:
        calls = alpaca_options.fetch_calls_chain(
            wheel.get("underlying", ""), min_dte=7, max_dte=55
        )
    except alpaca_options.AlpacaUnavailableError:
        return JSONResponse(status_code=503, content={
            "error": "alpaca_unavailable",
            "plain": "Alpaca paper API is not responding. Try again shortly.",
        })
    return {"calls": calls, "underlying": wheel.get("underlying", "")}


@app.get("/paper-wheels/{wheel_id}")
def route_paper_wheels_get(wheel_id: str):
    for w in _load_paper_wheels().get("wheels", []):
        if w["id"] == wheel_id:
            return _paper_wheel_view(w)
    return JSONResponse(status_code=404, content={"error": "Paper wheel not found"})


@app.post("/paper-wheels/{wheel_id}/submit-cc")
def route_paper_wheel_submit_cc(wheel_id: str, body: dict = Body(...)):
    data = _load_paper_wheels()
    wheel = next((w for w in data.get("wheels", []) if w["id"] == wheel_id), None)
    if not wheel:
        return JSONResponse(status_code=404, content={"error": "Paper wheel not found"})

    state = wheel_engine.replay(wheel.get("events", []))
    if state.get("state") != "SHARES":
        return JSONResponse(status_code=400, content={
            "error": f"Cannot submit CC: wheel is in state '{state.get('state')}', expected 'SHARES'."
        })

    strike = body.get("strike")
    expiry = body.get("expiry")
    mid    = body.get("mid")
    delta  = body.get("delta")
    dte    = body.get("dte")
    if not all([strike, expiry, mid]):
        return JSONResponse(status_code=400,
                            content={"error": "strike, expiry, and mid are required."})

    occ_symbol = alpaca_options.build_occ_symbol(
        wheel.get("underlying", ""), expiry, "call", float(strike)
    )
    try:
        order = alpaca_options.place_option_order(occ_symbol, "sell", 1, float(mid))
    except alpaca_options.AlpacaOrderRejectedError as e:
        return JSONResponse(status_code=400, content={
            "error": "alpaca_order_rejected",
            "plain": f"Alpaca rejected the CC order: {e.reason}.",
        })
    except alpaca_options.AlpacaUnavailableError:
        return JSONResponse(status_code=503, content={
            "error": "alpaca_unavailable",
            "plain": "Alpaca paper API is not responding. Try again shortly.",
        })

    wheel["events"].append({
        "type": "SOLD_CC", "strike": float(strike), "expiry": expiry,
        "dte": dte, "mid": float(mid),
        "delta": float(delta) if delta else None,
        "alpaca_order_id": order["order_id"], "fill_price": None,
    })
    _save_paper_wheels(data)
    return _paper_wheel_view(wheel)


@app.post("/paper-wheels/{wheel_id}/event")
def route_paper_wheels_event(wheel_id: str, body: dict = Body(...)):
    data = _load_paper_wheels()
    for w in data.get("wheels", []):
        if w["id"] == wheel_id:
            ev = body.get("event")
            new_event = ev if isinstance(ev, dict) and ev else body
            verdict = wheel_engine.validate(w.get("events", []), new_event)
            if not verdict.get("ok"):
                return JSONResponse(status_code=400, content={"error": verdict.get("reason")})
            w.setdefault("events", []).append(new_event)
            _save_paper_wheels(data)
            return _paper_wheel_view(w)
    return JSONResponse(status_code=404, content={"error": "Paper wheel not found"})


# _join_names, _build_rotation_note, get_portfolio_analysis moved to portfolio_engine.py / routes/portfolio.py


# ─────────────────────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

def _init_token():
    global _BANSHEE_TOKEN
    p = load_providers()
    if not p.get("banshee_token"):
        p["banshee_token"] = _secrets.token_hex(32)
        save_providers(p)
    _BANSHEE_TOKEN = p["banshee_token"]


if __name__ == "__main__":
    _init_token()
    print(f"Banshee Core starting on http://127.0.0.1:{PORT}")
    uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="warning")
