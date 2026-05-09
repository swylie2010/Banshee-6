# Banshee Pro — Signal Playbook

A living reference of what we've actually learned from testing. Read this before drawing conclusions from a backtest result.

---

## The Core Rules

### 1. PRE-SIGNAL belongs in sniper mode
- **Sniper (4h/1h/15m)** is where PRE-SIGNAL fires enough to matter (50–150 trades over 2yr)
- **Long_term (1wk/1d/4h)** fires too rarely — 8–23 trades over 5yr is not statistical fact, it's a vibe
- **Swing (1d/4h/1h)** lands in between — directional read, not a verdict

### 2. Asset character determines optimal mode
| Asset Type | Best Mode | Why |
|---|---|---|
| Trending macro assets (GLD) | Long_term confirmed + presignal | Clean persistent trends produce Sharpe 2.90 with minimal DD |
| Stocks (SPY, NVDA) | Sniper confirmed + presignal OR long_term | Sniper for active trading; long_term for position sizing |
| Crypto (BTC, PAXG) | Sniper PRE-SIGNAL only | Accumulation entries; confirmed signals arrive too late |
| ETH | Avoid | Negative or flat in every mode tested (sniper, swing, long_term) |

### 3. Confirmed signals are a drag on crypto
Banshee's verdict engine is a trend *confirmation* system. By the time all 3 timeframes agree, the move is 60–70% done. This is especially punishing on crypto where momentum is fast.

### 4. Long_term mode is a quality filter, not an alpha generator
- **Judge long_term by Sharpe**, not by alpha vs B&H
- B&H alpha is misleading in a BTC bull market — nothing active beats just holding during a moonrun
- Long_term confirmed+presignal: Sharpe 1.21, -33% max DD — excellent risk-adjusted, not an alpha machine
- Use long_term to answer: "is this a *clean* trade?" not "will this beat holding?"

### 5. Trade count is the first thing to check
| Trade Count | What it means |
|---|---|
| < 15 | Direction only — could be random noise |
| 15–30 | Weak signal — treat as a hypothesis |
| 30–50 | Getting real — starting to be meaningful |
| 50+ | Statistical basis — start drawing conclusions |
| 100+ | Solid — findings are defensible |

---

## The Reference Results (as of 2026-04-15)

### Sniper mode (4h/1h/15m), 2yr — statistically valid
| Asset | Mode | Return | Trades | Sharpe | Max DD |
|---|---|---|---|---|---|
| SPY | confirmed + presignal | +25.3% | 133 | **0.60** | -8.7% |
| NVDA | confirmed + presignal | +26.8% | 153 | 0.27 | -23.6% |
| BTC | presignal only | +21.0% | 98 | 0.27 | -17.0% |
| PAXG | presignal only | +3.5% | 65 | 0.15 | -6.7% |
| SPY | presignal only | +2.8% | 43 | 0.16 | -5.0% |
| ETH | presignal only | -21.8% | 108 | -0.19 | -32.2% |

### Long_term mode (1wk/1d/4h), 5yr — low sample, directional only
| Asset | Mode | Return | B&H | Alpha | Win Rate | Trades | Sharpe | Max DD |
|---|---|---|---|---|---|---|---|---|
| GLD | confirmed + presignal | +114.3% | +155.0% | -40.7% | **75.0%** | 16 | **2.90** | **-7.9%** |
| SPY | confirmed + presignal | +40.3% | +88.3% | -48.0% | 50.0% | 18 | **1.51** | -15.1% |
| BTC | confirmed + presignal | +71.1% | +176.8% | -105.7% | 39.1% | 23 | **1.21** | -33.3% |
| BTC | presignal only | +24.2% | +177.1% | -152.9% | 50.0% | 8 | 0.76 | -20.4% |
| ETH | confirmed + presignal | -30.0% | +61.6% | -91.7% | 45.8% | 24 | -0.07 | -38.6% |

**Key findings from long_term mode:**
- **GLD Sharpe 2.90** — institutional-grade. Long_term mode loves clean, persistent trends. Gold's multi-year trend was exactly that.
- **Sharpe ranking follows trend clarity:** GLD > SPY > BTC > ETH, which maps directly to how clean each asset's trend was over the period.
- **ETH is broken in every mode tested** (sniper, swing, long_term — all negative or flat). Position management made zero difference. Avoid until further investigation.
- **Alpha vs B&H is the wrong metric for long_term** — GLD "only" -40.7% alpha but Sharpe 2.90 and -7.9% max DD. You gave up some upside; you kept your capital intact. That's the trade.
- All long_term sample sizes are thin (8–24 trades). Treat as directional reads, not statistical verdicts.

---

## The Hard Limits (yfinance)
- **15m data:** 60-day max (sniper mode needs Binance or Alpaca for real lookbacks)
- **1h/4h data:** 730-day max (2yr cap)
- **Binance:** geo-blocked in US (HTTP 451) — works on VPN or non-US VPS, no code changes needed
- **Alpaca:** wired in for US stocks intraday (keys in `~/.banshee_keys.json`)
- **Crypto symbol format:** use `BTC/USD` for yfinance, `BTC-USDT` for Binance routing

---

## What Backtesting Can't Tell You
- Whether a setup *looked* clean at the time (human visual filter can't be modeled)
- Whether macro context would have made you skip it
- How you would have managed the trade emotionally
- Whether the edge holds going forward (all backtests are rear-view)

The backtest answers one question: **do these signals have mechanical edge when followed blindly?**
That's valuable — but it's not the whole story.

---

## The SMC Insight (2026-04-12)
SMC structure + ATR is the natural pairing. Both measure *force/displacement*.
The indicator stack (EMA, RSI, Stoch RSI) measures *momentum via past closes* — a different, laggier question.
This is why PRE-SIGNAL (which catches early structural moves) beats confirmed signals (which wait for indicator alignment).

---

*Last updated: 2026-04-15. Update this file whenever a backtest round produces a new insight.*
