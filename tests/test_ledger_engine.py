"""Tests for ledger_engine.py — the portfolio transaction ledger (money math)."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import ledger_engine as le


def _buy(sym, shares, price, date, opening=False):
    return {"type": "BUY", "sym": sym, "shares": shares, "price": price,
            "date": date, "opening": opening}

def _sell(sym, shares, price, date):
    return {"type": "SELL", "sym": sym, "shares": shares, "price": price, "date": date}


# ── replay: average cost across multiple buys ───────────────────
def test_avg_cost_two_buys():
    txns = [_buy("NVDA", 10, 120.0, "2024-01-15"),
            _buy("NVDA", 5, 140.0, "2024-03-02")]
    state = le.replay(txns)
    pos = state["positions"][0]
    assert pos["sym"] == "NVDA"
    assert pos["shares"] == pytest.approx(15.0)
    # (10*120 + 5*140) / 15 = 126.6667
    assert pos["avg_cost"] == pytest.approx(126.6667, abs=1e-3)
    assert pos["cost_basis"] == pytest.approx(1900.0, abs=1e-2)


# ── replay: partial sell realizes vs average ────────────────────
def test_partial_sell_realizes_vs_average():
    txns = [_buy("NVDA", 10, 120.0, "2024-01-15"),
            _buy("NVDA", 5, 140.0, "2024-03-02"),
            _sell("NVDA", 8, 160.0, "2024-06-10")]
    state = le.replay(txns)
    pos = state["positions"][0]
    assert pos["shares"] == pytest.approx(7.0)
    # avg cost unchanged by a sell
    assert pos["avg_cost"] == pytest.approx(126.6667, abs=1e-3)
    # realized = 8 * (160 - 126.6667) = 266.67
    assert state["realized_pnl"] == pytest.approx(266.67, abs=1e-2)


# ── replay: full sell zeroes the position ───────────────────────
def test_full_sell_drops_position():
    txns = [_buy("AAPL", 10, 150.0, "2024-01-01"),
            _sell("AAPL", 10, 170.0, "2024-02-01")]
    state = le.replay(txns)
    assert state["positions"] == []
    assert state["realized_pnl"] == pytest.approx(200.0, abs=1e-2)


# ── replay: re-buy after full sell starts fresh basis ───────────
def test_rebuy_after_full_sell_fresh_basis():
    txns = [_buy("AAPL", 10, 150.0, "2024-01-01"),
            _sell("AAPL", 10, 170.0, "2024-02-01"),
            _buy("AAPL", 4, 200.0, "2024-03-01")]
    state = le.replay(txns)
    pos = state["positions"][0]
    assert pos["shares"] == pytest.approx(4.0)
    assert pos["avg_cost"] == pytest.approx(200.0)
    assert pos["first_date"] == "2024-03-01"


# ── replay: realized loss ───────────────────────────────────────
def test_realized_loss():
    txns = [_buy("X", 10, 100.0, "2024-01-01"),
            _sell("X", 10, 80.0, "2024-02-01")]
    state = le.replay(txns)
    assert state["realized_pnl"] == pytest.approx(-200.0, abs=1e-2)


# ── replay: cash + deposits through interleaved txns ────────────
def test_cash_and_deposits_interleaved():
    txns = [
        {"type": "DEPOSIT", "amount": 5000.0, "date": "2024-01-01"},
        _buy("NVDA", 10, 120.0, "2024-01-15"),   # -1200 -> 3800
        _buy("NVDA", 5, 140.0, "2024-03-02"),    # -700  -> 3100
        _sell("NVDA", 8, 160.0, "2024-06-10"),   # +1280 -> 4380
        {"type": "WITHDRAW", "amount": 1000.0, "date": "2024-07-01"},  # -1000 -> 3380
    ]
    state = le.replay(txns)
    assert state["total_deposited"] == pytest.approx(5000.0, abs=1e-2)
    assert state["cash"] == pytest.approx(3380.0, abs=1e-2)


# ── replay: negative cash warns, does not raise ─────────────────
def test_negative_cash_warns_not_raises():
    txns = [_buy("NVDA", 10, 120.0, "2024-01-15")]  # cash 0 -> -1200
    state = le.replay(txns)
    assert any("negative" in w for w in state["warnings"])
    assert state["cash"] == pytest.approx(-1200.0, abs=1e-2)


# ── replay: opening BUY sets basis, does not debit cash ─────────
def test_opening_buy_no_cash_debit():
    txns = [_buy("NVDA", 10, 120.0, "2024-01-15", opening=True)]
    state = le.replay(txns)
    assert state["cash"] == pytest.approx(0.0)
    assert state["warnings"] == []
    assert state["positions"][0]["cost_basis"] == pytest.approx(1200.0, abs=1e-2)


# ── replay: price=null opening lot — counted in shares, no basis ─
def test_opening_null_price_no_basis():
    txns = [_buy("NVDA", 10, None, "2024-01-15", opening=True)]
    state = le.replay(txns)
    pos = state["positions"][0]
    assert pos["shares"] == pytest.approx(10.0)
    assert pos["cost_basis"] == pytest.approx(0.0)
    assert pos["avg_cost"] == pytest.approx(0.0)


# ── replay: oversell clamps to held + warns ─────────────────────
def test_oversell_clamps_and_warns():
    txns = [_buy("X", 5, 100.0, "2024-01-01"),
            _sell("X", 8, 120.0, "2024-02-01")]
    state = le.replay(txns)
    assert state["positions"] == []           # all 5 sold
    assert any("clamped" in w for w in state["warnings"])
    assert state["realized_pnl"] == pytest.approx(100.0, abs=1e-2)  # 5*(120-100)


# ── replay: sell with no position is ignored + warns ────────────
def test_sell_no_position_ignored():
    txns = [_sell("X", 5, 120.0, "2024-02-01")]
    state = le.replay(txns)
    assert state["positions"] == []
    assert state["realized_pnl"] == pytest.approx(0.0)
    assert any("no shares held" in w for w in state["warnings"])


# ── replay: empty / single / all-cash ───────────────────────────
def test_empty_ledger():
    state = le.replay([])
    assert state == {"positions": [], "cash": 0.0, "realized_pnl": 0.0,
                     "total_deposited": 0.0, "warnings": []}

def test_all_cash_ledger():
    txns = [{"type": "DEPOSIT", "amount": 1000.0, "date": "2024-01-01"}]
    state = le.replay(txns)
    assert state["positions"] == []
    assert state["cash"] == pytest.approx(1000.0)
    assert state["total_deposited"] == pytest.approx(1000.0)


# ── replay: as_of cuts off later transactions ───────────────────
def test_as_of_cutoff():
    txns = [_buy("NVDA", 10, 120.0, "2024-01-15"),
            _buy("NVDA", 5, 140.0, "2024-03-02")]
    state = le.replay(txns, as_of="2024-02-01")
    assert state["positions"][0]["shares"] == pytest.approx(10.0)
