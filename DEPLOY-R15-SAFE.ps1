[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][ValidatePattern('^[0-9a-fA-F]{40}$')][string]$ExpectedSha
)
$ErrorActionPreference='Stop';Set-StrictMode -Version Latest
$root=Split-Path -Parent $MyInvocation.MyCommand.Path;Set-Location $root
$branch=(git branch --show-current).Trim();$head=(git rev-parse HEAD).Trim()
if($branch -ne 'closure/r15-master-correctness-20261005'){throw "WRONG_BRANCH=$branch"}
if($head -ne $ExpectedSha){throw "SHA_MISMATCH expected=$ExpectedSha actual=$head"}
if(git status --porcelain){throw 'WORKTREE_NOT_CLEAN'}
$main=(git ls-remote origin refs/heads/main);Write-Host "R15_RELEASE_PREFLIGHT=PASS" -ForegroundColor Green
Write-Host "HEAD=$head";Write-Host "REMOTE_MAIN=$main"
Write-Host 'DEPLOYMENT_PERFORMED=NO'
Write-Host 'Run production deployment only as a separate explicitly-authorized operation.'
