-- Match details for telling matches apart (owner, 2026-10-14).
--
-- An admin tags each match from dropdowns, so the values stay the same from
-- match to match:
--   * venue: picked from `venues`, a list an admin can add to;
--   * match type: the match's DIVISION (male / female / mixed). It describes
--     the match, never a player: no gender is stored for anybody;
--   * tournament or not and, for a tournament, its level. Pro / amateur is
--     carried by the level (local amateur / local pro / regional / national).
-- All of it is ADMIN-OWNED like title / season: a publish never writes it
-- (`ingest_match_bundle` inserts only the key and the date) and
-- `src/publish/backup.py` exports it.
--
-- The player page compares a player with everyone else in the same match type:
-- `leaderboard` and `window_matches` take the type as a new last parameter, so
-- "the last N matches" counts within the type. League tier, like the rest of
-- the leaderboard.

-- ════════════════════════════════════════════════════════════════════════
-- venues: one spelling per place, added from the admin page
-- ════════════════════════════════════════════════════════════════════════
create table public.venues (
  name       text primary key check (name = btrim(name) and name <> ''),
  created_at timestamptz not null default now()
);
create unique index venues_name_ci on public.venues (lower(name));

-- the venues typed so far become the list (one spelling per lower-case name,
-- a capitalised one first), and every match is written with that spelling
update public.matches set venue = nullif(btrim(venue), '') where venue is distinct from nullif(btrim(venue), '');
insert into public.venues (name)
select distinct on (lower(venue)) venue from public.matches where venue is not null
order by lower(venue), venue = lower(venue), venue collate "C";
update public.matches m set venue = v.name
from public.venues v where lower(m.venue) = lower(v.name) and m.venue <> v.name;

alter table public.matches
  add constraint matches_venue_fkey foreign key (venue) references public.venues (name) on update cascade;

alter table public.venues enable row level security;
create policy members_read on public.venues for select to authenticated using (true);
create policy admin_insert on public.venues for insert to authenticated
  with check (public.is_admin());

-- explicit privileges (20261007120000): nothing for anon, add-only for admins
grant select, insert on public.venues to authenticated;
grant select on public.venues to service_role;

-- ════════════════════════════════════════════════════════════════════════
-- match type, tournament, level
-- ════════════════════════════════════════════════════════════════════════
alter table public.matches
  add column match_type text check (match_type in ('male', 'female', 'mixed')),
  add column is_tournament boolean,
  add column tournament_level text
    check (tournament_level in ('local_amateur', 'local_pro', 'regional', 'national')),
  add constraint matches_level_needs_tournament check (tournament_level is null or is_tournament);

grant update (match_type, is_tournament, tournament_level) on public.matches to authenticated;

-- ════════════════════════════════════════════════════════════════════════
-- window_matches + leaderboard: an optional match type
-- ════════════════════════════════════════════════════════════════════════
drop function public.window_matches(text, date, date, int, bigint, boolean);
create function public.window_matches(
  p_season text, p_from date, p_to date, p_last_n int,
  p_player bigint default null, p_drafts boolean default false,
  p_match_type text default null)
returns setof bigint
language sql stable security definer set search_path = public as $$
  select w.id from (
    select m.id,
           row_number() over (order by m.match_date desc, m.start_time desc nulls last, m.id desc) as rn
    from public.matches m
    where auth.uid() is not null
      and (m.status = 'published' or (p_drafts and public.is_admin()))
      and (p_season is null or m.season = p_season)
      and (p_from is null or m.match_date >= p_from)
      and (p_to is null or m.match_date <= p_to)
      and (p_match_type is null or m.match_type = p_match_type)
      and (p_player is null or exists (
            select 1 from public.match_participants mp
            where mp.match_id = m.id and mp.player_id = p_player))
  ) w
  where p_last_n is null or w.rn <= p_last_n
$$;
-- internal: only the definer functions call it
revoke execute on function public.window_matches(text, date, date, int, bigint, boolean, text)
  from public, anon, authenticated;

drop function public.leaderboard(text, date, date, int);
create function public.leaderboard(
  p_season text default null, p_from date default null, p_to date default null,
  p_last_n int default null, p_match_type text default null)
returns table (player_id bigint, display_name text, matches bigint, wins bigint,
               fantasy numeric, kills bigint, aces bigint, digs bigint,
               assists bigint, blocks bigint, errors bigint,
               attacks bigint, attack_errors bigint, serves bigint,
               points_played bigint, fantasy_per_21 numeric,
               serve_errors bigint, recv_points bigint, recv_won bigint,
               serve_points bigint, serve_won bigint)
language sql stable security definer set search_path = public as $$
  with rally as (
    select p.match_id, tm.team,
           count(*) filter (where p.serving_team = tm.team)                              as serve_n,
           count(*) filter (where p.serving_team = tm.team and p.winner_team = tm.team)  as serve_won,
           count(*) filter (where p.serving_team <> tm.team)                             as recv_n,
           count(*) filter (where p.serving_team <> tm.team and p.winner_team = tm.team) as recv_won
    from public.points p
    cross join (values ('A'), ('B')) as tm(team)
    where p.winner_team is not null
      and p.match_id in (select public.window_matches(p_season, p_from, p_to, p_last_n,
                                                      p_match_type => p_match_type))
    group by p.match_id, tm.team
  )
  select p.id, p.display_name,
         count(distinct f.match_id),
         count(distinct f.match_id) filter (where f.team = m.winner_team),
         sum(f.fantasy),
         sum(f.kills)::bigint, sum(f.aces)::bigint, sum(f.digs)::bigint,
         sum(f.assists)::bigint, sum(f.blocks)::bigint,
         sum(f.serve_errors + f.attack_errors + f.handling_errors)::bigint,
         sum(f.attacks)::bigint, sum(f.attack_errors)::bigint, sum(f.serves)::bigint,
         coalesce(sum(m.n_points), 0)::bigint,
         round(sum(f.fantasy) / nullif(sum(m.n_points), 0) * 21, 1),
         sum(f.serve_errors)::bigint,
         coalesce(sum(r.recv_n), 0)::bigint, coalesce(sum(r.recv_won), 0)::bigint,
         coalesce(sum(r.serve_n), 0)::bigint, coalesce(sum(r.serve_won), 0)::bigint
  from public.player_match_fantasy f
  join public.matches m on m.id = f.match_id
  join public.players p on p.id = f.player_id
  left join rally r on r.match_id = f.match_id and r.team = f.team
  where f.match_id in (select public.window_matches(p_season, p_from, p_to, p_last_n,
                                                    p_match_type => p_match_type))
  group by p.id, p.display_name
  order by sum(f.fantasy) desc, p.display_name;
$$;

-- A recreated function starts with the default EXECUTE for everyone: close
-- it, then open the read API again (members only, never anon).
revoke execute on function public.leaderboard(text, date, date, int, text)
  from public, anon, authenticated;
grant execute on function public.leaderboard(text, date, date, int, text) to authenticated;
