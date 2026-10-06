from __future__ import annotations

import json
import os
import pathlib
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import traceback

from urllib.request import urlopen

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


USERS=[
    ("admin","admin@atsone.local","Admin@123"),
    ("teamlead","teamlead@atsone.local","Lead@123"),
    ("recruiter","recruiter@atsone.local","Recruit@123"),
    ("sales","sales@atsone.local","Sales@123"),
    ("hr","hr@atsone.local","HR@123"),
    ("finance","finance@atsone.local","Finance@123"),
    ("client","client@atsone.local","Client@123"),
    ("candidate","candidate@atsone.local","Candidate@123"),
    ("worker","worker@atsone.local","Worker@123"),
    ("supplier","supplier@atsone.local","Supplier@123"),
    ("approver","approver@atsone.local","Approve@123"),
]

INTERNAL={
    "admin","teamlead","recruiter","sales","hr","finance"
}

JS_BUILTINS={
    "if","for","while","switch","return",
    "String","Number","Boolean","Object","Array",
    "Math","Date","JSON","parseInt","parseFloat",
    "encodeURIComponent","decodeURIComponent",
    "setTimeout","clearTimeout","Promise"
}

ERROR_MARKERS=[
    "Unable to load page.",
    "Unable to load.",
    "Unknown page",
    "Server error"
]

FORBIDDEN_VISIBLE=[
    "Demo connector",
    "LinkedIn-style Demo",
    "fake success"
]

ALLOWED_DISABLED={
    "previous",
    "next"
}


def free_port():
    s=socket.socket()
    s.bind(("127.0.0.1",0))
    p=s.getsockname()[1]
    s.close()
    return p


def report_failure(failures,kind,role,route,detail):
    item={
        "kind":kind,
        "role":role,
        "route":route,
        "detail":str(detail)
    }
    failures.append(item)
    print(
        f"[FAIL] {kind} :: role={role} route={route} :: {detail}",
        flush=True
    )


def wait_server(url,proc):
    for _ in range(240):
        if proc.poll() is not None:
            return False
        try:
            with urlopen(url+"/api/health",timeout=1) as r:
                if r.status==200:
                    return True
        except Exception:
            pass
        time.sleep(.15)
    return False


def clear_browser_logs(driver):
    for typ in ("browser","performance"):
        try:
            driver.get_log(typ)
        except Exception:
            pass


def performance_5xx(driver,base):
    failures=[]
    try:
        logs=driver.get_log("performance")
    except Exception:
        return failures

    for entry in logs:
        try:
            msg=json.loads(entry["message"])["message"]
            if msg.get("method")!="Network.responseReceived":
                continue
            response=msg["params"]["response"]
            status=int(response.get("status") or 0)
            url=response.get("url") or ""
            if url.startswith(base) and status>=500:
                failures.append({
                    "status":status,
                    "url":url
                })
        except Exception:
            continue

    return failures


def javascript_errors(driver):
    out=[]
    try:
        logs=driver.get_log("browser")
    except Exception:
        return out

    for entry in logs:
        level=str(entry.get("level") or "").upper()
        source=str(entry.get("source") or "").lower()
        message=str(entry.get("message") or "")

        if level=="SEVERE" and source=="javascript":
            out.append(message)

    return out


def visible_click_handlers(driver):
    return driver.execute_script(
        """
        return [...document.querySelectorAll(
            '#content [onclick], .sidebar [onclick], .topbar [onclick]'
        )]
        .filter(el => {
            const r=el.getBoundingClientRect();
            const s=getComputedStyle(el);
            return r.width>0 && r.height>0 &&
                   s.visibility!=='hidden' &&
                   s.display!=='none';
        })
        .map(el => ({
            tag:el.tagName,
            text:(el.innerText||el.getAttribute('aria-label')||'').trim(),
            onclick:el.getAttribute('onclick')||''
        }));
        """
    )


def undefined_handlers(driver,handlers):
    missing=[]

    for h in handlers:
        onclick=h.get("onclick") or ""

        # Only validate direct/global function calls.
        # Ignore property/method calls such as:
        #   array.forEach()
        #   document.getElementById()
        #   document.querySelectorAll()
        names=re.findall(
            r"(?<![.$\w])([A-Za-z_$][A-Za-z0-9_$]*)\s*\(",
            onclick
        )

        for name in names:
            if name in JS_BUILTINS:
                continue

            ok=driver.execute_script(
                """
                try {
                    return typeof window[arguments[0]] === 'function';
                } catch (_) {
                    return false;
                }
                """,
                name
            )

            if not ok:
                missing.append({
                    "text":h.get("text"),
                    "onclick":onclick,
                    "function":name
                })

    unique=[]
    seen=set()

    for item in missing:
        key=(item["onclick"],item["function"])
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)

    return unique


def unexplained_disabled(driver):
    rows=driver.execute_script(
        """
        return [...document.querySelectorAll('button[disabled]')]
        .filter(el => {
            const r=el.getBoundingClientRect();
            const s=getComputedStyle(el);
            return r.width>0 && r.height>0 &&
                   s.visibility!=='hidden' &&
                   s.display!=='none';
        })
        .map(el => (el.innerText||el.textContent||'').trim());
        """
    )

    return [
        x for x in rows
        if x.strip().lower() not in ALLOWED_DISABLED
    ]


def route_text(driver):
    return driver.execute_script(
        """
        const c=document.querySelector('#content');
        return c ? (c.innerText||'') : '';
        """
    ) or ""


def wait_route(driver):
    WebDriverWait(driver,12).until(
        lambda d: (
            d.execute_script(
                """
                const c=document.querySelector('#content');
                if(!c)return false;
                const t=(c.innerText||'').trim();
                return t.length>0 && !t.startsWith('Loading');
                """
            )
        )
    )


def current_routes(driver,role):
    routes=driver.execute_script(
        """
        try {
            if(typeof NAV==='undefined' || !NAV[ME.role])return [];
            return NAV[ME.role].map(x=>x[0]);
        } catch (_) {
            return [];
        }
        """
    ) or []

    if role in INTERNAL and "r19Ops" not in routes:
        routes.append("r19Ops")

    return routes


def audit_current_page(
    driver,
    base,
    role,
    route,
    failures,
    stats
):
    text=route_text(driver)

    stats["routes"]+=1

    for marker in ERROR_MARKERS:
        if marker.lower() in text.lower():
            report_failure(
                failures,
                "PAGE_LOAD_ERROR",
                role,
                route,
                marker
            )

    for marker in FORBIDDEN_VISIBLE:
        if marker.lower() in text.lower():
            report_failure(
                failures,
                "LEGACY_DEMO_MARKER",
                role,
                route,
                marker
            )

    handlers=visible_click_handlers(driver)
    stats["visible_handlers"]+=len(handlers)

    missing=undefined_handlers(driver,handlers)

    for item in missing:
        report_failure(
            failures,
            "UNDEFINED_BUTTON_HANDLER",
            role,
            route,
            json.dumps(item,ensure_ascii=False)
        )

    disabled=unexplained_disabled(driver)

    for label in disabled:
        report_failure(
            failures,
            "UNEXPLAINED_DISABLED_BUTTON",
            role,
            route,
            label
        )

    for err in javascript_errors(driver):
        report_failure(
            failures,
            "JAVASCRIPT_ERROR",
            role,
            route,
            err
        )

    for net in performance_5xx(driver,base):
        report_failure(
            failures,
            "HTTP_5XX",
            role,
            route,
            json.dumps(net)
        )


def audit_launcher(
    driver,
    base,
    role,
    failures,
    stats
):
    driver.execute_script("go('menu')")
    wait_route(driver)
    time.sleep(.2)

    count=driver.execute_script(
        """
        return [...document.querySelectorAll(
            '#content .r16-menu-item, #content .module-link'
        )].filter(el=>{
            const r=el.getBoundingClientRect();
            return r.width>0 && r.height>0;
        }).length;
        """
    )

    stats["launcher_links"]+=int(count or 0)

    for index in range(int(count or 0)):

        driver.execute_script("go('menu')")
        wait_route(driver)
        time.sleep(.15)

        links=driver.find_elements(
            By.CSS_SELECTOR,
            "#content .r16-menu-item, #content .module-link"
        )

        visible=[
            x for x in links
            if x.is_displayed()
        ]

        if index>=len(visible):
            continue

        link=visible[index]
        label=(link.text or "").strip()

        clear_browser_logs(driver)

        try:
            driver.execute_script(
                "arguments[0].click()",
                link
            )

            time.sleep(.35)

            modal_text=driver.execute_script(
                """
                const m=document.querySelector('#modalRoot');
                return m ? (m.innerText||'').trim() : '';
                """
            ) or ""

            if modal_text:

                handlers=driver.execute_script(
                    """
                    return [...document.querySelectorAll(
                        '#modalRoot [onclick]'
                    )].map(el=>({
                        text:(el.innerText||'').trim(),
                        onclick:el.getAttribute('onclick')||''
                    }));
                    """
                )

                missing=undefined_handlers(
                    driver,
                    handlers
                )

                for item in missing:
                    report_failure(
                        failures,
                        "LAUNCHER_MODAL_HANDLER",
                        role,
                        "menu",
                        label+" :: "+json.dumps(item)
                    )

                driver.execute_script(
                    """
                    if(typeof closeModal==='function')closeModal();
                    """
                )

            else:
                try:
                    wait_route(driver)
                except Exception:
                    pass

                text=route_text(driver)

                for marker in ERROR_MARKERS:
                    if marker.lower() in text.lower():
                        report_failure(
                            failures,
                            "LAUNCHER_ACTION_ERROR",
                            role,
                            "menu",
                            label+" :: "+marker
                        )

            for err in javascript_errors(driver):
                report_failure(
                    failures,
                    "LAUNCHER_JS_ERROR",
                    role,
                    "menu",
                    label+" :: "+err
                )

            for net in performance_5xx(driver,base):
                report_failure(
                    failures,
                    "LAUNCHER_HTTP_5XX",
                    role,
                    "menu",
                    label+" :: "+json.dumps(net)
                )

        except Exception as exc:
            report_failure(
                failures,
                "LAUNCHER_EXCEPTION",
                role,
                "menu",
                label+" :: "+str(exc)
            )


def main():

    repo=pathlib.Path(sys.argv[1]).resolve()
    evidence=pathlib.Path(sys.argv[2]).resolve()
    chrome=os.environ["ATS_AUDIT_CHROME"]

    evidence.mkdir(parents=True,exist_ok=True)
    screens=evidence/"screenshots"
    screens.mkdir(parents=True,exist_ok=True)

    with tempfile.TemporaryDirectory(
        prefix="ats-r20-browser-"
    ) as td:

        app=pathlib.Path(td)/"app"

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
        base=f"http://127.0.0.1:{port}"

        env=os.environ.copy()

        env.update(
            ATS_ONE_MODE="test",
            ATS_ONE_RESET_AUTHORITY_CONFIRMED="LOCAL_TEST_ONLY",
            SUPABASE_URL="",
            SUPABASE_SERVICE_ROLE_KEY="",
            RENDER_INSTANCE_ID=""
        )

        server_log=(evidence/"server.log").open(
            "w",
            encoding="utf-8"
        )

        proc=subprocess.Popen(
            [
                sys.executable,
                "-u",
                "server.py",
                "--host","127.0.0.1",
                "--port",str(port),
                "--reset",
                "--quiet"
            ],
            cwd=app,
            env=env,
            stdout=server_log,
            stderr=subprocess.STDOUT
        )

        driver=None

        failures=[]
        role_results=[]

        stats={
            "roles":0,
            "routes":0,
            "visible_handlers":0,
            "launcher_links":0
        }

        try:

            if not wait_server(base,proc):
                raise RuntimeError(
                    "ISOLATED_SERVER_NOT_READY"
                )

            print(
                "[PASS] ISOLATED_SERVER_READY",
                flush=True
            )

            options=Options()
            options.binary_location=chrome

            options.add_argument("--headless=new")
            options.add_argument("--disable-gpu")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--window-size=1600,1200")
            options.add_argument("--disable-extensions")
            options.add_argument("--disable-background-networking")

            options.set_capability(
                "goog:loggingPrefs",
                {
                    "browser":"ALL",
                    "performance":"ALL"
                }
            )

            driver=webdriver.Chrome(
                options=options
            )

            wait=WebDriverWait(driver,12)

            for role,email,password in USERS:

                print(
                    f"\n=== ROLE {role.upper()} ===",
                    flush=True
                )

                stats["roles"]+=1

                driver.delete_all_cookies()
                driver.get(base+"/")

                wait.until(
                    EC.presence_of_element_located(
                        (By.ID,"loginForm")
                    )
                )

                # Login DOM can be replaced after initial renderLogin()
                # when boot()/api-me completes. Do not retain stale elements.

                stable_marker=None
                stable_count=0

                for _ in range(80):

                    marker=driver.execute_script(
                        """
                        const form=document.getElementById('loginForm');

                        if(!form){
                            return null;
                        }

                        if(!form.dataset.r20AuditMarker){
                            form.dataset.r20AuditMarker=
                                'r20-'+Date.now()+'-'+
                                Math.random().toString(36).slice(2);
                        }

                        return form.dataset.r20AuditMarker;
                        """
                    )

                    if marker and marker==stable_marker:
                        stable_count+=1
                    else:
                        stable_marker=marker
                        stable_count=0

                    if stable_marker and stable_count>=4:
                        break

                    time.sleep(.10)

                if not stable_marker or stable_count<4:
                    report_failure(
                        failures,
                        "LOGIN_FORM_NOT_STABLE",
                        role,
                        "login",
                        email
                    )
                    continue

                clear_browser_logs(driver)

                submitted=driver.execute_script(
                    """
                    const form=document.getElementById('loginForm');

                    if(!form){
                        return false;
                    }

                    const emailInput=form.querySelector(
                        'input[name="email"]'
                    );

                    const passwordInput=form.querySelector(
                        'input[name="password"]'
                    );

                    const submitButton=form.querySelector(
                        'button[type="submit"],button'
                    );

                    if(
                        !emailInput ||
                        !passwordInput ||
                        !submitButton
                    ){
                        return false;
                    }

                    emailInput.value=arguments[0];
                    passwordInput.value=arguments[1];

                    emailInput.dispatchEvent(
                        new Event(
                            'input',
                            {bubbles:true}
                        )
                    );

                    passwordInput.dispatchEvent(
                        new Event(
                            'input',
                            {bubbles:true}
                        )
                    );

                    submitButton.click();

                    return true;
                    """,
                    email,
                    password
                )

                if not submitted:
                    report_failure(
                        failures,
                        "LOGIN_FORM_ATOMIC_SUBMIT_FAILED",
                        role,
                        "login",
                        email
                    )
                    continue

                try:
                    wait.until(
                        EC.presence_of_element_located(
                            (By.CSS_SELECTOR,".app-shell")
                        )
                    )
                except Exception:
                    report_failure(
                        failures,
                        "LOGIN_UI_FAILED",
                        role,
                        "login",
                        email
                    )
                    continue

                actual_role=driver.execute_script(
                    """
                    try{
                        return typeof ME!=='undefined'
                            ? ME.role
                            : null;
                    }catch(_){
                        return null;
                    }
                    """
                )

                if actual_role!=role:
                    report_failure(
                        failures,
                        "ROLE_IDENTITY_MISMATCH",
                        role,
                        "login",
                        f"actual={actual_role}"
                    )
                    continue

                print(
                    f"[PASS] LOGIN_{role.upper()}",
                    flush=True
                )

                routes=current_routes(
                    driver,
                    role
                )

                role_record={
                    "role":role,
                    "routes":routes,
                    "route_count":len(routes)
                }

                role_results.append(role_record)

                for index,route in enumerate(routes):

                    clear_browser_logs(driver)

                    try:

                        driver.execute_script(
                            "go(arguments[0])",
                            route
                        )

                        wait_route(driver)
                        time.sleep(.2)

                        audit_current_page(
                            driver,
                            base,
                            role,
                            route,
                            failures,
                            stats
                        )

                        print(
                            f"[PASS] ROUTE_{role}_{route}",
                            flush=True
                        )

                        if index==0:
                            driver.save_screenshot(
                                str(
                                    screens/
                                    f"{role}-home.png"
                                )
                            )

                    except Exception as exc:

                        report_failure(
                            failures,
                            "ROUTE_EXCEPTION",
                            role,
                            route,
                            str(exc)
                        )

                        try:
                            driver.save_screenshot(
                                str(
                                    screens/
                                    f"FAIL-{role}-{route}.png"
                                )
                            )
                        except Exception:
                            pass

                if role in INTERNAL:
                    audit_launcher(
                        driver,
                        base,
                        role,
                        failures,
                        stats
                    )

            # ----------------------------------------------------------
            # REPORT
            # ----------------------------------------------------------

            report={
                "stats":stats,
                "roles":role_results,
                "failures":failures
            }

            (evidence/"R20-BROWSER-AUDIT.json").write_text(
                json.dumps(
                    report,
                    indent=2,
                    ensure_ascii=False
                ),
                encoding="utf-8"
            )

            lines=[
                "# ATS-One R20 Browser Role/Button Audit",
                "",
                f"- Roles: {stats['roles']}",
                f"- Routes audited: {stats['routes']}",
                f"- Visible onclick handlers inspected: {stats['visible_handlers']}",
                f"- Launcher links exercised: {stats['launcher_links']}",
                f"- Failures: {len(failures)}",
                "",
            ]

            if failures:
                lines.append("## Failures")
                lines.append("")

                for item in failures:
                    lines.append(
                        "- "
                        +item["kind"]
                        +" | "
                        +item["role"]
                        +" | "
                        +item["route"]
                        +" | "
                        +item["detail"]
                    )
            else:
                lines += [
                    "## Result",
                    "",
                    "BROWSER_ROLE_AUDIT=PASS",
                    "UNDEFINED_BUTTON_HANDLERS=0",
                    "UNEXPLAINED_DISABLED_BUTTONS=0",
                    "HTTP_5XX=0",
                    "JAVASCRIPT_ERRORS=0",
                    "LEGACY_DEMO_MARKERS=0",
                ]

            (evidence/"R20-BROWSER-AUDIT.md").write_text(
                "\n".join(lines).rstrip()+"\n",
                encoding="utf-8"
            )

            print("")
            print("========================================")
            print(" R20 BROWSER AUDIT RESULT")
            print("========================================")
            print(f"ROLES_AUDITED={stats['roles']}")
            print(f"ROUTES_AUDITED={stats['routes']}")
            print(
                "VISIBLE_BUTTON_HANDLERS="
                +str(stats["visible_handlers"])
            )
            print(
                "LAUNCHER_LINKS_EXERCISED="
                +str(stats["launcher_links"])
            )
            print(f"FAILURES={len(failures)}")

            if failures:
                print("BROWSER_ROLE_AUDIT=FAIL")
                return 1

            print("BROWSER_ROLE_AUDIT=PASS")
            print("UNDEFINED_BUTTON_HANDLERS=0")
            print("UNEXPLAINED_DISABLED_BUTTONS=0")
            print("HTTP_5XX=0")
            print("JAVASCRIPT_ERRORS=0")
            print("LEGACY_DEMO_MARKERS=0")

            return 0

        except Exception:
            traceback.print_exc()
            return 2

        finally:

            if driver is not None:
                try:
                    driver.quit()
                except Exception:
                    pass

            if proc.poll() is None:
                proc.terminate()

                try:
                    proc.wait(timeout=8)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=5)

            server_log.close()


if __name__=="__main__":
    raise SystemExit(main())
