#!/usr/bin/env python3
"""ATS-One R8 executable acceptance suite.

Local mode copies the application into a temporary directory, starts it with a
fresh SQLite database, and mutates only that isolated copy. Live-readonly mode
performs authenticated reads only.
"""
import argparse, base64, hashlib, http.cookiejar, json, os, shutil, socket, sqlite3, subprocess, sys, tempfile, time, urllib.error, urllib.parse, urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parent

class API:
    def __init__(self,base):
        self.base=base.rstrip('/');self.jar=http.cookiejar.CookieJar();self.opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))
    def req(self,path,method='GET',body=None):
        raw=None;headers={'Accept':'application/json'}
        if body is not None:raw=json.dumps(body).encode();headers['Content-Type']='application/json'
        request=urllib.request.Request(self.base+path,data=raw,headers=headers,method=method)
        try:
            with self.opener.open(request,timeout=10) as response:
                payload=response.read();ctype=response.headers.get('Content-Type','')
                if 'json' in ctype:
                    try:payload=json.loads(payload.decode())
                    except Exception:pass
                return response.status,payload,dict(response.headers)
        except urllib.error.HTTPError as error:
            payload=error.read()
            try:payload=json.loads(payload.decode())
            except Exception:pass
            return error.code,payload,dict(error.headers)
    def login(self,email='admin@atsone.local',password='Admin@123'):
        return self.req('/api/login','POST',{'email':email,'password':password})

class Results:
    def __init__(self):self.checks=[]
    def check(self,label,condition,detail=''):
        self.checks.append({'label':label,'status':'PASS' if condition else 'FAIL','detail':str(detail)})
        print(f"[{'PASS' if condition else 'FAIL':4}] {label}"+(f' -- {detail}' if detail else ''))
        return condition
    def protect(self,label,fn):
        try:return self.check(label,bool(fn()),'executable validation')
        except Exception as exc:return self.check(label,False,f'{type(exc).__name__}: {exc}')
    def document(self):
        fail=sum(x['status']=='FAIL' for x in self.checks)
        return {'overall':'PASS' if fail==0 else 'FAIL','fail':fail,'pass':len(self.checks)-fail,'checks':self.checks}

def free_port():
    s=socket.socket();s.bind(('127.0.0.1',0));port=s.getsockname()[1];s.close();return port

def wait_ready(base,seconds=15):
    api=API(base);end=time.time()+seconds
    while time.time()<end:
        try:
            if api.req('/api/health')[0]==200:return True
        except Exception:pass
        time.sleep(.15)
    return False

def ok(response,code=None):return response[0]==(code or response[0]) and 200<=response[0]<300
def body(response):return response[1] if isinstance(response[1],dict) else {}
def rows(response):return response[1] if isinstance(response[1],list) else []

def local_suite(base,db_path,result):
    admin=API(base);recruiter=API(base);finance=API(base);worker=API(base);candidate=API(base);supplier=API(base)
    assert admin.login()[0]==200
    assert recruiter.login('recruiter@atsone.local','Recruit@123')[0]==200
    assert finance.login('finance@atsone.local','Finance@123')[0]==200
    assert worker.login('worker@atsone.local','Worker@123')[0]==200
    assert candidate.login('candidate@atsone.local','Candidate@123')[0]==200
    assert supplier.login('supplier@atsone.local','Supplier@123')[0]==200

    empty={'profession':'','specialty':'','licenses':[],'certifications':[],'qualification':'','require':[],'exclude':[],'attributes':[],'title':'','state':'','zip':'','radius_miles':'','pay_min':'','pay_max':'','available_before':'','without_mapping':False,'raw_boolean':''}
    r=admin.req('/api/search/talent','POST',empty);result.check('SEARCH_EMPTY_NO_HIDDEN_AVAILABILITY',r[0]==200 and body(r).get('count')==8,body(r).get('count'))
    def search(expr,**extra):return admin.req('/api/search/talent','POST',{**empty,'raw_boolean':expr,**extra})
    a=search('(Java OVER 5 YRS OR Python OVER 5 YRS) AND NOT Mainframe');result.check('BOOLEAN_AND_OR_NOT',a[0]==200 and body(a).get('count',0)>=2,body(a).get('count'))
    a=search('(Java OVER 5 YRS AND (Banking OVER 2 YRS OR AWS OVER 5 YRS)) AND NOT Mainframe');result.check('BOOLEAN_NESTED',a[0]==200 and body(a).get('count',0)>=1)
    a=search('("Amazon Web Services" OVER 5 YRS OR AWS OVER 5 YRS)');result.check('BOOLEAN_QUOTED_MULTIWORD',a[0]==200 and body(a).get('count',0)>=1)
    a=search('Amazon Web Services OVER 5 YRS');result.check('BOOLEAN_UNQUOTED_MULTIWORD',a[0]==200 and body(a).get('count',0)>=1)
    a=search('(Java AND');result.check('BOOLEAN_INVALID_SYNTAX_400',a[0]==400 and 'detail' in body(a),body(a))
    a=search('Java OVER 8 YRS');result.check('BOOLEAN_YEARS',a[0]==200 and any(x['first_name']=='Arjun' for x in body(a).get('results',[])))
    a=search('DEVELOPER RECENT OVER 5 YRS');result.check('BOOLEAN_RECENT',a[0]==200 and body(a).get('count',0)>=1)
    mapped=search('Amazon Web Services OVER 5 YRS');result.check('SYNONYM_MAPPING',body(mapped).get('count',0)>=1)
    literal=search('Amazon Web Services OVER 5 YRS',without_mapping=True);result.check('WITHOUT_MAPPING_LITERAL',literal[0]==200 and body(literal).get('count',0)<body(mapped).get('count',0))
    geo=admin.req('/api/search/talent','POST',{**empty,'zip':'78701','radius_miles':25});bad_geo=admin.req('/api/search/talent','POST',{**empty,'zip':'NO-SUCH-ZIP','radius_miles':25});result.check('ZIP_RADIUS',geo[0]==200 and any(x['first_name']=='Liam' for x in body(geo).get('results',[])) and bad_geo[0]==400)
    jc=admin.req('/api/jobs/2/search-criteria');jm=admin.req('/api/jobs/2/matches');result.check('JOB_TO_TALENT_SEARCH',jc[0]==200 and jm[0]==200 and body(jc).get('require') is not None)
    cm=admin.req('/api/candidates/2/matches');result.check('DIVAMATCH_SHARED_ENGINE',cm[0]==200 and all('match_reasons' in x and 'relevance' in x for x in body(cm).get('results',[])))
    evidence=body(search('Java OVER 5 YRS')).get('results',[]);result.check('SEARCH_EXPAND',bool(evidence and evidence[0].get('match_reasons')));result.check('SEARCH_RELEVANCY',bool(evidence and isinstance(evidence[0].get('relevance'),(int,float))))

    c=body(recruiter.req('/api/candidates','POST',{'first_name':'R8','last_name':'Candidate','email':'r8@example.test','zip':'78701','profession':'Software Engineer','current_title':'Cloud Engineer','skills':[{'skill':'GCP','years':6,'recent':True}]}));cid=c.get('id')
    skill=body(recruiter.req(f'/api/candidates/{cid}/skills','POST',{'skill':'TypeScript','years':4,'recent':True}));exp=body(recruiter.req(f'/api/candidates/{cid}/experience','POST',{'company':'Example','title':'Cloud Engineer','start_date':'2020-01-01','skills':'GCP, TypeScript'}));lic=body(recruiter.req(f'/api/candidates/{cid}/licenses','POST',{'license_type':'Test License','state':'TX'}));cert=body(recruiter.req(f'/api/candidates/{cid}/certifications','POST',{'name':'Cloud Cert'}));qual=body(recruiter.req(f'/api/candidates/{cid}/qualifications','POST',{'name':'Degree','value':'BS'}));attr=body(recruiter.req(f'/api/candidates/{cid}/attributes','POST',{'attribute':'Top Candidate','value':'Yes'}))
    patch_skill=recruiter.req(f'/api/candidates/{cid}/skills/{skill.get("id")}','PATCH',{'years':5});result.check('CANDIDATE_STRUCTURED_CRUD',all(x.get('id') for x in (c,skill,exp,lic,cert,qual,attr)) and patch_skill[0]==200)
    parsed=recruiter.req('/api/resume/parse','POST',{'resume_text':'Jane Doe\njane@example.com\nSenior Java Developer with 7 years Java and AWS.'});result.check('RESUME_REVIEW_WORKFLOW',parsed[0]==200 and body(parsed).get('review_required') is True and body(parsed).get('skills'))
    raw=b'R8 document evidence';doc=body(recruiter.req(f'/api/candidates/{cid}/documents','POST',{'name':'Evidence','file_name':'evidence.txt','mime_type':'text/plain','content_base64':base64.b64encode(raw).decode()}));download=recruiter.req(f'/api/candidate-documents/{doc.get("id")}/download');verify=recruiter.req(f'/api/candidate-documents/{doc.get("id")}','PATCH',{'verify':True});result.check('DOCUMENT_WORKFLOW',doc.get('id') and download[0]==200 and download[1]==raw and verify[0]==200)
    hot=body(recruiter.req('/api/hotlists','POST',{'name':'R8 Pool'}));bulk=recruiter.req('/api/search/bulk','POST',{'action':'hotlist','candidate_ids':[cid],'hotlist_id':hot.get('id')});result.check('SEARCH_BULK_ACTION',bulk[0]==200 and body(bulk).get('affected')==1)
    hm=recruiter.req(f'/api/hotlists/{hot.get("id")}/members/{cid}','PATCH',{'status':'Qualified','note':'R8'});hr=recruiter.req(f'/api/hotlists/{hot.get("id")}/members/{cid}','DELETE');hu=recruiter.req(f'/api/hotlists/{hot.get("id")}','PATCH',{'name':'R8 Pool Renamed'});hd=recruiter.req(f'/api/hotlists/{hot.get("id")}','DELETE');result.check('HOTLIST_FULL_CRUD',all(x[0]==200 for x in (hm,hr,hu,hd)))

    co=body(admin.req('/api/companies','POST',{'name':'R8 Client'}));contact=body(admin.req('/api/contacts','POST',{'company_id':co.get('id'),'first_name':'R8','last_name':'Manager'}));lead=body(admin.req('/api/leads','POST',{'company_id':co.get('id'),'contact_id':contact.get('id'),'title':'R8 Lead'}));converted=body(admin.req(f'/api/leads/{lead.get("id")}/convert','POST',{'value':10000}));opp_patch=admin.req(f'/api/opportunities/{converted.get("opportunity_id")}','PATCH',{'stage':'Won','status':'Won','next_activity':'Kickoff'});result.check('CRM_LIFECYCLE',co.get('id') and contact.get('id') and converted.get('opportunity_id') and opp_patch[0]==200)
    job=body(admin.req('/api/jobs','POST',{'title':'R8 Java Engineer','company_id':co.get('id'),'contact_id':contact.get('id'),'profession':'Software Engineer','required_skills':'Java:5:recent|AWS:3:true','zip':'78701'}));ju=body(admin.req(f'/api/jobs/{job.get("id")}/users','POST',{'user_id':3,'role_name':'Secondary Recruiter'}));result.check('JOB_ROLE_CRUD',job.get('id') and ju.get('id'))
    clone=body(admin.req(f'/api/jobs/{job.get("id")}/clone','POST',{}));archive=admin.req(f'/api/jobs/{clone.get("id")}','DELETE');restore=admin.req(f'/api/jobs/{clone.get("id")}','PATCH',{'status':'Open'});result.check('JOB_CLONE_ARCHIVE',clone.get('id') and archive[0]==200 and restore[0]==200)
    dist=body(admin.req(f'/api/jobs/{job.get("id")}/distribution','POST',{'channel':'Internal Careers','status':'Published'}));dist_patch=admin.req(f'/api/job-distribution/{dist.get("id")}','PATCH',{'status':'Unpublished'});result.check('JOB_DISTRIBUTION_LIFECYCLE',dist.get('id') and dist_patch[0]==200)

    admin.req(f'/api/jobs/{job.get("id")}/interested','POST',{'candidate_id':cid,'status':'qualified'})
    sub=body(admin.req(f'/api/jobs/{job.get("id")}/submissions','POST',{'candidate_id':cid,'status':'draft','rtr_status':'Approved','compliance_status':'Approved'}));sid=sub.get('id')
    admin.req(f'/api/submissions/{sid}/status','POST',{'status':'submitted'});admin.req(f'/api/submissions/{sid}/status','POST',{'status':'client_review'})
    interview=body(admin.req('/api/interviews','POST',{'submission_id':sid,'scheduled_at':'2026-11-01T10:00:00','timezone':'Asia/Kolkata','interviewer':'R8 Manager'}));ires=admin.req(f'/api/interviews/{interview.get("id")}','PATCH',{'scheduled_at':'2026-11-02T10:00:00','status':'completed','feedback':'Strong','rating':5});result.check('INTERVIEW_LIFECYCLE',interview.get('id') and ires[0]==200)
    admin.req(f'/api/submissions/{sid}/status','POST',{'status':'offer'});hired=admin.req(f'/api/submissions/{sid}/status','POST',{'status':'hired'});invalid=admin.req(f'/api/submissions/{sid}/status','POST',{'status':'submitted'});result.check('HIRING_TRANSITION_GATES',hired[0]==200 and invalid[0]==409)
    assess=body(admin.req('/api/assessments','POST',{'candidate_id':cid,'job_id':job.get('id'),'title':'R8 Skills','questions':[{'prompt':'Explain Java','points':10}]}));aid=assess.get('id');qrows=[]
    conn=sqlite3.connect(db_path)
    try:qrows=conn.execute('SELECT id FROM assessment_questions WHERE assessment_id=?',(aid,)).fetchall()
    finally:conn.close()
    answers=admin.req(f'/api/assessments/{aid}/answers','POST',{'answers':[{'question_id':qrows[0][0],'answer':'Answer','awarded_points':8}]});review=admin.req(f'/api/assessments/{aid}','PATCH',{'status':'reviewed','notes':'Reviewed'});result.check('ASSESSMENT_LIFECYCLE',answers[0]==200 and review[0]==200 and body(answers).get('score')==8)
    onboard=body(admin.req('/api/onboarding','POST',{'candidate_id':cid,'job_id':job.get('id'),'submission_id':sid,'package_name':'R8 Package','requirements':[{'type':'Document','name':'ID'}]}));package=body(admin.req(f'/api/onboarding/{onboard.get("id")}'));rid=package.get('requirements',[{}])[0].get('id');complete=admin.req(f'/api/onboarding/requirements/{rid}/status','POST',{'status':'Complete','evidence_document_id':doc.get('id')});result.check('ONBOARDING_LIFECYCLE',complete[0]==200 and body(admin.req(f'/api/onboarding/{onboard.get("id")}')).get('status')=='complete')
    start=body(admin.req('/api/starts','POST',{'submission_id':sid,'start_date':'2026-11-10'}));start_active=admin.req(f'/api/starts/{start.get("id")}','PATCH',{'status':'active'});start_complete=admin.req(f'/api/starts/{start.get("id")}','PATCH',{'status':'completed'});result.check('START_LIFECYCLE',start.get('id') and start_active[0]==200 and start_complete[0]==200)
    assignment=body(admin.req('/api/assignments','POST',{'start_id':start.get('id'),'candidate_id':cid,'job_id':job.get('id'),'company_id':co.get('id'),'status':'pending','worksite':'Austin','bill_rate':100,'pay_rate':70}));aa=admin.req(f'/api/assignments/{assignment.get("id")}','PATCH',{'status':'active'});hold=admin.req(f'/api/assignments/{assignment.get("id")}','PATCH',{'status':'on_hold'});back=admin.req(f'/api/assignments/{assignment.get("id")}','PATCH',{'status':'active'});result.check('ASSIGNMENT_LIFECYCLE',assignment.get('id') and all(x[0]==200 for x in (aa,hold,back)))
    shift=body(admin.req('/api/shifts','POST',{'assignment_id':assignment.get('id'),'shift_date':'2026-11-11','start_time':'09:00','end_time':'17:00'}));shift_patch=admin.req(f'/api/shifts/{shift.get("id")}','PATCH',{'start_time':'08:30'});result.check('SHIFT_CRUD',shift.get('id') and shift_patch[0]==200)
    attendance=body(admin.req('/api/attendance','POST',{'shift_id':shift.get('id'),'candidate_id':cid,'check_in':'2026-11-11T08:25:00'}));att_patch=admin.req(f'/api/attendance/{attendance.get("id")}','PATCH',{'check_out':'2026-11-11T17:00:00','status':'Present'});result.check('ATTENDANCE_CRUD',attendance.get('id') and att_patch[0]==200)
    ts=body(worker.req('/api/timesheets','POST',{'assignment_id':1,'week_start':'2026-11-02','status':'draft','daily':{'mon':9,'tue':9,'wed':9,'thu':9,'fri':9}}));submit=worker.req(f'/api/timesheets/{ts.get("id")}/status','POST',{'status':'submitted'});approve=finance.req(f'/api/timesheets/{ts.get("id")}/status','POST',{'status':'approved'});reopen=finance.req(f'/api/timesheets/{ts.get("id")}/status','POST',{'status':'reopened'});result.check('TIMESHEET_LIFECYCLE',all(x[0]==200 for x in (submit,approve,reopen)) and ts.get('overtime_hours')==5)
    ex=body(worker.req('/api/expenses','POST',{'assignment_id':1,'amount':50,'category':'Travel','receipt_ref':'R8','status':'submitted'}));exa=finance.req(f'/api/expenses/{ex.get("id")}/status','POST',{'status':'approved'});exr=finance.req(f'/api/expenses/{ex.get("id")}','PATCH',{'status':'reopened'});result.check('EXPENSE_LIFECYCLE',ex.get('id') and exa[0]==200 and exr[0]==200)
    po=body(finance.req('/api/purchase-orders','POST',{'company_id':co.get('id'),'job_id':job.get('id'),'assignment_id':assignment.get('id'),'po_number':'R8-PO-1','amount':50000}));poc=finance.req(f'/api/purchase-orders/{po.get("id")}','PATCH',{'status':'Closed'});result.check('PO_LIFECYCLE',po.get('id') and poc[0]==200)
    inv=body(finance.req('/api/invoices','POST',{'company_id':co.get('id'),'assignment_id':assignment.get('id'),'amount':1000,'tax':100,'status':'draft'}));issue=finance.req(f'/api/invoices/{inv.get("id")}','PATCH',{'status':'issued'});p1=finance.req(f'/api/invoices/{inv.get("id")}/payments','POST',{'amount':500,'reference':'R8-P1'});p2=finance.req(f'/api/invoices/{inv.get("id")}/payments','POST',{'amount':600,'reference':'R8-P2'});result.check('INVOICE_LIFECYCLE',all(x[0] in (200,201) for x in (issue,p1,p2)) and body(p2).get('status')=='paid')
    vms=body(admin.req('/api/vms/accounts','POST',{'name':'R8 VMS','platform':'Internal'}));mapping=body(admin.req('/api/vms/mappings','POST',{'vms_account_id':vms.get('id'),'object_type':'job','external_id':'R8-J','internal_id':job.get('id')}));sync=admin.req(f'/api/vms/accounts/{vms.get("id")}/sync','POST',{});result.check('VMS_INTERNAL_CRUD',vms.get('id') and mapping.get('id') and body(sync).get('status')=='Success')
    sup=body(admin.req('/api/suppliers','POST',{'name':'R8 Supplier'}));release=admin.req(f'/api/suppliers/{sup.get("id")}/releases','POST',{'job_id':job.get('id'),'max_submissions':1});deactivate=admin.req(f'/api/suppliers/{sup.get("id")}','PATCH',{'status':'Inactive'});supplier_candidate=body(supplier.req('/api/supplier/candidates','POST',{'first_name':'R8','last_name':'Supplier Candidate'}));supplier_submission=supplier.req('/api/jobs/4/submissions','POST',{'candidate_id':supplier_candidate.get('id'),'status':'submitted'});result.check('SUPPLIER_RELEASE_ADMIN',sup.get('id') and release[0]==201 and deactivate[0]==200 and supplier_candidate.get('id') and supplier_submission[0]==201)
    task=body(admin.req('/api/tasks','POST',{'entity_type':'candidate','entity_id':cid,'title':'R8 Task'}));task_done=admin.req(f'/api/tasks/{task.get("id")}','PATCH',{'status':'Complete'});result.check('TASK_LIFECYCLE',task.get('id') and task_done[0]==200)
    auto=body(admin.req('/api/automations','POST',{'name':'R8 Automation','trigger_name':'candidate.created','condition':{},'action':{'type':'create_task','title':'Automated'}}));dry=admin.req(f'/api/automations/{auto.get("id")}/run','POST',{'dry_run':True});execute=admin.req(f'/api/automations/{auto.get("id")}/run','POST',{});result.check('AUTOMATION_INTERNAL_ENGINE',body(dry).get('status')=='Dry Run' and body(execute).get('status')=='Success')
    connector=body(admin.req('/api/integrations','POST',{'category':'Internal','name':'R8 Connector','mode':'Internal','config':{'endpoint':'local'}}));test=admin.req(f'/api/integrations/{connector.get("id")}/test','POST',{});logs=admin.req(f'/api/integrations/{connector.get("id")}/logs');result.check('INTEGRATION_CONFIG',connector.get('id') and body(test).get('status')=='Success' and len(rows(logs))==1)
    udf=body(admin.req('/api/custom-fields','POST',{'entity_type':'candidate','field_name':'R8 Score','field_type':'number'}));value=admin.req('/api/custom-values','POST',{'entity_type':'candidate','entity_id':cid,'field_id':udf.get('id'),'value':'9.5'});invalid_value=admin.req('/api/custom-values','POST',{'entity_type':'candidate','entity_id':cid,'field_id':udf.get('id'),'value':'bad'});result.check('UDF_CRUD',udf.get('id') and value[0]==200 and invalid_value[0]==400)
    user=body(admin.req('/api/users','POST',{'email':'r8.user@example.test','name':'R8 User','role':'recruiter'}));public=API(base);accepted=public.req('/api/auth/invitations/accept','POST',{'token':user.get('invitation_token'),'password':'Initial@123','name':'R8 User'});user_patch=admin.req(f'/api/users/{user.get("id")}','PATCH',{'role':'hr','active':0});final_admin=admin.req('/api/users/1','PATCH',{'active':0});result.check('USER_ADMIN_LIFECYCLE',user.get('id') and accepted[0]==201 and user_patch[0]==200 and final_admin[0]==409)
    report_def=body(admin.req('/api/reports/definitions','POST',{'name':'R8 Pipeline','report_key':'recruiting_pipeline','parameters':{}}));report=admin.req('/api/reports/run?report_key=recruiting_pipeline');export=admin.req('/api/reports/export?report_key=finance_aging');result.check('REPORT_EXECUTION_EXPORT',report_def.get('id') and report[0]==200 and export[0]==200 and isinstance(export[1],bytes) and export[1].startswith(b'\xef\xbb\xbf'))
    archived=admin.req(f'/api/candidates/{cid}','DELETE');restored=admin.req(f'/api/candidates/{cid}','PATCH',{'status':'Active'});result.check('ARCHIVE_RESTORE',archived[0]==200 and restored[0]==200)

    # Provision tenant two directly in the isolated fixture. Runtime APIs must still enforce it.
    salt=b'R8-tenant-salt!';digest=hashlib.pbkdf2_hmac('sha256',b'Tenant@123',salt,150_000);encoded=base64.b64encode(salt).decode()+':'+base64.b64encode(digest).decode()
    conn=sqlite3.connect(db_path)
    try:
        conn.execute("INSERT INTO tenants(name,slug,status,created_at) VALUES('Tenant Two','tenant-two','Active',datetime('now'))");tid=conn.execute("SELECT id FROM tenants WHERE slug='tenant-two'").fetchone()[0]
        conn.execute("INSERT INTO users(email,pass_hash,name,role,active,created_at,tenant_id) VALUES(?,?,?,?,1,datetime('now'),?)",('tenant2.admin@example.test',encoded,'Tenant Two Admin','admin',tid));conn.commit()
    finally:conn.close()
    tenant2=API(base);login2=tenant2.login('tenant2.admin@example.test','Tenant@123');list2=tenant2.req('/api/candidates');direct2=tenant2.req('/api/candidates/1');created2=body(tenant2.req('/api/candidates','POST',{'first_name':'Tenant','last_name':'Two'}));cross1=admin.req(f'/api/candidates/{created2.get("id")}')
    result.check('TENANT_ISOLATION',login2[0]==200 and list2[0]==200 and rows(list2)==[] and direct2[0]==404 and created2.get('tenant_id')==tid and cross1[0]==404)
    sec=[candidate.req('/api/search/talent','POST',empty),candidate.req('/api/candidates/2','PATCH',{'last_name':'Denied'}),supplier.req('/api/candidates'),candidate.req('/api/invoices')]
    result.check('SECURITY_REGRESSION',all(x[0] in (403,404) for x in sec),[x[0] for x in sec])
    css=(ROOT/'web'/'styles.css').read_text(encoding='utf-8')
    palette=['--primary:#6757D9','--primary-2:#8B7DE8','--accent:#1DAA8B','--coral:#E87D63','--amber:#D59A32','--app-bg:#F7F7FB','--panel:#FFFFFF','--nav:#FBFAFF','--ink:#263044','--muted:#71798A','--line:#E1E3EC','--soft:#F0EEFB']
    result.check('LIGHT_DISTINCT_THEME',all(x in css for x in palette) and 'background:var(--app-bg)' in css)
    app=(ROOT/'web'/'app.js').read_text(encoding='utf-8')
    controls=['openStructuredCandidate','uploadCandidateDocument','openJobSearch','runBulkAction','cloneJob','publishJob','newAssignment','newPurchaseOrder','newVMSAccount','newSupplier','runOperationalReport','newUDF','newAutomation','newConnector']
    result.check('MAIN_UI_FUNCTIONAL_CONTROLS',all(x in app for x in controls),', '.join(controls))

# R12C_DYNAMIC_LIVE_VERSION
def source_app_version():
    server=(ROOT/'server.py').read_text(
        encoding='utf-8'
    )

    for line in server.splitlines():
        line=line.strip()

        if (
            line.startswith('APP_VERSION')
            and '=' in line
        ):
            return (
                line.split('=',1)[1]
                    .strip()
                    .strip('"')
                    .strip("'")
            )

    raise RuntimeError(
        'APP_VERSION not found in server.py'
    )


def readonly_suite(base,result):
    api=API(base);login=api.login();health=api.req('/api/health');me=api.req('/api/me');candidates=api.req('/api/candidates');jobs=api.req('/api/jobs');search=api.req('/api/search/talent','POST',{'raw_boolean':'Java OR Python','available_before':'','radius_miles':''});matches=api.req('/api/candidates/1/matches')
    expected_version=source_app_version()
    actual_version=body(health).get('version')
    persistence=body(health).get('persistence')

    result.check(
        'LIVE_HEALTH_VERSION',
        login[0]==200
        and health[0]==200
        and actual_version==expected_version
        and persistence in (
            'local-sqlite',
            'supabase-storage'
        ),
        f'actual={actual_version} expected={expected_version} persistence={persistence}'
    )
    result.check('LIVE_SESSION_READS',me[0]==200 and candidates[0]==200 and jobs[0]==200)
    result.check('LIVE_BOOLEAN_READONLY',search[0]==200 and isinstance(body(search).get('results'),list))
    result.check('LIVE_MATCH_READONLY',matches[0]==200)
    anonymous=API(base);result.check('LIVE_RBAC_READ_PROTECTION',anonymous.req('/api/candidates')[0]==401)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--base-url');parser.add_argument('--live-readonly',action='store_true');parser.add_argument('--json-out',required=True);args=parser.parse_args();result=Results();proc=None;log=None
    try:
        if args.live_readonly:
            if not args.base_url:parser.error('--base-url is required with --live-readonly')
            readonly_suite(args.base_url,result)
        else:
            with tempfile.TemporaryDirectory(prefix='ats-one-r8-',ignore_cleanup_errors=True) as temp:
                run=Path(temp);shutil.copy2(ROOT/'server.py',run/'server.py');shutil.copy2(ROOT/'parity_api.py',run/'parity_api.py') if (ROOT/'parity_api.py').exists() else None;shutil.copy2(ROOT/'r14_api.py',run/'r14_api.py') if (ROOT/'r14_api.py').exists() else None;[shutil.copy2(ROOT/f,run/f) for f in ('core_policies.py','persistence_authority.py','r15_migrations.py') if (ROOT/f).exists()];shutil.copytree(ROOT/'web',run/'web');(run/'data').mkdir();port=free_port();base=f'http://127.0.0.1:{port}'
                log=open(run/'server.log','w',encoding='utf-8');env=os.environ.copy();env['ATS_ONE_MODE']='test';env['ATS_ONE_RESET_AUTHORITY_CONFIRMED']='LOCAL_TEST_ONLY';proc=subprocess.Popen([sys.executable,'server.py','--host','127.0.0.1','--port',str(port),'--reset','--quiet'],cwd=run,env=env,stdout=log,stderr=subprocess.STDOUT)
                if not wait_ready(base):raise RuntimeError((run/'server.log').read_text(encoding='utf-8',errors='replace'))
                local_suite(base,run/'data'/'ats_one.db',result)
                proc.terminate();proc.wait(timeout=5);proc=None;log.close()
    except Exception as exc:
        result.check('SUITE_EXECUTION',False,f'{type(exc).__name__}: {exc}')
    finally:
        if proc:
            try:
                if proc.poll() is None:
                    proc.terminate()
                    try:proc.wait(timeout=5)
                    except Exception:
                        proc.kill()
                        try:proc.wait(timeout=5)
                        except Exception:pass
            except Exception:
                pass
        if log:
            try:log.flush()
            except Exception:pass
            try:log.close()
            except Exception:pass
    document=result.document();out_path=Path(args.json_out);out_path.parent.mkdir(parents=True,exist_ok=True);out_path.write_text(json.dumps(document,indent=2),encoding='utf-8');print(f"OVERALL={document['overall']} PASS={document['pass']} FAIL={document['fail']}");return 0 if document['fail']==0 else 1

if __name__=='__main__':raise SystemExit(main())
