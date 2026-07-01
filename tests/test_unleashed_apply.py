import banshee_ai
import core_state


def test_apply_uses_active_profile_override(tmp_path, monkeypatch):
    monkeypatch.setattr(core_state, "_UNLEASHED_PROFILES_FILE", tmp_path / "p.json")
    pid = core_state.upsert_unleashed_profile(None, "Aggro", "\n\nAGGRO OVERRIDE")["id"]
    core_state.set_active_unleashed_profile(pid)
    out = banshee_ai._apply_unleashed_override("BASE", unleashed=True)
    assert out == "BASE\n\nAGGRO OVERRIDE"


def test_apply_off_returns_base(tmp_path, monkeypatch):
    monkeypatch.setattr(core_state, "_UNLEASHED_PROFILES_FILE", tmp_path / "p.json")
    assert banshee_ai._apply_unleashed_override("BASE", unleashed=False) == "BASE"


def test_apply_default_contains_canonical_block(tmp_path, monkeypatch):
    monkeypatch.setattr(core_state, "_UNLEASHED_PROFILES_FILE", tmp_path / "p.json")
    out = banshee_ai._apply_unleashed_override("BASE", unleashed=True)
    assert "UNLEASHED OVERRIDE" in out


def test_smc_system_prompt_reads_file_each_call(tmp_path, monkeypatch):
    monkeypatch.setattr(banshee_ai, "_PROMPTS_DIR", str(tmp_path))
    (tmp_path / "smc.txt").write_text("SMC V1")
    assert banshee_ai._smc_system_prompt() == "SMC V1"
    (tmp_path / "smc.txt").write_text("SMC V2")
    assert banshee_ai._smc_system_prompt() == "SMC V2"
