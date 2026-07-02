import core_state as cs
from routes import analysis


def test_effective_unleashed_param_overrides_global():
    cs.save_unleashed({"enabled": False})              # global OFF
    assert analysis._effective_unleashed(True) is True   # per-call override wins
    assert analysis._effective_unleashed(False) is False
    assert analysis._effective_unleashed(None) is False  # None ⇒ read global
    assert cs.load_unleashed()["enabled"] is False        # global never mutated


def test_effective_unleashed_reads_global_when_none():
    cs.save_unleashed({"enabled": True})
    assert analysis._effective_unleashed(None) is True
    cs.save_unleashed({"enabled": False})                 # restore


# ─────────────────────────────────────────────────────────────────────────────
# MCP layer — per-call `unleashed` forwarding (Task 9)
#
# Note: mcp_server._get(path, **params) already forwards to `requests.get(...,
# params=clean)`, filtering out any None-valued kwargs before they ever become
# part of the query string. mcp_server._post(path, body) has no such kwarg
# channel, so scan_assets appends `?unleashed=...` directly onto the path
# string it hands to `_post` (Core's POST /scan reads `unleashed` as a FastAPI
# query param, not a body field). These tests stub `_get`/`_post` at the
# signature the real code actually calls them with.
# ─────────────────────────────────────────────────────────────────────────────

def test_mcp_radar_forwards_unleashed_param(monkeypatch):
    import mcp_server
    captured = {}

    def fake_get(path, **params):
        captured["path"] = path
        captured["params"] = params
        return "ok"

    monkeypatch.setattr(mcp_server, "_get", fake_get)
    mcp_server.get_asset_radar("BTC-USD", mode="swing", unleashed=True)
    assert captured["params"].get("unleashed") is True


def test_mcp_radar_omits_unleashed_when_none(monkeypatch):
    import mcp_server
    captured = {}

    def fake_get(path, **params):
        captured["params"] = params
        return "ok"

    monkeypatch.setattr(mcp_server, "_get", fake_get)
    mcp_server.get_asset_radar("BTC-USD", mode="swing")
    assert captured["params"].get("unleashed") is None


def test_mcp_scan_forwards_unleashed_param(monkeypatch):
    import mcp_server
    captured = {}

    def fake_post(path, body):
        captured["path"] = path
        captured["body"] = body
        return "ok"

    monkeypatch.setattr(mcp_server, "_post", fake_post)
    mcp_server.scan_assets(["BTC-USD"], unleashed=True)
    assert "unleashed=true" in captured["path"].lower()

    mcp_server.scan_assets(["BTC-USD"], unleashed=False)
    assert "unleashed=false" in captured["path"].lower()


def test_mcp_scan_omits_unleashed_when_none(monkeypatch):
    import mcp_server
    captured = {}

    def fake_post(path, body):
        captured["path"] = path
        return "ok"

    monkeypatch.setattr(mcp_server, "_post", fake_post)
    mcp_server.scan_assets(["BTC-USD"])
    assert "unleashed" not in captured["path"].lower()


def test_mcp_nexus_forwards_unleashed_param(monkeypatch):
    import mcp_server
    captured = {}

    def fake_get(path, **params):
        captured["params"] = params
        return "ok"

    monkeypatch.setattr(mcp_server, "_get", fake_get)
    mcp_server.synthesize_nexus("BTC-USD", use_ai=False, unleashed=False)
    assert captured["params"].get("unleashed") is False


def test_mcp_nexus_omits_unleashed_when_none(monkeypatch):
    import mcp_server
    captured = {}

    def fake_get(path, **params):
        captured["params"] = params
        return "ok"

    monkeypatch.setattr(mcp_server, "_get", fake_get)
    mcp_server.synthesize_nexus("BTC-USD", use_ai=False)
    assert captured["params"].get("unleashed") is None
