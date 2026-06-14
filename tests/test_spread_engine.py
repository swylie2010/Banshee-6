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

def _sym(sym="SPY", spot=25.0, contracts=None, closes=None, earnings=None, failed=False):
    if contracts is None:
        # Two contracts: short leg (25 strike) + long leg ($5 below = 20 strike)
        # Spot=25, strike=25 (ATM). Width=$5 → max loss=$500. That's huge for a $25 stock.
        # Max BPR for starter = $125. So max_loss = $125.
        # So width - net_credit = 1.25 → net_credit = width - 1.25 = 5 - 1.25 = 3.75
        # For a $25 strike with 38 DTE and 30% IV, ATM put premium ≈ $0.50-$1.00
        # OTM put (5 points below, at 20) would be maybe $0.10-$0.20
        # So net_credit = $0.75 - $0.20 = $0.55, which gives max_loss = (5 - 0.55)*100 = $445. Still too high.
        # Actually, the math doesn't work out. $5 width * 100 = $500 max loss. We need net_credit >= $3.75.
        # But realistic premiums can't be that high. So let me use a lower stock price or smaller width.
        # Actually, looking back at the code: bpr = (width - net_credit) * 100
        # width is in dollars (points), not cents. So width=5 means $5 per share, or $500 per contract.
        # So if width = 5 points and we need bpr <= 125, then (5 - net_credit) * 100 <= 125
        # Solving: net_credit >= 5 - 1.25 = 3.75 points = $375 per contract
        # For a $25 option,that's 3.75/25 = 15% of the strike, which is unrealistic for 38 DTE.
        # So the only option is to pick a smaller width. The code uses SPREAD_WIDTH = 5.0,
        # so I can't change it without modifying the constant.
        # Actually wait, let me re-read the BPR calculation. Line 519:
        # bpr = round((width - net_credit) * 100, 2)
        # So width = strike - long_strike = 25 - 20 = 5
        # net_credit = short_mid - long_mid
        # bpr = (5 - net_credit) * 100
        # If short_mid = 5.0 and long_mid = 1.25, then net_credit = 3.75, bpr = (5 - 3.75) * 100 = 125
        # But short_mid = 5.0 on a $25 strike is way too high (20% of strike).
        # OK, I think the test data just needs to use a realistic stock. Let me use a higher-priced stock
        # like $500, but then adjust the width to be smaller, or use a much higher capital tier.
        # Actually, let me just use a capital tier that can handle it. Let me check what's needed:
        # For a $5 wide spread with net_credit $0.50: max_loss = (5 - 0.50) * 100 = $450
        # To fit within 5% of account: account >= 450 / 0.05 = $9,000
        # Closest tier is "building" = $27,500, max_bpr = $1,375. That should work.
        # So I'll leave SPREAD_WIDTH = 5.0, use strikes 25/20, net_credit ~0.50-1.00,
        # and just use the "building" tier in the test.
        # Actually simpler: just use realistic premiums. For $25 strike with 30% IV, 38 DTE, OTM puts:
        # 25 strike (ATM): ~$1.00
        # 20 strike (OTM, 5 points down): ~$0.25
        # Net credit = $1.00 - $0.25 = $0.75, max_loss = (5 - 0.75) * 100 = $425
        # Still too high for "starter" ($125). Need "building" tier.
        contracts = [_put(25.0, 38, mid=1.00), _put(20.0, 38, mid=0.25)]
    return {"sym": sym, "spot": spot, "contracts": contracts,
            "closes": closes or _closes(start=25.0), "earnings_date": earnings, "failed": failed}

# ── find_spread_candidate tests ───────────────────────────────────────────────

def test_find_spread_candidate_returns_dict_on_valid_input():
    data = [_sym()]
    result = find_spread_candidate(data, "building")
    assert result is not None
    assert result["underlying"] == "SPY"
    assert result["short_strike"] == 25.0
    assert result["long_strike"] == 20.0

def test_find_spread_candidate_bpr_formula():
    data = [_sym()]
    result = find_spread_candidate(data, "building")
    expected_credit = round(1.00 - 0.25, 4)  # short_mid - long_mid from _sym() defaults
    expected_bpr = round((5.0 - expected_credit) * 100, 2)  # (width - net_credit) * 100, width=$5
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


# ── grade_spread tests ────────────────────────────────────────────────────────

from options_engine import grade_spread

def _spec(underlying="SPY", short_strike=500.0, long_strike=495.0,
          net_credit=1.50, dte=38, tier="building"):
    expiration = (date.today() + timedelta(days=dte)).isoformat()
    return {"underlying": underlying, "short_strike": short_strike,
            "long_strike": long_strike, "net_credit": net_credit,
            "expiration": expiration, "tier": tier}

def _ctx(spot=510.0, ivr=45.0, short_delta=0.25, short_oi=800,
         long_oi=700, earnings_date=None):
    return {"spot": spot, "ivr": ivr, "short_delta": short_delta,
            "short_oi": short_oi, "long_oi": long_oi,
            "earnings_date": earnings_date}

def test_grade_spread_returns_8_rules():
    rules = grade_spread(_spec(), _ctx())
    assert len(rules) == 8

def test_grade_spread_all_pass_on_clean_input():
    rules = grade_spread(_spec(), _ctx())
    assert all(r["passed"] for r in rules)

def test_grade_spread_fails_unapproved_underlying():
    rules = grade_spread(_spec(underlying="FAKE"), _ctx())
    underlying_rule = next(r for r in rules if r["key"] == "underlying")
    assert underlying_rule["passed"] is False

def test_grade_spread_fails_earnings_within_14_days():
    expiry = (date.today() + timedelta(days=38)).isoformat()
    earn = (date.today() + timedelta(days=30)).isoformat()
    spec = _spec()
    spec["expiration"] = expiry
    rules = grade_spread(spec, _ctx(earnings_date=earn))
    earn_rule = next(r for r in rules if r["key"] == "earnings")
    assert earn_rule["passed"] is False

def test_grade_spread_fails_bpr_exceeds_5pct():
    # building tier = $27,500 → max BPR = $1,375
    # $50 wide, $0.10 credit → BPR = (50 - 0.10) * 100 = $4,990 > $1,375
    # Force by using tiny credit on $50-wide spread
    spec = _spec(short_strike=550.0, long_strike=500.0, net_credit=0.10, tier="starter")
    # starter = $2,500 → max BPR = $125
    # BPR = (50 - 0.10) * 100 = $4,990 > $125
    rules = grade_spread(spec, _ctx())
    size_rule = next(r for r in rules if r["key"] == "size")
    assert size_rule["passed"] is False

def test_grade_spread_rule_structure():
    rules = grade_spread(_spec(), _ctx())
    for r in rules:
        assert "key" in r
        assert "label" in r
        assert "passed" in r
        assert "reason" in r
