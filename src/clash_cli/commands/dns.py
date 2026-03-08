"""``clash dns query/flush`` — DNS utilities."""

from __future__ import annotations

import argparse

from ..daemon import launcher
from ..formatters import output, error
from ..errors import ClashError


def register(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser(
        "dns",
        help="DNS query and cache management",
        description="Query DNS through mihomo or flush the DNS cache.",
    )
    dsub = p.add_subparsers(dest="dns_action", metavar="ACTION")

    q = dsub.add_parser(
        "query",
        help="Resolve a domain name via mihomo",
        description="Send a DNS query through mihomo's built-in DNS resolver.",
    )
    q.add_argument("name", help="Domain name to resolve (e.g. google.com)")
    q.add_argument(
        "--type",
        dest="qtype",
        default="A",
        help="DNS record type (default: A)",
    )
    q.set_defaults(func=_cmd_query)

    fl = dsub.add_parser(
        "flush",
        help="Flush mihomo DNS cache",
        description="Clear all cached DNS entries in the running mihomo instance.",
    )
    fl.set_defaults(func=_cmd_flush)


def _cmd_query(args: argparse.Namespace) -> None:
    as_json = getattr(args, "json", False)
    try:
        client = launcher.get_client()
        result = client.dns_query(args.name, args.qtype)
    except ClashError as e:
        error(e.message, code=e.code, as_json=as_json, exit_code=3)
        return

    if as_json:
        output(result, as_json=True)
        return

    # human-friendly output
    status = result.get("Status", -1)
    answers = result.get("Answer", [])
    if status != 0 or not answers:
        output(f"  DNS query for {args.name} ({args.qtype}): NXDOMAIN / no answer")
        return

    lines = [f"  DNS query for {args.name} ({args.qtype}):"]
    for ans in answers:
        name = ans.get("name", args.name).rstrip(".")
        data = ans.get("data", "?")
        ttl = ans.get("TTL", "?")
        lines.append(f"    {name}  →  {data}  (TTL {ttl})")
    output("\n".join(lines))


def _cmd_flush(args: argparse.Namespace) -> None:
    as_json = getattr(args, "json", False)
    try:
        client = launcher.get_client()
        client.flush_dns()
    except ClashError as e:
        error(e.message, code=e.code, as_json=as_json, exit_code=3)
        return

    if as_json:
        output({"flushed": True}, as_json=True)
    else:
        output("✓ DNS cache flushed")
