"""``clash mode get/set`` — switch proxy mode (global / direct / rule)."""

from __future__ import annotations

import argparse

from ..daemon import launcher
from ..formatters import output, error
from ..errors import ClashError

VALID_MODES = ("global", "direct", "rule")


def register(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser(
        "mode",
        help="Get or set the proxy mode (global / direct / rule)",
        description=(
            "Control how traffic is routed:\n"
            "  global  — all traffic goes through the selected proxy\n"
            "  direct  — all traffic bypasses proxies\n"
            "  rule    — traffic is matched against rules to decide proxy or direct"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    msub = p.add_subparsers(dest="mode_action", metavar="ACTION")

    get_p = msub.add_parser("get", help="Print the current mode")
    get_p.set_defaults(func=_cmd_get)

    set_p = msub.add_parser(
        "set",
        help="Change the proxy mode",
        description="Change mode via PATCH /configs. Takes effect immediately.",
    )
    set_p.add_argument("mode", choices=VALID_MODES,
                       help="Target mode: global | direct | rule")
    set_p.set_defaults(func=_cmd_set)


def _cmd_get(args: argparse.Namespace) -> None:
    as_json = getattr(args, "json", False)
    try:
        client = launcher.get_client()
        cfg = client.get_configs()
    except ClashError as e:
        error(e.message, code=e.code, as_json=as_json, exit_code=3)

    mode = cfg.get("mode", "unknown")
    if as_json:
        output({"mode": mode}, as_json=True)
    else:
        output(mode)


def _cmd_set(args: argparse.Namespace) -> None:
    as_json = getattr(args, "json", False)
    mode = args.mode
    try:
        client = launcher.get_client()
        client.patch_configs({"mode": mode})
    except ClashError as e:
        error(e.message, code=e.code, as_json=as_json, exit_code=3)

    if as_json:
        output({"mode": mode}, as_json=True)
    else:
        output(f"✓ Mode: {mode}")
