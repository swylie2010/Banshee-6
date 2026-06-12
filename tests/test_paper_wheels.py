import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import json, uuid
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
import banshee_core as bc
import routes.options as _opts_mod
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
    with patch.object(_opts_mod, "load_paper_wheels", return_value={"wheels": []}):
        r = client.get("/paper-wheels")
    assert r.status_code == 200
    assert r.json()["wheels"] == []


def test_list_returns_wheels():
    wheels = [_make_wheel("SPY"), _make_wheel("QQQ")]
    with patch.object(_opts_mod, "load_paper_wheels", return_value={"wheels": wheels}):
        r = client.get("/paper-wheels")
    assert r.status_code == 200
    assert len(r.json()["wheels"]) == 2


# ── GET /paper-wheels/alerts ──────────────────────────────────────────────────

def test_alerts_returns_only_attention_wheels():
    wheels = [
        _make_wheel("SPY", needs_attention=True, attention_reason="checkpoint_due"),
        _make_wheel("QQQ", needs_attention=False),
    ]
    with patch.object(_opts_mod, "load_paper_wheels", return_value={"wheels": wheels}):
        r = client.get("/paper-wheels/alerts")
    assert r.status_code == 200
    alerts = r.json()["alerts"]
    assert len(alerts) == 1
    assert alerts[0]["underlying"] == "SPY"
    assert alerts[0]["attention_reason"] == "checkpoint_due"


def test_alerts_returns_empty_when_none():
    with patch.object(_opts_mod, "load_paper_wheels", return_value={"wheels": [_make_wheel()]}):
        r = client.get("/paper-wheels/alerts")
    assert r.json()["alerts"] == []


# ── DELETE /paper-wheels/{id} ─────────────────────────────────────────────────

def test_delete_removes_wheel():
    w = _make_wheel()
    data = {"wheels": [w]}
    saved = {}
    def fake_save(d): saved.update(d)
    with patch.object(_opts_mod, "load_paper_wheels", return_value=data), \
         patch.object(_opts_mod, "save_paper_wheels", side_effect=fake_save), \
         patch("routes.options.alpaca_options.cancel_order", return_value=True):
        r = client.delete(f"/paper-wheels/{w['id']}")
    assert r.status_code == 200
    assert r.json()["ok"] is True
    assert saved["wheels"] == []


def test_delete_cancels_unfilled_order():
    w = _make_wheel(events=[_sold_csp(order_id="open-ord")])
    data = {"wheels": [w]}
    cancel_called = []
    with patch.object(_opts_mod, "load_paper_wheels", return_value=data), \
         patch.object(_opts_mod, "save_paper_wheels"), \
         patch("routes.options.alpaca_options.cancel_order",
               side_effect=lambda oid: cancel_called.append(oid) or True):
        client.delete(f"/paper-wheels/{w['id']}")
    assert "open-ord" in cancel_called


def test_delete_404_for_unknown_id():
    with patch.object(_opts_mod, "load_paper_wheels", return_value={"wheels": []}):
        r = client.delete("/paper-wheels/nonexistent")
    assert r.status_code == 404


# ── POST /paper-wheels ────────────────────────────────────────────────────────

def _candidate_snap():
    return {
        "candidate": {
            "underlying": "SPY", "strike": 450.0, "expiry": "2026-08-15",
            "dte": 45, "mid": 2.35, "delta": -0.25,
            "bid": 2.20, "ask": 2.50, "iv": 0.18,
            "open_interest": 5000, "volume": 1200, "spot": 465.0,
        }
    }


def _fake_order(order_id="placed-ord"):
    return {"order_id": order_id, "status": "accepted", "submitted_at": "2026-06-10T10:00:00"}


def test_create_paper_wheel_places_csp_and_returns_pending_fill():
    saved = {}
    def fake_save(d): saved.update(d)
    with patch.object(_opts_mod, "load_paper_wheels", return_value={"wheels": []}), \
         patch.object(_opts_mod, "save_paper_wheels", side_effect=fake_save), \
         patch("routes.options.alpaca_options.place_option_order", return_value=_fake_order()):
        r = client.post("/paper-wheels", json={
            "candidate_snapshot": _candidate_snap(), "underlying": "SPY", "name": "Test"
        })
    assert r.status_code == 200
    body = r.json()
    assert body["pending_fill"] is True
    assert len(saved["wheels"]) == 1
    ev = saved["wheels"][0]["events"][0]
    assert ev["type"] == "SOLD_CSP"
    assert ev["alpaca_order_id"] == "placed-ord"
    assert ev["fill_price"] is None


def test_create_paper_wheel_rejected_order_no_record_created():
    saved = {}
    def fake_save(d): saved.update(d)
    with patch.object(_opts_mod, "load_paper_wheels", return_value={"wheels": []}), \
         patch.object(_opts_mod, "save_paper_wheels", side_effect=fake_save), \
         patch("routes.options.alpaca_options.place_option_order",
               side_effect=alpaca_options.AlpacaOrderRejectedError("insufficient buying power")):
        r = client.post("/paper-wheels", json={
            "candidate_snapshot": _candidate_snap(), "underlying": "SPY"
        })
    assert r.status_code == 400
    assert "insufficient buying power" in r.json()["plain"]
    assert saved == {}  # no record created


def test_create_paper_wheel_alpaca_unavailable_returns_503():
    with patch.object(_opts_mod, "load_paper_wheels", return_value={"wheels": []}), \
         patch("routes.options.alpaca_options.place_option_order",
               side_effect=alpaca_options.AlpacaUnavailableError("timeout")):
        r = client.post("/paper-wheels", json={
            "candidate_snapshot": _candidate_snap(), "underlying": "SPY"
        })
    assert r.status_code == 503
    assert r.json()["error"] == "alpaca_unavailable"


def test_create_paper_wheel_missing_underlying_returns_400():
    r = client.post("/paper-wheels", json={"candidate_snapshot": {}, "underlying": ""})
    assert r.status_code == 400


# ── GET /paper-wheels/{id} ────────────────────────────────────────────────────

def test_get_paper_wheel_returns_pending_fill_true_when_no_fill_price():
    w = _make_wheel(events=[_sold_csp(fill_price=None)])
    with patch.object(_opts_mod, "load_paper_wheels", return_value={"wheels": [w]}):
        r = client.get(f"/paper-wheels/{w['id']}")
    assert r.status_code == 200
    assert r.json()["pending_fill"] is True


def test_get_paper_wheel_returns_pending_fill_false_when_filled():
    w = _make_wheel(events=[_sold_csp(fill_price=2.40)])
    with patch.object(_opts_mod, "load_paper_wheels", return_value={"wheels": [w]}):
        r = client.get(f"/paper-wheels/{w['id']}")
    assert r.status_code == 200
    assert r.json()["pending_fill"] is False


def test_get_paper_wheel_404_unknown():
    with patch.object(_opts_mod, "load_paper_wheels", return_value={"wheels": []}):
        r = client.get("/paper-wheels/nope")
    assert r.status_code == 404


# ── GET /paper-wheels/{id}/calls ──────────────────────────────────────────────

def test_get_calls_returns_chain():
    w = _make_wheel()
    fake_calls = [{"type": "call", "strike": 460.0, "expiry": "2026-08-15",
                   "dte": 65, "mid": 1.50, "delta": 0.28, "occ_symbol": "SPY260815C00460000",
                   "underlying": "SPY", "spot": 465.0, "bid": 1.40, "ask": 1.60,
                   "iv": 0.18, "open_interest": 0, "volume": 0}]
    with patch.object(_opts_mod, "load_paper_wheels", return_value={"wheels": [w]}), \
         patch("routes.options.alpaca_options.fetch_calls_chain", return_value=fake_calls):
        r = client.get(f"/paper-wheels/{w['id']}/calls")
    assert r.status_code == 200
    assert len(r.json()["calls"]) == 1
    assert r.json()["calls"][0]["strike"] == 460.0


def test_get_calls_503_on_unavailable():
    w = _make_wheel()
    with patch.object(_opts_mod, "load_paper_wheels", return_value={"wheels": [w]}), \
         patch("routes.options.alpaca_options.fetch_calls_chain",
               side_effect=alpaca_options.AlpacaUnavailableError("timeout")):
        r = client.get(f"/paper-wheels/{w['id']}/calls")
    assert r.status_code == 503


# ── POST /paper-wheels/{id}/submit-cc ────────────────────────────────────────

def _assigned_wheel():
    """Wheel that reached SHARES state (assigned CSP, no CC yet)."""
    return _make_wheel(events=[
        _sold_csp(fill_price=2.40),
        {"type": "CHECKPOINT_HELD", "leg": "csp"},
        {"type": "ASSIGNED", "strike": 450.0, "expiry_price": 445.0},
    ])


def test_submit_cc_places_order_and_appends_event():
    w = _assigned_wheel()
    data = {"wheels": [w]}
    saved = {}
    def fake_save(d): saved.update(d)
    with patch.object(_opts_mod, "load_paper_wheels", return_value=data), \
         patch.object(_opts_mod, "save_paper_wheels", side_effect=fake_save), \
         patch("routes.options.alpaca_options.place_option_order",
               return_value={"order_id": "cc-ord-1", "status": "accepted", "submitted_at": "2026-06-10T11:00:00"}):
        r = client.post(f"/paper-wheels/{w['id']}/submit-cc", json={
            "strike": 455.0, "expiry": "2026-08-15", "mid": 1.80, "delta": 0.28, "dte": 45
        })
    assert r.status_code == 200
    body = r.json()
    assert body["pending_fill"] is True
    assert body["state"]["state"] == "CC_OPEN"
    last_ev = saved["wheels"][0]["events"][-1]
    assert last_ev["type"] == "SOLD_CC"
    assert last_ev["alpaca_order_id"] == "cc-ord-1"
    assert last_ev["fill_price"] is None


def test_submit_cc_rejected_returns_400():
    w = _assigned_wheel()
    with patch.object(_opts_mod, "load_paper_wheels", return_value={"wheels": [w]}), \
         patch("routes.options.alpaca_options.place_option_order",
               side_effect=alpaca_options.AlpacaOrderRejectedError("insufficient")):
        r = client.post(f"/paper-wheels/{w['id']}/submit-cc", json={
            "strike": 455.0, "expiry": "2026-08-15", "mid": 1.80
        })
    assert r.status_code == 400


def test_submit_cc_wrong_state_returns_400():
    # Wheel in CASH state cannot submit a CC
    w = _make_wheel(events=[])  # CASH state
    with patch.object(_opts_mod, "load_paper_wheels", return_value={"wheels": [w]}):
        r = client.post(f"/paper-wheels/{w['id']}/submit-cc", json={
            "strike": 455.0, "expiry": "2026-08-15", "mid": 1.80
        })
    assert r.status_code == 400
    assert "SHARES" in r.json()["error"]
