"""
predator_engine.py — The Daily Predator Intelligence Pipeline
=============================================================
Three-stage automated market-intelligence pipeline.

Stage 1 — Intake:   Harvest primary-source data (RSS, SEC EDGAR, DeFiLlama,
                    US Treasury TGA, GitHub commit velocity, Snapshot DAO)
Stage 2 — Bouncer:  Two-tier filter (watchlist relevance + significance gates)
Stage 3 — Engine:   Two-pass AI synthesis → structured JSON briefing

Briefings stored in daily_briefings.jsonl (append-only, one object per day).
Config stored in predator_config.json.
"""

import os
import json
import re
import time
import hashlib
import requests
import feedparser
from datetime import datetime, timedelta, timezone
from typing import Optional

# ─────────────────────────────────────────────────────────────────────────────
# PATHS
# ─────────────────────────────────────────────────────────────────────────────

_DIR           = os.path.dirname(os.path.abspath(__file__))
BRIEFINGS_PATH = os.path.join(_DIR, "daily_briefings.jsonl")
CONFIG_PATH    = os.path.join(_DIR, "predator_config.json")

# ─────────────────────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────────────────────

DEFAULT_CONFIG = {
    "watchlist": ["BTC/USD", "ETH/USD", "SPY"],
    "custom_keywords": [],
    "discovery_sensitivity": 3,
    "schedule_time": "08:00",
    "enabled_sources": ["rss", "sec_8k", "sec_form4", "defillama",
                        "treasury_tga", "github_commits", "snapshot_dao"],
    "significance_thresholds": {
        "treasury_drain_pct": 2.0,
        "token_unlock_supply_pct": 10.0,
        "insider_buy_usd": 500000,
        "github_velocity_pct": 50.0,   # flag if commit count swings ±50% week-over-week
    },
}


def load_predator_config() -> dict:
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            merged = {**DEFAULT_CONFIG, **cfg}
            merged["significance_thresholds"] = {
                **DEFAULT_CONFIG["significance_thresholds"],
                **cfg.get("significance_thresholds", {}),
            }
            return merged
        except Exception:
            pass
    return dict(DEFAULT_CONFIG)


def save_predator_config(cfg: dict):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)


# ─────────────────────────────────────────────────────────────────────────────
# SYMBOL → KEYWORD MAPPING (Tier 1 Bouncer)
# ─────────────────────────────────────────────────────────────────────────────

SYMBOL_KEYWORDS: dict[str, list[str]] = {
    "BTC/USD":   ["bitcoin", "btc", "crypto", "coinbase", "microstrategy", "mstr", "cryptocurrency", "halving"],
    "ETH/USD":   ["ethereum", "eth", "ether", "defi", "vitalik",
                  "uniswap", "aave", "compound", "makerdao", "arbitrum",
                  "optimism", "base chain", "zksync", "layer 2", "l2"],
    "SUI/USD":   ["sui", "mysten", "sui network"],
    "SOL/USD":   ["solana", "sol"],
    "XRP/USD":   ["ripple", "xrp"],
    "SPY":       ["s&p 500", "s&p500", "spy", "equity market", "stock market", "dow jones", "s&p"],
    "QQQ":       ["nasdaq", "qqq", "tech stocks"],
    "NVDA":      ["nvidia", "nvda", "gpu", "semiconductor", "ai chip", "jensen huang"],
    "AAPL":      ["apple", "aapl", "iphone", "tim cook", "apple inc"],
    "TSLA":      ["tesla", "tsla", "elon musk", "electric vehicle"],
    "MSFT":      ["microsoft", "msft", "azure", "satya nadella"],
    "META":      ["meta", "facebook", "instagram", "mark zuckerberg"],
    "AMZN":      ["amazon", "amzn", "aws", "jeff bezos"],
    "GLD":       ["gold", "gld", "precious metals", "xau"],
    "TLT":       ["treasury", "bonds", "tlt", "t-bond", "10-year yield"],
    "DX-Y.NYB":  ["dollar index", "dxy", "usd index"],
    "HYG":       ["high yield", "junk bonds", "credit spread"],
    "OIL":       ["crude oil", "wti", "brent", "opec"],
}


def symbols_to_keywords(symbols: list[str]) -> list[str]:
    """Derive a flat keyword list from a list of ticker symbols."""
    keywords = []
    for sym in symbols:
        sym_upper = sym.upper().replace("-USD", "/USD").replace("-USDT", "/USD")
        mapped = SYMBOL_KEYWORDS.get(sym_upper)
        if mapped:
            keywords.extend(mapped)
        else:
            base = re.sub(r'[/-](USD|USDT|EUR)$', '', sym_upper, flags=re.IGNORECASE)
            keywords.append(base.lower())
    return list(set(keywords))


# ─────────────────────────────────────────────────────────────────────────────
# STAGE 1 — INTAKE
# ─────────────────────────────────────────────────────────────────────────────

RSS_SOURCES = [
    ("FED",         "https://www.federalreserve.gov/feeds/press_all.xml"),
    ("BLS",         "https://www.bls.gov/feed/bls_latest.rss"),
    ("TREASURY",    "https://home.treasury.gov/news/press-releases/rss.xml"),
    ("MARKETWATCH", "https://feeds.marketwatch.com/marketwatch/topstories/"),
    ("CNBC",        "https://www.cnbc.com/id/100003114/device/rss/rss.html"),
    ("YAHOO_FIN",   "https://finance.yahoo.com/rss/topfinstories"),
    ("COINDESK",    "https://www.coindesk.com/arc/outboundfeeds/rss/"),
    ("ZEROHEDGE",   "https://feeds.feedburner.com/zerohedge/feed"),
    ("CRYPTOPANIC", "https://cryptopanic.com/news/rss/"),
]

EVENT_TRIGGERS = {
    "CPI", "PPI", "FOMC", "NFP", "INFLATION", "RATE", "RECESSION",
    "TARIFF", "JOBS", "GDP", "UNEMPLOYMENT", "POWELL", "FED",
    "YIELD", "TREASURY", "DEBT", "LIQUIDITY", "RATE CUT", "RATE HIKE",
    "BAILOUT", "DEFAULT", "SANCTIONS", "WAR", "BANKRUPTCY",
}


def _parse_date(entry) -> datetime:
    """Parse any date from a feedparser entry. Returns UTC datetime."""
    t = getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None)
    if t:
        try:
            return datetime.fromtimestamp(time.mktime(t), tz=timezone.utc)
        except Exception:
            pass
    raw = getattr(entry, "published", None) or getattr(entry, "updated", None)
    if raw:
        try:
            from dateutil import parser as date_parser
            dt = date_parser.parse(raw)
            return dt.astimezone(timezone.utc) if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except Exception:
            pass
    return datetime.now(tz=timezone.utc)


def _fetch_rss(enabled: bool = True) -> list[dict]:
    if not enabled:
        return []
    now = datetime.now(tz=timezone.utc)
    events = []
    for label, url in RSS_SOURCES:
        try:
            feed = feedparser.parse(url)
        except Exception:
            continue
        for entry in feed.entries[:8]:
            title = entry.get("title", "").strip()
            if not title:
                continue
            raw_sum = entry.get("summary", "") or entry.get("description", "")
            summary = re.sub(r"<[^>]+>", "", raw_sum).strip()[:300]
            link = entry.get("link", "")
            pub_dt = _parse_date(entry)
            age_h = (now - pub_dt).total_seconds() / 3600

            text_upper = (title + " " + summary).upper()
            triggers = [t for t in EVENT_TRIGGERS if t in text_upper]

            events.append({
                "source":             label,
                "source_type":        "rss",
                "title":              title,
                "summary":            summary,
                "url":                link,
                "age_hours":          round(age_h, 1),
                "published":          pub_dt.isoformat(),
                "event_id":           hashlib.md5(f"{label}:{title}".encode()).hexdigest()[:12],
                "triggers":           triggers,
                "significance_flags": ["EVENT_TRIGGER"] if triggers else [],
            })
    return events


_SEC_HEADERS = {
    "User-Agent": "BansheePro research@banshee.local",
    "Accept": "application/json",
}

# EDGAR REST API — full-text search (no auth required, no browse-UI needed)
_EDGAR_SEARCH_URL = "https://efts.sec.gov/LATEST/search-index"


def _fetch_edgar_rest(form_type: str, days_back: int = 2, count: int = 30) -> list[dict]:
    """
    Fetch recent SEC filings from EDGAR REST full-text search API.
    Returns list of raw hit dicts.
    """
    today = datetime.now(tz=timezone.utc)
    start = (today - timedelta(days=days_back)).strftime("%Y-%m-%d")
    end   = today.strftime("%Y-%m-%d")
    params = {
        "q":          '""',
        "forms":      form_type,
        "dateRange":  "custom",
        "startdt":    start,
        "enddt":      end,
    }
    try:
        r = requests.get(_EDGAR_SEARCH_URL, headers=_SEC_HEADERS, params=params, timeout=12)
        if r.status_code != 200:
            return []
        data = r.json()
        return data.get("hits", {}).get("hits", [])[:count]
    except Exception:
        return []


def _fetch_sec_8k(enabled: bool = True) -> list[dict]:
    """Fetch recent SEC 8-K filings via EDGAR REST search API."""
    if not enabled:
        return []
    events = []
    now = datetime.now(tz=timezone.utc)
    hits = _fetch_edgar_rest("8-K", days_back=2, count=30)
    for hit in hits:
        src = hit.get("_source", {})
        names = src.get("display_names", ["Unknown"])
        company = names[0].split("(")[0].strip() if names else "Unknown"
        period  = src.get("period_ending", "")
        form_id = src.get("file_num", [""])[0]
        cik     = (src.get("ciks") or [""])[0].lstrip("0")
        title   = f"{company} — 8-K filing"
        url     = f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik}&type=8-K&dateb=&owner=include&count=5"
        raw_items = src.get("items") or []
        # Normalize to a flat list of strings
        if isinstance(raw_items, str):
            raw_items = [x.strip() for x in raw_items.split(",") if x.strip()]
        items = raw_items  # list[str]
        items_str = ", ".join(items) if items else ""

        sig_flags = []
        if "5.02" in items:
            sig_flags.append("EXEC_DEPARTURE_502")
        if "1.01" in items:
            sig_flags.append("MATERIAL_AGREEMENT_101")
        if "2.02" in items:
            sig_flags.append("EARNINGS_RESULTS_202")

        # Try to parse filing date for age
        filed = src.get("file_date") or period
        age_h = 24.0
        if filed:
            try:
                from dateutil import parser as dp
                filed_dt = dp.parse(filed).replace(tzinfo=timezone.utc)
                age_h = (now - filed_dt).total_seconds() / 3600
            except Exception:
                pass

        events.append({
            "source":             "SEC_8K",
            "source_type":        "sec_8k",
            "title":              title + (f" (items: {items_str})" if items_str else ""),
            "company":            company,
            "summary":            f"{company} filed an 8-K. Items: {items_str or 'see filing'}. Period: {period}.",
            "url":                url,
            "age_hours":          round(age_h, 1),
            "published":          (now.isoformat()),
            "event_id":           hashlib.md5(f"8K:{company}:{period}".encode()).hexdigest()[:12],
            "triggers":           [],
            "significance_flags": sig_flags,
        })
    return events


def _fetch_sec_form4(enabled: bool = True) -> list[dict]:
    """Fetch recent SEC Form 4 insider filings via EDGAR REST search API."""
    if not enabled:
        return []
    events = []
    now = datetime.now(tz=timezone.utc)
    hits = _fetch_edgar_rest("4", days_back=2, count=30)
    for hit in hits:
        src     = hit.get("_source", {})
        names   = src.get("display_names", ["Unknown"])
        company = names[0].split("(")[0].strip() if names else "Unknown"
        period  = src.get("period_ending", "")
        cik     = (src.get("ciks") or [""])[0].lstrip("0")
        title   = f"{company} — Form 4 insider transaction"
        url     = f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik}&type=4&dateb=&owner=include&count=5"

        filed = src.get("file_date") or period
        age_h = 24.0
        if filed:
            try:
                from dateutil import parser as dp
                filed_dt = dp.parse(filed).replace(tzinfo=timezone.utc)
                age_h = (now - filed_dt).total_seconds() / 3600
            except Exception:
                pass

        events.append({
            "source":             "SEC_FORM4",
            "source_type":        "sec_form4",
            "title":              title,
            "company":            company,
            "summary":            f"Insider transaction (Form 4) filed for {company}. Period: {period}.",
            "url":                url,
            "age_hours":          round(age_h, 1),
            "published":          now.isoformat(),
            "event_id":           hashlib.md5(f"F4:{company}:{period}".encode()).hexdigest()[:12],
            "triggers":           [],
            "significance_flags": [],
        })
    return events


def _fetch_defillama(enabled: bool = True, unlock_threshold_pct: float = 10.0) -> list[dict]:
    """Fetch upcoming token unlock events from DeFiLlama."""
    if not enabled:
        return []
    events = []
    try:
        r = requests.get("https://api.llama.fi/emission", timeout=12)
        if r.status_code != 200:
            return []
        data = r.json()
        if not isinstance(data, list):
            return []
        now = datetime.now(tz=timezone.utc)
        for protocol in data[:60]:
            name = protocol.get("name", "Unknown")
            upcoming = protocol.get("upcomingEvent", [])
            if not upcoming:
                continue
            for event in upcoming[:2]:
                ts = event.get("timestamp") or event.get("date")
                if not ts:
                    continue
                try:
                    event_dt = datetime.fromtimestamp(float(ts), tz=timezone.utc)
                except Exception:
                    continue
                days_away = (event_dt - now).total_seconds() / 86400
                if days_away < 0 or days_away > 7:
                    continue

                tokens = event.get("noOfTokens") or event.get("amount") or 0
                circ = (
                    (protocol.get("token") or {}).get("circSupply")
                    or protocol.get("circSupply")
                    or 0
                )
                pct = (float(tokens) / float(circ) * 100) if circ else 0.0

                sig_flags = []
                if pct >= unlock_threshold_pct:
                    sig_flags.append(f"TOKEN_UNLOCK_{pct:.0f}PCT")

                events.append({
                    "source":             "DEFILLAMA",
                    "source_type":        "defillama",
                    "title":              (
                        f"{name}: {tokens:,.0f} tokens unlock "
                        f"in {days_away:.0f}d ({pct:.1f}% supply)"
                    ),
                    "company":            name,
                    "summary":            (
                        f"Token unlock event for {name}: {tokens:,.0f} tokens "
                        f"in {days_away:.0f} days (~{pct:.1f}% of circulating supply)."
                    ),
                    "url":                f"https://defillama.com/unlocks",
                    "age_hours":          0.0,
                    "days_away":          round(days_away, 1),
                    "unlock_pct":         round(pct, 2),
                    "published":          now.isoformat(),
                    "event_id":           hashlib.md5(f"DFL:{name}:{ts}".encode()).hexdigest()[:12],
                    "triggers":           [],
                    "significance_flags": sig_flags,
                })
    except Exception:
        pass
    return events


def _fetch_treasury_tga(enabled: bool = True, drain_threshold_pct: float = 2.0) -> list[dict]:
    """
    Fetch US Treasury General Account (TGA) balance from fiscaldata.treasury.gov.
    Free, no auth required. Values reported in millions of USD.

    A significant TGA drain (Treasury spending down reserves) is a liquidity
    injection into the banking system — historically bullish for risk assets.
    A refill (Treasury rebuilding reserves) is a liquidity drain — bearish.
    """
    if not enabled:
        return []
    try:
        url = "https://api.fiscaldata.treasury.gov/services/api/v1/accounting/dts/dts_table_1"
        params = {
            "fields":     "record_date,account_name,open_today_bal",
            "filter":     "account_name:in:(Federal Reserve Account)",
            "sort":       "-record_date",
            "limit":      "5",
        }
        r = requests.get(url, params=params, timeout=12)
        if r.status_code != 200:
            return []
        data = r.json().get("data", [])
        if len(data) < 2:
            return []

        # Balances are in millions — convert to billions for readability
        latest_m = float(str(data[0]["open_today_bal"]).replace(",", ""))
        prev_m   = float(str(data[1]["open_today_bal"]).replace(",", ""))
        change_m = latest_m - prev_m
        change_bn = change_m / 1_000
        latest_bn = latest_m / 1_000
        change_pct = (change_m / prev_m * 100) if prev_m else 0.0

        sig_flags = []
        if change_pct < -drain_threshold_pct:
            sig_flags.append(f"TGA_DRAIN_{abs(change_pct):.1f}PCT")
        elif change_pct > drain_threshold_pct:
            sig_flags.append(f"TGA_REFILL_{change_pct:.1f}PCT")

        direction = "drained" if change_bn < 0 else "refilled"
        record_date = data[0].get("record_date", "unknown date")

        return [{
            "source":             "TREASURY_TGA",
            "source_type":        "treasury_tga",
            "title":              (
                f"US Treasury TGA {direction} ${abs(change_bn):.1f}B "
                f"({change_pct:+.1f}%) — balance now ${latest_bn:.1f}B"
            ),
            "summary":            (
                f"Treasury General Account ({record_date}): "
                f"${latest_bn:.1f}B balance, changed {change_pct:+.1f}% "
                f"(${change_bn:+.1f}B). "
                + ("Drain = liquidity injection into banking system (risk-on)."
                   if change_bn < 0
                   else "Refill = liquidity drain from banking system (risk-off).")
            ),
            "url":                "https://fiscaldata.treasury.gov/datasets/daily-treasury-statement/",
            "age_hours":          24.0,
            "published":          datetime.now(tz=timezone.utc).isoformat(),
            "event_id":           hashlib.md5(f"TGA:{record_date}".encode()).hexdigest()[:12],
            "triggers":           ["TREASURY", "LIQUIDITY"],
            "significance_flags": sig_flags,
            "tga_balance_bn":     round(latest_bn, 1),
            "tga_change_pct":     round(change_pct, 2),
            "tga_change_bn":      round(change_bn, 1),
        }]
    except Exception:
        return []


# Crypto repos to track for commit velocity
_GITHUB_REPOS: dict[str, str] = {
    "BTC": "bitcoin/bitcoin",
    "ETH": "ethereum/go-ethereum",
    "SUI": "MystenLabs/sui",
}

_GITHUB_HEADERS = {
    "User-Agent": "BansheePro research@banshee.local",
    "Accept":     "application/vnd.github.v3+json",
}


def _fetch_github_commits(
    enabled: bool = True,
    velocity_threshold_pct: float = 50.0,
) -> list[dict]:
    """
    Fetch weekly commit velocity for key crypto repos from the GitHub REST API.
    Free, no auth (60 req/hr unauthenticated — we use 6 calls/day total).

    A sudden spike in commits often precedes a major protocol upgrade or fix.
    A steep drop can signal developer exodus — a fundamental bearish signal.
    """
    if not enabled:
        return []

    now     = datetime.now(tz=timezone.utc)
    since_7  = (now - timedelta(days=7)).isoformat()
    since_14 = (now - timedelta(days=14)).isoformat()
    until_7  = (now - timedelta(days=7)).isoformat()

    events = []
    for symbol, repo in _GITHUB_REPOS.items():
        try:
            # Last 7 days
            r1 = requests.get(
                f"https://api.github.com/repos/{repo}/commits",
                params={"since": since_7, "per_page": 100},
                headers=_GITHUB_HEADERS, timeout=10,
            )
            if r1.status_code != 200:
                continue
            recent = len(r1.json())

            # Prior 7 days (7–14 days ago)
            r2 = requests.get(
                f"https://api.github.com/repos/{repo}/commits",
                params={"since": since_14, "until": until_7, "per_page": 100},
                headers=_GITHUB_HEADERS, timeout=10,
            )
            prior = len(r2.json()) if r2.status_code == 200 else 0

            pct_change = ((recent - prior) / prior * 100) if prior > 0 else 0.0

            sig_flags = []
            if pct_change > velocity_threshold_pct:
                sig_flags.append(f"DEV_SPIKE_{symbol}")
            elif pct_change < -velocity_threshold_pct:
                sig_flags.append(f"DEV_SLOWDOWN_{symbol}")

            direction = f"{pct_change:+.0f}%" if prior > 0 else "baseline"
            events.append({
                "source":             "GITHUB",
                "source_type":        "github_commits",
                "title":              (
                    f"{symbol} dev activity: {recent} commits/7d "
                    f"({direction} vs prior week)"
                ),
                "summary":            (
                    f"{symbol} ({repo}): {recent} commits last 7 days "
                    f"vs {prior} prior week ({direction}). "
                    + (f"Unusual spike — possible major protocol work."
                       if pct_change > velocity_threshold_pct
                       else f"Unusual slowdown — developer disengagement signal."
                       if pct_change < -velocity_threshold_pct
                       else "Commit velocity within normal range.")
                ),
                "url":                f"https://github.com/{repo}/commits",
                "age_hours":          0.0,
                "published":          now.isoformat(),
                "event_id":           hashlib.md5(
                    f"GH:{repo}:{now.strftime('%Y-%W')}".encode()
                ).hexdigest()[:12],
                "triggers":           [],
                "significance_flags": sig_flags,
                "commit_count_7d":    recent,
                "commit_count_prior": prior,
                "commit_pct_change":  round(pct_change, 1),
            })
        except Exception:
            continue

    return events


# Major DeFi / DAO spaces to monitor on Snapshot
_SNAPSHOT_SPACES = [
    "uniswap", "aave.eth", "compound-governance.eth", "makerdao.eth",
    "arbitrumfoundation.eth", "optimismfoundation.eth", "ens.eth",
    "gitcoin.eth", "lido-snapshot.eth",
]

# Keywords that indicate treasury-risk proposals worth flagging
_DAO_TREASURY_KEYWORDS = [
    "treasury", "liquidat", "sell", "transfer funds", "grant",
    "budget", "protocol revenue", "diversif", "buyback",
]


def _fetch_snapshot_dao(enabled: bool = True) -> list[dict]:
    """
    Fetch recent DAO governance proposals from Snapshot.org.
    Free GraphQL API, no auth required.

    Treasury-related proposals (liquidations, fund transfers, grants)
    can move large sums of ETH/stablecoins into or out of circulation —
    a direct structural supply/demand event.
    """
    if not enabled:
        return []

    now      = datetime.now(tz=timezone.utc)
    since_ts = int((now - timedelta(days=3)).timestamp())

    query = """
    {
      proposals(
        first: 20,
        where: { space_in: %s, created_gte: %d },
        orderBy: "created",
        orderDirection: desc
      ) {
        id
        title
        body
        start
        end
        state
        space { id name }
      }
    }
    """ % (json.dumps(_SNAPSHOT_SPACES), since_ts)

    try:
        r = requests.post(
            "https://hub.snapshot.org/graphql",
            json={"query": query},
            headers={"Content-Type": "application/json"},
            timeout=12,
        )
        if r.status_code != 200:
            return []
        proposals = r.json().get("data", {}).get("proposals", [])
        if not proposals:
            return []

        events = []
        for prop in proposals:
            title      = (prop.get("title") or "").strip()
            body       = (prop.get("body") or "")[:300]
            space      = prop.get("space") or {}
            space_name = space.get("name", "Unknown DAO")
            space_id   = space.get("id", "")
            state      = prop.get("state", "unknown")
            end_ts     = prop.get("end") or 0
            start_ts   = prop.get("start") or int(now.timestamp())
            prop_id    = prop.get("id", "")

            text           = (title + " " + body).lower()
            treasury_flagged = any(kw in text for kw in _DAO_TREASURY_KEYWORDS)

            sig_flags = ["DAO_TREASURY_VOTE"] if treasury_flagged else []

            days_left = (end_ts - int(now.timestamp())) / 86400
            age_h     = (int(now.timestamp()) - start_ts) / 3600

            events.append({
                "source":             f"SNAPSHOT/{space_name}",
                "source_type":        "snapshot_dao",
                "title":              f"[{space_name}] {title}",
                "company":            space_name,
                "summary":            (
                    f"{space_name} proposal ({state}): {title}. "
                    + (f"Ends in {days_left:.0f}d." if days_left > 0 else "Voting closed.")
                    + (" — TREASURY ACTION FLAGGED." if treasury_flagged else "")
                ),
                "url":                f"https://snapshot.org/#/{space_id}/proposal/{prop_id}",
                "age_hours":          round(age_h, 1),
                "published":          datetime.fromtimestamp(
                    start_ts, tz=timezone.utc
                ).isoformat(),
                "event_id":           hashlib.md5(f"SNAP:{prop_id}".encode()).hexdigest()[:12],
                "triggers":           [],
                "significance_flags": sig_flags,
                "dao_space":          space_name,
                "proposal_state":     state,
                "days_left":          round(days_left, 1),
            })

        return events
    except Exception:
        return []


def run_intake(config: dict) -> list[dict]:
    """Stage 1: Collect all events from enabled sources."""
    enabled = set(config.get("enabled_sources", DEFAULT_CONFIG["enabled_sources"]))
    thresholds = config.get("significance_thresholds", DEFAULT_CONFIG["significance_thresholds"])

    all_events = []
    all_events.extend(_fetch_rss("rss" in enabled))
    all_events.extend(_fetch_sec_8k("sec_8k" in enabled))
    all_events.extend(_fetch_sec_form4("sec_form4" in enabled))
    all_events.extend(_fetch_defillama(
        "defillama" in enabled,
        unlock_threshold_pct=thresholds.get("token_unlock_supply_pct", 10.0),
    ))
    all_events.extend(_fetch_treasury_tga(
        "treasury_tga" in enabled,
        drain_threshold_pct=thresholds.get("treasury_drain_pct", 2.0),
    ))
    all_events.extend(_fetch_github_commits(
        "github_commits" in enabled,
        velocity_threshold_pct=thresholds.get("github_velocity_pct", 50.0),
    ))
    all_events.extend(_fetch_snapshot_dao("snapshot_dao" in enabled))
    return all_events


# ─────────────────────────────────────────────────────────────────────────────
# STAGE 2 — THE BOUNCER
# ─────────────────────────────────────────────────────────────────────────────

def run_bouncer(
    events: list[dict],
    config: dict,
    watchlist_symbols: Optional[list[str]] = None,
) -> dict:
    """
    Stage 2: Two-tier filter.

    Tier 1 — Watchlist Signal (precision): relevance to symbols user is watching.
    Tier 2 — Significance Threshold (discovery): important regardless of watchlist.

    Returns: {"watchlist": [...], "discovered": [...], "rejected_count": int}
    """
    watchlist  = watchlist_symbols or config.get("watchlist", [])
    custom_kw  = [k.lower() for k in config.get("custom_keywords", [])]
    sensitivity = config.get("discovery_sensitivity", 3)

    watchlist_kw = set(symbols_to_keywords(watchlist) + custom_kw)

    watchlist_events  = []
    discovered_events = []
    rejected = 0
    seen_ids = set()

    for event in events:
        eid = event.get("event_id", "")
        if eid in seen_ids:
            continue
        seen_ids.add(eid)

        text = (event["title"] + " " + event.get("summary", "") + " " +
                event.get("company", "")).lower()

        # ── Tier 1: watchlist keyword match ──────────────────────────────────
        tier1_match = any(kw in text for kw in watchlist_kw)

        # ── Tier 2: significance gate ─────────────────────────────────────────
        sig_flags  = event.get("significance_flags", [])
        triggers   = event.get("triggers", [])
        src_type   = event.get("source_type", "")

        # Always-significant regardless of sensitivity
        always_sig = any(
            f in sig_flags for f in [
                "EXEC_DEPARTURE_502", "MATERIAL_AGREEMENT_101",
                "EARNINGS_RESULTS_202",
            ]
        ) or any(f.startswith("TOKEN_UNLOCK_") for f in sig_flags)

        tier2_match = False
        if sensitivity >= 1:
            tier2_match = always_sig
        if sensitivity >= 2:
            tier2_match = tier2_match or bool(sig_flags)
        if sensitivity >= 3:
            tier2_match = tier2_match or bool(triggers)
        if sensitivity >= 4:
            tier2_match = tier2_match or src_type in ("sec_8k", "sec_form4")
        if sensitivity >= 5:
            tier2_match = True

        if tier1_match:
            event["_tier"] = "watchlist"
            watchlist_events.append(event)
        elif tier2_match:
            event["_tier"] = "discovered"
            discovered_events.append(event)
        else:
            rejected += 1

    return {
        "watchlist":      watchlist_events[:20],
        "discovered":     discovered_events[:15],
        "rejected_count": rejected,
    }


# ─────────────────────────────────────────────────────────────────────────────
# STAGE 3 — THE ENGINE (Two-pass AI)
# ─────────────────────────────────────────────────────────────────────────────

_PASS1_SYSTEM = (
    "You are The Daily Predator — Banshee Pro's market intelligence analyst. "
    "Your job is to reason through today's filtered market events and identify "
    "intersections, second-order effects, and non-obvious implications. "
    "Think like a senior macro trader who reads between the lines. "
    "Be direct, specific, and concise. Reference actual company names and event types. "
    "No hedging. Every sentence should carry information a trader can act on."
)

_PASS2_SYSTEM = (
    "You are a JSON extraction engine. "
    "Extract the analysis from the provided text into the exact JSON schema given. "
    "Output ONLY valid JSON — no markdown, no explanation, no code fences. "
    "All string values must be properly escaped. Arrays may be empty but must exist."
)


def _strip_json_fences(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"\s*```$", "", text, flags=re.MULTILINE)
    return text.strip()


def _format_events_for_prompt(events: list[dict], label: str, cap: int = 12) -> str:
    if not events:
        return f"--- {label} ---\nNone.\n"
    lines = [f"--- {label} ({len(events)} events) ---"]
    for ev in events[:cap]:
        age_str = (
            f"in {ev.get('days_away', '?')}d"
            if ev.get("source_type") == "defillama"
            else f"{ev['age_hours']:.0f}h ago"
        )
        sig_tag = (
            f" [FLAGS: {', '.join(ev['significance_flags'])}]"
            if ev.get("significance_flags")
            else ""
        )
        lines.append(f"[{ev['source']}]{sig_tag} ({age_str}) {ev['title']}")
        if ev.get("summary"):
            lines.append(f"  → {ev['summary'][:150]}")
    return "\n".join(lines)


def _attach_urls(items: list[dict], raw_events: list[dict]) -> None:
    """Attach source-matched URLs from raw intake events to briefing items in-place."""
    source_urls: dict[str, list[str]] = {}
    for ev in raw_events:
        key = (ev.get("source") or "").lower().strip()
        url = (ev.get("url") or "").strip()
        if key and url:
            source_urls.setdefault(key, [])
            if url not in source_urls[key]:
                source_urls[key].append(url)
    for item in items:
        key = (item.get("source") or "").lower().strip()
        urls = source_urls.get(key, [])
        item["url"] = urls[0] if urls else None


def run_engine(
    bounced: dict,
    config: dict,
    ai_cfg: dict,
    yesterday_briefing: Optional[dict] = None,
) -> dict:
    """
    Stage 3: Two-pass AI synthesis.

    Pass 1: Chain-of-thought reasoning about events and intersections.
    Pass 2: Extract structured JSON with impact scores.
    """
    import banshee_ai

    watchlist_events  = bounced.get("watchlist", [])
    discovered_events = bounced.get("discovered", [])
    date_str = datetime.now(tz=timezone.utc).strftime("%A, %B %d, %Y")

    # ── Pass 1: Reason ────────────────────────────────────────────────────────
    watchlist_block  = _format_events_for_prompt(watchlist_events, "WATCHLIST EVENTS")
    discovered_block = _format_events_for_prompt(discovered_events, "DISCOVERED SIGNALS")

    yesterday_block = ""
    if yesterday_briefing:
        prev_items = (
            yesterday_briefing.get("watchlist_events", [])[:3]
            + yesterday_briefing.get("discovered_signals", [])[:2]
        )
        if prev_items:
            yesterday_block = "--- YESTERDAY'S FLAGGED ITEMS (check if resolved/escalated) ---\n"
            for item in prev_items:
                hl = item.get("headline") or item.get("title", "")
                yesterday_block += f"- {hl}\n"

    pass1_prompt = f"""THE DAILY PREDATOR — Market Intelligence Brief
DATE: {date_str}

{watchlist_block}

{discovered_block}

{yesterday_block}
TASK: Reason about the above events in three passes:
1. WATCHLIST: What events directly affect the user's tracked assets? Rate their significance 1-10.
2. DISCOVERY: What should the user be watching that they aren't? Why is each significant?
3. FOLLOWUPS: For yesterday's items — developed, resolved, or escalated?
4. SYNTHESIS: One sentence — the single most important thing a trader needs to know today.

Be specific. Name companies and effects directly. Total response under 450 words."""

    pass1_reasoning = banshee_ai.call_ai(
        ai_cfg, pass1_prompt, system_prompt_override=_PASS1_SYSTEM
    )

    # ── Pass 2: Extract structured JSON ──────────────────────────────────────
    schema = """{
  "watchlist_events": [
    {"headline": "string", "source": "string", "impact_score": 7, "symbols": ["BTC"], "lede": "string (1 sentence)"}
  ],
  "discovered_signals": [
    {"headline": "string", "source": "string", "impact_score": 8, "reason_flagged": "string", "lede": "string (1 sentence)"}
  ],
  "yesterday_followups": [
    {"original": "string", "status": "escalated|resolved|developing|new", "update": "string"}
  ],
  "top_story": "string (1 sentence — most important thing for a trader today)",
  "macro_tone": "BULLISH|BEARISH|NEUTRAL|MIXED",
  "risk_level": 3
}"""

    pass2_prompt = f"""ANALYSIS TO EXTRACT:
{pass1_reasoning}

RAW EVENT COUNTS: watchlist={len(watchlist_events)}, discovered={len(discovered_events)}

Extract into this JSON schema. impact_score is 1–10. risk_level is 1–5 (1=quiet day, 5=high alert).
OUTPUT ONLY THE JSON OBJECT — no markdown, no explanation:
{schema}"""

    pass2_raw = banshee_ai.call_ai(
        ai_cfg, pass2_prompt, system_prompt_override=_PASS2_SYSTEM
    )

    # Parse JSON
    structured: dict = {}
    try:
        clean = _strip_json_fences(pass2_raw)
        structured = json.loads(clean)
    except Exception:
        structured = {
            "watchlist_events":   [],
            "discovered_signals": [],
            "yesterday_followups": [],
            "top_story":   "JSON parse error — see ai_narrative for full analysis.",
            "macro_tone":  "NEUTRAL",
            "risk_level":  3,
        }

    _attach_urls(structured.get("watchlist_events", []), watchlist_events)
    _attach_urls(structured.get("discovered_signals", []), discovered_events)

    briefing = {
        "date":               datetime.now(tz=timezone.utc).strftime("%Y-%m-%d"),
        "generated_at":       datetime.now(tz=timezone.utc).isoformat(),
        "ai_narrative":       pass1_reasoning,
        "watchlist_events":   structured.get("watchlist_events", []),
        "discovered_signals": structured.get("discovered_signals", []),
        "yesterday_followups":structured.get("yesterday_followups", []),
        "top_story":          structured.get("top_story", ""),
        "macro_tone":         structured.get("macro_tone", "NEUTRAL"),
        "risk_level":         int(structured.get("risk_level", 3)),
        "event_counts": {
            "watchlist_intake":  len(watchlist_events),
            "discovered_intake": len(discovered_events),
            "rejected":          bounced.get("rejected_count", 0),
        },
    }
    return briefing


# ─────────────────────────────────────────────────────────────────────────────
# STORAGE
# ─────────────────────────────────────────────────────────────────────────────

def save_briefing(briefing: dict):
    """Append briefing to daily_briefings.jsonl (one JSON object per line)."""
    with open(BRIEFINGS_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(briefing) + "\n")


def load_latest_briefing() -> Optional[dict]:
    """Load the most recent briefing from daily_briefings.jsonl."""
    if not os.path.exists(BRIEFINGS_PATH):
        return None
    last = None
    with open(BRIEFINGS_PATH, "r", encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()
            if stripped:
                try:
                    last = json.loads(stripped)
                except Exception:
                    pass
    return last


def load_briefing_by_date(date_str: str) -> Optional[dict]:
    """Load briefing for a specific date (YYYY-MM-DD)."""
    if not os.path.exists(BRIEFINGS_PATH):
        return None
    with open(BRIEFINGS_PATH, "r", encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()
            if stripped:
                try:
                    b = json.loads(stripped)
                    if b.get("date") == date_str:
                        return b
                except Exception:
                    pass
    return None


def today_briefing_exists() -> bool:
    """Check if today's briefing already exists."""
    today = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
    return load_briefing_by_date(today) is not None


# ─────────────────────────────────────────────────────────────────────────────
# FULL PIPELINE
# ─────────────────────────────────────────────────────────────────────────────

def run_daily_cycle(
    ai_cfg: dict,
    watchlist_symbols: Optional[list[str]] = None,
    force: bool = False,
) -> dict:
    """
    Run the complete 3-stage pipeline.

    If today's briefing already exists and force=False, returns the cached one.
    Merges watchlist_symbols with config watchlist before running.
    """
    if not force and today_briefing_exists():
        return load_latest_briefing()

    config = load_predator_config()
    if watchlist_symbols:
        merged = list(set(config.get("watchlist", []) + watchlist_symbols))
        config["watchlist"] = merged

    # Stage 1
    all_events = run_intake(config)

    # Stage 2
    bounced = run_bouncer(all_events, config, config.get("watchlist", []))

    # Stage 3 — inject yesterday's briefing for followup memory
    yesterday = load_latest_briefing()
    if yesterday and yesterday.get("date") == datetime.now(tz=timezone.utc).strftime("%Y-%m-%d"):
        yesterday = None  # Today's own briefing is not "yesterday"

    briefing = run_engine(bounced, config, ai_cfg, yesterday_briefing=yesterday)
    save_briefing(briefing)
    return briefing


# ─────────────────────────────────────────────────────────────────────────────
# NEXUS INTEGRATION HELPER
# ─────────────────────────────────────────────────────────────────────────────

def get_briefing_for_nexus(briefing: Optional[dict]) -> str:
    """
    Format a briefing as catalyst context for injection into Nexus synthesis prompt.

    IMPORTANT: Does NOT include macro tone or risk level — those are news-derived
    heuristics that must NOT override the quantitative macro sensor data already
    present in the Nexus prompt. Only event headlines and ledes are included.
    """
    if not briefing:
        return ""

    date = briefing.get("date", "unknown date")
    top  = briefing.get("top_story", "")

    lines = [
        f"--- DAILY PREDATOR NEWS CATALYSTS ({date}) ---",
        f"CONTEXT NOTE: The items below are news events and catalysts. "
        f"They are NOT a macro risk assessment. The quantitative macro regime "
        f"(sensor data above) is the authoritative risk signal — use that, not these headlines, "
        f"to judge the macro environment.",
        f"TOP CATALYST: {top}",
    ]

    wl = briefing.get("watchlist_events", [])
    if wl:
        lines.append("Watchlist-relevant events:")
        for ev in wl[:3]:
            score = ev.get("impact_score", 0)
            hl    = ev.get("headline") or ev.get("title", "")
            lede  = ev.get("lede", "")
            lines.append(f"  [{score}/10] {hl}" + (f" — {lede}" if lede else ""))

    ds = briefing.get("discovered_signals", [])
    if ds:
        lines.append("Discovered signals (outside watchlist):")
        for ev in ds[:2]:
            score  = ev.get("impact_score", 0)
            hl     = ev.get("headline") or ev.get("title", "")
            reason = ev.get("reason_flagged") or ev.get("lede", "")
            lines.append(f"  [{score}/10] {hl}" + (f" — {reason}" if reason else ""))

    return "\n".join(lines)
