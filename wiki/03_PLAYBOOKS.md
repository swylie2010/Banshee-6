# Banshee Pro 4 — Playbooks

Step-by-step guides for recurring procedures.

---

## Playbook 1: New Machine Setup

1. Copy `Banshee_Pro_4/` to the new machine
2. Run `pip install -r requirements.txt`
3. Create `~/.banshee_keys.json` with FRED + AI keys (or set via Settings tab in Streamlit)
4. Update BOTH MCP config files (`~/.claude/.mcp.json` AND `~/.mcp.json`) with the new absolute path to `mcp_server.py`
5. Run `launch_banshee.bat` to start Core + Streamlit
6. Verify Core health: `curl http://localhost:8765/health`
7. Restart Claude Code so it picks up the new MCP config

**Critical:** Both MCP files must match. If one is stale, MCP tools will use the old path silently.

---

## Playbook 2: Calibration Run (requires TradingView open)

Goal: compare Banshee's computed indicator values against TradingView ground truth.

1. Open TradingView Desktop, load the symbol and timeframe to calibrate
2. Ensure RSI, MACD, EMA, ATR, VWAP indicators are visible on the chart
3. Read current TV values via MCP: `data_get_study_values`
4. Run Banshee calibration: `python calibrate.py SYMBOL MODE`
   - Example: `python calibrate.py NVDA long_term`
5. Compare the output table. Acceptable drift thresholds:
   - RSI: ≤5pt | Stoch K: ≤5pt | Stoch D: ≤12pt | MACD: ≤15% rel | VWAP/ATR: ≤1.5% rel
6. If drift is within threshold: `python calibrate.py SYMBOL MODE --save` to update baseline
7. If drift exceeds threshold: investigate `micro_engine.py` for algorithm divergence

**NVDA 1W status (2026-05-02):** TV ground truth complete for RSI, MACD, StochRSI, VWAP, Close. All within drift thresholds (MACD pixel-perfect, RSI -2.85pt, StochD -4.18pt). EMA 50/200/ATR absent from baseline — `indicator_set_inputs` could not set EMA period (returns empty updated_inputs). Calibration is functionally complete; those three fields show INFO.

---

## Playbook 3: Connect TradingView (trigger phrase: "Let's connect TradingView")

1. Run `C:\Users\swyli\launch-tv.bat` — launches Chrome with CDP on port 9222
2. In Claude Code, verify MCP connection: call `tv_health_check`
3. Review `~/tradingview-mcp-jackson/rules.json` — confirm watchlist and bias criteria are current
4. Run `chart_get_state` to verify the active chart symbol and indicators
5. Confirm `htf_levels.json` is current for the symbol you're analyzing

**TV role:** Live chart eyes only — not a data pipeline. TV = eyes, Banshee = brain, Claude = synthesis.

---

## Playbook 4: Add a New Asset

1. **Asset Profile** (`asset_profiles.py`): add symbol to `KNOWN_ASSET_CLASSES` with the correct class key
   - Crypto: `crypto_altcoin` (most alts) or `crypto_btc` (BTC pairs)
   - Gold-linked: `gold_proxy`
   - Stocks: `equity` or `default`
2. **htf_levels.json**: if TV is open, extract named levels (yearly/monthly opens, PDH/PDL, EW targets) and add to `htf_levels.json`
3. **TV OHLCV** (optional): extract 1W/1D/4H/1H bars via `data_get_ohlcv` and save to `tv_extract/ohlcv/` for offline fallback
4. **Calibration** (optional): run `python calibrate.py SYMBOL MODE` to establish a baseline

---

## Playbook 5: Session End Memory Update

Do ALL of these before closing the session:

1. **Mark to-do items done** in `ACTIVE_TASK.md` — update to the next task if the current one is complete
2. **Append to running notes** (`Banshee_Running_Notes.md` in Claude memory) — one dated entry, discussions and decisions only, NO code
3. **Update wiki pages** if any architectural facts changed (file names, ports, design decisions)
4. **Update `02_DATA_AND_ASSETS.md`** if any asset profiles, htf_levels, or calibration status changed

**If the session was cut short:** The to-do and wiki are more important than the running notes. Update the wiki/ACTIVE_TASK first.

---

## Playbook 6: TV Replay Signal Validation (for disputed or Alpaca-anomaly trades)

**Purpose:** When a trade didn't execute correctly through Alpaca (or was closed early by human intervention), use TradingView replay to determine whether the signal was actually correct — independent of execution quality. Cleanly separates signal quality from execution quality.

**What this answers:** "If the trade had executed as Banshee described, would it have hit target before stop?"

**Steps:**
1. Pull the trade details from the journal: entry price, stop price, target price, entry date/time, symbol
2. Open TradingView with CDP connected (`launch-tv.bat`)
3. Set the chart to the correct symbol and timeframe
4. Start replay at a bar *before* the entry: `replay_start` with `date` set to the entry date
5. Advance bar by bar (`replay_step`) until the entry bar — note where entry, stop, and target sit relative to price action
6. Continue advancing until either stop or target is hit
7. Record the result:
   - Target hit before stop → `signal_correct = True`, failure was execution/management
   - Stop hit → `signal_correct = False`, signal was genuinely wrong
   - Neither hit in reasonable time → inconclusive (thesis didn't resolve)
8. Update the journal entry via `log_signal_outcome` with the finding and a note explaining it was replay-validated

**Important:** This is forensic analysis, not re-trading. The goal is honest signal evaluation, not finding reasons the trade "should have worked."
