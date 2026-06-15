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
    """Mean of recorded latencies, or inf if no samples."""
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

def _to_ccxt_sym(symbol: str) -> str:
    """Convert yfinance-style ('BTC-USD') or bare crypto ticker ('BTC') to ccxt pair ('BTC/USD')."""
    s = symbol.upper()
    # Already ccxt format
    if "/" in s:
        return s
    # Dash-style: "BTC-USD" → "BTC/USD", "BTC-USDT" → "BTC/USDT"
    for quote in ("-USDT", "-USD"):
        if s.endswith(quote):
            return s[:-len(quote)] + "/" + quote[1:]
    # Bare known crypto ticker: "BTC" → "BTC/USD"
    base = s.split("-")[0]
    if base in _CRYPTO_TICKERS:
        return base + "/USD"
    # Equity or unknown — return as-is
    return s


def _coinbase_spot(symbol: str) -> float | None:
    try:
        import ccxt
        ccxt_sym = _to_ccxt_sym(symbol)
        ex = ccxt.coinbase({"enableRateLimit": True})
        ticker = ex.fetch_ticker(ccxt_sym)
        last = ticker.get("last")
        return float(last) if last else None
    except Exception:
        return None


def _coingecko_spot(symbol: str) -> float | None:
    try:
        import requests
        base = symbol.upper().split("/")[0].split("-")[0]
        cg_id = _CG_IDS.get(base)
        if not cg_id:
            return None
        keys = _load_keys()
        api_key = keys.get("COINGECKO", {}).get("key", "")
        base_url = "https://api.coingecko.com/api/v3"
        headers = {"x-cg-demo-api-key": api_key} if api_key else {}
        r = requests.get(
            f"{base_url}/simple/price",
            params={"ids": cg_id, "vs_currencies": "usd"},
            headers=headers,
            timeout=5,
        )
        r.raise_for_status()
        return float(r.json()[cg_id]["usd"])
    except Exception:
        return None


def _alpaca_spot(symbol: str) -> float | None:
    try:
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
    except Exception:
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


# ── OHLCV adapters ─────────────────────────────────────────────────────────────

def _coinbase_ohlcv(symbol: str, timeframe: str, limit: int) -> pd.DataFrame:
    """Crypto OHLCV from Coinbase via ccxt. Resamples 4H and 1W from shorter bars."""
    try:
        import ccxt
        ccxt_sym = _to_ccxt_sym(symbol)
        resample_map = {"4h": ("2h", 2, "4h"), "1wk": ("1d", 7, "1W")}
        if timeframe in resample_map:
            fetch_tf, mult, resample_rule = resample_map[timeframe]
            fetch_limit = (limit + 50) * mult
        else:
            fetch_tf, fetch_limit, resample_rule = timeframe, limit + 50, None
        ex = ccxt.coinbase({"enableRateLimit": True})
        ohlcv = ex.fetch_ohlcv(ccxt_sym, fetch_tf, limit=fetch_limit)
        if not ohlcv:
            return pd.DataFrame()
        df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        df = df.sort_values("timestamp").drop_duplicates("timestamp").reset_index(drop=True)
        if resample_rule:
            df = (
                df.set_index("timestamp")
                .resample(resample_rule)
                .agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"})
                .dropna()
                .reset_index()
            )
        for col in ("open", "high", "low", "close", "volume"):
            df[col] = df[col].astype(float)
        return df[["timestamp", "open", "high", "low", "close", "volume"]].tail(limit).reset_index(drop=True)
    except Exception:
        return pd.DataFrame()


def _alpaca_ohlcv(symbol: str, timeframe: str, limit: int) -> pd.DataFrame:
    """Equity OHLCV from Alpaca Markets REST API."""
    try:
        import requests
        from datetime import datetime, timedelta
        keys = _load_keys()
        ak = keys.get("ALPACA_KEY", {}).get("key", "")
        sk = keys.get("ALPACA_SECRET", {}).get("key", "")
        if not ak or not sk:
            return pd.DataFrame()
        tf_map = {"1h": "1Hour", "4h": "4Hour", "1d": "1Day", "1wk": "1Week"}
        alpaca_tf = tf_map.get(timeframe)
        if not alpaca_tf:
            return pd.DataFrame()
        start = (datetime.utcnow() - timedelta(days=limit + 60)).strftime("%Y-%m-%d")
        r = requests.get(
            f"https://data.alpaca.markets/v2/stocks/{symbol}/bars",
            headers={"APCA-API-KEY-ID": ak, "APCA-API-SECRET-KEY": sk},
            params={"timeframe": alpaca_tf, "start": start, "limit": limit, "adjustment": "raw"},
            timeout=10,
        )
        r.raise_for_status()
        bars = r.json().get("bars", [])
        if not bars:
            return pd.DataFrame()
        df = pd.DataFrame(bars).rename(
            columns={"t": "timestamp", "o": "open", "h": "high", "l": "low", "c": "close", "v": "volume"}
        )
        df["timestamp"] = pd.to_datetime(df["timestamp"]).dt.tz_convert("UTC").dt.tz_localize(None)
        for col in ("open", "high", "low", "close", "volume"):
            df[col] = df[col].astype(float)
        return df[["timestamp", "open", "high", "low", "close", "volume"]].reset_index(drop=True)
    except Exception:
        return pd.DataFrame()


def _yfinance_ohlcv(symbol: str, timeframe: str, limit: int) -> pd.DataFrame:
    """Universal OHLCV fallback via yfinance."""
    try:
        import yfinance as yf
        yf_intervals = {
            "1wk": ("1wk", "10y"), "1d": ("1d", "2y"),
            "4h":  ("1h",  "730d"), "1h": ("1h", "60d"), "15m": ("15m", "60d"),
        }
        if timeframe not in yf_intervals:
            return pd.DataFrame()
        interval, period = yf_intervals[timeframe]
        hist = yf.Ticker(symbol).history(period=period, interval=interval)
        if hist.empty:
            return pd.DataFrame()
        hist = hist.reset_index()
        hist.columns = [c.lower() for c in hist.columns]
        ts_col = "date" if "date" in hist.columns else "datetime"
        hist = hist.rename(columns={ts_col: "timestamp"})
        hist["timestamp"] = pd.to_datetime(hist["timestamp"]).dt.tz_localize(None)
        hist = hist[["timestamp", "open", "high", "low", "close", "volume"]]
        if timeframe == "4h":
            hist = (
                hist.set_index("timestamp")
                .resample("4h")
                .agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"})
                .dropna()
                .reset_index()
            )
        for col in ("open", "high", "low", "close", "volume"):
            hist[col] = hist[col].astype(float)
        return hist[["timestamp", "open", "high", "low", "close", "volume"]].tail(limit).reset_index(drop=True)
    except Exception:
        return pd.DataFrame()


_OHLCV_FNS: dict = {
    "coinbase": _coinbase_ohlcv,
    "alpaca":   _alpaca_ohlcv,
    "yfinance": _yfinance_ohlcv,
}
_OHLCV_CRYPTO = ["coinbase", "yfinance"]
_OHLCV_EQUITY = ["alpaca", "yfinance"]


def _fetch_ohlcv_impl(symbol: str, timeframe: str, limit: int) -> pd.DataFrame:
    """Shared implementation — routes through provider chain."""
    chain = _OHLCV_CRYPTO if _asset_class(symbol) == "crypto" else _OHLCV_EQUITY
    for name in _by_speed(chain):
        fn = _OHLCV_FNS[name]
        try:
            t0 = time.monotonic()
            df = fn(symbol, timeframe, limit)
            if df is not None and not df.empty:
                _record_latency(name, (time.monotonic() - t0) * 1000)
                return df
        except Exception:
            pass
    return pd.DataFrame()


@ttl_cache(ttl=14400)
def _fetch_ohlcv_daily(symbol: str, timeframe: str, limit: int) -> pd.DataFrame:
    return _fetch_ohlcv_impl(symbol, timeframe, limit)


@ttl_cache(ttl=900)
def _fetch_ohlcv_intraday(symbol: str, timeframe: str, limit: int) -> pd.DataFrame:
    return _fetch_ohlcv_impl(symbol, timeframe, limit)


def fetch_ohlcv(symbol: str, timeframe: str, limit: int = 300) -> pd.DataFrame:
    """OHLCV via fastest available provider. Daily/weekly: 4h cache. Intraday: 15m cache."""
    if timeframe in ("1d", "1wk"):
        return _fetch_ohlcv_daily(symbol, timeframe, limit).copy()
    return _fetch_ohlcv_intraday(symbol, timeframe, limit).copy()


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
        price = _coingecko_spot("BTC")
        if price:
            _record_latency("coingecko", (time.monotonic() - t0) * 1000)
    except Exception:
        pass
    return {"price": price, "speed": get_speed_report()}
