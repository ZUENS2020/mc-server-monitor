# mc-server-monitor

面向 **Paper + Crafty** 的 Minecraft 服务器监控面板：单文件 Python、无第三方依赖、Docker 就绪。

![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)
![License: MIT](https://img.shields.io/badge/license-MIT-green)

## 功能

| 模块 | 说明 |
|---|---|
| MC 状态 | 在线/人数/TPS/MSPT/JVM 内存/难度/视距/隧道 |
| 整机资源 | CPU/内存/磁盘/Swap/网络/负载 |
| 性能趋势 | 近 60 分钟 CPU/内存/负载曲线（PCP 或内置采样） |
| 玩家墙 | RCON 实时 HP/饱食/坐标/维度/经验/模式/护甲 |
| 安全 | CoreProtect 放置速率 + GrimAC 日志 |
| 预警 | 阈值告警、外网/隧道探测、Crafty 自动备份 |
| 详情页 | 指标卡、实时日志、报警历史 |

## 截图

适合 1080p 常驻屏：工业风深色 UI、MC 12 格状态面板、玩家卡片自适应列数。

## 快速开始（Docker）

```bash
git clone https://github.com/ZUENS2020/mc-server-monitor.git
cd mc-server-monitor
cp .env.example .env
# 编辑 .env：Crafty 凭据路径、MC 地址、连接地址等

docker compose up -d --build
open http://localhost:8765
```

### 与 Crafty 同机（host 网络）

MC/RCON/Crafty 在宿主机上时，叠加 host 覆盖文件：

```bash
export HOST_DATA_DIR=~/dashboard/data
export HOST_CRAFTY_DIR=~/crafty
docker compose -f docker-compose.yml -f docker-compose.host.example.yml up -d --build
```

`pid: host` 用于读取宿主机 Java 进程内存；PCP 性能图需挂载 `/var/log/pcp/pmlogger`（可选）。

### 预填性能历史（宿主机有 PCP 时）

```bash
DATA_DIR=./data PCP_LOG_DIR=/var/log/pcp/pmlogger python3 dashboard.py --seed-history
```

## systemd（裸机）

```bash
mkdir -p ~/dashboard/data
cp dashboard.py ~/dashboard/
cp .env.example ~/dashboard/.env
cp dashboard.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now dashboard
```

`dashboard.service` 使用 `%h/dashboard`，适配任意用户主目录。

## 配置

所有配置通过环境变量或 `.env` 注入，详见 [`.env.example`](.env.example)。

| 变量 | 说明 |
|---|---|
| `CRAFTY_URL` / `CRAFTY_CREDS_FILE` | Crafty API 与管理员凭据 |
| `CRAFTY_DATA_DIR` | Crafty 数据目录（含 `servers/`） |
| `MC_HOST` / `MC_RCON_HOST` | 游戏端口与 RCON |
| `MC_CONNECT_ADDRESS` | 面板展示的对外连接地址 |
| `TUNNEL_*` | 可选隧道 TCP/systemd 探测 |
| `ENABLE_*` | 功能开关，`auto` 按文件系统自动检测 |

**仓库内不含任何密码。** RCON 密码从 `server.properties` 读取；Crafty 密码从凭据 JSON 或 `CRAFTY_PASSWORD` 读取。

## API

| 路径 | 说明 |
|---|---|
| `GET /` | Web 面板 |
| `GET /api/status` | 汇总状态 |
| `GET /api/detail?id=mc` | MC 详情 |
| `GET /api/logs?id=mc&tail=N` | 日志 |
| `GET /api/history?range=60` | 性能历史 |
| `GET /api/players` | 玩家实时数据 |
| `GET /api/alertlog?tail=N` | 报警历史 |

## 架构

```
dashboard.py          # 单文件：HTTP 服务 + 采集 + 前端
Dockerfile            # python:3.12-slim
docker-compose.yml    # 通用部署
.env.example          # 配置模板
```

- 采集线程 5s 刷新；玩家 API 2s 轮询；性能图 30s 采样写入 `data/metrics_ring.json`
- Docker 内无 `pmrep` 时自动回退环形缓冲；宿主机可用 `--seed-history` 从 PCP 导入

## 依赖

- **必需**：Python 3.10+、Crafty 管理的 Paper 服务器、RCON 开启
- **可选**：PCP/pmrep（性能图）、CoreProtect、GrimAC

## 安全

面板可读服务器日志与玩家坐标。**公网暴露务必加认证**（Cloudflare Access、反向代理鉴权等）。详见 [SECURITY.md](SECURITY.md)。

## License

[MIT](LICENSE)
