"""Main CLI entry point for clash_cli.

Usage::

    clash <command> [options]
    clash --json <command> [options]

The ``--json`` flag is a **global** option that forces all output to be
machine-readable JSON (``{"status": "ok", "data": ...}`` or
``{"status": "error", "error": {...}}``).
"""

from __future__ import annotations

import argparse
import sys

from . import __version__
from .commands import start, profile, mode, proxy, rule, conn, log, dns


def build_parser() -> argparse.ArgumentParser:
    """Construct the top-level parser and register every sub-command."""

    parser = argparse.ArgumentParser(
        prog="clash",
        description=(
            "clash_cli — CLI proxy manager powered by mihomo.\n"
            "Manage mihomo instances, profiles, proxies, rules, and "
            "connections from the terminal."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        default=False,
        dest="json",
        help="Output results as machine-readable JSON",
    )

    sub = parser.add_subparsers(dest="command", metavar="COMMAND")

    # Register all command modules
    start.register_start(sub)     # clash start
    start.register_stop(sub)      # clash stop
    start.register_restart(sub)   # clash restart
    start.register_status(sub)    # clash status
    profile.register(sub)         # profile add / list / use / refresh / delete
    mode.register(sub)            # mode get / set
    proxy.register(sub)           # proxy list / use / delay
    rule.register(sub)            # rule list
    conn.register(sub)            # conn list / close
    log.register(sub)             # log tail
    dns.register(sub)             # dns query / flush

    return parser


def main(argv: list[str] | None = None) -> None:
    """Parse arguments and dispatch to the appropriate sub-command."""

    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    # Some commands register sub-actions (e.g. ``profile add``).
    # If the sub-action is missing, print the command's help.
    func = getattr(args, "func", None)
    if func is None:
        # Find the sub-parser for this command and print its help
        for action in parser._subparsers._actions:
            if isinstance(action, argparse._SubParsersAction):
                sub_parser = action.choices.get(args.command)
                if sub_parser:
                    sub_parser.print_help()
                    break
        sys.exit(0)

    func(args)


if __name__ == "__main__":
    main()
