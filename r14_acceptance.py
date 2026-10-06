#!/usr/bin/env python3
import argparse, http.cookiejar, json, os, shutil, socket, subprocess, sys, tempfile, time, urllib.error, urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parent

def source_app_version():
 server=(ROOT/'server.py').read_text(encoding='utf-8-sig')
 for line in server.splitlines():
  line=line.strip()
  if line.startswith('APP_VERSION') and '=' in line:return line.split('=',1)[1].strip().strip(chr(34)).strip(chr(39))
 raise RuntimeError('APP_VERSION not found')

def free_port():
 s=socket.socket();s.bind(('127.0.0.1',0));p=s.getsockname()[1];s.close();return p
class Client:
 def __init__(self,base):
  self.base=base;self.jar=http.cookiejar.CookieJar();self.opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))
 def req(self,path,method='GET',body=None,expect=None):
  data=None if body is None else json.dumps(body).encode();req=urllib.request.Request(self.base+path,data=data,method=method,headers={'Content-Type':'application/json'})
  try:
   with self.opener.open(req,timeout=5) as r:raw=r.read();status=r.status
  except urllib.error.HTTPError as e:status=e.code;raw=e.read()
  val=json.loads(raw.decode() or '{}') if raw else {}
  if expect is not None and status!=expect:raise AssertionError(f'{method} {path}: expected {expect}, got {status}: {val}')
  if expect is None and not 200<=status<300:raise AssertionError(f'{method} {path}: HTTP {status}: {val}')
  return val,status

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--json-out');args=ap.parse_args();results=[]
 def check(name,fn):
  try:fn();results.append((name,'PASS',''))
  except Exception as e:results.append((name,'FAIL',str(e)))
 with tempfile.TemporaryDirectory(prefix='ats-r14-') as td:
  t=Path(td)
  for f in ['server.py','parity_api.py','r14_api.py','core_policies.py','persistence_authority.py','r15_migrations.py']:
   shutil.copy2(ROOT/f,t/f)
  shutil.copytree(ROOT/'web',t/'web')
  port=free_port();env=os.environ.copy()
  for k in ['SUPABASE_URL','SUPABASE_SERVICE_ROLE_KEY','SUPABASE_BUCKET','SUPABASE_DB_OBJECT','RENDER']:env.pop(k,None)
  env['ATS_ONE_MODE']='test'
  env['ATS_ONE_RESET_AUTHORITY_CONFIRMED']='LOCAL_TEST_ONLY'
  server_log=open(t/'r14-server.log','w',encoding='utf-8');p=subprocess.Popen([sys.executable,'server.py','--host','127.0.0.1','--port',str(port),'--quiet'],cwd=t,env=env,stdout=server_log,stderr=subprocess.STDOUT,text=True)
  try:
   base=f'http://127.0.0.1:{port}'
   for _ in range(100):
    try:
     with urllib.request.urlopen(base+'/api/health',timeout=1) as r:
      if r.status==200:break
    except Exception:time.sleep(.1)
   else:server_log.flush();raise RuntimeError('server did not start: '+((t/'r14-server.log').read_text(encoding='utf-8',errors='replace')[-4000:]))
   c=Client(base)
   check('HEALTH_VERSION',lambda: (_ for _ in ()).throw(AssertionError(c.req('/api/health')[0])) if c.req('/api/health')[0].get('version')!=source_app_version() else None)
   check('LOGIN_ADMIN',lambda:c.req('/api/login','POST',{'email':'admin@atsone.local','password':'Admin@123'},200))
   cov=c.req('/api/r14/coverage')[0];check('COVERAGE_DOMAINS',lambda: (_ for _ in ()).throw(AssertionError(cov)) if len(cov.get('domains',[]))<18 else None)
   # IDs from seed
   cand=1;contact=1;company=1;job=1;start=1;timesheet=1;supplier=1
   def create(path,body):return c.req(path,'POST',body,201)[0]
   check('CONTACT_HOTLIST',lambda:create('/api/contact-hotlists',{'name':'R14 QA','description':'server backed','visibility':'Team'}))
   hl=c.req('/api/contact-hotlists')[0][0]['id'];check('CONTACT_HOTLIST_MEMBER',lambda:create(f'/api/contact-hotlists/{hl}/members',{'contact_id':contact}))
   check('CANDIDATE_EEO',lambda:create('/api/r14/candidate-eeo',{'candidate_id':cand,'voluntary':1,'gender':'Prefer not to say'}))
   check('CANDIDATE_HR',lambda:create('/api/r14/candidate-hr',{'candidate_id':cand,'employee_no':'QA-1','employment_type':'Contract'}))
   check('CANDIDATE_BACKGROUND',lambda:create('/api/r14/candidate-background',{'candidate_id':cand,'provider':'Internal QA','package_name':'Basic','status':'Not Started'}))
   check('CANDIDATE_DUPLICATES',lambda:c.req(f'/api/candidates/duplicates?candidate_id={cand}'))
   check('JOB_CATALOG',lambda:create('/api/r14/job-catalogs',{'name':'Java Catalog','profession':'Software Engineer','specialty':'Backend'}))
   check('JOB_ALERT',lambda:create('/api/r14/job-alerts',{'name':'Java Alert','criteria_json':{'title':'Java'},'channel':'Email','frequency':'Daily'}))
   check('JOB_NOTE',lambda:create('/api/r14/job-notes',{'job_id':job,'note':'QA note'}))
   check('ONBOARDING_RULE',lambda:create('/api/r14/onboarding-rules',{'name':'NY Rule','state':'NY','condition_json':{},'priority':10}))
   check('ESIGN_RECORD',lambda:create('/api/r14/esign-envelopes',{'candidate_id':cand,'provider':'Internal','subject':'QA Envelope'}))
   check('EMPLOYMENT_VERIFICATION',lambda:create('/api/r14/employment-verifications',{'candidate_id':cand,'provider':'Internal','case_type':'Work Authorization'}))
   check('START_EVENT',lambda:create('/api/r14/start-events',{'start_id':start,'event_type':'Status Change','to_status':'active'}))
   check('TIME_RULE',lambda:create('/api/r14/time-rules',{'name':'Daily OT','rule_type':'Daily OT','threshold':8,'multiplier':1.5}))
   check('TIME_ADJUSTMENT',lambda:create('/api/r14/timesheet-adjustments',{'timesheet_id':timesheet,'reason':'QA','status':'Pending'}))
   check('TIME_LOCK',lambda:create('/api/r14/time-locks',{'period_start':'2026-09-01','period_end':'2026-09-30','scope_type':'Tenant','locked':1}))
   sow=create('/api/r14/sows',{'sow_no':'SOW-QA','company_id':company,'name':'QA SOW','budget':10000});check('SOW',lambda:None)
   check('MILESTONE',lambda:create('/api/r14/milestones',{'sow_id':sow['id'],'name':'M1','amount':1000,'status':'Planned'}))
   check('PAYROLL_BATCH',lambda:create('/api/r14/payroll-batches',{'batch_no':'PB-QA','status':'Draft','gross_pay':1000,'net_pay':800}))
   check('SALARY_RECORD',lambda:create('/api/r14/salary-records',{'candidate_id':cand,'effective_date':'2026-10-01','regular_rate':50,'ot_rate':75}))
   check('OVERHEAD',lambda:create('/api/r14/overheads',{'name':'Burden','calc_type':'Percent','value':12.5}))
   check('PER_DIEM',lambda:create('/api/r14/per-diems',{'name':'Meal','location':'NY','amount':65}))
   check('STIPEND',lambda:create('/api/r14/stipends',{'name':'Phone','category':'Equipment','amount':50}))
   check('WORKERS_COMP',lambda:create('/api/r14/workers-comp',{'code':'QA-8810','state':'NY','description':'Clerical','rate':0.15}))
   check('THREAD',lambda:create('/api/r14/threads',{'entity_type':'candidate','entity_id':cand,'subject':'QA Thread'}))
   check('CAMPAIGN',lambda:create('/api/r14/campaigns',{'name':'QA Campaign','channel':'Email','subject':'Hello','body':'QA'}))
   report=create('/api/r14/report-builders',{'name':'QA Candidate Report','entity_type':'candidates','columns_json':['id','first_name','last_name','status'],'filters_json':{}});check('REPORT_DEF',lambda:None)
   check('REPORT_RUN',lambda:c.req('/api/report-builder/run?id='+str(report['id'])))
   check('DASHBOARD',lambda:create('/api/r14/dashboards',{'name':'QA Dashboard','is_shared':1,'layout_json':{}}))
   wf=create('/api/r14/workflows',{'name':'QA Workflow','trigger_name':'manual','entity_type':'candidate','definition_json':{'steps':[]}});check('WORKFLOW_DEF',lambda:None)
   check('WORKFLOW_RUN',lambda:c.req('/api/workflows/run','POST',{'workflow_id':wf['id'],'entity_type':'candidate','entity_id':cand},201))
   check('SUPPLIER_CONTRACT',lambda:create('/api/r14/supplier-contracts',{'supplier_id':supplier,'contract_no':'SC-QA','status':'Active'}))
   check('SUPPLIER_SCORECARD',lambda:create('/api/r14/supplier-scorecards',{'supplier_id':supplier,'quality_score':95,'sla_score':98}))
   check('SUPPLIER_COMPLIANCE',lambda:create('/api/r14/supplier-compliance',{'supplier_id':supplier,'requirement':'Insurance','status':'Pending'}))
   check('DIVISION',lambda:create('/api/r14/divisions',{'name':'QA Division','code':'QA','status':'Active'}))
   check('USER_GROUP',lambda:create('/api/r14/user-groups',{'name':'QA Group'}))
   check('USER_GOAL',lambda:create('/api/r14/user-goals',{'user_id':1,'goal_type':'Submittals','target':20,'actual':5}))
   check('MFA_SETUP',lambda:c.req('/api/auth/mfa/setup','POST',{}))
   check('SESSIONS',lambda:c.req('/api/auth/sessions'))
   gateways=c.req('/api/r14/external-gateways')[0];check('EXTERNAL_GATES_TRUTHFUL',lambda: (_ for _ in ()).throw(AssertionError(gateways)) if len(gateways)<8 or any(x.get('status')=='Connected' for x in gateways) else None)
   # Candidate role denied admin resources
   c.req('/api/logout','POST',{},200);c.req('/api/login','POST',{'email':'candidate@atsone.local','password':'Candidate@123'},200)
   check('ROLE_DENY_FINANCE',lambda:c.req('/api/r14/sows',expect=403))
  finally:
   try:
    if p.poll() is None:
     p.terminate()
     try:p.wait(timeout=5)
     except Exception:
      p.kill()
      try:p.wait(timeout=5)
      except Exception:pass
   finally:
    try:server_log.flush()
    except Exception:pass
    try:server_log.close()
    except Exception:pass
 doc={'overall':'PASS' if all(x[1]=='PASS' for x in results) else 'FAIL','pass':sum(x[1]=='PASS' for x in results),'fail':sum(x[1]=='FAIL' for x in results),'results':[{'name':a,'status':b,'detail':d} for a,b,d in results]}
 print(json.dumps(doc,indent=2))
 if args.json_out:
  out=Path(args.json_out);out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(doc,indent=2),encoding='utf-8')
 return 0 if doc['fail']==0 else 1
if __name__=='__main__':raise SystemExit(main())
