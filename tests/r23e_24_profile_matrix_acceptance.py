from __future__ import annotations

import argparse
import csv
import http.cookiejar
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import traceback
import urllib.error
import urllib.request

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait


USERS = {
    "admin": ("admin@atsone.local", "Admin@123"),
    "teamlead": ("teamlead@atsone.local", "Lead@123"),
    "recruiter": ("recruiter@atsone.local", "Recruit@123"),
    "sales": ("sales@atsone.local", "Sales@123"),
    "hr": ("hr@atsone.local", "HR@123"),
    "finance": ("finance@atsone.local", "Finance@123"),
    "client": ("client@atsone.local", "Client@123"),
    "candidate": ("candidate@atsone.local", "Candidate@123"),
    "worker": ("worker@atsone.local", "Worker@123"),
    "supplier": ("supplier@atsone.local", "Supplier@123"),
    "approver": ("approver@atsone.local", "Approve@123"),
}

INTERNAL_ROLES = {
    "admin",
    "teamlead",
    "recruiter",
    "sales",
    "hr",
    "finance",
}

PORTAL_ROUTES = {
    "client": "clientPortal",
    "candidate": "candidatePortal",
    "worker": "workerPortal",
    "supplier": "supplierPortal",
    "approver": "approverPortal",
}

ROUTE_MODULE = {
    "dashboard": "dashboard",
    "talent": "talent",
    "boolean": "talent",
    "candidates": "candidate",
    "hotlists": "hotlist",
    "jobs": "job",
    "companies": "crm",
    "contacts": "crm",
    "submissions": "submission",
    "interviews": "interview",
    "assessments": "assessment",
    "onboarding": "onboarding",
    "assignments": "assignment",
    "timesheets": "timesheet",
    "expenses": "expense",
    "finance": "finance",
    "vms": "vms",
    "suppliers": "supplier",
    "communications": "communication",
    "reports": "report",
    "admin": "admin",
    "audit": "audit",
}

DIRECT_ROUTES = list(ROUTE_MODULE)

ERROR_MARKERS = (
    "Unable to load page.",
    "Permission denied",
    "Server error",
    "Unknown page",
)


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
            if body is not None
            else None
        )

        headers = {"Accept": "application/json"}

        if raw is not None:
            headers["Content-Type"] = "application/json"

        request = urllib.request.Request(
            self.base + path,
            data=raw,
            headers=headers,
            method=method,
        )

        try:
            response = self.opener.open(
                request,
                timeout=15,
            )
        except urllib.error.HTTPError as exc:
            response = exc
        except Exception as exc:
            return 0, {
                "transport_error": repr(exc)
            }

        with response:
            data = response.read()

            try:
                payload = json.loads(
                    data.decode("utf-8")
                )
            except Exception:
                payload = data.decode(
                    "utf-8-sig",
                    errors="replace",
                )

            return int(response.status), payload

    def login(self, email, password):
        return self.req(
            "/api/login",
            "POST",
            {
                "email": email,
                "password": password,
            },
        )


def free_port():
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    value = sock.getsockname()[1]
    sock.close()
    return value


def load_r23(app):
    source = app / "r23_rbac.py"

    spec = importlib.util.spec_from_file_location(
        "r23_r10_authority",
        source,
    )

    if not spec or not spec.loader:
        raise SetupFailure(
            "R23_RBAC_IMPORT_FAILED"
        )

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    return module


def flag(row, name):
    try:
        return int(
            (row or {}).get(name)
            or 0
        ) == 1
    except Exception:
        return False


def allowed_module(perms, module):
    row = perms.get(module)

    if not flag(row, "can_view"):
        return False

    if module == "document":
        return flag(
            row,
            "can_documents",
        )

    if module in {
        "finance",
        "invoice",
    }:
        return flag(
            row,
            "can_financial",
        )

    if module == "admin":
        return flag(
            row,
            "can_admin",
        )

    return True


def browser_login(
    driver,
    email,
    password,
):
    driver.delete_all_cookies()

    driver.get(
        driver.current_url.split(
            "/",
            3,
        )[0]
        + "//"
        + driver.current_url.split(
            "/",
            3,
        )[2]
        + "/"
    )

    return driver.execute_async_script(
        """
        const email=arguments[0];
        const password=arguments[1];
        const done=arguments[arguments.length-1];

        fetch('/api/login',{
          method:'POST',
          headers:{
            'Content-Type':'application/json'
          },
          body:JSON.stringify({
            email,
            password
          })
        })
        .then(async r=>{
          done([
            Number(r.status),
            await r.text()
          ]);
        })
        .catch(e=>{
          done([0,String(e)]);
        });
        """,
        email,
        password,
    )


def browser_switch(
    driver,
    team_id,
    profile_id,
):
    return driver.execute_async_script(
        """
        const team_id=arguments[0];
        const profile_id=arguments[1];
        const done=arguments[arguments.length-1];

        fetch('/api/r23/session-context',{
          method:'POST',
          headers:{
            'Content-Type':'application/json'
          },
          body:JSON.stringify({
            team_id,
            profile_id
          })
        })
        .then(async r=>{
          done([
            Number(r.status),
            await r.text()
          ]);
        })
        .catch(e=>{
          done([0,String(e)]);
        });
        """,
        team_id,
        profile_id,
    )


def browser_boot(driver):
    return driver.execute_async_script(
        """
        const done=arguments[arguments.length-1];

        try{
          Promise.resolve(boot())
            .then(()=>done([1,'ok']))
            .catch(e=>done([0,String(e)]));
        }catch(e){
          done([0,String(e)]);
        }
        """
    )


def browser_route_wait(driver, route_name):
    result = driver.execute_async_script(
        """
        const target=arguments[0];
        const done=arguments[arguments.length-1];

        try{
          Promise.resolve(route(target))
            .then(()=>{
              requestAnimationFrame(()=>{
                const c=document.querySelector('#content');
                done([
                  1,
                  c ? (c.innerText||'') : ''
                ]);
              });
            })
            .catch(e=>done([0,String(e)]));
        }catch(e){
          done([0,String(e)]);
        }
        """,
        route_name,
    )

    if (
        not result
        or int(result[0] or 0) != 1
    ):
        raise RuntimeError(
            "BROWSER_ROUTE_AWAIT_FAILED "
            + str(route_name)
            + " :: "
            + str(result)
        )

    return result


def wait_content(driver, timeout=6):
    try:
        WebDriverWait(
            driver,
            timeout,
        ).until(
            lambda d:
                d.execute_script(
                    """
                    const c=document.querySelector(
                      '#content'
                    );

                    if(!c)return false;

                    const t=(
                      c.innerText||''
                    ).trim();

                    return (
                      t.length>0 &&
                      !t.startsWith('Loading')
                    );
                    """
                )
        )

        return True
    except Exception:
        return False


def content_text(driver):
    try:
        return driver.execute_script(
            """
            const c=document.querySelector(
              '#content'
            );

            return c
              ? (c.innerText||'')
              : '';
            """
        ) or ""
    except Exception:
        return ""


def clear_logs(driver):
    for kind in ("browser", "performance"):
        try:
            driver.get_log(kind)
        except Exception:
            pass


def js_errors(driver):
    result = []

    try:
        logs = driver.get_log("browser")
    except Exception:
        return result

    for row in logs:
        if str(
            row.get("level")
            or ""
        ).upper() != "SEVERE":
            continue

        result.append(
            str(
                row.get("message")
                or ""
            )
        )

    return result


def http_5xx(driver, base):
    result = []

    try:
        logs = driver.get_log(
            "performance"
        )
    except Exception:
        return result

    for row in logs:
        try:
            message = json.loads(
                row["message"]
            )["message"]

            if (
                message.get("method")
                != "Network.responseReceived"
            ):
                continue

            response = message[
                "params"
            ]["response"]

            status = int(
                response.get("status")
                or 0
            )

            url = str(
                response.get("url")
                or ""
            )

            if (
                url.startswith(base)
                and status >= 500
            ):
                result.append(
                    {
                        "status": status,
                        "url": url,
                    }
                )
        except Exception:
            continue

    return result


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument("repo")
    parser.add_argument("evidence")
    parser.add_argument("chrome")

    args = parser.parse_args()

    repo = Path(args.repo).resolve()
    evidence = Path(args.evidence).resolve()
    chrome = Path(args.chrome).resolve()

    evidence.mkdir(
        parents=True,
        exist_ok=True,
    )

    screenshots = (
        evidence
        / "screenshots"
    )

    screenshots.mkdir(
        parents=True,
        exist_ok=True,
    )

    report = {
        "mode":
            "R23E_R10R1_24_PROFILE_BROWSER_API_MATRIX",

        "result":
            "NOT_RUN",

        "profile_count":
            0,

        "internal_profile_count":
            0,

        "portal_profile_count":
            0,

        "api_checks":
            0,

        "nav_checks":
            0,

        "browser_route_checks":
            0,

        "functional_failures":
            [],

        "first_actual_failure":
            None,

        "product_change":
            False,

        "main_change":
            False,

        "production_change":
            False,
    }

    failures = []

    profile_matrix = []
    api_matrix = []
    browser_matrix = []

    def failure(
        kind,
        persona,
        detail,
    ):
        item = {
            "kind": kind,
            "persona": persona,
            "detail": detail,
        }

        failures.append(item)

        print(
            "[FAIL] "
            + kind
            + " :: "
            + persona
            + " :: "
            + str(detail)[:800],
            flush=True,
        )

    def passed(
        kind,
        persona,
        detail="",
    ):
        print(
            "[PASS] "
            + kind
            + " :: "
            + persona
            + (
                " :: "
                + str(detail)[:400]
                if detail != ""
                else ""
            ),
            flush=True,
        )

    def shot(
        driver,
        slug,
        marker,
    ):
        safe = re.sub(
            r"[^A-Za-z0-9._-]+",
            "_",
            slug,
        )

        target = (
            screenshots
            / (
                safe
                + "-"
                + marker
                + ".png"
            )
        )

        try:
            driver.save_screenshot(
                str(target)
            )
        except Exception:
            pass

    def write_csv(path, rows):
        if not rows:
            path.write_text(
                "",
                encoding="utf-8",
            )
            return

        with path.open(
            "w",
            newline="",
            encoding="utf-8-sig",
        ) as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=list(
                    rows[0].keys()
                ),
            )

            writer.writeheader()
            writer.writerows(rows)

    outcome = 20

    try:
        with tempfile.TemporaryDirectory(
            prefix="ats-r23e-r10r1-"
        ) as td:

            app = Path(td) / "app"

            shutil.copytree(
                repo,
                app,
                ignore=shutil.ignore_patterns(
                    ".git",
                    "data",
                    "evidence",
                    "__pycache__",
                    ".pytest_cache",
                    "node_modules",
                    ".venv",
                    "venv",
                ),
            )

            authority = load_r23(app)

            personas = list(
                authority.PERSONAS
            )

            modules = list(
                authority.MODULES
            )

            report[
                "profile_count"
            ] = len(personas)

            report[
                "internal_profile_count"
            ] = sum(
                1
                for _, _, role in personas
                if role in INTERNAL_ROLES
            )

            report[
                "portal_profile_count"
            ] = sum(
                1
                for _, _, role in personas
                if role not in INTERNAL_ROLES
            )

            if len(personas) != 24:
                failure(
                    "ENTERPRISE_PERSONA_COUNT",
                    "SYSTEM",
                    {
                        "expected": 24,
                        "actual": len(personas),
                    },
                )

            port = free_port()
            base = (
                "http://127.0.0.1:"
                + str(port)
            )

            env = os.environ.copy()

            env.update(
                ATS_ONE_MODE="test",
                ATS_ONE_RESET_AUTHORITY_CONFIRMED=
                    "LOCAL_TEST_ONLY",
                SUPABASE_URL="",
                SUPABASE_SERVICE_ROLE_KEY="",
                RENDER_INSTANCE_ID="",
            )

            server_handle = (
                evidence
                / "server.log"
            ).open(
                "w",
                encoding="utf-8",
            )

            process = subprocess.Popen(
                [
                    sys.executable,
                    "-u",
                    "server.py",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(port),
                    "--reset",
                    "--quiet",
                ],
                cwd=app,
                env=env,
                stdout=server_handle,
                stderr=subprocess.STDOUT,
            )

            driver = None

            try:
                ready = False

                for _ in range(240):
                    if process.poll() is not None:
                        break

                    status, _ = API(
                        base
                    ).req(
                        "/api/health"
                    )

                    if status == 200:
                        ready = True
                        break

                    time.sleep(.15)

                if not ready:
                    raise SetupFailure(
                        "ISOLATED_SERVER_NOT_READY"
                    )

                print(
                    "[PASS] ISOLATED_SERVER_READY",
                    flush=True,
                )

                admin = API(base)

                status, _ = admin.login(
                    "admin@atsone.local",
                    "Admin@123",
                )

                if status != 200:
                    raise SetupFailure(
                        "ADMIN_LOGIN_FAILED"
                    )

                status, catalog = admin.req(
                    "/api/r23/role-profiles"
                )

                if (
                    status != 200
                    or not isinstance(
                        catalog,
                        list,
                    )
                ):
                    raise SetupFailure(
                        "PROFILE_CATALOG_FAILED"
                    )

                profile_by_slug = {
                    row["slug"]: row
                    for row in catalog
                    if isinstance(row, dict)
                    and row.get("slug")
                }

                status, users = admin.req(
                    "/api/r23/users-context"
                )

                if (
                    status != 200
                    or not isinstance(
                        users,
                        list,
                    )
                ):
                    raise SetupFailure(
                        "USERS_CONTEXT_FAILED"
                    )

                user_by_role = {
                    row["role"]: row
                    for row in users
                    if isinstance(row, dict)
                    and row.get("role")
                }

                status, teams = admin.req(
                    "/api/r23/teams"
                )

                if (
                    status != 200
                    or not isinstance(
                        teams,
                        list,
                    )
                    or not teams
                ):
                    raise SetupFailure(
                        "TEAMS_FAILED"
                    )

                default_team = next(
                    (
                        row
                        for row in teams
                        if row.get("code")
                        == "default"
                    ),
                    teams[0],
                )

                team_id = int(
                    default_team["id"]
                )

                # ------------------------------------------
                # PROFILE PERMISSION AUTHORITY
                # ------------------------------------------

                permission_by_slug = {}

                for (
                    persona,
                    slug,
                    base_role,
                ) in personas:

                    profile = profile_by_slug.get(
                        slug
                    )

                    if not profile:
                        failure(
                            "BUILTIN_PROFILE_MISSING",
                            persona,
                            slug,
                        )
                        continue

                    user = user_by_role.get(
                        base_role
                    )

                    if not user:
                        failure(
                            "BASE_USER_MISSING",
                            persona,
                            base_role,
                        )
                        continue

                    status, payload = admin.req(
                        (
                            "/api/r23/role-profiles/"
                            + str(
                                profile["id"]
                            )
                            + "/permissions"
                        )
                    )

                    if (
                        status != 200
                        or not isinstance(
                            payload,
                            dict,
                        )
                    ):
                        failure(
                            "PROFILE_PERMISSION_READ",
                            persona,
                            status,
                        )
                        continue

                    permissions = {
                        row["module"]: row
                        for row in (
                            payload.get(
                                "permissions"
                            )
                            or []
                        )
                        if isinstance(row, dict)
                        and row.get("module")
                    }

                    permission_by_slug[
                        slug
                    ] = permissions

                    for module in modules:
                        row = (
                            permissions.get(
                                module
                            )
                            or {}
                        )

                        profile_matrix.append(
                            {
                                "persona":
                                    persona,

                                "slug":
                                    slug,

                                "base_role":
                                    base_role,

                                "module":
                                    module,

                                "can_view":
                                    int(
                                        row.get(
                                            "can_view"
                                        )
                                        or 0
                                    ),

                                "can_create":
                                    int(
                                        row.get(
                                            "can_create"
                                        )
                                        or 0
                                    ),

                                "can_edit":
                                    int(
                                        row.get(
                                            "can_edit"
                                        )
                                        or 0
                                    ),

                                "can_delete":
                                    int(
                                        row.get(
                                            "can_delete"
                                        )
                                        or 0
                                    ),

                                "can_approve":
                                    int(
                                        row.get(
                                            "can_approve"
                                        )
                                        or 0
                                    ),

                                "can_export":
                                    int(
                                        row.get(
                                            "can_export"
                                        )
                                        or 0
                                    ),

                                "can_admin":
                                    int(
                                        row.get(
                                            "can_admin"
                                        )
                                        or 0
                                    ),

                                "can_financial":
                                    int(
                                        row.get(
                                            "can_financial"
                                        )
                                        or 0
                                    ),

                                "can_documents":
                                    int(
                                        row.get(
                                            "can_documents"
                                        )
                                        or 0
                                    ),

                                "data_scope":
                                    row.get(
                                        "data_scope"
                                    )
                                    or "",
                            }
                        )

                    status, assign = admin.req(
                        (
                            "/api/r23/teams/"
                            + str(team_id)
                            + "/members"
                        ),
                        "POST",
                        {
                            "user_id":
                                int(
                                    user["id"]
                                ),

                            "profile_id":
                                int(
                                    profile["id"]
                                ),

                            "is_primary":
                                False,
                        },
                    )

                    if status != 200:
                        failure(
                            "PROFILE_ASSIGNMENT",
                            persona,
                            {
                                "status": status,
                                "payload": assign,
                            },
                        )
                    else:
                        passed(
                            "PROFILE_ASSIGNMENT",
                            persona,
                        )

                # ------------------------------------------
                # REPRESENTATIVE DOCUMENT FIXTURE
                # ------------------------------------------

                import base64

                recruiter = user_by_role[
                    "recruiter"
                ]

                status, candidate = admin.req(
                    "/api/candidates",
                    "POST",
                    {
                        "first_name": "R23E",
                        "last_name":
                            "ProfileMatrix",
                        "email":
                            "r23e-profile-matrix@example.test",
                        "owner_user_id":
                            int(
                                recruiter["id"]
                            ),
                    },
                )

                if (
                    status != 201
                    or not candidate.get("id")
                ):
                    raise SetupFailure(
                        "DOCUMENT_CANDIDATE_FIXTURE_FAILED"
                    )

                candidate_id = int(
                    candidate["id"]
                )

                status, document = admin.req(
                    (
                        "/api/candidates/"
                        + str(candidate_id)
                        + "/documents"
                    ),
                    "POST",
                    {
                        "name":
                            "R23E Profile Matrix",

                        "file_name":
                            "r23e-profile-matrix.txt",

                        "mime_type":
                            "text/plain",

                        "content_base64":
                            base64.b64encode(
                                b"R23E PROFILE MATRIX"
                            ).decode("ascii"),
                    },
                )

                if (
                    status != 201
                    or not document.get("id")
                ):
                    raise SetupFailure(
                        "DOCUMENT_FIXTURE_FAILED"
                    )

                document_id = int(
                    document["id"]
                )

                # ------------------------------------------
                # API PROBES
                # ------------------------------------------

                probes = {
                    "dashboard":
                        ("GET", "/api/dashboard", None),

                    "talent":
                        ("POST", "/api/search/talent", {}),

                    "candidate":
                        ("GET", "/api/candidates", None),

                    "job":
                        ("GET", "/api/jobs", None),

                    "crm":
                        ("GET", "/api/companies", None),

                    "submission":
                        ("GET", "/api/submissions", None),

                    "interview":
                        ("GET", "/api/interviews", None),

                    "onboarding":
                        ("GET", "/api/onboarding", None),

                    "assignment":
                        ("GET", "/api/assignments", None),

                    "timesheet":
                        ("GET", "/api/timesheets", None),

                    "expense":
                        ("GET", "/api/expenses", None),

                    "finance":
                        ("GET", "/api/purchase-orders", None),

                    "invoice":
                        ("GET", "/api/invoices", None),

                    "report":
                        ("GET", "/api/reports/summary", None),

                    "communication":
                        ("GET", "/api/communications", None),

                    "hotlist":
                        ("GET", "/api/hotlists", None),

                    "assessment":
                        ("GET", "/api/assessments", None),

                    "document":
                        (
                            "GET",
                            (
                                "/api/candidate-documents/"
                                + str(document_id)
                                + "/download"
                            ),
                            None,
                        ),

                    "vms":
                        ("GET", "/api/vms", None),

                    "supplier":
                        ("GET", "/api/suppliers", None),

                    "audit":
                        ("GET", "/api/audit", None),

                    "admin":
                        ("GET", "/api/r23/role-profiles", None),
                }

                print("")
                print(
                    "===== 24 PROFILE API MATRIX =====",
                    flush=True,
                )

                for (
                    persona,
                    slug,
                    base_role,
                ) in personas:

                    profile = profile_by_slug.get(
                        slug
                    )

                    user = user_by_role.get(
                        base_role
                    )

                    if not profile or not user:
                        continue

                    email, password = USERS[
                        base_role
                    ]

                    api = API(base)

                    status, payload = api.login(
                        email,
                        password,
                    )

                    if status != 200:
                        failure(
                            "API_LOGIN",
                            persona,
                            status,
                        )
                        continue

                    status, selection = api.req(
                        "/api/r23/session-context",
                        "POST",
                        {
                            "team_id":
                                team_id,

                            "profile_id":
                                int(
                                    profile["id"]
                                ),
                        },
                    )

                    if status != 200:
                        failure(
                            "API_CONTEXT_SWITCH",
                            persona,
                            {
                                "status": status,
                                "payload": selection,
                            },
                        )
                        continue

                    status, context = api.req(
                        "/api/r23/context"
                    )

                    selected = (
                        context.get(
                            "selected"
                        )
                        if isinstance(
                            context,
                            dict,
                        )
                        else None
                    )

                    if not (
                        status == 200
                        and isinstance(
                            selected,
                            dict,
                        )
                        and selected.get(
                            "profile_slug"
                        ) == slug
                    ):
                        failure(
                            "API_SELECTED_CONTEXT",
                            persona,
                            {
                                "status": status,
                                "selected": selected,
                            },
                        )
                    else:
                        passed(
                            "API_SELECTED_CONTEXT",
                            persona,
                        )

                    # Portal profiles use portal/base-role
                    # authorization rather than internal
                    # operational module pages.
                    if (
                        base_role
                        not in INTERNAL_ROLES
                    ):
                        continue

                    perms = permission_by_slug.get(
                        slug,
                        {},
                    )

                    for module, probe in probes.items():

                        method, path, body = probe

                        expected = allowed_module(
                            perms,
                            module,
                        )

                        status, payload = api.req(
                            path,
                            method,
                            body,
                        )

                        report[
                            "api_checks"
                        ] += 1

                        actual_allowed = (
                            200 <= status < 300
                        )

                        ok = (
                            actual_allowed
                            if expected
                            else status in (
                                403,
                                404,
                            )
                        )

                        api_matrix.append(
                            {
                                "persona":
                                    persona,

                                "slug":
                                    slug,

                                "base_role":
                                    base_role,

                                "module":
                                    module,

                                "method":
                                    method,

                                "path":
                                    path,

                                "expected_allowed":
                                    int(expected),

                                "status":
                                    status,

                                "pass":
                                    int(ok),
                            }
                        )

                        if not ok:
                            failure(
                                "API_PERMISSION_MISMATCH",
                                persona,
                                {
                                    "module":
                                        module,

                                    "expected_allowed":
                                        expected,

                                    "status":
                                        status,

                                    "path":
                                        path,

                                    "payload":
                                        payload,
                                },
                            )

                # ------------------------------------------
                # BROWSER
                # ------------------------------------------

                options = Options()

                options.binary_location = str(
                    chrome
                )

                options.add_argument(
                    "--headless=new"
                )

                options.add_argument(
                    "--disable-gpu"
                )

                options.add_argument(
                    "--no-sandbox"
                )

                options.add_argument(
                    "--disable-dev-shm-usage"
                )

                options.add_argument(
                    "--disable-extensions"
                )

                options.add_argument(
                    "--disable-background-networking"
                )

                options.add_argument(
                    "--window-size=1600,1200"
                )

                options.set_capability(
                    "goog:loggingPrefs",
                    {
                        "browser": "ALL",
                        "performance": "ALL",
                    },
                )

                driver = webdriver.Chrome(
                    options=options
                )

                driver.set_script_timeout(
                    20
                )

                driver.get(base + "/")

                print("")
                print(
                    "===== 24 PROFILE BROWSER MATRIX =====",
                    flush=True,
                )

                for (
                    persona,
                    slug,
                    base_role,
                ) in personas:

                    print(
                        "\n=== PROFILE "
                        + persona
                        + " ===",
                        flush=True,
                    )

                    profile = profile_by_slug.get(
                        slug
                    )

                    if not profile:
                        continue

                    email, password = USERS[
                        base_role
                    ]

                    login_result = browser_login(
                        driver,
                        email,
                        password,
                    )

                    if (
                        not login_result
                        or int(
                            login_result[0]
                            or 0
                        ) != 200
                    ):
                        failure(
                            "BROWSER_LOGIN",
                            persona,
                            login_result,
                        )

                        shot(
                            driver,
                            slug,
                            "login",
                        )

                        continue

                    switch_result = browser_switch(
                        driver,
                        team_id,
                        int(
                            profile["id"]
                        ),
                    )

                    if (
                        not switch_result
                        or int(
                            switch_result[0]
                            or 0
                        ) != 200
                    ):
                        failure(
                            "BROWSER_CONTEXT_SWITCH",
                            persona,
                            switch_result,
                        )

                        shot(
                            driver,
                            slug,
                            "switch",
                        )

                        continue

                    boot_result = browser_boot(
                        driver
                    )

                    if (
                        not boot_result
                        or int(
                            boot_result[0]
                            or 0
                        ) != 1
                    ):
                        failure(
                            "BROWSER_BOOT",
                            persona,
                            boot_result,
                        )

                        shot(
                            driver,
                            slug,
                            "boot",
                        )

                        continue

                    try:
                        WebDriverWait(
                            driver,
                            10,
                        ).until(
                            lambda d:
                                d.execute_script(
                                    """
                                    return !!document.querySelector(
                                      '.app-shell'
                                    );
                                    """
                                )
                        )
                    except Exception:
                        failure(
                            "BROWSER_APP_SHELL",
                            persona,
                            "missing",
                        )

                        shot(
                            driver,
                            slug,
                            "shell",
                        )

                        continue

                    # Wait for r23EnhanceShell.
                    chip_ok = False
                    chip = ""

                    for _ in range(50):
                        chip = driver.execute_script(
                            """
                            const e=document.querySelector(
                              '.user-chip .muted'
                            );

                            return e
                              ? (e.innerText||'')
                              : '';
                            """
                        ) or ""

                        if persona in chip:
                            chip_ok = True
                            break

                        time.sleep(.10)

                    if not chip_ok:
                        failure(
                            "BROWSER_PROFILE_CHIP",
                            persona,
                            chip,
                        )
                    else:
                        passed(
                            "BROWSER_PROFILE_CHIP",
                            persona,
                        )

                    # --------------------------------------
                    # PORTAL
                    # --------------------------------------

                    if (
                        base_role
                        not in INTERNAL_ROLES
                    ):
                        route = PORTAL_ROUTES[
                            base_role
                        ]

                        clear_logs(driver)

                        browser_route_wait(
                            driver,
                            route,
                        )

                        loaded = wait_content(
                            driver,
                            8,
                        )

                        text = content_text(
                            driver
                        )

                        markers = [
                            marker
                            for marker in ERROR_MARKERS
                            if marker.lower()
                            in text.lower()
                        ]

                        js = js_errors(
                            driver
                        )

                        net = http_5xx(
                            driver,
                            base,
                        )

                        ok = (
                            loaded
                            and not markers
                            and not js
                            and not net
                        )

                        report[
                            "browser_route_checks"
                        ] += 1

                        browser_matrix.append(
                            {
                                "persona":
                                    persona,

                                "slug":
                                    slug,

                                "base_role":
                                    base_role,

                                "route":
                                    route,

                                "module":
                                    "portal",

                                "expected_allowed":
                                    1,

                                "loaded":
                                    int(loaded),

                                "blocked":
                                    int(bool(markers)),

                                "pass":
                                    int(ok),
                            }
                        )

                        if not ok:
                            failure(
                                "PORTAL_BROWSER_WORKFLOW",
                                persona,
                                {
                                    "route":
                                        route,

                                    "loaded":
                                        loaded,

                                    "markers":
                                        markers,

                                    "js":
                                        js[:5],

                                    "http_5xx":
                                        net[:5],
                                },
                            )

                            shot(
                                driver,
                                slug,
                                "portal",
                            )
                        else:
                            passed(
                                "PORTAL_BROWSER_WORKFLOW",
                                persona,
                                route,
                            )

                        continue

                    perms = permission_by_slug.get(
                        slug,
                        {},
                    )

                    # --------------------------------------
                    # NAV VISIBILITY
                    # --------------------------------------

                    nav_rows = driver.execute_script(
                        """
                        return [
                          ...document.querySelectorAll(
                            '.sidebar .navitem[data-route]'
                          )
                        ].map(el=>({
                          route:el.dataset.route||'',
                          visible:
                            el.getBoundingClientRect().width>0 &&
                            el.getBoundingClientRect().height>0 &&
                            getComputedStyle(el).display!=='none' &&
                            getComputedStyle(el).visibility!=='hidden'
                        }));
                        """
                    ) or []

                    for row in nav_rows:

                        route = row.get(
                            "route"
                        )

                        module = ROUTE_MODULE.get(
                            route
                        )

                        if not module:
                            continue

                        expected = allowed_module(
                            perms,
                            module,
                        )

                        visible = bool(
                            row.get(
                                "visible"
                            )
                        )

                        report[
                            "nav_checks"
                        ] += 1

                        if visible != expected:
                            failure(
                                "BROWSER_NAV_PERMISSION_MISMATCH",
                                persona,
                                {
                                    "route":
                                        route,

                                    "module":
                                        module,

                                    "expected_visible":
                                        expected,

                                    "actual_visible":
                                        visible,
                                },
                            )

                    # --------------------------------------
                    # DIRECT ROUTE ACCESS
                    # --------------------------------------

                    for route in DIRECT_ROUTES:

                        module = ROUTE_MODULE[
                            route
                        ]

                        expected = allowed_module(
                            perms,
                            module,
                        )

                        clear_logs(driver)

                        browser_route_wait(
                            driver,
                            route,
                        )

                        loaded = wait_content(
                            driver,
                            6,
                        )

                        text = content_text(
                            driver
                        )

                        blocked = any(
                            marker.lower()
                            in text.lower()
                            for marker
                            in ERROR_MARKERS
                        )

                        js = js_errors(
                            driver
                        )

                        net = http_5xx(
                            driver,
                            base,
                        )

                        if expected:
                            ok = (
                                loaded
                                and not blocked
                                and not js
                                and not net
                            )
                        else:
                            ok = blocked

                        report[
                            "browser_route_checks"
                        ] += 1

                        browser_matrix.append(
                            {
                                "persona":
                                    persona,

                                "slug":
                                    slug,

                                "base_role":
                                    base_role,

                                "route":
                                    route,

                                "module":
                                    module,

                                "expected_allowed":
                                    int(expected),

                                "loaded":
                                    int(loaded),

                                "blocked":
                                    int(blocked),

                                "pass":
                                    int(ok),
                            }
                        )

                        if not ok:
                            failure(
                                (
                                    "BROWSER_ALLOWED_ROUTE_FAILURE"
                                    if expected
                                    else
                                    "BROWSER_DIRECT_ROUTE_PERMISSION_BYPASS"
                                ),
                                persona,
                                {
                                    "route":
                                        route,

                                    "module":
                                        module,

                                    "expected":
                                        expected,

                                    "loaded":
                                        loaded,

                                    "blocked":
                                        blocked,

                                    "text":
                                        text[:350],

                                    "js":
                                        js[:5],

                                    "http_5xx":
                                        net[:5],
                                },
                            )

                            shot(
                                driver,
                                slug,
                                route,
                            )

                write_csv(
                    evidence
                    / "PROFILE-PERMISSION-MATRIX.csv",
                    profile_matrix,
                )

                write_csv(
                    evidence
                    / "API-PERMISSION-MATRIX.csv",
                    api_matrix,
                )

                write_csv(
                    evidence
                    / "BROWSER-PERMISSION-MATRIX.csv",
                    browser_matrix,
                )

            finally:
                if driver is not None:
                    try:
                        driver.quit()
                    except Exception:
                        pass

                if process.poll() is None:
                    process.terminate()

                try:
                    process.wait(
                        timeout=15
                    )
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(
                        timeout=15
                    )

                server_handle.close()

                print(
                    (
                        "ISOLATED_SERVER_REAPED=PASS"
                        if process.poll() is not None
                        else
                        "ISOLATED_SERVER_REAPED=FAIL"
                    ),
                    flush=True,
                )

        report[
            "functional_failures"
        ] = failures

        report[
            "first_actual_failure"
        ] = (
            failures[0]
            if failures
            else None
        )

        if failures:
            report[
                "result"
            ] = "FUNCTIONAL_GAPS_PROVEN"
            outcome = 10
        else:
            report[
                "result"
            ] = "PASS"
            outcome = 0

    except SetupFailure as exc:
        report[
            "result"
        ] = "SETUP_FAILURE"

        report[
            "setup_failure"
        ] = str(exc)

        outcome = 20

    except Exception as exc:
        report[
            "result"
        ] = "HARNESS_ERROR"

        report[
            "exception"
        ] = repr(exc)

        traceback.print_exc()

        outcome = 20

    finally:
        (
            evidence
            / "R23E-R10R1-RESULT.json"
        ).write_text(
            json.dumps(
                report,
                indent=2,
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )

        print("")
        print("=" * 70)
        print(" ATS-ONE R23E-R10R1 RESULT")
        print("=" * 70)

        print(
            "R23E_R10R1_RESULT="
            + str(
                report["result"]
            )
        )

        print(
            "PROFILE_COUNT="
            + str(
                report["profile_count"]
            )
        )

        print(
            "INTERNAL_PROFILE_COUNT="
            + str(
                report[
                    "internal_profile_count"
                ]
            )
        )

        print(
            "PORTAL_PROFILE_COUNT="
            + str(
                report[
                    "portal_profile_count"
                ]
            )
        )

        print(
            "API_CHECKS="
            + str(
                report["api_checks"]
            )
        )

        print(
            "NAV_CHECKS="
            + str(
                report["nav_checks"]
            )
        )

        print(
            "BROWSER_ROUTE_CHECKS="
            + str(
                report[
                    "browser_route_checks"
                ]
            )
        )

        print(
            "FUNCTIONAL_FAILURE_COUNT="
            + str(
                len(
                    report[
                        "functional_failures"
                    ]
                )
            )
        )

        if report[
            "first_actual_failure"
        ]:
            print(
                "FIRST_ACTUAL_FAILURE="
                + str(
                    report[
                        "first_actual_failure"
                    ]
                )
            )
        else:
            print(
                "FIRST_ACTUAL_FAILURE="
            )

        print(
            "PRODUCT_CHANGE=NO"
        )

        print(
            "MAIN_CHANGE=NO"
        )

        print(
            "REMOTE_PUSH=NO"
        )

        print(
            "PRODUCTION_CHANGE=NO"
        )

        print(
            "EVIDENCE_ROOT="
            + str(evidence)
        )

        print("=" * 70)

    return outcome


if __name__ == "__main__":
    raise SystemExit(main())