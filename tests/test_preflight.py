import sqlite3
from pathlib import Path


def test_preflight_is_read_only_when_cache_root_is_missing(hotcache, base_config, monkeypatch, tmp_path):
    missing_cache = tmp_path / "does-not-exist"
    base_config["cache"]["root"] = str(missing_cache)

    db_path = Path(base_config["playback_reporting"]["database_path"])
    con = sqlite3.connect(db_path)
    con.execute("CREATE TABLE PlaybackActivity (ItemId TEXT, DateCreated TEXT)")
    con.commit()
    con.close()

    monkeypatch.setattr(hotcache, "jellyfin_get", lambda *_args, **_kwargs: [])

    rc = hotcache.run_preflight(base_config)
    assert rc == 1
    assert not missing_cache.exists()
