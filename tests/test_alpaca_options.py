import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import alpaca_options as ao


# ── build_occ_symbol ──────────────────────────────────────────────────────────

def test_build_occ_standard_put():
    assert ao.build_occ_symbol("SPY", "2024-09-20", "put", 450.0) == "SPY240920P00450000"


def test_build_occ_standard_call():
    assert ao.build_occ_symbol("SPY", "2024-09-20", "call", 450.0) == "SPY240920C00450000"


def test_build_occ_fractional_strike():
    assert ao.build_occ_symbol("SPY", "2024-09-20", "put", 452.5) == "SPY240920P00452500"


def test_build_occ_four_letter_underlying():
    assert ao.build_occ_symbol("AAPL", "2026-08-21", "call", 200.0) == "AAPL260821C00200000"


def test_build_occ_high_strike():
    assert ao.build_occ_symbol("SPX", "2025-01-17", "put", 5000.0) == "SPX250117P05000000"


def test_build_occ_lowercases_type():
    # "PUT" and "put" both produce P
    assert ao.build_occ_symbol("SPY", "2024-09-20", "PUT", 450.0) == "SPY240920P00450000"


# ── _parse_occ_symbol ─────────────────────────────────────────────────────────

def test_parse_occ_roundtrip():
    sym = ao.build_occ_symbol("SPY", "2024-09-20", "put", 450.0)
    p = ao._parse_occ_symbol(sym)
    assert p["underlying"] == "SPY"
    assert p["expiry"] == "2024-09-20"
    assert p["option_type"] == "put"
    assert p["strike"] == 450.0


def test_parse_occ_call():
    p = ao._parse_occ_symbol("AAPL260821C00200000")
    assert p["underlying"] == "AAPL"
    assert p["option_type"] == "call"
    assert p["strike"] == 200.0


def test_parse_occ_fractional():
    p = ao._parse_occ_symbol("SPY240920P00452500")
    assert p["strike"] == 452.5


def test_parse_occ_invalid_returns_none():
    assert ao._parse_occ_symbol("NOT_AN_OCC_SYMBOL") is None
    assert ao._parse_occ_symbol("") is None
