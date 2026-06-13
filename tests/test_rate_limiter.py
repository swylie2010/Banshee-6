import pytest
import time
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient


# ── Unit tests for _AiRateLimiter ────────────────────────────────────────────

def test_limiter_allows_calls_up_to_cap():
    from core_state import _AiRateLimiter
    limiter = _AiRateLimiter()
    for i in range(5):
        allowed, count, _ = limiter.check(max_calls=5)
        assert allowed is True, f"Call {i+1} should be allowed"
        assert count == i + 1


def test_limiter_blocks_call_at_cap_plus_one():
    from core_state import _AiRateLimiter
    limiter = _AiRateLimiter()
    for _ in range(5):
        limiter.check(max_calls=5)
    allowed, count, reset_ts = limiter.check(max_calls=5)
    assert allowed is False
    assert count == 5
    assert reset_ts > 0


def test_limiter_does_not_increment_when_blocked():
    from core_state import _AiRateLimiter
    limiter = _AiRateLimiter()
    for _ in range(3):
        limiter.check(max_calls=3)
    # Two blocked calls
    limiter.check(max_calls=3)
    limiter.check(max_calls=3)
    # Internal deque should still have exactly 3 timestamps
    assert len(limiter._timestamps) == 3


def test_limiter_resets_after_window():
    from core_state import _AiRateLimiter
    limiter = _AiRateLimiter()

    fake_now = [0.0]

    def mock_time():
        return fake_now[0]

    with patch("core_state.time.time", side_effect=mock_time):
        # Fill the cap at t=0
        for _ in range(3):
            limiter.check(max_calls=3, window_sec=60)

        # Advance past the window
        fake_now[0] = 61.0
        allowed, count, _ = limiter.check(max_calls=3, window_sec=60)

    assert allowed is True
    assert count == 1


def test_limiter_reset_ts_is_correct():
    from core_state import _AiRateLimiter
    limiter = _AiRateLimiter()
    t0 = time.time()
    for _ in range(3):
        limiter.check(max_calls=3, window_sec=3600)
    _, _, reset_ts = limiter.check(max_calls=3, window_sec=3600)
    # reset_ts should be approximately t0 + 3600
    assert abs(reset_ts - (t0 + 3600)) < 2.0


# ── check_ai_budget() behaviour ───────────────────────────────────────────────

def test_check_ai_budget_raises_429_when_over_limit():
    from core_state import _AiRateLimiter, check_ai_budget
    from fastapi import HTTPException

    # Replace the module-level singleton with a full limiter
    mock_limiter = _AiRateLimiter()
    # Fill it up
    for _ in range(50):
        mock_limiter.check(max_calls=50)

    with patch("core_state._ai_rate_limiter", mock_limiter), \
         patch("shared_data.load_providers", return_value={"ai_rate_limit_per_hour": 50}):
        with pytest.raises(HTTPException) as exc_info:
            check_ai_budget()

    assert exc_info.value.status_code == 429
    assert "rate limit" in exc_info.value.detail.lower()
    assert "Resets at" in exc_info.value.detail


def test_check_ai_budget_allows_when_under_limit():
    from core_state import _AiRateLimiter, check_ai_budget

    mock_limiter = _AiRateLimiter()

    with patch("core_state._ai_rate_limiter", mock_limiter), \
         patch("shared_data.load_providers", return_value={"ai_rate_limit_per_hour": 50}):
        # Should not raise
        check_ai_budget()


def test_check_ai_budget_respects_custom_cap():
    from core_state import _AiRateLimiter, check_ai_budget
    from fastapi import HTTPException

    mock_limiter = _AiRateLimiter()
    # Fill up to cap=2
    for _ in range(2):
        mock_limiter.check(max_calls=2)

    with patch("core_state._ai_rate_limiter", mock_limiter), \
         patch("shared_data.load_providers", return_value={"ai_rate_limit_per_hour": 2}):
        with pytest.raises(HTTPException) as exc_info:
            check_ai_budget()

    assert exc_info.value.status_code == 429
