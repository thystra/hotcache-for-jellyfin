import pytest


def test_second_run_lock_is_rejected(hotcache, base_config):
    first = hotcache.acquire_run_lock(base_config)
    try:
        with pytest.raises(RuntimeError, match="another jellyfin-hotcache run"):
            hotcache.acquire_run_lock(base_config)
    finally:
        first.close()


def test_run_lock_can_be_reacquired_after_release(hotcache, base_config):
    first = hotcache.acquire_run_lock(base_config)
    first.close()
    second = hotcache.acquire_run_lock(base_config)
    second.close()
