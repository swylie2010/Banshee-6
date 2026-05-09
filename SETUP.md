# Banshee Pro — New Machine Setup Guide
*For the AI assistant helping with this: read this first.*

---

## What This Is

Banshee Pro is a unified trading command center that combines:
- **Macro engine** — VIX, yield curve, Fed liquidity, 12 sensors, regime scoring (CLEAR / CAUTION / CRACK)
- **Micro engine** — EMA stack, Supertrend, Stoch RSI, VWAP, OBV, ATR trade plans, funding rate
- **Streamlit UI** — 4 tabs: Macro Weather | Asset Radar | Banshee Nexus | Market Intel
- **MCP server** — 5 tools Claude Code can call directly (the hard part to set up)

The owner is not technical. Your job is to get this running with minimal friction.

---

## Files in This Folder

| File | Purpose |
|------|---------|
| `app.py` | Streamlit UI — run this to launch the dashboard |
| `macro_engine.py` | Macro regime engine |
| `micro_engine.py` | Technical analysis engine |
| `shared_data.py` | Shared data fetchers: yfinance (stocks), Coinbase/Binance via ccxt (crypto) |
| `banshee_ai.py` | AI synthesis prompt builder |
| `mcp_server.py` | MCP server (stdio transport) — Claude Code calls this |
| `launch_banshee.bat` | Windows shortcut to launch the Streamlit UI |

---

## Step 1 — Install Dependencies

```bash
pip install streamlit yfinance ccxt pandas numpy anthropic
```

---

## Step 2 — Launch the UI (optional but useful to verify)

**Windows:**
```
Double-click launch_banshee.bat
```
**Mac/Linux:**
```bash
cd /path/to/Banshee_Pro
streamlit run app.py
```

First launch: enter FRED API key and AI API key in the sidebar. They save to `~/.banshee_keys.json`.

---

## Step 3 — Register the MCP Server (the critical part)

This is what lets Claude Code use Banshee's 5 tools directly in conversation.

There are **TWO files** that must both be updated. Claude Code checks both:

### File 1: `~/.claude/.mcp.json`
### File 2: `~/.mcp.json`

Both files should contain the same content:

**Windows:**
```json
{
  "mcpServers": {
    "banshee-pro": {
      "command": "python",
      "args": ["C:/Users/YOUR_USERNAME/path/to/Banshee_Pro/mcp_server.py"]
    }
  }
}
```

**Mac/Linux:**
```json
{
  "mcpServers": {
    "banshee-pro": {
      "command": "python3",
      "args": ["/Users/YOUR_USERNAME/path/to/Banshee_Pro/mcp_server.py"]
    }
  }
}
```

Use the **actual absolute path** to `mcp_server.py` on this machine.
Use forward slashes even on Windows.
Transport is stdio — no server needs to be pre-running. Claude Code spawns it automatically.

---

## Step 4 — Verify It's Working

Start a new Claude Code session and run all 5 tools:

1. `get_macro_weather` — no arguments needed
2. `read_market_intel` — no arguments needed
3. `get_asset_radar("BTC/USD", "swing")`
4. `scan_assets(["BTC/USD", "ETH/USD", "SPY"], "swing")`
5. `synthesize_nexus("BTC/USD", "swing", use_ai=False)`

If the MCP tools don't appear, the most common cause is that only one of the two `.mcp.json` files was updated. Check both.

---

## MCP Tool Reference

| Tool | What it does | Key args |
|------|-------------|----------|
| `get_macro_weather` | Global macro regime snapshot | none |
| `read_market_intel` | Live RSS headlines + event keywords | none |
| `get_asset_radar` | Full technical analysis for one symbol | `symbol`, `mode` |
| `scan_assets` | Ranked leaderboard across a watchlist | `symbols[]`, `mode` |
| `synthesize_nexus` | Top-down AI briefing: macro + micro + news | `symbol`, `mode`, `use_ai` |

**Mode options:** `"swing"` (default), `"long_term"`, `"sniper"`
**Crypto symbols:** `"BTC/USD"`, `"ETH/USD"`, `"SOL/USD"`, `"SUI/USD"`, `"XRP/USD"`
**Stock symbols:** `"NVDA"`, `"SPY"`, `"AAPL"`, `"TSLA"`
**Futures:** `"GC=F"` (gold), `"CL=F"` (oil)

---

## Data Sources

- **Stocks/ETFs/Futures:** Yahoo Finance (yfinance)
- **Crypto OHLCV:** Coinbase (primary) → Yahoo Finance fallback
- **Crypto funding rate:** Binance perpetual futures (ccxt binanceusdm)
- **Macro data:** FRED API (Fed liquidity), yfinance (VIX, SPY, HYG, etc.), RSS feeds

No paid data subscriptions required. FRED API key is free at fred.stlouisfed.org.

---

## Keys File

`~/.banshee_keys.json` stores:
- `FRED_API` — macroeconomic data (free from FRED)
- `AI_API` — Claude or Gemini key for the Nexus AI briefing

Enter these in the Streamlit sidebar on first launch, or copy the file from the old machine.

---

*Banshee Pro v1.6 — built on this machine, designed to travel.*
