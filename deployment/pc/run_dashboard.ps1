param(
  [string]$Distro = "Ubuntu-22.04",
  [string[]]$LaunchArguments = @()
)

$ErrorActionPreference = "Stop"

function Convert-ToWslPath {
  param([Parameter(Mandatory = $true)][string]$WindowsPath)

  $normalized = $WindowsPath -replace '\\', '/'
  if ($normalized -match '^([A-Za-z]):/(.*)$') {
    return "/mnt/$($matches[1].ToLower())/$($matches[2])"
  }
  throw "Cannot convert Windows path to WSL path: $WindowsPath"
}

function Quote-BashArgument([string]$Value) {
  return "'" + ($Value -replace "'", "'\\''") + "'"
}

$repoRoot = (Resolve-Path "$PSScriptRoot/../..").Path
$available = @(& wsl.exe -l -q 2>$null | ForEach-Object { $_.Trim() } |
  Where-Object { $_ })
if ($LASTEXITCODE -ne 0) {
  throw "WSL is not available on this PC."
}
if ($available -notcontains $Distro) {
  throw "WSL distro '$Distro' was not found. Available: $($available -join ', ')"
}

$wslRepo = Convert-ToWslPath $repoRoot
$argsText = ($LaunchArguments | ForEach-Object { Quote-BashArgument $_ }) -join ' '
$bashCommand = "cd '$wslRepo' && exec bash deployment/pc/run_dashboard.sh $argsText"
Write-Host "[run_dashboard] WSL distro: $Distro"
Write-Host "[run_dashboard] Foxglove endpoint will be ws://127.0.0.1:8765"

& wsl.exe -d $Distro -- bash -lc $bashCommand
exit $LASTEXITCODE
