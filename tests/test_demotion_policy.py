from __future__ import annotations

import copy
import datetime as dt

import pytest


def test_demote_after_days_cold_defaults_to_14(hotcache, base_config):
    config = copy.deepcopy(base_config)
    config["cache"].pop("demote_after_days_unwatched", None)
    config["cache"].pop("demote_after_days_cold", None)

    assert hotcache.get_demote_after_days_cold(config) == 14


def test_demote_after_days_cold_wins_over_legacy_alias(hotcache, base_config):
    config = copy.deepcopy(base_config)
    config["cache"]["demote_after_days_unwatched"] = 90
    config["cache"]["demote_after_days_cold"] = 14

    assert hotcache.get_demote_after_days_cold(config) == 14


def test_legacy_demote_after_days_unwatched_is_still_supported(hotcache, base_config):
    config = copy.deepcopy(base_config)
    config["cache"].pop("demote_after_days_cold", None)
    config["cache"]["demote_after_days_unwatched"] = 30

    assert hotcache.get_demote_after_days_cold(config) == 30


def test_negative_cold_grace_is_rejected(hotcache, base_config):
    config = copy.deepcopy(base_config)
    config["cache"]["demote_after_days_cold"] = -1

    with pytest.raises(RuntimeError, match="non-negative integer"):
        hotcache.get_demote_after_days_cold(config)


def _manifest_item(tmp_path, *, age_days: int):
    source = tmp_path / "library" / "cold.mkv"
    cache = tmp_path / "cache" / "movies" / "cold.mkv"
    when = (
        dt.datetime.now(dt.timezone.utc).astimezone()
        - dt.timedelta(days=age_days)
    ).isoformat()
    return source, {
        "version": 1,
        "items": {
            str(source): {
                "title": "Cold item",
                "cache": str(cache),
                "size_bytes": 1234,
                "promoted_at": when,
                "last_seen_hot": when,
            }
        },
    }


def test_dry_run_demotes_after_cold_grace(hotcache, base_config, tmp_path):
    config = copy.deepcopy(base_config)
    config["cache"]["enable_demotion"] = True
    config["cache"]["demote_after_days_cold"] = 14
    source, manifest = _manifest_item(tmp_path, age_days=15)

    actions = hotcache.demote_cold_files(config, manifest, set(), True)

    assert len(actions) == 1
    assert actions[0].source == str(source)
    assert actions[0].status == "DRY-RUN DEMOTE"
    assert actions[0].reason == "not hot for 14 days"


def test_dry_run_keeps_item_inside_cold_grace(hotcache, base_config, tmp_path):
    config = copy.deepcopy(base_config)
    config["cache"]["enable_demotion"] = True
    config["cache"]["demote_after_days_cold"] = 14
    _source, manifest = _manifest_item(tmp_path, age_days=13)

    assert hotcache.demote_cold_files(config, manifest, set(), True) == []


def test_dry_run_demotion_updates_projected_usage(hotcache, base_config, tmp_path):
    config = copy.deepcopy(base_config)
    libraries = hotcache.build_libraries(config)
    source = tmp_path / "library" / "cold.mkv"
    action = hotcache.Action(
        status="DRY-RUN DEMOTE",
        title="Cold item",
        source=str(source),
        cache=str(tmp_path / "cache" / "movies" / "cold.mkv"),
        size_bytes=200,
    )
    report = hotcache.RunReport(
        started_at="2026-09-27T00:00:00-04:00",
        dry_run=True,
        projected_cache_used=1000,
        projected_music_used=100,
        projected_video_used=900,
    )

    hotcache.apply_cache_removal_projection(report, [action], libraries)

    assert report.projected_cache_used == 800
    assert report.projected_music_used == 100
    assert report.projected_video_used == 700


def test_report_shows_demotion_policy(hotcache, base_config):
    config = copy.deepcopy(base_config)
    config["cache"]["enable_demotion"] = True
    config["cache"]["demote_after_days_cold"] = 14
    report = hotcache.RunReport(
        started_at="2026-09-27T00:00:00-04:00",
        dry_run=True,
        cache_limit=hotcache.parse_size("1GiB"),
        filesystem_free=hotcache.parse_size("1GiB"),
    )

    text = hotcache.build_report_text(config, report)

    assert "Demotion enabled:     True" in text
    assert "Demote after cold:    14 days" in text
