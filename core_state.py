"""
core_state.py — Banshee 6 Shared Constants, Caches, and Pure Utilities
=======================================================================
Extracted from banshee_core.py as foundation for domain-module refactor.
No side effects on import — only definitions.
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

# ── Constants ─────────────────────────────────────────────────────────────────
PORT              = 8765
_MACRO_CACHE_FILE = Path.home() / ".banshee_macro_cache.json"
_CACHE_TTL        = 15 * 60   # seconds
_STRATEGIES_FILE  = os.path.join(os.path.dirname(os.path.abspath(__file__)), "strategies.json")

MODE_ALIASES = {
    "active":    "swing",
    "position":  "long_term",
    "long_term": "long_term",
    "swing":     "swing",
    "sniper":    "sniper",
}

_OHLCV_TTL   = 5 * 60   # 5 minutes — shared symbol cache across UI + MCP calls
_OHLCV_CACHE: dict = {}  # (symbol_upper, mode) → {"tfs": dict, "ts": float}

# Response-level cache for slow compute endpoints (radar analysis, SMC engine)
# Key: str cache key  →  {"ts": float, "body": str}
_RESP_TTL   = 3 * 60   # 3 minutes
_RESP_CACHE: dict = {}

_KILL_SWITCH_FILE = Path.home() / ".banshee_kill_switch.json"

_PRESETS_PATH      = Path(__file__).parent / "banshee_presets.json"
_PORTFOLIO_PATH    = Path(__file__).parent / "banshee_portfolio.json"
_WHEELS_PATH       = Path(__file__).parent / "banshee_wheels.json"
_PAPER_WHEELS_PATH = Path(__file__).parent / "paper_wheels.json"


# ── Pure utility functions ────────────────────────────────────────────────────

def _sanitize(obj):
    """Recursively convert numpy/pandas/non-JSON types to Python natives so jsonable_encoder doesn't 500."""
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize(v) for v in obj]
    if isinstance(obj, pd.DataFrame):
        return _df_to_records(obj)
    if isinstance(obj, pd.Series):
        return [_sanitize(v) for v in obj.tolist()]
    if isinstance(obj, np.bool_):
        return bool(obj)
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        v = float(obj)
        return None if (v != v) else v  # NaN != NaN is the NaN check
    if isinstance(obj, float) and obj != obj:
        return None  # plain Python NaN
    if isinstance(obj, np.datetime64):
        return str(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    return obj


def _df_to_records(df) -> list:
    """Serialize a DataFrame to JSON-safe records list."""
    if df is None or (hasattr(df, "empty") and df.empty):
        return []
    return json.loads(df.to_json(orient="records", date_format="iso"))


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("Data as of %Y-%m-%d %H:%M UTC")


def _cache_age_min() -> int | None:
    try:
        if not _MACRO_CACHE_FILE.exists():
            return None
        age = datetime.now(timezone.utc).timestamp() - _MACRO_CACHE_FILE.stat().st_mtime
        return max(0, int(age / 60))
    except Exception:
        return None


def _cache_header(source: str) -> str:
    if source == "cache":
        age = _cache_age_min()
        age_str = f"{age} min ago" if age is not None else "age unknown"
        return f"Data as of now  [macro cached {age_str} — max 15 min delay]"
    return _ts() + "  [live]"


def _load_macro_cache() -> dict | None:
    try:
        if not _MACRO_CACHE_FILE.exists():
            return None
        age = datetime.now(timezone.utc).timestamp() - _MACRO_CACHE_FILE.stat().st_mtime
        if age > _CACHE_TTL:
            return None
        with open(_MACRO_CACHE_FILE) as f:
            return json.load(f)
    except Exception:
        return None


def _save_macro_cache(mac_data: dict, news_lines: list, events: list):
    try:
        payload = {"mac_data": mac_data, "news_lines": news_lines, "events": events}
        with open(_MACRO_CACHE_FILE, "w") as f:
            json.dump(payload, f)
    except Exception:
        pass


def _load_kill_switch_state() -> dict:
    try:
        if _KILL_SWITCH_FILE.exists():
            return json.loads(_KILL_SWITCH_FILE.read_text())
    except Exception:
        pass
    return {"fired": False, "fired_at": None, "positions_closed": [], "domino_phase": 0, "regime": ""}


def _save_kill_switch_state(state: dict):
    try:
        _KILL_SWITCH_FILE.write_text(json.dumps(state, indent=2))
    except Exception:
        pass
