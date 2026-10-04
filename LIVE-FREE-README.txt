ATS ONE LIVE FREE — Render + Supabase Storage persistence

This package is a hardened public-preview build of ATS One.
Validated local deep audit at build time:
  FAIL=0
  PASS=206
  PARTIAL=31
  EXTERNAL=7

Important:
- It is multi-user on one Render web instance.
- SQLite remains the application database for compatibility.
- Supabase Storage privately persists/checkpoints the SQLite DB so a Render Free restart/spin-down can restore it.
- This is suitable for free testing/demo/internal evaluation, not high-scale production.
- 31 capability areas remain PARTIAL according to the included deep auditor.
- External vendor integrations require real vendor credentials/contracts.

Run DEPLOY-FREE-LIVE.ps1 from PowerShell. It will:
1. run the local deep audit and fail closed on any actual FAIL,
2. authenticate/create a GitHub public repo,
3. authenticate/create a Supabase free organization/project (if absent),
4. retrieve a backend service-role key without printing it,
5. create a Render Free web service,
6. wait for /api/health and print/open the live URL.

R2 WINDOWS PARSER FIX: all PowerShell controllers are ASCII-safe/UTF-8-BOM and CMD launchers prefer PowerShell 7.
