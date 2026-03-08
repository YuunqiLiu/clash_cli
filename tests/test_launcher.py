"""Tests for clash_cli.daemon.launcher (process management)."""

from __future__ import annotations

import os
import textwrap
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from clash_cli.daemon.launcher import (
    find_mihomo, is_running, _pid_alive, get_client,
)
from clash_cli.daemon.registry import State, save_state, clear_state
from clash_cli.errors import ClashError


# ------------------------------------------------------------------
# find_mihomo
# ------------------------------------------------------------------

class TestFindMihomo:
    def test_env_var(self, tmp_path, monkeypatch):
        fake = tmp_path / "mihomo"
        fake.write_text("#!/bin/sh\n")
        fake.chmod(0o755)
        monkeypatch.setenv("CLASH_MIHOMO_PATH", str(fake))
        assert find_mihomo() == str(fake)

    def test_env_var_not_executable(self, tmp_path, monkeypatch):
        fake = tmp_path / "mihomo"
        fake.write_text("not executable")
        fake.chmod(0o644)
        monkeypatch.setenv("CLASH_MIHOMO_PATH", str(fake))
        # Falls through to shutil.which
        with patch("shutil.which", return_value=None):
            with pytest.raises(ClashError) as exc:
                find_mihomo()
            assert exc.value.code == "MIHOMO_NOT_FOUND"

    def test_meipass_bundled(self, tmp_path, monkeypatch):
        """Binary found in sys._MEIPASS (PyInstaller one-file bundle)."""
        fake = tmp_path / "mihomo"
        fake.write_text("#!/bin/sh\n")
        fake.chmod(0o755)
        monkeypatch.delenv("CLASH_MIHOMO_PATH", raising=False)
        import clash_cli.daemon.launcher as _launcher
        monkeypatch.setattr(_launcher.sys, "_MEIPASS", str(tmp_path), raising=False)
        monkeypatch.setattr("shutil.which", lambda _: None)
        result = find_mihomo()
        assert result == str(fake)

    def test_on_path(self, monkeypatch):
        monkeypatch.delenv("CLASH_MIHOMO_PATH", raising=False)
        with patch("shutil.which", return_value="/usr/local/bin/mihomo"):
            assert find_mihomo() == "/usr/local/bin/mihomo"

    def test_not_found(self, monkeypatch):
        monkeypatch.delenv("CLASH_MIHOMO_PATH", raising=False)
        with patch("shutil.which", return_value=None):
            with pytest.raises(ClashError) as exc:
                find_mihomo()
            assert exc.value.code == "MIHOMO_NOT_FOUND"


# ------------------------------------------------------------------
# is_running
# ------------------------------------------------------------------

class TestIsRunning:
    def test_no_state(self, isolate_home):
        assert is_running() is False

    def test_pid_zero(self, isolate_home):
        save_state(State(pid=0))
        assert is_running() is False

    @patch("clash_cli.daemon.launcher._pid_alive", return_value=True)
    def test_alive(self, mock_alive, isolate_home):
        save_state(State(pid=12345))
        assert is_running() is True

    @patch("clash_cli.daemon.launcher._pid_alive", return_value=False)
    def test_stale_state_cleaned(self, mock_alive, isolate_home):
        save_state(State(pid=99999))
        assert is_running() is False
        # State should be cleaned up
        from clash_cli.daemon.registry import load_state
        assert load_state().pid == 0


# ------------------------------------------------------------------
# get_client
# ------------------------------------------------------------------

class TestGetClient:
    def test_not_running(self, isolate_home):
        with pytest.raises(ClashError) as exc:
            get_client()
        assert exc.value.code == "MIHOMO_NOT_RUNNING"

    @patch("clash_cli.daemon.launcher._pid_alive", return_value=True)
    @patch("clash_cli.daemon.launcher.get_secret", return_value="abc")
    def test_returns_client(self, mock_secret, mock_alive, isolate_home):
        save_state(State(pid=12345, port=9090))
        client = get_client()
        assert client.base_url == "http://127.0.0.1:9090"

    @patch("clash_cli.daemon.launcher._pid_alive", return_value=True)
    @patch("clash_cli.daemon.launcher.get_secret", return_value=None)
    def test_no_secret(self, mock_secret, mock_alive, isolate_home):
        save_state(State(pid=12345, port=9090))
        with pytest.raises(ClashError) as exc:
            get_client()
        assert exc.value.code == "AUTH_FAILED"
