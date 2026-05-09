# Banshee Pro 4 — Architecture

## Three-Layer Design (all complete as of 2026-04-27)

```
┌─────────────────────────────────────────┐
│  Streamlit UI  (app.py — display only)  │
│  HTTP client → Core. No engine imports. │
└────────────────┬────────────────────────┘
                 │ HTTP
┌────────────────▼────────────────────────┐
│  FastAPI Core  (banshee_core.py :8765)  │
│  Owns cache, calls engines, runs 24/7   │
└────────────────┬────────────────────────┘
                 │ Python calls
┌────────────────▼────────────────────────┐
│  Engines  (pure Python, no Streamlit)   │
│  macro · micro · smc · shared_data      │
└─────────────────────────────────────────┘
        ↑ also consumed by
┌───────────────────────────────────────┐
│  MCP Server  (mcp_server.py — stdio)  │
│  Thin proxy: MCP call → Core HTTP     │
│  Claude spawns on demand              │
└───────────────────────────────────────┘
```

**Key principle:** Human (Streamlit) and AI (MCP) are equal consumers of the same Core. Neither is privileged. One cache, one source of truth.

## Ports & Launch

| Process | Port | Started by |
|---------|------|-----------|
| FastAPI Core | 8765 | `launch_banshee.bat` (first, minimized) |
| Streamlit UI | dynamic | `launch_banshee.bat` (3s after Core) |
| MCP Server | stdio | Claude Code auto-spawns |

## Key Files

| File | Role |
|------|------|
| `banshee_core.py` | FastAPI Core — 12 HTTP endpoints, unified cache, engine orchestration |
| `mcp_server.py` | MCP thin proxy — ~130 lines, calls Core via HTTP |
| `app.py` | Streamlit UI — display only, calls Core via HTTP |
| `macro_engine.py` | VIX, yield curve, Fed liquidity, RSS feeds, regime scoring |
| `micro_engine.py` | EMA stack, Stoch RSI, VWAP, Supertrend, funding rate, ATR trade plan |
| `smc_engine.py` | SMC: swings, BOS/CHoCH, FVGs, order blocks, PD zones, inducement |
| `structure_map.py` | Structure Map tab — standalone Plotly chart, own symbol/TF selectors |
| `knowledge_graph.py` | Domino State, Asset Safety (Bouncer), contradiction detector |
| `risk_engine.py` | Position sizing: units, R-targets, leverage/margin table |
| `shared_data.py` | Unified data fetchers — Coinbase/YF/TV fallback chain |
| `cache_utils.py` | `ttl_cache(ttl=N)` — replaces `@st.cache_data`, zero Streamlit dependency |
| `paper_trader.py` | Paper Trade Journal — bracket orders, sync, outcome logging |
| `predator_engine.py` | Daily Predator — RSS intake, Bouncer filter, briefing output |
| `banshee_ai.py` | AI prompt builder + call wrapper (Claude or Gemini) |
| `strategy_lab.py` | Signal Lab — MTF backtest, Discovery, Saved Results |
| `asset_profiles.py` | Asset class system — presets, weights, gate flags |
| `calibrate.py` | One-command calibration runner: `python calibrate.py NVDA long_term` |
| `launch_banshee.bat` | Windows startup: Core (minimized) → Streamlit |

## MCP Config (both files must match)

`~/.claude/.mcp.json` AND `~/.mcp.json`:
```json
{
  "mcpServers": {
    "banshee-pro": {
      "command": "python",
      "args": ["C:/Users/swyli/AntiEverything/Banshee_Pro_4/mcp_server.py"]
    },
    "tradingview": {
      "command": "node",
      "args": ["C:/Users/swyli/tradingview-mcp-jackson/src/server.js"]
    }
  }
}
```

## MCP Tools (12)

`get_macro_weather`, `read_market_intel`, `get_regime`, `get_watchlist`, `get_asset_radar`, `scan_assets`, `synthesize_nexus`, `build_execution_plan`, `get_strategy_results`, `get_smc_structure`, `log_signal_outcome`, `get_signal_log`

## Mode Names

| Label | Key | Timeframes |
|-------|-----|-----------|
| Long Term | `long_term` | 1wk / 1d / 4h |
| Swing | `swing` | 1d / 4h / 1h |
| Sniper | `sniper` | 4h / 1h / 15m |

Aliases: `"active"` → swing, `"position"` → long_term

## Keys File

`~/.banshee_keys.json` — FRED API key + AI API key (Claude or Gemini). Set via Streamlit sidebar Settings tab.
