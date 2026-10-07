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

from http.server import (
    BaseHTTPRequestHandler,
    ThreadingHTTPServer,
)


class API:

    def __init__(self,base):

        self.base=base.rstrip("/")

        jar=http.cookiejar.CookieJar()

        self.opener=urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(
                jar
            )
        )


    def req(
        self,
        path,
        method="GET",
        body=None
    ):

        raw=(
            json.dumps(body).encode()
            if body is not None
            else None
        )

        headers={
            "Accept":"application/json"
        }

        if raw is not None:
            headers["Content-Type"]="application/json"
        request=urllib.request.Request(
            self.base+path,
            data=raw,
            headers=headers,
            method=method
        )

        try:
            response=self.opener.open(
                request,
                timeout=10
            )

        except urllib.error.HTTPError as exc:
            response=exc

        with response:

            raw=response.read()

            try:
                payload=json.loads(
                    raw.decode()
                )
            except Exception:
                payload=raw

            return (
                response.status,
                payload
            )


    def login(
        self,
        email,
        password
    ):

        return self.req(
            "/api/login",
            "POST",
            {
                "email":email,
                "password":password,
            }
        )


class Provider(BaseHTTPRequestHandler):

    def log_message(self,*args):
        pass


    def _read(self):

        n=int(
            self.headers.get(
                "Content-Length"
            )
            or 0
        )

        if not n:
            return {}

        raw=self.rfile.read(n)

        try:
            return json.loads(
                raw.decode()
            )
        except Exception:
            return {}


    def _send(self,obj,status=200):

        raw=json.dumps(
            obj
        ).encode()

        self.send_response(status)

        self.send_header(
            "Content-Type",
            "application/json"
        )

        self.send_header(
            "Content-Length",
            str(len(raw))
        )

        self.end_headers()

        self.wfile.write(raw)


    def do_GET(self):

        self._send({
            "ok":True,
            "id":"R22-PROVIDER-HEALTH"
        })


    def do_POST(self):

        self._read()

        if self.path=="/reference_check":

            return self._send({
                "ok":True,
                "id":"R22-REFERENCE-001",
                "status":"submitted"
            })


        if self.path=="/wotc_screen":

            return self._send({
                "ok":True,
                "id":"R22-WOTC-001",
                "eligible":True
            })


        if self.path=="/sync_calendar":

            return self._send({
                "ok":True,
                "id":"R22-OUTLOOK-001",
                "synced":3
            })


        if self.path=="/enrich_candidate":

            return self._send({
                "ok":True,
                "id":"R22-ENRICH-001",
                "candidate_patch":{
                    "current_title":
                        "Enriched Platform Engineer",

                    "city":
                        "Enriched City",

                    "summary":
                        "Verified provider enrichment"
                }
            })


        return self._send(
            {
                "ok":False,
                "error":"Unknown path"
            },
            404
        )


def free_port():

    sock=socket.socket()

    sock.bind(
        ("127.0.0.1",0)
    )

    value=sock.getsockname()[1]

    sock.close()

    return value


def check(
    name,
    condition,
    detail=""
):

    print(
        f"[{'PASS' if condition else 'FAIL'}] "
        +name
        +(f" :: {detail}" if detail else ""),
        flush=True
    )

    if not condition:
        raise RuntimeError(
            name+" "+str(detail)
        )


def main():

    repo=pathlib.Path(
        sys.argv[1]
    ).resolve()

    evidence=pathlib.Path(
        sys.argv[2]
    ).resolve()

    evidence.mkdir(
        parents=True,
        exist_ok=True
    )


    provider_port=free_port()

    provider=ThreadingHTTPServer(
        (
            "127.0.0.1",
            provider_port
        ),
        Provider
    )

    threading.Thread(
        target=provider.serve_forever,
        daemon=True
    ).start()


    with tempfile.TemporaryDirectory(
        prefix="ats-r22-"
    ) as temp_dir:

        app=(
            pathlib.Path(temp_dir)
            /"app"
        )

        shutil.copytree(
            repo,
            app,
            ignore=shutil.ignore_patterns(
                ".git",
                "data",
                "__pycache__",
                ".pytest_cache",
                ".venv",
                "venv",
                "node_modules"
            )
        )


        port=free_port()

        base=(
            f"http://127.0.0.1:{port}"
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

        env.pop(
            "R22_MISSING_CREDENTIAL",
            None
        )


        log_path=(
            evidence
            /"r22-server.log"
        )

        log=log_path.open(
            "w",
            encoding="utf-8"
        )


        proc=subprocess.Popen(
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

            ready=False

            for _ in range(200):

                if proc.poll() is not None:
                    break

                try:
                    st,health=API(base).req(
                        "/api/health"
                    )

                    if (
                        st==200
                        and health.get("ok")
                    ):
                        ready=True
                        break

                except Exception:
                    pass

                time.sleep(.15)


            check(
                "SERVER_READY",
                ready
            )


            admin=API(base)

            st,user=admin.login(
                "admin@atsone.local",
                "Admin@123"
            )

            check(
                "ADMIN_LOGIN_UNCHANGED",
                st==200,
                st
            )


            # --------------------------------------------------
            # WHITE-LABEL APPLICATION
            # --------------------------------------------------

            st,brand=admin.req(
                "/api/r22/branding"
            )

            check(
                "BRANDING_READ",
                st==200
                and brand.get(
                    "product_name"
                )=="ATS One"
            )


            st,brand=admin.req(
                "/api/r22/branding",
                "POST",
                {
                    "product_name":
                        "Northstar Talent Cloud",

                    "portal_title":
                        "Northstar Careers",

                    "logo_url":
                        "https://example.invalid/logo.svg",

                    "primary_color":
                        "#123456",

                    "secondary_color":
                        "#654321",

                    "support_email":
                        "support@example.com",
                }
            )

            check(
                "WHITE_LABEL_SAVE",
                st==200
                and brand.get(
                    "product_name"
                )=="Northstar Talent Cloud"
                and brand.get(
                    "primary_color"
                )=="#123456",
                (st,brand)
            )


            public=API(base)

            st,pub=public.req(
                "/api/r22/public-branding"
            )

            check(
                "PUBLIC_LOGIN_BRANDING",
                st==200
                and pub.get(
                    "product_name"
                )=="Northstar Talent Cloud",
                (st,pub)
            )


            # --------------------------------------------------
            # CANDIDATE
            # --------------------------------------------------

            st,candidates=admin.req(
                "/api/candidates"
            )

            check(
                "CANDIDATES_AVAILABLE",
                st==200
                and bool(candidates)
            )

            cid=candidates[0]["id"]


            # --------------------------------------------------
            # CREATE REAL CONTROLLED HTTP ADAPTERS
            # --------------------------------------------------

            definitions=[
                (
                    "reference-check",
                    "Reference Check",
                    "reference_check",
                    "/reference_check",
                ),

                (
                    "wotc",
                    "WOTC",
                    "wotc_screen",
                    "/wotc_screen",
                ),

                (
                    "outlook",
                    "Outlook",
                    "sync_calendar",
                    "/sync_calendar",
                ),

                (
                    "candidate-enrichment",
                    "Candidate Enrichment",
                    "enrich_candidate",
                    "/enrich_candidate",
                ),
            ]


            connectors={}

            for (
                key,
                category,
                action,
                path
            ) in definitions:

                st,res=admin.req(
                    "/api/integrations",
                    "POST",
                    {
                        "category":category,

                        "name":
                            "R22 Controlled "
                            +category,

                        "mode":"External",
                        "status":"Configured",

                        "config":{
                            "base_url":
                                f"http://127.0.0.1:{provider_port}",

                            "auth":{
                                "type":"none"
                            },

                            "paths":{
                                action:{
                                    "path":path,
                                    "method":"POST"
                                }
                            }
                        }
                    }
                )

                check(
                    "CONNECTOR_CREATE_"
                    +key.upper()
                        .replace("-","_"),
                    st==201
                    and isinstance(
                        res.get("id"),
                        int
                    ),
                    (st,res)
                )

                connectors[key]=res["id"]


            st,adapters=admin.req(
                "/api/r22/adapters"
            )

            check(
                "ADAPTER_REGISTRY_READ",
                st==200
                and len(adapters)==4
                and all(
                    x.get("connectors")
                    for x in adapters
                ),
                (st,adapters)
            )


            # --------------------------------------------------
            # REFERENCE CHECK
            # --------------------------------------------------

            st,res=admin.req(
                "/api/r22/adapters/reference-check/execute",
                "POST",
                {
                    "connector_id":
                        connectors[
                            "reference-check"
                        ],

                    "candidate_id":cid,
                }
            )

            check(
                "REFERENCE_CHECK_REAL_HTTP",
                st==200
                and res.get("ok") is True
                and res.get(
                    "provider_id"
                )=="R22-REFERENCE-001",
                (st,res)
            )


            # --------------------------------------------------
            # WOTC
            # --------------------------------------------------

            st,res=admin.req(
                "/api/r22/adapters/wotc/execute",
                "POST",
                {
                    "connector_id":
                        connectors["wotc"],

                    "candidate_id":cid,
                }
            )

            check(
                "WOTC_REAL_HTTP",
                st==200
                and res.get("ok") is True
                and res.get(
                    "provider_id"
                )=="R22-WOTC-001",
                (st,res)
            )


            # --------------------------------------------------
            # OUTLOOK / MICROSOFT GRAPH STYLE SYNC
            # --------------------------------------------------

            st,res=admin.req(
                "/api/r22/adapters/outlook/execute",
                "POST",
                {
                    "connector_id":
                        connectors["outlook"],

                    "payload":{
                        "calendar":
                            "primary",

                        "window":
                            "next-7-days",
                    }
                }
            )

            check(
                "OUTLOOK_REAL_HTTP_SYNC",
                st==200
                and res.get("ok") is True
                and res.get(
                    "provider_id"
                )=="R22-OUTLOOK-001",
                (st,res)
            )


            # --------------------------------------------------
            # CANDIDATE ENRICHMENT — PROVIDER + DATABASE UPDATE
            # --------------------------------------------------

            st,res=admin.req(
                "/api/r22/adapters/candidate-enrichment/execute",
                "POST",
                {
                    "connector_id":
                        connectors[
                            "candidate-enrichment"
                        ],

                    "candidate_id":cid,
                }
            )

            check(
                "CANDIDATE_ENRICHMENT_REAL_HTTP",
                st==200
                and res.get("ok") is True
                and res.get(
                    "provider_id"
                )=="R22-ENRICH-001"
                and "current_title"
                    in res.get(
                        "candidate_updated_fields",
                        []
                    ),
                (st,res)
            )


            st,candidate=admin.req(
                f"/api/candidates/{cid}"
            )

            check(
                "CANDIDATE_ENRICHMENT_PERSISTED",
                st==200
                and candidate.get(
                    "current_title"
                )=="Enriched Platform Engineer"
                and candidate.get(
                    "city"
                )=="Enriched City",
                (st,candidate)
            )


            # --------------------------------------------------
            # EXTERNAL PROVIDER TRUTH GATES
            # --------------------------------------------------

            st,missing_creds=admin.req(
                "/api/integrations",
                "POST",
                {
                    "category":
                        "Reference Check",

                    "name":
                        "Missing Credential Truth Gate",

                    "mode":"External",
                    "status":"Configured",

                    "credential_ref":
                        "R22_MISSING_CREDENTIAL",

                    "config":{
                        "base_url":
                            f"http://127.0.0.1:{provider_port}",

                        "auth":{
                            "type":"bearer"
                        },

                        "paths":{
                            "reference_check":{
                                "path":
                                    "/reference_check",

                                "method":
                                    "POST"
                            }
                        }
                    }
                }
            )

            check(
                "MISSING_CREDENTIAL_CONNECTOR_CREATED",
                st==201
            )


            st,res=admin.req(
                "/api/r22/adapters/reference-check/execute",
                "POST",
                {
                    "connector_id":
                        missing_creds["id"],

                    "candidate_id":cid,
                }
            )

            check(
                "NO_FAKE_SUCCESS_WITHOUT_CREDENTIALS",
                st==409
                and res.get("ok") is False
                and res.get(
                    "status"
                )=="Credentials Required",
                (st,res)
            )


            st,missing_cfg=admin.req(
                "/api/integrations",
                "POST",
                {
                    "category":"WOTC",
                    "name":
                        "Missing Configuration Truth Gate",

                    "mode":"External",
                    "status":"Configured",
                    "config":{}
                }
            )

            check(
                "MISSING_CONFIGURATION_CONNECTOR_CREATED",
                st==201
            )


            st,res=admin.req(
                "/api/r22/adapters/wotc/execute",
                "POST",
                {
                    "connector_id":
                        missing_cfg["id"],

                    "candidate_id":cid,
                }
            )

            check(
                "NO_FAKE_SUCCESS_WITHOUT_CONFIGURATION",
                st==409
                and res.get("ok") is False
                and res.get(
                    "status"
                )=="Configuration Required",
                (st,res)
            )


            # --------------------------------------------------
            # MULTILINGUAL CANDIDATE EXPERIENCE
            # --------------------------------------------------

            candidate_api=API(base)

            st,_=candidate_api.login(
                "candidate@atsone.local",
                "Candidate@123"
            )

            check(
                "CANDIDATE_LOGIN",
                st==200
            )


            st,experience=candidate_api.req(
                "/api/r22/candidate-experience"
            )

            supported={
                x["code"]
                for x in experience.get(
                    "supported_locales",
                    []
                )
            }

            check(
                "MULTILINGUAL_LANGUAGES_AVAILABLE",
                st==200
                and {
                    "en",
                    "es",
                    "fr",
                    "hi",
                }.issubset(supported),
                (st,experience)
            )


            st,res=candidate_api.req(
                "/api/r22/candidate-experience",
                "POST",
                {
                    "locale":"hi"
                }
            )

            check(
                "CANDIDATE_LANGUAGE_SAVE",
                st==200
                and res.get(
                    "locale"
                )=="hi",
                (st,res)
            )


            st,experience=candidate_api.req(
                "/api/r22/candidate-experience"
            )

            check(
                "CANDIDATE_LANGUAGE_PERSISTENCE",
                st==200
                and experience.get(
                    "locale"
                )=="hi"
                and experience.get(
                    "translations",
                    {}
                ).get(
                    "welcome"
                )=="स्वागत है",
                (st,experience)
            )


            check(
                "CANDIDATE_WHITE_LABEL_VISIBLE",
                experience.get(
                    "branding",
                    {}
                ).get(
                    "product_name"
                )=="Northstar Talent Cloud"
            )


            # --------------------------------------------------
            # AUDIT / COVERAGE
            # --------------------------------------------------

            st,cases=admin.req(
                "/api/r22/external-cases"
            )

            check(
                "EXTERNAL_CASE_AUDIT",
                st==200
                and len(cases)>=6,
                len(cases)
                    if isinstance(
                        cases,
                        list
                    )
                    else cases
            )


            st,coverage=admin.req(
                "/api/r22/coverage"
            )

            check(
                "R22_COVERAGE",
                st==200
                and coverage.get(
                    "multilingual_candidate_experience"
                )=="working"
                and coverage.get(
                    "white_label_application"
                )=="working"
                and coverage.get(
                    "reference_check_adapter"
                )=="working"
                and coverage.get(
                    "wotc_adapter"
                )=="working"
                and coverage.get(
                    "outlook_synchronization_adapter"
                )=="working"
                and coverage.get(
                    "candidate_enrichment_adapter"
                )=="working"
            )


            js=(
                app
                /"web"
                /"r22.js"
            ).read_text(
                encoding="utf-8"
            ).lower()


            check(
                "FRONTEND_MULTILINGUAL_SURFACE",
                "multilingual candidate experience"
                in js
                and "r22setcandidatelocale"
                in js
            )


            check(
                "FRONTEND_WHITE_LABEL_SURFACE",
                "white-label"
                in js
                and "r22savebranding"
                in js
            )


            print(
                "R22_SIX_GAP_FUNCTIONAL_ACCEPTANCE=PASS",
                flush=True
            )


        finally:

            if proc.poll() is None:

                proc.terminate()

                try:
                    proc.wait(
                        timeout=10
                    )

                except subprocess.TimeoutExpired:

                    proc.kill()
                    proc.wait(
                        timeout=5
                    )

            log.close()


    provider.shutdown()
    provider.server_close()

    return 0


if __name__=="__main__":
    raise SystemExit(
        main()
    )
