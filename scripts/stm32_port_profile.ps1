param(
    [ValidateSet('USART1', 'USART3')]
    [string]$HostUart = 'USART1',
    [ValidateSet('Debug', 'Release')]
    [string]$Configuration = 'Release',
    [switch]$Flash
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$firmwareDir = Join-Path $repoRoot 'firmware/stm32_chassis'
$hostUsart = if ($HostUart -eq 'USART1') { '1' } else { '3' }

Write-Host "[profile] Host link: $HostUart"
if ($HostUart -eq 'USART1') {
    Write-Host '[profile] Pins: PA9 TX / PA10 RX (approved custom UART1 connector)'
} else {
    Write-Host '[profile] Pins: PD8 TX / PD9 RX (stock/factory wiring only)'
}

if ($Flash) {
    if ($Configuration -ne 'Release') {
        throw '-Flash requires -Configuration Release.'
    }
    $deployScript = Join-Path $repoRoot 'scripts/deploy_rock64.ps1'
    Write-Host '[profile] Flashing only through the Rock64 build/verify/UART-proof workflow...'
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $deployScript -HostUsart $hostUsart
    if ($LASTEXITCODE -ne 0) { throw "Rock64 deployment failed ($LASTEXITCODE)." }
} else {
    Push-Location $firmwareDir
    try {
        & cmake --preset $Configuration "-DROCK64_HOST_USART=$hostUsart"
        if ($LASTEXITCODE -ne 0) { throw "CMake configure failed ($LASTEXITCODE)." }

        & cmake --build --preset $Configuration --parallel 4
        if ($LASTEXITCODE -ne 0) { throw "Firmware build failed ($LASTEXITCODE)." }
    } finally {
        Pop-Location
    }
}

Write-Host "[profile] Ready: $firmwareDir/build/$Configuration/RosRobotControllerM4.bin"
