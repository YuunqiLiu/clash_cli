"""Human-friendly and JSON formatters for CLI output."""

from __future__ import annotations

import json
import sys
from typing import Any


def output(data: Any, *, as_json: bool = False) -> None:
    """Print *data* to stdout.

    When *as_json* is ``True``, wrap *data* in ``{"status": "ok", "data": ...}``
    and emit compact JSON.  Otherwise print *data* as-is (should be a string).
    """
    if as_json:
        print(json.dumps({"status": "ok", "data": data}, ensure_ascii=False))
    else:
        if isinstance(data, str):
            print(data)
        else:
            print(json.dumps(data, indent=2, ensure_ascii=False))


def error(msg: str, code: str = "ERROR", *, as_json: bool = False, exit_code: int = 1) -> None:
    """Print an error and ``sys.exit``."""
    if as_json:
        print(json.dumps({
            "status": "error",
            "error": {"code": code, "message": msg},
        }, ensure_ascii=False))
    else:
        print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(exit_code)
