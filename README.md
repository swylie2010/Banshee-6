# Banshee 6

[![Buy Me A Coffee](https://www.buymeacoffee.com/assets/img/custom_images/orange_img.png)](https://buymeacoffee.com/sowily)

A trading analysis tool that runs entirely on your computer. Banshee watches the markets, spots the footprints that institutional money leaves behind in price data, and gives you plain-English explanations of what it sees. It does not place trades — that's always your call.

---

## What It Does

- **Smart Money Concepts** — detects order blocks, fair value gaps, break-of-structure, and liquidity sweeps across your watchlist
- **Macro regime** — tracks Fed liquidity, interest rate posture, and economic conditions to tell you whether the market is risk-on or risk-off
- **Options analysis** — screens for Wheel strategy candidates (cash-secured puts), tracks paper trades, and grades setups
- **Gridbot calculator** — sizes a grid trading setup and estimates returns given your capital and fee structure
- **AI briefings** — synthesizes macro + structure + signals into a written read using your choice of AI provider (Gemini, Claude, OpenAI, or local Ollama)
- **MCP server** — lets Claude Code talk directly to Banshee, pulling live data into your AI conversations
- **Multi-source data** — Coinbase, CoinGecko, Alpaca, and yfinance in a latency-ranked chain; fastest provider wins

---

## Quick Start

**Requires:** Python 3.10+ and Node.js (any recent version).

1. Download or clone this repo
2. Double-click `launch_banshee.bat`
3. The launcher sets up the Python environment, installs packages, builds the UI, and opens `http://localhost:8765/ui/` in your browser

Everything runs locally. No cloud account needed to get started.

→ **Full setup guide:** [SETUP.md](SETUP.md)

---

## API Keys

All free. All stored locally in `~/.banshee_keys.json` — nothing leaves your machine.

| Key | Required | What for |
|-----|----------|----------|
| FRED API | Yes | Macro data (rates, liquidity) |
| AI provider | Yes | Written analysis (Gemini / Claude / OpenAI / Ollama) |
| Alpaca | Optional | Paper options trading |
| CoinGecko | Optional | Higher rate limits on crypto price data |

---

## Disclaimer

Banshee is a research and analysis tool, not financial advice. It reads markets — it does not predict them. All paper trading features use fake money only. Never trade more than you can afford to lose.

---

[![Buy Me A Coffee](https://www.buymeacoffee.com/assets/img/custom_images/orange_img.png)](https://buymeacoffee.com/sowily)
