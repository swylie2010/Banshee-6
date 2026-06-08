"""Tests for the symbol resolver in banshee_core.py (pure logic, stubbed prices)."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import banshee_core as bc


# Stub price book keyed by NORMALIZED symbol (the form _resolve_one looks up).
PRICES = {
    "NVDA":    208.64,   # valid equity
    "BRK-B":   477.0,    # valid (dash form); BRK.B / BRK.b do NOT price
    "BTC":     28.03,    # bare BTC resolves to a $28 stock (the trap)
    "BTC-USD": 63000.0,  # the crypto pair (normalized from BTC/USD)
}
def _stub_price(sym):
    return PRICES.get(sym)


def test_valid_equity_resolves_no_suggestion():
    r = bc._resolve_one("NVDA", _stub_price)
    assert r["resolved"] is True
    assert r["price"] == 208.64
    assert r["suggestion"] is None and r["reason"] is None


def test_dotted_class_share_unresolved_suggests_dash():
    r = bc._resolve_one("BRK.b", _stub_price)
    assert r["resolved"] is False
    assert r["suggestion"] == "BRK-B"
    assert r["reason"] == "unresolved"


def test_crypto_pair_form_resolves():
    r = bc._resolve_one("BTC/USD", _stub_price)   # normalized -> BTC-USD
    assert r["resolved"] is True
    assert r["normalized"] == "BTC-USD"
    assert r["suggestion"] is None


def test_bare_crypto_ticker_resolves_but_flags_ambiguity():
    # bare BTC prices as a $28 stock, but BTC/USD also prices -> suggest the coin
    r = bc._resolve_one("BTC", _stub_price)
    assert r["resolved"] is True
    assert r["price"] == 28.03
    assert r["suggestion"] == "BTC/USD"
    assert r["reason"] == "crypto_ambiguity"


def test_genuinely_unknown_no_suggestion():
    r = bc._resolve_one("ZZZZ", _stub_price)
    assert r["resolved"] is False
    assert r["suggestion"] is None and r["reason"] is None


def test_empty_symbol():
    r = bc._resolve_one("", _stub_price)
    assert r["resolved"] is False
    assert r["normalized"] is None


def test_norm_symbol_pair_to_dash():
    assert bc._norm_symbol("btc/usd") == "BTC-USD"
    assert bc._norm_symbol("  nvda ") == "NVDA"
