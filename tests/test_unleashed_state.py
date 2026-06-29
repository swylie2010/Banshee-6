import core_state


def test_load_unleashed_defaults_to_disabled(tmp_path, monkeypatch):
    monkeypatch.setattr(core_state, "_UNLEASHED_FILE", tmp_path / "u.json")
    assert core_state.load_unleashed() == {"enabled": False}


def test_save_then_load_roundtrips(tmp_path, monkeypatch):
    monkeypatch.setattr(core_state, "_UNLEASHED_FILE", tmp_path / "u.json")
    core_state.save_unleashed({"enabled": True})
    assert core_state.load_unleashed() == {"enabled": True}


def test_load_unleashed_survives_corrupt_file(tmp_path, monkeypatch):
    f = tmp_path / "u.json"
    f.write_text("not json{{")
    monkeypatch.setattr(core_state, "_UNLEASHED_FILE", f)
    assert core_state.load_unleashed() == {"enabled": False}
