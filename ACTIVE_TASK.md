# Active Task: Banshee 5 — React UI Phase 6 (next)

**✅ Phase 1 complete (2026-05-12):**
- `ui/` directory created in Banshee_5 — canonical home for all React UI files
- `index.html` — Lightweight Charts CDN added, `api.js` wired in
- `api.js` — fetch client: real Core calls with mock fallback, symbol normalisation (BTC→BTC/USD), TF mapping (1H→1h)
- `parts.jsx` — SVG Chart replaced with Lightweight Charts canvas. Shows ◆ LIVE / ◇ MOCK badge. Real OHLCV candles from Core working.
- `banshee_core.py` — CORS middleware + `/ui` StaticFiles mount. Version bumped to 5.0.
- `launch_banshee.bat` — updated to open `http://localhost:8765/ui/` instead of Streamlit
- Streamlit (`app.py`) kept intact as fallback — run manually if needed

**✅ Phase 2 complete (2026-05-13):**
- `micro_engine.py` — payload now includes `rsi` (float) and `chg_pct` (24h % from last 2 closes on fast TF)
- `banshee_core.py` — `/radar?output_mode=full` now returns `rsi`, `chg_pct`, `bias` (↑ STRONG/↑ MILD/→ FLAT/↓ MILD/↓ STRONG derived from trends dict); `_compute_bias()` helper added
- `app.jsx` — `App` fetches radar for all 20 assets on mount (parallel, swing mode); `radarData` state keyed by sym; `mergeRadar()` merges live fields (price, chg, verdict, edge, bias, rsi, atr); `AssetGrid` + `Sidebar` both receive live data; `DetailView` opens with merged asset
- `parts.jsx` — `AssetCard` shows dimmed loading overlay + blinking "◇ LOADING…" badge while pending; top stripe goes grey during load; "◆ LIVE" badge (green) replaces HUD ID once live data arrives

**UI lives at:** `http://localhost:8765/ui/`
**Restart Core** before testing to pick up micro_engine.py + banshee_core.py changes.

**✅ Phase 3 complete (2026-05-13): SMC Overlay on the chart**
- `SMCZoneRenderer` / `SMCZonePaneView` / `SMCZonePrimitive` — LW Charts v4.2 primitive classes in `parts.jsx`
- `smcToZones()` — parses `/smc/json` response: active OBs (solid fill, dashed if gate_passed=false) + active/partial FVGs (lighter fill) + skips mitigated/filled
- `Chart` component — accepts `smcData` + `smcLoading` props; attaches/detaches primitive on data change; SMC toggle button (top-right: "SMC ◇" loading → "SMC ◆/○" on/off)
- HTF key levels rendered as dotted amber price lines (up to 25 levels from `flat_levels`)
- `DetailView` — fetches SMC via `window.API.fetchSMC(sym, tf)` on symbol/tf change (cancellable); passes data + loading state to Chart
- `api.js` — `fetchSMC` now accepts UI tf format ("4H") and maps to core format ("4h") internally

**✅ Phase 4 complete (2026-05-14):**
- `api.js` — `fetchGH(sym)` + `fetchXABCD(sym)` added; both exported on `window.API`
- `parts.jsx` — `XABCDPrimitive` / `XABCDPaneView` / `XABCDRenderer`: canvas primitive draws XABCD leg polylines (dashed for forming, solid for confirmed) + PRZ shaded band (forming) or dotted D-level line (confirmed), point labels (X/A/B/C/D); `GHLevelsPrimitive` renders up to 12 hot zones as dashed price lines color-coded by bias (teal=floor, red=ceiling, amber=mixed; weight→opacity/thickness); Chart accepts `ghData/ghLoading` + `xabcdData/xabcdLoading`; toggle badges stacked: SMC ◆ (cyan) / GH ◆ (magenta) / XABCD ◆ (amber)
- `app.jsx` — `DetailView` fetches both GH and XABCD on symbol change (not tf); passes all to Chart

**✅ Phase 5 complete (2026-05-15):**
- `parts.jsx` — `SMCMarkersRenderer` / `SMCMarkersPaneView` / `SMCMarkersPrimitive`: canvas primitive draws swing labels (HH/LH/HL/LL triangles, last 14 labeled swings) + BOS/CHoCH text markers with dashed tick at break level; teal=bullish, red=bearish; attached alongside zone primitive, tied to same SMC toggle
- `parts.jsx` — EQH/EQL unswept liquidity pools as dotted `createPriceLine` calls (red=EQH resting sell stops, teal=EQL resting buy stops); swept pools skipped; managed via `eqlLinesRef`
- `app.jsx` — `sensorsToTopBar()` maps `/macro/sensors` response to TopBar shape: short regime label, dynamic regime color (green/yellow/red via `regime_level`), 6 live flag rows (VIX/SKEW/10Y/CREDIT/DXY 5D/CURVE); defensive try-catch + `Number()` coercion guards against bad sensor values
- `app.jsx` — `App` fetches macro on mount; TopBar regime dot/label color reflect live `regime_level`; `DetailView` + `RecBox` use live `risk_score` for PowerBar + signal checklist
- `app.jsx` — radar fetch skips VIX/DXY/TLT (macro reference symbols that don't have a trading radar profile); eliminates console warnings for those symbols

**✅ Phase 6 complete — UX Polish (2026-05-16):**
- Version badge: `v3.42` → `v5.0`
- Overlay toggles: added `zIndex: 10` to SMC/GH/XABCD buttons (LW Charts canvas was intercepting clicks)
- Ticker tape: wired to live `radarData`; `◆ TAPE · LIVE` / `◇ TAPE · MOCK` badge
- Timeframes: removed `1m`/`5m` (always mock); sniper mode now offers `15m`/`1H`
- Macro flags: click any flag (VIX/SKEW/10Y/CREDIT/DXY 5D/CURVE) → floating explanation panel
- Sidebar search: type any ticker → fetches Core radar, opens DetailView (handles custom symbols via `customAsset` state)
- AI Analysis: `◆ AI ANALYSIS` button in RecBox → calls `POST /ai/briefing`, shows text inline; resets on asset change

**✅ Phase 6 complete (2026-05-20):** V4 Streamlit feature audit done — 8 gaps identified, captured as Phase 7 backlog below.

---

# Active Task: Banshee 5 — Phase 7 (React UI — Missing Features)

**Next up: SMC Visual Redesign (Phase 8) — spec written, implementation plan needed**

---

## Phase 7 Backlog (ordered)

1. ✅ V4 feature audit — done
2. ✅ **GH Arc Renderer** — DONE (2026-05-20). Canvas ellipses in pixel space via `GHArcPrimitive`. Teal=floor, red=ceiling, 6 Fib levels. Works correctly on 1D. Sub-daily TFs show circles at wrong horizontal positions (bar-index mismatch) — known limitation, fixable later with timestamp-based centering.
3. ✅ **Warning/exception boxes** — DONE (2026-05-24). `computeWarnings()` + `WarnPanel` in original `app.jsx`. Then superseded by full UX redesign (see item 3b below).
3b. ✅ **Multi-page architecture + full UX redesign** — DONE (2026-05-25). Complete rewrite of `app.jsx` (~1800 lines) + new components in `parts.jsx`. Replaces cramped RecBox/WarnPanel with 4-page routing: Grid → AssetHub → AnalysisPage (SMC/GH/NEXUS tabs) → MacroPage. `AlertCard`/`AlertStrip` for full-width V4-style alert banners. `MacroSensorCard` for expandable sensor cards. `DeepDiveCard` for navigation. `SENSOR_EXPLAIN` dict. Full-width AI panels per tab.
4. ✅ **Settings page** — DONE (2026-05-25). Sidebar nav button + full-page layout. Two sections: API Keys (FRED, Alpaca key+secret) and AI Brain (provider dropdown: Gemini/OpenAI/Anthropic/Ollama/Custom, model, key, URL for Ollama/Tailscale, Test Connection button). Keys masked on load, server merges on save. Ollama over Tailscale confirmed working.
5. ✅ **SMC display refinement — DONE (2026-05-27).** V4 color scheme restored, inducement borders, PD zone gradients, OTE axis labels, FVG markers, full legend below chart. SMC AI pipeline fixed (now uses smc_analysis() dual-TF pathway). Optometry UI built: four named lenses (ALL/BATTLEFIELD/FOOTPRINTS/SNIPER) on TF bar with hotkeys 1–4. Hover composite deferred to backlog (see item 12b). Spec + plan at docs/superpowers/.
6. ✅ **Per-tab AI briefings** — DONE (2026-05-25). Each tab (SMC/GH/Nexus) now sends its `tab` param to `/ai/briefing`. `build_banshee_prompt()` has tab-specific format instructions: GH=zone status+harmonics+key levels+bias; SMC=structure+zones+liquidity+setup; Nexus=full cross-system synthesis. GH tab also injects XABCD pattern context. AbortController cancels stale in-flight requests on tab/symbol change.
6b. ✅ **AI button recolor** — DONE (2026-05-26). All AI analysis buttons now amber (`var(--amber)`).
6. ✅ **Risk Desk (interactive)** — DONE (2026-05-26). Full reactive position sizing calculator. 4 inputs → debounced POST to `/execution-plan` → 3 result panels (position size, capital efficiency 1x-5x leverage table, exit targets 1R/2R/3R). Auto-populates from focused symbol on mount. SMC conflicted checkbox halves size.
7. ✅ **Trading Journal** — DONE (2026-05-26). Full React port: open trades with live P&L from radarData, edit levels / close trade forms. Closed trades with outcome quality panel and annotation log. Feedback analysis button. Two backend bugs fixed (signal_correct str vs bool, update-levels optional fields).
8. ✅ **Signal Lab** — DONE (2026-05-26). Saved backtest results viewer with filter row + results table + inspect panel. "OPEN STRATEGY LAB →" button links out to Streamlit at localhost:8501. Option C approach (saved viewer + link-out, not iframe).
9. ✅ **Macro Deep-Dive sidebar panel — DONE (2026-05-28).** MacroPage was already the deep-dive page. Completed it: added 3 missing sensors (gold=GLD 5D, liquidity=Fed balance 60D, rotation=XLU/XLF/XLK/XLE vs SPY) with full SENSOR_EXPLAIN entries. MACRO_SENSOR_ROWS restructured: row 3=xle/copper/gold, row 4=liquidity/rotation. Macro AI briefing fixed (was broken — `fetchAIBriefing("MACRO")` hit OHLCV fetch → error every time) and given a dedicated `tab="macro"` pathway. New `build_macro_prompt()` in `banshee_ai.py`: macro-only briefing (no per-asset data), format: Regime Read → Sensors in Focus → What to Watch → Positioning Implications. Genuinely different from Nexus: macro briefing is environment-wide, Nexus is per-asset.
10. ✅ **News / Predator sidebar panel — DONE (2026-05-28).** Full-page NewsPage component: masthead (macro_tone badge + risk dots), top story block, collapsible ai_narrative, Run Daily Predator button with pipeline progress, Watchlist Events / Discovered Signals / Yesterday Followups card sections. PredatorCard (clickable source link when URL present, impact badge) + FollowupCard (status pill). Backend: `_attach_urls()` in `predator_engine.py` threads source-matched URLs from raw intake events into briefing JSON. CSS var naming fixed sitewide (all components now use established --bg-1, --bg-2, --bg-3, --ink, --buy, --sell). 9 commits on main.
11. ✅ **Pine Script generator for GH — DONE (2026-05-29).** `generate_pine_script()` in `geometric_harmonic.py` — 8 circles × 6 Fib levels as 60-pt polylines in normalized log space, teal=floor/red=ceiling, macro 20% transp/local 60% transp. `GET /geo-harmonic/pine` endpoint + `generate_gh_pine` MCP tool + PINE SCRIPT GENERATOR amber panel on GH tab (scrollable code block + COPY button). Spec + plan at docs/superpowers/. 64/64 tests green.
11b. ✅ **GH coordinate output + Pine Script UI polish** — DONE (2026-05-30). `cx_ts` added to `gh_circles` in engine. Table on GH tab: per-circle anchor date+price + shared radius endpoint date+price (6 columns, magenta border). Pine Script panel collapsible (▼/▲ toggle, starts collapsed) and moved below AI analysis.
12b. ✅ **Hover composite (Lens 4 SNIPER)** — superseded by full SMC Visual Redesign below (hover context card is included in that spec).
12. ✅ **Banshee Manual sidebar panel** — DONE (2026-06-01). Full content: 4-lens optometry guide, 8-step setup workflow, SMC concepts glossary (10 entries), GH arcs section, XABCD patterns reference (8 patterns with ratios). Hybrid format: walkthrough for lenses/workflow, reference cards for concepts.

---

# ✅ Phase 8 Complete (2026-05-31): SMC Visual Redesign

**Spec:** `docs/superpowers/specs/2026-05-30-smc-visual-redesign.md`
**Plan:** `docs/superpowers/plans/2026-05-31-smc-visual-redesign.md`
**Commits:** `244c01b` → `dee87fb` (13 commits) — all on `main`

- ✅ Color system: OBs deep blue/crimson, FVGs vivid teal/red, all direct hex
- ✅ Session weight badges: ⚡◈★ drawn on OB canvas rectangles
- ✅ HTF 4-color lines: gold (yearly/monthly), purple (MM), teal (VWAP), steel (Elliott)
- ✅ Swing markers: 16px orange/blue triangles
- ✅ BATTLEFIELD: BOS/CHoCH colored label boxes
- ✅ Dynamic visual weight: 3% proximity threshold, cold=35%; SNIPER filter-based
- ✅ Hover hit-testing: all 7 element types (OB, FVG, HTF, EQH, EQL, swing, BOS/CHoCH)
- ✅ HoverContextCard: lens-aware right panel, empty state shows lens description

---

# Next Task: Phase 9 — Polish & UX Fixes

Identified 2026-06-01. Mix of quick fixes and medium-effort items. Do quick batch first, then medium.

## Quick Fixes (batch together, few lines each)

- [x] **Sidebar toggle button** — changed to orange `#FF6D00` (2026-06-01)
- [x] **Back arrows** — all 6 `onBack` buttons changed to orange `#FF6D00` (2026-06-01)
- [x] **Tab labels (SMC/GH/Nexus)** — inactive tabs changed from `var(--ink-4)` to `var(--ink)` (2026-06-01)
- [x] **Macro flag name turns red when stressed** — `var(--sell)` color applied when f.st is stressed (2026-06-01)
- [x] **Alert section label font** — bumped 11→12 in parts.jsx (2026-06-01)
- [x] **GH coordinate table font** — bumped 11→12 in app.jsx (2026-06-01)

## Medium Effort

- [x] **SMC legend collapsible** — `legendOpen` state + toggle bar with ▼/▲; starts collapsed (2026-06-01)
- [x] **Nexus timeframe selector** — `nexusTf` state + TF bar row added above Nexus chart (2026-06-01)

## Also Fixed This Session (user review findings)

- [x] **AssetHub "GRID" back button** — was `var(--ink-2)`, now `#FF6D00` (2026-06-01)
- [x] **AssetCard live badge overlap** — removed absolute positioning, moved inline below price/chg in header column (2026-06-01)
- [x] **Sidebar accessibility** — zIndex raised 4→35; sidebar now slides in on top of any full-page overlay (2026-06-01)
- [x] **SMC legend button visibility** — toggle bar text brightened to `var(--ink)` (2026-06-01)
- [x] **SMC legend completeness** — added FVG bull/bear split, swing markers (HH/LH orange ▼, HL/LL blue ▲), BOS ▲/▼, CHoCH ▲/▼, EQH/EQL dotted lines, HTF level types (gold/purple/teal/steel) with section dividers (2026-06-01)

## Phase 9 Additions (2026-06-01 review findings)

### Quick Fixes
- [x] **Settings back button** — DONE (2026-06-02). Was still `var(--ink-2)`; now `#FF6D00`. MacroPage back button also caught and fixed.
- [x] **Nexus TF → trade recommendation** — DONE (2026-06-02). `nexusMode` derived from `nexusTf` (1H=sniper/4H=swing/1D=long); stop/tp multiplier (0.4/1.2/3.0) updates on TF change; MODE label + HOLD time shown in trade panel.
- [x] **Nexus bottom bar (Edge Score/RSI/ATR/Vol/Bias)** — DONE (2026-06-02). MetricTile grid (5 cols) added below chart+aside block on Nexus tab; read-only, same layout as AssetHub.
- [x] **Macro flag popup on asset pages** — DONE (2026-06-02). TopBar `zIndex` raised 5→40 so its stacking context clears the page overlay z-index of 30; flag panels now appear on all pages.

### Medium Effort
- [x] **Macro 3-tier color system** — DONE (2026-06-02). `critical` bool added to all sensors in `macro_engine.py` with sharper thresholds (e.g. VIX>35, curve<-0.5, DXY>4%). `sensorsToTopBar` now emits "stressed"/"elevated"/"calm". TopBar: bullet + label both show green/yellow/red per tier. MacroSensorCard: teal=OK, amber=warning, red=critical with matching bg/border tints.
- [x] **Predator news: clickable article titles** — DONE (2026-06-02). Headline is now the `<a>` link with cyan hover; source chip demoted to plain label. `_attach_urls()` confirmed correct (source-name match). Non-functional links are AI paraphrase mismatches — acceptable.

### Needs Spec / Reference V4
- [x] **Risk Desk restore + Simulate** — DONE (2026-06-02). 9 commits (`1ea6b8d`→`2af53d0`). `journalOpen` API helper; seedAsset snapshot prop; search box in Risk Desk; simulate mode banner + PAPER TRADE button (useEffect cleanup); AssetHub SIMULATE confirmation panel (SIMULATE NOW / OPEN RISK DESK); EXECUTE "not enabled" inline message; Escape key simulate-mode routing fixed; mode state forwarded to journal POST. Manual section added.
- [x] **Watchlist custom groups** — DONE (2026-06-07). `PresetsModal` (parts.jsx): two-column overlay, create/rename/add tickers/reorder/delete. `customPresets` localStorage state in App; `watchlists` derived prop replaces all `window.WATCHLISTS` references. Spec + plan at docs/superpowers/.
- [ ] **Predator article injection (V4 restore)** — V4 Streamlit had a text area on the Predator page ("Story / URL") with an "Add to Banshee Collective Memory" button. User-injected strings were stored in session state and passed as `manual_stories` to every `/ai/briefing` call, labeled "USER INJECTED CONSTRAINTS (Highest Priority)" in the prompt. Backend (`banshee_ai.py` line 99, `banshee_core.py` line 1425) already fully supports `manual_stories`. React V5 hardcodes `manual_stories: []` in `api.js` line 193. Needs: text input + add button on NewsPage, session-level story list with per-story delete, and `manual_stories` wired through `fetchAIBriefing`.

## Phase 9 Additions — Round 2 (captured 2026-06-02)

- [x] **Technical indicators on chart** — DONE (2026-06-04). EMA 50 (blue), EMA 200 (red), VWAP (purple dashed) on main pane + Stoch RSI %K/%D toggleable. EMA/VWAP on by default, Stoch off. Toggle buttons on RIGHT side of chart (EMA ◆, VWAP ◆, STOCH ◆). Spec + plan at docs/superpowers/. 6 commits. **Stoch sub-pane display issue remains** — see next item below.
- [x] **Stoch sub-pane fix + drag-to-resize** — DONE (2026-06-06). Fixed layout overflow by making Chart's outer wrapper a fixed `height`-pixel envelope — main chart shrinks when Stoch is on, expands when off; parent layout never sees a height change. Added drag handle (6px bar between main and Stoch panes): drag up/down resizes Stoch (60–300px range), main chart adjusts via `applyOptions({ height })`. Stoch uses `autoSize: true` so it self-resizes. `stochHeight` state persists across toggle offs/ons.
- [x] **Signal checklist + edge check** — DONE (2026-06-03).

## Sovereign AI Architecture (very long-term, foundational — captured 2026-06-03)

These three items are core to Banshee's identity: local-first, cheap, hot-swappable AI brains. No urgency — build them when the time is right, but the design should inform Settings page evolution now.

- [ ] **Standardize Ollama path on OpenAI API schema** — `call_ai()` currently hits Ollama's legacy `/api/generate` with a flat `prompt:` string. Ollama also serves `/v1/chat/completions` (OpenAI compat). Migrate the `ollama` branch to use `openai.OpenAI(base_url=..., api_key="ollama")`. This collapses the Ollama + Custom branches into one and makes any OpenAI-compat provider (LM Studio, Jan, LocalAI, Groq, Together, Fireworks, OpenRouter, Vertex, Mistral AI) configurable with just a base_url + model name. Gemini and Anthropic retain their own SDK branches — their native SDKs expose features (thinking tokens, caching, 1M context) the compat layer doesn't.
- [ ] **Context-aware routing** — No token counting exists today. `num_ctx: 8192` is hardcoded for Ollama. Build a `route_by_capacity()` wrapper: measure assembled prompt size (tiktoken or `len//4` approximation), compare to configured model context limit, either truncate secondary sections (news, distant FVGs, older structure events) or fall back to the cloud brain. This is the key piece that makes Banshee *aware* of its own cognitive capacity and able to route around limits without human intervention. When Gemma 5 ships with 1M context, this logic becomes a config value change, not a code change.
- [ ] **Externalize system prompts** — `_SMC_SYSTEM_PROMPT` and the default system prompt in `call_ai()` are hardcoded Python strings. Move to external YAML files with named variants per model family (e.g. `prompts/smc_gemma.yaml`, `prompts/smc_gemini.yaml`). Different model families respond differently to formatting — Gemma prefers direct instructions, Gemini handles detailed constraints well. This lets prompt tuning happen without code deploys and lets Banshee carry model-specific personalities.
- [ ] **AI Brain roster + Settings expansion** — The current Settings page has one active brain (provider + model + key + URL). Long-term this becomes a named roster: multiple configured brains, each with type/base_url/model/context_limit/cost_tier. Routing policy selector: "prefer local, fall back to cloud if context > X". Candidate providers to eventually support beyond Ollama: LM Studio (localhost:1234, OpenAI compat), Jan.ai, LocalAI, Groq (cloud, ultra-fast LPU), Together AI, Fireworks AI, OpenRouter (meta-API: one key, 100+ models), Google Vertex AI (enterprise Gemini + open models via Model Garden), Mistral AI, Cerebras. Most already speak OpenAI compat — once item 1 above is done, adding them is a URL.

## Longer-Term (needs spec/design before touching code)

- [ ] **Dynamic zone boundaries ("blast radius")** — Zones should be bounded on *both* sides by their own history, not the viewport. Left edge: always the formation candle (`start_time`) — never bleeds left into the viewport on scroll. Right edge: active zones extend to current candle; mitigated zones cap at the mitigation candle and render as a ghost (10% opacity, no solid border). Together these give the trader a free temporal read: zone width = age at a glance, no label needed. A month-old unmitigated OB reads differently than a day-old one just from geometry. The ghost box approach (from Blast Radius.md) is the right model for the right edge — not hiding mitigated zones entirely, but anchoring them in time. Key data needed: `end_time` (mitigation candle timestamp) from SMC engine — check whether `smc_engine.py` already stores this or only tracks status. Affects ALL lens and FOOTPRINTS most. Needs a spec session before touching canvas code.
- [ ] **Timeframe filtering by data availability** — `TF_LIST = ["1H", "4H", "1D"]` is hardcoded. Timeframes that the data source can't serve should not appear. Requires: Core API to report available TFs per symbol/source, UI to filter TF_LIST accordingly. Blocked on data source architecture.
- [ ] **Custom data source / API management** — allow users to plug in their own API keys (CoinGecko paid, Binance, etc.) and have the timeframe list reflect what that source supports. Would live in Settings page as a "Data Sources" section. Core needs a pluggable fetcher layer. Needs a proper spec session.

## Security Hardening (pre-open-source, needs dedicated session)

Research doc: `Research and Resources/BLACK HAT.md` — Gemini black-hat analysis, 4-phase roadmap.

Key issues identified (grouped by phase):
- **Phase 1 (Secrets):** `os.chmod(KEYS_FILE, 0o600)` missing in `shared_data.py`; `/settings` endpoint may leak masked keys to browser Network tab; sanitize stack traces in error responses
- **Phase 2 (Auth/SSRF):** No local bearer token — any process on machine can hit `:8765`; `/settings/test` passes user-supplied URL directly to `requests.post()` — block internal IP ranges (127.x, 192.168.x, 169.254.x)
- **Phase 3 (Concurrency/Input):** No file lock on `paper_trades.json` — background scheduler + UI writes can collide and corrupt; no symbol input validation (length/charset checks on `/radar`, `/smc`, etc.); RSS feed content injected raw into LLM prompt — wrap in `<user_content>` tags + system prompt guard
- **Phase 4 (Legal/UX):** Risk acknowledgment modal on first launch (store `accepted_disclaimer: true` in settings); hardcode Alpaca connection to paper endpoint for V1; HITL for any live trade action; CORS must be surgical (`localhost:3000` only, never `*`)
- **Other:** Pin versions in `requirements.txt`; `.gitignore` must cover `.banshee_keys.json`, `.banshee_kill_switch.json`, `paper_trades.json`; audit for accidental key logging in exception handlers

When to tackle: before any public/open-source release. No urgency now.

## Sector Rotation / Growth Detection (macro engine expansion)

Research doc: `Research and Resources/Sector Rotation and Macro Signal System For Growth indicator.md`

Current state: `macro_engine.py` has a stub `rotation` sensor tracking 4 sectors (XLU/XLF/XLK/XLE vs SPY, 5-day) but its **weight is 0** — not affecting risk score.

What the research paper describes (full MacroRotationEngine):
- All 10 sector SPDRs (XLK/XLY/XLI/XLB/XLE/XLF/XLV/XLP/XLU/XLRE) vs SPY benchmark
- Comparative Relative Strength (CRS) = sector/SPY ratio per day
- Rate of Change (ROC) on CRS over 5-day (velocity) and 21-day (structure) windows
- FRED macro overlay: copper-to-gold ratio (PCOPPUSDM / GOLDAMGBD228NLBM), M2 (WM2NS), 10Y yield (DGS10) — requires FRED API key (already in settings)
- Cross-Asset Momentum Divergence (CAMD) detection: sector outperforming when SPY is weak = stealth accumulation signal
- JSON payload → LLM synthesis → "Rotation Alert"

Integration: new `sector_rotation_engine.py` → results surfaced on MacroPage as a new sensor row + rotation alert card. Existing FRED key in settings is the only new credential needed. Needs spec session before build.

## Cosmetic (known, low priority)

- [ ] BOS/CHoCH box edge clamping — canvas overflow on top/right edges, cosmetic only

**Context (carry forward):**
- Banshee 5 = asset-centric visual platform. Click asset → unified chart with toggleable overlays.
- Babel standalone for now; esbuild migration after all overlays are working.
- Signal Lab / Trade Journal keep their Streamlit tabs; link to them from React UI.
- Diagnostic badge on Chart (⚠ / ◆ LIVE / ◇ MOCK) — keep while debugging, remove when stable.

**Trigger phrase:** "Banshee React UI wiring session"

---
# Previously Completed: ✅ Trade Journal UI "Feedback Analysis" Button — DONE

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
5. ✅ **XABCD harmonic pattern scanner** — `xabcd_scanner.py` built; `GET /xabcd` Core endpoint; `scan_xabcd` MCP tool; XABCD section added to Geo Harmonic tab in `app.py`. Gartley, Bat, Alt Bat, Butterfly, Crab, Deep Crab, Shark, 5-0. ZigZag pct-reversal, ±5% ratio tolerance, confirmed + forming patterns with PRZ. (2026-05-12)

**Phase 3 — Pine Script Generator: ✅ DONE (2026-05-29)**
`generate_pine_script()` in `geometric_harmonic.py`. Paste-ready Pine Script v5 — circles drawn as 60-pt polylines in normalized log-space (same math as engine). 1D chart only. Values baked in at generation time.

---
## Ops Notes (from Linux session 2026-05-08)
- **stop_banshee.sh created** — `pkill -f banshee_core.py && pkill -f "streamlit run"` — run when stale processes block port 8501
- **Hermes launch order** — Core must be up (`/health` responding) before starting Hermes; first-try "couldn't find Banshee" errors are purely a race condition, not a config issue
- **API keys confirmed present** — `~/.banshee_keys.json` has FRED, Gemini 2.5 Flash, and Alpaca on Linux machine
