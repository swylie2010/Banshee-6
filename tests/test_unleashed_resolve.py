import core_state as cs


def _reset(tmp_path, monkeypatch):
    monkeypatch.setattr(cs, "_UNLEASHED_PROFILES_FILE", tmp_path / "profiles.json")


def test_default_profile_has_per_surface_slots(tmp_path, monkeypatch):
    _reset(tmp_path, monkeypatch)
    data = cs.load_unleashed_profiles()
    d = data["profiles"]["default"]
    assert d["locked"] is True
    for surface in ("nexus", "smc"):
        assert d["surfaces"][surface]["mode"] == "nudge"
        assert d["surfaces"][surface]["text"] == cs.DEFAULT_UNLEASHED_OVERRIDE


def test_legacy_override_profile_migrates_to_surfaces(tmp_path, monkeypatch):
    _reset(tmp_path, monkeypatch)
    # Simulate an old-schema file with a single `override` string.
    import json
    (tmp_path / "profiles.json").write_text(json.dumps({
        "active": "u_old",
        "profiles": {"u_old": {"name": "Old", "override": "BE BOLD", "locked": False}},
    }))
    data = cs.load_unleashed_profiles()
    s = data["profiles"]["u_old"]["surfaces"]
    assert s["nexus"] == {"mode": "nudge", "text": "BE BOLD"}
    assert s["smc"] == {"mode": "nudge", "text": "BE BOLD"}
    assert "override" not in data["profiles"]["u_old"]
