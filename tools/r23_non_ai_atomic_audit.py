from __future__ import annotations

import csv
import json
import pathlib
import re
import sys
from collections import Counter, defaultdict


repo = pathlib.Path(sys.argv[1]).resolve()
evidence = pathlib.Path(sys.argv[2]).resolve()
evidence.mkdir(parents=True, exist_ok=True)


AI_EXCLUDED = {
    "AI Assistant",
    "EVA",
    "DataTune",
    "Generative AI",
    "AI chatbot",
    "AI sentiment analysis",
    "AI autonomous matching",
}


CAPS = []


def add(category, area, capability, signals, weight=1):
    CAPS.append(
        {
            "category": category,
            "area": area,
            "capability": capability,
            "signals": signals,
            "weight": weight,
        }
    )


# =====================================================================
# ORGANIZATION / USERS / RBAC / TEAMS
# =====================================================================

add("Administration","Users","User creation",["/api/users","create user"])
add("Administration","Users","User deactivate/reactivate",["active","/api/users"])
add("Administration","Users","Password reset",["reset token","auth_reset"])
add("Administration","Users","MFA",["auth_mfa","totp"])
add("Administration","Users","User invitation",["auth_invitations","invitation"])
add("Administration","Profiles","Configurable role/profile creation",["role_profiles","permission profile"])
add("Administration","Profiles","Role/profile cloning",["clone role","clone profile"])
add("Administration","Profiles","Role/profile rename",["role_profiles","display_name"])
add("Administration","Profiles","Role/profile deactivate",["role_profiles","active"])
add("Administration","Permissions","Module permission matrix",["role_permissions","permission"])
add("Administration","Permissions","Action-level permissions",["create","edit","delete","approve","export"])
add("Administration","Permissions","Data-scope own/team/all",["data_scope","own","team","all"])
add("Administration","Permissions","Financial field visibility",["financial","redact"])
add("Administration","Permissions","Document privacy permissions",["document","permission"])
add("Administration","Permissions","Integration/admin configuration permission",["integration","admin"])
add("Administration","Teams","Multiple teams",["teams","team_members"])
add("Administration","Teams","Choose team at login/session",["choose team","team_id"])
add("Administration","Teams","Team membership management",["team_members","user_id"])
add("Administration","Groups","Divisions",["divisions_r14"])
add("Administration","Groups","User groups",["user_groups_r14"])
add("Administration","Groups","Group membership",["user_group_members_r14"])
add("Administration","Audit","Audit trail",["audit_log"])
add("Administration","Audit","Access log reporting",["access log"])
add("Administration","Custom Fields","User-defined fields",["custom_fields","entity_custom_values"])
add("Administration","Feature Configuration","Team/profile feature switches",["feature configuration"])
add("Administration","SSO","SSO configuration",["sso_configs_r14"])
add("Administration","Branding","White-label branding",["tenant_branding_r22"])
add("Administration","Help","Help / best-practices center",["help","best practices"])
add("Administration","Release","Release notes / what's new",["release notes","what's new"])


# =====================================================================
# PERSONAS / OPERATING PROFILES
# =====================================================================

for persona in [
    "System Administrator",
    "Recruiting Manager",
    "Team Lead",
    "Recruiter",
    "Sourcer",
    "Sales",
    "Business Development",
    "Account Manager",
    "Onboarding Coordinator",
    "Compliance Specialist",
    "Credentialing Specialist",
    "HR / Workforce Operations",
    "Payroll",
    "Billing / Accounts Receivable",
    "Finance Manager",
    "VMS / MSP Coordinator",
    "Supplier / Vendor Manager",
    "Operations Manager",
    "Reporting / BI User",
    "Client / Hiring Manager",
    "Candidate",
    "Worker / Contractor",
    "Supplier",
    "Timesheet / Expense Approver",
]:
    key = persona.lower().replace(" / "," ").replace("/"," ")
    add(
        "Personas",
        "Profiles",
        persona,
        [key, key.replace(" ","_")],
    )


# =====================================================================
# CANDIDATE SOURCING / SEARCH
# =====================================================================

add("Search & Sourcing","Candidates","Candidate database search",["/api/candidates"])
add("Search & Sourcing","Candidates","Boolean candidate search",["boolean","perform_search"])
add("Search & Sourcing","Candidates","Relevant-years skill search",["candidate_skills","years","last_used"])
add("Search & Sourcing","Candidates","Resume text search",["resume_text"])
add("Search & Sourcing","Candidates","Candidate note search",["candidate_notes"])
add("Search & Sourcing","Candidates","Candidate attribute search",["candidate_attributes"])
add("Search & Sourcing","Candidates","Geographic search",["latitude","longitude"])
add("Search & Sourcing","Candidates","Availability search",["availability_date"])
add("Search & Sourcing","Candidates","Candidate import",["import candidates"])
add("Search & Sourcing","Candidates","Bulk candidate import validation",["candidate import","validation"])
add("Search & Sourcing","Candidates","Candidate duplicate detection",["duplicate_score","duplicates"])
add("Search & Sourcing","Candidates","Candidate merge",["candidate_merge_history","merge"])
add("Search & Sourcing","Candidates","Candidate hotlists / pools",["hotlists","hotlist_members"])
add("Search & Sourcing","Candidates","Talent cluster / mass actions",["talent cluster","bulk"])
add("Search & Sourcing","Harvesting","Resume harvesting",["harvest"])
add("Search & Sourcing","Harvesting","Harvest assignment by user",["harvest","user_id"])
add("Search & Sourcing","Job Boards","External job-board sourcing",["job board","connector"])
add("Search & Sourcing","Job Boards","Job-board quota/account visibility",["quota","job board"])
add("Search & Sourcing","Matching","Candidate-to-job matching",["match_jobs_for_candidate"])
add("Search & Sourcing","Matching","Job-to-candidate matching",["matches","candidate"])
add("Search & Sourcing","Matching","Match explanation/reasons",["reasons","match"])


# =====================================================================
# CANDIDATE RECORD
# =====================================================================

add("Candidate Management","Profile","Candidate profile",["candidate_bundle"])
add("Candidate Management","Profile","Employment history",["candidate_experience"])
add("Candidate Management","Profile","Skills",["candidate_skills"])
add("Candidate Management","Profile","Licenses",["candidate_licenses"])
add("Candidate Management","Profile","Certifications",["candidate_certifications"])
add("Candidate Management","Profile","Qualifications",["candidate_qualifications"])
add("Candidate Management","Profile","Candidate attributes",["candidate_attributes"])
add("Candidate Management","Profile","Candidate notes",["candidate_notes"])
add("Candidate Management","Profile","Candidate tasks",["tasks"])
add("Candidate Management","Profile","Candidate communications",["communications"])
add("Candidate Management","Documents","Candidate documents",["candidate_documents"])
add("Candidate Management","Documents","Document versioning",["candidate_document_versions"])
add("Candidate Management","Documents","Document download authorization",["candidate-documents","download"])
add("Candidate Management","Privacy","Do-not-contact",["do_not_contact"])
add("Candidate Management","Privacy","Email consent",["consent_email"])
add("Candidate Management","Privacy","SMS consent",["consent_sms"])
add("Candidate Management","Privacy","Candidate privacy requests",["candidate_privacy_actions"])
add("Candidate Management","Lifecycle","Candidate archival",["archived_at"])
add("Candidate Management","Quality","Candidate credibility score",["credibility_score"])
add("Candidate Management","HR","Candidate HR record",["candidate_hr_records"])
add("Candidate Management","EEO","EEO record",["candidate_eeo"])


# =====================================================================
# RESUME / REGISTRATION / PORTAL
# =====================================================================

add("Candidate Portal","Registration","Registration with uploaded resume",["candidate portal","resume"])
add("Candidate Portal","Registration","Registration with pasted resume",["resume_text"])
add("Candidate Portal","Registration","Registration without resume",["candidate portal"])
add("Candidate Portal","Registration","Resume maker/editor",["resume maker","resume builder"])
add("Candidate Portal","Profile","Candidate self-service profile edit",["candidate portal","profile"])
add("Candidate Portal","Jobs","Public job search",["candidateportal","open positions"])
add("Candidate Portal","Jobs","Job application / interest",["candidateApply","interested"])
add("Candidate Portal","Jobs","Application tracking",["my applications"])
add("Candidate Portal","Jobs","Saved/ideal jobs",["ideal job","saved job"])
add("Candidate Portal","Alerts","Candidate job alerts",["job_alerts_r14"])
add("Candidate Portal","Filters","Radius/location filters",["radius","latitude","longitude"])
add("Candidate Portal","Filters","Work-mode filters",["work_mode"])
add("Candidate Portal","Localization","English",["'en'","English"])
add("Candidate Portal","Localization","Spanish",["'es'","Español"])
add("Candidate Portal","Localization","French",["'fr'","Français"])
add("Candidate Portal","Localization","Chinese",["'zh'","中文"])


# =====================================================================
# JOBS / RECRUITING
# =====================================================================

add("Jobs & Recruiting","Jobs","Job requisition management",["/api/jobs"])
add("Jobs & Recruiting","Jobs","Job search",["jobsearch","/api/jobs"])
add("Jobs & Recruiting","Jobs","Primary recruiter",["primary_recruiter_id"])
add("Jobs & Recruiting","Jobs","Secondary/multiple recruiters",["job_users"])
add("Jobs & Recruiting","Jobs","Job cloning",["cloneJob","/clone"])
add("Jobs & Recruiting","Jobs","Job archive",["archiveJob"])
add("Jobs & Recruiting","Jobs","Job status history",["job_status_history_r14"])
add("Jobs & Recruiting","Jobs","Job notes",["job_notes_r14"])
add("Jobs & Recruiting","Jobs","Job catalogs/templates",["job_catalogs_r14"])
add("Jobs & Recruiting","Jobs","Job attachments",["job_attachments"])
add("Jobs & Recruiting","Jobs","Job distribution",["job_distribution"])
add("Jobs & Recruiting","Jobs","Internal career publication",["internal careers"])
add("Jobs & Recruiting","Interest","Interested-candidate workflow",["interested_candidates"])
add("Jobs & Recruiting","Submittals","Submission workflow",["submissions"])
add("Jobs & Recruiting","Submittals","Client review",["client_review"])
add("Jobs & Recruiting","Submittals","Right-to-represent",["rtr_status","right to represent"])
add("Jobs & Recruiting","Submittals","Compliance status",["compliance_status"])
add("Jobs & Recruiting","Interviews","Interview scheduling",["interviews","scheduled"])
add("Jobs & Recruiting","Interviews","Interview reschedule",["interview","scheduled"])
add("Jobs & Recruiting","Interviews","No-show handling",["no_show"])
add("Jobs & Recruiting","Interviews","Interview feedback",["interview","feedback"])
add("Jobs & Recruiting","Assessments","Assessments",["assessments"])
add("Jobs & Recruiting","Assessments","Questionnaires",["questionnaire"])
add("Jobs & Recruiting","Offer","Offer workflow",["'offer'","submission"])
add("Jobs & Recruiting","Hire","Hire workflow",["'hired'"])
add("Jobs & Recruiting","Starts","Start management",["starts"])
add("Jobs & Recruiting","Starts","Start cancellation",["cancellation_reason"])
add("Jobs & Recruiting","History","Workflow history",["workflow_history"])
add("Jobs & Recruiting","Alerts","Recruiter job alerts",["job_alerts_r14"])


# =====================================================================
# CRM / SALES / ACCOUNT MANAGEMENT
# =====================================================================

add("CRM","Companies","Company management",["/api/companies"])
add("CRM","Companies","Parent/child company hierarchy",["parent_company_id"])
add("CRM","Companies","Company addresses",["company_addresses_r14"])
add("CRM","Companies","Company owners",["company_owners_r14"])
add("CRM","Companies","Company attachments",["company_attachments"])
add("CRM","Contacts","Contact management",["/api/contacts"])
add("CRM","Contacts","Contact social links",["contact_social_r14"])
add("CRM","Contacts","Contact attachments",["contact_attachments"])
add("CRM","Contacts","Contact hotlists",["contact_hotlists"])
add("CRM","Leads","Lead management",["leads"])
add("CRM","Opportunities","Opportunity pipeline",["opportunities"])
add("CRM","Tasks","CRM tasks",["tasks","owner_user_id"])
add("CRM","Pipeline","Company pipeline dashboard",["company_pipeline"])
add("CRM","Account Management","Dedicated account-manager ownership",["account manager","owner_user_id"])
add("CRM","Account Management","Client relationship activity history",["company","communications"])
add("CRM","Analytics","Company mini dashboard",["company","dashboard"])
add("CRM","Analytics","Contact mini dashboard",["contact","dashboard"])


# =====================================================================
# CLIENT / HIRING MANAGER PORTAL
# =====================================================================

add("Client Portal","Requisitions","Client requisition requests",["client_requisition_requests_r14"])
add("Client Portal","Requisitions","Requisition templates/job catalogs",["job_catalogs_r14"])
add("Client Portal","Submittals","Review submitted candidates",["clientportal","submissions"])
add("Client Portal","Submittals","Approve/reject candidate",["client_review"])
add("Client Portal","Feedback","Candidate feedback",["feedback"])
add("Client Portal","Interviews","Request/schedule interview",["clientportal","interview"])
add("Client Portal","Hire","Request hire",["hire"])
add("Client Portal","Communication","Client communication",["communication"])
add("Client Portal","Reports","Client-facing reports",["client","reports"])
add("Client Portal","Alerts","Client alerts",["client","alert"])


# =====================================================================
# ONBOARDING / COMPLIANCE
# =====================================================================

add("Onboarding & Compliance","Packages","Paperless onboarding",["onboarding_packages"])
add("Onboarding & Compliance","Packages","Onboarding requirements",["onboarding_requirements"])
add("Onboarding & Compliance","Rules","Client-specific onboarding rules",["onboarding_rules_r14","client_id"])
add("Onboarding & Compliance","Rules","State/locality rules",["onboarding_rules_r14","state"])
add("Onboarding & Compliance","Rules","Tax-category rules",["tax_category"])
add("Onboarding & Compliance","Rules","Profession-specific rules",["profession"])
add("Onboarding & Compliance","E-Sign","E-sign envelopes",["esign_envelopes_r14"])
add("Onboarding & Compliance","Credentials","Credential expiration tracking",["expiry_date"])
add("Onboarding & Compliance","Credentials","Credential verification",["verified_at","credential"])
add("Onboarding & Compliance","Background","Background check workflow",["candidate_background_cases"])
add("Onboarding & Compliance","References","Reference check workflow",["reference-check"])
add("Onboarding & Compliance","Employment","Employment verification",["employment_verifications_r14"])
add("Onboarding & Compliance","E-Verify","E-Verify integration surface",["E-Verify","employment-verifications"])
add("Onboarding & Compliance","I-9","I-9 workflow",["I-9"])
add("Onboarding & Compliance","EEO","EEO capability",["candidate_eeo"])
add("Onboarding & Compliance","Compliance","Supplier compliance",["supplier_compliance_r14"])
add("Onboarding & Compliance","Dashboard","Onboarding dashboard",["onboarding dashboard"])


# =====================================================================
# WORKFORCE / TIME / EXPENSE
# =====================================================================

add("Workforce","Assignments","Assignment management",["assignments"])
add("Workforce","Assignments","Assignment status workflow",["assignment","pending","active","completed"])
add("Workforce","Assignments","Assignment ending alerts",["assignment ending"])
add("Workforce","Shift","Shift management",["shifts"])
add("Workforce","Shift","Per-diem staffing",["per_diems_r14"])
add("Workforce","Attendance","Attendance management",["attendance"])
add("Workforce","Time","Timesheet entry",["timesheets"])
add("Workforce","Time","Timesheet approval",["approved_by","timesheet"])
add("Workforce","Time","Timesheet rejection",["rejected","timesheet"])
add("Workforce","Time","Timesheet adjustment",["timesheet_adjustments_r14"])
add("Workforce","Time","Time-period lock",["time_period_locks_r14"])
add("Workforce","Time","Overtime/time rules",["time_rules_r14"])
add("Workforce","Expenses","Expense entry",["expenses"])
add("Workforce","Expenses","Expense approval",["expense","approved"])
add("Workforce","Expenses","Expense rejection",["expense","rejected"])
add("Workforce","PTO","PTO requests",["pto_requests_r14"])
add("Workforce","Portal","Worker portal",["workerPortal"])
add("Workforce","Portal","Approver portal",["approverPortal"])


# =====================================================================
# FINANCIALS
# =====================================================================

add("Financials","SOW","SOW records",["sow_records_r14"])
add("Financials","SOW","SOW milestones",["milestones_r14"])
add("Financials","Billing","Billing records",["billing_records_r14"])
add("Financials","Billing","Invoice creation",["invoices"])
add("Financials","Billing","Invoice issue",["issued"])
add("Financials","Billing","Partial payment",["part_paid"])
add("Financials","Billing","Full payment",["paid_amount"])
add("Financials","Billing","Invoice void",["void"])
add("Financials","AR","Accounts-receivable aging",["aging","invoice"])
add("Financials","AR","Collections workflow",["collections","invoice"])
add("Financials","AR","Outstanding balance",["balance"])
add("Financials","Payroll","Payroll profiles",["payroll_profiles_r14"])
add("Financials","Payroll","Payroll batches",["payroll_batches_r14"])
add("Financials","Payroll","Pay statements",["pay_statements_r14"])
add("Financials","Payroll","Salary/pay-rate records",["salary_records_r14"])
add("Financials","Payroll","Payroll provider execution",["payroll","connector"])
add("Financials","Costs","Overheads",["overheads_r14"])
add("Financials","Costs","Per diems",["per_diems_r14"])
add("Financials","Costs","Stipends",["stipends_r14"])
add("Financials","Costs","Workers compensation codes",["workers_comp_codes_r14"])
add("Financials","Margin","Gross-margin calculation",["gross margin"])
add("Financials","Margin","Margin/rate calculator",["margin calculator","calcudiva"])
add("Financials","GL","General-ledger integration",["general ledger","connector"])
add("Financials","Profitability","Client/job profitability reporting",["profitability","margin"])


# =====================================================================
# VMS / MSP / SUPPLIERS
# =====================================================================

add("VMS / MSP","Accounts","VMS account management",["vms_accounts"])
add("VMS / MSP","MSP","MSP administrator workflow",["msp"])
add("VMS / MSP","Catalog","Job catalogs",["job_catalogs_r14"])
add("VMS / MSP","Cost Centers","Cost centers",["cost_center"])
add("VMS / MSP","Approvals","Requisition approval chain",["approval"])
add("VMS / MSP","Release","Supplier job release",["supplier_releases"])
add("VMS / MSP","Suppliers","Supplier management",["suppliers"])
add("VMS / MSP","Suppliers","Supplier contracts",["supplier_contracts_r14"])
add("VMS / MSP","Suppliers","Supplier scorecards",["supplier_scorecards_r14"])
add("VMS / MSP","Suppliers","Supplier compliance",["supplier_compliance_r14"])
add("VMS / MSP","Supplier Portal","Supplier portal",["supplierPortal"])
add("VMS / MSP","Supplier Portal","Supplier candidate submission",["supplier","candidate"])
add("VMS / MSP","Supplier Portal","Supplier job visibility",["supplier_releases"])
add("VMS / MSP","Manager","Hiring-manager VMS workflow",["approverPortal"])
add("VMS / MSP","Sync","VMS job sync",["vms","sync"])
add("VMS / MSP","Sync","VMS time sync",["timesheet","vms"])
add("VMS / MSP","Sync","VMS expense sync",["expense","vms"])
add("VMS / MSP","Sync","VMS SOW sync",["sow","vms"])
add("VMS / MSP","Offboarding","Supplier/worker offboarding",["offboarding","termination"])


# =====================================================================
# COMMUNICATION / CALENDAR / INTERVIEW
# =====================================================================

add("Communication","Email","Email communication",["channel","Email"])
add("Communication","SMS","SMS communication",["channel","SMS"])
add("Communication","Threads","Communication threads",["communication_threads_r14"])
add("Communication","Campaigns","Campaign definitions",["campaigns_r14"])
add("Communication","Campaigns","Campaign recipients",["campaign_members_r14"])
add("Communication","Campaigns","Campaign execution",["campaign_runs_r19"])
add("Communication","Campaigns","Unsubscribe handling",["unsubscribed_at"])
add("Communication","Calendar","Calendar",["calendar"])
add("Communication","Outlook","Outlook synchronization",["outlook"])
add("Communication","VOIP","VOIP integration",["VOIP"])
add("Communication","Interview","Live interview",["Live Interview"])
add("Communication","Interview","Meeting provider",["meeting_connector_id"])
add("Communication","Interview","Meeting recording link",["recording_url"])
add("Communication","Interview","Meeting auto-note/history",["meeting","note"])


# =====================================================================
# REPORTS / DASHBOARDS
# =====================================================================

add("Reporting","Builder","Report builder",["report_builders_r14"])
add("Reporting","Builder","Report filters",["filters_json"])
add("Reporting","Builder","Report grouping",["group_by"])
add("Reporting","Builder","Report sorting",["sort_json"])
add("Reporting","Schedules","Report schedules",["report_schedules_r14"])
add("Reporting","Schedules","Scheduled delivery",["recipients","report_schedules"])
add("Reporting","Schedules","CSV output",["CSV"])
add("Reporting","Runs","Report run history",["report_runs_r19"])
add("Reporting","Sharing","Shared reports",["is_shared"])
add("Reporting","Dashboards","User dashboard",["User Dashboard"])
add("Reporting","Dashboards","Team dashboard",["Team Dashboard"])
add("Reporting","Dashboards","Onboarding dashboard",["Onboarding Dashboard"])
add("Reporting","Dashboards","e-Interview dashboard",["e-Interview Dashboard"])
add("Reporting","Dashboards","Shared dashboards",["dashboards_r14","is_shared"])
add("Reporting","Dashboards","Dashboard widgets",["dashboard_widgets_r14"])
add("Reporting","Recruiting","Recruiter productivity report",["Recruiter Productivity"])
add("Reporting","Recruiting","Time-to-submit report",["Time to Submit"])
add("Reporting","Recruiting","Submittal funnel report",["Submittal Funnel"])
add("Reporting","Recruiting","Interview conversion report",["Interview Conversion"])
add("Reporting","Recruiting","Starts & placements report",["Starts & Placements"])
add("Reporting","Recruiting","Recruiting leaderboard",["leaderboard"])
add("Reporting","Candidates","Candidate source report",["Candidate Source"])
add("Reporting","Jobs","Open jobs aging report",["Open Jobs Aging"])
add("Reporting","Onboarding","Onboarding completion report",["Onboarding Completion"])
add("Reporting","Credentials","Credential expiry report",["Credential Expiry"])
add("Reporting","Workforce","Assignment ending report",["Assignment Ending"])
add("Reporting","Workforce","Timesheet aging report",["Timesheet Aging"])
add("Reporting","Workforce","Expense aging report",["Expense Aging"])
add("Reporting","Financial","Client revenue report",["Client Revenue"])
add("Reporting","Financial","Gross margin report",["Gross Margin"])
add("Reporting","VMS","VMS sync exception report",["VMS Sync Exceptions"])
add("Reporting","Supplier","Supplier performance report",["Supplier Performance"])
add("Reporting","Audit","Audit access report",["Audit Access"])
add("Reporting","Journals","Candidate notes journal",["candidate_notes"])
add("Reporting","Journals","Job notes journal",["job_notes"])
add("Reporting","Journals","Company/contact activity journal",["contact","company","notes"])
add("Reporting","Permissions","User permissions report",["permissions","report"])
add("Reporting","Harvesting","Harvester assignment report",["harvest","assignment","report"])


# =====================================================================
# INTEGRATIONS / API
# =====================================================================

for cap, sig in [
    ("Job boards",["job board","external_gateways"]),
    ("Background screening",["Background Screening"]),
    ("Reference checks",["Reference Check"]),
    ("WOTC",["WOTC"]),
    ("E-Verify",["E-Verify"]),
    ("Certified e-sign",["Certified E-Signature"]),
    ("Payroll",["Payroll","connector"]),
    ("General ledger",["General Ledger"]),
    ("Email/SMS",["Production Email/SMS"]),
    ("VOIP",["VOIP"]),
    ("VMS Fieldglass",["Fieldglass"]),
    ("VMS Beeline",["Beeline"]),
    ("Outlook",["outlook"]),
    ("Candidate enrichment",["candidate-enrichment"]),
    ("Assessment providers",["assessment","connector"]),
]:
    add("Integrations","External",cap,sig)

add("Integrations","Truth Gate","Credentials-required state",["Credentials Required"])
add("Integrations","Truth Gate","Configuration-required state",["Configuration Required"])
add("Integrations","Truth Gate","Real HTTP execution",["provider_http_status"])
add("Integrations","Truth Gate","External transaction audit",["external_transactions_r19"])
add("Integrations","API","Application API surface",["/api/"])
add("Integrations","API","API authentication",["session","Authentication required"])
add("Integrations","API","Tenant isolation",["tenant_id"])


# =====================================================================
# MOBILE / WHITE LABEL
# =====================================================================

add("Mobile & White Label","Responsive","Responsive recruiter web experience",["viewport"])
add("Mobile & White Label","Worker","MyTime-style worker mobile workflow",["workerPortal","timesheet"])
add("Mobile & White Label","Candidate","Mobile candidate portal",["candidatePortal"])
add("Mobile & White Label","Branding","White-label portal",["tenant_branding_r22"])
add("Mobile & White Label","PWA","Installable PWA manifest",["manifest.json","serviceWorker"])
add("Mobile & White Label","Offline","Offline/PWA cache",["serviceWorker","cache"])


# =====================================================================
# SOURCE INVENTORY
# =====================================================================

ALLOWED_SUFFIXES = {
    ".py",
    ".js",
    ".html",
    ".css",
    ".sql",
    ".webmanifest",
}

SKIP_TOP = {
    "tests",
    "tools",
    ".git",
    ".github",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    "data",
    "evidence",
    "audit-results",
}

SKIP_PREFIXES = (
    "R10-",
    "R11-",
    "R12-",
    "R13-",
    "R14-",
    "R15-",
    "R16-",
    "R17-",
    "R18-",
    "R19-",
    "R20-",
    "R21-",
    "R22-",
    "R23-",
    "ACCEPTANCE",
    "FUNCTION-MAP",
    "ARCHITECTURE",
    "README",
    "HANDOFF",
)

files = []

for p in repo.rglob("*"):

    if not p.is_file():
        continue

    rel = p.relative_to(repo)
    rels = rel.as_posix()

    if rel.parts and rel.parts[0] in SKIP_TOP:
        continue

    if any(
        part in SKIP_TOP
        for part in rel.parts
    ):
        continue

    name_lower = p.name.lower()
    stem_lower = p.stem.lower()

    # ---------------------------------------------------------------
    # STRICT NON-PRODUCT FILE EXCLUSION
    #
    # These files can mention capability names because they test,
    # audit, prove or document them. They are never implementation
    # evidence.
    # ---------------------------------------------------------------

    if (
        "acceptance" in stem_lower
        or "audit" in stem_lower
        or "scanner" in stem_lower
        or "checker" in stem_lower
        or "evidence" in stem_lower
        or "handoff" in stem_lower
        or stem_lower.startswith("test")
        or stem_lower.startswith("verify")
        or stem_lower.startswith("probe")
        or stem_lower.endswith("_test")
        or stem_lower.endswith("_tests")
        or stem_lower.endswith("_gate")
        or stem_lower.endswith("_proof")
        or stem_lower.endswith("_check")
    ):
        continue

    if p.suffix.lower() not in ALLOWED_SUFFIXES:
        continue

    if p.name.startswith(SKIP_PREFIXES):
        continue

    try:
        text = p.read_text(
            encoding="utf-8",
            errors="ignore",
        )
    except OSError:
        continue

    files.append(
        (
            rels,
            text,
            text.lower(),
        )
    )

def search_signal(signal):
    needle = signal.lower()

    hits = []

    for rel, text, low in files:
        if needle in low:
            hits.append(rel)

    return sorted(set(hits))


rows = []

for cap in CAPS:
    signal_results = []

    for signal in cap["signals"]:
        hits = search_signal(signal)

        signal_results.append(
            {
                "signal": signal,
                "hits": hits,
            }
        )

    found = [
        x
        for x in signal_results
        if x["hits"]
    ]

    ratio = (
        len(found) / len(signal_results)
        if signal_results
        else 0.0
    )

    if ratio >= 0.75:
        status = "STATIC_EVIDENCE_STRONG"

    elif ratio > 0:
        status = "STATIC_EVIDENCE_PARTIAL"

    else:
        status = "MISSING_OR_UNPROVEN"

    evidence_files = sorted(
        {
            h
            for x in found
            for h in x["hits"]
        }
    )

    rows.append(
        {
            **cap,
            "status": status,
            "matched_signals": len(found),
            "total_signals": len(signal_results),
            "evidence_files": evidence_files,
            "signal_detail": signal_results,
        }
    )


counts = Counter(
    r["status"]
    for r in rows
)

weights = {
    "STATIC_EVIDENCE_STRONG": 1.0,
    "STATIC_EVIDENCE_PARTIAL": 0.5,
    "MISSING_OR_UNPROVEN": 0.0,
}

score = sum(
    weights[r["status"]] * r["weight"]
    for r in rows
)

max_score = sum(
    r["weight"]
    for r in rows
)

coverage = (
    round(
        100.0 * score / max_score,
        2,
    )
    if max_score
    else 0.0
)


csv_path = evidence / "R23-NONAI-ATOMIC-MATRIX.csv"

with csv_path.open(
    "w",
    newline="",
    encoding="utf-8",
) as f:

    w = csv.writer(f)

    w.writerow(
        [
            "category",
            "area",
            "capability",
            "status",
            "matched_signals",
            "total_signals",
            "evidence_files",
        ]
    )

    for r in rows:
        w.writerow(
            [
                r["category"],
                r["area"],
                r["capability"],
                r["status"],
                r["matched_signals"],
                r["total_signals"],
                "; ".join(r["evidence_files"]),
            ]
        )


json_path = evidence / "R23-NONAI-ATOMIC-MATRIX.json"

json_path.write_text(
    json.dumps(
        {
            "ai_excluded": sorted(AI_EXCLUDED),
            "total_atomic_capabilities": len(rows),
            "static_evidence_strong": counts["STATIC_EVIDENCE_STRONG"],
            "static_evidence_partial": counts["STATIC_EVIDENCE_PARTIAL"],
            "missing_or_unproven": counts["MISSING_OR_UNPROVEN"],
            "static_coverage_percent": coverage,
            "functional_parity_percent": None,
            "rows": rows,
        },
        indent=2,
        ensure_ascii=False,
    )
    + "\n",
    encoding="utf-8",
)


by_category = defaultdict(
    lambda: Counter()
)

for r in rows:
    by_category[r["category"]][r["status"]] += 1


md = []

md.append("# ATS-One R23 Non-AI JobDiva Deep Atomic Audit")
md.append("")
md.append("AI/EVA is deliberately excluded from this closure.")
md.append("")
md.append(f"- Atomic capabilities: {len(rows)}")
md.append(
    f"- Strong static evidence: "
    f"{counts['STATIC_EVIDENCE_STRONG']}"
)
md.append(
    f"- Partial static evidence: "
    f"{counts['STATIC_EVIDENCE_PARTIAL']}"
)
md.append(
    f"- Missing / unproven: "
    f"{counts['MISSING_OR_UNPROVEN']}"
)
md.append(
    f"- Weighted static coverage: "
    f"{coverage}%"
)
md.append("")
md.append(
    "**Static coverage is NOT functional parity. "
    "100% is forbidden until functional, browser, API, "
    "security and workflow gates pass.**"
)
md.append("")
md.append("## Category summary")
md.append("")
md.append(
    "| Category | Strong | Partial | Missing |"
)
md.append(
    "|---|---:|---:|---:|"
)

for cat in sorted(by_category):
    c = by_category[cat]

    md.append(
        f"| {cat} | "
        f"{c['STATIC_EVIDENCE_STRONG']} | "
        f"{c['STATIC_EVIDENCE_PARTIAL']} | "
        f"{c['MISSING_OR_UNPROVEN']} |"
    )


md.append("")
md.append("## Missing / unproven")
md.append("")

for r in rows:
    if r["status"] == "MISSING_OR_UNPROVEN":
        md.append(
            f"- {r['category']} > "
            f"{r['area']} > "
            f"{r['capability']}"
        )


md.append("")
md.append("## Partial")
md.append("")

for r in rows:
    if r["status"] == "STATIC_EVIDENCE_PARTIAL":
        md.append(
            f"- {r['category']} > "
            f"{r['area']} > "
            f"{r['capability']}"
        )


md_path = evidence / "R23-NONAI-ATOMIC-SUMMARY.md"

md_path.write_text(
    "\n".join(md).rstrip()
    + "\n",
    encoding="utf-8",
)


print("=" * 70)
print(" ATS-ONE R23A NON-AI DEEP ATOMIC PARITY AUDIT")
print("=" * 70)
print(
    f"TOTAL_ATOMIC_CAPABILITIES="
    f"{len(rows)}"
)
print(
    "STATIC_EVIDENCE_STRONG="
    f"{counts['STATIC_EVIDENCE_STRONG']}"
)
print(
    "STATIC_EVIDENCE_PARTIAL="
    f"{counts['STATIC_EVIDENCE_PARTIAL']}"
)
print(
    "MISSING_OR_UNPROVEN="
    f"{counts['MISSING_OR_UNPROVEN']}"
)
print(
    "MEASURED_STATIC_NON_AI_COVERAGE_PERCENT="
    f"{coverage}"
)
print(
    "FUNCTIONAL_PARITY_PERCENT="
    "NOT_YET_MEASURED"
)
print(
    "AI_EVA="
    "EXCLUDED"
)
print(
    "ONE_HUNDRED_PERCENT_AUTHORIZED="
    "NO"
)
print("=" * 70)


print("")
print("=== TOP MISSING / UNPROVEN ===")

missing = [
    r
    for r in rows
    if r["status"] == "MISSING_OR_UNPROVEN"
]

for r in missing[:80]:
    print(
        "MISSING="
        + r["category"]
        + " > "
        + r["area"]
        + " > "
        + r["capability"]
    )


print("")
print("=== PARTIAL ===")

partial = [
    r
    for r in rows
    if r["status"] == "STATIC_EVIDENCE_PARTIAL"
]

for r in partial[:80]:
    print(
        "PARTIAL="
        + r["category"]
        + " > "
        + r["area"]
        + " > "
        + r["capability"]
    )


print("")
print(
    "NEXT="
    "R23B_CLOSE_RBAC_TEAMS_PROFILES"
)