"""Tests for clash_cli.config."""

from pathlib import Path

from clash_cli.config import (
    home_dir, profiles_dir, runtime_dir, cache_dir,
    DEFAULT_CONTROLLER_PORT, DEFAULT_MIXED_PORT,
)


def test_home_dir_uses_env(isolate_home):
    h = home_dir()
    assert h == isolate_home
    assert h.exists()


def test_profiles_dir_created(isolate_home):
    d = profiles_dir()
    assert d.exists()
    assert d.parent == isolate_home


def test_runtime_dir_created(isolate_home):
    d = runtime_dir()
    assert d.exists()
    assert d.parent == isolate_home


def test_cache_dir_created(isolate_home):
    d = cache_dir()
    assert d.exists()
    assert d.parent == isolate_home


def test_default_ports():
    assert DEFAULT_CONTROLLER_PORT == 9090
    assert DEFAULT_MIXED_PORT == 7890
