import pytest


def test_sessions_api_failure_is_fatal(hotcache, monkeypatch):
    def fail(*_args, **_kwargs):
        raise RuntimeError("API unavailable")

    monkeypatch.setattr(hotcache, "jellyfin_get", fail)
    with pytest.raises(RuntimeError, match="API unavailable"):
        hotcache.get_active_paths({})


def test_unexpected_sessions_response_is_fatal(hotcache, monkeypatch):
    monkeypatch.setattr(hotcache, "jellyfin_get", lambda *_args, **_kwargs: {"bad": "shape"})
    with pytest.raises(RuntimeError, match="unexpected response"):
        hotcache.get_active_paths({})
