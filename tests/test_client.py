"""Tests for clash_cli.daemon.client (MihomoClient)."""

from __future__ import annotations

import json

import pytest
import responses

from clash_cli.daemon.client import MihomoClient
from clash_cli.errors import ClashError


BASE = "http://127.0.0.1:9090"


@pytest.fixture
def client():
    return MihomoClient(port=9090, secret="test-secret", timeout=2)


# ------------------------------------------------------------------
# Low-level
# ------------------------------------------------------------------

class TestRequestHelpers:
    @responses.activate
    def test_get(self, client):
        responses.add(responses.GET, f"{BASE}/version",
                      json={"version": "v1.18.0"}, status=200)
        result = client.get("/version")
        assert result["version"] == "v1.18.0"

    @responses.activate
    def test_put(self, client):
        responses.add(responses.PUT, f"{BASE}/configs",
                      json={}, status=200)
        result = client.put("/configs", data={"path": "/x"})
        assert result == {}

    @responses.activate
    def test_patch(self, client):
        responses.add(responses.PATCH, f"{BASE}/configs",
                      json={}, status=200)
        result = client.patch("/configs", data={"mode": "global"})
        assert result == {}

    @responses.activate
    def test_delete(self, client):
        responses.add(responses.DELETE, f"{BASE}/connections",
                      body=b"", status=204)
        result = client.delete("/connections")
        assert result == {}

    @responses.activate
    def test_auth_error(self, client):
        responses.add(responses.GET, f"{BASE}/version", status=401)
        with pytest.raises(ClashError) as exc:
            client.get("/version")
        assert exc.value.code == "AUTH_FAILED"

    @responses.activate
    def test_not_found(self, client):
        responses.add(responses.GET, f"{BASE}/no-such", status=404)
        with pytest.raises(ClashError) as exc:
            client.get("/no-such")
        assert exc.value.code == "NOT_FOUND"

    @responses.activate
    def test_connection_error(self, client):
        # Use responses to block real HTTP; simulate a ConnectionError
        import requests as _req
        responses.add(
            responses.GET, "http://127.0.0.1:19999/version",
            body=_req.ConnectionError("refused"),
        )
        bad = MihomoClient(port=19999, secret="x", timeout=0.1)
        with pytest.raises(ClashError) as exc:
            bad.get("/version")
        assert exc.value.code == "MIHOMO_NOT_RUNNING"

    @responses.activate
    def test_bearer_header(self, client):
        responses.add(responses.GET, f"{BASE}/version",
                      json={"version": "v1"}, status=200)
        client.get("/version")
        assert responses.calls[0].request.headers["Authorization"] == "Bearer test-secret"


# ------------------------------------------------------------------
# API methods
# ------------------------------------------------------------------

class TestAPIEndpoints:
    @responses.activate
    def test_get_version(self, client):
        responses.add(responses.GET, f"{BASE}/version",
                      json={"version": "v1.18.0"}, status=200)
        assert client.get_version()["version"] == "v1.18.0"

    @responses.activate
    def test_get_configs(self, client):
        responses.add(responses.GET, f"{BASE}/configs",
                      json={"mode": "rule"}, status=200)
        assert client.get_configs()["mode"] == "rule"

    @responses.activate
    def test_patch_configs(self, client):
        responses.add(responses.PATCH, f"{BASE}/configs",
                      json={}, status=200)
        client.patch_configs({"mode": "global"})
        body = json.loads(responses.calls[0].request.body)
        assert body["mode"] == "global"

    @responses.activate
    def test_get_proxies(self, client):
        responses.add(responses.GET, f"{BASE}/proxies",
                      json={"proxies": {"DIRECT": {"type": "Direct"}}}, status=200)
        result = client.get_proxies()
        assert "DIRECT" in result["proxies"]

    @responses.activate
    def test_select_proxy(self, client):
        name = "MyGroup"
        responses.add(responses.PUT, f"{BASE}/proxies/{name}",
                      json={}, status=200)
        client.select_proxy(name, "HK-01")
        body = json.loads(responses.calls[0].request.body)
        assert body["name"] == "HK-01"

    @responses.activate
    def test_test_proxy_delay(self, client):
        responses.add(
            responses.GET,
            f"{BASE}/proxies/HK-01/delay",
            json={"delay": 120},
            status=200,
        )
        result = client.test_proxy_delay("HK-01", "https://cp.cloudflare.com/generate_204", 5000)
        assert result["delay"] == 120

    @responses.activate
    def test_get_rules(self, client):
        responses.add(responses.GET, f"{BASE}/rules",
                      json={"rules": [{"type": "DOMAIN", "payload": "google.com", "proxy": "PROXY"}]},
                      status=200)
        result = client.get_rules()
        assert len(result["rules"]) == 1

    @responses.activate
    def test_get_connections(self, client):
        responses.add(responses.GET, f"{BASE}/connections",
                      json={"connections": [], "downloadTotal": 0, "uploadTotal": 0},
                      status=200)
        result = client.get_connections()
        assert result["connections"] == []

    @responses.activate
    def test_close_all_connections(self, client):
        responses.add(responses.DELETE, f"{BASE}/connections",
                      body=b"", status=204)
        client.close_all_connections()

    @responses.activate
    def test_close_connection(self, client):
        responses.add(responses.DELETE, f"{BASE}/connections/abc123",
                      body=b"", status=204)
        client.close_connection("abc123")

    @responses.activate
    def test_dns_query(self, client):
        responses.add(responses.GET, f"{BASE}/dns/query",
                      json={"Status": 0, "Answer": [{"data": "1.2.3.4"}]},
                      status=200)
        result = client.dns_query("example.com", "A")
        assert result["Answer"][0]["data"] == "1.2.3.4"

    @responses.activate
    def test_flush_dns(self, client):
        responses.add(responses.POST, f"{BASE}/cache/dns/flush",
                      body=b"", status=204)
        client.flush_dns()

    @responses.activate
    def test_get_groups(self, client):
        responses.add(responses.GET, f"{BASE}/group",
                      json={"proxies": {}}, status=200)
        result = client.get_groups()
        assert "proxies" in result
