from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone


MODULES = [
    "dashboard",
    "talent",
    "candidate",
    "job",
    "crm",
    "submission",
    "interview",
    "onboarding",
    "assignment",
    "timesheet",
    "expense",
    "finance",
    "invoice",
    "report",
    "communication",
    "hotlist",
    "assessment",
    "document",
    "vms",
    "supplier",
    "audit",
    "admin",
    "r14",
]


BASE_MODULES = {
    "admin": set(MODULES),

    "teamlead": {
        "dashboard","talent","candidate","job","crm",
        "submission","interview","onboarding","assignment",
        "timesheet","expense","report","communication",
        "hotlist","assessment","document","vms","supplier",
        "audit","r14",
    },

    "recruiter": {
        "dashboard","talent","candidate","job","submission",
        "interview","onboarding","hotlist","assessment",
        "document","communication","report","r14",
    },

    "sales": {
        "dashboard","crm","job","submission",
        "communication","report","r14",
    },

    "hr": {
        "dashboard","candidate","onboarding","document",
        "assignment","timesheet","expense","report","r14",
    },

    "finance": {
        "dashboard","assignment","timesheet","expense",
        "finance","invoice","report","r14",
    },

    "client": set(),
    "candidate": set(),
    "worker": set(),
    "supplier": set(),
    "approver": set(),
}


PERSONAS = [
    ("System Administrator","system_administrator","admin"),
    ("Recruiting Manager","recruiting_manager","teamlead"),
    ("Team Lead","team_lead","teamlead"),
    ("Recruiter","recruiter","recruiter"),
    ("Sourcer","sourcer","recruiter"),
    ("Sales","sales","sales"),
    ("Business Development","business_development","sales"),
    ("Account Manager","account_manager","sales"),
    ("Onboarding Coordinator","onboarding_coordinator","hr"),
    ("Compliance Specialist","compliance_specialist","hr"),
    ("Credentialing Specialist","credentialing_specialist","hr"),
    ("HR / Workforce Operations","hr_workforce_operations","hr"),
    ("Payroll","payroll","finance"),
    ("Billing / Accounts Receivable","billing_accounts_receivable","finance"),
    ("Finance Manager","finance_manager","finance"),
    ("VMS / MSP Coordinator","vms_msp_coordinator","teamlead"),
    ("Supplier / Vendor Manager","supplier_vendor_manager","teamlead"),
    ("Operations Manager","operations_manager","teamlead"),
    ("Reporting / BI User","reporting_bi_user","teamlead"),
    ("Client / Hiring Manager","client_hiring_manager","client"),
    ("Candidate","candidate","candidate"),
    ("Worker / Contractor","worker_contractor","worker"),
    ("Supplier","supplier","supplier"),
    ("Timesheet / Expense Approver","timesheet_expense_approver","approver"),
]


DEFAULT_PROFILE_BY_ROLE = {
    "admin":"system_administrator",
    "teamlead":"team_lead",
    "recruiter":"recruiter",
    "sales":"sales",
    "hr":"hr_workforce_operations",
    "finance":"finance_manager",
    "client":"client_hiring_manager",
    "candidate":"candidate",
    "worker":"worker_contractor",
    "supplier":"supplier",
    "approver":"timesheet_expense_approver",
}


def now():
    return datetime.now(
        timezone.utc
    ).replace(
        microsecond=0
    ).isoformat()


def rows(conn, sql, params=()):
    return [
        dict(x)
        for x in conn.execute(
            sql,
            params,
        ).fetchall()
    ]


def one(conn, sql, params=()):
    x = conn.execute(
        sql,
        params,
    ).fetchone()

    return dict(x) if x else None


def send(h, payload, status=200):
    h._json(payload, status)
    return True


def slug(value):
    return re.sub(
        r"[^a-z0-9]+",
        "_",
        str(value or "").lower(),
    ).strip("_")[:80]


def token_key(token):
    if not token:
        return None

    return hashlib.sha256(
        str(token).encode("utf-8")
    ).hexdigest()


def ensure_r23_schema(conn):

    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS role_profiles_r23(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            display_name TEXT NOT NULL,
            slug TEXT NOT NULL,
            base_role TEXT NOT NULL,
            description TEXT,
            active INTEGER NOT NULL DEFAULT 1,
            is_system INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(tenant_id,slug)
        );

        CREATE TABLE IF NOT EXISTS profile_permissions_r23(
            profile_id INTEGER NOT NULL,
            module TEXT NOT NULL,
            can_view INTEGER NOT NULL DEFAULT 0,
            can_create INTEGER NOT NULL DEFAULT 0,
            can_edit INTEGER NOT NULL DEFAULT 0,
            can_delete INTEGER NOT NULL DEFAULT 0,
            can_approve INTEGER NOT NULL DEFAULT 0,
            can_export INTEGER NOT NULL DEFAULT 0,
            can_admin INTEGER NOT NULL DEFAULT 0,
            can_financial INTEGER NOT NULL DEFAULT 0,
            can_documents INTEGER NOT NULL DEFAULT 0,
            data_scope TEXT NOT NULL DEFAULT 'all',
            PRIMARY KEY(profile_id,module)
        );

        CREATE TABLE IF NOT EXISTS teams_r23(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            code TEXT NOT NULL,
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(tenant_id,code)
        );

        CREATE TABLE IF NOT EXISTS team_members_r23(
            team_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            profile_id INTEGER NOT NULL,
            is_primary INTEGER NOT NULL DEFAULT 0,
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY(team_id,user_id,profile_id)
        );

        CREATE TABLE IF NOT EXISTS session_context_r23(
            session_key TEXT PRIMARY KEY,
            tenant_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            team_id INTEGER NOT NULL,
            profile_id INTEGER NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS access_log_r23(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id INTEGER NOT NULL,
            user_id INTEGER,
            event_type TEXT NOT NULL,
            path TEXT,
            method TEXT,
            detail TEXT,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS release_notes_r23(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id INTEGER NOT NULL,
            version TEXT NOT NULL,
            title TEXT NOT NULL,
            body TEXT NOT NULL,
            published_at TEXT NOT NULL,
            UNIQUE(tenant_id,version,title)
        );

        CREATE TABLE IF NOT EXISTS help_articles_r23(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id INTEGER NOT NULL,
            category TEXT NOT NULL,
            title TEXT NOT NULL,
            body TEXT NOT NULL,
            active INTEGER NOT NULL DEFAULT 1,
            UNIQUE(tenant_id,category,title)
        );

        CREATE INDEX IF NOT EXISTS idx_r23_profiles
        ON role_profiles_r23(tenant_id,active);

        CREATE INDEX IF NOT EXISTS idx_r23_teams
        ON teams_r23(tenant_id,active);

        CREATE INDEX IF NOT EXISTS idx_r23_members
        ON team_members_r23(user_id,active);

        CREATE INDEX IF NOT EXISTS idx_r23_access
        ON access_log_r23(tenant_id,id);
        """
    )

    for tenant in rows(
        conn,
        "SELECT id FROM tenants",
    ):
        tid = int(tenant["id"])
        ts = now()

        conn.execute(
            """
            INSERT OR IGNORE INTO teams_r23(
                tenant_id,name,code,active,created_at,updated_at
            )
            VALUES(
                ?,'Default Team','default',1,?,?
            )
            """,
            (tid,ts,ts),
        )

        for name, profile_slug, base_role in PERSONAS:
            conn.execute(
                """
                INSERT OR IGNORE INTO role_profiles_r23(
                    tenant_id,name,display_name,slug,base_role,
                    description,active,is_system,created_at,updated_at
                )
                VALUES(
                    ?,?,?,?,?,?,1,1,?,?
                )
                """,
                (
                    tid,
                    name,
                    name,
                    profile_slug,
                    base_role,
                    "Built-in enterprise permission profile: " + name,
                    ts,
                    ts,
                ),
            )

        for profile in rows(
            conn,
            """
            SELECT id,base_role
            FROM role_profiles_r23
            WHERE tenant_id=?
            """,
            (tid,),
        ):
            for module in BASE_MODULES.get(
                profile["base_role"],
                set(),
            ):
                conn.execute(
                    """
                    INSERT OR IGNORE INTO profile_permissions_r23(
                        profile_id,module,
                        can_view,can_create,can_edit,can_delete,
                        can_approve,can_export,can_admin,
                        can_financial,can_documents,data_scope
                    )
                    VALUES(
                        ?,?,
                        1,1,1,1,1,1,
                        ?,?,?,'all'
                    )
                    """,
                    (
                        profile["id"],
                        module,
                        1
                        if (
                            profile["base_role"]=="admin"
                            and module=="admin"
                        )
                        else 0,
                        1
                        if module in {"finance","invoice"}
                        else 0,
                        1
                        if module in {
                            "candidate",
                            "document",
                            "onboarding",
                        }
                        else 0,
                    ),
                )

        conn.execute(
            """
            INSERT OR IGNORE INTO release_notes_r23(
                tenant_id,version,title,body,published_at
            )
            VALUES(
                ?,
                'R23B',
                'Enterprise Profiles & Teams',
                'Configurable role profiles, multiple teams, permission matrices, team/profile switching, access logs and enterprise staffing personas.',
                ?
            )
            """,
            (tid,ts),
        )

        articles = [
            (
                "Getting Started",
                "Choose Your Team",
                "Choose an authorized team and permission profile from the session selector."
            ),
            (
                "Best Practices",
                "Permissions Best Practices",
                "Use least privilege, separate finance and recruiting access, and review access logs."
            ),
            (
                "Best Practices",
                "Team Design Best Practices",
                "Use teams for branches, delivery groups, client pods and MSP programs."
            ),
        ]

        for category,title,body in articles:
            conn.execute(
                """
                INSERT OR IGNORE INTO help_articles_r23(
                    tenant_id,category,title,body,active
                )
                VALUES(?,?,?,?,1)
                """,
                (tid,category,title,body),
            )

        _ensure_existing_users(
            conn,
            tid,
        )

    conn.commit()


def _profile(conn, tid, profile_id):
    return one(
        conn,
        """
        SELECT *
        FROM role_profiles_r23
        WHERE tenant_id=?
          AND id=?
        """,
        (tid,int(profile_id)),
    )


def _team(conn, tid, team_id):
    return one(
        conn,
        """
        SELECT *
        FROM teams_r23
        WHERE tenant_id=?
          AND id=?
        """,
        (tid,int(team_id)),
    )


def _ensure_existing_users(conn, tid):

    team = one(
        conn,
        """
        SELECT id
        FROM teams_r23
        WHERE tenant_id=?
          AND code='default'
        """,
        (tid,),
    )

    if not team:
        return

    for user in rows(
        conn,
        """
        SELECT id,role
        FROM users
        WHERE tenant_id=?
        """,
        (tid,),
    ):
        profile_slug = DEFAULT_PROFILE_BY_ROLE.get(
            user["role"]
        )

        if not profile_slug:
            continue

        profile = one(
            conn,
            """
            SELECT id
            FROM role_profiles_r23
            WHERE tenant_id=?
              AND slug=?
              AND active=1
            """,
            (tid,profile_slug),
        )

        if not profile:
            continue

        exists = one(
            conn,
            """
            SELECT 1 ok
            FROM team_members_r23
            WHERE user_id=?
              AND active=1
            LIMIT 1
            """,
            (user["id"],),
        )

        if exists:
            continue

        ts = now()

        conn.execute(
            """
            INSERT OR IGNORE INTO team_members_r23(
                team_id,user_id,profile_id,
                is_primary,active,created_at,updated_at
            )
            VALUES(
                ?,?,?,1,1,?,?
            )
            """,
            (
                team["id"],
                user["id"],
                profile["id"],
                ts,
                ts,
            ),
        )


def _session_token(h):
    try:
        return (
            h._cookies()
            or {}
        ).get("ats_session")
    except Exception:
        return None


def effective_context(conn, u, token=None):

    tid = int(u["tenant_id"])
    uid = int(u["id"])

    _ensure_existing_users(
        conn,
        tid,
    )

    assignments = rows(
        conn,
        """
        SELECT
            tm.team_id,
            tm.profile_id,
            tm.is_primary,
            t.name AS team_name,
            t.code AS team_code,
            rp.name AS profile_name,
            rp.display_name,
            rp.slug AS profile_slug,
            rp.base_role

        FROM team_members_r23 tm

        JOIN teams_r23 t
          ON t.id=tm.team_id
         AND t.tenant_id=?

        JOIN role_profiles_r23 rp
          ON rp.id=tm.profile_id
         AND rp.tenant_id=?

        WHERE tm.user_id=?
          AND tm.active=1
          AND t.active=1
          AND rp.active=1

        ORDER BY
            tm.is_primary DESC,
            t.name,
            rp.name
        """,
        (tid,tid,uid),
    )

    selected = None
    key = token_key(token)

    if key:
        selected = one(
            conn,
            """
            SELECT
                sc.team_id,
                sc.profile_id,
                t.name AS team_name,
                t.code AS team_code,
                rp.name AS profile_name,
                rp.display_name,
                rp.slug AS profile_slug,
                rp.base_role

            FROM session_context_r23 sc

            JOIN teams_r23 t
              ON t.id=sc.team_id
             AND t.tenant_id=sc.tenant_id

            JOIN role_profiles_r23 rp
              ON rp.id=sc.profile_id
             AND rp.tenant_id=sc.tenant_id

            WHERE sc.session_key=?
              AND sc.tenant_id=?
              AND sc.user_id=?
              AND t.active=1
              AND rp.active=1
            """,
            (key,tid,uid),
        )

        if selected and not any(
            int(x["team_id"])==int(selected["team_id"])
            and
            int(x["profile_id"])==int(selected["profile_id"])
            for x in assignments
        ):
            selected = None

    if not selected and assignments:
        selected = dict(assignments[0])

    permissions = []

    if selected:
        permissions = rows(
            conn,
            """
            SELECT *
            FROM profile_permissions_r23
            WHERE profile_id=?
            ORDER BY module
            """,
            (selected["profile_id"],),
        )

    return {
        "selected":selected,
        "assignments":assignments,
        "permissions":permissions,
    }


def _can_admin(conn, u, h):

    if u.get("role")!="admin":
        return False

    ctx = effective_context(
        conn,
        u,
        _session_token(h),
    )

    selected = ctx.get("selected")

    if not selected:
        return True

    p = one(
        conn,
        """
        SELECT can_view,can_admin
        FROM profile_permissions_r23
        WHERE profile_id=?
          AND module='admin'
        """,
        (selected["profile_id"],),
    )

    return bool(
        p
        and int(p.get("can_view") or 0)==1
        and int(p.get("can_admin") or 0)==1
    )


def r23_permission_denied(
    conn,
    u,
    token,
    module,
    method,
    path="",
):

    ctx = effective_context(
        conn,
        u,
        token,
    )

    selected = ctx.get("selected")

    if not selected:
        return False

    perm = one(
        conn,
        """
        SELECT *
        FROM profile_permissions_r23
        WHERE profile_id=?
          AND module=?
        """,
        (selected["profile_id"],module),
    )

    if not perm:
        return True

    method = (
        method
        or "GET"
    ).upper()

    path = (
        path
        or ""
    ).lower()

    action = "view"

    # R23_TALENT_SEARCH_VIEW_ACTION
    if method=="POST" and path=="/api/search/talent":
        action="view"
    elif method=="POST":
        action = (
            "approve"
            if any(
                marker in path
                for marker in (
                    "/approve",
                    "/reject",
                    "/status",
                    "/submit",
                )
            )
            else "create"
        )

    elif method in {"PUT","PATCH"}:
        action = "edit"

    elif method=="DELETE":
        action = "delete"

    column = {
        "view":"can_view",
        "create":"can_create",
        "edit":"can_edit",
        "delete":"can_delete",
        "approve":"can_approve",
    }[action]

    return not bool(
        int(
            perm.get(column)
            or 0
        )
    )


def _audit(
    conn,
    u,
    event,
    path="",
    method="",
    detail="",
):

    conn.execute(
        """
        INSERT INTO access_log_r23(
            tenant_id,user_id,event_type,
            path,method,detail,created_at
        )
        VALUES(?,?,?,?,?,?,?)
        """,
        (
            u["tenant_id"],
            u.get("id"),
            event,
            path,
            method,
            detail,
            now(),
        ),
    )


def r23_get(h, conn, u, path, qs):

    tid = u["tenant_id"]

    if path=="/api/r23/context":
        return send(
            h,
            effective_context(
                conn,
                u,
                _session_token(h),
            ),
        )

    if path=="/api/r23/personas":
        return send(
            h,
            [
                {
                    "name":name,
                    "slug":profile_slug,
                    "base_role":base_role,
                }
                for name,profile_slug,base_role
                in PERSONAS
            ],
        )

    if path=="/api/r23/role-profiles":

        if not _can_admin(conn,u,h):
            return send(
                h,
                {"error":"Permission denied"},
                403,
            )

        return send(
            h,
            rows(
                conn,
                """
                SELECT *
                FROM role_profiles_r23
                WHERE tenant_id=?
                ORDER BY
                    active DESC,
                    is_system DESC,
                    name
                """,
                (tid,),
            ),
        )

    m = re.fullmatch(
        r"/api/r23/role-profiles/(\d+)/permissions",
        path,
    )

    if m:

        if not _can_admin(conn,u,h):
            return send(
                h,
                {"error":"Permission denied"},
                403,
            )

        profile = _profile(
            conn,
            tid,
            m.group(1),
        )

        if not profile:
            return send(
                h,
                {"error":"Profile not found"},
                404,
            )

        return send(
            h,
            {
                "profile":profile,
                "modules":MODULES,
                "permissions":rows(
                    conn,
                    """
                    SELECT *
                    FROM profile_permissions_r23
                    WHERE profile_id=?
                    ORDER BY module
                    """,
                    (profile["id"],),
                ),
            },
        )

    if path=="/api/r23/teams":

        if not _can_admin(conn,u,h):
            return send(
                h,
                {"error":"Permission denied"},
                403,
            )

        return send(
            h,
            rows(
                conn,
                """
                SELECT *
                FROM teams_r23
                WHERE tenant_id=?
                ORDER BY active DESC,name
                """,
                (tid,),
            ),
        )

    if path=="/api/r23/users-context":

        if not _can_admin(conn,u,h):
            return send(
                h,
                {"error":"Permission denied"},
                403,
            )

        users = rows(
            conn,
            """
            SELECT id,email,name,role,active
            FROM users
            WHERE tenant_id=?
            ORDER BY name
            """,
            (tid,),
        )

        for item in users:
            item["assignments"] = rows(
                conn,
                """
                SELECT
                    tm.team_id,
                    tm.profile_id,
                    tm.is_primary,
                    t.name AS team_name,
                    rp.name AS profile_name,
                    rp.display_name,
                    rp.base_role

                FROM team_members_r23 tm

                JOIN teams_r23 t
                  ON t.id=tm.team_id

                JOIN role_profiles_r23 rp
                  ON rp.id=tm.profile_id

                WHERE tm.user_id=?
                  AND tm.active=1

                ORDER BY
                    tm.is_primary DESC,
                    t.name,
                    rp.name
                """,
                (item["id"],),
            )

        return send(h,users)

    if path=="/api/r23/access-log":

        if u["role"] not in {"admin","teamlead"}:
            return send(
                h,
                {"error":"Permission denied"},
                403,
            )

        try:
            limit = int(
                (
                    qs.get("limit")
                    or [200]
                )[0]
            )
        except Exception:
            limit = 200

        limit = min(
            max(limit,1),
            1000,
        )

        return send(
            h,
            rows(
                conn,
                """
                SELECT *
                FROM access_log_r23
                WHERE tenant_id=?
                ORDER BY id DESC
                LIMIT ?
                """,
                (tid,limit),
            ),
        )

    if path=="/api/r23/release-notes":
        return send(
            h,
            rows(
                conn,
                """
                SELECT *
                FROM release_notes_r23
                WHERE tenant_id=?
                ORDER BY id DESC
                """,
                (tid,),
            ),
        )

    if path=="/api/r23/help":
        return send(
            h,
            rows(
                conn,
                """
                SELECT *
                FROM help_articles_r23
                WHERE tenant_id=?
                  AND active=1
                ORDER BY category,title
                """,
                (tid,),
            ),
        )

    return False


def r23_post(h, conn, u, path, data):

    tid = u["tenant_id"]

    if path=="/api/r23/role-profiles":

        if not _can_admin(conn,u,h):
            return send(
                h,
                {"error":"Permission denied"},
                403,
            )

        name = str(
            data.get("name")
            or ""
        ).strip()

        base_role = str(
            data.get("base_role")
            or ""
        ).strip().lower()

        profile_slug = slug(
            data.get("slug")
            or name
        )

        if not name:
            return send(
                h,
                {"error":"name required"},
                400,
            )

        if base_role not in BASE_MODULES:
            return send(
                h,
                {"error":"Unsupported base_role"},
                400,
            )

        if one(
            conn,
            """
            SELECT id
            FROM role_profiles_r23
            WHERE tenant_id=?
              AND slug=?
            """,
            (tid,profile_slug),
        ):
            return send(
                h,
                {"error":"Profile slug already exists"},
                409,
            )

        ts = now()

        cur = conn.execute(
            """
            INSERT INTO role_profiles_r23(
                tenant_id,name,display_name,slug,
                base_role,description,active,is_system,
                created_at,updated_at
            )
            VALUES(
                ?,?,?,?,?,?,1,0,?,?
            )
            """,
            (
                tid,
                name,
                name,
                profile_slug,
                base_role,
                str(
                    data.get("description")
                    or "Custom permission profile"
                ),
                ts,
                ts,
            ),
        )

        default_scope = str(
            data.get("data_scope")
            or "all"
        )

        if default_scope not in {"own","team","all"}:
            default_scope = "all"

        for module in BASE_MODULES[base_role]:

            conn.execute(
                """
                INSERT INTO profile_permissions_r23(
                    profile_id,module,
                    can_view,can_create,can_edit,can_delete,
                    can_approve,can_export,can_admin,
                    can_financial,can_documents,data_scope
                )
                VALUES(
                    ?,?,
                    1,1,1,1,1,1,
                    0,?,?,?
                )
                """,
                (
                    cur.lastrowid,
                    module,
                    1
                    if module in {"finance","invoice"}
                    else 0,
                    1
                    if module in {
                        "candidate",
                        "document",
                        "onboarding",
                    }
                    else 0,
                    default_scope,
                ),
            )

        _audit(
            conn,
            u,
            "PROFILE_CREATE",
            path,
            "POST",
            name,
        )

        conn.commit()

        return send(
            h,
            _profile(
                conn,
                tid,
                cur.lastrowid,
            ),
            201,
        )

    m = re.fullmatch(
        r"/api/r23/role-profiles/(\d+)/clone",
        path,
    )

    if m:

        if not _can_admin(conn,u,h):
            return send(
                h,
                {"error":"Permission denied"},
                403,
            )

        source = _profile(
            conn,
            tid,
            m.group(1),
        )

        if not source:
            return send(
                h,
                {"error":"Profile not found"},
                404,
            )

        name = str(
            data.get("name")
            or source["name"]+" Copy"
        ).strip()

        profile_slug = slug(
            data.get("slug")
            or name
        )

        if one(
            conn,
            """
            SELECT id
            FROM role_profiles_r23
            WHERE tenant_id=?
              AND slug=?
            """,
            (tid,profile_slug),
        ):
            return send(
                h,
                {"error":"Profile slug already exists"},
                409,
            )

        ts = now()

        cur = conn.execute(
            """
            INSERT INTO role_profiles_r23(
                tenant_id,name,display_name,slug,
                base_role,description,active,is_system,
                created_at,updated_at
            )
            VALUES(
                ?,?,?,?,?,?,1,0,?,?
            )
            """,
            (
                tid,
                name,
                name,
                profile_slug,
                source["base_role"],
                source.get("description"),
                ts,
                ts,
            ),
        )

        conn.execute(
            """
            INSERT INTO profile_permissions_r23(
                profile_id,module,
                can_view,can_create,can_edit,can_delete,
                can_approve,can_export,can_admin,
                can_financial,can_documents,data_scope
            )

            SELECT
                ?,
                module,
                can_view,
                can_create,
                can_edit,
                can_delete,
                can_approve,
                can_export,
                can_admin,
                can_financial,
                can_documents,
                data_scope

            FROM profile_permissions_r23
            WHERE profile_id=?
            """,
            (
                cur.lastrowid,
                source["id"],
            ),
        )

        _audit(
            conn,
            u,
            "PROFILE_CLONE",
            path,
            "POST",
            "clone role / clone profile: "+name,
        )

        conn.commit()

        return send(
            h,
            _profile(
                conn,
                tid,
                cur.lastrowid,
            ),
            201,
        )

    m = re.fullmatch(
        r"/api/r23/role-profiles/(\d+)/rename",
        path,
    )

    if m:

        if not _can_admin(conn,u,h):
            return send(
                h,
                {"error":"Permission denied"},
                403,
            )

        profile = _profile(
            conn,
            tid,
            m.group(1),
        )

        if not profile:
            return send(
                h,
                {"error":"Profile not found"},
                404,
            )

        name = str(
            data.get("name")
            or ""
        ).strip()

        if not name:
            return send(
                h,
                {"error":"name required"},
                400,
            )

        profile_slug = slug(
            data.get("slug")
            or name
        )

        conflict = one(
            conn,
            """
            SELECT id
            FROM role_profiles_r23
            WHERE tenant_id=?
              AND slug=?
              AND id<>?
            """,
            (
                tid,
                profile_slug,
                profile["id"],
            ),
        )

        if conflict:
            return send(
                h,
                {"error":"Profile slug already exists"},
                409,
            )

        conn.execute(
            """
            UPDATE role_profiles_r23
            SET
                name=?,
                display_name=?,
                slug=?,
                updated_at=?
            WHERE id=?
              AND tenant_id=?
            """,
            (
                name,
                name,
                profile_slug,
                now(),
                profile["id"],
                tid,
            ),
        )

        _audit(
            conn,
            u,
            "PROFILE_RENAME",
            path,
            "POST",
            name,
        )

        conn.commit()

        return send(
            h,
            _profile(
                conn,
                tid,
                profile["id"],
            ),
        )

    m = re.fullmatch(
        r"/api/r23/role-profiles/(\d+)/deactivate",
        path,
    )

    if m:

        if not _can_admin(conn,u,h):
            return send(
                h,
                {"error":"Permission denied"},
                403,
            )

        profile = _profile(
            conn,
            tid,
            m.group(1),
        )

        if not profile:
            return send(
                h,
                {"error":"Profile not found"},
                404,
            )

        if int(profile.get("is_system") or 0)==1:
            return send(
                h,
                {
                    "error":
                    "System profiles cannot be deactivated; clone and customize instead"
                },
                409,
            )

        active = (
            1
            if bool(data.get("active"))
            else 0
        )

        conn.execute(
            """
            UPDATE role_profiles_r23
            SET active=?,updated_at=?
            WHERE id=?
              AND tenant_id=?
            """,
            (
                active,
                now(),
                profile["id"],
                tid,
            ),
        )

        _audit(
            conn,
            u,
            "PROFILE_ACTIVE_CHANGE",
            path,
            "POST",
            profile["name"]+"="+str(active),
        )

        conn.commit()

        return send(
            h,
            _profile(
                conn,
                tid,
                profile["id"],
            ),
        )

    m = re.fullmatch(
        r"/api/r23/role-profiles/(\d+)/permissions",
        path,
    )

    if m:

        if not _can_admin(conn,u,h):
            return send(
                h,
                {"error":"Permission denied"},
                403,
            )

        profile = _profile(
            conn,
            tid,
            m.group(1),
        )

        if not profile:
            return send(
                h,
                {"error":"Profile not found"},
                404,
            )

        permissions = data.get("permissions")

        if not isinstance(permissions,list):
            return send(
                h,
                {"error":"permissions array required"},
                400,
            )

        for item in permissions:

            module = str(
                item.get("module")
                or ""
            ).strip()

            if module not in MODULES:
                continue

            scope = str(
                item.get("data_scope")
                or "all"
            )

            if scope not in {"own","team","all"}:
                scope = "all"

            flags = [
                1 if bool(item.get(key)) else 0
                for key in (
                    "can_view",
                    "can_create",
                    "can_edit",
                    "can_delete",
                    "can_approve",
                    "can_export",
                    "can_admin",
                    "can_financial",
                    "can_documents",
                )
            ]

            conn.execute(
                """
                INSERT INTO profile_permissions_r23(
                    profile_id,module,
                    can_view,can_create,can_edit,can_delete,
                    can_approve,can_export,can_admin,
                    can_financial,can_documents,data_scope
                )
                VALUES(
                    ?,?,?,?,?,?,?,?,?,?,?,?
                )

                ON CONFLICT(profile_id,module)
                DO UPDATE SET
                    can_view=excluded.can_view,
                    can_create=excluded.can_create,
                    can_edit=excluded.can_edit,
                    can_delete=excluded.can_delete,
                    can_approve=excluded.can_approve,
                    can_export=excluded.can_export,
                    can_admin=excluded.can_admin,
                    can_financial=excluded.can_financial,
                    can_documents=excluded.can_documents,
                    data_scope=excluded.data_scope
                """,
                (
                    profile["id"],
                    module,
                    *flags,
                    scope,
                ),
            )

        _audit(
            conn,
            u,
            "PROFILE_PERMISSIONS_UPDATE",
            path,
            "POST",
            profile["name"],
        )

        conn.commit()

        return send(
            h,
            {
                "ok":True,
                "profile_id":profile["id"],
            },
        )

    if path=="/api/r23/teams":

        if not _can_admin(conn,u,h):
            return send(
                h,
                {"error":"Permission denied"},
                403,
            )

        name = str(
            data.get("name")
            or ""
        ).strip()

        code = slug(
            data.get("code")
            or name
        )

        if not name:
            return send(
                h,
                {"error":"name required"},
                400,
            )

        if one(
            conn,
            """
            SELECT id
            FROM teams_r23
            WHERE tenant_id=?
              AND code=?
            """,
            (tid,code),
        ):
            return send(
                h,
                {"error":"Team code already exists"},
                409,
            )

        ts = now()

        cur = conn.execute(
            """
            INSERT INTO teams_r23(
                tenant_id,name,code,active,created_at,updated_at
            )
            VALUES(
                ?,?,?,1,?,?
            )
            """,
            (tid,name,code,ts,ts),
        )

        _audit(
            conn,
            u,
            "TEAM_CREATE",
            path,
            "POST",
            name,
        )

        conn.commit()

        return send(
            h,
            _team(
                conn,
                tid,
                cur.lastrowid,
            ),
            201,
        )

    m = re.fullmatch(
        r"/api/r23/teams/(\d+)/members",
        path,
    )

    if m:

        if not _can_admin(conn,u,h):
            return send(
                h,
                {"error":"Permission denied"},
                403,
            )

        team = _team(
            conn,
            tid,
            m.group(1),
        )

        if not team:
            return send(
                h,
                {"error":"Team not found"},
                404,
            )

        try:
            user_id = int(data.get("user_id"))
            profile_id = int(data.get("profile_id"))
        except Exception:
            return send(
                h,
                {
                    "error":
                    "user_id and profile_id required"
                },
                400,
            )

        user = one(
            conn,
            """
            SELECT id
            FROM users
            WHERE tenant_id=?
              AND id=?
            """,
            (tid,user_id),
        )

        profile = _profile(
            conn,
            tid,
            profile_id,
        )

        if (
            not user
            or not profile
            or int(profile.get("active") or 0)!=1
        ):
            return send(
                h,
                {"error":"User/profile not found"},
                404,
            )

        primary = (
            1
            if bool(data.get("is_primary"))
            else 0
        )

        if primary:
            conn.execute(
                """
                UPDATE team_members_r23
                SET is_primary=0
                WHERE user_id=?
                """,
                (user_id,),
            )

        ts = now()

        conn.execute(
            """
            INSERT INTO team_members_r23(
                team_id,user_id,profile_id,
                is_primary,active,created_at,updated_at
            )
            VALUES(
                ?,?,?,?,1,?,?
            )

            ON CONFLICT(team_id,user_id,profile_id)
            DO UPDATE SET
                is_primary=excluded.is_primary,
                active=1,
                updated_at=excluded.updated_at
            """,
            (
                team["id"],
                user_id,
                profile_id,
                primary,
                ts,
                ts,
            ),
        )

        _audit(
            conn,
            u,
            "TEAM_MEMBER_ASSIGN",
            path,
            "POST",
            f"user={user_id},profile={profile_id}",
        )

        conn.commit()

        return send(
            h,
            {"ok":True},
        )

    if path=="/api/r23/session-context":

        token = _session_token(h)

        if not token:
            return send(
                h,
                {"error":"Session cookie required"},
                400,
            )

        try:
            team_id = int(data.get("team_id"))
            profile_id = int(data.get("profile_id"))
        except Exception:
            return send(
                h,
                {
                    "error":
                    "team_id and profile_id required"
                },
                400,
            )

        allowed = one(
            conn,
            """
            SELECT 1 ok

            FROM team_members_r23 tm

            JOIN teams_r23 t
              ON t.id=tm.team_id

            JOIN role_profiles_r23 rp
              ON rp.id=tm.profile_id

            WHERE tm.user_id=?
              AND tm.team_id=?
              AND tm.profile_id=?
              AND tm.active=1
              AND t.active=1
              AND rp.active=1
              AND t.tenant_id=?
              AND rp.tenant_id=?
            """,
            (
                u["id"],
                team_id,
                profile_id,
                tid,
                tid,
            ),
        )

        if not allowed:
            return send(
                h,
                {
                    "error":
                    "Team/profile assignment not authorized"
                },
                403,
            )

        conn.execute(
            """
            INSERT INTO session_context_r23(
                session_key,tenant_id,user_id,
                team_id,profile_id,updated_at
            )
            VALUES(
                ?,?,?,?,?,?
            )

            ON CONFLICT(session_key)
            DO UPDATE SET
                tenant_id=excluded.tenant_id,
                user_id=excluded.user_id,
                team_id=excluded.team_id,
                profile_id=excluded.profile_id,
                updated_at=excluded.updated_at
            """,
            (
                token_key(token),
                tid,
                u["id"],
                team_id,
                profile_id,
                now(),
            ),
        )

        _audit(
            conn,
            u,
            "SESSION_CONTEXT_SWITCH",
            path,
            "POST",
            f"team={team_id},profile={profile_id}",
        )

        conn.commit()

        return send(
            h,
            effective_context(
                conn,
                u,
                token,
            ),
        )

    return False
