from __future__ import annotations

import http.cookiejar
import json
import os
import pathlib
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request


class API:

    def __init__(self,base):
        self.base=base.rstrip("/")
        jar=http.cookiejar.CookieJar()
        self.opener=urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(jar)
        )

    def request(self,path,method="GET",body=None):
        raw=(
            json.dumps(body).encode("utf-8")
            if body is not None
            else None
        )

        headers={"Accept":"application/json"}

        if raw is not None:
            headers["Content-Type"]="application/json"

        req=urllib.request.Request(
            self.base+path,
            data=raw,
            headers=headers,
            method=method,
        )

        try:
            response=self.opener.open(
                req,
                timeout=12,
            )
        except urllib.error.HTTPError as exc:
            response=exc

        with response:
            raw=response.read()

            try:
                payload=json.loads(
                    raw.decode("utf-8")
                )
            except Exception:
                payload=raw.decode(
                    "utf-8",
                    errors="replace",
                )

            return response.status,payload

    def login(self,email,password):
        return self.request(
            "/api/login",
            "POST",
            {
                "email":email,
                "password":password,
            },
        )


def free_port():
    sock=socket.socket()
    sock.bind(("127.0.0.1",0))
    value=sock.getsockname()[1]
    sock.close()
    return value


def require(name,condition,detail=None):
    print(
        f"[{'PASS' if condition else 'FAIL'}] {name}"
        +(f" :: {detail}" if detail is not None else ""),
        flush=True,
    )

    if not condition:
        raise RuntimeError(name)


def main():

    repo=pathlib.Path(
        sys.argv[1]
    ).resolve()

    evidence=pathlib.Path(
        sys.argv[2]
    ).resolve()

    evidence.mkdir(
        parents=True,
        exist_ok=True,
    )

    with tempfile.TemporaryDirectory(
        prefix="ats-r23e-own-scope-"
    ) as temp:

        app=pathlib.Path(temp)/"app"

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

        env=os.environ.copy()

        env.update(
            ATS_ONE_MODE="test",
            ATS_ONE_RESET_AUTHORITY_CONFIRMED=
                "LOCAL_TEST_ONLY",
            SUPABASE_URL="",
            SUPABASE_SERVICE_ROLE_KEY="",
            RENDER_INSTANCE_ID="",
        )

        port=free_port()
        base=f"http://127.0.0.1:{port}"

        log_path=evidence/"server.log"

        with log_path.open(
            "w",
            encoding="utf-8",
        ) as log:

            proc=subprocess.Popen(
                [
                    sys.executable,
                    "-u",
                    "server.py",
                    "--host","127.0.0.1",
                    "--port",str(port),
                    "--reset",
                    "--quiet",
                ],
                cwd=app,
                env=env,
                stdout=log,
                stderr=subprocess.STDOUT,
            )

            try:

                ready=False

                for _ in range(240):

                    if proc.poll() is not None:
                        break

                    try:
                        status,_=API(base).request(
                            "/api/health"
                        )

                        if status==200:
                            ready=True
                            break

                    except Exception:
                        pass

                    time.sleep(.15)

                require(
                    "ISOLATED_SERVER_READY",
                    ready,
                )

                admin=API(base)

                status,_=admin.login(
                    "admin@atsone.local",
                    "Admin@123",
                )

                require(
                    "ADMIN_LOGIN",
                    status==200,
                    status,
                )

                status,users=admin.request(
                    "/api/r23/users-context"
                )

                require(
                    "USERS_CONTEXT",
                    status==200
                    and isinstance(users,list),
                    status,
                )

                recruiter=next(
                    (
                        x for x in users
                        if x.get("role")=="recruiter"
                    ),
                    None,
                )

                sales=next(
                    (
                        x for x in users
                        if x.get("role")=="sales"
                    ),
                    None,
                )

                require(
                    "RECRUITER_FOUND",
                    bool(recruiter),
                    recruiter,
                )

                require(
                    "FOREIGN_OWNER_FOUND",
                    bool(sales),
                    sales,
                )

                recruiter_id=int(
                    recruiter["id"]
                )

                sales_id=int(
                    sales["id"]
                )

                status,teams=admin.request(
                    "/api/r23/teams"
                )

                require(
                    "TEAMS_READ",
                    status==200
                    and bool(teams),
                    status,
                )

                default_team=next(
                    (
                        x for x in teams
                        if x.get("code")=="default"
                    ),
                    teams[0],
                )

                team_id=int(
                    default_team["id"]
                )

                status,profile=admin.request(
                    "/api/r23/role-profiles",
                    "POST",
                    {
                        "name":
                            "R23E Own Scope Recruiter",

                        "slug":
                            "r23e_own_scope_recruiter",

                        "base_role":
                            "recruiter",

                        "data_scope":
                            "own",

                        "description":
                            "Permanent R23E own scope regression",
                    },
                )

                require(
                    "OWN_PROFILE_CREATE",
                    status==201
                    and isinstance(profile,dict)
                    and profile.get("id"),
                    (status,profile),
                )

                profile_id=int(
                    profile["id"]
                )

                status,payload=admin.request(
                    f"/api/r23/teams/{team_id}/members",
                    "POST",
                    {
                        "user_id":
                            recruiter_id,

                        "profile_id":
                            profile_id,

                        "is_primary":
                            False,
                    },
                )

                require(
                    "OWN_PROFILE_ASSIGN",
                    status==200,
                    (status,payload),
                )

                status,own=admin.request(
                    "/api/candidates",
                    "POST",
                    {
                        "first_name":
                            "R23EOwn",

                        "last_name":
                            "Candidate",

                        "email":
                            "r23e-own@example.test",

                        "owner_user_id":
                            recruiter_id,
                    },
                )

                require(
                    "OWN_FIXTURE_CREATE",
                    status==201
                    and own.get("id"),
                    status,
                )

                own_id=int(own["id"])

                status,foreign=admin.request(
                    "/api/candidates",
                    "POST",
                    {
                        "first_name":
                            "R23EForeign",

                        "last_name":
                            "Candidate",

                        "email":
                            "r23e-foreign@example.test",

                        "owner_user_id":
                            sales_id,
                    },
                )

                require(
                    "FOREIGN_FIXTURE_CREATE",
                    status==201
                    and foreign.get("id"),
                    status,
                )

                foreign_id=int(
                    foreign["id"]
                )

                recruiter_api=API(base)

                status,_=recruiter_api.login(
                    "recruiter@atsone.local",
                    "Recruit@123",
                )

                require(
                    "RECRUITER_LOGIN",
                    status==200,
                    status,
                )

                status,context=recruiter_api.request(
                    "/api/r23/session-context",
                    "POST",
                    {
                        "team_id":
                            team_id,

                        "profile_id":
                            profile_id,
                    },
                )

                require(
                    "OWN_CONTEXT_SWITCH",
                    status==200,
                    (status,context),
                )

                status,rows=recruiter_api.request(
                    "/api/candidates"
                )

                require(
                    "CANDIDATE_LIST_HTTP",
                    status==200
                    and isinstance(rows,list),
                    status,
                )

                ids={
                    int(x["id"])
                    for x in rows
                    if isinstance(x,dict)
                    and x.get("id") is not None
                }

                require(
                    "OWN_RECORD_VISIBLE",
                    own_id in ids,
                    sorted(ids),
                )

                require(
                    "FOREIGN_RECORD_HIDDEN",
                    foreign_id not in ids,
                    {
                        "foreign_id":
                            foreign_id,

                        "visible_ids":
                            sorted(ids),
                    },
                )

                status,payload=recruiter_api.request(
                    f"/api/candidates/{own_id}"
                )

                require(
                    "OWN_DIRECT_ID_ALLOWED",
                    status==200,
                    status,
                )

                status,payload=recruiter_api.request(
                    f"/api/candidates/{foreign_id}"
                )

                require(
                    "FOREIGN_DIRECT_ID_BLOCKED",
                    status in (403,404),
                    (status,payload),
                )

                status,payload=recruiter_api.request(
                    f"/api/candidates/{foreign_id}/matches"
                )

                require(
                    "FOREIGN_MATCHES_BYPASS_BLOCKED",
                    status in (403,404),
                    (status,payload),
                )

                result={
                    "result":"PASS",
                    "own_candidate_id":own_id,
                    "foreign_candidate_id":foreign_id,
                    "checks":[
                        "OWN_RECORD_VISIBLE",
                        "FOREIGN_RECORD_HIDDEN",
                        "OWN_DIRECT_ID_ALLOWED",
                        "FOREIGN_DIRECT_ID_BLOCKED",
                        "FOREIGN_MATCHES_BYPASS_BLOCKED",
                    ],
                }

                (
                    evidence /
                    "R23E-OWN-SCOPE-REGRESSION.json"
                ).write_text(
                    json.dumps(
                        result,
                        indent=2,
                    ),
                    encoding="utf-8",
                )

                print("")
                print("="*70)
                print(
                    " R23E OWN-SCOPE REGRESSION = PASS"
                )
                print("="*70)
                print(
                    "CANDIDATE_LIST_OWN_SCOPE=PASS"
                )
                print(
                    "CANDIDATE_DIRECT_ID_OWN_SCOPE=PASS"
                )
                print(
                    "CANDIDATE_MATCHES_OWN_SCOPE=PASS"
                )
                print("="*70)

                return 0

            finally:

                if proc.poll() is None:
                    proc.terminate()

                    try:
                        proc.wait(timeout=10)

                    except subprocess.TimeoutExpired:
                        proc.kill()
                        proc.wait(timeout=5)


if __name__=="__main__":
    raise SystemExit(main())
