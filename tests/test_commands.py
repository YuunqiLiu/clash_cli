"""Tests for command modules (mode, proxy, rule, conn, dns)."""

from __future__ import annotations

import argparse
import json
from unittest.mock import patch, MagicMock

import pytest

from clash_cli.errors import ClashError


# ------------------------------------------------------------------
# mode
# ------------------------------------------------------------------

class TestModeGet:
    @patch("clash_cli.commands.mode.launcher")
    def test_mode_get_human(self, mock_launcher, capsys):
        from clash_cli.commands.mode import _cmd_get
        mock_launcher.get_client.return_value.get_configs.return_value = {"mode": "rule"}
        args = argparse.Namespace(json=False)
        _cmd_get(args)
        out = capsys.readouterr().out
        assert "rule" in out

    @patch("clash_cli.commands.mode.launcher")
    def test_mode_get_json(self, mock_launcher, capsys):
        from clash_cli.commands.mode import _cmd_get
        mock_launcher.get_client.return_value.get_configs.return_value = {"mode": "global"}
        args = argparse.Namespace(json=True)
        _cmd_get(args)
        data = json.loads(capsys.readouterr().out)
        assert data["data"]["mode"] == "global"


class TestModeSet:
    @patch("clash_cli.commands.mode.launcher")
    def test_mode_set_valid(self, mock_launcher, capsys):
        from clash_cli.commands.mode import _cmd_set
        mock_launcher.get_client.return_value.patch_configs.return_value = {}
        args = argparse.Namespace(json=False, mode="global")
        _cmd_set(args)
        out = capsys.readouterr().out
        assert "global" in out

    def test_mode_set_invalid_rejected_by_argparse(self):
        """Invalid mode values are rejected by argparse choices at parse time."""
        from clash_cli.cli import build_parser
        parser = build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["mode", "set", "invalid_mode"])


# ------------------------------------------------------------------
# rule
# ------------------------------------------------------------------

class TestRuleList:
    @patch("clash_cli.commands.rule.launcher")
    def test_rule_list_human(self, mock_launcher, capsys):
        from clash_cli.commands.rule import _cmd_list
        mock_launcher.get_client.return_value.get_rules.return_value = {
            "rules": [
                {"type": "DOMAIN-SUFFIX", "payload": "google.com", "proxy": "PROXY"},
                {"type": "MATCH", "payload": "", "proxy": "DIRECT"},
            ]
        }
        args = argparse.Namespace(json=False, max_rules=50)
        _cmd_list(args)
        out = capsys.readouterr().out
        assert "google.com" in out
        assert "DIRECT" in out

    @patch("clash_cli.commands.rule.launcher")
    def test_rule_list_json(self, mock_launcher, capsys):
        from clash_cli.commands.rule import _cmd_list
        mock_launcher.get_client.return_value.get_rules.return_value = {
            "rules": [{"type": "MATCH", "payload": "", "proxy": "DIRECT"}]
        }
        args = argparse.Namespace(json=True, max_rules=50)
        _cmd_list(args)
        data = json.loads(capsys.readouterr().out)
        assert data["status"] == "ok"
        assert len(data["data"]) == 1


# ------------------------------------------------------------------
# conn
# ------------------------------------------------------------------

class TestConnList:
    @patch("clash_cli.commands.conn.launcher")
    def test_conn_list_empty(self, mock_launcher, capsys):
        from clash_cli.commands.conn import _cmd_list
        mock_launcher.get_client.return_value.get_connections.return_value = {
            "connections": []
        }
        args = argparse.Namespace(json=False, max_conns=20)
        _cmd_list(args)
        out = capsys.readouterr().out
        assert "No active" in out

    @patch("clash_cli.commands.conn.launcher")
    def test_conn_list_json(self, mock_launcher, capsys):
        from clash_cli.commands.conn import _cmd_list
        mock_launcher.get_client.return_value.get_connections.return_value = {
            "connections": [{"id": "abc", "metadata": {"host": "x.com", "destinationPort": "443"},
                             "chains": ["PROXY"], "download": 1024, "upload": 512}]
        }
        args = argparse.Namespace(json=True, max_conns=20)
        _cmd_list(args)
        data = json.loads(capsys.readouterr().out)
        assert data["status"] == "ok"
        assert len(data["data"]) == 1


class TestConnClose:
    @patch("clash_cli.commands.conn.launcher")
    def test_close_all(self, mock_launcher, capsys):
        from clash_cli.commands.conn import _cmd_close
        mock_launcher.get_client.return_value.close_all_connections.return_value = {}
        args = argparse.Namespace(json=False, all=True, id=None)
        _cmd_close(args)
        out = capsys.readouterr().out
        assert "All connections closed" in out

    @patch("clash_cli.commands.conn.launcher")
    def test_close_by_id(self, mock_launcher, capsys):
        from clash_cli.commands.conn import _cmd_close
        mock_launcher.get_client.return_value.close_connection.return_value = {}
        args = argparse.Namespace(json=False, all=False, id="abc123")
        _cmd_close(args)
        out = capsys.readouterr().out
        assert "abc123" in out


# ------------------------------------------------------------------
# dns
# ------------------------------------------------------------------

class TestDnsQuery:
    @patch("clash_cli.commands.dns.launcher")
    def test_dns_query_human(self, mock_launcher, capsys):
        from clash_cli.commands.dns import _cmd_query
        mock_launcher.get_client.return_value.dns_query.return_value = {
            "Status": 0,
            "Answer": [{"name": "example.com.", "data": "93.184.216.34", "TTL": 300}],
        }
        args = argparse.Namespace(json=False, name="example.com", qtype="A")
        _cmd_query(args)
        out = capsys.readouterr().out
        assert "93.184.216.34" in out

    @patch("clash_cli.commands.dns.launcher")
    def test_dns_query_json(self, mock_launcher, capsys):
        from clash_cli.commands.dns import _cmd_query
        mock_launcher.get_client.return_value.dns_query.return_value = {
            "Status": 0, "Answer": [{"data": "1.2.3.4"}],
        }
        args = argparse.Namespace(json=True, name="example.com", qtype="A")
        _cmd_query(args)
        data = json.loads(capsys.readouterr().out)
        assert data["status"] == "ok"


class TestDnsFlush:
    @patch("clash_cli.commands.dns.launcher")
    def test_flush_human(self, mock_launcher, capsys):
        from clash_cli.commands.dns import _cmd_flush
        mock_launcher.get_client.return_value.flush_dns.return_value = {}
        args = argparse.Namespace(json=False)
        _cmd_flush(args)
        out = capsys.readouterr().out
        assert "flushed" in out.lower() or "✓" in out


# ------------------------------------------------------------------
# proxy
# ------------------------------------------------------------------

class TestProxyList:
    @patch("clash_cli.commands.proxy.launcher")
    def test_proxy_list_json(self, mock_launcher, capsys):
        from clash_cli.commands.proxy import _cmd_list
        mock_launcher.get_client.return_value.get_proxies.return_value = {
            "proxies": {
                "DIRECT": {"type": "Direct", "name": "DIRECT"},
                "REJECT": {"type": "Reject", "name": "REJECT"},
            }
        }
        args = argparse.Namespace(json=True, group=None)
        _cmd_list(args)
        data = json.loads(capsys.readouterr().out)
        assert data["status"] == "ok"
