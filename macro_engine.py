"""
macro_engine.py — Banshee Pro Macro Regime Engine
=================================================
This engine calculates the global macro risk regime.
It determines if the environment is a "tailwind" or a "headwind"
for your specific trades by looking at VIX, Yield Curve, Liquidity, etc.
"""

import json
import hashlib
import feedparser
import pandas as pd
import numpy as np
import re
import time
from datetime import datetime, timedelta, timezone
from dateutil import parser as date_parser

from cache_utils import ttl_cache
from shared_data import fetch_yf_history, fetch_yf_fast_info

# ─────────────────────────────────────────────────────────────────
# FREE RSS NEWS FEEDS
# ─────────────────────────────────────────────────────────────────
FREE_RSS_FEEDS = [
    ("FED",        "https://www.federalreserve.gov/feeds/press_all.xml"),
    ("BLS",        "https://www.bls.gov/feed/bls_latest.rss"),
    ("TREASURY",   "https://home.treasury.gov/news/press-releases/rss.xml"),
    ("MARKETWATCH","https://feeds.marketwatch.com/marketwatch/topstories/"),
    ("CNBC",       "https://www.cnbc.com/id/100003114/device/rss/rss.html"),
    ("YAHOO_FIN",  "https://finance.yahoo.com/rss/topfinstories"),
    ("COINDESK",   "https://www.coindesk.com/arc/outboundfeeds/rss/"),
    ("ZEROHEDGE",  "https://feeds.feedburner.com/zerohedge/feed"),
]

EVENT_TRIGGERS = ["CPI", "PPI", "FOMC", "NFP", "INFLATION", "RATE",
                  "RECESSION", "TARIFF", "JOBS", "GDP", "UNEMPLOYMENT",
                  "POWELL", "FED", "YIELD", "TREASURY", "DEBT"]

STALE_HOURS   = 72
AGING_HOURS   = 24
FRESH_HOURS   = 6

def _parse_feed_date(entry) -> datetime | None:
    t = getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None)
    if t:
        try:
            return datetime.fromtimestamp(time.mktime(t), tz=timezone.utc)
        except Exception:
            pass
    raw_date = getattr(entry, "published", None) or getattr(entry, "updated", None)
    if raw_date:
        try:
            dt = date_parser.parse(raw_date)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            else:
                dt = dt.astimezone(timezone.utc)
            return dt
        except Exception:
            pass
    return None

def _freshness_label(age_hours: float) -> str:
    if age_hours < FRESH_HOURS: return "FRESH"
    elif age_hours < AGING_HOURS: return "CURRENT"
    elif age_hours < STALE_HOURS: return "AGING"
    else: return "STALE"

@ttl_cache(ttl=900)
def get_intel_feeds(dismissed_tuple: tuple = ()) -> tuple[list[dict], list[str]]:
    """Fetch free RSS feeds and identify macroeconomic triggers."""
    dismissed_ids = set(dismissed_tuple)
    now_utc  = datetime.now(tz=timezone.utc)
    stories  = []
    triggered_events = []

    for label, url in FREE_RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
        except Exception:
            continue
        
        for entry in feed.entries[:6]:
            title = entry.get("title", "").strip()
            link  = entry.get("link", "")
            if not title: continue

            raw_summary = entry.get("summary", "") or entry.get("description", "")
            clean_summary = re.sub(r'<[^>]+>', '', raw_summary).strip()
            if len(clean_summary) > 250: clean_summary = clean_summary[:247] + "..."

            raw_id = f"{label}:{title}"
            story_id = hashlib.md5(raw_id.encode()).hexdigest()[:12]

            if story_id in dismissed_ids: continue

            pub_dt = _parse_feed_date(entry)
            age_hours = (now_utc - pub_dt).total_seconds() / 3600 if pub_dt else 12
            freshness = _freshness_label(age_hours)

            title_upper = (title + " " + clean_summary).upper()
            story_triggers = [t for t in EVENT_TRIGGERS if t in title_upper]
            for t in story_triggers:
                if t not in triggered_events:
                    triggered_events.append(t)

            stories.append({
                "id":        story_id,
                "source":    label,
                "title":     title,
                "url":       link,
                "summary":   clean_summary,
                "published": pub_dt,
                "age_hours": age_hours,
                "freshness": freshness,
                "triggers":  story_triggers,
            })

    stories.sort(key=lambda s: s["age_hours"])
    return stories, triggered_events

def build_news_prompt_lines(stories: list[dict]) -> list[str]:
    lines = []
    for s in stories:
        if s["freshness"] == "STALE": continue
        tag = ""
        if s["freshness"] == "FRESH": tag = " [FRESH]"
        elif s["freshness"] == "AGING": tag = " [AGING]"
        summary_line = f"   Summary: {s['summary']}" if s.get('summary') else ""
        lines.append(f"[{s['source']}]{tag} {s['title']}\n{summary_line}")
    return lines

# ─────────────────────────────────────────────────────────────────
# MARKET TELEMETRY (Utilizing shared_data.py cache)
# ─────────────────────────────────────────────────────────────────
@ttl_cache(ttl=900)
def get_flight_data() -> dict:
    data = {}
    
    # 1. Single price snapshots
    for key, ticker in [("vix", "^VIX"), ("t10", "^TNX"), ("t03", "^IRX"), ("skew", "^SKEW")]:
        data[key] = fetch_yf_fast_info(ticker)
        
    # 2. Price History (used for calculating % changes)
    tickers = ["XLE", "SPY", "HYG", "IEF", "BTC-USD", "ETH-USD", "DX-Y.NYB", "GLD", "TLT", "HG=F", "XLU", "XLF", "XLK"]
    for ticker in tickers:
        key = ticker.replace("-", "_").replace(".", "_").replace("=", "_")
        hist = fetch_yf_history(ticker, period="7d", interval="1d")
        data[key] = hist["Close"] if not hist.empty else None

    data["fetched_at"] = datetime.now()
    return data

def pct_change(series) -> float | None:
    if series is None or len(series) < 2: return None
    return (series.iloc[-1] - series.iloc[0]) / series.iloc[0] * 100

def compute_sensors(d: dict, liq_change: float | None) -> dict:
    vix   = d.get("vix")
    t10   = d.get("t10")
    t03   = d.get("t03")
    curve = ((t10 / 10) - (t03 / 10)) if (t10 and t03) else None

    btc_7d  = pct_change(d.get("BTC_USD"))
    eth_7d  = pct_change(d.get("ETH_USD"))
    eth_btc_rel = (eth_7d - btc_7d) if (eth_7d is not None and btc_7d is not None) else None
    dxy_5d  = pct_change(d.get("DX_Y_NYB"))
    xle_5d  = pct_change(d.get("XLE"))
    spy_5d  = pct_change(d.get("SPY"))
    hyg_5d  = pct_change(d.get("HYG"))
    ief_5d  = pct_change(d.get("IEF"))
    gld_5d  = pct_change(d.get("GLD"))
    tlt_5d  = pct_change(d.get("TLT"))
    cop_5d  = pct_change(d.get("HG_F"))
    xlu_5d  = pct_change(d.get("XLU"))
    xlf_5d  = pct_change(d.get("XLF"))
    xlk_5d  = pct_change(d.get("XLK"))
    skew    = d.get("skew")

    sensors = {
        "vix": {
            "value":    vix,
            "warning":  vix is not None and vix > 25,
            "critical": vix is not None and vix > 35,
            "status":   "ELEVATED" if (vix and vix > 20) else "SMOOTH",
            "sub":      f"Fear thermometer. Above 25 = market panic. Now: {vix:.1f}" if vix else "No data",
        },
        "curve": {
            "value":    curve,
            "warning":  curve is not None and curve < 0,
            "critical": curve is not None and curve < -0.5,
            "status":   "INVERTED" if (curve is not None and curve < 0) else "NORMAL",
            "sub":      f"10Y minus 3M. Warns of recession if < 0%. Now: {curve:.2f}%" if curve is not None else "No data",
        },
        "liquidity": {
            "value":    liq_change,
            "warning":  liq_change is not None and liq_change < -2,
            "critical": liq_change is not None and liq_change < -4,
            "status":   "DRAINING" if (liq_change and liq_change < -2) else "STABLE",
            "sub":      f"Fed balance 60d. < -2% = draining liquidity. Now: {liq_change:.1f}%" if liq_change is not None else "Add FRED key",
        },
        "btc": {
            "value":    btc_7d,
            "warning":  btc_7d is not None and btc_7d < -5,
            "critical": btc_7d is not None and btc_7d < -15,
            "status":   "STRESS" if (btc_7d and btc_7d < -5) else "OK",
            "sub":      f"BTC 7d. Big drops = risk pullback. Now: {btc_7d:.1f}%" if btc_7d is not None else "No data",
        },
        "eth_btc": {
            "value":    eth_btc_rel,
            "warning":  eth_btc_rel is not None and eth_btc_rel < -5,
            "critical": eth_btc_rel is not None and eth_btc_rel < -10,
            "status":   "BTC DOMINANCE" if (eth_btc_rel is not None and eth_btc_rel < -5) else (
                        "ETH LEADING"   if (eth_btc_rel is not None and eth_btc_rel > 3)  else "NEUTRAL"),
            "sub":      f"ETH vs BTC 7d relative. ETH lagging BTC = crypto risk-off. Now: {eth_btc_rel:+.1f}%" if eth_btc_rel is not None else "No data",
        },
        "dxy": {
            "value":    dxy_5d,
            "warning":  dxy_5d is not None and dxy_5d > 2,
            "critical": dxy_5d is not None and dxy_5d > 4,
            "status":   "SURGE" if (dxy_5d and dxy_5d > 2) else "STABLE",
            "sub":      f"US Dollar 5-day strength. Squeezes global money. Now: {dxy_5d:.1f}%" if dxy_5d is not None else "No data",
        },
        "credit": {
            "value":    (hyg_5d, ief_5d),
            "warning":  (hyg_5d is not None and ief_5d is not None and hyg_5d < ief_5d),
            "critical": (hyg_5d is not None and ief_5d is not None and (ief_5d - hyg_5d) > 1),
            "status":   "STRESS" if (hyg_5d is not None and ief_5d is not None and hyg_5d < ief_5d) else "OK",
            "sub":      f"HYG vs IEF. Junk falling behind = early warning." if hyg_5d is not None else "No data",
        },
        "xle": {
            "value":    xle_5d,
            "warning":  False,
            "critical": False,
            "status":   "SAFE HARBOR" if (xle_5d and spy_5d and xle_5d > 0 and xle_5d > spy_5d) else "NO FLIGHT",
            "sub":      f"Energy outrunning market indicates defensive rotation." if xle_5d is not None else "No data",
        },
        "gold": {
            "value":    gld_5d,
            "warning":  False,
            "critical": False,
            "status":   "FEAR BUYING" if (gld_5d and gld_5d > 1) else "NEUTRAL",
            "sub":      f"Gold 5-day. Rising fast = safety buying. Now: {gld_5d:.1f}%" if gld_5d is not None else "No data",
        },
        "skew": {
            "value":    skew,
            "warning":  skew is not None and skew > 145,
            "critical": skew is not None and skew > 160,
            "status":   "TAIL RISK" if (skew and skew > 145) else ("ELEVATED" if (skew and skew > 130) else "NORMAL"),
            "sub":      f"CBOE SKEW. Smart money hedging. Now: {skew:.1f}" if skew is not None else "No data",
        },
        "copper": {
            "value":    cop_5d,
            "warning":  cop_5d is not None and cop_5d < -3,
            "critical": cop_5d is not None and cop_5d < -6,
            "status":   "GROWTH WARN" if (cop_5d and cop_5d < -3) else ("SOFT" if (cop_5d and cop_5d < -1) else "OK"),
            "sub":      f"Dr. Copper 5-day. Drops = growth falling. Now: {cop_5d:.1f}%" if cop_5d is not None else "No data",
        },
        "bonds": {
            "value":    tlt_5d,
            "warning":  False,
            "critical": False,
            "status":   "SELLING (yields rising)" if (tlt_5d and tlt_5d < -1) else ("BUYING (flight to safety)" if (tlt_5d and tlt_5d > 1) else "FLAT"),
            "sub":      f"TLT 5-day. Yields rising = stress/inflation. Now: {tlt_5d:.1f}%" if tlt_5d is not None else "No data",
        },
        "rotation": {
            "value":    (xlu_5d, xlf_5d, xlk_5d, xle_5d, spy_5d),
            "warning":  xlu_5d is not None and spy_5d is not None and xlu_5d > 0 and xlu_5d > spy_5d,
            "critical": xlu_5d is not None and spy_5d is not None and xlu_5d > 0 and (xlu_5d - spy_5d) > 2,
            "status":   "DEFENSIVE FLIGHT" if (xlu_5d and spy_5d and xlu_5d > 0 and xlu_5d > spy_5d) else ("RISK-ON" if (xlk_5d and spy_5d and xlk_5d > spy_5d) else "MIXED"),
            "sub":      f"Utilities leading equals fear trade." if xlu_5d is not None else "No data",
        },
    }

    warning_count = sum(1 for s in sensors.values() if s["warning"])
    sensors["warning_count"] = warning_count

    # Weighted risk score
    sensor_weights = {"vix":18, "curve":18, "credit":16, "dxy":14, "btc":12, "eth_btc":6, "liquidity":10, "skew":8, "copper":4, "rotation":0}
    score = sum(sensor_weights[k] for k, s in sensors.items() if k in sensor_weights and s["warning"])
    if gld_5d and gld_5d > 1: score += min(5, int(gld_5d * 1.5))
    sensors["risk_score"] = min(100, max(5, score))  # floor at 5 — there is never zero risk on a trading day

    import knowledge_graph
    domino = knowledge_graph.get_domino_state(sensors)
    sensors["domino_phase"] = domino["phase"]
    sensors["domino_state_str"] = domino["state_str"]
    sensors["domino_desc"] = domino["description"]

    if domino["phase"] == 0:
        sensors["regime"] = f"ALL CLEAR — RISK: {sensors['risk_score']}/100"
        sensors["regime_level"] = "green"
    elif domino["phase"] == 1:
        sensors["regime"] = f"CAUTION — RISK: {sensors['risk_score']}/100 · {warning_count} SENSORS TRIPPED"
        sensors["regime_level"] = "yellow"
    else:
        sensors["regime"] = f"{domino['state_str']} — RISK: {sensors['risk_score']}/100 · P{domino['phase']} TRIGGERED"
        sensors["regime_level"] = "red"

    # Gradient contradiction patterns (below-threshold signals that form footprints)
    sensors["contradictions"] = knowledge_graph.detect_contradictions(sensors)

    return sensors


# ─────────────────────────────────────────────────────────────────
# FED LIQUIDITY (Requires FRED key)
# ─────────────────────────────────────────────────────────────────
@ttl_cache(ttl=3600)
def get_fed_liquidity(api_key: str | None) -> tuple[float | None, float | None]:
    if not api_key: return None, None
    try:
        from fredapi import Fred
        fred  = Fred(api_key=api_key)
        end   = datetime.now()
        start = end - timedelta(days=90)
        
        assets   = fred.get_series("WALCL",    start, end)
        treasury = fred.get_series("WTREGEN",  start, end)
        rrp      = fred.get_series("RRPONTSYD",start, end)

        df = pd.DataFrame({"A": assets, "T": treasury, "R": rrp}).ffill().dropna()
        df["liq"] = (df["A"] / 1000 - df["T"] / 1000 - df["R"]) / 1000
        current = float(df["liq"].iloc[-1])
        change  = (df["liq"].iloc[-1] - df["liq"].iloc[0]) / df["liq"].iloc[0] * 100
        return current, float(change)
    except Exception:
        return None, None

@ttl_cache(ttl=3600)
def get_fred_extras(api_key: str | None) -> dict:
    if not api_key: return {"hy_oas": None, "nfci": None}
    result = {"hy_oas": None, "nfci": None}
    try:
        from fredapi import Fred
        fred  = Fred(api_key=api_key)
        end   = datetime.now()
        start = end - timedelta(days=30)
        
        try:
            hy = fred.get_series("BAMLH0A0HYM2", start, end)
            result["hy_oas"] = float(hy.dropna().iloc[-1]) if not hy.dropna().empty else None
        except Exception: pass

        try:
            nfci = fred.get_series("NFCI", start, end)
            result["nfci"] = float(nfci.dropna().iloc[-1]) if not nfci.dropna().empty else None
        except Exception: pass
    except Exception: pass
    return result

# ─────────────────────────────────────────────────────────────────
# CORRELATION
# ─────────────────────────────────────────────────────────────────
@ttl_cache(ttl=3600)
def get_correlation_matrix() -> pd.DataFrame | None:
    symbols = {"BTC": "BTC-USD", "SPY": "SPY", "DXY": "DX-Y.NYB", "VIX": "^VIX"}
    prices  = {}
    for name, ticker in symbols.items():
        try:
            hist = fetch_yf_history(ticker, period="3mo", interval="1d")
            try: hist.index = hist.index.tz_convert(None)
            except: pass
            prices[name] = hist["Close"]
        except Exception: pass
    df = pd.DataFrame(prices).ffill().dropna()
    return df.corr() if not df.empty else None
