# Banshee Pro 4 — Anti-Patterns

Things we tried that failed, or must never be repeated. Read this before making a similar decision.

---

## AP-1: MCP Transport — Never Use SSE

**What happened:** Tried SSE transport for the MCP server. Failed because SSE requires a pre-running server; nobody started it, so Claude got connection refused.

**Rule:** Always use `stdio` transport. Claude auto-spawns the process on demand. No pre-running server needed.

---

## AP-2: ML Lens — Parked Indefinitely

**What happened:** Trained a Transformer on EUR/USD 1h (2020–2023). Result: 49% directional accuracy — below random chance. Two likely causes: look-ahead bias in the scaler (fitted on full dataset, not train-only) and brutal signal-to-noise ratio on 1h forex.

**Rule:** Do not revisit ML approaches until directional accuracy can clear 55% on out-of-sample data. If revisiting: fix scaler bias first (fit on train only), then retrain, then retest. If still 49–51% on a different architecture, the problem is the data, not the model.

---

## AP-3: Presignal-Only — Dead on Most Assets

**What happened:** Presignal-only mode tested across 84+ batch runs. Average return: -3.9%, Sharpe: -0.17. Destructive on BTC/ETH in all modes.

**Rule:** Never use presignal-only as a standalone strategy. It is only useful as an *additive layer* to confirmed signals (confirmed + presignal beats confirmed-only). Exception: PAXG and some crypto in sniper mode show marginal positive results but with too few trades to trust.

---

## AP-4: Don't Accept Domain Corrections Without Evaluating Against the Spec

**What happened:** During inducement gate implementation, user offered a correction to the gate logic. Claude accepted it without pushback, then found the original spec comment said the opposite. After discussion, both were actually compatible — but the reflexive agreement nearly introduced a bug.

**Rule:** When the user offers a domain-specific correction to SMC logic or trading concepts, discuss it first — don't immediately agree and build. Say what the spec says, say what the user is saying, and resolve the conflict explicitly before writing code. This is captured in `feedback_spec_before_building.md` in Claude memory.

---

## AP-5: Both MCP Config Files Must Match

**What happened:** Updated `~/.claude/.mcp.json` but forgot `~/.mcp.json`. Old tools loaded after restart because one file still pointed to the old path.

**Rule:** Any time the MCP server path changes (new machine, new Pro version), update BOTH files simultaneously. Check both before debugging "old tools" symptoms.

---

## AP-6: `@st.cache_data` in Engine Files — Never Again

**What happened:** `macro_engine.py` and `shared_data.py` had `@st.cache_data` decorators and `import streamlit`. This made the engines impossible to run headless (MCP server, tests, Core) — `streamlit run` had to be active for the cache to work.

**Rule:** Engines are pure Python. They use `@ttl_cache` from `cache_utils.py`. Zero Streamlit imports allowed in engine files. `@st.cache_data` is only for `app.py` if absolutely needed.

---

## AP-7: Crypto Shorts Are Destructive (BTC/ETH)

**What happened:** Batch testing confirmed BTC and ETH shorts both produce deeply negative returns in all tested configurations. VIX gate does not save them.

**Rule:** Do not enable shorts for BTC or ETH. Only PAXG benefits from a short overlay (and only with VIX20 gate active). Crypto shorts are only valid in sustained bear regimes that our current 2-year test windows don't capture well.

---

## AP-8: Stale Memory Is Not Ground Truth — Code Is

**What happened:** The `banshee_pro.md` semantic memory file accumulated session notes over time and drifted from reality. Several items were marked "done" that were only partially done or not done at all. This was only caught by running a code audit.

**Rule:** When resuming after interrupted sessions or when something "feels off" about the memory, run a code audit (spawn an Explore agent against specific items) before trusting memory files. Memory is a point-in-time snapshot. The code is always ground truth.

---

## AP-9: Two Off-by-One Bugs in `smc_engine.py` — Found via TV OHLCV Cross-Check (2026-05-01)

**What happened:** BTCUSD 1D cross-validation against TradingView OHLCV data exposed two systematic errors that had been silently suppressing output for all assets.

**Bug 1 — OB lifecycle start:** `is_ob_active()` was starting the post-formation scan at `ob["idx"] + 1` (the candle that created the OB), which is the same candle as the BOS itself. This immediately voided every OB at the gate check. The correct start is `event_idx + 1` (the candle *after* the BOS that confirmed the OB). Result before fix: 0 active OBs. After: 2 pass through.

**Bug 2 — EQL sweep scan window:** `detect_eql()` started its sweep scan at `idx_2 + 1`, missing any sweeps that occurred between `idx_1` and `idx_2`. The correct start is `idx_1 + 1` (skipping `idx_2` explicitly with a `continue`). Result before fix: 3 false "unswept" EQL pools. After: 0.

**Rule:** Off-by-one errors in SMC detection are silent — they produce plausible-looking (but wrong) output rather than errors. Any time OB or EQL counts feel suspiciously low/high, run `validate_smc.py BTCUSD 1D` and cross-check against the TV chart before concluding the market has no structure.

---

## AP-10: INDUCEMENT_HARD_GATE Silently Removes Valid OBs — Always Check gate_passed (2026-05-01)

**What happened:** After fixing AP-9 bugs, the April bullish OBs (CHoCH Apr 7, BOS Apr 13) still weren't appearing in output. The hypothesis was that `FVG_WINDOW=5` was too tight. Full investigation showed both OBs formed correctly and were `active`. The actual cause: `INDUCEMENT_HARD_GATE = True` removed them entirely from `result["order_blocks"]` because there were zero EQL pools between the OB tops and current price — BTC ripped from the BOS to $79K without creating consolidation-era inducement pools.

**The trap:** When OBs are missing from output, the intuition is to look at detection logic (FVG window, swing lookback, etc.). But `INDUCEMENT_HARD_GATE` is a post-detection filter that silently erases valid, perfectly-formed OBs. There's no trace of the removal in the output.

**Rule:** When active OBs are unexpectedly absent, check `gate_passed` before investigating detection logic. Call `smc_engine.detect_order_blocks()` directly (bypasses the gate) and compare counts against `smc_engine.run()` output. If the count differs, the gate is the culprit — not detection. The fix was to change the gate from a filter to a tag (`gate_passed: bool`), so candidates remain visible in a separate tier.
