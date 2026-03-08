"""Persistent state stored under ``~/.clash_cli/``."""

from __future__ import annotations

import json
import os
import getpass
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import keyring
import keyring.errors

from ..config import home_dir, profiles_dir, STATE_FILE, KEYRING_SERVICE


# ---------------------------------------------------------------------------
# State (mihomo process info)
# ---------------------------------------------------------------------------

@dataclass
class State:
    """Serialisable snapshot of the running mihomo instance."""

    version: int = 1
    pid: int = 0
    port: int = 0
    mixed_port: int = 0
    active_profile: str = ""
    started_at: str = ""
    log_level: str = "info"
    mihomo_binary: str = ""


def _state_path() -> Path:
    return home_dir() / STATE_FILE


def load_state() -> State:
    p = _state_path()
    if not p.exists():
        return State()
    try:
        with open(p) as f:
            data = json.load(f)
        return State(**{k: v for k, v in data.items() if k in State.__dataclass_fields__})
    except (json.JSONDecodeError, TypeError):
        return State()


def save_state(state: State) -> None:
    with open(_state_path(), "w") as f:
        json.dump(asdict(state), f, indent=2)


def clear_state() -> None:
    p = _state_path()
    if p.exists():
        p.unlink()


# ---------------------------------------------------------------------------
# Secret (keyring)
# ---------------------------------------------------------------------------

def _username() -> str:
    return getpass.getuser()


def store_secret(secret: str) -> None:
    keyring.set_password(KEYRING_SERVICE, _username(), secret)


def get_secret() -> Optional[str]:
    return keyring.get_password(KEYRING_SERVICE, _username())


def delete_secret() -> None:
    try:
        keyring.delete_password(KEYRING_SERVICE, _username())
    except keyring.errors.PasswordDeleteError:
        pass


# ---------------------------------------------------------------------------
# Profile metadata
# ---------------------------------------------------------------------------

@dataclass
class ProfileMeta:
    name: str = ""
    url: str = ""
    etag: str = ""
    updated_at: str = ""
    auto_refresh_hours: int = 24
    node_count: int = 0
    group_count: int = 0


def profile_yaml_path(name: str) -> Path:
    return profiles_dir() / f"{name}.yaml"


def profile_meta_path(name: str) -> Path:
    return profiles_dir() / f"{name}.meta.json"


def load_profile_meta(name: str) -> Optional[ProfileMeta]:
    p = profile_meta_path(name)
    if not p.exists():
        return None
    try:
        with open(p) as f:
            data = json.load(f)
        return ProfileMeta(**{k: v for k, v in data.items() if k in ProfileMeta.__dataclass_fields__})
    except (json.JSONDecodeError, TypeError):
        return None


def save_profile_meta(meta: ProfileMeta) -> None:
    with open(profile_meta_path(meta.name), "w") as f:
        json.dump(asdict(meta), f, indent=2)


def delete_profile_files(name: str) -> None:
    for p in (profile_yaml_path(name), profile_meta_path(name)):
        if p.exists():
            p.unlink()


def list_profiles() -> list[ProfileMeta]:
    results: list[ProfileMeta] = []
    for p in sorted(profiles_dir().glob("*.meta.json")):
        meta = load_profile_meta(p.stem.replace(".meta", ""))
        if meta:
            results.append(meta)
    return results
