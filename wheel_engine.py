"""
wheel_engine.py — Banshee Options Phase 2 "The Simulated Wheel".

PURE. No I/O, no network, NEVER imports yfinance. Event-sourced: replay() folds
an append-only event log into the FSM state, the single suggested next move, and
running totals. Same discipline as options_engine.py / ledger_engine.py.

States: CASH -> CSP_OPEN -> SHARES -> CC_OPEN (and back). See the Phase 2 spec.
"""
import math

def _init_state():
    return {
        "state": "CASH",
        "premium_collected": 0.0,
        "realized_pnl": 0.0,
        "cycles_completed": 0,
        "shares_held": 0,
        "cost_basis": None,      # per-share assignment strike while holding shares
        "cycle_premium": 0.0,    # premium collected within the current cycle (dollars); /100 converts to per-share credit (1 contract = 100 shares)
        "leg": None,             # current open leg dict
        "checkpoint_done": False,
        "history": [],
        "error": None,
    }


def _on_sold_csp(st, ev):
    prem = round((ev.get("mid") or 0.0) * 100.0, 2)
    st["leg"] = {"leg": "csp", "strike": ev.get("strike"), "expiry": ev.get("expiry"),
                 "dte": ev.get("dte"), "delta": ev.get("delta"), "premium": prem}
    st["premium_collected"] += prem
    st["cycle_premium"] += prem
    st["checkpoint_done"] = False
    st["state"] = "CSP_OPEN"
    st["history"].append(f"Sold a cash-secured put @ ${ev.get('strike')} — collected ${prem:,.0f}.")


def _on_checkpoint_held(st, ev):
    st["checkpoint_done"] = True
    st["history"].append("Held through the 50%/21-day checkpoint.")


def _on_closed_early(st, ev):
    leg = st["leg"] or {}
    if not leg:
        st["history"].append("CLOSED_EARLY received with no open position — ignored.")
        return
    prem = leg.get("premium", 0.0)
    close_cost = ev.get("est_close_cost")
    if close_cost is None:
        close_cost = round(prem * 0.5, 2)
    kept = prem - close_cost
    if leg.get("leg") == "csp":
        st["realized_pnl"] += kept
        st["cycles_completed"] += 1
        st["cycle_premium"] = 0.0
        st["state"] = "CASH"
        st["leg"] = None
        st["checkpoint_done"] = False
        st["history"].append(f"Closed the put early — kept ${kept:,.0f}. Back to cash.")
    else:  # covered call: buy it back, keep ~half, still hold shares
        # CC gain flows through net_cost_basis (cycle_premium), NOT realized_pnl — shares aren't sold yet
        st["cycle_premium"] -= close_cost
        st["state"] = "SHARES"
        st["leg"] = None
        st["checkpoint_done"] = False
        st["history"].append(f"Closed the call early — net kept ${kept:,.0f}. Still hold 100 shares.")


_HANDLERS = {
    "SOLD_CSP": _on_sold_csp,
    "CHECKPOINT_HELD": _on_checkpoint_held,
    "CLOSED_EARLY": _on_closed_early,
}


def replay(events):
    """Pure fold over the event log. Never raises — a bad event yields an
    error-state result with an actionable reason."""
    st = _init_state()
    for ev in events or []:
        h = _HANDLERS.get((ev or {}).get("type"))
        if h is None:
            st["error"] = f"Unknown event type: {(ev or {}).get('type')!r}"
            break
        try:
            h(st, ev)
        except Exception as e:  # defensive — engine must never raise to callers
            st["error"] = f"Could not apply {(ev or {}).get('type')!r}: {e}"
            break
    return _result(st)


def _totals(st):
    ncb = None
    if st["shares_held"] and st["cost_basis"] is not None:
        ncb = round(st["cost_basis"] - st["cycle_premium"] / 100.0, 2)
    return {
        "premium_collected": round(st["premium_collected"], 2),
        "net_cost_basis": ncb,
        "realized_pnl": round(st["realized_pnl"], 2),
        "cycles_completed": st["cycles_completed"],
        "shares_held": st["shares_held"],
    }


def _position(st):
    if st["leg"]:
        return dict(st["leg"])
    if st["shares_held"] and st["cost_basis"] is not None:
        return {"shares": st["shares_held"], "cost_basis": st["cost_basis"],
                "net_cost_basis": round(st["cost_basis"] - st["cycle_premium"] / 100.0, 2)}
    return None


def _decay_plain(st):
    prem = (st["leg"] or {}).get("premium", 0.0)
    half = round(prem * 0.5, 2)
    return (f"Time decay has likely eaten about half the premium. Close now to lock in "
            f"~${half:,.0f} and free up, or hold to expiry for the rest.")


def _next_move(st):
    s = st["state"]
    if s == "CASH":
        return {"action": "SELL_CSP", "label": "Sell a cash-secured put",
                "plain": "Start the wheel: get paid to offer to buy at a discount."}
    if s == "SHARES":
        return {"action": "SELL_CC", "label": "Sell a covered call",
                "plain": "You own 100 shares — get paid to agree to sell them higher."}
    if s in ("CSP_OPEN", "CC_OPEN"):
        if not st["checkpoint_done"]:
            return {"action": "CHECKPOINT", "label": "Manage the position", "plain": _decay_plain(st)}
        return {"action": "RESOLVE_EXPIRY", "label": "Resolve at expiry",
                "plain": "Where did the price land at expiry?"}
    return None


def _pending(st):
    s = st["state"]
    if s in ("CSP_OPEN", "CC_OPEN"):
        leg = (st["leg"] or {}).get("leg")
        if not st["checkpoint_done"]:
            half = round((st["leg"] or {}).get("premium", 0.0) * 0.5, 2)
            return {"kind": "checkpoint", "leg": leg, "plain": _decay_plain(st),
                    "est_close_cost": half,
                    "options": [
                        {"event": "CLOSED_EARLY", "label": f"Close early (~${half:,.0f})"},
                        {"event": "CHECKPOINT_HELD", "label": "Hold to expiry"},
                    ]}
        return {"kind": "expiry", "leg": leg, "needs": "expiry_price",
                "plain": "Enter the price at expiry to resolve."}
    return None


def _result(st):
    if st["error"]:
        return {"state": "error", "error": st["error"], "next_move": None,
                "position": None, "pending_decision": None,
                "totals": _totals(st), "history": st["history"]}
    return {"state": st["state"], "next_move": _next_move(st), "position": _position(st),
            "pending_decision": _pending(st), "totals": _totals(st),
            "history": st["history"], "error": None}
