$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = Get-Command python -ErrorAction SilentlyContinue

if (-not $Python) {
    throw "Python 3 is required to run the Tank Robot E2E mission."
}

& $Python.Source (Join-Path $ScriptDir "scripts/e2e_mission.py")
exit $LASTEXITCODE
