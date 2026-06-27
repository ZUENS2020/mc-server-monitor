# NEC Minecraft 服务器监控面板

一个**纯 Python 标准库**(无第三方依赖)写的单文件监控面板,跑在自托管服务器上,**聚焦一台 Minecraft(Paper)服务器**的全面状态:在线/玩家/TPS/MSPT/内存/难度/视距/隧道、整机资源、性能趋势、玩家墙(血/食/甲/坐标)、作弊检测与全报警持久化。为 **1080P 屏幕常驻显示**设计,工业风、全直角。

> 早期版本曾聚合监控本机所有 Docker/systemd 服务;现已精简为只监控 MC 服务器 + frpc 隧道(`SERVICES` 字典)。首页是 MC 状态面板,日志只在详情页。

> 本面板是为特定主机(代号 `nec`)定制的:容器名、服务单元名等写在 `SERVICES` 字典里,部署到别的机器时按需改。**代码内不含任何密钥** —— Crafty 管理员密码、RCON 密码均在运行时从本地文件读取。

## 功能

- **服务聚合状态** —— Docker(`docker ps`/`stats`)、systemd 用户服务(`systemctl --user`)、宿主进程(`pgrep`)、TCP 端口探测,绿/黄/红三态。
- **整机总览** —— CPU / 内存 / 磁盘 / Swap / 网络速率 / 负载 / 运行时长,带进度条。
- **性能趋势图** —— 近 60 分钟 CPU% / 内存% / 负载,数据来自 **PCP**(`pmrep` 读 pmlogger 归档,跨午夜合并最近两个归档),纯 SVG 绘制。
- **服务详情页** —— 指标卡 + **实时日志终端**(来源自动选:`docker logs` / `journalctl --user` / `journalctl`(系统)/ Minecraft `latest.log`),日志按级别高亮。
- **主动预警** —— 阈值规则(磁盘/内存/Swap/CPU 持续/负载/容器异常)+ 连通性探测(直连外网 `cloudflare.com`、代理出口 `gstatic/generate_204`、MC 隧道 TCP)。告警条 + 浏览器标签标题提示。
- **预警自动备份** —— 当内存/Swap/CPU/负载/MC 停止等预警触发时,调用 Crafty 备份接口做一次世界存档(3 小时冷却,磁盘/连通性告警不触发)。
- **Minecraft 玩家墙** —— 通过 **RCON**(`list` + `data get entity`)实时读取每个在线玩家的 血量 / 饱食 / 坐标 / 维度 / 经验 / 模式 / 四件护甲等级,带皮肤头像;卡片列数随人数自适应;左侧竖条按状态变色(正常绿 / 危险黄(血或饱食<一半)/ 死亡红闪烁)。在线人数通过 Server List Ping 获取。
- **TPS / MSPT 监控** —— RCON 读服务器 `tps`/`mspt`,玩家墙顶部显示(TPS 按健康度变色),TPS 偏低接入预警。
- **作弊 / 异常检测** —— 读 CoreProtect 数据库统计每玩家**方块放置速率**(排除 `#` 自然源),爆发式放置(疑似打印机 / 自动搭建)在卡上亮黄/红并预警;解析 **GrimAC** 控制台日志,移动类作弊(fly/speed/Baritone)违规同步到预警。需服务器装 CoreProtect + GrimAC 插件。

## 技术

- 单文件 `dashboard.py`,仅用 Python 标准库,HTTP 服务 `http.server`,端口 **8765**。
- 后台线程每 5s 采集,外网探测线程每 25s,玩家数据 1s 缓存供高频(2s)前端轮询。
- 前端纯原生 JS + SVG,无构建、无框架。

## 接口

| 路径 | 说明 |
|---|---|
| `/` | 面板页面 |
| `/api/status` | 服务/整机/告警/玩家 汇总 |
| `/api/detail?id=<服务>` | 单服务详情 |
| `/api/logs?id=<服务>&tail=N` | 日志 |
| `/api/history?range=60` | 性能历史(分钟) |
| `/api/players` | MC 玩家实时状态 |

## 部署

```bash
mkdir -p ~/dashboard && cp dashboard.py ~/dashboard/
cp dashboard.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now dashboard
```

需要:Python 3、`docker`(当前用户可用)、`systemctl --user`(建议开 linger)、可选 `pmrep`(PCP,用于性能图)、目标 MC 服务器开启 RCON(`server.properties`)。对外可经 Cloudflare Tunnel 暴露(纯 HTTP,`localhost:8765`)—— **建议套一层 Cloudflare Access 认证**,因为面板可读各服务日志。

## 依赖的外部约定

- Crafty Controller 数据在 `~/crafty/`,管理员凭据 `~/crafty/config/default-creds.txt`,MC 存档 `~/crafty/servers/<uuid>/`。
- MC 服务器 `server.properties` 开启 `enable-rcon=true` 并设 `rcon.password`(面板自动读取)。
