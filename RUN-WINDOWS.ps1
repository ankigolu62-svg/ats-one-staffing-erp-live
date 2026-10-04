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
        $exe = $c[0]; $prefix = @($c[1])
        try {
            $v = & $exe @prefix -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null
            if ($LASTEXITCODE -eq 0 -and $v) { return @{ Exe=$exe; Prefix=$prefix } }
        } catch {}
    }
    return $null
}

function Install-PythonIfNeeded {
    $found = Find-Python
    if ($found) { return $found }

    Write-Host '[ATS One] Python not found. Attempting one-time user install with winget...' -ForegroundColor Yellow
    $winget = Get-Command winget -ErrorAction SilentlyContinue
    if (-not $winget) {
        throw 'Python 3 is not installed and winget is unavailable. Install Python 3.11+ once, then rerun RUN-WINDOWS.ps1.'
    }

    & $winget.Source install --id Python.Python.3.13 -e --scope user --accept-package-agreements --accept-source-agreements --silent
    if ($LASTEXITCODE -ne 0) { throw "winget Python installation failed with exit code $LASTEXITCODE" }

    $paths = @(
        "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe"
    )
    foreach ($x in $paths) {
        if (Test-Path $x) { return @{ Exe=$x; Prefix=@() } }
    }
    $found = Find-Python
    if (-not $found) { throw 'Python installation completed but python.exe could not be located.' }
    return $found
}

if (-not (Test-Path '.\server.py')) { throw 'server.py missing from package.' }
if (-not (Test-Path '.\web\index.html')) { throw 'web\index.html missing from package.' }

$python = Install-PythonIfNeeded

# Pick first free local port, starting with 8765.
$Port = 8765
while ($Port -lt 8790) {
    $listener = $null
    try {
        $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, $Port)
        $listener.Start(); $listener.Stop(); break
    } catch {
        if ($listener) { try { $listener.Stop() } catch {} }
        $Port++
    }
}
if ($Port -ge 8790) { throw 'No free local port found in range 8765-8789.' }

Write-Host ''
Write-Host '======================================================================' -ForegroundColor Cyan
Write-Host ' ATS ONE STAFFING ERP - LOCAL MULTI-USER SERVER' -ForegroundColor Cyan
Write-Host '======================================================================' -ForegroundColor Cyan
Write-Host "ROOT=$Root"
Write-Host "PYTHON=$($python.Exe)"
Write-Host "PORT=$Port"
Write-Host "URL=http://127.0.0.1:$Port/" -ForegroundColor Green
Write-Host 'Press Ctrl+C in this window to stop the server.'
Write-Host '======================================================================' -ForegroundColor Cyan
Write-Host ''

& $python.Exe @($python.Prefix) '.\server.py' --host 127.0.0.1 --port $Port --open
if ($LASTEXITCODE -ne 0) { throw "ATS One server exited with code $LASTEXITCODE" }
