param(
  [switch]$Build,
  [switch]$Verify,
  [switch]$Erase
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path "$PSScriptRoot/..").Path
$fwDir = Join-Path $repoRoot "firmware/stm32_chassis"
$buildDir = Join-Path $fwDir "build/Release"

function Resolve-ToolPath {
  param(
    [Parameter(Mandatory = $true)]
    [string]$Name,
    [string[]]$Candidates = @()
  )

  $cmd = Get-Command $Name -ErrorAction SilentlyContinue
  if ($cmd) {
    return $cmd.Source
  }

  foreach ($candidate in $Candidates) {
    if (Test-Path $candidate) {
      return $candidate
    }
  }

  return $null
}

$cmakeExe = Resolve-ToolPath -Name "cmake" -Candidates @(
  "C:\Program Files\Microsoft Visual Studio\2022\Community\Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe",
  "C:\Program Files\Microsoft Visual Studio\2022\Professional\Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe",
  "C:\Program Files\Microsoft Visual Studio\2022\Enterprise\Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe"
)

$ninjaExe = Resolve-ToolPath -Name "ninja" -Candidates @(
  "C:\Program Files\Microsoft Visual Studio\2022\Community\Common7\IDE\CommonExtensions\Microsoft\CMake\Ninja\ninja.exe",
  "C:\Program Files\Microsoft Visual Studio\2022\Professional\Common7\IDE\CommonExtensions\Microsoft\CMake\Ninja\ninja.exe",
  "C:\Program Files\Microsoft Visual Studio\2022\Enterprise\Common7\IDE\CommonExtensions\Microsoft\CMake\Ninja\ninja.exe"
)

$openocdExe = Resolve-ToolPath -Name "openocd" -Candidates @(
  "C:\Program Files\OpenOCD\bin\openocd.exe",
  "C:\Program Files (x86)\OpenOCD\bin\openocd.exe",
  "C:\ST\STM32CubeCLT\OpenOCD\bin\openocd.exe"
)
$openocdCfg = Join-Path $repoRoot "scripts/openocd_stm32f407.cfg"

if (-not $cmakeExe) {
  throw "cmake not found in PATH"
}

if (-not $openocdExe) {
  throw "openocd.exe not found. Install OpenOCD (or STM32CubeCLT OpenOCD) and re-run."
}

if ($Build) {
  Push-Location $fwDir
  try {
    if ($ninjaExe) {
      $env:Path = "$(Split-Path $ninjaExe);$env:Path"
    }
    & $cmakeExe --preset Release
    & $cmakeExe --build --preset Release -j4
  }
  finally {
    Pop-Location
  }
}

$binFile = Join-Path $buildDir "RosRobotControllerM4.bin"

if (-not (Test-Path $binFile)) {
  throw "Firmware binary not found at $binFile. Run with -Build first."
}

$programCmd = ('program "{0}" 0x8000000' -f $binFile.Replace('\', '/'))
if ($Verify) { $programCmd += " verify" }
$programCmd += " reset"

$cmds = @("transport select swd", "init")
if ($Erase) {
  $cmds += "stm32f4x mass_erase 0"
}
$cmds += $programCmd

$openocdCmd = ($cmds -join "; ")
$openocdCmd += "; shutdown"

& $openocdExe -f $openocdCfg -c $openocdCmd
$openocdExit = $LASTEXITCODE

if ($openocdExit -eq 0) {
  Write-Host "Flash finished (ST-Link/OpenOCD)." -ForegroundColor Green
  exit 0
}

throw "OpenOCD failed with exit code $openocdExit"
