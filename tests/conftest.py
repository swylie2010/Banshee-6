"""conftest.py — session-wide setup for Banshee route tests.

The soul token gate (_TokenGate middleware) was added in B6. All TestClient-based
route tests need a token header. We handle this once here:
  1. Override _BANSHEE_TOKEN with a predictable test value.
  2. Subclass TestClient to auto-inject the header on every request.
  3. Patch fastapi.testclient.TestClient so existing test files pick it up
     without modification (conftest.py loads before test modules are imported).
"""
import fastapi.testclient as _ftc
from starlette.testclient import TestClient as _BaseClient

import banshee_core as bc

_TEST_TOKEN = "pytest-banshee-token"
bc._BANSHEE_TOKEN = _TEST_TOKEN


class _AuthClient(_BaseClient):
    def __init__(self, app, **kwargs):
        h = dict(kwargs.pop("headers", None) or {})
        h.setdefault("x-banshee-token", _TEST_TOKEN)
        super().__init__(app, headers=h, **kwargs)


# Patch both the starlette and fastapi exports so any import style gets the
# authenticated client.
_ftc.TestClient = _AuthClient
