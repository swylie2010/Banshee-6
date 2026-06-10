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


def test_grade_option_exposes_mid():
    """grade_option() return dict must include mid from the nearest contract."""
    spec = {'underlying': 'SPY', 'strike': 480.0, 'dte': 40, 'cash_backed': True}
    market_ctx = {
        'spot': 490.0,
        'contracts': [{'type': 'put', 'strike': 480.0, 'iv': 0.20, 'open_interest': 1500,
                        'expiry': '2026-08-01', 'dte': 40, 'mid': 2.50}],
        'closes': [],
    }
    result = oe.grade_option(spec, market_ctx)
    assert 'mid' in result
    assert result['mid'] == 2.50


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


# ── AI narrative functions ────────────────────────────────────────────────────

def _mock_cfg():
    return {'type': 'test', 'key': 'test', 'model': 'test'}


def test_summarize_run_returns_string_with_real_cfg_mocked(monkeypatch):
    import banshee_ai
    monkeypatch.setattr(banshee_ai, 'call_ai_briefing',
                        lambda cfg, prompt, **kw: "Option expired worthless. You kept the premium.")
    run = {'outcome': 'expired_worthless', 'pnl': 200.0, 'premium_collected': 200.0,
           'underlying': 'SPY', 'plain': 'Expired worthless.'}
    result = banshee_ai.summarize_run(_mock_cfg(), run)
    assert isinstance(result, str) and len(result) > 5


def test_summarize_run_graceful_degradation(monkeypatch):
    import banshee_ai
    monkeypatch.setattr(banshee_ai, 'call_ai_briefing', lambda *a, **kw: (_ for _ in ()).throw(Exception("AI down")))
    run = {'outcome': 'assigned', 'pnl': -1800.0, 'plain': 'Assigned.'}
    result = banshee_ai.summarize_run(_mock_cfg(), run)
    assert isinstance(result, str)
    assert 'narration unavailable' in result.lower() or 'assigned' in result.lower()


def test_compare_runs_graceful_degradation(monkeypatch):
    import banshee_ai
    monkeypatch.setattr(banshee_ai, 'call_ai_briefing', lambda *a, **kw: (_ for _ in ()).throw(Exception("AI down")))
    run_a = {'outcome': 'expired_worthless', 'pnl': 200.0, 'plain': 'A.'}
    run_b = {'outcome': 'assigned', 'pnl': -1800.0, 'plain': 'B.'}
    result = banshee_ai.compare_runs(_mock_cfg(), run_a, run_b)
    assert isinstance(result, str)
    assert 'narration unavailable' in result.lower() or 'run a' in result.lower()


def test_explain_why_not_graceful_degradation(monkeypatch):
    import banshee_ai
    monkeypatch.setattr(banshee_ai, 'call_ai_briefing', lambda *a, **kw: (_ for _ in ()).throw(Exception("AI down")))
    graded = {'failed': ['cash'], 'rules': [
        {'key': 'cash', 'label': 'Cash backing', 'passed': False,
         'risk_if_broken': 'Margin call in a crash.'}
    ]}
    run = {'outcome': 'margin_call', 'pnl': -7800.0, 'plain': 'Margin call.'}
    result = banshee_ai.explain_why_not(_mock_cfg(), graded, run)
    assert isinstance(result, str)
    assert 'narration unavailable' in result.lower() or 'cash' in result.lower()


def test_compare_runs_returns_string(monkeypatch):
    import banshee_ai
    monkeypatch.setattr(banshee_ai, 'call_ai_briefing', lambda cfg, p, **kw: "Run A kept more.")
    run_a = {'outcome': 'expired_worthless', 'pnl': 200.0, 'plain': 'A expired.'}
    run_b = {'outcome': 'assigned', 'pnl': -1800.0, 'plain': 'B assigned.'}
    result = banshee_ai.compare_runs(_mock_cfg(), run_a, run_b)
    assert isinstance(result, str) and len(result) > 5


def test_compare_runs_no_material_difference_flagged(monkeypatch):
    import banshee_ai
    captured = {}
    def fake_ai(cfg, prompt, **kw):
        captured['prompt'] = prompt
        return "No difference."
    monkeypatch.setattr(banshee_ai, 'call_ai_briefing', fake_ai)
    # Same outcome, same PNL
    run_a = {'outcome': 'expired_worthless', 'pnl': 200.0, 'plain': 'A.'}
    run_b = {'outcome': 'expired_worthless', 'pnl': 201.0, 'plain': 'B.'}
    banshee_ai.compare_runs(_mock_cfg(), run_a, run_b)
    assert 'no material difference' in captured['prompt'].lower() or 'same outcome' in captured['prompt'].lower()


def test_explain_why_not_returns_string(monkeypatch):
    import banshee_ai
    monkeypatch.setattr(banshee_ai, 'call_ai_briefing', lambda cfg, p, **kw: "Naked selling is dangerous.")
    graded = {'failed': ['cash'], 'rules': [
        {'key': 'cash', 'label': 'Cash backing', 'passed': False,
         'risk_if_broken': 'Margin call in a crash.'}
    ]}
    run = {'outcome': 'margin_call', 'pnl': -7800.0, 'plain': 'Margin call.'}
    result = banshee_ai.explain_why_not(_mock_cfg(), graded, run)
    assert isinstance(result, str) and len(result) > 5
