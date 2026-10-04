# Architecture

```text
Browser sessions (Admin / Recruiter / Sales / HR / Finance / Client / Candidate / Worker / Supplier / Approver)
                                  |
                                  v
                    Threaded local HTTP/API server
                                  |
      +----------------------+----------------------+--------------------+
      |                      |                      |                    |
      v                      v                      v                    v
 Tenant session        Workflow guards      Shared match engine   Audit/history
 + RBAC/direct-ID      + validation         Boolean/years/geo     + reports
      |                      |                      |                    |
      +----------------------+----------------------+--------------------+
                                  |
                                  v
                         SQLite shared database
                   WAL + forward-only schema migration
                   tenant_id on tenant-owned records
                   document versions stored with the DB
```

## Core object graph

```text
Company -> Contact -> Lead / Opportunity -> Job
                                     Job -> Interested Candidate -> Submittal -> Interview
Candidate -> Resume/Skills/Licenses/Certifications/Qualifications/Attributes
Submittal -> Onboarding -> Start -> Assignment
Assignment -> Shift / Timesheet / Expense -> PO -> Invoice
VMS Account -> Mapping -> Job/Submittal/Assignment/Timesheet/Expense
Supplier -> Released Job -> Supplier Submittal -> same internal submittal lifecycle
Tenant -> Users/Sessions -> all tenant-owned operational objects
```

The browser never owns authoritative business data; it calls the shared server API. This is intentionally different from the earlier localStorage demo.

## Persistence and migrations

`init_db()` applies idempotent `CREATE TABLE IF NOT EXISTS` statements and guarded
`ALTER TABLE ... ADD COLUMN` migrations. Existing rows are assigned to tenant 1;
the database is never reset as part of a normal upgrade. On the free live profile,
the SQLite database—including document version content—is checkpointed to the
configured private Supabase Storage object.

## Search and matching

Talent Search parses Boolean input into a validated syntax tree. Candidate evidence
is assembled from structured skills, non-overlapping employment periods, titles and
recent-use signals. Job-to-candidate and candidate-to-job endpoints use the same
evidence model and return scores plus reasons. Postal radius filters use resolved
coordinates and reject unknown origins instead of silently ignoring the filter.

## External boundary

Connector and VMS configuration, mappings, test state, retry/run history and safe
internal actions are persisted locally. Network calls to paid job boards,
Fieldglass/Beeline, production messaging, payroll/GL, screening, government identity
services and certified e-signature providers remain explicitly external until real
credentials and contracts are supplied.
