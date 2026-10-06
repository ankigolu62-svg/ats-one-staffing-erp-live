# ATS-One R17 — Full JobDiva-equivalent parity ledger

Authority: R16R1 `f1669e8583949e48df7b81fbcad964553b8aa3f0`. R16R1 V3 reported 27/27 **route/UI/auth smoke tests**; not full business-cycle acceptance.

This is a **release-blocking acceptance contract**, not a claim that JobDiva's proprietary application, private screens, patent-specific engine, third-party integrations, or mobile applications have been copied. Functional equivalence requires separate and independently verified outcomes.

Evidence reference: https://www.jobdiva.com/ — core modules ATS, CRM, onboarding, DivaFinancials, VMS synchronization, reports/analytics and integration ecosystem; https://www.jobdiva.com/candidate-engagement — smart sourcing, communications, live interviews; https://www.jobdiva.com/vendor-management-system-divavms — MSP/supplier workflow.

## Non-negotiable gates

- **A / Visible UI:** Every action/menu can be reached by the authorized role; no misleading dead controls.
- **B / API:** Action has a real, role-checked backend with validation and truthful error state.
- **C / Persistence:** New data survives restart and is linked to original entities.
- **D / Integrity:** Entity ownership, legal transitions, money math, optimistic concurrency and tenant boundaries cannot be bypassed.
- **E / E2E:** Complete create→view→edit→transition→report→audit→portal sequence is exercised using isolated data.
- **F / Security:** Negative role and cross-tenant tests, no PII/rate leaks, test/prod data separation.
- **G / External:** Live vendor integration only after provisioned credentials, real send/sync receipt, retries/observability, and written approval; NOT CONNECTED never counts PASS.
- **H / Production:** Verified controlled deployment, health, authenticated live read-only checks, durability, rollback and release evidence.

## Feature-level acceptance inventory

| # | Area | Observable in R16R1 | Still required for complete functional equivalence |
|---|---|---|---|
| 01 | Identity/security/tenancy | Sessions, RBAC and tenant model | Exhaustive negative rights across **all** routes, role portals, PII minimization, storage/access controls, safe concurrent multi-user operations; R17 hardens known document/onboarding/time/job leaks. |
| 02 | Resume intake/parsing | Paste/manual/text intake | Genuine PDF/DOCX parsing with structured chronology and version/consent management; authenticated inbound email intake, duplicates and preview/commit checks. |
| 03 | Candidate master | 13-profile-tab UI; records/docs/notes | Each action CRUD/E2E, duplicate merges, history, compliance expiry and sourcing/ownership roles. |
| 04 | Talent search | 8 tabs, boolean query, relevant-years fields, results controls | Server-side truth for nested Boolean/exclude/geo/scoring/pagination across large realistic corpora; query explainability/performance; saved searches/dynamic pools. |
| 05 | External talent harvesting | Unconnected job-board notice | Authorized job-board subscription/harvest, consent, delta synchronization, dedupe, rate limits and audit. |
| 06 | Jobs & job ownership | R16R1 job list route and legacy search | Full job status/edit/clone/approval/assignment/distribution and all 11-column actions with persistence and role isolation. |
| 07 | CRM/sales | Companies, contacts, leads, opportunities | Activities, relationship history, pipeline audit, customer requirements, approval/rate cards and robust company-linked permissions. |
| 08 | Submittal→placement | Interested, submissions, interviews, offers, starts | Full legal status state graph, RTR, compliant profiles, client approvals/rejections, workflow transitions, negative E2E and audit. |
| 09 | Engagement/communications | Email merge logging and DivaBuzz-style history | Real provider-acknowledged outbound/inbound email/SMS, opt-out/consent, conversation threads, templating, failure/retries and schedules. |
| 10 | Assessments/live interviews | Assessment forms; live provider placeholder | Real video provider, recording permissions, files/retention, links to candidate and submittal, scores and role-safe sharing. |
| 11 | Onboarding/e-sign | Package/requirements workflow | Full evidence collection, secure signatures/vendor receipts, expiration, company/client workflows and legal/compliance gates. |
| 12 | Workforce | Starts, assignments, shifts, attendance | Assignment contracts, renewals/ending, approver and worker portal traceability, time/pay policy validation. |
| 13 | Time/expenses/approvals | Submission, approvals and some portal flows | Complete weekly edits, idempotency, overtime/local rules, locking, receipt attachment, audit and client/worker rate separation. |
| 14 | Finance/back office | Invoices, POs, payment records, margin | Real billing calculation, complex rates, taxation, credits/disputes, reconciliations, payment receipts and payroll/GL vendor integrations. |
| 15 | VMS/MSP/supplier | Accounts/mapping/release/internal history | Authorized live VMS adapters/contract, sync/exception resolution and supplier/client lifecycle parity. |
| 16 | Analytics/reporting | Defined reports/export and dashboards | Configurable BI/report builder, sharing permissions, row-level visibility, arbitrary filters, scheduled delivery and reproducible financial correctness. |
| 17 | Configuration/customization | Custom fields, automation metadata, connectors | Workflow and policy authoring, admin maintenance, audit, operational alerting, full fail-closed replay. |
| 18 | Portals/mobile | Candidate, client, worker, supplier, approver browser portals | End-to-end portal-permission coverage; responsive/mobile accessibility; native apps not implemented. |
| 19 | Integrations | Connector reference metadata and NOT CONNECTED gates | Real vendor evidence for each requested integration; impossible to certify without accounts/approvals. |
| 20 | Operations/production | R16R1 static + browser baseline | Representative concurrent load, persistence durability/recovery, zero-downtime migration, backup/restore, live UI E2E, support runbook. |

## R17 scope implemented by the accompanying patch (must still pass Windows tests)

- GET candidate document download enforces document RBAC, candidate/worker ownership and tenant scope; document/assessment endpoints now flow through tenant policy override dispatch.
- GET onboarding package enforces role and own-candidate checks; requirement query is tenant scoped.
- Portal timesheets expose worker pay-side or client/approver bill-side only; internal roles retain both.
- Timesheet POST status actions explicitly block unauthorized roles and stop client/supplier draft/submission control.
- Job list/detail restrict portal roles and redact candidate/worker/supplier bill-side or client pay-side details.
- Static asset resolver prevents sibling-directory path-prefix confusion.
- Global search fails visibly on incomplete API results instead of presenting fake zero results.

## Acceptance status discipline

`NOT_TESTED`, `FAIL`, `BLOCKED_EXTERNAL`, `PASS` and `NOT_APPLICABLE` are distinct. No percentages are to be fabricated. **JobDiva-equivalent 100% PASS is NOT CLAIMED by R17.** The expected next gate is a full **module-by-module traceable audit** then iterative implementation and retesting; each row above must satisfy A–H as applicable before final release.
