<#
.SYNOPSIS
  Sync the current checkout to the Rock64 and rebuild the host ROS workspace.

.DESCRIPTION
  This is the non-flashing deployment path. It transfers source/configuration,
  builds the Rock64 host workspace, and optionally restarts the acquisition
  service. It never programs the STM32 or ESP32.
#>
[CmdletBinding()]
param(
  [string]$HostName = "192.168.1.139",
  [string]$UserName = "rock64",
  [string]$RemoteRoot = "/opt/rock64-robot",
  [switch]$RestartService
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$archive = Join-Path ([System.IO.Path]::GetTempPath()) (
  "tank-robot-sync-{0}.tar.gz" -f ([guid]::NewGuid())
)
$remoteArchive = "$RemoteRoot/.codex-sync.tar.gz"
$target = "$UserName@$HostName"

function Invoke-NativeChecked {
  param([string]$File, [string[]]$Arguments)
  & $File @Arguments
  if ($LASTEXITCODE -ne 0) {
    throw "$File failed with exit code $LASTEXITCODE"
  }
}

try {
  foreach ($command in @("ssh.exe", "scp.exe", "tar.exe")) {
    if (-not (Get-Command $command -ErrorAction SilentlyContinue)) {
      throw "$command is required for Rock64 synchronization"
    }
  }

  Push-Location $repoRoot
  try {
    Write-Host "Creating non-flashing source archive..."
    $tarArgs = @(
      "-czf", $archive,
      "--exclude=.git", "--exclude=.idea", "--exclude=.vscode",
      "--exclude=.pytest_cache", "--exclude=firmware/stm32_chassis/build",
      "--exclude=firmware/esp32_sensors/.pio",
      "--exclude=host_ws/build", "--exclude=host_ws/install",
      "--exclude=host_ws/log", "--exclude=log", "--exclude=*.bin",
      "--exclude=*.elf", "--exclude=*.hex", "--exclude=*.map",
      "deployment", "scripts", "host_ws/src",
      "firmware/stm32_chassis", "firmware/esp32_sensors", "Makefile"
    )
    Invoke-NativeChecked "tar.exe" $tarArgs
  } finally {
    Pop-Location
  }

  Write-Host "Uploading source archive to $target ..."
  Invoke-NativeChecked "scp.exe" @($archive, "$target`:$remoteArchive")

$extract = @"
set -e
mkdir -p '$RemoteRoot'
# Remove only source trees owned by this deployment before extracting.  The
# archive intentionally excludes build/install/log and operator config; not
# deleting these trees leaves stale Python entry points and launch files on
# the Rock64 after a source file is removed locally.
rm -rf '$RemoteRoot/deployment' '$RemoteRoot/scripts' '$RemoteRoot/host_ws/src' '$RemoteRoot/firmware/stm32_chassis' '$RemoteRoot/firmware/esp32_sensors' '$RemoteRoot/Makefile'
tar --no-same-owner -xzf '$remoteArchive' -C '$RemoteRoot'
rm -f '$remoteArchive'
# Windows tar archives do not preserve POSIX executable bits. Restore them for
# every operator-facing shell entry point so a fresh sync cannot leave a
# working checkout with a non-runnable single-command test.
find '$RemoteRoot/scripts' '$RemoteRoot/deployment/scripts' -type f -name '*.sh' -exec chmod 0755 {} +
"@
  Write-Host "Installing source on Rock64 (no hardware programming)..."
  Invoke-NativeChecked "ssh.exe" @($target, $extract)

  $build = @"
set -e
unset AMENT_PREFIX_PATH CMAKE_PREFIX_PATH COLCON_PREFIX_PATH PYTHONPATH ROS_PACKAGE_PATH
source /opt/ros/humble/setup.bash
cd '$RemoteRoot/host_ws'
rosdep install --from-paths src --ignore-src -r -y
colcon build --symlink-install --packages-up-to agent_core robot_bringup robot_drivers robot_teleop robot_audio
"@
  Write-Host "Building Rock64 ROS workspace..."
  Invoke-NativeChecked "ssh.exe" @("-tt", $target, $build)

  if ($RestartService) {
    Write-Host "Installing updated service units and restarting acquisition services..."
    $restart = "sudo bash '$RemoteRoot/deployment/scripts/apply_systemd.sh'; systemctl is-active rock64-fastdds-discovery.service rock64-robot.service"
    Invoke-NativeChecked "ssh.exe" @("-tt", $target, $restart)
  } else {
    Write-Host "Build complete. Services were not restarted; rerun with -RestartService when ready."
  }
} finally {
  if (Test-Path -LiteralPath $archive) {
    Remove-Item -LiteralPath $archive -Force
  }
}
