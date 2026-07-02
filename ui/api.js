/* Banshee — API client
 * Fetches from Core (:8765). When Core returns no real bars for a symbol+timeframe,
 * the chart shows an honest "no real data" state — it NEVER fabricates candles.
 *
 * TF normalisation: UI uses "1H","4H","1D","1W"; Core keys are "1h","4h","1d","1wk".
 * (Weekly is "1wk", not "1w" — getting this wrong silently routed every weekly
 *  request to the old mock fallback.)
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
  "1H": "1h", "4H": "4h", "1D": "1d", "1W": "1wk",
};

/* symbol normalisation: "BTC" → "BTC/USD", equities stay as-is */
function coreSymbol(sym) {
  const CRYPTO = ["BTC","ETH","SOL","AVAX","HYPE","HBAR","TAO","XLM","NEAR","BNB","ADA","DOT","LINK","MATIC","UNI","AAVE","CRV"];
  const COMMOD  = ["GOLD","SILV","OIL","NGAS"];
  const COMMOD_PAIR = { GOLD:"XAU/USD", SILV:"SLV", OIL:"WTI", NGAS:"NG" };
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

let _token = null;
const _ready = (async function _bootstrap() {
  try {
    const r = await fetch(`${API_BASE}/auth/token`);
    const d = await r.json();
    _token = d.token;
  } catch (_) {}
})();

function _headers(extra = {}) {
  return { "Content-Type": "application/json", "X-Banshee-Token": _token, ...extra };
}

async function _fetch(url, opts = {}) {
  await _ready;
  const h = { "X-Banshee-Token": _token, ...(opts.headers || {}) };
  return fetch(url, { ...opts, headers: h });
}

/* fetch OHLCV for a symbol+tf from Core; returns LW-formatted candles.
   opts.deep=true requests the fast-then-complete Stage-2 upgrade. */
async function fetchOHLCV(sym, tf, opts = {}) {
  const mode    = TF_TO_MODE[tf] || "swing";
  const coreKey = TF_CORE_KEY[tf] || tf.toLowerCase();
  const pair    = coreSymbol(sym);
  const deepQS  = opts.deep ? "&deep=1" : "";
  try {
    const res  = await _fetch(`${API_BASE}/ohlcv?symbol=${encodeURIComponent(pair)}&mode=${mode}${deepQS}`);
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
    /* No real bars for this symbol+timeframe (Core down, unsupported symbol, or a
       provider returned nothing). NEVER fabricate candles on a trading chart — an
       honest empty state is safer than fake prices. The caller renders "no real data". */
    console.warn(`[api] no real OHLCV for ${sym}/${tf}:`, err.message);
    return { candles: [], indicators: null, source: "nodata" };
  }
}

/* fetch Asset Radar data for a symbol */
async function fetchRadar(sym, mode = "swing") {
  const pair = coreSymbol(sym);
  try {
    const res  = await _fetch(`${API_BASE}/radar?symbol=${encodeURIComponent(pair)}&mode=${mode}&output_mode=full`);
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
    const res = await _fetch(`${API_BASE}/macro/sensors`);
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
    const res  = await _fetch(`${API_BASE}/smc/json?symbol=${encodeURIComponent(pair)}&ltf=${ltf}`);
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
    const res = await _fetch(`${API_BASE}/presets`);
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
    await _fetch(`${API_BASE}/presets`, {
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
    const res = await _fetch(`${API_BASE}/xabcd?symbol=${encodeURIComponent(pair)}`);
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
    const res = await _fetch(`${API_BASE}/geo-harmonic?symbol=${encodeURIComponent(pair)}&multi_window=true`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (err) {
    console.warn(`[api] GH fallback for ${sym}:`, err.message);
    return null;
  }
}


/* request an AI synthesis briefing for a symbol — POSTs to /ai/briefing
 * tab: "nexus" | "smc" | "gh" — controls prompt focus and format
 * signal: optional AbortSignal to cancel a stale in-flight request
 */
async function fetchAIBriefing(sym, mode = "swing", tab = "nexus", signal = null, manualStories = []) {
  const pair = coreSymbol(sym);
  try {
    const res = await _fetch(`${API_BASE}/ai/briefing`, {
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
    const res = await _fetch(`${API_BASE}/settings`);
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
    const res = await _fetch(`${API_BASE}/settings`, {
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
    const res = await _fetch(`${API_BASE}/settings/test`, {
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
    const res = await _fetch(`${API_BASE}/strategies/data`);
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
    const res = await _fetch(`${API_BASE}/execution-plan`, {
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
    const res = await _fetch(`${API_BASE}/journal/trades`);
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
    const res = await _fetch(`${API_BASE}/journal/close`, {
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
    const res = await _fetch(`${API_BASE}/journal/update-levels`, {
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
    const res = await _fetch(`${API_BASE}/journal/update-outcome`, {
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
    const res = await _fetch(`${API_BASE}/journal/sync-alpaca`, { method: "POST" });
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
    const res = await _fetch(`${API_BASE}/journal/feedback-synthesis`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (err) { return { error: err.message }; }
}

/* fetch the latest Predator briefing */
async function fetchPredatorBriefing() {
  try {
    const res = await _fetch(`${API_BASE}/predator/briefing`);
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
    const res = await _fetch(`${API_BASE}/predator/run`, {
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
    const res = await _fetch(`${API_BASE}/journal/open`, {
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

async function fetchRotation() {
  try {
    const res = await _fetch(`${API_BASE}/rotation`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (err) {
    console.warn("[api] fetchRotation:", err.message);
    return { error: err.message, sectors: [], camd_alerts: [], spy_roc_21: null, macro_env: null, timestamp: null };
  }
}

/* fetch all portfolios */
async function fetchPortfolios() {
  try {
    const res = await _fetch(`${API_BASE}/portfolios`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (err) {
    console.warn("[api] fetchPortfolios:", err.message);
    return null;
  }
}

/* create a new portfolio */
async function createPortfolio(portfolio) {
  try {
    const res = await _fetch(`${API_BASE}/portfolios`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(portfolio),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (err) {
    console.warn("[api] createPortfolio:", err.message);
    return { error: err.message };
  }
}

/* update a portfolio by id */
async function updatePortfolio(id, updates) {
  try {
    const res = await _fetch(`${API_BASE}/portfolios/${id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(updates),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (err) {
    console.warn("[api] updatePortfolio:", err.message);
    return { error: err.message };
  }
}

/* fetch analysis for a portfolio by id */
async function fetchPortfolioAnalysis(id) {
  try {
    const res = await _fetch(`${API_BASE}/portfolios/${id}/analysis`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (err) {
    console.warn("[api] fetchPortfolioAnalysis:", err.message);
    return { error: err.message };
  }
}

/* resolve / validate a symbol (entry-time check). Fail-open: a network error
   returns resolved:true so a blip never shows a false "unknown symbol". */
async function resolveSymbol(sym) {
  try {
    const res = await _fetch(`${API_BASE}/resolve-symbol?sym=${encodeURIComponent(sym)}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (err) {
    console.warn("[api] resolveSymbol:", err.message);
    return { resolved: true, suggestion: null, reason: null };
  }
}

/* fetch the curated Wheel options universe list */
async function fetchOptionsUniverse() {
  try {
    const r = await _fetch(`${API_BASE}/options/universe`);
    if (!r.ok) return { universe: [] };
    return await r.json();
  } catch (e) { console.warn("[api] fetchOptionsUniverse:", e.message); return { universe: [] }; }
}

/* fetch the single best Cash-Secured Put candidate from the Wheel universe */
async function fetchOptionsCandidate(accountSize) {
  try {
    const q = accountSize ? `?account_size=${encodeURIComponent(accountSize)}` : "";
    const r = await _fetch(`${API_BASE}/options/candidate${q}`);
    if (!r.ok) return { candidate: null, error_note: "Options scan unavailable." };
    return await r.json();
  } catch (e) { console.warn("[api] fetchOptionsCandidate:", e.message); return { candidate: null, error_note: "Options scan unavailable." }; }
}

/* grade a user-composed option against Banshee's rules (inverse of the candidate search) */
async function gradeOption(spec) {
  try {
    const r = await _fetch(`${API_BASE}/options/grade`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(spec),
    });
    const body = await r.json();
    if (!r.ok) return { error: (body && body.error) || `HTTP ${r.status}` };
    return body;
  } catch (e) {
    console.warn("[api] gradeOption:", e.message);
    return { error: "Couldn't reach the grader — try again in a moment." };
  }
}

/* ── Options Learning Engine (Spec 2) ────────────────────────────────────── */

async function runScenario(spec, terminalPrice) {
  try {
    const r = await _fetch(`${API_BASE}/options/scenario`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ spec, terminal_price: terminalPrice }),
    });
    return r.ok ? r.json() : { error: (await r.json()).detail?.error || 'Scenario failed.' };
  } catch (e) { return { error: 'Scenario unavailable — try again.' }; }
}

async function learnRecap(run) {
  try {
    const r = await _fetch(`${API_BASE}/options/learn/recap`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ run }),
    });
    return r.ok ? r.json() : { text: 'Narration unavailable.' };
  } catch (e) { return { text: 'Narration unavailable.' }; }
}

async function learnCompare(runA, runB) {
  try {
    const r = await _fetch(`${API_BASE}/options/learn/compare`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ run_a: runA, run_b: runB }),
    });
    return r.ok ? r.json() : { text: 'Comparison unavailable.' };
  } catch (e) { return { text: 'Comparison unavailable.' }; }
}

async function learnWhyNot(graded, run) {
  try {
    const r = await _fetch(`${API_BASE}/options/learn/why-not`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ graded, run }),
    });
    return r.ok ? r.json() : { text: 'Narration unavailable.' };
  } catch (e) { return { text: 'Narration unavailable.' }; }
}

/* ── Simulated Wheel FSM ──────────────────────────────────────────────────── */

/* list all active wheel positions */
async function listWheels() {
  try {
    const res = await _fetch(`${API_BASE}/wheels`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (err) {
    console.warn("[api] listWheels:", err.message);
    return { error: err.message };
  }
}

/* create a new wheel position */
async function createWheel(body) {
  try {
    const res = await _fetch(`${API_BASE}/wheels`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      const errBody = await res.json().catch(() => ({}));
      throw new Error(errBody.error || `HTTP ${res.status}`);
    }
    return await res.json();
  } catch (err) {
    console.warn("[api] createWheel:", err.message);
    return { error: err.message };
  }
}

/* get a single wheel position by id */
async function getWheel(id) {
  try {
    const res = await _fetch(`${API_BASE}/wheels/${id}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (err) {
    console.warn("[api] getWheel:", err.message);
    return { error: err.message };
  }
}

/* post a state-machine event to a wheel position */
async function postWheelEvent(id, event) {
  try {
    const res = await _fetch(`${API_BASE}/wheels/${id}/event`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ event }),
    });
    if (!res.ok) {
      const errBody = await res.json().catch(() => ({}));
      throw new Error(errBody.error || `HTTP ${res.status}`);
    }
    return await res.json();
  } catch (err) {
    console.warn("[api] postWheelEvent:", err.message);
    return { error: err.message };
  }
}

/* delete a wheel position by id */
async function deleteWheel(id) {
  try {
    const res = await _fetch(`${API_BASE}/wheels/${id}`, { method: "DELETE" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (err) {
    console.warn("[api] deleteWheel:", err.message);
    return { error: err.message };
  }
}

/* ── Paper Wheel FSM (Alpaca paper trading) ──────────────────────────────── */

/* list all paper wheel positions */
async function listPaperWheels() {
  const r = await _fetch(`${API_BASE}/paper-wheels`);
  if (!r.ok) throw await r.json();
  return r.json();
}

/* get a single paper wheel by id */
async function getPaperWheel(id) {
  const r = await _fetch(`${API_BASE}/paper-wheels/${id}`);
  if (!r.ok) throw await r.json();
  return r.json();
}

/* create a new paper wheel position */
async function createPaperWheel(body) {
  const r = await _fetch(`${API_BASE}/paper-wheels`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw await r.json();
  return r.json();
}

/* submit a covered call order on a paper wheel */
async function submitPaperCC(wheelId, body) {
  const r = await _fetch(`${API_BASE}/paper-wheels/${wheelId}/submit-cc`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw await r.json();
  return r.json();
}

/* fetch the calls chain for a paper wheel (used when state===SHARES) */
async function getPaperWheelCalls(wheelId) {
  const r = await _fetch(`${API_BASE}/paper-wheels/${wheelId}/calls`);
  if (!r.ok) throw await r.json();
  return r.json();
}

/* delete a paper wheel by id */
async function deletePaperWheel(id) {
  const r = await _fetch(`${API_BASE}/paper-wheels/${id}`, { method: "DELETE" });
  if (!r.ok) throw await r.json();
  return r.json();
}

/* fetch wheels that need attention (alert strip) */
async function getPaperWheelAlerts() {
  const r = await _fetch(`${API_BASE}/paper-wheels/alerts`);
  if (!r.ok) throw await r.json();
  return r.json();
}

/* post a manual FSM event to a paper wheel */
async function postPaperWheelEvent(wheelId, event) {
  const r = await _fetch(`${API_BASE}/paper-wheels/${wheelId}/event`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ event }),
  });
  if (!r.ok) throw await r.json();
  return r.json();
}

async function analyzeGridbot(sym, capital, gridCount, feePct, rangeMin = null, rangeMax = null) {
  const body = { sym, capital, grid_count: gridCount, fee_pct: feePct };
  if (rangeMin != null && rangeMax != null) { body.range_min = rangeMin; body.range_max = rangeMax; }
  const r = await _fetch(`${API_BASE}/gridbot/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw await r.json();
  return r.json();
}

async function deployPaperGridbot(sym, capital, gridCount, feePct, rangeMin = null, rangeMax = null) {
  const body = { sym, capital, grid_count: gridCount, fee_pct: feePct };
  if (rangeMin != null && rangeMax != null) { body.range_min = rangeMin; body.range_max = rangeMax; }
  const r = await _fetch(`${API_BASE}/gridbot/paper`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw await r.json();
  return r.json();
}

async function getPaperGridbot() {
  const r = await _fetch(`${API_BASE}/gridbot/paper`);
  if (r.status === 404) return null;
  if (!r.ok) throw await r.json();
  return r.json();
}

async function stopPaperGridbot() {
  const r = await _fetch(`${API_BASE}/gridbot/paper`, { method: "DELETE" });
  if (!r.ok) throw await r.json();
  return r.json();
}

async function shutdownBanshee() {
  try {
    await _fetch(`${API_BASE}/shutdown`, { method: "POST" });
  } catch (_) { /* server dies mid-response — expected */ }
  return { ok: true };
}

/* fetch per-provider speed tier data for the DATA SOURCES settings section */
async function fetchDataSourceSpeed() {
  const r = await _fetch(`${API_BASE}/settings/data-sources/speed`);
  return r.ok ? r.json() : null;
}

/* test CoinGecko connectivity (and save key first) */
async function testCoinGecko() {
  const r = await _fetch(`${API_BASE}/settings/data-sources/test-coingecko`, {
    method: "POST", body: "{}", headers: { "Content-Type": "application/json" },
  });
  return r.ok ? r.json() : null;
}

/* test custom provider connectivity */
async function testCustomSource() {
  const r = await _fetch(`${API_BASE}/settings/data-sources/test-custom`, {
    method: "POST", body: "{}", headers: { "Content-Type": "application/json" },
  });
  return r.ok ? r.json() : null;
}

async function fetchAuditEntries({ limit = 50, tool = "", since = "", offset = 0 } = {}) {
  try {
    const q = new URLSearchParams();
    q.set("limit", limit);
    q.set("offset", offset);
    if (tool) q.set("tool", tool);
    if (since) q.set("since", since);
    const res = await _fetch(`${API_BASE}/audit/entries?${q}`);
    if (!res.ok) return { total: 0, entries: [], error: await res.text() };
    return await res.json();
  } catch (e) {
    return { total: 0, entries: [], error: e.message };
  }
}

async function fetchAuditSummary(days = 7) {
  try {
    const res = await _fetch(`${API_BASE}/audit/summary?days=${days}`);
    if (!res.ok) return { error: await res.text() };
    return await res.json();
  } catch (e) {
    return { error: e.message };
  }
}

/* fetch current Unleashed mode state */
async function fetchUnleashed() {
  try {
    const res = await _fetch(`${API_BASE}/unleashed`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();            // {enabled: bool}
  } catch (err) {
    console.warn("[api] fetchUnleashed:", err.message);
    return { enabled: false };
  }
}

/* set Unleashed mode state; returns {status, enabled} */
async function setUnleashed(enabled) {
  try {
    const res = await _fetch(`${API_BASE}/unleashed`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ enabled }),
    });
    return (await res.json());
  } catch (err) {
    console.warn("[api] setUnleashed:", err.message);
    return { enabled };
  }
}

async function fetchUnleashedProfiles() {
  try {
    const res = await _fetch(`${API_BASE}/unleashed/profiles`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();            // {active, profiles:[{id,name,override,locked}]}
  } catch (err) {
    console.warn("[api] fetchUnleashedProfiles:", err.message);
    return { active: "default", profiles: [] };
  }
}

async function saveUnleashedProfile(profile) {    // {id?, name, surfaces}
  try {
    const res = await _fetch(`${API_BASE}/unleashed/profiles`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(profile),
    });
    const data = await res.json();
    if (!res.ok) return { status: "error", message: data.detail || `HTTP ${res.status}` };
    return { status: "saved", id: data.id };
  } catch (err) {
    console.warn("[api] saveUnleashedProfile:", err.message);
    return { status: "error", message: err.message };
  }
}

/* fetch the base (built-in) Unleashed prompt text for a surface ("nexus" | "smc") */
async function fetchBasePrompt(surface) {
  try {
    const res = await _fetch(`${API_BASE}/unleashed/base?surface=${encodeURIComponent(surface)}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();            // {surface, text}
  } catch (err) {
    console.warn("[api] fetchBasePrompt:", err.message);
    return { surface, text: "" };
  }
}

async function setActiveUnleashedProfile(id) {
  try {
    const res = await _fetch(`${API_BASE}/unleashed/profiles/active`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id }),
    });
    const data = await res.json();
    if (!res.ok) return { status: "error", message: data.detail || `HTTP ${res.status}` };
    return { status: "saved", active: data.active };
  } catch (err) {
    console.warn("[api] setActiveUnleashedProfile:", err.message);
    return { status: "error", message: err.message };
  }
}

async function deleteUnleashedProfile(id) {
  try {
    const res = await _fetch(`${API_BASE}/unleashed/profiles/${id}`, { method: "DELETE" });
    const data = await res.json();
    if (!res.ok) return { status: "error", message: data.detail || `HTTP ${res.status}` };
    return { status: "deleted" };
  } catch (err) {
    console.warn("[api] deleteUnleashedProfile:", err.message);
    return { status: "error", message: err.message };
  }
}

window.API = { fetchOHLCV, fetchRadar, fetchMacro, fetchSMC, fetchPresets, savePresets, fetchGH, fetchXABCD, fetchAIBriefing, fetchSettings, saveSettings, testAIConnection, fetchStrategies, fetchExecutionPlan, fetchTrades, closeTrade, updateLevels, updateOutcome, syncAlpaca, fetchFeedbackSynthesis, fetchPredatorBriefing, runPredator, journalOpen, coreSymbol, fetchRotation, fetchPortfolios, createPortfolio, updatePortfolio, fetchPortfolioAnalysis, resolveSymbol, fetchOptionsUniverse, fetchOptionsCandidate, gradeOption, listWheels, createWheel, getWheel, postWheelEvent, deleteWheel, runScenario, learnRecap, learnCompare, learnWhyNot, listPaperWheels, getPaperWheel, createPaperWheel, submitPaperCC, getPaperWheelCalls, deletePaperWheel, getPaperWheelAlerts, postPaperWheelEvent, analyzeGridbot, deployPaperGridbot, getPaperGridbot, stopPaperGridbot, shutdownBanshee, fetchDataSourceSpeed, testCoinGecko, testCustomSource, fetchAuditEntries, fetchAuditSummary, fetchUnleashed, setUnleashed, fetchUnleashedProfiles, saveUnleashedProfile, fetchBasePrompt, setActiveUnleashedProfile, deleteUnleashedProfile };
