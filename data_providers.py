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
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd

from cache_utils import ttl_cache


# ── Key loading (direct — no import from shared_data to avoid circular dep) ───

_KEYS_FILE = Path.home() / ".banshee_keys.json"

_keys_cache: dict = {}
_keys_cache_ts: float = 0.0
_KEYS_TTL = 30.0


def _load_keys() -> dict:
    global _keys_cache, _keys_cache_ts
    if _keys_cache and time.monotonic() - _keys_cache_ts < _KEYS_TTL:
        return _keys_cache
    try:
        _keys_cache = json.loads(_KEYS_FILE.read_text())
    except Exception:
        _keys_cache = {}
    _keys_cache_ts = time.monotonic()
    return _keys_cache


def _is_enabled(name: str, asset_class: str) -> bool:
    """Return True if this provider is enabled for the given asset class."""
    keys = _load_keys()
    if name == "coinbase":
        return bool(keys.get("COINBASE", {}).get("enabled", False)) and asset_class == "crypto"
    if name == "alpaca":
        return bool(keys.get("ALPACA_KEY", {}).get("key")) and bool(keys.get("ALPACA_KEY", {}).get("enabled", False))
    if name == "coingecko":
        return bool(keys.get("COINGECKO", {}).get("enabled", False)) and asset_class == "crypto"
    if name == "yfinance":
        return bool(keys.get("YFINANCE", {}).get("enabled", False))
    if name == "custom":
        c = keys.get("CUSTOM_DATA", {})
        if not c.get("enabled", False) or not c.get("base_url"):
            return False
        ac = c.get("asset_class", "both")
        return ac == "both" or ac == asset_class
    return False


def _active_chain(call_type: str, asset_class: str) -> list[str]:
    """Return speed-ordered list of enabled provider names for this call type + asset class."""
    candidates = {
        "spot":  {"crypto": ["coinbase", "coingecko", "custom", "yfinance"],
                  "equity": ["alpaca", "custom", "yfinance"]},
        "ohlcv": {"crypto": ["coinbase", "custom", "yfinance"],
                  "equity": ["alpaca", "custom", "yfinance"]},
    }[call_type][asset_class]
    return _by_speed([n for n in candidates if _is_enabled(n, asset_class)])


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
    "custom":    deque(maxlen=10),
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
        cg = keys.get("COINGECKO", {})
        api_key = cg.get("key", "")
        if api_key and cg.get("key_type") == "pro":
            base_url = "https://pro-api.coingecko.com/api/v3"
            headers = {"x-cg-pro-api-key": api_key}
        elif api_key:
            base_url = "https://api.coingecko.com/api/v3"
            headers = {"x-cg-demo-api-key": api_key}
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
    if "/" in symbol:
        symbol = symbol.replace("/", "-")   # BTC/USD -> BTC-USD for yfinance
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


def _custom_spot(symbol: str) -> float | None:
    try:
        keys = _load_keys()
        c = keys.get("CUSTOM_DATA", {})
        if not c.get("base_url"):
            return None
        import requests as _req
        r = _req.get(
            f"{c['base_url'].rstrip('/')}/spot",
            params={"symbol": symbol, "apikey": c.get("api_key", "")},
            timeout=5,
        )
        r.raise_for_status()
        price = r.json().get("price")
        return float(price) if price else None
    except Exception:
        return None


_SPOT_FNS: dict = {
    "coinbase":  _coinbase_spot,
    "coingecko": _coingecko_spot,
    "alpaca":    _alpaca_spot,
    "yfinance":  _yfinance_spot,
    "custom":    _custom_spot,
}


@ttl_cache(ttl=60, skip_none=True)
def get_spot_price(symbol: str) -> float | None:
    """Last known price via the fastest available provider. 60s cache."""
    chain = _active_chain("spot", _asset_class(symbol))
    for name in chain:
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
    if "/" in symbol:
        symbol = symbol.replace("/", "-")   # BTC/USD -> BTC-USD for yfinance
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


def _custom_ohlcv(symbol: str, timeframe: str, limit: int) -> pd.DataFrame:
    try:
        keys = _load_keys()
        c = keys.get("CUSTOM_DATA", {})
        if not c.get("base_url"):
            return pd.DataFrame()
        import requests as _req
        r = _req.get(
            f"{c['base_url'].rstrip('/')}/ohlcv",
            params={"symbol": symbol, "timeframe": timeframe,
                    "limit": limit, "apikey": c.get("api_key", "")},
            timeout=10,
        )
        r.raise_for_status()
        bars = r.json().get("bars", [])
        if not bars:
            return pd.DataFrame()
        df = pd.DataFrame(bars)
        df["timestamp"] = pd.to_datetime(df["timestamp"]).dt.tz_localize(None)
        for col in ("open", "high", "low", "close", "volume"):
            df[col] = df[col].astype(float)
        return df[["timestamp", "open", "high", "low", "close", "volume"]].tail(limit).reset_index(drop=True)
    except Exception:
        return pd.DataFrame()


_OHLCV_FNS: dict = {
    "coinbase": _coinbase_ohlcv,
    "alpaca":   _alpaca_ohlcv,
    "yfinance": _yfinance_ohlcv,
    "custom":   _custom_ohlcv,
}


# ── Depth rank (for fast-then-complete Stage 2) ────────────────────────────────
# How much OHLCV history a provider can return. "deep" sources return long history
# (yfinance ~2y, Alpaca long, custom assumed-deep); shallow sources are per-request
# capped (Coinbase ~300, no pagination). coingecko is spot-only in our integration
# and is intentionally absent → never an OHLCV deep candidate.
_DEPTH_RANK: dict[str, int] = {
    "yfinance": 3,
    "alpaca":   3,
    "custom":   2,   # user's own source — assume deep; pick-best sorts it out
    "coinbase": 1,   # shallow, per-request cap
}


def _deep_chain(asset_class: str, exclude: str | None = None, cap: int = 3) -> list[str]:
    """Enabled, OHLCV-capable providers ranked by history depth (deepest first),
    excluding `exclude` (the provider Stage 1 already used), capped at `cap`.
    Empty when nothing deeper than the fast source is available (the no-op path)."""
    names = [
        n for n in _DEPTH_RANK
        if n != exclude and n in _OHLCV_FNS and _is_enabled(n, asset_class)
    ]
    names.sort(key=lambda n: _DEPTH_RANK[n], reverse=True)
    return names[:cap]


_DEEP_POLL_TIMEOUT = 6.0   # seconds — bounded wall-clock for the Stage-2 background poll


def _deep_fetch_one(name: str, symbol: str, timeframe: str, limit: int):
    """Fetch one deep provider, timing it. Records latency only on a non-empty result."""
    fn = _OHLCV_FNS[name]
    t0 = time.monotonic()
    df = fn(symbol, timeframe, limit)
    if df is not None and not df.empty:
        _record_latency(name, (time.monotonic() - t0) * 1000)
    return name, df


def fetch_ohlcv_deep(symbol: str, timeframe: str, limit: int) -> pd.DataFrame:
    """Fast-then-complete Stage 2: poll the deep providers in parallel and return the
    freshest-then-deepest OHLCV frame. Excludes the fastest provider (Stage 1 already
    returned it). Returns an empty DataFrame when nothing deeper/fresher is available."""
    asset_class = _asset_class(symbol)
    fast_chain  = _active_chain("ohlcv", asset_class)
    fast        = fast_chain[0] if fast_chain else None
    deep_names  = _deep_chain(asset_class, exclude=fast)
    if not deep_names:
        return pd.DataFrame()

    results: list[tuple[str, pd.DataFrame]] = []
    with ThreadPoolExecutor(max_workers=len(deep_names)) as ex:
        futs = {ex.submit(_deep_fetch_one, n, symbol, timeframe, limit): n
                for n in deep_names}
        try:
            for fut in as_completed(futs, timeout=_DEEP_POLL_TIMEOUT):
                try:
                    _name, df = fut.result()
                    if df is not None and not df.empty:
                        results.append((_name, df))
                except Exception:
                    pass
        except TimeoutError:
            pass   # take whatever finished inside the budget

    if not results:
        return pd.DataFrame()
    # freshest last bar, then most bars
    best = max(results, key=lambda r: (r[1]["timestamp"].iloc[-1], len(r[1])))
    return best[1]


def _fetch_ohlcv_impl(symbol: str, timeframe: str, limit: int) -> pd.DataFrame:
    """Shared implementation — routes through provider chain."""
    chain = _active_chain("ohlcv", _asset_class(symbol))
    for name in chain:
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


def has_capability(capability: str) -> bool:
    """True if any currently-enabled provider declares this capability."""
    keys = _load_keys()
    _CAPS = {
        "coinbase":  {"spot", "ohlcv"},
        "alpaca":    {"spot", "ohlcv"},
        "coingecko": {"spot"},
        "yfinance":  {"spot", "ohlcv", "options_chain", "earnings_calendar"},
        "custom":    set(keys.get("CUSTOM_DATA", {}).get("capabilities", [])),
    }
    for name, caps in _CAPS.items():
        if capability not in caps:
            continue
        for ac in ("crypto", "equity", "both"):
            if _is_enabled(name, ac):
                return True
    return False


def get_speed_report() -> dict:
    """Return latency summary for all providers including enabled state."""
    result = {}
    for name in ("coinbase", "alpaca", "coingecko", "yfinance", "custom"):
        avg = _mean_latency(name)
        samples = len(_latency.get(name, []))
        enabled = any(_is_enabled(name, ac) for ac in ("crypto", "equity"))
        result[name] = {
            "avg_ms": round(avg) if avg != float("inf") else None,
            "samples": samples,
            "tier": _tier(avg),
            "enabled": enabled,
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


def probe_custom_latency() -> dict:
    """Fire a timed custom provider spot fetch to populate latency data."""
    t0 = time.monotonic()
    price = None
    try:
        price = _custom_spot("BTC")
        if price:
            _record_latency("custom", (time.monotonic() - t0) * 1000)
    except Exception:
        pass
    return {"price": price, "speed": get_speed_report()}
