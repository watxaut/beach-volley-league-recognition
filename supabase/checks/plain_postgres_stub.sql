-- ONLY for a vanilla PostgreSQL (tests/test_supabase_schema.py): the minimum
-- of Supabase the migrations rely on -- the three API roles, auth.users +
-- auth.uid(), storage.buckets/objects and Supabase's default grants.
-- NEVER run this against a Supabase project (local or hosted): it has the
-- real versions of all of this.
do $$ begin
  if not exists (select from pg_roles where rolname = 'anon') then
    create role anon nologin;
    create role authenticated nologin;
    create role service_role nologin bypassrls;
  end if;
end $$;

create schema if not exists auth;
create table if not exists auth.users (
  id    uuid primary key default gen_random_uuid(),
  email text,
  email_confirmed_at timestamptz        -- set when an invite is accepted
);
-- Same lookup order as Supabase's auth.uid().
create or replace function auth.uid() returns uuid language sql stable as $$
  select coalesce(
    nullif(current_setting('request.jwt.claim.sub', true), ''),
    (nullif(current_setting('request.jwt.claims', true), '')::jsonb ->> 'sub')
  )::uuid
$$;
grant usage on schema auth to anon, authenticated, service_role;
grant execute on function auth.uid() to anon, authenticated, service_role;

create schema if not exists storage;
create table if not exists storage.buckets (
  id                 text primary key,
  name               text not null,
  public             boolean default false,
  file_size_limit    bigint,
  allowed_mime_types text[]
);
create table if not exists storage.objects (
  id        uuid primary key default gen_random_uuid(),
  bucket_id text references storage.buckets,
  name      text,
  owner     uuid,
  created_at timestamptz default now()
);
alter table storage.objects enable row level security;
grant usage on schema storage to anon, authenticated, service_role;
grant select, insert on storage.objects to authenticated;

grant usage on schema public to anon, authenticated, service_role;
-- The PERMISSIVE defaults (every project before 2026-05-30, the local CLI
-- stack): the worst case for 20261007120000_explicit_grants.sql, which has to
-- take all of it away again.
alter default privileges in schema public grant all on tables to anon, authenticated, service_role;
alter default privileges in schema public grant all on sequences to anon, authenticated, service_role;
alter default privileges in schema public grant execute on functions to anon, authenticated, service_role;
