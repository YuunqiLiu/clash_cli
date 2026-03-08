"""
Integration test fixtures — starts a real mihomo instance on loopback ports.

网络隔离保证：
  - allow-lan: false   只绑定 127.0.0.1
  - 无 TUN / redir     不接管系统流量
  - DNS 关闭           不影响系统解析
  - 端口 19090/17890   不与系统已有 Clash 冲突
  - 测试只访问 API 端口，proxy 端口全程不调用

跳过条件：
  - mihomo 二进制不存在（本地 / CI 都可配置）
  - 或设置了 SKIP_INTEGRATION=1
"""

from __future__ import annotations

import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Generator

import pytest
import requests

from clash_cli.daemon.client import MihomoClient

# -------------------------------------------------------------------------
# Constants
# -------------------------------------------------------------------------

INTEGRATION_CONFIG = Path(__file__).parent / "fixtures" / "mihomo.yaml"
CONTROLLER_PORT = 19090
MIXED_PORT = 17890
SECRET = "integration-test-secret"

POLL_INTERVAL = 0.3   # seconds between readiness checks
POLL_MAX = 40         # 40 × 0.3s = 12s max startup time


# -------------------------------------------------------------------------
# Binary discovery (same priority as launcher.find_mihomo)
# -------------------------------------------------------------------------

def _find_mihomo_binary() -> str | None:
    env = os.environ.get("CLASH_MIHOMO_PATH")
    if env and os.path.isfile(env) and os.access(env, os.X_OK):
        return env

    which = shutil.which("mihomo")
    if which:
        return which

    return None


# -------------------------------------------------------------------------
# Session-scoped fixture
# -------------------------------------------------------------------------

@pytest.fixture(scope="session")
def mihomo(tmp_path_factory) -> Generator[MihomoClient, None, None]:
    """Start mihomo once per test session; yield a MihomoClient; shut down.

    Skips automatically if:
      - SKIP_INTEGRATION=1 is set, or
      - no mihomo binary is found.
    """
    if os.environ.get("SKIP_INTEGRATION") == "1":
        pytest.skip("SKIP_INTEGRATION=1")

    binary = _find_mihomo_binary()
    if binary is None:
        pytest.skip(
            "mihomo binary not found. "
            "Set CLASH_MIHOMO_PATH or install to PATH. "
            "Run: make install-mihomo  (see Makefile)"
        )

    # Use a tmp directory as the Mihomo home (cache, geoip, etc.)
    mihomo_home = tmp_path_factory.mktemp("mihomo_home")
    log_file = mihomo_home / "mihomo.log"

    cmd = [
        binary,
        "-d", str(mihomo_home),
        "-f", str(INTEGRATION_CONFIG),
    ]

    with open(log_file, "w") as log_fd:
        proc = subprocess.Popen(
            cmd,
            stdout=log_fd,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )

    # Poll until controller is ready
    client = MihomoClient(port=CONTROLLER_PORT, secret=SECRET, timeout=2)
    ready = False
    for _ in range(POLL_MAX):
        time.sleep(POLL_INTERVAL)
        if proc.poll() is not None:
            log_text = log_file.read_text()[-1000:]
            pytest.fail(
                f"mihomo exited unexpectedly (code {proc.returncode}).\n"
                f"Log tail:\n{log_text}"
            )
        try:
            resp = client.get_version()
            if resp.get("version"):
                ready = True
                break
        except Exception:
            continue

    if not ready:
        proc.terminate()
        pytest.fail("mihomo did not become ready within timeout")

    print(f"\n[integration] mihomo started: pid={proc.pid}, port={CONTROLLER_PORT}",
          file=sys.stderr)

    yield client

    # Teardown
    try:
        proc.terminate()
        proc.wait(timeout=5)
    except (ProcessLookupError, subprocess.TimeoutExpired):
        try:
            proc.kill()
        except ProcessLookupError:
            pass

    print(f"\n[integration] mihomo stopped: pid={proc.pid}", file=sys.stderr)
