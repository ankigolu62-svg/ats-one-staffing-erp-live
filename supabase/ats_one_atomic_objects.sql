-- ATS-One R15 persistence authority table.
-- Install once in the Supabase project's SQL editor before deploying R15.
create table if not exists public.ats_one_atomic_objects (
  key text primary key,
  data_b64 text not null,
  version bigint not null default 1 check (version > 0),
  updated_at timestamptz not null default now()
);

create index if not exists ats_one_atomic_objects_updated_idx
  on public.ats_one_atomic_objects(updated_at desc);

alter table public.ats_one_atomic_objects enable row level security;

-- No anon/authenticated policies are intentionally created. The application
-- uses the server-side service_role key, which bypasses RLS. Never expose that
-- key to the browser.
