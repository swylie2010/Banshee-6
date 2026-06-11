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


class AlpacaUnavailableError(Exception):
    """Alpaca API unreachable or SDK not installed."""


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
