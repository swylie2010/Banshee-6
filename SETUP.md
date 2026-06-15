# Banshee 6 — Setup Guide

Banshee 6 is a trading analysis tool that runs on your computer. It watches the markets, spots patterns that big institutions leave behind in price data, and gives you plain-English explanations of what it sees. It does not place trades — that's always your call.

---

## Before You Start

You need two free programs installed on your computer:

**Python 3.10 or newer**
Download from [python.org](https://python.org). During install, check the box that says **"Add Python to PATH"** — this is easy to miss and causes problems later if skipped.

**Node.js (any recent version)**
Download from [nodejs.org](https://nodejs.org). Just run the installer, no special options needed.

To check if both are already installed, open a terminal and run:
```
python --version
node --version
```
Both should show a version number. If either says "not found", install it first.

---

## Step 1 — Launch Banshee

Double-click `launch_banshee.bat` in the Banshee folder.

That's it. The launcher handles everything automatically:
- Creates a private Python environment so Banshee's packages don't interfere with anything else on your computer
- Installs all required packages (this takes a few minutes on the very first run)
- Builds the web UI
- Starts the Banshee server
- Opens the UI in your browser at `http://localhost:8765/ui/`

On the first launch, you'll see a disclaimer screen — read it and click through. Then you'll see a 4-digit PIN screen. You can set your own PIN or skip it for now in Settings later.

---

## Step 2 — Add Your API Keys

Banshee needs a couple of free API keys to pull in real data. Go to **Settings** in the sidebar (gear icon) and enter them there.

**FRED API key** — for economic data (interest rates, liquidity, etc.)
Get one free at [fred.stlouisfed.org/docs/api/api_key.html](https://fred.stlouisfed.org/docs/api/api_key.html). Takes about 60 seconds.

**AI brain** — Banshee can use several AI providers for its written analysis. Pick one:
- **Google Gemini** — get a free key at [aistudio.google.com](https://aistudio.google.com)
- **Anthropic Claude** — get a key at [console.anthropic.com](https://console.anthropic.com)
- **OpenAI** — get a key at [platform.openai.com](https://platform.openai.com)
- **Ollama** — runs AI on your own computer, no key needed. Install from [ollama.com](https://ollama.com) and set the URL to `http://localhost:11434`

**Alpaca** (optional) — only needed if you want to use the paper options trading feature. Get a free paper trading account at [alpaca.markets](https://alpaca.markets). Banshee only ever uses the paper (fake money) endpoint.

**CoinGecko** (optional) — a free demo key raises rate limits for crypto price lookups. Get one at [coingecko.com/api](https://www.coingecko.com/en/api). In Settings → DATA SOURCES, enter the key and leave the selector on **demo**.

All keys are stored in a file on your computer called `~/.banshee_keys.json` — they never leave your machine.

---

## Step 3 — Set Up the MCP Server (optional but powerful)

This step lets Claude Code talk to Banshee directly — you can ask Claude questions and it will pull live data from Banshee to answer them.

You need to add Banshee to **two** config files. Claude Code checks both, so if you only update one it won't work.

Open (or create) these two files:
- `C:\Users\YOUR_USERNAME\.claude\.mcp.json`
- `C:\Users\YOUR_USERNAME\.mcp.json`

Both files need the same content:

```json
{
  "mcpServers": {
    "banshee-pro": {
      "command": "C:/Users/YOUR_USERNAME/AntiEverything/Banshee_6/.venv/Scripts/python.exe",
      "args": ["C:/Users/YOUR_USERNAME/AntiEverything/Banshee_6/mcp_server.py"]
    }
  }
}
```

Replace `YOUR_USERNAME` with your actual Windows username. Use forward slashes, not backslashes.

Restart Claude Code after saving. You'll know it worked when you can see "banshee-pro" listed in Claude Code's MCP panel, or when Claude responds to questions with live Banshee data.

---

## MCP Tools Available

Once the MCP server is connected, Claude Code has access to these Banshee tools:

| Tool | What it does |
|------|-------------|
| `get_macro_weather` | Global macro regime — is the market in risk-on or risk-off mode? |
| `get_asset_radar` | Full technical analysis for one symbol |
| `scan_assets` | Ranked analysis across your whole watchlist |
| `synthesize_nexus` | Top-down AI briefing: macro + structure + signals combined |
| `get_smc_structure` | Raw Smart Money Concepts data for a symbol |
| `build_execution_plan` | Position sizing and entry/exit levels for a trade idea |
| `get_geo_harmonic` | Geometric Harmonic arc levels (key price zones) |
| `get_options_candidate` | Best cash-secured put candidate from the options universe |
| `get_paper_wheels` | Status of your paper options wheel trades |
| `check_kill_switch` | Whether any open trades have hit their loss limit |

---

## Stopping Banshee

Click the **⏻ STOP BANSHEE** button in the sidebar. This shuts down the server cleanly. Don't just close the browser tab — the server keeps running in the background until you stop it properly.

To restart, just double-click `launch_banshee.bat` again.

---

## Troubleshooting

**"Port 8765 already in use"** — A previous Banshee session is still running. Open PowerShell and run `stop_banshee.ps1`, or restart your computer.

**UI shows but data won't load** — Check the Settings page. You probably have a missing or incorrect API key.

**MCP tools not showing up in Claude Code** — Make sure you updated *both* `.mcp.json` files (see Step 3) and restarted Claude Code.

**npm errors during launch** — Node.js probably isn't installed, or the install didn't finish. Re-install Node.js and try again.

**Python not found** — During Python install you need to check "Add Python to PATH". Uninstall Python and reinstall with that box checked.
