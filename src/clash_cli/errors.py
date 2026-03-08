"""Custom exception hierarchy for clash_cli."""

from __future__ import annotations


class ClashError(Exception):
    """Base exception carrying an error *code* understood by formatters."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
