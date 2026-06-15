"""routes/gridbot.py — Gridbot calculator endpoint."""
import asyncio

from fastapi import APIRouter, Body
from fastapi.responses import JSONResponse

import gridbot_engine

router = APIRouter()


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
