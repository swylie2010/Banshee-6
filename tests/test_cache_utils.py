import time
from cache_utils import ttl_cache


def test_expired_entries_are_evicted():
    call_count = 0

    @ttl_cache(ttl=1)
    def my_func(x):
        nonlocal call_count
        call_count += 1
        return x * 2

    # Populate with two different keys
    my_func(1)
    my_func(2)
    assert call_count == 2

    # Wait for both to expire
    time.sleep(1.1)

    # Call with a new key — this insert should evict key(1) and key(2)
    my_func(3)
    assert call_count == 3

    # key(1) should have been evicted, so re-calling it must re-execute
    my_func(1)
    assert call_count == 4


def test_unexpired_entries_are_not_evicted():
    call_count = 0

    @ttl_cache(ttl=60)
    def my_func(x):
        nonlocal call_count
        call_count += 1
        return x

    my_func(1)
    my_func(2)
    assert call_count == 2

    # Call with a new key — no entries expired, so 1 and 2 stay cached
    my_func(3)
    my_func(1)  # should hit cache, not call the function
    assert call_count == 3  # only my_func(3) triggered a new call
