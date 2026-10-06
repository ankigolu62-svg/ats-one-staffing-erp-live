from __future__ import annotations

import csv
import io
import json
import re

from datetime import datetime,timedelta,timezone

from r14_api import REPORT_ENTITIES
from r18_api import (
    allrows,
    one,
    _tenant,
    _run_connector,
    _connector_state,
    now,
    audit,
)


INTERNAL={"admin","teamlead","recruiter","sales","hr","finance"}
ADMIN={"admin","teamlead"}
RECRUITING={"admin","teamlead","recruiter","sales","hr"}


def _cols(conn,table):
    return {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}


def _addcol(conn,table,name,decl):
    if name not in _cols(conn,table):
        conn.execute(
            f"ALTER TABLE {table} ADD COLUMN {name} {decl}"
        )


def ensure_r19_schema(conn):

    for table,name,decl in [
        ("external_gateways_r14","connector_id","INTEGER"),
        ("external_gateways_r14","last_provider_status","INTEGER"),
        ("external_gateways_r14","last_provider_reference","TEXT"),

        ("campaigns_r14","connector_id","INTEGER"),
        ("campaigns_r14","last_run_at","TEXT"),

        ("report_schedules_r14","connector_id","INTEGER"),
        ("report_schedules_r14","last_error","TEXT"),

        ("job_alerts_r14","connector_id","INTEGER"),

        ("interviews","meeting_connector_id","INTEGER"),
        ("interviews","meeting_provider_id","TEXT"),
        ("interviews","meeting_status","TEXT"),
        ("interviews","recording_url","TEXT"),

        ("candidate_background_cases","connector_id","INTEGER"),
        ("esign_envelopes_r14","connector_id","INTEGER"),
        ("employment_verifications_r14","connector_id","INTEGER"),
        ("payroll_batches_r14","connector_id","INTEGER"),
    ]:
        _addcol(conn,table,name,decl)

    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS external_transactions_r19(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,
            action TEXT NOT NULL,
            entity_type TEXT,
            entity_id INTEGER,
            connector_id INTEGER NOT NULL,
            status TEXT NOT NULL,
            provider_id TEXT,
            provider_http_status INTEGER,
            detail TEXT,
            user_id INTEGER,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            tenant_id INTEGER NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_external_tx_r19_tenant
        ON external_transactions_r19(tenant_id,id);

        CREATE TABLE IF NOT EXISTS campaign_runs_r19(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER NOT NULL,
            connector_id INTEGER,
            status TEXT NOT NULL,
            total INTEGER DEFAULT 0,
            delivered INTEGER DEFAULT 0,
            failed INTEGER DEFAULT 0,
            skipped INTEGER DEFAULT 0,
            detail TEXT,
            started_at TEXT NOT NULL,
            finished_at TEXT,
            user_id INTEGER,
            tenant_id INTEGER NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_campaign_runs_r19
        ON campaign_runs_r19(tenant_id,campaign_id,id);

        CREATE TABLE IF NOT EXISTS report_runs_r19(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            schedule_id INTEGER,
            report_id INTEGER NOT NULL,
            status TEXT NOT NULL,
            row_count INTEGER DEFAULT 0,
            output_format TEXT,
            artifact_text TEXT,
            delivery_status TEXT,
            error TEXT,
            started_at TEXT NOT NULL,
            finished_at TEXT,
            user_id INTEGER,
            tenant_id INTEGER NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_report_runs_r19
        ON report_runs_r19(tenant_id,report_id,id);

        CREATE TABLE IF NOT EXISTS job_alert_runs_r19(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            alert_id INTEGER NOT NULL,
            match_count INTEGER DEFAULT 0,
            status TEXT NOT NULL,
            detail TEXT,
            created_at TEXT NOT NULL,
            user_id INTEGER,
            tenant_id INTEGER NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_job_alert_runs_r19
        ON job_alert_runs_r19(tenant_id,alert_id,id);
        """
    )

    # Known historical seed wording must not pretend to be a live post.
    conn.execute(
        """
        UPDATE job_distribution
        SET channel='LinkedIn',
            status='Credentials Required',
            external_post_id=NULL,
            last_sync=NULL,
            applications=0
        WHERE lower(COALESCE(channel,''))='linkedin-style demo'
        """
    )

    conn.commit()


def _report_data(conn,u,report):

    entity=str(report.get("entity_type") or "")

    if entity not in REPORT_ENTITIES:
        raise ValueError("Unsupported report entity")

    table,allowed=REPORT_ENTITIES[entity]

    actual=_cols(conn,table)

    allowed=[
        c for c in allowed
        if c in actual
    ]

    if not allowed:
        raise ValueError("Report has no available columns")

    try:
        selected=json.loads(
            report.get("columns_json") or "[]"
        )
    except Exception:
        selected=[]

    selected=[
        c for c in selected
        if c in allowed
    ]

    if not selected:
        selected=allowed[:10]

    try:
        filters=json.loads(
            report.get("filters_json") or "{}"
        )
    except Exception:
        filters={}

    where=["tenant_id=?"]
    params=[u["tenant_id"]]

    for key,value in filters.items():

        if (
            key in allowed
            and value not in (None,"")
        ):
            where.append(
                f"CAST({key} AS TEXT) LIKE ?"
            )
            params.append("%"+str(value)+"%")

    sql=(
        f"SELECT {','.join(selected)} "
        f"FROM {table} "
        f"WHERE {' AND '.join(where)} "
        "LIMIT 5000"
    )

    return selected,allrows(conn,sql,params)


def _report_artifact(columns,rows,fmt):

    fmt=str(fmt or "CSV").upper()

    if fmt=="JSON":
        return json.dumps(rows,indent=2,default=str)

    out=io.StringIO()

    writer=csv.DictWriter(
        out,
        fieldnames=columns,
        extrasaction="ignore"
    )

    writer.writeheader()

    for row in rows:
        writer.writerow(row)

    return out.getvalue()


def _next_run(freq):

    n=datetime.now(timezone.utc)

    f=str(freq or "Weekly").lower()

    if f=="daily":
        n+=timedelta(days=1)
    elif f=="monthly":
        n+=timedelta(days=30)
    else:
        n+=timedelta(days=7)

    return n.replace(microsecond=0).isoformat()


def _gateway_connector(conn,gateway,u):

    cid=gateway.get("connector_id")

    if not cid:
        return None

    return _tenant(
        conn,
        "integration_connectors",
        int(cid),
        u
    )


def _domain_record_after_external(
    conn,u,category,data,result
):

    if not result.get("ok"):
        return

    provider_id=result.get("provider_id")
    ts=now()

    if (
        category=="background"
        and data.get("background_case_id")
    ):

        row=_tenant(
            conn,
            "candidate_background_cases",
            int(data["background_case_id"]),
            u
        )

        if row:
            conn.execute(
                """
                UPDATE candidate_background_cases
                SET status='Submitted',
                    external_id=?,
                    requested_at=COALESCE(requested_at,?),
                    connector_id=?,
                    updated_at=?
                WHERE id=? AND tenant_id=?
                """,
                (
                    provider_id,ts,
                    int(data["connector_id"]),
                    ts,row["id"],u["tenant_id"]
                )
            )

    elif (
        category=="esign"
        and data.get("esign_envelope_id")
    ):

        row=_tenant(
            conn,
            "esign_envelopes_r14",
            int(data["esign_envelope_id"]),
            u
        )

        if row:
            conn.execute(
                """
                UPDATE esign_envelopes_r14
                SET status='Sent',
                    external_id=?,
                    sent_at=COALESCE(sent_at,?),
                    connector_id=?,
                    updated_at=?
                WHERE id=? AND tenant_id=?
                """,
                (
                    provider_id,ts,
                    int(data["connector_id"]),
                    ts,row["id"],u["tenant_id"]
                )
            )

    elif (
        category=="everify"
        and data.get("verification_id")
    ):

        row=_tenant(
            conn,
            "employment_verifications_r14",
            int(data["verification_id"]),
            u
        )

        if row:
            conn.execute(
                """
                UPDATE employment_verifications_r14
                SET status='Submitted',
                    external_id=?,
                    submitted_at=COALESCE(submitted_at,?),
                    connector_id=?,
                    updated_at=?
                WHERE id=? AND tenant_id=?
                """,
                (
                    provider_id,ts,
                    int(data["connector_id"]),
                    ts,row["id"],u["tenant_id"]
                )
            )

    elif (
        category in {"payroll","gl"}
        and data.get("payroll_batch_id")
    ):

        row=_tenant(
            conn,
            "payroll_batches_r14",
            int(data["payroll_batch_id"]),
            u
        )

        if row:
            conn.execute(
                """
                UPDATE payroll_batches_r14
                SET status='Submitted',
                    external_id=?,
                    connector_id=?,
                    updated_at=?
                WHERE id=? AND tenant_id=?
                """,
                (
                    provider_id,
                    int(data["connector_id"]),
                    ts,row["id"],u["tenant_id"]
                )
            )


def r19_get(h,conn,u,path,qs):

    if path=="/api/r19/coverage":

        h._json({
            "version":"R19",
            "campaign_executor":"working",
            "report_scheduler_executor":"working",
            "job_alert_executor":"working",
            "external_gateway_http":"working",
            "external_workflow_actions":"working",
            "meeting_provider_adapter":"working",
            "candidate_duplicate_intelligence":"working",
            "external_provider_truth_gate":"working"
        })

        return True

    if path=="/api/r19/campaigns":

        if u["role"] not in INTERNAL:
            h._json({"error":"Permission denied"},403)
            return True

        rows=allrows(
            conn,
            """
            SELECT
                c.*,
                (
                    SELECT COUNT(*)
                    FROM campaign_members_r14 m
                    WHERE m.campaign_id=c.id
                      AND m.tenant_id=c.tenant_id
                ) member_count,
                (
                    SELECT COUNT(*)
                    FROM campaign_members_r14 m
                    WHERE m.campaign_id=c.id
                      AND m.tenant_id=c.tenant_id
                      AND lower(m.status)='delivered'
                ) delivered_count
            FROM campaigns_r14 c
            WHERE c.tenant_id=?
            ORDER BY c.id DESC
            """,
            (u["tenant_id"],)
        )

        for row in rows:

            connector=None

            if row.get("connector_id"):
                connector=_tenant(
                    conn,
                    "integration_connectors",
                    int(row["connector_id"]),
                    u
                )

            row["connector_state"]=(
                _connector_state(connector)
                if connector
                else (
                    "Internal"
                    if str(row.get("channel")).lower()=="internal"
                    else "Credentials Required"
                )
            )

        h._json(rows)
        return True

    m=re.fullmatch(r"/api/r19/campaigns/(\d+)",path)

    if m:

        if u["role"] not in INTERNAL:
            h._json({"error":"Permission denied"},403)
            return True

        campaign=_tenant(
            conn,
            "campaigns_r14",
            int(m.group(1)),
            u
        )

        if not campaign:
            h._json({"error":"Not found"},404)
            return True

        campaign["members"]=allrows(
            conn,
            """
            SELECT
                m.*,
                c.first_name,
                c.last_name,
                c.email,
                c.phone
            FROM campaign_members_r14 m
            LEFT JOIN candidates c
                   ON c.id=m.candidate_id
            WHERE m.campaign_id=?
              AND m.tenant_id=?
            ORDER BY m.id
            """,
            (campaign["id"],u["tenant_id"])
        )

        campaign["runs"]=allrows(
            conn,
            """
            SELECT *
            FROM campaign_runs_r19
            WHERE campaign_id=?
              AND tenant_id=?
            ORDER BY id DESC
            LIMIT 50
            """,
            (campaign["id"],u["tenant_id"])
        )

        h._json(campaign)
        return True

    if path=="/api/r19/report-schedules":

        if u["role"] not in INTERNAL:
            h._json({"error":"Permission denied"},403)
            return True

        rows=allrows(
            conn,
            """
            SELECT
                s.*,
                r.name report_name,
                r.entity_type
            FROM report_schedules_r14 s
            JOIN report_builders_r14 r
              ON r.id=s.report_id
             AND r.tenant_id=s.tenant_id
            WHERE s.tenant_id=?
            ORDER BY s.id DESC
            """,
            (u["tenant_id"],)
        )

        for row in rows:

            connector=None

            if row.get("connector_id"):
                connector=_tenant(
                    conn,
                    "integration_connectors",
                    int(row["connector_id"]),
                    u
                )

            row["connector_state"]=(
                _connector_state(connector)
                if connector
                else (
                    "Not Required"
                    if not row.get("recipients")
                    else "Credentials Required"
                )
            )

        h._json(rows)
        return True

    if path=="/api/r19/report-runs":

        if u["role"] not in INTERNAL:
            h._json({"error":"Permission denied"},403)
            return True

        h._json(
            allrows(
                conn,
                """
                SELECT *
                FROM report_runs_r19
                WHERE tenant_id=?
                ORDER BY id DESC
                LIMIT 100
                """,
                (u["tenant_id"],)
            )
        )

        return True

    if path=="/api/r19/external-gateways":

        if u["role"] not in ADMIN:
            h._json({"error":"Permission denied"},403)
            return True

        rows=allrows(
            conn,
            """
            SELECT *
            FROM external_gateways_r14
            WHERE tenant_id=?
            ORDER BY category,provider
            """,
            (u["tenant_id"],)
        )

        for row in rows:

            connector=_gateway_connector(
                conn,row,u
            )

            row["connection_state"]=(
                _connector_state(connector)
                if connector
                else "Configuration Required"
            )

            if connector:
                row["connector_name"]=connector.get("name")

        h._json(rows)
        return True

    if path=="/api/r19/external-transactions":

        if u["role"] not in ADMIN|{"hr","finance"}:
            h._json({"error":"Permission denied"},403)
            return True

        h._json(
            allrows(
                conn,
                """
                SELECT *
                FROM external_transactions_r19
                WHERE tenant_id=?
                ORDER BY id DESC
                LIMIT 200
                """,
                (u["tenant_id"],)
            )
        )

        return True

    if path=="/api/r19/job-alerts":

        if u["role"] not in RECRUITING:
            h._json({"error":"Permission denied"},403)
            return True

        h._json(
            allrows(
                conn,
                """
                SELECT *
                FROM job_alerts_r14
                WHERE tenant_id=?
                ORDER BY id DESC
                """,
                (u["tenant_id"],)
            )
        )

        return True

    m=re.fullmatch(
        r"/api/r19/candidates/(\d+)/duplicates",
        path
    )

    if m:

        if u["role"] not in RECRUITING:
            h._json({"error":"Permission denied"},403)
            return True

        cid=int(m.group(1))

        source=_tenant(
            conn,
            "candidates",
            cid,
            u
        )

        if not source:
            h._json({"error":"Candidate not found"},404)
            return True

        rows=allrows(
            conn,
            """
            SELECT
                id,first_name,last_name,email,phone,
                city,state,zip,current_title,status
            FROM candidates
            WHERE tenant_id=?
              AND id<>?
              AND lower(COALESCE(status,''))<>'archived'
            """,
            (u["tenant_id"],cid)
        )

        results=[]

        source_name=(
            str(source.get("first_name") or "").strip().lower()
            +" "
            +str(source.get("last_name") or "").strip().lower()
        ).strip()

        for row in rows:

            score=0
            reasons=[]

            if (
                source.get("email")
                and row.get("email")
                and str(source["email"]).strip().lower()
                    ==str(row["email"]).strip().lower()
            ):
                score=max(score,100)
                reasons.append("exact_email")

            if (
                source.get("phone")
                and row.get("phone")
                and re.sub(r"\D","",str(source["phone"]))
                    ==re.sub(r"\D","",str(row["phone"]))
            ):
                score=max(score,95)
                reasons.append("exact_phone")

            row_name=(
                str(row.get("first_name") or "").strip().lower()
                +" "
                +str(row.get("last_name") or "").strip().lower()
            ).strip()

            if source_name and source_name==row_name:
                score=max(score,75)
                reasons.append("exact_name")

                if (
                    source.get("zip")
                    and row.get("zip")
                    and str(source["zip"]).lower()
                       ==str(row["zip"]).lower()
                ):
                    score=max(score,85)
                    reasons.append("same_zip")

            if score>=70:
                results.append({
                    **row,
                    "duplicate_score":score,
                    "reasons":reasons
                })

        results.sort(
            key=lambda x:(-x["duplicate_score"],x["id"])
        )

        h._json({
            "candidate_id":cid,
            "results":results
        })

        return True

    return False


def r19_post(h,conn,u,path,data):

    # ==============================================================
    # CAMPAIGN CREATE
    # ==============================================================

    if path=="/api/r19/campaigns":

        if u["role"] not in INTERNAL:
            h._json({"error":"Permission denied"},403)
            return True

        name=str(data.get("name") or "").strip()

        if not name:
            h._json({"error":"Campaign name required"},400)
            return True

        channel=str(data.get("channel") or "Email")

        if channel not in {
            "Internal","Email","SMS"
        }:
            h._json({"error":"Unsupported channel"},400)
            return True

        connector_id=data.get("connector_id")

        if connector_id and not _tenant(
            conn,
            "integration_connectors",
            int(connector_id),
            u
        ):
            h._json({"error":"Connector not found"},404)
            return True

        ts=now()

        cur=conn.execute(
            """
            INSERT INTO campaigns_r14(
                name,channel,subject,body,status,
                scheduled_at,sent_at,owner_user_id,
                created_at,updated_at,tenant_id,
                connector_id,last_run_at
            )
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                name,channel,
                data.get("subject"),
                data.get("body"),
                "Draft",
                data.get("scheduled_at"),
                None,
                u["id"],
                ts,ts,
                u["tenant_id"],
                connector_id,
                None
            )
        )

        campaign_id=cur.lastrowid

        for raw_cid in data.get("candidate_ids") or []:

            cid=int(raw_cid)

            if not _tenant(
                conn,
                "candidates",
                cid,
                u
            ):
                continue

            conn.execute(
                """
                INSERT OR IGNORE INTO campaign_members_r14(
                    campaign_id,candidate_id,status,
                    created_at,tenant_id
                )
                VALUES(?,?,'Queued',?,?)
                """,
                (
                    campaign_id,cid,
                    ts,u["tenant_id"]
                )
            )

        audit(
            conn,u,
            "CREATE",
            "campaign",
            campaign_id,
            name,
            h.client_address[0]
        )

        conn.commit()

        h._json(
            {"id":campaign_id},
            201
        )

        return True

    # ==============================================================
    # CAMPAIGN EXECUTOR
    # ==============================================================

    m=re.fullmatch(
        r"/api/r19/campaigns/(\d+)/run",
        path
    )

    if m:

        if u["role"] not in INTERNAL:
            h._json({"error":"Permission denied"},403)
            return True

        campaign=_tenant(
            conn,
            "campaigns_r14",
            int(m.group(1)),
            u
        )

        if not campaign:
            h._json({"error":"Campaign not found"},404)
            return True

        members=allrows(
            conn,
            """
            SELECT
                m.*,
                c.first_name,
                c.last_name,
                c.email,
                c.phone,
                c.do_not_contact,
                c.consent_email,
                c.consent_sms
            FROM campaign_members_r14 m
            JOIN candidates c
              ON c.id=m.candidate_id
             AND c.tenant_id=m.tenant_id
            WHERE m.campaign_id=?
              AND m.tenant_id=?
              AND lower(COALESCE(m.status,'')) NOT IN (
                  'delivered','unsubscribed'
              )
            ORDER BY m.id
            """,
            (campaign["id"],u["tenant_id"])
        )

        if not members:
            h._json(
                {"error":"Campaign has no queued recipients"},
                409
            )
            return True

        channel=str(campaign.get("channel") or "Email")
        connector=None

        connector_id=(
            data.get("connector_id")
            or campaign.get("connector_id")
        )

        if channel!="Internal":

            if not connector_id:
                h._json(
                    {
                        "error":"Credentials Required",
                        "status":"Credentials Required"
                    },
                    409
                )
                return True

            connector=_tenant(
                conn,
                "integration_connectors",
                int(connector_id),
                u
            )

            if not connector:
                h._json({"error":"Connector not found"},404)
                return True

        started=now()

        run_cur=conn.execute(
            """
            INSERT INTO campaign_runs_r19(
                campaign_id,connector_id,status,
                total,delivered,failed,skipped,
                detail,started_at,user_id,tenant_id
            )
            VALUES(?,?, 'Running', ?,0,0,0,'',?,?,?)
            """,
            (
                campaign["id"],
                connector_id,
                len(members),
                started,
                u["id"],
                u["tenant_id"]
            )
        )

        run_id=run_cur.lastrowid

        delivered=0
        failed=0
        skipped=0

        for member in members:

            cid=member["candidate_id"]

            if member.get("do_not_contact"):
                status="Skipped DNC"
                skipped+=1

            elif (
                channel=="Email"
                and not member.get("email")
            ):
                status="Failed"
                failed+=1

            elif (
                channel=="Email"
                and int(member.get("consent_email") or 0)==0
            ):
                status="Skipped Consent"
                skipped+=1

            elif (
                channel=="SMS"
                and (
                    not member.get("phone")
                    or int(member.get("consent_sms") or 0)==0
                )
            ):
                status="Skipped Consent"
                skipped+=1

            elif channel=="Internal":

                conn.execute(
                    """
                    INSERT INTO communications(
                        entity_type,entity_id,channel,direction,
                        subject,body,user_id,status,
                        created_at,tenant_id
                    )
                    VALUES(
                        'candidate',?,'Internal','Outbound',
                        ?,?,?,'Logged',?,?
                    )
                    """,
                    (
                        cid,
                        campaign.get("subject"),
                        campaign.get("body"),
                        u["id"],
                        now(),
                        u["tenant_id"]
                    )
                )

                status="Delivered"
                delivered+=1

            else:

                action=(
                    "send_email"
                    if channel=="Email"
                    else "send_sms"
                )

                destination=(
                    member.get("email")
                    if channel=="Email"
                    else member.get("phone")
                )

                result=_run_connector(
                    conn,u,connector,action,{
                        "to":destination,
                        "subject":campaign.get("subject"),
                        "body":campaign.get("body"),
                        "candidate_id":cid,
                        "campaign_id":campaign["id"]
                    }
                )

                if result.get("ok"):
                    status="Delivered"
                    delivered+=1
                else:
                    status=result.get("status") or "Failed"
                    failed+=1

                conn.execute(
                    """
                    INSERT INTO communications(
                        entity_type,entity_id,channel,direction,
                        subject,body,user_id,status,
                        created_at,tenant_id
                    )
                    VALUES(
                        'candidate',?,?, 'Outbound',
                        ?,?,?,?, ?,?
                    )
                    """,
                    (
                        cid,channel,
                        campaign.get("subject"),
                        campaign.get("body"),
                        u["id"],
                        "Sent" if result.get("ok") else status,
                        now(),
                        u["tenant_id"]
                    )
                )

            conn.execute(
                """
                UPDATE campaign_members_r14
                SET status=?,
                    delivered_at=CASE
                      WHEN ?='Delivered' THEN ?
                      ELSE delivered_at
                    END
                WHERE id=? AND tenant_id=?
                """,
                (
                    status,status,now(),
                    member["id"],u["tenant_id"]
                )
            )

        if delivered and not failed:
            final="Completed"
        elif delivered:
            final="Partially Completed"
        else:
            final="Failed"

        finished=now()

        conn.execute(
            """
            UPDATE campaign_runs_r19
            SET status=?,
                delivered=?,
                failed=?,
                skipped=?,
                finished_at=?,
                detail=?
            WHERE id=? AND tenant_id=?
            """,
            (
                final,
                delivered,
                failed,
                skipped,
                finished,
                f"delivered={delivered};failed={failed};skipped={skipped}",
                run_id,u["tenant_id"]
            )
        )

        conn.execute(
            """
            UPDATE campaigns_r14
            SET status=?,
                sent_at=?,
                last_run_at=?,
                connector_id=COALESCE(?,connector_id),
                updated_at=?
            WHERE id=? AND tenant_id=?
            """,
            (
                final,
                finished if delivered else campaign.get("sent_at"),
                finished,
                connector_id,
                finished,
                campaign["id"],
                u["tenant_id"]
            )
        )

        audit(
            conn,u,
            "RUN",
            "campaign",
            campaign["id"],
            final,
            h.client_address[0]
        )

        conn.commit()

        h._json({
            "run_id":run_id,
            "status":final,
            "total":len(members),
            "delivered":delivered,
            "failed":failed,
            "skipped":skipped
        })

        return True

    # ==============================================================
    # REPORT SCHEDULE CREATE
    # ==============================================================

    if path=="/api/r19/report-schedules":

        if u["role"] not in INTERNAL:
            h._json({"error":"Permission denied"},403)
            return True

        report=_tenant(
            conn,
            "report_builders_r14",
            int(data.get("report_id") or 0),
            u
        )

        if not report:
            h._json({"error":"Report not found"},404)
            return True

        connector_id=data.get("connector_id")

        if connector_id and not _tenant(
            conn,
            "integration_connectors",
            int(connector_id),
            u
        ):
            h._json({"error":"Connector not found"},404)
            return True

        ts=now()

        cur=conn.execute(
            """
            INSERT INTO report_schedules_r14(
                report_id,frequency,recipients,format,
                active,last_run_at,next_run_at,
                created_at,updated_at,tenant_id,
                connector_id,last_error
            )
            VALUES(?,?,?,?,1,NULL,?,?,?,?,?,NULL)
            """,
            (
                report["id"],
                data.get("frequency") or "Weekly",
                data.get("recipients"),
                str(data.get("format") or "CSV").upper(),
                _next_run(data.get("frequency")),
                ts,ts,
                u["tenant_id"],
                connector_id
            )
        )

        audit(
            conn,u,
            "CREATE",
            "report_schedule",
            cur.lastrowid,
            report.get("name") or "",
            h.client_address[0]
        )

        conn.commit()

        h._json({"id":cur.lastrowid},201)
        return True

    # ==============================================================
    # REPORT EXECUTION
    # ==============================================================

    m=re.fullmatch(
        r"/api/r19/report-schedules/(\d+)/run",
        path
    )

    if m:

        if u["role"] not in INTERNAL:
            h._json({"error":"Permission denied"},403)
            return True

        schedule=_tenant(
            conn,
            "report_schedules_r14",
            int(m.group(1)),
            u
        )

        if not schedule:
            h._json({"error":"Schedule not found"},404)
            return True

        if not int(schedule.get("active") or 0):
            h._json({"error":"Schedule is inactive"},409)
            return True

        report=_tenant(
            conn,
            "report_builders_r14",
            int(schedule["report_id"]),
            u
        )

        if not report:
            h._json({"error":"Report not found"},404)
            return True

        started=now()

        try:
            columns,rows=_report_data(
                conn,u,report
            )

            artifact=_report_artifact(
                columns,
                rows,
                schedule.get("format")
            )

            delivery="Not Required"
            error=None

            recipients=str(
                schedule.get("recipients") or ""
            ).strip()

            if recipients:

                cid=(
                    data.get("connector_id")
                    or schedule.get("connector_id")
                )

                if not cid:
                    delivery="Credentials Required"
                    error="Delivery connector is not configured"

                else:

                    connector=_tenant(
                        conn,
                        "integration_connectors",
                        int(cid),
                        u
                    )

                    if not connector:
                        delivery="Configuration Required"
                        error="Delivery connector not found"

                    else:

                        result=_run_connector(
                            conn,u,connector,
                            "send_email",
                            {
                                "to":recipients,
                                "subject":"Scheduled report: "
                                    +str(report.get("name") or ""),
                                "body":"ATS-One scheduled report attached.",
                                "attachment":{
                                    "name":
                                      str(report.get("name") or "report")
                                      +"."
                                      +str(schedule.get("format") or "csv").lower(),
                                    "content":artifact
                                }
                            }
                        )

                        delivery=(
                            "Delivered"
                            if result.get("ok")
                            else result.get("status")
                        )

                        if not result.get("ok"):
                            error=result.get("detail")

            final=(
                "Generated"
                if delivery in {
                    "Not Required","Delivered"
                }
                else "Generated - Delivery Pending"
            )

            cur=conn.execute(
                """
                INSERT INTO report_runs_r19(
                    schedule_id,report_id,status,row_count,
                    output_format,artifact_text,
                    delivery_status,error,
                    started_at,finished_at,
                    user_id,tenant_id
                )
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    schedule["id"],
                    report["id"],
                    final,
                    len(rows),
                    schedule.get("format") or "CSV",
                    artifact,
                    delivery,
                    error,
                    started,
                    now(),
                    u["id"],
                    u["tenant_id"]
                )
            )

            conn.execute(
                """
                UPDATE report_schedules_r14
                SET last_run_at=?,
                    next_run_at=?,
                    last_error=?,
                    connector_id=COALESCE(?,connector_id),
                    updated_at=?
                WHERE id=? AND tenant_id=?
                """,
                (
                    now(),
                    _next_run(schedule.get("frequency")),
                    error,
                    data.get("connector_id"),
                    now(),
                    schedule["id"],
                    u["tenant_id"]
                )
            )

            audit(
                conn,u,
                "RUN",
                "report_schedule",
                schedule["id"],
                final,
                h.client_address[0]
            )

            conn.commit()

            h._json({
                "run_id":cur.lastrowid,
                "status":final,
                "row_count":len(rows),
                "delivery_status":delivery
            })

        except Exception as exc:

            conn.rollback()

            h._json(
                {
                    "error":"Report execution failed",
                    "detail":str(exc)
                },
                500
            )

        return True

    # ==============================================================
    # EXTERNAL GATEWAY LINK
    # ==============================================================

    m=re.fullmatch(
        r"/api/r19/external-gateways/(\d+)/link",
        path
    )

    if m:

        if u["role"] not in ADMIN:
            h._json({"error":"Permission denied"},403)
            return True

        gateway=_tenant(
            conn,
            "external_gateways_r14",
            int(m.group(1)),
            u
        )

        connector=_tenant(
            conn,
            "integration_connectors",
            int(data.get("connector_id") or 0),
            u
        )

        if not gateway or not connector:
            h._json(
                {"error":"Gateway or connector not found"},
                404
            )
            return True

        conn.execute(
            """
            UPDATE external_gateways_r14
            SET connector_id=?,
                status='Ready for Test',
                updated_at=?
            WHERE id=? AND tenant_id=?
            """,
            (
                connector["id"],
                now(),
                gateway["id"],
                u["tenant_id"]
            )
        )

        audit(
            conn,u,
            "LINK",
            "external_gateway",
            gateway["id"],
            f"connector={connector['id']}",
            h.client_address[0]
        )

        conn.commit()

        h._json({"ok":True})
        return True

    # ==============================================================
    # EXTERNAL GATEWAY LIVE TEST
    # ==============================================================

    m=re.fullmatch(
        r"/api/r19/external-gateways/(\d+)/test",
        path
    )

    if m:

        if u["role"] not in ADMIN:
            h._json({"error":"Permission denied"},403)
            return True

        gateway=_tenant(
            conn,
            "external_gateways_r14",
            int(m.group(1)),
            u
        )

        if not gateway:
            h._json({"error":"Gateway not found"},404)
            return True

        connector=_gateway_connector(
            conn,gateway,u
        )

        if not connector:
            h._json(
                {
                    "error":"Configuration Required",
                    "status":"Configuration Required"
                },
                409
            )
            return True

        result=_run_connector(
            conn,u,connector,
            "test",
            {
                "provider":gateway.get("provider"),
                "category":gateway.get("category")
            }
        )

        conn.execute(
            """
            UPDATE external_gateways_r14
            SET status=?,
                last_test_at=?,
                last_error=?,
                last_provider_status=?,
                last_provider_reference=?,
                updated_at=?
            WHERE id=? AND tenant_id=?
            """,
            (
                "Connected"
                if result.get("ok")
                else result.get("status"),
                now(),
                None if result.get("ok")
                    else result.get("detail"),
                result.get("provider_http_status"),
                result.get("provider_id"),
                now(),
                gateway["id"],
                u["tenant_id"]
            )
        )

        audit(
            conn,u,
            "TEST",
            "external_gateway",
            gateway["id"],
            result.get("status") or "",
            h.client_address[0]
        )

        conn.commit()

        code=result.pop("http_status")

        h._json(result,code)
        return True

    # ==============================================================
    # REAL EXTERNAL TRANSACTION EXECUTOR
    # ==============================================================

    m=re.fullmatch(
        r"/api/r19/external/"
        r"(background|esign|everify|payroll|gl|job-board|vms)"
        r"/execute",
        path
    )

    if m:

        category=m.group(1)

        allowed={
            "background":{"admin","teamlead","hr"},
            "esign":{"admin","teamlead","hr"},
            "everify":{"admin","teamlead","hr"},
            "payroll":{"admin","finance"},
            "gl":{"admin","finance"},
            "job-board":{"admin","teamlead","recruiter","sales"},
            "vms":{"admin","teamlead"},
        }[category]

        if u["role"] not in allowed:
            h._json({"error":"Permission denied"},403)
            return True

        connector=_tenant(
            conn,
            "integration_connectors",
            int(data.get("connector_id") or 0),
            u
        )

        if not connector:
            h._json({"error":"Connector not found"},404)
            return True

        action={
            "background":"background_check",
            "esign":"esign",
            "everify":"everify",
            "payroll":"payroll",
            "gl":"gl_export",
            "job-board":"job_board",
            "vms":"vms",
        }[category]

        payload=data.get("payload") or {}

        result=_run_connector(
            conn,u,connector,
            action,
            payload
        )

        cur=conn.execute(
            """
            INSERT INTO external_transactions_r19(
                category,action,entity_type,entity_id,
                connector_id,status,provider_id,
                provider_http_status,detail,
                user_id,created_at,updated_at,tenant_id
            )
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                category,
                action,
                data.get("entity_type"),
                data.get("entity_id"),
                connector["id"],
                result.get("status") or "Unknown",
                result.get("provider_id"),
                result.get("provider_http_status"),
                result.get("detail"),
                u["id"],
                now(),now(),
                u["tenant_id"]
            )
        )

        _domain_record_after_external(
            conn,u,category,data,result
        )

        audit(
            conn,u,
            "EXTERNAL",
            category,
            cur.lastrowid,
            result.get("status") or "",
            h.client_address[0]
        )

        conn.commit()

        code=result.pop("http_status")

        h._json({
            "transaction_id":cur.lastrowid,
            **result
        },code)

        return True

    # ==============================================================
    # INTERVIEW MEETING PROVIDER
    # ==============================================================

    m=re.fullmatch(
        r"/api/r19/interviews/(\d+)/meeting",
        path
    )

    if m:

        if u["role"] not in INTERNAL:
            h._json({"error":"Permission denied"},403)
            return True

        interview=_tenant(
            conn,
            "interviews",
            int(m.group(1)),
            u
        )

        if not interview:
            h._json({"error":"Interview not found"},404)
            return True

        connector=_tenant(
            conn,
            "integration_connectors",
            int(data.get("connector_id") or 0),
            u
        )

        if not connector:
            h._json({"error":"Connector not found"},404)
            return True

        result=_run_connector(
            conn,u,connector,
            "create_meeting",
            {
                "interview_id":interview["id"],
                "scheduled_at":interview.get("scheduled_at"),
                "timezone":interview.get("timezone"),
                "interviewer":interview.get("interviewer"),
                "location_or_link":interview.get("location_or_link")
            }
        )

        if result.get("ok"):

            conn.execute(
                """
                UPDATE interviews
                SET meeting_connector_id=?,
                    meeting_provider_id=?,
                    meeting_status='Created'
                WHERE id=? AND tenant_id=?
                """,
                (
                    connector["id"],
                    result.get("provider_id"),
                    interview["id"],
                    u["tenant_id"]
                )
            )

        audit(
            conn,u,
            "MEETING_PROVIDER",
            "interview",
            interview["id"],
            result.get("status") or "",
            h.client_address[0]
        )

        conn.commit()

        code=result.pop("http_status")

        h._json(result,code)
        return True

    # ==============================================================
    # JOB ALERT EXECUTOR
    # ==============================================================

    m=re.fullmatch(
        r"/api/r19/job-alerts/(\d+)/run",
        path
    )

    if m:

        if u["role"] not in RECRUITING:
            h._json({"error":"Permission denied"},403)
            return True

        alert=_tenant(
            conn,
            "job_alerts_r14",
            int(m.group(1)),
            u
        )

        if not alert:
            h._json({"error":"Alert not found"},404)
            return True

        if not int(alert.get("active") or 0):
            h._json({"error":"Alert is inactive"},409)
            return True

        try:
            criteria=json.loads(
                alert.get("criteria_json") or "{}"
            )
        except Exception:
            criteria={}

        sql=[
            """
            SELECT
                id,job_no,title,city,state,
                work_mode,profession,specialty,
                pay_min,pay_max
            FROM jobs
            WHERE tenant_id=?
              AND status='Open'
              AND archived_at IS NULL
            """
        ]

        params=[u["tenant_id"]]

        for key in (
            "title","city","state",
            "work_mode","profession","specialty"
        ):

            value=criteria.get(key)

            if value:
                sql.append(
                    f" AND lower(COALESCE({key},'')) LIKE ?"
                )
                params.append(
                    "%"+str(value).lower()+"%"
                )

        sql.append(
            " ORDER BY created_at DESC LIMIT 100"
        )

        matches=allrows(
            conn,
            "".join(sql),
            params
        )

        channel=str(alert.get("channel") or "Email")
        delivery="Matched"

        if channel in {"Email","SMS"}:

            cid=(
                data.get("connector_id")
                or alert.get("connector_id")
            )

            if not cid:
                delivery="Credentials Required"
            else:

                connector=_tenant(
                    conn,
                    "integration_connectors",
                    int(cid),
                    u
                )

                candidate=None

                if alert.get("candidate_id"):
                    candidate=_tenant(
                        conn,
                        "candidates",
                        int(alert["candidate_id"]),
                        u
                    )

                if not connector or not candidate:
                    delivery="Configuration Required"
                else:

                    action=(
                        "send_email"
                        if channel=="Email"
                        else "send_sms"
                    )

                    destination=(
                        candidate.get("email")
                        if channel=="Email"
                        else candidate.get("phone")
                    )

                    result=_run_connector(
                        conn,u,connector,
                        action,{
                            "to":destination,
                            "subject":"Job Alert: "
                                +str(alert.get("name") or ""),
                            "body":
                                f"{len(matches)} matching job(s) available.",
                            "job_ids":[x["id"] for x in matches]
                        }
                    )

                    delivery=(
                        "Delivered"
                        if result.get("ok")
                        else result.get("status")
                    )

                    if result.get("ok"):
                        conn.execute(
                            """
                            UPDATE job_alerts_r14
                            SET connector_id=?
                            WHERE id=? AND tenant_id=?
                            """,
                            (
                                connector["id"],
                                alert["id"],
                                u["tenant_id"]
                            )
                        )

        conn.execute(
            """
            UPDATE job_alerts_r14
            SET last_run_at=?,
                updated_at=?
            WHERE id=? AND tenant_id=?
            """,
            (
                now(),now(),
                alert["id"],
                u["tenant_id"]
            )
        )

        cur=conn.execute(
            """
            INSERT INTO job_alert_runs_r19(
                alert_id,match_count,status,
                detail,created_at,user_id,tenant_id
            )
            VALUES(?,?,?,?,?,?,?)
            """,
            (
                alert["id"],
                len(matches),
                delivery,
                json.dumps({
                    "job_ids":[x["id"] for x in matches]
                }),
                now(),
                u["id"],
                u["tenant_id"]
            )
        )

        audit(
            conn,u,
            "RUN",
            "job_alert",
            alert["id"],
            delivery,
            h.client_address[0]
        )

        conn.commit()

        h._json({
            "run_id":cur.lastrowid,
            "status":delivery,
            "match_count":len(matches),
            "matches":matches
        })

        return True

    # ==============================================================
    # WORKFLOW EXECUTOR WITH REAL EXTERNAL STEPS
    # ==============================================================

    m=re.fullmatch(
        r"/api/r19/workflows/(\d+)/run",
        path
    )

    if m:

        if u["role"] not in ADMIN:
            h._json({"error":"Permission denied"},403)
            return True

        workflow=_tenant(
            conn,
            "workflow_definitions_r14",
            int(m.group(1)),
            u
        )

        if not workflow:
            h._json({"error":"Workflow not found"},404)
            return True

        if not int(workflow.get("active") or 0):
            h._json({"error":"Workflow inactive"},409)
            return True

        try:
            definition=json.loads(
                workflow.get("definition_json") or "{}"
            )
        except Exception:
            h._json(
                {"error":"Workflow definition invalid"},
                400
            )
            return True

        steps=definition.get("steps")

        if not isinstance(steps,list):
            h._json(
                {"error":"Workflow steps array required"},
                400
            )
            return True

        started=now()

        run=conn.execute(
            """
            INSERT INTO workflow_runs_r14(
                workflow_id,entity_type,entity_id,status,
                context_json,started_at,tenant_id
            )
            VALUES(?,?,?,?,?,?,?)
            """,
            (
                workflow["id"],
                data.get("entity_type")
                    or workflow.get("entity_type"),
                data.get("entity_id"),
                "Running",
                json.dumps(data.get("context") or {}),
                started,
                u["tenant_id"]
            )
        )

        run_id=run.lastrowid
        outcomes=[]

        external_map={
            "send_email":"send_email",
            "send_sms":"send_sms",
            "esign":"esign",
            "background_check":"background_check",
            "payroll":"payroll",
            "vms":"vms",
            "everify":"everify",
            "job_board":"job_board",
        }

        waiting=False
        error=None

        for index,step in enumerate(steps,start=1):

            if not isinstance(step,dict):
                error=f"step {index} invalid"
                break

            action=str(step.get("action") or "").lower()

            if action in {"audit","log"}:

                message=str(
                    step.get("message") or "workflow step"
                )[:500]

                audit(
                    conn,u,
                    "WORKFLOW_STEP",
                    data.get("entity_type")
                        or workflow.get("entity_type")
                        or "workflow",
                    data.get("entity_id"),
                    message,
                    h.client_address[0]
                )

                outcomes.append({
                    "step":index,
                    "action":action,
                    "ok":True
                })

            elif action=="create_task":

                cur=conn.execute(
                    """
                    INSERT INTO tasks(
                        entity_type,entity_id,title,due_at,
                        owner_user_id,status,priority,
                        created_at,tenant_id
                    )
                    VALUES(?,?,?,?,?,'Open',?,?,?)
                    """,
                    (
                        data.get("entity_type")
                            or workflow.get("entity_type"),
                        data.get("entity_id"),
                        step.get("title")
                            or "Workflow task",
                        step.get("due_at"),
                        step.get("owner_user_id")
                            or u["id"],
                        step.get("priority")
                            or "Normal",
                        now(),
                        u["tenant_id"]
                    )
                )

                outcomes.append({
                    "step":index,
                    "action":"create_task",
                    "id":cur.lastrowid,
                    "ok":True
                })

            elif action in external_map:

                connector_id=(
                    step.get("connector_id")
                    or data.get("connector_id")
                )

                connector=(
                    _tenant(
                        conn,
                        "integration_connectors",
                        int(connector_id),
                        u
                    )
                    if connector_id
                    else None
                )

                if not connector:
                    waiting=True
                    error=(
                        f"step {index}: "
                        "external connector configuration required"
                    )
                    outcomes.append({
                        "step":index,
                        "action":action,
                        "ok":False,
                        "status":"Configuration Required"
                    })
                    break

                result=_run_connector(
                    conn,u,connector,
                    external_map[action],
                    step.get("payload")
                    or data.get("context")
                    or {}
                )

                outcomes.append({
                    "step":index,
                    "action":action,
                    "ok":bool(result.get("ok")),
                    "status":result.get("status"),
                    "provider_id":result.get("provider_id")
                })

                if not result.get("ok"):
                    waiting=True
                    error=result.get("detail")
                    break

            else:
                error=f"unsupported workflow action: {action}"
                break

        if error and not waiting:
            final="Failed"
            code=400
        elif waiting:
            final="Waiting External"
            code=409
        else:
            final="Completed"
            code=201

        conn.execute(
            """
            UPDATE workflow_runs_r14
            SET status=?,
                context_json=?,
                finished_at=?,
                error=?
            WHERE id=? AND tenant_id=?
            """,
            (
                final,
                json.dumps({
                    "input":data.get("context") or {},
                    "outcomes":outcomes
                }),
                now(),
                error,
                run_id,
                u["tenant_id"]
            )
        )

        audit(
            conn,u,
            "RUN",
            "workflow",
            workflow["id"],
            final,
            h.client_address[0]
        )

        conn.commit()

        h._json({
            "run_id":run_id,
            "status":final,
            "outcomes":outcomes,
            "error":error
        },code)

        return True

    return False
