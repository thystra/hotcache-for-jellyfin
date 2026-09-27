from __future__ import annotations

from pathlib import Path


def _managed_fixture(hotcache, base_config):
    library = hotcache.build_libraries(base_config)[0]
    source = library.source / "Example Movie.mkv"
    cache = Path(base_config["cache"]["root"]) / "movies" / "Example Movie.mkv"
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_bytes(b"abcdef")

    preserved = source.with_name(source.name + ".cached")
    preserved.write_bytes(b"abcdef")
    source.symlink_to(cache)

    manifest = {
        "version": 1,
        "items": {
            str(source): {
                "title": "Example Movie",
                "item_id": "item-1",
                "library": library.name,
                "kind": library.kind,
                "media_group": "video",
                "source": str(source),
                "cache": str(cache),
                "preserved_original": str(preserved),
                "size_bytes": 1,
            }
        },
    }
    return source, cache, preserved, manifest


def test_managed_cache_state_summary_counts_valid_promoted_state(
    hotcache, base_config
):
    _source, _cache, _preserved, manifest = _managed_fixture(
        hotcache, base_config
    )

    count, size = hotcache.managed_cache_state_summary(base_config, manifest)

    assert count == 1
    assert size == 6


def test_managed_cache_state_summary_excludes_broken_state(
    hotcache, base_config
):
    source, _cache, _preserved, manifest = _managed_fixture(
        hotcache, base_config
    )
    source.unlink()
    source.write_bytes(b"not-a-symlink")

    count, size = hotcache.managed_cache_state_summary(base_config, manifest)

    assert count == 0
    assert size == 0


def test_report_distinguishes_state_actions_and_candidates(
    hotcache, base_config
):
    report = hotcache.RunReport(
        started_at="2026-09-27T09:00:00-04:00",
        dry_run=True,
        cache_limit=190 * 1024**3,
        cache_used_before=10 * 1024**3,
        cache_used_after=10 * 1024**3,
        projected_cache_used=10 * 1024**3,
        projected_video_used=10 * 1024**3,
        promoted_state_count=3,
        promoted_state_bytes=10 * 1024**3,
        hot_already_promoted_count=3,
    )
    report.promoted.append(
        hotcache.Action(
            status="DRY-RUN PROMOTE",
            title="New Movie",
            source="/library/New Movie.mkv",
            cache="/cache/New Movie.mkv",
            size_bytes=1,
            reason="eligible",
        )
    )
    report.candidates.append(
        hotcache.Action(
            status="CANDIDATE",
            title="New Movie",
            source="/library/New Movie.mkv",
            cache="/cache/New Movie.mkv",
            size_bytes=1,
            reason="eligible",
        )
    )

    text = hotcache.build_report_text(base_config, report)

    assert "Promoted files:       3" in text
    assert "Hot already promoted: 3" in text
    assert "Uncached candidates:  1" in text
    assert "Promoted this run:" in text
    assert "Candidates:" in text
    assert "CACHED HOT" not in text
