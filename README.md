# Minecraft 服务器监控面板

纯 Python 标准库单文件监控面板，聚焦 **Paper + Crafty** 部署的 Minecraft 服务器：在线/TPS/MSPT/玩家墙/整机资源/性能趋势/作弊检测/报警持久化/预警自动备份。支持 **环境变量配置** 与 **Docker 部署**。

> 早期版本曾聚合监控本机所有 Docker/systemd 服务；现已精简为 MC 服务器 + 可选隧道探测。代码内不含密钥 —— Crafty 密码、RCON 密码均在运行时从挂载文件或环境变量读取。

## 功能

- **MC 状态面板** — 在线/人数/TPS/MSPT/内存/难度/视距/隧道/连接地址
- **整机资源** — CPU/内存/磁盘/Swap/网络/负载（可 `ENABLE_HOST_METRICS=false` 关闭）
- **性能趋势** — PCP `pmrep` 近 60 分钟曲线（`ENABLE_PCP=auto` 自动检测）
- **玩家墙** — RCON 实时血量/饱食/坐标/维度/经验/模式/护甲
- **安全检测** — CoreProtect 放置速率 + GrimAC 日志解析
- **预警** — 阈值 + 外网/隧道连通性探测；触发 Crafty 自动备份
- **详情页** — 指标卡 + 实时日志 + 安全区 + 报警历史

## 快速开始（Docker，推荐）

```bash
cp .env.example .env
# 编辑 .env：至少设置 CRAFTY_CREDS_FILE 或 CRAFTY_PASSWORD、MC_CONNECT_ADDRESS 等

docker compose up -d --build
# 访问 http://localhost:8765
```

### nec 主机（host 网络 + 真实路径）

```bash
cp .env.example .env
docker compose -f docker-compose.yml -f docker-compose.nec.yml up -d --build
```

`docker-compose.nec.yml` 会启用 `network_mode: host`，挂载 `~/crafty` 与 PCP 日志，行为与现有 systemd 部署等价。迁移前可并行跑在不同端口验证。

## 环境变量

| 变量 | 默认 | 说明 |
|---|---|---|
| `DASHBOARD_PORT` | `8765` | HTTP 端口 |
| `DASHBOARD_TITLE` | `MC 监控` | 页面标题 |
| `DATA_DIR` | `/data` | 数据目录（alerts.log 等） |
| `CRAFTY_URL` | `https://127.0.0.1:8443` | Crafty API 地址 |
| `CRAFTY_USERNAME` | `admin` | Crafty 用户名 |
| `CRAFTY_PASSWORD` | — | 明文密码（与凭据文件二选一） |
| `CRAFTY_CREDS_FILE` | `/crafty/config/default-creds.txt` | JSON 凭据文件 |
| `CRAFTY_SERVER_ID` | 自动 | 服务器 UUID，空则取最新 |
| `CRAFTY_DATA_DIR` | `~/crafty` | Crafty 数据根目录 |
| `MC_HOST` / `MC_PORT` | `127.0.0.1` / `25565` | Server List Ping |
| `MC_RCON_HOST` | 同 `MC_HOST` | RCON 地址 |
| `MC_CONNECT_ADDRESS` | — | 面板展示的连接地址 |
| `TUNNEL_*` | 见 `.env.example` | 隧道探测（systemd/tcp/none） |
| `ENABLE_*` | 见 `.env.example` | 功能开关，`auto` 按文件系统自动检测 |

完整列表见 [`.env.example`](.env.example)。

## systemd 部署（裸机）

```bash
mkdir -p ~/dashboard/data
cp dashboard.py ~/dashboard/
cp .env.example ~/dashboard/.env   # 按需修改
cp dashboard.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now dashboard
```

`dashboard.service` 默认直接跑 `dashboard.py`；未设置环境变量时使用与 nec 兼容的内置默认值（`~/crafty`、`frp-top.com:18650` 等）。

## API

| 路径 | 说明 |
|---|---|
| `/` | 面板页面 |
| `/api/status` | 汇总状态 |
| `/api/detail?id=mc` | MC 详情 |
| `/api/logs?id=mc&tail=N` | 日志 |
| `/api/history?range=60` | 性能历史 |
| `/api/players` | 玩家实时数据 |
| `/api/alertlog?tail=N` | 报警历史 |

## 依赖

- Python 3.10+
- 可选：`pmrep`（PCP 性能图）、CoreProtect + GrimAC 插件、Crafty Controller

对外暴露建议套 **Cloudflare Access** 或同类认证。
