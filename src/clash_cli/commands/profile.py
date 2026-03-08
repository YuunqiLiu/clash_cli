"""``clash profile add/list/use/refresh/delete`` — subscription management."""

from __future__ import annotations

import argparse
import re
from datetime import datetime, timezone
from typing import Optional

import requests
import yaml

from ..daemon import registry, launcher
from ..formatters import output, error
from ..errors import ClashError
from ..config import profiles_dir


def register(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser(
        "profile",
        help="Manage subscription profiles",
        description=(
            "Add, list, switch, refresh, or delete mihomo configuration profiles.\n"
            "Profiles are subscription URLs downloaded and cached locally."
        ),
    )
    psub = p.add_subparsers(dest="profile_action", metavar="ACTION")

    # --- add ---
    add_p = psub.add_parser(
        "add",
        help="Download a subscription URL and save as a named profile",
        description="Download <url>, validate as YAML, and store under ~/.clash_cli/profiles/<name>.yaml.",
    )
    add_p.add_argument("name", help="Short name for this profile (e.g. 'home', 'work')")
    add_p.add_argument("url", help="Subscription URL to download")
    add_p.add_argument("--use", action="store_true",
                       help="Immediately switch to this profile after adding")
    add_p.set_defaults(func=_cmd_add)

    # --- list ---
    list_p = psub.add_parser(
        "list",
        help="List all saved profiles",
        description="Show all profiles in ~/.clash_cli/profiles/ with node counts and timestamps.",
    )
    list_p.set_defaults(func=_cmd_list)

    # --- use ---
    use_p = psub.add_parser(
        "use",
        help="Switch the active profile (hot-reload mihomo config)",
        description="Load the named profile into the running mihomo instance via PUT /configs.",
    )
    use_p.add_argument("name", help="Profile name to activate")
    use_p.set_defaults(func=_cmd_use)

    # --- refresh ---
    ref_p = psub.add_parser(
        "refresh",
        help="Re-download subscription and update the profile",
        description=(
            "Re-fetch the subscription URL for the named profile (or the active one).\n"
            "Uses ETag / If-None-Match to skip unnecessary downloads."
        ),
    )
    ref_p.add_argument("name", nargs="?", default=None,
                       help="Profile name to refresh (default: active profile)")
    ref_p.set_defaults(func=_cmd_refresh)

    # --- delete ---
    del_p = psub.add_parser(
        "delete",
        help="Delete a saved profile",
        description="Remove the profile YAML and metadata. Cannot delete the active profile.",
    )
    del_p.add_argument("name", help="Profile name to delete")
    del_p.set_defaults(func=_cmd_delete)


# ------------------------------------------------------------------

def _mask_url(url: str) -> str:
    """Hide sensitive query params."""
    return re.sub(r'(token|key|password)=[^&]+', r'\1=***', url, flags=re.I)


def _count_nodes_groups(config: dict) -> tuple[int, int]:
    proxies = config.get("proxies", [])
    groups = config.get("proxy-groups", [])
    return len(proxies), len(groups)


def _cmd_add(args: argparse.Namespace) -> None:
    as_json = getattr(args, "json", False)
    name: str = args.name
    url: str = args.url

    # Download
    try:
        resp = requests.get(url, timeout=30,
                            headers={"User-Agent": "clash_cli/0.1"})
        resp.raise_for_status()
    except requests.RequestException as e:
        error(f"Download failed: {e}", code="DOWNLOAD_FAILED", as_json=as_json)

    # Validate YAML
    try:
        config = yaml.safe_load(resp.text)
        if not isinstance(config, dict):
            raise ValueError("not a mapping")
    except Exception as e:
        error(f"Invalid config YAML: {e}", code="INVALID_CONFIG", as_json=as_json)

    # Save
    yaml_path = registry.profile_yaml_path(name)
    yaml_path.write_text(resp.text, encoding="utf-8")

    nodes, groups = _count_nodes_groups(config)
    meta = registry.ProfileMeta(
        name=name,
        url=url,
        etag=resp.headers.get("ETag", ""),
        updated_at=datetime.now(timezone.utc).isoformat(),
        node_count=nodes,
        group_count=groups,
    )
    registry.save_profile_meta(meta)

    if as_json:
        from dataclasses import asdict
        output(asdict(meta), as_json=True)
    else:
        output(
            f'✓ Profile "{name}" added\n'
            f"  Proxies: {nodes} nodes in {groups} groups\n"
            f"  Updated: {meta.updated_at}"
        )

    if args.use:
        # Delegate to use
        args.name = name
        _cmd_use(args)


def _cmd_list(args: argparse.Namespace) -> None:
    as_json = getattr(args, "json", False)
    profiles = registry.list_profiles()
    state = registry.load_state()
    active = state.active_profile

    if as_json:
        from dataclasses import asdict
        items = []
        for m in profiles:
            d = asdict(m)
            d["active"] = (m.name == active)
            items.append(d)
        output(items, as_json=True)
        return

    if not profiles:
        output("No profiles. Run: clash profile add <name> <url>")
        return

    lines = [f"  {'NAME':<12} {'NODES':>5}  {'UPDATED':<20} URL"]
    for m in profiles:
        marker = "✦" if m.name == active else " "
        ts = m.updated_at[:19].replace("T", " ") if m.updated_at else "-"
        lines.append(
            f"{marker} {m.name:<12} {m.node_count:>5}  {ts:<20} {_mask_url(m.url)}"
        )
    output("\n".join(lines))


def _cmd_use(args: argparse.Namespace) -> None:
    as_json = getattr(args, "json", False)
    name: str = args.name

    yaml_path = registry.profile_yaml_path(name)
    if not yaml_path.exists():
        error(f'Profile "{name}" not found', code="PROFILE_NOT_FOUND", as_json=as_json)

    # If mihomo is running, hot-reload
    if launcher.is_running():
        try:
            client = launcher.get_client()
            client.reload_configs(str(yaml_path.resolve()))
        except ClashError as e:
            error(e.message, code=e.code, as_json=as_json)

    # Update state
    state = registry.load_state()
    state.active_profile = name
    registry.save_state(state)

    meta = registry.load_profile_meta(name)
    nodes = meta.node_count if meta else "?"
    if as_json:
        output({"profile": name, "node_count": nodes}, as_json=True)
    else:
        output(f'✓ Switched to profile "{name}" ({nodes} nodes)')


def _cmd_refresh(args: argparse.Namespace) -> None:
    as_json = getattr(args, "json", False)
    name: Optional[str] = args.name
    if name is None:
        state = registry.load_state()
        name = state.active_profile
    if not name:
        error("No profile to refresh", code="PROFILE_NOT_FOUND", as_json=as_json)

    meta = registry.load_profile_meta(name)
    if not meta or not meta.url:
        error(f'Profile "{name}" has no URL (local file?)',
              code="DOWNLOAD_FAILED", as_json=as_json)

    headers = {"User-Agent": "clash_cli/0.1"}
    if meta.etag:
        headers["If-None-Match"] = meta.etag

    try:
        resp = requests.get(meta.url, timeout=30, headers=headers)
    except requests.RequestException as e:
        error(f"Download failed: {e}", code="DOWNLOAD_FAILED", as_json=as_json)

    if resp.status_code == 304:
        if as_json:
            output({"profile": name, "changed": False}, as_json=True)
        else:
            output(f'Profile "{name}" is already up to date')
        return

    resp.raise_for_status()
    try:
        config = yaml.safe_load(resp.text)
        if not isinstance(config, dict):
            raise ValueError("not a mapping")
    except Exception as e:
        error(f"Invalid config YAML: {e}", code="INVALID_CONFIG", as_json=as_json)

    old_nodes = meta.node_count
    yaml_path = registry.profile_yaml_path(name)
    yaml_path.write_text(resp.text, encoding="utf-8")

    nodes, groups = _count_nodes_groups(config)
    meta.etag = resp.headers.get("ETag", "")
    meta.updated_at = datetime.now(timezone.utc).isoformat()
    meta.node_count = nodes
    meta.group_count = groups
    registry.save_profile_meta(meta)

    # Hot-reload if active
    state = registry.load_state()
    if state.active_profile == name and launcher.is_running():
        try:
            client = launcher.get_client()
            client.reload_configs(str(yaml_path.resolve()))
        except ClashError:
            pass

    if as_json:
        output({"profile": name, "changed": True,
                "old_nodes": old_nodes, "new_nodes": nodes}, as_json=True)
    else:
        output(f'✓ Profile "{name}" updated (was: {old_nodes} nodes → now: {nodes} nodes)')


def _cmd_delete(args: argparse.Namespace) -> None:
    as_json = getattr(args, "json", False)
    name: str = args.name
    state = registry.load_state()
    if state.active_profile == name and launcher.is_running():
        error(f'Cannot delete active profile "{name}". Switch first.',
              code="PROFILE_ACTIVE", as_json=as_json)

    if not registry.profile_yaml_path(name).exists():
        error(f'Profile "{name}" not found', code="PROFILE_NOT_FOUND", as_json=as_json)
    registry.delete_profile_files(name)
    if as_json:
        output({"profile": name, "deleted": True}, as_json=True)
    else:
        output(f'✓ Profile "{name}" deleted')
