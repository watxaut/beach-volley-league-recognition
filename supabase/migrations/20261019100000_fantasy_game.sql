-- The fantasy GAME (owner, 2026-10-19): match days, lineups, captain, tables.
--
-- Until now "fantasy" was a stat: points per player per match
-- (`player_match_fantasy`, the active rule set). This adds the game played on
-- top of it, the VNL / FPL pattern:
--   * a MATCH DAY groups FIXTURES (matches scheduled ahead: time, venue, the
--     pair on each side), in a season (`season` text, as `matches.season`);
--   * a member picks `squad_size` players of that day under a `budget`, one of
--     them captain (points x `captain_multiplier`), until the day LOCKS at its
--     first scheduled match; lineups stay private until then;
--   * prices are a SNAPSHOT taken when an admin opens the day (5.0 .. 10.0 by
--     the player's percentile of fantasy per 21 over their last 10 published
--     matches, 7.5 without history; an admin may override before opening);
--   * an admin links each fixture to its published match (the video) and
--     publishes it TO FANTASY: only then do its points count.
-- Points follow LIVE (owner decision): the game reads `player_match_fantasy`,
-- so a review, a rule change or `make republish-all` re-scores past days.
-- A player scores the sum over the day's fixtures published to fantasy in
-- which they were assigned a slot -- by player, never by slot (an unknown
-- slot is nobody's). A member writes only through `save_lineup`.

-- ════════════════════════════════════════════════════════════════════════
-- tables
-- ════════════════════════════════════════════════════════════════════════
create table public.fantasy_match_days (
  id                 bigint generated always as identity primary key,
  season             text not null check (season = btrim(season) and season <> ''),
  name               text not null check (name = btrim(name) and name <> ''),
  status             text not null default 'draft' check (status in ('draft', 'open')),
  squad_size         smallint not null default 3 check (squad_size between 1 and 8),
  budget             numeric(5,1) not null default 22.5 check (budget > 0),
  captain_multiplier numeric(3,1) not null default 2 check (captain_multiplier >= 1),
  opened_at          timestamptz,
  created_at         timestamptz not null default now(),
  unique (season, name)
);

create table public.fantasy_fixtures (
  id                bigint generated always as identity primary key,
  match_day_id      bigint not null references public.fantasy_match_days on delete cascade,
  scheduled_at      timestamptz not null,
  venue             text references public.venues (name) on update cascade,
  match_id          bigint unique references public.matches,   -- the published video
  fantasy_published boolean not null default false,
  cancelled         boolean not null default false,
  created_at        timestamptz not null default now(),
  constraint fantasy_fixtures_published_needs_match
    check (not fantasy_published or (match_id is not null and not cancelled))
);
create index fantasy_fixtures_day on public.fantasy_fixtures (match_day_id);

-- The league players of a fixture. A guest the league does not know is simply
-- not listed: nobody can pick them.
create table public.fantasy_fixture_players (
  fixture_id bigint not null references public.fantasy_fixtures on delete cascade,
  player_id  bigint not null references public.players,
  team       char(1) not null check (team in ('A', 'B')),
  primary key (fixture_id, player_id)
);

create table public.fantasy_prices (
  match_day_id bigint not null references public.fantasy_match_days on delete cascade,
  player_id    bigint not null references public.players,
  price        numeric(4,1) not null check (price > 0),
  is_override  boolean not null default false,
  primary key (match_day_id, player_id)
);

create table public.fantasy_lineups (
  match_day_id      bigint not null references public.fantasy_match_days on delete cascade,
  user_id           uuid not null references public.profiles (user_id) on delete cascade,
  player_ids        bigint[] not null check (cardinality(player_ids) > 0),
  captain_player_id bigint not null references public.players,
  updated_at        timestamptz not null default now(),
  primary key (match_day_id, user_id),
  check (captain_player_id = any (player_ids))
);

-- ════════════════════════════════════════════════════════════════════════
-- the lock: the day's first scheduled match. A fixture cancelled after its
-- time still counts (cancelling the first match never unlocks a day); one
-- cancelled before its time moves the deadline to the next.
-- ════════════════════════════════════════════════════════════════════════
create function public.fantasy_locks_at(p_day bigint) returns timestamptz
language sql stable security definer set search_path = public as $$
  select min(scheduled_at) from public.fantasy_fixtures
  where match_day_id = p_day and (not cancelled or scheduled_at <= now())
$$;

-- League-wide suggested price (internal): 5.0 + 5.0 x the percentile of
-- fantasy per 21 over each player's last 10 published matches, to 0.5. The
-- per-21 definition is the leaderboard's (sum fantasy / sum points x 21).
create function public.fantasy_suggested_prices()
returns table (player_id bigint, price numeric, per21 numeric, n_matches bigint)
language sql stable security definer set search_path = public as $$
  with recent as (
    select f.player_id, f.fantasy, m.n_points,
           row_number() over (partition by f.player_id
                              order by m.match_date desc, m.start_time desc nulls last, m.id desc) as rn
    from public.player_match_fantasy f
    join public.matches m on m.id = f.match_id and m.status = 'published'
    where f.player_id is not null
  ), per as (
    select r.player_id, count(*) as n,
           sum(r.fantasy) / nullif(sum(r.n_points), 0) * 21 as per21
    from recent r where r.rn <= 10
    group by r.player_id
  )
  select p.player_id,
         round((5 + 5 * percent_rank() over (order by p.per21)) * 2) / 2,
         round(p.per21, 1), p.n
  from per p where p.per21 is not null
$$;

-- A player's points on a day (internal): every fixture of the day published
-- to fantasy whose match is published and in which the player had a slot.
create function public.fantasy_player_points(p_day bigint)
returns table (player_id bigint, points numeric)
language sql stable security definer set search_path = public as $$
  select f.player_id, sum(f.fantasy)
  from public.fantasy_fixtures fx
  join public.matches m on m.id = fx.match_id and m.status = 'published'
  join public.player_match_fantasy f on f.match_id = fx.match_id and f.player_id is not null
  where fx.match_day_id = p_day and fx.fantasy_published and not fx.cancelled
  group by f.player_id
$$;

-- Every lineup's points on a day (internal): the captain counts x multiplier.
create function public.fantasy_lineup_scores(p_day bigint)
returns table (user_id uuid, points numeric)
language sql stable security definer set search_path = public as $$
  select l.user_id,
         coalesce(sum(pp.points * case when pid = l.captain_player_id
                                       then d.captain_multiplier else 1 end), 0)
  from public.fantasy_lineups l
  join public.fantasy_match_days d on d.id = l.match_day_id
  cross join lateral unnest(l.player_ids) as pid
  left join public.fantasy_player_points(p_day) pp on pp.player_id = pid
  where l.match_day_id = p_day
  group by l.user_id
$$;

-- Day state (internal): locked = open and past its first match; final =
-- locked, at least one fixture published to fantasy and none still waiting.
create function public.fantasy_day_state(p_day bigint, out locks_at timestamptz,
                                         out locked boolean, out final boolean)
language sql stable security definer set search_path = public as $$
  select public.fantasy_locks_at(d.id),
         d.status = 'open' and coalesce(public.fantasy_locks_at(d.id) <= now(), false),
         d.status = 'open' and coalesce(public.fantasy_locks_at(d.id) <= now(), false)
           and exists (select 1 from public.fantasy_fixtures fx
                       where fx.match_day_id = d.id and fx.fantasy_published)
           and not exists (select 1 from public.fantasy_fixtures fx
                           where fx.match_day_id = d.id and not fx.cancelled
                             and not fx.fantasy_published)
  from public.fantasy_match_days d where d.id = p_day
$$;

-- ════════════════════════════════════════════════════════════════════════
-- guards: what an open or locked day may no longer change
-- ════════════════════════════════════════════════════════════════════════
create function public.fantasy_day_guard() returns trigger
language plpgsql set search_path = public as $$
begin
  if old.status = 'open' and (new.squad_size <> old.squad_size or new.budget <> old.budget
                              or new.captain_multiplier <> old.captain_multiplier) then
    raise exception 'the rules of an open match day are fixed';
  end if;
  return new;
end $$;
create trigger fantasy_day_guard before update on public.fantasy_match_days
  for each row execute function public.fantasy_day_guard();

create function public.fantasy_fixture_guard() returns trigger
language plpgsql security definer set search_path = public as $$
declare
  v_day    bigint := coalesce(new.match_day_id, old.match_day_id);
  v_status text;
begin
  if tg_op = 'UPDATE' and new.match_day_id <> old.match_day_id then
    raise exception 'a fixture cannot move to another match day';
  end if;
  select status into v_status from public.fantasy_match_days where id = v_day;
  if tg_op = 'DELETE' and v_status = 'open' then
    raise exception 'the match day is open: cancel the fixture instead';
  end if;
  if v_status = 'open' and public.fantasy_locks_at(v_day) <= now()
     and (tg_op = 'INSERT' or (tg_op = 'UPDATE' and new.scheduled_at <> old.scheduled_at)) then
    raise exception 'the match day is locked';
  end if;
  return coalesce(new, old);
end $$;
create trigger fantasy_fixture_guard before insert or update or delete on public.fantasy_fixtures
  for each row execute function public.fantasy_fixture_guard();

create function public.fantasy_fixture_player_guard() returns trigger
language plpgsql security definer set search_path = public as $$
declare
  v_day    bigint;
  v_status text;
begin
  select fx.match_day_id, d.status into v_day, v_status
  from public.fantasy_fixtures fx join public.fantasy_match_days d on d.id = fx.match_day_id
  where fx.id = coalesce(new.fixture_id, old.fixture_id);
  if v_status = 'open' and public.fantasy_locks_at(v_day) <= now() then
    raise exception 'the match day is locked';
  end if;
  if tg_op <> 'DELETE' and (select count(*) from public.fantasy_fixture_players
                            where fixture_id = new.fixture_id and team = new.team
                              and player_id <> new.player_id) >= 2 then
    raise exception 'a side has two players';
  end if;
  -- a player added to an open day gets the price they would have had
  if tg_op = 'INSERT' and v_status = 'open' then
    insert into public.fantasy_prices (match_day_id, player_id, price)
    values (v_day, new.player_id,
            coalesce((select s.price from public.fantasy_suggested_prices() s
                      where s.player_id = new.player_id), 7.5))
    on conflict do nothing;
  end if;
  return coalesce(new, old);
end $$;
create trigger fantasy_fixture_player_guard before insert or update or delete
  on public.fantasy_fixture_players
  for each row execute function public.fantasy_fixture_player_guard();

-- ════════════════════════════════════════════════════════════════════════
-- RLS: members read open days; admins write days and fixtures; a lineup is
-- its owner's (others' only through the definer functions, after the lock)
-- ════════════════════════════════════════════════════════════════════════
alter table public.fantasy_match_days      enable row level security;
alter table public.fantasy_fixtures        enable row level security;
alter table public.fantasy_fixture_players enable row level security;
alter table public.fantasy_prices          enable row level security;
alter table public.fantasy_lineups         enable row level security;

create policy open_or_admin_read on public.fantasy_match_days for select to authenticated
  using (status = 'open' or public.is_admin());
create policy admin_insert on public.fantasy_match_days for insert to authenticated
  with check (public.is_admin() and status = 'draft');
create policy admin_update on public.fantasy_match_days for update to authenticated
  using (public.is_admin()) with check (public.is_admin());
create policy admin_delete_draft on public.fantasy_match_days for delete to authenticated
  using (public.is_admin() and status = 'draft');

-- the day's own RLS (inside the subquery) decides who sees its rows
create policy day_visible_read on public.fantasy_fixtures for select to authenticated
  using (exists (select 1 from public.fantasy_match_days d where d.id = match_day_id));
create policy admin_write on public.fantasy_fixtures for all to authenticated
  using (public.is_admin()) with check (public.is_admin());

create policy day_visible_read on public.fantasy_fixture_players for select to authenticated
  using (exists (select 1 from public.fantasy_fixtures fx where fx.id = fixture_id));
create policy admin_write on public.fantasy_fixture_players for all to authenticated
  using (public.is_admin()) with check (public.is_admin());

create policy day_visible_read on public.fantasy_prices for select to authenticated
  using (exists (select 1 from public.fantasy_match_days d where d.id = match_day_id));

create policy own_or_admin_read on public.fantasy_lineups for select to authenticated
  using (user_id = auth.uid() or public.is_admin());

-- explicit privileges (20261007120000): nothing for anon; admins write only
-- the admin-owned columns (status, the match link and "published to fantasy"
-- go through the RPCs below); prices and lineups only through RPCs
grant select on
  public.fantasy_match_days, public.fantasy_fixtures, public.fantasy_fixture_players,
  public.fantasy_prices, public.fantasy_lineups
  to authenticated;
grant insert (season, name, squad_size, budget, captain_multiplier),
      update (season, name, squad_size, budget, captain_multiplier), delete
  on public.fantasy_match_days to authenticated;
grant insert (match_day_id, scheduled_at, venue),
      update (scheduled_at, venue, cancelled), delete
  on public.fantasy_fixtures to authenticated;
grant insert, update (team), delete on public.fantasy_fixture_players to authenticated;
-- `make backup`: the game is admin- and member-written data
grant select on
  public.fantasy_match_days, public.fantasy_fixtures, public.fantasy_fixture_players,
  public.fantasy_prices, public.fantasy_lineups
  to service_role;

-- ════════════════════════════════════════════════════════════════════════
-- member RPCs
-- ════════════════════════════════════════════════════════════════════════
-- The name a member plays under (emails are never shown to other members).
create function public.set_my_display_name(p_name text) returns text
language plpgsql security definer set search_path = public as $$
declare v_name text := btrim(coalesce(p_name, ''));
begin
  if auth.uid() is null then raise exception 'not authenticated'; end if;
  if char_length(v_name) < 2 or char_length(v_name) > 30 then
    raise exception 'a name has 2 to 30 characters';
  end if;
  if exists (select 1 from public.profiles
             where lower(display_name) = lower(v_name) and user_id <> auth.uid()) then
    raise exception 'that name is taken';
  end if;
  update public.profiles set display_name = v_name where user_id = auth.uid();
  return v_name;
end $$;

create function public.save_lineup(p_day bigint, p_players bigint[], p_captain bigint)
returns jsonb
language plpgsql security definer set search_path = public as $$
declare
  d       public.fantasy_match_days;
  v_total numeric;
  v_n     int := coalesce(cardinality(p_players), 0);
begin
  if auth.uid() is null then raise exception 'not authenticated'; end if;
  select * into d from public.fantasy_match_days where id = p_day;
  if not found or d.status <> 'open' then raise exception 'this match day is not open'; end if;
  if public.fantasy_locks_at(p_day) <= now() then raise exception 'this match day is locked'; end if;
  if (select display_name from public.profiles where user_id = auth.uid()) is null then
    raise exception 'choose your manager name first';
  end if;
  if (select count(distinct x) from unnest(p_players) x where x is not null) <> v_n then
    raise exception 'pick each player only once';
  end if;
  if v_n <> d.squad_size then raise exception 'pick exactly % players', d.squad_size; end if;
  if exists (select unnest(p_players)
             except
             select fp.player_id from public.fantasy_fixture_players fp
             join public.fantasy_fixtures fx on fx.id = fp.fixture_id
             where fx.match_day_id = p_day and not fx.cancelled) then
    raise exception 'a picked player does not play this match day';
  end if;
  if p_captain is null or not (p_captain = any (p_players)) then
    raise exception 'the captain must be one of your picks';
  end if;
  select sum(price) into v_total from public.fantasy_prices
  where match_day_id = p_day and player_id = any (p_players);
  if v_total > d.budget then
    raise exception 'over budget: % of %', v_total, d.budget;
  end if;
  insert into public.fantasy_lineups (match_day_id, user_id, player_ids, captain_player_id)
  values (p_day, auth.uid(), p_players, p_captain)
  on conflict (match_day_id, user_id) do update
    set player_ids = excluded.player_ids, captain_player_id = excluded.captain_player_id,
        updated_at = now();
  return jsonb_build_object('player_ids', p_players, 'captain', p_captain, 'cost', v_total);
end $$;

-- Everything one match-day page needs. Lineups of others only after the lock.
create function public.fantasy_match_day(p_day bigint) returns jsonb
language plpgsql stable security definer set search_path = public as $$
declare
  d public.fantasy_match_days;
  s record;
begin
  if auth.uid() is null then raise exception 'not authenticated'; end if;
  select * into d from public.fantasy_match_days where id = p_day;
  if not found or (d.status = 'draft' and not public.is_admin()) then return null; end if;
  select * into s from public.fantasy_day_state(p_day);
  return jsonb_build_object(
    'day', jsonb_build_object(
      'id', d.id, 'season', d.season, 'name', d.name, 'status', d.status,
      'squad_size', d.squad_size, 'budget', d.budget,
      'captain_multiplier', d.captain_multiplier,
      'locks_at', s.locks_at, 'locked', s.locked, 'final', s.final),
    'me', jsonb_build_object(
      'manager', (select display_name from public.profiles where user_id = auth.uid())),
    'fixtures', (
      select coalesce(jsonb_agg(jsonb_build_object(
               'id', fx.id, 'scheduled_at', fx.scheduled_at, 'venue', fx.venue,
               'cancelled', fx.cancelled, 'fantasy_published', fx.fantasy_published,
               'match_key', m.match_key, 'score_a', m.score_a, 'score_b', m.score_b,
               'players', (select coalesce(jsonb_agg(jsonb_build_object(
                                    'player_id', fp.player_id, 'team', fp.team)
                                  order by fp.team, fp.player_id), '[]'::jsonb)
                           from public.fantasy_fixture_players fp where fp.fixture_id = fx.id))
             order by fx.scheduled_at, fx.id), '[]'::jsonb)
      from public.fantasy_fixtures fx
      left join public.matches m on m.id = fx.match_id
        and (m.status = 'published' or public.is_admin())
      where fx.match_day_id = p_day),
    -- the day's players: price (snapshot once open; override or suggestion in
    -- a draft), the last 5 fantasy scores (league tier) and the day's points
    'players', (
      select coalesce(jsonb_agg(jsonb_build_object(
               'player_id', p.id, 'display_name', p.display_name,
               'price', coalesce(pr.price, sp.price, 7.5),
               'is_override', coalesce(pr.is_override, false),
               'per21', sp.per21,
               'form', (select coalesce(jsonb_agg(r.fantasy order by r.rn desc), '[]'::jsonb)
                        from (select f.fantasy,
                                     row_number() over (order by m.match_date desc,
                                       m.start_time desc nulls last, m.id desc) as rn
                              from public.player_match_fantasy f
                              join public.matches m on m.id = f.match_id and m.status = 'published'
                              where f.player_id = p.id) r
                        where r.rn <= 5),
               'points', pp.points)
             order by coalesce(pr.price, sp.price, 7.5) desc, p.display_name), '[]'::jsonb)
      from (select distinct fp.player_id
            from public.fantasy_fixture_players fp
            join public.fantasy_fixtures fx on fx.id = fp.fixture_id
            where fx.match_day_id = p_day) dp
      join public.players p on p.id = dp.player_id
      left join public.fantasy_prices pr on pr.match_day_id = p_day and pr.player_id = p.id
      left join public.fantasy_suggested_prices() sp on sp.player_id = p.id
      left join public.fantasy_player_points(p_day) pp on pp.player_id = p.id),
    'my_lineup', (
      select jsonb_build_object('player_ids', l.player_ids, 'captain', l.captain_player_id,
                                'points', sc.points, 'updated_at', l.updated_at)
      from public.fantasy_lineups l
      left join public.fantasy_lineup_scores(p_day) sc on sc.user_id = l.user_id
      where l.match_day_id = p_day and l.user_id = auth.uid()),
    'lineups', case when s.locked then (
      select coalesce(jsonb_agg(jsonb_build_object(
               'manager', pf.display_name, 'is_me', l.user_id = auth.uid(),
               'player_ids', l.player_ids, 'captain', l.captain_player_id,
               'points', sc.points, 'rank', sc.rnk)
             order by sc.rnk, pf.display_name), '[]'::jsonb)
      from public.fantasy_lineups l
      join public.profiles pf on pf.user_id = l.user_id
      join (select x.user_id, x.points, rank() over (order by x.points desc) as rnk
            from public.fantasy_lineup_scores(p_day) x) sc on sc.user_id = l.user_id
      where l.match_day_id = p_day)
    end,
    'n_lineups', (select count(*) from public.fantasy_lineups where match_day_id = p_day));
end $$;

-- The match days a member can see, newest first, with their own score and
-- the leader once locked.
create function public.fantasy_days(p_season text default null)
returns table (id bigint, season text, name text, status text, locks_at timestamptz,
               locked boolean, final boolean, n_fixtures bigint, has_lineup boolean,
               my_points numeric, leader text, leader_points numeric)
language sql stable security definer set search_path = public as $$
  select d.id, d.season, d.name, d.status, st.locks_at, st.locked, st.final,
         (select count(*) from public.fantasy_fixtures fx
          where fx.match_day_id = d.id and not fx.cancelled),
         exists (select 1 from public.fantasy_lineups l
                 where l.match_day_id = d.id and l.user_id = auth.uid()),
         (select sc.points from public.fantasy_lineup_scores(d.id) sc
          where sc.user_id = auth.uid()),
         case when st.locked then (
           select string_agg(pf.display_name, ', ' order by pf.display_name)
           from public.fantasy_lineup_scores(d.id) sc
           join public.profiles pf on pf.user_id = sc.user_id
           where sc.points = (select max(x.points) from public.fantasy_lineup_scores(d.id) x)) end,
         case when st.locked then (select max(x.points) from public.fantasy_lineup_scores(d.id) x) end
  from public.fantasy_match_days d
  cross join lateral public.fantasy_day_state(d.id) st
  where auth.uid() is not null
    and (d.status = 'open' or public.is_admin())
    and (p_season is null or d.season = p_season)
  order by st.locks_at desc nulls first, d.id desc
$$;

-- The season table: locked days only (before the lock a lineup is private).
-- Ties on a final day are a win for each; tie-break of the table = day wins.
create function public.fantasy_standings(p_season text default null)
returns table (manager text, is_me boolean, total numeric, days_played bigint,
               day_wins bigint, last_points numeric, rank bigint)
language sql stable security definer set search_path = public as $$
  with days as (
    select d.id, st.locks_at, st.final
    from public.fantasy_match_days d
    cross join lateral public.fantasy_day_state(d.id) st
    where auth.uid() is not null and st.locked
      and (p_season is null or d.season = p_season)
  ), scores as (
    select dd.id as day_id, dd.locks_at, dd.final, sc.user_id, sc.points
    from days dd cross join lateral public.fantasy_lineup_scores(dd.id) sc
  ), best as (
    select day_id, max(points) as top from scores where final group by day_id
  ), per as (
    select s.user_id, sum(s.points) as total, count(*) as days_played,
           count(*) filter (where s.final and s.points = b.top) as day_wins,
           (array_agg(s.points order by s.locks_at desc))[1] as last_points
    from scores s left join best b on b.day_id = s.day_id
    group by s.user_id
  )
  select pf.display_name, per.user_id = auth.uid(), per.total, per.days_played,
         per.day_wins, per.last_points,
         rank() over (order by per.total desc, per.day_wins desc)
  from per join public.profiles pf on pf.user_id = per.user_id
  order by 7, pf.display_name
$$;

-- ════════════════════════════════════════════════════════════════════════
-- admin RPCs
-- ════════════════════════════════════════════════════════════════════════
-- A price override, only while the day is a draft (prices never move while
-- people pick). NULL removes the override.
create function public.set_fantasy_price(p_day bigint, p_player bigint, p_price numeric)
returns void
language plpgsql security definer set search_path = public as $$
begin
  if not public.is_admin() then raise exception 'admins only'; end if;
  if (select status from public.fantasy_match_days where id = p_day) is distinct from 'draft' then
    raise exception 'prices are fixed once the match day is open';
  end if;
  if p_price is null then
    delete from public.fantasy_prices where match_day_id = p_day and player_id = p_player;
  else
    insert into public.fantasy_prices (match_day_id, player_id, price, is_override)
    values (p_day, p_player, round(p_price * 2) / 2, true)
    on conflict (match_day_id, player_id) do update
      set price = excluded.price, is_override = true;
  end if;
end $$;

-- Opening a day snapshots the prices (overrides kept) and lets members pick.
create function public.open_fantasy_match_day(p_day bigint) returns void
language plpgsql security definer set search_path = public as $$
declare v_status text;
begin
  if not public.is_admin() then raise exception 'admins only'; end if;
  select status into v_status from public.fantasy_match_days where id = p_day for update;
  if v_status is null then raise exception 'no such match day'; end if;
  if v_status <> 'draft' then raise exception 'the match day is already open'; end if;
  if not exists (select 1 from public.fantasy_fixture_players fp
                 join public.fantasy_fixtures fx on fx.id = fp.fixture_id
                 where fx.match_day_id = p_day and not fx.cancelled) then
    raise exception 'add the fixtures and their players first';
  end if;
  if public.fantasy_locks_at(p_day) <= now() then
    raise exception 'its first match has already started';
  end if;
  insert into public.fantasy_prices (match_day_id, player_id, price)
  select distinct p_day, fp.player_id, coalesce(sp.price, 7.5)
  from public.fantasy_fixture_players fp
  join public.fantasy_fixtures fx on fx.id = fp.fixture_id
  left join public.fantasy_suggested_prices() sp on sp.player_id = fp.player_id
  where fx.match_day_id = p_day
  on conflict do nothing;
  update public.fantasy_match_days set status = 'open', opened_at = now() where id = p_day;
end $$;

-- Link a fixture to its match (the video), or unlink with NULL. Returns who
-- differs between the fixture and the match's assigned slots ("a sub played").
create function public.link_fixture_match(p_fixture bigint, p_match bigint) returns jsonb
language plpgsql security definer set search_path = public as $$
declare fx public.fantasy_fixtures;
begin
  if not public.is_admin() then raise exception 'admins only'; end if;
  select * into fx from public.fantasy_fixtures where id = p_fixture for update;
  if not found then raise exception 'no such fixture'; end if;
  if p_match is null then
    update public.fantasy_fixtures set match_id = null, fantasy_published = false where id = p_fixture;
    return jsonb_build_object('missing', '[]'::jsonb, 'extra', '[]'::jsonb);
  end if;
  if fx.cancelled then raise exception 'the fixture was cancelled'; end if;
  if not exists (select 1 from public.matches where id = p_match) then
    raise exception 'no such match';
  end if;
  if exists (select 1 from public.fantasy_fixtures where match_id = p_match and id <> p_fixture) then
    raise exception 'that match is linked to another fixture';
  end if;
  update public.fantasy_fixtures
     set match_id = p_match,
         fantasy_published = fantasy_published and match_id = p_match
   where id = p_fixture;
  return public.fixture_match_mismatch(p_fixture);
end $$;

-- Fixture players who have no slot in the linked match, and assigned slots
-- who are not in the fixture (admin page; internal to the admin RPCs).
create function public.fixture_match_mismatch(p_fixture bigint) returns jsonb
language sql stable security definer set search_path = public as $$
  select jsonb_build_object(
    'missing', coalesce((select jsonb_agg(p.display_name order by p.display_name)
                         from public.fantasy_fixture_players fp
                         join public.players p on p.id = fp.player_id
                         where fp.fixture_id = fx.id
                           and not exists (select 1 from public.match_participants mp
                                           where mp.match_id = fx.match_id
                                             and mp.player_id = fp.player_id)), '[]'::jsonb),
    'extra', coalesce((select jsonb_agg(p.display_name order by p.display_name)
                       from public.match_participants mp
                       join public.players p on p.id = mp.player_id
                       where mp.match_id = fx.match_id
                         and not exists (select 1 from public.fantasy_fixture_players fp
                                         where fp.fixture_id = fx.id
                                           and fp.player_id = mp.player_id)), '[]'::jsonb))
  from public.fantasy_fixtures fx
  where fx.id = p_fixture and public.is_admin()
$$;

-- Publishing a fixture to fantasy makes its points count; it needs its match
-- linked and published.
create function public.publish_fixture_to_fantasy(p_fixture bigint, p_on boolean) returns void
language plpgsql security definer set search_path = public as $$
declare fx public.fantasy_fixtures;
begin
  if not public.is_admin() then raise exception 'admins only'; end if;
  select * into fx from public.fantasy_fixtures where id = p_fixture for update;
  if not found then raise exception 'no such fixture'; end if;
  if p_on then
    if fx.cancelled then raise exception 'the fixture was cancelled'; end if;
    if fx.match_id is null then raise exception 'link the fixture to its match first'; end if;
    if (select status from public.matches where id = fx.match_id) <> 'published' then
      raise exception 'publish the match first';
    end if;
  end if;
  update public.fantasy_fixtures set fantasy_published = p_on where id = p_fixture;
end $$;

-- ════════════════════════════════════════════════════════════════════════
-- function privileges: members get the read API, save_lineup and the name;
-- the admin RPCs check is_admin() inside; the helpers stay internal
-- ════════════════════════════════════════════════════════════════════════
revoke execute on function
  public.fantasy_locks_at(bigint), public.fantasy_suggested_prices(),
  public.fantasy_player_points(bigint), public.fantasy_lineup_scores(bigint),
  public.fantasy_day_state(bigint), public.fantasy_day_guard(),
  public.fantasy_fixture_guard(), public.fantasy_fixture_player_guard(),
  public.set_my_display_name(text), public.save_lineup(bigint, bigint[], bigint),
  public.fantasy_match_day(bigint), public.fantasy_days(text), public.fantasy_standings(text),
  public.set_fantasy_price(bigint, bigint, numeric), public.open_fantasy_match_day(bigint),
  public.link_fixture_match(bigint, bigint), public.fixture_match_mismatch(bigint),
  public.publish_fixture_to_fantasy(bigint, boolean)
  from public, anon, authenticated;
grant execute on function
  public.set_my_display_name(text), public.save_lineup(bigint, bigint[], bigint),
  public.fantasy_match_day(bigint), public.fantasy_days(text), public.fantasy_standings(text),
  public.set_fantasy_price(bigint, bigint, numeric), public.open_fantasy_match_day(bigint),
  public.link_fixture_match(bigint, bigint), public.fixture_match_mismatch(bigint),
  public.publish_fixture_to_fantasy(bigint, boolean)
  to authenticated;
