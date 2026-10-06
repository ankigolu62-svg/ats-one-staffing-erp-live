/* ATS-One R19 — real execution surfaces. */

async function pageR19Operations(){
 const [
  campaigns,
  schedules,
  gateways,
  tx,
  alerts,
  connectors
 ]=await Promise.all([
  api('/api/r19/campaigns'),
  api('/api/r19/report-schedules'),
  api('/api/r19/external-gateways'),
  api('/api/r19/external-transactions'),
  api('/api/r19/job-alerts'),
  api('/api/integrations')
 ]);

 $('#content').innerHTML=`<div class="page">
 ${head(
   'Enterprise Execution Center',
   'R19 › Real Internal / External Execution'
 )}

 ${panel('Campaign Execution',`
 <table class="grid">
 <tr>
  <th>Name</th><th>Channel</th><th>Status</th>
  <th>Members</th><th>Delivered</th>
  <th>Connector</th><th>Action</th>
 </tr>
 ${campaigns.map(x=>`
 <tr>
  <td>${esc(x.name)}</td>
  <td>${esc(x.channel)}</td>
  <td>${status(x.status)}</td>
  <td>${x.member_count}</td>
  <td>${x.delivered_count}</td>
  <td>${status(x.connector_state)}</td>
  <td>
   <button class="btn small"
    onclick="r19RunCampaign(${x.id})">Run</button>
  </td>
 </tr>`).join('')}
 </table>`,
 `<button class="btn small"
  onclick="r19CreateInternalCampaign()">+ Campaign</button>` )}

 ${panel('Report Scheduler',`
 <table class="grid">
 <tr>
  <th>Report</th><th>Frequency</th><th>Format</th>
  <th>Recipients</th><th>Last Run</th><th>Next Run</th>
  <th>Delivery</th><th>Action</th>
 </tr>
 ${schedules.map(x=>`
 <tr>
  <td>${esc(x.report_name)}</td>
  <td>${esc(x.frequency)}</td>
  <td>${esc(x.format)}</td>
  <td>${esc(x.recipients||'')}</td>
  <td>${fmtDate(x.last_run_at)}</td>
  <td>${fmtDate(x.next_run_at)}</td>
  <td>${status(x.connector_state)}</td>
  <td>
   <button class="btn small"
    onclick="r19RunSchedule(${x.id})">Run Now</button>
  </td>
 </tr>`).join('')}
 </table>`)}

 ${panel('External Provider Gates',`
 <table class="grid">
 <tr>
  <th>Provider</th><th>Category</th><th>State</th>
  <th>Connector</th><th>Last Test</th><th>Error</th><th>Action</th>
 </tr>
 ${gateways.map(x=>`
 <tr>
  <td>${esc(x.provider)}</td>
  <td>${esc(x.category)}</td>
  <td>${status(x.connection_state)}</td>
  <td>${esc(x.connector_name||'')}</td>
  <td>${fmtDate(x.last_test_at)}</td>
  <td>${esc(x.last_error||'')}</td>
  <td>
   ${x.connector_id
    ? `<button class="btn small"
        onclick="r19TestGateway(${x.id})">Test</button>`
    : `<button class="btn small"
        onclick="r19LinkGateway(${x.id})">Link</button>`}
  </td>
 </tr>`).join('')}
 </table>`)}

 ${panel('Job Alerts',`
 <table class="grid">
 <tr>
  <th>Name</th><th>Channel</th><th>Frequency</th>
  <th>Active</th><th>Last Run</th><th>Action</th>
 </tr>
 ${alerts.map(x=>`
 <tr>
  <td>${esc(x.name)}</td>
  <td>${esc(x.channel)}</td>
  <td>${esc(x.frequency)}</td>
  <td>${x.active?'Yes':'No'}</td>
  <td>${fmtDate(x.last_run_at)}</td>
  <td>
   <button class="btn small"
    onclick="r19RunAlert(${x.id})">Run</button>
  </td>
 </tr>`).join('')}
 </table>`)}

 ${panel('External Transaction History',`
 <table class="grid">
 <tr>
  <th>Date</th><th>Category</th><th>Action</th>
  <th>Status</th><th>Provider ID</th><th>HTTP</th>
 </tr>
 ${tx.slice(0,50).map(x=>`
 <tr>
  <td>${fmtDate(x.created_at)}</td>
  <td>${esc(x.category)}</td>
  <td>${esc(x.action)}</td>
  <td>${status(x.status)}</td>
  <td>${esc(x.provider_id||'')}</td>
  <td>${x.provider_http_status??''}</td>
 </tr>`).join('')}
 </table>`)}

 <div class="callout warn">
 <b>External truth rule:</b>
 provider state becomes Connected only after an actual configured
 HTTP request succeeds. Missing customer credentials remain
 Credentials Required / Configuration Required.
 </div>
 </div>`;

 window.R19_CONNECTORS=connectors;
}

async function r19CreateInternalCampaign(){
 const candidates=REF?.candidates||[];

 modal(
  'Create Internal Campaign',
  `<form id="r19Camp">
   <div class="formgrid">
    ${formFields([
      {name:'name',label:'Name',value:'Candidate Follow-up'},
      {name:'subject',label:'Subject',value:'Follow-up'},
      {name:'body',label:'Message',type:'textarea',span:true},
      {
       name:'candidate_id',
       label:'Candidate',
       type:'select',
       options:candidates.map(x=>({
        value:x.id,
        label:x.name
       }))
      }
    ])}
   </div>
  </form>`,
  `<button class="btn" onclick="closeModal()">Cancel</button>
   <button class="btn primary"
    onclick="r19SaveCampaign()">Create</button>`
 );
}

async function r19SaveCampaign(){
 const d=fd($('#r19Camp'));
 try{
  await api('/api/r19/campaigns',{
   method:'POST',
   body:{
    name:d.name,
    channel:'Internal',
    subject:d.subject,
    body:d.body,
    candidate_ids:[Number(d.candidate_id)]
   }
  });
  closeModal();
  toast('Campaign created');
  pageR19Operations();
 }catch(e){toast(e.message,'err')}
}

async function r19RunCampaign(id){
 try{
  const r=await api(`/api/r19/campaigns/${id}/run`,{
   method:'POST',
   body:{}
  });
  toast('Campaign '+r.status);
 }catch(e){toast(e.message,'err')}
 pageR19Operations();
}

async function r19RunSchedule(id){
 try{
  const r=await api(`/api/r19/report-schedules/${id}/run`,{
   method:'POST',
   body:{}
  });
  toast(`Report ${r.status}: ${r.row_count} rows`);
 }catch(e){toast(e.message,'err')}
 pageR19Operations();
}

async function r19LinkGateway(id){
 const rows=window.R19_CONNECTORS||[];

 modal(
  'Link Real Connector',
  `<div class="field">
   <label>Connector</label>
   <select id="r19GatewayConnector">
    ${rows.map(x=>`
     <option value="${x.id}">
      ${esc(x.category)} — ${esc(x.name)}
      — ${esc(x.connection_state||x.status)}
     </option>`).join('')}
   </select>
  </div>`,
  `<button class="btn" onclick="closeModal()">Cancel</button>
   <button class="btn primary"
    onclick="r19DoLinkGateway(${id})">Link</button>`
 );
}

async function r19DoLinkGateway(id){
 const connector_id=Number(
  document.getElementById('r19GatewayConnector').value
 );
 try{
  await api(`/api/r19/external-gateways/${id}/link`,{
   method:'POST',
   body:{connector_id}
  });
  closeModal();
  toast('Gateway linked');
  pageR19Operations();
 }catch(e){toast(e.message,'err')}
}

async function r19TestGateway(id){
 try{
  const r=await api(`/api/r19/external-gateways/${id}/test`,{
   method:'POST',
   body:{}
  });
  toast('Provider test: '+r.status);
 }catch(e){toast(e.message,'err')}
 pageR19Operations();
}

async function r19RunAlert(id){
 try{
  const r=await api(`/api/r19/job-alerts/${id}/run`,{
   method:'POST',
   body:{}
  });
  toast(`${r.match_count} matching jobs`);
 }catch(e){toast(e.message,'err')}
 pageR19Operations();
}


/* Extend interview screen with real provider controls. */
const R19_PREV_INTERVIEWS=pageInterviews;

pageInterviews=async function(){
 await R19_PREV_INTERVIEWS();

 if(!ME || !['admin','teamlead','recruiter','sales','hr','finance'].includes(ME.role)){
  return;
 }

 const [rows,connectors]=await Promise.all([
  api('/api/interviews'),
  api('/api/integrations')
 ]);

 const page=document.querySelector('#content .page');
 if(!page)return;

 page.insertAdjacentHTML(
  'beforeend',
  panel(
   'Meeting Provider Execution',
   `<table class="grid">
    <tr>
     <th>Interview</th><th>Candidate</th><th>Job</th>
     <th>Provider ID</th><th>Status</th><th>Action</th>
    </tr>
    ${rows.map(x=>`
     <tr>
      <td>#${x.id}</td>
      <td>${esc((x.first_name||'')+' '+(x.last_name||''))}</td>
      <td>${esc(x.job_title||'')}</td>
      <td>${esc(x.meeting_provider_id||'')}</td>
      <td>${status(x.meeting_status||'Not Created')}</td>
      <td>
       <button class="btn small"
        onclick="r19CreateMeeting(${x.id})">Create Meeting</button>
      </td>
     </tr>`).join('')}
    </table>`
  )
 );

 window.R19_MEETING_CONNECTORS=connectors;
};

async function r19CreateMeeting(id){
 const rows=window.R19_MEETING_CONNECTORS||[];

 if(!rows.length){
  return toast('No connector configured','err');
 }

 modal(
  'Create Provider Meeting',
  `<div class="field">
   <label>Connector</label>
   <select id="r19MeetingConnector">
    ${rows.map(x=>`
     <option value="${x.id}">
      ${esc(x.category)} — ${esc(x.name)}
     </option>`).join('')}
   </select>
  </div>`,
  `<button class="btn" onclick="closeModal()">Cancel</button>
   <button class="btn primary"
    onclick="r19DoMeeting(${id})">Create</button>`
 );
}

async function r19DoMeeting(id){
 const connector_id=Number(
  document.getElementById('r19MeetingConnector').value
 );
 try{
  const r=await api(`/api/r19/interviews/${id}/meeting`,{
   method:'POST',
   body:{connector_id}
  });
  closeModal();
  toast('Meeting provider: '+r.status);
  pageInterviews();
 }catch(e){toast(e.message,'err')}
}


/* Add enterprise execution center to launcher. */
const R19_PREV_MENU=pageMenu;

pageMenu=function(){
 R19_PREV_MENU();

 const launcher=document.querySelector('.launcher');

 if(!launcher)return;

 launcher.insertAdjacentHTML(
  'beforeend',
  `<div class="module-card r19-card">
   <h3>Production Execution</h3>
   <div class="module-links">
    <div class="module-link" onclick="go('r19Ops')">
     <span class="module-ico">◆</span>
     <span class="module-name">Enterprise Execution Center</span>
    </div>
   </div>
  </div>`
 );
};

const R19_PREV_ROUTE=route;

route=async function(r){
 const base=(r||'').split('/')[0];

 if(base==='r19Ops'){
  CURRENT=r;
  const c=document.getElementById('content');
  if(c)c.innerHTML='<div class="page"><div class="panel"><div class="panel-body">Loading…</div></div></div>';
  try{
   await pageR19Operations();
  }catch(e){
   if(c)c.innerHTML=`<div class="page"><div class="panel"><div class="panel-body"><b>Unable to load.</b><br>${esc(e.message)}</div></div></div>`;
  }
  return;
 }

 await R19_PREV_ROUTE(r);
};
