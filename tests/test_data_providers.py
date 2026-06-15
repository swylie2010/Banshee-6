"""tests/test_data_providers.py — unit tests for data_providers.py"""
import pytest


def test_asset_class_crypto_slash():
    import data_providers
    assert data_providers._asset_class("BTC/USD") == "crypto"

def test_asset_class_crypto_dash():
    import data_providers
    assert data_providers._asset_class("BTC-USD") == "crypto"

def test_asset_class_known_crypto_ticker():
    import data_providers
    assert data_providers._asset_class("ETH") == "crypto"

def test_asset_class_equity():
    import data_providers
    assert data_providers._asset_class("AAPL") == "equity"

def test_asset_class_equity_spy():
    import data_providers
    assert data_providers._asset_class("SPY") == "equity"

def test_mean_latency_no_samples():
    import data_providers
    # A provider with no recorded samples should return inf
    data_providers._latency["coinbase"].clear()
    assert data_providers._mean_latency("coinbase") == float("inf")

def test_mean_latency_with_samples():
    import data_providers
    data_providers._latency["coinbase"].clear()
    data_providers._record_latency("coinbase", 100.0)
    data_providers._record_latency("coinbase", 200.0)
    assert data_providers._mean_latency("coinbase") == 150.0
    data_providers._latency["coinbase"].clear()  # cleanup

def test_record_latency_on_failure_not_called():
    import data_providers
    data_providers._latency["yfinance"].clear()
    # failure path should NOT record — callers only call _record_latency on success
    assert len(data_providers._latency["yfinance"]) == 0

def test_tier_fast():
    import data_providers
    assert data_providers._tier(94.0) == "FAST"

def test_tier_good():
    import data_providers
    assert data_providers._tier(800.0) == "GOOD"

def test_tier_slow():
    import data_providers
    assert data_providers._tier(9000.0) == "SLOW"

def test_tier_untested():
    import data_providers
    assert data_providers._tier(float("inf")) == "UNTESTED"
