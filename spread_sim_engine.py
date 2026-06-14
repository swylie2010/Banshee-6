"""
spread_sim_engine.py — Banshee Spread Sim FSM.

PURE. No I/O. Event-sourced: replay(events) folds an append-only event log
into a SpreadState. Mirrors wheel_engine.py structure and conventions.

States: IDLE → SPREAD_OPEN ↔ AT_RISK → CLOSED
                          → EXPIRED
                AT_RISK   → ROLLED → SPREAD_OPEN (new leg)
"""

# AT_RISK threshold: underlying within this % of short strike
_AT_RISK_PCT = 0.02


def _init_state() -> dict:
    return {
        "status": "IDLE",
        "short_strike": None,
        "long_strike": None,
        "credit": None,
        "expiration": None,
        "current_price": None,
        "unrealized_pnl": None,
        "realized_pnl": None,
        "events": [],
        "error": None,
    }


def _is_at_risk(current_price: float, short_strike: float) -> bool:
    if not current_price or not short_strike or short_strike <= 0:
        return False
    return current_price <= short_strike * (1 + _AT_RISK_PCT)


def _on_open_spread(state: dict, data: dict) -> dict:
    state["status"] = "SPREAD_OPEN"
    state["short_strike"] = data.get("short_strike")
    state["long_strike"] = data.get("long_strike")
    state["credit"] = data.get("credit")
    state["expiration"] = data.get("expiration")
    state["current_price"] = data.get("underlying_price")
    state["realized_pnl"] = None
    state["unrealized_pnl"] = 0.0
    return state


def _on_price_update(state: dict, data: dict) -> dict:
    if state["status"] not in ("SPREAD_OPEN", "AT_RISK"):
        return state
    price = data.get("current_underlying_price")
    if price is not None:
        state["current_price"] = price
        short = state["short_strike"] or 0
        long = state["long_strike"] or 0
        credit = state["credit"] or 0
        width = short - long
        if price >= short:
            state["unrealized_pnl"] = round(credit * 100, 2)
        elif price <= long:
            state["unrealized_pnl"] = round((credit - width) * 100, 2)
        else:
            intrinsic_loss = short - price
            state["unrealized_pnl"] = round((credit - intrinsic_loss) * 100, 2)
        if _is_at_risk(price, short):
            state["status"] = "AT_RISK"
        elif state["status"] == "AT_RISK":
            state["status"] = "SPREAD_OPEN"
    return state


def _on_close_spread(state: dict, data: dict) -> dict:
    if state["status"] not in ("SPREAD_OPEN", "AT_RISK"):
        return state
    state["status"] = "CLOSED"
    state["realized_pnl"] = data.get("realized_pnl")
    state["unrealized_pnl"] = None
    return state


def _on_expire_worthless(state: dict, data: dict) -> dict:
    if state["status"] not in ("SPREAD_OPEN", "AT_RISK"):
        return state
    state["status"] = "EXPIRED"
    state["realized_pnl"] = data.get("max_profit")
    state["unrealized_pnl"] = None
    return state


def _on_roll(state: dict, data: dict) -> dict:
    if state["status"] != "AT_RISK":
        return state
    state["status"] = "SPREAD_OPEN"
    state["short_strike"] = data.get("new_short_strike")
    state["long_strike"] = data.get("new_long_strike")
    state["expiration"] = data.get("new_expiration")
    roll_net = data.get("roll_net", 0)
    state["credit"] = round((state["credit"] or 0) + roll_net, 4)
    state["unrealized_pnl"] = 0.0
    return state


_HANDLERS = {
    "OPEN_SPREAD": _on_open_spread,
    "PRICE_UPDATE": _on_price_update,
    "CLOSE_SPREAD": _on_close_spread,
    "EXPIRE_WORTHLESS": _on_expire_worthless,
    "ROLL": _on_roll,
}


def replay(events: list) -> dict:
    """Fold an append-only event log into the current SpreadState.

    Never raises. Returns error state on bad input.
    """
    state = _init_state()
    for ev in (events or []):
        try:
            event_type = ev.get("event_type") or ev.get("type", "")
            data = ev.get("data") or {}
            handler = _HANDLERS.get(event_type)
            if handler:
                state = handler(state, data)
            state["events"].append(ev)
        except Exception as exc:
            state["error"] = str(exc)
            return state
    return state
