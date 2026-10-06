# R15 durable persistence

R15 replaces mutable whole-file Storage uploads with a Postgres-backed CAS object authority.
Before a production R15 deploy, run `ats_one_atomic_objects.sql` in the existing Supabase project.
The backend requires `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, and optionally
`SUPABASE_PERSISTENCE_TABLE=ats_one_atomic_objects`. A missing table or lost writer lease is a
fail-closed startup/write failure; there is no fallback to last-write-wins Storage.
