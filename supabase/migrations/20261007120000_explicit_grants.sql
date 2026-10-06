-- Explicit Data API privileges (security review, 2026-10-06).
--
-- The earlier migrations relied on Supabase granting ALL on every new table
-- in `public` to anon / authenticated / service_role. Projects created since
-- 2026-05-30 no longer do that (supabase.com/changelog/45329): without the
-- grants below every table read from the web app fails with 42501
-- "permission denied", and so do the keep-alive ping and `make backup`. Where
-- the old default still applies (the local CLI stack, a project created with
-- "Automatically expose new tables"), RLS was the ONLY thing between the
-- public key and every table.
--
-- From here on the grants are the first gate and RLS the second:
--   anon           no table, view or sequence; EXECUTE on ping() only
--   authenticated  SELECT everywhere (RLS picks the rows); writes only on the
--                  admin-owned tables and columns (RLS picks who)
--   service_role   the publish RPCs (granted in init.sql) and SELECT on what
--                  `make backup` exports -- its writes go through the RPC
-- A NEW table or view gets NOTHING until its migration grants it.

-- ════════════════════════════════════════════════════════════════════════
-- same starting point on every stack: no automatic exposure
-- ════════════════════════════════════════════════════════════════════════
alter default privileges in schema public
  revoke all on tables from anon, authenticated, service_role;
alter default privileges in schema public
  revoke all on sequences from anon, authenticated, service_role;
revoke all on all tables    in schema public from anon, authenticated, service_role;
revoke all on all sequences in schema public from anon, authenticated, service_role;

-- ════════════════════════════════════════════════════════════════════════
-- members and admins (the web app)
-- ════════════════════════════════════════════════════════════════════════
grant select on
  public.profiles, public.players, public.matches, public.match_sources,
  public.match_participants, public.points, public.actions, public.match_publications,
  public.fantasy_rulesets, public.fantasy_rules,
  public.player_match_stats, public.action_fantasy, public.player_match_fantasy,
  public.touch_context
  to authenticated;

-- Admin-owned tables: the admin_* policies decide who.
grant insert, update, delete on
  public.players, public.fantasy_rulesets, public.fantasy_rules
  to authenticated;

-- Tables that mix both owners: only the admin-owned COLUMNS are writable, so
-- not even an admin session can rewrite a score or a thumbnail path through
-- the API (the ownership rule of init.sql, now enforced by the database).
grant update (title, venue, season, status, detail_public) on public.matches to authenticated;
grant update (player_id) on public.match_participants to authenticated;
grant update (role, display_name) on public.profiles to authenticated;

-- ════════════════════════════════════════════════════════════════════════
-- the laptop (secret key): `make backup` reads the admin-owned tables
-- ════════════════════════════════════════════════════════════════════════
grant select on
  public.profiles, public.players, public.matches, public.match_participants,
  public.fantasy_rulesets, public.fantasy_rules
  to service_role;

-- ════════════════════════════════════════════════════════════════════════
-- ping(): the keep-alive runs as anon, which no longer reads any table, so
-- the function reads the count as its owner. Still exposes nothing.
-- ════════════════════════════════════════════════════════════════════════
create or replace function public.ping() returns text
language sql stable security definer set search_path = public as $$
  select 'ok:' || (select count(*) from public.fantasy_rulesets)::text;
$$;
