"""
smc_engine.py — Banshee Pro Smart Money Concepts Engine
========================================================
Phase 1: ATR baseline, swing point detection, and market structure labeling
         (BOS / CHoCH state machine).

Design principles:
  - Every threshold from the spec is a named constant at the top — one place to tune.
  - Every function has a plain-English docstring: what it detects, what it returns, WHY.
  - No Streamlit imports — this file is pure pandas/numpy so it can be tested independently.
  - Each phase adds to this file without breaking what came before.
"""

import numpy as np
import pandas as pd


# ─── CONFIGURABLE CONSTANTS ────────────────────────────────────────────────────
# All thresholds derived from the SMC spec live here.
# Change these numbers without touching any detection logic below.

# ATR baseline
ATR_PERIOD = 14                      # standard 14-period lookback

# Swing detection
SWING_FRACTAL_CANDLES = 2            # candles either side (5-candle pattern total)

# BOS displacement requirement
# The breaking candle's full range must be >= this multiple of ATR to count as
# genuine institutional displacement (not a slow drift through the level).
BOS_DISPLACEMENT_ATR_MULT = 1.5

# Equal Highs / Lows tolerance  (Phase 4)
# Two swing points are "equal" if their prices differ by <= ATR * this fraction.
EQH_EQL_ATR_TOLERANCE = 0.05

# FVG displacement requirement  (Phase 2)
# The central candle of a 3-candle FVG must be >= this ATR multiple.
FVG_DISPLACEMENT_ATR_MULT = 1.0

# OTE Fibonacci sub-zone  (Phase 3+)
# High-probability entries only inside this retracement band of the dealing range.
OTE_FIB_LOW  = 0.62
OTE_FIB_HIGH = 0.79

# Session weight multipliers  (Phase 3+)
# Set any of these to 1.0 to neutralise it.
SILVER_BULLET_WEIGHT  = 2.0    # 03:00-04:00, 10:00-11:00, 14:00-15:00 EST
LONDON_KILLZONE_WEIGHT = 1.5   # 02:00-05:00 EST
NY_KILLZONE_WEIGHT     = 1.5   # 07:00-10:00 EST
LONDON_CLOSE_WEIGHT    = 0.8   # 10:00-12:00 EST
ASIAN_RANGE_WEIGHT     = 0.5   # 20:00-00:00 EST

# Inducement gate  (Phase 4)
# Each OB gets two fields:
#   has_pending_inducement — unswept EQH/EQL sits between current price and the OB zone.
#                            Positive qualifier: trap is set, smart money has reason to drive
#                            price here. OB is worth watching but not yet actionable.
#   inducement_swept       — a pool WAS in that zone and has since been swept.
#                            The trap has fired; this is the entry signal.
#
# False = annotate OBs with both fields, pass all signals through.
# True  = hard block: only inducement_swept=True OBs qualify.
#         Pending-inducement OBs are suppressed (trap not fired yet).
#         No-inducement OBs are suppressed (per SMC: the OB itself becomes the trap).
INDUCEMENT_HARD_GATE = True


# ─── SESSION WEIGHT ────────────────────────────────────────────────────────────

def get_session_weight(ts) -> float:
    """
    Return the session multiplier for a timestamp.

    WHY: ICT session windows carry different levels of institutional participation.
    Silver Bullet hours (03, 10, 14 EST) are the highest-probability delivery windows.
    Killzones follow. Asian range is low-conviction chop. All other hours default to 1.0.

    Naive timestamps are assumed UTC — matches the ccxt/Coinbase data source.
    Priority order: Silver Bullet > London Killzone > NY Killzone > London Close > Asian Range.
    """
    try:
        pt = pd.Timestamp(ts)
        if pt.tzinfo is None:
            pt = pt.tz_localize("UTC")
        hour = pt.tz_convert("America/New_York").hour
    except Exception:
        return 1.0

    if hour in (3, 10, 14):   # Silver Bullet: 03–04, 10–11, 14–15 EST
        return SILVER_BULLET_WEIGHT
    if 2 <= hour < 5:         # London Killzone (02–05; Silver Bullet hour already caught)
        return LONDON_KILLZONE_WEIGHT
    if 7 <= hour < 10:        # NY Killzone
        return NY_KILLZONE_WEIGHT
    if 10 <= hour < 12:       # London Close (hour 10 already caught above)
        return LONDON_CLOSE_WEIGHT
    if hour >= 20:            # Asian Range
        return ASIAN_RANGE_WEIGHT
    return 1.0


# ─── ATR ───────────────────────────────────────────────────────────────────────

def compute_atr(df: pd.DataFrame) -> pd.Series:
    """
    Compute the Average True Range using Wilder's smoothing method.

    WHY: ATR is the engine's universal ruler. Every spatial tolerance in SMC —
    how far apart is "equal", how large must a displacement candle be — is expressed
    as a multiple of ATR so the same thresholds work on BTC/USD at $80k and on
    a $10 stock without any manual tuning.

    Wilder smoothing: seed with the simple average of the first ATR_PERIOD bars,
    then each subsequent bar = (prior_atr * (n-1) + current_tr) / n.
    The first ATR_PERIOD - 1 values are NaN (not enough history yet).

    Returns a Series aligned with df's index.
    """
    high  = df["high"]
    low   = df["low"]
    prev_close = df["close"].shift(1)

    # True Range = the greatest of three measurements
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low  - prev_close).abs(),
    ], axis=1).max(axis=1)

    atr = pd.Series(np.nan, index=df.index)
    if len(tr) < ATR_PERIOD:
        return atr

    # Seed the first value with a simple average
    atr.iloc[ATR_PERIOD - 1] = tr.iloc[:ATR_PERIOD].mean()

    # Wilder roll-forward
    for i in range(ATR_PERIOD, len(tr)):
        atr.iloc[i] = (atr.iloc[i - 1] * (ATR_PERIOD - 1) + tr.iloc[i]) / ATR_PERIOD

    return atr


# ─── SWING DETECTION ───────────────────────────────────────────────────────────

def detect_swings(df: pd.DataFrame) -> list:
    """
    Detect confirmed swing highs and lows using a 5-candle fractal pattern.

    WHY: Market structure depends entirely on identifying the peaks and troughs
    institutions use as reference points. Without robust swing detection,
    every downstream concept (BOS, CHoCH, Order Blocks, Fair Value Gaps)
    is built on shaky ground.

    Rule (from the SMC spec):
      Swing HIGH at candle i: high[i] is strictly greater than high[i-1],
        high[i-2], high[i+1], and high[i+2].
      Swing LOW at candle i: low[i] is strictly less than all four neighbours.

    Why 2 candles each side?
      1 candle each side creates too much noise (every minor wiggle becomes a swing).
      2 candles each side (the spec's choice) filters out internal noise while still
      reacting quickly enough to track institutional structure.

    The last SWING_FRACTAL_CANDLES candles are skipped — they haven't yet been
    confirmed by the candles that follow them.

    Returns a list of dicts, sorted by index, each containing:
      idx        — integer row position in df
      timestamp  — the candle's timestamp
      price      — swing price (high for swing high, low for swing low)
      swing_type — "high" or "low"
      label      — None here; filled in by label_structure()
    """
    swings = []
    n      = SWING_FRACTAL_CANDLES
    highs  = df["high"].values
    lows   = df["low"].values

    # Pull timestamps — support both column and DatetimeIndex formats
    if "timestamp" in df.columns:
        timestamps = df["timestamp"].values
    else:
        timestamps = df.index.values

    for i in range(n, len(df) - n):
        # Swing High: this candle's high is the tallest in its 5-candle window
        is_swing_high = (
            all(highs[i] > highs[i - j] for j in range(1, n + 1)) and
            all(highs[i] > highs[i + j] for j in range(1, n + 1))
        )
        # Swing Low: this candle's low is the lowest in its 5-candle window
        is_swing_low = (
            all(lows[i] < lows[i - j] for j in range(1, n + 1)) and
            all(lows[i] < lows[i + j] for j in range(1, n + 1))
        )

        if is_swing_high:
            swings.append({
                "idx":        i,
                "timestamp":  timestamps[i],
                "price":      float(highs[i]),
                "swing_type": "high",
                "label":      None,
            })
        if is_swing_low:
            swings.append({
                "idx":        i,
                "timestamp":  timestamps[i],
                "price":      float(lows[i]),
                "swing_type": "low",
                "label":      None,
            })

    swings.sort(key=lambda s: s["idx"])
    return swings


# ─── MARKET STRUCTURE STATE MACHINE ────────────────────────────────────────────

def label_structure(df: pd.DataFrame, swings: list) -> dict:
    """
    Walk the swing sequence to label each swing HH/LH or HL/LL and detect
    BOS (Break of Structure) and CHoCH (Change of Character) events.

    WHY: The sequence of highs and lows IS the trend. Three higher highs
    and higher lows = institutional accumulation (BULLISH). The moment a key
    low breaks (CHoCH), smart money has flagged a potential reversal. When the
    next high then breaks (BOS), the new trend is confirmed.

    State machine (directly from the spec):
      BULLISH  + body close > last external swing high  + displacement → BOS_BULL
      BULLISH  + body close < last external swing low                  → CHoCH_BEAR → BEARISH
      BEARISH  + body close < last external swing low   + displacement → BOS_BEAR
      BEARISH  + body close > last external swing high                 → CHoCH_BULL → BULLISH
      ANY      + wick breaks level, body stays inside                  → Liquidity Sweep (logged)

    BOS requires displacement: breaking candle range >= BOS_DISPLACEMENT_ATR_MULT * ATR.
    CHoCH does NOT require displacement — the break of the protected level is enough.

    Returns a dict:
      swing_highs      — list of swing high dicts with "label" filled in
      swing_lows       — list of swing low dicts with "label" filled in
      structure_events — list of event dicts (see below)
      current_state    — "BULLISH" | "BEARISH" | "UNDEFINED"
      atr              — pd.Series of ATR values

    Each structure_event dict contains:
      idx, timestamp, price (the level that was broken), event_type, state_after
    """
    atr    = compute_atr(df)
    closes = df["close"].values
    opens  = df["open"].values
    highs  = df["high"].values
    lows   = df["low"].values

    if "timestamp" in df.columns:
        timestamps = df["timestamp"].values
    else:
        timestamps = df.index.values

    swing_highs = [s for s in swings if s["swing_type"] == "high"]
    swing_lows  = [s for s in swings if s["swing_type"] == "low"]

    # ── Step 1: Label each swing relative to the previous one of the same type ─
    # This is independent of state — it's just a comparison of consecutive peaks/troughs.
    for i, sh in enumerate(swing_highs):
        if i == 0:
            sh["label"] = "SH"  # no prior high to compare yet
        else:
            sh["label"] = "HH" if sh["price"] > swing_highs[i - 1]["price"] else "LH"

    for i, sl in enumerate(swing_lows):
        if i == 0:
            sl["label"] = "SL"  # no prior low to compare yet
        else:
            sl["label"] = "HL" if sl["price"] > swing_lows[i - 1]["price"] else "LL"

    # ── Step 2: BOS / CHoCH state machine ──────────────────────────────────────
    structure_events = []
    current_state    = "UNDEFINED"

    # Reference levels the state machine defends.
    # ref_high = the current external swing high (break above = BOS in bull / CHoCH in bear)
    # ref_low  = the current external swing low  (break below = CHoCH in bull / BOS in bear)
    ref_high     = None
    ref_low      = None
    ref_high_idx = -1
    ref_low_idx  = -1

    # Index the swings for O(1) lookup per candle
    sh_by_idx = {s["idx"]: s for s in swing_highs}
    sl_by_idx = {s["idx"]: s for s in swing_lows}

    for i in range(len(df)):

        # Register any new swing confirmed at this candle as a reference level.
        # We use the latest of each type (most recent swing = current reference).
        if i in sh_by_idx:
            ref_high     = sh_by_idx[i]["price"]
            ref_high_idx = i
            # Initialise state once we have at least one high and one low
            if current_state == "UNDEFINED" and ref_low is not None:
                # The swing that appeared first in time sets the initial structure bias.
                # Low came before high → market built up → bullish start.
                current_state = "BULLISH" if ref_low_idx < ref_high_idx else "BEARISH"

        if i in sl_by_idx:
            ref_low     = sl_by_idx[i]["price"]
            ref_low_idx = i
            if current_state == "UNDEFINED" and ref_high is not None:
                current_state = "BULLISH" if ref_low_idx < ref_high_idx else "BEARISH"

        # Can't evaluate until state and both reference levels are established
        if current_state == "UNDEFINED" or ref_high is None or ref_low is None:
            continue

        # Candle body = from open to close (excludes wicks)
        body_high = max(opens[i], closes[i])
        body_low  = min(opens[i], closes[i])

        # Displacement check: is this candle large enough to count as genuine
        # institutional delivery (not just a slow drift across the level)?
        candle_range = float(highs[i] - lows[i])
        atr_val      = float(atr.iloc[i]) if i < len(atr) and not np.isnan(atr.iloc[i]) else None
        has_displacement = (
            atr_val is not None and
            candle_range >= BOS_DISPLACEMENT_ATR_MULT * atr_val
        )

        # ── BULLISH state ────────────────────────────────────────────────────
        if current_state == "BULLISH":

            if body_high > ref_high and has_displacement:
                # Body closed above last swing high WITH displacement → BOS: trend continues.
                structure_events.append({
                    "idx":        i,
                    "timestamp":  timestamps[i],
                    "price":      ref_high,     # the level that was broken
                    "event_type": "BOS_BULL",
                    "state_after": "BULLISH",
                })
                # The new peak becomes the next BOS target; ref_low stays (protected floor).
                ref_high     = float(highs[i])
                ref_high_idx = i

            elif body_low < ref_low:
                # Body closed below protected swing low → CHoCH: trend may be reversing.
                structure_events.append({
                    "idx":        i,
                    "timestamp":  timestamps[i],
                    "price":      ref_low,
                    "event_type": "CHoCH_BEAR",
                    "state_after": "BEARISH",
                })
                current_state = "BEARISH"
                ref_low       = float(lows[i])
                ref_low_idx   = i

        # ── BEARISH state ────────────────────────────────────────────────────
        elif current_state == "BEARISH":

            if body_low < ref_low and has_displacement:
                # Body closed below last swing low WITH displacement → BOS: trend continues.
                structure_events.append({
                    "idx":        i,
                    "timestamp":  timestamps[i],
                    "price":      ref_low,
                    "event_type": "BOS_BEAR",
                    "state_after": "BEARISH",
                })
                ref_low     = float(lows[i])
                ref_low_idx = i

            elif body_high > ref_high:
                # Body closed above protected swing high → CHoCH: trend may be reversing.
                structure_events.append({
                    "idx":        i,
                    "timestamp":  timestamps[i],
                    "price":      ref_high,
                    "event_type": "CHoCH_BULL",
                    "state_after": "BULLISH",
                })
                current_state = "BULLISH"
                ref_high      = float(highs[i])
                ref_high_idx  = i

    return {
        "swing_highs":       swing_highs,
        "swing_lows":        swing_lows,
        "structure_events":  structure_events,
        "current_state":     current_state,
        "atr":               atr,
    }


# ─── FAIR VALUE GAPS ───────────────────────────────────────────────────────────

def detect_fvgs(df: pd.DataFrame, atr: pd.Series) -> list:
    """
    Detect Fair Value Gaps (FVGs) and track their mitigation lifecycle.

    WHY: FVGs are zones of price imbalance where institutional delivery was so
    aggressive that the market skipped over a range of prices. They act as magnetic
    draw points — price tends to return to fill these voids. Unmitigated FVGs
    near current price are primary entry targets when aligned with trend direction.

    Detection rule (from the SMC spec, 3-candle sequence):
      Bullish FVG:  C3 low  > C1 high  AND  C2 range >= FVG_DISPLACEMENT_ATR_MULT * ATR
        Zone: bottom = C1 high, top = C3 low
      Bearish FVG:  C3 high < C1 low   AND  C2 range >= FVG_DISPLACEMENT_ATR_MULT * ATR
        Zone: top = C1 low, bottom = C3 high

    Lifecycle states:
      "active"    — price has not re-entered the zone since creation
      "partial"   — a candle wick entered the zone but the gap isn't fully filled
      "mitigated" — a wick has touched the far boundary (gap fully filled)

    Returns a list of FVG dicts, each containing:
      idx, timestamp — when the FVG was confirmed (candle 3 closes)
      kind           — "bullish" | "bearish"
      top, bottom    — zone bounds (top > bottom always)
      status         — "active" | "partial" | "mitigated"
      mitigated_at   — row index where fully mitigated, or None
    """
    fvgs = []

    if "timestamp" in df.columns:
        timestamps = df["timestamp"].values
    else:
        timestamps = df.index.values

    highs  = df["high"].values
    lows   = df["low"].values
    opens  = df["open"].values
    closes = df["close"].values

    # ── Pass 1: detect FVG formation ──────────────────────────────────────────
    for i in range(1, len(df) - 1):
        atr_val = float(atr.iloc[i]) if i < len(atr) and not np.isnan(atr.iloc[i]) else None
        if atr_val is None:
            continue

        c2_range = float(highs[i] - lows[i])
        if c2_range < FVG_DISPLACEMENT_ATR_MULT * atr_val:
            continue  # central candle too small — no displacement

        c1_high = float(highs[i - 1])
        c1_low  = float(lows[i - 1])
        c3_high = float(highs[i + 1])
        c3_low  = float(lows[i + 1])

        if c3_low > c1_high:
            # Bullish FVG — gap between c1 high and c3 low
            fvgs.append({
                "idx":          i + 1,
                "timestamp":    timestamps[i + 1],
                "kind":         "bullish",
                "top":          c3_low,
                "bottom":       c1_high,
                "status":       "active",
                "mitigated_at": None,
            })
        elif c3_high < c1_low:
            # Bearish FVG — gap between c3 high and c1 low
            fvgs.append({
                "idx":          i + 1,
                "timestamp":    timestamps[i + 1],
                "kind":         "bearish",
                "top":          c1_low,
                "bottom":       c3_high,
                "status":       "active",
                "mitigated_at": None,
            })

    # ── Pass 2: track lifecycle for each FVG ─────────────────────────────────
    for fvg in fvgs:
        creation_idx = fvg["idx"]
        top    = fvg["top"]
        bottom = fvg["bottom"]

        for j in range(creation_idx + 1, len(df)):
            wick_high = float(highs[j])
            wick_low  = float(lows[j])

            if fvg["kind"] == "bullish":
                # Bullish FVG fills from the top downward
                if wick_low <= bottom:
                    # Wick touched the bottom bound — gap fully filled
                    fvg["status"]       = "mitigated"
                    fvg["mitigated_at"] = j
                    break
                elif wick_low < top:
                    # Wick entered but didn't fill — partial; keep scanning
                    fvg["status"] = "partial"

            else:  # bearish
                # Bearish FVG fills from the bottom upward
                if wick_high >= top:
                    fvg["status"]       = "mitigated"
                    fvg["mitigated_at"] = j
                    break
                elif wick_high > bottom:
                    fvg["status"] = "partial"

    return fvgs


# ─── PREMIUM / DISCOUNT ZONES ──────────────────────────────────────────────────

def compute_pd_zones(swing_highs: list, swing_lows: list, current_state: str) -> dict | None:
    """
    Compute the Premium/Discount zone from the current active dealing range.

    WHY: Institutional algorithms only buy in discount (cheap) and sell in premium
    (expensive). Knowing where the current 50% equilibrium line sits tells you
    which half of the range is high-probability for entries vs. already-extended.
    The OTE (Optimal Trade Entry) sub-zone (62-79% Fibonacci retracement) is where
    the highest-probability entries cluster.

    Dealing range: last confirmed swing high and last confirmed swing low.

    In BULLISH state:
      - Below equilibrium (50%) = Discount zone  → look to buy
      - OTE = 62-79% retracement FROM the high into discount
            = prices between (high - 0.79 * range) and (high - 0.62 * range)

    In BEARISH state:
      - Above equilibrium (50%) = Premium zone   → look to sell
      - OTE = 62-79% retracement FROM the low into premium
            = prices between (low + 0.62 * range) and (low + 0.79 * range)

    Returns None if dealing range is invalid (no swings or state UNDEFINED).

    Returns a dict with:
      range_high, range_low  — the active dealing range bounds
      equilibrium            — exact 50% midpoint
      ote_top, ote_bottom    — OTE sub-zone bounds (top > bottom always)
      discount_top           — == equilibrium (discount is below this)
      premium_bottom         — == equilibrium (premium is above this)
      state                  — current_state for rendering decisions
    """
    if not swing_highs or not swing_lows or current_state == "UNDEFINED":
        return None

    range_high = swing_highs[-1]["price"]
    range_low  = swing_lows[-1]["price"]

    if range_high <= range_low:
        return None

    range_size  = range_high - range_low
    equilibrium = (range_high + range_low) / 2.0

    if current_state == "BULLISH":
        # OTE: 62-79% retracement from the high
        ote_top    = range_high - OTE_FIB_LOW  * range_size   # shallower retrace
        ote_bottom = range_high - OTE_FIB_HIGH * range_size   # deeper retrace
    else:
        # BEARISH — OTE: 62-79% retracement from the low
        ote_bottom = range_low + OTE_FIB_LOW  * range_size
        ote_top    = range_low + OTE_FIB_HIGH * range_size

    return {
        "range_high":      range_high,
        "range_low":       range_low,
        "equilibrium":     equilibrium,
        "ote_top":         ote_top,
        "ote_bottom":      ote_bottom,
        "discount_top":    equilibrium,    # discount is everything below this
        "premium_bottom":  equilibrium,    # premium is everything above this
        "state":           current_state,
    }


# ─── ORDER BLOCKS ──────────────────────────────────────────────────────────────

def detect_order_blocks(df: pd.DataFrame, structure_events: list,
                        fvgs: list) -> list:
    """
    Detect Order Blocks — the last opposite-color candle before a displacement wave.

    WHY: Order Blocks are the price zones where institutions accumulated or
    distributed positions immediately before a strong directional move. Price
    frequently returns to these zones to retest the institutional footprint.
    They are the PRIMARY entry trigger in the SMC framework.

    Rule (from the spec):
      1. Start from a validated BOS or CHoCH event that CONTAINS an FVG in its
         displacement leg — no FVG means no institutional displacement, no valid OB.
      2. Walk backward from the event candle to find the last opposite-color candle.
         Bullish displacement → last bearish candle (close < open)
         Bearish displacement → last bullish candle (close > open)
      3. That candle is the Order Block.

    Zone definition:
      Default:          open-to-close body of the OB candle.
      Overlap exception: if the OB candle's wick physically overlaps the
                        accompanying FVG, expand the zone to the full high-to-low.

    Lifecycle states:
      "active"      — price has not re-entered the zone
      "touched"     — a wick entered the zone (still valid for entry on first touch)
      "degraded"    — a candle body closed past the 50% mean threshold (reduced weight)
      "invalidated" — a candle body closed through the distal boundary (OB destroyed)

    Returns a list of OB dicts.
    """
    opens  = df["open"].values
    closes = df["close"].values
    highs  = df["high"].values
    lows   = df["low"].values

    if "timestamp" in df.columns:
        timestamps = df["timestamp"].values
    else:
        timestamps = df.index.values

    # How far back to search for the opposing candle from the BOS/CHoCH candle.
    OB_LOOKBACK = 20
    # A related FVG must be created within this many candles of the event.
    FVG_WINDOW  = 5

    raw_obs = []

    for event in structure_events:
        event_idx  = event["idx"]
        event_type = event["event_type"]
        is_bull    = event_type.endswith("BULL")   # bullish displacement → bearish OB candle

        # ── Prerequisite: must have an FVG in the displacement leg ──────────
        fvg_kind  = "bullish" if is_bull else "bearish"
        fvg_found = None
        for fvg in fvgs:
            if (fvg["kind"] == fvg_kind and
                    abs(fvg["idx"] - event_idx) <= FVG_WINDOW):
                fvg_found = fvg
                break

        if fvg_found is None:
            continue   # no FVG → not a valid OB formation

        # ── Find the last opposite-color candle before the event ─────────────
        ob_idx = None
        for j in range(event_idx - 1, max(-1, event_idx - OB_LOOKBACK - 1), -1):
            if is_bull and closes[j] < opens[j]:   # bearish candle for bullish OB
                ob_idx = j
                break
            if not is_bull and closes[j] > opens[j]:  # bullish candle for bearish OB
                ob_idx = j
                break

        if ob_idx is None:
            continue

        c_open  = float(opens[ob_idx])
        c_close = float(closes[ob_idx])
        c_high  = float(highs[ob_idx])
        c_low   = float(lows[ob_idx])

        # ── Zone definition ──────────────────────────────────────────────────
        if is_bull:
            # Bearish candle: open > close; zone top = open, bottom = close
            zone_top    = c_open
            zone_bottom = c_close
            # Overlap exception: if OB wick (high) touches or enters the FVG
            if c_high >= fvg_found["bottom"]:
                zone_top    = c_high
                zone_bottom = c_low
        else:
            # Bullish candle: close > open; zone top = close, bottom = open
            zone_top    = c_close
            zone_bottom = c_open
            # Overlap exception: if OB wick (low) touches or enters the FVG
            if c_low <= fvg_found["top"]:
                zone_top    = c_high
                zone_bottom = c_low

        # Guard against zero-width zones (doji candles)
        if zone_top <= zone_bottom:
            zone_top = c_high
            zone_bottom = c_low
        if zone_top <= zone_bottom:
            continue

        mean_threshold = (zone_top + zone_bottom) / 2.0
        # Distal end: the boundary price would need to breach to invalidate the block
        # Bullish OB → distal = bottom (price breaks down through it)
        # Bearish OB → distal = top   (price breaks up  through it)
        distal = zone_bottom if is_bull else zone_top

        raw_obs.append({
            "idx":            ob_idx,
            "event_idx":      event_idx,   # BOS/CHoCH candle — lifecycle starts after this
            "timestamp":      timestamps[ob_idx],
            "kind":           "bullish" if is_bull else "bearish",
            "zone_top":       zone_top,
            "zone_bottom":    zone_bottom,
            "mean_threshold": mean_threshold,
            "distal":         distal,
            "caused_by":      event_type,
            "status":         "active",
            "touched_at":     None,
            "sapped_at":      None,
            "invalidated_at": None,
        })

    # ── Deduplicate: same OB candle can be referenced by multiple events ─────
    seen    = set()
    obs     = []
    for ob in raw_obs:
        key = (ob["idx"], ob["kind"])
        if key not in seen:
            seen.add(key)
            obs.append(ob)

    # ── Lifecycle tracking ───────────────────────────────────────────────────
    for ob in obs:
        # Lifecycle starts AFTER the BOS/CHoCH candle that created this OB, not just
        # after the OB candle itself. The event candle's wick almost always dips into
        # the OB as a liquidity grab before the explosive move — starting there would
        # immediately sap every valid OB before it ever gets a retest.
        start    = ob["event_idx"] + 1
        zt       = ob["zone_top"]
        zb       = ob["zone_bottom"]
        mt       = ob["mean_threshold"]
        is_bull_ob = ob["kind"] == "bullish"

        for j in range(start, len(df)):
            w_high = float(highs[j])
            w_low  = float(lows[j])
            b_high = max(float(opens[j]), float(closes[j]))
            b_low  = min(float(opens[j]), float(closes[j]))

            if is_bull_ob:
                # Price approaches from above, re-testing the OB zone
                if w_low <= zt and ob["touched_at"] is None:
                    ob["touched_at"] = j
                    if ob["status"] == "active":
                        ob["status"] = "touched"
                if b_low < zb:
                    # Body closed through the distal — structural level destroyed
                    ob["status"] = "invalidated"
                    ob["invalidated_at"] = j
                    break
                if w_low < zb:
                    # Wick swept through the distal without a body close — institutional
                    # interest at this level has been consumed; treat as hollow
                    ob["status"] = "sapped"
                    ob["sapped_at"] = j
                    break
                if b_low < mt and ob["status"] in ("active", "touched"):
                    ob["status"] = "degraded"
            else:
                # Price approaches from below, re-testing the OB zone
                if w_high >= zb and ob["touched_at"] is None:
                    ob["touched_at"] = j
                    if ob["status"] == "active":
                        ob["status"] = "touched"
                if b_high > zt:
                    # Body closed through the distal — structural level destroyed
                    ob["status"] = "invalidated"
                    ob["invalidated_at"] = j
                    break
                if w_high > zt:
                    # Wick swept through the distal without a body close — hollow
                    ob["status"] = "sapped"
                    ob["sapped_at"] = j
                    break
                if b_high > mt and ob["status"] in ("active", "touched"):
                    ob["status"] = "degraded"

    return obs


# ─── EQUAL HIGHS / EQUAL LOWS ─────────────────────────────────────────────────

def detect_eqh_eql(swing_highs: list, swing_lows: list,
                   atr: pd.Series, df: pd.DataFrame) -> list:
    """
    Detect Equal Highs (EQH) and Equal Lows (EQL) — resting liquidity pools.

    WHY: When two swing points form at nearly identical price levels, retail
    traders place stops just beyond them. Institutions deliberately drive price
    through these levels to harvest the liquidity before reversing. EQH/EQL are
    NOT entry signals — they are TARGET variables and trap detectors.

    Tolerance: abs(price1 - price2) <= ATR * EQH_EQL_ATR_TOLERANCE (0.05)

    Lifecycle: once a candle wick sweeps the level, the liquidity is consumed
    and the pool is marked "swept".

    Returns a list of liquidity pool dicts, each with:
      kind     — "eqh" | "eql"
      level    — the average price of the two matching swing points
      idx_1, idx_2   — candle indices of the two swings
      price_1, price_2
      swept    — bool; True once the level has been wicked through
      swept_at — candle index where swept, or None
    """
    highs_arr = df["high"].values
    lows_arr  = df["low"].values

    # Use the last valid ATR value as the tolerance ruler
    last_atr = None
    for val in reversed(atr.values):
        if not np.isnan(val):
            last_atr = float(val)
            break

    if last_atr is None:
        return []

    tolerance = last_atr * EQH_EQL_ATR_TOLERANCE
    pools     = []

    # ── Equal Highs ──────────────────────────────────────────────────────────
    for i in range(len(swing_highs)):
        for j in range(i + 1, len(swing_highs)):
            h1 = swing_highs[i]["price"]
            h2 = swing_highs[j]["price"]
            if abs(h1 - h2) <= tolerance:
                level = (h1 + h2) / 2.0
                pools.append({
                    "kind":    "eqh",
                    "level":   level,
                    "idx_1":   swing_highs[i]["idx"],
                    "idx_2":   swing_highs[j]["idx"],
                    "price_1": h1,
                    "price_2": h2,
                    "swept":   False,
                    "swept_at": None,
                })

    # ── Equal Lows ───────────────────────────────────────────────────────────
    for i in range(len(swing_lows)):
        for j in range(i + 1, len(swing_lows)):
            l1 = swing_lows[i]["price"]
            l2 = swing_lows[j]["price"]
            if abs(l1 - l2) <= tolerance:
                level = (l1 + l2) / 2.0
                pools.append({
                    "kind":    "eql",
                    "level":   level,
                    "idx_1":   swing_lows[i]["idx"],
                    "idx_2":   swing_lows[j]["idx"],
                    "price_1": l1,
                    "price_2": l2,
                    "swept":   False,
                    "swept_at": None,
                })

    # ── Sweep lifecycle ───────────────────────────────────────────────────────
    # Scan from FIRST swing point onward, not from the second.
    # A sweep can occur between idx_1 and idx_2 (e.g., price dips through the level
    # on the same move that forms the second equal low). Scanning only from idx_2+1
    # would miss that bar entirely. idx_2 itself is skipped — it's the formation of
    # the second swing, not a sweep of the pool.
    for pool in pools:
        start = pool["idx_1"] + 1
        lvl   = pool["level"]

        for j in range(start, len(df)):
            if j == pool["idx_2"]:
                continue  # second swing formation, not a sweep
            if pool["kind"] == "eqh":
                # A wick above the EQH level sweeps it
                if float(highs_arr[j]) > lvl:
                    pool["swept"]    = True
                    pool["swept_at"] = j
                    break
            else:
                # A wick below the EQL level sweeps it
                if float(lows_arr[j]) < lvl:
                    pool["swept"]    = True
                    pool["swept_at"] = j
                    break

    return pools


# ─── MAIN ENTRY POINT ──────────────────────────────────────────────────────────

def run(df: pd.DataFrame) -> dict:
    """
    Main entry point for the SMC analysis engine.

    Accepts a standard Banshee OHLCV DataFrame with columns:
      timestamp, open, high, low, close, volume

    Phase 1: ATR, swing detection, BOS/CHoCH state machine
    Phase 2: Fair Value Gaps (detect + lifecycle), Premium/Discount zones

    Returns the full structure dict with all computed objects.
    Returns {"error": str} if the DataFrame is too short or missing columns.
    """
    required_cols = {"open", "high", "low", "close"}
    if df.empty or not required_cols.issubset(df.columns):
        return {"error": "DataFrame is missing required OHLCV columns (open, high, low, close)"}

    min_candles = ATR_PERIOD + SWING_FRACTAL_CANDLES * 2 + 1
    if len(df) < min_candles:
        return {"error": f"Need at least {min_candles} candles, got {len(df)}"}

    swings = detect_swings(df)
    result = label_structure(df, swings)
    result["swings_all"] = swings   # convenience: all swings in one list

    # Phase 2 additions
    result["fvgs"]     = detect_fvgs(df, result["atr"])
    result["pd_zones"] = compute_pd_zones(
        result["swing_highs"], result["swing_lows"], result["current_state"]
    )

    # Phase 4 additions
    result["order_blocks"] = detect_order_blocks(
        df, result["structure_events"], result["fvgs"]
    )
    result["liquidity_pools"] = detect_eqh_eql(
        result["swing_highs"], result["swing_lows"], result["atr"], df
    )

    # ── Session weight ────────────────────────────────────────────────────────
    # Tag each OB with the session weight at its formation candle.
    # Also expose the current session weight (most recent candle) at the top level
    # so the AI prompt and Structure Map can reflect what session we're in right now.
    last_ts = df["timestamp"].iloc[-1] if "timestamp" in df.columns else df.index[-1]
    result["current_session_weight"] = get_session_weight(last_ts)
    for ob in result["order_blocks"]:
        ob["session_weight"] = get_session_weight(ob["timestamp"])

    # ── Inducement status ─────────────────────────────────────────────────────
    # For each OB, find any EQH/EQL pools sitting in the inducement zone:
    # the gap between current price and the OB zone.  Two fields are set:
    #   has_pending_inducement — unswept pool in the zone (trap is set, not yet fired)
    #   inducement_swept       — swept pool in the zone  (trap has fired, ready to enter)
    current_price = float(df["close"].iloc[-1])
    pools         = result["liquidity_pools"]

    for ob in result["order_blocks"]:
        ob_top    = ob["zone_top"]
        ob_bottom = ob["zone_bottom"]

        if ob["kind"] == "bullish":
            # Bullish OB is below price; inducement = EQL in the gap above the OB
            zone_pools = [
                p for p in pools
                if p["kind"] == "eql" and ob_top < p["level"] < current_price
            ]
        else:
            # Bearish OB is above price; inducement = EQH in the gap below the OB
            zone_pools = [
                p for p in pools
                if p["kind"] == "eqh" and current_price < p["level"] < ob_bottom
            ]

        ob["has_pending_inducement"] = any(not p["swept"] for p in zone_pools)
        ob["inducement_swept"]       = any(p["swept"]     for p in zone_pools)

    # Hard gate: tag OBs that have not yet met the inducement requirement.
    # Instead of filtering them out, mark gate_passed=False so they remain visible
    # as candidates (dashed/low-opacity on the Structure Map) while being excluded
    # from signal scoring and the AI prompt.
    for ob in result["order_blocks"]:
        if (INDUCEMENT_HARD_GATE
                and ob["status"] in ("active", "touched", "degraded")
                and not ob["inducement_swept"]):
            ob["gate_passed"] = False
        else:
            ob["gate_passed"] = True

    return result


# ─── HTF LEVEL CONFLUENCE ──────────────────────────────────────────────────────

def load_htf_levels() -> dict:
    """Load htf_levels.json from the Banshee 5 directory."""
    import json, os
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "htf_levels.json")
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


_HTF_SKIP_KEYS = frozenset({
    "note", "expiry_note", "current_context",
    "extracted_date", "source_symbol", "source_timeframe",
    "price_at_extraction", "_meta",
})


def _classify_level_type(name: str) -> str:
    n = name.lower()
    if "yearly" in n or "monthly" in n or "weekly" in n:
        return "yearly_monthly"
    if "market_maker" in n or "pd_" in n or "pw_" in n:
        return "market_maker"
    if "vwap" in n:
        return "vwap"
    if "elliott" in n or "fib_" in n or "impulse" in n or "wave" in n or "correction" in n:
        return "elliott_wave"
    return "other"


def flatten_levels(asset_dict: dict) -> list:
    """
    Flatten a single asset's htf_levels entry into [{name, price}] pairs.

    Walks the nested JSON tree and surfaces every numeric leaf as a named price
    level. Non-price metadata keys (notes, dates, etc.) are skipped.

    Returns a list sorted by price ascending.
    """
    result = []

    def _walk(obj, prefix):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k in _HTF_SKIP_KEYS:
                    continue
                _walk(v, f"{prefix}.{k}" if prefix else k)
        elif isinstance(obj, (int, float)) and not isinstance(obj, bool):
            result.append({"name": prefix, "price": float(obj), "level_type": _classify_level_type(prefix)})

    _walk(asset_dict, "")
    result.sort(key=lambda x: x["price"])
    return result


def tag_htf_confluence(result: dict, asset_levels: dict) -> None:
    """
    Add 'htf_confluence' list to every OB and FVG in result (in-place).

    A level is "near" if it falls within 1 ATR of the zone boundaries.
    Each confluence entry: {'name': str, 'price': float}

    WHY: When an OB or FVG coincides with a named institutional reference level
    (yearly open, market maker PD/PW, VWAP zone, Elliott Wave pivot), the
    two independent methods pointing to the same price raises conviction.
    This field doesn't change signal direction — it weights it higher.
    """
    atr_series = result.get("atr")
    if atr_series is None or atr_series.empty:
        return

    atr_val = None
    for v in reversed(atr_series.values):
        if not np.isnan(float(v)):
            atr_val = float(v)
            break
    if atr_val is None:
        return

    levels = flatten_levels(asset_levels)
    if not levels:
        return

    for ob in result.get("order_blocks", []):
        lo = ob["zone_bottom"] - atr_val
        hi = ob["zone_top"]    + atr_val
        ob["htf_confluence"] = [lv for lv in levels if lo <= lv["price"] <= hi]

    for fvg in result.get("fvgs", []):
        lo = fvg["bottom"] - atr_val
        hi = fvg["top"]    + atr_val
        fvg["htf_confluence"] = [lv for lv in levels if lo <= lv["price"] <= hi]
