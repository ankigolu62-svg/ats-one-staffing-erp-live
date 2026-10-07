import base64
import hashlib
import hmac
import json
import re
import secrets
import sqlite3
import struct
import time
from datetime import datetime, timezone

INTERNAL={"admin","teamlead","recruiter","sales","hr","finance"}
RECRUITING={"admin","teamlead","recruiter","sales","hr"}
CRM={"admin","teamlead","sales","recruiter"}
WORKFORCE={"admin","teamlead","hr","finance"}
FINANCE={"admin","finance"}
ADMIN={"admin"}
HR_PRIVACY={"admin","hr"}
SCREENING={"admin","teamlead","recruiter","hr"}

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
"candidate-eeo":("candidate_eeo",HR_PRIVACY,{"candidate_id","voluntary","gender","ethnicity","veteran_status","disability_status","consent_at"}),
"candidate-hr":("candidate_hr_records",HR_PRIVACY,{"candidate_id","employee_no","employment_type","tax_status","work_location","manager","department","hire_date","termination_date","termination_reason"}),
"candidate-background":("candidate_background_cases",SCREENING,{"candidate_id","provider","package_name","status","external_id","requested_at","completed_at","result_summary"}),
"candidate-privacy":("candidate_privacy_actions",ADMIN,{"candidate_id","action_type","status","requested_at","completed_at","note"}),
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
"submissions":("submissions",["id","candidate_id","job_id","status","rtr_status","compliance_status","client_rate","candidate_rate","created_at","updated_at"]),
"assignments":("assignments",["id","candidate_id","job_id","company_id","status","start_date","end_date","worksite","cost_center","bill_rate","pay_rate","created_at","updated_at"]),
"timesheets":("timesheets",["id","candidate_id","assignment_id","week_start","total_hours","overtime_hours","status","created_at","updated_at"]),
"expenses":("expenses",["id","candidate_id","assignment_id","expense_date","category","amount","status","created_at","updated_at"]),
"invoices":("invoices",["id","invoice_no","company_id","job_id","amount","tax","paid_amount","status","due_date","created_at","updated_at"]),
"companies":("companies",["id","name","company_type","industry","status","city","state","country","billing_terms","created_at"]),
"contacts":("contacts",["id","company_id","first_name","last_name","title","email","phone","role_type","status","created_at"]),
}

# Declarative relationship and lifecycle policy.  SQLite foreign keys cannot be
# retrofitted safely onto the legacy schema in place, so every generic R14 write
# is required to pass this tenant-aware application-level relationship gate.
PARENT_REFS={
 "candidate-eeo":{"candidate_id":"candidates"},
 "candidate-hr":{"candidate_id":"candidates"},
 "candidate-background":{"candidate_id":"candidates"},
 "candidate-privacy":{"candidate_id":"candidates"},
 "job-notes":{"job_id":"jobs"},
 "job-status-history":{"job_id":"jobs"},
 "job-alerts":{"user_id":"users","candidate_id":"candidates"},
 "company-addresses":{"company_id":"companies"},
 "company-owners":{"company_id":"companies","user_id":"users"},
 "contact-social":{"contact_id":"contacts"},
 "start-events":{"start_id":"starts"},
 "onboarding-rules":{"client_id":"companies"},
 "esign-envelopes":{"onboarding_id":"onboarding_packages","candidate_id":"candidates"},
 "employment-verifications":{"candidate_id":"candidates"},
 "time-rules":{"client_id":"companies"},
 "timesheet-adjustments":{"timesheet_id":"timesheets","requested_by":"users","approved_by":"users"},
 "time-locks":{"user_id":"users"},
 "sows":{"company_id":"companies","owner_user_id":"users"},
 "milestones":{"sow_id":"sow_records_r14"},
 "payroll-profiles":{"candidate_id":"candidates"},
 "salary-records":{"candidate_id":"candidates","assignment_id":"assignments"},
 "billing-records":{"assignment_id":"assignments","invoice_id":"invoices"},
 "job-alerts":{"user_id":"users","candidate_id":"candidates"},
 "campaign-members":{"campaign_id":"campaigns_r14","candidate_id":"candidates"},
 "report-schedules":{"report_id":"report_builders_r14"},
 "dashboards":{"owner_user_id":"users"},
 "dashboard-widgets":{"dashboard_id":"dashboards_r14","report_id":"report_builders_r14"},
 "workflow-runs":{"workflow_id":"workflow_definitions_r14"},
 "supplier-contracts":{"supplier_id":"suppliers"},
 "supplier-scorecards":{"supplier_id":"suppliers"},
 "supplier-compliance":{"supplier_id":"suppliers"},
 "requisition-requests":{"company_id":"companies","contact_user_id":"users","reviewed_by":"users","job_id":"jobs"},
 "pto-requests":{"candidate_id":"candidates","assignment_id":"assignments","approver_user_id":"users"},
 "pay-statements":{"candidate_id":"candidates"},
 "divisions":{"parent_id":"divisions_r14"},
 "user-groups":{"division_id":"divisions_r14"},
 "group-members":{"group_id":"user_groups_r14","user_id":"users"},
 "user-goals":{"user_id":"users"},
}

ENTITY_REGISTRY={
 "candidate":"candidates","candidates":"candidates","job":"jobs","jobs":"jobs",
 "company":"companies","companies":"companies","contact":"contacts","contacts":"contacts",
 "submission":"submissions","submissions":"submissions","assignment":"assignments","assignments":"assignments",
 "timesheet":"timesheets","timesheets":"timesheets","invoice":"invoices","invoices":"invoices",
 "start":"starts","starts":"starts","supplier":"suppliers","suppliers":"suppliers",
 "user":"users","users":"users","sow":"sow_records_r14","workflow":"workflow_definitions_r14",
}

# These fields express state-machine outcomes and may not be changed through the
# generic CRUD endpoint.  Dedicated services (or the workflow runner below)
# must establish the transition and its evidence.
PROTECTED_PATCH_FIELDS={
 "candidate-background":{"status","requested_at","completed_at","result_summary"},
 "candidate-privacy":{"action_type","status","requested_at","completed_at"},
 "job-status-history":{"from_status","to_status"},
 "start-events":{"event_type","from_status","to_status","effective_date"},
 "esign-envelopes":{"status","sent_at","signed_at","document_hash"},
 "timesheet-adjustments":{"status","approved_by","acted_at"},
 "time-locks":{"locked"},
 "sows":{"status","billed"},
 "milestones":{"status","completed_at"},
 "payroll-profiles":{"status"},
 "payroll-batches":{"status","gross_pay","net_pay"},
 "salary-records":{"status"},
 "billing-records":{"status","amount"},
 "campaigns":{"status","scheduled_at","sent_at"},
 "campaign-members":{"status","delivered_at","bounced_at","unsubscribed_at"},
 "report-schedules":{"active","last_run_at","next_run_at"},
 "workflow-runs":{"status","started_at","finished_at","error"},
 "requisition-requests":{"status","reviewed_by","reviewed_at","job_id"},
 "pto-requests":{"status","approver_user_id"},
 "pay-statements":{"candidate_id","period_start","period_end","gross","deductions","net","currency","external_id"},
 "sso-configs":{"enabled"},
 "external-gateways":{"status","last_test_at","last_error"},
}

IMMUTABLE_RESOURCES={"candidate-privacy","job-status-history","start-events","workflow-runs","pay-statements"}

CONFIGURATION_ONLY={
 "dashboards":"Layout configuration only.",
 "dashboard-widgets":"Layout configuration only.",
 "sso-configs":"Configuration only; SSO authentication is not implemented.",
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

def _table_exists(conn,table):
 return bool(row(conn,"SELECT 1 ok FROM sqlite_master WHERE type='table' AND name=?",(table,)))

def _parent_is_eligible(parent):
 if parent.get("archived_at") not in (None,""):return False
 if "active" in parent and parent.get("active") in (0,"0",False):return False
 status=str(parent.get("status") or "").strip().lower()
 return status not in {"archived","deleted","inactive","cancelled","canceled","terminated","closed","void"}

def _parent_owned_active(conn,table,rid,tid):
 if not rid or not _table_exists(conn,table):return None
 parent=owned(conn,table,int(rid),tid)
 return parent if parent and _parent_is_eligible(parent) else None

def _validate_parent_refs(conn,slug,payload,tid):
 for field,table in PARENT_REFS.get(slug,{}).items():
  if field not in payload or payload.get(field) in (None,""):continue
  try:rid=int(payload[field])
  except (TypeError,ValueError):return f"{field} must be an integer"
  if not _parent_owned_active(conn,table,rid,tid):return f"{field} does not reference an active tenant-owned record"
 return None

def _validate_entity_ref(conn,entity_type,entity_id,tid,required=False):
 et=str(entity_type or "").strip().lower();eid=entity_id
 if not et and eid in (None,"",0,"0"):
  return "entity_type and entity_id are required" if required else None
 if not et or eid in (None,"",0,"0"):return "entity_type and entity_id must be supplied together"
 table=ENTITY_REGISTRY.get(et)
 if not table:return "Unsupported entity_type"
 try:eid=int(eid)
 except (TypeError,ValueError):return "entity_id must be an integer"
 if not _parent_owned_active(conn,table,eid,tid):return "Entity does not reference an active tenant-owned record"
 return None

def _validate_polymorphic_refs(conn,slug,payload,tid,existing=None):
 if slug not in {"threads","workflow-runs"}:return None
 entity_type=payload.get("entity_type",(existing or {}).get("entity_type"))
 entity_id=payload.get("entity_id",(existing or {}).get("entity_id"))
 return _validate_entity_ref(conn,entity_type,entity_id,tid,required=False)

def _object_scope_allowed(slug,record,u):
 if u.get("role")=="worker" and slug in {"pto-requests","pay-statements"}:
  return int(record.get("candidate_id") or 0)==int(u.get("candidate_id") or 0)
 if u.get("role")=="client" and slug=="requisition-requests":
  return int(record.get("company_id") or 0)==int(u.get("company_id") or 0)
 return True

def _configuration_guard(slug,payload):
 if slug=="sso-configs" and payload.get("enabled") not in (None,0,"0",False):
  return "SSO cannot be enabled until an authentication flow is connected"
 return None

def _decorate_configuration_only(slug,items):
 message=CONFIGURATION_ONLY.get(slug)
 if message:
  for item in items:item["capability_status"]=message
 return items

def _session_public_id(token):return hashlib.sha256(str(token).encode()).hexdigest()

def _session_rows(conn,u):
 data=rows(conn,"SELECT token,created_at,expires_at FROM sessions WHERE user_id=? AND tenant_id=? ORDER BY created_at DESC",(u["id"],u["tenant_id"]))
 for item in data:item["id"]=_session_public_id(item.pop("token"))
 return data

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

def _verify_password(password, encoded):
 try:
  s,d=encoded.split(":",1);salt=base64.b64decode(s);expected=base64.b64decode(d)
  got=hashlib.pbkdf2_hmac("sha256",str(password or "").encode(),salt,150_000)
  return hmac.compare_digest(expected,got)
 except Exception:return False

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
  existing=row(conn,"SELECT * FROM users WHERE lower(email)=lower(?) AND tenant_id=?",(inv["email"],inv["tenant_id"]))
  if existing and int(existing.get("active") or 0)==1:return send(h,{"error":"User already exists"},409)
  if existing:
   conn.execute("UPDATE users SET pass_hash=?,name=?,role=?,active=1 WHERE id=? AND tenant_id=?",(_hash_password(pw),data.get("name") or existing.get("name") or inv["email"],inv["role"],existing["id"],inv["tenant_id"]));uid=existing["id"]
  else:
   cur=conn.execute("INSERT INTO users(email,pass_hash,name,role,active,created_at,tenant_id) VALUES(?,?,?,?,1,?,?)",(inv["email"],_hash_password(pw),data.get("name") or inv["email"],inv["role"],now(),inv["tenant_id"]));uid=cur.lastrowid
  conn.execute("UPDATE auth_invitations_r14 SET status='Accepted' WHERE id=?",(inv["id"],));conn.commit();return send(h,{"ok":True,"user_id":uid},201)
 if path=="/api/auth/reset/confirm":
  token=str(data.get("token") or "");pw=str(data.get("password") or "")
  if len(pw)<10:return send(h,{"error":"Password must be at least 10 characters"},400)
  th=hashlib.sha256(token.encode()).hexdigest();r=row(conn,"SELECT * FROM auth_reset_tokens_r14 WHERE token_hash=? AND used_at IS NULL",(th,))
  if not r:return send(h,{"error":"Reset token invalid"},400)
  if r.get("expires_at") and r["expires_at"]<now():return send(h,{"error":"Reset token expired"},400)
  conn.execute("UPDATE users SET pass_hash=? WHERE id=? AND tenant_id=?",(_hash_password(pw),r["user_id"],r["tenant_id"]));conn.execute("UPDATE auth_reset_tokens_r14 SET used_at=? WHERE id=?",(now(),r["id"]));conn.execute("DELETE FROM sessions WHERE user_id=? AND tenant_id=?",(r["user_id"],r["tenant_id"]));conn.commit();return send(h,{"ok":True})
 return False

def _attachments_get(h,conn,u,path):
 patterns=[(r"/api/jobs/(\d+)/attachments(?:/(\d+))?","job_attachments_r14","job_id","jobs",RECRUITING),(r"/api/companies/(\d+)/attachments(?:/(\d+))?","company_attachments_r14","company_id","companies",CRM),(r"/api/contacts/(\d+)/attachments(?:/(\d+))?","contact_attachments_r14","contact_id","contacts",CRM)]
 for pat,table,parent,parent_table,roles in patterns:
  m=re.fullmatch(pat,path)
  if m:
   if u["role"] not in roles:return send(h,{"error":"Permission denied"},403)
   pid=int(m.group(1));parent_row=owned(conn,parent_table,pid,u["tenant_id"])
   if not parent_row:return send(h,{"error":"Parent not found"},404)
   if m.group(2):
    item=row(conn,f"SELECT * FROM {table} WHERE id=? AND {parent}=? AND tenant_id=?",(int(m.group(2)),pid,u["tenant_id"]))
    if not item:return send(h,{"error":"Attachment not found"},404)
    content=item.pop("content",b"") or b""
    if not hmac.compare_digest(hashlib.sha256(content).hexdigest(),str(item.get("sha256") or "")):
     return send(h,{"error":"Attachment integrity verification failed"},500)
    item["content_base64"]=base64.b64encode(content).decode();item["content_disposition"]="attachment"
    audit(conn,u,"DOWNLOAD",table,item["id"],f"{parent}={pid}");conn.commit();return send(h,item)
   data=rows(conn,f"SELECT * FROM {table} WHERE {parent}=? AND tenant_id=? ORDER BY id DESC",(pid,u["tenant_id"]))
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
  return send(h,_session_rows(conn,u))
 if path=="/api/auth/mfa":
  m=row(conn,"SELECT id,user_id,enabled,verified_at,created_at,updated_at FROM auth_mfa_r14 WHERE user_id=? AND tenant_id=?",(u["id"],tid));return send(h,m or {"enabled":0})
 if path=="/api/report-builder/run":
  if u["role"] not in INTERNAL:return send(h,{"error":"Permission denied"},403)
  rid=int((qs.get("id") or [0])[0] or 0);d=owned(conn,"report_builders_r14",rid,tid)
  if not d:return send(h,{"error":"Report not found"},404)
  entity=d["entity_type"]
  if entity not in REPORT_ENTITIES:return send(h,{"error":"Unsupported report entity"},400)
  table,allowed=REPORT_ENTITIES[entity];actual=cols(conn,table);allowed=[name for name in allowed if name in actual]
  if not allowed:return send(h,{"error":"Report entity has no available columns"},409)
  try:selected=json.loads(d.get("columns_json") or "[]")
  except Exception:selected=[]
  aliases={"bill_rate":"client_rate","pay_rate":"candidate_rate"} if entity=="submissions" else {}
  selected=[aliases.get(x,x) for x in selected];selected=[x for x in selected if x in allowed] or allowed[:8]
  try:filters=json.loads(d.get("filters_json") or "{}")
  except Exception:filters={}
  where=["tenant_id=?"];params=[tid]
  for k,v in filters.items():
   if k in allowed and v not in (None,""):
    where.append(f"CAST({k} AS TEXT) LIKE ?");params.append("%"+str(v)+"%")
  data=rows(conn,f"SELECT {','.join(selected)} FROM {table} WHERE {' AND '.join(where)} LIMIT 5000",params);return send(h,{"columns":selected,"rows":data,"count":len(data)})
 if path=="/api/r14/coverage":
  return send(h,{"version":"R15_MASTER_CORRECTNESS","domains":["server_contact_hotlists","candidate_enterprise_record","candidate_merge_privacy","job_catalog_alert_history","crm_enterprise","onboarding_rules","starts_termination","time_rules_adjustments_locks","sow_milestones_payroll","communications_campaigns","report_builder_schedules_dashboards","workflow_studio","supplier_governance","portal_extensions","organization_hierarchy","auth_lifecycle_mfa","pwa_mobile_web","external_gateway_contracts"],"configuration_only":CONFIGURATION_ONLY,"external_live_required":["LinkedIn / Paid Job Boards","Fieldglass","Beeline","Production Email/SMS/VOIP","Background Screening","Payroll / General Ledger","E-Verify","Certified E-Signature"]})
 m=re.fullmatch(r"/api/r14/([a-z-]+)",path)
 if m and m.group(1) in RESOURCE:
  slug=m.group(1);table,roles,_=RESOURCE[slug]
  candidate_self_read=(u["role"]=="candidate" and slug in {"candidate-eeo","employment-verifications"})
  supplier_self_read=(u["role"]=="supplier" and slug in {"supplier-contracts","supplier-scorecards","supplier-compliance"})
  if u["role"] not in roles and not candidate_self_read and not supplier_self_read:return send(h,{"error":"Permission denied"},403)
  sql=f"SELECT * FROM {table} WHERE tenant_id=?";params=[tid]
  # Role scoping for worker/client resources
  if slug in {"pto-requests","pay-statements"} and u["role"]=="worker":sql+=" AND candidate_id=?";params.append(int(u.get("candidate_id") or 0))
  if slug=="requisition-requests" and u["role"]=="client":sql+=" AND company_id=?";params.append(int(u.get("company_id") or 0))
  if candidate_self_read:sql+=" AND candidate_id=?";params.append(int(u.get("candidate_id") or 0))
  if supplier_self_read:sql+=" AND supplier_id=?";params.append(int(u.get("supplier_id") or 0))
  sql+=" ORDER BY id DESC LIMIT 1000";data=_decorate_configuration_only(slug,rows(conn,sql,params))
  if slug in {"candidate-eeo","candidate-hr","candidate-privacy"}:
   audit(conn,u,"READ",table,None,"collection");conn.commit()
  return send(h,data)
 return False

def _attachment_post(h,conn,u,path,data):
 patterns=[(r"/api/jobs/(\d+)/attachments","job_attachments_r14","job_id","jobs",RECRUITING),(r"/api/companies/(\d+)/attachments","company_attachments_r14","company_id","companies",CRM),(r"/api/contacts/(\d+)/attachments","contact_attachments_r14","contact_id","contacts",CRM)]
 for pat,table,parent,parent_table,roles in patterns:
  m=re.fullmatch(pat,path)
  if m:
   if u["role"] not in roles:return send(h,{"error":"Permission denied"},403)
   try:content=base64.b64decode(data.get("content_base64") or "",validate=True)
   except Exception:return send(h,{"error":"content_base64 invalid"},400)
   if len(content)>10*1024*1024:return send(h,{"error":"Attachment exceeds 10 MB"},413)
   name=str(data.get("name") or "attachment.bin").strip();mime=str(data.get("mime_type") or "application/octet-stream").strip().lower();pid=int(m.group(1))
   if not _parent_owned_active(conn,parent_table,pid,u["tenant_id"]):return send(h,{"error":"Parent not found or inactive"},404)
   if not name or len(name)>255 or "\x00" in name:return send(h,{"error":"Attachment name invalid"},400)
   if mime in {"text/html","image/svg+xml","application/javascript","text/javascript","application/x-msdownload","application/x-powershell"}:return send(h,{"error":"Attachment content type is not allowed"},415)
   cur=conn.execute(f"INSERT INTO {table}({parent},name,mime_type,size_bytes,sha256,content,user_id,created_at,tenant_id) VALUES(?,?,?,?,?,?,?,?,?)",(pid,name,mime,len(content),hashlib.sha256(content).hexdigest(),content,u["id"],now(),u["tenant_id"]));audit(conn,u,"CREATE",table,cur.lastrowid,f"{parent}={pid}");conn.commit();return send(h,{"id":cur.lastrowid},201)
 return False

def _merge_candidate(h,conn,u,data):
 if u["role"] not in {"admin","teamlead","recruiter","hr"}:return send(h,{"error":"Permission denied"},403)
 src=int(data.get("source_candidate_id") or 0);dst=int(data.get("target_candidate_id") or 0);tid=u["tenant_id"]
 source=owned(conn,"candidates",src,tid);target=owned(conn,"candidates",dst,tid)
 if src==dst or not source or not target or not _parent_is_eligible(source) or not _parent_is_eligible(target):return send(h,{"error":"Invalid or inactive source/target"},400)
 refs={"candidate_skills":"candidate_id","candidate_experience":"candidate_id","candidate_licenses":"candidate_id","candidate_certifications":"candidate_id","candidate_qualifications":"candidate_id","candidate_attributes":"candidate_id","candidate_documents":"candidate_id","candidate_notes":"candidate_id","interested_candidates":"candidate_id","submissions":"candidate_id","onboarding_packages":"candidate_id","starts":"candidate_id","assignments":"candidate_id","timesheets":"candidate_id","expenses":"candidate_id","candidate_preferred_locations":"candidate_id","candidate_education":"candidate_id","candidate_work_authorization":"candidate_id","candidate_do_not_submit":"candidate_id","candidate_references":"candidate_id","communication_preferences":"candidate_id","candidate_eeo":"candidate_id","candidate_hr_records":"candidate_id","candidate_background_cases":"candidate_id"}
 applicable=[(table,col) for table,col in refs.items() if _table_exists(conn,table) and col in cols(conn,table) and "tenant_id" in cols(conn,table)]
 conn.execute("SAVEPOINT candidate_merge_preflight")
 try:
  for table,col in applicable:conn.execute(f"UPDATE {table} SET {col}=? WHERE {col}=? AND tenant_id=?",(dst,src,tid))
  conn.execute("ROLLBACK TO candidate_merge_preflight");conn.execute("RELEASE candidate_merge_preflight")
 except sqlite3.IntegrityError as exc:
  conn.execute("ROLLBACK TO candidate_merge_preflight");conn.execute("RELEASE candidate_merge_preflight")
  return send(h,{"error":"Candidate merge has child conflicts","detail":str(exc)},409)
 except Exception:
  conn.execute("ROLLBACK TO candidate_merge_preflight");conn.execute("RELEASE candidate_merge_preflight")
  return send(h,{"error":"Candidate merge preflight failed"},500)
 moved={};conn.execute("SAVEPOINT candidate_merge_apply")
 try:
  for table,col in applicable:moved[table]=conn.execute(f"UPDATE {table} SET {col}=? WHERE {col}=? AND tenant_id=?",(dst,src,tid)).rowcount
  residual={table:row(conn,f"SELECT COUNT(*) count FROM {table} WHERE {col}=? AND tenant_id=?",(src,tid))["count"] for table,col in applicable}
  residual={table:count for table,count in residual.items() if count}
  if residual:raise RuntimeError("residual candidate children")
  stamp=now();conn.execute("UPDATE candidates SET status='Archived',archived_at=?,updated_at=? WHERE id=? AND tenant_id=?",(stamp,stamp,src,tid))
  cur=conn.execute("INSERT INTO candidate_merge_history(source_candidate_id,target_candidate_id,fields_json,moved_counts_json,user_id,created_at,tenant_id) VALUES(?,?,?,?,?,?,?)",(src,dst,json.dumps(data.get("fields") or {}),json.dumps(moved,sort_keys=True),u["id"],stamp,tid));audit(conn,u,"MERGE","candidate",dst,f"source={src}")
  conn.execute("RELEASE candidate_merge_apply");conn.commit();return send(h,{"ok":True,"merge_id":cur.lastrowid,"moved":moved})
 except Exception:
  conn.execute("ROLLBACK TO candidate_merge_apply");conn.execute("RELEASE candidate_merge_apply")
  return send(h,{"error":"Candidate merge failed without modifying either candidate"},409)

def _redact_candidate(h,conn,u,data):
 if u["role"]!="admin":return send(h,{"error":"Permission denied"},403)
 cid=int(data.get("candidate_id") or 0);tid=u["tenant_id"];c=owned(conn,"candidates",cid,tid)
 if not c:return send(h,{"error":"Candidate not found"},404)
 suffix=hashlib.sha256(f"{tid}:{cid}".encode()).hexdigest()[:12];stamp=now();conn.execute("SAVEPOINT candidate_redaction")
 try:
  document_ids=[]
  if _table_exists(conn,"candidate_documents"):
   document_ids=[x["id"] for x in rows(conn,"SELECT id FROM candidate_documents WHERE candidate_id=? AND tenant_id=?",(cid,tid))]
  if document_ids and _table_exists(conn,"candidate_document_versions"):
   marks=",".join("?" for _ in document_ids);conn.execute(f"DELETE FROM candidate_document_versions WHERE document_id IN ({marks}) AND tenant_id=?",tuple(document_ids)+(tid,))
  delete_tables=["candidate_skills","candidate_experience","candidate_licenses","candidate_certifications","candidate_qualifications","candidate_attributes","candidate_documents","candidate_notes","candidate_preferred_locations","candidate_education","candidate_work_authorization","candidate_do_not_submit","candidate_references","communication_preferences","candidate_eeo","candidate_hr_records","candidate_background_cases","candidate_privacy_actions"]
  erased={}
  for table in delete_tables:
   if _table_exists(conn,table) and "candidate_id" in cols(conn,table) and "tenant_id" in cols(conn,table):erased[table]=conn.execute(f"DELETE FROM {table} WHERE candidate_id=? AND tenant_id=?",(cid,tid)).rowcount
  if _table_exists(conn,"communications"):
   erased["communications"]=conn.execute("UPDATE communications SET subject='[REDACTED]',body='[REDACTED]' WHERE lower(entity_type) IN ('candidate','candidates') AND entity_id=? AND tenant_id=?",(cid,tid)).rowcount
  if _table_exists(conn,"tasks"):
   erased["tasks"]=conn.execute("UPDATE tasks SET title='[REDACTED]' WHERE lower(entity_type) IN ('candidate','candidates') AND entity_id=? AND tenant_id=?",(cid,tid)).rowcount
  linked_users=rows(conn,"SELECT id FROM users WHERE candidate_id=? AND tenant_id=?",(cid,tid))
  for linked in linked_users:
   uid=linked["id"];conn.execute("UPDATE users SET email=?,name='Redacted user',candidate_id=NULL,active=0 WHERE id=? AND tenant_id=?",(f"redacted-{suffix}-{uid}@invalid.local",uid,tid));conn.execute("DELETE FROM sessions WHERE user_id=? AND tenant_id=?",(uid,tid))
  conn.execute("UPDATE candidates SET first_name='Redacted',last_name=?,email=?,phone=NULL,city=NULL,state=NULL,country=NULL,zip=NULL,profession=NULL,specialty=NULL,current_title=NULL,availability_date=NULL,pay_min=NULL,pay_max=NULL,source=NULL,summary='[REDACTED]',resume_text='[REDACTED]',consent_sms=0,consent_email=0,do_not_contact=1,status='Archived',archived_at=?,updated_at=? WHERE id=? AND tenant_id=?",(suffix,f"redacted-{suffix}@invalid.local",stamp,stamp,cid,tid))
  residual=sum(row(conn,f"SELECT COUNT(*) count FROM {table} WHERE candidate_id=? AND tenant_id=?",(cid,tid))["count"] for table in delete_tables if _table_exists(conn,table) and "candidate_id" in cols(conn,table) and "tenant_id" in cols(conn,table))
  if residual:raise RuntimeError("redaction verification failed")
  cur=conn.execute("INSERT INTO candidate_privacy_actions(candidate_id,action_type,status,requested_at,completed_at,note,user_id,created_at,tenant_id) VALUES(?,?,?,?,?,?,?,?,?)",(cid,"Redact","Completed",stamp,stamp,"Privacy redaction completed; operational finance records retained under policy.",u["id"],stamp,tid));audit(conn,u,"REDACT","candidate",cid,json.dumps(erased,sort_keys=True))
  conn.execute("RELEASE candidate_redaction");conn.commit();return send(h,{"ok":True,"privacy_action_id":cur.lastrowid,"erased":erased})
 except Exception:
  conn.execute("ROLLBACK TO candidate_redaction");conn.execute("RELEASE candidate_redaction")
  return send(h,{"error":"Candidate redaction failed without partial completion"},500)

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
  current=row(conn,"SELECT * FROM auth_mfa_r14 WHERE user_id=? AND tenant_id=?",(u["id"],tid))
  if current and int(current.get("enabled") or 0)==1:
   account=row(conn,"SELECT pass_hash FROM users WHERE id=? AND tenant_id=?",(u["id"],tid))
   password_ok=bool(account and _verify_password(data.get("current_password"),account.get("pass_hash") or ""))
   code_ok=r14_verify_totp(current.get("secret") or "",data.get("current_code"))
   if not (password_ok and code_ok):return send(h,{"error":"Current password and MFA code are required to re-enroll MFA"},403)
  secret=_b32_secret();conn.execute("INSERT INTO auth_mfa_r14(user_id,secret,enabled,created_at,updated_at,tenant_id) VALUES(?,?,0,?,?,?) ON CONFLICT(tenant_id,user_id) DO UPDATE SET secret=excluded.secret,enabled=0,verified_at=NULL,updated_at=excluded.updated_at",(u["id"],secret,now(),now(),tid));audit(conn,u,"MFA_REENROLL" if current else "MFA_SETUP","auth_mfa",u["id"],"");conn.commit();issuer="ATS-One";uri=f"otpauth://totp/{issuer}:{u['email']}?secret={secret}&issuer={issuer}";return send(h,{"secret":secret,"otpauth_uri":uri})
 if path=="/api/auth/mfa/verify":
  m=row(conn,"SELECT * FROM auth_mfa_r14 WHERE user_id=? AND tenant_id=?",(u["id"],tid))
  if not m or not r14_verify_totp(m["secret"],data.get("code")):return send(h,{"error":"Invalid MFA code"},400)
  conn.execute("UPDATE auth_mfa_r14 SET enabled=1,verified_at=?,updated_at=? WHERE id=?",(now(),now(),m["id"]));conn.commit();return send(h,{"ok":True,"enabled":1})
 if path=="/api/workflows/run":
  if u["role"] not in {"admin","teamlead"}:return send(h,{"error":"Permission denied"},403)
  wid=int(data.get("workflow_id") or 0);w=owned(conn,"workflow_definitions_r14",wid,tid)
  if not w:return send(h,{"error":"Workflow not found"},404)
  if not int(w.get("active") or 0):return send(h,{"error":"Workflow is inactive"},409)
  try:definition=json.loads(w.get("definition_json") or "{}")
  except Exception:return send(h,{"error":"Workflow definition is invalid JSON"},400)
  steps=definition.get("steps") if isinstance(definition,dict) else None
  if not isinstance(steps,list):return send(h,{"error":"Workflow definition requires a steps array"},400)
  entity_type=data.get("entity_type") or w.get("entity_type");entity_id=data.get("entity_id")
  if entity_id not in (None,""):
   err=_validate_entity_ref(conn,entity_type,entity_id,tid,required=True)
   if err:return send(h,{"error":err},400)
  started=now();cur=conn.execute("INSERT INTO workflow_runs_r14(workflow_id,entity_type,entity_id,status,context_json,started_at,tenant_id) VALUES(?,?,?,?,?,?,?)",(wid,entity_type,entity_id,"Running",jsonish(data.get("context") or {}),started,tid));run_id=cur.lastrowid
  try:
   outcomes=[]
   for index,step in enumerate(steps):
    if not isinstance(step,dict):raise ValueError(f"step {index+1} must be an object")
    action=str(step.get("action") or "").strip().lower()
    if action in {"audit","log"}:
     message=str(step.get("message") or "workflow step")[:500];audit(conn,u,"WORKFLOW_STEP",entity_type or "workflow",entity_id,message);outcomes.append({"step":index+1,"action":"audit","ok":True})
    elif action=="set_context":
     key=str(step.get("key") or "").strip()
     if not key:raise ValueError(f"step {index+1} key required")
     outcomes.append({"step":index+1,"action":"set_context","key":key,"value":step.get("value"),"ok":True})
    elif action in {"external","send_email","send_sms","esign","background_check","payroll","vms"}:
     raise RuntimeError("external action is not connected")
    else:raise ValueError(f"unsupported workflow action: {action or '<empty>'}")
   finished=now();conn.execute("UPDATE workflow_runs_r14 SET status='Completed',context_json=?,finished_at=?,error=NULL WHERE id=? AND tenant_id=?",(jsonish({"input":data.get("context") or {},"outcomes":outcomes}),finished,run_id,tid));audit(conn,u,"RUN","workflow",wid,f"run={run_id}");conn.commit();return send(h,{"run_id":run_id,"status":"Completed","outcomes":outcomes},201)
  except RuntimeError as exc:
   conn.execute("UPDATE workflow_runs_r14 SET status='Waiting External',finished_at=?,error=? WHERE id=? AND tenant_id=?",(now(),str(exc),run_id,tid));conn.commit();return send(h,{"run_id":run_id,"status":"Waiting External","error":str(exc)},409)
  except Exception as exc:
   conn.execute("UPDATE workflow_runs_r14 SET status='Failed',finished_at=?,error=? WHERE id=? AND tenant_id=?",(now(),str(exc),run_id,tid));conn.commit();return send(h,{"run_id":run_id,"status":"Failed","error":str(exc)},400)
 m=re.fullmatch(r"/api/r14/([a-z-]+)",path)
 if m and m.group(1) in RESOURCE:
  slug=m.group(1);table,roles,allowed=RESOURCE[slug]
  if u["role"] not in roles:return send(h,{"error":"Permission denied"},403)
  payload=dict(data)
  if slug=="requisition-requests" and u["role"]=="client":payload["company_id"]=u.get("company_id");payload["contact_user_id"]=u["id"];payload.setdefault("requested_at",now())
  if slug in {"pto-requests"} and u["role"]=="worker":payload["candidate_id"]=u.get("candidate_id")
  if slug=="pay-statements" and u["role"]=="worker":return send(h,{"error":"Permission denied"},403)
  guard=_configuration_guard(slug,payload)
  if guard:return send(h,{"error":guard},409)
  err=_validate_parent_refs(conn,slug,payload,tid) or _validate_polymorphic_refs(conn,slug,payload,tid)
  if err:return send(h,{"error":err},400)
  protected=PROTECTED_PATCH_FIELDS.get(slug,set())
  if protected.intersection(payload) and slug not in {"candidate-background","candidate-privacy","job-status-history","start-events","esign-envelopes","timesheet-adjustments","time-locks","sows","milestones","payroll-profiles","payroll-batches","salary-records","billing-records","campaigns","campaign-members","report-schedules","workflow-runs","requisition-requests","pto-requests","pay-statements","sso-configs","external-gateways"}:return send(h,{"error":"Lifecycle/security fields require a dedicated operation"},409)
  extra={}
  if "owner_user_id" in allowed and not payload.get("owner_user_id"):payload["owner_user_id"]=u["id"]
  if "requested_by" in allowed and not payload.get("requested_by"):payload["requested_by"]=u["id"]
  if "user_id" in allowed and slug in {"job-alerts"} and not payload.get("user_id"):payload["user_id"]=u["id"]
  try:rid=insert_generic(conn,table,payload,allowed,u,extra)
  except sqlite3.IntegrityError as exc:return send(h,{"error":"Relationship or uniqueness constraint failed","detail":str(exc)},409)
  audit(conn,u,"CREATE",table,rid,slug);conn.commit();return send(h,{"id":rid},201)
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
 if not _object_scope_allowed(slug,existing,u):return send(h,{"error":"Permission denied"},403)
 if slug in IMMUTABLE_RESOURCES:return send(h,{"error":"Resource is immutable; use its dedicated operation"},409)
 fields=[k for k in data if k in allowed]
 if not fields:return send(h,{"error":"No valid fields"},400)
 protected=PROTECTED_PATCH_FIELDS.get(slug,set()).intersection(fields)
 if protected:return send(h,{"error":"Lifecycle/security fields require a dedicated operation","fields":sorted(protected)},409)
 payload=dict(existing);payload.update({k:data[k] for k in fields})
 guard=_configuration_guard(slug,payload)
 if guard:return send(h,{"error":guard},409)
 err=_validate_parent_refs(conn,slug,payload,u["tenant_id"]) or _validate_polymorphic_refs(conn,slug,payload,u["tenant_id"],existing)
 if err:return send(h,{"error":err},400)
 c=cols(conn,table);vals=[]
 for k in fields:vals.append(jsonish(data[k]) if k.endswith("_json") else data[k])
 if "updated_at" in c:fields.append("updated_at");vals.append(now())
 try:conn.execute(f"UPDATE {table} SET "+",".join(f"{x}=?" for x in fields)+" WHERE id=? AND tenant_id=?",tuple(vals)+(rid,u["tenant_id"]))
 except sqlite3.IntegrityError as exc:return send(h,{"error":"Relationship or uniqueness constraint failed","detail":str(exc)},409)
 audit(conn,u,"UPDATE",table,rid,",".join(fields));conn.commit();return send(h,{"ok":True})

def r14_delete(h,conn,u,path,qs):
 m=re.fullmatch(r"/api/contact-hotlists/(\d+)/members/(\d+)",path)
 if m:
  if u["role"] not in CRM:return send(h,{"error":"Permission denied"},403)
  conn.execute("DELETE FROM contact_hotlist_members WHERE hotlist_id=? AND contact_id=? AND tenant_id=?",(int(m.group(1)),int(m.group(2)),u["tenant_id"]));conn.commit();return send(h,{"ok":True})
 m=re.fullmatch(r"/api/contact-hotlists/(\d+)",path)
 if m:
  if u["role"] not in CRM:return send(h,{"error":"Permission denied"},403)
  hid=int(m.group(1));conn.execute("DELETE FROM contact_hotlist_members WHERE hotlist_id=? AND tenant_id=?",(hid,u["tenant_id"]));conn.execute("DELETE FROM contact_hotlists WHERE id=? AND tenant_id=?",(hid,u["tenant_id"]));conn.commit();return send(h,{"ok":True})
 m=re.fullmatch(r"/api/auth/sessions/([0-9a-fA-F]{64})",path)
 if m:
  sid=m.group(1).lower();tokens=rows(conn,"SELECT token FROM sessions WHERE user_id=? AND tenant_id=?",(u["id"],u["tenant_id"]))
  token=next((x["token"] for x in tokens if _session_public_id(x["token"])==sid),None)
  if not token:return send(h,{"error":"Session not found"},404)
  conn.execute("DELETE FROM sessions WHERE token=? AND user_id=? AND tenant_id=?",(token,u["id"],u["tenant_id"]));conn.commit();return send(h,{"ok":True})
 m=re.fullmatch(r"/api/(jobs|companies|contacts)/(\d+)/attachments/(\d+)",path)
 if m:
  kind,pid,aid=m.group(1),int(m.group(2)),int(m.group(3));cfg={"jobs":("job_attachments_r14","job_id",RECRUITING),"companies":("company_attachments_r14","company_id",CRM),"contacts":("contact_attachments_r14","contact_id",CRM)}[kind]
  table,parent,roles=cfg
  if u["role"] not in roles:return send(h,{"error":"Permission denied"},403)
  cur=conn.execute(f"DELETE FROM {table} WHERE id=? AND {parent}=? AND tenant_id=?",(aid,pid,u["tenant_id"]))
  if not cur.rowcount:return send(h,{"error":"Attachment not found"},404)
  audit(conn,u,"DELETE",table,aid,f"{parent}={pid}");conn.commit();return send(h,{"ok":True})
 m=re.fullmatch(r"/api/r14/([a-z-]+)/(\d+)",path)
 if not m:return False
 slug=m.group(1);rid=int(m.group(2))
 if slug not in RESOURCE:return send(h,{"error":"Unknown R14 resource"},404)
 table,roles,_=RESOURCE[slug]
 if u["role"] not in roles:return send(h,{"error":"Permission denied"},403)
 existing=owned(conn,table,rid,u["tenant_id"])
 if not existing:return send(h,{"error":"Not found"},404)
 if not _object_scope_allowed(slug,existing,u):return send(h,{"error":"Permission denied"},403)
 if slug in IMMUTABLE_RESOURCES:return send(h,{"error":"Resource cannot be deleted"},409)
 cur=conn.execute(f"DELETE FROM {table} WHERE id=? AND tenant_id=?",(rid,u["tenant_id"]))
 if not cur.rowcount:return send(h,{"error":"Not found"},404)
 audit(conn,u,"DELETE",table,rid,slug);conn.commit();return send(h,{"ok":True})
