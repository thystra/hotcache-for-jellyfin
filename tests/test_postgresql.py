from __future__ import annotations

import copy
import os
from pathlib import Path

import pytest


def test_userdata_custom_keys_are_not_counted_as_separate_plays(hotcache, base_config, tmp_path):
    dsn = os.environ.get("HOTCACHE_TEST_PG_DSN")
    if not dsn:
        pytest.skip("set HOTCACHE_TEST_PG_DSN to run PostgreSQL integration test")

    psycopg = pytest.importorskip("psycopg")

    library_root = tmp_path / "pg-library"
    library_root.mkdir()
    item_a = library_root / "item-a.mkv"
    item_b = library_root / "item-b.mkv"
    item_a.write_bytes(b"A")
    item_b.write_bytes(b"B")

    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute('DROP TABLE IF EXISTS public."UserData"')
            cur.execute('DROP TABLE IF EXISTS public."BaseItems"')
            cur.execute('''
                CREATE TABLE public."BaseItems" (
                    "Id" text PRIMARY KEY,
                    "Path" text,
                    "Name" text
                )
            ''')
            cur.execute('''
                CREATE TABLE public."UserData" (
                    "ItemId" text NOT NULL,
                    "UserId" text NOT NULL,
                    "CustomDataKey" text NOT NULL,
                    "PlayCount" integer NOT NULL,
                    "LastPlayedDate" timestamptz NOT NULL
                )
            ''')
            cur.executemany(
                'INSERT INTO public."BaseItems" ("Id", "Path", "Name") VALUES (%s, %s, %s)',
                [
                    ("item-a", str(item_a), "Item A"),
                    ("item-b", str(item_b), "Item B"),
                ],
            )
            rows = [
                ("item-a", "user-1", "key-a", 1),
                ("item-a", "user-1", "key-b", 1),
                ("item-a", "user-1", "key-c", 1),
                ("item-a", "user-2", "key-a", 2),
                ("item-b", "user-1", "key-a", 1),
                ("item-b", "user-1", "key-b", 1),
                ("item-b", "user-1", "key-c", 1),
            ]
            cur.executemany(
                '''INSERT INTO public."UserData"
                   ("ItemId", "UserId", "CustomDataKey", "PlayCount", "LastPlayedDate")
                   VALUES (%s, %s, %s, %s, now())''',
                rows,
            )
        conn.commit()

    cfg = copy.deepcopy(base_config)
    cfg["libraries"]["movies"][0]["source"] = str(library_root)
    cfg["cache"]["promote_after_plays_movies"] = 2
    cfg["playback_reporting"] = {
        "source": "postgresql",
        "postgresql": {"dsn": dsn},
    }

    libraries = hotcache.build_libraries(cfg)
    candidates = hotcache.query_playback_reporting_postgresql(cfg, libraries, {".mkv"})

    assert len(candidates) == 1
    assert candidates[0].item_id == "item-a"
    assert candidates[0].plays == 3
