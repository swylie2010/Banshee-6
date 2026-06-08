/* Banshee — synthetic market data */

const ASSETS = [
  // crypto
  { sym: "BTC", pair: "BTC/USD", name: "Bitcoin",        cls: "CRYPTO", price: 67420.50, chg: 2.41,  edge: 84, verdict: "BUY",  bias: "↑ STRONG", vol: 1.42, rsi: 64, atr: 1820 },
  { sym: "ETH", pair: "ETH/USD", name: "Ethereum",       cls: "CRYPTO", price: 3842.18,  chg: 1.62,  edge: 71, verdict: "BUY",  bias: "↑ MILD",   vol: 1.10, rsi: 58, atr: 142 },
  { sym: "SOL", pair: "SOL/USD", name: "Solana",         cls: "CRYPTO", price: 182.54,   chg: -0.84, edge: 58, verdict: "WAIT", bias: "→ FLAT",   vol: 1.85, rsi: 51, atr: 8.2 },
  { sym: "AVAX",pair: "AVAX/USD",name: "Avalanche",      cls: "CRYPTO", price: 38.92,    chg: -2.15, edge: 41, verdict: "SELL", bias: "↓ MILD",   vol: 2.04, rsi: 38, atr: 2.1 },
  // mega tech
  { sym: "NVDA", pair: "NVDA",  name: "NVIDIA",          cls: "EQUITY", price: 138.20,   chg: 3.18,  edge: 91, verdict: "BUY",  bias: "↑ STRONG", vol: 0.92, rsi: 71, atr: 4.8 },
  { sym: "AAPL", pair: "AAPL",  name: "Apple",           cls: "EQUITY", price: 213.45,   chg: -1.42, edge: 32, verdict: "SELL", bias: "↓ MILD",   vol: 0.61, rsi: 34, atr: 3.2 },
  { sym: "MSFT", pair: "MSFT",  name: "Microsoft",       cls: "EQUITY", price: 432.10,   chg: 0.84,  edge: 76, verdict: "BUY",  bias: "↑ MILD",   vol: 0.58, rsi: 62, atr: 6.4 },
  { sym: "GOOGL",pair: "GOOGL", name: "Alphabet",        cls: "EQUITY", price: 174.55,   chg: 0.21,  edge: 62, verdict: "WAIT", bias: "→ FLAT",   vol: 0.71, rsi: 53, atr: 2.9 },
  { sym: "META", pair: "META",  name: "Meta Platforms",  cls: "EQUITY", price: 542.30,   chg: 1.08,  edge: 79, verdict: "BUY",  bias: "↑ MILD",   vol: 0.74, rsi: 64, atr: 9.1 },
  { sym: "AMD",  pair: "AMD",   name: "Adv. Micro Dev.", cls: "EQUITY", price: 156.40,   chg: -2.62, edge: 28, verdict: "SELL", bias: "↓ STRONG", vol: 1.21, rsi: 31, atr: 5.6 },
  { sym: "TSLA", pair: "TSLA",  name: "Tesla",           cls: "EQUITY", price: 246.80,   chg: 0.42,  edge: 49, verdict: "WAIT", bias: "→ FLAT",   vol: 1.34, rsi: 47, atr: 7.8 },
  // macro / indices
  { sym: "SPY",  pair: "SPY",   name: "S&P 500 ETF",     cls: "INDEX",  price: 578.20,   chg: 0.62,  edge: 68, verdict: "BUY",  bias: "↑ MILD",   vol: 0.42, rsi: 58, atr: 4.1 },
  { sym: "QQQ",  pair: "QQQ",   name: "Nasdaq 100 ETF",  cls: "INDEX",  price: 501.15,   chg: 0.91,  edge: 73, verdict: "BUY",  bias: "↑ MILD",   vol: 0.51, rsi: 61, atr: 5.2 },
  { sym: "DXY",  pair: "DXY",   name: "USD Index",       cls: "MACRO",  price: 104.85,   chg: -0.18, edge: 51, verdict: "WAIT", bias: "→ FLAT",   vol: 0.32, rsi: 49, atr: 0.42 },
  { sym: "TLT",  pair: "TLT",   name: "20Y Treasuries",  cls: "MACRO",  price: 89.25,    chg: -0.34, edge: 47, verdict: "WAIT", bias: "↓ MILD",   vol: 0.48, rsi: 44, atr: 0.81 },
  { sym: "VIX",  pair: "VIX",   name: "Volatility Idx.", cls: "MACRO",  price: 14.21,    chg: 4.82,  edge: 38, verdict: "WAIT", bias: "↑ MILD",   vol: 2.14, rsi: 56, atr: 1.2 },
  // commodities
  { sym: "GOLD", pair: "XAU/USD",name: "Gold Spot",      cls: "COMMOD", price: 2654.10,  chg: 0.78,  edge: 82, verdict: "BUY",  bias: "↑ STRONG", vol: 0.54, rsi: 67, atr: 18.4 },
  { sym: "SILV", pair: "XAG/USD",name: "Silver Spot",    cls: "COMMOD", price: 31.42,    chg: 1.21,  edge: 74, verdict: "BUY",  bias: "↑ MILD",   vol: 0.92, rsi: 62, atr: 0.62 },
  { sym: "OIL",  pair: "WTI",   name: "WTI Crude",       cls: "COMMOD", price: 73.41,    chg: -1.38, edge: 38, verdict: "SELL", bias: "↓ MILD",   vol: 1.04, rsi: 41, atr: 1.4 },
  { sym: "NGAS", pair: "NG",    name: "Natural Gas",     cls: "COMMOD", price: 2.84,     chg: 2.94,  edge: 64, verdict: "WAIT", bias: "↑ MILD",   vol: 1.84, rsi: 54, atr: 0.12 },
];

const WATCHLISTS = [
  { id: "all",    name: "ALL SIGNALS",    syms: ASSETS.map(a => a.sym), tag: "WL-00" },
  { id: "crypto", name: "CRYPTO MAJORS",  syms: ["BTC","ETH","SOL","AVAX"], tag: "WL-01" },
  { id: "tech",   name: "TECH MEGACAPS",  syms: ["NVDA","AAPL","MSFT","GOOGL","META","AMD","TSLA"], tag: "WL-02" },
  { id: "macro",  name: "MACRO / INDEX",  syms: ["SPY","QQQ","DXY","TLT","VIX"], tag: "WL-03" },
  { id: "commod", name: "COMMODITIES",    syms: ["GOLD","SILV","OIL","NGAS"], tag: "WL-04" },
  { id: "alpha",  name: "TOP EDGE ≥ 70",  syms: ASSETS.filter(a => a.edge >= 70).map(a => a.sym), tag: "WL-05" },
];

/* deterministic pseudo-random walk for charts */
function seedRand(seed) {
  let s = seed >>> 0;
  return () => {
    s = (s * 1664525 + 1013904223) >>> 0;
    return (s & 0xfffffff) / 0xfffffff;
  };
}
function hashStr(str) {
  let h = 2166136261;
  for (let i = 0; i < str.length; i++) {
    h ^= str.charCodeAt(i);
    h = (h * 16777619) >>> 0;
  }
  return h;
}
/* generate candles for a symbol + tf */
function buildCandles(sym, tf, n = 80) {
  const TF_VOL = { "1m": 0.0008, "5m": 0.0016, "15m": 0.003, "1H": 0.006, "4H": 0.012, "1D": 0.024, "1W": 0.06 };
  const TF_DRIFT = { "1m": 0, "5m": 0, "15m": 0.0001, "1H": 0.0002, "4H": 0.0004, "1D": 0.0008, "1W": 0.0014 };
  const a = ASSETS.find(x => x.sym === sym);
  if (!a) return [];
  const rng = seedRand(hashStr(sym + tf));
  const trend = a.chg > 0 ? 1 : a.chg < 0 ? -1 : 0;
  const vol = TF_VOL[tf] * (a.vol || 1);
  const drift = TF_DRIFT[tf] * trend;
  let p = a.price * (1 - (n * (drift * 0.6) + (rng() - 0.5) * vol * 4));
  const out = [];
  for (let i = 0; i < n; i++) {
    const o = p;
    const change = (drift + (rng() - 0.5) * vol);
    const c = o * (1 + change);
    const h = Math.max(o, c) * (1 + rng() * vol * 0.6);
    const l = Math.min(o, c) * (1 - rng() * vol * 0.6);
    out.push({ o, h, l, c });
    p = c;
  }
  /* ensure last close close to current price */
  const lastClose = out[out.length - 1].c;
  const scale = a.price / lastClose;
  return out.map(k => ({ o: k.o * scale, h: k.h * scale, l: k.l * scale, c: k.c * scale }));
}

const TIMEFRAMES = ["15m","1H","4H","1D","1W"];

const MACRO = {
  warning: 64,           // 0-100, higher = more risk
  regime: "RISK-ON",     // or RISK-OFF
  vix: 14.21,
  dxy: 104.85,
  yld10: 4.21,
  liquidity: 58,         // 0-100
  breadth: 62,           // 0-100
  cycleDay: 142,
  sessionTime: "09:42:18 EST",
  flags: [
    { k: "VIX",  v: "14.2",  st: "calm" },
    { k: "DXY",  v: "104.8", st: "neutral" },
    { k: "10Y",  v: "4.21%", st: "elevated" },
    { k: "HY-OAS", v: "298bp", st: "calm" },
    { k: "BREADTH", v: "62%", st: "neutral" },
    { k: "SKEW", v: "138.2", st: "elevated" },
  ],
};

const NEWS = [
  { t: "09:41", tag: "MACRO",  txt: "FOMC minutes — markets expect 25bp cut at next meeting" },
  { t: "09:38", tag: "EARN",   txt: "NVDA guides Q3 above consensus, data center +154% YoY" },
  { t: "09:31", tag: "FLOW",   txt: "Equity ETF inflows $4.2B w/w — broadest since Nov '24" },
  { t: "09:24", tag: "CRYPTO", txt: "BTC ETF net inflow +$284M, IBIT leads" },
  { t: "09:18", tag: "MACRO",  txt: "China Nov PMI 50.4, services 49.8 — mixed signal" },
  { t: "09:12", tag: "FX",     txt: "USDJPY rejected 156, BoJ jawboning continues" },
  { t: "09:04", tag: "CRED",   txt: "HY-OAS at 298bp — tightest in 18 months" },
];

window.ASSETS = ASSETS;
window.WATCHLISTS = WATCHLISTS;
window.TIMEFRAMES = TIMEFRAMES;
window.MACRO = MACRO;
window.NEWS = NEWS;
window.buildCandles = buildCandles;
