"""
Integration tests against a real mihomo instance.

These tests validate that our MihomoClient:
  - Sends correctly-shaped HTTP requests
  - Parses real mihomo responses without KeyError / AttributeError
  - Handles mode switching, proxy selection as mihomo actually behaves

网络影响：零
  所有测试只访问 http://127.0.0.1:19090（REST API）
  不访问 proxy 端口 (17890)，不发任何出站代理流量。

运行方式：
  pytest tests/integration/ -v -m integration
  pytest tests/integration/ -v          # 也可以
  SKIP_INTEGRATION=1 pytest             # 跳过集成测试，只跑 unit tests
"""

from __future__ import annotations

import pytest

from clash_cli.daemon.client import MihomoClient
from clash_cli.errors import ClashError

pytestmark = pytest.mark.integration


# =========================================================================
# 1. Version / Info
# =========================================================================

class TestVersion:
    def test_get_version_returns_semver(self, mihomo: MihomoClient):
        """Version string must look like 'v1.x.y'."""
        result = mihomo.get_version()
        assert "version" in result, f"Unexpected response: {result}"
        ver = result["version"]
        assert ver.startswith("v"), f"Expected version starting with 'v', got: {ver}"
        parts = ver.lstrip("v").split(".")
        assert len(parts) >= 2, f"Not a valid semver: {ver}"

    def test_version_has_meta_field(self, mihomo: MihomoClient):
        """meta field distinguishes mihomo (Meta fork) from vanilla Clash."""
        result = mihomo.get_version()
        # 'meta' key should exist in mihomo responses
        assert "meta" in result, (
            "'meta' key missing — is this actually Mihomo (metacubex fork)? "
            f"Got: {result}"
        )
        assert result["meta"] is True


# =========================================================================
# 2. Configs
# =========================================================================

class TestConfigs:
    def test_get_configs_shape(self, mihomo: MihomoClient):
        """Config response must include all fields we depend on."""
        cfg = mihomo.get_configs()
        required_keys = {"mode", "log-level", "mixed-port", "allow-lan"}
        missing = required_keys - cfg.keys()
        assert not missing, f"Missing config keys: {missing}"

    def test_initial_mode_is_rule(self, mihomo: MihomoClient):
        cfg = mihomo.get_configs()
        assert cfg["mode"] == "rule", f"Expected 'rule', got: {cfg['mode']}"

    def test_patch_mode_global(self, mihomo: MihomoClient):
        mihomo.patch_configs({"mode": "global"})
        cfg = mihomo.get_configs()
        assert cfg["mode"] == "global"

    def test_patch_mode_direct(self, mihomo: MihomoClient):
        mihomo.patch_configs({"mode": "direct"})
        cfg = mihomo.get_configs()
        assert cfg["mode"] == "direct"

    def test_patch_mode_back_to_rule(self, mihomo: MihomoClient):
        """Restore to rule mode — run last to avoid test ordering issues."""
        mihomo.patch_configs({"mode": "rule"})
        cfg = mihomo.get_configs()
        assert cfg["mode"] == "rule"

    def test_controller_port_is_not_exposed_to_lan(self, mihomo: MihomoClient):
        """allow-lan must be False in the test config."""
        cfg = mihomo.get_configs()
        assert cfg.get("allow-lan") is False, (
            "SAFETY CHECK FAILED: allow-lan is True in integration config! "
            "This would expose the proxy to the LAN."
        )


# =========================================================================
# 3. Proxies
# =========================================================================

class TestProxies:
    def test_get_proxies_has_direct_and_reject(self, mihomo: MihomoClient):
        """DIRECT and REJECT are built-in proxies that must always exist."""
        result = mihomo.get_proxies()
        assert "proxies" in result
        proxies = result["proxies"]
        assert "DIRECT" in proxies, f"DIRECT missing. Keys: {list(proxies.keys())}"
        assert "REJECT" in proxies, f"REJECT missing. Keys: {list(proxies.keys())}"

    def test_get_proxies_direct_type(self, mihomo: MihomoClient):
        proxies = mihomo.get_proxies()["proxies"]
        assert proxies["DIRECT"]["type"] == "Direct"

    def test_get_proxies_has_test_nodes(self, mihomo: MihomoClient):
        """Verify our fixture nodes appear in the proxy list."""
        proxies = mihomo.get_proxies()["proxies"]
        assert "test-node-hk" in proxies
        assert "test-node-sg" in proxies

    def test_get_proxy_individual(self, mihomo: MihomoClient):
        result = mihomo.get_proxy("DIRECT")
        assert result.get("name") == "DIRECT"
        assert result.get("type") == "Direct"

    def test_get_proxy_not_found(self, mihomo: MihomoClient):
        with pytest.raises(ClashError) as exc:
            mihomo.get_proxy("this-proxy-does-not-exist")
        assert exc.value.code == "NOT_FOUND"

    def test_select_proxy_in_group(self, mihomo: MihomoClient):
        """Switch the PROXY group to DIRECT, verify the change is reflected."""
        mihomo.select_proxy("PROXY", "DIRECT")
        result = mihomo.get_proxy("PROXY")
        # mihomo returns current selection in 'now'
        assert result.get("now") == "DIRECT", (
            f"Expected 'now' == 'DIRECT', got: {result.get('now')}"
        )


# =========================================================================
# 4. Groups
# =========================================================================

class TestGroups:
    def test_get_groups_returns_dict(self, mihomo: MihomoClient):
        result = mihomo.get_groups()
        assert "proxies" in result

    def test_proxy_group_exists(self, mihomo: MihomoClient):
        result = mihomo.get_groups()
        groups = result["proxies"]
        assert "PROXY" in groups, f"PROXY group missing. Got: {list(groups.keys())}"

    def test_group_has_all_field(self, mihomo: MihomoClient):
        """Each group must have 'all' (the member list)."""
        result = mihomo.get_groups()
        for name, g in result["proxies"].items():
            assert "all" in g, f"Group '{name}' missing 'all' field: {g}"


# =========================================================================
# 5. Rules
# =========================================================================

class TestRules:
    def test_get_rules_has_match(self, mihomo: MihomoClient):
        """MATCH rule must be last — our config always has one."""
        result = mihomo.get_rules()
        assert "rules" in result
        rules = result["rules"]
        assert len(rules) > 0
        last = rules[-1]
        assert last["type"] == "MATCH", f"Last rule should be MATCH, got: {last}"

    def test_rules_have_required_fields(self, mihomo: MihomoClient):
        """Every rule must have type, payload, proxy."""
        rules = mihomo.get_rules()["rules"]
        for r in rules:
            for field in ("type", "payload", "proxy"):
                assert field in r, f"Rule missing '{field}': {r}"


# =========================================================================
# 6. Connections
# =========================================================================

class TestConnections:
    def test_get_connections_shape(self, mihomo: MihomoClient):
        """Even with zero connections, response shape must be correct."""
        result = mihomo.get_connections()
        assert "connections" in result
        assert "downloadTotal" in result
        assert "uploadTotal" in result
        assert isinstance(result["connections"], list)

    def test_close_all_connections_no_error(self, mihomo: MihomoClient):
        """Closing all connections when none exist should not raise."""
        mihomo.close_all_connections()  # idempotent, should not raise


# =========================================================================
# 7. DNS
# =========================================================================

class TestDns:
    def test_flush_dns_cache(self, mihomo: MihomoClient):
        """Flushing DNS cache should succeed (even if DNS is disabled)."""
        # mihomo accepts the POST even with dns.enable: false
        # Should not raise a non-404 error
        try:
            mihomo.flush_dns()
        except ClashError as e:
            if e.code == "NOT_FOUND":
                pytest.skip("DNS cache flush endpoint not available on this build")
            raise

    def test_dns_query_when_disabled_returns_error(self, mihomo: MihomoClient):
        """With dns.enable: false, DNS query should fail gracefully."""
        try:
            result = mihomo.dns_query("example.com", "A")
            # If it succeeds (some builds answer anyway), check shape
            assert "Status" in result or "Answer" in result
        except ClashError:
            # Any ClashError is acceptable when DNS is disabled
            pass


# =========================================================================
# 8. Auth
# =========================================================================

class TestAuth:
    def test_wrong_secret_raises_auth_failed(self, mihomo: MihomoClient):
        """Requests with invalid Bearer token must return 401."""
        bad = MihomoClient(port=19090, secret="wrong-secret", timeout=3)
        with pytest.raises(ClashError) as exc:
            bad.get_version()
        assert exc.value.code == "AUTH_FAILED"

    def test_empty_secret_raises_auth_failed(self, mihomo: MihomoClient):
        no_auth = MihomoClient(port=19090, secret="", timeout=3)
        with pytest.raises(ClashError) as exc:
            no_auth.get_version()
        assert exc.value.code == "AUTH_FAILED"
