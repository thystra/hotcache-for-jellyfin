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


def test_report_uses_mutually_exclusive_final_states(hotcache, base_config):
    report = hotcache.RunReport(
        started_at="2026-09-29T06:33:53-04:00",
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
            title="Promoted Movie",
            source="/library/Promoted Movie.mkv",
            cache="/cache/Promoted Movie.mkv",
            size_bytes=1,
            reason="eligible",
        )
    )
    report.waiting_for_space.append(
        hotcache.Action(
            status="WAITING FOR SPACE",
            title="Waiting Movie",
            source="/library/Waiting Movie.mkv",
            cache="/cache/Waiting Movie.mkv",
            size_bytes=1,
            reason="video cache limit exceeded",
        )
    )
    report.deferred.append(
        hotcache.Action(
            status="DEFERRED",
            title="Active Movie",
            source="/library/Active Movie.mkv",
            cache="/cache/Active Movie.mkv",
            size_bytes=1,
            reason="file is currently being streamed",
        )
    )
    report.blocked_by_policy.append(
        hotcache.Action(
            status="BLOCKED BY POLICY",
            title="Oversized Movie",
            source="/library/Oversized Movie.mkv",
            cache="/cache/Oversized Movie.mkv",
            size_bytes=1,
            reason="file exceeds max_single_file_promotion_size",
        )
    )
    report.attention_required.append(
        hotcache.Action(
            status="ATTENTION REQUIRED",
            title="Inconsistent Movie",
            source="/library/Inconsistent Movie.mkv",
            cache="/cache/Inconsistent Movie.mkv",
            size_bytes=1,
            reason="managed cache state is inconsistent",
        )
    )

    text = hotcache.build_report_text(base_config, report)

    assert f"Version: {hotcache.HOTCACHE_VERSION}" in text
    assert "Promoted files:       3" in text
    assert "Hot already promoted: 3" in text
    assert "Pending candidates:   2" in text
    assert "Waiting for space:    1" in text
    assert "Deferred:             1" in text
    assert "Blocked by policy:    1" in text
    assert "Attention required:   1" in text
    assert "Promoted this run:" in text
    assert "Waiting for space:" in text
    assert "Deferred:" in text
    assert "Blocked by policy:" in text
    assert "Attention required:" in text
    assert "Candidates:" not in text
    assert "Uncached candidates:" not in text
    assert text.count("Promoted Movie") == 3  # title, source, cache in one final-state section


def test_promotion_outcome_classification(hotcache):
    assert hotcache.classify_promotion_outcome(
        "file is currently being streamed"
    ) == "deferred"
    assert hotcache.classify_promotion_outcome(
        "video cache limit exceeded after reserving music space"
    ) == "waiting_for_space"
    assert hotcache.classify_promotion_outcome(
        "filesystem free-space floor exceeded: free 1 GiB"
    ) == "waiting_for_space"
    assert hotcache.classify_promotion_outcome(
        "file exceeds max_single_file_promotion_size: 40 GiB"
    ) == "blocked_by_policy"
    assert hotcache.classify_promotion_outcome(
        "source file does not exist"
    ) == "attention_required"
