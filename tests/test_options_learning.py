"""Tests for the Spec 2 learning-engine additions to options_engine.py."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import options_engine as oe


# ── run_scenario ─────────────────────────────────────────────────────────────

def test_run_scenario_expired_worthless():
    spec = {'strike': 480.0, 'mid': 2.0, 'cash_backed': True, 'underlying': 'SPY'}
    r = oe.run_scenario(spec, terminal_price=490.0)
    assert r['outcome'] == 'expired_worthless'
    assert r['pnl'] == 200.0          # 2.0 * 100 * 1 contract
    assert r['net_cost_basis'] is None
    assert r['margin_required'] is None


def test_run_scenario_assigned_cash_backed():
    spec = {'strike': 480.0, 'mid': 2.0, 'cash_backed': True, 'underlying': 'SPY'}
    r = oe.run_scenario(spec, terminal_price=460.0)
    assert r['outcome'] == 'assigned'
    # gross_loss = (480-460)*100 = 2000; premium = 200; pnl = 200-2000 = -1800
    assert r['pnl'] == -1800.0
    assert r['net_cost_basis'] == 478.0   # 480 - 2.0
    assert r['margin_required'] is None


def test_run_scenario_margin_call_naked():
    spec = {'strike': 480.0, 'mid': 2.0, 'cash_backed': False, 'underlying': 'SPY'}
    r = oe.run_scenario(spec, terminal_price=400.0)
    assert r['outcome'] == 'margin_call'
    # margin_required = 480*100*0.20 = 9600
    assert r['margin_required'] == 9600.0
    # gross_loss = (480-400)*100 = 8000; premium = 200; pnl = 200-8000 = -7800
    assert r['pnl'] == -7800.0
    assert r['net_cost_basis'] is None


def test_run_scenario_multiple_contracts():
    spec = {'strike': 480.0, 'mid': 2.0, 'cash_backed': True, 'contracts': 5}
    r = oe.run_scenario(spec, terminal_price=490.0)
    assert r['contracts'] == 5
    assert r['premium_collected'] == 1000.0   # 2.0 * 100 * 5
    assert r['pnl'] == 1000.0
    assert r['cash_tied_up'] == 480.0 * 100 * 5


def test_run_scenario_expired_naked_cash_tied_up_is_margin():
    spec = {'strike': 480.0, 'mid': 2.0, 'cash_backed': False}
    r = oe.run_scenario(spec, terminal_price=490.0)  # expires OTM
    assert r['outcome'] == 'expired_worthless'
    assert r['cash_tied_up'] == 9600.0   # 480*100*0.20

def test_run_scenario_plain_is_string():
    spec = {'strike': 480.0, 'mid': 2.0, 'cash_backed': True}
    r = oe.run_scenario(spec, terminal_price=490.0)
    assert isinstance(r['plain'], str) and len(r['plain']) > 10


# ── danger_lever_scenarios ────────────────────────────────────────────────────

def test_danger_lever_naked_reckless_not_cash_backed():
    base = {'strike': 480.0, 'mid': 2.0, 'cash_backed': True, 'underlying': 'SPY', 'dte': 40}
    d = oe.danger_lever_scenarios(base, 'naked', spot=500.0)
    assert d['lever'] == 'naked'
    assert d['reckless_spec']['cash_backed'] is False
    assert d['safe_spec']['cash_backed'] is True


def test_danger_lever_oversize_reckless_contracts():
    base = {'strike': 480.0, 'mid': 2.0, 'cash_backed': True, 'underlying': 'SPY', 'dte': 40}
    d = oe.danger_lever_scenarios(base, 'oversize', spot=500.0)
    assert d['reckless_spec']['contracts'] == 5
    assert d['safe_spec'].get('contracts', 1) == 1


def test_danger_lever_high_delta_reckless_strike_near_spot():
    base = {'strike': 480.0, 'mid': 2.0, 'cash_backed': True, 'underlying': 'SPY', 'dte': 40}
    d = oe.danger_lever_scenarios(base, 'high_delta', spot=500.0)
    assert d['reckless_spec']['strike'] >= 490.0   # near ATM


def test_danger_lever_single_stock_crash_deeper():
    base = {'strike': 480.0, 'mid': 2.0, 'cash_backed': True, 'underlying': 'SPY', 'dte': 40}
    d = oe.danger_lever_scenarios(base, 'single_stock', spot=500.0)
    d_naked = oe.danger_lever_scenarios(base, 'naked', spot=500.0)
    # single-stock crash should be deeper (lower terminal price) than ETF crash
    assert d['crash_price'] < d_naked['crash_price']


def test_danger_lever_unknown_returns_none():
    base = {'strike': 480.0, 'mid': 2.0, 'cash_backed': True}
    assert oe.danger_lever_scenarios(base, 'unknown_lever', spot=500.0) is None


def test_danger_lever_calm_above_safe_strike():
    base = {'strike': 480.0, 'mid': 2.0, 'cash_backed': True, 'underlying': 'SPY', 'dte': 40}
    for lever in ('naked', 'oversize', 'high_delta', 'single_stock'):
        d = oe.danger_lever_scenarios(base, lever, spot=500.0)
        # calm scenario: option expires OTM for both safe AND reckless (safe_spec strike = 480)
        r_safe = oe.run_scenario(d['safe_spec'], d['calm_price'])
        assert r_safe['outcome'] == 'expired_worthless', f"lever={lever} calm should expire worthless"
