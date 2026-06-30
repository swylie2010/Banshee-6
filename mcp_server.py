"""
mcp_server.py — Banshee Pro MCP Server (thin proxy to Banshee Core)
====================================================================
Launched by Claude Code / Claude Desktop via stdio transport.
Forwards every tool call to the Banshee Core server on localhost:8765.

Start the Core first via launch_banshee.bat before using these tools.
If the Core is offline, each tool returns an informative error — nothing breaks.

Tools exposed:
  get_macro_weather      — global macro regime (VIX, yield curve, liquidity…)
  read_market_intel      — Daily Predator briefing (or RSS fallback)
  get_regime             — lightweight regime bucket + go/no-go (near-instant from cache)
  get_watchlist          — user's saved symbol watchlist (use before scan_assets)
  get_asset_radar        — full multi-timeframe technical analysis for one asset
  scan_assets            — ranked scan across a list of symbols
  synthesize_nexus       — macro + micro + news top-down AI briefing
  build_execution_plan   — position sizing and R-target execution plan
  get_strategy_results   — retrieve saved Strategy Lab backtests
  get_smc_structure      — SMC structure map analysis (swings, BOS/CHoCH, FVGs, OBs)
  open_paper_trade       — open a new paper trade (call after synthesize_nexus + build_execution_plan)
  check_kill_switch      — close all open paper positions if CRACK DETECTED (domino_phase >= 2)
  log_signal_outcome     — record exit reason, signal correctness, or timestamped note on any trade
  get_signal_log         — retrieve judged trades + regime/exit-reason pattern stats
  get_options_candidate  — best CSP candidate from the Wheel universe (SPY/QQQ/IWM/DIA)
  get_paper_wheels       — all paper Wheel positions with track record summary
  get_paper_wheel_alerts — paper wheels needing attention (checkpoint/expiry/fill)
  open_paper_wheel       — create a paper Wheel + place Alpaca paper CSP order
  analyze_gridbot        — 4-phase gridbot analysis (regime, topology, capital, risk)
  deploy_paper_gridbot   — deploy a paper grid (one active at a time)
  get_paper_gridbot      — check in on a running paper grid
  stop_paper_gridbot     — stop the active paper grid (the learning-event trigger)
  get_audit_log          — recent Banshee audit log entries
  get_audit_summary      — aggregated Banshee usage statistics
"""

import json
import os
import pathlib
import sys

import requests

# Portability fix — same pattern as before so Claude Desktop always finds this file.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mcp.server.fastmcp import FastMCP

from banshee_gateway import (
    BansheeGateway,
    AuditLogSchema, AuditSummarySchema,
    ExecutionPlanSchema, GeoHarmonicSchema,
    GridbotSchema, NexusSchema, OptionsCandidateSchema,
    PaperTradeSchema, PaperWheelSchema, RadarSchema,
    SMCSchema, ScanSchema, SignalOutcomeSchema,
    StrategyResultsSchema, XABCDSchema,
)

mcp = FastMCP("Banshee Pro")

CORE_URL = "http://127.0.0.1:8765"
_TIMEOUT = 120  # seconds — give engines time to fetch data on a cold cache

_OFFLINE_MSG = (
    "BANSHEE CORE OFFLINE — run launch_banshee.bat to start the Core server first.\n"
    "The Core must be running before MCP tools will respond."
)

_KEYS_FILE = pathlib.Path.home() / ".banshee_keys.json"


def _banshee_token() -> str:
    try:
        return json.loads(_KEYS_FILE.read_text()).get("banshee_token", "")
    except Exception:
        return ""


def _get(path: str, **params) -> str:
    try:
        clean = {k: v for k, v in params.items() if v is not None}
        r = requests.get(f"{CORE_URL}{path}", params=clean, timeout=_TIMEOUT,
                         headers={"X-Banshee-Token": _banshee_token()})
        return r.text
    except requests.ConnectionError:
        return _OFFLINE_MSG
    except Exception as e:
        return f"Core error ({path}): {e}"


def _post(path: str, body: dict) -> str:
    try:
        r = requests.post(f"{CORE_URL}{path}", json=body, timeout=_TIMEOUT,
                          headers={"X-Banshee-Token": _banshee_token()})
        return r.text
    except requests.ConnectionError:
        return _OFFLINE_MSG
    except Exception as e:
        return f"Core error ({path}): {e}"


def _delete(path: str) -> str:
    try:
        r = requests.delete(f"{CORE_URL}{path}", timeout=_TIMEOUT,
                            headers={"X-Banshee-Token": _banshee_token()})
        return r.text
    except requests.ConnectionError:
        return _OFFLINE_MSG
    except Exception as e:
        return f"Core error ({path}): {e}"


# Gateway — instantiated after _banshee_token is defined
gateway = BansheeGateway(token_fn=_banshee_token)

# ─────────────────────────────────────────────────────────────────────────────

@mcp.tool()
def get_macro_weather() -> str:
    """
    Returns the current global macroeconomic risk regime.
    Reads VIX, yield curve, Fed liquidity, BTC canary, DXY, credit stress, and SKEW.
    Use before sizing into any trade to confirm macro is a tailwind, not headwind.
    Returns: MACRO REGIME / SYSTEMIC RISK SCORE / ACTIVE WARNINGS / SENSOR DETAILS.
    """
    return gateway.call("get_macro_weather", {}, None, lambda _: _get("/macro/weather"))


@mcp.tool()
def read_market_intel() -> str:
    """
    Returns today's Daily Predator structured intelligence briefing if available,
    otherwise falls back to live RSS financial headlines.
    Includes: top story, watchlist events with impact scores, discovered signals,
    yesterday followups, macro tone, and risk level.
    Run the Daily Predator from the Market Intel tab to generate a fresh briefing.
    """
    return gateway.call("read_market_intel", {}, None, lambda _: _get("/intel"))


@mcp.tool()
def get_regime() -> str:
    """
    Lightweight macro regime check — regime bucket, risk score, active warning count.
    Fast go/no-go before committing to a full synthesize_nexus call.
    Reads from the 15-minute disk cache when warm; falls back to a live fetch.
    Regime buckets: TRENDING / NEUTRAL / CAUTION / FEAR.
    """
    return gateway.call("get_regime", {}, None, lambda _: _get("/regime"))


@mcp.tool()
def get_watchlist() -> str:
    """
    Returns the user's saved watchlist from predator_config.json.
    Use this before scan_assets so you know what to scan without asking the user.
    Also returns the configured sensitivity and any custom Tier 1 keywords.
    """
    return gateway.call("get_watchlist", {}, None, lambda _: _get("/watchlist"))


@mcp.tool()
def get_unleashed_mode() -> str:
    """
    Report whether Banshee is in UNLEASHED mode (global, on/off).
    In unleashed mode, short-term Triggers are surfaced even against the higher-timeframe
    Bias (htf_bias), labeled with their risk. In conservative mode those are withheld (WAIT).
    Use this to know which lens the radar/nexus verdicts are currently being read through.
    """
    return _get("/unleashed")


@mcp.tool()
def set_unleashed_mode(enabled: bool) -> str:
    """
    Flick Banshee UNLEASHED mode on (true) or off (false). GLOBAL and BINARY.
    Unleashed widens the aperture: it surfaces actionable short-term Triggers (with stated
    risk) that conservative mode buries under WAIT. It NEVER issues execute instructions —
    it flags; you decide. The UI turns RED while unleashed. Returns the new state.
    """
    return _post("/unleashed", {"enabled": enabled})


@mcp.tool()
def get_asset_radar(symbol: str, mode: str = "swing", output_mode: str = "human") -> str:
    """
    Full multi-timeframe technical analysis for a single asset.
    Calculates: EMA 20/50/200, SuperTrend, Stochastic RSI, VWAP, swing S/R,
    volume pressure, funding rate (crypto), entry quality, and ATR trade plan.

    Response includes htf_bias (dict: direction/conviction), trigger, alignment,
    unleashed (bool), and — when unleashed — a frame caveat. Read htf_bias and
    trigger separately rather than collapsing to the single verdict string.

    Args:
        symbol:      Ticker — crypto 'BTC/USD', stocks 'NVDA', futures 'GC=F'.
        mode:        'long_term' (W/D/4H), 'swing' (D/4H/1H) [default], 'sniper' (4H/1H/15m).
                     Aliases: 'active' → swing, 'position' → long_term.
        output_mode: 'human' [default] — full narrative. 'agent' — compact JSON.
    """
    return gateway.call(
        "get_asset_radar",
        {"symbol": symbol, "mode": mode, "output_mode": output_mode},
        RadarSchema,
        lambda p: _get("/radar", symbol=p["symbol"], mode=p["mode"], output_mode=p["output_mode"]),
    )


@mcp.tool()
def scan_assets(symbols: list[str], mode: str = "swing", output_mode: str = "human") -> str:
    """
    Scans a list of symbols and returns a ranked leaderboard sorted by absolute edge score.
    Answers: 'What's the best trade on my watchlist right now?'

    Args:
        symbols:     List of tickers, e.g. ['BTC/USD', 'ETH/USD', 'NVDA', 'SPY'].
        mode:        Same as get_asset_radar — 'long_term', 'swing' [default], 'sniper'.
        output_mode: 'human' [default] — formatted table. 'agent' — compact JSON array.
    """
    return gateway.call(
        "scan_assets",
        {"symbols": symbols, "mode": mode, "output_mode": output_mode},
        ScanSchema,
        lambda p: _post("/scan", {"symbols": p["symbols"], "mode": p["mode"], "output_mode": p["output_mode"]}),
    )


@mcp.tool()
def synthesize_nexus(symbol: str, mode: str = "swing", use_ai: bool = True, output_mode: str = "human") -> str:
    """
    Full top-down Banshee synthesis: macro regime + micro technicals + news.
    The flagship tool — macro context, catalyst scan, live TA, and AI narrative.

    Response includes htf_bias (dict: direction/conviction), trigger, alignment,
    unleashed (bool), and — when unleashed — a frame caveat. Read htf_bias and
    trigger separately rather than collapsing to the single verdict string.

    Args:
        symbol:      Ticker to analyze (e.g. 'BTC/USD', 'NVDA', 'SPY').
        mode:        'long_term', 'swing' [default], or 'sniper'.
        use_ai:      Set False to skip the AI call and return structured data only.
        output_mode: 'human' [default] — full narrative. 'agent' — compact JSON.
    """
    return gateway.call(
        "synthesize_nexus",
        {"symbol": symbol, "mode": mode, "use_ai": use_ai, "output_mode": output_mode},
        NexusSchema,
        lambda p: _get("/nexus", symbol=p["symbol"], mode=p["mode"], use_ai=p["use_ai"], output_mode=p["output_mode"]),
    )


@mcp.tool()
def build_execution_plan(
    account_size: float,
    risk_percent: float,
    entry_price: float,
    stop_loss: float,
    smc_conflicted: bool = False,
) -> str:
    """
    Calculates position size so worst-case loss equals exactly (account * risk% / 100).
    Also returns leverage/margin table and 1R/2R/3R take-profit targets.

    Args:
        account_size:   Total account in dollars (e.g. 10000).
        risk_percent:   Max risk per trade as a % (e.g. 1.0 for 1%).
        entry_price:    Planned entry price.
        stop_loss:      Stop-loss price (below entry for longs, above for shorts).
        smc_conflicted: Set True when HTF and LTF SMC structure disagree (CONFLICTED
                        alignment). Position size will be halved and a confidence
                        warning will appear in the output.
    """
    return gateway.call(
        "build_execution_plan",
        {
            "account_size":   account_size,
            "risk_percent":   risk_percent,
            "entry_price":    entry_price,
            "stop_loss":      stop_loss,
            "smc_conflicted": smc_conflicted,
        },
        ExecutionPlanSchema,
        lambda p: _post("/execution-plan", p),
    )


@mcp.tool()
def get_strategy_results(strategy_name: str = "") -> str:
    """
    Retrieves saved Strategy Lab backtest results.
    LIST mode (no arg): summary leaderboard of all saved strategies.
    DETAIL mode (name provided): full record with entry conditions, stats, and
    an AGENT EVALUATION block with plain-English verdict and live-trading flag.

    Args:
        strategy_name: Name to retrieve (case-insensitive). Omit to list all.
    """
    return gateway.call(
        "get_strategy_results",
        {"strategy_name": strategy_name},
        StrategyResultsSchema,
        lambda p: _get("/strategies", name=p["strategy_name"] if p["strategy_name"] else None),
    )


@mcp.tool()
def get_smc_structure(symbol: str, ltf: str = "4h", htf: str = "1d", use_ai: bool = True) -> str:
    """
    Smart Money Concepts cross-timeframe structure analysis.
    Runs the Banshee SMC engine on two timeframes, then optionally generates
    an AI narrative: HTF state → LTF state → alignment → next scenario.

    Args:
        symbol:  Ticker. Crypto: 'BTC/USD'. Stock/ETF: 'NVDA', 'SPY'.
        ltf:     Lower timeframe for chart detail. Default '4h'.
        htf:     Higher timeframe for structural context. Default '1d'.
        use_ai:  Set False to return raw SMC data without the AI narrative.
    """
    return gateway.call(
        "get_smc_structure",
        {"symbol": symbol, "ltf": ltf, "htf": htf, "use_ai": use_ai},
        SMCSchema,
        lambda p: _get("/smc", symbol=p["symbol"], ltf=p["ltf"], htf=p["htf"], use_ai=p["use_ai"]),
    )


@mcp.tool()
def open_paper_trade(
    symbol: str,
    direction: str,
    entry_price: float,
    stop_price: float,
    target_price: float,
    position_usd: float = 5000.0,
    verdict: str = "",
    regime: str = "",
    macro_regime: str = "",
    notes: str = "",
) -> str:
    """
    Open a new paper trade in the Banshee journal.

    Call this AFTER synthesize_nexus + build_execution_plan — never cold.
    The trade is logged immediately; an Alpaca bracket/market order is placed
    if Alpaca keys are configured (equity = bracket, crypto = market order).

    Args:
        symbol:       Banshee symbol, e.g. "BTC/USD" or "NVDA"
        direction:    "long" or "short"
        entry_price:  Planned entry price
        stop_price:   Stop-loss price
        target_price: Take-profit price
        position_usd: Dollar size (default $5000)
        verdict:      Banshee verdict string from synthesize_nexus (recommended)
        regime:       Regime bucket from get_regime() (recommended)
        macro_regime: Macro regime string from get_macro_weather() (optional)
        notes:        Any additional context to attach to the trade

    Returns: JSON with status, trade_id, order_id, order_type, and any Alpaca error.
    """
    return gateway.call(
        "open_paper_trade",
        {
            "symbol":       symbol,
            "direction":    direction,
            "entry_price":  entry_price,
            "stop_price":   stop_price,
            "target_price": target_price,
            "position_usd": position_usd,
            "verdict":      verdict,
            "regime":       regime,
            "macro_regime": macro_regime,
            "notes":        notes,
        },
        PaperTradeSchema,
        lambda p: _post("/journal/open", p),
    )


@mcp.tool()
def log_signal_outcome(
    trade_id: int,
    exit_reason: str = "",
    signal_correct: bool | None = None,
    note: str = "",
) -> str:
    """
    Record the outcome quality of any paper trade — open or closed.
    This is the Autonomous Agent training data foundation: distinguish execution failures
    from direction failures so patterns can be learned over time.

    Use this any time something notable happens on a trade:
    - Price wicked below stop but broker didn't fill → exit_reason='wick_not_triggered', signal_correct=True
    - Direction was wrong from the start → signal_correct=False
    - Conviction changed before stop hit → exit_reason='conviction_changed'
    - Any other observation → just pass a note

    Args:
        trade_id:       ID from the paper trade journal.
        exit_reason:    One of: target_hit | stop_hit | manual_close | wick_not_triggered |
                        conviction_changed | forced_liquidation | other
        signal_correct: True = direction was right regardless of P&L or execution.
                        False = Banshee called the wrong direction.
                        Omit if unsure — can be set later.
        note:           Free-text observation appended as a timestamped annotation.
    """
    return gateway.call(
        "log_signal_outcome",
        {"trade_id": trade_id, "exit_reason": exit_reason, "signal_correct": signal_correct, "note": note},
        SignalOutcomeSchema,
        lambda p: _post("/journal/annotate", {k: v for k, v in p.items() if v not in (None, "")}),
    )


@mcp.tool()
def check_kill_switch() -> str:
    """
    Check the macro domino phase and auto-close all open paper positions if CRACK DETECTED
    (domino_phase >= 2). Safe to call repeatedly — idempotent when no open trades remain.

    Returns: whether the kill switch fired, domino phase, regime, and a list of any
    positions closed with their exit prices and P&L.
    Use this any time you suspect macro has deteriorated into crisis territory,
    or after seeing CRACK DETECTED in get_macro_weather / get_regime output.
    """
    return gateway.call("check_kill_switch", {}, None, lambda _: _get("/kill-switch/check"))


@mcp.tool()
def get_signal_log() -> str:
    """
    Returns the full signal quality log: all trades with explicit outcome judgements,
    plus aggregate stats broken down by regime and exit reason.

    Use this to ask: 'How often is Banshee directionally correct?'
    and 'In which regimes does it get direction wrong?'
    This is the core Autonomous Agent training data read path.
    """
    return gateway.call("get_signal_log", {}, None, lambda _: _get("/journal/signal-log"))


# ─────────────────────────────────────────────────────────────────────────────
# AUTONOMOUS AGENT STEP 3 — FEEDBACK SYNTHESIS
# ─────────────────────────────────────────────────────────────────────────────

@mcp.tool()
def get_feedback_synthesis() -> str:
    """
    Autonomous Agent Step 3: AI-powered feedback synthesis.

    Cross-references all judged closed trades with the Daily Predator briefing
    that was active on each trade's exit day. Returns a narrative identifying:
    - Which regimes Banshee is correct vs. systematically wrong in
    - Whether macro tone/risk_level correlates with losses
    - Specific blind spots where trades went against the briefing
    - 2-3 concrete rule adjustments to improve signal quality

    Use this after accumulating judged trades to drive systematic improvement.
    Requires: judged closed trades (via log_signal_outcome) + daily briefings.
    """
    return gateway.call("get_feedback_synthesis", {}, None, lambda _: _get("/journal/feedback-synthesis"))


# ─────────────────────────────────────────────────────────────────────────────
# GEOMETRIC HARMONIC
# ─────────────────────────────────────────────────────────────────────────────

@mcp.tool()
def get_geo_harmonic(symbol: str, n_local: int = 233) -> str:
    """
    Geometric Harmonic analysis — multi-scalar Fibonacci arc hot zones.

    Computes macro Fibonacci arcs (anchored at absolute ATL/ATH) and local arcs
    (anchored at ZigZag pivots in the last n_local daily bars), then finds
    circle-circle intersection singularities and clusters them via DBSCAN into
    ranked hot zones. Output gives exact TradingView circle anchor coordinates.

    Use when:
    - You want objective geometric price levels for an asset (replaces "placed by feel")
    - Setting TradingView Fibonacci circle anchors for a new position
    - Cross-checking SMC OBs/FVGs against geometric confluence

    Args:
        symbol:  Ticker — crypto 'BTC/USD', stocks 'NVDA', futures 'GC=F'.
        n_local: Local ZigZag window in daily bars. Must be 144, 233, or 377 (default 233).
                 Smaller = more reactive; larger = more structural.

    Returns: ranked hot zones with price + weight + distance% from current price,
             macro anchors (ATL/ATH bar + date), arc levels at current bar,
             and ZigZag pivot summary.
    """
    return gateway.call(
        "get_geo_harmonic",
        {"symbol": symbol, "n_local": n_local},
        GeoHarmonicSchema,
        lambda p: _get("/geo-harmonic", symbol=p["symbol"], n_local=p["n_local"]),
    )


# generate_gh_pine tool removed — Pine can't drive TV's native Fib Circle tool.
# Use get_geo_harmonic; its circle anchors (center + radius_endpoint) place TV's
# native Fib Circles by hand or via direct MCP chart drawing.


# ─────────────────────────────────────────────────────────────────────────────
# XABCD HARMONIC SCANNER
# ─────────────────────────────────────────────────────────────────────────────

@mcp.tool()
def scan_xabcd(symbol: str, pct: float = 0.03) -> str:
    """
    XABCD Harmonic Pattern Scanner — Gartley, Bat, Butterfly, Crab, Shark, 5-0.

    Builds a ZigZag swing structure and validates every 5-point sequence against
    Scott Carney's Fibonacci ratio tables (±5% tolerance). Also detects *forming*
    patterns where only X, A, B, C exist and projects the Potential Reversal Zone
    (PRZ) price range where D is expected to complete the pattern.

    Use when:
    - You want to know if a harmonic pattern is currently forming or just completed.
    - Cross-checking a PRZ against SMC OBs/FVGs or Geo Harmonic hot zones.
    - Looking for high-probability reversal zones backed by Fibonacci geometry.

    Args:
        symbol: Ticker — crypto 'BTC/USD', stocks 'NVDA', futures 'GC=F'.
        pct:    ZigZag reversal threshold as a decimal (default 0.03 = 3%).
                Lower values find more pivots (noisier); higher values = fewer, cleaner.

    Returns: Confirmed patterns (with D PRZ and confidence score) and forming
             patterns (with projected PRZ range to watch).
    """
    return gateway.call(
        "scan_xabcd",
        {"symbol": symbol, "pct": pct},
        XABCDSchema,
        lambda p: _get("/xabcd", symbol=p["symbol"], pct=p["pct"]),
    )


# ─────────────────────────────────────────────────────────────────────────────
# OPTIONS WHEEL
# ─────────────────────────────────────────────────────────────────────────────

@mcp.tool()
def get_options_candidate(account_size: float | None = None) -> str:
    """
    Returns the current best Cash-Secured Put (CSP) candidate from the Wheel strategy universe.
    Checks guardrails: 35–45 DTE, 0.20–0.30 |delta|, OI > 1000, IVR estimate > 35, cash-secured only.
    Universe: SPY, QQQ, IWM, DIA (broad ETFs — no single-name earnings risk).

    Args:
        account_size: Account size in dollars. If provided, triggers the honest 5% eligibility gate —
                      a too-small account returns a clear account_too_small message, not a footnote.
                      Omit to get the candidate without the size check.

    Returns: JSON with the best candidate (strike, expiry, delta, mid premium, IVR estimate,
             guardrail verdicts) or an error/no-candidate message. Cached for 5 minutes.

    Call before open_paper_wheel to confirm the spec passes all guardrails.
    """
    return gateway.call(
        "get_options_candidate",
        {"account_size": account_size},
        OptionsCandidateSchema,
        lambda p: _get("/options/candidate", account_size=p["account_size"]),
    )


@mcp.tool()
def get_paper_wheel_alerts() -> str:
    """
    Returns paper Wheel positions that need attention right now.
    Flags: checkpoint_due (50%-profit or 21-DTE decision point), expiry_due (0 DTE),
    needs_attention (fill pending, order expired/canceled).

    Use as a morning check: "Do any of my paper options need action today?"
    Returns a clear message when nothing is pending — never an empty string.
    """
    return gateway.call("get_paper_wheel_alerts", {}, None, lambda _: _get("/paper-wheels/alerts"))


@mcp.tool()
def get_paper_wheels() -> str:
    """
    Returns all paper Wheel positions with FSM state, live P&L, and attention flags.
    Also shows a track record summary: total completed cycles and net realized P&L.

    FSM states: CASH (ready for next CSP), CSP_OPEN, SHARES (assigned, ready for CC), CC_OPEN.
    A single wheel can complete multiple cycles — the 'Cycles' count reflects total reps.

    Use to answer: "Where am I in the Wheel?" and "How is my paper track record?"
    """
    return gateway.call("get_paper_wheels", {}, None, lambda _: _get("/paper-wheels"))


@mcp.tool()
def open_paper_wheel(
    underlying: str,
    strike: float,
    expiry: str,
    premium: float,
    name: str = "",
) -> str:
    """
    Open a new paper Wheel trade — places a Cash-Secured Put sell-to-open order on Alpaca paper.

    CALL AFTER get_options_candidate confirms all guardrails pass. Never call cold.
    The order targets paper-api.alpaca.markets only — never the live endpoint.

    Args:
        underlying: Ticker, e.g. "SPY"
        strike:     Put strike price, e.g. 450.0
        expiry:     Expiry date ISO format, e.g. "2024-09-20"
        premium:    Mid-price per share from the candidate's 'mid' field, e.g. 2.50
        name:       Optional label (defaults to "<UNDERLYING> Paper Wheel")

    Returns: JSON with the new wheel record, pending_fill status, and Alpaca order_id.
             On Alpaca rejection (400) or unavailability (503): structured error string,
             no wheel record is created.
    """
    return gateway.call(
        "open_paper_wheel",
        {"underlying": underlying, "strike": strike, "expiry": expiry,
         "premium": premium, "name": name},
        PaperWheelSchema,
        lambda p: _post("/paper-wheels", {
            "candidate_snapshot": {
                "candidate": {
                    "underlying": p["underlying"],
                    "strike":     p["strike"],
                    "expiry":     p["expiry"],
                    "mid":        p["premium"],
                }
            },
            "name": p["name"] or f"{p['underlying'].upper()} Paper Wheel",
        }),
    )


# ─────────────────────────────────────────────────────────────────────────────
# GRIDBOT TOOLS
# ─────────────────────────────────────────────────────────────────────────────

@mcp.tool()
def analyze_gridbot(
    symbol: str,
    capital: float,
    grid_count: int = 10,
    fee_pct: float = 0.1,
) -> str:
    """
    4-phase gridbot analysis for a given asset and capital.
    Always call this before deploy_paper_gridbot.

    Phase 1 — Regime check: MA120 slope + RSI. Returns ELIGIBLE / NOT ELIGIBLE.
    Phase 2 — Topology: arithmetic (<= 15% range) or geometric (> 15% range).
    Phase 3 — Capital plan: 50% anchor + soft martingale across grid levels.
    Phase 4 — Risk guardrails: disaster stop, max drawdown estimate, fee churn warning.

    ELIGIBLE is a flag, not a block — you decide whether to deploy.

    Args:
        symbol:     Ticker. Crypto: 'BTC/USD'. Stock/ETF: 'NVDA', 'SPY'.
        capital:    Total USD to allocate across the grid.
        grid_count: Number of grid levels (default 10).
        fee_pct:    Exchange fee percentage per fill (default 0.1).
    """
    return gateway.call(
        "analyze_gridbot",
        {"symbol": symbol, "capital": capital, "grid_count": grid_count, "fee_pct": fee_pct},
        GridbotSchema,
        lambda p: _post("/gridbot/analyze", {"sym": p["symbol"], "capital": p["capital"],
                                              "grid_count": p["grid_count"], "fee_pct": p["fee_pct"]}),
    )


@mcp.tool()
def deploy_paper_gridbot(
    symbol: str,
    capital: float,
    grid_count: int = 10,
    fee_pct: float = 0.1,
) -> str:
    """
    Deploy a paper (simulated) grid for the given asset and capital.
    Only one grid can be active at a time — stop the current one first.

    Returns the initial slot ladder and deployed config.
    The grid runs automatically via a 5-minute server-side poller — no action needed
    between check-ins.

    Args:
        symbol:     Ticker. Crypto: 'BTC/USD'. Stock/ETF: 'NVDA', 'SPY'.
        capital:    Total USD to allocate across the grid.
        grid_count: Number of grid levels (default 10).
        fee_pct:    Exchange fee percentage per fill (default 0.1).
    """
    return gateway.call(
        "deploy_paper_gridbot",
        {"symbol": symbol, "capital": capital, "grid_count": grid_count, "fee_pct": fee_pct},
        GridbotSchema,
        lambda p: _post("/gridbot/paper", {"sym": p["symbol"], "capital": p["capital"],
                                            "grid_count": p["grid_count"], "fee_pct": p["fee_pct"]}),
    )


@mcp.tool()
def get_paper_gridbot() -> str:
    """
    Check in on the active (or most recently stopped) paper grid.
    Returns current price, slot fill count, realized P&L, unrealized P&L,
    cycle count, and status.

    Note: price data may lag up to 15 minutes (yfinance). Do not use fill
    accuracy to judge real-time performance — this is a simulator.
    """
    raw = gateway.call("get_paper_gridbot", {}, None, lambda _: _get("/gridbot/paper"))
    if raw.startswith(("BANSHEE", "Core error", '{"error"')):
        return raw
    return raw + "\n\n⚠ Price data may lag up to 15 min (yfinance). Use for structure, not real-time fills."


@mcp.tool()
def stop_paper_gridbot() -> str:
    """
    Stop the active paper grid. This is the learning-event trigger.

    Returns final P&L, cycle count, and full slot state.
    After calling this, write a journal entry: what you saw, why you stopped,
    what you learned.
    """
    return gateway.call("stop_paper_gridbot", {}, None, lambda _: _delete("/gridbot/paper"))


# ─────────────────────────────────────────────────────────────────────────────
# OBSERVATORY — audit log access for calling agents
# ─────────────────────────────────────────────────────────────────────────────

@mcp.tool()
def get_audit_log(limit: int = 50, tool: str = "", since: str = "") -> str:
    """
    Returns recent Banshee audit log entries — what tools were called, with what
    parameters, whether validation passed, and what the outcome was.

    Use this to inspect Banshee's recent behavior, verify that calls were
    recorded correctly, or report activity to your user.

    Args:
        limit: Number of entries to return (1–500, default 50). Newest first.
        tool:  Filter by tool name (e.g. 'synthesize_nexus'). Empty = all tools.
        since: ISO date string to filter entries after (e.g. '2026-06-20').
    """
    return gateway.call(
        "get_audit_log",
        {"limit": limit, "tool": tool, "since": since},
        AuditLogSchema,
        lambda p: _get("/audit/entries",
                       limit=p["limit"],
                       tool=p["tool"] if p["tool"] else None,
                       since=p["since"] if p["since"] else None),
    )


@mcp.tool()
def get_audit_summary(days: int = 7) -> str:
    """
    Returns aggregated Banshee usage statistics over a rolling window.
    Includes: total calls, breakdown by tool, validation failure rate,
    top violation rules, signal distribution, top tickers, and average latency.

    Use this to report on Banshee's behavior patterns to your user, or to
    factor recent signal distribution into your analysis.

    Args:
        days: Rolling window in days (1–90, default 7).
    """
    return gateway.call(
        "get_audit_summary",
        {"days": days},
        AuditSummarySchema,
        lambda p: _get("/audit/summary", days=p["days"]),
    )


# ─────────────────────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    mcp.run(transport="stdio")
