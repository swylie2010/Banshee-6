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


# ── migration persistence (Phase 2) ─────────────────────────────
def test_ensure_transactions_migrates_holdings_once():
    pf = {
        "id": "pf_legacy",
        "holdings": [{"sym": "NVDA", "shares": 10, "entry_price": 120.0,
                      "entry_date": "2024-01-15", "cls": "TECH"}],
    }
    changed = bc._ensure_transactions(pf, "2026-06-08")
    assert changed is True
    assert len(pf["transactions"]) == 1
    t = pf["transactions"][0]
    assert t["type"] == "BUY" and t["sym"] == "NVDA" and t["opening"] is True
    assert t["price"] == 120.0 and t["date"] == "2024-01-15"


def test_ensure_transactions_idempotent():
    pf = {
        "id": "pf_legacy",
        "holdings": [{"sym": "NVDA", "shares": 10, "entry_price": 120.0,
                      "entry_date": "2024-01-15", "cls": "TECH"}],
    }
    bc._ensure_transactions(pf, "2026-06-08")          # first: migrates
    snapshot = list(pf["transactions"])
    changed = bc._ensure_transactions(pf, "2026-06-08")  # second: no-op
    assert changed is False
    assert pf["transactions"] == snapshot


def test_ensure_transactions_no_holdings_no_change():
    pf = {"id": "pf_empty"}
    assert bc._ensure_transactions(pf, "2026-06-08") is False
    assert "transactions" not in pf or pf["transactions"] == []


def test_ensure_transactions_existing_txns_untouched():
    pf = {
        "id": "pf_new",
        "transactions": [{"id": "tx_1", "type": "DEPOSIT", "amount": 1000.0, "date": "2024-01-01"}],
        "holdings": [{"sym": "X", "cls": "TECH", "shares": 1}],
    }
    assert bc._ensure_transactions(pf, "2026-06-08") is False
    assert len(pf["transactions"]) == 1 and pf["transactions"][0]["type"] == "DEPOSIT"


def test_migration_write_back_round_trips(tmp_portfolios):
    """The migrate-once helper + save persists transactions to disk."""
    data = bc._load_portfolios()
    data["portfolios"].append({
        "id": "pf_legacy",
        "name": "Legacy",
        "holdings": [{"sym": "NVDA", "shares": 10, "entry_price": 120.0,
                      "entry_date": "2024-01-15", "cls": "TECH"}],
    })
    bc._save_portfolios(data)

    # simulate what the analysis endpoint does on first read
    data = bc._load_portfolios()
    pf = next(p for p in data["portfolios"] if p["id"] == "pf_legacy")
    if bc._ensure_transactions(pf, "2026-06-08"):
        bc._save_portfolios(data)

    on_disk = json.loads(tmp_portfolios.read_text(encoding="utf-8"))
    persisted = on_disk["portfolios"][0]
    assert len(persisted["transactions"]) == 1
    assert persisted["transactions"][0]["opening"] is True
