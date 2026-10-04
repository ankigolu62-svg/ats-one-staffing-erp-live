#!/usr/bin/env python3
import argparse, base64, hashlib, hmac, json, mimetypes, os, re, secrets, sqlite3, sys, threading, time, urllib.parse, urllib.request, urllib.error, webbrowser
from datetime import datetime, timedelta, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

APP_NAME = "ATS One Staffing ERP"
APP_VERSION = "2.1.0-live-free"
BASE_DIR = Path(__file__).resolve().parent
WEB_DIR = BASE_DIR / "web"
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "ats_one.db"

# Optional free cloud persistence using Supabase Storage.
# The live Render instance continues using SQLite locally for compatibility,
# while every successful write is checkpointed and backed up to a private
# Supabase Storage object. On a fresh Render boot the DB is restored first.
SUPABASE_URL = (os.environ.get("SUPABASE_URL") or "").rstrip("/")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or ""
SUPABASE_BUCKET = os.environ.get("SUPABASE_BUCKET") or "ats-one-private"
SUPABASE_DB_OBJECT = os.environ.get("SUPABASE_DB_OBJECT") or "ats_one.db"
REMOTE_PERSISTENCE_ENABLED = bool(SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY)
_BACKUP_LOCK = threading.Lock()
_BACKUP_ACTIVE = threading.local()

INTERNAL_ROLES = {"admin","teamlead","recruiter","sales","hr","finance"}
CANDIDATE_EDIT_ROLES = {"admin","teamlead","recruiter","hr"}
JOB_EDIT_ROLES = {"admin","teamlead","recruiter","sales"}
RECRUITING_ROLES = {"admin","teamlead","recruiter","sales","hr"}
WORKFORCE_ADMIN_ROLES = {"admin","teamlead","hr","finance"}

def _supabase_headers(content_type=None, upsert=False):
    h={
        "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
        "apikey": SUPABASE_SERVICE_ROLE_KEY,
    }
    if content_type: h["Content-Type"]=content_type
    if upsert: h["x-upsert"]="true"
    return h

def _supabase_request(method, url, data=None, headers=None, timeout=45):
    req=urllib.request.Request(url, data=data, method=method, headers=headers or {})
    return urllib.request.urlopen(req, timeout=timeout)

def ensure_remote_bucket():
    if not REMOTE_PERSISTENCE_ENABLED: return
    payload=json.dumps({"id":SUPABASE_BUCKET,"name":SUPABASE_BUCKET,"public":False}).encode()
    try:
        with _supabase_request("POST", f"{SUPABASE_URL}/storage/v1/bucket", payload, _supabase_headers("application/json")):
            pass
    except urllib.error.HTTPError as e:
        if e.code not in (400,409): raise

def restore_remote_db_if_needed():
    if not REMOTE_PERSISTENCE_ENABLED or DB_PATH.exists(): return False
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    ensure_remote_bucket()
    url=f"{SUPABASE_URL}/storage/v1/object/authenticated/{urllib.parse.quote(SUPABASE_BUCKET)}/{urllib.parse.quote(SUPABASE_DB_OBJECT)}"
    try:
        with _supabase_request("GET", url, None, _supabase_headers()) as r:
            raw=r.read()
        if raw:
            tmp=DB_PATH.with_suffix(".restore.tmp")
            tmp.write_bytes(raw)
            os.replace(tmp,DB_PATH)
            return True
    except urllib.error.HTTPError as e:
        if e.code not in (400,404): raise
    return False

def backup_remote_db():
    if not REMOTE_PERSISTENCE_ENABLED or not DB_PATH.exists(): return
    if getattr(_BACKUP_ACTIVE,"value",False): return
    with _BACKUP_LOCK:
        _BACKUP_ACTIVE.value=True
        try:
            ensure_remote_bucket()
            raw=DB_PATH.read_bytes()
            url=f"{SUPABASE_URL}/storage/v1/object/{urllib.parse.quote(SUPABASE_BUCKET)}/{urllib.parse.quote(SUPABASE_DB_OBJECT)}"
            try:
                with _supabase_request("POST", url, raw, _supabase_headers("application/octet-stream", True)):
                    pass
            except urllib.error.HTTPError as e:
                # Some Storage versions use PUT for upsert. Retry safely.
                if e.code in (400,405,409):
                    with _supabase_request("PUT", url, raw, _supabase_headers("application/octet-stream", True)):
                        pass
                else:
                    raise
        except Exception as e:
            print(f"REMOTE_BACKUP_WARNING={e}", file=sys.stderr, flush=True)
        finally:
            _BACKUP_ACTIVE.value=False

class PersistentSQLiteConnection(sqlite3.Connection):
    def commit(self):
        super().commit()
        if REMOTE_PERSISTENCE_ENABLED:
            try:
                # Ensure main DB file contains all committed WAL pages before upload.
                super().execute("PRAGMA wal_checkpoint(FULL)")
            except Exception:
                pass
            backup_remote_db()

ROLE_PERMISSIONS = {
    "admin": {"*"},
    "teamlead": {"dashboard","talent","candidate","job","crm","submission","interview","onboarding","assignment","timesheet","expense","report","communication","hotlist","assessment","document","vms","supplier","audit"},
    "recruiter": {"dashboard","talent","candidate","job","submission","interview","onboarding","hotlist","assessment","document","communication","report"},
    "sales": {"dashboard","crm","job","submission","communication","report"},
    "hr": {"dashboard","candidate","onboarding","document","assignment","timesheet","expense","report"},
    "finance": {"dashboard","assignment","timesheet","expense","finance","invoice","report"},
    "client": {"client_portal"},
    "candidate": {"candidate_portal"},
    "worker": {"worker_portal"},
    "supplier": {"supplier_portal"},
    "approver": {"approver_portal"},
}

DEMO_USERS = [
    ("admin@atsone.local","Admin@123","System Administrator","admin",None,None),
    ("teamlead@atsone.local","Lead@123","Tanya Team Lead","teamlead",None,None),
    ("recruiter@atsone.local","Recruit@123","Ravi Recruiter","recruiter",None,None),
    ("sales@atsone.local","Sales@123","Maya Account Manager","sales",None,None),
    ("hr@atsone.local","HR@123","Neha HR Ops","hr",None,None),
    ("finance@atsone.local","Finance@123","Amit Finance","finance",None,None),
    ("client@atsone.local","Client@123","Olivia Hiring Manager","client",1,None),
    ("candidate@atsone.local","Candidate@123","Priya Nair","candidate",None,1),
    ("worker@atsone.local","Worker@123","Arjun Mehta","worker",None,2),
    ("supplier@atsone.local","Supplier@123","Nina Supplier","supplier",None,None),
    ("approver@atsone.local","Approve@123","Carlos Approver","approver",1,None),
]

STATUS_FLOW = {
    "interested": ["interested","qualified","rejected"],
    "submission": ["draft","submitted","client_review","interview","offer","hired","rejected","withdrawn"],
    "interview": ["scheduled","completed","cancelled","no_show"],
    "onboarding": ["not_started","in_progress","complete","blocked"],
    "assignment": ["pending","active","ending","completed","terminated","cancelled"],
    "timesheet": ["draft","submitted","approved","rejected","invoiced"],
    "expense": ["draft","submitted","approved","rejected","invoiced"],
    "invoice": ["draft","issued","part_paid","paid","void"],
}

SYNONYMS = {
    "javascript": ["js","javascript","ecmascript"],
    "js": ["js","javascript","ecmascript"],
    "registered nurse": ["registered nurse","rn"],
    "rn": ["rn","registered nurse"],
    "aws": ["aws","amazon web services"],
    "azure": ["azure","microsoft azure"],
    "postgresql": ["postgresql","postgres"],
    "react": ["react","reactjs","react.js"],
    "spring": ["spring","spring boot","springboot"],
    "data engineer": ["data engineer","etl engineer","data engineering"],
}

SCHEMA = r'''
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS users(
 id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT UNIQUE NOT NULL, pass_hash TEXT NOT NULL,
 name TEXT NOT NULL, role TEXT NOT NULL, company_id INTEGER, candidate_id INTEGER,
 active INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY, user_id INTEGER NOT NULL, expires_at TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS companies(
 id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, company_type TEXT DEFAULT 'Client', industry TEXT,
 status TEXT DEFAULT 'Active', owner_user_id INTEGER, parent_company_id INTEGER, website TEXT, phone TEXT,
 address TEXT, city TEXT, state TEXT, country TEXT DEFAULT 'USA', billing_terms TEXT DEFAULT 'Net 30',
 submission_guidelines TEXT, discount_rule TEXT, notes TEXT, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS contacts(
 id INTEGER PRIMARY KEY AUTOINCREMENT, company_id INTEGER, first_name TEXT, last_name TEXT, title TEXT,
 email TEXT, phone TEXT, role_type TEXT DEFAULT 'Hiring Manager', owner_user_id INTEGER, status TEXT DEFAULT 'Active',
 notes TEXT, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS candidates(
 id INTEGER PRIMARY KEY AUTOINCREMENT, first_name TEXT NOT NULL, last_name TEXT NOT NULL, email TEXT, phone TEXT,
 city TEXT, state TEXT, country TEXT DEFAULT 'USA', zip TEXT, profession TEXT, specialty TEXT, current_title TEXT,
 availability_date TEXT, pay_min REAL, pay_max REAL, desired_rate_type TEXT DEFAULT 'hour', source TEXT,
 status TEXT DEFAULT 'Active', owner_user_id INTEGER, resume_text TEXT, summary TEXT, consent_sms INTEGER DEFAULT 1,
 consent_email INTEGER DEFAULT 1, do_not_contact INTEGER DEFAULT 0, credibility_score INTEGER DEFAULT 75,
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS candidate_skills(
 id INTEGER PRIMARY KEY AUTOINCREMENT, candidate_id INTEGER NOT NULL, skill TEXT NOT NULL, years REAL DEFAULT 0,
 recent INTEGER DEFAULT 0, last_used TEXT, UNIQUE(candidate_id, skill)
);
CREATE TABLE IF NOT EXISTS candidate_experience(
 id INTEGER PRIMARY KEY AUTOINCREMENT, candidate_id INTEGER NOT NULL, company TEXT, title TEXT,
 start_date TEXT, end_date TEXT, description TEXT, skills TEXT
);
CREATE TABLE IF NOT EXISTS candidate_licenses(
 id INTEGER PRIMARY KEY AUTOINCREMENT, candidate_id INTEGER NOT NULL, license_type TEXT, country TEXT,
 state TEXT, license_number TEXT, status TEXT DEFAULT 'Active', expiry_date TEXT, documented INTEGER DEFAULT 1
);
CREATE TABLE IF NOT EXISTS candidate_certifications(
 id INTEGER PRIMARY KEY AUTOINCREMENT, candidate_id INTEGER NOT NULL, name TEXT, status TEXT DEFAULT 'Active',
 expiry_date TEXT, documented INTEGER DEFAULT 1
);
CREATE TABLE IF NOT EXISTS candidate_qualifications(
 id INTEGER PRIMARY KEY AUTOINCREMENT, candidate_id INTEGER NOT NULL, name TEXT, value TEXT, sub_value TEXT
);
CREATE TABLE IF NOT EXISTS candidate_attributes(
 id INTEGER PRIMARY KEY AUTOINCREMENT, candidate_id INTEGER NOT NULL, attribute TEXT NOT NULL, value TEXT
);
CREATE TABLE IF NOT EXISTS candidate_documents(
 id INTEGER PRIMARY KEY AUTOINCREMENT, candidate_id INTEGER NOT NULL, doc_type TEXT, name TEXT, status TEXT,
 expiry_date TEXT, file_name TEXT, verified_by INTEGER, verified_at TEXT, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS candidate_notes(
 id INTEGER PRIMARY KEY AUTOINCREMENT, candidate_id INTEGER NOT NULL, user_id INTEGER NOT NULL, note TEXT NOT NULL,
 note_type TEXT DEFAULT 'General', created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS hotlists(
 id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, description TEXT, owner_user_id INTEGER,
 visibility TEXT DEFAULT 'Team', mode TEXT DEFAULT 'static', saved_search_json TEXT, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS hotlist_members(
 id INTEGER PRIMARY KEY AUTOINCREMENT, hotlist_id INTEGER NOT NULL, candidate_id INTEGER NOT NULL,
 status TEXT DEFAULT 'Active', note TEXT, added_by INTEGER, created_at TEXT NOT NULL,
 UNIQUE(hotlist_id,candidate_id)
);
CREATE TABLE IF NOT EXISTS jobs(
 id INTEGER PRIMARY KEY AUTOINCREMENT, job_no TEXT UNIQUE NOT NULL, title TEXT NOT NULL, company_id INTEGER,
 contact_id INTEGER, primary_recruiter_id INTEGER, sales_user_id INTEGER, status TEXT DEFAULT 'Open', priority TEXT DEFAULT 'Normal',
 position_type TEXT DEFAULT 'Contract', openings INTEGER DEFAULT 1, filled INTEGER DEFAULT 0, work_mode TEXT DEFAULT 'Onsite',
 city TEXT, state TEXT, country TEXT DEFAULT 'USA', zip TEXT, start_date TEXT, end_date TEXT,
 pay_min REAL, pay_max REAL, bill_min REAL, bill_max REAL, rate_type TEXT DEFAULT 'hour', profession TEXT, specialty TEXT,
 required_skills TEXT, required_qualifications TEXT, required_licenses TEXT, required_certifications TEXT,
 description TEXT, submission_guidelines_override TEXT, source TEXT DEFAULT 'Direct', external_vms_id TEXT,
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS job_users(
 id INTEGER PRIMARY KEY AUTOINCREMENT, job_id INTEGER NOT NULL, user_id INTEGER NOT NULL, role_name TEXT NOT NULL,
 UNIQUE(job_id,user_id,role_name)
);
CREATE TABLE IF NOT EXISTS interested_candidates(
 id INTEGER PRIMARY KEY AUTOINCREMENT, job_id INTEGER NOT NULL, candidate_id INTEGER NOT NULL,
 status TEXT DEFAULT 'interested', source TEXT, user_id INTEGER, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 UNIQUE(job_id,candidate_id)
);
CREATE TABLE IF NOT EXISTS submissions(
 id INTEGER PRIMARY KEY AUTOINCREMENT, job_id INTEGER NOT NULL, candidate_id INTEGER NOT NULL,
 recruiter_id INTEGER, status TEXT DEFAULT 'draft', client_rate REAL, candidate_rate REAL, availability TEXT,
 recruiter_summary TEXT, compliance_status TEXT DEFAULT 'Pending', rtr_status TEXT DEFAULT 'Pending',
 submitted_at TEXT, client_feedback TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS interviews(
 id INTEGER PRIMARY KEY AUTOINCREMENT, submission_id INTEGER NOT NULL, interview_type TEXT DEFAULT 'Video',
 scheduled_at TEXT, timezone TEXT DEFAULT 'UTC', status TEXT DEFAULT 'scheduled', location_or_link TEXT,
 interviewer TEXT, feedback TEXT, rating INTEGER, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS assessments(
 id INTEGER PRIMARY KEY AUTOINCREMENT, candidate_id INTEGER NOT NULL, job_id INTEGER, title TEXT,
 assessment_type TEXT DEFAULT 'Questionnaire', status TEXT DEFAULT 'Invited', score REAL, max_score REAL DEFAULT 100,
 invited_at TEXT, completed_at TEXT, notes TEXT
);
CREATE TABLE IF NOT EXISTS onboarding_packages(
 id INTEGER PRIMARY KEY AUTOINCREMENT, candidate_id INTEGER NOT NULL, job_id INTEGER, submission_id INTEGER,
 package_name TEXT, status TEXT DEFAULT 'not_started', assigned_by INTEGER, due_date TEXT, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS onboarding_requirements(
 id INTEGER PRIMARY KEY AUTOINCREMENT, package_id INTEGER NOT NULL, requirement_type TEXT, name TEXT,
 mandatory INTEGER DEFAULT 1, status TEXT DEFAULT 'Pending', completed_at TEXT, expiry_date TEXT, note TEXT
);
CREATE TABLE IF NOT EXISTS starts(
 id INTEGER PRIMARY KEY AUTOINCREMENT, submission_id INTEGER NOT NULL, start_date TEXT, status TEXT DEFAULT 'Confirmed',
 cancellation_reason TEXT, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS assignments(
 id INTEGER PRIMARY KEY AUTOINCREMENT, start_id INTEGER, candidate_id INTEGER NOT NULL, job_id INTEGER NOT NULL,
 company_id INTEGER, status TEXT DEFAULT 'pending', start_date TEXT, end_date TEXT, worksite TEXT, cost_center TEXT,
 vms_id TEXT, approver_contact_id INTEGER, bill_rate REAL, pay_rate REAL, overtime_rule TEXT DEFAULT '1.5x after 40h',
 payroll_profile TEXT, po_number TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS timesheets(
 id INTEGER PRIMARY KEY AUTOINCREMENT, assignment_id INTEGER NOT NULL, candidate_id INTEGER NOT NULL,
 week_start TEXT NOT NULL, status TEXT DEFAULT 'draft', total_hours REAL DEFAULT 0, regular_hours REAL DEFAULT 0,
 overtime_hours REAL DEFAULT 0, daily_json TEXT, submitted_at TEXT, approved_by INTEGER, approved_at TEXT,
 rejection_note TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 UNIQUE(assignment_id,week_start)
);
CREATE TABLE IF NOT EXISTS expenses(
 id INTEGER PRIMARY KEY AUTOINCREMENT, assignment_id INTEGER NOT NULL, candidate_id INTEGER NOT NULL,
 expense_date TEXT, category TEXT, amount REAL, receipt_ref TEXT, status TEXT DEFAULT 'draft', description TEXT,
 approved_by INTEGER, approved_at TEXT, rejection_note TEXT, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS purchase_orders(
 id INTEGER PRIMARY KEY AUTOINCREMENT, company_id INTEGER, job_id INTEGER, po_number TEXT UNIQUE, amount REAL,
 start_date TEXT, end_date TEXT, status TEXT DEFAULT 'Open'
);
CREATE TABLE IF NOT EXISTS invoices(
 id INTEGER PRIMARY KEY AUTOINCREMENT, invoice_no TEXT UNIQUE, company_id INTEGER, assignment_id INTEGER,
 period_start TEXT, period_end TEXT, amount REAL, tax REAL DEFAULT 0, status TEXT DEFAULT 'draft', due_date TEXT,
 issued_at TEXT, paid_at TEXT, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS vms_accounts(
 id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, platform TEXT, status TEXT DEFAULT 'Active', sync_mode TEXT DEFAULT 'Demo',
 last_sync TEXT, notes TEXT
);
CREATE TABLE IF NOT EXISTS vms_mappings(
 id INTEGER PRIMARY KEY AUTOINCREMENT, vms_account_id INTEGER, object_type TEXT, external_id TEXT,
 internal_id INTEGER, external_status TEXT, internal_status TEXT, mapping_json TEXT, updated_at TEXT
);
CREATE TABLE IF NOT EXISTS suppliers(
 id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, status TEXT DEFAULT 'Active', contact_name TEXT, email TEXT,
 phone TEXT, tier TEXT DEFAULT 'Preferred', notes TEXT
);
CREATE TABLE IF NOT EXISTS supplier_releases(
 id INTEGER PRIMARY KEY AUTOINCREMENT, supplier_id INTEGER, job_id INTEGER, released_at TEXT, status TEXT DEFAULT 'Open',
 max_submissions INTEGER DEFAULT 3
);
CREATE TABLE IF NOT EXISTS communications(
 id INTEGER PRIMARY KEY AUTOINCREMENT, entity_type TEXT, entity_id INTEGER, channel TEXT, direction TEXT,
 subject TEXT, body TEXT, user_id INTEGER, status TEXT DEFAULT 'Logged', created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS tasks(
 id INTEGER PRIMARY KEY AUTOINCREMENT, entity_type TEXT, entity_id INTEGER, title TEXT, due_at TEXT,
 owner_user_id INTEGER, status TEXT DEFAULT 'Open', priority TEXT DEFAULT 'Normal', created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS leads(
 id INTEGER PRIMARY KEY AUTOINCREMENT, company_id INTEGER, contact_id INTEGER, title TEXT NOT NULL, source TEXT,
 status TEXT DEFAULT 'New', owner_user_id INTEGER, next_action TEXT, next_action_at TEXT, notes TEXT, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS opportunities(
 id INTEGER PRIMARY KEY AUTOINCREMENT, company_id INTEGER, contact_id INTEGER, name TEXT NOT NULL, stage TEXT DEFAULT 'Lead',
 value REAL DEFAULT 0, probability INTEGER DEFAULT 10, owner_user_id INTEGER, expected_close TEXT, next_activity TEXT,
 status TEXT DEFAULT 'Open', notes TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS shifts(
 id INTEGER PRIMARY KEY AUTOINCREMENT, assignment_id INTEGER, candidate_id INTEGER, shift_date TEXT, start_time TEXT, end_time TEXT,
 location TEXT, status TEXT DEFAULT 'Scheduled', created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS attendance(
 id INTEGER PRIMARY KEY AUTOINCREMENT, shift_id INTEGER, candidate_id INTEGER, check_in TEXT, check_out TEXT, status TEXT, note TEXT
);
CREATE TABLE IF NOT EXISTS job_distribution(
 id INTEGER PRIMARY KEY AUTOINCREMENT, job_id INTEGER, channel TEXT, external_post_id TEXT, status TEXT DEFAULT 'Published',
 published_at TEXT, last_sync TEXT, applications INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS integration_connectors(
 id INTEGER PRIMARY KEY AUTOINCREMENT, category TEXT, name TEXT, mode TEXT DEFAULT 'Demo', status TEXT DEFAULT 'Configured',
 config_json TEXT, last_sync TEXT, notes TEXT
);
CREATE TABLE IF NOT EXISTS automations(
 id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, trigger_name TEXT, condition_json TEXT, action_json TEXT,
 active INTEGER DEFAULT 1, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS custom_fields(
 id INTEGER PRIMARY KEY AUTOINCREMENT, entity_type TEXT, field_name TEXT, field_type TEXT, required INTEGER DEFAULT 0,
 options_json TEXT, active INTEGER DEFAULT 1
);
CREATE TABLE IF NOT EXISTS entity_custom_values(
 id INTEGER PRIMARY KEY AUTOINCREMENT, entity_type TEXT, entity_id INTEGER, field_id INTEGER, value TEXT,
 UNIQUE(entity_type,entity_id,field_id)
);
CREATE TABLE IF NOT EXISTS audit_log(
 id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, action TEXT, entity_type TEXT, entity_id INTEGER,
 detail TEXT, ip TEXT, created_at TEXT NOT NULL
);
'''

def utcnow():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

def today(): return datetime.now().date().isoformat()

def hash_password(password: str, salt: bytes | None=None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 150_000)
    return base64.b64encode(salt).decode()+":"+base64.b64encode(digest).decode()

def verify_password(password: str, encoded: str) -> bool:
    try:
        s,d=encoded.split(':',1); salt=base64.b64decode(s); expected=base64.b64decode(d)
        got=hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 150_000)
        return hmac.compare_digest(expected,got)
    except Exception: return False

def db():
    conn=sqlite3.connect(DB_PATH, timeout=30, factory=PersistentSQLiteConnection, check_same_thread=False)
    conn.row_factory=sqlite3.Row
    conn.execute('PRAGMA foreign_keys=ON')
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA busy_timeout=30000')
    return conn

def qone(conn, sql, params=()):
    r=conn.execute(sql,params).fetchone(); return dict(r) if r else None

def qall(conn, sql, params=()): return [dict(r) for r in conn.execute(sql,params).fetchall()]

def audit(conn, user_id, action, entity_type, entity_id=None, detail='', ip=''):
    conn.execute('INSERT INTO audit_log(user_id,action,entity_type,entity_id,detail,ip,created_at) VALUES(?,?,?,?,?,?,?)',
                 (user_id,action,entity_type,entity_id,detail,ip,utcnow()))

def init_db(reset=False):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if reset and REMOTE_PERSISTENCE_ENABLED:
        raise RuntimeError("Remote live database reset is disabled. Use an explicit maintenance workflow.")
    if reset and DB_PATH.exists(): DB_PATH.unlink()
    if not reset:
        restore_remote_db_if_needed()
    conn=db(); conn.executescript(SCHEMA)
    seeded=qone(conn,"SELECT value FROM meta WHERE key='seeded'")
    if not seeded:
        seed(conn)
        conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('seeded','1')")
        conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('version',?)",(APP_VERSION,))
    conn.commit(); conn.close()

def seed(conn):
    now=utcnow()
    # companies
    companies=[
      ('Northstar Health System','Client','Healthcare','Active',2,None,'https://northstar.example','+1 415 555 0101','100 Market St','San Francisco','CA','USA','Net 30','Resume, active license, BLS/ACLS, recruiter summary and right-to-represent required.','2% discount if payment within 10 days','High-volume travel nursing client.'),
      ('Apex Financial Group','Client','Banking','Active',4,None,'https://apex.example','+1 212 555 0188','1 Liberty Plaza','New York','NY','USA','Net 45','Maximum 3 candidates per job. Include rate, availability, screening summary.','1.5% early-pay discount','Enterprise technology staffing account.'),
      ('BluePeak Technologies','Client','Technology','Active',4,None,'https://bluepeak.example','+1 512 555 0114','500 Congress Ave','Austin','TX','USA','Net 30','Portfolio or GitHub requested for engineering roles.','','Product and cloud engineering.'),
      ('Vantage MSP','MSP','Staffing','Active',4,None,'https://vantage.example','+1 312 555 0199','233 Wacker Dr','Chicago','IL','USA','Net 60','VMS submission only. No direct manager outreach.','','MSP/VMS managed account.'),
    ]
    for c in companies:
        conn.execute('''INSERT INTO companies(name,company_type,industry,status,owner_user_id,parent_company_id,website,phone,address,city,state,country,billing_terms,submission_guidelines,discount_rule,notes,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',(*c,now))
    # users
    for email,pw,name,role,company_id,candidate_id in DEMO_USERS:
        conn.execute('INSERT INTO users(email,pass_hash,name,role,company_id,candidate_id,active,created_at) VALUES(?,?,?,?,?,?,1,?)',
                     (email,hash_password(pw),name,role,company_id,candidate_id,now))
    # contacts
    contacts=[
      (1,'Olivia','Chen','Director, Talent Acquisition','olivia.chen@northstar.example','+1 415 555 0150','Hiring Manager',4,'Active','Primary nursing program contact'),
      (1,'Carlos','Mendez','Nurse Staffing Manager','carlos.mendez@northstar.example','+1 415 555 0162','Timesheet Approver',4,'Active','Approves contingent workforce time'),
      (2,'Ethan','Cole','VP Engineering','ethan.cole@apex.example','+1 212 555 0144','Hiring Manager',4,'Active','Java platform hiring manager'),
      (3,'Samantha','Lee','Head of Data','samantha.lee@bluepeak.example','+1 512 555 0177','Hiring Manager',4,'Active','Data platform stakeholder'),
      (4,'Marcus','Stone','Program Manager','marcus.stone@vantage.example','+1 312 555 0120','MSP Contact',4,'Active','VMS program contact'),
    ]
    for c in contacts:
        conn.execute('INSERT INTO contacts(company_id,first_name,last_name,title,email,phone,role_type,owner_user_id,status,notes,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)',(*c,now))
    # candidates
    candidates=[
      ('Priya','Nair','candidate@atsone.local','+91 98765 10001','Pune','MH','India','411001','Data Engineer','Cloud Data','Senior Data Engineer','2026-10-05',42,55,'hour','Referral','Active',3,
       'Senior Data Engineer with 8 years experience in Python, SQL, Azure, Databricks, Microsoft Fabric, Spark, ETL, Airflow and data warehousing. Built medallion Bronze Silver Gold pipelines.','Production data engineer specializing in Fabric/Azure lakehouse platforms.',1,1,0,91),
      ('Arjun','Mehta','worker@atsone.local','+91 98765 10002','Bengaluru','KA','India','560001','Software Engineer','Backend','Senior Java Developer','2026-09-15',38,48,'hour','Database','Active',3,
       'Senior Java developer with Spring Boot, Kafka, AWS, PostgreSQL, microservices and banking domain experience. 9 years software engineering.','Backend engineer for high-throughput financial systems.',1,1,0,88),
      ('Sofia','Rodriguez','sofia.rn@example.com','+1 951 300 8580','Riverside','CA','USA','92501','RN','CVICU','Travel RN - CVICU','2026-10-01',70,85,'hour','Job Board','Active',3,
       'Registered Nurse RN with 7 years ICU/CVICU, BLS, ACLS and California RN license. Travel nurse and Cerner experience.','Experienced CVICU travel nurse.',1,1,0,95),
      ('Emma','Wilson','emma.rn@example.com','+1 904 866 0770','Jacksonville','FL','USA','32202','RN','Case Management','RN Case Manager','2026-10-10',62,75,'hour','Resume Harvest','Active',3,
       'Registered Nurse and case manager with 6 years nursing experience. Epic and utilization review. Compact RN license.','RN case management specialist.',1,1,0,84),
      ('Liam','Chen','liam.cloud@example.com','+1 512 555 0170','Austin','TX','USA','78701','Software Engineer','Cloud','Cloud Platform Engineer','2026-10-03',55,70,'hour','LinkedIn','Active',3,
       'Cloud engineer with AWS Kubernetes Terraform Go Python and SRE experience. 7 years.','Platform/SRE engineer.',1,1,0,86),
      ('Noah','Patel','noah.java@example.com','+1 201 555 0190','Jersey City','NJ','USA','07302','Software Engineer','Backend','Java Developer','2026-10-15',45,58,'hour','Referral','Active',3,
       'Java developer with 6 years Java, Spring Boot, Oracle, Kafka and banking. Mainframe exposure earlier in career.','Java engineer in banking.',1,1,0,79),
      ('Aisha','Khan','aisha.ba@example.com','+44 7700 900123','London','','UK','EC1A','Business Analyst','Finance','Senior Business Analyst','2026-10-06',50,65,'hour','Database','Active',3,
       'Business analyst with 9 years banking, finance, payments, SQL, Jira and regulatory change.','Financial services BA.',1,1,0,82),
      ('Miguel','Santos','miguel.de@example.com','+1 305 555 0119','Miami','FL','USA','33101','Data Engineer','Cloud Data','Data Engineer','2026-10-08',48,62,'hour','Job Board','Active',3,
       'Data engineer with 5 years Python SQL AWS Glue Redshift Airflow dbt and Spark.','AWS data engineer.',1,1,0,83),
    ]
    for c in candidates:
        conn.execute('''INSERT INTO candidates(first_name,last_name,email,phone,city,state,country,zip,profession,specialty,current_title,availability_date,pay_min,pay_max,desired_rate_type,source,status,owner_user_id,resume_text,summary,consent_sms,consent_email,do_not_contact,credibility_score,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',(*c,now,now))
    # skill helper
    skills={
      1:[('Python',7,1,'2026-09-01'),('SQL',8,1,'2026-09-01'),('Azure',5,1,'2026-09-01'),('Microsoft Fabric',3,1,'2026-09-01'),('Databricks',5,1,'2026-09-01'),('Spark',6,1,'2026-09-01'),('Airflow',4,1,'2026-07-01')],
      2:[('Java',9,1,'2026-09-01'),('Spring Boot',7,1,'2026-09-01'),('Kafka',5,1,'2026-09-01'),('AWS',6,1,'2026-09-01'),('PostgreSQL',5,1,'2026-09-01'),('Banking',5,1,'2026-09-01')],
      3:[('RN',7,1,'2026-08-01'),('CVICU',5,1,'2026-08-01'),('ICU',7,1,'2026-08-01'),('Cerner',4,1,'2026-08-01')],
      4:[('RN',6,1,'2026-08-15'),('Case Management',4,1,'2026-08-15'),('Epic',5,1,'2026-08-15'),('Utilization Review',4,1,'2026-08-15')],
      5:[('AWS',6,1,'2026-09-01'),('Kubernetes',5,1,'2026-09-01'),('Terraform',5,1,'2026-09-01'),('Go',4,1,'2026-09-01'),('Python',5,1,'2026-09-01'),('SRE',5,1,'2026-09-01')],
      6:[('Java',6,1,'2026-08-01'),('Spring Boot',5,1,'2026-08-01'),('Oracle',5,1,'2026-08-01'),('Kafka',3,1,'2026-08-01'),('Banking',4,1,'2026-08-01'),('Mainframe',1,0,'2019-01-01')],
      7:[('Business Analysis',9,1,'2026-09-01'),('Banking',7,1,'2026-09-01'),('Finance',8,1,'2026-09-01'),('Payments',5,1,'2026-09-01'),('SQL',4,1,'2026-09-01')],
      8:[('Python',5,1,'2026-09-01'),('SQL',5,1,'2026-09-01'),('AWS',4,1,'2026-09-01'),('Airflow',3,1,'2026-09-01'),('dbt',3,1,'2026-09-01'),('Spark',4,1,'2026-09-01')]
    }
    for cid, rows in skills.items():
        for s in rows: conn.execute('INSERT INTO candidate_skills(candidate_id,skill,years,recent,last_used) VALUES(?,?,?,?,?)',(cid,*s))
    exp=[
      (1,'Intelelctra Systems','Senior Data Engineer','2022-01-01',None,'Built Fabric/Azure medallion pipelines and data quality frameworks.','Python,SQL,Azure,Fabric,Databricks,Spark'),
      (1,'DataNova','Data Engineer','2018-06-01','2021-12-31','ETL pipelines and warehouse modernization.','Python,SQL,Airflow,Spark'),
      (2,'Apex Bank','Senior Java Developer','2021-01-01',None,'Microservices, event streaming and banking services.','Java,Spring Boot,Kafka,AWS,PostgreSQL,Banking'),
      (2,'TechOrbit','Java Developer','2017-05-01','2020-12-31','Enterprise Java APIs.','Java,Spring,Oracle'),
      (3,'Mercy Medical','Travel RN CVICU','2021-01-01',None,'CVICU bedside nursing.','RN,CVICU,ICU,Cerner'),
      (4,'Atlantic Health','RN Case Manager','2022-01-01',None,'Care coordination and utilization review.','RN,Case Management,Epic'),
    ]
    for r in exp: conn.execute('INSERT INTO candidate_experience(candidate_id,company,title,start_date,end_date,description,skills) VALUES(?,?,?,?,?,?,?)',r)
    licenses=[(3,'Registered Nurse RN','USA','CA','RN-CA-88731','Active','2027-12-31',1),(4,'Registered Nurse RN','USA','FL','RN-FL-19283','Active','2027-06-30',1)]
    for r in licenses: conn.execute('INSERT INTO candidate_licenses(candidate_id,license_type,country,state,license_number,status,expiry_date,documented) VALUES(?,?,?,?,?,?,?,?)',r)
    certs=[(3,'BLS','Active','2027-04-30',1),(3,'ACLS','Active','2027-02-28',1),(4,'BLS','Active','2027-05-31',1)]
    for r in certs: conn.execute('INSERT INTO candidate_certifications(candidate_id,name,status,expiry_date,documented) VALUES(?,?,?,?,?)',r)
    quals=[(1,'Degree','B.Tech','Computer Science'),(2,'Degree','B.E.','Computer Science'),(3,'Degree','BSN','Nursing'),(4,'Degree','BSN','Nursing'),(7,'Degree','MBA','Finance')]
    for r in quals: conn.execute('INSERT INTO candidate_qualifications(candidate_id,name,value,sub_value) VALUES(?,?,?,?)',r)
    attrs=[(1,'Top Candidate','Yes'),(1,'Fabric Certified','Yes'),(2,'Top Candidate','Yes'),(3,'Travel Ready','Yes'),(3,'Top Candidate','Yes'),(4,'Compact License','Yes'),(6,'Do Not Use Mainframe Roles','Yes')]
    for r in attrs: conn.execute('INSERT INTO candidate_attributes(candidate_id,attribute,value) VALUES(?,?,?)',r)
    # docs
    for cid,typ,name,status,expd in [(3,'License','California RN License','Verified','2027-12-31'),(3,'Certification','ACLS','Verified','2027-02-28'),(1,'Resume','Priya Nair Resume','Current',None),(2,'Resume','Arjun Mehta Resume','Current',None)]:
        conn.execute('INSERT INTO candidate_documents(candidate_id,doc_type,name,status,expiry_date,file_name,verified_by,verified_at,created_at) VALUES(?,?,?,?,?,?,?,?,?)',(cid,typ,name,status,expd,name.replace(' ','_')+'.pdf',2 if status=='Verified' else None,now if status=='Verified' else None,now))
    # jobs
    jobs=[
      ('26-00401','Travel RN - CVICU',1,1,3,4,'Open','Urgent','Contract',4,1,'Onsite','San Francisco','CA','USA','94103','2026-10-20','2027-01-20',72,82,105,120,'hour','RN','CVICU','RN:2:recent|CVICU:2:recent|Cerner:1:false','BSN','Registered Nurse RN:CA','BLS|ACLS','13-week travel assignment. Night shift. CVICU experience required.',None,'Direct',None),
      ('26-00402','Senior Java Platform Engineer',2,3,3,4,'Open','High','Contract',2,0,'Hybrid','New York','NY','USA','10005','2026-10-15','2027-09-30',50,62,85,105,'hour','Software Engineer','Backend','Java:5:recent|Spring Boot:4:recent|Kafka:2:false|Banking:2:false','Bachelors','','','Modernize banking microservices and event platform.',None,'Direct',None),
      ('26-00403','Senior Data Engineer - Fabric',3,4,3,4,'Open','High','Contract-to-Hire',1,0,'Remote','Austin','TX','USA','78701','2026-10-10','2027-04-10',48,65,88,110,'hour','Data Engineer','Cloud Data','Python:5:recent|SQL:5:recent|Microsoft Fabric:2:recent|Azure:3:false','Bachelors','','','Build Bronze/Silver/Gold data products on Microsoft Fabric and OneLake.',None,'Direct',None),
      ('26-00404','Cloud SRE',4,5,3,4,'Open','Normal','Contract',3,0,'Remote','Chicago','IL','USA','60601','2026-11-01','2027-10-31',55,72,95,120,'hour','Software Engineer','Cloud','AWS:4:recent|Kubernetes:3:recent|Terraform:3:recent|SRE:3:false','Bachelors','','','MSP-managed cloud reliability role.',None,'VMS','VMS-REQ-88341'),
      ('26-00388','RN Case Manager',1,1,3,4,'On Hold','Normal','Contract',2,1,'Hybrid','Oakland','CA','USA','94607','2026-10-15','2027-01-15',60,72,92,108,'hour','RN','Case Management','RN:3:recent|Case Management:2:recent','BSN','Registered Nurse RN:CA','BLS','Care management and utilization review.',None,'Direct',None),
    ]
    for j in jobs:
        conn.execute('''INSERT INTO jobs(job_no,title,company_id,contact_id,primary_recruiter_id,sales_user_id,status,priority,position_type,openings,filled,work_mode,city,state,country,zip,start_date,end_date,pay_min,pay_max,bill_min,bill_max,rate_type,profession,specialty,required_skills,required_qualifications,required_licenses,required_certifications,description,submission_guidelines_override,source,external_vms_id,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',(*j,now,now))
    # job users
    for jid in range(1,6):
        conn.execute('INSERT OR IGNORE INTO job_users(job_id,user_id,role_name) VALUES(?,?,?)',(jid,3,'Primary Recruiter'))
        conn.execute('INSERT OR IGNORE INTO job_users(job_id,user_id,role_name) VALUES(?,?,?)',(jid,4,'Sales'))
    # initial hotlists
    conn.execute('INSERT INTO hotlists(name,description,owner_user_id,visibility,mode,saved_search_json,created_at) VALUES(?,?,?,?,?,?,?)',('Priority Java Banking','Java candidates with banking background',3,'Team','dynamic',json.dumps({'require':[{'term':'Java','years':5,'recent':True},{'term':'Banking','years':2,'recent':False}]}),now))
    conn.execute('INSERT INTO hotlists(name,description,owner_user_id,visibility,mode,saved_search_json,created_at) VALUES(?,?,?,?,?,?,?)',('Travel RN - West Coast','Vetted west coast RN candidates',3,'Team','static',None,now))
    conn.execute('INSERT INTO hotlist_members(hotlist_id,candidate_id,status,note,added_by,created_at) VALUES(?,?,?,?,?,?)',(2,3,'Active','CVICU ready',3,now))
    # lifecycle data
    conn.execute('INSERT INTO interested_candidates(job_id,candidate_id,status,source,user_id,created_at,updated_at) VALUES(?,?,?,?,?,?,?)',(2,2,'qualified','Talent Search',3,now,now))
    conn.execute('INSERT INTO submissions(job_id,candidate_id,recruiter_id,status,client_rate,candidate_rate,availability,recruiter_summary,compliance_status,rtr_status,submitted_at,client_feedback,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(2,2,3,'interview',98,58,'2 weeks','Strong banking Java profile. Kafka and AWS production experience.','Complete','Signed',now,'Proceed to technical interview',now,now))
    conn.execute('INSERT INTO interviews(submission_id,interview_type,scheduled_at,timezone,status,location_or_link,interviewer,feedback,rating,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)',(1,'Video',(datetime.now()+timedelta(days=2)).replace(microsecond=0).isoformat(),'America/New_York','scheduled','https://meet.local/interview-001','Ethan Cole','',None,now))
    conn.execute('INSERT INTO starts(submission_id,start_date,status,cancellation_reason,created_at) VALUES(?,?,?,?,?)',(1,'2026-09-15','Confirmed',None,now))
    conn.execute('INSERT INTO assignments(start_id,candidate_id,job_id,company_id,status,start_date,end_date,worksite,cost_center,vms_id,approver_contact_id,bill_rate,pay_rate,overtime_rule,payroll_profile,po_number,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(1,2,2,2,'active','2026-09-15','2027-09-30','Apex NYC Hybrid','ENG-PLATFORM',None,3,98,58,'1.5x after 40h','W2-Hourly','PO-APEX-26091',now,now))
    week=(datetime.now().date()-timedelta(days=datetime.now().date().weekday())).isoformat()
    daily={'Mon':8,'Tue':8,'Wed':8,'Thu':8,'Fri':8,'Sat':0,'Sun':0}
    conn.execute('INSERT INTO timesheets(assignment_id,candidate_id,week_start,status,total_hours,regular_hours,overtime_hours,daily_json,submitted_at,approved_by,approved_at,rejection_note,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(1,2,week,'submitted',40,40,0,json.dumps(daily),now,None,None,None,now,now))
    conn.execute('INSERT INTO expenses(assignment_id,candidate_id,expense_date,category,amount,receipt_ref,status,description,approved_by,approved_at,rejection_note,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(1,2,today(),'Travel',45.50,'receipt-demo-001','submitted','Client-site transit',None,None,None,now))
    # onboarding
    conn.execute('INSERT INTO onboarding_packages(candidate_id,job_id,submission_id,package_name,status,assigned_by,due_date,created_at) VALUES(?,?,?,?,?,?,?,?)',(2,2,1,'Apex Contractor Start Package','in_progress',3,'2026-10-01',now))
    for typ,name,status in [('E-Sign','Right to Represent','Complete'),('Tax','W-4 / Tax Profile','Complete'),('Policy','Apex Security Policy','Pending'),('Identity','I-9 / Identity Verification','Pending')]:
        conn.execute('INSERT INTO onboarding_requirements(package_id,requirement_type,name,mandatory,status,completed_at,expiry_date,note) VALUES(?,?,?,?,?,?,?,?)',(1,typ,name,1,status,now if status=='Complete' else None,None,''))
    # assessments
    conn.execute('INSERT INTO assessments(candidate_id,job_id,title,assessment_type,status,score,max_score,invited_at,completed_at,notes) VALUES(?,?,?,?,?,?,?,?,?,?)',(2,2,'Java Platform Technical Screen','Technical','Completed',87,100,now,now,'Strong Spring/Kafka fundamentals'))
    conn.execute('INSERT INTO assessments(candidate_id,job_id,title,assessment_type,status,score,max_score,invited_at,completed_at,notes) VALUES(?,?,?,?,?,?,?,?,?,?)',(1,3,'Fabric Data Engineering Questionnaire','Questionnaire','Invited',None,100,now,None,''))
    # finance
    conn.execute('INSERT INTO purchase_orders(company_id,job_id,po_number,amount,start_date,end_date,status) VALUES(?,?,?,?,?,?,?)',(2,2,'PO-APEX-26091',450000,'2026-09-15','2027-09-30','Open'))
    conn.execute('INSERT INTO invoices(invoice_no,company_id,assignment_id,period_start,period_end,amount,tax,status,due_date,issued_at,paid_at,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',('INV-260901',2,1,'2026-09-15','2026-09-21',3920,0,'issued','2026-10-31',now,None,now))
    # VMS / suppliers
    conn.execute('INSERT INTO vms_accounts(name,platform,status,sync_mode,last_sync,notes) VALUES(?,?,?,?,?,?)',('Vantage MSP Production','Fieldglass','Active','Demo',now,'Demo connector: map external requisitions, submissions, workers, timesheets and expenses.'))
    conn.execute('INSERT INTO vms_mappings(vms_account_id,object_type,external_id,internal_id,external_status,internal_status,mapping_json,updated_at) VALUES(?,?,?,?,?,?,?,?)',(1,'Job','VMS-REQ-88341',4,'Released','Open',json.dumps({'title':'title','location':'city/state','rate':'bill_range'}),now))
    conn.execute('INSERT INTO suppliers(name,status,contact_name,email,phone,tier,notes) VALUES(?,?,?,?,?,?,?)',('TechSource Partners','Active','Nina Supplier','supplier@atsone.local','+1 646 555 0109','Preferred','Engineering supplier'))
    conn.execute('INSERT INTO supplier_releases(supplier_id,job_id,released_at,status,max_submissions) VALUES(?,?,?,?,?)',(1,4,now,'Open',3))
    # tasks/comms/automations/custom fields
    for e in [
      ('candidate',2,'Follow up after Apex interview',(datetime.now()+timedelta(days=3)).isoformat(),3,'Open','High'),
      ('job',1,'Submit 2 more CVICU candidates',(datetime.now()+timedelta(days=1)).isoformat(),3,'Open','High'),
      ('company',1,'Northstar Q4 staffing review',(datetime.now()+timedelta(days=5)).isoformat(),4,'Open','Normal')]:
        conn.execute('INSERT INTO tasks(entity_type,entity_id,title,due_at,owner_user_id,status,priority,created_at) VALUES(?,?,?,?,?,?,?,?)',(*e,now))
    conn.execute('INSERT INTO communications(entity_type,entity_id,channel,direction,subject,body,user_id,status,created_at) VALUES(?,?,?,?,?,?,?,?,?)',('candidate',2,'Email','Outbound','Interview confirmed','Apex interview scheduled. Calendar invite sent.',3,'Sent',now))
    conn.execute('INSERT INTO automations(name,trigger_name,condition_json,action_json,active,created_at) VALUES(?,?,?,?,?,?)',('Interview Reminder','interview.scheduled',json.dumps({'hours_before':24}),json.dumps({'channel':'email+sms','template':'Interview Reminder'}),1,now))
    conn.execute('INSERT INTO automations(name,trigger_name,condition_json,action_json,active,created_at) VALUES(?,?,?,?,?,?)',('Assignment End Redeploy','assignment.ending',json.dumps({'days_before':30}),json.dumps({'create_task':True,'campaign':'Redeployment'}),1,now))
    conn.execute('INSERT INTO custom_fields(entity_type,field_name,field_type,required,options_json,active) VALUES(?,?,?,?,?,?)',('candidate','Work Authorization','select',1,json.dumps(['US Citizen','Green Card','H1B','OPT','Other']),1))
    conn.execute('INSERT INTO custom_fields(entity_type,field_name,field_type,required,options_json,active) VALUES(?,?,?,?,?,?)',('job','Client Program','text',0,None,1))
    # sales pipeline, shifts, distribution and integration registry
    conn.execute('INSERT INTO leads(company_id,contact_id,title,source,status,owner_user_id,next_action,next_action_at,notes,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)',(3,4,'BluePeak Data Engineering Expansion','Referral','Qualified',4,'Schedule workforce planning call',(datetime.now()+timedelta(days=4)).isoformat(),'Potential Q4 data program',now))
    for op in [(1,1,'Northstar Travel Nursing Q4','Presentation',240000,60,4,'2026-10-20','Rate-card review','Open',''),(2,3,'Apex Platform Modernization','Negotiation',380000,75,4,'2026-10-10','MSA addendum','Open',''),(3,4,'BluePeak Data Platform','Qualified',190000,40,4,'2026-11-05','Technical intake','Open','')]:
        conn.execute('INSERT INTO opportunities(company_id,contact_id,name,stage,value,probability,owner_user_id,expected_close,next_activity,status,notes,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',(*op,now,now))
    for n in range(5):
        day=(datetime.now().date()+timedelta(days=n)).isoformat()
        conn.execute('INSERT INTO shifts(assignment_id,candidate_id,shift_date,start_time,end_time,location,status,created_at) VALUES(?,?,?,?,?,?,?,?)',(1,2,day,'09:00','17:00','Apex NYC Hybrid','Scheduled',now))
    for jid,ch,post,apps in [(1,'Career Site','CAREER-401',11),(1,'Indeed','IND-98401',7),(2,'Career Site','CAREER-402',9),(3,'LinkedIn-style Demo','LI-20403',14),(4,'VMS','VMS-REQ-88341',3)]:
        conn.execute('INSERT INTO job_distribution(job_id,channel,external_post_id,status,published_at,last_sync,applications) VALUES(?,?,?,?,?,?,?)',(jid,ch,post,'Published',now,now,apps))
    connectors=[('Job Boards','Career Site','Live','Connected',{},now,'Native career portal'),('VMS','Fieldglass','Demo','Configured',{},now,'Credentials required for live vendor API'),('VMS','Beeline','Demo','Configured',{},None,'Credentials required for live vendor API'),('Background','Background Check Provider','Demo','Configured',{},None,'Vendor account required'),('Payroll','Payroll / GL','Demo','Configured',{},None,'Mapping ready; credentials required'),('Communication','Email / SMS','Demo','Configured',{},None,'Local activity log works; provider credentials required')]
    for row in connectors:
        conn.execute('INSERT INTO integration_connectors(category,name,mode,status,config_json,last_sync,notes) VALUES(?,?,?,?,?,?,?)',(row[0],row[1],row[2],row[3],json.dumps(row[4]),row[5],row[6]))
    # initial audit
    audit(conn,1,'SEED','system',None,'Initial demo/working dataset created','127.0.0.1')

# ---------- talent search ----------
def norm(s): return re.sub(r'\s+',' ',(s or '').strip().lower())

def candidate_bundle(conn, cid):
    c=qone(conn,'SELECT * FROM candidates WHERE id=?',(cid,))
    if not c: return None
    c['skills']=qall(conn,'SELECT skill,years,recent,last_used FROM candidate_skills WHERE candidate_id=? ORDER BY years DESC',(cid,))
    c['experience']=qall(conn,'SELECT * FROM candidate_experience WHERE candidate_id=? ORDER BY COALESCE(end_date,"9999") DESC',(cid,))
    c['licenses']=qall(conn,'SELECT * FROM candidate_licenses WHERE candidate_id=?',(cid,))
    c['certifications']=qall(conn,'SELECT * FROM candidate_certifications WHERE candidate_id=?',(cid,))
    c['qualifications']=qall(conn,'SELECT * FROM candidate_qualifications WHERE candidate_id=?',(cid,))
    c['attributes']=qall(conn,'SELECT * FROM candidate_attributes WHERE candidate_id=?',(cid,))
    c['documents']=qall(conn,'SELECT * FROM candidate_documents WHERE candidate_id=? ORDER BY created_at DESC',(cid,))
    c['notes']=qall(conn,'SELECT n.*,u.name user_name FROM candidate_notes n LEFT JOIN users u ON u.id=n.user_id WHERE n.candidate_id=? ORDER BY n.created_at DESC LIMIT 50',(cid,))
    c['hotlists']=qall(conn,'SELECT h.id,h.name,hm.status,hm.note FROM hotlist_members hm JOIN hotlists h ON h.id=hm.hotlist_id WHERE hm.candidate_id=?',(cid,))
    c['submissions']=qall(conn,'SELECT s.*,j.job_no,j.title job_title,j.company_id FROM submissions s JOIN jobs j ON j.id=s.job_id WHERE s.candidate_id=? ORDER BY s.created_at DESC',(cid,))
    c['assignments']=qall(conn,'SELECT a.*,j.job_no,j.title job_title,co.name company_name FROM assignments a JOIN jobs j ON j.id=a.job_id LEFT JOIN companies co ON co.id=a.company_id WHERE a.candidate_id=? ORDER BY a.created_at DESC',(cid,))
    c['assessments']=qall(conn,'SELECT a.*,j.job_no,j.title job_title FROM assessments a LEFT JOIN jobs j ON j.id=a.job_id WHERE a.candidate_id=? ORDER BY a.invited_at DESC',(cid,))
    c['onboarding']=qall(conn,'SELECT p.*,j.job_no,j.title job_title FROM onboarding_packages p LEFT JOIN jobs j ON j.id=p.job_id WHERE p.candidate_id=? ORDER BY p.created_at DESC',(cid,))
    c['tasks']=qall(conn,"SELECT * FROM tasks WHERE entity_type='candidate' AND entity_id=? ORDER BY due_at",(cid,))
    c['communications']=qall(conn,"SELECT * FROM communications WHERE entity_type='candidate' AND entity_id=? ORDER BY created_at DESC LIMIT 50",(cid,))
    return c

def skill_match(bundle, term, min_years=0, recent=False, mapping=True):
    t=norm(term)
    if mapping:
        aliases=set(SYNONYMS.get(t,[t]))
        aliases.add(t)
        # Reverse synonym resolution: searching for "Amazon Web Services"
        # maps to a stored "AWS" skill and vice versa.
        for key,vals in SYNONYMS.items():
            normvals={norm(x) for x in vals}
            if t==norm(key) or t in normvals:
                aliases.add(norm(key)); aliases.update(normvals)
        aliases=list(aliases)
    else:
        aliases=[t]
    best=0; recent_ok=False; found=False
    for s in bundle.get('skills',[]):
        sn=norm(s['skill'])
        if any(a==sn or a in sn or sn in a for a in aliases):
            found=True
            best=max(best,float(s.get('years') or 0)); recent_ok=recent_ok or bool(s.get('recent'))
    # fallback text match for zero-year keyword filters
    if min_years <= 0 and not found:
        text=norm((bundle.get('resume_text') or '')+' '+(bundle.get('current_title') or '')+' '+(bundle.get('profession') or '')+' '+(bundle.get('specialty') or ''))
        if any(a in text for a in aliases): found=True; best=0.01; recent_ok=True
    ok=found and best >= float(min_years or 0) and (not recent or recent_ok)
    return ok, best

def eval_boolean(bundle, expression, mapping=True):
    expr=(expression or '').strip()
    if not expr: return True
    conditions={}
    pattern=re.compile(r'(?P<term>"[^"]+"|[A-Za-z0-9_+#.\-/]+)\s+(?:(?P<recent>RECENT)\s+)?OVER\s+(?P<years>\d+(?:\.\d+)?)\s+YRS',re.I)
    def repl(m):
        key=f'__COND{len(conditions)}__'; conditions[key]=(m.group('term').strip('"'),float(m.group('years')),bool(m.group('recent'))); return key
    expr=pattern.sub(repl,expr)
    tokens=re.findall(r'__COND\d+__|\(|\)|\bAND\b|\bOR\b|\bNOT\b|"[^"]+"|[^\s()]+',expr,flags=re.I)
    pos=0
    def term_value(tok):
        if tok in conditions:
            t,y,r=conditions[tok]; return skill_match(bundle,t,y,r,mapping)[0]
        term=tok.strip('"')
        ok,_=skill_match(bundle,term,0,False,mapping); return ok
    def parse_primary():
        nonlocal pos
        if pos>=len(tokens): return True
        tok=tokens[pos]
        if tok.upper()=='NOT': pos+=1; return not parse_primary()
        if tok=='(':
            pos+=1; v=parse_or()
            if pos < len(tokens) and tokens[pos]==')': pos+=1
            return v
        pos+=1; return term_value(tok)
    def parse_and():
        nonlocal pos
        v=parse_primary()
        while pos<len(tokens) and tokens[pos].upper()=='AND': pos+=1; v = v and parse_primary()
        return v
    def parse_or():
        nonlocal pos
        v=parse_and()
        while pos<len(tokens) and tokens[pos].upper()=='OR': pos+=1; v = v or parse_and()
        return v
    try: return bool(parse_or())
    except Exception: return False

def check_require_sequence(bundle, rows, mapping=True):
    rows=[r for r in (rows or []) if (r.get('term') or '').strip()]
    if not rows: return True,0
    value=None; points=0
    for i,r in enumerate(rows):
        ok,best=skill_match(bundle,r.get('term',''),float(r.get('years') or 0),bool(r.get('recent')),mapping)
        if ok: points += 15 + min(best,10)
        if value is None: value=ok
        else:
            op=(r.get('operator') or 'AND').upper(); value = (value or ok) if op=='OR' else (value and ok)
    return bool(value),points

def perform_search(conn, crit):
    candidates=qall(conn,"SELECT id FROM candidates WHERE status!='Archived'")
    out=[]; mapping=not bool(crit.get('without_mapping'))
    for row in candidates:
        b=candidate_bundle(conn,row['id']); score=0; reasons=[]
        if crit.get('profession'):
            if norm(crit['profession']) not in norm(b.get('profession')): continue
            score+=14; reasons.append('profession')
        if crit.get('specialty'):
            if norm(crit['specialty']) not in norm(b.get('specialty')): continue
            score+=12; reasons.append('specialty')
        title=crit.get('title','').strip()
        if title and norm(title) not in norm(b.get('current_title')): continue
        if title: score+=8; reasons.append('title')
        # license filters all required
        failed=False
        for lf in crit.get('licenses') or []:
            matched=False
            for lic in b.get('licenses',[]):
                if lf.get('type') and norm(lf['type']) not in norm(lic.get('license_type')): continue
                if lf.get('country') and norm(lf['country']) != norm(lic.get('country')): continue
                if lf.get('state') and norm(lf['state']) != norm(lic.get('state')): continue
                if lf.get('active') and norm(lic.get('status'))!='active': continue
                if lf.get('documented') and not lic.get('documented'): continue
                if lf.get('expiry_after') and (not lic.get('expiry_date') or lic['expiry_date'] < lf['expiry_after']): continue
                matched=True; break
            if not matched: failed=True; break
            score+=12
        if failed: continue
        for cf in crit.get('certifications') or []:
            matched=False
            for cert in b.get('certifications',[]):
                if cf.get('name') and norm(cf['name']) not in norm(cert.get('name')): continue
                if cf.get('active') and norm(cert.get('status'))!='active': continue
                if cf.get('documented') and not cert.get('documented'): continue
                if cf.get('expiry_after') and (not cert.get('expiry_date') or cert['expiry_date'] < cf['expiry_after']): continue
                matched=True; break
            if not matched: failed=True; break
            score+=10
        if failed: continue
        qual=crit.get('qualification','').strip()
        if qual:
            qtext=' '.join((x.get('name','')+' '+x.get('value','')+' '+(x.get('sub_value') or '')) for x in b.get('qualifications',[]))
            if norm(qual) not in norm(qtext): continue
            score+=8
        attrs=[norm(x) for x in (crit.get('attributes') or []) if x]
        if attrs:
            at=[norm(x.get('attribute')) for x in b.get('attributes',[])]
            if not all(any(a in x for x in at) for a in attrs): continue
            score+=8*len(attrs)
        req_ok,req_score=check_require_sequence(b,crit.get('require'),mapping)
        if not req_ok: continue
        score+=req_score
        for ex in crit.get('exclude') or []:
            term=ex.get('term') if isinstance(ex,dict) else ex
            ok,_=skill_match(b,term,0,False,mapping)
            if ok: failed=True; break
        if failed: continue
        state=(crit.get('state') or '').strip()
        if state and norm(state)!=norm(b.get('state')): continue
        avail=crit.get('available_before')
        if avail and b.get('availability_date') and b['availability_date']>avail: continue
        pay_min=crit.get('pay_min'); pay_max=crit.get('pay_max')
        if pay_min not in (None,'') and (b.get('pay_max') or 0) < float(pay_min): continue
        if pay_max not in (None,'') and (b.get('pay_min') or 0) > float(pay_max): continue
        raw=crit.get('raw_boolean','').strip()
        if raw and not eval_boolean(b,raw,mapping): continue
        if raw: score+=20; reasons.append('boolean')
        # recency and credibility relevance
        score += min((b.get('credibility_score') or 0)/10,10)
        b['relevance']=round(min(score,99),1)
        b['match_reasons']=reasons
        out.append(b)
    out.sort(key=lambda x:(-x['relevance'],x['last_name'],x['first_name']))
    return out

def compile_criteria(c):
    bits=[]
    if c.get('profession'): bits.append(f"PROFESSION [ {c['profession']} IS {c.get('specialty') or 'ANY'} ]")
    for l in c.get('licenses') or []:
        t=l.get('type') or 'LICENSE'; st=l.get('state') or 'ANY'; bits.append(f'LICENCES=("{t}" ST IN {{{st}}})')
    for cert in c.get('certifications') or []: bits.append(f'CERTIFICATION [ {cert.get("name")} ]')
    for i,r in enumerate(c.get('require') or []):
        if not r.get('term'): continue
        op='' if i==0 else ' '+(r.get('operator') or 'AND')+' '
        recent=' RECENT' if r.get('recent') else ''
        yrs=f" OVER {r.get('years')} YRS" if float(r.get('years') or 0)>0 else ''
        bits.append(op+f"({r['term']}{recent}{yrs})")
    for e in c.get('exclude') or []:
        t=e.get('term') if isinstance(e,dict) else e
        if t: bits.append(f'NOT ({t})')
    if c.get('title'): bits.append(f'TITLE [ {c["title"]} ]')
    if c.get('raw_boolean'): bits.append('BOOLEAN [ '+c['raw_boolean']+' ]')
    return ' '.join(bits) or 'ALL ACTIVE CANDIDATES'

# ---------- handler ----------
class Handler(BaseHTTPRequestHandler):
    server_version='ATSOne/2.0'
    def log_message(self, fmt, *args):
        if getattr(self.server,'quiet',False): return
        sys.stderr.write('%s - - [%s] %s\n' % (self.address_string(),self.log_date_time_string(),fmt%args))
    def _json(self, data, status=200, headers=None):
        raw=json.dumps(data,ensure_ascii=False,default=str).encode()
        self.send_response(status); self.send_header('Content-Type','application/json; charset=utf-8'); self.send_header('Content-Length',str(len(raw)))
        self.send_header('Cache-Control','no-store')
        if headers:
            for k,v in headers.items(): self.send_header(k,v)
        self.end_headers(); self.wfile.write(raw)
    def _body(self):
        n=int(self.headers.get('Content-Length','0') or 0); raw=self.rfile.read(n) if n else b''
        if not raw: return {}
        try: return json.loads(raw.decode())
        except Exception: return {}
    def _cookies(self):
        out={}
        for part in self.headers.get('Cookie','').split(';'):
            if '=' in part:
                k,v=part.strip().split('=',1); out[k]=v
        return out
    def _user(self, conn):
        tok=self._cookies().get('ats_session') or self.headers.get('X-Session-Token')
        if not tok: return None
        return qone(conn,'''SELECT u.* FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token=? AND s.expires_at>? AND u.active=1''',(tok,utcnow()))
    def _need(self, conn, perm=None, roles=None):
        u=self._user(conn)
        if not u: self._json({'error':'Authentication required'},401); return None
        if roles and u['role'] not in roles and u['role']!='admin': self._json({'error':'Permission denied'},403); return None
        if perm:
            ps=ROLE_PERMISSIONS.get(u['role'],set())
            if '*' not in ps and perm not in ps: self._json({'error':'Permission denied'},403); return None
        return u
    def _serve_static(self,path):
        if path=='/': path='/index.html'
        rel=urllib.parse.unquote(path.split('?',1)[0]).lstrip('/')
        fp=(WEB_DIR/rel).resolve()
        if not str(fp).startswith(str(WEB_DIR.resolve())) or not fp.is_file():
            fp=WEB_DIR/'index.html'
        raw=fp.read_bytes(); ctype=mimetypes.guess_type(str(fp))[0] or 'application/octet-stream'
        self.send_response(200); self.send_header('Content-Type',ctype); self.send_header('Content-Length',str(len(raw)))
        self.send_header('Cache-Control','no-cache' if fp.name=='index.html' else 'public, max-age=3600'); self.end_headers(); self.wfile.write(raw)
    def do_GET(self):
        p=urllib.parse.urlparse(self.path); path=p.path; qs=urllib.parse.parse_qs(p.query)
        if not path.startswith('/api/'): return self._serve_static(path)
        conn=db()
        try:
            if path=='/api/health': return self._json({'ok':True,'app':APP_NAME,'version':APP_VERSION,'db':str(DB_PATH),'persistence':'supabase-storage' if REMOTE_PERSISTENCE_ENABLED else 'local-sqlite'})
            if path=='/api/me':
                u=self._need(conn)
                if u: u.pop('pass_hash',None); return self._json(u)
                return
            u=self._need(conn)
            if not u: return
            if path=='/api/dashboard': return self._json(self.dashboard(conn,u))
            if path=='/api/candidates':
                if u['role'] not in INTERNAL_ROLES: return self._json({'error':'Permission denied'},403)
                term=(qs.get('q') or [''])[0].strip(); sql="SELECT * FROM candidates WHERE 1=1"; params=[]
                if term: sql+=" AND (first_name||' '||last_name LIKE ? OR email LIKE ? OR phone LIKE ? OR current_title LIKE ? OR profession LIKE ?)"; params += ['%'+term+'%']*5
                sql+=' ORDER BY updated_at DESC LIMIT 500'; return self._json(qall(conn,sql,params))
            m=re.fullmatch(r'/api/candidates/(\d+)',path)
            if m:
                cid=int(m.group(1));
                if u['role'] in ('candidate','worker') and u.get('candidate_id')!=cid: return self._json({'error':'Permission denied'},403)
                b=candidate_bundle(conn,cid); return self._json(b or {'error':'Not found'},200 if b else 404)
            if path=='/api/hotlists':
                rows=qall(conn,'''SELECT h.*,u.name owner_name,(SELECT COUNT(*) FROM hotlist_members hm WHERE hm.hotlist_id=h.id) member_count FROM hotlists h LEFT JOIN users u ON u.id=h.owner_user_id ORDER BY h.created_at DESC''')
                return self._json(rows)
            m=re.fullmatch(r'/api/hotlists/(\d+)',path)
            if m:
                hid=int(m.group(1)); h=qone(conn,'SELECT * FROM hotlists WHERE id=?',(hid,));
                if not h: return self._json({'error':'Not found'},404)
                h['members']=qall(conn,'''SELECT hm.*,c.first_name,c.last_name,c.current_title,c.city,c.state,c.email FROM hotlist_members hm JOIN candidates c ON c.id=hm.candidate_id WHERE hm.hotlist_id=? ORDER BY hm.created_at DESC''',(hid,))
                if h.get('mode')=='dynamic' and h.get('saved_search_json'):
                    try: h['dynamic_results']=perform_search(conn,json.loads(h['saved_search_json']))
                    except Exception: h['dynamic_results']=[]
                return self._json(h)
            if path=='/api/jobs':
                sql='''SELECT j.*,co.name company_name,ct.first_name||' '||ct.last_name contact_name,u.name recruiter_name,
                 (SELECT COUNT(*) FROM submissions s WHERE s.job_id=j.id) submission_count,
                 (SELECT COUNT(*) FROM interested_candidates i WHERE i.job_id=j.id) interested_count
                 FROM jobs j LEFT JOIN companies co ON co.id=j.company_id LEFT JOIN contacts ct ON ct.id=j.contact_id LEFT JOIN users u ON u.id=j.primary_recruiter_id WHERE 1=1'''; params=[]
                if u['role']=='client': sql+=' AND j.company_id=?'; params.append(u['company_id'])
                if u['role']=='supplier': sql+=' AND j.id IN (SELECT job_id FROM supplier_releases WHERE supplier_id=1 AND status="Open")'
                sql+=' ORDER BY CASE j.status WHEN "Open" THEN 0 ELSE 1 END,j.created_at DESC'; return self._json(qall(conn,sql,params))
            m=re.fullmatch(r'/api/jobs/(\d+)',path)
            if m:
                jid=int(m.group(1)); j=qone(conn,'''SELECT j.*,co.name company_name,ct.first_name||' '||ct.last_name contact_name,co.submission_guidelines company_submission_guidelines FROM jobs j LEFT JOIN companies co ON co.id=j.company_id LEFT JOIN contacts ct ON ct.id=j.contact_id WHERE j.id=?''',(jid,))
                if not j: return self._json({'error':'Not found'},404)
                if u['role']=='client' and j.get('company_id')!=u.get('company_id'): return self._json({'error':'Permission denied'},403)
                if u['role']=='supplier':
                    rel=qone(conn,"SELECT 1 ok FROM supplier_releases WHERE supplier_id=1 AND job_id=? AND status='Open'",(jid,))
                    if not rel: return self._json({'error':'Permission denied'},403)
                if u['role'] in ('candidate','worker') and j.get('status')!='Open': return self._json({'error':'Permission denied'},403)
                j['interested']=qall(conn,'''SELECT i.*,c.first_name,c.last_name,c.current_title,c.email FROM interested_candidates i JOIN candidates c ON c.id=i.candidate_id WHERE i.job_id=? ORDER BY i.updated_at DESC''',(jid,))
                j['submissions']=qall(conn,'''SELECT s.*,c.first_name,c.last_name,c.current_title,c.email FROM submissions s JOIN candidates c ON c.id=s.candidate_id WHERE s.job_id=? ORDER BY s.updated_at DESC''',(jid,))
                j['users']=qall(conn,'''SELECT ju.*,u.name,u.email FROM job_users ju JOIN users u ON u.id=ju.user_id WHERE ju.job_id=?''',(jid,))
                j['supplier_releases']=qall(conn,'''SELECT sr.*,s.name supplier_name FROM supplier_releases sr JOIN suppliers s ON s.id=sr.supplier_id WHERE sr.job_id=?''',(jid,))
                return self._json(j)
            if path=='/api/companies':
                if u['role'] not in INTERNAL_ROLES: return self._json({'error':'Permission denied'},403)
                return self._json(qall(conn,'SELECT c.*,(SELECT COUNT(*) FROM contacts x WHERE x.company_id=c.id) contact_count,(SELECT COUNT(*) FROM jobs j WHERE j.company_id=c.id) job_count FROM companies c ORDER BY c.name'))
            if path=='/api/contacts': return self._json(qall(conn,'SELECT ct.*,co.name company_name FROM contacts ct LEFT JOIN companies co ON co.id=ct.company_id ORDER BY ct.last_name,ct.first_name'))
            if path=='/api/leads': return self._json(qall(conn,'''SELECT l.*,co.name company_name,ct.first_name||' '||ct.last_name contact_name,u.name owner_name FROM leads l LEFT JOIN companies co ON co.id=l.company_id LEFT JOIN contacts ct ON ct.id=l.contact_id LEFT JOIN users u ON u.id=l.owner_user_id ORDER BY l.created_at DESC'''))
            if path=='/api/opportunities': return self._json(qall(conn,'''SELECT o.*,co.name company_name,ct.first_name||' '||ct.last_name contact_name,u.name owner_name FROM opportunities o LEFT JOIN companies co ON co.id=o.company_id LEFT JOIN contacts ct ON ct.id=o.contact_id LEFT JOIN users u ON u.id=o.owner_user_id ORDER BY CASE o.stage WHEN 'Negotiation' THEN 1 WHEN 'Presentation' THEN 2 WHEN 'Qualified' THEN 3 ELSE 4 END,o.expected_close'''))
            if path=='/api/shifts':
                sql='''SELECT sh.*,c.first_name,c.last_name,j.title job_title,co.name company_name FROM shifts sh JOIN candidates c ON c.id=sh.candidate_id LEFT JOIN assignments a ON a.id=sh.assignment_id LEFT JOIN jobs j ON j.id=a.job_id LEFT JOIN companies co ON co.id=a.company_id WHERE 1=1'''; params=[]
                if u['role']=='worker': sql+=' AND sh.candidate_id=?';params.append(u['candidate_id'])
                sql+=' ORDER BY sh.shift_date,sh.start_time';return self._json(qall(conn,sql,params))
            if path=='/api/job-distribution': return self._json(qall(conn,'''SELECT d.*,j.job_no,j.title job_title FROM job_distribution d JOIN jobs j ON j.id=d.job_id ORDER BY d.published_at DESC'''))
            if path=='/api/integrations': return self._json(qall(conn,'SELECT * FROM integration_connectors ORDER BY category,name'))
            if path=='/api/submissions':
                sql='''SELECT s.*,c.first_name,c.last_name,c.current_title,j.job_no,j.title job_title,co.name company_name FROM submissions s JOIN candidates c ON c.id=s.candidate_id JOIN jobs j ON j.id=s.job_id LEFT JOIN companies co ON co.id=j.company_id WHERE 1=1'''; params=[]
                if u['role']=='client': sql+=' AND j.company_id=?'; params.append(u['company_id'])
                if u['role']=='candidate': sql+=' AND s.candidate_id=?'; params.append(u['candidate_id'])
                sql+=' ORDER BY s.updated_at DESC'; return self._json(qall(conn,sql,params))
            if path=='/api/interviews':
                sql='''SELECT i.*,s.job_id,s.candidate_id,c.first_name,c.last_name,j.job_no,j.title job_title,co.name company_name FROM interviews i JOIN submissions s ON s.id=i.submission_id JOIN candidates c ON c.id=s.candidate_id JOIN jobs j ON j.id=s.job_id LEFT JOIN companies co ON co.id=j.company_id WHERE 1=1'''; params=[]
                if u['role']=='client': sql+=' AND j.company_id=?'; params.append(u['company_id'])
                if u['role']=='candidate': sql+=' AND c.id=?'; params.append(u['candidate_id'])
                sql+=' ORDER BY i.scheduled_at DESC'; return self._json(qall(conn,sql,params))
            if path=='/api/assessments': return self._json(qall(conn,'''SELECT a.*,c.first_name,c.last_name,j.job_no,j.title job_title FROM assessments a JOIN candidates c ON c.id=a.candidate_id LEFT JOIN jobs j ON j.id=a.job_id ORDER BY a.invited_at DESC'''))
            if path=='/api/onboarding':
                sql='''SELECT p.*,c.first_name,c.last_name,j.job_no,j.title job_title,(SELECT COUNT(*) FROM onboarding_requirements r WHERE r.package_id=p.id) req_count,(SELECT COUNT(*) FROM onboarding_requirements r WHERE r.package_id=p.id AND lower(r.status)='complete') complete_count FROM onboarding_packages p JOIN candidates c ON c.id=p.candidate_id LEFT JOIN jobs j ON j.id=p.job_id WHERE 1=1'''; params=[]
                if u['role'] in ('candidate','worker'): sql+=' AND p.candidate_id=?'; params.append(u['candidate_id'])
                sql+=' ORDER BY p.created_at DESC'; return self._json(qall(conn,sql,params))
            m=re.fullmatch(r'/api/onboarding/(\d+)',path)
            if m:
                pid=int(m.group(1)); p=qone(conn,'SELECT * FROM onboarding_packages WHERE id=?',(pid,));
                if not p:return self._json({'error':'Not found'},404)
                p['requirements']=qall(conn,'SELECT * FROM onboarding_requirements WHERE package_id=? ORDER BY id',(pid,)); return self._json(p)
            if path=='/api/assignments':
                sql='''SELECT a.*,c.first_name,c.last_name,j.job_no,j.title job_title,co.name company_name,ct.first_name||' '||ct.last_name approver_name FROM assignments a JOIN candidates c ON c.id=a.candidate_id JOIN jobs j ON j.id=a.job_id LEFT JOIN companies co ON co.id=a.company_id LEFT JOIN contacts ct ON ct.id=a.approver_contact_id WHERE 1=1'''; params=[]
                if u['role']=='worker': sql+=' AND a.candidate_id=?'; params.append(u['candidate_id'])
                if u['role']=='client': sql+=' AND a.company_id=?'; params.append(u['company_id'])
                sql+=' ORDER BY a.updated_at DESC'; return self._json(qall(conn,sql,params))
            if path=='/api/timesheets':
                sql='''SELECT t.*,c.first_name,c.last_name,j.title job_title,co.name company_name,a.bill_rate,a.pay_rate FROM timesheets t JOIN assignments a ON a.id=t.assignment_id JOIN candidates c ON c.id=t.candidate_id JOIN jobs j ON j.id=a.job_id LEFT JOIN companies co ON co.id=a.company_id WHERE 1=1'''; params=[]
                if u['role']=='worker': sql+=' AND t.candidate_id=?';params.append(u['candidate_id'])
                if u['role'] in ('client','approver'): sql+=' AND a.company_id=?';params.append(u['company_id'])
                sql+=' ORDER BY t.week_start DESC'; return self._json(qall(conn,sql,params))
            if path=='/api/expenses':
                sql='''SELECT e.*,c.first_name,c.last_name,j.title job_title,co.name company_name FROM expenses e JOIN assignments a ON a.id=e.assignment_id JOIN candidates c ON c.id=e.candidate_id JOIN jobs j ON j.id=a.job_id LEFT JOIN companies co ON co.id=a.company_id WHERE 1=1''';params=[]
                if u['role']=='worker': sql+=' AND e.candidate_id=?';params.append(u['candidate_id'])
                if u['role'] in ('client','approver'): sql+=' AND a.company_id=?';params.append(u['company_id'])
                sql+=' ORDER BY e.expense_date DESC'; return self._json(qall(conn,sql,params))
            if path=='/api/invoices':
                if u['role'] not in ('admin','finance','teamlead'): return self._json({'error':'Permission denied'},403)
                return self._json(qall(conn,'''SELECT i.*,co.name company_name,c.first_name,c.last_name,j.title job_title FROM invoices i LEFT JOIN companies co ON co.id=i.company_id LEFT JOIN assignments a ON a.id=i.assignment_id LEFT JOIN candidates c ON c.id=a.candidate_id LEFT JOIN jobs j ON j.id=a.job_id ORDER BY i.created_at DESC'''))
            if path=='/api/purchase-orders': return self._json(qall(conn,'SELECT p.*,co.name company_name,j.job_no,j.title job_title FROM purchase_orders p LEFT JOIN companies co ON co.id=p.company_id LEFT JOIN jobs j ON j.id=p.job_id ORDER BY p.id DESC'))
            if path=='/api/vms':
                return self._json({'accounts':qall(conn,'SELECT * FROM vms_accounts ORDER BY id'),'mappings':qall(conn,'SELECT vm.*,va.name account_name FROM vms_mappings vm LEFT JOIN vms_accounts va ON va.id=vm.vms_account_id ORDER BY vm.updated_at DESC')})
            if path=='/api/suppliers':
                rows=qall(conn,'SELECT s.*,(SELECT COUNT(*) FROM supplier_releases sr WHERE sr.supplier_id=s.id) released_job_count FROM suppliers s ORDER BY s.name'); return self._json(rows)
            if path=='/api/communications': return self._json(qall(conn,'SELECT c.*,u.name user_name FROM communications c LEFT JOIN users u ON u.id=c.user_id ORDER BY c.created_at DESC LIMIT 500'))
            if path=='/api/tasks':
                return self._json(qall(conn,'SELECT t.*,u.name owner_name FROM tasks t LEFT JOIN users u ON u.id=t.owner_user_id ORDER BY CASE t.status WHEN "Open" THEN 0 ELSE 1 END,t.due_at'))
            if path=='/api/automations': return self._json(qall(conn,'SELECT * FROM automations ORDER BY id DESC'))
            if path=='/api/users':
                if u['role']!='admin': return self._json({'error':'Permission denied'},403)
                return self._json(qall(conn,'SELECT id,email,name,role,company_id,candidate_id,active,created_at FROM users ORDER BY name'))
            if path=='/api/custom-fields': return self._json(qall(conn,'SELECT * FROM custom_fields ORDER BY entity_type,field_name'))
            if path=='/api/audit':
                if u['role'] not in ('admin','teamlead'): return self._json({'error':'Permission denied'},403)
                return self._json(qall(conn,'SELECT a.*,u.name user_name,u.email FROM audit_log a LEFT JOIN users u ON u.id=a.user_id ORDER BY a.id DESC LIMIT 1000'))
            if path=='/api/reports/summary': return self._json(self.report_summary(conn,u))
            if path=='/api/reference':
                if u['role'] in INTERNAL_ROLES:
                    return self._json({'companies':qall(conn,'SELECT id,name FROM companies ORDER BY name'),'contacts':qall(conn,"SELECT id,company_id,first_name||' '||last_name name FROM contacts ORDER BY last_name"),'users':qall(conn,'SELECT id,name,role FROM users WHERE active=1 ORDER BY name'),'candidates':qall(conn,"SELECT id,first_name||' '||last_name name,current_title FROM candidates ORDER BY last_name"),'jobs':qall(conn,'SELECT id,job_no,title,company_id,status FROM jobs ORDER BY created_at DESC'),'suppliers':qall(conn,'SELECT id,name FROM suppliers ORDER BY name')})
                if u['role'] in ('client','approver'):
                    co=u.get('company_id')
                    return self._json({'companies':qall(conn,'SELECT id,name FROM companies WHERE id=?',(co,)),'contacts':qall(conn,"SELECT id,company_id,first_name||' '||last_name name FROM contacts WHERE company_id=? ORDER BY last_name",(co,)),'users':[],'candidates':[],'jobs':qall(conn,'SELECT id,job_no,title,company_id,status FROM jobs WHERE company_id=? ORDER BY created_at DESC',(co,)),'suppliers':[]})
                return self._json({'companies':[],'contacts':[],'users':[],'candidates':[],'jobs':[],'suppliers':[]})
            return self._json({'error':'API endpoint not found'},404)
        finally: conn.close()
    def do_POST(self):
        p=urllib.parse.urlparse(self.path); path=p.path; data=self._body(); conn=db()
        try:
            if path=='/api/login':
                email=(data.get('email') or '').strip().lower(); pw=data.get('password') or ''
                u=qone(conn,'SELECT * FROM users WHERE lower(email)=? AND active=1',(email,))
                if not u or not verify_password(pw,u['pass_hash']): return self._json({'error':'Invalid email or password'},401)
                tok=secrets.token_urlsafe(32); exp=(datetime.now(timezone.utc)+timedelta(hours=18)).replace(microsecond=0).isoformat()
                conn.execute('INSERT INTO sessions(token,user_id,expires_at,created_at) VALUES(?,?,?,?)',(tok,u['id'],exp,utcnow())); audit(conn,u['id'],'LOGIN','user',u['id'],'Successful login',self.client_address[0]);conn.commit();u.pop('pass_hash',None)
                return self._json({'user':u},200,{'Set-Cookie':f'ats_session={tok}; Path=/; HttpOnly; SameSite=Lax; Max-Age=64800' + ('; Secure' if os.environ.get('RENDER') or os.environ.get('FORCE_SECURE_COOKIE')=='1' else '')})
            if path=='/api/logout':
                tok=self._cookies().get('ats_session');
                if tok: conn.execute('DELETE FROM sessions WHERE token=?',(tok,));conn.commit()
                return self._json({'ok':True},200,{'Set-Cookie':'ats_session=; Path=/; Max-Age=0; HttpOnly; SameSite=Lax'})
            u=self._need(conn)
            if not u:return
            if path=='/api/search/talent':
                if u['role'] not in ('admin','teamlead','recruiter','sales','hr'): return self._json({'error':'Permission denied'},403)
                res=perform_search(conn,data); criteria=compile_criteria(data); audit(conn,u['id'],'SEARCH','candidate',None,criteria,self.client_address[0]);conn.commit()
                return self._json({'criteria':criteria,'duration_ms':0,'count':len(res),'results':res})
            if path=='/api/candidates':
                if u['role'] not in ('admin','teamlead','recruiter','hr'): return self._json({'error':'Permission denied'},403)
                required=['first_name','last_name'];
                if any(not data.get(x) for x in required): return self._json({'error':'first_name and last_name required'},400)
                now=utcnow(); cols=['first_name','last_name','email','phone','city','state','country','zip','profession','specialty','current_title','availability_date','pay_min','pay_max','desired_rate_type','source','status','owner_user_id','resume_text','summary']
                vals=[data.get(c) for c in cols]; vals[6]=vals[6] or 'USA'; vals[14]=vals[14] or 'hour'; vals[15]=vals[15] or 'Manual'; vals[16]=vals[16] or 'Active'; vals[17]=vals[17] or u['id']
                cur=conn.execute('INSERT INTO candidates('+','.join(cols)+',created_at,updated_at) VALUES('+','.join(['?']*(len(cols)+2))+')',(*vals,now,now)); cid=cur.lastrowid
                for s in data.get('skills') or []:
                    conn.execute('INSERT OR REPLACE INTO candidate_skills(candidate_id,skill,years,recent,last_used) VALUES(?,?,?,?,?)',(cid,s.get('skill'),float(s.get('years') or 0),1 if s.get('recent') else 0,s.get('last_used')))
                audit(conn,u['id'],'CREATE','candidate',cid,f"{data.get('first_name')} {data.get('last_name')}",self.client_address[0]); conn.commit(); return self._json(candidate_bundle(conn,cid),201)
            m=re.fullmatch(r'/api/candidates/(\d+)/notes',path)
            if m:
                if u['role'] not in CANDIDATE_EDIT_ROLES: return self._json({'error':'Permission denied'},403)
                cid=int(m.group(1)); note=(data.get('note') or '').strip();
                if not note:return self._json({'error':'note required'},400)
                cur=conn.execute('INSERT INTO candidate_notes(candidate_id,user_id,note,note_type,created_at) VALUES(?,?,?,?,?)',(cid,u['id'],note,data.get('note_type') or 'General',utcnow())); audit(conn,u['id'],'ADD_NOTE','candidate',cid,note[:120],self.client_address[0]);conn.commit();return self._json({'id':cur.lastrowid,'ok':True},201)
            m=re.fullmatch(r'/api/hotlists/(\d+)/members',path)
            if m:
                if u['role'] not in RECRUITING_ROLES: return self._json({'error':'Permission denied'},403)
                hid=int(m.group(1)); cid=int(data.get('candidate_id') or 0)
                conn.execute('INSERT OR REPLACE INTO hotlist_members(hotlist_id,candidate_id,status,note,added_by,created_at) VALUES(?,?,?,?,?,?)',(hid,cid,'Active',data.get('note',''),u['id'],utcnow()));audit(conn,u['id'],'ADD_HOTLIST_MEMBER','hotlist',hid,f'candidate={cid}',self.client_address[0]);conn.commit();return self._json({'ok':True},201)
            if path=='/api/hotlists':
                if u['role'] not in RECRUITING_ROLES: return self._json({'error':'Permission denied'},403)
                cur=conn.execute('INSERT INTO hotlists(name,description,owner_user_id,visibility,mode,saved_search_json,created_at) VALUES(?,?,?,?,?,?,?)',(data.get('name') or 'Untitled Hotlist',data.get('description',''),u['id'],data.get('visibility','Team'),data.get('mode','static'),json.dumps(data.get('saved_search')) if data.get('saved_search') else None,utcnow())); audit(conn,u['id'],'CREATE','hotlist',cur.lastrowid,data.get('name',''),self.client_address[0]);conn.commit(); return self._json({'id':cur.lastrowid,'ok':True},201)
            if path=='/api/companies':
                if u['role'] not in ('admin','teamlead','sales'): return self._json({'error':'Permission denied'},403)
                now=utcnow();cur=conn.execute('INSERT INTO companies(name,company_type,industry,status,owner_user_id,website,phone,address,city,state,country,billing_terms,submission_guidelines,discount_rule,notes,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(data.get('name'),data.get('company_type','Client'),data.get('industry'),data.get('status','Active'),u['id'],data.get('website'),data.get('phone'),data.get('address'),data.get('city'),data.get('state'),data.get('country','USA'),data.get('billing_terms','Net 30'),data.get('submission_guidelines'),data.get('discount_rule'),data.get('notes'),now));audit(conn,u['id'],'CREATE','company',cur.lastrowid,data.get('name',''),self.client_address[0]);conn.commit();return self._json({'id':cur.lastrowid,'ok':True},201)
            if path=='/api/contacts':
                if u['role'] not in ('admin','teamlead','sales','recruiter'): return self._json({'error':'Permission denied'},403)
                cur=conn.execute('INSERT INTO contacts(company_id,first_name,last_name,title,email,phone,role_type,owner_user_id,status,notes,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)',(data.get('company_id'),data.get('first_name'),data.get('last_name'),data.get('title'),data.get('email'),data.get('phone'),data.get('role_type','Hiring Manager'),u['id'],data.get('status','Active'),data.get('notes'),utcnow()));audit(conn,u['id'],'CREATE','contact',cur.lastrowid,(data.get('first_name','')+' '+data.get('last_name','')).strip(),self.client_address[0]);conn.commit();return self._json({'id':cur.lastrowid,'ok':True},201)
            if path=='/api/leads':
                cur=conn.execute('INSERT INTO leads(company_id,contact_id,title,source,status,owner_user_id,next_action,next_action_at,notes,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)',(data.get('company_id'),data.get('contact_id'),data.get('title'),data.get('source','Manual'),data.get('status','New'),u['id'],data.get('next_action'),data.get('next_action_at'),data.get('notes'),utcnow()));audit(conn,u['id'],'CREATE','lead',cur.lastrowid,data.get('title',''),self.client_address[0]);conn.commit();return self._json({'id':cur.lastrowid,'ok':True},201)
            if path=='/api/opportunities':
                now=utcnow();cur=conn.execute('INSERT INTO opportunities(company_id,contact_id,name,stage,value,probability,owner_user_id,expected_close,next_activity,status,notes,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',(data.get('company_id'),data.get('contact_id'),data.get('name'),data.get('stage','Lead'),float(data.get('value') or 0),int(data.get('probability') or 10),u['id'],data.get('expected_close'),data.get('next_activity'),data.get('status','Open'),data.get('notes'),now,now));audit(conn,u['id'],'CREATE','opportunity',cur.lastrowid,data.get('name',''),self.client_address[0]);conn.commit();return self._json({'id':cur.lastrowid,'ok':True},201)
            if path=='/api/jobs':
                if u['role'] not in ('admin','teamlead','recruiter','sales'): return self._json({'error':'Permission denied'},403)
                seq=(qone(conn,'SELECT COUNT(*) n FROM jobs')['n'] or 0)+401; job_no=data.get('job_no') or f"26-{seq:05d}"; now=utcnow()
                cols=['job_no','title','company_id','contact_id','primary_recruiter_id','sales_user_id','status','priority','position_type','openings','filled','work_mode','city','state','country','zip','start_date','end_date','pay_min','pay_max','bill_min','bill_max','rate_type','profession','specialty','required_skills','required_qualifications','required_licenses','required_certifications','description','submission_guidelines_override','source','external_vms_id']
                vals=[data.get(c) for c in cols]; vals[0]=job_no; vals[4]=vals[4] or (u['id'] if u['role'] in ('recruiter','teamlead') else 3); vals[5]=vals[5] or 4; vals[6]=vals[6] or 'Open'; vals[7]=vals[7] or 'Normal'; vals[8]=vals[8] or 'Contract'; vals[9]=vals[9] or 1; vals[10]=vals[10] or 0; vals[11]=vals[11] or 'Onsite'; vals[14]=vals[14] or 'USA'; vals[22]=vals[22] or 'hour'; vals[31]=vals[31] or 'Direct'
                cur=conn.execute('INSERT INTO jobs('+','.join(cols)+',created_at,updated_at) VALUES('+','.join(['?']*(len(cols)+2))+')',(*vals,now,now)); jid=cur.lastrowid;audit(conn,u['id'],'CREATE','job',jid,job_no+' '+str(data.get('title')),self.client_address[0]);conn.commit();return self._json({'id':jid,'job_no':job_no,'ok':True},201)
            m=re.fullmatch(r'/api/jobs/(\d+)/interested',path)
            if m:
                jid=int(m.group(1))
                if u['role']=='candidate':
                    job=qone(conn,"SELECT id FROM jobs WHERE id=? AND status='Open'",(jid,))
                    if not job: return self._json({'error':'Permission denied'},403)
                    cid=u.get('candidate_id')
                elif u['role'] in RECRUITING_ROLES:
                    cid=int(data.get('candidate_id') or 0)
                else:
                    return self._json({'error':'Permission denied'},403)
                now=utcnow()
                conn.execute('INSERT INTO interested_candidates(job_id,candidate_id,status,source,user_id,created_at,updated_at) VALUES(?,?,?,?,?,?,?) ON CONFLICT(job_id,candidate_id) DO UPDATE SET status=excluded.status,user_id=excluded.user_id,updated_at=excluded.updated_at',(jid,cid,data.get('status','interested'),data.get('source','Manual'),u['id'],now,now)); audit(conn,u['id'],'MARK_INTERESTED','job',jid,f'candidate={cid}',self.client_address[0]);conn.commit();return self._json({'ok':True})
            m=re.fullmatch(r'/api/jobs/(\d+)/submissions',path)
            if m:
                jid=int(m.group(1))
                if u['role']=='supplier':
                    rel=qone(conn,"SELECT 1 ok FROM supplier_releases WHERE supplier_id=1 AND job_id=? AND status='Open'",(jid,))
                    if not rel: return self._json({'error':'Permission denied'},403)
                elif u['role'] not in ('admin','teamlead','recruiter','sales'):
                    return self._json({'error':'Permission denied'},403)
                cid=int(data.get('candidate_id') or 0); now=utcnow();
                cur=conn.execute('INSERT INTO submissions(job_id,candidate_id,recruiter_id,status,client_rate,candidate_rate,availability,recruiter_summary,compliance_status,rtr_status,submitted_at,client_feedback,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(jid,cid,u['id'],data.get('status','submitted'),data.get('client_rate'),data.get('candidate_rate'),data.get('availability'),data.get('recruiter_summary',''),data.get('compliance_status','Pending'),data.get('rtr_status','Pending'),now if data.get('status','submitted')!='draft' else None,'',now,now)); sid=cur.lastrowid;audit(conn,u['id'],'CREATE','submission',sid,f'job={jid}, candidate={cid}',self.client_address[0]);conn.commit();return self._json({'id':sid,'ok':True},201)
            m=re.fullmatch(r'/api/submissions/(\d+)/status',path)
            if m:
                sid=int(m.group(1)); st=data.get('status');
                if st not in STATUS_FLOW['submission']: return self._json({'error':'Invalid status'},400)
                if u['role']=='client':
                    own=qone(conn,'SELECT s.id FROM submissions s JOIN jobs j ON j.id=s.job_id WHERE s.id=? AND j.company_id=?',(sid,u.get('company_id')))
                    if not own: return self._json({'error':'Permission denied'},403)
                    if st not in ('client_review','interview','rejected','offer','hired'): return self._json({'error':'Client cannot set that status'},403)
                elif u['role'] not in ('admin','teamlead','recruiter','sales'):
                    return self._json({'error':'Permission denied'},403)
                conn.execute('UPDATE submissions SET status=?,client_feedback=COALESCE(?,client_feedback),updated_at=? WHERE id=?',(st,data.get('client_feedback'),utcnow(),sid));audit(conn,u['id'],'STATUS','submission',sid,st,self.client_address[0]);conn.commit();return self._json({'ok':True})
            if path=='/api/interviews':
                if u['role'] not in ('admin','teamlead','recruiter','sales'): return self._json({'error':'Permission denied'},403)
                sid=int(data.get('submission_id') or 0); cur=conn.execute('INSERT INTO interviews(submission_id,interview_type,scheduled_at,timezone,status,location_or_link,interviewer,feedback,rating,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)',(sid,data.get('interview_type','Video'),data.get('scheduled_at'),data.get('timezone','UTC'),data.get('status','scheduled'),data.get('location_or_link',''),data.get('interviewer',''),data.get('feedback',''),data.get('rating'),utcnow())); conn.execute('UPDATE submissions SET status="interview",updated_at=? WHERE id=?',(utcnow(),sid));audit(conn,u['id'],'CREATE','interview',cur.lastrowid,f'submission={sid}',self.client_address[0]);conn.commit();return self._json({'id':cur.lastrowid,'ok':True},201)
            if path=='/api/assessments':
                if u['role'] not in ('admin','teamlead','recruiter','hr'): return self._json({'error':'Permission denied'},403)
                cur=conn.execute('INSERT INTO assessments(candidate_id,job_id,title,assessment_type,status,score,max_score,invited_at,completed_at,notes) VALUES(?,?,?,?,?,?,?,?,?,?)',(data.get('candidate_id'),data.get('job_id'),data.get('title') or 'Assessment',data.get('assessment_type','Questionnaire'),'Invited',None,data.get('max_score',100),utcnow(),None,data.get('notes','')));audit(conn,u['id'],'CREATE','assessment',cur.lastrowid,data.get('title',''),self.client_address[0]);conn.commit();return self._json({'id':cur.lastrowid,'ok':True},201)
            if path=='/api/onboarding':
                if u['role'] not in ('admin','teamlead','recruiter','hr'): return self._json({'error':'Permission denied'},403)
                cur=conn.execute('INSERT INTO onboarding_packages(candidate_id,job_id,submission_id,package_name,status,assigned_by,due_date,created_at) VALUES(?,?,?,?,?,?,?,?)',(data.get('candidate_id'),data.get('job_id'),data.get('submission_id'),data.get('package_name') or 'Standard Onboarding','not_started',u['id'],data.get('due_date'),utcnow())); pid=cur.lastrowid
                reqs=data.get('requirements') or [{'type':'E-Sign','name':'Right to Represent'},{'type':'Identity','name':'Identity Verification'},{'type':'Policy','name':'Client Policies'}]
                for r in reqs: conn.execute('INSERT INTO onboarding_requirements(package_id,requirement_type,name,mandatory,status,completed_at,expiry_date,note) VALUES(?,?,?,?,?,?,?,?)',(pid,r.get('type','Document'),r.get('name','Requirement'),1 if r.get('mandatory',True) else 0,'Pending',None,r.get('expiry_date'),''))
                audit(conn,u['id'],'CREATE','onboarding',pid,data.get('package_name','Standard Onboarding'),self.client_address[0]);conn.commit();return self._json({'id':pid,'ok':True},201)
            m=re.fullmatch(r'/api/onboarding/requirements/(\d+)/status',path)
            if m:
                if u['role'] not in ('admin','teamlead','recruiter','hr'): return self._json({'error':'Permission denied'},403)
                rid=int(m.group(1)); st=data.get('status','Complete'); conn.execute('UPDATE onboarding_requirements SET status=?,completed_at=? WHERE id=?',(st,utcnow() if st.lower()=='complete' else None,rid)); pkg=qone(conn,'SELECT package_id FROM onboarding_requirements WHERE id=?',(rid,));
                if pkg:
                    counts=qone(conn,"SELECT COUNT(*) total,SUM(CASE WHEN lower(status)='complete' THEN 1 ELSE 0 END) done FROM onboarding_requirements WHERE package_id=?",(pkg['package_id'],)); pst='complete' if counts['total']==counts['done'] else 'in_progress';conn.execute('UPDATE onboarding_packages SET status=? WHERE id=?',(pst,pkg['package_id']))
                audit(conn,u['id'],'STATUS','onboarding_requirement',rid,st,self.client_address[0]);conn.commit();return self._json({'ok':True})
            if path=='/api/assignments':
                if u['role'] not in ('admin','teamlead','hr','finance'): return self._json({'error':'Permission denied'},403)
                now=utcnow();cur=conn.execute('INSERT INTO assignments(start_id,candidate_id,job_id,company_id,status,start_date,end_date,worksite,cost_center,vms_id,approver_contact_id,bill_rate,pay_rate,overtime_rule,payroll_profile,po_number,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(data.get('start_id'),data.get('candidate_id'),data.get('job_id'),data.get('company_id'),data.get('status','pending'),data.get('start_date'),data.get('end_date'),data.get('worksite'),data.get('cost_center'),data.get('vms_id'),data.get('approver_contact_id'),data.get('bill_rate'),data.get('pay_rate'),data.get('overtime_rule','1.5x after 40h'),data.get('payroll_profile','Hourly'),data.get('po_number'),now,now));audit(conn,u['id'],'CREATE','assignment',cur.lastrowid,'',self.client_address[0]);conn.commit();return self._json({'id':cur.lastrowid,'ok':True},201)
            if path=='/api/timesheets':
                if u['role'] not in ('admin','teamlead','finance','hr','worker'): return self._json({'error':'Permission denied'},403)
                cid=u['candidate_id'] if u['role']=='worker' else data.get('candidate_id'); aid=int(data.get('assignment_id') or 0)
                if u['role']=='worker' and not qone(conn,'SELECT id FROM assignments WHERE id=? AND candidate_id=?',(aid,u.get('candidate_id'))): return self._json({'error':'Permission denied'},403)
                daily=data.get('daily') or {}; total=sum(float(v or 0) for v in daily.values()); regular=min(total,40); ot=max(0,total-40); now=utcnow();
                cur=conn.execute('INSERT INTO timesheets(assignment_id,candidate_id,week_start,status,total_hours,regular_hours,overtime_hours,daily_json,submitted_at,approved_by,approved_at,rejection_note,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(assignment_id,week_start) DO UPDATE SET status=excluded.status,total_hours=excluded.total_hours,regular_hours=excluded.regular_hours,overtime_hours=excluded.overtime_hours,daily_json=excluded.daily_json,submitted_at=excluded.submitted_at,updated_at=excluded.updated_at',(aid,cid,data.get('week_start'),data.get('status','submitted'),total,regular,ot,json.dumps(daily),now if data.get('status','submitted')=='submitted' else None,None,None,None,now,now)); tid=cur.lastrowid or qone(conn,'SELECT id FROM timesheets WHERE assignment_id=? AND week_start=?',(aid,data.get('week_start')))['id'];audit(conn,u['id'],'UPSERT','timesheet',tid,f'{total} hours',self.client_address[0]);conn.commit();return self._json({'id':tid,'total_hours':total,'regular_hours':regular,'overtime_hours':ot,'ok':True},201)
            m=re.fullmatch(r'/api/timesheets/(\d+)/status',path)
            if m:
                tid=int(m.group(1)); st=data.get('status');
                if st not in STATUS_FLOW['timesheet']: return self._json({'error':'Invalid status'},400)
                if st in ('approved','rejected') and u['role'] not in ('admin','finance','client','approver','teamlead'): return self._json({'error':'Permission denied'},403)
                conn.execute('UPDATE timesheets SET status=?,approved_by=?,approved_at=?,rejection_note=?,updated_at=? WHERE id=?',(st,u['id'] if st=='approved' else None,utcnow() if st=='approved' else None,data.get('rejection_note'),utcnow(),tid));audit(conn,u['id'],'STATUS','timesheet',tid,st,self.client_address[0]);conn.commit();return self._json({'ok':True})
            if path=='/api/expenses':
                if u['role'] not in ('admin','teamlead','finance','hr','worker'): return self._json({'error':'Permission denied'},403)
                if u['role']=='worker' and not qone(conn,'SELECT id FROM assignments WHERE id=? AND candidate_id=?',(data.get('assignment_id'),u.get('candidate_id'))): return self._json({'error':'Permission denied'},403)
                cid=u['candidate_id'] if u['role']=='worker' else data.get('candidate_id');cur=conn.execute('INSERT INTO expenses(assignment_id,candidate_id,expense_date,category,amount,receipt_ref,status,description,approved_by,approved_at,rejection_note,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(data.get('assignment_id'),cid,data.get('expense_date') or today(),data.get('category','Other'),float(data.get('amount') or 0),data.get('receipt_ref',''),data.get('status','submitted'),data.get('description',''),None,None,None,utcnow()));audit(conn,u['id'],'CREATE','expense',cur.lastrowid,str(data.get('amount')),self.client_address[0]);conn.commit();return self._json({'id':cur.lastrowid,'ok':True},201)
            m=re.fullmatch(r'/api/expenses/(\d+)/status',path)
            if m:
                if u['role'] not in ('admin','teamlead','finance','client','approver'): return self._json({'error':'Permission denied'},403)
                eid=int(m.group(1)); st=data.get('status')
                if u['role'] in ('client','approver'):
                    own=qone(conn,'SELECT e.id FROM expenses e JOIN assignments a ON a.id=e.assignment_id WHERE e.id=? AND a.company_id=?',(eid,u.get('company_id')))
                    if not own: return self._json({'error':'Permission denied'},403)
                conn.execute('UPDATE expenses SET status=?,approved_by=?,approved_at=?,rejection_note=? WHERE id=?',(st,u['id'] if st=='approved' else None,utcnow() if st=='approved' else None,data.get('rejection_note'),eid));audit(conn,u['id'],'STATUS','expense',eid,st,self.client_address[0]);conn.commit();return self._json({'ok':True})
            if path=='/api/invoices':
                if u['role'] not in ('admin','finance'): return self._json({'error':'Permission denied'},403)
                seq=(qone(conn,'SELECT COUNT(*) n FROM invoices')['n'] or 0)+902; inv=data.get('invoice_no') or f'INV-26{seq:04d}'; now=utcnow();cur=conn.execute('INSERT INTO invoices(invoice_no,company_id,assignment_id,period_start,period_end,amount,tax,status,due_date,issued_at,paid_at,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(inv,data.get('company_id'),data.get('assignment_id'),data.get('period_start'),data.get('period_end'),float(data.get('amount') or 0),float(data.get('tax') or 0),data.get('status','draft'),data.get('due_date'),now if data.get('status')=='issued' else None,None,now));audit(conn,u['id'],'CREATE','invoice',cur.lastrowid,inv,self.client_address[0]);conn.commit();return self._json({'id':cur.lastrowid,'invoice_no':inv,'ok':True},201)
            if path=='/api/communications':
                cur=conn.execute('INSERT INTO communications(entity_type,entity_id,channel,direction,subject,body,user_id,status,created_at) VALUES(?,?,?,?,?,?,?,?,?)',(data.get('entity_type'),data.get('entity_id'),data.get('channel','Email'),data.get('direction','Outbound'),data.get('subject',''),data.get('body',''),u['id'],data.get('status','Logged'),utcnow()));audit(conn,u['id'],'CREATE','communication',cur.lastrowid,data.get('subject',''),self.client_address[0]);conn.commit();return self._json({'id':cur.lastrowid,'ok':True},201)
            if path=='/api/users':
                if u['role']!='admin': return self._json({'error':'Permission denied'},403)
                email=(data.get('email') or '').strip().lower();pw=data.get('password') or 'ChangeMe@123';cur=conn.execute('INSERT INTO users(email,pass_hash,name,role,company_id,candidate_id,active,created_at) VALUES(?,?,?,?,?,?,1,?)',(email,hash_password(pw),data.get('name') or email,data.get('role','recruiter'),data.get('company_id'),data.get('candidate_id'),utcnow()));audit(conn,u['id'],'CREATE','user',cur.lastrowid,email,self.client_address[0]);conn.commit();return self._json({'id':cur.lastrowid,'ok':True},201)
            if path=='/api/reset':
                if u['role']!='admin': return self._json({'error':'Permission denied'},403)
                conn.close(); init_db(reset=True); return self._json({'ok':True,'message':'Database reset to seed data. Please login again.'})
            return self._json({'error':'API endpoint not found'},404)
        except sqlite3.IntegrityError as e:
            conn.rollback(); return self._json({'error':'Database constraint failed','detail':str(e)},409)
        except Exception as e:
            conn.rollback(); return self._json({'error':'Server error','detail':str(e)},500)
        finally:
            try: conn.close()
            except Exception: pass
    def do_PATCH(self):
        path=urllib.parse.urlparse(self.path).path; data=self._body(); conn=db()
        try:
            u=self._need(conn)
            if not u:return
            m=re.fullmatch(r'/api/candidates/(\d+)',path)
            if m:
                cid=int(m.group(1))
                if u['role'] in ('candidate','worker'):
                    if u.get('candidate_id')!=cid: return self._json({'error':'Permission denied'},403)
                    allowed={'first_name','last_name','email','phone','city','state','country','zip','current_title','availability_date','pay_min','pay_max','desired_rate_type','resume_text','summary','consent_sms','consent_email','do_not_contact'}
                elif u['role'] in CANDIDATE_EDIT_ROLES:
                    allowed={'first_name','last_name','email','phone','city','state','country','zip','profession','specialty','current_title','availability_date','pay_min','pay_max','desired_rate_type','source','status','resume_text','summary','consent_sms','consent_email','do_not_contact','credibility_score'}
                else:
                    return self._json({'error':'Permission denied'},403)
                fields=[k for k in data if k in allowed]
                if not fields:return self._json({'error':'No valid fields'},400)
                conn.execute('UPDATE candidates SET '+','.join(f'{k}=?' for k in fields)+',updated_at=? WHERE id=?',tuple(data[k] for k in fields)+(utcnow(),cid));audit(conn,u['id'],'UPDATE','candidate',cid,','.join(fields),self.client_address[0]);conn.commit();return self._json({'ok':True})
            m=re.fullmatch(r'/api/jobs/(\d+)',path)
            if m:
                if u['role'] not in JOB_EDIT_ROLES: return self._json({'error':'Permission denied'},403)
                jid=int(m.group(1)); allowed={'title','company_id','contact_id','primary_recruiter_id','sales_user_id','status','priority','position_type','openings','filled','work_mode','city','state','country','zip','start_date','end_date','pay_min','pay_max','bill_min','bill_max','rate_type','profession','specialty','required_skills','required_qualifications','required_licenses','required_certifications','description','submission_guidelines_override','source','external_vms_id'}; fields=[k for k in data if k in allowed]
                if not fields:return self._json({'error':'No valid fields'},400)
                conn.execute('UPDATE jobs SET '+','.join(f'{k}=?' for k in fields)+',updated_at=? WHERE id=?',tuple(data[k] for k in fields)+(utcnow(),jid));audit(conn,u['id'],'UPDATE','job',jid,','.join(fields),self.client_address[0]);conn.commit();return self._json({'ok':True})
            return self._json({'error':'Not found'},404)
        finally: conn.close()
    def dashboard(self,conn,u):
        role=u['role']; data={'role':role,'user':{'id':u['id'],'name':u['name']}}
        if role in ('candidate','worker'):
            cid=u['candidate_id']; data['candidate']=candidate_bundle(conn,cid); data['jobs']=qall(conn,"SELECT id,job_no,title,city,state,work_mode,pay_min,pay_max,rate_type FROM jobs WHERE status='Open' ORDER BY created_at DESC LIMIT 12"); return data
        if role=='client':
            co=u['company_id']; data['company']=qone(conn,'SELECT * FROM companies WHERE id=?',(co,)); data['open_jobs']=qone(conn,"SELECT COUNT(*) n FROM jobs WHERE company_id=? AND status='Open'",(co,))['n']; data['submissions']=qone(conn,'SELECT COUNT(*) n FROM submissions s JOIN jobs j ON j.id=s.job_id WHERE j.company_id=?',(co,))['n']; data['interviews']=qone(conn,"SELECT COUNT(*) n FROM interviews i JOIN submissions s ON s.id=i.submission_id JOIN jobs j ON j.id=s.job_id WHERE j.company_id=? AND i.status='scheduled'",(co,))['n']; return data
        if role=='supplier':
            data['released_jobs']=qone(conn,"SELECT COUNT(*) n FROM supplier_releases WHERE supplier_id=1 AND status='Open'")['n']; return data
        data.update({
          'open_jobs':qone(conn,"SELECT COUNT(*) n FROM jobs WHERE status='Open'")['n'],
          'primary_jobs':qone(conn,"SELECT COUNT(*) n FROM jobs WHERE status='Open' AND primary_recruiter_id=?",(u['id'],))['n'],
          'jobs_no_activity':qone(conn,"SELECT COUNT(*) n FROM jobs j WHERE status='Open' AND NOT EXISTS(SELECT 1 FROM submissions s WHERE s.job_id=j.id)")['n'],
          'active_assignments':qone(conn,"SELECT COUNT(*) n FROM assignments WHERE status='active'")['n'],
          'starts_30':qone(conn,"SELECT COUNT(*) n FROM starts WHERE start_date>=date('now','-30 day')")['n'],
          'pending_onboarding':qone(conn,"SELECT COUNT(*) n FROM onboarding_packages WHERE status!='complete'")['n'],
          'pending_timesheets':qone(conn,"SELECT COUNT(*) n FROM timesheets WHERE status='submitted'")['n'],
          'pending_expenses':qone(conn,"SELECT COUNT(*) n FROM expenses WHERE status='submitted'")['n'],
          'open_tasks':qone(conn,"SELECT COUNT(*) n FROM tasks WHERE status='Open' AND owner_user_id=?",(u['id'],))['n'],
          'candidates':qone(conn,"SELECT COUNT(*) n FROM candidates WHERE status='Active'")['n'],
          'pipeline':qall(conn,"SELECT status,COUNT(*) count FROM submissions GROUP BY status ORDER BY count DESC"),
          'job_status':qall(conn,"SELECT status,COUNT(*) count FROM jobs GROUP BY status ORDER BY count DESC"),
          'company_pipeline':[{'stage':'Lead','count':4},{'stage':'Qualified','count':3},{'stage':'Presentation','count':2},{'stage':'Negotiation','count':1},{'stage':'Won','count':2}],
          'recent_jobs':qall(conn,"SELECT j.id,j.job_no,j.title,j.status,j.priority,co.name company_name,(SELECT COUNT(*) FROM submissions s WHERE s.job_id=j.id) submissions FROM jobs j LEFT JOIN companies co ON co.id=j.company_id ORDER BY j.created_at DESC LIMIT 8"),
          'tasks':qall(conn,"SELECT * FROM tasks WHERE owner_user_id=? AND status='Open' ORDER BY due_at LIMIT 8",(u['id'],)),
        }); return data
    def report_summary(self,conn,u):
        return {
          'recruiting':{'active_candidates':qone(conn,"SELECT COUNT(*) n FROM candidates WHERE status='Active'")['n'],'open_jobs':qone(conn,"SELECT COUNT(*) n FROM jobs WHERE status='Open'")['n'],'submissions_30':qone(conn,"SELECT COUNT(*) n FROM submissions WHERE created_at>=datetime('now','-30 day')")['n'],'interviews_scheduled':qone(conn,"SELECT COUNT(*) n FROM interviews WHERE status='scheduled'")['n']},
          'workforce':{'active_assignments':qone(conn,"SELECT COUNT(*) n FROM assignments WHERE status='active'")['n'],'pending_timesheets':qone(conn,"SELECT COUNT(*) n FROM timesheets WHERE status='submitted'")['n'],'pending_expenses':qone(conn,"SELECT COUNT(*) n FROM expenses WHERE status='submitted'")['n']},
          'finance':{'issued_invoices':qone(conn,"SELECT COALESCE(SUM(amount+tax),0) n FROM invoices WHERE status IN ('issued','part_paid')")['n'],'paid_invoices':qone(conn,"SELECT COALESCE(SUM(amount+tax),0) n FROM invoices WHERE status='paid'")['n'],'open_po_value':qone(conn,"SELECT COALESCE(SUM(amount),0) n FROM purchase_orders WHERE status='Open'")['n']},
          'submission_by_status':qall(conn,'SELECT status,COUNT(*) count FROM submissions GROUP BY status'),
          'jobs_by_company':qall(conn,'SELECT co.name company,COUNT(j.id) count FROM companies co LEFT JOIN jobs j ON j.company_id=co.id GROUP BY co.id ORDER BY count DESC')
        }

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--host',default='127.0.0.1'); ap.add_argument('--port',type=int,default=8765); ap.add_argument('--open',action='store_true'); ap.add_argument('--reset',action='store_true'); ap.add_argument('--quiet',action='store_true'); args=ap.parse_args()
    init_db(reset=args.reset)
    srv=ThreadingHTTPServer((args.host,args.port),Handler); srv.quiet=args.quiet
    url=f'http://127.0.0.1:{args.port}/'
    print('='*72); print(f' {APP_NAME} {APP_VERSION}'); print('='*72); print(f'LOCAL_URL={url}'); print(f'DATABASE={DB_PATH}'); print(f'PERSISTENCE={"SUPABASE_STORAGE" if REMOTE_PERSISTENCE_ENABLED else "LOCAL_SQLITE"}'); print(f'HOST={args.host} PORT={args.port}'); print('CTRL+C to stop server'); print('='*72,flush=True)
    if args.open: threading.Timer(1.1,lambda:webbrowser.open(url)).start()
    try: srv.serve_forever()
    except KeyboardInterrupt: pass
    finally: srv.server_close()

if __name__=='__main__': main()
