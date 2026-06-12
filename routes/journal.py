"""routes/journal.py — trade journal and kill-switch."""
import json
import os

import paper_trader  # consolidated top-level import (was lazy in each route)

from datetime import datetime, timezone

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

import banshee_ai
import predator_engine
from core_state import _load_kill_switch_state, _save_kill_switch_state
from routes.macro import get_sensors as _get_sensors
from shared_data import load_providers

router = APIRouter()


# ─────────────────────────────────────────────────────────────────────────────
# Pydantic models
# ─────────────────────────────────────────────────────────────────────────────

class JournalOpenRequest(BaseModel):
    symbol: str
    direction: str          # "long" or "short"
    entry_price: float
    stop_price: float
    target_price: float
    position_usd: float = 5000.0
    verdict: str = ""
    regime: str = ""
    macro_regime: str = ""
    edge: str = ""
    mode: str = ""
    notes: str = ""


class JournalCloseRequest(BaseModel):
    trade_id: int
    exit_price: float
    notes: str = ""
    exit_reason: str | None = None


class JournalSyncAlpacaRequest(BaseModel):
    pass


class JournalAnnotateRequest(BaseModel):
    trade_id: int
    note: str = ""
    signal_correct: bool | None = None
    exit_reason: str | None = None


class JournalUpdateOutcomeRequest(BaseModel):
    trade_id: int
    signal_correct: str | None = None  # UI sends "yes"/"no"/"partial"/null
    exit_reason: str | None = None
    note: str = ""


class JournalUpdateLevelsRequest(BaseModel):
    trade_id: int
    stop_price: float | None = None
    target_price: float | None = None


# ─────────────────────────────────────────────────────────────────────────────
# ROUTE 11.5 — Kill Switch
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/kill-switch/check")
def route_kill_switch_check():
    """
    Check the domino phase. If CRACK DETECTED (phase >= 2) and open positions exist,
    close them all with exit_reason='kill_switch_crack' and record the event.
    Safe to call repeatedly — idempotent when no open trades remain.
    """
    sensors, _source = _get_sensors()
    domino_phase = sensors.get("domino_phase", 0)
    regime       = sensors.get("regime", "UNKNOWN")

    if domino_phase < 2:
        _save_kill_switch_state({
            "fired": False, "fired_at": None,
            "positions_closed": [], "domino_phase": domino_phase, "regime": regime,
        })
        return JSONResponse(content={
            "fired": False,
            "domino_phase": domino_phase,
            "regime": regime,
            "positions_closed": [],
            "message": f"Domino phase {domino_phase} — regime safe, kill switch not triggered.",
        })

    note   = f"Kill switch: CRACK DETECTED (domino_phase={domino_phase})"
    closed = paper_trader.close_all_open_trades(note=note)

    if closed:
        state = {
            "fired":            True,
            "fired_at":         datetime.now(timezone.utc).isoformat(),
            "positions_closed": closed,
            "domino_phase":     domino_phase,
            "regime":           regime,
        }
        _save_kill_switch_state(state)
        msg = f"KILL SWITCH FIRED — closed {len(closed)} position(s). CRACK DETECTED (domino_phase={domino_phase})."
    else:
        msg = f"CRACK DETECTED (domino_phase={domino_phase}) but no open positions to close."

    return JSONResponse(content={
        "fired":            len(closed) > 0,
        "domino_phase":     domino_phase,
        "regime":           regime,
        "positions_closed": closed,
        "message":          msg,
    })


@router.get("/kill-switch/status")
def route_kill_switch_status():
    """Return last kill switch state from disk — no action taken."""
    return JSONResponse(content=_load_kill_switch_state())


# ─────────────────────────────────────────────────────────────────────────────
# ROUTE 11 — Journal: annotate / set outcome / signal log
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/journal/open")
def route_journal_open(body: JournalOpenRequest):
    """Open a new paper trade. Called by agent after synthesize_nexus + build_execution_plan."""
    direction = body.direction.lower()
    if direction not in ("long", "short"):
        return JSONResponse(content={"error": "direction must be 'long' or 'short'"}, status_code=400)

    banshee_ctx = {
        "verdict":      body.verdict,
        "regime":       body.regime,
        "macro_regime": body.macro_regime,
        "edge":         body.edge,
        "mode":         body.mode,
    }
    result = paper_trader.place_paper_trade(
        symbol=body.symbol.upper(),
        direction=direction,
        entry_price=body.entry_price,
        stop_price=body.stop_price,
        target_price=body.target_price,
        banshee_context=banshee_ctx,
        position_usd=body.position_usd,
    )
    if body.notes and result.get("trade_id"):
        paper_trader.annotate_trade(result["trade_id"], body.notes)
    return result


@router.post("/journal/close")
def route_journal_close(body: JournalCloseRequest):
    """Close a specific open trade by ID. Routes through Core so Streamlit never writes directly."""
    ok = paper_trader.close_trade(
        trade_id=body.trade_id,
        exit_price=body.exit_price,
        notes=body.notes,
        exit_reason=body.exit_reason,
    )
    if not ok:
        return JSONResponse(content={"error": f"trade {body.trade_id} not found"}, status_code=404)
    return {"status": "closed", "trade_id": body.trade_id}


@router.post("/journal/sync-alpaca")
def route_journal_sync_alpaca():
    """Sync open trade levels against Alpaca positions. Returns number of trades updated."""
    n = paper_trader.sync_alpaca_status()
    return {"updated": n}


@router.post("/journal/annotate")
def route_journal_annotate(body: JournalAnnotateRequest):
    """
    Swiss-army journal update: append a note, set signal_correct, or set exit_reason.
    All fields are optional — pass whichever you want to update.
    Works on open and closed trades.
    """
    if not body.note and body.signal_correct is None and body.exit_reason is None:
        return JSONResponse(content={"error": "provide at least one of: note, signal_correct, exit_reason"}, status_code=400)

    ok = paper_trader.set_signal_outcome(
        trade_id=body.trade_id,
        signal_correct=body.signal_correct,
        exit_reason=body.exit_reason,
        note=body.note,
    )
    if not ok:
        return JSONResponse(content={"error": f"trade {body.trade_id} not found"}, status_code=404)
    return {"status": "updated", "trade_id": body.trade_id}


@router.get("/journal/signal-log")
def route_journal_signal_log():
    """
    Return all trades annotated with signal_correct and/or exit_reason,
    plus aggregate stats broken down by regime and exit_reason.
    """
    all_trades = paper_trader.get_all_trades()

    # Split into judged (signal_correct set) and full closed set
    judged   = [t for t in all_trades if t.get("signal_correct") is not None]
    correct  = [t for t in judged     if t.get("signal_correct") is True]
    closed   = [t for t in all_trades if t.get("status") == "closed"]

    # Regime breakdown — signal correct rate per regime
    regime_stats: dict = {}
    for t in judged:
        r = t.get("regime") or "unknown"
        bucket = regime_stats.setdefault(r, {"judged": 0, "correct": 0})
        bucket["judged"] += 1
        if t.get("signal_correct"):
            bucket["correct"] += 1
    for r, b in regime_stats.items():
        b["correct_rate_pct"] = round(b["correct"] / b["judged"] * 100, 1) if b["judged"] else None

    # Exit reason breakdown
    exit_counts: dict = {}
    for t in closed:
        reason = t.get("exit_reason") or "unset"
        exit_counts[reason] = exit_counts.get(reason, 0) + 1

    return JSONResponse(content={
        "total_trades":     len(all_trades),
        "judged_trades":    len(judged),
        "signal_correct_rate_pct": round(len(correct) / len(judged) * 100, 1) if judged else None,
        "regime_breakdown": regime_stats,
        "exit_reason_breakdown": exit_counts,
        "judged_trade_list": judged,
    })


@router.get("/journal/feedback-synthesis")
def route_journal_feedback_synthesis():
    """
    Autonomous Agent Step 3: AI synthesis cross-referencing judged closed trades with the
    Daily Predator briefing active on each trade's exit day.

    Returns a narrative identifying regime patterns, briefing-vs-outcome correlations,
    and suggested rule adjustments.
    """
    all_trades    = paper_trader.get_all_trades()
    judged_closed = [
        t for t in all_trades
        if t.get("status") == "closed" and t.get("signal_correct") is not None
    ]

    if not judged_closed:
        return JSONResponse(content={
            "narrative":         "No judged closed trades yet. Use /journal/annotate to record signal outcomes.",
            "trade_count":       0,
            "briefings_matched": 0,
            "trades_analyzed":   0,
        })

    # Index all briefings by date
    briefings_by_date: dict = {}
    if os.path.exists(predator_engine.BRIEFINGS_PATH):
        with open(predator_engine.BRIEFINGS_PATH, "r", encoding="utf-8") as _f:
            for _line in _f:
                stripped = _line.strip()
                if stripped:
                    try:
                        b = json.loads(stripped)
                        briefings_by_date[b["date"]] = b
                    except Exception:
                        pass

    # Build per-trade context blocks (cap at last 30)
    trade_blocks = []
    matched = 0
    for t in judged_closed[-30:]:
        exit_date = (t.get("exit_time") or "")[:10]
        briefing  = briefings_by_date.get(exit_date)
        if briefing:
            matched += 1

        sc    = "CORRECT" if t.get("signal_correct") else "WRONG"
        block = (
            f"Trade #{t['id']} | {t.get('symbol','?')} {t.get('direction','?')} | "
            f"Regime: {t.get('regime','unknown')} | PnL: {t.get('pnl_pct','?')}% | "
            f"Exit: {t.get('exit_reason') or 'unset'} | Signal: {sc}"
        )
        if briefing:
            wl_headlines = "; ".join(
                ev.get("headline", "") for ev in briefing.get("watchlist_events", [])[:3]
            )
            block += (
                f"\n  Predator ({exit_date}): tone={briefing.get('macro_tone','?')} "
                f"risk={briefing.get('risk_level','?')}/5 | {briefing.get('top_story','')}"
            )
            if wl_headlines:
                block += f"\n  Watchlist events: {wl_headlines}"
        else:
            block += f"\n  Predator ({exit_date}): no briefing on file"

        trade_blocks.append(block)

    prompt = f"""AUTONOMOUS AGENT FEEDBACK SYNTHESIS — Trade Outcome vs Predator Intelligence

Analyzing {len(judged_closed)} judged closed trades. {matched} had a Predator briefing on the exit day.

TRADE LOG:
{chr(10).join(trade_blocks)}

QUESTIONS TO ANSWER:
1. REGIME PATTERNS: In which regimes is Banshee directionally correct even when trades don't profit? Where is it systematically wrong?
2. PREDATOR CORRELATION: On days when trades stopped out, what did the Predator say? Was the macro_tone and risk_level consistent with the loss?
3. BLIND SPOTS: Was Banshee trading against the macro briefing on any losing trades? Give specific examples using trade IDs.
4. ADJUSTMENTS: What 2-3 concrete rule changes would improve signal quality? Be specific (e.g., "avoid longs when risk_level >= 4 and macro_tone is BEARISH").

Keep your response to 400 words. Be direct. Use trade IDs and regime names to back up every claim."""

    providers = load_providers()
    ai_cfg    = providers.get("AI_API", {})

    if not ai_cfg.get("key"):
        return JSONResponse(content={
            "narrative":         "AI not configured — set AI_API key in providers.",
            "trade_count":       len(judged_closed),
            "briefings_matched": matched,
            "trades_analyzed":   len(trade_blocks),
        })

    system = (
        "You are Banshee Pro's Autonomous Agent, its self-correction engine. "
        "Your job is to identify systematic errors in trade signals by cross-referencing "
        "trade outcomes with macro intelligence briefings. "
        "Be specific: name regimes, cite trade IDs, and propose actionable rule changes. "
        "No hedging. Every sentence should inform a concrete rule improvement."
    )

    narrative = banshee_ai.call_ai(ai_cfg, prompt, system_prompt_override=system)

    return JSONResponse(content={
        "narrative":         narrative,
        "trade_count":       len(judged_closed),
        "briefings_matched": matched,
        "trades_analyzed":   len(trade_blocks),
    })


# ─────────────────────────────────────────────────────────────────────────────
# ROUTE — Journal trades (React Trade Journal)
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/journal/trades")
def route_journal_trades():
    """Return all trades + stats for the React Trade Journal page."""
    return {
        "trades": paper_trader.get_all_trades(),
        "stats":  paper_trader.get_stats(),
    }


@router.post("/journal/update-outcome")
def route_journal_update_outcome(body: JournalUpdateOutcomeRequest):
    """Set signal quality fields on a trade (open or closed)."""
    # Map string values from UI to bool/None/passthrough for set_signal_outcome
    sc = body.signal_correct
    if sc == "yes":
        sc_val = True
    elif sc == "no":
        sc_val = False
    else:
        sc_val = sc  # "partial" or None pass through as-is
    ok = paper_trader.set_signal_outcome(
        trade_id=body.trade_id,
        signal_correct=sc_val,
        exit_reason=body.exit_reason,
        note=body.note,
    )
    if not ok:
        return JSONResponse(
            content={"error": f"trade {body.trade_id} not found"}, status_code=404
        )
    return {"status": "updated", "trade_id": body.trade_id}


@router.post("/journal/update-levels")
def route_journal_update_levels(body: JournalUpdateLevelsRequest):
    """Update stop and target price on an open trade."""
    ok = paper_trader.update_trade_levels(
        trade_id=body.trade_id,
        stop_price=body.stop_price,
        target_price=body.target_price,
    )
    if not ok:
        return JSONResponse(
            content={"error": f"trade {body.trade_id} not found"}, status_code=404
        )
    return {"status": "updated", "trade_id": body.trade_id}
