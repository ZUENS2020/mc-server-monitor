# MC Monitor Android

Material Design 3 客户端，对接监控面板 API。

## 界面（v1.2）

| Tab | 内容 |
|-----|------|
| **概览** | 指标网格、服务器状态、玩家预览、活跃预警（可关闭） |
| **玩家** | 实时玩家详情（3s 刷新） |
| **性能** | TPS/MSPT/CPU/内存数值 + 60 分钟趋势图 |
| **控制** | Crafty 启停/重启/备份、服务列表 |

子页面：**预警日志**（按级别筛选）、服务详情、服务日志。

## 构建（仅 Win11 / J 盘）

Mac 不安装 Android SDK，不在 Mac 上构建。在 Win 开发机执行：

```powershell
powershell -ExecutionPolicy Bypass -File J:\AndroidDev\projects\mc-server-monitor\android\build-release.ps1 -Version 1.2.2
```

或手动：

```powershell
cd J:\AndroidDev\projects\mc-server-monitor\android\mc-monitor-android
.\gradlew.bat assembleRelease
# APK: app\build\outputs\apk\release\app-release.apk
```

## Crafty 控制

需服务端 `dashboard.py` 已配置 Crafty 凭据（`.env` / `CRAFTY_CREDS_FILE`）。App 通过 `/api/crafty` 与 `/api/crafty/action` 代理，不在手机端保存 Crafty 密码。
