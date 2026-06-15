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


# ── Public stubs (replaced in Tasks 2 & 3) ───────────────────────────────────

def get_spot_price(symbol: str) -> float | None:
    return None  # replaced in Task 2


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
