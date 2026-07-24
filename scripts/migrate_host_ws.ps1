param(
  [string]$SourceWorkspace = "ros2_ws/src",
  [string]$TargetWorkspace = "host_ws/src"
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path "$PSScriptRoot/..").Path
$src = Join-Path $repoRoot $SourceWorkspace
$dst = Join-Path $repoRoot $TargetWorkspace

if (-not (Test-Path $src)) {
  throw "Source workspace not found: $src"
}

New-Item -ItemType Directory -Force -Path $dst | Out-Null
Write-Host "[migrate_host_ws] Copying packages from $src to $dst"

Get-ChildItem -Path $src -Directory | ForEach-Object {
  $target = Join-Path $dst $_.Name
  if (Test-Path $target) {
    Write-Host "[migrate_host_ws] Skipping existing package: $($_.Name)"
    return
  }

  Copy-Item -Recurse -Force $_.FullName $target
  Write-Host "[migrate_host_ws] Copied: $($_.Name)"
}

Write-Host "[migrate_host_ws] Complete"
