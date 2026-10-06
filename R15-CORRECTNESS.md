# ATS-One R15 correctness authority

R15 is the remediation layer for the 45-item forensic audit. The authoritative rules are:

- authorization is server-side and includes tenant, role and object ownership;
- parent IDs are tenant-owned, active relationship references and lifecycle fields do not use unrestricted generic PATCH;
- money, time and state transitions are validated before mutation;
- sensitive EEO/HR data is HR/privacy scoped;
- demo credentials exist only in explicit demo/local/test mode and the production login UI does not publish them;
- disconnected schedulers, campaigns and SSO remain configuration-only and cannot report fake execution/connection;
- external job boards, VMS, communications, screening, payroll/GL, E-Verify and production e-sign remain Not Connected until real provider proof exists;
- durable remote SQLite snapshots use a Postgres-backed compare-and-swap object authority and writer lease. Mutable last-write-wins Storage snapshots are not a supported R15 production mode;
- `SUPABASE_PERSISTENCE_TABLE=ats_one_atomic_objects` must exist before production R15 deployment (see `supabase/ats_one_atomic_objects.sql`);
- identity uses globally unique email with one primary tenant on the user row (`global-email-primary-tenant`).

Production deployment is intentionally separate from remediation. R15 branch verification must pass from a clean clone before any production change.
