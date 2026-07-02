import banshee_ai


def test_prompt_includes_bias_trigger_block():
    micro = {
        "symbol": "BTC/USD", "price": 60000, "verdict": "SELL SETUP", "edge": -3.0,
        "entry_quality": {"quality": "READY", "reasons": []},
        "bias": {"direction": "BEARISH", "conviction": "STRONG"},
        "trigger": {"direction": "SHORT", "actionable": True,
                    "extended_reading": {"extended": True, "in_trend": True,
                                         "momentum_note": "live", "mean_reversion_note": "bounce risk"}},
        "alignment": "aligned",
        "unleashed": True,
        "frame": "UNLEASHED MODE: ...",
    }
    text = banshee_ai.build_banshee_prompt({}, micro, include_macro=False)
    assert "BIAS" in text and "TRIGGER" in text and "ALIGNMENT" in text
    assert "BEARISH" in text and "SHORT" in text


def test_call_ai_appends_override_only_when_unleashed(monkeypatch, tmp_path):
    import core_state
    monkeypatch.setattr(core_state, "_UNLEASHED_PROFILES_FILE", tmp_path / "p.json")
    captured = {}

    def fake_provider(cfg, system_prompt, prompt):
        captured["sys"] = system_prompt
        return "ok"

    # Stub the actual provider dispatch so no network call happens, and intercept
    # the assembled system prompt via the _dispatch_provider seam.
    monkeypatch.setattr(banshee_ai, "_dispatch_provider", fake_provider, raising=False)

    banshee_ai.call_ai({"type": "gemini", "key": "x", "model": "m"},
                       "hello", system_prompt_override="BASE SYSTEM", unleashed=True)
    out_on = captured["sys"]

    banshee_ai.call_ai({"type": "gemini", "key": "x", "model": "m"},
                       "hello", system_prompt_override="BASE SYSTEM", unleashed=False)
    out_off = captured["sys"]

    assert "UNLEASHED OVERRIDE" in out_on
    assert out_off == "BASE SYSTEM" + banshee_ai._EXTERNAL_CONTENT_GUARD
