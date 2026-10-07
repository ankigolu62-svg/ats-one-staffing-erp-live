/*
 ATS-One R23D
 Remaining non-AI JobDiva atomic closure.

 Functional surfaces:
 - Choose Team / Profile
 - Onboarding Dashboard
 - e-Interview Dashboard
 - Recruiting Leaderboard
 - CalcuDiva Margin Calculator
 - Job Board Quota / Account Visibility
 - Collections Workflow
 - Client / Job Profitability
 - Supplier / Worker Offboarding and Termination
*/


const R23D_PREV_RENDER_SHELL =
  renderShell;


renderShell=function(){

  R23D_PREV_RENDER_SHELL();

  setTimeout(
    ()=>{

      const select=
        document.getElementById(
          'r23-context-select'
        );

      if(
        select
        &&
        !document.getElementById(
          'r23d-choose-team-label'
        )
      ){

        const label=
          document.createElement(
            'span'
          );

        label.id=
          'r23d-choose-team-label';

        label.textContent=
          'Choose Team / Profile';

        label.className=
          'subtle';

        label.style.marginLeft=
          '8px';

        select.parentNode.insertBefore(
          label,
          select
        );
      }

    },
    0
  );
};


function r23dMetric(
  label,
  value
){

  return `
    <div class="metric">
      <strong>
        ${esc(value)}
      </strong>

      <span>
        ${esc(label)}
      </span>
    </div>
  `;
}


async function r23dOnboardingDashboard(){

  const d=
    await api(
      '/api/r23d/onboarding-dashboard'
    );

  return panel(
    'Onboarding Dashboard',
    `
    <div
      class="metric-row"
      style="
        grid-template-columns:
        repeat(4,1fr)
      ">

      ${r23dMetric(
        'Total',
        d.total
      )}

      ${r23dMetric(
        'Completed',
        d.completed
      )}

      ${r23dMetric(
        'Incomplete',
        d.incomplete
      )}

      ${r23dMetric(
        'Overdue',
        d.overdue
      )}

    </div>

    <div
      class="metric-row"
      style="
        grid-template-columns:
        repeat(3,1fr);
        margin-top:12px
      ">

      ${r23dMetric(
        'Requirements',
        d.total_requirements
      )}

      ${r23dMetric(
        'Requirements Complete',
        d.completed_requirements
      )}

      ${r23dMetric(
        'Expiring ≤30 Days',
        d.expiring_30_days
      )}

    </div>

    <div
      class="tablewrap"
      style="margin-top:12px">

      <table class="grid">

        <tr>
          <th>Candidate</th>
          <th>Job</th>
          <th>Package</th>
          <th>Status</th>
          <th>Due</th>
        </tr>

        ${
          (
            d.overdue_packages
            ||[]
          )
          .map(
            x=>`
            <tr>
              <td>
                ${esc(
                  [
                    x.first_name,
                    x.last_name
                  ]
                  .filter(Boolean)
                  .join(' ')
                )}
              </td>

              <td>
                ${esc(
                  x.job_no
                  ||x.job_id
                  ||''
                )}
                ${x.title?' · '+esc(x.title):''}
              </td>

              <td>
                ${esc(
                  x.package_name
                  ||''
                )}
              </td>

              <td>
                ${status(
                  x.status
                  ||''
                )}
              </td>

              <td>
                ${esc(
                  x.due_date
                  ||''
                )}
              </td>
            </tr>
            `
          )
          .join('')
        }

      </table>

    </div>
    `
  );
}


const R23D_PREV_ONBOARDING=
  pageOnboarding;


pageOnboarding=
async function(){

  await R23D_PREV_ONBOARDING();

  if(
    ![
      'admin',
      'teamlead',
      'recruiter',
      'sales',
      'hr'
    ].includes(
      ME?.role
    )
  ){
    return;
  }

  const page=
    document.querySelector(
      '#content .page'
    );

  if(!page){
    return;
  }

  page.insertAdjacentHTML(
    'beforeend',
    await r23dOnboardingDashboard()
  );
};


const R23D_PREV_ASSESSMENTS=
  pageAssessments;


pageAssessments=
async function(){

  await R23D_PREV_ASSESSMENTS();

  if(
    ![
      'admin',
      'teamlead',
      'recruiter',
      'sales',
      'hr'
    ].includes(
      ME?.role
    )
  ){
    return;
  }

  const d=
    await api(
      '/api/r23d/e-interview-dashboard'
    );

  const page=
    document.querySelector(
      '#content .page'
    );

  if(!page){
    return;
  }

  page.insertAdjacentHTML(
    'beforeend',
    panel(
      'e-Interview Dashboard',
      `
      <div
        class="metric-row"
        style="
          grid-template-columns:
          repeat(6,1fr)
        ">

        ${r23dMetric(
          'Assessment Invites',
          d.invited
        )}

        ${r23dMetric(
          'Assessment Completed',
          d.completed
        )}

        ${r23dMetric(
          'Average Score',
          d.average_score
        )}

        ${r23dMetric(
          'Interviews',
          d.total_interviews
        )}

        ${r23dMetric(
          'Interview Complete',
          d.completed_interviews
        )}

        ${r23dMetric(
          'No Show',
          d.no_show
        )}

      </div>
      `
    )
  );
};


async function r23dReportsPanels(){

  const [
    leaderboard,
    profitability
  ] =
    await Promise.all([
      api(
        '/api/r23d/recruiting-leaderboard'
      ),

      api(
        '/api/r23d/profitability'
      )
    ]);


  const leaderHtml=
    panel(
      'Recruiting Leaderboard',
      `
      <div class="tablewrap">
        <table class="grid">

          <tr>
            <th>Rank</th>
            <th>User</th>
            <th>Role</th>
            <th>Submissions</th>
            <th>Interviews</th>
            <th>Placements</th>
            <th>Score</th>
          </tr>

          ${
            leaderboard.rows.map(
              x=>`
              <tr>
                <td>${x.rank}</td>
                <td>${esc(x.name)}</td>
                <td>${esc(x.role)}</td>
                <td>${x.submissions}</td>
                <td>${x.interviews}</td>
                <td>${x.placements}</td>
                <td>${x.activity_score}</td>
              </tr>
              `
            ).join('')
          }

        </table>
      </div>
      `
    );


  const profitHtml=
    panel(
      'Client / Job Profitability',
      `
      <div
        class="metric-row"
        style="
          grid-template-columns:
          repeat(4,1fr)
        ">

        ${r23dMetric(
          'Revenue',
          money(
            profitability.revenue
          )
        )}

        ${r23dMetric(
          'Cost',
          money(
            profitability.cost
          )
        )}

        ${r23dMetric(
          'Gross Margin',
          money(
            profitability.gross_margin
          )
        )}

        ${r23dMetric(
          'Margin %',
          profitability.margin_percent
          +'%'
        )}

      </div>

      <div
        class="tablewrap"
        style="margin-top:12px">

        <table class="grid">

          <tr>
            <th>Client</th>
            <th>Job</th>
            <th>Hours</th>
            <th>Revenue</th>
            <th>Cost</th>
            <th>Gross Margin</th>
            <th>Margin %</th>
          </tr>

          ${
            profitability.rows.map(
              x=>`
              <tr>
                <td>
                  ${esc(
                    x.company_name
                    ||''
                  )}
                </td>

                <td>
                  ${esc(
                    x.job_no
                    ||x.job_id
                    ||''
                  )}
                  ${x.job_title?' · '+esc(x.job_title):''}
                </td>

                <td>
                  ${Number(
                    x.approved_hours
                    ||0
                  )}
                </td>

                <td>
                  ${money(
                    x.revenue
                  )}
                </td>

                <td>
                  ${money(
                    x.cost
                  )}
                </td>

                <td>
                  ${money(
                    x.gross_margin
                  )}
                </td>

                <td>
                  ${x.margin_percent}%
                </td>
              </tr>
              `
            ).join('')
          }

        </table>

      </div>
      `
    );


  return (
    leaderHtml
    +
    profitHtml
  );
}


const R23D_PREV_REPORTS=
  pageReports;


pageReports=
async function(){

  await R23D_PREV_REPORTS();

  if(
    ![
      'admin',
      'teamlead',
      'recruiter',
      'sales',
      'hr',
      'finance'
    ].includes(
      ME?.role
    )
  ){
    return;
  }

  const page=
    document.querySelector(
      '#content .page'
    );

  if(!page){
    return;
  }

  try{

    page.insertAdjacentHTML(
      'beforeend',
      await r23dReportsPanels()
    );

  }
  catch(_){}
};


async function r23dOpenMarginCalculator(){

  modal(
    'CalcuDiva Margin Calculator',
    `
    <form id="r23d-margin-form">

      <div class="formgrid">

        <div class="field">
          <label>Bill Rate</label>
          <input
            name="bill_rate"
            type="number"
            step="0.01"
            required>
        </div>

        <div class="field">
          <label>Pay Rate</label>
          <input
            name="pay_rate"
            type="number"
            step="0.01"
            required>
        </div>

        <div class="field">
          <label>Burden %</label>
          <input
            name="burden_percent"
            type="number"
            step="0.01"
            value="12">
        </div>

        <div class="field">
          <label>Target Margin %</label>
          <input
            name="target_margin_percent"
            type="number"
            step="0.01"
            value="20">
        </div>

      </div>

      <div
        id="r23d-margin-result"
        style="margin-top:14px">
      </div>

    </form>
    `,
    `
    <button
      class="btn"
      onclick="closeModal()">
      Close
    </button>

    <button
      class="btn primary"
      onclick="r23dCalculateMargin()">
      Calculate
    </button>
    `
  );
}


async function r23dCalculateMargin(){

  const d=
    fd(
      document.getElementById(
        'r23d-margin-form'
      )
    );

  const r=
    await api(
      '/api/r23d/margin-calculator',
      {
        method:'POST',
        body:d
      }
    );

  document.getElementById(
    'r23d-margin-result'
  ).innerHTML=`

    <div class="metric-row"
      style="
        grid-template-columns:
        repeat(4,1fr)
      ">

      ${r23dMetric(
        'Loaded Cost',
        money(r.loaded_cost)
      )}

      ${r23dMetric(
        'Gross Profit',
        money(r.gross_profit)
      )}

      ${r23dMetric(
        'Gross Margin %',
        r.gross_margin_percent+'%'
      )}

      ${r23dMetric(
        'Target Bill Rate',
        r.target_bill_rate===null
        ?'-'
        :money(r.target_bill_rate)
      )}

    </div>
  `;
}


async function r23dCollectionAction(
  invoiceId
){

  modal(
    'Collections Workflow',
    `
    <form id="r23d-collection-form">

      <div class="formgrid">

        <div class="field">
          <label>Action</label>

          <select name="action_type">
            <option>Follow Up</option>
            <option>Promise To Pay</option>
            <option>Dispute</option>
            <option>Escalation</option>
            <option>Final Notice</option>
          </select>
        </div>

        <div class="field">
          <label>Status</label>

          <select name="status">
            <option>Open</option>
            <option>Promise To Pay</option>
            <option>Disputed</option>
            <option>Escalated</option>
            <option>Closed</option>
          </select>
        </div>

        <div class="field">
          <label>Promised Amount</label>

          <input
            name="promised_amount"
            type="number"
            step="0.01">
        </div>

        <div class="field">
          <label>Promise Date</label>

          <input
            name="promise_date"
            type="date">
        </div>

        <div
          class="field"
          style="grid-column:1/-1">

          <label>Note</label>

          <textarea
            name="note"
            rows="4"></textarea>
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
      onclick="
        r23dSubmitCollection(
          ${Number(invoiceId)}
        )
      ">
      Save Action
    </button>
    `
  );
}


async function r23dSubmitCollection(
  invoiceId
){

  const body=
    fd(
      document.getElementById(
        'r23d-collection-form'
      )
    );

  await api(
    `/api/r23d/collections/${Number(invoiceId)}/action`,
    {
      method:'POST',
      body
    }
  );

  closeModal();

  toast(
    'Collection action saved'
  );

  await pageFinance();
}


const R23D_PREV_FINANCE=
  pageFinance;


pageFinance=
async function(){

  await R23D_PREV_FINANCE();

  if(
    ![
      'admin',
      'finance'
    ].includes(
      ME?.role
    )
  ){
    return;
  }

  const page=
    document.querySelector(
      '#content .page'
    );

  if(!page){
    return;
  }

  const collections=
    await api(
      '/api/r23d/collections'
    );


  page.insertAdjacentHTML(
    'beforeend',
    panel(
      'CalcuDiva Margin Calculator',
      `
      <p class="subtle">
        Bill rate, pay rate, burden,
        markup and gross margin calculator.
      </p>

      <button
        class="btn primary"
        onclick="r23dOpenMarginCalculator()">

        Open Margin Calculator

      </button>
      `
    )
  );


  page.insertAdjacentHTML(
    'beforeend',
    panel(
      'Collections Workflow',
      `
      <div class="kv">
        <b>Total Outstanding</b>

        <span>
          ${money(
            collections.total_outstanding
          )}
        </span>
      </div>

      <div class="tablewrap">

        <table class="grid">

          <tr>
            <th>Invoice</th>
            <th>Client</th>
            <th>Status</th>
            <th>Aging</th>
            <th>Balance</th>
            <th>Latest Collection</th>
            <th></th>
          </tr>

          ${
            collections.invoices.map(
              x=>`
              <tr>
                <td>
                  ${esc(
                    x.invoice_no
                    ||x.id
                  )}
                </td>

                <td>
                  ${esc(
                    x.company_name
                    ||''
                  )}
                </td>

                <td>
                  ${status(
                    x.status
                    ||''
                  )}
                </td>

                <td>
                  ${Number(
                    x.aging_days
                    ||0
                  )} days
                </td>

                <td>
                  ${money(
                    x.balance
                  )}
                </td>

                <td>
                  ${
                    x.latest_collection
                    ?esc(
                      x.latest_collection
                      .action_type
                    )
                    :'—'
                  }
                </td>

                <td>
                  <button
                    class="btn small"
                    onclick="
                      r23dCollectionAction(
                        ${x.id}
                      )
                    ">
                    Action
                  </button>
                </td>
              </tr>
              `
            ).join('')
          }

        </table>

      </div>
      `
    )
  );


  try{

    const profit=
      await api(
        '/api/r23d/profitability'
      );

    page.insertAdjacentHTML(
      'beforeend',
      panel(
        'Client / Job Profitability',
        `
        <div
          class="metric-row"
          style="
            grid-template-columns:
            repeat(4,1fr)
          ">

          ${r23dMetric(
            'Revenue',
            money(profit.revenue)
          )}

          ${r23dMetric(
            'Cost',
            money(profit.cost)
          )}

          ${r23dMetric(
            'Gross Margin',
            money(profit.gross_margin)
          )}

          ${r23dMetric(
            'Margin %',
            profit.margin_percent+'%'
          )}

        </div>
        `
      )
    );

  }
  catch(_){}
};


async function r23dAddJobBoardAccount(){

  modal(
    'Job Board Account / Quota',
    `
    <form id="r23d-jobboard-form">

      <div class="formgrid">

        <div class="field">
          <label>Provider</label>
          <input
            name="provider"
            placeholder="Monster / CareerBuilder / Dice"
            required>
        </div>

        <div class="field">
          <label>Account Name</label>
          <input
            name="account_name"
            required>
        </div>

        <div class="field">
          <label>Total Quota</label>
          <input
            name="quota_total"
            type="number"
            value="0">
        </div>

        <div class="field">
          <label>Quota Used</label>
          <input
            name="quota_used"
            type="number"
            value="0">
        </div>

        <div class="field">
          <label>Quota Reset</label>
          <input
            name="quota_reset_at"
            type="date">
        </div>

        <div class="field">
          <label>Contract End</label>
          <input
            name="contract_end"
            type="date">
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
      onclick="r23dSaveJobBoardAccount()">
      Save
    </button>
    `
  );
}


async function r23dSaveJobBoardAccount(){

  const body=
    fd(
      document.getElementById(
        'r23d-jobboard-form'
      )
    );

  await api(
    '/api/r23d/job-board-accounts',
    {
      method:'POST',
      body
    }
  );

  closeModal();

  toast(
    'Job board account saved'
  );

  await pageAdmin();
}


const R23D_PREV_ADMIN=
  pageAdmin;


pageAdmin=
async function(){

  await R23D_PREV_ADMIN();

  if(
    ME?.role
    !=='admin'
  ){
    return;
  }

  const d=
    await api(
      '/api/r23d/job-board-accounts'
    );

  const page=
    document.querySelector(
      '#content .page'
    );

  if(!page){
    return;
  }


  page.insertAdjacentHTML(
    'beforeend',
    panel(
      'Job Board Quota / Account Visibility',
      `
      <div style="margin-bottom:10px">

        <button
          class="btn primary"
          onclick="r23dAddJobBoardAccount()">

          + Job Board Account

        </button>

      </div>

      <div class="tablewrap">

        <table class="grid">

          <tr>
            <th>Provider</th>
            <th>Account</th>
            <th>Status</th>
            <th>Quota Total</th>
            <th>Used</th>
            <th>Remaining</th>
            <th>Reset</th>
          </tr>

          ${
            d.accounts.map(
              x=>`
              <tr>
                <td>${esc(x.provider)}</td>
                <td>${esc(x.account_name)}</td>
                <td>${status(x.status)}</td>
                <td>${x.quota_total}</td>
                <td>${x.quota_used}</td>
                <td>${x.quota_remaining}</td>
                <td>${esc(x.quota_reset_at||'')}</td>
              </tr>
              `
            ).join('')
          }

        </table>

      </div>
      `
    )
  );
};


async function r23dOpenOffboarding(){

  modal(
    'Supplier / Worker Offboarding and Termination',
    `
    <form id="r23d-offboarding-form">

      <div class="formgrid">

        <div class="field">
          <label>Assignment ID</label>

          <input
            name="assignment_id"
            type="number"
            required>
        </div>

        <div class="field">
          <label>Supplier ID (optional)</label>

          <input
            name="supplier_id"
            type="number">
        </div>

        <div
          class="field"
          style="grid-column:1/-1">

          <label>Termination Reason</label>

          <textarea
            name="termination_reason"
            rows="4"
            required></textarea>
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
      onclick="r23dSubmitOffboarding()">
      Start Offboarding
    </button>
    `
  );
}


async function r23dSubmitOffboarding(){

  const body=
    fd(
      document.getElementById(
        'r23d-offboarding-form'
      )
    );

  await api(
    '/api/r23d/vms-offboarding',
    {
      method:'POST',
      body
    }
  );

  closeModal();

  toast(
    'Offboarding started'
  );

  await pageVMS();
}


async function r23dCompleteOffboarding(
  id
){

  await api(
    `/api/r23d/vms-offboarding/${Number(id)}/complete`,
    {
      method:'POST',
      body:{}
    }
  );

  toast(
    'Offboarding completed'
  );

  await pageVMS();
}


const R23D_PREV_VMS=
  pageVMS;


pageVMS=
async function(){

  await R23D_PREV_VMS();

  if(
    ![
      'admin',
      'teamlead',
      'hr'
    ].includes(
      ME?.role
    )
  ){
    return;
  }

  const d=
    await api(
      '/api/r23d/vms-offboarding'
    );

  const page=
    document.querySelector(
      '#content .page'
    );

  if(!page){
    return;
  }


  page.insertAdjacentHTML(
    'beforeend',
    panel(
      'Supplier / Worker Offboarding and Termination',
      `
      <div style="margin-bottom:10px">

        <button
          class="btn primary"
          onclick="r23dOpenOffboarding()">

          + Start Offboarding

        </button>

      </div>

      <div class="tablewrap">

        <table class="grid">

          <tr>
            <th>Worker</th>
            <th>Job</th>
            <th>Supplier</th>
            <th>Status</th>
            <th>Termination Reason</th>
            <th></th>
          </tr>

          ${
            d.cases.map(
              x=>`
              <tr>
                <td>
                  ${esc(
                    [
                      x.first_name,
                      x.last_name
                    ]
                    .filter(Boolean)
                    .join(' ')
                  )}
                </td>

                <td>
                  ${esc(
                    x.job_no
                    ||x.assignment_id
                  )}
                  ${x.job_title?' · '+esc(x.job_title):''}
                </td>

                <td>
                  ${esc(
                    x.supplier_name
                    ||''
                  )}
                </td>

                <td>
                  ${status(
                    x.status
                  )}
                </td>

                <td>
                  ${esc(
                    x.termination_reason
                    ||''
                  )}
                </td>

                <td>
                  ${
                    x.status!=='Completed'
                    ?`
                      <button
                        class="btn small"
                        onclick="
                          r23dCompleteOffboarding(
                            ${x.id}
                          )
                        ">
                        Complete
                      </button>
                    `
                    :''
                  }
                </td>
              </tr>
              `
            ).join('')
          }

        </table>

      </div>
      `
    )
  );
};
