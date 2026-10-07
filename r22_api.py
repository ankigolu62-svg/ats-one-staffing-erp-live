from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request

from r18_api import (
    allrows,
    one,
    _tenant,
    _connector_state,
    _build_connector_request,
    _redact,
    now,
    audit,
)


INTERNAL={
    "admin",
    "teamlead",
    "recruiter",
    "sales",
    "hr",
    "finance",
}


ADAPTERS={
    "reference-check":{
        "label":"Reference Check",
        "action":"reference_check",
        "candidate_required":True,
        "categories":{
            "referencecheck",
            "referencechecking",
        },
    },

    "wotc":{
        "label":"WOTC",
        "action":"wotc_screen",
        "candidate_required":True,
        "categories":{
            "wotc",
            "workopportunitytaxcredit",
            "taxcredit",
        },
    },

    "outlook":{
        "label":"Outlook",
        "action":"sync_calendar",
        "candidate_required":False,
        "categories":{
            "outlook",
            "microsoftgraph",
            "office365",
            "microsoft365",
        },
    },

    "candidate-enrichment":{
        "label":"Candidate Enrichment",
        "action":"enrich_candidate",
        "candidate_required":True,
        "categories":{
            "candidateenrichment",
            "enrichment",
        },
    },
}


LOCALES={
    "en":{
        "label":"English",
        "welcome":"Welcome",
        "subtitle":"Search open positions, track your applications and manage your candidate profile.",
        "language":"Language",
        "my_applications":"My Applications",
        "profile_credibility":"Profile Credibility",
        "availability":"Availability",
        "active_processes":"active process(es)",
        "open_positions":"Open Positions",
        "apply":"Apply / Interested",
        "job":"Job",
        "status":"Status",
        "submitted":"Submitted",
        "interest_registered":"Interest registered. Recruiter can now qualify and submit you.",
    },

    "es":{
        "label":"Español",
        "welcome":"Bienvenido",
        "subtitle":"Busca puestos abiertos, sigue tus solicitudes y administra tu perfil de candidato.",
        "language":"Idioma",
        "my_applications":"Mis solicitudes",
        "profile_credibility":"Credibilidad del perfil",
        "availability":"Disponibilidad",
        "active_processes":"proceso(s) activo(s)",
        "open_positions":"Puestos abiertos",
        "apply":"Solicitar / Interesado",
        "job":"Puesto",
        "status":"Estado",
        "submitted":"Enviado",
        "interest_registered":"Interés registrado. El reclutador puede continuar con tu candidatura.",
    },

    "fr":{
        "label":"Français",
        "welcome":"Bienvenue",
        "subtitle":"Recherchez les postes ouverts, suivez vos candidatures et gérez votre profil candidat.",
        "language":"Langue",
        "my_applications":"Mes candidatures",
        "profile_credibility":"Crédibilité du profil",
        "availability":"Disponibilité",
        "active_processes":"processus actif(s)",
        "open_positions":"Postes ouverts",
        "apply":"Postuler / Intéressé",
        "job":"Poste",
        "status":"Statut",
        "submitted":"Soumis",
        "interest_registered":"Intérêt enregistré. Le recruteur peut poursuivre votre candidature.",
    },

    "zh":{
        "label":"中文",
        "welcome":"欢迎",
        "subtitle":"搜索开放职位、跟踪您的申请并管理候选人资料。",
        "language":"语言",
        "my_applications":"我的申请",
        "profile_credibility":"资料可信度",
        "availability":"可入职时间",
        "active_processes":"个进行中的流程",
        "open_positions":"开放职位",
        "apply":"申请 / 感兴趣",
        "job":"职位",
        "status":"状态",
        "submitted":"已提交",
        "interest_registered":"已登记您的兴趣。招聘人员现在可以继续处理您的候选流程。",
    },

    "hi":{
        "label":"हिन्दी",
        "welcome":"स्वागत है",
        "subtitle":"खुली नौकरियाँ खोजें, अपने आवेदन ट्रैक करें और अपना उम्मीदवार प्रोफ़ाइल प्रबंधित करें।",
        "language":"भाषा",
        "my_applications":"मेरे आवेदन",
        "profile_credibility":"प्रोफ़ाइल विश्वसनीयता",
        "availability":"उपलब्धता",
        "active_processes":"सक्रिय प्रक्रिया",
        "open_positions":"खुली नौकरियाँ",
        "apply":"आवेदन / रुचि",
        "job":"नौकरी",
        "status":"स्थिति",
        "submitted":"जमा किया",
        "interest_registered":"रुचि दर्ज हो गई है। भर्तीकर्ता अब आपकी उम्मीदवारी आगे बढ़ा सकता है।",
    },
}


DEFAULT_BRANDING={
    "product_name":"ATS One",
    "portal_title":"ATS One Staffing ERP",
    "logo_url":"",
    "primary_color":"#164e63",
    "secondary_color":"#0f172a",
    "support_email":"",
}


def ensure_r22_schema(conn):

    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS tenant_branding_r22(
            tenant_id INTEGER PRIMARY KEY,
            product_name TEXT NOT NULL,
            portal_title TEXT NOT NULL,
            logo_url TEXT,
            primary_color TEXT NOT NULL,
            secondary_color TEXT NOT NULL,
            support_email TEXT,
            updated_at TEXT NOT NULL,
            updated_by INTEGER
        );

        CREATE TABLE IF NOT EXISTS candidate_locale_preferences_r22(
            tenant_id INTEGER NOT NULL,
            candidate_id INTEGER NOT NULL,
            locale TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            updated_by INTEGER,
            PRIMARY KEY(tenant_id,candidate_id)
        );

        CREATE TABLE IF NOT EXISTS external_cases_r22(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,
            action TEXT NOT NULL,
            candidate_id INTEGER,
            connector_id INTEGER NOT NULL,
            status TEXT NOT NULL,
            provider_id TEXT,
            provider_http_status INTEGER,
            detail TEXT,
            payload_json TEXT,
            response_json TEXT,
            user_id INTEGER,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            tenant_id INTEGER NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_external_cases_r22_tenant
        ON external_cases_r22(tenant_id,id);

        CREATE INDEX IF NOT EXISTS idx_locale_r22_candidate
        ON candidate_locale_preferences_r22(tenant_id,candidate_id);
        """
    )


def _norm_category(value):
    return re.sub(
        r"[^a-z0-9]+",
        "",
        str(value or "").lower()
    )


def _locale(value):
    code=str(value or "en").strip().lower().replace("_","-")
    code=code.split("-",1)[0]
    return code if code in LOCALES else "en"


def _branding(conn,tenant_id):

    row=one(
        conn,
        """
        SELECT *
        FROM tenant_branding_r22
        WHERE tenant_id=?
        """,
        (tenant_id,)
    )

    if row:
        return row

    return {
        "tenant_id":tenant_id,
        **DEFAULT_BRANDING,
        "updated_at":None,
        "updated_by":None,
    }


def _adapter_connectors(conn,u,key):

    spec=ADAPTERS[key]

    rows=allrows(
        conn,
        """
        SELECT *
        FROM integration_connectors
        WHERE tenant_id=?
        ORDER BY id DESC
        """,
        (u["tenant_id"],)
    )

    result=[]

    for row in rows:

        if _norm_category(row.get("category")) not in spec["categories"]:
            continue

        item=dict(row)
        item["connection_state"]=_connector_state(row)
        result.append(item)

    return result


def _candidate_payload(candidate):

    if not candidate:
        return None

    keys=(
        "id",
        "first_name",
        "last_name",
        "email",
        "phone",
        "city",
        "state",
        "country",
        "zip",
        "profession",
        "specialty",
        "current_title",
        "availability_date",
    )

    return {
        key:candidate.get(key)
        for key in keys
    }


def _run_http_adapter(
    conn,
    u,
    connector,
    action,
    payload,
):

    state=_connector_state(connector)

    if state=="Configuration Required":
        return {
            "ok":False,
            "_api_status":409,
            "status":"Configuration Required",
            "detail":"External endpoint configuration is incomplete.",
            "provider_http_status":None,
            "provider_id":None,
            "response_json":None,
        }

    if state=="Credentials Required":
        return {
            "ok":False,
            "_api_status":409,
            "status":"Credentials Required",
            "detail":"Authorized provider credentials are required.",
            "provider_http_status":None,
            "provider_id":None,
            "response_json":None,
        }

    try:

        req,timeout,secret=_build_connector_request(
            connector,
            action,
            payload
        )

        try:
            with urllib.request.urlopen(req,timeout=timeout) as response:
                code=int(response.status)
                raw=response.read(1024*512)

        except urllib.error.HTTPError as exc:
            code=int(exc.code)
            raw=exc.read(1024*512)

        text=raw.decode("utf-8","replace")
        safe=_redact(text,[secret])

        parsed=None

        try:
            parsed=json.loads(safe)
        except Exception:
            parsed=None

        ok=200 <= code < 300
        status="Success" if ok else "Provider Error"

        provider_id=None

        if isinstance(parsed,dict):
            provider_id=(
                parsed.get("id")
                or parsed.get("message_id")
                or parsed.get("reference_id")
                or parsed.get("request_id")
            )

        detail=f"HTTP {code}"

        if safe:
            detail+=" :: "+safe[:1200]

        conn.execute(
            """
            INSERT INTO integration_logs(
                connector_id,action,status,detail,
                user_id,created_at,tenant_id
            )
            VALUES(?,?,?,?,?,?,?)
            """,
            (
                connector["id"],
                action,
                status,
                detail,
                u["id"],
                now(),
                u["tenant_id"],
            )
        )

        if ok:

            conn.execute(
                """
                UPDATE integration_connectors
                SET status='Connected',
                    last_sync=?,
                    last_error=NULL,
                    connected_at=COALESCE(connected_at,?)
                WHERE id=? AND tenant_id=?
                """,
                (
                    now(),
                    now(),
                    connector["id"],
                    u["tenant_id"],
                )
            )

        else:

            conn.execute(
                """
                UPDATE integration_connectors
                SET last_error=?
                WHERE id=? AND tenant_id=?
                """,
                (
                    f"HTTP {code}",
                    connector["id"],
                    u["tenant_id"],
                )
            )

        return {
            "ok":ok,
            "_api_status":200 if ok else 502,
            "status":status,
            "provider_http_status":code,
            "provider_id":provider_id,
            "detail":detail,
            "response_json":parsed,
        }

    except PermissionError as exc:

        return {
            "ok":False,
            "_api_status":409,
            "status":"Credentials Required",
            "provider_http_status":None,
            "provider_id":None,
            "detail":str(exc),
            "response_json":None,
        }

    except ValueError as exc:

        return {
            "ok":False,
            "_api_status":409,
            "status":"Configuration Required",
            "provider_http_status":None,
            "provider_id":None,
            "detail":str(exc),
            "response_json":None,
        }

    except Exception as exc:

        safe=_redact(str(exc),[])

        conn.execute(
            """
            INSERT INTO integration_logs(
                connector_id,action,status,detail,
                user_id,created_at,tenant_id
            )
            VALUES(?,?,?,?,?,?,?)
            """,
            (
                connector["id"],
                action,
                "Failed",
                safe,
                u["id"],
                now(),
                u["tenant_id"],
            )
        )

        return {
            "ok":False,
            "_api_status":502,
            "status":"Failed",
            "provider_http_status":None,
            "provider_id":None,
            "detail":safe,
            "response_json":None,
        }


def r22_public_get(h,conn,path,qs):

    if path=="/api/r22/public-branding":

        h._json(
            _branding(conn,1)
        )

        return True

    return False


def r22_get(h,conn,u,path,qs):

    if path=="/api/r22/coverage":

        if u["role"] not in INTERNAL:
            h._json({"error":"Permission denied"},403)
            return True

        h._json({
            "version":"R22",
            "multilingual_candidate_experience":"working",
            "white_label_application":"working",
            "reference_check_adapter":"working",
            "wotc_adapter":"working",
            "outlook_synchronization_adapter":"working",
            "candidate_enrichment_adapter":"working",
            "external_provider_truth_gate":"working",
        })

        return True


    if path=="/api/r22/branding":

        h._json(
            _branding(
                conn,
                u["tenant_id"]
            )
        )

        return True


    if path=="/api/r22/candidate-experience":

        if u["role"]!="candidate" or not u.get("candidate_id"):
            h._json({"error":"Permission denied"},403)
            return True

        pref=one(
            conn,
            """
            SELECT locale
            FROM candidate_locale_preferences_r22
            WHERE tenant_id=?
              AND candidate_id=?
            """,
            (
                u["tenant_id"],
                u["candidate_id"],
            )
        )

        requested=(
            (qs.get("locale") or [None])[0]
            if qs
            else None
        )

        code=_locale(
            requested
            or (pref or {}).get("locale")
            or "en"
        )

        h._json({
            "locale":code,
            "supported_locales":[
                {
                    "code":key,
                    "label":value["label"],
                }
                for key,value in LOCALES.items()
            ],
            "translations":LOCALES[code],
            "branding":_branding(
                conn,
                u["tenant_id"]
            ),
        })

        return True


    if path=="/api/r22/adapters":

        if u["role"] not in INTERNAL:
            h._json({"error":"Permission denied"},403)
            return True

        items=[]

        for key,spec in ADAPTERS.items():

            connectors=_adapter_connectors(
                conn,u,key
            )

            items.append({
                "key":key,
                "label":spec["label"],
                "action":spec["action"],
                "candidate_required":spec["candidate_required"],
                "connectors":[
                    {
                        "id":row["id"],
                        "name":row.get("name"),
                        "category":row.get("category"),
                        "mode":row.get("mode"),
                        "connection_state":row["connection_state"],
                    }
                    for row in connectors
                ],
            })

        h._json(items)
        return True


    if path=="/api/r22/external-cases":

        if u["role"] not in INTERNAL:
            h._json({"error":"Permission denied"},403)
            return True

        h._json(
            allrows(
                conn,
                """
                SELECT *
                FROM external_cases_r22
                WHERE tenant_id=?
                ORDER BY id DESC
                LIMIT 200
                """,
                (u["tenant_id"],)
            )
        )

        return True

    return False


def r22_post(h,conn,u,path,data):

    # ==============================================================
    # WHITE-LABEL BRANDING
    # ==============================================================

    if path=="/api/r22/branding":

        if u["role"]!="admin":
            h._json({"error":"Permission denied"},403)
            return True

        product_name=str(
            data.get("product_name")
            or ""
        ).strip()[:80]

        portal_title=str(
            data.get("portal_title")
            or product_name
            or ""
        ).strip()[:120]

        logo_url=str(
            data.get("logo_url")
            or ""
        ).strip()[:500]

        primary=str(
            data.get("primary_color")
            or "#164e63"
        ).strip()

        secondary=str(
            data.get("secondary_color")
            or "#0f172a"
        ).strip()

        support_email=str(
            data.get("support_email")
            or ""
        ).strip()[:200]

        if not product_name:
            h._json(
                {"error":"product_name required"},
                400
            )
            return True

        if not re.fullmatch(
            r"#[0-9A-Fa-f]{6}",
            primary
        ):
            h._json(
                {"error":"Invalid primary_color"},
                400
            )
            return True

        if not re.fullmatch(
            r"#[0-9A-Fa-f]{6}",
            secondary
        ):
            h._json(
                {"error":"Invalid secondary_color"},
                400
            )
            return True

        if (
            logo_url
            and not (
                logo_url.startswith("https://")
                or logo_url.startswith("/")
            )
        ):
            h._json(
                {"error":"logo_url must be HTTPS or relative"},
                400
            )
            return True

        if (
            support_email
            and not re.fullmatch(
                r"[^@\s]+@[^@\s]+\.[^@\s]+",
                support_email
            )
        ):
            h._json(
                {"error":"Invalid support_email"},
                400
            )
            return True

        ts=now()

        conn.execute(
            """
            INSERT INTO tenant_branding_r22(
                tenant_id,
                product_name,
                portal_title,
                logo_url,
                primary_color,
                secondary_color,
                support_email,
                updated_at,
                updated_by
            )
            VALUES(?,?,?,?,?,?,?,?,?)
            ON CONFLICT(tenant_id)
            DO UPDATE SET
                product_name=excluded.product_name,
                portal_title=excluded.portal_title,
                logo_url=excluded.logo_url,
                primary_color=excluded.primary_color,
                secondary_color=excluded.secondary_color,
                support_email=excluded.support_email,
                updated_at=excluded.updated_at,
                updated_by=excluded.updated_by
            """,
            (
                u["tenant_id"],
                product_name,
                portal_title,
                logo_url,
                primary,
                secondary,
                support_email,
                ts,
                u["id"],
            )
        )

        audit(
            conn,
            u,
            "UPDATE",
            "tenant_branding",
            u["tenant_id"],
            product_name,
            h.client_address[0],
        )

        conn.commit()

        h._json(
            _branding(
                conn,
                u["tenant_id"]
            )
        )

        return True


    # ==============================================================
    # MULTILINGUAL CANDIDATE EXPERIENCE
    # ==============================================================

    if path=="/api/r22/candidate-experience":

        if u["role"]!="candidate" or not u.get("candidate_id"):
            h._json({"error":"Permission denied"},403)
            return True

        raw=str(
            data.get("locale")
            or ""
        ).strip().lower()

        code=_locale(raw)

        if not raw or code not in LOCALES:
            h._json(
                {"error":"Unsupported locale"},
                400
            )
            return True

        conn.execute(
            """
            INSERT INTO candidate_locale_preferences_r22(
                tenant_id,
                candidate_id,
                locale,
                updated_at,
                updated_by
            )
            VALUES(?,?,?,?,?)
            ON CONFLICT(tenant_id,candidate_id)
            DO UPDATE SET
                locale=excluded.locale,
                updated_at=excluded.updated_at,
                updated_by=excluded.updated_by
            """,
            (
                u["tenant_id"],
                u["candidate_id"],
                code,
                now(),
                u["id"],
            )
        )

        audit(
            conn,
            u,
            "UPDATE",
            "candidate_locale",
            u["candidate_id"],
            code,
            h.client_address[0],
        )

        conn.commit()

        h._json({
            "ok":True,
            "locale":code,
            "translations":LOCALES[code],
        })

        return True


    # ==============================================================
    # REAL PROVIDER ADAPTER EXECUTION
    #
    # Reference Check
    # WOTC
    # Outlook / Microsoft Graph
    # Candidate Enrichment
    # ==============================================================

    m=re.fullmatch(
        r"/api/r22/adapters/"
        r"(reference-check|wotc|outlook|candidate-enrichment)"
        r"/execute",
        path
    )

    if m:

        if u["role"] not in {
            "admin",
            "teamlead",
            "recruiter",
            "sales",
            "hr",
        }:
            h._json({"error":"Permission denied"},403)
            return True

        key=m.group(1)
        spec=ADAPTERS[key]

        try:
            connector_id=int(
                data.get("connector_id")
                or 0
            )
        except Exception:
            connector_id=0

        connector=_tenant(
            conn,
            "integration_connectors",
            connector_id,
            u
        )

        if not connector:
            h._json(
                {"error":"Connector not found"},
                404
            )
            return True

        if (
            _norm_category(
                connector.get("category")
            )
            not in spec["categories"]
        ):
            h._json(
                {
                    "error":
                    "Connector category does not match requested adapter"
                },
                409
            )
            return True

        candidate=None
        candidate_id=data.get("candidate_id")

        if spec["candidate_required"]:

            try:
                candidate_id=int(
                    candidate_id
                    or 0
                )
            except Exception:
                candidate_id=0

            candidate=_tenant(
                conn,
                "candidates",
                candidate_id,
                u
            )

            if not candidate:
                h._json(
                    {"error":"Candidate not found"},
                    404
                )
                return True

        supplied=data.get("payload") or {}

        if not isinstance(supplied,dict):
            h._json(
                {"error":"payload must be an object"},
                400
            )
            return True

        payload={
            "source":"ATS-One",
            "adapter":key,
            "requested_by":u["id"],
            **supplied,
        }

        if candidate:
            payload["candidate"]=_candidate_payload(
                candidate
            )

        result=_run_http_adapter(
            conn,
            u,
            connector,
            spec["action"],
            payload,
        )

        updated_fields=[]

        # ----------------------------------------------------------
        # Candidate enrichment is a true data operation:
        # verified provider JSON can update an explicit whitelist.
        # ----------------------------------------------------------

        if (
            key=="candidate-enrichment"
            and candidate
            and result.get("ok")
            and isinstance(
                result.get("response_json"),
                dict
            )
        ):

            response=result["response_json"]

            patch=(
                response.get("candidate_patch")
                or response.get("candidate")
                or {}
            )

            if isinstance(patch,dict):

                allowed={
                    "phone",
                    "city",
                    "state",
                    "country",
                    "zip",
                    "profession",
                    "specialty",
                    "current_title",
                    "summary",
                    "availability_date",
                }

                clean={
                    k:v
                    for k,v in patch.items()
                    if k in allowed
                    and v is not None
                }

                if clean:

                    fields=list(clean.keys())

                    assignments=[
                        f"{name}=?"
                        for name in fields
                    ]

                    values=[
                        clean[name]
                        for name in fields
                    ]

                    assignments.append(
                        "updated_at=?"
                    )

                    values.append(now())
                    values.extend([
                        candidate["id"],
                        u["tenant_id"],
                    ])

                    conn.execute(
                        "UPDATE candidates SET "
                        +",".join(assignments)
                        +" WHERE id=? AND tenant_id=?",
                        values
                    )

                    updated_fields=fields

        ts=now()

        cur=conn.execute(
            """
            INSERT INTO external_cases_r22(
                category,
                action,
                candidate_id,
                connector_id,
                status,
                provider_id,
                provider_http_status,
                detail,
                payload_json,
                response_json,
                user_id,
                created_at,
                updated_at,
                tenant_id
            )
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                key,
                spec["action"],
                candidate["id"]
                    if candidate
                    else None,
                connector["id"],
                result.get("status"),
                result.get("provider_id"),
                result.get("provider_http_status"),
                result.get("detail"),
                json.dumps(
                    payload,
                    separators=(",",":"),
                    ensure_ascii=False,
                ),
                json.dumps(
                    result.get("response_json"),
                    separators=(",",":"),
                    ensure_ascii=False,
                )
                if result.get("response_json") is not None
                else None,
                u["id"],
                ts,
                ts,
                u["tenant_id"],
            )
        )

        audit(
            conn,
            u,
            "EXECUTE",
            key,
            cur.lastrowid,
            result.get("status") or "",
            h.client_address[0],
        )

        conn.commit()

        api_status=int(
            result.pop(
                "_api_status",
                200
            )
        )

        h._json(
            {
                "case_id":cur.lastrowid,
                "candidate_updated_fields":
                    updated_fields,
                **result,
            },
            api_status
        )

        return True

    return False
