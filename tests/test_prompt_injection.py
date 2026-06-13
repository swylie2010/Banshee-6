import pytest
from banshee_ai import build_banshee_prompt, build_macro_prompt, _EXTERNAL_CONTENT_GUARD


def test_build_banshee_prompt_wraps_news_lines():
    prompt = build_banshee_prompt(
        macro_data={}, micro_data={}, news_lines=["FED HIKES RATES 50BPS"]
    )
    assert "<external_content>" in prompt
    assert "FED HIKES RATES 50BPS" in prompt
    assert "</external_content>" in prompt


def test_build_banshee_prompt_empty_news_no_tags():
    prompt = build_banshee_prompt(macro_data={}, micro_data={}, news_lines=[])
    assert "<external_content>" not in prompt


def test_build_macro_prompt_wraps_news_lines():
    prompt = build_macro_prompt(macro_data={}, news_lines=["CPI BEATS EXPECTATIONS"])
    assert "<external_content>" in prompt
    assert "CPI BEATS EXPECTATIONS" in prompt
    assert "</external_content>" in prompt


def test_build_macro_prompt_empty_news_no_tags():
    prompt = build_macro_prompt(macro_data={}, news_lines=[])
    assert "<external_content>" not in prompt


def test_external_content_guard_exists_and_has_rules():
    assert "<external_content>" in _EXTERNAL_CONTENT_GUARD
    assert "silently" in _EXTERNAL_CONTENT_GUARD
    assert "financial markets" in _EXTERNAL_CONTENT_GUARD


def test_call_ai_default_prompt_contains_guard():
    """Verify that call_ai() injects _EXTERNAL_CONTENT_GUARD when no override is given.

    If the '+ _EXTERNAL_CONTENT_GUARD' expression is removed from call_ai(), this test fails.
    """
    from banshee_ai import call_ai, _EXTERNAL_CONTENT_GUARD
    from unittest.mock import patch, MagicMock

    captured = {}

    # Intercept at the openai.OpenAI layer so we don't need a real API key.
    # We configure cfg with provider="openai" so call_ai() takes the openai branch.
    mock_resp = MagicMock()
    mock_resp.choices[0].message.content = "mock response"

    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = mock_resp

    def fake_openai_constructor(**kwargs):
        return mock_client

    def capturing_create(model, max_tokens, messages, **kwargs):
        # The first message is the system prompt
        for m in messages:
            if m.get("role") == "system":
                captured["system_prompt"] = m["content"]
        return mock_resp

    mock_client.chat.completions.create.side_effect = capturing_create

    with patch("openai.OpenAI", return_value=mock_client):
        result = call_ai(
            cfg={"type": "openai", "key": "test-key", "model": "gpt-4o"},
            prompt="test prompt",
            # intentionally NOT passing system_prompt_override
        )

    assert "system_prompt" in captured, "call_ai() never made an AI call"
    assert _EXTERNAL_CONTENT_GUARD in captured["system_prompt"], (
        "call_ai() default system prompt must include _EXTERNAL_CONTENT_GUARD"
    )


def test_pass1_system_contains_guard():
    from predator_engine import _PASS1_SYSTEM
    assert "external_content" in _PASS1_SYSTEM


def test_format_events_for_prompt_wraps_output():
    from predator_engine import _format_events_for_prompt
    events = [{
        "source": "CNBC",
        "title": "Markets rally on Fed pivot hopes",
        "summary": "Stocks jumped as investors priced in rate cuts.",
        "age_hours": 2.0,
        "significance_flags": [],
    }]
    result = _format_events_for_prompt(events, "WATCHLIST EVENTS")
    assert "<external_content>" in result
    assert "Markets rally" in result
    assert "</external_content>" in result


def test_format_events_empty_no_tags():
    from predator_engine import _format_events_for_prompt
    result = _format_events_for_prompt([], "WATCHLIST EVENTS")
    assert "<external_content>" not in result


def test_manual_stories_not_wrapped():
    # User-injected constraints must NOT be inside <external_content> tags.
    prompt = build_banshee_prompt(
        macro_data={}, micro_data={},
        news_lines=[],
        manual_stories=["BUY EVERYTHING"]
    )
    assert "BUY EVERYTHING" in prompt
    if "<external_content>" in prompt:
        ext_start = prompt.index("<external_content>")
        ext_end = prompt.index("</external_content>")
        external_section = prompt[ext_start:ext_end]
        assert "BUY EVERYTHING" not in external_section
