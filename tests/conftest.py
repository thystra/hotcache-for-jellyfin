from __future__ import annotations

import importlib.machinery
import importlib.util
import sys
from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def hotcache():
    root = Path(__file__).resolve().parents[1]
    script = root / "jellyfin-hotcache"
    loader = importlib.machinery.SourceFileLoader("jellyfin_hotcache", str(script))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    sys.modules[loader.name] = module
    loader.exec_module(module)
    return module


@pytest.fixture
def base_config(tmp_path):
    library = tmp_path / "library"
    cache = tmp_path / "cache"
    library.mkdir()
    cache.mkdir()
    return {
        "hotcache": {
            "enabled": True,
            "lock_file": str(tmp_path / "hotcache.lock"),
            "maintenance": {
                "restore_all_files_and_disable": False,
                "skip_active_streams": True,
                "remove_empty_cache_dirs": True,
            },
        },
        "jellyfin": {
            "url": "http://127.0.0.1:8096",
            "api_key": "test-key",
        },
        "playback_reporting": {
            "source": "sqlite",
            "database_path": str(tmp_path / "playback.db"),
        },
        "cache": {
            "root": str(cache),
            "max_cache_size": "1GB",
            "minimum_free_cache_space": "0B",
            "dry_run": True,
            "enable_promotion": True,
            "enable_demotion": False,
            "promotion_mode": "main_file_only",
            "allow_directory_promotion": False,
            "max_single_file_promotion_size": "500MB",
            "max_single_file_percent_of_cache": 75,
            "hot_window_days": 30,
            "promote_after_plays_movies": 2,
            "promote_after_plays_kids_movies": 1,
            "promote_after_plays_shows": 1,
            "promote_after_plays_kids_tv": 1,
            "promote_after_plays_music": 5,
            "demote_after_days_unwatched": 90,
            "verify_copy": True,
            "use_absolute_symlinks": True,
            "skip_if_active_stream": True,
            "preserve_original_on_source": True,
            "preserved_original_suffix": ".cached",
            "keep_original_until_verified": True,
            "music": {
                "max_cache_size": "100MB",
                "reserve_for_music": "100MB",
            },
        },
        "media_selection": {
            "video_extensions": [".mkv"],
            "audio_extensions": [".flac"],
            "ignore_dirs": [],
        },
        "libraries": {
            "movies": [
                {
                    "name": "Movies",
                    "source": str(library),
                    "cache_subdir": "movies",
                }
            ],
            "shows": [],
            "music": [],
        },
        "reporting": {"enabled": False},
    }
