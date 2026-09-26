from pathlib import Path

import pytest


def test_cached_symlink_keeps_logical_library_identity(hotcache, tmp_path):
    library_root = tmp_path / "library"
    cache_root = tmp_path / "cache"
    library_root.mkdir()
    cache_root.mkdir()
    cached = cache_root / "movie.mkv"
    cached.write_bytes(b"movie")
    logical = library_root / "movie.mkv"
    logical.symlink_to(cached)

    library = hotcache.Library("Movies", "movie", library_root, Path("movies"), 2)
    assert hotcache.find_matching_library(logical, [library]) == library
    assert hotcache.safe_relative_path(logical, library_root) == Path("movie.mkv")


def test_safe_relative_path_rejects_outside_library(hotcache, tmp_path):
    library_root = tmp_path / "library"
    outside = tmp_path / "elsewhere" / "movie.mkv"
    library_root.mkdir()
    outside.parent.mkdir()
    outside.write_bytes(b"movie")

    with pytest.raises(RuntimeError, match="outside configured library root"):
        hotcache.safe_relative_path(outside, library_root)


def test_active_paths_preserve_logical_path(hotcache, monkeypatch, tmp_path):
    logical = tmp_path / "library" / "movie.mkv"
    cached = tmp_path / "cache" / "movie.mkv"
    logical.parent.mkdir()
    cached.parent.mkdir()
    cached.write_bytes(b"movie")
    logical.symlink_to(cached)

    monkeypatch.setattr(
        hotcache,
        "jellyfin_get",
        lambda *_args, **_kwargs: [{"NowPlayingItem": {"Path": str(logical)}}],
    )

    assert hotcache.get_active_paths({}) == {str(hotcache.logical_path(logical))}
