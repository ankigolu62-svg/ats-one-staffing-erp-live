const $=(s,r=document)=>r.querySelector(s), $$=(s,r=document)=>[...r.querySelectorAll(s)];
const esc=s=>String(s??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
const fmtDate=s=>s?new Date(s).toLocaleDateString():'';
const money=n=>n==null||n===''?'':new Intl.NumberFormat('en-US',{style:'currency',currency:'USD',maximumFractionDigits:2}).format(n);
const status=s=>`<span class="status ${esc(String(s||'').toLowerCase().replaceAll(' ','_'))}">${esc(s||'')}</span>`;
const tag=s=>`<span class="tag">${esc(s)}</span>`;

const R10_ICON_PATHS={
 home:'<path d="M3 11.5 12 4l9 7.5"/><path d="M5.5 10.5V20h13v-9.5"/><path d="M9.5 20v-6h5v6"/>',
 menu:'<rect x="4" y="4" width="6" height="6" rx="1"/><rect x="14" y="4" width="6" height="6" rx="1"/><rect x="4" y="14" width="6" height="6" rx="1"/><rect x="14" y="14" width="6" height="6" rx="1"/>',
 dashboard:'<path d="M4 13h6V4H4zM14 20h6V9h-6zM4 20h6v-3H4zM14 5h6V4h-6z"/>',
 talent:'<circle cx="11" cy="11" r="6"/><path d="m16 16 4 4"/><path d="M8 11h6M11 8v6"/>',
 boolean:'<path d="M5 6h5M5 12h5M5 18h5"/><path d="M15 6h4M15 12h4M15 18h4"/><path d="m12 4 2 2-2 2M12 10l2 2-2 2M12 16l2 2-2 2"/>',
 candidates:'<circle cx="12" cy="8" r="3"/><path d="M5 20c.8-4 3.2-6 7-6s6.2 2 7 6"/>',
 hotlists:'<path d="M12 21s7-4.4 7-11a4 4 0 0 0-7-2.5A4 4 0 0 0 5 10c0 6.6 7 11 7 11Z"/>',
 jobs:'<rect x="3" y="7" width="18" height="13" rx="2"/><path d="M9 7V4h6v3M3 12h18M10 12v2h4v-2"/>',
 companies:'<path d="M4 21V5h10v16M14 10h6v11M7 8h1M10 8h1M7 12h1M10 12h1M7 16h1M10 16h1"/>',
 contacts:'<circle cx="9" cy="8" r="3"/><path d="M3 20c.5-4 2.5-6 6-6s5.5 2 6 6M16 8h5M18.5 5.5v5"/>',
 submissions:'<path d="M5 12h12"/><path d="m13 8 4 4-4 4"/><path d="M4 5h8M4 19h8"/>',
 interviews:'<rect x="3" y="5" width="14" height="14" rx="2"/><path d="m17 10 4-2v8l-4-2z"/><circle cx="10" cy="10" r="2"/>',
 assessments:'<path d="M6 4h12v16H6z"/><path d="m9 10 2 2 4-5M9 16h6"/>',
 onboarding:'<rect x="5" y="3" width="14" height="18" rx="2"/><path d="M9 3v3h6V3M9 11h6M9 15h6"/>',
 assignments:'<path d="M4 7h16v13H4z"/><path d="M8 7V4h8v3M8 12h8"/>',
 timesheets:'<circle cx="12" cy="12" r="9"/><path d="M12 7v6l4 2"/>',
 expenses:'<rect x="3" y="6" width="18" height="13" rx="2"/><path d="M3 10h18M7 15h4"/>',
 finance:'<circle cx="12" cy="12" r="9"/><path d="M15 8.5c-.8-.7-1.8-1-3-1-1.7 0-3 1-3 2.3 0 3.7 6 1.5 6 5.1 0 1.4-1.3 2.6-3.2 2.6-1.3 0-2.5-.4-3.3-1.2M12 5v14"/>',
 vms:'<path d="M4 8h13l-3-3M20 16H7l3 3"/><path d="M17 5v6M7 13v6"/>',
 suppliers:'<path d="M8 12 5 9l-3 3 5 5 4-4"/><path d="m16 12 3-3 3 3-5 5-4-4"/><path d="m9 13 3 3 3-3"/>',
 communications:'<path d="M4 5h16v12H8l-4 4z"/><path d="m6 8 6 4 6-4"/>',
 reports:'<path d="M5 20V10h4v10M10 20V4h4v16M15 20v-7h4v7"/>',
 admin:'<circle cx="12" cy="12" r="3"/><path d="M19 12a7 7 0 0 0-.1-1l2-1.5-2-3.4-2.4 1a7 7 0 0 0-1.7-1L14.5 3h-5l-.4 3.1a7 7 0 0 0-1.7 1L5 6.1 3 9.5 5 11a7 7 0 0 0 0 2l-2 1.5 2 3.4 2.4-1a7 7 0 0 0 1.7 1l.4 3.1h5l.4-3.1a7 7 0 0 0 1.7-1l2.4 1 2-3.4L19 13a7 7 0 0 0 0-1Z"/>',
 audit:'<path d="M5 3h14v18H5z"/><path d="M8 8h8M8 12h8M8 16h5"/>',
 search:'<circle cx="10.5" cy="10.5" r="6.5"/><path d="m15.5 15.5 5 5"/>',
 logout:'<path d="M10 5H5v14h5M14 8l4 4-4 4M8 12h10"/>',
 pin:'<path d="m9 3 6 6-2 2 2 5-2 2-5-5-2 2-1-1 4-4-3-5z"/>',
 star:'<path d="m12 3 2.7 5.5 6.1.9-4.4 4.3 1 6.1-5.4-2.9-5.4 2.9 1-6.1-4.4-4.3 6.1-.9z"/>',
 default:'<circle cx="12" cy="12" r="8"/><path d="M8 12h8M12 8v8"/>'
};

function r10Icon(name){
 const key=R10_ICON_PATHS[name]?name:'default';
 return `<svg class="r10-icon" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">${R10_ICON_PATHS[key]}</svg>`;
}

async function r10SuggestInline(input,kind,profession=''){
 if(!input)return;

 if(input.dataset.r10Skip==='1'){
   delete input.dataset.r10Skip;
   return;
 }

 const parent=input.parentElement;
 if(!parent)return;

 parent.querySelectorAll('.r10-autocomplete').forEach(x=>x.remove());

 const q=input.value.trim();
 const url='/api/search/suggestions?kind='+
   encodeURIComponent(kind)+
   '&q='+encodeURIComponent(q)+
   (profession?'&profession='+encodeURIComponent(profession):'');

 let data;
 try{
   data=await api(url);
 }catch(e){
   return;
 }

 const items=data.items||[];
 if(!items.length)return;

 const list=document.createElement('div');
 list.className='r10-autocomplete';
 list.setAttribute('role','listbox');

 let active=-1;

 const choose=(value)=>{
   input.dataset.r10Skip='1';
   input.value=value;
   input.dispatchEvent(new Event('input',{bubbles:true}));
   list.remove();
   input.focus();
 };

 items.forEach((value,index)=>{
   const option=document.createElement('button');
   option.type='button';
   option.className='r10-autocomplete-option';
   option.textContent=value;
   option.dataset.index=String(index);
   option.onclick=()=>choose(value);
   list.appendChild(option);
 });

 parent.appendChild(list);

 input.onkeydown=(event)=>{
   const options=[...list.querySelectorAll('.r10-autocomplete-option')];
   if(!options.length)return;

   if(event.key==='ArrowDown'){
     event.preventDefault();
     active=(active+1)%options.length;
   }else if(event.key==='ArrowUp'){
     event.preventDefault();
     active=(active-1+options.length)%options.length;
   }else if(event.key==='Enter' && active>=0){
     event.preventDefault();
     options[active].click();
     return;
   }else if(event.key==='Escape'){
     list.remove();
     return;
   }else{
     return;
   }

   options.forEach(
     (x,i)=>x.classList.toggle('active',i===active)
   );
 };

 setTimeout(()=>{
   document.addEventListener('click',function close(ev){
     if(ev.target!==input && !list.contains(ev.target)){
       list.remove();
       document.removeEventListener('click',close);
     }
   });
 },0);
}

let ME=null, REF=null, CURRENT='menu', SEARCH_STATE=null, PROFILE_TAB='Resume', selectedSearch=new Set();

async function api(url,opt={}){opt.headers={'Content-Type':'application/json',...(opt.headers||{})}; if(opt.body && typeof opt.body!=='string')opt.body=JSON.stringify(opt.body); const r=await fetch(url,opt); const d=await r.json().catch(()=>({})); if(!r.ok) throw new Error(d.detail||d.error||`HTTP ${r.status}`); return d;}
function toast(msg,type='ok'){const d=document.createElement('div');d.className='toast '+type;d.textContent=msg;$('#toastRoot').appendChild(d);setTimeout(()=>d.remove(),3500)}
function modal(title,body,footer='',large=false){$('#modalRoot').innerHTML=`<div class="modal-back" onclick="if(event.target===this)closeModal()"><div class="modal ${large?'large':''}"><div class="modal-head"><span>${title}</span><button class="btn small" onclick="closeModal()">✕</button></div><div class="modal-body">${body}</div>${footer?`<div class="modal-foot">${footer}</div>`:''}</div></div>`}
function closeModal(){$('#modalRoot').innerHTML=''}
function fd(form){return Object.fromEntries(new FormData(form).entries())}
function formFields(fields){return fields.map(f=>{let input=''; if(f.type==='select') input=`<select name="${f.name}">${(f.options||[]).map(x=>{const value=x.value??x;return `<option value="${esc(value)}" ${String(value)===String(f.value??'')?'selected':''}>${esc(x.label??x)}</option>`}).join('')}</select>`; else if(f.type==='textarea') input=`<textarea rows="${f.rows||4}" name="${f.name}" placeholder="${esc(f.placeholder||'')}">${esc(f.value??'')}</textarea>`; else input=`<input type="${f.type||'text'}" name="${f.name}" value="${esc(f.value??'')}" placeholder="${esc(f.placeholder||'')}" ${f.required?'required':''}>`; return `<div class="field ${f.span?'span2':''}"><label>${esc(f.label)}</label>${input}</div>`}).join('')}

const internalRoles=['admin','teamlead','recruiter','sales','hr','finance'];
const NAV={
 admin:[['menu','⌂','App Menu'],['dashboard','▥','Dashboard'],['talent','◉','Talent Search'],['boolean','B','Boolean Search'],['candidates','👤','Candidates'],['hotlists','🔥','Hotlists / Pools'],['jobs','💼','Jobs'],['companies','🏢','Companies / CRM'],['contacts','☎','Contacts'],['submissions','↗','Submittals'],['interviews','🎥','Interviews'],['assessments','✓','Assessments'],['onboarding','📋','Onboarding'],['assignments','🧰','Assignments'],['timesheets','🕒','Timesheets'],['expenses','💳','Expenses'],['finance','＄','Finance'],['vms','⇄','VMS / MSP'],['suppliers','🤝','Suppliers'],['communications','✉','Communication'],['reports','📊','Reports'],['admin','⚙','Admin'],['audit','🧾','Audit Trail']],
 teamlead:null,recruiter:null,sales:null,hr:null,finance:null,
 client:[['clientPortal','🏢','Client Portal']],candidate:[['candidatePortal','🔎','Candidate Portal']],worker:[['workerPortal','🕒','MyTime Portal']],supplier:[['supplierPortal','🤝','Supplier Portal']],approver:[['approverPortal','✓','Approver Portal']]
};
NAV.teamlead=NAV.admin.filter(x=>!['admin','finance'].includes(x[0]));
NAV.recruiter=NAV.admin.filter(x=>['menu','dashboard','talent','boolean','candidates','hotlists','jobs','submissions','interviews','assessments','onboarding','communications','reports'].includes(x[0]));
NAV.sales=NAV.admin.filter(x=>['menu','dashboard','jobs','companies','contacts','submissions','communications','reports'].includes(x[0]));
NAV.hr=NAV.admin.filter(x=>['menu','dashboard','candidates','onboarding','assignments','timesheets','expenses','reports'].includes(x[0]));
NAV.finance=NAV.admin.filter(x=>['menu','dashboard','assignments','timesheets','expenses','finance','reports'].includes(x[0]));

async function boot(){try{ME=await api('/api/me');REF=await api('/api/reference');renderShell();route(location.hash.slice(1)||defaultRoute())}catch(e){renderLogin()}}
function defaultRoute(){return internalRoles.includes(ME?.role)?'menu':({client:'clientPortal',candidate:'candidatePortal',worker:'workerPortal',supplier:'supplierPortal',approver:'approverPortal'}[ME?.role]||'menu')}
function renderLogin(){ME=null; document.body.innerHTML=`<div id="app"></div><div id="modalRoot"></div><div id="toastRoot"></div>`; $('#app').innerHTML=`<div class="login-shell"><div class="login-card"><div class="login-hero"><div class="brandmark"><b>ATS</b> One</div><h1>Staffing ERP</h1><p>Multi-user recruiting, CRM, sourcing, onboarding, workforce and financial operations in one linked system.</p><div class="login-features"><div class="login-feature"><b>Talent Intelligence</b><br>Boolean + experience-aware search</div><div class="login-feature"><b>Staffing Workflow</b><br>Job → Submission → Start → Assignment</div><div class="login-feature"><b>Back Office</b><br>Time, expense, PO & invoices</div><div class="login-feature"><b>Role Portals</b><br>Client, candidate, worker & supplier</div></div></div><div class="login-form"><h2>Sign in</h2><p class="subtle">Use any demo account below. All accounts use the same shared server database.</p><form id="loginForm"><div class="field"><label>Email</label><input name="email" value="admin@atsone.local" autocomplete="username"></div><div class="field"><label>Password</label><input name="password" type="password" value="Admin@123" autocomplete="current-password"></div><button class="btn primary wide">SIGN IN</button></form><div class="demo-grid">${[['Admin','admin@atsone.local','Admin@123'],['Recruiter','recruiter@atsone.local','Recruit@123'],['Team Lead','teamlead@atsone.local','Lead@123'],['Sales','sales@atsone.local','Sales@123'],['HR','hr@atsone.local','HR@123'],['Finance','finance@atsone.local','Finance@123'],['Client','client@atsone.local','Client@123'],['Candidate','candidate@atsone.local','Candidate@123'],['Worker','worker@atsone.local','Worker@123'],['Supplier','supplier@atsone.local','Supplier@123'],['Approver','approver@atsone.local','Approve@123']].map(x=>`<div class="demo-pill" onclick="quickLogin('${x[1]}','${x[2]}')"><b>${x[0]}</b><br>${x[1]}</div>`).join('')}</div></div></div></div>`; $('#loginForm').onsubmit=async e=>{e.preventDefault();const d=fd(e.target);try{await api('/api/login',{method:'POST',body:d});await boot()}catch(er){toast(er.message,'err')}}}
async function quickLogin(email,password){try{await api('/api/login',{method:'POST',body:{email,password}});await boot()}catch(e){toast(e.message,'err')}}
function renderShell(){document.body.innerHTML=`<div id="app"></div><div id="modalRoot"></div><div id="toastRoot"></div>`; const nav=NAV[ME.role]||[]; $('#app').innerHTML=`<div class="app-shell"><div class="topbar"><div class="logo"><b>ATS</b> One</div><div class="global-search"><input id="globalQ" placeholder="Search candidates, jobs, companies…"><button class="r10-icon-button" aria-label="Search" onclick="globalSearch()">${r10Icon("search")}</button></div><div class="top-icons"><span class="r10-top-icon">${r10Icon("pin")}</span><span class="r10-top-icon">${r10Icon("star")}</span><span class="weather">72°F</span><span class="r10-top-icon">${r10Icon("admin")}</span></div><div class="user-chip"><div class="avatar">${esc(ME.name[0])}</div><div><b>${esc(ME.name)}</b><div class="muted" style="font-size:10px">${esc(ME.role)}</div></div><button class="btn small r10-icon-button" aria-label="Sign out" onclick="logout()">${r10Icon("logout")}</button></div></div><div class="layout"><aside class="sidebar"><div class="side-title">Navigation</div>${nav.map(x=>`<div class="navitem" data-route="${x[0]}" onclick="go('${x[0]}')"><span class="navicon">${r10Icon(x[0])}</span>${x[2]}</div>`).join('')}<div class="side-title">Session</div><div class="navitem" onclick="go('menu')"><span class="navicon">${r10Icon("home")}</span>Home</div></aside><main class="content" id="content"></main></div></div>`; $('#globalQ').addEventListener('keydown',e=>{if(e.key==='Enter')globalSearch()})}
async function logout(){await api('/api/logout',{method:'POST'}).catch(()=>{});renderLogin()}
function go(r){location.hash=r;route(r)}
async function route(r){CURRENT=r; $$('.navitem').forEach(n=>n.classList.toggle('active',n.dataset.route===r)); const c=$('#content'); if(!c)return; c.innerHTML='<div class="page"><div class="panel"><div class="panel-body">Loading…</div></div></div>'; try{
 const [base,id]=r.split('/'); const fn={menu:pageMenu,dashboard:pageDashboard,talent:pageTalent,boolean:pageBoolean,candidates:pageCandidates,candidate:()=>pageCandidate(id),hotlists:pageHotlists,jobs:pageJobs,job:()=>pageJob(id),companies:pageCompanies,contacts:pageContacts,submissions:pageSubmissions,interviews:pageInterviews,assessments:pageAssessments,onboarding:pageOnboarding,assignments:pageAssignments,timesheets:pageTimesheets,expenses:pageExpenses,finance:pageFinance,vms:pageVMS,suppliers:pageSuppliers,communications:pageCommunications,reports:pageReports,admin:pageAdmin,audit:pageAudit,candidatePortal:pageCandidatePortal,clientPortal:pageClientPortal,workerPortal:pageWorkerPortal,supplierPortal:pageSupplierPortal,approverPortal:pageApproverPortal}[base]; if(!fn)throw new Error('Unknown page'); await fn(); enhanceR8Controls(base,id); }catch(e){c.innerHTML=`<div class="page"><div class="panel"><div class="panel-body"><b>Unable to load page.</b><br>${esc(e.message)}</div></div></div>`}}
window.addEventListener('hashchange',()=>route(location.hash.slice(1)||defaultRoute()));
function head(title,crumb='',actions=''){return `<div class="pagehead"><div><h1>${title}</h1><div class="crumb">${crumb}</div></div><div class="actions">${actions}</div></div>`}
function panel(title,body,extra=''){return `<div class="panel"><div class="panel-title"><span>${title}</span>${extra}</div><div class="panel-body">${body}</div></div>`}

function pageMenu(){const modules=[
 ['teal','Talent Management',[['◉','Talent Search','talent'],['B','Boolean Search','boolean'],['💡','New Candidate','newCandidate'],['👤','Search Candidates','candidates'],['🧑‍💼','Search Employees','assignments'],['🔥','Candidate Hotlists','hotlists'],['📝','Candidate Notes','candidates'],['🏷','Search Attributes','talent'],['⬆','Import Candidates','newCandidate']]],
 ['orange','Job Management',[['💼','My Jobs','jobs'],['🧳','My Jobs as Primary','jobs'],['🔍','Search Jobs','jobs'],['➕','New Job','newJob'],['📊','Jobs Dashboard','dashboard'],['📌','My Jobs Dashboard','dashboard'],['↗','Submittals','submissions'],['🎥','Interviews','interviews']]],
 ['purple','CRM',[['👤','My Contacts','contacts'],['🔎','Search Contacts','contacts'],['➕','New Contact','newContact'],['🔥','Contact Hotlists','contacts'],['🏢','Search Companies','companies'],['➕','New Company','newCompany'],['📈','Opportunities','companies'],['🧲','Leads','companies']]],
 ['blue','Reporting Tools',[['📄','Reports','reports'],['📊','BI Shared With Me','reports'],['🧾','Audit Trail','audit'],['⚙','Configuration','admin']]],
 ['blue','Dashboards',[['📊','User Dashboard','dashboard'],['👥','Team Dashboard','dashboard'],['📈','Opportunities','companies'],['💵','Financial','finance']]],
 ['yellow','Events & Communication',[['📅','Calendar','interviews'],['🎤','e-Interview','assessments'],['✉','Email / SMS','communications'],['✅','Onboarding','onboarding'],['🕒','Timesheets','timesheets'],['❓','Help / Map','reports']]],
 ]; $('#content').innerHTML=`<div class="launcher-bg"><div class="launcher">${modules.map(m=>`<div class="module-card ${m[0]}"><h3>${m[1]}</h3><div class="module-links">${m[2].map(a=>`<div class="module-link" onclick="menuAction('${a[2]}')"><span class="module-ico">${r10Icon(a[2])}</span><span class="module-name">${a[1]}</span></div>`).join('')}</div></div>`).join('')}</div></div>`}
function menuAction(a){if(a==='newCandidate')return openCandidateForm();if(a==='newJob')return openJobForm();if(a==='newContact')return openContactInfo();if(a==='newCompany')return openCompanyInfo();go(a)}

async function pageDashboard(){const d=await api('/api/dashboard'); if(!internalRoles.includes(ME.role)) return go(defaultRoute()); const max=Math.max(...d.company_pipeline.map(x=>x.count),1); $('#content').innerHTML=`<div class="page">${head('User Dashboard','Home › Dashboards › User Dashboard')}<div class="dashboard-grid"><div class="dashcol"><div class="metric-panel"><h3>My Sales Funnel</h3><div class="funnel">${d.company_pipeline.map(x=>`<div>${x.stage} · ${x.count}</div>`).join('')}</div></div><div class="metric-panel"><h3>My Recruiting Activities So Far This Week</h3><div class="panel-body"><div class="kv"><b>Open Tasks</b><span>${d.open_tasks}</span></div><div class="kv"><b>Active Candidates</b><span>${d.candidates}</span></div><div class="kv"><b>Submittals</b><span>${d.pipeline.reduce((a,x)=>a+x.count,0)}</span></div></div></div></div><div class="dashcol"><div class="metric-panel"><h3>My Open Jobs</h3><div class="metric-row"><div class="metric"><strong>${d.open_jobs}</strong><span>Open Jobs</span></div><div class="metric"><strong>${d.primary_jobs}</strong><span>As Primary</span></div><div class="metric"><strong>${d.jobs_no_activity}</strong><span>W/O Activity</span></div><div class="metric"><strong>${Math.max(0,d.open_jobs-d.primary_jobs)}</strong><span>As Secondary</span></div></div></div><div class="metric-panel"><h3>My Sales Pipeline of Companies</h3><div class="bar-chart">${d.company_pipeline.map(x=>`<div class="bar" style="height:${Math.max(8,(x.count/max)*135)}px"><em>${x.count}</em><label>${x.stage}</label></div>`).join('')}</div></div><div class="metric-panel"><h3>Recent Jobs</h3><div class="tablewrap"><table class="grid"><tr><th>Job #</th><th>Title</th><th>Client</th><th>Status</th><th>Subs</th></tr>${d.recent_jobs.map(j=>`<tr><td><a class="link" onclick="go('job/${j.id}')">${j.job_no}</a></td><td>${esc(j.title)}</td><td>${esc(j.company_name||'')}</td><td>${status(j.status)}</td><td>${j.submissions}</td></tr>`).join('')}</table></div></div></div><div class="dashcol"><div class="metric-panel"><h3>My Current Employees</h3><div class="metric-row" style="grid-template-columns:1fr 1fr"><div class="metric"><strong>${d.active_assignments}</strong><span>Active</span></div><div class="metric bad"><strong>${d.pending_timesheets}</strong><span>Timesheets Pending</span></div></div></div><div class="metric-panel"><h3>My Starts Onboarding</h3><div class="metric-row" style="grid-template-columns:1fr 1fr"><div class="metric"><strong>${d.starts_30}</strong><span>Starts</span></div><div class="metric warn"><strong>${d.pending_onboarding}</strong><span>Incomplete Packages</span></div></div></div><div class="metric-panel"><h3>To Do This Week</h3><div class="panel-body">${d.tasks.length?d.tasks.map(t=>`<div class="kv"><span>${esc(t.title)}</span><small>${fmtDate(t.due_at)}</small></div>`).join(''):'<div class="empty">No tasks</div>'}</div></div><div class="metric-panel"><h3>Finance Attention</h3><div class="metric-row" style="grid-template-columns:1fr 1fr"><div class="metric warn"><strong>${d.pending_expenses}</strong><span>Expenses Pending</span></div><div class="metric"><strong>${d.active_assignments}</strong><span>Billable Assignments</span></div></div></div></div></div></div>`}

const professions=['RN','Data Engineer','Software Engineer','Business Analyst','Nurse Practitioner','Physician Assistant','LPN LVN','CNA','MRI Technologist','Cloud Engineer','QA / SDET','Project Manager'];
function blankSearch(){return {tab:'Profession/Specialty',profession:'',specialty:'',licenses:[],certifications:[],qualification:'',require:[{term:'',years:0,recent:false,operator:'AND'}],exclude:[{term:''}],exclude_candidate_ids:[],attributes:[],title:'',state:'',zip:'',radius:'50',pay_min:'',pay_max:'',available_before:'',without_mapping:false,raw_boolean:''}}
async function pageTalent(){SEARCH_STATE=SEARCH_STATE||blankSearch(); renderTalent()}
function renderTalent(results=null,criteria='',duration=''){const s=SEARCH_STATE; const tabs=['Profession/Specialty','Licenses','Certifications','Qualification','Require','Exclude','Attribute','Title']; let main='';
 if(s.tab==='Profession/Specialty')main=`<div class="sectionhead">PROFESSION / SPECIALTY</div><p class="subtle">Type to search professions and specialties. Suggestions combine current ATS data with a safe starter vocabulary.</p><div class="r10-profession-search"><div class="field"><label>Profession</label><input id="r10ProfessionInput" data-testid="profession-input" autocomplete="off" placeholder="Start typing: Software Engineer, Data Engineer..." value="${esc(s.profession)}" oninput="SEARCH_STATE.profession=this.value;refreshCriteria();r10SuggestInline(this,'profession')"></div><div class="field"><label>Specialty</label><input id="r10SpecialtyInput" data-testid="specialty-input" autocomplete="off" placeholder="Backend, Java Backend, Data Platform..." value="${esc(s.specialty)}" oninput="SEARCH_STATE.specialty=this.value;refreshCriteria();r10SuggestInline(this,'specialty',SEARCH_STATE.profession)"></div></div><div class="r10-selected-criteria">${s.profession?`<span class="tag">Profession: ${esc(s.profession)}</span>`:''}${s.specialty?`<span class="tag">Specialty: ${esc(s.specialty)}</span>`:''}</div>`;
 if(s.tab==='Licenses')main=`<div class="sectionhead">LICENSES</div>${licenseRows()}<button class="btn small" onclick="addLicense()">+ AND License</button>`;
 if(s.tab==='Certifications')main=`<div class="sectionhead">CERTIFICATIONS</div>${certRows()}<button class="btn small" onclick="addCert()">+ AND Certification</button>`;
 if(s.tab==='Qualification')main=`<div class="sectionhead">QUALIFICATION</div><div class="field"><label>Degree / qualification / value</label><input value="${esc(s.qualification)}" oninput="SEARCH_STATE.qualification=this.value;refreshCriteria();r10SuggestInline(this,'qualification')" placeholder="BSN, MBA, Bachelors…"></div><p class="subtle">Qualification searches structured qualification records, not only raw resume text.</p>`;
 if(s.tab==='Require')main=`<div class="sectionhead">REQUIRE — MUST-HAVE SKILLS / EXPERIENCE</div>${requireRows()}<button class="btn small" onclick="addRequire()">+ Add condition</button><div class="field"><label>Raw Boolean / JobDiva-style expression</label><textarea rows="3" oninput="SEARCH_STATE.raw_boolean=this.value;refreshCriteria()" placeholder='(DEVELOPER RECENT OVER 5 YRS) AND (JAVA OVER 5 YRS OR "C #" OVER 5 YRS)'>${esc(s.raw_boolean)}</textarea></div>`;
 if(s.tab==='Exclude')main=`<div class="sectionhead">EXCLUDE</div>${excludeRows()}<button class="btn small" onclick="addExclude()">+ Add excluded term</button>`;
 if(s.tab==='Attribute')main=`<div class="sectionhead">ATTRIBUTE</div><div class="field"><label>Internal candidate attributes (comma separated)</label><input value="${esc(s.attributes.join(', '))}" oninput="SEARCH_STATE.attributes=this.value.split(',').map(x=>x.trim()).filter(Boolean);refreshCriteria()" placeholder="Top Candidate, Compact License"></div>`;
 if(s.tab==='Title')main=`<div class="sectionhead">TITLE</div><div class="field"><label>Current / most recent title contains</label><input value="${esc(s.title)}" oninput="SEARCH_STATE.title=this.value;refreshCriteria();r10SuggestInline(this,'title')" placeholder="Senior Java Developer"></div>`;
 const res=results?`<div style="margin-top:14px"><div class="search-criteria-line">Search Criteria: <b>${esc(criteria)}</b> <span class="muted" style="float:right">Showing ${results.length} · ${duration||0} ms</span></div><div class="actionbar"><span class="actionlink" onclick="searchAction('exclude')">✖ Exclude</span><span class="actionlink" onclick="searchAction('qualify')">✔ Qualify</span><span class="actionlink" onclick="searchAction('expand')">👀 Expand</span><span class="actionlink" onclick="searchAction('hotlist')">🔥 Hotlist</span><span class="actionlink" onclick="searchAction('preview')">🔎 Preview</span><span class="actionlink" onclick="searchAction('relevancy')">🎉 Relevancy</span><span class="actionlink" onclick="searchAction('bulk')">Bulk Action ▾</span><span class="actionlink" onclick="searchAction('email')">✉ Email Merge</span></div><div class="tablewrap"><table class="grid"><tr><th><input type="checkbox" onchange="toggleAllSearch(this.checked)"></th><th>Name</th><th>Phone</th><th>City</th><th>State</th><th>Received</th><th>Available</th><th>Last Note</th><th>Relevancy</th></tr>${results.map(c=>`<tr data-cid="${c.id}"><td><input class="srchk" type="checkbox" value="${c.id}" onchange="toggleSearchSel(${c.id},this.checked)"></td><td><a class="link" onclick="go('candidate/${c.id}')">${esc(c.first_name+' '+c.last_name)}</a><br><small>${esc(c.current_title||'')}</small></td><td>${esc(c.phone||'')}</td><td>${esc(c.city||'')}</td><td>${esc(c.state||'')}</td><td>${fmtDate(c.created_at)}</td><td>${fmtDate(c.availability_date)}</td><td>${c.notes?.[0]?fmtDate(c.notes[0].created_at):''}</td><td class="score">${c.relevance}%</td></tr>`).join('')}</table></div></div>`:'';
 $('#content').innerHTML=`<div class="page">${head('Talent Search','App Menu › Sourcing › Talent Search','<button class="btn" onclick="saveDynamicPool()">Save as Dynamic Pool</button>')}<div class="search-shell"><div class="search-titlebar">Talent Search</div><div class="search-tabs">${tabs.map(t=>`<div class="search-tab ${s.tab===t?'active':''}" onclick="SEARCH_STATE.tab='${t}';renderTalent()">${t}</div>`).join('')}</div><div class="search-grid"><div class="search-main">${main}<div class="criteria-box" id="criteriaPreview">${esc(compileLocalCriteria())}</div></div><div class="search-side"><div class="sectionhead">REFINE SEARCH</div><div class="side-row"><label>State:</label><input value="${esc(s.state)}" oninput="SEARCH_STATE.state=this.value"></div><div class="side-row"><label>Zip Code:</label><input value="${esc(s.zip)}" oninput="SEARCH_STATE.zip=this.value"></div><div class="side-row"><label>Within:</label><select onchange="SEARCH_STATE.radius=this.value"><option>25</option><option ${s.radius==='50'?'selected':''}>50</option><option>100</option><option>250</option></select></div><div class="sectionhead" style="margin-top:12px">SALARY / PAY</div><div class="side-row"><label>Min:</label><input type="number" value="${esc(s.pay_min)}" oninput="SEARCH_STATE.pay_min=this.value"></div><div class="side-row"><label>Max:</label><input type="number" value="${esc(s.pay_max)}" oninput="SEARCH_STATE.pay_max=this.value"></div><div class="sectionhead" style="margin-top:12px">AVAILABILITY</div><div class="side-row"><label>Available by:</label><input type="date" value="${esc(s.available_before)}" oninput="SEARCH_STATE.available_before=this.value"></div><label style="display:block;margin-top:10px"><input type="checkbox" ${s.without_mapping?'checked':''} onchange="SEARCH_STATE.without_mapping=this.checked"> w/o Mapping</label><p class="subtle" style="font-size:11px">Turn mapping off to match only literal skill terms instead of normalized aliases.</p></div></div><div class="search-footer"><button class="btn primary" onclick="runTalentSearch()">SEARCH</button> <button class="btn" onclick="SEARCH_STATE=blankSearch();renderTalent()">CLEAR</button></div></div>${res}</div>`}
function pickProfession(p){if(SEARCH_STATE.profession===p){SEARCH_STATE.profession='';SEARCH_STATE.specialty=''}else SEARCH_STATE.profession=p;renderTalent()}
function licenseRows(){if(!SEARCH_STATE.licenses.length)SEARCH_STATE.licenses.push({type:'',country:'USA',state:'',active:true,expiry_after:'',documented:false});return SEARCH_STATE.licenses.map((r,i)=>`<div class="filter-row"><input class="skillterm" placeholder="License type" value="${esc(r.type)}" oninput="SEARCH_STATE.licenses[${i}].type=this.value;refreshCriteria();r10SuggestInline(this,'license')"><select onchange="SEARCH_STATE.licenses[${i}].country=this.value"><option>USA</option><option ${r.country==='India'?'selected':''}>India</option><option ${r.country==='UK'?'selected':''}>UK</option></select><input placeholder="State" value="${esc(r.state)}" oninput="SEARCH_STATE.licenses[${i}].state=this.value;refreshCriteria()"><input type="date" title="Expiring After" value="${esc(r.expiry_after)}" oninput="SEARCH_STATE.licenses[${i}].expiry_after=this.value"><button class="btn small" onclick="SEARCH_STATE.licenses.splice(${i},1);renderTalent()">✕</button></div><div style="margin:0 0 9px 130px"><label><input type="checkbox" ${r.active?'checked':''} onchange="SEARCH_STATE.licenses[${i}].active=this.checked"> Active</label> &nbsp; <label><input type="checkbox" ${r.documented?'checked':''} onchange="SEARCH_STATE.licenses[${i}].documented=this.checked"> Require Documentation</label></div>`).join('')}
function certRows(){if(!SEARCH_STATE.certifications.length)SEARCH_STATE.certifications.push({name:'',active:true,expiry_after:'',documented:false});return SEARCH_STATE.certifications.map((r,i)=>`<div class="filter-row"><input class="skillterm" placeholder="Certification e.g. ACLS" value="${esc(r.name)}" oninput="SEARCH_STATE.certifications[${i}].name=this.value;refreshCriteria();r10SuggestInline(this,'certification')"><span><label><input type="checkbox" ${r.active?'checked':''} onchange="SEARCH_STATE.certifications[${i}].active=this.checked"> Active</label></span><input type="date" value="${esc(r.expiry_after)}" oninput="SEARCH_STATE.certifications[${i}].expiry_after=this.value"><span><label><input type="checkbox" ${r.documented?'checked':''} onchange="SEARCH_STATE.certifications[${i}].documented=this.checked"> Doc</label></span><button class="btn small" onclick="SEARCH_STATE.certifications.splice(${i},1);renderTalent()">✕</button></div>`).join('')}
function requireRows(){return SEARCH_STATE.require.map((r,i)=>`<div class="filter-row"><input class="skillterm" placeholder="Required term / skill" value="${esc(r.term)}" oninput="SEARCH_STATE.require[${i}].term=this.value;refreshCriteria();r10SuggestInline(this,'skill')"><input type="number" min="0" step=".5" value="${esc(r.years)}" title="Minimum years" oninput="SEARCH_STATE.require[${i}].years=this.value;refreshCriteria()"><label><input type="checkbox" ${r.recent?'checked':''} onchange="SEARCH_STATE.require[${i}].recent=this.checked;refreshCriteria()"> Recent</label><select onchange="SEARCH_STATE.require[${i}].operator=this.value;refreshCriteria()"><option>AND</option><option ${r.operator==='OR'?'selected':''}>OR</option></select><button class="btn small" onclick="SEARCH_STATE.require.splice(${i},1);renderTalent()">✕</button></div>`).join('')}
function excludeRows(){return SEARCH_STATE.exclude.map((r,i)=>`<div class="filter-row" style="grid-template-columns:1fr 40px"><input class="skillterm" placeholder="Excluded term" value="${esc(r.term)}" oninput="SEARCH_STATE.exclude[${i}].term=this.value;refreshCriteria();r10SuggestInline(this,'skill')"><button class="btn small" onclick="SEARCH_STATE.exclude.splice(${i},1);renderTalent()">✕</button></div>`).join('')}
function addLicense(){SEARCH_STATE.licenses.push({type:'',country:'USA',state:'',active:true,expiry_after:'',documented:false});renderTalent()} function addCert(){SEARCH_STATE.certifications.push({name:'',active:true,expiry_after:'',documented:false});renderTalent()} function addRequire(){SEARCH_STATE.require.push({term:'',years:0,recent:false,operator:'AND'});renderTalent()} function addExclude(){SEARCH_STATE.exclude.push({term:''});renderTalent()}
function compileLocalCriteria(){const s=SEARCH_STATE,b=[]; if(s.profession)b.push(`PROFESSION [ ${s.profession} IS ${s.specialty||'ANY'} ]`);s.licenses.filter(x=>x.type).forEach(x=>b.push(`LICENCES=("${x.type}" ST IN {${x.state||'ANY'}})`));s.certifications.filter(x=>x.name).forEach(x=>b.push(`CERTIFICATION [ ${x.name} ]`));s.require.filter(x=>x.term).forEach((x,i)=>b.push(`${i?x.operator+' ':''}(${x.term}${x.recent?' RECENT':''}${+x.years>0?' OVER '+x.years+' YRS':''})`));s.exclude.filter(x=>x.term).forEach(x=>b.push(`NOT (${x.term})`));if(s.title)b.push(`TITLE [ ${s.title} ]`);if(s.raw_boolean)b.push(`BOOLEAN [ ${s.raw_boolean} ]`);return b.join(' ')||'ALL ACTIVE CANDIDATES'}
function refreshCriteria(){const e=$('#criteriaPreview');if(e)e.textContent=compileLocalCriteria()}
function intentionalSearch(){const s=SEARCH_STATE;return {profession:s.profession||'',specialty:s.specialty||'',licenses:(s.licenses||[]).filter(x=>x.type),certifications:(s.certifications||[]).filter(x=>x.name),qualification:s.qualification||'',require:(s.require||[]).filter(x=>x.term),exclude:(s.exclude||[]).filter(x=>x.term),exclude_candidate_ids:s.exclude_candidate_ids||[],attributes:s.attributes||[],title:s.title||'',state:s.state||'',zip:s.zip||'',radius_miles:s.zip?s.radius:'',pay_min:s.pay_min||'',pay_max:s.pay_max||'',available_before:s.available_before||'',without_mapping:!!s.without_mapping,raw_boolean:s.raw_boolean||''}}
async function runTalentSearch(){try{const d=await api('/api/search/talent',{method:'POST',body:intentionalSearch()});window.LAST_TALENT_RESULTS=d.results;selectedSearch.clear();renderTalent(d.results,d.criteria,d.duration_ms)}catch(e){toast(e.message,'err')}}
function toggleSearchSel(id,on){on?selectedSearch.add(id):selectedSearch.delete(id)} function toggleAllSearch(on){$$('.srchk').forEach(x=>{x.checked=on;toggleSearchSel(+x.value,on)})}
async function searchAction(a){const ids=[...selectedSearch];if(!ids.length)return toast('Select one or more candidates first','err'); if(a==='exclude'){$$('tr[data-cid]').filter(r=>ids.includes(+r.dataset.cid)).forEach(r=>r.remove());return toast(`${ids.length} result(s) excluded from this result set`)} if(a==='preview')return go('candidate/'+ids[0]); if(a==='expand')return go('candidate/'+ids[0]); if(a==='relevancy')return toast('Results are already sorted by computed relevancy'); if(a==='hotlist'){const hs=await api('/api/hotlists'); modal('Add to Hotlist',`<div class="field"><label>Hotlist</label><select id="hotSel">${hs.map(h=>`<option value="${h.id}">${esc(h.name)}</option>`).join('')}</select></div>`,`<button class="btn" onclick="closeModal()">Cancel</button><button class="btn primary" onclick="addSelectedHotlist()">Add ${ids.length}</button>`);return} if(a==='qualify'){modal('Qualify against Job',`<div class="field"><label>Job</label><select id="qualJob">${REF.jobs.filter(j=>j.status==='Open').map(j=>`<option value="${j.id}">${j.job_no} — ${esc(j.title)}</option>`).join('')}</select></div><p>Selected candidates will be placed into the job's <b>Interested / Qualified</b> pool.</p>`,`<button class="btn" onclick="closeModal()">Cancel</button><button class="btn primary" onclick="qualifySelected()">Qualify</button>`);return} if(a==='email'){for(const id of ids)await api('/api/communications',{method:'POST',body:{entity_type:'candidate',entity_id:id,channel:'Email',direction:'Outbound',subject:'Talent outreach',body:'Personalized recruiter outreach logged from Talent Search.',status:'Sent'}});return toast(`Email merge logged for ${ids.length} candidate(s)`)} toast('Bulk action menu is available through Hotlist, Qualify and Email Merge in this build')}
async function addSelectedHotlist(){const hid=+$('#hotSel').value;for(const cid of selectedSearch)await api(`/api/hotlists/${hid}/members`,{method:'POST',body:{candidate_id:cid}});closeModal();toast(`${selectedSearch.size} candidate(s) added to hotlist`)}
async function qualifySelected(){const jid=+$('#qualJob').value;for(const cid of selectedSearch)await api(`/api/jobs/${jid}/interested`,{method:'POST',body:{candidate_id:cid,status:'qualified',source:'Talent Search'}});closeModal();toast(`${selectedSearch.size} candidate(s) qualified for job`)}
async function searchAction(a){const ids=[...selectedSearch];if(!ids.length)return toast('Select one or more candidates first','err');const selected=(window.LAST_TALENT_RESULTS||[]).filter(x=>ids.includes(x.id));if(a==='exclude'){SEARCH_STATE.exclude_candidate_ids=[...new Set([...(SEARCH_STATE.exclude_candidate_ids||[]),...ids])];return runTalentSearch()}if(a==='preview')return go('candidate/'+ids[0]);if(a==='expand')return modal('Structured Match Evidence',selected.map(c=>`<h3>${esc(c.first_name+' '+c.last_name)} â€” ${c.relevance}%</h3><div class="codeblock">${esc(JSON.stringify(c.match_reasons||[],null,2))}</div>`).join(''),'<button class="btn" onclick="closeModal()">Close</button>',true);if(a==='relevancy')return modal('Relevancy Scores',selected.map(c=>`<div class="kv"><b>${esc(c.first_name+' '+c.last_name)}</b><span>${c.relevance}% Â· ${esc((c.match_reasons||[]).map(x=>typeof x==='string'?x:(x.term||x.type)).join(', '))}</span></div>`).join(''),'<button class="btn" onclick="closeModal()">Close</button>');if(a==='hotlist'){const hs=await api('/api/hotlists');return modal('Add to Hotlist',`<div class="field"><label>Hotlist</label><select id="hotSel">${hs.map(h=>`<option value="${h.id}">${esc(h.name)}</option>`).join('')}</select></div>`,`<button class="btn" onclick="closeModal()">Cancel</button><button class="btn primary" onclick="addSelectedHotlist()">Add ${ids.length}</button>`)}if(a==='qualify')return modal('Qualify against Job',`<div class="field"><label>Job</label><select id="qualJob">${REF.jobs.filter(j=>j.status==='Open').map(j=>`<option value="${j.id}">${j.job_no} â€” ${esc(j.title)}</option>`).join('')}</select></div>`,`<button class="btn" onclick="closeModal()">Cancel</button><button class="btn primary" onclick="qualifySelected()">Qualify</button>`);if(a==='email'){await api('/api/search/bulk',{method:'POST',body:{action:'email',candidate_ids:ids,subject:'Talent outreach',body:'Personalized recruiter outreach logged from Talent Search.'}});return toast(`Email merge logged for ${ids.length} candidate(s)`)}if(a==='bulk')return modal('Bulk Action Engine',`<p>${ids.length} candidates selected.</p><div class="field"><label>Action</label><select id="bulkKind"><option value="email">Email outreach</option><option value="qualify">Qualify for job</option><option value="hotlist">Add to hotlist</option></select></div>`,`<button class="btn" onclick="closeModal()">Cancel</button><button class="btn primary" onclick="runBulkAction()">Continue</button>`)}
async function runBulkAction(){const action=$('#bulkKind').value;closeModal();return searchAction(action)}
async function saveDynamicPool(){const name=prompt('Dynamic Talent Pool / Hotlist name:','Saved Talent Search');if(!name)return;await api('/api/hotlists',{method:'POST',body:{name,description:'Dynamic pool saved from Talent Search',visibility:'Team',mode:'dynamic',saved_search:intentionalSearch()}});toast('Dynamic pool saved')}


function r10BooleanResultHTML(results,criteria,duration){
 const rows=results||[];

 return `<div class="r10-boolean-results">
   <div class="search-criteria-line">
     Search Criteria: <b>${esc(criteria||'')}</b>
     <span class="muted" style="float:right">
       Showing ${rows.length} · ${duration||0} ms
     </span>
   </div>

   ${rows.length?`
   <div class="actionbar">
     <span class="actionlink" onclick="searchAction('exclude')">Exclude</span>
     <span class="actionlink" onclick="searchAction('qualify')">Qualify</span>
     <span class="actionlink" onclick="searchAction('expand')">Expand</span>
     <span class="actionlink" onclick="searchAction('hotlist')">Hotlist</span>
     <span class="actionlink" onclick="searchAction('preview')">Preview</span>
     <span class="actionlink" onclick="searchAction('relevancy')">Relevancy</span>
     <span class="actionlink" onclick="searchAction('bulk')">Bulk Action</span>
     <span class="actionlink" onclick="searchAction('email')">Email Merge</span>
   </div>

   <div class="tablewrap">
   <table class="grid">
    <tr>
      <th><input type="checkbox" onchange="toggleAllSearch(this.checked)"></th>
      <th>Name</th>
      <th>Title</th>
      <th>Location</th>
      <th>Relevancy</th>
      <th>Evidence</th>
    </tr>
    ${rows.map(c=>`
      <tr data-cid="${c.id}">
       <td><input class="srchk" type="checkbox" value="${c.id}" onchange="toggleSearchSel(${c.id},this.checked)"></td>
       <td><a class="link" onclick="go('candidate/${c.id}')">${esc(c.first_name+' '+c.last_name)}</a></td>
       <td>${esc(c.current_title||'')}</td>
       <td>${esc([c.city,c.state].filter(Boolean).join(', '))}</td>
       <td class="score">${c.relevance}%</td>
       <td>${esc((c.match_reasons||[]).map(x=>typeof x==='string'?x:(x.term||x.type||'match')).join(', '))}</td>
      </tr>
    `).join('')}
   </table>
   </div>`:
   '<div class="empty">No candidates matched this Boolean expression.</div>'}
 </div>`;
}

async function pageBoolean(){
 SEARCH_STATE=SEARCH_STATE||blankSearch();

 $('#content').innerHTML=`<div class="page">
 ${head(
   'Boolean Search',
   'App Menu › Sourcing › Boolean Search'
 )}
 <div class="panel">
  <div class="panel-title">
   <span>Experience-aware Boolean Search</span>
  </div>
  <div class="panel-body">
   <p class="subtle">
    Use AND, OR, NOT, parentheses, RECENT and OVER N YRS.
    This page uses the same server-side matching engine as Talent Search.
   </p>

   <div class="r10-boolean-toolbar">
    <button class="btn small" onclick="r10BooleanInsert(' AND ')">AND</button>
    <button class="btn small" onclick="r10BooleanInsert(' OR ')">OR</button>
    <button class="btn small" onclick="r10BooleanInsert(' NOT ')">NOT</button>
    <button class="btn small" onclick="r10BooleanInsert('(')">(</button>
    <button class="btn small" onclick="r10BooleanInsert(')')">)</button>
    <button class="btn small" onclick="r10BooleanInsert(' RECENT ')">RECENT</button>
    <button class="btn small" onclick="r10BooleanInsert(' OVER 5 YRS')">OVER 5 YRS</button>
   </div>

   <div class="field">
    <label>Boolean expression</label>
    <textarea
      id="r10BooleanExpression"
      data-testid="boolean-expression"
      rows="5"
      placeholder='(Java OVER 5 YRS AND Banking OVER 2 YRS) AND NOT Mainframe'
      oninput="SEARCH_STATE.raw_boolean=this.value"
    >${esc(SEARCH_STATE.raw_boolean||'')}</textarea>
   </div>

   <div class="r10-example-grid">
    <button class="r10-example" onclick="r10BooleanExample(this.textContent)">
     (Java OVER 5 YRS AND Banking OVER 2 YRS) AND NOT Mainframe
    </button>
    <button class="r10-example" onclick="r10BooleanExample(this.textContent)">
     (DEVELOPER RECENT OVER 5 YRS) AND (JAVA OVER 5 YRS OR "C #" OVER 5 YRS)
    </button>
    <button class="r10-example" onclick="r10BooleanExample(this.textContent)">
     Amazon Web Services OVER 5 YRS
    </button>
   </div>

   <label class="r10-map-toggle">
    <input
      id="r10BooleanMapping"
      type="checkbox"
      ${SEARCH_STATE.without_mapping?'':'checked'}
      onchange="SEARCH_STATE.without_mapping=!this.checked"
    >
    Synonym / normalized skill mapping
   </label>

   <div class="actions" style="margin-top:14px">
    <button
      class="btn"
      data-testid="boolean-validate"
      onclick="r10ValidateBoolean()"
    >Validate</button>

    <button
      class="btn primary"
      data-testid="boolean-search"
      onclick="r10RunBooleanSearch()"
    >Search Candidates</button>

    <button
      class="btn"
      onclick="SEARCH_STATE.raw_boolean='';pageBoolean()"
    >Clear</button>
   </div>

   <div
     id="r10BooleanValidation"
     data-testid="boolean-validation"
     class="r10-validation"
   ></div>
  </div>
 </div>

 <div id="r10BooleanResults"></div>
 </div>`;
}

function r10BooleanInsert(value){
 const el=$('#r10BooleanExpression');
 if(!el)return;

 const start=el.selectionStart??el.value.length;
 const end=el.selectionEnd??el.value.length;

 el.value=
   el.value.slice(0,start)+
   value+
   el.value.slice(end);

 SEARCH_STATE.raw_boolean=el.value;

 el.focus();

 const pos=start+value.length;
 el.setSelectionRange(pos,pos);
}

function r10BooleanExample(value){
 const el=$('#r10BooleanExpression');
 if(!el)return;

 el.value=value.trim();
 SEARCH_STATE.raw_boolean=el.value;
 el.focus();
}

async function r10ValidateBoolean(){
 const expression=$('#r10BooleanExpression')?.value.trim()||'';
 const out=$('#r10BooleanValidation');

 if(!expression){
   out.className='r10-validation bad';
   out.textContent='Enter a Boolean expression.';
   return false;
 }

 try{
   await api(
     '/api/search/boolean/validate?q='+
     encodeURIComponent(expression)
   );

   out.className='r10-validation good';
   out.textContent='Valid Boolean expression';
   return true;

 }catch(e){
   out.className='r10-validation bad';
   out.textContent='Invalid Boolean expression: '+e.message;
   return false;
 }
}

async function r10RunBooleanSearch(){
 const valid=await r10ValidateBoolean();

 if(!valid)return;

 const expression=$('#r10BooleanExpression').value.trim();

 SEARCH_STATE=SEARCH_STATE||blankSearch();
 SEARCH_STATE.raw_boolean=expression;
 SEARCH_STATE.without_mapping=
   !($('#r10BooleanMapping')?.checked);

 selectedSearch.clear();

 const payload=intentionalSearch();

 try{
   const data=await api(
     '/api/search/talent',
     {
       method:'POST',
       body:payload
     }
   );

   $('#r10BooleanResults').innerHTML=
     r10BooleanResultHTML(
       data.results||[],
       data.criteria||expression,
       data.duration_ms||0
     );

 }catch(e){
   const out=$('#r10BooleanValidation');
   out.className='r10-validation bad';
   out.textContent=e.message;
 }
}


async function pageCandidates(){const rows=await api('/api/candidates'); $('#content').innerHTML=`<div class="page">${head('Candidates','Talent Management › Search Candidates','<button class="btn primary" onclick="openCandidateForm()">+ New Candidate</button>')} ${panel('Candidate Database',`<div class="tablewrap"><table class="grid"><tr><th>Name</th><th>Title</th><th>Profession</th><th>Location</th><th>Availability</th><th>Pay</th><th>Source</th><th>Status</th></tr>${rows.map(c=>`<tr><td><a class="link" onclick="go('candidate/${c.id}')">${esc(c.first_name+' '+c.last_name)}</a><br><small>${esc(c.email||'')}</small></td><td>${esc(c.current_title||'')}</td><td>${esc(c.profession||'')}<br><small>${esc(c.specialty||'')}</small></td><td>${esc([c.city,c.state,c.country].filter(Boolean).join(', '))}</td><td>${fmtDate(c.availability_date)}</td><td>${money(c.pay_min)}–${money(c.pay_max)}/${esc(c.desired_rate_type)}</td><td>${esc(c.source||'')}</td><td>${status(c.status)}</td></tr>`).join('')}</table></div>`)}</div>`}
function openCandidateForm(){modal('New Candidate',`<form id="candForm"><div class="formgrid">${formFields([{name:'first_name',label:'First Name',required:true},{name:'last_name',label:'Last Name',required:true},{name:'email',label:'Email'},{name:'phone',label:'Phone'},{name:'current_title',label:'Current Title'},{name:'profession',label:'Profession'},{name:'specialty',label:'Specialty'},{name:'city',label:'City'},{name:'state',label:'State'},{name:'country',label:'Country',value:'USA'},{name:'zip',label:'Postal Code'},{name:'availability_date',label:'Available Date',type:'date'},{name:'source',label:'Source',value:'Manual'},{name:'resume_text',label:'Resume / Profile Text',type:'textarea',span:true}])}</div><button type="button" class="btn small" onclick="previewResumeParse()">Parse resume for recruiter review</button><div id="parseReview"></div></form>`,`<button class="btn" onclick="closeModal()">Cancel</button><button class="btn primary" onclick="submitCandidate()">Create Candidate</button>`,true)}
async function previewResumeParse(){const text=$('#candForm').elements.resume_text.value;try{const parsed=await api('/api/resume/parse',{method:'POST',body:{resume_text:text}});window.PARSED_RESUME=parsed;$('#parseReview').innerHTML=`<p><b>Review required:</b> ${esc(parsed.current_title||'No title inferred')} Â· ${parsed.skills.length} skills inferred.</p><div class="codeblock">${esc(JSON.stringify(parsed.skills,null,2))}</div>`}catch(e){toast(e.message,'err')}}
async function submitCandidate(){const d=fd($('#candForm'));try{const c=await api('/api/candidates',{method:'POST',body:d});closeModal();toast('Candidate created');go('candidate/'+c.id)}catch(e){toast(e.message,'err')}}

async function pageCandidate(id){const c=await api('/api/candidates/'+id); const tabs=['Resume','Wallet','Credibility','DivaMatch','Email','Tasks','Assignment','Onboard','Calendar']; if(!tabs.includes(PROFILE_TAB))PROFILE_TAB='Resume'; let body='';
 if(PROFILE_TAB==='Resume')body=`<div class="two-col">${panel('Professional Summary',`<p>${esc(c.summary||'')}</p><div class="codeblock" style="background:#f8fafb;color:#3c505b">${esc(c.resume_text||'')}</div>`)}${panel('Skills & Experience',`${c.skills.map(s=>`<div class="kv"><b>${esc(s.skill)}</b><span>${s.years} yrs ${s.recent?'<span class="tag">Recent</span>':''}</span></div>`).join('')}<h4>Employment</h4>${c.experience.map(x=>`<div style="margin-bottom:9px"><b>${esc(x.title||'')}</b> · ${esc(x.company||'')}<br><small>${fmtDate(x.start_date)} — ${x.end_date?fmtDate(x.end_date):'Present'}</small><div>${esc(x.description||'')}</div></div>`).join('')}`)}</div>`;
 if(PROFILE_TAB==='Wallet')body=`<div class="three-col">${panel('Licenses',c.licenses.length?c.licenses.map(x=>`<div class="kv"><b>${esc(x.license_type)}</b><span>${esc(x.state)} · ${status(x.status)}<br>Exp ${fmtDate(x.expiry_date)}</span></div>`).join(''):'No licenses')}${panel('Certifications',c.certifications.length?c.certifications.map(x=>`<div class="kv"><b>${esc(x.name)}</b><span>${status(x.status)} · Exp ${fmtDate(x.expiry_date)}</span></div>`).join(''):'No certifications')}${panel('Qualifications & Attributes',c.qualifications.map(x=>tag(`${x.value} ${x.sub_value||''}`)).join('')+'<hr>'+c.attributes.map(x=>tag(x.attribute)).join(''))}</div>${panel('Documents',`<table class="grid"><tr><th>Type</th><th>Name</th><th>Status</th><th>Expiry</th></tr>${c.documents.map(x=>`<tr><td>${x.doc_type}</td><td>${esc(x.name)}</td><td>${status(x.status)}</td><td>${fmtDate(x.expiry_date)}</td></tr>`).join('')}</table>`)}`;
 if(PROFILE_TAB==='Credibility')body=`<div class="two-col">${panel('Candidate Credibility',`<div style="font-size:44px;color:#4aa3d1">${c.credibility_score}/100</div><div class="progress"><i style="width:${c.credibility_score}%"></i></div><p>Profile completeness, verified credentials, history and communication signals are represented in this local scoring model.</p>`)}${panel('Controls',`<div class="kv"><b>SMS consent</b><span>${c.consent_sms?'Yes':'No'}</span></div><div class="kv"><b>Email consent</b><span>${c.consent_email?'Yes':'No'}</span></div><div class="kv"><b>Do Not Contact</b><span>${c.do_not_contact?'Yes':'No'}</span></div><div class="kv"><b>Source</b><span>${esc(c.source||'')}</span></div>`)}</div>`;
 if(PROFILE_TAB==='DivaMatch')body=`<div id="matchPane">Calculating job matches…</div>`;
 if(PROFILE_TAB==='Email')body=`${panel('Communication History',`<table class="grid"><tr><th>Date</th><th>Channel</th><th>Direction</th><th>Subject</th><th>Status</th></tr>${c.communications.map(x=>`<tr><td>${fmtDate(x.created_at)}</td><td>${x.channel}</td><td>${x.direction}</td><td>${esc(x.subject)}</td><td>${status(x.status)}</td></tr>`).join('')}</table>`, '<button class="btn small" onclick="sendCandidateEmail('+c.id+')">+ Email / SMS</button>')}`;
 if(PROFILE_TAB==='Tasks')body=panel('Candidate Tasks & Notes',`<div class="two-col"><div><h4>Tasks</h4>${c.tasks.map(x=>`<div class="kv"><b>${esc(x.title)}</b><span>${fmtDate(x.due_at)} · ${status(x.status)}</span></div>`).join('')||'No tasks'}</div><div><h4>Notes</h4>${c.notes.map(x=>`<div style="border-bottom:1px solid #e5ecef;padding:6px 0"><b>${esc(x.user_name||'')}</b> <small>${fmtDate(x.created_at)}</small><br>${esc(x.note)}</div>`).join('')||'No notes'}<button class="btn small" style="margin-top:8px" onclick="addCandidateNote(${c.id})">+ Note</button></div></div>`);
 if(PROFILE_TAB==='Assignment')body=panel('Assignment History',`<table class="grid"><tr><th>Job</th><th>Company</th><th>Status</th><th>Start</th><th>End</th><th>Bill / Pay</th></tr>${c.assignments.map(x=>`<tr><td>${x.job_no} · ${esc(x.job_title)}</td><td>${esc(x.company_name||'')}</td><td>${status(x.status)}</td><td>${fmtDate(x.start_date)}</td><td>${fmtDate(x.end_date)}</td><td>${money(x.bill_rate)} / ${money(x.pay_rate)}</td></tr>`).join('')}</table>`);
 if(PROFILE_TAB==='Onboard')body=panel('Onboarding Packages',`<table class="grid"><tr><th>Package</th><th>Job</th><th>Due</th><th>Status</th></tr>${c.onboarding.map(x=>`<tr><td>${esc(x.package_name)}</td><td>${esc(x.job_no||'')} ${esc(x.job_title||'')}</td><td>${fmtDate(x.due_date)}</td><td>${status(x.status)}</td></tr>`).join('')}</table>`);
 if(PROFILE_TAB==='Calendar')body=panel('Interview / Calendar Activity',`<p class="subtle">Candidate interview schedule is linked through submissions.</p><button class="btn" onclick="go('interviews')">Open Interview Calendar</button>`);
 $('#content').innerHTML=`<div class="page">${head('Candidate Profile','Talent Management › Candidate','<button class="btn" onclick="addCandidateNote('+c.id+')">+ Note</button><button class="btn" onclick="candidateHotlist('+c.id+')">🔥 Hotlist</button><button class="btn primary" onclick="sendCandidateEmail('+c.id+')">✉ Contact</button>')}<div class="profile-head"><div><div class="profile-name">${esc(c.first_name+' '+c.last_name)}</div><div class="profile-meta"><span>📞 ${esc(c.phone||'')}</span><span>✉ ${esc(c.email||'')}</span><span>📍 ${esc([c.city,c.state,c.country].filter(Boolean).join(', '))}</span><span>💼 ${esc(c.current_title||'')}</span></div></div><div class="profile-score"><strong>${c.credibility_score}</strong><span>Credibility</span></div></div><div class="tabs">${tabs.map(t=>`<div class="tabbtn ${PROFILE_TAB===t?'active':''}" onclick="PROFILE_TAB='${t}';pageCandidate(${c.id})">${t}</div>`).join('')}</div><div style="margin-top:12px">${body}</div></div>`; if(PROFILE_TAB==='DivaMatch')renderMatch(c)}
async function renderMatch(c){const jobs=await api('/api/jobs');const skills=Object.fromEntries(c.skills.map(s=>[s.skill.toLowerCase(),+s.years]));const scored=jobs.filter(j=>j.status==='Open').map(j=>{const req=(j.required_skills||'').split('|').filter(Boolean);let got=0;req.forEach(r=>{const [term,yrs]=r.split(':');const y=Object.entries(skills).find(([k])=>k.includes(term.toLowerCase())||term.toLowerCase().includes(k))?.[1]||0;if(y>=+(yrs||0))got++});return {...j,score:req.length?Math.round(got/req.length*100):50}}).sort((a,b)=>b.score-a.score);$('#matchPane').innerHTML=panel('DivaMatch-style Job Matches',`<table class="grid"><tr><th>Job</th><th>Client</th><th>Location</th><th>Match</th><th></th></tr>${scored.map(j=>`<tr><td><a class="link" onclick="go('job/${j.id}')">${j.job_no} · ${esc(j.title)}</a></td><td>${esc(j.company_name||'')}</td><td>${esc([j.city,j.state].filter(Boolean).join(', '))}</td><td class="score">${j.score}%</td><td><button class="btn small" onclick="markInterested(${j.id},${c.id})">Interested</button></td></tr>`).join('')}</table>`)}
async function addCandidateNote(cid){const n=prompt('Candidate note:');if(!n)return;await api(`/api/candidates/${cid}/notes`,{method:'POST',body:{note:n}});toast('Note added');pageCandidate(cid)}
async function candidateHotlist(cid){const hs=await api('/api/hotlists');modal('Add Candidate to Hotlist',`<select id="oneHot">${hs.map(h=>`<option value="${h.id}">${esc(h.name)}</option>`).join('')}</select>`,`<button class="btn primary" onclick="(async()=>{await api('/api/hotlists/'+document.getElementById('oneHot').value+'/members',{method:'POST',body:{candidate_id:${cid}}});closeModal();toast('Added to hotlist')})()">Add</button>`)}
function sendCandidateEmail(cid){modal('Email / SMS Candidate',`<form id="commForm"><div class="formgrid">${formFields([{name:'channel',label:'Channel',type:'select',options:['Email','SMS','Phone']},{name:'subject',label:'Subject',value:'Recruiting follow-up'},{name:'body',label:'Message',type:'textarea',span:true,value:'Hello, I wanted to follow up regarding your opportunities.'}])}</div></form>`,`<button class="btn" onclick="closeModal()">Cancel</button><button class="btn primary" onclick="submitComm(${cid})">Send / Log</button>`)}
async function submitComm(cid){const d=fd($('#commForm'));await api('/api/communications',{method:'POST',body:{entity_type:'candidate',entity_id:cid,channel:d.channel,direction:'Outbound',subject:d.subject,body:d.body,status:'Sent'}});closeModal();toast('Communication logged')}
async function markInterested(jid,cid){await api(`/api/jobs/${jid}/interested`,{method:'POST',body:{candidate_id:cid,status:'interested',source:'DivaMatch'}});toast('Candidate marked interested for job')}
function openStructuredCandidate(cid){modal('Add Structured Candidate Record',`<form id="structuredForm"><div class="formgrid">${formFields([{name:'section',label:'Record Type',type:'select',options:['skills','experience','licenses','certifications','qualifications','attributes']},{name:'name',label:'Name / Skill / Title',required:true},{name:'value',label:'Value / Company'},{name:'years',label:'Years',type:'number'},{name:'state',label:'State'},{name:'expiry_date',label:'Expiry',type:'date'}])}</div></form>`,`<button class="btn" onclick="closeModal()">Cancel</button><button class="btn primary" onclick="submitStructuredCandidate(${cid})">Add</button>`)}
async function submitStructuredCandidate(cid){const d=fd($('#structuredForm')),section=d.section;let body=section==='skills'?{skill:d.name,years:d.years,recent:true}:section==='experience'?{title:d.name,company:d.value}:section==='licenses'?{license_type:d.name,state:d.state,status:'Active',expiry_date:d.expiry_date,documented:true}:section==='certifications'?{name:d.name,status:'Active',expiry_date:d.expiry_date,documented:true}:section==='qualifications'?{name:d.name,value:d.value}:{attribute:d.name,value:d.value};await api(`/api/candidates/${cid}/${section}`,{method:'POST',body});closeModal();toast('Structured record added');pageCandidate(cid)}
function uploadCandidateDocument(cid){modal('Upload Candidate Document',`<form id="docForm"><div class="formgrid">${formFields([{name:'doc_type',label:'Type',value:'Resume'},{name:'name',label:'Display Name',required:true},{name:'expiry_date',label:'Expiry',type:'date'},{name:'file',label:'File',type:'file'}])}</div></form>`,`<button class="btn" onclick="closeModal()">Cancel</button><button class="btn primary" onclick="submitCandidateDocument(${cid})">Upload</button>`)}
async function submitCandidateDocument(cid){const form=$('#docForm'),file=form.elements.file.files[0];if(!file)return toast('Choose a file','err');const content=await new Promise((ok,fail)=>{const r=new FileReader();r.onload=()=>ok(String(r.result).split(',')[1]);r.onerror=fail;r.readAsDataURL(file)});await api(`/api/candidates/${cid}/documents`,{method:'POST',body:{doc_type:form.elements.doc_type.value,name:form.elements.name.value||file.name,file_name:file.name,mime_type:file.type,expiry_date:form.elements.expiry_date.value,content_base64:content}});closeModal();toast('Document uploaded');pageCandidate(cid)}
async function archiveCandidate(cid){if(!confirm('Archive this candidate?'))return;await api(`/api/candidates/${cid}`,{method:'DELETE'});toast('Candidate archived');go('candidates')}
async function renderMatch(c){const data=await api(`/api/candidates/${c.id}/matches`);const scored=data.results||[];$('#matchPane').innerHTML=panel('Shared-Engine Job Matches',`<table class="grid"><tr><th>Job</th><th>Location</th><th>Match</th><th>Reasons</th><th></th></tr>${scored.map(j=>`<tr><td><a class="link" onclick="go('job/${j.id}')">${j.job_no} Â· ${esc(j.title)}</a></td><td>${esc([j.city,j.state].filter(Boolean).join(', '))}</td><td class="score">${j.relevance}%</td><td>${esc((j.match_reasons||[]).map(x=>x.term||x.type).join(', '))}</td><td><button class="btn small" onclick="markInterested(${j.id},${c.id})">Interested</button></td></tr>`).join('')}</table>`)}

async function pageHotlists(){const hs=await api('/api/hotlists');$('#content').innerHTML=`<div class="page">${head('Candidate Hotlists / Talent Pools','Talent Management › Hotlists','<button class="btn primary" onclick="newHotlist()">+ New Hotlist</button>')}<div class="three-col">${hs.map(h=>`<div class="panel"><div class="panel-title"><span>🔥 ${esc(h.name)}</span>${status(h.mode)}</div><div class="panel-body"><p>${esc(h.description||'')}</p><div class="bigstat">${h.member_count}</div><small>${h.mode==='dynamic'?'saved search':'static members'}</small><hr><button class="btn small" onclick="viewHotlist(${h.id})">Open Pool</button> <button class="btn small" onclick="editHotlist(${h.id})">Edit</button> <button class="btn small" onclick="archiveHotlist(${h.id})">Archive</button></div></div>`).join('')}</div></div>`}
function newHotlist(){modal('New Hotlist / Talent Pool',`<form id="hotForm"><div class="formgrid">${formFields([{name:'name',label:'Name',required:true},{name:'visibility',label:'Visibility',type:'select',options:['Team','Private','Company']},{name:'mode',label:'Mode',type:'select',options:['static','dynamic']},{name:'description',label:'Description',type:'textarea',span:true}])}</div></form>`,`<button class="btn" onclick="closeModal()">Cancel</button><button class="btn primary" onclick="submitHotlist()">Create</button>`)}
async function submitHotlist(){const d=fd($('#hotForm'));await api('/api/hotlists',{method:'POST',body:d});closeModal();toast('Hotlist created');pageHotlists()}
async function viewHotlist(id){const h=await api('/api/hotlists/'+id);const dynamic=h.mode==='dynamic',rows=dynamic?(h.dynamic_results||[]):h.members;modal(`🔥 ${esc(h.name)}`,`<p>${esc(h.description||'')}</p><div class="tablewrap"><table class="grid"><tr><th>Name</th><th>Title</th><th>Location</th><th>Status / Relevance</th>${dynamic?'':'<th>Action</th>'}</tr>${rows.map(c=>`<tr><td><a class="link" onclick="closeModal();go('candidate/${c.candidate_id||c.id}')">${esc((c.first_name||'')+' '+(c.last_name||''))}</a></td><td>${esc(c.current_title||'')}</td><td>${esc([c.city,c.state].filter(Boolean).join(', '))}</td><td>${c.relevance?c.relevance+'%':status(c.status||'Active')}</td>${dynamic?'':`<td><button class="btn small" onclick="removeHotlistMember(${id},${c.candidate_id})">Remove</button></td>`}</tr>`).join('')}</table></div>`,`<button class="btn" onclick="closeModal()">Close</button>`,true)}
async function editHotlist(id){const h=await api('/api/hotlists/'+id);modal('Edit Hotlist / Talent Pool',`<form id="hotEditForm"><div class="formgrid">${formFields([{name:'name',label:'Name',required:true,value:h.name},{name:'visibility',label:'Visibility',type:'select',options:['Team','Private','Company'],value:h.visibility},{name:'description',label:'Description',type:'textarea',span:true,value:h.description||''}])}</div></form>`,`<button class="btn" onclick="closeModal()">Cancel</button><button class="btn primary" onclick="saveHotlist(${id})">Save</button>`)}
async function saveHotlist(id){await api('/api/hotlists/'+id,{method:'PATCH',body:fd($('#hotEditForm'))});closeModal();toast('Hotlist updated');pageHotlists()}
async function removeHotlistMember(hid,cid){if(!confirm('Remove this candidate from the hotlist?'))return;await api(`/api/hotlists/${hid}/members/${cid}`,{method:'DELETE'});toast('Candidate removed');viewHotlist(hid)}
async function archiveHotlist(id){if(!confirm('Archive this hotlist?'))return;await api('/api/hotlists/'+id,{method:'DELETE'});toast('Hotlist archived');pageHotlists()}

async function pageJobs(){const [rows,dist]=await Promise.all([api('/api/jobs'),api('/api/job-distribution')]);$('#content').innerHTML=`<div class="page">${head('Jobs','Job Management › My Jobs','<button class="btn primary" onclick="openJobForm()">+ New Job</button>')} ${panel('Job Requisitions',`<div class="tablewrap"><table class="grid"><tr><th>Job #</th><th>Title</th><th>Client</th><th>Priority</th><th>Status</th><th>Openings</th><th>Interested</th><th>Submittals</th><th>Primary Recruiter</th></tr>${rows.map(j=>`<tr><td><a class="link" onclick="go('job/${j.id}')">${j.job_no}</a></td><td>${esc(j.title)}</td><td>${esc(j.company_name||'')}</td><td>${status(j.priority)}</td><td>${status(j.status)}</td><td>${j.filled}/${j.openings}</td><td>${j.interested_count}</td><td>${j.submission_count}</td><td>${esc(j.recruiter_name||'')}</td></tr>`).join('')}</table></div>`)}${panel('Job Distribution / Posting Channels',`<table class="grid"><tr><th>Job</th><th>Channel</th><th>External Post ID</th><th>Status</th><th>Applications</th><th>Last Sync</th></tr>${dist.map(x=>`<tr><td>${x.job_no} · ${esc(x.job_title)}</td><td>${esc(x.channel)}</td><td class="mono">${esc(x.external_post_id||'')}</td><td>${status(x.status)}</td><td>${x.applications}</td><td>${fmtDate(x.last_sync)}</td></tr>`).join('')}</table>`)}</div>`}
function openJobForm(){modal('New Job Requisition',`<form id="jobForm"><div class="formgrid">${formFields([{name:'title',label:'Job Title',required:true},{name:'company_id',label:'Company',type:'select',options:REF.companies.map(x=>({value:x.id,label:x.name}))},{name:'contact_id',label:'Hiring Manager',type:'select',options:REF.contacts.map(x=>({value:x.id,label:x.name}))},{name:'priority',label:'Priority',type:'select',options:['Normal','High','Urgent']},{name:'position_type',label:'Position Type',type:'select',options:['Contract','Contract-to-Hire','Direct Hire','Per Diem']},{name:'work_mode',label:'Work Mode',type:'select',options:['Onsite','Hybrid','Remote']},{name:'city',label:'City'},{name:'state',label:'State'},{name:'profession',label:'Profession'},{name:'specialty',label:'Specialty'},{name:'pay_min',label:'Pay Min',type:'number'},{name:'pay_max',label:'Pay Max',type:'number'},{name:'bill_min',label:'Bill Min',type:'number'},{name:'bill_max',label:'Bill Max',type:'number'},{name:'required_skills',label:'Required skills mapping',span:true,placeholder:'Java:5:recent|Kafka:2:false'},{name:'description',label:'Description',type:'textarea',span:true}])}</div></form>`,`<button class="btn" onclick="closeModal()">Cancel</button><button class="btn primary" onclick="submitJob()">Create Job</button>`,true)}
async function submitJob(){const d=fd($('#jobForm'));try{const j=await api('/api/jobs',{method:'POST',body:d});closeModal();toast('Job created');REF=await api('/api/reference');go('job/'+j.id)}catch(e){toast(e.message,'err')}}
async function pageJob(id){
 const j=await api('/api/jobs/'+id);
 const overview=`<div class="kv"><b>Client</b><span>${esc(j.company_name||'')}</span></div>
 <div class="kv"><b>Hiring Manager</b><span>${esc(j.contact_name||'')}</span></div>
 <div class="kv"><b>Status / Priority</b><span>${status(j.status)} ${status(j.priority)}</span></div>
 <div class="kv"><b>Type / Mode</b><span>${esc(j.position_type)} · ${esc(j.work_mode)}</span></div>
 <div class="kv"><b>Location</b><span>${esc([j.city,j.state,j.country].filter(Boolean).join(', '))}</span></div>
 <div class="kv"><b>Pay</b><span>${money(j.pay_min)}–${money(j.pay_max)} / ${j.rate_type}</span></div>
 <div class="kv"><b>Bill</b><span>${money(j.bill_min)}–${money(j.bill_max)} / ${j.rate_type}</span></div>
 <div class="kv"><b>Openings</b><span>${j.filled}/${j.openings} filled</span></div>`;
 const req=`<p><b>${esc(j.profession||'')} ${esc(j.specialty||'')}</b></p><p>${(j.required_skills||'').split('|').filter(Boolean).map(tag).join(' ')}</p>
 <div class="kv"><b>Qualification</b><span>${esc(j.required_qualifications||'')}</span></div>
 <div class="kv"><b>License</b><span>${esc(j.required_licenses||'')}</span></div>
 <div class="kv"><b>Certification</b><span>${esc(j.required_certifications||'')}</span></div><p>${esc(j.description||'')}</p>`;
 const guidelines=`<div class="two-col"><div><b>Inherited from Company</b><p>${esc(j.company_submission_guidelines||'None')}</p></div><div><b>Job Override</b><p>${esc(j.submission_guidelines_override||'No override — company rules apply')}</p></div></div>`;
 const interested=`<table class="grid"><tr><th>Candidate</th><th>Status</th><th>Source</th><th></th></tr>${j.interested.map(x=>`<tr><td><a class="link" onclick="go('candidate/${x.candidate_id}')">${esc(x.first_name+' '+x.last_name)}</a><br><small>${esc(x.current_title||'')}</small></td><td>${status(x.status)}</td><td>${esc(x.source||'')}</td><td><button class="btn small" onclick="quickSubmit(${j.id},${x.candidate_id})">Submit</button></td></tr>`).join('')}</table>`;
 const submissions=`<table class="grid"><tr><th>Candidate</th><th>Status</th><th>RTR</th><th>Compliance</th><th>Rate</th></tr>${j.submissions.map(x=>`<tr><td><a class="link" onclick="go('candidate/${x.candidate_id}')">${esc(x.first_name+' '+x.last_name)}</a></td><td>${status(x.status)}</td><td>${status(x.rtr_status)}</td><td>${status(x.compliance_status)}</td><td>${money(x.client_rate)}</td></tr>`).join('')}</table>`;
 const suppliers=j.supplier_releases.length?panel('Supplier Releases',j.supplier_releases.map(x=>`<div class="kv"><b>${esc(x.supplier_name)}</b><span>${status(x.status)} · max ${x.max_submissions} submissions</span></div>`).join('')):'';
 const actions=`<button class="btn" onclick="openJobSearch(${j.id})">Find Candidates</button><button class="btn primary" onclick="jobAddSubmission(${j.id})">+ Submittal</button>`;
 $('#content').innerHTML=`<div class="page">${head(`${j.job_no} — ${esc(j.title)}`,'Job Management › Job Detail',actions)}<div class="two-col">${panel('Job Overview',overview)}${panel('Requirements',req)}</div>${panel('Candidate Submittal Guidelines',guidelines)}<div class="two-col">${panel(`Interested / Qualified (${j.interested.length})`,interested)}${panel(`Submittals (${j.submissions.length})`,submissions)}</div>${suppliers}</div>`;
}
function openJobSearch(jid){SEARCH_STATE=blankSearch();const j=REF.jobs.find(x=>x.id==jid);if(j){SEARCH_STATE.title='';}go('talent')}
async function openJobSearch(jid){const criteria=await api(`/api/jobs/${jid}/search-criteria`);SEARCH_STATE={...blankSearch(),...criteria,radius:String(criteria.radius_miles||50)};delete SEARCH_STATE.radius_miles;go('talent');setTimeout(runTalentSearch,0)}
async function quickSubmit(jid,cid){const c=await api('/api/candidates/'+cid);const j=await api('/api/jobs/'+jid);modal('Create Submittal',`<form id="subForm"><p><b>${esc(c.first_name+' '+c.last_name)}</b> → <b>${esc(j.job_no+' '+j.title)}</b></p><div class="formgrid">${formFields([{name:'client_rate',label:'Client Bill Rate',value:j.bill_min||''},{name:'candidate_rate',label:'Candidate Pay Rate',value:c.pay_min||''},{name:'availability',label:'Availability',value:c.availability_date||''},{name:'rtr_status',label:'Right to Represent',type:'select',options:['Pending','Signed','Waived']},{name:'compliance_status',label:'Compliance',type:'select',options:['Pending','Complete','Blocked']},{name:'recruiter_summary',label:'Recruiter Summary',type:'textarea',span:true,value:c.summary||''}])}</div></form>`,`<button class="btn" onclick="closeModal()">Cancel</button><button class="btn primary" onclick="submitSubmittal(${jid},${cid})">Submit to Client</button>`,true)}
async function submitSubmittal(jid,cid){const d=fd($('#subForm'));d.candidate_id=cid;d.status='submitted';const s=await api(`/api/jobs/${jid}/submissions`,{method:'POST',body:d});closeModal();toast('Submittal created');pageJob(jid)}
function jobAddSubmission(jid){modal('Select Candidate',`<div class="field"><label>Candidate</label><select id="jobCand">${REF.candidates.map(c=>`<option value="${c.id}">${esc(c.name)} — ${esc(c.current_title||'')}</option>`).join('')}</select></div>`,`<button class="btn" onclick="closeModal()">Cancel</button><button class="btn primary" onclick="(async()=>{let c=+document.getElementById('jobCand').value;closeModal();quickSubmit(${jid},c)})()">Next</button>`)}

async function pageCompanies(){
 const [rows,leads,opps]=await Promise.all([api('/api/companies'),api('/api/leads'),api('/api/opportunities')]);
 const pipeline=opps.map(o=>`<tr><td>${esc(o.name)}</td><td>${esc(o.company_name||'')}</td><td>${status(o.stage)}</td><td>${money(o.value)}</td><td>${o.probability}%</td><td>${fmtDate(o.expected_close)}</td><td>${esc(o.next_activity||'')}</td></tr>`).join('');
 $('#content').innerHTML=`<div class="page">${head('Companies / CRM','CRM › Companies / Leads / Opportunities','<button class="btn" onclick="newLead()">+ Lead</button><button class="btn" onclick="newOpportunity()">+ Opportunity</button><button class="btn primary" onclick="openCompanyInfo()">+ New Company</button>')}
 ${panel('Company Database',`<table class="grid"><tr><th>Company</th><th>Type</th><th>Industry</th><th>Location</th><th>Contacts</th><th>Jobs</th><th>Terms</th><th>Status</th></tr>${rows.map(x=>`<tr><td><b>${esc(x.name)}</b><br><small>${esc(x.website||'')}</small></td><td>${esc(x.company_type)}</td><td>${esc(x.industry||'')}</td><td>${esc([x.city,x.state,x.country].filter(Boolean).join(', '))}</td><td>${x.contact_count}</td><td>${x.job_count}</td><td>${esc(x.billing_terms||'')}</td><td>${status(x.status)}</td></tr>`).join('')}</table>`)}
 <div class="two-col">${panel('Sales Opportunities',`<table class="grid"><tr><th>Opportunity</th><th>Company</th><th>Stage</th><th>Value</th><th>Prob.</th><th>Close</th><th>Next</th></tr>${pipeline}</table>`)}${panel('Leads',`<table class="grid"><tr><th>Lead</th><th>Company</th><th>Source</th><th>Status</th><th>Next Action</th></tr>${leads.map(x=>`<tr><td>${esc(x.title)}</td><td>${esc(x.company_name||'')}</td><td>${esc(x.source||'')}</td><td>${status(x.status)}</td><td>${esc(x.next_action||'')}<br><small>${fmtDate(x.next_action_at)}</small></td></tr>`).join('')}</table>`)}</div></div>`;
}
function openCompanyInfo(){modal('New Company',`<form id="companyForm"><div class="formgrid">${formFields([{name:'name',label:'Company Name',required:true},{name:'company_type',label:'Type',type:'select',options:['Client','Prospect','MSP','Vendor']},{name:'industry',label:'Industry'},{name:'website',label:'Website'},{name:'phone',label:'Phone'},{name:'billing_terms',label:'Billing Terms',value:'Net 30'},{name:'city',label:'City'},{name:'state',label:'State'},{name:'country',label:'Country',value:'USA'},{name:'submission_guidelines',label:'Candidate Submittal Guidelines',type:'textarea',span:true},{name:'discount_rule',label:'Discount / Rate Rule',span:true},{name:'notes',label:'Notes',type:'textarea',span:true}])}</div></form>`,`<button class="btn" onclick="closeModal()">Cancel</button><button class="btn primary" onclick="submitCompany()">Create Company</button>`,true)}
async function submitCompany(){try{await api('/api/companies',{method:'POST',body:fd($('#companyForm'))});closeModal();REF=await api('/api/reference');toast('Company created');pageCompanies()}catch(e){toast(e.message,'err')}}
function newLead(){modal('New Sales Lead',`<form id="leadForm"><div class="formgrid">${formFields([{name:'company_id',label:'Company',type:'select',options:REF.companies.map(x=>({value:x.id,label:x.name}))},{name:'contact_id',label:'Contact',type:'select',options:REF.contacts.map(x=>({value:x.id,label:x.name}))},{name:'title',label:'Lead',required:true},{name:'source',label:'Source',value:'Referral'},{name:'status',label:'Status',type:'select',options:['New','Qualified','Contacted','Nurture','Closed']},{name:'next_action',label:'Next Action'},{name:'next_action_at',label:'Next Action Date',type:'date'},{name:'notes',label:'Notes',type:'textarea',span:true}])}</div></form>`,`<button class="btn" onclick="closeModal()">Cancel</button><button class="btn primary" onclick="submitLead()">Create Lead</button>`)}
async function submitLead(){await api('/api/leads',{method:'POST',body:fd($('#leadForm'))});closeModal();toast('Lead created');pageCompanies()}
function newOpportunity(){modal('New Opportunity',`<form id="oppForm"><div class="formgrid">${formFields([{name:'company_id',label:'Company',type:'select',options:REF.companies.map(x=>({value:x.id,label:x.name}))},{name:'contact_id',label:'Contact',type:'select',options:REF.contacts.map(x=>({value:x.id,label:x.name}))},{name:'name',label:'Opportunity Name',required:true},{name:'stage',label:'Stage',type:'select',options:['Lead','Qualified','Presentation','Negotiation','Won','Lost']},{name:'value',label:'Value',type:'number'},{name:'probability',label:'Probability %',type:'number',value:'25'},{name:'expected_close',label:'Expected Close',type:'date'},{name:'next_activity',label:'Next Activity'},{name:'notes',label:'Notes',type:'textarea',span:true}])}</div></form>`,`<button class="btn" onclick="closeModal()">Cancel</button><button class="btn primary" onclick="submitOpportunity()">Create Opportunity</button>`)}
async function submitOpportunity(){await api('/api/opportunities',{method:'POST',body:fd($('#oppForm'))});closeModal();toast('Opportunity created');pageCompanies()}
async function pageContacts(){const rows=await api('/api/contacts');$('#content').innerHTML=`<div class="page">${head('Contacts','CRM › Contacts','<button class="btn primary" onclick="openContactInfo()">+ New Contact</button>')}${panel('Contacts',`<table class="grid"><tr><th>Name</th><th>Company</th><th>Title</th><th>Role</th><th>Email</th><th>Phone</th><th>Status</th></tr>${rows.map(x=>`<tr><td><b>${esc(x.first_name+' '+x.last_name)}</b></td><td>${esc(x.company_name||'')}</td><td>${esc(x.title||'')}</td><td>${esc(x.role_type||'')}</td><td>${esc(x.email||'')}</td><td>${esc(x.phone||'')}</td><td>${status(x.status)}</td></tr>`).join('')}</table>`)}</div>`}
function openContactInfo(){modal('New Contact',`<form id="contactForm"><div class="formgrid">${formFields([{name:'company_id',label:'Company',type:'select',options:REF.companies.map(x=>({value:x.id,label:x.name}))},{name:'role_type',label:'Role',type:'select',options:['Hiring Manager','Timesheet Approver','MSP Contact','Billing Contact','HR Contact']},{name:'first_name',label:'First Name',required:true},{name:'last_name',label:'Last Name',required:true},{name:'title',label:'Title'},{name:'email',label:'Email'},{name:'phone',label:'Phone'},{name:'notes',label:'Notes',type:'textarea',span:true}])}</div></form>`,`<button class="btn" onclick="closeModal()">Cancel</button><button class="btn primary" onclick="submitContact()">Create Contact</button>`)}
async function submitContact(){await api('/api/contacts',{method:'POST',body:fd($('#contactForm'))});closeModal();REF=await api('/api/reference');toast('Contact created');pageContacts()}

async function pageSubmissions(){const rows=await api('/api/submissions');$('#content').innerHTML=`<div class="page">${head('Candidate Submittals','Recruiting › Submittals')}${panel('Submittal Pipeline',`<table class="grid"><tr><th>Candidate</th><th>Job</th><th>Client</th><th>Status</th><th>RTR</th><th>Compliance</th><th>Bill</th><th>Pay</th><th>Action</th></tr>${rows.map(x=>`<tr><td><a class="link" onclick="go('candidate/${x.candidate_id}')">${esc(x.first_name+' '+x.last_name)}</a></td><td><a class="link" onclick="go('job/${x.job_id}')">${x.job_no} · ${esc(x.job_title)}</a></td><td>${esc(x.company_name||'')}</td><td>${status(x.status)}</td><td>${status(x.rtr_status)}</td><td>${status(x.compliance_status)}</td><td>${money(x.client_rate)}</td><td>${money(x.candidate_rate)}</td><td><button class="btn small" onclick="submissionStatus(${x.id})">Move</button> <button class="btn small" onclick="scheduleInterview(${x.id})">Interview</button></td></tr>`).join('')}</table>`)}</div>`}
function submissionStatus(id){const opts=['submitted','client_review','interview','offer','hired','rejected','withdrawn'];modal('Update Submittal Status',`<select id="subStatus">${opts.map(x=>`<option>${x}</option>`).join('')}</select><div class="field"><label>Client feedback</label><textarea id="subFeedback" rows="3"></textarea></div>`,`<button class="btn" onclick="closeModal()">Cancel</button><button class="btn primary" onclick="doSubmissionStatus(${id})">Update</button>`)}
async function doSubmissionStatus(id){await api(`/api/submissions/${id}/status`,{method:'POST',body:{status:$('#subStatus').value,client_feedback:$('#subFeedback').value}});closeModal();toast('Status updated');pageSubmissions()}
function scheduleInterview(sid){modal('Schedule Interview',`<form id="intForm"><div class="formgrid">${formFields([{name:'interview_type',label:'Type',type:'select',options:['Video','Phone','Onsite','Technical','Manager']},{name:'scheduled_at',label:'Date & Time',type:'datetime-local'},{name:'timezone',label:'Timezone',value:'America/New_York'},{name:'interviewer',label:'Interviewer'},{name:'location_or_link',label:'Location / Meeting Link',span:true}])}</div></form>`,`<button class="btn" onclick="closeModal()">Cancel</button><button class="btn primary" onclick="submitInterview(${sid})">Schedule</button>`)}
async function submitInterview(sid){const d=fd($('#intForm'));d.submission_id=sid;await api('/api/interviews',{method:'POST',body:d});closeModal();toast('Interview scheduled');go('interviews')}

async function pageInterviews(){const rows=await api('/api/interviews');$('#content').innerHTML=`<div class="page">${head('Interviews & Calendar','Events & Communication › Interviews')}${panel('Interview Schedule',`<table class="grid"><tr><th>Date / Time</th><th>Candidate</th><th>Job</th><th>Client</th><th>Type</th><th>Interviewer</th><th>Status</th><th>Location / Link</th></tr>${rows.map(x=>`<tr><td>${new Date(x.scheduled_at).toLocaleString()}</td><td><a class="link" onclick="go('candidate/${x.candidate_id}')">${esc(x.first_name+' '+x.last_name)}</a></td><td>${x.job_no} · ${esc(x.job_title)}</td><td>${esc(x.company_name||'')}</td><td>${esc(x.interview_type)}</td><td>${esc(x.interviewer||'')}</td><td>${status(x.status)}</td><td>${esc(x.location_or_link||'')}</td></tr>`).join('')}</table>`)}</div>`}
async function pageAssessments(){const rows=await api('/api/assessments');$('#content').innerHTML=`<div class="page">${head('Assessments / e-Interview','Candidate Engagement › Assessments','<button class="btn primary" onclick="newAssessment()">+ Invite</button>')}${panel('Assessment Center',`<table class="grid"><tr><th>Candidate</th><th>Assessment</th><th>Job</th><th>Type</th><th>Status</th><th>Score</th><th>Invited</th></tr>${rows.map(x=>`<tr><td>${esc(x.first_name+' '+x.last_name)}</td><td>${esc(x.title)}</td><td>${esc((x.job_no||'')+' '+(x.job_title||''))}</td><td>${esc(x.assessment_type)}</td><td>${status(x.status)}</td><td>${x.score==null?'':x.score+'/'+x.max_score}</td><td>${fmtDate(x.invited_at)}</td></tr>`).join('')}</table>`)}</div>`}
function newAssessment(){modal('Invite Assessment',`<form id="assForm"><div class="formgrid">${formFields([{name:'candidate_id',label:'Candidate',type:'select',options:REF.candidates.map(x=>({value:x.id,label:x.name}))},{name:'job_id',label:'Job',type:'select',options:REF.jobs.map(x=>({value:x.id,label:x.job_no+' '+x.title}))},{name:'title',label:'Assessment Title',value:'Technical Screening'},{name:'assessment_type',label:'Type',type:'select',options:['Questionnaire','Technical','Recorded Video','Live Interview']}])}</div></form>`,`<button class="btn" onclick="closeModal()">Cancel</button><button class="btn primary" onclick="submitAssessment()">Invite</button>`)}
async function submitAssessment(){await api('/api/assessments',{method:'POST',body:fd($('#assForm'))});closeModal();toast('Assessment invited');pageAssessments()}

async function pageOnboarding(){const rows=await api('/api/onboarding');$('#content').innerHTML=`<div class="page">${head('Onboarding','Workforce › Onboarding','<button class="btn primary" onclick="newOnboarding()">+ Assign Package</button>')}${panel('Onboarding Packages',`<table class="grid"><tr><th>Candidate</th><th>Job</th><th>Package</th><th>Due</th><th>Progress</th><th>Status</th><th></th></tr>${rows.map(x=>`<tr><td>${esc(x.first_name+' '+x.last_name)}</td><td>${esc((x.job_no||'')+' '+(x.job_title||''))}</td><td>${esc(x.package_name)}</td><td>${fmtDate(x.due_date)}</td><td>${x.complete_count}/${x.req_count}</td><td>${status(x.status)}</td><td><button class="btn small" onclick="openOnboarding(${x.id})">Open</button></td></tr>`).join('')}</table>`)}</div>`}
function newOnboarding(){modal('Assign Onboarding Package',`<form id="onbForm"><div class="formgrid">${formFields([{name:'candidate_id',label:'Candidate',type:'select',options:REF.candidates.map(x=>({value:x.id,label:x.name}))},{name:'job_id',label:'Job',type:'select',options:REF.jobs.map(x=>({value:x.id,label:x.job_no+' '+x.title}))},{name:'package_name',label:'Package Name',value:'Standard Client Onboarding'},{name:'due_date',label:'Due Date',type:'date'}])}</div></form>`,`<button class="btn" onclick="closeModal()">Cancel</button><button class="btn primary" onclick="submitOnboarding()">Assign</button>`)}
async function submitOnboarding(){await api('/api/onboarding',{method:'POST',body:fd($('#onbForm'))});closeModal();toast('Onboarding package assigned');pageOnboarding()}
async function openOnboarding(id){const p=await api('/api/onboarding/'+id);modal(esc(p.package_name),`<table class="grid"><tr><th>Requirement</th><th>Type</th><th>Mandatory</th><th>Status</th><th></th></tr>${p.requirements.map(x=>`<tr><td>${esc(x.name)}</td><td>${esc(x.requirement_type)}</td><td>${x.mandatory?'Yes':'No'}</td><td>${status(x.status)}</td><td><button class="btn small" onclick="completeReq(${x.id},${p.id})">${x.status==='Complete'?'Reopen':'Complete'}</button></td></tr>`).join('')}</table>`,`<button class="btn" onclick="closeModal()">Close</button>`,true)}
async function completeReq(rid,pid){const p=await api('/api/onboarding/'+pid);const r=p.requirements.find(x=>x.id===rid);await api('/api/onboarding/requirements/'+rid+'/status',{method:'POST',body:{status:r.status==='Complete'?'Pending':'Complete'}});openOnboarding(pid)}

async function pageAssignments(){const rows=await api('/api/assignments');$('#content').innerHTML=`<div class="page">${head('Assignments','Workforce › Assignment Record')}${panel('Assignment Records',`<table class="grid"><tr><th>Worker</th><th>Job</th><th>Client</th><th>Status</th><th>Dates</th><th>Worksite</th><th>Cost Center</th><th>Approver</th><th>Bill / Pay</th><th>PO / VMS</th></tr>${rows.map(x=>`<tr><td>${esc(x.first_name+' '+x.last_name)}</td><td>${x.job_no} · ${esc(x.job_title)}</td><td>${esc(x.company_name||'')}</td><td>${status(x.status)}</td><td>${fmtDate(x.start_date)}<br>${fmtDate(x.end_date)}</td><td>${esc(x.worksite||'')}</td><td>${esc(x.cost_center||'')}</td><td>${esc(x.approver_name||'')}</td><td>${money(x.bill_rate)}<br>${money(x.pay_rate)}</td><td>${esc(x.po_number||'')}<br>${esc(x.vms_id||'')}</td></tr>`).join('')}</table>`)}</div>`}
async function pageTimesheets(){const rows=await api('/api/timesheets');$('#content').innerHTML=`<div class="page">${head('Timesheets','Back Office › Time & Attendance')}${panel('Timesheets',`<table class="grid"><tr><th>Worker</th><th>Assignment / Job</th><th>Week</th><th>Hours</th><th>OT</th><th>Status</th><th>Bill Value</th><th>Pay Value</th><th>Action</th></tr>${rows.map(x=>`<tr><td>${esc(x.first_name+' '+x.last_name)}</td><td>${esc(x.job_title)}</td><td>${fmtDate(x.week_start)}</td><td>${x.total_hours}</td><td>${x.overtime_hours}</td><td>${status(x.status)}</td><td>${money(x.total_hours*x.bill_rate)}</td><td>${money(x.total_hours*x.pay_rate)}</td><td>${x.status==='submitted'?`<button class="btn small success" onclick="timeStatus(${x.id},'approved')">Approve</button> <button class="btn small danger" onclick="timeStatus(${x.id},'rejected')">Reject</button>`:''}</td></tr>`).join('')}</table>`)}</div>`}
async function timeStatus(id,s){try{await api(`/api/timesheets/${id}/status`,{method:'POST',body:{status:s,rejection_note:s==='rejected'?'Rejected by user':''}});toast('Timesheet '+s);pageTimesheets()}catch(e){toast(e.message,'err')}}
async function pageExpenses(){const rows=await api('/api/expenses');$('#content').innerHTML=`<div class="page">${head('Expenses','Back Office › Expenses')}${panel('Expense Claims',`<table class="grid"><tr><th>Worker</th><th>Date</th><th>Client / Job</th><th>Category</th><th>Amount</th><th>Receipt</th><th>Status</th><th>Action</th></tr>${rows.map(x=>`<tr><td>${esc(x.first_name+' '+x.last_name)}</td><td>${fmtDate(x.expense_date)}</td><td>${esc(x.company_name||'')}<br>${esc(x.job_title||'')}</td><td>${esc(x.category)}</td><td>${money(x.amount)}</td><td>${esc(x.receipt_ref||'')}</td><td>${status(x.status)}</td><td>${x.status==='submitted'?`<button class="btn small success" onclick="expenseStatus(${x.id},'approved')">Approve</button> <button class="btn small danger" onclick="expenseStatus(${x.id},'rejected')">Reject</button>`:''}</td></tr>`).join('')}</table>`)}</div>`}
async function expenseStatus(id,s){try{await api(`/api/expenses/${id}/status`,{method:'POST',body:{status:s,rejection_note:s==='rejected'?'Rejected by user':''}});toast('Expense '+s);pageExpenses()}catch(e){toast(e.message,'err')}}

async function pageFinance(){const [inv,po,as]=await Promise.all([api('/api/invoices'),api('/api/purchase-orders'),api('/api/assignments')]);$('#content').innerHTML=`<div class="page">${head('DivaFinancials-style Back Office','Finance › Billing / Payroll','<button class="btn primary" onclick="newInvoice()">+ Invoice</button>')}<div class="two-col">${panel('Invoices',`<table class="grid"><tr><th>Invoice</th><th>Client</th><th>Worker</th><th>Period</th><th>Amount</th><th>Status</th><th>Due</th></tr>${inv.map(x=>`<tr><td>${esc(x.invoice_no)}</td><td>${esc(x.company_name||'')}</td><td>${esc((x.first_name||'')+' '+(x.last_name||''))}</td><td>${fmtDate(x.period_start)}—${fmtDate(x.period_end)}</td><td>${money(x.amount+x.tax)}</td><td>${status(x.status)}</td><td>${fmtDate(x.due_date)}</td></tr>`).join('')}</table>`)}${panel('Purchase Orders / SOW Funding',`<table class="grid"><tr><th>PO</th><th>Client</th><th>Job</th><th>Amount</th><th>Dates</th><th>Status</th></tr>${po.map(x=>`<tr><td>${esc(x.po_number)}</td><td>${esc(x.company_name||'')}</td><td>${esc(x.job_no||'')} ${esc(x.job_title||'')}</td><td>${money(x.amount)}</td><td>${fmtDate(x.start_date)}—${fmtDate(x.end_date)}</td><td>${status(x.status)}</td></tr>`).join('')}</table>`)}</div>${panel('Assignment Margin / Spread',`<table class="grid"><tr><th>Worker</th><th>Job</th><th>Bill</th><th>Pay</th><th>Gross Spread</th><th>Margin %</th></tr>${as.map(x=>{const spread=(x.bill_rate||0)-(x.pay_rate||0),m=x.bill_rate?spread/x.bill_rate*100:0;return`<tr><td>${esc(x.first_name+' '+x.last_name)}</td><td>${esc(x.job_title)}</td><td>${money(x.bill_rate)}</td><td>${money(x.pay_rate)}</td><td>${money(spread)}</td><td>${m.toFixed(1)}%</td></tr>`}).join('')}</table>`)}</div>`}
function newInvoice(){modal('Create Invoice',`<form id="invForm"><div class="formgrid">${formFields([{name:'company_id',label:'Client',type:'select',options:REF.companies.map(x=>({value:x.id,label:x.name}))},{name:'assignment_id',label:'Assignment ID',value:'1'},{name:'period_start',label:'Period Start',type:'date'},{name:'period_end',label:'Period End',type:'date'},{name:'amount',label:'Amount',type:'number'},{name:'tax',label:'Tax',type:'number',value:'0'},{name:'status',label:'Status',type:'select',options:['draft','issued']},{name:'due_date',label:'Due Date',type:'date'}])}</div></form>`,`<button class="btn" onclick="closeModal()">Cancel</button><button class="btn primary" onclick="submitInvoice()">Create</button>`)}
async function submitInvoice(){await api('/api/invoices',{method:'POST',body:fd($('#invForm'))});closeModal();toast('Invoice created');pageFinance()}

async function pageVMS(){const [d,connectors]=await Promise.all([api('/api/vms'),api('/api/integrations')]);$('#content').innerHTML=`<div class="page">${head('VMS / MSP Synchronization','Integrations › VMS')}${panel('VMS Accounts',`<table class="grid"><tr><th>Account</th><th>Platform</th><th>Status</th><th>Mode</th><th>Last Sync</th><th>Notes</th></tr>${d.accounts.map(x=>`<tr><td><b>${esc(x.name)}</b></td><td>${esc(x.platform)}</td><td>${status(x.status)}</td><td>${status(x.sync_mode)}</td><td>${fmtDate(x.last_sync)}</td><td>${esc(x.notes||'')}</td></tr>`).join('')}</table>`)}${panel('Systematic Object Mapping',`<table class="grid"><tr><th>Account</th><th>Object</th><th>External ID</th><th>Internal ID</th><th>External Status</th><th>Internal Status</th><th>Mapping</th></tr>${d.mappings.map(x=>`<tr><td>${esc(x.account_name||'')}</td><td>${esc(x.object_type)}</td><td class="mono">${esc(x.external_id)}</td><td>${x.internal_id}</td><td>${status(x.external_status)}</td><td>${status(x.internal_status)}</td><td class="mono">${esc(x.mapping_json)}</td></tr>`).join('')}</table>`)}${panel('Integration Registry',`<table class="grid"><tr><th>Category</th><th>Connector</th><th>Mode</th><th>Status</th><th>Last Sync</th><th>Notes</th></tr>${connectors.map(x=>`<tr><td>${esc(x.category)}</td><td>${esc(x.name)}</td><td>${status(x.mode)}</td><td>${status(x.status)}</td><td>${fmtDate(x.last_sync)}</td><td>${esc(x.notes||'')}</td></tr>`).join('')}</table>`)}<div class="panel"><div class="panel-title">Supported Mapping Chain</div><div class="panel-body codeblock">External VMS Account ⇄ Internal Company\nExternal Requisition ⇄ Internal Job\nExternal Submission ⇄ Internal Submittal\nExternal Worker ⇄ Candidate / Employee\nExternal Assignment ⇄ Assignment\nExternal Timecard ⇄ Timesheet\nExternal Expense ⇄ Expense\nExternal SOW / PO ⇄ Financial Objects\nExternal Status ⇄ Configurable Internal Status</div></div></div>`}
async function pageSuppliers(){const rows=await api('/api/suppliers');$('#content').innerHTML=`<div class="page">${head('Supplier Management','MSP › Suppliers')}${panel('Supplier Network',`<table class="grid"><tr><th>Supplier</th><th>Contact</th><th>Email</th><th>Tier</th><th>Released Jobs</th><th>Status</th><th>Notes</th></tr>${rows.map(x=>`<tr><td><b>${esc(x.name)}</b></td><td>${esc(x.contact_name||'')}</td><td>${esc(x.email||'')}</td><td>${esc(x.tier)}</td><td>${x.released_job_count}</td><td>${status(x.status)}</td><td>${esc(x.notes||'')}</td></tr>`).join('')}</table>`)}</div>`}
async function pageCommunications(){const rows=await api('/api/communications');$('#content').innerHTML=`<div class="page">${head('Communication Center','Engagement › Email / SMS / Calls')}${panel('Activity Stream',`<table class="grid"><tr><th>Date</th><th>Entity</th><th>Channel</th><th>Direction</th><th>Subject</th><th>User</th><th>Status</th></tr>${rows.map(x=>`<tr><td>${new Date(x.created_at).toLocaleString()}</td><td>${esc(x.entity_type)} #${x.entity_id}</td><td>${esc(x.channel)}</td><td>${esc(x.direction)}</td><td>${esc(x.subject||'')}</td><td>${esc(x.user_name||'')}</td><td>${status(x.status)}</td></tr>`).join('')}</table>`)}</div>`}
async function pageReports(){const r=await api('/api/reports/summary');$('#content').innerHTML=`<div class="page">${head('Reports & BI','Reporting Tools › Reports')}<div class="three-col">${panel('Recruiting KPIs',Object.entries(r.recruiting).map(([k,v])=>`<div class="kv"><b>${esc(k.replaceAll('_',' '))}</b><span>${v}</span></div>`).join(''))}${panel('Workforce KPIs',Object.entries(r.workforce).map(([k,v])=>`<div class="kv"><b>${esc(k.replaceAll('_',' '))}</b><span>${v}</span></div>`).join(''))}${panel('Financial KPIs',Object.entries(r.finance).map(([k,v])=>`<div class="kv"><b>${esc(k.replaceAll('_',' '))}</b><span>${money(v)}</span></div>`).join(''))}</div><div class="two-col">${panel('Submittals by Status',r.submission_by_status.map(x=>`<div class="kv"><b>${esc(x.status)}</b><span>${x.count}</span></div>`).join(''))}${panel('Jobs by Company',r.jobs_by_company.map(x=>`<div class="kv"><b>${esc(x.company)}</b><span>${x.count}</span></div>`).join(''))}</div>${panel('Report Catalog',`<div class="pillbar">${['Recruiter Productivity','Time to Submit','Submittal Funnel','Interview Conversion','Starts & Placements','Candidate Source','Open Jobs Aging','Onboarding Completion','Credential Expiry','Assignment Ending','Timesheet Aging','Expense Aging','Client Revenue','Gross Margin','VMS Sync Exceptions','Supplier Performance','Audit Access'].map(tag).join('')}</div><p class="subtle">The local report service runs on the same relational data model. Additional report definitions can be added without duplicating operational data.</p>`)}</div>`}
async function pageAdmin(){const [users,cfs,autos]=await Promise.all([api('/api/users'),api('/api/custom-fields'),api('/api/automations')]);$('#content').innerHTML=`<div class="page">${head('Administration','Settings › Team / Profile / Permissions','<button class="btn primary" onclick="newUser()">+ User</button>')}<div class="two-col">${panel('Users & Roles',`<table class="grid"><tr><th>Name</th><th>Email</th><th>Role</th><th>Active</th></tr>${users.map(x=>`<tr><td>${esc(x.name)}</td><td>${esc(x.email)}</td><td>${status(x.role)}</td><td>${x.active?'Yes':'No'}</td></tr>`).join('')}</table>`)}${panel('Feature Configuration',`<div class="pillbar">${['On-Boarding','DivaFinancials','Assignment Record','Timesheet & Expenses','Leads','Attendance Tracking','Termination','Shift Calendaring','Talent Cluster','Start Cancellation','AI Assistant','VOIP','Live Interview','VMS Sync','Supplier Portal'].map(x=>`<label class="tag"><input type="checkbox" checked> ${x}</label>`).join('')}</div><p class="subtle">Configuration UI mirrors the team-level feature enablement model. Local build keeps core modules enabled.</p>`)}</div><div class="two-col">${panel('User Defined Fields',`<table class="grid"><tr><th>Entity</th><th>Field</th><th>Type</th><th>Required</th></tr>${cfs.map(x=>`<tr><td>${x.entity_type}</td><td>${esc(x.field_name)}</td><td>${x.field_type}</td><td>${x.required?'Yes':'No'}</td></tr>`).join('')}</table>`)}${panel('Automation Rules',autos.map(x=>`<div class="kv"><b>${esc(x.name)}</b><span>${esc(x.trigger_name)} · ${x.active?'Active':'Off'}</span></div>`).join(''))}</div>${panel('Data Maintenance',`<p>The reset action restores the shared database to its original seeded state and invalidates existing sessions.</p><button class="btn danger" onclick="resetDb()">Reset Database</button>`)}</div>`}
function newUser(){modal('Create User',`<form id="userForm"><div class="formgrid">${formFields([{name:'name',label:'Name',required:true},{name:'email',label:'Email',required:true},{name:'password',label:'Password',value:'ChangeMe@123'},{name:'role',label:'Role',type:'select',options:['recruiter','teamlead','sales','hr','finance','client','candidate','worker','supplier','approver']}])}</div></form>`,`<button class="btn" onclick="closeModal()">Cancel</button><button class="btn primary" onclick="submitUser()">Create</button>`)}
async function submitUser(){await api('/api/users',{method:'POST',body:fd($('#userForm'))});closeModal();toast('User created');pageAdmin()}
async function resetDb(){if(!confirm('Reset ALL local data to seeded state?'))return;await api('/api/reset',{method:'POST'});alert('Database reset. Login again.');renderLogin()}
function enhanceR8Controls(base,id){if(!internalRoles.includes(ME.role))return;const bar=$('.pagehead .actions');if(!bar)return;const controls={candidate:`<button class="btn" onclick="openStructuredCandidate(${+id})">+ Structured Record</button><button class="btn" onclick="uploadCandidateDocument(${+id})">Upload Document</button><button class="btn danger" onclick="archiveCandidate(${+id})">Archive</button>`,job:`<button class="btn" onclick="cloneJob(${+id})">Clone</button><button class="btn" onclick="publishJob(${+id})">Publish</button><button class="btn danger" onclick="archiveJob(${+id})">Archive</button>`,assignments:'<button class="btn primary" onclick="newAssignment()">+ Assignment</button>',finance:'<button class="btn" onclick="newPurchaseOrder()">+ Purchase Order</button>',vms:'<button class="btn primary" onclick="newVMSAccount()">+ VMS Account</button>',suppliers:'<button class="btn primary" onclick="newSupplier()">+ Supplier</button>',reports:'<button class="btn" onclick="runOperationalReport()">Run Report</button><button class="btn" onclick="exportOperationalReport()">Export CSV</button>',admin:'<button class="btn" onclick="newUDF()">+ UDF</button><button class="btn" onclick="newAutomation()">+ Automation</button><button class="btn" onclick="newConnector()">+ Connector</button>'};if(controls[base])bar.insertAdjacentHTML('beforeend',controls[base])}
async function cloneJob(id){const copy=await api(`/api/jobs/${id}/clone`,{method:'POST',body:{}});toast('Job cloned');go('job/'+copy.id)}
async function publishJob(id){await api(`/api/jobs/${id}/distribution`,{method:'POST',body:{channel:'Internal Careers',status:'Published'}});toast('Job published to internal careers')}
async function archiveJob(id){if(!confirm('Archive this job?'))return;await api(`/api/jobs/${id}`,{method:'DELETE'});toast('Job archived');go('jobs')}
function newAssignment(){modal('Create Assignment',`<form id="asgForm"><div class="formgrid">${formFields([{name:'candidate_id',label:'Worker',type:'select',options:REF.candidates.map(x=>({value:x.id,label:x.name}))},{name:'job_id',label:'Job',type:'select',options:REF.jobs.map(x=>({value:x.id,label:x.job_no+' '+x.title}))},{name:'company_id',label:'Company',type:'select',options:REF.companies.map(x=>({value:x.id,label:x.name}))},{name:'start_date',label:'Start',type:'date'},{name:'end_date',label:'End',type:'date'},{name:'worksite',label:'Worksite'},{name:'cost_center',label:'Cost Center'},{name:'bill_rate',label:'Bill Rate',type:'number'},{name:'pay_rate',label:'Pay Rate',type:'number'}])}</div></form>`,`<button class="btn" onclick="closeModal()">Cancel</button><button class="btn primary" onclick="submitAssignment()">Create</button>`)}
async function submitAssignment(){await api('/api/assignments',{method:'POST',body:fd($('#asgForm'))});closeModal();toast('Assignment created');pageAssignments()}
function newPurchaseOrder(){modal('Create Purchase Order',`<form id="poForm"><div class="formgrid">${formFields([{name:'company_id',label:'Company',type:'select',options:REF.companies.map(x=>({value:x.id,label:x.name}))},{name:'job_id',label:'Job',type:'select',options:REF.jobs.map(x=>({value:x.id,label:x.job_no+' '+x.title}))},{name:'po_number',label:'PO Number',required:true},{name:'amount',label:'Amount',type:'number'},{name:'start_date',label:'Start',type:'date'},{name:'end_date',label:'End',type:'date'}])}</div></form>`,`<button class="btn" onclick="closeModal()">Cancel</button><button class="btn primary" onclick="submitPurchaseOrder()">Create</button>`)}
async function submitPurchaseOrder(){await api('/api/purchase-orders',{method:'POST',body:fd($('#poForm'))});closeModal();toast('Purchase order created');pageFinance()}
function newVMSAccount(){modal('New Internal VMS Account',`<form id="vmsForm"><div class="formgrid">${formFields([{name:'name',label:'Name',required:true},{name:'platform',label:'Platform',value:'Internal'},{name:'sync_mode',label:'Mode',value:'Internal'},{name:'notes',label:'Notes',type:'textarea',span:true}])}</div></form>`,`<button class="btn" onclick="closeModal()">Cancel</button><button class="btn primary" onclick="submitVMSAccount()">Create</button>`)}
async function submitVMSAccount(){await api('/api/vms/accounts',{method:'POST',body:fd($('#vmsForm'))});closeModal();toast('VMS account created');pageVMS()}
function newSupplier(){modal('New Supplier',`<form id="supplierForm"><div class="formgrid">${formFields([{name:'name',label:'Supplier',required:true},{name:'contact_name',label:'Contact'},{name:'email',label:'Email'},{name:'phone',label:'Phone'},{name:'tier',label:'Tier',value:'Preferred'},{name:'notes',label:'Notes',type:'textarea',span:true}])}</div></form>`,`<button class="btn" onclick="closeModal()">Cancel</button><button class="btn primary" onclick="submitSupplier()">Create</button>`)}
async function submitSupplier(){await api('/api/suppliers',{method:'POST',body:fd($('#supplierForm'))});closeModal();toast('Supplier created');pageSuppliers()}
async function runOperationalReport(){const key=prompt('Report key: recruiting_pipeline, workforce_activity, or finance_aging','recruiting_pipeline');if(!key)return;const report=await api('/api/reports/run?report_key='+encodeURIComponent(key));modal('Operational Report',`<div class="codeblock">${esc(JSON.stringify(report.rows,null,2))}</div>`,'<button class="btn" onclick="closeModal()">Close</button>',true)}
function exportOperationalReport(){const key=prompt('Report key to export','finance_aging');if(key)location.href='/api/reports/export?report_key='+encodeURIComponent(key)}
function newUDF(){modal('New User Defined Field',`<form id="udfForm"><div class="formgrid">${formFields([{name:'entity_type',label:'Entity',value:'candidate'},{name:'field_name',label:'Field Name',required:true},{name:'field_type',label:'Type',type:'select',options:['text','number','date','boolean','select']}])}</div></form>`,`<button class="btn" onclick="closeModal()">Cancel</button><button class="btn primary" onclick="submitUDF()">Create</button>`)}
async function submitUDF(){await api('/api/custom-fields',{method:'POST',body:fd($('#udfForm'))});closeModal();toast('UDF created');pageAdmin()}
function newAutomation(){modal('New Internal Automation',`<form id="autoForm"><div class="formgrid">${formFields([{name:'name',label:'Name',required:true},{name:'trigger_name',label:'Trigger',value:'candidate.created'},{name:'task_title',label:'Task title',value:'Automation follow-up'}])}</div></form>`,`<button class="btn" onclick="closeModal()">Cancel</button><button class="btn primary" onclick="submitAutomation()">Create</button>`)}
async function submitAutomation(){const d=fd($('#autoForm'));await api('/api/automations',{method:'POST',body:{name:d.name,trigger_name:d.trigger_name,condition:{},action:{type:'create_task',title:d.task_title}}});closeModal();toast('Automation created');pageAdmin()}
function newConnector(){modal('New Connector Configuration',`<form id="connForm"><div class="formgrid">${formFields([{name:'category',label:'Category',value:'Internal'},{name:'name',label:'Name',required:true},{name:'mode',label:'Mode',type:'select',options:['Internal','Demo','External']},{name:'credential_ref',label:'Credential Reference (not secret)'},{name:'notes',label:'Notes',type:'textarea',span:true}])}</div></form>`,`<button class="btn" onclick="closeModal()">Cancel</button><button class="btn primary" onclick="submitConnector()">Create</button>`)}
async function submitConnector(){await api('/api/integrations',{method:'POST',body:fd($('#connForm'))});closeModal();toast('Connector configured');pageAdmin()}

/* ============================================================
   R12A_CONTROL_PERSISTENCE

   Operational controls injected by enhanceR8Controls() must
   survive direct pageX() rerenders triggered after CRUD actions
   and candidate profile tab switches.

   This wrapper is deliberately idempotent:
   - exactly one enhanced control set per rendered pagehead
   - route() may call enhancer again without duplication
   ============================================================ */

const R12A_ORIGINAL_ENHANCER =
    enhanceR8Controls;

enhanceR8Controls=function(base,id){

    if(
        !internalRoles.includes(ME.role)
    ){
        return;
    }

    const bar=$(
        '.pagehead .actions'
    );

    if(!bar){
        return;
    }

    const key=
        String(base||'')
        +':'
        +String(id||'');

    if(
        bar.dataset.r12Enhanced===key
    ){
        return;
    }

    R12A_ORIGINAL_ENHANCER(
        base,
        id
    );

    bar.dataset.r12Enhanced=key;
};


const R12A_ORIGINAL_PAGES={
    candidate:
        pageCandidate,

    job:
        pageJob,

    assignments:
        pageAssignments,

    finance:
        pageFinance,

    vms:
        pageVMS,

    suppliers:
        pageSuppliers,

    reports:
        pageReports,

    admin:
        pageAdmin
};


pageCandidate=async function(id){

    await R12A_ORIGINAL_PAGES
        .candidate(id);

    enhanceR8Controls(
        'candidate',
        id
    );
};


pageJob=async function(id){

    await R12A_ORIGINAL_PAGES
        .job(id);

    enhanceR8Controls(
        'job',
        id
    );
};


pageAssignments=async function(){

    await R12A_ORIGINAL_PAGES
        .assignments();

    enhanceR8Controls(
        'assignments'
    );
};


pageFinance=async function(){

    await R12A_ORIGINAL_PAGES
        .finance();

    enhanceR8Controls(
        'finance'
    );
};


pageVMS=async function(){

    await R12A_ORIGINAL_PAGES
        .vms();

    enhanceR8Controls(
        'vms'
    );
};


pageSuppliers=async function(){

    await R12A_ORIGINAL_PAGES
        .suppliers();

    enhanceR8Controls(
        'suppliers'
    );
};


pageReports=async function(){

    await R12A_ORIGINAL_PAGES
        .reports();

    enhanceR8Controls(
        'reports'
    );
};


pageAdmin=async function(){

    await R12A_ORIGINAL_PAGES
        .admin();

    enhanceR8Controls(
        'admin'
    );
};


async function pageAudit(){const rows=await api('/api/audit');$('#content').innerHTML=`<div class="page">${head('Audit Trail','Security › Audit')}${panel('Recent Activity',`<table class="grid"><tr><th>Date</th><th>User</th><th>Action</th><th>Entity</th><th>ID</th><th>Detail</th><th>IP</th></tr>${rows.map(x=>`<tr><td>${new Date(x.created_at).toLocaleString()}</td><td>${esc(x.user_name||x.email||'System')}</td><td>${esc(x.action)}</td><td>${esc(x.entity_type)}</td><td>${x.entity_id||''}</td><td>${esc(x.detail||'')}</td><td>${esc(x.ip||'')}</td></tr>`).join('')}</table>`)}</div>`}

async function pageCandidatePortal(){const d=await api('/api/dashboard');const c=d.candidate;const subs=c.submissions||[];$('#content').innerHTML=`<div class="page"><div class="portal-hero"><h1>Welcome, ${esc(c.first_name)}</h1><p>Search open positions, track your applications and manage your candidate profile.</p></div><div class="three-col">${panel('My Applications',`<div class="bigstat">${subs.length}</div><p>${subs.filter(x=>!['rejected','withdrawn'].includes(x.status)).length} active process(es)</p>`)}${panel('Profile Credibility',`<div class="bigstat">${c.credibility_score}%</div><div class="progress"><i style="width:${c.credibility_score}%"></i></div>`)}${panel('Availability',`<div class="bigstat" style="font-size:20px">${fmtDate(c.availability_date)}</div><p>${esc(c.current_title||'')}</p>`)}</div>${panel('My Applications',`<table class="grid"><tr><th>Job</th><th>Status</th><th>Submitted</th></tr>${subs.map(x=>`<tr><td>${x.job_no} · ${esc(x.job_title)}</td><td>${status(x.status)}</td><td>${fmtDate(x.submitted_at||x.created_at)}</td></tr>`).join('')}</table>`)}<h2>Open Positions</h2><div class="jobcards">${d.jobs.map(j=>`<div class="jobcard"><h3>${esc(j.title)}</h3><small>${j.job_no} · ${esc([j.city,j.state].filter(Boolean).join(', '))} · ${esc(j.work_mode)}</small><p>${money(j.pay_min)}–${money(j.pay_max)} / ${j.rate_type}</p><button class="btn primary" onclick="candidateApply(${j.id},${c.id})">Apply / Interested</button></div>`).join('')}</div></div>`}
async function candidateApply(jid,cid){await api(`/api/jobs/${jid}/interested`,{method:'POST',body:{candidate_id:cid,status:'interested',source:'Candidate Portal'}});toast('Interest registered. Recruiter can now qualify and submit you.')}
async function pageClientPortal(){const [d,jobs,subs,ints,ts]=await Promise.all([api('/api/dashboard'),api('/api/jobs'),api('/api/submissions'),api('/api/interviews'),api('/api/timesheets')]);$('#content').innerHTML=`<div class="page"><div class="portal-hero"><h1>${esc(d.company?.name||'Client')} Hiring Manager Portal</h1><p>Requisitions, candidate review, interviews and workforce approvals.</p></div><div class="three-col">${panel('Open Requisitions',`<div class="bigstat">${d.open_jobs}</div>`)}${panel('Candidates Submitted',`<div class="bigstat">${d.submissions}</div>`)}${panel('Upcoming Interviews',`<div class="bigstat">${d.interviews}</div>`)}</div>${panel('Candidate Review Queue',`<table class="grid"><tr><th>Candidate</th><th>Job</th><th>Summary</th><th>Rate</th><th>Status</th><th>Decision</th></tr>${subs.map(s=>`<tr><td>${esc(s.first_name+' '+s.last_name)}<br><small>${esc(s.current_title||'')}</small></td><td>${s.job_no} · ${esc(s.job_title)}</td><td>${esc(s.recruiter_summary||'')}</td><td>${money(s.client_rate)}</td><td>${status(s.status)}</td><td><button class="btn small" onclick="clientDecision(${s.id},'interview')">Interview</button> <button class="btn small danger" onclick="clientDecision(${s.id},'rejected')">Reject</button></td></tr>`).join('')}</table>`)}${panel('My Requisitions',`<table class="grid"><tr><th>Job</th><th>Location</th><th>Status</th><th>Openings</th><th>Submittals</th></tr>${jobs.map(j=>`<tr><td>${j.job_no} · ${esc(j.title)}</td><td>${esc([j.city,j.state].filter(Boolean).join(', '))}</td><td>${status(j.status)}</td><td>${j.filled}/${j.openings}</td><td>${j.submission_count}</td></tr>`).join('')}</table>`)}${panel('Timesheet Approval',`<table class="grid"><tr><th>Worker</th><th>Week</th><th>Hours</th><th>Status</th><th></th></tr>${ts.map(t=>`<tr><td>${esc(t.first_name+' '+t.last_name)}</td><td>${fmtDate(t.week_start)}</td><td>${t.total_hours}</td><td>${status(t.status)}</td><td>${t.status==='submitted'?`<button class="btn small success" onclick="timeStatus(${t.id},'approved')">Approve</button>`:''}</td></tr>`).join('')}</table>`)}</div>`}
async function clientDecision(id,st){await api(`/api/submissions/${id}/status`,{method:'POST',body:{status:st,client_feedback:st==='interview'?'Client requests interview':'Client declined candidate'}});toast('Candidate decision saved');pageClientPortal()}
async function pageWorkerPortal(){const [d,as,ts,ex,shifts]=await Promise.all([api('/api/dashboard'),api('/api/assignments'),api('/api/timesheets'),api('/api/expenses'),api('/api/shifts')]);const a=as[0];$('#content').innerHTML=`<div class="page"><div class="portal-hero"><h1>MyTime — ${esc(d.candidate.first_name+' '+d.candidate.last_name)}</h1><p>Assignment, shifts, time entry and expense management.</p></div>${a?panel('Current Assignment',`<div class="two-col"><div><div class="kv"><b>Job</b><span>${a.job_no} · ${esc(a.job_title)}</span></div><div class="kv"><b>Client</b><span>${esc(a.company_name||'')}</span></div><div class="kv"><b>Dates</b><span>${fmtDate(a.start_date)} — ${fmtDate(a.end_date)}</span></div></div><div><div class="kv"><b>Pay Rate</b><span>${money(a.pay_rate)}/hr</span></div><div class="kv"><b>Worksite</b><span>${esc(a.worksite||'')}</span></div><div class="kv"><b>Status</b><span>${status(a.status)}</span></div></div></div>`):''}${panel('Upcoming Shifts',`<table class="grid"><tr><th>Date</th><th>Time</th><th>Location</th><th>Status</th></tr>${shifts.map(s=>`<tr><td>${fmtDate(s.shift_date)}</td><td>${esc(s.start_time)}–${esc(s.end_time)}</td><td>${esc(s.location||'')}</td><td>${status(s.status)}</td></tr>`).join('')}</table>`)}<div class="two-col">${panel('My Timesheets',`<button class="btn primary small" onclick="newTimesheet(${a?.id||0},${d.candidate.id})">+ Enter Time</button><table class="grid" style="margin-top:8px"><tr><th>Week</th><th>Hours</th><th>OT</th><th>Status</th></tr>${ts.map(t=>`<tr><td>${fmtDate(t.week_start)}</td><td>${t.total_hours}</td><td>${t.overtime_hours}</td><td>${status(t.status)}</td></tr>`).join('')}</table>`)}${panel('My Expenses',`<button class="btn primary small" onclick="newExpense(${a?.id||0})">+ Expense</button><table class="grid" style="margin-top:8px"><tr><th>Date</th><th>Category</th><th>Amount</th><th>Status</th></tr>${ex.map(x=>`<tr><td>${fmtDate(x.expense_date)}</td><td>${esc(x.category)}</td><td>${money(x.amount)}</td><td>${status(x.status)}</td></tr>`).join('')}</table>`)}</div></div>`}
function newTimesheet(aid,cid){const monday=new Date();monday.setDate(monday.getDate()-((monday.getDay()+6)%7));const wk=monday.toISOString().slice(0,10);modal('Enter Timesheet',`<form id="timeForm"><input type="hidden" name="assignment_id" value="${aid}"><input type="hidden" name="week_start" value="${wk}"><div class="formgrid">${['Mon','Tue','Wed','Thu','Fri','Sat','Sun'].map(d=>`<div class="field"><label>${d}</label><input type="number" step=".25" name="${d}" value="${['Sat','Sun'].includes(d)?0:8}"></div>`).join('')}</div></form>`,`<button class="btn" onclick="closeModal()">Cancel</button><button class="btn primary" onclick="submitTimesheet()">Submit</button>`)}
async function submitTimesheet(){const d=fd($('#timeForm')),daily={};['Mon','Tue','Wed','Thu','Fri','Sat','Sun'].forEach(x=>daily[x]=+d[x]);await api('/api/timesheets',{method:'POST',body:{assignment_id:+d.assignment_id,week_start:d.week_start,daily,status:'submitted'}});closeModal();toast('Timesheet submitted');pageWorkerPortal()}
function newExpense(aid){modal('Submit Expense',`<form id="expForm"><div class="formgrid">${formFields([{name:'expense_date',label:'Date',type:'date',value:new Date().toISOString().slice(0,10)},{name:'category',label:'Category',type:'select',options:['Travel','Meals','Lodging','Mileage','Equipment','Other']},{name:'amount',label:'Amount',type:'number'},{name:'receipt_ref',label:'Receipt Reference'},{name:'description',label:'Description',type:'textarea',span:true}])}</div></form>`,`<button class="btn" onclick="closeModal()">Cancel</button><button class="btn primary" onclick="submitExpense(${aid})">Submit</button>`)}
async function submitExpense(aid){const d=fd($('#expForm'));d.assignment_id=aid;d.status='submitted';await api('/api/expenses',{method:'POST',body:d});closeModal();toast('Expense submitted');pageWorkerPortal()}
async function pageSupplierPortal(){const jobs=await api('/api/jobs');$('#content').innerHTML=`<div class="page"><div class="portal-hero"><h1>Supplier Portal</h1><p>Released requisitions and supplier submission workspace.</p></div>${panel('Released Jobs',`<table class="grid"><tr><th>Job</th><th>Location</th><th>Work Mode</th><th>Bill Range</th><th>Status</th><th></th></tr>${jobs.map(j=>`<tr><td>${j.job_no} · ${esc(j.title)}</td><td>${esc([j.city,j.state].filter(Boolean).join(', '))}</td><td>${esc(j.work_mode)}</td><td>${money(j.bill_min)}–${money(j.bill_max)}</td><td>${status(j.status)}</td><td><button class="btn small" onclick="supplierSubmit(${j.id})">Submit Candidate</button></td></tr>`).join('')}</table>`)}</div>`}
function supplierSubmit(jid){modal('Supplier Candidate Submission',`<div class="field"><label>Existing Candidate</label><select id="supCand">${REF.candidates.map(c=>`<option value="${c.id}">${esc(c.name)} — ${esc(c.current_title||'')}</option>`).join('')}</select></div><p class="subtle">Supplier submission enters the same internal submittal lifecycle and preserves source attribution.</p>`,`<button class="btn" onclick="closeModal()">Cancel</button><button class="btn primary" onclick="(async()=>{let cid=+document.getElementById('supCand').value;await api('/api/jobs/${jid}/submissions',{method:'POST',body:{candidate_id:cid,status:'submitted',recruiter_summary:'Supplier submitted candidate',compliance_status:'Pending',rtr_status:'Pending'}});closeModal();toast('Supplier submittal created')})()">Submit</button>`)}
async function pageApproverPortal(){const [ts,ex]=await Promise.all([api('/api/timesheets'),api('/api/expenses')]);$('#content').innerHTML=`<div class="page"><div class="portal-hero"><h1>Timesheet & Expense Approver</h1><p>Review submitted workforce transactions for your client organization.</p></div><div class="two-col">${panel('Timesheets',`<table class="grid"><tr><th>Worker</th><th>Week</th><th>Hours</th><th>Status</th><th></th></tr>${ts.map(t=>`<tr><td>${esc(t.first_name+' '+t.last_name)}</td><td>${fmtDate(t.week_start)}</td><td>${t.total_hours}</td><td>${status(t.status)}</td><td>${t.status==='submitted'?`<button class="btn small success" onclick="timeStatus(${t.id},'approved')">Approve</button> <button class="btn small danger" onclick="timeStatus(${t.id},'rejected')">Reject</button>`:''}</td></tr>`).join('')}</table>`)}${panel('Expenses',`<table class="grid"><tr><th>Worker</th><th>Date</th><th>Amount</th><th>Status</th><th></th></tr>${ex.map(x=>`<tr><td>${esc(x.first_name+' '+x.last_name)}</td><td>${fmtDate(x.expense_date)}</td><td>${money(x.amount)}</td><td>${status(x.status)}</td><td>${x.status==='submitted'?`<button class="btn small success" onclick="expenseStatus(${x.id},'approved')">Approve</button> <button class="btn small danger" onclick="expenseStatus(${x.id},'rejected')">Reject</button>`:''}</td></tr>`).join('')}</table>`)}</div></div>`}

async function globalSearch(){const q=$('#globalQ').value.trim();if(!q)return;const rows=await api('/api/candidates?q='+encodeURIComponent(q));modal('Global Search — Candidates',`<table class="grid"><tr><th>Name</th><th>Title</th><th>Location</th></tr>${rows.map(c=>`<tr><td><a class="link" onclick="closeModal();go('candidate/${c.id}')">${esc(c.first_name+' '+c.last_name)}</a></td><td>${esc(c.current_title||'')}</td><td>${esc([c.city,c.state].filter(Boolean).join(', '))}</td></tr>`).join('')}</table>`,`<button class="btn" onclick="closeModal()">Close</button>`,true)}

boot();
