"""test_auth_token_gate.py — /auth/token same-origin gate.

The token gate deliberately lets /auth/token through WITHOUT a token so the
browser UI can bootstrap. That left a residual hole: any local process could
`GET /auth/token` and read the soul token, then drive the whole API. The
same-origin gate closes the *accidental / naive* case (a bare GET from a
script or a mistaken/injected local AI agent) while leaving the browser UI —
which the browser stamps with same-origin request metadata — working
unchanged.

Honest limitation (documented, not tested here): a deliberate non-browser
client can forge these headers. Fully closing that needs OS-level socket auth.
"""
from starlette.testclient import TestClient

import banshee_core as bc

# The UI may be opened via either host; CORS allows both, so the gate must too.
_UI = "http://localhost:8765"
_UI_ALT = "http://127.0.0.1:8765"


def _raw_client():
    # Plain client — NO auto-injected headers (conftest's patched client would
    # add a token, which is irrelevant here since /auth/token is token-exempt,
    # but we want full control over request headers for this test).
    return TestClient(bc.app)


def test_bare_get_is_forbidden():
    """A naive GET with no origin metadata (curl / script / stray agent) → 403."""
    r = _raw_client().get("/auth/token")
    assert r.status_code == 403
    assert "token" not in r.json()


def test_same_origin_fetch_metadata_allows():
    """The browser stamps its own same-origin fetch → token is served."""
    r = _raw_client().get("/auth/token", headers={"sec-fetch-site": "same-origin"})
    assert r.status_code == 200
    assert r.json()["token"] == bc._BANSHEE_TOKEN


def test_referer_from_ui_allows_both_hosts():
    """UI opened via localhost OR 127.0.0.1 bootstraps via the Referer fallback."""
    for host in (_UI, _UI_ALT):
        r = _raw_client().get("/auth/token", headers={"referer": f"{host}/ui/"})
        assert r.status_code == 200, host
        assert r.json()["token"] == bc._BANSHEE_TOKEN


def test_allowlisted_origin_header_allows():
    """A cross-origin UI fetch (localhost page → 127.0.0.1 API) sends Origin."""
    r = _raw_client().get("/auth/token", headers={"origin": _UI_ALT})
    assert r.status_code == 200
    assert r.json()["token"] == bc._BANSHEE_TOKEN


def test_cross_site_fetch_metadata_forbidden():
    """Explicit cross-site fetch metadata is refused."""
    r = _raw_client().get("/auth/token", headers={"sec-fetch-site": "cross-site"})
    assert r.status_code == 403


def test_foreign_origin_forbidden():
    """An Origin that isn't the Banshee UI is refused."""
    r = _raw_client().get("/auth/token", headers={"origin": "http://evil.example"})
    assert r.status_code == 403


# ── Remote access (Tailscale): the UI is served on a non-localhost host ────────
# The gate must judge same-origin against the Host actually served, not a
# hardcoded localhost list — otherwise opening Banshee at the PC's Tailscale IP
# on a phone would 403 the token bootstrap and blank the app.
_TS = "http://100.64.1.2:8765"   # a Tailscale-range (100.64.0.0/10) address


def test_tailscale_origin_matching_host_allows():
    """Origin host == the Host we answered on → same origin → token served,
    with no Sec-Fetch-Site and no localhost involved."""
    r = TestClient(bc.app, base_url=_TS).get("/auth/token", headers={"origin": _TS})
    assert r.status_code == 200
    assert r.json()["token"] == bc._BANSHEE_TOKEN


def test_tailscale_referer_matching_host_allows():
    """Same, via the Referer fallback (some fetches carry Referer, not Origin)."""
    r = TestClient(bc.app, base_url=_TS).get("/auth/token", headers={"referer": f"{_TS}/ui/"})
    assert r.status_code == 200
    assert r.json()["token"] == bc._BANSHEE_TOKEN


def test_foreign_origin_on_tailscale_host_forbidden():
    """A cross-origin page still can't mint a token when Banshee runs on a
    Tailscale host: its Origin (≠ our Host) fails the dynamic match → 403."""
    r = TestClient(bc.app, base_url=_TS).get("/auth/token", headers={"origin": "http://evil.example"})
    assert r.status_code == 403
