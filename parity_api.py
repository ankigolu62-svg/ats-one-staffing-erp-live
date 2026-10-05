import base64
import hashlib
import json
import re
from datetime import datetime, timezone

INTERNAL = {"admin","teamlead","recruiter","sales","hr","finance"}
RECRUITING = {"admin","teamlead","recruiter","sales","hr"}
CRM = {"admin","teamlead","sales","recruiter"}
WORKFORCE = {"admin","teamlead","hr","finance"}
FINANCE = {"admin","finance"}
ADMIN = {"admin"}

SCHEMA = r"""
CREATE TABLE IF NOT EXISTS candidate_preferred_locations(
 id INTEGER PRIMARY KEY AUTOINCREMENT, candidate_id INTEGER NOT NULL,
 country TEXT, state TEXT, city TEXT, zip TEXT, radius_miles REAL DEFAULT 0,
 priority INTEGER DEFAULT 1, created_at TEXT NOT NULL, tenant_id INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS candidate_education(
 id INTEGER PRIMARY KEY AUTOINCREMENT, candidate_id INTEGER NOT NULL,
 institution TEXT, degree TEXT, field TEXT, start_date TEXT, end_date TEXT,
 graduated INTEGER DEFAULT 0, created_at TEXT NOT NULL, tenant_id INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS candidate_work_authorization(
 id INTEGER PRIMARY KEY AUTOINCREMENT, candidate_id INTEGER NOT NULL,
 country TEXT, authorization_type TEXT, status TEXT DEFAULT 'Active',
 expiry_date TEXT, sponsorship_required INTEGER DEFAULT 0,
 e_verify_status TEXT DEFAULT 'Not Started', verified_at TEXT,
 created_at TEXT NOT NULL, tenant_id INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS candidate_do_not_submit(
 id INTEGER PRIMARY KEY AUTOINCREMENT, candidate_id INTEGER NOT NULL,
 company_id INTEGER, job_id INTEGER, reason TEXT, active INTEGER DEFAULT 1,
 created_at TEXT NOT NULL, tenant_id INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS candidate_references(
 id INTEGER PRIMARY KEY AUTOINCREMENT, candidate_id INTEGER NOT NULL,
 name TEXT NOT NULL, company TEXT, title TEXT, email TEXT, phone TEXT,
 relationship TEXT, status TEXT DEFAULT 'Pending', notes TEXT,
 created_at TEXT NOT NULL, tenant_id INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS communication_preferences(
 id INTEGER PRIMARY KEY AUTOINCREMENT, candidate_id INTEGER NOT NULL,
 email_opt_out INTEGER DEFAULT 0, sms_opt_out INTEGER DEFAULT 0,
 phone_opt_out INTEGER DEFAULT 0, reason TEXT, effective_at TEXT,
 user_id INTEGER, created_at TEXT NOT NULL, tenant_id INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS company_notes(
 id INTEGER PRIMARY KEY AUTOINCREMENT, company_id INTEGER NOT NULL,
 note_type TEXT DEFAULT 'General', note TEXT NOT NULL, user_id INTEGER,
 created_at TEXT NOT NULL, tenant_id INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS contact_phones(
 id INTEGER PRIMARY KEY AUTOINCREMENT, contact_id INTEGER NOT NULL,
 phone_type TEXT DEFAULT 'Work', number TEXT NOT NULL, extension TEXT,
 is_primary INTEGER DEFAULT 0, created_at TEXT NOT NULL, tenant_id INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS contact_addresses(
 id INTEGER PRIMARY KEY AUTOINCREMENT, contact_id INTEGER NOT NULL,
 address_type TEXT DEFAULT 'Work', address1 TEXT, address2 TEXT, city TEXT,
 state TEXT, zip TEXT, country TEXT, is_default INTEGER DEFAULT 0,
 created_at TEXT NOT NULL, tenant_id INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS contact_notes(
 id INTEGER PRIMARY KEY AUTOINCREMENT, contact_id INTEGER NOT NULL,
 note_type TEXT DEFAULT 'General', note TEXT NOT NULL, user_id INTEGER,
 created_at TEXT NOT NULL, tenant_id INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS submission_events(
 id INTEGER PRIMARY KEY AUTOINCREMENT, submission_id INTEGER NOT NULL,
 event_type TEXT NOT NULL, from_status TEXT, to_status TEXT, note TEXT,
 user_id INTEGER, created_at TEXT NOT NULL, tenant_id INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS submission_attachments(
 id INTEGER PRIMARY KEY AUTOINCREMENT, submission_id INTEGER NOT NULL,
 name TEXT NOT NULL, mime_type TEXT, size_bytes INTEGER DEFAULT 0,
 sha256 TEXT, content BLOB, user_id INTEGER, created_at TEXT NOT NULL,
 tenant_id INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS onboarding_templates(
 id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, description TEXT,
 active INTEGER DEFAULT 1, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 tenant_id INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS onboarding_template_requirements(
 id INTEGER PRIMARY KEY AUTOINCREMENT, template_id INTEGER NOT NULL,
 requirement_type TEXT DEFAULT 'Document', name TEXT NOT NULL,
 mandatory INTEGER DEFAULT 1, sort_order INTEGER DEFAULT 0,
 tenant_id INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS timesheet_lines(
 id INTEGER PRIMARY KEY AUTOINCREMENT, timesheet_id INTEGER NOT NULL,
 work_date TEXT NOT NULL, category TEXT DEFAULT 'Regular', hours REAL DEFAULT 0,
 start_time TEXT, end_time TEXT, break_minutes INTEGER DEFAULT 0, note TEXT,
 created_at TEXT NOT NULL, tenant_id INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS expense_lines(
 id INTEGER PRIMARY KEY AUTOINCREMENT, expense_id INTEGER NOT NULL,
 expense_date TEXT, category TEXT, amount REAL DEFAULT 0, quantity REAL DEFAULT 1,
 billable INTEGER DEFAULT 1, pay_by_company INTEGER DEFAULT 0,
 currency TEXT DEFAULT 'USD', description TEXT, created_at TEXT NOT NULL,
 tenant_id INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS expense_receipts(
 id INTEGER PRIMARY KEY AUTOINCREMENT, expense_id INTEGER NOT NULL,
 file_name TEXT NOT NULL, mime_type TEXT, size_bytes INTEGER DEFAULT 0,
 sha256 TEXT, content BLOB, created_at TEXT NOT NULL,
 tenant_id INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS invoice_lines(
 id INTEGER PRIMARY KEY AUTOINCREMENT, invoice_id INTEGER NOT NULL,
 line_type TEXT DEFAULT 'Service', description TEXT, quantity REAL DEFAULT 1,
 rate REAL DEFAULT 0, amount REAL DEFAULT 0, tax REAL DEFAULT 0,
 source_type TEXT, source_id INTEGER, created_at TEXT NOT NULL,
 tenant_id INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS communication_templates(
 id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
 channel TEXT DEFAULT 'Email', subject TEXT, body TEXT, active INTEGER DEFAULT 1,
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 tenant_id INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS notifications(
 id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
 category TEXT DEFAULT 'General', title TEXT NOT NULL, body TEXT,
 entity_type TEXT, entity_id INTEGER, read_at TEXT, created_at TEXT NOT NULL,
 tenant_id INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS saved_views(
 id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
 entity_type TEXT NOT NULL, name TEXT NOT NULL, filters_json TEXT,
 columns_json TEXT, sort_json TEXT, is_shared INTEGER DEFAULT 0,
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 tenant_id INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS permission_overrides(
 id INTEGER PRIMARY KEY AUTOINCREMENT, role TEXT NOT NULL,
 module_name TEXT NOT NULL, can_view INTEGER DEFAULT 1,
 can_create INTEGER DEFAULT 0, can_edit INTEGER DEFAULT 0,
 can_delete INTEGER DEFAULT 0, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 tenant_id INTEGER NOT NULL DEFAULT 1,
 UNIQUE(tenant_id,role,module_name)
);
CREATE TABLE IF NOT EXISTS approval_steps(
 id INTEGER PRIMARY KEY AUTOINCREMENT, entity_type TEXT NOT NULL,
 entity_id INTEGER NOT NULL, step_no INTEGER NOT NULL DEFAULT 1,
 approver_role TEXT, approver_user_id INTEGER, status TEXT DEFAULT 'Pending',
 note TEXT, acted_at TEXT, created_at TEXT NOT NULL,
 tenant_id INTEGER NOT NULL DEFAULT 1
);
"""

RESOURCES = {
    "candidate-preferred-locations": ("candidate_preferred_locations", RECRUITING, {"country","state","city","zip","radius_miles","priority"}),
    "candidate-education": ("candidate_education", RECRUITING, {"institution","degree","field","start_date","end_date","graduated"}),
    "candidate-work-authorization": ("candidate_work_authorization", RECRUITING, {"country","authorization_type","status","expiry_date","sponsorship_required","e_verify_status","verified_at"}),
    "candidate-do-not-submit": ("candidate_do_not_submit", RECRUITING, {"company_id","job_id","reason","active"}),
    "candidate-references": ("candidate_references", RECRUITING, {"name","company","title","email","phone","relationship","status","notes"}),
    "communication-preferences": ("communication_preferences", RECRUITING, {"email_opt_out","sms_opt_out","phone_opt_out","reason","effective_at"}),
    "company-notes": ("company_notes", CRM, {"note_type","note"}),
    "contact-phones": ("contact_phones", CRM, {"phone_type","number","extension","is_primary"}),
    "contact-addresses": ("contact_addresses", CRM, {"address_type","address1","address2","city","state","zip","country","is_default"}),
    "contact-notes": ("contact_notes", CRM, {"note_type","note"}),
    "submission-events": ("submission_events", RECRUITING | {"sales"}, {"event_type","from_status","to_status","note"}),
    "onboarding-templates": ("onboarding_templates", {"admin","teamlead","hr","recruiter"}, {"name","description","active"}),
    "onboarding-template-requirements": ("onboarding_template_requirements", {"admin","teamlead","hr","recruiter"}, {"requirement_type","name","mandatory","sort_order"}),
    "timesheet-lines": ("timesheet_lines", WORKFORCE | {"worker","approver"}, {"work_date","category","hours","start_time","end_time","break_minutes","note"}),
    "expense-lines": ("expense_lines", WORKFORCE | {"worker","approver"}, {"expense_date","category","amount","quantity","billable","pay_by_company","currency","description"}),
    "invoice-lines": ("invoice_lines", FINANCE, {"line_type","description","quantity","rate","amount","tax","source_type","source_id"}),
    "communication-templates": ("communication_templates", {"admin","teamlead","recruiter","sales","hr"}, {"name","channel","subject","body","active"}),
    "notifications": ("notifications", INTERNAL, {"category","title","body","entity_type","entity_id","read_at"}),
    "saved-views": ("saved_views", INTERNAL, {"entity_type","name","filters_json","columns_json","sort_json","is_shared"}),
    "permission-overrides": ("permission_overrides", ADMIN, {"role","module_name","can_view","can_create","can_edit","can_delete"}),
    "approval-steps": ("approval_steps", INTERNAL, {"entity_type","entity_id","step_no","approver_role","approver_user_id","status","note","acted_at"}),
}

def now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

def rows(conn, sql, params=()):
    return [dict(r) for r in conn.execute(sql, params).fetchall()]

def row(conn, sql, params=()):
    r=conn.execute(sql, params).fetchone()
    return dict(r) if r else None

def send(h, payload, status=200):
    h._json(payload,status)
    return True

def ensure_parity_schema(conn):
    conn.executescript(SCHEMA)
    for table in [
        "candidate_preferred_locations","candidate_education","candidate_work_authorization",
        "candidate_do_not_submit","candidate_references","communication_preferences",
        "company_notes","contact_phones","contact_addresses","contact_notes",
        "submission_events","submission_attachments","onboarding_templates",
        "onboarding_template_requirements","timesheet_lines","expense_lines",
        "expense_receipts","invoice_lines","communication_templates","notifications",
        "saved_views","permission_overrides","approval_steps"
    ]:
        conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{table}_tenant ON {table}(tenant_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_pref_candidate ON candidate_preferred_locations(tenant_id,candidate_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_edu_candidate ON candidate_education(tenant_id,candidate_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_company_notes_parent ON company_notes(tenant_id,company_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_contact_phone_parent ON contact_phones(tenant_id,contact_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_submission_events_parent ON submission_events(tenant_id,submission_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_notifications_user ON notifications(tenant_id,user_id,read_at)")
    conn.commit()

def audit(conn,u,action,entity_type,entity_id=None,detail=""):
    conn.execute(
        "INSERT INTO audit_log(user_id,action,entity_type,entity_id,detail,ip,created_at,tenant_id) VALUES(?,?,?,?,?,?,?,?)",
        (u["id"],action,entity_type,entity_id,detail,"",now(),u["tenant_id"])
    )

def owned(conn, table, entity_id, tenant_id):
    return row(conn,f"SELECT id FROM {table} WHERE id=? AND tenant_id=?",(entity_id,tenant_id))

def candidate_ok(conn,u,cid,write=False):
    if write:
        return u["role"] in RECRUITING and owned(conn,"candidates",cid,u["tenant_id"])
    if u["role"] in INTERNAL:
        return owned(conn,"candidates",cid,u["tenant_id"])
    if u["role"] in {"candidate","worker"} and int(u.get("candidate_id") or 0)==int(cid):
        return owned(conn,"candidates",cid,u["tenant_id"])
    return False

def insert_fields(conn,table,base,data,allowed,tenant_id):
    values={k:data.get(k) for k in allowed if k in data}
    values.update(base)
    values["tenant_id"]=tenant_id
    if "created_at" in {r["name"] for r in rows(conn,f"PRAGMA table_info({table})")}:
        values["created_at"]=now()
    if "updated_at" in {r["name"] for r in rows(conn,f"PRAGMA table_info({table})")}:
        values["updated_at"]=now()
    cols=list(values)
    cur=conn.execute(
        f"INSERT INTO {table}("+",".join(cols)+") VALUES("+",".join("?" for _ in cols)+")",
        tuple(values[x] for x in cols)
    )
    return cur.lastrowid

def _list_parent(conn,table,parent_col,parent_id,tenant_id):
    return rows(conn,f"SELECT * FROM {table} WHERE {parent_col}=? AND tenant_id=? ORDER BY id DESC",(parent_id,tenant_id))

def parity_get(h,conn,u,path,qs):
    tid=u["tenant_id"]

    m=re.fullmatch(r"/api/candidates/(\d+)/(preferred-locations|education|work-authorization|do-not-submit|references|communication-preferences)",path)
    if m:
        cid=int(m.group(1)); slug=m.group(2)
        if not candidate_ok(conn,u,cid,False): return send(h,{"error":"Permission denied"},403)
        table={
            "preferred-locations":"candidate_preferred_locations",
            "education":"candidate_education",
            "work-authorization":"candidate_work_authorization",
            "do-not-submit":"candidate_do_not_submit",
            "references":"candidate_references",
            "communication-preferences":"communication_preferences",
        }[slug]
        return send(h,_list_parent(conn,table,"candidate_id",cid,tid))

    m=re.fullmatch(r"/api/companies/(\d+)/notes",path)
    if m:
        if u["role"] not in CRM:return send(h,{"error":"Permission denied"},403)
        cid=int(m.group(1))
        if not owned(conn,"companies",cid,tid):return send(h,{"error":"Not found"},404)
        return send(h,_list_parent(conn,"company_notes","company_id",cid,tid))

    m=re.fullmatch(r"/api/contacts/(\d+)/(phones|addresses|notes)",path)
    if m:
        if u["role"] not in CRM:return send(h,{"error":"Permission denied"},403)
        cid=int(m.group(1)); section=m.group(2)
        if not owned(conn,"contacts",cid,tid):return send(h,{"error":"Not found"},404)
        table={"phones":"contact_phones","addresses":"contact_addresses","notes":"contact_notes"}[section]
        return send(h,_list_parent(conn,table,"contact_id",cid,tid))

    m=re.fullmatch(r"/api/submissions/(\d+)/(events|attachments)",path)
    if m:
        if u["role"] not in INTERNAL:return send(h,{"error":"Permission denied"},403)
        sid=int(m.group(1)); section=m.group(2)
        if not owned(conn,"submissions",sid,tid):return send(h,{"error":"Not found"},404)
        table={"events":"submission_events","attachments":"submission_attachments"}[section]
        data=_list_parent(conn,table,"submission_id",sid,tid)
        if section=="attachments":
            for x in data:x.pop("content",None)
        return send(h,data)

    if path=="/api/onboarding/templates":
        if u["role"] not in INTERNAL:return send(h,{"error":"Permission denied"},403)
        return send(h,rows(conn,"SELECT * FROM onboarding_templates WHERE tenant_id=? ORDER BY active DESC,name",(tid,)))

    m=re.fullmatch(r"/api/onboarding/templates/(\d+)/requirements",path)
    if m:
        if u["role"] not in INTERNAL:return send(h,{"error":"Permission denied"},403)
        template_id=int(m.group(1))
        if not owned(conn,"onboarding_templates",template_id,tid):return send(h,{"error":"Not found"},404)
        return send(h,_list_parent(conn,"onboarding_template_requirements","template_id",template_id,tid))

    m=re.fullmatch(r"/api/timesheets/(\d+)/lines",path)
    if m:
        tsid=int(m.group(1))
        sheet=row(conn,"SELECT * FROM timesheets WHERE id=? AND tenant_id=?",(tsid,tid))
        if not sheet:return send(h,{"error":"Not found"},404)
        if u["role"]=="worker" and int(sheet["candidate_id"])!=int(u.get("candidate_id") or 0):return send(h,{"error":"Permission denied"},403)
        if u["role"] not in INTERNAL|{"worker","approver"}:return send(h,{"error":"Permission denied"},403)
        return send(h,_list_parent(conn,"timesheet_lines","timesheet_id",tsid,tid))

    m=re.fullmatch(r"/api/expenses/(\d+)/(lines|receipts)",path)
    if m:
        eid=int(m.group(1)); section=m.group(2)
        exp=row(conn,"SELECT * FROM expenses WHERE id=? AND tenant_id=?",(eid,tid))
        if not exp:return send(h,{"error":"Not found"},404)
        if u["role"]=="worker" and int(exp["candidate_id"])!=int(u.get("candidate_id") or 0):return send(h,{"error":"Permission denied"},403)
        if u["role"] not in INTERNAL|{"worker","approver"}:return send(h,{"error":"Permission denied"},403)
        table={"lines":"expense_lines","receipts":"expense_receipts"}[section]
        data=_list_parent(conn,table,"expense_id",eid,tid)
        if section=="receipts":
            for x in data:x.pop("content",None)
        return send(h,data)

    m=re.fullmatch(r"/api/invoices/(\d+)/lines",path)
    if m:
        if u["role"] not in FINANCE:return send(h,{"error":"Permission denied"},403)
        iid=int(m.group(1))
        if not owned(conn,"invoices",iid,tid):return send(h,{"error":"Not found"},404)
        return send(h,_list_parent(conn,"invoice_lines","invoice_id",iid,tid))

    if path=="/api/communication-templates":
        if u["role"] not in INTERNAL:return send(h,{"error":"Permission denied"},403)
        return send(h,rows(conn,"SELECT * FROM communication_templates WHERE tenant_id=? ORDER BY active DESC,name",(tid,)))

    if path=="/api/notifications":
        if u["role"] not in INTERNAL:return send(h,{"error":"Permission denied"},403)
        requested=int((qs.get("user_id") or [u["id"]])[0] or u["id"])
        if requested!=u["id"] and u["role"]!="admin":return send(h,{"error":"Permission denied"},403)
        return send(h,rows(conn,"SELECT * FROM notifications WHERE tenant_id=? AND user_id=? ORDER BY id DESC LIMIT 200",(tid,requested)))

    if path=="/api/saved-views":
        if u["role"] not in INTERNAL:return send(h,{"error":"Permission denied"},403)
        entity=(qs.get("entity_type") or [""])[0]
        sql="SELECT * FROM saved_views WHERE tenant_id=? AND (user_id=? OR is_shared=1)"
        params=[tid,u["id"]]
        if entity:
            sql+=" AND entity_type=?";params.append(entity)
        sql+=" ORDER BY id DESC"
        return send(h,rows(conn,sql,params))

    if path=="/api/permission-overrides":
        if u["role"]!="admin":return send(h,{"error":"Permission denied"},403)
        return send(h,rows(conn,"SELECT * FROM permission_overrides WHERE tenant_id=? ORDER BY role,module_name",(tid,)))

    if path=="/api/approval-steps":
        if u["role"] not in INTERNAL:return send(h,{"error":"Permission denied"},403)
        entity_type=(qs.get("entity_type") or [""])[0]
        entity_id=int((qs.get("entity_id") or [0])[0] or 0)
        sql="SELECT * FROM approval_steps WHERE tenant_id=?";params=[tid]
        if entity_type:sql+=" AND entity_type=?";params.append(entity_type)
        if entity_id:sql+=" AND entity_id=?";params.append(entity_id)
        sql+=" ORDER BY entity_type,entity_id,step_no,id"
        return send(h,rows(conn,sql,params))

    return False

def parity_post(h,conn,u,path,data):
    tid=u["tenant_id"]

    m=re.fullmatch(r"/api/candidates/(\d+)/(preferred-locations|education|work-authorization|do-not-submit|references|communication-preferences)",path)
    if m:
        cid=int(m.group(1));slug=m.group(2)
        if not candidate_ok(conn,u,cid,True):return send(h,{"error":"Permission denied"},403)
        meta={
          "preferred-locations":("candidate_preferred_locations",{"country","state","city","zip","radius_miles","priority"}),
          "education":("candidate_education",{"institution","degree","field","start_date","end_date","graduated"}),
          "work-authorization":("candidate_work_authorization",{"country","authorization_type","status","expiry_date","sponsorship_required","e_verify_status","verified_at"}),
          "do-not-submit":("candidate_do_not_submit",{"company_id","job_id","reason","active"}),
          "references":("candidate_references",{"name","company","title","email","phone","relationship","status","notes"}),
          "communication-preferences":("communication_preferences",{"email_opt_out","sms_opt_out","phone_opt_out","reason","effective_at"})
        }[slug]
        if slug=="do-not-submit":
            if data.get("company_id") and not owned(conn,"companies",int(data["company_id"]),tid):return send(h,{"error":"Company not found"},404)
            if data.get("job_id") and not owned(conn,"jobs",int(data["job_id"]),tid):return send(h,{"error":"Job not found"},404)
        base={"candidate_id":cid}
        if slug=="communication-preferences":base["user_id"]=u["id"]
        rid=insert_fields(conn,meta[0],base,data,meta[1],tid)
        audit(conn,u,"CREATE",meta[0],rid,f"candidate={cid}");conn.commit()
        return send(h,{"id":rid,"ok":True},201)

    m=re.fullmatch(r"/api/companies/(\d+)/notes",path)
    if m:
        if u["role"] not in CRM:return send(h,{"error":"Permission denied"},403)
        cid=int(m.group(1))
        if not owned(conn,"companies",cid,tid):return send(h,{"error":"Not found"},404)
        if not str(data.get("note") or "").strip():return send(h,{"error":"note required"},400)
        rid=insert_fields(conn,"company_notes",{"company_id":cid,"user_id":u["id"]},data,{"note_type","note"},tid)
        audit(conn,u,"CREATE","company_note",rid,f"company={cid}");conn.commit();return send(h,{"id":rid},201)

    m=re.fullmatch(r"/api/contacts/(\d+)/(phones|addresses|notes)",path)
    if m:
        if u["role"] not in CRM:return send(h,{"error":"Permission denied"},403)
        cid=int(m.group(1));section=m.group(2)
        if not owned(conn,"contacts",cid,tid):return send(h,{"error":"Not found"},404)
        meta={
          "phones":("contact_phones",{"phone_type","number","extension","is_primary"}),
          "addresses":("contact_addresses",{"address_type","address1","address2","city","state","zip","country","is_default"}),
          "notes":("contact_notes",{"note_type","note"})
        }[section]
        base={"contact_id":cid}
        if section=="notes":base["user_id"]=u["id"]
        rid=insert_fields(conn,meta[0],base,data,meta[1],tid)
        audit(conn,u,"CREATE",meta[0],rid,f"contact={cid}");conn.commit();return send(h,{"id":rid},201)

    m=re.fullmatch(r"/api/submissions/(\d+)/(events|attachments)",path)
    if m:
        if u["role"] not in INTERNAL:return send(h,{"error":"Permission denied"},403)
        sid=int(m.group(1));section=m.group(2)
        if not owned(conn,"submissions",sid,tid):return send(h,{"error":"Not found"},404)
        if section=="events":
            rid=insert_fields(conn,"submission_events",{"submission_id":sid,"user_id":u["id"]},data,{"event_type","from_status","to_status","note"},tid)
        else:
            encoded=data.get("content_base64") or ""
            try:content=base64.b64decode(encoded,validate=True)
            except Exception:return send(h,{"error":"content_base64 invalid"},400)
            if len(content)>10*1024*1024:return send(h,{"error":"attachment exceeds 10 MB"},413)
            name=data.get("name") or "attachment.bin";mime=data.get("mime_type") or "application/octet-stream"
            cur=conn.execute("INSERT INTO submission_attachments(submission_id,name,mime_type,size_bytes,sha256,content,user_id,created_at,tenant_id) VALUES(?,?,?,?,?,?,?,?,?)",(sid,name,mime,len(content),hashlib.sha256(content).hexdigest(),content,u["id"],now(),tid))
            rid=cur.lastrowid
        audit(conn,u,"CREATE","submission_"+section,rid,f"submission={sid}");conn.commit();return send(h,{"id":rid},201)

    if path=="/api/onboarding/templates":
        if u["role"] not in {"admin","teamlead","hr","recruiter"}:return send(h,{"error":"Permission denied"},403)
        rid=insert_fields(conn,"onboarding_templates",{},data,{"name","description","active"},tid)
        audit(conn,u,"CREATE","onboarding_template",rid,data.get("name",""));conn.commit();return send(h,{"id":rid},201)

    m=re.fullmatch(r"/api/onboarding/templates/(\d+)/requirements",path)
    if m:
        if u["role"] not in {"admin","teamlead","hr","recruiter"}:return send(h,{"error":"Permission denied"},403)
        template_id=int(m.group(1))
        if not owned(conn,"onboarding_templates",template_id,tid):return send(h,{"error":"Not found"},404)
        rid=insert_fields(conn,"onboarding_template_requirements",{"template_id":template_id},data,{"requirement_type","name","mandatory","sort_order"},tid)
        audit(conn,u,"CREATE","onboarding_template_requirement",rid,f"template={template_id}");conn.commit();return send(h,{"id":rid},201)

    m=re.fullmatch(r"/api/timesheets/(\d+)/lines",path)
    if m:
        tsid=int(m.group(1));sheet=row(conn,"SELECT * FROM timesheets WHERE id=? AND tenant_id=?",(tsid,tid))
        if not sheet:return send(h,{"error":"Not found"},404)
        if u["role"]=="worker" and int(sheet["candidate_id"])!=int(u.get("candidate_id") or 0):return send(h,{"error":"Permission denied"},403)
        if u["role"] not in WORKFORCE|{"worker"}:return send(h,{"error":"Permission denied"},403)
        rid=insert_fields(conn,"timesheet_lines",{"timesheet_id":tsid},data,{"work_date","category","hours","start_time","end_time","break_minutes","note"},tid)
        audit(conn,u,"CREATE","timesheet_line",rid,f"timesheet={tsid}");conn.commit();return send(h,{"id":rid},201)

    m=re.fullmatch(r"/api/expenses/(\d+)/(lines|receipts)",path)
    if m:
        eid=int(m.group(1));section=m.group(2);exp=row(conn,"SELECT * FROM expenses WHERE id=? AND tenant_id=?",(eid,tid))
        if not exp:return send(h,{"error":"Not found"},404)
        if u["role"]=="worker" and int(exp["candidate_id"])!=int(u.get("candidate_id") or 0):return send(h,{"error":"Permission denied"},403)
        if u["role"] not in WORKFORCE|{"worker"}:return send(h,{"error":"Permission denied"},403)
        if section=="lines":
            rid=insert_fields(conn,"expense_lines",{"expense_id":eid},data,{"expense_date","category","amount","quantity","billable","pay_by_company","currency","description"},tid)
        else:
            encoded=data.get("content_base64") or ""
            try:content=base64.b64decode(encoded,validate=True)
            except Exception:return send(h,{"error":"content_base64 invalid"},400)
            if len(content)>10*1024*1024:return send(h,{"error":"receipt exceeds 10 MB"},413)
            name=data.get("file_name") or "receipt.bin";mime=data.get("mime_type") or "application/octet-stream"
            cur=conn.execute("INSERT INTO expense_receipts(expense_id,file_name,mime_type,size_bytes,sha256,content,created_at,tenant_id) VALUES(?,?,?,?,?,?,?,?)",(eid,name,mime,len(content),hashlib.sha256(content).hexdigest(),content,now(),tid));rid=cur.lastrowid
        audit(conn,u,"CREATE","expense_"+section,rid,f"expense={eid}");conn.commit();return send(h,{"id":rid},201)

    m=re.fullmatch(r"/api/invoices/(\d+)/lines",path)
    if m:
        if u["role"] not in FINANCE:return send(h,{"error":"Permission denied"},403)
        iid=int(m.group(1))
        if not owned(conn,"invoices",iid,tid):return send(h,{"error":"Not found"},404)
        payload=dict(data)
        if payload.get("amount") in (None,""):
            payload["amount"]=float(payload.get("quantity") or 0)*float(payload.get("rate") or 0)
        rid=insert_fields(conn,"invoice_lines",{"invoice_id":iid},payload,{"line_type","description","quantity","rate","amount","tax","source_type","source_id"},tid)
        audit(conn,u,"CREATE","invoice_line",rid,f"invoice={iid}");conn.commit();return send(h,{"id":rid},201)

    if path=="/api/communication-templates":
        if u["role"] not in {"admin","teamlead","recruiter","sales","hr"}:return send(h,{"error":"Permission denied"},403)
        rid=insert_fields(conn,"communication_templates",{},data,{"name","channel","subject","body","active"},tid)
        audit(conn,u,"CREATE","communication_template",rid,data.get("name",""));conn.commit();return send(h,{"id":rid},201)

    if path=="/api/notifications":
        if u["role"] not in INTERNAL:return send(h,{"error":"Permission denied"},403)
        target=int(data.get("user_id") or u["id"])
        if not owned(conn,"users",target,tid):return send(h,{"error":"User not found"},404)
        rid=insert_fields(conn,"notifications",{"user_id":target},data,{"category","title","body","entity_type","entity_id","read_at"},tid)
        audit(conn,u,"CREATE","notification",rid,data.get("title",""));conn.commit();return send(h,{"id":rid},201)

    if path=="/api/saved-views":
        if u["role"] not in INTERNAL:return send(h,{"error":"Permission denied"},403)
        payload=dict(data)
        for k in ("filters_json","columns_json","sort_json"):
            if k in payload and not isinstance(payload[k],str):payload[k]=json.dumps(payload[k])
        rid=insert_fields(conn,"saved_views",{"user_id":u["id"]},payload,{"entity_type","name","filters_json","columns_json","sort_json","is_shared"},tid)
        audit(conn,u,"CREATE","saved_view",rid,data.get("name",""));conn.commit();return send(h,{"id":rid},201)

    if path=="/api/permission-overrides":
        if u["role"]!="admin":return send(h,{"error":"Permission denied"},403)
        values={k:data.get(k) for k in {"role","module_name","can_view","can_create","can_edit","can_delete"}}
        cur=conn.execute("""INSERT INTO permission_overrides(role,module_name,can_view,can_create,can_edit,can_delete,created_at,updated_at,tenant_id)
                           VALUES(?,?,?,?,?,?,?,?,?)
                           ON CONFLICT(tenant_id,role,module_name) DO UPDATE SET
                           can_view=excluded.can_view,can_create=excluded.can_create,can_edit=excluded.can_edit,
                           can_delete=excluded.can_delete,updated_at=excluded.updated_at""",
                         (values["role"],values["module_name"],values.get("can_view",1),values.get("can_create",0),values.get("can_edit",0),values.get("can_delete",0),now(),now(),tid))
        rid=cur.lastrowid or row(conn,"SELECT id FROM permission_overrides WHERE tenant_id=? AND role=? AND module_name=?",(tid,values["role"],values["module_name"]))["id"]
        audit(conn,u,"UPSERT","permission_override",rid,f'{values["role"]}:{values["module_name"]}');conn.commit();return send(h,{"id":rid},201)

    if path=="/api/approval-steps":
        if u["role"] not in INTERNAL:return send(h,{"error":"Permission denied"},403)
        if data.get("approver_user_id") and not owned(conn,"users",int(data["approver_user_id"]),tid):return send(h,{"error":"Approver user not found"},404)
        rid=insert_fields(conn,"approval_steps",{},data,{"entity_type","entity_id","step_no","approver_role","approver_user_id","status","note","acted_at"},tid)
        audit(conn,u,"CREATE","approval_step",rid,f'{data.get("entity_type")}:{data.get("entity_id")}');conn.commit();return send(h,{"id":rid},201)

    return False

def parity_patch(h,conn,u,path,data):
    m=re.fullmatch(r"/api/parity/([a-z-]+)/(\d+)",path)
    if not m:return False
    slug=m.group(1);rid=int(m.group(2))
    if slug not in RESOURCES:return send(h,{"error":"Unknown parity resource"},404)
    table,roles,allowed=RESOURCES[slug]
    if u["role"] not in roles:return send(h,{"error":"Permission denied"},403)
    existing=row(conn,f"SELECT * FROM {table} WHERE id=? AND tenant_id=?",(rid,u["tenant_id"]))
    if not existing:return send(h,{"error":"Not found"},404)
    if table=="saved_views" and u["role"]!="admin" and int(existing["user_id"])!=int(u["id"]):return send(h,{"error":"Permission denied"},403)
    if table=="notifications" and u["role"]!="admin" and int(existing["user_id"])!=int(u["id"]):return send(h,{"error":"Permission denied"},403)
    payload=dict(data)
    for k in ("filters_json","columns_json","sort_json"):
        if k in payload and not isinstance(payload[k],str):payload[k]=json.dumps(payload[k])
    fields=[k for k in payload if k in allowed]
    if not fields:return send(h,{"error":"No valid fields"},400)
    vals=[payload[k] for k in fields]
    if "updated_at" in {x["name"] for x in rows(conn,f"PRAGMA table_info({table})")}:
        fields.append("updated_at");vals.append(now())
    conn.execute(f"UPDATE {table} SET "+",".join(f"{x}=?" for x in fields)+" WHERE id=? AND tenant_id=?",tuple(vals)+(rid,u["tenant_id"]))
    audit(conn,u,"UPDATE",table,rid,",".join(fields));conn.commit();return send(h,{"ok":True})

def parity_delete(h,conn,u,path,qs):
    m=re.fullmatch(r"/api/parity/([a-z-]+)/(\d+)",path)
    if not m:return False
    slug=m.group(1);rid=int(m.group(2))
    if slug not in RESOURCES:return send(h,{"error":"Unknown parity resource"},404)
    table,roles,_=RESOURCES[slug]
    if u["role"] not in roles:return send(h,{"error":"Permission denied"},403)
    existing=row(conn,f"SELECT * FROM {table} WHERE id=? AND tenant_id=?",(rid,u["tenant_id"]))
    if not existing:return send(h,{"error":"Not found"},404)
    if table=="saved_views" and u["role"]!="admin" and int(existing["user_id"])!=int(u["id"]):return send(h,{"error":"Permission denied"},403)
    if table=="notifications" and u["role"]!="admin" and int(existing["user_id"])!=int(u["id"]):return send(h,{"error":"Permission denied"},403)
    conn.execute(f"DELETE FROM {table} WHERE id=? AND tenant_id=?",(rid,u["tenant_id"]))
    audit(conn,u,"DELETE",table,rid,"");conn.commit();return send(h,{"ok":True})