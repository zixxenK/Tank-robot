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
$gitCommit = (& git -C $repoRoot rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0 -or $gitCommit -notmatch '^[0-9a-f]{40}$') {
  throw "Unable to resolve the local Git commit."
}
$gitStatus = (& git -C $repoRoot status --porcelain)
if ($LASTEXITCODE -ne 0) {
  throw "Unable to inspect the local Git checkout."
}
if ($gitStatus) {
  throw "Local checkout is dirty. Commit and push the changes before deployment so the Rock64 can be pinned to the same Git commit.`n$gitStatus"
}
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
      "--exclude=firmware/esp32_sensors/.pio",
      "--exclude=deployment/scripts/archive",
      "--exclude=host_ws/build", "--exclude=host_ws/install", "--exclude=host_ws/log",
      "--exclude=log", "--exclude=*.bin", "--exclude=*.elf", "--exclude=*.hex",
      "--exclude=*.map",
      "deployment", "scripts", "tests", "stubs", "docs", "host_ws/src", "firmware/stm32_chassis", "firmware/esp32_sensors", "Makefile", "pytest.ini", "run_e2e.sh", "run_e2e.ps1"
    )
    Invoke-NativeChecked "tar.exe" $tarArgs
  } finally {
    Pop-Location
  }

  Write-Host "Uploading archive to $target ..."
  Invoke-NativeChecked "scp.exe" @("$archive", "$target`:$remoteArchive")

  $extract = @"
set -e
mkdir -p '$RemoteRoot'
# The archive is the complete source snapshot for these owned trees. Remove
# only those trees first so files deleted locally cannot remain as stale ROS
# nodes, launch files, or firmware sources on the Rock64.
rm -f '$RemoteRoot/.codex-preserved-systemd_config.conf'
if [ -f '$RemoteRoot/deployment/systemd/systemd_config.conf' ]; then
  # Keep the Rock64's machine-local operator configuration across replacement
  # of the tracked deployment tree.
  cp '$RemoteRoot/deployment/systemd/systemd_config.conf' \
     '$RemoteRoot/.codex-preserved-systemd_config.conf'
fi
rm -rf '$RemoteRoot/deployment' '$RemoteRoot/scripts' '$RemoteRoot/tests' '$RemoteRoot/stubs' '$RemoteRoot/docs' '$RemoteRoot/host_ws/src' '$RemoteRoot/firmware/stm32_chassis' '$RemoteRoot/firmware/esp32_sensors'
rm -f '$RemoteRoot/Makefile' '$RemoteRoot/pytest.ini' '$RemoteRoot/run_e2e.sh' '$RemoteRoot/run_e2e.ps1'
tar --no-same-owner -xzf '$remoteArchive' -C '$RemoteRoot'
if [ -f '$RemoteRoot/.codex-preserved-systemd_config.conf' ]; then
  mkdir -p '$RemoteRoot/deployment/systemd'
  cp '$RemoteRoot/.codex-preserved-systemd_config.conf' \
     '$RemoteRoot/deployment/systemd/systemd_config.conf'
fi
rm -f '$RemoteRoot/.codex-preserved-systemd_config.conf'
rm -f '$remoteArchive'
find '$RemoteRoot/scripts' '$RemoteRoot/deployment/scripts' -type f -name '*.sh' -exec chmod 0755 {} +
chmod 0755 '$RemoteRoot/run_e2e.sh'
"@
  Write-Host "Installing source on Rock64 ..."
  Invoke-NativeChecked "ssh.exe" @($target, $extract)

  $gitSync = @"
set -e
git -C '$RemoteRoot' fetch --quiet origin '$gitCommit'
git -C '$RemoteRoot' reset --hard '$gitCommit'
test "`$(git -C '$RemoteRoot' rev-parse HEAD)" = '$gitCommit'
echo "[deploy] Rock64 Git checkout pinned to $gitCommit"
"@
  Write-Host "Pinning Rock64 Git checkout to $gitCommit ..."
  Invoke-NativeChecked "ssh.exe" @($target, $gitSync)

  $remoteCommand = "STM32_BUILD_JOBS=4 FLASH_ESP32=true bash '$RemoteRoot/deployment/scripts/rock64_update_and_flash.sh'"
  Write-Host "Starting mandatory Rock64 host build, STM32 flash, ESP32 flash, and proof workflow. Sudo may prompt for the Rock64 password."
  Invoke-NativeChecked "ssh.exe" @("-tt", $target, $remoteCommand)
} finally {
  if (Test-Path -LiteralPath $archive) { Remove-Item -LiteralPath $archive -Force }
}
