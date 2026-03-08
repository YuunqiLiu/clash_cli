"""Tests for clash_cli.formatters."""

import json
import sys

from clash_cli.formatters import output, error


def test_output_human(capsys):
    output("hello world")
    captured = capsys.readouterr()
    assert captured.out.strip() == "hello world"


def test_output_json(capsys):
    output({"key": "val"}, as_json=True)
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["status"] == "ok"
    assert data["data"]["key"] == "val"


def test_output_json_list(capsys):
    output([1, 2, 3], as_json=True)
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["status"] == "ok"
    assert data["data"] == [1, 2, 3]


def test_output_non_string_human(capsys):
    """Non-string data in human mode → pretty JSON."""
    output({"a": 1})
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["a"] == 1


def test_error_human(capsys):
    with __import__("pytest").raises(SystemExit) as exc:
        error("something failed")
    assert exc.value.code == 1
    captured = capsys.readouterr()
    assert "something failed" in captured.err


def test_error_json(capsys):
    with __import__("pytest").raises(SystemExit) as exc:
        error("bad input", code="BAD_INPUT", as_json=True, exit_code=2)
    assert exc.value.code == 2
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["status"] == "error"
    assert data["error"]["code"] == "BAD_INPUT"
    assert data["error"]["message"] == "bad input"
