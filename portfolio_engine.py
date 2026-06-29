"""
portfolio_engine.py — Banshee 6 Portfolio Analysis Engine

Accepts DataFrames; never calls yfinance directly (adapter pattern).
"""

import sys
import numpy as np
import pandas as pd
from datetime import date as _date
from shared_data import load_providers, fetch_sector_closes
import micro_engine
import sector_rotation_engine
import banshee_ai
import ledger_engine
from core_state import _load_macro_cache, _sanitize
import data_providers as _dp
from cache_utils import ttl_cache

_SECTOR_ETF_MAP = {
    "TECH":     "XLK",
    "FINANCE":  "XLF",
    "CRYPTO":   "IBIT",
    "COMMS":    "XLC",
    "ENERGY":   "XLE",
    "HEALTH":   "XLV",
    "CONSUMER": "XLY",
    "UTILITY":  "XLU",
}

_GRADE_THRESHOLDS = [
    (95, "A+"), (90, "A"), (85, "A-"),
    (80, "B+"), (75, "B"), (70, "B-"),
    (65, "C+"), (60, "C"), (55, "C-"),
    (50, "D"),  (0,  "F"),
]


def score_to_grade(score: float) -> str:
    """Map 0-100 score to letter grade."""
    for threshold, grade in _GRADE_THRESHOLDS:
        if score >= threshold:
            return grade
    return "F"


def risk_metrics(portfolio_returns, benchmark_returns) -> dict:
    """Sharpe / max-drawdown / alpha / beta from a REAL daily portfolio return
    series (weighted blend of the holdings' actual price history). Returns all
    None when there isn't enough history — honest beats fabricated.

    portfolio_returns: daily returns Series for the actual portfolio (or None).
    benchmark_returns: blended benchmark daily returns Series (or empty).
    """
    out = {"sharpe": None, "alpha": None, "beta": None, "max_drawdown": None}
    if portfolio_returns is None or len(portfolio_returns) < 30:
        return out
    try:
        import quantstats as qs
        out["sharpe"]       = round(float(qs.stats.sharpe(portfolio_returns)), 3)
        out["max_drawdown"] = round(float(qs.stats.max_drawdown(portfolio_returns)), 4)
        if benchmark_returns is not None and not benchmark_returns.empty:
            out["alpha"], out["beta"] = _compute_alpha_beta(portfolio_returns, benchmark_returns)
    except Exception:
        pass
    return out


def run(holdings: pd.DataFrame, benchmark_returns: pd.Series, portfolio_returns=None) -> dict:
    """
    holdings: DataFrame with columns:
        sym (str), shares (float), entry_price (float|None),
        entry_date (str|None), current_price (float), cls (str)
    benchmark_returns: pre-fetched daily returns Series (DatetimeIndex)
    portfolio_returns: REAL daily return series for the actual weighted portfolio,
                       used for risk metrics. None → risk metrics come back None.
    Returns dict with keys: sharpe, alpha, beta, max_drawdown, twrr,
                            total_value, weights (list of dicts)
    """
    df = holdings.copy()
    df["value"]  = df["shares"] * df["current_price"]
    total_value  = df["value"].sum()

    if total_value <= 0:
        return {"error": "zero portfolio value"}

    df["weight"] = df["value"] / total_value

    # TWRR — Modified Dietz (simplified: per-holding return weighted by weight)
    has_entry = df.dropna(subset=["entry_price"])
    twrr = None
    if not has_entry.empty:
        gains = [
            ((row["current_price"] - row["entry_price"]) / row["entry_price"]) * row["weight"]
            for _, row in has_entry.iterrows()
            if row["entry_price"] > 0
        ]
        twrr = round(sum(gains), 4) if gains else None

    # Risk metrics from the REAL weighted return series (not a synthetic scale of
    # the benchmark). None when history/returns unavailable.
    rm = risk_metrics(portfolio_returns, benchmark_returns)
    sharpe, alpha, beta, max_dd = rm["sharpe"], rm["alpha"], rm["beta"], rm["max_drawdown"]

    return {
        "sharpe":       sharpe,
        "alpha":        alpha,
        "beta":         beta,
        "max_drawdown": max_dd,
        "twrr":         twrr,
        "total_value":  round(total_value, 2),
        "weights":      df[["sym", "shares", "weight", "value", "cls"]].to_dict("records"),
    }


def _compute_alpha_beta(port: pd.Series, bench: pd.Series) -> tuple:
    aligned = pd.concat([port, bench], axis=1).dropna()
    if len(aligned) < 10:
        return 0.0, 1.0
    y = aligned.iloc[:, 0].values
    x = aligned.iloc[:, 1].values
    beta  = float(np.cov(y, x)[0, 1] / (np.var(x) or 1))
    alpha = float((np.mean(y) - beta * np.mean(x)) * 252)  # annualised
    return round(alpha, 4), round(beta, 3)


def build_blended_benchmark(sector_weights: dict, closes: pd.DataFrame) -> pd.Series:
    """
    sector_weights: { 'TECH': 0.48, 'CRYPTO': 0.38, 'COMMS': 0.14 }
    closes: DataFrame of daily close prices with ETF tickers as columns.
            Caller provides this (fetched via yfinance adapter in shared_data).
    Returns: blended daily returns Series.
    """
    if closes.empty or not sector_weights:
        return pd.Series(dtype=float)

    blended   = pd.Series(0.0, index=closes.index)
    spy_weight = 0.0

    for sector, weight in sector_weights.items():
        etf = _SECTOR_ETF_MAP.get(sector.upper())
        if etf and etf in closes.columns:
            blended += closes[etf].pct_change().fillna(0) * weight
        else:
            spy_weight += weight  # unmapped → proxy to SPY

    if spy_weight > 0 and "SPY" in closes.columns:
        blended += closes["SPY"].pct_change().fillna(0) * spy_weight

    return blended.dropna()


def score_portfolio(
    engine_result: dict,
    radar_data: dict,
) -> dict:
    """
    engine_result: output of run()
    radar_data: { sym: { edge: float }, ... }  (from /radar endpoint)

    BASKET HEALTH grade = current momentum + trailing-year real risk only.
    Sector alignment was dropped from the grade (it was a hardcoded placeholder
    that conflated market rotation with basket quality); rotation is now surfaced
    separately as an informational note, not a judgment on the basket.

    Returns: { score, grade, momentum_score, risk_score }
    """
    weights_list = engine_result.get("weights", [])
    if not weights_list:
        return {"score": 0, "grade": "F", "momentum_score": 0,
                "risk_score": None}

    # Momentum: weighted average of edge scores
    total_w = sum(row["weight"] for row in weights_list) or 1
    momentum_score = sum(
        radar_data.get(row["sym"], {}).get("edge", 50) * (row["weight"] / total_w)
        for row in weights_list
    )
    momentum_score = min(100, max(0, round(momentum_score, 1)))

    sharpe = engine_result.get("sharpe")
    has_sharpe = sharpe is not None
    risk_score = None

    if has_sharpe:
        risk_score = min(100, max(0, round((sharpe / 2.0) * 100, 1)))
        # Momentum-led, real risk a meaningful counterweight.
        score = momentum_score * 0.60 + risk_score * 0.40
    else:
        # No trailing-year risk history → grade is pure basket momentum.
        score = momentum_score

    return {
        "score":          round(score, 1),
        "grade":          score_to_grade(score),
        "momentum_score": momentum_score,
        "risk_score":     risk_score,
    }


# ── Portfolio analysis helpers ─────────────────────────────────────────────────

def _fetch_radar_for_syms(syms: list) -> dict:
    """Portfolio-local version of fetch_all_radar_for_syms from routes/analysis.py."""
    from routes.analysis import get_ohlcv_cached
    cached_macro = _load_macro_cache()
    radar_sensors = cached_macro["mac_data"] if cached_macro and "mac_data" in cached_macro else None
    result = {}
    for sym in syms:
        try:
            tfs = get_ohlcv_cached(sym, "swing")
            if not tfs or "error" in tfs:
                continue
            r = micro_engine.run_analysis(sym, "swing", tfs, sensors=radar_sensors)
            if "error" not in r:
                result[sym] = r
        except Exception:
            pass
    return result


def _join_names(names: list) -> str:
    """'A' / 'A and B' — plain-English join for at most two names."""
    if not names:
        return ""
    return names[0] if len(names) == 1 else " and ".join(names[:2])


def _build_rotation_note(fred_key) -> dict | None:
    """Plain-English market sector-rotation note for the Portfolio page.

    Pure information — where market money is flowing right now — NOT a grade
    input and not a judgment on the user's basket. Mirrors the /rotation data
    path. Returns None on any failure (the UI just omits the section)."""
    try:
        closes = fetch_sector_closes()
        if closes.empty:
            return None
        rot = sector_rotation_engine.run(closes, fred_key)
        sectors = rot.get("sectors") or []
        if not sectors:
            return None
        # sectors arrive sorted by 21-day relative strength, strongest first.
        inflows  = [s for s in sectors if s["roc_21"] > 0][:3]
        outflows = [s for s in reversed(sectors) if s["roc_21"] < 0][:3]
        parts = []
        if inflows:
            parts.append("into "  + _join_names([s["name"] for s in inflows]))
        if outflows:
            parts.append("out of " + _join_names([s["name"] for s in outflows]))
        summary = ("Money is rotating " + ", ".join(parts) + ".") if parts \
                  else "Sector flows are mixed — no clear rotation right now."
        return {
            "summary":        summary,
            "inflows":        [{"name": s["name"], "roc_21": s["roc_21"]} for s in inflows],
            "outflows":       [{"name": s["name"], "roc_21": s["roc_21"]} for s in outflows],
            "interpretation": (rot.get("macro_env") or {}).get("interpretation"),
            "spy_roc_21":     rot.get("spy_roc_21"),
        }
    except Exception as e:
        print(f"[portfolio] rotation note failed: {e}", file=sys.stderr)
        return None


@ttl_cache(ttl=3600)
def _fetch_1y_closes(syms_key: tuple) -> pd.DataFrame:
    """1-year price history via pluggable provider chain. One fetch per symbol, combined.

    syms_key: tuple of symbols in yfinance form (e.g. "BTC-USD", "SPY", "AAPL").
    Returns DataFrame with symbol columns and DatetimeIndex matching the old yfinance shape.
    """
    # syms arrive in canonical dash form ("BTC-USD"); the provider chain expects
    # the slash pair form ("BTC/USD") for crypto. Convert back here. Equities pass through.
    def _to_dp(s: str) -> str:
        if s.endswith("-USD"):
            return s[:-4] + "/USD"
        return s

    closes = {}
    for sym in syms_key:
        try:
            df = _dp.fetch_ohlcv(_to_dp(sym), "1d", 260)
            if not df.empty and "close" in df.columns:
                closes[sym] = df.set_index("timestamp")["close"]
        except Exception:
            pass
    if not closes:
        return pd.DataFrame()
    return pd.DataFrame(closes)


def run_portfolio_analysis(portfolio: dict, today: str) -> dict:
    """Full portfolio analysis — called by routes/portfolio.py route handler.

    Returns the complete analysis dict (sanitized, JSON-safe).
    """

    holdings = portfolio.get("holdings", [])

    txns = portfolio.get("transactions") or []

    state = ledger_engine.replay(txns)
    positions = state["positions"]
    if not positions:
        return {"error": "Portfolio has no holdings"}

    # Static asset-class map from the legacy holdings (preserves sector tags like
    # TECH/FINANCE for the blended benchmark); fall back to a crypto/equity guess.
    cls_map = {h.get("sym"): h.get("cls") for h in holdings}

    def _cls_for_sym(sym):
        c = cls_map.get(sym)
        if c and c != "EQUITY":
            return c
        s = str(sym)
        return "CRYPTO" if ("/" in s or s.upper().endswith("-USD")) else (c or "EQUITY")

    syms = [p["sym"] for p in positions]

    # The closes DataFrame (from _fetch_1y_closes) is keyed by the canonical
    # "BTC-USD" dash form, not the app's "BTC/USD" display form. col_map maps each
    # position's display symbol → its column name in `closes`.
    def _canon_sym(s):
        s = str(s)
        return s.replace("/", "-") if "/" in s else s

    col_map = {p["sym"]: _canon_sym(p["sym"]) for p in positions}

    # Fetch current prices via the provider chain — include sector ETFs + SPY for blended benchmark
    sector_etfs = ["XLK", "XLF", "IBIT", "XLC", "XLE", "XLV", "XLY", "XLU", "SPY"]
    all_syms = list(dict.fromkeys(list(col_map.values()) + sector_etfs))  # dedupe, preserve order
    try:
        syms_key = tuple(sorted(all_syms))
        closes = _fetch_1y_closes(syms_key)
    except Exception as e:
        return {"error": f"Price fetch failed: {e}"}

    # Guard: if all providers are disabled / unavailable, closes will be empty and
    # every holding would show $0 — surface an actionable error instead.
    if closes.empty and positions:
        return {
            "error": "provider_unavailable",
            "user_message": "Enable a data provider to run portfolio analysis — Settings → Data Sources",
        }

    # Banshee's own radar prices assets that Yahoo can't (TAO/USD, SUI/USD are
    # absent from yfinance — "possibly delisted"). Fetch once; use it as a price
    # fallback here and for momentum scoring below.
    radar_data = _fetch_radar_for_syms(syms)

    # Build holdings rows from the replayed ledger positions: avg_cost is the
    # entry price, first_date is the entry date. Price from yfinance close,
    # falling back to radar price. Same shape the rest of the endpoint consumes.
    holdings_rows = []
    for p in positions:
        sym = p["sym"]
        col = col_map[sym]
        last = closes[col].iloc[-1] if col in closes.columns else None
        current_price = float(last) if last is not None and not pd.isna(last) else 0.0
        if current_price <= 0:
            rp = radar_data.get(sym, {}).get("price")
            if isinstance(rp, (int, float)) and rp > 0:
                current_price = float(rp)
        avg_cost = p["avg_cost"]
        holdings_rows.append({
            "sym": sym,
            "shares": p["shares"],
            "entry_price": avg_cost if avg_cost and avg_cost > 0 else None,
            "entry_date": p.get("first_date"),
            "current_price": current_price,
            "cls": _cls_for_sym(sym),
        })

    total_value  = sum(r["shares"] * r["current_price"] for r in holdings_rows)
    equal_weight = total_value <= 0   # no share counts entered → analyse as an equal-weight basket

    pe = sys.modules[__name__]  # reference self (this module) as pe

    # Build the REAL weighted daily-return series from the holdings' price history,
    # so Sharpe / drawdown / alpha / beta reflect this portfolio (not a synthetic
    # scaling of the benchmark). weight_of() returns each holding's weight.
    def _weighted_returns(weight_of):
        series = None
        for r in holdings_rows:
            w = weight_of(r)
            if w <= 0:
                continue
            col = col_map.get(r["sym"])
            if col and col in closes.columns:
                ret = closes[col].pct_change().fillna(0) * w
                series = ret if series is None else series.add(ret, fill_value=0)
        return series.dropna() if series is not None else None

    if equal_weight:
        # Equal-weight basket: 1/N each. No dollar value, but real return-based
        # risk metrics + momentum (radar edge) + sector alignment still grade it.
        n = len(holdings_rows) or 1
        weights = [{
            "sym": r["sym"], "shares": 0, "weight": round(1.0 / n, 4),
            "value": 0, "cls": r["cls"],
        } for r in holdings_rows]
        sector_weights = {}
        for r in holdings_rows:
            sector_weights[r["cls"]] = sector_weights.get(r["cls"], 0) + (1.0 / n)
        benchmark_returns = build_blended_benchmark(sector_weights, closes)
        port_returns = _weighted_returns(lambda r: 1.0 / n)
        rm = risk_metrics(port_returns, benchmark_returns)
        engine_result = {
            "sharpe": rm["sharpe"], "alpha": rm["alpha"], "beta": rm["beta"],
            "max_drawdown": rm["max_drawdown"], "twrr": None, "total_value": 0,
            "weights": weights, "equal_weight": True,
        }
    else:
        holdings_df = pd.DataFrame(holdings_rows)
        # Group by cls, use cls as sector proxy
        sector_weights = {}
        for r in holdings_rows:
            w = (r["shares"] * r["current_price"]) / total_value
            sector_weights[r["cls"]] = sector_weights.get(r["cls"], 0) + w
        benchmark_returns = build_blended_benchmark(sector_weights, closes)
        port_returns = _weighted_returns(lambda r: (r["shares"] * r["current_price"]) / total_value)
        engine_result = run(holdings_df, benchmark_returns, portfolio_returns=port_returns)
        if "error" in engine_result:
            return engine_result
        rm = risk_metrics(port_returns, benchmark_returns)

    # Normalise the engine's raw `edge` (unbounded bull−bear, can be negative) to
    # the 0-100 scale score_portfolio expects — same mapping the UI uses.
    for _sym, _r in radar_data.items():
        if isinstance(_r, dict) and isinstance(_r.get("edge"), (int, float)):
            _r["edge"] = max(0.0, min(100.0, round(50 + _r["edge"] * 2.5, 1)))

    # Score the portfolio — BASKET HEALTH = current momentum + trailing-year real
    # risk. Sector alignment is NOT a grade input; it's surfaced separately below
    # as an informational market-rotation note.
    scored = score_portfolio(engine_result, radar_data)

    # Market rotation note — informational context only (where market money is
    # flowing), never a judgment on the basket. Gracefully absent for all-crypto
    # books, since sector rotation is an equity-sector concept.
    rotation_note = None
    if any(r.get("cls") != "CRYPTO" for r in holdings_rows):
        rotation_note = _build_rotation_note(
            load_providers().get("FRED_API", {}).get("key"))

    # Cumulative return series (real weighted history) for the Returns chart
    returns_series = []
    if port_returns is not None and len(port_returns) > 0:
        cum = (1 + port_returns).cumprod() - 1
        for ts, v in cum.items():
            try:
                returns_series.append({
                    "time":  pd.Timestamp(ts).strftime("%Y-%m-%d"),
                    "value": round(float(v) * 100, 2),
                })
            except Exception:
                pass

    # Performance vs S&P 500 — two honest lenses:
    #   recent  : the current basket vs SPY over the last ~21 trading days
    #   overall : your actual return since entry vs SPY over each holding's own
    #             holding period (needs entry_price + entry_date) — this is what
    #             makes entry dates meaningful.
    performance = {}
    spy = closes["SPY"] if "SPY" in closes.columns else None
    try:
        if spy is not None and port_returns is not None and len(port_returns) > 5:
            spy_ret = spy.pct_change().reindex(port_returns.index).fillna(0)
            n = min(21, len(port_returns))
            p = float((1 + port_returns.tail(n)).prod() - 1) * 100
            b = float((1 + spy_ret.tail(n)).prod() - 1) * 100
            performance["recent"] = {"days": int(n), "portfolio": round(p, 1),
                                     "benchmark": round(b, 1), "vs_benchmark": round(p - b, 1)}
    except Exception:
        pass
    try:
        # Holdings with a usable entry price + date (tolerate bad dates per-row).
        dated = []
        for r in holdings_rows:
            ep, ed = r.get("entry_price"), r.get("entry_date")
            if not (ep and ep > 0 and ed and r["current_price"] > 0):
                continue
            try:
                dated.append((r, pd.Timestamp(ed)))
            except Exception:
                continue
        if dated and total_value > 0:
            # Entries can predate the 1y window (e.g. a 2022 dip buy) — fetch SPY
            # history back to the earliest entry so the benchmark spans the real period.
            start = (min(ts for _, ts in dated) - pd.Timedelta(days=5)).strftime("%Y-%m-%d")
            spy_df = _dp.fetch_ohlcv("SPY", "1d", 260)
            spy_long = None
            if not spy_df.empty:
                spy_df = spy_df[spy_df["timestamp"] >= pd.Timestamp(start)]
                if not spy_df.empty:
                    spy_long = spy_df.set_index("timestamp")["close"]
            if spy_long is not None and len(spy_long):
                spy_now = float(spy_long.iloc[-1])
                ov_you = ov_spy = ov_w = 0.0
                for r, ts in dated:
                    after = spy_long[spy_long.index >= ts]
                    if not len(after):
                        continue
                    w = (r["shares"] * r["current_price"]) / total_value
                    ov_you += (r["current_price"] / r["entry_price"] - 1) * w
                    ov_spy += (spy_now / float(after.iloc[0]) - 1) * w
                    ov_w += w
                if ov_w > 0:
                    py, bm = ov_you / ov_w * 100, ov_spy / ov_w * 100
                    performance["overall"] = {"portfolio": round(py, 1), "benchmark": round(bm, 1),
                                              "vs_benchmark": round(py - bm, 1), "coverage": round(ov_w, 3)}
    except Exception:
        pass

    # ── Phase 3: quarterly evolution one-liner ──────────────────────────
    # Reuse the already-fetched 1y `closes` (no new download). For a quarter-end
    # date, take the last close on/before it; fall back to the flat radar price
    # for coins yfinance can't price (TAO/SUI) so they stay in the basket.
    def _price_at(sym, d):
        col = col_map.get(sym)
        if col and col in closes.columns:
            try:
                ser = closes[col].loc[:pd.Timestamp(d)].dropna()
                if len(ser):
                    return float(ser.iloc[-1])
            except Exception:
                pass
        rp = radar_data.get(sym, {}).get("price")
        return float(rp) if isinstance(rp, (int, float)) and rp > 0 else None

    today_iso = _date.today().isoformat()
    earliest_txn = min((str(t.get("date", "")) for t in txns if t.get("date")),
                       default=None)
    try:
        evolution = ledger_engine.evolution_line(
            txns,
            ledger_engine.prev_quarter_end(today_iso),
            today_iso,
            _price_at,
            _cls_for_sym,
            ledger_engine.has_two_quarters(earliest_txn, today_iso),
        )
    except Exception:
        evolution = {"status": "unavailable", "reason": "internal",
                     "line": ledger_engine._INTERNAL_LINE}

    # Build full result
    result = {
        **engine_result,
        **scored,
        "holdings": holdings_rows,
        "sector_weights": sector_weights,
        "risk": rm if not equal_weight else {
            "sharpe": engine_result.get("sharpe"),
            "alpha": engine_result.get("alpha"),
            "beta": engine_result.get("beta"),
            "max_drawdown": engine_result.get("max_drawdown"),
        },
        "returns_series": returns_series,
        "performance": performance or None,
        "rotation": rotation_note,
        "evolution":       evolution,
        "cash":            state["cash"],
        "realized_pnl":    state["realized_pnl"],
        "total_deposited": state["total_deposited"],
        "total_return":    ledger_engine.total_return(
            state["realized_pnl"], state["total_deposited"], holdings_rows,
            opening_cost_basis=state.get("opening_cost_basis", 0.0)),
        "ledger_warnings": state["warnings"],
        "portfolio_id": portfolio.get("id", ""),
        "name": portfolio.get("name", ""),
    }

    # AI commentary
    try:
        providers = load_providers()
        ai_cfg = providers.get("AI_API", {})
        if ai_cfg and ai_cfg.get("key"):
            review = banshee_ai.portfolio_review(ai_cfg, portfolio, result)
            result["ai_review"] = review.dict()
        else:
            result["ai_review"] = None
    except Exception:
        result["ai_review"] = None

    return _sanitize(result)
