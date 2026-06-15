"""Tests for gridbot_sim.py — slot-based fill state machine."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import gridbot_sim

# ── Fixtures ──────────────────────────────────────────────────────────────────

LEVELS = [
    {"index": 0, "price": 90000.0, "capital_allocated": 250.0},
    {"index": 1, "price": 92000.0, "capital_allocated": 220.0},
    {"index": 2, "price": 94000.0, "capital_allocated": 190.0},
    {"index": 3, "price": 96000.0, "capital_allocated": 160.0},
    {"index": 4, "price": 98000.0, "capital_allocated": 130.0},
]

CONFIG = {
    "levels": LEVELS,
    "risk": {"disaster_stop": 88000.0},
    "fee_pct": 0.1,
}

# ── init_slots ────────────────────────────────────────────────────────────────

def test_init_slots_count():
    slots = gridbot_sim.init_slots(LEVELS)
    assert len(slots) == 4  # N+1 levels → N slots

def test_init_slots_structure():
    slots = gridbot_sim.init_slots(LEVELS)
    assert slots[0]["buy_price"]  == 90000.0
    assert slots[0]["sell_price"] == 92000.0
    assert slots[0]["capital_allocated"] == 250.0
    assert slots[0]["status"] == "empty"
    assert slots[0]["units"] == 0.0
    assert slots[0]["index"] == 0

def test_init_slots_last():
    slots = gridbot_sim.init_slots(LEVELS)
    assert slots[3]["buy_price"]  == 96000.0
    assert slots[3]["sell_price"] == 98000.0

# ── tick — BUY fills ──────────────────────────────────────────────────────────

def test_tick_single_buy_fill():
    slots = gridbot_sim.init_slots(LEVELS)
    # Price drops from 93000 → 91000: crosses slot[1] buy_price (92000)
    events = gridbot_sim.tick(slots, last_price=93000.0, current_price=91000.0,
                              disaster_stop=88000.0, fee_pct=0.1)
    buy_fills = [e for e in events if e["type"] == "BUY_FILL"]
    assert len(buy_fills) == 1
    assert buy_fills[0]["slot"] == 1
    assert buy_fills[0]["price"] == 92000.0
    assert buy_fills[0]["units"] == round(220.0 / 92000.0, 8)
    assert buy_fills[0]["capital_used"] == 220.0

def test_tick_multi_buy_fill():
    slots = gridbot_sim.init_slots(LEVELS)
    # Price drops from 95000 → 91000: crosses slots[2] (94000) and slots[1] (92000)
    events = gridbot_sim.tick(slots, last_price=95000.0, current_price=91000.0,
                              disaster_stop=88000.0, fee_pct=0.1)
    buy_fills = [e for e in events if e["type"] == "BUY_FILL"]
    assert len(buy_fills) == 2
    assert {e["slot"] for e in buy_fills} == {1, 2}

def test_tick_no_buy_if_already_holding():
    slots = gridbot_sim.init_slots(LEVELS)
    slots[1]["status"] = "holding"
    slots[1]["units"] = round(220.0 / 92000.0, 8)
    # Price drops through slot[1] buy level again — should NOT re-fill
    events = gridbot_sim.tick(slots, last_price=93000.0, current_price=91000.0,
                              disaster_stop=88000.0, fee_pct=0.1)
    buy_fills = [e for e in events if e["type"] == "BUY_FILL" and e["slot"] == 1]
    assert len(buy_fills) == 0

# ── tick — SELL fills ─────────────────────────────────────────────────────────

def test_tick_sell_fill():
    slots = gridbot_sim.init_slots(LEVELS)
    units = round(220.0 / 92000.0, 8)
    slots[1]["status"] = "holding"
    slots[1]["units"] = units
    # Price rises from 93000 → 95000: crosses slot[1] sell_price (94000)
    events = gridbot_sim.tick(slots, last_price=93000.0, current_price=95000.0,
                              disaster_stop=88000.0, fee_pct=0.1)
    sell_fills = [e for e in events if e["type"] == "SELL_FILL"]
    assert len(sell_fills) == 1
    assert sell_fills[0]["slot"] == 1
    assert sell_fills[0]["price"] == 94000.0
    assert sell_fills[0]["profit"] > 0  # sold higher than bought

def test_tick_no_sell_if_empty():
    slots = gridbot_sim.init_slots(LEVELS)
    # slot[1] is empty — no SELL should fire even if price crosses sell level
    events = gridbot_sim.tick(slots, last_price=93000.0, current_price=95000.0,
                              disaster_stop=88000.0, fee_pct=0.1)
    sell_fills = [e for e in events if e["type"] == "SELL_FILL"]
    assert len(sell_fills) == 0

def test_tick_no_op():
    slots = gridbot_sim.init_slots(LEVELS)
    # Price barely moves, no level crossed
    events = gridbot_sim.tick(slots, last_price=95000.0, current_price=95100.0,
                              disaster_stop=88000.0, fee_pct=0.1)
    assert events == []

# ── tick — disaster stop ──────────────────────────────────────────────────────

def test_tick_disaster_stop():
    slots = gridbot_sim.init_slots(LEVELS)
    slots[0]["status"] = "holding"
    slots[0]["units"] = round(250.0 / 90000.0, 8)
    events = gridbot_sim.tick(slots, last_price=89000.0, current_price=87000.0,
                              disaster_stop=88000.0, fee_pct=0.1)
    assert len(events) == 1
    assert events[0]["type"] == "DISASTER_STOP"
    assert events[0]["trigger_price"] == 87000.0
    assert events[0]["total_loss"] < 0  # loss is negative

def test_tick_disaster_stop_beats_normal_fills():
    # Even if price crossed a buy level AND the disaster stop, only DISASTER_STOP fires
    slots = gridbot_sim.init_slots(LEVELS)
    events = gridbot_sim.tick(slots, last_price=93000.0, current_price=86000.0,
                              disaster_stop=88000.0, fee_pct=0.1)
    types = [e["type"] for e in events]
    assert "DISASTER_STOP" in types
    assert "BUY_FILL" not in types

# ── replay ────────────────────────────────────────────────────────────────────

def test_replay_empty_events():
    state = gridbot_sim.replay([], CONFIG)
    assert state["status"] == "no_grid"

def test_replay_deploy_only():
    events = [{"type": "DEPLOY", "timestamp": "2026-06-14T10:00:00Z", "price": 95000.0}]
    state = gridbot_sim.replay(events, CONFIG)
    assert state["status"] == "active"
    assert len(state["slots"]) == 4
    assert all(s["status"] == "empty" for s in state["slots"])

def test_replay_buy_fill():
    units = round(220.0 / 92000.0, 8)
    events = [
        {"type": "DEPLOY",   "timestamp": "2026-06-14T10:00:00Z", "price": 95000.0},
        {"type": "BUY_FILL", "timestamp": "2026-06-14T10:05:00Z",
         "slot": 1, "price": 92000.0, "units": units, "capital_used": 220.0},
    ]
    state = gridbot_sim.replay(events, CONFIG)
    assert state["slots"][1]["status"] == "holding"
    assert state["slots"][1]["units"] == units
    assert state["realized_pnl"] == 0.0
    assert state["cycle_count"] == 0

def test_replay_full_cycle():
    units = round(220.0 / 92000.0, 8)
    profit = round(units * 94000.0 - 220.0 - 0.001 * (220.0 + units * 94000.0), 2)
    events = [
        {"type": "DEPLOY",    "timestamp": "2026-06-14T10:00:00Z", "price": 95000.0},
        {"type": "BUY_FILL",  "timestamp": "2026-06-14T10:05:00Z",
         "slot": 1, "price": 92000.0, "units": units, "capital_used": 220.0},
        {"type": "SELL_FILL", "timestamp": "2026-06-14T10:10:00Z",
         "slot": 1, "price": 94000.0, "units": units, "profit": profit},
    ]
    state = gridbot_sim.replay(events, CONFIG)
    assert state["slots"][1]["status"] == "empty"
    assert state["slots"][1]["units"] == 0.0
    assert state["cycle_count"] == 1
    assert state["realized_pnl"] == profit

def test_replay_disaster_stop():
    events = [
        {"type": "DEPLOY",        "timestamp": "2026-06-14T10:00:00Z", "price": 95000.0},
        {"type": "BUY_FILL",      "timestamp": "2026-06-14T10:05:00Z",
         "slot": 0, "price": 90000.0, "units": 0.00278, "capital_used": 250.0},
        {"type": "DISASTER_STOP", "timestamp": "2026-06-14T10:10:00Z",
         "trigger_price": 87000.0, "total_loss": -100.0},
    ]
    state = gridbot_sim.replay(events, CONFIG)
    assert state["status"] == "stopped_out"
    assert all(s["status"] == "empty" for s in state["slots"])

def test_replay_manual_stop():
    events = [
        {"type": "DEPLOY",      "timestamp": "2026-06-14T10:00:00Z", "price": 95000.0},
        {"type": "MANUAL_STOP", "timestamp": "2026-06-14T10:30:00Z", "current_price": 95000.0},
    ]
    state = gridbot_sim.replay(events, CONFIG)
    assert state["status"] == "stopped_by_user"

def test_replay_unrealized_pnl():
    units = round(220.0 / 92000.0, 8)
    events = [
        {"type": "DEPLOY",   "timestamp": "2026-06-14T10:00:00Z", "price": 95000.0},
        {"type": "BUY_FILL", "timestamp": "2026-06-14T10:05:00Z",
         "slot": 1, "price": 92000.0, "units": units, "capital_used": 220.0},
    ]
    state = gridbot_sim.replay(events, CONFIG, current_price=93000.0)
    # Holding slot 1: (93000 - 92000) * units = ~$2.39
    assert state["unrealized_pnl"] == round((93000.0 - 92000.0) * units, 2)
