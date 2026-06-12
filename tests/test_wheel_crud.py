"""CRUD round-trip for /wheels using FastAPI's TestClient against a temp store.

Mirrors the isolation strategy of test_portfolio_crud.py:
  - monkeypatch.setattr(bc, "_WHEELS_PATH", tmp_path / "...") redirects all
    load/save operations to a throwaway file so real banshee_wheels.json is
    never touched.
  - Uses a pytest fixture for the client to keep individual tests lean.
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import banshee_core as bc
import routes.options as _opts_mod
from fastapi.testclient import TestClient


@pytest.fixture
def wheels_client(tmp_path, monkeypatch):
    """TestClient with the wheel store redirected to a fresh tmp file."""
    p = tmp_path / "banshee_wheels.json"
    p.write_text('{"wheels": []}', encoding="utf-8")
    # Patch both bc and routes.options since _load_wheels/_save_wheels live there now
    monkeypatch.setattr(bc, "_WHEELS_PATH", p)
    monkeypatch.setattr(_opts_mod, "_WHEELS_PATH", p)
    return TestClient(bc.app)


# ── happy-path CRUD + event round-trip ───────────────────────────────────────

def test_create_list_event_delete_roundtrip(wheels_client):
    c = wheels_client

    snap = {
        "underlying": "SPY",
        "strike": 100,
        "expiry": "2026-07-17",
        "dte": 40,
        "mid": 2.0,
        "delta": -0.25,
    }
    r = c.post("/wheels", json={"candidate_snapshot": snap, "underlying": "SPY", "name": "SPY Wheel"})
    assert r.status_code == 200
    wid = r.json()["id"]
    assert r.json()["state"]["state"] == "CASH"

    # newly created wheel appears in the list
    lst = c.get("/wheels").json()["wheels"]
    assert any(w["id"] == wid for w in lst)

    # post a legal event → state advances to CSP_OPEN + premium accumulates
    ev = {
        "type": "SOLD_CSP",
        "strike": 100,
        "expiry": "2026-07-17",
        "dte": 40,
        "mid": 2.0,
        "delta": -0.25,
    }
    r2 = c.post(f"/wheels/{wid}/event", json={"event": ev})
    assert r2.status_code == 200
    assert r2.json()["state"]["state"] == "CSP_OPEN"
    assert r2.json()["state"]["totals"]["premium_collected"] == 200.0

    # fresh GET proves the event persisted to disk and replays the same state
    again = c.get(f"/wheels/{wid}").json()
    assert again["state"]["state"] == "CSP_OPEN"
    assert again["state"]["totals"]["premium_collected"] == 200.0

    # illegal event from CSP_OPEN → 400 with a clear reason
    bad = c.post(f"/wheels/{wid}/event", json={"event": {"type": "SOLD_CC"}})
    assert bad.status_code == 400
    assert "Can't do" in bad.json()["error"]

    # delete removes from list
    assert c.delete(f"/wheels/{wid}").json()["ok"] is True
    assert all(w["id"] != wid for w in c.get("/wheels").json()["wheels"])


# ── validation: missing underlying ───────────────────────────────────────────

def test_create_without_underlying_is_rejected(wheels_client):
    r = wheels_client.post("/wheels", json={"candidate_snapshot": {}})
    assert r.status_code == 400


# ── 404 for unknown wheel IDs ─────────────────────────────────────────────────

def test_unknown_wheel_id_returns_404(wheels_client):
    c = wheels_client
    assert c.get("/wheels/does-not-exist").status_code == 404
    assert c.post("/wheels/does-not-exist/event", json={"event": {"type": "SOLD_CSP"}}).status_code == 404
    assert c.delete("/wheels/does-not-exist").status_code == 404
