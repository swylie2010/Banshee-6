"""
options_data.py — Banshee Options data adapter (Phase 1).

The ONLY options code that touches a specific provider (yfinance). It maps raw
provider output into the engine's normalized contract BY MEANING (column
aliases), so a future user-supplied API or Alpaca feed gets its own adapter
filling the same shape. See feedback_data_source_agnostic.
"""
import math
from datetime import date as _date
from shared_data import get_last_price

# field -> accepted source column names (by meaning, not position)
_ALIASES = {
    "strike": ["strike"],
    "bid": ["bid"],
    "ask": ["ask"],
    "iv": ["impliedVolatility", "implied_vol", "iv"],
    "open_interest": ["openInterest", "open_interest", "oi"],
    "volume": ["volume", "vol"],
}


def _pick(row, names):
    for n in names:
        if n in row and row[n] is not None:
            return row[n]
    return None


def _safe_float(v, default=0.0):
    """None / NaN / non-numeric -> default."""
    if v is None:
        return default
    try:
        f = float(v)
    except (TypeError, ValueError):
        return default
    return default if math.isnan(f) else f


def _safe_int(v, default=0):
    """None / NaN / non-numeric -> default."""
    if v is None:
        return default
    try:
        f = float(v)
    except (TypeError, ValueError):
        return default
    return default if math.isnan(f) else int(f)


def _dte(expiry_iso, today_iso):
    y, m, d = (int(x) for x in str(expiry_iso).split("T")[0].split("-")[:3])
    ty, tm, td = (int(x) for x in str(today_iso).split("T")[0].split("-")[:3])
    return (_date(y, m, d) - _date(ty, tm, td)).days


def normalize_puts(df, spot, expiry, today):
    """Map a provider puts DataFrame -> [contract...]. Rows missing a strike or
    IV are skipped (can't be evaluated). Pure: `today` supplied by the caller."""
    dte = _dte(expiry, today)
    out = []
    for _, r in df.iterrows():
        row = r.to_dict()
        strike = _pick(row, _ALIASES["strike"])
        iv = _pick(row, _ALIASES["iv"])
        if strike is None or iv is None:
            continue
        try:
            if isinstance(iv, float) and math.isnan(iv):
                continue
        except TypeError:
            pass
        bid = _safe_float(_pick(row, _ALIASES["bid"]))
        ask = _safe_float(_pick(row, _ALIASES["ask"]))
        mid = round((bid + ask) / 2.0, 4) if (bid > 0 or ask > 0) else 0.0
        oi = _safe_int(_pick(row, _ALIASES["open_interest"]))
        vol = _safe_int(_pick(row, _ALIASES["volume"]))
        out.append({
            "type": "put", "underlying": None, "spot": spot,
            "strike": float(strike), "expiry": str(expiry), "dte": dte,
            "bid": bid, "ask": ask, "mid": mid,
            "iv": float(iv), "open_interest": oi, "volume": vol,
        })
    return out


def fetch_chain(symbol, today=None, max_dte=55):
    """Fetch put contracts for `symbol` within max_dte days.
    Returns (contracts, meta) on success, or an error dict when no capable provider is active."""
    import data_providers
    if not data_providers.has_capability("options_chain"):
        return {"error": "provider_unavailable", "feature": "options_chain",
                "user_message": "No provider available for options chain data — enable a compatible provider in Settings → Data Sources"}
    import yfinance as yf
    today = today or _date.today().isoformat()
    tk = yf.Ticker(symbol)
    spot = get_last_price(symbol)
    contracts = []
    for expiry in (tk.options or []):
        if _dte(expiry, today) > max_dte:
            continue
        try:
            oc = tk.option_chain(expiry)
            contracts.extend(normalize_puts(oc.puts, spot, expiry, today))
        except Exception:
            continue
    return contracts, {"sym": symbol, "spot": spot, "as_of": today}


def fetch_closes(symbol, period="1y"):
    """Trailing daily closes for the IVR realized-vol estimate, via provider chain."""
    import data_providers
    limit = 252 if period == "1y" else 126
    df = data_providers.fetch_ohlcv(symbol, "1d", limit)
    return [float(x) for x in df["close"].tolist()] if not df.empty else []


def fetch_earnings_date(symbol: str):
    """Return the next earnings date for symbol as a date object, or None.
    Returns an error dict when no capable provider is active.

    Defensive: yfinance calendar format varies by version. Returns None on
    any error so callers can treat missing data as 'no known earnings'.
    """
    import data_providers
    if not data_providers.has_capability("earnings_calendar"):
        return {"error": "provider_unavailable", "feature": "earnings_calendar",
                "user_message": "No provider available for earnings calendar — enable a compatible provider in Settings → Data Sources"}
    try:
        import yfinance as yf
        from datetime import date as _date
        cal = yf.Ticker(symbol).calendar
        if cal is None:
            return None
        # Dict form (newer yfinance): {"Earnings Date": [Timestamp, ...]}
        if isinstance(cal, dict):
            ed = cal.get("Earnings Date")
            if ed is None:
                return None
            if hasattr(ed, "__iter__") and not isinstance(ed, str):
                ed = next(iter(ed), None)
            return ed.date() if hasattr(ed, "date") else (ed if isinstance(ed, _date) else None)
        # DataFrame form (older yfinance)
        if hasattr(cal, "columns") and "Earnings Date" in cal.columns:
            raw = cal["Earnings Date"].iloc[0]
            return raw.date() if hasattr(raw, "date") else None
        if hasattr(cal, "index") and "Earnings Date" in cal.index:
            raw = cal.loc["Earnings Date"]
            if hasattr(raw, "__iter__"):
                raw = next(iter(raw), None)
            return raw.date() if raw is not None and hasattr(raw, "date") else None
        return None
    except Exception:
        return None
