#!/usr/bin/env python3
"""Isolated API role/privacy regression: NEVER runs against production."""
from __future__ import annotations
import argparse
from contextlib import closing
import base64
import hashlib
import http.cookiejar
import json
import os
import sqlite3
from pathlib import Path
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
        self.base=base.rstrip('/')
        self.opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    def request(self,path,method='GET',body=None):
        data=json.dumps(body).encode() if body is not None else None
        headers={'Accept':'application/json'}
        if body is not None: headers['Content-Type']='application/json'
        req=urllib.request.Request(self.base+path,data=data,headers=headers,method=method)
        try:
            r=self.opener.open(req,timeout=8)
        except urllib.error.HTTPError as e:
            r=e
        with r:
            body=r.read()
            ctype=r.headers.get('Content-Type','')
            if 'json' in ctype:
                try: body=json.loads(body.decode())
                except Exception: pass
            return r.status,body
    def login(self,role):
        secrets={'admin':('admin@atsone.local','Admin@123'), 'teamlead':('teamlead@atsone.local','Lead@123'),
                 'recruiter':('recruiter@atsone.local','Recruit@123'),'finance':('finance@atsone.local','Finance@123'),
                 'sales':('sales@atsone.local','Sales@123'), 'hr':('hr@atsone.local','HR@123'),
                 'client':('client@atsone.local','Client@123'), 'candidate':('candidate@atsone.local','Candidate@123'),
                 'worker':('worker@atsone.local','Worker@123'), 'supplier':('supplier@atsone.local','Supplier@123'),
                 'approver':('approver@atsone.local','Approve@123')}
        email,pw=secrets[role]
        return self.request('/api/login','POST',{'email':email,'password':pw})

class Acceptance:
    def __init__(self): self.items=[]
    def require(self,label,condition,detail=''):
        ok=bool(condition)
        self.items.append({'id':label,'status':'PASS' if ok else 'FAIL','detail':str(detail)})
        print(f"[{'PASS' if ok else 'FAIL'}] {label}"+(f' :: {detail}' if detail else ''),flush=True)
        return ok
    def summary(self):
        good=sum(x['status']=='PASS' for x in self.items)
        return {'pass':good,'total':len(self.items),'fail':len(self.items)-good,'tests':self.items,
                'result':'PASS' if good==len(self.items) and good>0 else 'FAIL'}

def free_port():
    s=socket.socket();s.bind(('127.0.0.1',0));port=s.getsockname()[1];s.close();return port

def run(repo:Path,output:Path):
    output.mkdir(parents=True,exist_ok=True)
    b=Acceptance()
    if not (repo/'server.py').is_file():raise RuntimeError('SOURCE_NOT_FOUND')
    with tempfile.TemporaryDirectory(prefix='ats-r17-role-audit-') as t:
        temp=Path(t);root=temp/'isolated-app'
        shutil.copytree(repo,root,ignore=shutil.ignore_patterns('.git','data','__pycache__','.pytest_cache','node_modules','.venv'))
        env=os.environ.copy()
        env.update(ATS_ONE_MODE='test',ATS_ONE_RESET_AUTHORITY_CONFIRMED='LOCAL_TEST_ONLY',
                   SUPABASE_URL='',SUPABASE_SERVICE_ROLE_KEY='',RENDER_INSTANCE_ID='')
        port=free_port();base=f'http://127.0.0.1:{port}'
        log_path=output/'r17-isolated-server.log'
        with log_path.open('w',encoding='utf-8') as log:
            p=subprocess.Popen([sys.executable,'-u','server.py','--host','127.0.0.1','--port',str(port),'--reset','--quiet'],
                               cwd=root,env=env,stdout=log,stderr=subprocess.STDOUT)
            try:
                up=False
                for _ in range(180):
                    if p.poll() is not None: break
                    try:
                        status,health=API(base).request('/api/health')
                        if status==200 and isinstance(health,dict) and health.get('ok'):up=True;break
                    except (OSError,TimeoutError):pass
                    time.sleep(.15)
                b.require('ISOLATED_SERVER_READY',up)
                if not up:raise RuntimeError('ISOLATED_SERVER_FAILED; see '+str(log_path))
                status,health=API(base).request('/api/health')
                b.require('NO_REMOTE_DATABASE',status==200 and health.get('persistence')=='local-sqlite')
                everyone=['admin','teamlead','recruiter','sales','hr','finance','client','candidate','worker','supplier','approver']
                clients={name:API(base) for name in everyone}
                for role in everyone:
                    status,_=clients[role].login(role)
                    b.require('LOGIN_'+role.upper(),status==200,status)
                admin=clients['admin'];recruiter=clients['recruiter'];worker=clients['worker'];candidate=clients['candidate']
                outsider=['client','supplier','approver','finance','sales']
                raw=b'R17_PRIVATE_CREDENTIAL_PAYLOAD_DO_NOT_EXPOSE'
                # Candidate 2 is an existing seeded worker. Upload a new binary document to a real candidate record.
                docstatus,doc=admin.request('/api/candidates/2/documents','POST',{
                    'name':'R17 Private Document','file_name':'r17-private.txt','mime_type':'text/plain',
                    'content_base64':base64.b64encode(raw).decode('ascii')})
                docid=doc.get('id') if isinstance(doc,dict) else None
                b.require('DOCUMENT_CREATED_IN_ISOLATED_DB',docstatus==201 and isinstance(docid,int),docstatus)
                if not docid:raise RuntimeError('COULD_NOT_CREATE_TEST_DOCUMENT')
                doc_path=f'/api/candidate-documents/{docid}/download'
                status,data=admin.request(doc_path)
                b.require('ADMIN_DOCUMENT_DOWNLOAD',status==200 and data==raw,status)
                status,data=recruiter.request(doc_path)
                b.require('RECRUITER_DOCUMENT_DOWNLOAD',status==200 and data==raw,status)
                status,data=worker.request(doc_path)
                b.require('WORKER_OWN_DOCUMENT_DOWNLOAD',status==200 and data==raw,status)
                status,_=candidate.request(doc_path)
                b.require('CANDIDATE_CANNOT_READ_OTHER_WORKER_DOCUMENT',status==403,status)
                for role in outsider:
                    status,_=clients[role].request(doc_path)
                    b.require('DOCUMENT_DENIED_'+role.upper(),status==403,status)
                st,onboard=admin.request('/api/onboarding','POST',{'candidate_id':2,'package_name':'R17 Private Onboarding','requirements':[{'type':'Policy','name':'Private R17'}]})
                pid=onboard.get('id') if isinstance(onboard,dict) else None
                b.require('ONBOARDING_CREATED_IN_ISOLATED_DB',st==201 and isinstance(pid,int),st)
                if not pid:raise RuntimeError('ONBOARDING_TEST_SETUP_FAILED')
                path=f'/api/onboarding/{pid}'
                st,item=admin.request(path)
                b.require('ADMIN_ONBOARDING_READ',st==200 and len(item.get('requirements',[]))==1,st)
                st,_=worker.request(path)
                b.require('WORKER_OWN_ONBOARDING',st==200,st)
                st,_=candidate.request(path)
                b.require('CANDIDATE_FOREIGN_ONBOARDING_DENIED',st==403,st)
                for role in ['client','supplier','approver']:
                    st,_=clients[role].request(path)
                    b.require('ONBOARDING_DENIED_'+role.upper(),st==403,st)
                for role in ['worker','candidate','supplier','client']:
                    st,jobs=clients[role].request('/api/jobs')
                    private=('pay_min','pay_max','external_vms_id') if role=='client' else ('bill_min','bill_max','external_vms_id')
                    ok=st==200 and isinstance(jobs,list) and len(jobs)>0 and all(
                        all(field not in j for field in private) for j in jobs)
                    b.require('JOB_LIST_FINANCIAL_FIELDS_REDACTED_'+role.upper(),ok,f'status={st} count={len(jobs) if isinstance(jobs,list) else 0}')
                    if isinstance(jobs,list) and jobs:
                        st,item=clients[role].request(f"/api/jobs/{jobs[0]['id']}")
                        b.require('JOB_DETAIL_REDACTED_'+role.upper(),st==200 and all(k not in item for k in private),st)
                st,jobs=admin.request('/api/jobs')
                b.require('ADMIN_JOBS_PRESERVE_FINANCIAL_FIELDS',st==200 and bool(jobs) and 'bill_max' in jobs[0],st)
                # Rebind only isolated seeded client/approver fixtures to the company with the seeded assignment.
                # This proves rate redaction on non-empty authorized portal results, not a vacuous empty list.
                # sqlite3.Connection context manager commits but DOES NOT close.
                # On Windows, an unclosed handle prevents TemporaryDirectory DB deletion.
                with closing(sqlite3.connect(root/'data'/'ats_one.db')) as conn:
                    conn.execute("UPDATE users SET company_id=2 WHERE email IN ('client@atsone.local','approver@atsone.local')")
                    conn.commit()
                print('R17_FIXTURE_SQLITE_CONNECTION_CLOSED=PASS',flush=True)
                for role in ['client','worker','approver']:
                    st,rows=clients[role].request('/api/timesheets')
                    b.require('TIMESHEET_ROLE_READ_'+role.upper(),st==200 and isinstance(rows,list),st)
                    hidden='bill_rate' if role=='worker' else 'pay_rate'
                    visible='pay_rate' if role=='worker' else 'bill_rate'
                    b.require('TIMESHEET_PRIVATE_RATES_REDACTED_'+role.upper(),st==200 and bool(rows) and all(hidden not in j and visible in j for j in rows),f'rows={len(rows) if isinstance(rows,list) else "invalid"}')
                st,rows=admin.request('/api/timesheets')
                b.require('ADMIN_TIMESHEET_RATES_AVAILABLE',st==200 and bool(rows) and 'pay_rate' in rows[0] and 'bill_rate' in rows[0],st)
                # Supplier/client could previously move a legal draft -> submitted timesheet transition.
                # Create a fresh draft belonging to the seeded worker/assignment IN ISOLATED DATABASE ONLY.
                st,draft=admin.request('/api/timesheets','POST',{'assignment_id':1,'candidate_id':2,
                    'week_start':'2026-12-07','daily':{'Mon':8},'status':'draft'})
                draft_id=draft.get('id') if isinstance(draft,dict) else None
                b.require('DRAFT_TIMESHEET_TEST_FIXTURE',st==201 and isinstance(draft_id,int),st)
                if draft_id:
                    for role in ('supplier','client','approver'):
                        st,_=clients[role].request(f'/api/timesheets/{draft_id}/status','POST',{'status':'submitted'})
                        b.require('UNAUTHORIZED_TIMESHEET_SUBMIT_DENIED_'+role.upper(),st==403,st)
                    st,_=admin.request(f'/api/timesheets/{draft_id}/status','POST',{'status':'submitted'})
                    b.require('AUTHORIZED_ADMIN_TIMESHEET_SUBMIT',st==200,st)
                else:b.require('UNAUTHORIZED_TIMESHEET_SUBMIT_DENIED',False,'no draft created')
                st,_=API(base).request(doc_path)
                b.require('ANONYMOUS_DOCUMENT_DENIED',st==401,st)
                result=b.summary()
                (output/'R17-SECURITY-RESULT.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
                print(f"R17_ROLE_SECURITY_TESTS={result['pass']}/{result['total']}",flush=True)
                print('R17_ROLE_SECURITY='+result['result'],flush=True)
                return 0 if result['result']=='PASS' else 1
            finally:
                # Always reap the *isolated test* process before DB cleanup.
                if p.poll() is None:
                    p.terminate()
                try:
                    p.wait(timeout=12)
                except subprocess.TimeoutExpired:
                    p.kill()
                    p.wait(timeout=12)
                if p.poll() is None:
                    raise RuntimeError('ISOLATED_TEST_SERVER_NOT_TERMINATED')
                print('ISOLATED_TEST_SERVER_REAPED=PASS',flush=True)

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('repo',type=Path);ap.add_argument('evidence',type=Path)
    args=ap.parse_args()
    try:raise SystemExit(run(args.repo.resolve(),args.evidence.resolve()))
    except Exception as exc:
        print('R17_SECURITY_FAIL_CLOSED='+str(exc),file=sys.stderr,flush=True)
        raise
