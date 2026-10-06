from __future__ import annotations

import csv
import json
import pathlib
import sys

ROOT=pathlib.Path(sys.argv[1]).resolve()

SOURCES={
 "FAQ":"https://www.jobdiva.com/faq",
 "ATS":"https://www.jobdiva.com/ats-software-for-staffing-agencies",
 "HOME":"https://www.jobdiva.com/",
 "FEATURE_INDEX":"https://login.jobdiva.com/careers.jsp",
 "INTEGRATIONS":"https://www.jobdiva.com/recruiting-software-third-party-integrations",
 "ENGAGEMENT":"https://www.jobdiva.com/candidate-engagement",
 "OPERATIONS":"https://www.jobdiva.com/operational-efficiency",
 "LOGIN":"https://login.jobdiva.com/index.jsp",
 "ZOOM":"https://login.jobdiva.com/zoom/JobDiva-Zoom-Documentation.pdf",
}

# Each signal group is AND-ed.
# Terms inside one group are OR alternatives.
#
# Example:
# [["candidate_skills"],["years","last_used"]]
# requires candidate_skills PLUS one years-like implementation signal.
#
# IMPORTANT: implementation scanner never scans this file.

def F(category,feature,source,external,*groups):
    return {
        "category":category,
        "feature":feature,
        "source":source,
        "external":external,
        "groups":[list(g) for g in groups],
    }

FEATURES=[

# ----------------------------------------------------------------------
# SEARCH / SOURCING
# ----------------------------------------------------------------------

F("Search & Sourcing","Candidate database search","FEATURE_INDEX",False,
  ("candidates",),("/api/candidates",)),

F("Search & Sourcing","Boolean candidate search","ATS",False,
  ("boolean",),("candidate","talent")),

F("Search & Sourcing","Relevant-years skill search","ENGAGEMENT",False,
  ("candidate_skills",),("years","last_used")),

F("Search & Sourcing","Resume parsing / structured resume data","OPERATIONS",False,
  ("resume_text",),("candidate_experience","candidate_skills")),

F("Search & Sourcing","Resume harvesting","FEATURE_INDEX",True,
  ("harvest","resume harvest"),("job board","job-board")),

F("Search & Sourcing","External job-board sourcing","FAQ",True,
  ("job board","job-board"),("connector","gateway","distribution")),

F("Search & Sourcing","Candidate-to-job matching","ATS",False,
  ("match_jobs_for_candidate","/matches"),),

F("Search & Sourcing","Duplicate candidate intelligence","ATS",False,
  ("duplicate_score","/duplicates"),),

F("Search & Sourcing","Candidate hotlists","FEATURE_INDEX",False,
  ("hotlists",),("hotlist_members",)),

F("Search & Sourcing","Candidate note search","FEATURE_INDEX",False,
  ("candidate_notes",),),

F("Search & Sourcing","Candidate attribute search","FEATURE_INDEX",False,
  ("candidate_attributes",),),

F("Search & Sourcing","Candidate import","FEATURE_INDEX",False,
  ("candidate import","candidate_import","import candidates"),),

# ----------------------------------------------------------------------
# CANDIDATE MANAGEMENT
# ----------------------------------------------------------------------

F("Candidate Management","Candidate profile management","ATS",False,
  ("candidate_bundle","/api/candidates"),),

F("Candidate Management","Candidate employment history","ATS",False,
  ("candidate_experience",),),

F("Candidate Management","Candidate skills","ATS",False,
  ("candidate_skills",),),

F("Candidate Management","Licenses","ATS",False,
  ("candidate_licenses",),),

F("Candidate Management","Certifications","ATS",False,
  ("candidate_certifications",),),

F("Candidate Management","Qualifications","ATS",False,
  ("candidate_qualifications",),),

F("Candidate Management","Candidate notes","ATS",False,
  ("candidate_notes",),),

F("Candidate Management","Candidate attributes","FEATURE_INDEX",False,
  ("candidate_attributes",),),

F("Candidate Management","Candidate documents","ATS",False,
  ("candidate_documents",),),

F("Candidate Management","Document versioning","ATS",False,
  ("candidate_document_versions",),),

F("Candidate Management","Custom / user-defined fields","FEATURE_INDEX",False,
  ("custom_fields",),("entity_custom_values",)),

F("Candidate Management","Do-not-contact management","ATS",False,
  ("do_not_contact",),),

F("Candidate Management","Email/SMS consent","ATS",False,
  ("consent_email",),("consent_sms",)),

F("Candidate Management","Candidate archival lifecycle","ATS",False,
  ("archived_at",),("candidates",)),

F("Candidate Management","Candidate credibility / quality score","ATS",False,
  ("credibility_score",),),

# ----------------------------------------------------------------------
# JOBS / RECRUITING
# ----------------------------------------------------------------------

F("Jobs & Recruiting","Job requisition management","FEATURE_INDEX",False,
  ("/api/jobs","jobs"),),

F("Jobs & Recruiting","Job search","FEATURE_INDEX",False,
  ("jobsearch","search jobs","/api/jobs"),),

F("Jobs & Recruiting","Job ownership / primary recruiter","ATS",False,
  ("primary_recruiter_id",),),

F("Jobs & Recruiting","Multi-user job assignment","ATS",False,
  ("job_users",),),

F("Jobs & Recruiting","Interested-candidate workflow","ATS",False,
  ("interested_candidates",),),

F("Jobs & Recruiting","Submission workflow","FAQ",False,
  ("submissions",),("client_review","submitted")),

F("Jobs & Recruiting","Interview workflow","FAQ",False,
  ("interviews",),("scheduled","no_show")),

F("Jobs & Recruiting","Candidate assessments","INTEGRATIONS",False,
  ("assessments",),),

F("Jobs & Recruiting","Offer workflow","FAQ",False,
  ("'offer'","\"offer\""),("submission",)),

F("Jobs & Recruiting","Hire workflow","FAQ",False,
  ("'hired'","\"hired\""),("submission",)),

F("Jobs & Recruiting","Start management","ATS",False,
  ("starts",),("start_date",)),

F("Jobs & Recruiting","Start cancellation","ATS",False,
  ("cancellation_reason",),),

F("Jobs & Recruiting","Workflow history","ATS",False,
  ("workflow_history",),),

F("Jobs & Recruiting","Job distribution","INTEGRATIONS",True,
  ("job_distribution","job distribution"),),

F("Jobs & Recruiting","Job alerts","ENGAGEMENT",False,
  ("job_alerts","job-alerts"),),

# ----------------------------------------------------------------------
# CRM
# ----------------------------------------------------------------------

F("CRM","Company management","FAQ",False,
  ("companies",),("/api/companies",)),

F("CRM","Large-company / parent-child account structure","FEATURE_INDEX",False,
  ("parent_company_id",),),

F("CRM","Contact management","FAQ",False,
  ("contacts",),("/api/contacts",)),

F("CRM","Lead management","HOME",False,
  ("leads",),),

F("CRM","Opportunity pipeline","HOME",False,
  ("opportunities",),),

F("CRM","CRM tasks","HOME",False,
  ("tasks",),("owner_user_id",)),

F("CRM","Company pipeline dashboard","ATS",False,
  ("company_pipeline",),),

# ----------------------------------------------------------------------
# WORKFORCE / FLEX
# ----------------------------------------------------------------------

F("Workforce","Flexible / per-diem staffing","FEATURE_INDEX",False,
  ("shift","shifts"),("assignment","attendance")),

F("Workforce","Shift management","FEATURE_INDEX",False,
  ("shifts",),),

F("Workforce","Attendance management","FEATURE_INDEX",False,
  ("attendance",),),

F("Workforce","Assignment management","ATS",False,
  ("assignments",),),

F("Workforce","Timesheet entry","FAQ",False,
  ("timesheets",),),

F("Workforce","Timesheet approval","FAQ",False,
  ("timesheets",),("approved_by","approved_at")),

F("Workforce","Expense management","ATS",False,
  ("expenses",),),

F("Workforce","Expense approval","ATS",False,
  ("expenses",),("approved_by","approved_at")),

F("Workforce","Worker portal","HOME",False,
  ("workerportal","worker_portal"),),

F("Workforce","Approver portal","ATS",False,
  ("approverportal","approver_portal"),),

# ----------------------------------------------------------------------
# ONBOARDING / COMPLIANCE
# ----------------------------------------------------------------------

F("Onboarding & Compliance","Paperless onboarding","OPERATIONS",False,
  ("onboarding_packages",),("onboarding_requirements",)),

F("Onboarding & Compliance","Credential expiration tracking","ATS",False,
  ("expiry_date",),("license","certification","document")),

F("Onboarding & Compliance","EEO capability","FEATURE_INDEX",False,
  ("eeo","equal employment"),),

F("Onboarding & Compliance","Background-check integration","INTEGRATIONS",True,
  ("background",),("connector","gateway")),

F("Onboarding & Compliance","E-Verify integration","INTEGRATIONS",True,
  ("e-verify","everify"),),

F("Onboarding & Compliance","Electronic signature integration","INTEGRATIONS",True,
  ("e-sign","esign","signature"),("connector","gateway")),

F("Onboarding & Compliance","Reference-check integration","INTEGRATIONS",True,
  ("reference check","reference_check"),),

F("Onboarding & Compliance","WOTC integration","INTEGRATIONS",True,
  ("wotc",),),

F("Onboarding & Compliance","I-9 workflow","INTEGRATIONS",False,
  ("i-9","i9"),),

# ----------------------------------------------------------------------
# VMS / MSP
# ----------------------------------------------------------------------

F("VMS / MSP","VMS account management","FEATURE_INDEX",True,
  ("vms_accounts",),),

F("VMS / MSP","VMS mapping","FEATURE_INDEX",True,
  ("vms_mappings",),),

F("VMS / MSP","VMS job synchronization","FAQ",True,
  ("vms",),("job","sync")),

F("VMS / MSP","VMS submission synchronization","ATS",True,
  ("vms",),("submission",),("sync","mapping")),

F("VMS / MSP","VMS timesheet synchronization","ATS",True,
  ("vms",),("timesheet",),("sync","gateway")),

F("VMS / MSP","VMS expense synchronization","ATS",True,
  ("vms",),("expense",),("sync","gateway")),

F("VMS / MSP","VMS SOW support","ATS",True,
  ("sow","statement of work"),),

F("VMS / MSP","Supplier management","FEATURE_INDEX",False,
  ("suppliers",),),

F("VMS / MSP","Supplier releases","ATS",False,
  ("supplier_releases",),),

F("VMS / MSP","Supplier portal","FEATURE_INDEX",False,
  ("supplierportal","supplier_portal"),),

F("VMS / MSP","Job approval flow","ATS",False,
  ("approver","approval"),("job","workflow")),

F("VMS / MSP","Job catalog","ATS",False,
  ("job_catalog","job catalog"),),

# ----------------------------------------------------------------------
# FINANCIAL
# ----------------------------------------------------------------------

F("Financials","Invoice management","FAQ",False,
  ("invoices",),("/api/invoices",)),

F("Financials","Invoice line items","ATS",False,
  ("invoice_lines",),),

F("Financials","Invoice issuing","ATS",False,
  ("issued_at",),("invoice",)),

F("Financials","Part-payment tracking","ATS",False,
  ("part_paid",),("paid_amount",)),

F("Financials","Invoice payment tracking","ATS",False,
  ("paid_at",),("invoice",)),

F("Financials","Purchase orders","ATS",False,
  ("purchase_orders",),("po_number",)),

F("Financials","Finance aging","ATS",False,
  ("finance_aging",),),

F("Financials","Payroll integration","INTEGRATIONS",True,
  ("payroll",),("connector","gateway")),

F("Financials","General-ledger integration","INTEGRATIONS",True,
  ("general ledger","gl connector","gl_"),),

F("Financials","SOW project financials","ATS",False,
  ("sow","statement of work"),("financial","amount","billing")),

F("Financials","Margin / CalcuDiva-style calculations","FEATURE_INDEX",False,
  ("bill_rate",),("pay_rate",),("margin","calculator","calcudiva")),

# ----------------------------------------------------------------------
# REPORTING / ANALYTICS
# ----------------------------------------------------------------------

F("Reports & Analytics","Operational reporting","FEATURE_INDEX",False,
  ("report_summary","run_report"),),

F("Reports & Analytics","Custom report definitions","ATS",False,
  ("report_definitions",),),

F("Reports & Analytics","Report builder","ATS",False,
  ("report_builders","report builder"),),

F("Reports & Analytics","Scheduled reports","ATS",False,
  ("report_schedules","report-schedules"),),

F("Reports & Analytics","Report execution history","ATS",False,
  ("report_runs","report-runs"),),

F("Reports & Analytics","CSV report generation","OPERATIONS",False,
  ("csv.writer","text/csv"),),

F("Reports & Analytics","Role dashboards","ATS",False,
  ("dashboard",),("role",)),

F("Reports & Analytics","BI dashboard surface","ATS",False,
  ("bi shared","bishared","bi"),("dashboard","analytics")),

F("Reports & Analytics","Large report catalog capability","ATS",False,
  ("report_definitions",),("report","reports")),

# ----------------------------------------------------------------------
# COMMUNICATION / ENGAGEMENT
# ----------------------------------------------------------------------

F("Communication","Internal communication logging","ENGAGEMENT",False,
  ("communications",),("internal",)),

F("Communication","Email provider integration","INTEGRATIONS",True,
  ("email",),("connector","gateway")),

F("Communication","SMS provider integration","INTEGRATIONS",True,
  ("sms",),("connector","gateway")),

F("Communication","Communication templates","FEATURE_INDEX",False,
  ("template","templates"),("communication","email","sms")),

F("Communication","Campaign management","ENGAGEMENT",False,
  ("campaigns_r14",),("campaign_members",)),

F("Communication","Campaign execution","ENGAGEMENT",False,
  ("campaign_runs_r19",),),

F("Communication","Workflow automation","ENGAGEMENT",False,
  ("automations",),("workflow","action")),

F("Communication","Calendar functionality","FEATURE_INDEX",False,
  ("calendar",),),

F("Communication","Outlook synchronization","FEATURE_INDEX",True,
  ("outlook","microsoft graph","office365"),),

F("Communication","VOIP integration","INTEGRATIONS",True,
  ("voip","phone connector"),),

F("Communication","Video/meeting provider integration","ZOOM",True,
  ("create_meeting","meeting"),("connector","provider")),

# ----------------------------------------------------------------------
# PORTALS
# ----------------------------------------------------------------------

F("Portals","Candidate portal","FEATURE_INDEX",False,
  ("candidateportal","candidate_portal"),),

F("Portals","Client / hiring manager portal","ATS",False,
  ("clientportal","client_portal"),),

F("Portals","Supplier portal","FEATURE_INDEX",False,
  ("supplierportal","supplier_portal"),),

F("Portals","Worker portal","HOME",False,
  ("workerportal","worker_portal"),),

F("Portals","Approver portal","ATS",False,
  ("approverportal","approver_portal"),),

F("Portals","Candidate job search","FAQ",False,
  ("candidateportal","candidate_portal"),("jobs","search")),

F("Portals","Candidate sign-in","LOGIN",False,
  ("/api/login",),("candidate",)),

F("Portals","Candidate resume/document upload","FAQ",False,
  ("candidate_documents",),("content_base64","upload")),

F("Portals","Candidate job alerts","FAQ",False,
  ("job_alerts","job-alerts"),),

F("Portals","Multilingual candidate experience","HOME",False,
  ("i18n","language selector","multilingual"),),

# ----------------------------------------------------------------------
# ADMIN / SECURITY
# ----------------------------------------------------------------------

F("Administration","Role-based access control","FEATURE_INDEX",False,
  ("role_permissions",),),

F("Administration","Tenant permission overrides","FEATURE_INDEX",False,
  ("permission_denied_by_override",),),

F("Administration","Audit trail","FEATURE_INDEX",False,
  ("audit_log",),),

F("Administration","Workflow audit history","FEATURE_INDEX",False,
  ("workflow_history",),),

F("Administration","Custom fields configuration","FEATURE_INDEX",False,
  ("custom_fields",),),

F("Administration","Multi-tenant data model","LOGIN",False,
  ("tenant_id",),("tenants",)),

F("Administration","Session management","LOGIN",False,
  ("sessions",),("expires_at",)),

F("Administration","Password reset","LOGIN",False,
  ("password_reset","reset_token","reset token"),),

F("Administration","MFA / TOTP","LOGIN",False,
  ("mfa","totp"),),

F("Administration","SSO capability","LOGIN",True,
  ("sso","oauth","saml"),),

F("Administration","Login lockout / brute-force controls","LOGIN",False,
  ("login","auth"),("lock","429")),

F("Administration","User invitations","LOGIN",False,
  ("user_invitations",),),

# ----------------------------------------------------------------------
# INTEGRATION PLATFORM
# ----------------------------------------------------------------------

F("Integration Platform","Integration connector registry","INTEGRATIONS",False,
  ("integration_connectors",),),

F("Integration Platform","External gateway registry","INTEGRATIONS",False,
  ("external_gateways",),),

F("Integration Platform","External HTTP execution","INTEGRATIONS",False,
  ("urllib.request",),("external","connector","gateway")),

F("Integration Platform","External transaction audit","INTEGRATIONS",False,
  ("external_transactions_r19",),),

F("Integration Platform","Background-check adapter","INTEGRATIONS",True,
  ("background",),("gateway","connector")),

F("Integration Platform","Job-board adapter","INTEGRATIONS",True,
  ("job-board","job board"),("gateway","connector","distribution")),

F("Integration Platform","Assessment-provider adapter","INTEGRATIONS",True,
  ("assessment",),("gateway","connector")),

F("Integration Platform","Resume-screening adapter","INTEGRATIONS",True,
  ("resume screening","screening"),("gateway","connector")),

F("Integration Platform","Candidate-enrichment adapter","INTEGRATIONS",True,
  ("enrichment",),("gateway","connector")),

F("Integration Platform","Payroll adapter","INTEGRATIONS",True,
  ("payroll",),("gateway","connector")),

F("Integration Platform","GL adapter","INTEGRATIONS",True,
  ("general ledger","gl connector","gl_"),("gateway","connector")),

F("Integration Platform","VMS adapter","INTEGRATIONS",True,
  ("vms",),("gateway","connector")),

F("Integration Platform","Meeting adapter","ZOOM",True,
  ("meeting",),("gateway","connector","provider")),

# ----------------------------------------------------------------------
# MOBILE / ACCESSIBILITY SURFACE
# ----------------------------------------------------------------------

F("Mobile","Installable PWA / mobile web capability","HOME",False,
  ("manifest.webmanifest",),),

F("Mobile","Mobile worker time/expense capability","HOME",False,
  ("workerportal","worker_portal"),("timesheets",),("expenses",)),

F("Mobile","White-label application capability","HOME",False,
  ("white-label","white label","branding"),),
]


# ----------------------------------------------------------------------
# BUILD IMPLEMENTATION-ONLY CORPUS
#
# Never scan:
# - tests
# - audit files
# - documentation
# - this scanner
# - generated R21 feature authority
#
# This prevents the feature names/search terms themselves from becoming
# implementation evidence.
# ----------------------------------------------------------------------

ALLOWED_SUFFIXES={".py",".js",".html",".css",".sql",".json",".webmanifest"}

SKIP_TOP={
    "tests",
    "tools",
    ".git",
    ".venv",
    "audit-results",
}

SKIP_PREFIXES=(
    "R17-",
    "R18-",
    "R19-",
    "R20-",
    "R21-",
    "ACCEPTANCE",
    "FUNCTION-MAP",
    "ARCHITECTURE",
    "README",
)

corpus=[]

for p in ROOT.rglob("*"):

    if not p.is_file():
        continue

    rel=p.relative_to(ROOT)
    rels=rel.as_posix()

    if rel.parts and rel.parts[0] in SKIP_TOP:
        continue

    if any(part in SKIP_TOP for part in rel.parts):
        continue

    if p.suffix.lower() not in ALLOWED_SUFFIXES:
        continue

    if p.name.startswith(SKIP_PREFIXES):
        continue

    try:
        text=p.read_text(
            encoding="utf-8",
            errors="ignore"
        ).lower()
    except OSError:
        continue

    corpus.append((rels,text))


def find_group(group):

    evidence=[]

    for term in group:

        needle=term.lower()

        for filename,text in corpus:

            if needle in text:
                evidence.append(
                    f"{filename}::{term}"
                )

                if len(evidence)>=4:
                    return evidence

    return evidence


rows=[]

for f in FEATURES:

    group_evidence=[]
    complete=True

    for group in f["groups"]:

        ev=find_group(group)

        if not ev:
            complete=False

        group_evidence.extend(ev)

    if f["external"]:
        status=(
            "EXTERNAL_ADAPTER_EVIDENCE_FOUND_CREDENTIALS_REQUIRED"
            if complete
            else
            "EXTERNAL_ADAPTER_MISSING_OR_UNPROVEN"
        )
    else:
        status=(
            "IMPLEMENTATION_EVIDENCE_FOUND_FUNCTIONAL_PROOF_REQUIRED"
            if complete
            else
            "IMPLEMENTATION_GAP_OR_UNPROVEN"
        )

    rows.append({
        "category":f["category"],
        "feature":f["feature"],
        "source_id":f["source"],
        "source_url":SOURCES[f["source"]],
        "external":f["external"],
        "status":status,
        "implementation_evidence":" | ".join(group_evidence[:12]),
        "required_signal_groups":" AND ".join(
            "("+" OR ".join(x)+")"
            for x in f["groups"]
        ),
    })


matrix=ROOT/"R21-JOBDIVA-PUBLIC-PARITY-MATRIX.csv"

with matrix.open("w",newline="",encoding="utf-8") as fh:

    w=csv.DictWriter(
        fh,
        fieldnames=[
            "category",
            "feature",
            "source_id",
            "source_url",
            "external",
            "status",
            "implementation_evidence",
            "required_signal_groups",
        ]
    )

    w.writeheader()
    w.writerows(rows)


internal=[x for x in rows if not x["external"]]
external=[x for x in rows if x["external"]]

internal_found=[
    x for x in internal
    if x["status"].startswith("IMPLEMENTATION_EVIDENCE_FOUND")
]

internal_gap=[
    x for x in internal
    if x["status"]=="IMPLEMENTATION_GAP_OR_UNPROVEN"
]

external_found=[
    x for x in external
    if x["status"].startswith("EXTERNAL_ADAPTER_EVIDENCE_FOUND")
]

external_gap=[
    x for x in external
    if x["status"]=="EXTERNAL_ADAPTER_MISSING_OR_UNPROVEN"
]

summary={
    "total_public_capabilities":len(rows),
    "internal_capabilities":len(internal),
    "external_capabilities":len(external),
    "internal_implementation_evidence_found":len(internal_found),
    "internal_gap_or_unproven":len(internal_gap),
    "external_adapter_evidence_found":len(external_found),
    "external_adapter_missing_or_unproven":len(external_gap),
    "internal_gap_features":[x["feature"] for x in internal_gap],
    "external_gap_features":[x["feature"] for x in external_gap],
}

(ROOT/"R21-JOBDIVA-PUBLIC-PARITY-SUMMARY.json").write_text(
    json.dumps(summary,indent=2,ensure_ascii=False)+"\n",
    encoding="utf-8"
)

authority={
    "source_urls":SOURCES,
    "capabilities":FEATURES,
    "scanner_rule":{
        "tests_scanned":False,
        "audit_docs_scanned":False,
        "scanner_scanned_itself":False,
        "implementation_source_only":True,
        "signal_groups":"AND between groups / OR within each group",
    },
}

(ROOT/"R21-JOBDIVA-PUBLIC-AUTHORITY.json").write_text(
    json.dumps(authority,indent=2,ensure_ascii=False)+"\n",
    encoding="utf-8"
)


md=[
"# ATS-One R21 — JobDiva Public Parity Differential",
"",
"R20 is the frozen implementation baseline.",
"",
"Important: static implementation evidence is not functional parity.",
"Each capability with implementation evidence must still receive functional acceptance.",
"",
f"- Total public capabilities inventoried: {len(rows)}",
f"- Internal capabilities: {len(internal)}",
f"- External/provider capabilities: {len(external)}",
f"- Internal implementation evidence found: {len(internal_found)}",
f"- Internal gap/unproven: {len(internal_gap)}",
f"- External adapter evidence found: {len(external_found)}",
f"- External adapter gap/unproven: {len(external_gap)}",
"",
"## Internal gaps / unproven",
"",
]

if internal_gap:
    for x in internal_gap:
        md.append(
            f"- {x['category']} :: {x['feature']}"
        )
else:
    md.append("- None in static differential.")

md += [
"",
"## External adapters missing / unproven",
"",
]

if external_gap:
    for x in external_gap:
        md.append(
            f"- {x['category']} :: {x['feature']}"
        )
else:
    md.append("- None in static differential.")

md += [
"",
"## Interpretation",
"",
"- IMPLEMENTATION_EVIDENCE_FOUND_FUNCTIONAL_PROOF_REQUIRED does not mean JobDiva parity is proven.",
"- IMPLEMENTATION_GAP_OR_UNPROVEN must be implemented or explicitly disproven as a requirement.",
"- EXTERNAL_ADAPTER_EVIDENCE_FOUND_CREDENTIALS_REQUIRED requires real provider credentials before Connected/Success can be claimed.",
"- Private/undocumented JobDiva functionality requires client JobDiva tenant evidence.",
"",
]

(ROOT/"R21-JOBDIVA-PUBLIC-PARITY-SUMMARY.md").write_text(
    "\n".join(md)+"\n",
    encoding="utf-8"
)


print("="*72)
print(" ATS-ONE R21 JOBDIVA CLEAN-SOURCE PUBLIC PARITY DIFFERENTIAL")
print("="*72)

print(f"IMPLEMENTATION_SOURCE_FILES_SCANNED={len(corpus)}")
print(f"TOTAL_PUBLIC_CAPABILITIES={len(rows)}")
print(f"INTERNAL_CAPABILITIES={len(internal)}")
print(f"EXTERNAL_CAPABILITIES={len(external)}")

print(
    "INTERNAL_IMPLEMENTATION_EVIDENCE_FOUND="
    f"{len(internal_found)}"
)

print(
    "INTERNAL_GAP_OR_UNPROVEN="
    f"{len(internal_gap)}"
)

print(
    "EXTERNAL_ADAPTER_EVIDENCE_FOUND="
    f"{len(external_found)}"
)

print(
    "EXTERNAL_ADAPTER_MISSING_OR_UNPROVEN="
    f"{len(external_gap)}"
)

for x in internal_gap:
    print("GAP_INTERNAL="+x["feature"])

for x in external_gap:
    print("GAP_EXTERNAL="+x["feature"])

print("SCANNER_SELF_EVIDENCE=EXCLUDED")
print("TEST_EVIDENCE_AS_PRODUCT=EXCLUDED")
print("STATIC_EVIDENCE_IS_FUNCTIONAL_PARITY=NO")
print("PUBLIC_JOBDIVA_100_PERCENT=NOT_YET_PROVEN")
print("NEXT=FUNCTIONALLY_PROVE_AND_CLOSE_ALL_GAPS")
