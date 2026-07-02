"""
core_state.py — Banshee 6 Shared Constants, Caches, and Pure Utilities
=======================================================================
Extracted from banshee_core.py as foundation for domain-module refactor.
No side effects on import — only definitions.
"""

import json
import os
import time
import threading
import traceback
import secrets
from collections import deque
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
_OHLCV_CACHE: dict = {}  # (symbol_upper, mode, deep) → {"tfs": dict, "ts": float}

# Response-level cache for slow compute endpoints (radar analysis, SMC engine)
# Key: str cache key  →  {"ts": float, "body": str}
_RESP_TTL   = 3 * 60   # 3 minutes
_RESP_CACHE: dict = {}

_KILL_SWITCH_FILE = Path.home() / ".banshee_kill_switch.json"
_ERROR_LOG        = Path.home() / ".banshee_errors.log"

_PRESETS_PATH      = Path(__file__).parent / "banshee_presets.json"
_PORTFOLIO_PATH    = Path(__file__).parent / "banshee_portfolio.json"
_WHEELS_PATH       = Path(__file__).parent / "banshee_wheels.json"
_PAPER_WHEELS_PATH = Path(__file__).parent / "paper_wheels.json"
_PAPER_SPREADS_PATH = Path(__file__).parent / "paper_spreads.json"
_PAPER_GRIDBOT_PATH = Path(__file__).parent / "paper_gridbot.json"

# ── File locks (prevent concurrent write corruption) ─────────────────────────
_MACRO_CACHE_LOCK    = threading.Lock()
_KILL_SWITCH_LOCK    = threading.Lock()
_UNLEASHED_FILE      = Path.home() / ".banshee_unleashed.json"
_UNLEASHED_LOCK      = threading.Lock()

# ── Unleashed prompt profiles (editable override layer) ──────────────────────
DEFAULT_UNLEASHED_OVERRIDE = (
    "\n\n--- UNLEASHED OVERRIDE ---\n"
    "You are in UNLEASHED mode. Make the short-term call directly; do not hedge it into a "
    "non-answer. Evaluate SHORTS and LONGS symmetrically. When the higher-timeframe Bias and "
    "the lower-timeframe Trigger conflict, state BOTH explicitly — e.g. 'Long-term bias: X; "
    "short-term trigger: Y here, with risk Z.' These are short-term possibilities, not safe "
    "trades; you surface and state the risk, the human/agent decides. Never instruct an execution."
)
_UNLEASHED_PROFILES_FILE = Path.home() / ".banshee_unleashed_profiles.json"
_UNLEASHED_PROFILES_LOCK = threading.Lock()


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
        with _MACRO_CACHE_LOCK:
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
        with _KILL_SWITCH_LOCK:
            _KILL_SWITCH_FILE.write_text(json.dumps(state, indent=2))
    except Exception:
        pass


def load_unleashed() -> dict:
    """Global Unleashed-mode toggle. Defaults to disabled (conservative)."""
    try:
        if _UNLEASHED_FILE.exists():
            data = json.loads(_UNLEASHED_FILE.read_text())
            return {"enabled": bool(data.get("enabled", False))}
    except Exception:
        pass
    return {"enabled": False}


def save_unleashed(state: dict) -> None:
    try:
        with _UNLEASHED_LOCK:
            _UNLEASHED_FILE.write_text(json.dumps({"enabled": bool(state.get("enabled", False))}, indent=2))
    except Exception:
        pass


def _surface_slot(text: str, mode: str = "nudge") -> dict:
    return {"mode": mode if mode in ("nudge", "rewrite") else "nudge", "text": text or ""}


def _default_unleashed_profiles() -> dict:
    return {
        "active": "default",
        "profiles": {
            "default": {
                "name": "Default Unleashed",
                "locked": True,
                "surfaces": {
                    "nexus": _surface_slot(DEFAULT_UNLEASHED_OVERRIDE),
                    "smc":   _surface_slot(DEFAULT_UNLEASHED_OVERRIDE),
                },
            }
        },
    }


def _migrate_profile(prof: dict) -> dict:
    """Upgrade a legacy {name, override, locked} profile to per-surface slots.
    Idempotent: a profile already carrying `surfaces` is re-normalized through
    `_surface_slot` (mode re-clamped, text coerced) and its `surfaces` dict is
    rebuilt from scratch so extraneous surface keys are dropped and any missing
    surface is filled from stock. A non-dict entry (hand-corrupted file) is
    replaced with a fresh Recovered profile so the load stays fail-safe."""
    if not isinstance(prof, dict):
        return {"name": "Recovered", "locked": False,
                "surfaces": {"nexus": _surface_slot(""), "smc": _surface_slot("")}}
    existing = prof.get("surfaces")
    if isinstance(existing, dict):
        rebuilt = {}
        for surface in ("nexus", "smc"):
            slot = existing.get(surface)
            if isinstance(slot, dict):
                rebuilt[surface] = _surface_slot(slot.get("text", ""), slot.get("mode", "nudge"))
            else:
                rebuilt[surface] = _surface_slot("")
        prof.pop("override", None)
        prof["surfaces"] = rebuilt
        return prof
    legacy = prof.pop("override", "") or ""
    prof["surfaces"] = {"nexus": _surface_slot(legacy), "smc": _surface_slot(legacy)}
    return prof


def load_unleashed_profiles() -> dict:
    """Editable Unleashed profiles. Every profile is migrated to the per-surface
    schema on load; the Default profile is force-reset to the canonical constant."""
    data = None
    try:
        if _UNLEASHED_PROFILES_FILE.exists():
            loaded = json.loads(_UNLEASHED_PROFILES_FILE.read_text())
            if isinstance(loaded, dict) and isinstance(loaded.get("profiles"), dict):
                data = loaded
    except Exception:
        data = None
    if data is None:
        return _default_unleashed_profiles()
    for pid, prof in list(data["profiles"].items()):
        data["profiles"][pid] = _migrate_profile(prof)
    # Enforce the Default invariant every load.
    data["profiles"]["default"] = _default_unleashed_profiles()["profiles"]["default"]
    if data.get("active") not in data["profiles"]:
        data["active"] = "default"
    return data


def save_unleashed_profiles(data: dict) -> None:
    try:
        with _UNLEASHED_PROFILES_LOCK:
            _UNLEASHED_PROFILES_FILE.write_text(json.dumps(data, indent=2))
    except Exception:
        pass


def get_active_unleashed_override() -> str:
    data = load_unleashed_profiles()
    prof = data["profiles"].get(data["active"]) or data["profiles"]["default"]
    return prof.get("override", DEFAULT_UNLEASHED_OVERRIDE)


def get_active_unleashed_profile() -> dict:
    data = load_unleashed_profiles()
    prof = data["profiles"].get(data["active"], data["profiles"]["default"])
    return {"id": data["active"], "name": prof.get("name", "Default Unleashed")}


def upsert_unleashed_profile(pid, name: str, surfaces: dict) -> dict:
    if pid == "default":
        return {"ok": False, "error": "The Default Unleashed profile is locked and cannot be edited."}
    data = load_unleashed_profiles()
    if not pid:
        # token_hex(3) is plenty of entropy for a handful of profiles; the loop
        # guards against the astronomically unlikely collision so we never clobber.
        pid = "u_" + secrets.token_hex(3)
        while pid in data["profiles"]:
            pid = "u_" + secrets.token_hex(3)
    # Custom profiles carry locked=False so every stored entry matches the
    # documented {name, surfaces, locked} shape (Default is the only locked one).
    clean = {}
    for surface in ("nexus", "smc"):
        slot = (surfaces or {}).get(surface) or {}
        clean[surface] = _surface_slot(slot.get("text", ""), slot.get("mode", "nudge"))
    data["profiles"][pid] = {"name": name, "locked": False, "surfaces": clean}
    save_unleashed_profiles(data)
    return {"ok": True, "id": pid}


def delete_unleashed_profile(pid: str) -> dict:
    if pid == "default":
        return {"ok": False, "error": "The Default Unleashed profile cannot be deleted."}
    data = load_unleashed_profiles()
    if pid in data["profiles"]:
        del data["profiles"][pid]
        if data.get("active") == pid:
            data["active"] = "default"
        save_unleashed_profiles(data)
    return {"ok": True}


def set_active_unleashed_profile(pid: str) -> dict:
    data = load_unleashed_profiles()
    if pid not in data["profiles"]:
        return {"ok": False, "error": f"No such profile: {pid}"}
    data["active"] = pid
    save_unleashed_profiles(data)
    return {"ok": True, "active": pid}


def _log_error(context: str, exc: Exception) -> None:
    """Append a timestamped error entry to ~/.banshee_errors.log. Never raises."""
    try:
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        entry = f"\n[{ts}] {context}\n{traceback.format_exc()}\n"
        with open(_ERROR_LOG, "a", encoding="utf-8") as f:
            f.write(entry)
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────────────────────
# AI RATE LIMITER
# ─────────────────────────────────────────────────────────────────────────────

class _AiRateLimiter:
    def __init__(self):
        self._timestamps: deque = deque()
        self._lock = threading.Lock()

    def check(self, max_calls: int, window_sec: int = 3600) -> tuple[bool, int, float]:
        """Check budget and increment if allowed.
        Returns (allowed, calls_in_window, reset_unix_ts).
        reset_unix_ts is 0.0 when allowed."""
        now = time.time()
        with self._lock:
            while self._timestamps and now - self._timestamps[0] > window_sec:
                self._timestamps.popleft()
            count = len(self._timestamps)
            if count >= max_calls:
                return False, count, self._timestamps[0] + window_sec
            self._timestamps.append(now)
            return True, count + 1, 0.0


_ai_rate_limiter = _AiRateLimiter()


def check_ai_budget() -> None:
    """Raise HTTP 429 if the AI call budget is exhausted.
    Call at the top of any AI-invoking route handler."""
    from fastapi import HTTPException
    from datetime import datetime, timezone
    from shared_data import load_providers
    cap = int(load_providers().get("ai_rate_limit_per_hour", 50))
    allowed, calls, reset_ts = _ai_rate_limiter.check(max_calls=cap)
    if not allowed:
        reset_str = datetime.fromtimestamp(reset_ts, tz=timezone.utc).strftime("%H:%M UTC")
        raise HTTPException(
            status_code=429,
            detail=(
                f"AI rate limit reached ({calls} calls in the last hour). "
                f"Resets at {reset_str}."
            ),
        )
