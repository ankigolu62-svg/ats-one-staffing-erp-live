/*
 ATS_LOGIN_FROZEN_OPEN_R3

 Public login boundary:
 - normal email/password login preserved
 - all 11 seeded role shortcuts visible
 - MFA field removed from public login surface
 - candidate registration CTA removed from login surface

 Backend MFA remains available.
 Candidate registration capability remains available elsewhere.
 RBAC, profiles, permissions and business functions remain unchanged.
*/

(function () {

  const USERS = [
    ['System Administrator', 'admin@atsone.local', 'Admin@123'],
    ['Team Lead', 'teamlead@atsone.local', 'Lead@123'],
    ['Recruiter', 'recruiter@atsone.local', 'Recruit@123'],
    ['Sales / Account Manager', 'sales@atsone.local', 'Sales@123'],
    ['HR / Onboarding', 'hr@atsone.local', 'HR@123'],
    ['Finance / Payroll', 'finance@atsone.local', 'Finance@123'],
    ['Client / Hiring Manager', 'client@atsone.local', 'Client@123'],
    ['Candidate', 'candidate@atsone.local', 'Candidate@123'],
    ['Worker / Consultant', 'worker@atsone.local', 'Worker@123'],
    ['Supplier', 'supplier@atsone.local', 'Supplier@123'],
    ['Timesheet / Expense Approver', 'approver@atsone.local', 'Approve@123']
  ];

  const previousRenderLogin =
    window.renderLogin;

  if (
    typeof previousRenderLogin !== 'function'
  ) {
    console.error(
      'ATS_LOGIN_FREEZE_RENDER_LOGIN_MISSING'
    );
    return;
  }

  function cleanLoginSurface() {

    const form =
      document.getElementById(
        'loginForm'
      );

    if (form) {

      const mfa =
        form.querySelector(
          '[name="mfa_code"]'
        );

      if (mfa) {

        const field =
          mfa.closest('.field');

        if (field) {
          field.remove();
        }
        else {
          mfa.remove();
        }
      }
    }

    const registration =
      document.getElementById(
        'r23c-register-button'
      );

    if (registration) {
      registration.remove();
    }
  }

  function installStyles() {

    if (
      document.getElementById(
        'ats-open-role-style'
      )
    ) {
      return;
    }

    const style =
      document.createElement(
        'style'
      );

    style.id =
      'ats-open-role-style';

    style.textContent = `
      #ats-open-role-access {
        margin-top: 18px;
        padding-top: 16px;
        border-top: 1px solid rgba(120,130,150,.25);
      }

      #ats-open-role-access .ats-role-heading {
        font-size: 13px;
        font-weight: 800;
        margin-bottom: 4px;
      }

      #ats-open-role-access .ats-role-help {
        font-size: 11px;
        opacity: .72;
        margin-bottom: 10px;
      }

      #ats-open-role-access .ats-role-grid {
        display: grid;
        grid-template-columns: 1fr;
        gap: 7px;
      }

      #ats-open-role-access .ats-role-button {
        width: 100%;
        text-align: left;
        padding: 9px 11px;
        cursor: pointer;
      }

      #ats-open-role-access .ats-role-button strong {
        display: block;
        font-size: 12px;
      }

      #ats-open-role-access .ats-role-button small {
        display: block;
        margin-top: 2px;
        font-size: 10px;
        opacity: .72;
      }
    `;

    document.head.appendChild(
      style
    );
  }

  function addOpenRoleAccess() {

    const target =
      document.querySelector(
        '.login-form'
      );

    if (!target) {
      return;
    }

    if (
      document.getElementById(
        'ats-open-role-access'
      )
    ) {
      return;
    }

    installStyles();

    const box =
      document.createElement(
        'div'
      );

    box.id =
      'ats-open-role-access';

    const heading =
      document.createElement(
        'div'
      );

    heading.className =
      'ats-role-heading';

    heading.textContent =
      'OPEN ROLE ACCESS';

    const help =
      document.createElement(
        'div'
      );

    help.className =
      'ats-role-help';

    help.textContent =
      'Select a role to open ATS One.';

    const grid =
      document.createElement(
        'div'
      );

    grid.className =
      'ats-role-grid';

    USERS.forEach(
      ([label, email, password]) => {

        const button =
          document.createElement(
            'button'
          );

        button.type =
          'button';

        button.className =
          'btn ats-role-button';

        button.innerHTML =
          '<strong>' +
          label +
          '</strong><small>' +
          email +
          '</small>';

        button.onclick =
          async function () {

            button.disabled =
              true;

            try {

              await api(
                '/api/login',
                {
                  method: 'POST',
                  body: {
                    email,
                    password
                  }
                }
              );

              await boot();

            }
            catch (e) {

              button.disabled =
                false;

              toast(
                e.message,
                'err'
              );
            }
          };

        grid.appendChild(
          button
        );
      }
    );

    box.appendChild(
      heading
    );

    box.appendChild(
      help
    );

    box.appendChild(
      grid
    );

    target.appendChild(
      box
    );
  }

  window.renderLogin =
    function () {

      previousRenderLogin();

      cleanLoginSurface();

      addOpenRoleAccess();
    };

  window.ATS_LOGIN_FROZEN =
    'OPEN_11_ROLE_SHORTCUTS_R3';

})();
