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
