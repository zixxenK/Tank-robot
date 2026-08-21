<##
.SYNOPSIS
  Synchronize the local checkout to the Rock64, restart the robot service,
  and optionally attach the unified read-only dashboard.

.DESCRIPTION
  This is the normal PC operator entry point for a ready-to-run robot.
  Source/configuration and the ROS host workspace are transferred and built
  on the Rock64 by sync_rock64_safe.ps1. STM32 flashing remains opt-in because
  programming hardware during an unattended dashboard start is not safe.

  Use -FlashFirmware only when the robot is physically secured for a firmware
  update and the ST-Link is connected to the Rock64.
#>
[CmdletBinding()]
param(
  [string]$HostName = "192.168.1.139",
  [string]$UserName = "rock64",
  [string]$RemoteRoot = "/opt/rock64-robot",
  [switch]$FlashFirmware,
  [switch]$NoSync,
  [switch]$NoDashboard,
  [switch]$NoSlam
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path "$PSScriptRoot/../..").Path

function Invoke-ScriptChecked {
  param(
    [Parameter(Mandatory = $true)][string]$Path,
    [Parameter(Mandatory = $true)][string[]]$Arguments
  )

  & $Path @Arguments
  if ($LASTEXITCODE -ne 0) {
    throw "$Path failed with exit code $LASTEXITCODE"
  }
}

if (-not $NoSync) {
  if ($FlashFirmware) {
    Write-Host "[robot_ready] Running full Rock64 build/flash/verification workflow..."
    Invoke-ScriptChecked (Join-Path $repoRoot "scripts/deploy_rock64.ps1") @(
      "-HostName", $HostName,
      "-UserName", $UserName,
      "-RemoteRoot", $RemoteRoot
    )
  } else {
    Write-Host "[robot_ready] Syncing source and rebuilding Rock64 host workspace..."
    Invoke-ScriptChecked (Join-Path $repoRoot "scripts/sync_rock64_safe.ps1") @(
      "-HostName", $HostName,
      "-UserName", $UserName,
      "-RemoteRoot", $RemoteRoot,
      "-RestartService"
    )
  }
}

if (-not $NoDashboard) {
  $dashboardArgs = @(
    "-HostName", $HostName,
    "-UserName", $UserName,
    "-RemotePort", "8765"
  )
  if ($NoSlam) {
    $dashboardArgs += "-NoSlam"
  }

  Write-Host "[robot_ready] Attaching the read-only Foxglove dashboard..."
  Invoke-ScriptChecked (Join-Path $PSScriptRoot "run_dashboard_remote.ps1") $dashboardArgs
}
