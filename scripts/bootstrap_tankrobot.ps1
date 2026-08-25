<#!
.SYNOPSIS
  Install prerequisites and start Tank Robot from a clean Windows PC.

.DESCRIPTION
  This file is intended to be run by the public one-line bootstrap command:

    irm https://raw.githubusercontent.com/zixxenK/Tank-robot/main/scripts/bootstrap_tankrobot.ps1 | iex

  It installs Git, WSL2, and Docker Desktop when needed, resumes after a
  required reboot, clones/updates main, starts the Compose stack, and opens
  the local operator page.  No credentials are written by this script.
#>
[CmdletBinding()]
param([switch]$Resume)

$ErrorActionPreference = "Stop"
$repoUrl = "https://github.com/zixxenK/Tank-robot.git"
$branch = "main"
$installRoot = Join-Path $env:LOCALAPPDATA "TankRobot"
$repoRoot = Join-Path $installRoot "Tank-robot"
$bootstrapPath = Join-Path $installRoot "bootstrap_tankrobot.ps1"
$runOnceName = "TankRobotBootstrap"

function Write-Step([string]$Message) { Write-Host "[tankrobot] $Message" -ForegroundColor Cyan }
function Fail([string]$Message) { throw "[tankrobot] $Message" }

New-Item -ItemType Directory -Force -Path $installRoot | Out-Null

# A raw GitHub invocation has no stable script path. Save a local copy so the
# same command can continue after WSL requests a Windows restart.
try {
  Invoke-WebRequest -UseBasicParsing -Uri "https://raw.githubusercontent.com/zixxenK/Tank-robot/main/scripts/bootstrap_tankrobot.ps1" -OutFile $bootstrapPath
} catch {
  if (-not (Test-Path -LiteralPath $bootstrapPath)) { Fail "Unable to download the bootstrap script: $($_.Exception.Message)" }
}

function Set-ResumeOnBoot {
  $command = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$bootstrapPath`" -Resume"
  New-ItemProperty -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\RunOnce" -Name $runOnceName -Value $command -PropertyType String -Force | Out-Null
}

function Refresh-Path {
  $machine = [Environment]::GetEnvironmentVariable("Path", "Machine")
  $user = [Environment]::GetEnvironmentVariable("Path", "User")
  $env:Path = "$machine;$user"
}

function Ensure-Winget {
  if (-not (Get-Command winget.exe -ErrorAction SilentlyContinue)) {
    Fail "Windows App Installer (winget) is required. Install it from the Microsoft Store, then rerun this command."
  }
}

function Ensure-Package([string]$Id, [string]$Name) {
  if (Get-Command $Name -ErrorAction SilentlyContinue) { return }
  Ensure-Winget
  Write-Step "Installing $Id..."
  & winget.exe install --id $Id --exact --accept-source-agreements --accept-package-agreements --silent
  if ($LASTEXITCODE -ne 0) { Fail "winget could not install $Id (exit $LASTEXITCODE)." }
  Refresh-Path
}

function Find-FreePort {
  $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, 0)
  try { $listener.Start(); return $listener.LocalEndpoint.Port }
  finally { $listener.Stop() }
}

Ensure-Package "Git.Git" "git.exe"

$wslReady = $true
try { & wsl.exe --status *> $null; if ($LASTEXITCODE -ne 0) { $wslReady = $false } } catch { $wslReady = $false }
if (-not $wslReady) {
  Ensure-Winget
  Write-Step "Installing WSL2. Windows may restart and resume automatically..."
  Set-ResumeOnBoot
  & wsl.exe --install --no-distribution
  if ($LASTEXITCODE -ne 0) { Fail "WSL2 installation failed. Run 'wsl --install' as Administrator and rerun the bootstrapper." }
  shutdown.exe /r /t 10 /c "Tank Robot is installing WSL2 and will resume automatically."
  exit 0
}

if (-not (Get-Command docker.exe -ErrorAction SilentlyContinue)) {
  Ensure-Winget
  Write-Step "Installing Docker Desktop..."
  & winget.exe install --id Docker.DockerDesktop --exact --accept-source-agreements --accept-package-agreements --silent
  if ($LASTEXITCODE -ne 0) { Fail "Docker Desktop installation failed (exit $LASTEXITCODE)." }
  Refresh-Path
}

$dockerDesktop = Join-Path $env:ProgramFiles "Docker\Docker\Docker Desktop.exe"
if (Test-Path -LiteralPath $dockerDesktop) {
  Write-Step "Starting Docker Desktop..."
  Start-Process -FilePath $dockerDesktop -WindowStyle Hidden
}

Write-Step "Waiting for Docker Engine..."
$deadline = (Get-Date).AddMinutes(4)
while ((Get-Date) -lt $deadline) {
  & docker.exe info *> $null
  if ($LASTEXITCODE -eq 0) { break }
  Start-Sleep -Seconds 4
}
& docker.exe info *> $null
if ($LASTEXITCODE -ne 0) { Fail "Docker Engine did not become ready. Start Docker Desktop and rerun the bootstrapper." }

if (-not (Test-Path -LiteralPath (Join-Path $repoRoot ".git"))) {
  Write-Step "Cloning $repoUrl ($branch)..."
  if (Test-Path -LiteralPath $repoRoot) { Remove-Item -LiteralPath $repoRoot -Recurse -Force }
  & git.exe clone --branch $branch $repoUrl $repoRoot
  if ($LASTEXITCODE -ne 0) { Fail "Git clone failed." }
} else {
  $dirty = (& git.exe -C $repoRoot status --porcelain)
  if ($dirty) { Fail "The local checkout has uncommitted changes. Commit or move them before updating main." }
  Write-Step "Updating to the latest $branch..."
  & git.exe -C $repoRoot fetch origin $branch
  if ($LASTEXITCODE -ne 0) { Fail "Git fetch failed." }
  & git.exe -C $repoRoot merge --ff-only "origin/$branch"
  if ($LASTEXITCODE -ne 0) { Fail "The local checkout cannot fast-forward to origin/$branch." }
}

Write-Step "Building and starting Tank Robot containers..."
$env:TANKROBOT_OPERATOR_HOST_PORT = Find-FreePort
$env:TANKROBOT_SIM_FOXGLOVE_PORT = Find-FreePort
$env:TANKROBOT_DIRECT_FOXGLOVE_PORT = Find-FreePort
$env:TANKROBOT_SSH_FOXGLOVE_PORT = Find-FreePort
Push-Location $repoRoot
try {
  & docker.exe compose -p tankrobot up -d --build
  if ($LASTEXITCODE -ne 0) { Fail "Docker Compose failed." }
} finally { Pop-Location }

Start-Sleep -Seconds 3
$operatorUrl = "http://127.0.0.1:$env:TANKROBOT_OPERATOR_HOST_PORT"
Write-Step "Tank Robot is ready: $operatorUrl"
Start-Process $operatorUrl
