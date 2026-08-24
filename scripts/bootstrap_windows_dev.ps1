param(
  [switch]$PersistUserPath
)

$ErrorActionPreference = "Stop"

function Add-SessionPath {
  param([Parameter(Mandatory = $true)][string]$Dir)

  if (-not (Test-Path $Dir)) {
    return
  }

  $parts = $env:PATH -split ';'
  if ($parts -contains $Dir) {
    return
  }

  $env:PATH = "$Dir;$env:PATH"
}

function Add-UserPath {
  param([Parameter(Mandatory = $true)][string]$Dir)

  if (-not (Test-Path $Dir)) {
    return
  }

  $currentUserPath = [Environment]::GetEnvironmentVariable('PATH', 'User')
  $parts = @()
  if ($currentUserPath) {
    $parts = $currentUserPath -split ';'
  }

  if ($parts -contains $Dir) {
    return
  }

  $newPath = if ([string]::IsNullOrWhiteSpace($currentUserPath)) {
    $Dir
  } else {
    "$Dir;$currentUserPath"
  }

  [Environment]::SetEnvironmentVariable('PATH', $newPath, 'User')
}

function Resolve-FirstExisting {
  param([string[]]$Candidates)

  foreach ($candidate in $Candidates) {
    if (Test-Path $candidate) {
      return $candidate
    }
  }
  return $null
}

$repoRoot = (Resolve-Path "$PSScriptRoot/..").Path
Write-Host "[bootstrap] Repo root: $repoRoot"

$cmakeExe = Resolve-FirstExisting -Candidates @(
  "C:\Program Files\Microsoft Visual Studio\2022\Community\Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe",
  "C:\Program Files\Microsoft Visual Studio\2022\Professional\Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe",
  "C:\Program Files\Microsoft Visual Studio\2022\Enterprise\Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe",
  "C:\Program Files\CMake\bin\cmake.exe"
)

$ninjaExe = Resolve-FirstExisting -Candidates @(
  "C:\Program Files\Microsoft Visual Studio\2022\Community\Common7\IDE\CommonExtensions\Microsoft\CMake\Ninja\ninja.exe",
  "C:\Program Files\Microsoft Visual Studio\2022\Professional\Common7\IDE\CommonExtensions\Microsoft\CMake\Ninja\ninja.exe",
  "C:\Program Files\Microsoft Visual Studio\2022\Enterprise\Common7\IDE\CommonExtensions\Microsoft\CMake\Ninja\ninja.exe",
  "C:\Program Files\Ninja\ninja.exe"
)

$armGccExe = Resolve-FirstExisting -Candidates @(
  "C:\Program Files (x86)\Arm GNU Toolchain arm-none-eabi\14.2 rel1\bin\arm-none-eabi-gcc.exe",
  "C:\Program Files\GNU Arm Embedded Toolchain\10 2021.10\bin\arm-none-eabi-gcc.exe"
)

if (-not $cmakeExe) {
  throw "cmake.exe not found. Install Visual Studio CMake tools or CMake for Windows."
}
if (-not $ninjaExe) {
  throw "ninja.exe not found. Install Ninja (or Visual Studio CMake tools bundle)."
}
if (-not $armGccExe) {
  throw "arm-none-eabi-gcc.exe not found. Install Arm GNU Toolchain."
}

$cmakeDir = Split-Path -Parent $cmakeExe
$ninjaDir = Split-Path -Parent $ninjaExe
$armDir = Split-Path -Parent $armGccExe

Add-SessionPath -Dir $cmakeDir
Add-SessionPath -Dir $ninjaDir
Add-SessionPath -Dir $armDir

$pythonExe = Resolve-FirstExisting -Candidates @(
  "$env:LocalAppData\Programs\Python\Python312\python.exe",
  "C:\Program Files\Python312\python.exe"
)

if (-not $pythonExe) {
  Write-Host "[bootstrap] Python not found; downloading installer..."
  $installer = Join-Path $env:TEMP "python-3.12.10-amd64.exe"
  Invoke-WebRequest -Uri "https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe" -OutFile $installer
  Start-Process -FilePath $installer -ArgumentList "/quiet InstallAllUsers=0 PrependPath=1 Include_test=0" -Wait

  $pythonExe = Resolve-FirstExisting -Candidates @(
    "$env:LocalAppData\Programs\Python\Python312\python.exe",
    "C:\Program Files\Python312\python.exe"
  )

  if (-not $pythonExe) {
    throw "Python installation completed but python.exe was not found in expected locations."
  }
}

$pythonDir = Split-Path -Parent $pythonExe
Add-SessionPath -Dir $pythonDir

$userScripts = Join-Path $env:APPDATA "Python\Python312\Scripts"
Add-SessionPath -Dir $userScripts

Write-Host "[bootstrap] Installing/updating Python tooling..."
& $pythonExe -m pip install --upgrade pip
& $pythonExe -m pip install --user colcon-common-extensions

# Re-apply in case scripts were created during pip install
Add-SessionPath -Dir $userScripts

if ($PersistUserPath) {
  Add-UserPath -Dir $cmakeDir
  Add-UserPath -Dir $ninjaDir
  Add-UserPath -Dir $armDir
  Add-UserPath -Dir $pythonDir
  Add-UserPath -Dir $userScripts
  Write-Host "[bootstrap] User PATH updated persistently." -ForegroundColor Yellow
}

Write-Host "[bootstrap] Verifying toolchain..."
& cmake --version | Select-Object -First 1
& ninja --version
& arm-none-eabi-gcc --version | Select-Object -First 1
& $pythonExe --version
& $pythonExe -m colcon --help | Select-Object -First 1

Write-Host ""
Write-Host "[bootstrap] Done. This PowerShell session is now ready." -ForegroundColor Green
Write-Host "[bootstrap] Next commands:"
Write-Host "  cd $repoRoot\firmware\stm32_chassis"
Write-Host "  cmake --preset Debug"
Write-Host "  cmake --build --preset Debug --parallel 4"
Write-Host "  powershell -ExecutionPolicy Bypass -File .\scripts\build_host_windows.ps1 -UseWslFallback"
