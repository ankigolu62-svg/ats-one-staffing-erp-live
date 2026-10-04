/* ==============================================================
   ATS-ONE R12B — INTERNAL OPERATIONS UI
   ============================================================== */

(function(){

'use strict';

const R12B_VERSION =
    'R12B_INTERNAL_UI_1';

function actions(){
    return document.querySelector(
        '.pagehead .actions'
    );
}

function pageRoot(){
    return document.querySelector(
        '#content .page'
    );
}

function addAction(
    id,
    label,
    fn,
    css='btn'
){
    const bar=actions();

    if(!bar)return;

    if(
        document.getElementById(id)
    ){
        return;
    }

    const b=document.createElement(
        'button'
    );

    b.id=id;
    b.type='button';
    b.className=css;
    b.textContent=label;
    b.onclick=fn;

    bar.appendChild(b);
}

function panelBlock(
    id,
    title,
    html
){
    const root=pageRoot();

    if(!root)return;

    document
        .getElementById(id)
        ?.remove();

    const p=document.createElement(
        'div'
    );

    p.id=id;
    p.className='panel r12b-panel';

    p.innerHTML=
        `<div class="panel-title">
            <span>${esc(title)}</span>
            <span class="tag">
                Operations
            </span>
         </div>
         <div class="panel-body">
            ${html}
         </div>`;

    root.appendChild(p);
}

function opts(
    rows,
    labelFn
){
    return (rows||[])
        .map(
            x=>
                `<option value="${x.id}">
                    ${esc(labelFn(x))}
                 </option>`
        )
        .join('');
}

function selected(id){
    return Number(
        document
            .getElementById(id)
            ?.value
        ||0
    );
}

function err(e){
    toast(
        e?.message||String(e),
        'err'
    );
}


/* ==============================================================
   CANDIDATE
   ============================================================== */

async function editCandidate(id){

    try{
        const c=await api(
            `/api/candidates/${id}`
        );

        modal(
            'Edit Candidate',
            `<form id="r12CandidateForm">
             <div class="formgrid">
             ${formFields([
                {
                    name:'first_name',
                    label:'First Name',
                    value:c.first_name||''
                },
                {
                    name:'last_name',
                    label:'Last Name',
                    value:c.last_name||''
                },
                {
                    name:'email',
                    label:'Email',
                    value:c.email||''
                },
                {
                    name:'phone',
                    label:'Phone',
                    value:c.phone||''
                },
                {
                    name:'current_title',
                    label:'Current Title',
                    value:c.current_title||''
                },
                {
                    name:'profession',
                    label:'Profession',
                    value:c.profession||''
                },
                {
                    name:'specialty',
                    label:'Specialty',
                    value:c.specialty||''
                }
             ])}
             </div>
             </form>`,
            `<button class="btn"
                onclick="closeModal()">
                Cancel
             </button>
             <button class="btn primary"
                onclick="r12SaveCandidate(${id})">
                Save Candidate
             </button>`,
            true
        );

    }catch(e){
        err(e);
    }
}

async function saveCandidate(id){

    try{
        await api(
            `/api/candidates/${id}`,
            {
                method:'PATCH',
                body:fd(
                    document.getElementById(
                        'r12CandidateForm'
                    )
                )
            }
        );

        closeModal();
        toast('Candidate updated');

        await pageCandidate(id);

    }catch(e){
        err(e);
    }
}

async function restoreCandidates(){

    try{
        const rows=await api(
            '/api/candidates?include_archived=1'
        );

        const archived=rows.filter(
            x=>
                String(x.status||'')
                    .toLowerCase()
                ==='archived'
                ||x.archived_at
        );

        if(!archived.length){
            return toast(
                'No archived candidates'
            );
        }

        modal(
            'Restore Candidate',
            `<select id="r12ArchivedCandidate">
             ${opts(
                archived,
                x=>
                    `${x.first_name} ${x.last_name}`
             )}
             </select>`,
            `<button class="btn"
                onclick="closeModal()">
                Cancel
             </button>
             <button class="btn primary"
                onclick="r12RestoreCandidateNow()">
                Restore
             </button>`
        );

    }catch(e){
        err(e);
    }
}

async function restoreCandidateNow(){

    try{
        const id=selected(
            'r12ArchivedCandidate'
        );

        await api(
            `/api/candidates/${id}`,
            {
                method:'PATCH',
                body:{
                    status:'Active'
                }
            }
        );

        closeModal();
        toast('Candidate restored');

        await pageCandidates();

    }catch(e){
        err(e);
    }
}


/* ==============================================================
   HOTLIST RESTORE
   ============================================================== */

async function restoreHotlists(){

    try{
        const rows=await api(
            '/api/hotlists-archive'
        );

        if(!rows.length){
            return toast(
                'No archived hotlists'
            );
        }

        modal(
            'Restore Hotlist',
            `<select id="r12ArchivedHotlist">
             ${opts(
                rows,
                x=>x.name
             )}
             </select>`,
            `<button class="btn"
                onclick="closeModal()">
                Cancel
             </button>
             <button class="btn primary"
                onclick="r12RestoreHotlistNow()">
                Restore
             </button>`
        );

    }catch(e){
        err(e);
    }
}

async function restoreHotlistNow(){

    try{
        const id=selected(
            'r12ArchivedHotlist'
        );

        await api(
            `/api/hotlists/${id}`,
            {
                method:'PATCH',
                body:{
                    archived_at:null
                }
            }
        );

        closeModal();
        toast('Hotlist restored');

        await pageHotlists();

    }catch(e){
        err(e);
    }
}


/* ==============================================================
   JOB
   ============================================================== */

async function editJob(id){

    try{
        const j=await api(
            `/api/jobs/${id}`
        );

        modal(
            'Edit Job',
            `<form id="r12JobForm">
             <div class="formgrid">
             ${formFields([
                {
                    name:'title',
                    label:'Title',
                    value:j.title||''
                },
                {
                    name:'priority',
                    label:'Priority',
                    type:'select',
                    options:[
                        'Normal',
                        'High',
                        'Urgent'
                    ],
                    value:j.priority||'Normal'
                },
                {
                    name:'profession',
                    label:'Profession',
                    value:j.profession||''
                },
                {
                    name:'specialty',
                    label:'Specialty',
                    value:j.specialty||''
                },
                {
                    name:'required_skills',
                    label:'Required Skills',
                    type:'textarea',
                    span:true,
                    value:j.required_skills||''
                },
                {
                    name:'description',
                    label:'Description',
                    type:'textarea',
                    span:true,
                    value:j.description||''
                }
             ])}
             </div>
             </form>`,
            `<button class="btn"
                onclick="closeModal()">
                Cancel
             </button>
             <button class="btn primary"
                onclick="r12SaveJob(${id})">
                Save Job
             </button>`,
            true
        );

    }catch(e){
        err(e);
    }
}

async function saveJob(id){

    try{
        await api(
            `/api/jobs/${id}`,
            {
                method:'PATCH',
                body:fd(
                    document.getElementById(
                        'r12JobForm'
                    )
                )
            }
        );

        closeModal();
        toast('Job updated');

        await pageJob(id);

    }catch(e){
        err(e);
    }
}

async function restoreJobs(){

    try{
        const rows=await api(
            '/api/jobs?include_archived=1'
        );

        const archived=rows.filter(
            x=>
                x.archived_at
                ||String(x.status||'')
                    .toLowerCase()
                ==='archived'
        );

        if(!archived.length){
            return toast(
                'No archived jobs'
            );
        }

        modal(
            'Restore Job',
            `<select id="r12ArchivedJob">
             ${opts(
                archived,
                x=>
                    `${x.job_no} — ${x.title}`
             )}
             </select>`,
            `<button class="btn"
                onclick="closeModal()">
                Cancel
             </button>
             <button class="btn primary"
                onclick="r12RestoreJobNow()">
                Restore
             </button>`
        );

    }catch(e){
        err(e);
    }
}

async function restoreJobNow(){

    try{
        const id=selected(
            'r12ArchivedJob'
        );

        await api(
            `/api/jobs/${id}`,
            {
                method:'PATCH',
                body:{
                    status:'Open'
                }
            }
        );

        closeModal();
        toast('Job restored');

        await pageJobs();

    }catch(e){
        err(e);
    }
}

async function jobTeam(id){

    try{
        // R12C_FRESH_JOB_TEAM_REFERENCE
        const [j,freshRef]=await Promise.all([
            api(`/api/jobs/${id}`),
            api('/api/reference')
        ]);

        const jobUsers=
            freshRef.users||[];


        modal(
            'Job Team',
            `<div class="codeblock">
             ${
                (j.users||[])
                    .map(
                        x=>
                            `${esc(x.name)}
                             — ${esc(x.role_name)}`
                    )
                    .join('<br>')
                ||'No users assigned'
             }
             </div>

             <label>User</label>
             <select id="r12JobUser">
             ${opts(
                jobUsers,
                x=>
                    `${x.name} — ${x.role}`
             )}
             </select>

             <label>Role</label>
             <select id="r12JobRole">
                <option>
                    Primary Recruiter
                </option>
                <option>
                    Secondary Recruiter
                </option>
                <option>
                    Sales
                </option>
                <option>
                    Coordinator
                </option>
             </select>`,
            `<button class="btn"
                onclick="closeModal()">
                Close
             </button>
             <button class="btn primary"
                onclick="r12AssignJobUser(${id})">
                Assign
             </button>`,
            true
        );

    }catch(e){
        err(e);
    }
}

async function assignJobUser(id){

    try{
        await api(
            `/api/jobs/${id}/users`,
            {
                method:'POST',
                body:{
                    user_id:selected(
                        'r12JobUser'
                    ),
                    role_name:
                        document
                            .getElementById(
                                'r12JobRole'
                            )
                            .value
                }
            }
        );

        closeModal();
        toast('Job team updated');

        await pageJob(id);

    }catch(e){
        err(e);
    }
}


/* ==============================================================
   CRM
   ============================================================== */

async function crmPanel(){

    try{
        const [
            companies,
            contacts,
            leads,
            opportunities
        ]=await Promise.all([
            api('/api/companies'),
            api('/api/contacts'),
            api('/api/leads'),
            api('/api/opportunities')
        ]);

        panelBlock(
            'r12-crm-panel',
            'CRM Lifecycle Operations',
            `<div class="r12-grid">

             <div>
                <label>Company</label>
                <select id="r12Company">
                ${opts(
                    companies,
                    x=>x.name
                )}
                </select>
                <button class="btn small"
                    onclick="r12EditCompany()">
                    Edit Company
                </button>
             </div>

             <div>
                <label>Contact</label>
                <select id="r12Contact">
                ${opts(
                    contacts,
                    x=>
                        `${x.first_name} ${x.last_name}`
                )}
                </select>
                <button class="btn small"
                    onclick="r12EditContact()">
                    Edit Contact
                </button>
             </div>

             <div>
                <label>Lead</label>
                <select id="r12Lead">
                ${opts(
                    leads,
                    x=>
                        `${x.title} — ${x.status}`
                )}
                </select>
                <button class="btn small"
                    onclick="r12ConvertLead()">
                    Convert Lead
                </button>
             </div>

             <div>
                <label>Opportunity</label>
                <select id="r12Opportunity">
                ${opts(
                    opportunities,
                    x=>
                        `${x.name} — ${x.stage}`
                )}
                </select>
                <button class="btn small"
                    onclick="r12OpportunityStage()">
                    Update Stage
                </button>
             </div>

             </div>`
        );

    }catch(e){
        err(e);
    }
}

async function editCompany(){

    try{
        const id=selected(
            'r12Company'
        );

        const rows=await api(
            '/api/companies'
        );

        const c=rows.find(
            x=>x.id===id
        );

        if(!c)return;

        modal(
            'Edit Company',
            `<form id="r12CompanyForm">
             <div class="formgrid">
             ${formFields([
                {
                    name:'name',
                    label:'Name',
                    value:c.name||''
                },
                {
                    name:'industry',
                    label:'Industry',
                    value:c.industry||''
                },
                {
                    name:'status',
                    label:'Status',
                    value:c.status||'Active'
                },
                {
                    name:'submission_guidelines',
                    label:'Submission Guidelines',
                    type:'textarea',
                    span:true,
                    value:c.submission_guidelines||''
                }
             ])}
             </div></form>`,
            `<button class="btn"
                onclick="closeModal()">
                Cancel
             </button>
             <button class="btn primary"
                onclick="r12SaveCompany(${id})">
                Save
             </button>`
        );

    }catch(e){
        err(e);
    }
}

async function saveCompany(id){

    try{
        await api(
            `/api/companies/${id}`,
            {
                method:'PATCH',
                body:fd(
                    document.getElementById(
                        'r12CompanyForm'
                    )
                )
            }
        );

        closeModal();
        toast('Company updated');

        await pageCompanies();

    }catch(e){
        err(e);
    }
}

async function editContact(){

    try{
        const id=selected(
            'r12Contact'
        );

        const rows=await api(
            '/api/contacts'
        );

        const c=rows.find(
            x=>x.id===id
        );

        if(!c)return;

        modal(
            'Edit Contact',
            `<form id="r12ContactForm">
             <div class="formgrid">
             ${formFields([
                {
                    name:'first_name',
                    label:'First Name',
                    value:c.first_name||''
                },
                {
                    name:'last_name',
                    label:'Last Name',
                    value:c.last_name||''
                },
                {
                    name:'title',
                    label:'Title',
                    value:c.title||''
                },
                {
                    name:'email',
                    label:'Email',
                    value:c.email||''
                },
                {
                    name:'phone',
                    label:'Phone',
                    value:c.phone||''
                },
                {
                    name:'status',
                    label:'Status',
                    value:c.status||'Active'
                }
             ])}
             </div></form>`,
            `<button class="btn"
                onclick="closeModal()">
                Cancel
             </button>
             <button class="btn primary"
                onclick="r12SaveContact(${id})">
                Save
             </button>`
        );

    }catch(e){
        err(e);
    }
}

async function saveContact(id){

    try{
        await api(
            `/api/contacts/${id}`,
            {
                method:'PATCH',
                body:fd(
                    document.getElementById(
                        'r12ContactForm'
                    )
                )
            }
        );

        closeModal();
        toast('Contact updated');

        await pageContacts();

    }catch(e){
        err(e);
    }
}

async function convertLead(){

    try{
        const id=selected(
            'r12Lead'
        );

        const value=prompt(
            'Opportunity value',
            '50000'
        );

        if(value===null)return;

        await api(
            `/api/leads/${id}/convert`,
            {
                method:'POST',
                body:{
                    value:Number(value||0),
                    probability:25
                }
            }
        );

        toast('Lead converted');

        await pageCompanies();

    }catch(e){
        err(e);
    }
}

async function opportunityStage(){

    try{
        const id=selected(
            'r12Opportunity'
        );

        const stage=prompt(
            'Stage',
            'Negotiation'
        );

        if(!stage)return;

        await api(
            `/api/opportunities/${id}`,
            {
                method:'PATCH',
                body:{
                    stage:stage
                }
            }
        );

        toast('Opportunity stage updated');

        await pageCompanies();

    }catch(e){
        err(e);
    }
}


/* ==============================================================
   INTERVIEW
   ============================================================== */

async function interviewPanel(){

    try{
        const rows=await api(
            '/api/interviews'
        );

        panelBlock(
            'r12-interview-panel',
            'Interview Feedback / Rating',
            `<select id="r12Interview">
             ${opts(
                rows,
                x=>
                    `${x.first_name} ${x.last_name}
                     — ${x.job_title}
                     — ${x.status}`
             )}
             </select>

             <button class="btn small"
                onclick="r12InterviewFeedback()">
                Feedback / Rating
             </button>`
        );

    }catch(e){
        err(e);
    }
}

async function interviewFeedback(){

    try{
        const id=selected(
            'r12Interview'
        );

        const rows=await api(
            '/api/interviews'
        );

        const x=rows.find(
            r=>r.id===id
        );

        modal(
            'Interview Feedback',
            `<form id="r12InterviewForm">
             <div class="formgrid">
             ${formFields([
                {
                    name:'feedback',
                    label:'Feedback',
                    type:'textarea',
                    span:true,
                    value:x?.feedback||''
                },
                {
                    name:'rating',
                    label:'Rating',
                    type:'number',
                    value:x?.rating||''
                }
             ])}
             </div></form>`,
            `<button class="btn"
                onclick="closeModal()">
                Cancel
             </button>
             <button class="btn primary"
                onclick="r12SaveInterview(${id})">
                Save
             </button>`
        );

    }catch(e){
        err(e);
    }
}

async function saveInterview(id){

    try{
        await api(
            `/api/interviews/${id}`,
            {
                method:'PATCH',
                body:fd(
                    document.getElementById(
                        'r12InterviewForm'
                    )
                )
            }
        );

        closeModal();
        toast('Interview feedback saved');

        await pageInterviews();

    }catch(e){
        err(e);
    }
}


/* ==============================================================
   ASSESSMENT
   ============================================================== */

async function assessmentPanel(){

    try{
        const rows=await api(
            '/api/assessments'
        );

        panelBlock(
            'r12-assessment-panel',
            'Assessment Review / Scoring',
            `<select id="r12Assessment">
             ${opts(
                rows,
                x=>
                    `${x.first_name} ${x.last_name}
                     — ${x.title}
                     — ${x.status}`
             )}
             </select>

             <button class="btn small"
                onclick="r12AssessmentReview()">
                Review / Score
             </button>`
        );

    }catch(e){
        err(e);
    }
}

async function assessmentReview(){

    try{
        const id=selected(
            'r12Assessment'
        );

        const a=await api(
            `/api/assessments/${id}`
        );

        const answers=
            Object.fromEntries(
                (a.answers||[])
                    .map(
                        x=>[
                            x.question_id,
                            x
                        ]
                    )
            );

        let html='';

        if(
            (a.questions||[]).length
        ){
            html=
                a.questions
                    .map(
                        (q,i)=>{
                            const old=
                                answers[q.id]
                                ||{};

                            return `
                            <div class="r12-question">
                                <b>
                                    ${i+1}.
                                    ${esc(q.prompt)}
                                </b>

                                <input
                                    class="r12-answer"
                                    data-q="${q.id}"
                                    value="${esc(old.answer||'')}"
                                    placeholder="Reviewed answer"
                                >

                                <input
                                    class="r12-points"
                                    data-p="${q.id}"
                                    type="number"
                                    min="0"
                                    max="${q.points||1}"
                                    value="${old.awarded_points||0}"
                                >

                                <small>
                                    Max ${q.points||1}
                                </small>
                            </div>`;
                        }
                    )
                    .join('');

        }else{
            html=`
                <p class="subtle">
                    No assessment questions.
                </p>
                <label>Score</label>
                <input
                    id="r12DirectScore"
                    type="number"
                    value="${a.score||0}"
                >`;
        }

        modal(
            'Assessment Review',
            `<div id="r12AssessmentReview">
                ${html}
             </div>`,
            `<button class="btn"
                onclick="closeModal()">
                Cancel
             </button>
             <button class="btn primary"
                onclick="r12SaveAssessment(
                    ${id},
                    ${(a.questions||[]).length}
                )">
                Complete Review
             </button>`,
            true
        );

    }catch(e){
        err(e);
    }
}

async function saveAssessment(
    id,
    questionCount
){

    try{
        if(questionCount){

            const answers=[
                ...document.querySelectorAll(
                    '.r12-answer'
                )
            ].map(
                a=>{
                    const q=Number(
                        a.dataset.q
                    );

                    const p=document.querySelector(
                        `[data-p="${q}"]`
                    );

                    return {
                        question_id:q,
                        answer:a.value,
                        awarded_points:
                            Number(
                                p?.value||0
                            )
                    };
                }
            );

            await api(
                `/api/assessments/${id}/answers`,
                {
                    method:'POST',
                    body:{
                        answers,
                        status:'Completed'
                    }
                }
            );

        }else{

            const score=Number(
                document
                    .getElementById(
                        'r12DirectScore'
                    )
                    .value
                ||0
            );

            await api(
                `/api/assessments/${id}`,
                {
                    method:'PATCH',
                    body:{
                        score:score
                    }
                }
            );
        }

        closeModal();
        toast('Assessment review saved');

        await pageAssessments();

    }catch(e){
        err(e);
    }
}


/* ==============================================================
   WORKFORCE
   ============================================================== */

async function workforcePanel(){

    try{
        const [
            assignments,
            shifts,
            attendance
        ]=await Promise.all([
            api('/api/assignments'),
            api('/api/shifts'),
            api('/api/attendance')
        ]);

        panelBlock(
            'r12-workforce-panel',
            'Assignment / Shift / Attendance',
            `<div class="r12-grid">

             <div>
             <label>Assignment</label>
             <select id="r12Assignment">
             ${opts(
                assignments,
                x=>
                    `${x.first_name||''}
                     ${x.last_name||''}
                     — ${x.job_title||x.job_no||x.id}`
             )}
             </select>
             <button class="btn small"
                onclick="r12EditAssignment()">
                Edit Assignment
             </button>
             <button class="btn small"
                onclick="r12NewShift()">
                + Shift
             </button>
             </div>

             <div>
             <label>Shift</label>
             <select id="r12Shift">
             ${opts(
                shifts,
                x=>
                    `${x.first_name} ${x.last_name}
                     — ${x.shift_date}`
             )}
             </select>
             <button class="btn small"
                onclick="r12EditShift()">
                Edit Shift
             </button>
             <button class="btn small"
                onclick="r12Attendance()">
                Attendance
             </button>
             </div>

             <div>
             <label>Attendance</label>
             <select id="r12Attendance">
             ${opts(
                attendance,
                x=>
                    `${x.first_name} ${x.last_name}
                     — ${x.status}`
             )}
             </select>
             <button class="btn small"
                onclick="r12EditAttendance()">
                Edit Attendance
             </button>
             </div>

             </div>`
        );

    }catch(e){
        err(e);
    }
}

async function editAssignment(){

    try{
        const id=selected(
            'r12Assignment'
        );

        const rows=await api(
            '/api/assignments'
        );

        const a=rows.find(
            x=>x.id===id
        );

        modal(
            'Edit Assignment',
            `<form id="r12AssignmentForm">
             <div class="formgrid">
             ${formFields([
                {
                    name:'worksite',
                    label:'Worksite',
                    value:a?.worksite||''
                },
                {
                    name:'cost_center',
                    label:'Cost Center',
                    value:a?.cost_center||''
                },
                {
                    name:'bill_rate',
                    label:'Bill Rate',
                    type:'number',
                    value:a?.bill_rate||0
                },
                {
                    name:'pay_rate',
                    label:'Pay Rate',
                    type:'number',
                    value:a?.pay_rate||0
                },
                {
                    name:'po_number',
                    label:'PO Number',
                    value:a?.po_number||''
                }
             ])}
             </div></form>`,
            `<button class="btn"
                onclick="closeModal()">
                Cancel
             </button>
             <button class="btn primary"
                onclick="r12SaveAssignment(${id})">
                Save
             </button>`
        );

    }catch(e){
        err(e);
    }
}

async function saveAssignment(id){

    try{
        await api(
            `/api/assignments/${id}`,
            {
                method:'PATCH',
                body:fd(
                    document.getElementById(
                        'r12AssignmentForm'
                    )
                )
            }
        );

        closeModal();
        toast('Assignment updated');

        await pageAssignments();

    }catch(e){
        err(e);
    }
}

function newShift(){

    const assignmentId=
        selected(
            'r12Assignment'
        );

    modal(
        'Create Shift',
        `<form id="r12ShiftForm">
         <input
            type="hidden"
            name="assignment_id"
            value="${assignmentId}"
         >
         <div class="formgrid">
         ${formFields([
            {
                name:'shift_date',
                label:'Date',
                type:'date'
            },
            {
                name:'start_time',
                label:'Start',
                type:'time'
            },
            {
                name:'end_time',
                label:'End',
                type:'time'
            },
            {
                name:'location',
                label:'Location'
            },
            {
                name:'status',
                label:'Status',
                value:'Scheduled'
            }
         ])}
         </div></form>`,
        `<button class="btn"
            onclick="closeModal()">
            Cancel
         </button>
         <button class="btn primary"
            onclick="r12SaveShift()">
            Create
         </button>`
    );
}

async function saveShift(){

    try{
        await api(
            '/api/shifts',
            {
                method:'POST',
                body:fd(
                    document.getElementById(
                        'r12ShiftForm'
                    )
                )
            }
        );

        closeModal();
        toast('Shift created');

        await pageAssignments();

    }catch(e){
        err(e);
    }
}

async function editShift(){

    try{
        const id=selected(
            'r12Shift'
        );

        const rows=await api(
            '/api/shifts'
        );

        const s=rows.find(
            x=>x.id===id
        );

        modal(
            'Edit Shift',
            `<form id="r12ShiftEdit">
             <div class="formgrid">
             ${formFields([
                {
                    name:'shift_date',
                    label:'Date',
                    type:'date',
                    value:s?.shift_date||''
                },
                {
                    name:'start_time',
                    label:'Start',
                    type:'time',
                    value:s?.start_time||''
                },
                {
                    name:'end_time',
                    label:'End',
                    type:'time',
                    value:s?.end_time||''
                },
                {
                    name:'location',
                    label:'Location',
                    value:s?.location||''
                },
                {
                    name:'status',
                    label:'Status',
                    value:s?.status||'Scheduled'
                }
             ])}
             </div></form>`,
            `<button class="btn"
                onclick="closeModal()">
                Cancel
             </button>
             <button class="btn primary"
                onclick="r12SaveShiftEdit(${id})">
                Save
             </button>`
        );

    }catch(e){
        err(e);
    }
}

async function saveShiftEdit(id){

    try{
        await api(
            `/api/shifts/${id}`,
            {
                method:'PATCH',
                body:fd(
                    document.getElementById(
                        'r12ShiftEdit'
                    )
                )
            }
        );

        closeModal();
        toast('Shift updated');

        await pageAssignments();

    }catch(e){
        err(e);
    }
}

function attendance(){

    const shiftId=
        selected(
            'r12Shift'
        );

    modal(
        'Attendance',
        `<form id="r12AttendanceForm">
         <input
            type="hidden"
            name="shift_id"
            value="${shiftId}"
         >
         <div class="formgrid">
         ${formFields([
            {
                name:'check_in',
                label:'Check In'
            },
            {
                name:'check_out',
                label:'Check Out'
            },
            {
                name:'status',
                label:'Status',
                value:'Present'
            },
            {
                name:'note',
                label:'Note',
                type:'textarea',
                span:true
            }
         ])}
         </div></form>`,
        `<button class="btn"
            onclick="closeModal()">
            Cancel
         </button>
         <button class="btn primary"
            onclick="r12SaveAttendance()">
            Save
         </button>`
    );
}

async function saveAttendance(){

    try{
        await api(
            '/api/attendance',
            {
                method:'POST',
                body:fd(
                    document.getElementById(
                        'r12AttendanceForm'
                    )
                )
            }
        );

        closeModal();
        toast('Attendance saved');

        await pageAssignments();

    }catch(e){
        err(e);
    }
}

async function editAttendance(){

    try{
        const id=selected(
            'r12Attendance'
        );

        const rows=await api(
            '/api/attendance'
        );

        const a=rows.find(
            x=>x.id===id
        );

        modal(
            'Edit Attendance',
            `<form id="r12AttendanceEdit">
             <div class="formgrid">
             ${formFields([
                {
                    name:'check_in',
                    label:'Check In',
                    value:a?.check_in||''
                },
                {
                    name:'check_out',
                    label:'Check Out',
                    value:a?.check_out||''
                },
                {
                    name:'status',
                    label:'Status',
                    value:a?.status||''
                },
                {
                    name:'note',
                    label:'Note',
                    type:'textarea',
                    span:true,
                    value:a?.note||''
                }
             ])}
             </div></form>`,
            `<button class="btn"
                onclick="closeModal()">
                Cancel
             </button>
             <button class="btn primary"
                onclick="r12SaveAttendanceEdit(${id})">
                Save
             </button>`
        );

    }catch(e){
        err(e);
    }
}

async function saveAttendanceEdit(id){

    try{
        await api(
            `/api/attendance/${id}`,
            {
                method:'PATCH',
                body:fd(
                    document.getElementById(
                        'r12AttendanceEdit'
                    )
                )
            }
        );

        closeModal();
        toast('Attendance updated');

        await pageAssignments();

    }catch(e){
        err(e);
    }
}


/* ==============================================================
   FINANCE
   ============================================================== */

async function financePanel(){

    try{
        const rows=await api(
            '/api/invoices'
        );

        panelBlock(
            'r12-finance-panel',
            'Invoice Lifecycle',
            `<select id="r12Invoice">
             ${opts(
                rows,
                x=>
                    `${x.invoice_no}
                     — ${x.status}
                     — Balance ${x.balance}`
             )}
             </select>

             <button class="btn small"
                onclick="r12IssueInvoice()">
                Issue
             </button>

             <button class="btn small"
                onclick="r12Payment()">
                Record Payment
             </button>

             <button class="btn small danger"
                onclick="r12VoidInvoice()">
                Void
             </button>

             <button class="btn small"
                onclick="r12InvoiceHistory()">
                History / Payments
             </button>`
        );

    }catch(e){
        err(e);
    }
}

async function issueInvoice(){

    try{
        const id=selected(
            'r12Invoice'
        );

        await api(
            `/api/invoices/${id}`,
            {
                method:'PATCH',
                body:{
                    status:'issued'
                }
            }
        );

        toast('Invoice issued');

        await pageFinance();

    }catch(e){
        err(e);
    }
}

function payment(){

    const id=selected(
        'r12Invoice'
    );

    modal(
        'Record Payment',
        `<form id="r12PaymentForm">
         <div class="formgrid">
         ${formFields([
            {
                name:'amount',
                label:'Amount',
                type:'number'
            },
            {
                name:'reference',
                label:'Reference'
            },
            {
                name:'payment_date',
                label:'Payment Date',
                type:'date'
            }
         ])}
         </div></form>`,
        `<button class="btn"
            onclick="closeModal()">
            Cancel
         </button>
         <button class="btn primary"
            onclick="r12SavePayment(${id})">
            Record
         </button>`
    );
}

async function savePayment(id){

    try{
        await api(
            `/api/invoices/${id}/payments`,
            {
                method:'POST',
                body:fd(
                    document.getElementById(
                        'r12PaymentForm'
                    )
                )
            }
        );

        closeModal();
        toast('Payment recorded');

        await pageFinance();

    }catch(e){
        err(e);
    }
}

async function voidInvoice(){

    try{
        const id=selected(
            'r12Invoice'
        );

        const reason=prompt(
            'Void reason'
        );

        if(!reason)return;

        await api(
            `/api/invoices/${id}`,
            {
                method:'PATCH',
                body:{
                    status:'void',
                    void_reason:reason
                }
            }
        );

        toast('Invoice voided');

        await pageFinance();

    }catch(e){
        err(e);
    }
}

async function invoiceHistory(){

    try{
        const id=selected(
            'r12Invoice'
        );

        const [
            invoice,
            history
        ]=await Promise.all([
            api(
                `/api/invoices/${id}`
            ),
            api(
                `/api/invoices/${id}/history`
            )
        ]);

        modal(
            'Invoice History',
            `<h4>Payments</h4>
             <div class="codeblock">
             ${esc(
                JSON.stringify(
                    invoice.payments||[],
                    null,
                    2
                )
             )}
             </div>
             <h4>Workflow</h4>
             <div class="codeblock">
             ${esc(
                JSON.stringify(
                    history||[],
                    null,
                    2
                )
             )}
             </div>`,
            `<button class="btn"
                onclick="closeModal()">
                Close
             </button>`,
            true
        );

    }catch(e){
        err(e);
    }
}


/* ==============================================================
   VMS
   ============================================================== */

async function vmsPanel(){

    try{
        const d=await api(
            '/api/vms'
        );

        panelBlock(
            'r12-vms-panel',
            'VMS Mapping / Sync',
            `<div class="r12-grid">

             <div>
             <label>Account</label>
             <select id="r12VMSAccount">
             ${opts(
                d.accounts||[],
                x=>`${x.name} — ${x.status}`
             )}
             </select>

             <button class="btn small"
                onclick="r12NewMapping()">
                + Mapping
             </button>

             <button class="btn small"
                onclick="r12VMSSync('sync')">
                Sync
             </button>

             <button class="btn small"
                onclick="r12VMSSync('retry')">
                Retry
             </button>
             </div>

             <div>
             <label>Mapping</label>
             <select id="r12Mapping">
             ${opts(
                d.mappings||[],
                x=>
                    `${x.account_name}
                     — ${x.object_type}
                     — ${x.external_id||''}`
             )}
             </select>

             <button class="btn small"
                onclick="r12EditMapping()">
                Edit Mapping
             </button>
             </div>

             </div>`
        );

    }catch(e){
        err(e);
    }
}

function newMapping(){

    const account=
        selected(
            'r12VMSAccount'
        );

    modal(
        'New VMS Mapping',
        `<form id="r12MapForm">
         <input
            type="hidden"
            name="vms_account_id"
            value="${account}"
         >
         <div class="formgrid">
         ${formFields([
            {
                name:'object_type',
                label:'Object Type',
                value:'job'
            },
            {
                name:'external_id',
                label:'External ID'
            },
            {
                name:'internal_id',
                label:'Internal ID'
            },
            {
                name:'external_status',
                label:'External Status'
            },
            {
                name:'internal_status',
                label:'Internal Status'
            }
         ])}
         </div></form>`,
        `<button class="btn"
            onclick="closeModal()">
            Cancel
         </button>
         <button class="btn primary"
            onclick="r12SaveMapping()">
            Create
         </button>`
    );
}

async function saveMapping(){

    try{
        await api(
            '/api/vms/mappings',
            {
                method:'POST',
                body:fd(
                    document.getElementById(
                        'r12MapForm'
                    )
                )
            }
        );

        closeModal();
        toast('VMS mapping created');

        await pageVMS();

    }catch(e){
        err(e);
    }
}

async function editMapping(){

    try{
        const id=selected(
            'r12Mapping'
        );

        const d=await api(
            '/api/vms'
        );

        const m=(d.mappings||[])
            .find(
                x=>x.id===id
            );

        if(!m)return;

        modal(
            'Edit VMS Mapping',
            `<form id="r12MapEdit">
             <div class="formgrid">
             ${formFields([
                {
                    name:'object_type',
                    label:'Object Type',
                    value:m.object_type||''
                },
                {
                    name:'external_id',
                    label:'External ID',
                    value:m.external_id||''
                },
                {
                    name:'internal_id',
                    label:'Internal ID',
                    value:m.internal_id||''
                },
                {
                    name:'external_status',
                    label:'External Status',
                    value:m.external_status||''
                },
                {
                    name:'internal_status',
                    label:'Internal Status',
                    value:m.internal_status||''
                }
             ])}
             </div></form>`,
            `<button class="btn"
                onclick="closeModal()">
                Cancel
             </button>
             <button class="btn primary"
                onclick="r12SaveMappingEdit(${id})">
                Save
             </button>`
        );

    }catch(e){
        err(e);
    }
}

async function saveMappingEdit(id){

    try{
        await api(
            `/api/vms-mappings/${id}`,
            {
                method:'PATCH',
                body:fd(
                    document.getElementById(
                        'r12MapEdit'
                    )
                )
            }
        );

        closeModal();
        toast('VMS mapping updated');

        await pageVMS();

    }catch(e){
        err(e);
    }
}

async function vmsSync(action){

    try{
        const id=selected(
            'r12VMSAccount'
        );

        const d=await api(
            '/api/vms'
        );

        const prior=(d.history||[])
            .find(
                x=>
                    Number(x.vms_account_id)
                    ===id
            );

        const result=await api(
            `/api/vms/accounts/${id}/${action}`,
            {
                method:'POST',
                body:{
                    retry_of:
                        action==='retry'
                            ?prior?.id||null
                            :null
                }
            }
        );

        toast(
            `VMS ${action}: ${result.status}`
        );

        await pageVMS();

    }catch(e){
        err(e);
    }
}


/* ==============================================================
   SUPPLIER
   ============================================================== */

async function supplierPanel(){

    try{
        const [
            suppliers,
            jobs
        ]=await Promise.all([
            api('/api/suppliers'),
            api('/api/jobs')
        ]);

        panelBlock(
            'r12-supplier-panel',
            'Supplier Release Administration',
            `<label>Supplier</label>
             <select id="r12Supplier">
             ${opts(
                suppliers,
                x=>x.name
             )}
             </select>

             <label>Job</label>
             <select id="r12SupplierJob">
             ${opts(
                jobs,
                x=>`${x.job_no} — ${x.title}`
             )}
             </select>

             <label>Max Submissions</label>
             <input
                id="r12SupplierLimit"
                type="number"
                value="3"
             >

             <button class="btn small"
                onclick="r12ReleaseSupplier('Open')">
                Release Job
             </button>

             <button class="btn small danger"
                onclick="r12ReleaseSupplier('Closed')">
                Close Release
             </button>`
        );

    }catch(e){
        err(e);
    }
}

async function releaseSupplier(statusValue){

    try{
        const sid=selected(
            'r12Supplier'
        );

        const jid=selected(
            'r12SupplierJob'
        );

        const limit=Number(
            document
                .getElementById(
                    'r12SupplierLimit'
                )
                .value
            ||3
        );

        await api(
            `/api/suppliers/${sid}/releases`,
            {
                method:'POST',
                body:{
                    job_id:jid,
                    status:statusValue,
                    max_submissions:limit
                }
            }
        );

        toast(
            statusValue==='Open'
                ?'Job released'
                :'Release closed'
        );

        await pageSuppliers();

    }catch(e){
        err(e);
    }
}


/* ==============================================================
   ADMIN
   ============================================================== */

async function adminPanel(){

    try{
        const [
            users,
            fields,
            automations,
            connectors
        ]=await Promise.all([
            api('/api/users'),
            api('/api/custom-fields'),
            api('/api/automations'),
            api('/api/integrations')
        ]);

        panelBlock(
            'r12-admin-panel',
            'Advanced Administration',
            `<div class="r12-grid">

             <div>
             <label>User</label>
             <select id="r12User">
             ${opts(
                users,
                x=>
                    `${x.name} — ${x.role}
                     — ${x.active?'Active':'Disabled'}`
             )}
             </select>
             <button class="btn small"
                onclick="r12EditUser()">
                Edit / Role / Reset
             </button>
             </div>

             <div>
             <label>UDF</label>
             <select id="r12UDF">
             ${opts(
                fields,
                x=>
                    `${x.entity_type}.${x.field_name}`
             )}
             </select>
             <button class="btn small"
                onclick="r12EditUDF()">
                Edit UDF
             </button>
             <button class="btn small"
                onclick="r12UDFValue()">
                Set Value
             </button>
             </div>

             <div>
             <label>Automation</label>
             <select id="r12Automation">
             ${opts(
                automations,
                x=>
                    `${x.name}
                     — ${x.active?'Active':'Off'}`
             )}
             </select>
             <button class="btn small"
                onclick="r12EditAutomation()">
                Edit
             </button>
             <button class="btn small"
                onclick="r12RunAutomation(true)">
                Dry Run
             </button>
             <button class="btn small"
                onclick="r12RunAutomation(false)">
                Run
             </button>
             <button class="btn small"
                onclick="r12AutomationHistory()">
                History
             </button>
             </div>

             <div>
             <label>Connector</label>
             <select id="r12Connector">
             ${opts(
                connectors,
                x=>
                    `${x.name}
                     — ${x.mode}
                     — ${x.status}`
             )}
             </select>
             <button class="btn small"
                onclick="r12EditConnector()">
                Edit
             </button>
             <button class="btn small"
                onclick="r12ConnectorAction('test')">
                Test
             </button>
             <button class="btn small"
                onclick="r12ConnectorAction('sync')">
                Sync
             </button>
             <button class="btn small"
                onclick="r12ConnectorLogs()">
                Logs
             </button>
             </div>

             </div>`
        );

    }catch(e){
        err(e);
    }
}

async function editUser(){

    try{
        const id=selected(
            'r12User'
        );

        const users=await api(
            '/api/users'
        );

        const u=users.find(
            x=>x.id===id
        );

        if(!u)return;

        modal(
            'Edit User',
            `<form id="r12UserForm">
             <div class="formgrid">
             ${formFields([
                {
                    name:'name',
                    label:'Name',
                    value:u.name||''
                },
                {
                    name:'email',
                    label:'Email',
                    value:u.email||''
                },
                {
                    name:'role',
                    label:'Role',
                    type:'select',
                    options:[
                        'admin',
                        'teamlead',
                        'recruiter',
                        'sales',
                        'hr',
                        'finance',
                        'client',
                        'candidate',
                        'worker',
                        'supplier',
                        'approver'
                    ],
                    value:u.role
                },
                {
                    name:'active',
                    label:'Active 1 / 0',
                    value:u.active?1:0
                },
                {
                    name:'password',
                    label:'New Password (optional)'
                }
             ])}
             </div></form>`,
            `<button class="btn"
                onclick="closeModal()">
                Cancel
             </button>
             <button class="btn primary"
                onclick="r12SaveUser(${id})">
                Save
             </button>`
        );

    }catch(e){
        err(e);
    }
}

async function saveUser(id){

    try{
        const body=fd(
            document.getElementById(
                'r12UserForm'
            )
        );

        body.active=
            String(body.active)==='1';

        if(!body.password){
            delete body.password;
        }

        await api(
            `/api/users/${id}`,
            {
                method:'PATCH',
                body
            }
        );

        closeModal();
        toast('User updated');

        await pageAdmin();

    }catch(e){
        err(e);
    }
}

async function editUDF(){

    try{
        const id=selected(
            'r12UDF'
        );

        const fields=await api(
            '/api/custom-fields'
        );

        const f=fields.find(
            x=>x.id===id
        );

        if(!f)return;

        modal(
            'Edit UDF',
            `<form id="r12UDFForm">
             <div class="formgrid">
             ${formFields([
                {
                    name:'entity_type',
                    label:'Entity',
                    value:f.entity_type
                },
                {
                    name:'field_name',
                    label:'Field',
                    value:f.field_name
                },
                {
                    name:'field_type',
                    label:'Type',
                    type:'select',
                    options:[
                        'text',
                        'number',
                        'date',
                        'boolean',
                        'select'
                    ],
                    value:f.field_type
                },
                {
                    name:'required',
                    label:'Required 1 / 0',
                    value:f.required?1:0
                },
                {
                    name:'active',
                    label:'Active 1 / 0',
                    value:f.active?1:0
                }
             ])}
             </div></form>`,
            `<button class="btn"
                onclick="closeModal()">
                Cancel
             </button>
             <button class="btn primary"
                onclick="r12SaveUDF(${id})">
                Save
             </button>`
        );

    }catch(e){
        err(e);
    }
}

async function saveUDF(id){

    try{
        const body=fd(
            document.getElementById(
                'r12UDFForm'
            )
        );

        body.required=
            String(body.required)==='1';

        body.active=
            String(body.active)==='1';

        await api(
            `/api/custom-fields/${id}`,
            {
                method:'PATCH',
                body
            }
        );

        closeModal();
        toast('UDF updated');

        await pageAdmin();

    }catch(e){
        err(e);
    }
}

function udfValue(){

    const fieldId=
        selected(
            'r12UDF'
        );

    modal(
        'Set UDF Value',
        `<form id="r12UDFValueForm">

         <input
            type="hidden"
            name="field_id"
            value="${fieldId}"
         >

         <div class="formgrid">
         ${formFields([
            {
                name:'entity_type',
                label:'Entity Type',
                type:'select',
                options:[
                    'candidate',
                    'job',
                    'company',
                    'contact',
                    'assignment'
                ]
            },
            {
                name:'entity_id',
                label:'Entity ID',
                type:'number'
            },
            {
                name:'value',
                label:'Value'
            }
         ])}
         </div></form>`,
        `<button class="btn"
            onclick="closeModal()">
            Cancel
         </button>
         <button class="btn primary"
            onclick="r12SaveUDFValue()">
            Save
         </button>`
    );
}

async function saveUDFValue(){

    try{
        await api(
            '/api/custom-values',
            {
                method:'POST',
                body:fd(
                    document.getElementById(
                        'r12UDFValueForm'
                    )
                )
            }
        );

        closeModal();
        toast('UDF value saved');

    }catch(e){
        err(e);
    }
}

async function editAutomation(){

    try{
        const id=selected(
            'r12Automation'
        );

        const rows=await api(
            '/api/automations'
        );

        const a=rows.find(
            x=>x.id===id
        );

        if(!a)return;

        modal(
            'Edit Automation',
            `<form id="r12AutomationForm">
             <div class="formgrid">
             ${formFields([
                {
                    name:'name',
                    label:'Name',
                    value:a.name||''
                },
                {
                    name:'trigger_name',
                    label:'Trigger',
                    value:a.trigger_name||''
                },
                {
                    name:'active',
                    label:'Active 1 / 0',
                    value:a.active?1:0
                }
             ])}
             </div></form>`,
            `<button class="btn"
                onclick="closeModal()">
                Cancel
             </button>
             <button class="btn primary"
                onclick="r12SaveAutomation(${id})">
                Save
             </button>`
        );

    }catch(e){
        err(e);
    }
}

async function saveAutomation(id){

    try{
        const body=fd(
            document.getElementById(
                'r12AutomationForm'
            )
        );

        body.active=
            String(body.active)==='1';

        await api(
            `/api/automations/${id}`,
            {
                method:'PATCH',
                body
            }
        );

        closeModal();
        toast('Automation updated');

        await pageAdmin();

    }catch(e){
        err(e);
    }
}

async function runAutomation(dryRun){

    try{
        const id=selected(
            'r12Automation'
        );

        const result=await api(
            `/api/automations/${id}/run`,
            {
                method:'POST',
                body:{
                    dry_run:dryRun,
                    entity_type:'candidate',
                    entity_id:1
                }
            }
        );

        toast(
            `Automation: ${result.status}`
        );

    }catch(e){
        err(e);
    }
}

async function automationHistory(){

    try{
        const id=selected(
            'r12Automation'
        );

        const rows=await api(
            '/api/automation-runs?automation_id='
            +encodeURIComponent(id)
        );

        modal(
            'Automation History',
            `<div class="codeblock">
             ${esc(
                JSON.stringify(
                    rows,
                    null,
                    2
                )
             )}
             </div>`,
            `<button class="btn"
                onclick="closeModal()">
                Close
             </button>`,
            true
        );

    }catch(e){
        err(e);
    }
}

async function editConnector(){

    try{
        const id=selected(
            'r12Connector'
        );

        const rows=await api(
            '/api/integrations'
        );

        const c=rows.find(
            x=>x.id===id
        );

        if(!c)return;

        modal(
            'Edit Connector',
            `<form id="r12ConnectorForm">
             <div class="formgrid">
             ${formFields([
                {
                    name:'category',
                    label:'Category',
                    value:c.category||''
                },
                {
                    name:'name',
                    label:'Name',
                    value:c.name||''
                },
                {
                    name:'mode',
                    label:'Mode',
                    type:'select',
                    options:[
                        'Internal',
                        'Demo',
                        'External'
                    ],
                    value:c.mode||'Internal'
                },
                {
                    name:'status',
                    label:'Status',
                    value:c.status||''
                },
                {
                    name:'credential_ref',
                    label:'Credential Reference',
                    value:c.credential_ref||''
                },
                {
                    name:'notes',
                    label:'Notes',
                    type:'textarea',
                    span:true,
                    value:c.notes||''
                }
             ])}
             </div></form>`,
            `<button class="btn"
                onclick="closeModal()">
                Cancel
             </button>
             <button class="btn primary"
                onclick="r12SaveConnector(${id})">
                Save
             </button>`
        );

    }catch(e){
        err(e);
    }
}

async function saveConnector(id){

    try{
        await api(
            `/api/integrations/${id}`,
            {
                method:'PATCH',
                body:fd(
                    document.getElementById(
                        'r12ConnectorForm'
                    )
                )
            }
        );

        closeModal();
        toast('Connector updated');

        await pageAdmin();

    }catch(e){
        err(e);
    }
}

async function connectorAction(action){

    try{
        const id=selected(
            'r12Connector'
        );

        const result=await api(
            `/api/integrations/${id}/${action}`,
            {
                method:'POST',
                body:{}
            }
        );

        toast(
            `${action}: ${result.status}`
        );

    }catch(e){
        err(e);
    }
}

async function connectorLogs(){

    try{
        const id=selected(
            'r12Connector'
        );

        const rows=await api(
            `/api/integrations/${id}/logs`
        );

        modal(
            'Connector Logs',
            `<div class="codeblock">
             ${esc(
                JSON.stringify(
                    rows,
                    null,
                    2
                )
             )}
             </div>`,
            `<button class="btn"
                onclick="closeModal()">
                Close
             </button>`,
            true
        );

    }catch(e){
        err(e);
    }
}


/* ==============================================================
   PAGE WRAPPERS
   ============================================================== */

const original={
    candidates:pageCandidates,
    candidate:pageCandidate,
    hotlists:pageHotlists,
    jobs:pageJobs,
    job:pageJob,
    companies:pageCompanies,
    contacts:pageContacts,
    interviews:pageInterviews,
    assessments:pageAssessments,
    assignments:pageAssignments,
    finance:pageFinance,
    vms:pageVMS,
    suppliers:pageSuppliers,
    admin:pageAdmin
};


pageCandidates=async function(){

    await original.candidates();

    addAction(
        'r12-restore-candidate',
        'Restore Archived',
        restoreCandidates
    );
};


pageCandidate=async function(id){

    await original.candidate(id);

    addAction(
        'r12-edit-candidate',
        'Edit Candidate',
        ()=>editCandidate(id)
    );
};


pageHotlists=async function(){

    await original.hotlists();

    addAction(
        'r12-restore-hotlist',
        'Restore Archived',
        restoreHotlists
    );
};


pageJobs=async function(){

    await original.jobs();

    addAction(
        'r12-restore-job',
        'Restore Archived',
        restoreJobs
    );
};


pageJob=async function(id){

    await original.job(id);

    addAction(
        'r12-edit-job',
        'Edit Job',
        ()=>editJob(id)
    );

    addAction(
        'r12-job-team',
        'Job Team',
        ()=>jobTeam(id)
    );
};


pageCompanies=async function(){

    await original.companies();
    await crmPanel();
};


pageContacts=async function(){

    await original.contacts();
    await crmPanel();
};


pageInterviews=async function(){

    await original.interviews();
    await interviewPanel();
};


pageAssessments=async function(){

    await original.assessments();
    await assessmentPanel();
};


pageAssignments=async function(){

    await original.assignments();
    await workforcePanel();
};


pageFinance=async function(){

    await original.finance();
    await financePanel();
};


pageVMS=async function(){

    await original.vms();
    await vmsPanel();
};


pageSuppliers=async function(){

    await original.suppliers();
    await supplierPanel();
};


pageAdmin=async function(){

    await original.admin();
    await adminPanel();
};


/* ==============================================================
   EXPORT ACTIONS FOR INLINE ONCLICK
   ============================================================== */

Object.assign(
    window,
    {
        r12SaveCandidate:
            saveCandidate,

        r12RestoreCandidateNow:
            restoreCandidateNow,

        r12RestoreHotlistNow:
            restoreHotlistNow,

        r12SaveJob:
            saveJob,

        r12RestoreJobNow:
            restoreJobNow,

        r12AssignJobUser:
            assignJobUser,

        r12EditCompany:
            editCompany,

        r12SaveCompany:
            saveCompany,

        r12EditContact:
            editContact,

        r12SaveContact:
            saveContact,

        r12ConvertLead:
            convertLead,

        r12OpportunityStage:
            opportunityStage,

        r12InterviewFeedback:
            interviewFeedback,

        r12SaveInterview:
            saveInterview,

        r12AssessmentReview:
            assessmentReview,

        r12SaveAssessment:
            saveAssessment,

        r12EditAssignment:
            editAssignment,

        r12SaveAssignment:
            saveAssignment,

        r12NewShift:
            newShift,

        r12SaveShift:
            saveShift,

        r12EditShift:
            editShift,

        r12SaveShiftEdit:
            saveShiftEdit,

        r12Attendance:
            attendance,

        r12SaveAttendance:
            saveAttendance,

        r12EditAttendance:
            editAttendance,

        r12SaveAttendanceEdit:
            saveAttendanceEdit,

        r12IssueInvoice:
            issueInvoice,

        r12Payment:
            payment,

        r12SavePayment:
            savePayment,

        r12VoidInvoice:
            voidInvoice,

        r12InvoiceHistory:
            invoiceHistory,

        r12NewMapping:
            newMapping,

        r12SaveMapping:
            saveMapping,

        r12EditMapping:
            editMapping,

        r12SaveMappingEdit:
            saveMappingEdit,

        r12VMSSync:
            vmsSync,

        r12ReleaseSupplier:
            releaseSupplier,

        r12EditUser:
            editUser,

        r12SaveUser:
            saveUser,

        r12EditUDF:
            editUDF,

        r12SaveUDF:
            saveUDF,

        r12UDFValue:
            udfValue,

        r12SaveUDFValue:
            saveUDFValue,

        r12EditAutomation:
            editAutomation,

        r12SaveAutomation:
            saveAutomation,

        r12RunAutomation:
            runAutomation,

        r12AutomationHistory:
            automationHistory,

        r12EditConnector:
            editConnector,

        r12SaveConnector:
            saveConnector,

        r12ConnectorAction:
            connectorAction,

        r12ConnectorLogs:
            connectorLogs
    }
);


/* ==============================================================
   STYLE
   ============================================================== */

const style=document.createElement(
    'style'
);

style.textContent=`
.r12b-panel{
    margin-top:16px;
}

.r12-grid{
    display:grid;
    grid-template-columns:
        repeat(
            auto-fit,
            minmax(250px,1fr)
        );
    gap:14px;
}

.r12-grid > div{
    padding:12px;
    border:1px solid #e2e8f0;
    border-radius:10px;
    background:#fbfcff;
}

.r12-grid select,
.r12-grid input{
    width:100%;
    margin:6px 0 9px;
}

.r12-grid .btn{
    margin:
        3px
        4px
        3px
        0;
}

.r12-question{
    border-bottom:
        1px solid #e5e7eb;
    padding:12px 0;
}

.r12-question input{
    width:100%;
    display:block;
    margin-top:7px;
}
`;

document.head.appendChild(
    style
);

window.R12B_VERSION =
    R12B_VERSION;

})();
