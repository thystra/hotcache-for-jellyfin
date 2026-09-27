from __future__ import annotations

import copy

import pytest


def test_environment_file_loads_missing_variable(hotcache, monkeypatch, tmp_path):
    env_file = tmp_path / "environment"
    env_file.write_text("JELLYFIN_API_KEY=from-file\n", encoding="utf-8")
    monkeypatch.delenv("JELLYFIN_API_KEY", raising=False)

    assert hotcache.load_environment_file(env_file) == 1
    assert hotcache.os.environ["JELLYFIN_API_KEY"] == "from-file"


def test_process_environment_takes_precedence(hotcache, monkeypatch, tmp_path):
    env_file = tmp_path / "environment"
    env_file.write_text("JELLYFIN_API_KEY=from-file\n", encoding="utf-8")
    monkeypatch.setenv("JELLYFIN_API_KEY", "from-process")

    assert hotcache.load_environment_file(env_file) == 0
    assert hotcache.os.environ["JELLYFIN_API_KEY"] == "from-process"


def test_environment_file_supports_comments_and_quotes(hotcache, monkeypatch, tmp_path):
    env_file = tmp_path / "environment"
    env_file.write_text(
        "# secrets\n; alternate comment\nJELLYFIN_API_KEY='quoted value'\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("JELLYFIN_API_KEY", raising=False)

    hotcache.load_environment_file(env_file)
    assert hotcache.os.environ["JELLYFIN_API_KEY"] == "quoted value"


def test_environment_file_rejects_malformed_line(hotcache, tmp_path):
    env_file = tmp_path / "environment"
    env_file.write_text("NOT_AN_ASSIGNMENT\n", encoding="utf-8")

    with pytest.raises(RuntimeError, match="expected NAME=value"):
        hotcache.load_environment_file(env_file)


def test_human_size_uses_explicit_binary_units(hotcache):
    assert hotcache.human_size(hotcache.parse_size("190GiB")) == "190.0 GiB"
    assert hotcache.human_size(hotcache.parse_size("1GiB")) == "1.0 GiB"


def test_report_shows_group_usage_and_remaining(hotcache, base_config):
    config = copy.deepcopy(base_config)
    config["cache"]["max_cache_size"] = "190GiB"
    config["cache"]["music"]["max_cache_size"] = "5GiB"
    config["cache"]["music"]["reserve_for_music"] = "5GiB"

    report = hotcache.RunReport(
        started_at="2026-09-26T20:53:40-04:00",
        dry_run=True,
        cache_used_before=hotcache.parse_size("70GiB"),
        cache_used_after=hotcache.parse_size("70GiB"),
        cache_limit=hotcache.parse_size("190GiB"),
        filesystem_free=hotcache.parse_size("134GiB"),
        projected_cache_used=hotcache.parse_size("100GiB"),
        projected_music_used=hotcache.parse_size("3GiB"),
        projected_video_used=hotcache.parse_size("97GiB"),
    )

    text = hotcache.build_report_text(config, report)

    assert "Configured limit:   190.0 GiB" in text
    assert "Projected used:     100.0 GiB" in text
    assert "Remaining allowed:  90.0 GiB" in text
    assert "Music limit:        5.0 GiB" in text
    assert "Music projected:    3.0 GiB" in text
    assert "Music remaining:    2.0 GiB" in text
    assert "Video limit:        185.0 GiB" in text
    assert "Video projected:    97.0 GiB" in text
    assert "Video remaining:    88.0 GiB" in text
    assert "Filesystem free:    134.0 GiB" in text
