[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

function Banner([string]$Text) {
    Write-Host ''
    Write-Host ('=' * 78) -ForegroundColor Cyan
    Write-Host (' ' + $Text) -ForegroundColor Cyan
    Write-Host ('=' * 78) -ForegroundColor Cyan
}
function Refresh-Path {
    $machine = [Environment]::GetEnvironmentVariable('Path','Machine')
    $user    = [Environment]::GetEnvironmentVariable('Path','User')
    $env:Path = "$machine;$user"
}
function Need-Command([string]$Name, [string]$WingetId) {
    if (Get-Command $Name -ErrorAction SilentlyContinue) { return }
    if (-not (Get-Command winget.exe -ErrorAction SilentlyContinue)) {
        throw "MISSING_$($Name.ToUpper())_AND_WINGET_NOT_AVAILABLE"
    }
    Write-Host "Installing $Name ($WingetId)..." -ForegroundColor Yellow
    & winget.exe install --id $WingetId -e --accept-package-agreements --accept-source-agreements
    if ($LASTEXITCODE -ne 0) { throw "WINGET_INSTALL_FAILED=$WingetId EXIT=$LASTEXITCODE" }
    Refresh-Path
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) { throw "COMMAND_STILL_MISSING=$Name" }
}
function Run-Text([scriptblock]$Script) {
    $out = & $Script 2>&1 | Out-String
    if ($LASTEXITCODE -ne $null -and $LASTEXITCODE -ne 0) { throw "COMMAND_FAILED EXIT=$LASTEXITCODE`n$out" }
    return $out.Trim()
}
function Parse-Json([string]$Text, [string]$Label) {
    try { return ($Text | ConvertFrom-Json) } catch { throw "$Label JSON_PARSE_FAIL`n$Text" }
}
function Find-StringRecursive($Object, [scriptblock]$Predicate) {
    if ($null -eq $Object) { return $null }
    if ($Object -is [string]) {
        if (& $Predicate $Object) { return $Object }
        return $null
    }
    if ($Object -is [System.Collections.IDictionary]) {
        foreach ($k in $Object.Keys) {
            $v = Find-StringRecursive $Object[$k] $Predicate
            if ($v) { return $v }
        }
        return $null
    }
    if ($Object -is [System.Collections.IEnumerable] -and -not ($Object -is [string])) {
        foreach ($x in $Object) {
            $v = Find-StringRecursive $x $Predicate
            if ($v) { return $v }
        }
        return $null
    }
    foreach ($p in $Object.PSObject.Properties) {
        $v = Find-StringRecursive $p.Value $Predicate
        if ($v) { return $v }
    }
    return $null
}
function Get-SupabaseCliJson([string[]]$Args) {
    $raw = & npx.cmd --yes supabase@latest @Args -o json 2>&1 | Out-String
    if ($LASTEXITCODE -ne 0) { throw "SUPABASE_CLI_FAILED: npx supabase $($Args -join ' ')`n$raw" }
    return Parse-Json $raw 'SUPABASE'
}
function Get-PropertyAny($Obj, [string[]]$Names) {
    foreach ($n in $Names) {
        $p = $Obj.PSObject.Properties[$n]
        if ($p -and $null -ne $p.Value -and "$($p.Value)" -ne '') { return $p.Value }
    }
    return $null
}

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root
Banner 'ATS-ONE - FAIL-CLOSED FREE LIVE DEPLOY (GITHUB + SUPABASE + RENDER)'
Write-Host "ROOT=$Root"

# ------------------------------------------------------------------
# 1/8 Tooling
# ------------------------------------------------------------------
Write-Host ''
Write-Host '[1/8] TOOLING' -ForegroundColor Yellow
Need-Command git.exe 'Git.Git'
Need-Command gh.exe 'GitHub.cli'
Need-Command node.exe 'OpenJS.NodeJS.LTS'
Need-Command render.exe 'render.cli'
if (-not (Get-Command npx.cmd -ErrorAction SilentlyContinue)) { Refresh-Path }
if (-not (Get-Command npx.cmd -ErrorAction SilentlyContinue)) { throw 'NPX_NOT_AVAILABLE_AFTER_NODE_INSTALL' }

$py = $null
if (Get-Command py.exe -ErrorAction SilentlyContinue) { $py = 'py.exe' }
elseif (Get-Command python.exe -ErrorAction SilentlyContinue) { $py = 'python.exe' }
else {
    Need-Command python.exe 'Python.Python.3.13'
    $py='python.exe'
}
Write-Host "TOOLS=PASS PYTHON=$py" -ForegroundColor Green

# ------------------------------------------------------------------
# 2/8 Deep acceptance gate
# ------------------------------------------------------------------
Write-Host ''
Write-Host '[2/8] DEEP SECURITY/FUNCTION AUDIT' -ForegroundColor Yellow
if ($py -eq 'py.exe') { & py.exe -3 deep_audit.py } else { & python.exe deep_audit.py }
if ($LASTEXITCODE -ne 0) { throw "DEEP_AUDIT_FAIL EXIT=$LASTEXITCODE - deployment blocked" }
$latestAudit = Get-ChildItem (Join-Path $Root 'audit-results') -Filter 'DEEP-AUDIT-*.json' -File |
    Sort-Object LastWriteTime -Descending | Select-Object -First 1
if (-not $latestAudit) { throw 'DEEP_AUDIT_JSON_MISSING' }
$audit = Get-Content $latestAudit.FullName -Raw | ConvertFrom-Json

# AUDIT_COUNT_SAFE_R3
# deep_audit.py omits a status key when its count is zero.
# StrictMode therefore must not directly dereference a missing property.
function Get-AuditCountSafe($Counts, [string]$Name) {
    if ($null -eq $Counts) {
        return 0
    }

    $prop = $Counts.PSObject.Properties[$Name]

    if ($null -eq $prop -or $null -eq $prop.Value) {
        return 0
    }

    return [int]$prop.Value
}

$auditPass     = Get-AuditCountSafe $audit.counts 'PASS'
$auditFail     = Get-AuditCountSafe $audit.counts 'FAIL'
$auditPartial  = Get-AuditCountSafe $audit.counts 'PARTIAL'
$auditExternal = Get-AuditCountSafe $audit.counts 'EXTERNAL'
if ([int]$auditFail -ne 0) { throw "DEEP_AUDIT_FAIL_COUNT=$($auditFail)" }
Write-Host "AUDIT_GATE=PASS PASS=$($auditPass) FAIL=$($auditFail) PARTIAL=$($auditPartial) EXTERNAL=$($auditExternal)" -ForegroundColor Green

# ------------------------------------------------------------------
# 3/8 GitHub auth + repository
# ------------------------------------------------------------------
Write-Host ''
Write-Host '[3/8] GITHUB' -ForegroundColor Yellow
& gh.exe auth status -h github.com *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Host 'GitHub browser authorization khulega. Login/Authorize karke terminal par wapas aana.' -ForegroundColor Cyan
    & gh.exe auth login --hostname github.com --git-protocol https --web
    if ($LASTEXITCODE -ne 0) { throw 'GITHUB_AUTH_FAILED' }
}
$owner = ((& gh.exe api user --jq '.login' 2>$null | Out-String).Trim())
if (-not $owner) { throw 'GITHUB_OWNER_NOT_RESOLVED' }
$repoName = 'ats-one-staffing-erp-live'
$repoFull = "$owner/$repoName"
$repoUrl = "https://github.com/$repoFull"

# Remove generated runtime evidence/data from Git tracking.
Remove-Item -Recurse -Force (Join-Path $Root 'audit-results') -ErrorAction SilentlyContinue
Get-ChildItem (Join-Path $Root 'data') -Filter '*.db*' -File -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue

if (-not (Test-Path (Join-Path $Root '.git'))) {
    & git.exe init -b main
    if ($LASTEXITCODE -ne 0) { throw 'GIT_INIT_FAILED' }
}
& git.exe config user.name $owner
$ghEmail = ((& gh.exe api user --jq '.email // empty' 2>$null | Out-String).Trim())
if (-not $ghEmail) { $ghEmail = "$owner@users.noreply.github.com" }
& git.exe config user.email $ghEmail
& git.exe add -A
& git.exe commit -m 'ATS One live-free secure deploy' 2>$null
# commit exit 1 is okay when there is nothing new.

& gh.exe repo view $repoFull *> $null
if ($LASTEXITCODE -eq 0) {
    $remote = (& git.exe remote get-url origin 2>$null | Out-String).Trim()
    if (-not $remote) { & git.exe remote add origin "$repoUrl.git" }
    else { & git.exe remote set-url origin "$repoUrl.git" }
    & git.exe push -u origin main --force-with-lease
    if ($LASTEXITCODE -ne 0) { throw 'GITHUB_PUSH_FAILED' }
} else {
    & gh.exe repo create $repoFull --public --source . --remote origin --push
    if ($LASTEXITCODE -ne 0) { throw 'GITHUB_REPO_CREATE_FAILED' }
}
Write-Host "GITHUB_REPO=$repoUrl" -ForegroundColor Green

# ------------------------------------------------------------------
# 4/8 Supabase auth + organization
# ------------------------------------------------------------------
Write-Host ''
Write-Host '[4/8] SUPABASE ACCOUNT/ORG' -ForegroundColor Yellow
Write-Host 'Supabase browser authorization khul sakta hai. Authorize karke terminal par wapas aana.' -ForegroundColor Cyan
& npx.cmd --yes supabase@latest login
if ($LASTEXITCODE -ne 0) { throw 'SUPABASE_LOGIN_FAILED' }
$orgs = @(Get-SupabaseCliJson @('orgs','list'))
if ($orgs.Count -eq 0) {
    Write-Host 'Supabase organization nahi hai. CLI ab organization create karega; naam pooche to ATS-One use kar sakte ho.' -ForegroundColor Cyan
    & npx.cmd --yes supabase@latest orgs create
    if ($LASTEXITCODE -ne 0) { throw 'SUPABASE_ORG_CREATE_FAILED' }
    $orgs = @(Get-SupabaseCliJson @('orgs','list'))
}
if ($orgs.Count -eq 0) { throw 'SUPABASE_ORG_NOT_FOUND_AFTER_CREATE' }
$org = $orgs[0]
$orgId = Get-PropertyAny $org @('id','organization_id')
if (-not $orgId) { throw 'SUPABASE_ORG_ID_NOT_RESOLVED' }
Write-Host "SUPABASE_ORG=$($org.name)" -ForegroundColor Green

# ------------------------------------------------------------------
# 5/8 Supabase free project + backend secret
# ------------------------------------------------------------------
Write-Host ''
Write-Host '[5/8] SUPABASE PROJECT + PRIVATE STORAGE CREDENTIAL' -ForegroundColor Yellow
$projectName = 'ats-one-live'
$projects = @(Get-SupabaseCliJson @('projects','list'))
$project = $projects | Where-Object { $_.name -eq $projectName } | Select-Object -First 1
if (-not $project) {
    $alphabet = 'abcdefghijkmnopqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789!@#%'
    $dbPw = -join (1..28 | ForEach-Object { $alphabet[(Get-Random -Minimum 0 -Maximum $alphabet.Length)] })
    $createRaw = & npx.cmd --yes supabase@latest projects create $projectName --org-id $orgId --db-password $dbPw --region ap-south-1 -o json 2>&1 | Out-String
    if ($LASTEXITCODE -ne 0) { throw "SUPABASE_PROJECT_CREATE_FAILED`n$createRaw" }
    $project = Parse-Json $createRaw 'SUPABASE_PROJECT_CREATE'
    $dbPw = $null
}
$projectRef = Get-PropertyAny $project @('id','ref','project_ref')
if (-not $projectRef) { throw 'SUPABASE_PROJECT_REF_NOT_RESOLVED' }
Write-Host "SUPABASE_PROJECT_REF=$projectRef"

# Wait until API keys are available. Do not print secrets.
$keys = $null
for ($i=1; $i -le 36; $i++) {
    try {
        $keys = @(Get-SupabaseCliJson @('projects','api-keys','--project-ref',"$projectRef"))
        if ($keys.Count -gt 0) { break }
    } catch {
        if ($i -eq 36) { throw }
    }
    Write-Host "Waiting for Supabase project... attempt=$i" -ForegroundColor DarkGray
    Start-Sleep -Seconds 10
}
if (-not $keys -or $keys.Count -eq 0) { throw 'SUPABASE_API_KEYS_NOT_AVAILABLE' }
$serviceKey = $null
foreach ($k in $keys) {
    $id = "$(Get-PropertyAny $k @('id','name','type'))".ToLowerInvariant()
    $val = Get-PropertyAny $k @('api_key','key','value')
    if ($val -and ($id -eq 'service_role' -or $id -like '*service_role*')) { $serviceKey = "$val"; break }
}
if (-not $serviceKey) {
    throw 'SUPABASE_SERVICE_ROLE_KEY_NOT_FOUND - open Project Settings > API Keys and ensure legacy service_role key is enabled, then rerun.'
}
$supabaseUrl = "https://$projectRef.supabase.co"
Write-Host 'SUPABASE_SECRET=RESOLVED_NOT_PRINTED' -ForegroundColor Green

# ------------------------------------------------------------------
# 6/8 Render login
# ------------------------------------------------------------------
Write-Host ''
Write-Host '[6/8] RENDER AUTH' -ForegroundColor Yellow
Write-Host 'Render browser authorization khulega. Authorize CLI karke terminal par wapas aana.' -ForegroundColor Cyan
& render.exe login
if ($LASTEXITCODE -ne 0) { throw 'RENDER_LOGIN_FAILED' }

# ------------------------------------------------------------------
# 7/8 Create/update free Render web service
# ------------------------------------------------------------------
Write-Host ''
Write-Host '[7/8] RENDER FREE WEB SERVICE' -ForegroundColor Yellow
$safeOwner = ($owner.ToLowerInvariant() -replace '[^a-z0-9-]','-').Trim('-')
$serviceName = "ats-one-$safeOwner"
if ($serviceName.Length -gt 45) { $serviceName=$serviceName.Substring(0,45).Trim('-') }

$servicesRaw = & render.exe services --output json --confirm 2>&1 | Out-String
if ($LASTEXITCODE -ne 0) { throw "RENDER_SERVICE_LIST_FAILED`n$servicesRaw" }
$services = Parse-Json $servicesRaw 'RENDER_SERVICES'
$existing = @($services) | Where-Object { $_.name -eq $serviceName } | Select-Object -First 1

if ($existing) {
    $sid = Get-PropertyAny $existing @('id','serviceId')
    if (-not $sid) { throw 'RENDER_EXISTING_SERVICE_ID_NOT_FOUND' }
    & render.exe services update $sid `
        --repo $repoUrl `
        --branch main `
        --build-command 'pip install -r requirements.txt' `
        --start-command 'python server.py --host 0.0.0.0 --port $PORT' `
        --health-check-path '/api/health' `
        --auto-deploy=true `
        --output json --confirm *> $null
    if ($LASTEXITCODE -ne 0) { throw 'RENDER_SERVICE_UPDATE_FAILED' }
    # Environment variable mutation is guaranteed on create; for an existing service,
    # recreate is safer than silently leaving stale secrets. Ask user to delete only if mismatch.
    Write-Host 'Existing Render service found. Triggering deploy; if its Supabase env was from an older project, delete that service and rerun this controller.' -ForegroundColor Yellow
    & render.exe deploys create $sid --wait --confirm *> $null
    if ($LASTEXITCODE -ne 0) { throw 'RENDER_REDEPLOY_FAILED' }
} else {
    $create = & render.exe services create `
        --name $serviceName `
        --type web_service `
        --runtime python `
        --region singapore `
        --plan free `
        --repo $repoUrl `
        --branch main `
        --build-command 'pip install -r requirements.txt' `
        --start-command 'python server.py --host 0.0.0.0 --port $PORT' `
        --health-check-path '/api/health' `
        --auto-deploy=true `
        --env-var "SUPABASE_URL=$supabaseUrl" `
        --env-var "SUPABASE_SERVICE_ROLE_KEY=$serviceKey" `
        --env-var 'SUPABASE_BUCKET=ats-one-private' `
        --env-var 'SUPABASE_DB_OBJECT=ats_one.db' `
        --env-var 'FORCE_SECURE_COOKIE=1' `
        --output json --confirm 2>&1 | Out-String
    if ($LASTEXITCODE -ne 0) { throw "RENDER_SERVICE_CREATE_FAILED`n$create" }
    $created = Parse-Json $create 'RENDER_CREATE'
    $sid = Get-PropertyAny $created @('id','serviceId')
    if (-not $sid) {
        # Resolve by name if create response nests details.
        $all2 = Parse-Json ((& render.exe services --output json --confirm 2>&1 | Out-String)) 'RENDER_SERVICES_AFTER_CREATE'
        $found = @($all2) | Where-Object { $_.name -eq $serviceName } | Select-Object -First 1
        $sid = Get-PropertyAny $found @('id','serviceId')
    }
    if (-not $sid) { throw 'RENDER_SERVICE_ID_NOT_RESOLVED' }
    & render.exe deploys create $sid --wait --confirm *> $null
    if ($LASTEXITCODE -ne 0) {
        # First creation already kicks off a deploy; a duplicate trigger can fail while active.
        Write-Host 'First Render deploy is already running; continuing to HTTP health polling.' -ForegroundColor DarkYellow
    }
}
$serviceKey = $null

# ------------------------------------------------------------------
# 8/8 Resolve URL + live health gate
# ------------------------------------------------------------------
Write-Host ''
Write-Host '[8/8] LIVE HEALTH GATE' -ForegroundColor Yellow
$liveUrl = "https://$serviceName.onrender.com"
$healthy = $false
$health = $null
for ($i=1; $i -le 36; $i++) {
    try {
        $health = Invoke-RestMethod -Uri "$liveUrl/api/health" -Method Get -TimeoutSec 20
        if ($health.ok -eq $true) { $healthy=$true; break }
    } catch {}
    Write-Host "Waiting for Render live service... attempt=$i URL=$liveUrl" -ForegroundColor DarkGray
    Start-Sleep -Seconds 10
}
if (-not $healthy) {
    throw "LIVE_HEALTH_GATE_FAIL URL=$liveUrl - inspect Render logs; no false PASS issued."
}
if ($health.persistence -ne 'supabase-storage') {
    throw "LIVE_PERSISTENCE_GATE_FAIL persistence=$($health.persistence)"
}

Banner 'ATS-ONE LIVE = PASS'
Write-Host "GITHUB=$repoUrl" -ForegroundColor Green
Write-Host "SUPABASE_PROJECT=https://supabase.com/dashboard/project/$projectRef" -ForegroundColor Green
Write-Host "LIVE_URL=$liveUrl" -ForegroundColor Green
Write-Host "HEALTH=$liveUrl/api/health"
Write-Host "PERSISTENCE=$($health.persistence)"
Write-Host "AUDIT_FAILS=$($auditFail)"
Write-Host "AUDIT_PARTIAL=$($auditPartial)"
Write-Host ''
Write-Host 'Demo login: admin@atsone.local / Admin@123' -ForegroundColor Cyan
Start-Process $liveUrl



