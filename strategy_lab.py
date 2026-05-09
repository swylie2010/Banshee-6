"""
strategy_lab.py — Strategy Lab for Banshee Pro 2
STRATLAB-A: Strategy Persistence (save/load to strategies.json)
STRATLAB-B: Comparative Runs (multi-TF/lookback table in one click)
"""
from __future__ import annotations

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import json
import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# ─── Strategy Persistence ─────────────────────────────────────────────────────

STRATEGIES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "strategies.json")


def _load_strategies() -> dict:
    """Return dict of {name: strategy_data} from strategies.json."""
    if not os.path.exists(STRATEGIES_FILE):
        return {}
    try:
        with open(STRATEGIES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_strategy(name: str, data: dict) -> None:
    """Upsert one strategy into strategies.json (keyed by name)."""
    strategies = _load_strategies()
    # Strip non-serialisable fields (plotly figures, DataFrames)
    clean = {k: v for k, v in data.items() if k not in ("equity_fig", "trade_log")}
    clean["saved_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    strategies[name] = clean
    with open(STRATEGIES_FILE, "w", encoding="utf-8") as f:
        json.dump(strategies, f, indent=2, default=str)


def _delete_strategy(name: str) -> None:
    """Remove a strategy from strategies.json."""
    strategies = _load_strategies()
    if name in strategies:
        del strategies[name]
        with open(STRATEGIES_FILE, "w", encoding="utf-8") as f:
            json.dump(strategies, f, indent=2, default=str)


def _delete_all_strategies() -> None:
    """Wipe all entries from strategies.json."""
    with open(STRATEGIES_FILE, "w", encoding="utf-8") as f:
        json.dump({}, f, indent=2)

# ─── Saved Results Viewer ─────────────────────────────────────────────────────

def render_saved_results() -> None:
    st.markdown("## 📊 Saved Results")
    strategies = _load_strategies()

    if not strategies:
        st.info("No saved results yet. Run a backtest in Strategy Lab and hit 💾 Save Result.")
        return

    # ── Build summary rows ────────────────────────────────────────────────────
    rows = []
    for name, data in strategies.items():
        stats = data.get("stats", {})
        rows.append({
            "Name": name,
            "Symbol": data.get("symbol", "—"),
            "Timeframe": data.get("timeframe", "—"),
            "Lookback": data.get("lookback", "—"),
            "Type": data.get("type", "custom"),
            "Return": stats.get("total_return", data.get("total_return", "—")),
            "vs B&H": stats.get("bnh_return", "—"),
            "Alpha": stats.get("alpha", "—"),
            "Win Rate": stats.get("win_rate", "—"),
            "Trades": stats.get("n_trades", "—"),
            "Max DD": stats.get("max_dd", "—"),
            "Sharpe": stats.get("sharpe", "—"),
            "Saved": data.get("saved_at", "—"),
        })

    df = pd.DataFrame(rows)

    # ── Filters ───────────────────────────────────────────────────────────────
    col_f1, col_f2, col_f3 = st.columns([2, 2, 2])
    with col_f1:
        sym_filter = st.text_input("Filter by symbol", placeholder="e.g. BTC")
    with col_f2:
        type_options = ["All"] + sorted(df["Type"].unique().tolist())
        type_filter = st.selectbox("Filter by type", type_options)
    with col_f3:
        min_trades_on = st.checkbox(
            "Hide thin samples (< 15 trades)",
            value=True,
            help="Hides results with fewer than 15 trades — small samples produce unreliable Sharpe numbers.",
        )

    filtered = df.copy()
    if sym_filter:
        filtered = filtered[filtered["Symbol"].str.contains(sym_filter, case=False, na=False)]
    if type_filter != "All":
        filtered = filtered[filtered["Type"] == type_filter]
    if min_trades_on:
        def _parse_trades(val):
            try:
                return int(str(val))
            except (ValueError, TypeError):
                return 0
        filtered = filtered[filtered["Trades"].apply(_parse_trades) >= 15]

    st.markdown(f"**{len(filtered)} result(s)**")

    # ── Colour-code Return column ─────────────────────────────────────────────
    def _color_val(val):
        if isinstance(val, str) and val.startswith("+"):
            return "color: #2ecc71; font-weight: bold"
        if isinstance(val, str) and val.startswith("-"):
            return "color: #e74c3c; font-weight: bold"
        return ""

    styled = filtered.style.applymap(_color_val, subset=["Return", "Alpha", "vs B&H"])
    st.dataframe(styled, width="stretch", hide_index=True)

    st.markdown("---")
    st.markdown("### Inspect / Delete")

    selected_name = st.selectbox("Select a result to inspect or delete", ["— select —"] + list(strategies.keys()))

    if selected_name and selected_name != "— select —":
        data = strategies[selected_name]
        stats = data.get("stats", {})

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Return", stats.get("total_return", data.get("total_return", "—")))
        c2.metric("vs B&H", stats.get("bnh_return", "—"))
        c3.metric("Alpha", stats.get("alpha", "—"))
        c4.metric("Win Rate", stats.get("win_rate", "—"))

        d1, d2, d3, d4 = st.columns(4)
        d1.metric("Trades", stats.get("n_trades", "—"))
        d2.metric("Max DD", stats.get("max_dd", "—"))
        d3.metric("Sharpe", stats.get("sharpe", "—"))
        presignal = stats.get("presignal_count", "—")
        presignal_pct = stats.get("presignal_pct", "")
        d4.metric("Pre-Signal", f"{presignal} ({presignal_pct})" if presignal_pct else str(presignal))

        with st.expander("Full record (raw JSON)"):
            st.json(data)

        st.markdown("---")
        if st.button(f"🗑 Delete '{selected_name}'", type="secondary"):
            _delete_strategy(selected_name)
            st.success(f"Deleted '{selected_name}'.")
            st.rerun()

    st.markdown("---")
    st.markdown("### Danger Zone")
    if not st.session_state.get("confirm_delete_all"):
        if st.button("🗑 Delete All Results", type="secondary"):
            st.session_state["confirm_delete_all"] = True
            st.rerun()
    else:
        st.warning(f"This will permanently delete **all {len(strategies)} saved result(s)**. Are you sure?")
        col_yes, col_no = st.columns([1, 3])
        with col_yes:
            if st.button("Yes, delete all", type="primary"):
                _delete_all_strategies()
                st.session_state["confirm_delete_all"] = False
                st.success("All results deleted.")
                st.rerun()
        with col_no:
            if st.button("Cancel"):
                st.session_state["confirm_delete_all"] = False
                st.rerun()


# ─── Constants ────────────────────────────────────────────────────────────────

INDICATORS = [
    "EMA 50 vs EMA 200",
    "RSI",
    "Stoch RSI (K vs D)",
    "Supertrend Direction",
    "Price vs VWAP",
    "ADX",
    "BB Fast Position",
]

CONDITIONS = {
    "EMA 50 vs EMA 200":     ["crosses above", "crosses below", "is above", "is below"],
    "RSI":                   ["< (oversold)", "> (overbought)", "crosses above", "crosses below"],
    "Stoch RSI (K vs D)":   ["K crosses above D", "K crosses below D", "K < 20", "K > 80"],
    "Supertrend Direction":  ["turns bullish", "turns bearish", "is bullish", "is bearish"],
    "Price vs VWAP":         ["crosses above", "crosses below", "is above", "is below"],
    "ADX":                   ["rises above", "falls below"],
    "BB Fast Position":      ["enters bull zone", "enters bear zone", "squeeze starts", "above fast upper", "below fast lower"],
}

# Conditions that take a numeric threshold value
VALUE_CONDITIONS = {
    "EMA 50 vs EMA 200":    [],
    "RSI":                  ["< (oversold)", "> (overbought)", "crosses above", "crosses below"],
    "Stoch RSI (K vs D)":  [],
    "Supertrend Direction": [],
    "Price vs VWAP":        [],
    "ADX":                  ["rises above", "falls below"],
    "BB Fast Position":     [],
}

# Default threshold values
DEFAULTS = {
    "RSI": 30,
    "ADX": 25,
}

TIMEFRAMES = ["15m", "1h", "4h", "1d", "1wk"]
LOOKBACKS  = ["6 months", "1 year", "2 years", "5 years"]

EXIT_MODES = [
    "ATR-based (1.5x stop / 3x target)",
    "Fixed %",
    "Opposing entry signal",
]

FREQ_MAP = {"15m": "15T", "1h": "1H", "4h": "4H", "1d": "D", "1wk": "W"}

# yfinance intraday history limits (calendar days).
# Exceeding these returns empty data with no useful error from yfinance.
_YF_INTERVAL_MAX_DAYS = {
    "1m": 7, "2m": 60, "5m": 60, "15m": 60, "30m": 60,
    "60m": 730, "1h": 730,
    "90m": 60,
    # Daily and above have no meaningful limit
    "1d": None, "5d": None, "1wk": None, "1mo": None, "3mo": None,
}
_LOOKBACK_DAYS = {
    "6 months": 183, "1 year": 365, "2 years": 730, "5 years": 1825,
}


def _check_yf_limits(interval: str, lookback: str):
    """Return an error string if the interval/lookback combo exceeds yfinance limits, else None."""
    max_days = _YF_INTERVAL_MAX_DAYS.get(interval)
    lb_days  = _LOOKBACK_DAYS.get(lookback, 365)
    if max_days and lb_days > max_days:
        return (
            f"yfinance only provides {interval} data for the last {max_days} days "
            f"(you selected '{lookback}' ≈ {lb_days} days). "
            f"Switch to a shorter lookback (≤ {max_days} days) or use a higher timeframe (1h, 4h, 1d)."
        )
    return None


# ─── Backtest engine ───────────────────────────────────────────────────────────

def _yf_symbol(symbol: str) -> str:
    """Convert 'BTC/USD' → 'BTC-USD' for yfinance."""
    return symbol.replace("/", "-")


def _is_crypto(symbol: str) -> bool:
    """Return True if the symbol looks like a crypto pair (BTC/USD, ETH-USD, etc.)."""
    return "/" in symbol or symbol.upper().endswith(("-USD", "-USDT", "-USDC"))


def _fetch_binance_ohlcv(symbol: str, timeframe: str, lookback: str):
    """
    Fetch OHLCV from Binance's public API. No API key required!

    Why Binance instead of yfinance for crypto intraday?
    - yfinance caps 15m data at 60 days — useless for a real 2-year backtest.
    - Binance has full history (2017–present) for 15m, 1h, 4h, and 1d.
    - No sign-up, no rate limits for this use case.

    Binance symbol format: BTC/USD → BTCUSDT (we try USDT, then USDC, then BUSD).
    Returns (df, error_str) — same contract as _fetch_backtest_data.
    """
    import urllib.request, urllib.error, json as _json

    # Binance uses different interval names than yfinance
    binance_interval = {"15m": "15m", "1h": "1h", "4h": "4h", "1d": "1d", "1wk": "1w"}
    bi = binance_interval.get(timeframe)
    if not bi:
        return pd.DataFrame(), f"Binance doesn't support timeframe '{timeframe}'."

    # How many calendar days to go back?
    lb_days = _LOOKBACK_DAYS.get(lookback, 365)

    # Extract the base coin (BTC from BTC/USD, ETH from ETH-USD, etc.)
    base = symbol.split("/")[0].split("-")[0].upper()
    quote_options = ["USDT", "USDC", "BUSD"]  # try most-liquid quote first

    for quote in quote_options:
        sym_bn   = f"{base}{quote}"
        all_rows = []
        # Binance timestamps are milliseconds since Unix epoch
        start_ms = int((pd.Timestamp.now() - pd.Timedelta(days=lb_days)).timestamp() * 1000)

        try:
            # Binance returns max 1000 candles per request — loop until we have all bars
            while True:
                url = (
                    f"https://api.binance.com/api/v3/klines"
                    f"?symbol={sym_bn}&interval={bi}&startTime={start_ms}&limit=1000"
                )
                with urllib.request.urlopen(url, timeout=12) as resp:
                    data = _json.loads(resp.read())

                if not data:
                    break
                all_rows.extend(data)
                # If fewer than 1000 returned, we've hit the current time
                if len(data) < 1000:
                    break
                # Advance start past the last returned candle (+ 1 ms to avoid overlap)
                start_ms = int(data[-1][0]) + 1

            if not all_rows:
                continue  # try next quote currency

            # Binance kline columns: [open_time, open, high, low, close, volume, ...]
            df = pd.DataFrame(all_rows, columns=[
                "timestamp", "open", "high", "low", "close", "volume",
                "close_time", "quote_vol", "n_trades",
                "taker_base", "taker_quote", "ignore",
            ])
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
            for col in ("open", "high", "low", "close", "volume"):
                df[col] = pd.to_numeric(df[col], errors="coerce")

            df = df[["timestamp", "open", "high", "low", "close", "volume"]].dropna().reset_index(drop=True)

            # 4h is not a native Binance interval when requested as 1h — resample
            if timeframe == "4h" and bi == "4h":
                # Binance DOES support 4h natively, so no resample needed — but
                # if we ever download 1h and need 4h, this block handles it:
                pass

            return df.reset_index(drop=True), None

        except urllib.error.HTTPError as e:
            if e.code == 400:
                # 400 = symbol not found on Binance — try next quote currency
                continue
            if e.code in (451, 403):
                # 451 = geo-block (common US restriction on Binance.com)
                # 403 = forbidden — both mean "not accessible from this region"
                return pd.DataFrame(), f"Binance is geo-blocked in this region (HTTP {e.code}). Falling back to yfinance."
            return pd.DataFrame(), f"Binance HTTP {e.code} for {sym_bn}: {e.reason}"
        except Exception as e:
            return pd.DataFrame(), f"Binance fetch failed ({sym_bn}): {e}"

    return pd.DataFrame(), (
        f"'{symbol}' not found on Binance (tried {base}USDT / {base}USDC / {base}BUSD). "
        "If this is a stock symbol, use the standard backtest (yfinance)."
    )


def _fetch_alpaca_ohlcv(symbol: str, timeframe: str, lookback: str):
    """
    Fetch OHLCV from Alpaca for stocks (SPY, NVDA, etc.).
    Requires ALPACA_KEY and ALPACA_SECRET saved in ~/.banshee_keys.json via Settings.
    Returns (df, error_str) — same contract as _fetch_binance_ohlcv.
    """
    try:
        from alpaca.data.historical import StockHistoricalDataClient
        from alpaca.data.requests import StockBarsRequest
        from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
        from alpaca.data.enums import Adjustment
    except ImportError:
        return pd.DataFrame(), "alpaca-py not installed. Run: pip install alpaca-py"

    from shared_data import load_providers
    providers = load_providers()
    api_key = providers.get("ALPACA_KEY", {}).get("key", "")
    secret  = providers.get("ALPACA_SECRET", {}).get("key", "")
    if not api_key or not secret:
        return pd.DataFrame(), "Alpaca keys not configured. Add them in ⚙️ Settings."

    tf_map = {
        "15m": TimeFrame(15, TimeFrameUnit.Minute),
        "1h":  TimeFrame(1,  TimeFrameUnit.Hour),
        "4h":  TimeFrame(4,  TimeFrameUnit.Hour),
        "1d":  TimeFrame(1,  TimeFrameUnit.Day),
    }
    if timeframe not in tf_map:
        return pd.DataFrame(), f"Alpaca: unsupported timeframe {timeframe}"

    days_map = {"6 months": 183, "1 year": 365, "2 years": 730, "5 years": 1825}
    days  = days_map.get(lookback, 365)
    start = datetime.utcnow() - timedelta(days=days)

    # Strip any crypto suffixes — Alpaca expects plain tickers like SPY, NVDA
    clean = symbol.upper().split("/")[0].replace("-USD", "").replace("-USDT", "")

    try:
        client  = StockHistoricalDataClient(api_key, secret)
        request = StockBarsRequest(symbol_or_symbols=clean, timeframe=tf_map[timeframe], start=start,
                                   adjustment=Adjustment.ALL)
        bars    = client.get_stock_bars(request)
        df_raw  = bars.df
        if df_raw.empty:
            return pd.DataFrame(), f"Alpaca returned no data for {clean} ({timeframe}, {lookback})."
        # bars.df has a MultiIndex (symbol, timestamp) — drop the symbol level
        if isinstance(df_raw.index, pd.MultiIndex):
            df_raw = df_raw.reset_index(level=0, drop=True).reset_index()
        else:
            df_raw = df_raw.reset_index()
        df_raw.columns = [str(c).lower() for c in df_raw.columns]
        ts_col = next((c for c in df_raw.columns if "time" in c or "date" in c), df_raw.columns[0])
        df = df_raw.rename(columns={ts_col: "timestamp"})[["timestamp", "open", "high", "low", "close", "volume"]].copy()
        df["timestamp"] = pd.to_datetime(df["timestamp"]).dt.tz_localize(None)
        df = df.sort_values("timestamp").reset_index(drop=True)
        return df, None
    except Exception as e:
        return pd.DataFrame(), f"Alpaca error for {clean}: {e}"


# ─── TV OHLCV LOCAL FILE TIER ─────────────────────────────────────────────────
# TV-extracted files live in tv_extract/ohlcv/ and are the highest-fidelity source
# (same data as calibration ground truth). Used when available and sufficient.

_TV_OHLCV_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tv_extract", "ohlcv")

_TV_SYMBOL_MAP = {
    "BTC/USD":   "BTCUSD",
    "BTC-USD":   "BTCUSD",
    "ETH/USD":   "ETHUSD",
    "ETH-USD":   "ETHUSD",
    "ETH/BTC":   "ETHBTC",
    "ETH-BTC":   "ETHBTC",
    "PAXG/USD":  "PAXGUSDC",
    "PAXG-USD":  "PAXGUSDC",
    "SOL/USD":   "SOLUSD",
    "SOL/USDT":  "SOLUSDT",
    "NVDA":      "NVDA",
    "SPY":       "SPY",
}

_TV_TF_MAP = {
    "1wk": "1W",
    "1d":  "1D",
    "4h":  "4H",
    "1h":  "1H",
}

# Minimum bars expected per lookback × timeframe combo.
# TV file is only used when it can supply ≥80% of this count after filtering.
# Crypto 4H/1H cells are large because crypto trades 24/7; stocks are ~250 days/yr.
_EXPECTED_BARS = {
    "2 years": {"1wk": 104, "1d": 500,  "4h": 2000, "1h": 4000},
    "5 years": {"1wk": 260, "1d": 1250, "4h": 5000, "1h": 10000},
    "1 year":  {"1wk": 52,  "1d": 250,  "4h": 1000, "1h": 2000},
    "6 months":{"1wk": 26,  "1d": 125,  "4h": 500,  "1h": 1000},
}


def _load_tv_ohlcv(symbol: str, timeframe: str):
    """
    Try to load the most recent TV-extracted OHLCV file for symbol/timeframe.
    Returns (df, None) on success, (empty_df, reason_str) on miss.

    Timestamps are returned tz-naive UTC to match the yfinance/Binance output format.
    """
    import glob
    prefix = _TV_SYMBOL_MAP.get(symbol.upper(), _TV_SYMBOL_MAP.get(symbol))
    if not prefix:
        return pd.DataFrame(), f"No TV file mapping for {symbol}"
    tf_suffix = _TV_TF_MAP.get(timeframe)
    if not tf_suffix:
        return pd.DataFrame(), f"No TV file mapping for timeframe {timeframe}"

    pattern = os.path.join(_TV_OHLCV_DIR, f"{prefix}_{tf_suffix}_[0-9]*.json")
    matches = [f for f in glob.glob(pattern) if "META" not in f]
    if not matches:
        return pd.DataFrame(), f"No TV file for {symbol} {timeframe}"

    latest = sorted(matches)[-1]
    try:
        with open(latest, encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        return pd.DataFrame(), f"TV file read error: {e}"

    bars = data.get("bars", [])
    if not bars:
        return pd.DataFrame(), f"TV file has no bars: {os.path.basename(latest)}"

    df = pd.DataFrame(bars)
    df.rename(columns={"time": "timestamp"}, inplace=True)
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="s", utc=True).dt.tz_convert(None)
    df = df[["timestamp", "open", "high", "low", "close", "volume"]].sort_values("timestamp").reset_index(drop=True)
    return df, None


def _apply_lookback_filter(df: pd.DataFrame, lookback: str) -> pd.DataFrame:
    """Trim df to the requested lookback period measured back from the last bar."""
    delta_map = {
        "6 months": pd.DateOffset(months=6),
        "1 year":   pd.DateOffset(years=1),
        "2 years":  pd.DateOffset(years=2),
        "5 years":  pd.DateOffset(years=5),
    }
    delta = delta_map.get(lookback)
    if delta is None or df.empty:
        return df
    cutoff = df["timestamp"].iloc[-1] - delta
    return df[df["timestamp"] >= cutoff].reset_index(drop=True)


def _fetch_backtest_data(symbol: str, timeframe: str, lookback: str):
    """
    Return (df, error_str). df has columns: timestamp, open, high, low, close, volume.

    Routing logic (priority order):
    1. TV-extracted local files — highest fidelity, same source as calibration.
       Only used when the file covers ≥80% of the requested lookback period.
    2. Binance public API — crypto symbols on all timeframes (full history, no auth).
    3. Alpaca — stocks on intraday timeframes (requires API keys).
    4. yfinance — universal fallback.
    """
    # ── Tier 1: TV-extracted local files ─────────────────────────────────────
    tv_df, _ = _load_tv_ohlcv(symbol, timeframe)
    if not tv_df.empty:
        filtered = _apply_lookback_filter(tv_df, lookback)
        min_needed = _EXPECTED_BARS.get(lookback, {}).get(timeframe, 50)
        if len(filtered) >= int(min_needed * 0.80):
            return filtered, None

    # ── Tier 2+: live data sources ────────────────────────────────────────────
    # Crypto routing: Binance for all crypto timeframes, Alpaca for stocks intraday only
    crypto_tfs   = {"15m", "1h", "4h", "1d", "1wk"}
    intraday_tfs = {"15m", "1h", "4h"}
    binance_warning = ""
    if _is_crypto(symbol) and timeframe in crypto_tfs:
        df, err = _fetch_binance_ohlcv(symbol, timeframe, lookback)
        if not df.empty:
            return df, None
        # USDT/USDC pairs have no valid Yahoo Finance equivalent — fail loudly
        # rather than silently substituting USD data and corrupting comparisons
        if not symbol.upper().endswith(("/USD", "-USD")):
            return pd.DataFrame(), f"Binance required for {symbol} but unavailable: {err}"
        binance_warning = f"[Binance fallback to yfinance] {err} — "
    elif not _is_crypto(symbol) and timeframe in intraday_tfs:
        df, err = _fetch_alpaca_ohlcv(symbol, timeframe, lookback)
        if not df.empty:
            return df, None
        binance_warning = f"[Alpaca fallback to yfinance] {err} — "

    try:
        import yfinance as yf
    except ImportError:
        return pd.DataFrame(), "yfinance is not installed. Run: pip install yfinance"

    period_map = {"6 months": "6mo", "1 year": "1y", "2 years": "2y", "5 years": "5y"}
    # 4h is resampled from 1h
    interval_map = {"15m": "15m", "1h": "1h", "4h": "1h", "1d": "1d", "1wk": "1wk"}

    period      = period_map.get(lookback, "1y")
    dl_interval = interval_map.get(timeframe, "1d")
    yf_sym      = _yf_symbol(symbol)

    # Warn if yfinance intraday limits will truncate the data
    limit_err = _check_yf_limits(dl_interval, lookback)
    if limit_err:
        return pd.DataFrame(), binance_warning + limit_err

    try:
        raw = yf.download(yf_sym, period=period, interval=dl_interval, progress=False, auto_adjust=True)
    except Exception as e:
        return pd.DataFrame(), f"Download failed for {yf_sym}: {e}"

    if raw.empty:
        return pd.DataFrame(), f"No data returned for {symbol} ({timeframe}, {lookback})."

    # Flatten MultiIndex columns (yfinance ≥ 0.2 returns them for single tickers too)
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = [str(c[0]).lower() for c in raw.columns]
    else:
        raw.columns = [str(c).lower() for c in raw.columns]

    df = raw.reset_index()
    df.columns = [str(c).lower() for c in df.columns]
    # Rename the timestamp column regardless of what yfinance calls it
    ts_col = next((c for c in df.columns if c in ("date", "datetime", "index")), df.columns[0])
    df = df.rename(columns={ts_col: "timestamp"})
    df["timestamp"] = pd.to_datetime(df["timestamp"]).dt.tz_localize(None)

    for col in ("open", "high", "low", "close", "volume"):
        if col not in df.columns:
            return pd.DataFrame(), f"Missing required column '{col}' in downloaded data."

    df = df[["timestamp", "open", "high", "low", "close", "volume"]].dropna().reset_index(drop=True)

    if timeframe == "4h":
        df = (df.set_index("timestamp")
                .resample("4h")
                .agg({"open": "first", "high": "max", "low": "min",
                      "close": "last", "volume": "sum"})
                .dropna().reset_index())

    return df.reset_index(drop=True), None


def _eval_condition(df: pd.DataFrame, indicator: str, condition: str, value) -> "pd.Series | None":
    """Translate one UI condition row into a boolean Series over df's integer index."""
    close = df["close"]

    if indicator == "EMA 50 vs EMA 200":
        e50, e200 = df["ema_50"], df["ema_200"]
        if condition == "crosses above":  return (e50 > e200) & (e50.shift(1) <= e200.shift(1))
        if condition == "crosses below":  return (e50 < e200) & (e50.shift(1) >= e200.shift(1))
        if condition == "is above":       return e50 > e200
        if condition == "is below":       return e50 < e200

    elif indicator == "RSI":
        rsi = df.get("rsi", pd.Series(50.0, index=df.index))
        v = float(value) if value is not None else 50.0
        if condition == "< (oversold)":   return rsi < v
        if condition == "> (overbought)": return rsi > v
        if condition == "crosses above":  return (rsi > v) & (rsi.shift(1) <= v)
        if condition == "crosses below":  return (rsi < v) & (rsi.shift(1) >= v)

    elif indicator == "Stoch RSI (K vs D)":
        k = df.get("stoch_k", pd.Series(50.0, index=df.index))
        d = df.get("stoch_d", pd.Series(50.0, index=df.index))
        if condition == "K crosses above D": return (k > d) & (k.shift(1) <= d.shift(1))
        if condition == "K crosses below D": return (k < d) & (k.shift(1) >= d.shift(1))
        if condition == "K < 20":            return k < 20
        if condition == "K > 80":            return k > 80

    elif indicator == "Supertrend Direction":
        st_col = df.get("st_bull", pd.Series(True, index=df.index))
        if condition == "turns bullish":
            return st_col.astype(bool) & (~st_col.shift(1).fillna(False).astype(bool))
        if condition == "turns bearish":
            return (~st_col.astype(bool)) & st_col.shift(1).fillna(True).astype(bool)
        if condition == "is bullish":    return st_col.astype(bool)
        if condition == "is bearish":    return (~st_col.astype(bool))

    elif indicator == "Price vs VWAP":
        vwap = df.get("vwap", pd.Series(np.nan, index=df.index))
        if condition == "crosses above": return (close > vwap) & (close.shift(1) <= vwap.shift(1))
        if condition == "crosses below": return (close < vwap) & (close.shift(1) >= vwap.shift(1))
        if condition == "is above":      return close > vwap
        if condition == "is below":      return close < vwap

    elif indicator == "ADX":
        adx = df.get("adx", pd.Series(np.nan, index=df.index))
        v = float(value) if value is not None else 25.0
        if condition == "rises above": return (adx > v) & (adx.shift(1) <= v)
        if condition == "falls below": return (adx < v) & (adx.shift(1) >= v)

    elif indicator == "BB Fast Position":
        # bb_fast_pos: 0=lower band, 1=upper band, <0=below lower, >1=above upper
        # bb_squeeze: True when fast bands are inside slow bands
        if "bb_fast_pos" not in df.columns:
            return None
        fp      = df["bb_fast_pos"]
        squeeze = df.get("bb_squeeze", pd.Series(False, index=df.index)).astype(bool)
        bull_zone = fp >= 0.6   # upper half of fast bands
        bear_zone = fp <= 0.4   # lower half of fast bands
        if condition == "enters bull zone":  return bull_zone & (~bull_zone.shift(1).fillna(False))
        if condition == "enters bear zone":  return bear_zone & (~bear_zone.shift(1).fillna(False))
        if condition == "squeeze starts":    return squeeze & (~squeeze.shift(1).fillna(False))
        if condition == "above fast upper":  return fp > 1
        if condition == "below fast lower":  return fp < 0

    return None


_CONDITION_INVERSE = {
    "crosses above":       "crosses below",
    "crosses below":       "crosses above",
    "is above":            "is below",
    "is below":            "is above",
    "< (oversold)":        "> (overbought)",
    "> (overbought)":      "< (oversold)",
    "K crosses above D":   "K crosses below D",
    "K crosses below D":   "K crosses above D",
    "K < 20":              "K > 80",
    "K > 80":              "K < 20",
    "turns bullish":       "turns bearish",
    "turns bearish":       "turns bullish",
    "is bullish":          "is bearish",
    "is bearish":          "is bullish",
    "rises above":         "falls below",
    "falls below":         "rises above",
    "enters bull zone":    "enters bear zone",
    "enters bear zone":    "enters bull zone",
    "above fast upper":    "below fast lower",
    "below fast lower":    "above fast upper",
}


def _build_entry_mask(df: pd.DataFrame, conditions: list) -> pd.Series:
    mask = pd.Series(True, index=df.index)
    for cond in conditions:
        c = _eval_condition(df, cond["indicator"], cond["condition"], cond.get("value"))
        if c is not None:
            mask = mask & c.fillna(False)
    return mask.fillna(False)


def _build_opposing_exit_mask(df: pd.DataFrame, conditions: list) -> pd.Series:
    """Exit when ANY entry condition flips to its inverse."""
    mask = pd.Series(False, index=df.index)
    for cond in conditions:
        inv = _CONDITION_INVERSE.get(cond["condition"])
        if inv:
            c = _eval_condition(df, cond["indicator"], inv, cond.get("value"))
            if c is not None:
                mask = mask | c.fillna(False)
    return mask.fillna(False)


def _run_backtest(
    symbol: str, timeframe: str, lookback: str,
    conditions: list, exit_mode: str,
    stop_pct: float = 2.0, target_pct: float = 4.0,
) -> dict:
    """Fetch data, compute indicators, run vectorbt backtest. Returns result dict."""
    try:
        import vectorbt as vbt
    except ImportError:
        return {"status": "error", "error": "vectorbt is not installed. Run: pip install vectorbt"}

    import plotly.graph_objects as go
    from micro_engine import add_all_indicators

    # ── Fetch OHLCV ───────────────────────────────────────────────────────────
    df, err = _fetch_backtest_data(symbol, timeframe, lookback)
    if err:
        return {"status": "error", "error": err}
    if df.empty:
        return {"status": "error", "error": f"No data returned for {symbol}."}

    # ── Compute indicators ────────────────────────────────────────────────────
    df = add_all_indicators(df)
    if df.empty or len(df) < 50:
        return {"status": "error", "error": "Not enough bars to compute indicators (need ≥ 50)."}

    # ── Build entry/exit signals ──────────────────────────────────────────────
    entry_mask = _build_entry_mask(df, conditions)

    df_idx = df.set_index("timestamp")
    close   = df_idx["close"]
    freq    = FREQ_MAP.get(timeframe, "D")
    entry_s = pd.Series(entry_mask.values, index=df_idx.index, dtype=bool)

    try:
        if exit_mode == "ATR-based (1.5x stop / 3x target)":
            atr     = df_idx["atr"].fillna(close * 0.02)
            sl_stop = (1.5 * atr / close).clip(0.001, 0.5)
            tp_stop = (3.0 * atr / close).clip(0.001, 2.0)
            exit_s  = pd.Series(False, index=df_idx.index)
            pf = vbt.Portfolio.from_signals(
                close=close, entries=entry_s, exits=exit_s,
                sl_stop=sl_stop, tp_stop=tp_stop, freq=freq,
            )
        elif exit_mode == "Fixed %":
            exit_s = pd.Series(False, index=df_idx.index)
            pf = vbt.Portfolio.from_signals(
                close=close, entries=entry_s, exits=exit_s,
                sl_stop=stop_pct / 100.0, tp_stop=target_pct / 100.0, freq=freq,
            )
        else:  # Opposing entry signal
            exit_mask = _build_opposing_exit_mask(df, conditions)
            exit_s    = pd.Series(exit_mask.values, index=df_idx.index, dtype=bool)
            pf = vbt.Portfolio.from_signals(
                close=close, entries=entry_s, exits=exit_s, freq=freq,
            )
    except Exception as e:
        return {"status": "error", "error": f"vectorbt portfolio construction failed: {e}"}

    # ── Extract stats ─────────────────────────────────────────────────────────
    try:
        raw = pf.stats()
    except Exception as e:
        return {"status": "error", "error": f"Stats extraction failed: {e}"}

    def _pct(key):
        v = raw.get(key, float("nan"))
        return f"{float(v):+.1f}%" if not pd.isna(v) else "—"

    def _ratio(key):
        v = raw.get(key, float("nan"))
        return f"{float(v):.2f}" if not pd.isna(v) else "—"

    def _int(key, fallback=None):
        v = raw.get(key, raw.get(fallback, float("nan")) if fallback else float("nan"))
        return str(int(float(v))) if not pd.isna(v) else "—"

    stats = {
        "total_return": _pct("Total Return [%]"),
        "sharpe":       _ratio("Sharpe Ratio"),
        "max_dd":       f"{-abs(float(raw.get('Max Drawdown [%]', 0))):+.1f}%" if not pd.isna(raw.get("Max Drawdown [%]", float("nan"))) else "—",
        "win_rate":     _pct("Win Rate [%]"),
        "n_trades":     _int("Total Closed Trades", "Total Trades"),
    }

    # ── Equity curve ──────────────────────────────────────────────────────────
    equity = pf.value()
    fig = go.Figure(go.Scatter(
        x=equity.index, y=equity.values,
        mode="lines", name="Portfolio Value",
        line=dict(color="#00d4ff", width=2),
        fill="tozeroy", fillcolor="rgba(0,212,255,0.07)",
    ))
    fig.update_layout(
        title=f"Equity Curve — {symbol} ({timeframe}, {lookback})",
        xaxis_title="Date", yaxis_title="Portfolio Value ($)",
        template="plotly_dark", height=350,
        margin=dict(l=40, r=20, t=40, b=40),
    )

    # ── Trade log ─────────────────────────────────────────────────────────────
    trade_log = None
    try:
        trades = pf.trades.records_readable
        keep = [c for c in ["Entry Timestamp", "Exit Timestamp", "Entry Price",
                             "Exit Price", "Return [%]", "PnL"] if c in trades.columns]
        tlog = trades[keep].copy()
        if "Return [%]" in tlog.columns:
            tlog["Return [%]"] = tlog["Return [%]"].map(
                lambda x: f"{x:+.2f}%" if pd.notna(x) else "—")
        for pc in ("Entry Price", "Exit Price"):
            if pc in tlog.columns:
                tlog[pc] = tlog[pc].map(lambda x: f"{x:,.4f}" if pd.notna(x) else "—")
        if "PnL" in tlog.columns:
            tlog["PnL"] = tlog["PnL"].map(lambda x: f"{x:+.2f}" if pd.notna(x) else "—")
        trade_log = tlog
    except Exception:
        pass

    result = {"status": "done", "stats": stats, "equity_fig": fig}
    if trade_log is not None:
        result["trade_log"] = trade_log
    return result


# ─── True MTF Backtest ────────────────────────────────────────────────────────

def _run_mtf_backtest(
    symbol: str,
    mode: str,
    lookback: str,
    include_presignal: bool = True,
    presignal_only: bool = False,
    position_mgmt: bool = False,
    allow_shorts: bool = False,
    vix_short_gate: float | None = None,
) -> dict:
    """
    Walk-forward multi-timeframe backtest using Banshee's real verdict logic.

    Downloads all historical data upfront (no live collection), then replays
    bar-by-bar using score_timeframe() × 3 + compute_verdict() — the exact
    same logic get_asset_radar uses live.

    Entry mode is controlled by two flags (mutually exclusive):
      include_presignal=True, presignal_only=False  → confirmed + PRE-SIGNAL
      include_presignal=False, presignal_only=False → confirmed signals only
      presignal_only=True                           → PRE-SIGNAL entries ONLY
          (confirmed BUY SETUP / STRONG BUY are ignored — pure early-entry test)

    allow_shorts=True adds short entries (STRONG SELL / SELL SETUP / PRE-SIGNAL SHORT)
    with symmetric 1.5×ATR stop above entry and 3.0×ATR target below. Only one
    open trade at a time — closing a long on a bearish signal can immediately flip
    to a short on the same bar, and vice versa.
    """
    import plotly.graph_objects as go
    from micro_engine import add_all_indicators, score_timeframe, compute_verdict, get_trend, detect_rsi_divergence

    MODE_TFS = {
        "swing":     ["1d", "4h", "1h"],
        "long_term": ["1wk", "1d", "4h"],
        "sniper":    ["4h", "1h", "15m"],
    }
    tfs = MODE_TFS.get(mode, MODE_TFS["swing"])
    tf_slow, tf_mid, tf_fast = tfs

    period_map = {"6 months": "6mo", "1 year": "1y", "2 years": "2y", "5 years": "5y"}
    period = period_map.get(lookback, "2y")

    # ── Download all three timeframes upfront ─────────────────────────────────
    try:
        import yfinance as yf
    except ImportError:
        return {"status": "error", "error": "yfinance not installed. Run: pip install yfinance"}

    yf_sym = symbol.replace("/", "-")

    # ── VIX history for regime gate (downloaded once if needed) ──────────────
    vix_ts  = None   # numpy array of timestamps
    vix_vals = None  # numpy array of VIX closes (same index)
    if allow_shorts and vix_short_gate is not None:
        try:
            _vix_raw = yf.download("^VIX", period=period, interval="1d",
                                   progress=False, auto_adjust=True)
            if not _vix_raw.empty:
                if isinstance(_vix_raw.columns, pd.MultiIndex):
                    _vix_raw.columns = [str(c[0]).lower() for c in _vix_raw.columns]
                else:
                    _vix_raw.columns = [str(c).lower() for c in _vix_raw.columns]
                _vix_raw = _vix_raw.reset_index()
                _vix_raw.columns = [str(c).lower() for c in _vix_raw.columns]
                _ts_col = next((c for c in _vix_raw.columns if c in ("date", "datetime")), _vix_raw.columns[0])
                _vix_raw["_ts"] = pd.to_datetime(_vix_raw[_ts_col]).dt.tz_localize(None)
                _vix_raw = _vix_raw.dropna(subset=["_ts", "close"]).sort_values("_ts")
                vix_ts   = _vix_raw["_ts"].values
                vix_vals = _vix_raw["close"].values
        except Exception:
            pass  # gate silently disabled if VIX data unavailable

    def _dl(interval, resample_to=None):
        # ── Crypto routing: Binance for all crypto TFs; Alpaca for stocks intraday ──
        crypto_tfs   = {"15m", "1h", "4h", "1d", "1wk"}
        intraday_tfs = {"15m", "1h", "4h"}
        binance_note = ""
        if _is_crypto(symbol) and interval in crypto_tfs:
            df_bn, err_bn = _fetch_binance_ohlcv(symbol, interval, lookback)
            if not df_bn.empty:
                return df_bn.reset_index(drop=True), None
            # USDT/USDC pairs have no valid Yahoo Finance equivalent — fail loudly
            # rather than silently substituting USD data and corrupting comparisons
            if not symbol.upper().endswith(("/USD", "-USD")):
                return pd.DataFrame(), f"Binance required for {symbol} but unavailable: {err_bn}"
            binance_note = f"[Binance unavailable: {err_bn}] "
        elif not _is_crypto(symbol) and interval in intraday_tfs:
            df_al, err_al = _fetch_alpaca_ohlcv(symbol, interval, lookback)
            if not df_al.empty:
                return df_al.reset_index(drop=True), None
            binance_note = f"[Alpaca unavailable: {err_al}] "

        # ── yfinance fallback ─────────────────────────────────────────────────
        # 4h is resampled from 1h on yfinance (no native 4h)
        dl_interval = {"4h": "1h", "15m": "15m"}.get(interval, interval)
        # Check yfinance intraday limits before downloading
        limit_err = _check_yf_limits(dl_interval, lookback)
        if limit_err:
            return pd.DataFrame(), binance_note + limit_err
        try:
            raw = yf.download(yf_sym, period=period, interval=dl_interval,
                              progress=False, auto_adjust=True)
        except Exception as e:
            return pd.DataFrame(), binance_note + str(e)
        if raw.empty:
            return pd.DataFrame(), binance_note + f"No data for {symbol} {interval} — symbol may be unavailable or delisted on Yahoo Finance."
        if isinstance(raw.columns, pd.MultiIndex):
            raw.columns = [str(c[0]).lower() for c in raw.columns]
        else:
            raw.columns = [str(c).lower() for c in raw.columns]
        df = raw.reset_index()
        df.columns = [str(c).lower() for c in df.columns]
        ts_col = next((c for c in df.columns if c in ("date", "datetime")), df.columns[0])
        df = df.rename(columns={ts_col: "timestamp"})
        df["timestamp"] = pd.to_datetime(df["timestamp"]).dt.tz_localize(None)
        for col in ("open", "high", "low", "close", "volume"):
            if col not in df.columns:
                return pd.DataFrame(), f"Missing column '{col}'"
        df = df[["timestamp", "open", "high", "low", "close", "volume"]].dropna().reset_index(drop=True)
        if interval in ("4h",):
            df = (df.set_index("timestamp")
                    .resample("4h")
                    .agg({"open": "first", "high": "max", "low": "min",
                          "close": "last", "volume": "sum"})
                    .dropna().reset_index())
        return df.reset_index(drop=True), None

    df_slow, err = _dl(tf_slow)
    if err: return {"status": "error", "error": f"Slow TF ({tf_slow}): {err}"}
    df_mid,  err = _dl(tf_mid)
    if err: return {"status": "error", "error": f"Mid TF ({tf_mid}): {err}"}
    df_fast, err = _dl(tf_fast)
    if err: return {"status": "error", "error": f"Fast TF ({tf_fast}): {err}"}

    if len(df_slow) < 60:
        return {"status": "error", "error": f"Not enough slow-TF bars ({len(df_slow)}). Try a longer lookback."}

    # ── Walk-forward loop ─────────────────────────────────────────────────────
    # Step through every slow-TF bar (skip first 60 for indicator warmup).
    # At each bar, slice each TF up to that timestamp, compute verdict.
    trades = []
    equity = 100.0
    equity_curve = []
    bnh_curve    = []   # buy-and-hold baseline: $100 invested at bar MIN_BARS
    bnh_start    = None # close price at the first bar we actually test (set on first loop iter)
    in_trade  = False
    trade_dir = "long"   # "long" or "short" for the current open trade
    entry_price = stop = target = 0.0
    entry_ts    = None
    entry_type  = ""      # "BUY SETUP", "STRONG BUY", "PRE-SIGNAL", "SHORT: ..." — tracked per trade
    # Position management state (used when position_mgmt=True)
    pos_size       = 1.0  # fraction of position still open (1.0 = full, 0.5 = half)
    at_breakeven   = False
    partial_taken  = False
    MIN_BARS       = 60

    slow_ts = df_slow["timestamp"].values

    for i in range(MIN_BARS, len(df_slow)):
        ts_now = slow_ts[i]

        # Slice each TF to current timestamp (no look-ahead)
        s_slice = df_slow.iloc[:i+1].copy()
        m_slice = df_mid[df_mid["timestamp"] <= ts_now].copy()
        f_slice = df_fast[df_fast["timestamp"] <= ts_now].copy()

        _bnh_close = float(df_slow.iloc[i]["close"])
        if bnh_start is None:
            bnh_start = _bnh_close

        if len(m_slice) < 20 or len(f_slice) < 20:
            equity_curve.append((ts_now, equity))
            bnh_curve.append((ts_now, 100.0 * _bnh_close / bnh_start))
            continue

        # Add indicators
        s_ind = add_all_indicators(s_slice)
        m_ind = add_all_indicators(m_slice)
        f_ind = add_all_indicators(f_slice)

        if s_ind.empty or m_ind.empty or f_ind.empty:
            equity_curve.append((ts_now, equity))
            bnh_curve.append((ts_now, 100.0 * _bnh_close / bnh_start))
            continue

        # Score each timeframe
        s_bull, s_bear, _ = score_timeframe(s_ind)
        m_bull, m_bear, _ = score_timeframe(m_ind)
        f_bull, f_bear, _ = score_timeframe(f_ind)

        trend_slow = get_trend(s_ind)
        trend_mid  = get_trend(m_ind)
        trend_fast = get_trend(f_ind)

        slow_adx = float(s_ind.iloc[-1].get("adx", float("nan")))
        rsi_div_slow = detect_rsi_divergence(s_ind) if not s_ind.empty else None
        verdict, _, _, pre_signal = compute_verdict(
            trend_slow, trend_mid, trend_fast,
            s_bull, s_bear, m_bull, m_bear, f_bull, f_bear,
            slow_adx=slow_adx, rsi_divergence=rsi_div_slow,
        )

        close_now = float(df_slow.iloc[i]["close"])
        atr_val   = float(s_ind.iloc[-1].get("atr", close_now * 0.02))

        # ── Manage open trade ────────────────────────────────────────────────
        if in_trade:
            # 1R distance (positive regardless of direction)
            risk_per_r = entry_price - stop if trade_dir == "long" else stop - entry_price

            # ── Position management milestones (only when flag is set) ────────
            if position_mgmt and risk_per_r > 0:
                if trade_dir == "long":
                    at_1r    = close_now >= entry_price + risk_per_r
                    at_1pt5r = close_now >= entry_price + 1.5 * risk_per_r
                else:
                    at_1r    = close_now <= entry_price - risk_per_r
                    at_1pt5r = close_now <= entry_price - 1.5 * risk_per_r

                if not at_breakeven and at_1r:
                    stop         = entry_price
                    at_breakeven = True

                if not partial_taken and at_1pt5r:
                    if trade_dir == "long":
                        partial_pnl = (close_now - entry_price) / entry_price * 0.5
                    else:
                        partial_pnl = (entry_price - close_now) / entry_price * 0.5
                    equity *= (1 + partial_pnl)
                    trades.append({
                        "entry_ts":   entry_ts, "exit_ts": ts_now,
                        "entry":      entry_price, "exit": close_now,
                        "entry_type": entry_type,
                        "result":     "PARTIAL (50%)", "pnl_pct": partial_pnl * 100,
                        "size":       0.5,
                    })
                    pos_size      = 0.5
                    partial_taken = True

            # ── Hard stops / targets ──────────────────────────────────────────
            stop_hit   = close_now <= stop   if trade_dir == "long" else close_now >= stop
            target_hit = close_now >= target if trade_dir == "long" else close_now <= target

            if stop_hit:
                pnl_pct = (stop - entry_price) / entry_price * pos_size if trade_dir == "long" else (entry_price - stop) / entry_price * pos_size
                equity *= (1 + pnl_pct)
                trades.append({"entry_ts": entry_ts, "exit_ts": ts_now,
                                "entry": entry_price, "exit": stop,
                                "entry_type": entry_type,
                                "result": "STOP", "pnl_pct": pnl_pct * 100,
                                "size": pos_size})
                in_trade = False
            elif target_hit:
                pnl_pct = (target - entry_price) / entry_price * pos_size if trade_dir == "long" else (entry_price - target) / entry_price * pos_size
                equity *= (1 + pnl_pct)
                trades.append({"entry_ts": entry_ts, "exit_ts": ts_now,
                                "entry": entry_price, "exit": target,
                                "entry_type": entry_type,
                                "result": "TARGET", "pnl_pct": pnl_pct * 100,
                                "size": pos_size})
                in_trade = False
            elif trade_dir == "long" and (
                verdict in ("STRONG SELL", "SELL SETUP") or
                (include_presignal and pre_signal == "PRE-SIGNAL SHORT")
            ):
                pnl_pct     = (close_now - entry_price) / entry_price * pos_size
                equity     *= (1 + pnl_pct)
                exit_reason = "PRE-SIGNAL EXIT" if pre_signal == "PRE-SIGNAL SHORT" else "SIGNAL EXIT"
                trades.append({"entry_ts": entry_ts, "exit_ts": ts_now,
                                "entry": entry_price, "exit": close_now,
                                "entry_type": entry_type,
                                "result": exit_reason, "pnl_pct": pnl_pct * 100,
                                "size": pos_size})
                in_trade = False
            elif trade_dir == "short" and (
                verdict in ("BUY SETUP", "STRONG BUY") or
                (include_presignal and pre_signal == "PRE-SIGNAL LONG")
            ):
                pnl_pct     = (entry_price - close_now) / entry_price * pos_size
                equity     *= (1 + pnl_pct)
                exit_reason = "PRE-SIGNAL EXIT" if pre_signal == "PRE-SIGNAL LONG" else "SIGNAL EXIT"
                trades.append({"entry_ts": entry_ts, "exit_ts": ts_now,
                                "entry": entry_price, "exit": close_now,
                                "entry_type": entry_type,
                                "result": exit_reason, "pnl_pct": pnl_pct * 100,
                                "size": pos_size})
                in_trade = False

        # ── Open new trade ────────────────────────────────────────────────────
        is_confirmed       = verdict in ("BUY SETUP", "STRONG BUY")
        is_presignal_fire  = pre_signal == "PRE-SIGNAL LONG"
        is_confirmed_short = verdict in ("STRONG SELL", "SELL SETUP")
        is_presignal_short = pre_signal == "PRE-SIGNAL SHORT"

        if presignal_only:
            should_enter       = is_presignal_fire and not is_confirmed
            should_enter_short = is_presignal_short and not is_confirmed_short
        elif include_presignal:
            should_enter       = is_confirmed or (is_presignal_fire and not is_confirmed)
            should_enter_short = is_confirmed_short or (is_presignal_short and not is_confirmed_short)
        else:
            should_enter       = is_confirmed
            should_enter_short = is_confirmed_short

        if not in_trade and should_enter:
            in_trade      = True
            trade_dir     = "long"
            entry_price   = close_now
            stop          = close_now - 1.5 * atr_val
            target        = close_now + 3.0 * atr_val
            entry_ts      = ts_now
            pos_size      = 1.0
            at_breakeven  = False
            partial_taken = False
            entry_type    = "PRE-SIGNAL" if (is_presignal_fire and not is_confirmed) else verdict

        elif allow_shorts and not in_trade and should_enter_short and (
            vix_short_gate is None
            or vix_ts is None
            or (
                (idx := int(np.searchsorted(vix_ts, ts_now, side="right")) - 1) >= 0
                and float(vix_vals[idx]) >= vix_short_gate
            )
        ):
            in_trade      = True
            trade_dir     = "short"
            entry_price   = close_now
            stop          = close_now + 1.5 * atr_val
            target        = close_now - 3.0 * atr_val
            entry_ts      = ts_now
            pos_size      = 1.0
            at_breakeven  = False
            partial_taken = False
            entry_type    = "SHORT: PRE-SIGNAL" if (is_presignal_short and not is_confirmed_short) else f"SHORT: {verdict}"

        bnh_curve.append((ts_now, 100.0 * _bnh_close / bnh_start))
        equity_curve.append((ts_now, equity))

    # Close any open trade at last price (end of backtest window)
    if in_trade:
        last_price = float(df_slow.iloc[-1]["close"])
        if trade_dir == "long":
            pnl_pct = (last_price - entry_price) / entry_price * pos_size
        else:
            pnl_pct = (entry_price - last_price) / entry_price * pos_size
        equity    *= (1 + pnl_pct)
        trades.append({"entry_ts": entry_ts, "exit_ts": slow_ts[-1],
                        "entry": entry_price, "exit": last_price,
                        "entry_type": entry_type,
                        "result": "OPEN→CLOSE", "pnl_pct": pnl_pct * 100,
                        "size": pos_size})

    # ── Stats ─────────────────────────────────────────────────────────────────
    n_trades  = len(trades)
    if n_trades == 0:
        return {"status": "error", "error": "No trades generated. Try a longer lookback or different mode."}

    pnls      = [t["pnl_pct"] for t in trades]
    wins      = [p for p in pnls if p > 0]
    win_rate  = len(wins) / n_trades * 100
    total_ret = (equity - 100.0)

    presignal_count = sum(1 for t in trades if t.get("entry_type") == "PRE-SIGNAL")
    short_count     = sum(1 for t in trades if str(t.get("entry_type", "")).startswith("SHORT:"))

    # Sharpe from equity curve returns
    eq_vals   = [e for _, e in equity_curve]
    eq_rets   = pd.Series(eq_vals).pct_change().dropna()
    sharpe    = (eq_rets.mean() / eq_rets.std() * np.sqrt(252)) if eq_rets.std() > 0 else 0.0

    # Max drawdown
    eq_s      = pd.Series(eq_vals)
    roll_max  = eq_s.cummax()
    dd        = ((eq_s - roll_max) / roll_max * 100)
    max_dd    = float(dd.min())

    # Buy-and-hold return over the same window
    bnh_ret = (bnh_curve[-1][1] - 100.0) if bnh_curve else 0.0
    alpha   = total_ret - bnh_ret   # positive = beat buy-and-hold

    stats = {
        "total_return":     f"{total_ret:+.1f}%",
        "bnh_return":       f"{bnh_ret:+.1f}%",
        "alpha":            f"{alpha:+.1f}%",
        "sharpe":           f"{sharpe:.2f}",
        "max_dd":           f"{max_dd:+.1f}%",
        "win_rate":         f"{win_rate:+.1f}%",
        "n_trades":         str(n_trades),
        "presignal_count":  str(presignal_count),
        "presignal_pct":    f"{presignal_count / n_trades * 100:.0f}%" if n_trades else "0%",
        "short_count":      str(short_count),
        "short_pct":        f"{short_count / n_trades * 100:.0f}%" if n_trades else "0%",
    }

    # ── Equity curve chart ────────────────────────────────────────────────────
    ec_ts  = [t for t, _ in equity_curve]
    ec_val = [v for _, v in equity_curve]
    bnh_ts  = [t for t, _ in bnh_curve]
    bnh_val = [v for _, v in bnh_curve]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=ec_ts, y=ec_val, mode="lines", name="Banshee Strategy",
        line=dict(color="#00d4ff", width=2),
        fill="tozeroy", fillcolor="rgba(0,212,255,0.07)",
    ))
    fig.add_trace(go.Scatter(
        x=bnh_ts, y=bnh_val, mode="lines", name="Buy & Hold",
        line=dict(color="#ff9900", width=1.5, dash="dot"),
    ))
    fig.update_layout(
        title=f"MTF Equity Curve — {symbol} ({mode}, {lookback})",
        xaxis_title="Date", yaxis_title="Portfolio Value (start=100)",
        template="plotly_dark", height=350,
        margin=dict(l=40, r=20, t=40, b=40),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )

    # ── Trade log ─────────────────────────────────────────────────────────────
    trade_log = pd.DataFrame(trades)
    if not trade_log.empty:
        # Ensure "size" column exists (older rows from non-position-mgmt runs won't have it)
        if "size" not in trade_log.columns:
            trade_log["size"] = 1.0
        trade_log["size"]     = trade_log["size"].map(lambda x: f"{x:.0%}")
        trade_log["pnl_pct"]  = trade_log["pnl_pct"].map(lambda x: f"{x:+.2f}%")
        trade_log["entry"]    = trade_log["entry"].map(lambda x: f"{x:,.4f}")
        trade_log["exit"]     = trade_log["exit"].map(lambda x: f"{x:,.4f}")
        trade_log = trade_log.rename(columns={
            "entry_ts":   "Entry Date",
            "exit_ts":    "Exit Date",
            "entry_type": "Signal Type",
            "entry":      "Entry Price",
            "exit":       "Exit Price",
            "result":     "Exit Reason",
            "pnl_pct":    "P&L %",
            "size":       "Size",
        })

    return {
        "status":           "done",
        "stats":            stats,
        "equity_fig":       fig,
        "trade_log":        trade_log,
        "symbol":           symbol,
        "mode":             mode,
        "lookback":         lookback,
        "tfs":              f"{tf_slow}/{tf_mid}/{tf_fast}",
        "presignal_count":   presignal_count,
        "include_presignal": include_presignal,
        "presignal_only":    presignal_only,
        "position_mgmt":     position_mgmt,
        "allow_shorts":      allow_shorts,
        "vix_short_gate":    vix_short_gate,
        "short_count":       short_count,
    }


def _render_mtf_backtest_tab():
    st.markdown("### True MTF Backtest")
    st.markdown(
        "Replays Banshee's **real multi-timeframe verdict logic** against historical data. "
        "Downloads all bars upfront, walks forward bar-by-bar — no live collection needed."
    )
    st.markdown(
        "Uses the exact same `score_timeframe()` + `compute_verdict()` that `get_asset_radar` "
        "runs live, across all three timeframes with proper weighting."
    )
    st.markdown("---")

    # ── Signal Playbook hint ──────────────────────────────────────────────────
    with st.expander("📖 Before you run — Signal Playbook cheat sheet", expanded=False):
        st.markdown("""
**Trade count first — everything else second:**
| Trades | What it means |
|---|---|
| < 15 | Direction only — could be noise |
| 15–30 | Weak signal — treat as hypothesis |
| 30–50 | Getting real |
| 50+ | Statistical basis — start drawing conclusions |

**Which mode works for which asset:**
| Asset | Best mode | Why |
|---|---|---|
| GLD / trending macro assets | Long_term confirmed + presignal | Sharpe 2.90 — clean persistent trends |
| Stocks (SPY, NVDA) | Sniper confirmed + presignal | Sharpe 0.60, -8.7% max DD |
| Crypto (BTC) | Sniper presignal only | Confirmed signals arrive too late |
| ETH | Avoid | Negative in every mode tested |

**Judge long_term by Sharpe, not alpha.** B&H alpha is misleading in bull markets — use Sharpe + max DD.

*Full playbook: open the **📖 Manual** tab in the sidebar → Signal Playbook.*
""")

    st.markdown("---")

    # ── Named Strategy Presets ────────────────────────────────────────────────
    _PRESETS = {
        "🥇 Gold Stalker (PAXG)": {
            "desc": "Best risk-adjusted in full batch — Sharpe 1.38, +69%, -9% DD over 2y.  PAXG long_term + confirmed+pre + shorts gated VIX≥20 + position mgmt.",
            "mtf_symbol":           "PAXG/USD",
            "mtf_mode":             "long_term",
            "mtf_lookback":         "2 years",
            "mtf_entry_mode_radio": "Confirmed + PRE-SIGNAL (both)",
            "mtf_position_mgmt":    True,
            "mtf_allow_shorts":     True,
            "mtf_vix_gate_label":   "VIX ≥ 20 (recommended)",
        },
        "📈 NVDA Long-Term": {
            "desc": "Validated TradFi sleeper — Sharpe 2.21, +338%, 29 trades over 5y.  NVDA long_term + confirmed+pre + position mgmt.",
            "mtf_symbol":           "NVDA",
            "mtf_mode":             "long_term",
            "mtf_lookback":         "5 years",
            "mtf_entry_mode_radio": "Confirmed + PRE-SIGNAL (both)",
            "mtf_position_mgmt":    True,
            "mtf_allow_shorts":     False,
            "mtf_vix_gate_label":   "No gate",
        },
    }

    _p_col, _load_col = st.columns([3, 1])
    with _p_col:
        _preset_name = st.selectbox(
            "Load named strategy",
            ["— Custom —"] + list(_PRESETS.keys()),
            key="mtf_preset_select",
        )
    with _load_col:
        st.write("")
        st.write("")
        if _preset_name != "— Custom —" and st.button("Load →", key="mtf_load_preset"):
            for _k, _v in _PRESETS[_preset_name].items():
                if _k != "desc":
                    st.session_state[_k] = _v
            st.session_state["mtf_preset_select"] = "— Custom —"
            st.rerun()

    if _preset_name != "— Custom —":
        st.info(_PRESETS[_preset_name]["desc"])

    st.markdown("---")

    c1, c2, c3 = st.columns([2, 2, 2])
    with c1:
        symbol = st.text_input("Symbol", placeholder="e.g. BTC/USD, SPY, NVDA",
                               key="mtf_symbol").strip().upper()
    with c2:
        mode = st.selectbox("Mode", ["swing", "long_term", "sniper"], key="mtf_mode")
    with c3:
        lookback = st.selectbox("Lookback", LOOKBACKS, index=2, key="mtf_lookback")

    tf_labels = {
        "swing":     "Daily / 4H / 1H",
        "long_term": "Weekly / Daily / 4H",
        "sniper":    "4H / 1H / 15m",
    }
    st.caption(f"Timeframes: **{tf_labels.get(mode, '')}**  ·  Exit: 3× ATR target or 1.5× ATR stop")

    # Entry mode radio — confirmed-only vs confirmed+pre-signal
    # PRE-SIGNAL only mode removed: batch testing confirmed it's dead (-3.9% avg, Sharpe -0.17)
    ENTRY_MODES = [
        "Confirmed only (BUY SETUP / STRONG BUY)",
        "Confirmed + PRE-SIGNAL (both)",
    ]
    entry_mode = st.radio(
        "Entry mode",
        ENTRY_MODES,
        index=1,
        key="mtf_entry_mode_radio",
        horizontal=True,
        help=(
            "Confirmed only = baseline. "
            "Confirmed + PRE-SIGNAL = adds early entries on pre-signal bars (recommended — batch avg +82.3%)."
        ),
    )
    include_presignal = entry_mode != ENTRY_MODES[0]
    presignal_only    = False

    position_mgmt = st.checkbox(
        "Position Management (1R → breakeven, 1.5R → 50% off, remainder to 2R)",
        value=False,
        key="mtf_position_mgmt",
        help=(
            "Simulates real trade management: move stop to breakeven at 1R profit, "
            "take 50% off at 1.5R, let the rest run to the 2R target. "
            "Comparison with default (all-in / all-out) shows how much edge comes from management."
        ),
    )

    allow_shorts = st.checkbox(
        "Allow shorts (open short positions on bearish signals)",
        value=False,
        key="mtf_allow_shorts",
        help="Batch result: shorts hurt BTC/ETH (both go negative over 2y). Only PAXG benefits — use Gold Stalker preset for the validated config.",
    )

    _VIX_OPTS = {
        "No gate": None,
        "VIX ≥ 20 (recommended)": 20.0,
        "VIX ≥ 25": 25.0,
        "VIX ≥ 30": 30.0,
    }
    vix_short_gate = None
    if allow_shorts:
        _vix_label = st.selectbox(
            "VIX gate for shorts",
            list(_VIX_OPTS.keys()),
            index=1,
            key="mtf_vix_gate_label",
            help="Only open short positions when VIX is at or above this level. VIX≥20 added +22% return on PAXG in batch tests.",
        )
        vix_short_gate = _VIX_OPTS[_vix_label]

    # Warn on combos that exceed yfinance intraday data limits
    # (crypto symbols will use Binance instead, so no real limit for them)
    _mode_worst_interval = {"sniper": "15m", "swing": "1h", "long_term": "4h"}
    _worst = _mode_worst_interval.get(mode, "1d")
    _limit_warn = _check_yf_limits(_worst, lookback)
    if _limit_warn and not _is_crypto(symbol):
        st.warning(f"**Data limit warning:** {_limit_warn}", icon="⚠️")

    # ── Playbook hint card ────────────────────────────────────────────────────
    # Shows the active profile for the entered symbol so you know exactly which
    # weights and gates will drive this backtest before hitting Run.
    if symbol:
        from asset_profiles import get_effective_profile as _gep, load_profiles as _lp
        _hp      = _gep(symbol)
        _confirmed = symbol in _lp()
        _hclass  = _hp.get("asset_class", "default")
        _hrm     = _hp.get("risk_model", {})
        _hstop   = _hrm.get("stop_multiplier",   1.5)
        _htgt    = _hrm.get("target_multiplier", 3.0)
        _hchand  = _hrm.get("chandelier_exit",   False)
        _hvgate  = _hp.get("volume_gate",  False)
        _hethg   = _hp.get("eth_btc_gate", False)
        _conf_str = "confirmed" if _confirmed else "suggested"
        _flags = []
        if _hchand: _flags.append("Chandelier ✓")
        if _hvgate: _flags.append("Vol gate ✓")
        if _hethg:  _flags.append("ETH/BTC gate ✓")
        _flag_str = "  ·  " + "  ·  ".join(_flags) if _flags else ""
        st.info(
            f"🎛️ **Profile:** {_hclass} ({_conf_str})  ·  "
            f"Stop {_hstop}× ATR  ·  Target {_htgt}× ATR"
            f"{_flag_str}  —  *change in ⚙️ Settings → Asset Profiles*",
            icon="🎛️",
        )

        # ── Batch data insight ────────────────────────────────────────────────
        with st.expander("📊 What does our data say?", expanded=False):
            _strats  = _load_strategies()
            _sym_key = symbol.upper()
            _matches = []
            for _bname, _bdata in _strats.items():
                if not _bname.startswith("[BATCH]"):
                    continue
                _bname_up = _bname.upper()
                if _sym_key.replace("/", "") not in _bname_up.replace("/", "") and _sym_key not in _bname_up:
                    continue
                if mode not in _bname:
                    continue
                _bstats = _bdata.get("stats", {})
                try:
                    _bnt = int(str(_bstats.get("n_trades", 0)))
                except (ValueError, TypeError):
                    _bnt = 0
                if _bnt < 15:
                    continue
                try:
                    _bsh = float(str(_bstats.get("sharpe", 0)))
                except (ValueError, TypeError):
                    _bsh = -999.0
                # Extract entry-mode label: "[BATCH] SYM mode lookback LABEL"
                _bparts = _bname[len("[BATCH] "):].split(" ", 3)
                _blabel = _bparts[3] if len(_bparts) > 3 else _bname
                _matches.append((_bsh, _blabel, _bstats))

            _matches.sort(reverse=True)

            if not _matches:
                st.info(f"No batch results (≥ 15 trades) for **{symbol}** · **{mode}**. Run the batch to populate.")
            else:
                st.caption(f"Top batch results — **{symbol}** · **{mode}** · ≥ 15 trades · sorted by Sharpe")
                for _rank, (_bsh, _blabel, _bstats) in enumerate(_matches[:5], 1):
                    _ret = _bstats.get("total_return", "—")
                    _dd  = _bstats.get("max_dd", "—")
                    _nt  = _bstats.get("n_trades", "—")
                    st.markdown(
                        f"**#{_rank}** `{_blabel}`  —  "
                        f"Sharpe **{_bsh:.2f}**  ·  Return {_ret}  ·  DD {_dd}  ·  {_nt} trades"
                    )
                if len(_matches) > 5:
                    st.caption(f"… and {len(_matches) - 5} more. See Saved Results tab for the full table.")

    if st.button("▶ Run MTF Backtest", key="mtf_run_btn", type="primary"):
        if not symbol:
            st.error("Enter a symbol first.")
        else:
            with st.spinner(f"Downloading {symbol} history and replaying Banshee verdicts…"):
                result = _run_mtf_backtest(
                    symbol, mode, lookback,
                    include_presignal=include_presignal,
                    presignal_only=presignal_only,
                    position_mgmt=position_mgmt,
                    allow_shorts=allow_shorts,
                    vix_short_gate=vix_short_gate,
                )
            st.session_state["mtf_result"] = result

    result = st.session_state.get("mtf_result")
    if not result:
        return

    if result["status"] == "error":
        st.error(result["error"])
        return

    stats = result["stats"]
    st.markdown("---")
    if result.get("presignal_only"):
        mode_label = "PRE-SIGNAL Only"
    elif result.get("include_presignal"):
        mode_label = "Confirmed + PRE-SIGNAL"
    else:
        mode_label = "Confirmed Only"
    mgmt_label = " · Position Mgmt ON" if result.get("position_mgmt") else ""
    st.markdown(f"#### Results — {result['symbol']} · {result['mode']} · {result['tfs']} · {result['lookback']} · [{mode_label}]{mgmt_label}")

    m1, m2, m3, m4, m5, m6, m7 = st.columns(7)
    m1.metric("Banshee Return",  stats["total_return"])
    m2.metric("Buy & Hold",      stats["bnh_return"])
    m3.metric("Alpha vs B&H",    stats["alpha"],
              help="Positive = Banshee beat doing nothing. Negative = you'd have been better off just holding.")
    m4.metric("Sharpe Ratio",    stats["sharpe"])
    m5.metric("Max Drawdown",    stats["max_dd"])
    m6.metric("Win Rate",        stats["win_rate"])
    m7.metric("# Trades",        stats["n_trades"])

    # Show the PRE-SIGNAL breakdown — was early entry actually used?
    ps_count = int(stats.get("presignal_count", "0"))
    n_trades_int = int(stats["n_trades"]) if stats["n_trades"] != "—" else 0
    presignal_on = result.get("include_presignal") or result.get("presignal_only")
    if presignal_on and ps_count > 0:
        confirmed_count = n_trades_int - ps_count
        st.info(
            f"⚡ **PRE-SIGNAL contributed {ps_count} of {n_trades_int} entries** "
            f"({stats.get('presignal_pct','0%')} of trades). "
            f"{confirmed_count} were confirmed BUY SETUP / STRONG BUY. "
            "Check the Trade Log → Signal Type column to see which trades fired early.",
            icon="⚡",
        )
    elif presignal_on and ps_count == 0:
        st.caption("PRE-SIGNAL was enabled but no early entries fired (all trades were confirmed signals).")

    if n_trades_int < 5:
        st.warning(
            f"Only {n_trades_int} trade(s) found — results are not statistically meaningful. "
            "Banshee's MTF verdict requires all 3 timeframes to align, which is intentionally rare. "
            "Try a longer lookback (2–5 years) or 'swing' / 'long_term' mode for more signals.",
            icon="⚠️",
        )

    st.plotly_chart(result["equity_fig"], width="stretch")

    tlog = result.get("trade_log")
    if tlog is not None and not tlog.empty:
        with st.expander("Trade Log (includes Signal Type column)", expanded=False):
            st.dataframe(tlog, width="stretch")

    st.markdown("---")
    # Reset the save-name field whenever a new result arrives (avoids Streamlit
    # persisting the user's last-typed name across different runs).
    _result_id = f"{result['symbol']}_{result['mode']}_{result['lookback']}"
    if st.session_state.get("_mtf_last_result_id") != _result_id:
        st.session_state["_mtf_last_result_id"] = _result_id
        st.session_state["mtf_save_name"] = f"MTF {result['symbol']} {result['mode']}"
    save_name = st.text_input("Save as", key="mtf_save_name")
    if st.button("💾 Save Result", key="mtf_save_btn"):
        _save_strategy(save_name, {
            "type":       "mtf_backtest",
            "symbol":     result["symbol"],
            "timeframe":  result["tfs"],
            "lookback":   result["lookback"],
            "conditions": [f"Banshee MTF verdict ({result['mode']} mode)"],
            "exit_mode":  "ATR 1.5x stop / 3x target",
            "stats":      stats,
        })
        st.success(f"Saved as '{save_name}'")


# ─── Discovery Mode ────────────────────────────────────────────────────────────

# Each entry here is one indicator tested in isolation.
# We use event-based conditions (crosses / turns) so each entry is a discrete
# signal — not a state that fires on every single bar.
DISCOVERY_COMBOS = [
    {
        "name":      "Supertrend Flip Bullish",
        "indicator": "Supertrend Direction",
        "condition": "turns bullish",
        "value":     None,
        "note":      "Price crosses above the Supertrend line — a momentum flip.",
    },
    {
        "name":      "EMA Golden Cross",
        "indicator": "EMA 50 vs EMA 200",
        "condition": "crosses above",
        "value":     None,
        "note":      "Fast EMA (50) crosses slow EMA (200) — classic trend-following entry.",
    },
    {
        "name":      "RSI Oversold Bounce",
        "indicator": "RSI",
        "condition": "crosses above",
        "value":     30,
        "note":      "RSI climbs back above 30 — exhaustion bounce / seller fatigue signal.",
    },
    {
        "name":      "Stoch RSI Bullish Cross",
        "indicator": "Stoch RSI (K vs D)",
        "condition": "K crosses above D",
        "value":     None,
        "note":      "Fast stoch line crosses slow — short-term momentum turning upward.",
    },
    {
        "name":      "Price Reclaims VWAP",
        "indicator": "Price vs VWAP",
        "condition": "crosses above",
        "value":     None,
        "note":      "Price crosses back above fair value — institutional buy zone.",
    },
    {
        "name":      "ADX Trend Trigger",
        "indicator": "ADX",
        "condition": "rises above",
        "value":     25,
        "note":      "Trend strength ignites past 25 — choppy phase ending, direction forming.",
    },
    {
        "name":      "Dual BB Position",
        "indicator": "BB Fast Position",
        "condition": "enters bull zone",
        "value":     None,
        "note":      "Price moves into the upper half of the fast Bollinger Band — momentum quality signal; filters out weak rallies.",
    },
]


def _render_discovery_tab():
    """
    Discovery Mode — test each indicator one at a time.

    The problem with most strategies: traders combine 3-5 indicators with AND logic,
    which produces almost no trades. Before building a complex setup, you need to know
    which indicators actually have edge on THIS asset and THIS timeframe.

    Discovery tests each indicator alone → ranks them → you take the top 1-2
    winners to the Build Strategy tab and combine them. Science first, then art.
    """
    st.markdown("### Discovery Mode")
    st.markdown(
        "Test each indicator **one at a time** to find which ones actually have "
        "historical edge for your asset and timeframe. Start here — there's no point "
        "combining indicators if they don't individually show any edge."
    )

    with st.expander("How Discovery Mode works", expanded=False):
        st.markdown("""
**Problem:** Most strategy builders AND together 3–5 indicators. Result: barely any trades,
no statistical meaning, and no idea which indicators are actually doing the work.

**Discovery Mode's approach:**
1. Test Supertrend alone → how does it perform?
2. Test EMA golden cross alone → better or worse?
3. Test RSI oversold bounce alone → any edge?
4. ...repeat for all 6 indicators
5. **Rank by Sharpe Ratio** — the best risk-adjusted returns tell you what's working.

**Then:** Take your top 1–2 indicators to the **Build Strategy** tab.
Use AND logic to require both of them to confirm before entering.
Now you have a real, evidence-based reason to use those specific indicators together.

> Think of it like A/B testing your indicators before shipping the strategy.
        """)

    st.markdown("---")

    c1, c2, c3 = st.columns([2, 2, 2])
    with c1:
        # Auto-fill from active session symbol if one is loaded
        active_sym   = st.session_state.get("active_symbol", "") or ""
        disc_symbol  = st.text_input(
            "Symbol",
            value=st.session_state.get("disc_symbol", active_sym),
            placeholder="e.g. BTC/USD, NVDA, SPY",
            key="disc_symbol_input",
        ).strip().upper()
        st.session_state["disc_symbol"] = disc_symbol
    with c2:
        disc_tf_default = st.session_state.get("disc_tf", "1d")
        tf_idx  = TIMEFRAMES.index(disc_tf_default) if disc_tf_default in TIMEFRAMES else 3
        disc_tf = st.selectbox("Timeframe", TIMEFRAMES, index=tf_idx, key="disc_tf_select")
        st.session_state["disc_tf"] = disc_tf
    with c3:
        disc_lb_default = st.session_state.get("disc_lb", "2 years")
        lb_idx  = LOOKBACKS.index(disc_lb_default) if disc_lb_default in LOOKBACKS else 2
        disc_lb = st.selectbox("Lookback", LOOKBACKS, index=lb_idx, key="disc_lb_select")
        st.session_state["disc_lb"] = disc_lb

    disc_exit = st.radio(
        "Exit method used for ALL tests (keeps comparison apples-to-apples)",
        ["ATR-based (1.5x stop / 3x target)", "Fixed %"],
        horizontal=True,
        key="disc_exit_radio",
    )

    run_col, _ = st.columns([1, 3])
    with run_col:
        disc_run = st.button(
            "▶ Run Discovery",
            type="primary",
            key="disc_run_btn",
            disabled=not disc_symbol,
        )

    if not disc_symbol:
        st.caption("Enter a symbol above to enable discovery.")

    if disc_run and disc_symbol:
        all_results = []
        prog = st.progress(0, text="Starting discovery scan…")

        for idx, combo in enumerate(DISCOVERY_COMBOS):
            prog.progress(idx / len(DISCOVERY_COMBOS), text=f"Testing: {combo['name']}…")

            # Run the standard backtest engine with just ONE condition at a time
            r = _run_backtest(
                symbol=disc_symbol,
                timeframe=disc_tf,
                lookback=disc_lb,
                conditions=[{
                    "indicator": combo["indicator"],
                    "condition": combo["condition"],
                    "value":     combo["value"],
                }],
                exit_mode=disc_exit,
            )
            all_results.append({
                "name":      combo["name"],
                "note":      combo["note"],
                "indicator": combo["indicator"],
                "condition": combo["condition"],
                "status":    r.get("status"),
                "error":     r.get("error", ""),
                "stats":     r.get("stats", {}),
                "equity_fig": r.get("equity_fig"),
            })

        prog.progress(1.0, text=f"Discovery complete — {len(all_results)} indicators tested.")
        st.session_state["discovery_result"] = {
            "symbol":  disc_symbol,
            "tf":      disc_tf,
            "lb":      disc_lb,
            "combos":  all_results,
            "ran_at":  datetime.now().strftime("%Y-%m-%d %H:%M"),
        }

    # ── Display results ────────────────────────────────────────────────────────
    disc_result = st.session_state.get("discovery_result")
    if not disc_result:
        return

    st.markdown("---")
    st.markdown(f"#### Indicator Rankings — {disc_result['symbol']} · {disc_result['tf']} · {disc_result['lb']}")
    st.caption(f"Ran at: {disc_result['ran_at']}  ·  Sorted by Sharpe Ratio (best risk-adjusted return)")

    # Build the leaderboard table
    rows = []
    for r in disc_result["combos"]:
        s = r["stats"]
        if r["status"] == "done":
            # Parse the Sharpe string to a float for sorting ("1.23" → 1.23)
            try:
                sharpe_num = float(s.get("sharpe", "0").replace("—", "0"))
            except Exception:
                sharpe_num = 0.0

            # Determine edge tier based on Sharpe
            if sharpe_num >= 0.8:
                edge_label = "⭐ STRONG"
            elif sharpe_num >= 0.3:
                edge_label = "⚠️ MARGINAL"
            elif sharpe_num >= 0:
                edge_label = "❌ WEAK"
            else:
                edge_label = "❌ NEGATIVE"

            rows.append({
                "_sort":      sharpe_num,    # hidden sort key
                "Indicator":  r["name"],
                "What it tests": r["note"],
                "Return":     s.get("total_return", "—"),
                "Sharpe":     s.get("sharpe",       "—"),
                "Max DD":     s.get("max_dd",        "—"),
                "Win Rate":   s.get("win_rate",      "—"),
                "# Trades":   s.get("n_trades",      "—"),
                "Edge Tier":  edge_label,
            })
        else:
            rows.append({
                "_sort":         -999,
                "Indicator":     r["name"],
                "What it tests": r["note"],
                "Return": "—", "Sharpe": "—", "Max DD": "—",
                "Win Rate": "—", "# Trades": "—",
                "Edge Tier": f"❌ Error: {r.get('error','?')[:50]}",
            })

    # Sort by Sharpe (highest first) and strip the hidden sort column
    rows.sort(key=lambda x: x["_sort"], reverse=True)
    display_rows = [{k: v for k, v in row.items() if k != "_sort"} for row in rows]

    st.dataframe(pd.DataFrame(display_rows), width="stretch", hide_index=True)

    # ── Top recommendation ─────────────────────────────────────────────────────
    strong_rows = [r for r in rows if "STRONG" in r.get("Edge Tier", "")]
    marginal_rows = [r for r in rows if "MARGINAL" in r.get("Edge Tier", "")]

    if strong_rows:
        top_name   = strong_rows[0]["Indicator"]
        top_sharpe = strong_rows[0]["Sharpe"]
        second_tip = (
            f" Consider pairing it with **{strong_rows[1]['Indicator']}** (Sharpe {strong_rows[1]['Sharpe']})."
            if len(strong_rows) > 1 else
            (f" **{marginal_rows[0]['Indicator']}** (Sharpe {marginal_rows[0]['Sharpe']}) could work as a second filter."
             if marginal_rows else "")
        )
        st.success(
            f"**Top pick:** {top_name} (Sharpe {top_sharpe}). "
            f"This indicator shows real edge on {disc_result['symbol']} ({disc_result['tf']}).{second_tip} "
            f"Head to **Build Strategy** and add them as AND conditions.",
            icon="✅",
        )
    elif marginal_rows:
        st.warning(
            f"No indicator showed strong standalone edge. "
            f"Best available: **{marginal_rows[0]['Indicator']}** (Sharpe {marginal_rows[0]['Sharpe']}). "
            "Try a different timeframe or longer lookback before combining.",
            icon="⚠️",
        )
    else:
        st.error(
            "No indicator showed positive edge on this symbol/timeframe. "
            "This asset may be too choppy for trend-following strategies. "
            "Consider mean-reversion approaches or try a longer timeframe.",
            icon="❌",
        )

    # ── Promote Discovery rankings → Asset Profile ────────────────────────────
    st.markdown("---")
    st.markdown("#### Promote to Asset Profile")
    st.markdown(
        "Convert these Discovery rankings into a permanent profile for "
        f"**{disc_result['symbol']}**. "
        "Top-ranked indicators get higher weights in live verdicts — Banshee will shout "
        "louder when your proven indicators fire and whisper when the weaker ones do."
    )
    if st.button(
        f"📌 Promote to {disc_result['symbol']} Profile",
        key="disc_promote_btn",
        type="secondary",
        help="Saves these Sharpe-ranked weights to banshee_profiles.json. You can reset anytime in Settings.",
    ):
        from asset_profiles import promote_discovery_to_profile, save_profile, get_profile as _gp
        old_profile = _gp(disc_result["symbol"])
        new_profile = promote_discovery_to_profile(disc_result["symbol"], disc_result)
        save_profile(disc_result["symbol"], new_profile)

        # Show a diff of what changed
        changes = []
        for key, new_ind in new_profile["indicators"].items():
            old_w = old_profile["indicators"].get(key, {}).get("weight", 1.0)
            new_w = new_ind.get("weight", 1.0)
            if abs(new_w - old_w) > 0.05:
                arrow = "↑" if new_w > old_w else "↓"
                changes.append(f"**{new_ind.get('label', key)}**: {old_w:.1f} → {new_w:.1f} {arrow}")

        if changes:
            st.success(
                f"Profile saved for **{disc_result['symbol']}**. Weight changes:\n\n"
                + "  \n".join(changes),
                icon="📌",
            )
        else:
            st.info(f"Profile saved for **{disc_result['symbol']}** — no weight changes (all indicators ranked equally).", icon="📌")

    st.markdown("---")

    # ── Equity curves for successful runs ──────────────────────────────────────
    done_combos = [r for r in disc_result["combos"] if r["status"] == "done" and r.get("equity_fig")]
    # Sort by sharpe so the best appear at the top
    done_combos_sorted = sorted(
        done_combos,
        key=lambda r: float(r["stats"].get("sharpe", "0").replace("—", "0")),
        reverse=True,
    )
    if done_combos_sorted:
        st.markdown("#### Equity Curves (click to expand, best first)")
        for r in done_combos_sorted:
            s = r["stats"]
            label = f"{r['name']} — Return: {s.get('total_return','?')}  |  Sharpe: {s.get('sharpe','?')}  |  Win Rate: {s.get('win_rate','?')}"
            with st.expander(label, expanded=False):
                st.caption(r["note"])
                st.plotly_chart(r["equity_fig"], width="stretch")

    st.markdown("---")
    st.info(
        "**Next step:** Take your top 1–2 indicators to **Build Strategy**. "
        "Add them as entry conditions — both must be true at once (AND logic). "
        "That's confluence: you need the evidence before you risk your capital.",
        icon="➡️",
    )


# ─── Live Snapshot tab ─────────────────────────────────────────────────────────

def _render_live_snapshot_tab():
    """
    Live Snapshot — right now, for your loaded symbol, should you trade?

    Reads from the app's session cache (no new network request). Shows every
    indicator's current state, counts confluence, and gives a clear GO / NO-GO
    with an ATR-based trade plan pre-filled.
    """
    st.markdown("### Live Snapshot")
    st.markdown(
        "Real-time GO / NO-GO for the symbol you've loaded in the sidebar. "
        "No new network call — reads the data already in memory."
    )

    # Check if a symbol has been loaded via the sidebar
    active_sym = st.session_state.get("active_symbol")
    cache      = st.session_state.get("symbol_cache", {})

    if not active_sym or active_sym not in cache:
        st.info(
            "No symbol loaded yet. Go to the **sidebar**, type a symbol, "
            "and click **Load** — then come back here for your snapshot.",
            icon="📡",
        )
        return

    entry    = cache[active_sym]
    analysis = entry.get("analysis", {})
    mode     = entry.get("mode", "swing")
    fetched  = entry.get("fetched_at")
    age_str  = fetched.strftime("%H:%M:%S") if fetched else "unknown time"

    if "error" in analysis:
        st.error(f"Data error for {active_sym}: {analysis['error']}")
        return

    # Pull all the key fields from the analysis payload
    verdict    = analysis.get("verdict", "WAIT — NO TRADE")
    pre_signal = analysis.get("pre_signal")
    bull_score = analysis.get("bull_score", 0)
    bear_score = analysis.get("bear_score", 0)
    edge       = analysis.get("edge", 0)
    atr_plan   = analysis.get("atr_plan")
    eq         = analysis.get("entry_quality", {})
    support    = analysis.get("support", [])
    resistance = analysis.get("resistance", [])
    signals    = analysis.get("signals", {})

    st.markdown(f"#### {active_sym} — {mode.replace('_', ' ').title()} Mode")
    st.caption(f"Loaded at {age_str} · Refresh via sidebar Force Refresh button")

    # ── Verdict banner ─────────────────────────────────────────────────────────
    # Color-coded bar showing the overall Banshee verdict
    VERDICT_COLORS = {
        "STRONG BUY":      "#00ff99",
        "BUY SETUP":       "#00cc77",
        "WAIT — NO TRADE": "#888888",
        "SELL SETUP":      "#ff6655",
        "STRONG SELL":     "#ff2222",
    }
    vc = VERDICT_COLORS.get(verdict, "#888888")
    st.markdown(
        f"<div style='background:{vc}22; border-left:5px solid {vc}; "
        f"padding:12px 18px; border-radius:6px; margin-bottom:12px;'>"
        f"<span style='color:{vc}; font-size:1.4em; font-weight:bold;'>{verdict}</span>"
        f"<span style='color:#aaa; margin-left:20px; font-size:0.95em;'>"
        f"Edge: {edge:+.1f}  ·  Bull {bull_score:.1f} vs Bear {bear_score:.1f}"
        f"</span></div>",
        unsafe_allow_html=True,
    )

    # PRE-SIGNAL alert — shows up even when main verdict is WAIT
    if pre_signal:
        st.warning(
            f"⚡ **{pre_signal}** — early signal detected before full 3-TF confirmation. "
            "Enter smaller size or wait for the next timeframe to confirm.",
            icon="⚡",
        )

    # ── Entry quality (timing check) ──────────────────────────────────────────
    quality      = eq.get("quality", "WAIT")
    quality_icon = {"READY": "✅", "CAUTION": "⚠️", "WAIT": "🛑"}.get(quality, "—")
    st.markdown(f"**Entry Timing:** {quality_icon} **{quality}**")
    for reason in eq.get("reasons", []):
        st.caption(f"  • {reason}")

    st.markdown("---")

    # ── Indicator checklist ────────────────────────────────────────────────────
    st.markdown("#### Indicator Checklist")
    st.caption("Green = bullish signal   ·   Red = bearish   ·   Gray = neutral")

    # Flatten all signals from all timeframes, keeping the first occurrence of each indicator
    # (the slow TF signal is most meaningful, but we show whichever is seen first)
    seen_indicators = {}
    for tf_label, tf_sigs in signals.items():
        for sig in tf_sigs:
            key = sig["indicator"]
            if key not in seen_indicators:
                seen_indicators[key] = {
                    "state":       sig["state"],
                    "explanation": sig["explanation"],
                    "tf":          tf_label,
                }

    # Keywords that classify a signal as bullish or bearish
    BULL_WORDS = {"BULLISH", "UPTREND", "ACCUMULATION", "ABOVE", "OVERSOLD",
                  "FRESH BULLISH", "LEADING ACCUMULATION", "BOUNCE", "MOMENTUM"}
    BEAR_WORDS = {"BEARISH", "DOWNTREND", "DISTRIBUTION", "BELOW", "OVERBOUGHT",
                  "FRESH BEARISH", "PULLBACK"}

    def _classify(state: str) -> str:
        upper = state.upper()
        if any(w in upper for w in BULL_WORDS): return "bull"
        if any(w in upper for w in BEAR_WORDS): return "bear"
        return "neutral"

    bull_count = sum(1 for v in seen_indicators.values() if _classify(v["state"]) == "bull")
    bear_count = sum(1 for v in seen_indicators.values() if _classify(v["state"]) == "bear")
    total_sigs = len(seen_indicators)

    # Confluence bar
    if total_sigs > 0:
        pct     = bull_count / total_sigs
        bar_col = "#00ff99" if pct >= 0.65 else ("#ffaa00" if pct >= 0.45 else "#ff6655")
        st.markdown(
            f"<div style='margin-bottom:10px;'>"
            f"<span style='color:{bar_col}; font-weight:bold; font-size:1.05em;'>"
            f"{bull_count}/{total_sigs} indicators bullish</span> "
            f"<span style='color:#888;'>({bear_count} bearish)</span>"
            f"</div>",
            unsafe_allow_html=True,
        )

    # Render each indicator as a colour-coded card (2 per row)
    items = list(seen_indicators.items())
    for row_start in range(0, len(items), 2):
        cols = st.columns(2)
        for col_idx, (ind_name, sig_data) in enumerate(items[row_start : row_start + 2]):
            direction = _classify(sig_data["state"])
            color = {"bull": "#00cc77", "bear": "#ff6655", "neutral": "#888888"}[direction]
            icon  = {"bull": "▲", "bear": "▼", "neutral": "─"}[direction]
            with cols[col_idx]:
                st.markdown(
                    f"<div style='background:{color}18; border-left:3px solid {color}; "
                    f"padding:7px 11px; border-radius:5px; margin-bottom:7px;'>"
                    f"<b style='color:{color};'>{icon} {ind_name}</b><br>"
                    f"<span style='color:#ccc; font-size:0.85em;'>{sig_data['state']}</span><br>"
                    f"<span style='color:#888; font-size:0.75em;'>"
                    f"{sig_data['explanation']} <i>({sig_data['tf']})</i>"
                    f"</span></div>",
                    unsafe_allow_html=True,
                )

    st.markdown("---")

    # ── ATR Trade Plan ─────────────────────────────────────────────────────────
    st.markdown("#### Trade Plan")

    if atr_plan:
        # Decide direction based on verdict + pre-signal
        is_long = verdict in ("STRONG BUY", "BUY SETUP") or pre_signal == "PRE-SIGNAL LONG"
        if is_long:
            entry_p  = atr_plan["entry"]
            stop_p   = atr_plan["stop_long"]
            target_p = atr_plan["target_long"]
            direction = "LONG"
        else:
            entry_p  = atr_plan["entry"]
            stop_p   = atr_plan["stop_short"]
            target_p = atr_plan["target_short"]
            direction = "SHORT"

        risk_pts   = abs(entry_p - stop_p)
        reward_pts = abs(target_p - entry_p)
        rr         = reward_pts / risk_pts if risk_pts > 0 else 0.0

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Direction",   direction)
        c2.metric("Entry",       f"{entry_p:,.4f}")
        c3.metric("Stop Loss",   f"{stop_p:,.4f}",   delta=f"-{risk_pts:.4f}", delta_color="inverse")
        c4.metric("Take Profit", f"{target_p:,.4f}", delta=f"+{reward_pts:.4f}")
        st.caption(f"ATR: {atr_plan['atr']:.4f}  ·  R:R = {rr:.1f}:1  ·  Stop = 1.5×ATR, Target = 3.0×ATR")
    else:
        st.caption("ATR plan unavailable (insufficient data on fast timeframe).")

    # ── Key levels ─────────────────────────────────────────────────────────────
    if support or resistance:
        st.markdown("---")
        st.markdown("#### Key Levels")
        lc, rc = st.columns(2)
        with lc:
            st.markdown("**Support**")
            for lvl in support[:3]:
                st.caption(f"  {lvl:,.4f}")
        with rc:
            st.markdown("**Resistance**")
            for lvl in resistance[:3]:
                st.caption(f"  {lvl:,.4f}")

    # ── Final GO / NO-GO decision ──────────────────────────────────────────────
    st.markdown("---")
    st.markdown("#### Decision")

    if quality == "READY" and verdict in ("STRONG BUY", "BUY SETUP"):
        st.success("**GO — Long setup confirmed. Entry quality clear.**", icon="✅")
    elif quality == "READY" and verdict in ("STRONG SELL", "SELL SETUP"):
        st.error("**GO SHORT — Bearish setup confirmed. Entry quality clear.**", icon="📉")
    elif pre_signal and quality in ("READY", "CAUTION"):
        st.warning(
            f"**EARLY SIGNAL ({pre_signal}) — Full confirmation pending. "
            "Trade with reduced size or wait for the next TF to confirm.**",
            icon="⚡",
        )
    elif quality == "CAUTION":
        st.warning("**CAUTION — Edge exists but timing isn't clean. Wait for better entry.**", icon="⚠️")
    else:
        st.info("**PASS — No clean setup right now. Preserve capital, wait for clarity.**", icon="🛑")


# ─── Session state helpers ─────────────────────────────────────────────────────

def _init_state():
    if "lab_conditions" not in st.session_state:
        st.session_state.lab_conditions = [{"indicator": INDICATORS[0], "condition": CONDITIONS[INDICATORS[0]][0], "value": None}]
    if "lab_exit_mode" not in st.session_state:
        st.session_state.lab_exit_mode = EXIT_MODES[0]
    if "lab_stop_pct" not in st.session_state:
        st.session_state.lab_stop_pct = 2.0
    if "lab_target_pct" not in st.session_state:
        st.session_state.lab_target_pct = 4.0
    if "lab_timeframe" not in st.session_state:
        st.session_state.lab_timeframe = "1d"
    if "lab_symbol" not in st.session_state:
        st.session_state.lab_symbol = ""
    if "lab_lookback" not in st.session_state:
        st.session_state.lab_lookback = "1 year"
    if "lab_strategy_name" not in st.session_state:
        st.session_state.lab_strategy_name = "My Strategy"
    if "lab_backtest_result" not in st.session_state:
        st.session_state.lab_backtest_result = None   # filled in Step 3
    if "lab_banshee_result" not in st.session_state:
        st.session_state.lab_banshee_result = None    # filled in Step 4
    if "lab_comp_results" not in st.session_state:
        st.session_state.lab_comp_results = []        # filled in STRATLAB-B
    if "lab_comp_symbol" not in st.session_state:
        st.session_state.lab_comp_symbol = ""
    if "mtf_result" not in st.session_state:
        st.session_state.mtf_result = None
    # Discovery Mode state
    if "discovery_result" not in st.session_state:
        st.session_state.discovery_result = None
    if "disc_symbol" not in st.session_state:
        st.session_state["disc_symbol"] = ""
    if "disc_tf" not in st.session_state:
        st.session_state["disc_tf"] = "1d"
    if "disc_lb" not in st.session_state:
        st.session_state["disc_lb"] = "2 years"

# ─── Build Strategy tab ────────────────────────────────────────────────────────

def _render_build_tab():
    st.markdown("### Strategy Configuration")

    # ── Load Saved Strategy ────────────────────────────────────────────────────
    saved = _load_strategies()
    user_strategies = {k: v for k, v in saved.items() if v.get("type") != "banshee_validation"}
    if user_strategies:
        with st.expander("📂 Load Saved Strategy", expanded=False):
            load_names = list(user_strategies.keys())
            selected_load = st.selectbox("Select strategy", load_names, key="lab_load_select")
            col_load, col_del = st.columns([1, 1])
            with col_load:
                if st.button("Load", key="lab_load_btn"):
                    s = user_strategies[selected_load]
                    st.session_state.lab_strategy_name = s.get("strategy_name", selected_load)
                    st.session_state.lab_conditions    = [dict(c) for c in s.get("conditions", [])]
                    st.session_state.lab_exit_mode     = s.get("exit_mode", EXIT_MODES[0])
                    st.session_state.lab_stop_pct      = float(s.get("stop_pct", 2.0))
                    st.session_state.lab_target_pct    = float(s.get("target_pct", 4.0))
                    st.session_state.lab_symbol        = s.get("symbol", "")
                    st.session_state.lab_timeframe     = s.get("timeframe", "1d")
                    st.session_state.lab_lookback      = s.get("lookback", "1 year")
                    st.session_state.lab_backtest_result = None
                    st.success(f"Loaded **{selected_load}**")
                    st.rerun()
            with col_del:
                if st.button("🗑 Delete", key="lab_del_saved_btn"):
                    _delete_strategy(selected_load)
                    st.success(f"Deleted **{selected_load}**")
                    st.rerun()
            st.caption(f"Saved: {user_strategies[selected_load].get('saved_at', '—')}")

    st.session_state.lab_strategy_name = st.text_input(
        "Strategy Name",
        value=st.session_state.lab_strategy_name,
        key="lab_strategy_name_input",
    )

    st.markdown("---")
    st.markdown("#### Entry Conditions *(all must be true simultaneously)*")

    conditions = st.session_state.lab_conditions
    to_remove = None

    for i, cond in enumerate(conditions):
        col_ind, col_cond, col_val, col_del = st.columns([2.5, 2.5, 1.5, 0.5])

        with col_ind:
            new_indicator = st.selectbox(
                f"Indicator {i+1}",
                INDICATORS,
                index=INDICATORS.index(cond["indicator"]) if cond["indicator"] in INDICATORS else 0,
                key=f"lab_ind_{i}",
                label_visibility="collapsed",
            )
            if new_indicator != cond["indicator"]:
                cond["indicator"] = new_indicator
                cond["condition"] = CONDITIONS[new_indicator][0]
                cond["value"] = None

        with col_cond:
            cond_opts = CONDITIONS[cond["indicator"]]
            cur_cond_idx = cond_opts.index(cond["condition"]) if cond["condition"] in cond_opts else 0
            cond["condition"] = st.selectbox(
                f"Condition {i+1}",
                cond_opts,
                index=cur_cond_idx,
                key=f"lab_cond_{i}",
                label_visibility="collapsed",
            )

        with col_val:
            needs_value = cond["condition"] in VALUE_CONDITIONS.get(cond["indicator"], [])
            if needs_value:
                default_val = DEFAULTS.get(cond["indicator"], 50)
                cond["value"] = st.number_input(
                    f"Value {i+1}",
                    value=float(cond["value"]) if cond["value"] is not None else float(default_val),
                    step=1.0,
                    key=f"lab_val_{i}",
                    label_visibility="collapsed",
                )
            else:
                st.write("")   # spacer

        with col_del:
            if len(conditions) > 1:
                if st.button("✕", key=f"lab_del_{i}", help="Remove this condition"):
                    to_remove = i

    if to_remove is not None:
        st.session_state.lab_conditions.pop(to_remove)
        st.rerun()

    if st.button("＋ Add Condition", key="lab_add_cond"):
        st.session_state.lab_conditions.append({
            "indicator": INDICATORS[0],
            "condition": CONDITIONS[INDICATORS[0]][0],
            "value": None,
        })
        st.rerun()

    st.markdown("---")
    st.markdown("#### Exit Conditions")

    st.session_state.lab_exit_mode = st.radio(
        "Exit Method",
        EXIT_MODES,
        index=EXIT_MODES.index(st.session_state.lab_exit_mode),
        key="lab_exit_mode_radio",
        horizontal=True,
    )

    if st.session_state.lab_exit_mode == "Fixed %":
        c1, c2 = st.columns(2)
        with c1:
            st.session_state.lab_stop_pct = st.number_input(
                "Stop Loss %", min_value=0.1, max_value=50.0,
                value=st.session_state.lab_stop_pct, step=0.5, key="lab_stop_pct_input"
            )
        with c2:
            st.session_state.lab_target_pct = st.number_input(
                "Take Profit %", min_value=0.1, max_value=200.0,
                value=st.session_state.lab_target_pct, step=0.5, key="lab_target_pct_input"
            )

    st.markdown("---")
    st.markdown("#### Symbol & Backtest Window")

    # Auto-fill symbol from active session if available
    active_sym = st.session_state.get("active_symbol", "") or ""
    if active_sym and not st.session_state.lab_symbol:
        st.session_state.lab_symbol = active_sym

    c1, c2, c3 = st.columns([2, 2, 2])
    with c1:
        st.session_state.lab_symbol = st.text_input(
            "Symbol",
            value=st.session_state.lab_symbol or active_sym,
            placeholder="e.g. BTC/USD, NVDA",
            key="lab_symbol_input",
        ).strip().upper()
    with c2:
        tf_idx = TIMEFRAMES.index(st.session_state.lab_timeframe) if st.session_state.lab_timeframe in TIMEFRAMES else 3
        st.session_state.lab_timeframe = st.selectbox(
            "Timeframe", TIMEFRAMES, index=tf_idx, key="lab_tf_select"
        )
    with c3:
        lb_idx = LOOKBACKS.index(st.session_state.lab_lookback) if st.session_state.lab_lookback in LOOKBACKS else 1
        st.session_state.lab_lookback = st.selectbox(
            "Lookback Period", LOOKBACKS, index=lb_idx, key="lab_lb_select"
        )

    st.markdown("---")
    st.markdown("#### Position Sizing")
    st.info("Fixed 1% risk per trade (R-based) — consistent with the Risk Desk. Configurable sizing coming in a later step.", icon="ℹ️")

    st.markdown("---")

    run_col, save_col, _ = st.columns([1, 1, 2])
    with run_col:
        run_clicked = st.button(
            "▶ Run Backtest",
            type="primary",
            key="lab_run_btn",
            disabled=not st.session_state.lab_symbol,
        )
    with save_col:
        save_clicked = st.button(
            "💾 Save Strategy",
            key="lab_save_btn",
            disabled=not st.session_state.lab_strategy_name,
        )

    if not st.session_state.lab_symbol:
        st.caption("Enter a symbol above to enable backtesting.")

    if save_clicked:
        name = st.session_state.lab_strategy_name.strip() or "Unnamed"
        payload = {
            "strategy_name": name,
            "conditions":    [dict(c) for c in st.session_state.lab_conditions],
            "exit_mode":     st.session_state.lab_exit_mode,
            "stop_pct":      st.session_state.lab_stop_pct,
            "target_pct":    st.session_state.lab_target_pct,
            "symbol":        st.session_state.lab_symbol,
            "timeframe":     st.session_state.lab_timeframe,
            "lookback":      st.session_state.lab_lookback,
        }
        # Attach stats from last run if available
        result = st.session_state.get("lab_backtest_result")
        if result and result.get("status") == "done":
            payload["stats"] = result.get("stats", {})
        _save_strategy(name, payload)
        st.success(f"Strategy **{name}** saved.")

    if run_clicked:
        if not st.session_state.lab_symbol:
            st.error("Please enter a symbol before running a backtest.")
        else:
            with st.spinner(f"Running backtest for {st.session_state.lab_symbol}…"):
                result = _run_backtest(
                    symbol=st.session_state.lab_symbol,
                    timeframe=st.session_state.lab_timeframe,
                    lookback=st.session_state.lab_lookback,
                    conditions=st.session_state.lab_conditions,
                    exit_mode=st.session_state.lab_exit_mode,
                    stop_pct=st.session_state.lab_stop_pct,
                    target_pct=st.session_state.lab_target_pct,
                )
            result.update({
                "strategy_name": st.session_state.lab_strategy_name,
                "symbol":        st.session_state.lab_symbol,
                "timeframe":     st.session_state.lab_timeframe,
                "lookback":      st.session_state.lab_lookback,
                "conditions":    [dict(c) for c in st.session_state.lab_conditions],
                "exit_mode":     st.session_state.lab_exit_mode,
                "requested_at":  datetime.now().strftime("%Y-%m-%d %H:%M"),
            })
            st.session_state.lab_backtest_result = result
            if result["status"] == "error":
                st.error(result.get("error", "Backtest failed."))
            else:
                st.success("Backtest complete — see the **Backtest Results** tab.")

# ─── Backtest Results tab ──────────────────────────────────────────────────────

def _render_results_tab():
    result = st.session_state.get("lab_backtest_result")

    if result is None:
        st.info("No backtest has been run yet. Configure a strategy in the **Build Strategy** tab and click **Run Backtest**.", icon="📊")
        return

    st.markdown(f"### {result.get('strategy_name', 'Strategy')} — Results")
    st.caption(f"Symbol: **{result['symbol']}** · Timeframe: **{result['timeframe']}** · Lookback: **{result['lookback']}** · Requested: {result.get('requested_at', '—')}")

    if result.get("status") == "error":
        st.error(result.get("error", "Backtest failed."))
        return

    if result.get("status") == "pending":
        st.warning(
            "Backtest engine not yet wired (Step 3). Below is the strategy config that will be passed to vectorbt.",
            icon="🔧",
        )
        st.markdown("**Entry Conditions:**")
        for i, cond in enumerate(result.get("conditions", []), 1):
            val_str = f" → `{cond['value']}`" if cond.get("value") is not None else ""
            st.markdown(f"  {i}. **{cond['indicator']}** — *{cond['condition']}*{val_str}")
        st.markdown(f"**Exit:** {result['exit_mode']}")
        st.markdown("**Position Sizing:** 1% risk per trade (R-based)")
        return

    # ── Populated by Step 3 ──
    stats = result.get("stats", {})
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Total Return", stats.get("total_return", "—"))
    c2.metric("Sharpe Ratio", stats.get("sharpe",       "—"))
    c3.metric("Max Drawdown", stats.get("max_dd",        "—"))
    c4.metric("Win Rate",     stats.get("win_rate",      "—"))
    c5.metric("# Trades",     stats.get("n_trades",      "—"))

    if "equity_fig" in result:
        st.plotly_chart(result["equity_fig"], width="stretch")

    if "trade_log" in result:
        st.markdown("#### Trade Log")
        st.dataframe(result["trade_log"], width="stretch")

# ─── Banshee Validation ───────────────────────────────────────────────────────

# Fixed conditions that mirror Banshee's own verdict logic
_BANSHEE_CONDITIONS = [
    {"indicator": "Supertrend Direction", "condition": "is bullish",    "value": None},
    {"indicator": "EMA 50 vs EMA 200",    "condition": "is above",      "value": None},
    {"indicator": "RSI",                  "condition": "< (oversold)",  "value": 70},
]


def _run_banshee_validation(symbol: str, timeframe: str, lookback: str) -> dict:
    """Run the pre-built Banshee strategy and return a result dict."""
    result = _run_backtest(
        symbol=symbol,
        timeframe=timeframe,
        lookback=lookback,
        conditions=_BANSHEE_CONDITIONS,
        exit_mode="ATR-based (1.5x stop / 3x target)",
    )
    result.update({
        "symbol":       symbol,
        "timeframe":    timeframe,
        "lookback":     lookback,
        "requested_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    })
    return result


# ─── Banshee Validation tab ───────────────────────────────────────────────────

def _render_banshee_validation_tab():
    st.markdown("### Banshee Signal Validation")
    st.markdown(
        "Tests whether Banshee's own verdict logic has a historical edge. "
        "This is the empirical grounding check — does what Banshee calls a BUY actually go up?"
    )

    st.markdown("---")
    st.markdown("#### Pre-Built Strategy (mirrors Banshee's rules)")

    with st.expander("Strategy Definition", expanded=True):
        st.markdown("""
| Component | Rule |
|-----------|------|
| **Entry 1** | Supertrend is bullish (`st_bull == True`) |
| **Entry 2** | EMA 50 > EMA 200 (uptrend confirmed) |
| **Entry 3** | RSI < 70 (not overbought at entry) |
| **Exit — Target** | +3× ATR from entry price |
| **Exit — Stop** | −1.5× ATR from entry price |
| **Sizing** | 1% risk per trade (R-based) |
        """)

    st.markdown("---")
    st.markdown("#### Run Parameters")

    c1, c2, c3 = st.columns([2, 2, 2])
    with c1:
        active_sym = st.session_state.get("active_symbol", "") or ""
        bv_symbol = st.text_input(
            "Symbol",
            value=active_sym,
            placeholder="e.g. BTC/USD, SPY",
            key="bv_symbol_input",
        ).strip().upper()
    with c2:
        bv_tf = st.selectbox("Timeframe", ["1d", "4h", "1h"], index=0, key="bv_tf_select")
    with c3:
        bv_lb = st.selectbox("Lookback Period", LOOKBACKS, index=2, key="bv_lb_select")  # default 2 years

    run_col, _ = st.columns([1, 3])
    with run_col:
        bv_run = st.button(
            "▶ Validate Banshee",
            type="primary",
            key="bv_run_btn",
            disabled=not bv_symbol,
        )

    if not bv_symbol:
        st.caption("Enter a symbol above to enable validation.")

    if bv_run:
        if not bv_symbol:
            st.error("Please enter a symbol.")
        else:
            with st.spinner(f"Running Banshee validation for {bv_symbol}…"):
                result = _run_banshee_validation(bv_symbol, bv_tf, bv_lb)
            st.session_state.lab_banshee_result = result
            if result["status"] == "error":
                st.error(result.get("error", "Validation failed."))
            else:
                st.success("Validation complete — results below.")

    bv_result = st.session_state.get("lab_banshee_result")
    if bv_result and bv_result.get("status") not in (None, "pending"):
        st.markdown("---")
        st.markdown(f"#### Validation Results — {bv_result['symbol']} ({bv_result['timeframe']}, {bv_result['lookback']})")
        st.caption(f"Requested: {bv_result.get('requested_at', '—')}")

        if bv_result.get("status") == "error":
            st.error(bv_result.get("error", "Validation failed."))
        else:
            stats = bv_result.get("stats", {})
            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric("Total Return", stats.get("total_return", "—"))
            c2.metric("Sharpe Ratio", stats.get("sharpe",       "—"))
            c3.metric("Max Drawdown", stats.get("max_dd",        "—"))
            c4.metric("Win Rate",     stats.get("win_rate",      "—"))
            c5.metric("# Trades",     stats.get("n_trades",      "—"))
            if "equity_fig" in bv_result:
                st.plotly_chart(bv_result["equity_fig"], width="stretch")
            if "trade_log" in bv_result:
                st.markdown("#### Trade Log")
                st.dataframe(bv_result["trade_log"], width="stretch")

            if st.button("💾 Save Validation Result", key="bv_save_btn"):
                sym  = bv_result["symbol"]
                tf   = bv_result["timeframe"]
                save_name = f"[BV] {sym} {tf}"
                _save_strategy(save_name, {
                    "type":       "banshee_validation",
                    "symbol":     sym,
                    "timeframe":  tf,
                    "lookback":   bv_result.get("lookback", ""),
                    "stats":      stats,
                    "requested_at": bv_result.get("requested_at", ""),
                })
                st.success(f"Saved as **{save_name}**")

# ─── Comparative Runs tab ─────────────────────────────────────────────────────

def _render_comparative_tab():
    st.markdown("### Comparative Runs")
    st.markdown(
        "Run the same strategy across multiple timeframes and lookbacks in one click. "
        "Results appear as a sortable table so you can spot which combo has the best edge."
    )

    st.markdown("---")
    st.markdown("#### Strategy Source")

    source = st.radio(
        "Use strategy from",
        ["Current Config", "Load Saved Strategy"],
        key="comp_source_radio",
        horizontal=True,
    )

    comp_conditions = st.session_state.lab_conditions
    comp_exit_mode  = st.session_state.lab_exit_mode
    comp_stop_pct   = st.session_state.lab_stop_pct
    comp_target_pct = st.session_state.lab_target_pct
    comp_name       = st.session_state.lab_strategy_name

    if source == "Load Saved Strategy":
        saved = _load_strategies()
        user_strategies = {k: v for k, v in saved.items() if v.get("type") not in ("banshee_validation", "comparative_run")}
        if not user_strategies:
            st.warning("No saved strategies found. Save one in the **Build Strategy** tab first.")
            return
        sel = st.selectbox("Select strategy", list(user_strategies.keys()), key="comp_load_select")
        s = user_strategies[sel]
        comp_conditions = [dict(c) for c in s.get("conditions", [])]
        comp_exit_mode  = s.get("exit_mode", EXIT_MODES[0])
        comp_stop_pct   = float(s.get("stop_pct", 2.0))
        comp_target_pct = float(s.get("target_pct", 4.0))
        comp_name       = s.get("strategy_name", sel)
        with st.expander("Strategy conditions", expanded=False):
            for i, cond in enumerate(comp_conditions, 1):
                val_str = f" → `{cond['value']}`" if cond.get("value") is not None else ""
                st.markdown(f"  {i}. **{cond['indicator']}** — *{cond['condition']}*{val_str}")
            st.markdown(f"**Exit:** {comp_exit_mode}")

    st.markdown("---")
    st.markdown("#### Symbol")

    active_sym = st.session_state.get("active_symbol", "") or ""
    default_sym = st.session_state.get("lab_comp_symbol", "") or active_sym
    comp_symbol = st.text_input(
        "Symbol",
        value=default_sym,
        placeholder="e.g. BTC/USD, NVDA",
        key="comp_symbol_input",
    ).strip().upper()
    st.session_state.lab_comp_symbol = comp_symbol

    st.markdown("---")
    st.markdown("#### Timeframes & Lookbacks")

    c1, c2 = st.columns(2)
    with c1:
        sel_tfs = st.multiselect(
            "Timeframes",
            TIMEFRAMES,
            default=["1d", "4h"],
            key="comp_tf_multiselect",
        )
    with c2:
        sel_lbs = st.multiselect(
            "Lookback Periods",
            LOOKBACKS,
            default=["1 year", "2 years"],
            key="comp_lb_multiselect",
        )

    if sel_tfs and sel_lbs:
        n = len(sel_tfs) * len(sel_lbs)
        st.caption(f"{n} combination{'s' if n != 1 else ''} will be run.")

    st.markdown("---")

    run_col, save_col, _ = st.columns([1.5, 1.5, 3])
    with run_col:
        run_all = st.button(
            "▶ Run All",
            type="primary",
            key="comp_run_btn",
            disabled=not (comp_symbol and sel_tfs and sel_lbs),
        )
    with save_col:
        save_all = st.button(
            "💾 Save All Results",
            key="comp_save_btn",
            disabled=not st.session_state.get("lab_comp_results"),
        )

    if not comp_symbol:
        st.caption("Enter a symbol to enable runs.")
    elif not sel_tfs or not sel_lbs:
        st.caption("Select at least one timeframe and one lookback.")

    if run_all and comp_symbol and sel_tfs and sel_lbs:
        combinations = [(tf, lb) for tf in sel_tfs for lb in sel_lbs]
        results = []
        prog = st.progress(0, text="Starting…")
        for i, (tf, lb) in enumerate(combinations):
            prog.progress(i / len(combinations), text=f"Running {comp_symbol} {tf} / {lb}…")
            r = _run_backtest(
                symbol=comp_symbol,
                timeframe=tf,
                lookback=lb,
                conditions=comp_conditions,
                exit_mode=comp_exit_mode,
                stop_pct=comp_stop_pct,
                target_pct=comp_target_pct,
            )
            results.append({
                "strategy_name": comp_name,
                "symbol":        comp_symbol,
                "timeframe":     tf,
                "lookback":      lb,
                "status":        r.get("status"),
                "error":         r.get("error", ""),
                "stats":         r.get("stats", {}),
                "equity_fig":    r.get("equity_fig"),
                "trade_log":     r.get("trade_log"),
                "requested_at":  datetime.now().strftime("%Y-%m-%d %H:%M"),
            })
        prog.progress(1.0, text="Done.")
        st.session_state.lab_comp_results = results
        done = sum(1 for r in results if r["status"] == "done")
        errs = len(results) - done
        msg = f"All {len(results)} runs complete — {done} succeeded"
        if errs:
            msg += f", {errs} failed"
        st.success(msg + ".")

    if save_all and st.session_state.get("lab_comp_results"):
        saved_count = 0
        for r in st.session_state.lab_comp_results:
            if r["status"] == "done":
                key = f"[CR] {r['strategy_name']} {r['symbol']} {r['timeframe']} {r['lookback']}"
                _save_strategy(key, {
                    "type":          "comparative_run",
                    "strategy_name": r["strategy_name"],
                    "symbol":        r["symbol"],
                    "timeframe":     r["timeframe"],
                    "lookback":      r["lookback"],
                    "stats":         r["stats"],
                    "requested_at":  r["requested_at"],
                })
                saved_count += 1
        st.success(f"Saved {saved_count} result{'s' if saved_count != 1 else ''} to strategies.json")

    # ── Results table ──────────────────────────────────────────────────────────
    comp_results = st.session_state.get("lab_comp_results")
    if comp_results:
        st.markdown("---")
        first = comp_results[0]
        st.markdown(f"#### Results — {first['symbol']} · {first['strategy_name']}")
        st.caption(f"Requested: {first.get('requested_at', '—')}")

        rows = []
        for r in comp_results:
            stats = r.get("stats", {})
            if r["status"] == "done":
                rows.append({
                    "Timeframe":    r["timeframe"],
                    "Lookback":     r["lookback"],
                    "Total Return": stats.get("total_return", "—"),
                    "Sharpe":       stats.get("sharpe",       "—"),
                    "Max DD":       stats.get("max_dd",        "—"),
                    "Win Rate":     stats.get("win_rate",      "—"),
                    "# Trades":     stats.get("n_trades",      "—"),
                    "Status":       "✅",
                })
            else:
                rows.append({
                    "Timeframe":    r["timeframe"],
                    "Lookback":     r["lookback"],
                    "Total Return": "—",
                    "Sharpe":       "—",
                    "Max DD":       "—",
                    "Win Rate":     "—",
                    "# Trades":     "—",
                    "Status":       f"❌ {r.get('error', 'failed')[:60]}",
                })

        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)

        done_results = [r for r in comp_results if r["status"] == "done" and r.get("equity_fig")]
        if done_results:
            st.markdown("#### Equity Curves")
            for r in done_results:
                with st.expander(f"{r['timeframe']} / {r['lookback']}", expanded=False):
                    st.plotly_chart(r["equity_fig"], width="stretch")
                    if r.get("trade_log") is not None:
                        st.dataframe(r["trade_log"], width="stretch")


# ─── Main entry point ──────────────────────────────────────────────────────────

def render():
    _init_state()

    st.markdown("<h1>🔬 Signal Lab</h1>", unsafe_allow_html=True)
    st.markdown("Validate indicator timing and entry quality — find what has edge for each asset.")

    build_tab, results_tab, banshee_tab, mtf_tab, comp_tab, disc_tab, live_tab = st.tabs([
        "🛠 Build Strategy",
        "📊 Backtest Results",
        "🦅 Banshee Validation",
        "🔬 MTF Backtest",
        "⚖️ Comparative Runs",
        "🔍 Discovery",        # NEW: test indicators one-at-a-time to find what works
        "📡 Live Snapshot",    # NEW: right-now GO/NO-GO for the active symbol
    ])

    with build_tab:
        _render_build_tab()

    with results_tab:
        _render_results_tab()

    with banshee_tab:
        _render_banshee_validation_tab()

    with mtf_tab:
        _render_mtf_backtest_tab()

    with comp_tab:
        _render_comparative_tab()

    with disc_tab:
        _render_discovery_tab()

    with live_tab:
        _render_live_snapshot_tab()
