# Banshee Pro 4 — OpenClaw Vision

The long-horizon goal: an autonomous AI trading agent that runs 24/7, makes decisions, and learns from its own trade history.

## What OpenClaw Is

Banshee Pro 4 is the decision-support tool a human uses. OpenClaw is the agent that *is* the human — it reads Banshee's output, executes trades, monitors them, and logs outcomes. The journal is the training data foundation.

**Key separation:** Banshee tells you what the market is doing. OpenClaw decides what to do about it. They are separate systems. Banshee must never be coupled to OpenClaw's execution logic.

## Why the Journal Matters Now

Every paper trade logged with `signal_correct` and `exit_reason` is a training data point for OpenClaw. The critical distinction:

- **`signal_correct`** — was Banshee's *direction* right? (independent of P&L)
- **`exit_reason`** — why did the trade close? (`target_hit`, `stop_hit`, `wick_not_triggered`, etc.)

A trade where price wicked through the stop but Alpaca didn't fire = `signal_correct=True`, `exit_reason=wick_not_triggered`. This lets OpenClaw eventually answer: "In which regimes is Banshee directionally accurate even when trades don't profit?"

## Build Order (sequential — each step requires the previous)

**Step 1 — Confidence Scoring** ✅ *COMPLETE (2026-04-29)*
When SMC verdict is CONFLICTED, position size is halved and a confidence warning is surfaced. Implemented via `smc_conflicted: bool` param added to `risk_engine.calculate_execution_plan()`, wired through `banshee_core.py` (`ExecutionPlanRequest`), MCP `build_execution_plan` tool, and the Streamlit Risk Desk tab (checkbox + orange warning banner).

**Step 2 — Kill Switch** ✅ *COMPLETE (2026-04-29)*
When domino_phase >= 2 (CRACK DETECTED), auto-close all open paper positions with `exit_reason="kill_switch_crack"` and surface a critical red banner in the Macro Weather tab. Implemented via:
- `paper_trader.close_all_open_trades()` — fetches live prices and closes all open/logged_only trades
- `banshee_core.py` `/kill-switch/check` (POST action) + `/kill-switch/status` (read-only) endpoints
- Background scheduler job `_bg_check_kill_switch` runs every 15 min alongside macro refresh
- MCP `check_kill_switch` tool — callable by Claude to manually trigger or verify
- Streamlit Macro Weather tab shows a critical red banner if `~/.banshee_kill_switch.json` records a fired event

**Step 3 — Feedback Loops** ✅ *COMPLETE (2026-04-30)*
AI cross-references closed journal entries against Daily Predator briefings. Implemented via:
- `banshee_core.py` `GET /journal/feedback-synthesis` — loads judged closed trades + indexes `daily_briefings.jsonl` by date; attaches each trade's exit-day briefing (macro_tone, risk_level, top_story, watchlist headlines); calls `banshee_ai.call_ai()` with an OpenClaw self-correction prompt targeting regime patterns, blind spots, and rule adjustments
- MCP `get_feedback_synthesis` tool — callable by Claude; returns meta counts + AI narrative

**Step 4 and beyond** — autonomous execution, self-sizing, regime-adaptive strategy selection. These require Steps 1–3 to be proven and stable first.

## Architecture Requirement

OpenClaw must run 24/7, independent of whether the Streamlit UI is open. This is why the FastAPI Core exists — it's always-on regardless of UI state. OpenClaw will be a Core client, same as MCP and Streamlit.

## Current Foundation (already built)

- `paper_trader.py` — full journal with bracket orders, sync, outcome fields; `close_all_open_trades()` for kill switch
- `log_signal_outcome` MCP tool — Claude can log trade quality after the fact
- `get_signal_log` MCP tool — retrieve signal history for analysis
- `check_kill_switch` MCP tool — trigger or verify the CRACK kill switch
- `get_feedback_synthesis` MCP tool — OpenClaw self-correction: trade outcomes × Predator briefings → rule adjustment narrative
- `banshee_core.py` — always-on Core; `/kill-switch/check` + `/kill-switch/status` + `/journal/feedback-synthesis` endpoints; background 15-min kill switch job
- `build_execution_plan()` — position sizing ready for agent use (SMC-conflicted halving in Step 1)
