from __future__ import annotations

import sqlite3
import sys
from pathlib import Path


ROOT=Path(
    sys.argv[1]
).resolve()


sys.path.insert(
    0,
    str(ROOT),
)


from r22_api import (
    LOCALES,
    ensure_r22_schema,
    r22_get,
    r22_post,
)


from r23c_candidate import (
    ensure_r23c_schema,
    r23c_public_get,
    r23c_public_post,
    r23c_get,
    r23c_post,
)


class H:

    def __init__(
        self,
        token="token",
    ):

        self.status=None
        self.payload=None
        self.token=token
        self.client_address=(
            "127.0.0.1",
            12345,
        )


    def _json(
        self,
        payload,
        status=200,
        headers=None,
    ):

        self.status=status
        self.payload=payload


    def _cookies(
        self,
    ):

        return {
            "ats_session":
                self.token
        }


def public_get(
    conn,
    path,
):

    h=H()

    assert r23c_public_get(
        h,
        conn,
        path,
        {},
    )

    return h


def public_post(
    conn,
    path,
    data,
):

    h=H()

    assert r23c_public_post(
        h,
        conn,
        path,
        data,
    )

    return h


def get(
    conn,
    user,
    path,
):

    h=H()

    assert r23c_get(
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

    h=H()

    assert r23c_post(
        h,
        conn,
        user,
        path,
        data,
    )

    return h


conn=sqlite3.connect(
    ":memory:"
)

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
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE NOT NULL,
        pass_hash TEXT NOT NULL,
        name TEXT NOT NULL,
        role TEXT NOT NULL,
        company_id INTEGER,
        candidate_id INTEGER,
        active INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL,
        tenant_id INTEGER NOT NULL
    );

    CREATE TABLE candidates(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        first_name TEXT NOT NULL,
        last_name TEXT NOT NULL,
        email TEXT,
        phone TEXT,
        city TEXT,
        state TEXT,
        country TEXT DEFAULT 'USA',
        zip TEXT,
        profession TEXT,
        specialty TEXT,
        current_title TEXT,
        availability_date TEXT,
        pay_min REAL,
        pay_max REAL,
        desired_rate_type TEXT DEFAULT 'hour',
        source TEXT,
        status TEXT DEFAULT 'Active',
        owner_user_id INTEGER,
        resume_text TEXT,
        summary TEXT,
        consent_sms INTEGER DEFAULT 1,
        consent_email INTEGER DEFAULT 1,
        do_not_contact INTEGER DEFAULT 0,
        credibility_score INTEGER DEFAULT 75,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        tenant_id INTEGER NOT NULL
    );

    CREATE TABLE audit_log(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        action TEXT,
        entity_type TEXT,
        entity_id INTEGER,
        detail TEXT,
        ip TEXT,
        created_at TEXT NOT NULL,
        tenant_id INTEGER NOT NULL
    );


    CREATE TABLE jobs(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_no TEXT UNIQUE NOT NULL,
        title TEXT NOT NULL,
        company_id INTEGER,
        status TEXT DEFAULT 'Open',
        work_mode TEXT DEFAULT 'Onsite',
        city TEXT,
        state TEXT,
        country TEXT DEFAULT 'USA',
        pay_min REAL,
        pay_max REAL,
        rate_type TEXT DEFAULT 'hour',
        profession TEXT,
        specialty TEXT,
        required_skills TEXT,
        description TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        tenant_id INTEGER NOT NULL
    );

    INSERT INTO tenants
    VALUES(
        1,
        'Tenant',
        'tenant',
        'Active',
        '2026-10-07'
    );

    INSERT INTO tenants
    VALUES(
        2,
        'Other',
        'other',
        'Active',
        '2026-10-07'
    );

    INSERT INTO jobs(
        job_no,
        title,
        status,
        work_mode,
        city,
        state,
        country,
        profession,
        specialty,
        required_skills,
        description,
        created_at,
        updated_at,
        tenant_id
    )
    VALUES(
        'J-001',
        'Senior Java Developer',
        'Open',
        'Hybrid',
        'Bhopal',
        'MP',
        'India',
        'Software Engineer',
        'Java Backend',
        'Java Spring Kafka AWS',
        'Backend engineering role',
        '2026-10-07',
        '2026-10-07',
        1
    );

    INSERT INTO jobs(
        job_no,
        title,
        status,
        work_mode,
        city,
        state,
        country,
        profession,
        specialty,
        required_skills,
        description,
        created_at,
        updated_at,
        tenant_id
    )
    VALUES(
        'J-X',
        'Other Tenant Job',
        'Open',
        'Remote',
        'X',
        'X',
        'X',
        'Other',
        'Other',
        'Other',
        'Other',
        '2026-10-07',
        '2026-10-07',
        2
    );
    """
)


ensure_r22_schema(
    conn
)

ensure_r23c_schema(
    conn
)


h=public_get(
    conn,
    "/api/r23c/public-registration",
)


assert h.status==200

assert h.payload[
    "resume_maker"
] is True

assert any(
    x["code"]
    ==
    "resume_maker"
    for x
    in h.payload[
        "resume_modes"
    ]
)

print(
    "PUBLIC_REGISTRATION_OPTIONS=PASS"
)


h=public_post(
    conn,
    "/api/r23c/register-candidate",
    {
        "first_name":
            "Riya",

        "last_name":
            "Sharma",

        "email":
            "riya@example.com",

        "password":
            "StrongPass123!",

        "resume_mode":
            "resume_maker",

        "locale":
            "zh",

        "headline":
            "Senior Java Developer",

        "profession":
            "Software Engineer",

        "summary":
            "Backend engineer",

        "skills_text":
            "Java, Spring, Kafka, AWS",

        "experience_text":
            "Platform engineering experience",

        "education_text":
            "B.Tech Computer Science",
    },
)


assert h.status==201

candidate_id=int(
    h.payload[
        "candidate_id"
    ]
)


assert h.payload[
    "registration_mode"
]=="resume_maker"


assert h.payload[
    "locale"
]=="zh"


print(
    "PUBLIC_RESUME_MAKER_REGISTRATION=PASS"
)


user=dict(
    conn.execute(
        """
        SELECT *
        FROM users
        WHERE candidate_id=?
        """,
        (
            candidate_id,
        ),
    ).fetchone()
)


candidate=dict(
    conn.execute(
        """
        SELECT *
        FROM candidates
        WHERE id=?
        """,
        (
            candidate_id,
        ),
    ).fetchone()
)


assert user[
    "role"
]=="candidate"


assert (
    candidate[
        "resume_text"
    ]
    and
    "PROFESSIONAL SUMMARY"
    in candidate[
        "resume_text"
    ]
)


print(
    "CANDIDATE_ACCOUNT_LINK=PASS"
)

print(
    "RESUME_GENERATION=PASS"
)


assert (
    "zh"
    in LOCALES
)

assert (
    LOCALES[
        "zh"
    ][
        "label"
    ]
    ==
    "中文"
)


h22=H()

assert r22_get(
    h22,
    conn,
    user,
    "/api/r22/candidate-experience",
    {},
)


assert any(
    x[
        "code"
    ]
    ==
    "zh"
    for x
    in h22.payload[
        "supported_locales"
    ]
)


print(
    "CHINESE_CANDIDATE_LOCALIZATION=PASS"
)


for code in (
    "en",
    "es",
    "fr",
    "zh",
):

    h22=H()

    assert r22_post(
        h22,
        conn,
        user,
        "/api/r22/candidate-experience",
        {
            "locale":
                code
        },
    )

    assert h22.status==200


print(
    "EN_ES_FR_ZH_LOCALE_PERSISTENCE=PASS"
)


h=get(
    conn,
    user,
    "/api/r23c/candidate-portal",
)


assert h.status==200

assert h.payload[
    "latest_resume"
][
    "version"
]==1


assert any(
    int(
        j[
            "id"
        ]
    )
    ==
    1
    for j
    in h.payload[
        "ideal_jobs"
    ]
)


assert all(
    int(
        j[
            "id"
        ]
    )
    !=
    2
    for j
    in h.payload[
        "ideal_jobs"
    ]
)


print(
    "IDEAL_JOBS=PASS"
)

print(
    "IDEAL_JOBS_TENANT_SCOPE=PASS"
)


h=post(
    conn,
    user,
    "/api/r23c/saved-jobs",
    {
        "job_id":
            1
    },
)


assert h.status==201


h=get(
    conn,
    user,
    "/api/r23c/saved-jobs",
)


assert len(
    h.payload
)==1


assert int(
    h.payload[
        0
    ][
        "id"
    ]
)==1


print(
    "SAVED_JOBS=PASS"
)


h=post(
    conn,
    user,
    "/api/r23c/saved-jobs/1/remove",
    {},
)


assert h.status==200


h=get(
    conn,
    user,
    "/api/r23c/saved-jobs",
)


assert len(
    h.payload
)==0


print(
    "REMOVE_SAVED_JOB=PASS"
)


h=post(
    conn,
    user,
    "/api/r23c/saved-jobs",
    {
        "job_id":
            2
    },
)


assert h.status==404


print(
    "SAVED_JOB_CROSS_TENANT_BLOCK=PASS"
)


h=post(
    conn,
    user,
    "/api/r23c/resume-builder",
    {
        "headline":
            "Lead Java Engineer",

        "summary":
            "Updated summary",

        "skills_text":
            "Java, Spring Boot, Kafka",

        "experience_text":
            "Updated experience",

        "education_text":
            "Updated education",
    },
)


assert h.status==201

assert h.payload[
    "version"
]==2


candidate=dict(
    conn.execute(
        """
        SELECT *
        FROM candidates
        WHERE id=?
        """,
        (
            candidate_id,
        ),
    ).fetchone()
)


assert (
    candidate[
        "current_title"
    ]
    ==
    "Lead Java Engineer"
)


assert (
    "Updated experience"
    in candidate[
        "resume_text"
    ]
)


print(
    "RESUME_MAKER_EDIT=PASS"
)

print(
    "RESUME_VERSIONING=PASS"
)


other={
    "id":
        999,

    "email":
        "internal@test",

    "name":
        "Internal",

    "role":
        "recruiter",

    "candidate_id":
        None,

    "tenant_id":
        1,
}


h=get(
    conn,
    other,
    "/api/r23c/candidate-portal",
)


assert h.status==403


print(
    "CANDIDATE_PORTAL_ROLE_BOUNDARY=PASS"
)


server=(
    ROOT
    /"server.py"
).read_text(
    encoding="utf-8"
)


index=(
    ROOT
    /"web"
    /"index.html"
).read_text(
    encoding="utf-8"
)


js=(
    ROOT
    /"web"
    /"r23c.js"
).read_text(
    encoding="utf-8"
)


assert (
    "ensure_r23c_schema(conn)"
    in server
)


assert (
    "r23c_public_get("
    in server
)


assert (
    "r23c_public_post("
    in server
)


assert (
    "r23c_get("
    in server
)


assert (
    "r23c_post("
    in server
)


assert (
    '/r23c.js?v=R23C-1'
    in index
)


assert (
    "Resume Maker / Resume Builder"
    in js
)


assert (
    "Saved Jobs"
    in js
)


assert (
    "Ideal Jobs"
    in js
)


assert (
    "CREATE CANDIDATE ACCOUNT"
    in js
)


print(
    "R23C_SERVER_UI_INTEGRATION=PASS"
)

print(
    "R23C_CANDIDATE_PORTAL=PASS"
)
