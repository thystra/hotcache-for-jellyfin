from pathlib import Path


def prepared_cached_item(hotcache, base_config):
    library_root = Path(base_config["libraries"]["movies"][0]["source"])
    cache_root = Path(base_config["cache"]["root"])
    source = library_root / "movie.mkv"
    cache = cache_root / "movies" / "movie.mkv"
    cache.parent.mkdir(parents=True)
    cache.write_bytes(b"abcdef")
    preserved = source.with_name(source.name + ".cached")
    preserved.write_bytes(b"abcdef")
    source.symlink_to(cache)
    manifest = {
        "version": 1,
        "items": {
            str(source): {
                "title": "Movie",
                "cache": str(cache),
                "preserved_original": str(preserved),
                "size_bytes": 6,
            }
        },
    }
    return source, cache, preserved, manifest


def test_restore_returns_preserved_original(hotcache, base_config):
    source, cache, preserved, manifest = prepared_cached_item(hotcache, base_config)
    actions = hotcache.restore_all_cached_files(base_config, manifest, set(), False)

    assert actions[0].status == "RESTORED"
    assert source.is_file() and not source.is_symlink()
    assert source.read_bytes() == b"abcdef"
    assert not cache.exists()
    assert not preserved.exists()
    assert manifest["items"] == {}


def test_restore_refuses_wrong_symlink_target(hotcache, base_config, tmp_path):
    source, cache, _preserved, manifest = prepared_cached_item(hotcache, base_config)
    source.unlink()
    wrong = tmp_path / "wrong.mkv"
    wrong.write_bytes(b"abcdef")
    source.symlink_to(wrong)

    actions = hotcache.restore_all_cached_files(base_config, manifest, set(), False)
    assert actions[0].status == "SKIPPED RESTORE"
    assert "does not match" in actions[0].reason
    assert source.is_symlink()
    assert cache.exists()


def test_restore_removes_stale_manifest_entry(hotcache, base_config):
    library_root = Path(base_config["libraries"]["movies"][0]["source"])
    cache_root = Path(base_config["cache"]["root"])
    source = library_root / "movie.mkv"
    source.write_bytes(b"restored")
    cache = cache_root / "missing.mkv"
    manifest = {
        "version": 1,
        "items": {str(source): {"title": "Movie", "cache": str(cache), "size_bytes": 8}},
    }

    actions = hotcache.restore_all_cached_files(base_config, manifest, set(), False)
    assert actions[0].status == "REMOVED STALE MANIFEST ENTRY"
    assert manifest["items"] == {}


def test_restore_keeps_dangling_symlink_for_manual_repair(hotcache, base_config):
    library_root = Path(base_config["libraries"]["movies"][0]["source"])
    cache_root = Path(base_config["cache"]["root"])
    source = library_root / "movie.mkv"
    cache = cache_root / "missing.mkv"
    source.symlink_to(cache)
    manifest = {
        "version": 1,
        "items": {str(source): {"title": "Movie", "cache": str(cache), "size_bytes": 8}},
    }

    actions = hotcache.restore_all_cached_files(base_config, manifest, set(), False)
    assert actions[0].status == "SKIPPED RESTORE"
    assert "manual repair" in actions[0].reason
    assert source.is_symlink()
    assert str(source) in manifest["items"]
