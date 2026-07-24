param(
  [string]$Workspace = "host_ws",
  [string]$Ros2Setup = "",
  [switch]$SymlinkInstall = $true,
  [switch]$UseWslFallback,
  [string]$WslDistro = "Ubuntu-22.04",
  [string]$WslRosDistro = "humble"
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path "$PSScriptRoot/..").Path
$wsPath = Join-Path $repoRoot $Workspace
$py = "C:\Users\ZIXXE\AppData\Local\Programs\Python\Python312\python.exe"

if (-not (Test-Path $wsPath)) {
  throw "Workspace not found: $wsPath"
}

if (-not (Test-Path $py)) {
  throw "Python not found at $py"
}

if (-not $Ros2Setup) {
  $ros2Candidates = @(
    "C:\dev\ros2_humble\local_setup.bat",
    "C:\opt\ros\humble\local_setup.bat"
  )
  $Ros2Setup = $ros2Candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
}

if (-not $Ros2Setup -or -not (Test-Path $Ros2Setup)) {
  if ($UseWslFallback) {
    $fallbackScript = Join-Path $PSScriptRoot "build_host_wsl.ps1"
    if (-not (Test-Path $fallbackScript)) {
      throw "WSL fallback requested but script is missing: $fallbackScript"
    }

    $fallbackArgs = @(
      "-ExecutionPolicy", "Bypass",
      "-File", $fallbackScript,
      "-Workspace", $Workspace,
      "-Distro", $WslDistro,
      "-RosDistro", $WslRosDistro
    )
    if ($SymlinkInstall) {
      $fallbackArgs += "-SymlinkInstall"
    }

    & powershell @fallbackArgs
    if ($LASTEXITCODE -ne 0) {
      throw "WSL fallback build failed with exit code $LASTEXITCODE"
    }
    return
  }

  throw @"
ROS2 local_setup.bat not found.
Install ROS2 on Windows and re-run, or provide explicit path:
  powershell -ExecutionPolicy Bypass -File .\\scripts\\build_host_windows.ps1 -Ros2Setup "C:\\dev\\ros2_humble\\local_setup.bat"

Or enable WSL fallback:
  powershell -ExecutionPolicy Bypass -File .\\scripts\\build_host_windows.ps1 -UseWslFallback
"@
}

$vsDevCmdCandidates = @(
  "C:\Program Files\Microsoft Visual Studio\2022\Community\Common7\Tools\VsDevCmd.bat",
  "C:\Program Files\Microsoft Visual Studio\2022\Professional\Common7\Tools\VsDevCmd.bat",
  "C:\Program Files\Microsoft Visual Studio\2022\Enterprise\Common7\Tools\VsDevCmd.bat"
)

$vsDevCmd = $vsDevCmdCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $vsDevCmd) {
  throw "Could not find VsDevCmd.bat. Install Visual Studio Build Tools or VS 2022."
}

$colconArgs = "build"
if ($SymlinkInstall) {
  $colconArgs += " --symlink-install"
}

Push-Location $wsPath
try {
  $cmd = '"{0}" -no_logo -arch=amd64 && call "{1}" && "{2}" -m colcon {3}' -f $vsDevCmd, $Ros2Setup, $py, $colconArgs
  cmd.exe /d /s /c $cmd
  if ($LASTEXITCODE -ne 0) {
    throw "Host build failed with exit code $LASTEXITCODE"
  }
}
finally {
  Pop-Location
}

Write-Host "Host workspace build completed: $wsPath" -ForegroundColor Green
