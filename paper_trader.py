"""
paper_trader.py — Banshee Pro Paper Trading Journal
=====================================================
Connects to Alpaca paper trading to place bracket orders and logs the full
Banshee context (verdict, regime, macro, ATR plan) alongside every trade.

This is the forward signal log — the honest test of whether Banshee's full
layered system outperforms the bare indicator backtests.

Storage: ~/AntiEverything/Banshee_6/paper_trades.json
"""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional

JOURNAL_FILE  = Path(__file__).parent / "paper_trades.json"
_JOURNAL_LOCK = threading.Lock()  # serialises all load-modify-save sequences within a process

VALID_EXIT_REASONS = {
    "target_hit", "stop_hit", "manual_close",
    "wick_not_triggered", "conviction_changed",
    "forced_liquidation", "kill_switch_crack", "other",
}

# Alpaca crypto symbols use "BTC/USD" format; stocks use plain "NVDA"
# Map Banshee symbols → Alpaca trading symbols
def _alpaca_symbol(banshee_symbol: str) -> str:
    """Convert Banshee symbol to Alpaca trading symbol."""
    s = banshee_symbol.upper()
    # Already in Alpaca format (BTC/USD, SOL/USD, ETH/USD)
    if "/" in s:
        # Prefer /USD over /USDT for Alpaca
        base = s.split("/")[0]
        return f"{base}/USD"
    return s  # NVDA, SPY etc — already correct


def _is_crypto(symbol: str) -> bool:
    return "/" in symbol or symbol.upper().endswith(("-USD", "-USDT", "-USDC"))


def _load_journal() -> list[dict]:
    if JOURNAL_FILE.exists():
        try:
            return json.loads(JOURNAL_FILE.read_text(encoding="utf-8"))
        except Exception:
            return []
    return []


def _save_journal(trades: list[dict]):
    JOURNAL_FILE.write_text(
        json.dumps(trades, indent=2, default=str),
        encoding="utf-8"
    )


def _get_client():
    from shared_data import load_providers
    from alpaca.trading.client import TradingClient
    p = load_providers()
    key    = p.get("ALPACA_KEY", {}).get("key", "")
    secret = p.get("ALPACA_SECRET", {}).get("key", "")
    if not key or not secret:
        raise ValueError("Alpaca keys not configured. Add them in Settings.")
    return TradingClient(key, secret, paper=True)


def place_paper_trade(
    symbol: str,
    direction: str,          # "long" or "short"
    entry_price: float,
    stop_price: float,
    target_price: float,
    banshee_context: dict,   # full res dict from micro_engine
    position_usd: float = 5000.0,
) -> dict:
    """
    Place a bracket paper trade on Alpaca and record it in the journal.

    Returns a result dict with status, order_id, and any error message.
    """
    from alpaca.trading.requests import MarketOrderRequest, TakeProfitRequest, StopLossRequest
    from alpaca.trading.enums import OrderSide, TimeInForce, OrderClass

    alpaca_sym = _alpaca_symbol(symbol)
    side = OrderSide.BUY if direction == "long" else OrderSide.SELL
    crypto = _is_crypto(symbol)

    # Calculate quantity from position size
    qty = round(position_usd / entry_price, 6 if crypto else 0)
    if qty <= 0:
        qty = 1

    order_id   = None
    order_error = None

    try:
        client = _get_client()

        if crypto:
            # Alpaca doesn't support bracket orders for crypto — place a plain market
            # order so the position is tracked; stop/target are managed via the journal.
            req = MarketOrderRequest(
                symbol        = alpaca_sym,
                qty           = qty,
                side          = side,
                time_in_force = TimeInForce.GTC,
            )
        else:
            req = MarketOrderRequest(
                symbol        = alpaca_sym,
                qty           = qty,
                side          = side,
                time_in_force = TimeInForce.GTC,
                order_class   = OrderClass.BRACKET,
                take_profit   = TakeProfitRequest(limit_price=round(target_price, 2)),
                stop_loss     = StopLossRequest(stop_price=round(stop_price, 2)),
            )
        order = client.submit_order(req)
        order_id = str(order.id)

    except Exception as e:
        order_error = str(e)

    # Always log, even if Alpaca order failed
    trade = {
        "id":            _next_id(),
        "timestamp":     datetime.now().isoformat(timespec="seconds"),
        "symbol":        symbol,
        "alpaca_symbol": alpaca_sym,
        "direction":     direction,
        "entry_price":   entry_price,
        "stop_price":    stop_price,
        "target_price":  target_price,
        "position_usd":  position_usd,
        "qty":           qty,
        "rr":            round(abs(target_price - entry_price) / abs(entry_price - stop_price), 2) if stop_price != entry_price else 0,
        # Banshee context at signal time
        "verdict":       banshee_context.get("verdict", ""),
        "regime":        banshee_context.get("regime", ""),
        "macro_regime":  banshee_context.get("macro_regime", ""),
        "edge":          banshee_context.get("edge", ""),
        "mode":          banshee_context.get("mode", ""),
        "risk_score":    banshee_context.get("risk_score"),
        # Alpaca order tracking
        "alpaca_order_id": order_id,
        "alpaca_error":    order_error,
        # crypto = market order placed (no bracket); equity = full bracket order
        "status":          "open" if order_id else "logged_only",
        "order_type":      ("market_only" if (order_id and crypto) else
                           "bracket"      if order_id else "logged_only"),
        # Outcome (filled in when closed)
        "exit_price":    None,
        "exit_time":     None,
        "pnl_pct":       None,
        "outcome":       None,   # "win" / "loss" / "breakeven"
        "notes":         "",
        # Outcome quality — set via log_signal_outcome MCP tool or journal UI
        "exit_reason":    None,  # target_hit|stop_hit|manual_close|wick_not_triggered|conviction_changed|other
        "signal_correct": None,  # bool — was direction right regardless of P&L/execution
        "annotations":    [],    # [{ts, note}] — timestamped event log, append-only
    }

    with _JOURNAL_LOCK:
        trades = _load_journal()
        trades.append(trade)
        _save_journal(trades)

    return {
        "status":      "placed" if order_id else "logged_only",
        "order_id":    order_id,
        "order_type":  trade["order_type"],
        "alpaca_error": order_error,   # informational only — trade is logged regardless
        "trade_id":    trade["id"],
    }


def get_open_trades() -> list[dict]:
    return [t for t in _load_journal() if t.get("status") in ("open", "logged_only")]


def get_all_trades() -> list[dict]:
    return _load_journal()


def close_all_open_trades(note: str = "") -> list[dict]:
    """
    Fetch current price for every open/logged_only trade and close them all.
    Used by the kill switch when CRACK regime is detected.
    Returns a list of summary dicts for the positions closed.
    """
    open_trades = get_open_trades()
    if not open_trades:
        return []

    # Fetch prices outside the lock — external network calls, can be slow
    open_ids     = {t["id"] for t in open_trades}
    prices       = {t["id"]: (_fetch_current_price(t["symbol"]) or t.get("entry_price", 0.0))
                   for t in open_trades}
    close_note   = note or "Kill switch: CRACK DETECTED"

    with _JOURNAL_LOCK:
        trades = _load_journal()
        closed = []
        for t in trades:
            if t["id"] not in open_ids:
                continue
            price = prices[t["id"]]
            _close_journal_trade(t, price, close_note)
            t["exit_reason"] = "kill_switch_crack"
            closed.append({
                "id":         t["id"],
                "symbol":     t["symbol"],
                "direction":  t["direction"],
                "exit_price": price,
                "pnl_pct":    t.get("pnl_pct"),
            })
        if closed:
            _save_journal(trades)
    return closed


def update_trade_levels(
    trade_id: int,
    stop_price: Optional[float] = None,
    target_price: Optional[float] = None,
) -> bool:
    """Update stop and/or target on an open trade and recalculate R:R.
    Only updates fields that are provided (non-None); existing values are preserved."""
    with _JOURNAL_LOCK:
        trades = _load_journal()
        for t in trades:
            if t["id"] == trade_id:
                if stop_price is not None:
                    t["stop_price"] = stop_price
                if target_price is not None:
                    t["target_price"] = target_price
                # Recalculate R:R only when both levels are known
                entry = t.get("entry_price")
                s = t.get("stop_price")
                tgt = t.get("target_price")
                if entry is not None and s is not None and tgt is not None and s != entry:
                    t["rr"] = round(abs(tgt - entry) / abs(entry - s), 2)
                _save_journal(trades)
                return True
    return False


def close_trade(
    trade_id: int,
    exit_price: float,
    notes: str = "",
    exit_reason: Optional[str] = None,
) -> bool:
    """Manually close a logged trade and record outcome."""
    with _JOURNAL_LOCK:
        trades = _load_journal()
        for t in trades:
            if t["id"] == trade_id:
                direction = t.get("direction", "long")
                entry     = t.get("entry_price", exit_price)
                pnl_pct   = ((exit_price - entry) / entry * 100) if direction == "long" \
                       else ((entry - exit_price) / entry * 100)
                t["exit_price"] = exit_price
                t["exit_time"]  = datetime.now().isoformat(timespec="seconds")
                t["pnl_pct"]    = round(pnl_pct, 2)
                t["outcome"]    = "win" if pnl_pct > 0 else ("loss" if pnl_pct < 0 else "breakeven")
                t["status"]     = "closed"
                t["notes"]      = notes
                if exit_reason and exit_reason in VALID_EXIT_REASONS:
                    t["exit_reason"] = exit_reason
                _save_journal(trades)
                return True
    return False


def _infer_exit_reason(note: str) -> Optional[str]:
    """Guess exit_reason from an auto-generated note string."""
    n = note.lower()
    if "target" in n:   return "target_hit"
    if "stop" in n:     return "stop_hit"
    if "canceled" in n or "rejected" in n or "expired" in n:
        return "other"
    return None


def _close_journal_trade(t: dict, exit_price: float, note: str = "") -> None:
    """Fill in outcome fields on a trade dict in-place."""
    direction = t.get("direction", "long")
    entry     = t.get("entry_price", exit_price)
    pnl_pct   = ((exit_price - entry) / entry * 100) if direction == "long" \
           else ((entry - exit_price) / entry * 100)
    t["exit_price"] = exit_price
    t["exit_time"]  = datetime.now().isoformat(timespec="seconds")
    t["pnl_pct"]    = round(pnl_pct, 2)
    t["outcome"]    = "win" if pnl_pct > 0 else ("loss" if pnl_pct < 0 else "breakeven")
    t["status"]     = "closed"
    if note:
        t["notes"] = note
    # Auto-infer exit_reason only if not already set by user
    if not t.get("exit_reason") and note:
        inferred = _infer_exit_reason(note)
        if inferred:
            t["exit_reason"] = inferred


def _fetch_current_price(symbol: str) -> Optional[float]:
    """Fetch the latest price for any symbol — crypto via Binance, stocks via yfinance."""
    import urllib.request, json as _json
    try:
        if _is_crypto(symbol):
            base  = symbol.split("/")[0].upper()
            sym_bn = f"{base}USDT"
            url   = f"https://api.binance.com/api/v3/ticker/price?symbol={sym_bn}"
            with urllib.request.urlopen(url, timeout=8) as r:
                return float(_json.loads(r.read())["price"])
        else:
            from shared_data import get_last_price
            return get_last_price(symbol)
    except Exception:
        return None


def _check_levels(t: dict, current_price: float) -> Optional[tuple[str, float]]:
    """Return (reason, level) if stop or target is hit, else None."""
    stop      = t.get("stop_price")
    target    = t.get("target_price")
    direction = t.get("direction", "long")
    if direction == "long":
        if stop   and current_price <= stop:   return ("stop",   stop)
        if target and current_price >= target: return ("target", target)
    else:
        if stop   and current_price >= stop:   return ("stop",   stop)
        if target and current_price <= target: return ("target", target)
    return None


def sync_alpaca_status() -> int:
    """
    Check all open trades and close any that have hit their stop or target.

    - Bracket orders (equities): checks Alpaca fill status
    - Market-only orders (crypto with Alpaca position): checks current price vs levels,
      closes Alpaca position if hit
    - Logged-only (no Alpaca order): checks current price vs levels, updates journal only
    Returns number of trades updated.
    """
    open_trades = get_open_trades()
    if not open_trades:
        return 0

    # All network I/O (Alpaca + price fetches) happens outside the lock
    try:
        client    = _get_client()
        positions = {p.symbol: p for p in client.get_all_positions()}
    except Exception:
        client    = None
        positions = {}

    # Build a list of (trade_id, exit_price, note) for trades that need closing
    closures: list[tuple[int, float, str]] = []
    for t in open_trades:
        try:
            order_type = t.get("order_type", "logged_only")

            if order_type == "bracket" and client:
                alpaca_sym = t.get("alpaca_symbol", _alpaca_symbol(t["symbol"]))
                if alpaca_sym in positions:
                    continue
                exit_price = t["entry_price"]
                note = "Alpaca bracket closed"
                try:
                    parent = client.get_order_by_id(t["alpaca_order_id"])
                    parent_status = str(parent.status).lower()
                    if "canceled" in parent_status or "rejected" in parent_status or "expired" in parent_status:
                        note = f"Alpaca order {parent_status} before entry"
                    else:
                        legs = getattr(parent, "legs", None) or []
                        for leg in legs:
                            leg_status = str(leg.status).lower()
                            if "filled" in leg_status and leg.filled_avg_price:
                                exit_price = float(leg.filled_avg_price)
                                leg_type = str(getattr(leg, "type", "")).lower()
                                reason = "target" if "limit" in leg_type else "stop"
                                note = f"Alpaca bracket {reason} filled at ${exit_price:.2f}"
                                break
                except Exception:
                    pass
                closures.append((t["id"], exit_price, note))

            elif order_type == "market_only" and client:
                alpaca_sym    = t.get("alpaca_symbol", _alpaca_symbol(t["symbol"]))
                pos           = positions.get(alpaca_sym)
                current_price = float(pos.current_price) if pos else _fetch_current_price(t["symbol"])
                if current_price is None:
                    continue
                hit = _check_levels(t, current_price)
                if hit:
                    reason, level = hit
                    try:
                        client.close_position(alpaca_sym)
                    except Exception:
                        pass
                    note = f"Auto-closed: {reason} hit at ~${current_price:.4f} (level ${level:.4f})"
                    closures.append((t["id"], current_price, note))

            else:
                current_price = _fetch_current_price(t["symbol"])
                if current_price is None:
                    continue
                hit = _check_levels(t, current_price)
                if hit:
                    reason, level = hit
                    note = f"Auto-closed: {reason} hit at ~${current_price:.4f} (level ${level:.4f})"
                    closures.append((t["id"], current_price, note))

        except Exception:
            continue

    if not closures:
        return 0

    # Apply all closures under the lock in a single read-modify-write
    close_map = {tid: (price, note) for tid, price, note in closures}
    with _JOURNAL_LOCK:
        trades  = _load_journal()
        updated = 0
        for t in trades:
            if t["id"] in close_map:
                price, note = close_map[t["id"]]
                _close_journal_trade(t, price, note)
                updated += 1
        if updated:
            _save_journal(trades)
    return updated


def annotate_trade(trade_id: int, note: str) -> bool:
    """Append a timestamped note to a trade's annotation log (works on open or closed trades)."""
    trades = _load_journal()
    for t in trades:
        if t["id"] == trade_id:
            entry = {"ts": datetime.now().isoformat(timespec="seconds"), "note": note}
            t.setdefault("annotations", []).append(entry)
            _save_journal(trades)
            return True
    return False


def set_signal_outcome(
    trade_id: int,
    signal_correct=None,  # bool | str | None — True/False or "partial"
    exit_reason: Optional[str] = None,
    note: str = "",
) -> bool:
    """
    Set quality fields on any trade (open or closed).
    signal_correct: True/False = direction right/wrong; "partial" = mixed result.
    exit_reason: one of VALID_EXIT_REASONS.
    Optionally appends an annotation if note is provided.
    """
    with _JOURNAL_LOCK:
        trades = _load_journal()
        for t in trades:
            if t["id"] == trade_id:
                if signal_correct is not None:
                    # Store bool as-is; store "partial" (or any str) as-is
                    t["signal_correct"] = signal_correct if isinstance(signal_correct, str) else bool(signal_correct)
                if exit_reason and exit_reason in VALID_EXIT_REASONS:
                    t["exit_reason"] = exit_reason
                if note:
                    t.setdefault("annotations", []).append(
                        {"ts": datetime.now().isoformat(timespec="seconds"), "note": note}
                    )
                _save_journal(trades)
                return True
    return False


def get_stats() -> dict:
    """Summary stats for the trade journal."""
    all_trades = _load_journal()
    trades = [t for t in all_trades if t.get("status") == "closed"]
    if not trades:
        return {"total": 0}
    wins   = [t for t in trades if t.get("outcome") == "win"]
    losses = [t for t in trades if t.get("outcome") == "loss"]
    pnls   = [t["pnl_pct"] for t in trades if t.get("pnl_pct") is not None]

    # Signal quality — judged subset (signal_correct explicitly set)
    judged  = [t for t in all_trades if t.get("signal_correct") is not None]
    correct = [t for t in judged if t.get("signal_correct") is True]

    # Exit reason breakdown across all closed trades
    exit_counts: dict = {}
    for t in trades:
        r = t.get("exit_reason") or "unset"
        exit_counts[r] = exit_counts.get(r, 0) + 1

    return {
        "total":      len(trades),
        "wins":       len(wins),
        "losses":     len(losses),
        "win_rate":   round(len(wins) / len(trades) * 100, 1),
        "avg_pnl":    round(sum(pnls) / len(pnls), 2) if pnls else 0,
        "total_pnl":  round(sum(pnls), 2),
        "best":       round(max(pnls), 2) if pnls else 0,
        "worst":      round(min(pnls), 2) if pnls else 0,
        # Signal quality
        "judged_trades":    len(judged),
        "signal_correct_rate": round(len(correct) / len(judged) * 100, 1) if judged else None,
        "exit_reasons": exit_counts,
    }


def get_current_price(symbol: str) -> Optional[float]:
    """Public wrapper — fetch latest price for any symbol."""
    return _fetch_current_price(symbol)


def _next_id() -> int:
    trades = _load_journal()
    return max((t.get("id", 0) for t in trades), default=0) + 1
