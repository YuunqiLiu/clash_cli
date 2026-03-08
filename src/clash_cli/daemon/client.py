"""HTTP client wrapping the mihomo RESTful API."""

from __future__ import annotations

from typing import Any, Optional, Iterator

import requests

from ..errors import ClashError


class MihomoClient:
    """Thin wrapper around the mihomo external-controller REST API.

    Parameters
    ----------
    host : str
        Controller address (default ``127.0.0.1``).
    port : int
        Controller port (e.g. ``9090``).
    secret : str
        Bearer token for ``Authorization`` header.
    timeout : float
        HTTP request timeout in seconds (default ``10``).
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 9090,
        secret: str = "",
        timeout: float = 10,
    ) -> None:
        self.base_url = f"http://{host}:{port}"
        self.timeout = timeout
        self._session = requests.Session()
        self._session.headers.update({
            "Authorization": f"Bearer {secret}",
            "Content-Type": "application/json",
        })

    # ------------------------------------------------------------------
    # Low-level helpers
    # ------------------------------------------------------------------

    def _request(self, method: str, path: str, **kwargs: Any) -> dict:
        kwargs.setdefault("timeout", self.timeout)
        try:
            resp = self._session.request(method, f"{self.base_url}{path}", **kwargs)
        except requests.ConnectionError:
            raise ClashError("MIHOMO_NOT_RUNNING",
                             "mihomo is not running. Run: clash start")
        if resp.status_code == 401:
            raise ClashError("AUTH_FAILED", "Invalid API secret")
        if resp.status_code == 404:
            raise ClashError("NOT_FOUND", f"Resource not found: {path}")
        resp.raise_for_status()
        if not resp.content:
            return {}
        return resp.json()

    def get(self, path: str, params: dict | None = None) -> dict:
        return self._request("GET", path, params=params)

    def put(self, path: str, data: dict | None = None, params: dict | None = None) -> dict:
        return self._request("PUT", path, json=data, params=params)

    def patch(self, path: str, data: dict | None = None) -> dict:
        return self._request("PATCH", path, json=data)

    def delete(self, path: str) -> dict:
        return self._request("DELETE", path)

    def stream_get(self, path: str, params: dict | None = None) -> Iterator[dict]:
        """Yield JSON objects from an SSE / streaming GET endpoint."""
        import json as _json
        try:
            resp = self._session.get(
                f"{self.base_url}{path}",
                params=params,
                stream=True,
                timeout=None,
            )
        except requests.ConnectionError:
            raise ClashError("MIHOMO_NOT_RUNNING",
                             "mihomo is not running. Run: clash start")
        resp.raise_for_status()
        for line in resp.iter_lines(decode_unicode=True):
            if line:
                try:
                    yield _json.loads(line)
                except _json.JSONDecodeError:
                    continue

    # ------------------------------------------------------------------
    # Version / status
    # ------------------------------------------------------------------

    def get_version(self) -> dict:
        return self.get("/version")

    def get_traffic(self) -> dict:
        return self.get("/traffic")

    def get_memory(self) -> dict:
        return self.get("/memory")

    # ------------------------------------------------------------------
    # Configs
    # ------------------------------------------------------------------

    def get_configs(self) -> dict:
        return self.get("/configs")

    def patch_configs(self, data: dict) -> dict:
        return self.patch("/configs", data)

    def reload_configs(self, path: str, force: bool = True) -> dict:
        params = {"force": "true"} if force else {}
        return self.put("/configs", data={"path": path, "payload": ""}, params=params)

    # ------------------------------------------------------------------
    # Proxies
    # ------------------------------------------------------------------

    def get_proxies(self) -> dict:
        return self.get("/proxies")

    def get_proxy(self, name: str) -> dict:
        return self.get(f"/proxies/{requests.utils.quote(name, safe='')}")

    def select_proxy(self, group: str, proxy: str) -> dict:
        return self.put(
            f"/proxies/{requests.utils.quote(group, safe='')}",
            data={"name": proxy},
        )

    def test_proxy_delay(self, name: str, url: str, timeout_ms: int) -> dict:
        return self.get(
            f"/proxies/{requests.utils.quote(name, safe='')}/delay",
            params={"url": url, "timeout": timeout_ms},
        )

    # ------------------------------------------------------------------
    # Groups
    # ------------------------------------------------------------------

    def get_groups(self) -> dict:
        return self.get("/group")

    def test_group_delay(self, name: str, url: str, timeout_ms: int) -> dict:
        return self.get(
            f"/group/{requests.utils.quote(name, safe='')}/delay",
            params={"url": url, "timeout": timeout_ms},
        )

    # ------------------------------------------------------------------
    # Rules
    # ------------------------------------------------------------------

    def get_rules(self) -> dict:
        return self.get("/rules")

    # ------------------------------------------------------------------
    # Connections
    # ------------------------------------------------------------------

    def get_connections(self) -> dict:
        return self.get("/connections")

    def close_connection(self, conn_id: str) -> dict:
        return self.delete(f"/connections/{conn_id}")

    def close_all_connections(self) -> dict:
        return self.delete("/connections")

    # ------------------------------------------------------------------
    # DNS
    # ------------------------------------------------------------------

    def dns_query(self, name: str, qtype: str = "A") -> dict:
        return self.get("/dns/query", params={"name": name, "type": qtype})

    def flush_dns(self) -> dict:
        return self._request("POST", "/cache/dns/flush")

    def flush_fakeip(self) -> dict:
        return self._request("POST", "/cache/fakeip/flush")

    # ------------------------------------------------------------------
    # Logs
    # ------------------------------------------------------------------

    def stream_logs(self, level: str = "info") -> Iterator[dict]:
        """Stream log entries from mihomo."""
        return self.stream_get("/logs", params={"level": level})
