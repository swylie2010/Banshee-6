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
"""

import os
import sys

import requests

# Portability fix — same pattern as before so Claude Desktop always finds this file.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Banshee Pro")

CORE_URL = "http://127.0.0.1:8765"
_TIMEOUT = 120  # seconds — give engines time to fetch data on a cold cache

_OFFLINE_MSG = (
    "BANSHEE CORE OFFLINE — run launch_banshee.bat to start the Core server first.\n"
    "The Core must be running before MCP tools will respond."
)


def _get(path: str, **params) -> str:
    try:
        clean = {k: v for k, v in params.items() if v is not None}
        r = requests.get(f"{CORE_URL}{path}", params=clean, timeout=_TIMEOUT)
        return r.text
    except requests.ConnectionError:
        return _OFFLINE_MSG
    except Exception as e:
        return f"Core error ({path}): {e}"


def _post(path: str, body: dict) -> str:
    try:
        r = requests.post(f"{CORE_URL}{path}", json=body, timeout=_TIMEOUT)
        return r.text
    except requests.ConnectionError:
        return _OFFLINE_MSG
    except Exception as e:
        return f"Core error ({path}): {e}"


# ─────────────────────────────────────────────────────────────────────────────

@mcp.tool()
def get_macro_weather() -> str:
    """
    Returns the current global macroeconomic risk regime.
    Reads VIX, yield curve, Fed liquidity, BTC canary, DXY, credit stress, and SKEW.
    Use before sizing into any trade to confirm macro is a tailwind, not headwind.
    Returns: MACRO REGIME / SYSTEMIC RISK SCORE / ACTIVE WARNINGS / SENSOR DETAILS.
    """
    return _get("/macro/weather")


@mcp.tool()
def read_market_intel() -> str:
    """
    Returns today's Daily Predator structured intelligence briefing if available,
    otherwise falls back to live RSS financial headlines.
    Includes: top story, watchlist events with impact scores, discovered signals,
    yesterday followups, macro tone, and risk level.
    Run the Daily Predator from the Market Intel tab to generate a fresh briefing.
    """
    return _get("/intel")


@mcp.tool()
def get_regime() -> str:
    """
    Lightweight macro regime check — regime bucket, risk score, active warning count.
    Fast go/no-go before committing to a full synthesize_nexus call.
    Reads from the 15-minute disk cache when warm; falls back to a live fetch.
    Regime buckets: TRENDING / NEUTRAL / CAUTION / FEAR.
    """
    return _get("/regime")


@mcp.tool()
def get_watchlist() -> str:
    """
    Returns the user's saved watchlist from predator_config.json.
    Use this before scan_assets so you know what to scan without asking the user.
    Also returns the configured sensitivity and any custom Tier 1 keywords.
    """
    return _get("/watchlist")


@mcp.tool()
def get_asset_radar(symbol: str, mode: str = "swing", output_mode: str = "human") -> str:
    """
    Full multi-timeframe technical analysis for a single asset.
    Calculates: EMA 20/50/200, SuperTrend, Stochastic RSI, VWAP, swing S/R,
    volume pressure, funding rate (crypto), entry quality, and ATR trade plan.

    Args:
        symbol:      Ticker — crypto 'BTC/USD', stocks 'NVDA', futures 'GC=F'.
        mode:        'long_term' (W/D/4H), 'swing' (D/4H/1H) [default], 'sniper' (4H/1H/15m).
                     Aliases: 'active' → swing, 'position' → long_term.
        output_mode: 'human' [default] — full narrative. 'agent' — compact JSON.
    """
    return _get("/radar", symbol=symbol, mode=mode, output_mode=output_mode)


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
    return _post("/scan", {"symbols": symbols, "mode": mode, "output_mode": output_mode})


@mcp.tool()
def synthesize_nexus(symbol: str, mode: str = "swing", use_ai: bool = True, output_mode: str = "human") -> str:
    """
    Full top-down Banshee synthesis: macro regime + micro technicals + news.
    The flagship tool — macro context, catalyst scan, live TA, and AI narrative.

    Args:
        symbol:      Ticker to analyze (e.g. 'BTC/USD', 'NVDA', 'SPY').
        mode:        'long_term', 'swing' [default], or 'sniper'.
        use_ai:      Set False to skip the AI call and return structured data only.
        output_mode: 'human' [default] — full narrative. 'agent' — compact JSON.
    """
    return _get("/nexus", symbol=symbol, mode=mode, use_ai=use_ai, output_mode=output_mode)


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
    return _post("/execution-plan", {
        "account_size":   account_size,
        "risk_percent":   risk_percent,
        "entry_price":    entry_price,
        "stop_loss":      stop_loss,
        "smc_conflicted": smc_conflicted,
    })


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
    return _get("/strategies", name=strategy_name if strategy_name else None)


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
    return _get("/smc", symbol=symbol, ltf=ltf, htf=htf, use_ai=use_ai)


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
    import json
    body = {
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
    }
    raw = _post("/journal/open", body)
    try:
        return json.dumps(json.loads(raw), indent=2)
    except Exception:
        return raw


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
    body: dict = {"trade_id": trade_id}
    if exit_reason:
        body["exit_reason"] = exit_reason
    if signal_correct is not None:
        body["signal_correct"] = signal_correct
    if note:
        body["note"] = note
    import json
    raw = _post("/journal/annotate", body)
    try:
        return json.dumps(json.loads(raw), indent=2)
    except Exception:
        return raw


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
    import json
    raw = _get("/kill-switch/check")
    try:
        data = json.loads(raw)
        lines = [
            f"KILL SWITCH: {'FIRED' if data.get('fired') else 'NOT TRIGGERED'}",
            f"DOMINO PHASE: {data.get('domino_phase', '?')}",
            f"REGIME: {data.get('regime', '?')}",
            data.get("message", ""),
        ]
        closed = data.get("positions_closed", [])
        if closed:
            lines += ["", f"POSITIONS CLOSED ({len(closed)}):"]
            for p in closed:
                pnl = f"{p['pnl_pct']:+.2f}%" if p.get("pnl_pct") is not None else "N/A"
                lines.append(
                    f"  #{p['id']} {p['symbol']} {p['direction'].upper()} — "
                    f"exit ${p['exit_price']:.4f}  P&L: {pnl}"
                )
        return "\n".join(lines)
    except Exception:
        return raw


@mcp.tool()
def get_signal_log() -> str:
    """
    Returns the full signal quality log: all trades with explicit outcome judgements,
    plus aggregate stats broken down by regime and exit reason.

    Use this to ask: 'How often is Banshee directionally correct?'
    and 'In which regimes does it get direction wrong?'
    This is the core Autonomous Agent training data read path.
    """
    import json
    raw = _get("/journal/signal-log")
    try:
        data = json.loads(raw)
        lines = [
            f"TOTAL TRADES: {data.get('total_trades', 0)}",
            f"JUDGED (signal_correct set): {data.get('judged_trades', 0)}",
        ]
        rate = data.get("signal_correct_rate_pct")
        lines.append(f"SIGNAL CORRECT RATE: {rate}%" if rate is not None else "SIGNAL CORRECT RATE: not yet judged")

        regime_bd = data.get("regime_breakdown", {})
        if regime_bd:
            lines += ["", "REGIME BREAKDOWN:"]
            for regime, stats in regime_bd.items():
                lines.append(f"  {regime}: {stats['correct']}/{stats['judged']} correct ({stats.get('correct_rate_pct', '?')}%)")

        exit_bd = data.get("exit_reason_breakdown", {})
        if exit_bd:
            lines += ["", "EXIT REASON BREAKDOWN:"]
            for reason, count in sorted(exit_bd.items(), key=lambda x: -x[1]):
                lines.append(f"  {reason}: {count}")

        judged_list = data.get("judged_trade_list", [])
        if judged_list:
            lines += ["", f"JUDGED TRADES ({len(judged_list)}):"]
            for t in judged_list[-20:]:  # last 20 to keep it readable
                sc    = "✓" if t.get("signal_correct") else "✗"
                er    = t.get("exit_reason") or "—"
                ann_n = len(t.get("annotations", []))
                lines.append(
                    f"  #{t['id']} {t.get('symbol','?')} {t.get('direction','?')} "
                    f"[{sc}] exit:{er}  P&L:{t.get('pnl_pct','?')}%  notes:{ann_n}"
                )
        return "\n".join(lines)
    except Exception:
        return raw


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
    import json
    raw = _get("/journal/feedback-synthesis")
    try:
        data = json.loads(raw)
        narrative = data.get("narrative", "")
        meta = (
            f"[Trades analyzed: {data.get('trades_analyzed', 0)} | "
            f"Judged closed: {data.get('trade_count', 0)} | "
            f"Briefings matched: {data.get('briefings_matched', 0)}]"
        )
        return f"{meta}\n\n{narrative}"
    except Exception:
        return raw


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
    import json
    raw = _get("/geo-harmonic", symbol=symbol, n_local=n_local)
    try:
        data = json.loads(raw)
        if "error" in data:
            return f"GEO HARMONIC ERROR: {data['error']}"

        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import geometric_harmonic as gh
        return gh.format_human(data, symbol=symbol)
    except Exception:
        return raw


@mcp.tool()
def generate_gh_pine(symbol: str, arithmetic_mid: bool = False) -> str:
    """
    Generate a paste-ready Pine Script v5 indicator that draws Banshee's
    Geo Harmonic Fibonacci arc circles on a TradingView 1D chart.

    Draws all GH circles at 6 Fib levels (0.382, 0.5, 0.618, 0.786, 1.0, 1.618)
    as 60-point polylines. Teal = floor support, red = ceiling resistance.
    Macro anchors (ATL/ATH) at 20% transparency, local ZigZag pivots at 60%.

    Paste the returned script into TradingView's Pine Editor and run it on a 1D
    chart. Log scale is recommended. Values are baked in — re-run after
    significant price moves.

    Args:
        symbol:         Ticker — crypto 'BTC/USD', stocks 'NVDA', futures 'GC=F'.
        arithmetic_mid: Use (ATH+ATL)/2 as radius endpoint instead of sqrt(ATH*ATL).

    Returns: Complete Pine Script v5 string ready to paste into TradingView.
    """
    import json
    raw = _get("/geo-harmonic/pine", symbol=symbol, arithmetic_mid=arithmetic_mid)
    try:
        data = json.loads(raw)
        if "error" in data:
            return f"GH PINE ERROR: {data['error']}"
        return data.get("pine_script", raw)
    except Exception:
        return raw


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
    import json
    raw = _get("/xabcd", symbol=symbol, pct=pct)
    try:
        data = json.loads(raw)
        if "error" in data:
            return f"XABCD SCANNER ERROR: {data['error']}"
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import xabcd_scanner as xs
        return xs.format_human(data, symbol=symbol)
    except Exception:
        return raw


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
    import json
    raw = _get("/options/candidate", account_size=account_size)
    try:
        return json.dumps(json.loads(raw), indent=2)
    except Exception:
        return raw


@mcp.tool()
def get_paper_wheel_alerts() -> str:
    """
    Returns paper Wheel positions that need attention right now.
    Flags: checkpoint_due (50%-profit or 21-DTE decision point), expiry_due (0 DTE),
    needs_attention (fill pending, order expired/canceled).

    Use as a morning check: "Do any of my paper options need action today?"
    Returns a clear message when nothing is pending — never an empty string.
    """
    import json
    raw = _get("/paper-wheels/alerts")
    try:
        data = json.loads(raw)
        alerts = data.get("alerts", [])
        if not alerts:
            return "NO PAPER WHEEL ALERTS — all paper wheels are on track."
        lines = [f"PAPER WHEEL ALERTS ({len(alerts)}):"]
        for a in alerts:
            reason = a.get("attention_reason") or "needs attention"
            lines.append(f"  #{a.get('id', '?')[:8]} {a.get('underlying', '?')} — {reason}")
        return "\n".join(lines)
    except Exception:
        return raw


# ─────────────────────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    mcp.run(transport="stdio")
