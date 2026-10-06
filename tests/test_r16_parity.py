#!/usr/bin/env python3
from pathlib import Path
import re, sys, json

ROOT=Path(__file__).resolve().parents[1]
js=(ROOT/'web'/'r16.js').read_text(encoding='utf-8')
css=(ROOT/'web'/'r16.css').read_text(encoding='utf-8')
index=(ROOT/'web'/'index.html').read_text(encoding='utf-8')
logo=ROOT/'web'/'ats-one-logo.svg'

checks = {
 "R16_VERSION": "R16_JOBDIVA_PUBLIC_PARITY_RC1" in js,
 "FOUR_APP_MENU_GROUPS": all(x in js for x in ["Sourcing","Jobs","Analytics","Engagement"]),
 "NEW_CANDIDATE_FOUR_METHODS": all(x in js for x in ["Upload Resume","Email Resume","Paste Resume","Register Without Resume"]),
 "TALENT_EIGHT_TABS": all(x in js for x in ["Profession/Specialty","Licenses","Certifications","Qualification","Require","Exclude","Attribute","Title"]),
 "PROFESSION_ADD_REMOVE": all(x in js for x in ["ADD","REMOVE","r16AddProfession","r16RemoveProfession"]),
 "SKILL_AND_OR_NOT": all(x in js for x in ["r16AddSkill('AND')","r16AddSkill('OR')","r16AddSkill('NOT')"]),
 "SEPARATE_RESULTS_WORKSPACE": "r16-result-back" in js and "r16OpenResults" in js,
 "RESULT_ACTIONS": all(x in js for x in ["exclude","qualify","expand","hotlist","preview","relevancy","bulk","email"]),
 "PREVIEW_IS_INLINE_PANE": "r16PreviewPane" in js and "Resume Preview" in js,
 "RELEVANCY_SORT": "R16_RESULTS.sort" in js,
 "EXPAND_BROADENS": "p.specialty=''" in js and "years:0,recent:false" in js,
 "CANDIDATE_SPLIT_PROFILE": "r16-candidate-layout" in js and "r16-candidate-left" in js,
 "CANDIDATE_EXTENDED_TABS": all(x in js for x in ["Saved Email","e-interviews","Live Interviews","LinkedIn","Zoom Meetings"]),
 "DIVAMATCH_CHECK_SCORE": "Check Score" in js and "r16CheckJobScore" in js,
 "GLOBAL_MULTI_ENTITY": all(x in js for x in ["/api/candidates?q=","/api/jobs","/api/companies","/api/contacts"]),
 "JOB_LIST_EXTENDED": all(x in js for x in ["H.Manager","Harvest","Max Bill","Users"]),
 "ENGAGEMENT_PAGES": all(x in js for x in ["Company Calendars","Job Calendars","e-Interview","Live Interview","DivaBuzz"]),
 "TRUTHFUL_EXTERNAL_GATES": js.count("NOT CONNECTED") >= 5,
 "LOGO_ASSET": logo.exists() and "ats-one-logo.svg" in js,
 "INDEX_LOADS_R16_JS": "/r16.js" in index,
 "INDEX_LOADS_R16_CSS": "/r16.css" in index,
 "CSS_RESULT_FULLSCREEN": ".r16-result-back" in css,
}
failed=[k for k,v in checks.items() if not v]
for k,v in checks.items():
    print(f"{k}={'PASS' if v else 'FAIL'}")
print(f"R16_STATIC_TOTAL={len(checks)}")
print(f"R16_STATIC_FAIL={len(failed)}")
if failed:
    print("FAILED="+",".join(failed))
    raise SystemExit(1)
print("R16_PUBLIC_PARITY_STATIC_GATE=PASS")
print("LITERAL_PRIVATE_JOBDIVA_TENANT_PARITY=UNVERIFIED")
