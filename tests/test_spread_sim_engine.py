"""Tests for the Spread Sim FSM (spread_sim_engine.replay)."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import spread_sim_engine


def _ev(event_type, **kwargs):
    return {"event_type": event_type, "timestamp": "2026-06-14T10:00:00", "data": kwargs}


def test_replay_empty_returns_idle():
    state = spread_sim_engine.replay([])
    assert state["status"] == "IDLE"
    assert state["short_strike"] is None


def test_replay_open_spread():
    events = [_ev("OPEN_SPREAD", short_strike=500.0, long_strike=495.0,
                  credit=1.50, underlying_price=510.0, expiration="2026-07-25")]
    state = spread_sim_engine.replay(events)
    assert state["status"] == "SPREAD_OPEN"
    assert state["short_strike"] == 500.0
    assert state["long_strike"] == 495.0
    assert state["credit"] == 1.50


def test_replay_close_records_pnl():
    events = [
        _ev("OPEN_SPREAD", short_strike=500.0, long_strike=495.0,
            credit=1.50, underlying_price=510.0, expiration="2026-07-25"),
        _ev("CLOSE_SPREAD", close_cost=0.75, realized_pnl=75.0),
    ]
    state = spread_sim_engine.replay(events)
    assert state["status"] == "CLOSED"
    assert state["realized_pnl"] == 75.0


def test_replay_expire_worthless():
    events = [
        _ev("OPEN_SPREAD", short_strike=500.0, long_strike=495.0,
            credit=1.50, underlying_price=510.0, expiration="2026-07-25"),
        _ev("EXPIRE_WORTHLESS", max_profit=150.0),
    ]
    state = spread_sim_engine.replay(events)
    assert state["status"] == "EXPIRED"
    assert state["realized_pnl"] == 150.0


def test_replay_price_update_triggers_at_risk():
    events = [
        _ev("OPEN_SPREAD", short_strike=500.0, long_strike=495.0,
            credit=1.50, underlying_price=510.0, expiration="2026-07-25"),
        _ev("PRICE_UPDATE", current_underlying_price=491.0),  # within 2% of 500
    ]
    state = spread_sim_engine.replay(events)
    assert state["status"] == "AT_RISK"
    assert state["current_price"] == 491.0


def test_replay_price_update_not_at_risk_when_safe():
    events = [
        _ev("OPEN_SPREAD", short_strike=500.0, long_strike=495.0,
            credit=1.50, underlying_price=510.0, expiration="2026-07-25"),
        _ev("PRICE_UPDATE", current_underlying_price=520.0),
    ]
    state = spread_sim_engine.replay(events)
    assert state["status"] == "SPREAD_OPEN"


def test_replay_roll_creates_new_spread():
    events = [
        _ev("OPEN_SPREAD", short_strike=500.0, long_strike=495.0,
            credit=1.50, underlying_price=510.0, expiration="2026-07-25"),
        _ev("PRICE_UPDATE", current_underlying_price=491.0),
        _ev("ROLL", new_short_strike=490.0, new_long_strike=485.0,
            new_expiration="2026-08-22", roll_net=-0.25),
    ]
    state = spread_sim_engine.replay(events)
    assert state["status"] == "SPREAD_OPEN"
    assert state["short_strike"] == 490.0


def test_replay_event_log_length():
    events = [
        _ev("OPEN_SPREAD", short_strike=500.0, long_strike=495.0,
            credit=1.50, underlying_price=510.0, expiration="2026-07-25"),
        _ev("CLOSE_SPREAD", close_cost=0.50, realized_pnl=100.0),
    ]
    state = spread_sim_engine.replay(events)
    assert len(state["events"]) == 2
