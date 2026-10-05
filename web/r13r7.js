(function(){
'use strict';
const R13R7_VERSION='R13R7_PUBLIC_PARITY_1';

function r7Root(){
  return document.querySelector('#content .page') || document.querySelector('#content');
}
function r7Panel(id,title,html){
  const root=r7Root();if(!root)return;
  document.getElementById(id)?.remove();
  const d=document.createElement('div');d.id=id;d.className='panel r7-panel';
  d.innerHTML=`<div class="panel-title"><span>${esc(title)}</span><span class="tag">Deep Operations</span></div><div class="panel-body">${html}</div>`;
  root.appendChild(d);
}
function r7Table(rows,cols){
  if(!rows?.length)return '<div class="r7-empty">No records</div>';
  return `<table class="r7-table"><tr>${cols.map(c=>`<th>${esc(c[0])}</th>`).join('')}</tr>${rows.map(r=>`<tr>${cols.map(c=>`<td>${esc(typeof c[1]==='function'?c[1](r):(r[c[1]]??''))}</td>`).join('')}</tr>`).join('')}</table>`;
}
function r7Fields(fields){
  return fields.map(f=>{
    if(f.type==='select'){
      const options=(f.options||[]).map(x=>typeof x==='object'?x:{value:x,label:x});
      return {name:f.name,label:f.label,type:'select',options,value:f.value??''};
    }
    return f;
  });
}
function r7Create(title,endpoint,fields,after){
  window.__r7After=after;
  modal(title,`<form id="r7CreateForm"><div class="r13-modal-grid">${formFields(r7Fields(fields))}</div></form>`,
    `<button class="btn" onclick="closeModal()">Cancel</button><button class="btn primary" onclick="r7SubmitCreate('${endpoint.replaceAll("'","\\'")}')">Save</button>`,true);
}
async function r7SubmitCreate(endpoint){
  try{
    const data=fd(document.getElementById('r7CreateForm'));
    for(const k of Object.keys(data)){
      if(['graduated','sponsorship_required','email_opt_out','sms_opt_out','phone_opt_out','active','mandatory','billable','pay_by_company','is_primary','is_default','is_shared','can_view','can_create','can_edit','can_delete'].includes(k)){
        data[k]=['1','true','yes','on'].includes(String(data[k]).toLowerCase())?1:0;
      }
      if(['radius_miles','priority','company_id','job_id','step_no','approver_user_id','entity_id','hours','break_minutes','amount','quantity','rate','tax','source_id'].includes(k) && data[k]!==''){
        data[k]=Number(data[k]);
      }
    }
    await api(endpoint,{method:'POST',body:data});
    closeModal();toast('Saved');
    if(typeof window.__r7After==='function')await window.__r7After();
  }catch(e){toast(e.message,'err')}
}
async function r7Delete(resource,id,after){
  if(!confirm('Delete this record?'))return;
  try{await api(`/api/parity/${resource}/${id}`,{method:'DELETE'});toast('Deleted');if(after)await after()}catch(e){toast(e.message,'err')}
}
const yesNo=[{value:0,label:'No'},{value:1,label:'Yes'}];

async function r7Candidate(id){
  const urls=['preferred-locations','education','work-authorization','do-not-submit','references','communication-preferences'];
  const [loc,edu,wa,dns,refs,prefs]=await Promise.all(urls.map(x=>api(`/api/candidates/${id}/${x}`)));
  const companies=REF?.companies||[];
  const jobs=await api('/api/jobs').catch(()=>[]);
  const refresh=()=>r7Candidate(id);
  r7Panel('r7-candidate-deep','Enterprise Candidate Record',`
    <div class="r7-toolbar">
      <button class="btn small" onclick='r7Create("Preferred Location","/api/candidates/${id}/preferred-locations",${JSON.stringify([{name:"country",label:"Country"},{name:"state",label:"State / Province"},{name:"city",label:"City"},{name:"zip",label:"Postal Code"},{name:"radius_miles",label:"Radius Miles",type:"number"},{name:"priority",label:"Priority",type:"number",value:1}])},()=>r7Candidate(${id}))'>+ Preferred Location</button>
      <button class="btn small" onclick='r7Create("Education","/api/candidates/${id}/education",${JSON.stringify([{name:"institution",label:"Institution"},{name:"degree",label:"Degree"},{name:"field",label:"Field of Study"},{name:"start_date",label:"Start",type:"date"},{name:"end_date",label:"End",type:"date"},{name:"graduated",label:"Graduated",type:"select",options:yesNo}])},()=>r7Candidate(${id}))'>+ Education</button>
      <button class="btn small" onclick='r7Create("Work Authorization","/api/candidates/${id}/work-authorization",${JSON.stringify([{name:"country",label:"Country"},{name:"authorization_type",label:"Authorization Type"},{name:"status",label:"Status"},{name:"expiry_date",label:"Expiry",type:"date"},{name:"sponsorship_required",label:"Sponsorship Required",type:"select",options:yesNo},{name:"e_verify_status",label:"E-Verify Status"}])},()=>r7Candidate(${id}))'>+ Work Authorization</button>
      <button class="btn small" id="r7-add-reference">+ Reference</button>
      <button class="btn small" id="r7-add-dns">+ Do Not Submit</button>
      <button class="btn small" id="r7-add-pref">+ Communication Preference</button>
    </div>
    <div class="r7-grid">
      <div class="r7-section"><h4>Preferred Locations</h4>${r7Table(loc,[['Country','country'],['State','state'],['City','city'],['Zip','zip'],['Radius',x=>x.radius_miles||0]])}</div>
      <div class="r7-section"><h4>Education</h4>${r7Table(edu,[['Institution','institution'],['Degree','degree'],['Field','field'],['End','end_date']])}</div>
      <div class="r7-section"><h4>Work Authorization / E-Verify</h4>${r7Table(wa,[['Country','country'],['Type','authorization_type'],['Status','status'],['E-Verify','e_verify_status'],['Expiry','expiry_date']])}</div>
      <div class="r7-section"><h4>Do Not Submit</h4>${r7Table(dns,[['Company ID','company_id'],['Job ID','job_id'],['Reason','reason'],['Active',x=>x.active?'Yes':'No']])}</div>
      <div class="r7-section"><h4>References</h4>${r7Table(refs,[['Name','name'],['Company','company'],['Relationship','relationship'],['Status','status']])}</div>
      <div class="r7-section"><h4>Communication Preference History</h4>${r7Table(prefs,[['Email opt-out',x=>x.email_opt_out?'Yes':'No'],['SMS opt-out',x=>x.sms_opt_out?'Yes':'No'],['Phone opt-out',x=>x.phone_opt_out?'Yes':'No'],['Reason','reason'],['Effective','effective_at']])}</div>
    </div>`);
  document.getElementById('r7-add-reference').onclick=()=>r7Create('Reference',`/api/candidates/${id}/references`,[
    {name:'name',label:'Name',required:true},{name:'company',label:'Company'},{name:'title',label:'Title'},{name:'email',label:'Email'},
    {name:'phone',label:'Phone'},{name:'relationship',label:'Relationship'},{name:'status',label:'Status',type:'select',options:['Pending','Verified','Unable to Verify']},{name:'notes',label:'Notes',type:'textarea',span:true}
  ],refresh);
  document.getElementById('r7-add-dns').onclick=()=>r7Create('Do Not Submit',`/api/candidates/${id}/do-not-submit`,[
    {name:'company_id',label:'Company',type:'select',options:[{value:'',label:'—'},...companies.map(x=>({value:x.id,label:x.name}))]},
    {name:'job_id',label:'Job',type:'select',options:[{value:'',label:'—'},...jobs.map(x=>({value:x.id,label:`${x.job_no} ${x.title}`}))]},
    {name:'reason',label:'Reason',type:'textarea',span:true},{name:'active',label:'Active',type:'select',options:yesNo,value:1}
  ],refresh);
  document.getElementById('r7-add-pref').onclick=()=>r7Create('Communication Preference',`/api/candidates/${id}/communication-preferences`,[
    {name:'email_opt_out',label:'Email Opt Out',type:'select',options:yesNo},{name:'sms_opt_out',label:'SMS Opt Out',type:'select',options:yesNo},
    {name:'phone_opt_out',label:'Phone Opt Out',type:'select',options:yesNo},{name:'effective_at',label:'Effective At',type:'datetime-local'},
    {name:'reason',label:'Reason',type:'textarea',span:true}
  ],refresh);
}

async function r7Company(id){
  const notes=await api(`/api/companies/${id}/notes`);
  r7Panel('r7-company-notes','Company Activity & Notes',`
    <div class="r7-toolbar"><button class="btn small primary" id="r7-company-note-add">+ Note</button></div>
    ${r7Table(notes,[['Date','created_at'],['Type','note_type'],['Note','note']])}`);
  document.getElementById('r7-company-note-add').onclick=()=>r7Create('Company Note',`/api/companies/${id}/notes`,[
    {name:'note_type',label:'Type',type:'select',options:['General','Sales','Client','Compliance','Financial']},
    {name:'note',label:'Note',type:'textarea',span:true,required:true}
  ],()=>r7Company(id));
}

async function r7Contact(id){
  const [phones,addresses,notes]=await Promise.all([
    api(`/api/contacts/${id}/phones`),api(`/api/contacts/${id}/addresses`),api(`/api/contacts/${id}/notes`)
  ]);
  r7Panel('r7-contact-deep','Contact Detail Extensions',`
    <div class="r7-toolbar">
      <button class="btn small" id="r7-phone-add">+ Phone</button>
      <button class="btn small" id="r7-address-add">+ Address</button>
      <button class="btn small" id="r7-contact-note-add">+ Note</button>
    </div>
    <div class="r7-grid">
      <div class="r7-section"><h4>Phones</h4>${r7Table(phones,[['Type','phone_type'],['Number','number'],['Ext','extension'],['Primary',x=>x.is_primary?'Yes':'No']])}</div>
      <div class="r7-section"><h4>Addresses</h4>${r7Table(addresses,[['Type','address_type'],['Address','address1'],['City','city'],['State','state'],['Country','country']])}</div>
      <div class="r7-section"><h4>Notes</h4>${r7Table(notes,[['Date','created_at'],['Type','note_type'],['Note','note']])}</div>
    </div>`);
  document.getElementById('r7-phone-add').onclick=()=>r7Create('Contact Phone',`/api/contacts/${id}/phones`,[
    {name:'phone_type',label:'Type',type:'select',options:['Work','Mobile','Home','Other']},{name:'number',label:'Number',required:true},{name:'extension',label:'Extension'},{name:'is_primary',label:'Primary',type:'select',options:yesNo}
  ],()=>r7Contact(id));
  document.getElementById('r7-address-add').onclick=()=>r7Create('Contact Address',`/api/contacts/${id}/addresses`,[
    {name:'address_type',label:'Type',type:'select',options:['Work','Billing','Home','Other']},{name:'address1',label:'Address 1'},{name:'address2',label:'Address 2'},
    {name:'city',label:'City'},{name:'state',label:'State / Province'},{name:'zip',label:'Postal Code'},{name:'country',label:'Country'},{name:'is_default',label:'Default',type:'select',options:yesNo}
  ],()=>r7Contact(id));
  document.getElementById('r7-contact-note-add').onclick=()=>r7Create('Contact Note',`/api/contacts/${id}/notes`,[
    {name:'note_type',label:'Type',type:'select',options:['General','Call','Email','Meeting','Compliance']},{name:'note',label:'Note',type:'textarea',span:true,required:true}
  ],()=>r7Contact(id));
}

async function r7SubmissionWorkspace(){
  const subs=await api('/api/submissions');
  r7Panel('r7-submission-ops','Submission Detail / Timeline / Attachments',`
    <div class="field"><label>Submission</label><select id="r7-submission-select"><option value="">Select…</option>${subs.map(x=>`<option value="${x.id}">#${x.id} · ${esc((x.first_name||'')+' '+(x.last_name||''))} → ${esc(x.job_no||'')} ${esc(x.job_title||'')}</option>`).join('')}</select></div>
    <div id="r7-submission-detail" class="r7-empty">Select a submission.</div>`);
  document.getElementById('r7-submission-select').onchange=()=>r7LoadSubmission(document.getElementById('r7-submission-select').value);
}
async function r7LoadSubmission(id){
  if(!id)return;
  const [events,files]=await Promise.all([api(`/api/submissions/${id}/events`),api(`/api/submissions/${id}/attachments`)]);
  document.getElementById('r7-submission-detail').innerHTML=`
    <div class="r7-toolbar"><button class="btn small" id="r7-event-add">+ Timeline Event</button><input id="r7-sub-file" type="file"><button class="btn small" id="r7-sub-upload">Upload Attachment</button></div>
    <div class="r7-grid"><div class="r7-section"><h4>Timeline</h4>${r7Table(events,[['Date','created_at'],['Event','event_type'],['From','from_status'],['To','to_status'],['Note','note']])}</div>
    <div class="r7-section"><h4>Attachments</h4>${r7Table(files,[['Name','name'],['Type','mime_type'],['Bytes','size_bytes']])}</div></div>`;
  document.getElementById('r7-event-add').onclick=()=>r7Create('Submission Event',`/api/submissions/${id}/events`,[
    {name:'event_type',label:'Event Type',type:'select',options:['Presented','Client Feedback','Rate Change','Interview','Offer','Rejection','Withdrawal','Note']},
    {name:'from_status',label:'From Status'},{name:'to_status',label:'To Status'},{name:'note',label:'Note',type:'textarea',span:true}
  ],()=>r7LoadSubmission(id));
  document.getElementById('r7-sub-upload').onclick=async()=>{
    const f=document.getElementById('r7-sub-file').files?.[0];if(!f)return toast('Choose a file','err');
    const b64=await r7FileBase64(f);await api(`/api/submissions/${id}/attachments`,{method:'POST',body:{name:f.name,mime_type:f.type||'application/octet-stream',content_base64:b64}});toast('Uploaded');await r7LoadSubmission(id);
  };
}

async function r7FileBase64(file){
  const buf=await file.arrayBuffer();let s='';const a=new Uint8Array(buf);const step=0x8000;
  for(let i=0;i<a.length;i+=step)s+=String.fromCharCode(...a.subarray(i,i+step));
  return btoa(s);
}

async function r7OnboardingTemplates(){
  const rows=await api('/api/onboarding/templates');
  r7Panel('r7-onboarding-templates','Onboarding Template Library',`
    <div class="r7-toolbar"><button class="btn small primary" id="r7-template-add">+ Template</button></div>
    ${r7Table(rows,[['Name','name'],['Description','description'],['Active',x=>x.active?'Yes':'No']])}`);
  document.getElementById('r7-template-add').onclick=()=>r7Create('Onboarding Template','/api/onboarding/templates',[
    {name:'name',label:'Template Name',required:true},{name:'description',label:'Description',type:'textarea',span:true},{name:'active',label:'Active',type:'select',options:yesNo,value:1}
  ],r7OnboardingTemplates);
}

async function r7Timesheets(){
  const sheets=await api('/api/timesheets');
  r7Panel('r7-timesheet-lines','Detailed Timecard Lines',`
    <div class="field"><label>Timesheet</label><select id="r7-ts-select"><option value="">Select…</option>${sheets.map(x=>`<option value="${x.id}">#${x.id} · ${esc(x.worker_name||x.candidate_name||'')} · ${esc(x.week_start||'')}</option>`).join('')}</select></div>
    <div id="r7-ts-lines" class="r7-empty">Select a timesheet.</div>`);
  document.getElementById('r7-ts-select').onchange=()=>r7LoadTimesheet(document.getElementById('r7-ts-select').value);
}
async function r7LoadTimesheet(id){
  if(!id)return;const lines=await api(`/api/timesheets/${id}/lines`);
  document.getElementById('r7-ts-lines').innerHTML=`<div class="r7-toolbar"><button class="btn small" id="r7-ts-add">+ Time Line</button></div>${r7Table(lines,[['Date','work_date'],['Category','category'],['Hours','hours'],['Start','start_time'],['End','end_time'],['Break','break_minutes'],['Note','note']])}`;
  document.getElementById('r7-ts-add').onclick=()=>r7Create('Time Line',`/api/timesheets/${id}/lines`,[
    {name:'work_date',label:'Work Date',type:'date',required:true},{name:'category',label:'Category',type:'select',options:['Regular','Overtime','Double Time','PTO','Holiday']},{name:'hours',label:'Hours',type:'number'},
    {name:'start_time',label:'Start',type:'time'},{name:'end_time',label:'End',type:'time'},{name:'break_minutes',label:'Break Minutes',type:'number'},{name:'note',label:'Note',type:'textarea',span:true}
  ],()=>r7LoadTimesheet(id));
}

async function r7Expenses(){
  const exps=await api('/api/expenses');
  r7Panel('r7-expense-deep','Expense Lines & Receipts',`
    <div class="field"><label>Expense</label><select id="r7-exp-select"><option value="">Select…</option>${exps.map(x=>`<option value="${x.id}">#${x.id} · ${esc(x.category||'')} · ${esc(x.amount||'')}</option>`).join('')}</select></div>
    <div id="r7-exp-detail" class="r7-empty">Select an expense.</div>`);
  document.getElementById('r7-exp-select').onchange=()=>r7LoadExpense(document.getElementById('r7-exp-select').value);
}
async function r7LoadExpense(id){
  if(!id)return;const [lines,receipts]=await Promise.all([api(`/api/expenses/${id}/lines`),api(`/api/expenses/${id}/receipts`)]);
  document.getElementById('r7-exp-detail').innerHTML=`
    <div class="r7-toolbar"><button class="btn small" id="r7-exp-line-add">+ Expense Line</button><input id="r7-receipt-file" type="file"><button class="btn small" id="r7-receipt-upload">Upload Receipt</button></div>
    <div class="r7-grid"><div class="r7-section"><h4>Lines</h4>${r7Table(lines,[['Date','expense_date'],['Category','category'],['Amount','amount'],['Qty','quantity'],['Currency','currency'],['Billable',x=>x.billable?'Yes':'No']])}</div>
    <div class="r7-section"><h4>Receipts</h4>${r7Table(receipts,[['File','file_name'],['Type','mime_type'],['Bytes','size_bytes']])}</div></div>`;
  document.getElementById('r7-exp-line-add').onclick=()=>r7Create('Expense Line',`/api/expenses/${id}/lines`,[
    {name:'expense_date',label:'Date',type:'date'},{name:'category',label:'Category'},{name:'amount',label:'Amount',type:'number'},{name:'quantity',label:'Quantity',type:'number',value:1},
    {name:'billable',label:'Billable',type:'select',options:yesNo,value:1},{name:'pay_by_company',label:'Pay By Company',type:'select',options:yesNo},{name:'currency',label:'Currency',value:'USD'},{name:'description',label:'Description',type:'textarea',span:true}
  ],()=>r7LoadExpense(id));
  document.getElementById('r7-receipt-upload').onclick=async()=>{const f=document.getElementById('r7-receipt-file').files?.[0];if(!f)return toast('Choose receipt','err');const b64=await r7FileBase64(f);await api(`/api/expenses/${id}/receipts`,{method:'POST',body:{file_name:f.name,mime_type:f.type||'application/octet-stream',content_base64:b64}});toast('Receipt uploaded');await r7LoadExpense(id)};
}

async function r7Finance(){
  const invoices=await api('/api/invoices');
  r7Panel('r7-invoice-lines','Invoice Line Items',`
    <div class="field"><label>Invoice</label><select id="r7-inv-select"><option value="">Select…</option>${invoices.map(x=>`<option value="${x.id}">${esc(x.invoice_no||('#'+x.id))} · ${esc(x.company_name||'')}</option>`).join('')}</select></div>
    <div id="r7-inv-lines" class="r7-empty">Select an invoice.</div>`);
  document.getElementById('r7-inv-select').onchange=()=>r7LoadInvoice(document.getElementById('r7-inv-select').value);
}
async function r7LoadInvoice(id){
  if(!id)return;const lines=await api(`/api/invoices/${id}/lines`);
  document.getElementById('r7-inv-lines').innerHTML=`<div class="r7-toolbar"><button class="btn small" id="r7-inv-add">+ Invoice Line</button></div>${r7Table(lines,[['Type','line_type'],['Description','description'],['Qty','quantity'],['Rate','rate'],['Amount','amount'],['Tax','tax']])}`;
  document.getElementById('r7-inv-add').onclick=()=>r7Create('Invoice Line',`/api/invoices/${id}/lines`,[
    {name:'line_type',label:'Line Type',type:'select',options:['Service','Time','Expense','Adjustment','Tax']},{name:'description',label:'Description'},
    {name:'quantity',label:'Quantity',type:'number',value:1},{name:'rate',label:'Rate',type:'number'},{name:'amount',label:'Amount',type:'number'},{name:'tax',label:'Tax',type:'number'},
    {name:'source_type',label:'Source Type'},{name:'source_id',label:'Source ID',type:'number'}
  ],()=>r7LoadInvoice(id));
}

async function r7Communications(){
  const rows=await api('/api/communication-templates');
  r7Panel('r7-comm-templates','Communication Template Library',`
    <div class="r7-toolbar"><button class="btn small primary" id="r7-template-comm-add">+ Template</button></div>
    ${r7Table(rows,[['Name','name'],['Channel','channel'],['Subject','subject'],['Active',x=>x.active?'Yes':'No']])}`);
  document.getElementById('r7-template-comm-add').onclick=()=>r7Create('Communication Template','/api/communication-templates',[
    {name:'name',label:'Name',required:true},{name:'channel',label:'Channel',type:'select',options:['Email','SMS','Phone']},{name:'subject',label:'Subject'},
    {name:'body',label:'Body',type:'textarea',span:true},{name:'active',label:'Active',type:'select',options:yesNo,value:1}
  ],r7Communications);
}

async function r7Admin(){
  const [perms,approvals]=await Promise.all([api('/api/permission-overrides'),api('/api/approval-steps')]);
  r7Panel('r7-admin-enterprise','Granular Permissions & Approval Steps',`
    <div class="r7-toolbar"><button class="btn small" id="r7-perm-add">+ Permission Override</button><button class="btn small" id="r7-approval-add">+ Approval Step</button></div>
    <div class="r7-grid"><div class="r7-section"><h4>Permission Overrides</h4>${r7Table(perms,[['Role','role'],['Module','module_name'],['View',x=>x.can_view?'Y':'N'],['Create',x=>x.can_create?'Y':'N'],['Edit',x=>x.can_edit?'Y':'N'],['Delete',x=>x.can_delete?'Y':'N']])}</div>
    <div class="r7-section"><h4>Approval Steps</h4>${r7Table(approvals,[['Entity','entity_type'],['ID','entity_id'],['Step','step_no'],['Role','approver_role'],['Status','status']])}</div></div>`);
  document.getElementById('r7-perm-add').onclick=()=>r7Create('Permission Override','/api/permission-overrides',[
    {name:'role',label:'Role',type:'select',options:['admin','teamlead','recruiter','sales','hr','finance']},{name:'module_name',label:'Module'},
    {name:'can_view',label:'View',type:'select',options:yesNo,value:1},{name:'can_create',label:'Create',type:'select',options:yesNo},{name:'can_edit',label:'Edit',type:'select',options:yesNo},{name:'can_delete',label:'Delete',type:'select',options:yesNo}
  ],r7Admin);
  document.getElementById('r7-approval-add').onclick=()=>r7Create('Approval Step','/api/approval-steps',[
    {name:'entity_type',label:'Entity Type'},{name:'entity_id',label:'Entity ID',type:'number'},{name:'step_no',label:'Step',type:'number',value:1},
    {name:'approver_role',label:'Approver Role'},{name:'approver_user_id',label:'Approver User ID',type:'number'},{name:'status',label:'Status',type:'select',options:['Pending','Approved','Rejected','Skipped']},{name:'note',label:'Note',type:'textarea',span:true}
  ],r7Admin);
}

async function r7Dashboard(){
  const rows=await api('/api/notifications');
  r7Panel('r7-notifications','Notification Center',`${r7Table(rows,[['Date','created_at'],['Category','category'],['Title','title'],['Message','body'],['Read',x=>x.read_at?'Yes':'No']])}`);
}

function r7CurrentFilters(prefix){
  const o={};document.querySelectorAll(`[id^="${prefix}"]`).forEach(x=>o[x.id]=x.value);return o;
}
async function r7SavedViews(entity,prefix){
  const rows=await api(`/api/saved-views?entity_type=${encodeURIComponent(entity)}`);
  r7Panel(`r7-saved-${entity}`,`${entity[0].toUpperCase()+entity.slice(1)} Saved Views`,`
    <div class="r7-toolbar"><button class="btn small" id="r7-save-view-btn">Save Current View</button></div>
    ${r7Table(rows,[['Name','name'],['Shared',x=>x.is_shared?'Yes':'No'],['Created','created_at']])}`);
  document.getElementById('r7-save-view-btn').onclick=async()=>{
    const name=prompt('View name');if(!name)return;
    const headers=[...document.querySelectorAll('.grid th')].map(x=>x.innerText.trim());
    await api('/api/saved-views',{method:'POST',body:{entity_type:entity,name,filters_json:r7CurrentFilters(prefix),columns_json:headers,is_shared:0}});
    toast('View saved');await r7SavedViews(entity,prefix);
  };
}

async function enhanceR13R7(r){
  try{
    const [base,id]=String(r||'').split('/');
    if(base==='candidate' && id)await r7Candidate(id);
    else if(base==='company' && id)await r7Company(id);
    else if(base==='contact' && id)await r7Contact(id);
    else if(base==='submissions')await r7SubmissionWorkspace();
    else if(base==='onboarding')await r7OnboardingTemplates();
    else if(base==='timesheets')await r7Timesheets();
    else if(base==='expenses')await r7Expenses();
    else if(base==='finance')await r7Finance();
    else if(base==='communications')await r7Communications();
    else if(base==='admin' && ME?.role==='admin')await r7Admin();
    else if(base==='dashboard' && ['admin','teamlead','recruiter','sales','hr','finance'].includes(ME?.role))await r7Dashboard();
    else if(base==='candidates')await r7SavedViews('candidates','r13-c-');
    else if(base==='jobSearch' || base==='jobs' || base==='primaryJobs')await r7SavedViews('jobs','r13-j-');
  }catch(e){console.error('R13R7 enhancement failed',e);toast('Deep operations: '+e.message,'err')}
}

const R7_ORIGINAL_ROUTE=route;
route=async function(r){
  await R7_ORIGINAL_ROUTE(r);
  await enhanceR13R7(r);
};

Object.assign(window,{R13R7_VERSION,r7Create,r7SubmitCreate,r7Delete,r7Candidate,r7Company,r7Contact,r7LoadSubmission,r7LoadTimesheet,r7LoadExpense,r7LoadInvoice,enhanceR13R7});
})();