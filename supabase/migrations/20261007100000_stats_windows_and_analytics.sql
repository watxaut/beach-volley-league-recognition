-- Stats the brainstorm (docs/stats_feature_brainstorm.md, "Now") asked for,
-- all derived from facts already in the database -- no new perception, so no
-- re-publish is needed for any of it.
--
--   O4 / I1  time windows: every read takes (season, from, to, last N matches).
--            Last N counts the newest N published matches of the READER's
--            scope: the league's N for the leaderboard, the player's own N
--            for a profile (`player_profile`).
--   N1       side-out % and break-point % (points table only).
--   N2       serve targeting (who received each serve).
--   N3       reception outcome, a pass-quality proxy: what the receiving
--            possession became. No pass grading.
--   N4       attack efficiency, split into reception and transition attacks.
--   N8 / F3  match report: per-player line vs their own average, per-team
--            side-out / break, serve targets, per-point fantasy timeline,
--            fantasy per 21 points, form (last 5).
--
-- Visibility is unchanged: league tier (totals, box score, side-out of a
-- match) for every member; player analytics for the player / admins / opted-in
-- players; the per-point timeline only where the play-by-play is visible.

-- ════════════════════════════════════════════════════════════════════════
-- touch_context: every touch with the possession it belongs to.
-- possession 0 = the serve, 1 = the receiving team's first possession (the
-- reception), 2 = the answer, ... A possession starts at each touch_number 1
-- (hidden touches keep their numbers, so the count is complete).
-- ════════════════════════════════════════════════════════════════════════
create view public.touch_context with (security_invoker = true) as
select a.match_id, a.point_no, a.seq, a.frame, a.slot, a.team, a.action, a.outcome,
       a.is_assist, a.touch_number, a.observed, a.height_m, a.attack_zone, a.spike_type,
       p.serving_team, p.winner_team,
       (sum(coalesce((a.touch_number = 1)::int, 0))
          over (partition by a.match_id, a.point_no order by a.seq))::smallint as possession
from public.actions a
join public.points p on p.match_id = a.match_id and p.point_no = a.point_no;

-- ════════════════════════════════════════════════════════════════════════
-- window_matches: the matches a (season, from, to, last N) filter keeps,
-- newest first. Internal: only the definer functions below call it.
-- ════════════════════════════════════════════════════════════════════════
create function public.window_matches(
  p_season text, p_from date, p_to date, p_last_n int,
  p_player bigint default null, p_drafts boolean default false)
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
      and (p_player is null or exists (
            select 1 from public.match_participants mp
            where mp.match_id = m.id and mp.player_id = p_player))
  ) w
  where p_last_n is null or w.rn <= p_last_n
$$;

-- ════════════════════════════════════════════════════════════════════════
-- leaderboard with a window; adds the denominators the rates need (H1) and
-- fantasy per 21 points played (F3: long and short matches compare).
-- ════════════════════════════════════════════════════════════════════════
drop function public.leaderboard(text);
create function public.leaderboard(
  p_season text default null, p_from date default null, p_to date default null,
  p_last_n int default null)
returns table (player_id bigint, display_name text, matches bigint, wins bigint,
               fantasy numeric, kills bigint, aces bigint, digs bigint,
               assists bigint, blocks bigint, errors bigint,
               attacks bigint, attack_errors bigint, serves bigint,
               points_played bigint, fantasy_per_21 numeric)
language sql stable security definer set search_path = public as $$
  select p.id, p.display_name,
         count(distinct f.match_id),
         count(distinct f.match_id) filter (where f.team = m.winner_team),
         sum(f.fantasy),
         sum(f.kills)::bigint, sum(f.aces)::bigint, sum(f.digs)::bigint,
         sum(f.assists)::bigint, sum(f.blocks)::bigint,
         sum(f.serve_errors + f.attack_errors + f.handling_errors)::bigint,
         sum(f.attacks)::bigint, sum(f.attack_errors)::bigint, sum(f.serves)::bigint,
         coalesce(sum(m.n_points), 0)::bigint,
         round(sum(f.fantasy) / nullif(sum(m.n_points), 0) * 21, 1)
  from public.player_match_fantasy f
  join public.matches m on m.id = f.match_id
  join public.players p on p.id = f.player_id
  where f.match_id in (select public.window_matches(p_season, p_from, p_to, p_last_n))
  group by p.id, p.display_name
  order by sum(f.fantasy) desc, p.display_name;
$$;

-- ════════════════════════════════════════════════════════════════════════
-- player_profile with a window and the new analytics.
-- ════════════════════════════════════════════════════════════════════════
drop function public.player_profile(bigint);
create function public.player_profile(
  p_player_id bigint, p_season text default null, p_from date default null,
  p_to date default null, p_last_n int default null)
returns jsonb
language plpgsql stable security definer set search_path = public as $$
declare
  v_player    jsonb;
  v_history   jsonb;
  v_totals    jsonb;
  v_form      jsonb;
  v_analytics jsonb := null;
  v_allowed   boolean;
  v_ids       bigint[];
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

  select coalesce(array_agg(w), '{}')
    into v_ids
  from public.window_matches(p_season, p_from, p_to, p_last_n, p_player_id, true) w;

  with h as (
    select m.id as match_id, m.match_key, m.match_date, m.start_time, m.title, m.venue,
           m.season, m.score_a, m.score_b, m.n_points, f.team, f.slot,
           (f.team = m.winner_team) as won, f.fantasy, f.kills, f.aces, f.digs,
           f.assists, f.blocks, f.serves, f.attacks, f.attack_errors, f.serve_errors,
           f.serve_errors + f.attack_errors + f.handling_errors as errors
    from public.player_match_fantasy f
    join public.matches m on m.id = f.match_id
    where f.player_id = p_player_id
      and f.match_id = any (v_ids)
  )
  select coalesce(jsonb_agg(to_jsonb(h) order by h.match_date desc, h.start_time desc), '[]'::jsonb),
         jsonb_build_object(
           'matches', count(*), 'wins', count(*) filter (where won),
           'fantasy', coalesce(sum(fantasy), 0), 'kills', coalesce(sum(kills), 0),
           'aces', coalesce(sum(aces), 0), 'digs', coalesce(sum(digs), 0),
           'assists', coalesce(sum(assists), 0), 'blocks', coalesce(sum(blocks), 0),
           'errors', coalesce(sum(errors), 0), 'serves', coalesce(sum(serves), 0),
           'attacks', coalesce(sum(attacks), 0),
           'attack_errors', coalesce(sum(attack_errors), 0),
           'serve_errors', coalesce(sum(serve_errors), 0),
           'points_played', coalesce(sum(n_points), 0),
           'fantasy_per_21', round(sum(fantasy) / nullif(sum(n_points), 0) * 21, 1))
    into v_history, v_totals
  from h;

  -- Form ignores the window: the newest five matches overall, oldest first
  -- (a sparkline), and the average over everything for the comparison.
  select jsonb_build_object(
           'n', count(*),
           'avg5', round(avg(fantasy) filter (where rn <= 5), 2),
           'avg_all', round(avg(fantasy), 2),
           'last5', coalesce(jsonb_agg(fantasy order by rn desc) filter (where rn <= 5), '[]'::jsonb))
    into v_form
  from (select f.fantasy,
               row_number() over (order by m.match_date desc, m.start_time desc nulls last, m.id desc) as rn
        from public.player_match_fantasy f
        join public.matches m on m.id = f.match_id
        where f.player_id = p_player_id
          and (m.status = 'published' or public.is_admin())) x;

  v_allowed := public.can_see_player_analytics(p_player_id);
  if v_allowed then
    with me as (
      select mp.match_id, mp.slot, mp.team
      from public.match_participants mp
      where mp.player_id = p_player_id and mp.match_id = any (v_ids)
    ),
    mine as (
      select t.*, a.landing_x_m, a.landing_y_m, a.landing_err_x_m, a.landing_err_y_m,
             a.landing_in, a.landing_result, a.landing_source, a.own_y_m
      from public.touch_context t
      join public.actions a on a.match_id = t.match_id and a.point_no = t.point_no and a.seq = t.seq
      join me on me.match_id = t.match_id and me.slot = t.slot
    ),
    -- rallies of the matches in the window, from the player's seat
    rallies as (
      select p.*, me.slot as my_slot, me.team as my_team
      from public.points p join me on me.match_id = p.match_id
      where p.winner_team is not null
    ),
    -- who received each serve: the credited first touch of the other team
    recv as (
      select r.match_id, r.point_no, r.serving_team, r.server_slot, r.my_slot, r.my_team,
             r.winner_team, a.slot as receiver_slot, a.team as receiver_team
      from rallies r
      left join public.actions a
        on a.match_id = r.match_id and a.point_no = r.point_no and a.seq = 1
       and a.touch_number = 1 and a.slot is not null
       and a.team is distinct from r.serving_team
    ),
    -- the possession that followed each of MY receptions
    rcp as (
      select t.match_id, t.point_no
      from mine t
      where t.possession = 1 and t.touch_number = 1 and t.seq = 1
    ),
    rcp_poss as (
      select r.match_id, r.point_no,
             coalesce(bool_or(t.action = 'spike'), false)    as has_spike,
             coalesce(bool_or(t.action = 'overpass'), false) as has_over,
             coalesce(bool_or(t.outcome = 'error'), false)   as has_error,
             coalesce(bool_or(t.outcome = 'kill'), false)    as has_kill
      from rcp r
      join public.touch_context t
        on t.match_id = r.match_id and t.point_no = r.point_no and t.possession = 1
      group by r.match_id, r.point_no
    )
    select jsonb_build_object(
      -- rates with their denominators (H1)
      'n_attacks',       count(*) filter (where action in ('spike', 'overpass')),
      'n_kills',         count(*) filter (where action in ('spike', 'overpass') and outcome = 'kill'),
      'n_attack_errors', count(*) filter (where action in ('spike', 'overpass') and outcome = 'error'),
      'n_serves',        count(*) filter (where action = 'serve'),
      'n_aces',          count(*) filter (where action = 'serve' and outcome = 'ace'),
      'n_serve_errors',  count(*) filter (where action = 'serve' and outcome = 'error'),
      'kill_rate',  round(count(*) filter (where action in ('spike', 'overpass') and outcome = 'kill')::numeric
                          / nullif(count(*) filter (where action in ('spike', 'overpass')), 0), 3),
      'attack_error_rate', round(count(*) filter (where action in ('spike', 'overpass') and outcome = 'error')::numeric
                          / nullif(count(*) filter (where action in ('spike', 'overpass')), 0), 3),
      'ace_rate',   round(count(*) filter (where action = 'serve' and outcome = 'ace')::numeric
                          / nullif(count(*) filter (where action = 'serve'), 0), 3),
      'serve_error_rate', round(count(*) filter (where action = 'serve' and outcome = 'error')::numeric
                          / nullif(count(*) filter (where action = 'serve'), 0), 3),
      -- N4: attack efficiency, reception attacks vs transition attacks
      'hit', jsonb_build_object(
        'reception', jsonb_build_object(
          'n',      count(*) filter (where action in ('spike', 'overpass') and possession = 1),
          'kills',  count(*) filter (where action in ('spike', 'overpass') and possession = 1 and outcome = 'kill'),
          'errors', count(*) filter (where action in ('spike', 'overpass') and possession = 1 and outcome = 'error')),
        'transition', jsonb_build_object(
          'n',      count(*) filter (where action in ('spike', 'overpass') and possession >= 2),
          'kills',  count(*) filter (where action in ('spike', 'overpass') and possession >= 2 and outcome = 'kill'),
          'errors', count(*) filter (where action in ('spike', 'overpass') and possession >= 2 and outcome = 'error'))),
      'attack_zones', coalesce((select jsonb_object_agg(z, n) from (
                         select attack_zone as z, count(*) as n from mine
                         where action in ('spike', 'overpass') and attack_zone is not null
                         group by attack_zone) zz), '{}'::jsonb),
      'landings', coalesce((select jsonb_agg(jsonb_build_object(
                         'x', landing_x_m, 'y', landing_y_m,
                         'ex', landing_err_x_m, 'ey', landing_err_y_m,
                         'in', landing_in, 'outcome', outcome,
                         'result', landing_result, 'source', landing_source,
                         'zone', attack_zone, 'type', spike_type))
                       from mine where action in ('spike', 'overpass')
                         and (landing_y_m is not null or landing_result is not null)),
                       '[]'::jsonb),
      'touch_depths', coalesce((select jsonb_agg(jsonb_build_object(
                         'action', action, 'y', own_y_m))
                       from mine where own_y_m is not null), '[]'::jsonb),
      -- N1: side-out and break-point, as points won over points played
      'rally', (select jsonb_build_object(
          'own_serve', jsonb_build_object(
            'n',   count(*) filter (where server_slot = my_slot),
            'won', count(*) filter (where server_slot = my_slot and winner_team = my_team)),
          'team_serving', jsonb_build_object(
            'n',   count(*) filter (where serving_team = my_team),
            'won', count(*) filter (where serving_team = my_team and winner_team = my_team)),
          'team_receiving', jsonb_build_object(
            'n',   count(*) filter (where serving_team <> my_team),
            'won', count(*) filter (where serving_team <> my_team and winner_team = my_team)))
        from rallies),
      -- N2: serve targeting. As the receiver: of the serves aimed at my team
      -- (a credited first touch), how many I took. As the server: who took mine.
      'serve_in', (select jsonb_build_object(
          'opp_serves',  count(*) filter (where serving_team <> my_team),
          'team_credited', count(*) filter (where serving_team <> my_team and receiver_team = my_team),
          'mine',        count(*) filter (where serving_team <> my_team and receiver_slot = my_slot))
        from recv),
      'serve_out', (select jsonb_build_object(
          'serves', count(*) filter (where server_slot = my_slot),
          'unseen', count(*) filter (where server_slot = my_slot and receiver_slot is null),
          'to', coalesce((select jsonb_agg(jsonb_build_object(
                    'player_id', t.player_id, 'display_name', t.display_name, 'n', t.n)
                    order by t.n desc, t.display_name)
                  from (select mp.player_id, coalesce(pl.display_name, rv.receiver_slot) as display_name,
                               count(*) as n
                        from recv rv
                        left join public.match_participants mp
                          on mp.match_id = rv.match_id and mp.slot = rv.receiver_slot
                        left join public.players pl on pl.id = mp.player_id
                        where rv.server_slot = rv.my_slot and rv.receiver_slot is not null
                        group by mp.player_id, coalesce(pl.display_name, rv.receiver_slot)) t),
                 '[]'::jsonb))
        from recv),
      -- N3: what my receptions became (pass-quality proxy, no grading)
      'reception', (select jsonb_build_object(
          'n', count(*),
          'spike',   count(*) filter (where has_spike),
          'overpass', count(*) filter (where not has_spike and has_over),
          'error',   count(*) filter (where not has_spike and not has_over and has_error),
          'none',    count(*) filter (where not has_spike and not has_over and not has_error),
          'first_ball_kills', count(*) filter (where has_kill))
        from rcp_poss),
      -- progress: the sequences a rolling window is drawn from, oldest first
      'attack_series', coalesce((select jsonb_agg(jsonb_build_object(
                         'd', m.match_date,
                         'r', case s.outcome when 'kill' then 'kill' when 'error' then 'error' else 'other' end)
                         order by m.match_date, m.start_time, s.point_no, s.seq)
                       from mine s join public.matches m on m.id = s.match_id
                       where s.action in ('spike', 'overpass')), '[]'::jsonb),
      'serve_series', coalesce((select jsonb_agg(jsonb_build_object(
                         'd', m.match_date,
                         'r', case s.outcome when 'ace' then 'ace' when 'error' then 'error' else 'other' end)
                         order by m.match_date, m.start_time, s.point_no, s.seq)
                       from mine s join public.matches m on m.id = s.match_id
                       where s.action = 'serve'), '[]'::jsonb))
      into v_analytics
    from mine;
  end if;

  return jsonb_build_object('player', v_player, 'totals', v_totals, 'history', v_history,
                            'form', v_form, 'can_see_analytics', v_allowed,
                            'analytics', v_analytics);
end $$;

-- ════════════════════════════════════════════════════════════════════════
-- match_report: the report card of one match (league tier, plus the
-- per-point fantasy timeline where the play-by-play is visible).
-- ════════════════════════════════════════════════════════════════════════
create function public.match_report(p_match_id bigint)
returns jsonb
language plpgsql stable security definer set search_path = public as $$
declare
  v_ok       boolean;
  v_detail   boolean;
  v_teams    jsonb;
  v_players  jsonb;
  v_targets  jsonb;
  v_timeline jsonb := null;
begin
  if auth.uid() is null then
    raise exception 'not authenticated';
  end if;
  select exists (select 1 from public.matches m
                 where m.id = p_match_id and (m.status = 'published' or public.is_admin()))
    into v_ok;
  if not v_ok then
    return null;
  end if;
  v_detail := public.can_see_match_detail(p_match_id);

  -- N1 per team: side-out (receiving) and break-point (serving)
  select coalesce(jsonb_object_agg(t.team, jsonb_build_object(
           'serve_n', t.serve_n, 'serve_won', t.serve_won,
           'recv_n', t.recv_n, 'recv_won', t.recv_won)), '{}'::jsonb)
    into v_teams
  from (select tm.team,
               count(*) filter (where p.serving_team = tm.team)                              as serve_n,
               count(*) filter (where p.serving_team = tm.team and p.winner_team = tm.team)  as serve_won,
               count(*) filter (where p.serving_team <> tm.team)                             as recv_n,
               count(*) filter (where p.serving_team <> tm.team and p.winner_team = tm.team) as recv_won
        from public.points p
        cross join (values ('A'), ('B')) as tm(team)
        where p.match_id = p_match_id and p.winner_team is not null
        group by tm.team) t;

  -- N2: who took each team's serves (the credited first touch of the other team)
  with serve_recv as (
    select p.serving_team, a.slot as receiver_slot
    from public.points p
    left join public.actions a
      on a.match_id = p.match_id and a.point_no = p.point_no and a.seq = 1
     and a.touch_number = 1 and a.slot is not null
     and a.team is distinct from p.serving_team
    where p.match_id = p_match_id and p.serving_team is not null
  )
  select coalesce(jsonb_object_agg(s.serving_team, jsonb_build_object('to', s.recv, 'unseen', s.unseen)),
                  '{}'::jsonb)
    into v_targets
  from (select r.serving_team,
               count(*) filter (where r.receiver_slot is null) as unseen,
               (select coalesce(jsonb_object_agg(x.receiver_slot, x.n), '{}'::jsonb)
                from (select receiver_slot, count(*) as n from serve_recv q
                      where q.serving_team = r.serving_team and q.receiver_slot is not null
                      group by receiver_slot) x) as recv
        from serve_recv r
        group by r.serving_team) s;

  -- Per player: this match against their other published matches (N8), the
  -- attack split (N4) and how often they won the point they served.
  select coalesce(jsonb_agg(r order by r.team, r.slot), '[]'::jsonb)
    into v_players
  from (
    select f.slot, f.team, f.player_id, pl.display_name, f.fantasy,
           round(f.fantasy / nullif(m.n_points, 0) * 21, 1) as fantasy_per_21,
           f.serves, f.aces, f.serve_errors, f.digs, f.sets, f.assists, f.attacks, f.kills,
           f.attack_errors, f.handling_errors,
           (select jsonb_build_object(
              'reception', jsonb_build_object(
                'n', count(*) filter (where t.action in ('spike', 'overpass') and t.possession = 1),
                'kills', count(*) filter (where t.action in ('spike', 'overpass') and t.possession = 1 and t.outcome = 'kill'),
                'errors', count(*) filter (where t.action in ('spike', 'overpass') and t.possession = 1 and t.outcome = 'error')),
              'transition', jsonb_build_object(
                'n', count(*) filter (where t.action in ('spike', 'overpass') and t.possession >= 2),
                'kills', count(*) filter (where t.action in ('spike', 'overpass') and t.possession >= 2 and t.outcome = 'kill'),
                'errors', count(*) filter (where t.action in ('spike', 'overpass') and t.possession >= 2 and t.outcome = 'error')))
            from public.touch_context t
            where t.match_id = f.match_id and t.slot = f.slot) as hit,
           (select jsonb_build_object(
              'n', count(*) filter (where p.server_slot = f.slot),
              'won', count(*) filter (where p.server_slot = f.slot and p.winner_team = f.team))
            from public.points p
            where p.match_id = f.match_id and p.winner_team is not null) as own_serve,
           case when f.player_id is null then null else (
             select jsonb_build_object(
                'matches', count(*),
                'fantasy', round(avg(o.fantasy), 2),
                'kills', round(avg(o.kills), 2), 'aces', round(avg(o.aces), 2),
                'digs', round(avg(o.digs), 2), 'assists', round(avg(o.assists), 2),
                'errors', round(avg(o.serve_errors + o.attack_errors + o.handling_errors), 2),
                'attacks', round(avg(o.attacks), 2))
             from public.player_match_fantasy o
             join public.matches mo on mo.id = o.match_id and mo.status = 'published'
             where o.player_id = f.player_id and o.match_id <> f.match_id)
           end as avg
    from public.player_match_fantasy f
    join public.matches m on m.id = f.match_id
    left join public.players pl on pl.id = f.player_id
    where f.match_id = p_match_id
  ) r;

  if v_detail then
    select coalesce(jsonb_agg(jsonb_build_object('point_no', t.point_no, 'slot', t.slot, 'pts', t.pts)
                              order by t.point_no, t.slot), '[]'::jsonb)
      into v_timeline
    from (select af.point_no, af.slot, sum(af.points) as pts
          from public.action_fantasy af
          where af.match_id = p_match_id
          group by af.point_no, af.slot) t;
  end if;

  return jsonb_build_object('match_id', p_match_id, 'teams', v_teams, 'players', v_players,
                            'serve_targets', v_targets, 'timeline', v_timeline);
end $$;

-- ════════════════════════════════════════════════════════════════════════
-- privileges. New functions get Supabase's default EXECUTE for anon: close
-- it, then open exactly the read API.
-- ════════════════════════════════════════════════════════════════════════
revoke execute on function
  public.window_matches(text, date, date, int, bigint, boolean),
  public.leaderboard(text, date, date, int),
  public.player_profile(bigint, text, date, date, int),
  public.match_report(bigint)
  from public, anon, authenticated;
grant execute on function
  public.leaderboard(text, date, date, int),
  public.player_profile(bigint, text, date, date, int),
  public.match_report(bigint)
  to authenticated;
