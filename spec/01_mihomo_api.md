# Chapter 1: mihomo REST API 速查

clash_cli 通过 mihomo 的 RESTful API 实现所有控制操作。本文档归纳 clash_cli 需要用到的 API。

## 1.1 认证

所有请求需携带 header：
```
Authorization: Bearer ${secret}
```
其中 `secret` 由 mihomo 配置文件的 `secret` 字段指定。

## 1.2 基础信息

| 端点 | 方法 | 说明 | clash_cli 命令 |
|------|------|------|---------------|
| `/version` | GET | 获取版本信息 | `clash status` |
| `/traffic` | GET/WS | 实时流量（kbps） | `clash status --traffic` |
| `/memory` | GET/WS | 实时内存（kb） | `clash status --memory` |
| `/logs` | GET/WS | 实时日志流 | `clash log` |

`/logs` 可选参数：`?level=info|warning|error|debug`

## 1.3 运行配置 — `/configs`

| 端点 | 方法 | 说明 | clash_cli 命令 |
|------|------|------|---------------|
| `/configs` | GET | 获取运行配置 | `clash mode get` |
| `/configs` | PATCH | 修改配置字段 | `clash mode set` |
| `/configs` | PUT | 重载配置文件 | `clash profile use` |
| `/restart` | POST | 重启内核 | `clash restart` |

PATCH 示例（切换模式）：
```json
PATCH /configs
{"mode": "global"}
```

PUT 示例（加载新配置文件）：
```json
PUT /configs?force=true
{"path": "/home/user/.clash_cli/profiles/home.yaml", "payload": ""}
```

## 1.4 代理 — `/proxies`

| 端点 | 方法 | 说明 | clash_cli 命令 |
|------|------|------|---------------|
| `/proxies` | GET | 获取所有代理/组 | `clash proxy list` |
| `/proxies/{name}` | GET | 获取特定代理信息 | `clash proxy list --group X` |
| `/proxies/{name}` | PUT | 选择代理 | `clash proxy use` |
| `/proxies/{name}/delay` | GET | 测试延迟 | `clash proxy delay` |

选择代理示例：
```json
PUT /proxies/Proxy
{"name": "HK-01"}
```

延迟测试参数：
```
GET /proxies/HK-01/delay?url=https://cp.cloudflare.com/generate_204&timeout=5000
```

## 1.5 策略组 — `/group`

| 端点 | 方法 | 说明 | clash_cli 命令 |
|------|------|------|---------------|
| `/group` | GET | 获取所有策略组 | `clash proxy list` |
| `/group/{name}` | GET | 获取特定策略组 | `clash proxy list --group X` |
| `/group/{name}` | DELETE | 清除 fixed 选择 | — |
| `/group/{name}/delay` | GET | 组内全部测速 | `clash proxy delay --group X` |

组延迟测试参数：
```
GET /group/Proxy/delay?url=https://cp.cloudflare.com/generate_204&timeout=5000
```

## 1.6 代理集合 — `/providers/proxies`

| 端点 | 方法 | 说明 | clash_cli 命令 |
|------|------|------|---------------|
| `/providers/proxies` | GET | 获取所有 provider | `clash provider list` |
| `/providers/proxies/{name}` | GET | 获取特定 provider | — |
| `/providers/proxies/{name}` | PUT | 更新 provider | `clash provider update` |
| `/providers/proxies/{name}/healthcheck` | GET | 健康检查 | `clash provider check` |

## 1.7 规则 — `/rules`

| 端点 | 方法 | 说明 | clash_cli 命令 |
|------|------|------|---------------|
| `/rules` | GET | 获取所有规则 | `clash rule list` |
| `/rules/disable` | PATCH | 临时禁用规则 | — |
| `/providers/rules` | GET | 获取所有规则集合 | `clash rule providers` |
| `/providers/rules/{name}` | PUT | 更新规则集合 | — |

## 1.8 连接 — `/connections`

| 端点 | 方法 | 说明 | clash_cli 命令 |
|------|------|------|---------------|
| `/connections` | GET/WS | 获取活跃连接 | `clash conn list` |
| `/connections` | DELETE | 关闭所有连接 | `clash conn close --all` |
| `/connections/{id}` | DELETE | 关闭特定连接 | `clash conn close <id>` |

GET 可选参数：`?interval=1000`（WS 刷新间隔，毫秒）

## 1.9 DNS — `/dns`

| 端点 | 方法 | 说明 | clash_cli 命令 |
|------|------|------|---------------|
| `/dns/query` | GET | DNS 查询 | `clash dns query` |
| `/cache/fakeip/flush` | POST | 清除 fakeip 缓存 | `clash dns flush` |
| `/cache/dns/flush` | POST | 清除 dns 缓存 | `clash dns flush` |

DNS 查询参数：
```
GET /dns/query?name=example.com&type=A
```

## 1.10 API 调用封装规范

clash_cli 中通过 `daemon/client.py` 统一封装 HTTP 调用：

```python
# client.py 伪代码
class MihomoClient:
    def __init__(self, host: str, port: int, secret: str):
        self.base = f"http://{host}:{port}"
        self.headers = {"Authorization": f"Bearer {secret}"}

    def get(self, path: str, params: dict = None) -> dict: ...
    def put(self, path: str, data: dict = None, params: dict = None) -> dict: ...
    def patch(self, path: str, data: dict) -> dict: ...
    def delete(self, path: str) -> dict: ...
    def stream(self, path: str, params: dict = None): ...  # SSE/WS
```

**错误处理**：
- mihomo 未运行 → 连接拒绝 → `MIHOMO_NOT_RUNNING`
- 401 → secret 错误 → `AUTH_FAILED`
- 404 → 代理/组不存在 → `NOT_FOUND`
- 其他 HTTP 错误 → 透传 mihomo 错误信息
