"""
options_engine.py — Banshee Options, Phase 1 "The Calm Room" (The Wheel).

PURE. No I/O, no network, NEVER imports yfinance (adapter pattern —
see feedback_data_source_agnostic). Consumes a normalized options-chain
contract supplied by the caller. Uses math.erf for the normal CDF so there
is no scipy dependency.
"""
import math

# ── Guardrail constants ─────────────────────────────────────────
DTE_MIN, DTE_MAX = 35, 45
DELTA_LOW, DELTA_HIGH = 0.20, 0.30
OI_MIN = 1000
IVR_MIN = 35
OPTIONS_RISK_FREE = 0.043   # ~3-month T-bill; FRED DGS3MO override optional later


def _norm_cdf(x):
    """Standard normal CDF via the error function (stdlib, no scipy)."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def put_delta(spot, strike, dte, iv, r=OPTIONS_RISK_FREE):
    """Black-Scholes put delta (negative). None on degenerate inputs."""
    try:
        T = dte / 365.0
        if spot <= 0 or strike <= 0 or T <= 0 or iv <= 0:
            return None
        d1 = (math.log(spot / strike) + (r + iv * iv / 2.0) * T) / (iv * math.sqrt(T))
        return -_norm_cdf(-d1)
    except (ValueError, ZeroDivisionError, TypeError):
        return None


def annualized_yield(mid, strike, dte):
    """Premium yield on collateral, annualized: mid * (365/dte) / strike."""
    if not mid or not strike or not dte or strike <= 0 or dte <= 0:
        return 0.0
    return mid * (365.0 / dte) / strike


def breakeven(strike, mid):
    """CSP breakeven = strike minus premium collected. None on missing inputs."""
    if strike is None or mid is None:
        return None
    return round(strike - mid, 2)


def realized_vol_series(closes, window=21):
    """Annualized rolling realized volatility of daily log returns."""
    rets = []
    for i in range(1, len(closes or [])):
        p0, p1 = closes[i - 1], closes[i]
        if p0 and p1 and p0 > 0 and p1 > 0:
            rets.append(math.log(p1 / p0))
    out = []
    for i in range(window, len(rets) + 1):
        w = rets[i - window:i]
        m = sum(w) / len(w)
        var = sum((x - m) ** 2 for x in w) / (len(w) - 1) if len(w) > 1 else 0.0
        out.append(math.sqrt(var) * math.sqrt(252))
    return out


def estimate_ivr(current_iv, realized_vols):
    """Approximate IV Rank: percentile (0-100) of current_iv within the
    trailing realized-vol band. None when inputs are unusable. Phase 1 proxy —
    flagged 'est.' everywhere; tightened with a real feed in Phase 3."""
    vals = [v for v in (realized_vols or []) if v is not None and v > 0]
    if current_iv is None or not vals:
        return None
    below = sum(1 for v in vals if v < current_iv)
    return round(100.0 * below / len(vals), 1)


def _eligible_from(u):
    """Yield candidate dicts for one underlying that pass the HARD guardrails."""
    spot = u.get("spot")
    rv = realized_vol_series(u.get("closes") or [])
    for c in u.get("contracts", []):
        if c.get("type") != "put":
            continue
        dte, iv = c.get("dte"), c.get("iv")
        strike, mid, oi = c.get("strike"), c.get("mid"), c.get("open_interest")
        if dte is None or not (DTE_MIN <= dte <= DTE_MAX):
            continue
        d = put_delta(spot, strike, dte, iv)
        if d is None or not (DELTA_LOW <= abs(d) <= DELTA_HIGH):
            continue
        if not oi or oi <= OI_MIN:
            continue
        if not mid or mid <= 0 or not strike or strike <= 0:
            continue
        yield {
            "underlying": u.get("sym"), "name": u.get("name", u.get("sym")),
            "strike": strike, "expiry": c.get("expiry"), "dte": dte,
            "mid": round(mid, 2), "delta": round(d, 3),
            "collateral": round(strike * 100, 2),
            "breakeven": breakeven(strike, mid),
            "prob_keep": round(1 - abs(d), 3),
            "annualized_yield": round(annualized_yield(mid, strike, dte), 4),
            "open_interest": int(oi),
            "ivr_estimate": estimate_ivr(iv, rv),
        }


def _guardrails(b):
    pk = round(b["prob_keep"] * 100)
    ivr = b["ivr_estimate"]
    return [
        {"key": "dte", "label": "Days to expiry", "value": f"{b['dte']} days", "passed": True,
         "plain": f"{b['dte']} days out — enough time for the clock to work in your favor."},
        {"key": "delta", "label": "Delta", "value": f"{abs(b['delta']):.2f}", "passed": True,
         "plain": f"Delta {abs(b['delta']):.2f} — about {pk}% chance it expires worthless."},
        {"key": "oi", "label": "Open interest", "value": f"{b['open_interest']:,}", "passed": True,
         "plain": f"Open interest {b['open_interest']:,} — easy to get in and out at a fair price."},
        {"key": "cash", "label": "Cash-secured", "value": f"${b['collateral']:,.0f}", "passed": True,
         "plain": "Fully cash-secured — no borrowing, ever."},
        {"key": "ivr", "label": "IV Rank (est.)",
         "value": (f"~{ivr:.0f} est." if ivr is not None else "n/a"),
         "passed": (ivr is None or ivr >= IVR_MIN),
         "plain": ("Premium is rich enough relative to recent calm to be worth the risk."
                   if (ivr is not None and ivr >= IVR_MIN)
                   else ("Not enough price history to estimate IV Rank — treat this as unknown."
                         if ivr is None
                         else "Premium looks thin right now (estimated) — normally the Wheel waits."))},
    ]


def _translation(b):
    premium = b["mid"] * 100
    pk = round(b["prob_keep"] * 100)
    return {
        "headline": f"Get paid to offer to buy {b['underlying']} at a discount",
        "plain_english": (
            f"You'd offer {b['dte']} days of \"insurance\" on {b['underlying']} and collect "
            f"${premium:,.0f} right now. If {b['underlying']} dips below ${b['strike']:,.2f}, "
            f"you agree to buy 100 shares at that discount — a price you'd be glad to own it at. "
            f"Odds of just keeping the ${premium:,.0f}: about {pk}%."),
        "prob_keep": b["prob_keep"],
        "guidance": (f"If you took this, Banshee aims to close it at half the profit "
                     f"(~${premium / 2:,.0f}) or by day 21 — whichever first. You never track that yourself."),
    }


def best_candidate(universe_data, account_size=None):
    """Scan normalized per-underlying data, return the single best CSP move.
    The 5% max-per-trade rule is a HARD GATE: when account_size is given, only
    contracts whose collateral fits within 5% of the account are eligible. If
    none fit, candidate is None and account_too_small explains the threshold.
    Never raises on bad data — a failed underlying is recorded in partial_failures."""
    scanned, failures, eligible = [], [], []
    for u in universe_data or []:
        scanned.append(u.get("sym"))
        if u.get("failed"):
            failures.append(u.get("sym"))
            continue
        eligible.extend(_eligible_from(u))

    base = {"universe_scanned": scanned, "partial_failures": failures,
            "ivr_estimated": True}
    none_result = {**base, "candidate": None, "guardrails": [], "translation": None,
                   "low_iv_warning": False, "account_too_small": None}
    if not eligible:
        return none_result

    affordable = eligible
    if account_size and account_size > 0:
        cap = account_size * 0.05
        affordable = [e for e in eligible if e["collateral"] <= cap]
        if not affordable:
            cheapest = min(e["collateral"] for e in eligible)
            return {**none_result, "account_too_small": {
                "account_size": account_size,
                "max_per_trade": round(cap, 2),
                "cheapest_collateral": round(cheapest, 2),
                "min_account_for_5pct": round(cheapest / 0.05, 2),
            }}

    best = max(affordable, key=lambda e: (e["annualized_yield"],
                                          -abs(abs(e["delta"]) - 0.25),
                                          e["open_interest"]))
    if account_size and account_size > 0:
        pct = best["collateral"] / account_size * 100
        best["sizing"] = {"account_size": account_size, "pct": round(pct, 2),
                          "within_5pct": pct <= 5.0}

    ivr = best["ivr_estimate"]
    return {**base, "candidate": best, "guardrails": _guardrails(best),
            "translation": _translation(best),
            "low_iv_warning": (ivr is not None and ivr < IVR_MIN),
            "account_too_small": None}
