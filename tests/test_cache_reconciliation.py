from __future__ import annotations

import copy
from pathlib import Path


def _candidate(hotcache, base_config, source: Path):
    library = hotcache.build_libraries(base_config)[0]
    return hotcache.Candidate(
        item_id="item-1",
        user_id="user-1",
        title="Example Movie",
        source_file=source,
        library=library,
        plays=4,
        last_played="2026-09-27T08:00:00-04:00",
        size_bytes=6,
        reason="4 lifetime plays; last played within 30 days",
    )


def _managed_state(hotcache, base_config):
    config = copy.deepcopy(base_config)
    library_root = Path(config["libraries"]["movies"][0]["source"])
    cache_root = Path(config["cache"]["root"])

    source = library_root / "Example Movie.mkv"
    cache_file = cache_root / "movies" / "Example Movie.mkv"
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    cache_file.write_bytes(b"cached")

    preserved = source.with_name(source.name + ".cached")
    preserved.write_bytes(b"cached")
    source.symlink_to(cache_file)

    candidate = _candidate(hotcache, config, source)
    manifest = {
        "version": 1,
        "items": {
            str(source): {
                "title": "Old title",
                "item_id": "old-item",
                "library": "Movies",
                "kind": "movie",
                "media_group": "video",
                "source": str(source),
                "cache": str(cache_file),
                "preserved_original": str(preserved),
                "size_bytes": 1,
                "promoted_at": "2026-09-01T00:00:00+00:00",
                "last_seen_hot": "2026-09-01T00:00:00+00:00",
                "last_played": "2026-09-01T00:00:00+00:00",
            }
        },
    }
    return config, candidate, cache_file, preserved, manifest


def test_reconcile_managed_candidate_refreshes_healthy_cached_item(
    hotcache, base_config
):
    config, candidate, cache_file, preserved, manifest = _managed_state(
        hotcache, base_config
    )
    old_promoted_at = manifest["items"][str(candidate.source_file)]["promoted_at"]

    state, reason = hotcache.reconcile_managed_candidate(
        candidate, cache_file, manifest, config
    )

    assert state == "cached"
    assert "already cached; managed state verified" in reason
    entry = manifest["items"][str(candidate.source_file)]
    assert entry["title"] == "Example Movie"
    assert entry["item_id"] == "item-1"
    assert entry["last_played"] == candidate.last_played
    assert entry["plays_last_seen"] == 4
    assert entry["size_bytes"] == len(b"cached")
    assert entry["promoted_at"] == old_promoted_at
    assert entry["preserved_original"] == str(preserved)
    assert entry["last_seen_hot"] != "2026-09-01T00:00:00+00:00"


def test_reconcile_managed_candidate_rejects_wrong_symlink_target(
    hotcache, base_config, tmp_path
):
    config, candidate, cache_file, _preserved, manifest = _managed_state(
        hotcache, base_config
    )
    source = candidate.source_file
    source.unlink()
    wrong = tmp_path / "wrong-cache.mkv"
    wrong.write_bytes(b"cached")
    source.symlink_to(wrong)

    state, reason = hotcache.reconcile_managed_candidate(
        candidate, cache_file, manifest, config
    )

    assert state == "inconsistent"
    assert "source symlink targets" in reason


def test_reconcile_managed_candidate_rejects_manifest_cache_path_drift(
    hotcache, base_config, tmp_path
):
    config, candidate, cache_file, _preserved, manifest = _managed_state(
        hotcache, base_config
    )
    manifest["items"][str(candidate.source_file)]["cache"] = str(
        tmp_path / "different-cache.mkv"
    )

    state, reason = hotcache.reconcile_managed_candidate(
        candidate, cache_file, manifest, config
    )

    assert state == "inconsistent"
    assert "does not match configured cache path" in reason


def test_reconcile_managed_candidate_does_not_adopt_untracked_state(
    hotcache, base_config
):
    config, candidate, cache_file, _preserved, _manifest = _managed_state(
        hotcache, base_config
    )

    state, reason = hotcache.reconcile_managed_candidate(
        candidate, cache_file, {"version": 1, "items": {}}, config
    )

    assert state == "unmanaged"
    assert reason == ""
