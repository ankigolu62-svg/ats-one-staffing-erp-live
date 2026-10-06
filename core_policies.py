"""Authoritative validation policies shared by ATS-One legacy handlers.

The functions in this module intentionally have no dependency on the HTTP
server.  They can therefore be exercised against disposable SQLite databases
without starting a web process.
"""
from __future__ import annotations

import json
import math
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation


class PolicyError(ValueError):
    """A deterministic client-visible policy violation."""

    def __init__(self, message: str, status: int = 400, code: str = "POLICY_VIOLATION"):
        super().__init__(message)
        self.status = status
        self.code = code


def row_dict(row):
    return dict(row) if row is not None else None


def exact_money(value, field: str, *, allow_zero: bool = True, maximum: str = "999999999.99") -> Decimal:
    """Parse finite, non-negative money with at most two fractional digits."""
    if isinstance(value, bool) or value is None:
        raise PolicyError(f"{field} is required", 400, "INVALID_MONEY")
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise PolicyError(f"{field} must be a valid monetary amount", 400, "INVALID_MONEY")
    if not amount.is_finite() or amount < 0 or (not allow_zero and amount == 0):
        raise PolicyError(f"{field} must be finite and non-negative", 400, "INVALID_MONEY")
    if amount > Decimal(maximum) or amount.as_tuple().exponent < -2:
        raise PolicyError(f"{field} is outside the supported monetary range", 400, "INVALID_MONEY")
    return amount.quantize(Decimal("0.01"))


def bounded_hours(value, field: str = "hours") -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise PolicyError(f"{field} must be numeric", 400, "INVALID_HOURS")
    if not math.isfinite(number) or number < 0 or number > 24:
        raise PolicyError(f"{field} must be between 0 and 24", 400, "INVALID_HOURS")
    return number


def safe_identifier(value, field: str, pattern: str = r"[A-Za-z0-9][A-Za-z0-9._/-]{0,79}") -> str:
    text = str(value or "").strip()
    if not re.fullmatch(pattern, text):
        raise PolicyError(f"{field} contains unsupported characters", 400, "INVALID_IDENTIFIER")
    return text


def tenant_parent(conn, table: str, parent_id, tenant_id: int, *, active: bool = True):
    if table not in {
        "users", "companies", "contacts", "candidates", "jobs", "submissions",
        "interviews", "starts", "assignments", "timesheets", "expenses", "invoices",
        "suppliers", "onboarding_packages", "candidate_documents",
    }:
        raise PolicyError("Unsupported relationship target", 400, "INVALID_RELATIONSHIP")
    try:
        numeric_id = int(parent_id)
    except (TypeError, ValueError):
        raise PolicyError(f"{table} parent id is invalid", 400, "INVALID_RELATIONSHIP")
    row = row_dict(conn.execute(f"SELECT * FROM {table} WHERE id=? AND tenant_id=?", (numeric_id, tenant_id)).fetchone())
    if not row:
        raise PolicyError(f"{table} parent not found", 404, "PARENT_NOT_FOUND")
    if active:
        status = str(row.get("status") or "").strip().lower()
        if row.get("archived_at") or status in {"archived", "deleted", "closed", "cancelled", "terminated", "void"}:
            raise PolicyError(f"{table} parent is not active", 409, "PARENT_INACTIVE")
    return row


ENTITY_REGISTRY = {
    "candidate": "candidates", "job": "jobs", "company": "companies",
    "contact": "contacts", "submission": "submissions", "assignment": "assignments",
    "timesheet": "timesheets", "expense": "expenses", "invoice": "invoices",
}


def entity_reference(conn, entity_type, entity_id, tenant_id: int, *, active: bool = True):
    kind = str(entity_type or "").strip().lower()
    table = ENTITY_REGISTRY.get(kind)
    if not table:
        raise PolicyError("Unsupported entity_type", 400, "INVALID_ENTITY_TYPE")
    return kind, tenant_parent(conn, table, entity_id, tenant_id, active=active)


def assignment_graph(conn, data: dict, tenant_id: int):
    candidate = tenant_parent(conn, "candidates", data.get("candidate_id"), tenant_id)
    job = tenant_parent(conn, "jobs", data.get("job_id"), tenant_id)
    company_id = data.get("company_id") or job.get("company_id")
    company = tenant_parent(conn, "companies", company_id, tenant_id)
    if int(job.get("company_id") or 0) != int(company["id"]):
        raise PolicyError("Assignment company does not match job company", 409, "RELATIONSHIP_MISMATCH")
    start = None
    if data.get("start_id"):
        start = tenant_parent(conn, "starts", data["start_id"], tenant_id)
        submission = row_dict(conn.execute(
            "SELECT s.* FROM submissions s WHERE s.id=? AND s.tenant_id=?",
            (start.get("submission_id"), tenant_id),
        ).fetchone())
        if not submission:
            raise PolicyError("Assignment start has no tenant-owned submission", 409, "RELATIONSHIP_MISMATCH")
        for field, expected in (("candidate_id", candidate["id"]), ("job_id", job["id"])):
            if int(submission.get(field) or 0) != int(expected):
                raise PolicyError(f"Assignment {field} does not match start submission", 409, "RELATIONSHIP_MISMATCH")
    approver = None
    if data.get("approver_contact_id"):
        approver = tenant_parent(conn, "contacts", data["approver_contact_id"], tenant_id)
        if int(approver.get("company_id") or 0) != int(company["id"]):
            raise PolicyError("Approver contact does not belong to assignment company", 409, "RELATIONSHIP_MISMATCH")
    return candidate, job, company, start, approver


def time_period_locked(conn, tenant_id: int, assignment: dict, period_start: str, user_id=None) -> bool:
    try:
        day = datetime.fromisoformat(str(period_start)[:10]).date().isoformat()
    except (TypeError, ValueError):
        raise PolicyError("week_start must be an ISO date", 400, "INVALID_DATE")
    scopes = [("tenant", tenant_id), ("assignment", assignment.get("id")), ("company", assignment.get("company_id"))]
    if user_id is not None:
        scopes.append(("user", user_id))
    for scope_type, scope_id in scopes:
        if scope_id is None:
            continue
        found = conn.execute(
            """SELECT 1 FROM time_period_locks_r14
               WHERE tenant_id=? AND locked=1 AND lower(scope_type)=? AND scope_id=?
                 AND date(?) BETWEEN date(period_start) AND date(period_end) LIMIT 1""",
            (tenant_id, scope_type, scope_id, day),
        ).fetchone()
        if found:
            return True
    return bool(conn.execute(
        """SELECT 1 FROM time_period_locks_r14
           WHERE tenant_id=? AND locked=1 AND lower(scope_type) IN ('all','tenant')
             AND (scope_id IS NULL OR scope_id=?)
             AND date(?) BETWEEN date(period_start) AND date(period_end) LIMIT 1""",
        (tenant_id, tenant_id, day),
    ).fetchone())


def permission_denied_by_override(conn, tenant_id: int, role: str, module: str, action: str) -> bool:
    column = {"GET": "can_view", "POST": "can_create", "PATCH": "can_edit", "DELETE": "can_delete"}.get(action.upper())
    if not column:
        return False
    row = conn.execute(
        f"SELECT {column} decision FROM permission_overrides WHERE tenant_id=? AND lower(role)=? AND lower(module_name)=?",
        (tenant_id, role.lower(), module.lower()),
    ).fetchone()
    return row is not None and int(row[0]) == 0


def canonical_json(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
