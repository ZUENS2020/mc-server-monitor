# migrate-android-to-j.ps1
# Run in Admin PowerShell on Win. Moves remaining Android data from C: to J:
$ErrorActionPreference = "Stop"

$CSdk     = "$env:LOCALAPPDATA\Android\Sdk"
$JSdk     = "J:\AndroidDev\Sdk"
$CAndroid = "$env:USERPROFILE\.android"
$JAndroid = "J:\AndroidDev\.android"
$CGradle  = "$env:USERPROFILE\.gradle"
$JGradle  = "J:\AndroidDev\.gradle"

Write-Host "=== Android location audit ==="
@(
    @{ Name = "SDK (C default)"; Path = $CSdk },
    @{ Name = "SDK (J target)";  Path = $JSdk },
    @{ Name = "AVD (C default)"; Path = $CAndroid },
    @{ Name = "AVD (J target)";  Path = $JAndroid },
    @{ Name = "Gradle (C)";      Path = $CGradle },
    @{ Name = "Gradle (J)";      Path = $JGradle },
    @{ Name = "Android Studio";  Path = "J:\AndroidStudio" },
    @{ Name = "MC Monitor app";  Path = "J:\AndroidDev\projects\mc-monitor-android" }
) | ForEach-Object {
    $ok = Test-Path $_.Path
    $size = if ($ok) {
        $s = (Get-ChildItem $_.Path -Recurse -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum
        "{0:N2} GB" -f ($s / 1GB)
    } else { "missing" }
    Write-Host ("{0,-16} {1,-10} {2}" -f $_.Name, $size, $_.Path)
}

Write-Host ""
Write-Host "=== Step 1: merge C SDK extras into J SDK (emulator, system-images) ==="
$mergeDirs = @("emulator", "system-images", "sources", "skins", "extras")
foreach ($d in $mergeDirs) {
    $src = Join-Path $CSdk $d
    $dst = Join-Path $JSdk $d
    if (Test-Path $src) {
        Write-Host "robocopy $d ..."
        robocopy $src $dst /E /XO /R:1 /W:1 /NFL /NDL /NJH /NJS | Out-Null
    }
}

Write-Host "=== Step 2: move AVD to J: ==="
New-Item -ItemType Directory -Force -Path $JAndroid | Out-Null
if (Test-Path $CAndroid) {
    robocopy $CAndroid $JAndroid /E /XO /R:1 /W:1 /NFL /NDL /NJH /NJS | Out-Null
}

Write-Host "=== Step 3: merge Gradle cache to J: ==="
New-Item -ItemType Directory -Force -Path $JGradle | Out-Null
if (Test-Path $CGradle) {
    robocopy $CGradle $JGradle /E /XO /R:1 /W:1 /NFL /NDL /NJH /NJS | Out-Null
}

Write-Host "=== Step 4: set user environment variables ==="
[Environment]::SetEnvironmentVariable("ANDROID_HOME", $JSdk, "User")
[Environment]::SetEnvironmentVariable("ANDROID_SDK_ROOT", $JSdk, "User")
[Environment]::SetEnvironmentVariable("JAVA_HOME", "J:\AndroidStudio\jbr", "User")
[Environment]::SetEnvironmentVariable("GRADLE_USER_HOME", $JGradle, "User")
# AVD .ini files live under .android\avd — not the .android root
[Environment]::SetEnvironmentVariable("ANDROID_AVD_HOME", "$JAndroid\avd", "User")
[Environment]::SetEnvironmentVariable("ANDROID_USER_HOME", $JAndroid, "User")

$pathUser = [Environment]::GetEnvironmentVariable("Path", "User")
$add = @(
    "J:\AndroidStudio\jbr\bin",
    "$JSdk\platform-tools",
    "$JSdk\emulator",
    "$JSdk\cmdline-tools\latest\bin"
)
foreach ($p in $add) {
    if ($pathUser -notlike "*$p*") { $pathUser = "$pathUser;$p" }
}
[Environment]::SetEnvironmentVariable("Path", $pathUser.TrimStart(";"), "User")

Write-Host "=== Step 5: update project local.properties ==="
$localProps = "J:\AndroidDev\projects\mc-monitor-android\local.properties"
"sdk.dir=J\:\\AndroidDev\\Sdk" | Set-Content -Encoding ASCII $localProps

Write-Host ""
Write-Host "Done. Next:"
Write-Host "  1. Restart Android Studio"
Write-Host "  2. Settings -> Android SDK -> SDK path = J:\AndroidDev\Sdk"
Write-Host "  3. Settings -> Appearance -> Android Studio path = J:\AndroidStudio"
Write-Host "  4. After build OK, delete old C SDK to free space:"
Write-Host "       $CSdk"
Write-Host "       $CAndroid  (if copied)"
Write-Host "       $CGradle   (if copied)"
