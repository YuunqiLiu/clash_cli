"""Shared fixtures for clash_cli tests."""

from __future__ import annotations

import json
import os
import sys
import pytest
from pathlib import Path
from unittest.mock import MagicMock


@pytest.fixture(autouse=True)
def isolate_home(tmp_path, monkeypatch):
    """Redirect CLASH_CLI_HOME to a temp directory for every test."""
    home = tmp_path / ".clash_cli"
    home.mkdir()
    monkeypatch.setenv("CLASH_CLI_HOME", str(home))
    return home


@pytest.fixture
def profiles_dir(isolate_home):
    d = isolate_home / "profiles"
    d.mkdir(exist_ok=True)
    return d


@pytest.fixture
def runtime_dir(isolate_home):
    d = isolate_home / "runtime"
    d.mkdir(exist_ok=True)
    return d


@pytest.fixture
def mock_client():
    """Return a MagicMock that behaves like MihomoClient."""
    client = MagicMock()
    client.get_version.return_value = {"version": "v1.18.0", "premium": False}
    client.get_configs.return_value = {"mode": "rule", "log-level": "info"}
    client.get_proxies.return_value = {"proxies": {}}
    client.get_rules.return_value = {"rules": []}
    client.get_connections.return_value = {"connections": [], "downloadTotal": 0, "uploadTotal": 0}
    client.get_groups.return_value = {"proxies": {}}
    return client
