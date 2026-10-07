/*
 ATS-One R18 production functional closure.
 Authentication/login code is intentionally untouched.
*/

async function pageAssignments(){
 const [rows,att]=await Promise.all([
   api('/api/assignments'),
   api('/api/attendance')
 ]);

 $('#content').innerHTML=`<div class="page">
 ${head(
   'Assignments',
   'Workforce › Assignment Record',
   '<button class="btn primary" onclick="r18AttendanceForm()">+ Attendance</button>'
 )}

 ${panel('Assignment Records',`
 <table class="grid">
 <tr>
  <th>Worker</th><th>Job</th><th>Client</th>
  <th>Status</th><th>Dates</th><th>Worksite</th>
  <th>Cost Center</th><th>Approver</th>
  <th>Bill / Pay</th><th>PO / VMS</th><th>Action</th>
 </tr>
 ${rows.map(x=>`
 <tr>
  <td>${esc(x.first_name+' '+x.last_name)}</td>
  <td>${esc(x.job_no)} · ${esc(x.job_title)}</td>
  <td>${esc(x.company_name||'')}</td>
  <td>${status(x.status)}</td>
  <td>${fmtDate(x.start_date)}<br>${fmtDate(x.end_date)}</td>
  <td>${esc(x.worksite||'')}</td>
  <td>${esc(x.cost_center||'')}</td>
  <td>${esc(x.approver_name||'')}</td>
  <td>${money(x.bill_rate)}<br>${money(x.pay_rate)}</td>
  <td>${esc(x.po_number||'')}<br>${esc(x.vms_id||'')}</td>
  <td>
   <button class="btn small"
    onclick="r18AttendanceForm(${x.id})">Attendance</button>
  </td>
 </tr>`).join('')}
 </table>`)}

 ${panel('Attendance History',`
 <table class="grid">
 <tr>
  <th>Date</th><th>Worker</th><th>Job</th>
  <th>Status</th><th>Scheduled</th><th>Worked</th>
  <th>Late</th><th>Approval</th><th>Note</th><th>Action</th>
 </tr>
 ${att.map(x=>`
 <tr>
  <td>${fmtDate(x.attendance_date||x.shift_date)}</td>
  <td>${esc((x.first_name||'')+' '+(x.last_name||''))}</td>
  <td>${esc(x.job_title||'')}</td>
  <td>${status(x.status||'')}</td>
  <td>${x.scheduled_hours??0}</td>
  <td>${x.worked_hours??0}</td>
  <td>${x.late_minutes??0}</td>
  <td>${status(x.approval_state||'Pending')}</td>
  <td>${esc(x.note||'')}</td>
  <td>
   ${String(x.approval_state||'').toLowerCase()!=='approved'
     ? `<button class="btn small success"
          onclick="r18ApproveAttendance(${x.id})">Approve</button>`
     : ''}
  </td>
 </tr>`).join('')}
 </table>`)}
 </div>`;
}

async function r18AttendanceForm(selected){
 const rows=await api('/api/assignments');

 modal(
  'Attendance Entry',
  `<form id="r18AttForm">
   <div class="formgrid">
   ${formFields([
     {
       name:'assignment_id',
       label:'Assignment',
       type:'select',
       options:rows.map(x=>({
         value:x.id,
         label:x.first_name+' '+x.last_name+' — '+x.job_title
       }))
     },
     {name:'attendance_date',label:'Date',type:'date'},
     {
       name:'status',
       label:'Status',
       type:'select',
       options:['Present','Late','Absent','PTO','Holiday']
     },
     {name:'scheduled_hours',label:'Scheduled Hours',type:'number',value:8},
     {name:'worked_hours',label:'Worked Hours',type:'number',value:8},
     {name:'late_minutes',label:'Late Minutes',type:'number',value:0},
     {name:'absence_reason',label:'Absence Reason'},
     {name:'note',label:'Note',type:'textarea',span:true}
   ])}
   </div>
  </form>`,
  `<button class="btn" onclick="closeModal()">Cancel</button>
   <button class="btn primary"
    onclick="r18SaveAttendance()">Save</button>`
 );

 if(selected){
   const el=document.querySelector(
     '#r18AttForm [name=assignment_id]'
   );
   if(el)el.value=String(selected);
 }
}

async function r18SaveAttendance(){
 try{
  await api('/api/attendance',{
    method:'POST',
    body:fd($('#r18AttForm'))
  });
  closeModal();
  toast('Attendance saved');
  pageAssignments();
 }catch(e){
  toast(e.message,'err');
 }
}

async function r18ApproveAttendance(id){
 try{
  await api('/api/attendance/'+id,{
    method:'PATCH',
    body:{approval_state:'Approved'}
  });
  toast('Attendance approved');
  pageAssignments();
 }catch(e){
  toast(e.message,'err');
 }
}


async function pageFinance(){
 const [inv,po,assignments]=await Promise.all([
   api('/api/invoices'),
   api('/api/purchase-orders'),
   api('/api/assignments')
 ]);

 $('#content').innerHTML=`<div class="page">
 ${head(
   'Financial Operations',
   'Finance › Billing / Payroll',
   '<button class="btn primary" onclick="newInvoice()">+ Invoice</button>'
 )}

 ${panel('Invoices',`
 <table class="grid">
 <tr>
  <th>Invoice</th><th>Client</th><th>Worker</th>
  <th>Period</th><th>Total</th><th>Status</th>
  <th>Due</th><th>Balance</th><th>Action</th>
 </tr>
 ${inv.map(x=>`
 <tr>
  <td>${esc(x.invoice_no)}</td>
  <td>${esc(x.company_name||'')}</td>
  <td>${esc((x.first_name||'')+' '+(x.last_name||''))}</td>
  <td>${fmtDate(x.period_start)}—${fmtDate(x.period_end)}</td>
  <td>${money((x.amount||0)+(x.tax||0)-(x.discount||0))}</td>
  <td>${status(x.status)}</td>
  <td>${fmtDate(x.due_date)}</td>
  <td>${money(x.balance||0)}</td>
  <td>
   <button class="btn small"
    onclick="r18OpenInvoice(${x.id})">Open</button>
  </td>
 </tr>`).join('')}
 </table>`)}

 <div class="two-col">
 ${panel('Purchase Orders / SOW Funding',`
 <table class="grid">
 <tr>
  <th>PO</th><th>Client</th><th>Job</th>
  <th>Amount</th><th>Dates</th><th>Status</th>
 </tr>
 ${po.map(x=>`
 <tr>
  <td>${esc(x.po_number)}</td>
  <td>${esc(x.company_name||'')}</td>
  <td>${esc((x.job_no||'')+' '+(x.job_title||''))}</td>
  <td>${money(x.amount)}</td>
  <td>${fmtDate(x.start_date)}—${fmtDate(x.end_date)}</td>
  <td>${status(x.status)}</td>
 </tr>`).join('')}
 </table>`)}

 ${panel('Assignment Margin / Spread',`
 <table class="grid">
 <tr>
  <th>Worker</th><th>Job</th><th>Bill</th>
  <th>Pay</th><th>Spread</th><th>Margin %</th>
 </tr>
 ${assignments.map(x=>{
   const spread=(x.bill_rate||0)-(x.pay_rate||0);
   const margin=x.bill_rate ? spread/x.bill_rate*100 : 0;
   return `<tr>
    <td>${esc(x.first_name+' '+x.last_name)}</td>
    <td>${esc(x.job_title)}</td>
    <td>${money(x.bill_rate)}</td>
    <td>${money(x.pay_rate)}</td>
    <td>${money(spread)}</td>
    <td>${margin.toFixed(1)}%</td>
   </tr>`;
 }).join('')}
 </table>`)}
 </div>
 </div>`;
}

async function r18OpenInvoice(id){
 try{
  const x=await api('/api/invoices/'+id);

  modal(
   'Invoice '+esc(x.invoice_no),
   `<div class="three-col">
    <div class="kv"><b>Status</b><span>${status(x.status)}</span></div>
    <div class="kv"><b>Total</b><span>${money(x.total)}</span></div>
    <div class="kv"><b>Balance</b><span>${money(x.balance)}</span></div>
   </div>

   <h3>Line Items</h3>
   <table class="grid">
   <tr><th>Description</th><th>Qty</th><th>Rate</th><th>Amount</th></tr>
   ${(x.lines||[]).map(l=>`
    <tr>
     <td>${esc(l.description)}</td>
     <td>${l.quantity}</td>
     <td>${money(l.rate)}</td>
     <td>${money(l.amount)}</td>
    </tr>`).join('')}
   </table>

   <h3>Payments</h3>
   <table class="grid">
   <tr><th>Date</th><th>Amount</th><th>Reference</th></tr>
   ${(x.payments||[]).map(p=>`
    <tr>
     <td>${fmtDate(p.payment_date)}</td>
     <td>${money(p.amount)}</td>
     <td>${esc(p.reference||'')}</td>
    </tr>`).join('')}
   </table>`,
   `<button class="btn" onclick="closeModal()">Close</button>
    ${x.status==='draft'
      ? `<button class="btn"
          onclick="r18AddLine(${x.id})">+ Line</button>
         <button class="btn primary"
          onclick="r18Issue(${x.id})">Issue</button>`
      : ''}
    ${['issued','part_paid'].includes(x.status)
      ? `<button class="btn primary"
          onclick="r18Payment(${x.id})">Record Payment</button>`
      : ''}
    ${!['paid','void'].includes(x.status)
      ? `<button class="btn danger"
          onclick="r18Void(${x.id})">Void</button>`
      : ''}`,
   true
  );

 }catch(e){
  toast(e.message,'err');
 }
}

async function r18AddLine(id){
 const description=prompt('Description');
 if(!description)return;

 const quantity=prompt('Quantity','1');
 const unit_price=prompt('Unit price','0');

 try{
  await api(`/api/invoices/${id}/lines`,{
   method:'POST',
   body:{description,quantity,unit_price}
  });
  r18OpenInvoice(id);
 }catch(e){
  toast(e.message,'err');
 }
}

async function r18Issue(id){
 try{
  await api(`/api/invoices/${id}/issue`,{
   method:'POST',
   body:{}
  });
  closeModal();
  toast('Invoice issued');
  pageFinance();
 }catch(e){
  toast(e.message,'err');
 }
}

async function r18Payment(id){
 const amount=prompt('Payment amount');
 if(!amount)return;

 const reference=prompt('Payment reference','');

 try{
  await api(`/api/invoices/${id}/payments`,{
   method:'POST',
   body:{amount,reference}
  });
  closeModal();
  toast('Payment recorded');
  pageFinance();
 }catch(e){
  toast(e.message,'err');
 }
}

async function r18Void(id){
 const reason=prompt('Void reason','Voided by authorized user');
 if(!reason)return;

 try{
  await api(`/api/invoices/${id}/void`,{
   method:'POST',
   body:{reason}
  });
  closeModal();
  toast('Invoice voided');
  pageFinance();
 }catch(e){
  toast(e.message,'err');
 }
}


async function pageVMS(){
 const [d,connectors]=await Promise.all([
   api('/api/vms'),
   api('/api/integrations')
 ]);

 $('#content').innerHTML=`<div class="page">
 ${head('VMS / MSP Synchronization','Integrations › VMS')}

 ${panel('VMS Accounts',`
 <table class="grid">
 <tr>
  <th>Account</th><th>Platform</th><th>Status</th>
  <th>Connection</th><th>Last Sync</th><th>Notes</th><th>Action</th>
 </tr>
 ${d.accounts.map(x=>`
 <tr>
  <td><b>${esc(x.name)}</b></td>
  <td>${esc(x.platform)}</td>
  <td>${status(x.status)}</td>
  <td>${status(x.connection_state||x.sync_mode)}</td>
  <td>${fmtDate(x.last_sync)}</td>
  <td>${esc(x.notes||'')}</td>
  <td>
   <button class="btn small"
    onclick="r18VmsSync(${x.id})">Sync</button>
  </td>
 </tr>`).join('')}
 </table>`)}

 ${panel('Object Mapping',`
 <table class="grid">
 <tr>
  <th>Account</th><th>Object</th><th>External ID</th>
  <th>Internal ID</th><th>External Status</th>
  <th>Internal Status</th><th>Mapping</th>
 </tr>
 ${d.mappings.map(x=>`
 <tr>
  <td>${esc(x.account_name||'')}</td>
  <td>${esc(x.object_type||'')}</td>
  <td class="mono">${esc(x.external_id||'')}</td>
  <td>${x.internal_id??''}</td>
  <td>${status(x.external_status||'')}</td>
  <td>${status(x.internal_status||'')}</td>
  <td class="mono">${esc(x.mapping_json||'')}</td>
 </tr>`).join('')}
 </table>`)}

 ${panel('Integration Registry',`
 <table class="grid">
 <tr>
  <th>Category</th><th>Connector</th><th>Mode</th>
  <th>Connection</th><th>Last Sync</th><th>Notes</th><th>Action</th>
 </tr>
 ${connectors.map(x=>`
 <tr>
  <td>${esc(x.category)}</td>
  <td>${esc(x.name)}</td>
  <td>${status(x.mode)}</td>
  <td>${status(x.connection_state||x.status)}</td>
  <td>${fmtDate(x.last_sync)}</td>
  <td>${esc(x.notes||'')}</td>
  <td>
   ${String(x.mode||'').toLowerCase()==='internal'
    ? ''
    : `<button class="btn small"
       onclick="r18Connector(${x.id},'test')">Test</button>
       <button class="btn small"
       onclick="r18Connector(${x.id},'sync')">Sync</button>`}
  </td>
 </tr>`).join('')}
 </table>`)}

 ${panel('Sync History',`
 <table class="grid">
 <tr><th>Date</th><th>Account</th><th>Status</th><th>Detail</th></tr>
 ${(d.history||[]).map(x=>`
 <tr>
  <td>${fmtDate(x.created_at)}</td>
  <td>#${x.vms_account_id}</td>
  <td>${status(x.status)}</td>
  <td>${esc(x.detail||'')}</td>
 </tr>`).join('')}
 </table>`)}

 <div class="callout warn">
  <b>Production truth gate:</b>
  an external integration becomes Connected only after an actual configured
  provider HTTP request succeeds with authorized customer credentials.
 </div>
 </div>`;
}

async function r18Connector(id,action){
 try{
  const r=await api(`/api/integrations/${id}/${action}`,{
   method:'POST',
   body:{}
  });
  toast(`${action}: ${r.status}`);
 }catch(e){
  toast(e.message,'err');
 }
 pageVMS();
}

async function r18VmsSync(id){
 try{
  const r=await api(`/api/vms/accounts/${id}/sync`,{
   method:'POST',
   body:{}
  });
  toast('VMS '+r.status);
 }catch(e){
  toast(e.message,'err');
 }
 pageVMS();
}


async function pageCommunications(){
 const canInspectIntegrations=['admin','teamlead'].includes(ME?.role);
 const [rows,connectors]=await Promise.all([
   api('/api/communications'),
   canInspectIntegrations ? api('/api/integrations').catch(()=>[]) : Promise.resolve([])
 ]);

 const providers=connectors.filter(
   x=>String(x.category||'').toLowerCase()==='communication'
 );

 $('#content').innerHTML=`<div class="page">
 ${head(
   'Communication Center',
   'Engagement › Email / SMS / Calls',
   '<button class="btn primary" onclick="r18Compose()">+ Communication</button>'
 )}

 ${panel('Provider State',
   providers.map(x=>`
    <div class="kv">
     <b>${esc(x.name)}</b>
     <span>${status(x.connection_state||x.status)}</span>
    </div>`).join('')
   || '<div class="empty">No production communication provider configured.</div>'
 )}

 ${panel('Activity Stream',`
 <table class="grid">
 <tr>
  <th>Date</th><th>Entity</th><th>Channel</th>
  <th>Direction</th><th>Subject</th><th>User</th><th>Status</th>
 </tr>
 ${rows.map(x=>`
 <tr>
  <td>${new Date(x.created_at).toLocaleString()}</td>
  <td>${esc(x.entity_type)} #${x.entity_id}</td>
  <td>${esc(x.channel)}</td>
  <td>${esc(x.direction)}</td>
  <td>${esc(x.subject||'')}</td>
  <td>${esc(x.user_name||'')}</td>
  <td>${status(x.status)}</td>
 </tr>`).join('')}
 </table>`)}
 </div>`;
}

async function r18Compose(){
 const connectors=await api('/api/integrations').catch(()=>[]);

 const providers=connectors.filter(
   x=>String(x.category||'').toLowerCase()==='communication'
 );

 modal(
  'Communication',
  `<form id="r18Comm">
   <div class="formgrid">
   ${formFields([
    {
      name:'channel',
      label:'Channel',
      type:'select',
      options:['Internal','Email','SMS','Call']
    },
    {
      name:'connector_id',
      label:'Provider',
      type:'select',
      options:[
       {value:'',label:'None / Internal'},
       ...providers.map(x=>({
        value:x.id,
        label:x.name+' — '+(x.connection_state||x.status)
       }))
      ]
    },
    {name:'entity_type',label:'Entity Type',value:'candidate'},
    {name:'entity_id',label:'Entity ID',type:'number'},
    {name:'to',label:'To'},
    {name:'subject',label:'Subject'},
    {name:'body',label:'Message',type:'textarea',span:true}
   ])}
   </div>
  </form>`,
  `<button class="btn" onclick="closeModal()">Cancel</button>
   <button class="btn primary"
    onclick="r18SendCommunication()">Send</button>`
 );
}

async function r18SendCommunication(){
 try{
  await api('/api/communications/send',{
   method:'POST',
   body:fd($('#r18Comm'))
  });
  closeModal();
  toast('Communication processed');
  pageCommunications();
 }catch(e){
  toast(e.message,'err');
 }
}
