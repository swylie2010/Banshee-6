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
import threading
import secrets as _secrets
from datetime import datetime, timezone
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.staticfiles import StaticFiles

# ── Portability fix ───────────────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import macro_engine
import predator_engine
from shared_data import load_providers, save_providers
from core_state import (
    PORT, _PORTFOLIO_PATH, _WHEELS_PATH,
    _save_macro_cache,
    _save_kill_switch_state,
)
from routes.admin import router as _admin_router
from routes.macro import router as _macro_router, get_sensors as _get_sensors
from routes.journal import router as _journal_router
from routes.analysis import (
    router as _analysis_router,
    get_ohlcv_cached as _get_ohlcv_cached,
    _resolve_one, _norm_symbol, _live_price,
)
from routes.portfolio import router as _portfolio_router
from routes.options import router as _options_router
from routes.gridbot import router as _gridbot_router
from routes.audit import router as _audit_router

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
        if path not in {"/health", "/auth/token", "/favicon.ico"} and not path.startswith("/ui"):
            _presented = request.headers.get("x-banshee-token") or ""
            # constant-time compare avoids a (localhost-only, theoretical) timing side-channel
            if not _secrets.compare_digest(_presented, _BANSHEE_TOKEN):
                return JSONResponse({"detail": "Unauthorized"}, status_code=401)
        return await call_next(request)


app.add_middleware(_TokenGate)
app.include_router(_admin_router)
app.include_router(_macro_router)
app.include_router(_journal_router)
app.include_router(_analysis_router)
app.include_router(_portfolio_router)
app.include_router(_options_router)
app.include_router(_gridbot_router)
app.include_router(_audit_router)


@app.get("/auth/token")
async def route_auth_token():
    return {"token": _BANSHEE_TOKEN}


# ─────────────────────────────────────────────────────────────────────────────
# BACKGROUND SCHEDULER — macro refresh, paper trade sync, Predator daily
# Runs 24/7 with Core regardless of UI state.
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


def _bg_tick_paper_gridbot():
    """Background job: poll price and detect grid fills every 5 minutes."""
    try:
        from routes.gridbot import load_paper_gridbot, save_paper_gridbot
        import gridbot_sim
        import gridbot_engine
        from shared_data import get_last_price
        from datetime import datetime, timezone

        grid = load_paper_gridbot()
        if not grid:
            return

        # Quick check on stored events before running the full replay
        last_event_type = next(
            (e.get("type") for e in reversed(grid.get("events", []))),
            None,
        )
        if last_event_type in ("DISASTER_STOP", "MANUAL_STOP"):
            return  # already stopped — skip replay entirely

        state = gridbot_sim.replay(grid["events"], grid["config"])
        if state["status"] != "active":
            return  # defense-in-depth: replay confirms it's not active

        yf_sym = gridbot_engine._to_yf_sym(grid["sym"])
        current_price = get_last_price(yf_sym)
        if not current_price:
            return  # can't fetch price — skip this tick silently

        disaster_stop = grid["config"]["risk"]["disaster_stop"]
        new_events = gridbot_sim.tick(
            state["slots"],
            last_price=grid["last_price"],
            current_price=current_price,
            disaster_stop=disaster_stop,
            fee_pct=grid.get("fee_pct", 0.1),
        )

        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        grid["events"].extend(new_events)
        grid["last_price"] = current_price
        grid["last_tick_at"] = now
        save_paper_gridbot(grid)
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
    _bg_scheduler.add_job(
        _bg_tick_paper_gridbot,
        "interval",
        minutes=5,
        id="paper_gridbot_poller",
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


# ─────────────────────────────────────────────────────────────────────────────
# PORTFOLIO CRUD HELPERS
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


def _maybe_refresh_predator():
    """One freshness check: run today's Daily Predator if it's missing, an AI key
    is configured, and it's past the 8am-local gate. Best-effort — the analysis
    path reads whatever briefing is current, so freshness must never disturb the
    server or block a request."""
    try:
        import predator_engine
        ai_cfg  = (load_providers() or {}).get("AI_API")
        has_key = bool(ai_cfg and ai_cfg.get("key"))
        if predator_engine.should_auto_refresh(datetime.now().hour,
                                               predator_engine.today_briefing_exists(),
                                               has_key):
            predator_engine.run_daily_cycle(ai_cfg, force=False)
    except Exception:
        pass  # freshness is best-effort; never crash the Core


def _predator_freshness_loop():
    """Daemon: keep today's Predator briefing fresh without a manual click. Fires
    shortly after boot (covers a fresh launch) and rechecks every 30 min (covers a
    machine left running across midnight — the first post-8am check runs the day)."""
    while True:
        _maybe_refresh_predator()
        time.sleep(30 * 60)


if __name__ == "__main__":
    _init_token()
    threading.Thread(target=_predator_freshness_loop, daemon=True).start()
    print(f"Banshee Core starting on http://127.0.0.1:{PORT}")
    uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="warning")
