"""
alpaca_options.py — Banshee Options Phase 3 Alpaca adapter.

Sole I/O layer for Alpaca paper options. Pure functions (build_occ_symbol,
_parse_occ_symbol) have no imports and are testable without alpaca-py.
All I/O functions (fetch_calls_chain, place_option_order, get_order,
get_position, cancel_order) do lazy SDK imports so the module loads even
when alpaca-py is absent.

Always targets paper-api.alpaca.markets — never the live endpoint.
"""
import math
import re

_OCC_RE = re.compile(r'^([A-Z]+)(\d{2})(\d{2})(\d{2})([CP])(\d{8})$')

# Live options trading is intentionally disabled in this build.
# Users who wish to enable live execution may set this to True at their own risk.
_LIVE_TRADING_ENABLED = False


class AlpacaUnavailableError(Exception):
    """Alpaca API unreachable or SDK not installed."""


class LiveTradingNotEnabled(Exception):
    """Live options trading is disabled in this build."""


class AlpacaOrderRejectedError(Exception):
    """Alpaca rejected the order; .reason has the human-readable cause."""
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


def build_occ_symbol(underlying: str, expiry_iso: str, option_type: str, strike: float) -> str:
    """Build an OCC option symbol.
    Example: build_occ_symbol("SPY", "2024-09-20", "put", 450.0) -> "SPY240920P00450000"
    """
    date_part = expiry_iso.replace("-", "")[2:]          # YYMMDD
    type_char  = option_type.upper()[0]                  # P or C
    strike_int = int(round(strike * 1000))
    return f"{underlying.upper()}{date_part}{type_char}{strike_int:08d}"


def _parse_occ_symbol(occ: str):
    """Parse an OCC symbol back to components. Returns dict or None on failure."""
    m = _OCC_RE.match(occ or "")
    if not m:
        return None
    underlying, yy, mm, dd, type_char, strike_str = m.groups()
    year   = 2000 + int(yy)
    expiry = f"{year}-{mm}-{dd}"
    option_type = "call" if type_char == "C" else "put"
    strike = int(strike_str) / 1000.0
    return {"underlying": underlying, "expiry": expiry,
            "option_type": option_type, "strike": strike}


def _dte(expiry_iso: str, today_iso: str) -> int:
    from datetime import date as _d
    y, m, d   = (int(x) for x in str(expiry_iso).split("T")[0].split("-")[:3])
    ty, tm, td = (int(x) for x in str(today_iso).split("T")[0].split("-")[:3])
    return (_d(y, m, d) - _d(ty, tm, td)).days


def _safe_float(v, default=0.0) -> float:
    if v is None:
        return default
    try:
        f = float(v)
    except (TypeError, ValueError):
        return default
    return default if math.isnan(f) else f


# ── Client factories ──────────────────────────────────────────────────────────

def _get_alpaca_keys() -> tuple:
    """Load Alpaca API key/secret from .banshee_keys.json. Raises AlpacaUnavailableError if missing."""
    try:
        from shared_data import load_providers
    except ImportError as e:
        raise AlpacaUnavailableError(f"shared_data not found: {e}")
    p      = load_providers()
    key    = p.get("ALPACA_KEY", {}).get("key", "")
    secret = p.get("ALPACA_SECRET", {}).get("key", "")
    if not key or not secret:
        raise AlpacaUnavailableError("Alpaca keys not configured — add them in Settings.")
    return key, secret


def _get_trading_client():
    """TradingClient(paper=True) using keys from .banshee_keys.json."""
    try:
        from alpaca.trading.client import TradingClient
    except ImportError as e:
        raise AlpacaUnavailableError(f"alpaca-py not installed: {e}")
    key, secret = _get_alpaca_keys()
    try:
        return TradingClient(key, secret, paper=True)
    except Exception as e:
        raise AlpacaUnavailableError(str(e))


def _get_data_client():
    """OptionHistoricalDataClient using same keys."""
    try:
        from alpaca.data.historical.option import OptionHistoricalDataClient
    except ImportError as e:
        raise AlpacaUnavailableError(f"alpaca-py not installed: {e}")
    key, secret = _get_alpaca_keys()
    try:
        return OptionHistoricalDataClient(key, secret)
    except Exception as e:
        raise AlpacaUnavailableError(str(e))


# ── Public I/O functions ──────────────────────────────────────────────────────

def fetch_calls_chain(symbol: str, min_dte: int, max_dte: int, spot: float = None) -> list:
    """Fetch calls chain from Alpaca. Returns list of normalized contracts.
    Same shape as options_data.normalize_puts() plus delta and occ_symbol fields."""
    from datetime import date, timedelta
    try:
        from alpaca.data.requests import OptionChainRequest
        from alpaca.trading.enums import ContractType
    except ImportError as e:
        raise AlpacaUnavailableError(str(e))

    if spot is None:
        try:
            import yfinance as yf
            spot = float(yf.Ticker(symbol).fast_info["lastPrice"])
        except Exception:
            spot = 0.0

    today   = date.today()
    exp_gte = (today + timedelta(days=min_dte)).isoformat()
    exp_lte = (today + timedelta(days=max_dte)).isoformat()

    try:
        client = _get_data_client()
        req    = OptionChainRequest(
            underlying_symbol=symbol,
            expiration_date_gte=exp_gte,
            expiration_date_lte=exp_lte,
            type=ContractType.CALL,
        )
        chain = client.get_option_chain(req)
    except AlpacaUnavailableError:
        raise
    except Exception as e:
        raise AlpacaUnavailableError(str(e))

    today_iso = today.isoformat()
    out = []
    for occ_sym, snap in (chain or {}).items():
        parsed = _parse_occ_symbol(occ_sym)
        if not parsed:
            continue
        dte = _dte(parsed["expiry"], today_iso)
        if not (min_dte <= dte <= max_dte):
            continue
        quote = snap.latest_quote
        bid   = _safe_float(quote.bid_price if quote else None)
        ask   = _safe_float(quote.ask_price if quote else None)
        mid   = round((bid + ask) / 2.0, 4) if (bid > 0 or ask > 0) else 0.0
        iv    = _safe_float(snap.implied_volatility)
        delta = _safe_float(snap.greeks.delta, None) if snap.greeks else None
        out.append({
            "type": "call", "underlying": symbol, "spot": spot,
            "strike": parsed["strike"], "expiry": parsed["expiry"], "dte": dte,
            "bid": bid, "ask": ask, "mid": mid, "iv": iv,
            "open_interest": 0, "volume": 0,
            "delta": delta, "occ_symbol": occ_sym,
        })
    return sorted(out, key=lambda c: (c["dte"], c["strike"]))


def place_option_order(occ_symbol: str, side: str, qty: int, limit_price: float) -> dict:
    """Submit a limit order to Alpaca paper. side should be 'sell'.
    Returns {order_id, status, submitted_at}.
    Raises AlpacaOrderRejectedError or AlpacaUnavailableError."""
    try:
        from alpaca.trading.requests import LimitOrderRequest
        from alpaca.trading.enums import OrderSide, TimeInForce, PositionIntent
        from alpaca.common.exceptions import APIError
    except ImportError as e:
        raise AlpacaUnavailableError(str(e))

    order_side = OrderSide.SELL if side.lower() == "sell" else OrderSide.BUY
    req = LimitOrderRequest(
        symbol=occ_symbol,
        qty=qty,
        side=order_side,
        time_in_force=TimeInForce.DAY,
        limit_price=float(limit_price),
        position_intent=PositionIntent.SELL_TO_OPEN,
    )
    try:
        client = _get_trading_client()
        order  = client.submit_order(req)
    except AlpacaUnavailableError:
        raise
    except APIError as e:
        raise AlpacaOrderRejectedError(str(e))
    except Exception as e:
        raise AlpacaUnavailableError(str(e))

    return {
        "order_id":     str(order.id),
        "status":       order.status.value,
        "submitted_at": order.submitted_at.isoformat() if order.submitted_at else None,
    }


def get_order(order_id: str) -> dict:
    """Poll an order by ID. Returns {status, filled_avg_price, filled_at}.
    Raises AlpacaUnavailableError on network failure."""
    try:
        from alpaca.common.exceptions import APIError
    except ImportError as e:
        raise AlpacaUnavailableError(str(e))
    try:
        client = _get_trading_client()
        order  = client.get_order_by_id(order_id)
    except AlpacaUnavailableError:
        raise
    except Exception as e:
        raise AlpacaUnavailableError(str(e))
    return {
        "status":           order.status.value,
        "filled_avg_price": _safe_float(order.filled_avg_price, None) if order.filled_avg_price else None,
        "filled_at":        order.filled_at.isoformat() if order.filled_at else None,
    }


def get_position(occ_symbol: str):
    """Return open position dict or None if not found.
    Raises AlpacaUnavailableError on network failure."""
    try:
        from alpaca.common.exceptions import APIError
    except ImportError as e:
        raise AlpacaUnavailableError(str(e))
    try:
        client = _get_trading_client()
        pos    = client.get_open_position(occ_symbol)
    except AlpacaUnavailableError:
        raise
    except Exception:
        return None   # position not found (404) or other error
    return {
        "qty":             _safe_float(pos.qty),
        "avg_entry_price": _safe_float(pos.avg_entry_price),
        "unrealized_pl":   _safe_float(pos.unrealized_pl),
        "current_price":   _safe_float(pos.current_price, None) if pos.current_price else None,
    }


def cancel_order(order_id: str) -> bool:
    """Attempt to cancel an order. Returns True on success, False if already terminal."""
    try:
        client = _get_trading_client()
        client.cancel_order_by_id(order_id)
        return True
    except Exception:
        return False


# ── Paper-wheel polling ───────────────────────────────────────────────────────

def _poll_one_paper_wheel(wheel: dict) -> bool:
    """
    Poll Alpaca for status of a single paper wheel.
    Returns True if anything changed (so caller knows to save).
    """
    from datetime import datetime as _dt, date as _date
    import wheel_engine
    changed = False

    events = wheel.get("events", [])
    # Find most recent event with an alpaca_order_id
    open_ev = None
    for ev in reversed(events):
        if ev.get("alpaca_order_id"):
            open_ev = ev
            break

    if not open_ev:
        return False

    order_id = open_ev["alpaca_order_id"]

    if open_ev.get("fill_price") is None:
        # Order pending — check order status
        try:
            order = get_order(order_id)
        except AlpacaUnavailableError:
            return False

        status = order.get("status", "")
        if status == "filled":
            open_ev["fill_price"]  = order.get("filled_avg_price")
            open_ev["fill_time"]   = order.get("filled_at")
            wheel["needs_attention"]  = False
            wheel["attention_reason"] = None
            changed = True
        elif status in ("expired", "canceled"):
            wheel["needs_attention"]  = True
            wheel["attention_reason"] = "order_pending"
            changed = True

    else:
        # Order filled — check open position
        underlying = wheel.get("underlying", "")
        expiry     = open_ev.get("expiry", "")
        option_type = "put" if open_ev.get("type") == "SOLD_CSP" else "call"
        strike     = open_ev.get("strike")
        if not (underlying and expiry and strike):
            return False

        occ = build_occ_symbol(underlying, expiry, option_type, float(strike))
        try:
            pos = get_position(occ)
        except AlpacaUnavailableError:
            return False

        if pos:
            # Compute DTE before building live dict so it can be included
            try:
                from datetime import date as _d2
                exp_date = _d2.fromisoformat(expiry)
                live_dte = (exp_date - _d2.today()).days
            except Exception:
                exp_date = None
                live_dte = None
            wheel["live"] = {
                "unrealized_pl":  pos.get("unrealized_pl"),
                "current_price":  pos.get("current_price"),
                "last_polled":    _dt.utcnow().isoformat(),
                "dte":            live_dte,
            }
            changed = True
            # DTE checks for attention prompts
            try:
                if exp_date is None:
                    from datetime import date as _d2
                    exp_date = _d2.fromisoformat(expiry)
                dte = live_dte if live_dte is not None else (exp_date - _d2.today()).days
                fsm_state = wheel_engine.replay(events)
                already_held = any(e.get("type") == "CHECKPOINT_HELD" for e in events)
                if dte <= 0 and not wheel.get("attention_reason") == "expiry_due":
                    wheel["needs_attention"]  = True
                    wheel["attention_reason"] = "expiry_due"
                    changed = True
                elif dte <= 21 and not already_held:
                    wheel["needs_attention"]  = True
                    wheel["attention_reason"] = "checkpoint_due"
                    changed = True
            except Exception:
                pass
        else:
            # Position gone — likely expired or assigned
            if not wheel.get("needs_attention"):
                wheel["needs_attention"]  = True
                wheel["attention_reason"] = "expired"
                changed = True

    wheel["last_polled"] = _dt.utcnow().isoformat() if changed else wheel.get("last_polled")
    return changed


def poll_paper_wheels(data: dict) -> bool:
    """Poll all paper wheels in the given store dict for Alpaca fills.
    Mutates data['wheels'] in place. Returns True if any wheel changed.
    Called by the background scheduler in banshee_core.py."""
    wheels = data.get("wheels", [])
    if not wheels:
        return False
    changed_any = False
    for wheel in wheels:
        if _poll_one_paper_wheel(wheel):
            changed_any = True
    return changed_any
