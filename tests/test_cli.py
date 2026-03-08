"""Tests for the main CLI parser and dispatch."""

from __future__ import annotations

import pytest

from clash_cli.cli import build_parser, main


class TestParser:
    def test_version_flag(self, capsys):
        with pytest.raises(SystemExit) as exc:
            main(["--version"])
        assert exc.value.code == 0
        out = capsys.readouterr().out
        assert "0.1.0" in out

    def test_no_command_shows_help(self, capsys):
        with pytest.raises(SystemExit) as exc:
            main([])
        assert exc.value.code == 0

    def test_json_flag_parsed(self):
        parser = build_parser()
        args = parser.parse_args(["--json", "status"])
        assert args.json is True
        assert args.command == "status"

    def test_subcommands_registered(self):
        parser = build_parser()
        # Collect all registered subcommand names
        for action in parser._subparsers._actions:
            if hasattr(action, "_name_parser_map"):
                names = set(action._name_parser_map.keys())
                break
        else:
            names = set()

        expected = {"start", "stop", "restart", "status",
                    "profile", "mode", "proxy", "rule",
                    "conn", "log", "dns"}
        assert expected.issubset(names), f"Missing commands: {expected - names}"

    def test_profile_no_action_shows_help(self, capsys):
        """profile without sub-action should print help, not crash."""
        with pytest.raises(SystemExit) as exc:
            main(["profile"])
        assert exc.value.code == 0
