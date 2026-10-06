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
            data=r.read()

            try:
                data=json.loads(data.decode())
            except Exception:
                pass

            return r.status,data


class Vendor(BaseHTTPRequestHandler):
    def log_message(self,*a):
        pass

    def _send(self,obj):
        raw=json.dumps(obj).encode()
        self.send_response(200)
        self.send_header("Content-Type","application/json")
        self.send_header("Content-Length",str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        self._send({
            "ok":True,
            "provider":"controlled-r18-test"
        })

    def do_POST(self):
        n=int(self.headers.get("Content-Length") or 0)
        if n:
            self.rfile.read(n)

        self._send({
            "ok":True,
            "id":"R18-PROVIDER-001"
        })


def port():
    s=socket.socket()
    s.bind(("127.0.0.1",0))
    p=s.getsockname()[1]
    s.close()
    return p


def check(name,ok,detail=""):
    print(
        f"[{'PASS' if ok else 'FAIL'}] {name}"
        +(f" :: {detail}" if detail else ""),
        flush=True
    )

    if not ok:
        raise RuntimeError(name+" "+detail)


def main():
    repo=pathlib.Path(sys.argv[1]).resolve()
    evidence=pathlib.Path(sys.argv[2]).resolve()
    evidence.mkdir(parents=True,exist_ok=True)

    vp=port()
    vendor=ThreadingHTTPServer(("127.0.0.1",vp),Vendor)
    threading.Thread(
        target=vendor.serve_forever,
        daemon=True
    ).start()

    with tempfile.TemporaryDirectory(prefix="ats-r18-") as td:
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

        pnum=port()
        base=f"http://127.0.0.1:{pnum}"

        log=(evidence/"server.log").open("w",encoding="utf-8")

        proc=subprocess.Popen(
            [
                sys.executable,"-u","server.py",
                "--host","127.0.0.1",
                "--port",str(pnum),
                "--reset","--quiet"
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

            api=API(base)

            st,_=api.req(
                "/api/login",
                "POST",
                {
                    "email":"admin@atsone.local",
                    "password":"Admin@123"
                }
            )

            check("ADMIN_LOGIN_UNCHANGED",st==200,str(st))

            st,assign=api.req("/api/assignments")
            check("ASSIGNMENTS_READ",st==200 and bool(assign))

            st,a=api.req(
                "/api/attendance",
                "POST",
                {
                    "assignment_id":assign[0]["id"],
                    "attendance_date":"2026-10-06",
                    "status":"Present",
                    "scheduled_hours":8,
                    "worked_hours":8,
                    "late_minutes":0,
                    "note":"R18 acceptance"
                }
            )

            check(
                "ATTENDANCE_CREATE",
                st==201 and isinstance(a.get("id"),int),
                str((st,a))
            )

            aid=a["id"]

            st,_=api.req(
                f"/api/attendance/{aid}",
                "PATCH",
                {
                    "worked_hours":7.5,
                    "approval_state":"Approved"
                }
            )

            check("ATTENDANCE_APPROVE",st==200,str(st))

            st,rows=api.req("/api/attendance")
            hit=[x for x in rows if x["id"]==aid][0]

            check(
                "ATTENDANCE_PERSISTENCE",
                hit["approval_state"]=="Approved"
                and float(hit["worked_hours"])==7.5
            )

            st,companies=api.req("/api/companies")
            check("COMPANIES_READ",st==200 and bool(companies))

            st,inv=api.req(
                "/api/invoices",
                "POST",
                {
                    "company_id":companies[0]["id"],
                    "period_start":"2026-10-01",
                    "period_end":"2026-10-07",
                    "tax":10,
                    "discount":5,
                    "due_date":"2026-10-31",
                    "lines":[{
                        "description":"Staffing services",
                        "quantity":10,
                        "unit_price":10
                    }]
                }
            )

            check(
                "INVOICE_CREATE",
                st==201 and isinstance(inv.get("id"),int),
                str((st,inv))
            )

            iid=inv["id"]

            st,_=api.req(
                f"/api/invoices/{iid}/issue",
                "POST",
                {}
            )
            check("INVOICE_ISSUE",st==200,str(st))

            st,p=api.req(
                f"/api/invoices/{iid}/payments",
                "POST",
                {"amount":50,"reference":"PARTIAL"}
            )

            check(
                "INVOICE_PART_PAYMENT",
                st==201 and p.get("status")=="part_paid",
                str((st,p))
            )

            st,p=api.req(
                f"/api/invoices/{iid}/payments",
                "POST",
                {"amount":55,"reference":"FINAL"}
            )

            check(
                "INVOICE_FULL_PAYMENT",
                st==201
                and p.get("status")=="paid"
                and float(p.get("balance"))==0,
                str((st,p))
            )

            st,detail=api.req(f"/api/invoices/{iid}")

            check(
                "INVOICE_DETAIL",
                st==200
                and detail["status"]=="paid"
                and len(detail["lines"])==1
                and len(detail["payments"])==2
            )

            st,connectors=api.req("/api/integrations")

            check("INTEGRATIONS_READ",st==200)

            check(
                "NO_DEMO_CONNECTOR_MODE",
                all(
                    str(x.get("mode") or "").lower()!="demo"
                    for x in connectors
                )
            )

            fieldglass=[
                x for x in connectors
                if "fieldglass" in str(x.get("name") or "").lower()
            ]

            if fieldglass:
                check(
                    "FIELDGLASS_NOT_FAKE_CONNECTED",
                    fieldglass[0].get("connection_state")
                    in {
                        "Configuration Required",
                        "Credentials Required",
                        "Ready for Test"
                    }
                )

            st,c=api.req(
                "/api/integrations",
                "POST",
                {
                    "category":"VMS",
                    "name":"R18 Controlled Provider",
                    "mode":"External",
                    "status":"Configured",
                    "config":{
                        "base_url":f"http://127.0.0.1:{vp}",
                        "auth":{"type":"none"},
                        "paths":{
                            "test":{
                                "path":"/health",
                                "method":"GET"
                            },
                            "sync":{
                                "path":"/sync",
                                "method":"POST"
                            }
                        }
                    }
                }
            )

            check(
                "CONTROLLED_CONNECTOR_CREATE",
                st==201 and isinstance(c.get("id"),int),
                str((st,c))
            )

            cid=c["id"]

            st,res=api.req(
                f"/api/integrations/{cid}/test",
                "POST",
                {}
            )

            check(
                "REAL_HTTP_CONNECTOR_TEST",
                st==200
                and res.get("ok") is True
                and res.get("provider_http_status")==200,
                str((st,res))
            )

            st,res=api.req(
                f"/api/integrations/{cid}/sync",
                "POST",
                {"payload":{"hello":"world"}}
            )

            check(
                "REAL_HTTP_CONNECTOR_SYNC",
                st==200
                and res.get("ok") is True
                and res.get("provider_id")=="R18-PROVIDER-001",
                str((st,res))
            )

            st,candidates=api.req("/api/candidates")
            check("CANDIDATES_READ",st==200 and bool(candidates))

            st,res=api.req(
                "/api/communications/send",
                "POST",
                {
                    "channel":"Internal",
                    "entity_type":"candidate",
                    "entity_id":candidates[0]["id"],
                    "subject":"R18 acceptance",
                    "body":"Internal communication"
                }
            )

            check(
                "INTERNAL_COMMUNICATION",
                st==201 and res.get("status")=="Logged",
                str((st,res))
            )

            st,jobs=api.req("/api/jobs?include_archived=1")

            check(
                "HARVEST_STATUS_FIELD_PRESENT",
                st==200
                and bool(jobs)
                and "harvest_status" in jobs[0]
            )

            print("R18_POWERSHELL_ACCEPTANCE=PASS",flush=True)

        finally:
            if proc.poll() is None:
                proc.terminate()

                try:
                    proc.wait(timeout=8)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=5)

            log.close()

    vendor.shutdown()
    vendor.server_close()

    return 0


if __name__=="__main__":
    raise SystemExit(main())
