# Active Task: ✅ Trade Journal UI "Feedback Analysis" Button — DONE

**Context:**
The `get_feedback_synthesis` MCP tool and `GET /journal/feedback-synthesis` Core endpoint both exist and work. The endpoint cross-references judged closed trades with `daily_briefings.jsonl` via AI synthesis to surface recurring patterns. It is not yet exposed in the Streamlit UI.

**Objective:**
Add a "Feedback Analysis" button to the Trade Journal tab in `app.py` that calls the Core endpoint and displays the synthesis result.

**Steps:**
1. Read the Trade Journal tab in `app.py` to understand its current layout and how it calls Core
2. Add a "Feedback Analysis" button that calls `GET /journal/feedback-synthesis` via the Core HTTP client
3. Display the returned synthesis text in an `st.markdown` or `st.expander` block below the journal table
4. Test: ensure the button works when there are judged trades and when there are none

**Key files:**
- `app.py` — Streamlit UI (Trade Journal tab)
- `banshee_core.py` — `GET /journal/feedback-synthesis` endpoint (already exists)

**Completed:**
- ✅ OpenClaw Step 1: Confidence Scoring — `smc_conflicted` param halves position size; surfaced in Risk Desk + MCP (2026-04-29)
- ✅ OpenClaw Step 2: Kill Switch — `close_all_open_trades()` + `/kill-switch/check` + `/kill-switch/status` + background 15-min scheduler job + `check_kill_switch` MCP tool + red banner in Macro Weather UI (2026-04-29)
- ✅ OpenClaw Step 3: Feedback Loops — `GET /journal/feedback-synthesis` endpoint + `get_feedback_synthesis` MCP tool; cross-references judged closed trades with `daily_briefings.jsonl` via AI synthesis (2026-04-30)
- ✅ OHLCV → SMC Validation — `validate_smc.py` built; BTCUSD 1D cross-checked vs TV; two bugs fixed (OB lifecycle offset, EQL sweep window); documented in AP-9 (2026-05-01)
- ✅ Candidate OB visibility — FVG_WINDOW hypothesis was a false lead; real cause was INDUCEMENT_HARD_GATE filtering active OBs with no EQL in their path. Changed gate from filter to tag (`gate_passed: bool`); candidates render as dashed/20%-opacity "OB? ▲" on Structure Map; shown in separate CANDIDATES section in validate_smc.py; excluded from AI prompt and signal scoring (2026-05-01)

**Backlog (next tasks in order):**
1. ✅ Trade Journal UI "Feedback Analysis" button — done (2026-05-01)
2. ✅ Add missing altcoins to `KNOWN_ASSET_CLASSES` in `asset_profiles.py`: HYPE, HBAR, TAO, XLM, NEAR — already present (2026-05-02)
3. ✅ Review/verify `~/tradingview-mcp-jackson/rules.json` — rewritten with Banshee's actual watchlist, SMC bias criteria, per-class risk rules, validated strategies (2026-05-02)
4. ✅ NVDA calibration baseline — TV ground truth written to `tv_extract/calibration/NVDA_long_term_baseline.json`; all indicators within drift thresholds (RSI -2.85pt, MACD pixel-perfect, StochD -4.18pt); ema_50/200/atr fields need TV baseline (indicator_set_inputs couldn't set EMA length) (2026-05-02)
5. ✅ Linux pre-flight — ghost-close fixed (threading.Lock + POST /journal/close + POST /journal/sync-alpaca; app.py routed through Core); response cache added to /radar and /smc (3-min TTL on micro_engine/smc_engine results); launch_banshee.sh created; OPENCLAW_PROTOCOL.md written (2026-05-02)

- ✅ SOL full calibration — 1W + 1D OHLCV extracted; htf_levels.json populated (yearly $124.65, monthly $83.08, EW levels, EMA 200 daily $115.82, VP node map, SMC snapshot); Asset Radar long_term vs sniper divergence confirmed and explained; Fibonacci circles read via MCP (2026-05-06)

**✅ Wire Geo Harmonic context into Nexus AI Briefing — DONE (2026-05-07)**

- `banshee_ai.py` — `build_banshee_prompt()` now accepts `geo_harmonic_context: str = ""`; injects `--- GEO HARMONIC CONTEXT ---` section + ▲/▼/◈ instruction before format block
- `banshee_core.py` — `route_ai_briefing()` calls `gh.run(_gh_df, multi_window=True)` on the 1d frame; formats top 5 zones (bias symbol, price, dist%, tier, sources); passes as `geo_harmonic_context`; fails silently if GH unavailable

**After Linux setup:** Set up Banshee Pro 4 on Linux machine + configure Gemini CLI MCP + run first OpenClaw test session (NVDA long_term, paper trade)

**Backlog — Geometric Harmonic Feature (design-complete, ready to build):**
Full research doc at `Research and Resources/Geometric Harmonic Trading Application Development.md`.

**Final design (all open questions resolved):**
- Macro anchors: absolute ATL (Circle A, bottom-up) and absolute ATH (Circle B, top-down)
- Local anchors: ZigZag highest/lowest within last N candles, N ∈ {144, 233, 377} (Fibonacci bar counts, not calendar dates)
- ATH rule: absolute ATH; when new ATH set, Circle B shifts and full recalculation triggers (Vector Decay)
- Sc calibration: HYBRID — macro circles use Macro Log Scaling `(ln(ATH)-ln(ATL))/(T_ATH-T_ATL)`; local circles use ATR method `ATR_period / 1 time unit` (ATR already in micro_engine.py)
- Intersection ranking: DBSCAN clustering; weights: Macro-Macro > Macro-Local > Local-Local
- Vector Decay: local circles expire at 233 or 377 bars, or on new ATH
- Phase 2 only: XABCD harmonic pattern scanner (Gartley, Bat, Butterfly, Crab, Shark, 5-0)

**UI: own Streamlit tab** (changed from "AI context only") with:
- ZigZag overlay (swing structure)
- Lines showing arc cross-sections at current timeframe price axis
- Intersection markers (hot zone coordinates)
- Text summary of ranked significant price levels
- MCP tool exposing same data to AI
- Purpose: give user exact TradingView anchor coordinates (currently placed by feel)

Trigger phrase for build session: "Geometric Harmonic build session"

**✅ BUILT (2026-05-06):**
- `geometric_harmonic.py` — engine: ZigZag pivots, log-price normalization (Sc_macro), macro + local Fib arcs, circle-circle intersection math, DBSCAN clustering, `run()` + `format_human()` API
- `banshee_core.py` — `GET /geo-harmonic` endpoint (route 12)
- `app.py` — "🔮 Geo Harmonic" sidebar tab + `render_geo_harmonic()` function
- `mcp_server.py` — `get_geo_harmonic(symbol, n_local)` tool
- `requirements.txt` — `scikit-learn` added

**Restart Core to activate the endpoint.**

**Phase 2 — Refinements (design settled 2026-05-06):**
1. ✅ **Surface radius endpoint in output** — `radius_endpoint` dict in result: date + price (`√(ATH×ATL)` geometric, or `(ATH+ATL)/2` arithmetic); surfaced as 5th metric in UI (2026-05-07)
2. ✅ **Directional bias per level** — `origin` tracked per circle (floor/ceiling); propagated through arc_levels → singularities → all_points → hot_zones via 65% weighted majority vote; ▼/▲/◈ symbols in chart labels, table, and MCP text (2026-05-07)
3. ✅ **Arithmetic midpoint mode toggle** — `arithmetic_mid` param on `run()`, Core route, and UI checkbox; uses `(ATH+ATL)/2` as radius endpoint instead of `√(ATH×ATL)` (2026-05-07)
4. ✅ **Multi-window confluence filter** — `multi_window=True` default; all 3 ZigZag windows generate circles; `source` tracked per circle (`macro_atl`, `macro_ath`, `local_144/233/377`); DBSCAN clusters filtered to 2+ distinct sources; `sources` list exposed per hot zone; UI checkbox replaces n_local selector as primary control (2026-05-07)
5. **XABCD harmonic pattern scanner** — Gartley, Bat, Butterfly, Crab, Shark, 5-0 ratio validation. Trigger phrase: "Geo Harmonic XABCD session"

**Phase 3 — Pine Script Generator:**
Banshee computes the exact anchor parameters and outputs them as Pine Script input values. User pastes into TradingView → circles render correctly with proper log-space scaling. Division of labor: Banshee is the brain (math + coordinates), Pine is the renderer (visual). This closes the gap between text reporting and the visual information the arcs carry as price approaches them in real time.
Trigger phrase: "Geo Harmonic Pine Script session"

---
## Ops Notes (from Linux session 2026-05-08)
- **stop_banshee.sh created** — `pkill -f banshee_core.py && pkill -f "streamlit run"` — run when stale processes block port 8501
- **Hermes launch order** — Core must be up (`/health` responding) before starting Hermes; first-try "couldn't find Banshee" errors are purely a race condition, not a config issue
- **API keys confirmed present** — `~/.banshee_keys.json` has FRED, Gemini 2.5 Flash, and Alpaca on Linux machine
