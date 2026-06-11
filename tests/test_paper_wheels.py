import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import json, uuid
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
import banshee_core as bc
import alpaca_options

client = TestClient(bc.app)

# ── helpers ───────────────────────────────────────────────────────────────────

def _make_wheel(underlying="SPY", needs_attention=False, attention_reason=None, events=None):
    return {
        "id": str(uuid.uuid4()),
        "name": f"{underlying} Paper Wheel",
        "underlying": underlying,
        "created": "2026-06-10",
        "candidate_snapshot": {},
        "events": events or [],
        "needs_attention": needs_attention,
        "attention_reason": attention_reason,
        "live": None,
        "last_polled": None,
    }


def _sold_csp(order_id="ord-1", fill_price=None):
    return {
        "type": "SOLD_CSP", "strike": 450.0, "expiry": "2026-08-15",
        "dte": 45, "mid": 2.35, "delta": -0.25,
        "alpaca_order_id": order_id, "fill_price": fill_price,
    }


# ── GET /paper-wheels ─────────────────────────────────────────────────────────

def test_list_returns_empty_list():
    with patch.object(bc, "_load_paper_wheels", return_value={"wheels": []}):
        r = client.get("/paper-wheels")
    assert r.status_code == 200
    assert r.json()["wheels"] == []


def test_list_returns_wheels():
    wheels = [_make_wheel("SPY"), _make_wheel("QQQ")]
    with patch.object(bc, "_load_paper_wheels", return_value={"wheels": wheels}):
        r = client.get("/paper-wheels")
    assert r.status_code == 200
    assert len(r.json()["wheels"]) == 2


# ── GET /paper-wheels/alerts ──────────────────────────────────────────────────

def test_alerts_returns_only_attention_wheels():
    wheels = [
        _make_wheel("SPY", needs_attention=True, attention_reason="checkpoint_due"),
        _make_wheel("QQQ", needs_attention=False),
    ]
    with patch.object(bc, "_load_paper_wheels", return_value={"wheels": wheels}):
        r = client.get("/paper-wheels/alerts")
    assert r.status_code == 200
    alerts = r.json()["alerts"]
    assert len(alerts) == 1
    assert alerts[0]["underlying"] == "SPY"
    assert alerts[0]["attention_reason"] == "checkpoint_due"


def test_alerts_returns_empty_when_none():
    with patch.object(bc, "_load_paper_wheels", return_value={"wheels": [_make_wheel()]}):
        r = client.get("/paper-wheels/alerts")
    assert r.json()["alerts"] == []


# ── DELETE /paper-wheels/{id} ─────────────────────────────────────────────────

def test_delete_removes_wheel():
    w = _make_wheel()
    data = {"wheels": [w]}
    saved = {}
    def fake_save(d): saved.update(d)
    with patch.object(bc, "_load_paper_wheels", return_value=data), \
         patch.object(bc, "_save_paper_wheels", side_effect=fake_save), \
         patch("banshee_core.alpaca_options.cancel_order", return_value=True):
        r = client.delete(f"/paper-wheels/{w['id']}")
    assert r.status_code == 200
    assert r.json()["ok"] is True
    assert saved["wheels"] == []


def test_delete_cancels_unfilled_order():
    w = _make_wheel(events=[_sold_csp(order_id="open-ord")])
    data = {"wheels": [w]}
    cancel_called = []
    with patch.object(bc, "_load_paper_wheels", return_value=data), \
         patch.object(bc, "_save_paper_wheels"), \
         patch("banshee_core.alpaca_options.cancel_order",
               side_effect=lambda oid: cancel_called.append(oid) or True):
        client.delete(f"/paper-wheels/{w['id']}")
    assert "open-ord" in cancel_called


def test_delete_404_for_unknown_id():
    with patch.object(bc, "_load_paper_wheels", return_value={"wheels": []}):
        r = client.delete("/paper-wheels/nonexistent")
    assert r.status_code == 404
