"""routes/shared_helpers.py — Internal helpers shared across route modules.

Extracted from banshee_core.py to break circular-import chains between
banshee_core.py and routes/*.py.  Both banshee_core.py and any router that
needs these functions import from here.

No side effects on import.
"""

from datetime import datetime, timezone

import macro_engine
import micro_engine
from shared_data import load_providers, fetch_crypto_ohlcv
from core_state import (
    _OHLCV_CACHE, _OHLCV_TTL,
    _load_macro_cache, _save_macro_cache,
)


def _get_sensors() -> tuple[dict, str]:
    """Return (sensors_dict, source). Reads cache or fetches live."""
    cached = _load_macro_cache()
    if cached and "mac_data" in cached:
        return cached["mac_data"], "cache"
    providers = load_providers()
    fred_key  = providers.get("FRED_API", {}).get("key")
    flight    = macro_engine.get_flight_data()
    _, liq_chg = macro_engine.get_fed_liquidity(fred_key)
    sensors   = macro_engine.compute_sensors(flight, liq_chg)
    cached2   = _load_macro_cache()
    _save_macro_cache(sensors,
                      cached2.get("news_lines", []) if cached2 else [],
                      cached2.get("events",     []) if cached2 else [])
    return sensors, "live"


def _get_ohlcv_cached(symbol: str, mode: str) -> dict:
    """Fetch TF DataFrames with a 5-minute in-memory cache."""
    key   = (symbol.upper(), mode)
    entry = _OHLCV_CACHE.get(key)
    now   = datetime.now(timezone.utc).timestamp()
    if entry and (now - entry["ts"]) < _OHLCV_TTL:
        return entry["tfs"]
    tfs = micro_engine.load_and_prepare(symbol, mode)
    if tfs and "error" not in tfs:
        _OHLCV_CACHE[key] = {"tfs": tfs, "ts": now}
    return tfs


def _fetch_smc_df(symbol: str, tf: str):
    if "/" in symbol:
        return fetch_crypto_ohlcv(symbol, tf, limit=300)
    return micro_engine.fetch_stock(symbol, tf)
