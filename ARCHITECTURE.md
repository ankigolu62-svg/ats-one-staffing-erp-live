# Architecture

```text
Browser sessions (Admin / Recruiter / Sales / HR / Finance / Client / Candidate / Worker / Supplier / Approver)
                                  |
                                  v
                    Threaded local HTTP/API server
                                  |
             +--------------------+------------------+
             |                    |                  |
             v                    v                  v
        Auth + RBAC        Workflow/Search       Audit log
             |                    |                  |
             +--------------------+------------------+
                                  |
                                  v
                         SQLite shared database
                             WAL enabled
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
```

The browser never owns authoritative business data; it calls the shared server API. This is intentionally different from the earlier localStorage demo.
