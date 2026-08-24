param(
  [string]$Workspace = "host_ws",
  [string]$Distro = "Ubuntu-22.04",
  [string]$RosDistro = "humble",
  [switch]$SymlinkInstall = $true
)

$ErrorActionPreference = "Stop"

function Convert-ToWslPath {
  param([Parameter(Mandatory = $true)][string]$WindowsPath)

  $normalized = $WindowsPath -replace '\\', '/'
  if ($normalized -match '^([A-Za-z]):/(.*)$') {
    $drive = $matches[1].ToLower()
    $rest = $matches[2]
    return "/mnt/$drive/$rest"
  }

  throw "Cannot convert to WSL path: $WindowsPath"
}

$repoRoot = (Resolve-Path "$PSScriptRoot/..").Path
$wsPath = Join-Path $repoRoot $Workspace

if ($RosDistro -ne "humble") {
  throw "Only ROS2 humble is supported by this repository policy. Requested: $RosDistro"
}

if (-not (Test-Path $wsPath)) {
  throw "Workspace not found: $wsPath"
}

$wslList = & wsl.exe -l -q 2>$null
if ($LASTEXITCODE -ne 0) {
  throw "WSL is not available on this machine."
}

$distros = @($wslList | ForEach-Object { $_.Trim() } | Where-Object { $_ -ne "" })
if ($distros -notcontains $Distro) {
  throw "WSL distro '$Distro' not found. Available: $($distros -join ', ')"
}

$wslWorkspace = Convert-ToWslPath -WindowsPath $wsPath
$symlinkArg = ""
if ($SymlinkInstall) {
  $symlinkArg = " --symlink-install"
}

$wslRepo = Convert-ToWslPath -WindowsPath $repoRoot
$bashCmd = "set -e; export HOST_WS_PATH='$wslWorkspace'; source '$wslRepo/deployment/scripts/source_host_ws.sh'; cd \"`$HOST_WS_PATH\"; colcon build$symlinkArg; source '$wslRepo/deployment/scripts/source_host_ws.sh'"

Write-Host "[build_host_wsl] Distro: $Distro"
Write-Host "[build_host_wsl] ROS2  : $RosDistro"
Write-Host "[build_host_wsl] WS    : $wslWorkspace"

& wsl.exe -d $Distro -- bash -lc $bashCmd
if ($LASTEXITCODE -ne 0) {
  throw "WSL host build failed with exit code $LASTEXITCODE"
}

Write-Host "Host workspace build completed via WSL: $wsPath" -ForegroundColor Green
