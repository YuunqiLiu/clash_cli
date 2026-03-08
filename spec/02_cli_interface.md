# Chapter 2: CLI 命令接口设计

## 2.1 设计理念

与 wave_reader / cov_reader 一致：Agent 和人类使用同一套 CLI，不需要 MCP 层。

| 原则 | 说明 |
|------|------|
| 统一入口 | 所有操作通过 `clash` 一个命令 |
| 双模式输出 | 默认 human-friendly，`--json` 切换为机器可解析 |
| 幂等安全 | `start` 重复调用不会启动多个 mihomo |
| 错误码统一 | JSON 模式下所有错误都有 `code` + `message` |
| 仅 Linux | 不考虑 macOS / Windows 路径和特性 |

---

## 2.2 统一入口

```
clash <subcommand> [options] [arguments]
```

### 全局选项

| 选项 | 默认值 | 说明 |
|------|--------|------|
| `--json` | false | JSON 格式输出 |
| `--host <host>` | 127.0.0.1 | mihomo controller 地址 |
| `--port <port>` | 从 state.json 读取 | mihomo controller 端口 |
| `--secret <token>` | 从 keyring 读取 | API 认证 secret |

### 子命令总览

| 类别 | 子命令 | 描述 | 优先级 |
|------|--------|------|--------|
| 进程 | `start` | 启动 mihomo | P0 |
| 进程 | `stop` | 停止 mihomo | P0 |
| 进程 | `restart` | 重启 mihomo | P1 |
| 进程 | `status` | 查看运行状态 | P0 |
| 配置 | `profile add` | 新增订阅配置 | P0 |
| 配置 | `profile list` | 列出所有配置 | P0 |
| 配置 | `profile use` | 切换活跃配置 | P0 |
| 配置 | `profile refresh` | 刷新/更新订阅 | P0 |
| 配置 | `profile delete` | 删除配置 | P1 |
| 配置 | `profile show` | 查看配置详情 | P2 |
| 模式 | `mode set` | 切换模式 | P0 |
| 模式 | `mode get` | 查看当前模式 | P0 |
| 代理 | `proxy list` | 列出代理/组 | P0 |
| 代理 | `proxy use` | 切换代理 | P0 |
| 代理 | `proxy delay` | 延迟测试 | P0 |
| 规则 | `rule list` | 列出规则 | P2 |
| 连接 | `conn list` | 列出活跃连接 | P1 |
| 连接 | `conn close` | 关闭连接 | P1 |
| 日志 | `log` | 实时日志 | P1 |
| DNS | `dns query` | DNS 查询 | P2 |
| DNS | `dns flush` | 清空 DNS 缓存 | P2 |

---

## 2.3 各子命令详细说明

### 2.3.1 `clash start`

```bash
clash start [options]
```

| 选项 | 默认值 | 说明 |
|------|--------|------|
| `--profile <name>` | 上次使用的 | 使用指定 profile 启动 |
| `--port <port>` | 9090 | controller 端口 |
| `--mixed-port <port>` | 7890 | 混合代理端口 |
| `--log-level <level>` | info | 日志级别 |

**流程**：
1. 读取 `~/.clash_cli/state.json`，检查是否已在运行
2. 如果已运行，提示并退出（或 `--force` 先停再启）
3. 生成随机 secret，通过 keyring 存储
4. 基于选定 profile 生成 mihomo 配置（注入 controller 端口、secret）
5. 启动 mihomo 子进程
6. 等待 `/version` 返回，确认启动成功
7. 写入 state.json（pid、port、profile 名）

**Human 输出**：
```
$ clash start --profile home
✓ mihomo started (pid: 12345)
  Controller:   127.0.0.1:9090
  Mixed proxy:  127.0.0.1:7890
  Profile:      home
  Mode:         rule
  Log level:    info
```

**JSON 输出**：
```json
{
  "status": "ok",
  "data": {
    "pid": 12345,
    "controller": "127.0.0.1:9090",
    "mixed_port": 7890,
    "profile": "home",
    "mode": "rule"
  }
}
```

### 2.3.2 `clash stop`

```bash
clash stop
```

**流程**：
1. 从 state.json 读取 pid
2. 发送 SIGTERM，等待退出
3. 清理 state.json
4. 从 keyring 清除 secret

```
$ clash stop
✓ mihomo stopped (pid: 12345)
```

### 2.3.3 `clash restart`

```bash
clash restart
```

等价于 `clash stop && clash start`（保留当前 profile 和端口设置）。

### 2.3.4 `clash status`

```bash
clash status [--traffic] [--memory]
```

**Human 输出**：
```
$ clash status
● mihomo running (pid: 12345)
  Version:      v1.18.3
  Profile:      home
  Mode:         rule
  Uptime:       2h 15m
  Controller:   127.0.0.1:9090
  Mixed proxy:  127.0.0.1:7890
  Traffic:      ↑ 1.2 MB/s  ↓ 5.8 MB/s
  Memory:       48.2 MB
```

mihomo 未运行时：
```
$ clash status
○ mihomo is not running
```

---

### 2.3.5 `clash profile add`

```bash
clash profile add <name> <url> [options]
```

| 选项 | 默认值 | 说明 |
|------|--------|------|
| `--use` | false | 添加后立即切换为活跃配置 |
| `--interval <hours>` | 24 | 自动刷新间隔（0 为禁用） |

**流程**：
1. 下载 URL → `~/.clash_cli/profiles/<name>.yaml`
2. 解析 yaml，验证格式合法
3. 写入 `<name>.meta.json`（url、etag、时间戳、interval）
4. 如果 `--use`，执行 `profile use <name>`

```
$ clash profile add home "https://example.com/sub?token=xxx" --use
✓ Profile "home" added
  Proxies: 15 nodes in 3 groups
  Updated: 2026-03-08 14:30:00
  Mode:    rule
✓ Switched to profile "home"
```

### 2.3.6 `clash profile list`

```bash
clash profile list
```

```
$ clash profile list
  NAME     NODES  UPDATED              URL
✦ home     15     2026-03-08 14:30     https://example.com/sub?token=***
  work     8      2026-03-07 09:15     https://work.com/sub?token=***
  test     3      2026-03-05 20:00     (local file)
```

`✦` 标记活跃配置。URL 中敏感部分用 `***` 遮蔽。

### 2.3.7 `clash profile use`

```bash
clash profile use <name>
```

**流程**：
1. 验证 `<name>.yaml` 存在
2. 通过 `PUT /configs?force=true` 热加载
3. 更新 state.json 的 `active_profile`

```
$ clash profile use work
✓ Switched to profile "work" (8 nodes)
```

### 2.3.8 `clash profile refresh`

```bash
clash profile refresh [name]
```

不指定 name 则刷新当前活跃 profile。

**流程**：
1. 读取 meta.json 中的 URL
2. 带 `If-None-Match: <etag>` 请求
3. 304 → 无需更新
4. 200 → 覆写 yaml + 更新 meta.json
5. 如果是活跃 profile，自动 `PUT /configs` 热重载

```
$ clash profile refresh
✓ Profile "home" updated (was: 15 nodes → now: 16 nodes)
  New node: US-03
```

### 2.3.9 `clash profile delete`

```bash
clash profile delete <name>
```

禁止删除当前活跃 profile。删除 yaml 和 meta.json。

---

### 2.3.10 `clash mode set`

```bash
clash mode set <mode>
```

| mode 值 | 含义 |
|---------|------|
| `global` | 全局代理 |
| `direct` | 全局直连 |
| `rule` | 规则匹配 |

通过 `PATCH /configs {"mode": "..."}` 实现。

```
$ clash mode set global
✓ Mode: global
```

### 2.3.11 `clash mode get`

```bash
clash mode get
```

通过 `GET /configs` 获取。

```
$ clash mode get
rule
```

JSON 模式：`{"status": "ok", "data": {"mode": "rule"}}`

---

### 2.3.12 `clash proxy list`

```bash
clash proxy list [--group <name>] [--all]
```

| 选项 | 说明 |
|------|------|
| `--group <name>` | 仅显示指定策略组 |
| `--all` | 显示所有节点（含 DIRECT、REJECT 等内置） |

```
$ clash proxy list
Group: Proxy (selector)  [current: HK-01]
  ✦ HK-01         12ms
    HK-02         18ms
    SG-01         45ms
    JP-01         timeout
    US-01         120ms

Group: Auto (url-test)  [current: HK-01]
  ✦ HK-01         12ms
    HK-02         18ms
    SG-01         45ms
```

### 2.3.13 `clash proxy use`

```bash
clash proxy use <group> <proxy>
```

通过 `PUT /proxies/<group> {"name": "<proxy>"}` 实现。

```
$ clash proxy use Proxy SG-01
✓ Proxy: SG-01
```

### 2.3.14 `clash proxy delay`

```bash
clash proxy delay [--group <name>] [--proxy <name>] [--url <url>] [--timeout <ms>]
```

| 选项 | 默认值 | 说明 |
|------|--------|------|
| `--group <name>` | 所有组 | 测试指定组 |
| `--proxy <name>` | — | 测试单个节点 |
| `--url <url>` | `https://cp.cloudflare.com/generate_204` | 测试 URL |
| `--timeout <ms>` | 5000 | 超时时间 |

```
$ clash proxy delay --group Proxy
Testing 5 proxies in group "Proxy"...
  HK-01  ████████░░   12ms
  HK-02  ████████░░   18ms
  SG-01  ██████░░░░   45ms
  US-01  ████░░░░░░  120ms
  JP-01  ──────────  timeout
```

单节点测试：
```
$ clash proxy delay --proxy HK-01
HK-01: 12ms
```

---

### 2.3.15 `clash rule list`

```bash
clash rule list [--max <n>]
```

```
$ clash rule list --max 5
  #   TYPE            PAYLOAD               PROXY
  1   RULE-SET        reject-domain         REJECT
  2   RULE-SET        proxy-domain          Proxy
  3   DOMAIN-SUFFIX   baidu.com             DIRECT
  4   DOMAIN-KEYWORD  google                Proxy
  5   GEOIP           CN                    DIRECT
  ... (235 more rules)
```

### 2.3.16 `clash conn list`

```bash
clash conn list [--sort <field>] [--max <n>]
```

| 选项 | 默认值 | 说明 |
|------|--------|------|
| `--sort` | download | 排序字段：download, upload, time |
| `--max` | 20 | 最大显示条数 |

```
$ clash conn list --max 3
  ID       HOST                      CHAIN          DL         UL        TIME
  abc123   cdn.example.com:443       HK-01→DIRECT   2.1 MB    120 KB    2m30s
  def456   api.github.com:443        SG-01→DIRECT   890 KB    45 KB     1m15s
  ghi789   stream.example.com:443    JP-01→DIRECT   15.3 MB   200 KB    5m00s
  (47 more connections)
```

### 2.3.17 `clash conn close`

```bash
clash conn close [id] [--all]
```

```
$ clash conn close --all
✓ Closed 50 connections

$ clash conn close abc123
✓ Connection abc123 closed
```

### 2.3.18 `clash log`

```bash
clash log [--level <level>]
```

实时跟踪日志（通过 SSE `/logs`）。`Ctrl+C` 退出。

```
$ clash log --level warning
[2026-03-08 14:30:01] [warning] dns timeout for example.com
[2026-03-08 14:30:05] [error] HK-02 connection failed: timeout
```

### 2.3.19 `clash dns query`

```bash
clash dns query <domain> [--type <type>]
```

```
$ clash dns query google.com --type A
google.com  A  142.250.80.14  (12ms)
```

### 2.3.20 `clash dns flush`

```bash
clash dns flush [--fakeip]
```

| 选项 | 说明 |
|------|------|
| `--fakeip` | 同时清除 fakeip 缓存 |

```
$ clash dns flush --fakeip
✓ DNS cache flushed
✓ FakeIP cache flushed
```

---

## 2.4 错误处理规范

### Human 模式

```
$ clash proxy use Proxy NonExistent
ERROR: Proxy "NonExistent" not found in group "Proxy"
```

### JSON 模式

所有错误统一格式：
```json
{
  "status": "error",
  "error": {
    "code": "NOT_FOUND",
    "message": "Proxy \"NonExistent\" not found in group \"Proxy\""
  }
}
```

### 错误码表

| 错误码 | 含义 | 触发场景 |
|--------|------|---------|
| `MIHOMO_NOT_RUNNING` | mihomo 未运行 | 任何需要 mihomo 的命令 |
| `ALREADY_RUNNING` | mihomo 已在运行 | `start` 重复调用 |
| `AUTH_FAILED` | secret 认证失败 | secret 不匹配 |
| `NOT_FOUND` | 资源不存在 | 代理/组/profile 名不存在 |
| `PROFILE_NOT_FOUND` | profile 不存在 | `profile use/refresh/delete` |
| `PROFILE_ACTIVE` | profile 正在使用 | `profile delete` 活跃 profile |
| `DOWNLOAD_FAILED` | 下载失败 | `profile add/refresh` URL 不可达 |
| `INVALID_CONFIG` | 配置格式错误 | profile yaml 解析失败 |
| `INVALID_MODE` | 无效模式 | `mode set` 参数错误 |
| `TIMEOUT` | 操作超时 | `proxy delay` |
| `INTERNAL_ERROR` | 内部错误 | 兜底错误码 |

---

## 2.5 退出码

| 退出码 | 含义 |
|--------|------|
| 0 | 成功 |
| 1 | 一般错误 |
| 2 | 参数解析错误 |
| 3 | mihomo 未运行 |
| 4 | 认证失败 |
