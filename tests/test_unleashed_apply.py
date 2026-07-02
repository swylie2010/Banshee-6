import banshee_ai
import core_state as cs


def test_guard_is_always_last(monkeypatch, tmp_path):
    monkeypatch.setattr(cs, "_UNLEASHED_PROFILES_FILE", tmp_path / "p.json")
    captured = {}

    def fake_provider(cfg, system_prompt, prompt):
        captured["sys"] = system_prompt
        return "ok"

    # Intercept the assembled system prompt by stubbing the provider dispatch.
    monkeypatch.setattr(banshee_ai, "_dispatch_provider", fake_provider, raising=False)
    banshee_ai.call_ai({"type": "gemini", "key": "x", "model": "m"},
                       "hello", unleashed=True, surface="nexus")
    assert captured["sys"].endswith(banshee_ai._EXTERNAL_CONTENT_GUARD)


def test_smc_system_prompt_reads_file_each_call(tmp_path, monkeypatch):
    # Unrelated to the deleted _apply_unleashed_override: preserved from the prior
    # version of this file since _smc_system_prompt's file-reload behavior is still
    # live code with no other coverage.
    monkeypatch.setattr(banshee_ai, "_PROMPTS_DIR", str(tmp_path))
    (tmp_path / "smc.txt").write_text("SMC V1")
    assert banshee_ai._smc_system_prompt() == "SMC V1"
    (tmp_path / "smc.txt").write_text("SMC V2")
    assert banshee_ai._smc_system_prompt() == "SMC V2"
