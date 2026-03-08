"""Tests for clash_cli.daemon.registry (state + profile + keyring)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

from clash_cli.daemon.registry import (
    State, load_state, save_state, clear_state,
    ProfileMeta, load_profile_meta, save_profile_meta,
    delete_profile_files, list_profiles,
    profile_yaml_path, profile_meta_path,
    store_secret, get_secret, delete_secret,
)


# ------------------------------------------------------------------
# State
# ------------------------------------------------------------------

class TestState:
    def test_default_state(self):
        s = State()
        assert s.pid == 0
        assert s.port == 0
        assert s.active_profile == ""

    def test_save_and_load(self, isolate_home):
        s = State(pid=42, port=9090, active_profile="main")
        save_state(s)
        loaded = load_state()
        assert loaded.pid == 42
        assert loaded.port == 9090
        assert loaded.active_profile == "main"

    def test_load_missing_returns_default(self, isolate_home):
        s = load_state()
        assert s.pid == 0

    def test_clear_state(self, isolate_home):
        save_state(State(pid=1))
        clear_state()
        assert load_state().pid == 0

    def test_load_corrupted_returns_default(self, isolate_home):
        state_path = isolate_home / "state.json"
        state_path.write_text("NOT JSON")
        s = load_state()
        assert s.pid == 0

    def test_load_ignores_extra_fields(self, isolate_home):
        state_path = isolate_home / "state.json"
        state_path.write_text(json.dumps({"pid": 10, "unknown_field": "x"}))
        s = load_state()
        assert s.pid == 10


# ------------------------------------------------------------------
# Profiles
# ------------------------------------------------------------------

class TestProfileMeta:
    def test_save_and_load(self, profiles_dir):
        meta = ProfileMeta(name="test", url="https://example.com/sub",
                           node_count=5, group_count=2)
        save_profile_meta(meta)
        loaded = load_profile_meta("test")
        assert loaded is not None
        assert loaded.name == "test"
        assert loaded.url == "https://example.com/sub"
        assert loaded.node_count == 5

    def test_load_missing_returns_none(self, profiles_dir):
        assert load_profile_meta("nonexistent") is None

    def test_delete_profile_files(self, profiles_dir):
        yaml_p = profile_yaml_path("del_me")
        yaml_p.write_text("proxies: []")
        meta = ProfileMeta(name="del_me", url="https://x.com")
        save_profile_meta(meta)
        assert yaml_p.exists()
        delete_profile_files("del_me")
        assert not yaml_p.exists()
        assert not profile_meta_path("del_me").exists()

    def test_list_profiles(self, profiles_dir):
        for name in ("alpha", "beta"):
            save_profile_meta(ProfileMeta(name=name, url=f"https://{name}.com"))
        results = list_profiles()
        names = [m.name for m in results]
        assert "alpha" in names
        assert "beta" in names


# ------------------------------------------------------------------
# Keyring (mocked)
# ------------------------------------------------------------------

class TestKeyring:
    @patch("clash_cli.daemon.registry.keyring")
    def test_store_and_get(self, mock_kr):
        store_secret("my-secret")
        mock_kr.set_password.assert_called_once()

    @patch("clash_cli.daemon.registry.keyring")
    def test_get_secret(self, mock_kr):
        mock_kr.get_password.return_value = "abc123"
        assert get_secret() == "abc123"

    @patch("clash_cli.daemon.registry.keyring")
    def test_delete_secret_no_error(self, mock_kr):
        delete_secret()
        mock_kr.delete_password.assert_called_once()

    @patch("clash_cli.daemon.registry.keyring")
    def test_delete_secret_ignores_keyring_error(self, mock_kr):
        # Attach the real exception class to the mock so the except clause works
        import keyring.errors as _ke
        mock_kr.errors = _ke
        mock_kr.delete_password.side_effect = _ke.PasswordDeleteError()
        # Should not raise
        delete_secret()
