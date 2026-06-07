# Sector Rotation Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Sector Rotation Engine that tracks CRS/ROC momentum across 10 sector SPDRs, surfaces results on MacroPage as a plain-English summary + ranked table + conditional CAMD alert banner, and injects rotation context into the macro AI briefing.

**Architecture:** New `sector_rotation_engine.py` with a data-source-agnostic `run(closes_df)` interface; `shared_data.py` provides a yfinance adapter `fetch_sector_closes()` cached for 4 hours; a new `GET /rotation` endpoint in `banshee_core.py` wires them together; `RotationSection` component renders the results on MacroPage. Weight=0 in risk score — informational only.

**Tech Stack:** Python (pandas, numpy, fredapi), FastAPI, React (Babel standalone), parts.jsx/app.jsx pattern.

---

## File Map

| File | Change |
|------|--------|
| `sector_rotation_engine.py` | **Create** — pure CRS/ROC computation, data-source agnostic |
| `tests/test_sector_rotation_engine.py` | **Create** — unit tests for the engine |
| `shared_data.py` | **Modify** — add `fetch_sector_closes()` yfinance adapter |
| `banshee_core.py` | **Modify** — import + `GET /rotation` route |
| `ui/api.js` | **Modify** — add `fetchRotation()` |
| `ui/parts.jsx` | **Modify** — add `RotationSection` component + window registration |
| `ui/app.jsx` | **Modify** — MacroPage state + useEffect + render RotationSection |
| `banshee_ai.py` | **Modify** — add `rotation_context` param to `build_macro_prompt()` |

---

## Task 1: Create `sector_rotation_engine.py` (TDD)

**Files:**
- Create: `C:\Users\swyli\AntiEverything\Banshee_5\tests\test_sector_rotation_engine.py`
- Create: `C:\Users\swyli\AntiEverything\Banshee_5\sector_rotation_engine.py`

- [ ] **Step 1: Create `tests/` directory and write failing tests**

Create `C:\Users\swyli\AntiEverything\Banshee_5\tests\test_sector_rotation_engine.py`:

```python
"""Tests for sector_rotation_engine.run()."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pandas as pd
import pytest
import sector_rotation_engine as sre

_TICKERS = ["SPY","XLK","XLY","XLI","XLB","XLE","XLF","XLV","XLP","XLU","XLRE"]
_SECTOR_NAMES = {
    "XLK":"Technology","XLY":"Consumer Discretionary","XLI":"Industrials",
    "XLB":"Materials","XLE":"Energy","XLF":"Financials","XLV":"Healthcare",
    "XLP":"Consumer Staples","XLU":"Utilities","XLRE":"Real Estate",
}


def _make_closes(n=30, spy_flat=True):
    """
    Synthetic closes DataFrame.
    - SPY: flat at 100 (spy_flat=True) or growing 90→100 (spy_flat=False)
    - XLU: growing 90→110 (roc_21 > 0, roc_5 > 0)
    - XLK: shrinking 110→90 (roc_21 < 0)
    - All others: flat at 100
    """
    dates = pd.bdate_range("2026-01-01", periods=n)
    data = {}
    if spy_flat:
        data["SPY"] = [100.0] * n
    else:
        data["SPY"] = [90.0 + 10.0 * i / (n - 1) for i in range(n)]
    data["XLU"]  = [90.0 + 20.0 * i / (n - 1) for i in range(n)]
    data["XLK"]  = [110.0 - 20.0 * i / (n - 1) for i in range(n)]
    for t in ["XLY","XLI","XLB","XLE","XLF","XLV","XLP","XLRE"]:
        data[t] = [100.0] * n
    return pd.DataFrame(data, index=dates)


def test_output_keys_present():
    result = sre.run(_make_closes(), fred_key=None)
    assert "sectors" in result
    assert "camd_alerts" in result
    assert "spy_roc_21" in result
    assert "macro_env" in result
    assert result["macro_env"] is None  # no FRED key


def test_all_ten_sectors_present():
    result = sre.run(_make_closes(), fred_key=None)
    tickers = [s["ticker"] for s in result["sectors"]]
    for t in _SECTOR_NAMES:
        assert t in tickers, f"{t} missing from sectors"


def test_sector_fields_present():
    result = sre.run(_make_closes(), fred_key=None)
    for s in result["sectors"]:
        assert "ticker" in s
        assert "name" in s
        assert "roc_5" in s
        assert "roc_21" in s
        assert "camd" in s


def test_sectors_sorted_by_roc21_descending():
    result = sre.run(_make_closes(), fred_key=None)
    rocs = [s["roc_21"] for s in result["sectors"]]
    assert rocs == sorted(rocs, reverse=True)


def test_xlu_has_positive_roc21():
    result = sre.run(_make_closes(), fred_key=None)
    xlu = next(s for s in result["sectors"] if s["ticker"] == "XLU")
    assert xlu["roc_21"] > 0


def test_xlk_has_negative_roc21():
    result = sre.run(_make_closes(), fred_key=None)
    xlk = next(s for s in result["sectors"] if s["ticker"] == "XLK")
    assert xlk["roc_21"] < 0


def test_camd_fires_when_spy_flat_and_sector_outperforms():
    # SPY flat (roc_21 = 0 ≤ 0), XLU outperforming → CAMD = True
    result = sre.run(_make_closes(spy_flat=True), fred_key=None)
    xlu = next(s for s in result["sectors"] if s["ticker"] == "XLU")
    assert xlu["camd"] is True
    assert any(a["ticker"] == "XLU" for a in result["camd_alerts"])


def test_camd_does_not_fire_when_spy_rising():
    # SPY growing 90→100 (spy_roc_21 > 0) → CAMD never fires regardless of sector
    result = sre.run(_make_closes(spy_flat=False), fred_key=None)
    assert all(not s["camd"] for s in result["sectors"])
    assert result["camd_alerts"] == []


def test_insufficient_data_returns_error_shape():
    tiny = _make_closes(n=10)
    result = sre.run(tiny, fred_key=None)
    assert "error" in result
    assert result["sectors"] == []
    assert result["camd_alerts"] == []
    assert result["spy_roc_21"] is None


def test_camd_alerts_sorted_by_divergence_strength():
    result = sre.run(_make_closes(), fred_key=None)
    strengths = [a["divergence_strength"] for a in result["camd_alerts"]]
    assert strengths == sorted(strengths, reverse=True)


def test_sector_names_match():
    result = sre.run(_make_closes(), fred_key=None)
    for s in result["sectors"]:
        assert s["name"] == _SECTOR_NAMES[s["ticker"]]
```

- [ ] **Step 2: Run tests to confirm they all fail (module not found)**

```bash
cd C:/Users/swyli/AntiEverything/Banshee_5
python -m pytest tests/test_sector_rotation_engine.py -v 2>&1 | head -20
```

Expected: `ModuleNotFoundError: No module named 'sector_rotation_engine'`

- [ ] **Step 3: Create `sector_rotation_engine.py`**

Create `C:\Users\swyli\AntiEverything\Banshee_5\sector_rotation_engine.py`:

```python
"""
sector_rotation_engine.py — Banshee 5 Sector Rotation Engine
=============================================================
Tracks institutional capital flows across the 10 S&P 500 sector SPDRs
using Comparative Relative Strength (CRS) and Rate of Change (ROC) math.

Data-source agnostic: run() accepts a pre-fetched DataFrame and never
calls yfinance directly. The caller provides the closes.
"""

import sys
import pandas as pd
import numpy as np
from datetime import datetime, timezone
from cache_utils import ttl_cache

SECTORS = {
    "XLK":  "Technology",
    "XLY":  "Consumer Discretionary",
    "XLI":  "Industrials",
    "XLB":  "Materials",
    "XLE":  "Energy",
    "XLF":  "Financials",
    "XLV":  "Healthcare",
    "XLP":  "Consumer Staples",
    "XLU":  "Utilities",
    "XLRE": "Real Estate",
}

_ERROR_SHAPE = {
    "error": "Insufficient data",
    "sectors": [],
    "camd_alerts": [],
    "spy_roc_21": None,
    "macro_env": None,
}


def run(closes_df: pd.DataFrame, fred_key: str | None = None) -> dict:
    """
    Compute sector rotation metrics from a pre-fetched closes DataFrame.

    Args:
        closes_df: DataFrame with DatetimeIndex and columns for SPY + all 10
                   sector SPDRs. Needs at least 22 trading-day rows.
        fred_key:  Optional FRED API key. If None, macro_env is omitted.

    Returns:
        dict with keys: timestamp, spy_roc_21, sectors, camd_alerts, macro_env.
        On insufficient data, returns _ERROR_SHAPE with an "error" key.
    """
    closes = closes_df.dropna(how="all").copy()

    if len(closes) < 22 or "SPY" not in closes.columns:
        return dict(_ERROR_SHAPE)

    spy = closes["SPY"]

    # SPY 21-day absolute momentum — gate for CAMD detection
    spy_roc_21 = float((spy.iloc[-1] - spy.iloc[-22]) / spy.iloc[-22] * 100)

    sectors_out = []
    for ticker, name in SECTORS.items():
        if ticker not in closes.columns:
            continue

        sector_prices = closes[ticker]
        crs = sector_prices / spy  # Comparative Relative Strength

        # Rate of Change on the CRS ratio
        roc_21 = float((crs.iloc[-1] - crs.iloc[-22]) / crs.iloc[-22] * 100)
        roc_5  = float((crs.iloc[-1] - crs.iloc[-6])  / crs.iloc[-6]  * 100)

        # CAMD: sector outperforming AND SPY flat-or-falling
        camd = bool(roc_21 > 0 and roc_5 > 0 and spy_roc_21 <= 0)

        sectors_out.append({
            "ticker": ticker,
            "name":   name,
            "roc_5":  round(roc_5,  2),
            "roc_21": round(roc_21, 2),
            "camd":   camd,
        })

    sectors_out.sort(key=lambda s: s["roc_21"], reverse=True)

    camd_alerts = [
        {
            "ticker":             s["ticker"],
            "name":               s["name"],
            "roc_5":              s["roc_5"],
            "roc_21":             s["roc_21"],
            "divergence_strength": round(s["roc_21"] - spy_roc_21, 2),
        }
        for s in sectors_out if s["camd"]
    ]
    camd_alerts.sort(key=lambda a: a["divergence_strength"], reverse=True)

    macro_env = _get_macro_env(fred_key) if fred_key else None

    return {
        "timestamp":   datetime.now(timezone.utc).isoformat(),
        "spy_roc_21":  round(spy_roc_21, 2),
        "sectors":     sectors_out,
        "camd_alerts": camd_alerts,
        "macro_env":   macro_env,
    }


@ttl_cache(ttl=14400)
def _get_macro_env(fred_key: str | None) -> dict | None:
    """
    Fetch copper/gold ratio + 10Y yield from FRED. Cached 4 hours.
    Returns None silently on any failure (FRED key absent, network error, etc.).
    """
    if not fred_key:
        return None
    try:
        from fredapi import Fred
        from datetime import timedelta

        fred  = Fred(api_key=fred_key)
        end   = pd.Timestamp.now()
        start = end - pd.Timedelta(days=90)

        copper = fred.get_series("PCOPPUSDM",        observation_start=start, observation_end=end).dropna()
        gold   = fred.get_series("GOLDAMGBD228NLBM", observation_start=start, observation_end=end).dropna()
        dgs10  = fred.get_series("DGS10",            observation_start=start, observation_end=end).dropna()

        if copper.empty or gold.empty or dgs10.empty:
            return None

        # Align monthly copper to daily gold via forward-fill
        combined = pd.DataFrame({"copper": copper, "gold": gold}).ffill().dropna()
        if len(combined) < 2:
            return None

        lookback = min(22, len(combined) - 1)
        cg_now   = combined["copper"].iloc[-1] / combined["gold"].iloc[-1]
        cg_prev  = combined["copper"].iloc[-lookback] / combined["gold"].iloc[-lookback]
        cg_trend = cg_now - cg_prev

        y_lookback  = min(22, len(dgs10) - 1)
        yield_now   = float(dgs10.iloc[-1])
        yield_prev  = float(dgs10.iloc[-y_lookback])
        yield_trend = yield_now - yield_prev

        if cg_trend > 0 and yield_trend > 0:
            interp = "Risk-On Expansion: Rising Copper/Gold ratio and rising yields indicate cyclical growth."
        elif cg_trend < 0 and yield_trend < 0:
            interp = "Risk-Off Contraction: Falling Copper/Gold ratio and falling yields indicate defensive positioning."
        elif cg_trend > 0 and yield_trend <= 0:
            interp = "Divergence Warning: Copper/Gold ratio rising but yields falling. Expect yield capitulation upwards."
        else:
            interp = "Divergence Warning: Copper/Gold ratio falling but yields rising. Expect yield capitulation downwards."

        return {
            "copper_gold_ratio": round(float(cg_now), 6),
            "ten_year_yield":    round(yield_now, 3),
            "interpretation":    interp,
        }
    except Exception as e:
        print(f"[sector_rotation] FRED fetch failed: {e}", file=sys.stderr)
        return None
```

- [ ] **Step 4: Run tests — all should pass**

```bash
cd C:/Users/swyli/AntiEverything/Banshee_5
python -m pytest tests/test_sector_rotation_engine.py -v
```

Expected: 11 tests PASSED

- [ ] **Step 5: Commit**

```bash
cd C:/Users/swyli/AntiEverything/Banshee_5
git add sector_rotation_engine.py tests/test_sector_rotation_engine.py
git commit -m "feat: add sector rotation engine with CRS/ROC math and unit tests"
```

---

## Task 2: Add `fetch_sector_closes()` to `shared_data.py`

**Files:**
- Modify: `C:\Users\swyli\AntiEverything\Banshee_5\shared_data.py` (after line 203, end of file)

- [ ] **Step 1: Append `fetch_sector_closes()` to `shared_data.py`**

Add this function at the **end** of `shared_data.py` (after `fetch_funding_rate`):

```python
@ttl_cache(ttl=14400)
def fetch_sector_closes() -> pd.DataFrame:
    """
    Fetch ~3 months of daily closes for SPY + all 10 sector SPDRs.
    Returns DataFrame with DatetimeIndex, one column per ticker.

    Data-source adapter for sector_rotation_engine — yfinance today,
    swappable when the user supplies a different data source. The engine
    itself never calls yfinance; it receives this DataFrame.

    Cached 4 hours (14400s). First call takes 2-5s; subsequent calls instant.
    """
    tickers = ["SPY", "XLK", "XLY", "XLI", "XLB", "XLE", "XLF", "XLV", "XLP", "XLU", "XLRE"]
    try:
        raw = yf.download(
            tickers=tickers,
            period="3mo",
            interval="1d",
            auto_adjust=True,
            progress=False,
        )
        # yf.download with multiple tickers returns MultiIndex columns: (field, ticker)
        closes = raw["Close"].dropna(how="all")
        closes.index = pd.to_datetime(closes.index).tz_localize(None)
        return closes[tickers]  # consistent column order
    except Exception as e:
        print(f"[fetch_sector_closes] yfinance failed: {e}", file=sys.stderr)
        return pd.DataFrame()
```

- [ ] **Step 2: Quick smoke test — confirm the fetch works**

```bash
cd C:/Users/swyli/AntiEverything/Banshee_5
python -c "
from shared_data import fetch_sector_closes
df = fetch_sector_closes()
print('shape:', df.shape)
print('cols:', list(df.columns))
print('rows:', len(df))
print('last row:')
print(df.iloc[-1])
"
```

Expected: shape ~(63, 11), all 11 tickers as columns, no errors.

- [ ] **Step 3: Commit**

```bash
cd C:/Users/swyli/AntiEverything/Banshee_5
git add shared_data.py
git commit -m "feat: add fetch_sector_closes() yfinance adapter to shared_data"
```

---

## Task 3: Add `GET /rotation` endpoint to `banshee_core.py`

**Files:**
- Modify: `C:\Users\swyli\AntiEverything\Banshee_5\banshee_core.py`

- [ ] **Step 1: Add `sector_rotation_engine` import and `fetch_sector_closes` to existing import**

Find line 41 in `banshee_core.py`:
```python
from shared_data import load_providers, fetch_crypto_ohlcv
```

Replace with:
```python
from shared_data import load_providers, fetch_crypto_ohlcv, fetch_sector_closes
```

Find lines 35-42 (the engine imports block) and add `sector_rotation_engine` after `predator_engine`:
```python
import macro_engine
import micro_engine
import banshee_ai
import risk_engine
import smc_engine
import predator_engine
import sector_rotation_engine
from shared_data import load_providers, fetch_crypto_ohlcv, fetch_sector_closes
from knowledge_graph import get_regime_weights
```

- [ ] **Step 2: Add `GET /rotation` route after `/macro/intel`**

Find the line `@app.get("/macro/intel")` (line ~1256). Insert the following block **after** the entire `/macro/intel` route function ends (look for the next `@app.` decorator after it — insert before that):

```python
@app.get("/rotation")
def route_rotation():
    """
    Sector rotation payload: CRS/ROC metrics for all 10 sector SPDRs vs SPY.
    Cached via fetch_sector_closes() (4h TTL in shared_data).
    Returns graceful error shape on data failure — never raises.
    """
    providers = load_providers()
    fred_key  = providers.get("FRED_API", {}).get("key")
    try:
        closes = fetch_sector_closes()
        if closes.empty:
            return {"error": "Data unavailable", "sectors": [], "camd_alerts": [],
                    "spy_roc_21": None, "macro_env": None}
        return sector_rotation_engine.run(closes, fred_key)
    except Exception as e:
        return {"error": str(e), "sectors": [], "camd_alerts": [],
                "spy_roc_21": None, "macro_env": None}
```

- [ ] **Step 3: Start Core and test the endpoint**

```bash
cd C:/Users/swyli/AntiEverything/Banshee_5
# Start Core if not running (in a separate terminal or background)
# Then test:
python -c "
import requests
r = requests.get('http://localhost:8765/rotation')
import json
d = r.json()
print('spy_roc_21:', d.get('spy_roc_21'))
print('sector count:', len(d.get('sectors', [])))
print('camd_alerts:', d.get('camd_alerts'))
print('first sector:', d['sectors'][0] if d.get('sectors') else 'none')
"
```

Expected: `spy_roc_21` is a float, `sector count` is 10, `first sector` has ticker/name/roc_5/roc_21/camd keys.

- [ ] **Step 4: Commit**

```bash
cd C:/Users/swyli/AntiEverything/Banshee_5
git add banshee_core.py
git commit -m "feat: add GET /rotation endpoint wired to sector_rotation_engine"
```

---

## Task 4: Add `fetchRotation()` to `api.js`

**Files:**
- Modify: `C:\Users\swyli\AntiEverything\Banshee_5\ui\api.js`

- [ ] **Step 1: Add `fetchRotation` function before the `window.API` export**

Find line 417 in `ui/api.js` (just before `window.API = ...`). Insert:

```js
async function fetchRotation() {
  try {
    const res = await fetch(`${BASE}/rotation`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (err) {
    console.warn("[api] fetchRotation:", err.message);
    return { error: err.message, sectors: [], camd_alerts: [], spy_roc_21: null, macro_env: null };
  }
}
```

- [ ] **Step 2: Add `fetchRotation` to the `window.API` export**

Find line 418:
```js
window.API = { fetchOHLCV, fetchRadar, fetchMacro, fetchSMC, fetchPresets, savePresets, fetchGH, fetchGHPine, fetchXABCD, fetchAIBriefing, fetchSettings, saveSettings, testAIConnection, fetchStrategies, fetchExecutionPlan, fetchTrades, closeTrade, updateLevels, updateOutcome, syncAlpaca, fetchFeedbackSynthesis, fetchPredatorBriefing, runPredator, journalOpen, coreSymbol };
```

Replace with (add `fetchRotation` at the end before the closing `}`):
```js
window.API = { fetchOHLCV, fetchRadar, fetchMacro, fetchSMC, fetchPresets, savePresets, fetchGH, fetchGHPine, fetchXABCD, fetchAIBriefing, fetchSettings, saveSettings, testAIConnection, fetchStrategies, fetchExecutionPlan, fetchTrades, closeTrade, updateLevels, updateOutcome, syncAlpaca, fetchFeedbackSynthesis, fetchPredatorBriefing, runPredator, journalOpen, coreSymbol, fetchRotation };
```

- [ ] **Step 3: Commit**

```bash
cd C:/Users/swyli/AntiEverything/Banshee_5
git add ui/api.js
git commit -m "feat: add fetchRotation() to api.js"
```

---

## Task 5: Add `RotationSection` component to `parts.jsx`

**Files:**
- Modify: `C:\Users\swyli\AntiEverything\Banshee_5\ui\parts.jsx`

- [ ] **Step 1: Add `RotationSection` function before the `window.MacroSensorCard` line**

Find line 2033 in `parts.jsx` (the comment before `MacroSensorCard`):
```js
/* ── MacroSensorCard — expandable macro sensor display ───────── */
```

Insert the following block **before** that comment:

```jsx
/* ── RotationSection — sector rotation engine panel ─────────── */
function RotationSection({ data, loading }) {
  const sty = {
    wrap:    { marginBottom: 16 },
    header:  { fontSize: 10, color: "var(--ink-4)", letterSpacing: 1, marginBottom: 8, textTransform: "uppercase" },
    summary: { fontSize: 12, color: "var(--ink)", marginBottom: 12, lineHeight: 1.6 },
    muted:   { fontSize: 12, color: "var(--ink-4)", padding: "12px 0" },
    table:   { width: "100%", borderCollapse: "collapse", fontSize: 11 },
    th:      { textAlign: "left",  padding: "4px 6px", fontWeight: 400, color: "var(--ink-4)",
               borderBottom: "1px solid var(--bg-3)" },
    thR:     { textAlign: "right", padding: "4px 6px", fontWeight: 400, color: "var(--ink-4)",
               borderBottom: "1px solid var(--bg-3)" },
    td:      { padding: "4px 6px" },
    tdR:     { padding: "4px 6px", textAlign: "right" },
    alert:   { marginTop: 12, border: "1px solid var(--amber)", borderRadius: 4,
               padding: "10px 12px", background: "rgba(255,160,0,0.05)" },
    alertHd: { fontSize: 10, color: "var(--amber)", fontWeight: 700, marginBottom: 6, letterSpacing: 1 },
    alertRow:{ fontSize: 11, color: "var(--ink)", marginBottom: 3 },
    alertSub:{ fontSize: 11, color: "var(--ink-4)", marginTop: 8, fontStyle: "italic" },
  };

  if (loading) return (
    <div style={sty.wrap}>
      <div style={sty.header}>SECTOR ROTATION ENGINE</div>
      <div style={sty.muted}>◇ LOADING ROTATION DATA...</div>
    </div>
  );

  if (!data || data.error || !data.sectors?.length) return (
    <div style={sty.wrap}>
      <div style={sty.header}>SECTOR ROTATION ENGINE</div>
      <div style={sty.muted}>Rotation data unavailable.</div>
    </div>
  );

  const { sectors, camd_alerts, macro_env } = data;

  // Plain-English summary — no AI, pure string interpolation
  const positive  = sectors.filter(s => s.roc_21 > 0);
  const negative  = sectors.filter(s => s.roc_21 < 0);
  const intoNames = positive.slice(0, 2).map(s => s.name).join(" and ");
  const outNames  = negative.slice(-2).map(s => s.name).reverse().join(" and ");
  let summary;
  if (intoNames && outNames) {
    summary = `Money appears to be flowing INTO ${intoNames}, and OUT OF ${outNames} this month.`;
  } else if (intoNames) {
    summary = `Money appears to be flowing INTO ${intoNames} this month.`;
  } else if (outNames) {
    summary = `Money appears to be flowing OUT OF ${outNames} this month.`;
  } else {
    summary = "Sector flows are mixed with no clear directional trend this month.";
  }

  return (
    <div style={sty.wrap}>
      <div style={sty.header}>SECTOR ROTATION ENGINE</div>
      <div style={sty.summary}>{summary}</div>

      <table style={sty.table}>
        <thead>
          <tr>
            <th style={sty.th}>SECTOR</th>
            <th style={sty.thR}>5D RS</th>
            <th style={sty.thR}>21D RS</th>
            <th style={sty.thR}>FLOW</th>
          </tr>
        </thead>
        <tbody>
          {sectors.map(s => {
            const rowBg = s.roc_21 > 0
              ? "rgba(0,200,100,0.07)"
              : s.roc_21 < 0
              ? "rgba(200,50,50,0.07)"
              : "transparent";
            const r5Arrow = s.roc_5 >= 0 ? "▲" : "▼";
            const r5Color = s.roc_5 >= 0 ? "var(--buy)" : "var(--sell)";
            return (
              <tr key={s.ticker} style={{ background: rowBg, borderBottom: "1px solid rgba(255,255,255,0.03)" }}>
                <td style={{ ...sty.td, color: "var(--ink)" }}>{s.name}</td>
                <td style={{ ...sty.tdR, color: r5Color }}>
                  {r5Arrow}{Math.abs(s.roc_5).toFixed(2)}%
                </td>
                <td style={{ ...sty.tdR, color: s.roc_21 >= 0 ? "var(--buy)" : "var(--sell)" }}>
                  {s.roc_21 >= 0 ? "+" : ""}{s.roc_21.toFixed(2)}%
                </td>
                <td style={sty.tdR}>
                  {s.camd && (
                    <span style={{ color: "var(--buy)", fontSize: 10, fontWeight: 600 }}>◆ CAMD</span>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>

      {camd_alerts?.length > 0 && (
        <div style={sty.alert}>
          <div style={sty.alertHd}>⚡ ROTATION ALERT</div>
          {camd_alerts.map(a => (
            <div key={a.ticker} style={sty.alertRow}>
              {a.ticker} · {a.name} — 21D: +{a.roc_21.toFixed(2)}% · 5D: +{a.roc_5.toFixed(2)}% · Divergence: +{a.divergence_strength.toFixed(2)}
            </div>
          ))}
          {macro_env?.interpretation && (
            <div style={sty.alertSub}>{macro_env.interpretation}</div>
          )}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Register `RotationSection` on window**

Find line 2113:
```js
window.MacroSensorCard = MacroSensorCard;
```

Add the line immediately after:
```js
window.RotationSection = RotationSection;
```

- [ ] **Step 3: Commit**

```bash
cd C:/Users/swyli/AntiEverything/Banshee_5
git add ui/parts.jsx
git commit -m "feat: add RotationSection component to parts.jsx"
```

---

## Task 6: Wire `RotationSection` into MacroPage in `app.jsx`

**Files:**
- Modify: `C:\Users\swyli\AntiEverything\Banshee_5\ui\app.jsx`

- [ ] **Step 1: Add rotation state to MacroPage**

Find this line in `app.jsx` inside `MacroPage`:
```js
const [aiText, setAiText]       = useState(null);
const [aiLoading, setAiLoading] = useState(false);
const [aiError, setAiError]     = useState(null);
```

Add after those lines:
```js
const [rotationData,    setRotationData]    = useState(null);
const [rotationLoading, setRotationLoading] = useState(true);
```

- [ ] **Step 2: Add `useEffect` to fetch rotation data on mount**

Find the closing `}` of the `MacroPage` function's state/hooks block (look for the first `return (` inside `MacroPage`). Insert this `useEffect` before the `return`:

```js
React.useEffect(() => {
  window.API.fetchRotation()
    .then(d  => { setRotationData(d);    setRotationLoading(false); })
    .catch(() =>                          setRotationLoading(false));
}, []);
```

- [ ] **Step 3: Render `RotationSection` below the sensor grid**

Inside the `MacroPage` return JSX, find the `MACRO_SENSOR_ROWS.map(...)` block — it renders the sensor card grid. Find the closing `</div>` after that map. Insert `<window.RotationSection>` immediately after it (before the AI briefing button section):

```jsx
<window.RotationSection data={rotationData} loading={rotationLoading} />
```

- [ ] **Step 4: Hard refresh and verify in browser**

1. Restart Core: kill and relaunch `launch_banshee.bat`
2. Open `http://localhost:8765/ui/` in browser
3. Navigate to MacroPage (the macro sensor view)
4. Hard refresh: `Ctrl+Shift+R`
5. Confirm:
   - "◇ LOADING ROTATION DATA..." appears briefly
   - Replaced by "SECTOR ROTATION ENGINE" header
   - Plain-English summary sentence present
   - 10-row table sorted by 21D RS descending
   - Green/red row tints applied correctly
   - If CAMD conditions met: amber alert banner visible
   - If not: no alert banner (not even an empty card)

- [ ] **Step 5: Commit**

```bash
cd C:/Users/swyli/AntiEverything/Banshee_5
git add ui/app.jsx
git commit -m "feat: wire RotationSection into MacroPage with rotation state + fetch"
```

---

## Task 7: Add rotation context to macro AI briefing

**Files:**
- Modify: `C:\Users\swyli\AntiEverything\Banshee_5\banshee_ai.py` (line 161)
- Modify: `C:\Users\swyli\AntiEverything\Banshee_5\banshee_core.py` (line ~1450)

- [ ] **Step 1: Add `rotation_context` param to `build_macro_prompt()`**

Find line 161 in `banshee_ai.py`:
```python
def build_macro_prompt(macro_data: dict, news_lines: list = []) -> str:
```

Replace with:
```python
def build_macro_prompt(macro_data: dict, news_lines: list = [], rotation_context: str = "") -> str:
```

Find the section that adds news lines (around line 207):
```python
    if news_lines:
        prompt += "\n--- MARKET INTEL ---\n"
        for line in news_lines:
            prompt += f"{line}\n"

    prompt += (
        "\nINSTRUCTION: ...
```

Insert the rotation block between news_lines and the INSTRUCTION line:
```python
    if rotation_context:
        prompt += "\n--- SECTOR ROTATION ---\n"
        prompt += rotation_context + "\n"
```

- [ ] **Step 2: Build rotation context string in `route_ai_briefing` macro branch**

Find lines 1441-1451 in `banshee_core.py`:
```python
    if req.tab == "macro":
        mac_data, _src = _get_sensors()
        cached         = _load_macro_cache()
        news_lines     = cached.get("news_lines", []) if cached else []
        predator_brief = predator_engine.load_latest_briefing()
        predator_lines = predator_engine.get_briefing_for_nexus(predator_brief)
        if predator_lines:
            news_lines = [predator_lines] + news_lines
        prompt = banshee_ai.build_macro_prompt(mac_data, news_lines)
        return banshee_ai.call_ai(cfg, prompt)
```

Replace with:
```python
    if req.tab == "macro":
        mac_data, _src = _get_sensors()
        cached         = _load_macro_cache()
        news_lines     = cached.get("news_lines", []) if cached else []
        predator_brief = predator_engine.load_latest_briefing()
        predator_lines = predator_engine.get_briefing_for_nexus(predator_brief)
        if predator_lines:
            news_lines = [predator_lines] + news_lines

        # Build rotation context (non-blocking — fails silently)
        rotation_ctx = ""
        try:
            closes = fetch_sector_closes()
            if not closes.empty:
                rot = sector_rotation_engine.run(closes, providers.get("FRED_API", {}).get("key"))
                if rot.get("sectors"):
                    top  = [s for s in rot["sectors"] if s["roc_21"] > 0][:3]
                    bot  = [s for s in rot["sectors"] if s["roc_21"] < 0][-2:]
                    top_lines = [
                        f"{s['name']} ({s['roc_21']:+.1f}% 21D RS{' CAMD' if s['camd'] else ''})"
                        for s in top
                    ]
                    rotation_ctx = "Top flow: " + ", ".join(top_lines)
                    if bot:
                        rotation_ctx += "\nWeakest: " + ", ".join(
                            f"{s['name']} ({s['roc_21']:+.1f}% 21D RS)" for s in bot
                        )
                    if rot.get("macro_env") and rot["macro_env"].get("interpretation"):
                        rotation_ctx += f"\n{rot['macro_env']['interpretation']}"
        except Exception:
            pass

        prompt = banshee_ai.build_macro_prompt(mac_data, news_lines, rotation_context=rotation_ctx)
        return banshee_ai.call_ai(cfg, prompt)
```

- [ ] **Step 3: Verify AI briefing still works**

1. Open MacroPage in the browser
2. Click the macro AI briefing button
3. Confirm it returns a briefing (no crash)
4. If sectors are flowing, the AI response should mention sector rotation in point 4 (Positioning Implications)

- [ ] **Step 4: Commit**

```bash
cd C:/Users/swyli/AntiEverything/Banshee_5
git add banshee_ai.py banshee_core.py
git commit -m "feat: inject sector rotation context into macro AI briefing"
```

---

## Self-Review Checklist

- [x] **Spec coverage:** Engine (run, CRS, ROC, CAMD, graceful error) ✓ — fetch adapter (fetch_sector_closes, ttl=14400) ✓ — endpoint (GET /rotation, error shape) ✓ — api.js (fetchRotation) ✓ — RotationSection (summary, table, CAMD banner, loading) ✓ — macro AI briefing (rotation_context) ✓
- [x] **Placeholders:** None found. All code blocks are complete.
- [x] **Type consistency:** `sectors` array shape defined in Task 1, used identically in Task 5. `fred_key` always `str | None`. `fetch_sector_closes` imported in both Task 2 (defined) and Task 3 (imported in Core). `rotation_context: str = ""` defined in Task 7 step 1 matches call site in step 2.
- [x] **One gap found and added:** `fetch_sector_closes` must be added to the `from shared_data import ...` line in Task 3 step 1 — already covered.
