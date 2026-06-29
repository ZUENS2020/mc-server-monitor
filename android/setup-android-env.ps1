# J:\AndroidDev\setup-android-env.ps1 - MC Monitor Android dev env on J:
$ErrorActionPreference = "Stop"
$Root = "J:\AndroidDev"
$Sdk  = "$Root\Sdk"
$Jbr  = "J:\AndroidStudio\jbr"
$CmdZip = "$Root\downloads\commandlinetools-win-latest.zip"
$CmdUrl = "https://dl.google.com/android/repository/commandlinetools-win-11076708_latest.zip"

New-Item -ItemType Directory -Force -Path "$Root\downloads", "$Root\projects", "$Root\.gradle", "$Sdk\cmdline-tools" | Out-Null

# 用户环境变量
[Environment]::SetEnvironmentVariable("ANDROID_HOME", $Sdk, "User")
[Environment]::SetEnvironmentVariable("ANDROID_SDK_ROOT", $Sdk, "User")
[Environment]::SetEnvironmentVariable("JAVA_HOME", $Jbr, "User")
[Environment]::SetEnvironmentVariable("GRADLE_USER_HOME", "$Root\.gradle", "User")
[Environment]::SetEnvironmentVariable("ANDROID_AVD_HOME", "$Root\.android\avd", "User")
[Environment]::SetEnvironmentVariable("ANDROID_USER_HOME", "$Root\.android", "User")

$pathUser = [Environment]::GetEnvironmentVariable("Path", "User")
$add = @(
    "$Jbr\bin",
    "$Sdk\platform-tools",
    "$Sdk\emulator",
    "$Sdk\cmdline-tools\latest\bin"
)
foreach ($p in $add) {
    if ($pathUser -notlike "*$p*") { $pathUser = "$pathUser;$p" }
}
[Environment]::SetEnvironmentVariable("Path", $pathUser.TrimStart(";"), "User")

Write-Host "==> Download Android cmdline-tools ..."
if (-not (Test-Path "$Sdk\cmdline-tools\latest\bin\sdkmanager.bat")) {
    Invoke-WebRequest -Uri $CmdUrl -OutFile $CmdZip -UseBasicParsing
    Expand-Archive -Path $CmdZip -DestinationPath "$Root\downloads\cmdline-unpack" -Force
    New-Item -ItemType Directory -Force -Path "$Sdk\cmdline-tools\latest" | Out-Null
    Move-Item "$Root\downloads\cmdline-unpack\cmdline-tools\*" "$Sdk\cmdline-tools\latest\" -Force
}

$env:ANDROID_HOME = $Sdk
$env:JAVA_HOME = $Jbr
$sdkmgr = "$Sdk\cmdline-tools\latest\bin\sdkmanager.bat"

Write-Host "==> Install SDK packages ..."
$packages = @(
    "platform-tools",
    "platforms;android-35",
    "build-tools;35.0.1"
)
foreach ($pkg in $packages) {
    echo y | & $sdkmgr --sdk_root=$Sdk $pkg
}

Write-Host ""
Write-Host "Done. Reopen terminal / Android Studio."
Write-Host "  ANDROID_HOME = $Sdk"
Write-Host "  JAVA_HOME    = $Jbr"
Write-Host "  Project      = $Root\projects\mc-monitor-android"
