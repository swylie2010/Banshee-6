"""Tests for spread engine: find_spread_candidate and grade_spread."""
from datetime import date, timedelta
from options_engine import find_spread_candidate, APPROVED_SPREAD_UNIVERSE

# ── Helpers ──────────────────────────────────────────────────────────────────

def _put(strike, dte, iv=0.30, mid=None, oi=600):
    if mid is None:
        mid = round(strike * iv * (dte / 365) ** 0.5 * 0.4, 2)
    expiry = (date.today() + timedelta(days=dte)).isoformat()
    return {"type": "put", "strike": strike, "dte": dte, "iv": iv,
            "mid": mid, "open_interest": oi, "expiry": expiry, "bid": mid - 0.05, "ask": mid + 0.05}

def _closes(n=260, start=400.0):
    import math, random
    random.seed(42)
    closes = [start]
    for _ in range(n - 1):
        closes.append(round(closes[-1] * math.exp(random.gauss(0, 0.01)), 2))
    return closes

def _sym(sym="SPY", spot=500.0, contracts=None, closes=None, earnings=None, failed=False):
    if contracts is None:
        # Two contracts: short leg (25-delta ~500 strike) + long leg ($5 below)
        contracts = [_put(500.0, 38), _put(495.0, 38, mid=1.20)]
    return {"sym": sym, "spot": spot, "contracts": contracts,
            "closes": closes or _closes(), "earnings_date": earnings, "failed": failed}

# ── find_spread_candidate tests ───────────────────────────────────────────────

def test_find_spread_candidate_returns_dict_on_valid_input():
    data = [_sym()]
    result = find_spread_candidate(data, "starter")
    assert result is not None
    assert result["underlying"] == "SPY"
    assert result["short_strike"] == 500.0
    assert result["long_strike"] == 495.0

def test_find_spread_candidate_bpr_formula():
    data = [_sym()]
    result = find_spread_candidate(data, "starter")
    expected_credit = round(_put(500.0, 38)["mid"] - 1.20, 4)
    expected_bpr = round((500.0 - 495.0 - expected_credit) * 100, 2)
    assert abs(result["bpr"] - expected_bpr) < 0.01

def test_find_spread_candidate_returns_none_when_bpr_too_large():
    # starter tier capital = $2,500 → max BPR = $125
    # A $5-wide spread on a $500 stock will have BPR > $125 normally
    # Force a case where BPR exceeds 5% of $2,500
    fat_credit = 0.10  # tiny credit → BPR ≈ $490
    contracts = [_put(500.0, 38, mid=0.15), _put(495.0, 38, mid=0.05)]
    data = [_sym(contracts=contracts)]
    result = find_spread_candidate(data, "starter")
    # BPR = (500 - 495 - 0.10) * 100 = $490 > $125 max for starter
    assert result is None

def test_find_spread_candidate_skips_earnings_within_14_days():
    expiry = (date.today() + timedelta(days=38)).isoformat()
    earnings = (date.today() + timedelta(days=30)).isoformat()  # within 14 days of expiry
    contracts = [_put(500.0, 38), _put(495.0, 38, mid=1.20)]
    for c in contracts:
        c["expiry"] = expiry
    data = [_sym(earnings=earnings, contracts=contracts)]
    result = find_spread_candidate(data, "institutional")
    assert result is None

def test_find_spread_candidate_skips_failed_symbols():
    data = [_sym(failed=True)]
    result = find_spread_candidate(data, "institutional")
    assert result is None

def test_approved_spread_universe_contains_etfs_and_stocks():
    assert "SPY" in APPROVED_SPREAD_UNIVERSE
    assert "NVDA" in APPROVED_SPREAD_UNIVERSE
    assert "FAKE" not in APPROVED_SPREAD_UNIVERSE
