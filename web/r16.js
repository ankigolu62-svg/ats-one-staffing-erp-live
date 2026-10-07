/* ATS-One R16 — JobDiva publicly-evidenced recruiter workflow parity overlay.
   Loaded after R14.  This file intentionally does not fake external integrations. */
window.R16_VERSION='R16_JOBDIVA_PUBLIC_PARITY_RC1';


function r16MenuCapability(route){

 const map={
  talent:'talent',
  newCandidateR16:'candidates',
  candidates:'candidates',
  employees:'assignments',
  hotlists:'hotlists',
  candidateNotes:'candidates',
  candidateAttributes:'candidates',
  candidateImport:'candidates',

  jobs:'jobs',
  primaryJobs:'jobs',
  jobSearch:'jobs',
  newJobR16:'jobs',
  dashboard:'dashboard',

  reports:'reports',
  biShared:'reports',

  calendar:'interviews',
  companyCalendarR16:'interviews',
  jobCalendarR16:'interviews',
  eInterviewR16:'assessments',
  liveInterviewR16:'interviews',
  divaBuzzR16:'communications',

  r19Ops:'r19Ops'
 };

 return map[route] || route;
}

function r16MenuAllowed(route){

 if(!ME || !ME.role){
  return false;
 }

 const allowed=new Set(
  (NAV[ME.role]||[]).map(x=>x[0])
 );

 // R19 enterprise execution center is available only
 // to staff roles that R19 itself supports.
 if(route==='r19Ops'){
  return [
   'admin',
   'teamlead',
   'recruiter',
   'sales',
   'hr',
   'finance'
  ].includes(ME.role);
 }

 return allowed.has(
  r16MenuCapability(route)
 );
}

function r16Brand(){
  return `<img src="/ats-one-logo.svg" class="r16-brand-img" alt="ATS One">`;
}

const R16_MENU = [
  ['sourcing','Sourcing',[
    ['talent','Talent Search'],['newCandidateR16','New Candidate'],['candidates','Search Candidates'],
    ['employees','Search Employees'],['hotlists','Candidate Hotlists'],['candidateNotes','Search Cand. Notes'],
    ['candidateAttributes','Search Attributes'],['candidateImport','Import Candidates']
  ]],
  ['jobs','Jobs',[
    ['jobs','My Jobs'],['primaryJobs','My Jobs as Primary'],['jobSearch','Search Jobs'],
    ['newJobR16','New Job'],['dashboard','My Jobs Dashboard'],['dashboard','Primary Jobs Dashboard']
  ]],
  ['analytics','Analytics',[
    ['reports','Reports'],['biShared','BI Shared With Me']
  ]],
  ['engagement','Engagement',[
    ['calendar','My Calendar'],['companyCalendarR16','Company Calendars'],['jobCalendarR16','Job Calendars'],
    ['eInterviewR16','e-Interview'],['liveInterviewR16','Live Interview'],['divaBuzzR16','DivaBuzz']
  ]]
];

renderShell = function(){
  document.body.innerHTML=`<div id="app"></div><div id="modalRoot"></div><div id="toastRoot"></div>`;
  const nav=NAV[ME.role]||[];
  $('#app').innerHTML=`
  <div class="app-shell r16-shell">
   <div class="topbar r16-topbar">
    <button class="r16-logo-button" aria-label="Home" onclick="go('menu')">${r16Brand()}</button>
    <div class="global-search r16-global">
      <input id="globalQ" placeholder="Search candidates, contacts, jobs, companies...">
      <button class="r10-icon-button" aria-label="Search" onclick="globalSearch()">${r10Icon("search")}</button>
    </div>
    <div class="top-icons">
      <span class="r10-top-icon" title="Reminders">${r10Icon("pin")}</span>
      <span class="r10-top-icon" title="Favorites">${r10Icon("star")}</span>
      <span class="r10-top-icon" title="Settings">${r10Icon("admin")}</span>
    </div>
    <div class="user-chip"><div class="avatar">${esc(ME.name[0])}</div><div><b>${esc(ME.name)}</b><div class="muted" style="font-size:10px">${esc(ME.role)}</div></div><button class="btn small r10-icon-button" aria-label="Sign out" onclick="logout()">${r10Icon("logout")}</button></div>
   </div>
   <div class="layout">
    <aside class="sidebar">
     <div class="side-title">Navigation</div>
     ${nav.map(x=>`<div class="navitem" data-route="${x[0]}" onclick="go('${x[0]}')"><span class="navicon">${r10Icon(x[0])}</span>${x[2]}</div>`).join('')}
     <div class="side-title">Session</div>
     <div class="navitem" onclick="go('menu')"><span class="navicon">${r10Icon("home")}</span>Home</div>
    </aside>
    <main class="content" id="content"></main>
   </div>
  </div>`;
  $('#globalQ').addEventListener('keydown',e=>{if(e.key==='Enter')globalSearch()});
};

pageMenu = function(){

 const groups=R16_MENU
  .map(group=>[
   group[0],
   group[1],
   group[2].filter(
    ([route])=>r16MenuAllowed(route)
   )
  ])
  .filter(group=>group[2].length);

 $('#content').innerHTML=
  `<div class="r16-launcher">
   ${groups.map(group=>`
    <section class="r16-menu-card ${group[0]}">
     <h2>${esc(group[1])}</h2>
     <div class="r16-menu-grid">
      ${group[2].map(([route,label])=>`
       <button
        class="r16-menu-item"
        data-r16-route="${esc(route)}"
        onclick="r16MenuGo('${route}')">
        <span>${
         r10Icon(
          route==='newCandidateR16'
           ?'candidates'
           :route==='newJobR16'
            ?'jobs'
            :route
         )
        }</span>
        <b>${esc(label)}</b>
       </button>`
      ).join('')}
     </div>
    </section>`
   ).join('')}
  </div>`;
};

function r16MenuGo(route){
  if(route==='newCandidateR16') return openCandidateForm();
  if(route==='newJobR16') return openJobForm();
  go(route);
}

globalSearch = async function(){
  const q=$('#globalQ')?.value.trim();
  if(!q)return;
  const lower=q.toLowerCase();
  if(!internalRoles.includes(ME.role))return toast('Global Search is limited to staff accounts.','err');
  let candidates,jobs,companies,contacts;
  try {
    [candidates,jobs,companies,contacts]=await Promise.all([
      api('/api/candidates?q='+encodeURIComponent(q)),
      api('/api/jobs'),
      api('/api/companies'),
      api('/api/contacts')
    ]);
  } catch(error) {
    toast('Global Search could not complete: '+(error.message||String(error)),'err');
    return;
  }
  const hit=x=>JSON.stringify(x||{}).toLowerCase().includes(lower);
  const js=jobs.filter(hit).slice(0,40), co=companies.filter(hit).slice(0,40), ct=contacts.filter(hit).slice(0,40);
  modal('Global Search',`
   <div class="r16-global-results">
    ${panel(`Candidates (${candidates.length})`,`<table class="grid"><tr><th>Name</th><th>Title</th><th>Location</th></tr>${candidates.slice(0,40).map(c=>`<tr><td><a class="link" onclick="closeModal();go('candidate/${c.id}')">${esc(c.first_name+' '+c.last_name)}</a></td><td>${esc(c.current_title||'')}</td><td>${esc([c.city,c.state].filter(Boolean).join(', '))}</td></tr>`).join('')}</table>`)}
    ${panel(`Jobs (${js.length})`,`<table class="grid"><tr><th>#</th><th>Title</th><th>Client</th></tr>${js.map(j=>`<tr><td><a class="link" onclick="closeModal();go('job/${j.id}')">${esc(j.job_no||'')}</a></td><td>${esc(j.title||'')}</td><td>${esc(j.company_name||'')}</td></tr>`).join('')}</table>`)}
    ${panel(`Companies (${co.length})`,`<table class="grid"><tr><th>Company</th><th>Industry</th><th>Location</th></tr>${co.map(x=>`<tr><td>${esc(x.name||'')}</td><td>${esc(x.industry||'')}</td><td>${esc([x.city,x.state].filter(Boolean).join(', '))}</td></tr>`).join('')}</table>`)}
    ${panel(`Contacts (${ct.length})`,`<table class="grid"><tr><th>Name</th><th>Company</th><th>Title</th></tr>${ct.map(x=>`<tr><td>${esc((x.first_name||'')+' '+(x.last_name||''))}</td><td>${esc(x.company_name||'')}</td><td>${esc(x.title||'')}</td></tr>`).join('')}</table>`)}
   </div>`,
   `<button class="btn" onclick="closeModal()">Close</button>`,true);
};

/* ---------------- Candidate intake ---------------- */
openCandidateForm = function(){
  modal('New Candidate — Choose Intake Method',`
   <div class="r16-intake-grid">
    <button onclick="r16CandidateUpload()"><b>Upload Resume</b><span>Upload a resume and review parsed fields before commit.</span></button>
    <button onclick="r16CandidateEmail()"><b>Email Resume</b><span>Inbound email intake requires a connected mail gateway.</span></button>
    <button onclick="r16CandidatePaste()"><b>Paste Resume</b><span>Paste resume text, parse it, review, then create.</span></button>
    <button onclick="r16CandidateRegister()"><b>Register Without Resume</b><span>Create the candidate manually without a resume.</span></button>
   </div>`,`<button class="btn" onclick="closeModal()">Cancel</button>`,true);
};

function r16CandidateRegister(){
  modal('Register Without Resume',`<form id="r16Reg"><div class="formgrid">${formFields([
    {name:'first_name',label:'First Name',required:true},{name:'last_name',label:'Last Name',required:true},
    {name:'email',label:'Email'},{name:'phone',label:'Phone'},{name:'current_title',label:'Current Title'},
    {name:'profession',label:'Profession'},{name:'specialty',label:'Specialty'},{name:'city',label:'City'},
    {name:'state',label:'State'},{name:'country',label:'Country',value:'USA'},
    {name:'source',label:'Resume Source',value:'Manual Registration'}
  ])}</div></form>`,
  `<button class="btn" onclick="openCandidateForm()">Back</button><button class="btn primary" onclick="r16CreateRegistered()">Create Candidate</button>`,true);
}
async function r16CreateRegistered(){
  try{const c=await api('/api/candidates',{method:'POST',body:fd($('#r16Reg'))});closeModal();toast('Candidate created');go('candidate/'+c.id)}catch(e){toast(e.message,'err')}
}

function r16CandidatePaste(){
  modal('Paste Resume',`
   <div class="field"><label>Resume Source</label><input id="r16PasteSource" value="Recruiter Paste"></div>
   <div class="field"><label>Resume Text</label><textarea id="r16PasteText" rows="18" placeholder="Paste the candidate resume here"></textarea></div>
   <div id="r16ParseReview"></div>`,
   `<button class="btn" onclick="openCandidateForm()">Back</button><button class="btn primary" onclick="r16ParsePasted()">Parse Resume</button>`,true);
}
async function r16ParsePasted(){
  try{
    const parsed=await api('/api/resume/parse',{method:'POST',body:{resume_text:$('#r16PasteText').value}});
    window.R16_PARSED=parsed;window.R16_PARSED.source=$('#r16PasteSource').value||'Recruiter Paste';
    $('#r16ParseReview').innerHTML=r16ParseReviewHtml(parsed);
  }catch(e){toast(e.message,'err')}
}
function r16ParseReviewHtml(p){
  return `<div class="r16-review"><h3>Recruiter Review Required</h3>
   <div class="formgrid">
    ${formFields([
      {name:'first_name',label:'First Name',value:p.first_name||''},{name:'last_name',label:'Last Name',value:p.last_name||''},
      {name:'email',label:'Email',value:p.email||''},{name:'phone',label:'Phone',value:p.phone||''},
      {name:'current_title',label:'Current Title',value:p.current_title||''}
    ]).replaceAll('name="','data-r16-review name="')}
   </div>
   <p><b>Parsed skills:</b> ${(p.skills||[]).map(x=>tag(`${x.skill} ${x.years||0} yrs`)).join(' ')||'None detected'}</p>
   <button class="btn primary" onclick="r16CommitParsedCandidate()">Create Candidate</button>
  </div>`;
}
async function r16CommitParsedCandidate(){
  const p=window.R16_PARSED||{}, body={...p,source:p.source||'Parsed Resume'};
  $$('#r16ParseReview [data-r16-review]').forEach(el=>body[el.name]=el.value);
  try{const c=await api('/api/candidates',{method:'POST',body});closeModal();toast('Candidate created from reviewed parse');go('candidate/'+c.id)}catch(e){toast(e.message,'err')}
}

function r16CandidateUpload(){
  modal('Upload Resume',`
   <div class="field"><label>Resume Source</label><input id="r16UploadSource" value="Recruiter Upload"></div>
   <div class="field"><label>Resume File</label><input id="r16ResumeFile" type="file" accept=".txt,.md,.csv,.rtf,.doc,.docx,.pdf"></div>
   <div class="r16-truth">Text/RTF-like files can be parsed locally. DOCX/PDF binary parsing requires a connected document parser; the UI will not fake a successful parse.</div>
   <div id="r16ParseReview"></div>`,
   `<button class="btn" onclick="openCandidateForm()">Back</button><button class="btn primary" onclick="r16ReadResumeFile()">Parse & Review</button>`,true);
}
async function r16ReadResumeFile(){
  const f=$('#r16ResumeFile')?.files?.[0]; if(!f)return toast('Choose a resume file','err');
  const ext=(f.name.split('.').pop()||'').toLowerCase();
  if(['pdf','doc','docx'].includes(ext))return toast('Binary document parser is not connected; use Paste Resume or connect a parser.','err');
  const text=await f.text();$('#r16PasteText')?.remove();
  try{
    const parsed=await api('/api/resume/parse',{method:'POST',body:{resume_text:text}});
    parsed.source=$('#r16UploadSource').value||'Recruiter Upload';window.R16_PARSED=parsed;
    $('#r16ParseReview').innerHTML=r16ParseReviewHtml(parsed);
  }catch(e){toast(e.message,'err')}
}
function r16CandidateEmail(){
  modal('Email Resume Intake',`
   <div class="r16-external-card"><h3>Inbound Resume Email Gateway</h3>
   <p>JobDiva-style email ingestion requires an authenticated production mailbox / inbound mail connector.</p>
   <b>Status: NOT CONNECTED</b><p>No candidate will be fabricated from an email until a real connector is configured.</p></div>`,
   `<button class="btn" onclick="openCandidateForm()">Back</button><button class="btn" onclick="closeModal()">Close</button>`,true);
}

/* ---------------- Talent Search ---------------- */
const R16_SPECIALTIES={
 'RN':['Cardiology','Case Management','Cath Lab','CCU','CVICU','ER','ICU','Labor & Delivery','Med/Surg','NICU','OR','PACU','Pediatrics','Telemetry'],
 'Software Engineer':['Backend','Frontend','Full Stack','Java Backend','Distributed Systems','Mobile'],
 'Data Engineer':['Data Platform','ETL / ELT','Databricks','Spark','Cloud Data','Streaming'],
 'QA / SDET':['Automation','API Testing','Performance','Mobile','SDET'],
 'Business Analyst':['BFSI','Healthcare','Product','Data','ERP'],
 'Project Manager':['IT','Infrastructure','ERP','Healthcare','BFSI']
};

blankSearch = function(){
  return {tab:'Profession/Specialty',profession:'',specialty:'',licenses:[],certifications:[],qualification:'',
    require:[{term:'',years:0,recent:false,operator:'AND',without_mapping:false}],
    exclude:[],exclude_candidate_ids:[],attributes:[],title:'',state:'',zip:'',radius:'50',
    pay_min:'',pay_max:'',available_before:'',without_mapping:false,raw_boolean:''};
};

pageTalent = async function(){SEARCH_STATE=SEARCH_STATE||blankSearch();r16RenderTalent()};

function r16ProfessionNames(){
  return [...new Set([...(typeof professions!=='undefined'?professions:[]),...Object.keys(R16_SPECIALTIES)])].sort();
}
function r16AddProfession(p){SEARCH_STATE.profession=p;if(!(R16_SPECIALTIES[p]||[]).includes(SEARCH_STATE.specialty))SEARCH_STATE.specialty='';r16RenderTalent()}
function r16RemoveProfession(){SEARCH_STATE.profession='';SEARCH_STATE.specialty='';r16RenderTalent()}
function r16SetSpecialty(s){SEARCH_STATE.specialty=SEARCH_STATE.specialty===s?'':s;r16RenderTalent()}

function r16RequireRow(r,i){
 return `<div class="r16-skill-row">
  <select onchange="SEARCH_STATE.require[${i}].operator=this.value;r16RefreshCriteria()">
   ${['AND','OR','NOT'].map(x=>`<option ${r.operator===x?'selected':''}>${x}</option>`).join('')}
  </select>
  <input placeholder="Skill / term" value="${esc(r.term||'')}" oninput="SEARCH_STATE.require[${i}].term=this.value;r16RefreshCriteria();r10SuggestInline(this,'skill')">
  <input type="number" min="0" step=".5" title="Relevant years" value="${esc(r.years||0)}" oninput="SEARCH_STATE.require[${i}].years=this.value;r16RefreshCriteria()">
  <label><input type="checkbox" ${r.recent?'checked':''} onchange="SEARCH_STATE.require[${i}].recent=this.checked;r16RefreshCriteria()"> Recent</label>
  <label><input type="checkbox" ${r.without_mapping?'checked':''} onchange="SEARCH_STATE.require[${i}].without_mapping=this.checked"> w/o Mapping</label>
  <button class="btn small" onclick="SEARCH_STATE.require.splice(${i},1);r16RenderTalent()">✕</button>
 </div>`;
}
function r16AddSkill(op){SEARCH_STATE.require.push({term:'',years:0,recent:false,operator:op,without_mapping:false});r16RenderTalent()}

function r16CompileCriteria(){
  const s=SEARCH_STATE,b=[];
  if(s.profession)b.push(`PROFESSION [ ${s.profession} IS ${s.specialty||'ANY'} ]`);
  (s.licenses||[]).filter(x=>x.type).forEach(x=>b.push(`LICENCES=("${x.type}" ST IN {${x.state||'ANY'}})`));
  (s.certifications||[]).filter(x=>x.name).forEach(x=>b.push(`CERTIFICATION [ ${x.name} ]`));
  (s.require||[]).filter(x=>x.term).forEach((x,i)=>{
    const op=i===0?'':`${x.operator||'AND'} `;
    b.push(`${op}(${x.term}${x.recent?' RECENT':''}${+x.years>0?' OVER '+x.years+' YRS':''}${x.without_mapping?' W/O MAPPING':''})`);
  });
  (s.exclude||[]).filter(x=>x.term).forEach(x=>b.push(`NOT (${x.term})`));
  if(s.qualification)b.push(`QUALIFICATION [ ${s.qualification} ]`);
  if(s.title)b.push(`TITLE [ ${s.title} ]`);
  return b.join(' ')||'ALL ACTIVE CANDIDATES';
}
function r16RefreshCriteria(){const e=$('#criteriaPreview');if(e)e.textContent=r16CompileCriteria()}

function r16Payload(){
  const s=SEARCH_STATE;
  const required=[],excluded=[...(s.exclude||[])];
  (s.require||[]).filter(x=>x.term).forEach((x,idx)=>{
    if((x.operator||'AND')==='NOT')excluded.push({term:x.term});
    else required.push({term:x.term,years:x.years,recent:x.recent,operator:required.length===0?'AND':(x.operator||'AND')});
  });
  return {
    profession:s.profession||'',specialty:s.specialty||'',
    licenses:(s.licenses||[]).filter(x=>x.type),certifications:(s.certifications||[]).filter(x=>x.name),
    qualification:s.qualification||'',require:required,exclude:excluded.filter(x=>x.term),
    exclude_candidate_ids:s.exclude_candidate_ids||[],attributes:s.attributes||[],title:s.title||'',
    state:s.state||'',zip:s.zip||'',radius_miles:s.zip?s.radius:'',
    pay_min:s.pay_min||'',pay_max:s.pay_max||'',available_before:s.available_before||'',
    without_mapping:!!s.without_mapping,raw_boolean:s.raw_boolean||''
  };
}

function r16RenderTalent(){
 const s=SEARCH_STATE,tabs=['Profession/Specialty','Licenses','Certifications','Qualification','Require','Exclude','Attribute','Title'];
 let main='';
 if(s.tab==='Profession/Specialty'){
   const profs=r16ProfessionNames(), specs=R16_SPECIALTIES[s.profession]||[];
   main=`<div class="sectionhead">PROFESSION / SPECIALTY</div>
   <div class="r16-prof-grid">
    <div><h4>Profession</h4><div class="r16-choice-list">${profs.map(p=>`<div class="r16-choice"><span>${esc(p)}</span><button class="btn small ${s.profession===p?'danger':'success'}" onclick="${s.profession===p?'r16RemoveProfession()':`r16AddProfession('${p.replaceAll("'","\\'")}')`}">${s.profession===p?'REMOVE':'ADD'}</button></div>`).join('')}</div></div>
    <div><h4>Specialty</h4>${s.profession?`<div class="r16-choice-list">${specs.map(sp=>`<div class="r16-choice"><span>${esc(sp)}</span><button class="btn small ${s.specialty===sp?'danger':'success'}" onclick="r16SetSpecialty('${sp.replaceAll("'","\\'")}')">${s.specialty===sp?'REMOVE':'ADD'}</button></div>`).join('')||'<div class="empty">No configured specialty vocabulary for this profession.</div>'}</div>`:'<div class="empty">ADD a profession first.</div>'}</div>
   </div>`;
 }
 if(s.tab==='Licenses')main=`<div class="sectionhead">LICENSES</div>${licenseRows()}<button class="btn small" onclick="addLicense()">+ AND License</button>`;
 if(s.tab==='Certifications')main=`<div class="sectionhead">CERTIFICATIONS</div>${certRows()}<button class="btn small" onclick="addCert()">+ AND Certification</button>`;
 if(s.tab==='Qualification')main=`<div class="sectionhead">QUALIFICATION</div><div class="field"><label>Degree / Qualification</label><input value="${esc(s.qualification)}" oninput="SEARCH_STATE.qualification=this.value;r16RefreshCriteria();r10SuggestInline(this,'qualification')"></div>`;
 if(s.tab==='Require')main=`<div class="sectionhead">REQUIRE — SKILLS / RELEVANT EXPERIENCE</div>
   <div class="r16-builder-tools"><button class="btn small" onclick="r16AddSkill('AND')">+ AND</button><button class="btn small" onclick="r16AddSkill('OR')">+ OR</button><button class="btn small" onclick="r16AddSkill('NOT')">+ NOT</button></div>
   ${(s.require||[]).map(r16RequireRow).join('')||'<div class="empty">Add a skill condition.</div>'}
   <div class="field"><label>Advanced Boolean Expression</label><textarea rows="3" oninput="SEARCH_STATE.raw_boolean=this.value;r16RefreshCriteria()" placeholder='(JAVA RECENT OVER 5 YRS) AND (SPRING OR KAFKA)'>${esc(s.raw_boolean||'')}</textarea></div>`;
 if(s.tab==='Exclude')main=`<div class="sectionhead">EXCLUDE</div>${excludeRows()}<button class="btn small" onclick="addExclude()">+ Excluded Term</button>`;
 if(s.tab==='Attribute')main=`<div class="sectionhead">ATTRIBUTE</div><div class="field"><label>Candidate Attributes</label><input value="${esc((s.attributes||[]).join(', '))}" oninput="SEARCH_STATE.attributes=this.value.split(',').map(x=>x.trim()).filter(Boolean);r16RefreshCriteria()"></div>`;
 if(s.tab==='Title')main=`<div class="sectionhead">TITLE</div><div class="field"><label>Current / Recent Title</label><input value="${esc(s.title)}" oninput="SEARCH_STATE.title=this.value;r16RefreshCriteria();r10SuggestInline(this,'title')"></div>`;

 $('#content').innerHTML=`<div class="page r16-talent">${head('Talent Search','App Menu › Sourcing › Talent Search','<button class="btn" onclick="saveDynamicPool()">Save Search / Dynamic Pool</button>')}
  <div class="search-shell">
   <div class="search-titlebar">Talent Search</div>
   <div class="search-tabs">${tabs.map(t=>`<div class="search-tab ${s.tab===t?'active':''}" onclick="SEARCH_STATE.tab='${t}';r16RenderTalent()">${t}</div>`).join('')}</div>
   <div class="search-grid">
    <div class="search-main">${main}<div class="criteria-box" id="criteriaPreview">${esc(r16CompileCriteria())}</div></div>
    <div class="search-side">
     <div class="sectionhead">REFINE SEARCH</div>
     <div class="side-row"><label>State:</label><input value="${esc(s.state)}" oninput="SEARCH_STATE.state=this.value"></div>
     <div class="side-row"><label>Zip Code:</label><input value="${esc(s.zip)}" oninput="SEARCH_STATE.zip=this.value"></div>
     <div class="side-row"><label>Within:</label><select onchange="SEARCH_STATE.radius=this.value">${['25','50','100','250'].map(x=>`<option ${s.radius===x?'selected':''}>${x}</option>`).join('')}</select></div>
     <div class="sectionhead" style="margin-top:12px">SALARY / PAY</div>
     <div class="side-row"><label>Min:</label><input type="number" value="${esc(s.pay_min)}" oninput="SEARCH_STATE.pay_min=this.value"></div>
     <div class="side-row"><label>Max:</label><input type="number" value="${esc(s.pay_max)}" oninput="SEARCH_STATE.pay_max=this.value"></div>
     <div class="sectionhead" style="margin-top:12px">AVAILABILITY</div>
     <div class="side-row"><label>Available by:</label><input type="date" value="${esc(s.available_before)}" oninput="SEARCH_STATE.available_before=this.value"></div>
     <label class="r16-check"><input type="checkbox" ${s.without_mapping?'checked':''} onchange="SEARCH_STATE.without_mapping=this.checked"> w/o Mapping (all skill terms)</label>
     <div class="r16-external-mini"><b>Real-Time Job Board Access</b><br>Status: NOT CONNECTED</div>
    </div>
   </div>
   <div class="search-footer"><button class="btn primary" onclick="runTalentSearch()">SEARCH</button> <button class="btn" onclick="SEARCH_STATE=blankSearch();r16RenderTalent()">CLEAR</button></div>
  </div>
 </div>`;
}

let R16_RESULTS=[],R16_RESULT_CRITERIA='',R16_RESULT_MS=0,R16_RESULT_PAGE=1,R16_RESULT_SIZE=50,R16_EXPANDED=false;

runTalentSearch = async function(){
 try{
  const d=await api('/api/search/talent',{method:'POST',body:r16Payload()});
  R16_RESULTS=d.results||[];R16_RESULT_CRITERIA=d.criteria||r16CompileCriteria();R16_RESULT_MS=d.duration_ms||0;R16_RESULT_PAGE=1;R16_EXPANDED=false;selectedSearch.clear();
  r16OpenResults();
 }catch(e){toast(e.message,'err')}
};

function r16OpenResults(){
 const root=$('#modalRoot');if(!root)return;
 root.innerHTML=`<div class="r16-result-back"><div class="r16-result-window">
  <div class="r16-result-head"><div><b>Talent Search Results</b><div class="muted">${esc(R16_RESULT_CRITERIA)}</div></div><button class="btn" onclick="closeModal()">✕ Close</button></div>
  <div id="r16ResultBody"></div><div id="r16PreviewPane"></div>
 </div></div>`;
 r16RenderResults();
}
function r16RenderResults(){
 const body=$('#r16ResultBody');if(!body)return;
 const rows=[...R16_RESULTS];const start=(R16_RESULT_PAGE-1)*R16_RESULT_SIZE,end=Math.min(start+R16_RESULT_SIZE,rows.length),shown=rows.slice(start,end);
 body.innerHTML=`
  <div class="search-criteria-line">Search Criteria: <b>${esc(R16_RESULT_CRITERIA)}</b><span class="muted" style="float:right">Showing ${rows.length?start+1:0}-${end} of ${rows.length} · ${R16_RESULT_MS} ms ${R16_EXPANDED?'· EXPANDED':''}</span></div>
  <div class="actionbar">
   <span class="actionlink" onclick="r16ResultAction('exclude')">✖ Exclude</span>
   <span class="actionlink" onclick="r16ResultAction('qualify')">✓ Qualify</span>
   <span class="actionlink" onclick="r16ResultAction('expand')">◉ Expand</span>
   <span class="actionlink" onclick="r16ResultAction('hotlist')">🔥 Hotlist</span>
   <span class="actionlink" onclick="r16ResultAction('preview')">🔎 Preview</span>
   <span class="actionlink" onclick="r16ResultAction('relevancy')">↕ Relevancy</span>
   <span class="actionlink" onclick="r16ResultAction('bulk')">Bulk Action ▾</span>
   <span class="actionlink" onclick="r16ResultAction('email')">✉ Email Merge</span>
  </div>
  <div class="tablewrap r16-result-table"><table class="grid"><tr>
   <th><input type="checkbox" onchange="r16SelectAllVisible(this.checked)"></th><th>Name</th><th>Phone</th><th>City</th><th>State</th><th>Received</th><th>Available</th><th>Last Note</th><th>Relevancy</th>
  </tr>${shown.map(c=>`<tr data-cid="${c.id}">
   <td><input class="srchk" type="checkbox" value="${c.id}" ${selectedSearch.has(c.id)?'checked':''} onchange="toggleSearchSel(${c.id},this.checked)"></td>
   <td><a class="link" onclick="closeModal();go('candidate/${c.id}')">${esc(c.first_name+' '+c.last_name)}</a><br><small>${esc(c.current_title||'')}</small></td>
   <td>${esc(c.phone||'')}</td><td>${esc(c.city||'')}</td><td>${esc(c.state||'')}</td><td>${fmtDate(c.created_at)}</td><td>${fmtDate(c.availability_date)}</td><td>${c.notes?.[0]?fmtDate(c.notes[0].created_at):''}</td><td class="score">${c.relevance}%</td>
  </tr>`).join('')}</table></div>
  <div class="r16-pager"><button class="btn small" ${R16_RESULT_PAGE<=1?'disabled':''} onclick="R16_RESULT_PAGE--;r16RenderResults()">Previous</button><span>Page ${R16_RESULT_PAGE} / ${Math.max(1,Math.ceil(rows.length/R16_RESULT_SIZE))}</span><button class="btn small" ${end>=rows.length?'disabled':''} onclick="R16_RESULT_PAGE++;r16RenderResults()">Next</button></div>`;
}
function r16SelectAllVisible(on){$$('#r16ResultBody .srchk').forEach(x=>{x.checked=on;toggleSearchSel(+x.value,on)})}
async function r16ResultAction(a){
 const ids=[...selectedSearch];
 if(a!=='expand' && a!=='relevancy' && !ids.length)return toast('Select one or more candidates first','err');
 if(a==='exclude'){SEARCH_STATE.exclude_candidate_ids=[...new Set([...(SEARCH_STATE.exclude_candidate_ids||[]),...ids])];const d=await api('/api/search/talent',{method:'POST',body:r16Payload()});R16_RESULTS=d.results||[];R16_RESULT_CRITERIA=d.criteria||R16_RESULT_CRITERIA;selectedSearch.clear();return r16RenderResults()}
 if(a==='expand'){
   const p=r16Payload();p.specialty='';p.require=(p.require||[]).map(x=>({...x,years:0,recent:false}));p.radius_miles=p.zip?250:'';
   const d=await api('/api/search/talent',{method:'POST',body:p});R16_RESULTS=d.results||[];R16_RESULT_CRITERIA='EXPANDED: '+(d.criteria||'');R16_RESULT_MS=d.duration_ms||0;R16_EXPANDED=true;selectedSearch.clear();return r16RenderResults();
 }
 if(a==='preview')return r16PreviewCandidate(ids[0]);
 if(a==='relevancy'){R16_RESULTS.sort((x,y)=>(y.relevance||0)-(x.relevance||0));return r16RenderResults()}
 if(a==='qualify')return r16QualifyDialog(ids);
 if(a==='hotlist')return r16HotlistDialog(ids);
 if(a==='email')return r16EmailDialog(ids);
 if(a==='bulk')return r16BulkDialog(ids);
}
async function r16PreviewCandidate(id){
 const c=await api('/api/candidates/'+id);
 $('#r16PreviewPane').innerHTML=`<aside class="r16-preview"><button class="btn small r16-preview-close" onclick="$('#r16PreviewPane').innerHTML=''">✕</button>
 <h2>${esc(c.first_name+' '+c.last_name)}</h2><div class="muted">${esc(c.current_title||'')} · ${esc([c.city,c.state].filter(Boolean).join(', '))}</div>
 <h3>Resume Preview</h3><div class="r16-resume-preview">${esc(c.resume_text||c.summary||'No resume text available.')}</div></aside>`;
}
async function r16QualifyDialog(ids){
 const jobs=(REF?.jobs||[]).filter(j=>j.status==='Open');
 $('#r16PreviewPane').innerHTML=`<aside class="r16-preview"><button class="btn small r16-preview-close" onclick="$('#r16PreviewPane').innerHTML=''">✕</button><h3>Qualify against Job</h3><select id="r16QualJob">${jobs.map(j=>`<option value="${j.id}">${esc(j.job_no+' — '+j.title)}</option>`).join('')}</select><button class="btn primary" onclick="r16DoQualify(${JSON.stringify(ids)})">Qualify ${ids.length}</button></aside>`;
}
async function r16DoQualify(ids){const jid=+$('#r16QualJob').value;await api('/api/search/bulk',{method:'POST',body:{action:'qualify',candidate_ids:ids,job_id:jid}});toast(`${ids.length} candidate(s) qualified`);$('#r16PreviewPane').innerHTML=''}
async function r16HotlistDialog(ids){
 const hs=await api('/api/hotlists');$('#r16PreviewPane').innerHTML=`<aside class="r16-preview"><button class="btn small r16-preview-close" onclick="$('#r16PreviewPane').innerHTML=''">✕</button><h3>Add to Hotlist</h3><select id="r16Hot">${hs.map(h=>`<option value="${h.id}">${esc(h.name)}</option>`).join('')}</select><button class="btn primary" onclick="r16DoHotlist(${JSON.stringify(ids)})">Add ${ids.length}</button></aside>`;
}
async function r16DoHotlist(ids){await api('/api/search/bulk',{method:'POST',body:{action:'hotlist',candidate_ids:ids,hotlist_id:+$('#r16Hot').value}});toast('Added to hotlist');$('#r16PreviewPane').innerHTML=''}
function r16EmailDialog(ids){$('#r16PreviewPane').innerHTML=`<aside class="r16-preview"><button class="btn small r16-preview-close" onclick="$('#r16PreviewPane').innerHTML=''">✕</button><h3>Email Merge</h3><input id="r16EmailSubject" placeholder="Subject"><textarea id="r16EmailBody" rows="8" placeholder="Message"></textarea><button class="btn primary" onclick="r16DoEmail(${JSON.stringify(ids)})">Send / Log ${ids.length}</button><p class="muted">Delivery requires a connected production email provider; without one this records the communication only.</p></aside>`}
async function r16DoEmail(ids){await api('/api/search/bulk',{method:'POST',body:{action:'email',candidate_ids:ids,subject:$('#r16EmailSubject').value,body:$('#r16EmailBody').value}});toast('Email merge logged');$('#r16PreviewPane').innerHTML=''}
function r16BulkDialog(ids){$('#r16PreviewPane').innerHTML=`<aside class="r16-preview"><button class="btn small r16-preview-close" onclick="$('#r16PreviewPane').innerHTML=''">✕</button><h3>Bulk Action</h3><select id="r16BulkKind"><option value="qualify">Qualify</option><option value="hotlist">Hotlist</option><option value="email">Email Merge</option></select><button class="btn primary" onclick="r16ResultAction($('#r16BulkKind').value)">Continue</button></aside>`}

/* ---------------- Candidate profile ---------------- */
let R16_CAND_TAB='Resume';
const R16_CAND_TABS=['Resume','Wallet','Credibility','DivaMatch','Saved Email','Tasks','Assignment','Onboard','Calendar','e-interviews','Live Interviews','LinkedIn','Zoom Meetings'];

pageCandidate = async function(id){
 const c=await api('/api/candidates/'+id);window.R16_CURRENT_CAND=c;
 const notes=(c.notes||[]),licenses=(c.licenses||[]),submitted=(c.submissions||[]);
 const left=`<aside class="r16-candidate-left">
  <h2>${esc(c.first_name+' '+c.last_name)}</h2><div class="muted">${esc(c.current_title||'')}</div>
  <div class="r16-cand-stat"><b>Submitted</b><span>${submitted.length}</span></div>
  <div class="r16-cand-stat"><b>Interviewed</b><span>${submitted.filter(x=>String(x.status||'').toLowerCase().includes('interview')).length}</span></div>
  <div class="r16-cand-stat"><b>Started / Assignments</b><span>${(c.assignments||[]).length}</span></div>
  <div class="r16-cand-stat"><b>Notes</b><span>${notes.length}</span></div>
  <div class="r16-cand-stat"><b>Qualifications</b><span>${(c.qualifications||[]).length}</span></div>
  <h4>Licenses</h4>${licenses.map(x=>`<div class="r16-license"><b>${esc(x.license_type||'')}</b><span>${esc(x.state||'')} ${esc(x.license_number||'')} · Exp ${fmtDate(x.expiry_date)}</span></div>`).join('')||'<div class="muted">None</div>'}
  <hr><div>${esc(c.email||'')}</div><div>${esc(c.phone||'')}</div><div>${esc([c.city,c.state,c.country].filter(Boolean).join(', '))}</div>
 </aside>`;
 $('#content').innerHTML=`<div class="page r16-candidate-page">${head('Candidate Profile','Talent Management › Candidate',`<button class="btn" onclick="addCandidateNote(${c.id})">+ Note</button><button class="btn" onclick="candidateHotlist(${c.id})">Hotlist</button><button class="btn primary" onclick="sendCandidateEmail(${c.id})">Contact</button>`)}
  <div class="r16-candidate-layout">${left}<section class="r16-candidate-main"><div class="tabs r16-cand-tabs">${R16_CAND_TABS.map(t=>`<button class="tabbtn ${R16_CAND_TAB===t?'active':''}" onclick="R16_CAND_TAB='${t}';r16CandidateTab(${c.id})">${esc(t)}</button>`).join('')}</div><div id="r16CandBody"></div></section></div></div>`;
 await r16CandidateTab(c.id);
};

async function r16CandidateTab(id){
 const c=window.R16_CURRENT_CAND?.id==id?window.R16_CURRENT_CAND:await api('/api/candidates/'+id);window.R16_CURRENT_CAND=c;
 let body='';
 if(R16_CAND_TAB==='Resume'){
   body=panel('Resume Versions / Parsed Resume',`<div class="r16-resume-version"><b>Current Resume</b><span>Source: ${esc(c.source||'Unknown')} · Received ${fmtDate(c.created_at)}</span></div><div class="r16-resume-preview">${esc(c.resume_text||c.summary||'No resume text available.')}</div>${(c.documents||[]).filter(x=>String(x.doc_type||'').toLowerCase().includes('resume')).map(x=>`<div class="kv"><b>${esc(x.name||x.file_name)}</b><span>${status(x.status)} · ${fmtDate(x.created_at)}</span></div>`).join('')}`);
 }
 if(R16_CAND_TAB==='Wallet')body=`<div class="r16-wallet-status">${(c.documents||[]).length?'Credential Wallet: REVIEW':'Credential Wallet: INCOMPLETE'}</div><div class="three-col">${panel('Licenses',(c.licenses||[]).map(x=>`<div class="kv"><b>${esc(x.license_type)}</b><span>${status(x.status)} · ${esc(x.state||'')} · ${fmtDate(x.expiry_date)}</span></div>`).join('')||'None')}${panel('Certifications',(c.certifications||[]).map(x=>`<div class="kv"><b>${esc(x.name)}</b><span>${status(x.status)} · ${fmtDate(x.expiry_date)}</span></div>`).join('')||'None')}${panel('Documents',(c.documents||[]).map(x=>`<div class="kv"><b>${esc(x.name)}</b><span>${status(x.status)}</span></div>`).join('')||'None')}</div>`;
 if(R16_CAND_TAB==='Credibility')body=panel('Candidate Credibility',`<div class="r16-score">${c.credibility_score||0}/100</div><div class="progress"><i style="width:${c.credibility_score||0}%"></i></div><p>Score reflects locally evidenced profile completeness and verified records. It is not represented as a JobDiva proprietary score.</p>`);
 if(R16_CAND_TAB==='DivaMatch')body=`<div class="r16-match-tools"><input id="r16CheckJob" placeholder="Job #"><button class="btn" onclick="r16CheckJobScore(${c.id})">Check Score</button></div><div id="r16MatchBody">Loading matches…</div>`;
 if(R16_CAND_TAB==='Saved Email')body=panel('Saved Email / Communication History',`<table class="grid"><tr><th>Date</th><th>Channel</th><th>Direction</th><th>Subject</th><th>Status</th></tr>${(c.communications||[]).map(x=>`<tr><td>${fmtDate(x.created_at)}</td><td>${esc(x.channel)}</td><td>${esc(x.direction)}</td><td>${esc(x.subject||'')}</td><td>${status(x.status)}</td></tr>`).join('')}</table>`);
 if(R16_CAND_TAB==='Tasks')body=panel('Candidate Tasks',`${(c.tasks||[]).map(x=>`<div class="kv"><b>${esc(x.title)}</b><span>${fmtDate(x.due_at)} · ${status(x.status)}</span></div>`).join('')||'<div class="empty">No tasks</div>'}`);
 if(R16_CAND_TAB==='Assignment')body=panel('Assignments',`<table class="grid"><tr><th>Job</th><th>Company</th><th>Status</th><th>Start</th><th>End</th><th>Bill / Pay</th></tr>${(c.assignments||[]).map(x=>`<tr><td>${esc(x.job_no||'')} · ${esc(x.job_title||'')}</td><td>${esc(x.company_name||'')}</td><td>${status(x.status)}</td><td>${fmtDate(x.start_date)}</td><td>${fmtDate(x.end_date)}</td><td>${money(x.bill_rate)} / ${money(x.pay_rate)}</td></tr>`).join('')}</table>`);
 if(R16_CAND_TAB==='Onboard')body=panel('Onboarding',`<table class="grid"><tr><th>Package</th><th>Job</th><th>Due</th><th>Status</th></tr>${(c.onboarding||[]).map(x=>`<tr><td>${esc(x.package_name||'')}</td><td>${esc(x.job_no||'')} ${esc(x.job_title||'')}</td><td>${fmtDate(x.due_date)}</td><td>${status(x.status)}</td></tr>`).join('')}</table>`);
 if(R16_CAND_TAB==='Calendar'){const ints=(await api('/api/interviews').catch(()=>[])).filter(x=>+x.candidate_id===+c.id);body=panel('Calendar',`<table class="grid"><tr><th>Date / Time</th><th>Job</th><th>Type</th><th>Status</th></tr>${ints.map(x=>`<tr><td>${x.scheduled_at?new Date(x.scheduled_at).toLocaleString():''}</td><td>${esc(x.job_no||'')} ${esc(x.job_title||'')}</td><td>${esc(x.interview_type||'')}</td><td>${status(x.status)}</td></tr>`).join('')}</table>`)}
 if(R16_CAND_TAB==='e-interviews'){const a=(await api('/api/assessments').catch(()=>[])).filter(x=>+x.candidate_id===+c.id);body=panel('e-Interviews / Assessments',`<table class="grid"><tr><th>Assessment</th><th>Type</th><th>Status</th><th>Score</th></tr>${a.map(x=>`<tr><td>${esc(x.title||'')}</td><td>${esc(x.assessment_type||'')}</td><td>${status(x.status)}</td><td>${x.score??''}</td></tr>`).join('')}</table>`)}
 if(R16_CAND_TAB==='Live Interviews')body=panel('Live Interviews',`<div class="r16-external-card"><b>Live video provider: NOT CONNECTED</b><p>Interview scheduling records remain available through Calendar. Recording/share behavior requires an authorized video integration.</p></div>`);
 if(R16_CAND_TAB==='LinkedIn')body=panel('LinkedIn',`<div class="r16-external-card"><b>LinkedIn integration: NOT CONNECTED</b><p>No profile data is fabricated.</p></div>`);
 if(R16_CAND_TAB==='Zoom Meetings')body=panel('Zoom Meetings',`<div class="r16-external-card"><b>Zoom integration: NOT CONNECTED</b><p>Upcoming/previous meeting and recording actions appear only after a real Zoom connector is configured.</p></div>`);
 $('#r16CandBody').innerHTML=body;
 if(R16_CAND_TAB==='DivaMatch')await r16LoadMatches(c);
}
async function r16LoadMatches(c){const d=await api(`/api/candidates/${c.id}/matches`);window.R16_MATCHES=d.results||[];$('#r16MatchBody').innerHTML=panel('DivaMatch — Job Matches',`<table class="grid"><tr><th>Match</th><th>Job</th><th>Client</th><th>Location</th><th>Start</th><th></th></tr>${window.R16_MATCHES.map(j=>`<tr><td class="score">${j.relevance}%</td><td><a class="link" onclick="go('job/${j.id}')">${esc(j.job_no)} · ${esc(j.title)}</a></td><td>${esc(j.company_name||'')}</td><td>${esc([j.city,j.state].filter(Boolean).join(', '))}</td><td>${fmtDate(j.start_date)}</td><td><button class="btn small" onclick="markInterested(${j.id},${c.id})">Interested</button></td></tr>`).join('')}</table>`)}
function r16CheckJobScore(cid){const q=$('#r16CheckJob').value.trim().toLowerCase(),j=(window.R16_MATCHES||[]).find(x=>String(x.job_no||'').toLowerCase()===q||String(x.id)===q);toast(j?`Match score: ${j.relevance}%`:'Job not found in current match set',j?'ok':'err')}

/* ---------------- Job list ---------------- */
pageJobs = async function(){
 const rows=await api('/api/jobs?include_archived=1');
 $('#content').innerHTML=`<div class="page">${head('My Jobs','Job Management › My Jobs','<button class="btn primary" onclick="openJobForm()">+ New Job</button>')}
 ${panel('Job List',`<div class="r16-job-filter"><label>Status <select id="r16JobStatus" onchange="r16FilterJobRows(this.value)"><option value="">All</option>${['Open','On Hold','Filled','Cancelled','Closed','Expired','Ignored'].map(x=>`<option>${x}</option>`).join('')}</select></label><span>Display ${rows.length} jobs</span></div>
 <div class="tablewrap"><table class="grid" id="r16JobGrid"><tr><th>Issued</th><th>Title</th><th>Company</th><th>H.Manager</th><th>Location</th><th>Status</th><th>Job #</th><th>Harvest</th><th>Max Bill</th><th>Start</th><th>Users</th></tr>${rows.map(j=>`<tr data-status="${esc(j.status||'')}"><td>${fmtDate(j.created_at)}</td><td><a class="link" onclick="go('job/${j.id}')">${esc(j.title||'')}</a></td><td>${esc(j.company_name||'')}</td><td>${esc(j.contact_name||'')}</td><td>${esc([j.city,j.state].filter(Boolean).join(', '))}</td><td>${status(j.status)}</td><td>${esc(j.job_no||'')}</td><td>${esc(j.harvest_status||'Not configured')}</td><td>${money(j.bill_max)}</td><td>${fmtDate(j.start_date)}</td><td>${esc(j.recruiter_name||'')}</td></tr>`).join('')}</table></div>`)}</div>`;
};
function r16FilterJobRows(v){$$('#r16JobGrid tr[data-status]').forEach(tr=>tr.style.display=!v||tr.dataset.status===v?'':'none')}

/* ---------------- Engagement pages ---------------- */
async function pageR16CompanyCalendar(){
 const ints=await api('/api/interviews');
 $('#content').innerHTML=`<div class="page">${head('Company Calendars','Engagement › Company Calendars')}${panel('Company Interview Calendar',`<table class="grid"><tr><th>Date</th><th>Company</th><th>Candidate</th><th>Job</th><th>Status</th></tr>${ints.map(x=>`<tr><td>${x.scheduled_at?new Date(x.scheduled_at).toLocaleString():''}</td><td>${esc(x.company_name||'')}</td><td>${esc((x.first_name||'')+' '+(x.last_name||''))}</td><td>${esc(x.job_no||'')} ${esc(x.job_title||'')}</td><td>${status(x.status)}</td></tr>`).join('')}</table>`)}</div>`;
}
async function pageR16JobCalendar(){
 const ints=await api('/api/interviews');
 $('#content').innerHTML=`<div class="page">${head('Job Calendars','Engagement › Job Calendars')}${panel('Job Interview Calendar',`<table class="grid"><tr><th>Date</th><th>Job</th><th>Candidate</th><th>Interviewer</th><th>Status</th></tr>${ints.map(x=>`<tr><td>${x.scheduled_at?new Date(x.scheduled_at).toLocaleString():''}</td><td>${esc(x.job_no||'')} ${esc(x.job_title||'')}</td><td>${esc((x.first_name||'')+' '+(x.last_name||''))}</td><td>${esc(x.interviewer||'')}</td><td>${status(x.status)}</td></tr>`).join('')}</table>`)}</div>`;
}
async function pageR16EInterview(){await pageAssessments()}
async function pageR16LiveInterview(){$('#content').innerHTML=`<div class="page">${head('Live Interview','Engagement › Live Interview')}${panel('Live Interview Provider','<div class="r16-external-card"><b>NOT CONNECTED</b><p>Connect an authorized live-video provider to create meetings, recordings and shareable interview packages.</p></div>')}</div>`}
async function pageR16DivaBuzz(){
 const rows=await api('/api/communications');
 $('#content').innerHTML=`<div class="page">${head('DivaBuzz-style Communication Hub','Engagement › Messaging')}${panel('Conversation Activity',`<table class="grid"><tr><th>Date</th><th>Entity</th><th>Channel</th><th>Direction</th><th>Subject</th><th>Status</th></tr>${rows.map(x=>`<tr><td>${x.created_at?new Date(x.created_at).toLocaleString():''}</td><td>${esc(x.entity_type)} #${esc(x.entity_id)}</td><td>${esc(x.channel)}</td><td>${esc(x.direction)}</td><td>${esc(x.subject||'')}</td><td>${status(x.status)}</td></tr>`).join('')}</table><p class="muted">Production SMS/VOIP delivery remains NOT CONNECTED until a real provider is authorized.</p>`)}</div>`;
}

/* Extend current route without replacing R13/R14 behavior for established routes. */
const R16_PREV_ROUTE=route;
route = async function(r){
 const base=String(r||'').split('/')[0];
 const custom={
  jobs:pageJobs,
  employees:pageAssignments,
  companyCalendarR16:pageR16CompanyCalendar,
  jobCalendarR16:pageR16JobCalendar,
  eInterviewR16:pageR16EInterview,
  liveInterviewR16:pageR16LiveInterview,
  divaBuzzR16:pageR16DivaBuzz
 }[base];
 if(custom){
   CURRENT=r;$$('.navitem').forEach(n=>n.classList.toggle('active',n.dataset.route===r));
   const c=$('#content');if(c)c.innerHTML='<div class="page"><div class="panel"><div class="panel-body">Loading…</div></div></div>';
   try{return await custom()}catch(e){if(c)c.innerHTML=`<div class="page"><div class="panel"><div class="panel-body"><b>Unable to load page.</b><br>${esc(e.message)}</div></div></div>`;return}
 }
 return R16_PREV_ROUTE(r);
};

window.R16_PARITY_MARKERS={
 logo_asset:true,app_menu_four_groups:true,new_candidate_four_methods:true,talent_eight_tabs:true,
 profession_add_remove:true,skill_and_or_not:true,separate_results_workspace:true,
 result_exclude:true,result_qualify:true,result_expand:true,result_hotlist:true,result_preview:true,
 result_relevancy:true,result_bulk:true,result_email_merge:true,candidate_split_profile:true,
 candidate_extended_tabs:true,divamatch_check_score:true,global_multi_entity_search:true,
 job_list_extended_columns:true,company_calendar:true,job_calendar:true,e_interview:true,
 live_interview_truthful_gate:true,divabuzz_truthful_gate:true
};
