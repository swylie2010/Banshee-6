# Banshee 6 — Operational Guide

**Audience:** The owner/builder of this system and any AI agent assisting them.
**Purpose:** Plain-English explanation of every concept this system implements, how to read a live chart, and how to make trading decisions from what you see. This is not code documentation — the code has that. This is the decision manual.

**Update rule:** Every time a new feature is added or a threshold is changed, update the relevant section here before closing the session. Stale documentation is worse than none.

---

## What Banshee 6 Is

A unified trading analysis platform built on Smart Money Concepts (SMC) — the theory that institutional traders (banks, hedge funds, "smart money") leave detectable footprints in price action, and that retail traders consistently lose because they trade the obvious levels institutions use as traps. Banshee's job is to identify those traps and position on the institutional side instead.

The system has several engines working together:

| Engine | File | What it does |
|---|---|---|
| SMC Engine | `smc_engine.py` | Swing detection, market structure, OBs, FVGs, liquidity pools |
| Micro Engine | `micro_engine.py` | Short-term momentum indicators (RSI, MACD, ADX, etc.) |
| Macro Engine | `macro_engine.py` | Macro regime (VIX, DXY, yield curve, risk-on/off) |
| Sector Rotation | `sector_rotation_engine.py` | Relative strength across 10 sectors; money-flow direction |
| Geometric Harmonic | `geometric_harmonic.py` | Fibonacci arc circles anchored at ATH/ATL; hot-zone clustering |
| XABCD Scanner | `xabcd_scanner.py` | Gartley, Bat, Butterfly, Crab and 4 other harmonic patterns |
| Options Engine | `options_engine.py` | Cash-secured put candidate scoring; spread grader; IV rank estimate |
| Wheel Engine | `wheel_engine.py` | Event-sourced FSM for the options wheel strategy |
| Spread Sim Engine | `spread_sim_engine.py` | Bull put spread simulation (event-sourced, mirrors wheel engine) |
| Gridbot Engine | `gridbot_engine.py` | Grid-trading regime check, topology, capital plan, risk guardrails |
| Portfolio Engine | `portfolio_engine.py` | Grade, benchmark, momentum and risk scoring for a holdings book |
| Ledger Engine | `ledger_engine.py` | Avg-cost accounting, realized P&L, evolution one-liner |
| Predator Engine | `predator_engine.py` | Daily news intake, event classification, AI briefing |
| Banshee AI | `banshee_ai.py` | Synthesizes all engines into a plain-English AI narrative |
| React UI | `ui/` | Browser-based dashboard served at `http://localhost:8765/ui/` |
| MCP Server | `mcp_server.py` | Exposes 22 tools so Claude Code can query Banshee directly |

---

## SMC Concepts — What Each One Is and Why It Matters

### ATR (Average True Range)
The system's universal ruler. Every distance, tolerance, and threshold is expressed as a multiple of ATR, not a fixed price. This means the same logic works on BTC at $80,000 and NVDA at $120 without manual retuning. Period: 14 candles, Wilder smoothing.

**Constant:** `ATR_PERIOD = 14`

---

### Swing Points
A 5-candle fractal pattern: a swing HIGH is a candle whose high is strictly greater than the 2 candles on each side. A swing LOW is the mirror image. These are the peaks and troughs institutions use as reference points for everything downstream.

**Why 2 candles each side:** 1 candle creates too much noise. 2 is the spec's balance between sensitivity and signal quality.

**Constant:** `SWING_FRACTAL_CANDLES = 2`

---

### BOS (Break of Structure)
The breaking candle's body closes beyond a prior swing point AND the candle's full range is ≥ 1.5× ATR. The displacement requirement filters out slow drifts — only genuine institutional delivery qualifies.

- **BOS BULL** (green dashed line) — broke above last swing high. Uptrend confirmed.
- **BOS BEAR** (red dashed line) — broke below last swing low. Downtrend confirmed.

**Constant:** `BOS_DISPLACEMENT_ATR_MULT = 1.5`

---

### CHoCH (Change of Character)
The body closes beyond the *protected* level (the last swing in the opposite direction). No displacement required — the break alone signals a potential trend flip.

- **CHoCH BULL** (green dotted line) — first sign structure is turning bullish. Watch for follow-through BOS to confirm.
- **CHoCH BEAR** (red dotted line) — first sign structure is turning bearish.

**Reading tip:** CHoCH is a warning, not a signal. BOS after CHoCH is confirmation.

---

### FVG (Fair Value Gap)
Three consecutive candles where the center candle moves so fast it leaves a gap between candle 1's high and candle 3's low (bullish) or candle 1's low and candle 3's high (bearish). Center candle must be ≥ 1.0× ATR.

FVGs are imbalances — price moved too fast for fair two-sided trading to occur. Price frequently returns to rebalance these gaps before continuing.

- **Green FVG box (FVG ▲)** — bullish gap, acts as support on pullback.
- **Red FVG box (FVG ▼)** — bearish gap, acts as resistance on bounce.
- **◑ symbol** — FVG is partially filled (price entered but didn't fully close the gap).

**Constant:** `FVG_DISPLACEMENT_ATR_MULT = 1.0`

---

### Premium / Discount Zones (P/D)
The current dealing range is defined by the last swing high and swing low in the state machine's reference. The midpoint (50%) is equilibrium (EQ, gray dashed line).

- **Discount zone (green background)** — price below EQ. Where smart money looks to buy. Long entries preferred here.
- **Premium zone (red/pink background)** — price above EQ. Where smart money sells. Avoid chasing longs.
- **OTE band (amber band)** — 61.8%–79% retracement. The Optimal Trade Entry zone. Deep enough to be a real pullback, not so deep it breaks structure. Best entries cluster here.

**Constants:** `OTE_FIB_LOW = 0.62`, `OTE_FIB_HIGH = 0.79`

---

### Order Blocks (OB)
The last opposite-color candle before a displacement wave that also contains an FVG in its leg. This is the candle where institutions placed their entry orders before the big move. Price returning to this zone is price returning to the institutional footprint.

**Validity rule:** The displacement event (BOS or CHoCH) must have an FVG within 5 candles. No FVG = no institutional displacement = no valid OB.

**Zone definition:**
- Bullish OB: bearish candle (close < open), zone = open to close. If the OB wick overlaps the FVG, expand to full high-to-low.
- Bearish OB: bullish candle (close > open), zone = close to open. Same wick exception.

**Status lifecycle:**
| Status | Meaning |
|---|---|
| `active` | Price has not entered the zone |
| `touched` | A wick entered the zone — first touch, still valid |
| `degraded` | A candle body closed past the 50% mean threshold — institutions partially failed to defend |
| `sapped` | A wick swept completely through the distal boundary — zone is hollow, skip it |
| `invalidated` | A candle body closed through the distal boundary — OB destroyed, skip it |

**Visual encoding on chart:**
- Blue box (OB ▲) = bullish OB
- Red box (OB ▼) = bearish OB
- ◑ = touched status
- ⚠ = degraded status

---

### EQH / EQL (Equal Highs / Equal Lows)
Two swing points at nearly identical price levels (within 5% of ATR). Retail traders see these as double-top resistance (EQH) or double-bottom support (EQL) and cluster stop-losses just beyond them. Institutions deliberately drive price through these levels to harvest that liquidity before reversing.

EQH/EQL are **not entry signals** — they are trap detectors and target variables.

- **Red dashed line (EQH)** — stop-losses sitting above. Smart money spikes price through to collect them, then reverses.
- **Green dashed line (EQL)** — stop-losses sitting below. Smart money drops through to collect them, then reverses.
- Once swept: marked as consumed. An EQL/EQH that has been swept is no longer a live trap.

**Constant:** `EQH_EQL_ATR_TOLERANCE = 0.05`

---

### Inducement (Phase 4 Concept)
An EQH or EQL that sits in the gap between current price and an Order Block. This is the retail trap smart money must sweep on the way to the OB.

**The SMC golden rule:** "If an Order Block doesn't have inducement in front of it, the Order Block becomes the inducement." An OB with no EQH/EQL in front is itself likely a trap — retail traders will place orders there and get swept.

**Two fields are set on every OB:**

| Field | Value | Meaning |
|---|---|---|
| `has_pending_inducement` | True | Unswept EQH/EQL sits between price and this OB. Trap is set. Smart money has a reason to drive price here. **Watch, don't enter yet.** |
| `has_pending_inducement` | False | No unswept trap in front — either it was swept, or there never was one. |
| `inducement_swept` | True | A pool WAS in the inducement zone and has since been swept. The trap has fired. **This OB is now actionable.** |
| `inducement_swept` | False | No swept pool in the zone. |

**Visual encoding:**
- **Amber border + ⌛** — `has_pending_inducement = True`. Watching state.
- **Green border + ⚡** — `inducement_swept = True`. Actionable state.
- **Normal blue/red border** — neither field set. Lower conviction; the OB may be the trap.

**Geometry:**
- Bullish OB (below price): looks for EQL where `ob_zone_top < eql_level < current_price`
- Bearish OB (above price): looks for EQH where `current_price < eqh_level < ob_zone_bottom`

**The hard gate (`INDUCEMENT_HARD_GATE`):**
- `False` (current setting) — all OBs shown; amber/green tags are informational only.
- `True` — only `inducement_swept = True` OBs appear as actionable. OBs with pending inducement are suppressed (not ready). OBs with no inducement are suppressed (may be the trap).

**Only flip to True after visual verification** that the amber/green tags are correctly tagging setups on the chart.

---

### Session Weights
ICT (Inner Circle Trader) theory holds that different trading sessions have different levels of institutional participation. OBs that form or are approached during high-participation windows carry more weight.

| Session | Hours (EST) | Weight | Constant |
|---|---|---|---|
| Silver Bullet | 03–04, 10–11, 14–15 | 2.0× | `SILVER_BULLET_WEIGHT` |
| London Killzone | 02–05 | 1.5× | `LONDON_KILLZONE_WEIGHT` |
| NY Killzone | 07–10 | 1.5× | `NY_KILLZONE_WEIGHT` |
| London Close | 10–12 | 0.8× | `LONDON_CLOSE_WEIGHT` |
| Asian Range | 20–00 | 0.5× | `ASIAN_RANGE_WEIGHT` |
| All other hours | — | 1.0× | (default) |

**Priority on overlap:** Silver Bullet wins. So 10:00 EST is Silver Bullet (2.0×), not London Close (0.8×).

**Two outputs from `run()`:**
- `ob["session_weight"]` — weight at the OB's formation candle. An OB formed during Silver Bullet was created during peak institutional participation.
- `result["current_session_weight"]` — what session you're in right now (last candle). Relevant for entry timing.

---

## How to Read a Banshee Chart — Step by Step

### Step 1: Structure State
Open the SMC tab for your asset and look at the top of the chart panel: **BULLISH / BEARISH / UNDEFINED**. This is the state machine's current read based on the sequence of swing highs and lows. Start here — everything else is filtered through this lens.

### Step 2: HTF Context
The HTF selector runs the same SMC engine on a higher timeframe (e.g., 1D while you're on 4H). Check it for alignment. A bullish 4H setup inside a bearish 1D structure is a counter-trend trade — lower confidence.

### Step 3: Are You in Premium or Discount?
- Looking for a long? You want price in the **discount zone (green background)** or inside the **OTE band (amber band)**.
- Looking for a short? You want price in the **premium zone (red background)**.
- If price is near EQ (gray dashed), it can go either way — wait for a clearer read.

### Step 4: Find the Qualifying OB
Look for active or touched Order Blocks in your target zone. Prioritize:
1. **Green border (⚡)** — inducement has fired. Highest confidence.
2. **Amber border (⌛)** — trap is set but not fired. Put this on your watch list; don't enter yet.
3. **Normal border** — lower conviction. The OB may itself be a trap.

Avoid degraded OBs unless there's strong confluence from other factors.

### Step 5: Check Inducement Status
If you're looking at an amber OB: find the EQL or EQH that's tagging it. That level is the line in the sand — when price sweeps through it (and the pool becomes swept), the border will flip to green. That sweep is your trigger to prepare for entry.

### Step 6: Check Session
Is the current time in a Silver Bullet or killzone window? `current_session_weight` from the engine tells you this numerically. Entries taken during Silver Bullet windows have historically higher institutional delivery probability. Entries during the Asian range (0.5×) are lower conviction.

### Step 7: Check FVGs
Is there a nearby FVG in the same direction as your OB? FVG + OB at the same level is a confluence zone — both the imbalance and the institutional footprint are in agreement.

### Step 8: The AI Narrative
The Banshee AI tab synthesizes all of the above into a plain-English read. If you're not sure what you're seeing on the chart, read the AI output first — it describes the same information in prose.

---

## What Good vs. Bad Setups Look Like

### High-confidence long setup:
- Structure state: BULLISH
- Price pulled back into discount or OTE zone
- Bullish OB with **green border (⚡)** — inducement swept
- OB status: active or touched (not degraded)
- Nearby bullish FVG at same level
- Current time in Silver Bullet or NY Killzone
- HTF structure also bullish

### Watch-list (not yet ready):
- Everything above but OB has **amber border (⌛)**
- Wait for the EQL in front to be swept. That sweep is the entry trigger.

### Skip:
- OB is degraded or sapped
- OB has no inducement tags at all (normal border) — it may be the trap
- Price in premium zone for a long
- Structure state UNDEFINED
- HTF and LTF in conflict

---

## Known Limitations and Pending Work

### INDUCEMENT_HARD_GATE is OFF
`smc_engine.py:66 — INDUCEMENT_HARD_GATE = False`

The amber/green tags are live and informational. The gate has not been activated because visual verification is still in progress. Once the tagging has been confirmed correct across several assets and timeframes, flip to `True`. This will filter the active OB list to only `inducement_swept = True` OBs.

### Session weight is tagged but not scored
Each OB now has a `session_weight` field, and `current_session_weight` is available from `run()`. These are not yet factored into the Banshee AI confidence score or displayed numerically on the Structure Map. This is a future wiring task.

### No unified decision score
The system currently surfaces all the inputs (structure, OB status, inducement, session, FVGs, macro) but does not combine them into a single numeric entry confidence score. The AI narrative handles synthesis in prose, but a quantitative score would allow backtesting of the full decision logic. This is a planned future track.

---

## Calibration Guide

Banshee is a complex engine. Calibration is how you verify it's computing correctly and tune it when something drifts. Think of it like checking the timing on a car engine — the engine can run wrong without obviously breaking down.

There are two types of calibration: **indicator calibration** (are Banshee's computed values matching ground truth?) and **HTF level calibration** (are the key reference levels up to date?).

---

### Indicator Calibration

**When to run:** If signals feel "off" — Banshee says oversold but the chart looks strong, or vice versa. Also run after any change to `micro_engine.py` or a data source switch.

**How to run:**

Use the calibration script (the fastest path):

```bash
cd ~/AntiEverything/Banshee_6
python calibrate.py NVDA long_term          # show current values; auto-compare if baseline exists
python calibrate.py BTC/USD swing           # same for BTC swing
python calibrate.py NVDA long_term --save   # save current values as new baseline
```

Output is a comparison table — each indicator shows Banshee value, baseline value, delta, and OK/WARN flag. If no baseline exists it prints current values and prompts you to `--save`.

To use TV ground truth as the baseline: run `--save` once to create the file, then open `tv_extract/calibration/NVDA_long_term_baseline.json` and replace the `values` block with values from `data_get_study_values` (TV MCP). Future runs will compare against those real numbers.

If you need to inspect individual values without the script:

```bash
python -c "
import sys; sys.path.insert(0, '.')
import micro_engine
tfs = micro_engine.load_and_prepare('NVDA', 'long_term')
df  = tfs.get('1wk')
last = df.iloc[-1]
for k in ['close','rsi','stoch_k','stoch_d','macd','macd_signal','macd_hist','vwap']:
    print(f'{k:15s}: {last[k]:.4f}')
"
```

Alternatively, use the MCP agent output — `raw_indicators` block is now included in every `get_asset_radar` agent-mode response.

**How to interpret results (first baseline: 2026-04-25, NVDA 1W):**

| Indicator | Banshee | TV | Delta | Verdict |
|---|---|---|---|---|
| MACD | 4.577 | 4.57 | ~0 | ✅ Perfect |
| MACD Signal | 3.122 | 3.12 | ~0 | ✅ Perfect |
| Stoch K | 92.98 | 93.63 | -0.65 | ✅ Fine |
| VWAP | 184.10 | 183.83 | +0.27 | ✅ Fine |
| RSI | 62.33 | 65.11 | -2.78 | ⚠️ Small drift |
| Stoch D | 61.91 | 69.60 | -7.69 | ⚠️ Amplified drift |

**Acceptable drift:** ±3 points on RSI, ±1 on MACD, ±10 on Stoch D (D is doubly-smoothed, amplifies upstream drift). Same signal bucket = no action needed.

**Drift diagnosis:** MACD perfect = algorithm and data are correct. RSI drift comes from minor yfinance vs TV feed disagreements on a few historical bars. Stoch D drift = RSI drift × two smoothing layers. Root cause is data source, not bugs.

**When drift is a problem:** If RSI drifts >5 points and would change the signal bucket (e.g., Banshee says "above midline" but TV shows "overbought"), investigate:
1. Check yfinance data for gaps or split errors: `df.tail(20)` and compare close prices to TV
2. Check parameter constants at top of `micro_engine.py`: `RSI_PERIOD`, `STOCH_PERIOD/K/D`
3. MACD: `e12 = ewm(span=12)`, `e26 = ewm(span=26)`, `signal = ewm(span=9)` — must match TV settings

---

### HTF Level Calibration

**What it is:** Named institutional reference levels that Banshee can't compute from raw OHLCV. Stored in `htf_levels.json`. Examples: yearly opens, Market Maker PD/PW levels, Elliott Wave targets.

**File location:** `~/AntiEverything/Banshee_6/htf_levels.json`

**In the UI:** The Structure Map draws these levels as horizontal lines (gold = opens, purple = Market Maker, teal = VWAP, gray = Elliott Wave). Any OB or FVG whose zone falls within 1 ATR of a named level gets a **★** tag on its chart label. The AI narrative (Rule 8) will also call out these confluences explicitly. No action needed — it's automatic once the file is populated.

**When to update:** Whenever TradingView is available and you're about to make a trading decision on an asset. Takes ~60 seconds.

**How to update:**

1. Set TV chart to the asset + weekly timeframe, all indicators visible
2. Run via MCP: `data_get_pine_labels` + `data_get_pine_lines` + `data_get_study_values`
3. Update the relevant asset block in `htf_levels.json`
4. Set `extracted_date` to today

**Elliott Wave note:** The wave *targets* expire when the correction completes. The wave *pivot prices* (tops/bottoms) remain as permanent historical S/R. When updating, keep old pivots, update or remove the target block.

**Accessible TV indicators (as of 2026-04-25):**
- `Daily Weekly Monthly Yearly Opens` → yearly/monthly open prices via `data_get_pine_labels`
- `Market Maker Levels (v6)` → PD/PW High/Low via `data_get_pine_labels`
- `VWAP Supply & Demand Zones PRO` → zone prices via `data_get_pine_labels` (ignore historical pre-split prices)
- `Elliott Wave Chart Pattern` → pivot labels via `data_get_pine_labels`
- RSI, MACD, Stoch RSI → numeric values via `data_get_study_values`

**NOT accessible (canvas rendering — permanent limitation):** Volume Profile, LuxAlgo Liquidity, Session Volume Profile, Crypto Liquidation Heatmap.

---

### Calibration Quick-Reference

| What feels wrong | First check |
|---|---|
| Signals feel late or too slow | Check RSI drift vs TV; check EMA periods in `micro_engine.py` |
| OBs not matching what you see on chart | Compare Banshee SMC output vs visual; `INDUCEMENT_HARD_GATE` state |
| Verdict contradicts chart structure | Run `synthesize_nexus` and read the macro layer — may be macro-gated |
| Key level missed in SMC output | Update `htf_levels.json` — Banshee doesn't know levels it wasn't told |
| Stoch D very different from TV | Normal if RSI has minor drift; check if K matches (should be within 1pt) |

---

## Update Protocol

When adding a new feature to any engine:

1. Add or update the relevant section in this guide.
2. If a new named constant is added to `smc_engine.py`, add it to the constants table in the relevant concept section.
3. If a new visual element is added to the React UI, add it to the "How to Read a Banshee Chart" section.
4. If the interpretation of an existing field changes, update the concept section AND the step-by-step workflow.
5. If a gate or flag is flipped (e.g., `INDUCEMENT_HARD_GATE`), note it in "Known Limitations and Pending Work."

This guide is the single source of truth for how to use this system. The code is the implementation; this is the intent.
