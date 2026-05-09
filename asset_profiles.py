"""
asset_profiles.py — Per-Asset Strategy Profiles for Banshee Pro
================================================================
Every asset behaves differently. BTC tends to lead with OBV. NVDA
responds well to EMA stacks. A choppy stock might need volume gating
before any momentum signal is trusted.

This module stores per-symbol configurations so Banshee can calibrate
itself from real backtest evidence rather than using the same hardwired
weights for every ticker.

HOW IT WORKS:
  1. Each symbol gets a profile stored in banshee_profiles.json
  2. The profile controls: which indicators are active + their weights
  3. score_timeframe() reads the active profile and adjusts scoring
  4. Discovery Mode results can be "promoted" to update a profile
  5. The Settings tab lets you view and edit any symbol's profile

WHY WEIGHTS INSTEAD OF ON/OFF:
  Turning an indicator fully off removes information. Setting its weight
  low (e.g. 0.3×) lets it still contribute a whisper while the indicators
  that actually work for this asset shout louder. More nuanced = better.

DATA STRUCTURE (one entry per symbol in banshee_profiles.json):
{
  "BTC/USD": {
    "symbol": "BTC/USD",
    "indicators": {
      "supertrend":  {"enabled": true, "weight": 2.0},
      "ema_stack":   {"enabled": true, "weight": 2.0},
      ...
    },
    "volume_gate":   false,   -- require above-avg volume for momentum signals
    "promoted_from": null,    -- Discovery strategy that set these weights
    "updated_at":    "..."
  }
}
"""

import os
import json
from datetime import datetime

# Profiles are stored alongside the other Banshee data files
PROFILES_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "banshee_profiles.json",
)

# ── Default indicator configuration ──────────────────────────────────────────
# These weights match the old hardwired behaviour exactly — so a symbol with
# no saved profile scores identically to before. Raising a weight amplifies
# that indicator's contribution; lowering it dampens it; setting enabled=False
# skips it entirely.

DEFAULT_INDICATORS: dict = {
    "supertrend":  {
        "enabled": True, "weight": 2.0,
        "label":   "Supertrend",
        "note":    "Trend-following line. Reliable in trending markets, whipsaws in chop.",
    },
    "ema_stack":   {
        "enabled": True, "weight": 2.0,
        "label":   "EMA Stack (20/50/200)",
        "note":    "Whether short/mid/slow EMAs are stacked bullish or bearish.",
    },
    "ema_price":   {
        "enabled": True, "weight": 1.0,
        "label":   "Price vs EMA 50",
        "note":    "Is price above or below the medium EMA? Simple buyer/seller control.",
    },
    "rsi":         {
        "enabled": True, "weight": 1.5,
        "label":   "RSI",
        "note":    "Momentum oscillator. Useful for spotting exhaustion at extremes.",
    },
    "stoch_rsi":   {
        "enabled": True, "weight": 1.5,
        "label":   "Stoch RSI",
        "note":    "Fast momentum cross. Noisy but catches short-term reversals early.",
    },
    "macd":        {
        "enabled": True, "weight": 2.0,
        "label":   "MACD",
        "note":    "Trend + momentum combined. Less noisy than Stoch RSI.",
    },
    "obv":         {
        "enabled": True, "weight": 1.0,
        "label":   "OBV vs OBV EMA",
        "note":    "Is smart money accumulating or distributing?",
    },
    "obv_leading": {
        "enabled": True, "weight": 2.0,
        "label":   "OBV Leading Accumulation",
        "note":    "OBV rising while price is flat = buying before the move. PRE-SIGNAL ancestor.",
    },
    "bb_slow":     {
        "enabled": True, "weight": 1.0,
        "label":   "BB Slow (20 SMA / close / 2σ)",
        "note":    "Standard Bollinger Band. Price at bands signals potential reversals.",
    },
    "bb_fast":     {
        "enabled": True, "weight": 1.0,
        "label":   "BB Fast (4 SMA / open / 2σ)",
        "note":    "Short-term volatility envelope. Dual-band position reveals momentum quality.",
    },
    "vwap":        {
        "enabled": True, "weight": 1.0,
        "label":   "VWAP",
        "note":    "Fair value anchor. Institutions use this as buy/sell reference.",
    },
    "mfi": {
        "enabled": True, "weight": 1.5,
        "label":   "MFI (Money Flow Index)",
        "note":    "Volume-weighted RSI. Catches institutional accumulation before price moves. Overbought=80, Oversold=20.",
    },
    "fisher": {
        "enabled": True, "weight": 1.5,
        "label":   "Fisher Transform",
        "note":    "Normalizes price to a Gaussian distribution. Near-vertical spikes at extremes = genuine exhaustion turning points.",
    },
}

# Volume gate: when enabled, momentum signals (RSI, Stoch RSI, MACD) are
# suppressed on bars where volume is below the 20-period average.
# Structural signals (Supertrend, EMA) are unaffected.
MOMENTUM_INDICATORS = {"rsi", "stoch_rsi", "macd", "obv", "obv_leading"}

DEFAULT_PROFILE: dict = {
    "indicators":    DEFAULT_INDICATORS,
    "volume_gate":   False,   # start permissive; user enables after testing
    "promoted_from": None,
    "updated_at":    None,
    # ── Asset class system ────────────────────────────────────────────────────
    # Controls preset weights, stop multipliers, and special gates.
    # "default" = original Banshee behaviour (no special handling).
    "asset_class":   "default",
    "eth_btc_gate":  False,   # ETH/BTC ratio gate for altcoins
    "risk_model":    {
        "stop_multiplier":   1.5,   # ATR × this = stop distance
        "target_multiplier": 3.0,   # ATR × this = profit target
        "chandelier_exit":   False, # Trail stop at highest high − stop_multiplier × ATR
    },
}

# ── Asset Class System ─────────────────────────────────────────────────────────
# Well-known tickers → suggested asset class on first scan (never overrides saved).
KNOWN_ASSET_CLASSES: dict = {
    # BTC
    "BTC/USD":   "crypto_btc",  "BTC/USDT":  "crypto_btc",  "BTC-USD":   "crypto_btc",
    # ETH and altcoins
    "ETH/USD":   "crypto_altcoin", "ETH/USDT": "crypto_altcoin", "ETH/USDC": "crypto_altcoin", "ETH-USD": "crypto_altcoin",
    "SOL/USD":   "crypto_altcoin", "SOL/USDT": "crypto_altcoin",
    "SUI/USD":   "crypto_altcoin", "SUI/USDT": "crypto_altcoin",
    "BNB/USD":   "crypto_altcoin", "BNB/USDT": "crypto_altcoin",
    "XRP/USD":   "crypto_altcoin", "XRP/USDT": "crypto_altcoin",
    "ADA/USD":   "crypto_altcoin", "ADA/USDT": "crypto_altcoin",
    "AVAX/USD":  "crypto_altcoin", "AVAX/USDT": "crypto_altcoin",
    "HYPE/USD":  "crypto_altcoin", "HYPE/USDT": "crypto_altcoin",
    "HBAR/USD":  "crypto_altcoin", "HBAR/USDT": "crypto_altcoin",
    "TAO/USD":   "crypto_altcoin", "TAO/USDT":  "crypto_altcoin",
    "XLM/USD":   "crypto_altcoin", "XLM/USDT":  "crypto_altcoin",
    "NEAR/USD":  "crypto_altcoin", "NEAR/USDT": "crypto_altcoin",
    "DOGE/USD":  "crypto_altcoin", "DOGE/USDT": "crypto_altcoin",
    "LINK/USD":  "crypto_altcoin", "LINK/USDT": "crypto_altcoin",
    "DOT/USD":   "crypto_altcoin", "DOT/USDT":  "crypto_altcoin",
    # Gold proxies — PAXG is here on purpose, NOT in altcoins
    "PAXG/USD":  "gold_proxy",  "PAXG/USDT": "gold_proxy",  "PAXG-USD": "gold_proxy",
    "GLD":       "gold_proxy",  "IAU":        "gold_proxy",
    "GC=F":      "gold_proxy",  "XAUUSD":     "gold_proxy",
    # Equities
    "SPY":   "equity", "QQQ":   "equity", "IWM":  "equity",
    "NVDA":  "equity", "MSFT":  "equity", "AAPL": "equity",
    "TSLA":  "equity", "META":  "equity", "AMZN": "equity",
    "GOOG":  "equity", "GOOGL": "equity", "AMD":  "equity",
}

ASSET_CLASS_LABELS: dict = {
    "default":        "⚪ Default",
    "crypto_btc":     "🟠 BTC",
    "crypto_altcoin": "🔷 Altcoin (ETH-style)",
    "gold_proxy":     "🟡 Gold Proxy",
    "equity":         "📈 Equity",
}

ASSET_CLASS_OPTIONS: list = list(ASSET_CLASS_LABELS.keys())

# Per-class preset: overrides applied on top of DEFAULT_PROFILE when asset_class is set.
# User-saved indicator weights always take final precedence over preset values.
ASSET_CLASS_PRESETS: dict = {
    "default": {
        "risk_model":          {"stop_multiplier": 1.5, "target_multiplier": 3.0, "chandelier_exit": False},
        "eth_btc_gate":        False,
        "volume_gate":         False,
        "indicator_overrides": {},
    },
    "crypto_btc": {
        "risk_model":          {"stop_multiplier": 2.0, "target_multiplier": 4.0, "chandelier_exit": False},
        "eth_btc_gate":        False,
        "volume_gate":         False,
        "indicator_overrides": {
            "obv_leading": {"weight": 2.5},  # BTC is an OBV-leading asset
            "mfi":         {"weight": 1.5},
        },
    },
    "crypto_altcoin": {
        "risk_model":          {"stop_multiplier": 2.5, "target_multiplier": 5.0, "chandelier_exit": True},
        "eth_btc_gate":        True,   # Gate long signals on ETH/BTC ratio
        "volume_gate":         True,   # Suppress momentum signals on low-volume bars
        "indicator_overrides": {
            "mfi":         {"weight": 2.5},  # Volume-weighted — more reliable than RSI on alts
            "fisher":      {"weight": 2.0},  # Statistical extremes catch real exhaustion
            "rsi":         {"weight": 0.75}, # Price-only, unreliable in altcoin noise
            "macd":        {"weight": 1.0},  # Demote — lags too much on alts
            "obv_leading": {"weight": 2.5},  # Smart money accumulation before the move
        },
    },
    "gold_proxy": {
        "risk_model":          {"stop_multiplier": 2.0, "target_multiplier": 4.0, "chandelier_exit": False},
        "eth_btc_gate":        False,
        "volume_gate":         False,
        "indicator_overrides": {
            "ema_stack":  {"weight": 3.0},  # Gold trends cleanly and persistently
            "supertrend": {"weight": 2.5},
            "macd":       {"weight": 2.5},  # Good for slow-moving trend continuation
            "stoch_rsi":  {"weight": 0.75}, # Too noisy for gold's pace
            "mfi":        {"weight": 1.5},
        },
    },
    "equity": {
        "risk_model":          {"stop_multiplier": 1.5, "target_multiplier": 3.0, "chandelier_exit": False},
        "eth_btc_gate":        False,
        "volume_gate":         False,
        "indicator_overrides": {},  # Default weights work well for equities
    },
}


# ── Profile I/O ───────────────────────────────────────────────────────────────

def load_profiles() -> dict:
    """Return all saved profiles as { symbol: profile_dict }."""
    if not os.path.exists(PROFILES_FILE):
        return {}
    try:
        with open(PROFILES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def get_profile(symbol: str) -> dict:
    """
    Return the full profile for a symbol, merging saved data with defaults.

    This means:
    - New symbols get defaults automatically (no profile required)
    - Saved profiles only need to store what differs from defaults
    - Adding a new indicator to DEFAULT_INDICATORS propagates to all symbols
    """
    profiles = load_profiles()
    saved    = profiles.get(symbol, {})

    # Top-level fields (volume_gate, promoted_from, etc.)
    profile = {**DEFAULT_PROFILE, **{k: v for k, v in saved.items() if k != "indicators"}}

    # Indicators: start from defaults, overlay any saved overrides
    merged = {}
    for key, defaults in DEFAULT_INDICATORS.items():
        override = saved.get("indicators", {}).get(key, {})
        merged[key] = {**defaults, **override}

    profile["indicators"] = merged
    return profile


def save_profile(symbol: str, profile: dict) -> None:
    """Upsert one symbol's profile into banshee_profiles.json."""
    profiles = load_profiles()
    profile["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    profiles[symbol] = profile
    with open(PROFILES_FILE, "w", encoding="utf-8") as f:
        json.dump(profiles, f, indent=2)


def reset_profile(symbol: str) -> None:
    """Delete a symbol's profile so it falls back to defaults."""
    profiles = load_profiles()
    if symbol in profiles:
        del profiles[symbol]
        with open(PROFILES_FILE, "w", encoding="utf-8") as f:
            json.dump(profiles, f, indent=2)


# ── Discovery → Profile promotion ────────────────────────────────────────────

# Maps Discovery Mode indicator names to the profile keys above
_DISC_TO_PROFILE_KEY = {
    "Supertrend Flip Bullish":  "supertrend",
    "EMA Golden Cross":         "ema_stack",
    "RSI Oversold Bounce":      "rsi",
    "Stoch RSI Bullish Cross":  "stoch_rsi",
    "Price Reclaims VWAP":      "vwap",
    "ADX Trend Trigger":        "obv",      # ADX not in profile yet; map to OBV loosely
    "Dual BB Position":         "bb_fast",
}

# Rank 1 gets the highest weight boost, rank 6+ gets a mild penalty
_RANK_WEIGHTS = [3.0, 2.5, 2.0, 1.5, 1.0, 0.5]


def promote_discovery_to_profile(symbol: str, discovery_result: dict) -> dict:
    """
    Convert Discovery Mode rankings into a per-asset indicator profile.

    The best indicator gets weight 3.0 (loud), the worst gets 0.5 (whisper).
    Indicators that failed to run keep their default weights.

    Returns the new profile dict — caller must call save_profile() to persist it.

    WHY THIS MATTERS:
    Discovery found that on BTC, OBV has a Sharpe of 1.2 but MACD has -0.3.
    Without promotion, Banshee weights them equally in live verdicts.
    After promotion, OBV shouts and MACD whispers — the verdict reflects reality.
    """
    profile = get_profile(symbol)

    # Only use combos that actually completed successfully
    done_combos = [
        r for r in discovery_result.get("combos", [])
        if r.get("status") == "done"
    ]

    # Sort by Sharpe (best first)
    done_combos.sort(
        key=lambda r: float(r["stats"].get("sharpe", "0").replace("—", "0")),
        reverse=True,
    )

    # Apply rank-based weights to matching profile keys
    for rank, combo in enumerate(done_combos):
        key = _DISC_TO_PROFILE_KEY.get(combo["name"])
        if key and key in profile["indicators"]:
            profile["indicators"][key]["weight"] = _RANK_WEIGHTS[
                min(rank, len(_RANK_WEIGHTS) - 1)
            ]

    profile["promoted_from"] = (
        f"Discovery on {discovery_result.get('symbol', symbol)} "
        f"({discovery_result.get('tf', '?')}, {discovery_result.get('lb', '?')}) "
        f"— {datetime.now().strftime('%Y-%m-%d')}"
    )
    return profile


# ── Convenience helpers ────────────────────────────────────────────────────────

def get_suggested_asset_class(symbol: str) -> str | None:
    """Return the suggested asset class for a well-known symbol, or None if unknown."""
    return KNOWN_ASSET_CLASSES.get(symbol)


def get_effective_profile(symbol: str) -> dict:
    """
    Return a fully-resolved profile for live analysis.

    Resolution order (highest wins):
    1. User-saved indicator weights from banshee_profiles.json
    2. Asset class preset overrides (from ASSET_CLASS_PRESETS)
    3. DEFAULT_PROFILE / DEFAULT_INDICATORS

    If no saved profile exists and the symbol is in KNOWN_ASSET_CLASSES, the
    suggested class is auto-applied silently — NOT saved. The UI still shows
    the "confirm asset type" prompt until the user explicitly saves.
    """
    profiles = load_profiles()
    saved    = profiles.get(symbol, {})

    # Determine asset class: prefer saved, else suggest from known list, else default
    if "asset_class" in saved:
        asset_class = saved["asset_class"]
    else:
        asset_class = KNOWN_ASSET_CLASSES.get(symbol, "default")

    preset = ASSET_CLASS_PRESETS.get(asset_class, ASSET_CLASS_PRESETS["default"])

    # Start from DEFAULT_PROFILE skeleton
    profile = {**DEFAULT_PROFILE}
    profile["asset_class"]  = asset_class
    profile["risk_model"]   = dict(preset.get("risk_model",  DEFAULT_PROFILE["risk_model"]))
    profile["eth_btc_gate"] = preset.get("eth_btc_gate", False)
    profile["volume_gate"]  = preset.get("volume_gate",  False)

    # Saved top-level fields override preset (user has final say on gate toggles etc.)
    for k, v in saved.items():
        if k != "indicators":
            profile[k] = v

    # Build indicators: defaults → preset overrides → saved overrides
    merged = {}
    for key, defaults in DEFAULT_INDICATORS.items():
        preset_override = preset.get("indicator_overrides", {}).get(key, {})
        saved_override  = saved.get("indicators", {}).get(key, {})
        merged[key] = {**defaults, **preset_override, **saved_override}

    profile["indicators"] = merged
    return profile


def get_weight(profile: dict, key: str) -> float:
    """Return the effective weight for one indicator key. 0.0 if disabled."""
    ind = profile.get("indicators", {}).get(key, DEFAULT_INDICATORS.get(key, {}))
    if not ind.get("enabled", True):
        return 0.0
    return float(ind.get("weight", 1.0))


def is_enabled(profile: dict, key: str) -> bool:
    """Return True if an indicator is enabled in this profile."""
    ind = profile.get("indicators", {}).get(key, DEFAULT_INDICATORS.get(key, {}))
    return bool(ind.get("enabled", True))
