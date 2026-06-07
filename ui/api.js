/* Banshee — API client
 * Fetches from Core (:8765). Falls back to mock data on failure so the UI
 * stays usable even when Core is down or a symbol isn't supported.
 *
 * TF normalisation: UI uses "1H","4H","1D","1W"; Core uses "1h","4h","1d","1w"
 */

const API_BASE = "http://localhost:8765";

/* mode implied by a given timeframe */
const TF_TO_MODE = {
  "1m": "sniper", "5m": "sniper", "15m": "sniper",
  "1H": "swing",  "4H": "swing",  "1D": "swing",
  "1W": "long",
};

/* UI tf label → Core tf key returned in /ohlcv response */
const TF_CORE_KEY = {
  "1m": "1m", "5m": "5m", "15m": "15m",
  "1H": "1h", "4H": "4h", "1D": "1d", "1W": "1w",
};

/* symbol normalisation: "BTC" → "BTC/USD", equities stay as-is */
function coreSymbol(sym) {
  const CRYPTO = ["BTC","ETH","SOL","AVAX","HYPE","HBAR","TAO","XLM","NEAR","BNB","ADA","DOT","LINK","MATIC","UNI","AAVE","CRV"];
  const COMMOD  = ["GOLD","SILV","OIL","NGAS"];
  const COMMOD_PAIR = { GOLD:"XAU/USD", SILV:"XAG/USD", OIL:"WTI", NGAS:"NG" };
  if (COMMOD_PAIR[sym]) return COMMOD_PAIR[sym];
  if (CRYPTO.includes(sym)) return sym + "/USD";
  return sym; // equities & indices pass through unchanged
}

/* transform Core OHLCV records into LightweightCharts candle format */
function toLWCandles(records) {
  return records
    .filter(r => r.timestamp && r.open != null && r.close != null)
    .map(r => ({
      time: Math.floor(new Date(r.timestamp).getTime() / 1000),
      open:  r.open,
      high:  r.high,
      low:   r.low,
      close: r.close,
    }))
    .sort((a, b) => a.time - b.time);
}

/* extract a named indicator column from Core OHLCV records → LW Charts {time,value} format */
function toIndicatorSeries(records, field) {
  return records
    .filter(r => r.timestamp && r[field] != null && !isNaN(r[field]))
    .map(r => ({ time: Math.floor(new Date(r.timestamp).getTime() / 1000), value: r[field] }))
    .sort((a, b) => a.time - b.time);
}

/* fetch OHLCV for a symbol+tf from Core; returns LW-formatted candles */
async function fetchOHLCV(sym, tf) {
  const mode    = TF_TO_MODE[tf] || "swing";
  const coreKey = TF_CORE_KEY[tf] || tf.toLowerCase();
  const pair    = coreSymbol(sym);
  try {
    const res  = await fetch(`${API_BASE}/ohlcv?symbol=${encodeURIComponent(pair)}&mode=${mode}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    if (data.error) throw new Error(data.error);
    const records = data.tfs?.[coreKey];
    if (!records || !records.length) throw new Error(`no data for tf=${coreKey}`);
    return {
      candles: toLWCandles(records),
      indicators: {
        ema50:  toIndicatorSeries(records, 'ema_50'),
        ema200: toIndicatorSeries(records, 'ema_200'),
        vwap:   toIndicatorSeries(records, 'vwap'),
        stochK: toIndicatorSeries(records, 'stoch_k'),
        stochD: toIndicatorSeries(records, 'stoch_d'),
      },
      source: "live",
    };
  } catch (err) {
    console.warn(`[api] OHLCV fallback for ${sym}/${tf}:`, err.message);
    /* fall back to mock candles so the chart still renders */
    const mockRaw = window.buildCandles(sym, tf, 80);
    const now = Math.floor(Date.now() / 1000);
    const TF_SEC = { "1m":60,"5m":300,"15m":900,"1H":3600,"4H":14400,"1D":86400,"1W":604800 };
    const step = TF_SEC[tf] || 3600;
    const candles = mockRaw.map((c, i) => ({
      time:  now - (mockRaw.length - 1 - i) * step,
      open:  c.o, high: c.h, low: c.l, close: c.c,
    }));
    return { candles, indicators: null, source: "mock" };
  }
}

/* fetch Asset Radar data for a symbol */
async function fetchRadar(sym, mode = "swing") {
  const pair = coreSymbol(sym);
  try {
    const res  = await fetch(`${API_BASE}/radar?symbol=${encodeURIComponent(pair)}&mode=${mode}&output_mode=full`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (err) {
    console.warn(`[api] radar fallback for ${sym}:`, err.message);
    return null;
  }
}

/* fetch macro sensors (TopBar flags) */
async function fetchMacro() {
  try {
    const res = await fetch(`${API_BASE}/macro/sensors`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (err) {
    console.warn("[api] macro fallback:", err.message);
    return null;
  }
}

/* fetch SMC JSON for overlay rendering — tf accepts UI format ("4H") or core format ("4h") */
async function fetchSMC(sym, tf = "4H") {
  const pair = coreSymbol(sym);
  const ltf  = TF_CORE_KEY[tf] || tf.toLowerCase();
  try {
    const res  = await fetch(`${API_BASE}/smc/json?symbol=${encodeURIComponent(pair)}&ltf=${ltf}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (err) {
    console.warn(`[api] SMC fallback for ${sym}:`, err.message);
    return null;
  }
}

/* fetch presets array from Core */
async function fetchPresets() {
  try {
    const res = await fetch(`${API_BASE}/presets`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    return data.presets ?? [];
  } catch (err) {
    console.warn("[api] fetchPresets:", err.message);
    return null; // null = Core unavailable (use localStorage migration)
  }
}

async function savePresets(presets) {
  try {
    await fetch(`${API_BASE}/presets`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ presets }),
    });
  } catch (err) {
    console.warn("[api] savePresets:", err.message);
  }
}

/* fetch XABCD harmonic patterns for chart overlay — always uses daily data */
async function fetchXABCD(sym) {
  const pair = coreSymbol(sym);
  try {
    const res = await fetch(`${API_BASE}/xabcd?symbol=${encodeURIComponent(pair)}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (err) {
    console.warn(`[api] XABCD fallback for ${sym}:`, err.message);
    return null;
  }
}

/* fetch Geo Harmonic hot zones for chart overlay — always uses daily data */
async function fetchGH(sym) {
  const pair = coreSymbol(sym);
  try {
    const res = await fetch(`${API_BASE}/geo-harmonic?symbol=${encodeURIComponent(pair)}&multi_window=true`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (err) {
    console.warn(`[api] GH fallback for ${sym}:`, err.message);
    return null;
  }
}

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

/* request an AI synthesis briefing for a symbol — POSTs to /ai/briefing
 * tab: "nexus" | "smc" | "gh" — controls prompt focus and format
 * signal: optional AbortSignal to cancel a stale in-flight request
 */
async function fetchAIBriefing(sym, mode = "swing", tab = "nexus", signal = null, manualStories = []) {
  const pair = coreSymbol(sym);
  try {
    const res = await fetch(`${API_BASE}/ai/briefing`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ symbol: pair, mode, manual_stories: manualStories, tab }),
      signal,
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return { text: await res.text(), error: null };
  } catch (err) {
    if (err.name === "AbortError") return { text: null, error: null, aborted: true };
    console.warn(`[api] AI briefing for ${sym}:`, err.message);
    return { text: null, error: err.message };
  }
}

/* fetch current settings (keys masked) */
async function fetchSettings() {
  try {
    const res = await fetch(`${API_BASE}/settings`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (err) {
    console.warn("[api] fetchSettings:", err.message);
    return null;
  }
}

/* save settings — masked values (starting with •••••) are preserved server-side */
async function saveSettings(settings) {
  try {
    const res = await fetch(`${API_BASE}/settings`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ settings }),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (err) {
    console.warn("[api] saveSettings:", err.message);
    return { status: "error", message: err.message };
  }
}

/* test AI connection with current form values */
async function testAIConnection(aiConfig) {
  try {
    const res = await fetch(`${API_BASE}/settings/test`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ settings: { AI_API: aiConfig } }),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (err) {
    console.warn("[api] testAIConnection:", err.message);
    return { status: "error", message: err.message };
  }
}

/* fetch saved backtest strategies for Signal Lab */
async function fetchStrategies() {
  try {
    const res = await fetch(`${API_BASE}/strategies/data`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (err) {
    console.warn("[api] fetchStrategies:", err.message);
    return {};
  }
}

/* POST to /execution-plan for Risk Desk — always uses JSON output mode */
async function fetchExecutionPlan({ account_size, risk_percent, entry_price, stop_loss, smc_conflicted = false }) {
  try {
    const res = await fetch(`${API_BASE}/execution-plan`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ account_size, risk_percent, entry_price, stop_loss, smc_conflicted, output_mode: "json" }),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (err) {
    console.warn("[api] fetchExecutionPlan:", err.message);
    return { error: err.message };
  }
}

/* fetch all trades + stats for Trade Journal */
async function fetchTrades() {
  try {
    const res = await fetch(`${API_BASE}/journal/trades`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (err) {
    console.warn("[api] fetchTrades:", err.message);
    return { trades: [], stats: {} };
  }
}

/* close an open trade */
async function closeTrade({ trade_id, exit_price, exit_reason = null, notes = "" }) {
  try {
    const res = await fetch(`${API_BASE}/journal/close`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ trade_id, exit_price, notes, exit_reason }),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (err) {
    console.warn("[api] closeTrade:", err.message);
    return { error: err.message };
  }
}

/* update stop/target levels on an open trade */
async function updateLevels({ trade_id, stop_price, target_price }) {
  try {
    const res = await fetch(`${API_BASE}/journal/update-levels`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ trade_id, stop_price, target_price }),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (err) {
    console.warn("[api] updateLevels:", err.message);
    return { error: err.message };
  }
}

/* set outcome quality fields on a trade */
async function updateOutcome({ trade_id, signal_correct = null, exit_reason = null, note = "" }) {
  try {
    const res = await fetch(`${API_BASE}/journal/update-outcome`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ trade_id, signal_correct, exit_reason, note }),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (err) {
    console.warn("[api] updateOutcome:", err.message);
    return { error: err.message };
  }
}

/* trigger Alpaca sync */
async function syncAlpaca() {
  try {
    const res = await fetch(`${API_BASE}/journal/sync-alpaca`, { method: "POST" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (err) {
    console.warn("[api] syncAlpaca:", err.message);
    return { updated: 0 };
  }
}

/* fetch feedback synthesis for journal analysis */
async function fetchFeedbackSynthesis() {
  try {
    const res = await fetch(`${API_BASE}/journal/feedback-synthesis`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (err) { return { error: err.message }; }
}

/* fetch the latest Predator briefing */
async function fetchPredatorBriefing() {
  try {
    const res = await fetch(`${API_BASE}/predator/briefing`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (err) {
    console.warn("[api] fetchPredatorBriefing:", err.message);
    return null;
  }
}

/* trigger the Daily Predator pipeline; resolves when complete (2-3 min) */
async function runPredator(force = true, manualStories = []) {
  try {
    const res = await fetch(`${API_BASE}/predator/run`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ watchlist: [], force, manual_stories: manualStories }),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (err) {
    console.warn("[api] runPredator:", err.message);
    return null;
  }
}

/* open a paper trade in the journal — wraps POST /journal/open */
async function journalOpen({ symbol, direction, entry_price, stop_price,
  target_price, position_usd = 1000, verdict = "", edge = "", mode = "swing", notes = "" }) {
  const pair = coreSymbol(symbol);
  try {
    const res = await fetch(`${API_BASE}/journal/open`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ symbol: pair, direction, entry_price, stop_price,
        target_price, position_usd, verdict, edge, mode, notes }),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (err) {
    console.warn("[api] journalOpen:", err.message);
    return { error: err.message };
  }
}

window.API = { fetchOHLCV, fetchRadar, fetchMacro, fetchSMC, fetchPresets, savePresets, fetchGH, fetchGHPine, fetchXABCD, fetchAIBriefing, fetchSettings, saveSettings, testAIConnection, fetchStrategies, fetchExecutionPlan, fetchTrades, closeTrade, updateLevels, updateOutcome, syncAlpaca, fetchFeedbackSynthesis, fetchPredatorBriefing, runPredator, journalOpen, coreSymbol };
