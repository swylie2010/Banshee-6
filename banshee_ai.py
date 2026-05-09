"""
banshee_ai.py — The Banshee Synthesis Brain
===========================================
This module combines macro regime data and micro technical data
into a unified prompt, allowing the AI to evaluate technical breakouts
within the context of global risk.
"""

import math
from datetime import datetime, timezone



def build_banshee_prompt(macro_data: dict, micro_data: dict, news_lines: list = [], manual_stories: list = [], include_macro: bool = True, geo_harmonic_context: str = "") -> str:
    """
    Constructs the prompt for the AI acting as the Banshee Pro quantitative analyst.
    If include_macro is True, it injects the Macro Regime warnings to context-adjust the read.
    """
    # ── Micro Asset Data Extraction
    symbol  = micro_data.get("symbol", "UNKNOWN")
    price   = micro_data.get("price", "UNKNOWN")
    verdict = micro_data.get("verdict", "UNKNOWN")
    edge    = micro_data.get("edge", "UNKNOWN")
    eq      = micro_data.get("entry_quality", {})
    eq_lbl  = eq.get("quality", "UNKNOWN")
    safety  = micro_data.get("asset_safety", {})
    setup   = micro_data.get("setup_name", "Unknown Setup")
    
    trend_keys = list(micro_data.get("trends", {}).keys())
    trend_keys += ["Slow", "Mid", "Fast"][len(trend_keys):3]  # pad to 3 if any timeframe is missing
    slow, mid, fast = trend_keys[:3]
    trends  = micro_data.get("trends", {})
    
    vol     = micro_data.get("volume", "UNKNOWN")
    funding = micro_data.get("funding_rate", {})
    f_rate  = funding.get("rate_pct", "N/A")
    f_risk  = funding.get("risk_label", "N/A")

    # ── Initial Prompt Assembly
    date_str = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')
    
    prompt = f"DATE: {date_str} UTC\n"
    prompt += f"Analyze the asset {symbol} which is currently trading at ${price}.\n\n"
    
    if safety:
        prompt += f"ASSET CLASSIFICATION: {safety.get('category', 'Unknown')}\n"
        prompt += f"MACRO HOSTILITY CHECK: {'HOSTILE - DO NOT BUY' if safety.get('is_hostile') else 'PERMITTED'}\n"
        prompt += f"SAFETY RATIONALE: {safety.get('rationale', '')}\n\n"
    
    prompt += f"--- MICRO ASSET TECHNICALS ---\n"
    prompt += f"CONFLUENCE SETUP: {setup}\n"
    prompt += f"ALGORITHMIC VERDICT: {verdict} (Score Edge: {edge})\n"
    prompt += f"ENTRY TIMING QUALITY: {eq_lbl}\n"
    if eq.get("reasons"):
        prompt += "Timing Notes: " + " | ".join(eq["reasons"]) + "\n"
        
    asym = micro_data.get("asymmetry", {})
    if asym:
        prompt += f"\nASYMMETRY SCORE (HUMAN EDGE FACTOR): {asym.get('score', 0)}/100 - {asym.get('label', 'Standard')}\n"
        if asym.get("reasons"):
            prompt += "Asymmetry Rationale: " + " | ".join(asym["reasons"]) + "\n"

    prompt += f"\nTrend Alignment:\n- {slow} Trend: {trends.get(slow, 'UNKNOWN')}\n- {mid} Trend: {trends.get(mid, 'UNKNOWN')}\n- {fast} Trend: {trends.get(fast, 'UNKNOWN')}\n\n"
    
    if funding.get("available"):
        prompt += f"Funding Rate Squeeze Risk: {f_risk} ({f_rate}%)\n"
    prompt += f"Volume Pressure: {vol}\n\n"
    
    # ── Conditionally Add Macro Context
    if include_macro and macro_data:
        regime    = macro_data.get("regime", "UNKNOWN")
        warnings  = macro_data.get("warning_count", 0)
        risk_score = macro_data.get("risk_score", 0)
        
        prompt += f"--- MACRO WEATHER ENVIRONMENT (Crucial Context) ---\n"
        prompt += f"The holistic macroeconomic environment is currently categorized as:\n"
        prompt += f"REGIME: {regime}\n"
        prompt += f"SYSTEMIC RISK SCORE: {risk_score}/100\n"
        prompt += f"ACTIVE SENSOR WARNINGS: {warnings}\n\n"
        
        prompt += "KEY RISK SENSORS TRIPPED:\n"
        for name, s in macro_data.items():
            if isinstance(s, dict) and s.get("warning", False):
                prompt += f"- {name.upper()}: {s.get('status')} ({s.get('sub')})\n"

        contradictions = macro_data.get("contradictions", [])
        if contradictions:
            prompt += "\nCONTRADICTION PATTERNS (below-threshold signals forming institutional footprints):\n"
            for c in contradictions:
                prompt += f"  [{c['severity']}] {c['name']}: {c['description']}\n"
            prompt += (
                "INSTRUCTION ADDENDUM: The contradiction patterns above are deterministic signals "
                "that individually fall below headline alarm thresholds but together indicate "
                "gradient danger. You MUST factor these into your MACRO OVERLAY section. "
                "Name each pattern explicitly in your briefing.\n"
            )

    # ── Append Intel Feeds & Injections
    if manual_stories:
        prompt += "\n--- USER INJECTED CONSTRAINTS (Highest Priority) ---\n"
        prompt += "The user has provided the following specific constraints or headlines to anchor your thesis:\n"
        for i, ms in enumerate(manual_stories):
            prompt += f"- {ms}\n"

    if news_lines:
        prompt += "\n--- MARKET INTEL (News Catalysts) ---\n"
        prompt += (
            "News events and catalysts below. IMPORTANT: these are narrative context only. "
            "The MACRO WEATHER SENSOR DATA above is the authoritative quantitative risk signal — "
            "do NOT let news tone override it. If sensors show ALL CLEAR, the macro regime is ALL CLEAR "
            "even if headlines sound alarming. Factor in news only for catalyst timing and asset-specific events.\n"
        )
        for line in news_lines:
            prompt += f"{line}\n"

    if geo_harmonic_context:
        prompt += "\n--- GEO HARMONIC CONTEXT ---\n"
        prompt += geo_harmonic_context + "\n"

    if include_macro and macro_data:
        prompt += "\nINSTRUCTION: Analyze the asset's technicals within this macro environment. "
        prompt += "If the micro technicals are bullish (Strong Buy, Buy Setup) but the Macro Regime is CAUTION or CRACK DETECTED, "
        prompt += "you MUST WARN the user that this breakout is occurring in a hostile macro environment. "
        prompt += "Conversely, if the macro environment is strong (ALL CLEAR), confirm that the tailwind supports the technicals.\n"
    else:
        prompt += "INSTRUCTION: Analyze the asset's technicals purely on its own merits without macro context.\n"

    if geo_harmonic_context:
        prompt += ("If a Geo Harmonic hot zone sits within 3% of current price, address whether price is approaching "
                   "from the expected direction: a ▼ ceiling zone is resistance when price approaches from below; "
                   "a ▲ floor zone is support when price approaches from above.\n")
        
    prompt += "\nFormat your briefing as:\n"
    prompt += "1. THE VERDICT: Direct summary of what to do (1 sentence).\n"
    prompt += "2. THE 'WHY': 1 paragraph explaining the interplay between the technical setup today and the entry quality.\n"
    if include_macro:
        prompt += "3. MACRO OVERLAY: 1 paragraph explicitly addressing how the current Macro regime changes the risk profile of this specific trade.\n"
    prompt += "4. RISK PARAMETERS: Brief note on squeeze risk or notable obstacles.\n"

    return prompt

def call_ai(cfg: dict, prompt: str, system_prompt_override: str = None) -> str:
    """Executes the AI request using either Gemini or Claude.

    Pass system_prompt_override to replace the default Banshee system prompt.
    Used by smc_analysis() which needs a different analyst persona.
    """
    system_prompt = system_prompt_override or (
        "You are OpenClaw / Banshee: an autonomous quantitative agent. "
        "You MUST strictly obey the Macro Hostility Check. If an asset is flagged as HOSTILE, "
        "you are absolutely forbidden from recommending a long position, regardless of how bullish the Micro Technicals are... "
        "HOWEVER, if the Asymmetry Score (Human Edge Factor) indicates HIGH ASYMMETRY (20% Wallet), "
        "you are AUTHORIZED and EXPECTED to recognize this as an exceptional 'Creative Risk' trade. "
        "In these asymmetric cases, prioritize the massive reward skew over standard probability warnings. "
        "Format briefings exactly as requested."
    )
    try:
        if cfg["type"].lower() == "gemini":
            import google.genai as genai
            client   = genai.Client(api_key=cfg["key"])
            response = client.models.generate_content(
                model=cfg["model"], 
                contents=prompt,
                config=genai.types.GenerateContentConfig(
                    system_instruction=system_prompt
                )
            )
            return response.text

        elif cfg["type"].lower() == "claude":
            import anthropic
            client = anthropic.Anthropic(api_key=cfg["key"])
            msg    = client.messages.create(
                model=cfg["model"],
                max_tokens=1024,
                system=system_prompt,
                messages=[{"role": "user", "content": prompt}]
            )
            return msg.content[0].text

    except Exception as e:
        return f"AI call failed: {e}"

    return "Unknown provider type."


# ─────────────────────────────────────────────────────────────────────────────
# SMC STRUCTURE ANALYST  (Phase 3)
# ─────────────────────────────────────────────────────────────────────────────

def _build_smc_context(label: str, tf: str, df, smc_data: dict,
                       flat_levels: list = None) -> str:
    """
    Serialise one timeframe's SMC output into compact, LLM-readable text.

    WHY compact text rather than raw JSON: the LLM reads this like a briefing
    document — named sections, human units, directional language. Dumping raw
    nested dicts produces worse reasoning than a structured paragraph form.
    """
    current_price = float(df["close"].iloc[-1])

    # ATR — used for expressing FVG distances in volatility-normalised units
    atr_series = smc_data.get("atr")
    current_atr = None
    if atr_series is not None and len(atr_series) > 0:
        raw = float(atr_series.iloc[-1])
        if not math.isnan(raw):
            current_atr = raw

    state    = smc_data.get("current_state", "UNDEFINED")
    pd_zones = smc_data.get("pd_zones")

    lines = [f"=== {label} ({tf}) — {state} ==="]

    # ── Dealing range + price position ──────────────────────────────────────
    if pd_zones:
        rh      = pd_zones["range_high"]
        rl      = pd_zones["range_low"]
        eq      = pd_zones["equilibrium"]
        ote_bot = pd_zones["ote_bottom"]
        ote_top = pd_zones["ote_top"]

        in_ote     = ote_bot <= current_price <= ote_top
        zone_label = "IN PREMIUM" if current_price > eq else "IN DISCOUNT"
        if in_ote:
            zone_label += " (OTE)"
        dist_to_eq = current_price - eq

        lines.append(
            f"Dealing Range: {rl:,.2f} – {rh:,.2f} | "
            f"EQ: {eq:,.2f} | OTE: {ote_bot:,.2f} – {ote_top:,.2f}"
        )
        lines.append(
            f"Price: {current_price:,.2f} → {zone_label} "
            f"(dist to EQ: {dist_to_eq:+,.2f})"
        )
    else:
        lines.append(f"Price: {current_price:,.2f} | Dealing range: not computed")

    # ── Recent structure events (last 4) ────────────────────────────────────
    events = smc_data.get("structure_events", [])
    if events:
        lines.append("Recent Structure Events (newest last):")
        for ev in events[-4:]:
            lines.append(f"  {ev['event_type']} @ {ev['price']:,.2f}")
    else:
        lines.append("Structure Events: None detected")

    # ── Swing sequence (last 6 swing points by time) ────────────────────────
    swing_highs = smc_data.get("swing_highs", [])
    swing_lows  = smc_data.get("swing_lows",  [])
    all_recent  = sorted(swing_highs[-4:] + swing_lows[-4:], key=lambda s: s["idx"])
    if all_recent:
        seq = " → ".join(
            f"{s.get('label','?')}({'H' if s['swing_type']=='high' else 'L'})"
            for s in all_recent[-6:]
        )
        lines.append(f"Swing Sequence: {seq}")

    # ── Unmitigated FVGs nearest price (up to 4) ────────────────────────────
    fvgs        = smc_data.get("fvgs", [])
    active_fvgs = [f for f in fvgs if f["status"] in ("active", "partial")]
    if active_fvgs:
        def _dist(fvg):
            mid = (fvg["top"] + fvg["bottom"]) / 2.0
            return abs(mid - current_price) / (current_atr or 1.0)

        nearby = sorted(active_fvgs, key=_dist)[:4]
        lines.append("Unmitigated FVGs (nearest first):")
        for fvg in nearby:
            mid        = (fvg["top"] + fvg["bottom"]) / 2.0
            signed_atr = ((mid - current_price) / current_atr) if current_atr else 0
            direction  = "above" if signed_atr > 0 else "below"
            lines.append(
                f"  {fvg['kind'].upper()} FVG {fvg['bottom']:,.2f}–{fvg['top']:,.2f} "
                f"({fvg['status']}, {abs(signed_atr):.1f} ATR {direction} price)"
            )
    else:
        lines.append("Unmitigated FVGs: None")

    # ── Active Order Blocks nearest price (up to 3) ───────────────────────────
    obs        = smc_data.get("order_blocks", [])
    active_obs = [o for o in obs if o["status"] in ("active", "touched", "degraded") and o.get("gate_passed", True)]
    if active_obs:
        def _ob_dist(ob):
            mid = (ob["zone_top"] + ob["zone_bottom"]) / 2.0
            return abs(mid - current_price) / (current_atr or 1.0)

        nearby_obs = sorted(active_obs, key=_ob_dist)[:3]
        lines.append("Active Order Blocks (nearest first):")
        for ob in nearby_obs:
            mid   = (ob["zone_top"] + ob["zone_bottom"]) / 2.0
            dist  = ((mid - current_price) / current_atr) if current_atr else 0
            dirn  = "above" if dist > 0 else "below"
            lines.append(
                f"  {ob['kind'].upper()} OB {ob['zone_bottom']:,.2f}–{ob['zone_top']:,.2f} "
                f"({ob['status']}, {abs(dist):.1f} ATR {dirn} price)"
            )
    else:
        lines.append("Active Order Blocks: None")

    # ── Live liquidity pools (EQH/EQL) ────────────────────────────────────────
    pools      = smc_data.get("liquidity_pools", [])
    live_pools = [p for p in pools if not p["swept"]]
    if live_pools:
        lines.append("Unswept Liquidity Pools (EQH/EQL):")
        for p in live_pools[:4]:
            dist  = ((p["level"] - current_price) / current_atr) if current_atr else 0
            dirn  = "above" if dist > 0 else "below"
            lines.append(
                f"  {p['kind'].upper()} @ {p['level']:,.2f} "
                f"({abs(dist):.1f} ATR {dirn} price)"
            )
    else:
        lines.append("Liquidity Pools: None")

    # ── Named HTF reference levels (within 5 ATR of current price) ───────────
    if flat_levels and current_atr:
        nearby = [
            lv for lv in flat_levels
            if abs(lv["price"] - current_price) <= 5.0 * current_atr
        ]
        if nearby:
            lines.append("Named HTF Reference Levels (within 5 ATR):")
            for lv in sorted(nearby, key=lambda x: abs(x["price"] - current_price)):
                short = lv["name"].rsplit(".", 1)[-1].replace("_", " ")
                dist  = (lv["price"] - current_price) / current_atr
                dirn  = "above" if dist > 0 else "below"
                lines.append(
                    f"  {short}: {lv['price']:,.2f} ({abs(dist):.1f} ATR {dirn} price)"
                )

    return "\n".join(lines)


def build_smc_prompt(symbol: str,
                     htf_tf: str, htf_df, htf_smc: dict,
                     ltf_tf: str, ltf_df, ltf_smc: dict,
                     flat_levels: list = None) -> str:
    """
    Assembles the full SMC analysis prompt from two timeframes of engine output.
    Passed to call_ai() with the SMC-specific system prompt.
    """
    htf_block = _build_smc_context("HTF STRUCTURE", htf_tf, htf_df, htf_smc,
                                   flat_levels=flat_levels)
    ltf_block = _build_smc_context("LTF STRUCTURE", ltf_tf, ltf_df, ltf_smc,
                                   flat_levels=flat_levels)

    htf_state = htf_smc.get("current_state", "UNDEFINED")
    ltf_state = ltf_smc.get("current_state", "UNDEFINED")

    if htf_state == "UNDEFINED" or ltf_state == "UNDEFINED":
        alignment = "INSUFFICIENT DATA — one or both timeframes undefined"
    elif htf_state == ltf_state:
        alignment = f"ALIGNED — both timeframes {htf_state}"
    else:
        alignment = f"CONFLICTED — HTF {htf_state} vs LTF {ltf_state}"

    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    current_price = float(ltf_df["close"].iloc[-1])

    return f"""DATE: {date_str}
ASSET: {symbol} | Current Price: {current_price:,.2f}

{htf_block}

{ltf_block}

=== CROSS-TF ALIGNMENT ===
HTF ({htf_tf}) Bias: {htf_state} | LTF ({ltf_tf}) Bias: {ltf_state}
Alignment: {alignment}

=== REASONING TASK ===
Work through these steps in order:
1. What is HTF structure saying? (state, FVG locations, dealing range position)
2. What is LTF structure saying? (recent BOS/CHoCH, micro bias)
3. Do HTF and LTF agree or conflict?
4. Where is price relative to EQ, OTE, and unmitigated FVGs?
5. What scenario does this structural setup point to?
"""


_SMC_SYSTEM_PROMPT = (
    "You are Banshee's SMC Structure Analyst — a Smart Money Concepts specialist.\n"
    "Your job: read market structure across two timeframes and produce a concise, "
    "grounded narrative for a human trader.\n\n"
    "RULES:\n"
    "1. Follow the reasoning chain in order. Do not skip steps.\n"
    "2. Be direct and specific. Reference actual price levels from the data.\n"
    "3. No hedging with 'may' or 'might' unless the data is genuinely ambiguous.\n"
    "4. If HTF and LTF conflict, call it out explicitly — that IS a signal.\n"
    "5. You are reading structure, not recommending trades.\n"
    "6. Keep the total response under 300 words.\n"
    "7. Every SMC term (CHoCH, BOS, OB, FVG, OTE, EQH, EQL, etc.) must be followed "
    "by a plain-English clarification in parentheses on first use. "
    "Example: 'A CHoCH (structure shift — short-term trend just reversed) occurred at 82,400.'\n"
    "8. If Named HTF Reference Levels appear in the data: when an OB or FVG coincides "
    "with one of these levels, call it out explicitly. Example: 'The bullish OB at 189.50 "
    "aligns with the Yearly Open at 189.84 — institutional confluence.' If no levels are "
    "provided, skip this step.\n\n"
    "REQUIRED FORMAT — 4 sections, 2-3 sentences each:\n"
    "**HTF READ:** [what the higher timeframe structure is saying]\n"
    "**LTF READ:** [what the lower timeframe is doing right now]\n"
    "**PRICE POSITION:** [where price sits relative to EQ, OTE, key FVGs, and any named reference levels]\n"
    "**SCENARIO:** [what this structural setup points to — the most probable next move]"
)


def smc_analysis(symbol: str,
                 htf_tf: str, htf_df, htf_smc: dict,
                 ltf_tf: str, ltf_df, ltf_smc: dict,
                 cfg: dict,
                 flat_levels: list = None) -> str:
    """
    Generate an AI narrative for SMC cross-timeframe structure.

    Inputs:
      symbol           — ticker string for display (e.g. "BTC/USD")
      htf_tf / htf_df / htf_smc — higher timeframe label, OHLCV df, smc_engine.run() output
      ltf_tf / ltf_df / ltf_smc — lower timeframe equivalents
      cfg              — AI provider config dict (from load_providers())
      flat_levels      — optional list from smc_engine.flatten_levels(); if provided,
                         nearby named reference levels are included in the AI context

    Returns the narrative string or an error message prefixed with "AI call failed:".
    """
    prompt = build_smc_prompt(symbol, htf_tf, htf_df, htf_smc,
                              ltf_tf, ltf_df, ltf_smc,
                              flat_levels=flat_levels)
    return call_ai(cfg, prompt, system_prompt_override=_SMC_SYSTEM_PROMPT)
