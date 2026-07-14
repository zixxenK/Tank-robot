param(
  [switch]$Build,
  [switch]$Verify,
  [switch]$Erase
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path "$PSScriptRoot/..").Path
$fwDir = Join-Path $repoRoot "firmware/stm32_chassis"
$buildDir = Join-Path $fwDir "build-ninja"
$elfFile = Join-Path $buildDir "rock64_ranger_fw"

$armBin = "C:\Users\ZIXXE\.platformio\packages\toolchain-gccarmnoneeabi\bin"
$cmakeExe = "C:\Program Files\Microsoft Visual Studio\2022\Community\Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe"
$ninjaExe = "C:\Program Files\Microsoft Visual Studio\2022\Community\Common7\IDE\CommonExtensions\Microsoft\CMake\Ninja\ninja.exe"
$openocdExe = "C:\Users\ZIXXE\.platformio\packages\tool-openocd\bin\openocd.exe"
$stFlashExe = "C:\Users\ZIXXE\.platformio\packages\tool-stm32duino\texane-stlink\st-flash.exe"
$openocdCfg = Join-Path $repoRoot "scripts/openocd_stm32f407.cfg"

if (-not (Test-Path $openocdExe)) {
  throw "OpenOCD not found at $openocdExe"
}

if ($Build) {
  $env:Path = "$armBin;$env:Path"
  Push-Location $fwDir
  try {
    if (Test-Path $buildDir) {
      Remove-Item -Recurse -Force $buildDir
    }
    & $cmakeExe -G Ninja -B build-ninja "-DCMAKE_MAKE_PROGRAM:FILEPATH=$ninjaExe" "-DCMAKE_TOOLCHAIN_FILE:FILEPATH=cmake/stm32_toolchain.cmake"
    & $cmakeExe --build build-ninja
  }
  finally {
    Pop-Location
  }
}

if (-not (Test-Path $elfFile)) {
  throw "Firmware ELF not found at $elfFile. Run with -Build first."
}

$programCmd = ('program "{0}"' -f $elfFile)
if ($Verify) { $programCmd += " verify" }
$programCmd += " reset"

$cmds = @("init")
if ($Erase) {
  $cmds += "stm32f4x mass_erase 0"
}
$cmds += $programCmd

$openocdCmd = ($cmds -join "; ")
$openocdCmd += "; shutdown"

& $openocdExe -f $openocdCfg -c $openocdCmd
$openocdExit = $LASTEXITCODE

if ($openocdExit -eq 0) {
  Write-Host "Flash finished (OpenOCD)." -ForegroundColor Green
  exit 0
}

Write-Warning "OpenOCD failed with exit code $openocdExit. Trying st-flash fallback..."

if (-not (Test-Path $stFlashExe)) {
  throw "st-flash fallback not found at $stFlashExe"
}

$binFile = Join-Path $buildDir "rock64_ranger_fw.bin"
if (-not (Test-Path $binFile)) {
  throw "BIN firmware not found at $binFile"
}

if ($Erase) {
  & $stFlashExe erase
  if ($LASTEXITCODE -ne 0) {
    throw "st-flash erase failed with exit code $LASTEXITCODE"
  }
}

& $stFlashExe --reset write $binFile 0x08000000
if ($LASTEXITCODE -ne 0) {
  throw "st-flash write failed with exit code $LASTEXITCODE"
}

if ($Verify) {
  Write-Warning "st-flash fallback completed. Explicit verify is not implemented in this script."
}

Write-Host "Flash finished (st-flash fallback)." -ForegroundColor Green
