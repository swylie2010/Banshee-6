# Banshee Pro 3 — Full Batch Test Analysis
*358 batch entries across 7 assets × 3 modes × 2 timeframes × signal/mgmt/shorts/VIX permutations*
*Analyzed: 2026-04-22*

---

## TL;DR — What the Data Says

1. **Presignal-only is dead.** Confirmed+Pre averages +82.3% / Sharpe 0.65. Presignal-only averages -3.9% / Sharpe -0.17. This is the single clearest finding.
2. **Position management always wins.** +27.1% → +52.3% avg return; MaxDD tightens; no downside.
3. **PAXG long_term is the crown jewel.** Sharpe 3.37, +47.5%, only -6% DD over 2y. Statistically thin (10 trades) but consistently exceptional across all VIX configs.
4. **Crypto shorts generally destroy returns.** BTC and ETH both go negative with shorts enabled in 2y window. The VIX gate doesn't save them.
5. **VIX20 gate specifically helps PAXG.** +36.4% → +58.4% (Sharpe 0.76 → 1.20) with shorts+vix20. The gate correctly blocks PAXG shorts during fear spikes.
6. **Sniper mode is the return king, long_term is the Sharpe king.**

---

## Finding 1: Presignal Is Definitively Over

| Config | n | Avg Return | Avg Sharpe |
|---|---|---|---|
| Confirmed + Pre-signal | 84 | **+82.3%** | **+0.65** |
| Pre-signal Only | 82 | **-3.9%** | **-0.17** |

Pre-signal-only loses money on average across all assets and modes. Remove it from consideration for all live strategies.

---

## Finding 2: Position Management Is Free Alpha

| Config | n | Avg Return | Avg Sharpe | Avg MaxDD |
|---|---|---|---|---|
| No management | 83 | +27.1% | 0.21 | -28.0% |
| With management | 83 | +52.3% | 0.28 | -26.5% |

+25% return improvement with slightly tighter drawdown. Always enable it.

---

## Finding 3: Mode Comparison (5y, confirmed+pre, with mgmt)

| Mode | Avg Return | Avg Sharpe | Avg MaxDD |
|---|---|---|---|
| Sniper | +322.1% | 0.43 | -40.0% |
| Swing | +137.6% | 0.69 | -45.7% |
| Long_term | +112.5% | **1.55** | **-33.8%** |

**Sniper:** Max return, choppiest ride. 5-year ETH sniper hit +1548% but with Sharpe 0.46 — lever-driven outlier.
**Long_term:** Best risk-adjusted across the board. Fires infrequently but accurately.
**Swing:** Worst of both worlds in most configurations. Better than long_term only on raw return.

2-year view (more realistic, recent market):

| Mode | Avg Return | Avg Sharpe | Avg MaxDD |
|---|---|---|---|
| Sniper | +44.9% | 0.42 | -30.6% |
| Long_term | +7.4% | 0.69 | -11.9% |
| Swing | +11.3% | 0.43 | -26.9% |

Long_term wins on Sharpe with the smallest drawdown even over 2y.

---

## Finding 4: Asset Rankings

| Asset | Avg Return (all batch) | Avg Sharpe | Notes |
|---|---|---|---|
| PAXG/USD | +73.4% | **1.44** | Gold trend-follower, dominant Sharpe |
| ETH/USD | +55.0% | 0.05 | High returns but volatile alpha |
| NVDA | +61.6% | 0.26 | Skewed by 5y BNH being enormous |
| BTC/USD | +39.3% | 0.19 | BNH hard to beat |
| SPY | +18.2% | **0.64** | Remarkable consistency for an index |
| SOL/USD | +14.2% | -0.29 | Worst overall; volatility kills it |
| SOL/USDT | +16.5% | -0.32 | Effectively identical to SOL/USD |

**PAXG** and **SPY** are the two highest-quality signal environments. PAXG trends; SPY is structurally bullish and responds well to SMC long_term signals.

---

## Finding 5: Crypto Shorts Are a Losing Proposition

2-year window, confirmed+pre, all crypto assets:

| Config | Avg Return | Avg Sharpe | Avg MaxDD |
|---|---|---|---|
| Longs only | **+16.1%** | **0.48** | -23.7% |
| Longs + Shorts | +1.2% | 0.13 | -37.5% |

Shorts **add 14% drawdown and destroy the Sharpe ratio** in 2y testing.

Per asset with shorts (2y, confirmed+pre, no VIX):

| Asset | Return | Sharpe | MaxDD |
|---|---|---|---|
| BTC/USD | -17.1% | -0.08 | -39.3% |
| ETH/USD | -45.7% | -0.27 | -64.2% |
| PAXG/USD | +36.4% | **+0.76** | -12.3% |
| SOL/USD (swing) | negative across configs | — | — |

**PAXG is the only crypto asset where shorts add value.** The gold market has legitimate, tradeable bear phases unlike BTC/ETH in recent history.

---

## Finding 6: VIX Gate Results (BTC/ETH/PAXG, 2y, confirmed+pre, with shorts)

### PAXG — VIX gate is a meaningful upgrade:

| VIX Gate | Return | Sharpe | MaxDD | Win Rate |
|---|---|---|---|---|
| None | +46.8% | 0.94 | -12.1% | 50% |
| VIX20 | **+69.3%** | **1.38** | -9.4% | 53% |
| VIX25 | +62.6% | 1.27 | -8.5% | 56% |
| VIX30 | +56.3% | 1.22 | -10.3% | 56% |

**VIX20 is the optimal gate for PAXG.** It blocks shorts during fear spikes when gold tends to rally, adding +22% return and improving Sharpe by +0.44. VIX25/30 also help but less so.

### BTC/USD — VIX gate doesn't save shorts:

| VIX Gate | Return | Sharpe | MaxDD |
|---|---|---|---|
| None | -8.5% | +0.02 | -34.8% |
| VIX20 | -6.9% | -0.02 | -35.6% |
| VIX25 | -25.0% | -0.41 | -42.6% |
| VIX30 | +0.2% | +0.07 | -24.5% |

Marginally better at vix30 but not worth the complexity. VIX20/25 actually make BTC worse.

### ETH/USD — VIX gate makes little difference when the baseline is deeply negative:

All ETH+shorts+2y configs land between -18% and -45% return regardless of VIX threshold.

**Verdict:** VIX gate is only justified for **PAXG**, and the optimal threshold is **VIX20**.

---

## Finding 7: NVDA Is a Sleeper Hit

| Config | Return | Sharpe | MaxDD | Trades |
|---|---|---|---|---|
| long_term 5y confirmed+pre+mgmt | **+338.9%** | **2.21** | -28.5% | 29 |
| long_term 5y confirmed+pre | +319.4% | 2.15 | -28.5% | 27 |
| swing 5y confirmed+pre+mgmt | +314.6% | 1.06 | -35.4% | 135 |
| sniper 5y confirmed+pre+mgmt | +395.7% | 0.62 | -47.7% | 121 |

NVDA long_term 5y at Sharpe 2.21 with 29 trades is statistically meaningful. The system correctly captured the AI-driven NVDA rally with minimal whipsawing. This is one of the highest-quality signals in the entire dataset.

*Note: NVDA's BNH was enormous over 5y, so aggregate alpha is negative — but the absolute return and Sharpe are still exceptional for an active strategy.*

---

## Finding 8: SPY Performance

| Config | Return | Sharpe | MaxDD | Trades |
|---|---|---|---|---|
| long_term 2y confirmed+pre | +15.9% | 3.07 | 0.0% | 3 |
| long_term 5y confirmed+pre | +43.5% | 1.60 | -14.2% | 19 |
| swing 5y confirmed+pre+mgmt | +51.5% | 0.92 | -9.8% | 98 |
| sniper 2y confirmed+pre+mgmt | +30.6% | 0.73 | -7.7% | 149 |

SPY long_term 2y (Sharpe 3.07) has only 3 trades — statistically fragile. The 5y long_term (19 trades, Sharpe 1.60) is more credible. SPY swing 5y is genuinely solid: 98 trades, Sharpe 0.92, -9.8% DD.

SPY with shorts is uniformly bad — long-bias index, don't short it.

---

## Summary — Recommended Live Configurations

### Tier 1: Core Strategies (Deploy These)

| Strategy | Config | Return | Sharpe | MaxDD | Why |
|---|---|---|---|---|---|
| PAXG long_term | 2y, confirmed+pre, shorts+vix20, +mgmt | +69.3% | **1.38** | -9.4% | Best risk-adjusted in the dataset |
| PAXG long_term | 5y, confirmed+pre, shorts+vix25 | +126.1% | **2.80** | -6.4% | If you trust the 5y window |
| NVDA long_term | 5y, confirmed+pre, +mgmt | +338.9% | **2.21** | -28.5% | Statistically valid (29 trades) |
| SPY swing | 5y, confirmed+pre, +mgmt | +51.5% | **0.92** | -9.8% | Low DD, high trade count |

### Tier 2: Higher Return, Higher Risk

| Strategy | Config | Return | Sharpe | MaxDD |
|---|---|---|---|---|
| BTC/USD sniper | 5y, confirmed+pre, vix20, +mgmt | +573.9% | 0.40 | -32.7% |
| ETH/USD sniper | 5y, confirmed+pre, no shorts | +383.9% | 0.34 | -48.1% |
| SOL/USDT sniper | 5y, confirmed+pre, +mgmt | +540.8% | 0.31 | -57.1% |

### Remove From Consideration
- **Presignal-only** — dead in every configuration
- **Crypto shorts (BTC/ETH/SOL)** — negative in 2y, not worth the DD expansion
- **SOL as a priority asset** — worst Sharpe, highest DD, not meaningfully different from SOL/USDT

---

## Statistical Caution Flags

| Entry | Issue |
|---|---|
| PAXG long_term 2y (all) | 6–10 trades — directionally clear but low sample |
| SPY long_term 2y | 3 trades, 0% DD — too thin to rely on |
| ETH long_term 2y + vix20 | 3 trades — same concern |
| 5y returns generally | Capture 2020–2021 bull; past conditions may not repeat |

The highest-confidence result in the entire dataset: **PAXG long_term 5y (19 trades, Sharpe 2.68–2.80)** — meaningful sample, consistent across VIX configurations, gold-market fundamentals support the signal.

---

## What to Build Next

1. **Wire PAXG long_term + VIX20 gate + shorts + mgmt as a named strategy in the live Banshee UI** — it's the best-performing overall
2. **Add NVDA long_term confirmed+pre+mgmt as a TradFi track** — the signal works
3. **Kill the presignal-only path from the UI** — no reason to show broken configs
4. **Consider a "quality mode" filter** — only surface strategies with n_trades ≥ 15 in the Strategy Lab to avoid the thin-sample traps
