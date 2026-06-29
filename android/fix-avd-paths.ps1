$androidHome = "J:\AndroidDev\.android"
$avdDir = "$androidHome\avd"
$sdk = "J:\AndroidDev\Sdk"
$oldAvd = "C:\Users\22595\.android"
$oldSdk = "C:\Users\22595\AppData\Local\Android\Sdk"

Get-ChildItem $androidHome -Recurse -Include *.ini,*.conf,*.txt -ErrorAction SilentlyContinue | ForEach-Object {
    $c = [IO.File]::ReadAllText($_.FullName)
    $n = $c.Replace($oldAvd, $androidHome).Replace($oldSdk, $sdk)
    if ($n -ne $c) {
        [IO.File]::WriteAllText($_.FullName, $n)
        Write-Host "fixed $($_.FullName)"
    }
}

[Environment]::SetEnvironmentVariable("ANDROID_AVD_HOME", $avdDir, "User")
$env:ANDROID_AVD_HOME = $avdDir
$env:ANDROID_SDK_ROOT = $sdk
& "$sdk\emulator\emulator.exe" -list-avds
