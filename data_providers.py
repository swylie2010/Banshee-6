"""data_providers.py — Pluggable data source layer for Banshee 6.

Public API:
    get_spot_price(symbol)  -> float | None
    fetch_ohlcv(symbol, timeframe, limit)  -> pd.DataFrame
    get_speed_report()  -> dict

All provider logic is private. Callers never know which provider delivered the data.
No imports from shared_data.py (avoids circular import) — keys read directly via _load_keys().
"""

import json
import time
from collections import deque
from pathlib import Path

import pandas as pd

from cache_utils import ttl_cache


# ── Key loading (direct — no import from shared_data to avoid circular dep) ───

_KEYS_FILE = Path.home() / ".banshee_keys.json"


def _load_keys() -> dict:
    try:
        return json.loads(_KEYS_FILE.read_text())
    except Exception:
        return {}


# ── CoinGecko symbol map ───────────────────────────────────────────────────────
# CoinGecko uses slugs, not tickers. Only covers Banshee's crypto universe.
# If a symbol isn't here, CoinGecko is skipped silently.

_CG_IDS: dict[str, str] = {
    "BTC": "bitcoin",        "ETH": "ethereum",       "SOL": "solana",
    "BNB": "binancecoin",    "XRP": "ripple",          "ADA": "cardano",
    "AVAX": "avalanche-2",   "MATIC": "matic-network", "DOGE": "dogecoin",
    "LINK": "chainlink",     "DOT": "polkadot",        "UNI": "uniswap",
    "LTC": "litecoin",       "ATOM": "cosmos",         "NEAR": "near",
    "HYPE": "hyperliquid",   "HBAR": "hedera-hashgraph",
    "TAO": "bittensor",      "XLM": "stellar",
    "SUI": "sui",            "INJ": "injective-protocol",
}

# Known crypto tickers that don't carry "/" or "-USD" but are crypto
_CRYPTO_TICKERS = set(_CG_IDS.keys()) | {
    "BCH", "SHIB", "PAXG", "AAVE", "CRV", "FTM", "OP", "ARB", "APT", "ALGO",
}


# ── Asset class inference ──────────────────────────────────────────────────────

def _asset_class(symbol: str) -> str:
    """Return 'crypto' or 'equity' based on symbol format."""
    s = symbol.upper()
    if "/" in s or "-USD" in s or "-USDT" in s:
        return "crypto"
    base = s.split("-")[0]
    if base in _CRYPTO_TICKERS:
        return "crypto"
    return "equity"


# ── Latency tracker ────────────────────────────────────────────────────────────

_latency: dict[str, deque] = {
    "coinbase":  deque(maxlen=10),
    "alpaca":    deque(maxlen=10),
    "coingecko": deque(maxlen=10),
    "yfinance":  deque(maxlen=10),
}


def _record_latency(name: str, ms: float) -> None:
    """Record a successful fetch latency. Never called on failure."""
    if name in _latency:
        _latency[name].append(ms)


def _mean_latency(name: str) -> float:
    """Mean of recorded latencies, or inf if no samples (UNTESTED)."""
    d = _latency.get(name)
    if not d:
        return float("inf")
    return sum(d) / len(d)


def _tier(avg_ms: float) -> str:
    if avg_ms == float("inf"):
        return "UNTESTED"
    if avg_ms <= 300:
        return "FAST"
    if avg_ms <= 2000:
        return "GOOD"
    return "SLOW"


def _by_speed(names: list[str]) -> list[str]:
    """Return provider names sorted fastest-first by observed latency."""
    return sorted(names, key=_mean_latency)


# ── Spot price adapters ────────────────────────────────────────────────────────

def _coinbase_spot(symbol: str) -> float | None:
    import ccxt
    ex = ccxt.coinbase({"enableRateLimit": True})
    ticker = ex.fetch_ticker(symbol)
    time.sleep(0.1)
    last = ticker.get("last")
    return float(last) if last else None


def _coingecko_spot(symbol: str) -> float | None:
    import requests
    # Normalise: "BTC/USD" → "BTC", "BTC-USD" → "BTC"
    base = symbol.upper().split("/")[0].split("-")[0]
    cg_id = _CG_IDS.get(base)
    if not cg_id:
        return None  # symbol not in map — skip silently
    keys = _load_keys()
    api_key = keys.get("COINGECKO", {}).get("key", "")
    if api_key:
        base_url = "https://pro-api.coingecko.com/api/v3"
        headers = {"x-cg-pro-api-key": api_key}
    else:
        base_url = "https://api.coingecko.com/api/v3"
        headers = {}
    r = requests.get(
        f"{base_url}/simple/price",
        params={"ids": cg_id, "vs_currencies": "usd"},
        headers=headers,
        timeout=5,
    )
    r.raise_for_status()
    return float(r.json()[cg_id]["usd"])


def _alpaca_spot(symbol: str) -> float | None:
    import requests
    keys = _load_keys()
    ak = keys.get("ALPACA_KEY", {}).get("key", "")
    sk = keys.get("ALPACA_SECRET", {}).get("key", "")
    if not ak or not sk:
        return None
    r = requests.get(
        f"https://data.alpaca.markets/v2/stocks/{symbol}/quotes/latest",
        headers={"APCA-API-KEY-ID": ak, "APCA-API-SECRET-KEY": sk},
        timeout=5,
    )
    r.raise_for_status()
    q = r.json().get("quote", {})
    bid, ask = q.get("bp", 0), q.get("ap", 0)
    if bid and ask:
        return float((bid + ask) / 2)
    return None


def _yfinance_spot(symbol: str) -> float | None:
    import yfinance as yf
    try:
        info = yf.Ticker(symbol).fast_info
        price = info.last_price
        if price and price > 0:
            return float(price)
    except Exception:
        pass
    try:
        hist = yf.Ticker(symbol).history(period="5d", interval="1d")
        if not hist.empty and "Close" in hist.columns:
            return float(hist["Close"].iloc[-1])
    except Exception:
        pass
    return None


_SPOT_FNS: dict = {
    "coinbase":  _coinbase_spot,
    "coingecko": _coingecko_spot,
    "alpaca":    _alpaca_spot,
    "yfinance":  _yfinance_spot,
}
_SPOT_CRYPTO = ["coinbase", "coingecko", "yfinance"]
_SPOT_EQUITY = ["alpaca", "yfinance"]


@ttl_cache(ttl=60, skip_none=True)
def get_spot_price(symbol: str) -> float | None:
    """Last known price via the fastest available provider. 60s cache."""
    chain = _SPOT_CRYPTO if _asset_class(symbol) == "crypto" else _SPOT_EQUITY
    for name in _by_speed(chain):
        fn = _SPOT_FNS[name]
        try:
            t0 = time.monotonic()
            result = fn(symbol)
            if result is not None and result > 0:
                _record_latency(name, (time.monotonic() - t0) * 1000)
                return result
        except Exception:
            pass
    return None


# ── OHLCV stub (replaced in Task 3) ──────────────────────────────────────────

def fetch_ohlcv(symbol: str, timeframe: str, limit: int = 300) -> pd.DataFrame:
    return pd.DataFrame()  # replaced in Task 3


def get_speed_report() -> dict:
    """Return latency summary for all providers. Called by /settings/data-sources/speed."""
    result = {}
    for name in ("coinbase", "alpaca", "coingecko", "yfinance"):
        avg = _mean_latency(name)
        samples = len(_latency.get(name, []))
        result[name] = {
            "avg_ms": round(avg) if avg != float("inf") else None,
            "samples": samples,
            "tier": _tier(avg),
        }
    return result


def probe_coingecko_latency() -> dict:
    """Fire a timed CoinGecko BTC spot fetch (bypasses cache) to populate latency data.
    Called by POST /settings/data-sources/test-coingecko from the Settings TEST button."""
    t0 = time.monotonic()
    price = None
    try:
        price = _coingecko_spot("BTC")  # _coingecko_spot defined in Task 2
        if price:
            _record_latency("coingecko", (time.monotonic() - t0) * 1000)
    except Exception:
        pass
    return {"price": price, "speed": get_speed_report()}
