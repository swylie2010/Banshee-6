# tests/test_provider_toggle.py
import pytest
import pandas as pd
from unittest.mock import patch


def _keys(overrides=None):
    """Base config: all providers disabled."""
    base = {
        "COINBASE":  {"enabled": False},
        "ALPACA_KEY": {"key": "", "enabled": False},
        "COINGECKO": {"enabled": False},
        "YFINANCE":  {"enabled": False},
        "CUSTOM_DATA": {"enabled": False, "base_url": "", "asset_class": "both"},
    }
    if overrides:
        for k, v in overrides.items():
            if isinstance(v, dict) and k in base:
                base[k].update(v)
            else:
                base[k] = v
    return base


# ── _is_enabled ──────────────────────────────────────────────────────────────

def test_yfinance_disabled_by_default():
    import data_providers
    with patch("data_providers._load_keys", return_value=_keys()):
        assert data_providers._is_enabled("yfinance", "equity") is False


def test_yfinance_enabled_when_flag_set():
    import data_providers
    with patch("data_providers._load_keys", return_value=_keys({"YFINANCE": {"enabled": True}})):
        assert data_providers._is_enabled("yfinance", "equity") is True
        assert data_providers._is_enabled("yfinance", "crypto") is True


def test_coinbase_disabled_by_default():
    import data_providers
    with patch("data_providers._load_keys", return_value=_keys()):
        assert data_providers._is_enabled("coinbase", "crypto") is False


def test_coinbase_only_serves_crypto():
    import data_providers
    with patch("data_providers._load_keys", return_value=_keys({"COINBASE": {"enabled": True}})):
        assert data_providers._is_enabled("coinbase", "crypto") is True
        assert data_providers._is_enabled("coinbase", "equity") is False


# ── _active_chain ─────────────────────────────────────────────────────────────

def test_chain_empty_when_all_disabled():
    import data_providers
    with patch("data_providers._load_keys", return_value=_keys()):
        assert data_providers._active_chain("spot", "crypto") == []
        assert data_providers._active_chain("spot", "equity") == []
        assert data_providers._active_chain("ohlcv", "crypto") == []


def test_chain_includes_yfinance_when_enabled():
    import data_providers
    with patch("data_providers._load_keys", return_value=_keys({"YFINANCE": {"enabled": True}})):
        assert "yfinance" in data_providers._active_chain("spot", "crypto")
        assert "yfinance" in data_providers._active_chain("spot", "equity")


def test_custom_provider_joins_correct_chain():
    import data_providers
    with patch("data_providers._load_keys", return_value=_keys({
        "CUSTOM_DATA": {"enabled": True, "base_url": "http://x", "asset_class": "crypto"}
    })):
        assert "custom" in data_providers._active_chain("spot", "crypto")
        assert "custom" not in data_providers._active_chain("spot", "equity")


# ── get_spot_price / fetch_ohlcv with no providers ───────────────────────────

def test_get_spot_price_returns_none_when_no_providers():
    import data_providers
    with patch("data_providers._load_keys", return_value=_keys()):
        result = data_providers.get_spot_price.__wrapped__("BTC/USD")
        assert result is None


def test_fetch_ohlcv_returns_empty_df_when_no_providers():
    import data_providers
    with patch("data_providers._load_keys", return_value=_keys()):
        result = data_providers._fetch_ohlcv_impl("AAPL", "1d", 10)
        assert result.empty


# ── has_capability ────────────────────────────────────────────────────────────

def test_options_chain_unavailable_when_yfinance_off():
    import data_providers
    with patch("data_providers._load_keys", return_value=_keys()):
        assert data_providers.has_capability("options_chain") is False


def test_options_chain_available_when_yfinance_on():
    import data_providers
    with patch("data_providers._load_keys", return_value=_keys({"YFINANCE": {"enabled": True}})):
        assert data_providers.has_capability("options_chain") is True


def test_fetch_chain_returns_error_dict_when_no_capability():
    import options_data
    with patch("data_providers._load_keys", return_value=_keys()):
        result = options_data.fetch_chain("AAPL")
    assert isinstance(result, dict)
    assert result.get("error") == "provider_unavailable"
    assert "user_message" in result


def test_fetch_earnings_date_returns_error_dict_when_no_capability():
    import options_data
    with patch("data_providers._load_keys", return_value=_keys()):
        result = options_data.fetch_earnings_date("AAPL")
    assert isinstance(result, dict)
    assert result.get("error") == "provider_unavailable"
    assert "user_message" in result
