# **Systemic Architecture and Heuristic Rules for Algorithmic Smart Money Concepts (SMC)**

The translation of discretionary trading frameworks into deterministic algorithmic models requires the codification of visual heuristics into strict mathematical rules, boolean flags, and object lifecycles. Smart Money Concepts (SMC), fundamentally rooted in the analysis of institutional order flow, liquidity engineering, and market structure shifts, present a unique challenge for quantitative development.1 The methodology inherently relies on subjective visual pattern recognition. The objective of this architecture is to establish a definitive, mechanically rigid rulebook that strips away discretionary ambiguity. This allows a deterministic script to detect high-probability chart anomalies, track their lifecycles, and package them as structured data payloads for artificial intelligence evaluation. This specification establishes the core mathematical primitives, state machines, object schemas, and heuristic scoring matrices required to build a systemic Smart Money Concepts engine capable of communicating market context through natural language generation.

## **Foundational Mathematical Primitives**

Before complex institutional patterns can be identified, the system must establish a normalized mathematical baseline to interpret price action dynamically. Hardcoded tick or pip values fail across varying asset classes and timeframes due to differing volatility regimes.3 To resolve this, all spatial tolerances within the system are governed by a dynamic volatility metric.

### **Average True Range (ATR) Baseline**

The foundational unit of measurement for spatial tolerance is the Average True Range (ATR). The system must maintain a rolling calculation of the ATR over a standard fourteen-period lookback.5 This metric normalizes distance, allowing the algorithm to define proximity and momentum dynamically across any chart, from a one-minute scalping timeframe to a daily macro timeframe.3

The True Range for a single period is calculated as the greatest absolute value among three measurements:

1. The current high minus the current low.  
2. The absolute value of the current high minus the previous close.  
3. The absolute value of the current low minus the previous close.5

By applying a smoothed moving average (typically the Wilder smoothing method) to this True Range, the system generates a continuous volatility baseline.5 Consequently, all proximity checks, threshold validations, and momentum measurements are calculated as a fractional percentage or a multiple of this prevailing ATR.5 This ensures the algorithm adapts instantly to periods of high volatility or consolidation.3

### **Swing Point Array Generation**

Market structure relies on the continuous detection of structural peaks and troughs, known as swing points. A programmatic definition of a swing point eliminates the visual subjectivity of identifying highs and lows.8 The system must maintain active, dynamically updating arrays of Swing High and Swing Low objects, validated through a strict fractal sequence.9

The consensus programmatic rule for defining a significant swing point requires a five-candle fractal pattern, establishing a "two-candle lookback" and "two-candle confirmation" tolerance.8

* **Swing High:** A Swing High is mathematically validated only when a central candle forms a high that is strictly greater than the highest prices of the two candles immediately preceding it and the two candles immediately following it.8  
* **Swing Low:** A Swing Low requires a central low strictly less than the two preceding and two subsequent lows.8

Until the fifth candle closes, establishing the right-side validation, the swing point remains in a candidate state and cannot be utilized for structural calculations.9 Lowering the candle count to a three-candle pattern (one on each side) generates overly frequent, noisy signals that destabilize the market structure state machine, while a five-candle pattern filters internal noise and establishes robust external structure.9 Each validated Swing Point object must store its timestamp, precise price level, and type (High or Low) in active memory arrays.

## **Market Structure State Machine**

Market structure operates as a continuous, deterministic state machine, shifting between BULLISH, BEARISH, and CONSOLIDATING regimes based on the interaction between current price delivery and the validated swing point arrays.10 To prevent the algorithm from reacting to lower-timeframe noise, the system must distinguish between external structure and internal structure. External structure defines the macro trend, established by the highest highs and lowest lows of the dealing range, while internal structure represents the minor fluctuations within the prevailing external boundaries.10 The algorithm must strictly map the external structure to define the directional bias.10

### **Break of Structure (BOS)**

**Plain Definition:** A Break of Structure (BOS) is an event that confirms the continuation of the prevailing market trend, indicating that institutional forces remain in control of the current direction.11

**What it Looks Like:** In a bullish trend, the price creates a series of higher highs and higher lows. A BOS appears as a strong bullish candle pushing through the peak of the previous swing high and closing above it.13 In a bearish trend, it is a strong bearish candle pushing through the lowest point of the previous swing low.14

**Exact Qualifying Conditions:**

* **Candles Involved:** The event requires a reference external Swing Point (High or Low) and an active breaking candle.12  
* **Body vs. Wick:** The defining mechanical rule for a valid BOS is the strict requirement of a candle body close.10 If the active candle breaches the external swing point with a wick but the body fails to close beyond the level, the system must immediately classify the event as a Liquidity Sweep, NOT a BOS.10  
* **Validity:** The BOS is only valid if it breaks a structural external swing point that initiated a prior pullback. Furthermore, a high-probability BOS requires algorithmic displacement—the breaking candle must exhibit significant momentum, defined programmatically as a candle range exceeding a 1.5x multiplier of the current ATR.12

**Mitigation and Invalidation:** A BOS is an instantaneous event that updates the state machine; it does not possess an active lifecycle or mitigation status. Once a BOS is logged, the system updates the Current\_State (e.g., confirming BULLISH) and resets the external dealing range parameters to the new high and the protected low that caused the break.10

**Weight and Interactions:** A BOS validates trend continuation. Any Order Blocks or Fair Value Gaps created within the price leg that caused the BOS are assigned maximum positive weighting by the evaluation engine, as they are aligned with confirmed institutional momentum.16

### **Change of Character (CHoCH)**

**Plain Definition:** A Change of Character (CHoCH) acts as the primary state transition mechanism, signaling an early potential reversal in institutional order flow and a shift in market sentiment.10 While a BOS confirms the trend, a CHoCH warns of its failure.12

**What it Looks Like:** In an active bullish state characterized by higher highs and higher lows, a bearish CHoCH appears as a sudden downward impulse that breaks below the most recent higher low.17 Visually, it breaks the "stair-step" pattern of the trend.

**Exact Qualifying Conditions:**

* **Candles Involved:** The event evaluates the active breaking candle against the specific Swing Point responsible for the prior trend structure.12  
* **Body vs. Wick:** Similar to the BOS, a valid CHoCH strictly requires a full candle body close beyond the critical level.10 A wick penetration is classified solely as a stop-loss hunt (Liquidity Sweep).10  
* **Validity and Community Disagreement:** The architectural divergence among practitioners regarding this concept revolves around which swing points qualify for a CHoCH. Some traders define a CHoCH as the break of *any* internal swing point. This introduces massive system noise and categorizes engineered traps (Inducements) as trend changes. The strict programmatic rule implemented for this engine dictates that the broken swing point must be the exact external swing that caused the preceding Break of Structure.10 Breaking a random internal swing point does not constitute a valid state transition.10

**Mitigation and Invalidation:** Like the BOS, a CHoCH is an instantaneous event flag. It invalidates the prior market state.

**Weight and Interactions:** A valid CHoCH immediately transitions the Current\_State of the market. Consequently, all active Order Blocks aligned with the previous trend are heavily downgraded or marked for deletion, as the institutional bias has demonstrably shifted.12 The CHoCH carries the highest weight when it occurs immediately after price has swept a major higher-timeframe liquidity pool.10

### **State Transition Matrix**

The continuous interaction of price against the swing point arrays is governed by the following state transition matrix, executed upon the close of every new candle:

| Current State | Evaluation Trigger | Validation Rule | Resulting Action |
| :---- | :---- | :---- | :---- |
| BULLISH | Candle closes \> Highest External Swing High | Body Close Required | Log BOS\_Bullish Event, Maintain BULLISH State |
| BULLISH | Candle closes \< Lowest External Swing Low | Body Close Required | Log CHoCH\_Bearish Event, Transition to BEARISH State |
| BEARISH | Candle closes \< Lowest External Swing Low | Body Close Required | Log BOS\_Bearish Event, Maintain BEARISH State |
| BEARISH | Candle closes \> Highest External Swing High | Body Close Required | Log CHoCH\_Bullish Event, Transition to BULLISH State |
| ANY | Candle wicks beyond Swing, Body closes inside | Wick Penetration Only | Log Liquidity\_Sweep Event, Maintain Current State |

## **Institutional Inefficiencies and Object Lifecycles**

Institutional footprints are mathematically identifiable as severe imbalances in price delivery. When massive capital is deployed, the resulting momentum creates voids in the price action and distinct origin points where accumulation or distribution occurred. The algorithm must construct these inefficiencies as discrete objects with defined properties, strict spatial bounds, and continuous lifecycles, tracking them from creation to invalidation.

### **Displacement and Fair Value Gaps (FVG)**

**Plain Definition:** A Fair Value Gap (FVG) is a zone of price imbalance where institutional buying or selling pressure was so aggressive that the market skipped over a range of prices, leaving unfilled orders behind.18 It acts as a highly magnetic draw on price as the market naturally seeks to rebalance the inefficiency.20

**What it Looks Like:** It is a three-candle sequence where a prominent, long-bodied central candle is flanked by two candles whose wicks fail to overlap, creating a visible "gap" or empty space in the middle of the formation.18

**Exact Qualifying Conditions:**

* **Candles Involved:** A strict three-candle sequence.19  
* **Body vs. Wick:** The gap is defined entirely by the wicks of the first and third candles.19  
* **Validity:** For a bullish FVG, the low of Candle 3 must be strictly greater than the high of Candle 1\. The FVG object is bound between Candle 1 High (Bottom Bound) and Candle 3 Low (Top Bound). For a bearish FVG, the high of Candle 3 must be strictly less than the low of Candle 1\. The object is bound between Candle 1 Low (Top Bound) and Candle 3 High (Bottom Bound).19 The central candle (Candle 2\) must exhibit Displacement, quantified as a total range greater than 1.0x the current ATR.15

**Mitigation and Invalidation:**

* **Active:** The FVG remains in an active state as long as price does not re-enter the defined zone.  
* **Partially Mitigated:** If a subsequent candle wick enters the FVG bounds but does not fill the gap entirely, the object is flagged as partially mitigated, reducing its magnetic weight.10  
* **Fully Mitigated / Invalidated:** If a subsequent candle wick or body completely overlaps the opposite boundary (e.g., trades down to touch Candle 1 High in a Bullish FVG), the gap is filled. The object's state changes to Invalidated, and its programmatic weight drops to zero.10

**Weight and Interactions:** Unmitigated FVGs carry immense weight as primary entry targets when aligned with a structural trend.10 They interact directly with Order Blocks; an Order Block that immediately precedes an FVG is assigned the highest possible probability score.20

### **Order Blocks (OB)**

**Plain Definition:** An Order Block represents the specific price range where institutional entities accumulated or distributed positions immediately prior to a displacement wave.21 It is the footprint of smart money entering the market.21

**What it Looks Like:** It is the last opposing candle before a strong, impulsive trend sequence.21 In a bullish setup, it is the final down-close (bearish) candle before a rally; in a bearish setup, it is the final up-close (bullish) candle before a drop.21

**Exact Qualifying Conditions:**

* **Candles Involved:** The system looks backward from a validated displacement event (a BOS or CHoCH that contains an FVG). The Order Block is the extreme opposite-color candle immediately preceding that displacement.20  
* **Body vs. Wick (The Zone Definition):** The architectural debate regarding whether an Order Block zone is defined by the candle body or the wicks is resolved through conditional logic based on proximity to the subsequent Fair Value Gap.25  
  * *Default Rule:* The high-probability zone of the Order Block is defined purely by the open and close of the candle body, establishing the core institutional volume node while filtering out the extremes of the wicks.25  
  * *Overlap Exception:* If the wick of the origin candle physically overlaps with the boundaries of the subsequent FVG, the algorithm expands the Order Block zone to include the extreme wick, mapping the entire high-to-low range of the candle.25  
* **Validity:** The block must be the catalyst for a structural break, and it must initiate a displacement wave that leaves an FVG.20 An Order Block forming in the middle of a consolidating range without causing a structural break is classified as noise and ignored.20

**Mitigation and Invalidation (The Mean Threshold):**

* **Mitigation:** An Order Block is mitigated when a subsequent candle's wick enters the defined zone. It remains valid for a trade entry upon this first touch.23  
* **The Mean Threshold Rule:** The Mean Threshold is calculated as the exact 50% mathematical midpoint of the defined Order Block zone.25 If a subsequent candle body closes past the Mean Threshold, the Order Block is severely downgraded in probability. Institutional algorithms are expected to defend the first half of the block; a close past the 50% mark indicates defense failure.23  
* **Invalidation:** If a candle body closes completely through the distal boundary of the Order Block (the lowest low for a bullish block, or highest high for a bearish block), the object is instantly destroyed.10

**Weight and Interactions:** Order Blocks are the primary execution triggers in the SMC framework. Their weight is exponentially increased if the Order Block's formation swept a local liquidity pool prior to expanding.20 Upon invalidation, an Order Block interacts with the state machine by transitioning into a Breaker Block.

### **Breaker Blocks and Mitigation Blocks**

When an active Order Block fails to support the price and is invalidated by a structural break, its polarity flips.

**Breaker Blocks:**

* **Definition:** A failed Order Block that resulted in a structural break.27  
* **Conditions:** The critical programmatic prerequisite for a Breaker Block is a prior liquidity sweep.23 A bullish Breaker Block originates as a failed bearish Order Block. Before failing, this bearish block must have swept an external high. When strong downward displacement shatters this block, it becomes a high-probability future resistance zone.23  
* **Weight:** Breaker Blocks carry exceptional weight. They represent trapped institutional volume being liquidated at break-even, naturally propelling the market in the direction of the new trend.27

**Mitigation Blocks:**

* **Definition:** A failed Order Block that did *not* sweep liquidity prior to its failure.23  
* **Conditions:** The mechanical distinction lies solely in the lack of a prior sweep.23 A Mitigation Block forms when price fails to sweep the extreme, creating a lower high or higher low before breaking down through the block.23  
* **Weight:** The system assigns a significantly lower algorithmic weight to Mitigation Blocks. The lack of a prior sweep suggests the structural shift may merely be an internal fluctuation rather than a macro institutional reversal.27

| Block Object | Pre-requisite Action | Invalidation Trigger | New State Polarity | Algorithmic Weight |
| :---- | :---- | :---- | :---- | :---- |
| Order Block | Displacement \+ FVG creation | Body close past distal end | Breaker/Mitigation | High |
| Breaker Block | OB swept external liquidity before failure | Body close past distal end | Destroyed | Highest |
| Mitigation Block | OB failed to sweep liquidity before failure | Body close past distal end | Destroyed | Medium |

## **Liquidity Engineering and Target Variables**

Institutional algorithms require vast amounts of counter-party liquidity to execute massive orders without causing excessive slippage.1 This liquidity is engineered by inducing retail participants into predictable behaviors and subsequently triggering their protective stop losses.29 The programmatic detection of these liquidity pools is critical for the AI engine to define take-profit targets, establish Wait Conditions, and filter out engineered traps.30

### **Equal Highs and Equal Lows (EQH / EQL)**

**Plain Definition:** Equal Highs and Equal Lows act as powerful magnetic targets for price. They represent concentrated pools of retail stop-loss orders residing just beyond obvious horizontal support and resistance levels.10

**What it Looks Like:** Two or more structural swing points forming at virtually the identical price level, creating a flat top or flat bottom.30

**Exact Qualifying Conditions:**

* **Candles Involved:** The system evaluates pairs of validated Swing High or Swing Low objects stored in the active arrays.30  
* **Tolerance Calculation:** Because absolute mathematical equality rarely occurs in fluid markets to the exact tick, the algorithm must employ a dynamic tolerance threshold. The absolute difference between the extreme prices of High\_1 and High\_2 is calculated. If this absolute difference is less than or equal to 5% of the current 14-period ATR (Tolerance \= ATR \* 0.05), the algorithm links the two points and instantiates a Liquidity Pool object.7 This dynamically captures visually equal levels while filtering out structurally distinct swings regardless of the asset's volatility.3  
* **Validity:** The Equal High/Low object remains valid until price penetrates the level by at least one tick, triggering the resting stop losses.31

**Mitigation and Invalidation:** Once a candle wick breaches the price level of the EQH/EQL, the liquidity is considered swept, and the object is deleted from active memory.31

**Weight and Interactions:** These zones are strictly prohibited from being utilized as entry triggers.30 They interact with the system entirely as target variables. If an active trade is initiated, an EQH/EQL object resting in the path of the trend is assigned as a Take-Profit target.30 Furthermore, if an un-swept EQH/EQL rests immediately in front of an Order Block, the Order Block is flagged as a potential trap, as the system anticipates price will drive through the block to sweep the liquidity.10

### **The Inducement Trap (IDM)**

**Plain Definition:** Inducement represents the deliberate engineering of short-term structural signals designed to trap premature market participants before the true institutional move occurs.29 It is the most complex variable to codify deterministically.

**What it Looks Like:** A minor pullback and subsequent bounce that occurs *before* price reaches the true, deep Order Block that initiated the trend.34 Retail traders buy the minor bounce, placing their stops below it. The market then crashes through the bounce, hits the real Order Block, and reverses.34

**Exact Qualifying Conditions:**

* **Programmatic Rule (The First Pullback Logic):** To codify Inducement reliably, the system must utilize a strict "first pullback" state rule.34 The logic sequence activates immediately following a confirmed Break of Structure.35  
  1. The system identifies the new absolute extreme (the highest high of the breakout leg).  
  2. Once the market begins to retrace from this extreme, the algorithm traces the price action backwards toward the origin Order Block.  
  3. The *very first* validated internal Swing Point encountered during this retracement path is mathematically classified and locked as the Inducement (IDM) level.34  
* **Validity:** The Inducement object remains valid until price sweeps it.

**Mitigation and Invalidation:** The Inducement is mitigated the moment a candle wick drops below (or rises above) the defined Swing Point price level, harvesting the engineered liquidity.36

**Weight and Interactions:** The Inducement level acts as a primary boolean gatekeeper for the entire algorithmic trading engine.

* **The "No Inducement, No Trade" Protocol:** If the system detects a Fair Value Gap or an Order Block that resides structurally *between* the new extreme and the Inducement level, it is classified as an engineered trap. The AI agent must apply a strict block on any long or short signals generated from this zone.34  
* The system will only validate Order Blocks that reside structurally *deeper* than the Inducement level, ensuring that the necessary liquidity has been harvested prior to institutional entry.34 Once the IDM is swept, the deepest remaining Order Block is upgraded to a High Probability status.36

## **Spatial and Temporal Constraints**

Institutional algorithms are constrained by spatial value definitions and strict temporal operating windows. The AI evaluation engine must grade setups based on where they occur in the price range, and exactly what time of day they are formed.

### **Premium, Discount, and Optimal Trade Entry (OTE)**

Value is defined mathematically through the subdivision of the active dealing range.

**Qualifying Conditions:** When the market state machine registers a confirmed trend bounded by an external Swing High and an external Swing Low, the algorithm applies a spatial matrix.10 The total vertical distance between the external bounds is calculated, and the exact 50% midpoint is established as the Equilibrium line.10

* In a BULLISH state, the spatial area below the 50% Equilibrium is the **Discount zone**.10  
* In a BEARISH state, the area above the 50% Equilibrium is the **Premium zone**.10

**Optimal Trade Entry (OTE):** Further precision is achieved through a specific algorithmic sub-zone residing between the 62% and 79% Fibonacci retracement levels of the active dealing range.10

**Interactions and Weighting:** The AI applies a strict spatial constraint: high-probability long signals can *only* be validated from Order Blocks residing deep within the Discount zone, and short signals are exclusively generated from Order Blocks high in the Premium zone.10 If a setup forms on the wrong side of equilibrium (e.g., buying in Premium), it is heavily downgraded by the scoring matrix.10 When a validated Order Block perfectly intersects with the OTE coordinates inside the correct hemisphere, the algorithm assigns maximum spatial weighting.10

### **Session Timing and Killzones**

Algorithmic validation must account for time as a primary axis of probability. Institutional order flow is highly concentrated during specific periods of overlapping global liquidity.38 The system restricts high-probability validations to defined temporal windows, known as Killzones, to avoid the low volume and algorithmic chop characteristic of off-hours trading.38

The temporal architecture is hardcoded to Eastern Standard Time (EST) to maintain alignment with the New York institutional close.38 The system maintains an active chronometer and tags all objects with the following session booleans:

1. **Asian Range (20:00 to 00:00 EST):** Characterized by algorithmic consolidation.40 The system suppresses macro trend-following signals during this phase, utilizing the period strictly to map the boundary Swing Highs and Lows that will serve as liquidity pools for later sessions.39  
2. **London Killzone (02:00 to 05:00 EST):** Captures the influx of European institutional volume.40 The highest probability events generated here are manipulation sweeps—rapid movements that trigger the Asian Range liquidity pools before reversing to establish the true daily trend.39 Order Blocks formed in this window carry exceptional weight.42  
3. **New York Killzone (07:00 to 10:00 EST):** Overlaps with the London session and encompasses major US economic data releases.38 The system anticipates extreme volatility and structural displacement, actively validating continuation setups that align with the momentum established in London.38  
4. **London Close Killzone (10:00 to 12:00 EST):** Represents the final injection of volume as European desks close.40 The algorithm expects minor reversals and mean-reverting price action, downgrading new macro setups and prioritizing exit conditions.42

**The Silver Bullet Micro-Sessions:** Within these broad killzones, the algorithm prioritizes highly specific one-hour micro-sessions.43 These strict temporal parameters occur at:

* 03:00 to 04:00 EST (London Open Silver Bullet)  
* 10:00 to 11:00 EST (New York AM Silver Bullet)  
* 14:00 to 15:00 EST (New York PM Silver Bullet).43

Structural breaks and FVGs that materialize precisely within these sixty-minute constraints are subjected to the highest positive multipliers in the evaluation engine, as they represent the absolute peak of algorithmic institutional delivery.43

| Temporal Array | Timeframe (EST) | Primary System Function | Object Weight Modifier |
| :---- | :---- | :---- | :---- |
| Asian Range | 20:00 \- 00:00 | Map Range Boundaries / Suppress Signals | 0.5x (Downgrade) |
| London Killzone | 02:00 \- 05:00 | Identify Liquidity Sweeps / Establish Trend | 1.5x (Upgrade) |
| New York Killzone | 07:00 \- 10:00 | Trend Continuation / Volatility Breakouts | 1.5x (Upgrade) |
| London Close | 10:00 \- 12:00 | Mean Reversion / Exit Processing | 0.8x (Downgrade) |
| Silver Bullet | Specific 1hr windows | Execute precise FVG/OB entries | 2.0x (Max Upgrade) |

## **The Heuristic Scoring Matrix and Conflict Resolution**

The deterministic evaluation of Smart Money Concepts relies on a rigorous scoring matrix. The script processes real-time chart data, instantiates the geometric objects and lifecycles defined above, and generates a JSON payload for the evaluating AI agent. The AI agent processes this payload against a strict conditional hierarchy to output a definitive trade probability score: High, Medium, Low, or Invalid.

### **1\. The Golden Setup (High Probability)**

To classify a payload as High Probability, a strict conjunction of structural, spatial, and temporal booleans must resolve to true. The system requires perfect alignment across all matrices.

**The Golden Setup Conditional Logic:**

* IF Macro\_State \== Micro\_State (Trend Alignment is True)  
* AND Inducement\_Swept \== True (The first internal pullback has been neutralized) 34  
* AND Target\_OB\_Spatial\_Zone \== OTE\_Discount OR OTE\_Premium (Price is in the Optimal Trade Entry zone) 10  
* AND Target\_OB\_Mitigation\_Status \== Unmitigated (Mean Threshold is untested) 25  
* AND Target\_OB\_Origin \== Liquidity\_Sweep (The OB swept local liquidity before displacing) 20  
* AND Active\_Session \== Killzone OR Silver\_Bullet 43  
* THEN Probability\_Score \= HIGH

If this exact combination of flags is present, the AI engine evaluates the setup as highly actionable. The institutional footprint is clear, liquidity has been engineered and harvested, and the timing aligns with algorithmic delivery.36

### **2\. Downgrade Triggers (Medium Probability)**

A mathematically perfect structure can be degraded by contextual anomalies. The AI engine applies negative multipliers to the setup's probability score if specific downgrade triggers are detected.

**Downgrade Logic:**

* **Spatial Violation:** IF Target\_OB\_Spatial\_Zone\!= OTE (e.g., the OB is in the Discount zone, but only at the 40% retracement level rather than the 62-79% OTE), THEN Downgrade to MEDIUM.10  
* **Temporal Violation:** IF Active\_Session \== Asian\_Range OR Dead\_Zone, THEN Downgrade to MEDIUM.42 Time kills volume; setups formed outside of peak liquidity windows lack the institutional backing required for sustained follow-through.42  
* **Mitigation Degradation:** IF Target\_OB\_Mitigation\_Status \== Partially\_Mitigated (Price previously wicked the OB but remained above the Mean Threshold), THEN Downgrade to MEDIUM.10 Institutional orders may have already been heavily consumed, reducing the repulsive force of the zone.10

### **3\. Invalidation and Trap Criteria (Low Probability / Do Not Trade)**

Specific configurations immediately flag a setup as a structural trap, rendering it completely invalid for execution. The AI agent must recognize these mathematical signatures to prevent the system from becoming exit liquidity.

**Invalidation Logic:**

* **The Inducement Trap:** IF Target\_OB \> Inducement\_Level (for longs) OR Target\_OB \< Inducement\_Level (for shorts), THEN Probability\_Score \= INVALID.34 The system assumes smart money intends to drive price through this OB to trigger the resting liquidity of the Inducement level.37  
* **Liquidity Magnet Trap:** IF Distance(Target\_OB, EQH\_EQL\_Pool) \< (ATR \* 0.1) AND Pool\_Swept \== False, THEN Probability\_Score \= INVALID.10 If un-swept Equal Lows rest immediately in front of a bullish Order Block, the system aborts. The market is overwhelmingly likely to crash through the Order Block to trigger the Equal Lows.10  
* **Mean Threshold Failure:** IF Prior\_Candle\_Close \> Mean\_Threshold (50% midpoint of the OB), THEN Probability\_Score \= INVALID.23 The institutional defense of the level has failed.

### **4\. Conflict Resolution (The Tie-Breakers)**

When analyzing multi-timeframe fractal environments, contradictory signals are inevitable. The AI evaluation agent applies a strict set of tie-breaking rules to navigate structural collisions deterministically.

**Hierarchy 1: State Overrides All (Macro over Micro)** Internal structure on a higher timeframe invariably appears as external structure on a lower timeframe. Therefore, the macro state machine always overrides the micro state machine. If the 15-minute execution chart registers a bullish CHoCH, but the 4-hour macro chart remains in a BEARISH state, the system subordinates the lower-timeframe signal.37 The AI evaluates the 15-minute bullish CHoCH not as a true trend reversal, but as the initiation of an internal pullback designed to drive price upward into a 4-hour Premium Order Block.37 Long signals are blocked, and the system prepares for short executions at the macro level.

**Hierarchy 2: Sweeps Precede Structure** When structural signals conflict directly with liquidity metrics, the algorithm prioritizes liquidity mechanics.10 If the system detects a valid bullish BOS, confirming an upward trend, but simultaneously identifies a massive, unmitigated pool of Equal Lows resting below the current price action, a synthesis conflict occurs. The resolution engine dictates that "sweeps precede structure." The AI suspends trend-following long executions despite the bullish state, anticipating an institutional manipulation sequence to sweep the Equal Lows before continuing.10

**Hierarchy 3: Array Overlaps Compound Probability** Conflicts frequently arise when multiple institutional arrays occupy the same spatial zone. For instance, a displacement wave may generate a Breaker Block that perfectly aligns with a newly formed Fair Value Gap. When arrays overlap, their algorithmic weighting is combined rather than split.20 The confluence of a Breaker Block, an FVG, and Optimal Trade Entry coordinates creates an interlocking zone of high institutional density, resulting in the highest possible validation score for the AI evaluating agent.20

By standardizing these Smart Money Concepts into rigid mathematical tolerances, object lifecycles, and deterministic boolean logic, the subjective art of institutional chart reading is successfully codified. The resulting heuristic matrix provides the absolute clarity required for an AI model to ingest chart data, process structural hierarchies, and output highly accurate, natural language market analysis.

#### **Works cited**

1. Smart Money Concept (SMC) Forex Strategy Explained \- ePlanet Brokers, accessed April 12, 2026, [https://eplanetbrokers.com/training/smart-money-concept](https://eplanetbrokers.com/training/smart-money-concept)  
2. What Is the Smart Money Concept and How Does the ICT Trading Strategy Work? \- ATAS, accessed April 12, 2026, [https://atas.net/blog/what-is-the-smart-money-concept-and-how-does-the-ict-trading-strategy-work/](https://atas.net/blog/what-is-the-smart-money-concept-and-how-does-the-ict-trading-strategy-work/)  
3. ATR Trading Strategies Guide \- TradersPost, accessed April 12, 2026, [https://blog.traderspost.io/article/atr-trading-strategies-guide](https://blog.traderspost.io/article/atr-trading-strategies-guide)  
4. Why most retail traders misuse ATR (and how to actually use it) | by Luka \- Medium, accessed April 12, 2026, [https://lukasavi-34031.medium.com/why-most-retail-traders-misuse-atr-and-how-to-actually-use-it-4657d707f01b](https://lukasavi-34031.medium.com/why-most-retail-traders-misuse-atr-and-how-to-actually-use-it-4657d707f01b)  
5. Average True Range (ATR) and Average True Range Percent (ATRP) | ChartSchool | StockCharts.com, accessed April 12, 2026, [https://chartschool.stockcharts.com/table-of-contents/technical-indicators-and-overlays/technical-indicators/average-true-range-atr-and-average-true-range-percent-atrp](https://chartschool.stockcharts.com/table-of-contents/technical-indicators-and-overlays/technical-indicators/average-true-range-atr-and-average-true-range-percent-atrp)  
6. ATR: Technical Indicator \- FTMO Academy, accessed April 12, 2026, [https://academy.ftmo.com/lesson/atr-technical-indicator/](https://academy.ftmo.com/lesson/atr-technical-indicator/)  
7. Average True Range (ATR) Indicator Guide: Master Volatility Trading \- VT Markets, accessed April 12, 2026, [https://www.vtmarkets.com/discover/average-true-range-atr-indicator-guide-master-volatility-trading/](https://www.vtmarkets.com/discover/average-true-range-atr-indicator-guide-master-volatility-trading/)  
8. Smart Money Trading—How to Identify Swing Highs and Lows \- Altrady, accessed April 12, 2026, [https://www.altrady.com/crypto-trading/smart-money-concept/how-to-identify-swing-highs-and-lows](https://www.altrady.com/crypto-trading/smart-money-concept/how-to-identify-swing-highs-and-lows)  
9. Williams Fractal: Spotting Reversal in Trends \- LuxAlgo, accessed April 12, 2026, [https://www.luxalgo.com/blog/williams-fractal-spotting-reversal-in-trends/](https://www.luxalgo.com/blog/williams-fractal-spotting-reversal-in-trends/)  
10. SMC Market Structure: BoS And CHoCH Made Simple \- Daily Price Action, accessed April 12, 2026, [https://dailypriceaction.com/blog/smc-market-structure/](https://dailypriceaction.com/blog/smc-market-structure/)  
11. Day 3: SMC & ICT Market Structure Explained — BOS, CHoCH ..., accessed April 12, 2026, [https://tradingstrategyguides.com/day-3-smc-ict-market-structure-explained-bos-choch-swing-points-2026/](https://tradingstrategyguides.com/day-3-smc-ict-market-structure-explained-bos-choch-swing-points-2026/)  
12. Day 7: BOS Vs CHoCH — How To Tell If The Trend Is Continuing Or Breaking Down, accessed April 12, 2026, [https://tradingstrategyguides.com/day-7-bos-vs-choch-how-to-tell-if-the-trend-is-continuing-or-breaking-down/](https://tradingstrategyguides.com/day-7-bos-vs-choch-how-to-tell-if-the-trend-is-continuing-or-breaking-down/)  
13. Master Market Trends: Understanding BOS and CHOCH in Trading \- Aron Groups, accessed April 12, 2026, [https://arongroups.co/technical-analyze/bos-and-choch/](https://arongroups.co/technical-analyze/bos-and-choch/)  
14. What Is BOS in Trading? Break of Structure Explained (SMC Guide) \- Zaye Capital Markets, accessed April 12, 2026, [https://zayecapitalmarkets.com/what-is-bos-break-of-structure-in-trading/](https://zayecapitalmarkets.com/what-is-bos-break-of-structure-in-trading/)  
15. Displacement Explained (Institutional Signature) | How Smart Money Moves Price, accessed April 12, 2026, [https://www.youtube.com/watch?v=j08cd9EkgYU](https://www.youtube.com/watch?v=j08cd9EkgYU)  
16. Full breakdown of my SMC level 1 strategy as a full time trader for 8 years now \- Reddit, accessed April 12, 2026, [https://www.reddit.com/r/Trading/comments/1qwv5g3/full\_breakdown\_of\_my\_smc\_level\_1\_strategy\_as\_a/](https://www.reddit.com/r/Trading/comments/1qwv5g3/full_breakdown_of_my_smc_level_1_strategy_as_a/)  
17. CHoCH in SMC Trading Explained: Spot Trend Reversals Early \- Zaye Capital Markets, accessed April 12, 2026, [https://zayecapitalmarkets.com/what-is-choch-change-of-character-in-trading/](https://zayecapitalmarkets.com/what-is-choch-change-of-character-in-trading/)  
18. Market Momentum Explained: Displacement, Manipulation & Imbalances in SMC, accessed April 12, 2026, [https://acy.com/en/market-news/education/market-momentum-explained-displacement-manipulation-imbalances-smc-j-o-04152025-113853/](https://acy.com/en/market-news/education/market-momentum-explained-displacement-manipulation-imbalances-smc-j-o-04152025-113853/)  
19. GitHub \- joshyattridge/smart-money-concepts: Discover our Python package designed for algorithmic trading. It brings ICT's smart money concepts to Python, offering a range of indicators for your algorithmic trading strategies., accessed April 12, 2026, [https://github.com/joshyattridge/smart-money-concepts](https://github.com/joshyattridge/smart-money-concepts)  
20. Anatomy of a Valid Order Block in Smart Money Concepts \- ACY Securities, accessed April 12, 2026, [https://acy.com/en/market-news/education/anatomy-of-a-valid-order-block-j-o-20251110-092434/](https://acy.com/en/market-news/education/anatomy-of-a-valid-order-block-j-o-20251110-092434/)  
21. Smart Money Concepts Terminology: Deep Dive Guide to Profits \- Trade The Pool, accessed April 12, 2026, [https://tradethepool.com/technical-skill/smart-money-concepts-terminology/](https://tradethepool.com/technical-skill/smart-money-concepts-terminology/)  
22. Day 5: Order Blocks Explained — ICT Vs SMC Guide To Bullish & Bearish OBs, accessed April 12, 2026, [https://tradingstrategyguides.com/day-5-order-blocks-explained-ict-vs-smc-guide-to-bullish-bearish-obs/](https://tradingstrategyguides.com/day-5-order-blocks-explained-ict-vs-smc-guide-to-bullish-bearish-obs/)  
23. Master the Mitigation Block ICT and Learn to Trade it, accessed April 12, 2026, [https://innercircletrader.net/tutorials/ict-mitigation-block-explained/](https://innercircletrader.net/tutorials/ict-mitigation-block-explained/)  
24. What Are ICT Order Blocks and Breaker Blocks in Trading? \- ATAS, accessed April 12, 2026, [https://atas.net/blog/what-are-ict-order-blocks-and-breaker-blocks-in-trading/](https://atas.net/blog/what-are-ict-order-blocks-and-breaker-blocks-in-trading/)  
25. Mean threshold of orderblocks : r/InnerCircleTraders \- Reddit, accessed April 12, 2026, [https://www.reddit.com/r/InnerCircleTraders/comments/1b5a3o9/mean\_threshold\_of\_orderblocks/](https://www.reddit.com/r/InnerCircleTraders/comments/1b5a3o9/mean_threshold_of_orderblocks/)  
26. Order Block Explained \- Alchemy Markets, accessed April 12, 2026, [https://alchemymarkets.com/education/strategies/order-block/](https://alchemymarkets.com/education/strategies/order-block/)  
27. Order Blocks, Breaker Blocks, and Mitigation Blocks \- The ICT Trader, accessed April 12, 2026, [https://theicttrader.com/2024/03/24/order-blocks-breaker-blocks-and-mitigation-blocks/](https://theicttrader.com/2024/03/24/order-blocks-breaker-blocks-and-mitigation-blocks/)  
28. Smart Money Concepts Made Simple: The Definitive SMC Guide \- Daily Price Action, accessed April 12, 2026, [https://dailypriceaction.com/blog/smart-money-concepts/](https://dailypriceaction.com/blog/smart-money-concepts/)  
29. Inducement in Trading: Definition, Types and Identification \- XS.com, accessed April 12, 2026, [https://www.xs.com/en/blog/inducement-in-trading/](https://www.xs.com/en/blog/inducement-in-trading/)  
30. Equal Lows (EQLs) Explained \- Flux Charts, accessed April 12, 2026, [https://www.fluxcharts.com/articles/equal-lows-eqls-explained](https://www.fluxcharts.com/articles/equal-lows-eqls-explained)  
31. What Is Equal Highs (EQHs) Trading and How it Works \- XS.com, accessed April 12, 2026, [https://www.xs.com/en/blog/equal-highs-eqh/](https://www.xs.com/en/blog/equal-highs-eqh/)  
32. Equal Highs & Lows and Old Highs & Lows Explained \- YouTube, accessed April 12, 2026, [https://www.youtube.com/watch?v=kmS9yLiWPYg](https://www.youtube.com/watch?v=kmS9yLiWPYg)  
33. What Is Inducement in SMC Trading? Complete Guide to Smart Money Traps, accessed April 12, 2026, [https://zayecapitalmarkets.com/what-is-inducement-in-smc-trading/](https://zayecapitalmarkets.com/what-is-inducement-in-smc-trading/)  
34. Inducement Trading \[PDF\] | HowToTrade, accessed April 12, 2026, [https://howtotrade.com/wp-content/uploads/2024/08/Inducement-Trading.pdf](https://howtotrade.com/wp-content/uploads/2024/08/Inducement-Trading.pdf)  
35. What is Inducement Trading \- Inducement in Forex Explained Step by Step \- ICT Trading, accessed April 12, 2026, [https://innercircletrader.net/tutorials/what-is-inducement-in-forex/](https://innercircletrader.net/tutorials/what-is-inducement-in-forex/)  
36. Smart Money Concept Explained: How Institutions Really Move the Market, accessed April 12, 2026, [https://zayecapitalmarkets.com/smart-money-concept-in-forex/](https://zayecapitalmarkets.com/smart-money-concept-in-forex/)  
37. Inducement in SMC Explained (This Makes It Easy) \- YouTube, accessed April 12, 2026, [https://www.youtube.com/watch?v=1m-jbv9BGoY](https://www.youtube.com/watch?v=1m-jbv9BGoY)  
38. Forex Trading Sessions in EST: ICT Trading Guide \- Defcofx, accessed April 12, 2026, [https://www.defcofx.com/forex-trading-sessions-in-est-ict-trading/](https://www.defcofx.com/forex-trading-sessions-in-est-ict-trading/)  
39. ICT London Killzone Time & Strategy for Precision Entries \- Aron Groups, accessed April 12, 2026, [https://arongroups.co/forex-articles/ict-london-killzone-time/](https://arongroups.co/forex-articles/ict-london-killzone-time/)  
40. Master All 4 ICT Kill Zones Times – Ultimate Guide for 2025, accessed April 12, 2026, [https://innercircletrader.net/tutorials/master-ict-kill-zones/](https://innercircletrader.net/tutorials/master-ict-kill-zones/)  
41. ict killzones confuse me asf : r/InnerCircleTraders \- Reddit, accessed April 12, 2026, [https://www.reddit.com/r/InnerCircleTraders/comments/1mpg868/ict\_killzones\_confuse\_me\_asf/](https://www.reddit.com/r/InnerCircleTraders/comments/1mpg868/ict_killzones_confuse_me_asf/)  
42. Trading ICT Kill Zones in Forex: Complete Guide for 2025 \- HowToTrade, accessed April 12, 2026, [https://howtotrade.com/blog/ict-kill-zones/](https://howtotrade.com/blog/ict-kill-zones/)  
43. ICT Silver Bullet Times to Trade \- Ultima Markets, accessed April 12, 2026, [https://www.ultimamarkets.com/academy/ict-silver-bullet-times-to-trade/](https://www.ultimamarkets.com/academy/ict-silver-bullet-times-to-trade/)  
44. Master ICT Silver Bullet Strategy – 2025 Guide \- ICT Trading, accessed April 12, 2026, [https://innercircletrader.net/tutorials/ict-silver-bullet-strategy/](https://innercircletrader.net/tutorials/ict-silver-bullet-strategy/)  
45. ICT Silver Bullet Evolution 2025 \- YouTube, accessed April 12, 2026, [https://www.youtube.com/watch?v=4ByfwxyqJQU](https://www.youtube.com/watch?v=4ByfwxyqJQU)  
46. The Power of Multi-Timeframe Analysis in Smart Money Concepts (SMC) \- ACY Securities, accessed April 12, 2026, [https://acy.com/en/market-news/education/power-of-multi-timeframe-analysis-in-smart-money-concepts-j-o-134004/](https://acy.com/en/market-news/education/power-of-multi-timeframe-analysis-in-smart-money-concepts-j-o-134004/)