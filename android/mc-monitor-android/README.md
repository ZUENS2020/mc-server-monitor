# MC Monitor Android

Material Design 3（Jetpack Compose）客户端，对接 [mc-server-monitor](https://github.com/ZUENS2020/mc-server-monitor) 监控面板 API。

## 环境（J 盘 Win11）

```powershell
powershell -ExecutionPolicy Bypass -File J:\AndroidDev\setup-android-env.ps1
```

- SDK：`J:\AndroidDev\Sdk`
- JDK：`J:\AndroidStudio\jbr`
- 项目：`J:\AndroidDev\projects\mc-monitor-android`

## 构建

```powershell
cd J:\AndroidDev\projects\mc-monitor-android
.\gradlew.bat assembleRelease
# APK: app\build\outputs\apk\release\app-release.apk
```

## 界面

| Tab | 功能 |
|-----|------|
| **概览** | MC / 主机状态、性能、活跃预警、关闭预警 |
| **玩家** | `/api/players` 实时列表（3s 刷新）、装备/在线时长/放置速率 |
| **服务** | 服务组列表 → 详情页（指标、CoreProtect、GrimAC）→ 日志 |
| **管理** | 服务器 URL、预警历史、CPU/内存/负载趋势图 |

## API

默认 `https://monitor.zuens2020.work`，可在「管理」页修改。
