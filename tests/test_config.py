import copy

import pytest


def test_api_key_can_come_from_environment(hotcache, base_config, monkeypatch):
    cfg = copy.deepcopy(base_config)
    cfg["jellyfin"]["api_key"] = ""
    cfg["jellyfin"]["api_key_env"] = "JELLYFIN_API_KEY"
    monkeypatch.setenv("JELLYFIN_API_KEY", "from-env")
    assert hotcache.get_jellyfin_api_key(cfg) == "from-env"


@pytest.mark.parametrize(
    "key,value,match",
    [
        ("allow_directory_promotion", True, "file-first"),
        ("promotion_mode", "directory", "main_file_only"),
        ("preserve_original_on_source", False, "preserving the NAS original"),
        ("use_absolute_symlinks", False, "absolute_symlinks"),
    ],
)
def test_validate_config_rejects_unsafe_modes(hotcache, base_config, key, value, match):
    cfg = copy.deepcopy(base_config)
    cfg["cache"][key] = value
    with pytest.raises(RuntimeError, match=match):
        hotcache.validate_config(cfg)
