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
        raw = json.dumps(body).encode("utf-8") if body is not None else None

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
            response = self.opener.open(request, timeout=12)
        except urllib.error.HTTPError as exc:
            response = exc

        with response:
            data = response.read()

            try:
                payload = json.loads(data.decode("utf-8"))
            except Exception:
                payload = data.decode("utf-8-sig", errors="replace")

            return int(response.status), payload

    def login(self, email, password):
        return self.req(
            "/api/login",
            "POST",
            {"email": email, "password": password},
        )


def free_port():
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    value = sock.getsockname()[1]
    sock.close()
    return value


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("repo")
    parser.add_argument("evidence")
    args = parser.parse_args()

    repo = Path(args.repo).resolve()
    evidence = Path(args.evidence).resolve()
    evidence.mkdir(parents=True, exist_ok=True)

    report = {
        "mode": "R23E_R8R1_MUTATION_SCOPE_RUNTIME",
        "result": "NOT_RUN",
        "checks": [],
        "functional_failures": [],
        "first_actual_failure": None,
        "product_change": False,
        "main_change": False,
        "production_change": False,
    }

    failures = []

    def check(name, ok, detail=None, functional=False):
        row = {
            "name": name,
            "pass": bool(ok),
            "category": "FUNCTIONAL" if functional else "SETUP",
        }

        if detail is not None:
            row["detail"] = detail

        report["checks"].append(row)

        print(
            "[{}] {}".format("PASS" if ok else "FAIL", name)
            + (" :: {}".format(str(detail)[:700]) if detail is not None else ""),
            flush=True,
        )

        if not ok:
            if functional:
                failures.append(name)
            else:
                raise SetupFailure(name)

    def allowed(name, result):
        status, payload = result
        check(
            name,
            status in (200, 201),
            {"status": status, "payload": payload},
            functional=True,
        )

    def blocked(name, result):
        status, payload = result
        check(
            name,
            status in (403, 404),
            {"status": status, "payload": payload},
            functional=True,
        )

    outcome = 20

    try:
        with tempfile.TemporaryDirectory(prefix="ats-r23e-r8r1-") as td:
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

            env = os.environ.copy()
            env.update(
                ATS_ONE_MODE="test",
                ATS_ONE_RESET_AUTHORITY_CONFIRMED="LOCAL_TEST_ONLY",
                SUPABASE_URL="",
                SUPABASE_SERVICE_ROLE_KEY="",
                RENDER_INSTANCE_ID="",
            )

            port = free_port()
            base = f"http://127.0.0.1:{port}"

            with (evidence / "server.log").open("w", encoding="utf-8") as log:
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
                    stdout=log,
                    stderr=subprocess.STDOUT,
                )

                try:
                    ready = False

                    for _ in range(240):
                        if process.poll() is not None:
                            break

                        try:
                            status, _ = API(base).req("/api/health")

                            if status == 200:
                                ready = True
                                break
                        except Exception:
                            pass

                        time.sleep(0.15)

                    check("ISOLATED_SERVER_READY", ready)

                    admin = API(base)
                    recruiter = API(base)

                    status, _ = admin.login(
                        "admin@atsone.local",
                        "Admin@123",
                    )
                    check("ADMIN_LOGIN", status == 200, status)

                    status, _ = recruiter.login(
                        "recruiter@atsone.local",
                        "Recruit@123",
                    )
                    check("RECRUITER_LOGIN", status == 200, status)

                    # --------------------------------------------------
                    # USERS
                    # --------------------------------------------------

                    status, users = admin.req("/api/r23/users-context")

                    check(
                        "USERS_CONTEXT",
                        status == 200 and isinstance(users, list),
                        status,
                    )

                    by_role = {
                        row["role"]: row
                        for row in users
                        if isinstance(row, dict) and row.get("role")
                    }

                    for role in ("recruiter", "sales", "hr"):
                        check(
                            "USER_" + role.upper(),
                            role in by_role,
                        )

                    recruiter_id = int(by_role["recruiter"]["id"])
                    sales_id = int(by_role["sales"]["id"])
                    hr_id = int(by_role["hr"]["id"])

                    # --------------------------------------------------
                    # SYSTEM PROFILES
                    # --------------------------------------------------

                    status, profiles = admin.req("/api/r23/role-profiles")

                    check(
                        "PROFILE_CATALOG",
                        status == 200 and isinstance(profiles, list),
                        status,
                    )

                    by_slug = {
                        row["slug"]: row
                        for row in profiles
                        if isinstance(row, dict) and row.get("slug")
                    }

                    check(
                        "SALES_PROFILE_PRESENT",
                        "sales" in by_slug,
                    )

                    check(
                        "HR_PROFILE_PRESENT",
                        "hr_workforce_operations" in by_slug,
                    )

                    sales_profile = int(by_slug["sales"]["id"])
                    hr_profile = int(
                        by_slug["hr_workforce_operations"]["id"]
                    )

                    # --------------------------------------------------
                    # TEAMS
                    # --------------------------------------------------

                    status, teams = admin.req("/api/r23/teams")

                    check(
                        "TEAM_LIST",
                        status == 200
                        and isinstance(teams, list)
                        and bool(teams),
                        status,
                    )

                    default_team = next(
                        (
                            row
                            for row in teams
                            if row.get("code") == "default"
                        ),
                        teams[0],
                    )

                    default_team_id = int(default_team["id"])

                    team_ids = {}

                    for tag in ("Alpha", "Beta"):
                        status, payload = admin.req(
                            "/api/r23/teams",
                            "POST",
                            {"name": "R23E Mutation " + tag},
                        )

                        check(
                            "TEAM_" + tag.upper() + "_CREATE",
                            status == 201
                            and isinstance(payload, dict)
                            and payload.get("id"),
                            status,
                        )

                        team_ids[tag] = int(payload["id"])

                    alpha = team_ids["Alpha"]
                    beta = team_ids["Beta"]

                    # --------------------------------------------------
                    # OWN / TEAM PROFILES
                    # --------------------------------------------------

                    custom_profiles = {}

                    for scope in ("own", "team"):
                        status, payload = admin.req(
                            "/api/r23/role-profiles",
                            "POST",
                            {
                                "name":
                                    "R23E Mutation "
                                    + scope.upper()
                                    + " Recruiter",

                                "slug":
                                    "r23e_mutation_"
                                    + scope
                                    + "_recruiter",

                                "base_role":
                                    "recruiter",

                                "data_scope":
                                    scope,
                            },
                        )

                        check(
                            scope.upper() + "_PROFILE_CREATE",
                            status == 201
                            and isinstance(payload, dict)
                            and payload.get("id"),
                            status,
                        )

                        custom_profiles[scope] = int(
                            payload["id"]
                        )

                    own_profile = custom_profiles["own"]
                    team_profile = custom_profiles["team"]

                    # --------------------------------------------------
                    # TEAM MEMBERSHIP
                    # --------------------------------------------------

                    memberships = [
                        (
                            "OWN_DEFAULT",
                            default_team_id,
                            recruiter_id,
                            own_profile,
                        ),
                        (
                            "RECRUITER_ALPHA",
                            alpha,
                            recruiter_id,
                            team_profile,
                        ),
                        (
                            "SALES_ALPHA",
                            alpha,
                            sales_id,
                            sales_profile,
                        ),
                        (
                            "HR_BETA",
                            beta,
                            hr_id,
                            hr_profile,
                        ),
                    ]

                    for name, team_id, user_id, profile_id in memberships:
                        status, payload = admin.req(
                            f"/api/r23/teams/{team_id}/members",
                            "POST",
                            {
                                "user_id": user_id,
                                "profile_id": profile_id,
                                "is_primary": False,
                            },
                        )

                        check(
                            "MEMBERSHIP_" + name,
                            status == 200,
                            {"status": status, "payload": payload},
                        )

                    # --------------------------------------------------
                    # CANDIDATE FIXTURES
                    # --------------------------------------------------

                    candidates = {}

                    fixtures = [
                        ("OWN", recruiter_id),
                        ("OWN_FOREIGN", sales_id),
                        ("TEAMMATE", sales_id),
                        ("OUTSIDER", hr_id),
                    ]

                    for tag, owner_id in fixtures:
                        status, payload = admin.req(
                            "/api/candidates",
                            "POST",
                            {
                                "first_name": "R23E" + tag,
                                "last_name": "MutationProbe",
                                "email":
                                    "r23e-mut-"
                                    + tag.lower().replace("_", "-")
                                    + "@example.test",
                                "current_title": "Original " + tag,
                                "owner_user_id": owner_id,
                            },
                        )

                        check(
                            "CANDIDATE_" + tag + "_CREATE",
                            status == 201
                            and isinstance(payload, dict)
                            and payload.get("id"),
                            status,
                        )

                        candidates[tag] = int(payload["id"])

                    # --------------------------------------------------
                    # SKILL / DOCUMENT FIXTURES
                    # --------------------------------------------------

                    assets = {}

                    for tag in ("OWN_FOREIGN", "OUTSIDER"):
                        cid = candidates[tag]

                        status, skill = admin.req(
                            f"/api/candidates/{cid}/skills",
                            "POST",
                            {
                                "skill":
                                    "R23E-"
                                    + tag
                                    + "-ORIGINAL-SKILL",
                                "years": 1,
                            },
                        )

                        check(
                            "SKILL_FIXTURE_" + tag,
                            status == 201
                            and isinstance(skill, dict)
                            and skill.get("id"),
                            status,
                        )

                        marker = (
                            "R23E-"
                            + tag
                            + "-ORIGINAL-DOCUMENT"
                        )

                        status, document = admin.req(
                            f"/api/candidates/{cid}/documents",
                            "POST",
                            {
                                "name":
                                    tag
                                    + " Original Document",
                                "file_name":
                                    tag.lower()
                                    + ".txt",
                                "mime_type":
                                    "text/plain",
                                "doc_type":
                                    "Other",
                                "content_base64":
                                    base64.b64encode(
                                        marker.encode("utf-8")
                                    ).decode("ascii"),
                            },
                        )

                        check(
                            "DOCUMENT_FIXTURE_" + tag,
                            status == 201
                            and isinstance(document, dict)
                            and document.get("id"),
                            status,
                        )

                        assets[tag] = {
                            "skill_id":
                                int(skill["id"]),
                            "document_id":
                                int(document["id"]),
                        }

                    # --------------------------------------------------
                    # SCOPE RUNNER
                    # --------------------------------------------------

                    def probe_scope(
                        prefix,
                        scope,
                        team_id,
                        profile_id,
                        allowed_id,
                        blocked_id,
                        asset,
                    ):
                        print(
                            "\n===== "
                            + prefix
                            + " MUTATION PROBE =====",
                            flush=True,
                        )

                        status, selection = recruiter.req(
                            "/api/r23/session-context",
                            "POST",
                            {
                                "team_id": team_id,
                                "profile_id": profile_id,
                            },
                        )

                        check(
                            prefix + "_CONTEXT_SWITCH",
                            status == 200
                            and isinstance(selection, dict)
                            and int(
                                (
                                    selection.get("selected")
                                    or {}
                                ).get("profile_id")
                                or 0
                            ) == profile_id,
                            status,
                        )

                        status, context = recruiter.req(
                            "/api/r23/context"
                        )

                        check(
                            prefix + "_CONTEXT_READ",
                            status == 200
                            and isinstance(context, dict),
                            status,
                        )

                        candidate_perm = next(
                            (
                                row
                                for row in context.get(
                                    "permissions",
                                    []
                                )
                                if row.get("module")
                                == "candidate"
                            ),
                            None,
                        )

                        document_perm = next(
                            (
                                row
                                for row in context.get(
                                    "permissions",
                                    []
                                )
                                if row.get("module")
                                == "document"
                            ),
                            None,
                        )

                        check(
                            prefix + "_SCOPE_CONFIRMED",
                            bool(candidate_perm)
                            and candidate_perm.get(
                                "data_scope"
                            ) == scope,
                            candidate_perm,
                        )

                        check(
                            prefix + "_DOCUMENT_CAPABILITY_PRESENT",
                            bool(candidate_perm)
                            and int(
                                candidate_perm.get(
                                    "can_documents"
                                )
                                or 0
                            ) == 1
                            and bool(document_perm)
                            and int(
                                document_perm.get(
                                    "can_documents"
                                )
                                or 0
                            ) == 1,
                            {
                                "candidate": candidate_perm,
                                "document": document_perm,
                            },
                        )

                        # Positive mutation control.
                        allowed(
                            prefix
                            + "_ALLOWED_CANDIDATE_PATCH",
                            recruiter.req(
                                f"/api/candidates/{allowed_id}",
                                "PATCH",
                                {
                                    "current_title":
                                        prefix
                                        + " Allowed Mutation"
                                },
                            ),
                        )

                        # Base candidate.
                        blocked(
                            prefix
                            + "_FOREIGN_CANDIDATE_PATCH_BLOCKED",
                            recruiter.req(
                                f"/api/candidates/{blocked_id}",
                                "PATCH",
                                {
                                    "current_title":
                                        "ILLEGAL "
                                        + prefix
                                        + " PATCH"
                                },
                            ),
                        )

                        # Resume commit.
                        blocked(
                            prefix
                            + "_FOREIGN_RESUME_COMMIT_BLOCKED",
                            recruiter.req(
                                f"/api/candidates/{blocked_id}/resume/commit",
                                "POST",
                                {
                                    "reviewed": {
                                        "summary":
                                            "ILLEGAL "
                                            + prefix
                                            + " RESUME"
                                    }
                                },
                            ),
                        )

                        # Nested skill create.
                        blocked(
                            prefix
                            + "_FOREIGN_SKILL_POST_BLOCKED",
                            recruiter.req(
                                f"/api/candidates/{blocked_id}/skills",
                                "POST",
                                {
                                    "skill":
                                        "ILLEGAL-"
                                        + prefix
                                        + "-SKILL",
                                    "years": 99,
                                },
                            ),
                        )

                        # Nested skill patch.
                        blocked(
                            prefix
                            + "_FOREIGN_SKILL_PATCH_BLOCKED",
                            recruiter.req(
                                (
                                    f"/api/candidates/{blocked_id}"
                                    f"/skills/{asset['skill_id']}"
                                ),
                                "PATCH",
                                {"years": 77},
                            ),
                        )

                        # Note.
                        blocked(
                            prefix
                            + "_FOREIGN_NOTE_POST_BLOCKED",
                            recruiter.req(
                                f"/api/candidates/{blocked_id}/notes",
                                "POST",
                                {
                                    "note":
                                        "ILLEGAL "
                                        + prefix
                                        + " NOTE"
                                },
                            ),
                        )

                        # Nested document create.
                        blocked(
                            prefix
                            + "_FOREIGN_DOCUMENT_POST_BLOCKED",
                            recruiter.req(
                                f"/api/candidates/{blocked_id}/documents",
                                "POST",
                                {
                                    "name":
                                        "Illegal "
                                        + prefix
                                        + " Document",
                                    "file_name":
                                        "illegal-"
                                        + prefix.lower()
                                        + ".txt",
                                    "mime_type":
                                        "text/plain",
                                    "content_base64":
                                        base64.b64encode(
                                            (
                                                "illegal-"
                                                + prefix
                                            ).encode("utf-8")
                                        ).decode("ascii"),
                                },
                            ),
                        )

                        # Direct document patch.
                        blocked(
                            prefix
                            + "_FOREIGN_DOCUMENT_PATCH_BLOCKED",
                            recruiter.req(
                                (
                                    "/api/candidate-documents/"
                                    + str(asset["document_id"])
                                ),
                                "PATCH",
                                {
                                    "name":
                                        "ILLEGAL "
                                        + prefix
                                        + " DOC PATCH"
                                },
                            ),
                        )

                        # Bulk mutation.
                        blocked(
                            prefix
                            + "_FOREIGN_BULK_EMAIL_BLOCKED",
                            recruiter.req(
                                "/api/search/bulk",
                                "POST",
                                {
                                    "candidate_ids": [
                                        blocked_id
                                    ],
                                    "action": "email",
                                    "subject":
                                        "ILLEGAL "
                                        + prefix
                                        + " BULK",
                                    "body":
                                        "must not persist",
                                },
                            ),
                        )

                        # Nested skill deletion.
                        blocked(
                            prefix
                            + "_FOREIGN_SKILL_DELETE_BLOCKED",
                            recruiter.req(
                                (
                                    f"/api/candidates/{blocked_id}"
                                    f"/skills/{asset['skill_id']}"
                                ),
                                "DELETE",
                            ),
                        )

                        # Direct document deletion.
                        blocked(
                            prefix
                            + "_FOREIGN_DOCUMENT_DELETE_BLOCKED",
                            recruiter.req(
                                (
                                    "/api/candidate-documents/"
                                    + str(asset["document_id"])
                                ),
                                "DELETE",
                            ),
                        )

                        # Candidate archive/delete.
                        blocked(
                            prefix
                            + "_FOREIGN_CANDIDATE_DELETE_BLOCKED",
                            recruiter.req(
                                f"/api/candidates/{blocked_id}",
                                "DELETE",
                            ),
                        )

                    # --------------------------------------------------
                    # OWN SCOPE
                    # --------------------------------------------------

                    probe_scope(
                        "OWN",
                        "own",
                        default_team_id,
                        own_profile,
                        candidates["OWN"],
                        candidates["OWN_FOREIGN"],
                        assets["OWN_FOREIGN"],
                    )

                    # --------------------------------------------------
                    # TEAM SCOPE
                    # --------------------------------------------------

                    probe_scope(
                        "TEAM",
                        "team",
                        alpha,
                        team_profile,
                        candidates["TEAMMATE"],
                        candidates["OUTSIDER"],
                        assets["OUTSIDER"],
                    )

                finally:
                    if process.poll() is None:
                        process.terminate()

                    try:
                        process.wait(timeout=12)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=12)

                    check(
                        "ISOLATED_SERVER_REAPED",
                        process.poll() is not None,
                    )

        report["functional_failures"] = failures
        report["first_actual_failure"] = (
            failures[0] if failures else None
        )

        if failures:
            report["result"] = "FUNCTIONAL_GAPS_PROVEN"
            outcome = 10
        else:
            report["result"] = "PASS"
            outcome = 0

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
        result_path = (
            evidence
            / "R23E-R8R1-MUTATION-SCOPE-RESULT.json"
        )

        result_path.write_text(
            json.dumps(
                report,
                indent=2,
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )

        passed = sum(
            1
            for row in report["checks"]
            if row["pass"]
        )

        failed = sum(
            1
            for row in report["checks"]
            if not row["pass"]
        )

        print("")
        print("=" * 70)
        print(" ATS-ONE R23E-R8R1 RESULT")
        print("=" * 70)
        print("R23E_R8R1_RESULT=" + report["result"])
        print("CHECKS_PASS=" + str(passed))
        print("CHECKS_FAIL=" + str(failed))
        print(
            "FIRST_ACTUAL_FAILURE="
            + str(
                report["first_actual_failure"]
                or ""
            )
        )
        print(
            "FUNCTIONAL_FAILURES="
            + ";".join(failures)
        )
        print("PRODUCT_CHANGE=NO")
        print("MAIN_CHANGE=NO")
        print("PRODUCTION_CHANGE=NO")
        print("FULL_REGRESSION_RUN=NO")
        print("EVIDENCE_ROOT=" + str(evidence))
        print("=" * 70)

    return outcome


if __name__ == "__main__":
    raise SystemExit(main())