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


# ── I/O functions (mocked alpaca-py) ─────────────────────────────────────────
from unittest.mock import MagicMock, patch


def _make_snapshot(occ_sym, bid, ask, iv, delta):
    snap = MagicMock()
    snap.symbol = occ_sym
    snap.implied_volatility = iv
    snap.latest_quote = MagicMock(bid_price=bid, ask_price=ask)
    snap.greeks = MagicMock(delta=delta)
    return snap


def test_fetch_calls_chain_normalizes_snapshots():
    # Use future-dated OCC symbols (35 DTE from 2026-06-10 = 2026-07-15)
    fake_chain = {
        "SPY260715C00460000": _make_snapshot("SPY260715C00460000", 1.80, 2.20, 0.18, 0.28),
        "SPY260715C00470000": _make_snapshot("SPY260715C00470000", 0.90, 1.10, 0.15, 0.18),
    }
    with patch("alpaca_options._get_data_client") as mock_dc, \
         patch("alpaca_options._get_trading_client"):
        mock_dc.return_value.get_option_chain.return_value = fake_chain
        results = ao.fetch_calls_chain("SPY", min_dte=7, max_dte=55, spot=465.0)

    assert len(results) == 2
    r = results[0]
    assert r["type"] == "call"
    assert r["underlying"] == "SPY"
    assert r["spot"] == 465.0
    assert r["bid"] == 1.80
    assert r["ask"] == 2.20
    assert abs(r["mid"] - 2.0) < 0.01
    assert r["iv"] == 0.18
    assert r["delta"] == 0.28
    assert "occ_symbol" in r


def test_fetch_calls_chain_skips_unparseable_symbols():
    fake_chain = {
        "INVALID": _make_snapshot("INVALID", 1.0, 2.0, 0.20, 0.25),
        "SPY260715C00460000": _make_snapshot("SPY260715C00460000", 1.80, 2.20, 0.18, 0.28),
    }
    with patch("alpaca_options._get_data_client") as mock_dc:
        mock_dc.return_value.get_option_chain.return_value = fake_chain
        results = ao.fetch_calls_chain("SPY", min_dte=7, max_dte=55, spot=465.0)
    assert len(results) == 1


def test_place_option_order_returns_order_id():
    fake_order = MagicMock()
    fake_order.id = "order-uuid-123"
    fake_order.status.value = "accepted"
    fake_order.submitted_at.isoformat.return_value = "2026-06-10T10:00:00+00:00"
    with patch("alpaca_options._get_trading_client") as mock_tc:
        mock_tc.return_value.submit_order.return_value = fake_order
        result = ao.place_option_order("SPY260715P00450000", "sell", 1, 2.35)
    assert result["order_id"] == "order-uuid-123"
    assert result["status"] == "accepted"


def test_place_option_order_raises_rejected_on_api_error():
    from alpaca.common.exceptions import APIError
    with patch("alpaca_options._get_trading_client") as mock_tc:
        mock_tc.return_value.submit_order.side_effect = APIError("insufficient buying power")
        try:
            ao.place_option_order("SPY260715P00450000", "sell", 1, 2.35)
            assert False, "should have raised"
        except ao.AlpacaOrderRejectedError as e:
            assert "insufficient buying power" in e.reason


def test_get_order_returns_status_dict():
    fake_order = MagicMock()
    fake_order.status.value = "filled"
    fake_order.filled_avg_price = "2.40"
    fake_order.filled_at.isoformat.return_value = "2026-06-10T10:05:00+00:00"
    with patch("alpaca_options._get_trading_client") as mock_tc:
        mock_tc.return_value.get_order_by_id.return_value = fake_order
        r = ao.get_order("order-uuid-123")
    assert r["status"] == "filled"
    assert r["filled_avg_price"] == 2.40


def test_get_position_returns_dict_when_found():
    fake_pos = MagicMock()
    fake_pos.qty = "1"
    fake_pos.avg_entry_price = "2.40"
    fake_pos.unrealized_pl = "-12.50"
    fake_pos.current_price = "2.27"
    with patch("alpaca_options._get_trading_client") as mock_tc:
        mock_tc.return_value.get_open_position.return_value = fake_pos
        r = ao.get_position("SPY260715P00450000")
    assert r["qty"] == 1.0
    assert r["unrealized_pl"] == -12.50


def test_get_position_returns_none_when_not_found():
    from alpaca.common.exceptions import APIError
    with patch("alpaca_options._get_trading_client") as mock_tc:
        mock_tc.return_value.get_open_position.side_effect = APIError("position not found")
        assert ao.get_position("SPY260715P00450000") is None


def test_cancel_order_returns_true_on_success():
    with patch("alpaca_options._get_trading_client") as mock_tc:
        mock_tc.return_value.cancel_order_by_id.return_value = None
        assert ao.cancel_order("order-uuid-123") is True


def test_cancel_order_returns_false_on_exception():
    with patch("alpaca_options._get_trading_client") as mock_tc:
        mock_tc.return_value.cancel_order_by_id.side_effect = Exception("already filled")
        assert ao.cancel_order("order-uuid-123") is False


def test_poll_paper_wheels_returns_bool():
    """poll_paper_wheels must accept a wheels data dict and return a bool."""
    import alpaca_options
    data = {"wheels": []}   # empty — safe to call without network
    result = alpaca_options.poll_paper_wheels(data)
    assert isinstance(result, bool)
