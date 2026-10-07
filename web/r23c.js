/*
 ATS-One R23C
 Candidate Portal:
 - Public Registration
 - Resume Maker / Resume Builder
 - Saved Jobs
 - Ideal Jobs
 - English / Español / Français / 中文
*/


const R23C_LABELS={
  en:{
    resume:'Resume Maker / Resume Builder',
    saved:'Saved Jobs',
    ideal:'Ideal Jobs',
    edit:'Edit Resume',
    saveJob:'Save Job',
    remove:'Remove',
    noSaved:'No saved jobs yet.',
    noIdeal:'No ideal jobs available.'
  },

  es:{
    resume:'Creador / Editor de Currículum',
    saved:'Empleos guardados',
    ideal:'Empleos ideales',
    edit:'Editar currículum',
    saveJob:'Guardar empleo',
    remove:'Eliminar',
    noSaved:'Aún no hay empleos guardados.',
    noIdeal:'No hay empleos ideales disponibles.'
  },

  fr:{
    resume:'Créateur / Éditeur de CV',
    saved:'Emplois enregistrés',
    ideal:'Emplois idéaux',
    edit:'Modifier le CV',
    saveJob:'Enregistrer',
    remove:'Retirer',
    noSaved:'Aucun emploi enregistré.',
    noIdeal:'Aucun emploi idéal disponible.'
  },

  zh:{
    resume:'简历制作 / 简历编辑器',
    saved:'已保存职位',
    ideal:'理想职位',
    edit:'编辑简历',
    saveJob:'保存职位',
    remove:'移除',
    noSaved:'尚未保存职位。',
    noIdeal:'暂无理想职位。'
  },

  hi:{
    resume:'रिज़्यूमे मेकर / रिज़्यूमे बिल्डर',
    saved:'सेव की गई नौकरियाँ',
    ideal:'उपयुक्त नौकरियाँ',
    edit:'रिज़्यूमे संपादित करें',
    saveJob:'जॉब सेव करें',
    remove:'हटाएँ',
    noSaved:'अभी कोई सेव की गई नौकरी नहीं है।',
    noIdeal:'अभी कोई उपयुक्त नौकरी उपलब्ध नहीं है।'
  }
};


function r23cLocale(){

  return (
    R22_CANDIDATE_EXPERIENCE
    ?.locale
    ||'en'
  );
}


function r23cLabels(){

  return (
    R23C_LABELS[
      r23cLocale()
    ]
    ||R23C_LABELS.en
  );
}


const R23C_PREV_RENDER_LOGIN=
  renderLogin;


renderLogin=function(){

  R23C_PREV_RENDER_LOGIN();

  const form=
    document.querySelector(
      '.login-form'
    );

  if(
    !form
    ||
    document.getElementById(
      'r23c-register-button'
    )
  ){
    return;
  }

  const button=
    document.createElement(
      'button'
    );

  button.id=
    'r23c-register-button';

  button.className=
    'btn wide';

  button.type=
    'button';

  button.style.marginTop=
    '10px';

  button.textContent=
    'CREATE CANDIDATE ACCOUNT';

  button.onclick=
    r23cOpenRegistration;

  form.appendChild(
    button
  );
};


async function r23cOpenRegistration(){

  const config=
    await api(
      '/api/r23c/public-registration'
    );

  const modeOptions=
    config.resume_modes
    .map(
      x=>`
        <option value="${esc(x.code)}">
          ${esc(x.label)}
        </option>
      `
    )
    .join('');

  const localeOptions=
    config.supported_locales
    .map(
      x=>`
        <option value="${esc(x.code)}">
          ${esc(x.label)}
        </option>
      `
    )
    .join('');


  modal(
    'Candidate Registration + Resume Maker',
    `
    <form id="r23c-register-form">

      <div class="formgrid">

        <div class="field">
          <label>First Name</label>
          <input
            name="first_name"
            required>
        </div>

        <div class="field">
          <label>Last Name</label>
          <input
            name="last_name"
            required>
        </div>

        <div class="field">
          <label>Email</label>
          <input
            name="email"
            type="email"
            required>
        </div>

        <div class="field">
          <label>Password</label>
          <input
            name="password"
            type="password"
            minlength="10"
            required>
        </div>

        <div class="field">
          <label>Language</label>
          <select name="locale">
            ${localeOptions}
          </select>
        </div>

        <div class="field">
          <label>Registration Mode</label>
          <select
            name="resume_mode"
            onchange="
              r23cRegistrationModeChanged(
                this.value
              )
            ">
            ${modeOptions}
          </select>
        </div>

        <div class="field">
          <label>Current / Target Title</label>
          <input
            name="headline"
            placeholder="Java Developer">
        </div>

        <div class="field">
          <label>Profession</label>
          <input
            name="profession">
        </div>

        <div
          class="field"
          style="grid-column:1/-1">

          <label>
            Professional Summary
          </label>

          <textarea
            name="summary"
            rows="4"></textarea>
        </div>

        <div
          class="field r23c-maker-field"
          style="grid-column:1/-1">

          <label>Skills</label>

          <textarea
            name="skills_text"
            rows="4"
            placeholder="Java, Spring Boot, Kafka, AWS"></textarea>
        </div>

        <div
          class="field r23c-maker-field"
          style="grid-column:1/-1">

          <label>Experience</label>

          <textarea
            name="experience_text"
            rows="7"
            placeholder="Company | Role | Dates | Achievements"></textarea>
        </div>

        <div
          class="field r23c-maker-field"
          style="grid-column:1/-1">

          <label>Education</label>

          <textarea
            name="education_text"
            rows="4"></textarea>
        </div>

        <div
          class="field r23c-paste-field"
          style="
            grid-column:1/-1;
            display:none
          ">

          <label>
            Paste Existing Resume
          </label>

          <textarea
            name="resume_text"
            rows="10"></textarea>
        </div>

      </div>

    </form>
    `,
    `
    <button
      class="btn"
      onclick="closeModal()">
      Cancel
    </button>

    <button
      class="btn primary"
      onclick="r23cSubmitRegistration()">
      Create Candidate Account
    </button>
    `,
    true
  );
}


function r23cRegistrationModeChanged(
  mode
){

  const maker=
    mode
    ==='resume_maker';

  const paste=
    mode
    ==='paste_resume';

  document
    .querySelectorAll(
      '.r23c-maker-field'
    )
    .forEach(
      x=>{
        x.style.display=
          maker
          ?''
          :'none';
      }
    );

  document
    .querySelectorAll(
      '.r23c-paste-field'
    )
    .forEach(
      x=>{
        x.style.display=
          paste
          ?''
          :'none';
      }
    );
}


async function r23cSubmitRegistration(){

  const form=
    document.getElementById(
      'r23c-register-form'
    );

  const body=
    fd(
      form
    );

  await api(
    '/api/r23c/register-candidate',
    {
      method:'POST',
      body
    }
  );

  closeModal();

  toast(
    'Candidate account created'
  );

  await api(
    '/api/login',
    {
      method:'POST',
      body:{
        email:
          body.email,

        password:
          body.password
      }
    }
  );

  await boot();
}


async function r23cOpenResumeMaker(){

  const d=
    await api(
      '/api/r23c/resume-builder'
    );

  const c=
    d.candidate
    ||{};

  const r=
    d.latest
    ||{};


  modal(
    'Resume Maker / Resume Builder',
    `
    <form id="r23c-resume-form">

      <div class="formgrid">

        <div
          class="field"
          style="grid-column:1/-1">

          <label>
            Headline / Current Title
          </label>

          <input
            name="headline"
            value="${esc(
              r.headline
              ||c.current_title
              ||''
            )}">
        </div>

        <div
          class="field"
          style="grid-column:1/-1">

          <label>
            Professional Summary
          </label>

          <textarea
            name="summary"
            rows="5">${esc(
              r.summary
              ||c.summary
              ||''
            )}</textarea>
        </div>

        <div
          class="field"
          style="grid-column:1/-1">

          <label>
            Skills
          </label>

          <textarea
            name="skills_text"
            rows="5">${esc(
              r.skills_text
              ||''
            )}</textarea>
        </div>

        <div
          class="field"
          style="grid-column:1/-1">

          <label>
            Experience
          </label>

          <textarea
            name="experience_text"
            rows="9">${esc(
              r.experience_text
              ||''
            )}</textarea>
        </div>

        <div
          class="field"
          style="grid-column:1/-1">

          <label>
            Education
          </label>

          <textarea
            name="education_text"
            rows="5">${esc(
              r.education_text
              ||''
            )}</textarea>
        </div>

      </div>

      ${
        r.resume_text
        ?`
          <div style="margin-top:14px">
            <label>
              Current Generated Resume
            </label>

            <pre
              style="
                white-space:pre-wrap;
                max-height:260px;
                overflow:auto
              ">${esc(
                r.resume_text
              )}</pre>
          </div>
        `
        :''
      }

    </form>
    `,
    `
    <button
      class="btn"
      onclick="closeModal()">
      Cancel
    </button>

    <button
      class="btn primary"
      onclick="r23cSaveResume()">
      Save Resume Version
    </button>
    `,
    true
  );
}


async function r23cSaveResume(){

  const body=
    fd(
      document.getElementById(
        'r23c-resume-form'
      )
    );

  const result=
    await api(
      '/api/r23c/resume-builder',
      {
        method:'POST',
        body
      }
    );

  closeModal();

  toast(
    `Resume version ${result.version} saved`
  );

  await pageCandidatePortal();
}


async function r23cSaveJob(
  jobId
){

  await api(
    '/api/r23c/saved-jobs',
    {
      method:'POST',
      body:{
        job_id:
          Number(
            jobId
          )
      }
    }
  );

  toast(
    'Job saved'
  );

  await pageCandidatePortal();
}


async function r23cRemoveSavedJob(
  jobId
){

  await api(
    `/api/r23c/saved-jobs/${Number(jobId)}/remove`,
    {
      method:'POST',
      body:{}
    }
  );

  toast(
    'Saved job removed'
  );

  await pageCandidatePortal();
}


function r23cJobCard(
  job,
  action,
){

  return `
    <div
      class="jobcard"
      style="margin-bottom:10px">

      <div>
        <b>
          ${esc(
            job.title
            ||''
          )}
        </b>

        <div class="subtle">
          ${esc(
            job.job_no
            ||''
          )}

          ·

          ${esc(
            [
              job.city,
              job.state,
              job.work_mode
            ]
            .filter(Boolean)
            .join(' · ')
          )}
        </div>

        ${
          job.ideal_job_score
          !==undefined
          ?`
            <div class="subtle">
              Match score:
              ${Number(
                job.ideal_job_score
              )}

              ${
                (
                  job.match_terms
                  ||[]
                ).length
                ?' · '
                 +esc(
                   job.match_terms
                   .join(', ')
                 )
                :''
              }
            </div>
          `
          :''
        }

      </div>

      <div>
        ${action}
      </div>

    </div>
  `;
}


async function r23cEnhanceCandidatePortal(){

  if(
    ME?.role
    !=='candidate'
  ){
    return;
  }

  const d=
    await api(
      '/api/r23c/candidate-portal'
    );

  const page=
    document.querySelector(
      '#content .page'
    );

  if(!page){
    return;
  }

  const t=
    r23cLabels();

  const resume=
    d.latest_resume
    ||{};


  page.insertAdjacentHTML(
    'beforeend',
    panel(
      t.resume,
      `
      <div class="kv">
        <b>Current Version</b>

        <span>
          ${
            resume.version
            ?`Version ${resume.version}`
            :'No generated resume yet'
          }
        </span>
      </div>

      <div class="kv">
        <b>Headline</b>

        <span>
          ${esc(
            resume.headline
            ||d.candidate.current_title
            ||''
          )}
        </span>
      </div>

      <div style="margin-top:12px">
        <button
          class="btn primary"
          onclick="r23cOpenResumeMaker()">

          ${esc(
            t.edit
          )}

        </button>
      </div>
      `
    )
  );


  const savedBody=
    (
      d.saved_jobs
      ||[]
    ).length
    ?d.saved_jobs
      .map(
        j=>
          r23cJobCard(
            j,
            `
            <button
              class="btn small"
              onclick="
                r23cRemoveSavedJob(
                  ${j.id}
                )
              ">
              ${esc(t.remove)}
            </button>
            `
          )
      )
      .join('')
    :`<div class="empty">${esc(t.noSaved)}</div>`;


  page.insertAdjacentHTML(
    'beforeend',
    panel(
      t.saved,
      savedBody
    )
  );


  const savedIds=
    new Set(
      (
        d.saved_jobs
        ||[]
      ).map(
        x=>
          Number(
            x.id
          )
      )
    );


  const idealBody=
    (
      d.ideal_jobs
      ||[]
    ).length
    ?d.ideal_jobs
      .slice(
        0,
        12
      )
      .map(
        j=>{

          const save=
            savedIds.has(
              Number(
                j.id
              )
            )
            ?`<span class="subtle">Saved</span>`
            :`
              <button
                class="btn small"
                onclick="
                  r23cSaveJob(
                    ${j.id}
                  )
                ">
                ${esc(t.saveJob)}
              </button>
            `;

          return r23cJobCard(
            j,
            `
              ${save}

              <button
                class="btn small primary"
                onclick="
                  candidateApply(
                    ${j.id},
                    ${d.candidate.id}
                  )
                ">
                Apply
              </button>
            `
          );
        }
      )
      .join('')
    :`<div class="empty">${esc(t.noIdeal)}</div>`;


  page.insertAdjacentHTML(
    'beforeend',
    panel(
      t.ideal,
      idealBody
    )
  );
}


const R23C_PREV_CANDIDATE_PORTAL=
  pageCandidatePortal;


pageCandidatePortal=
async function(){

  await R23C_PREV_CANDIDATE_PORTAL();

  await r23cEnhanceCandidatePortal();
};
