# Grid Fixes (Option C) + Portfolio Analysis Easter Egg — Design Spec
**Date:** 2026-06-07  
**Status:** Approved — ready for implementation planning

---

## Overview

Two features shipping as a pair. Part 1 (grid fixes) is pure repair work that benefits every watchlist. Part 2 (portfolio analysis) is a hidden easter egg that only reveals itself once the user creates a custom preset — the deeper they go, the richer the experience.

---

## Part 1 — Grid Fixes (Option C)

Four changes shipping together. All grid views benefit.

### Fix 1: Layout clipping

**Problem:** The AssetGrid has `overflowY: "auto"` but parent flex containers grow instead of constraining, so cards at the bottom of large presets are clipped and unreachable.

**Root cause:** Missing `minHeight: 0` down the flex chain from App → page layout wrapper → AssetGrid container. Flex children default to `minHeight: auto`, which lets them grow past the viewport.

**Fix:** Add `minHeight: 0` to every flex child in the layout chain. The grid already has `overflowY: "auto"` — it just never activates. Also ensure the ticker tape at the bottom is `flex: "0 0 auto"` (already is) and the grid wrapper is `flex: 1, minHeight: 0`.

One-line fix per wrapper in `app.jsx`.

---

### Fix 2: localStorage snapshot cache

**Problem:** On every page load, custom preset cards start from zero-filled stub data (`price: 0, chg: 0, edge: 50, verdict: 'WAIT'`). They look broken until the radar fetch resolves.

**Fix:** After every successful radar fetch, write the full per-symbol payload to `localStorage['banshee_snapshot']` as a JSON object keyed by symbol:

```json
{
  "BTC":  { "price": 63219, "chg": 1.4, "edge": 72, "verdict": "BUY", "bias": "↑ STRONG", "rsi": 58, "name": "Bitcoin", "cls": "CRYPTO" },
  "AAPL": { "price": 187.42, ... }
}
```

On mount, read `banshee_snapshot` and use it to hydrate any symbol whose data would otherwise be stub. Cards open looking real immediately (stale but credible).

**Badge states (three):**

| Badge | Color | Condition |
|---|---|---|
| `◇ INIT` | gray `--ink-4` | No snapshot entry for this symbol |
| `◈ CACHED` | amber | Snapshot data present, radar not yet resolved |
| `◆ LIVE` | teal `--buy` | Live radar data received this session |

Badge lives in the price column, below the `chg` line. Once live data merges, badge flips to LIVE and the snapshot is rewritten.

---

### Fix 3: Card state redesign

**Problem:** The WAIT verdict chip uses `rgba(245,158,11,0.06)` background — 6% amber on near-black = invisible. Custom preset cards look empty even though all sections render.

**Fix:** Three distinct visual states:

**INIT (no snapshot):**
- Stripe: `--line` (neutral gray)
- Price: `—` in `--ink-4`
- Sparkline area: shimmer animation (CSS `background-size: 200%` linear-gradient sweep)
- Verdict chip: dashed gray border, `— PENDING —` label, no fill
- Edge ring: `?` in dim color, `--line-2` border
- Footer metrics: `—` values at 40% opacity

**CACHED (snapshot data, radar pending):**
- Stripe: gradient using cached verdict color
- Price + chg: real cached values
- Sparkline: flat dashed line (no OHLCV yet)
- Verdict chip: real cached verdict, normal colors
- Edge ring: real cached edge score
- Footer metrics: real cached BIAS + RSI
- Badge: `◈ CACHED` amber

**LIVE (current session data):**
- Unchanged from current design for built-in symbols
- Badge: `◆ LIVE` teal
- Sparkline: real candles (from `buildCandles` for ASSETS members, from OHLCV fetch for custom symbols)

---

### Fix 4: Real sparklines for custom symbols

**Problem:** `buildCandles` in `data.js` immediately returns `[]` for any symbol not in `window.ASSETS`. The `Spark` component returns `null` for empty candles, so custom preset cards have a blank spark area.

**Fix:** Lazy OHLCV fetch for unknown symbols on first card render:

- Call existing Core endpoint: `GET /ohlcv?sym=META&tf=1H&n=60`
- **Debounce:** batch all unknown symbols on a 300ms timer so a 20-symbol preset fires one batched request, not 20 individual ones
- Store result in component state; re-render spark with real candles
- Built-in symbols continue using `buildCandles` (instant, no network)
- **Batch behavior:** the debounce timer collects all unknown symbols across the grid into a list, then fires one `GET /ohlcv` call per symbol sequentially (or in parallel, max 4 concurrent). This is not a new batch endpoint — it's debounced individual calls to the existing endpoint.
- **Fallback:** if Core is offline or returns an error, show flat dashed line (same as CACHED state spark) — no error UI needed

---

## Part 2 — Portfolio Analysis Easter Egg

### Design philosophy

This is not a Banshee scream. It's ice cream. The portfolio page uses a light pastel color scheme (lavender-cream walls, mint for positive performance, rose for negative, peach for alerts, lavender for AI) — distinct from the dark trading interface. The easter egg should feel like a reward.

---

### Entry point

A `PORTFOLIO ▸` button in the AssetGrid header, styled in peach with a soft border. Appears **only** on custom presets — never on built-in watchlists. It's quiet enough to miss on first encounter.

Clicking it for the first time opens the setup modal. On subsequent visits, it navigates directly to the portfolio page.

---

### Setup modal — first time

**Pre-fill behavior:** The symbol list is populated from the custom preset. The user only needs to add shares and optionally entry data — no re-entering tickers.

**Fields per row:**
- Symbol (pre-filled, read-only)
- Class (pre-filled, read-only)
- Live price (pre-filled from current data)
- Shares owned (required — free text number input)
- Entry price (optional)
- Entry date (optional — enables TWRR and historical tracking)

**Thesis field:** Optional free-text investment hypothesis. If provided, AI commentary explicitly evaluates against this thesis rather than a generic S&P 500 comparison.

**Adding symbols in the portfolio modal:** The user can add rows for symbols not in the preset. After adding, prompt: _"Add [TSLA] to the My Tech Plays preset too?"_ — soft confirmation, not forced.

**Removing symbols:** If a user deletes a row in the setup table, prompt: _"Remove [BTC] from the My Tech Plays preset too? (You might want to keep watching it.)"_ — note leans toward keeping, since a sold position may still be worth monitoring.

**Storage:** `banshee_portfolio.json` in the Banshee root:

```json
{
  "portfolios": [
    {
      "id": "uuid",
      "preset_id": "my_tech_plays",
      "name": "My Tech Plays",
      "thesis": "I believe AI infrastructure and digital assets will massively outperform the S&P 500 over the next decade.",
      "holdings": [
        { "sym": "AAPL", "shares": 10, "entry_price": 155.00, "entry_date": "2024-01-15" },
        { "sym": "NVDA", "shares": 5, "entry_price": null, "entry_date": null }
      ],
      "grade_history": [
        { "date": "2026-03-01", "grade": "B", "score": 72 },
        { "date": "2026-06-01", "grade": "B+", "score": 79 }
      ]
    }
  ]
}
```

---

### Portfolio page — visual design (ice cream palette)

**Color scheme (portfolio-only, does not affect rest of app):**

```
--bg-0: #fdf8ff   (soft white-lavender, body)
--bg-1: #f5f0ff   (light lavender, topbar/panels)
--bg-2: #ece5ff   (slightly deeper lavender)
--bg-3: #e0d8f8   (border-area tint)
--line: #c8bce8   (lavender border)
--ink:   #1e1640  (deep purple text)
--ink-2: #42368a
--ink-3: #7a6fb0
--ink-4: #a898cc
--mint:     #5dd6b4   (positive / portfolio line)
--rose:     #f080a0   (negative)
--peach:    #f4a860   (accent / alerts)
--lavender: #c4a8f8   (AI / secondary chart)
--gold:     #e8b840   (grade circle)
```

---

### Portfolio page — layout (inverted pyramid)

#### Level 1 — Grade band (topbar)

- **Grade circle:** 60×60px, vanilla radial gradient fill, gold border + glow. Letter grade A+ to F in warm dark gold.
- **KPIs:** Total Value | TWRR % (vs benchmark) | Sharpe | Max Drawdown
- **Name + count** right-aligned

Below the topbar, an **AI banner** spanning full width:
- Lavender-to-sky diagonal gradient background
- `◈` icon in lavender
- One paragraph of thesis-aligned commentary from the Pydantic `PortfolioReview` model
- Thesis quoted in italics below, left-bordered in lavender
- If no thesis provided: commentary compares to blended benchmark only

#### Level 2 — Dual lens (two columns)

**Left — Cumulative returns chart:**
- LightweightCharts line chart
- Portfolio line: mint `#5dd6b4`, 2.5px, with soft mint fill beneath
- Benchmark line: lavender `#c4a8f8`, 1.5px, dashed
- Benchmark label: auto-composed from sector weights (e.g. "70% QQQ · 30% BTC")
- Soft lavender-cream chart background

**Right — Risk scorecard:**
- 2×2 grid of metric cells
- Each cell has a 3px top border in its accent color: mint (Alpha), sky (Beta), lavender (Sharpe), peach (Tracking Error)
- Positive Alpha → mint text; negative → rose text
- Context note below each value (e.g. "good risk-adj. return", "high = active mgmt")

#### Level 3 — Component breakdown (two columns)

**Left — Holdings breakdown table:**
- Columns: SYM | SHARES | VALUE | WEIGHT | DRIFT | ALPHA
- DRIFT shows how far weight has moved from initial target (peach if over, sky if under)
- ALPHA per-asset vs blended benchmark (mint if positive, rose if negative)

**Right — Sector allocation vs rotation signals:**
- Rows: sector name | pill bar | pct | rotation signal badge
- Bars use gradient fills: mint for tech, peach for crypto, lavender for comms, etc.
- Bars are rounded-pill style (border-radius: 8px)
- Rotation signal from existing `sector_rotation_engine.py`: `↑ IN` (green), `↓ OUT` (rose), `→` (neutral)
- Summary note at bottom: "N of M sectors have positive rotation signals"

#### Level 4 — Grade history

- Flex row of monthly grade bars
- Bar color by grade tier: A grades = mint, B grades = sky, C grades = rose, D/F = rose darker
- Current month marked with ★
- Heights proportional to score (0–100)
- Labels: month abbreviation below, grade letter above bar

---

### Grade formula

| Component | Weight | Source | Notes |
|---|---|---|---|
| Momentum | 35% | Weighted avg of asset `edge` scores from radar | Always available |
| Sector alignment | 35% | % of portfolio weight in sectors with positive rotation signals | Always available |
| Risk-adjusted return | 30% | Normalized Sharpe ratio | Only when entry data provided; if missing, weight splits equally to momentum (50%) and sector alignment (50%) |

Score 0–100 maps to grades: A+ (95+), A (90–94), A- (85–89), B+ (80–84), B (75–79), B- (70–74), C+ (65–69), C (60–64), C- (55–59), D (50–54), F (<50).

---

### Backend

#### `portfolio_engine.py` (new file, follows engine adapter pattern)

```python
def run(holdings: pd.DataFrame, benchmark_returns: pd.Series) -> dict:
    """
    holdings: DataFrame with columns [sym, shares, entry_price, entry_date, current_price]
    benchmark_returns: pre-fetched benchmark return series
    Returns: { sharpe, alpha, beta, max_drawdown, twrr, portfolio_returns }
    """

def build_blended_benchmark(sector_weights: dict) -> pd.Series:
    """
    sector_weights: { 'TECH': 0.48, 'CRYPTO': 0.38, 'COMMS': 0.14 }
    ETF map: TECH→XLK, FINANCE→XLF, CRYPTO→IBIT, COMMS→XLC, ENERGY→XLE,
             HEALTH→XLV, CONSUMER→XLY, UTILITY→XLU.
    Sectors not in map are proxied by SPY weighted proportionally.
    Fetches via yfinance adapter, blends by weight. Returns: daily returns series.
    """

def score_portfolio(engine_result: dict, radar_data: dict, rotation_data: dict) -> dict:
    """
    Returns: { score: 0-100, grade: 'B+', momentum_score, alignment_score, risk_score }
    """
```

Engine accepts DataFrames; adapter handles yfinance fetching. Never couple engine to yfinance directly (see engine adapter pattern).

#### API endpoints (add to `banshee_core.py`)

| Method | Path | Description |
|---|---|---|
| GET | `/portfolios` | List all portfolios |
| POST | `/portfolios` | Create portfolio |
| PUT | `/portfolios/{id}` | Update portfolio (holdings, thesis) |
| GET | `/portfolios/{id}/analysis` | Run full QuantStats analysis, return grade + all metrics |

#### Python libraries

- `quantstats` — Sharpe, Alpha, Beta, Max Drawdown, TWRR  
- `yfinance` — via existing adapter pattern (DataFrames in, DataFrames out)  
- `pydantic` — `PortfolioReview` model for structured AI output

#### `PortfolioReview` Pydantic model

```python
class AssetNote(BaseModel):
    sym: str
    note: str
    sentiment: Literal["positive", "neutral", "negative"]

class PortfolioReview(BaseModel):
    thought_process: str
    overall_health_score: int        # 0-100
    primary_observation: str
    goals_alignment: str
    thesis_alignment_note: str       # empty string if no thesis provided
    asset_breakdown: list[AssetNote]
```

---

### Frontend routing

Portfolio page is a new route, same pattern as `MacroPage` and `NewsPage`. Navigation: `PORTFOLIO ▸` button sets `currentPage = 'portfolio'` + `currentPortfolioId`. Back arrow returns to the custom preset grid.

The ice cream color scheme is applied via a scoped CSS class (e.g. `class="portfolio-page"`) on the page wrapper — it does not bleed into the rest of the app.

---

### Preset ↔ Portfolio sync rules

The preset is the **watchlist** (what to watch). The portfolio is the **ownership record** (what you own). They are loosely coupled, not tightly synced.

| Action | Prompt |
|---|---|
| Add symbol in portfolio modal | "Add [SYM] to the _[Preset Name]_ preset too?" |
| Remove symbol from portfolio | "Remove [SYM] from the _[Preset Name]_ preset too? (You might want to keep watching it.)" |

Both prompts are soft confirmations — the user can decline. The preset and portfolio can legitimately drift apart (e.g., tracking a sold position on the watchlist).

---

### Grade history snapshot

Grade is snapshotted once per calendar month. Logic on `GET /portfolios/{id}/analysis`:
1. Run the full score calculation.
2. Check `grade_history` for an entry where `date` matches the current `YYYY-MM` prefix.
3. If none found: append `{ date: "YYYY-MM-01", grade, score }`.
4. If found and the new score is higher: update in place (grade can improve within a month, never regress mid-month).
5. Write updated `banshee_portfolio.json` to disk.

---

### Out of scope (v1)

- Monte Carlo simulations
- Options / derivatives positions
- Multi-portfolio comparison view
- Export to CSV/PDF
- Mobile layout
