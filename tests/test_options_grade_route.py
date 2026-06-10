from fastapi.testclient import TestClient
import banshee_core
import options_data

client = TestClient(banshee_core.app)

def _fake_chain(sym, *a, **k):
    return ([{"type": "put", "strike": 480.0, "iv": 0.22,
              "open_interest": 5000, "dte": 42}],
            {"sym": sym, "spot": 500.0, "as_of": "2026-06-10"})

def _fake_closes(sym, *a, **k):
    return [500.0 * (1 + 0.001 * ((i % 7) - 3)) for i in range(60)]

def test_grade_route_clean_spy(monkeypatch):
    monkeypatch.setattr(options_data, "fetch_chain", _fake_chain)
    monkeypatch.setattr(options_data, "fetch_closes", _fake_closes)
    r = client.post("/options/grade", json={
        "underlying": "SPY", "strike": 480.0, "dte": 42,
        "cash_backed": True, "account_size": 2_000_000})
    assert r.status_code == 200
    body = r.json()
    assert body["passes_all"] is True
    assert body["failed"] == []

def test_grade_route_missing_fields_is_400(monkeypatch):
    monkeypatch.setattr(options_data, "fetch_chain", _fake_chain)
    monkeypatch.setattr(options_data, "fetch_closes", _fake_closes)
    r = client.post("/options/grade", json={"underlying": "SPY"})
    assert r.status_code == 400
    assert "error" in r.json()
