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
import threading
import time
import urllib.error
import urllib.request

from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer


class API:

    def __init__(self,base):
        self.base=base.rstrip("/")
        jar=http.cookiejar.CookieJar()
        self.opener=urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(jar)
        )

    def req(self,path,method="GET",body=None):
        raw=json.dumps(body).encode() if body is not None else None
        headers={"Accept":"application/json"}

        if raw is not None:
            headers["Content-Type"]="application/json"

        req=urllib.request.Request(
            self.base+path,
            data=raw,
            headers=headers,
            method=method
        )

        try:
            r=self.opener.open(req,timeout=10)
        except urllib.error.HTTPError as e:
            r=e

        with r:
            raw=r.read()

            try:
                payload=json.loads(raw.decode())
            except Exception:
                payload=raw

            return r.status,payload

    def login(self,email,password):
        return self.req(
            "/api/login",
            "POST",
            {"email":email,"password":password}
        )


class Provider(BaseHTTPRequestHandler):

    def log_message(self,*args):
        pass

    def _reply(self):
        raw=json.dumps({
            "ok":True,
            "id":"R19-PROVIDER-REAL-TEST-001"
        }).encode()

        self.send_response(200)
        self.send_header("Content-Type","application/json")
        self.send_header("Content-Length",str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        self._reply()

    def do_POST(self):
        n=int(self.headers.get("Content-Length") or 0)
        if n:
            self.rfile.read(n)
        self._reply()


def port():
    s=socket.socket()
    s.bind(("127.0.0.1",0))
    n=s.getsockname()[1]
    s.close()
    return n


def check(name,condition,detail=""):
    print(
        f"[{'PASS' if condition else 'FAIL'}] {name}"
        +(f" :: {detail}" if detail else ""),
        flush=True
    )

    if not condition:
        raise RuntimeError(name+" "+str(detail))


def main():

    repo=pathlib.Path(sys.argv[1]).resolve()
    evidence=pathlib.Path(sys.argv[2]).resolve()
    evidence.mkdir(parents=True,exist_ok=True)

    provider_port=port()

    provider=ThreadingHTTPServer(
        ("127.0.0.1",provider_port),
        Provider
    )

    threading.Thread(
        target=provider.serve_forever,
        daemon=True
    ).start()

    with tempfile.TemporaryDirectory(
        prefix="ats-r19-"
    ) as td:

        app=pathlib.Path(td)/"app"

        shutil.copytree(
            repo,
            app,
            ignore=shutil.ignore_patterns(
                ".git","data","__pycache__",
                ".pytest_cache","node_modules",
                ".venv","venv"
            )
        )

        env=os.environ.copy()

        env.update(
            ATS_ONE_MODE="test",
            ATS_ONE_RESET_AUTHORITY_CONFIRMED="LOCAL_TEST_ONLY",
            SUPABASE_URL="",
            SUPABASE_SERVICE_ROLE_KEY="",
            RENDER_INSTANCE_ID=""
        )

        server_port=port()
        base=f"http://127.0.0.1:{server_port}"

        log=(evidence/"server.log").open(
            "w",
            encoding="utf-8"
        )

        proc=subprocess.Popen(
            [
                sys.executable,
                "-u",
                "server.py",
                "--host","127.0.0.1",
                "--port",str(server_port),
                "--reset",
                "--quiet"
            ],
            cwd=app,
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT
        )

        try:

            ready=False

            for _ in range(240):

                if proc.poll() is not None:
                    break

                try:
                    st,_=API(base).req("/api/health")
                    if st==200:
                        ready=True
                        break
                except Exception:
                    pass

                time.sleep(.15)

            check("SERVER_READY",ready)

            admin=API(base)

            st,_=admin.login(
                "admin@atsone.local",
                "Admin@123"
            )

            check(
                "ADMIN_LOGIN_UNCHANGED",
                st==200,
                st
            )

            # --------------------------------------------------
            # CREATE REAL LOCAL HTTP CONNECTOR
            # --------------------------------------------------

            actions={
                name:{
                    "path":"/"+name,
                    "method":"POST"
                }
                for name in [
                    "sync",
                    "send_email",
                    "send_sms",
                    "background_check",
                    "esign",
                    "everify",
                    "payroll",
                    "gl_export",
                    "job_board",
                    "vms",
                    "create_meeting"
                ]
            }

            actions["test"]={
                "path":"/health",
                "method":"GET"
            }

            st,c=admin.req(
                "/api/integrations",
                "POST",
                {
                    "category":"Enterprise Test",
                    "name":"R19 Controlled Real HTTP Provider",
                    "mode":"External",
                    "status":"Configured",
                    "config":{
                        "base_url":
                            f"http://127.0.0.1:{provider_port}",
                        "auth":{"type":"none"},
                        "paths":actions
                    }
                }
            )

            check(
                "REAL_CONNECTOR_CREATED",
                st==201 and isinstance(c.get("id"),int),
                (st,c)
            )

            connector_id=c["id"]

            # --------------------------------------------------
            # CAMPAIGN EXECUTION
            # --------------------------------------------------

            st,cands=admin.req("/api/candidates")
            check("CANDIDATES_AVAILABLE",st==200 and bool(cands))

            candidate_id=cands[0]["id"]

            st,camp=admin.req(
                "/api/r19/campaigns",
                "POST",
                {
                    "name":"R19 Internal Campaign",
                    "channel":"Internal",
                    "subject":"R19",
                    "body":"Real internal campaign",
                    "candidate_ids":[candidate_id]
                }
            )

            check(
                "CAMPAIGN_CREATE",
                st==201 and camp.get("id"),
                (st,camp)
            )

            st,run=admin.req(
                f"/api/r19/campaigns/{camp['id']}/run",
                "POST",
                {}
            )

            check(
                "CAMPAIGN_EXECUTION",
                st==200
                and run.get("delivered")==1
                and run.get("status")=="Completed",
                (st,run)
            )

            # --------------------------------------------------
            # REPORT BUILDER + SCHEDULER
            # --------------------------------------------------

            st,report=admin.req(
                "/api/r14/report-builders",
                "POST",
                {
                    "name":"R19 Candidate Report",
                    "entity_type":"candidates",
                    "columns_json":
                        '["id","first_name","last_name","status"]',
                    "filters_json":"{}",
                    "is_shared":1
                }
            )

            check(
                "REPORT_DEFINITION_CREATE",
                st==201 and report.get("id"),
                (st,report)
            )

            st,schedule=admin.req(
                "/api/r19/report-schedules",
                "POST",
                {
                    "report_id":report["id"],
                    "frequency":"Daily",
                    "format":"CSV"
                }
            )

            check(
                "REPORT_SCHEDULE_CREATE",
                st==201 and schedule.get("id"),
                (st,schedule)
            )

            st,rr=admin.req(
                f"/api/r19/report-schedules/{schedule['id']}/run",
                "POST",
                {}
            )

            check(
                "REPORT_SCHEDULE_EXECUTION",
                st==200
                and rr.get("status")=="Generated"
                and rr.get("row_count",0)>0,
                (st,rr)
            )

            # --------------------------------------------------
            # REAL EXTERNAL GATEWAY TEST
            # --------------------------------------------------

            st,gates=admin.req(
                "/api/r19/external-gateways"
            )

            check(
                "EXTERNAL_GATEWAYS_READ",
                st==200 and bool(gates)
            )

            gateway=gates[0]

            st,_=admin.req(
                f"/api/r19/external-gateways/{gateway['id']}/link",
                "POST",
                {"connector_id":connector_id}
            )

            check(
                "EXTERNAL_GATEWAY_LINK",
                st==200,
                st
            )

            st,gtest=admin.req(
                f"/api/r19/external-gateways/{gateway['id']}/test",
                "POST",
                {}
            )

            check(
                "EXTERNAL_GATEWAY_REAL_HTTP_TEST",
                st==200
                and gtest.get("ok") is True
                and gtest.get("provider_http_status")==200,
                (st,gtest)
            )

            # --------------------------------------------------
            # BACKGROUND REAL EXTERNAL TRANSACTION
            # --------------------------------------------------

            st,external=admin.req(
                "/api/r19/external/background/execute",
                "POST",
                {
                    "connector_id":connector_id,
                    "entity_type":"candidate",
                    "entity_id":candidate_id,
                    "payload":{
                        "candidate_id":candidate_id,
                        "package":"Standard"
                    }
                }
            )

            check(
                "BACKGROUND_REAL_HTTP_EXECUTION",
                st==200
                and external.get("ok") is True
                and external.get("provider_id")
                    =="R19-PROVIDER-REAL-TEST-001",
                (st,external)
            )

            st,tx=admin.req(
                "/api/r19/external-transactions"
            )

            check(
                "EXTERNAL_TRANSACTION_AUDIT",
                st==200
                and any(
                    x.get("category")=="background"
                    and x.get("status")=="Success"
                    for x in tx
                )
            )

            # --------------------------------------------------
            # INTERVIEW MEETING PROVIDER
            # --------------------------------------------------

            st,interviews=admin.req("/api/interviews")
            check(
                "INTERVIEWS_AVAILABLE",
                st==200 and bool(interviews)
            )

            iid=interviews[0]["id"]

            st,meeting=admin.req(
                f"/api/r19/interviews/{iid}/meeting",
                "POST",
                {"connector_id":connector_id}
            )

            check(
                "MEETING_PROVIDER_REAL_HTTP",
                st==200
                and meeting.get("ok") is True
                and meeting.get("provider_id")
                    =="R19-PROVIDER-REAL-TEST-001",
                (st,meeting)
            )

            # --------------------------------------------------
            # JOB ALERT EXECUTION
            # --------------------------------------------------

            st,alert=admin.req(
                "/api/r14/job-alerts",
                "POST",
                {
                    "name":"R19 Open Job Alert",
                    "criteria_json":"{}",
                    "channel":"Internal",
                    "frequency":"Daily",
                    "active":1
                }
            )

            check(
                "JOB_ALERT_CREATE_ACTIVE",
                st==201 and alert.get("id"),
                (st,alert)
            )

            st,ar=admin.req(
                f"/api/r19/job-alerts/{alert['id']}/run",
                "POST",
                {}
            )

            check(
                "JOB_ALERT_EXECUTION",
                st==200
                and ar.get("status")=="Matched"
                and ar.get("match_count",0)>0,
                (st,ar)
            )

            # --------------------------------------------------
            # WORKFLOW WITH EXTERNAL STEP
            # --------------------------------------------------

            definition={
                "steps":[
                    {
                        "action":"audit",
                        "message":"R19 workflow internal step"
                    },
                    {
                        "action":"background_check",
                        "connector_id":connector_id,
                        "payload":{
                            "candidate_id":candidate_id
                        }
                    }
                ]
            }

            st,wf=admin.req(
                "/api/r14/workflows",
                "POST",
                {
                    "name":"R19 External Workflow",
                    "trigger_name":"manual",
                    "entity_type":"candidate",
                    "definition_json":
                        json.dumps(definition),
                    "active":1
                }
            )

            check(
                "WORKFLOW_CREATE",
                st==201 and wf.get("id"),
                (st,wf)
            )

            st,wr=admin.req(
                f"/api/r19/workflows/{wf['id']}/run",
                "POST",
                {
                    "entity_type":"candidate",
                    "entity_id":candidate_id,
                    "context":{"source":"R19 test"}
                }
            )

            check(
                "WORKFLOW_EXTERNAL_EXECUTION",
                st==201
                and wr.get("status")=="Completed"
                and all(
                    x.get("ok")
                    for x in wr.get("outcomes",[])
                ),
                (st,wr)
            )

            # --------------------------------------------------
            # DUPLICATE INTELLIGENCE
            # --------------------------------------------------

            original=cands[0]

            st,newcand=admin.req(
                "/api/candidates",
                "POST",
                {
                    "first_name":original["first_name"],
                    "last_name":original["last_name"],
                    "email":original.get("email"),
                    "phone":original.get("phone"),
                    "city":original.get("city"),
                    "state":original.get("state"),
                    "zip":original.get("zip")
                }
            )

            check(
                "DUPLICATE_FIXTURE_CREATE",
                st==201 and newcand.get("id"),
                (st,newcand)
            )

            st,dup=admin.req(
                f"/api/r19/candidates/{candidate_id}/duplicates"
            )

            check(
                "DUPLICATE_INTELLIGENCE",
                st==200
                and any(
                    x.get("id")==newcand["id"]
                    and x.get("duplicate_score",0)>=70
                    for x in dup.get("results",[])
                ),
                (st,dup)
            )

            # --------------------------------------------------
            # R19 COVERAGE
            # --------------------------------------------------

            st,cov=admin.req("/api/r19/coverage")

            check(
                "R19_COVERAGE",
                st==200
                and cov.get("campaign_executor")=="working"
                and cov.get("external_gateway_http")=="working"
            )

            print(
                "R19_ACCEPTANCE=PASS",
                flush=True
            )

        finally:

            if proc.poll() is None:
                proc.terminate()

                try:
                    proc.wait(timeout=8)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=5)

            log.close()

    provider.shutdown()
    provider.server_close()

    return 0


if __name__=="__main__":
    raise SystemExit(main())
