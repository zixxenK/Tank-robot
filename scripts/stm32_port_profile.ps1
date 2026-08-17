param(
    [ValidateSet('USART1')]
    [string]$HostUart = 'USART1',
    [ValidateSet('Debug', 'Release')]
    [string]$Configuration = 'Release',
    [switch]$Flash
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$firmwareDir = Join-Path $repoRoot 'firmware/stm32_chassis'

Write-Host '[profile] Production host link: physical UART1 -> USART1 PA9/PA10'

if ($Flash) {
    if ($Configuration -ne 'Release') {
        throw '-Flash requires -Configuration Release.'
    }
    $deployScript = Join-Path $repoRoot 'scripts/deploy_rock64.ps1'
    Write-Host '[profile] Flashing only through the Rock64 build/verify/UART-proof workflow...'
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $deployScript
    if ($LASTEXITCODE -ne 0) { throw "Rock64 deployment failed ($LASTEXITCODE)." }
} else {
    Push-Location $firmwareDir
    try {
        & cmake --preset $Configuration
        if ($LASTEXITCODE -ne 0) { throw "CMake configure failed ($LASTEXITCODE)." }

        & cmake --build --preset $Configuration --parallel 4
        if ($LASTEXITCODE -ne 0) { throw "Firmware build failed ($LASTEXITCODE)." }
    } finally {
        Pop-Location
    }
}

Write-Host "[profile] Ready: $firmwareDir/build/$Configuration/RosRobotControllerM4.bin"
