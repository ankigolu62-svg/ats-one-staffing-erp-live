from __future__ import annotations

import argparse
import base64
import http.cookiejar
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import traceback
import urllib.error
import urllib.request


class SetupFailure(RuntimeError):
    pass


class API:
    def __init__(self, base):
        self.base = base.rstrip("/")
        jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(jar)
        )

    def req(self, path, method="GET", body=None):
        raw = (
            json.dumps(body).encode("utf-8")
            if body is not None else None
        )

        headers = {"Accept": "application/json"}

        if raw is not None:
            headers["Content-Type"] = "application/json"

        request = urllib.request.Request(
            self.base + path,
            data=raw,
            headers=headers,
            method=method
        )

        try:
            response = self.opener.open(request, timeout=12)
        except urllib.error.HTTPError as exc:
            response = exc

        with response:
            data = response.read()

            try:
                payload = json.loads(data.decode("utf-8"))
            except (UnicodeError, ValueError):
                payload = data.decode(
                    "utf-8-sig", errors="replace"
                )

            return int(response.status), payload

    def login(self, email, password):
        return self.req(
            "/api/login",
            "POST",
            {"email": email, "password": password}
        )


def free_port():
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    value = sock.getsockname()[1]
    sock.close()
    return value


def permissions_row(module, **overrides):
    row = {
        "module": module,
        "can_view": True,
        "can_create": True,
        "can_edit": True,
        "can_delete": True,
        "can_approve": True,
        "can_export": True,
        "can_admin": False,
        "can_financial": False,
        "can_documents": False,
        "data_scope": "all"
    }

    row.update(overrides)
    return row


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("repo")
    parser.add_argument("evidence")
    args = parser.parse_args()

    repo = Path(args.repo).resolve()
    evidence = Path(args.evidence).resolve()

    report = {
        "mode": "R23E_R6_SENSITIVE_PERMISSION_RUNTIME",
        "result": "NOT_RUN",
        "checks": [],
        "functional_failures": [],
        "first_actual_failure": None,
        "product_change": False,
        "main_change": False,
        "remote_push": False,
        "production_change": False
    }

    failures = []

    def check(name, ok, detail=None, functional=False):
        item = {
            "name": name,
            "pass": bool(ok),
            "category": (
                "FUNCTIONAL" if functional else "SETUP"
            )
        }

        if detail is not None:
            item["detail"] = detail

        report["checks"].append(item)

        print(
            "[{}] {}".format(
                "PASS" if ok else "FAIL", name
            )
            + (
                " :: {}".format(str(detail)[:500])
                if detail is not None else ""
            ),
            flush=True
        )

        if not ok:
            if functional:
                failures.append(name)
            else:
                raise SetupFailure(name)

    outcome = 20

    try:
        with tempfile.TemporaryDirectory(
            prefix="ats-r23e-r6-"
        ) as td:

            app = Path(td) / "app"

            shutil.copytree(
                repo,
                app,
                ignore=shutil.ignore_patterns(
                    ".git", "data", "evidence",
                    "__pycache__", ".pytest_cache",
                    "node_modules", ".venv", "venv"
                )
            )

            env = os.environ.copy()
            env.update(
                ATS_ONE_MODE="test",
                ATS_ONE_RESET_AUTHORITY_CONFIRMED="LOCAL_TEST_ONLY",
                SUPABASE_URL="",
                SUPABASE_SERVICE_ROLE_KEY="",
                RENDER_INSTANCE_ID=""
            )

            number = free_port()
            base = "http://127.0.0.1:{}".format(number)

            with (evidence / "server.log").open(
                "w", encoding="utf-8"
            ) as log:

                proc = subprocess.Popen(
                    [
                        sys.executable, "-u", "server.py",
                        "--host", "127.0.0.1",
                        "--port", str(number),
                        "--reset", "--quiet"
                    ],
                    cwd=app,
                    env=env,
                    stdout=log,
                    stderr=subprocess.STDOUT
                )

                try:
                    ready = False

                    for _ in range(240):
                        if proc.poll() is not None:
                            break

                        try:
                            status, _ = API(base).req("/api/health")
                            if status == 200:
                                ready = True
                                break
                        except (OSError, TimeoutError):
                            pass

                        time.sleep(0.15)

                    check("ISOLATED_SERVER_READY", ready)

                    admin = API(base)
                    finance = API(base)
                    recruiter = API(base)

                    for name, client, email, password in (
                        (
                            "ADMIN", admin,
                            "admin@atsone.local", "Admin@123"
                        ),
                        (
                            "FINANCE", finance,
                            "finance@atsone.local", "Finance@123"
                        ),
                        (
                            "RECRUITER", recruiter,
                            "recruiter@atsone.local", "Recruit@123"
                        )
                    ):
                        status, _ = client.login(email, password)

                        check(
                            "LOGIN_" + name,
                            status == 200,
                            status
                        )

                    # Positive controls: actual seeded invoice data.
                    status, invoice_rows = finance.req("/api/invoices")

                    check(
                        "FINANCIAL_POSITIVE_CONTROL",
                        status == 200
                        and isinstance(invoice_rows, list)
                        and bool(invoice_rows)
                        and "amount" in invoice_rows[0],
                        status
                    )

                    # Real isolated document fixture.
                    status, candidate = admin.req(
                        "/api/candidates",
                        "POST",
                        {
                            "first_name": "R23E",
                            "last_name": "DocumentProbe",
                            "email": "r23e-doc@example.test"
                        }
                    )

                    check(
                        "DOCUMENT_CANDIDATE_CREATED",
                        status == 201
                        and isinstance(candidate, dict)
                        and bool(candidate.get("id")),
                        status
                    )

                    candidate_id = int(candidate["id"])
                    marker = "R23E-SYNTHETIC-DOCUMENT-CONTENT"

                    status, document = admin.req(
                        "/api/candidates/{}/documents".format(
                            candidate_id
                        ),
                        "POST",
                        {
                            "name": "R23E Restricted Test Document",
                            "file_name": "r23e-probe.txt",
                            "doc_type": "Other",
                            "mime_type": "text/plain",
                            "content_base64": base64.b64encode(
                                marker.encode("utf-8")
                            ).decode("ascii")
                        }
                    )

                    check(
                        "DOCUMENT_FIXTURE_CREATED",
                        status == 201
                        and isinstance(document, dict)
                        and bool(document.get("id")),
                        status
                    )

                    doc_id = int(document["id"])

                    status, baseline_document = recruiter.req(
                        "/api/candidate-documents/{}/download".format(
                            doc_id
                        )
                    )

                    check(
                        "DOCUMENT_POSITIVE_CONTROL",
                        status == 200
                        and marker in str(baseline_document),
                        status
                    )

                    status, baseline_candidate = recruiter.req(
                        "/api/candidates/{}".format(candidate_id)
                    )

                    check(
                        "DOCUMENT_METADATA_POSITIVE_CONTROL",
                        status == 200
                        and isinstance(baseline_candidate, dict)
                        and any(
                            int(d.get("id") or 0) == doc_id
                            for d in baseline_candidate.get(
                                "documents", []
                            )
                        ),
                        status
                    )

                    # Report reading and CSV export must work before
                    # we remove export privileges.
                    report_url = (
                        "/api/reports/run"
                        "?report_key=recruiting_pipeline"
                    )

                    export_url = (
                        "/api/reports/export"
                        "?report_key=recruiting_pipeline"
                    )

                    status, report_data = recruiter.req(report_url)

                    check(
                        "REPORT_VIEW_POSITIVE_CONTROL",
                        status == 200
                        and isinstance(report_data, dict)
                        and isinstance(report_data.get("rows"), list),
                        status
                    )

                    status, csv_data = recruiter.req(export_url)

                    check(
                        "REPORT_EXPORT_POSITIVE_CONTROL",
                        status == 200
                        and "job_no" in str(csv_data),
                        status
                    )

                    # R23 permission management and context setup.
                    status, users = admin.req(
                        "/api/r23/users-context"
                    )

                    check(
                        "USERS_CONTEXT",
                        status == 200
                        and isinstance(users, list),
                        status
                    )

                    ids = {
                        row["role"]: int(row["id"])
                        for row in users
                        if isinstance(row, dict)
                        and row.get("role")
                    }

                    check(
                        "FINANCE_AND_RECRUITER_PRESENT",
                        "finance" in ids and "recruiter" in ids
                    )

                    status, teams = admin.req("/api/r23/teams")

                    check(
                        "TEAMS_READ",
                        status == 200
                        and isinstance(teams, list)
                        and bool(teams),
                        status
                    )

                    default_team = next(
                        (
                            t for t in teams
                            if t.get("code") == "default"
                        ),
                        teams[0]
                    )

                    team_id = int(default_team["id"])

                    profiles = {}

                    for name, slug, role in (
                        (
                            "Finance", "r23e_finance_restricted",
                            "finance"
                        ),
                        (
                            "Recruiter", "r23e_recruiter_restricted",
                            "recruiter"
                        )
                    ):
                        status, created = admin.req(
                            "/api/r23/role-profiles",
                            "POST",
                            {
                                "name": "R23E " + name + " Restricted",
                                "slug": slug,
                                "base_role": role,
                                "data_scope": "all"
                            }
                        )

                        check(
                            "RESTRICTED_" + name.upper() + "_PROFILE",
                            status == 201
                            and isinstance(created, dict)
                            and bool(created.get("id")),
                            status
                        )

                        profiles[role] = int(created["id"])

                    updates = {
                        "finance": [
                            permissions_row(
                                "invoice",
                                can_financial=False
                            )
                        ],
                        "recruiter": [
                            permissions_row(
                                "candidate",
                                can_documents=False
                            ),
                            permissions_row(
                                "document",
                                can_documents=False
                            ),
                            permissions_row(
                                "report",
                                can_export=False
                            )
                        ]
                    }

                    for role in ("finance", "recruiter"):
                        profile_id = profiles[role]

                        status, _ = admin.req(
                            "/api/r23/role-profiles/{}/permissions".format(
                                profile_id
                            ),
                            "POST",
                            {"permissions": updates[role]}
                        )

                        check(
                            "RESTRICTED_PERMISSION_SAVE_" + role.upper(),
                            status == 200,
                            status
                        )

                        status, _ = admin.req(
                            "/api/r23/teams/{}/members".format(
                                team_id
                            ),
                            "POST",
                            {
                                "user_id": ids[role],
                                "profile_id": profile_id,
                                "is_primary": False
                            }
                        )

                        check(
                            "RESTRICTED_ASSIGN_" + role.upper(),
                            status == 200,
                            status
                        )

                    for role, client in (
                        ("finance", finance),
                        ("recruiter", recruiter)
                    ):
                        status, selection = client.req(
                            "/api/r23/session-context",
                            "POST",
                            {
                                "team_id": team_id,
                                "profile_id": profiles[role]
                            }
                        )

                        check(
                            "PROFILE_SWITCH_" + role.upper(),
                            status == 200
                            and isinstance(selection, dict)
                            and int(
                                (
                                    selection.get("selected")
                                    or {}
                                ).get("profile_id") or 0
                            ) == profiles[role],
                            status
                        )

                    contexts = {}

                    for role, client in (
                        ("finance", finance),
                        ("recruiter", recruiter)
                    ):
                        status, ctx = client.req("/api/r23/context")

                        check(
                            "CONTEXT_READ_" + role.upper(),
                            status == 200
                            and isinstance(ctx, dict),
                            status
                        )

                        contexts[role] = {
                            p["module"]: p
                            for p in ctx.get("permissions", [])
                        }

                    financial_flag = contexts["finance"].get(
                        "invoice", {}
                    )

                    doc_flag = contexts["recruiter"].get(
                        "document", {}
                    )

                    candidate_flag = contexts["recruiter"].get(
                        "candidate", {}
                    )

                    export_flag = contexts["recruiter"].get(
                        "report", {}
                    )

                    check(
                        "FINANCIAL_FLAG_CONFIRMED",
                        financial_flag.get("can_view") == 1
                        and financial_flag.get("can_financial") == 0,
                        financial_flag
                    )

                    check(
                        "DOCUMENT_FLAG_CONFIRMED",
                        doc_flag.get("can_view") == 1
                        and doc_flag.get("can_documents") == 0
                        and candidate_flag.get("can_view") == 1
                        and candidate_flag.get("can_documents") == 0,
                        {
                            "document": doc_flag,
                            "candidate": candidate_flag
                        }
                    )

                    check(
                        "EXPORT_FLAG_CONFIRMED",
                        export_flag.get("can_view") == 1
                        and export_flag.get("can_export") == 0,
                        export_flag
                    )

                    # -------------------------------------------------
                    # REAL FUNCTIONAL SECURITY PROBES
                    # -------------------------------------------------

                    print(
                        "\n===== RESTRICTED FINANCIAL ACCESS =====",
                        flush=True
                    )

                    status, restricted_invoices = finance.req(
                        "/api/invoices"
                    )

                    amount_fields = {
                        "amount", "tax", "discount", "paid_amount",
                        "balance", "total", "pay_rate",
                        "bill_rate", "rate"
                    }

                    has_amount_data = (
                        isinstance(restricted_invoices, list)
                        and any(
                            isinstance(row, dict)
                            and bool(amount_fields.intersection(
                                row.keys()
                            ))
                            for row in restricted_invoices
                        )
                    )

                    check(
                        "FINANCIAL_AMOUNT_ACCESS_RESTRICTED",
                        status in (403, 404)
                        or (
                            status == 200
                            and isinstance(restricted_invoices, list)
                            and not has_amount_data
                        ),
                        {
                            "status": status,
                            "contains_amount_fields": has_amount_data
                        },
                        functional=True
                    )

                    print(
                        "\n===== RESTRICTED DOCUMENT ACCESS =====",
                        flush=True
                    )

                    status, restricted_download = recruiter.req(
                        "/api/candidate-documents/{}/download".format(
                            doc_id
                        )
                    )

                    check(
                        "DOCUMENT_BINARY_ACCESS_RESTRICTED",
                        status in (403, 404),
                        {"status": status},
                        functional=True
                    )

                    status, restricted_candidate = recruiter.req(
                        "/api/candidates/{}".format(candidate_id)
                    )

                    documents_exposed = (
                        isinstance(restricted_candidate, dict)
                        and any(
                            int(d.get("id") or 0) == doc_id
                            for d in restricted_candidate.get(
                                "documents", []
                            )
                            if isinstance(d, dict)
                        )
                    )

                    check(
                        "DOCUMENT_METADATA_RESTRICTED",
                        status in (403, 404)
                        or (
                            status == 200
                            and isinstance(restricted_candidate, dict)
                            and not documents_exposed
                        ),
                        {
                            "status": status,
                            "document_metadata_exposed": documents_exposed
                        },
                        functional=True
                    )

                    print(
                        "\n===== RESTRICTED EXPORT ACCESS =====",
                        flush=True
                    )

                    status, view_data = recruiter.req(report_url)

                    check(
                        "REPORT_VIEW_STILL_ALLOWED",
                        status == 200
                        and isinstance(view_data, dict),
                        {"status": status},
                        functional=True
                    )

                    status, restricted_export = recruiter.req(
                        export_url
                    )

                    check(
                        "REPORT_CSV_EXPORT_RESTRICTED",
                        status in (403, 404),
                        {"status": status},
                        functional=True
                    )

                finally:
                    if proc.poll() is None:
                        proc.terminate()

                    try:
                        proc.wait(timeout=12)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        proc.wait(timeout=12)

                    if proc.poll() is None:
                        raise RuntimeError(
                            "ISOLATED_TEST_SERVER_NOT_REAPED"
                        )

                    print(
                        "ISOLATED_SERVER_REAPED=PASS",
                        flush=True
                    )

        report["functional_failures"] = failures
        report["first_actual_failure"] = (
            failures[0] if failures else None
        )

        report["result"] = (
            "FUNCTIONAL_GAP_PROVEN"
            if failures else "PASS"
        )

        outcome = 10 if failures else 0

    except SetupFailure as exc:
        report["result"] = "SETUP_FAILURE"
        report["first_setup_failure"] = str(exc)
        outcome = 20

    except Exception as exc:
        report["result"] = "HARNESS_ERROR"
        report["exception"] = repr(exc)
        traceback.print_exc()
        outcome = 20

    finally:
        (
            evidence / "R23E-R6-RESULT.json"
        ).write_text(
            json.dumps(
                report, indent=2, ensure_ascii=False
            ) + "\n",
            encoding="utf-8"
        )

        passed = sum(
            1 for row in report["checks"] if row["pass"]
        )

        failed = sum(
            1 for row in report["checks"] if not row["pass"]
        )

        print("\n" + "=" * 70, flush=True)
        print(" ATS-ONE R23E-R6 RESULT", flush=True)
        print("=" * 70, flush=True)
        print("R23E_R6_RESULT=" + report["result"], flush=True)
        print("CHECKS_PASS=" + str(passed), flush=True)
        print("CHECKS_FAIL=" + str(failed), flush=True)
        print(
            "FIRST_ACTUAL_FAILURE="
            + str(report["first_actual_failure"] or ""),
            flush=True
        )
        print(
            "FUNCTIONAL_FAILURES="
            + ";".join(failures),
            flush=True
        )
        print("PRODUCT_CHANGE=NO", flush=True)
        print("PRODUCTION_CHANGE=NO", flush=True)
        print("FULL_REGRESSION_RUN=NO", flush=True)
        print("EVIDENCE_ROOT=" + str(evidence), flush=True)
        print("=" * 70, flush=True)

    return outcome


if __name__ == "__main__":
    raise SystemExit(main())