"""``clash rule list`` — display routing rules."""

from __future__ import annotations

import argparse

from ..daemon import launcher
from ..formatters import output, error
from ..errors import ClashError


def register(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser(
        "rule",
        help="List routing rules",
        description="Display the active routing rules loaded by mihomo.",
    )
    psub = p.add_subparsers(dest="rule_action", metavar="ACTION")

    ls = psub.add_parser(
        "list",
        help="List all rules",
        description="Retrieve all rules from GET /rules and display them.",
    )
    ls.add_argument("--max", type=int, default=50, dest="max_rules",
                    help="Maximum rules to show (default: 50)")
    ls.set_defaults(func=_cmd_list)


def _cmd_list(args: argparse.Namespace) -> None:
    as_json = getattr(args, "json", False)
    try:
        client = launcher.get_client()
        data = client.get_rules()
    except ClashError as e:
        error(e.message, code=e.code, as_json=as_json, exit_code=3)

    rules = data.get("rules", [])
    if as_json:
        output(rules[:args.max_rules], as_json=True)
        return

    if not rules:
        output("No rules loaded")
        return

    lines = [f"  {'#':<5} {'TYPE':<18} {'PAYLOAD':<30} PROXY"]
    for i, r in enumerate(rules[:args.max_rules], 1):
        lines.append(
            f"  {i:<5} {r.get('type',''):<18} {r.get('payload',''):<30} {r.get('proxy','')}"
        )
    remaining = len(rules) - args.max_rules
    if remaining > 0:
        lines.append(f"  ... ({remaining} more rules)")
    output("\n".join(lines))
