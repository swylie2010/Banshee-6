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


def test_invalid_mode_reclamped_on_load(tmp_path, monkeypatch):
    _reset(tmp_path, monkeypatch)
    import json
    (tmp_path / "profiles.json").write_text(json.dumps({
        "active": "u_bad",
        "profiles": {"u_bad": {"name": "Bad", "locked": False, "surfaces": {
            "nexus": {"mode": "bogus", "text": "keep"},
            "smc":   {"mode": "rewrite", "text": "ok"},
        }}},
    }))
    data = cs.load_unleashed_profiles()
    s = data["profiles"]["u_bad"]["surfaces"]
    # Invalid mode is clamped back to the safe default; valid mode is preserved.
    assert s["nexus"] == {"mode": "nudge", "text": "keep"}
    assert s["smc"] == {"mode": "rewrite", "text": "ok"}


def test_extraneous_surface_key_dropped_on_load(tmp_path, monkeypatch):
    _reset(tmp_path, monkeypatch)
    import json
    (tmp_path / "profiles.json").write_text(json.dumps({
        "active": "u_extra",
        "profiles": {"u_extra": {"name": "Extra", "locked": False, "surfaces": {
            "nexus": {"mode": "nudge", "text": "n"},
            "smc":   {"mode": "nudge", "text": "s"},
            "macro": {"mode": "nudge", "text": "should vanish"},
        }}},
    }))
    data = cs.load_unleashed_profiles()
    assert set(data["profiles"]["u_extra"]["surfaces"].keys()) == {"nexus", "smc"}


def test_non_dict_profile_entry_recovered_on_load(tmp_path, monkeypatch):
    _reset(tmp_path, monkeypatch)
    import json
    (tmp_path / "profiles.json").write_text(json.dumps({
        "active": "default",
        "profiles": {"u_corrupt": "not a dict at all"},
    }))
    data = cs.load_unleashed_profiles()  # must not raise
    rec = data["profiles"]["u_corrupt"]
    assert rec["locked"] is False
    assert set(rec["surfaces"].keys()) == {"nexus", "smc"}
    assert rec["surfaces"]["nexus"] == {"mode": "nudge", "text": ""}


def test_resolve_nudge_appends(tmp_path, monkeypatch):
    _reset(tmp_path, monkeypatch)
    cs.upsert_unleashed_profile("", "P", {"nexus": {"mode": "nudge", "text": "ADD ME"},
                                          "smc":   {"mode": "nudge", "text": ""}})
    data = cs.load_unleashed_profiles()
    pid = [k for k in data["profiles"] if k != "default"][0]
    cs.set_active_unleashed_profile(pid)
    assert cs.resolve_unleashed("nexus", "BASE") == "BASE\nADD ME"
    # blank text ⇒ stock base
    assert cs.resolve_unleashed("smc", "SMCBASE") == "SMCBASE"


def test_resolve_rewrite_replaces(tmp_path, monkeypatch):
    _reset(tmp_path, monkeypatch)
    cs.upsert_unleashed_profile("", "P", {"nexus": {"mode": "rewrite", "text": "WHOLE NEW"},
                                          "smc":   {"mode": "nudge", "text": ""}})
    data = cs.load_unleashed_profiles()
    pid = [k for k in data["profiles"] if k != "default"][0]
    cs.set_active_unleashed_profile(pid)
    assert cs.resolve_unleashed("nexus", "BASE") == "WHOLE NEW"


def test_resolve_unknown_surface_returns_base(tmp_path, monkeypatch):
    _reset(tmp_path, monkeypatch)
    assert cs.resolve_unleashed("nope", "BASE") == "BASE"
