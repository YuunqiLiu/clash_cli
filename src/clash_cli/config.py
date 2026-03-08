"""Paths, defaults and constants for clash_cli."""

from __future__ import annotations

import os
from pathlib import Path


def home_dir() -> Path:
    """Return ``~/.clash_cli``, creating it if needed."""
    p = Path(os.environ.get("CLASH_CLI_HOME", Path.home() / ".clash_cli"))
    p.mkdir(parents=True, exist_ok=True)
    return p


def profiles_dir() -> Path:
    d = home_dir() / "profiles"
    d.mkdir(exist_ok=True)
    return d


def runtime_dir() -> Path:
    d = home_dir() / "runtime"
    d.mkdir(exist_ok=True)
    return d


def cache_dir() -> Path:
    d = home_dir() / "cache"
    d.mkdir(exist_ok=True)
    return d


STATE_FILE = "state.json"
KEYRING_SERVICE = "clash_cli"

DEFAULT_CONTROLLER_PORT = 9090
DEFAULT_MIXED_PORT = 7890
DEFAULT_LOG_LEVEL = "info"
DEFAULT_TEST_URL = "https://cp.cloudflare.com/generate_204"
DEFAULT_TIMEOUT_MS = 5000
STARTUP_POLL_INTERVAL = 0.5  # seconds
STARTUP_POLL_MAX = 10
STOP_TIMEOUT = 5  # seconds
