# GH Pine Script Generator — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `generate_pine_script()` to the GH engine, expose it via a REST endpoint + MCP tool, and add a PINE button on the GH tab in the React UI that renders a copyable code block.

**Architecture:** `generate_pine_script(result, symbol)` lives in `geometric_harmonic.py` alongside `run()` and `format_human()`. `GET /geo-harmonic/pine` in `banshee_core.py` calls `run()` then the generator. MCP tool `generate_gh_pine` and the React UI both call this same endpoint. All anchor values are hardcoded in the generated script — paste and run, no manual entry required.

**Tech Stack:** Python 3, FastAPI, Pine Script v5 (generated string), React (Babel standalone), `test_banshee.py` custom harness.

---

### Task 1: `generate_pine_script()` — engine function + tests

**Files:**
- Modify: `geometric_harmonic.py` (append after `format_human()`, after line 415)
- Modify: `test_banshee.py` (insert before `# --- Summary ---`, before line 600)

- [ ] **Step 1: Write failing tests in `test_banshee.py`**

Insert before the `# --- Summary ---` block (line 600):

```python

# --- 6. generate_pine_script ------------------------------------------------

print("\n--- 6. generate_pine_script -------------------------------------------------")

def _pine_valid_result():
    import geometric_harmonic as gh
    import numpy as np
    import pandas as pd
    np.random.seed(42)
    n = 200
    p = 10000.0 * np.cumprod(1 + np.random.normal(0, 0.01, n))
    p[50]  = p[:50].min()  * 0.85
    p[150] = p[100:].max() * 1.15
    df = pd.DataFrame({
        "timestamp": pd.date_range("2021-01-01", periods=n, freq="D"),
        "open":  p, "high": p * 1.01, "low": p * 0.99,
        "close": p, "volume": np.ones(n) * 1000,
    })
    result = gh.run(df, multi_window=True)
    assert "error" not in result, f"run() failed: {result}"
    script = gh.generate_pine_script(result, symbol="TEST/USD")
    assert isinstance(script, str)
    assert script.startswith("//@version=5")
    assert "TEST/USD" in script
    assert str(result["sc_macro"]) in script
    assert "barstate.islast" in script
    n_calls = script.count("draw_circle(")
    assert n_calls == len(result["gh_circles"]), \
        f"expected {len(result['gh_circles'])} draw_circle calls, got {n_calls}"
    assert "polyline.new(" in script

def _pine_error_result():
    import geometric_harmonic as gh
    script = gh.generate_pine_script({"error": "No data"})
    assert script.startswith("//@version=5")
    assert 'runtime.error("No data")' in script

def _pine_no_symbol():
    import geometric_harmonic as gh
    import numpy as np, pandas as pd
    np.random.seed(7)
    n = 150
    p = 100.0 * np.cumprod(1 + np.random.normal(0, 0.01, n))
    df = pd.DataFrame({
        "timestamp": pd.date_range("2022-01-01", periods=n, freq="D"),
        "open": p, "high": p*1.01, "low": p*0.99,
        "close": p, "volume": np.ones(n)*1000,
    })
    result = gh.run(df, multi_window=True)
    script = gh.generate_pine_script(result)
    assert "UNKNOWN" in script

_test("pine: valid result → correct Pine structure",  _pine_valid_result)
_test("pine: error result → error Pine script",        _pine_error_result)
_test("pine: no symbol → UNKNOWN in title",            _pine_no_symbol)
```

- [ ] **Step 2: Run tests — confirm 3 new FAILs**

```bash
cd ~/AntiEverything/Banshee_5
python test_banshee.py 2>&1 | tail -15
```

Expected: 3 FAILs — `AttributeError: module 'geometric_harmonic' has no attribute 'generate_pine_script'`

- [ ] **Step 3: Implement `generate_pine_script()` in `geometric_harmonic.py`**

Append after the last line of `format_human()` (after line 415):

```python


def generate_pine_script(result: dict, symbol: str = "") -> str:
    """
    Generate a paste-ready Pine Script v5 indicator that draws Banshee's GH
    Fibonacci arc circles on a TradingView 1D chart as polylines.

    6 Fib levels: 0.382, 0.500, 0.618, 0.786, 1.000, 1.618.
    60 points per arc. Teal = floor support, red = ceiling resistance.
    Macro anchors at 20% transparency, local ZigZag pivots at 60%.

    WARNING: 1D chart only. Bar-index math assumes daily spacing.
    Re-generate after significant price moves.
    """
    if "error" in result:
        err = result["error"].replace('"', '\\"')
        return (
            "//@version=5\n"
            'indicator("Banshee GH — ERROR", overlay=true)\n'
            f'runtime.error("{err}")\n'
        )

    from datetime import date as _date

    sc_macro  = result["sc_macro"]
    t_now     = result["radius_endpoint"]["bar"]
    circles   = result.get("gh_circles", [])
    anchors   = result.get("anchors", {})
    atl       = anchors.get("ATL", {})
    ath       = anchors.get("ATH", {})
    sym_label = (symbol or "UNKNOWN").replace('"', '\\"')
    today     = _date.today().isoformat()

    call_lines: list = []
    for c in circles:
        bars_ago = int(round(t_now - c["cx_bar"]))
        cp       = c["center_price"]
        r_base   = c["r_base"]
        clr      = "color.teal" if c["origin"] == "floor" else "color.red"
        transp   = "20" if "macro" in c["source"] else "60"
        label    = c["label"]
        call_lines.append(
            f'    draw_circle({bars_ago}, {cp}, {r_base}, {clr}, {transp})  // {label}'
        )

    calls = "\n".join(call_lines) if call_lines else "    // no circles computed"

    return "\n".join([
        "//@version=5",
        f'indicator("Banshee GH — {sym_label}", overlay=true, max_polylines_count=100)',
        f"// Generated: {today} | Symbol: {sym_label}",
        f"// ATL: {str(atl.get('ts', '?'))[:10]} @ {atl.get('price', 0)}"
        f"  |  ATH: {str(ath.get('ts', '?'))[:10]} @ {ath.get('price', 0)}",
        "// WARNING: 1D CHART ONLY — log scale recommended",
        "",
        "// Hardcoded parameters — regenerate from Banshee when price moves significantly",
        f"SC_MACRO   = float({sc_macro})",
        "FIB_RATIOS = array.from(0.382, 0.500, 0.618, 0.786, 1.000, 1.618)",
        "N_PTS      = 60",
        "",
        "// bars_ago: daily bars before today the anchor sits",
        "// cp: anchor price | r_base: base radius in normalized log space",
        "// clr: teal=floor support, red=ceiling resistance",
        "// transp: 20=macro anchor, 60=local ZigZag pivot",
        "draw_circle(int bars_ago, float cp, float r_base, color clr, int transp) =>",
        "    cy_norm = math.log(cp) / SC_MACRO",
        "    for fi = 0 to array.size(FIB_RATIOS) - 1",
        "        fib   = array.get(FIB_RATIOS, fi)",
        "        r_fib = r_base * fib",
        "        pts   = array.new<chart.point>()",
        "        for i = 0 to N_PTS - 1",
        "            theta  = float(i) / float(N_PTS) * 2.0 * math.pi",
        "            x_abs  = int(math.round(float(bar_index - bars_ago) + r_fib * math.cos(theta)))",
        "            y_norm = cy_norm + r_fib * math.sin(theta)",
        "            price  = math.exp(y_norm * SC_MACRO)",
        "            if x_abs >= 0 and price > 0.0",
        "                array.push(pts, chart.point.from_index(x_abs, price))",
        "        if array.size(pts) > 1",
        "            polyline.new(pts, curved=false,",
        "                         line_color=color.new(clr, transp),",
        "                         line_width=1)",
        "",
        "if barstate.islast",
        calls,
    ]) + "\n"
```

- [ ] **Step 4: Run tests — all 3 new tests should pass**

```bash
cd ~/AntiEverything/Banshee_5
python test_banshee.py 2>&1 | tail -15
```

Expected: `PASS  pine: valid result → correct Pine structure`, `PASS  pine: error result → error Pine script`, `PASS  pine: no symbol → UNKNOWN in title`. All prior tests still green.

- [ ] **Step 5: Commit**

```bash
cd ~/AntiEverything/Banshee_5
git add geometric_harmonic.py test_banshee.py
git commit -m "$(cat <<'EOF'
feat: add generate_pine_script() to geometric_harmonic engine

Generates paste-ready Pine Script v5 indicator — GH Fibonacci arc
circles as 60-pt polylines, 6 Fib levels, teal/red color scheme.
Includes 3 unit tests.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: `GET /geo-harmonic/pine` endpoint + `fetchGHPine()` in api.js

**Files:**
- Modify: `banshee_core.py` (insert after line 1948, after closing of `route_geo_harmonic`)
- Modify: `ui/api.js` (insert after `fetchGH` at line 150; update exports at line 355)

- [ ] **Step 1: Add endpoint to `banshee_core.py`**

Insert after line 1948 (the blank line after `route_geo_harmonic`'s `return` statement):

```python

@app.get("/geo-harmonic/pine")
def route_geo_harmonic_pine(
    symbol:         str  = Query(...),
    arithmetic_mid: bool = Query(False),
    multi_window:   bool = Query(True),
):
    """
    Generate a paste-ready Pine Script v5 indicator for GH circles.
    Returns {"symbol": ..., "pine_script": "..."}.
    Paste the pine_script into TradingView's Pine Editor on a 1D chart.
    """
    import geometric_harmonic as gh
    tfs = _get_ohlcv_cached(symbol, "swing")
    if not tfs or "error" in tfs:
        return JSONResponse(content={"error": f"Failed to load data for {symbol}"})
    df = tfs.get("1d")
    if df is None or (hasattr(df, "empty") and df.empty):
        valid = [k for k, v in tfs.items() if isinstance(v, pd.DataFrame) and not v.empty]
        if not valid:
            return JSONResponse(content={"error": f"No data for {symbol}"})
        df = tfs[valid[0]]
    result = gh.run(df, arithmetic_mid=arithmetic_mid, multi_window=multi_window)
    if "error" in result:
        return JSONResponse(content={"error": result["error"]})
    pine = gh.generate_pine_script(result, symbol=symbol)
    return JSONResponse(content={"symbol": symbol, "pine_script": pine})
```

- [ ] **Step 2: Add `fetchGHPine()` to `ui/api.js`**

Insert after the closing brace of `fetchGH` (after line 150):

```javascript

/* generate Pine Script v5 indicator for GH circles — returns {pine_script: "..."} */
async function fetchGHPine(sym) {
  const pair = coreSymbol(sym);
  try {
    const res = await fetch(`${API_BASE}/geo-harmonic/pine?symbol=${encodeURIComponent(pair)}&multi_window=true`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (err) {
    console.warn(`[api] GH Pine fallback for ${sym}:`, err.message);
    return { error: err.message };
  }
}
```

- [ ] **Step 3: Export `fetchGHPine` from `api.js`**

Replace the existing `window.API = { ... }` line (line 355) with:

```javascript
window.API = { fetchOHLCV, fetchRadar, fetchMacro, fetchSMC, fetchPresets, fetchGH, fetchGHPine, fetchXABCD, fetchAIBriefing, fetchSettings, saveSettings, testAIConnection, fetchStrategies, fetchExecutionPlan, fetchTrades, closeTrade, updateLevels, updateOutcome, syncAlpaca, fetchFeedbackSynthesis, fetchPredatorBriefing, runPredator, coreSymbol };
```

- [ ] **Step 4: Smoke test the endpoint**

Ensure Core is running at `http://localhost:8765/health`, then:

```bash
curl "http://localhost:8765/geo-harmonic/pine?symbol=BTC%2FUSD" 2>/dev/null | python -c "import sys,json; d=json.load(sys.stdin); s=d.get('pine_script','ERROR'); print(s[:300] if s != 'ERROR' else d)"
```

Expected: first 300 chars of Pine Script starting with `//@version=5` and containing `SC_MACRO`

- [ ] **Step 5: Commit**

```bash
cd ~/AntiEverything/Banshee_5
git add banshee_core.py ui/api.js
git commit -m "$(cat <<'EOF'
feat: add GET /geo-harmonic/pine endpoint and fetchGHPine() in api.js

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: MCP tool `generate_gh_pine` in `mcp_server.py`

**Files:**
- Modify: `mcp_server.py` (insert after `get_geo_harmonic()`, after line 473)

- [ ] **Step 1: Add the MCP tool**

Insert after line 473 (after the closing of `get_geo_harmonic`):

```python


@mcp.tool()
def generate_gh_pine(symbol: str, arithmetic_mid: bool = False) -> str:
    """
    Generate a paste-ready Pine Script v5 indicator that draws Banshee's
    Geo Harmonic Fibonacci arc circles on a TradingView 1D chart.

    Draws all GH circles at 6 Fib levels (0.382, 0.5, 0.618, 0.786, 1.0, 1.618)
    as 60-point polylines. Teal = floor support, red = ceiling resistance.
    Macro anchors (ATL/ATH) at 20% transparency, local ZigZag pivots at 60%.

    Paste the returned script into TradingView's Pine Editor and run it on a 1D
    chart. Log scale is recommended. Values are baked in — re-run after
    significant price moves.

    Args:
        symbol:         Ticker — crypto 'BTC/USD', stocks 'NVDA', futures 'GC=F'.
        arithmetic_mid: Use (ATH+ATL)/2 as radius endpoint instead of √(ATH×ATL).

    Returns: Complete Pine Script v5 string ready to paste into TradingView.
    """
    import json
    raw = _get("/geo-harmonic/pine", symbol=symbol, arithmetic_mid=arithmetic_mid)
    try:
        data = json.loads(raw)
        if "error" in data:
            return f"GH PINE ERROR: {data['error']}"
        return data.get("pine_script", raw)
    except Exception:
        return raw
```

- [ ] **Step 2: Verify no import errors**

```bash
cd ~/AntiEverything/Banshee_5
python -c "import mcp_server; print('MCP import OK')"
```

Expected: `MCP import OK`

- [ ] **Step 3: Commit**

```bash
cd ~/AntiEverything/Banshee_5
git add mcp_server.py
git commit -m "$(cat <<'EOF'
feat: add generate_gh_pine MCP tool

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: UI — PINE button + code block on GH tab

**Files:**
- Modify: `ui/app.jsx` (three edits: state declarations, symbol-change reset, PINE panel)

- [ ] **Step 1: Add pine state variables**

Find (around line 1041):
```javascript
const [ghData, setGhData]         = useState(null);
const [ghLoading, setGhLoading]   = useState(false);
```

Insert immediately after those two lines:
```javascript
const [pineScript, setPineScript]   = useState(null);
const [pineLoading, setPineLoading] = useState(false);
const [pineError, setPineError]     = useState(null);
```

- [ ] **Step 2: Reset pine state when symbol changes**

Find the `useEffect` that resets SMC/GH state on `asset.sym` change. It will contain calls like `setSmcData(null)` and `setGhData(null)`. Add these three lines inside the same effect body:

```javascript
setPineScript(null); setPineLoading(false); setPineError(null);
```

- [ ] **Step 3: Add the PINE panel**

Find line 1264:
```javascript
{tab === "smc" && smcData && !smcData.error && <window.SMCLegend />}
```

Insert immediately after it:
```javascript
{tab === "gh" && (
  <div style={{ padding: "14px 14px 0 14px" }}>
    <div style={{ background: "var(--bg-2)", border: "1px solid var(--line)", borderLeft: "3px solid var(--amber)" }}>
      <div style={{ padding: "12px 16px", borderBottom: "1px solid var(--line)", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <window.Label color="var(--amber)">PINE SCRIPT GENERATOR</window.Label>
        <button
          onClick={() => {
            if (pineLoading) return;
            setPineLoading(true); setPineError(null); setPineScript(null);
            window.API.fetchGHPine(asset.sym)
              .then(d => {
                if (d.error) { setPineError(d.error); }
                else { setPineScript(d.pine_script); }
              })
              .catch(e => setPineError(e.message))
              .finally(() => setPineLoading(false));
          }}
          disabled={pineLoading}
          style={{
            padding: "7px 16px",
            background: pineScript ? "rgba(245,158,11,0.1)" : "transparent",
            border: "1px solid " + (pineScript ? "var(--amber)" : "var(--line-2)"),
            color: pineLoading ? "var(--wait)" : "var(--amber)",
            cursor: pineLoading ? "default" : "pointer",
            fontFamily: "'JetBrains Mono', monospace",
            fontSize: 12, letterSpacing: "0.16em", fontWeight: 700,
          }}>
          {pineLoading ? "◇ GENERATING…" : pineScript ? "◆ REGENERATE" : "◆ GENERATE PINE SCRIPT"}
        </button>
      </div>
      {(pineScript || pineError) && (
        <div style={{ padding: "12px 16px" }}>
          {pineError && (
            <div style={{ fontSize: 12, color: "var(--sell)", letterSpacing: "0.06em" }}>⚠ {pineError}</div>
          )}
          {pineScript && (
            <div>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8 }}>
                <span className="mono" style={{ fontSize: 11, color: "var(--ink-4)", letterSpacing: "0.1em" }}>
                  PASTE INTO TRADINGVIEW PINE EDITOR · 1D CHART ONLY
                </span>
                <button
                  onClick={() => navigator.clipboard.writeText(pineScript)}
                  style={{
                    padding: "4px 12px",
                    background: "var(--bg-3)",
                    border: "1px solid var(--line-2)",
                    color: "var(--ink-2)",
                    cursor: "pointer",
                    fontFamily: "'JetBrains Mono', monospace",
                    fontSize: 11, letterSpacing: "0.12em",
                  }}>
                  COPY
                </button>
              </div>
              <pre style={{
                margin: 0, padding: "10px 12px",
                background: "var(--bg-3)", border: "1px solid var(--line-2)",
                fontSize: 11, color: "var(--ink-2)",
                fontFamily: "'JetBrains Mono', monospace",
                lineHeight: 1.6, overflowX: "auto",
                maxHeight: 280, overflowY: "auto", whiteSpace: "pre",
              }}>
                {pineScript}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  </div>
)}
```

- [ ] **Step 4: Test in browser**

1. Start Core if not running: `python banshee_core.py` (from `~/AntiEverything/Banshee_5`)
2. Open `http://localhost:8765/ui/` — hard-refresh with `Ctrl+Shift+R`
3. Click any asset → open detail view → click **GH** tab
4. Scroll below the chart — confirm "PINE SCRIPT GENERATOR" amber panel is visible
5. Click **◆ GENERATE PINE SCRIPT** — button shows `◇ GENERATING…` during fetch
6. Confirm code block appears with a scrollable `<pre>` and COPY button
7. Click COPY — paste into a text editor, confirm script starts with `//@version=5`
8. Confirm script contains `draw_circle(` calls and `SC_MACRO`
9. Switch to a different asset — confirm the pine panel resets (no stale code block)

- [ ] **Step 5: Commit**

```bash
cd ~/AntiEverything/Banshee_5
git add ui/app.jsx
git commit -m "$(cat <<'EOF'
feat: add PINE button and code block panel to GH tab in React UI

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```
