"""Forward-only R15 database migrations and integrity guardrails."""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timezone


MIGRATION_VERSION = 1501
MIGRATION_NAME = "r15-correctness-foundations"


GUARDRAIL_SQL = r"""
CREATE TABLE IF NOT EXISTS schema_migrations(
  version INTEGER PRIMARY KEY, name TEXT NOT NULL, checksum TEXT NOT NULL, applied_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS user_tenant_memberships(
  id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, tenant_id INTEGER NOT NULL,
  role TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL,
  UNIQUE(user_id, tenant_id)
);
CREATE TABLE IF NOT EXISTS user_invitations(
  id INTEGER PRIMARY KEY AUTOINCREMENT, tenant_id INTEGER NOT NULL, user_id INTEGER NOT NULL,
  email TEXT NOT NULL, token_hash TEXT NOT NULL UNIQUE, expires_at TEXT NOT NULL,
  used_at TEXT, created_by INTEGER, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS security_events(
  id INTEGER PRIMARY KEY AUTOINCREMENT, tenant_id INTEGER, user_id INTEGER,
  event_type TEXT NOT NULL, subject_hash TEXT, ip_hash TEXT, detail TEXT,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS login_attempts(
  subject_hash TEXT NOT NULL, ip_hash TEXT NOT NULL, failures INTEGER NOT NULL DEFAULT 0,
  window_started_at TEXT NOT NULL, blocked_until TEXT, updated_at TEXT NOT NULL,
  PRIMARY KEY(subject_hash, ip_hash)
);
CREATE INDEX IF NOT EXISTS idx_security_events_time ON security_events(created_at);
CREATE INDEX IF NOT EXISTS idx_invitations_user ON user_invitations(tenant_id,user_id,used_at);

CREATE TRIGGER IF NOT EXISTS r15_jobs_parent_insert
BEFORE INSERT ON jobs BEGIN
  SELECT CASE WHEN NEW.company_id IS NOT NULL AND NOT EXISTS(
    SELECT 1 FROM companies p WHERE p.id=NEW.company_id AND p.tenant_id=NEW.tenant_id
      AND lower(COALESCE(p.status,'active')) NOT IN ('archived','deleted','inactive')
  ) THEN RAISE(ABORT,'R15_PARENT: jobs.company_id') END;
  SELECT CASE WHEN NEW.contact_id IS NOT NULL AND NOT EXISTS(
    SELECT 1 FROM contacts p WHERE p.id=NEW.contact_id AND p.tenant_id=NEW.tenant_id
      AND p.company_id=NEW.company_id AND lower(COALESCE(p.status,'active')) NOT IN ('archived','deleted','inactive')
  ) THEN RAISE(ABORT,'R15_PARENT: jobs.contact_id') END;
END;
CREATE TRIGGER IF NOT EXISTS r15_jobs_parent_update
BEFORE UPDATE OF company_id,contact_id,tenant_id ON jobs BEGIN
  SELECT CASE WHEN NEW.company_id IS NOT NULL AND NOT EXISTS(
    SELECT 1 FROM companies p WHERE p.id=NEW.company_id AND p.tenant_id=NEW.tenant_id
  ) THEN RAISE(ABORT,'R15_PARENT: jobs.company_id') END;
  SELECT CASE WHEN NEW.contact_id IS NOT NULL AND NOT EXISTS(
    SELECT 1 FROM contacts p WHERE p.id=NEW.contact_id AND p.tenant_id=NEW.tenant_id AND p.company_id=NEW.company_id
  ) THEN RAISE(ABORT,'R15_PARENT: jobs.contact_id') END;
END;

CREATE TRIGGER IF NOT EXISTS r15_submissions_parent_insert
BEFORE INSERT ON submissions BEGIN
  SELECT CASE WHEN NOT EXISTS(SELECT 1 FROM jobs p WHERE p.id=NEW.job_id AND p.tenant_id=NEW.tenant_id
    AND p.archived_at IS NULL AND lower(COALESCE(p.status,'open')) NOT IN ('archived','deleted','closed','cancelled'))
    THEN RAISE(ABORT,'R15_PARENT: submissions.job_id') END;
  SELECT CASE WHEN NOT EXISTS(SELECT 1 FROM candidates p WHERE p.id=NEW.candidate_id AND p.tenant_id=NEW.tenant_id
    AND p.archived_at IS NULL AND lower(COALESCE(p.status,'active')) NOT IN ('archived','deleted'))
    THEN RAISE(ABORT,'R15_PARENT: submissions.candidate_id') END;
  SELECT CASE WHEN lower(COALESCE(NEW.status,'submitted')) NOT IN ('rejected','withdrawn') AND EXISTS(
    SELECT 1 FROM submissions s WHERE s.tenant_id=NEW.tenant_id AND s.job_id=NEW.job_id
      AND s.candidate_id=NEW.candidate_id AND lower(s.status) NOT IN ('rejected','withdrawn'))
    THEN RAISE(ABORT,'R15_DUPLICATE: active submission') END;
END;
CREATE TRIGGER IF NOT EXISTS r15_submissions_unique_update
BEFORE UPDATE OF job_id,candidate_id,status,tenant_id ON submissions BEGIN
  SELECT CASE WHEN lower(COALESCE(NEW.status,'submitted')) NOT IN ('rejected','withdrawn') AND EXISTS(
    SELECT 1 FROM submissions s WHERE s.id<>OLD.id AND s.tenant_id=NEW.tenant_id
      AND s.job_id=NEW.job_id AND s.candidate_id=NEW.candidate_id
      AND lower(s.status) NOT IN ('rejected','withdrawn'))
    THEN RAISE(ABORT,'R15_DUPLICATE: active submission') END;
END;

CREATE TRIGGER IF NOT EXISTS r15_interviews_parent_insert
BEFORE INSERT ON interviews BEGIN
  SELECT CASE WHEN NOT EXISTS(SELECT 1 FROM submissions p WHERE p.id=NEW.submission_id AND p.tenant_id=NEW.tenant_id)
    THEN RAISE(ABORT,'R15_PARENT: interviews.submission_id') END;
END;

CREATE TRIGGER IF NOT EXISTS r15_assignments_graph_insert
BEFORE INSERT ON assignments BEGIN
  SELECT CASE WHEN NOT EXISTS(SELECT 1 FROM candidates p WHERE p.id=NEW.candidate_id AND p.tenant_id=NEW.tenant_id
    AND p.archived_at IS NULL AND lower(COALESCE(p.status,'active')) NOT IN ('archived','deleted'))
    THEN RAISE(ABORT,'R15_PARENT: assignments.candidate_id') END;
  SELECT CASE WHEN NOT EXISTS(SELECT 1 FROM jobs j WHERE j.id=NEW.job_id AND j.tenant_id=NEW.tenant_id
    AND j.company_id=NEW.company_id AND j.archived_at IS NULL AND lower(COALESCE(j.status,'open')) NOT IN ('archived','deleted','closed','cancelled'))
    THEN RAISE(ABORT,'R15_GRAPH: assignments.job/company') END;
  SELECT CASE WHEN NEW.start_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM starts s JOIN submissions sub ON sub.id=s.submission_id AND sub.tenant_id=s.tenant_id WHERE s.id=NEW.start_id
    AND s.tenant_id=NEW.tenant_id AND sub.candidate_id=NEW.candidate_id AND sub.job_id=NEW.job_id)
    THEN RAISE(ABORT,'R15_GRAPH: assignments.start') END;
  SELECT CASE WHEN NEW.approver_contact_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM contacts c
    WHERE c.id=NEW.approver_contact_id AND c.tenant_id=NEW.tenant_id AND c.company_id=NEW.company_id)
    THEN RAISE(ABORT,'R15_GRAPH: assignments.approver') END;
END;

CREATE TRIGGER IF NOT EXISTS r15_timesheets_parent_insert
BEFORE INSERT ON timesheets BEGIN
  SELECT CASE WHEN NOT EXISTS(SELECT 1 FROM assignments a WHERE a.id=NEW.assignment_id
    AND a.tenant_id=NEW.tenant_id AND a.candidate_id=NEW.candidate_id
    AND lower(COALESCE(a.status,'pending')) NOT IN ('archived','deleted','completed','terminated','cancelled'))
    THEN RAISE(ABORT,'R15_GRAPH: timesheets.assignment') END;
END;
CREATE TRIGGER IF NOT EXISTS r15_expenses_parent_insert
BEFORE INSERT ON expenses BEGIN
  SELECT CASE WHEN NOT EXISTS(SELECT 1 FROM assignments a WHERE a.id=NEW.assignment_id
    AND a.tenant_id=NEW.tenant_id AND a.candidate_id=NEW.candidate_id)
    THEN RAISE(ABORT,'R15_GRAPH: expenses.assignment') END;
END;

CREATE TRIGGER IF NOT EXISTS r15_expenses_money_insert BEFORE INSERT ON expenses BEGIN
  SELECT CASE WHEN NEW.amount IS NULL OR NEW.amount<0 OR NEW.amount>999999999.99
    THEN RAISE(ABORT,'R15_MONEY: expenses.amount') END;
END;
CREATE TRIGGER IF NOT EXISTS r15_expenses_money_update BEFORE UPDATE OF amount ON expenses BEGIN
  SELECT CASE WHEN NEW.amount IS NULL OR NEW.amount<0 OR NEW.amount>999999999.99
    THEN RAISE(ABORT,'R15_MONEY: expenses.amount') END;
END;
CREATE TRIGGER IF NOT EXISTS r15_invoices_money_insert BEFORE INSERT ON invoices BEGIN
  SELECT CASE WHEN NEW.amount IS NULL OR NEW.amount<0 OR NEW.tax IS NULL OR NEW.tax<0
    OR COALESCE(NEW.paid_amount,0)<0 OR COALESCE(NEW.paid_amount,0)>NEW.amount+NEW.tax
    THEN RAISE(ABORT,'R15_MONEY: invoices') END;
END;
CREATE TRIGGER IF NOT EXISTS r15_invoices_money_update BEFORE UPDATE OF amount,tax,paid_amount ON invoices BEGIN
  SELECT CASE WHEN NEW.amount IS NULL OR NEW.amount<0 OR NEW.tax IS NULL OR NEW.tax<0
    OR COALESCE(NEW.paid_amount,0)<0 OR COALESCE(NEW.paid_amount,0)>NEW.amount+NEW.tax
    THEN RAISE(ABORT,'R15_MONEY: invoices') END;
END;
CREATE TRIGGER IF NOT EXISTS r15_payments_money_insert BEFORE INSERT ON invoice_payments BEGIN
  SELECT CASE WHEN NEW.amount IS NULL OR NEW.amount<=0 THEN RAISE(ABORT,'R15_MONEY: payment') END;
END;
"""


def _now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _columns(conn, table):
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}


def apply_r15_migrations(conn):
    """Apply ordered, idempotent R15 changes without deleting existing rows."""
    conn.execute("CREATE TABLE IF NOT EXISTS schema_migrations(version INTEGER PRIMARY KEY,name TEXT NOT NULL,checksum TEXT NOT NULL,applied_at TEXT NOT NULL)")
    checksum = hashlib.sha256(GUARDRAIL_SQL.encode()).hexdigest()
    recorded = conn.execute("SELECT checksum FROM schema_migrations WHERE version=?", (MIGRATION_VERSION,)).fetchone()
    if recorded and recorded[0] != checksum:
        raise RuntimeError("R15 migration checksum mismatch")
    if not recorded:
        conn.executescript(GUARDRAIL_SQL)
        conn.execute(
            "INSERT INTO schema_migrations(version,name,checksum,applied_at) VALUES(?,?,?,?)",
            (MIGRATION_VERSION, MIGRATION_NAME, checksum, _now()),
        )
    if "session_id" not in _columns(conn, "sessions"):
        conn.execute("ALTER TABLE sessions ADD COLUMN session_id TEXT")
    for token, in conn.execute("SELECT token FROM sessions WHERE session_id IS NULL OR session_id='' ").fetchall():
        conn.execute("UPDATE sessions SET session_id=? WHERE token=?", (secrets.token_urlsafe(18), token))
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_sessions_session_id ON sessions(session_id)")
    conn.execute(
        """INSERT INTO user_tenant_memberships(user_id,tenant_id,role,active,created_at)
           SELECT id,tenant_id,role,active,? FROM users
           WHERE 1=1
           ON CONFLICT(user_id,tenant_id) DO UPDATE SET role=excluded.role,active=excluded.active""",
        (_now(),),
    )
    return MIGRATION_VERSION


def scan_integrity(conn):
    """Return counts for critical legacy graph violations without mutating data."""
    checks = {
        "submission_job": "SELECT COUNT(*) FROM submissions c LEFT JOIN jobs p ON p.id=c.job_id AND p.tenant_id=c.tenant_id WHERE p.id IS NULL",
        "submission_candidate": "SELECT COUNT(*) FROM submissions c LEFT JOIN candidates p ON p.id=c.candidate_id AND p.tenant_id=c.tenant_id WHERE p.id IS NULL",
        "interview_submission": "SELECT COUNT(*) FROM interviews c LEFT JOIN submissions p ON p.id=c.submission_id AND p.tenant_id=c.tenant_id WHERE p.id IS NULL",
        "assignment_candidate": "SELECT COUNT(*) FROM assignments c LEFT JOIN candidates p ON p.id=c.candidate_id AND p.tenant_id=c.tenant_id WHERE p.id IS NULL",
        "assignment_job": "SELECT COUNT(*) FROM assignments c LEFT JOIN jobs p ON p.id=c.job_id AND p.tenant_id=c.tenant_id WHERE p.id IS NULL",
        "timesheet_assignment": "SELECT COUNT(*) FROM timesheets c LEFT JOIN assignments p ON p.id=c.assignment_id AND p.tenant_id=c.tenant_id WHERE p.id IS NULL",
        "expense_assignment": "SELECT COUNT(*) FROM expenses c LEFT JOIN assignments p ON p.id=c.assignment_id AND p.tenant_id=c.tenant_id WHERE p.id IS NULL",
    }
    return {name: conn.execute(sql).fetchone()[0] for name, sql in checks.items()}
