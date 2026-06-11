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


# ── _dte ─────────────────────────────────────────────────────────────────────

def test_dte_same_day():
    assert ao._dte("2024-09-20", "2024-09-20") == 0


def test_dte_positive():
    assert ao._dte("2024-09-21", "2024-09-20") == 1


def test_dte_45_days():
    assert ao._dte("2024-11-04", "2024-09-20") == 45


# ── _safe_float ───────────────────────────────────────────────────────────────

def test_safe_float_numeric_string():
    assert ao._safe_float("123.45") == 123.45


def test_safe_float_none_returns_default_zero():
    assert ao._safe_float(None) == 0.0


def test_safe_float_none_with_none_default():
    assert ao._safe_float(None, None) is None


def test_safe_float_nan_returns_default():
    assert ao._safe_float(float('nan')) == 0.0


def test_safe_float_invalid_string_returns_default():
    assert ao._safe_float("not-a-number") == 0.0


# ── Exception classes ────────────────────────────────────────────────────────

def test_alpaca_order_rejected_error_reason():
    e = ao.AlpacaOrderRejectedError("insufficient buying power")
    assert e.reason == "insufficient buying power"
    assert "insufficient buying power" in str(e)


def test_alpaca_unavailable_error():
    e = ao.AlpacaUnavailableError("timeout")
    assert "timeout" in str(e)
