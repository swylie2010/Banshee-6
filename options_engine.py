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


def run_scenario(spec, terminal_price):
    """Compute the deterministic outcome of a put option at expiry.
    spec: {strike, mid, cash_backed (bool), underlying (str), contracts (int, default 1)}.
    terminal_price: float — hypothetical underlying price at expiry.
    Never raises. Returns a result dict."""
    try:
        contracts = int(spec.get('contracts') or 1)
        strike = float(spec['strike'])
        mid = float(spec['mid'])
        cash_backed = bool(spec.get('cash_backed', True))
        underlying = spec.get('underlying', '?')
        premium = round(mid * 100 * contracts, 2)
        collateral = round(strike * 100 * contracts, 2)
        margin_required = round(strike * 100 * contracts * 0.20, 2)

        if float(terminal_price) >= strike:
            outcome = 'expired_worthless'
            pnl = premium
            cash_tied_up = collateral if cash_backed else margin_required
            net_cost_basis = None
            mr = None if cash_backed else margin_required
            plain = (f"Option expired worthless — you kept ${premium:,.0f} in premium "
                     f"and the obligation disappeared.")
        else:
            gross_loss = round((strike - float(terminal_price)) * 100 * contracts, 2)
            pnl = round(premium - gross_loss, 2)
            if cash_backed:
                outcome = 'assigned'
                cash_tied_up = collateral
                net_cost_basis = round(strike - mid, 2)
                mr = None
                plain = (f"Assigned — own {contracts * 100} shares at ${strike:,.2f} "
                         f"(net cost basis ${net_cost_basis:,.2f}/share). "
                         f"Cycle P&L so far: ${pnl:,.0f}.")
            else:
                outcome = 'margin_call'
                cash_tied_up = margin_required
                net_cost_basis = None
                mr = margin_required
                unhedged = round(max(0.0, gross_loss - premium), 2)
                plain = (f"Margin call — collected ${premium:,.0f} but owe ${gross_loss:,.0f}. "
                         f"Net hit: ${unhedged:,.0f}. Margin posted was ${margin_required:,.0f}.")

        return {
            'underlying': underlying,
            'strike': strike,
            'terminal_price': round(float(terminal_price), 2),
            'contracts': contracts,
            'premium_collected': premium,
            'outcome': outcome,
            'pnl': pnl,
            'cash_tied_up': cash_tied_up,
            'net_cost_basis': net_cost_basis,
            'margin_required': mr,
            'cash_backed': cash_backed,
            'plain': plain,
        }
    except Exception as e:
        return {'outcome': 'error', 'error': str(e), 'pnl': 0,
                'plain': f'Scenario calculation failed: {e}'}


def danger_lever_scenarios(base_spec, lever, spot):
    """Build the reckless spec + calm/crash terminal prices for one of the 4 danger levers.
    base_spec: the safe candidate spec dict (strike, mid, underlying, dte, cash_backed).
    lever: 'naked' | 'high_delta' | 'single_stock' | 'oversize'.
    spot: float — current underlying price.
    Returns result dict, or None for an unknown lever. Never raises.
    NOTE: The UI (DangerLeverPanel in options.jsx) duplicates the lever constants (0.85/0.62/×2.5/5)
    to fan out 4 parallel runScenario calls without a round-trip. Keep the two in sync."""
    try:
        base_strike = float(base_spec.get('strike', spot * 0.97))
        base_mid = float(base_spec.get('mid', 2.0))

        if lever == 'naked':
            reckless = {**base_spec, 'cash_backed': False}
            calm_price = round(base_strike + 2.0, 2)
            crash_price = round(base_strike * 0.85, 2)
            label = 'Skip the cash backing (naked / on margin)'
            description = 'Same trade, no cash set aside. Only 20% margin covers you.'
        elif lever == 'high_delta':
            atm_strike = round(spot * 0.99, 2)
            atm_mid = round(base_mid * 2.5, 2)
            reckless = {**base_spec, 'strike': atm_strike, 'mid': atm_mid, 'cash_backed': True}
            calm_price = round(spot * 1.02, 2)
            crash_price = round(spot * 0.85, 2)
            label = 'Chase higher assignment odds (high delta / near-ATM strike)'
            description = (f'Move the strike to ${atm_strike:,.2f} — near the money. '
                           f'Richer premium (${round(atm_mid * 100):,}), far more likely to be assigned.')
        elif lever == 'single_stock':
            reckless = {**base_spec, 'underlying': 'SINGLE STOCK (hypothetical)',
                        'mid': round(base_mid * 2.0, 2)}
            calm_price = round(base_strike + 2.0, 2)
            crash_price = round(base_strike * 0.62, 2)
            label = 'Sell against a single volatile stock'
            description = ('Same structure, single name. Double the premium — '
                           'because a 40%+ gap on earnings is real.')
        elif lever == 'oversize':
            reckless = {**base_spec, 'contracts': 5}
            calm_price = round(base_strike + 2.0, 2)
            crash_price = round(base_strike * 0.85, 2)
            label = 'Bet bigger than 5% (5 contracts instead of 1)'
            description = '5× the contracts — same per-contract math, 5× the capital and damage.'
        else:
            return None

        return {
            'lever': lever,
            'label': label,
            'description': description,
            'safe_spec': dict(base_spec),
            'reckless_spec': reckless,
            'calm_price': calm_price,
            'crash_price': crash_price,
        }
    except Exception as e:
        return None


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
        {"key": "dte", "label": "Time to expiry (DTE)", "value": f"{b['dte']} days", "passed": True,
         "plain": f"{b['dte']} days out — enough time for the clock to work in your favor."},
        {"key": "delta", "label": "Assignment odds (delta)", "value": f"{abs(b['delta']):.2f}", "passed": True,
         "plain": f"Delta {abs(b['delta']):.2f} — about {pk}% chance it expires worthless."},
        {"key": "oi", "label": "Liquidity (open interest)", "value": f"{b['open_interest']:,}", "passed": True,
         "plain": f"Open interest {b['open_interest']:,} — easy to get in and out at a fair price."},
        {"key": "cash", "label": "Cash backing (cash-secured)", "value": f"${b['collateral']:,.0f}", "passed": True,
         "plain": "Fully cash-secured — no borrowing, ever."},
        {"key": "ivr", "label": "Premium richness (IV rank, est.)",
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
        "guidance": (f"A common safe practice: once you've collected about half the premium "
                     f"(~${premium / 2:,.0f}) or you're near 21 days out — whichever comes first — many "
                     f"traders close early to lock the win and cut risk. Banshee can flag when you're "
                     f"there, but the decision, and tracking it, are yours."),
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


# Approved underlyings for a beginner Wheel — broad funds that can't gap on one headline.
BROAD_ETFS = {"SPY", "QQQ", "IWM", "DIA"}


def _nearest_contract(contracts, strike):
    """Closest put by strike, for reading IV/OI of a user-chosen strike. None if none."""
    puts = [c for c in (contracts or [])
            if c.get("type") == "put" and c.get("strike") is not None]
    if not puts or strike is None:
        return None
    return min(puts, key=lambda c: abs(c["strike"] - strike))


def grade_option(spec, market_ctx):
    """Grade a user-composed cash-secured put against EVERY rule (the inverse of
    best_candidate). Pure. spec: {underlying, strike, dte, cash_backed(bool),
    account_size(optional)}. market_ctx: {spot, contracts, closes}. Returns a
    rule-by-rule verdict; labels follow the Jargon Naming Standard."""
    underlying = (spec.get("underlying") or "").upper()
    strike = spec.get("strike")
    dte = spec.get("dte")
    cash_backed = bool(spec.get("cash_backed", True))
    account_size = spec.get("account_size")

    spot = (market_ctx or {}).get("spot")
    contracts = (market_ctx or {}).get("contracts") or []
    rv = realized_vol_series((market_ctx or {}).get("closes") or [])
    near = _nearest_contract(contracts, strike)
    iv = near.get("iv") if near else None
    mid = near.get("mid") if near else None
    oi = near.get("open_interest") if near else None
    d = put_delta(spot, strike, dte, iv) if (spot and strike and dte and iv) else None
    ivr = estimate_ivr(iv, rv)
    collateral = round(strike * 100, 2) if strike else None

    rules = []
    rules.append({"key": "cash", "label": "Cash backing (cash-secured)",
        "value": "fully cash-secured" if cash_backed else "naked / on margin",
        "passed": cash_backed,
        "why": "You keep the full purchase price in cash, ready to actually buy the shares.",
        "risk_if_broken": "Selling naked means a crash can demand cash you don't have — a margin call and forced liquidation, far past the premium you collected."})

    passed_delta = d is not None and DELTA_LOW <= abs(d) <= DELTA_HIGH
    rules.append({"key": "delta", "label": "Assignment odds (delta)",
        "value": (f"{abs(d):.2f}" if d is not None else "n/a"),
        "passed": passed_delta,
        "why": "A 0.20–0.30 delta means roughly a 70–80% chance it expires worthless.",
        "risk_if_broken": "Higher delta pays more, but you're forced to buy the shares far more often — that's buying stock, not collecting income."})

    passed_dte = dte is not None and DTE_MIN <= dte <= DTE_MAX
    rules.append({"key": "dte", "label": "Time to expiry (DTE)",
        "value": (f"{dte} days" if dte is not None else "n/a"),
        "passed": passed_dte,
        "why": "35–45 days is where time-decay works hardest in your favor.",
        "risk_if_broken": "Too short collects little premium; too long commits your cash for ages."})

    passed_oi = oi is not None and oi > OI_MIN
    rules.append({"key": "oi", "label": "Liquidity (open interest)",
        "value": (f"{oi:,}" if oi else "n/a"),
        "passed": passed_oi,
        "why": "Over 1,000 open contracts means you can get in and out at a fair price.",
        "risk_if_broken": "A thin contract can trap you — you may not be able to exit without a steep haircut."})

    passed_ivr = ivr is None or ivr >= IVR_MIN
    rules.append({"key": "ivr", "label": "Premium richness (IV rank, est.)",
        "value": (f"~{ivr:.0f} est." if ivr is not None else "n/a"),
        "passed": passed_ivr,
        "why": "Premium should be rich enough to be worth the risk; below the line, the Wheel usually waits.",
        "risk_if_broken": "Thin premium isn't worth the obligation you'd take on."})

    passed_under = underlying in BROAD_ETFS
    rules.append({"key": "underlying", "label": "What you sell against (underlying)",
        "value": underlying or "n/a",
        "passed": passed_under,
        "why": "Broad funds (SPY/QQQ/IWM/DIA) can't gap 30% on a single headline.",
        "risk_if_broken": "A single name pays more because it can crater on one earnings report overnight."})

    if account_size and account_size > 0 and collateral:
        pct = collateral / account_size * 100
        passed_size = pct <= 5.0
        size_val = f"{round(pct, 2)}% of account"
    else:
        passed_size = None
        size_val = "no account size given"
    rules.append({"key": "size", "label": "Trade size (% of account)",
        "value": size_val,
        "passed": passed_size,
        "why": "No single trade should use more than 5% of your account.",
        "risk_if_broken": "One assignment ties up everything — no dry powder, stuck holding for months."})

    failed = [r["key"] for r in rules if r["passed"] is False]
    skipped = [r["key"] for r in rules if r["passed"] is None]
    return {
        "underlying": underlying, "strike": strike, "dte": dte,
        "collateral": collateral,
        "delta": (round(d, 3) if d is not None else None),
        "ivr_estimate": ivr,
        "mid": mid,
        "data_quality": {
            "nearest_listed_strike": (near["strike"] if near else None),
            "strike_gap": (round(abs(near["strike"] - strike), 2)
                           if (near and strike is not None) else None),
        },
        "rules": rules, "failed": failed, "skipped": skipped,
        "passes_all": len(failed) == 0 and not skipped,
    }
