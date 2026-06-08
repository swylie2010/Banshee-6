"""
knowledge_graph.py — Banshee Pro Ontology & Rule Engine
=========================================================
This module houses the deterministic rulesets of a Wall Street Portfolio Manager.
It converts raw data into semantic constants ('ALL CLEAR', 'CAUTION', 'CRACK DETECTED')
to ensure AI components (and future autonomous agents) operate within
impenetrable risk frameworks.
"""

def get_domino_state(sensors: dict) -> dict:
    """
    Evaluates the macro sensors and returns a structured logic state.
    """
    vix_elevated = sensors.get('vix', {}).get('warning', False)
    curve_inv = sensors.get('curve', {}).get('warning', False)
    credit_stress = sensors.get('credit', {}).get('warning', False)
    liq_draining = sensors.get('liquidity', {}).get('warning', False)
    btc_dropping = sensors.get('btc', {}).get('warning', False)
    dxy_surge = sensors.get('dxy', {}).get('warning', False)

    # Calculate Phase
    if curve_inv and credit_stress and liq_draining and (btc_dropping or vix_elevated):
        phase = 3
        state_str = "CRACK DETECTED"
        desc = "Systemic Contagion Phase. Liquidity is exiting markets rapidly. Rotate to cash or hard defensives."
    elif curve_inv and credit_stress and vix_elevated:
        phase = 2
        state_str = "CRACK DETECTED"
        desc = "Credit Stress Phase. Fixed income is pricing recession and fear is elevated."
    elif curve_inv or dxy_surge or liq_draining:
        phase = 1
        state_str = "CAUTION"
        desc = "Late Cycle Warning. The monetary weather is shifting. Reduce position sizes."
    else:
        phase = 0
        state_str = "ALL CLEAR"
        desc = "Market skies are clear. Normal risk-taking behavior is permitted."

    return {
        "phase": phase,
        "state_str": state_str, 
        "description": desc
    }


def classify_asset(symbol: str) -> str:
    """
    Maps a specific ticker to its fundamental financial profile. 
    Includes user-specific heavy trading assets (Crypto, Tokenized Metals).
    """
    sym = symbol.upper().replace("-USD", "").replace("/USD", "")
    
    # User's Crypto ecosystem + generic high vol
    high_beta = ["BTC", "ETH", "SOL", "SUI", "TAO", "HYPE", "AVAX", "NVDA", "TSLA", "SMCI", "MSTR", "COIN"]
    # Broad market indices and standard tech
    risk_on = ["SPY", "QQQ", "AAPL", "MSFT", "META", "IWM", "AMZN"]
    # Slow movers, safe havens, and staples
    defensive = ["XLE", "XLU", "XLP", "GLD", "PAXG", "SILVER", "XAG", "JNJ", "WMT", "TLT", "IEF"]
    cash = ["SGOV", "SHV", "USDC", "USDT"]

    if sym in high_beta: return "High-Beta"
    if sym in risk_on: return "Risk-On"
    if sym in defensive: return "Defensive"
    if sym in cash: return "Cash-Equivalent"
    
    # Fallbacks based on common heuristics
    if "/" in symbol or "-USD" in symbol:
        return "High-Beta"  # Unmapped crypto
    
    return "Unknown/Standard Edge"


def evaluate_asset_safety(symbol: str, domino_phase: int) -> dict:
    """
    The Bouncer. Evaluates if the current Macro Domino Phase allows
    for taking risk on the given asset class.
    """
    category = classify_asset(symbol)
    
    is_hostile = False
    rationale = f"Asset is {category}. Environment allows for standard positioning."
    
    if domino_phase == 2:
        if category == "High-Beta":
            is_hostile = True
            rationale = "Domino Phase 2 (Credit Stress) historically punishes High-Beta assets severely. Capital preservation is priority."
        else:
            rationale = "Domino Phase 2 favors Defensive positioning, but broad markets may still exhibit chop."
            
    elif domino_phase >= 3:
        if category in ["High-Beta", "Risk-On"]:
            is_hostile = True
            rationale = "Domino Phase 3 (Contagion/Liquidity Drain) requires absolute avoidance of Risk-On and High-Beta. Sector rotations point strictly to Cash or Defensives (Staples/Utilities)."
        elif category == "Defensive":
            rationale = "Domino Phase 3 active. Defensive assets (Gold, Treasuries, Utilities) are the only permitted long allocations."

    return {
        "category": category,
        "is_hostile": is_hostile,
        "rationale": rationale
    }


def identify_micro_setup(indicators: dict) -> str:
    """
    Translates raw math into a named pattern (Confluence Map).
    indicators expected: rsi (float), bb_pos (float), macd_bull_cross (bool), obv_up (bool), price_over_ema50 (bool)
    """
    if not indicators: 
        return "No clear setup structure"
        
    rsi = indicators.get("rsi", 50)
    bb_pos = indicators.get("bb_pos", 0.5)
    macd_bull = indicators.get("macd_bull", False)
    obv_up = indicators.get("obv_up", False)
    price_over_ema50 = indicators.get("price_over_ema50", False)
    
    if rsi < 35 and bb_pos < 0.15 and macd_bull:
        return "Exhaustion Reversion (Deep oversold bounce with momentum shift)"
    elif rsi > 65 and bb_pos > 0.85 and not macd_bull:
        return "Topping Exhaustion (Stretched upside momentum fading)"
    elif price_over_ema50 and macd_bull and obv_up and rsi > 50 and rsi < 70:
        return "Trend Continuation (Healthy accumulation channel)"
    elif not price_over_ema50 and not macd_bull and not obv_up and rsi < 50:
        return "Trend Breakdown (Distribution cascade)"
        
    return "Choppy / Indecision Market"

def detect_contradictions(sensors: dict) -> list:
    """
    Scans macro sensors for named contradiction patterns — gradient signals
    that individually fall below warning thresholds but form a recognizable
    institutional footprint when combined.

    These are injected into the AI prompt and UI so gradient danger is visible
    even when the headline risk score appears calm.

    Returns a list of {"name", "severity", "description"} dicts.
    Severity: "HIGH" | "MEDIUM"
    """
    patterns = []

    vix_warn     = sensors.get("vix", {}).get("warning", False)
    curve_warn   = sensors.get("curve", {}).get("warning", False)
    credit_warn  = sensors.get("credit", {}).get("warning", False)
    liq_warn     = sensors.get("liquidity", {}).get("warning", False)
    btc_warn     = sensors.get("btc", {}).get("warning", False)
    dxy_warn     = sensors.get("dxy", {}).get("warning", False)
    skew_warn    = sensors.get("skew", {}).get("warning", False)
    copper_warn  = sensors.get("copper", {}).get("warning", False)
    rotation_warn = sensors.get("rotation", {}).get("warning", False)

    skew_elevated = sensors.get("skew", {}).get("status") in ("TAIL RISK", "ELEVATED")
    gold_fear     = sensors.get("gold", {}).get("status") == "FEAR BUYING"
    xle_harbor    = sensors.get("xle", {}).get("status") == "SAFE HARBOR"
    risk_score    = sensors.get("risk_score", 0)

    # 1. Smart money buying crash protection while retail is calm
    if skew_warn and not vix_warn:
        patterns.append({
            "name": "STEALTH_FEAR_PATTERN",
            "severity": "HIGH",
            "description": (
                "SKEW (institutional tail-risk hedging) is elevated but VIX is calm. "
                "Smart money is quietly buying crash protection before retail panics. "
                "This gap historically closes violently — VIX spike is the likely resolution."
            )
        })

    # 2. Liquidity draining silently before markets notice
    if liq_warn and not vix_warn and not curve_warn:
        patterns.append({
            "name": "LIQUIDITY_TRAP",
            "severity": "HIGH",
            "description": (
                "Fed liquidity is draining but VIX and the yield curve remain benign. "
                "Markets are pricing in 'enough' liquidity. When the drain reaches "
                "market structure, corrections feel sudden. Watch for VIX spike as confirmation."
            )
        })

    # 3. Bond market sees stress that equity vol ignores
    if credit_warn and not vix_warn and not btc_warn:
        patterns.append({
            "name": "CREDIT_DENIAL",
            "severity": "MEDIUM",
            "description": (
                "Credit markets (HYG underperforming IEF) are pricing stress that equity "
                "vol (VIX) hasn't absorbed. Bond markets lead equities. This divergence "
                "typically resolves via equity drawdown, not credit recovery."
            )
        })

    # 4. Dollar + liquidity drain: double squeeze on global capital
    if dxy_warn and liq_warn:
        patterns.append({
            "name": "DXY_LIQUIDITY_SQUEEZE",
            "severity": "HIGH",
            "description": (
                "Dollar surging AND Fed liquidity draining simultaneously — a double-barrel "
                "squeeze on global risk capital. Historically lethal for EM assets, crypto, "
                "and leveraged positions. Reduce size aggressively."
            )
        })

    # 5. Crypto canary leading TradFi by 2-4 weeks
    if btc_warn and risk_score < 30:
        patterns.append({
            "name": "CANARY_DIVERGENCE",
            "severity": "MEDIUM",
            "description": (
                "BTC (risk canary) is dropping materially while the broader risk score "
                "remains low. Crypto typically leads traditional markets by 2-4 weeks. "
                "Do not dismiss as crypto noise — watch for TradFi follow-through."
            )
        })

    # 6. Quiet sector rotation before the headline alarm
    if (xle_harbor or rotation_warn) and risk_score < 25:
        patterns.append({
            "name": "DEFENSIVE_ROTATION_STEALTH",
            "severity": "MEDIUM",
            "description": (
                "Defensive sector rotation is occurring (Energy/Utilities outperforming SPY) "
                "while the headline risk score appears low. Institutions are repositioning "
                "ahead of a regime shift that won't appear in VIX until later."
            )
        })

    # 7. Dual fear indicators contradict the headline regime
    if gold_fear and skew_elevated and risk_score < 40:
        patterns.append({
            "name": "GOLD_SKEW_DIVERGENCE",
            "severity": "HIGH",
            "description": (
                "Gold is in active fear-buying mode AND SKEW is elevated, "
                "but the headline risk score doesn't reflect full alarm. "
                "This dual below-the-surface fear signal is often the last warning "
                "before a sharp risk-off move."
            )
        })

    # 8. Two leading recession indicators in agreement
    if copper_warn and credit_warn:
        patterns.append({
            "name": "COPPER_CREDIT_RECESSION_SIGNAL",
            "severity": "HIGH",
            "description": (
                "Dr. Copper (economic growth proxy) AND credit spreads are both warning. "
                "Two of the most reliable leading recession indicators are in agreement. "
                "Probability of growth deceleration is materially elevated — not noise."
            )
        })

    return patterns


def get_regime_weights(sensors: dict) -> tuple:
    """
    Determines the current macro regime bucket and returns corresponding
    indicator weight multipliers for score_timeframe().

    Multipliers scale the existing asset-profile weights:
      1.0 = no change   0.5 = halve the contribution   1.5 = amplify by 50%

    Buckets:
      FEAR     — VIX > 25 OR domino_phase >= 2
      CAUTION  — domino_phase == 1 OR VIX 18-25
      TRENDING — VIX < 15 AND domino_phase == 0 AND risk_score < 20
      NEUTRAL  — everything else (no adjustments)

    Contradiction bump: STEALTH_FEAR_PATTERN, LIQUIDITY_TRAP, or CREDIT_DENIAL
    in the contradictions list escalates NEUTRAL → CAUTION, CAUTION → FEAR.
    This catches fear that hasn't yet registered in VIX.

    Returns (bucket_name: str, multipliers: dict).
    """
    vix_val    = sensors.get("vix", {}).get("value") or 0.0
    phase      = sensors.get("domino_phase", 0)
    risk_score = sensors.get("risk_score", 0)
    contradictions = [c.get("name", "") for c in sensors.get("contradictions", [])]

    escalating = any(c in contradictions for c in (
        "STEALTH_FEAR_PATTERN", "LIQUIDITY_TRAP", "CREDIT_DENIAL",
    ))

    # Determine base bucket
    if phase >= 2 or vix_val > 25:
        bucket = "FEAR"
    elif phase == 1 or vix_val > 18:
        bucket = "CAUTION"
    elif 0 < vix_val < 15 and phase == 0 and risk_score < 20:
        bucket = "TRENDING"
    else:
        bucket = "NEUTRAL"

    # Contradiction bump — escalate one level regardless of hard thresholds
    if escalating:
        if bucket == "NEUTRAL":
            bucket = "CAUTION"
        elif bucket == "CAUTION":
            bucket = "FEAR"

    _WEIGHTS = {
        "FEAR": {
            # Trend-followers whipsaw badly in fear regimes
            "supertrend":  0.5,
            "ema_stack":   0.8,
            "ema_price":   0.8,
            # Oscillators overshoot — RSI can stay at 20 for days
            "rsi":         0.7,
            "stoch_rsi":   0.7,
            "macd":        0.7,
            # Volume signals become MORE informative — capitulation is real
            "obv_leading": 1.2,
            # BB outer touches are more meaningful when bands are wide
            "bb_slow":     1.2,
            # adx, obv, bb_fast, vwap unchanged (1.0)
        },
        "CAUTION": {
            # Early whipsaw risk — mild reduction, not dramatic
            "supertrend": 0.8,
            "rsi":        0.85,
            "stoch_rsi":  0.85,
        },
        "TRENDING": {
            # Supertrend's best environment — smooth, directional price
            "supertrend": 1.5,
            "adx":        1.3,
            "ema_stack":  1.2,
            # RSI stays overbought/oversold for weeks in strong trends
            "rsi":        0.9,
        },
        "NEUTRAL": {},
    }

    return bucket, _WEIGHTS[bucket]


def calculate_asymmetry_score(micro_data: dict, domino_phase: int) -> dict:
    """
    Calculates the Asymmetry Score ("The Human Edge / Autonomous Agent 20% Wallet").
    Identifies setups with low probability but extreme payout (high asymmetry).
    Factors in divergences (W/M formations), support proximity, squeeze mechanics,
    and macro/micro conflicts.
    """
    score = 0
    reasons = []

    verdict = micro_data.get("verdict", "")
    is_bullish = ("BUY" in verdict)
    is_bearish = ("SELL" in verdict)
    
    safety = micro_data.get("asset_safety", {})
    is_hostile = safety.get("is_hostile", False)
    
    setup = micro_data.get("setup_name", "")
    funding = micro_data.get("funding_rate", {})
    warnings = micro_data.get("warnings", {})
    
    # 1. Macro/Micro Conflict (Contrarian Bet) -> +30
    if is_bullish and is_hostile:
        score += 30
        reasons.append("Contrarian Long: Strong micro setup but Macro is hostile (Leap of faith).")
    elif is_bearish and domino_phase == 0:
        score += 30
        reasons.append("Contrarian Short: Absolute market is risk-on, but asset is breaking down loudly.")

    # 2. Reversion / Divergences (W/M Formations & Stoch Bottoms) -> +30
    if "Exhaustion Reversion" in setup or "Topping Exhaustion" in setup:
        score += 15
        reasons.append("Exhaustion identified. High reward if reversion holds.")
        
    divergences = warnings.get("rsi_divergences", [])
    if divergences:
        score += 15
        reasons.append(f"Divergence Action ({', '.join(divergences)}). Potential W/M structure.")

    # 3. Squeeze Mechanics -> +25
    if funding.get("available") and funding.get("rate_pct") is not None:
        rate = funding.get("rate_pct", 0)
        # Highly negative funding means heavy shorting. A long here could squeeze them.
        if is_bullish and rate <= -0.01:
            score += 25
            reasons.append("Massive short squeeze potential (negative funding).")
        # Highly positive funding means long crowding. A short here could flush them.
        elif is_bearish and rate >= 0.01:
            score += 25
            reasons.append("Massive long flush potential (positive funding).")

    # 4. Deep Extremes & Support Proximity -> +15
    edge = abs(micro_data.get("edge", 0))
    if edge >= 6:
        score += 15
        reasons.append("Extreme quantitative micro conviction despite noise.")

    score = min(max(int(score), 0), 100)
    
    label = "Standard Probability"
    if score >= 70:
        label = "HIGH ASYMMETRY (20% Wallet / Human Edge)"
    elif score >= 45:
        label = "Elevated Asymmetry"

    return {
        "score": score,
        "label": label,
        "reasons": reasons
    }
