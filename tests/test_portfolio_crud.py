"""Tests for portfolio CRUD + migration persistence in banshee_core.py.

These call the route functions directly (FastAPI's Body(...) default is inert
on a direct call) and monkeypatch the on-disk portfolio path to a tmp file so
the real banshee_portfolio.json is never touched.
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import banshee_core as bc


@pytest.fixture
def tmp_portfolios(tmp_path, monkeypatch):
    """Point the portfolio store at a fresh tmp file for each test."""
    p = tmp_path / "banshee_portfolio.json"
    p.write_text(json.dumps({"portfolios": []}), encoding="utf-8")
    monkeypatch.setattr(bc, "_PORTFOLIO_PATH", p)
    return p


def test_create_portfolio_stores_transactions(tmp_portfolios):
    body = {
        "preset_id": "preset_x",
        "name": "T",
        "thesis": "test",
        "transactions": [
            {"id": "tx_1", "type": "BUY", "sym": "NVDA", "shares": 10,
             "price": 120.0, "date": "2024-01-15", "opening": True},
        ],
        "holdings": [{"sym": "NVDA", "cls": "TECH", "shares": 10}],
    }
    created = bc.create_portfolio(body)
    assert created["id"]
    assert created["transactions"] == body["transactions"]
    assert created["holdings"] == body["holdings"]
    # round-trips through disk
    on_disk = json.loads(tmp_portfolios.read_text(encoding="utf-8"))
    assert on_disk["portfolios"][0]["transactions"] == body["transactions"]


def test_create_portfolio_defaults_transactions_to_empty(tmp_portfolios):
    created = bc.create_portfolio({"name": "Empty"})
    assert created["transactions"] == []
    assert created["holdings"] == []


def test_update_portfolio_replaces_transactions(tmp_portfolios):
    created = bc.create_portfolio({
        "name": "T",
        "transactions": [{"id": "tx_1", "type": "BUY", "sym": "NVDA",
                          "shares": 10, "price": 120.0, "date": "2024-01-15"}],
        "holdings": [{"sym": "NVDA", "cls": "TECH", "shares": 10}],
    })
    new_txns = [
        {"id": "tx_1", "type": "BUY", "sym": "NVDA", "shares": 10, "price": 120.0, "date": "2024-01-15"},
        {"id": "tx_2", "type": "SELL", "sym": "NVDA", "shares": 4, "price": 160.0, "date": "2024-06-01"},
    ]
    updated = bc.update_portfolio(created["id"], {
        "transactions": new_txns,
        "holdings": [{"sym": "NVDA", "cls": "TECH", "shares": 6}],
    })
    assert updated["transactions"] == new_txns
    assert updated["holdings"][0]["shares"] == 6
    on_disk = json.loads(tmp_portfolios.read_text(encoding="utf-8"))
    assert len(on_disk["portfolios"][0]["transactions"]) == 2


def test_update_portfolio_unknown_id_404(tmp_portfolios):
    res = bc.update_portfolio("nope", {"transactions": []})
    # JSONResponse with 404
    assert getattr(res, "status_code", None) == 404
