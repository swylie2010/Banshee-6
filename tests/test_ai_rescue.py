import pytest
import pandas as pd
from unittest.mock import patch, MagicMock, call


# ── Fixtures ────────────────────────────────────────────────────────────────

def _bad_df():
    """A DataFrame with non-standard column names that will fail fetch_stock's parsing."""
    return pd.DataFrame({
        "WEIRD_DATE": pd.to_datetime(["2024-01-01"]),
        "OPEN_PRICE":  [100.0],
        "HIGH_PRICE":  [101.0],
        "LOW_PRICE":   [99.0],
        "CLOSE_PRICE": [100.5],
        "VOL":         [1000],
    })


def _good_rename_map():
    """A valid AI response rename map — all values in the allow-list."""
    return {"WEIRD_DATE": "timestamp", "OPEN_PRICE": "open", "HIGH_PRICE": "high",
            "LOW_PRICE": "low", "CLOSE_PRICE": "close", "VOL": "volume"}


def _bad_rename_map():
    """An invalid AI response — 'exec_code' is not in the allow-list."""
    return {"WEIRD_DATE": "timestamp", "OPEN_PRICE": "exec_code",
            "HIGH_PRICE": "high", "LOW_PRICE": "low", "CLOSE_PRICE": "close", "VOL": "volume"}


# ── Tests ────────────────────────────────────────────────────────────────────

def test_rescue_skipped_when_disabled():
    """When allow_ai_data_rescue is False the rescue block must not call AI."""
    import micro_engine
    import banshee_ai

    with patch("micro_engine.fetch_yf_history", return_value=_bad_df()), \
         patch("shared_data.load_providers", return_value={"allow_ai_data_rescue": False}), \
         patch.object(banshee_ai, "call_ai") as mock_ai:

        df, err = micro_engine.fetch_stock("AAPL", "1d")

    mock_ai.assert_not_called()
    assert df.empty
    assert err is not None


def test_rescue_enabled_by_default():
    """allow_ai_data_rescue defaults to True when key is absent (no behavior change)."""
    import micro_engine
    import banshee_ai

    valid_map_json = str(_good_rename_map()).replace("'", '"')

    with patch("micro_engine.fetch_yf_history", return_value=_bad_df()), \
         patch("shared_data.load_providers", return_value={
             "AI_API": {"type": "openai", "key": "sk-test", "model": "gpt-4o"}
         }), \
         patch("core_state._log_error"), \
         patch.object(banshee_ai, "call_ai", return_value=valid_map_json):

        df, err = micro_engine.fetch_stock("AAPL", "1d")

    # Should succeed (no error) — default True means rescue fires
    assert err is None
    assert not df.empty


def test_rescue_logs_before_ai_call():
    """_log_error must be called BEFORE the AI call — not after."""
    import micro_engine
    import banshee_ai

    call_order = []

    def track_log(ctx, exc):
        call_order.append("log")

    def track_ai(cfg, prompt, **kwargs):
        call_order.append("ai")
        return str(_good_rename_map()).replace("'", '"')

    with patch("micro_engine.fetch_yf_history", return_value=_bad_df()), \
         patch("shared_data.load_providers", return_value={
             "AI_API": {"type": "openai", "key": "sk-test", "model": "gpt-4o"}
         }), \
         patch("core_state._log_error", side_effect=track_log), \
         patch.object(banshee_ai, "call_ai", side_effect=track_ai):

        micro_engine.fetch_stock("AAPL", "1d")

    assert "log" in call_order, "_log_error was never called"
    assert "ai" in call_order, "call_ai was never called"
    assert call_order.index("log") < call_order.index("ai"), \
        "_log_error must be called before call_ai"


def test_rescue_rejects_invalid_column_names():
    """AI returning a column name outside the allow-list must return an error, not apply the map."""
    import micro_engine
    import banshee_ai

    bad_map_json = str(_bad_rename_map()).replace("'", '"')

    with patch("micro_engine.fetch_yf_history", return_value=_bad_df()), \
         patch("shared_data.load_providers", return_value={
             "AI_API": {"type": "openai", "key": "sk-test", "model": "gpt-4o"}
         }), \
         patch("core_state._log_error"), \
         patch.object(banshee_ai, "call_ai", return_value=bad_map_json):

        df, err = micro_engine.fetch_stock("AAPL", "1d")

    assert df.empty
    assert err is not None
    assert "invalid column" in err.lower() or "exec_code" in err


def test_rescue_accepts_valid_column_names():
    """AI returning a valid rename map must produce a non-empty DataFrame."""
    import micro_engine
    import banshee_ai

    good_map_json = str(_good_rename_map()).replace("'", '"')

    with patch("micro_engine.fetch_yf_history", return_value=_bad_df()), \
         patch("shared_data.load_providers", return_value={
             "AI_API": {"type": "openai", "key": "sk-test", "model": "gpt-4o"}
         }), \
         patch("core_state._log_error"), \
         patch.object(banshee_ai, "call_ai", return_value=good_map_json):

        df, err = micro_engine.fetch_stock("AAPL", "1d")

    assert err is None
    assert not df.empty
    assert list(df.columns) == ["timestamp", "open", "high", "low", "close", "volume"]


def test_rescue_handles_ai_returning_no_json():
    """If AI response contains no JSON dict, rescue fails gracefully (no crash)."""
    import micro_engine
    import banshee_ai

    with patch("micro_engine.fetch_yf_history", return_value=_bad_df()), \
         patch("shared_data.load_providers", return_value={
             "AI_API": {"type": "openai", "key": "sk-test", "model": "gpt-4o"}
         }), \
         patch("core_state._log_error"), \
         patch.object(banshee_ai, "call_ai", return_value="Sorry, I cannot determine the column mapping."):

        df, err = micro_engine.fetch_stock("AAPL", "1d")

    # No JSON found — should return error, not crash
    assert err is not None
    assert df.empty


def test_rescue_handles_malformed_json():
    """If AI response contains malformed JSON (e.g. single quotes), rescue fails gracefully."""
    import micro_engine
    import banshee_ai

    # Python dict repr uses single quotes — json.loads rejects this
    single_quoted = str(_good_rename_map())  # e.g. "{'WEIRD_DATE': 'timestamp', ...}"

    with patch("micro_engine.fetch_yf_history", return_value=_bad_df()), \
         patch("shared_data.load_providers", return_value={
             "AI_API": {"type": "openai", "key": "sk-test", "model": "gpt-4o"}
         }), \
         patch("core_state._log_error"), \
         patch.object(banshee_ai, "call_ai", return_value=single_quoted):

        df, err = micro_engine.fetch_stock("AAPL", "1d")

    # Should fail gracefully — not crash, not apply partial rename
    assert err is not None
    assert df.empty
