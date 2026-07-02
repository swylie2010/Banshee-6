from fastapi.testclient import TestClient
import banshee_core as bc

client = TestClient(bc.app)


def test_base_route_returns_nexus_prompt():
    r = client.get("/unleashed/base", params={"surface": "nexus"})
    assert r.status_code == 200
    body = r.json()
    assert body["surface"] == "nexus"
    assert isinstance(body["text"], str) and len(body["text"]) > 0


def test_base_route_returns_smc_prompt():
    r = client.get("/unleashed/base", params={"surface": "smc"})
    assert r.status_code == 200
    assert r.json()["surface"] == "smc"


def test_base_route_rejects_unknown_surface():
    r = client.get("/unleashed/base", params={"surface": "bogus"})
    assert r.status_code == 400
