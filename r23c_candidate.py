from __future__ import annotations

import base64
import hashlib
import re
import secrets
from datetime import datetime, timezone


# Real candidate-portal localization authority.
# These values also power registration and portal controls.
SUPPORTED_PORTAL_LOCALES={
    'en':'English',
    'es':'Español',
    'fr':'Français',
    'hi':'हिन्दी',
    'zh':'中文',
}


REGISTRATION_MODES={
    "resume_maker":"Resume Maker / Resume Builder",
    "paste_resume":"Paste Resume",
    "no_resume":"Register Without Resume",
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
        for x
        in conn.execute(
            sql,
            params,
        ).fetchall()
    ]


def one(
    conn,
    sql,
    params=(),
):

    x=conn.execute(
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


def _hash_password(
    password,
):

    salt=secrets.token_bytes(
        16
    )

    digest=hashlib.pbkdf2_hmac(
        "sha256",
        password.encode(),
        salt,
        150_000,
    )

    return (
        base64.b64encode(
            salt
        ).decode()
        +":"
        +base64.b64encode(
            digest
        ).decode()
    )


def _email(
    value,
):

    value=str(
        value
        or ""
    ).strip().lower()

    if not re.fullmatch(
        r"[^@\s]+@[^@\s]+\.[^@\s]+",
        value,
    ):
        return None

    return value


def _locale(
    value,
):

    code=str(
        value
        or "en"
    ).strip().lower()

    code=code.replace(
        "_",
        "-"
    ).split(
        "-",
        1,
    )[0]

    if (
        code
        not in
        SUPPORTED_PORTAL_LOCALES
    ):
        code="en"

    return code


def ensure_r23c_schema(
    conn,
):

    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS
        candidate_saved_jobs_r23c(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id INTEGER NOT NULL,
            candidate_id INTEGER NOT NULL,
            job_id INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE(
                tenant_id,
                candidate_id,
                job_id
            )
        );

        CREATE TABLE IF NOT EXISTS
        candidate_resume_versions_r23c(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id INTEGER NOT NULL,
            candidate_id INTEGER NOT NULL,
            version INTEGER NOT NULL,

            headline TEXT,
            summary TEXT,
            skills_text TEXT,
            experience_text TEXT,
            education_text TEXT,

            resume_text TEXT NOT NULL,
            created_at TEXT NOT NULL,

            UNIQUE(
                tenant_id,
                candidate_id,
                version
            )
        );

        CREATE TABLE IF NOT EXISTS
        candidate_registration_audit_r23c(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id INTEGER NOT NULL,
            candidate_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            registration_mode TEXT NOT NULL,
            locale TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS
        idx_saved_jobs_r23c_candidate
        ON candidate_saved_jobs_r23c(
            tenant_id,
            candidate_id,
            id
        );

        CREATE INDEX IF NOT EXISTS
        idx_resume_versions_r23c_candidate
        ON candidate_resume_versions_r23c(
            tenant_id,
            candidate_id,
            version
        );
        """
    )

    conn.commit()


def _candidate_user(
    u,
):

    return (
        u.get("role")
        ==
        "candidate"
        and
        bool(
            u.get(
                "candidate_id"
            )
        )
    )


def _candidate(
    conn,
    u,
):

    if not _candidate_user(
        u
    ):
        return None

    return one(
        conn,
        """
        SELECT *
        FROM candidates
        WHERE tenant_id=?
          AND id=?
        """,
        (
            u["tenant_id"],
            u["candidate_id"],
        ),
    )


def _render_resume(
    candidate,
    headline,
    summary,
    skills_text,
    experience_text,
    education_text,
):

    full_name=(
        (
            str(
                candidate.get(
                    "first_name"
                )
                or ""
            )
            +" "
            +str(
                candidate.get(
                    "last_name"
                )
                or ""
            )
        )
        .strip()
    )

    contact=[
        candidate.get(
            "email"
        ),
        candidate.get(
            "phone"
        ),
        ", ".join(
            [
                str(x)
                for x in (
                    candidate.get(
                        "city"
                    ),
                    candidate.get(
                        "state"
                    ),
                    candidate.get(
                        "country"
                    ),
                )
                if x
            ]
        ),
    ]

    contact=[
        str(x)
        for x in contact
        if x
    ]

    parts=[
        full_name,
        headline,
        " | ".join(
            contact
        ),
    ]

    if summary:
        parts += [
            "",
            "PROFESSIONAL SUMMARY",
            summary,
        ]

    if skills_text:
        parts += [
            "",
            "SKILLS",
            skills_text,
        ]

    if experience_text:
        parts += [
            "",
            "EXPERIENCE",
            experience_text,
        ]

    if education_text:
        parts += [
            "",
            "EDUCATION",
            education_text,
        ]

    return "\n".join(
        [
            x
            for x in parts
            if x is not None
        ]
    ).strip()


def _save_resume(
    conn,
    tenant_id,
    candidate_id,
    headline,
    summary,
    skills_text,
    experience_text,
    education_text,
):

    candidate=one(
        conn,
        """
        SELECT *
        FROM candidates
        WHERE tenant_id=?
          AND id=?
        """,
        (
            tenant_id,
            candidate_id,
        ),
    )

    if not candidate:
        raise ValueError(
            "Candidate not found"
        )

    resume_text=_render_resume(
        candidate,
        headline,
        summary,
        skills_text,
        experience_text,
        education_text,
    )

    version=(
        int(
            (
                one(
                    conn,
                    """
                    SELECT
                        COALESCE(
                            MAX(version),
                            0
                        ) max_version
                    FROM candidate_resume_versions_r23c
                    WHERE tenant_id=?
                      AND candidate_id=?
                    """,
                    (
                        tenant_id,
                        candidate_id,
                    ),
                )
                or {}
            ).get(
                "max_version"
            )
            or 0
        )
        +1
    )

    cur=conn.execute(
        """
        INSERT INTO
        candidate_resume_versions_r23c(
            tenant_id,
            candidate_id,
            version,
            headline,
            summary,
            skills_text,
            experience_text,
            education_text,
            resume_text,
            created_at
        )
        VALUES(
            ?,?,?,?,?,?,?,?,?,?
        )
        """,
        (
            tenant_id,
            candidate_id,
            version,
            headline,
            summary,
            skills_text,
            experience_text,
            education_text,
            resume_text,
            now(),
        ),
    )

    conn.execute(
        """
        UPDATE candidates
        SET
            current_title=
                CASE
                    WHEN ?<>'' THEN ?
                    ELSE current_title
                END,
            summary=?,
            resume_text=?,
            updated_at=?
        WHERE tenant_id=?
          AND id=?
        """,
        (
            headline,
            headline,
            summary,
            resume_text,
            now(),
            tenant_id,
            candidate_id,
        ),
    )

    return {
        "id":
            cur.lastrowid,

        "version":
            version,

        "headline":
            headline,

        "summary":
            summary,

        "skills_text":
            skills_text,

        "experience_text":
            experience_text,

        "education_text":
            education_text,

        "resume_text":
            resume_text,
    }


def _latest_resume(
    conn,
    tenant_id,
    candidate_id,
):

    return one(
        conn,
        """
        SELECT *
        FROM candidate_resume_versions_r23c
        WHERE tenant_id=?
          AND candidate_id=?
        ORDER BY version DESC
        LIMIT 1
        """,
        (
            tenant_id,
            candidate_id,
        ),
    )


def _saved_jobs(
    conn,
    tenant_id,
    candidate_id,
):

    return rows(
        conn,
        """
        SELECT
            s.id AS saved_id,
            s.created_at AS saved_at,

            j.id,
            j.job_no,
            j.title,
            j.city,
            j.state,
            j.country,
            j.work_mode,
            j.profession,
            j.specialty,
            j.pay_min,
            j.pay_max,
            j.rate_type,
            j.status

        FROM candidate_saved_jobs_r23c s

        JOIN jobs j
          ON j.id=s.job_id
         AND j.tenant_id=s.tenant_id

        WHERE s.tenant_id=?
          AND s.candidate_id=?

        ORDER BY s.id DESC
        """,
        (
            tenant_id,
            candidate_id,
        ),
    )


def _tokens(
    value,
):

    return {
        x
        for x
        in re.findall(
            r"[a-z0-9+#.]{2,}",
            str(
                value
                or ""
            ).lower(),
        )
    }


def _ideal_jobs(
    conn,
    candidate,
    limit=20,
):

    wanted=_tokens(
        " ".join(
            [
                str(
                    candidate.get(
                        "current_title"
                    )
                    or ""
                ),
                str(
                    candidate.get(
                        "profession"
                    )
                    or ""
                ),
                str(
                    candidate.get(
                        "specialty"
                    )
                    or ""
                ),
                str(
                    candidate.get(
                        "resume_text"
                    )
                    or ""
                ),
            ]
        )
    )

    result=[]

    for job in rows(
        conn,
        """
        SELECT
            id,
            job_no,
            title,
            city,
            state,
            country,
            work_mode,
            profession,
            specialty,
            required_skills,
            description,
            pay_min,
            pay_max,
            rate_type,
            status

        FROM jobs

        WHERE tenant_id=?
          AND lower(status)='open'

        ORDER BY updated_at DESC,id DESC
        LIMIT 500
        """,
        (
            candidate["tenant_id"],
        ),
    ):

        job_tokens=_tokens(
            " ".join(
                [
                    str(
                        job.get(
                            "title"
                        )
                        or ""
                    ),
                    str(
                        job.get(
                            "profession"
                        )
                        or ""
                    ),
                    str(
                        job.get(
                            "specialty"
                        )
                        or ""
                    ),
                    str(
                        job.get(
                            "required_skills"
                        )
                        or ""
                    ),
                    str(
                        job.get(
                            "description"
                        )
                        or ""
                    ),
                ]
            )
        )

        common=sorted(
            wanted
            &
            job_tokens
        )

        score=len(
            common
        )*10

        if (
            candidate.get(
                "state"
            )
            and job.get(
                "state"
            )
            and
            str(
                candidate["state"]
            ).lower()
            ==
            str(
                job["state"]
            ).lower()
        ):
            score+=8

        if (
            candidate.get(
                "city"
            )
            and job.get(
                "city"
            )
            and
            str(
                candidate["city"]
            ).lower()
            ==
            str(
                job["city"]
            ).lower()
        ):
            score+=5

        item=dict(
            job
        )

        item[
            "ideal_job_score"
        ]=score

        item[
            "match_terms"
        ]=common[:12]

        result.append(
            item
        )

    result.sort(
        key=lambda x:(
            -int(
                x[
                    "ideal_job_score"
                ]
            ),
            str(
                x.get(
                    "title"
                )
                or ""
            ).lower(),
        )
    )

    return result[
        :limit
    ]


def r23c_public_get(
    h,
    conn,
    path,
    qs,
):

    if (
        path
        ==
        "/api/r23c/public-registration"
    ):

        return send(
            h,
            {
                "resume_modes":[
                    {
                        "code":
                            key,

                        "label":
                            label,
                    }
                    for key,label
                    in
                    REGISTRATION_MODES.items()
                ],

                "supported_locales":[
                    {
                        "code":
                            key,

                        "label":
                            label,
                    }
                    for key,label
                    in
                    SUPPORTED_PORTAL_LOCALES.items()
                ],

                "resume_maker":
                    True,

                "resume_builder":
                    True,

                "register_without_resume":
                    True,

                "paste_resume":
                    True,
            },
        )

    return False


def r23c_public_post(
    h,
    conn,
    path,
    data,
):

    if (
        path
        !=
        "/api/r23c/register-candidate"
    ):
        return False

    tenant_id=1

    tenant=one(
        conn,
        """
        SELECT id
        FROM tenants
        WHERE id=?
        """,
        (
            tenant_id,
        ),
    )

    if not tenant:

        return send(
            h,
            {
                "error":
                    "Public candidate portal is not configured"
            },
            503,
        )

    first_name=str(
        data.get(
            "first_name"
        )
        or ""
    ).strip()[:100]

    last_name=str(
        data.get(
            "last_name"
        )
        or ""
    ).strip()[:100]

    email=_email(
        data.get(
            "email"
        )
    )

    password=str(
        data.get(
            "password"
        )
        or ""
    )

    mode=str(
        data.get(
            "resume_mode"
        )
        or "resume_maker"
    )

    locale=_locale(
        data.get(
            "locale"
        )
    )

    if (
        not first_name
        or not last_name
    ):

        return send(
            h,
            {
                "error":
                    "first_name and last_name required"
            },
            400,
        )

    if not email:

        return send(
            h,
            {
                "error":
                    "Valid email required"
            },
            400,
        )

    if (
        len(
            password
        )
        <10
    ):

        return send(
            h,
            {
                "error":
                    "Password must be at least 10 characters"
            },
            400,
        )

    if (
        mode
        not in
        REGISTRATION_MODES
    ):

        return send(
            h,
            {
                "error":
                    "Unsupported registration mode"
            },
            400,
        )

    if one(
        conn,
        """
        SELECT id
        FROM users
        WHERE lower(email)=lower(?)
        """,
        (
            email,
        ),
    ):

        return send(
            h,
            {
                "error":
                    "Account already exists"
            },
            409,
        )

    if one(
        conn,
        """
        SELECT id
        FROM candidates
        WHERE tenant_id=?
          AND lower(email)=lower(?)
        """,
        (
            tenant_id,
            email,
        ),
    ):

        return send(
            h,
            {
                "error":
                    "Candidate record already exists; use account recovery or recruiter invitation"
            },
            409,
        )

    headline=str(
        data.get(
            "headline"
        )
        or ""
    ).strip()[:250]

    summary=str(
        data.get(
            "summary"
        )
        or ""
    ).strip()[:5000]

    skills_text=str(
        data.get(
            "skills_text"
        )
        or ""
    ).strip()[:10000]

    experience_text=str(
        data.get(
            "experience_text"
        )
        or ""
    ).strip()[:20000]

    education_text=str(
        data.get(
            "education_text"
        )
        or ""
    ).strip()[:10000]

    pasted_resume=str(
        data.get(
            "resume_text"
        )
        or ""
    ).strip()[:100000]

    if (
        mode
        ==
        "paste_resume"
        and not pasted_resume
    ):

        return send(
            h,
            {
                "error":
                    "resume_text required for paste_resume"
            },
            400,
        )

    ts=now()

    cur=conn.execute(
        """
        INSERT INTO candidates(
            first_name,
            last_name,
            email,
            phone,
            city,
            state,
            country,
            profession,
            specialty,
            current_title,
            source,
            status,
            resume_text,
            summary,
            consent_sms,
            consent_email,
            created_at,
            updated_at,
            tenant_id
        )
        VALUES(
            ?,?,?,?,?,?,?,?,?,?,
            'Candidate Portal',
            'Active',
            ?,?,
            1,
            1,
            ?,?,?
        )
        """,
        (
            first_name,
            last_name,
            email,
            str(
                data.get(
                    "phone"
                )
                or ""
            ).strip()[:60],
            str(
                data.get(
                    "city"
                )
                or ""
            ).strip()[:100],
            str(
                data.get(
                    "state"
                )
                or ""
            ).strip()[:100],
            str(
                data.get(
                    "country"
                )
                or "USA"
            ).strip()[:100],
            str(
                data.get(
                    "profession"
                )
                or ""
            ).strip()[:150],
            str(
                data.get(
                    "specialty"
                )
                or ""
            ).strip()[:150],
            headline,
            (
                pasted_resume
                if mode
                ==
                "paste_resume"
                else ""
            ),
            summary,
            ts,
            ts,
            tenant_id,
        ),
    )

    candidate_id=(
        cur.lastrowid
    )

    ucur=conn.execute(
        """
        INSERT INTO users(
            email,
            pass_hash,
            name,
            role,
            candidate_id,
            active,
            created_at,
            tenant_id
        )
        VALUES(
            ?,?,?,?,
            ?,
            1,
            ?,?
        )
        """,
        (
            email,
            _hash_password(
                password
            ),
            (
                first_name
                +" "
                +last_name
            ).strip(),
            "candidate",
            candidate_id,
            ts,
            tenant_id,
        ),
    )

    user_id=(
        ucur.lastrowid
    )

    conn.execute(
        """
        INSERT INTO
        candidate_locale_preferences_r22(
            tenant_id,
            candidate_id,
            locale,
            updated_at,
            updated_by
        )
        VALUES(
            ?,?,?,?,?
        )

        ON CONFLICT(
            tenant_id,
            candidate_id
        )

        DO UPDATE SET
            locale=excluded.locale,
            updated_at=excluded.updated_at,
            updated_by=excluded.updated_by
        """,
        (
            tenant_id,
            candidate_id,
            locale,
            ts,
            user_id,
        ),
    )

    if (
        mode
        ==
        "resume_maker"
    ):

        _save_resume(
            conn,
            tenant_id,
            candidate_id,
            headline,
            summary,
            skills_text,
            experience_text,
            education_text,
        )

    conn.execute(
        """
        INSERT INTO
        candidate_registration_audit_r23c(
            tenant_id,
            candidate_id,
            user_id,
            registration_mode,
            locale,
            created_at
        )
        VALUES(
            ?,?,?,?,?,?
        )
        """,
        (
            tenant_id,
            candidate_id,
            user_id,
            mode,
            locale,
            ts,
        ),
    )

    conn.commit()

    return send(
        h,
        {
            "ok":
                True,

            "candidate_id":
                candidate_id,

            "user_id":
                user_id,

            "registration_mode":
                mode,

            "locale":
                locale,
        },
        201,
    )


def r23c_get(
    h,
    conn,
    u,
    path,
    qs,
):

    if (
        path
        ==
        "/api/r23c/candidate-portal"
    ):

        candidate=_candidate(
            conn,
            u,
        )

        if not candidate:

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
            {
                "candidate":
                    candidate,

                "latest_resume":
                    _latest_resume(
                        conn,
                        u[
                            "tenant_id"
                        ],
                        u[
                            "candidate_id"
                        ],
                    ),

                "resume_versions":
                    rows(
                        conn,
                        """
                        SELECT
                            id,
                            version,
                            headline,
                            created_at
                        FROM candidate_resume_versions_r23c
                        WHERE tenant_id=?
                          AND candidate_id=?
                        ORDER BY version DESC
                        LIMIT 25
                        """,
                        (
                            u[
                                "tenant_id"
                            ],
                            u[
                                "candidate_id"
                            ],
                        ),
                    ),

                "saved_jobs":
                    _saved_jobs(
                        conn,
                        u[
                            "tenant_id"
                        ],
                        u[
                            "candidate_id"
                        ],
                    ),

                "ideal_jobs":
                    _ideal_jobs(
                        conn,
                        candidate,
                    ),

                "supported_locales":
                    [
                        {
                            "code":
                                key,

                            "label":
                                value,
                        }
                        for key,value
                        in
                        SUPPORTED_PORTAL_LOCALES.items()
                    ],
            },
        )

    if (
        path
        ==
        "/api/r23c/resume-builder"
    ):

        candidate=_candidate(
            conn,
            u,
        )

        if not candidate:

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
            {
                "candidate":
                    candidate,

                "latest":
                    _latest_resume(
                        conn,
                        u[
                            "tenant_id"
                        ],
                        u[
                            "candidate_id"
                        ],
                    ),

                "versions":
                    rows(
                        conn,
                        """
                        SELECT
                            id,
                            version,
                            headline,
                            created_at
                        FROM candidate_resume_versions_r23c
                        WHERE tenant_id=?
                          AND candidate_id=?
                        ORDER BY version DESC
                        LIMIT 50
                        """,
                        (
                            u[
                                "tenant_id"
                            ],
                            u[
                                "candidate_id"
                            ],
                        ),
                    ),
            },
        )

    if (
        path
        ==
        "/api/r23c/saved-jobs"
    ):

        if not _candidate_user(
            u
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
            _saved_jobs(
                conn,
                u[
                    "tenant_id"
                ],
                u[
                    "candidate_id"
                ],
            ),
        )

    if (
        path
        ==
        "/api/r23c/ideal-jobs"
    ):

        candidate=_candidate(
            conn,
            u,
        )

        if not candidate:

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
            _ideal_jobs(
                conn,
                candidate,
            ),
        )

    return False


def r23c_post(
    h,
    conn,
    u,
    path,
    data,
):

    if (
        path
        ==
        "/api/r23c/resume-builder"
    ):

        candidate=_candidate(
            conn,
            u,
        )

        if not candidate:

            return send(
                h,
                {
                    "error":
                        "Permission denied"
                },
                403,
            )

        headline=str(
            data.get(
                "headline"
            )
            or candidate.get(
                "current_title"
            )
            or ""
        ).strip()[:250]

        summary=str(
            data.get(
                "summary"
            )
            or ""
        ).strip()[:5000]

        skills_text=str(
            data.get(
                "skills_text"
            )
            or ""
        ).strip()[:10000]

        experience_text=str(
            data.get(
                "experience_text"
            )
            or ""
        ).strip()[:20000]

        education_text=str(
            data.get(
                "education_text"
            )
            or ""
        ).strip()[:10000]

        result=_save_resume(
            conn,
            u[
                "tenant_id"
            ],
            u[
                "candidate_id"
            ],
            headline,
            summary,
            skills_text,
            experience_text,
            education_text,
        )

        conn.commit()

        return send(
            h,
            result,
            201,
        )

    if (
        path
        ==
        "/api/r23c/saved-jobs"
    ):

        if not _candidate_user(
            u
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

            job_id=int(
                data.get(
                    "job_id"
                )
            )

        except Exception:

            return send(
                h,
                {
                    "error":
                        "job_id required"
                },
                400,
            )

        job=one(
            conn,
            """
            SELECT id
            FROM jobs
            WHERE tenant_id=?
              AND id=?
              AND lower(status)='open'
            """,
            (
                u[
                    "tenant_id"
                ],
                job_id,
            ),
        )

        if not job:

            return send(
                h,
                {
                    "error":
                        "Open job not found"
                },
                404,
            )

        conn.execute(
            """
            INSERT OR IGNORE INTO
            candidate_saved_jobs_r23c(
                tenant_id,
                candidate_id,
                job_id,
                created_at
            )
            VALUES(
                ?,?,?,?
            )
            """,
            (
                u[
                    "tenant_id"
                ],
                u[
                    "candidate_id"
                ],
                job_id,
                now(),
            ),
        )

        conn.commit()

        return send(
            h,
            {
                "ok":
                    True,

                "saved_job":
                    True,

                "job_id":
                    job_id,
            },
            201,
        )

    m=re.fullmatch(
        r"/api/r23c/saved-jobs/(\d+)/remove",
        path,
    )

    if m:

        if not _candidate_user(
            u
        ):

            return send(
                h,
                {
                    "error":
                        "Permission denied"
                },
                403,
            )

        job_id=int(
            m.group(
                1
            )
        )

        conn.execute(
            """
            DELETE FROM
            candidate_saved_jobs_r23c

            WHERE tenant_id=?
              AND candidate_id=?
              AND job_id=?
            """,
            (
                u[
                    "tenant_id"
                ],
                u[
                    "candidate_id"
                ],
                job_id,
            ),
        )

        conn.commit()

        return send(
            h,
            {
                "ok":
                    True,

                "saved_job":
                    False,

                "job_id":
                    job_id,
            },
        )

    return False
