from pathlib import Path


def make_candidate(hotcache, source: Path, library):
    return hotcache.Candidate(
        item_id="item-1",
        user_id="user-1",
        title="Movie",
        source_file=source,
        library=library,
        plays=3,
        last_played="2026-09-26T12:00:00-04:00",
        size_bytes=source.stat().st_size,
        reason="test",
    )


def test_promotion_preserves_original_and_creates_symlink(hotcache, base_config):
    library_root = Path(base_config["libraries"]["movies"][0]["source"])
    cache_root = Path(base_config["cache"]["root"])
    source = library_root / "movie.mkv"
    source.write_bytes(b"abcdef")
    library = hotcache.build_libraries(base_config)[0]
    candidate = make_candidate(hotcache, source, library)
    cache_file = hotcache.build_cache_path(cache_root, candidate)
    manifest = {"version": 1, "items": {}}

    action = hotcache.promote_file(candidate, cache_file, False, manifest, base_config)

    preserved = source.with_name(source.name + ".cached")
    assert action.status == "PROMOTED"
    assert source.is_symlink()
    assert source.resolve() == cache_file.resolve()
    assert cache_file.read_bytes() == b"abcdef"
    assert preserved.read_bytes() == b"abcdef"
    assert manifest["items"][str(source)]["preserved_original"] == str(preserved)


def test_dry_run_promotion_changes_nothing(hotcache, base_config):
    library_root = Path(base_config["libraries"]["movies"][0]["source"])
    cache_root = Path(base_config["cache"]["root"])
    source = library_root / "movie.mkv"
    source.write_bytes(b"abcdef")
    library = hotcache.build_libraries(base_config)[0]
    candidate = make_candidate(hotcache, source, library)
    cache_file = hotcache.build_cache_path(cache_root, candidate)
    manifest = {"version": 1, "items": {}}

    action = hotcache.promote_file(candidate, cache_file, True, manifest, base_config)

    assert action.status == "DRY-RUN PROMOTE"
    assert source.is_file() and not source.is_symlink()
    assert not cache_file.exists()
    assert not source.with_name(source.name + ".cached").exists()
    assert manifest["items"] == {}


def test_can_promote_rejects_active_file(hotcache, base_config):
    library_root = Path(base_config["libraries"]["movies"][0]["source"])
    cache_root = Path(base_config["cache"]["root"])
    source = library_root / "movie.mkv"
    source.write_bytes(b"abcdef")
    library = hotcache.build_libraries(base_config)[0]
    candidate = make_candidate(hotcache, source, library)
    cache_file = hotcache.build_cache_path(cache_root, candidate)

    ok, reason = hotcache.can_promote_file(
        source, cache_file, cache_root,
        10**9, 0, 10**9, 100,
        {str(hotcache.logical_path(source))},
        base_config, candidate,
    )
    assert not ok
    assert "currently being streamed" in reason


def test_can_promote_rejects_existing_preserved_sidecar(hotcache, base_config):
    library_root = Path(base_config["libraries"]["movies"][0]["source"])
    cache_root = Path(base_config["cache"]["root"])
    source = library_root / "movie.mkv"
    source.write_bytes(b"abcdef")
    source.with_name(source.name + ".cached").write_bytes(b"old")
    library = hotcache.build_libraries(base_config)[0]
    candidate = make_candidate(hotcache, source, library)
    cache_file = hotcache.build_cache_path(cache_root, candidate)

    ok, reason = hotcache.can_promote_file(
        source, cache_file, cache_root,
        10**9, 0, 10**9, 100, set(),
        base_config, candidate,
    )
    assert not ok
    assert "sidecar already exists" in reason
