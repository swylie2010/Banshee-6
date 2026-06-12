"""routes/options.py — options analysis, simulated wheels, paper wheels."""
import json
import sys
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Body, HTTPException, Query
from fastapi.responses import JSONResponse

from core_state import _WHEELS_PATH, _PAPER_WHEELS_PATH, _sanitize
import options_engine
import options_data
import wheel_engine
import alpaca_options
import banshee_ai

router = APIRouter()

# ── Simulated Wheel helpers (private) ─────────────────────────────────────────

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


# ── Paper wheel helpers (load/save PUBLIC for background job) ──────────────────

def _pending_fill(wheel: dict) -> bool:
    """True when the most recent Alpaca-linked event has fill_price=None."""
    for ev in reversed(wheel.get("events", [])):
        if ev.get("alpaca_order_id"):
            return ev.get("fill_price") is None
    return False


def load_paper_wheels() -> dict:
    """PUBLIC — used by background job in banshee_core.py."""
    if _PAPER_WHEELS_PATH.exists():
        try:
            return json.loads(_PAPER_WHEELS_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"wheels": []}


def save_paper_wheels(data: dict) -> None:
    """PUBLIC — used by background job in banshee_core.py."""
    _PAPER_WHEELS_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


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


# ── Options routes (7) ────────────────────────────────────────────────────────

_OPTIONS_UNIVERSE = [
    {"sym": "SPY", "name": "S&P 500 ETF"},
    {"sym": "QQQ", "name": "Nasdaq-100 ETF"},
    {"sym": "IWM", "name": "Russell 2000 ETF"},
    {"sym": "DIA", "name": "Dow Jones ETF"},
]

_OPTIONS_CACHE = {}          # account_size_key -> (timestamp, sanitized_result)
_OPTIONS_CACHE_TTL = 300     # 5 minutes


@router.get("/options/universe")
def route_options_universe():
    return {"universe": _OPTIONS_UNIVERSE}


@router.get("/options/candidate")
def route_options_candidate(account_size: float = None):
    """Scan the curated Wheel universe for the single best Cash-Secured Put.
    Read-only; never executes. Failures per-underlying are reported, not fatal."""
    import time
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


@router.post("/options/grade")
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


@router.post("/options/scenario")
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


@router.post("/options/learn/recap")
def route_learn_recap(body: dict = Body(...)):
    """AI plain-English recap of a single scenario run. Returns {text}."""
    from shared_data import load_providers
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


@router.post("/options/learn/compare")
def route_learn_compare(body: dict = Body(...)):
    """AI comparative narration of two scenario runs. Returns {text}."""
    from shared_data import load_providers
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


@router.post("/options/learn/why-not")
def route_learn_why_not(body: dict = Body(...)):
    """AI explanation linking a failing grade to its simulated consequence. Returns {text}."""
    from shared_data import load_providers
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


# ── Simulated wheel routes (5) ────────────────────────────────────────────────

@router.get("/wheels")
def route_wheels_list():
    data = _load_wheels()
    return {"wheels": [_wheel_view(w, include_cc=False) for w in data.get("wheels", [])]}


@router.post("/wheels")
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


@router.get("/wheels/{wheel_id}")
def route_wheels_get(wheel_id: str):
    for w in _load_wheels().get("wheels", []):
        if w["id"] == wheel_id:
            return _wheel_view(w)
    return JSONResponse(status_code=404, content={"error": "Wheel not found"})


@router.post("/wheels/{wheel_id}/event")
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


@router.delete("/wheels/{wheel_id}")
def route_wheels_delete(wheel_id: str):
    data = _load_wheels()
    before = len(data.get("wheels", []))
    data["wheels"] = [w for w in data.get("wheels", []) if w["id"] != wheel_id]
    if len(data["wheels"]) == before:
        return JSONResponse(status_code=404, content={"error": "Wheel not found"})
    _save_wheels(data)
    return {"ok": True}


# ── Paper wheel routes (8) ────────────────────────────────────────────────────
# IMPORTANT: /paper-wheels/alerts MUST be registered before /paper-wheels/{wheel_id}

@router.get("/paper-wheels/alerts")
def route_paper_wheels_alerts():
    data = load_paper_wheels()
    alerts = [
        {"id": w["id"], "name": w.get("name", ""), "underlying": w.get("underlying", ""),
         "attention_reason": w.get("attention_reason")}
        for w in data.get("wheels", [])
        if w.get("needs_attention")
    ]
    return {"alerts": alerts}


@router.get("/paper-wheels")
def route_paper_wheels_list():
    data = load_paper_wheels()
    return {"wheels": [_paper_wheel_view(w) for w in data.get("wheels", [])]}


@router.delete("/paper-wheels/{wheel_id}")
def route_paper_wheels_delete(wheel_id: str):
    data = load_paper_wheels()
    wheel = next((w for w in data.get("wheels", []) if w["id"] == wheel_id), None)
    if not wheel:
        return JSONResponse(status_code=404, content={"error": "Paper wheel not found"})
    for ev in reversed(wheel.get("events", [])):
        if ev.get("alpaca_order_id") and ev.get("fill_price") is None:
            alpaca_options.cancel_order(ev["alpaca_order_id"])
            break
    data["wheels"] = [w for w in data["wheels"] if w["id"] != wheel_id]
    save_paper_wheels(data)
    return {"ok": True}


@router.post("/paper-wheels")
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

    data = load_paper_wheels()
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
    save_paper_wheels(data)
    return _paper_wheel_view(wheel)


@router.get("/paper-wheels/{wheel_id}/calls")
def route_paper_wheel_calls(wheel_id: str):
    data = load_paper_wheels()
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


@router.get("/paper-wheels/{wheel_id}")
def route_paper_wheels_get(wheel_id: str):
    for w in load_paper_wheels().get("wheels", []):
        if w["id"] == wheel_id:
            return _paper_wheel_view(w)
    return JSONResponse(status_code=404, content={"error": "Paper wheel not found"})


@router.post("/paper-wheels/{wheel_id}/submit-cc")
def route_paper_wheel_submit_cc(wheel_id: str, body: dict = Body(...)):
    data = load_paper_wheels()
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
    save_paper_wheels(data)
    return _paper_wheel_view(wheel)


@router.post("/paper-wheels/{wheel_id}/event")
def route_paper_wheels_event(wheel_id: str, body: dict = Body(...)):
    data = load_paper_wheels()
    for w in data.get("wheels", []):
        if w["id"] == wheel_id:
            ev = body.get("event")
            new_event = ev if isinstance(ev, dict) and ev else body
            verdict = wheel_engine.validate(w.get("events", []), new_event)
            if not verdict.get("ok"):
                return JSONResponse(status_code=400, content={"error": verdict.get("reason")})
            w.setdefault("events", []).append(new_event)
            save_paper_wheels(data)
            return _paper_wheel_view(w)
    return JSONResponse(status_code=404, content={"error": "Paper wheel not found"})
