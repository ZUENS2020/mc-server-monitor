# Win11 only — build MC Monitor APK and publish GitHub Release.
# Usage: powershell -ExecutionPolicy Bypass -File J:\AndroidDev\projects\mc-server-monitor\android\build-release.ps1 -Version 1.2.2

param(
    [string]$Version = "1.2.2",
    [string]$RepoRoot = "J:\AndroidDev\projects\mc-server-monitor",
    [string]$StudioRoot = "J:\AndroidDev\projects\mc-monitor-android"
)

$ErrorActionPreference = "Stop"

$env:ANDROID_HOME = "J:\AndroidDev\Sdk"
$env:ANDROID_SDK_ROOT = "J:\AndroidDev\Sdk"
$env:ANDROID_AVD_HOME = "J:\AndroidDev\.android\avd"
$env:GRADLE_USER_HOME = "J:\AndroidDev\.gradle"
$env:JAVA_HOME = "J:\AndroidStudio\jbr"

$apkName = "mc-monitor-v$Version.apk"
$distDir = Join-Path $RepoRoot "dist"
$appDir = Join-Path $RepoRoot "android\mc-monitor-android"

Write-Host "=== Pull latest ==="
Set-Location $RepoRoot
git pull origin main

Write-Host "=== Sync android source to Studio project ==="
if (Test-Path $StudioRoot) {
    robocopy $appDir $StudioRoot /MIR /XD .gradle build app\build .idea /NFL /NDL /NJH /NJS | Out-Null
    $buildRoot = $StudioRoot
} else {
    $buildRoot = $appDir
}

$localProps = Join-Path $buildRoot "local.properties"
Set-Content -Path $localProps -Value "sdk.dir=J:/AndroidDev/Sdk" -Encoding ASCII -NoNewline

Write-Host "=== Build release APK ==="
Set-Location $buildRoot
& .\gradlew.bat assembleRelease

$apkSrc = Join-Path $buildRoot "app\build\outputs\apk\release\app-release.apk"
if (-not (Test-Path $apkSrc)) { throw "APK not found: $apkSrc" }

New-Item -ItemType Directory -Force -Path $distDir | Out-Null
$apkDst = Join-Path $distDir $apkName
Copy-Item -Force $apkSrc $apkDst
Write-Host "APK: $apkDst"

$tag = "v$Version"
$notes = @"
## MC Monitor Android v$Version

### 变更
- 概览 / 控制 Tab 职责分离（预警只在概览，控制页专注 Crafty + 服务）
- 趋势图固定 60 分钟，移除时长切换
- 实时指标 3×2 等宽网格对齐
- Crafty 接口兼容与轮询刷新
- 服务端已部署 ``/api/crafty``（NEC dashboard）

### 安装
下载 ``$apkName``，允许未知来源后安装。

### 构建环境
仅 Win11 + J: 盘 Android SDK，Mac 不构建。
"@

Write-Host "=== GitHub Release $tag ==="
Set-Location $RepoRoot
$existing = gh release view $tag 2>$null
if ($LASTEXITCODE -eq 0) {
    gh release upload $tag $apkDst --clobber
} else {
    gh release create $tag $apkDst --title "MC Monitor Android v$Version" --notes $notes
}

Write-Host "Done: https://github.com/ZUENS2020/mc-server-monitor/releases/tag/$tag"
