ATS ONE — DEEP FUNCTION AUDIT
=============================
Run DEEP-FUNCTION-AUDIT.ps1 on Windows.

What it does:
- creates an isolated temporary runtime copy (your live/local ats_one.db is not reset or modified)
- starts a fresh seeded server on a free port
- checks package/UI route coverage
- authenticates all 11 roles
- exercises all documented GET API surfaces
- creates and links candidate/CRM/job/submission/interview/onboarding/assignment/time/expense/invoice records
- tests all 8 Talent Search dimensions and Boolean/years/recent/mapping behavior
- tests hotlists and dynamic pools
- tests client/candidate/worker/supplier/approver portals
- runs 24 concurrent sessions
- validates audit logging
- executes negative RBAC/data-isolation probes
- runs full_live_acceptance.py and resolves former internal gaps only from executable isolated-runtime labels
- verifies Boolean syntax errors, shared matching, tenant isolation, lifecycle transitions, CRUD, reports and the R8 theme
- marks real vendor integrations as EXTERNAL when credentials/contracts are required

Outputs:
  audit-results\DEEP-AUDIT-YYYYMMDD-HHMMSS.txt
  audit-results\DEEP-AUDIT-YYYYMMDD-HHMMSS.json

The TXT report automatically opens in Notepad.
Exit code 0 = no actual FAIL findings.
Exit code 2 = one or more actual FAIL findings exist; read the report.
Internal PARTIAL and real credential-bound EXTERNAL results are reported separately.
