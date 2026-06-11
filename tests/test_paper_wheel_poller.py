import pytest
from unittest.mock import patch, MagicMock
import banshee_core as bc
import alpaca_options


def _wheel_with_pending_order(order_id="ord-1", option_type="SOLD_CSP"):
    return {
        "id": "w1", "underlying": "SPY",
        "events": [{"type": option_type, "strike": 450.0, "expiry": "2026-08-15",
                    "dte": 45, "mid": 2.35, "delta": -0.25,
                    "alpaca_order_id": order_id, "fill_price": None}],
        "needs_attention": False, "attention_reason": None,
        "live": None, "last_polled": None,
    }


def _wheel_with_filled_order(order_id="ord-1"):
    return {
        "id": "w1", "underlying": "SPY",
        "events": [{"type": "SOLD_CSP", "strike": 450.0, "expiry": "2026-08-15",
                    "dte": 45, "mid": 2.35, "delta": -0.25,
                    "alpaca_order_id": order_id, "fill_price": 2.40}],
        "needs_attention": False, "attention_reason": None,
        "live": None, "last_polled": None,
    }


def test_poll_pending_fill_sets_fill_price_on_filled_order():
    wheel = _wheel_with_pending_order()
    fake_order = {"status": "filled", "filled_avg_price": 2.38, "filled_at": "2026-06-10T10:05:00"}
    with patch("banshee_core.alpaca_options.get_order", return_value=fake_order):
        changed = bc._poll_one_paper_wheel(wheel)
    assert changed is True
    assert wheel["events"][0]["fill_price"] == 2.38
    assert wheel["needs_attention"] is False


def test_poll_pending_fill_sets_attention_on_expired_order():
    wheel = _wheel_with_pending_order()
    fake_order = {"status": "expired"}
    with patch("banshee_core.alpaca_options.get_order", return_value=fake_order):
        changed = bc._poll_one_paper_wheel(wheel)
    assert changed is True
    assert wheel["needs_attention"] is True
    assert wheel["attention_reason"] == "order_pending"


def test_poll_pending_fill_no_change_on_alpaca_unavailable():
    wheel = _wheel_with_pending_order()
    with patch("banshee_core.alpaca_options.get_order",
               side_effect=alpaca_options.AlpacaUnavailableError("timeout")):
        changed = bc._poll_one_paper_wheel(wheel)
    assert changed is False
    assert wheel["events"][0]["fill_price"] is None


def test_poll_filled_order_updates_live_dict_when_position_exists():
    wheel = _wheel_with_filled_order()
    fake_pos = {"qty": 1.0, "avg_entry_price": 2.40,
                "unrealized_pl": -10.0, "current_price": 2.30}
    with patch("banshee_core.alpaca_options.get_position", return_value=fake_pos):
        changed = bc._poll_one_paper_wheel(wheel)
    assert changed is True
    assert wheel["live"]["unrealized_pl"] == -10.0
    assert wheel["live"]["current_price"] == 2.30
    assert "last_polled" in wheel["live"]


def test_poll_filled_order_sets_expired_attention_when_position_gone():
    wheel = _wheel_with_filled_order()
    with patch("banshee_core.alpaca_options.get_position", return_value=None):
        changed = bc._poll_one_paper_wheel(wheel)
    assert changed is True
    assert wheel["needs_attention"] is True
    assert wheel["attention_reason"] == "expired"


def test_poll_no_events_with_order_id_returns_false():
    wheel = {
        "id": "w1", "underlying": "SPY",
        "events": [{"type": "SOLD_CSP", "strike": 450.0, "expiry": "2026-08-15",
                    "dte": 45, "mid": 2.35}],  # no alpaca_order_id
        "needs_attention": False, "attention_reason": None, "live": None, "last_polled": None,
    }
    changed = bc._poll_one_paper_wheel(wheel)
    assert changed is False


def test_bg_poll_saves_when_changed():
    wheel = _wheel_with_pending_order()
    fake_order = {"status": "filled", "filled_avg_price": 2.38, "filled_at": "2026-06-10T10:05:00"}
    saved = {}
    def fake_save(d): saved.update(d)
    with patch.object(bc, "_load_paper_wheels", return_value={"wheels": [wheel]}), \
         patch.object(bc, "_save_paper_wheels", side_effect=fake_save), \
         patch("banshee_core.alpaca_options.get_order", return_value=fake_order):
        bc._bg_poll_paper_wheels()
    assert saved  # save was called
    assert saved["wheels"][0]["events"][0]["fill_price"] == 2.38


def test_bg_poll_does_not_crash_on_exception():
    with patch.object(bc, "_load_paper_wheels", side_effect=Exception("disk full")):
        bc._bg_poll_paper_wheels()  # must not raise
