from __future__ import annotations

import copy
import subprocess
from types import SimpleNamespace


GIB = 1024 ** 3


def test_inspect_filesystem_reads_zfs_quota_state(hotcache, monkeypatch, tmp_path):
    cache = tmp_path / "cache"
    cache.mkdir()

    monkeypatch.setattr(
        hotcache.shutil,
        "disk_usage",
        lambda _path: SimpleNamespace(free=120 * GIB),
    )

    def fake_run(command, **_kwargs):
        if command[0] == "findmnt":
            return subprocess.CompletedProcess(
                command,
                0,
                stdout=f"zfs CACHE/jellyfin-cache {cache}\n",
                stderr="",
            )
        if command[:2] == ["zfs", "get"]:
            return subprocess.CompletedProcess(
                command,
                0,
                stdout=(
                    "quota\tnone\n"
                    f"refquota\t{200 * GIB}\n"
                    f"used\t{67 * GIB}\n"
                    f"referenced\t{66 * GIB}\n"
                    f"available\t{134 * GIB}\n"
                ),
                stderr="",
            )
        if command[:2] == ["zpool", "get"]:
            return subprocess.CompletedProcess(
                command,
                0,
                stdout=f"{531 * GIB}\n",
                stderr="",
            )
        raise AssertionError(command)

    monkeypatch.setattr(hotcache.subprocess, "run", fake_run)

    info = hotcache.inspect_filesystem(cache)

    assert info.fs_type == "zfs"
    assert info.dataset == "CACHE/jellyfin-cache"
    assert info.pool == "CACHE"
    assert info.zfs_details_available is True
    assert info.zfs_quota is None
    assert info.zfs_refquota == 200 * GIB
    assert info.zfs_used == 67 * GIB
    assert info.zfs_referenced == 66 * GIB
    assert info.zfs_available == 134 * GIB
    assert info.available == 134 * GIB
    assert info.zpool_free == 531 * GIB


def test_inspect_filesystem_non_zfs_falls_back_to_disk_usage(
    hotcache,
    monkeypatch,
    tmp_path,
):
    cache = tmp_path / "cache"
    cache.mkdir()

    monkeypatch.setattr(
        hotcache.shutil,
        "disk_usage",
        lambda _path: SimpleNamespace(free=42 * GIB),
    )

    def fake_run(command, **_kwargs):
        assert command[0] == "findmnt"
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=f"ext4 /dev/nvme0n1p2 {cache}\n",
            stderr="",
        )

    monkeypatch.setattr(hotcache.subprocess, "run", fake_run)

    info = hotcache.inspect_filesystem(cache)

    assert info.fs_type == "ext4"
    assert info.source == "/dev/nvme0n1p2"
    assert info.available == 42 * GIB
    assert info.zfs_details_available is False


def test_report_shows_zfs_capacity_and_effective_remaining(
    hotcache,
    base_config,
):
    config = copy.deepcopy(base_config)
    config["cache"]["max_cache_size"] = "190GiB"
    config["cache"]["minimum_free_cache_space"] = "5GiB"
    config["cache"]["music"]["max_cache_size"] = "5GiB"
    config["cache"]["music"]["reserve_for_music"] = "5GiB"

    filesystem = hotcache.FilesystemInfo(
        fs_type="zfs",
        source="CACHE/jellyfin-cache",
        mountpoint="/srv/jellyfin-cache",
        available=134 * GIB,
        dataset="CACHE/jellyfin-cache",
        pool="CACHE",
        zfs_details_available=True,
        zfs_quota=None,
        zfs_refquota=200 * GIB,
        zfs_used=67 * GIB,
        zfs_referenced=66 * GIB,
        zfs_available=134 * GIB,
        zpool_free=531 * GIB,
    )
    report = hotcache.RunReport(
        started_at="2026-09-26T22:00:00-04:00",
        dry_run=True,
        cache_used_before=70 * GIB,
        cache_used_after=70 * GIB,
        cache_limit=190 * GIB,
        filesystem_free=134 * GIB,
        filesystem_info=filesystem,
        projected_cache_used=100 * GIB,
        projected_music_used=3 * GIB,
        projected_video_used=97 * GIB,
    )

    text = hotcache.build_report_text(config, report)

    assert "Filesystem:" in text
    assert "Type:                 ZFS" in text
    assert "Dataset:              CACHE/jellyfin-cache" in text
    assert "Pool:                 CACHE" in text
    assert "Pool free:            531.0 GiB" in text
    assert "Dataset quota:        none" in text
    assert "Dataset refquota:     200.0 GiB" in text
    assert "Dataset used:         67.0 GiB" in text
    assert "Dataset referenced:   66.0 GiB" in text
    assert "Dataset available:    134.0 GiB" in text
    assert "Remaining by policy:  90.0 GiB" in text
    assert "Filesystem available: 134.0 GiB" in text
    assert "Projected growth:     30.0 GiB" in text
    assert "Effective remaining:  90.0 GiB" in text


def test_effective_remaining_is_limited_by_filesystem_headroom(
    hotcache,
    base_config,
):
    config = copy.deepcopy(base_config)
    config["cache"]["max_cache_size"] = "190GiB"
    config["cache"]["minimum_free_cache_space"] = "5GiB"

    report = hotcache.RunReport(
        started_at="2026-09-26T22:00:00-04:00",
        dry_run=True,
        cache_used_after=70 * GIB,
        cache_limit=190 * GIB,
        filesystem_free=40 * GIB,
        projected_cache_used=100 * GIB,
    )

    policy, available, reserve, growth, effective = hotcache.calculate_capacity_remaining(
        config,
        report,
    )

    assert policy == 90 * GIB
    assert available == 40 * GIB
    assert reserve == 5 * GIB
    assert growth == 30 * GIB
    assert effective == 5 * GIB
