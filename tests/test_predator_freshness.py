"""tests/test_predator_freshness.py — the auto-refresh decision gate.

The background freshness loop (banshee_core) triggers a Daily Predator run only
when should_auto_refresh() is True. Keeping the decision a pure function lets us
test the 8am-local gate / missing-briefing / no-AI-key branches without threads,
network, or AI calls.
"""
import predator_engine as pe


def test_refresh_when_stale_key_and_past_8am():
    assert pe.should_auto_refresh(8, briefing_exists_today=False, has_ai_key=True) is True
    assert pe.should_auto_refresh(14, briefing_exists_today=False, has_ai_key=True) is True


def test_no_refresh_before_8am_local():
    # A machine left on overnight must NOT fire a pointless 00:05 run.
    assert pe.should_auto_refresh(7, briefing_exists_today=False, has_ai_key=True) is False
    assert pe.should_auto_refresh(0, briefing_exists_today=False, has_ai_key=True) is False


def test_no_refresh_when_today_already_exists():
    assert pe.should_auto_refresh(10, briefing_exists_today=True, has_ai_key=True) is False


def test_no_refresh_without_ai_key():
    assert pe.should_auto_refresh(10, briefing_exists_today=False, has_ai_key=False) is False


def test_briefing_is_stale_helper():
    import datetime
    today = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    assert pe.briefing_is_stale(None) is True
    assert pe.briefing_is_stale({}) is True
    assert pe.briefing_is_stale({"date": "2000-01-01"}) is True
    assert pe.briefing_is_stale({"date": today}) is False
