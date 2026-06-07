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
import numpy as np
import ccxt
import time
from pathlib import Path
from datetime import datetime, timedelta, timezone
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

def load_providers() -> dict:
    """Load saved API keys from disk. Returns empty dict if none are saved."""
    if KEYS_FILE.exists():
        try:
            with open(KEYS_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_providers(providers: dict):
    """Write API keys to disk. Called when the user adds/removes keys in the sidebar."""
    with open(KEYS_FILE, "w") as f:
        json.dump(providers, f, indent=2)


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

# ─────────────────────────────────────────────────────────────────
# 3. CRYPTO DATA FETCHERS (COINBASE/BINANCE)
# ─────────────────────────────────────────────────────────────────

# We initialize these locally as needed, since ccxt objects shouldn't be cached.
def _get_coinbase():
    return ccxt.coinbase({"enableRateLimit": True})

def _get_binance_futures():
    return ccxt.binanceusdm({"enableRateLimit": True})

@ttl_cache(ttl=900)
def fetch_crypto_ohlcv(symbol: str, timeframe: str, limit: int = 300) -> tuple[pd.DataFrame, str | None]:
    """
    Fetch Crypto OHLCV (Open, High, Low, Close, Volume) data from Coinbase.
    Returns the dataframe and an optional error message (if it falls back).
    Timeframes supported by our system: "1h", "4h", "1d", "1wk".
    """
    # Map our timeframes to ccxt's native ones or fetch a smaller one to resample 
    resample_map = {"4h": ("2h", 2, "4h"), "1wk": ("1d", 7, "1W")}
    if timeframe in resample_map:
        fetch_tf, mult, resample_rule = resample_map[timeframe]
        fetch_limit = (limit + 50) * mult
    else:
        fetch_tf, fetch_limit, resample_rule = timeframe, limit + 50, None
        
    coinbase_error = None
    try:
        exchange = _get_coinbase()
        ohlcv = exchange.fetch_ohlcv(symbol, fetch_tf, limit=fetch_limit)
        time.sleep(0.2) # Polite rate sleep
        
        if ohlcv:
            df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
            df = df.sort_values("timestamp").drop_duplicates("timestamp").reset_index(drop=True)

            if resample_rule:
                # Combine shorter bars into the requested timeframe (e.g. 2h into 4h)
                df = (
                    df.set_index("timestamp")
                    .resample(resample_rule)
                    .agg({"open": "first", "high": "max", "low": "min",
                          "close": "last", "volume": "sum"})
                    .dropna()
                    .reset_index()
                )
            return df.reset_index(drop=True), None
    except Exception as e:
        coinbase_error = str(e)
        
    # SILENT FALLBACK to Yahoo Finance if Coinbase is down
    print(f"Coinbase failed for {symbol}: {coinbase_error}. Trying YF...", file=sys.stderr)
    yf_symbol = symbol.split("/")[0] + "-USD"
    yf_intervals = {"1wk": ("1wk","10y"), "1d": ("1d","2y"), "4h": ("1h","730d"), "1h": ("1h", "60d"), "15m": ("15m", "60d")}
    if timeframe in yf_intervals:
        interval, period = yf_intervals[timeframe]
        hist = fetch_yf_history(yf_symbol, period, interval)
        if not hist.empty:
            # Reformat to match the Coinbase columns
            hist = hist.reset_index()
            hist.columns = [c.lower() for c in hist.columns]
            ts_col = "date" if "date" in hist.columns else "datetime"
            hist = hist.rename(columns={ts_col: "timestamp"})
            hist["timestamp"] = pd.to_datetime(hist["timestamp"]).dt.tz_localize(None)
            hist = hist[["timestamp", "open", "high", "low", "close", "volume"]]
            
            # Resample 1H to 4H manually
            if timeframe == "4h":
                hist = (hist.set_index("timestamp").resample("4h")
                        .agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"})
                        .dropna().reset_index())
                
            return hist, "Coinbase failed, using Yahoo Finance fallback."
            
    # LAST RESORT: TV extracted local JSON files (offline fallback; useful for pairs like ETH/BTC with no YF equivalent)
    print(f"YF also failed for {symbol}. Trying TV local files...", file=sys.stderr)
    tv_df = _load_sd_tv_ohlcv(symbol, timeframe)
    if not tv_df.empty:
        return tv_df.tail(limit).reset_index(drop=True), "Coinbase + YF failed; using TV extracted data (may be stale)."

    return pd.DataFrame(), "Coinbase, Yahoo Finance, and TV local files all failed."

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
