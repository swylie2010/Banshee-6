import core_state
import banshee_core as bc
from fastapi.testclient import TestClient


def _client(tmp_path, monkeypatch):
    monkeypatch.setattr(core_state, "_UNLEASHED_PROFILES_FILE", tmp_path / "p.json")
    return TestClient(bc.app)


def test_list_profiles_seeds_default(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    r = c.get("/unleashed/profiles")
    assert r.status_code == 200
    d = r.json()
    assert d["active"] == "default"
    assert any(p["id"] == "default" and p["locked"] for p in d["profiles"])


def test_create_and_activate_profile(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    surfaces = {
        "nexus": {"mode": "nudge", "text": "OV1"},
        "smc": {"mode": "nudge", "text": "OV1"},
    }
    r = c.post("/unleashed/profiles", json={"name": "My Setting 1", "surfaces": surfaces})
    assert r.status_code == 200
    pid = r.json()["id"]
    r2 = c.post("/unleashed/profiles/active", json={"id": pid})
    assert r2.status_code == 200
    assert core_state.resolve_unleashed("nexus", "BASE") == "BASE\nOV1"
    assert core_state.resolve_unleashed("smc", "BASE") == "BASE\nOV1"


def test_list_profiles_returns_surfaces_not_override(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    surfaces = {
        "nexus": {"mode": "rewrite", "text": "N-TEXT"},
        "smc": {"mode": "nudge", "text": "S-TEXT"},
    }
    pid = c.post("/unleashed/profiles", json={"name": "Surfaced", "surfaces": surfaces}).json()["id"]

    profiles = c.get("/unleashed/profiles").json()["profiles"]

    # No profile object may carry the dead 'override' key.
    assert all("override" not in p for p in profiles)

    created = next(p for p in profiles if p["id"] == pid)
    assert created["surfaces"]["nexus"] == {"mode": "rewrite", "text": "N-TEXT"}
    assert created["surfaces"]["smc"] == {"mode": "nudge", "text": "S-TEXT"}

    # The Default profile must also expose surfaces.
    default = next(p for p in profiles if p["id"] == "default")
    assert "surfaces" in default
    assert "nexus" in default["surfaces"] and "smc" in default["surfaces"]


def test_edit_default_rejected(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    surfaces = {
        "nexus": {"mode": "nudge", "text": "y"},
        "smc": {"mode": "nudge", "text": "y"},
    }
    r = c.post("/unleashed/profiles", json={"id": "default", "name": "x", "surfaces": surfaces})
    assert r.status_code == 422


def test_delete_default_rejected(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    r = c.delete("/unleashed/profiles/default")
    assert r.status_code == 422


def test_delete_profile(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    surfaces = {
        "nexus": {"mode": "nudge", "text": "Z"},
        "smc": {"mode": "nudge", "text": "Z"},
    }
    pid = c.post("/unleashed/profiles", json={"name": "Temp", "surfaces": surfaces}).json()["id"]
    r = c.delete(f"/unleashed/profiles/{pid}")
    assert r.status_code == 200
    ids = [p["id"] for p in c.get("/unleashed/profiles").json()["profiles"]]
    assert pid not in ids


def test_set_active_unknown_rejected(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    r = c.post("/unleashed/profiles/active", json={"id": "nope"})
    assert r.status_code == 422
