"""Manage the mihomo child process lifecycle (start / stop / status)."""

from __future__ import annotations

import os
import shutil
import signal
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import yaml

from ..config import (
    home_dir, runtime_dir, cache_dir,
    DEFAULT_CONTROLLER_PORT, DEFAULT_MIXED_PORT, DEFAULT_LOG_LEVEL,
    STARTUP_POLL_INTERVAL, STARTUP_POLL_MAX, STOP_TIMEOUT,
)
from ..errors import ClashError
from .registry import (
    State, load_state, save_state, clear_state,
    store_secret, get_secret, delete_secret,
    profile_yaml_path,
)
from .client import MihomoClient


# ------------------------------------------------------------------
# Binary discovery
# ------------------------------------------------------------------

def find_mihomo() -> str:
    """Locate the mihomo binary.

    Search order:
    1. ``$CLASH_MIHOMO_PATH`` environment variable
    2. PyInstaller one-file bundle (``sys._MEIPASS/mihomo``)
    3. Same directory as the ``clash`` executable
    4. ``mihomo`` on ``$PATH``

    Returns the absolute path, or raises :class:`ClashError`.
    """
    env = os.environ.get("CLASH_MIHOMO_PATH")
    if env and os.path.isfile(env) and os.access(env, os.X_OK):
        return env

    # PyInstaller one-file mode: binaries are extracted to sys._MEIPASS
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidate = Path(meipass) / "mihomo"
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)

    # Next to this script / frozen exe
    here = Path(__file__).resolve().parent.parent
    candidate = here / "mihomo"
    if candidate.is_file() and os.access(candidate, os.X_OK):
        return str(candidate)

    # System PATH
    which = shutil.which("mihomo")
    if which:
        return which

    raise ClashError(
        "MIHOMO_NOT_FOUND",
        "mihomo binary not found. Install it or set CLASH_MIHOMO_PATH.",
    )


# ------------------------------------------------------------------
# Process helpers
# ------------------------------------------------------------------

def _pid_alive(pid: int) -> bool:
    """Return True if *pid* belongs to a running mihomo process."""
    try:
        cmdline = Path(f"/proc/{pid}/cmdline").read_text()
        return "mihomo" in cmdline
    except (OSError, FileNotFoundError):
        return False


# ------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------

def is_running() -> bool:
    """Check whether a managed mihomo instance is running."""
    state = load_state()
    if state.pid == 0:
        return False
    if _pid_alive(state.pid):
        return True
    # Stale state — clean up
    clear_state()
    return False


def start(
    profile_name: str,
    port: int = DEFAULT_CONTROLLER_PORT,
    mixed_port: int = DEFAULT_MIXED_PORT,
    log_level: str = DEFAULT_LOG_LEVEL,
    force: bool = False,
) -> State:
    """Start mihomo with the given *profile_name*.

    Returns the new :class:`State` on success.
    """
    if is_running():
        if force:
            stop()
        else:
            raise ClashError("ALREADY_RUNNING",
                             "mihomo is already running. Use --force or run: clash stop")

    # Locate binary
    binary = find_mihomo()

    # Validate profile
    yaml_path = profile_yaml_path(profile_name)
    if not yaml_path.exists():
        raise ClashError("PROFILE_NOT_FOUND",
                         f'Profile "{profile_name}" not found. Run: clash profile add')

    # Generate secret
    secret = uuid.uuid4().hex
    store_secret(secret)

    # Inject runtime config
    with open(yaml_path) as f:
        config = yaml.safe_load(f) or {}

    config["external-controller"] = f"127.0.0.1:{port}"
    config["secret"] = secret
    config["mixed-port"] = mixed_port
    config["log-level"] = log_level

    runtime_config = runtime_dir() / "config.yaml"
    with open(runtime_config, "w") as f:
        yaml.dump(config, f, allow_unicode=True)

    # Start process
    log_file = runtime_dir() / "mihomo.log"
    log_fd = open(log_file, "w")

    proc = subprocess.Popen(
        [binary, "-d", str(cache_dir()), "-f", str(runtime_config)],
        stdout=log_fd,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )

    # Poll until controller is ready
    client = MihomoClient(port=port, secret=secret, timeout=2)
    for _ in range(STARTUP_POLL_MAX):
        time.sleep(STARTUP_POLL_INTERVAL)
        if proc.poll() is not None:
            log_fd.close()
            delete_secret()
            snippet = ""
            try:
                snippet = log_file.read_text()[-500:]
            except Exception:
                pass
            raise ClashError("START_FAILED",
                             f"mihomo exited immediately (code {proc.returncode}). "
                             f"Log tail:\n{snippet}")
        try:
            client.get_version()
            break
        except ClashError:
            continue
    else:
        proc.terminate()
        log_fd.close()
        delete_secret()
        raise ClashError("START_TIMEOUT",
                         "mihomo did not become ready in time")

    log_fd.close()

    state = State(
        pid=proc.pid,
        port=port,
        mixed_port=mixed_port,
        active_profile=profile_name,
        started_at=datetime.now(timezone.utc).isoformat(),
        log_level=log_level,
        mihomo_binary=binary,
    )
    save_state(state)
    return state


def stop() -> int:
    """Stop the managed mihomo instance.  Returns the old PID."""
    state = load_state()
    if state.pid == 0 or not _pid_alive(state.pid):
        clear_state()
        delete_secret()
        raise ClashError("MIHOMO_NOT_RUNNING",
                         "mihomo is not running")
    pid = state.pid
    os.kill(pid, signal.SIGTERM)
    deadline = time.time() + STOP_TIMEOUT
    while time.time() < deadline:
        if not _pid_alive(pid):
            break
        time.sleep(0.2)
    else:
        os.kill(pid, signal.SIGKILL)

    clear_state()
    delete_secret()
    return pid


def get_client() -> MihomoClient:
    """Return a :class:`MihomoClient` for the running instance."""
    state = load_state()
    if state.pid == 0 or not _pid_alive(state.pid):
        raise ClashError("MIHOMO_NOT_RUNNING",
                         "mihomo is not running. Run: clash start")
    secret = get_secret()
    if not secret:
        raise ClashError("AUTH_FAILED",
                         "Cannot retrieve API secret from keyring")
    return MihomoClient(port=state.port, secret=secret)
