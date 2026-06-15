"""routes/gridbot.py — Gridbot calculator + paper trading endpoints."""
import asyncio
import json
import threading
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Body
from fastapi.responses import JSONResponse

import gridbot_engine
import gridbot_sim
from core_state import _PAPER_GRIDBOT_PATH

router = APIRouter()

_PAPER_GRIDBOT_LOCK = threading.Lock()


# ── Storage helpers ────────────────────────────────────────────────────────────

def load_paper_gridbot() -> dict | None:
    """Return the stored grid dict, or None if file missing/corrupt."""
    if _PAPER_GRIDBOT_PATH.exists():
        try:
            return json.loads(_PAPER_GRIDBOT_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return None


def save_paper_gridbot(data: dict) -> None:
    """PUBLIC — also called by background tick job in banshee_core.py."""
    with _PAPER_GRIDBOT_LOCK:
        _PAPER_GRIDBOT_PATH.write_text(
            json.dumps(data, indent=2), encoding="utf-8"
        )


def _active_grid(data: dict | None) -> bool:
    """True if the stored grid is currently active (not stopped)."""
    if not data:
        return False
    state = gridbot_sim.replay(data.get("events", []), data.get("config", {}))
    return state["status"] == "active"


# ── Calculator route (existing) ────────────────────────────────────────────────

@router.post("/gridbot/analyze")
async def route_gridbot_analyze(
    sym:        str   = Body(...),
    capital:    float = Body(...),
    grid_count: int   = Body(10),
    fee_pct:    float = Body(0.1),
):
    try:
        result = await asyncio.to_thread(
            gridbot_engine.analyze_gridbot,
            sym, float(capital), int(grid_count), float(fee_pct),
        )
        if "error" in result:
            return JSONResponse({"error": result["error"]}, status_code=400)
        return result
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


# ── Paper trading routes ───────────────────────────────────────────────────────

@router.post("/gridbot/paper")
async def route_gridbot_paper_deploy(
    sym:        str   = Body(...),
    capital:    float = Body(...),
    grid_count: int   = Body(10),
    fee_pct:    float = Body(0.1),
):
    """Deploy a virtual paper grid. Only one active grid allowed at a time."""
    existing = load_paper_gridbot()
    if _active_grid(existing):
        return JSONResponse(
            {"error": "A paper grid is already active. Stop it first."},
            status_code=409,
        )

    try:
        config = await asyncio.to_thread(
            gridbot_engine.analyze_gridbot,
            sym, float(capital), int(grid_count), float(fee_pct),
        )
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)

    if "error" in config:
        return JSONResponse({"error": config["error"]}, status_code=400)

    # Fetch current price for the DEPLOY event
    try:
        from shared_data import get_last_price
        yf_sym = gridbot_engine._to_yf_sym(sym)
        deploy_price = get_last_price(yf_sym) or config["current_price"]
    except Exception:
        deploy_price = config["current_price"]

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    grid = {
        "id": f"gb_{now[:10].replace('-', '')}_{sym.upper()}_{uuid.uuid4().hex[:6]}",
        "sym": sym.upper(),
        "fee_pct": float(fee_pct),
        "deployed_at": now,
        "last_price": deploy_price,
        "last_tick_at": now,
        "config": config,
        "events": [{"type": "DEPLOY", "timestamp": now, "price": deploy_price}],
    }
    save_paper_gridbot(grid)

    state = gridbot_sim.replay(grid["events"], config, current_price=deploy_price)
    return {"grid": grid, "state": state}


@router.get("/gridbot/paper")
async def route_gridbot_paper_get():
    """Return the active (or most recent stopped) grid + replayed state."""
    grid = load_paper_gridbot()
    if not grid:
        return JSONResponse({"error": "No paper grid found."}, status_code=404)

    try:
        from shared_data import get_last_price
        yf_sym = gridbot_engine._to_yf_sym(grid["sym"])
        current_price = get_last_price(yf_sym) or grid["last_price"]
    except Exception:
        current_price = grid["last_price"]

    state = gridbot_sim.replay(grid["events"], grid["config"], current_price=current_price)
    return {"grid": grid, "state": state, "current_price": current_price}


@router.delete("/gridbot/paper")
async def route_gridbot_paper_stop():
    """Stop the active paper grid (manual stop)."""
    grid = load_paper_gridbot()
    if not grid:
        return JSONResponse({"error": "No paper grid found."}, status_code=404)
    if not _active_grid(grid):
        return JSONResponse({"error": "Grid is already stopped."}, status_code=409)

    try:
        from shared_data import get_last_price
        yf_sym = gridbot_engine._to_yf_sym(grid["sym"])
        current_price = get_last_price(yf_sym) or grid["last_price"]
    except Exception:
        current_price = grid["last_price"]

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    grid["events"].append({
        "type": "MANUAL_STOP",
        "timestamp": now,
        "current_price": current_price,
    })
    save_paper_gridbot(grid)
    state = gridbot_sim.replay(grid["events"], grid["config"], current_price=current_price)
    return {"grid": grid, "state": state}
