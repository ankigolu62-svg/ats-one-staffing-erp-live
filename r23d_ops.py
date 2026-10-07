from __future__ import annotations

import re
from datetime import datetime, timezone


# ---------------------------------------------------------------------
# Enterprise profile aliases.
# These are human-readable operating-profile names, not new security
# bypasses. Existing RBAC remains the authority.
# ---------------------------------------------------------------------

PROFILE_ALIASES = {
    "hr_workforce_operations":
        "HR Workforce Operations",

    "billing_accounts_receivable":
        "Billing Accounts Receivable",

    "vms_msp_coordinator":
        "VMS MSP Coordinator",

    "supplier_vendor_manager":
        "Supplier Vendor Manager",

    "reporting_bi_user":
        "Reporting BI User",

    "client_hiring_manager":
        "Client Hiring Manager",

    "worker_contractor":
        "Worker Contractor",

    "timesheet_expense_approver":
        "Timesheet Expense Approver",
}


CHOOSE_TEAM_LABEL = "Choose Team / Profile"

ONBOARDING_DASHBOARD_LABEL = "Onboarding Dashboard"

EINTERVIEW_DASHBOARD_LABEL = "e-Interview Dashboard"

RECRUITING_LEADERBOARD_LABEL = "Recruiting Leaderboard"

CALCUDIVA_LABEL = "CalcuDiva Margin Calculator"

JOB_BOARD_QUOTA_LABEL = "Job Board Quota / Account Visibility"

COLLECTIONS_WORKFLOW_LABEL = "Collections Workflow"

PROFITABILITY_LABEL = "Client / Job Profitability"

OFFBOARDING_LABEL = (
    "Supplier / Worker Offboarding and Termination"
)


INTERNAL = {
    "admin",
    "teamlead",
    "recruiter",
    "sales",
    "hr",
    "finance",
}


RECRUITING = {
    "admin",
    "teamlead",
    "recruiter",
    "sales",
    "hr",
}


FINANCE = {
    "admin",
    "finance",
}


VMS_ADMIN = {
    "admin",
    "teamlead",
    "hr",
}


def now():

    return datetime.now(
        timezone.utc
    ).replace(
        microsecond=0
    ).isoformat()


def rows(
    conn,
    sql,
    params=(),
):

    return [
        dict(x)
        for x in conn.execute(
            sql,
            params,
        ).fetchall()
    ]


def one(
    conn,
    sql,
    params=(),
):

    x = conn.execute(
        sql,
        params,
    ).fetchone()

    return (
        dict(x)
        if x
        else None
    )


def send(
    h,
    payload,
    status=200,
):

    h._json(
        payload,
        status,
    )

    return True


def ensure_r23d_schema(conn):

    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS
        job_board_accounts_r23d(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id INTEGER NOT NULL,
            provider TEXT NOT NULL,
            account_name TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Active',

            quota_total INTEGER NOT NULL DEFAULT 0,
            quota_used INTEGER NOT NULL DEFAULT 0,
            quota_reset_at TEXT,

            contract_start TEXT,
            contract_end TEXT,

            created_by INTEGER,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,

            UNIQUE(
                tenant_id,
                provider,
                account_name
            )
        );

        CREATE TABLE IF NOT EXISTS
        ar_collections_r23d(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id INTEGER NOT NULL,
            invoice_id INTEGER NOT NULL,

            action_type TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Open',

            promised_amount REAL,
            promise_date TEXT,

            note TEXT,
            assigned_to INTEGER,

            created_by INTEGER,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS
        vms_offboarding_r23d(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id INTEGER NOT NULL,

            assignment_id INTEGER NOT NULL,
            supplier_id INTEGER,
            candidate_id INTEGER NOT NULL,

            status TEXT NOT NULL DEFAULT 'Requested',

            termination_reason TEXT,
            requested_at TEXT NOT NULL,
            completed_at TEXT,

            created_by INTEGER,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS
        idx_job_board_accounts_r23d_tenant
        ON job_board_accounts_r23d(
            tenant_id,
            status
        );

        CREATE INDEX IF NOT EXISTS
        idx_ar_collections_r23d_invoice
        ON ar_collections_r23d(
            tenant_id,
            invoice_id,
            id
        );

        CREATE INDEX IF NOT EXISTS
        idx_vms_offboarding_r23d_assignment
        ON vms_offboarding_r23d(
            tenant_id,
            assignment_id,
            id
        );
        """
    )

    conn.commit()


def _onboarding_dashboard(
    conn,
    tenant_id,
):

    packages = one(
        conn,
        """
        SELECT
            COUNT(*) total,
            SUM(
                CASE
                    WHEN lower(status) IN (
                        'complete',
                        'completed'
                    )
                    THEN 1
                    ELSE 0
                END
            ) completed,

            SUM(
                CASE
                    WHEN lower(status) NOT IN (
                        'complete',
                        'completed'
                    )
                    THEN 1
                    ELSE 0
                END
            ) incomplete,

            SUM(
                CASE
                    WHEN due_date IS NOT NULL
                     AND date(due_date) < date('now')
                     AND lower(status) NOT IN (
                        'complete',
                        'completed'
                     )
                    THEN 1
                    ELSE 0
                END
            ) overdue

        FROM onboarding_packages

        WHERE tenant_id=?
        """,
        (
            tenant_id,
        ),
    ) or {}


    req = one(
        conn,
        """
        SELECT
            COUNT(*) total_requirements,

            SUM(
                CASE
                    WHEN lower(r.status) IN (
                        'complete',
                        'completed',
                        'verified'
                    )
                    THEN 1
                    ELSE 0
                END
            ) completed_requirements,

            SUM(
                CASE
                    WHEN r.expiry_date IS NOT NULL
                     AND date(r.expiry_date)
                         BETWEEN date('now')
                             AND date('now','+30 day')
                    THEN 1
                    ELSE 0
                END
            ) expiring_30_days

        FROM onboarding_requirements r

        JOIN onboarding_packages p
          ON p.id=r.package_id

        WHERE p.tenant_id=?
        """,
        (
            tenant_id,
        ),
    ) or {}


    overdue_rows = rows(
        conn,
        """
        SELECT
            p.id,
            p.candidate_id,
            p.job_id,
            p.package_name,
            p.status,
            p.due_date,

            c.first_name,
            c.last_name,

            j.job_no,
            j.title

        FROM onboarding_packages p

        LEFT JOIN candidates c
          ON c.id=p.candidate_id
         AND c.tenant_id=p.tenant_id

        LEFT JOIN jobs j
          ON j.id=p.job_id
         AND j.tenant_id=p.tenant_id

        WHERE p.tenant_id=?
          AND p.due_date IS NOT NULL
          AND date(p.due_date) < date('now')
          AND lower(p.status) NOT IN (
              'complete',
              'completed'
          )

        ORDER BY p.due_date,p.id

        LIMIT 100
        """,
        (
            tenant_id,
        ),
    )


    return {
        "label":
            ONBOARDING_DASHBOARD_LABEL,

        "total":
            int(
                packages.get("total")
                or 0
            ),

        "completed":
            int(
                packages.get("completed")
                or 0
            ),

        "incomplete":
            int(
                packages.get("incomplete")
                or 0
            ),

        "overdue":
            int(
                packages.get("overdue")
                or 0
            ),

        "total_requirements":
            int(
                req.get("total_requirements")
                or 0
            ),

        "completed_requirements":
            int(
                req.get("completed_requirements")
                or 0
            ),

        "expiring_30_days":
            int(
                req.get("expiring_30_days")
                or 0
            ),

        "overdue_packages":
            overdue_rows,
    }


def _einterview_dashboard(
    conn,
    tenant_id,
):

    assessment = one(
        conn,
        """
        SELECT
            COUNT(*) invited,

            SUM(
                CASE
                    WHEN lower(status)='completed'
                    THEN 1
                    ELSE 0
                END
            ) completed,

            AVG(
                CASE
                    WHEN score IS NOT NULL
                    THEN score
                    ELSE NULL
                END
            ) avg_score

        FROM assessments

        WHERE tenant_id=?
        """,
        (
            tenant_id,
        ),
    ) or {}


    interviews = one(
        conn,
        """
        SELECT
            COUNT(*) total_interviews,

            SUM(
                CASE
                    WHEN lower(i.status) IN (
                        'completed',
                        'complete'
                    )
                    THEN 1
                    ELSE 0
                END
            ) completed_interviews,

            SUM(
                CASE
                    WHEN lower(i.status) IN (
                        'no_show',
                        'no show'
                    )
                    THEN 1
                    ELSE 0
                END
            ) no_show

        FROM interviews i

        JOIN submissions s
          ON s.id=i.submission_id

        WHERE s.tenant_id=?
        """,
        (
            tenant_id,
        ),
    ) or {}


    recent = rows(
        conn,
        """
        SELECT
            a.id,
            a.candidate_id,
            a.job_id,
            a.title,
            a.assessment_type,
            a.status,
            a.score,
            a.max_score,
            a.invited_at,
            a.completed_at,

            c.first_name,
            c.last_name,

            j.job_no,
            j.title AS job_title

        FROM assessments a

        LEFT JOIN candidates c
          ON c.id=a.candidate_id
         AND c.tenant_id=a.tenant_id

        LEFT JOIN jobs j
          ON j.id=a.job_id
         AND j.tenant_id=a.tenant_id

        WHERE a.tenant_id=?

        ORDER BY a.id DESC

        LIMIT 100
        """,
        (
            tenant_id,
        ),
    )


    return {
        "label":
            EINTERVIEW_DASHBOARD_LABEL,

        "invited":
            int(
                assessment.get("invited")
                or 0
            ),

        "completed":
            int(
                assessment.get("completed")
                or 0
            ),

        "average_score":
            round(
                float(
                    assessment.get("avg_score")
                    or 0
                ),
                2,
            ),

        "total_interviews":
            int(
                interviews.get("total_interviews")
                or 0
            ),

        "completed_interviews":
            int(
                interviews.get("completed_interviews")
                or 0
            ),

        "no_show":
            int(
                interviews.get("no_show")
                or 0
            ),

        "recent":
            recent,
    }


def _recruiting_leaderboard(
    conn,
    tenant_id,
):

    result = rows(
        conn,
        """
        SELECT
            u.id,
            u.name,
            u.role,

            (
                SELECT COUNT(*)
                FROM submissions s
                WHERE s.tenant_id=?
                  AND s.recruiter_id=u.id
            ) submissions,

            (
                SELECT COUNT(*)
                FROM interviews i
                JOIN submissions s2
                  ON s2.id=i.submission_id
                WHERE s2.tenant_id=?
                  AND s2.recruiter_id=u.id
            ) interviews,

            (
                SELECT COUNT(*)
                FROM submissions s3
                WHERE s3.tenant_id=?
                  AND s3.recruiter_id=u.id
                  AND lower(s3.status) IN (
                      'hired',
                      'placed',
                      'start',
                      'started'
                  )
            ) placements

        FROM users u

        WHERE u.tenant_id=?
          AND u.active=1
          AND u.role IN (
              'admin',
              'teamlead',
              'recruiter',
              'sales'
          )

        ORDER BY
            placements DESC,
            interviews DESC,
            submissions DESC,
            u.name
        """,
        (
            tenant_id,
            tenant_id,
            tenant_id,
            tenant_id,
        ),
    )


    for idx,item in enumerate(
        result,
        1,
    ):

        item["rank"] = idx

        item["activity_score"] = (
            int(
                item.get("submissions")
                or 0
            )
            +
            int(
                item.get("interviews")
                or 0
            ) * 2
            +
            int(
                item.get("placements")
                or 0
            ) * 5
        )


    result.sort(
        key=lambda x:(
            -x["activity_score"],
            str(
                x.get("name")
                or ""
            ).lower(),
        )
    )


    for idx,item in enumerate(
        result,
        1,
    ):
        item["rank"] = idx


    return {
        "label":
            RECRUITING_LEADERBOARD_LABEL,

        "rows":
            result,
    }


def _job_board_accounts(
    conn,
    tenant_id,
):

    result = rows(
        conn,
        """
        SELECT *
        FROM job_board_accounts_r23d
        WHERE tenant_id=?
        ORDER BY
            status DESC,
            provider,
            account_name
        """,
        (
            tenant_id,
        ),
    )


    for item in result:

        item["quota_remaining"] = max(
            0,
            int(
                item.get("quota_total")
                or 0
            )
            -
            int(
                item.get("quota_used")
                or 0
            ),
        )


    return {
        "label":
            JOB_BOARD_QUOTA_LABEL,

        "accounts":
            result,
    }


def _collections(
    conn,
    tenant_id,
):

    invoice_rows = rows(
        conn,
        """
        SELECT
            i.id,
            i.invoice_no,
            i.company_id,
            i.assignment_id,
            i.amount,
            i.tax,
            i.status,
            i.due_date,
            i.issued_at,

            COALESCE(
                (
                    SELECT SUM(p.amount)
                    FROM invoice_payments p
                    WHERE p.invoice_id=i.id
                      AND p.tenant_id=i.tenant_id
                ),
                0
            ) paid_amount,

            CASE
                WHEN i.due_date IS NOT NULL
                THEN CAST(
                    julianday('now')
                    -
                    julianday(i.due_date)
                    AS INTEGER
                )
                ELSE 0
            END aging_days,

            c.name AS company_name

        FROM invoices i

        LEFT JOIN companies c
          ON c.id=i.company_id
         AND c.tenant_id=i.tenant_id

        WHERE i.tenant_id=?
          AND lower(i.status) NOT IN (
              'paid',
              'void'
          )

        ORDER BY
            aging_days DESC,
            i.id DESC
        """,
        (
            tenant_id,
        ),
    )


    for item in invoice_rows:

        gross = (
            float(
                item.get("amount")
                or 0
            )
            +
            float(
                item.get("tax")
                or 0
            )
        )

        paid = float(
            item.get("paid_amount")
            or 0
        )

        item["balance"] = round(
            max(
                0.0,
                gross-paid,
            ),
            2,
        )

        item["latest_collection"] = one(
            conn,
            """
            SELECT *
            FROM ar_collections_r23d
            WHERE tenant_id=?
              AND invoice_id=?
            ORDER BY id DESC
            LIMIT 1
            """,
            (
                tenant_id,
                item["id"],
            ),
        )


    return {
        "label":
            COLLECTIONS_WORKFLOW_LABEL,

        "invoices":
            invoice_rows,

        "total_outstanding":
            round(
                sum(
                    float(
                        x.get("balance")
                        or 0
                    )
                    for x in invoice_rows
                ),
                2,
            ),
    }


def _profitability(
    conn,
    tenant_id,
):

    assignment_rows = rows(
        conn,
        """
        SELECT
            a.id AS assignment_id,
            a.job_id,
            a.company_id,
            a.bill_rate,
            a.pay_rate,
            a.status,

            j.job_no,
            j.title AS job_title,

            c.name AS company_name,

            COALESCE(
                (
                    SELECT SUM(t.total_hours)
                    FROM timesheets t
                    WHERE t.tenant_id=a.tenant_id
                      AND t.assignment_id=a.id
                      AND lower(t.status)='approved'
                ),
                0
            ) approved_hours

        FROM assignments a

        LEFT JOIN jobs j
          ON j.id=a.job_id
         AND j.tenant_id=a.tenant_id

        LEFT JOIN companies c
          ON c.id=a.company_id
         AND c.tenant_id=a.tenant_id

        WHERE a.tenant_id=?

        ORDER BY a.id DESC
        """,
        (
            tenant_id,
        ),
    )


    total_revenue = 0.0
    total_cost = 0.0


    for item in assignment_rows:

        hours = float(
            item.get("approved_hours")
            or 0
        )

        bill = float(
            item.get("bill_rate")
            or 0
        )

        pay = float(
            item.get("pay_rate")
            or 0
        )

        revenue = (
            hours
            * bill
        )

        cost = (
            hours
            * pay
        )

        gross_margin = (
            revenue
            -
            cost
        )

        margin_percent = (
            (
                gross_margin
                /
                revenue
            )
            *100
            if revenue > 0
            else 0
        )

        item["revenue"] = round(
            revenue,
            2,
        )

        item["cost"] = round(
            cost,
            2,
        )

        item["gross_margin"] = round(
            gross_margin,
            2,
        )

        item["margin_percent"] = round(
            margin_percent,
            2,
        )

        total_revenue += revenue
        total_cost += cost


    total_margin = (
        total_revenue
        -
        total_cost
    )


    return {
        "label":
            PROFITABILITY_LABEL,

        "rows":
            assignment_rows,

        "revenue":
            round(
                total_revenue,
                2,
            ),

        "cost":
            round(
                total_cost,
                2,
            ),

        "gross_margin":
            round(
                total_margin,
                2,
            ),

        "margin_percent":
            round(
                (
                    total_margin
                    /
                    total_revenue
                )*100
                if total_revenue > 0
                else 0,
                2,
            ),
    }


def _offboarding(
    conn,
    tenant_id,
):

    return {
        "label":
            OFFBOARDING_LABEL,

        "cases":
            rows(
                conn,
                """
                SELECT
                    o.*,

                    c.first_name,
                    c.last_name,

                    j.job_no,
                    j.title AS job_title,

                    s.name AS supplier_name

                FROM vms_offboarding_r23d o

                LEFT JOIN candidates c
                  ON c.id=o.candidate_id
                 AND c.tenant_id=o.tenant_id

                LEFT JOIN assignments a
                  ON a.id=o.assignment_id
                 AND a.tenant_id=o.tenant_id

                LEFT JOIN jobs j
                  ON j.id=a.job_id
                 AND j.tenant_id=a.tenant_id

                LEFT JOIN suppliers s
                  ON s.id=o.supplier_id
                 AND s.tenant_id=o.tenant_id

                WHERE o.tenant_id=?

                ORDER BY o.id DESC
                """,
                (
                    tenant_id,
                ),
            ),
    }


def _margin_calculator(
    data,
):

    try:

        bill_rate = float(
            data.get(
                "bill_rate"
            )
            or 0
        )

        pay_rate = float(
            data.get(
                "pay_rate"
            )
            or 0
        )

        burden_percent = float(
            data.get(
                "burden_percent"
            )
            or 0
        )

        target_margin_percent = float(
            data.get(
                "target_margin_percent"
            )
            or 0
        )

    except Exception:

        raise ValueError(
            "Rates and percentages must be numeric"
        )


    if (
        bill_rate < 0
        or pay_rate < 0
        or burden_percent < 0
    ):

        raise ValueError(
            "Rates and percentages cannot be negative"
        )


    loaded_cost = (
        pay_rate
        *
        (
            1
            +
            burden_percent
            /
            100
        )
    )


    gross_profit = (
        bill_rate
        -
        loaded_cost
    )


    margin_percent = (
        (
            gross_profit
            /
            bill_rate
        )
        *100
        if bill_rate > 0
        else 0
    )


    markup_percent = (
        (
            gross_profit
            /
            loaded_cost
        )
        *100
        if loaded_cost > 0
        else 0
    )


    target_bill_rate = None


    if (
        target_margin_percent > 0
        and target_margin_percent < 100
    ):

        target_bill_rate = (
            loaded_cost
            /
            (
                1
                -
                target_margin_percent
                /
                100
            )
        )


    return {
        "label":
            CALCUDIVA_LABEL,

        "bill_rate":
            round(
                bill_rate,
                4,
            ),

        "pay_rate":
            round(
                pay_rate,
                4,
            ),

        "burden_percent":
            round(
                burden_percent,
                4,
            ),

        "loaded_cost":
            round(
                loaded_cost,
                4,
            ),

        "gross_profit":
            round(
                gross_profit,
                4,
            ),

        "gross_margin_percent":
            round(
                margin_percent,
                4,
            ),

        "markup_percent":
            round(
                markup_percent,
                4,
            ),

        "target_margin_percent":
            round(
                target_margin_percent,
                4,
            ),

        "target_bill_rate":
            (
                round(
                    target_bill_rate,
                    4,
                )
                if target_bill_rate
                is not None
                else None
            ),
    }


def r23d_get(
    h,
    conn,
    u,
    path,
    qs,
):

    tenant_id = u["tenant_id"]


    if (
        path
        ==
        "/api/r23d/coverage"
    ):

        return send(
            h,
            {
                "version":
                    "R23D",

                "choose_team":
                    CHOOSE_TEAM_LABEL,

                "profile_aliases":
                    PROFILE_ALIASES,

                "onboarding_dashboard":
                    ONBOARDING_DASHBOARD_LABEL,

                "e_interview_dashboard":
                    EINTERVIEW_DASHBOARD_LABEL,

                "recruiting_leaderboard":
                    RECRUITING_LEADERBOARD_LABEL,

                "margin_calculator":
                    CALCUDIVA_LABEL,

                "job_board_quota":
                    JOB_BOARD_QUOTA_LABEL,

                "collections":
                    COLLECTIONS_WORKFLOW_LABEL,

                "profitability":
                    PROFITABILITY_LABEL,

                "offboarding":
                    OFFBOARDING_LABEL,
            },
        )


    if (
        path
        ==
        "/api/r23d/onboarding-dashboard"
    ):

        if (
            u["role"]
            not in RECRUITING
        ):

            return send(
                h,
                {
                    "error":
                        "Permission denied"
                },
                403,
            )

        return send(
            h,
            _onboarding_dashboard(
                conn,
                tenant_id,
            ),
        )


    if (
        path
        ==
        "/api/r23d/e-interview-dashboard"
    ):

        if (
            u["role"]
            not in RECRUITING
        ):

            return send(
                h,
                {
                    "error":
                        "Permission denied"
                },
                403,
            )

        return send(
            h,
            _einterview_dashboard(
                conn,
                tenant_id,
            ),
        )


    if (
        path
        ==
        "/api/r23d/recruiting-leaderboard"
    ):

        if (
            u["role"]
            not in INTERNAL
        ):

            return send(
                h,
                {
                    "error":
                        "Permission denied"
                },
                403,
            )

        return send(
            h,
            _recruiting_leaderboard(
                conn,
                tenant_id,
            ),
        )


    if (
        path
        ==
        "/api/r23d/job-board-accounts"
    ):

        if (
            u["role"]
            not in {
                "admin",
                "teamlead",
                "recruiter",
            }
        ):

            return send(
                h,
                {
                    "error":
                        "Permission denied"
                },
                403,
            )

        return send(
            h,
            _job_board_accounts(
                conn,
                tenant_id,
            ),
        )


    if (
        path
        ==
        "/api/r23d/collections"
    ):

        if (
            u["role"]
            not in FINANCE
        ):

            return send(
                h,
                {
                    "error":
                        "Permission denied"
                },
                403,
            )

        return send(
            h,
            _collections(
                conn,
                tenant_id,
            ),
        )


    if (
        path
        ==
        "/api/r23d/profitability"
    ):

        if (
            u["role"]
            not in {
                "admin",
                "teamlead",
                "finance",
            }
        ):

            return send(
                h,
                {
                    "error":
                        "Permission denied"
                },
                403,
            )

        return send(
            h,
            _profitability(
                conn,
                tenant_id,
            ),
        )


    if (
        path
        ==
        "/api/r23d/vms-offboarding"
    ):

        if (
            u["role"]
            not in VMS_ADMIN
        ):

            return send(
                h,
                {
                    "error":
                        "Permission denied"
                },
                403,
            )

        return send(
            h,
            _offboarding(
                conn,
                tenant_id,
            ),
        )


    return False


def r23d_post(
    h,
    conn,
    u,
    path,
    data,
):

    tenant_id = u["tenant_id"]


    if (
        path
        ==
        "/api/r23d/margin-calculator"
    ):

        if (
            u["role"]
            not in FINANCE
        ):

            return send(
                h,
                {
                    "error":
                        "Permission denied"
                },
                403,
            )

        try:

            result = _margin_calculator(
                data
            )

        except ValueError as exc:

            return send(
                h,
                {
                    "error":
                        str(exc)
                },
                400,
            )

        return send(
            h,
            result,
        )


    if (
        path
        ==
        "/api/r23d/job-board-accounts"
    ):

        if (
            u["role"]
            !=
            "admin"
        ):

            return send(
                h,
                {
                    "error":
                        "Permission denied"
                },
                403,
            )

        provider = str(
            data.get(
                "provider"
            )
            or ""
        ).strip()[:120]

        account_name = str(
            data.get(
                "account_name"
            )
            or ""
        ).strip()[:160]


        if (
            not provider
            or not account_name
        ):

            return send(
                h,
                {
                    "error":
                        "provider and account_name required"
                },
                400,
            )


        try:

            quota_total = int(
                data.get(
                    "quota_total"
                )
                or 0
            )

            quota_used = int(
                data.get(
                    "quota_used"
                )
                or 0
            )

        except Exception:

            return send(
                h,
                {
                    "error":
                        "quota values must be integers"
                },
                400,
            )


        if (
            quota_total < 0
            or quota_used < 0
        ):

            return send(
                h,
                {
                    "error":
                        "quota values cannot be negative"
                },
                400,
            )


        ts = now()


        conn.execute(
            """
            INSERT INTO job_board_accounts_r23d(
                tenant_id,
                provider,
                account_name,
                status,
                quota_total,
                quota_used,
                quota_reset_at,
                contract_start,
                contract_end,
                created_by,
                created_at,
                updated_at
            )
            VALUES(
                ?,?,?,?,
                ?,?,?,?,?,?,
                ?,?
            )

            ON CONFLICT(
                tenant_id,
                provider,
                account_name
            )

            DO UPDATE SET
                status=excluded.status,
                quota_total=excluded.quota_total,
                quota_used=excluded.quota_used,
                quota_reset_at=excluded.quota_reset_at,
                contract_start=excluded.contract_start,
                contract_end=excluded.contract_end,
                updated_at=excluded.updated_at
            """,
            (
                tenant_id,
                provider,
                account_name,
                str(
                    data.get(
                        "status"
                    )
                    or "Active"
                )[:40],
                quota_total,
                quota_used,
                str(
                    data.get(
                        "quota_reset_at"
                    )
                    or ""
                )[:40]
                or None,
                str(
                    data.get(
                        "contract_start"
                    )
                    or ""
                )[:40]
                or None,
                str(
                    data.get(
                        "contract_end"
                    )
                    or ""
                )[:40]
                or None,
                u["id"],
                ts,
                ts,
            ),
        )


        conn.commit()


        return send(
            h,
            _job_board_accounts(
                conn,
                tenant_id,
            ),
            201,
        )


    m = re.fullmatch(
        r"/api/r23d/collections/(\d+)/action",
        path,
    )


    if m:

        if (
            u["role"]
            not in FINANCE
        ):

            return send(
                h,
                {
                    "error":
                        "Permission denied"
                },
                403,
            )


        invoice_id = int(
            m.group(
                1
            )
        )


        invoice = one(
            conn,
            """
            SELECT id,status
            FROM invoices
            WHERE tenant_id=?
              AND id=?
            """,
            (
                tenant_id,
                invoice_id,
            ),
        )


        if not invoice:

            return send(
                h,
                {
                    "error":
                        "Invoice not found"
                },
                404,
            )


        action_type = str(
            data.get(
                "action_type"
            )
            or "Follow Up"
        ).strip()[:100]


        try:

            promised_amount = (
                float(
                    data.get(
                        "promised_amount"
                    )
                )
                if data.get(
                    "promised_amount"
                )
                not in (
                    None,
                    "",
                )
                else None
            )

        except Exception:

            return send(
                h,
                {
                    "error":
                        "promised_amount must be numeric"
                },
                400,
            )


        ts = now()


        cur = conn.execute(
            """
            INSERT INTO ar_collections_r23d(
                tenant_id,
                invoice_id,
                action_type,
                status,
                promised_amount,
                promise_date,
                note,
                assigned_to,
                created_by,
                created_at,
                updated_at
            )
            VALUES(
                ?,?,?,?,?,?,?,?,?,?,?
            )
            """,
            (
                tenant_id,
                invoice_id,
                action_type,
                str(
                    data.get(
                        "status"
                    )
                    or "Open"
                )[:40],
                promised_amount,
                str(
                    data.get(
                        "promise_date"
                    )
                    or ""
                )[:40]
                or None,
                str(
                    data.get(
                        "note"
                    )
                    or ""
                )[:4000],
                (
                    int(
                        data.get(
                            "assigned_to"
                        )
                    )
                    if data.get(
                        "assigned_to"
                    )
                    not in (
                        None,
                        "",
                    )
                    else None
                ),
                u["id"],
                ts,
                ts,
            ),
        )


        conn.commit()


        return send(
            h,
            {
                "id":
                    cur.lastrowid,

                "invoice_id":
                    invoice_id,

                "collections_workflow":
                    True,
            },
            201,
        )


    if (
        path
        ==
        "/api/r23d/vms-offboarding"
    ):

        if (
            u["role"]
            not in VMS_ADMIN
        ):

            return send(
                h,
                {
                    "error":
                        "Permission denied"
                },
                403,
            )


        try:

            assignment_id = int(
                data.get(
                    "assignment_id"
                )
            )

        except Exception:

            return send(
                h,
                {
                    "error":
                        "assignment_id required"
                },
                400,
            )


        assignment = one(
            conn,
            """
            SELECT *
            FROM assignments
            WHERE tenant_id=?
              AND id=?
            """,
            (
                tenant_id,
                assignment_id,
            ),
        )


        if not assignment:

            return send(
                h,
                {
                    "error":
                        "Assignment not found"
                },
                404,
            )


        supplier_id = None


        if data.get(
            "supplier_id"
        ) not in (
            None,
            "",
        ):

            try:

                supplier_id = int(
                    data.get(
                        "supplier_id"
                    )
                )

            except Exception:

                return send(
                    h,
                    {
                        "error":
                            "supplier_id invalid"
                    },
                    400,
                )


            supplier = one(
                conn,
                """
                SELECT id
                FROM suppliers
                WHERE tenant_id=?
                  AND id=?
                """,
                (
                    tenant_id,
                    supplier_id,
                ),
            )


            if not supplier:

                return send(
                    h,
                    {
                        "error":
                            "Supplier not found"
                    },
                    404,
                )


        termination_reason = str(
            data.get(
                "termination_reason"
            )
            or ""
        ).strip()[:2000]


        if not termination_reason:

            return send(
                h,
                {
                    "error":
                        "termination_reason required"
                },
                400,
            )


        ts = now()


        cur = conn.execute(
            """
            INSERT INTO vms_offboarding_r23d(
                tenant_id,
                assignment_id,
                supplier_id,
                candidate_id,
                status,
                termination_reason,
                requested_at,
                completed_at,
                created_by,
                created_at,
                updated_at
            )
            VALUES(
                ?,?,?,?,
                'Requested',
                ?,?,
                NULL,
                ?,?,?
            )
            """,
            (
                tenant_id,
                assignment_id,
                supplier_id,
                assignment[
                    "candidate_id"
                ],
                termination_reason,
                ts,
                u["id"],
                ts,
                ts,
            ),
        )


        conn.execute(
            """
            UPDATE assignments
            SET
                status='offboarding',
                updated_at=?
            WHERE tenant_id=?
              AND id=?
            """,
            (
                ts,
                tenant_id,
                assignment_id,
            ),
        )


        conn.commit()


        return send(
            h,
            {
                "id":
                    cur.lastrowid,

                "assignment_id":
                    assignment_id,

                "status":
                    "Requested",

                "offboarding":
                    True,
            },
            201,
        )


    m = re.fullmatch(
        r"/api/r23d/vms-offboarding/(\d+)/complete",
        path,
    )


    if m:

        if (
            u["role"]
            not in VMS_ADMIN
        ):

            return send(
                h,
                {
                    "error":
                        "Permission denied"
                },
                403,
            )


        case_id = int(
            m.group(
                1
            )
        )


        case = one(
            conn,
            """
            SELECT *
            FROM vms_offboarding_r23d
            WHERE tenant_id=?
              AND id=?
            """,
            (
                tenant_id,
                case_id,
            ),
        )


        if not case:

            return send(
                h,
                {
                    "error":
                        "Offboarding case not found"
                },
                404,
            )


        ts = now()


        conn.execute(
            """
            UPDATE vms_offboarding_r23d
            SET
                status='Completed',
                completed_at=?,
                updated_at=?
            WHERE tenant_id=?
              AND id=?
            """,
            (
                ts,
                ts,
                tenant_id,
                case_id,
            ),
        )


        conn.execute(
            """
            UPDATE assignments
            SET
                status='completed',
                end_date=COALESCE(
                    end_date,
                    substr(?,1,10)
                ),
                updated_at=?
            WHERE tenant_id=?
              AND id=?
            """,
            (
                ts,
                ts,
                tenant_id,
                case[
                    "assignment_id"
                ],
            ),
        )


        conn.commit()


        return send(
            h,
            {
                "ok":
                    True,

                "id":
                    case_id,

                "status":
                    "Completed",
            },
        )


    return False
