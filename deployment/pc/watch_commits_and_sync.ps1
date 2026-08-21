<##
.SYNOPSIS
  Watch the local Git branch and deploy each new committed revision to Rock64.

.DESCRIPTION
  This deliberately watches committed revisions only. Automatically copying
  every keystroke to a powered robot and restarting its ROS graph is unsafe.
  Commit a tested change, leave this process running, and the existing safe
  Rock64 sync/build/restart scripts will deploy it.
#>
[CmdletBinding()]
param(
  [string]$HostName = "192.168.1.139",
  [string]$UserName = "rock64",
  [string]$RemoteRoot = "/opt/rock64-robot",
  [ValidateRange(10, 3600)][int]$IntervalSeconds = 30
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path "$PSScriptRoot/../..").Path
$syncScript = Join-Path $repoRoot "deployment/pc/robot_ready.ps1"
$lastRevision = ""

Write-Host "[watch_sync] Watching committed revisions in $repoRoot"
Write-Host "[watch_sync] Press Ctrl+C to stop. Interval: ${IntervalSeconds}s"

while ($true) {
  Push-Location $repoRoot
  try {
    $revision = (& git rev-parse HEAD).Trim()
    $dirty = (& git status --porcelain).Trim()
  } finally {
    Pop-Location
  }

  if ($dirty) {
    Write-Warning "Working tree has uncommitted changes; waiting for a clean commit."
  } elseif ($revision -ne $lastRevision) {
    Write-Host "[watch_sync] New committed revision: $($revision.Substring(0, 8))"
    $readyArgs = @(
      "-HostName", $HostName,
      "-UserName", $UserName,
      "-RemoteRoot", $RemoteRoot,
      "-NoDashboard"
    )
    & $syncScript @readyArgs
    if ($LASTEXITCODE -eq 0) {
      $lastRevision = $revision
      Write-Host "[watch_sync] Rock64 is running $($revision.Substring(0, 8))." -ForegroundColor Green
    } else {
      Write-Warning "Deployment failed; will retry on the next poll."
    }
  }

  Start-Sleep -Seconds $IntervalSeconds
}
