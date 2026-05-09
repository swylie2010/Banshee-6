"""
risk_engine.py — Banshee Pro Risk Management Engine
===================================================
Calculates optimal position sizing, exact risk parameters, and dynamic
capital efficiency scaling across leverage profiles.
"""

def calculate_execution_plan(account_size: float, risk_percent: float, entry_price: float, stop_loss: float, smc_conflicted: bool = False) -> dict:
    """
    Given an account size, risk tolerance (%), exact entry, and stop,
    computes the position size to ensure risk is strictly capped.
    Also returns capital efficiency metrics and structured take-profit zones.
    """
    if entry_price <= 0 or stop_loss <= 0 or entry_price == stop_loss:
        return {"error": "Invalid entry or stop loss price."}

    is_long = entry_price > stop_loss
    max_risk_dollars = account_size * (risk_percent / 100.0)
    stop_distance = abs(entry_price - stop_loss)

    position_size = max_risk_dollars / stop_distance

    confidence_note = None
    if smc_conflicted:
        position_size = position_size * 0.5
        confidence_note = (
            "SMC CONFLICTED: HTF and LTF structure disagree — position sized at 50% conviction. "
            "Wait for timeframe alignment before committing full size."
        )

    position_value = position_size * entry_price

    leverage_levels = [1, 2, 5, 10, 20, 50, 100]
    capital_efficiency = []
    
    for lvl in leverage_levels:
        margin_required = position_value / lvl
        capital_efficiency.append({
            "leverage": lvl,
            "margin_required": margin_required
        })

    def calc_target(r):
        return entry_price + (stop_distance * r) if is_long else entry_price - (stop_distance * r)

    targets = [
        {"r_multiple": 1, "price": calc_target(1), "profit": max_risk_dollars * 1},
        {"r_multiple": 2, "price": calc_target(2), "profit": max_risk_dollars * 2},
        {"r_multiple": 3, "price": calc_target(3), "profit": max_risk_dollars * 3},
    ]

    return {
        "account_size": account_size,
        "risk_percent": risk_percent,
        "entry_price": entry_price,
        "stop_loss": stop_loss,
        "is_long": is_long,
        "max_risk_dollars": max_risk_dollars,
        "position_size": position_size,
        "position_value": position_value,
        "capital_efficiency": capital_efficiency,
        "targets": targets,
        "smc_conflicted": smc_conflicted,
        "confidence_note": confidence_note,
    }
