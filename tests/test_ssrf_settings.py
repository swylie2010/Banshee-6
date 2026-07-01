"""tests/test_ssrf_settings.py — SSRF hardening on POST /settings/test (2026-07-01).

The ollama/custom provider branch fetches an operator-supplied URL. The old guard
was IPv4-only (socket.gethostbyname), failed OPEN on any resolution error, and
followed redirects — so an IPv6-resolving host or a 302→metadata redirect slipped
through. These tests pin the hardened behavior:

  * IPv6 addresses are actually resolved and classified (not skipped).
  * Private / loopback / link-local targets are rejected (fail CLOSED).
  * Redirects are never followed (allow_redirects=False).

DNS is monkeypatched so the tests are deterministic and offline.
"""
import socket
import pytest
from fastapi.testclient import TestClient

import banshee_core as bc


@pytest.fixture()
def client():
    return TestClient(bc.app)


def _test_custom(client, url):
    return client.post(
        "/settings/test",
        json={"settings": {"AI_API": {"type": "custom", "url": url}}},
    )


def test_rejects_ipv6_loopback(client, monkeypatch):
    # Host literal is NOT the allow-listed "::1", but resolves to IPv6 loopback.
    # gethostbyname (old code) would have thrown here and failed open.
    monkeypatch.setattr(
        socket, "getaddrinfo",
        lambda host, *a, **k: [(socket.AF_INET6, 0, 0, "", ("::1", 0, 0, 0))],
    )
    r = _test_custom(client, "http://sneaky-ipv6.example:11434")
    body = r.json()
    assert body["status"] == "error"
    assert "private/internal" in body["message"]


def test_rejects_ipv6_link_local(client, monkeypatch):
    monkeypatch.setattr(
        socket, "getaddrinfo",
        lambda host, *a, **k: [(socket.AF_INET6, 0, 0, "", ("fe80::1", 0, 0, 0))],
    )
    r = _test_custom(client, "http://link-local.example:11434")
    assert r.json()["status"] == "error"


def test_rejects_ipv4_metadata_address(client, monkeypatch):
    # 169.254.169.254 (cloud metadata) is link-local → must be rejected.
    monkeypatch.setattr(
        socket, "getaddrinfo",
        lambda host, *a, **k: [(socket.AF_INET, 0, 0, "", ("169.254.169.254", 0))],
    )
    r = _test_custom(client, "http://metadata.example:11434")
    assert r.json()["status"] == "error"


def test_fails_closed_on_resolution_error(client, monkeypatch):
    def _boom(*a, **k):
        raise socket.gaierror("nope")
    monkeypatch.setattr(socket, "getaddrinfo", _boom)
    r = _test_custom(client, "http://does-not-resolve.example:11434")
    body = r.json()
    assert body["status"] == "error"
    assert "resolve" in body["message"].lower()


def test_localhost_still_allowed(client, monkeypatch):
    # Local Ollama must keep working: localhost is the one permitted private target.
    monkeypatch.setattr(
        socket, "getaddrinfo",
        lambda host, *a, **k: [(socket.AF_INET, 0, 0, "", ("127.0.0.1", 0))],
    )
    captured = {}

    class _Resp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"response": "OK"}

    def _fake_post(url, **kwargs):
        captured.update(kwargs)
        return _Resp()

    import requests
    monkeypatch.setattr(requests, "post", _fake_post)
    r = _test_custom(client, "http://localhost:11434")
    assert r.json().get("status") == "ok"


def test_does_not_follow_redirects(client, monkeypatch):
    # A public host is allowed through — but the request must not follow a 302
    # that could bounce to an internal metadata endpoint.
    monkeypatch.setattr(
        socket, "getaddrinfo",
        lambda host, *a, **k: [(socket.AF_INET, 0, 0, "", ("93.184.216.34", 0))],
    )
    captured = {}

    class _Resp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"response": "OK"}

    def _fake_post(url, **kwargs):
        captured.update(kwargs)
        return _Resp()

    import requests
    monkeypatch.setattr(requests, "post", _fake_post)
    r = _test_custom(client, "http://public.example:11434")
    assert r.json().get("status") == "ok"
    assert captured.get("allow_redirects") is False
