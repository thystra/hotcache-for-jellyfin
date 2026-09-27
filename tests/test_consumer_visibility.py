import sqlite3
from pathlib import Path

import pytest


def _make_fake_jellyfin_process(
    proc_root: Path,
    pid: int,
    process_root: Path,
) -> None:
    proc_dir = proc_root / str(pid)
    proc_dir.mkdir(parents=True)
    (proc_dir / "comm").write_text("jellyfin\n", encoding="utf-8")
    (proc_dir / "root").symlink_to(process_root, target_is_directory=True)


def test_cache_visibility_detects_bare_metal(
    hotcache,
    base_config,
    tmp_path,
):
    proc_root = tmp_path / "proc"
    proc_root.mkdir()
    _make_fake_jellyfin_process(proc_root, 101, Path("/"))

    mode, detail = hotcache.verify_jellyfin_cache_visibility(
        base_config,
        Path(base_config["cache"]["root"]),
        proc_root=proc_root,
    )

    assert mode == "bare-metal"
    assert "PID(s) 101" in detail


def test_cache_visibility_accepts_container_identity_mount(
    hotcache,
    base_config,
    tmp_path,
):
    proc_root = tmp_path / "proc"
    proc_root.mkdir()
    container_root = tmp_path / "container-root"
    container_root.mkdir()
    _make_fake_jellyfin_process(proc_root, 202, container_root)

    cache_root = Path(base_config["cache"]["root"])
    visible = container_root / str(cache_root).lstrip("/")
    visible.parent.mkdir(parents=True)
    visible.symlink_to(cache_root, target_is_directory=True)

    mode, detail = hotcache.verify_jellyfin_cache_visibility(
        base_config,
        cache_root,
        proc_root=proc_root,
    )

    assert mode == "containerized"
    assert "PID(s) 202" in detail


def test_cache_visibility_rejects_container_without_cache_mount(
    hotcache,
    base_config,
    tmp_path,
):
    proc_root = tmp_path / "proc"
    proc_root.mkdir()
    container_root = tmp_path / "container-root"
    container_root.mkdir()
    _make_fake_jellyfin_process(proc_root, 303, container_root)

    with pytest.raises(RuntimeError, match="Docker/Compose"):
        hotcache.verify_jellyfin_cache_visibility(
            base_config,
            Path(base_config["cache"]["root"]),
            proc_root=proc_root,
        )


def test_cache_visibility_can_be_explicitly_disabled(
    hotcache,
    base_config,
):
    base_config["jellyfin"]["verify_cache_visibility"] = False

    mode, detail = hotcache.verify_jellyfin_cache_visibility(
        base_config,
        Path(base_config["cache"]["root"]),
    )

    assert mode == "unchecked"
    assert "verify_cache_visibility=false" in detail


def test_real_promotion_guard_fails_closed(
    hotcache,
    base_config,
    monkeypatch,
):
    def fail_visibility(*_args, **_kwargs):
        raise RuntimeError("container cannot see cache root; update Docker/Compose")

    monkeypatch.setattr(
        hotcache,
        "verify_jellyfin_cache_visibility",
        fail_visibility,
    )

    with pytest.raises(RuntimeError, match="Refusing to promote files"):
        hotcache.guard_promotion_cache_visibility(
            base_config,
            Path(base_config["cache"]["root"]),
            dry_run=False,
        )


def test_dry_run_guard_warns_without_failing(
    hotcache,
    base_config,
    monkeypatch,
):
    def fail_visibility(*_args, **_kwargs):
        raise RuntimeError("container cannot see cache root; update Docker/Compose")

    monkeypatch.setattr(
        hotcache,
        "verify_jellyfin_cache_visibility",
        fail_visibility,
    )

    warning = hotcache.guard_promotion_cache_visibility(
        base_config,
        Path(base_config["cache"]["root"]),
        dry_run=True,
    )

    assert warning is not None
    assert "Real promotion will be refused" in warning


def test_preflight_reports_cache_visibility_failure(
    hotcache,
    base_config,
    monkeypatch,
    capsys,
):
    db_path = Path(base_config["playback_reporting"]["database_path"])
    con = sqlite3.connect(db_path)
    con.execute("CREATE TABLE PlaybackActivity (ItemId TEXT, DateCreated TEXT)")
    con.commit()
    con.close()

    monkeypatch.setattr(hotcache, "jellyfin_get", lambda *_args, **_kwargs: [])

    def fail_visibility(*_args, **_kwargs):
        raise RuntimeError(
            "containerized Jellyfin cannot see cache root; update Docker/Compose"
        )

    monkeypatch.setattr(
        hotcache,
        "verify_jellyfin_cache_visibility",
        fail_visibility,
    )

    rc = hotcache.run_preflight(base_config)
    output = capsys.readouterr().out

    assert rc == 1
    assert "FAIL  Jellyfin cache visibility" in output
    assert "Docker/Compose" in output
