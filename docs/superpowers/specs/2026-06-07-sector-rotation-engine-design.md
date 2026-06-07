# Sector Rotation Engine — Design Spec
**Date:** 2026-06-07
**Status:** Approved

## Overview

A new engine that tracks where institutional capital is flowing across the 10 S&P 500 sector SPDRs using Comparative Relative Strength (CRS) and Rate of Change (ROC) math. Informational only — weight=0 in risk score. Goal: show which sectors are gaining or losing money flow, ideally a step ahead, at minimum in stride with the move.

## Architecture

**Approach:** Standalone module + new `/rotation` endpoint. Follows the same pattern as `geometric_harmonic.py`, `macro_engine.py`, etc.

**Files changed:**
- `sector_rotation_engine.py` (new) — pure computation, data-source agnostic
- `shared_data.py` — new `fetch_sector_closes()` adapter (yfinance today, swappable tomorrow)
- `banshee_core.py` — new `GET /rotation` endpoint
- `api.js` — new `fetchRotation()` call
- `ui/app.jsx` — MacroPage gains `rotationData` state + rotation panel
- `ui/parts.jsx` — new `RotationSection` component
- `banshee_ai.py` — `build_macro_prompt()` gains rotation context block

---

## Backend Engine (`sector_rotation_engine.py`)

### Interface

```python
def run(closes_df: pd.DataFrame, fred_key: str | None = None) -> dict:
    """
    closes_df: DataFrame with DatetimeIndex, columns = [SPY, XLK, XLY, XLI,
               XLB, XLE, XLF, XLV, XLP, XLU, XLRE]. Needs 25+ trading days.
    fred_key:  Optional FRED API key. If None, macro_env is omitted.
    Returns rotation payload dict.
    """
```

The engine never calls yfinance. It receives a pre-fetched DataFrame and is oblivious to the data source. When the user eventually wires in Alpaca, Polygon, or a CSV upload, only the adapter changes — not the engine.

### Data Fetch Adapter (`shared_data.py`)

```python
def fetch_sector_closes() -> pd.DataFrame:
    tickers = ["SPY","XLK","XLY","XLI","XLB","XLE","XLF","XLV","XLP","XLU","XLRE"]
    # Uses existing fetch_yf_history under the hood, period="3mo" (~63 trading days)
    # Returns DataFrame: DatetimeIndex, one column per ticker
```

### Core Math

| Metric | Formula | Purpose |
|--------|---------|---------|
| CRS_t | sector_close_t / SPY_close_t | Strips absolute market direction |
| ROC_5 | (CRS_t − CRS_{t−5}) / CRS_{t−5} × 100 | 1-week velocity trigger |
| ROC_21 | (CRS_t − CRS_{t−21}) / CRS_{t−21} × 100 | 1-month structural bid |
| SPY_ROC_21 | (SPY_t − SPY_{t−21}) / SPY_{t−21} × 100 | Broad market trend for CAMD gate |

**CAMD detection:** A sector is flagged `camd: true` when `ROC_21 > 0 AND ROC_5 > 0 AND SPY_ROC_21 ≤ 0`. The sector ranking is always computed unconditionally. CAMD is a layer on top — it identifies which outperformers are doing so against a weak or flat market.

**Divergence strength:** `ROC_21 − SPY_ROC_21` — how far ahead of the market the sector is running. Used to rank CAMD alerts.

### FRED Macro Context (optional)

Uses `fredapi` (already a dependency). Fetches:
- `PCOPPUSDM` — global copper price, monthly, forward-filled to daily
- `GOLDAMGBD228NLBM` — gold fixing price, daily
- `DGS10` — 10-year Treasury yield, daily

Computes copper/gold ratio and `macro_interpretation` string:
- CG rising + yield rising → "Risk-On Expansion"
- CG falling + yield falling → "Risk-Off Contraction"
- Divergence cases → "Divergence Warning: expect yield capitulation [up/down]"

If `fred_key` is None or FRED call fails: `macro_env` is `null` in the payload. Engine does not raise — fails silently.

### Output Payload

```json
{
  "timestamp": "2026-06-07T14:00:00Z",
  "spy_roc_21": -2.85,
  "sectors": [
    { "ticker": "XLU", "name": "Utilities",           "roc_5": 1.45, "roc_21": 5.10, "camd": true  },
    { "ticker": "XLP", "name": "Consumer Staples",    "roc_5": 0.92, "roc_21": 3.45, "camd": true  },
    { "ticker": "XLV", "name": "Healthcare",          "roc_5": 0.30, "roc_21": 1.20, "camd": false },
    { "ticker": "XLF", "name": "Financials",          "roc_5":-0.10, "roc_21": 0.80, "camd": false },
    { "ticker": "XLI", "name": "Industrials",         "roc_5":-0.40, "roc_21":-0.50, "camd": false },
    { "ticker": "XLB", "name": "Materials",           "roc_5":-0.60, "roc_21":-1.10, "camd": false },
    { "ticker": "XLE", "name": "Energy",              "roc_5":-0.80, "roc_21":-1.80, "camd": false },
    { "ticker": "XLRE","name": "Real Estate",         "roc_5":-1.20, "roc_21":-2.40, "camd": false },
    { "ticker": "XLY", "name": "Consumer Discret.",   "roc_5":-1.50, "roc_21":-3.10, "camd": false },
    { "ticker": "XLK", "name": "Technology",          "roc_5":-2.10, "roc_21":-4.20, "camd": false }
  ],
  "camd_alerts": [
    { "ticker": "XLU", "name": "Utilities",        "roc_5": 1.45, "roc_21": 5.10, "divergence_strength": 7.95 },
    { "ticker": "XLP", "name": "Consumer Staples", "roc_5": 0.92, "roc_21": 3.45, "divergence_strength": 6.30 }
  ],
  "macro_env": {
    "copper_gold_ratio": 0.00281,
    "ten_year_yield": 3.925,
    "interpretation": "Risk-Off Contraction: Falling Copper/Gold ratio and falling yields indicate defensive positioning."
  }
}
```

**Graceful error shape** (when data is unavailable):
```json
{ "error": "Data unavailable", "sectors": [], "camd_alerts": [], "spy_roc_21": null, "macro_env": null }
```

---

## Core Endpoint (`banshee_core.py`)

```python
GET /rotation
```

- Calls `fetch_sector_closes()` → `sector_rotation_engine.run(closes_df, fred_key)`
- `@ttl_cache(ttl=14400)` — 4-hour cache, same decorator used for `get_fed_liquidity`
- Returns JSON payload
- On exception: returns graceful error shape with HTTP 200 (UI handles it, no crash)

---

## Frontend (`api.js`)

```js
fetchRotation: () => fetch(`${BASE}/rotation`).then(r => r.json())
```

Exported on `window.API`. No symbol or TF params — rotation is always global.

---

## MacroPage UI (`app.jsx` + `parts.jsx`)

### State (MacroPage)

```js
const [rotationData, setRotationData] = useState(null);
const [rotationLoading, setRotationLoading] = useState(true);
```

`useEffect` on mount calls `window.API.fetchRotation()`. Independent of the existing sensors fetch — they do not block each other.

### Panel Layout (below MACRO_SENSOR_ROWS, above AI briefing button)

```
┌─────────────────────────────────────────────────────┐
│  SECTOR ROTATION ENGINE                             │
│                                                     │
│  Money appears to be flowing INTO Utilities and     │
│  Consumer Staples, and OUT OF Technology and        │
│  Real Estate this month.                            │
│                                                     │
│  SECTOR          5D RS    21D RS   FLOW             │
│  ─────────────────────────────────────────          │
│  ◆ Utilities      ▲+1.45%  +5.10%  ◆ CAMD          │  ← green tint
│  ◆ Consumer Stpl  ▲+0.92%  +3.45%  ◆ CAMD          │  ← green tint
│    Healthcare     ▲+0.30%  +1.20%                   │  ← green tint
│    Financials     ▼-0.10%  +0.80%                   │
│    Industrials    ▼-0.40%  -0.50%                   │
│    Materials      ▼-0.60%  -1.10%                   │
│    Energy         ▼-0.80%  -1.80%                   │
│    Real Estate    ▼-1.20%  -2.40%                   │  ← red tint
│    Consumer Disc  ▼-1.50%  -3.10%                   │  ← red tint
│    Technology     ▼-2.10%  -4.20%                   │  ← red tint
│                                                     │
│  ┌─────────────────────────────────────────────┐   │
│  │ ⚡ ROTATION ALERT                            │   │  ← amber border
│  │ XLU · Utilities — 21D: +5.10% · 5D: +1.45% │   │  (only when CAMD fires)
│  │ XLP · Consumer Staples — 21D: +3.45% · ...  │   │
│  │ Risk-Off Contraction: Falling Copper/Gold... │   │
│  └─────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────┘
```

**Color rules (table rows):**
- Top 3 by `roc_21` where `roc_21 > 0` → green tint bg (`rgba(0,200,100,0.08)`)
- Bottom 3 by `roc_21` where `roc_21 < 0` → red tint bg (`rgba(200,50,50,0.08)`)
- Middle rows → no tint

**`◆ CAMD` badge:** cyan, same style as other live badges. Only appears on rows where `camd: true`.

**CAMD Alert Banner:** only renders when `camd_alerts.length > 0`. Absent entirely (no empty card) when nothing fires. Amber border (`var(--amber)`), dark bg.

**`macro_interpretation` string:** shown inside the CAMD banner when `macro_env` is present. Omitted if FRED key not configured — banner still shows with just the sector lines.

**Loading state:** `◇ LOADING ROTATION DATA...` in `--ink-4`, single line, while `rotationLoading` is true.

**Plain-English summary:** Template string generated from `sectors` array — top 2 by `roc_21` (positive) = INTO, bottom 2 by `roc_21` (negative) = OUT OF. No AI — pure string interpolation.

### New `parts.jsx` component

`RotationSection({ data, loading })` — self-contained. Handles null/error/loading/success states internally.

---

## Macro AI Briefing (`banshee_ai.py`)

`build_macro_prompt()` gains an optional `rotation_context: str` param. When rotation data is available, the Core endpoint assembles a short block:

```
--- SECTOR ROTATION ---
Top flow: Utilities (+5.10% 21D RS, CAMD), Consumer Staples (+3.45% 21D RS, CAMD)
Weakest: Technology (-4.20% 21D RS), Consumer Discretionary (-3.10% 21D RS)
Interpretation: Risk-Off Contraction
```

Injected before the format block. Fails silently if rotation data is stale or unavailable.

---

## What This Does NOT Do

- Does not affect the risk score (weight=0, informational only)
- Does not add a new AI button or tab — rotation context feeds into the existing macro briefing
- Does not fetch individual stock data — SPDRs only
- Does not store history — live snapshot, not a time-series tracker
