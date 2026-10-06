# Functional Map

## Talent Management
- Shared candidate master record
- Skills with relevant years, recent-use flag and last-used date
- Employment segments
- Profession / specialty
- Licenses: country, state, status, expiry and documentation flag
- Certifications: status, expiry and documentation flag
- Structured qualifications
- Candidate attributes / tags
- Candidate document metadata plus SQLite-backed binary versions, verification and download
- Notes, tasks and communication history
- Credibility score
- Static hotlists
- Dynamic talent pools saved from search criteria
- Candidate-to-job matching through the same server-side evidence/scoring engine used by Talent Search
- Deterministic resume extraction with an explicit recruiter review/commit step
- Role-secured structured CRUD and candidate archive/restore

## Deep Talent Search
Eight JobDiva-style search areas are represented:
1. Profession / Specialty
2. Licenses
3. Certifications
4. Qualification
5. Require
6. Exclude
7. Attribute
8. Title

Additional refinements:
- state
- ZIP / radius validation and Haversine distance filtering for resolved postal coordinates
- pay range
- availability date
- mapping on/off
- raw Boolean expression

Working Boolean examples:

```text
(Java OVER 5 YRS AND Banking OVER 2 YRS) AND NOT Mainframe
(DEVELOPER RECENT OVER 5 YRS) AND (JAVA OVER 5 YRS OR "C #" OVER 5 YRS)
```

Result actions include Exclude, Qualify, Expand, Hotlist, Preview, Relevancy, Bulk Action entry point and Email Merge logging.
Exclusions persist in the active criteria; Expand and Relevancy expose structured evidence; bulk actions execute on the server.

## Jobs / Recruiting
- Job creation
- client / hiring manager linkage
- primary recruiter and sales ownership
- status, priority, type, openings and location
- pay and bill ranges
- structured requirement strings
- company submittal guideline inheritance + job override
- interested/qualified candidate layer
- submittal layer kept separate from interest
- RTR and compliance status
- client feedback
- interview scheduling
- job distribution publish/unpublish/sync-state records
- job role assignment, full edit, clone and archive/restore
- guarded interested/submission/interview/offer/hire/start/assignment transitions

## CRM / Sales
- Company creation
- Contact creation
- company type and industry
- billing terms
- company-level candidate submittal rules
- discount/rate rule storage
- Leads
- Opportunities with stage, value, probability and expected close
- dashboard sales pipeline derived from current tenant data
- lead update/conversion and opportunity stage/won/lost lifecycle

## Candidate profile areas
- Resume
- Wallet
- Credibility
- job-match view
- Email/communication
- Tasks/Notes
- Assignment
- Onboarding
- Calendar/Interview linkage

## Assessments / Interviews
- questionnaires / technical / recorded-video / live-interview types
- questions, answers, score, completion and recruiter review
- interview type, schedule, timezone, interviewer, link/location, feedback, rating and guarded status lifecycle

## Onboarding
- package assignment
- job/candidate/submittal linkage
- requirement list
- mandatory flag
- completion status
- automatic package completion when all requirements are complete
- requirement CRUD, evidence-document link and expiry

## Workforce
- Start object
- Assignment record
- bill rate / pay rate
- worksite
- cost center
- VMS ID
- approver
- overtime rule
- payroll profile
- PO number
- shifts
- assignment status lifecycle
- start create/update/cancel/complete and assignment transition history
- shift and attendance CRUD

## Time / Expense
- worker time entry by day
- automatic regular/overtime split after 40h
- draft / submit / approve / reject / reopen with guarded role transitions
- client/approver portal
- expenses with category, amount, receipt reference and approval status

## Finance
- purchase orders
- invoices
- issue, partial/full payment, void, due/aging state and payment history
- assignment margin/spread view
- bill and pay sides remain separate

## VMS / MSP / Suppliers
- VMS account
- external/internal object IDs
- external/internal status mapping
- mapping JSON
- supplier registry
- job release to supplier
- supplier portal
- VMS-released jobs
- internal VMS CRUD, mapping CRUD, sync/retry history and error state
- supplier activate/deactivate, release/unrelease and submission-limit enforcement

## Portals / Roles
- Admin
- Team Lead
- Recruiter
- Sales
- HR
- Finance
- Client / Hiring Manager
- Candidate
- Worker / MyTime
- Supplier
- Timesheet/Expense Approver

## Platform
- server-side authentication
- PBKDF2 password hashes
- session cookies
- role-based permissions
- role-filtered data views
- threaded local server
- SQLite WAL concurrent access
- audit trail
- typed UDF definition/value CRUD
- automation CRUD, safe internal execution, dry-run and run history
- connector configuration, credential-reference metadata, test/sync state and logs
- saved parameterized operational reports and CSV export
- tenant-scoped sessions, reads and writes with a forward-migrated default tenant
- reset/seed support

## Verification

- `deep_audit.py` retains the legacy audit and consumes executable R8 acceptance results.
- `full_live_acceptance.py` starts an isolated temporary database in local mode and supports non-mutating `--live-readonly` checks.
- Current application version: `3.0.0-full`.

## External services requiring real credentials
The internal workflow and mapping exist, but live calls require customer/vendor credentials for: real job boards, LinkedIn, Fieldglass/Beeline, background screening, payroll/GL, production email/SMS/VOIP, government verification and production e-sign services.

<!-- R15_CORRECTNESS_AUTHORITY_BEGIN -->
## R15 correctness authority
R15 supersedes earlier capability wording where it conflicts with `R15-CORRECTNESS.md`.
Security/lifecycle/financial mutations are policy-gated; disconnected schedulers/campaigns/SSO are configuration-only;
external vendors remain Not Connected without live proof; production durability requires the Postgres-backed CAS authority.
The identity model is globally unique email with one primary tenant per user row.
<!-- R15_CORRECTNESS_AUTHORITY_END -->