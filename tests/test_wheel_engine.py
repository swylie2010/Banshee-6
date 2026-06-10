import wheel_engine as we


def test_empty_log_starts_in_cash():
    r = we.replay([])
    assert r["state"] == "CASH"
    assert r["next_move"]["action"] == "SELL_CSP"
    assert r["position"] is None
    assert r["totals"] == {
        "premium_collected": 0.0, "net_cost_basis": None,
        "realized_pnl": 0.0, "cycles_completed": 0, "shares_held": 0,
    }


def test_sold_csp_opens_position_and_collects_premium():
    r = we.replay([
        {"type": "SOLD_CSP", "strike": 100, "expiry": "2026-07-17", "dte": 40, "mid": 2.00, "delta": -0.25},
    ])
    assert r["state"] == "CSP_OPEN"
    assert r["totals"]["premium_collected"] == 200.0
    assert r["position"]["leg"] == "csp"
    assert r["position"]["premium"] == 200.0
    assert r["next_move"]["action"] == "CHECKPOINT"
    assert r["pending_decision"]["kind"] == "checkpoint"
    assert r["pending_decision"]["est_close_cost"] == 100.0


def test_unknown_event_returns_error_state_not_raise():
    r = we.replay([{"type": "NONSENSE"}])
    assert r["state"] == "error"
    assert "NONSENSE" in r["error"]
