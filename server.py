#!/usr/bin/env python3
import argparse, atexit, base64, csv, hashlib, hmac, io, json, math, mimetypes, os, re, secrets, sqlite3, sys, threading, time, urllib.parse, urllib.request, urllib.error, webbrowser
from datetime import datetime, timedelta, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from parity_api import ensure_parity_schema, parity_get, parity_post, parity_patch, parity_delete
from r14_api import ensure_r14_schema, r14_public_post, r14_get, r14_post, r14_patch, r14_delete, r14_mfa_required, r14_verify_totp
from core_policies import PolicyError, assignment_graph, bounded_hours, entity_reference, exact_money, permission_denied_by_override, safe_identifier, tenant_parent, time_period_locked
from r15_migrations import apply_r15_migrations, scan_integrity
from r18_api import ensure_r18_schema, r18_get, r18_post, r18_patch, r18_delete
from r19_api import ensure_r19_schema, r19_get, r19_post
from r22_api import ensure_r22_schema, r22_public_get, r22_get, r22_post
from r23_rbac import ensure_r23_schema, r23_get, r23_post, r23_permission_denied, effective_context
from r23c_candidate import ensure_r23c_schema, r23c_public_get, r23c_public_post, r23c_get, r23c_post
from r23d_ops import ensure_r23d_schema, r23d_get, r23d_post
from persistence_authority import DurabilityError, LeaseConflict, PersistenceError, SchemaPolicy, SnapshotAuthority, SnapshotValidationError, SupabasePostgrestAtomicStore, WriterLease

APP_NAME = "ATS One Staffing ERP"
APP_VERSION = "7.5.0-r23d-non-ai-gap-closure"
IDENTITY_MODEL = "global-email-primary-tenant"
BASE_DIR = Path(__file__).resolve().parent
WEB_DIR = BASE_DIR / "web"
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "ats_one.db"

# R15 durable persistence authority.
#
# The historical mutable whole-file Supabase Storage backup protocol was
# removed because it could acknowledge a local write before remote durability,
# restore unverified bytes, and let multiple instances overwrite each other.
# R15 uses a Postgres-backed CAS object table via Supabase/PostgREST.  A
# production process cannot become a writer unless it owns the remote lease.
SUPABASE_URL = (os.environ.get("SUPABASE_URL") or "").rstrip("/")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or ""
SUPABASE_PERSISTENCE_TABLE = os.environ.get("SUPABASE_PERSISTENCE_TABLE") or "ats_one_atomic_objects"
REMOTE_PERSISTENCE_ENABLED = bool(SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY)
APP_MODE = (os.environ.get("ATS_ONE_MODE") or "production").strip().lower()
DEMO_MODE = APP_MODE in {"demo", "local", "test"}
_REMOTE_STORE = None
_REMOTE_LEASE = None
_REMOTE_AUTHORITY = None
_REMOTE_FAILURE = None
_REMOTE_HEARTBEAT_STOP = threading.Event()
_REMOTE_HEARTBEAT_THREAD = None
_REMOTE_LOCK = threading.RLock()


def _remote_policy():
    return SchemaPolicy(
        frozenset({
            "meta", "tenants", "users", "sessions", "candidates", "jobs",
            "submissions", "assignments", "timesheets", "expenses", "invoices",
            "schema_migrations",
        }),
        min_user_version=0,
    )


def _remote_heartbeat():
    global _REMOTE_FAILURE
    while not _REMOTE_HEARTBEAT_STOP.wait(20.0):
        try:
            if _REMOTE_LEASE is not None:
                _REMOTE_LEASE.renew()
        except BaseException as exc:
            _REMOTE_FAILURE = exc
            print(f"PERSISTENCE_LEASE_FAILURE={exc!r}", file=sys.stderr, flush=True)
            return


def _init_remote_authority():
    global _REMOTE_STORE, _REMOTE_LEASE, _REMOTE_AUTHORITY, _REMOTE_HEARTBEAT_THREAD
    if not REMOTE_PERSISTENCE_ENABLED:
        return None
    with _REMOTE_LOCK:
        if _REMOTE_AUTHORITY is not None:
            if _REMOTE_FAILURE is not None:
                raise DurabilityError("remote persistence authority is degraded") from _REMOTE_FAILURE
            return _REMOTE_AUTHORITY
        owner = (os.environ.get("RENDER_INSTANCE_ID") or os.environ.get("HOSTNAME") or secrets.token_hex(12)).strip()
        store = SupabasePostgrestAtomicStore(
            SUPABASE_URL,
            SUPABASE_SERVICE_ROLE_KEY,
            table=SUPABASE_PERSISTENCE_TABLE,
        )
        lease = WriterLease(store, owner_id=owner, duration_seconds=90.0)
        lease.acquire()
        authority = SnapshotAuthority(store, lease, retention=3)
        _REMOTE_STORE = store
        _REMOTE_LEASE = lease
        _REMOTE_AUTHORITY = authority
        _REMOTE_HEARTBEAT_STOP.clear()
        _REMOTE_HEARTBEAT_THREAD = threading.Thread(
            target=_remote_heartbeat,
            name="ats-one-persistence-lease",
            daemon=True,
        )
        _REMOTE_HEARTBEAT_THREAD.start()
        return authority


def _release_remote_authority():
    _REMOTE_HEARTBEAT_STOP.set()
    if _REMOTE_HEARTBEAT_THREAD is not None and _REMOTE_HEARTBEAT_THREAD.is_alive():
        _REMOTE_HEARTBEAT_THREAD.join(2.0)
    try:
        if _REMOTE_LEASE is not None:
            _REMOTE_LEASE.release()
    except Exception:
        pass


atexit.register(_release_remote_authority)


def restore_remote_db_if_needed():
    if not REMOTE_PERSISTENCE_ENABLED or DB_PATH.exists():
        return False
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    authority = _init_remote_authority()
    try:
        result = authority.restore(DB_PATH, _remote_policy())
        print(
            f"PERSISTENCE_RESTORE_GENERATION={result.entry.generation} "
            f"FALLBACK={str(result.used_fallback).upper()}",
            flush=True,
        )
        return True
    except SnapshotValidationError as exc:
        if "no remote snapshot generations exist" in str(exc):
            return False
        raise


def prove_remote_durability():
    if not REMOTE_PERSISTENCE_ENABLED:
        return None
    if _REMOTE_FAILURE is not None:
        raise DurabilityError("remote persistence authority is degraded") from _REMOTE_FAILURE
    authority = _init_remote_authority()
    if _REMOTE_LEASE is None:
        raise DurabilityError("writer lease is unavailable")
    # A lease renewal immediately before publication makes a stale writer fail
    # before any remote mutation. SnapshotAuthority re-checks it around CAS ops.
    _REMOTE_LEASE.renew()
    return authority.publish(DB_PATH, _remote_policy())


class PersistentSQLiteConnection(sqlite3.Connection):
    def commit(self):
        super().commit()
        if REMOTE_PERSISTENCE_ENABLED:
            # The SQLite backup API used by SnapshotAuthority includes committed
            # WAL pages, so correctness does not depend on a swallowed checkpoint.
            # A request is not allowed to observe commit() success unless the CAS
            # generation and manifest were read-back and verified.
            prove_remote_durability()

INTERNAL_ROLES = {"admin","teamlead","recruiter","sales","hr","finance"}
CANDIDATE_EDIT_ROLES = {"admin","teamlead","recruiter","hr"}
JOB_EDIT_ROLES = {"admin","teamlead","recruiter","sales"}
RECRUITING_ROLES = {"admin","teamlead","recruiter","sales","hr"}
WORKFORCE_ADMIN_ROLES = {"admin","teamlead","hr","finance"}

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
    "amazon web services": ["amazon web services","aws"],
    "gcp": ["gcp","google cloud platform"],
    "google cloud platform": ["google cloud platform","gcp"],
    "azure": ["azure","microsoft azure"],
    "postgresql": ["postgresql","postgres"],
    "postgres": ["postgres","postgresql"],
    "typescript": ["typescript","ts"],
    "ts": ["ts","typescript"],
    "kubernetes": ["kubernetes","k8s"],
    "k8s": ["k8s","kubernetes"],
    "react": ["react","reactjs","react.js"],
    "spring": ["spring","spring boot","springboot"],
    "data engineer": ["data engineer","etl engineer","data engineering"],
}

SCHEMA = r'''
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS tenants(
 id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, slug TEXT UNIQUE NOT NULL,
 status TEXT NOT NULL DEFAULT 'Active', created_at TEXT NOT NULL
);
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
CREATE TABLE IF NOT EXISTS candidate_document_versions(
 id INTEGER PRIMARY KEY AUTOINCREMENT, document_id INTEGER NOT NULL, version INTEGER NOT NULL,
 file_name TEXT, mime_type TEXT, size_bytes INTEGER DEFAULT 0, sha256 TEXT, content BLOB,
 uploaded_by INTEGER, created_at TEXT NOT NULL, UNIQUE(document_id,version)
);
CREATE TABLE IF NOT EXISTS assessment_questions(
 id INTEGER PRIMARY KEY AUTOINCREMENT, assessment_id INTEGER NOT NULL, prompt TEXT NOT NULL,
 question_type TEXT DEFAULT 'text', choices_json TEXT, points REAL DEFAULT 1, sort_order INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS assessment_answers(
 id INTEGER PRIMARY KEY AUTOINCREMENT, assessment_id INTEGER NOT NULL, question_id INTEGER NOT NULL,
 answer TEXT, awarded_points REAL DEFAULT 0, answered_at TEXT, UNIQUE(assessment_id,question_id)
);
CREATE TABLE IF NOT EXISTS invoice_payments(
 id INTEGER PRIMARY KEY AUTOINCREMENT, invoice_id INTEGER NOT NULL, amount REAL NOT NULL,
 reference TEXT, payment_date TEXT NOT NULL, user_id INTEGER, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS workflow_history(
 id INTEGER PRIMARY KEY AUTOINCREMENT, entity_type TEXT NOT NULL, entity_id INTEGER NOT NULL,
 from_status TEXT, to_status TEXT, note TEXT, user_id INTEGER, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS automation_runs(
 id INTEGER PRIMARY KEY AUTOINCREMENT, automation_id INTEGER NOT NULL, dry_run INTEGER DEFAULT 0,
 status TEXT, result_json TEXT, user_id INTEGER, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS integration_logs(
 id INTEGER PRIMARY KEY AUTOINCREMENT, connector_id INTEGER NOT NULL, action TEXT, status TEXT,
 detail TEXT, user_id INTEGER, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS vms_sync_history(
 id INTEGER PRIMARY KEY AUTOINCREMENT, vms_account_id INTEGER NOT NULL, status TEXT,
 detail TEXT, retry_of INTEGER, user_id INTEGER, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS report_definitions(
 id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, report_key TEXT NOT NULL,
 description TEXT, parameters_json TEXT, owner_user_id INTEGER, is_shared INTEGER DEFAULT 0,
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS audit_log(
 id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, action TEXT, entity_type TEXT, entity_id INTEGER,
 detail TEXT, ip TEXT, created_at TEXT NOT NULL
);
'''

TENANT_TABLES = (
    'users','sessions','companies','contacts','candidates','candidate_skills','candidate_experience',
    'candidate_licenses','candidate_certifications','candidate_qualifications','candidate_attributes',
    'candidate_documents','candidate_notes','hotlists','hotlist_members','jobs','job_users',
    'interested_candidates','submissions','interviews','assessments','assessment_questions',
    'assessment_answers','onboarding_packages','onboarding_requirements','starts','assignments',
    'timesheets','expenses','purchase_orders','invoices','invoice_payments','vms_accounts','vms_mappings',
    'vms_sync_history','suppliers','supplier_releases','communications','tasks','leads','opportunities',
    'shifts','attendance','job_distribution','integration_connectors','integration_logs','automations',
    'automation_runs','custom_fields','entity_custom_values','candidate_document_versions',
    'workflow_history','report_definitions','audit_log'
)

POSTAL_COORDINATES = {
    '411001': (18.5204, 73.8567), '560001': (12.9716, 77.5946),
    '92501': (33.9806, -117.3755), '32202': (30.3322, -81.6557),
    '78701': (30.2672, -97.7431), '07302': (40.7178, -74.0435),
    'EC1A': (51.5202, -0.0977), '33101': (25.7617, -80.1918),
    '94105': (37.7898, -122.3942), '10006': (40.7094, -74.0131),
}

def _columns(conn, table):
    return {r['name'] for r in qall(conn,f'PRAGMA table_info({table})')}

def _add_column(conn, table, definition):
    name=definition.split()[0]
    if name not in _columns(conn,table): conn.execute(f'ALTER TABLE {table} ADD COLUMN {definition}')

def migrate_db(conn):
    """Forward-only, idempotent migrations for both existing live DBs and fresh audit DBs."""
    conn.execute("INSERT OR IGNORE INTO tenants(id,name,slug,status,created_at) VALUES(1,'Default Tenant','default','Active',?)",(utcnow(),))
    existing={r['name'] for r in qall(conn,"SELECT name FROM sqlite_master WHERE type='table'")}
    for table in TENANT_TABLES:
        if table in existing: _add_column(conn,table,'tenant_id INTEGER NOT NULL DEFAULT 1')
    for table,definition in (
        ('users','supplier_id INTEGER'),('candidates','latitude REAL'),('candidates','longitude REAL'),
        ('candidates','supplier_id INTEGER'),
        ('candidates','archived_at TEXT'),('jobs','latitude REAL'),('jobs','longitude REAL'),
        ('jobs','archived_at TEXT'),('hotlists','archived_at TEXT'),('hotlists','updated_at TEXT'),
        ('candidate_documents','current_version INTEGER NOT NULL DEFAULT 1'),
        ('candidate_documents','mime_type TEXT'),('candidate_documents','size_bytes INTEGER NOT NULL DEFAULT 0'),
        ('onboarding_requirements','evidence_document_id INTEGER'),('starts','updated_at TEXT'),
        ('assignments','termination_reason TEXT'),('invoices','paid_amount REAL NOT NULL DEFAULT 0'),
        ('purchase_orders','assignment_id INTEGER'),
        ('invoices','void_reason TEXT'),('vms_accounts','last_error TEXT'),
        ('integration_connectors','credential_ref TEXT'),('automations','updated_at TEXT'),
    ):
        if table in existing: _add_column(conn,table,definition)
    conn.execute("UPDATE users SET supplier_id=1 WHERE role='supplier' AND supplier_id IS NULL")
    for postal,(lat,lon) in POSTAL_COORDINATES.items():
        conn.execute('UPDATE candidates SET latitude=COALESCE(latitude,?),longitude=COALESCE(longitude,?) WHERE upper(zip)=upper(?)',(lat,lon,postal))
        conn.execute('UPDATE jobs SET latitude=COALESCE(latitude,?),longitude=COALESCE(longitude,?) WHERE upper(zip)=upper(?)',(lat,lon,postal))
    for table in TENANT_TABLES:
        if table in existing:
            conn.execute(f'CREATE INDEX IF NOT EXISTS idx_{table}_tenant ON {table}(tenant_id)')


    ensure_parity_schema(conn)
    ensure_r14_schema(conn)
    apply_r15_migrations(conn)
    ensure_r18_schema(conn)
    ensure_r19_schema(conn)
    ensure_r22_schema(conn)
    ensure_r23_schema(conn)
    ensure_r23c_schema(conn)
    ensure_r23d_schema(conn)

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
    owner=qone(conn,'SELECT tenant_id FROM users WHERE id=?',(user_id,)) if user_id else None
    conn.execute('INSERT INTO audit_log(user_id,action,entity_type,entity_id,detail,ip,created_at,tenant_id) VALUES(?,?,?,?,?,?,?,?)',
                 (user_id,action,entity_type,entity_id,detail,ip,utcnow(),(owner or {}).get('tenant_id',1)))

def _secure_first_admin_bootstrap(conn):
    """Create a disabled-password admin plus one-time invitation when explicitly configured."""
    email=(os.environ.get('ATS_ONE_BOOTSTRAP_EMAIL') or '').strip().lower()
    token=os.environ.get('ATS_ONE_BOOTSTRAP_TOKEN') or ''
    if not email or len(token)<24:
        return False
    if qone(conn,'SELECT id FROM users WHERE lower(email)=?',(email,)):
        return False
    now=utcnow(); expiry=(datetime.now(timezone.utc)+timedelta(hours=1)).replace(microsecond=0).isoformat()
    cur=conn.execute('INSERT INTO users(email,pass_hash,name,role,active,created_at,tenant_id) VALUES(?,?,?,?,1,?,1)',
                     (email,hash_password(secrets.token_urlsafe(48)),os.environ.get('ATS_ONE_BOOTSTRAP_NAME') or 'Initial Administrator','admin',now))
    conn.execute('INSERT INTO user_invitations(tenant_id,user_id,email,token_hash,expires_at,created_by,created_at) VALUES(1,?,?,?,?,NULL,?)',
                 (cur.lastrowid,email,hashlib.sha256(token.encode()).hexdigest(),expiry,now))
    conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('bootstrap_state','invitation-created')")
    return True


def init_db(reset=False):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if reset and (not DEMO_MODE or os.environ.get('ATS_ONE_RESET_AUTHORITY_CONFIRMED')!='LOCAL_TEST_ONLY'):
        raise RuntimeError("Database reset requires explicit local/test maintenance authority")
    if reset and REMOTE_PERSISTENCE_ENABLED:
        raise RuntimeError("Remote database reset is disabled")
    if reset and DB_PATH.exists(): DB_PATH.unlink()
    if not reset:
        restore_remote_db_if_needed()
    conn=db(); conn.executescript(SCHEMA); migrate_db(conn)
    seeded=qone(conn,"SELECT value FROM meta WHERE key='seeded'")
    if not seeded:
        if DEMO_MODE:
            seed(conn)
            conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('seeded','demo')")
        elif _secure_first_admin_bootstrap(conn):
            conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('seeded','secure-bootstrap')")
        migrate_db(conn)
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

def candidate_bundle(conn, cid, tenant_id=None):
    c=qone(conn,'SELECT * FROM candidates WHERE id=?'+(' AND tenant_id=?' if tenant_id is not None else ''),(cid,tenant_id) if tenant_id is not None else (cid,))
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

class BooleanSyntaxError(ValueError): pass

def _aliases(term, mapping=True):
    t=norm(term).strip('"')
    if not mapping: return {t}
    out={t}
    for key,vals in SYNONYMS.items():
        family={norm(key),*(norm(x) for x in vals)}
        if t in family: out.update(family)
    return {x for x in out if x}

def _text_has(text, alias):
    text=norm(text); alias=norm(alias)
    if not alias: return False
    if alias in text:
        if len(alias)<=2 and alias.isalnum():
            return re.search(r'(?<![a-z0-9])'+re.escape(alias)+r'(?![a-z0-9])',text,re.I) is not None
        return True
    return False

def _date_value(value, fallback):
    try: return datetime.fromisoformat(str(value)[:10]).date()
    except Exception: return fallback

def skill_evidence(bundle, term, mapping=True):
    aliases=_aliases(term,mapping); structured=0.0; recent_ok=False; sources=[]; intervals=[]
    now=datetime.now().date(); recent_cutoff=now-timedelta(days=548)
    for s in bundle.get('skills',[]):
        if any(_text_has(s.get('skill'),a) or _text_has(a,s.get('skill')) for a in aliases):
            years=float(s.get('years') or 0); structured=max(structured,years)
            last=_date_value(s.get('last_used'),datetime(1900,1,1).date())
            recent_ok=recent_ok or bool(s.get('recent')) or last>=recent_cutoff
            sources.append({'source':'structured_skill','label':s.get('skill'),'years':years,'recent':bool(s.get('recent'))})
    for exp in bundle.get('experience',[]):
        text=' '.join(str(exp.get(k) or '') for k in ('title','skills','description'))
        if not any(_text_has(text,a) for a in aliases): continue
        start=_date_value(exp.get('start_date'),now); end=_date_value(exp.get('end_date'),now)
        if end<start: start,end=end,start
        intervals.append((start,end)); current=not exp.get('end_date') or end>=recent_cutoff
        recent_ok=recent_ok or current
        sources.append({'source':'employment','label':exp.get('title') or exp.get('company'),'start':str(start),'end':str(end),'recent':current})
    # Merge overlapping employment ranges so the same time period is never double-counted.
    merged=[]
    for start,end in sorted(intervals):
        if merged and start<=merged[-1][1]+timedelta(days=1): merged[-1]=(merged[-1][0],max(merged[-1][1],end))
        else: merged.append((start,end))
    employment_years=sum((end-start).days+1 for start,end in merged)/365.25
    title_text=' '.join(str(bundle.get(k) or '') for k in ('current_title','profession','specialty'))
    title_match=any(_text_has(title_text,a) for a in aliases)
    if title_match:
        recent_ok=True; sources.append({'source':'current_profile','label':bundle.get('current_title') or bundle.get('profession'),'recent':True})
    found=bool(sources)
    if not found:
        resume=bundle.get('resume_text') or ''
        if any(_text_has(resume,a) for a in aliases):
            found=True; sources.append({'source':'resume','label':term,'recent':False})
    years=max(structured,employment_years)
    return {'term':term,'found':found,'years':round(years,2),'recent':recent_ok,'sources':sources}

def skill_match(bundle, term, min_years=0, recent=False, mapping=True):
    evidence=skill_evidence(bundle,term,mapping)
    ok=evidence['found'] and evidence['years']>=float(min_years or 0) and (not recent or evidence['recent'])
    return ok,evidence['years']

def _boolean_tokens(expression):
    tokens=[]; i=0; text=expression or ''
    while i<len(text):
        if text[i].isspace(): i+=1; continue
        if text[i] in '()': tokens.append((text[i],text[i])); i+=1; continue
        if text[i]=='"':
            j=i+1
            while j<len(text) and text[j]!='"': j+=1
            if j>=len(text): raise BooleanSyntaxError(f'Unterminated quoted phrase at character {i+1}')
            phrase=text[i+1:j].strip()
            if not phrase: raise BooleanSyntaxError('Quoted phrase cannot be empty')
            tokens.append(('WORD',phrase)); i=j+1; continue
        j=i
        while j<len(text) and not text[j].isspace() and text[j] not in '()"': j+=1
        word=text[i:j]; upper=word.upper()
        tokens.append((upper if upper in ('AND','OR','NOT') else 'WORD',word)); i=j
    return tokens

def parse_boolean(expression):
    tokens=_boolean_tokens((expression or '').strip())
    if not tokens: raise BooleanSyntaxError('Boolean expression is empty')
    pos=0
    def primary():
        nonlocal pos
        if pos>=len(tokens): raise BooleanSyntaxError('Expected a term at end of expression')
        typ,val=tokens[pos]
        if typ=='NOT': pos+=1; return ('NOT',primary())
        if typ=='(':
            pos+=1
            if pos<len(tokens) and tokens[pos][0]==')': raise BooleanSyntaxError('Empty parentheses are not allowed')
            node=or_expr()
            if pos>=len(tokens) or tokens[pos][0]!=')': raise BooleanSyntaxError('Missing closing parenthesis')
            pos+=1; return node
        if typ in ('AND','OR',')'): raise BooleanSyntaxError(f'Expected a term, found {val!r}')
        words=[]
        while pos<len(tokens) and tokens[pos][0]=='WORD': words.append(tokens[pos][1]); pos+=1
        raw=' '.join(words).strip()
        match=re.fullmatch(r'(.+?)\s+(?:(RECENT)\s+)?OVER\s+(\d+(?:\.\d+)?)\s+YRS',raw,re.I)
        if match: return ('TERM',match.group(1).strip(),float(match.group(3)),bool(match.group(2)))
        if re.search(r'\b(?:RECENT\s+)?OVER\b|\bYRS\b',raw,re.I): raise BooleanSyntaxError(f'Malformed experience condition: {raw!r}')
        return ('TERM',raw,0.0,False)
    def and_expr():
        nonlocal pos
        node=primary()
        while pos<len(tokens) and tokens[pos][0]=='AND': pos+=1; node=('AND',node,primary())
        return node
    def or_expr():
        nonlocal pos
        node=and_expr()
        while pos<len(tokens) and tokens[pos][0]=='OR': pos+=1; node=('OR',node,and_expr())
        return node
    tree=or_expr()
    if pos!=len(tokens):
        typ,val=tokens[pos]
        if typ==')': raise BooleanSyntaxError('Unexpected closing parenthesis')
        raise BooleanSyntaxError(f'Missing AND or OR before {val!r}')
    return tree

def eval_boolean_tree(bundle, tree, mapping=True, evidence=None):
    op=tree[0]
    if op=='TERM':
        detail=skill_evidence(bundle,tree[1],mapping)
        if evidence is not None: evidence.append(detail)
        return detail['found'] and detail['years']>=tree[2] and (not tree[3] or detail['recent'])
    if op=='NOT': return not eval_boolean_tree(bundle,tree[1],mapping,evidence)
    left=eval_boolean_tree(bundle,tree[1],mapping,evidence)
    right=eval_boolean_tree(bundle,tree[2],mapping,evidence)
    return (left and right) if op=='AND' else (left or right)

def eval_boolean(bundle, expression, mapping=True):
    if not (expression or '').strip(): return True
    return bool(eval_boolean_tree(bundle,parse_boolean(expression),mapping))

def resolve_postal(postal):
    return POSTAL_COORDINATES.get(str(postal or '').strip().upper())

def distance_miles(lat1,lon1,lat2,lon2):
    p1,p2=math.radians(float(lat1)),math.radians(float(lat2)); dp=math.radians(float(lat2)-float(lat1)); dl=math.radians(float(lon2)-float(lon1))
    a=math.sin(dp/2)**2+math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 3958.7613*2*math.atan2(math.sqrt(a),math.sqrt(1-a))

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
    tenant_id=int(crit.get('_tenant_id') or 1)
    candidates=qall(conn,"SELECT id FROM candidates WHERE tenant_id=? AND lower(status)!='archived'",(tenant_id,))
    out=[]; mapping=not bool(crit.get('without_mapping')); excluded={int(x) for x in (crit.get('exclude_candidate_ids') or [])}
    raw=crit.get('raw_boolean','').strip(); raw_tree=parse_boolean(raw) if raw else None
    center=None; radius=crit.get('radius_miles',crit.get('radius'))
    if radius not in (None,''):
        try: radius=float(radius)
        except Exception: raise ValueError('radius_miles must be numeric')
        if radius<=0: raise ValueError('radius_miles must be greater than zero')
        center=resolve_postal(crit.get('zip'))
        if not center: raise ValueError(f"Postal code {crit.get('zip')!r} could not be resolved for radius search")
    for row in candidates:
        if row['id'] in excluded: continue
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
        for requirement in crit.get('require') or []:
            if requirement.get('term'):
                ev=skill_evidence(b,requirement['term'],mapping)
                if ev['found']: reasons.append({'type':'skill','term':requirement['term'],'years':ev['years'],'recent':ev['recent'],'sources':ev['sources']})
        for ex in crit.get('exclude') or []:
            term=ex.get('term') if isinstance(ex,dict) else ex
            ok,_=skill_match(b,term,0,False,mapping)
            if ok: failed=True; break
        if failed: continue
        state=(crit.get('state') or '').strip()
        if state and norm(state)!=norm(b.get('state')): continue
        if center:
            lat=b.get('latitude'); lon=b.get('longitude')
            if lat is None or lon is None:
                coords=resolve_postal(b.get('zip')); lat,lon=coords if coords else (None,None)
            if lat is None or lon is None: continue
            miles=distance_miles(center[0],center[1],lat,lon)
            if miles>radius: continue
            b['distance_miles']=round(miles,1); score+=max(0,10-(miles/radius)*10); reasons.append({'type':'distance','miles':round(miles,1),'radius':radius})
        avail=crit.get('available_before')
        if avail and b.get('availability_date') and b['availability_date']>avail: continue
        pay_min=crit.get('pay_min'); pay_max=crit.get('pay_max')
        if pay_min not in (None,'') and (b.get('pay_max') or 0) < float(pay_min): continue
        if pay_max not in (None,'') and (b.get('pay_min') or 0) > float(pay_max): continue
        if raw_tree:
            boolean_evidence=[]
            if not eval_boolean_tree(b,raw_tree,mapping,boolean_evidence): continue
            score+=20; reasons.append({'type':'boolean','expression':raw,'evidence':boolean_evidence})
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

def job_search_criteria(job, tenant_id=1):
    skills=[]
    for raw in re.split(r'[|,;\n]+',job.get('required_skills') or ''):
        term=raw.strip()
        if not term: continue
        m=re.fullmatch(r'(.+?)\s+(?:(RECENT)\s+)?OVER\s+(\d+(?:\.\d+)?)\s+YRS',term,re.I)
        legacy=re.fullmatch(r'(.+?):(\d+(?:\.\d+)?)(?::(recent|true|false))?',term,re.I)
        skills.append({'term':m.group(1).strip() if m else (legacy.group(1).strip() if legacy else term),'years':float(m.group(3)) if m else (float(legacy.group(2)) if legacy else 0),'recent':bool(m and m.group(2)) or bool(legacy and norm(legacy.group(3)) in ('recent','true')),'operator':'AND'})
    return {'profession':job.get('profession') or '','specialty':job.get('specialty') or '',
            'title':'','require':skills,'state':job.get('state') or '','zip':job.get('zip') or '',
            'radius_miles':50 if job.get('zip') and resolve_postal(job.get('zip')) else '',
            'pay_max':job.get('pay_max') if job.get('pay_max') is not None else '',
            'available_before':job.get('start_date') or '','_tenant_id':tenant_id}

def match_jobs_for_candidate(conn, candidate_id, tenant_id):
    bundle=candidate_bundle(conn,candidate_id)
    if not bundle or int(bundle.get('tenant_id') or 1)!=int(tenant_id): return []
    rows=[]
    for job in qall(conn,"SELECT * FROM jobs WHERE tenant_id=? AND lower(status)='open' AND archived_at IS NULL",(tenant_id,)):
        crit=job_search_criteria(job,tenant_id); crit['state']=''; crit['zip']=''; crit['radius_miles']=''; crit['available_before']=''
        require=crit.get('require') or []; score=0; reasons=[]; matched=0
        for req in require:
            ev=skill_evidence(bundle,req['term'],True); ok=ev['found'] and ev['years']>=float(req.get('years') or 0) and (not req.get('recent') or ev['recent'])
            if ok: matched+=1; score+=20; reasons.append({'type':'skill','term':req['term'],'years':ev['years'],'recent':ev['recent'],'sources':ev['sources']})
        if job.get('profession') and norm(job['profession']) in norm(bundle.get('profession')): score+=20; reasons.append({'type':'profession','value':job['profession']})
        if job.get('specialty') and norm(job['specialty']) in norm(bundle.get('specialty')): score+=10; reasons.append({'type':'specialty','value':job['specialty']})
        if require and matched==0: continue
        row=dict(job); row['relevance']=round(min(99,score+(bundle.get('credibility_score') or 0)/10),1); row['match_reasons']=reasons; rows.append(row)
    rows.sort(key=lambda x:-x['relevance']); return rows

def deterministic_resume_parse(text):
    text=(text or '').strip()
    if not text: raise ValueError('resume_text is required')
    lines=[x.strip() for x in text.splitlines() if x.strip()]
    email_match=re.search(r'[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}',text,re.I)
    phone_match=re.search(r'(?:\+?\d[\d ()-]{7,}\d)',text)
    known={alias for key,vals in SYNONYMS.items() for alias in ({key}|set(vals))}
    known.update({'python','sql','java','c++','c #','c#','azure','databricks','spark','kafka','terraform','go','airflow','dbt','mainframe','banking','developer','nursing','epic','cerner'})
    skills=[]
    for skill in sorted(known,key=len,reverse=True):
        if _text_has(text,skill) and not any(norm(x['skill'])==norm(skill) for x in skills): skills.append({'skill':skill.title() if skill.islower() else skill,'years':0,'recent':False})
    years_match=re.search(r'(\d+(?:\.\d+)?)\s*(?:\+\s*)?years?',text,re.I)
    if years_match and skills:
        for item in skills[:3]: item['years']=float(years_match.group(1))
    title=''
    title_terms=('data engineer','software engineer','java developer','registered nurse','business analyst','project manager','cloud engineer','developer')
    for candidate in title_terms:
        if _text_has(text,candidate): title=candidate.title(); break
    name=''
    if lines and len(lines[0])<80 and not email_match and not any(ch.isdigit() for ch in lines[0]): name=lines[0]
    parts=name.split(None,1)
    return {'resume_text':text,'first_name':parts[0] if parts else '','last_name':parts[1] if len(parts)>1 else '',
            'email':email_match.group(0) if email_match else '','phone':phone_match.group(0).strip() if phone_match else '',
            'current_title':title,'skills':skills,'experience':[],
            'review_required':True,'parser':'deterministic-local','warnings':['Dates and employers require recruiter review before commit.']}

def connector_config_json(config):
    config=config or {}
    if not isinstance(config,dict):raise ValueError('config must be an object')
    forbidden=[]
    def walk(value,path=''):
        if not isinstance(value,dict):return
        for key,item in value.items():
            label=(path+'.'+str(key)).strip('.')
            if re.search(r'(?:password|secret|token|api[_-]?key|private[_-]?key)',str(key),re.I):forbidden.append(label)
            elif isinstance(item,dict):walk(item,label)
    walk(config)
    if forbidden:raise ValueError('Secret values are not accepted; store only credential_ref metadata ('+', '.join(forbidden)+')')
    return json.dumps(config,separators=(',',':'))

TRANSITIONS = {
    'interested': {'interested':{'qualified','rejected'},'qualified':{'rejected','interested'},'rejected':{'interested'}},
    'submission': {'draft':{'submitted','withdrawn'},'submitted':{'client_review','interview','rejected','withdrawn'},'client_review':{'interview','offer','rejected'},'interview':{'offer','rejected'},'offer':{'hired','rejected','withdrawn'},'hired':set(),'rejected':set(),'withdrawn':set()},
    'interview': {'scheduled':{'scheduled','completed','cancelled','no_show'},'completed':set(),'cancelled':{'scheduled'},'no_show':{'scheduled'}},
    'assessment': {'invited':{'in_progress','completed','cancelled'},'in_progress':{'completed','cancelled'},'completed':{'reviewed'},'reviewed':set(),'cancelled':set()},
    'start': {'confirmed':{'active','cancelled'},'active':{'completed','cancelled'},'completed':set(),'cancelled':set()},
    'assignment': {'pending':{'active','cancelled'},'active':{'on_hold','ending','completed','terminated'},'on_hold':{'active','terminated','completed'},'ending':{'completed','terminated'},'completed':set(),'terminated':set(),'cancelled':set()},
    'timesheet': {'draft':{'submitted'},'submitted':{'approved','rejected'},'approved':{'reopened','invoiced'},'rejected':{'draft','submitted'},'reopened':{'draft','submitted'},'invoiced':set()},
    'expense': {'draft':{'submitted'},'submitted':{'approved','rejected'},'approved':{'reopened','invoiced'},'rejected':{'draft','submitted'},'reopened':{'draft','submitted'},'invoiced':set()},
    'invoice': {'draft':{'issued','void'},'issued':{'part_paid','paid','void'},'part_paid':{'part_paid','paid','void'},'paid':set(),'void':set()},
}

def ensure_transition(kind,current,target):
    current=norm(current); target=norm(target)
    if current==target: return
    if target not in TRANSITIONS.get(kind,{}).get(current,set()):
        raise ValueError(f'Invalid {kind} transition from {current!r} to {target!r}')

def record_transition(conn,u,kind,entity_id,current,target,note=''):
    conn.execute('INSERT INTO workflow_history(entity_type,entity_id,from_status,to_status,note,user_id,created_at,tenant_id) VALUES(?,?,?,?,?,?,?,?)',(kind,entity_id,current,target,note,u['id'],utcnow(),u['tenant_id']))

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
        self._body_error=None
        if not raw: return {}
        ctype=(self.headers.get('Content-Type') or '').split(';',1)[0].strip().lower()
        if ctype and ctype!='application/json':
            self._body_error='Content-Type must be application/json'; return None
        try:
            value=json.loads(raw.decode('utf-8'))
        except (UnicodeDecodeError,json.JSONDecodeError):
            self._body_error='Malformed JSON'; return None
        if not isinstance(value,dict):
            self._body_error='JSON request body must be an object'; return None
        return value
    def _cookies(self):
        out={}
        for part in self.headers.get('Cookie','').split(';'):
            if '=' in part:
                k,v=part.strip().split('=',1); out[k]=v
        return out
    def _user(self, conn):
        tok=self._cookies().get('ats_session') or self.headers.get('X-Session-Token')
        if not tok: return None
        return qone(conn,'''SELECT u.* FROM sessions s JOIN users u ON u.id=s.user_id AND u.tenant_id=s.tenant_id WHERE s.token=? AND s.expires_at>? AND u.active=1''',(tok,utcnow()))
    def _permission_module(self):
        path=urllib.parse.urlparse(self.path).path.lower()
        mapping=[('/api/candidate-documents','document'),('/api/assessments','assessment'),('/api/candidates','candidate'),('/api/jobs','job'),('/api/submissions','submission'),('/api/interviews','interview'),('/api/onboarding','onboarding'),('/api/assignments','assignment'),('/api/timesheets','timesheet'),('/api/expenses','expense'),('/api/invoices','invoice'),('/api/companies','crm'),('/api/contacts','crm'),('/api/leads','crm'),('/api/opportunities','crm'),('/api/reports','report'),('/api/communications','communication'),('/api/hotlists','hotlist'),('/api/vms','vms'),('/api/suppliers','supplier'),('/api/r14','r14')]
        return next((module for prefix,module in mapping if path.startswith(prefix)),None)
    def _r23_data_scope(self,conn,u,module):
        token=self._cookies().get('ats_session') or self.headers.get('X-Session-Token')
        ctx=effective_context(conn,u,token)
        selected=ctx.get('selected')
        if not selected:return 'all'
        permission=next((x for x in ctx.get('permissions') or [] if x.get('module')==module),None)
        if not permission:return None
        scope=str(permission.get('data_scope') or 'all').strip().lower()
        return scope if scope in {'own','team','all'} else 'all'
    def _candidate_scope_allows(self,conn,u,candidate_id):
        if u['role'] not in INTERNAL_ROLES:return True
        scope=self._r23_data_scope(conn,u,'candidate')
        if scope!='own':return True
        row=qone(conn,'SELECT owner_user_id FROM candidates WHERE id=? AND tenant_id=?',(candidate_id,u['tenant_id']))
        if not row:return None
        try:return int(row.get('owner_user_id'))==int(u['id'])
        except (TypeError,ValueError):return False
    def _need(self, conn, perm=None, roles=None):
        u=self._user(conn)
        if not u: self._json({'error':'Authentication required'},401); return None
        if roles and u['role'] not in roles and u['role']!='admin': self._json({'error':'Permission denied'},403); return None
        if perm:
            ps=ROLE_PERMISSIONS.get(u['role'],set())
            if '*' not in ps and perm not in ps: self._json({'error':'Permission denied'},403); return None
        module=perm or self._permission_module()
        if module and permission_denied_by_override(conn,u['tenant_id'],u['role'],module,self.command):
            self._json({'error':'Permission denied by tenant policy'},403); return None
        if module and r23_permission_denied(
            conn,
            u,
            self._cookies().get('ats_session') or self.headers.get('X-Session-Token'),
            module,
            self.command,
            urllib.parse.urlparse(self.path).path,
        ):
            self._json({'error':'Permission denied by active profile'},403); return None
        return u
    def _tenant_row(self,conn,table,row_id,u):
        return qone(conn,f'SELECT * FROM {table} WHERE id=? AND tenant_id=?',(row_id,u['tenant_id']))
    def _binary(self,raw,content_type='application/octet-stream',name=None,status=200):
        self.send_response(status); self.send_header('Content-Type',content_type); self.send_header('Content-Length',str(len(raw)))
        self.send_header('Cache-Control','no-store')
        if name:
            safe_name=re.sub('[^A-Za-z0-9._-]','_',name)
            self.send_header('Content-Disposition',f'attachment; filename="{safe_name}"')
        self.end_headers(); self.wfile.write(raw)
    def _serve_static(self,path):
        if path=='/': path='/index.html'
        rel=urllib.parse.unquote(path.split('?',1)[0]).lstrip('/')
        fp=(WEB_DIR/rel).resolve()
        try:
            fp.relative_to(WEB_DIR.resolve())
        except ValueError:
            fp=WEB_DIR/'index.html'
        if not fp.is_file():
            fp=WEB_DIR/'index.html'
        raw=fp.read_bytes(); ctype=mimetypes.guess_type(str(fp))[0] or 'application/octet-stream'
        self.send_response(200); self.send_header('Content-Type',ctype); self.send_header('Content-Length',str(len(raw)))
        self.send_header('Cache-Control','no-cache' if fp.name=='index.html' else 'public, max-age=3600'); self.end_headers(); self.wfile.write(raw)
    def do_GET(self):
        p=urllib.parse.urlparse(self.path); path=p.path; qs=urllib.parse.parse_qs(p.query)
        if not path.startswith('/api/'): return self._serve_static(path)
        conn=db()
        try:
            if path=='/api/health': return self._json({'ok':True,'app':APP_NAME,'version':APP_VERSION,'db':str(DB_PATH),'persistence':'supabase-postgrest-cas' if REMOTE_PERSISTENCE_ENABLED else 'local-sqlite','identity_model':IDENTITY_MODEL})
            if path=='/api/me':
                u=self._need(conn)
                if u: u.pop('pass_hash',None); return self._json(u)
                return
            if r22_public_get(self,conn,path,qs): return
            if r23c_public_get(self,conn,path,qs): return
            u=self._need(conn)
            if not u: return
            if parity_get(self,conn,u,path,qs): return
            if r14_get(self,conn,u,path,qs): return
            if r18_get(self,conn,u,path,qs): return
            if r19_get(self,conn,u,path,qs): return
            if r22_get(self,conn,u,path,qs): return
            if r23_get(self,conn,u,path,qs): return
            if r23c_get(self,conn,u,path,qs): return
            if r23d_get(self,conn,u,path,qs): return
            if path=='/api/dashboard': return self._json(self.dashboard(conn,u))
            if path=='/api/supplier/candidates':
                if u['role']!='supplier':return self._json({'error':'Permission denied'},403)
                return self._json(qall(conn,"SELECT id,first_name,last_name,email,current_title,status FROM candidates WHERE tenant_id=? AND supplier_id=? AND lower(status)!='archived' ORDER BY last_name",(u['tenant_id'],u.get('supplier_id'))))
            if path=='/api/candidates':
                if u['role'] not in INTERNAL_ROLES: return self._json({'error':'Permission denied'},403)
                term=(qs.get('q') or [''])[0].strip(); sql="SELECT * FROM candidates WHERE tenant_id=?"; params=[u['tenant_id']]
                candidate_scope=self._r23_data_scope(conn,u,'candidate')
                if candidate_scope=='own':
                    sql+=" AND owner_user_id=?";params.append(u['id'])
                if (qs.get('include_archived') or ['0'])[0]!='1': sql+=" AND lower(status)!='archived'"
                if term: sql+=" AND (first_name||' '||last_name LIKE ? OR email LIKE ? OR phone LIKE ? OR current_title LIKE ? OR profession LIKE ?)"; params += ['%'+term+'%']*5
                sql+=' ORDER BY updated_at DESC LIMIT 500'; return self._json(qall(conn,sql,params))
            m=re.fullmatch(r'/api/candidates/(\d+)',path)
            if m:
                cid=int(m.group(1));
                if u['role'] not in INTERNAL_ROLES|{'candidate','worker'}:return self._json({'error':'Permission denied'},403)
                if u['role'] in ('candidate','worker') and u.get('candidate_id')!=cid: return self._json({'error':'Permission denied'},403)
                scope_allowed=self._candidate_scope_allows(conn,u,cid)
                if scope_allowed is None:return self._json({'error':'Not found'},404)
                if scope_allowed is False:return self._json({'error':'Permission denied'},403)
                b=candidate_bundle(conn,cid,u['tenant_id']); return self._json(b or {'error':'Not found'},200 if b else 404)
            m=re.fullmatch(r'/api/candidates/(\d+)/matches',path)
            if m:
                cid=int(m.group(1))
                if u['role'] not in INTERNAL_ROLES and u.get('candidate_id')!=cid: return self._json({'error':'Permission denied'},403)
                scope_allowed=self._candidate_scope_allows(conn,u,cid)
                if scope_allowed is None:return self._json({'error':'Not found'},404)
                if scope_allowed is False:return self._json({'error':'Permission denied'},403)
                return self._json({'candidate_id':cid,'results':match_jobs_for_candidate(conn,cid,u['tenant_id'])})
            m=re.fullmatch(r'/api/candidate-documents/(\d+)/download',path)
            if m:
                permissions=ROLE_PERMISSIONS.get(u['role'],set())
                if '*' not in permissions and 'document' not in permissions and u['role'] not in ('candidate','worker'):
                    return self._json({'error':'Permission denied'},403)
                doc=self._tenant_row(conn,'candidate_documents',int(m.group(1)),u)
                if not doc: return self._json({'error':'Not found'},404)
                if u['role'] in ('candidate','worker') and u.get('candidate_id')!=doc['candidate_id']: return self._json({'error':'Permission denied'},403)
                ver=qone(conn,'SELECT * FROM candidate_document_versions WHERE document_id=? AND tenant_id=? ORDER BY version DESC LIMIT 1',(doc['id'],u['tenant_id']))
                if not ver or ver.get('content') is None:return self._json({'error':'Document content not found'},404)
                return self._binary(bytes(ver['content']),ver.get('mime_type') or 'application/octet-stream',ver.get('file_name') or doc.get('file_name'))

            # R12B_READ_HELPERS
            if path=='/api/hotlists-archive':
                if u['role'] not in RECRUITING_ROLES:
                    return self._json(
                        {'error':'Permission denied'},
                        403
                    )

                rows=qall(
                    conn,
                    '''SELECT
                           h.*,
                           u.name owner_name,
                           (
                               SELECT COUNT(*)
                               FROM hotlist_members hm
                               WHERE hm.hotlist_id=h.id
                                 AND hm.tenant_id=h.tenant_id
                           ) member_count
                       FROM hotlists h
                       LEFT JOIN users u
                              ON u.id=h.owner_user_id
                       WHERE h.tenant_id=?
                         AND h.archived_at IS NOT NULL
                       ORDER BY h.updated_at DESC,h.id DESC''',
                    (u['tenant_id'],)
                )

                return self._json(rows)

            if path=='/api/hotlists':
                if u['role'] not in RECRUITING_ROLES:return self._json({'error':'Permission denied'},403)
                rows=qall(conn,'''SELECT h.*,u.name owner_name,(SELECT COUNT(*) FROM hotlist_members hm WHERE hm.hotlist_id=h.id AND hm.tenant_id=h.tenant_id) member_count FROM hotlists h LEFT JOIN users u ON u.id=h.owner_user_id WHERE h.tenant_id=? AND h.archived_at IS NULL ORDER BY h.created_at DESC''',(u['tenant_id'],))
                return self._json(rows)
            m=re.fullmatch(r'/api/hotlists/(\d+)',path)
            if m:
                hid=int(m.group(1)); h=qone(conn,'SELECT * FROM hotlists WHERE id=? AND tenant_id=?',(hid,u['tenant_id']));
                if not h: return self._json({'error':'Not found'},404)
                h['members']=qall(conn,'''SELECT hm.*,c.first_name,c.last_name,c.current_title,c.city,c.state,c.email FROM hotlist_members hm JOIN candidates c ON c.id=hm.candidate_id WHERE hm.hotlist_id=? ORDER BY hm.created_at DESC''',(hid,))
                if h.get('mode')=='dynamic' and h.get('saved_search_json'):
                    try:
                        saved=json.loads(h['saved_search_json']);saved['_tenant_id']=u['tenant_id'];h['dynamic_results']=perform_search(conn,saved)
                    except Exception: h['dynamic_results']=[]
                return self._json(h)
            if path=='/api/jobs':
                if u['role'] not in INTERNAL_ROLES|{'client','supplier','candidate','worker'}:
                    return self._json({'error':'Permission denied'},403)
                sql='''SELECT j.*,co.name company_name,ct.first_name||' '||ct.last_name contact_name,u.name recruiter_name,
                 (SELECT COUNT(*) FROM submissions s WHERE s.job_id=j.id) submission_count,
                 (SELECT COUNT(*) FROM interested_candidates i WHERE i.job_id=j.id) interested_count,
                 (SELECT d.status FROM job_distribution d WHERE d.job_id=j.id AND d.tenant_id=j.tenant_id ORDER BY d.id DESC LIMIT 1) harvest_status
                 FROM jobs j LEFT JOIN companies co ON co.id=j.company_id LEFT JOIN contacts ct ON ct.id=j.contact_id LEFT JOIN users u ON u.id=j.primary_recruiter_id WHERE j.tenant_id=?'''; params=[u['tenant_id']]
                if (qs.get('include_archived') or ['0'])[0]!='1': sql+=' AND j.archived_at IS NULL'
                if u['role']=='client': sql+=' AND j.company_id=?'; params.append(u['company_id'])
                if u['role']=='supplier': sql+=' AND j.id IN (SELECT job_id FROM supplier_releases WHERE supplier_id=? AND tenant_id=? AND status="Open")';params.extend([u.get('supplier_id'),u['tenant_id']])
                if u['role'] in ('candidate','worker'):sql+=' AND j.status="Open"'
                sql+=' ORDER BY CASE j.status WHEN "Open" THEN 0 ELSE 1 END,j.created_at DESC'
                rows=qall(conn,sql,params)
                if u['role'] in ('candidate','worker','supplier','client'):
                    for row in rows:
                        private_fields=('pay_min','pay_max','external_vms_id') if u['role']=='client' else ('bill_min','bill_max','external_vms_id','submission_guidelines_override')
                        for private_field in private_fields:
                            row.pop(private_field,None)
                return self._json(rows)
            m=re.fullmatch(r'/api/jobs/(\d+)',path)
            if m:
                if u['role'] not in INTERNAL_ROLES|{'client','supplier','candidate','worker'}:
                    return self._json({'error':'Permission denied'},403)
                jid=int(m.group(1)); j=qone(conn,'''SELECT j.*,co.name company_name,ct.first_name||' '||ct.last_name contact_name,co.submission_guidelines company_submission_guidelines FROM jobs j LEFT JOIN companies co ON co.id=j.company_id LEFT JOIN contacts ct ON ct.id=j.contact_id WHERE j.id=? AND j.tenant_id=?''',(jid,u['tenant_id']))
                if not j: return self._json({'error':'Not found'},404)
                if u['role']=='client' and j.get('company_id')!=u.get('company_id'): return self._json({'error':'Permission denied'},403)
                if u['role']=='supplier':
                    rel=qone(conn,"SELECT 1 ok FROM supplier_releases WHERE supplier_id=? AND job_id=? AND tenant_id=? AND status='Open'",(u.get('supplier_id'),jid,u['tenant_id']))
                    if not rel: return self._json({'error':'Permission denied'},403)
                if u['role'] in ('candidate','worker') and j.get('status')!='Open': return self._json({'error':'Permission denied'},403)
                j['interested']=qall(conn,'''SELECT i.*,c.first_name,c.last_name,c.current_title,c.email FROM interested_candidates i JOIN candidates c ON c.id=i.candidate_id WHERE i.job_id=? AND i.tenant_id=? ORDER BY i.updated_at DESC''',(jid,u['tenant_id'])) if u['role'] in INTERNAL_ROLES|{'client'} else []
                if u['role']=='supplier':j['submissions']=qall(conn,'''SELECT s.*,c.first_name,c.last_name,c.current_title,c.email FROM submissions s JOIN candidates c ON c.id=s.candidate_id WHERE s.job_id=? AND s.recruiter_id=? AND s.tenant_id=? ORDER BY s.updated_at DESC''',(jid,u['id'],u['tenant_id']))
                elif u['role'] in INTERNAL_ROLES|{'client'}:j['submissions']=qall(conn,'''SELECT s.*,c.first_name,c.last_name,c.current_title,c.email FROM submissions s JOIN candidates c ON c.id=s.candidate_id WHERE s.job_id=? AND s.tenant_id=? ORDER BY s.updated_at DESC''',(jid,u['tenant_id']))
                else:j['submissions']=[]
                j['users']=qall(conn,'''SELECT ju.*,u.name,u.email FROM job_users ju JOIN users u ON u.id=ju.user_id WHERE ju.job_id=? AND ju.tenant_id=?''',(jid,u['tenant_id'])) if u['role'] in INTERNAL_ROLES else []
                j['supplier_releases']=qall(conn,'''SELECT sr.*,s.name supplier_name FROM supplier_releases sr JOIN suppliers s ON s.id=sr.supplier_id WHERE sr.job_id=? AND sr.tenant_id=?''',(jid,u['tenant_id'])) if u['role'] in INTERNAL_ROLES else []
                if u['role'] in ('candidate','worker','supplier','client'):
                    private_fields=('pay_min','pay_max','external_vms_id') if u['role']=='client' else ('bill_min','bill_max','external_vms_id','submission_guidelines_override')
                    for private_field in private_fields:
                        j.pop(private_field,None)
                return self._json(j)
            m=re.fullmatch(r'/api/jobs/(\d+)/(search-criteria|matches)',path)
            if m:
                if u['role'] not in RECRUITING_ROLES:return self._json({'error':'Permission denied'},403)
                job=self._tenant_row(conn,'jobs',int(m.group(1)),u)
                if not job:return self._json({'error':'Not found'},404)
                criteria=job_search_criteria(job,u['tenant_id'])
                if m.group(2)=='search-criteria':return self._json(criteria)
                results=perform_search(conn,criteria)
                return self._json({'job_id':job['id'],'criteria':criteria,'count':len(results),'results':results})
            if path=='/api/companies':
                if u['role'] not in INTERNAL_ROLES: return self._json({'error':'Permission denied'},403)
                return self._json(qall(conn,'SELECT c.*,(SELECT COUNT(*) FROM contacts x WHERE x.company_id=c.id AND x.tenant_id=c.tenant_id) contact_count,(SELECT COUNT(*) FROM jobs j WHERE j.company_id=c.id AND j.tenant_id=c.tenant_id) job_count FROM companies c WHERE c.tenant_id=? ORDER BY c.name',(u['tenant_id'],)))
            if path=='/api/contacts':
                if u['role'] not in INTERNAL_ROLES:return self._json({'error':'Permission denied'},403)
                return self._json(qall(conn,'SELECT ct.*,co.name company_name FROM contacts ct LEFT JOIN companies co ON co.id=ct.company_id WHERE ct.tenant_id=? ORDER BY ct.last_name,ct.first_name',(u['tenant_id'],)))
            if path=='/api/leads':
                if u['role'] not in INTERNAL_ROLES:return self._json({'error':'Permission denied'},403)
                return self._json(qall(conn,'''SELECT l.*,co.name company_name,ct.first_name||' '||ct.last_name contact_name,u.name owner_name FROM leads l LEFT JOIN companies co ON co.id=l.company_id LEFT JOIN contacts ct ON ct.id=l.contact_id LEFT JOIN users u ON u.id=l.owner_user_id WHERE l.tenant_id=? ORDER BY l.created_at DESC''',(u['tenant_id'],)))
            if path=='/api/opportunities':
                if u['role'] not in INTERNAL_ROLES:return self._json({'error':'Permission denied'},403)
                return self._json(qall(conn,'''SELECT o.*,co.name company_name,ct.first_name||' '||ct.last_name contact_name,u.name owner_name FROM opportunities o LEFT JOIN companies co ON co.id=o.company_id LEFT JOIN contacts ct ON ct.id=o.contact_id LEFT JOIN users u ON u.id=o.owner_user_id WHERE o.tenant_id=? ORDER BY CASE o.stage WHEN 'Negotiation' THEN 1 WHEN 'Presentation' THEN 2 WHEN 'Qualified' THEN 3 ELSE 4 END,o.expected_close''',(u['tenant_id'],)))
            if path=='/api/shifts':
                if u['role'] not in INTERNAL_ROLES|{'worker'}:return self._json({'error':'Permission denied'},403)
                sql='''SELECT sh.*,c.first_name,c.last_name,j.title job_title,co.name company_name FROM shifts sh JOIN candidates c ON c.id=sh.candidate_id LEFT JOIN assignments a ON a.id=sh.assignment_id LEFT JOIN jobs j ON j.id=a.job_id LEFT JOIN companies co ON co.id=a.company_id WHERE sh.tenant_id=?'''; params=[u['tenant_id']]
                if u['role']=='worker': sql+=' AND sh.candidate_id=?';params.append(u['candidate_id'])
                sql+=' ORDER BY sh.shift_date,sh.start_time';return self._json(qall(conn,sql,params))
            if path=='/api/attendance':
                if u['role'] not in INTERNAL_ROLES|{'worker'}:return self._json({'error':'Permission denied'},403)
                sql='''SELECT at.*,sh.shift_date,sh.start_time,sh.end_time,c.first_name,c.last_name FROM attendance at LEFT JOIN shifts sh ON sh.id=at.shift_id JOIN candidates c ON c.id=at.candidate_id WHERE at.tenant_id=?''';params=[u['tenant_id']]
                if u['role']=='worker':sql+=' AND at.candidate_id=?';params.append(u['candidate_id'])
                return self._json(qall(conn,sql+' ORDER BY COALESCE(at.check_in,sh.shift_date) DESC',params))
            if path=='/api/job-distribution':
                if u['role'] not in INTERNAL_ROLES:return self._json({'error':'Permission denied'},403)
                return self._json(qall(conn,'''SELECT d.*,j.job_no,j.title job_title FROM job_distribution d JOIN jobs j ON j.id=d.job_id WHERE d.tenant_id=? ORDER BY d.published_at DESC''',(u['tenant_id'],)))
            if path=='/api/integrations':
                if u['role'] not in ('admin','teamlead'):return self._json({'error':'Permission denied'},403)
                return self._json(qall(conn,'SELECT * FROM integration_connectors WHERE tenant_id=? ORDER BY category,name',(u['tenant_id'],)))
            m=re.fullmatch(r'/api/integrations/(\d+)/logs',path)
            if m:
                if u['role'] not in ('admin','teamlead'):return self._json({'error':'Permission denied'},403)
                if not self._tenant_row(conn,'integration_connectors',int(m.group(1)),u):return self._json({'error':'Not found'},404)
                return self._json(qall(conn,'SELECT * FROM integration_logs WHERE connector_id=? AND tenant_id=? ORDER BY id DESC',(int(m.group(1)),u['tenant_id'])))
            if path=='/api/submissions':
                if u['role'] not in INTERNAL_ROLES|{'client','candidate','supplier'}:return self._json({'error':'Permission denied'},403)
                sql='''SELECT s.*,c.first_name,c.last_name,c.current_title,j.job_no,j.title job_title,co.name company_name FROM submissions s JOIN candidates c ON c.id=s.candidate_id JOIN jobs j ON j.id=s.job_id LEFT JOIN companies co ON co.id=j.company_id WHERE s.tenant_id=?'''; params=[u['tenant_id']]
                if u['role']=='client': sql+=' AND j.company_id=?'; params.append(u['company_id'])
                if u['role']=='candidate': sql+=' AND s.candidate_id=?'; params.append(u['candidate_id'])
                if u['role']=='supplier':sql+=' AND s.recruiter_id=?';params.append(u['id'])
                sql+=' ORDER BY s.updated_at DESC'; return self._json(qall(conn,sql,params))
            if path=='/api/interviews':
                if u['role'] not in INTERNAL_ROLES|{'client','candidate'}:return self._json({'error':'Permission denied'},403)
                sql='''SELECT i.*,s.job_id,s.candidate_id,c.first_name,c.last_name,j.job_no,j.title job_title,co.name company_name FROM interviews i JOIN submissions s ON s.id=i.submission_id JOIN candidates c ON c.id=s.candidate_id JOIN jobs j ON j.id=s.job_id LEFT JOIN companies co ON co.id=j.company_id WHERE i.tenant_id=?'''; params=[u['tenant_id']]
                if u['role']=='client': sql+=' AND j.company_id=?'; params.append(u['company_id'])
                if u['role']=='candidate': sql+=' AND c.id=?'; params.append(u['candidate_id'])
                sql+=' ORDER BY i.scheduled_at DESC'; return self._json(qall(conn,sql,params))

            m=re.fullmatch(
                r'/api/assessments/(\d+)',
                path
            )

            if m:
                if u['role'] not in INTERNAL_ROLES|{'candidate','worker'}:
                    return self._json(
                        {'error':'Permission denied'},
                        403
                    )

                aid=int(m.group(1))

                assessment=self._tenant_row(
                    conn,
                    'assessments',
                    aid,
                    u
                )

                if not assessment:
                    return self._json(
                        {'error':'Not found'},
                        404
                    )

                if (
                    u['role'] in ('candidate','worker')
                    and assessment['candidate_id']
                        !=u.get('candidate_id')
                ):
                    return self._json(
                        {'error':'Permission denied'},
                        403
                    )

                assessment['questions']=qall(
                    conn,
                    '''SELECT *
                       FROM assessment_questions
                       WHERE assessment_id=?
                         AND tenant_id=?
                       ORDER BY sort_order,id''',
                    (
                        aid,
                        u['tenant_id']
                    )
                )

                assessment['answers']=qall(
                    conn,
                    '''SELECT *
                       FROM assessment_answers
                       WHERE assessment_id=?
                         AND tenant_id=?
                       ORDER BY question_id,id''',
                    (
                        aid,
                        u['tenant_id']
                    )
                )

                return self._json(
                    assessment
                )

            if path=='/api/assessments':
                if u['role'] not in INTERNAL_ROLES|{'candidate','worker'}:return self._json({'error':'Permission denied'},403)
                sql='''SELECT a.*,c.first_name,c.last_name,j.job_no,j.title job_title FROM assessments a JOIN candidates c ON c.id=a.candidate_id LEFT JOIN jobs j ON j.id=a.job_id WHERE a.tenant_id=?''';params=[u['tenant_id']]
                if u['role'] in ('candidate','worker'):sql+=' AND a.candidate_id=?';params.append(u['candidate_id'])
                return self._json(qall(conn,sql+' ORDER BY a.invited_at DESC',params))
            if path=='/api/onboarding':
                if u['role'] not in INTERNAL_ROLES|{'candidate','worker'}:return self._json({'error':'Permission denied'},403)
                sql='''SELECT p.*,c.first_name,c.last_name,j.job_no,j.title job_title,(SELECT COUNT(*) FROM onboarding_requirements r WHERE r.package_id=p.id) req_count,(SELECT COUNT(*) FROM onboarding_requirements r WHERE r.package_id=p.id AND lower(r.status)='complete') complete_count FROM onboarding_packages p JOIN candidates c ON c.id=p.candidate_id LEFT JOIN jobs j ON j.id=p.job_id WHERE p.tenant_id=?'''; params=[u['tenant_id']]
                if u['role'] in ('candidate','worker'): sql+=' AND p.candidate_id=?'; params.append(u['candidate_id'])
                sql+=' ORDER BY p.created_at DESC'; return self._json(qall(conn,sql,params))
            m=re.fullmatch(r'/api/onboarding/(\d+)',path)
            if m:
                if u['role'] not in INTERNAL_ROLES|{'candidate','worker'}:
                    return self._json({'error':'Permission denied'},403)
                pid=int(m.group(1)); p=qone(conn,'SELECT * FROM onboarding_packages WHERE id=? AND tenant_id=?',(pid,u['tenant_id']));
                if not p:return self._json({'error':'Not found'},404)
                if u['role'] in ('candidate','worker') and p['candidate_id']!=u.get('candidate_id'):
                    return self._json({'error':'Permission denied'},403)
                p['requirements']=qall(conn,'SELECT * FROM onboarding_requirements WHERE package_id=? AND tenant_id=? ORDER BY id',(pid,u['tenant_id'])); return self._json(p)
            if path=='/api/starts':
                if u['role'] not in INTERNAL_ROLES:return self._json({'error':'Permission denied'},403)
                return self._json(qall(conn,'''SELECT st.*,s.job_id,s.candidate_id,c.first_name,c.last_name,j.title job_title FROM starts st JOIN submissions s ON s.id=st.submission_id JOIN candidates c ON c.id=s.candidate_id JOIN jobs j ON j.id=s.job_id WHERE st.tenant_id=? ORDER BY st.created_at DESC''',(u['tenant_id'],)))
            if path=='/api/assignments':
                if u['role'] not in INTERNAL_ROLES|{'worker','client'}:return self._json({'error':'Permission denied'},403)
                sql='''SELECT a.*,c.first_name,c.last_name,j.job_no,j.title job_title,co.name company_name,ct.first_name||' '||ct.last_name approver_name FROM assignments a JOIN candidates c ON c.id=a.candidate_id JOIN jobs j ON j.id=a.job_id LEFT JOIN companies co ON co.id=a.company_id LEFT JOIN contacts ct ON ct.id=a.approver_contact_id WHERE a.tenant_id=?'''; params=[u['tenant_id']]
                if u['role']=='worker': sql+=' AND a.candidate_id=?'; params.append(u['candidate_id'])
                if u['role']=='client': sql+=' AND a.company_id=?'; params.append(u['company_id'])
                sql+=' ORDER BY a.updated_at DESC'; return self._json(qall(conn,sql,params))
            if path=='/api/timesheets':
                if u['role'] not in INTERNAL_ROLES|{'worker','client','approver'}:return self._json({'error':'Permission denied'},403)
                sql='''SELECT t.*,c.first_name,c.last_name,j.title job_title,co.name company_name,a.bill_rate,a.pay_rate FROM timesheets t JOIN assignments a ON a.id=t.assignment_id JOIN candidates c ON c.id=t.candidate_id JOIN jobs j ON j.id=a.job_id LEFT JOIN companies co ON co.id=a.company_id WHERE t.tenant_id=?'''; params=[u['tenant_id']]
                if u['role']=='worker': sql+=' AND t.candidate_id=?';params.append(u['candidate_id'])
                if u['role'] in ('client','approver'): sql+=' AND a.company_id=?';params.append(u['company_id'])
                sql+=' ORDER BY t.week_start DESC'
                rows=qall(conn,sql,params)
                if u['role'] in ('worker','client','approver'):
                    for row in rows:
                        if u['role']=='worker': row.pop('bill_rate',None)
                        else: row.pop('pay_rate',None)
                return self._json(rows)
            if path=='/api/expenses':
                if u['role'] not in INTERNAL_ROLES|{'worker','client','approver'}:return self._json({'error':'Permission denied'},403)
                sql='''SELECT e.*,c.first_name,c.last_name,j.title job_title,co.name company_name FROM expenses e JOIN assignments a ON a.id=e.assignment_id JOIN candidates c ON c.id=e.candidate_id JOIN jobs j ON j.id=a.job_id LEFT JOIN companies co ON co.id=a.company_id WHERE e.tenant_id=?''';params=[u['tenant_id']]
                if u['role']=='worker': sql+=' AND e.candidate_id=?';params.append(u['candidate_id'])
                if u['role'] in ('client','approver'): sql+=' AND a.company_id=?';params.append(u['company_id'])
                sql+=' ORDER BY e.expense_date DESC'; return self._json(qall(conn,sql,params))
            if path=='/api/invoices':
                if u['role'] not in ('admin','finance','teamlead'): return self._json({'error':'Permission denied'},403)
                return self._json(qall(conn,'''SELECT i.*,(i.amount+i.tax-i.paid_amount) balance,CASE WHEN i.due_date IS NOT NULL AND i.status IN ('issued','part_paid') THEN MAX(0,CAST(julianday('now')-julianday(i.due_date) AS INTEGER)) ELSE 0 END aging_days,co.name company_name,c.first_name,c.last_name,j.title job_title FROM invoices i LEFT JOIN companies co ON co.id=i.company_id LEFT JOIN assignments a ON a.id=i.assignment_id LEFT JOIN candidates c ON c.id=a.candidate_id LEFT JOIN jobs j ON j.id=a.job_id WHERE i.tenant_id=? ORDER BY i.created_at DESC''',(u['tenant_id'],)))
            m=re.fullmatch(r'/api/invoices/(\d+)',path)
            if m:
                if u['role'] not in ('admin','finance','teamlead'):return self._json({'error':'Permission denied'},403)
                invoice=self._tenant_row(conn,'invoices',int(m.group(1)),u)
                if not invoice:return self._json({'error':'Not found'},404)
                invoice['balance']=float(invoice.get('amount') or 0)+float(invoice.get('tax') or 0)-float(invoice.get('paid_amount') or 0);invoice['payments']=qall(conn,'SELECT * FROM invoice_payments WHERE invoice_id=? AND tenant_id=? ORDER BY payment_date,id',(invoice['id'],u['tenant_id']));return self._json(invoice)
            if path=='/api/purchase-orders':
                if u['role'] not in ('admin','finance','teamlead'):return self._json({'error':'Permission denied'},403)
                return self._json(qall(conn,'SELECT p.*,co.name company_name,j.job_no,j.title job_title FROM purchase_orders p LEFT JOIN companies co ON co.id=p.company_id LEFT JOIN jobs j ON j.id=p.job_id WHERE p.tenant_id=? ORDER BY p.id DESC',(u['tenant_id'],)))
            if path=='/api/vms':
                if u['role'] not in ('admin','teamlead','sales'):return self._json({'error':'Permission denied'},403)
                return self._json({'accounts':qall(conn,'SELECT * FROM vms_accounts WHERE tenant_id=? ORDER BY id',(u['tenant_id'],)),'mappings':qall(conn,'SELECT vm.*,va.name account_name FROM vms_mappings vm LEFT JOIN vms_accounts va ON va.id=vm.vms_account_id WHERE vm.tenant_id=? ORDER BY vm.updated_at DESC',(u['tenant_id'],)),'history':qall(conn,'SELECT * FROM vms_sync_history WHERE tenant_id=? ORDER BY id DESC LIMIT 100',(u['tenant_id'],))})
            if path=='/api/suppliers':
                if u['role'] not in INTERNAL_ROLES|{'supplier'}:return self._json({'error':'Permission denied'},403)
                if u['role']=='supplier':
                    rows=qall(conn,'SELECT s.*,(SELECT COUNT(*) FROM supplier_releases sr WHERE sr.supplier_id=s.id) released_job_count FROM suppliers s WHERE s.id=? AND s.tenant_id=?',(u.get('supplier_id'),u['tenant_id']))
                else: rows=qall(conn,'SELECT s.*,(SELECT COUNT(*) FROM supplier_releases sr WHERE sr.supplier_id=s.id) released_job_count FROM suppliers s WHERE s.tenant_id=? ORDER BY s.name',(u['tenant_id'],))
                return self._json(rows)
            if path=='/api/communications':
                if u['role'] not in INTERNAL_ROLES:return self._json({'error':'Permission denied'},403)
                return self._json(qall(conn,'SELECT c.*,u.name user_name FROM communications c LEFT JOIN users u ON u.id=c.user_id WHERE c.tenant_id=? ORDER BY c.created_at DESC LIMIT 500',(u['tenant_id'],)))
            if path=='/api/tasks':
                if u['role'] not in INTERNAL_ROLES:return self._json({'error':'Permission denied'},403)
                return self._json(qall(conn,'SELECT t.*,u.name owner_name FROM tasks t LEFT JOIN users u ON u.id=t.owner_user_id WHERE t.tenant_id=? AND lower(t.status)!="archived" ORDER BY CASE t.status WHEN "Open" THEN 0 ELSE 1 END,t.due_at',(u['tenant_id'],)))

            if path=='/api/automation-runs':
                if u['role'] not in ('admin','teamlead'):
                    return self._json(
                        {'error':'Permission denied'},
                        403
                    )

                automation_id=int(
                    (
                        qs.get('automation_id')
                        or [0]
                    )[0]
                    or 0
                )

                sql='''SELECT
                           r.*,
                           a.name automation_name,
                           u.name user_name
                       FROM automation_runs r
                       JOIN automations a
                         ON a.id=r.automation_id
                       LEFT JOIN users u
                         ON u.id=r.user_id
                       WHERE r.tenant_id=?'''

                params=[
                    u['tenant_id']
                ]

                if automation_id:
                    sql+=' AND r.automation_id=?'
                    params.append(
                        automation_id
                    )

                sql+=' ORDER BY r.id DESC LIMIT 200'

                return self._json(
                    qall(
                        conn,
                        sql,
                        params
                    )
                )

            if path=='/api/automations':
                if u['role'] not in ('admin','teamlead'):return self._json({'error':'Permission denied'},403)
                return self._json(qall(conn,'SELECT * FROM automations WHERE tenant_id=? ORDER BY id DESC',(u['tenant_id'],)))
            if path=='/api/users':
                if u['role']!='admin': return self._json({'error':'Permission denied'},403)
                return self._json(qall(conn,'SELECT id,email,name,role,company_id,candidate_id,supplier_id,active,created_at FROM users WHERE tenant_id=? ORDER BY name',(u['tenant_id'],)))
            if path=='/api/custom-fields':
                if u['role'] not in INTERNAL_ROLES:return self._json({'error':'Permission denied'},403)
                return self._json(qall(conn,'SELECT * FROM custom_fields WHERE tenant_id=? ORDER BY entity_type,field_name',(u['tenant_id'],)))
            if path=='/api/custom-values':
                if u['role'] not in INTERNAL_ROLES:return self._json({'error':'Permission denied'},403)
                entity_type=(qs.get('entity_type') or [''])[0];entity_id=int((qs.get('entity_id') or [0])[0] or 0)
                return self._json(qall(conn,'SELECT v.*,f.field_name,f.field_type FROM entity_custom_values v JOIN custom_fields f ON f.id=v.field_id WHERE v.tenant_id=? AND v.entity_type=? AND v.entity_id=?',(u['tenant_id'],entity_type,entity_id)))
            m=re.fullmatch(r'/api/(assignments|starts|submissions|timesheets|expenses|invoices)/(\d+)/history',path)
            if m:
                if u['role'] not in INTERNAL_ROLES:return self._json({'error':'Permission denied'},403)
                return self._json(qall(conn,'SELECT * FROM workflow_history WHERE tenant_id=? AND entity_type=? AND entity_id=? ORDER BY id',(u['tenant_id'],m.group(1).rstrip('s'),int(m.group(2)))))
            if path=='/api/audit':
                if u['role'] not in ('admin','teamlead'): return self._json({'error':'Permission denied'},403)
                return self._json(qall(conn,'SELECT a.*,u.name user_name,u.email FROM audit_log a LEFT JOIN users u ON u.id=a.user_id WHERE a.tenant_id=? ORDER BY a.id DESC LIMIT 1000',(u['tenant_id'],)))
            if path=='/api/reports/definitions':
                if u['role'] not in INTERNAL_ROLES:return self._json({'error':'Permission denied'},403)
                rows=qall(conn,'SELECT * FROM report_definitions WHERE tenant_id=? AND (owner_user_id=? OR is_shared=1) ORDER BY is_shared DESC,name',(u['tenant_id'],u['id']))
                return self._json(rows)
            if path=='/api/reports/summary':
                if u['role'] not in INTERNAL_ROLES:return self._json({'error':'Permission denied'},403)
                return self._json(self.report_summary(conn,u))
            if path=='/api/reports/catalog':
                if u['role'] not in INTERNAL_ROLES:return self._json({'error':'Permission denied'},403)
                builtins=[{'report_key':'recruiting_pipeline','name':'Recruiting Pipeline','parameters':['from','to']},{'report_key':'workforce_activity','name':'Workforce Activity','parameters':['status']},{'report_key':'finance_aging','name':'Invoice Aging','parameters':['as_of']}]
                saved=qall(conn,'SELECT * FROM report_definitions WHERE tenant_id=? ORDER BY name',(u['tenant_id'],))
                return self._json({'builtins':builtins,'saved':saved})
            if path in ('/api/reports/run','/api/reports/export'):
                if u['role'] not in INTERNAL_ROLES:return self._json({'error':'Permission denied'},403)
                key=(qs.get('report_key') or ['recruiting_pipeline'])[0]
                try:rows=self.run_report(conn,u,key,qs)
                except ValueError as e:return self._json({'error':str(e)},400)
                if path.endswith('/export'):
                    output=io.StringIO(); fields=list(rows[0]) if rows else ['message']; writer=csv.DictWriter(output,fieldnames=fields);writer.writeheader();writer.writerows(rows or [{'message':'No rows'}])
                    return self._binary(output.getvalue().encode('utf-8-sig'),'text/csv; charset=utf-8',key+'.csv')
                return self._json({'report_key':key,'count':len(rows),'rows':rows})
            if path=='/api/tenants/current': return self._json(qone(conn,'SELECT * FROM tenants WHERE id=?',(u['tenant_id'],)))

            if path=='/api/search/suggestions':
                if u['role'] not in RECRUITING_ROLES:
                    return self._json({'error':'Permission denied'},403)

                kind=(qs.get('kind') or [''])[0].strip().lower()
                term=(qs.get('q') or [''])[0].strip()
                profession=(qs.get('profession') or [''])[0].strip()

                try:
                    limit=min(max(int((qs.get('limit') or ['12'])[0]),1),25)
                except Exception:
                    limit=12

                starters={
                    'profession':[
                        'Software Engineer','Data Engineer','Cloud Engineer',
                        'QA / SDET','Business Analyst','Project Manager',
                        'DevOps Engineer','Security Engineer','Data Scientist',
                        'Machine Learning Engineer','Registered Nurse',
                        'Nurse Practitioner','Physician Assistant',
                        'Recruiter','Product Manager'
                    ],
                    'specialty':[
                        'Backend','Frontend','Full Stack','Java Backend',
                        'Spring Boot','Microservices','Cloud Platform',
                        'Data Platform','ETL / ELT','Automation',
                        'Performance Engineering','Security','Analytics'
                    ],
                    'skill':[
                        'Java','Spring Boot','Microservices','Python',
                        'PySpark','Databricks','AWS','Azure','GCP',
                        'SQL','Kafka','React','TypeScript','Kubernetes',
                        'Terraform','Selenium','REST Assured'
                    ],
                    'license':['RN','LPN','LVN','CNA','NP','PA'],
                    'certification':[
                        'AWS Certified','Azure Certified','GCP Certified',
                        'PMP','ACLS','BLS','CKA','Databricks Certified'
                    ],
                    'qualification':[
                        'Bachelors','Masters','MBA','BSN','B.Tech',
                        'M.Tech','Computer Science','Nursing'
                    ],
                    'attribute':[
                        'Top Candidate','Compact License',
                        'Available Immediately','Preferred Supplier',
                        'Security Cleared'
                    ],
                    'title':[
                        'Senior Java Developer','Software Engineer',
                        'Data Engineer','Cloud Engineer','QA Engineer',
                        'Business Analyst','Project Manager'
                    ]
                }

                if kind not in starters:
                    return self._json({
                        'error':'Unsupported suggestion kind',
                        'supported':sorted(starters)
                    },400)

                tid=u['tenant_id']
                values=[]

                def extend_rows(sql,params):
                    for row in qall(conn,sql,params):
                        value=(row.get('value') or '').strip()
                        if value:
                            values.append(value)

                if kind=='profession':
                    extend_rows(
                        '''SELECT profession value
                           FROM candidates
                           WHERE tenant_id=? AND profession IS NOT NULL
                           UNION ALL
                           SELECT profession value
                           FROM jobs
                           WHERE tenant_id=? AND profession IS NOT NULL''',
                        (tid,tid)
                    )

                elif kind=='specialty':
                    if profession:
                        extend_rows(
                            '''SELECT specialty value
                               FROM candidates
                               WHERE tenant_id=? AND specialty IS NOT NULL
                                 AND lower(COALESCE(profession,''))=lower(?)
                               UNION ALL
                               SELECT specialty value
                               FROM jobs
                               WHERE tenant_id=? AND specialty IS NOT NULL
                                 AND lower(COALESCE(profession,''))=lower(?)''',
                            (tid,profession,tid,profession)
                        )
                    else:
                        extend_rows(
                            '''SELECT specialty value
                               FROM candidates
                               WHERE tenant_id=? AND specialty IS NOT NULL
                               UNION ALL
                               SELECT specialty value
                               FROM jobs
                               WHERE tenant_id=? AND specialty IS NOT NULL''',
                            (tid,tid)
                        )

                elif kind=='skill':
                    extend_rows(
                        '''SELECT skill value
                           FROM candidate_skills
                           WHERE tenant_id=? AND skill IS NOT NULL''',
                        (tid,)
                    )

                elif kind=='license':
                    extend_rows(
                        '''SELECT license_type value
                           FROM candidate_licenses
                           WHERE tenant_id=? AND license_type IS NOT NULL''',
                        (tid,)
                    )

                elif kind=='certification':
                    extend_rows(
                        '''SELECT name value
                           FROM candidate_certifications
                           WHERE tenant_id=? AND name IS NOT NULL''',
                        (tid,)
                    )

                elif kind=='qualification':
                    extend_rows(
                        '''SELECT value
                           FROM candidate_qualifications
                           WHERE tenant_id=? AND value IS NOT NULL
                           UNION ALL
                           SELECT name value
                           FROM candidate_qualifications
                           WHERE tenant_id=? AND name IS NOT NULL''',
                        (tid,tid)
                    )

                elif kind=='attribute':
                    extend_rows(
                        '''SELECT attribute value
                           FROM candidate_attributes
                           WHERE tenant_id=? AND attribute IS NOT NULL''',
                        (tid,)
                    )

                elif kind=='title':
                    extend_rows(
                        '''SELECT current_title value
                           FROM candidates
                           WHERE tenant_id=? AND current_title IS NOT NULL
                           UNION ALL
                           SELECT title value
                           FROM jobs
                           WHERE tenant_id=? AND title IS NOT NULL''',
                        (tid,tid)
                    )

                values.extend(starters[kind])

                needle=term.casefold()
                seen=set()
                result=[]

                for value in values:
                    value=' '.join(str(value).split())
                    key=value.casefold()

                    if not value or key in seen:
                        continue

                    if needle and needle not in key:
                        continue

                    seen.add(key)
                    result.append(value)

                result.sort(
                    key=lambda x:(
                        0 if needle and x.casefold().startswith(needle) else 1,
                        x.casefold()
                    )
                )

                return self._json({
                    'kind':kind,
                    'query':term,
                    'profession':profession,
                    'items':result[:limit]
                })

            if path=='/api/search/boolean/validate':
                if u['role'] not in RECRUITING_ROLES:
                    return self._json({'error':'Permission denied'},403)

                expression=(qs.get('q') or [''])[0].strip()

                try:
                    tree=parse_boolean(expression)
                    return self._json({
                        'ok':True,
                        'expression':expression,
                        'tree':tree
                    })
                except BooleanSyntaxError as exc:
                    return self._json({
                        'ok':False,
                        'expression':expression,
                        'detail':str(exc)
                    },400)

            if path=='/api/reference':
                if u['role'] in INTERNAL_ROLES:
                    tid=u['tenant_id'];return self._json({'companies':qall(conn,'SELECT id,name FROM companies WHERE tenant_id=? ORDER BY name',(tid,)),'contacts':qall(conn,"SELECT id,company_id,first_name||' '||last_name name FROM contacts WHERE tenant_id=? ORDER BY last_name",(tid,)),'users':qall(conn,'SELECT id,name,role FROM users WHERE active=1 AND tenant_id=? ORDER BY name',(tid,)),'candidates':qall(conn,"SELECT id,first_name||' '||last_name name,current_title FROM candidates WHERE tenant_id=? AND lower(status)!='archived' ORDER BY last_name",(tid,)),'jobs':qall(conn,'SELECT id,job_no,title,company_id,status FROM jobs WHERE tenant_id=? AND archived_at IS NULL ORDER BY created_at DESC',(tid,)),'suppliers':qall(conn,'SELECT id,name FROM suppliers WHERE tenant_id=? ORDER BY name',(tid,))})
                if u['role'] in ('client','approver'):
                    co=u.get('company_id')
                    return self._json({'companies':qall(conn,'SELECT id,name FROM companies WHERE id=?',(co,)),'contacts':qall(conn,"SELECT id,company_id,first_name||' '||last_name name FROM contacts WHERE company_id=? ORDER BY last_name",(co,)),'users':[],'candidates':[],'jobs':qall(conn,'SELECT id,job_no,title,company_id,status FROM jobs WHERE company_id=? ORDER BY created_at DESC',(co,)),'suppliers':[]})
                if u['role']=='supplier':
                    sid=u.get('supplier_id');return self._json({'companies':[],'contacts':[],'users':[],'candidates':qall(conn,"SELECT id,first_name||' '||last_name name,current_title FROM candidates WHERE tenant_id=? AND supplier_id=? ORDER BY last_name",(u['tenant_id'],sid)),'jobs':qall(conn,"SELECT j.id,j.job_no,j.title,j.company_id,j.status FROM jobs j JOIN supplier_releases sr ON sr.job_id=j.id AND sr.tenant_id=j.tenant_id WHERE j.tenant_id=? AND sr.supplier_id=? AND sr.status='Open'",(u['tenant_id'],sid)),'suppliers':qall(conn,'SELECT id,name FROM suppliers WHERE id=? AND tenant_id=?',(sid,u['tenant_id']))})
                return self._json({'companies':[],'contacts':[],'users':[],'candidates':[],'jobs':[],'suppliers':[]})
            return self._json({'error':'API endpoint not found'},404)
        except (BrokenPipeError,ConnectionResetError):
            return
        except Exception as e:
            incident=secrets.token_hex(8);print(f'GET_ERROR incident={incident} path={path} error={e!r}',file=sys.stderr,flush=True);return self._json({'error':'Server error','incident':incident},500)
        finally: conn.close()
    def do_POST(self):
        p=urllib.parse.urlparse(self.path); path=p.path; data=self._body(); conn=db()
        try:
            if data is None:return self._json({'error':getattr(self,'_body_error','Malformed JSON')},400)
            if r14_public_post(self,conn,path,data): return
            if r23c_public_post(self,conn,path,data): return
            if path=='/api/login':
                email=(data.get('email') or '').strip().lower();pw=data.get('password') or '';ip=str(self.client_address[0] if self.client_address else '')
                subject_hash=hashlib.sha256(email.encode()).hexdigest();ip_hash=hashlib.sha256(ip.encode()).hexdigest();attempt=qone(conn,'SELECT * FROM login_attempts WHERE subject_hash=? AND ip_hash=?',(subject_hash,ip_hash));now_dt=datetime.now(timezone.utc)
                if attempt and attempt.get('blocked_until') and attempt['blocked_until']>now_dt.replace(microsecond=0).isoformat():return self._json({'error':'Invalid email or password'},429)
                u=qone(conn,'SELECT * FROM users WHERE lower(email)=? AND active=1',(email,))
                password_ok=bool(u and verify_password(pw,u['pass_hash']))
                mfa=r14_mfa_required(conn,u) if u else None;mfa_ok=not mfa or r14_verify_totp(mfa['secret'],data.get('mfa_code'))
                if not password_ok or not mfa_ok:
                    failures=int((attempt or {}).get('failures') or 0)+1;window=(attempt or {}).get('window_started_at') or utcnow();blocked=(now_dt+timedelta(minutes=min(30,2**max(0,failures-5)))).replace(microsecond=0).isoformat() if failures>=5 else None
                    conn.execute('INSERT INTO login_attempts(subject_hash,ip_hash,failures,window_started_at,blocked_until,updated_at) VALUES(?,?,?,?,?,?) ON CONFLICT(subject_hash,ip_hash) DO UPDATE SET failures=excluded.failures,blocked_until=excluded.blocked_until,updated_at=excluded.updated_at',(subject_hash,ip_hash,failures,window,blocked,utcnow()));conn.execute('INSERT INTO security_events(tenant_id,user_id,event_type,subject_hash,ip_hash,detail,created_at) VALUES(?,?,?,?,?,?,?)',((u or {}).get('tenant_id'),(u or {}).get('id'),'LOGIN_FAILED',subject_hash,ip_hash,'authentication failed',utcnow()));conn.commit();return self._json({'error':'Invalid email or password'},401 if not blocked else 429)
                conn.execute('DELETE FROM login_attempts WHERE subject_hash=? AND ip_hash=?',(subject_hash,ip_hash));tok=secrets.token_urlsafe(32);exp=(now_dt+timedelta(hours=18)).replace(microsecond=0).isoformat();conn.execute('INSERT INTO sessions(token,user_id,expires_at,created_at,tenant_id) VALUES(?,?,?,?,?)',(tok,u['id'],exp,utcnow(),u['tenant_id']));audit(conn,u['id'],'LOGIN','user',u['id'],'Successful login',ip);conn.commit();u.pop('pass_hash',None);return self._json({'user':u},200,{'Set-Cookie':f'ats_session={tok}; Path=/; HttpOnly; SameSite=Lax; Max-Age=64800' + ('; Secure' if os.environ.get('RENDER') or os.environ.get('FORCE_SECURE_COOKIE')=='1' else '')})
            if path=='/api/logout':
                tok=self._cookies().get('ats_session');
                if tok: conn.execute('DELETE FROM sessions WHERE token=?',(tok,));conn.commit()
                return self._json({'ok':True},200,{'Set-Cookie':'ats_session=; Path=/; Max-Age=0; HttpOnly; SameSite=Lax'})
            u=self._need(conn)
            if not u:return
            if parity_post(self,conn,u,path,data): return
            if r14_post(self,conn,u,path,data): return
            if r18_post(self,conn,u,path,data): return
            if r19_post(self,conn,u,path,data): return
            if r22_post(self,conn,u,path,data): return
            if r23_post(self,conn,u,path,data): return
            if r23c_post(self,conn,u,path,data): return
            if r23d_post(self,conn,u,path,data): return
            if path=='/api/search/talent':
                if u['role'] not in ('admin','teamlead','recruiter','sales','hr'): return self._json({'error':'Permission denied'},403)
                data=dict(data);data['_tenant_id']=u['tenant_id']
                try: res=perform_search(conn,data)
                except (BooleanSyntaxError,ValueError) as e:return self._json({'error':'Invalid search criteria','detail':str(e)},400)
                criteria=compile_criteria(data); audit(conn,u['id'],'SEARCH','candidate',None,criteria,self.client_address[0]);conn.commit()
                return self._json({'criteria':criteria,'duration_ms':0,'count':len(res),'results':res})
            if path=='/api/resume/parse':
                if u['role'] not in CANDIDATE_EDIT_ROLES:return self._json({'error':'Permission denied'},403)
                try:return self._json(deterministic_resume_parse(data.get('resume_text') or data.get('text')),200)
                except ValueError as e:return self._json({'error':str(e)},400)
            if path=='/api/supplier/candidates':
                if u['role']!='supplier' or not u.get('supplier_id'):return self._json({'error':'Permission denied'},403)
                if not data.get('first_name') or not data.get('last_name'):return self._json({'error':'first_name and last_name required'},400)
                now=utcnow();cur=conn.execute('INSERT INTO candidates(first_name,last_name,email,phone,city,state,country,zip,current_title,profession,specialty,status,source,resume_text,summary,owner_user_id,supplier_id,created_at,updated_at,tenant_id) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(data.get('first_name'),data.get('last_name'),data.get('email'),data.get('phone'),data.get('city'),data.get('state'),data.get('country','USA'),data.get('zip'),data.get('current_title'),data.get('profession'),data.get('specialty'),'Active','Supplier',data.get('resume_text'),data.get('summary'),u['id'],u['supplier_id'],now,now,u['tenant_id']));cid=cur.lastrowid
                for s in data.get('skills') or []:conn.execute('INSERT INTO candidate_skills(candidate_id,skill,years,recent,last_used,tenant_id) VALUES(?,?,?,?,?,?)',(cid,s.get('skill'),float(s.get('years') or 0),1 if s.get('recent') else 0,s.get('last_used'),u['tenant_id']))
                audit(conn,u['id'],'CREATE','supplier_candidate',cid,f'supplier={u["supplier_id"]}',self.client_address[0]);conn.commit();return self._json({'id':cid,'ok':True},201)
            if path=='/api/candidates':
                if u['role'] not in ('admin','teamlead','recruiter','hr'): return self._json({'error':'Permission denied'},403)
                required=['first_name','last_name'];
                if any(not data.get(x) for x in required): return self._json({'error':'first_name and last_name required'},400)
                if data.get('owner_user_id') and not self._tenant_row(conn,'users',int(data['owner_user_id']),u):return self._json({'error':'Owner not found'},404)
                now=utcnow(); cols=['first_name','last_name','email','phone','city','state','country','zip','profession','specialty','current_title','availability_date','pay_min','pay_max','desired_rate_type','source','status','owner_user_id','resume_text','summary','latitude','longitude','tenant_id']
                vals=[data.get(c) for c in cols]; vals[6]=vals[6] or 'USA'; vals[14]=vals[14] or 'hour'; vals[15]=vals[15] or 'Manual'; vals[16]=vals[16] or 'Active'; vals[17]=vals[17] or u['id']
                coords=resolve_postal(data.get('zip'))
                if vals[20] is None and coords:vals[20]=coords[0]
                if vals[21] is None and coords:vals[21]=coords[1]
                vals[22]=u['tenant_id']
                cur=conn.execute('INSERT INTO candidates('+','.join(cols)+',created_at,updated_at) VALUES('+','.join(['?']*(len(cols)+2))+')',(*vals,now,now)); cid=cur.lastrowid
                for s in data.get('skills') or []:
                    conn.execute('INSERT OR REPLACE INTO candidate_skills(candidate_id,skill,years,recent,last_used,tenant_id) VALUES(?,?,?,?,?,?)',(cid,s.get('skill'),float(s.get('years') or 0),1 if s.get('recent') else 0,s.get('last_used'),u['tenant_id']))
                for exp in data.get('experience') or []:
                    conn.execute('INSERT INTO candidate_experience(candidate_id,company,title,start_date,end_date,description,skills,tenant_id) VALUES(?,?,?,?,?,?,?,?)',(cid,exp.get('company'),exp.get('title'),exp.get('start_date'),exp.get('end_date'),exp.get('description'),exp.get('skills'),u['tenant_id']))
                audit(conn,u['id'],'CREATE','candidate',cid,f"{data.get('first_name')} {data.get('last_name')}",self.client_address[0]); conn.commit(); return self._json(candidate_bundle(conn,cid),201)
            m=re.fullmatch(r'/api/candidates/(\d+)/resume/commit',path)
            if m:
                if u['role'] not in CANDIDATE_EDIT_ROLES:return self._json({'error':'Permission denied'},403)
                cid=int(m.group(1));candidate=self._tenant_row(conn,'candidates',cid,u)
                if not candidate:return self._json({'error':'Not found'},404)
                reviewed=data.get('reviewed') or data
                fields=[x for x in ('first_name','last_name','email','phone','current_title','resume_text','summary') if x in reviewed]
                if fields:conn.execute('UPDATE candidates SET '+','.join(f'{x}=?' for x in fields)+',updated_at=? WHERE id=? AND tenant_id=?',tuple(reviewed[x] for x in fields)+(utcnow(),cid,u['tenant_id']))
                for s in reviewed.get('skills') or []:
                    if not (s.get('skill') or '').strip():continue
                    conn.execute('INSERT INTO candidate_skills(candidate_id,skill,years,recent,last_used,tenant_id) VALUES(?,?,?,?,?,?) ON CONFLICT(candidate_id,skill) DO UPDATE SET years=excluded.years,recent=excluded.recent,last_used=excluded.last_used',(cid,s['skill'].strip(),float(s.get('years') or 0),1 if s.get('recent') else 0,s.get('last_used'),u['tenant_id']))
                for exp in reviewed.get('experience') or []:
                    conn.execute('INSERT INTO candidate_experience(candidate_id,company,title,start_date,end_date,description,skills,tenant_id) VALUES(?,?,?,?,?,?,?,?)',(cid,exp.get('company'),exp.get('title'),exp.get('start_date'),exp.get('end_date'),exp.get('description'),exp.get('skills'),u['tenant_id']))
                audit(conn,u['id'],'RESUME_COMMIT','candidate',cid,'Recruiter-reviewed deterministic parse',self.client_address[0]);conn.commit();return self._json(candidate_bundle(conn,cid,u['tenant_id']))
            m=re.fullmatch(r'/api/candidates/(\d+)/(skills|experience|licenses|certifications|qualifications|attributes|documents)',path)
            if m:
                if u['role'] not in CANDIDATE_EDIT_ROLES:return self._json({'error':'Permission denied'},403)
                cid=int(m.group(1));section=m.group(2)
                if not self._tenant_row(conn,'candidates',cid,u):return self._json({'error':'Not found'},404)
                if data.get('owner_user_id') and not self._tenant_row(conn,'users',int(data['owner_user_id']),u):return self._json({'error':'Owner not found'},404)
                if section=='skills':
                    skill=(data.get('skill') or '').strip()
                    if not skill:return self._json({'error':'skill required'},400)
                    cur=conn.execute('INSERT INTO candidate_skills(candidate_id,skill,years,recent,last_used,tenant_id) VALUES(?,?,?,?,?,?) ON CONFLICT(candidate_id,skill) DO UPDATE SET years=excluded.years,recent=excluded.recent,last_used=excluded.last_used',(cid,skill,float(data.get('years') or 0),1 if data.get('recent') else 0,data.get('last_used'),u['tenant_id']));item=qone(conn,'SELECT * FROM candidate_skills WHERE candidate_id=? AND skill=?',(cid,skill))
                elif section=='experience':
                    cur=conn.execute('INSERT INTO candidate_experience(candidate_id,company,title,start_date,end_date,description,skills,tenant_id) VALUES(?,?,?,?,?,?,?,?)',(cid,data.get('company'),data.get('title'),data.get('start_date'),data.get('end_date'),data.get('description'),data.get('skills'),u['tenant_id']));item=qone(conn,'SELECT * FROM candidate_experience WHERE id=?',(cur.lastrowid,))
                elif section=='licenses':
                    cur=conn.execute('INSERT INTO candidate_licenses(candidate_id,license_type,country,state,license_number,status,expiry_date,documented,tenant_id) VALUES(?,?,?,?,?,?,?,?,?)',(cid,data.get('license_type'),data.get('country'),data.get('state'),data.get('license_number'),data.get('status','Active'),data.get('expiry_date'),1 if data.get('documented',True) else 0,u['tenant_id']));item=qone(conn,'SELECT * FROM candidate_licenses WHERE id=?',(cur.lastrowid,))
                elif section=='certifications':
                    cur=conn.execute('INSERT INTO candidate_certifications(candidate_id,name,status,expiry_date,documented,tenant_id) VALUES(?,?,?,?,?,?)',(cid,data.get('name'),data.get('status','Active'),data.get('expiry_date'),1 if data.get('documented',True) else 0,u['tenant_id']));item=qone(conn,'SELECT * FROM candidate_certifications WHERE id=?',(cur.lastrowid,))
                elif section=='qualifications':
                    cur=conn.execute('INSERT INTO candidate_qualifications(candidate_id,name,value,sub_value,tenant_id) VALUES(?,?,?,?,?)',(cid,data.get('name'),data.get('value'),data.get('sub_value'),u['tenant_id']));item=qone(conn,'SELECT * FROM candidate_qualifications WHERE id=?',(cur.lastrowid,))
                elif section=='attributes':
                    cur=conn.execute('INSERT INTO candidate_attributes(candidate_id,attribute,value,tenant_id) VALUES(?,?,?,?)',(cid,data.get('attribute'),data.get('value'),u['tenant_id']));item=qone(conn,'SELECT * FROM candidate_attributes WHERE id=?',(cur.lastrowid,))
                else:
                    encoded=data.get('content_base64') or ''
                    try:content=base64.b64decode(encoded,validate=True) if encoded else b''
                    except Exception:return self._json({'error':'content_base64 is invalid'},400)
                    if len(content)>10*1024*1024:return self._json({'error':'Document exceeds 10 MB limit'},413)
                    file_name=data.get('file_name') or data.get('name') or 'document.bin';mime=data.get('mime_type') or mimetypes.guess_type(file_name)[0] or 'application/octet-stream'
                    cur=conn.execute('INSERT INTO candidate_documents(candidate_id,doc_type,name,status,expiry_date,file_name,verified_by,verified_at,created_at,current_version,mime_type,size_bytes,tenant_id) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',(cid,data.get('doc_type','Other'),data.get('name') or file_name,data.get('status','Pending'),data.get('expiry_date'),file_name,None,None,utcnow(),1,mime,len(content),u['tenant_id']));did=cur.lastrowid
                    conn.execute('INSERT INTO candidate_document_versions(document_id,version,file_name,mime_type,size_bytes,sha256,content,uploaded_by,created_at,tenant_id) VALUES(?,?,?,?,?,?,?,?,?,?)',(did,1,file_name,mime,len(content),hashlib.sha256(content).hexdigest(),content,u['id'],utcnow(),u['tenant_id']));item=qone(conn,'SELECT * FROM candidate_documents WHERE id=?',(did,))
                audit(conn,u['id'],'CREATE','candidate_'+section,item['id'],f'candidate={cid}',self.client_address[0]);conn.commit();return self._json(item,201)
            if path=='/api/search/bulk':
                if u['role'] not in RECRUITING_ROLES:return self._json({'error':'Permission denied'},403)
                ids=sorted({int(x) for x in (data.get('candidate_ids') or [])});action=norm(data.get('action'))
                valid={r['id'] for r in qall(conn,'SELECT id FROM candidates WHERE tenant_id=? AND id IN ('+(','.join('?'*len(ids)) if ids else 'NULL')+')',(u['tenant_id'],*ids))}
                if not valid:return self._json({'error':'No tenant-owned candidates selected'},400)
                affected=0
                if action=='hotlist':
                    hid=int(data.get('hotlist_id') or 0)
                    if not self._tenant_row(conn,'hotlists',hid,u):return self._json({'error':'Hotlist not found'},404)
                    for cid in valid:conn.execute('INSERT OR IGNORE INTO hotlist_members(hotlist_id,candidate_id,status,note,added_by,created_at,tenant_id) VALUES(?,?,?,?,?,?,?)',(hid,cid,'Active',data.get('note',''),u['id'],utcnow(),u['tenant_id']));affected+=1
                elif action=='qualify':
                    jid=int(data.get('job_id') or 0)
                    if not self._tenant_row(conn,'jobs',jid,u):return self._json({'error':'Job not found'},404)
                    for cid in valid:
                        now=utcnow();conn.execute('INSERT INTO interested_candidates(job_id,candidate_id,status,source,user_id,created_at,updated_at,tenant_id) VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(job_id,candidate_id) DO UPDATE SET status="qualified",updated_at=excluded.updated_at',(jid,cid,'qualified','Talent Bulk',u['id'],now,now,u['tenant_id']));affected+=1
                elif action=='email':
                    for cid in valid:conn.execute('INSERT INTO communications(entity_type,entity_id,channel,direction,subject,body,user_id,status,created_at,tenant_id) VALUES(?,?,?,?,?,?,?,?,?,?)',('candidate',cid,'Email','Outbound',data.get('subject','Talent outreach'),data.get('body',''),u['id'],'Logged',utcnow(),u['tenant_id']));affected+=1
                else:return self._json({'error':'Supported actions: hotlist, qualify, email'},400)
                audit(conn,u['id'],'BULK_'+action.upper(),'candidate',None,f'count={affected}',self.client_address[0]);conn.commit();return self._json({'ok':True,'action':action,'affected':affected})
            m=re.fullmatch(r'/api/candidates/(\d+)/notes',path)
            if m:
                if u['role'] not in CANDIDATE_EDIT_ROLES: return self._json({'error':'Permission denied'},403)
                cid=int(m.group(1)); note=(data.get('note') or '').strip();
                if not note:return self._json({'error':'note required'},400)
                if not self._tenant_row(conn,'candidates',cid,u):return self._json({'error':'Not found'},404)
                cur=conn.execute('INSERT INTO candidate_notes(candidate_id,user_id,note,note_type,created_at,tenant_id) VALUES(?,?,?,?,?,?)',(cid,u['id'],note,data.get('note_type') or 'General',utcnow(),u['tenant_id'])); audit(conn,u['id'],'ADD_NOTE','candidate',cid,note[:120],self.client_address[0]);conn.commit();return self._json({'id':cur.lastrowid,'ok':True},201)
            m=re.fullmatch(r'/api/hotlists/(\d+)/members',path)
            if m:
                if u['role'] not in RECRUITING_ROLES: return self._json({'error':'Permission denied'},403)
                hid=int(m.group(1)); cid=int(data.get('candidate_id') or 0)
                if not self._tenant_row(conn,'hotlists',hid,u) or not self._tenant_row(conn,'candidates',cid,u):return self._json({'error':'Hotlist or candidate not found'},404)
                conn.execute('INSERT INTO hotlist_members(hotlist_id,candidate_id,status,note,added_by,created_at,tenant_id) VALUES(?,?,?,?,?,?,?) ON CONFLICT(hotlist_id,candidate_id) DO UPDATE SET status=excluded.status,note=excluded.note',(hid,cid,data.get('status','Active'),data.get('note',''),u['id'],utcnow(),u['tenant_id']));audit(conn,u['id'],'ADD_HOTLIST_MEMBER','hotlist',hid,f'candidate={cid}',self.client_address[0]);conn.commit();return self._json({'ok':True},201)
            if path=='/api/hotlists':
                if u['role'] not in RECRUITING_ROLES: return self._json({'error':'Permission denied'},403)
                now=utcnow();cur=conn.execute('INSERT INTO hotlists(name,description,owner_user_id,visibility,mode,saved_search_json,created_at,updated_at,tenant_id) VALUES(?,?,?,?,?,?,?,?,?)',(data.get('name') or 'Untitled Hotlist',data.get('description',''),data.get('owner_user_id') or u['id'],data.get('visibility','Team'),data.get('mode','static'),json.dumps(data.get('saved_search')) if data.get('saved_search') else None,now,now,u['tenant_id'])); audit(conn,u['id'],'CREATE','hotlist',cur.lastrowid,data.get('name',''),self.client_address[0]);conn.commit(); return self._json({'id':cur.lastrowid,'ok':True},201)
            if path=='/api/companies':
                if u['role'] not in ('admin','teamlead','sales'): return self._json({'error':'Permission denied'},403)
                now=utcnow();cur=conn.execute('INSERT INTO companies(name,company_type,industry,status,owner_user_id,website,phone,address,city,state,country,billing_terms,submission_guidelines,discount_rule,notes,created_at,tenant_id) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(data.get('name'),data.get('company_type','Client'),data.get('industry'),data.get('status','Active'),u['id'],data.get('website'),data.get('phone'),data.get('address'),data.get('city'),data.get('state'),data.get('country','USA'),data.get('billing_terms','Net 30'),data.get('submission_guidelines'),data.get('discount_rule'),data.get('notes'),now,u['tenant_id']));audit(conn,u['id'],'CREATE','company',cur.lastrowid,data.get('name',''),self.client_address[0]);conn.commit();return self._json({'id':cur.lastrowid,'ok':True},201)
            if path=='/api/contacts':
                if u['role'] not in ('admin','teamlead','sales','recruiter'): return self._json({'error':'Permission denied'},403)
                if data.get('company_id') and not self._tenant_row(conn,'companies',int(data['company_id']),u):return self._json({'error':'Company not found'},404)
                cur=conn.execute('INSERT INTO contacts(company_id,first_name,last_name,title,email,phone,role_type,owner_user_id,status,notes,created_at,tenant_id) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(data.get('company_id'),data.get('first_name'),data.get('last_name'),data.get('title'),data.get('email'),data.get('phone'),data.get('role_type','Hiring Manager'),u['id'],data.get('status','Active'),data.get('notes'),utcnow(),u['tenant_id']));audit(conn,u['id'],'CREATE','contact',cur.lastrowid,(data.get('first_name','')+' '+data.get('last_name','')).strip(),self.client_address[0]);conn.commit();return self._json({'id':cur.lastrowid,'ok':True},201)
            if path=='/api/leads':
                if u['role'] not in ('admin','teamlead','sales'):return self._json({'error':'Permission denied'},403)
                if data.get('company_id') and not self._tenant_row(conn,'companies',int(data['company_id']),u):return self._json({'error':'Company not found'},404)
                if data.get('contact_id') and not self._tenant_row(conn,'contacts',int(data['contact_id']),u):return self._json({'error':'Contact not found'},404)
                cur=conn.execute('INSERT INTO leads(company_id,contact_id,title,source,status,owner_user_id,next_action,next_action_at,notes,created_at,tenant_id) VALUES(?,?,?,?,?,?,?,?,?,?,?)',(data.get('company_id'),data.get('contact_id'),data.get('title'),data.get('source','Manual'),data.get('status','New'),u['id'],data.get('next_action'),data.get('next_action_at'),data.get('notes'),utcnow(),u['tenant_id']));audit(conn,u['id'],'CREATE','lead',cur.lastrowid,data.get('title',''),self.client_address[0]);conn.commit();return self._json({'id':cur.lastrowid,'ok':True},201)
            if path=='/api/opportunities':
                if u['role'] not in ('admin','teamlead','sales'):return self._json({'error':'Permission denied'},403)
                if data.get('company_id') and not self._tenant_row(conn,'companies',int(data['company_id']),u):return self._json({'error':'Company not found'},404)
                if data.get('contact_id') and not self._tenant_row(conn,'contacts',int(data['contact_id']),u):return self._json({'error':'Contact not found'},404)
                now=utcnow();cur=conn.execute('INSERT INTO opportunities(company_id,contact_id,name,stage,value,probability,owner_user_id,expected_close,next_activity,status,notes,created_at,updated_at,tenant_id) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(data.get('company_id'),data.get('contact_id'),data.get('name'),data.get('stage','Lead'),float(data.get('value') or 0),int(data.get('probability') or 10),u['id'],data.get('expected_close'),data.get('next_activity'),data.get('status','Open'),data.get('notes'),now,now,u['tenant_id']));audit(conn,u['id'],'CREATE','opportunity',cur.lastrowid,data.get('name',''),self.client_address[0]);conn.commit();return self._json({'id':cur.lastrowid,'ok':True},201)
            if path=='/api/jobs':
                if u['role'] not in ('admin','teamlead','recruiter','sales'): return self._json({'error':'Permission denied'},403)
                seq=(qone(conn,'SELECT COUNT(*) n FROM jobs')['n'] or 0)+401; job_no=data.get('job_no') or f"26-{seq:05d}"; now=utcnow()
                cols=['job_no','title','company_id','contact_id','primary_recruiter_id','sales_user_id','status','priority','position_type','openings','filled','work_mode','city','state','country','zip','start_date','end_date','pay_min','pay_max','bill_min','bill_max','rate_type','profession','specialty','required_skills','required_qualifications','required_licenses','required_certifications','description','submission_guidelines_override','source','external_vms_id','latitude','longitude','tenant_id']
                if data.get('company_id') and not self._tenant_row(conn,'companies',int(data['company_id']),u):return self._json({'error':'Company not found'},404)
                if data.get('contact_id'):
                    contact=self._tenant_row(conn,'contacts',int(data['contact_id']),u)
                    if not contact:return self._json({'error':'Contact not found'},404)
                    if data.get('company_id') and int(contact.get('company_id') or 0)!=int(data.get('company_id') or 0):return self._json({'error':'Contact does not belong to job company'},409)
                try:job_no=safe_identifier(job_no,'job_no')
                except PolicyError as e:return self._json({'error':str(e),'code':e.code},e.status)
                for owner_field in ('primary_recruiter_id','sales_user_id'):
                    if data.get(owner_field) and not self._tenant_row(conn,'users',int(data[owner_field]),u):return self._json({'error':owner_field+' not found'},404)
                vals=[data.get(c) for c in cols]; vals[0]=job_no; vals[4]=vals[4] or u['id']; vals[5]=vals[5] or u['id']; vals[6]=vals[6] or 'Open'; vals[7]=vals[7] or 'Normal'; vals[8]=vals[8] or 'Contract'; vals[9]=vals[9] or 1; vals[10]=vals[10] or 0; vals[11]=vals[11] or 'Onsite'; vals[14]=vals[14] or 'USA'; vals[22]=vals[22] or 'hour'; vals[31]=vals[31] or 'Direct'
                coords=resolve_postal(data.get('zip'))
                if vals[33] is None and coords:vals[33]=coords[0]
                if vals[34] is None and coords:vals[34]=coords[1]
                vals[35]=u['tenant_id']
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
                if not self._tenant_row(conn,'jobs',jid,u) or not self._tenant_row(conn,'candidates',cid,u):return self._json({'error':'Job or candidate not found'},404)
                now=utcnow();target=data.get('status','interested');existing=qone(conn,'SELECT * FROM interested_candidates WHERE job_id=? AND candidate_id=? AND tenant_id=?',(jid,cid,u['tenant_id']))
                if existing:
                    try:ensure_transition('interested',existing['status'],target)
                    except ValueError as e:return self._json({'error':str(e)},409)
                conn.execute('INSERT INTO interested_candidates(job_id,candidate_id,status,source,user_id,created_at,updated_at,tenant_id) VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(job_id,candidate_id) DO UPDATE SET status=excluded.status,user_id=excluded.user_id,updated_at=excluded.updated_at',(jid,cid,target,data.get('source','Manual'),u['id'],now,now,u['tenant_id'])); audit(conn,u['id'],'MARK_INTERESTED','job',jid,f'candidate={cid}',self.client_address[0]);conn.commit();return self._json({'ok':True})
            m=re.fullmatch(r'/api/jobs/(\d+)/submissions',path)
            if m:
                jid=int(m.group(1))
                if u['role']=='supplier':
                    rel=qone(conn,"SELECT * FROM supplier_releases WHERE supplier_id=? AND job_id=? AND tenant_id=? AND status='Open'",(u.get('supplier_id'),jid,u['tenant_id']))
                    if not rel: return self._json({'error':'Permission denied'},403)
                    used=qone(conn,'SELECT COUNT(*) n FROM submissions WHERE job_id=? AND recruiter_id=? AND tenant_id=?',(jid,u['id'],u['tenant_id']))['n']
                    if used>=int(rel.get('max_submissions') or 0):return self._json({'error':'Supplier submission limit reached'},409)
                    supplier_candidate=self._tenant_row(conn,'candidates',int(data.get('candidate_id') or 0),u)
                    if not supplier_candidate or supplier_candidate.get('supplier_id')!=u.get('supplier_id'):return self._json({'error':'Supplier may submit only its own candidates'},403)
                elif u['role'] not in ('admin','teamlead','recruiter','sales'):
                    return self._json({'error':'Permission denied'},403)
                cid=int(data.get('candidate_id') or 0); now=utcnow();
                if not self._tenant_row(conn,'jobs',jid,u) or not self._tenant_row(conn,'candidates',cid,u):return self._json({'error':'Job or candidate not found'},404)
                initial=data.get('status','submitted')
                if initial not in ('draft','submitted'):return self._json({'error':'New submissions must start as draft or submitted'},409)
                cur=conn.execute('INSERT INTO submissions(job_id,candidate_id,recruiter_id,status,client_rate,candidate_rate,availability,recruiter_summary,compliance_status,rtr_status,submitted_at,client_feedback,created_at,updated_at,tenant_id) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(jid,cid,u['id'],initial,data.get('client_rate'),data.get('candidate_rate'),data.get('availability'),data.get('recruiter_summary',''),data.get('compliance_status','Pending'),data.get('rtr_status','Pending'),now if initial!='draft' else None,'',now,now,u['tenant_id'])); sid=cur.lastrowid;audit(conn,u['id'],'CREATE','submission',sid,f'job={jid}, candidate={cid}',self.client_address[0]);conn.commit();return self._json({'id':sid,'ok':True},201)
            m=re.fullmatch(r'/api/submissions/(\d+)/status',path)
            if m:
                sid=int(m.group(1)); st=data.get('status');
                if st not in STATUS_FLOW['submission']: return self._json({'error':'Invalid status'},400)
                submission=self._tenant_row(conn,'submissions',sid,u)
                if not submission:return self._json({'error':'Not found'},404)
                if u['role']=='client':
                    own=qone(conn,'SELECT s.id FROM submissions s JOIN jobs j ON j.id=s.job_id WHERE s.id=? AND j.company_id=?',(sid,u.get('company_id')))
                    if not own: return self._json({'error':'Permission denied'},403)
                    if st not in ('client_review','interview','rejected','offer','hired'): return self._json({'error':'Client cannot set that status'},403)
                elif u['role'] not in ('admin','teamlead','recruiter','sales'):
                    return self._json({'error':'Permission denied'},403)
                try:ensure_transition('submission',submission['status'],st)
                except ValueError as e:return self._json({'error':str(e)},409)
                if st=='hired' and (norm(submission.get('compliance_status')) not in ('approved','complete') or norm(submission.get('rtr_status')) not in ('approved','complete','signed')):return self._json({'error':'RTR and compliance approval are required before hire'},409)
                conn.execute('UPDATE submissions SET status=?,client_feedback=COALESCE(?,client_feedback),compliance_status=COALESCE(?,compliance_status),rtr_status=COALESCE(?,rtr_status),updated_at=? WHERE id=? AND tenant_id=?',(st,data.get('client_feedback'),data.get('compliance_status'),data.get('rtr_status'),utcnow(),sid,u['tenant_id']));record_transition(conn,u,'submission',sid,submission['status'],st,data.get('client_feedback',''));audit(conn,u['id'],'STATUS','submission',sid,st,self.client_address[0]);conn.commit();return self._json({'ok':True})
            if path=='/api/interviews':
                if u['role'] not in ('admin','teamlead','recruiter','sales'): return self._json({'error':'Permission denied'},403)
                sid=int(data.get('submission_id') or 0);submission=self._tenant_row(conn,'submissions',sid,u)
                if not submission:return self._json({'error':'Submission not found'},404)
                try:ensure_transition('submission',submission['status'],'interview')
                except ValueError as e:return self._json({'error':str(e)},409)
                if norm(submission.get('rtr_status')) not in ('approved','complete','signed') or norm(submission.get('compliance_status')) in ('blocked','failed','rejected'):
                    return self._json({'error':'RTR approval and non-blocked compliance are required before interview'},409)
                now=utcnow();cur=conn.execute('INSERT INTO interviews(submission_id,interview_type,scheduled_at,timezone,status,location_or_link,interviewer,feedback,rating,created_at,tenant_id) VALUES(?,?,?,?,?,?,?,?,?,?,?)',(sid,data.get('interview_type','Video'),data.get('scheduled_at'),data.get('timezone','UTC'),data.get('status','scheduled'),data.get('location_or_link',''),data.get('interviewer',''),data.get('feedback',''),data.get('rating'),now,u['tenant_id']));conn.execute('UPDATE submissions SET status="interview",updated_at=? WHERE id=? AND tenant_id=? AND status=?',(now,sid,u['tenant_id'],submission['status']));record_transition(conn,u,'submission',sid,submission['status'],'interview','Interview created');audit(conn,u['id'],'CREATE','interview',cur.lastrowid,f'submission={sid}',self.client_address[0]);conn.commit();return self._json({'id':cur.lastrowid,'ok':True},201)
            if path=='/api/assessments':
                if u['role'] not in ('admin','teamlead','recruiter','hr'): return self._json({'error':'Permission denied'},403)
                if not self._tenant_row(conn,'candidates',int(data.get('candidate_id') or 0),u):return self._json({'error':'Candidate not found'},404)
                cur=conn.execute('INSERT INTO assessments(candidate_id,job_id,title,assessment_type,status,score,max_score,invited_at,completed_at,notes,tenant_id) VALUES(?,?,?,?,?,?,?,?,?,?,?)',(data.get('candidate_id'),data.get('job_id'),data.get('title') or 'Assessment',data.get('assessment_type','Questionnaire'),'Invited',None,data.get('max_score',100),utcnow(),None,data.get('notes',''),u['tenant_id']));aid=cur.lastrowid
                for idx,q in enumerate(data.get('questions') or []):conn.execute('INSERT INTO assessment_questions(assessment_id,prompt,question_type,choices_json,points,sort_order,tenant_id) VALUES(?,?,?,?,?,?,?)',(aid,q.get('prompt'),q.get('question_type','text'),json.dumps(q.get('choices') or []),float(q.get('points') or 1),idx,u['tenant_id']))
                audit(conn,u['id'],'CREATE','assessment',aid,data.get('title',''),self.client_address[0]);conn.commit();return self._json({'id':aid,'ok':True},201)
            if path=='/api/onboarding':
                if u['role'] not in ('admin','teamlead','recruiter','hr'): return self._json({'error':'Permission denied'},403)
                if not self._tenant_row(conn,'candidates',int(data.get('candidate_id') or 0),u):return self._json({'error':'Candidate not found'},404)
                cur=conn.execute('INSERT INTO onboarding_packages(candidate_id,job_id,submission_id,package_name,status,assigned_by,due_date,created_at,tenant_id) VALUES(?,?,?,?,?,?,?,?,?)',(data.get('candidate_id'),data.get('job_id'),data.get('submission_id'),data.get('package_name') or 'Standard Onboarding','not_started',u['id'],data.get('due_date'),utcnow(),u['tenant_id'])); pid=cur.lastrowid
                reqs=data.get('requirements') or [{'type':'E-Sign','name':'Right to Represent'},{'type':'Identity','name':'Identity Verification'},{'type':'Policy','name':'Client Policies'}]
                for r in reqs: conn.execute('INSERT INTO onboarding_requirements(package_id,requirement_type,name,mandatory,status,completed_at,expiry_date,note,evidence_document_id,tenant_id) VALUES(?,?,?,?,?,?,?,?,?,?)',(pid,r.get('type','Document'),r.get('name','Requirement'),1 if r.get('mandatory',True) else 0,'Pending',None,r.get('expiry_date'),'',r.get('evidence_document_id'),u['tenant_id']))
                audit(conn,u['id'],'CREATE','onboarding',pid,data.get('package_name','Standard Onboarding'),self.client_address[0]);conn.commit();return self._json({'id':pid,'ok':True},201)
            m=re.fullmatch(r'/api/onboarding/(\d+)/requirements',path)
            if m:
                if u['role'] not in CANDIDATE_EDIT_ROLES:return self._json({'error':'Permission denied'},403)
                pid=int(m.group(1))
                if not self._tenant_row(conn,'onboarding_packages',pid,u):return self._json({'error':'Not found'},404)
                cur=conn.execute('INSERT INTO onboarding_requirements(package_id,requirement_type,name,mandatory,status,completed_at,expiry_date,note,evidence_document_id,tenant_id) VALUES(?,?,?,?,?,?,?,?,?,?)',(pid,data.get('requirement_type','Document'),data.get('name'),1 if data.get('mandatory',True) else 0,data.get('status','Pending'),None,data.get('expiry_date'),data.get('note'),data.get('evidence_document_id'),u['tenant_id']));conn.execute("UPDATE onboarding_packages SET status='in_progress' WHERE id=? AND tenant_id=?",(pid,u['tenant_id']));audit(conn,u['id'],'CREATE','onboarding_requirement',cur.lastrowid,data.get('name',''),self.client_address[0]);conn.commit();return self._json({'id':cur.lastrowid},201)
            m=re.fullmatch(r'/api/onboarding/requirements/(\d+)/status',path)
            if m:
                if u['role'] not in ('admin','teamlead','recruiter','hr'): return self._json({'error':'Permission denied'},403)
                rid=int(m.group(1)); st=data.get('status','Complete');req=self._tenant_row(conn,'onboarding_requirements',rid,u)
                if not req:return self._json({'error':'Not found'},404)
                conn.execute('UPDATE onboarding_requirements SET status=?,completed_at=?,note=COALESCE(?,note),evidence_document_id=COALESCE(?,evidence_document_id) WHERE id=? AND tenant_id=?',(st,utcnow() if st.lower()=='complete' else None,data.get('note'),data.get('evidence_document_id'),rid,u['tenant_id'])); pkg=qone(conn,'SELECT package_id FROM onboarding_requirements WHERE id=?',(rid,));
                if pkg:
                    counts=qone(conn,"SELECT COUNT(*) total,SUM(CASE WHEN lower(status)='complete' THEN 1 ELSE 0 END) done FROM onboarding_requirements WHERE package_id=?",(pkg['package_id'],)); pst='complete' if counts['total']==counts['done'] else 'in_progress';conn.execute('UPDATE onboarding_packages SET status=? WHERE id=?',(pst,pkg['package_id']))
                audit(conn,u['id'],'STATUS','onboarding_requirement',rid,st,self.client_address[0]);conn.commit();return self._json({'ok':True})
            if path=='/api/assignments':
                if u['role'] not in ('admin','teamlead','hr','finance'): return self._json({'error':'Permission denied'},403)
                try:
                    candidate,job,company,start,approver=assignment_graph(conn,data,u['tenant_id'])
                    bill=float(exact_money(data.get('bill_rate') or 0,'bill_rate'));pay=float(exact_money(data.get('pay_rate') or 0,'pay_rate'))
                except PolicyError as e:return self._json({'error':str(e),'code':e.code},e.status)
                now=utcnow();cur=conn.execute('INSERT INTO assignments(start_id,candidate_id,job_id,company_id,status,start_date,end_date,worksite,cost_center,vms_id,approver_contact_id,bill_rate,pay_rate,overtime_rule,payroll_profile,po_number,created_at,updated_at,tenant_id) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(data.get('start_id'),candidate['id'],job['id'],company['id'],data.get('status','pending'),data.get('start_date'),data.get('end_date'),data.get('worksite'),data.get('cost_center'),data.get('vms_id'),data.get('approver_contact_id'),bill,pay,data.get('overtime_rule','1.5x after 40h'),data.get('payroll_profile','Hourly'),data.get('po_number'),now,now,u['tenant_id']));audit(conn,u['id'],'CREATE','assignment',cur.lastrowid,'',self.client_address[0]);conn.commit();return self._json({'id':cur.lastrowid,'ok':True},201)
            if path=='/api/timesheets':
                if u['role'] not in ('admin','teamlead','finance','hr','worker'): return self._json({'error':'Permission denied'},403)
                cid=u['candidate_id'] if u['role']=='worker' else data.get('candidate_id'); aid=int(data.get('assignment_id') or 0)
                assignment=self._tenant_row(conn,'assignments',aid,u)
                if not assignment:return self._json({'error':'Assignment not found'},404)
                if int(assignment.get('candidate_id') or 0)!=int(cid or 0):return self._json({'error':'Candidate does not match assignment'},409)
                if u['role']=='worker' and assignment.get('candidate_id')!=u.get('candidate_id'): return self._json({'error':'Permission denied'},403)
                week=data.get('week_start')
                try:
                    if time_period_locked(conn,u['tenant_id'],assignment,week,u['id']):return self._json({'error':'Time period is locked'},409)
                    daily=data.get('daily') or {};clean_daily={k:bounded_hours(v,str(k)) for k,v in daily.items()};total=sum(clean_daily.values())
                except PolicyError as e:return self._json({'error':str(e),'code':e.code},e.status)
                regular=min(total,40);ot=max(0,total-40);now=utcnow();status=data.get('status','submitted')
                if status not in ('draft','submitted'):return self._json({'error':'New timesheets must start as draft or submitted'},409)
                existing=qone(conn,'SELECT * FROM timesheets WHERE assignment_id=? AND week_start=? AND tenant_id=?',(aid,week,u['tenant_id']))
                if existing:
                    if norm(existing.get('status')) not in ('draft','rejected','reopened'):return self._json({'error':'Existing timesheet is not editable; use an explicit reopen/status operation'},409)
                    conn.execute('UPDATE timesheets SET candidate_id=?,status=?,total_hours=?,regular_hours=?,overtime_hours=?,daily_json=?,submitted_at=?,approved_by=NULL,approved_at=NULL,rejection_note=NULL,updated_at=? WHERE id=? AND tenant_id=?',(cid,status,total,regular,ot,json.dumps(clean_daily),now if status=='submitted' else None,now,existing['id'],u['tenant_id']));tid=existing['id'];action='UPDATE'
                else:
                    cur=conn.execute('INSERT INTO timesheets(assignment_id,candidate_id,week_start,status,total_hours,regular_hours,overtime_hours,daily_json,submitted_at,approved_by,approved_at,rejection_note,created_at,updated_at,tenant_id) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(aid,cid,week,status,total,regular,ot,json.dumps(clean_daily),now if status=='submitted' else None,None,None,None,now,now,u['tenant_id']));tid=cur.lastrowid;action='CREATE'
                audit(conn,u['id'],action,'timesheet',tid,f'{total} hours',self.client_address[0]);conn.commit();return self._json({'id':tid,'total_hours':total,'regular_hours':regular,'overtime_hours':ot,'ok':True},201 if action=='CREATE' else 200)
            m=re.fullmatch(r'/api/timesheets/(\d+)/status',path)
            if m:
                if u['role'] not in ('admin','teamlead','finance','hr','worker','client','approver'):
                    return self._json({'error':'Permission denied'},403)
                tid=int(m.group(1)); st=data.get('status');
                if st in ('draft','submitted') and u['role'] not in ('admin','teamlead','finance','hr','worker'):
                    return self._json({'error':'Permission denied'},403)
                if st not in TRANSITIONS['timesheet']: return self._json({'error':'Invalid status'},400)
                sheet=self._tenant_row(conn,'timesheets',tid,u)
                if not sheet:return self._json({'error':'Not found'},404)
                if u['role'] in ('client','approver'):
                    own=qone(conn,'SELECT t.id FROM timesheets t JOIN assignments a ON a.id=t.assignment_id WHERE t.id=? AND t.tenant_id=? AND a.company_id=?',(tid,u['tenant_id'],u.get('company_id')))
                    if not own:return self._json({'error':'Permission denied'},403)
                if st in ('approved','rejected') and u['role'] not in ('admin','finance','client','approver','teamlead'): return self._json({'error':'Permission denied'},403)
                if st in ('reopened','invoiced') and u['role'] not in ('admin','finance','teamlead'):return self._json({'error':'Permission denied'},403)
                if u['role']=='worker' and sheet.get('candidate_id')!=u.get('candidate_id'):return self._json({'error':'Permission denied'},403)
                assignment=self._tenant_row(conn,'assignments',sheet['assignment_id'],u)
                try:
                    if assignment and time_period_locked(conn,u['tenant_id'],assignment,sheet.get('week_start'),u['id']):return self._json({'error':'Time period is locked'},409)
                except PolicyError as e:return self._json({'error':str(e),'code':e.code},e.status)
                try:ensure_transition('timesheet',sheet['status'],st)
                except ValueError as e:return self._json({'error':str(e)},409)
                conn.execute('UPDATE timesheets SET status=?,approved_by=?,approved_at=?,rejection_note=?,updated_at=? WHERE id=? AND tenant_id=?',(st,u['id'] if st=='approved' else None,utcnow() if st=='approved' else None,data.get('rejection_note'),utcnow(),tid,u['tenant_id']));record_transition(conn,u,'timesheet',tid,sheet['status'],st,data.get('rejection_note',''));audit(conn,u['id'],'STATUS','timesheet',tid,st,self.client_address[0]);conn.commit();return self._json({'ok':True})
            if path=='/api/expenses':
                if u['role'] not in ('admin','teamlead','finance','hr','worker'): return self._json({'error':'Permission denied'},403)
                assignment=self._tenant_row(conn,'assignments',int(data.get('assignment_id') or 0),u)
                if not assignment:return self._json({'error':'Assignment not found'},404)
                if u['role']=='worker' and assignment.get('candidate_id')!=u.get('candidate_id'): return self._json({'error':'Permission denied'},403)
                if data.get('status','submitted') not in ('draft','submitted'):return self._json({'error':'New expenses must start as draft or submitted'},409)
                cid=u['candidate_id'] if u['role']=='worker' else data.get('candidate_id')
                if int(assignment.get('candidate_id') or 0)!=int(cid or 0):return self._json({'error':'Candidate does not match assignment'},409)
                try:amount=float(exact_money(data.get('amount'),'amount'))
                except PolicyError as e:return self._json({'error':str(e),'code':e.code},e.status)
                cur=conn.execute('INSERT INTO expenses(assignment_id,candidate_id,expense_date,category,amount,receipt_ref,status,description,approved_by,approved_at,rejection_note,created_at,tenant_id) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',(data.get('assignment_id'),cid,data.get('expense_date') or today(),data.get('category','Other'),amount,data.get('receipt_ref',''),data.get('status','submitted'),data.get('description',''),None,None,None,utcnow(),u['tenant_id']));audit(conn,u['id'],'CREATE','expense',cur.lastrowid,str(amount),self.client_address[0]);conn.commit();return self._json({'id':cur.lastrowid,'ok':True},201)
            m=re.fullmatch(r'/api/expenses/(\d+)/status',path)
            if m:
                if u['role'] not in ('admin','teamlead','finance','client','approver'): return self._json({'error':'Permission denied'},403)
                eid=int(m.group(1)); st=data.get('status')
                if st not in TRANSITIONS['expense']:return self._json({'error':'Invalid status'},400)
                expense=self._tenant_row(conn,'expenses',eid,u)
                if not expense:return self._json({'error':'Not found'},404)
                if u['role'] in ('client','approver'):
                    own=qone(conn,'SELECT e.id FROM expenses e JOIN assignments a ON a.id=e.assignment_id WHERE e.id=? AND a.company_id=?',(eid,u.get('company_id')))
                    if not own: return self._json({'error':'Permission denied'},403)
                try:ensure_transition('expense',expense['status'],st)
                except ValueError as e:return self._json({'error':str(e)},409)
                conn.execute('UPDATE expenses SET status=?,approved_by=?,approved_at=?,rejection_note=? WHERE id=? AND tenant_id=?',(st,u['id'] if st=='approved' else None,utcnow() if st=='approved' else None,data.get('rejection_note'),eid,u['tenant_id']));record_transition(conn,u,'expense',eid,expense['status'],st,data.get('rejection_note',''));audit(conn,u['id'],'STATUS','expense',eid,st,self.client_address[0]);conn.commit();return self._json({'ok':True})
            if path=='/api/invoices':
                if u['role'] not in ('admin','finance'): return self._json({'error':'Permission denied'},403)
                if data.get('status','draft') not in ('draft','issued'):return self._json({'error':'New invoices must start as draft or issued'},409)
                if data.get('company_id') and not self._tenant_row(conn,'companies',int(data['company_id']),u):return self._json({'error':'Company not found'},404)
                if data.get('assignment_id') and not self._tenant_row(conn,'assignments',int(data['assignment_id']),u):return self._json({'error':'Assignment not found'},404)
                try:amount=float(exact_money(data.get('amount'),'amount'));tax=float(exact_money(data.get('tax') or 0,'tax'))
                except PolicyError as e:return self._json({'error':str(e),'code':e.code},e.status)
                if data.get('assignment_id'):
                    a=self._tenant_row(conn,'assignments',int(data['assignment_id']),u)
                    if a and data.get('company_id') and int(a.get('company_id') or 0)!=int(data.get('company_id') or 0):return self._json({'error':'Invoice company does not match assignment company'},409)
                seq=(qone(conn,'SELECT COUNT(*) n FROM invoices WHERE tenant_id=?',(u['tenant_id'],))['n'] or 0)+902; inv=data.get('invoice_no') or (f'INV-26{seq:04d}' if u['tenant_id']==1 else f'T{u["tenant_id"]}-INV-{seq:04d}');now=utcnow();cur=conn.execute('INSERT INTO invoices(invoice_no,company_id,assignment_id,period_start,period_end,amount,tax,status,due_date,issued_at,paid_at,created_at,paid_amount,tenant_id) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(inv,data.get('company_id'),data.get('assignment_id'),data.get('period_start'),data.get('period_end'),amount,tax,data.get('status','draft'),data.get('due_date'),now if data.get('status')=='issued' else None,None,now,0,u['tenant_id']));audit(conn,u['id'],'CREATE','invoice',cur.lastrowid,inv,self.client_address[0]);conn.commit();return self._json({'id':cur.lastrowid,'invoice_no':inv,'ok':True},201)
            if path=='/api/communications':
                if u['role'] not in INTERNAL_ROLES:
                    if u['role'] not in ('candidate','worker') or data.get('entity_type')!='candidate' or int(data.get('entity_id') or 0)!=int(u.get('candidate_id') or 0):return self._json({'error':'Permission denied'},403)
                cur=conn.execute('INSERT INTO communications(entity_type,entity_id,channel,direction,subject,body,user_id,status,created_at,tenant_id) VALUES(?,?,?,?,?,?,?,?,?,?)',(data.get('entity_type'),data.get('entity_id'),data.get('channel','Email'),data.get('direction','Outbound'),data.get('subject',''),data.get('body',''),u['id'],data.get('status','Logged'),utcnow(),u['tenant_id']));audit(conn,u['id'],'CREATE','communication',cur.lastrowid,data.get('subject',''),self.client_address[0]);conn.commit();return self._json({'id':cur.lastrowid,'ok':True},201)
            if path=='/api/users':
                if u['role']!='admin': return self._json({'error':'Permission denied'},403)
                for field,table in (('company_id','companies'),('candidate_id','candidates'),('supplier_id','suppliers')):
                    if data.get(field) and not self._tenant_row(conn,table,int(data[field]),u):return self._json({'error':field+' not found'},404)
                email=(data.get('email') or '').strip().lower()
                if not email or '@' not in email:return self._json({'error':'Valid email required'},400)
                if data.get('password'):return self._json({'error':'Direct passwords are not accepted; use invitation setup'},400)
                if qone(conn,'SELECT id FROM users WHERE lower(email)=?',(email,)):return self._json({'error':'Email already belongs to an ATS identity'},409)
                token=secrets.token_urlsafe(32);temporary=secrets.token_urlsafe(48);now=utcnow();cur=conn.execute('INSERT INTO users(email,pass_hash,name,role,company_id,candidate_id,supplier_id,active,created_at,tenant_id) VALUES(?,?,?,?,?,?,?,0,?,?)',(email,hash_password(temporary),data.get('name') or email,data.get('role','recruiter'),data.get('company_id'),data.get('candidate_id'),data.get('supplier_id'),now,u['tenant_id']));uid=cur.lastrowid
                exp=(datetime.now(timezone.utc)+timedelta(days=7)).replace(microsecond=0).isoformat();conn.execute("INSERT INTO auth_invitations_r14(email,role,token_hash,expires_at,status,invited_by,created_at,tenant_id) VALUES(?,?,?,?, 'Pending',?,?,?)",(email,data.get('role','recruiter'),hashlib.sha256(token.encode()).hexdigest(),exp,u['id'],now,u['tenant_id']));audit(conn,u['id'],'INVITE','user',uid,email,self.client_address[0]);conn.commit();return self._json({'id':uid,'ok':True,'invitation_token':token,'expires_at':exp},201)
            m=re.fullmatch(r'/api/jobs/(\d+)/clone',path)
            if m:
                if u['role'] not in JOB_EDIT_ROLES:return self._json({'error':'Permission denied'},403)
                source=self._tenant_row(conn,'jobs',int(m.group(1)),u)
                if not source:return self._json({'error':'Not found'},404)
                seq=(qone(conn,'SELECT COUNT(*) n FROM jobs WHERE tenant_id=?',(u['tenant_id'],))['n'] or 0)+401;job_no=data.get('job_no') or f'26-{seq:05d}'
                cols=['job_no','title','company_id','contact_id','primary_recruiter_id','sales_user_id','status','priority','position_type','openings','filled','work_mode','city','state','country','zip','start_date','end_date','pay_min','pay_max','bill_min','bill_max','rate_type','profession','specialty','required_skills','required_qualifications','required_licenses','required_certifications','description','submission_guidelines_override','source','external_vms_id','latitude','longitude','tenant_id','created_at','updated_at']
                vals=[job_no,data.get('title') or source['title']+' (Copy)']+[source.get(x) for x in cols[2:]]
                vals[6]='Draft';vals[10]=0;vals[-2]=utcnow();vals[-1]=utcnow()
                cur=conn.execute('INSERT INTO jobs('+','.join(cols)+') VALUES('+','.join('?' for _ in cols)+')',vals);audit(conn,u['id'],'CLONE','job',cur.lastrowid,f'from={source["id"]}',self.client_address[0]);conn.commit();return self._json({'id':cur.lastrowid,'job_no':job_no},201)
            m=re.fullmatch(r'/api/jobs/(\d+)/users',path)
            if m:
                if u['role'] not in JOB_EDIT_ROLES:return self._json({'error':'Permission denied'},403)
                jid=int(m.group(1));uid=int(data.get('user_id') or 0)
                if not self._tenant_row(conn,'jobs',jid,u) or not self._tenant_row(conn,'users',uid,u):return self._json({'error':'Job or user not found'},404)
                cur=conn.execute('INSERT INTO job_users(job_id,user_id,role_name,tenant_id) VALUES(?,?,?,?) ON CONFLICT(job_id,user_id,role_name) DO NOTHING',(jid,uid,data.get('role_name','Secondary Recruiter'),u['tenant_id']));row=qone(conn,'SELECT * FROM job_users WHERE job_id=? AND user_id=? AND role_name=?',(jid,uid,data.get('role_name','Secondary Recruiter')));audit(conn,u['id'],'ASSIGN_USER','job',jid,str(uid),self.client_address[0]);conn.commit();return self._json(row,201)
            m=re.fullmatch(r'/api/jobs/(\d+)/distribution',path)
            if m:
                if u['role'] not in JOB_EDIT_ROLES:return self._json({'error':'Permission denied'},403)
                jid=int(m.group(1));
                if not self._tenant_row(conn,'jobs',jid,u):return self._json({'error':'Not found'},404)
                for field,table in (('company_id','companies'),('contact_id','contacts'),('primary_recruiter_id','users'),('sales_user_id','users')):
                    if data.get(field) and not self._tenant_row(conn,table,int(data[field]),u):return self._json({'error':field+' not found'},404)
                status=data.get('status','Published');now=utcnow();cur=conn.execute('INSERT INTO job_distribution(job_id,channel,external_post_id,status,published_at,last_sync,applications,tenant_id) VALUES(?,?,?,?,?,?,?,?)',(jid,data.get('channel','Internal Careers'),data.get('external_post_id'),status,now if norm(status)=='published' else None,now,0,u['tenant_id']));audit(conn,u['id'],'DISTRIBUTE','job',jid,f'{data.get("channel")}:{status}',self.client_address[0]);conn.commit();return self._json({'id':cur.lastrowid,'status':status},201)
            m=re.fullmatch(r'/api/leads/(\d+)/convert',path)
            if m:
                if u['role'] not in ('admin','teamlead','sales'):return self._json({'error':'Permission denied'},403)
                lead=self._tenant_row(conn,'leads',int(m.group(1)),u)
                if not lead:return self._json({'error':'Not found'},404)
                now=utcnow();cur=conn.execute('INSERT INTO opportunities(company_id,contact_id,name,stage,value,probability,owner_user_id,expected_close,next_activity,status,notes,created_at,updated_at,tenant_id) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(lead.get('company_id'),lead.get('contact_id'),data.get('name') or lead['title'],'Qualified',float(data.get('value') or 0),int(data.get('probability') or 25),u['id'],data.get('expected_close'),lead.get('next_action'),'Open',lead.get('notes'),now,now,u['tenant_id']));conn.execute("UPDATE leads SET status='Converted' WHERE id=? AND tenant_id=?",(lead['id'],u['tenant_id']));audit(conn,u['id'],'CONVERT','lead',lead['id'],f'opportunity={cur.lastrowid}',self.client_address[0]);conn.commit();return self._json({'opportunity_id':cur.lastrowid},201)
            m=re.fullmatch(r'/api/assessments/(\d+)/answers',path)
            if m:
                aid=int(m.group(1));assessment=self._tenant_row(conn,'assessments',aid,u)
                if not assessment:return self._json({'error':'Not found'},404)
                if u['role'] in ('candidate','worker') and assessment['candidate_id']!=u.get('candidate_id'):return self._json({'error':'Permission denied'},403)
                total=0.0
                for answer in data.get('answers') or []:
                    question=qone(conn,'SELECT * FROM assessment_questions WHERE id=? AND assessment_id=? AND tenant_id=?',(answer.get('question_id'),aid,u['tenant_id']))
                    if not question:continue
                    points=0.0 if u['role'] in ('candidate','worker') else float(answer.get('awarded_points') or 0);total+=points
                    conn.execute('INSERT INTO assessment_answers(assessment_id,question_id,answer,awarded_points,answered_at,tenant_id) VALUES(?,?,?,?,?,?) ON CONFLICT(assessment_id,question_id) DO UPDATE SET answer=excluded.answer,awarded_points=excluded.awarded_points,answered_at=excluded.answered_at',(aid,question['id'],answer.get('answer'),points,utcnow(),u['tenant_id']))
                target=data.get('status','Completed')
                if norm(target) not in ('in_progress','completed'):return self._json({'error':'Answers may set only in_progress or completed'},409)
                conn.execute('UPDATE assessments SET status=?,score=?,completed_at=? WHERE id=? AND tenant_id=?',(target,total,utcnow() if norm(target)=='completed' else None,aid,u['tenant_id']));audit(conn,u['id'],'ANSWER','assessment',aid,f'score={total}',self.client_address[0]);conn.commit();return self._json({'id':aid,'score':total,'status':target})
            if path=='/api/starts':
                if u['role'] not in ('admin','teamlead','recruiter','hr'):return self._json({'error':'Permission denied'},403)
                sid=int(data.get('submission_id') or 0);submission=self._tenant_row(conn,'submissions',sid,u)
                if not submission or norm(submission['status'])!='hired':return self._json({'error':'A tenant-owned hired submission is required'},409)
                now=utcnow();cur=conn.execute('INSERT INTO starts(submission_id,start_date,status,cancellation_reason,created_at,updated_at,tenant_id) VALUES(?,?,?,?,?,?,?)',(sid,data.get('start_date'),data.get('status','Confirmed'),None,now,now,u['tenant_id']));audit(conn,u['id'],'CREATE','start',cur.lastrowid,'',self.client_address[0]);conn.commit();return self._json({'id':cur.lastrowid},201)
            if path=='/api/shifts':
                if u['role'] not in WORKFORCE_ADMIN_ROLES:return self._json({'error':'Permission denied'},403)
                assignment=self._tenant_row(conn,'assignments',int(data.get('assignment_id') or 0),u)
                if not assignment:return self._json({'error':'Assignment not found'},404)
                cur=conn.execute('INSERT INTO shifts(assignment_id,candidate_id,shift_date,start_time,end_time,location,status,created_at,tenant_id) VALUES(?,?,?,?,?,?,?,?,?)',(assignment['id'],assignment['candidate_id'],data.get('shift_date'),data.get('start_time'),data.get('end_time'),data.get('location') or assignment.get('worksite'),data.get('status','Scheduled'),utcnow(),u['tenant_id']));audit(conn,u['id'],'CREATE','shift',cur.lastrowid,'',self.client_address[0]);conn.commit();return self._json({'id':cur.lastrowid},201)
            if path=='/api/attendance':
                if u['role'] not in WORKFORCE_ADMIN_ROLES|{'worker'}:return self._json({'error':'Permission denied'},403)
                shift=self._tenant_row(conn,'shifts',int(data.get('shift_id') or 0),u)
                cid=int(data.get('candidate_id') or (shift or {}).get('candidate_id') or 0)
                if not shift or (u['role']=='worker' and cid!=u.get('candidate_id')):return self._json({'error':'Shift not found or denied'},403)
                cur=conn.execute('INSERT INTO attendance(shift_id,candidate_id,check_in,check_out,status,note,tenant_id) VALUES(?,?,?,?,?,?,?)',(shift['id'],cid,data.get('check_in'),data.get('check_out'),data.get('status','Present'),data.get('note'),u['tenant_id']));audit(conn,u['id'],'CREATE','attendance',cur.lastrowid,'',self.client_address[0]);conn.commit();return self._json({'id':cur.lastrowid},201)
            if path=='/api/purchase-orders':
                if u['role'] not in ('admin','finance','teamlead'):return self._json({'error':'Permission denied'},403)
                if data.get('company_id') and not self._tenant_row(conn,'companies',int(data['company_id']),u):return self._json({'error':'Company not found'},404)
                if data.get('job_id') and not self._tenant_row(conn,'jobs',int(data['job_id']),u):return self._json({'error':'Job not found'},404)
                if data.get('assignment_id') and not self._tenant_row(conn,'assignments',int(data['assignment_id']),u):return self._json({'error':'Assignment not found'},404)
                cur=conn.execute('INSERT INTO purchase_orders(company_id,job_id,assignment_id,po_number,amount,start_date,end_date,status,tenant_id) VALUES(?,?,?,?,?,?,?,?,?)',(data.get('company_id'),data.get('job_id'),data.get('assignment_id'),data.get('po_number'),float(data.get('amount') or 0),data.get('start_date'),data.get('end_date'),data.get('status','Open'),u['tenant_id']));audit(conn,u['id'],'CREATE','purchase_order',cur.lastrowid,data.get('po_number',''),self.client_address[0]);conn.commit();return self._json({'id':cur.lastrowid},201)
            m=re.fullmatch(r'/api/invoices/(\d+)/payments',path)
            if m:
                if u['role'] not in ('admin','finance'):return self._json({'error':'Permission denied'},403)
                invoice=self._tenant_row(conn,'invoices',int(m.group(1)),u)
                if not invoice:return self._json({'error':'Not found'},404)
                if norm(invoice['status']) not in ('issued','part_paid'):return self._json({'error':'Only issued invoices can receive payment'},409)
                amount=float(data.get('amount') or 0);balance=float(invoice['amount'] or 0)+float(invoice['tax'] or 0)-float(invoice.get('paid_amount') or 0)
                if amount<=0 or amount>balance+0.005:return self._json({'error':'Payment must be positive and no greater than balance'},400)
                new_paid=float(invoice.get('paid_amount') or 0)+amount;target='paid' if new_paid+0.005>=float(invoice['amount'] or 0)+float(invoice['tax'] or 0) else 'part_paid';now=utcnow()
                cur=conn.execute('INSERT INTO invoice_payments(invoice_id,amount,reference,payment_date,user_id,created_at,tenant_id) VALUES(?,?,?,?,?,?,?)',(invoice['id'],amount,data.get('reference'),data.get('payment_date') or today(),u['id'],now,u['tenant_id']));conn.execute('UPDATE invoices SET paid_amount=?,status=?,paid_at=? WHERE id=? AND tenant_id=?',(new_paid,target,now if target=='paid' else None,invoice['id'],u['tenant_id']));record_transition(conn,u,'invoice',invoice['id'],invoice['status'],target,data.get('reference',''));audit(conn,u['id'],'PAYMENT','invoice',invoice['id'],str(amount),self.client_address[0]);conn.commit();return self._json({'id':cur.lastrowid,'status':target,'paid_amount':new_paid,'balance':round(balance-amount,2)},201)
            if path in ('/api/vms/accounts','/api/vms/mappings'):
                if u['role'] not in ('admin','teamlead'):return self._json({'error':'Permission denied'},403)
                if path.endswith('accounts'):cur=conn.execute('INSERT INTO vms_accounts(name,platform,status,sync_mode,last_sync,notes,last_error,tenant_id) VALUES(?,?,?,?,?,?,?,?)',(data.get('name'),data.get('platform'),data.get('status','Active'),data.get('sync_mode','Internal'),None,data.get('notes'),None,u['tenant_id']))
                else:
                    if not self._tenant_row(conn,'vms_accounts',int(data.get('vms_account_id') or 0),u):return self._json({'error':'VMS account not found'},404)
                    cur=conn.execute('INSERT INTO vms_mappings(vms_account_id,object_type,external_id,internal_id,external_status,internal_status,mapping_json,updated_at,tenant_id) VALUES(?,?,?,?,?,?,?,?,?)',(data.get('vms_account_id'),data.get('object_type'),data.get('external_id'),data.get('internal_id'),data.get('external_status'),data.get('internal_status'),json.dumps(data.get('mapping') or {}),utcnow(),u['tenant_id']))
                audit(conn,u['id'],'CREATE','vms',cur.lastrowid,path,self.client_address[0]);conn.commit();return self._json({'id':cur.lastrowid},201)
            m=re.fullmatch(r'/api/vms/accounts/(\d+)/(sync|retry)',path)
            if m:
                if u['role'] not in ('admin','teamlead'):return self._json({'error':'Permission denied'},403)
                account=self._tenant_row(conn,'vms_accounts',int(m.group(1)),u)
                if not account:return self._json({'error':'Not found'},404)
                status='Success';detail='Internal mappings reconciled; external network calls remain adapter-controlled.';cur=conn.execute('INSERT INTO vms_sync_history(vms_account_id,status,detail,retry_of,user_id,created_at,tenant_id) VALUES(?,?,?,?,?,?,?)',(account['id'],status,detail,data.get('retry_of'),u['id'],utcnow(),u['tenant_id']));conn.execute('UPDATE vms_accounts SET last_sync=?,last_error=NULL WHERE id=? AND tenant_id=?',(utcnow(),account['id'],u['tenant_id']));audit(conn,u['id'],'SYNC','vms_account',account['id'],status,self.client_address[0]);conn.commit();return self._json({'run_id':cur.lastrowid,'status':status})
            if path=='/api/suppliers':
                if u['role'] not in ('admin','teamlead','sales'):return self._json({'error':'Permission denied'},403)
                cur=conn.execute('INSERT INTO suppliers(name,status,contact_name,email,phone,tier,notes,tenant_id) VALUES(?,?,?,?,?,?,?,?)',(data.get('name'),data.get('status','Active'),data.get('contact_name'),data.get('email'),data.get('phone'),data.get('tier','Preferred'),data.get('notes'),u['tenant_id']));audit(conn,u['id'],'CREATE','supplier',cur.lastrowid,data.get('name',''),self.client_address[0]);conn.commit();return self._json({'id':cur.lastrowid},201)
            m=re.fullmatch(r'/api/suppliers/(\d+)/releases',path)
            if m:
                if u['role'] not in ('admin','teamlead','sales'):return self._json({'error':'Permission denied'},403)
                supplier=self._tenant_row(conn,'suppliers',int(m.group(1)),u);job=self._tenant_row(conn,'jobs',int(data.get('job_id') or 0),u)
                if not supplier or not job:return self._json({'error':'Supplier or job not found'},404)
                existing=qone(conn,'SELECT * FROM supplier_releases WHERE supplier_id=? AND job_id=? AND tenant_id=?',(supplier['id'],job['id'],u['tenant_id']))
                if existing:
                    conn.execute('UPDATE supplier_releases SET status=?,max_submissions=?,released_at=? WHERE id=?',(data.get('status','Open'),int(data.get('max_submissions') or 3),utcnow(),existing['id']));rid=existing['id']
                else:rid=conn.execute('INSERT INTO supplier_releases(supplier_id,job_id,released_at,status,max_submissions,tenant_id) VALUES(?,?,?,?,?,?)',(supplier['id'],job['id'],utcnow(),data.get('status','Open'),int(data.get('max_submissions') or 3),u['tenant_id'])).lastrowid
                audit(conn,u['id'],'RELEASE','supplier',supplier['id'],f'job={job["id"]}',self.client_address[0]);conn.commit();return self._json({'id':rid},201)
            if path=='/api/tasks':
                if u['role'] not in INTERNAL_ROLES:return self._json({'error':'Permission denied'},403)
                cur=conn.execute('INSERT INTO tasks(entity_type,entity_id,title,due_at,owner_user_id,status,priority,created_at,tenant_id) VALUES(?,?,?,?,?,?,?,?,?)',(data.get('entity_type'),data.get('entity_id'),data.get('title'),data.get('due_at'),data.get('owner_user_id') or u['id'],data.get('status','Open'),data.get('priority','Normal'),utcnow(),u['tenant_id']));audit(conn,u['id'],'CREATE','task',cur.lastrowid,data.get('title',''),self.client_address[0]);conn.commit();return self._json({'id':cur.lastrowid},201)
            if path=='/api/automations':
                if u['role'] not in ('admin','teamlead'):return self._json({'error':'Permission denied'},403)
                now=utcnow();cur=conn.execute('INSERT INTO automations(name,trigger_name,condition_json,action_json,active,created_at,updated_at,tenant_id) VALUES(?,?,?,?,?,?,?,?)',(data.get('name'),data.get('trigger_name'),json.dumps(data.get('condition') or {}),json.dumps(data.get('action') or {}),1 if data.get('active',True) else 0,now,now,u['tenant_id']));audit(conn,u['id'],'CREATE','automation',cur.lastrowid,data.get('name',''),self.client_address[0]);conn.commit();return self._json({'id':cur.lastrowid},201)
            m=re.fullmatch(r'/api/automations/(\d+)/run',path)
            if m:
                if u['role'] not in ('admin','teamlead'):return self._json({'error':'Permission denied'},403)
                rule=self._tenant_row(conn,'automations',int(m.group(1)),u)
                if not rule:return self._json({'error':'Not found'},404)
                try:action=json.loads(rule.get('action_json') or '{}')
                except Exception:action={}
                supported=action.get('type') in ('create_task','log_communication','set_status')
                dry=bool(data.get('dry_run',False));result={'supported':supported,'action':action,'executed':False}
                if not supported:status='Unsupported'
                elif dry:status='Dry Run';result['would_execute']=True
                elif action.get('type')=='create_task':
                    conn.execute('INSERT INTO tasks(entity_type,entity_id,title,due_at,owner_user_id,status,priority,created_at,tenant_id) VALUES(?,?,?,?,?,?,?,?,?)',(data.get('entity_type','automation'),data.get('entity_id'),action.get('title','Automation task'),action.get('due_at'),action.get('owner_user_id') or u['id'],'Open',action.get('priority','Normal'),utcnow(),u['tenant_id']));status='Success';result['executed']=True
                elif action.get('type')=='log_communication':
                    conn.execute('INSERT INTO communications(entity_type,entity_id,channel,direction,subject,body,user_id,status,created_at,tenant_id) VALUES(?,?,?,?,?,?,?,?,?,?)',(data.get('entity_type'),data.get('entity_id'),'Internal','Outbound',action.get('subject','Automation'),action.get('body',''),u['id'],'Logged',utcnow(),u['tenant_id']));status='Success';result['executed']=True
                else:status='Validated';result['executed']=False;result['detail']='set_status requires an explicit lifecycle endpoint and is validation-only'
                cur=conn.execute('INSERT INTO automation_runs(automation_id,dry_run,status,result_json,user_id,created_at,tenant_id) VALUES(?,?,?,?,?,?,?)',(rule['id'],1 if dry else 0,status,json.dumps(result),u['id'],utcnow(),u['tenant_id']));audit(conn,u['id'],'RUN','automation',rule['id'],status,self.client_address[0]);conn.commit();return self._json({'run_id':cur.lastrowid,'status':status,'result':result})
            if path=='/api/integrations':
                if u['role']!='admin':return self._json({'error':'Permission denied'},403)
                try:config_json=connector_config_json(data.get('config'))
                except ValueError as e:return self._json({'error':str(e)},400)
                cur=conn.execute('INSERT INTO integration_connectors(category,name,mode,status,config_json,last_sync,notes,credential_ref,tenant_id) VALUES(?,?,?,?,?,?,?,?,?)',(data.get('category'),data.get('name'),data.get('mode','Internal'),data.get('status','Configured'),config_json,None,data.get('notes'),data.get('credential_ref'),u['tenant_id']));audit(conn,u['id'],'CREATE','integration',cur.lastrowid,data.get('name',''),self.client_address[0]);conn.commit();return self._json({'id':cur.lastrowid},201)
            m=re.fullmatch(r'/api/integrations/(\d+)/(test|sync)',path)
            if m:
                if u['role']!='admin':return self._json({'error':'Permission denied'},403)
                connector=self._tenant_row(conn,'integration_connectors',int(m.group(1)),u)
                if not connector:return self._json({'error':'Not found'},404)
                action=m.group(2);external=norm(connector.get('mode')) not in ('internal','demo');status='External Credentials Required' if external and not connector.get('credential_ref') else 'Success';detail='Configuration metadata validated; no secret values were exposed.'
                cur=conn.execute('INSERT INTO integration_logs(connector_id,action,status,detail,user_id,created_at,tenant_id) VALUES(?,?,?,?,?,?,?)',(connector['id'],action,status,detail,u['id'],utcnow(),u['tenant_id']));conn.execute('UPDATE integration_connectors SET last_sync=? WHERE id=? AND tenant_id=?',(utcnow() if status=='Success' else connector.get('last_sync'),connector['id'],u['tenant_id']));audit(conn,u['id'],action.upper(),'integration',connector['id'],status,self.client_address[0]);conn.commit();return self._json({'log_id':cur.lastrowid,'status':status,'detail':detail})
            if path=='/api/custom-fields':
                if u['role']!='admin':return self._json({'error':'Permission denied'},403)
                if data.get('field_type') not in ('text','number','date','boolean','select'):return self._json({'error':'field_type must be text, number, date, boolean, or select'},400)
                cur=conn.execute('INSERT INTO custom_fields(entity_type,field_name,field_type,required,options_json,active,tenant_id) VALUES(?,?,?,?,?,?,?)',(data.get('entity_type'),data.get('field_name'),data.get('field_type'),1 if data.get('required') else 0,json.dumps(data.get('options') or []),1,u['tenant_id']));audit(conn,u['id'],'CREATE','custom_field',cur.lastrowid,data.get('field_name',''),self.client_address[0]);conn.commit();return self._json({'id':cur.lastrowid},201)
            if path=='/api/custom-values':
                if u['role'] not in INTERNAL_ROLES:return self._json({'error':'Permission denied'},403)
                field=self._tenant_row(conn,'custom_fields',int(data.get('field_id') or 0),u)
                if not field:return self._json({'error':'Field not found'},404)
                entity_type=data.get('entity_type');entity_table={'candidate':'candidates','job':'jobs','company':'companies','contact':'contacts','assignment':'assignments'}.get(entity_type)
                if not entity_table or not self._tenant_row(conn,entity_table,int(data.get('entity_id') or 0),u):return self._json({'error':'Tenant-owned entity not found'},404)
                value=data.get('value')
                try:
                    if field['field_type']=='number':float(value)
                    elif field['field_type']=='boolean' and norm(str(value)) not in ('true','false','1','0','yes','no'):raise ValueError()
                    elif field['field_type']=='date':datetime.fromisoformat(str(value)[:10])
                    elif field['field_type']=='select' and value not in json.loads(field.get('options_json') or '[]'):raise ValueError()
                except Exception:return self._json({'error':f'Invalid {field["field_type"]} value'},400)
                conn.execute('INSERT INTO entity_custom_values(entity_type,entity_id,field_id,value,tenant_id) VALUES(?,?,?,?,?) ON CONFLICT(entity_type,entity_id,field_id) DO UPDATE SET value=excluded.value',(data.get('entity_type'),data.get('entity_id'),field['id'],str(value),u['tenant_id']));audit(conn,u['id'],'UPSERT','custom_value',data.get('entity_id'),field['field_name'],self.client_address[0]);conn.commit();return self._json({'ok':True})
            if path=='/api/reports/definitions':
                if u['role'] not in INTERNAL_ROLES:return self._json({'error':'Permission denied'},403)
                now=utcnow();cur=conn.execute('INSERT INTO report_definitions(name,report_key,description,parameters_json,owner_user_id,is_shared,created_at,updated_at,tenant_id) VALUES(?,?,?,?,?,?,?,?,?)',(data.get('name'),data.get('report_key'),data.get('description'),json.dumps(data.get('parameters') or {}),u['id'],1 if data.get('is_shared') else 0,now,now,u['tenant_id']));audit(conn,u['id'],'CREATE','report_definition',cur.lastrowid,data.get('name',''),self.client_address[0]);conn.commit();return self._json({'id':cur.lastrowid},201)
            if path=='/api/reset':
                if APP_MODE not in {'demo','local','test'} or os.environ.get('ATS_ONE_RESET_AUTHORITY_CONFIRMED')!='LOCAL_TEST_ONLY':
                    return self._json({'error':'Endpoint not available'},404)
                if u['role']!='admin': return self._json({'error':'Permission denied'},403)
                conn.close(); init_db(reset=True); return self._json({'ok':True,'message':'Local/test database reset to seed data. Please login again.'})
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
            if data is None:return self._json({'error':getattr(self,'_body_error','Malformed JSON')},400)
            u=self._need(conn)
            if not u:return
            if parity_patch(self,conn,u,path,data): return
            if r14_patch(self,conn,u,path,data): return
            if r18_patch(self,conn,u,path,data): return
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
                if not self._tenant_row(conn,'candidates',cid,u):return self._json({'error':'Not found'},404)
                if 'zip' in fields and ('latitude' not in data or 'longitude' not in data):
                    coords=resolve_postal(data.get('zip'))
                    if coords:data['latitude'],data['longitude']=coords;fields += [x for x in ('latitude','longitude') if x not in fields]
                archived=utcnow() if norm(data.get('status'))=='archived' else (None if 'status' in data else None)
                extra=',archived_at=?' if 'status' in data else ''
                conn.execute('UPDATE candidates SET '+','.join(f'{k}=?' for k in fields)+',updated_at=?'+extra+' WHERE id=? AND tenant_id=?',tuple(data[k] for k in fields)+(utcnow(),)+((archived,) if 'status' in data else ())+(cid,u['tenant_id']));audit(conn,u['id'],'UPDATE','candidate',cid,','.join(fields),self.client_address[0]);conn.commit();return self._json({'ok':True})
            m=re.fullmatch(r'/api/jobs/(\d+)',path)
            if m:
                if u['role'] not in JOB_EDIT_ROLES: return self._json({'error':'Permission denied'},403)
                jid=int(m.group(1)); allowed={'title','company_id','contact_id','primary_recruiter_id','sales_user_id','status','priority','position_type','openings','filled','work_mode','city','state','country','zip','start_date','end_date','pay_min','pay_max','bill_min','bill_max','rate_type','profession','specialty','required_skills','required_qualifications','required_licenses','required_certifications','description','submission_guidelines_override','source','external_vms_id','latitude','longitude'}; fields=[k for k in data if k in allowed]
                if not fields:return self._json({'error':'No valid fields'},400)
                if not self._tenant_row(conn,'jobs',jid,u):return self._json({'error':'Not found'},404)
                if 'zip' in fields and ('latitude' not in data or 'longitude' not in data):
                    coords=resolve_postal(data.get('zip'))
                    if coords:data['latitude'],data['longitude']=coords;fields += [x for x in ('latitude','longitude') if x not in fields]
                archived=utcnow() if norm(data.get('status'))=='archived' else (None if 'status' in data else None);extra=',archived_at=?' if 'status' in data else ''
                conn.execute('UPDATE jobs SET '+','.join(f'{k}=?' for k in fields)+',updated_at=?'+extra+' WHERE id=? AND tenant_id=?',tuple(data[k] for k in fields)+(utcnow(),)+((archived,) if 'status' in data else ())+(jid,u['tenant_id']));audit(conn,u['id'],'UPDATE','job',jid,','.join(fields),self.client_address[0]);conn.commit();return self._json({'ok':True})
            m=re.fullmatch(r'/api/candidates/(\d+)/(skills|experience|licenses|certifications|qualifications|attributes)/(\d+)',path)
            if m:
                if u['role'] not in CANDIDATE_EDIT_ROLES:return self._json({'error':'Permission denied'},403)
                cid,section,item_id=int(m.group(1)),m.group(2),int(m.group(3));table={'skills':'candidate_skills','experience':'candidate_experience','licenses':'candidate_licenses','certifications':'candidate_certifications','qualifications':'candidate_qualifications','attributes':'candidate_attributes'}[section]
                row=qone(conn,f'SELECT * FROM {table} WHERE id=? AND candidate_id=? AND tenant_id=?',(item_id,cid,u['tenant_id']))
                if not row:return self._json({'error':'Not found'},404)
                allowed={'skills':{'skill','years','recent','last_used'},'experience':{'company','title','start_date','end_date','description','skills'},'licenses':{'license_type','country','state','license_number','status','expiry_date','documented'},'certifications':{'name','status','expiry_date','documented'},'qualifications':{'name','value','sub_value'},'attributes':{'attribute','value'}}[section];fields=[x for x in data if x in allowed]
                if not fields:return self._json({'error':'No valid fields'},400)
                conn.execute(f'UPDATE {table} SET '+','.join(f'{x}=?' for x in fields)+' WHERE id=? AND tenant_id=?',tuple(data[x] for x in fields)+(item_id,u['tenant_id']));audit(conn,u['id'],'UPDATE',table,item_id,','.join(fields),self.client_address[0]);conn.commit();return self._json({'ok':True})
            m=re.fullmatch(r'/api/candidate-documents/(\d+)',path)
            if m:
                if u['role'] not in CANDIDATE_EDIT_ROLES:return self._json({'error':'Permission denied'},403)
                did=int(m.group(1));doc=self._tenant_row(conn,'candidate_documents',did,u)
                if not doc:return self._json({'error':'Not found'},404)
                fields=[x for x in data if x in {'doc_type','name','status','expiry_date'}]
                if data.get('verify'):
                    data['status']='Verified';fields.append('status') if 'status' not in fields else None
                    conn.execute('UPDATE candidate_documents SET verified_by=?,verified_at=? WHERE id=? AND tenant_id=?',(u['id'],utcnow(),did,u['tenant_id']))
                if fields:conn.execute('UPDATE candidate_documents SET '+','.join(f'{x}=?' for x in fields)+' WHERE id=? AND tenant_id=?',tuple(data[x] for x in fields)+(did,u['tenant_id']))
                encoded=data.get('content_base64')
                if encoded is not None:
                    try:content=base64.b64decode(encoded,validate=True)
                    except Exception:return self._json({'error':'content_base64 is invalid'},400)
                    if len(content)>10*1024*1024:return self._json({'error':'Document exceeds 10 MB limit'},413)
                    version=int(doc.get('current_version') or 1)+1;name=data.get('file_name') or doc.get('file_name');mime=data.get('mime_type') or mimetypes.guess_type(name or '')[0] or 'application/octet-stream'
                    conn.execute('INSERT INTO candidate_document_versions(document_id,version,file_name,mime_type,size_bytes,sha256,content,uploaded_by,created_at,tenant_id) VALUES(?,?,?,?,?,?,?,?,?,?)',(did,version,name,mime,len(content),hashlib.sha256(content).hexdigest(),content,u['id'],utcnow(),u['tenant_id']));conn.execute('UPDATE candidate_documents SET current_version=?,file_name=?,mime_type=?,size_bytes=? WHERE id=? AND tenant_id=?',(version,name,mime,len(content),did,u['tenant_id']))
                audit(conn,u['id'],'UPDATE','candidate_document',did,','.join(fields),self.client_address[0]);conn.commit();return self._json({'ok':True})
            m=re.fullmatch(r'/api/hotlists/(\d+)/members/(\d+)',path)
            if m:
                if u['role'] not in RECRUITING_ROLES:return self._json({'error':'Permission denied'},403)
                hid,cid=int(m.group(1)),int(m.group(2));member=qone(conn,'SELECT * FROM hotlist_members WHERE hotlist_id=? AND candidate_id=? AND tenant_id=?',(hid,cid,u['tenant_id']))
                if not member:return self._json({'error':'Not found'},404)
                fields=[x for x in data if x in {'status','note'}]
                if not fields:return self._json({'error':'No valid fields'},400)
                conn.execute('UPDATE hotlist_members SET '+','.join(f'{x}=?' for x in fields)+' WHERE id=? AND tenant_id=?',tuple(data[x] for x in fields)+(member['id'],u['tenant_id']));audit(conn,u['id'],'UPDATE_MEMBER','hotlist',hid,f'candidate={cid}',self.client_address[0]);conn.commit();return self._json({'ok':True})
            m=re.fullmatch(r'/api/submissions/(\d+)',path)
            if m:
                if u['role'] not in RECRUITING_ROLES|{'client'}:return self._json({'error':'Permission denied'},403)
                sid=int(m.group(1));submission=self._tenant_row(conn,'submissions',sid,u)
                if not submission:return self._json({'error':'Not found'},404)
                if u['role']=='client':
                    job=self._tenant_row(conn,'jobs',submission['job_id'],u)
                    if not job or job['company_id']!=u.get('company_id'):return self._json({'error':'Permission denied'},403)
                fields=[x for x in data if x in {'client_rate','candidate_rate','availability','recruiter_summary','compliance_status','rtr_status','client_feedback'}]
                if not fields:return self._json({'error':'No valid fields'},400)
                conn.execute('UPDATE submissions SET '+','.join(f'{x}=?' for x in fields)+',updated_at=? WHERE id=? AND tenant_id=?',tuple(data[x] for x in fields)+(utcnow(),sid,u['tenant_id']));audit(conn,u['id'],'UPDATE','submission',sid,','.join(fields),self.client_address[0]);conn.commit();return self._json({'ok':True})
            m=re.fullmatch(r'/api/onboarding/(\d+)',path)
            if m:
                if u['role'] not in CANDIDATE_EDIT_ROLES:return self._json({'error':'Permission denied'},403)
                pid=int(m.group(1));package=self._tenant_row(conn,'onboarding_packages',pid,u)
                if not package:return self._json({'error':'Not found'},404)
                fields=[x for x in data if x in {'package_name','status','due_date'}]
                if not fields:return self._json({'error':'No valid fields'},400)
                conn.execute('UPDATE onboarding_packages SET '+','.join(f'{x}=?' for x in fields)+' WHERE id=? AND tenant_id=?',tuple(data[x] for x in fields)+(pid,u['tenant_id']));audit(conn,u['id'],'UPDATE','onboarding',pid,','.join(fields),self.client_address[0]);conn.commit();return self._json({'ok':True})
            m=re.fullmatch(r'/api/onboarding/requirements/(\d+)',path)
            if m:
                if u['role'] not in CANDIDATE_EDIT_ROLES:return self._json({'error':'Permission denied'},403)
                rid=int(m.group(1));req=self._tenant_row(conn,'onboarding_requirements',rid,u)
                if not req:return self._json({'error':'Not found'},404)
                fields=[x for x in data if x in {'requirement_type','name','mandatory','status','expiry_date','note','evidence_document_id'}]
                if not fields:return self._json({'error':'No valid fields'},400)
                conn.execute('UPDATE onboarding_requirements SET '+','.join(f'{x}=?' for x in fields)+' WHERE id=? AND tenant_id=?',tuple(data[x] for x in fields)+(rid,u['tenant_id']));audit(conn,u['id'],'UPDATE','onboarding_requirement',rid,','.join(fields),self.client_address[0]);conn.commit();return self._json({'ok':True})
            m=re.fullmatch(r'/api/(interviews|assessments|starts|assignments|timesheets|expenses|invoices)/(\d+)',path)
            if m:
                kind=m.group(1);row_id=int(m.group(2));table=kind;row=self._tenant_row(conn,table,row_id,u)
                if not row:return self._json({'error':'Not found'},404)
                if kind=='interviews': allowed={'scheduled_at','timezone','status','location_or_link','interviewer','feedback','rating','interview_type'};transition='interview';roles=RECRUITING_ROLES|{'client'}
                elif kind=='assessments': allowed={'status','score','max_score','notes'};transition='assessment';roles=CANDIDATE_EDIT_ROLES
                elif kind=='starts': allowed={'start_date','status','cancellation_reason'};transition='start';roles={'admin','teamlead','recruiter','hr'}
                elif kind=='assignments': allowed={'status','start_date','end_date','worksite','cost_center','vms_id','approver_contact_id','bill_rate','pay_rate','overtime_rule','payroll_profile','po_number','termination_reason'};transition='assignment';roles=WORKFORCE_ADMIN_ROLES
                elif kind=='timesheets': allowed={'status','rejection_note','daily_json'};transition='timesheet';roles={'admin','teamlead','finance','hr','approver'}
                elif kind=='expenses': allowed={'status','rejection_note','receipt_ref','description','amount'};transition='expense';roles={'admin','teamlead','finance','hr','approver'}
                else: allowed={'status','due_date','void_reason'};transition='invoice';roles={'admin','finance'}
                if u['role'] not in roles:return self._json({'error':'Permission denied'},403)
                if kind=='interviews' and u['role']=='client':
                    own=qone(conn,'SELECT i.id FROM interviews i JOIN submissions s ON s.id=i.submission_id JOIN jobs j ON j.id=s.job_id WHERE i.id=? AND i.tenant_id=? AND j.company_id=?',(row_id,u['tenant_id'],u.get('company_id')))
                    if not own:return self._json({'error':'Permission denied'},403)
                if kind in ('timesheets','expenses') and u['role']=='approver':
                    own=qone(conn,f'SELECT x.id FROM {table} x JOIN assignments a ON a.id=x.assignment_id WHERE x.id=? AND x.tenant_id=? AND a.company_id=?',(row_id,u['tenant_id'],u.get('company_id')))
                    if not own:return self._json({'error':'Permission denied'},403)
                fields=[x for x in data if x in allowed]
                if not fields:return self._json({'error':'No valid fields'},400)
                if kind=='assignments':
                    merged=dict(row);merged.update(data)
                    try:
                        assignment_graph(conn,merged,u['tenant_id'])
                        for money_field in ('bill_rate','pay_rate'):
                            if money_field in data:data[money_field]=float(exact_money(data[money_field],money_field))
                    except PolicyError as e:return self._json({'error':str(e),'code':e.code},e.status)
                if kind=='expenses' and 'amount' in data:
                    try:data['amount']=float(exact_money(data['amount'],'amount'))
                    except PolicyError as e:return self._json({'error':str(e),'code':e.code},e.status)
                if 'status' in fields:
                    try:ensure_transition(transition,row['status'],data['status'])
                    except ValueError as e:return self._json({'error':str(e)},409)
                    record_transition(conn,u,transition,row_id,row['status'],data['status'],data.get('note') or data.get('cancellation_reason') or data.get('rejection_note') or '')
                extras=[];values=[data[x] for x in fields]
                if kind=='starts':extras.append('updated_at=?');values.append(utcnow())
                if kind=='assignments':extras.append('updated_at=?');values.append(utcnow())
                if kind=='interviews' and norm(data.get('status'))=='completed':pass
                if kind=='assessments' and norm(data.get('status'))=='completed':extras.append('completed_at=?');values.append(utcnow())
                if kind=='invoices' and norm(data.get('status'))=='issued':extras.append('issued_at=?');values.append(utcnow())
                conn.execute(f'UPDATE {table} SET '+','.join([*(f'{x}=?' for x in fields),*extras])+' WHERE id=? AND tenant_id=?',tuple(values)+(row_id,u['tenant_id']));audit(conn,u['id'],'UPDATE',kind,row_id,','.join(fields),self.client_address[0]);conn.commit();return self._json({'ok':True})
            m=re.fullmatch(r'/api/users/(\d+)',path)
            if m:
                if u['role']!='admin':return self._json({'error':'Permission denied'},403)
                uid=int(m.group(1));target=self._tenant_row(conn,'users',uid,u)
                if not target:return self._json({'error':'Not found'},404)
                if data.get('active') in (0,False,'0') and target['role']=='admin':
                    active=qone(conn,"SELECT COUNT(*) n FROM users WHERE tenant_id=? AND role='admin' AND active=1",(u['tenant_id'],))['n']
                    if active<=1:return self._json({'error':'Cannot disable the final active admin'},409)
                if data.get('password'):return self._json({'error':'Direct password changes are disabled; use the reset-token flow'},400)
                fields=[x for x in data if x in {'email','name','role','company_id','candidate_id','supplier_id','active'}]
                values=[data[x] for x in fields]
                if not fields:return self._json({'error':'No valid fields'},400)
                conn.execute('UPDATE users SET '+','.join(f'{x}=?' for x in fields)+' WHERE id=? AND tenant_id=?',tuple(values)+(uid,u['tenant_id']))
                if data.get('active') in (0,False,'0') or 'role' in data:conn.execute('DELETE FROM sessions WHERE user_id=? AND tenant_id=?',(uid,u['tenant_id']))
                audit(conn,u['id'],'UPDATE','user',uid,','.join(fields),self.client_address[0]);conn.commit();return self._json({'ok':True})
            simple={
              'hotlists':('hotlists',{'name','description','owner_user_id','visibility','mode','saved_search_json','archived_at'},RECRUITING_ROLES),
              'companies':('companies',{'name','company_type','industry','status','owner_user_id','parent_company_id','website','phone','address','city','state','country','billing_terms','submission_guidelines','discount_rule','notes'},{'admin','teamlead','sales'}),
              'contacts':('contacts',{'company_id','first_name','last_name','title','email','phone','role_type','owner_user_id','status','notes'},{'admin','teamlead','sales','recruiter'}),
              'leads':('leads',{'company_id','contact_id','title','source','status','owner_user_id','next_action','next_action_at','notes'},{'admin','teamlead','sales'}),
              'opportunities':('opportunities',{'company_id','contact_id','name','stage','value','probability','owner_user_id','expected_close','next_activity','status','notes'},{'admin','teamlead','sales'}),
              'shifts':('shifts',{'shift_date','start_time','end_time','location','status'},WORKFORCE_ADMIN_ROLES),
              'attendance':('attendance',{'check_in','check_out','status','note'},WORKFORCE_ADMIN_ROLES),
              'purchase-orders':('purchase_orders',{'company_id','job_id','assignment_id','po_number','amount','start_date','end_date','status'},{'admin','finance','teamlead'}),
              'vms-accounts':('vms_accounts',{'name','platform','status','sync_mode','notes'},{'admin','teamlead'}),
              'vms-mappings':('vms_mappings',{'object_type','external_id','internal_id','external_status','internal_status','mapping_json'},{'admin','teamlead'}),
              'suppliers':('suppliers',{'name','status','contact_name','email','phone','tier','notes'},{'admin','teamlead','sales'}),
              'tasks':('tasks',{'entity_type','entity_id','title','due_at','owner_user_id','status','priority'},INTERNAL_ROLES),
              'automations':('automations',{'name','trigger_name','condition_json','action_json','active'},{'admin','teamlead'}),
              'integrations':('integration_connectors',{'category','name','mode','status','config_json','notes','credential_ref'},{'admin'}),
              'custom-fields':('custom_fields',{'entity_type','field_name','field_type','required','options_json','active'},{'admin'}),
              'report-definitions':('report_definitions',{'name','report_key','description','parameters_json','is_shared'},INTERNAL_ROLES),
              'job-distribution':('job_distribution',{'channel','external_post_id','status','last_sync','applications'},JOB_EDIT_ROLES),
            }
            m=re.fullmatch(r'/api/([a-z-]+)/(\d+)',path)
            if m and m.group(1) in simple:
                table,allowed,roles=simple[m.group(1)];row_id=int(m.group(2))
                if u['role'] not in roles:return self._json({'error':'Permission denied'},403)
                if not self._tenant_row(conn,table,row_id,u):return self._json({'error':'Not found'},404)
                values=dict(data)
                if table=='hotlists' and 'saved_search' in data:values['saved_search_json']=json.dumps(data['saved_search'])
                if table in ('automations','integration_connectors','custom_fields','report_definitions'):
                    for key in ('condition','action','config','options','parameters'):
                        if key in data:
                            try:values[key+'_json']=connector_config_json(data[key]) if key=='config' else json.dumps(data[key])
                            except ValueError as e:return self._json({'error':str(e)},400)
                fields=[x for x in values if x in allowed]
                if not fields:return self._json({'error':'No valid fields'},400)
                extras=[];vals=[values[x] for x in fields]
                if 'updated_at' in _columns(conn,table):extras.append('updated_at=?');vals.append(utcnow())
                conn.execute(f'UPDATE {table} SET '+','.join([*(f'{x}=?' for x in fields),*extras])+' WHERE id=? AND tenant_id=?',tuple(vals)+(row_id,u['tenant_id']));audit(conn,u['id'],'UPDATE',table,row_id,','.join(fields),self.client_address[0]);conn.commit();return self._json({'ok':True})
            return self._json({'error':'Not found'},404)
        finally: conn.close()
    def do_DELETE(self):
        p=urllib.parse.urlparse(self.path);path=p.path;qs=urllib.parse.parse_qs(p.query);conn=db()
        try:
            u=self._need(conn)
            if not u:return
            if parity_delete(self,conn,u,path,qs): return
            if r14_delete(self,conn,u,path,qs): return
            if r18_delete(self,conn,u,path,qs): return
            m=re.fullmatch(r'/api/(candidates|jobs|hotlists)/(\d+)',path)
            if m:
                kind,row_id=m.group(1),int(m.group(2));table=kind;roles=CANDIDATE_EDIT_ROLES if kind=='candidates' else (JOB_EDIT_ROLES if kind=='jobs' else RECRUITING_ROLES)
                if u['role'] not in roles:return self._json({'error':'Permission denied'},403)
                row=self._tenant_row(conn,table,row_id,u)
                if not row:return self._json({'error':'Not found'},404)
                if kind=='hotlists' and (qs.get('hard') or ['0'])[0]=='1' and u['role']=='admin':
                    conn.execute('DELETE FROM hotlist_members WHERE hotlist_id=? AND tenant_id=?',(row_id,u['tenant_id']));conn.execute('DELETE FROM hotlists WHERE id=? AND tenant_id=?',(row_id,u['tenant_id']));action='DELETE'
                else:
                    if kind=='hotlists':conn.execute('UPDATE hotlists SET archived_at=?,updated_at=? WHERE id=? AND tenant_id=?',(utcnow(),utcnow(),row_id,u['tenant_id']))
                    else:conn.execute(f"UPDATE {table} SET status='Archived',archived_at=?,updated_at=? WHERE id=? AND tenant_id=?",(utcnow(),utcnow(),row_id,u['tenant_id']))
                    action='ARCHIVE'
                audit(conn,u['id'],action,kind[:-1] if kind.endswith('s') else kind,row_id,'',self.client_address[0]);conn.commit();return self._json({'ok':True,'action':action.lower()})
            m=re.fullmatch(r'/api/candidates/(\d+)/(skills|experience|licenses|certifications|qualifications|attributes)/(\d+)',path)
            if m:
                if u['role'] not in CANDIDATE_EDIT_ROLES:return self._json({'error':'Permission denied'},403)
                cid,section,item_id=int(m.group(1)),m.group(2),int(m.group(3));table={'skills':'candidate_skills','experience':'candidate_experience','licenses':'candidate_licenses','certifications':'candidate_certifications','qualifications':'candidate_qualifications','attributes':'candidate_attributes'}[section]
                cur=conn.execute(f'DELETE FROM {table} WHERE id=? AND candidate_id=? AND tenant_id=?',(item_id,cid,u['tenant_id']))
                if not cur.rowcount:return self._json({'error':'Not found'},404)
                audit(conn,u['id'],'DELETE',table,item_id,f'candidate={cid}',self.client_address[0]);conn.commit();return self._json({'ok':True})
            m=re.fullmatch(r'/api/hotlists/(\d+)/members/(\d+)',path)
            if m:
                if u['role'] not in RECRUITING_ROLES:return self._json({'error':'Permission denied'},403)
                hid,cid=int(m.group(1)),int(m.group(2));cur=conn.execute('DELETE FROM hotlist_members WHERE hotlist_id=? AND candidate_id=? AND tenant_id=?',(hid,cid,u['tenant_id']))
                if not cur.rowcount:return self._json({'error':'Not found'},404)
                audit(conn,u['id'],'REMOVE_MEMBER','hotlist',hid,f'candidate={cid}',self.client_address[0]);conn.commit();return self._json({'ok':True})
            m=re.fullmatch(r'/api/jobs/(\d+)/users/(\d+)',path)
            if m:
                if u['role'] not in JOB_EDIT_ROLES:return self._json({'error':'Permission denied'},403)
                cur=conn.execute('DELETE FROM job_users WHERE job_id=? AND id=? AND tenant_id=?',(int(m.group(1)),int(m.group(2)),u['tenant_id']))
                if not cur.rowcount:return self._json({'error':'Not found'},404)
                audit(conn,u['id'],'UNASSIGN_USER','job',int(m.group(1)),'',self.client_address[0]);conn.commit();return self._json({'ok':True})
            m=re.fullmatch(r'/api/candidate-documents/(\d+)',path)
            if m:
                if u['role'] not in CANDIDATE_EDIT_ROLES:return self._json({'error':'Permission denied'},403)
                did=int(m.group(1))
                if not self._tenant_row(conn,'candidate_documents',did,u):return self._json({'error':'Not found'},404)
                conn.execute('DELETE FROM candidate_document_versions WHERE document_id=? AND tenant_id=?',(did,u['tenant_id']));conn.execute('DELETE FROM candidate_documents WHERE id=? AND tenant_id=?',(did,u['tenant_id']));audit(conn,u['id'],'DELETE','candidate_document',did,'',self.client_address[0]);conn.commit();return self._json({'ok':True})
            m=re.fullmatch(r'/api/custom-values/(\d+)',path)
            if m:
                cur=conn.execute('DELETE FROM entity_custom_values WHERE id=? AND tenant_id=?',(int(m.group(1)),u['tenant_id']))
                if not cur.rowcount:return self._json({'error':'Not found'},404)
                audit(conn,u['id'],'DELETE','custom_value',int(m.group(1)),'',self.client_address[0]);conn.commit();return self._json({'ok':True})
            archived={'companies':('companies',{'admin','teamlead','sales'}),'contacts':('contacts',{'admin','teamlead','sales','recruiter'}),'leads':('leads',{'admin','teamlead','sales'}),'opportunities':('opportunities',{'admin','teamlead','sales'}),'suppliers':('suppliers',{'admin','teamlead','sales'}),'tasks':('tasks',INTERNAL_ROLES),'onboarding':('onboarding_packages',CANDIDATE_EDIT_ROLES)}
            m=re.fullmatch(r'/api/([a-z]+)/(\d+)',path)
            if m and m.group(1) in archived:
                table,roles=archived[m.group(1)]
                if u['role'] not in roles:return self._json({'error':'Permission denied'},403)
                row=self._tenant_row(conn,table,int(m.group(2)),u)
                if not row:return self._json({'error':'Not found'},404)
                conn.execute(f"UPDATE {table} SET status='Archived' WHERE id=? AND tenant_id=?",(int(m.group(2)),u['tenant_id']));audit(conn,u['id'],'ARCHIVE',table,int(m.group(2)),'',self.client_address[0]);conn.commit();return self._json({'ok':True,'action':'archived'})
            simple={'shifts':('shifts',WORKFORCE_ADMIN_ROLES),'attendance':('attendance',WORKFORCE_ADMIN_ROLES),'onboarding-requirements':('onboarding_requirements',CANDIDATE_EDIT_ROLES),'job-distribution':('job_distribution',JOB_EDIT_ROLES),'vms-accounts':('vms_accounts',{'admin','teamlead'}),'vms-mappings':('vms_mappings',{'admin','teamlead'}),'automations':('automations',{'admin','teamlead'}),'integrations':('integration_connectors',{'admin'}),'custom-fields':('custom_fields',{'admin'}),'report-definitions':('report_definitions',INTERNAL_ROLES)}
            m=re.fullmatch(r'/api/([a-z-]+)/(\d+)',path)
            if m and m.group(1) in simple:
                table,roles=simple[m.group(1)]
                if u['role'] not in roles:return self._json({'error':'Permission denied'},403)
                cur=conn.execute(f'DELETE FROM {table} WHERE id=? AND tenant_id=?',(int(m.group(2)),u['tenant_id']))
                if not cur.rowcount:return self._json({'error':'Not found'},404)
                audit(conn,u['id'],'DELETE',table,int(m.group(2)),'',self.client_address[0]);conn.commit();return self._json({'ok':True})
            return self._json({'error':'Not found'},404)
        except sqlite3.IntegrityError as e:
            conn.rollback();return self._json({'error':'Delete blocked by related records','detail':str(e)},409)
        finally:conn.close()
    def dashboard(self,conn,u):
        role=u['role']; data={'role':role,'user':{'id':u['id'],'name':u['name']}}
        if role in ('candidate','worker'):
            cid=u['candidate_id']; data['candidate']=candidate_bundle(conn,cid,u['tenant_id']); data['jobs']=qall(conn,"SELECT id,job_no,title,city,state,work_mode,pay_min,pay_max,rate_type FROM jobs WHERE tenant_id=? AND status='Open' AND archived_at IS NULL ORDER BY created_at DESC LIMIT 12",(u['tenant_id'],)); return data
        if role=='client':
            co=u['company_id']; data['company']=qone(conn,'SELECT * FROM companies WHERE id=?',(co,)); data['open_jobs']=qone(conn,"SELECT COUNT(*) n FROM jobs WHERE company_id=? AND status='Open'",(co,))['n']; data['submissions']=qone(conn,'SELECT COUNT(*) n FROM submissions s JOIN jobs j ON j.id=s.job_id WHERE j.company_id=?',(co,))['n']; data['interviews']=qone(conn,"SELECT COUNT(*) n FROM interviews i JOIN submissions s ON s.id=i.submission_id JOIN jobs j ON j.id=s.job_id WHERE j.company_id=? AND i.status='scheduled'",(co,))['n']; return data
        if role=='supplier':
            data['released_jobs']=qone(conn,"SELECT COUNT(*) n FROM supplier_releases WHERE supplier_id=? AND tenant_id=? AND status='Open'",(u.get('supplier_id'),u['tenant_id']))['n']; return data
        if role=='approver':
            co=u.get('company_id');tid=u['tenant_id']
            data['pending_timesheets']=qone(conn,"SELECT COUNT(*) n FROM timesheets t JOIN assignments a ON a.id=t.assignment_id AND a.tenant_id=t.tenant_id WHERE t.tenant_id=? AND a.company_id=? AND t.status='submitted'",(tid,co))['n'];data['pending_expenses']=qone(conn,"SELECT COUNT(*) n FROM expenses e JOIN assignments a ON a.id=e.assignment_id AND a.tenant_id=e.tenant_id WHERE e.tenant_id=? AND a.company_id=? AND e.status='submitted'",(tid,co))['n'];return data
        tid=u['tenant_id']
        data.update({
          'open_jobs':qone(conn,"SELECT COUNT(*) n FROM jobs WHERE tenant_id=? AND status='Open'",(tid,))['n'],
          'primary_jobs':qone(conn,"SELECT COUNT(*) n FROM jobs WHERE tenant_id=? AND status='Open' AND primary_recruiter_id=?",(tid,u['id']))['n'],
          'jobs_no_activity':qone(conn,"SELECT COUNT(*) n FROM jobs j WHERE j.tenant_id=? AND status='Open' AND NOT EXISTS(SELECT 1 FROM submissions s WHERE s.job_id=j.id AND s.tenant_id=j.tenant_id)",(tid,))['n'],
          'active_assignments':qone(conn,"SELECT COUNT(*) n FROM assignments WHERE tenant_id=? AND status='active'",(tid,))['n'],
          'starts_30':qone(conn,"SELECT COUNT(*) n FROM starts WHERE tenant_id=? AND start_date>=date('now','-30 day')",(tid,))['n'],
          'pending_onboarding':qone(conn,"SELECT COUNT(*) n FROM onboarding_packages WHERE tenant_id=? AND status!='complete'",(tid,))['n'],
          'pending_timesheets':qone(conn,"SELECT COUNT(*) n FROM timesheets WHERE tenant_id=? AND status='submitted'",(tid,))['n'],
          'pending_expenses':qone(conn,"SELECT COUNT(*) n FROM expenses WHERE tenant_id=? AND status='submitted'",(tid,))['n'],
          'open_tasks':qone(conn,"SELECT COUNT(*) n FROM tasks WHERE tenant_id=? AND status='Open' AND owner_user_id=?",(tid,u['id']))['n'],
          'candidates':qone(conn,"SELECT COUNT(*) n FROM candidates WHERE tenant_id=? AND status='Active'",(tid,))['n'],
          'pipeline':qall(conn,"SELECT status,COUNT(*) count FROM submissions WHERE tenant_id=? GROUP BY status ORDER BY count DESC",(tid,)),
          'job_status':qall(conn,"SELECT status,COUNT(*) count FROM jobs WHERE tenant_id=? GROUP BY status ORDER BY count DESC",(tid,)),
          'company_pipeline':qall(conn,"SELECT stage,COUNT(*) count FROM opportunities WHERE tenant_id=? GROUP BY stage ORDER BY count DESC",(tid,)),
          'recent_jobs':qall(conn,"SELECT j.id,j.job_no,j.title,j.status,j.priority,co.name company_name,(SELECT COUNT(*) FROM submissions s WHERE s.job_id=j.id AND s.tenant_id=j.tenant_id) submissions FROM jobs j LEFT JOIN companies co ON co.id=j.company_id WHERE j.tenant_id=? ORDER BY j.created_at DESC LIMIT 8",(tid,)),
          'tasks':qall(conn,"SELECT * FROM tasks WHERE tenant_id=? AND owner_user_id=? AND status='Open' ORDER BY due_at LIMIT 8",(tid,u['id'])),
        }); return data
    def run_report(self,conn,u,key,params):
        tid=u['tenant_id']
        if key=='recruiting_pipeline':return qall(conn,'''SELECT j.job_no,j.title,j.status,co.name company,COUNT(DISTINCT s.id) submissions,COUNT(DISTINCT i.id) interviews FROM jobs j LEFT JOIN companies co ON co.id=j.company_id LEFT JOIN submissions s ON s.job_id=j.id AND s.tenant_id=j.tenant_id LEFT JOIN interviews i ON i.submission_id=s.id AND i.tenant_id=j.tenant_id WHERE j.tenant_id=? GROUP BY j.id ORDER BY j.created_at DESC''',(tid,))
        if key=='workforce_activity':return qall(conn,'''SELECT a.id,c.first_name||' '||c.last_name worker,j.title job,a.status,a.start_date,a.end_date,a.worksite,a.cost_center FROM assignments a JOIN candidates c ON c.id=a.candidate_id JOIN jobs j ON j.id=a.job_id WHERE a.tenant_id=? ORDER BY a.updated_at DESC''',(tid,))
        if key=='finance_aging':return qall(conn,'''SELECT i.invoice_no,co.name company,i.amount,i.tax,i.paid_amount,(i.amount+i.tax-i.paid_amount) balance,i.status,i.due_date,CAST(julianday('now')-julianday(i.due_date) AS INTEGER) days_past_due FROM invoices i LEFT JOIN companies co ON co.id=i.company_id WHERE i.tenant_id=? ORDER BY i.due_date''',(tid,))
        raise ValueError('Unknown report_key')
    def report_summary(self,conn,u):
        tid=u['tenant_id']
        return {
          'recruiting':{'active_candidates':qone(conn,"SELECT COUNT(*) n FROM candidates WHERE tenant_id=? AND status='Active'",(tid,))['n'],'open_jobs':qone(conn,"SELECT COUNT(*) n FROM jobs WHERE tenant_id=? AND status='Open'",(tid,))['n'],'submissions_30':qone(conn,"SELECT COUNT(*) n FROM submissions WHERE tenant_id=? AND created_at>=datetime('now','-30 day')",(tid,))['n'],'interviews_scheduled':qone(conn,"SELECT COUNT(*) n FROM interviews WHERE tenant_id=? AND status='scheduled'",(tid,))['n']},
          'workforce':{'active_assignments':qone(conn,"SELECT COUNT(*) n FROM assignments WHERE tenant_id=? AND status='active'",(tid,))['n'],'pending_timesheets':qone(conn,"SELECT COUNT(*) n FROM timesheets WHERE tenant_id=? AND status='submitted'",(tid,))['n'],'pending_expenses':qone(conn,"SELECT COUNT(*) n FROM expenses WHERE tenant_id=? AND status='submitted'",(tid,))['n']},
          'finance':{'issued_invoices':qone(conn,"SELECT COALESCE(SUM(amount+tax-paid_amount),0) n FROM invoices WHERE tenant_id=? AND status IN ('issued','part_paid')",(tid,))['n'],'paid_invoices':qone(conn,"SELECT COALESCE(SUM(paid_amount),0) n FROM invoices WHERE tenant_id=? AND status='paid'",(tid,))['n'],'open_po_value':qone(conn,"SELECT COALESCE(SUM(amount),0) n FROM purchase_orders WHERE tenant_id=? AND status='Open'",(tid,))['n']},
          'submission_by_status':qall(conn,'SELECT status,COUNT(*) count FROM submissions WHERE tenant_id=? GROUP BY status',(tid,)),
          'jobs_by_company':qall(conn,'SELECT co.name company,COUNT(j.id) count FROM companies co LEFT JOIN jobs j ON j.company_id=co.id AND j.tenant_id=co.tenant_id WHERE co.tenant_id=? GROUP BY co.id ORDER BY count DESC',(tid,))
        }

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--host',default='127.0.0.1'); ap.add_argument('--port',type=int,default=8765); ap.add_argument('--open',action='store_true'); ap.add_argument('--reset',action='store_true'); ap.add_argument('--quiet',action='store_true'); args=ap.parse_args()
    init_db(reset=args.reset)
    srv=ThreadingHTTPServer((args.host,args.port),Handler); srv.quiet=args.quiet
    url=f'http://127.0.0.1:{args.port}/'
    print('='*72); print(f' {APP_NAME} {APP_VERSION}'); print('='*72); print(f'LOCAL_URL={url}'); print(f'DATABASE={DB_PATH}'); print(f'PERSISTENCE={"SUPABASE_POSTGREST_CAS" if REMOTE_PERSISTENCE_ENABLED else "LOCAL_SQLITE"}'); print(f'HOST={args.host} PORT={args.port}'); print('CTRL+C to stop server'); print('='*72,flush=True)
    if args.open: threading.Timer(1.1,lambda:webbrowser.open(url)).start()
    try: srv.serve_forever()
    except KeyboardInterrupt: pass
    finally: srv.server_close()

if __name__=='__main__': main()
