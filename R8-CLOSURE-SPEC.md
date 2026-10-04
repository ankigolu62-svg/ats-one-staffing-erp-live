# ATS-ONE R8 FULL INTERNAL LIVE CLOSURE

You are modifying the existing ATS-One staffing ERP repository.

NON-NEGOTIABLE SAFETY
- Work only inside this repository.
- Do not push, deploy, delete remote resources, log out accounts, create a new Supabase project, create a new Render service, or reset the live DB.
- Do not expose secrets.
- Preserve existing persisted SQLite data. Schema changes must be forward migrations using CREATE IF NOT EXISTS / ALTER-style guarded migrations.
- Do not remove existing security/RBAC fixes.
- Do not weaken tests to obtain a pass.
- Existing 244+ audit coverage must be preserved or expanded.
- Convert previous PARTIAL declarations into actual implemented workflows plus actual tests. Do not merely rename PARTIAL to PASS.
- Third-party integrations requiring real credentials may remain EXTERNAL; never fake them.

VERSION
- Set application version to exactly: 3.0.0-full

THEME
Keep the product LIGHT. Do not redesign the overall navigation/layout merely to look different.
Replace the JobDiva-like sky-blue appearance with an original light palette and centralize colors through CSS variables.

Required palette:
--primary: #6757D9
--primary-2: #8B7DE8
--accent: #1DAA8B
--coral: #E87D63
--amber: #D59A32
--app-bg: #F7F7FB
--panel: #FFFFFF
--nav: #FBFAFF
--ink: #263044
--muted: #71798A
--line: #E1E3EC
--soft: #F0EEFB

Requirements:
- light background only
- white panels
- indigo/lavender primary controls and selected navigation
- mint success/accent
- coral warning/action highlights where appropriate
- replace hard-coded old blue theme values in core UI
- preserve accessibility/contrast
- do not copy JobDiva logos, trademarks or exact proprietary visual treatment

============================================================
A. TALENT SEARCH / BOOLEAN SEARCH — MUST BE REAL
============================================================

Repair and deepen the existing search engine.

1. The initial search must NOT silently filter by today's availability date.
   blankSearch().available_before must start empty.

2. Boolean parser must correctly support:
   AND
   OR
   NOT
   nested parentheses
   quoted multi-word phrases
   unquoted multi-word skill phrases where grammar allows
   OVER N YRS
   RECENT OVER N YRS
   mixed case
   +, #, ., /, - in skill names

Examples that must work:
(Java OVER 5 YRS AND Banking OVER 2 YRS) AND NOT Mainframe
("Amazon Web Services" OVER 5 YRS OR AWS OVER 5 YRS)
Amazon Web Services OVER 5 YRS
(Java OVER 5 YRS OR Python OVER 5 YRS) AND NOT Mainframe
(DEVELOPER RECENT OVER 5 YRS)
("C #" OVER 3 YRS OR "C++" OVER 3 YRS)

3. Malformed Boolean expressions must return HTTP 400 with a useful syntax error.
Do not silently return zero results.

4. Mapping:
AWS <-> Amazon Web Services
GCP <-> Google Cloud Platform
JS <-> JavaScript
TS <-> TypeScript
K8s <-> Kubernetes
Postgres <-> PostgreSQL
Spring <-> Spring Boot where appropriate
and retain/extensibly structure existing aliases.
without_mapping=true must do literal matching only.

5. Experience-aware search:
Years/recent matching cannot depend solely on candidate_skills.
Use candidate structured skills PLUS employment history/title/experience skill segments.
Do not double-count overlapping history.
A term can match current_title, employment title, employment skills and structured skills.
OVER N YRS must have defensible accumulated/relevant experience semantics.
RECENT must require current/recent use, not just historical occurrence.

6. Profession, specialty, title, qualification, license, certification, attributes,
state, pay and availability must remain functional.

7. ZIP/radius must become functional instead of decorative.
Implement candidate latitude/longitude or postal-location support and distance calculation.
Seed coordinates for existing demo postal codes.
Candidate create/edit must allow postal/geo workflow.
If radius is requested but a postal code cannot be resolved, return a clear validation error,
not silently ignore the filter.

8. Job -> Find Candidates:
openJobSearch(jobId) must prepopulate profession, specialty, required skills,
experience/recent flags, location/pay where meaningful, then run/display matching results.

9. Candidate -> DivaMatch:
Remove the separate simplistic browser-only matcher.
Create/use the same backend matching engine for candidate-to-job scoring.
Expose match reasons and score consistently.

10. Search actions:
- Exclude must persist for current search state rather than only deleting a DOM row.
- Qualify must create/update interested/qualified relation.
- Expand must show structured matching evidence.
- Hotlist must work.
- Preview must work.
- Relevancy must show score/reasons, not only a toast.
- Bulk Action must be a real action menu/engine.
- Email Merge must continue to log/send through configured communication adapter.
- Save Dynamic Pool must preserve intentional filters only.

============================================================
B. CANDIDATE MASTER — CLOSE ALL INTERNAL GAPS
============================================================

Implement full role-secured CRUD/UI and audit logging for:
- employment history
- skills
- licenses
- certifications
- qualifications/sub-values
- attributes
- candidate notes/tasks
- candidate document metadata
- document upload/download/version/verification using safe local/persistent object storage abstraction
- archive/restore candidate

Implement resume ingestion:
- user can upload/paste resume
- deterministic local extraction for contact/title/skills/basic employment when possible
- always allow recruiter review/edit before committing parsed structure
Do not claim AI-quality parsing where deterministic extraction cannot know something.

============================================================
C. HOTLISTS / TALENT POOLS
============================================================

Implement:
- create
- rename/edit
- visibility/owner update with RBAC
- add/remove members
- member status/note update
- archive/delete
- dynamic search update
- dynamic rerun
- duplicate prevention
- audit trail

============================================================
D. JOBS / RECRUITING
============================================================

Implement:
- full job edit
- archive/restore
- clone
- recruiter/sales/secondary user role assignment CRUD
- job distribution internal publish/unpublish/sync state workflow
- interested candidate lifecycle
- qualification
- RTR/compliance gates
- submission create/update/status lifecycle
- client review
- interview
- hired
- start
- start cancellation
- assignment creation
- termination/end
- preserve company submission-rule inheritance + job overrides
- prevent invalid workflow transitions

============================================================
E. CRM
============================================================

Implement real CRUD/lifecycles for:
- companies
- contacts
- leads
- lead status/update
- lead convert
- opportunities
- opportunity stages
- won/lost
- next activity
- audit
Dashboard CRM funnel must derive from live DB, not hard-coded counts.

============================================================
F. INTERVIEWS / ASSESSMENTS / ONBOARDING
============================================================

Interviews:
- create
- reschedule
- interviewer/link/timezone
- status lifecycle
- feedback
- rating
- completion/cancellation

Assessments:
- invite
- questions
- answers
- score
- status
- completion
- recruiter review

Onboarding:
- package CRUD
- requirements CRUD
- document/evidence attachment
- status
- completion
- expiry where relevant
- preserve existing auto-completion behavior

External certified e-sign / identity providers remain adapters marked EXTERNAL until credentials.

============================================================
G. WORKFORCE / TIME / EXPENSE / FINANCE
============================================================

Starts:
- create/update/cancel/complete

Assignments:
- create/edit
- active/on-hold/ended/terminated lifecycle
- bill/pay/worksite/cost-center/VMS/approver/overtime/payroll/PO
- history

Shifts:
- create/update/delete
- employee view

Attendance:
- create/update/delete
- links to assignment/shift/worker

Timesheets:
- draft
- submit
- approve/reject
- reopen/correct with proper roles
- automatic OT preserved
- audit

Expenses:
- draft/submit/approve/reject/reopen
- receipt reference/evidence
- audit

Purchase Orders:
- create/edit/status/close
- company/job/assignment mapping

Invoices:
- create
- issue
- partial payment
- payment
- void
- due/aging state
- payment history if needed
- protect finance-only operations

============================================================
H. VMS / SUPPLIERS / OPERATIONS
============================================================

VMS:
- internal account CRUD
- mapping CRUD
- sync job state
- sync history/error state
- manual retry
Real Fieldglass/Beeline network calls remain EXTERNAL until credentials.

Suppliers:
- supplier CRUD
- activate/deactivate
- release/unrelease jobs
- submission limit enforcement
- supplier scoped portal and isolation

Tasks:
- create/update/assign/complete/archive

Automations:
- rule CRUD
- trigger/condition/action model
- safe internal execution for supported actions
- run history
- dry-run/test action
No invented external vendor actions.

Integrations:
- connector config CRUD
- credential reference metadata without exposing secrets
- test/sync state
- logs
Real vendor actions remain EXTERNAL.

============================================================
I. ADMIN / UDF / USERS / REPORTING
============================================================

UDF:
- definition CRUD
- entity value CRUD
- type validation

Users:
- create
- edit
- enable/disable
- role change
- reset password
- cannot disable final active admin
- session invalidation where needed

Reports:
- keep summary reports
- add report definitions/catalog
- saved report definition
- parameterized execution
- CSV export
- practical operational reports for recruiting/workforce/finance
Do not claim "1000+ reports" unless actually present.

Delete/archive:
- safe archive/restore/delete policy on operational records
- hard-delete only where appropriate and protected

============================================================
J. TENANT BOUNDARY
============================================================

Add a real tenant model without destroying current live data.

Requirements:
- tenants table
- tenant_id on users and tenant-owned operational entities
- migrate existing rows to default tenant 1 safely
- session tied to tenant
- queries/mutations scoped to tenant where applicable
- no cross-tenant reads/writes by direct ID
- admin is tenant admin, not global superuser unless explicitly modeled
- create independent second tenant in isolated audit and prove isolation

Do not reset existing production data.

============================================================
K. SECURITY / QUALITY
============================================================

Preserve prior security fixes:
- candidate cannot patch another candidate
- candidate cannot patch internal jobs
- candidate cannot create internal hotlists
- candidate cannot create submission for another candidate
- candidate cannot force hired
- candidate cannot create interview/assignment
- candidate cannot approve expense
- candidate cannot list finance invoices/internal CRM
- supplier cannot browse internal candidate DB
- client direct-ID isolation
- safe reference endpoint
- supplier unreleased-job protection

Add input validation and transition checks where needed.

============================================================
L. AUDIT REQUIREMENTS
============================================================

Update deep_audit.py.

Important:
- preserve or INCREASE total coverage from 244
- do not delete checks to obtain a green result
- replace all previous internal PARTIAL declarations with executable validation
- target:
  FAIL=0
  PARTIAL=0
  EXTERNAL may remain 7 for real third-party credentials

Create:
full_live_acceptance.py

CLI:
python full_live_acceptance.py --json-out <file>
python full_live_acceptance.py --base-url <url> --live-readonly --json-out <file>

Local mode must:
- use isolated temp database
- start server automatically
- exercise Talent/Boolean cases
- exercise job->search and candidate->match
- exercise each new CRUD/lifecycle
- exercise tenant isolation
- exercise RBAC
- exercise invalid transitions
- verify light-theme required variables
- verify main pages expose functional controls
- return nonzero on failure
- write JSON:
  {
    "overall":"PASS|FAIL",
    "fail":0,
    "checks":[...]
  }

Live-readonly mode must not mutate operational live data.
It may login and test:
- health
- session
- Talent Search reads
- Boolean searches
- candidate/job reads
- match reads
- RBAC read protection
- version
- persistence indicator

Required local acceptance labels:
SEARCH_EMPTY_NO_HIDDEN_AVAILABILITY
BOOLEAN_AND_OR_NOT
BOOLEAN_NESTED
BOOLEAN_QUOTED_MULTIWORD
BOOLEAN_UNQUOTED_MULTIWORD
BOOLEAN_INVALID_SYNTAX_400
BOOLEAN_YEARS
BOOLEAN_RECENT
SYNONYM_MAPPING
WITHOUT_MAPPING_LITERAL
ZIP_RADIUS
JOB_TO_TALENT_SEARCH
DIVAMATCH_SHARED_ENGINE
SEARCH_EXPAND
SEARCH_RELEVANCY
SEARCH_BULK_ACTION
CANDIDATE_STRUCTURED_CRUD
DOCUMENT_WORKFLOW
HOTLIST_FULL_CRUD
JOB_ROLE_CRUD
JOB_CLONE_ARCHIVE
CRM_LIFECYCLE
INTERVIEW_LIFECYCLE
ASSESSMENT_LIFECYCLE
ONBOARDING_LIFECYCLE
START_LIFECYCLE
ASSIGNMENT_LIFECYCLE
SHIFT_CRUD
ATTENDANCE_CRUD
TIMESHEET_LIFECYCLE
EXPENSE_LIFECYCLE
PO_LIFECYCLE
INVOICE_LIFECYCLE
VMS_INTERNAL_CRUD
SUPPLIER_RELEASE_ADMIN
TASK_LIFECYCLE
AUTOMATION_INTERNAL_ENGINE
INTEGRATION_CONFIG
UDF_CRUD
USER_ADMIN_LIFECYCLE
REPORT_EXECUTION_EXPORT
ARCHIVE_RESTORE
TENANT_ISOLATION
SECURITY_REGRESSION
LIGHT_DISTINCT_THEME

============================================================
M. FILE / DEPLOY RULES
============================================================

- Python standard library is preferred; add dependency only if materially required.
- Node is only for JS syntax checking unless project changes require more.
- Keep Render start command compatible:
  python server.py --host 0.0.0.0 --port $PORT
- Keep /api/health.
- Keep Supabase Storage persistence.
- Do not reset the existing live SQLite database.
- Update FUNCTION-MAP.md and ARCHITECTURE.md truthfully.
- Keep EXTERNAL items explicit.
- Do not say complete unless tests prove it.

Before finishing:
python -m py_compile server.py deep_audit.py full_live_acceptance.py
node --check web/app.js
python deep_audit.py
python full_live_acceptance.py --json-out full-live-local.json

Fix failures before returning.