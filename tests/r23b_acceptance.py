from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

ROOT = Path(sys.argv[1]).resolve()
sys.path.insert(0,str(ROOT))

from r23_rbac import (
    PERSONAS,
    ensure_r23_schema,
    r23_get,
    r23_post,
    r23_permission_denied,
)


class H:
    def __init__(self, token="tok-r23"):
        self.status = None
        self.payload = None
        self.token = token

    def _json(self,payload,status=200,headers=None):
        self.status = status
        self.payload = payload

    def _cookies(self):
        return {"ats_session":self.token}


def get(conn,user,path,qs=None,token="tok-r23"):
    h=H(token)
    assert r23_get(
        h,conn,user,path,qs or {}
    )
    return h


def post(conn,user,path,data,token="tok-r23"):
    h=H(token)
    assert r23_post(
        h,conn,user,path,data
    )
    return h


conn=sqlite3.connect(":memory:")
conn.row_factory=sqlite3.Row

conn.executescript(
    """
    CREATE TABLE tenants(
        id INTEGER PRIMARY KEY,
        name TEXT,
        slug TEXT,
        status TEXT,
        created_at TEXT
    );

    CREATE TABLE users(
        id INTEGER PRIMARY KEY,
        email TEXT,
        name TEXT,
        role TEXT,
        active INTEGER,
        tenant_id INTEGER
    );

    INSERT INTO tenants
    VALUES(1,'Tenant 1','t1','Active','2026-10-07');

    INSERT INTO tenants
    VALUES(2,'Tenant 2','t2','Active','2026-10-07');

    INSERT INTO users
    VALUES(1,'admin@test','Admin','admin',1,1);

    INSERT INTO users
    VALUES(2,'sales@test','Sales','sales',1,1);

    INSERT INTO users
    VALUES(3,'other@test','Other','sales',1,2);
    """
)

ensure_r23_schema(conn)

admin=dict(
    conn.execute(
        "SELECT * FROM users WHERE id=1"
    ).fetchone()
)

sales=dict(
    conn.execute(
        "SELECT * FROM users WHERE id=2"
    ).fetchone()
)

required = {
    "System Administrator",
    "Recruiting Manager",
    "Team Lead",
    "Recruiter",
    "Sourcer",
    "Business Development",
    "Account Manager",
    "Onboarding Coordinator",
    "Compliance Specialist",
    "Credentialing Specialist",
    "HR / Workforce Operations",
    "Billing / Accounts Receivable",
    "Finance Manager",
    "VMS / MSP Coordinator",
    "Supplier / Vendor Manager",
    "Operations Manager",
    "Reporting / BI User",
    "Client / Hiring Manager",
    "Worker / Contractor",
    "Timesheet / Expense Approver",
}

actual = {
    x["name"]
    for x in conn.execute(
        "SELECT name FROM role_profiles_r23"
    )
}

assert required.issubset(actual)
assert len(PERSONAS) >= 24

print("ENTERPRISE_PERSONAS=PASS")

h=post(
    conn,
    admin,
    "/api/r23/role-profiles",
    {
        "name":"Northstar Account Manager",
        "base_role":"sales",
        "data_scope":"team",
    },
)

assert h.status==201
pid=int(h.payload["id"])

print("PROFILE_CREATE=PASS")

h=post(
    conn,
    admin,
    f"/api/r23/role-profiles/{pid}/clone",
    {"name":"Account Manager Clone"},
)

assert h.status==201
clone_id=int(h.payload["id"])

print("PROFILE_CLONE=PASS")

h=post(
    conn,
    admin,
    f"/api/r23/role-profiles/{clone_id}/rename",
    {"name":"Enterprise Account Manager"},
)

assert h.status==200
assert h.payload["display_name"]=="Enterprise Account Manager"

print("PROFILE_RENAME=PASS")

h=post(
    conn,
    admin,
    f"/api/r23/role-profiles/{clone_id}/deactivate",
    {"active":False},
)

assert h.status==200
assert int(h.payload["active"])==0

h=post(
    conn,
    admin,
    f"/api/r23/role-profiles/{clone_id}/deactivate",
    {"active":True},
)

assert h.status==200
assert int(h.payload["active"])==1

print("PROFILE_ACTIVATE_DEACTIVATE=PASS")

system_profile=conn.execute(
    """
    SELECT id
    FROM role_profiles_r23
    WHERE tenant_id=1
      AND slug='system_administrator'
    """
).fetchone()

h=post(
    conn,
    admin,
    f"/api/r23/role-profiles/{system_profile['id']}/deactivate",
    {"active":False},
)

assert h.status==409

print("SYSTEM_PROFILE_PROTECTION=PASS")

h=post(
    conn,
    admin,
    f"/api/r23/role-profiles/{pid}/permissions",
    {
        "permissions":[
            {
                "module":"crm",
                "can_view":False,
                "can_create":False,
                "can_edit":False,
                "can_delete":False,
                "can_approve":False,
                "can_export":False,
                "can_admin":False,
                "can_financial":False,
                "can_documents":False,
                "data_scope":"team",
            },
            {
                "module":"job",
                "can_view":True,
                "can_create":True,
                "can_edit":True,
                "can_delete":False,
                "can_approve":False,
                "can_export":True,
                "can_admin":False,
                "can_financial":False,
                "can_documents":False,
                "data_scope":"team",
            }
        ]
    },
)

assert h.status==200

print("PERMISSION_MATRIX=PASS")

h=post(
    conn,
    admin,
    "/api/r23/teams",
    {"name":"Northstar Delivery"},
)

assert h.status==201
team_id=int(h.payload["id"])

print("MULTIPLE_TEAMS=PASS")

h=post(
    conn,
    admin,
    f"/api/r23/teams/{team_id}/members",
    {
        "user_id":2,
        "profile_id":pid,
        "is_primary":True,
    },
)

assert h.status==200

print("TEAM_MEMBERSHIP=PASS")

h=post(
    conn,
    sales,
    "/api/r23/session-context",
    {
        "team_id":team_id,
        "profile_id":pid,
    },
)

assert h.status==200
assert int(h.payload["selected"]["team_id"])==team_id
assert int(h.payload["selected"]["profile_id"])==pid

print("CHOOSE_TEAM_PROFILE=PASS")

assert r23_permission_denied(
    conn,
    sales,
    "tok-r23",
    "crm",
    "GET",
    "/api/companies",
) is True

assert r23_permission_denied(
    conn,
    sales,
    "tok-r23",
    "job",
    "GET",
    "/api/jobs",
) is False

assert r23_permission_denied(
    conn,
    sales,
    "tok-r23",
    "job",
    "DELETE",
    "/api/jobs/1",
) is True

print("RUNTIME_PERMISSION_ENFORCEMENT=PASS")

tenant2_profile=conn.execute(
    """
    SELECT id
    FROM role_profiles_r23
    WHERE tenant_id=2
      AND slug='sales'
    """
).fetchone()

h=post(
    conn,
    admin,
    f"/api/r23/teams/{team_id}/members",
    {
        "user_id":3,
        "profile_id":tenant2_profile["id"],
        "is_primary":False,
    },
)

assert h.status==404

print("TENANT_BOUNDARY=PASS")

h=get(
    conn,
    admin,
    "/api/r23/access-log",
    {"limit":[200]},
)

assert h.status==200
assert len(h.payload)>=6

print("ACCESS_LOG_REPORTING=PASS")

h=get(
    conn,
    admin,
    "/api/r23/release-notes",
)

assert h.status==200
assert any(
    x["version"]=="R23B"
    for x in h.payload
)

print("RELEASE_NOTES=PASS")

h=get(
    conn,
    admin,
    "/api/r23/help",
)

assert h.status==200
assert any(
    x["category"]=="Best Practices"
    for x in h.payload
)

print("HELP_BEST_PRACTICES=PASS")

h=get(
    conn,
    sales,
    "/api/r23/role-profiles",
)

assert h.status==403

print("ADMIN_BOUNDARY=PASS")

server=(ROOT/"server.py").read_text(encoding="utf-8")
index=(ROOT/"web"/"index.html").read_text(encoding="utf-8")
js=(ROOT/"web"/"r23.js").read_text(encoding="utf-8")

assert "ensure_r23_schema(conn)" in server
assert "r23_permission_denied(" in server
assert "r23_get(self,conn,u,path,qs)" in server
assert "r23_post(self,conn,u,path,data)" in server
assert '/r23.js?v=R23B-1' in index

assert "Enterprise Role Profiles" in js
assert "Teams & Membership" in js
assert "Access Log" in js
assert "Help / Best Practices" in js
assert "What's New / Release Notes" in js

print("SERVER_UI_INTEGRATION=PASS")
print("R23B_ENTERPRISE_RBAC_TEAMS_PROFILES=PASS")
