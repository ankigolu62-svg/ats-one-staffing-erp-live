# ATS One Staffing ERP

A local, shared-database, multi-user staffing ERP built around the same broad operating model as enterprise staffing platforms: sourcing, candidate records, jobs, CRM, submittals, interviews, onboarding, assignments, time/expense, finance, VMS/MSP mapping, supplier access, reporting, audit and role portals.

## Windows — fastest start

Double-click `RUN-WINDOWS.cmd`, or right-click `RUN-WINDOWS.ps1` → **Run with PowerShell**.

The launcher:
1. validates the package,
2. uses an existing Python 3 installation if available,
3. if Python is missing, attempts a one-time user install through Windows `winget`,
4. finds a free port,
5. starts the local server and opens the browser.

No npm, Node, Java or external database is required.

## LAN / real simultaneous multi-user test

Run `RUN-LAN-WINDOWS.ps1` on the host PC. The script prints a LAN URL such as `http://192.168.1.25:8765/`.

Open that URL from multiple browsers/devices on the same trusted network and sign in with different roles. Every session uses the same SQLite database. SQLite WAL mode and a threaded HTTP server are enabled for concurrent local users.

## macOS / Linux

Run:

```bash
chmod +x RUN-MAC-LINUX.sh
./RUN-MAC-LINUX.sh
```

Python 3.11+ must already exist on macOS/Linux.

## Data

The working database is created automatically at `data/ats_one.db` on first start. Admin has a **Reset Database** function that restores the seeded data.

## Important external-integration boundary

The local product has working internal workflows and VMS/integration mapping objects. Real LinkedIn/job-board APIs, Fieldglass/Beeline, production email/SMS, payroll/GL, background checks, E-Verify or legally-certified e-signature services require vendor accounts, credentials and contracts. They cannot be made genuinely live with fabricated credentials.

See `FUNCTION-MAP.md`, `ARCHITECTURE.md`, `DEMO-USERS.txt` and `ACCEPTANCE-RESULT.txt`.

## Free live deployment (Render + Supabase Storage)

Use `DEPLOY-FREE-LIVE.ps1`. This hardened package is designed to run on a free Render web service and persist its SQLite database privately to Supabase Storage across free-instance restarts/spin-downs. The deployment controller creates/pushes a GitHub repository, provisions/uses a Supabase project, creates the Render service, and fails closed unless `/api/health` reports `persistence=supabase-storage`.

This is a free testing/evaluation architecture, not high-scale production. The included deep audit must show `FAIL=0`; remaining `PARTIAL`/`EXTERNAL` items are still explicitly reported and are not treated as completed functionality.
