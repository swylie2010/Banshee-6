"""tests/test_unleashed_route.py — HTTP surface tests for /unleashed toggle."""

from fastapi.testclient import TestClient
import banshee_core as bc
import core_state


def _client(tmp_path, monkeypatch):
    monkeypatch.setattr(core_state, "_UNLEASHED_FILE", tmp_path / "u.json")
    return TestClient(bc.app)


def test_get_unleashed_defaults_disabled(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    r = c.get("/unleashed")
    assert r.status_code == 200
    assert r.json() == {"enabled": False}


def test_post_unleashed_persists(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    r = c.post("/unleashed", json={"enabled": True})
    assert r.status_code == 200
    assert r.json()["enabled"] is True
    assert c.get("/unleashed").json() == {"enabled": True}
