$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

$py = Get-Command py -ErrorAction SilentlyContinue
$python = Get-Command python -ErrorAction SilentlyContinue
if ($py) { $Exe=$py.Source; $Prefix=@('-3') }
elseif ($python) { $Exe=$python.Source; $Prefix=@() }
else {
    Write-Host 'Python is required for LAN mode. Run RUN-WINDOWS.ps1 once first; it can install Python automatically.' -ForegroundColor Yellow
    exit 1
}

$Port=8765
$ips = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue | Where-Object { $_.IPAddress -notmatch '^127\.' -and $_.PrefixOrigin -ne 'WellKnown' } | Select-Object -ExpandProperty IPAddress -Unique
Write-Host '======================================================================' -ForegroundColor Cyan
Write-Host ' ATS ONE STAFFING ERP - LAN MULTI-USER MODE' -ForegroundColor Cyan
Write-Host '======================================================================' -ForegroundColor Cyan
Write-Host "This PC: http://127.0.0.1:$Port/" -ForegroundColor Green
foreach($ip in $ips){ Write-Host "Other device on same LAN: http://$ip`:$Port/" -ForegroundColor Green }
Write-Host 'Windows Firewall may ask for permission. Allow only on trusted/private networks.' -ForegroundColor Yellow
Write-Host '======================================================================' -ForegroundColor Cyan
& $Exe @Prefix '.\server.py' --host 0.0.0.0 --port $Port --open
