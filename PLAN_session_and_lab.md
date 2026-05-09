# Banshee Pro 2 — Development Plan
## Session Architecture + Strategy Lab

**Status:** Steps 1–4 COMPLETE. All Strategy Lab tabs operational.

---

## What Was Already Done (this session, do not redo)

- **ATR warmup bug fixed** in `micro_engine.py` → `add_supertrend()`:
  - Old code seeded `atr[0] = tr[0]`, causing severe underestimation on short timeframes (15m, 1h).
  - Fixed: seeds with `mean(tr[:period])`, fills warmup window with seed value.
  - This made sniper/swing modes show artificially tight stops. Long_term was fine (enough history).

---

## Step 1 — Session State / Symbol Switcher Architecture

### The Problem
Every tab currently fetches its own data independently:
- `render_asset_radar()` → local `target`, local `mode`, button "Scan Asset" → fresh fetch
- `render_banshee_nexus()` → same pattern, separate fetch
- `render_risk_desk()` → its own "Fetch Live Data" button
- If user checks BTC on Asset Radar then goes to Nexus, they re-enter BTC and re-fetch

### The Goal
- Pull once per symbol, stored in `st.session_state`
- Multiple symbols can be loaded in a session (BTC/USD, ETH/USD, NVDA)
- All tabs read from session cache, not from fresh fetches
- Mode switching (long_term/swing/sniper) refocuses which timeframes are shown — does NOT re-fetch
- 15-minute soft TTL (already handled by `@st.cache_data(ttl=900)` in shared_data.py)
- Force Refresh button re-fetches all currently loaded symbols

### Session State Keys to Add
```python
# Add to the session state init block (section 2 of app.py, around line 132):
if "active_symbol" not in st.session_state:
    st.session_state.active_symbol = None          # str | None
if "active_mode" not in st.session_state:
    st.session_state.active_mode = "swing"         # "long_term" | "swing" | "sniper"
if "symbol_cache" not in st.session_state:
    st.session_state.symbol_cache = {}             # { "BTC/USD": {"tfs": ..., "analysis": ..., "fetched_at": datetime} }
if "macro_cache" not in st.session_state:
    st.session_state.macro_cache = {}              # { "data": ..., "fetched_at": datetime }
```

### Symbol Switcher — Lives in the Sidebar
Replace the current sidebar (section 3 of app.py, around line 151) with this layout:

```
## 🦅 BANSHEE PRO 2.0

### NAVIGATOR
[radio: tabs as before, but now include 🧪 Strategy Lab]

---

### SYMBOL
[text_input: "Add Symbol" + "Load" button]
[pill buttons for each loaded symbol — clicking sets active_symbol]
[small "✕" next to each pill to remove from session]

### MODE
[selectbox or 3-button toggle: Long Term | Swing | Sniper]
→ sets st.session_state.active_mode globally

[Force Refresh button] — re-fetches all symbols in symbol_cache

---
🟢 FRED API  🟢 AI Key
```

### Helper Functions to Add (top of app.py, after imports)
```python
def load_symbol(symbol: str, mode: str):
    """Fetch all timeframes for a symbol and store in session cache."""
    tfs = micro_engine.load_and_prepare(symbol, mode)
    analysis = micro_engine.run_analysis(symbol, mode, tfs) if "error" not in tfs else tfs
    st.session_state.symbol_cache[symbol] = {
        "tfs": tfs,
        "analysis": analysis,
        "fetched_at": datetime.now(),
        "mode": mode,   # store which mode was used for this fetch
    }
    st.session_state.active_symbol = symbol

def get_active_data():
    """Return (tfs, analysis) for the active symbol, or (None, None)."""
    sym = st.session_state.active_symbol
    if not sym or sym not in st.session_state.symbol_cache:
        return None, None
    entry = st.session_state.symbol_cache[sym]
    return entry["tfs"], entry["analysis"]

def force_refresh():
    """Re-fetch all symbols currently in the session cache."""
    mode = st.session_state.active_mode
    for symbol in list(st.session_state.symbol_cache.keys()):
        load_symbol(symbol, mode)
```

### Tab Changes

**Asset Radar** (`render_asset_radar`):
- Remove local `target` text_input and `mode` selectbox
- Remove "Scan Asset" button
- Instead: check `get_active_data()` → if None, show "Load a symbol in the sidebar"
- If data exists, render it automatically
- The chart should use the fast timeframe for the CURRENT `active_mode` (not the fetched mode)
  - Re-run `run_analysis()` on cached `tfs` with the new mode — this is cheap (no network call)

**Banshee Nexus** (`render_banshee_nexus`):
- Same pattern: remove local inputs, read from session
- Macro data: cache in `macro_cache`. Re-use if < 15 min old. Only re-fetch if stale.
- AI checkbox stays (per-session preference)
- "Engage Nexus" button becomes "Generate AI Briefing" (since data is already loaded)

**Risk Desk** (`render_risk_desk`):
- Remove the "Auto-Fill from Ticker" input + "Fetch Live Data" button
- Instead: auto-populate `risk_entry` and `risk_stop` from session cache active symbol if available
- Show which symbol it pulled from
- All the math sliders remain — this is still a human what-if tool

### Re-analysis on Mode Switch
When mode changes in the sidebar, do NOT re-fetch network data. Instead:
```python
# When mode selectbox changes:
new_mode = st.selectbox(...)
if new_mode != st.session_state.active_mode:
    st.session_state.active_mode = new_mode
    # Re-run analysis on existing tfs with new mode
    sym = st.session_state.active_symbol
    if sym and sym in st.session_state.symbol_cache:
        tfs = st.session_state.symbol_cache[sym]["tfs"]
        new_analysis = micro_engine.run_analysis(sym, new_mode, tfs)
        st.session_state.symbol_cache[sym]["analysis"] = new_analysis
        st.session_state.symbol_cache[sym]["mode"] = new_mode
```
Note: `tfs` has ALL timeframes (1wk, 1d, 4h, 1h, 15m) already loaded by `load_and_prepare`.
Check that `load_and_prepare` fetches all timeframes, not just the 3 for the current mode.
If it only fetches 3, extend it to always fetch all 5 — small cost, enables free mode switching.

---

## Step 2 — Strategy Lab Skeleton ✅ DONE

**Gotchas discovered:**
- `requirements.txt` did not exist — created fresh with all known deps + `vectorbt`.
- `render_strategy_lab()` stub already existed in `app.py` (from a prior session); replaced it with a 2-line import+call to `strategy_lab.render()` rather than deleting the function entirely, so the router block is unchanged.
- `strategy_lab.py` stores backtest config in `st.session_state.lab_backtest_result` with `"status": "pending"` — Step 3 replaces the stub and populates the result dict with real stats + equity figure.



New file: `strategy_lab.py`
New nav entry: `"🧪 Strategy Lab"` added to the radio in the sidebar.
New router entry at bottom of app.py:
```python
elif view_mode == "🧪 Strategy Lab":
    import strategy_lab
    strategy_lab.render()
```

### The Concept
Fill-in-the-blank strategy builder → backtest → result. Three parts to any strategy:
1. **Entry signal** (e.g. EMA cross, RSI threshold, Supertrend flip)
2. **Exit signal** (e.g. ATR-based stop + target, fixed %, opposing signal)
3. **Position sizing** (fixed $ risk, fixed %, Kelly — keep simple)

### Required pip installs
```
vectorbt   # backtest engine (or backtesting.py — vectorbt is faster/more featured)
```
Add to requirements.txt.

### UI Layout (strategy_lab.py)
```
🧪 Strategy Lab

[Tabs inside this view: "Build Strategy" | "Backtest Results" | "Banshee Validation"]

--- Build Strategy tab ---
Strategy Name: [text_input]

Entry Conditions (AND logic):
  [dropdown: indicator] [dropdown: condition] [value/input]
  [+ Add Condition button]

Exit Conditions:
  [radio: ATR-based (1.5x stop / 3x target) | Fixed % | Opposing signal]
  [if Fixed %: two number_inputs for stop% and target%]

Timeframe: [selectbox: same options as rest of app]
Symbol: [auto-fills from active session symbol, or manual override]
Lookback Period: [slider: 6mo / 1y / 2y / 5y]

[Run Backtest button]

--- Backtest Results tab ---
[only renders if backtest has been run]
Equity curve (Plotly line chart)
Stats: Total Return, Sharpe Ratio, Max Drawdown, Win Rate, # Trades
Trade log table (entry date, exit date, return%)

--- Banshee Validation tab ---
Pre-built strategy that mimics Banshee's own signals:
  Entry: Supertrend bull + EMA_fast > EMA_slow + RSI < 70
  Exit: 3x ATR target or 1.5x ATR stop
  Run against any symbol to see if Banshee's own rules have historical edge
```

### Available Indicators for Entry Conditions
Pull from what micro_engine already computes (the `tfs` DataFrames have these columns):
- `ema_50`, `ema_200` — EMA crossover
- `rsi` — RSI threshold (< 30, > 70, etc.)
- `stoch_k`, `stoch_d` — Stoch RSI cross
- `st_bull` — Supertrend direction (bool)
- `vwap` — price vs VWAP
- `adx` — trend strength threshold

For backtesting, fetch data fresh via yfinance (not from session cache, since backtest needs full history).

---

## Step 3 — Wire First Strategy End-to-End ✅ DONE

First working strategy: **EMA Cross + ATR Stop**
- Entry: `ema_50` crosses above `ema_200` (golden cross)
- Exit: price hits `+3x ATR` (take profit) OR `−1.5x ATR` (stop loss)
- Sizing: fixed 1% risk per trade (R-based, consistent with Risk Desk)

Use `vectorbt` for the engine. Pattern:
```python
import vectorbt as vbt
entries = (ema_50 > ema_200) & (ema_50.shift(1) <= ema_200.shift(1))  # cross event
# exits computed from ATR levels per bar
portfolio = vbt.Portfolio.from_signals(close, entries, exits, ...)
stats = portfolio.stats()
```

Output goes into the "Backtest Results" tab.

---

## Step 4 — Banshee Signal Validation

Pre-built strategy in the "Banshee Validation" tab:
- Mimics Banshee's own verdict logic as closely as possible
- Entry: `st_bull == True` AND `ema_50 > ema_200` AND `rsi < 70`
- Exit: ATR-based (same as ATR trade plan)
- Run over 2 years of daily data for any symbol
- This answers: "does what Banshee says is a buy actually go up?"

This is the empirical Grounder from the testing framework insight.

---

## Break Points

After each step, Claude should:
1. Update the `## Status` line at the top of this file with what was completed
2. Note any gotchas discovered during implementation

**Break 1:** After Step 1 (session state + symbol switcher)
**Break 2:** After Step 2 (Strategy Lab skeleton wired in)
**Break 3:** After Step 3 (first backtest runs end-to-end)
**Break 4:** After Step 4 (Banshee validation tab) ✅ DONE

---

## File Map

| File | Role | Step Touched |
|---|---|---|
| `app.py` | Main Streamlit app — sidebar, routing, render functions | 1, 2 |
| `micro_engine.py` | Data loading + analysis — check `load_and_prepare` loads all 5 TFs | 1 |
| `shared_data.py` | Cache layer — no changes needed, TTL already set to 900s | — |
| `strategy_lab.py` | New file — entire Strategy Lab UI + backtest wiring | 2, 3, 4 |
| `requirements.txt` | Add `vectorbt` | 2 |

---

## Key Constraints / User Preferences

- User checks in periodically, not for long sessions — "pull once, view many ways"
- Force refresh is a manual override, not automatic beyond 15min TTL
- Risk Desk is a what-if human tool — preserve editability even after auto-fill
- Strategy Lab is new territory — start simple, one strategy end-to-end before adding complexity
- Free data only (yfinance, ccxt/Coinbase)
- The confidence problem: outputs mix facts/rules/AI inference — Strategy Lab is the empirical grounding layer
