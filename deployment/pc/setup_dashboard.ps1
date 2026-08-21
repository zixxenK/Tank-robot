param(
  [string]$Distro = "Ubuntu-22.04"
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
$bashCommand = "cd '$wslRepo' && bash deployment/pc/setup_wsl_dashboard.sh"
Write-Host "[setup_dashboard] WSL distro: $Distro"
Write-Host "[setup_dashboard] Repository:  $wslRepo"
Write-Host "[setup_dashboard] Installing/building the PC dashboard. sudo may ask for the WSL password."

& wsl.exe -d $Distro -- bash -lc $bashCommand
if ($LASTEXITCODE -ne 0) {
  throw "Dashboard setup failed with exit code $LASTEXITCODE"
}

Write-Host "Dashboard setup completed." -ForegroundColor Green
