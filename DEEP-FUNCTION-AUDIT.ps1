$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

function Find-Python {
    $candidates = @()
    if (Test-Path (Join-Path $Root 'runtime-win\python.exe')) { $candidates += ,@((Join-Path $Root 'runtime-win\python.exe'), @()) }
    $py = Get-Command py -ErrorAction SilentlyContinue
    if ($py) { $candidates += ,@($py.Source, @('-3')) }
    $p = Get-Command python -ErrorAction SilentlyContinue
    if ($p) { $candidates += ,@($p.Source, @()) }
    $p3 = Get-Command python3 -ErrorAction SilentlyContinue
    if ($p3) { $candidates += ,@($p3.Source, @()) }
    foreach ($c in $candidates) {
        try {
            $exe=$c[0]; $prefix=@($c[1]); $v=& $exe @prefix -c "import sys; print(sys.version_info.major)" 2>$null
            if ($LASTEXITCODE -eq 0 -and $v -eq '3') { return @{Exe=$exe;Prefix=$prefix} }
        } catch {}
    }
    return $null
}

function Install-PythonIfNeeded {
    $found=Find-Python
    if ($found) { return $found }
    Write-Host '[AUDIT] Python 3 not found. Attempting one-time user install with winget...' -ForegroundColor Yellow
    $winget=Get-Command winget -ErrorAction SilentlyContinue
    if (-not $winget) { throw 'Python 3 is missing and winget is unavailable. Install Python 3.11+ then rerun.' }
    & $winget.Source install --id Python.Python.3.13 -e --scope user --accept-package-agreements --accept-source-agreements --silent
    if ($LASTEXITCODE -ne 0) { throw "Python installation failed: $LASTEXITCODE" }
    foreach ($x in @("$env:LOCALAPPDATA\Programs\Python\Python313\python.exe","$env:LOCALAPPDATA\Programs\Python\Python312\python.exe","$env:LOCALAPPDATA\Programs\Python\Python311\python.exe")) {
        if (Test-Path $x) { return @{Exe=$x;Prefix=@()} }
    }
    $found=Find-Python
    if (-not $found) { throw 'Python installed but python.exe was not found.' }
    return $found
}

foreach ($f in @('server.py','deep_audit.py','web\index.html','web\app.js','web\styles.css')) {
    if (-not (Test-Path (Join-Path $Root $f))) { throw "Package preflight failed: missing $f" }
}

$python=Install-PythonIfNeeded
$out=Join-Path $Root 'audit-results'
New-Item -ItemType Directory -Force -Path $out | Out-Null

Write-Host ''
Write-Host '================================================================================================' -ForegroundColor Cyan
Write-Host ' ATS ONE - DEEP FUNCTION ACCEPTANCE AUDIT' -ForegroundColor Cyan
Write-Host ' Isolated test copy: live/user database will NOT be reset or modified by this controller.' -ForegroundColor Cyan
Write-Host '================================================================================================' -ForegroundColor Cyan
Write-Host "ROOT=$Root"
Write-Host "PYTHON=$($python.Exe)"
Write-Host "OUTPUT=$out"
Write-Host '================================================================================================' -ForegroundColor Cyan
Write-Host ''

& $python.Exe @($python.Prefix) '.\deep_audit.py' --output-dir $out
$AuditExit=$LASTEXITCODE

$latest=Get-ChildItem $out -Filter 'DEEP-AUDIT-*.txt' -File | Sort-Object LastWriteTime -Descending | Select-Object -First 1
if ($latest) {
    Write-Host ''
    Write-Host "AUDIT_REPORT=$($latest.FullName)" -ForegroundColor Green
    Start-Process notepad.exe $latest.FullName
}

if ($AuditExit -ne 0) {
    Write-Host "AUDIT_EXIT=$AuditExit (FAIL findings exist; see report)" -ForegroundColor Red
    exit $AuditExit
}
Write-Host 'AUDIT_EXIT=0' -ForegroundColor Green
