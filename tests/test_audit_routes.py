"""tests/test_audit_routes.py — tests for GET /audit/entries and GET /audit/summary."""
import json
import pathlib
import pytest
from fastapi.testclient import TestClient

import banshee_gateway as gw
import banshee_core as bc


@pytest.fixture()
def client():
    return TestClient(bc.app)


@pytest.fixture(autouse=True)
def tmp_audit(tmp_path, monkeypatch):
    audit = tmp_path / "test_audit.jsonl"
    monkeypatch.setattr(gw, "_AUDIT_PATH", audit)
    import routes.audit as ra
    monkeypatch.setattr(ra, "_AUDIT_PATH", audit)
    return audit


def _write_entries(audit_path, entries):
    with open(audit_path, "w") as f:
        for e in entries:
            f.write(json.dumps(e) + "\n")


# ── /audit/entries ────────────────────────────────────────────────────────────

def test_entries_empty_log(client, tmp_audit):
    r = client.get("/audit/entries")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 0
    assert data["entries"] == []


def test_entries_returns_newest_first(client, tmp_audit):
    _write_entries(tmp_audit, [
        {"id": "aud_1", "ts": "2026-06-20T10:00:00Z", "tool": "get_regime",
         "session": "anon", "request": {}, "validation": {"passed": True, "rules_checked": [], "violations": []},
         "outcome": {"status": "success", "duration_ms": 10}},
        {"id": "aud_2", "ts": "2026-06-20T11:00:00Z", "tool": "synthesize_nexus",
         "session": "anon", "request": {"symbol": "AAPL"}, "validation": {"passed": True, "rules_checked": [], "violations": []},
         "outcome": {"status": "success", "duration_ms": 300}},
    ])
    r = client.get("/audit/entries")
    assert r.status_code == 200
    entries = r.json()["entries"]
    assert entries[0]["id"] == "aud_2"  # newest first
    assert entries[1]["id"] == "aud_1"


def test_entries_filter_by_tool(client, tmp_audit):
    _write_entries(tmp_audit, [
        {"id": "aud_1", "ts": "2026-06-20T10:00:00Z", "tool": "get_regime",
         "session": "anon", "request": {}, "validation": {"passed": True, "rules_checked": [], "violations": []},
         "outcome": {"status": "success", "duration_ms": 10}},
        {"id": "aud_2", "ts": "2026-06-20T11:00:00Z", "tool": "synthesize_nexus",
         "session": "anon", "request": {"symbol": "AAPL"}, "validation": {"passed": True, "rules_checked": [], "violations": []},
         "outcome": {"status": "success", "duration_ms": 300}},
    ])
    r = client.get("/audit/entries?tool=get_regime")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 1
    assert data["entries"][0]["tool"] == "get_regime"


def test_entries_limit(client, tmp_audit):
    entries = [
        {"id": f"aud_{i}", "ts": f"2026-06-20T{i:02d}:00:00Z", "tool": "get_regime",
         "session": "anon", "request": {}, "validation": {"passed": True, "rules_checked": [], "violations": []},
         "outcome": {"status": "success", "duration_ms": 10}}
        for i in range(10)
    ]
    _write_entries(tmp_audit, entries)
    r = client.get("/audit/entries?limit=3")
    assert r.status_code == 200
    assert len(r.json()["entries"]) == 3


# ── /audit/summary ────────────────────────────────────────────────────────────

def test_summary_empty_log(client, tmp_audit):
    r = client.get("/audit/summary")
    assert r.status_code == 200
    data = r.json()
    assert data["calls"]["total"] == 0
    assert data["avg_latency_ms"] == 0


def test_summary_counts_tools(client, tmp_audit):
    _write_entries(tmp_audit, [
        {"id": "aud_1", "ts": "2026-06-20T10:00:00Z", "tool": "synthesize_nexus",
         "session": "anon", "request": {"symbol": "AAPL"}, "validation": {"passed": True, "rules_checked": [], "violations": []},
         "outcome": {"status": "success", "duration_ms": 300}},
        {"id": "aud_2", "ts": "2026-06-20T11:00:00Z", "tool": "synthesize_nexus",
         "session": "anon", "request": {"symbol": "NVDA"}, "validation": {"passed": True, "rules_checked": [], "violations": []},
         "outcome": {"status": "success", "duration_ms": 280}},
        {"id": "aud_3", "ts": "2026-06-20T12:00:00Z", "tool": "get_regime",
         "session": "anon", "request": {}, "validation": {"passed": True, "rules_checked": [], "violations": []},
         "outcome": {"status": "success", "duration_ms": 40}},
    ])
    r = client.get("/audit/summary?days=7")
    assert r.status_code == 200
    data = r.json()
    assert data["calls"]["total"] == 3
    assert data["calls"]["by_tool"]["synthesize_nexus"] == 2
    assert data["calls"]["by_tool"]["get_regime"] == 1


def test_summary_validation_failure_rate(client, tmp_audit):
    _write_entries(tmp_audit, [
        {"id": "aud_1", "ts": "2026-06-20T10:00:00Z", "tool": "get_asset_radar",
         "session": "anon", "request": {"symbol": "AAPL", "mode": "badmode"},
         "validation": {"passed": False, "rules_checked": [], "violations": [{"rule": "mode"}]},
         "outcome": {"status": "rejected", "duration_ms": 0}},
        {"id": "aud_2", "ts": "2026-06-20T11:00:00Z", "tool": "get_regime",
         "session": "anon", "request": {}, "validation": {"passed": True, "rules_checked": [], "violations": []},
         "outcome": {"status": "success", "duration_ms": 40}},
    ])
    r = client.get("/audit/summary")
    data = r.json()
    assert data["calls"]["validation_failure_rate"] == 0.5


def test_summary_top_tickers(client, tmp_audit):
    _write_entries(tmp_audit, [
        {"id": "aud_1", "ts": "2026-06-20T10:00:00Z", "tool": "synthesize_nexus",
         "session": "anon", "request": {"symbol": "AAPL"}, "validation": {"passed": True, "rules_checked": [], "violations": []},
         "outcome": {"status": "success", "duration_ms": 300}},
        {"id": "aud_2", "ts": "2026-06-20T11:00:00Z", "tool": "get_asset_radar",
         "session": "anon", "request": {"symbol": "AAPL"}, "validation": {"passed": True, "rules_checked": [], "violations": []},
         "outcome": {"status": "success", "duration_ms": 200}},
    ])
    r = client.get("/audit/summary")
    assert "AAPL" in r.json()["top_tickers"]
