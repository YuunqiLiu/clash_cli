"""``clash proxy list/use/delay`` — proxy and group operations."""

from __future__ import annotations

import argparse

from ..daemon import launcher
from ..formatters import output, error
from ..errors import ClashError
from ..config import DEFAULT_TEST_URL, DEFAULT_TIMEOUT_MS


def register(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser(
        "proxy",
        help="List, select, or test-delay proxy nodes",
        description=(
            "Inspect proxy groups and nodes, switch the active proxy in a\n"
            "selector group, or measure latency to individual nodes."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    psub = p.add_subparsers(dest="proxy_action", metavar="ACTION")

    # --- list ---
    ls = psub.add_parser(
        "list",
        help="List proxy groups and their nodes",
        description="Show all selector/url-test/fallback groups with current selection and delay.",
    )
    ls.add_argument("--group", "-g", default=None,
                    help="Show only the named group")
    ls.set_defaults(func=_cmd_list)

    # --- use ---
    use = psub.add_parser(
        "use",
        help="Select a proxy within a group",
        description="Send PUT /proxies/<group> to switch the selected node.",
    )
    use.add_argument("group", help="Proxy group name (e.g. 'Proxy')")
    use.add_argument("proxy", help="Proxy node name (e.g. 'HK-01')")
    use.set_defaults(func=_cmd_use)

    # --- delay ---
    dl = psub.add_parser(
        "delay",
        help="Test proxy latency",
        description=(
            "Measure round-trip delay to one or more proxies.\n"
            "Test a single node with --proxy, or all nodes in a group with --group."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    dl.add_argument("--group", "-g", default=None,
                    help="Test all nodes in this group")
    dl.add_argument("--proxy", "-p", default=None,
                    help="Test a single proxy node")
    dl.add_argument("--url", default=DEFAULT_TEST_URL,
                    help=f"URL for delay test (default: {DEFAULT_TEST_URL})")
    dl.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_MS,
                    help=f"Timeout in ms (default: {DEFAULT_TIMEOUT_MS})")
    dl.set_defaults(func=_cmd_delay)


# ------------------------------------------------------------------

def _cmd_list(args: argparse.Namespace) -> None:
    as_json = getattr(args, "json", False)
    try:
        client = launcher.get_client()
        data = client.get_proxies()
    except ClashError as e:
        error(e.message, code=e.code, as_json=as_json, exit_code=3)

    proxies = data.get("proxies", {})
    groups = {k: v for k, v in proxies.items()
              if v.get("type") in ("Selector", "URLTest", "Fallback", "LoadBalance")}

    if args.group:
        if args.group not in groups:
            error(f'Group "{args.group}" not found', code="NOT_FOUND", as_json=as_json)
        groups = {args.group: groups[args.group]}

    if as_json:
        output(groups, as_json=True)
        return

    if not groups:
        output("No proxy groups found")
        return

    lines = []
    for gname, ginfo in sorted(groups.items()):
        now = ginfo.get("now", "")
        gtype = ginfo.get("type", "")
        lines.append(f"Group: {gname} ({gtype})  [current: {now}]")
        for m in ginfo.get("all", []):
            name = m if isinstance(m, str) else m.get("name", "?")
            history = []
            if isinstance(m, dict):
                history = m.get("history", [])
            delay_str = ""
            if history:
                last = history[-1]
                d = last.get("delay", 0)
                delay_str = f"{d}ms" if d > 0 else "timeout"
            marker = "✦" if name == now else " "
            lines.append(f"  {marker} {name:<20} {delay_str}")
        lines.append("")
    output("\n".join(lines).rstrip())


def _cmd_use(args: argparse.Namespace) -> None:
    as_json = getattr(args, "json", False)
    try:
        client = launcher.get_client()
        client.select_proxy(args.group, args.proxy)
    except ClashError as e:
        error(e.message, code=e.code, as_json=as_json)
    if as_json:
        output({"group": args.group, "proxy": args.proxy}, as_json=True)
    else:
        output(f"✓ {args.group}: {args.proxy}")


def _cmd_delay(args: argparse.Namespace) -> None:
    as_json = getattr(args, "json", False)
    try:
        client = launcher.get_client()
    except ClashError as e:
        error(e.message, code=e.code, as_json=as_json, exit_code=3)

    if args.proxy:
        try:
            result = client.test_proxy_delay(args.proxy, args.url, args.timeout)
        except ClashError as e:
            error(e.message, code=e.code, as_json=as_json)
        delay = result.get("delay", 0)
        if as_json:
            output({"proxy": args.proxy, "delay_ms": delay if delay > 0 else None},
                   as_json=True)
        else:
            ds = f"{delay}ms" if delay > 0 else "timeout"
            output(f"{args.proxy}: {ds}")
        return

    group_name = args.group
    if group_name:
        try:
            result = client.test_group_delay(group_name, args.url, args.timeout)
        except ClashError as e:
            error(e.message, code=e.code, as_json=as_json)
        if as_json:
            output(result, as_json=True)
        else:
            lines = [f'Testing proxies in group "{group_name}"...']
            for name, delay in sorted(result.items(), key=lambda x: x[1] if x[1] > 0 else 99999):
                ds = f"{delay}ms" if delay > 0 else "timeout"
                bar = _delay_bar(delay)
                lines.append(f"  {name:<20} {bar}  {ds}")
            output("\n".join(lines))
        return

    error("Specify --group or --proxy", code="ERROR", as_json=as_json)


def _delay_bar(delay_ms: int, width: int = 10) -> str:
    if delay_ms <= 0:
        return "─" * width
    # Map 0-500ms to 0-width filled blocks
    filled = max(1, min(width, int((500 - min(delay_ms, 500)) / 500 * width)))
    return "█" * filled + "░" * (width - filled)
