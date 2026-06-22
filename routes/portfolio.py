"""routes/portfolio.py — portfolio CRUD and analysis.

Route handlers delegate to banshee_core helper functions so that tests can
monkeypatch banshee_core._PORTFOLIO_PATH and access bc._load_portfolios() etc.
directly. The helpers themselves live in banshee_core.py.
"""
from datetime import date as _date
from fastapi import APIRouter, Body
from fastapi.responses import JSONResponse

import portfolio_engine

router = APIRouter()


@router.get("/portfolios")
def get_portfolios():
    import banshee_core as _bc
    return _bc._load_portfolios()


@router.post("/portfolios")
def create_portfolio(body: dict = Body(...)):
    import banshee_core as _bc
    return _bc.create_portfolio(body)


@router.put("/portfolios/{portfolio_id}")
def update_portfolio(portfolio_id: str, body: dict = Body(...)):
    import banshee_core as _bc
    return _bc.update_portfolio(portfolio_id, body)


@router.get("/portfolios/{portfolio_id}/analysis")
def get_portfolio_analysis(portfolio_id: str):
    import banshee_core as _bc
    data = _bc._load_portfolios()
    portfolio = next((p for p in data["portfolios"] if p["id"] == portfolio_id), None)
    if not portfolio:
        return JSONResponse(status_code=404, content={"error": "Portfolio not found"})

    if _bc._ensure_transactions(portfolio, _date.today().isoformat()):
        _bc._save_portfolios(data)

    result = portfolio_engine.run_portfolio_analysis(portfolio, _date.today().isoformat())
    if isinstance(result, dict) and result.get("error") == "provider_unavailable":
        return JSONResponse(status_code=503, content=result)
    if "error" in result:
        return JSONResponse(status_code=400, content=result)
    return JSONResponse(content=result)
