# Chapter 3: Daemon 架构与状态管理

## 3.1 架构定位

与 wave_reader 不同，clash_cli **不需要独立的 Python Daemon 进程**。

| 对比 | wave_reader | clash_cli |
|------|-------------|-----------|
| 守护对象 | 波形引擎（内存中加载 GB 级文件） | mihomo 进程（自带 HTTP 服务） |
| Python Daemon | 需要（保持文件加载状态） | 不需要 |
| 通信方式 | Unix Socket RPC | HTTP REST（直接调 mihomo） |
| 状态持久化 | Registry 管理多 daemon | state.json 记录单 mihomo 的 pid/port |

**clash_cli 的 daemon 层 = mihomo 进程生命周期管理 + HTTP 客户端封装**

```
clash CLI
  │
  ├── commands/*.py     直接调用 daemon/client.py
  │
  └── daemon/
      ├── launcher.py   管理 mihomo 进程生命周期
      ├── client.py     HTTP 客户端，封装 mihomo REST API
      └── registry.py   ~/.clash_cli/ 状态文件管理
```

---

## 3.2 文件布局

```
~/.clash_cli/
├── state.json              # 主状态文件
├── profiles/               # 配置文件目录
│   ├── home.yaml           # 下载的订阅配置
│   ├── home.meta.json      # 配置元数据
│   ├── work.yaml
│   └── work.meta.json
├── runtime/                # 运行时文件
│   ├── config.yaml         # 当前注入后的配置（传给 mihomo）
│   └── mihomo.log          # mihomo stdout/stderr 日志
└── cache/                  # mihomo 工作目录
    ├── proxies/            # provider 缓存
    └── rules/              # rule-set 缓存
```

### 3.2.1 state.json 格式

```json
{
  "version": 1,
  "pid": 12345,
  "port": 9090,
  "mixed_port": 7890,
  "active_profile": "home",
  "started_at": "2026-03-08T14:30:00Z",
  "log_level": "info",
  "mihomo_binary": "/home/user/.local/bin/mihomo"
}
```

secret **不存储在 state.json 中**，通过 keyring 管理（见 3.5）。

### 3.2.2 profile meta.json 格式

```json
{
  "name": "home",
  "url": "https://example.com/sub?token=xxx",
  "etag": "\"abc123\"",
  "updated_at": "2026-03-08T14:30:00Z",
  "auto_refresh_hours": 24,
  "node_count": 15,
  "group_count": 3
}
```

---

## 3.3 mihomo 进程管理 — launcher.py

### 3.3.1 启动流程

```python
def start(profile_name: str, port: int, mixed_port: int, log_level: str):
    """
    1. 检查 state.json，若 pid 存在且进程活跃 → 报错 ALREADY_RUNNING
    2. 查找 mihomo 二进制（优先 bundled，其次 PATH）
    3. 生成随机 secret（uuid4），存入 keyring
    4. 读取 profiles/<name>.yaml，注入运行时参数：
       - external-controller: 127.0.0.1:<port>
       - secret: <generated>
       - mixed-port: <mixed_port>
       - log-level: <log_level>
       写入 runtime/config.yaml
    5. 启动 mihomo 子进程：
       mihomo -d ~/.clash_cli/cache -f ~/.clash_cli/runtime/config.yaml
       stdout/stderr → runtime/mihomo.log
    6. 轮询 GET /version（最多 10 次，间隔 500ms）
    7. 写入 state.json
    """
```

### 3.3.2 停止流程

```python
def stop():
    """
    1. 读取 state.json 获取 pid
    2. 验证 pid 存活（/proc/<pid>/cmdline 包含 mihomo）
    3. 发送 SIGTERM
    4. 等待退出（最多 5s），超时则 SIGKILL
    5. 清除 state.json
    6. 清除 keyring 中的 secret
    """
```

### 3.3.3 进程状态探测

```python
def is_running() -> bool:
    """
    1. 读取 state.json 的 pid
    2. 检查 /proc/<pid>/cmdline 是否包含 'mihomo'
    3. 可选：尝试 GET /version 确认 HTTP 可达
    """
```

如果 pid 存在但进程已死（stale state），自动清理 state.json。

---

## 3.4 HTTP 客户端 — client.py

### 3.4.1 基本设计

```python
import requests

class MihomoClient:
    def __init__(self, host: str = "127.0.0.1", port: int = None, secret: str = None):
        # port: 从 state.json 读取
        # secret: 从 keyring 读取
        self.base_url = f"http://{host}:{port}"
        self.session = requests.Session()
        self.session.headers["Authorization"] = f"Bearer {secret}"
        self.session.headers["Content-Type"] = "application/json"

    def _request(self, method, path, **kwargs) -> dict:
        """统一请求，处理错误"""
        try:
            resp = self.session.request(method, f"{self.base_url}{path}", **kwargs)
            resp.raise_for_status()
            return resp.json() if resp.content else {}
        except requests.ConnectionError:
            raise ClashError("MIHOMO_NOT_RUNNING", "mihomo is not running")
        except requests.HTTPError as e:
            if e.response.status_code == 401:
                raise ClashError("AUTH_FAILED", "Invalid secret")
            if e.response.status_code == 404:
                raise ClashError("NOT_FOUND", str(e))
            raise ClashError("API_ERROR", str(e))
```

### 3.4.2 便捷方法

```python
    # configs
    def get_configs(self) -> dict: ...
    def patch_configs(self, data: dict) -> dict: ...
    def reload_configs(self, path: str) -> dict: ...

    # proxies
    def get_proxies(self) -> dict: ...
    def get_proxy(self, name: str) -> dict: ...
    def select_proxy(self, group: str, proxy: str) -> dict: ...
    def test_proxy_delay(self, name: str, url: str, timeout: int) -> dict: ...

    # groups
    def get_groups(self) -> dict: ...
    def test_group_delay(self, name: str, url: str, timeout: int) -> dict: ...

    # connections
    def get_connections(self) -> dict: ...
    def close_connection(self, conn_id: str) -> dict: ...
    def close_all_connections(self) -> dict: ...

    # rules
    def get_rules(self) -> dict: ...

    # dns
    def dns_query(self, name: str, qtype: str) -> dict: ...
    def flush_dns(self) -> dict: ...
    def flush_fakeip(self) -> dict: ...

    # meta
    def get_version(self) -> dict: ...
    def get_traffic(self) -> dict: ...
    def get_memory(self) -> dict: ...

    # logs (SSE streaming)
    def stream_logs(self, level: str = None): ...
```

---

## 3.5 Secret 管理 — keyring

使用 Python `keyring` 模块安全存储 mihomo API secret。

```python
import keyring

SERVICE_NAME = "clash_cli"

def store_secret(username: str, secret: str):
    """存储 secret。username 通常为当前 Linux 用户名。"""
    keyring.set_password(SERVICE_NAME, username, secret)

def get_secret(username: str) -> str | None:
    """获取 secret。"""
    return keyring.get_password(SERVICE_NAME, username)

def delete_secret(username: str):
    """删除 secret。"""
    try:
        keyring.delete_password(SERVICE_NAME, username)
    except keyring.errors.PasswordDeleteError:
        pass
```

**Keyring 后端选择（Linux）**：
- 有 GNOME Keyring / KDE Wallet → 自动使用
- 无桌面环境（headless server）→ fallback 到 `keyring.backends.SecretService` 或 `keyrings.alt` 的加密文件后端
- 最差情况下向用户提示安装 `gnome-keyring` 或使用 `--secret` 参数

---

## 3.6 多实例支持

每个 Linux 用户有独立的 `~/.clash_cli/` 目录，因此多用户天然隔离。

**同一用户多实例**：当前设计为一个用户一个 mihomo 实例。如未来需要多实例：
- state.json 改为 state/<instance_name>.json
- 添加 `--instance` 全局选项
- keyring key 加入 instance 前缀

当前版本暂不实现多实例，预留扩展点。

---

## 3.7 mihomo 二进制查找策略

按优先级查找 mihomo 可执行文件：

1. **环境变量** `CLASH_MIHOMO_PATH`（如果用户手动指定）
2. **打包路径**（PyInstaller 打包时 bundle 的 mihomo）：
   `<clash_binary_dir>/mihomo`
3. **系统 PATH**：`which mihomo`
4. **submodule 编译输出**：`<project_root>/submodules/mihomo/mihomo`

找不到则报错：
```
ERROR: mihomo binary not found. Install it or set CLASH_MIHOMO_PATH.
```

---

## 3.8 配置注入策略

mihomo 配置文件由用户的 subscription YAML 为基础，clash_cli 在启动时**注入**以下字段（覆盖用户配置）：

| 字段 | 值 | 原因 |
|------|-----|------|
| `external-controller` | `127.0.0.1:<port>` | 确保 CLI 可连接 |
| `secret` | `<random>` | 安全认证 |
| `mixed-port` | `<mixed_port>` | 统一代理端口 |
| `log-level` | `<level>` | 用户可控 |

**不覆盖的字段**：proxies、proxy-groups、rules、dns 等用户配置全部保留。

注入实现：
```python
import yaml

def inject_runtime_config(profile_path: str, output_path: str, overrides: dict):
    with open(profile_path) as f:
        config = yaml.safe_load(f)
    config.update(overrides)
    with open(output_path, 'w') as f:
        yaml.dump(config, f, allow_unicode=True)
```

---

## 3.9 TODO 清单

| 项目 | 状态 | 说明 |
|------|------|------|
| TUN 模式 | TODO | 需要 root/cap_net_admin，需添加权限提示 |
| 系统代理 | TODO | iptables / env vars（http_proxy 等） |
| 自动刷新 | TODO | cron/systemd timer 定时调用 `profile refresh` |
| Web UI | TODO | 可选集成 metacubexd，通过 `external-ui` 提供 |
