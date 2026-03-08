"""``clash start / stop / restart / status`` — mihomo process management."""

from __future__ import annotations

import argparse

from ..daemon import launcher, registry
from ..formatters import output, error
from ..errors import ClashError
from ..config import DEFAULT_CONTROLLER_PORT, DEFAULT_MIXED_PORT, DEFAULT_LOG_LEVEL


def register_start(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser(
        "start",
        help="Start the mihomo proxy core",
        description=(
            "Launch a mihomo instance using the specified profile.\n"
            "If mihomo is already running, the command fails unless --force is given."
        ),
    )
    p.add_argument("--profile", "-p", default=None,
                   help="Profile name to activate (default: last used)")
    p.add_argument("--port", type=int, default=DEFAULT_CONTROLLER_PORT,
                   help=f"Controller API port (default: {DEFAULT_CONTROLLER_PORT})")
    p.add_argument("--mixed-port", type=int, default=DEFAULT_MIXED_PORT,
                   help=f"Mixed HTTP/SOCKS proxy port (default: {DEFAULT_MIXED_PORT})")
    p.add_argument("--log-level", default=DEFAULT_LOG_LEVEL,
                   choices=["silent", "error", "warning", "info", "debug"],
                   help=f"mihomo log level (default: {DEFAULT_LOG_LEVEL})")
    p.add_argument("--force", action="store_true",
                   help="Stop any running instance before starting")
    p.set_defaults(func=_cmd_start)


def _cmd_start(args: argparse.Namespace) -> None:
    as_json = getattr(args, "json", False)
    profile = args.profile
    if profile is None:
        # Try to reuse the last active profile
        state = registry.load_state()
        profile = state.active_profile or ""
    if not profile:
        error("No profile specified. Run: clash profile add <name> <url>",
              code="PROFILE_NOT_FOUND", as_json=as_json)

    try:
        state = launcher.start(
            profile_name=profile,
            port=args.port,
            mixed_port=args.mixed_port,
            log_level=args.log_level,
            force=args.force,
        )
    except ClashError as e:
        error(e.message, code=e.code, as_json=as_json)

    if as_json:
        output({
            "pid": state.pid,
            "controller": f"127.0.0.1:{state.port}",
            "mixed_port": state.mixed_port,
            "profile": state.active_profile,
            "mode": "rule",
        }, as_json=True)
    else:
        output(
            f"✓ mihomo started (pid: {state.pid})\n"
            f"  Controller:   127.0.0.1:{state.port}\n"
            f"  Mixed proxy:  127.0.0.1:{state.mixed_port}\n"
            f"  Profile:      {state.active_profile}\n"
            f"  Log level:    {state.log_level}"
        )


def register_stop(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser(
        "stop",
        help="Stop the running mihomo instance",
        description="Send SIGTERM to the managed mihomo process and clean up state.",
    )
    p.set_defaults(func=_cmd_stop)


def _cmd_stop(args: argparse.Namespace) -> None:
    as_json = getattr(args, "json", False)
    try:
        pid = launcher.stop()
    except ClashError as e:
        error(e.message, code=e.code, as_json=as_json)
    if as_json:
        output({"pid": pid, "stopped": True}, as_json=True)
    else:
        output(f"✓ mihomo stopped (pid: {pid})")


def register_restart(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser(
        "restart",
        help="Restart mihomo (stop then start with same settings)",
        description="Equivalent to ``clash stop && clash start`` preserving current settings.",
    )
    p.set_defaults(func=_cmd_restart)


def _cmd_restart(args: argparse.Namespace) -> None:
    as_json = getattr(args, "json", False)
    state = registry.load_state()
    profile = state.active_profile
    port = state.port or DEFAULT_CONTROLLER_PORT
    mixed_port = state.mixed_port or DEFAULT_MIXED_PORT
    log_level = state.log_level or DEFAULT_LOG_LEVEL

    try:
        launcher.stop()
    except ClashError:
        pass  # already stopped

    if not profile:
        error("No active profile to restart with", code="PROFILE_NOT_FOUND", as_json=as_json)

    try:
        new_state = launcher.start(
            profile_name=profile, port=port,
            mixed_port=mixed_port, log_level=log_level,
        )
    except ClashError as e:
        error(e.message, code=e.code, as_json=as_json)

    if as_json:
        output({"pid": new_state.pid, "restarted": True}, as_json=True)
    else:
        output(f"✓ mihomo restarted (pid: {new_state.pid})")


def register_status(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser(
        "status",
        help="Show mihomo running status",
        description="Display whether mihomo is running and, if so, version / config details.",
    )
    p.set_defaults(func=_cmd_status)


def _cmd_status(args: argparse.Namespace) -> None:
    as_json = getattr(args, "json", False)
    if not launcher.is_running():
        if as_json:
            output({"running": False}, as_json=True)
        else:
            output("○ mihomo is not running")
        return

    state = registry.load_state()
    try:
        client = launcher.get_client()
        ver = client.get_version()
        cfg = client.get_configs()
    except ClashError:
        ver = {}
        cfg = {}

    data = {
        "running": True,
        "pid": state.pid,
        "version": ver.get("version", "unknown"),
        "profile": state.active_profile,
        "mode": cfg.get("mode", "unknown"),
        "controller": f"127.0.0.1:{state.port}",
        "mixed_port": state.mixed_port,
    }
    if as_json:
        output(data, as_json=True)
    else:
        output(
            f"● mihomo running (pid: {state.pid})\n"
            f"  Version:      {data['version']}\n"
            f"  Profile:      {state.active_profile}\n"
            f"  Mode:         {data['mode']}\n"
            f"  Controller:   127.0.0.1:{state.port}\n"
            f"  Mixed proxy:  127.0.0.1:{state.mixed_port}"
        )
