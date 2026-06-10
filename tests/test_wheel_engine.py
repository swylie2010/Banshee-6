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


def _csp(strike=100, mid=2.00, dte=40):
    return {"type": "SOLD_CSP", "strike": strike, "expiry": "2026-07-17", "dte": dte, "mid": mid, "delta": -0.25}


def test_checkpoint_held_advances_to_expiry_decision():
    r = we.replay([_csp(), {"type": "CHECKPOINT_HELD", "leg": "csp"}])
    assert r["state"] == "CSP_OPEN"
    assert r["next_move"]["action"] == "RESOLVE_EXPIRY"
    assert r["pending_decision"]["kind"] == "expiry"
    assert r["pending_decision"]["needs"] == "expiry_price"


def test_close_csp_early_keeps_half_and_returns_to_cash():
    r = we.replay([_csp(mid=2.00), {"type": "CLOSED_EARLY", "leg": "csp", "est_close_cost": 100.0}])
    assert r["state"] == "CASH"
    assert r["totals"]["realized_pnl"] == 100.0   # 200 collected - 100 buyback
    assert r["totals"]["cycles_completed"] == 1
    assert r["totals"]["net_cost_basis"] is None


def test_close_early_defaults_buyback_to_half_premium():
    r = we.replay([_csp(mid=2.00), {"type": "CLOSED_EARLY", "leg": "csp"}])
    assert r["totals"]["realized_pnl"] == 100.0   # default est_close_cost = 50% of 200


def test_csp_expires_worthless_keeps_full_premium_and_loops():
    r = we.replay([
        _csp(mid=2.00), {"type": "CHECKPOINT_HELD", "leg": "csp"},
        {"type": "EXPIRED_WORTHLESS", "leg": "csp", "expiry_price": 105},
    ])
    assert r["state"] == "CASH"
    assert r["totals"]["realized_pnl"] == 200.0
    assert r["totals"]["cycles_completed"] == 1
    assert r["next_move"]["action"] == "SELL_CSP"


def test_csp_assigned_moves_to_shares_with_net_cost_basis():
    r = we.replay([
        _csp(strike=100, mid=2.00), {"type": "CHECKPOINT_HELD", "leg": "csp"},
        {"type": "ASSIGNED", "strike": 100, "expiry_price": 95},
    ])
    assert r["state"] == "SHARES"
    assert r["totals"]["shares_held"] == 100
    assert r["position"]["cost_basis"] == 100
    assert r["totals"]["net_cost_basis"] == 98.0   # 100 strike - 2.00/share premium
    assert r["next_move"]["action"] == "SELL_CC"
