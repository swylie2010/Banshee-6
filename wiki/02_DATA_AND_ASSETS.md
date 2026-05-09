# Banshee Pro 4 — Data & Assets

## Data Source Hierarchy

### Crypto OHLCV (shared_data.py `fetch_crypto_ohlcv`)
1. Coinbase (ccxt) — primary
2. Yahoo Finance — fallback
3. Local TV JSON (`tv_extract/ohlcv/`) — last resort

### Stock OHLCV (micro_engine.py `fetch_stock`)
1. Alpaca (with `adjustment=Adjustment.ALL` — critical for split-adjusted stocks)
2. Yahoo Finance — fallback

### Backtest data (strategy_lab.py `_fetch_backtest_data`)
1. Local TV JSON (if ≥80% bar coverage for the lookback period)
2. Binance (crypto all TFs — geo-blocked in US, transparent fallback)
3. Yahoo Finance

## TV OHLCV Files (extracted via TradingView MCP)

Location: `tv_extract/ohlcv/`
Format: `{SYMBOL}_{TF}_{DATE}.json`

| Asset | TFs Available | Source |
|-------|--------------|--------|
| BTC | 1W, 1D, 4H, 1H | KRAKEN:BTCUSD |
| PAXG | 1W, 1D, 4H, 1H | COINBASE:PAXGUSDC.P |
| SPY | 1W, 1D, 4H, 1H | AMEX:SPY |
| NVDA | 1W, 1D, 4H, 1H | NASDAQ:NVDA |
| ETHBTC | 1W, 1D, 4H, 1H | BINANCE:ETHBTC |
| SOL | 1W, 1D | KUCOIN:SOLUSDT (1W: 249 bars 2021-08-02→2026-05-06; 1D: 500 bars 2024-12-23→2026-05-06) |

**Note:** These are Claude's extraction work, not a live data pipeline. They serve as offline fallback and backtest data. Not for intraday use.

## HTF Levels (`htf_levels.json`)

Named institutional levels extracted from TradingView (yearly/monthly opens, Market Maker PD/PW, VWAP zones, Elliott Wave pivots). Wired into SMC engine — OBs/FVGs within 1 ATR of a named level get a ★ confluence tag.

| Asset | Status |
|-------|--------|
| NVDA | ✅ Populated |
| BTC | ✅ Populated |
| PAXG | ✅ Populated |
| SPY | ✅ Populated |
| SOL | ✅ Populated (2026-05-06) — yearly open $124.65, monthly open $83.08, daily EMAs/MACD/AVWAP, EW levels, VP node map, SMC snapshot |
| ETH | ❌ Not populated |
| Other altcoins | ❌ Not populated |

## Asset Profiles (`asset_profiles.py`)

Five asset classes with preset indicator weights and gate flags:

| Class | Key | Examples |
|-------|-----|---------|
| Default | `default` | SPY, most stocks |
| Crypto BTC | `crypto_btc` | BTC |
| Crypto Altcoin | `crypto_altcoin` | SOL, SUI, AVAX, and others |
| Gold Proxy | `gold_proxy` | PAXG, GLD |
| Equity | `equity` | NVDA, TSLA |

### KNOWN_ASSET_CLASSES — Current State
**Present:** BTC, PAXG, GLD, SPY, NVDA, TSLA, SOL, SUI, AVAX, HYPE, HBAR, TAO, XLM, NEAR

User's priority altcoins: SOL, SUI, HYPE, AVAX, HBAR, TAO, XLM, NEAR

## Calibration Baseline

Location: `tv_extract/calibration/NVDA_long_term_baseline.json`

| Field | Status |
|-------|--------|
| ATR | ✅ TV ground truth |
| VWAP | ✅ TV ground truth — pixel-perfect |
| RSI | ✅ TV verified 2026-04-29 — delta +3.34pt (within 5pt threshold) |
| MACD | ✅ TV verified 2026-04-29 — pixel-perfect |
| Stoch K/D | ✅ TV verified 2026-04-29 |
| EMA 50/200 | ✅ Banshee-computed, consistent with TV |

Baseline last saved: 2026-04-29. Run `python calibrate.py NVDA long_term` anytime to check drift.

## Key Backtest Findings (verified, batch-confirmed 2026-04-23)

- **Presignal-only**: dead on most assets (-3.9% avg). Exception: crypto in specific modes.
- **Position management**: always helps (+27% → +52% avg return, tighter DD). Always turn on.
- **Gold Stalker** (PAXG long_term + confirmed+pre + shorts + VIX20 + mgmt): Sharpe 1.38, +69%, -9% DD
- **NVDA Long-Term** (5y + mgmt): Sharpe 2.21, +338%, 29 trades — statistically valid
- **Crypto shorts** (BTC/ETH): both go negative. Only PAXG benefits from shorts.
- **SOL long-term 5y**: +78–112%, Sharpe 1.12–1.35 — catches the bull cycle; sits out bear chop correctly
