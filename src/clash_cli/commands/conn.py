"""``clash conn list/close`` — connection management."""

from __future__ import annotations

import argparse

from ..daemon import launcher
from ..formatters import output, error
from ..errors import ClashError


def register(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser(
        "conn",
        help="List or close active connections",
        description="Inspect or terminate TCP/UDP connections managed by mihomo.",
    )
    csub = p.add_subparsers(dest="conn_action", metavar="ACTION")

    ls = csub.add_parser(
        "list",
        help="List active connections",
        description="Show currently active connections with traffic stats.",
    )
    ls.add_argument("--max", type=int, default=20, dest="max_conns",
                    help="Maximum connections to show (default: 20)")
    ls.set_defaults(func=_cmd_list)

    cl = csub.add_parser(
        "close",
        help="Close connections",
        description="Close a specific connection by ID, or all connections with --all.",
    )
    cl.add_argument("id", nargs="?", default=None,
                    help="Connection ID to close (omit for --all)")
    cl.add_argument("--all", action="store_true",
                    help="Close all active connections")
    cl.set_defaults(func=_cmd_close)


def _fmt_bytes(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if abs(n) < 1024:
            return f"{n:.1f} {unit}" if unit != "B" else f"{n} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def _cmd_list(args: argparse.Namespace) -> None:
    as_json = getattr(args, "json", False)
    try:
        client = launcher.get_client()
        data = client.get_connections()
    except ClashError as e:
        error(e.message, code=e.code, as_json=as_json, exit_code=3)

    conns = data.get("connections", [])
    if as_json:
        output(conns[:args.max_conns], as_json=True)
        return

    if not conns:
        output("No active connections")
        return

    lines = [f"  {'ID':<12} {'HOST':<35} {'CHAIN':<18} {'DL':>10} {'UL':>10}"]
    for c in conns[:args.max_conns]:
        cid = c.get("id", "")[:10]
        meta = c.get("metadata", {})
        host = f"{meta.get('host', meta.get('destinationIP','?'))}:{meta.get('destinationPort','')}"
        chains = "→".join(c.get("chains", []))
        dl = _fmt_bytes(c.get("download", 0))
        ul = _fmt_bytes(c.get("upload", 0))
        lines.append(f"  {cid:<12} {host:<35} {chains:<18} {dl:>10} {ul:>10}")
    remaining = len(conns) - args.max_conns
    if remaining > 0:
        lines.append(f"  ({remaining} more connections)")
    output("\n".join(lines))


def _cmd_close(args: argparse.Namespace) -> None:
    as_json = getattr(args, "json", False)
    try:
        client = launcher.get_client()
    except ClashError as e:
        error(e.message, code=e.code, as_json=as_json, exit_code=3)

    if args.all:
        client.close_all_connections()
        if as_json:
            output({"closed": "all"}, as_json=True)
        else:
            output("✓ All connections closed")
    elif args.id:
        client.close_connection(args.id)
        if as_json:
            output({"closed": args.id}, as_json=True)
        else:
            output(f"✓ Connection {args.id} closed")
    else:
        error("Specify a connection ID or --all", code="ERROR", as_json=as_json)
