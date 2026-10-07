/*
 ATS-ONE R22
 - multilingual candidate experience / i18n language selector
 - white-label tenant branding
 - Reference Check provider adapter
 - WOTC provider adapter
 - Outlook / Microsoft Graph calendar synchronization
 - Candidate Enrichment provider adapter
*/

let R22_BRANDING=null;
let R22_CANDIDATE_EXPERIENCE=null;


async function r22PublicBranding(){

    try{
        return await api(
            '/api/r22/public-branding'
        );
    }
    catch(_){
        return null;
    }
}


function r22ApplyBrandingObject(b){

    if(!b){
        return;
    }

    R22_BRANDING=b;

    if(b.portal_title){
        document.title=b.portal_title;
    }

    document
        .querySelectorAll(
            '.logo,.brandmark'
        )
        .forEach(el=>{

            el.replaceChildren();

            if(b.logo_url){

                const img=
                    document.createElement(
                        'img'
                    );

                img.src=b.logo_url;
                img.alt=b.product_name||'Brand';
                img.style.height='25px';
                img.style.maxWidth='150px';
                img.style.objectFit='contain';

                el.appendChild(img);

                const space=
                    document.createTextNode(' ');

                el.appendChild(space);
            }

            el.appendChild(
                document.createTextNode(
                    b.product_name
                    ||'ATS One'
                )
            );
        });


    const primary=
        /^#[0-9a-f]{6}$/i.test(
            b.primary_color||''
        )
        ?b.primary_color
        :'#164e63';

    const secondary=
        /^#[0-9a-f]{6}$/i.test(
            b.secondary_color||''
        )
        ?b.secondary_color
        :'#0f172a';

    let style=
        document.getElementById(
            'r22-branding-style'
        );

    if(!style){

        style=document.createElement(
            'style'
        );

        style.id='r22-branding-style';

        document.head.appendChild(
            style
        );
    }

    style.textContent=`
        .topbar{
            box-shadow:
                inset 0 3px 0 ${primary};
        }

        .btn.primary{
            background:${primary}!important;
            border-color:${primary}!important;
        }

        .portal-hero{
            border-top:
                4px solid ${primary};
        }

        .r22-brand-card{
            border-left:
                4px solid ${secondary};
        }
    `;
}


async function r22ApplyPublicBranding(){

    const b=await r22PublicBranding();

    if(b){
        r22ApplyBrandingObject(b);
    }
}


const R22_ORIGINAL_RENDER_LOGIN=
    renderLogin;

renderLogin=function(){

    R22_ORIGINAL_RENDER_LOGIN();

    r22ApplyPublicBranding()
        .catch(()=>{});
};


const R22_ORIGINAL_RENDER_SHELL=
    renderShell;

renderShell=function(){

    R22_ORIGINAL_RENDER_SHELL();

    api('/api/r22/branding')
        .then(r22ApplyBrandingObject)
        .catch(()=>{});
};


function r22TranslateCandidatePage(d){

    if(!d || !d.translations){
        return;
    }

    const t=d.translations;

    const hero=document.querySelector(
        '#content .portal-hero'
    );

    if(hero){

        const h1=hero.querySelector('h1');
        const p=hero.querySelector('p');

        if(h1){

            const first=(
                ME?.name
                ||''
            ).split(/\s+/)[0];

            h1.textContent=
                t.welcome
                +(first?', '+first:'');
        }

        if(p){
            p.textContent=t.subtitle;
        }
    }


    const titleMap={
        'My Applications':
            t.my_applications,

        'Profile Credibility':
            t.profile_credibility,

        'Availability':
            t.availability,
    };


    document
        .querySelectorAll(
            '#content .panel-title span'
        )
        .forEach(el=>{

            const key=
                el.textContent.trim();

            if(titleMap[key]){
                el.textContent=
                    titleMap[key];
            }
        });


    document
        .querySelectorAll(
            '#content h2'
        )
        .forEach(el=>{

            if(
                el.textContent.trim()
                ==='Open Positions'
            ){
                el.textContent=
                    t.open_positions;
            }
        });


    const headerMap={
        'Job':t.job,
        'Status':t.status,
        'Submitted':t.submitted,
    };

    document
        .querySelectorAll(
            '#content th'
        )
        .forEach(el=>{

            const key=
                el.textContent.trim();

            if(headerMap[key]){
                el.textContent=
                    headerMap[key];
            }
        });


    document
        .querySelectorAll(
            '#content .jobcard button'
        )
        .forEach(el=>{
            el.textContent=t.apply;
        });


    const firstMetric=
        document.querySelector(
            '#content .three-col .panel .panel-body p'
        );

    if(firstMetric){

        const m=
            firstMetric.textContent
                .match(/\d+/);

        if(m){
            firstMetric.textContent=
                m[0]+' '
                +t.active_processes;
        }
    }
}


async function r22EnhanceCandidateExperience(){

    const d=await api(
        '/api/r22/candidate-experience'
    );

    R22_CANDIDATE_EXPERIENCE=d;

    if(d.branding){
        r22ApplyBrandingObject(
            d.branding
        );
    }

    const page=document.querySelector(
        '#content .page'
    );

    if(!page){
        return;
    }

    const existing=
        document.getElementById(
            'r22-language-selector'
        );

    if(existing){
        existing.remove();
    }


    const box=
        document.createElement(
            'div'
        );

    box.id='r22-language-selector';
    box.className=
        'panel r22-brand-card';

    const options=
        d.supported_locales
            .map(x=>`
                <option
                    value="${esc(x.code)}"
                    ${x.code===d.locale?'selected':''}
                >
                    ${esc(x.label)}
                </option>
            `)
            .join('');


    box.innerHTML=`
        <div class="panel-body"
             style="
                display:flex;
                justify-content:flex-end;
                gap:8px;
                align-items:center
             ">
            <b>
                ${esc(d.translations.language)}
            </b>

            <select
                style="max-width:180px"
                onchange="
                    r22SetCandidateLocale(
                        this.value
                    )
                ">
                ${options}
            </select>
        </div>
    `;

    page.insertBefore(
        box,
        page.firstChild
    );

    r22TranslateCandidatePage(d);
}


async function r22SetCandidateLocale(locale){

    await api(
        '/api/r22/candidate-experience',
        {
            method:'POST',
            body:{locale}
        }
    );

    await pageCandidatePortal();
}


const R22_ORIGINAL_CANDIDATE_PORTAL=
    pageCandidatePortal;

pageCandidatePortal=async function(){

    await R22_ORIGINAL_CANDIDATE_PORTAL();

    await r22EnhanceCandidateExperience();
};


candidateApply=async function(jid,cid){

    await api(
        `/api/jobs/${jid}/interested`,
        {
            method:'POST',
            body:{
                candidate_id:cid,
                status:'interested',
                source:'Candidate Portal'
            }
        }
    );

    let message=
        'Interest registered.';

    try{

        const d=
            R22_CANDIDATE_EXPERIENCE
            ||await api(
                '/api/r22/candidate-experience'
            );

        message=
            d.translations
                .interest_registered
            ||message;

    }
    catch(_){}

    toast(message);
};


const R22_ADAPTER_DEFS={

    'reference-check':{
        label:'Reference Check',
        action:'reference_check',
    },

    'wotc':{
        label:'WOTC',
        action:'wotc_screen',
    },

    'outlook':{
        label:'Outlook',
        action:'sync_calendar',
    },

    'candidate-enrichment':{
        label:'Candidate Enrichment',
        action:'enrich_candidate',
    },
};


async function r22EnhanceAdmin(){

    const [
        branding,
        adapters
    ]=await Promise.all([
        api('/api/r22/branding'),
        api('/api/r22/adapters')
    ]);


    const page=document.querySelector(
        '#content .page'
    );

    if(!page){
        return;
    }


    const brandBody=`
        <form id="r22BrandForm">
            <div class="formgrid">

                ${formFields([
                    {
                        name:'product_name',
                        label:'Product Name',
                        value:
                            branding.product_name
                    },
                    {
                        name:'portal_title',
                        label:'Browser / Portal Title',
                        value:
                            branding.portal_title
                    },
                    {
                        name:'logo_url',
                        label:'Logo URL (HTTPS)',
                        value:
                            branding.logo_url||''
                    },
                    {
                        name:'support_email',
                        label:'Support Email',
                        value:
                            branding.support_email||''
                    },
                    {
                        name:'primary_color',
                        label:'Primary Color',
                        value:
                            branding.primary_color
                    },
                    {
                        name:'secondary_color',
                        label:'Secondary Color',
                        value:
                            branding.secondary_color
                    }
                ])}

            </div>

            <div style="margin-top:12px">
                <button
                    type="button"
                    class="btn primary"
                    onclick="r22SaveBranding()">
                    Save White-Label Branding
                </button>
            </div>
        </form>
    `;


    page.insertAdjacentHTML(
        'beforeend',
        panel(
            'White-Label Application Branding',
            brandBody
        )
    );


    const rows=
        adapters.map(a=>{

            const c=
                a.connectors[0];

            return `
                <tr>
                    <td>
                        <b>${esc(a.label)}</b>
                    </td>

                    <td>
                        ${c
                            ?esc(c.name)
                            :'Not configured'}
                    </td>

                    <td>
                        ${status(
                            c
                            ?c.connection_state
                            :'Configuration Required'
                        )}
                    </td>

                    <td>
                        <button
                            class="btn small"
                            onclick="
                                r22ConfigureAdapter(
                                    '${a.key}'
                                )
                            ">
                            Configure
                        </button>

                        ${c?`
                            <button
                                class="btn small primary"
                                onclick="
                                    r22RunAdapter(
                                        '${a.key}',
                                        ${c.id}
                                    )
                                ">
                                Execute
                            </button>
                        `:''}
                    </td>
                </tr>
            `;
        }).join('');


    page.insertAdjacentHTML(
        'beforeend',
        panel(
            'JobDiva-Compatible Provider Adapters',
            `
            <p class="subtle">
                External success is recorded only after
                an actual provider HTTP response.
                Missing credentials remain
                Credentials Required.
            </p>

            <table class="grid">
                <tr>
                    <th>Capability</th>
                    <th>Connector</th>
                    <th>State</th>
                    <th>Action</th>
                </tr>

                ${rows}
            </table>
            `
        )
    );
}


async function r22SaveBranding(){

    const form=
        document.getElementById(
            'r22BrandForm'
        );

    if(!form){
        return;
    }

    const result=await api(
        '/api/r22/branding',
        {
            method:'POST',
            body:fd(form)
        }
    );

    r22ApplyBrandingObject(
        result
    );

    toast('Branding saved');

    await pageAdmin();
}


function r22ConfigureAdapter(key){

    const d=
        R22_ADAPTER_DEFS[key];

    if(!d){
        return;
    }

    modal(
        'Configure '+d.label,
        `
        <form id="r22AdapterForm">

            <input
                type="hidden"
                name="adapter_key"
                value="${esc(key)}">

            <div class="formgrid">

                ${formFields([
                    {
                        name:'name',
                        label:'Connector Name',
                        value:d.label
                    },
                    {
                        name:'base_url',
                        label:'Provider Base URL',
                        placeholder:
                            'https://provider.example/api'
                    },
                    {
                        name:'path',
                        label:'Action Path',
                        value:'/'+d.action
                    },
                    {
                        name:'method',
                        label:'Method',
                        type:'select',
                        options:[
                            'POST',
                            'GET'
                        ],
                        value:'POST'
                    },
                    {
                        name:'auth_type',
                        label:'Authentication',
                        type:'select',
                        options:[
                            'bearer',
                            'header',
                            'basic',
                            'none'
                        ],
                        value:'bearer'
                    },
                    {
                        name:'credential_ref',
                        label:'Environment Credential Reference',
                        placeholder:
                            'PROVIDER_API_KEY'
                    },
                    {
                        name:'header_name',
                        label:'API-Key Header (header auth only)',
                        value:'X-API-Key'
                    }
                ])}

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
            onclick="
                r22SaveAdapterConfig()
            ">
            Save Connector
        </button>
        `
    );
}


async function r22SaveAdapterConfig(){

    const form=
        document.getElementById(
            'r22AdapterForm'
        );

    if(!form){
        return;
    }

    const d=fd(form);

    const def=
        R22_ADAPTER_DEFS[
            d.adapter_key
        ];

    if(!def){
        throw new Error(
            'Unknown adapter'
        );
    }

    const auth={
        type:d.auth_type
    };

    if(
        d.auth_type==='header'
    ){
        auth.header_name=
            d.header_name
            ||'X-API-Key';
    }

    const paths={};

    paths[def.action]={
        path:d.path,
        method:d.method
    };


    await api(
        '/api/integrations',
        {
            method:'POST',
            body:{
                category:
                    def.label,

                name:
                    d.name
                    ||def.label,

                mode:'External',
                status:'Configured',

                credential_ref:
                    d.auth_type==='none'
                    ?''
                    :d.credential_ref,

                config:{
                    base_url:
                        d.base_url,

                    auth,

                    paths
                },

                notes:
                    'R22 real provider adapter'
            }
        }
    );

    closeModal();

    toast(
        def.label
        +' connector configured'
    );

    await pageAdmin();
}


async function r22RunAdapter(
    key,
    connectorId
){

    const def=
        R22_ADAPTER_DEFS[key];

    if(!def){
        return;
    }

    const body={
        connector_id:
            connectorId
    };

    if(key!=='outlook'){

        const candidateId=
            prompt(
                'Candidate ID'
            );

        if(candidateId===null){
            return;
        }

        body.candidate_id=
            Number(candidateId);
    }


    try{

        const result=await api(
            `/api/r22/adapters/${key}/execute`,
            {
                method:'POST',
                body
            }
        );

        toast(
            def.label
            +': '
            +(result.status||'Complete')
        );

    }
    catch(err){

        toast(
            err.message,
            'err'
        );
    }
}


const R22_ORIGINAL_PAGE_ADMIN=
    pageAdmin;

pageAdmin=async function(){

    await R22_ORIGINAL_PAGE_ADMIN();

    await r22EnhanceAdmin();
};
