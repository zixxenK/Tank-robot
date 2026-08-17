<#!
.SYNOPSIS
  Build, flash, launch, and safe-test one STM32 UART profile from the Rock64.

.DESCRIPTION
  This is the operator-facing wrapper.  The actual compiler, ST-Link, SWD
  launcher, readback verification, and UART proof all run on the Rock64.
  UART1 is the normal physical USB-C connector used by the Rock64 host.
#>
[CmdletBinding()]
param(
  [ValidateSet("UART1", "FACTORY_USART3")]
  [string]$Port = "UART1",
  [string]$HostName = "rock64",
  [string]$UserName = "rock64",
  [string]$RemoteRoot = "/opt/rock64-robot"
)

$ErrorActionPreference = "Stop"
$hostUsart = if ($Port -eq "UART1") { "1" } else { "3" }
$deployScript = Join-Path $PSScriptRoot "deploy_rock64.ps1"

if ($Port -eq "UART1") {
  Write-Host "[reflash] UART1 connector -> USART1 PA9/PA10 (approved custom host link)"
} else {
  Write-Host "[reflash] factory PD8/PD9 -> USART3 (reference profile; not product UART1)"
}

& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $deployScript `
  -HostName $HostName -UserName $UserName -RemoteRoot $RemoteRoot -HostUsart $hostUsart
if ($LASTEXITCODE -ne 0) {
  throw "Rock64 reflash failed ($LASTEXITCODE)."
}
