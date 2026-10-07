from __future__ import annotations

import argparse
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


class ProbeFailure(RuntimeError):
    def __init__(self, name, category):
        super().__init__(name)
        self.name = name
        self.category = category


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
                value = json.loads(data.decode("utf-8"))
            except (UnicodeError, ValueError):
                value = data.decode(
                    "utf-8", errors="replace"
                )

            return int(response.status), value

    def login(self, email, password):
        return self.req(
            "/api/login",
            "POST",
            {"email": email, "password": password}
        )


def port():
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    number = sock.getsockname()[1]
    sock.close()
    return number


def check(report, name, ok, detail=None, category="SETUP"):
    item = {
        "check": name,
        "pass": bool(ok),
        "category": category
    }

    if detail is not None:
        item["detail"] = detail

    report["checks"].append(item)

    print(
        "[{}] {}".format(
            "PASS" if ok else "FAIL",
            name
        )
        + (
            " :: {}".format(str(detail)[:700])
            if detail is not None else ""
        ),
        flush=True
    )

    if not ok:
        raise ProbeFailure(name, category)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("repo")
    parser.add_argument("evidence")
    args = parser.parse_args()

    repo = Path(args.repo).resolve()
    evidence = Path(args.evidence).resolve()
    evidence.mkdir(parents=True, exist_ok=True)

    report = {
        "mode": "R23E_R4_TEAM_SCOPE_ISOLATED_RUNTIME",
        "result": "NOT_RUN",
        "product_change": False,
        "main_change": False,
        "production_change": False,
        "checks": [],
        "first_failure": None
    }

    result_code = 20

    try:
        with tempfile.TemporaryDirectory(
            prefix="ats-r23e-r4-team-"
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
                    "venv"
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

            number = port()
            base = "http://127.0.0.1:{}".format(number)

            with (evidence / "server.log").open(
                "w", encoding="utf-8"
            ) as log:

                proc = subprocess.Popen(
                    [
                        sys.executable,
                        "-u",
                        "server.py",
                        "--host", "127.0.0.1",
                        "--port", str(number),
                        "--reset",
                        "--quiet"
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

                    check(report, "ISOLATED_SERVER_READY", ready)

                    admin = API(base)

                    status, _ = admin.login(
                        "admin@atsone.local",
                        "Admin@123"
                    )

                    check(
                        report,
                        "ADMIN_LOGIN",
                        status == 200,
                        status
                    )

                    status, users = admin.req(
                        "/api/r23/users-context"
                    )

                    check(
                        report,
                        "USERS_CONTEXT",
                        status == 200 and isinstance(users, list),
                        status
                    )

                    by_role = {
                        x["role"]: x
                        for x in users
                        if isinstance(x, dict) and x.get("role")
                    }

                    for role in ("recruiter", "sales", "hr"):
                        check(
                            report,
                            "USER_" + role.upper(),
                            role in by_role
                        )

                    recruiter_id = int(by_role["recruiter"]["id"])
                    sales_id = int(by_role["sales"]["id"])
                    hr_id = int(by_role["hr"]["id"])

                    status, profiles = admin.req(
                        "/api/r23/role-profiles"
                    )

                    check(
                        report,
                        "PROFILE_CATALOG",
                        status == 200 and isinstance(profiles, list),
                        status
                    )

                    by_slug = {
                        x["slug"]: x
                        for x in profiles
                        if isinstance(x, dict) and x.get("slug")
                    }

                    check(
                        report,
                        "SALES_PROFILE_PRESENT",
                        "sales" in by_slug
                    )

                    check(
                        report,
                        "HR_PROFILE_PRESENT",
                        "hr_workforce_operations" in by_slug
                    )

                    # Two distinct teams in an isolated test DB.
                    team_ids = {}

                    for tag in ("Alpha", "Beta"):
                        status, payload = admin.req(
                            "/api/r23/teams",
                            "POST",
                            {"name": "R23E Team " + tag}
                        )

                        check(
                            report,
                            "TEAM_" + tag.upper() + "_CREATED",
                            status == 201
                            and isinstance(payload, dict)
                            and bool(payload.get("id")),
                            status
                        )

                        team_ids[tag] = int(payload["id"])

                    alpha = team_ids["Alpha"]
                    beta = team_ids["Beta"]

                    # Recruiter profile with team-scoped data access.
                    status, profile = admin.req(
                        "/api/r23/role-profiles",
                        "POST",
                        {
                            "name": "R23E Team-Scoped Recruiter",
                            "slug": "r23e_team_scope_recruiter",
                            "base_role": "recruiter",
                            "data_scope": "team"
                        }
                    )

                    check(
                        report,
                        "TEAM_SCOPED_PROFILE_CREATED",
                        status == 201
                        and isinstance(profile, dict)
                        and bool(profile.get("id")),
                        status
                    )

                    team_profile = int(profile["id"])

                    # Alpha: recruiter and sales teammate.
                    # Beta: HR outsider.
                    memberships = [
                        (
                            "RECRUITER_ALPHA",
                            alpha,
                            recruiter_id,
                            team_profile
                        ),
                        (
                            "TEAMMATE_SALES_ALPHA",
                            alpha,
                            sales_id,
                            int(by_slug["sales"]["id"])
                        ),
                        (
                            "OUTSIDER_HR_BETA",
                            beta,
                            hr_id,
                            int(by_slug["hr_workforce_operations"]["id"])
                        )
                    ]

                    for name, team_id, user_id, profile_id in memberships:
                        status, _ = admin.req(
                            "/api/r23/teams/{}/members".format(team_id),
                            "POST",
                            {
                                "user_id": user_id,
                                "profile_id": profile_id,
                                "is_primary": False
                            }
                        )

                        check(
                            report,
                            "MEMBERSHIP_" + name,
                            status == 200,
                            status
                        )

                    # Three real records, each with a different owner.
                    candidate_ids = {}

                    for name, owner in (
                        ("OWN", recruiter_id),
                        ("TEAMMATE", sales_id),
                        ("OUTSIDER", hr_id)
                    ):
                        status, payload = admin.req(
                            "/api/candidates",
                            "POST",
                            {
                                "first_name": "R23E" + name,
                                "last_name": "TeamProbe",
                                "email":
                                    "r23e-{}@example.test".format(
                                        name.lower()
                                    ),
                                "owner_user_id": owner
                            }
                        )

                        check(
                            report,
                            "CANDIDATE_" + name + "_CREATED",
                            status == 201
                            and isinstance(payload, dict)
                            and bool(payload.get("id")),
                            status
                        )

                        candidate_ids[name] = int(payload["id"])

                    recruiter = API(base)

                    status, _ = recruiter.login(
                        "recruiter@atsone.local",
                        "Recruit@123"
                    )

                    check(
                        report,
                        "RECRUITER_LOGIN",
                        status == 200,
                        status
                    )

                    # Select Alpha with the team-scoped profile.
                    status, context = recruiter.req(
                        "/api/r23/session-context",
                        "POST",
                        {
                            "team_id": alpha,
                            "profile_id": team_profile
                        }
                    )

                    selected = (
                        context.get("selected")
                        if isinstance(context, dict)
                        else None
                    )

                    check(
                        report,
                        "TEAM_PROFILE_SWITCH",
                        status == 200
                        and isinstance(selected, dict)
                        and int(selected.get("team_id") or 0) == alpha
                        and int(selected.get("profile_id") or 0)
                            == team_profile,
                        status
                    )

                    status, context = recruiter.req(
                        "/api/r23/context"
                    )

                    check(
                        report,
                        "TEAM_CONTEXT_HTTP",
                        status == 200 and isinstance(context, dict),
                        status
                    )

                    chosen = context.get("selected") or {}

                    check(
                        report,
                        "SELECTED_TEAM_IS_ALPHA",
                        int(chosen.get("team_id") or 0) == alpha,
                        chosen.get("team_name")
                    )

                    permission = next(
                        (
                            x for x in context.get("permissions", [])
                            if x.get("module") == "candidate"
                        ),
                        None
                    )

                    check(
                        report,
                        "CANDIDATE_SCOPE_IS_TEAM",
                        bool(permission)
                        and permission.get("data_scope") == "team",
                        permission
                    )

                    # REAL FUNCTIONAL ACCEPTANCE STARTS HERE.
                    status, rows = recruiter.req("/api/candidates")

                    check(
                        report,
                        "CANDIDATE_LIST_HTTP",
                        status == 200 and isinstance(rows, list),
                        status,
                        category="FUNCTIONAL"
                    )

                    visible = {
                        int(x["id"])
                        for x in rows
                        if isinstance(x, dict)
                        and x.get("id") is not None
                    }

                    check(
                        report,
                        "TEAM_SCOPE_OWN_VISIBLE",
                        candidate_ids["OWN"] in visible,
                        {
                            "own_id": candidate_ids["OWN"],
                            "visible_ids": sorted(visible)
                        },
                        category="FUNCTIONAL"
                    )

                    check(
                        report,
                        "TEAM_SCOPE_TEAMMATE_VISIBLE",
                        candidate_ids["TEAMMATE"] in visible,
                        {
                            "teammate_id": candidate_ids["TEAMMATE"],
                            "visible_ids": sorted(visible)
                        },
                        category="FUNCTIONAL"
                    )

                    check(
                        report,
                        "TEAM_SCOPE_OUTSIDER_HIDDEN",
                        candidate_ids["OUTSIDER"] not in visible,
                        {
                            "outsider_id": candidate_ids["OUTSIDER"],
                            "visible_ids": sorted(visible)
                        },
                        category="FUNCTIONAL"
                    )

                    # Direct-ID read boundaries.
                    for key in ("OWN", "TEAMMATE"):
                        status, _ = recruiter.req(
                            "/api/candidates/{}".format(
                                candidate_ids[key]
                            )
                        )

                        check(
                            report,
                            "TEAM_SCOPE_DIRECT_" + key + "_ALLOWED",
                            status == 200,
                            status,
                            category="FUNCTIONAL"
                        )

                    # Direct-ID and matching bypass boundaries.
                    for tail, label in (
                        ("", "DIRECT_ID"),
                        ("/matches", "MATCHES")
                    ):
                        status, _ = recruiter.req(
                            "/api/candidates/{}{}".format(
                                candidate_ids["OUTSIDER"],
                                tail
                            )
                        )

                        check(
                            report,
                            "TEAM_SCOPE_OUTSIDER_" + label + "_BLOCKED",
                            status in (403, 404),
                            status,
                            category="FUNCTIONAL"
                        )

                    # Recruiter must not switch to unauthorized Beta.
                    status, _ = recruiter.req(
                        "/api/r23/session-context",
                        "POST",
                        {
                            "team_id": beta,
                            "profile_id": team_profile
                        }
                    )

                    check(
                        report,
                        "UNASSIGNED_BETA_CONTEXT_DENIED",
                        status == 403,
                        status,
                        category="FUNCTIONAL"
                    )

                    status, context = recruiter.req(
                        "/api/r23/context"
                    )

                    check(
                        report,
                        "DENIED_SWITCH_PRESERVES_ALPHA",
                        status == 200
                        and int(
                            (context.get("selected") or {})
                            .get("team_id") or 0
                        ) == alpha,
                        status,
                        category="FUNCTIONAL"
                    )

                    report["result"] = "PASS"
                    result_code = 0

                finally:
                    if proc.poll() is None:
                        proc.terminate()

                    try:
                        proc.wait(timeout=12)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        proc.wait(timeout=12)

                    print(
                        "ISOLATED_SERVER_REAPED=PASS"
                        if proc.poll() is not None
                        else "ISOLATED_SERVER_REAPED=FAIL",
                        flush=True
                    )

    except ProbeFailure as exc:
        report["first_failure"] = exc.name
        report["failure_category"] = exc.category

        report["result"] = (
            "FUNCTIONAL_GAP_PROVEN"
            if exc.category == "FUNCTIONAL"
            else "SETUP_FAILURE"
        )

        result_code = (
            10 if exc.category == "FUNCTIONAL" else 20
        )

        print(
            "FIRST_ACTUAL_FAILURE={}".format(exc.name),
            flush=True
        )

    except Exception as exc:
        report["result"] = "HARNESS_ERROR"
        report["exception"] = repr(exc)

        print(
            "HARNESS_EXCEPTION={}".format(repr(exc)),
            flush=True
        )

        traceback.print_exc()
        result_code = 20

    finally:
        (
            evidence / "R23E-R4-TEAM-SCOPE-RESULT.json"
        ).write_text(
            json.dumps(
                report,
                indent=2,
                ensure_ascii=False
            ) + "\n",
            encoding="utf-8"
        )

        print(
            "TEAM_SCOPE_PROBE={}".format(report["result"]),
            flush=True
        )

        print(
            "EVIDENCE_ROOT={}".format(evidence),
            flush=True
        )

    return result_code


if __name__ == "__main__":
    raise SystemExit(main())