"""
micro_engine.py — Banshee Pro Micro Asset Engine
=================================================
This engine handles individual symbol technical analysis.
It calculates EMAs, VWAP, Support/Resistance, and Stoch RSI.
Data is sourced from the unified shared_data cache.
"""

import time
import numpy as np
import pandas as pd
from shared_data import fetch_crypto_ohlcv, fetch_funding_rate
from asset_profiles import get_weight, is_enabled, MOMENTUM_INDICATORS, get_profile, get_effective_profile

# ─── SETTINGS ──────────────────────────────────────────────────────────────────
EMA_FAST   = 20
EMA_MED    = 50
EMA_SLOW   = 200
RSI_PERIOD = 14
SWING_WIN  = 3
ST_PERIOD  = 10
ST_MULT    = 3.0
STOCH_PERIOD = 14
STOCH_K    = 3
STOCH_D    = 3
VWAP_WIN   = 20

MODE_CONFIG = {
    "long_term": {
        "timeframes": ["1wk", "1d", "4h"],
        "tf_labels":  ["Weekly", "Daily", "4H"],
        "weights":    [0.40, 0.35, 0.25],
    },
    "swing": {
        "timeframes": ["1d", "4h", "1h"],
        "tf_labels":  ["Daily", "4H", "1H"],
        "weights":    [0.40, 0.35, 0.25],
    },
    "sniper": {
        "timeframes": ["4h", "1h", "15m"],
        "tf_labels":  ["4H", "1H", "15m"],
        "weights":    [0.40, 0.35, 0.25],
    },
}

# ─── DATA LOADING VIA SHARED_DATA ───────────────────────────────────────────────

def fetch_stock(symbol: str, timeframe: str) -> tuple[pd.DataFrame, str | None]:
    import data_providers
    limits = {"1wk": 520, "1d": 500, "4h": 300, "1h": 300, "15m": 300}
    if timeframe not in limits:
        return pd.DataFrame(), f"Invalid timeframe {timeframe}"
    df = data_providers.fetch_ohlcv(symbol, timeframe, limits[timeframe])
    if df.empty:
        return pd.DataFrame(), f"No data available for {symbol} {timeframe} — check Settings → Data Sources"
    df_raw = df.copy()
    try:
        required = {"timestamp", "open", "high", "low", "close", "volume"}
        if not required.issubset(df.columns):
            raise ValueError(f"Missing columns: {required - set(df.columns)}")
        return df[list(required)].reset_index(drop=True), None
    except Exception as e:
        try:
            from shared_data import load_providers
            import banshee_ai
            import json
            import re
            from core_state import _log_error

            providers = load_providers()
            if not providers.get("allow_ai_data_rescue", True):
                return pd.DataFrame(), f"Data parsing failed (AI rescue disabled): {e}"

            ai_cfg = providers.get("AI_API")
            if ai_cfg and ai_cfg.get("type") and ai_cfg.get("key"):
                raw_data = str(df_raw.head().to_dict(orient="records"))
                prompt = (f"The data format changed and broke my pandas script. Error: {e}\n"
                          f"Look at this raw data: {raw_data}\n"
                          f"Tell me the new column names for Date, Open, High, Low, Close, and Volume. "
                          f"Return ONLY a Python dictionary mapping the exact old names from the raw data to the new target names ('timestamp', 'open', 'high', 'low', 'close', 'volume'). "
                          f"Do not include any other text.")
                _log_error("ai-rescue", e)
                response = banshee_ai.call_ai(ai_cfg, prompt)
                match = re.search(r'\{.*\}', response, re.DOTALL)
                if match:
                    rename_map = json.loads(match.group(0))
                    _VALID_OHLCV_COLS = {"open", "high", "low", "close", "volume", "timestamp"}
                    bad_cols = [v for v in rename_map.values() if v not in _VALID_OHLCV_COLS]
                    if bad_cols:
                        return pd.DataFrame(), f"AI rescue rejected: invalid column names returned: {bad_cols}"
                    df = df_raw.rename(columns=rename_map)
                    df["timestamp"] = pd.to_datetime(df["timestamp"]).dt.tz_localize(None)
                    df = df[["timestamp", "open", "high", "low", "close", "volume"]]
                    return df.reset_index(drop=True), None
        except Exception as ai_err:
            return pd.DataFrame(), f"Data parsing failed, and self-healing AI rescue failed: {ai_err}"
        return pd.DataFrame(), f"Data parsing failed due to format change: {e}"


ALL_TIMEFRAMES = ["1wk", "1d", "4h", "1h", "15m"]

def load_and_prepare(symbol: str, mode: str = "active", is_crypto: bool = None) -> dict:
    """Fetch and prepare all 5 timeframes regardless of mode.
    Storing all TFs enables free mode switching without re-fetching."""
    if is_crypto is None:
        is_crypto = ("/" in symbol) or ("-USD" in symbol)

    # Match equity depth so crypto charts show more history. Deeper sources honour the higher
    # limit; per-request-capped sources (e.g. Coinbase ~300) simply return what they can.
    _crypto_limits = {"1wk": 520, "1d": 500, "4h": 300, "1h": 300, "15m": 300}
    tfs = {}
    for tf in ALL_TIMEFRAMES:
        if is_crypto:
            df, _ = fetch_crypto_ohlcv(symbol, tf, _crypto_limits.get(tf, 300))
        else:
            df, _ = fetch_stock(symbol, tf)
        tfs[tf] = add_all_indicators(df) if not df.empty else df

    return tfs


# ─── INDICATORS ────────────────────────────────────────────────────────────────

def add_supertrend(df: pd.DataFrame, period: int = ST_PERIOD, mult: float = ST_MULT) -> pd.DataFrame:
    high  = df["high"].values
    low   = df["low"].values
    close = df["close"].values

    tr    = np.maximum(high - low,
            np.maximum(np.abs(high - np.roll(close, 1)),
                       np.abs(low  - np.roll(close, 1))))
    tr[0] = high[0] - low[0]

    # Seed ATR with the mean of the first `period` TRs (proper RMA warmup).
    # Starting from a single bar (tr[0]) causes severe underestimation on short
    # timeframes (15m, 1h) where history is capped by the yfinance API.
    atr   = np.zeros(len(df))
    seed_end = min(period, len(df))
    atr[seed_end - 1] = np.mean(tr[:seed_end])
    alpha  = 1 / period
    for i in range(seed_end, len(df)):
        atr[i] = alpha * tr[i] + (1 - alpha) * atr[i - 1]
    # Fill the warmup window with the seed value so downstream code sees no zeros
    atr[:seed_end - 1] = atr[seed_end - 1]

    hl2 = (high + low) / 2
    raw_upper = hl2 + mult * atr
    raw_lower = hl2 - mult * atr

    upper, lower = np.zeros(len(df)), np.zeros(len(df))
    trend   = np.ones(len(df), dtype=bool)
    st_line = np.zeros(len(df))
    upper[0], lower[0] = raw_upper[0], raw_lower[0]

    for i in range(1, len(df)):
        upper[i] = raw_upper[i] if raw_upper[i] < upper[i-1] or close[i-1] > upper[i-1] else upper[i-1]
        lower[i] = raw_lower[i] if raw_lower[i] > lower[i-1] or close[i-1] < lower[i-1] else lower[i-1]

        if trend[i-1]:
            if close[i] <= lower[i]:
                trend[i], st_line[i] = False, upper[i]
            else:
                trend[i], st_line[i] = True,  lower[i]
        else:
            if close[i] >= upper[i]:
                trend[i], st_line[i] = True,  lower[i]
            else:
                trend[i], st_line[i] = False, upper[i]

    df["supertrend"] = st_line
    df["st_bull"]    = trend
    df["atr"]        = atr
    return df

def add_adx(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    if len(df) < period * 3:
        df["adx"] = np.nan
        return df

    high, low, close = df["high"].values, df["low"].values, df["close"].values
    n = len(df)
    prev_close, prev_high, prev_low = np.roll(close, 1), np.roll(high, 1), np.roll(low, 1)
    prev_close[0], prev_high[0], prev_low[0] = close[0], high[0], low[0]

    tr = np.maximum(high - low, np.maximum(np.abs(high - prev_close), np.abs(low - prev_close)))
    dm_plus  = np.where((high - prev_high) > (prev_low - low), np.maximum(high - prev_high, 0.0), 0.0)
    dm_minus = np.where((prev_low - low) > (high - prev_high), np.maximum(prev_low - low,  0.0), 0.0)
    dm_plus[0] = dm_minus[0] = 0.0

    atr_w, dmp_w, dmm_w = np.zeros(n), np.zeros(n), np.zeros(n)
    atr_w[period] = np.sum(tr[1:period + 1])
    dmp_w[period] = np.sum(dm_plus[1:period + 1])
    dmm_w[period] = np.sum(dm_minus[1:period + 1])
    for i in range(period + 1, n):
        atr_w[i] = atr_w[i-1] - atr_w[i-1] / period + tr[i]
        dmp_w[i] = dmp_w[i-1] - dmp_w[i-1] / period + dm_plus[i]
        dmm_w[i] = dmm_w[i-1] - dmm_w[i-1] / period + dm_minus[i]

    with np.errstate(divide="ignore", invalid="ignore"):
        di_plus  = np.where(atr_w > 0, 100 * dmp_w / atr_w, 0.0)
        di_minus = np.where(atr_w > 0, 100 * dmm_w / atr_w, 0.0)
        dx       = np.where((di_plus + di_minus) > 0, 100 * np.abs(di_plus - di_minus) / (di_plus + di_minus), 0.0)

    adx = np.zeros(n)
    start = 2 * period
    if start < n:
        adx[start] = np.mean(dx[period:start + 1])
        for i in range(start + 1, n):
            adx[i] = (adx[i-1] * (period - 1) + dx[i]) / period

    df["adx"] = np.where(adx == 0, np.nan, adx)
    return df

def add_stoch_rsi(df: pd.DataFrame, period: int=STOCH_PERIOD, k_smooth: int=STOCH_K, d_smooth: int=STOCH_D) -> pd.DataFrame:
    if df.empty or "rsi" not in df.columns:
        df["stoch_k"], df["stoch_d"] = np.nan, np.nan
        return df

    rsi = df["rsi"]
    rsi_low = rsi.rolling(period, min_periods=1).min()
    rsi_high = rsi.rolling(period, min_periods=1).max()
    raw_stoch = (rsi - rsi_low) / (rsi_high - rsi_low).replace(0, np.nan) * 100

    df["stoch_k"] = raw_stoch.rolling(k_smooth, min_periods=1).mean()
    df["stoch_d"] = df["stoch_k"].rolling(d_smooth, min_periods=1).mean()
    return df

def add_vwap(df: pd.DataFrame, window: int=VWAP_WIN) -> pd.DataFrame:
    typical_price = (df["high"] + df["low"] + df["close"]) / 3
    tp_vol = typical_price * df["volume"]
    rolling_tpv = tp_vol.rolling(window=window, min_periods=5).sum()
    rolling_vol = df["volume"].rolling(window=window, min_periods=5).sum()
    df["vwap"] = rolling_tpv / rolling_vol.replace(0, np.nan)
    return df

def identify_swings(df: pd.DataFrame, window: int=SWING_WIN) -> pd.DataFrame:
    roll_max = df["high"].rolling(window * 2 + 1, center=True).max()
    roll_min = df["low"].rolling(window * 2 + 1, center=True).min()
    df["swing_high"] = np.where(df["high"] == roll_max, df["high"], np.nan)
    df["swing_low"]  = np.where(df["low"]  == roll_min, df["low"],  np.nan)
    if len(df) > window:
        df.loc[df.index[-window:], ["swing_high", "swing_low"]] = np.nan
    return df

def detect_rsi_divergence(df: pd.DataFrame) -> str | None:
    if df.empty or "rsi" not in df.columns: return None
    
    if "swing_low" in df.columns:
        lows = df[df["swing_low"].notna()].tail(3)
        if len(lows) >= 2 and lows.iloc[-1]["low"] < lows.iloc[-2]["low"] and lows.iloc[-1]["rsi"] > lows.iloc[-2]["rsi"] and not np.isnan(lows.iloc[-1]["rsi"]):
            return "BULLISH"

    if "swing_high" in df.columns:
        highs = df[df["swing_high"].notna()].tail(3)
        if len(highs) >= 2 and highs.iloc[-1]["high"] > highs.iloc[-2]["high"] and highs.iloc[-1]["rsi"] < highs.iloc[-2]["rsi"] and not np.isnan(highs.iloc[-1]["rsi"]):
            return "BEARISH"

    return None

def add_mfi(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """Money Flow Index — volume-weighted RSI.
    Overbought threshold: 80 (vs RSI's 70). Oversold: 20 (vs RSI's 30).
    Integrating volume means a spike or drop needs actual capital behind it,
    which is what filters out ETH's lightweight fake-outs."""
    if len(df) < period + 1 or "volume" not in df.columns:
        df["mfi"] = np.nan
        return df

    typical  = (df["high"] + df["low"] + df["close"]) / 3
    raw_flow = typical * df["volume"]

    pos_flow = raw_flow.where(typical > typical.shift(1), 0.0)
    neg_flow = raw_flow.where(typical < typical.shift(1), 0.0)

    pos_mf = pos_flow.rolling(period, min_periods=period).sum()
    neg_mf = neg_flow.rolling(period, min_periods=period).sum()

    # Avoid division by zero — treat pure positive flow as MFI = 100
    mfi = np.where(
        neg_mf == 0,
        100.0,
        100.0 - (100.0 / (1.0 + pos_mf / neg_mf.replace(0, np.nan)))
    )
    df["mfi"] = mfi
    return df


def add_fisher(df: pd.DataFrame, period: int = 10) -> pd.DataFrame:
    """Fisher Transform — converts prices into a Gaussian (normal) distribution.
    Makes exhaustion turning points stand out as near-vertical spikes rather than
    ambiguous curve shapes. Signal line = previous bar's Fisher value.
    Cross at extreme (|Fisher| > 1.5) = statistically significant reversal trigger."""
    if len(df) < period + 1:
        df["fisher"]        = np.nan
        df["fisher_signal"] = np.nan
        return df

    high_p = df["high"].rolling(period, min_periods=period).max()
    low_p  = df["low"].rolling(period, min_periods=period).min()

    hl_range = (high_p - low_p).replace(0, np.nan)
    # Normalize close into (-1, 1), clamped at ±0.999 to keep log finite
    value = (2.0 * ((df["close"] - low_p) / hl_range) - 1.0).clip(-0.999, 0.999)

    fisher = 0.5 * np.log((1.0 + value) / (1.0 - value))
    df["fisher"]        = fisher
    df["fisher_signal"] = fisher.shift(1)   # One-bar lag = signal line
    return df


def add_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or len(df) < 30: return df

    df["ema_20"]  = df["close"].ewm(span=EMA_FAST, adjust=False).mean()
    df["ema_50"]  = df["close"].ewm(span=EMA_MED,  adjust=False).mean()
    df["ema_200"] = df["close"].ewm(span=EMA_SLOW, adjust=False).mean()

    delta = df["close"].diff()
    gain  = delta.where(delta > 0, 0).rolling(RSI_PERIOD).mean()
    loss  = (-delta.where(delta < 0, 0)).rolling(RSI_PERIOD).mean()
    df["rsi"] = 100 - (100 / (1 + gain / loss.replace(0, np.nan)))

    df = add_stoch_rsi(df)

    e12 = df["close"].ewm(span=12, adjust=False).mean()
    e26 = df["close"].ewm(span=26, adjust=False).mean()
    df["macd"]        = e12 - e26
    df["macd_signal"] = df["macd"].ewm(span=9, adjust=False).mean()
    df["macd_hist"]   = df["macd"] - df["macd_signal"]

    direction = np.sign(df["close"].diff()).fillna(0)
    df["obv"]     = (direction * df["volume"]).cumsum()
    df["obv_ema"] = df["obv"].ewm(span=20, adjust=False).mean()
    df["vol_ma"]  = df["volume"].rolling(20).mean()

    # ── Slow Bollinger Band (20 SMA / close / 2σ) ────────────────────────────
    # The classic BB — shows where price sits within medium-term volatility.
    df["bb_mid"]   = df["close"].rolling(20).mean()
    df["bb_std"]   = df["close"].rolling(20).std()
    df["bb_upper"] = df["bb_mid"] + 2 * df["bb_std"]
    df["bb_lower"] = df["bb_mid"] - 2 * df["bb_std"]

    # ── Fast Bollinger Band (4 SMA / open / 2σ) ──────────────────────────────
    # Short-term volatility envelope using the OPEN price.
    # Why open? The open reflects the market's consensus at the START of a bar,
    # before buyers and sellers duke it out. It's less reactive than close.
    # Two-band system insight:
    #   Price inside fast bands  → calm, normal conditions
    #   Price between fast/slow  → momentum building but not yet exhausted
    #   Price outside slow bands → extended / exhaustion zone
    df["bb_fast_mid"]   = df["open"].rolling(4, min_periods=2).mean()
    df["bb_fast_std"]   = df["open"].rolling(4, min_periods=2).std()
    df["bb_fast_upper"] = df["bb_fast_mid"] + 2 * df["bb_fast_std"]
    df["bb_fast_lower"] = df["bb_fast_mid"] - 2 * df["bb_fast_std"]

    # Position ratio: 0.0 = at lower band, 1.0 = at upper band, outside = <0 or >1
    slow_width            = (df["bb_upper"] - df["bb_lower"]).replace(0, np.nan)
    fast_width            = (df["bb_fast_upper"] - df["bb_fast_lower"]).replace(0, np.nan)
    df["bb_pos"]          = (df["close"] - df["bb_lower"])      / slow_width
    df["bb_fast_pos"]     = (df["close"] - df["bb_fast_lower"]) / fast_width

    # Squeeze: fast bands are entirely inside slow bands = energy coiling
    # (neither bullish nor bearish alone, but signals a breakout is coming)
    df["bb_squeeze"] = (
        (df["bb_fast_upper"] < df["bb_upper"]) &
        (df["bb_fast_lower"] > df["bb_lower"])
    )

    df = add_vwap(df)
    df = add_supertrend(df)
    df = add_adx(df)
    df = identify_swings(df)
    df = add_mfi(df)
    df = add_fisher(df)
    return df


# ─── ANALYSIS ──────────────────────────────────────────────────────────────────

def get_trend(df: pd.DataFrame) -> str:
    if df.empty or "swing_high" not in df.columns: return "UNKNOWN"
    highs = df[df["swing_high"].notna()]["high"]
    lows  = df[df["swing_low"].notna()]["low"]
    if len(highs) >= 2 and len(lows) >= 2:
        if highs.iloc[-1] > highs.iloc[-2] and lows.iloc[-1] > lows.iloc[-2]: return "UPTREND"
        if highs.iloc[-1] < highs.iloc[-2] and lows.iloc[-1] < lows.iloc[-2]: return "DOWNTREND"
    if "ema_20" in df.columns and "ema_50" in df.columns:
        last = df.iloc[-1]
        if last["ema_20"] > last["ema_50"]: return "UPTREND"
        if last["ema_20"] < last["ema_50"]: return "DOWNTREND"
    return "RANGING"

def _psychological_levels(price: float) -> list:
    if   price > 10_000: step = 5_000
    elif price > 1_000:  step = 1_000
    elif price > 100:    step = 50
    elif price > 10:     step = 5
    else:                step = 1
    base = round(price / step) * step
    return [base + i * step for i in range(-6, 7) if (base + i * step) > 0]

def find_sr_levels(df: pd.DataFrame, price: float, tolerance: float=0.005) -> tuple:
    if df.empty: return [], []
    highs = df[df["swing_high"].notna()]["swing_high"].values
    lows  = df[df["swing_low"].notna()]["swing_low"].values
    psych = np.array(_psychological_levels(price))

    all_levels = sorted(np.concatenate([highs, lows, psych]))
    clusters, i = [], 0
    while i < len(all_levels):
        group = [all_levels[i]]
        j = i + 1
        while j < len(all_levels) and all_levels[j] <= all_levels[i] * (1 + tolerance):
            group.append(all_levels[j])
            j += 1
        clusters.append(float(np.mean(group)))
        i = j

    support = sorted([l for l in clusters if l < price * 0.999], reverse=True)[:4]
    resistance = sorted([l for l in clusters if l > price * 1.001])[:4]
    return support, resistance

def analyze_volume(df: pd.DataFrame) -> tuple:
    if df.empty or "vol_ma" not in df.columns: return "UNKNOWN", None
    last = df.iloc[-1]
    vol_ratio = last["volume"] / last["vol_ma"] if last["vol_ma"] > 0 else 1
    obv_up = last["obv"] > last["obv_ema"]
    high_vol = vol_ratio > 1.4

    if high_vol and obv_up:     return "STRONG BUYING VOLUME", True
    if high_vol and not obv_up: return "STRONG SELLING VOLUME", False
    if obv_up:                  return "ACCUMULATION (OBV rising)", True
    return "DISTRIBUTION (OBV falling)", False

def apply_regime_weights(profile: dict, regime_mults: dict) -> dict:
    """
    Return a copy of the asset profile with indicator weights scaled by
    regime multipliers from knowledge_graph.get_regime_weights().

    The asset profile controls *which* indicators are trusted for this symbol.
    The regime multipliers control *how much* to trust them given current
    macro conditions. Multiplying them gives the effective weight.

    Only weights are modified — enabled/disabled flags are untouched so the
    asset profile's structural decisions are always respected.
    """
    if not regime_mults:
        return profile
    import copy
    p = copy.deepcopy(profile)
    for key, mult in regime_mults.items():
        if key in p.get("indicators", {}):
            p["indicators"][key]["weight"] = round(
                max(0.0, p["indicators"][key]["weight"] * mult), 4
            )
    return p


def score_timeframe(df: pd.DataFrame, profile: dict = None) -> tuple:
    """
    Score one timeframe's bullish/bearish strength.

    When `profile` is provided (from asset_profiles.get_profile), each indicator's
    contribution is scaled by its configured weight. Without a profile the function
    behaves identically to before — default weights reproduce the old hardwired values.

    Returns (bull_score, bear_score, signals_list).
    """
    if df.empty or len(df) < 5:
        return 0, 0, []
    last, prev = df.iloc[-1], df.iloc[-2]
    bull, bear, signals = 0.0, 0.0, []
    price = float(last["close"])

    # ── Volume gate ───────────────────────────────────────────────────────────
    # When enabled via profile, momentum indicators are suppressed on low-volume
    # bars. Structural signals (Supertrend, EMA, BB) fire regardless.
    volume_gate = profile.get("volume_gate", False) if profile else False
    low_volume  = False
    if volume_gate and "volume" in df.columns:
        vol_ma = df["volume"].rolling(20, min_periods=1).mean().iloc[-1]
        if not np.isnan(vol_ma) and vol_ma > 0:
            low_volume = float(last.get("volume", vol_ma)) < vol_ma

    def gated(key: str) -> bool:
        """Return True when volume gate is active and this key is a momentum indicator."""
        return low_volume and key in MOMENTUM_INDICATORS

    # ── Supertrend ────────────────────────────────────────────────────────────
    if not profile or is_enabled(profile, "supertrend"):
        w = get_weight(profile, "supertrend") if profile else 2.0
        st_bull = bool(last.get("st_bull", True))
        if st_bull:
            bull += w
            signals.append(("Supertrend", "BULLISH", "Price is above Supertrend line."))
        else:
            bear += w
            signals.append(("Supertrend", "BEARISH", "Price is below Supertrend line."))

    # ── EMA Stack (20/50/200) ─────────────────────────────────────────────────
    if not profile or is_enabled(profile, "ema_stack"):
        w = get_weight(profile, "ema_stack") if profile else 2.0
        e20, e50, e200 = last["ema_20"], last["ema_50"], last["ema_200"]
        if e20 > e50 > e200:
            bull += w;       signals.append(("EMA", "BULLISH",        "Stacked bullish."))
        elif e20 < e50 < e200:
            bear += w;       signals.append(("EMA", "BEARISH",        "Stacked bearish."))
        elif e20 > e50:
            bull += w * 0.5; signals.append(("EMA", "LEANING BULLISH","Short above medium."))
        else:
            bear += w * 0.5; signals.append(("EMA", "LEANING BEARISH","Short below medium."))

    # ── Price vs EMA50 ────────────────────────────────────────────────────────
    if not profile or is_enabled(profile, "ema_price"):
        w   = get_weight(profile, "ema_price") if profile else 1.0
        e50 = float(last["ema_50"])
        if price > e50:
            bull += w; signals.append(("Price/EMA50", "BULLISH", "Buyers controlling."))
        else:
            bear += w; signals.append(("Price/EMA50", "BEARISH", "Sellers controlling."))

    # ── RSI ───────────────────────────────────────────────────────────────────
    # Default weight 1.5 → strong tier (4/3 × 1.5 ≈ 2.0), weak tier (2/3 × 1.5 ≈ 1.0)
    # — reproduces old +2 / +1 constants exactly at default weight.
    if (not profile or is_enabled(profile, "rsi")) and not gated("rsi"):
        w      = get_weight(profile, "rsi") if profile else 1.5
        strong = w * (4 / 3)
        weak   = w * (2 / 3)
        rsi    = last.get("rsi", 50)
        if rsi < 30:
            bull += strong; signals.append(("RSI", "OVERSOLD",         "Extremely oversold."))
        elif rsi > 70:
            bear += strong; signals.append(("RSI", "OVERBOUGHT",       "Extremely overbought."))
        elif rsi >= 55:
            bull += weak;   signals.append(("RSI", "BULLISH MOMENTUM", "Above midline."))
        elif rsi <= 45:
            bear += weak;   signals.append(("RSI", "BEARISH MOMENTUM", "Below midline."))

    # ── Stoch RSI ─────────────────────────────────────────────────────────────
    if (not profile or is_enabled(profile, "stoch_rsi")) and not gated("stoch_rsi"):
        w      = get_weight(profile, "stoch_rsi") if profile else 1.5
        strong = w * (4 / 3)
        weak   = w * (2 / 3)
        k      = float(last.get("stoch_k", 50))
        d      = float(last.get("stoch_d", k))
        prev_k = float(prev.get("stoch_k", k))
        prev_d = float(prev.get("stoch_d", d))
        just_crossed_up = (k > d) and (prev_k <= prev_d)
        just_crossed_dn = (k < d) and (prev_k >= prev_d)
        if just_crossed_up and k < 50:
            bull += strong; signals.append(("Stoch RSI", "FRESH BULLISH CROSS", "Momentum turning UP."))
        elif just_crossed_dn and k > 50:
            bear += strong; signals.append(("Stoch RSI", "FRESH BEARISH CROSS", "Momentum turning DOWN."))
        elif k < 20:
            bull += weak;   signals.append(("Stoch RSI", "OVERSOLD",  "Momentum exhausted to downside."))
        elif k > 80:
            bear += weak;   signals.append(("Stoch RSI", "OVERBOUGHT","Momentum stretched upside."))

    # ── MACD ──────────────────────────────────────────────────────────────────
    if (not profile or is_enabled(profile, "macd")) and not gated("macd"):
        w        = get_weight(profile, "macd") if profile else 2.0
        cross_up = last["macd"] > last["macd_signal"] and prev["macd"] <= prev["macd_signal"]
        cross_dn = last["macd"] < last["macd_signal"] and prev["macd"] >= prev["macd_signal"]
        if cross_up:
            bull += w; signals.append(("MACD", "FRESH BULLISH CROSS", "Buyers momentum."))
        elif cross_dn:
            bear += w; signals.append(("MACD", "FRESH BEARISH CROSS", "Sellers momentum."))

    # ── OBV vs OBV EMA ────────────────────────────────────────────────────────
    if (not profile or is_enabled(profile, "obv")) and not gated("obv"):
        w      = get_weight(profile, "obv") if profile else 1.0
        obv_up = last["obv"] > last["obv_ema"]
        if obv_up:
            bull += w; signals.append(("OBV", "ACCUMULATION", "Smart money buying."))
        else:
            bear += w; signals.append(("OBV", "DISTRIBUTION", "Selling pressure."))

    # ── OBV Leading Accumulation ──────────────────────────────────────────────
    if (not profile or is_enabled(profile, "obv_leading")) and not gated("obv_leading") and len(df) >= 5:
        obv_5ago         = df.iloc[-5]["obv"]
        price_5ago       = df.iloc[-5]["close"]
        obv_rising_early = last["obv"] > obv_5ago
        price_flat_or_dn = float(last["close"]) <= float(price_5ago) * 1.005
        if obv_rising_early and price_flat_or_dn:
            w = get_weight(profile, "obv_leading") if profile else 2.0
            bull += w
            signals.append(("OBV", "LEADING ACCUMULATION", "Smart money buying before price moves."))

    # ── BB Slow (20 SMA / close / 2σ) ────────────────────────────────────────
    if not profile or is_enabled(profile, "bb_slow"):
        w        = get_weight(profile, "bb_slow") if profile else 1.0
        bb_width = last["bb_upper"] - last["bb_lower"]
        bb_pos   = (price - last["bb_lower"]) / bb_width if bb_width > 0 else 0.5
        if bb_pos < 0.1:
            bull += w; signals.append(("BB", "AT LOWER BAND", "Bounce zone."))
        elif bb_pos > 0.9:
            bear += w; signals.append(("BB", "AT UPPER BAND", "Pullback zone."))

    # ── BB Fast (4 SMA / open / 2σ) — dual-band position signals ─────────────
    # Price zones: below fast lower = short-term oversold; above fast upper = exhaustion;
    # upper half of fast bands = bullish momentum quality; lower half = bearish.
    # Squeeze (fast inside slow) = energy coiling, no directional bias yet.
    if (not profile or is_enabled(profile, "bb_fast")) and "bb_fast_upper" in df.columns:
        w            = get_weight(profile, "bb_fast") if profile else 1.0
        bb_fast_pos  = float(last.get("bb_fast_pos", 0.5))
        bb_squeeze   = bool(last.get("bb_squeeze",   False))
        if bb_squeeze:
            signals.append(("BB Fast", "SQUEEZE", "Fast bands inside slow — breakout loading."))
        elif bb_fast_pos < 0:
            bull += w;       signals.append(("BB Fast", "BELOW FAST LOWER", "Short-term oversold; bounce likely."))
        elif bb_fast_pos > 1:
            bear += w;       signals.append(("BB Fast", "ABOVE FAST UPPER", "Short-term exhaustion."))
        elif bb_fast_pos >= 0.6:
            bull += w * 0.5; signals.append(("BB Fast", "UPPER HALF", "Price in bullish zone of fast bands."))
        elif bb_fast_pos <= 0.4:
            bear += w * 0.5; signals.append(("BB Fast", "LOWER HALF", "Price in bearish zone of fast bands."))

    # ── VWAP ──────────────────────────────────────────────────────────────────
    if (not profile or is_enabled(profile, "vwap")) and "vwap" in df.columns and not np.isnan(last.get("vwap", float("nan"))):
        w        = get_weight(profile, "vwap") if profile else 1.0
        vwap     = float(last["vwap"])
        vwap_pct = (price - vwap) / vwap * 100
        if vwap_pct > 0.5:
            bull += w; signals.append(("VWAP", "ABOVE VWAP", "Buyers winning heavily."))
        elif vwap_pct < -0.5:
            bear += w; signals.append(("VWAP", "BELOW VWAP", "Sellers winning heavily."))

    # ── MFI (Money Flow Index) ────────────────────────────────────────────────
    # Volume-weighted momentum — a spike here needs real capital behind it.
    # Overbought threshold is 80 (not 70 like RSI) because MFI is harder to push.
    if (not profile or is_enabled(profile, "mfi")) and "mfi" in df.columns:
        mfi_raw = last.get("mfi", np.nan)
        if not (isinstance(mfi_raw, float) and np.isnan(mfi_raw)):
            w      = get_weight(profile, "mfi") if profile else 1.5
            strong = w * (4 / 3)
            weak   = w * (2 / 3)
            mfi_v  = float(mfi_raw)
            if mfi_v < 20:
                bull += strong; signals.append(("MFI", "OVERSOLD",       "Volume-backed demand exhausted — reversal likely."))
            elif mfi_v > 80:
                bear += strong; signals.append(("MFI", "OVERBOUGHT",     "Volume-backed supply pressure — reversal likely."))
            elif mfi_v >= 55:
                bull += weak;   signals.append(("MFI", "BULLISH FLOW",   "Positive money flow above midline."))
            elif mfi_v <= 45:
                bear += weak;   signals.append(("MFI", "BEARISH FLOW",   "Negative money flow below midline."))

    # ── Fisher Transform ──────────────────────────────────────────────────────
    # Signal line crossover at a statistical extreme (|Fisher| > 1.5) = genuine
    # exhaustion. A cross in the middle is a weak signal; a cross at ±1.5+ is rare
    # and meaningful — exactly what ETH needs to filter out the noise.
    if (not profile or is_enabled(profile, "fisher")) and "fisher" in df.columns:
        f_raw  = last.get("fisher",        np.nan)
        fs_raw = last.get("fisher_signal", np.nan)
        pf_raw = prev.get("fisher",        np.nan)
        ps_raw = prev.get("fisher_signal", np.nan)
        if not any(isinstance(x, float) and np.isnan(x) for x in [f_raw, fs_raw, pf_raw, ps_raw]):
            w          = get_weight(profile, "fisher") if profile else 1.5
            f_v, fs_v  = float(f_raw), float(fs_raw)
            pf_v, ps_v = float(pf_raw), float(ps_raw)
            bull_cross = f_v > fs_v and pf_v <= ps_v
            bear_cross = f_v < fs_v and pf_v >= ps_v
            if bull_cross and f_v < -1.5:
                bull += w * (4/3); signals.append(("Fisher", "BULLISH EXTREME CROSS", "Reversal signal at statistical floor — high conviction."))
            elif bear_cross and f_v > 1.5:
                bear += w * (4/3); signals.append(("Fisher", "BEARISH EXTREME CROSS", "Reversal signal at statistical ceiling — high conviction."))
            elif bull_cross:
                bull += w * (2/3); signals.append(("Fisher", "BULLISH CROSS",         "Momentum flipping up."))
            elif bear_cross:
                bear += w * (2/3); signals.append(("Fisher", "BEARISH CROSS",         "Momentum flipping down."))

    return bull, bear, signals

def compute_verdict(trend_slow, trend_mid, trend_fast,
                    s_bull, s_bear, m_bull, m_bear, f_bull, f_bear,
                    slow_adx=None, rsi_divergence=None) -> tuple:
    total_bull = s_bull * 0.40 + m_bull * 0.35 + f_bull * 0.25
    total_bear = s_bear * 0.40 + m_bear * 0.35 + f_bear * 0.25

    trends     = [trend_slow, trend_mid, trend_fast]
    bull_count = trends.count("UPTREND")
    bear_count = trends.count("DOWNTREND")

    if bull_count == 3:   total_bull += 3.5
    elif bull_count == 2: total_bull += 1.5
    if bear_count == 3:   total_bear += 3.5
    elif bear_count == 2: total_bear += 1.5

    edge = total_bull - total_bear

    if   edge >=  5: verdict = "STRONG BUY"
    elif edge >=  2: verdict = "BUY SETUP"
    elif edge <= -5: verdict = "STRONG SELL"
    elif edge <= -2: verdict = "SELL SETUP"
    else:            verdict = "WAIT — NO TRADE"

    if slow_adx is not None and not np.isnan(slow_adx) and slow_adx < 20:
        if verdict == "STRONG BUY": verdict = "BUY SETUP"
        elif verdict == "STRONG SELL": verdict = "SELL SETUP"

    # ── PRE-SIGNAL: fires before full trend confirmation ──────────────────────
    # Does NOT override the main verdict — it's an additive early-warning layer.
    pre_signal = None
    # Bullish pre-signal: RSI divergence on slow TF, OR 2/3 TFs bullish with
    # slow TF already leaning long but edge hasn't crossed the BUY SETUP threshold yet.
    if verdict in ("WAIT — NO TRADE", "BUY SETUP"):
        if rsi_divergence == "BULLISH":
            pre_signal = "PRE-SIGNAL LONG"
        elif bull_count >= 2 and s_bull > s_bear and 0 < edge < 2:
            pre_signal = "PRE-SIGNAL LONG"
    # Bearish pre-signal
    if verdict in ("WAIT — NO TRADE", "SELL SETUP"):
        if rsi_divergence == "BEARISH":
            pre_signal = "PRE-SIGNAL SHORT"
        elif bear_count >= 2 and s_bear > s_bull and -2 < edge < 0:
            pre_signal = "PRE-SIGNAL SHORT"

    return verdict, total_bull, total_bear, pre_signal

def compute_entry_quality(verdict: str, fast_df: pd.DataFrame, slow_adx: float, funding: dict) -> dict:
    if fast_df.empty or verdict == "WAIT — NO TRADE":
        return {"quality": "WAIT", "reasons": ["No directional edge — signals are conflicting."]}

    is_bearish = verdict in ("STRONG SELL", "SELL SETUP")
    is_bullish = verdict in ("STRONG BUY",  "BUY SETUP")
    last       = fast_df.iloc[-1]

    wait_reasons, caution_reasons = [], []

    if "stoch_k" in fast_df.columns:
        k = float(last.get("stoch_k", 50))
        if not np.isnan(k):
            if is_bearish and k < 25: wait_reasons.append("Stoch RSI is already oversold for shorts.")
            elif is_bullish and k > 75: wait_reasons.append("Stoch RSI is already overbought for longs.")
    if "rsi" in fast_df.columns:
        rsi = float(last.get("rsi", 50))
        if not np.isnan(rsi):
            if is_bearish and rsi < 35: wait_reasons.append("Fast RSI is oversold.")
            elif is_bullish and rsi > 65: wait_reasons.append("Fast RSI is overbought.")
            
    if slow_adx is not None and not np.isnan(float(slow_adx)) and float(slow_adx) < 20:
        caution_reasons.append("Choppy market (ADX < 20). False breakouts abound.")
        
    if funding and funding.get("rate_pct") is not None:
        rate = funding["rate_pct"]
        if is_bearish and rate < -0.05: caution_reasons.append("Short side extremely crowded — squeeze risk.")
        elif is_bullish and rate > 0.05: caution_reasons.append("Long side extremely crowded — cascade risk.")

    if wait_reasons: return {"quality": "WAIT", "reasons": wait_reasons + caution_reasons}
    elif caution_reasons: return {"quality": "CAUTION", "reasons": caution_reasons}
    return {"quality": "READY", "reasons": ["All timing conditions are clear."]}

def run_analysis(symbol: str, mode: str, tfs: dict, domino_phase: int = 0, sensors: dict = None) -> dict:
    """Full quantitative analysis given a set of pre-calculated dataframes per timeframe.

    When `sensors` is provided (full macro_engine output), regime gating is applied:
    the asset profile weights are scaled by regime multipliers before scoring.
    This makes the verdict sensitive to whether we are in FEAR, CAUTION, TRENDING,
    or NEUTRAL macro conditions — not just the raw indicator stack.
    """
    mcfg = MODE_CONFIG[mode]
    timeframes, labels = mcfg["timeframes"], mcfg["tf_labels"]

    df_slow = tfs.get(timeframes[0], pd.DataFrame())
    df_mid  = tfs.get(timeframes[1], pd.DataFrame())
    df_fast = tfs.get(timeframes[2], pd.DataFrame())

    ref_df = next((df for df in [df_fast, df_mid, df_slow] if not df.empty), pd.DataFrame())
    if ref_df.empty: return {"error": "No data returned."}
    price = float(ref_df.iloc[-1]["close"])

    # Load per-asset effective profile (preset + saved overrides), then apply macro regime scaling
    profile = get_effective_profile(symbol)
    if sensors:
        from knowledge_graph import get_regime_weights
        regime_bucket, regime_mults = get_regime_weights(sensors)
        profile = apply_regime_weights(profile, regime_mults)
    else:
        regime_bucket = "NEUTRAL"

    trend_slow = get_trend(df_slow) if not df_slow.empty else "UNKNOWN"
    trend_mid  = get_trend(df_mid) if not df_mid.empty else "UNKNOWN"
    trend_fast = get_trend(df_fast) if not df_fast.empty else "UNKNOWN"

    support, resistance = find_sr_levels(df_slow, price) if not df_slow.empty else ([], [])

    s_bull, s_bear, s_sigs = score_timeframe(df_slow, profile) if not df_slow.empty else (0, 0, [])
    m_bull, m_bear, m_sigs = score_timeframe(df_mid,  profile) if not df_mid.empty  else (0, 0, [])
    f_bull, f_bear, f_sigs = score_timeframe(df_fast, profile) if not df_fast.empty else (0, 0, [])

    vol_signal, _ = analyze_volume(df_fast if not df_fast.empty else df_mid)
    
    slow_adx = float(df_slow.iloc[-1]["adx"]) if not df_slow.empty and "adx" in df_slow.columns and not np.isnan(df_slow.iloc[-1]["adx"]) else None

    # Divergence detected on slow TF — the most meaningful timeframe for early warnings
    rsi_divergence = detect_rsi_divergence(df_slow) if not df_slow.empty else None

    verdict, total_bull, total_bear, pre_signal = compute_verdict(
        trend_slow, trend_mid, trend_fast,
        s_bull, s_bear, m_bull, m_bear, f_bull, f_bear,
        slow_adx=slow_adx, rsi_divergence=rsi_divergence,
    )
    
    # ── ETH/BTC Regime Gate ───────────────────────────────────────────────────
    # When enabled (crypto_altcoin profile), long signals are suppressed if ETH
    # is bleeding against BTC. A USD bullish breakout during BTC dominance is
    # usually BTC dragging the market — not ETH finding its own bid.
    eth_btc_regime = None
    if profile.get("eth_btc_gate", False):
        try:
            df_eb, _ = fetch_crypto_ohlcv("ETH/BTC", "1d")
            if not df_eb.empty and len(df_eb) >= 10:
                sma_period = min(50, len(df_eb))
                sma50      = df_eb["close"].rolling(sma_period).mean().iloc[-1]
                current_eb = float(df_eb["close"].iloc[-1])
                if current_eb > sma50:
                    eth_btc_regime = "OUTPERFORMING"
                else:
                    eth_btc_regime = "BTC_DOMINANCE"
                    # Suppress long signals — ETH underperforming BTC
                    if verdict == "STRONG BUY":
                        verdict = "BUY SETUP"
                    elif verdict == "BUY SETUP":
                        verdict = "WAIT — NO TRADE"
                    if pre_signal == "PRE-SIGNAL LONG":
                        pre_signal = None
            else:
                eth_btc_regime = "UNAVAILABLE"
        except Exception:
            eth_btc_regime = "UNAVAILABLE"

    is_crypto = "/" in symbol
    funding = {"available": True, "rate_pct": fetch_funding_rate(symbol)} if is_crypto else {}
    if funding.get("rate_pct") is None: funding = {"available": False}
    
    entry_quality = compute_entry_quality(verdict, df_fast, slow_adx, funding)

    # ATR plan — stop/target multipliers come from the asset profile's risk_model
    risk_model  = profile.get("risk_model", {})
    stop_mult   = float(risk_model.get("stop_multiplier",   1.5))
    target_mult = float(risk_model.get("target_multiplier", 3.0))
    chandelier  = bool(risk_model.get("chandelier_exit",    False))

    atr_plan = None
    if not df_fast.empty and "atr" in df_fast.columns:
        atr_val = float(df_fast.iloc[-1]["atr"])
        if not np.isnan(atr_val) and atr_val > 0:
            rr = round(target_mult / stop_mult, 2)
            rr_q = ("EXCELLENT" if rr >= 3 else "GOOD" if rr >= 2 else "MARGINAL") + f" ({rr:.1f}:1)"
            atr_plan = {
                "atr":          round(atr_val, 6),
                "entry":        round(price, 6),
                "stop_long":    round(price - stop_mult   * atr_val, 6),
                "target_long":  round(price + target_mult * atr_val, 6),
                "stop_short":   round(price + stop_mult   * atr_val, 6),
                "target_short": round(price - target_mult * atr_val, 6),
                "risk_reward":  rr,
                "rr_quality":   rr_q,
                "stop_mode":    f"{stop_mult}× ATR14",
            }
            if chandelier:
                atr_plan["chandelier_note"] = f"Chandelier Exit active — trail stop to highest high − {stop_mult}× ATR as trade progresses."

    import knowledge_graph
    safety = knowledge_graph.evaluate_asset_safety(symbol, domino_phase)
    
    last_fast = df_fast.iloc[-1] if not df_fast.empty else pd.Series(dtype=float)
    bb_lower = float(last_fast.get("bb_lower", 0)) if not last_fast.empty and not pd.isna(last_fast.get("bb_lower")) else 0.0
    bb_upper = float(last_fast.get("bb_upper", 1)) if not last_fast.empty and not pd.isna(last_fast.get("bb_upper")) else 1.0
    bb_width = bb_upper - bb_lower if bb_upper != bb_lower else 1.0
    bb_pos = (price - bb_lower) / bb_width

    indicators = {
        "rsi": float(last_fast.get("rsi", 50)) if not last_fast.empty and not pd.isna(last_fast.get("rsi")) else 50.0,
        "bb_pos": bb_pos,
        "macd_bull": float(last_fast.get("macd", 0)) > float(last_fast.get("macd_signal", 0)) if not last_fast.empty else False,
        "obv_up": float(last_fast.get("obv", 0)) > float(last_fast.get("obv_ema", 0)) if not last_fast.empty else False,
        "price_over_ema50": price > float(last_fast.get("ema_50", price)) if not last_fast.empty else False
    }
    setup_name = knowledge_graph.identify_micro_setup(indicators)

    def sigs_to_dicts(sigs): return [{"indicator": s[0], "state": s[1], "explanation": s[2]} for s in sigs]
    
    divergence = detect_rsi_divergence(df_fast) if not df_fast.empty else None

    from asset_profiles import load_profiles, get_suggested_asset_class
    _saved_profiles  = load_profiles()
    _asset_class     = profile.get("asset_class", "default")
    # confirmed = user has explicitly saved a profile with an asset_class set
    _class_confirmed = (symbol in _saved_profiles and
                        "asset_class" in _saved_profiles.get(symbol, {}))

    _chg_pct = 0.0
    if not df_fast.empty and len(df_fast) >= 2 and "close" in df_fast.columns:
        _prev = float(df_fast.iloc[-2]["close"])
        _last = float(df_fast.iloc[-1]["close"])
        if _prev > 0:
            _chg_pct = round((_last - _prev) / _prev * 100, 2)

    payload = {
        "symbol": symbol, "mode": mode, "price": round(price, 6), "verdict": verdict,
        "rsi": round(indicators["rsi"], 1),
        "chg_pct": _chg_pct,
        "pre_signal": pre_signal, "regime_bucket": regime_bucket,
        "asset_class": _asset_class, "asset_class_confirmed": _class_confirmed,
        "eth_btc_gate_enabled": bool(profile.get("eth_btc_gate", False)),
        "eth_btc_regime": eth_btc_regime,
        "stop_multiplier":    stop_mult,
        "target_multiplier":  target_mult,
        "chandelier_exit":    chandelier,
        "bull_score": round(total_bull, 2), "bear_score": round(total_bear, 2),
        "edge": round(total_bull - total_bear, 2), "entry_quality": entry_quality,
        "asset_safety": safety, "setup_name": setup_name,
        "trends": {labels[0]: trend_slow, labels[1]: trend_mid, labels[2]: trend_fast},
        "signals": {labels[0]: sigs_to_dicts(s_sigs), labels[1]: sigs_to_dicts(m_sigs), labels[2]: sigs_to_dicts(f_sigs)},
        "support": [round(x, 6) for x in support], "resistance": [round(x, 6) for x in resistance],
        "volume": vol_signal, "funding_rate": funding, "atr_plan": atr_plan,
        "warnings": {
            "missing_timeframes": [labels[i] for i, df in enumerate([df_slow, df_mid, df_fast]) if df.empty],
            "extreme_rsi": (
                [f"RSI OVERBOUGHT ({indicators['rsi']:.1f}) — Overextended, pullback risk"]
                if indicators["rsi"] > 75 else
                [f"RSI OVERSOLD ({indicators['rsi']:.1f}) — Possible exhaustion bounce"]
                if indicators["rsi"] < 25 else []
            ),
            "rsi_divergences": [divergence] if divergence else [],
            "weak_adx": (
                [f"ADX {slow_adx:.1f} — Weak trend, choppy conditions, breakout risk is low"]
                if slow_adx is not None and slow_adx < 20 else []
            ),
        }
    }
    
    payload["asymmetry"] = knowledge_graph.calculate_asymmetry_score(payload, domino_phase)

    from smc_engine import get_session_weight
    payload["session_weight"] = get_session_weight(pd.Timestamp.now(tz="UTC"))

    return payload
