"""
test_banshee.py ? Banshee Pro Automated Test Suite
===================================================
Run from the Banshee_5 directory:
    python test_banshee.py

Tests are organised into sections:
  1. Import smoke tests  ? all modules load without error
  2. Risk engine math    ? position sizing arithmetic
  3. Knowledge graph     ? domino phases, asset safety, contradictions, regime
  4. Asset profiles      ? class resolution, weight lookups, KNOWN_ASSET_CLASSES
  5. Asymmetry scoring   ? edge case inputs

No external test framework required. Results print as PASS/FAIL with a
final summary.  Exit code 1 if any test fails (useful for CI/scripts).
"""

from __future__ import annotations

import io
import os
import sys
import traceback

# Force UTF-8 output on Windows
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# --- Tiny test harness --------------------------------------------------------

_results: list[tuple[str, bool, str]] = []   # (name, passed, detail)

def _test(name: str, fn):
    """Run fn(), catch any exception, record pass/fail."""
    try:
        fn()
        _results.append((name, True, ""))
        print(f"  PASS  {name}")
    except AssertionError as e:
        _results.append((name, False, str(e)))
        print(f"  FAIL  {name}")
        print(f"        {e}")
    except Exception as e:
        _results.append((name, False, f"{type(e).__name__}: {e}"))
        print(f"  FAIL  {name}")
        print(f"        {type(e).__name__}: {e}")
        traceback.print_exc()


# --- Section 1 ? Import smoke tests ------------------------------------------

print("\n--- 1. Import smoke tests ---------------------------------------------------")

def _import_risk_engine():
    import risk_engine
    assert hasattr(risk_engine, "calculate_execution_plan")

def _import_knowledge_graph():
    import knowledge_graph
    assert hasattr(knowledge_graph, "get_domino_state")
    assert hasattr(knowledge_graph, "detect_contradictions")
    assert hasattr(knowledge_graph, "get_regime_weights")
    assert hasattr(knowledge_graph, "calculate_asymmetry_score")

def _import_asset_profiles():
    import asset_profiles
    assert hasattr(asset_profiles, "get_effective_profile")
    assert hasattr(asset_profiles, "KNOWN_ASSET_CLASSES")

def _import_shared_data():
    import shared_data  # noqa: F401 ? just checking import works

def _import_banshee_ai():
    import banshee_ai  # noqa: F401

def _import_strategy_lab():
    # strategy_lab imports streamlit ? that is fine headlessly
    import strategy_lab
    assert hasattr(strategy_lab, "_run_mtf_backtest")
    assert hasattr(strategy_lab, "_save_strategy")

def _import_micro_engine():
    from micro_engine import add_all_indicators, score_timeframe, compute_verdict
    assert callable(add_all_indicators)
    assert callable(score_timeframe)
    assert callable(compute_verdict)

_test("risk_engine imports",      _import_risk_engine)
_test("knowledge_graph imports",  _import_knowledge_graph)
_test("asset_profiles imports",   _import_asset_profiles)
_test("shared_data imports",      _import_shared_data)
_test("banshee_ai imports",       _import_banshee_ai)
_test("strategy_lab imports",     _import_strategy_lab)
_test("micro_engine imports",     _import_micro_engine)


# --- Section 2 ? Risk engine math ---------------------------------------------

print("\n-- 2. Risk engine math --------------------------------------------------")

from risk_engine import calculate_execution_plan

def _risk_basic_long():
    """$10k account, 1% risk, entry $100, stop $95 -> exactly 20 units, $2k value."""
    r = calculate_execution_plan(10_000, 1.0, 100.0, 95.0)
    assert "error" not in r, r.get("error")
    assert r["is_long"] is True
    assert abs(r["position_size"] - 20.0) < 0.0001, f"got {r['position_size']}"
    assert abs(r["position_value"] - 2000.0) < 0.01
    assert abs(r["max_risk_dollars"] - 100.0) < 0.0001

def _risk_basic_short():
    """$5k account, 2% risk, entry $50, stop $55 -> short (entry < stop inverted)."""
    r = calculate_execution_plan(5_000, 2.0, 50.0, 55.0)
    assert "error" not in r, r.get("error")
    assert r["is_long"] is False, "Expected short trade"
    assert abs(r["max_risk_dollars"] - 100.0) < 0.0001
    assert abs(r["position_size"] - 20.0) < 0.0001

def _risk_r_targets_long():
    """1R target must be exactly at entry + stop_distance."""
    r = calculate_execution_plan(10_000, 1.0, 100.0, 98.0)  # 2-point stop
    targets = {t["r_multiple"]: t["price"] for t in r["targets"]}
    assert abs(targets[1] - 102.0) < 0.0001, f"1R={targets[1]}"
    assert abs(targets[2] - 104.0) < 0.0001, f"2R={targets[2]}"
    assert abs(targets[3] - 106.0) < 0.0001, f"3R={targets[3]}"

def _risk_r_targets_short():
    """For a short, 1R target is below entry."""
    r = calculate_execution_plan(10_000, 1.0, 100.0, 102.0)  # stop above = short
    targets = {t["r_multiple"]: t["price"] for t in r["targets"]}
    assert abs(targets[1] - 98.0) < 0.0001, f"1R={targets[1]}"
    assert abs(targets[2] - 96.0) < 0.0001, f"2R={targets[2]}"

def _risk_leverage_table():
    """Capital efficiency table must include 1x through 100x."""
    r = calculate_execution_plan(10_000, 1.0, 100.0, 95.0)
    leverages = [row["leverage"] for row in r["capital_efficiency"]]
    for expected in [1, 2, 5, 10, 20, 50, 100]:
        assert expected in leverages, f"Missing leverage {expected}x"

def _risk_invalid_inputs():
    """Zero / equal entry+stop should return an error dict, not raise."""
    r1 = calculate_execution_plan(10_000, 1.0, 0, 95.0)
    assert "error" in r1, "Expected error for zero entry"
    r2 = calculate_execution_plan(10_000, 1.0, 100.0, 100.0)
    assert "error" in r2, "Expected error when entry == stop"

_test("risk ? basic long",           _risk_basic_long)
_test("risk ? basic short",          _risk_basic_short)
_test("risk ? R-target long",        _risk_r_targets_long)
_test("risk ? R-target short",       _risk_r_targets_short)
_test("risk ? leverage table",       _risk_leverage_table)
_test("risk ? invalid inputs",       _risk_invalid_inputs)


# --- Section 3 ? Knowledge graph ---------------------------------------------

print("\n-- 3. Knowledge graph ---------------------------------------------------")

from knowledge_graph import (
    get_domino_state, classify_asset, evaluate_asset_safety,
    identify_micro_setup, detect_contradictions, get_regime_weights,
)

# -- Domino state --------------------------------------------------------------

def _domino_phase_0():
    sensors = {}  # all falsy = all clear
    r = get_domino_state(sensors)
    assert r["phase"] == 0
    assert r["state_str"] == "ALL CLEAR"

def _domino_phase_1_dxy():
    sensors = {"dxy": {"warning": True}}
    r = get_domino_state(sensors)
    assert r["phase"] == 1
    assert r["state_str"] == "CAUTION"

def _domino_phase_2():
    sensors = {
        "curve":  {"warning": True},
        "credit": {"warning": True},
        "vix":    {"warning": True},
    }
    r = get_domino_state(sensors)
    assert r["phase"] == 2
    assert r["state_str"] == "CRACK DETECTED"

def _domino_phase_3():
    sensors = {
        "curve":     {"warning": True},
        "credit":    {"warning": True},
        "liquidity": {"warning": True},
        "btc":       {"warning": True},
        "vix":       {"warning": True},
    }
    r = get_domino_state(sensors)
    assert r["phase"] == 3
    assert r["state_str"] == "CRACK DETECTED"

_test("domino phase 0 ? ALL CLEAR",    _domino_phase_0)
_test("domino phase 1 ? CAUTION/DXY",  _domino_phase_1_dxy)
_test("domino phase 2 ? CRACK credit", _domino_phase_2)
_test("domino phase 3 ? CRACK full",   _domino_phase_3)

# -- Asset classification -------------------------------------------------------

def _classify_known_crypto():
    assert classify_asset("BTC/USD") == "High-Beta"
    assert classify_asset("ETH/USD") == "High-Beta"
    assert classify_asset("SOL/USD") == "High-Beta"

def _classify_equities():
    assert classify_asset("SPY") == "Risk-On"
    assert classify_asset("NVDA") == "High-Beta"

def _classify_defensive():
    assert classify_asset("GLD") == "Defensive"
    assert classify_asset("PAXG") == "Defensive"
    assert classify_asset("TLT") == "Defensive"

def _classify_cash():
    assert classify_asset("USDC") == "Cash-Equivalent"
    assert classify_asset("USDT") == "Cash-Equivalent"

def _classify_unknown_crypto():
    # Unknown crypto pairs should fall back to High-Beta
    result = classify_asset("HYPE/USD")
    assert result == "High-Beta", f"Expected High-Beta for unmapped crypto, got {result}"

_test("classify ? crypto high-beta",  _classify_known_crypto)
_test("classify ? equities",          _classify_equities)
_test("classify ? defensive",         _classify_defensive)
_test("classify ? cash",              _classify_cash)
_test("classify ? unknown crypto",    _classify_unknown_crypto)

# -- Asset safety --------------------------------------------------------------

def _safety_clear_market():
    r = evaluate_asset_safety("BTC/USD", domino_phase=0)
    assert r["is_hostile"] is False

def _safety_phase2_btc_hostile():
    r = evaluate_asset_safety("BTC/USD", domino_phase=2)
    assert r["is_hostile"] is True, "BTC should be hostile in phase 2"

def _safety_phase3_spy_hostile():
    r = evaluate_asset_safety("SPY", domino_phase=3)
    assert r["is_hostile"] is True, "SPY (Risk-On) should be hostile in phase 3"

def _safety_phase3_gld_ok():
    r = evaluate_asset_safety("GLD", domino_phase=3)
    assert r["is_hostile"] is False, "Gold should be permitted in phase 3"

def _safety_phase2_spy_not_hostile():
    """Phase 2 penalises High-Beta but not Risk-On."""
    r = evaluate_asset_safety("SPY", domino_phase=2)
    assert r["is_hostile"] is False, "SPY (Risk-On) should still be permitted in phase 2"

_test("safety ? phase 0, BTC ok",     _safety_clear_market)
_test("safety ? phase 2, BTC hostile",_safety_phase2_btc_hostile)
_test("safety ? phase 3, SPY hostile",_safety_phase3_spy_hostile)
_test("safety ? phase 3, GLD ok",     _safety_phase3_gld_ok)
_test("safety ? phase 2, SPY ok",     _safety_phase2_spy_not_hostile)

# -- Contradiction patterns -----------------------------------------------------

def _make_sensors(**overrides):
    """Build a minimal sensor dict; all warnings False unless overridden."""
    s = {
        "vix":      {"warning": False, "value": 16.0},
        "curve":    {"warning": False},
        "credit":   {"warning": False},
        "liquidity":{"warning": False},
        "btc":      {"warning": False},
        "dxy":      {"warning": False},
        "skew":     {"warning": False, "status": "NORMAL"},
        "copper":   {"warning": False},
        "rotation": {"warning": False},
        "gold":     {"status": "NEUTRAL"},
        "xle":      {"status": "NEUTRAL"},
        "risk_score": 15,
    }
    for path, val in overrides.items():
        parts = path.split(".")
        node = s
        for p in parts[:-1]:
            node = node[p]
        node[parts[-1]] = val
    return s

def _contradiction_stealth_fear():
    s = _make_sensors(**{"skew.warning": True, "vix.warning": False})
    patterns = [p["name"] for p in detect_contradictions(s)]
    assert "STEALTH_FEAR_PATTERN" in patterns, f"Got: {patterns}"

def _contradiction_liquidity_trap():
    s = _make_sensors(**{"liquidity.warning": True, "vix.warning": False, "curve.warning": False})
    patterns = [p["name"] for p in detect_contradictions(s)]
    assert "LIQUIDITY_TRAP" in patterns, f"Got: {patterns}"

def _contradiction_credit_denial():
    s = _make_sensors(**{"credit.warning": True, "vix.warning": False, "btc.warning": False})
    patterns = [p["name"] for p in detect_contradictions(s)]
    assert "CREDIT_DENIAL" in patterns, f"Got: {patterns}"

def _contradiction_dxy_squeeze():
    s = _make_sensors(**{"dxy.warning": True, "liquidity.warning": True})
    patterns = [p["name"] for p in detect_contradictions(s)]
    assert "DXY_LIQUIDITY_SQUEEZE" in patterns, f"Got: {patterns}"

def _contradiction_canary():
    s = _make_sensors(**{"btc.warning": True})
    s["risk_score"] = 20
    patterns = [p["name"] for p in detect_contradictions(s)]
    assert "CANARY_DIVERGENCE" in patterns, f"Got: {patterns}"

def _contradiction_gold_skew():
    s = _make_sensors()
    s["gold"]["status"] = "FEAR BUYING"
    s["skew"]["status"] = "TAIL RISK"
    s["risk_score"] = 30
    patterns = [p["name"] for p in detect_contradictions(s)]
    assert "GOLD_SKEW_DIVERGENCE" in patterns, f"Got: {patterns}"

def _contradiction_copper_credit():
    s = _make_sensors(**{"copper.warning": True, "credit.warning": True})
    patterns = [p["name"] for p in detect_contradictions(s)]
    assert "COPPER_CREDIT_RECESSION_SIGNAL" in patterns, f"Got: {patterns}"

def _contradiction_none_when_calm():
    s = _make_sensors()   # all normal
    patterns = detect_contradictions(s)
    assert patterns == [], f"Expected no contradictions on clean sensors, got: {patterns}"

_test("contradiction ? STEALTH_FEAR_PATTERN",           _contradiction_stealth_fear)
_test("contradiction ? LIQUIDITY_TRAP",                  _contradiction_liquidity_trap)
_test("contradiction ? CREDIT_DENIAL",                   _contradiction_credit_denial)
_test("contradiction ? DXY_LIQUIDITY_SQUEEZE",           _contradiction_dxy_squeeze)
_test("contradiction ? CANARY_DIVERGENCE",               _contradiction_canary)
_test("contradiction ? GOLD_SKEW_DIVERGENCE",            _contradiction_gold_skew)
_test("contradiction ? COPPER_CREDIT_RECESSION_SIGNAL",  _contradiction_copper_credit)
_test("contradiction ? none on clean sensors",           _contradiction_none_when_calm)

# -- Regime weights -------------------------------------------------------------

def _regime_fear():
    s = _make_sensors(**{"vix.value": 28.0, "vix.warning": True})
    bucket, weights = get_regime_weights(s)
    assert bucket == "FEAR", f"Expected FEAR, got {bucket}"
    assert "supertrend" in weights
    assert weights["supertrend"] < 1.0, "Supertrend should be dampened in FEAR"

def _regime_caution():
    s = _make_sensors(**{"vix.value": 20.0})
    bucket, weights = get_regime_weights(s)
    assert bucket == "CAUTION", f"Expected CAUTION, got {bucket}"

def _regime_trending():
    s = _make_sensors(**{"vix.value": 12.0})
    s["risk_score"] = 10
    bucket, weights = get_regime_weights(s)
    assert bucket == "TRENDING", f"Expected TRENDING, got {bucket}"
    assert weights.get("supertrend", 1.0) > 1.0, "Supertrend should be boosted in TRENDING"

def _regime_neutral():
    s = _make_sensors(**{"vix.value": 16.0})
    s["risk_score"] = 15
    bucket, weights = get_regime_weights(s)
    assert bucket == "NEUTRAL", f"Expected NEUTRAL, got {bucket}"
    assert weights == {}, "NEUTRAL should have no weight overrides"

def _regime_contradiction_escalation():
    """NEUTRAL + STEALTH_FEAR_PATTERN should escalate to CAUTION."""
    s = _make_sensors(**{"vix.value": 16.0, "skew.warning": True, "vix.warning": False})
    s["risk_score"] = 15
    contradictions = detect_contradictions(s)
    s["contradictions"] = contradictions
    bucket, _ = get_regime_weights(s)
    assert bucket == "CAUTION", f"Expected CAUTION after escalation, got {bucket}"

_test("regime ? FEAR bucket",                    _regime_fear)
_test("regime ? CAUTION bucket",                 _regime_caution)
_test("regime ? TRENDING bucket",                _regime_trending)
_test("regime ? NEUTRAL bucket",                 _regime_neutral)
_test("regime ? contradiction escalation",       _regime_contradiction_escalation)

# -- Micro setup naming ---------------------------------------------------------

def _setup_exhaustion_reversion():
    ind = {"rsi": 30, "bb_pos": 0.10, "macd_bull": True, "obv_up": False, "price_over_ema50": False}
    result = identify_micro_setup(ind)
    assert "Exhaustion" in result, f"Got: {result}"

def _setup_trend_continuation():
    ind = {"rsi": 58, "bb_pos": 0.5, "macd_bull": True, "obv_up": True, "price_over_ema50": True}
    result = identify_micro_setup(ind)
    assert "Trend Continuation" in result, f"Got: {result}"

def _setup_empty_indicators():
    result = identify_micro_setup({})
    assert result == "No clear setup structure"

_test("setup ? exhaustion reversion",    _setup_exhaustion_reversion)
_test("setup ? trend continuation",      _setup_trend_continuation)
_test("setup ? empty indicators",        _setup_empty_indicators)


# --- Section 4 ? Asset profiles ----------------------------------------------

print("\n-- 4. Asset profiles ----------------------------------------------------")

from asset_profiles import (
    get_effective_profile, get_suggested_asset_class,
    get_weight, is_enabled, KNOWN_ASSET_CLASSES,
)

def _profile_btc_class():
    p = get_effective_profile("BTC/USD")
    assert p["asset_class"] == "crypto_btc", f"Got: {p['asset_class']}"

def _profile_sol_altcoin():
    p = get_effective_profile("SOL/USD")
    assert p["asset_class"] == "crypto_altcoin", f"Got: {p['asset_class']}"

def _profile_paxg_gold():
    """PAXG must be gold_proxy ? it lives in KNOWN_ASSET_CLASSES correctly."""
    p = get_effective_profile("PAXG/USD")
    assert p["asset_class"] == "gold_proxy", f"Got: {p['asset_class']}"

def _profile_spy_equity():
    p = get_effective_profile("SPY")
    assert p["asset_class"] == "equity", f"Got: {p['asset_class']}"

def _profile_unknown_defaults():
    """An unmapped symbol should fall back to default profile."""
    p = get_effective_profile("RANDOMXYZ")
    assert p["asset_class"] == "default", f"Got: {p['asset_class']}"

def _profile_altcoin_preset_weights():
    """crypto_altcoin preset should give MFI weight > RSI weight."""
    p = get_effective_profile("SOL/USD")
    mfi_w = get_weight(p, "mfi")
    rsi_w = get_weight(p, "rsi")
    assert mfi_w > rsi_w, f"MFI={mfi_w} should > RSI={rsi_w} for altcoins"

def _profile_altcoin_volume_gate():
    """crypto_altcoin should have volume_gate=True from preset."""
    p = get_effective_profile("SOL/USD")
    assert p["volume_gate"] is True, "Altcoin preset should enable volume gate"

def _profile_gold_ema_boost():
    """gold_proxy preset should boost EMA stack above default."""
    p_gold = get_effective_profile("PAXG/USD")
    from asset_profiles import DEFAULT_INDICATORS
    default_ema_w = DEFAULT_INDICATORS["ema_stack"]["weight"]
    gold_ema_w = get_weight(p_gold, "ema_stack")
    assert gold_ema_w > default_ema_w, f"EMA should be boosted for gold: {gold_ema_w} vs default {default_ema_w}"

def _profile_get_weight_disabled():
    """is_enabled False -> get_weight returns 0.0."""
    from asset_profiles import DEFAULT_PROFILE
    import copy
    p = copy.deepcopy(DEFAULT_PROFILE)
    p["indicators"]["rsi"]["enabled"] = False
    assert get_weight(p, "rsi") == 0.0

def _profile_known_asset_classes_spot_checks():
    """Spot-check a few entries in KNOWN_ASSET_CLASSES."""
    checks = {
        "BTC/USD":  "crypto_btc",
        "ETH/USDT": "crypto_altcoin",
        "SOL/USDT": "crypto_altcoin",
        "PAXG/USD": "gold_proxy",
        "GLD":      "gold_proxy",
        "SPY":      "equity",
        "NVDA":     "equity",
    }
    for sym, expected in checks.items():
        actual = KNOWN_ASSET_CLASSES.get(sym)
        assert actual == expected, f"{sym}: expected {expected}, got {actual}"

def _suggest_asset_class():
    assert get_suggested_asset_class("BTC/USD")  == "crypto_btc"
    assert get_suggested_asset_class("SOL/USDT") == "crypto_altcoin"
    assert get_suggested_asset_class("PAXG/USD") == "gold_proxy"
    assert get_suggested_asset_class("RANDOMXYZ") is None

_test("profile ? BTC/USD -> crypto_btc",           _profile_btc_class)
_test("profile ? SOL/USD -> crypto_altcoin",        _profile_sol_altcoin)
_test("profile ? PAXG/USD -> gold_proxy",           _profile_paxg_gold)
_test("profile ? SPY -> equity",                    _profile_spy_equity)
_test("profile ? unknown -> default",               _profile_unknown_defaults)
_test("profile ? altcoin MFI > RSI weight",        _profile_altcoin_preset_weights)
_test("profile ? altcoin volume gate on",          _profile_altcoin_volume_gate)
_test("profile ? gold EMA stack boosted",          _profile_gold_ema_boost)
_test("profile ? disabled indicator = weight 0",   _profile_get_weight_disabled)
_test("profile ? KNOWN_ASSET_CLASSES spot checks", _profile_known_asset_classes_spot_checks)
_test("profile ? get_suggested_asset_class",       _suggest_asset_class)


# --- Section 5 ? Asymmetry scoring -------------------------------------------

print("\n-- 5. Asymmetry scoring -------------------------------------------------")

from knowledge_graph import calculate_asymmetry_score

def _asymmetry_zero_on_neutral():
    """No special conditions = score 0, label Standard Probability."""
    micro = {
        "verdict": "NEUTRAL", "edge": 0,
        "asset_safety": {"is_hostile": False},
        "setup_name": "Choppy / Indecision Market",
        "funding_rate": {"available": False},
        "warnings": {},
    }
    r = calculate_asymmetry_score(micro, domino_phase=0)
    assert r["score"] == 0, f"Expected 0, got {r['score']}"
    assert r["label"] == "Standard Probability"

def _asymmetry_contrarian_long():
    """Bullish signal in hostile macro = +30."""
    micro = {
        "verdict": "BUY SETUP", "edge": 2,
        "asset_safety": {"is_hostile": True},
        "setup_name": "Trend Continuation",
        "funding_rate": {"available": False},
        "warnings": {},
    }
    r = calculate_asymmetry_score(micro, domino_phase=2)
    assert r["score"] >= 30

def _asymmetry_short_squeeze():
    """Bearish signal + extreme positive funding = +25 (long flush)."""
    micro = {
        "verdict": "SELL SETUP", "edge": -3,
        "asset_safety": {"is_hostile": False},
        "setup_name": "Choppy",
        "funding_rate": {"available": True, "rate_pct": 0.02},
        "warnings": {},
    }
    r = calculate_asymmetry_score(micro, domino_phase=0)
    assert r["score"] >= 25

def _asymmetry_capped_at_100():
    """All signals firing at once should not exceed 100."""
    micro = {
        "verdict": "STRONG BUY", "edge": 8,
        "asset_safety": {"is_hostile": True},
        "setup_name": "Exhaustion Reversion (Deep oversold bounce with momentum shift)",
        "funding_rate": {"available": True, "rate_pct": -0.05},
        "warnings": {"rsi_divergences": ["bullish div slow TF"]},
    }
    r = calculate_asymmetry_score(micro, domino_phase=2)
    assert r["score"] <= 100, f"Score {r['score']} exceeds cap"
    assert r["score"] >= 0

_test("asymmetry ? 0 on neutral",       _asymmetry_zero_on_neutral)
_test("asymmetry ? contrarian long",    _asymmetry_contrarian_long)
_test("asymmetry ? short squeeze",      _asymmetry_short_squeeze)
_test("asymmetry ? capped at 100",      _asymmetry_capped_at_100)


# ── Journal / Strategies wrappers ──────────────────────────────────────────

def _test_journal_trades_shape():
    import paper_trader
    trades = paper_trader.get_all_trades()
    assert isinstance(trades, list), "get_all_trades must return a list"
    stats = paper_trader.get_stats()
    assert isinstance(stats, dict), "get_stats must return a dict"
    assert "total" in stats, "stats must have 'total' key"

_test("journal trades shape", _test_journal_trades_shape)


def _test_strategies_file_readable():
    import json, os
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "strategies.json")
    if not os.path.exists(path):
        return  # no file yet — pass
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert isinstance(data, dict), "strategies.json must be a JSON object"

_test("strategies.json readable", _test_strategies_file_readable)


def _test_update_trade_levels_unknown_id():
    import paper_trader
    result = paper_trader.update_trade_levels(999999, 1.0, 2.0)
    assert result is False, "update_trade_levels should return False for unknown ID"

_test("update_trade_levels unknown id", _test_update_trade_levels_unknown_id)



# --- 6. generate_pine_script ------------------------------------------------

print("\n--- 6. generate_pine_script -------------------------------------------------")

def _pine_valid_result():
    import geometric_harmonic as gh
    import numpy as np
    import pandas as pd
    np.random.seed(42)
    n = 200
    p = 10000.0 * np.cumprod(1 + np.random.normal(0, 0.01, n))
    p[50]  = p[:50].min()  * 0.85
    p[150] = p[100:].max() * 1.15
    df = pd.DataFrame({
        "timestamp": pd.date_range("2021-01-01", periods=n, freq="D"),
        "open":  p, "high": p * 1.01, "low": p * 0.99,
        "close": p, "volume": np.ones(n) * 1000,
    })
    result = gh.run(df, multi_window=True)
    assert "error" not in result, f"run() failed: {result}"
    script = gh.generate_pine_script(result, symbol="TEST/USD")
    assert isinstance(script, str)
    assert script.startswith("//@version=5")
    assert "TEST/USD" in script
    assert str(result["sc_macro"]) in script
    assert "barstate.islast" in script
    n_calls = script.count("    draw_circle(")  # 4-space indent = call site, not definition
    assert n_calls == len(result["gh_circles"]), \
        f"expected {len(result['gh_circles'])} draw_circle calls, got {n_calls}"
    assert "polyline.new(" in script

def _pine_error_result():
    import geometric_harmonic as gh
    script = gh.generate_pine_script({"error": "No data"})
    assert script.startswith("//@version=5")
    assert 'runtime.error("No data")' in script

def _pine_no_symbol():
    import geometric_harmonic as gh
    import numpy as np, pandas as pd
    np.random.seed(7)
    n = 150
    p = 100.0 * np.cumprod(1 + np.random.normal(0, 0.01, n))
    df = pd.DataFrame({
        "timestamp": pd.date_range("2022-01-01", periods=n, freq="D"),
        "open": p, "high": p*1.01, "low": p*0.99,
        "close": p, "volume": np.ones(n)*1000,
    })
    result = gh.run(df, multi_window=True)
    script = gh.generate_pine_script(result)
    assert "UNKNOWN" in script

_test("pine: valid result -> correct Pine structure",  _pine_valid_result)
_test("pine: error result -> error Pine script",        _pine_error_result)
_test("pine: no symbol -> UNKNOWN in title",            _pine_no_symbol)


# --- Summary ------------------------------------------------------------------

total  = len(_results)
passed = sum(1 for _, ok, _ in _results if ok)
failed = total - passed

print(f"\n{'-' * 60}")
print(f"  {passed}/{total} tests passed", end="")
if failed:
    print(f"  ({failed} FAILED)")
    failed_names = [name for name, ok, _ in _results if not ok]
    for name in failed_names:
        print(f"    ? {name}")
else:
    print("  ? all green")
print(f"{'-' * 60}\n")

sys.exit(0 if failed == 0 else 1)
