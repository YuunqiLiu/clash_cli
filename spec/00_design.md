# clash_cli 设计文档

## 0. 背景与目标

**clash_cli** 是一个命令行工具，将 Clash Verge（GUI）提供的所有核心操作暴露为 shell 命令，使人和 Agent 都能方便地控制代理行为。

内核与 Clash Verge 完全一致，使用 **mihomo**（即 Meta Clash）。

### 设计参考

复用 `wave_reader` / `cov_reader` 已验证的工程模式：

| 层次 | wave_reader/cov_reader | clash_cli |
|------|----------------------|-----------|
| 入口 | `wave_reader` / `cov_reader` | `clash` |
| 核心引擎 | vcdvcd / snps-urg binding | mihomo 进程（HTTP API） |
| Daemon 层 | Python daemon，按文件复用 | Python daemon，管理 mihomo 进程 |
| CLI 模式 | `subcommand [options]` | 同上 |
| 双输出 | human-friendly / `--json` | 同上 |
| 分发 | PyInstaller 单独二进制 | 同上，打包时 bundle mihomo |
| 构建 | Makefile + Dockerfile.build + GitHub Actions | 同上 |

---

## 1. 项目结构

```
clash_cli/
├── pyproject.toml
├── Makefile
├── Dockerfile.build
├── clash_cli_entry.py          # PyInstaller 入口
├── clash_cli.spec              # PyInstaller spec
├── .github/workflows/
│   └── release.yml
├── spec/                       # 设计文档（本目录）
│   ├── 00_design.md            # 本文件
│   ├── 01_mihomo_api.md        # mihomo REST API 速查
│   ├── 02_cli_interface.md     # 命令详细规范
│   └── 03_daemon_arch.md       # Daemon 架构
├── skill/
│   └── clash-cli/
│       └── SKILL.md
├── src/clash_cli/
│   ├── __init__.py
│   ├── cli.py                  # argparse 入口，dispatch 到 commands/
│   ├── config.py               # 路径、端口、默认值
│   ├── formatters.py           # human / JSON 双模式输出
│   ├── commands/
│   │   ├── __init__.py
│   │   ├── start.py            # start / stop / status
│   │   ├── profile.py          # profile add/list/use/refresh/delete
│   │   ├── mode.py             # mode set/get
│   │   ├── proxy.py            # proxy list/use/test-delay
│   │   ├── rule.py             # rule list
│   │   ├── conn.py             # conn list/close
│   │   └── log.py              # log tail
│   └── daemon/
│       ├── __init__.py
│       ├── launcher.py         # 启动/停止 mihomo 进程
│       ├── client.py           # HTTP 客户端，封装 mihomo REST API
│       └── registry.py         # 本地状态持久化（~/.clash_cli/）
├── submodules/
│   └── mihomo/                 # git submodule: fork of metacubex/mihomo
├── tests/
│   ├── conftest.py
│   └── test_*.py
└── case/
    └── example_config.yaml     # 测试用配置文件
```

---

## 2. 架构概览

```
用户 / Agent
    │
    │  clash <subcommand> [--json]
    ▼
┌─────────────────────────────────┐
│         clash_cli (Python)      │
│  cli.py → commands/*.py         │
│  ↓                              │
│  daemon/client.py               │  HTTP  ┌────────────────────┐
│  (requests to mihomo REST API)  │───────►│  mihomo 进程        │
└─────────────────────────────────┘        │  (子进程，常驻)     │
         │                                 │  127.0.0.1:9090    │
         ▼                                 └────────────────────┘
~/.clash_cli/
  state.json      # mihomo pid、端口、当前 profile 等
  profiles/       # 订阅配置文件缓存
  logs/           # mihomo 日志
```

**关键决策：不需要独立 Python Daemon**

与 wave_reader 不同，mihomo 本身就是一个常驻 HTTP 服务进程。
clash_cli 直接管理 mihomo 的生命周期（start/stop），并在每次命令调用时直接 HTTP 到 mihomo。
~/.clash_cli/state.json 记录 pid 和端口，避免每次重新探测。

---

## 3. 命令设计总览

统一入口：
```
clash <subcommand> [options]
```

全局选项：

| 选项 | 说明 |
|------|------|
| `--json` | JSON 格式输出（Agent 首选） |
| `--host <host>` | mihomo 地址，默认 127.0.0.1 |
| `--port <port>` | mihomo 控制器端口，默认 9090 |
| `--secret <token>` | API 认证 secret |

### 3.1 核心命令表

| 子命令 | 对应 GUI 操作 | mihomo API |
|--------|-------------|-----------|
| `start` | 启动 Core | 启动 mihomo 进程 |
| `stop` | 停止 Core | 终止 mihomo 进程 |
| `status` | 系统托盘状态 | GET /version |
| `profile add <url>` | 订阅 URL 新增配置 | 下载 → 写入 profiles/ |
| `profile list` | 配置列表 | 读 state.json |
| `profile use <name>` | 切换配置 | PUT /configs |
| `profile refresh [name]` | 刷新/更新订阅 | 重新下载 URL → PUT /configs |
| `profile delete <name>` | 删除配置 | 本地删除 |
| `mode set <mode>` | 全局/直连/规则/TUN 模式 | PATCH /configs `{"mode":"..."}` |
| `mode get` | 查看当前模式 | GET /configs |
| `proxy list [group]` | 代理节点列表 | GET /proxies |
| `proxy use <group> <proxy>` | 切换代理 | PUT /proxies/:group |
| `proxy delay [group] [proxy]` | 测速（延迟检测） | GET /proxies/:proxy/delay |
| `rule list` | 规则列表 | GET /rules |
| `conn list` | 活跃连接 | GET /connections |
| `conn close [id\|--all]` | 断开连接 | DELETE /connections/:id |
| `log` | 日志尾随 | GET /logs (SSE) |

### 3.2 模式参数

`mode set` 支持以下模式（与 mihomo 一致）：

| 参数 | 含义 |
|------|------|
| `global` | 全局代理 |
| `direct` | 全局直连 |
| `rule` | 规则匹配（局部代理） |
| `script` | 脚本模式（高级） |

---

## 4. mihomo 子模块

### 4.1 Fork 策略

- Fork `metacubex/mihomo` → `YuunqiLiu/mihomo`
- clash_cli 以 `git submodule` 引用 `submodules/mihomo`
- 构建时从子模块 build mihomo 二进制，bundle 到 PyInstaller 包

### 4.2 引入原因

- 锁定版本，保证 API 兼容性
- 未来可 patch（如自定义 log format、增加 API endpoint）
- 与 wave_reader/cov_reader 的第三方 C 库打包方式一致

### 4.3 构建流程

```
make build
  └── go build ./submodules/mihomo → bin/mihomo
  └── pyinstaller clash_cli.spec   (bundle bin/mihomo)
  └── 输出: dist/clash (单独可执行文件)
```

---

## 5. Profile 管理

profile 是 clash_cli 在 mihomo 之上增加的抽象层（mihomo 本身不持久化多配置）。

```
~/.clash_cli/
├── state.json              # { "active_profile": "home", "pid": 12345, "port": 9090, "secret": "..." }
└── profiles/
    ├── home.yaml           # 从 URL 下载缓存
    ├── home.meta.json      # { "url": "...", "updated_at": "...", "etag": "..." }
    ├── work.yaml
    └── work.meta.json
```

**profile add** 工作流：
1. 下载 URL → `~/.clash_cli/profiles/<name>.yaml`
2. 写入 meta.json（url、etag、时间戳）
3. 可选：`--use` 立即切换

**profile refresh** 工作流：
1. 读取 meta.json 中的 URL
2. 带 `If-None-Match: <etag>` 请求（304 则跳过）
3. 更新 yaml + meta
4. 如果是当前活跃 profile，自动 `PUT /configs` 热重载

---

## 6. 输出格式规范

所有命令必须支持两种输出模式：

### Human 模式（默认）

```
$ clash mode set global
✓ Mode: global

$ clash proxy list --group "Proxy"
Group: Proxy  (selector)
  ✦ HK-01  [12ms]
    SG-02  [45ms]
    JP-03  [timeout]

$ clash proxy delay --group "Proxy"
Testing 3 proxies in group "Proxy"...
  HK-01  ██████░░░░  12ms
  SG-02  ████████░░  45ms
  JP-03  ──────────  timeout
```

### JSON 模式（`--json`）

```json
{
  "status": "ok",
  "data": {
    "group": "Proxy",
    "type": "selector",
    "now": "HK-01",
    "proxies": [
      {"name": "HK-01", "delay_ms": 12},
      {"name": "SG-02", "delay_ms": 45},
      {"name": "JP-03", "delay_ms": null, "error": "timeout"}
    ]
  }
}
```

错误统一格式：
```json
{
  "status": "error",
  "error": {
    "code": "MIHOMO_NOT_RUNNING",
    "message": "mihomo is not running. Run: clash start"
  }
}
```

---

## 7. 工程规范

与 wave_reader/cov_reader 完全对齐：

| 项目 | 规范 |
|------|------|
| Python 版本 | ≥ 3.10 |
| 构建工具 | setuptools + PyInstaller |
| 测试 | pytest |
| CI | GitHub Actions (`release.yml`): build binary → release |
| 容器构建 | Dockerfile.build（与 host 环境隔离） |
| 代码组织 | `src/clash_cli/` layout |
| 配置 | `pyproject.toml` |

---

## 8. 设计决策（已确认）

| # | 问题 | 决策 |
|---|------|------|
| 1 | TUN 模式 | **TODO** — 暂不实现，需要 root/cap，后续版本考虑 |
| 2 | 多实例 | **允许** — 每个用户可独立运行自己的 mihomo 实例（不同端口） |
| 3 | secret 存储 | **keyring** — 使用 Python `keyring` 模块安全存储 mihomo API secret |
| 4 | 平台支持 | **仅 Linux** — 不考虑 macOS/Windows |
| 5 | 系统代理设置 | **TODO** — 暂不纳入 iptables 等系统级配置 |
