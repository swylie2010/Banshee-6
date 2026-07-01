"""routes/audit.py — read-only audit log endpoints."""

import datetime
import json
import pathlib
from collections import Counter, defaultdict

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

import banshee_gateway as gw

router = APIRouter()

# Re-export so tests can monkeypatch this module's reference too
_AUDIT_PATH = gw._AUDIT_PATH


def _read_all_entries() -> list:
    path = _AUDIT_PATH
    if not path.exists():
        return []
    entries = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except Exception:
                continue
    return entries


def _read_entries_in_window(days: int) -> list:
    path = _AUDIT_PATH
    if not path.exists():
        return []
    cutoff = datetime.datetime.utcnow() - datetime.timedelta(days=days)
    entries = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                e = json.loads(line)
                ts = datetime.datetime.strptime(e.get("ts", ""), "%Y-%m-%dT%H:%M:%SZ")
                if ts >= cutoff:
                    entries.append(e)
            except Exception:
                continue
    return entries


@router.get("/audit/entries")
def get_audit_entries(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    tool: str = Query(""),
    since: str = Query(""),
    session: str = Query(""),
):
    entries = _read_all_entries()

    # Filter
    if tool:
        entries = [e for e in entries if e.get("tool") == tool]
    if since:
        try:
            cutoff = datetime.datetime.fromisoformat(since.replace("Z", "+00:00"))
            entries = [
                e for e in entries
                if datetime.datetime.strptime(e.get("ts", ""), "%Y-%m-%dT%H:%M:%SZ")
                >= cutoff.replace(tzinfo=None)
            ]
        except Exception:
            pass
    if session:
        entries = [e for e in entries if e.get("session") == session]

    total = len(entries)
    # Newest first
    entries = list(reversed(entries))
    page = entries[offset: offset + limit]
    return JSONResponse({"total": total, "entries": page})


@router.get("/audit/summary")
def get_audit_summary(days: int = Query(7, ge=1, le=90)):
    entries = _read_entries_in_window(days)
    total = len(entries)

    tool_counts = Counter(e.get("tool", "") for e in entries)
    failed = sum(1 for e in entries if not e.get("validation", {}).get("passed", True))
    failure_rate = round(failed / total, 4) if total > 0 else 0.0

    violation_counts: Counter = Counter()
    for e in entries:
        for v in e.get("validation", {}).get("violations", []):
            violation_counts[v.get("rule", "unknown")] += 1

    signal_counts: Counter = Counter()
    for e in entries:
        sig = e.get("outcome", {}).get("signal", "")
        if sig:
            signal_counts[sig] += 1
    sig_total = sum(signal_counts.values())
    signal_dist = (
        {k: round(v / sig_total, 4) for k, v in signal_counts.most_common()}
        if sig_total else {}
    )

    ticker_counts: Counter = Counter()
    for e in entries:
        req = e.get("request", {})
        syms = req.get("symbols")
        sym = (
            (syms[0] if isinstance(syms, list) and syms else None)
            or req.get("symbol")
            or req.get("underlying")
            or req.get("sym")
        )
        if sym:
            ticker_counts[str(sym)] += 1

    latencies = [
        e.get("outcome", {}).get("duration_ms", 0)
        for e in entries
        if e.get("outcome", {}).get("status") == "success"
    ]
    avg_latency = round(sum(latencies) / len(latencies)) if latencies else 0

    day_counts: dict = defaultdict(int)
    for e in entries:
        day = e.get("ts", "")[:10]
        if day:
            day_counts[day] += 1

    return JSONResponse({
        "period_days": days,
        "calls": {
            "total": total,
            "by_tool": dict(tool_counts.most_common()),
            "validation_failure_rate": failure_rate,
            "per_day": dict(sorted(day_counts.items())),
        },
        "top_violations": [{"rule": r, "count": c} for r, c in violation_counts.most_common(10)],
        "signal_distribution": signal_dist,
        "top_tickers": [t for t, _ in ticker_counts.most_common(10)],
        "avg_latency_ms": avg_latency,
    })
