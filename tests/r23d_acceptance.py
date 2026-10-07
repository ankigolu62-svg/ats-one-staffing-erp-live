from __future__ import annotations

import sqlite3
import sys
from pathlib import Path


ROOT = Path(
    sys.argv[1]
).resolve()


sys.path.insert(
    0,
    str(ROOT),
)


from r23d_ops import (
    PROFILE_ALIASES,
    ensure_r23d_schema,
    r23d_get,
    r23d_post,
)


class H:

    def __init__(self):

        self.status = None
        self.payload = None


    def _json(
        self,
        payload,
        status=200,
        headers=None,
    ):

        self.status = status
        self.payload = payload


def get(
    conn,
    user,
    path,
):

    h = H()

    assert r23d_get(
        h,
        conn,
        user,
        path,
        {},
    )

    return h


def post(
    conn,
    user,
    path,
    data,
):

    h = H()

    assert r23d_post(
        h,
        conn,
        user,
        path,
        data,
    )

    return h


conn = sqlite3.connect(
    ":memory:"
)

conn.row_factory = sqlite3.Row


conn.executescript(
    """
    CREATE TABLE tenants(
        id INTEGER PRIMARY KEY,
        name TEXT
    );

    CREATE TABLE users(
        id INTEGER PRIMARY KEY,
        name TEXT,
        email TEXT,
        role TEXT,
        active INTEGER,
        tenant_id INTEGER
    );

    CREATE TABLE companies(
        id INTEGER PRIMARY KEY,
        name TEXT,
        tenant_id INTEGER
    );

    CREATE TABLE candidates(
        id INTEGER PRIMARY KEY,
        first_name TEXT,
        last_name TEXT,
        tenant_id INTEGER
    );

    CREATE TABLE jobs(
        id INTEGER PRIMARY KEY,
        job_no TEXT,
        title TEXT,
        company_id INTEGER,
        status TEXT,
        tenant_id INTEGER
    );

    CREATE TABLE submissions(
        id INTEGER PRIMARY KEY,
        job_id INTEGER,
        candidate_id INTEGER,
        recruiter_id INTEGER,
        status TEXT,
        submitted_at TEXT,
        created_at TEXT,
        updated_at TEXT,
        tenant_id INTEGER
    );

    CREATE TABLE interviews(
        id INTEGER PRIMARY KEY,
        submission_id INTEGER,
        status TEXT,
        rating INTEGER
    );

    CREATE TABLE assessments(
        id INTEGER PRIMARY KEY,
        candidate_id INTEGER,
        job_id INTEGER,
        title TEXT,
        assessment_type TEXT,
        status TEXT,
        score REAL,
        max_score REAL,
        invited_at TEXT,
        completed_at TEXT,
        tenant_id INTEGER
    );

    CREATE TABLE onboarding_packages(
        id INTEGER PRIMARY KEY,
        candidate_id INTEGER,
        job_id INTEGER,
        submission_id INTEGER,
        package_name TEXT,
        status TEXT,
        assigned_by INTEGER,
        due_date TEXT,
        created_at TEXT,
        tenant_id INTEGER
    );

    CREATE TABLE onboarding_requirements(
        id INTEGER PRIMARY KEY,
        package_id INTEGER,
        requirement_type TEXT,
        name TEXT,
        mandatory INTEGER,
        status TEXT,
        completed_at TEXT,
        expiry_date TEXT,
        note TEXT
    );

    CREATE TABLE assignments(
        id INTEGER PRIMARY KEY,
        candidate_id INTEGER,
        job_id INTEGER,
        company_id INTEGER,
        status TEXT,
        start_date TEXT,
        end_date TEXT,
        bill_rate REAL,
        pay_rate REAL,
        updated_at TEXT,
        tenant_id INTEGER
    );

    CREATE TABLE timesheets(
        id INTEGER PRIMARY KEY,
        assignment_id INTEGER,
        candidate_id INTEGER,
        week_start TEXT,
        status TEXT,
        total_hours REAL,
        tenant_id INTEGER
    );

    CREATE TABLE invoices(
        id INTEGER PRIMARY KEY,
        invoice_no TEXT,
        company_id INTEGER,
        assignment_id INTEGER,
        amount REAL,
        tax REAL,
        status TEXT,
        due_date TEXT,
        issued_at TEXT,
        tenant_id INTEGER
    );

    CREATE TABLE invoice_payments(
        id INTEGER PRIMARY KEY,
        invoice_id INTEGER,
        amount REAL,
        tenant_id INTEGER
    );

    CREATE TABLE suppliers(
        id INTEGER PRIMARY KEY,
        name TEXT,
        tenant_id INTEGER
    );


    INSERT INTO tenants
    VALUES(
        1,
        'Tenant'
    );


    INSERT INTO users
    VALUES(
        1,
        'Admin User',
        'admin@test',
        'admin',
        1,
        1
    );

    INSERT INTO users
    VALUES(
        2,
        'Recruiter One',
        'recruiter@test',
        'recruiter',
        1,
        1
    );

    INSERT INTO users
    VALUES(
        3,
        'Finance User',
        'finance@test',
        'finance',
        1,
        1
    );


    INSERT INTO companies
    VALUES(
        1,
        'Client One',
        1
    );


    INSERT INTO candidates
    VALUES(
        1,
        'Candidate',
        'One',
        1
    );


    INSERT INTO jobs
    VALUES(
        1,
        'JOB-1',
        'Java Developer',
        1,
        'Open',
        1
    );


    INSERT INTO submissions
    VALUES(
        1,
        1,
        1,
        2,
        'hired',
        '2026-10-01',
        '2026-10-01',
        '2026-10-01',
        1
    );


    INSERT INTO interviews
    VALUES(
        1,
        1,
        'completed',
        5
    );


    INSERT INTO assessments
    VALUES(
        1,
        1,
        1,
        'Technical e-Interview',
        'e-Interview',
        'Completed',
        88,
        100,
        '2026-10-01',
        '2026-10-02',
        1
    );


    INSERT INTO onboarding_packages
    VALUES(
        1,
        1,
        1,
        1,
        'Standard Onboarding',
        'in_progress',
        1,
        '2026-01-01',
        '2026-01-01',
        1
    );


    INSERT INTO onboarding_requirements
    VALUES(
        1,
        1,
        'Document',
        'License',
        1,
        'Pending',
        NULL,
        '2026-10-20',
        ''
    );


    INSERT INTO assignments
    VALUES(
        1,
        1,
        1,
        1,
        'active',
        '2026-10-01',
        NULL,
        100,
        60,
        '2026-10-01',
        1
    );


    INSERT INTO timesheets
    VALUES(
        1,
        1,
        1,
        '2026-10-05',
        'approved',
        40,
        1
    );


    INSERT INTO invoices
    VALUES(
        1,
        'INV-001',
        1,
        1,
        4000,
        0,
        'issued',
        '2026-09-01',
        '2026-08-01',
        1
    );


    INSERT INTO invoice_payments
    VALUES(
        1,
        1,
        1000,
        1
    );


    INSERT INTO suppliers
    VALUES(
        1,
        'Supplier One',
        1
    );
    """
)


ensure_r23d_schema(
    conn
)


admin = dict(
    conn.execute(
        "SELECT * FROM users WHERE id=1"
    ).fetchone()
)


recruiter = dict(
    conn.execute(
        "SELECT * FROM users WHERE id=2"
    ).fetchone()
)


finance = dict(
    conn.execute(
        "SELECT * FROM users WHERE id=3"
    ).fetchone()
)


# -------------------------------------------------------------
# Profile / team aliases
# -------------------------------------------------------------

coverage = get(
    conn,
    admin,
    "/api/r23d/coverage",
)


assert coverage.status == 200

assert (
    coverage.payload[
        "choose_team"
    ]
    ==
    "Choose Team / Profile"
)


expected_aliases = {
    "HR Workforce Operations",
    "Billing Accounts Receivable",
    "VMS MSP Coordinator",
    "Supplier Vendor Manager",
    "Reporting BI User",
    "Client Hiring Manager",
    "Worker Contractor",
    "Timesheet Expense Approver",
}


assert expected_aliases.issubset(
    set(
        PROFILE_ALIASES.values()
    )
)


print(
    "R23D_CHOOSE_TEAM_PROFILE=PASS"
)

print(
    "R23D_ENTERPRISE_PROFILE_ALIASES=PASS"
)


# -------------------------------------------------------------
# Onboarding Dashboard
# -------------------------------------------------------------

h = get(
    conn,
    recruiter,
    "/api/r23d/onboarding-dashboard",
)


assert h.status == 200

assert h.payload[
    "total"
] == 1

assert h.payload[
    "incomplete"
] == 1

assert h.payload[
    "overdue"
] == 1


print(
    "R23D_ONBOARDING_DASHBOARD=PASS"
)


# -------------------------------------------------------------
# e-Interview Dashboard
# -------------------------------------------------------------

h = get(
    conn,
    recruiter,
    "/api/r23d/e-interview-dashboard",
)


assert h.status == 200

assert h.payload[
    "completed"
] == 1

assert h.payload[
    "total_interviews"
] == 1


print(
    "R23D_EINTERVIEW_DASHBOARD=PASS"
)


# -------------------------------------------------------------
# Recruiting Leaderboard
# -------------------------------------------------------------

h = get(
    conn,
    admin,
    "/api/r23d/recruiting-leaderboard",
)


assert h.status == 200

row = next(
    x
    for x in h.payload["rows"]
    if x["id"] == 2
)


assert row[
    "submissions"
] == 1

assert row[
    "interviews"
] == 1

assert row[
    "placements"
] == 1


print(
    "R23D_RECRUITING_LEADERBOARD=PASS"
)


# -------------------------------------------------------------
# Margin / CalcuDiva
# -------------------------------------------------------------

h = post(
    conn,
    finance,
    "/api/r23d/margin-calculator",
    {
        "bill_rate":
            100,

        "pay_rate":
            60,

        "burden_percent":
            10,

        "target_margin_percent":
            25,
    },
)


assert h.status == 200

assert round(
    h.payload[
        "loaded_cost"
    ],
    2,
) == 66.00

assert round(
    h.payload[
        "gross_profit"
    ],
    2,
) == 34.00

assert (
    h.payload[
        "target_bill_rate"
    ]
    is not None
)


print(
    "R23D_CALCUDIVA_MARGIN_CALCULATOR=PASS"
)


# -------------------------------------------------------------
# Job board quota/account
# -------------------------------------------------------------

h = post(
    conn,
    admin,
    "/api/r23d/job-board-accounts",
    {
        "provider":
            "Monster",

        "account_name":
            "Production",

        "quota_total":
            100,

        "quota_used":
            30,

        "quota_reset_at":
            "2026-11-01",
    },
)


assert h.status == 201


h = get(
    conn,
    recruiter,
    "/api/r23d/job-board-accounts",
)


assert h.status == 200

assert len(
    h.payload[
        "accounts"
    ]
) == 1

assert h.payload[
    "accounts"
][0][
    "quota_remaining"
] == 70


print(
    "R23D_JOB_BOARD_QUOTA_ACCOUNT_VISIBILITY=PASS"
)


# -------------------------------------------------------------
# Collections
# -------------------------------------------------------------

h = get(
    conn,
    finance,
    "/api/r23d/collections",
)


assert h.status == 200

assert round(
    h.payload[
        "total_outstanding"
    ],
    2,
) == 3000.00


h = post(
    conn,
    finance,
    "/api/r23d/collections/1/action",
    {
        "action_type":
            "Promise To Pay",

        "status":
            "Promise To Pay",

        "promised_amount":
            2000,

        "promise_date":
            "2026-10-15",

        "note":
            "Client committed payment",
    },
)


assert h.status == 201


h = get(
    conn,
    finance,
    "/api/r23d/collections",
)


assert (
    h.payload[
        "invoices"
    ][0][
        "latest_collection"
    ][
        "action_type"
    ]
    ==
    "Promise To Pay"
)


print(
    "R23D_AR_COLLECTIONS_WORKFLOW=PASS"
)


# -------------------------------------------------------------
# Profitability
# -------------------------------------------------------------

h = get(
    conn,
    finance,
    "/api/r23d/profitability",
)


assert h.status == 200

assert round(
    h.payload[
        "revenue"
    ],
    2,
) == 4000.00

assert round(
    h.payload[
        "cost"
    ],
    2,
) == 2400.00

assert round(
    h.payload[
        "gross_margin"
    ],
    2,
) == 1600.00

assert round(
    h.payload[
        "margin_percent"
    ],
    2,
) == 40.00


print(
    "R23D_CLIENT_JOB_PROFITABILITY=PASS"
)


# -------------------------------------------------------------
# VMS supplier / worker offboarding
# -------------------------------------------------------------

h = post(
    conn,
    admin,
    "/api/r23d/vms-offboarding",
    {
        "assignment_id":
            1,

        "supplier_id":
            1,

        "termination_reason":
            "Assignment completed by client",
    },
)


assert h.status == 201

offboarding_id = int(
    h.payload[
        "id"
    ]
)


assignment = dict(
    conn.execute(
        """
        SELECT *
        FROM assignments
        WHERE id=1
        """
    ).fetchone()
)


assert (
    assignment[
        "status"
    ]
    ==
    "offboarding"
)


h = get(
    conn,
    admin,
    "/api/r23d/vms-offboarding",
)


assert len(
    h.payload[
        "cases"
    ]
) == 1

assert (
    h.payload[
        "cases"
    ][0][
        "termination_reason"
    ]
    ==
    "Assignment completed by client"
)


h = post(
    conn,
    admin,
    f"/api/r23d/vms-offboarding/{offboarding_id}/complete",
    {},
)


assert h.status == 200


assignment = dict(
    conn.execute(
        """
        SELECT *
        FROM assignments
        WHERE id=1
        """
    ).fetchone()
)


assert (
    assignment[
        "status"
    ]
    ==
    "completed"
)


print(
    "R23D_SUPPLIER_WORKER_OFFBOARDING=PASS"
)


# -------------------------------------------------------------
# Role boundaries
# -------------------------------------------------------------

h = post(
    conn,
    recruiter,
    "/api/r23d/margin-calculator",
    {
        "bill_rate":
            100,

        "pay_rate":
            60,
    },
)


assert h.status == 403


h = post(
    conn,
    finance,
    "/api/r23d/job-board-accounts",
    {
        "provider":
            "X",

        "account_name":
            "X",
    },
)


assert h.status == 403


print(
    "R23D_ROLE_SECURITY_BOUNDARIES=PASS"
)


# -------------------------------------------------------------
# UI/server hooks
# -------------------------------------------------------------

server = (
    ROOT / "server.py"
).read_text(
    encoding="utf-8"
)


index = (
    ROOT / "web" / "index.html"
).read_text(
    encoding="utf-8"
)


js = (
    ROOT / "web" / "r23d.js"
).read_text(
    encoding="utf-8"
)


assert (
    "ensure_r23d_schema(conn)"
    in server
)

assert (
    "r23d_get(self,conn,u,path,qs)"
    in server
)

assert (
    "r23d_post(self,conn,u,path,data)"
    in server
)

assert (
    '/r23d.js?v=R23D-1'
    in index
)

for phrase in [
    "Choose Team / Profile",
    "Onboarding Dashboard",
    "e-Interview Dashboard",
    "Recruiting Leaderboard",
    "CalcuDiva Margin Calculator",
    "Job Board Quota / Account Visibility",
    "Collections Workflow",
    "Client / Job Profitability",
    "Supplier / Worker Offboarding and Termination",
]:

    assert phrase in js


print(
    "R23D_SERVER_UI_INTEGRATION=PASS"
)

print(
    "R23D_REMAINING_NON_AI_GAPS=PASS"
)
