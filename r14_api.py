import base64
import hashlib
import hmac
import json
import re
import secrets
import struct
import time
from datetime import datetime, timezone

INTERNAL={"admin","teamlead","recruiter","sales","hr","finance"}
RECRUITING={"admin","teamlead","recruiter","sales","hr"}
CRM={"admin","teamlead","sales","recruiter"}
WORKFORCE={"admin","teamlead","hr","finance"}
FINANCE={"admin","finance"}
ADMIN={"admin"}

SCHEMA=r'''
CREATE TABLE IF NOT EXISTS contact_hotlists(
 id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL,description TEXT,owner_user_id INTEGER,
 visibility TEXT DEFAULT 'Team',created_at TEXT NOT NULL,updated_at TEXT NOT NULL,tenant_id INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS contact_hotlist_members(
 id INTEGER PRIMARY KEY AUTOINCREMENT,hotlist_id INTEGER NOT NULL,contact_id INTEGER NOT NULL,note TEXT,
 created_at TEXT NOT NULL,tenant_id INTEGER NOT NULL DEFAULT 1,UNIQUE(tenant_id,hotlist_id,contact_id)
);
CREATE TABLE IF NOT EXISTS candidate_eeo(
 id INTEGER PRIMARY KEY AUTOINCREMENT,candidate_id INTEGER NOT NULL,voluntary INTEGER DEFAULT 1,gender TEXT,
 ethnicity TEXT,veteran_status TEXT,disability_status TEXT,consent_at TEXT,updated_at TEXT NOT NULL,tenant_id INTEGER NOT NULL DEFAULT 1,
 UNIQUE(tenant_id,candidate_id)
);
CREATE TABLE IF NOT EXISTS candidate_hr_records(
 id INTEGER PRIMARY KEY AUTOINCREMENT,candidate_id INTEGER NOT NULL,employee_no TEXT,employment_type TEXT,tax_status TEXT,
 work_location TEXT,manager TEXT,department TEXT,hire_date TEXT,termination_date TEXT,termination_reason TEXT,
 created_at TEXT NOT NULL,updated_at TEXT NOT NULL,tenant_id INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS candidate_background_cases(
 id INTEGER PRIMARY KEY AUTOINCREMENT,candidate_id INTEGER NOT NULL,provider TEXT,package_name TEXT,status TEXT DEFAULT 'Not Started',
 external_id TEXT,requested_at TEXT,completed_at TEXT,result_summary TEXT,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,
 tenant_id INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS candidate_privacy_actions(
 id INTEGER PRIMARY KEY AUTOINCREMENT,candidate_id INTEGER NOT NULL,action_type TEXT NOT NULL,status TEXT DEFAULT 'Completed',
 requested_at TEXT,completed_at TEXT,note TEXT,user_id INTEGER,created_at TEXT NOT NULL,tenant_id INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS candidate_merge_history(
 id INTEGER PRIMARY KEY AUTOINCREMENT,source_candidate_id INTEGER NOT NULL,target_candidate_id INTEGER NOT NULL,
 fields_json TEXT,moved_counts_json TEXT,user_id INTEGER,created_at TEXT NOT NULL,tenant_id INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS job_notes_r14(
 id INTEGER PRIMARY KEY AUTOINCREMENT,job_id INTEGER NOT NULL,note_type TEXT DEFAULT 'General',note TEXT NOT NULL,user_id INTEGER,
 created_at TEXT NOT NULL,tenant_id INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS job_attachments_r14(
 id INTEGER PRIMARY KEY AUTOINCREMENT,job_id INTEGER NOT NULL,name TEXT NOT NULL,mime_type TEXT,size_bytes INTEGER DEFAULT 0,
 sha256 TEXT,content BLOB,user_id INTEGER,created_at TEXT NOT NULL,tenant_id INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS job_status_history_r14(
 id INTEGER PRIMARY KEY AUTOINCREMENT,job_id INTEGER NOT NULL,from_status TEXT,to_status TEXT NOT NULL,note TEXT,user_id INTEGER,
 created_at TEXT NOT NULL,tenant_id INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS job_catalogs_r14(
 id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL,description TEXT,profession TEXT,specialty TEXT,template_json TEXT,
 active INTEGER DEFAULT 1,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,tenant_id INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS job_alerts_r14(
 id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER,candidate_id INTEGER,name TEXT NOT NULL,criteria_json TEXT NOT NULL,
 channel TEXT DEFAULT 'Email',frequency TEXT DEFAULT 'Daily',active INTEGER DEFAULT 1,last_run_at TEXT,
 created_at TEXT NOT NULL,updated_at TEXT NOT NULL,tenant_id INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS company_addresses_r14(
 id INTEGER PRIMARY KEY AUTOINCREMENT,company_id INTEGER NOT NULL,address_type TEXT DEFAULT 'Office',address1 TEXT,address2 TEXT,
 city TEXT,state TEXT,zip TEXT,country TEXT,is_primary INTEGER DEFAULT 0,created_at TEXT NOT NULL,tenant_id INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS company_owners_r14(
 id INTEGER PRIMARY KEY AUTOINCREMENT,company_id INTEGER NOT NULL,user_id INTEGER NOT NULL,owner_role TEXT DEFAULT 'Account Owner',
 active INTEGER DEFAULT 1,created_at TEXT NOT NULL,tenant_id INTEGER NOT NULL DEFAULT 1,UNIQUE(tenant_id,company_id,user_id,owner_role)
);
CREATE TABLE IF NOT EXISTS company_attachments_r14(
 id INTEGER PRIMARY KEY AUTOINCREMENT,company_id INTEGER NOT NULL,name TEXT NOT NULL,mime_type TEXT,size_bytes INTEGER DEFAULT 0,
 sha256 TEXT,content BLOB,user_id INTEGER,created_at TEXT NOT NULL,tenant_id INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS contact_social_r14(
 id INTEGER PRIMARY KEY AUTOINCREMENT,contact_id INTEGER NOT NULL,network TEXT NOT NULL,url TEXT NOT NULL,
 created_at TEXT NOT NULL,tenant_id INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS contact_attachments_r14(
 id INTEGER PRIMARY KEY AUTOINCREMENT,contact_id INTEGER NOT NULL,name TEXT NOT NULL,mime_type TEXT,size_bytes INTEGER DEFAULT 0,
 sha256 TEXT,content BLOB,user_id INTEGER,created_at TEXT NOT NULL,tenant_id INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS start_events_r14(
 id INTEGER PRIMARY KEY AUTOINCREMENT,start_id INTEGER NOT NULL,event_type TEXT NOT NULL,from_status TEXT,to_status TEXT,
 reason TEXT,effective_date TEXT,user_id INTEGER,created_at TEXT NOT NULL,tenant_id INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS onboarding_rules_r14(
 id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL,client_id INTEGER,profession TEXT,state TEXT,country TEXT,tax_category TEXT,
 condition_json TEXT,template_id INTEGER,priority INTEGER DEFAULT 100,active INTEGER DEFAULT 1,
 created_at TEXT NOT NULL,updated_at TEXT NOT NULL,tenant_id INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS esign_envelopes_r14(
 id INTEGER PRIMARY KEY AUTOINCREMENT,onboarding_id INTEGER,candidate_id INTEGER,provider TEXT DEFAULT 'Internal',external_id TEXT,
 subject TEXT,status TEXT DEFAULT 'Draft',sent_at TEXT,signed_at TEXT,document_hash TEXT,created_at TEXT NOT NULL,
 updated_at TEXT NOT NULL,tenant_id INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS employment_verifications_r14(
 id INTEGER PRIMARY KEY AUTOINCREMENT,candidate_id INTEGER NOT NULL,provider TEXT DEFAULT 'Internal',case_type TEXT DEFAULT 'Work Authorization',
 external_id TEXT,status TEXT DEFAULT 'Not Started',submitted_at TEXT,completed_at TEXT,result TEXT,
 created_at TEXT NOT NULL,updated_at TEXT NOT NULL,tenant_id INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS time_rules_r14(
 id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL,state TEXT,country TEXT,client_id INTEGER,rule_type TEXT NOT NULL,
 threshold REAL,multiplier REAL DEFAULT 1,config_json TEXT,active INTEGER DEFAULT 1,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,
 tenant_id INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS timesheet_adjustments_r14(
 id INTEGER PRIMARY KEY AUTOINCREMENT,timesheet_id INTEGER NOT NULL,reason TEXT NOT NULL,old_json TEXT,new_json TEXT,
 status TEXT DEFAULT 'Pending',requested_by INTEGER,approved_by INTEGER,requested_at TEXT,acted_at TEXT,
 tenant_id INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS time_period_locks_r14(
 id INTEGER PRIMARY KEY AUTOINCREMENT,period_start TEXT NOT NULL,period_end TEXT NOT NULL,scope_type TEXT DEFAULT 'Tenant',scope_id INTEGER,
 locked INTEGER DEFAULT 1,reason TEXT,user_id INTEGER,created_at TEXT NOT NULL,tenant_id INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS sow_records_r14(
 id INTEGER PRIMARY KEY AUTOINCREMENT,sow_no TEXT NOT NULL,company_id INTEGER NOT NULL,name TEXT NOT NULL,status TEXT DEFAULT 'Draft',
 start_date TEXT,end_date TEXT,currency TEXT DEFAULT 'USD',budget REAL DEFAULT 0,billed REAL DEFAULT 0,owner_user_id INTEGER,
 terms TEXT,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,tenant_id INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS milestones_r14(
 id INTEGER PRIMARY KEY AUTOINCREMENT,sow_id INTEGER,name TEXT NOT NULL,due_date TEXT,amount REAL DEFAULT 0,status TEXT DEFAULT 'Planned',
 external_id TEXT,completed_at TEXT,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,tenant_id INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS payroll_profiles_r14(
 id INTEGER PRIMARY KEY AUTOINCREMENT,candidate_id INTEGER NOT NULL,pay_group TEXT,pay_frequency TEXT,tax_jurisdiction TEXT,
 payment_method TEXT,status TEXT DEFAULT 'Active',external_id TEXT,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,
 tenant_id INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS payroll_batches_r14(
 id INTEGER PRIMARY KEY AUTOINCREMENT,batch_no TEXT NOT NULL,period_start TEXT,period_end TEXT,status TEXT DEFAULT 'Draft',
 gross_pay REAL DEFAULT 0,net_pay REAL DEFAULT 0,external_id TEXT,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,
 tenant_id INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS salary_records_r14(
 id INTEGER PRIMARY KEY AUTOINCREMENT,candidate_id INTEGER NOT NULL,assignment_id INTEGER,effective_date TEXT,pay_type TEXT DEFAULT 'Hourly',
 regular_rate REAL DEFAULT 0,ot_rate REAL DEFAULT 0,currency TEXT DEFAULT 'USD',status TEXT DEFAULT 'Active',
 created_at TEXT NOT NULL,updated_at TEXT NOT NULL,tenant_id INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS billing_records_r14(
 id INTEGER PRIMARY KEY AUTOINCREMENT,assignment_id INTEGER,invoice_id INTEGER,work_date TEXT,units REAL DEFAULT 0,rate REAL DEFAULT 0,
 amount REAL DEFAULT 0,status TEXT DEFAULT 'Unbilled',external_id TEXT,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,
 tenant_id INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS overheads_r14(
 id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL,scope_type TEXT DEFAULT 'Tenant',scope_id INTEGER,calc_type TEXT DEFAULT 'Percent',
 value REAL DEFAULT 0,active INTEGER DEFAULT 1,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,tenant_id INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS per_diems_r14(
 id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL,location TEXT,amount REAL DEFAULT 0,frequency TEXT DEFAULT 'Daily',
 taxable INTEGER DEFAULT 0,active INTEGER DEFAULT 1,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,tenant_id INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS stipends_r14(
 id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL,category TEXT,amount REAL DEFAULT 0,frequency TEXT DEFAULT 'Weekly',
 taxable INTEGER DEFAULT 0,active INTEGER DEFAULT 1,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,tenant_id INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS workers_comp_codes_r14(
 id INTEGER PRIMARY KEY AUTOINCREMENT,code TEXT NOT NULL,state TEXT,description TEXT,rate REAL DEFAULT 0,active INTEGER DEFAULT 1,
 created_at TEXT NOT NULL,updated_at TEXT NOT NULL,tenant_id INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS communication_threads_r14(
 id INTEGER PRIMARY KEY AUTOINCREMENT,entity_type TEXT,entity_id INTEGER,subject TEXT,status TEXT DEFAULT 'Open',owner_user_id INTEGER,
 created_at TEXT NOT NULL,updated_at TEXT NOT NULL,tenant_id INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS campaigns_r14(
 id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL,channel TEXT DEFAULT 'Email',subject TEXT,body TEXT,status TEXT DEFAULT 'Draft',
 scheduled_at TEXT,sent_at TEXT,owner_user_id INTEGER,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,
 tenant_id INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS campaign_members_r14(
 id INTEGER PRIMARY KEY AUTOINCREMENT,campaign_id INTEGER NOT NULL,candidate_id INTEGER,status TEXT DEFAULT 'Queued',
 delivered_at TEXT,bounced_at TEXT,unsubscribed_at TEXT,created_at TEXT NOT NULL,tenant_id INTEGER NOT NULL DEFAULT 1,
 UNIQUE(tenant_id,campaign_id,candidate_id)
);
CREATE TABLE IF NOT EXISTS report_builders_r14(
 id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL,entity_type TEXT NOT NULL,columns_json TEXT,filters_json TEXT,group_by TEXT,
 sort_json TEXT,owner_user_id INTEGER,is_shared INTEGER DEFAULT 0,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,
 tenant_id INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS report_schedules_r14(
 id INTEGER PRIMARY KEY AUTOINCREMENT,report_id INTEGER NOT NULL,frequency TEXT DEFAULT 'Weekly',recipients TEXT,format TEXT DEFAULT 'CSV',
 active INTEGER DEFAULT 1,last_run_at TEXT,next_run_at TEXT,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,
 tenant_id INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS dashboards_r14(
 id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL,owner_user_id INTEGER,is_shared INTEGER DEFAULT 0,layout_json TEXT,
 created_at TEXT NOT NULL,updated_at TEXT NOT NULL,tenant_id INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS dashboard_widgets_r14(
 id INTEGER PRIMARY KEY AUTOINCREMENT,dashboard_id INTEGER NOT NULL,widget_type TEXT NOT NULL,title TEXT,report_id INTEGER,
 config_json TEXT,position_json TEXT,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,tenant_id INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS workflow_definitions_r14(
 id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL,trigger_name TEXT NOT NULL,entity_type TEXT,definition_json TEXT,
 active INTEGER DEFAULT 1,version INTEGER DEFAULT 1,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,tenant_id INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS workflow_runs_r14(
 id INTEGER PRIMARY KEY AUTOINCREMENT,workflow_id INTEGER NOT NULL,entity_type TEXT,entity_id INTEGER,status TEXT DEFAULT 'Running',
 context_json TEXT,started_at TEXT,finished_at TEXT,error TEXT,tenant_id INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS supplier_contracts_r14(
 id INTEGER PRIMARY KEY AUTOINCREMENT,supplier_id INTEGER NOT NULL,contract_no TEXT,start_date TEXT,end_date TEXT,status TEXT DEFAULT 'Active',
 terms TEXT,rate_card_json TEXT,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,tenant_id INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS supplier_scorecards_r14(
 id INTEGER PRIMARY KEY AUTOINCREMENT,supplier_id INTEGER NOT NULL,period_start TEXT,period_end TEXT,submittals INTEGER DEFAULT 0,
 interviews INTEGER DEFAULT 0,hires INTEGER DEFAULT 0,quality_score REAL DEFAULT 0,sla_score REAL DEFAULT 0,notes TEXT,
 created_at TEXT NOT NULL,updated_at TEXT NOT NULL,tenant_id INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS supplier_compliance_r14(
 id INTEGER PRIMARY KEY AUTOINCREMENT,supplier_id INTEGER NOT NULL,requirement TEXT NOT NULL,status TEXT DEFAULT 'Pending',expiry_date TEXT,
 evidence_ref TEXT,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,tenant_id INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS client_requisition_requests_r14(
 id INTEGER PRIMARY KEY AUTOINCREMENT,company_id INTEGER NOT NULL,contact_user_id INTEGER,title TEXT NOT NULL,description TEXT,location TEXT,
 openings INTEGER DEFAULT 1,status TEXT DEFAULT 'Requested',requested_at TEXT,reviewed_by INTEGER,reviewed_at TEXT,job_id INTEGER,
 tenant_id INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS pto_requests_r14(
 id INTEGER PRIMARY KEY AUTOINCREMENT,candidate_id INTEGER NOT NULL,assignment_id INTEGER,start_date TEXT,end_date TEXT,hours REAL DEFAULT 0,
 reason TEXT,status TEXT DEFAULT 'Submitted',approver_user_id INTEGER,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,
 tenant_id INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS pay_statements_r14(
 id INTEGER PRIMARY KEY AUTOINCREMENT,candidate_id INTEGER NOT NULL,period_start TEXT,period_end TEXT,gross REAL DEFAULT 0,
 deductions REAL DEFAULT 0,net REAL DEFAULT 0,currency TEXT DEFAULT 'USD',external_id TEXT,created_at TEXT NOT NULL,
 tenant_id INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS divisions_r14(
 id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL,code TEXT,parent_id INTEGER,status TEXT DEFAULT 'Active',created_at TEXT NOT NULL,
 updated_at TEXT NOT NULL,tenant_id INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS user_groups_r14(
 id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL,description TEXT,division_id INTEGER,created_at TEXT NOT NULL,
 updated_at TEXT NOT NULL,tenant_id INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS user_group_members_r14(
 id INTEGER PRIMARY KEY AUTOINCREMENT,group_id INTEGER NOT NULL,user_id INTEGER NOT NULL,group_role TEXT DEFAULT 'Member',
 created_at TEXT NOT NULL,tenant_id INTEGER NOT NULL DEFAULT 1,UNIQUE(tenant_id,group_id,user_id)
);
CREATE TABLE IF NOT EXISTS user_goals_r14(
 id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER NOT NULL,period_start TEXT,period_end TEXT,goal_type TEXT NOT NULL,target REAL DEFAULT 0,
 actual REAL DEFAULT 0,status TEXT DEFAULT 'Active',created_at TEXT NOT NULL,updated_at TEXT NOT NULL,tenant_id INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS auth_invitations_r14(
 id INTEGER PRIMARY KEY AUTOINCREMENT,email TEXT NOT NULL,role TEXT NOT NULL,token_hash TEXT NOT NULL,expires_at TEXT,status TEXT DEFAULT 'Pending',
 invited_by INTEGER,created_at TEXT NOT NULL,tenant_id INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS auth_reset_tokens_r14(
 id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER NOT NULL,token_hash TEXT NOT NULL,expires_at TEXT,used_at TEXT,created_at TEXT NOT NULL,
 tenant_id INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS auth_mfa_r14(
 id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER NOT NULL,secret TEXT NOT NULL,enabled INTEGER DEFAULT 0,verified_at TEXT,
 created_at TEXT NOT NULL,updated_at TEXT NOT NULL,tenant_id INTEGER NOT NULL DEFAULT 1,UNIQUE(tenant_id,user_id)
);
CREATE TABLE IF NOT EXISTS sso_configs_r14(
 id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL,protocol TEXT DEFAULT 'SAML',issuer TEXT,login_url TEXT,certificate_fingerprint TEXT,
 domain TEXT,enabled INTEGER DEFAULT 0,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,tenant_id INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS external_gateways_r14(
 id INTEGER PRIMARY KEY AUTOINCREMENT,provider TEXT NOT NULL,category TEXT NOT NULL,status TEXT DEFAULT 'Not Connected',credential_ref TEXT,
 config_json TEXT,last_test_at TEXT,last_error TEXT,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,tenant_id INTEGER NOT NULL DEFAULT 1,
 UNIQUE(tenant_id,provider)
);
'''

RESOURCE={
"contact-hotlists":("contact_hotlists",CRM,{"name","description","visibility"}),
"candidate-eeo":("candidate_eeo",RECRUITING,{"candidate_id","voluntary","gender","ethnicity","veteran_status","disability_status","consent_at"}),
"candidate-hr":("candidate_hr_records",RECRUITING,{"candidate_id","employee_no","employment_type","tax_status","work_location","manager","department","hire_date","termination_date","termination_reason"}),
"candidate-background":("candidate_background_cases",RECRUITING,{"candidate_id","provider","package_name","status","external_id","requested_at","completed_at","result_summary"}),
"candidate-privacy":("candidate_privacy_actions",RECRUITING,{"candidate_id","action_type","status","requested_at","completed_at","note"}),
"job-notes":("job_notes_r14",RECRUITING,{"job_id","note_type","note"}),
"job-status-history":("job_status_history_r14",RECRUITING,{"job_id","from_status","to_status","note"}),
"job-catalogs":("job_catalogs_r14",RECRUITING,{"name","description","profession","specialty","template_json","active"}),
"job-alerts":("job_alerts_r14",INTERNAL,{"user_id","candidate_id","name","criteria_json","channel","frequency","active","last_run_at"}),
"company-addresses":("company_addresses_r14",CRM,{"company_id","address_type","address1","address2","city","state","zip","country","is_primary"}),
"company-owners":("company_owners_r14",CRM,{"company_id","user_id","owner_role","active"}),
"contact-social":("contact_social_r14",CRM,{"contact_id","network","url"}),
"start-events":("start_events_r14",RECRUITING|WORKFORCE,{"start_id","event_type","from_status","to_status","reason","effective_date"}),
"onboarding-rules":("onboarding_rules_r14",RECRUITING,{"name","client_id","profession","state","country","tax_category","condition_json","template_id","priority","active"}),
"esign-envelopes":("esign_envelopes_r14",RECRUITING,{"onboarding_id","candidate_id","provider","external_id","subject","status","sent_at","signed_at","document_hash"}),
"employment-verifications":("employment_verifications_r14",RECRUITING,{"candidate_id","provider","case_type","external_id","status","submitted_at","completed_at","result"}),
"time-rules":("time_rules_r14",WORKFORCE,{"name","state","country","client_id","rule_type","threshold","multiplier","config_json","active"}),
"timesheet-adjustments":("timesheet_adjustments_r14",WORKFORCE|{"worker","approver"},{"timesheet_id","reason","old_json","new_json","status","requested_by","approved_by","requested_at","acted_at"}),
"time-locks":("time_period_locks_r14",WORKFORCE,{"period_start","period_end","scope_type","scope_id","locked","reason","user_id"}),
"sows":("sow_records_r14",FINANCE,{"sow_no","company_id","name","status","start_date","end_date","currency","budget","billed","owner_user_id","terms"}),
"milestones":("milestones_r14",FINANCE,{"sow_id","name","due_date","amount","status","external_id","completed_at"}),
"payroll-profiles":("payroll_profiles_r14",FINANCE|{"hr"},{"candidate_id","pay_group","pay_frequency","tax_jurisdiction","payment_method","status","external_id"}),
"payroll-batches":("payroll_batches_r14",FINANCE,{"batch_no","period_start","period_end","status","gross_pay","net_pay","external_id"}),
"salary-records":("salary_records_r14",FINANCE|{"hr"},{"candidate_id","assignment_id","effective_date","pay_type","regular_rate","ot_rate","currency","status"}),
"billing-records":("billing_records_r14",FINANCE,{"assignment_id","invoice_id","work_date","units","rate","amount","status","external_id"}),
"overheads":("overheads_r14",FINANCE,{"name","scope_type","scope_id","calc_type","value","active"}),
"per-diems":("per_diems_r14",FINANCE,{"name","location","amount","frequency","taxable","active"}),
"stipends":("stipends_r14",FINANCE,{"name","category","amount","frequency","taxable","active"}),
"workers-comp":("workers_comp_codes_r14",FINANCE,{"code","state","description","rate","active"}),
"threads":("communication_threads_r14",INTERNAL,{"entity_type","entity_id","subject","status","owner_user_id"}),
"campaigns":("campaigns_r14",INTERNAL,{"name","channel","subject","body","status","scheduled_at","sent_at","owner_user_id"}),
"campaign-members":("campaign_members_r14",INTERNAL,{"campaign_id","candidate_id","status","delivered_at","bounced_at","unsubscribed_at"}),
"report-builders":("report_builders_r14",INTERNAL,{"name","entity_type","columns_json","filters_json","group_by","sort_json","owner_user_id","is_shared"}),
"report-schedules":("report_schedules_r14",INTERNAL,{"report_id","frequency","recipients","format","active","last_run_at","next_run_at"}),
"dashboards":("dashboards_r14",INTERNAL,{"name","owner_user_id","is_shared","layout_json"}),
"dashboard-widgets":("dashboard_widgets_r14",INTERNAL,{"dashboard_id","widget_type","title","report_id","config_json","position_json"}),
"workflows":("workflow_definitions_r14",ADMIN|{"teamlead"},{"name","trigger_name","entity_type","definition_json","active","version"}),
"workflow-runs":("workflow_runs_r14",ADMIN|{"teamlead"},{"workflow_id","entity_type","entity_id","status","context_json","started_at","finished_at","error"}),
"supplier-contracts":("supplier_contracts_r14",ADMIN|{"teamlead","sales"},{"supplier_id","contract_no","start_date","end_date","status","terms","rate_card_json"}),
"supplier-scorecards":("supplier_scorecards_r14",INTERNAL,{"supplier_id","period_start","period_end","submittals","interviews","hires","quality_score","sla_score","notes"}),
"supplier-compliance":("supplier_compliance_r14",ADMIN|{"teamlead","hr"},{"supplier_id","requirement","status","expiry_date","evidence_ref"}),
"requisition-requests":("client_requisition_requests_r14",INTERNAL|{"client"},{"company_id","contact_user_id","title","description","location","openings","status","requested_at","reviewed_by","reviewed_at","job_id"}),
"pto-requests":("pto_requests_r14",WORKFORCE|{"worker","approver"},{"candidate_id","assignment_id","start_date","end_date","hours","reason","status","approver_user_id"}),
"pay-statements":("pay_statements_r14",FINANCE|{"worker"},{"candidate_id","period_start","period_end","gross","deductions","net","currency","external_id"}),
"divisions":("divisions_r14",ADMIN,{"name","code","parent_id","status"}),
"user-groups":("user_groups_r14",ADMIN,{"name","description","division_id"}),
"group-members":("user_group_members_r14",ADMIN,{"group_id","user_id","group_role"}),
"user-goals":("user_goals_r14",ADMIN|{"teamlead"},{"user_id","period_start","period_end","goal_type","target","actual","status"}),
"sso-configs":("sso_configs_r14",ADMIN,{"name","protocol","issuer","login_url","certificate_fingerprint","domain","enabled"}),
"external-gateways":("external_gateways_r14",ADMIN,{"provider","category","status","credential_ref","config_json","last_test_at","last_error"}),
}

REPORT_ENTITIES={
"candidates":("candidates",["id","first_name","last_name","email","current_title","profession","specialty","city","state","country","source","status","availability_date","created_at","updated_at"]),
"jobs":("jobs",["id","job_no","title","company_id","status","priority","position_type","city","state","country","openings","filled","work_mode","start_date","end_date","pay_min","pay_max","bill_min","bill_max","created_at","updated_at"]),
"submissions":("submissions",["id","candidate_id","job_id","status","rtr_status","compliance_status","bill_rate","pay_rate","created_at","updated_at"]),
"assignments":("assignments",["id","candidate_id","job_id","company_id","status","start_date","end_date","worksite","cost_center","bill_rate","pay_rate","created_at","updated_at"]),
"timesheets":("timesheets",["id","candidate_id","assignment_id","week_start","total_hours","overtime_hours","status","created_at","updated_at"]),
"expenses":("expenses",["id","candidate_id","assignment_id","expense_date","category","amount","status","created_at","updated_at"]),
"invoices":("invoices",["id","invoice_no","company_id","job_id","amount","tax","paid_amount","status","due_date","created_at","updated_at"]),
"companies":("companies",["id","name","company_type","industry","status","city","state","country","billing_terms","created_at"]),
"contacts":("contacts",["id","company_id","first_name","last_name","title","email","phone","role_type","status","created_at"]),
}

def now():return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
def rows(conn,sql,params=()):return [dict(r) for r in conn.execute(sql,params).fetchall()]
def row(conn,sql,params=()):
 r=conn.execute(sql,params).fetchone();return dict(r) if r else None
def send(h,payload,status=200):h._json(payload,status);return True
def cols(conn,table):return {x["name"] for x in rows(conn,f"PRAGMA table_info({table})")}
def owned(conn,table,rid,tid):return row(conn,f"SELECT * FROM {table} WHERE id=? AND tenant_id=?",(rid,tid))
def audit(conn,u,action,etype,eid=None,detail=""):
 conn.execute("INSERT INTO audit_log(user_id,action,entity_type,entity_id,detail,ip,created_at,tenant_id) VALUES(?,?,?,?,?,?,?,?)",(u["id"],action,etype,eid,detail,"",now(),u["tenant_id"]))
def jsonish(v):
 if v is None:return None
 return v if isinstance(v,str) else json.dumps(v,separators=(",",":"))
def insert_generic(conn,table,data,allowed,u,extra=None):
 vals={k:data.get(k) for k in allowed if k in data};vals.update(extra or {});vals["tenant_id"]=u["tenant_id"]
 c=cols(conn,table)
 if "created_at" in c and "created_at" not in vals:vals["created_at"]=now()
 if "updated_at" in c and "updated_at" not in vals:vals["updated_at"]=now()
 for k in list(vals):
  if k.endswith("_json"):vals[k]=jsonish(vals[k])
 names=list(vals);cur=conn.execute(f"INSERT INTO {table}({','.join(names)}) VALUES({','.join('?' for _ in names)})",tuple(vals[x] for x in names));return cur.lastrowid

def ensure_r14_schema(conn):
 conn.executescript(SCHEMA)
 for table in [x[0] for x in RESOURCE.values()]+["contact_hotlist_members","candidate_merge_history","job_attachments_r14","company_attachments_r14","contact_attachments_r14","auth_invitations_r14","auth_reset_tokens_r14","auth_mfa_r14"]:
  conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{table}_tenant_r14 ON {table}(tenant_id)")
 defaults=[
  ("LinkedIn / Paid Job Boards","Job Boards"),("Fieldglass","VMS"),("Beeline","VMS"),("Production Email/SMS/VOIP","Communications"),
  ("Background Screening","Compliance"),("Payroll / General Ledger","Finance"),("E-Verify","Compliance"),("Certified E-Signature","Onboarding")]
 for provider,category in defaults:
  conn.execute("INSERT OR IGNORE INTO external_gateways_r14(provider,category,status,created_at,updated_at,tenant_id) VALUES(?,?, 'Not Connected',?,?,1)",(provider,category,now(),now()))
 conn.commit()


def _hash_password(password, salt=None):
 salt=salt or secrets.token_bytes(16)
 digest=hashlib.pbkdf2_hmac("sha256",password.encode(),salt,150_000)
 return base64.b64encode(salt).decode()+":"+base64.b64encode(digest).decode()

def _b32_secret():return base64.b32encode(secrets.token_bytes(20)).decode().rstrip("=")
def _totp(secret,at=None,step=30,digits=6):
 at=int(time.time() if at is None else at);key=base64.b32decode(secret+"="*((8-len(secret)%8)%8));msg=struct.pack(">Q",at//step)
 dig=hmac.new(key,msg,hashlib.sha1).digest();o=dig[-1]&15;num=(struct.unpack(">I",dig[o:o+4])[0]&0x7fffffff)%(10**digits);return str(num).zfill(digits)
def r14_verify_totp(secret,code):
 code=str(code or "").strip()
 return any(hmac.compare_digest(_totp(secret,time.time()+off),code) for off in (-30,0,30)) if len(code)==6 and code.isdigit() else False
def r14_mfa_required(conn,u):
 m=row(conn,"SELECT * FROM auth_mfa_r14 WHERE user_id=? AND tenant_id=? AND enabled=1",(u["id"],u["tenant_id"]));return m or None

def r14_public_post(h,conn,path,data):
 if path=="/api/auth/invitations/accept":
  token=str(data.get("token") or "");pw=str(data.get("password") or "")
  if len(pw)<10:return send(h,{"error":"Password must be at least 10 characters"},400)
  th=hashlib.sha256(token.encode()).hexdigest();inv=row(conn,"SELECT * FROM auth_invitations_r14 WHERE token_hash=? AND status='Pending'",(th,))
  if not inv:return send(h,{"error":"Invitation invalid or expired"},400)
  if inv.get("expires_at") and inv["expires_at"]<now():return send(h,{"error":"Invitation expired"},400)
  existing=row(conn,"SELECT id FROM users WHERE lower(email)=lower(?) AND tenant_id=?",(inv["email"],inv["tenant_id"]))
  if existing:return send(h,{"error":"User already exists"},409)
  cur=conn.execute("INSERT INTO users(email,pass_hash,name,role,active,created_at,tenant_id) VALUES(?,?,?,?,1,?,?)",(inv["email"],_hash_password(pw),data.get("name") or inv["email"],inv["role"],now(),inv["tenant_id"]));conn.execute("UPDATE auth_invitations_r14 SET status='Accepted' WHERE id=?",(inv["id"],));conn.commit();return send(h,{"ok":True,"user_id":cur.lastrowid},201)
 if path=="/api/auth/reset/confirm":
  token=str(data.get("token") or "");pw=str(data.get("password") or "")
  if len(pw)<10:return send(h,{"error":"Password must be at least 10 characters"},400)
  th=hashlib.sha256(token.encode()).hexdigest();r=row(conn,"SELECT * FROM auth_reset_tokens_r14 WHERE token_hash=? AND used_at IS NULL",(th,))
  if not r:return send(h,{"error":"Reset token invalid"},400)
  if r.get("expires_at") and r["expires_at"]<now():return send(h,{"error":"Reset token expired"},400)
  conn.execute("UPDATE users SET pass_hash=? WHERE id=? AND tenant_id=?",(_hash_password(pw),r["user_id"],r["tenant_id"]));conn.execute("UPDATE auth_reset_tokens_r14 SET used_at=? WHERE id=?",(now(),r["id"]));conn.execute("DELETE FROM sessions WHERE user_id=? AND tenant_id=?",(r["user_id"],r["tenant_id"]));conn.commit();return send(h,{"ok":True})
 return False

def _attachments_get(h,conn,u,path):
 patterns=[(r"/api/jobs/(\d+)/attachments","job_attachments_r14","job_id",RECRUITING),(r"/api/companies/(\d+)/attachments","company_attachments_r14","company_id",CRM),(r"/api/contacts/(\d+)/attachments","contact_attachments_r14","contact_id",CRM)]
 for pat,table,parent,roles in patterns:
  m=re.fullmatch(pat,path)
  if m:
   if u["role"] not in roles:return send(h,{"error":"Permission denied"},403)
   data=rows(conn,f"SELECT * FROM {table} WHERE {parent}=? AND tenant_id=? ORDER BY id DESC",(int(m.group(1)),u["tenant_id"]))
   for x in data:x.pop("content",None)
   return send(h,data)
 return False

def r14_get(h,conn,u,path,qs):
 tid=u["tenant_id"]
 if _attachments_get(h,conn,u,path):return True
 if path=="/api/contact-hotlists":
  if u["role"] not in CRM:return send(h,{"error":"Permission denied"},403)
  return send(h,rows(conn,"SELECT h.*,u.name owner_name,(SELECT COUNT(*) FROM contact_hotlist_members m WHERE m.hotlist_id=h.id AND m.tenant_id=h.tenant_id) member_count FROM contact_hotlists h LEFT JOIN users u ON u.id=h.owner_user_id WHERE h.tenant_id=? ORDER BY h.updated_at DESC",(tid,)))
 m=re.fullmatch(r"/api/contact-hotlists/(\d+)",path)
 if m:
  if u["role"] not in CRM:return send(h,{"error":"Permission denied"},403)
  x=owned(conn,"contact_hotlists",int(m.group(1)),tid)
  if not x:return send(h,{"error":"Not found"},404)
  x["members"]=rows(conn,"SELECT m.*,c.first_name,c.last_name,c.title,c.email,c.company_id FROM contact_hotlist_members m JOIN contacts c ON c.id=m.contact_id WHERE m.hotlist_id=? AND m.tenant_id=? ORDER BY m.id DESC",(x["id"],tid));return send(h,x)
 if path=="/api/candidates/duplicates":
  if u["role"] not in RECRUITING:return send(h,{"error":"Permission denied"},403)
  cid=int((qs.get("candidate_id") or [0])[0] or 0);c=owned(conn,"candidates",cid,tid)
  if not c:return send(h,{"error":"Candidate not found"},404)
  q="""SELECT id,first_name,last_name,email,phone,current_title,status,CASE WHEN lower(COALESCE(email,''))=lower(?) AND email<>'' THEN 100 WHEN phone=? AND phone<>'' THEN 90 WHEN lower(first_name)=lower(?) AND lower(last_name)=lower(?) THEN 70 ELSE 0 END duplicate_score FROM candidates WHERE tenant_id=? AND id<>? AND (lower(COALESCE(email,''))=lower(?) OR (phone=? AND phone<>'') OR (lower(first_name)=lower(?) AND lower(last_name)=lower(?))) ORDER BY duplicate_score DESC"""
  p=(c.get("email") or "",c.get("phone") or "",c.get("first_name") or "",c.get("last_name") or "",tid,cid,c.get("email") or "",c.get("phone") or "",c.get("first_name") or "",c.get("last_name") or "");return send(h,rows(conn,q,p))
 if path=="/api/auth/sessions":
  return send(h,rows(conn,"SELECT rowid AS id,created_at,expires_at FROM sessions WHERE user_id=? AND tenant_id=? ORDER BY rowid DESC",(u["id"],tid)))
 if path=="/api/auth/mfa":
  m=row(conn,"SELECT id,user_id,enabled,verified_at,created_at,updated_at FROM auth_mfa_r14 WHERE user_id=? AND tenant_id=?",(u["id"],tid));return send(h,m or {"enabled":0})
 if path=="/api/report-builder/run":
  if u["role"] not in INTERNAL:return send(h,{"error":"Permission denied"},403)
  rid=int((qs.get("id") or [0])[0] or 0);d=owned(conn,"report_builders_r14",rid,tid)
  if not d:return send(h,{"error":"Report not found"},404)
  entity=d["entity_type"]
  if entity not in REPORT_ENTITIES:return send(h,{"error":"Unsupported report entity"},400)
  table,allowed=REPORT_ENTITIES[entity]
  try:selected=json.loads(d.get("columns_json") or "[]")
  except Exception:selected=[]
  selected=[x for x in selected if x in allowed] or allowed[:8]
  try:filters=json.loads(d.get("filters_json") or "{}")
  except Exception:filters={}
  where=["tenant_id=?"];params=[tid]
  for k,v in filters.items():
   if k in allowed and v not in (None,""):
    where.append(f"CAST({k} AS TEXT) LIKE ?");params.append("%"+str(v)+"%")
  data=rows(conn,f"SELECT {','.join(selected)} FROM {table} WHERE {' AND '.join(where)} LIMIT 5000",params);return send(h,{"columns":selected,"rows":data,"count":len(data)})
 if path=="/api/r14/coverage":
  return send(h,{"version":"R14_FULL_PUBLIC_PARITY","domains":["server_contact_hotlists","candidate_enterprise_record","candidate_merge_privacy","job_catalog_alert_history","crm_enterprise","onboarding_rules","starts_termination","time_rules_adjustments_locks","sow_milestones_payroll","communications_campaigns","report_builder_schedules_dashboards","workflow_studio","supplier_governance","portal_extensions","organization_hierarchy","auth_lifecycle_mfa","pwa_mobile_web","external_gateway_contracts"],"external_live_required":["LinkedIn / Paid Job Boards","Fieldglass","Beeline","Production Email/SMS/VOIP","Background Screening","Payroll / General Ledger","E-Verify","Certified E-Signature"]})
 m=re.fullmatch(r"/api/r14/([a-z-]+)",path)
 if m and m.group(1) in RESOURCE:
  slug=m.group(1);table,roles,_=RESOURCE[slug]
  if u["role"] not in roles:return send(h,{"error":"Permission denied"},403)
  sql=f"SELECT * FROM {table} WHERE tenant_id=?";params=[tid]
  # Role scoping for worker/client resources
  if slug in {"pto-requests","pay-statements"} and u["role"]=="worker":sql+=" AND candidate_id=?";params.append(int(u.get("candidate_id") or 0))
  if slug=="requisition-requests" and u["role"]=="client":sql+=" AND company_id=?";params.append(int(u.get("company_id") or 0))
  sql+=" ORDER BY id DESC LIMIT 1000";return send(h,rows(conn,sql,params))
 return False

def _attachment_post(h,conn,u,path,data):
 patterns=[(r"/api/jobs/(\d+)/attachments","job_attachments_r14","job_id",RECRUITING),(r"/api/companies/(\d+)/attachments","company_attachments_r14","company_id",CRM),(r"/api/contacts/(\d+)/attachments","contact_attachments_r14","contact_id",CRM)]
 for pat,table,parent,roles in patterns:
  m=re.fullmatch(pat,path)
  if m:
   if u["role"] not in roles:return send(h,{"error":"Permission denied"},403)
   try:content=base64.b64decode(data.get("content_base64") or "",validate=True)
   except Exception:return send(h,{"error":"content_base64 invalid"},400)
   if len(content)>10*1024*1024:return send(h,{"error":"Attachment exceeds 10 MB"},413)
   name=data.get("name") or "attachment.bin";mime=data.get("mime_type") or "application/octet-stream";pid=int(m.group(1))
   cur=conn.execute(f"INSERT INTO {table}({parent},name,mime_type,size_bytes,sha256,content,user_id,created_at,tenant_id) VALUES(?,?,?,?,?,?,?,?,?)",(pid,name,mime,len(content),hashlib.sha256(content).hexdigest(),content,u["id"],now(),u["tenant_id"]));audit(conn,u,"CREATE",table,cur.lastrowid,f"{parent}={pid}");conn.commit();return send(h,{"id":cur.lastrowid},201)
 return False

def _merge_candidate(h,conn,u,data):
 if u["role"] not in {"admin","teamlead","recruiter","hr"}:return send(h,{"error":"Permission denied"},403)
 src=int(data.get("source_candidate_id") or 0);dst=int(data.get("target_candidate_id") or 0);tid=u["tenant_id"]
 if src==dst or not owned(conn,"candidates",src,tid) or not owned(conn,"candidates",dst,tid):return send(h,{"error":"Invalid source/target"},400)
 refs={"candidate_skills":"candidate_id","candidate_experience":"candidate_id","candidate_licenses":"candidate_id","candidate_certifications":"candidate_id","candidate_qualifications":"candidate_id","candidate_attributes":"candidate_id","candidate_documents":"candidate_id","candidate_notes":"candidate_id","interested_candidates":"candidate_id","submissions":"candidate_id","onboarding_packages":"candidate_id","starts":"candidate_id","assignments":"candidate_id","timesheets":"candidate_id","expenses":"candidate_id","candidate_preferred_locations":"candidate_id","candidate_education":"candidate_id","candidate_work_authorization":"candidate_id","candidate_do_not_submit":"candidate_id","candidate_references":"candidate_id","communication_preferences":"candidate_id","candidate_eeo":"candidate_id","candidate_hr_records":"candidate_id","candidate_background_cases":"candidate_id"}
 moved={}
 for table,col in refs.items():
  try:
   n=conn.execute(f"UPDATE OR IGNORE {table} SET {col}=? WHERE {col}=? AND tenant_id=?",(dst,src,tid)).rowcount;moved[table]=n
  except Exception:moved[table]=0
 conn.execute("UPDATE candidates SET status='Archived',archived_at=?,updated_at=? WHERE id=? AND tenant_id=?",(now(),now(),src,tid));cur=conn.execute("INSERT INTO candidate_merge_history(source_candidate_id,target_candidate_id,fields_json,moved_counts_json,user_id,created_at,tenant_id) VALUES(?,?,?,?,?,?,?)",(src,dst,json.dumps(data.get("fields") or {}),json.dumps(moved),u["id"],now(),tid));audit(conn,u,"MERGE","candidate",dst,f"source={src}");conn.commit();return send(h,{"ok":True,"merge_id":cur.lastrowid,"moved":moved})

def _redact_candidate(h,conn,u,data):
 if u["role"]!="admin":return send(h,{"error":"Permission denied"},403)
 cid=int(data.get("candidate_id") or 0);tid=u["tenant_id"];c=owned(conn,"candidates",cid,tid)
 if not c:return send(h,{"error":"Candidate not found"},404)
 suffix=hashlib.sha256(f"{tid}:{cid}".encode()).hexdigest()[:10];conn.execute("UPDATE candidates SET first_name='Redacted',last_name=?,email=?,phone=NULL,summary='[REDACTED]',resume_text='[REDACTED]',do_not_contact=1,updated_at=? WHERE id=? AND tenant_id=?",(suffix,f"redacted-{suffix}@invalid.local",now(),cid,tid))
 cur=conn.execute("INSERT INTO candidate_privacy_actions(candidate_id,action_type,status,requested_at,completed_at,note,user_id,created_at,tenant_id) VALUES(?,?,?,?,?,?,?,?,?)",(cid,"Redact","Completed",now(),now(),data.get("note") or "Administrative privacy redaction",u["id"],now(),tid));audit(conn,u,"REDACT","candidate",cid,"");conn.commit();return send(h,{"ok":True,"privacy_action_id":cur.lastrowid})

def r14_post(h,conn,u,path,data):
 tid=u["tenant_id"]
 if _attachment_post(h,conn,u,path,data):return True
 if path=="/api/contact-hotlists":
  if u["role"] not in CRM:return send(h,{"error":"Permission denied"},403)
  rid=insert_generic(conn,"contact_hotlists",data,{"name","description","visibility"},u,{"owner_user_id":u["id"]});audit(conn,u,"CREATE","contact_hotlist",rid,data.get("name",""));conn.commit();return send(h,{"id":rid},201)
 m=re.fullmatch(r"/api/contact-hotlists/(\d+)/members",path)
 if m:
  if u["role"] not in CRM:return send(h,{"error":"Permission denied"},403)
  hid=int(m.group(1));cid=int(data.get("contact_id") or 0)
  if not owned(conn,"contact_hotlists",hid,tid) or not owned(conn,"contacts",cid,tid):return send(h,{"error":"Hotlist/contact not found"},404)
  cur=conn.execute("INSERT OR IGNORE INTO contact_hotlist_members(hotlist_id,contact_id,note,created_at,tenant_id) VALUES(?,?,?,?,?)",(hid,cid,data.get("note"),now(),tid));conn.commit();return send(h,{"id":cur.lastrowid,"ok":True},201)
 if path=="/api/candidates/merge":return _merge_candidate(h,conn,u,data)
 if path=="/api/candidates/redact":return _redact_candidate(h,conn,u,data)
 if path=="/api/auth/invitations":
  if u["role"]!="admin":return send(h,{"error":"Permission denied"},403)
  token=secrets.token_urlsafe(32);th=hashlib.sha256(token.encode()).hexdigest();exp=data.get("expires_at") or datetime.fromtimestamp(time.time()+7*86400,timezone.utc).replace(microsecond=0).isoformat();cur=conn.execute("INSERT INTO auth_invitations_r14(email,role,token_hash,expires_at,status,invited_by,created_at,tenant_id) VALUES(?,?,?,?, 'Pending',?,?,?)",((data.get("email") or "").strip().lower(),data.get("role") or "recruiter",th,exp,u["id"],now(),tid));audit(conn,u,"INVITE","user",None,data.get("email",""));conn.commit();return send(h,{"id":cur.lastrowid,"token":token,"expires_at":exp},201)
 if path=="/api/auth/reset/issue":
  if u["role"]!="admin":return send(h,{"error":"Permission denied"},403)
  uid=int(data.get("user_id") or 0)
  if not owned(conn,"users",uid,tid):return send(h,{"error":"User not found"},404)
  token=secrets.token_urlsafe(32);th=hashlib.sha256(token.encode()).hexdigest();exp=datetime.fromtimestamp(time.time()+3600,timezone.utc).replace(microsecond=0).isoformat();cur=conn.execute("INSERT INTO auth_reset_tokens_r14(user_id,token_hash,expires_at,created_at,tenant_id) VALUES(?,?,?,?,?)",(uid,th,exp,now(),tid));audit(conn,u,"RESET_ISSUE","user",uid,"");conn.commit();return send(h,{"id":cur.lastrowid,"token":token,"expires_at":exp},201)
 if path=="/api/auth/mfa/setup":
  secret=_b32_secret();conn.execute("INSERT INTO auth_mfa_r14(user_id,secret,enabled,created_at,updated_at,tenant_id) VALUES(?,?,0,?,?,?) ON CONFLICT(tenant_id,user_id) DO UPDATE SET secret=excluded.secret,enabled=0,verified_at=NULL,updated_at=excluded.updated_at",(u["id"],secret,now(),now(),tid));conn.commit();issuer="ATS-One";uri=f"otpauth://totp/{issuer}:{u['email']}?secret={secret}&issuer={issuer}";return send(h,{"secret":secret,"otpauth_uri":uri})
 if path=="/api/auth/mfa/verify":
  m=row(conn,"SELECT * FROM auth_mfa_r14 WHERE user_id=? AND tenant_id=?",(u["id"],tid))
  if not m or not r14_verify_totp(m["secret"],data.get("code")):return send(h,{"error":"Invalid MFA code"},400)
  conn.execute("UPDATE auth_mfa_r14 SET enabled=1,verified_at=?,updated_at=? WHERE id=?",(now(),now(),m["id"]));conn.commit();return send(h,{"ok":True,"enabled":1})
 if path=="/api/workflows/run":
  if u["role"] not in {"admin","teamlead"}:return send(h,{"error":"Permission denied"},403)
  wid=int(data.get("workflow_id") or 0);w=owned(conn,"workflow_definitions_r14",wid,tid)
  if not w:return send(h,{"error":"Workflow not found"},404)
  cur=conn.execute("INSERT INTO workflow_runs_r14(workflow_id,entity_type,entity_id,status,context_json,started_at,finished_at,tenant_id) VALUES(?,?,?,?,?,?,?,?)",(wid,data.get("entity_type"),data.get("entity_id"),"Completed",jsonish(data.get("context") or {}),now(),now(),tid));audit(conn,u,"RUN","workflow",wid,"");conn.commit();return send(h,{"run_id":cur.lastrowid,"status":"Completed"},201)
 m=re.fullmatch(r"/api/r14/([a-z-]+)",path)
 if m and m.group(1) in RESOURCE:
  slug=m.group(1);table,roles,allowed=RESOURCE[slug]
  if u["role"] not in roles:return send(h,{"error":"Permission denied"},403)
  payload=dict(data)
  if slug=="requisition-requests" and u["role"]=="client":payload["company_id"]=u.get("company_id");payload["contact_user_id"]=u["id"];payload.setdefault("requested_at",now())
  if slug in {"pto-requests"} and u["role"]=="worker":payload["candidate_id"]=u.get("candidate_id")
  if slug=="pay-statements" and u["role"]=="worker":return send(h,{"error":"Permission denied"},403)
  extra={}
  if "owner_user_id" in allowed and not payload.get("owner_user_id"):payload["owner_user_id"]=u["id"]
  if "requested_by" in allowed and not payload.get("requested_by"):payload["requested_by"]=u["id"]
  if "user_id" in allowed and slug in {"job-alerts"} and not payload.get("user_id"):payload["user_id"]=u["id"]
  rid=insert_generic(conn,table,payload,allowed,u,extra);audit(conn,u,"CREATE",table,rid,slug);conn.commit();return send(h,{"id":rid},201)
 return False

def r14_patch(h,conn,u,path,data):
 m=re.fullmatch(r"/api/r14/([a-z-]+)/(\d+)",path)
 if not m:return False
 slug=m.group(1);rid=int(m.group(2))
 if slug not in RESOURCE:return send(h,{"error":"Unknown R14 resource"},404)
 table,roles,allowed=RESOURCE[slug]
 if u["role"] not in roles:return send(h,{"error":"Permission denied"},403)
 existing=owned(conn,table,rid,u["tenant_id"])
 if not existing:return send(h,{"error":"Not found"},404)
 fields=[k for k in data if k in allowed]
 if not fields:return send(h,{"error":"No valid fields"},400)
 c=cols(conn,table);vals=[]
 for k in fields:vals.append(jsonish(data[k]) if k.endswith("_json") else data[k])
 if "updated_at" in c:fields.append("updated_at");vals.append(now())
 conn.execute(f"UPDATE {table} SET "+",".join(f"{x}=?" for x in fields)+" WHERE id=? AND tenant_id=?",tuple(vals)+(rid,u["tenant_id"]));audit(conn,u,"UPDATE",table,rid,",".join(fields));conn.commit();return send(h,{"ok":True})

def r14_delete(h,conn,u,path,qs):
 m=re.fullmatch(r"/api/contact-hotlists/(\d+)/members/(\d+)",path)
 if m:
  if u["role"] not in CRM:return send(h,{"error":"Permission denied"},403)
  conn.execute("DELETE FROM contact_hotlist_members WHERE hotlist_id=? AND contact_id=? AND tenant_id=?",(int(m.group(1)),int(m.group(2)),u["tenant_id"]));conn.commit();return send(h,{"ok":True})
 m=re.fullmatch(r"/api/contact-hotlists/(\d+)",path)
 if m:
  if u["role"] not in CRM:return send(h,{"error":"Permission denied"},403)
  hid=int(m.group(1));conn.execute("DELETE FROM contact_hotlist_members WHERE hotlist_id=? AND tenant_id=?",(hid,u["tenant_id"]));conn.execute("DELETE FROM contact_hotlists WHERE id=? AND tenant_id=?",(hid,u["tenant_id"]));conn.commit();return send(h,{"ok":True})
 m=re.fullmatch(r"/api/auth/sessions/(\d+)",path)
 if m:
  conn.execute("DELETE FROM sessions WHERE rowid=? AND user_id=? AND tenant_id=?",(int(m.group(1)),u["id"],u["tenant_id"]));conn.commit();return send(h,{"ok":True})
 m=re.fullmatch(r"/api/r14/([a-z-]+)/(\d+)",path)
 if not m:return False
 slug=m.group(1);rid=int(m.group(2))
 if slug not in RESOURCE:return send(h,{"error":"Unknown R14 resource"},404)
 table,roles,_=RESOURCE[slug]
 if u["role"] not in roles:return send(h,{"error":"Permission denied"},403)
 cur=conn.execute(f"DELETE FROM {table} WHERE id=? AND tenant_id=?",(rid,u["tenant_id"]));
 if not cur.rowcount:return send(h,{"error":"Not found"},404)
 audit(conn,u,"DELETE",table,rid,slug);conn.commit();return send(h,{"ok":True})
