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
- Candidate documents metadata
- Notes, tasks and communication history
- Credibility score
- Static hotlists
- Dynamic talent pools saved from search criteria
- Candidate-to-job matching view

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
- ZIP / radius UI
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
- job distribution records

## CRM / Sales
- Company creation
- Contact creation
- company type and industry
- billing terms
- company-level candidate submittal rules
- discount/rate rule storage
- Leads
- Opportunities with stage, value, probability and expected close
- dashboard sales pipeline

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
- invite status and scoring
- interview type, schedule, timezone, interviewer and link/location

## Onboarding
- package assignment
- job/candidate/submittal linkage
- requirement list
- mandatory flag
- completion status
- automatic package completion when all requirements are complete

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

## Time / Expense
- worker time entry by day
- automatic regular/overtime split after 40h
- submit / approve / reject
- client/approver portal
- expenses with category, amount, receipt reference and approval status

## Finance
- purchase orders
- invoices
- issue status and due date
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
- UDF definitions
- automation-rule registry
- integration registry
- reset/seed support

## External services requiring real credentials
The internal workflow and mapping exist, but live calls require customer/vendor credentials for: real job boards, LinkedIn, Fieldglass/Beeline, background screening, payroll/GL, production email/SMS/VOIP, government verification and production e-sign services.
