"""
cache_utils.py — Banshee Pro Cache Utilities
============================================
Process-level TTL cache for engine functions. Replaces @st.cache_data so
engine files have zero Streamlit dependency and can run headless.

When FastAPI Core is built, caching moves there and this file is retired.
"""

import time
from functools import wraps


def ttl_cache(ttl: int = 900, skip_none: bool = False):
    """
    Drop-in replacement for @st.cache_data(ttl=..., show_spinner=False).
    Each decorated function gets its own isolated cache dict (per closure).
    Keys are built from (args, sorted kwargs) — works for all simple types.

    skip_none=True: do not cache None results (retry on next call).
    """
    def decorator(func):
        _cache: dict = {}

        @wraps(func)
        def wrapper(*args, **kwargs):
            key = (args, tuple(sorted(kwargs.items())))
            now = time.monotonic()
            entry = _cache.get(key)
            if entry is not None and now - entry[0] < ttl:
                return entry[1]
            result = func(*args, **kwargs)
            if not (skip_none and result is None):
                # evict expired entries before inserting to prevent unbounded growth
                expired = [k for k, v in _cache.items() if now - v[0] >= ttl]
                for k in expired:
                    del _cache[k]
                _cache[key] = (now, result)
            return result

        return wrapper
    return decorator
