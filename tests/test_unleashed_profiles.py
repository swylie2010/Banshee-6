import json
import core_state


def _patch(tmp_path, monkeypatch):
    monkeypatch.setattr(core_state, "_UNLEASHED_PROFILES_FILE", tmp_path / "p.json")


def test_load_seeds_default_when_missing(tmp_path, monkeypatch):
    _patch(tmp_path, monkeypatch)
    data = core_state.load_unleashed_profiles()
    assert data["active"] == "default"
    assert data["profiles"]["default"]["locked"] is True
    assert "UNLEASHED OVERRIDE" in data["profiles"]["default"]["surfaces"]["nexus"]["text"]
    assert "UNLEASHED OVERRIDE" in data["profiles"]["default"]["surfaces"]["smc"]["text"]


def test_get_active_override_defaults_to_constant(tmp_path, monkeypatch):
    _patch(tmp_path, monkeypatch)
    assert core_state.resolve_unleashed("nexus", "BASE") == "BASE\n" + core_state.DEFAULT_UNLEASHED_OVERRIDE.strip()


def test_upsert_creates_and_activates(tmp_path, monkeypatch):
    _patch(tmp_path, monkeypatch)
    surfaces = {
        "nexus": {"mode": "nudge", "text": "OVERRIDE ONE"},
        "smc":   {"mode": "nudge", "text": "OVERRIDE ONE"},
    }
    res = core_state.upsert_unleashed_profile(None, "My Setting 1", surfaces)
    assert res["ok"] is True
    pid = res["id"]
    core_state.set_active_unleashed_profile(pid)
    prof = core_state.load_unleashed_profiles()["profiles"][pid]
    assert prof["surfaces"]["nexus"] == {"mode": "nudge", "text": "OVERRIDE ONE"}
    assert prof["surfaces"]["smc"] == {"mode": "nudge", "text": "OVERRIDE ONE"}
    assert core_state.get_active_unleashed_profile() == {"id": pid, "name": "My Setting 1"}


def test_created_profile_has_locked_false(tmp_path, monkeypatch):
    _patch(tmp_path, monkeypatch)
    surfaces = {
        "nexus": {"mode": "nudge", "text": "OV"},
        "smc":   {"mode": "nudge", "text": "OV"},
    }
    pid = core_state.upsert_unleashed_profile(None, "Custom", surfaces)["id"]
    prof = core_state.load_unleashed_profiles()["profiles"][pid]
    # Stored shape matches the documented {name, locked, surfaces} contract.
    assert prof == {
        "name": "Custom",
        "locked": False,
        "surfaces": {
            "nexus": {"mode": "nudge", "text": "OV"},
            "smc":   {"mode": "nudge", "text": "OV"},
        },
    }


def test_cannot_edit_locked_default(tmp_path, monkeypatch):
    _patch(tmp_path, monkeypatch)
    evil_surfaces = {"nexus": {"mode": "nudge", "text": "evil"}, "smc": {"mode": "nudge", "text": "evil"}}
    res = core_state.upsert_unleashed_profile("default", "Hacked", evil_surfaces)
    assert res["ok"] is False
    assert core_state.resolve_unleashed("nexus", "BASE") == "BASE\n" + core_state.DEFAULT_UNLEASHED_OVERRIDE.strip()


def test_cannot_delete_default(tmp_path, monkeypatch):
    _patch(tmp_path, monkeypatch)
    res = core_state.delete_unleashed_profile("default")
    assert res["ok"] is False
    assert "default" in core_state.load_unleashed_profiles()["profiles"]


def test_delete_active_falls_back_to_default(tmp_path, monkeypatch):
    _patch(tmp_path, monkeypatch)
    surfaces = {"nexus": {"mode": "nudge", "text": "X"}, "smc": {"mode": "nudge", "text": "X"}}
    pid = core_state.upsert_unleashed_profile(None, "Temp", surfaces)["id"]
    core_state.set_active_unleashed_profile(pid)
    core_state.delete_unleashed_profile(pid)
    d = core_state.load_unleashed_profiles()
    assert d["active"] == "default"
    assert core_state.resolve_unleashed("nexus", "BASE") == "BASE\n" + core_state.DEFAULT_UNLEASHED_OVERRIDE.strip()


def test_default_override_is_immutable_on_load(tmp_path, monkeypatch):
    _patch(tmp_path, monkeypatch)
    (tmp_path / "p.json").write_text(json.dumps({
        "active": "default",
        "profiles": {"default": {"name": "Default Unleashed", "override": "TAMPERED", "locked": False}},
    }))
    data = core_state.load_unleashed_profiles()
    assert data["profiles"]["default"]["surfaces"]["nexus"]["text"] == core_state.DEFAULT_UNLEASHED_OVERRIDE
    assert data["profiles"]["default"]["surfaces"]["smc"]["text"] == core_state.DEFAULT_UNLEASHED_OVERRIDE
    assert data["profiles"]["default"]["locked"] is True


def test_corrupt_file_falls_back(tmp_path, monkeypatch):
    _patch(tmp_path, monkeypatch)
    (tmp_path / "p.json").write_text("not json{{")
    assert core_state.resolve_unleashed("nexus", "BASE") == "BASE\n" + core_state.DEFAULT_UNLEASHED_OVERRIDE.strip()
