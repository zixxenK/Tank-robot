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
      "--exclude=deployment/scripts/archive",
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
rm -f '$RemoteRoot/.codex-preserved-systemd_config.conf'
if [ -f '$RemoteRoot/deployment/systemd/systemd_config.conf' ]; then
  # systemd_config.conf is machine-local and is intentionally not in the PC
  # archive. Preserve it while replacing the tracked deployment tree.
  cp '$RemoteRoot/deployment/systemd/systemd_config.conf' \
     '$RemoteRoot/.codex-preserved-systemd_config.conf'
fi
rm -rf '$RemoteRoot/deployment' '$RemoteRoot/scripts' '$RemoteRoot/host_ws/src' '$RemoteRoot/firmware/stm32_chassis' '$RemoteRoot/firmware/esp32_sensors' '$RemoteRoot/Makefile'
tar --no-same-owner -xzf '$remoteArchive' -C '$RemoteRoot'
if [ -f '$RemoteRoot/.codex-preserved-systemd_config.conf' ]; then
  mkdir -p '$RemoteRoot/deployment/systemd'
  cp '$RemoteRoot/.codex-preserved-systemd_config.conf' \
     '$RemoteRoot/deployment/systemd/systemd_config.conf'
fi
rm -f '$RemoteRoot/.codex-preserved-systemd_config.conf'
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
export HOST_WS_PATH='$RemoteRoot/host_ws'
source '$RemoteRoot/deployment/scripts/source_host_ws.sh'
export HOST_WS_PATH='$RemoteRoot/host_ws'
cd "`$HOST_WS_PATH"
rosdep install --from-paths src --ignore-src -r -y
# Generated ROS state is disposable and must be rebuilt from the synchronized
# source tree; otherwise removed packages can survive as stale entry points.
rm -rf '$RemoteRoot/host_ws/build' '$RemoteRoot/host_ws/install' '$RemoteRoot/host_ws/log'
# Build every maintained local package carried by the source archive.  Keeping
# the autonomous packages in this list prevents a clean sync from leaving
# stale or missing installed entry points behind.
colcon build --symlink-install
"@
  Write-Host "Building Rock64 ROS workspace..."
  Invoke-NativeChecked "ssh.exe" @("-tt", $target, $build)

  if ($RestartService) {
    Write-Host "Installing updated service units and restarting acquisition services..."
    # Discovery-server mode is optional. The robot service is the required
    # health signal; apply_systemd.sh owns the optional discovery unit.
    $restart = "sudo bash '$RemoteRoot/deployment/scripts/apply_systemd.sh'; systemctl is-active --quiet rock64-robot.service"
    Invoke-NativeChecked "ssh.exe" @("-tt", $target, $restart)
  } else {
    Write-Host "Build complete. Services were not restarted; rerun with -RestartService when ready."
  }
} finally {
  if (Test-Path -LiteralPath $archive) {
    Remove-Item -LiteralPath $archive -Force
  }
}
