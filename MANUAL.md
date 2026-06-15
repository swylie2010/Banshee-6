# Banshee Pro — User Manual

> **⚠ Not financial advice. Not a trading bot. Not a recommendation to buy or sell anything.**
> Banshee is an educational analysis tool. All outputs are for informational purposes only.
> Trading involves substantial risk of loss. Past performance of any signal, score, or indicator
> does not guarantee future results. Never risk money you cannot afford to lose.
> **The author is not a licensed financial advisor. Use this software entirely at your own risk.**

**What is Banshee Pro?**
A top-down trading command center. It reads the macro environment, analyzes a specific asset technically, maps its market structure, synthesizes everything with AI, and tells you whether there's a trade worth taking — and if so, exactly how to size it.

It is not a trading bot. It doesn't place orders. It gives you a structured briefing so you can make a better decision.

**The most important thing to understand before you use it:**
Banshee doesn't remove uncertainty — it removes the part where you wonder if you missed something. The macro sensors ran. The structure was read. The indicators scored. The AI synthesized it. If the output is "conflicted, don't trade" — you didn't miss a hidden signal. The conflict *is* the signal. You can sit out with confidence instead of sitting out with anxiety.

Most trading tools try to give you more signals. Banshee's best output is sometimes a clean "no." That's not a failure — that's the hard lifting done for you.

---

## The Flow of a Trade

This is the order that makes sense. Each step either gives you a green light to keep going or a reason to stop.

```
Macro Weather → Market Intel → Asset Radar → Structure Map → Banshee Nexus → Risk Desk
     ↓                ↓              ↓               ↓               ↓             ↓
  Should I         Any news       Is this        What is        Full AI        If yes,
  trade at        that changes   asset worth    the market     synthesis      how much?
  all today?      the picture?   looking at?    doing in
                                               structure?
```

**You don't have to run all six steps every time.** If Macro Weather shows FEAR regime with risk score 8/10, you might stop right there. The flow is a filter, not a checklist.

---

## Tab by Tab

### 🌦 Macro Weather
**What it is:** The big picture. 8 macro sensors (VIX, yield curve, Fed liquidity, DXY, credit spreads, gold/copper ratio, sector rotation, and others) combined into a regime bucket and a risk score.

**What to look at:**
- **Regime badge** (top of page): TRENDING, NEUTRAL, CAUTION, or FEAR. This is the headline.
- **Risk Score (1–10):** Higher = more systemic stress in the market. Above 6 = size down or wait.
- **Contradiction warnings:** Orange/red alert cards below the sensors. These fire when two sensors are telling opposite stories (e.g. VIX is calm but credit spreads are blowing out). These are often the most important signal on the page.
- **Sensor cards:** Click any card to expand the calibration notes. They explain what "warning" means for that specific sensor.

**What it means for your trade:**
- FEAR + high risk score = consider staying out or cutting position size in half
- CAUTION = trade if the setup is excellent, but don't size up
- TRENDING/NEUTRAL = macro has your back, normal sizing is fine

**Foibles:**
- Macro sensors use FRED data (free API key required). Without it, several sensors will show N/A.
- Data is cached for 15 minutes. The timestamp on each sensor tells you when it last fetched.
- Macro is a slow-moving signal. It doesn't change minute to minute. Check it once at the start of your session.

---

### 📰 Market Intel / Daily Predator
**What it is:** Live RSS news feed + AI-generated daily briefing. Tells you if there's a headline today that changes the macro or asset picture.

**What to look at:**
- **Daily Predator briefing** (if run): AI summary of today's key macro themes, discovered signals, and risk events. Run it once in the morning.
- **Raw Intel feed:** Live headlines. Scan for your asset name or macro keywords (Fed, CPI, rate, liquidity).
- **Inject Story into Nexus:** If you spot a specific headline that matters, paste it here. It gets baked into the Nexus AI briefing for that symbol.

**What it means for your trade:**
- A major scheduled event (Fed meeting, CPI print, earnings) = consider waiting until after, or sizing down
- Nothing relevant = proceed normally

**Foibles:**
- The Predator briefing requires an AI API key (Claude or Gemini). Configure in ⚙️ Settings.
- Run the briefing once. It saves for the day — you don't need to rerun it every time you open the app.

---

### 🎯 Asset Radar
**What it is:** Full technical analysis for one symbol. The micro layer. Three timeframes stacked (depends on mode), scored with 10+ indicators, producing a verdict.

**What to look at:**
- **Verdict badge:** STRONG BUY / BUY SETUP / NEUTRAL / SELL SETUP / STRONG SELL
- **PRE-SIGNAL badge (⚡):** Fires *before* the main verdict. Early accumulation detected. Useful for getting in ahead of the confirmed signal. See Signal Playbook for when to trust it.
- **Session field:** Shows the current ICT session window (Silver Bullet, Killzone, Regular, etc.) and its multiplier. A STRONG BUY during a Silver Bullet window (×2.0) carries more weight than the same verdict during the Asian range (×0.5). Only shown when outside regular hours.
- **Timeframe breakdown:** Each of the 3 timeframes has its own bull/bear score. All three agreeing = high conviction. Only 1 of 3 agreeing = low conviction, proceed carefully.
- **ATR Trade Plan:** Automatic entry/stop/target levels based on current ATR volatility. These are starting points, not gospel.
- **Regime overlay:** If Macro Weather is loaded, the radar will flag whether macro is helping or fighting your trade.

**Modes:**
| Mode | Timeframes | Use for |
|---|---|---|
| Sniper | 4h / 1h / 15m | Short-term trades, 1–5 day holds |
| Swing | 1d / 4h / 1h | Multi-week positions |
| Long Term | 1wk / 1d / 4h | Months-long positions, portfolio allocation |

**What it means for your trade:**
- STRONG BUY + macro TRENDING + all 3 TFs bullish = highest quality setup
- BUY SETUP + ⚡ PRE-SIGNAL = decent early entry, but macro and structure should agree
- Verdict bullish but only 1/3 TFs agree = skip or wait for alignment

**Foibles:**
- Load the symbol in the sidebar first. The sidebar symbol selector controls all tabs.
- Intraday data (sniper mode) is limited to ~60 days by yfinance. For longer history use Alpaca (stocks) or VPN for Binance (crypto).
- Crypto symbols: use `BTC-USD` format for yfinance. Binance routing uses `BTC/USDT` automatically.

---

### 🗺️ Structure Map
**What it is:** A candlestick chart with Smart Money Concepts (SMC) overlays. Shows you the actual market structure — where big money has been buying/selling, where price is likely to react, and what the structural bias is.

**The SMC Legend — Plain English:**

| Label | What it means | What to do with it |
|---|---|---|
| **HH** (Higher High) | Price made a new high above the previous swing high | Bullish structure intact |
| **HL** (Higher Low) | Price pulled back but held above the previous low | Bullish structure intact |
| **LH** (Lower High) | Price bounced but couldn't reach the previous high | Bearish structure forming |
| **LL** (Lower Low) | Price broke below the previous swing low | Bearish structure intact |
| **BOS** (Break of Structure) | Price closed beyond a key swing point — structure confirmed broken | Trend continuation signal. Direction of the break = direction of the trend. |
| **CHoCH** (Change of Character) | First BOS in the *opposite* direction — structure may be reversing | Early warning of trend reversal. Not confirmed until second BOS. |
| **FVG** (Fair Value Gap) | A 3-candle imbalance — price moved so fast it left a gap of unfilled orders | Price tends to return to fill FVGs. Active FVGs are likely reaction zones. |
| **OB** (Order Block) | The last opposite-colored candle before a strong BOS move | Where institutional orders likely sit. Strong reaction zone. |
| **EQH** (Equal Highs) | Two or more swing highs at nearly the same price | Liquidity pool above. Price may sweep it (fake breakout) before reversing. |
| **EQL** (Equal Lows) | Two or more swing lows at nearly the same price | Liquidity pool below. Price may sweep it before reversing. |
| **P/D Zone** | Premium (above equilibrium) or Discount (below equilibrium) | Buy in discount zones, sell/short in premium zones. EQ is the 50% midpoint of the current dealing range. |
| **OTE** (Optimal Trade Entry) | 62–79% Fibonacci retracement of the current leg | The sweet spot for entries after a BOS. Best risk:reward zone. |

**Inducement tags on Order Blocks:**
| Tag | Border | Meaning |
|---|---|---|
| **⚡** | Green | Inducement swept — an EQH/EQL trap in front of this OB has fired. The retail trap is done. **This OB is actionable.** |
| **⌛** | Amber | Inducement pending — an unswept EQH/EQL sits between price and this OB. Trap is set but hasn't fired. **Watch, don't enter yet.** |
| *(none)* | Normal | No inducement detected — the OB itself may be the trap. Lower confidence. |

Only OBs with ⚡ (swept) pass the active filter and qualify as signals.

**Session weight tags on Order Blocks:**
OBs formed during high-participation windows carry more weight. The multiplier appears directly on the label (e.g. `OB ▲ ⚡ ×2.0`).
| Tag | Session | Meaning |
|---|---|---|
| **×2.0** | Silver Bullet | 03:00–04:00, 10:00–11:00, 14:00–15:00 EST — peak institutional delivery windows |
| **×1.5** | Killzone | London (02–05 EST) or NY Open (07–10 EST) — elevated participation |
| *(none)* | Regular | Standard hours — normal weight |
| **×0.8** | London Close | 10:00–12:00 EST — thinning liquidity |
| **×0.5** | Asian Range | 20:00+ EST — low-conviction chop |

**HTF Confluence tag on Order Blocks:**
| Tag | Meaning |
|---|---|
| **★** | HTF Confluence — the OB zone overlaps a named institutional reference level (yearly open, Market Maker PD/PW, VWAP zone, Elliott Wave pivot). Two independent methods agree on this price. Treat it as a higher-confidence reaction zone. |

**Named HTF Reference Lines:**
The chart draws horizontal lines for every level stored in `htf_levels.json` for the active asset. Color key:
| Color | Category |
|---|---|
| Gold | Yearly/monthly opens (`opens.*`) |
| Purple | Market Maker PD/PW levels (`market_maker.*`) |
| Teal | VWAP supply/demand zones (`vwap.*`) |
| Steel gray | Elliott Wave targets and pivots (`elliott_wave.*`) |

Lines are labeled with their short name (e.g. "yearly open", "c fib 1618"). OBs and FVGs that land within 1 ATR of any of these lines receive the ★ tag automatically.

**The session info bar** (below the stats strip) shows what window you're currently in — color-coded and with a plain-English note about what that means for entry timing.

**How to read the chart top-down:**
1. What is the **overall structure** saying? More HH/HL = bullish. More LH/LL = bearish.
2. Was there a recent **BOS or CHoCH**? That tells you if the trend just confirmed or just warned of a reversal.
3. Where are the **unmitigated FVGs and OBs**? Those are your reaction zones.
4. Where is price sitting in the **P/D zones**? Entering a long in premium is a bad risk:reward.
5. Are there **EQH or EQL** nearby? A sweep of those levels is often a trap before the real move.
6. **What session is active?** The session info bar tells you. Entries in Silver Bullet or Killzone windows carry more institutional weight.

**The AI narrative panel** (if AI key is configured) synthesizes HTF vs LTF structure agreement and tells you the likely scenario in plain English. Read this after you've looked at the chart yourself.

**Layer toggles:** Each overlay (FVGs, OBs, EQH/EQL, BOS/CHoCH, Swings, P/D Zones) has its own checkbox. If the chart feels cluttered, turn off everything except Swings + BOS/CHoCH to see the bare structure first. Then add layers one at a time.

**Focus Mode:** Limits the number of swing points shown. If the chart is a mess of labels, turn this on and dial it down to 3–4 swings per type.

**Timeframe:** Always look at at least two timeframes. HTF (daily or 4h) for structural bias. LTF (1h or 15m) for entry precision.

**Foibles:**
- The more layers you show, the harder it is to read. Start minimal.
- OBs require a BOS + FVG to qualify. Not every candle before a move is an OB.
- EQH/EQL sweeps are often traps — price pokes above/below briefly, grabs the liquidity, then reverses hard. Don't chase the breakout.

---

### 🧠 Banshee Nexus
**What it is:** The full synthesis. Combines macro regime + micro verdict + SMC context + news into one AI briefing for the symbol you have loaded. This is the "should I actually trade this right now?" answer.

**What to look at:**
- **Regime overlay:** Macro context injected at the top. If macro is FEAR, Nexus will say so even if the technical picture is bullish.
- **Signal breakdown:** Same as Asset Radar but here it's in context of everything else.
- **AI narrative:** The synthesis prompt is carefully structured — it reasons from macro → structure → micro → news in order. Read it top to bottom.
- **Asymmetry score:** How much the trade favors the bull vs bear side. High positive = strong bull asymmetry.
- **Contradiction warnings:** If macro and micro are fighting each other, Nexus will flag it.

**What it means for your trade:**
- Use Nexus as a final confirmation, not a starting point. If you haven't looked at Macro Weather and the Structure Map first, the Nexus output won't mean as much.
- If Nexus says one thing and your gut says another — write down why before acting.

**Foibles:**
- Nexus makes a live API call to an AI model. It takes 5–15 seconds. The macro layer is cached (15 min TTL) so the wait is mostly for the AI response.
- If no AI key is configured, Nexus runs without the narrative — you get the raw signal data only.
- The AI is only as good as the data fed to it. If FRED data is missing (no API key), macro context will be partial.

---

### ⚖️ Risk Desk
**What it is:** Position sizing calculator. Given your account size, risk tolerance, and the ATR-based entry/stop from Asset Radar, it calculates exact unit size, margin required at various leverage levels, and R-targets.

**What to look at:**
- **Entry, Stop, Target:** Auto-filled from the last Asset Radar run. You can edit these manually.
- **Risk %:** What percent of your account you're willing to lose on this trade. Default 1%. Never go above 2% on a single trade.
- **Units / Contracts:** The exact position size.
- **Margin table:** How much capital is tied up at different leverage levels.
- **R-targets:** 1R (break even profit), 2R (twice your risk), 3R (three times). These are your exit levels.

**Foibles:**
- The Risk Desk is a what-if tool. Entry auto-fills but stays editable — you're not locked into the ATR numbers.
- If you change the symbol in the sidebar, re-run Asset Radar first so the Risk Desk picks up the new levels.

---

### 🔬 Signal Lab
**What it is:** A backtesting and signal validation tool. Tests whether Banshee's signals have mechanical edge when followed blindly over historical data.

**What it is NOT:** A strategy builder. It can't tell you what will work in the future, only what *would have* worked in the past on the data available.

**The key tabs:**
- **MTF Backtest:** Replays Banshee's real `score_timeframe()` + `compute_verdict()` over historical data. The most honest test of signal quality.
- **Discovery Mode:** Tests 6–7 indicators one at a time and ranks them by Sharpe ratio for this specific asset/timeframe. Useful for tuning Asset Profiles.
- **Live Snapshot:** Shows the current state of every indicator right now — green/red/neutral — with a confluence count and GO/NO-GO decision.
- **Comparative Runs:** Batch-tests the same setup across multiple timeframes and lookback periods.
- **Saved Results:** Your history of all saved backtest runs.

**Read the Signal Playbook before interpreting results.** Key rules:
- Under 30 trades = not statistically meaningful (directional read only)
- Sharpe ratio matters more than raw return
- Long_term mode is a quality filter — don't judge it by alpha vs B&H
- PRE-SIGNAL edge is real but lives in sniper mode

**Foibles:**
- Data is re-downloaded every run. This is slow on long lookbacks. A disk cache is planned but not yet built.
- yfinance 15m cap = 60 days. Sniper mode needs Alpaca (stocks) or VPN/Binance (crypto) for real historical depth.
- The lab can't model human judgment — it follows signals blindly. Your real results will differ because you'll skip some setups.

---

### 📊 Saved Results
All your saved backtest and validation runs in one filterable table. Colour-coded by return. Click any row to inspect the full metrics.

---

### 📒 Trade Journal
**What it is:** A live paper trading log wired directly to Alpaca's paper trading account. Every trade placed through Banshee is recorded here with the full Banshee context at signal time — verdict, regime, macro, edge score, session weight, mode.

**This is the honest test.** Backtests tell you what *would have* worked. The journal tells you what Banshee actually called in real time, with no hindsight.

**Open trade card shows:**
- Live price with unrealized P&L (auto-fetched, ~15 min delay)
- Distance to stop and target as a percentage
- R:R ratio
- Banshee context at entry (regime, macro, edge, mode)
- Alpaca order ID for bracket trades

**Controls on each open trade:**
- **Adjust stop / target** — edit the stop price or take-profit level on an already-open trade. R:R recalculates automatically. Press Enter or click Update Levels.
- **Manual close** — record the exit yourself (pre-filled with live price). Use this if you closed in Alpaca but the journal didn't auto-sync.
- **🔄 Sync Alpaca** — pulls the current state of all open bracket orders from Alpaca. Bracket trades auto-close in the journal when Alpaca's stop or target leg fills.

**Closed trade cards** show final outcome (win/loss/breakeven), exit price, P&L%, and any notes.

**Foibles:**
- Sync Alpaca runs automatically every 15 minutes while the app is open. If you closed a trade in Alpaca and the journal still shows it open, hit Sync manually.
- Regime and macro fields may be blank on older trades if the macro engine wasn't loaded at entry time.
- Bracket orders on equities are fully managed by Alpaca (stop + target both live). Crypto uses a market order entry only — stop/target enforcement is handled by Banshee's sync loop.

---

### ◆ Options — The Wheel & Bull Put Spreads
**What it is:** A beginner-first teaching tool for two conservative options income strategies — selling cash-secured puts as part of *The Wheel*, and selling Bull Put Spreads (credit spreads). Its job is to explain what an option is and help you make a good decision you understand — not to execute trades.

**The core idea:** When you sell an option, someone pays you cash up front (the premium) in exchange for an obligation you take on. The Wheel sells puts against ETFs you'd be happy to own anyway. Bull Put Spreads sell a put and simultaneously buy a cheaper one as a defined-risk cap — less premium, but you can never lose more than the width of the spread.

**The two tracks:**
- **The Wheel** — income-generating strategy using cash-secured puts → shares → covered calls in a cycle. Better suited to larger accounts. Requires full cash collateral.
- **Bull Put Spreads** — defined-risk credit spreads. Lower capital requirement. Better for smaller accounts or those who want a strict cap on maximum loss.

**The safety ladder:**
1. **Read** — Banshee finds the one candidate that passes every rule. You study it, nothing more.
2. **Grade** — You compose your own option idea; Banshee grades it rule-by-rule (the inverse of the search).
3. **Simulate** — Walk a chosen position through a full Wheel cycle, no money involved.
4. **Learn** — AI recap loop: try different numbers, compare scenarios, ask "why not?" on any graded position. The four danger levers (naked / high-delta / single-stock / oversize) are shown running calm vs crash months.

**Key guardrails Banshee enforces for The Wheel:**
- Cash-secured only (never margin) · 20–30 delta · 5% of account max per trade
- Open interest > 1,000 · IVR > 35 · 35–45 DTE · Broad ETFs only (SPY/QQQ/IWM/DIA)

**Foibles:**
- Options require an options chain data source. Banshee estimates IVR and delta from price/time math — flagged as "est." — until a real options feed is wired in. Treat estimates as directional, not precise.
- The account-size gate is real: below ~$20,000 the smallest qualifying position may exceed 5% of account. Banshee will tell you honestly if your account isn't there yet.
- No orders are placed. This is a read-and-learn tool.

---

### ⊞ Gridbot Calculator
**What it is:** A free educational calculator that shows how to configure a grid trading bot for any asset. Grid trading bots place a ladder of buy and sell orders across a price range, automatically buying dips and selling bounces to earn small repeated profits from oscillation.

**The most important thing to understand:** Gridbots thrive in sideways (ranging) markets and get hurt badly by strong trends. A bot deployed during a breakdown will buy all the way down. That's why the first thing the calculator checks is whether your asset is actually ranging right now — before showing you anything else.

**What the calculator shows:**

| Section | What it tells you |
|---------|------------------|
| **Regime Check** | Is this asset currently eligible for a gridbot? Shows MA120 slope, RSI-14, and a plain-English verdict. |
| **Grid Blueprint** | Arithmetic (equal dollar spacing) vs Geometric (equal % spacing) — auto-selected based on range size. Shows upper/lower bounds, spacing, and level count. |
| **Grid Levels** | Every individual limit order — price, type (BUY/SELL), capital allocated, and profit per completed oscillation. |
| **Capital Plan** | How your investment is split: 50% anchors at the current price; 50% spreads across levels using Soft Martingale scaling (outer levels get 3× more than inner ones — for cost-averaging without blowing up). |
| **Risk Guardrails** | Disaster stop price (where to switch to DCA mode), estimated max drawdown, and a fee churn check (warns if your grid spacing is too tight to profit after exchange fees). |

**How to use it:**
1. Enter the asset ticker (BTC, SPY, ETH, NVDA — anything yfinance supports)
2. Enter your capital amount
3. Set the number of grid levels (3–50) with the slider
4. Enter your exchange's trading fee %
5. Click ANALYZE — results appear in ~2–4 seconds

**Foibles:**
- Data comes from yfinance (6 months of daily bars). The fetch takes 2–4 seconds.
- Profit per cycle assumes price oscillates cleanly across the full range. Real grids fill unevenly.
- ELIGIBLE / NOT ELIGIBLE is a flag — Banshee calculates, you decide whether to act.
- No orders are placed. This is a read-and-learn tool.

---

### ⚙️ Settings
- **API Keys:** FRED (macro data) and AI (Claude or Gemini for Nexus narrative + Predator briefing)
- **AI Rate Limit:** How many AI calls per hour Banshee will make on your behalf. Default is 50/hr. If you hit the limit, AI features return HTTP 429 with a "Resets at HH:MM UTC" message — not an error, just a cooldown. Raise the limit in Settings if you're doing heavy analysis sessions.
- **DATA RECOVERY:** Toggle whether Banshee is allowed to call the AI when a column-rename rescue is needed in the micro engine. Off = strict, never uses AI to repair data. On (default) = AI rescue is allowed with column allow-list validation.
- **MCP Snippet:** Auto-generated config block for wiring Banshee into Claude Code as an MCP tool
- **Diagnostics:** Health board — checks all modules are importable, FRED is reachable, AI key is set
- **Asset Profiles:** Per-symbol indicator weight tuning. Promotes Discovery Mode results into live scoring weights.
- **Daily Predator config:** RSS feeds, keywords, scheduling

---

## Common Gotchas

- **Nothing loads / "Load a symbol" message everywhere:** You haven't entered a symbol in the sidebar yet. Type it in the Symbol box and click Load.
- **Macro sensors all show N/A:** No FRED API key. Go to ⚙️ Settings and add one (it's free at fred.stlouisfed.org).
- **Nexus is slow:** Normal. The macro layer is cached but the AI call takes time. If it freezes completely, check your AI API key in Settings.
- **Structure Map shows no BOS/CHoCH:** Either the selected timeframe/lookback doesn't have enough swings, or Focus Mode is filtering them out. Try a longer lookback or increase the Focus Mode slider.
- **Backtest returns look terrible vs B&H:** In a strong bull market, any active strategy will underperform holding. Use Sharpe ratio and max drawdown to evaluate the strategy — not alpha vs B&H.
- **Sniper mode backtest only covers 60 days:** yfinance limit. Add an Alpaca API key in Settings for US stocks, or use a VPN for crypto (Binance routing is built in — no code changes needed).
- **Symbol not found:** Try alternate formats. `BTC-USD` for Bitcoin on yfinance. Some assets use `.` (e.g. `BRK.B`). Futures may not be available.
- **"Symbol is too long" or "invalid characters" error:** Banshee validates symbols after normalization — max 10 characters, only `A-Z 0-9 - .` allowed. If you're getting a 400 error on a valid ticker, check if it resolved to a long form (e.g. full company name instead of ticker).
- **AI features returning 429:** You've hit the hourly AI rate limit. Banshee will tell you the reset time. You can raise the limit in ⚙️ Settings → AI Rate Limit.

---

## The Signal Playbook
For interpreting backtest results specifically — trade count thresholds, which mode works for which asset type, what Sharpe means — see **PLAYBOOK.md** in this folder.

---

*Last updated: 2026-06-14. This is a living document — update it when a new foible is discovered or a new tab is added.*
