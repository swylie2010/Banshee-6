"""
shared_data.py — Banshee Pro Shared Data & Cache Utility
========================================================
Unified data fetchers shared by macro_engine and micro_engine.
All functions are cached via ttl_cache (process-level TTL dict) so neither
engine duplicates API calls. No Streamlit dependency.
"""

import json
import sys
import yfinance as yf
import pandas as pd
import ccxt
import time
from pathlib import Path
from cache_utils import ttl_cache

# TV-extracted OHLCV fallback — local JSON files written by Claude via TradingView MCP.
# Only used as last resort when both Coinbase and Yahoo Finance fail (e.g. ETH/BTC has no YF equivalent).
_SD_TV_OHLCV_DIR = Path(__file__).parent / "tv_extract" / "ohlcv"
_SD_TV_SYMBOL_MAP = {
    "ETH/BTC": "ETHBTC",
    "ETH-BTC": "ETHBTC",
}
_SD_TV_TF_MAP = {"1wk": "1W", "1d": "1D", "4h": "4H", "1h": "1H"}

def _load_sd_tv_ohlcv(symbol: str, timeframe: str) -> pd.DataFrame:
    """Load most recent TV-extracted OHLCV JSON for symbol/timeframe. Returns empty df on miss."""
    import glob as _glob
    prefix = _SD_TV_SYMBOL_MAP.get(symbol) or _SD_TV_SYMBOL_MAP.get(symbol.upper())
    tf_suffix = _SD_TV_TF_MAP.get(timeframe)
    if not prefix or not tf_suffix:
        return pd.DataFrame()
    files = sorted(_glob.glob(str(_SD_TV_OHLCV_DIR / f"{prefix}_{tf_suffix}_*.json")))
    if not files:
        return pd.DataFrame()
    with open(files[-1]) as f:
        data = json.load(f)
    bars = data.get("bars", [])
    if not bars:
        return pd.DataFrame()
    df = pd.DataFrame(bars)
    df["timestamp"] = pd.to_datetime(df["time"], unit="s", utc=True).dt.tz_localize(None)
    return df[["timestamp", "open", "high", "low", "close", "volume"]].sort_values("timestamp").reset_index(drop=True)

# ─────────────────────────────────────────────────────────────────
# 1. API KEY MANAGEMENT
# ─────────────────────────────────────────────────────────────────
# All keys (Claude, Gemini, FRED) are saved in the user's home folder.
# This prevents them from accidentally being shared if the code is moved.
KEYS_FILE = Path.home() / ".banshee_keys.json"

_providers_cache: dict | None = None
_providers_cache_ts: float = 0.0
_PROVIDERS_TTL = 60.0

def load_providers() -> dict:
    """Load saved API keys from disk. Cached for 60 s to avoid per-request disk reads."""
    global _providers_cache, _providers_cache_ts
    if _providers_cache is not None and time.time() - _providers_cache_ts < _PROVIDERS_TTL:
        return _providers_cache
    result: dict = {}
    if KEYS_FILE.exists():
        try:
            with open(KEYS_FILE, "r") as f:
                result = json.load(f)
            try:
                KEYS_FILE.chmod(0o600)
            except Exception:
                pass  # no-op on Windows NTFS; active on Linux/Hermes
        except Exception:
            pass
    _providers_cache = result
    _providers_cache_ts = time.time()
    return result

def save_providers(providers: dict):
    """Write API keys to disk and update the in-memory cache immediately."""
    global _providers_cache, _providers_cache_ts
    with open(KEYS_FILE, "w") as f:
        json.dump(providers, f, indent=2)
    try:
        KEYS_FILE.chmod(0o600)
    except Exception:
        pass  # no-op on Windows NTFS; active on Linux/Hermes
    _providers_cache = providers
    _providers_cache_ts = time.time()


# ─────────────────────────────────────────────────────────────────
# 2. MARKET DATA FETCHERS (YFINANCE)
# ─────────────────────────────────────────────────────────────────

@ttl_cache(ttl=900)
def fetch_yf_history(ticker: str, period: str, interval: str = "1d") -> pd.DataFrame:
    """
    Fetch price history from Yahoo Finance and cache it.
    Both the Macro engine (for SPY, VIX) and Micro engine (for stocks) use this.
    """
    try:
        # yfinance uses periods like '5d', '3mo', '2y' and intervals like '1d', '1h'
        df = yf.Ticker(ticker).history(period=period, interval=interval)
        return df if not df.empty else pd.DataFrame()
    except Exception as e:
        print(f"Error fetching YF history for {ticker}: {e}", file=sys.stderr)
        return pd.DataFrame()

@ttl_cache(ttl=900)
def fetch_yf_fast_info(ticker: str) -> float | None:
    """
    Fetch the last known price for a ticker quickly.
    Falls back to a 5-day history check if the fast info fails.
    """
    try:
        info = yf.Ticker(ticker).fast_info
        return info["last_price"]
    except Exception:
        # Fallback to fetching actual recent history
        hist = fetch_yf_history(ticker, period="5d", interval="1d")
        if not hist.empty and "Close" in hist.columns:
            return float(hist["Close"].iloc[-1])
        return None

def get_last_price(symbol: str) -> float | None:
    """Last known price via pluggable provider chain in data_providers. 60s cache lives there."""
    import data_providers  # lazy import breaks potential circular dep
    return data_providers.get_spot_price(symbol)

# ─────────────────────────────────────────────────────────────────
# 3. CRYPTO DATA FETCHERS (COINBASE/BINANCE)
# ─────────────────────────────────────────────────────────────────

# We initialize these locally as needed, since ccxt objects shouldn't be cached.
def _get_coinbase():
    return ccxt.coinbase({"enableRateLimit": True})

def _get_binance_futures():
    return ccxt.binanceusdm({"enableRateLimit": True})

def fetch_crypto_ohlcv(symbol: str, timeframe: str, limit: int = 300) -> tuple[pd.DataFrame, str | None]:
    """
    Fetch OHLCV via pluggable provider chain. TV local files are a last-resort fallback
    kept here (not in data_providers) to avoid a circular import.
    """
    import data_providers
    df = data_providers.fetch_ohlcv(symbol, timeframe, limit)
    if not df.empty:
        return df, None
    # Last resort: locally extracted TV JSON files (offline; useful for ETH/BTC etc.)
    try:
        tv_df = _load_sd_tv_ohlcv(symbol, timeframe)
        if not tv_df.empty:
            return tv_df.tail(limit).reset_index(drop=True), "Using TV extracted data (may be stale)."
    except Exception:
        pass
    return pd.DataFrame(), "All data providers failed."

@ttl_cache(ttl=900)
def fetch_funding_rate(symbol: str) -> float | None:
    """
    Fetch perpetual futures funding rate from Binance. Only applies to crypto.
    """
    if "/" not in symbol:
        return None
    try:
        base = symbol.split("/")[0]
        binance_symbol = f"{base}/USDT:USDT"
        exchange = _get_binance_futures()
        data = exchange.fetch_funding_rate(binance_symbol)
        rate = data.get("fundingRate", 0) or 0
        return float(rate) * 100
    except Exception:
        return None


@ttl_cache(ttl=14400)
def fetch_sector_closes() -> "pd.DataFrame":
    """
    Fetch ~3 months of daily closes for SPY + all 10 sector SPDRs.
    Returns DataFrame with DatetimeIndex, one column per ticker.

    Data-source adapter for sector_rotation_engine — yfinance today,
    swappable when the user supplies a different data source. The engine
    itself never calls yfinance; it receives this DataFrame.

    Cached 4 hours (14400s). First call takes 2-5s; subsequent calls instant.
    """
    tickers = ["SPY", "XLK", "XLY", "XLI", "XLB", "XLE", "XLF", "XLV", "XLP", "XLU", "XLRE"]
    try:
        raw = yf.download(
            tickers=tickers,
            period="3mo",
            interval="1d",
            auto_adjust=True,
            progress=False,
        )
        # yf.download with multiple tickers returns MultiIndex columns: (field, ticker)
        closes = raw["Close"].dropna(how="all")
        closes.index = pd.to_datetime(closes.index).tz_localize(None)
        return closes[tickers]  # consistent column order
    except Exception as e:
        print(f"[fetch_sector_closes] yfinance failed: {e}", file=sys.stderr)
        return pd.DataFrame()
