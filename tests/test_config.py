"""Tests for config read/write/merge."""
import pytest
from pathlib import Path

from git_summarizer.config import (
    load_config, save_config, set_key, unset_key, build_default_map,
    load_repo_config, merge_configs, REPO_CONFIG_NAME,
)


@pytest.fixture(autouse=True)
def isolated_config(tmp_path, monkeypatch):
    """Redirect CONFIG_PATH to a temp dir so tests don't touch ~/.config."""
    import git_summarizer.config as cfg_module
    fake_path = tmp_path / "config.toml"
    monkeypatch.setattr(cfg_module, "CONFIG_PATH", fake_path)
    return fake_path


# ---------------------------------------------------------------------------
# load_config / save_config roundtrip
# ---------------------------------------------------------------------------

def test_load_config_missing_returns_empty():
    assert load_config() == {}


def test_save_and_load_string():
    save_config({"author": "Alice"})
    assert load_config()["author"] == "Alice"


def test_save_and_load_int():
    save_config({"days": 7})
    assert load_config()["days"] == 7


def test_save_and_load_bool_true():
    save_config({"no_ai": True})
    assert load_config()["no_ai"] is True


def test_save_and_load_bool_false():
    save_config({"no_ai": False})
    assert load_config()["no_ai"] is False


def test_save_overwrites():
    save_config({"author": "Alice"})
    save_config({"author": "Bob"})
    assert load_config()["author"] == "Bob"


# ---------------------------------------------------------------------------
# set_key / unset_key
# ---------------------------------------------------------------------------

def test_set_key_string():
    set_key("author", "Charlie")
    assert load_config()["author"] == "Charlie"


def test_set_key_int():
    set_key("days", "14")
    assert load_config()["days"] == 14


def test_set_key_bool_true():
    set_key("no_ai", "true")
    assert load_config()["no_ai"] is True


def test_set_key_bool_yes():
    set_key("no_ai", "yes")
    assert load_config()["no_ai"] is True


def test_set_key_bool_false():
    set_key("no_ai", "false")
    assert load_config()["no_ai"] is False


def test_set_key_invalid_key():
    with pytest.raises(ValueError, match="Unknown key"):
        set_key("badkey", "value")


def test_set_key_invalid_int():
    with pytest.raises(ValueError, match="must be an integer"):
        set_key("days", "notanint")


def test_unset_key_removes():
    set_key("author", "Alice")
    unset_key("author")
    assert "author" not in load_config()


def test_unset_key_missing_is_noop():
    unset_key("author")   # should not raise


# ---------------------------------------------------------------------------
# build_default_map
# ---------------------------------------------------------------------------

def test_build_default_map_empty():
    dm = build_default_map({})
    assert isinstance(dm, dict)
    assert "changelog" in dm
    assert "standup" in dm


def test_build_default_map_repo_as_tuple():
    dm = build_default_map({"repo": "/some/path"})
    assert dm["changelog"]["repo"] == ("/some/path",)


def test_build_default_map_days_in_standup():
    dm = build_default_map({"days": 3})
    assert dm["standup"]["days"] == 3
    assert "days" not in dm["changelog"]


def test_build_default_map_weeks_in_digest():
    dm = build_default_map({"weeks": 2})
    assert dm["digest"]["weeks"] == 2


def test_build_default_map_base_in_pr():
    dm = build_default_map({"base": "develop"})
    assert dm["pr"]["base"] == "develop"


def test_build_default_map_includes_new_commands():
    dm = build_default_map({})
    assert "release-notes" in dm
    assert "stats" in dm


# ---------------------------------------------------------------------------
# load_repo_config
# ---------------------------------------------------------------------------

def test_load_repo_config_missing(tmp_path):
    assert load_repo_config(str(tmp_path)) == {}


def test_load_repo_config_reads_file(tmp_path):
    (tmp_path / REPO_CONFIG_NAME).write_text('author = "TeamBot"\n')
    cfg = load_repo_config(str(tmp_path))
    assert cfg["author"] == "TeamBot"


# ---------------------------------------------------------------------------
# merge_configs
# ---------------------------------------------------------------------------

def test_merge_configs_later_wins():
    result = merge_configs({"a": 1, "b": 2}, {"b": 99})
    assert result["b"] == 99
    assert result["a"] == 1


def test_merge_configs_empty():
    assert merge_configs({}) == {}
