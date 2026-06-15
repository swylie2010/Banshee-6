"""
gridbot_sim.py — Banshee Gridbot Paper Trading Simulation Engine

PURE. No I/O, no network calls, no Banshee-specific imports.
Written to be readable and adaptable — if you want to build a real bot,
swap tick() WebSocket listeners for the polling call and replace
get_last_price() with your exchange's price feed.

Architecture — Slot model:
  N+1 price levels → N slots, each covering one adjacent pair.
  Slot i: BUY at levels[i], SELL at levels[i+1].
  Each slot is "empty" (awaiting a buy) or "holding" (bought, awaiting sell).

Event sourcing:
  All state is derived from an append-only event log via replay().
  tick() receives the current slot state from replay() and returns new events.
  The caller appends those events and saves — tick() never writes files.

Adapting for live execution:
  1. Replace the caller's price poll with a WebSocket "order filled" listener.
  2. Replace get_last_price() in the route layer with your exchange's price API.
  3. Replace BUY_FILL / SELL_FILL with real order submissions to your exchange.
"""

from datetime import datetime, timezone


# ── Constants ──────────────────────────────────────────────────────────────────


# ── Slot model ─────────────────────────────────────────────────────────────────

def init_slots(levels: list) -> list:
    """Build the initial slot list from the analyze_gridbot() levels output.
    Slot i pairs levels[i] (BUY) and levels[i+1] (SELL).
    Returns a fresh list — all slots start 'empty'."""
    slots = []
    for i in range(len(levels) - 1):
        slots.append({
            "index": i,
            "buy_price": levels[i]["price"],
            "sell_price": levels[i + 1]["price"],
            "capital_allocated": levels[i]["capital_allocated"],
            "status": "empty",
            "units": 0.0,
        })
    return slots


# ── Fill detection ─────────────────────────────────────────────────────────────

def tick(slots: list, last_price: float, current_price: float,
         disaster_stop: float, fee_pct: float = 0.1) -> list:
    """Detect level crossings between last_price and current_price.

    Rules:
    - Disaster stop check runs first. If breached, only DISASTER_STOP is returned.
    - BUY_FILL: price crossed DOWN through slot's buy_price and slot is 'empty'.
    - SELL_FILL: price crossed UP through slot's sell_price and slot is 'holding'.
    - Multiple slots can fill in one tick (price moved through several levels).

    Returns a list of new event dicts (empty list = nothing to record).
    The caller is responsible for appending these to the event log and saving.
    """
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Disaster stop: if current price is at or below the stop, close all open
    # positions at the stop price and halt the grid.
    if current_price <= disaster_stop:
        total_loss = sum(
            (disaster_stop - s["buy_price"]) * s["units"]
            for s in slots if s["status"] == "holding"
        )
        return [{
            "type": "DISASTER_STOP",
            "timestamp": now,
            "trigger_price": current_price,
            "total_loss": round(total_loss, 2),
        }]

    events = []

    # BUY fills: price moved down through a slot's buy level
    if current_price < last_price:
        for slot in slots:
            if (slot["status"] == "empty"
                    and current_price <= slot["buy_price"] < last_price):
                units = round(slot["capital_allocated"] / slot["buy_price"], 8)
                events.append({
                    "type": "BUY_FILL",
                    "timestamp": now,
                    "slot": slot["index"],
                    "price": slot["buy_price"],
                    "units": units,
                    "capital_used": slot["capital_allocated"],
                })

    # SELL fills: price moved up through a slot's sell level
    if current_price > last_price:
        for slot in slots:
            if (slot["status"] == "holding"
                    and last_price < slot["sell_price"] <= current_price):
                fee_cost = (fee_pct / 100) * (
                    slot["capital_allocated"] + slot["units"] * slot["sell_price"]
                )
                profit = round(
                    (slot["units"] * slot["sell_price"])
                    - slot["capital_allocated"]
                    - fee_cost,
                    2,
                )
                events.append({
                    "type": "SELL_FILL",
                    "timestamp": now,
                    "slot": slot["index"],
                    "price": slot["sell_price"],
                    "units": slot["units"],
                    "profit": profit,
                })

    return events


# ── State replay ───────────────────────────────────────────────────────────────

def replay(events: list, config: dict, current_price: float = None) -> dict:
    """Fold the event log into the current grid state.

    Pure: never raises. Unknown events are silently skipped.
    Returns a state dict with slots, P&L, and status.

    config must have: {"levels": [...], "risk": {"disaster_stop": float}, "fee_pct": float}
    current_price is optional — only needed to compute unrealized_pnl.
    """
    if not events:
        return _empty_result()

    deploy_ev = next((e for e in events if e.get("type") == "DEPLOY"), None)
    if deploy_ev is None:
        return _empty_result()

    slots = init_slots(config.get("levels", []))
    realized_pnl = 0.0
    cycle_count = 0
    status = "active"

    for ev in events:
        t = (ev or {}).get("type")
        if t == "DEPLOY":
            continue
        elif t == "BUY_FILL":
            idx = ev["slot"]
            if 0 <= idx < len(slots):
                slots[idx]["status"] = "holding"
                slots[idx]["units"] = ev.get("units", 0.0)
        elif t == "SELL_FILL":
            idx = ev["slot"]
            if 0 <= idx < len(slots):
                slots[idx]["status"] = "empty"
                slots[idx]["units"] = 0.0
                realized_pnl += ev.get("profit", 0.0)
                cycle_count += 1
        elif t == "DISASTER_STOP":
            for s in slots:
                s["status"] = "empty"
                s["units"] = 0.0
            status = "stopped_out"
        elif t == "MANUAL_STOP":
            status = "stopped_by_user"

    unrealized_pnl = 0.0
    if current_price is not None:
        unrealized_pnl = sum(
            (current_price - s["buy_price"]) * s["units"]
            for s in slots if s["status"] == "holding"
        )

    return {
        "slots": slots,
        "realized_pnl": round(realized_pnl, 2),
        "unrealized_pnl": round(unrealized_pnl, 2),
        "cycle_count": cycle_count,
        "status": status,
    }


def _empty_result():
    return {
        "slots": [],
        "realized_pnl": 0.0,
        "unrealized_pnl": 0.0,
        "cycle_count": 0,
        "status": "no_grid",
    }
