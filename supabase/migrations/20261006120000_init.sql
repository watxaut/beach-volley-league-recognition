-- Beach volley league: schema, access rules (RLS), stats views and the
-- publish RPC. Design + rationale: docs/web_platform_design.md.
--
-- Ownership rule (the one that makes re-publishing safe):
--   PIPELINE-OWNED rows/columns are written ONLY by ingest_match_bundle()
--   (points, actions, match_sources, slot rows, the score columns of matches).
--   ADMIN-OWNED data (players, profiles, slot -> player assignments, match
--   title/venue/season/status/detail_public, fantasy rules) is NEVER written
--   by a publish, so it survives every re-run of the pipeline.

-- ════════════════════════════════════════════════════════════════════════
-- types
-- ════════════════════════════════════════════════════════════════════════
create type public.app_role     as enum ('admin', 'viewer');
create type public.match_status as enum ('draft', 'published', 'hidden');

-- ════════════════════════════════════════════════════════════════════════
-- dimensions
-- ════════════════════════════════════════════════════════════════════════
create table public.profiles (
  user_id      uuid primary key references auth.users on delete cascade,
  email        text,
  role         public.app_role not null default 'viewer',
  display_name text,
  created_at   timestamptz not null default now()
);

create table public.players (
  id             bigint generated always as identity primary key,
  display_name   text not null,
  user_id        uuid unique references auth.users on delete set null,
  handedness     text check (handedness in ('left', 'right')),
  preferred_side text check (preferred_side in ('left', 'right')),
  photo_path     text,
  profile_public boolean not null default false,
  active         boolean not null default true,
  created_at     timestamptz not null default now()
);

-- ════════════════════════════════════════════════════════════════════════
-- facts
-- ════════════════════════════════════════════════════════════════════════
create table public.matches (
  id                     bigint generated always as identity primary key,
  -- the video's source stem: YYYYMMDD_HHMM_<venue>_<free text>
  match_key              text not null unique
                         check (match_key ~ '^[0-9]{8}_[0-9]{4}_[a-z0-9]+(_[a-z0-9]+)*$'),
  -- admin-owned
  title                  text,
  venue                  text,
  season                 text,
  status                 public.match_status not null default 'draft',
  detail_public          boolean not null default false,
  -- pipeline-owned
  match_date             date not null,
  start_time             time,
  points_to_win          smallint,
  score_a                smallint,
  score_b                smallint,
  winner_team            char(1) check (winner_team in ('A', 'B')),
  n_points               smallint,
  set_complete           boolean,
  duration_s             real,
  checks                 jsonb,
  current_publication_id bigint,
  created_at             timestamptz not null default now(),
  updated_at             timestamptz not null default now()
);
create index matches_date_idx on public.matches (match_date desc, start_time desc);

-- Admin-only facts about the source (RLS is row-level, so admin-only columns
-- live in their own table).
create table public.match_sources (
  match_id       bigint primary key references public.matches on delete cascade,
  video_filename text,
  video_url      text,
  video_sha256   text,
  fps            real,
  width          int,
  height         int
);

-- Bridge: the video only knows the slots P1A/P2A (squad A) and P1B/P2B
-- (squad B); an admin maps each slot to a real player. Touches store the
-- SLOT, never the person, so re-processing never loses an assignment.
create table public.match_participants (
  match_id    bigint not null references public.matches on delete cascade,
  slot        text   not null check (slot in ('P1A', 'P2A', 'P1B', 'P2B')),
  team        char(1) generated always as (right(slot, 1)) stored,
  player_id   bigint references public.players,
  thumb_path  text,
  assigned_by uuid references auth.users on delete set null,
  assigned_at timestamptz,
  primary key (match_id, slot),
  unique (match_id, player_id)          -- NULLs are distinct: unassigned is fine
);
create index match_participants_player_idx on public.match_participants (player_id);

-- One row per rally.
create table public.points (
  match_id      bigint   not null references public.matches on delete cascade,
  point_no      smallint not null,
  set_no        smallint not null default 1,
  start_frame   int      not null,
  end_frame     int      not null,
  serving_team  char(1),
  server_slot   text,
  near_team     char(1),
  winner_team   char(1),
  winner_source text,
  end_kind      text,                  -- ground | net | lost
  end_x_m       real,
  end_y_m       real,
  end_in_court  boolean,
  score_a_after smallint,
  score_b_after smallint,
  flags         text[] not null default '{}',
  primary key (match_id, point_no)
);

-- One row per touch: the lowest grain. Unseen / uncredited touches are kept
-- (complete play-by-play) with slot NULL; every stat counts only rows with a
-- slot (precision first). The publisher sets slot exactly when
-- postrun.player_stats credits the touch (a structurally named server counts
-- even when the serve itself was not seen; an unseen rally touch never does).
create table public.actions (
  match_id        bigint   not null,
  point_no        smallint not null,
  seq             smallint not null,   -- 0 = serve, then the touch order
  frame           int      not null,
  slot            text,                -- NULL = not credited to anyone
  team            char(1),
  side            text,                -- near | far (camera frame)
  action          text not null check (action in
                    ('serve', 'dig', 'set', 'spike', 'overpass', 'block', 'ball_handling')),
  touch_number    smallint,
  outcome         text check (outcome in ('ace', 'kill', 'error')),
  is_assist       boolean not null default false,
  observed        boolean not null,
  evidence        text,                -- vertex | gap | structure
  player_source   text,                -- reach | alternation | service_order | ...
  ends_possession boolean,
  height_m        real,
  own_x_m         real,                -- toucher's own-half frame: 0 = own baseline,
  own_y_m         real,                --   8 = net, 16 = opponents' baseline
  attack_zone     smallint check (attack_zone between 1 and 9),
  spike_type      text,
  landing_x_m     real,                -- attacker's frame (same axes as own_*)
  landing_y_m     real,
  landing_in      boolean,
  landing_source  text,                -- next_touch | ball_death
  dug_zone        smallint check (dug_zone between 1 and 9),
  extra           jsonb,
  primary key (match_id, point_no, seq),
  foreign key (match_id, point_no)
    references public.points (match_id, point_no) on delete cascade
);
create index actions_slot_idx on public.actions (match_id, slot);

-- The log: one row per publish call, kept forever (no cascade: a match with
-- history cannot be hard-deleted -- hide it instead).
create table public.match_publications (
  id               bigint generated always as identity primary key,
  match_id         bigint not null references public.matches,
  revision         int    not null,
  result           text   not null check (result in ('applied', 'unchanged')),
  content_sha256   text   not null,
  bundle_version   smallint not null,
  pipeline_version text,
  git_dirty        boolean,
  bundle_path      text,
  video_url        text,
  n_points         smallint,
  n_actions        smallint,
  score            text,
  published_by     text,
  published_at     timestamptz not null default now(),
  notes            text,
  unique (match_id, revision)
);
alter table public.matches
  add constraint matches_current_publication_fk
  foreign key (current_publication_id) references public.match_publications;

-- ════════════════════════════════════════════════════════════════════════
-- fantasy scoring: its own tables, so the points change without touching
-- any fact table. A rule awards `points` to every CREDITED touch whose
-- action is in `actions` and whose outcome equals `outcome` (NULL = any
-- outcome); `assist_only` restricts it to sets flagged as assists. Exactly
-- one rule set is active; switching sets (or editing points) rescores all
-- history, because every stat is a view.
-- ════════════════════════════════════════════════════════════════════════
create table public.fantasy_rulesets (
  id          bigint generated always as identity primary key,
  name        text not null unique,
  description text,
  is_active   boolean not null default false,
  created_at  timestamptz not null default now()
);
create unique index fantasy_rulesets_one_active
  on public.fantasy_rulesets (is_active) where is_active;

create table public.fantasy_rules (
  ruleset_id  bigint not null references public.fantasy_rulesets on delete cascade,
  rule_key    text   not null check (rule_key ~ '^[a-z][a-z0-9_]*$'),
  label       text   not null,
  actions     text[] not null check (cardinality(actions) > 0),
  outcome     text check (outcome in ('ace', 'kill', 'error')),
  assist_only boolean not null default false,
  points      numeric(4,1) not null,
  sort_order  smallint not null default 0,
  primary key (ruleset_id, rule_key)
);

-- G1 (owner-ratified 2026-09-27): kill +1, ace +1, dig +1, assist +0.5,
-- block +1, errors -1 (service fault / attack error / ball handling).
with rs as (
  insert into public.fantasy_rulesets (name, description, is_active)
  values ('G1', 'Owner-ratified 2026-09-27 (STATUS north-star G1)', true)
  returning id
)
insert into public.fantasy_rules
  (ruleset_id, rule_key, label, actions, outcome, assist_only, points, sort_order)
select rs.id, r.*
from rs, (values
  ('kill',           'Kill',           array['spike', 'overpass'],             'kill',  false,  1.0, 10),
  ('ace',            'Ace',            array['serve'],                         'ace',   false,  1.0, 20),
  ('dig',            'Dig',            array['dig'],                           null,    false,  1.0, 30),
  ('assist',         'Assist',         array['set'],                           null,    true,   0.5, 40),
  ('block',          'Block',          array['block'],                         null,    false,  1.0, 50),
  ('serve_error',    'Service error',  array['serve'],                         'error', false, -1.0, 60),
  ('attack_error',   'Attack error',   array['spike', 'overpass'],             'error', false, -1.0, 70),
  ('handling_error', 'Ball handling',  array['set', 'dig', 'ball_handling'],   'error', false, -1.0, 80)
) as r(rule_key, label, actions, outcome, assist_only, points, sort_order);

-- ════════════════════════════════════════════════════════════════════════
-- helpers (security definer: they read past RLS to answer one yes/no)
-- ════════════════════════════════════════════════════════════════════════
create function public.is_admin() returns boolean
language sql stable security definer set search_path = public as $$
  select exists (select 1 from public.profiles
                 where user_id = auth.uid() and role = 'admin');
$$;

-- Match detail (play-by-play, every touch): admins, the players of that
-- match, or everyone when an admin set detail_public.
create function public.can_see_match_detail(p_match bigint) returns boolean
language sql stable security definer set search_path = public as $$
  select public.is_admin() or exists (
    select 1 from public.matches m
    where m.id = p_match and m.status = 'published'
      and (m.detail_public or exists (
            select 1 from public.match_participants mp
            join public.players p on p.id = mp.player_id
            where mp.match_id = m.id and p.user_id = auth.uid())));
$$;

-- Player analytics (zones, rates, landings): the player, admins, or everyone
-- when the player turned profile_public on.
create function public.can_see_player_analytics(p_player bigint) returns boolean
language sql stable security definer set search_path = public as $$
  select public.is_admin() or exists (
    select 1 from public.players p
    where p.id = p_player and (p.profile_public or p.user_id = auth.uid()));
$$;

create function public.handle_new_user() returns trigger
language plpgsql security definer set search_path = public as $$
begin
  insert into public.profiles (user_id, email) values (new.id, new.email)
  on conflict (user_id) do nothing;
  return new;
end $$;
create trigger on_auth_user_created after insert on auth.users
  for each row execute function public.handle_new_user();

create function public.stamp_assignment() returns trigger
language plpgsql security definer set search_path = public as $$
begin
  if new.player_id is distinct from old.player_id then
    new.assigned_by := auth.uid();
    new.assigned_at := now();
  end if;
  return new;
end $$;
create trigger match_participants_stamp before update on public.match_participants
  for each row execute function public.stamp_assignment();

-- ════════════════════════════════════════════════════════════════════════
-- row-level security: every table, nothing for anon
-- ════════════════════════════════════════════════════════════════════════
alter table public.profiles           enable row level security;
alter table public.players            enable row level security;
alter table public.matches            enable row level security;
alter table public.match_sources      enable row level security;
alter table public.match_participants enable row level security;
alter table public.points             enable row level security;
alter table public.actions            enable row level security;
alter table public.match_publications enable row level security;
alter table public.fantasy_rulesets   enable row level security;
alter table public.fantasy_rules      enable row level security;

create policy own_or_admin_read on public.profiles for select to authenticated
  using (user_id = auth.uid() or public.is_admin());
create policy admin_write on public.profiles for update to authenticated
  using (public.is_admin()) with check (public.is_admin());

create policy members_read on public.players for select to authenticated using (true);
create policy admin_insert on public.players for insert to authenticated
  with check (public.is_admin());
create policy admin_update on public.players for update to authenticated
  using (public.is_admin()) with check (public.is_admin());
create policy admin_delete on public.players for delete to authenticated
  using (public.is_admin());

create policy published_or_admin_read on public.matches for select to authenticated
  using (status = 'published' or public.is_admin());
create policy admin_update on public.matches for update to authenticated
  using (public.is_admin()) with check (public.is_admin());

create policy admin_read on public.match_sources for select to authenticated
  using (public.is_admin());
create policy admin_read on public.match_publications for select to authenticated
  using (public.is_admin());

create policy visible_match_read on public.match_participants for select to authenticated
  using (public.is_admin() or exists (
    select 1 from public.matches m where m.id = match_id and m.status = 'published'));
create policy admin_update on public.match_participants for update to authenticated
  using (public.is_admin()) with check (public.is_admin());

create policy match_detail_read on public.points for select to authenticated
  using (public.can_see_match_detail(match_id));
create policy match_detail_read on public.actions for select to authenticated
  using (public.can_see_match_detail(match_id));

create policy members_read on public.fantasy_rulesets for select to authenticated using (true);
create policy admin_write on public.fantasy_rulesets for all to authenticated
  using (public.is_admin()) with check (public.is_admin());
create policy members_read on public.fantasy_rules for select to authenticated using (true);
create policy admin_write on public.fantasy_rules for all to authenticated
  using (public.is_admin()) with check (public.is_admin());

-- ════════════════════════════════════════════════════════════════════════
-- stats: views over the touches (security_invoker -> the caller's RLS
-- applies; the definer functions below read them as the owner)
-- ════════════════════════════════════════════════════════════════════════
create view public.player_match_stats with (security_invoker = true) as
select mp.match_id, mp.slot, mp.team, mp.player_id,
  count(a.seq) filter (where a.action = 'serve')                                        as serves,
  count(a.seq) filter (where a.action = 'serve' and a.outcome = 'ace')                  as aces,
  count(a.seq) filter (where a.action = 'serve' and a.outcome = 'error')                as serve_errors,
  count(a.seq) filter (where a.action = 'dig')                                          as digs,
  count(a.seq) filter (where a.action = 'set')                                          as sets,
  count(a.seq) filter (where a.is_assist)                                               as assists,
  count(a.seq) filter (where a.action in ('spike', 'overpass'))                         as attacks,
  count(a.seq) filter (where a.action in ('spike', 'overpass') and a.outcome = 'kill')  as kills,
  count(a.seq) filter (where a.action in ('spike', 'overpass') and a.outcome = 'error') as attack_errors,
  count(a.seq) filter (where a.action in ('set', 'dig', 'ball_handling')
                         and a.outcome = 'error')                                       as handling_errors,
  count(a.seq) filter (where a.action = 'block')                                        as blocks
from public.match_participants mp
left join public.actions a
  on a.match_id = mp.match_id and a.slot = mp.slot
group by mp.match_id, mp.slot, mp.team, mp.player_id;

-- Every (credited touch, matching active rule) pair: the fantasy ledger.
create view public.action_fantasy with (security_invoker = true) as
select a.match_id, a.point_no, a.seq, a.slot, r.rule_key, r.label, r.points
from public.actions a
join public.fantasy_rules r
  on a.action = any (r.actions)
 and (r.outcome is null or a.outcome = r.outcome)
 and (not r.assist_only or a.is_assist)
join public.fantasy_rulesets rs on rs.id = r.ruleset_id and rs.is_active
where a.slot is not null;

create view public.player_match_fantasy with (security_invoker = true) as
select s.*,
       coalesce(f.fantasy, 0)            as fantasy,
       coalesce(f.breakdown, '[]'::jsonb) as breakdown
from public.player_match_stats s
left join (
  select match_id, slot, sum(pts) as fantasy,
         jsonb_agg(jsonb_build_object('rule', rule_key, 'label', label,
                                      'count', n, 'points', pts) order by rule_key) as breakdown
  from (select match_id, slot, rule_key, label, count(*) as n, sum(points) as pts
        from public.action_fantasy group by match_id, slot, rule_key, label) per_rule
  group by match_id, slot
) f on f.match_id = s.match_id and f.slot = s.slot;

-- ════════════════════════════════════════════════════════════════════════
-- read API for the web app (league tier = aggregates, no raw touches)
-- ════════════════════════════════════════════════════════════════════════
create function public.leaderboard(p_season text default null)
returns table (player_id bigint, display_name text, matches bigint, wins bigint,
               fantasy numeric, kills bigint, aces bigint, digs bigint,
               assists bigint, blocks bigint, errors bigint)
language sql stable security definer set search_path = public as $$
  select p.id, p.display_name,
         count(distinct f.match_id),
         count(distinct f.match_id) filter (where f.team = m.winner_team),
         sum(f.fantasy),
         sum(f.kills)::bigint, sum(f.aces)::bigint, sum(f.digs)::bigint,
         sum(f.assists)::bigint, sum(f.blocks)::bigint,
         sum(f.serve_errors + f.attack_errors + f.handling_errors)::bigint
  from public.player_match_fantasy f
  join public.matches m on m.id = f.match_id and m.status = 'published'
  join public.players p on p.id = f.player_id
  where auth.uid() is not null
    and (p_season is null or m.season = p_season)
  group by p.id, p.display_name
  order by sum(f.fantasy) desc, p.display_name;
$$;

-- Box score of one match: one row per slot (league tier).
create function public.match_box_score(p_match_id bigint)
returns table (slot text, team char(1), player_id bigint, display_name text,
               serves bigint, aces bigint, serve_errors bigint, digs bigint,
               sets bigint, assists bigint, attacks bigint, kills bigint,
               attack_errors bigint, handling_errors bigint, blocks bigint,
               fantasy numeric, breakdown jsonb)
language sql stable security definer set search_path = public as $$
  select f.slot, f.team, f.player_id, p.display_name,
         f.serves, f.aces, f.serve_errors, f.digs, f.sets, f.assists, f.attacks,
         f.kills, f.attack_errors, f.handling_errors, f.blocks, f.fantasy, f.breakdown
  from public.player_match_fantasy f
  join public.matches m on m.id = f.match_id
  left join public.players p on p.id = f.player_id
  where f.match_id = p_match_id
    and auth.uid() is not null
    and (m.status = 'published' or public.is_admin())
  order by f.team, f.slot;
$$;

-- One player's page: totals + match history (league tier) and analytics
-- (only when can_see_player_analytics).
create function public.player_profile(p_player_id bigint)
returns jsonb
language plpgsql stable security definer set search_path = public as $$
declare
  v_player    jsonb;
  v_history   jsonb;
  v_totals    jsonb;
  v_analytics jsonb := null;
  v_allowed   boolean;
begin
  if auth.uid() is null then
    raise exception 'not authenticated';
  end if;
  select jsonb_build_object('id', p.id, 'display_name', p.display_name,
                            'profile_public', p.profile_public,
                            'is_me', p.user_id = auth.uid(),
                            'handedness', p.handedness, 'preferred_side', p.preferred_side)
    into v_player from public.players p where p.id = p_player_id;
  if v_player is null then
    return null;
  end if;

  with h as (
    select m.id as match_id, m.match_key, m.match_date, m.start_time, m.title, m.venue,
           m.season, m.score_a, m.score_b, f.team, f.slot,
           (f.team = m.winner_team) as won, f.fantasy, f.kills, f.aces, f.digs,
           f.assists, f.blocks, f.serves, f.attacks,
           f.serve_errors + f.attack_errors + f.handling_errors as errors
    from public.player_match_fantasy f
    join public.matches m on m.id = f.match_id
    where f.player_id = p_player_id
      and (m.status = 'published' or public.is_admin())
  )
  select coalesce(jsonb_agg(to_jsonb(h) order by h.match_date desc, h.start_time desc), '[]'::jsonb),
         jsonb_build_object(
           'matches', count(*), 'wins', count(*) filter (where won),
           'fantasy', coalesce(sum(fantasy), 0), 'kills', coalesce(sum(kills), 0),
           'aces', coalesce(sum(aces), 0), 'digs', coalesce(sum(digs), 0),
           'assists', coalesce(sum(assists), 0), 'blocks', coalesce(sum(blocks), 0),
           'errors', coalesce(sum(errors), 0), 'serves', coalesce(sum(serves), 0),
           'attacks', coalesce(sum(attacks), 0))
    into v_history, v_totals
  from h;

  v_allowed := public.can_see_player_analytics(p_player_id);
  if v_allowed then
    with mine as (
      select a.*
      from public.actions a
      join public.match_participants mp on mp.match_id = a.match_id and mp.slot = a.slot
      join public.matches m on m.id = a.match_id
      where mp.player_id = p_player_id
        and (m.status = 'published' or public.is_admin())
    )
    select jsonb_build_object(
      'kill_rate',  round(count(*) filter (where action in ('spike', 'overpass') and outcome = 'kill')::numeric
                          / nullif(count(*) filter (where action in ('spike', 'overpass')), 0), 3),
      'attack_error_rate', round(count(*) filter (where action in ('spike', 'overpass') and outcome = 'error')::numeric
                          / nullif(count(*) filter (where action in ('spike', 'overpass')), 0), 3),
      'ace_rate',   round(count(*) filter (where action = 'serve' and outcome = 'ace')::numeric
                          / nullif(count(*) filter (where action = 'serve'), 0), 3),
      'serve_error_rate', round(count(*) filter (where action = 'serve' and outcome = 'error')::numeric
                          / nullif(count(*) filter (where action = 'serve'), 0), 3),
      'attack_zones', coalesce((select jsonb_object_agg(z, n) from (
                         select attack_zone as z, count(*) as n from mine
                         where action in ('spike', 'overpass') and attack_zone is not null
                         group by attack_zone) zz), '{}'::jsonb),
      'landings', coalesce((select jsonb_agg(jsonb_build_object(
                         'x', landing_x_m, 'y', landing_y_m, 'in', landing_in,
                         'outcome', outcome, 'source', landing_source))
                       from mine where action in ('spike', 'overpass')
                         and landing_y_m is not null), '[]'::jsonb),
      'touch_depths', coalesce((select jsonb_agg(jsonb_build_object(
                         'action', action, 'y', own_y_m))
                       from mine where own_y_m is not null), '[]'::jsonb))
      into v_analytics
    from mine;
  end if;

  return jsonb_build_object('player', v_player, 'totals', v_totals, 'history', v_history,
                            'can_see_analytics', v_allowed, 'analytics', v_analytics);
end $$;

-- A player flips their own analytics visibility (an RPC, so they can't edit
-- any other column of players).
create function public.set_my_privacy(p_public boolean) returns boolean
language plpgsql security definer set search_path = public as $$
begin
  update public.players set profile_public = p_public where user_id = auth.uid();
  return found;
end $$;

-- Scoring changes (admin): copy a rule set to try new values without losing
-- the old one, and switch the active set atomically (the partial unique
-- index refuses two active sets, so the swap must be one statement pair in
-- one transaction).
create function public.clone_ruleset(p_from bigint, p_name text) returns bigint
language plpgsql security definer set search_path = public as $$
declare v_id bigint;
begin
  if not public.is_admin() then
    raise exception 'admins only';
  end if;
  insert into public.fantasy_rulesets (name, description, is_active)
  select p_name, 'copy of ' || name, false from public.fantasy_rulesets where id = p_from
  returning id into v_id;
  if v_id is null then
    raise exception 'no rule set %', p_from;
  end if;
  insert into public.fantasy_rules
    (ruleset_id, rule_key, label, actions, outcome, assist_only, points, sort_order)
  select v_id, rule_key, label, actions, outcome, assist_only, points, sort_order
  from public.fantasy_rules where ruleset_id = p_from;
  return v_id;
end $$;

create function public.activate_ruleset(p_ruleset_id bigint) returns void
language plpgsql security definer set search_path = public as $$
begin
  if not public.is_admin() then
    raise exception 'admins only';
  end if;
  if not exists (select 1 from public.fantasy_rulesets where id = p_ruleset_id) then
    raise exception 'no rule set %', p_ruleset_id;
  end if;
  update public.fantasy_rulesets set is_active = false where is_active and id <> p_ruleset_id;
  update public.fantasy_rulesets set is_active = true where id = p_ruleset_id;
end $$;

-- Keep-alive target for the scheduled GitHub workflow (free projects pause
-- after 7 idle days). Touches the database, exposes nothing.
create function public.ping() returns text
language sql stable set search_path = public as $$
  select 'ok:' || (select count(*) from public.fantasy_rulesets)::text;
$$;

-- ════════════════════════════════════════════════════════════════════════
-- publish API (service role only)
-- ════════════════════════════════════════════════════════════════════════

-- What is live for a match key (the publisher's --dry-run diff).
create function public.publish_preview(p_match_key text)
returns jsonb
language sql stable security definer set search_path = public as $$
  select coalesce((
    select jsonb_build_object(
      'exists', true, 'match_id', m.id, 'status', m.status,
      'score_a', m.score_a, 'score_b', m.score_b, 'n_points', m.n_points,
      'revision', p.revision, 'content_sha256', p.content_sha256,
      'n_actions', p.n_actions, 'video_sha256', s.video_sha256,
      'slots', (select coalesce(jsonb_agg(jsonb_build_object(
                  'slot', f.slot, 'player_id', f.player_id, 'fantasy', f.fantasy)
                  order by f.slot), '[]'::jsonb)
                from public.player_match_fantasy f where f.match_id = m.id))
    from public.matches m
    left join public.match_publications p on p.id = m.current_publication_id
    left join public.match_sources s on s.match_id = m.id
    where m.match_key = p_match_key),
    jsonb_build_object('exists', false));
$$;

-- Apply one match bundle in ONE transaction (docs/web_platform_design.md §3).
-- Same content hash as the live revision -> logged as 'unchanged', nothing
-- else is written. Otherwise the pipeline-owned rows are replaced; slot
-- rows are created if missing but their player_id is never touched.
create function public.ingest_match_bundle(p_bundle jsonb, p_bundle_path text, p_published_by text)
returns jsonb
language plpgsql security definer set search_path = public as $$
declare
  m      jsonb := p_bundle -> 'match';
  v_key  text  := m ->> 'match_key';
  v_hash text  := p_bundle ->> 'content_sha256';
  v_id   bigint;
  v_prev text;
  v_rev  int;
  v_pub  bigint;
begin
  if (p_bundle ->> 'bundle_version')::int is distinct from 1 then
    raise exception 'unsupported bundle_version %', p_bundle ->> 'bundle_version';
  end if;
  if v_hash is null or v_key is null then
    raise exception 'bundle lacks match.match_key or content_sha256';
  end if;
  perform pg_advisory_xact_lock(hashtext('ingest:' || v_key));

  insert into public.matches (match_key, match_date)
  values (v_key, (m ->> 'match_date')::date)
  on conflict (match_key) do nothing;
  select id into v_id from public.matches where match_key = v_key;

  -- the name is the id: refuse a different video under the same name
  if exists (select 1 from public.match_sources s
             where s.match_id = v_id and s.video_sha256 is not null
               and s.video_sha256 is distinct from m #>> '{video,sha256}')
     and not coalesce((p_bundle ->> 'replace_video')::boolean, false) then
    raise exception 'match % already holds a different video (re-publish with --replace-video)', v_key;
  end if;

  select p.content_sha256 into v_prev
  from public.matches mm
  join public.match_publications p on p.id = mm.current_publication_id
  where mm.id = v_id;
  select coalesce(max(revision), 0) + 1 into v_rev
  from public.match_publications where match_id = v_id;

  if v_prev is not distinct from v_hash then
    insert into public.match_publications
      (match_id, revision, result, content_sha256, bundle_version, pipeline_version,
       git_dirty, bundle_path, video_url, published_by, notes)
    values (v_id, v_rev, 'unchanged', v_hash, 1, p_bundle #>> '{provenance,pipeline_version}',
            (p_bundle #>> '{provenance,git_dirty}')::boolean, p_bundle_path,
            m #>> '{video,url}', p_published_by, p_bundle ->> 'note');
    return jsonb_build_object('match_id', v_id, 'revision', v_rev, 'result', 'unchanged');
  end if;

  -- Replace pipeline-owned rows (actions cascade from points).
  -- jsonb_populate_recordset fills a MISSING key from the base record, never
  -- from the column DEFAULT -- so the base carries match_id and the defaults.
  delete from public.points where match_id = v_id;
  insert into public.points
  select * from jsonb_populate_recordset(
    jsonb_populate_record(null::public.points,
      jsonb_build_object('match_id', v_id, 'set_no', 1, 'flags', '[]'::jsonb)),
    p_bundle -> 'points');
  insert into public.actions
  select * from jsonb_populate_recordset(
    jsonb_populate_record(null::public.actions,
      jsonb_build_object('match_id', v_id, 'is_assist', false)),
    p_bundle -> 'actions');

  insert into public.match_participants (match_id, slot, thumb_path)
  select v_id, s ->> 'slot', s ->> 'thumb_path'
  from jsonb_array_elements(coalesce(p_bundle -> 'slots', '[]'::jsonb)) s
  on conflict (match_id, slot) do update set thumb_path = excluded.thumb_path;

  insert into public.match_sources
    (match_id, video_filename, video_url, video_sha256, fps, width, height)
  values (v_id, m #>> '{video,filename}', m #>> '{video,url}', m #>> '{video,sha256}',
          (m #>> '{video,fps}')::real, (m #>> '{video,width}')::int,
          (m #>> '{video,height}')::int)
  on conflict (match_id) do update set
    video_filename = excluded.video_filename, video_url = excluded.video_url,
    video_sha256 = excluded.video_sha256, fps = excluded.fps,
    width = excluded.width, height = excluded.height;

  update public.matches set
    match_date    = (m ->> 'match_date')::date,
    start_time    = (m ->> 'start_time')::time,
    points_to_win = (m ->> 'points_to_win')::smallint,
    score_a       = (m ->> 'score_a')::smallint,
    score_b       = (m ->> 'score_b')::smallint,
    winner_team   = m ->> 'winner_team',
    n_points      = (m ->> 'n_points')::smallint,
    set_complete  = (m ->> 'set_complete')::boolean,
    duration_s    = (m ->> 'duration_s')::real,
    checks        = m -> 'checks',
    updated_at    = now()
  where id = v_id;

  insert into public.match_publications
    (match_id, revision, result, content_sha256, bundle_version, pipeline_version, git_dirty,
     bundle_path, video_url, n_points, n_actions, score, published_by, notes)
  values (v_id, v_rev, 'applied', v_hash, 1, p_bundle #>> '{provenance,pipeline_version}',
          (p_bundle #>> '{provenance,git_dirty}')::boolean, p_bundle_path, m #>> '{video,url}',
          jsonb_array_length(coalesce(p_bundle -> 'points', '[]'::jsonb)),
          jsonb_array_length(coalesce(p_bundle -> 'actions', '[]'::jsonb)),
          (m ->> 'score_a') || '-' || (m ->> 'score_b'), p_published_by, p_bundle ->> 'note')
  returning id into v_pub;
  update public.matches set current_publication_id = v_pub where id = v_id;

  return jsonb_build_object(
    'match_id', v_id, 'revision', v_rev, 'result', 'applied',
    'n_points', jsonb_array_length(coalesce(p_bundle -> 'points', '[]'::jsonb)),
    'n_actions', jsonb_array_length(coalesce(p_bundle -> 'actions', '[]'::jsonb)));
end $$;

-- ════════════════════════════════════════════════════════════════════════
-- function privileges: nothing for anon except ping(); the publish API for
-- the service role only.
-- ════════════════════════════════════════════════════════════════════════
revoke execute on all functions in schema public from public, anon;
grant execute on function public.ping() to anon, authenticated;
grant execute on function
  public.is_admin(), public.can_see_match_detail(bigint), public.can_see_player_analytics(bigint),
  public.leaderboard(text), public.match_box_score(bigint), public.player_profile(bigint),
  public.set_my_privacy(boolean), public.clone_ruleset(bigint, text),
  public.activate_ruleset(bigint)
  to authenticated;
revoke execute on function public.ingest_match_bundle(jsonb, text, text) from authenticated;
revoke execute on function public.publish_preview(text) from authenticated;
grant execute on function public.ingest_match_bundle(jsonb, text, text) to service_role;
grant execute on function public.publish_preview(text) to service_role;
