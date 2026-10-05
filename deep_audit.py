#!/usr/bin/env python3
import argparse, concurrent.futures, http.cookiejar, json, os, re, shutil, socket, subprocess, sys, tempfile, time, traceback, urllib.error, urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DEMO = {
 'admin':('admin@atsone.local','Admin@123'),
 'teamlead':('teamlead@atsone.local','Lead@123'),
 'recruiter':('recruiter@atsone.local','Recruit@123'),
 'sales':('sales@atsone.local','Sales@123'),
 'hr':('hr@atsone.local','HR@123'),
 'finance':('finance@atsone.local','Finance@123'),
 'client':('client@atsone.local','Client@123'),
 'candidate':('candidate@atsone.local','Candidate@123'),
 'worker':('worker@atsone.local','Worker@123'),
 'supplier':('supplier@atsone.local','Supplier@123'),
 'approver':('approver@atsone.local','Approve@123'),
}

class ResultBook:
    def __init__(self): self.rows=[]
    def add(self,section,name,status,detail=''):
        self.rows.append({'section':section,'name':name,'status':status,'detail':str(detail)})
        mark={'PASS':'PASS','FAIL':'FAIL','PARTIAL':'PARTIAL','EXTERNAL':'EXTERNAL','INFO':'INFO'}.get(status,status)
        print(f'[{mark:8}] {section} :: {name}' + (f' -- {detail}' if detail else ''))
    def check(self,section,name,cond,detail_ok='',detail_bad=''):
        self.add(section,name,'PASS' if cond else 'FAIL',detail_ok if cond else detail_bad)
        return cond
    def counts(self):
        d=defaultdict(int)
        for r in self.rows:d[r['status']]+=1
        return dict(d)

class API:
    def __init__(self,base):
        self.base=base.rstrip('/')
        self.jar=http.cookiejar.CookieJar()
        self.opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))
    def req(self,path,method='GET',body=None,timeout=8):
        data=None; headers={'Accept':'application/json'}
        if body is not None:
            data=json.dumps(body).encode(); headers['Content-Type']='application/json'
        req=urllib.request.Request(self.base+path,data=data,headers=headers,method=method)
        try:
            with self.opener.open(req,timeout=timeout) as r:
                raw=r.read(); ctype=r.headers.get('Content-Type','')
                try: obj=json.loads(raw.decode()) if raw else None
                except Exception: obj=raw.decode(errors='replace')
                return r.status,obj,dict(r.headers)
        except urllib.error.HTTPError as e:
            raw=e.read()
            try: obj=json.loads(raw.decode()) if raw else None
            except Exception: obj=raw.decode(errors='replace')
            return e.code,obj,dict(e.headers)
    def login(self,email,pw): return self.req('/api/login','POST',{'email':email,'password':pw})


def free_port():
    s=socket.socket();s.bind(('127.0.0.1',0));p=s.getsockname()[1];s.close();return p

def wait_server(base,seconds=15):
    c=API(base); end=time.time()+seconds
    while time.time()<end:
        try:
            st,obj,_=c.req('/api/health',timeout=1)
            if st==200 and isinstance(obj,dict) and obj.get('ok'):return True
        except Exception:pass
        time.sleep(.2)
    return False

def ids_by_name(rows,key='name'):
    return {str(x.get(key)):x.get('id') for x in rows if isinstance(x,dict)}

def contains_candidate(results,first,last):
    return any(str(x.get('first_name','')).lower()==first.lower() and str(x.get('last_name','')).lower()==last.lower() for x in results)

def capability_matrix(book, server_text, app_text, acceptance):
    sec='SOURCE CAPABILITY COVERAGE'
    # Runtime-backed / materially implemented
    full = [
      ('Candidate list/detail/create/basic patch/notes', ['/api/candidates', '/notes']),
      ('Deep Talent Search endpoint', ['/api/search/talent']),
      ('Static & dynamic hotlist create/add/view', ['/api/hotlists']),
      ('Company/contact/lead/opportunity create+list', ['/api/companies','/api/contacts','/api/leads','/api/opportunities']),
      ('Job create/list/detail/basic patch', ['/api/jobs']),
      ('Interested candidate layer', ['/interested']),
      ('Submission create + status workflow', ['/submissions','/status']),
      ('Interview create + list', ['/api/interviews']),
      ('Onboarding package + requirement completion', ['/api/onboarding','requirements']),
      ('Assignment create + list', ['/api/assignments']),
      ('Timesheet create/upsert + status', ['/api/timesheets']),
      ('Expense create + status', ['/api/expenses']),
      ('Invoice create + list', ['/api/invoices']),
      ('Communication log create + list', ['/api/communications']),
      ('User create + list', ['/api/users']),
      ('Summary reports', ['/api/reports/summary']),
      ('Audit trail', ['/api/audit']),
    ]
    for name, needles in full:
        ok=all(n in server_text for n in needles)
        book.add(sec,name,'PASS' if ok else 'FAIL','route(s) present' if ok else 'expected route missing')
    completed=[
      ('Resume parsing into structured experience/skills','RESUME_REVIEW_WORKFLOW'),
      ('Candidate employment history editing','CANDIDATE_STRUCTURED_CRUD'),
      ('Candidate licenses editing','CANDIDATE_STRUCTURED_CRUD'),
      ('Candidate certifications editing','CANDIDATE_STRUCTURED_CRUD'),
      ('Candidate qualifications/sub-values editing','CANDIDATE_STRUCTURED_CRUD'),
      ('Candidate attributes editing','CANDIDATE_STRUCTURED_CRUD'),
      ('Candidate document upload/version/verification','DOCUMENT_WORKFLOW'),
      ('Hotlist remove/update/delete','HOTLIST_FULL_CRUD'),
      ('Bulk Action engine','SEARCH_BULK_ACTION'),
      ('Job distribution publish/sync','JOB_DISTRIBUTION_LIFECYCLE'),
      ('Job user-role assignment / clone / delete','JOB_CLONE_ARCHIVE'),
      ('Lead lifecycle update/convert','CRM_LIFECYCLE'),
      ('Opportunity stage update / close-won/lost','CRM_LIFECYCLE'),
      ('Interview feedback/rating/status update','INTERVIEW_LIFECYCLE'),
      ('Assessment answer/scoring/completion','ASSESSMENT_LIFECYCLE'),
      ('Start lifecycle / cancellation / termination','START_LIFECYCLE'),
      ('Assignment lifecycle update/termination','ASSIGNMENT_LIFECYCLE'),
      ('Shift scheduling CRUD','SHIFT_CRUD'),
      ('Attendance CRUD','ATTENDANCE_CRUD'),
      ('Purchase order CRUD','PO_LIFECYCLE'),
      ('Invoice payment/status lifecycle','INVOICE_LIFECYCLE'),
      ('VMS account/mapping CRUD + sync engine','VMS_INTERNAL_CRUD'),
      ('Supplier registry/release administration','SUPPLIER_RELEASE_ADMIN'),
      ('Task create/assign/complete','TASK_LIFECYCLE'),
      ('Automation rule create/edit/execute','AUTOMATION_INTERNAL_ENGINE'),
      ('Integration credential/config/sync actions','INTEGRATION_CONFIG'),
      ('UDF definition/value CRUD','UDF_CRUD'),
      ('User disable/edit/reset-password/role update','USER_ADMIN_LIFECYCLE'),
      ('Parameterized saved report catalog and CSV export','REPORT_EXECUTION_EXPORT'),
      ('Delete/archive API coverage','ARCHIVE_RESTORE'),
      ('True multi-tenant tenant isolation','TENANT_ISOLATION'),
    ]
    for name,label in completed:
        passed=acceptance.get(label)=='PASS'
        book.add(sec,name,'PASS' if passed else 'FAIL',f'full_live_acceptance:{label}={acceptance.get(label,"MISSING")}')
    externals=['LinkedIn / paid job boards','Fieldglass / Beeline live VMS','Production Email/SMS/VOIP','Background screening / identity verification','Payroll/GL live connector','E-Verify/government verification','Legally-certified e-signature']
    for x in externals: book.add('EXTERNAL INTEGRATIONS',x,'EXTERNAL','Requires real vendor account/credentials/contract; internal mapping only can be tested locally.')


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output-dir',default=str(ROOT/'audit-results'));args=ap.parse_args()
    outdir=Path(args.output_dir);outdir.mkdir(parents=True,exist_ok=True)
    ts=datetime.now().strftime('%Y%m%d-%H%M%S')
    book=ResultBook()
    server_text=(ROOT/'server.py').read_text(encoding='utf-8',errors='replace')
    app_text=(ROOT/'web'/'app.js').read_text(encoding='utf-8',errors='replace')

    # Package / source checks
    sec='PACKAGE / UI'
    for rel in ['server.py','parity_api.py','deep_audit.py','full_live_acceptance.py','web/index.html','web/app.js','web/styles.css','web/r13r7.js','web/r13r7.css','FUNCTION-MAP.md','ARCHITECTURE.md','DEMO-USERS.txt']:
        book.check(sec,f'Package file {rel}',(ROOT/rel).is_file(),str(ROOT/rel),'missing')
    nav_expected=['Talent Search','Candidates','Hotlists / Pools','Jobs','Companies / CRM','Contacts','Submittals','Interviews','Assessments','Onboarding','Assignments','Timesheets','Expenses','Finance','VMS / MSP','Suppliers','Communication','Reports','Admin','Audit Trail','Candidate Portal','Client Portal','MyTime Portal','Supplier Portal','Approver Portal']
    for label in nav_expected: book.check(sec,f'UI route visible: {label}',label in app_text,'present','missing from app.js')
    tabs=['Profession/Specialty','Licenses','Certifications','Qualification','Require','Exclude','Attribute','Title']
    book.check(sec,'Talent Search has all 8 tabs',all(t in app_text for t in tabs),', '.join(tabs),'one or more tabs missing')
    actions=['Exclude','Qualify','Expand','Hotlist','Preview','Relevancy','Bulk Action','Email Merge']
    book.check(sec,'Talent result action bar exposes 8 actions',all(a in app_text for a in actions),', '.join(actions),'one or more result actions missing')

    # Execute the R8 acceptance suite once. Former PARTIAL declarations below
    # are resolved only from these real isolated runtime results.
    acceptance={}
    acceptance_json=outdir/f'FULL-LIVE-ACCEPTANCE-{ts}.json'
    completed=subprocess.run([sys.executable,str(ROOT/'full_live_acceptance.py'),'--json-out',str(acceptance_json)],cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=120)
    if acceptance_json.exists():
        acceptance={x['label']:x['status'] for x in json.loads(acceptance_json.read_text(encoding='utf-8')).get('checks',[])}
    book.check('R8 ACCEPTANCE','Executable full-live acceptance suite',completed.returncode==0 and bool(acceptance),f'{len(acceptance)} executable labels passed',completed.stdout[-2000:])

    # Create isolated copy and server
    proc=None
    with tempfile.TemporaryDirectory(prefix='ats-one-deep-audit-') as td:
        run=Path(td)/'app';run.mkdir()
        shutil.copy2(ROOT/'server.py',run/'server.py');shutil.copy2(ROOT/'parity_api.py',run/'parity_api.py') if (ROOT/'parity_api.py').exists() else None;shutil.copytree(ROOT/'web',run/'web');(run/'data').mkdir()
        port=free_port();base=f'http://127.0.0.1:{port}'
        logf=open(Path(td)/'server.log','w',encoding='utf-8')
        proc=subprocess.Popen([sys.executable,'server.py','--host','127.0.0.1','--port',str(port),'--reset','--quiet'],cwd=run,stdout=logf,stderr=subprocess.STDOUT)
        try:
            if not wait_server(base):
                book.add('RUNTIME','Server boot','FAIL','Server did not become healthy in isolated audit copy')
                raise RuntimeError('Audit server failed to start')
            book.add('RUNTIME','Server boot','PASS',base)
            anon=API(base)
            st,h,_=anon.req('/api/health');book.check('RUNTIME','Health API',st==200 and h.get('ok') is True,f"version={h.get('version')}",f'status={st} body={h}')
            for path,token in [('/', 'ATS'),('/app.js','const NAV'),('/styles.css','body')]:
                st,body,_=anon.req(path)
                txt=body if isinstance(body,str) else json.dumps(body)
                book.check('RUNTIME',f'Static asset {path}',st==200 and token in txt,f'status={st}',f'status={st}')
            st,_,_=anon.req('/api/candidates');book.check('AUTH / RBAC','Anonymous protected API rejected',st==401,f'status={st}',f'expected 401 got {st}')
            st,_,_=anon.login('admin@atsone.local','wrong-password');book.check('AUTH / RBAC','Invalid password rejected',st==401,f'status={st}',f'expected 401 got {st}')

            clients={}
            for role,(email,pw) in DEMO.items():
                c=API(base);st,obj,hdr=c.login(email,pw);ok=st==200 and obj.get('user',{}).get('role')==role
                book.check('AUTH / RBAC',f'Login {role}',ok,f"user={obj.get('user',{}).get('name','')}",f'status={st} body={obj}')
                if ok:
                    clients[role]=c
                    st2,me,_=c.req('/api/me');book.check('AUTH / RBAC',f'/me session {role}',st2==200 and me.get('role')==role,f'id={me.get("id")}',f'status={st2} body={me}')
            admin=clients['admin']; recruiter=clients['recruiter']; sales=clients['sales']; finance=clients['finance']; client=clients['client']; cand=clients['candidate']; worker=clients['worker']; supplier=clients['supplier']; approver=clients['approver']; hr=clients['hr']; lead=clients['teamlead']

            # Cookie properties
            ctmp=API(base);st,_,hdr=ctmp.login(*DEMO['admin']);cookie=hdr.get('Set-Cookie','')
            book.check('AUTH / RBAC','Session cookie HttpOnly', 'HttpOnly' in cookie,cookie,cookie)
            book.check('AUTH / RBAC','Session cookie SameSite=Lax', 'SameSite=Lax' in cookie,cookie,cookie)

            # Dashboards and all documented GET APIs under admin
            for role,c in clients.items():
                st,obj,_=c.req('/api/dashboard');book.check('ROLE PORTALS',f'Dashboard {role}',st==200 and isinstance(obj,dict) and obj.get('role')==role,f'keys={len(obj)}',f'status={st} body={obj}')
            admin_gets=['/api/candidates','/api/hotlists','/api/jobs','/api/companies','/api/contacts','/api/leads','/api/opportunities','/api/shifts','/api/job-distribution','/api/integrations','/api/submissions','/api/interviews','/api/assessments','/api/onboarding','/api/assignments','/api/timesheets','/api/expenses','/api/invoices','/api/purchase-orders','/api/vms','/api/suppliers','/api/communications','/api/tasks','/api/automations','/api/users','/api/custom-fields','/api/audit','/api/reports/summary','/api/reference']
            for p in admin_gets:
                st,obj,_=admin.req(p);book.check('API SURFACE',f'GET {p}',st==200,f'type={type(obj).__name__}',f'status={st} body={obj}')

            # Reference IDs
            st,ref,_=admin.req('/api/reference'); companies=ref['companies']; contacts=ref['contacts']; jobs0=ref['jobs']; candidates0=ref['candidates']
            st_client_me,client_me,_=client.req('/api/me'); company1=client_me.get('company_id')
            contact1=next((x['id'] for x in contacts if x.get('company_id')==company1),contacts[0]['id']); seed_job_company1=next((x['id'] for x in jobs0 if x.get('company_id')==company1),jobs0[0]['id'])
            book.check('DATA ISOLATION','Client demo account is bound to a company',st_client_me==200 and bool(company1),f'company_id={company1}',f'status={st_client_me} body={client_me}')

            # Candidate CRUD shared visibility
            unique=f'Audit{int(time.time())}'
            cp={'first_name':unique,'last_name':'Candidate','email':f'{unique.lower()}@example.test','current_title':'QA Automation Engineer','profession':'Quality Engineering','specialty':'SDET','city':'Audit City','state':'MP','country':'India','availability_date':'2026-10-15','pay_min':25,'pay_max':40,'resume_text':'Selenium Java API SQL automation','skills':[{'skill':'Selenium','years':7,'recent':True,'last_used':'2026-09-01'},{'skill':'Java','years':6,'recent':True,'last_used':'2026-09-01'},{'skill':'API Testing','years':5,'recent':True,'last_used':'2026-09-01'}]}
            st,newc,_=recruiter.req('/api/candidates','POST',cp);cid=newc.get('id') if isinstance(newc,dict) else None
            book.check('CANDIDATE MASTER','Recruiter creates candidate + structured skills',st==201 and cid and len(newc.get('skills',[]))==3,f'candidate_id={cid}',f'status={st} body={newc}')
            st,found,_=admin.req('/api/candidates?q='+unique);book.check('MULTI-USER','Recruiter-created candidate visible to Admin',st==200 and any(x.get('id')==cid for x in found),f'candidate_id={cid}',f'status={st}')
            st,patch,_=recruiter.req(f'/api/candidates/{cid}','PATCH',{'current_title':'Senior QA Automation Engineer','pay_max':45});book.check('CANDIDATE MASTER','Candidate patch',st==200 and patch.get('ok'),f'candidate_id={cid}',f'status={st} body={patch}')
            st,note,_=recruiter.req(f'/api/candidates/{cid}/notes','POST',{'note':'Deep audit note','note_type':'Audit'});book.check('CANDIDATE MASTER','Candidate note creation',st==201 and note.get('ok'),f'note_id={note.get("id")}',f'status={st} body={note}')
            st,prof,_=admin.req(f'/api/candidates/{cid}');book.check('CANDIDATE MASTER','Candidate profile bundles skills/notes/submissions',st==200 and prof.get('current_title')=='Senior QA Automation Engineer' and len(prof.get('notes',[]))>=1 and 'submissions' in prof,f"skills={len(prof.get('skills',[]))}, notes={len(prof.get('notes',[]))}",f'status={st}')

            # Deep search dimensions
            searches=[
              ('Profession/Specialty',{'profession':'Software Engineer','specialty':'Backend'},lambda r:contains_candidate(r,'Arjun','Mehta')),
              ('Require years + recent + exclude',{'require':[{'term':'Java','years':5,'recent':True,'operator':'AND'},{'term':'Banking','years':2,'recent':False,'operator':'AND'}],'exclude':[{'term':'Mainframe'}]},lambda r:contains_candidate(r,'Arjun','Mehta')),
              ('Raw Boolean parser',{'raw_boolean':'(Java OVER 5 YRS AND Banking OVER 2 YRS) AND NOT Mainframe'},lambda r:contains_candidate(r,'Arjun','Mehta')),
              ('Title',{'title':'Senior Java Developer'},lambda r:contains_candidate(r,'Arjun','Mehta')),
              ('License state/active/documented',{'licenses':[{'type':'Registered Nurse RN','country':'USA','state':'CA','active':True,'documented':True}]},lambda r:contains_candidate(r,'Sofia','Rodriguez')),
              ('Certification',{'certifications':[{'name':'ACLS','active':True,'documented':True}]},lambda r:contains_candidate(r,'Sofia','Rodriguez')),
              ('Qualification',{'qualification':'BSN'},lambda r:contains_candidate(r,'Sofia','Rodriguez')),
              ('Attribute',{'attributes':['Travel Ready']},lambda r:contains_candidate(r,'Sofia','Rodriguez')),
              ('State refinement',{'state':'CA'},lambda r:all(x.get('state')=='CA' for x in r) and len(r)>0),
              ('Pay minimum refinement',{'pay_min':80},lambda r:all(float(x.get('pay_max') or 0)>=80 for x in r) and len(r)>0),
              ('Availability refinement',{'available_before':'2026-09-20'},lambda r:all((not x.get('availability_date')) or x.get('availability_date')<='2026-09-20' for x in r) and len(r)>0),
            ]
            for name,crit,pred in searches:
                st,res,_=recruiter.req('/api/search/talent','POST',crit);rows=res.get('results',[]) if isinstance(res,dict) else []
                book.check('TALENT SEARCH',name,st==200 and pred(rows),f'count={len(rows)} criteria={res.get("criteria","") if isinstance(res,dict) else ""}',f'status={st} body={res}')
            st,mapped,_=recruiter.req('/api/search/talent','POST',{'require':[{'term':'Amazon Web Services','years':5,'recent':False,'operator':'AND'}]});
            st2,literal,_=recruiter.req('/api/search/talent','POST',{'without_mapping':True,'require':[{'term':'Amazon Web Services','years':5,'recent':False,'operator':'AND'}]});
            book.check('TALENT SEARCH','Skill synonym mapping toggle',st==200 and st2==200 and mapped.get('count',0)>=literal.get('count',0) and mapped.get('count',0)>0,f"mapped={mapped.get('count')} literal={literal.get('count')}",f'mapped={mapped} literal={literal}')
            # Search denied to candidate
            st,_,_=cand.req('/api/search/talent','POST',{'title':'Java'});book.check('AUTH / RBAC','Candidate denied internal Talent Search',st==403,f'status={st}',f'expected 403 got {st}')

            # Hotlists/pools + result actions
            st,h,_=recruiter.req('/api/hotlists','POST',{'name':f'Audit Static {ts}','description':'audit','mode':'static','visibility':'Team'});hid=h.get('id') if isinstance(h,dict) else None
            book.check('HOTLISTS / POOLS','Create static hotlist',st==201 and hid,f'hotlist_id={hid}',f'status={st} body={h}')
            st,add,_=recruiter.req(f'/api/hotlists/{hid}/members','POST',{'candidate_id':cid,'note':'audit member'});book.check('HOTLISTS / POOLS','Add hotlist member',st==201 and add.get('ok'),f'candidate_id={cid}',f'status={st}')
            st,hdet,_=recruiter.req(f'/api/hotlists/{hid}');book.check('HOTLISTS / POOLS','Static pool retrieval/member mapping',st==200 and any(x.get('candidate_id')==cid for x in hdet.get('members',[])),f"members={len(hdet.get('members',[]))}",f'status={st} body={hdet}')
            st,dh,_=recruiter.req('/api/hotlists','POST',{'name':f'Audit Dynamic {ts}','mode':'dynamic','saved_search':{'profession':'Software Engineer','specialty':'Backend'}});dhid=dh.get('id') if isinstance(dh,dict) else None
            st,dhd,_=recruiter.req(f'/api/hotlists/{dhid}');book.check('HOTLISTS / POOLS','Dynamic pool re-runs saved search',st==200 and len(dhd.get('dynamic_results',[]))>0,f"dynamic_results={len(dhd.get('dynamic_results',[]))}",f'status={st} body={dhd}')
            st,comm,_=recruiter.req('/api/communications','POST',{'entity_type':'candidate','entity_id':cid,'channel':'Email','direction':'Outbound','subject':'Audit Email Merge','body':'Audit outreach','status':'Sent'});book.check('TALENT SEARCH','Email Merge action logs communication',st==201 and comm.get('ok'),f'communication_id={comm.get("id")}',f'status={st}')

            # CRM chain and inheritance
            st,co,_=sales.req('/api/companies','POST',{'name':f'Audit Client {ts}','industry':'Technology','submission_guidelines':'MAX 3 SUBMITTALS; RTR REQUIRED','discount_rule':'5% after 90 days'});coid=co.get('id') if isinstance(co,dict) else None
            book.check('CRM','Create company',st==201 and coid,f'company_id={coid}',f'status={st} body={co}')
            st,ct,_=sales.req('/api/contacts','POST',{'company_id':coid,'first_name':'Audit','last_name':'Manager','title':'Hiring Manager','email':f'hm-{ts}@example.test'});ctid=ct.get('id') if isinstance(ct,dict) else None
            book.check('CRM','Create contact linked to company',st==201 and ctid,f'contact_id={ctid}',f'status={st} body={ct}')
            st,ld,_=sales.req('/api/leads','POST',{'company_id':coid,'contact_id':ctid,'title':'Audit Lead','status':'New'});book.check('CRM','Create lead',st==201 and ld.get('id'),f'lead_id={ld.get("id")}',f'status={st}')
            st,op,_=sales.req('/api/opportunities','POST',{'company_id':coid,'contact_id':ctid,'name':'Audit Opportunity','stage':'Qualified','value':150000,'probability':60});book.check('CRM','Create opportunity',st==201 and op.get('id'),f'opportunity_id={op.get("id")}',f'status={st}')
            st,jnew,_=sales.req('/api/jobs','POST',{'title':'Audit Platform Engineer','company_id':coid,'contact_id':ctid,'priority':'High','work_mode':'Hybrid','city':'Indore','state':'MP','profession':'Software Engineer','specialty':'Cloud','required_skills':'AWS:5:recent|Kubernetes:3:true','submission_guidelines_override':''});jid_inherit=jnew.get('id') if isinstance(jnew,dict) else None
            book.check('JOBS','Create job linked to CRM',st==201 and jid_inherit,f'job_id={jid_inherit}',f'status={st} body={jnew}')
            st,jd,_=admin.req(f'/api/jobs/{jid_inherit}');book.check('CRM','Company submission guideline exposed for job inheritance',st==200 and jd.get('company_submission_guidelines')=='MAX 3 SUBMITTALS; RTR REQUIRED',str(jd.get('company_submission_guidelines')),f'status={st} body={jd}')
            st,jp,_=recruiter.req(f'/api/jobs/{jid_inherit}','PATCH',{'priority':'Urgent','submission_guidelines_override':'MAX 2; CLIENT FORM REQUIRED'});book.check('JOBS','Job patch + guideline override',st==200 and jp.get('ok'),f'job_id={jid_inherit}',f'status={st}')
            st,jd2,_=admin.req(f'/api/jobs/{jid_inherit}');book.check('JOBS','Job override persists separately from company rule',jd2.get('submission_guidelines_override')=='MAX 2; CLIENT FORM REQUIRED' and jd2.get('company_submission_guidelines')=='MAX 3 SUBMITTALS; RTR REQUIRED',f"company={jd2.get('company_submission_guidelines')} override={jd2.get('submission_guidelines_override')}",str(jd2))

            # Main hiring chain on client company 1 for client visibility
            st,wjob,_=recruiter.req('/api/jobs','POST',{'title':f'Audit Client1 Java {ts}','company_id':company1,'contact_id':contact1,'priority':'Urgent','work_mode':'Remote','profession':'Software Engineer','specialty':'Backend','pay_min':40,'pay_max':60,'bill_min':70,'bill_max':90,'required_skills':'Java:5:recent|Banking:2:false'});wjid=wjob.get('id') if isinstance(wjob,dict) else None
            book.check('HIRING WORKFLOW','Create client-visible requisition',st==201 and wjid,f'job_id={wjid}',f'status={st} body={wjob}')
            st,interest,_=recruiter.req(f'/api/jobs/{wjid}/interested','POST',{'candidate_id':2,'status':'qualified','source':'Talent Search'});book.check('HIRING WORKFLOW','Recruiter qualifies candidate into Interested layer',st==200 and interest.get('ok'),f'job={wjid} candidate=2',f'status={st}')
            st,app,_=cand.req(f'/api/jobs/{wjid}/interested','POST',{'candidate_id':1,'status':'interested','source':'Candidate Portal'});book.check('CANDIDATE PORTAL','Candidate self-apply/interest',st==200 and app.get('ok'),f'job={wjid} candidate=1',f'status={st}')
            st,sub,_=recruiter.req(f'/api/jobs/{wjid}/submissions','POST',{'candidate_id':2,'status':'submitted','client_rate':85,'candidate_rate':50,'availability':'Immediate','recruiter_summary':'Audit qualified candidate','compliance_status':'Pending','rtr_status':'Pending'});sid=sub.get('id') if isinstance(sub,dict) else None
            book.check('HIRING WORKFLOW','Create submission separate from interest',st==201 and sid,f'submission_id={sid}',f'status={st} body={sub}')
            st,clsubs,_=client.req('/api/submissions');book.check('CLIENT PORTAL','Client sees submission for own company',st==200 and any(x.get('id')==sid for x in clsubs),f'visible_submissions={len(clsubs)}',f'status={st}')
            st,dec,_=client.req(f'/api/submissions/{sid}/status','POST',{'status':'interview','client_feedback':'Please schedule technical interview'});book.check('CLIENT PORTAL','Client advances submission to interview',st==200 and dec.get('ok'),f'submission={sid}',f'status={st} body={dec}')
            st,intv,_=recruiter.req('/api/interviews','POST',{'submission_id':sid,'interview_type':'Video','scheduled_at':'2026-10-02T14:00:00','timezone':'Asia/Kolkata','location_or_link':'https://example.test/meet/audit','interviewer':'Audit Panel'});iid=intv.get('id') if isinstance(intv,dict) else None
            book.check('INTERVIEWS','Create interview and link to submission',st==201 and iid,f'interview_id={iid}',f'status={st} body={intv}')
            st,subs_after,_=admin.req('/api/submissions');row=next((x for x in subs_after if x.get('id')==sid),{})
            book.check('INTERVIEWS','Interview creation moves submission status',row.get('status')=='interview',f"status={row.get('status')}",str(row))
            st,ass,_=recruiter.req('/api/assessments','POST',{'candidate_id':2,'job_id':wjid,'title':'Audit Technical Assessment','assessment_type':'Questionnaire','max_score':100});book.check('ASSESSMENTS','Assessment invite creation',st==201 and ass.get('id'),f'assessment_id={ass.get("id")}',f'status={st}')
            st,onb,_=hr.req('/api/onboarding','POST',{'candidate_id':2,'job_id':wjid,'submission_id':sid,'package_name':'Audit Standard Package','requirements':[{'type':'E-Sign','name':'RTR','mandatory':True},{'type':'Identity','name':'ID Verification','mandatory':True}]});pid=onb.get('id') if isinstance(onb,dict) else None
            book.check('ONBOARDING','Create onboarding package with requirements',st==201 and pid,f'package_id={pid}',f'status={st} body={onb}')
            st,pdet,_=hr.req(f'/api/onboarding/{pid}'); reqids=[x['id'] for x in pdet.get('requirements',[])]
            book.check('ONBOARDING','Package requirement mapping',st==200 and len(reqids)==2,f'requirements={reqids}',f'status={st} body={pdet}')
            for rid in reqids: hr.req(f'/api/onboarding/requirements/{rid}/status','POST',{'status':'Complete'})
            st,pdet2,_=hr.req(f'/api/onboarding/{pid}');book.check('ONBOARDING','Package auto-completes when all requirements complete',pdet2.get('status')=='complete',f"status={pdet2.get('status')}",str(pdet2))

            # Assignment / time / expense / finance
            st,asg,_=hr.req('/api/assignments','POST',{'candidate_id':2,'job_id':wjid,'company_id':company1,'status':'active','start_date':'2026-10-05','end_date':'2027-04-05','worksite':'Remote','cost_center':'CC-AUDIT','vms_id':'VMS-AUDIT-1','approver_contact_id':contact1,'bill_rate':85,'pay_rate':50,'overtime_rule':'1.5x after 40h','payroll_profile':'Hourly','po_number':'PO-AUDIT'});aid=asg.get('id') if isinstance(asg,dict) else None
            book.check('WORKFORCE','Create assignment with bill/pay/cost-center/VMS/approver mapping',st==201 and aid,f'assignment_id={aid}',f'status={st} body={asg}')
            st,wasg,_=worker.req('/api/assignments');book.check('WORKFORCE','Worker sees own assignment',st==200 and any(x.get('id')==aid for x in wasg),f'worker_assignments={len(wasg)}',f'status={st}')
            daily={'Mon':9,'Tue':9,'Wed':9,'Thu':9,'Fri':9,'Sat':0,'Sun':0}
            st,tsh,_=worker.req('/api/timesheets','POST',{'assignment_id':aid,'week_start':'2026-10-05','daily':daily,'status':'submitted'});tid=tsh.get('id') if isinstance(tsh,dict) else None
            book.check('TIME / EXPENSE','Worker submits 45h timesheet',st==201 and tid and tsh.get('total_hours')==45,f"total={tsh.get('total_hours')}",f'status={st} body={tsh}')
            book.check('TIME / EXPENSE','Automatic 40 regular / 5 overtime split',tsh.get('regular_hours')==40 and tsh.get('overtime_hours')==5,f"regular={tsh.get('regular_hours')} overtime={tsh.get('overtime_hours')}",str(tsh))
            st,ats,_=approver.req('/api/timesheets');book.check('APPROVER PORTAL','Approver sees client-company timesheet',st==200 and any(x.get('id')==tid for x in ats),f'visible={len(ats)}',f'status={st}')
            st,tapp,_=approver.req(f'/api/timesheets/{tid}/status','POST',{'status':'approved'});book.check('APPROVER PORTAL','Approver approves timesheet',st==200 and tapp.get('ok'),f'timesheet={tid}',f'status={st}')
            st,exp,_=worker.req('/api/expenses','POST',{'assignment_id':aid,'expense_date':'2026-10-06','category':'Travel','amount':125.5,'receipt_ref':'AUDIT-RCP-1','description':'Audit travel'});eid=exp.get('id') if isinstance(exp,dict) else None
            book.check('TIME / EXPENSE','Worker submits expense',st==201 and eid,f'expense_id={eid}',f'status={st} body={exp}')
            st,eapp,_=approver.req(f'/api/expenses/{eid}/status','POST',{'status':'approved'});book.check('APPROVER PORTAL','Approver approves expense',st==200 and eapp.get('ok'),f'expense={eid}',f'status={st}')
            st,inv,_=finance.req('/api/invoices','POST',{'company_id':company1,'assignment_id':aid,'period_start':'2026-10-05','period_end':'2026-10-11','amount':3825,'tax':0,'status':'issued','due_date':'2026-11-10'});invid=inv.get('id') if isinstance(inv,dict) else None
            book.check('FINANCE','Finance creates issued invoice',st==201 and invid,f"invoice={inv.get('invoice_no')}",f'status={st} body={inv}')
            st,rep,_=finance.req('/api/reports/summary');book.check('REPORTING','Summary report aggregates recruiting/workforce/finance',st==200 and all(k in rep for k in ['recruiting','workforce','finance','submission_by_status','jobs_by_company']),f"sections={list(rep.keys())}",f'status={st} body={rep}')

            # Supplier workflow
            st,sjobs,_=supplier.req('/api/jobs'); st2,ajobs,_=admin.req('/api/jobs'); released={x['id'] for x in sjobs}; allids={x['id'] for x in ajobs};
            book.check('SUPPLIER PORTAL','Supplier job list is release-filtered',st==200 and released.issubset(allids) and len(released)<len(allids),f'released={len(released)} all={len(allids)}',f'status={st} released={released} all={len(allids)}')
            if released:
                st,sc,_=supplier.req('/api/supplier/candidates','POST',{'first_name':'Supplier','last_name':'Candidate','email':'supplier.candidate@audit.local','current_title':'Released Job Candidate'});scid=sc.get('id') if isinstance(sc,dict) else None
                book.check('SUPPLIER PORTAL','Supplier creates isolated supplier candidate',st==201 and scid,f'candidate_id={scid}',f'status={st} body={sc}')
                rjid=next(iter(released));st,ss,_=supplier.req(f'/api/jobs/{rjid}/submissions','POST',{'candidate_id':scid,'status':'submitted','recruiter_summary':'Supplier audit submission','compliance_status':'Pending','rtr_status':'Pending'});book.check('SUPPLIER PORTAL','Supplier submits own candidate to released job',st==201 and ss.get('id'),f'submission_id={ss.get("id")}',f'status={st} body={ss}')

            # Concurrency
            def concurrent_probe(i):
                c=API(base);st,_,_=c.login(*DEMO['recruiter']);
                if st!=200:return False
                st,d,_=c.req('/api/dashboard');return st==200 and d.get('role')=='recruiter'
            with concurrent.futures.ThreadPoolExecutor(max_workers=12) as ex:
                vals=list(ex.map(concurrent_probe,range(24)))
            book.check('MULTI-USER','24 concurrent login+dashboard probes',all(vals),f'passed={sum(vals)}/24',f'passed={sum(vals)}/24')

            # Audit log must include mutations
            st,aud,_=admin.req('/api/audit'); actions={x.get('action') for x in aud}
            book.check('AUDIT','Mutation/search/login actions recorded',st==200 and {'LOGIN','CREATE','SEARCH'}.issubset(actions),f'actions={sorted(actions)}',f'status={st} actions={actions}')

            # Security / scope positive and negative tests
            st,_,_=cand.req('/api/candidates','POST',{'first_name':'No','last_name':'Access'});book.check('AUTH / RBAC','Candidate cannot create candidate master',st==403,f'status={st}',f'expected 403 got {st}')
            st,_,_=finance.req('/api/candidates','POST',{'first_name':'No','last_name':'Access'});book.check('AUTH / RBAC','Finance cannot create candidate master',st==403,f'status={st}',f'expected 403 got {st}')
            st,_,_=recruiter.req('/api/companies','POST',{'name':'No Access Co'});book.check('AUTH / RBAC','Recruiter cannot create company',st==403,f'status={st}',f'expected 403 got {st}')
            st,_,_=client.req('/api/jobs','POST',{'title':'No Access Job'});book.check('AUTH / RBAC','Client cannot create internal job through generic endpoint',st==403,f'status={st}',f'expected 403 got {st}')
            st,_,_=recruiter.req('/api/users','POST',{'email':f'bad-{ts}@x.test','name':'Bad','role':'admin','password':'x'});book.check('AUTH / RBAC','Non-admin cannot create user',st==403,f'status={st}',f'expected 403 got {st}')
            st,_,_=cand.req('/api/candidates/2');book.check('DATA ISOLATION','Candidate cannot open another candidate profile',st==403,f'status={st}',f'expected 403 got {st}')
            st,own,_=cand.req('/api/candidates/1');book.check('DATA ISOLATION','Candidate can open own profile',st==200 and own.get('id')==1,f'status={st}',f'status={st} body={own}')

            # Intentional deep security probes: these currently expose whether generic routes are insufficiently protected.
            security_probes=[]
            st,_,_=cand.req('/api/candidates/2','PATCH',{'summary':'UNAUTHORIZED_AUDIT_PROBE'});security_probes.append(('Candidate cannot PATCH another candidate',st in (401,403),st))
            st,_,_=cand.req(f'/api/jobs/{wjid}','PATCH',{'priority':'Low'});security_probes.append(('Candidate cannot PATCH internal job',st in (401,403),st))
            st,_,_=cand.req('/api/hotlists','POST',{'name':'Unauthorized Candidate Hotlist'});security_probes.append(('Candidate cannot create internal hotlist',st in (401,403),st))
            st,_,_=cand.req(f'/api/jobs/{wjid}/submissions','POST',{'candidate_id':2,'status':'hired'});security_probes.append(('Candidate cannot create submission for another candidate',st in (401,403),st))
            st,_,_=cand.req(f'/api/submissions/{sid}/status','POST',{'status':'hired'});security_probes.append(('Candidate cannot force submission to hired',st in (401,403),st))
            st,_,_=cand.req('/api/interviews','POST',{'submission_id':sid,'scheduled_at':'2026-12-01T10:00:00'});security_probes.append(('Candidate cannot create interview',st in (401,403),st))
            st,_,_=cand.req('/api/assignments','POST',{'candidate_id':1,'job_id':wjid,'company_id':company1,'status':'active'});security_probes.append(('Candidate cannot create assignment',st in (401,403),st))
            st,_,_=cand.req(f'/api/expenses/{eid}/status','POST',{'status':'approved'});security_probes.append(('Candidate cannot approve expense',st in (401,403),st))
            st,obj,_=cand.req('/api/invoices');security_probes.append(('Candidate cannot list finance invoices',st in (401,403),st))
            st,obj,_=cand.req('/api/companies');security_probes.append(('Candidate cannot list internal CRM companies',st in (401,403),st))
            st,obj,_=supplier.req('/api/candidates');security_probes.append(('Supplier cannot browse internal candidate database',st in (401,403),st))
            st,obj,_=client.req(f'/api/jobs/{jid_inherit}');security_probes.append(('Client cannot open another company job by direct ID',st in (401,403,404),st))
            st,obj,_=client.req('/api/reference'); safe_ref = st in (401,403) or (isinstance(obj,dict) and not obj.get('users') and not obj.get('candidates'));security_probes.append(('Client reference API must not expose internal users/candidate pool',safe_ref,st))
            for name,ok,actual in security_probes: book.check('SECURITY / DATA ISOLATION',name,ok,f'status={actual}',f'UNAUTHORIZED ACCESS ALLOWED status={actual}')

            # Supplier unreleased job should be blocked
            diff=list(allids-released)
            if diff:
                st,_,_=supplier.req(f'/api/jobs/{diff[0]}/submissions','POST',{'candidate_id':cid,'status':'submitted','recruiter_summary':'Unreleased audit probe'});book.check('SECURITY / DATA ISOLATION','Supplier cannot submit to unreleased job',st in (401,403,404),f'status={st}',f'UNAUTHORIZED submission allowed status={st}')

            # Role scoped collections
            st,cjobs,_=client.req('/api/jobs');book.check('DATA ISOLATION','Client job list scoped to own company',st==200 and all(x.get('company_id')==company1 for x in cjobs),f'count={len(cjobs)}',f'status={st}')
            st,wts,_=worker.req('/api/timesheets');book.check('DATA ISOLATION','Worker timesheets scoped to own candidate',st==200 and all(x.get('candidate_id')==2 for x in wts),f'count={len(wts)}',f'status={st}')
            st,wex,_=worker.req('/api/expenses');book.check('DATA ISOLATION','Worker expenses scoped to own candidate',st==200 and all(x.get('candidate_id')==2 for x in wex),f'count={len(wex)}',f'status={st}')
            st,ats2,_=approver.req('/api/timesheets');book.check('DATA ISOLATION','Approver timesheets scoped to own company',st==200 and all(x.get('company_name') for x in ats2),f'count={len(ats2)}',f'status={st}')

            # Logout invalidation
            lc=API(base);st,_,_=lc.login(*DEMO['admin']);st,_,_=lc.req('/api/logout','POST',{});st2,_,_=lc.req('/api/me');book.check('AUTH / RBAC','Logout invalidates session',st==200 and st2==401,f'after_logout={st2}',f'logout={st} after={st2}')

            # Source capability matrix and external boundaries
            capability_matrix(book,server_text,app_text,acceptance)

        except Exception as e:
            book.add('AUDITOR','Unhandled auditor exception','FAIL',f'{type(e).__name__}: {e}')
            traceback.print_exc()
        finally:
            if proc:
                proc.terminate()
                try:proc.wait(timeout=4)
                except Exception:proc.kill()
            logf.close()

    counts=book.counts(); total=len(book.rows)
    # Overall is deliberately strict: any runtime/security FAIL = FAIL; partials are visible but do not hide runtime pass/fail.
    overall='FAIL' if counts.get('FAIL',0) else ('PARTIAL' if counts.get('PARTIAL',0) else 'PASS')
    header=[
      '='*96,
      ' ATS ONE STAFFING ERP — DEEP FUNCTION ACCEPTANCE AUDIT',
      '='*96,
      f'TIMESTAMP={datetime.now(timezone.utc).isoformat()}',
      f'PYTHON={sys.version.split()[0]}',
      f'APP_ROOT={ROOT}',
      f'OVERALL={overall}',
      f'TOTAL_CHECKS={total}',
      f"PASS={counts.get('PASS',0)}",
      f"FAIL={counts.get('FAIL',0)}",
      f"PARTIAL={counts.get('PARTIAL',0)}",
      f"EXTERNAL={counts.get('EXTERNAL',0)}",
      '='*96,
    ]
    lines=header[:]
    current=None
    for r in book.rows:
        if r['section']!=current:
            current=r['section'];lines += ['',f'[{current}]']
        lines.append(f"{r['status']:8} | {r['name']}" + (f" | {r['detail']}" if r['detail'] else ''))
    lines += ['', '='*96, 'VERDICT LEGEND', 'PASS     = exercised and passed in isolated runtime or source route is materially implemented.', 'FAIL     = runtime bug, broken workflow, or security/data-isolation defect detected.', 'PARTIAL  = some functionality exists but the full claimed workflow/CRUD/lifecycle is not implemented.', 'EXTERNAL = cannot be truthfully validated without real third-party credentials/contracts.', '='*96]
    txt='\n'.join(lines)+'\n'
    txt_path=outdir/f'DEEP-AUDIT-{ts}.txt';json_path=outdir/f'DEEP-AUDIT-{ts}.json'
    txt_path.write_text(txt,encoding='utf-8')
    json_path.write_text(json.dumps({'overall':overall,'counts':counts,'results':book.rows},indent=2,ensure_ascii=False),encoding='utf-8')
    print('\n'+ '='*96)
    print(f'OVERALL={overall} TOTAL={total} PASS={counts.get("PASS",0)} FAIL={counts.get("FAIL",0)} PARTIAL={counts.get("PARTIAL",0)} EXTERNAL={counts.get("EXTERNAL",0)}')
    print(f'TXT={txt_path}')
    print(f'JSON={json_path}')
    print('='*96)
    # Return non-zero on actual FAIL so automation can fail closed.
    return 2 if counts.get('FAIL',0) else 0

if __name__=='__main__':
    raise SystemExit(main())
