"""``clash log tail`` — stream mihomo logs via SSE."""

from __future__ import annotations

import argparse
import sys

from ..daemon import launcher
from ..formatters import output, error
from ..errors import ClashError

VALID_LEVELS = ("debug", "info", "warning", "error", "silent")


def register(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser(
        "log",
        help="Stream or query mihomo logs",
        description="Stream real-time logs from mihomo using Server-Sent Events.",
    )
    lsub = p.add_subparsers(dest="log_action", metavar="ACTION")

    tail = lsub.add_parser(
        "tail",
        help="Stream logs in real time",
        description=(
            "Connect to mihomo log stream via SSE and print log lines.\n"
            "Press Ctrl-C to stop."
        ),
    )
    tail.add_argument(
        "--level",
        choices=VALID_LEVELS,
        default="info",
        help="Minimum log level to display (default: info)",
    )
    tail.set_defaults(func=_cmd_tail)


def _cmd_tail(args: argparse.Namespace) -> None:
    as_json = getattr(args, "json", False)
    try:
        client = launcher.get_client()
    except ClashError as e:
        error(e.message, code=e.code, as_json=as_json, exit_code=3)
        return

    if as_json:
        # In JSON mode, output newline-delimited JSON objects
        try:
            for entry in client.stream_logs(level=args.level):
                output(entry, as_json=True)
        except KeyboardInterrupt:
            pass
        return

    try:
        for entry in client.stream_logs(level=args.level):
            lvl = entry.get("type", "info").upper()
            msg = entry.get("payload", "")
            sys.stdout.write(f"[{lvl:<7}] {msg}\n")
            sys.stdout.flush()
    except KeyboardInterrupt:
        sys.stdout.write("\n")
