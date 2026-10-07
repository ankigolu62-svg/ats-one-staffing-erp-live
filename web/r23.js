/* ATS-One R23B Enterprise RBAC / Teams / Profiles */

let R23_CONTEXT = null;

async function r23LoadContext(){
  try{
    R23_CONTEXT = await api('/api/r23/context');
    return R23_CONTEXT;
  }catch(_){
    return null;
  }
}

function r23RouteModule(route){
  return ({
    dashboard:'dashboard',
    talent:'talent',
    boolean:'talent',
    candidates:'candidate',
    candidate:'candidate',
    hotlists:'hotlist',
    jobs:'job',
    job:'job',
    companies:'crm',
    contacts:'crm',
    submissions:'submission',
    interviews:'interview',
    assessments:'assessment',
    onboarding:'onboarding',
    assignments:'assignment',
    timesheets:'timesheet',
    expenses:'expense',
    finance:'finance',
    vms:'vms',
    suppliers:'supplier',
    communications:'communication',
    reports:'report',
    admin:'admin',
    audit:'audit'
  })[route];
}

async function r23EnhanceShell(){
  const ctx = await r23LoadContext();
  if(!ctx) return;

  const chip = document.querySelector('.user-chip');
  if(chip && ctx.selected){
    const role = chip.querySelector('.muted');
    if(role){
      role.textContent =
        `${ctx.selected.profile_name} · ${ctx.selected.team_name}`;
    }
  }

  const perms = new Map(
    (ctx.permissions || []).map(x => [x.module,x])
  );

  document.querySelectorAll('.navitem[data-route]').forEach(el=>{
    const route=(el.dataset.route||'').split('/')[0];
    const module=r23RouteModule(route);
    if(!module) return;
    const p=perms.get(module);
    if(!p || Number(p.can_view)!==1){
      el.style.display='none';
    }
  });

  if((ctx.assignments||[]).length > 1 && chip){
    let select=document.getElementById('r23-context-select');

    if(!select){
      select=document.createElement('select');
      select.id='r23-context-select';
      select.style.maxWidth='260px';
      select.style.marginLeft='8px';
      select.onchange=()=>r23SwitchContext(select.value);
      chip.parentNode.insertBefore(select,chip);
    }

    select.innerHTML=(ctx.assignments||[]).map(a=>{
      const value=`${a.team_id}:${a.profile_id}`;
      const selected=
        ctx.selected &&
        Number(ctx.selected.team_id)===Number(a.team_id) &&
        Number(ctx.selected.profile_id)===Number(a.profile_id);

      return `<option value="${esc(value)}" ${selected?'selected':''}>
        ${esc(a.profile_name)} · ${esc(a.team_name)}
      </option>`;
    }).join('');
  }
}

async function r23SwitchContext(value){
  const [team_id,profile_id]=String(value).split(':').map(Number);

  await api('/api/r23/session-context',{
    method:'POST',
    body:{team_id,profile_id}
  });

  await boot();
  toast('Team / profile switched');
}

const R23_ORIGINAL_RENDER_SHELL=renderShell;

renderShell=function(){
  R23_ORIGINAL_RENDER_SHELL();
  r23EnhanceShell().catch(()=>{});
};

function r23PermissionCheckbox(p,key){
  return `<input type="checkbox" data-k="${key}"
    ${Number(p?.[key]||0)===1?'checked':''}>`;
}

async function r23EditPermissions(id){
  const d=await api(`/api/r23/role-profiles/${id}/permissions`);
  const by=new Map((d.permissions||[]).map(x=>[x.module,x]));

  const rows=(d.modules||[]).map(module=>{
    const p=by.get(module)||{module,data_scope:'all'};

    return `<tr data-module="${esc(module)}">
      <td><b>${esc(module)}</b></td>
      <td>${r23PermissionCheckbox(p,'can_view')}</td>
      <td>${r23PermissionCheckbox(p,'can_create')}</td>
      <td>${r23PermissionCheckbox(p,'can_edit')}</td>
      <td>${r23PermissionCheckbox(p,'can_delete')}</td>
      <td>${r23PermissionCheckbox(p,'can_approve')}</td>
      <td>${r23PermissionCheckbox(p,'can_export')}</td>
      <td>${r23PermissionCheckbox(p,'can_admin')}</td>
      <td>${r23PermissionCheckbox(p,'can_financial')}</td>
      <td>${r23PermissionCheckbox(p,'can_documents')}</td>
      <td>
        <select class="r23-scope">
          <option value="own" ${p.data_scope==='own'?'selected':''}>Own</option>
          <option value="team" ${p.data_scope==='team'?'selected':''}>Team</option>
          <option value="all" ${p.data_scope==='all'?'selected':''}>All</option>
        </select>
      </td>
    </tr>`;
  }).join('');

  modal(
    `Permissions — ${d.profile.name}`,
    `<div class="tablewrap">
      <table class="grid">
        <tr>
          <th>Module</th><th>View</th><th>Create</th><th>Edit</th>
          <th>Delete</th><th>Approve</th><th>Export</th>
          <th>Admin</th><th>Financial</th><th>Documents</th><th>Scope</th>
        </tr>
        ${rows}
      </table>
    </div>`,
    `<button class="btn" onclick="closeModal()">Cancel</button>
     <button class="btn primary" onclick="r23SavePermissions(${Number(id)})">
       Save Permissions
     </button>`,
    true
  );
}

async function r23SavePermissions(id){
  const permissions=[...document.querySelectorAll('#modalRoot tr[data-module]')]
    .map(tr=>{
      const x={
        module:tr.dataset.module,
        data_scope:tr.querySelector('.r23-scope').value
      };

      tr.querySelectorAll('input[data-k]').forEach(cb=>{
        x[cb.dataset.k]=cb.checked;
      });

      return x;
    });

  await api(`/api/r23/role-profiles/${id}/permissions`,{
    method:'POST',
    body:{permissions}
  });

  closeModal();
  toast('Permissions saved');
  await pageAdmin();
}

async function r23CreateProfile(){
  const all=await api('/api/r23/role-profiles');
  const bases=[...new Set(all.map(x=>x.base_role))];

  modal(
    'Create Role / Profile',
    `<form id="r23-profile-form"><div class="formgrid">
      ${formFields([
        {name:'name',label:'Profile Name',required:true},
        {
          name:'base_role',
          label:'Base Security Role',
          type:'select',
          options:bases
        },
        {
          name:'data_scope',
          label:'Default Data Scope',
          type:'select',
          options:['own','team','all'],
          value:'team'
        },
        {
          name:'description',
          label:'Description',
          type:'textarea',
          span:true
        }
      ])}
    </div></form>`,
    `<button class="btn" onclick="closeModal()">Cancel</button>
     <button class="btn primary" onclick="r23SubmitProfile()">Create</button>`
  );
}

async function r23SubmitProfile(){
  const body=fd(document.getElementById('r23-profile-form'));

  await api('/api/r23/role-profiles',{
    method:'POST',
    body
  });

  closeModal();
  toast('Profile created');
  await pageAdmin();
}

async function r23CloneProfile(id){
  const name=prompt('Clone profile as','Custom Profile Copy');
  if(!name) return;

  await api(`/api/r23/role-profiles/${id}/clone`,{
    method:'POST',
    body:{name}
  });

  toast('Profile cloned');
  await pageAdmin();
}

async function r23RenameProfile(id,currentName){
  const name=prompt('Rename profile',currentName||'');
  if(!name || name===currentName) return;

  await api(`/api/r23/role-profiles/${id}/rename`,{
    method:'POST',
    body:{name}
  });

  toast('Profile renamed');
  await pageAdmin();
}

async function r23ToggleProfile(id,active){
  await api(`/api/r23/role-profiles/${id}/deactivate`,{
    method:'POST',
    body:{active:!active}
  });

  toast(active?'Profile deactivated':'Profile activated');
  await pageAdmin();
}

async function r23CreateTeam(){
  const name=prompt('Team name');
  if(!name) return;

  await api('/api/r23/teams',{
    method:'POST',
    body:{name}
  });

  toast('Team created');
  await pageAdmin();
}

async function r23AssignUser(){
  const [users,teams,profiles]=await Promise.all([
    api('/api/r23/users-context'),
    api('/api/r23/teams'),
    api('/api/r23/role-profiles')
  ]);

  modal(
    'Assign User to Team / Profile',
    `<form id="r23-assignment-form"><div class="formgrid">
      <div class="field">
        <label>User</label>
        <select name="user_id">
          ${users.filter(x=>x.active).map(
            x=>`<option value="${x.id}">${esc(x.name)} · ${esc(x.email)}</option>`
          ).join('')}
        </select>
      </div>

      <div class="field">
        <label>Team</label>
        <select name="team_id">
          ${teams.filter(x=>x.active).map(
            x=>`<option value="${x.id}">${esc(x.name)}</option>`
          ).join('')}
        </select>
      </div>

      <div class="field">
        <label>Profile</label>
        <select name="profile_id">
          ${profiles.filter(x=>x.active).map(
            x=>`<option value="${x.id}">${esc(x.name)} (${esc(x.base_role)})</option>`
          ).join('')}
        </select>
      </div>

      <div class="field">
        <label>Primary</label>
        <select name="is_primary">
          <option value="0">No</option>
          <option value="1">Yes</option>
        </select>
      </div>
    </div></form>`,
    `<button class="btn" onclick="closeModal()">Cancel</button>
     <button class="btn primary" onclick="r23SubmitAssignment()">Assign</button>`
  );
}

async function r23SubmitAssignment(){
  const d=fd(document.getElementById('r23-assignment-form'));

  await api(`/api/r23/teams/${Number(d.team_id)}/members`,{
    method:'POST',
    body:{
      user_id:Number(d.user_id),
      profile_id:Number(d.profile_id),
      is_primary:d.is_primary==='1'
    }
  });

  closeModal();
  toast('Team/profile assignment saved');
  await pageAdmin();
}

async function r23EnhanceAdmin(){
  if(ME?.role!=='admin') return;

  const [profiles,teams,users,access,release,help]=await Promise.all([
    api('/api/r23/role-profiles'),
    api('/api/r23/teams'),
    api('/api/r23/users-context'),
    api('/api/r23/access-log?limit=25'),
    api('/api/r23/release-notes'),
    api('/api/r23/help')
  ]);

  const page=document.querySelector('#content .page');
  if(!page) return;

  const profileRows=profiles.map(p=>`
    <tr>
      <td>
        <b>${esc(p.name)}</b><br>
        <small>${esc(p.slug)}</small>
      </td>
      <td>${esc(p.base_role)}</td>
      <td>${p.active?'Active':'Inactive'}</td>
      <td>
        <button class="btn small" onclick="r23EditPermissions(${p.id})">
          Permissions
        </button>
        <button class="btn small" onclick="r23CloneProfile(${p.id})">
          Clone
        </button>
        <button class="btn small"
          onclick="r23RenameProfile(${p.id},'${String(p.name).replaceAll("'","\\'")}')">
          Rename
        </button>
        ${p.is_system?'':`
          <button class="btn small"
            onclick="r23ToggleProfile(${p.id},${p.active?1:0})">
            ${p.active?'Deactivate':'Activate'}
          </button>
        `}
      </td>
    </tr>
  `).join('');

  const teamRows=teams.map(t=>`
    <tr>
      <td>${esc(t.name)}</td>
      <td>${esc(t.code)}</td>
      <td>${t.active?'Active':'Inactive'}</td>
    </tr>
  `).join('');

  const userRows=users.map(u=>`
    <tr>
      <td>${esc(u.name)}</td>
      <td>${esc(u.role)}</td>
      <td>
        ${(u.assignments||[]).map(
          a=>`${esc(a.profile_name)} @ ${esc(a.team_name)}${a.is_primary?' ★':''}`
        ).join('<br>')}
      </td>
    </tr>
  `).join('');

  page.insertAdjacentHTML('beforeend',panel(
    'Enterprise Role Profiles',
    `<div style="margin-bottom:10px">
      <button class="btn primary" onclick="r23CreateProfile()">+ Profile</button>
    </div>
    <div class="tablewrap">
      <table class="grid">
        <tr>
          <th>Profile</th><th>Base Role</th><th>Status</th><th>Actions</th>
        </tr>
        ${profileRows}
      </table>
    </div>`
  ));

  page.insertAdjacentHTML('beforeend',panel(
    'Teams & Membership',
    `<div style="margin-bottom:10px">
      <button class="btn primary" onclick="r23CreateTeam()">+ Team</button>
      <button class="btn" onclick="r23AssignUser()">Assign User</button>
    </div>
    <div class="two-col">
      <div>
        <table class="grid">
          <tr><th>Team</th><th>Code</th><th>Status</th></tr>
          ${teamRows}
        </table>
      </div>
      <div>
        <table class="grid">
          <tr><th>User</th><th>Base Role</th><th>Team / Profile</th></tr>
          ${userRows}
        </table>
      </div>
    </div>`
  ));

  page.insertAdjacentHTML('beforeend',panel(
    'Access Log',
    `<table class="grid">
      <tr><th>When</th><th>User</th><th>Event</th><th>Path</th></tr>
      ${access.map(x=>`
        <tr>
          <td>${esc(x.created_at)}</td>
          <td>${esc(x.user_id??'')}</td>
          <td>${esc(x.event_type)}</td>
          <td>${esc(x.path||'')}</td>
        </tr>
      `).join('')}
    </table>`
  ));

  page.insertAdjacentHTML('beforeend',panel(
    "What's New / Release Notes",
    release.map(x=>`
      <div class="kv">
        <b>${esc(x.version)} · ${esc(x.title)}</b>
        <span>${esc(x.published_at)}</span>
      </div>
      <p>${esc(x.body)}</p>
    `).join('')
  ));

  page.insertAdjacentHTML('beforeend',panel(
    'Help / Best Practices',
    help.map(x=>`
      <div style="margin-bottom:10px">
        <b>${esc(x.category)} · ${esc(x.title)}</b>
        <div>${esc(x.body)}</div>
      </div>
    `).join('')
  ));
}

const R23_ORIGINAL_PAGE_ADMIN=pageAdmin;

pageAdmin=async function(){
  await R23_ORIGINAL_PAGE_ADMIN();
  await r23EnhanceAdmin();
};
