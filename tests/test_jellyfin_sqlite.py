from __future__ import annotations

import copy
import datetime as dt
import os
import sqlite3
from pathlib import Path

import pytest


def _create_synthetic_jellyfin_db(db_path: Path, item_rows, userdata_rows) -> None:
    con = sqlite3.connect(db_path)
    try:
        con.execute(
            '''
            CREATE TABLE "BaseItems" (
                "Id" TEXT PRIMARY KEY,
                "Path" TEXT,
                "Name" TEXT
            )
            '''
        )
        con.execute(
            '''
            CREATE TABLE "UserData" (
                "Id" INTEGER PRIMARY KEY,
                "ItemId" TEXT NOT NULL,
                "UserId" TEXT NOT NULL,
                "CustomDataKey" TEXT,
                "PlayCount" INTEGER NOT NULL,
                "LastPlayedDate" TEXT
            )
            '''
        )
        con.executemany(
            'INSERT INTO "BaseItems" ("Id", "Path", "Name") VALUES (?, ?, ?)',
            item_rows,
        )
        con.executemany(
            '''
            INSERT INTO "UserData"
                ("ItemId", "UserId", "CustomDataKey", "PlayCount", "LastPlayedDate")
            VALUES (?, ?, ?, ?, ?)
            ''',
            userdata_rows,
        )
        con.commit()
    finally:
        con.close()


def test_core_sqlite_userdata_matches_postgresql_semantics(
    hotcache,
    base_config,
    monkeypatch,
    tmp_path,
):
    library_root = tmp_path / "sqlite-library"
    library_root.mkdir()
    item_a = library_root / "item-a.mkv"
    item_b = library_root / "item-b.mkv"
    item_a.write_bytes(b"A")
    item_b.write_bytes(b"B")

    now = dt.datetime.now(dt.timezone.utc).isoformat()
    db_path = tmp_path / "jellyfin.db"
    _create_synthetic_jellyfin_db(
        db_path,
        [
            ("item-a", str(item_a), "Item A"),
            ("item-b", str(item_b), "Item B"),
        ],
        [
            ("item-a", "user-1", "key-a", 1, now),
            ("item-a", "user-1", "key-b", 1, now),
            ("item-a", "user-1", "key-c", 1, now),
            ("item-a", "user-2", "key-a", 2, now),
            ("item-b", "user-1", "key-a", 1, now),
            ("item-b", "user-1", "key-b", 1, now),
            ("item-b", "user-1", "key-c", 1, now),
        ],
    )

    cfg = copy.deepcopy(base_config)
    cfg["libraries"]["movies"][0]["source"] = str(library_root)
    cfg["cache"]["promote_after_plays_movies"] = 2
    cfg["playback_reporting"] = {
        "source": "jellyfin_sqlite",
        "database_path": str(db_path),
    }

    def unexpected_api_lookup(*_args, **_kwargs):
        raise AssertionError("core SQLite path resolution must not use /Items")

    monkeypatch.setattr(hotcache, "get_item_from_jellyfin", unexpected_api_lookup)
    libraries = hotcache.build_libraries(cfg)
    candidates = hotcache.query_jellyfin_sqlite(cfg, libraries, {".mkv"})

    assert len(candidates) == 1
    assert candidates[0].item_id == "item-a"
    assert candidates[0].plays == 3
    assert candidates[0].title == "Item A"
    assert "lifetime plays" in candidates[0].reason


def test_core_sqlite_rejects_missing_required_schema(hotcache, tmp_path):
    db_path = tmp_path / "broken-jellyfin.db"
    con = sqlite3.connect(db_path)
    try:
        con.execute('CREATE TABLE "UserData" ("ItemId" TEXT)')
        con.execute('CREATE TABLE "BaseItems" ("Id" TEXT, "Path" TEXT)')
        con.commit()
    finally:
        con.close()

    with pytest.raises(RuntimeError, match="UserData is missing columns"):
        hotcache.inspect_jellyfin_sqlite_schema(db_path)


def test_official_jellyfin_container_schema(hotcache):
    db_value = os.environ.get("HOTCACHE_TEST_JELLYFIN_DB")
    if not db_value:
        pytest.skip(
            "set HOTCACHE_TEST_JELLYFIN_DB to a jellyfin.db initialized by the official container"
        )

    schema = hotcache.inspect_jellyfin_sqlite_schema(Path(db_value))
    assert {"itemid", "userid", "playcount", "lastplayeddate"}.issubset(
        set(schema["userdata_columns"])
    )
    assert {"id", "path"}.issubset(set(schema["baseitems_columns"]))
