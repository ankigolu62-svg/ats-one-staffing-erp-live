/* ==========================================================================
   ATS-ONE R13 DIRECT PARITY LAYER
   PowerShell-authored deterministic UI wiring. No external AI runtime.
   ========================================================================== */
(function(){
'use strict';

const R13_VERSION='R13_DIRECT_PARITY_1';
const R13_STATE={page:1,size:25,sort:'',dir:'asc'};

function r13Text(v){return String(v??'').toLowerCase()}
function r13Contains(v,q){return !q || r13Text(v).includes(r13Text(q))}
function r13Num(v){const n=Number(v);return Number.isFinite(n)?n:0}
function r13Date(v){return v?String(v).slice(0,10):''}
function r13Val(id){return document.getElementById(id)?.value??''}
function r13Checked(id){return !!document.getElementById(id)?.checked}
function r13SetHtml(html){document.getElementById('content').innerHTML=html}
function r13Rows(rows,fn){return (rows||[]).map(fn).join('')}
function r13Opt(rows,val,label,selected){
  return (rows||[]).map(x=>{
    const v=typeof val==='function'?val(x):x[val];
    const l=typeof label==='function'?label(x):x[label];
    return `<option value="${esc(v)}" ${String(v)===String(selected)?'selected':''}>${esc(l)}</option>`
  }).join('')
}
function r13Pager(total,page,size,rerun){
  const pages=Math.max(1,Math.ceil(total/size));
  const safe=Math.min(Math.max(1,page),pages);
  return `<div class="r13-pager"><span class="r13-count">${total} result(s) · page ${safe}/${pages}</span>
  <div class="buttons"><button class="btn small" ${safe<=1?'disabled':''} onclick="R13_STATE.page=${safe-1};${rerun}">Previous</button>
  <button class="btn small" ${safe>=pages?'disabled':''} onclick="R13_STATE.page=${safe+1};${rerun}">Next</button></div></div>`
}
function r13Page(rows){
  const start=(R13_STATE.page-1)*R13_STATE.size;
  return rows.slice(start,start+R13_STATE.size)
}
function r13Toolbar(fields,action,clearAction){
  return `<div class="r13-toolbar">${fields.join('')}
    <button class="btn primary" onclick="R13_STATE.page=1;${action}">Search</button>
    <button class="btn" onclick="${clearAction}">Clear</button>
  </div>`
}
function r13Field(id,label,placeholder='',type='text'){
  return `<div class="field compact"><label>${esc(label)}</label><input id="${id}" type="${type}" placeholder="${esc(placeholder)}"></div>`
}
function r13Select(id,label,options){
  return `<div class="field compact"><label>${esc(label)}</label><select id="${id}">${options}</select></div>`
}
function r13StatusOptions(){
  return '<option value="">All</option>'+['Open','On Hold','Filled','Cancelled','Closed','Expired','Ignored','Archived'].map(x=>`<option>${x}</option>`).join('')
}

/* ---------- truthful launcher routes ---------- */
pageMenu = function(){
 const modules=[
  ['Talent Management',[
    ['Talent Search','talent'],['Boolean Search','boolean'],['Search Candidates','candidates'],
    ['Search Employees','employees'],['Candidate Hotlists','hotlists'],['Candidate Notes','candidateNotes'],
    ['Search Attributes','candidateAttributes'],['Import Candidates','candidateImport']]],
  ['Job Management',[
    ['My Jobs','jobs'],['My Jobs as Primary','primaryJobs'],['Search Jobs','jobSearch'],
    ['New Job','newJob'],['Jobs Dashboard','dashboard'],['Submittals','submissions'],['Interviews','interviews']]],
  ['CRM',[
    ['Companies','companies'],['Contacts','contacts'],['Contact Hotlists','contactHotlists'],
    ['Leads / Opportunities','companies']]],
  ['Reporting / Admin',[
    ['Reports','reports'],['BI Shared With Me','biShared'],['Audit Trail','audit'],['Configuration','admin']]],
  ['Workforce / Back Office',[
    ['Onboarding','onboarding'],['Assignments','assignments'],['Calendar','calendar'],
    ['Timesheets','timesheets'],['Expenses','expenses'],['Finance','finance']]],
  ['VMS / Engagement',[
    ['VMS / MSP','vms'],['Suppliers','suppliers'],['Communication','communications'],['Assessments','assessments']]]
 ];
 r13SetHtml(`<div class="page">${head('ATS One — Functional Workspace','Home › App Menu')}
 <div class="launcher">${modules.map(m=>`<div class="module-card blue"><h3>${esc(m[0])}</h3><div class="module-links">${
   m[1].map(x=>`<div class="module-link" onclick="${x[1]==='newJob'?'openJobForm()':`go('${x[1]}')`}"><span class="module-name">${esc(x[0])}</span></div>`).join('')
 }</div></div>`).join('')}</div></div>`);
};

/* ---------- multi-entity global search ---------- */
globalSearch = async function(){
 const q=(document.getElementById('globalQ')?.value||'').trim();
 if(!q)return;
 try{
  const [cs,js,cos,cts,subs]=await Promise.all([
    api('/api/candidates'),api('/api/jobs'),api('/api/companies'),api('/api/contacts'),api('/api/submissions')
  ]);
  const c=cs.filter(x=>r13Contains([x.first_name,x.last_name,x.email,x.phone,x.current_title,x.profession,x.city,x.state].join(' '),q)).slice(0,30);
  const j=js.filter(x=>r13Contains([x.job_no,x.title,x.company_name,x.city,x.state,x.status].join(' '),q)).slice(0,30);
  const co=cos.filter(x=>r13Contains([x.name,x.industry,x.city,x.state,x.website].join(' '),q)).slice(0,30);
  const ct=cts.filter(x=>r13Contains([x.first_name,x.last_name,x.company_name,x.email,x.phone,x.title].join(' '),q)).slice(0,30);
  const s=subs.filter(x=>r13Contains([x.first_name,x.last_name,x.job_no,x.job_title,x.company_name,x.status].join(' '),q)).slice(0,30);
  modal('Global Search',
   `<div class="r13-section">Candidates (${c.length})</div>${c.map(x=>`<div><a class="link" onclick="closeModal();go('candidate/${x.id}')">${esc(x.first_name+' '+x.last_name)}</a> · ${esc(x.current_title||'')}</div>`).join('')||'<div class="r13-empty">None</div>'}
    <div class="r13-section">Jobs (${j.length})</div>${j.map(x=>`<div><a class="link" onclick="closeModal();go('job/${x.id}')">${esc(x.job_no+' · '+x.title)}</a> · ${esc(x.company_name||'')}</div>`).join('')||'<div class="r13-empty">None</div>'}
    <div class="r13-section">Companies (${co.length})</div>${co.map(x=>`<div><a class="link" onclick="closeModal();go('company/${x.id}')">${esc(x.name)}</a></div>`).join('')||'<div class="r13-empty">None</div>'}
    <div class="r13-section">Contacts (${ct.length})</div>${ct.map(x=>`<div><a class="link" onclick="closeModal();go('contact/${x.id}')">${esc(x.first_name+' '+x.last_name)}</a> · ${esc(x.company_name||'')}</div>`).join('')||'<div class="r13-empty">None</div>'}
    <div class="r13-section">Submittals (${s.length})</div>${s.map(x=>`<div>${esc(x.first_name+' '+x.last_name)} → ${esc(x.job_no+' '+x.job_title)} · ${status(x.status)}</div>`).join('')||'<div class="r13-empty">None</div>'}`,
   '<button class="btn" onclick="closeModal()">Close</button>',true);
 }catch(e){toast(e.message,'err')}
};

/* ---------- candidate list search/filter/paging ---------- */
async function pageCandidatesR13(){
 const rows=await api('/api/candidates?include_archived=1');
 window.R13_CANDIDATES=rows;
 renderCandidatesR13();
}
function renderCandidatesR13(){
 let rows=[...(window.R13_CANDIDATES||[])];
 const q=r13Val('r13-c-q'),st=r13Val('r13-c-status'),src=r13Val('r13-c-source'),state=r13Val('r13-c-state');
 if(q)rows=rows.filter(x=>r13Contains([x.first_name,x.last_name,x.email,x.phone,x.current_title,x.profession,x.specialty,x.city,x.state].join(' '),q));
 if(st)rows=rows.filter(x=>r13Text(x.status)===r13Text(st));
 if(src)rows=rows.filter(x=>r13Contains(x.source,src));
 if(state)rows=rows.filter(x=>r13Contains(x.state,state));
 rows.sort((a,b)=>String(a.last_name||'').localeCompare(String(b.last_name||'')));
 const shown=r13Page(rows);
 const tools=r13Toolbar([
   r13Field('r13-c-q','Name / title / skill','Search'),
   r13Field('r13-c-state','State / Province','State'),
   r13Field('r13-c-source','Source','Source'),
   r13Select('r13-c-status','Status','<option value="">All</option><option>Active</option><option>Archived</option>')
 ],'renderCandidatesR13()',"['r13-c-q','r13-c-state','r13-c-source','r13-c-status'].forEach(x=>document.getElementById(x).value='');R13_STATE.page=1;renderCandidatesR13()");
 r13SetHtml(`<div class="page">${head('Candidates','Talent Management › Candidate Database','<button class="btn primary" onclick="openCandidateForm()">+ New Candidate</button>')}
 ${panel('Search / Filter',tools)}
 ${panel('Candidate Database',`<div class="tablewrap"><table class="grid"><tr><th>Name</th><th>Title</th><th>Profession</th><th>Location</th><th>Availability</th><th>Source</th><th>Status</th></tr>${
 shown.map(c=>`<tr><td><a class="link" onclick="go('candidate/${c.id}')">${esc(c.first_name+' '+c.last_name)}</a><br><small>${esc(c.email||'')}</small></td><td>${esc(c.current_title||'')}</td><td>${esc(c.profession||'')}<br><small>${esc(c.specialty||'')}</small></td><td>${esc([c.city,c.state,c.country].filter(Boolean).join(', '))}</td><td>${fmtDate(c.availability_date)}</td><td>${esc(c.source||'')}</td><td>${status(c.status)}</td></tr>`).join('')
 }</table></div>${r13Pager(rows.length,R13_STATE.page,R13_STATE.size,'renderCandidatesR13()')}`)}</div>`);
}

/* ---------- employee search ---------- */
async function pageEmployeesR13(){
 const [asg,cs]=await Promise.all([api('/api/assignments'),api('/api/candidates')]);
 const map=Object.fromEntries(cs.map(x=>[x.id,x]));
 const q='';
 r13SetHtml(`<div class="page">${head('Search Employees','Talent Management › Employees')}
 ${panel('Employees / Workers',`<table class="grid"><tr><th>Employee</th><th>Job</th><th>Client</th><th>Assignment</th><th>Dates</th><th>Worksite</th></tr>${
 asg.map(a=>`<tr><td><a class="link" onclick="go('candidate/${a.candidate_id}')">${esc((a.first_name||'')+' '+(a.last_name||''))}</a></td><td>${esc(a.job_no||'')} · ${esc(a.job_title||'')}</td><td>${esc(a.company_name||'')}</td><td>${status(a.status)}</td><td>${fmtDate(a.start_date)} — ${fmtDate(a.end_date)}</td><td>${esc(a.worksite||'')}</td></tr>`).join('')
 }</table>`)}</div>`);
}

/* ---------- candidate notes search ---------- */
async function pageCandidateNotesR13(){
 const cs=await api('/api/candidates');
 const bundles=await Promise.all(cs.slice(0,150).map(x=>api('/api/candidates/'+x.id).catch(()=>null)));
 const notes=[];
 bundles.filter(Boolean).forEach(c=>(c.notes||[]).forEach(n=>notes.push({...n,candidate_id:c.id,candidate_name:c.first_name+' '+c.last_name})));
 notes.sort((a,b)=>String(b.created_at).localeCompare(String(a.created_at)));
 r13SetHtml(`<div class="page">${head('Candidate Notes','Talent Management › Candidate Notes')}
 ${panel('Notes Journal',`<table class="grid"><tr><th>Date</th><th>Candidate</th><th>User</th><th>Type</th><th>Note</th></tr>${
 notes.map(n=>`<tr><td>${fmtDate(n.created_at)}</td><td><a class="link" onclick="go('candidate/${n.candidate_id}')">${esc(n.candidate_name)}</a></td><td>${esc(n.user_name||'')}</td><td>${esc(n.note_type||'General')}</td><td>${esc(n.note||'')}</td></tr>`).join('')
 }</table>`)}</div>`);
}

/* ---------- attribute search ---------- */
async function pageCandidateAttributesR13(){
 const cs=await api('/api/candidates');
 const bundles=await Promise.all(cs.slice(0,150).map(x=>api('/api/candidates/'+x.id).catch(()=>null)));
 const attrs=[];
 bundles.filter(Boolean).forEach(c=>(c.attributes||[]).forEach(a=>attrs.push({...a,candidate_id:c.id,candidate_name:c.first_name+' '+c.last_name})));
 r13SetHtml(`<div class="page">${head('Search Attributes','Talent Management › Attributes')}
 ${panel('Candidate Attributes',`<table class="grid"><tr><th>Candidate</th><th>Attribute</th><th>Value</th></tr>${
 attrs.map(a=>`<tr><td><a class="link" onclick="go('candidate/${a.candidate_id}')">${esc(a.candidate_name)}</a></td><td>${esc(a.attribute||'')}</td><td>${esc(a.value||'')}</td></tr>`).join('')
 }</table>`)}</div>`);
}

/* ---------- CSV candidate import ---------- */
function pageCandidateImportR13(){
 r13SetHtml(`<div class="page">${head('Import Candidates','Talent Management › Import')}
 ${panel('CSV Import',`<div class="r13-truth">Expected columns: first_name,last_name,email,phone,current_title,profession,specialty,city,state,country,zip,source</div>
 <div class="field"><label>CSV File</label><input id="r13-import-file" type="file" accept=".csv,text/csv"></div>
 <div class="field"><label>Or paste CSV</label><textarea id="r13-import-text" rows="12"></textarea></div>
 <button class="btn primary" onclick="r13ImportCandidates()">Validate & Import</button>
 <div id="r13-import-result"></div>`)}</div>`);
}
function r13ParseCsv(text){
 const lines=String(text||'').replace(/\r/g,'').split('\n').filter(x=>x.trim());
 if(lines.length<2)return [];
 const parse=line=>{const out=[];let cur='',q=false;for(let i=0;i<line.length;i++){const ch=line[i];if(ch==='"'){if(q&&line[i+1]==='"'){cur+='"';i++}else q=!q}else if(ch===','&&!q){out.push(cur);cur=''}else cur+=ch}out.push(cur);return out};
 const h=parse(lines[0]).map(x=>x.trim());
 return lines.slice(1).map(line=>Object.fromEntries(parse(line).map((v,i)=>[h[i],v.trim()])));
}
async function r13ImportCandidates(){
 const f=document.getElementById('r13-import-file')?.files?.[0];
 let text=document.getElementById('r13-import-text')?.value||'';
 if(f)text=await f.text();
 const rows=r13ParseCsv(text);
 if(!rows.length)return toast('No CSV rows found','err');
 const required=rows.filter(x=>!x.first_name||!x.last_name);
 if(required.length)return toast(`${required.length} row(s) missing first_name/last_name`,'err');
 let ok=0,fail=0,errors=[];
 for(const row of rows){
  try{await api('/api/candidates',{method:'POST',body:row});ok++}
  catch(e){fail++;errors.push(e.message)}
 }
 document.getElementById('r13-import-result').innerHTML=`<div class="r13-truth">Imported ${ok}; failed ${fail}</div><div>${errors.map(esc).join('<br>')}</div>`;
}

/* ---------- job search/filter/paging ---------- */
async function pageJobSearchR13(primaryOnly=false){
 const rows=await api('/api/jobs?include_archived=1');
 window.R13_JOBS=rows;
 window.R13_PRIMARY_ONLY=!!primaryOnly;
 renderJobsR13();
}
function renderJobsR13(){
 let rows=[...(window.R13_JOBS||[])];
 const q=r13Val('r13-j-q'),company=r13Val('r13-j-company'),statev=r13Val('r13-j-state'),
       city=r13Val('r13-j-city'),st=r13Val('r13-j-status'),type=r13Val('r13-j-type'),
       issueFrom=r13Val('r13-j-issue-from'),issueTo=r13Val('r13-j-issue-to'),
       startFrom=r13Val('r13-j-start-from'),startTo=r13Val('r13-j-start-to');
 if(q)rows=rows.filter(x=>r13Contains([x.job_no,x.title,x.client_reference,x.company_name,x.contact_name].join(' '),q));
 if(company)rows=rows.filter(x=>r13Contains(x.company_name,company));
 if(statev)rows=rows.filter(x=>r13Contains(x.state,statev));
 if(city)rows=rows.filter(x=>r13Contains(x.city,city));
 if(st)rows=rows.filter(x=>r13Text(x.status)===r13Text(st));
 if(type)rows=rows.filter(x=>r13Text(x.position_type)===r13Text(type));
 if(issueFrom)rows=rows.filter(x=>r13Date(x.created_at)>=issueFrom);
 if(issueTo)rows=rows.filter(x=>r13Date(x.created_at)<=issueTo);
 if(startFrom)rows=rows.filter(x=>r13Date(x.start_date)>=startFrom);
 if(startTo)rows=rows.filter(x=>r13Date(x.start_date)<=startTo);
 if(window.R13_PRIMARY_ONLY && ME)rows=rows.filter(x=>Number(x.primary_recruiter_id)===Number(ME.id)||r13Text(x.recruiter_name)===r13Text(ME.name));
 rows.sort((a,b)=>String(b.updated_at||b.created_at||'').localeCompare(String(a.updated_at||a.created_at||'')));
 const shown=r13Page(rows);
 const tools=r13Toolbar([
  r13Field('r13-j-q','Job # / title / reference','Quick search'),
  r13Field('r13-j-company','Company','Company'),
  r13Field('r13-j-state','State / Province','State'),
  r13Field('r13-j-city','City','City'),
  r13Select('r13-j-status','Status',r13StatusOptions()),
  r13Select('r13-j-type','Job Type','<option value="">All</option><option>Contract</option><option>Contract-to-Hire</option><option>Direct Hire</option><option>Per Diem</option>'),
  r13Field('r13-j-issue-from','Issue From','', 'date'),
  r13Field('r13-j-issue-to','Issue To','', 'date'),
  r13Field('r13-j-start-from','Start From','', 'date'),
  r13Field('r13-j-start-to','Start To','', 'date')
 ],'renderJobsR13()',"document.querySelectorAll('.r13-toolbar input,.r13-toolbar select').forEach(x=>x.value='');R13_STATE.page=1;renderJobsR13()");
 r13SetHtml(`<div class="page">${head(window.R13_PRIMARY_ONLY?'My Jobs as Primary':'Job Search','Job Management › Search Jobs','<button class="btn primary" onclick="openJobForm()">+ New Job</button>')}
 ${panel('Search / Filters',tools)}
 ${panel('Job Results',`<table class="grid"><tr><th>Job #</th><th>Title</th><th>Client</th><th>Location</th><th>Type</th><th>Priority</th><th>Status</th><th>Openings</th><th>Primary</th></tr>${
 shown.map(j=>`<tr><td><a class="link" onclick="go('job/${j.id}')">${esc(j.job_no)}</a></td><td>${esc(j.title)}</td><td>${esc(j.company_name||'')}</td><td>${esc([j.city,j.state,j.country].filter(Boolean).join(', '))}</td><td>${esc(j.position_type||'')}</td><td>${status(j.priority)}</td><td>${status(j.status)}</td><td>${esc(j.filled)}/${esc(j.openings)}</td><td>${esc(j.recruiter_name||'')}</td></tr>`).join('')
 }</table>${r13Pager(rows.length,R13_STATE.page,R13_STATE.size,'renderJobsR13()')}`)}</div>`);
}

/* deeper new job editor, using fields current backend persists */
openJobForm = function(){
 const countries=['USA','India','Canada','United Kingdom','Australia','Germany','France','Singapore','UAE','Saudi Arabia'];
 modal('New Job Requisition — Full Editor',
 `<form id="jobForm"><div class="r13-section">Core</div><div class="r13-modal-grid">
 ${formFields([
  {name:'title',label:'Job Title',required:true},
  {name:'company_id',label:'Company',type:'select',options:REF.companies.map(x=>({value:x.id,label:x.name}))},
  {name:'contact_id',label:'Hiring Manager',type:'select',options:[{value:'',label:'—'},...REF.contacts.map(x=>({value:x.id,label:x.name}))]},
  {name:'status',label:'Status',type:'select',options:['Open','On Hold','Filled','Cancelled','Closed','Expired','Ignored']},
  {name:'priority',label:'Priority',type:'select',options:['Normal','High','Urgent']},
  {name:'position_type',label:'Job Type',type:'select',options:['Contract','Contract-to-Hire','Direct Hire','Per Diem']},
  {name:'openings',label:'Openings',type:'number',value:1},
  {name:'filled',label:'Filled',type:'number',value:0},
  {name:'work_mode',label:'Work Mode',type:'select',options:['Onsite','Hybrid','Remote']},
  {name:'country',label:'Country',type:'select',options:countries},
  {name:'state',label:'State / Province'},
  {name:'city',label:'City'},
  {name:'zip',label:'Postal Code'},
  {name:'start_date',label:'Start Date',type:'date'},
  {name:'end_date',label:'End Date',type:'date'}
 ])}
 </div><div class="r13-section">Rates / Search Criteria</div><div class="r13-modal-grid">
 ${formFields([
  {name:'rate_type',label:'Rate Unit',type:'select',options:['hour','day','week','month','year']},
  {name:'pay_min',label:'Pay Min',type:'number'},{name:'pay_max',label:'Pay Max',type:'number'},
  {name:'bill_min',label:'Bill Min',type:'number'},{name:'bill_max',label:'Bill Max',type:'number'},
  {name:'profession',label:'Profession'},{name:'specialty',label:'Specialty'},
  {name:'required_skills',label:'Required Skills (Skill:Years:Recent | ...)',type:'textarea',span:true},
  {name:'required_qualifications',label:'Qualifications',type:'textarea',span:true},
  {name:'required_licenses',label:'Licenses',type:'textarea',span:true},
  {name:'required_certifications',label:'Certifications',type:'textarea',span:true},
  {name:'submission_guidelines_override',label:'Submittal Instructions',type:'textarea',span:true},
  {name:'description',label:'Description',type:'textarea',span:true}
 ])}</div></form>`,
 `<button class="btn" onclick="closeModal()">Cancel</button><button class="btn primary" onclick="submitJob()">Create Job</button>`,true);
};

/* ---------- company + contact detail ---------- */
async function pageCompanyR13(id){
 const [companies,contacts,jobs,leads,opps]=await Promise.all([api('/api/companies'),api('/api/contacts'),api('/api/jobs'),api('/api/leads'),api('/api/opportunities')]);
 const c=companies.find(x=>Number(x.id)===Number(id));if(!c)throw new Error('Company not found');
 const ct=contacts.filter(x=>Number(x.company_id)===Number(id)),j=jobs.filter(x=>Number(x.company_id)===Number(id)),l=leads.filter(x=>Number(x.company_id)===Number(id)),o=opps.filter(x=>Number(x.company_id)===Number(id));
 r13SetHtml(`<div class="page">${head(c.name,'CRM › Company Detail','<button class="btn" onclick="go(\'companies\')">Back</button>')}
 <div class="r13-detail-grid">
 ${panel('Company Profile',`<div class="r13-kv"><b>Type</b>${esc(c.company_type||'')}</div><div class="r13-kv"><b>Industry</b>${esc(c.industry||'')}</div><div class="r13-kv"><b>Location</b>${esc([c.city,c.state,c.country].filter(Boolean).join(', '))}</div><div class="r13-kv"><b>Website</b>${esc(c.website||'')}</div><div class="r13-kv"><b>Billing Terms</b>${esc(c.billing_terms||'')}</div><div class="r13-kv"><b>Status</b>${status(c.status)}</div>`)}
 ${panel('Submission / Account Rules',`<div class="r13-kv"><b>Submission Guidelines</b>${esc(c.submission_guidelines||'')}</div><div class="r13-kv"><b>Discount / Rate Rule</b>${esc(c.discount_rule||'')}</div><div class="r13-kv"><b>Notes</b>${esc(c.notes||'')}</div>`)}
 </div>
 ${panel(`Contacts (${ct.length})`,`<table class="grid"><tr><th>Name</th><th>Role</th><th>Email</th><th>Phone</th></tr>${ct.map(x=>`<tr><td><a class="link" onclick="go('contact/${x.id}')">${esc(x.first_name+' '+x.last_name)}</a></td><td>${esc(x.role_type||'')}</td><td>${esc(x.email||'')}</td><td>${esc(x.phone||'')}</td></tr>`).join('')}</table>`)}
 ${panel(`Jobs (${j.length})`,`<table class="grid"><tr><th>Job</th><th>Title</th><th>Status</th></tr>${j.map(x=>`<tr><td><a class="link" onclick="go('job/${x.id}')">${esc(x.job_no)}</a></td><td>${esc(x.title)}</td><td>${status(x.status)}</td></tr>`).join('')}</table>`)}
 <div class="two-col">${panel(`Leads (${l.length})`,l.map(x=>`<div class="kv"><b>${esc(x.title)}</b><span>${status(x.status)}</span></div>`).join('')||'None')}${panel(`Opportunities (${o.length})`,o.map(x=>`<div class="kv"><b>${esc(x.name)}</b><span>${status(x.stage)} · ${money(x.value)}</span></div>`).join('')||'None')}</div>
 </div>`);
}
async function pageContactR13(id){
 const rows=await api('/api/contacts');const c=rows.find(x=>Number(x.id)===Number(id));if(!c)throw new Error('Contact not found');
 r13SetHtml(`<div class="page">${head(c.first_name+' '+c.last_name,'CRM › Contact Detail','<button class="btn" onclick="go(\'contacts\')">Back</button>')}
 <div class="r13-detail-grid">${panel('Contact',`<div class="r13-kv"><b>Company</b>${esc(c.company_name||'')}</div><div class="r13-kv"><b>Title</b>${esc(c.title||'')}</div><div class="r13-kv"><b>Role</b>${esc(c.role_type||'')}</div><div class="r13-kv"><b>Email</b>${esc(c.email||'')}</div><div class="r13-kv"><b>Phone</b>${esc(c.phone||'')}</div><div class="r13-kv"><b>Status</b>${status(c.status)}</div>`)}
 ${panel('Notes',`<div>${esc(c.notes||'No notes')}</div>`)}</div></div>`);
}

/* clickable company/contact rows */
const R13_ORIG_COMPANIES=pageCompanies;
pageCompanies=async function(){
 await R13_ORIG_COMPANIES();
 document.querySelectorAll('.grid tr').forEach(tr=>{
  const first=tr.querySelector('td:first-child b');
  if(!first)return;
  const name=first.textContent.trim();
  const row=(REF?.companies||[]).find(x=>x.name===name);
  if(row){first.classList.add('r13-link');first.onclick=()=>go('company/'+row.id)}
 });
};
const R13_ORIG_CONTACTS=pageContacts;
pageContacts=async function(){
 await R13_ORIG_CONTACTS();
 const rows=await api('/api/contacts');
 document.querySelectorAll('.grid tr').forEach(tr=>{
  const b=tr.querySelector('td:first-child b');if(!b)return;
  const name=b.textContent.trim();
  const row=rows.find(x=>(x.first_name+' '+x.last_name).trim()===name);
  if(row){b.classList.add('r13-link');b.onclick=()=>go('contact/'+row.id)}
 });
};

/* ---------- contact hotlists (searchable saved contact workspace using durable browser view names) ---------- */
async function pageContactHotlistsR13(){
 const contacts=await api('/api/contacts');
 const saved=JSON.parse(localStorage.getItem('atsone_contact_views')||'[]');
 r13SetHtml(`<div class="page">${head('Contact Hotlists','CRM › Contact Hotlists','<button class="btn primary" onclick="r13SaveContactView()">+ Save View</button>')}
 ${panel('Saved Contact Views',saved.length?saved.map((x,i)=>`<div class="kv"><b>${esc(x.name)}</b><span>${esc(x.query||'All contacts')} <button class="btn small" onclick="r13OpenContactView(${i})">Open</button> <button class="btn small danger" onclick="r13DeleteContactView(${i})">Delete</button></span></div>`).join(''):'<div class="r13-empty">No saved views yet</div>')}
 ${panel('All Contacts',`<table class="grid"><tr><th>Name</th><th>Company</th><th>Title</th><th>Email</th><th>Phone</th></tr>${contacts.map(x=>`<tr><td><a class="link" onclick="go('contact/${x.id}')">${esc(x.first_name+' '+x.last_name)}</a></td><td>${esc(x.company_name||'')}</td><td>${esc(x.title||'')}</td><td>${esc(x.email||'')}</td><td>${esc(x.phone||'')}</td></tr>`).join('')}</table>`)}</div>`);
}
function r13SaveContactView(){
 const name=prompt('View name');if(!name)return;const query=prompt('Filter text (name/company/title/email)','')??'';
 const saved=JSON.parse(localStorage.getItem('atsone_contact_views')||'[]');saved.push({name,query});localStorage.setItem('atsone_contact_views',JSON.stringify(saved));pageContactHotlistsR13();
}
async function r13OpenContactView(i){
 const saved=JSON.parse(localStorage.getItem('atsone_contact_views')||'[]');const v=saved[i];if(!v)return;
 const contacts=(await api('/api/contacts')).filter(x=>r13Contains([x.first_name,x.last_name,x.company_name,x.title,x.email].join(' '),v.query));
 modal(v.name,`<table class="grid"><tr><th>Name</th><th>Company</th><th>Title</th></tr>${contacts.map(x=>`<tr><td><a class="link" onclick="closeModal();go('contact/${x.id}')">${esc(x.first_name+' '+x.last_name)}</a></td><td>${esc(x.company_name||'')}</td><td>${esc(x.title||'')}</td></tr>`).join('')}</table>`,'<button class="btn" onclick="closeModal()">Close</button>',true);
}
function r13DeleteContactView(i){const s=JSON.parse(localStorage.getItem('atsone_contact_views')||'[]');s.splice(i,1);localStorage.setItem('atsone_contact_views',JSON.stringify(s));pageContactHotlistsR13()}

/* ---------- BI shared ---------- */
async function pageBISharedR13(){
 let defs=[];try{defs=await api('/api/reports/definitions')}catch(_){}
 const shared=(defs||[]).filter(x=>x.is_shared||Number(x.owner_user_id)!==Number(ME?.id));
 r13SetHtml(`<div class="page">${head('BI Shared With Me','Reporting › Shared BI')}
 ${panel('Shared Report Definitions',shared.length?`<table class="grid"><tr><th>Name</th><th>Report</th><th>Description</th></tr>${shared.map(x=>`<tr><td>${esc(x.name||'')}</td><td>${esc(x.report_key||'')}</td><td>${esc(x.description||'')}</td></tr>`).join('')}</table>`:'<div class="r13-empty">No shared definitions</div>')}</div>`);
}

/* ---------- calendar ---------- */
async function pageCalendarR13(){
 const rows=await api('/api/interviews');
 rows.sort((a,b)=>String(a.scheduled_at||'').localeCompare(String(b.scheduled_at||'')));
 r13SetHtml(`<div class="page">${head('Interview Calendar','Events › Calendar')}
 ${panel('Scheduled Interviews',`<table class="grid"><tr><th>Date / Time</th><th>Candidate</th><th>Job</th><th>Client</th><th>Type</th><th>Interviewer</th><th>Status</th></tr>${rows.map(x=>`<tr><td>${x.scheduled_at?new Date(x.scheduled_at).toLocaleString():''}</td><td>${esc(x.first_name+' '+x.last_name)}</td><td>${esc(x.job_no+' · '+x.job_title)}</td><td>${esc(x.company_name||'')}</td><td>${esc(x.interview_type||'')}</td><td>${esc(x.interviewer||'')}</td><td>${status(x.status)}</td></tr>`).join('')}</table>`)}</div>`);
}

/* ---------- enhanced audit filters ---------- */
const R13_ORIG_AUDIT=pageAudit;
pageAudit=async function(){
 const rows=await api('/api/audit');window.R13_AUDIT=rows;
 const users=[...new Set(rows.map(x=>x.user_name||x.email||'System'))].sort();
 const actions=[...new Set(rows.map(x=>x.action).filter(Boolean))].sort();
 const entities=[...new Set(rows.map(x=>x.entity_type).filter(Boolean))].sort();
 r13SetHtml(`<div class="page">${head('Audit Trail','Security › Audit')}
 ${panel('Filter',r13Toolbar([
  r13Field('r13-a-q','Detail / ID / IP','Search'),
  r13Select('r13-a-user','User','<option value="">All</option>'+users.map(x=>`<option>${esc(x)}</option>`).join('')),
  r13Select('r13-a-action','Action','<option value="">All</option>'+actions.map(x=>`<option>${esc(x)}</option>`).join('')),
  r13Select('r13-a-entity','Entity','<option value="">All</option>'+entities.map(x=>`<option>${esc(x)}</option>`).join('')),
  r13Field('r13-a-from','From','', 'date'),r13Field('r13-a-to','To','', 'date')
 ],'r13RenderAudit()',"document.querySelectorAll('.r13-toolbar input,.r13-toolbar select').forEach(x=>x.value='');R13_STATE.page=1;r13RenderAudit()"))}
 <div id="r13-a-results"></div></div>`);r13RenderAudit();
}
function r13RenderAudit(){
 let rows=[...(window.R13_AUDIT||[])],q=r13Val('r13-a-q'),u=r13Val('r13-a-user'),a=r13Val('r13-a-action'),e=r13Val('r13-a-entity'),f=r13Val('r13-a-from'),t=r13Val('r13-a-to');
 if(q)rows=rows.filter(x=>r13Contains([x.detail,x.entity_id,x.ip].join(' '),q));
 if(u)rows=rows.filter(x=>(x.user_name||x.email||'System')===u);if(a)rows=rows.filter(x=>x.action===a);if(e)rows=rows.filter(x=>x.entity_type===e);
 if(f)rows=rows.filter(x=>r13Date(x.created_at)>=f);if(t)rows=rows.filter(x=>r13Date(x.created_at)<=t);
 const shown=r13Page(rows);
 document.getElementById('r13-a-results').innerHTML=panel('Recent Activity',`<table class="grid"><tr><th>Date</th><th>User</th><th>Action</th><th>Entity</th><th>ID</th><th>Detail</th><th>IP</th></tr>${shown.map(x=>`<tr><td>${new Date(x.created_at).toLocaleString()}</td><td>${esc(x.user_name||x.email||'System')}</td><td>${esc(x.action)}</td><td>${esc(x.entity_type)}</td><td>${esc(x.entity_id||'')}</td><td>${esc(x.detail||'')}</td><td>${esc(x.ip||'')}</td></tr>`).join('')}</table>${r13Pager(rows.length,R13_STATE.page,R13_STATE.size,'r13RenderAudit()')}`);
}

/* ---------- truthful route resolver ---------- */
route = async function(r){
 CURRENT=r;
 document.querySelectorAll('.navitem').forEach(n=>n.classList.toggle('active',n.dataset.route===r));
 const c=document.getElementById('content');if(!c)return;
 c.innerHTML='<div class="page"><div class="panel"><div class="panel-body">Loading…</div></div></div>';
 try{
  const [base,id]=r.split('/');
  const fn={
   menu:pageMenu,dashboard:pageDashboard,talent:pageTalent,boolean:pageBoolean,
   candidates:pageCandidatesR13,candidate:()=>pageCandidate(id),
   employees:pageEmployeesR13,candidateNotes:pageCandidateNotesR13,
   candidateAttributes:pageCandidateAttributesR13,candidateImport:pageCandidateImportR13,
   hotlists:pageHotlists,jobs:()=>pageJobSearchR13(false),jobSearch:()=>pageJobSearchR13(false),
   primaryJobs:()=>pageJobSearchR13(true),job:()=>pageJob(id),
   companies:pageCompanies,company:()=>pageCompanyR13(id),
   contacts:pageContacts,contact:()=>pageContactR13(id),contactHotlists:pageContactHotlistsR13,
   submissions:pageSubmissions,interviews:pageInterviews,calendar:pageCalendarR13,
   assessments:pageAssessments,onboarding:pageOnboarding,assignments:pageAssignments,
   timesheets:pageTimesheets,expenses:pageExpenses,finance:pageFinance,vms:pageVMS,
   suppliers:pageSuppliers,communications:pageCommunications,reports:pageReports,biShared:pageBISharedR13,
   admin:pageAdmin,audit:pageAudit,candidatePortal:pageCandidatePortal,clientPortal:pageClientPortal,
   workerPortal:pageWorkerPortal,supplierPortal:pageSupplierPortal,approverPortal:pageApproverPortal
  }[base];
  if(!fn)throw new Error('Unknown page: '+base);
  await fn();
  try{enhanceR8Controls(base,id)}catch(_){}
 }catch(e){
  c.innerHTML=`<div class="page"><div class="panel"><div class="panel-body"><b>Unable to load page.</b><br>${esc(e.message)}</div></div></div>`;
 }
};

Object.assign(window,{
 R13_STATE,renderCandidatesR13,r13ImportCandidates,r13OpenContactView,r13DeleteContactView,r13SaveContactView,
 renderJobsR13,r13RenderAudit
});
window.R13_VERSION=R13_VERSION;
})();