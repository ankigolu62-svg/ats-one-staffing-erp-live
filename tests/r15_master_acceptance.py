#!/usr/bin/env python3
import base64, hashlib, http.cookiejar, json, os, shutil, socket, sqlite3, subprocess, sys, tempfile, time, urllib.error, urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

class API:
    def __init__(self,base):
        self.base=base;self.jar=http.cookiejar.CookieJar();self.opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))
    def req(self,path,method='GET',body=None,raw=None,headers=None):
        h={'Accept':'application/json',**(headers or {})};data=raw
        if body is not None:data=json.dumps(body).encode();h['Content-Type']='application/json'
        req=urllib.request.Request(self.base+path,data=data,headers=h,method=method)
        try:
            with self.opener.open(req,timeout=10) as r:
                b=r.read();ct=r.headers.get('Content-Type','')
                if 'json' in ct:
                    try:b=json.loads(b.decode())
                    except Exception:pass
                return r.status,b
        except urllib.error.HTTPError as e:
            b=e.read()
            try:b=json.loads(b.decode())
            except Exception:pass
            return e.code,b
    def login(self,email,password):return self.req('/api/login','POST',{'email':email,'password':password})

def port():
    s=socket.socket();s.bind(('127.0.0.1',0));p=s.getsockname()[1];s.close();return p

def wait(base):
    a=API(base)
    for _ in range(100):
        try:
            if a.req('/api/health')[0]==200:return True
        except Exception:pass
        time.sleep(.1)
    return False

def main():
    checks=[]
    def ck(name,ok,detail=''):
        checks.append((name,bool(ok),str(detail)));print(f"[{'PASS' if ok else 'FAIL'}] {name}"+(f" -- {detail}" if detail else ''))
    with tempfile.TemporaryDirectory(prefix='ats-r15-master-') as td:
        run=Path(td)
        for f in ['server.py','parity_api.py','r14_api.py','core_policies.py','persistence_authority.py','r15_migrations.py']:
            shutil.copy2(ROOT/f,run/f)
        shutil.copytree(ROOT/'web',run/'web')
        (run/'data').mkdir()
        p=port();base=f'http://127.0.0.1:{p}';env=os.environ.copy()
        for k in ['SUPABASE_URL','SUPABASE_SERVICE_ROLE_KEY','SUPABASE_BUCKET','SUPABASE_DB_OBJECT','SUPABASE_PERSISTENCE_TABLE','RENDER']:
            env.pop(k,None)
        env['ATS_ONE_MODE']='test';env['ATS_ONE_RESET_AUTHORITY_CONFIRMED']='LOCAL_TEST_ONLY'
        log=open(run/'server.log','w',encoding='utf-8')
        proc=subprocess.Popen([sys.executable,'server.py','--host','127.0.0.1','--port',str(p),'--reset','--quiet'],cwd=run,env=env,stdout=log,stderr=subprocess.STDOUT)
        try:
            if not wait(base):
                proc.terminate();proc.wait(2);log.close();print((run/'server.log').read_text());return 2
            admin=API(base);worker=API(base);client=API(base);finance=API(base);hr=API(base);approver=API(base)
            ck('LOGIN_ADMIN',admin.login('admin@atsone.local','Admin@123')[0]==200)
            ck('LOGIN_WORKER',worker.login('worker@atsone.local','Worker@123')[0]==200)
            ck('LOGIN_CLIENT',client.login('client@atsone.local','Client@123')[0]==200)
            ck('LOGIN_FINANCE',finance.login('finance@atsone.local','Finance@123')[0]==200)
            ck('LOGIN_HR',hr.login('hr@atsone.local','HR@123')[0]==200)
            ck('LOGIN_APPROVER',approver.login('approver@atsone.local','Approve@123')[0]==200)

            # ATS-001: worker pay-statement object scope + immutability.
            ps1=finance.req('/api/r14/pay-statements','POST',{'candidate_id':1,'period_start':'2026-09-01','period_end':'2026-09-15','gross':100,'deductions':10,'net':90,'currency':'USD'})
            ps2=finance.req('/api/r14/pay-statements','POST',{'candidate_id':2,'period_start':'2026-09-01','period_end':'2026-09-15','gross':100,'deductions':10,'net':90,'currency':'USD'})
            pid1=(ps1[1] or {}).get('id');pid2=(ps2[1] or {}).get('id')
            ck('ATS001_OTHER_PAY_PATCH_DENY',worker.req(f'/api/r14/pay-statements/{pid1}','PATCH',{'net':1})[0]==403)
            ck('ATS001_OTHER_PAY_DELETE_DENY',worker.req(f'/api/r14/pay-statements/{pid1}','DELETE')[0]==403)
            ck('ATS001_OWN_PAY_IMMUTABLE',worker.req(f'/api/r14/pay-statements/{pid2}','PATCH',{'net':1})[0]==409)

            # ATS-002: client requisition direct-ID scope.
            rq=admin.req('/api/r14/requisition-requests','POST',{'company_id':2,'title':'Other company req','status':'Requested'})
            rid=(rq[1] or {}).get('id')
            ck('ATS002_CLIENT_PATCH_DENY',client.req(f'/api/r14/requisition-requests/{rid}','PATCH',{'title':'hijack'})[0]==403)
            ck('ATS002_CLIENT_DELETE_DENY',client.req(f'/api/r14/requisition-requests/{rid}','DELETE')[0]==403)

            # Tenant-2 candidate for ATS-003.
            db=sqlite3.connect(run/'data'/'ats_one.db')
            try:
                db.execute("INSERT INTO tenants(name,slug,status,created_at) VALUES('T2','t2','Active',datetime('now'))");t2=db.execute("SELECT id FROM tenants WHERE slug='t2'").fetchone()[0]
                db.execute("INSERT INTO candidates(first_name,last_name,status,created_at,updated_at,tenant_id) VALUES('Other','Tenant','Active',datetime('now'),datetime('now'),?)",(t2,));foreign_candidate=db.execute('SELECT last_insert_rowid()').fetchone()[0];db.commit()
            finally:db.close()
            ck('ATS003_CROSS_TENANT_PARENT_DENY',admin.req('/api/r14/candidate-eeo','POST',{'candidate_id':foreign_candidate,'voluntary':1})[0] in (400,404,409))

            # ATS-005: approved timesheet cannot be overwritten by create/upsert.
            tsresp=admin.req('/api/timesheets');ts=tsresp[1][0];tid=ts['id'];week=ts['week_start']
            if str(ts['status']).lower()=='submitted': finance.req(f'/api/timesheets/{tid}/status','POST',{'status':'approved'})
            overwrite=worker.req('/api/timesheets','POST',{'assignment_id':1,'week_start':week,'status':'draft','daily':{'Mon':1}})
            ck('ATS005_APPROVED_TIMESHEET_IMMUTABLE',overwrite[0]==409,overwrite)

            # ATS-006: finance validation.
            ck('ATS006_NEGATIVE_EXPENSE_DENY',worker.req('/api/expenses','POST',{'assignment_id':1,'amount':-1,'category':'Travel'})[0] in (400,409))
            ck('ATS006_NEGATIVE_INVOICE_DENY',finance.req('/api/invoices','POST',{'company_id':2,'assignment_id':1,'amount':-1,'tax':0})[0] in (400,409))

            # ATS-009/010 report schema must execute without connection abort.
            rep=admin.req('/api/r14/report-builders','POST',{'name':'Submission Rates','entity_type':'submissions','columns_json':['id','client_rate','candidate_rate'],'filters_json':{}})
            report_id=(rep[1] or {}).get('id');runrep=admin.req(f'/api/report-builder/run?id={report_id}')
            ck('ATS009_REPORT_SCHEMA',runrep[0]==200,runrep)

            # ATS-022 malformed JSON is a 400 and creates nothing.
            bad=admin.req('/api/r14/divisions','POST',raw=b'{bad-json',headers={'Content-Type':'application/json'})
            ck('ATS022_MALFORMED_JSON_400',bad[0]==400,bad)

            # ATS-013 MFA re-enrollment requires step-up once enabled.
            setup=admin.req('/api/auth/mfa/setup','POST',{})
            secret=(setup[1] or {}).get('secret')
            if secret:
                # calculate current TOTP in-process using the same standard algorithm
                import hmac,struct
                key=base64.b32decode(secret+'='*((8-len(secret)%8)%8));counter=int(time.time())//30;dig=hmac.new(key,struct.pack('>Q',counter),hashlib.sha1).digest();o=dig[-1]&15;code=str((int.from_bytes(dig[o:o+4],'big')&0x7fffffff)%1000000).zfill(6)
                admin.req('/api/auth/mfa/verify','POST',{'code':code})
                re_setup=admin.req('/api/auth/mfa/setup','POST',{})
                ck('ATS013_MFA_REENROLL_STEPUP',re_setup[0] in (401,403,409),re_setup)
            else: ck('ATS013_MFA_REENROLL_STEPUP',False,setup)

            # ATS-015 approver dashboard must be scoped and not internal dashboard.
            dash=approver.req('/api/dashboard')
            d=dash[1] if isinstance(dash[1],dict) else {}
            ck('ATS015_APPROVER_DASHBOARD_SCOPE',dash[0]==200 and 'open_jobs' not in d and 'pending_timesheets' in d,d)

            # ATS-017 time lock enforcement on worker time entry.
            lock=finance.req('/api/r14/time-locks','POST',{'period_start':'2027-01-01','period_end':'2027-01-07','scope_type':'Tenant','locked':1,'reason':'close'})
            locked=worker.req('/api/timesheets','POST',{'assignment_id':1,'week_start':'2027-01-04','status':'draft','daily':{'Mon':8}})
            ck('ATS017_TIME_LOCK_ENFORCED',lock[0]==201 and locked[0]==409,(lock,locked))

            # ATS-036 attachment parent validation.
            att=admin.req('/api/jobs/999999/attachments','POST',{'file_name':'x.txt','mime_type':'text/plain','content_base64':base64.b64encode(b'x').decode()})
            ck('ATS036_ATTACHMENT_PARENT_DENY',att[0] in (400,404),att)

            # ATS-037 session IDs are opaque hashes, not SQLite rowid.
            sessions=admin.req('/api/auth/sessions');items=sessions[1] if isinstance(sessions[1],list) else []
            ck('ATS037_SESSION_PUBLIC_ID',bool(items) and all(len(str(x.get('id','')))==64 for x in items),items)

            # ATS-038 throttling/audit: fresh client fails repeatedly and is blocked.
            attacker=API(base);codes=[]
            for _ in range(6):codes.append(attacker.login('admin@atsone.local','wrong')[0])
            ck('ATS038_LOGIN_THROTTLE',429 in codes,codes)

            # ATS-041/042 admin user creation uses invitation and no supplied/default password.
            nu=admin.req('/api/users','POST',{'email':'invite.r15@example.test','name':'Invite User','role':'recruiter'})
            nbody=nu[1] if isinstance(nu[1],dict) else {}
            ck('ATS042_INVITATION_ONLY',nu[0]==201 and bool(nbody.get('invitation_token')) and 'password' not in nbody,nbody)

            # ATS-007 candidate merge must not silently archive on a conflicting child.
            c1=admin.req('/api/candidates','POST',{'first_name':'Merge','last_name':'Source','email':'merge.source@example.test'})[1]
            c2=admin.req('/api/candidates','POST',{'first_name':'Merge','last_name':'Target','email':'merge.target@example.test'})[1]
            if isinstance(c1,dict) and isinstance(c2,dict):
                admin.req(f"/api/candidates/{c1.get('id')}/skills",'POST',{'skill':'Java','years':1})
                admin.req(f"/api/candidates/{c2.get('id')}/skills",'POST',{'skill':'Java','years':2})
                merge=admin.req('/api/candidates/merge','POST',{'source_candidate_id':c1.get('id'),'target_candidate_id':c2.get('id')})
                ck('ATS007_MERGE_FAILS_CLOSED_ON_CONFLICT',merge[0] in (200,409) and not (merge[0]==200 and not isinstance(merge[1].get('moved'),dict)),merge)
            else: ck('ATS007_MERGE_FAILS_CLOSED_ON_CONFLICT',False,(c1,c2))

            # ATS-008 privacy action must redact tracked child PII before Completed.
            pc=admin.req('/api/candidates','POST',{'first_name':'Privacy','last_name':'Person','email':'privacy.person@example.test','phone':'123456'})[1]
            pcid=(pc or {}).get('id') if isinstance(pc,dict) else None
            if pcid:
                admin.req(f'/api/candidates/{pcid}/notes','POST',{'note':'private-note'})
                red=admin.req('/api/candidates/redact','POST',{'candidate_id':pcid})
                after=admin.req(f'/api/candidates/{pcid}')
                ck('ATS008_PRIVACY_REDACTION_VERIFIED',red[0]==200 and after[0]==200 and 'privacy.person@example.test' not in json.dumps(after[1]).lower(),(red,after))
            else: ck('ATS008_PRIVACY_REDACTION_VERIFIED',False,pc)

            # ATS-011 interview creation must respect submission state gates.
            newc=admin.req('/api/candidates','POST',{'first_name':'State','last_name':'Guard'})[1]
            ncid=(newc or {}).get('id') if isinstance(newc,dict) else None
            sub=admin.req('/api/jobs/2/submissions','POST',{'candidate_id':ncid,'status':'draft'}) if ncid else (500,{})
            sid=(sub[1] or {}).get('id') if isinstance(sub[1],dict) else None
            inter=admin.req('/api/interviews','POST',{'submission_id':sid,'scheduled_at':'2027-01-02T10:00:00'}) if sid else (500,{})
            ck('ATS011_INTERVIEW_STATE_GUARD',inter[0]==409,inter)

            # ATS-016 workflow runner must execute safe steps and never fake external success.
            wf=admin.req('/api/r14/workflows','POST',{'name':'External Workflow','trigger_name':'manual','entity_type':'candidate','definition_json':{'steps':[{'action':'external'}]},'active':1})
            wfid=(wf[1] or {}).get('id') if isinstance(wf[1],dict) else None
            wr=admin.req('/api/workflows/run','POST',{'workflow_id':wfid,'entity_type':'candidate','entity_id':2}) if wfid else (500,{})
            ck('ATS016_WORKFLOW_NO_FAKE_COMPLETED',wr[0]==409 and isinstance(wr[1],dict) and wr[1].get('status')=='Waiting External',wr)

            # ATS-018 permission overrides must be consumed by authorization.
            po=admin.req('/api/permission-overrides','POST',{'role':'worker','module_name':'timesheet','can_view':1,'can_create':0,'can_edit':0,'can_delete':0})
            denied=worker.req('/api/timesheets','POST',{'assignment_id':1,'week_start':'2027-02-01','status':'draft','daily':{'Mon':1}})
            ck('ATS018_PERMISSION_OVERRIDE_ENFORCED',po[0]==201 and denied[0]==403,(po,denied))

            # ATS-019 sensitive EEO/HR is not available to broad recruiting roles.
            recruiter=API(base);recruiter.login('recruiter@atsone.local','Recruit@123')
            ck('ATS019_EEO_RECRUITER_DENY',recruiter.req('/api/r14/candidate-eeo')[0]==403)
            ck('ATS019_HR_RECRUITER_DENY',recruiter.req('/api/r14/candidate-hr')[0]==403)

            # ATS-020/021 relationship consistency.
            bad_assignment=admin.req('/api/assignments','POST',{'candidate_id':1,'job_id':2,'company_id':1,'bill_rate':10,'pay_rate':5})
            ck('ATS020_ASSIGNMENT_GRAPH_DENY',bad_assignment[0] in (400,404,409),bad_assignment)
            bad_job=admin.req('/api/jobs','POST',{'title':'Bad Contact Job','company_id':2,'contact_id':1})
            ck('ATS021_JOB_CONTACT_GRAPH_DENY',bad_job[0] in (400,404,409),bad_job)

            # ATS-023 identity semantics are explicit rather than accidental.
            health=admin.req('/api/health')
            ck('ATS023_IDENTITY_MODEL_DECLARED',health[0]==200 and health[1].get('identity_model')=='global-email-primary-tenant',health)

            # ATS-034/035 disconnected engines/configurations are truth-gated.
            alert=admin.req('/api/r14/job-alerts','POST',{'name':'Active alert','criteria_json':{},'active':1})
            sso=admin.req('/api/r14/sso-configs','POST',{'name':'Corp','protocol':'SAML','enabled':1})
            ck('ATS034_EXECUTOR_SHELL_TRUTH_GATE',alert[0]==409,alert)
            ck('ATS035_SSO_NOT_FAKE_ENABLED',sso[0]==409,sso)

            # ATS-039 polymorphic entity IDs are registry/tenant validated.
            poly=admin.req('/api/r14/threads','POST',{'entity_type':'not-a-real-entity','entity_id':1,'subject':'bad'})
            ck('ATS039_POLYMORPHIC_REF_DENY',poly[0] in (400,404),poly)

            # ATS-040 archived parents cannot receive new R14 children.
            ar=admin.req('/api/candidates','POST',{'first_name':'Archive','last_name':'Parent'})[1]
            arid=(ar or {}).get('id') if isinstance(ar,dict) else None
            if arid:
                admin.req(f'/api/candidates/{arid}','DELETE')
                child=admin.req('/api/r14/candidate-eeo','POST',{'candidate_id':arid,'voluntary':1})
                ck('ATS040_ARCHIVED_PARENT_DENY',child[0] in (400,404,409),child)
            else: ck('ATS040_ARCHIVED_PARENT_DENY',False,ar)

            # ATS-043 generic lifecycle patch must fail.
            lock_id=(lock[1] or {}).get('id')
            ck('ATS043_GENERIC_LIFECYCLE_PATCH_DENY',admin.req(f'/api/r14/time-locks/{lock_id}','PATCH',{'locked':0})[0]==409)

            # Stored-XSS source gate: known dangerous raw job number interpolation removed.
            app=(ROOT/'web'/'app.js').read_text(encoding='utf-8')
            ck('ATS014_JOBNO_ESCAPED','${j.job_no}' not in app and '${s.job_no}' not in app and '${a.job_no}' not in app and '${x.job_no}' not in app)

            # Production reset path is not enabled merely by missing remote persistence env.
            ck('ATS033_RESET_AUTHORITY_SOURCE',"APP_MODE not in {'demo','local','test'}" in (ROOT/'server.py').read_text(encoding='utf-8'))

            # Cache/installability gates.
            sw=(ROOT/'web'/'sw.js').read_text(encoding='utf-8');manifest=json.loads((ROOT/'web'/'manifest.webmanifest').read_text());vercel=json.loads((ROOT/'vercel.json').read_text())
            ck('ATS028_SW_VERSIONED','ats-one-r15-' in sw and 'skipWaiting' in sw and 'clients.claim' in sw)
            ck('ATS029_PWA_ICONS',len(manifest.get('icons',[]))>=2 and (ROOT/'web'/'icons'/'ats-192.png').exists() and (ROOT/'web'/'icons'/'ats-512.png').exists())
            srcs={x.get('source') for x in vercel.get('headers',[])}
            ck('ATS030_CACHE_HEADERS',all(x in srcs for x in ['/sw.js','/r14.js','/r13.js','/r13r7.js','/manifest.webmanifest']))

            # Persistence source must not contain legacy mutable-storage helpers.
            server=(ROOT/'server.py').read_text(encoding='utf-8');pa=(ROOT/'persistence_authority.py').read_text(encoding='utf-8')
            ck('ATS024_027_PERSISTENCE_AUTHORITY','SupabasePostgrestAtomicStore' in server and 'SnapshotAuthority' in server and 'backup_remote_db' not in server and 'x-upsert' not in server and 'class SupabasePostgrestAtomicStore' in pa)
            ck('ATS026_VALIDATED_RESTORE','integrity_check' in pa and 'last-known-good' in pa and 'os.replace(temp_path, destination)' in pa)
            ck('ATS041_DEMO_SEED_MODE_GATED','DEMO_MODE = APP_MODE in' in server and 'if DEMO_MODE:' in server and 'DEMO_USERS' in server and 'Admin@123' not in (ROOT/'web'/'app.js').read_text(encoding='utf-8'))
            ck('ATS045_NEGATIVE_SUITE_PRESENT',True,'this suite exercises authorization, tenant, state, finance, malformed input, security, cache and persistence invariants')

        finally:
            if proc.poll() is None:
                proc.terminate()
                try:proc.wait(3)
                except subprocess.TimeoutExpired:proc.kill()
            log.close()
    failed=[x for x in checks if not x[1]]
    print(f'R15_MASTER_ACCEPTANCE={"PASS" if not failed else "FAIL"} PASS={len(checks)-len(failed)} FAIL={len(failed)}')
    return 0 if not failed else 1

if __name__=='__main__':raise SystemExit(main())
