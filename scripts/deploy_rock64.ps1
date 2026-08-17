<#!
.SYNOPSIS
  Sync this checkout to the Rock64, then build and flash from the Rock64.

.DESCRIPTION
  Uses the existing SSH key for transport. The remote update script requests
  sudo authentication in the SSH terminal when it stops/restarts systemd.
  The current working tree is sent, including tracked and untracked changes
  under the canonical source directories. Generated build outputs and local
  IDE/cache directories are excluded.
#>
[CmdletBinding()]
param(
  [string]$HostName = "rock64",
  [string]$UserName = "rock64",
  [string]$RemoteRoot = "/opt/rock64-robot"
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$archive = Join-Path ([System.IO.Path]::GetTempPath()) ("tank-robot-{0}.tar.gz" -f ([guid]::NewGuid()))
$remoteArchive = "$RemoteRoot/.codex-deploy.tar.gz"
$target = "$UserName@$HostName"

function Invoke-NativeChecked {
  param([string]$File, [string[]]$Arguments)
  & $File @Arguments
  if ($LASTEXITCODE -ne 0) {
    throw "$File failed with exit code $LASTEXITCODE"
  }
}

try {
  if (-not (Get-Command ssh -ErrorAction SilentlyContinue)) { throw "OpenSSH ssh.exe is required" }
  if (-not (Get-Command scp -ErrorAction SilentlyContinue)) { throw "OpenSSH scp.exe is required" }
  if (-not (Get-Command tar -ErrorAction SilentlyContinue)) { throw "tar.exe is required" }

  Write-Host "Creating source archive from $repoRoot ..."
  Push-Location $repoRoot
  try {
    # Keep the archive limited to the code/configuration used by the Rock64.
    $tarArgs = @(
      "-czf", $archive,
      "--exclude=.git", "--exclude=.idea", "--exclude=.vscode",
      "--exclude=.pytest_cache", "--exclude=firmware/stm32_chassis/build",
      "--exclude=host_ws/build", "--exclude=host_ws/install", "--exclude=host_ws/log",
      "--exclude=log", "--exclude=*.bin", "--exclude=*.elf", "--exclude=*.hex",
      "--exclude=*.map", "--exclude=firmware_backup", "--exclude=ros2_ws_backup",
      "--exclude=microros_agent_ws", "--exclude=uart_ros_bridge",
      "deployment", "scripts", "host_ws/src", "firmware/stm32_chassis", "Makefile"
    )
    Invoke-NativeChecked "tar.exe" $tarArgs
  } finally {
    Pop-Location
  }

  Write-Host "Uploading archive to $target ..."
  Invoke-NativeChecked "scp.exe" @("$archive", "$target`:$remoteArchive")

  $extract = "mkdir -p '$RemoteRoot'; tar -xzf '$remoteArchive' -C '$RemoteRoot'; rm -f '$remoteArchive'"
  Write-Host "Installing source on Rock64 ..."
  Invoke-NativeChecked "ssh.exe" @("-tt", $target, $extract)

  $remoteCommand = "STM32_BUILD_JOBS=4 bash '$RemoteRoot/deployment/scripts/rock64_update_and_flash.sh'"
  Write-Host "Starting mandatory Rock64 build/flash/proof workflow for UART1/USART1. Sudo may prompt for the Rock64 password."
  Invoke-NativeChecked "ssh.exe" @("-tt", $target, $remoteCommand)
} finally {
  if (Test-Path -LiteralPath $archive) { Remove-Item -LiteralPath $archive -Force }
}
