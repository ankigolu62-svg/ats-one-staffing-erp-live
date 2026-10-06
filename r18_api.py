from __future__ import annotations

import base64
import json
import os
import re
import secrets
import sqlite3
import urllib.error
import urllib.parse
import urllib.request

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


FINANCE_ROLES={"admin","finance","teamlead"}
WORKFORCE_ROLES={"admin","teamlead","hr","finance"}
INTERNAL_ROLES={"admin","teamlead","recruiter","sales","hr","finance"}


def now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def today():
    return datetime.now(timezone.utc).date().isoformat()


def one(conn,sql,args=()):
    r=conn.execute(sql,args).fetchone()
    return dict(r) if r else None


def allrows(conn,sql,args=()):
    return [dict(r) for r in conn.execute(sql,args).fetchall()]


def cols(conn,table):
    return {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}


def addcol(conn,table,name,decl):
    if name not in cols(conn,table):
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {decl}")


def money(value):
    try:
        return Decimal(str(value or "0")).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP
        )
    except InvalidOperation:
        raise ValueError("Invalid monetary value")


def audit(conn,u,action,entity,entity_id=None,detail="",ip=""):
    conn.execute(
        """
        INSERT INTO audit_log(
            user_id,action,entity_type,entity_id,
            detail,ip,created_at,tenant_id
        )
        VALUES(?,?,?,?,?,?,?,?)
        """,
        (
            u["id"],action,entity,entity_id,
            detail,ip,now(),u["tenant_id"]
        )
    )


def ensure_r18_schema(conn):

    # --------------------------------------------------------------
    # ATTENDANCE
    # --------------------------------------------------------------

    addcol(conn,"attendance","assignment_id","INTEGER")
    addcol(conn,"attendance","attendance_date","TEXT")
    addcol(conn,"attendance","scheduled_hours","REAL DEFAULT 0")
    addcol(conn,"attendance","worked_hours","REAL DEFAULT 0")
    addcol(conn,"attendance","late_minutes","INTEGER DEFAULT 0")
    addcol(conn,"attendance","absence_reason","TEXT")
    addcol(conn,"attendance","approval_state","TEXT DEFAULT 'Pending'")
    addcol(conn,"attendance","approved_by","INTEGER")
    addcol(conn,"attendance","approved_at","TEXT")
    addcol(conn,"attendance","created_at","TEXT")
    addcol(conn,"attendance","updated_at","TEXT")

    conn.execute(
        """
        UPDATE attendance
        SET assignment_id=(
              SELECT assignment_id
              FROM shifts
              WHERE shifts.id=attendance.shift_id
            )
        WHERE assignment_id IS NULL
          AND shift_id IS NOT NULL
        """
    )

    conn.execute(
        """
        UPDATE attendance
        SET attendance_date=(
              SELECT shift_date
              FROM shifts
              WHERE shifts.id=attendance.shift_id
            )
        WHERE attendance_date IS NULL
          AND shift_id IS NOT NULL
        """
    )

    conn.execute(
        """
        UPDATE attendance
        SET created_at=COALESCE(created_at,?),
            updated_at=COALESCE(updated_at,?)
        """,
        (now(),now())
    )

    # --------------------------------------------------------------
    # FINANCE
    # --------------------------------------------------------------

    addcol(conn,"invoices","paid_amount","REAL DEFAULT 0")
    addcol(conn,"invoices","discount","REAL DEFAULT 0")
    addcol(conn,"invoices","po_id","INTEGER")
    addcol(conn,"invoices","notes","TEXT")
    addcol(conn,"invoices","currency","TEXT DEFAULT 'USD'")
    addcol(conn,"invoices","updated_at","TEXT")
    addcol(conn,"invoices","void_reason","TEXT")

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS invoice_lines(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_id INTEGER NOT NULL,
            line_type TEXT DEFAULT 'Service',
            description TEXT,
            quantity REAL DEFAULT 1,
            rate REAL DEFAULT 0,
            amount REAL DEFAULT 0,
            tax REAL DEFAULT 0,
            source_type TEXT,
            source_id INTEGER,
            created_at TEXT NOT NULL,
            tenant_id INTEGER NOT NULL DEFAULT 1
        )
        """
    )

    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_invoice_lines_invoice_tenant
        ON invoice_lines(invoice_id,tenant_id)
        """
    )

    # --------------------------------------------------------------
    # CONNECTORS
    # --------------------------------------------------------------

    addcol(conn,"integration_connectors","last_error","TEXT")
    addcol(conn,"integration_connectors","last_test_at","TEXT")
    addcol(conn,"integration_connectors","connected_at","TEXT")

    addcol(conn,"vms_accounts","connector_id","INTEGER")

    # Historical Demo labels must not pretend to be production.
    conn.execute(
        """
        UPDATE integration_connectors
        SET mode='External',
            status='Credentials Required',
            last_sync=NULL
        WHERE lower(COALESCE(mode,''))='demo'
        """
    )

    conn.execute(
        """
        UPDATE vms_accounts
        SET sync_mode='Credentials Required',
            last_sync=NULL,
            notes=CASE
                WHEN lower(COALESCE(notes,'')) LIKE '%demo connector%'
                THEN 'External VMS connector requires authorized provider configuration and credentials.'
                ELSE notes
            END
        WHERE lower(COALESCE(sync_mode,''))='demo'
        """
    )

    # Native career portal is internal, not a fake external integration.
    conn.execute(
        """
        UPDATE integration_connectors
        SET mode='Internal',
            status='Connected',
            last_error=NULL
        WHERE lower(category)='job boards'
          AND lower(name)='career site'
        """
    )


def _tenant(conn,table,row_id,u):
    return one(
        conn,
        f"SELECT * FROM {table} WHERE id=? AND tenant_id=?",
        (row_id,u["tenant_id"])
    )


def _json_config(row):
    try:
        v=json.loads(row.get("config_json") or "{}")
        return v if isinstance(v,dict) else {}
    except Exception:
        return {}


def _connector_state(row):
    cfg=_json_config(row)

    if str(row.get("mode") or "").lower()=="internal":
        return "Connected"

    base=str(cfg.get("base_url") or "").strip()

    if not base:
        return "Configuration Required"

    auth=cfg.get("auth") or {}
    auth_type=str(auth.get("type") or "bearer").lower()

    if auth_type!="none":
        ref=str(row.get("credential_ref") or "").strip()
        if not ref or not os.environ.get(ref):
            return "Credentials Required"

    if str(row.get("status") or "").lower()=="connected":
        return "Connected"

    return "Ready for Test"


def _redact(text,secrets_to_hide):
    out=str(text or "")
    for secret in secrets_to_hide:
        if secret:
            out=out.replace(secret,"[REDACTED]")
    return out[:4000]


def _build_connector_request(connector,action,payload=None):

    cfg=_json_config(connector)
    base=str(cfg.get("base_url") or "").rstrip("/")

    if not base:
        raise ValueError("Configuration Required: base_url is missing")

    parsed=urllib.parse.urlparse(base)

    if parsed.scheme not in ("https","http"):
        raise ValueError("Configuration Required: base_url must be HTTP(S)")

    if parsed.scheme=="http" and parsed.hostname not in (
        "127.0.0.1","localhost","::1"
    ):
        raise ValueError("Production external connectors require HTTPS")

    paths=cfg.get("paths") or {}
    action_cfg=paths.get(action)

    if isinstance(action_cfg,str):
        action_cfg={"path":action_cfg}

    if not isinstance(action_cfg,dict):
        if action=="test":
            action_cfg={"path":"/","method":"GET"}
        else:
            raise ValueError(
                f"Configuration Required: no path configured for {action}"
            )

    path=str(action_cfg.get("path") or "/")
    method=str(action_cfg.get("method") or (
        "GET" if action=="test" else "POST"
    )).upper()

    url=base+"/"+path.lstrip("/")

    headers={
        "Accept":"application/json",
        "User-Agent":"ATS-One-R18/1.0",
        "X-ATS-Correlation-ID":secrets.token_hex(12)
    }

    custom=cfg.get("headers") or {}

    if isinstance(custom,dict):
        for k,v in custom.items():
            if not re.match(r"^[A-Za-z0-9-]+$",str(k)):
                continue
            headers[str(k)]=str(v)

    auth=cfg.get("auth") or {}
    auth_type=str(auth.get("type") or "bearer").lower()

    secret=None
    ref=str(connector.get("credential_ref") or "").strip()

    if auth_type!="none":
        if not ref:
            raise PermissionError("Credentials Required")

        secret=os.environ.get(ref)

        if not secret:
            raise PermissionError("Credentials Required")

        if auth_type=="bearer":
            headers["Authorization"]="Bearer "+secret

        elif auth_type=="header":
            header_name=str(auth.get("header_name") or "X-API-Key")
            headers[header_name]=secret

        elif auth_type=="basic":
            token=base64.b64encode(secret.encode()).decode()
            headers["Authorization"]="Basic "+token

        else:
            raise ValueError("Unsupported connector auth type")

    body=None

    if method not in ("GET","HEAD"):
        body=json.dumps(
            payload or {},
            separators=(",",":")
        ).encode()
        headers["Content-Type"]="application/json"

    timeout=float(cfg.get("timeout_seconds") or 20)

    timeout=min(max(timeout,1),60)

    return (
        urllib.request.Request(
            url,
            data=body,
            headers=headers,
            method=method
        ),
        timeout,
        secret
    )


def _run_connector(conn,u,connector,action,payload=None):

    state=_connector_state(connector)

    if state=="Configuration Required":
        return {
            "ok":False,
            "http_status":409,
            "status":"Configuration Required",
            "detail":"External endpoint configuration is incomplete."
        }

    if state=="Credentials Required":
        return {
            "ok":False,
            "http_status":409,
            "status":"Credentials Required",
            "detail":"Authorized provider credentials are required."
        }

    try:
        req,timeout,secret=_build_connector_request(
            connector,
            action,
            payload
        )

        started=now()

        try:
            with urllib.request.urlopen(req,timeout=timeout) as r:
                code=int(r.status)
                raw=r.read(1024*256)
                text=raw.decode("utf-8","replace")

        except urllib.error.HTTPError as e:
            code=int(e.code)
            raw=e.read(1024*256)
            text=raw.decode("utf-8","replace")

        safe=_redact(text,[secret])

        ok=200 <= code < 300

        status="Success" if ok else "Provider Error"

        detail=f"HTTP {code}"

        if safe:
            detail += " :: "+safe[:1200]

        conn.execute(
            """
            INSERT INTO integration_logs(
                connector_id,action,status,detail,
                user_id,created_at,tenant_id
            )
            VALUES(?,?,?,?,?,?,?)
            """,
            (
                connector["id"],action,status,detail,
                u["id"],started,u["tenant_id"]
            )
        )

        if ok:
            if action=="test":
                conn.execute(
                    """
                    UPDATE integration_connectors
                    SET status='Connected',
                        last_test_at=?,
                        connected_at=COALESCE(connected_at,?),
                        last_error=NULL
                    WHERE id=? AND tenant_id=?
                    """,
                    (now(),now(),connector["id"],u["tenant_id"])
                )
            else:
                conn.execute(
                    """
                    UPDATE integration_connectors
                    SET status='Connected',
                        last_sync=?,
                        last_error=NULL
                    WHERE id=? AND tenant_id=?
                    """,
                    (now(),connector["id"],u["tenant_id"])
                )
        else:
            conn.execute(
                """
                UPDATE integration_connectors
                SET last_error=?,
                    last_test_at=CASE
                        WHEN ?='test' THEN ?
                        ELSE last_test_at
                    END
                WHERE id=? AND tenant_id=?
                """,
                (
                    f"HTTP {code}",
                    action,
                    now(),
                    connector["id"],
                    u["tenant_id"]
                )
            )

        provider_id=None

        try:
            parsed=json.loads(text)
            if isinstance(parsed,dict):
                provider_id=(
                    parsed.get("id")
                    or parsed.get("message_id")
                    or parsed.get("reference_id")
                    or parsed.get("request_id")
                )
        except Exception:
            pass

        return {
            "ok":ok,
            "http_status":200 if ok else 502,
            "status":status,
            "provider_http_status":code,
            "provider_id":provider_id,
            "detail":detail
        }

    except PermissionError as e:

        conn.execute(
            """
            INSERT INTO integration_logs(
                connector_id,action,status,detail,
                user_id,created_at,tenant_id
            )
            VALUES(?,?,?,?,?,?,?)
            """,
            (
                connector["id"],action,
                "Credentials Required",
                str(e),u["id"],now(),u["tenant_id"]
            )
        )

        return {
            "ok":False,
            "http_status":409,
            "status":"Credentials Required",
            "detail":str(e)
        }

    except Exception as e:

        safe=_redact(str(e),[])

        conn.execute(
            """
            INSERT INTO integration_logs(
                connector_id,action,status,detail,
                user_id,created_at,tenant_id
            )
            VALUES(?,?,?,?,?,?,?)
            """,
            (
                connector["id"],action,
                "Failed",safe,u["id"],now(),u["tenant_id"]
            )
        )

        conn.execute(
            """
            UPDATE integration_connectors
            SET last_error=?
            WHERE id=? AND tenant_id=?
            """,
            (safe[:1000],connector["id"],u["tenant_id"])
        )

        return {
            "ok":False,
            "http_status":502,
            "status":"Failed",
            "detail":safe
        }


def _find_connector_for_vms(conn,account,u):

    if account.get("connector_id"):
        c=_tenant(
            conn,
            "integration_connectors",
            int(account["connector_id"]),
            u
        )
        if c:
            return c

    platform=str(account.get("platform") or "").lower()

    rows=allrows(
        conn,
        """
        SELECT *
        FROM integration_connectors
        WHERE tenant_id=?
          AND lower(category)='vms'
        ORDER BY id
        """,
        (u["tenant_id"],)
    )

    for c in rows:
        if platform and platform in str(c.get("name") or "").lower():
            return c

    return rows[0] if rows else None


def r18_get(h,conn,u,path,qs):

    # --------------------------------------------------------------
    # ATTENDANCE
    # --------------------------------------------------------------

    if path=="/api/attendance":

        if u["role"] not in INTERNAL_ROLES|{"worker"}:
            h._json({"error":"Permission denied"},403)
            return True

        sql="""
        SELECT
            at.*,
            a.job_id,
            a.company_id,
            j.title job_title,
            co.name company_name,
            c.first_name,
            c.last_name,
            sh.shift_date,
            sh.start_time,
            sh.end_time
        FROM attendance at
        LEFT JOIN assignments a
               ON a.id=at.assignment_id
              AND a.tenant_id=at.tenant_id
        LEFT JOIN shifts sh
               ON sh.id=at.shift_id
              AND sh.tenant_id=at.tenant_id
        JOIN candidates c
             ON c.id=at.candidate_id
        LEFT JOIN jobs j
               ON j.id=a.job_id
        LEFT JOIN companies co
               ON co.id=a.company_id
        WHERE at.tenant_id=?
        """

        args=[u["tenant_id"]]

        if u["role"]=="worker":
            sql+=" AND at.candidate_id=?"
            args.append(u.get("candidate_id"))

        sql+=" ORDER BY COALESCE(at.attendance_date,sh.shift_date) DESC,at.id DESC"

        h._json(allrows(conn,sql,args))
        return True

    m=re.fullmatch(r"/api/attendance/(\d+)",path)

    if m:

        row=_tenant(conn,"attendance",int(m.group(1)),u)

        if not row:
            h._json({"error":"Not found"},404)
            return True

        if u["role"]=="worker" and row["candidate_id"]!=u.get("candidate_id"):
            h._json({"error":"Permission denied"},403)
            return True

        if u["role"] not in INTERNAL_ROLES|{"worker"}:
            h._json({"error":"Permission denied"},403)
            return True

        h._json(row)
        return True

    # --------------------------------------------------------------
    # FINANCE
    # --------------------------------------------------------------

    # R18_INVOICE_LIST_TRUTH
    if path=="/api/invoices":

        if u["role"] not in FINANCE_ROLES:
            h._json({"error":"Permission denied"},403)
            return True

        rows=allrows(
            conn,
            """
            SELECT
                i.*,
                (
                    COALESCE(i.amount,0)
                    +COALESCE(i.tax,0)
                    -COALESCE(i.discount,0)
                    -COALESCE(i.paid_amount,0)
                ) balance,
                CASE
                    WHEN i.due_date IS NOT NULL
                     AND i.status IN ('issued','part_paid')
                    THEN MAX(
                        0,
                        CAST(
                            julianday('now')-julianday(i.due_date)
                            AS INTEGER
                        )
                    )
                    ELSE 0
                END aging_days,
                co.name company_name,
                c.first_name,
                c.last_name,
                j.title job_title
            FROM invoices i
            LEFT JOIN companies co
                   ON co.id=i.company_id
            LEFT JOIN assignments a
                   ON a.id=i.assignment_id
            LEFT JOIN candidates c
                   ON c.id=a.candidate_id
            LEFT JOIN jobs j
                   ON j.id=a.job_id
            WHERE i.tenant_id=?
            ORDER BY i.created_at DESC
            """,
            (u["tenant_id"],)
        )

        for row in rows:
            row["total"]=float(
                money(row.get("amount"))
                +money(row.get("tax"))
                -money(row.get("discount"))
            )
            row["balance"]=float(
                max(
                    Decimal("0"),
                    money(row.get("amount"))
                    +money(row.get("tax"))
                    -money(row.get("discount"))
                    -money(row.get("paid_amount"))
                )
            )

        h._json(rows)
        return True


    m=re.fullmatch(r"/api/invoices/(\d+)",path)

    if m:

        if u["role"] not in FINANCE_ROLES:
            h._json({"error":"Permission denied"},403)
            return True

        inv=_tenant(conn,"invoices",int(m.group(1)),u)

        if not inv:
            h._json({"error":"Not found"},404)
            return True

        inv["lines"]=allrows(
            conn,
            """
            SELECT *
            FROM invoice_lines
            WHERE invoice_id=? AND tenant_id=?
            ORDER BY id
            """,
            (inv["id"],u["tenant_id"])
        )

        inv["payments"]=allrows(
            conn,
            """
            SELECT *
            FROM invoice_payments
            WHERE invoice_id=? AND tenant_id=?
            ORDER BY payment_date,id
            """,
            (inv["id"],u["tenant_id"])
        )

        inv["history"]=allrows(
            conn,
            """
            SELECT *
            FROM workflow_history
            WHERE entity_type='invoice'
              AND entity_id=?
              AND tenant_id=?
            ORDER BY id
            """,
            (inv["id"],u["tenant_id"])
        )

        total=(
            money(inv.get("amount"))
            +money(inv.get("tax"))
            -money(inv.get("discount"))
        )

        paid=money(inv.get("paid_amount"))

        inv["total"]=float(total)
        inv["balance"]=float(max(Decimal("0"),total-paid))

        h._json(inv)
        return True

    # --------------------------------------------------------------
    # CONNECTOR TRUTH
    # --------------------------------------------------------------

    if path=="/api/integrations":

        if u["role"] not in {"admin","teamlead"}:
            h._json({"error":"Permission denied"},403)
            return True

        rows=allrows(
            conn,
            """
            SELECT *
            FROM integration_connectors
            WHERE tenant_id=?
            ORDER BY category,name
            """,
            (u["tenant_id"],)
        )

        for row in rows:
            row["connection_state"]=_connector_state(row)

            ref=str(row.get("credential_ref") or "")

            row["credential_present"]=bool(
                ref and os.environ.get(ref)
            )

        h._json(rows)
        return True

    if path=="/api/vms":

        if u["role"] not in {"admin","teamlead","sales"}:
            h._json({"error":"Permission denied"},403)
            return True

        accounts=allrows(
            conn,
            """
            SELECT *
            FROM vms_accounts
            WHERE tenant_id=?
            ORDER BY id
            """,
            (u["tenant_id"],)
        )

        for account in accounts:

            connector=_find_connector_for_vms(
                conn,
                account,
                u
            )

            account["connection_state"]=(
                _connector_state(connector)
                if connector
                else "Configuration Required"
            )

            account["connector_id"]=(
                connector["id"]
                if connector
                else None
            )

        mappings=allrows(
            conn,
            """
            SELECT vm.*,va.name account_name
            FROM vms_mappings vm
            LEFT JOIN vms_accounts va
                   ON va.id=vm.vms_account_id
            WHERE vm.tenant_id=?
            ORDER BY vm.updated_at DESC
            """,
            (u["tenant_id"],)
        )

        history=allrows(
            conn,
            """
            SELECT *
            FROM vms_sync_history
            WHERE tenant_id=?
            ORDER BY id DESC
            LIMIT 100
            """,
            (u["tenant_id"],)
        )

        h._json({
            "accounts":accounts,
            "mappings":mappings,
            "history":history
        })

        return True

    return False


def r18_post(h,conn,u,path,data):

    # --------------------------------------------------------------
    # ATTENDANCE CREATE
    # --------------------------------------------------------------

    if path=="/api/attendance":

        if u["role"] not in WORKFORCE_ROLES|{"worker"}:
            h._json({"error":"Permission denied"},403)
            return True

        aid=int(data.get("assignment_id") or 0)

        assignment=_tenant(conn,"assignments",aid,u)

        if not assignment:
            h._json({"error":"Assignment not found"},404)
            return True

        cid=int(
            data.get("candidate_id")
            or assignment["candidate_id"]
        )

        if cid != assignment["candidate_id"]:
            h._json(
                {"error":"Candidate does not belong to assignment"},
                409
            )
            return True

        if u["role"]=="worker" and cid!=u.get("candidate_id"):
            h._json({"error":"Permission denied"},403)
            return True

        shift_id=data.get("shift_id")

        if shift_id:

            shift=_tenant(conn,"shifts",int(shift_id),u)

            if (
                not shift
                or int(shift.get("assignment_id") or 0)!=aid
            ):
                h._json(
                    {"error":"Shift does not belong to assignment"},
                    409
                )
                return True

        worked=float(data.get("worked_hours") or 0)
        scheduled=float(data.get("scheduled_hours") or 0)

        if worked < 0 or worked > 24:
            h._json({"error":"worked_hours must be 0-24"},400)
            return True

        if scheduled < 0 or scheduled > 24:
            h._json({"error":"scheduled_hours must be 0-24"},400)
            return True

        approval=(
            "Pending"
            if u["role"]=="worker"
            else str(data.get("approval_state") or "Pending")
        )

        ts=now()

        cur=conn.execute(
            """
            INSERT INTO attendance(
                shift_id,assignment_id,candidate_id,
                attendance_date,check_in,check_out,
                status,note,scheduled_hours,worked_hours,
                late_minutes,absence_reason,
                approval_state,created_at,updated_at,
                tenant_id
            )
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                shift_id,
                aid,
                cid,
                data.get("attendance_date") or today(),
                data.get("check_in"),
                data.get("check_out"),
                data.get("status") or "Present",
                data.get("note"),
                scheduled,
                worked,
                int(data.get("late_minutes") or 0),
                data.get("absence_reason"),
                approval,
                ts,ts,
                u["tenant_id"]
            )
        )

        audit(
            conn,u,"CREATE","attendance",
            cur.lastrowid,
            f"assignment={aid}",
            h.client_address[0]
        )

        conn.commit()

        h._json(
            {"id":cur.lastrowid,"ok":True},
            201
        )

        return True

    # --------------------------------------------------------------
    # INVOICE CREATE
    # --------------------------------------------------------------

    if path=="/api/invoices":

        if u["role"] not in FINANCE_ROLES:
            h._json({"error":"Permission denied"},403)
            return True

        company_id=int(data.get("company_id") or 0)

        company=_tenant(conn,"companies",company_id,u)

        if not company:
            h._json({"error":"Company not found"},404)
            return True

        assignment_id=data.get("assignment_id")

        if assignment_id:
            assignment=_tenant(
                conn,
                "assignments",
                int(assignment_id),
                u
            )
            if not assignment:
                h._json({"error":"Assignment not found"},404)
                return True

        po_id=data.get("po_id")

        if po_id and not _tenant(
            conn,
            "purchase_orders",
            int(po_id),
            u
        ):
            h._json({"error":"PO not found"},404)
            return True

        lines=data.get("lines") or []

        if lines:
            subtotal=Decimal("0")

            for line in lines:
                qty=Decimal(str(line.get("quantity") or 1))
                price=money(line.get("unit_price"))
                subtotal += (qty*price)

            amount=subtotal.quantize(Decimal("0.01"))
        else:
            amount=money(data.get("amount"))

        tax=money(data.get("tax"))
        discount=money(data.get("discount"))

        if amount < 0 or tax < 0 or discount < 0:
            h._json(
                {"error":"Invoice monetary values cannot be negative"},
                400
            )
            return True

        invoice_no=(
            str(data.get("invoice_no") or "").strip()
            or "INV-"
            +datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
            +"-"
            +secrets.token_hex(2).upper()
        )

        target=str(data.get("status") or "draft").lower()

        if target not in {"draft","issued"}:
            h._json(
                {"error":"New invoice status must be draft or issued"},
                400
            )
            return True

        ts=now()

        cur=conn.execute(
            """
            INSERT INTO invoices(
                invoice_no,company_id,assignment_id,
                period_start,period_end,amount,tax,
                discount,paid_amount,status,due_date,
                issued_at,paid_at,po_id,notes,currency,
                created_at,updated_at,tenant_id
            )
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                invoice_no,
                company_id,
                assignment_id,
                data.get("period_start"),
                data.get("period_end"),
                float(amount),
                float(tax),
                float(discount),
                0,
                target,
                data.get("due_date"),
                ts if target=="issued" else None,
                None,
                po_id,
                data.get("notes"),
                data.get("currency") or "USD",
                ts,ts,
                u["tenant_id"]
            )
        )

        iid=cur.lastrowid

        for line in lines:

            qty=Decimal(str(line.get("quantity") or 1))
            price=money(line.get("unit_price"))
            total=(qty*price).quantize(Decimal("0.01"))

            conn.execute(
                """
                INSERT INTO invoice_lines(
                    invoice_id,description,quantity,
                    rate,amount,line_type,
                    created_at,tenant_id
                )
                VALUES(?,?,?,?,?,?,?,?)
                """,
                (
                    iid,
                    str(line.get("description") or "Service"),
                    float(qty),
                    float(price),
                    float(total),
                    line.get("line_type") or "Service",
                    ts,u["tenant_id"]
                )
            )

        audit(
            conn,u,"CREATE","invoice",
            iid,invoice_no,h.client_address[0]
        )

        conn.commit()

        h._json(
            {
                "id":iid,
                "invoice_no":invoice_no,
                "status":target
            },
            201
        )

        return True

    # --------------------------------------------------------------
    # ADD INVOICE LINE
    # --------------------------------------------------------------

    m=re.fullmatch(r"/api/invoices/(\d+)/lines",path)

    if m:

        if u["role"] not in FINANCE_ROLES:
            h._json({"error":"Permission denied"},403)
            return True

        inv=_tenant(conn,"invoices",int(m.group(1)),u)

        if not inv:
            h._json({"error":"Not found"},404)
            return True

        if str(inv["status"]).lower()!="draft":
            h._json(
                {"error":"Only draft invoices can be edited"},
                409
            )
            return True

        qty=Decimal(str(data.get("quantity") or 1))
        price=money(data.get("unit_price"))
        total=(qty*price).quantize(Decimal("0.01"))

        ts=now()

        cur=conn.execute(
            """
            INSERT INTO invoice_lines(
                invoice_id,description,quantity,
                rate,amount,line_type,
                created_at,tenant_id
            )
            VALUES(?,?,?,?,?,?,?,?)
            """,
            (
                inv["id"],
                data.get("description") or "Service",
                float(qty),
                float(price),
                float(total),
                data.get("line_type") or "Service",
                ts,u["tenant_id"]
            )
        )

        new_total=one(
            conn,
            """
            SELECT COALESCE(SUM(amount),0) total
            FROM invoice_lines
            WHERE invoice_id=? AND tenant_id=?
            """,
            (inv["id"],u["tenant_id"])
        )["total"]

        conn.execute(
            """
            UPDATE invoices
            SET amount=?,updated_at=?
            WHERE id=? AND tenant_id=?
            """,
            (new_total,ts,inv["id"],u["tenant_id"])
        )

        audit(
            conn,u,"ADD_LINE","invoice",
            inv["id"],
            str(cur.lastrowid),
            h.client_address[0]
        )

        conn.commit()

        h._json({"id":cur.lastrowid},201)
        return True

    # --------------------------------------------------------------
    # ISSUE / VOID INVOICE
    # --------------------------------------------------------------

    m=re.fullmatch(r"/api/invoices/(\d+)/(issue|void)",path)

    if m:

        if u["role"] not in FINANCE_ROLES:
            h._json({"error":"Permission denied"},403)
            return True

        iid=int(m.group(1))
        action=m.group(2)

        inv=_tenant(conn,"invoices",iid,u)

        if not inv:
            h._json({"error":"Not found"},404)
            return True

        current=str(inv["status"]).lower()
        ts=now()

        if action=="issue":

            if current!="draft":
                h._json(
                    {"error":"Only draft invoices can be issued"},
                    409
                )
                return True

            target="issued"

            conn.execute(
                """
                UPDATE invoices
                SET status='issued',
                    issued_at=?,
                    updated_at=?
                WHERE id=? AND tenant_id=?
                """,
                (ts,ts,iid,u["tenant_id"])
            )

        else:

            if current in {"paid","void"}:
                h._json(
                    {"error":"Paid or already void invoices cannot be voided"},
                    409
                )
                return True

            if money(inv.get("paid_amount")) > 0:
                h._json(
                    {"error":"Invoice with payments cannot be voided"},
                    409
                )
                return True

            target="void"

            conn.execute(
                """
                UPDATE invoices
                SET status='void',
                    void_reason=?,
                    updated_at=?
                WHERE id=? AND tenant_id=?
                """,
                (
                    data.get("reason") or "Voided",
                    ts,iid,u["tenant_id"]
                )
            )

        conn.execute(
            """
            INSERT INTO workflow_history(
                entity_type,entity_id,from_status,to_status,
                note,user_id,created_at,tenant_id
            )
            VALUES('invoice',?,?,?,?,?,?,?)
            """,
            (
                iid,current,target,
                data.get("reason") or "",
                u["id"],ts,u["tenant_id"]
            )
        )

        audit(
            conn,u,action.upper(),"invoice",
            iid,target,h.client_address[0]
        )

        conn.commit()

        h._json({"ok":True,"status":target})
        return True

    # --------------------------------------------------------------
    # PAYMENT WITH DECIMAL CHECKING
    # --------------------------------------------------------------

    m=re.fullmatch(r"/api/invoices/(\d+)/payments",path)

    if m:

        if u["role"] not in {"admin","finance"}:
            h._json({"error":"Permission denied"},403)
            return True

        iid=int(m.group(1))
        inv=_tenant(conn,"invoices",iid,u)

        if not inv:
            h._json({"error":"Not found"},404)
            return True

        current=str(inv["status"]).lower()

        if current not in {"issued","part_paid"}:
            h._json(
                {"error":"Only issued invoices can receive payment"},
                409
            )
            return True

        total=(
            money(inv.get("amount"))
            +money(inv.get("tax"))
            -money(inv.get("discount"))
        )

        paid=money(inv.get("paid_amount"))
        balance=total-paid
        payment=money(data.get("amount"))

        if payment <= 0 or payment > balance:
            h._json(
                {"error":"Payment must be positive and not exceed balance"},
                400
            )
            return True

        new_paid=paid+payment
        target="paid" if new_paid==total else "part_paid"
        ts=now()

        cur=conn.execute(
            """
            INSERT INTO invoice_payments(
                invoice_id,amount,reference,payment_date,
                user_id,created_at,tenant_id
            )
            VALUES(?,?,?,?,?,?,?)
            """,
            (
                iid,float(payment),
                data.get("reference"),
                data.get("payment_date") or today(),
                u["id"],ts,u["tenant_id"]
            )
        )

        conn.execute(
            """
            UPDATE invoices
            SET paid_amount=?,
                status=?,
                paid_at=?,
                updated_at=?
            WHERE id=? AND tenant_id=?
            """,
            (
                float(new_paid),
                target,
                ts if target=="paid" else None,
                ts,
                iid,u["tenant_id"]
            )
        )

        conn.execute(
            """
            INSERT INTO workflow_history(
                entity_type,entity_id,from_status,to_status,
                note,user_id,created_at,tenant_id
            )
            VALUES('invoice',?,?,?,?,?,?,?)
            """,
            (
                iid,current,target,
                data.get("reference") or "",
                u["id"],ts,u["tenant_id"]
            )
        )

        audit(
            conn,u,"PAYMENT","invoice",
            iid,str(payment),h.client_address[0]
        )

        conn.commit()

        h._json(
            {
                "id":cur.lastrowid,
                "status":target,
                "paid_amount":float(new_paid),
                "balance":float(total-new_paid)
            },
            201
        )

        return True

    # --------------------------------------------------------------
    # REAL GENERIC CONNECTOR TEST/SYNC
    # --------------------------------------------------------------

    m=re.fullmatch(r"/api/integrations/(\d+)/(test|sync)",path)

    if m:

        if u["role"]!="admin":
            h._json({"error":"Permission denied"},403)
            return True

        connector=_tenant(
            conn,
            "integration_connectors",
            int(m.group(1)),
            u
        )

        if not connector:
            h._json({"error":"Not found"},404)
            return True

        result=_run_connector(
            conn,u,connector,m.group(2),
            data.get("payload") or {
                "source":"ATS-One",
                "action":m.group(2)
            }
        )

        audit(
            conn,u,
            m.group(2).upper(),
            "integration",
            connector["id"],
            result["status"],
            h.client_address[0]
        )

        conn.commit()

        h._json(
            result,
            result.pop("http_status")
        )

        return True

    # --------------------------------------------------------------
    # REAL VMS SYNC GATE
    # --------------------------------------------------------------

    m=re.fullmatch(r"/api/vms/accounts/(\d+)/(sync|retry)",path)

    if m:

        if u["role"] not in {"admin","teamlead"}:
            h._json({"error":"Permission denied"},403)
            return True

        account=_tenant(
            conn,
            "vms_accounts",
            int(m.group(1)),
            u
        )

        if not account:
            h._json({"error":"Not found"},404)
            return True

        connector=_find_connector_for_vms(
            conn,account,u
        )

        if not connector:

            status="Configuration Required"
            detail="No VMS connector is configured for this account."

            cur=conn.execute(
                """
                INSERT INTO vms_sync_history(
                    vms_account_id,status,detail,retry_of,
                    user_id,created_at,tenant_id
                )
                VALUES(?,?,?,?,?,?,?)
                """,
                (
                    account["id"],status,detail,
                    data.get("retry_of"),
                    u["id"],now(),u["tenant_id"]
                )
            )

            conn.commit()

            h._json(
                {
                    "run_id":cur.lastrowid,
                    "status":status,
                    "detail":detail
                },
                409
            )

            return True

        payload={
            "vms_account":{
                "id":account["id"],
                "name":account.get("name"),
                "platform":account.get("platform")
            },
            "requested_action":m.group(2)
        }

        result=_run_connector(
            conn,u,connector,"sync",payload
        )

        hist_status=(
            "Success"
            if result["ok"]
            else result["status"]
        )

        cur=conn.execute(
            """
            INSERT INTO vms_sync_history(
                vms_account_id,status,detail,retry_of,
                user_id,created_at,tenant_id
            )
            VALUES(?,?,?,?,?,?,?)
            """,
            (
                account["id"],
                hist_status,
                result.get("detail"),
                data.get("retry_of"),
                u["id"],now(),u["tenant_id"]
            )
        )

        if result["ok"]:
            conn.execute(
                """
                UPDATE vms_accounts
                SET last_sync=?,
                    last_error=NULL,
                    sync_mode='Live'
                WHERE id=? AND tenant_id=?
                """,
                (now(),account["id"],u["tenant_id"])
            )
        else:
            conn.execute(
                """
                UPDATE vms_accounts
                SET last_error=?
                WHERE id=? AND tenant_id=?
                """,
                (
                    result.get("detail"),
                    account["id"],
                    u["tenant_id"]
                )
            )

        audit(
            conn,u,"SYNC","vms_account",
            account["id"],
            hist_status,
            h.client_address[0]
        )

        conn.commit()

        code=result.pop("http_status")

        h._json(
            {
                "run_id":cur.lastrowid,
                **result
            },
            code
        )

        return True

    # --------------------------------------------------------------
    # REAL COMMUNICATION PROVIDER
    # --------------------------------------------------------------

    if path=="/api/communications/send":

        if u["role"] not in INTERNAL_ROLES:
            h._json({"error":"Permission denied"},403)
            return True

        channel=str(data.get("channel") or "").strip()

        if channel not in {"Email","SMS","Call","Internal"}:
            h._json({"error":"Unsupported channel"},400)
            return True

        entity_type=data.get("entity_type")
        entity_id=int(data.get("entity_id") or 0)

        if entity_type=="candidate":

            candidate=_tenant(
                conn,
                "candidates",
                entity_id,
                u
            )

            if not candidate:
                h._json({"error":"Candidate not found"},404)
                return True

            if candidate.get("do_not_contact"):
                h._json({"error":"Candidate is Do Not Contact"},409)
                return True

            if channel=="Email" and not candidate.get("consent_email",1):
                h._json({"error":"Email consent is not available"},409)
                return True

            if channel=="SMS" and not candidate.get("consent_sms",0):
                h._json({"error":"SMS consent is not available"},409)
                return True

        if channel=="Internal":

            cur=conn.execute(
                """
                INSERT INTO communications(
                    entity_type,entity_id,channel,direction,
                    subject,body,user_id,status,
                    created_at,tenant_id
                )
                VALUES(?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    entity_type,entity_id,
                    channel,"Outbound",
                    data.get("subject"),
                    data.get("body"),
                    u["id"],"Logged",
                    now(),u["tenant_id"]
                )
            )

            audit(
                conn,u,"COMMUNICATION","communication",
                cur.lastrowid,"Internal",
                h.client_address[0]
            )

            conn.commit()

            h._json(
                {
                    "id":cur.lastrowid,
                    "status":"Logged"
                },
                201
            )

            return True

        connector_id=int(data.get("connector_id") or 0)

        connector=_tenant(
            conn,
            "integration_connectors",
            connector_id,
            u
        )

        if not connector:
            h._json(
                {"error":"Configured provider connector is required"},
                409
            )
            return True

        action={
            "Email":"send_email",
            "SMS":"send_sms",
            "Call":"call"
        }[channel]

        result=_run_connector(
            conn,u,connector,action,{
                "to":data.get("to"),
                "subject":data.get("subject"),
                "body":data.get("body"),
                "entity_type":entity_type,
                "entity_id":entity_id
            }
        )

        cur=conn.execute(
            """
            INSERT INTO communications(
                entity_type,entity_id,channel,direction,
                subject,body,user_id,status,
                created_at,tenant_id
            )
            VALUES(?,?,?,?,?,?,?,?,?,?)
            """,
            (
                entity_type,entity_id,
                channel,"Outbound",
                data.get("subject"),
                data.get("body"),
                u["id"],
                "Sent" if result["ok"] else result["status"],
                now(),u["tenant_id"]
            )
        )

        audit(
            conn,u,"COMMUNICATION","communication",
            cur.lastrowid,
            result["status"],
            h.client_address[0]
        )

        conn.commit()

        code=result.pop("http_status")

        h._json(
            {
                "id":cur.lastrowid,
                **result
            },
            code if not result["ok"] else 201
        )

        return True

    return False


def r18_patch(h,conn,u,path,data):

    # --------------------------------------------------------------
    # ATTENDANCE EDIT / APPROVE
    # --------------------------------------------------------------

    m=re.fullmatch(r"/api/attendance/(\d+)",path)

    if m:

        aid=int(m.group(1))
        row=_tenant(conn,"attendance",aid,u)

        if not row:
            h._json({"error":"Not found"},404)
            return True

        if u["role"]=="worker":

            if row["candidate_id"]!=u.get("candidate_id"):
                h._json({"error":"Permission denied"},403)
                return True

            allowed={
                "check_in","check_out","status","note",
                "worked_hours"
            }

        elif u["role"] in WORKFORCE_ROLES:

            allowed={
                "attendance_date","check_in","check_out",
                "status","note","scheduled_hours",
                "worked_hours","late_minutes",
                "absence_reason","approval_state"
            }

        else:
            h._json({"error":"Permission denied"},403)
            return True

        fields=[k for k in data if k in allowed]

        if not fields:
            h._json({"error":"No valid fields"},400)
            return True

        if "worked_hours" in data:
            wh=float(data["worked_hours"] or 0)
            if wh < 0 or wh > 24:
                h._json({"error":"worked_hours must be 0-24"},400)
                return True

        values=[data[k] for k in fields]

        extra=["updated_at=?"]
        values.append(now())

        if (
            "approval_state" in fields
            and str(data["approval_state"]).lower()=="approved"
        ):
            extra += [
                "approved_by=?",
                "approved_at=?"
            ]
            values += [u["id"],now()]

        sql=(
            "UPDATE attendance SET "
            +",".join(
                [f"{k}=?" for k in fields]
                +extra
            )
            +" WHERE id=? AND tenant_id=?"
        )

        conn.execute(
            sql,
            tuple(values)+(aid,u["tenant_id"])
        )

        audit(
            conn,u,"UPDATE","attendance",
            aid,",".join(fields),
            h.client_address[0]
        )

        conn.commit()

        h._json({"ok":True})
        return True

    # --------------------------------------------------------------
    # DRAFT INVOICE EDIT
    # --------------------------------------------------------------

    m=re.fullmatch(r"/api/invoices/(\d+)",path)

    if m:

        if u["role"] not in FINANCE_ROLES:
            h._json({"error":"Permission denied"},403)
            return True

        iid=int(m.group(1))
        inv=_tenant(conn,"invoices",iid,u)

        if not inv:
            h._json({"error":"Not found"},404)
            return True

        if str(inv["status"]).lower()!="draft":
            h._json(
                {"error":"Only draft invoices can be edited"},
                409
            )
            return True

        allowed={
            "company_id","assignment_id",
            "period_start","period_end",
            "tax","discount","due_date",
            "po_id","notes","currency"
        }

        fields=[k for k in data if k in allowed]

        if not fields:
            h._json({"error":"No valid fields"},400)
            return True

        for k in ("tax","discount"):
            if k in data:
                data[k]=float(money(data[k]))

        values=[data[k] for k in fields]

        conn.execute(
            "UPDATE invoices SET "
            +",".join(f"{k}=?" for k in fields)
            +",updated_at=? WHERE id=? AND tenant_id=?",
            tuple(values)+(now(),iid,u["tenant_id"])
        )

        audit(
            conn,u,"UPDATE","invoice",
            iid,",".join(fields),
            h.client_address[0]
        )

        conn.commit()

        h._json({"ok":True})
        return True

    return False


def r18_delete(h,conn,u,path,qs):

    m=re.fullmatch(r"/api/attendance/(\d+)",path)

    if m:

        if u["role"] not in WORKFORCE_ROLES:
            h._json({"error":"Permission denied"},403)
            return True

        aid=int(m.group(1))
        row=_tenant(conn,"attendance",aid,u)

        if not row:
            h._json({"error":"Not found"},404)
            return True

        if str(row.get("approval_state") or "").lower()=="approved":
            h._json(
                {"error":"Approved attendance cannot be deleted"},
                409
            )
            return True

        conn.execute(
            """
            DELETE FROM attendance
            WHERE id=? AND tenant_id=?
            """,
            (aid,u["tenant_id"])
        )

        audit(
            conn,u,"DELETE","attendance",
            aid,"",h.client_address[0]
        )

        conn.commit()

        h._json({"ok":True})
        return True

    m=re.fullmatch(r"/api/invoice-lines/(\d+)",path)

    if m:

        if u["role"] not in FINANCE_ROLES:
            h._json({"error":"Permission denied"},403)
            return True

        line=_tenant(
            conn,
            "invoice_lines",
            int(m.group(1)),
            u
        )

        if not line:
            h._json({"error":"Not found"},404)
            return True

        inv=_tenant(
            conn,
            "invoices",
            line["invoice_id"],
            u
        )

        if not inv or str(inv["status"]).lower()!="draft":
            h._json(
                {"error":"Only draft invoice lines can be deleted"},
                409
            )
            return True

        conn.execute(
            """
            DELETE FROM invoice_lines
            WHERE id=? AND tenant_id=?
            """,
            (line["id"],u["tenant_id"])
        )

        subtotal=one(
            conn,
            """
            SELECT COALESCE(SUM(amount),0) total
            FROM invoice_lines
            WHERE invoice_id=? AND tenant_id=?
            """,
            (inv["id"],u["tenant_id"])
        )["total"]

        conn.execute(
            """
            UPDATE invoices
            SET amount=?,updated_at=?
            WHERE id=? AND tenant_id=?
            """,
            (subtotal,now(),inv["id"],u["tenant_id"])
        )

        audit(
            conn,u,"DELETE_LINE","invoice",
            inv["id"],str(line["id"]),
            h.client_address[0]
        )

        conn.commit()

        h._json({"ok":True})
        return True

    return False
