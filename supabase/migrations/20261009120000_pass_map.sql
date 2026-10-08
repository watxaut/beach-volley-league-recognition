-- Reception and defense on the player page (#99).
--
-- The post-run layer labels the first touch of a possession `dig` whether it
-- followed a serve or an attack. The two are different skills, so
-- player_profile() now tells them apart from the touch BEFORE the dig:
--
--   reception   the previous touch is the serve
--   defense     the previous touch is a spike or an overpass from the other half
--
-- A dig after anything else is in neither. Only credited digs (`slot` set,
-- the same rule as every other stat) are listed.
--
-- `analytics.passes` = one row per credited reception / defense:
--   k          'reception' | 'defense'
--   sx, sy     where the player played it (own frame: y 0 = own baseline, 8 = net)
--   sex, sey   how far off that may be (about one sigma, metres; depth is weak)
--   x, y       where the ball was at the NEXT touch, if that touch was seen on
--              the same half -- where the pass went. Null when the ball went
--              over, died, or the next touch was not seen. A touch the stream
--              never saw is not trusted for a position (precision first).
--   ex, ey     the same error for that point
--   to         what that next touch was: set | spike | overpass
--   d          the match day
-- Both ends are in the passer's own frame (the next touch is the same team's,
-- and a team keeps its half within a rally, so the frames agree). No post-run change and no re-publish: every action
-- row already carries its own_x_m / own_y_m.
--
-- Analytics tier, signature and privileges unchanged (create or replace).

create or replace function public.player_profile(
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
             a.landing_in, a.landing_result, a.landing_source, a.own_x_m, a.own_y_m,
             (a.extra #>> '{court_err_m,0}')::real as own_err_x_m,
             (a.extra #>> '{court_err_m,1}')::real as own_err_y_m,
             m.match_date,
             -- hard / touch as the post-run flight read typed it. A row
             -- published before that read existed has no `extra.launch`: its
             -- `spike_type` is the causal guess (10 of 16 right) and is never
             -- shown as a type.
             case when a.extra ? 'launch' and t.spike_type in ('hard', 'touch')
                  then t.spike_type end as shot_type,
             case when t.action = 'overpass' then 'free'
                  when t.action <> 'spike' then null
                  when a.extra ? 'launch' and t.spike_type in ('hard', 'touch') then t.spike_type
                  else 'unread' end as shot
      from public.touch_context t
      join public.actions a on a.match_id = t.match_id and a.point_no = t.point_no and a.seq = t.seq
      join me on me.match_id = t.match_id and me.slot = t.slot
      join public.matches m on m.id = t.match_id
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
    ),
    -- every touch of the window's matches with the one before it and the one
    -- after it in its rally
    ctx as (
      select a.match_id, a.point_no, a.seq, a.slot, a.action, a.team, a.touch_number,
             a.own_x_m, a.own_y_m,
             (a.extra #>> '{court_err_m,0}')::real as err_x, (a.extra #>> '{court_err_m,1}')::real as err_y,
             lag(a.action) over w as prev_action, lag(a.team) over w as prev_team,
             lead(a.action) over w as next_action, lead(a.team) over w as next_team,
             lead(a.observed) over w as next_observed,
             lead(a.own_x_m) over w as next_x, lead(a.own_y_m) over w as next_y,
             (lead(a.extra) over w #>> '{court_err_m,0}')::real as next_err_x,
             (lead(a.extra) over w #>> '{court_err_m,1}')::real as next_err_y
      from public.actions a
      where a.match_id = any (v_ids)
      window w as (partition by a.match_id, a.point_no order by a.seq)
    ),
    -- my receptions (after a serve) and defenses (after an attack)
    passes as (
      select c.*, m.match_date,
             case when c.prev_action = 'serve' then 'reception' else 'defense' end as kind,
             (c.next_team = c.team and c.next_observed
              and c.next_x is not null and c.next_y is not null) as went
      from ctx c
      join me on me.match_id = c.match_id and me.slot = c.slot
      join public.matches m on m.id = c.match_id
      where c.action = 'dig' and c.touch_number = 1
        and c.prev_action in ('serve', 'spike', 'overpass')
        and c.prev_team <> c.team
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
      -- hard / touch / free ball / not read: the four add up to n_attacks
      'shots', jsonb_build_object(
        'hard', jsonb_build_object(
          'n',      count(*) filter (where shot = 'hard'),
          'kills',  count(*) filter (where shot = 'hard' and outcome = 'kill'),
          'errors', count(*) filter (where shot = 'hard' and outcome = 'error')),
        'touch', jsonb_build_object(
          'n',      count(*) filter (where shot = 'touch'),
          'kills',  count(*) filter (where shot = 'touch' and outcome = 'kill'),
          'errors', count(*) filter (where shot = 'touch' and outcome = 'error')),
        'free', jsonb_build_object(
          'n',      count(*) filter (where shot = 'free'),
          'kills',  count(*) filter (where shot = 'free' and outcome = 'kill'),
          'errors', count(*) filter (where shot = 'free' and outcome = 'error')),
        'unread', jsonb_build_object(
          'n',      count(*) filter (where shot = 'unread'),
          'kills',  count(*) filter (where shot = 'unread' and outcome = 'kill'),
          'errors', count(*) filter (where shot = 'unread' and outcome = 'error'))),
      'attack_zones', coalesce((select jsonb_object_agg(z, n) from (
                         select attack_zone as z, count(*) as n from mine
                         where action in ('spike', 'overpass') and attack_zone is not null
                         group by attack_zone) zz), '{}'::jsonb),
      'landings', coalesce((select jsonb_agg(jsonb_build_object(
                         'x', landing_x_m, 'y', landing_y_m,
                         'ex', landing_err_x_m, 'ey', landing_err_y_m,
                         'in', landing_in, 'outcome', outcome,
                         'result', landing_result, 'source', landing_source,
                         'zone', attack_zone, 'type', shot_type,
                         -- the attack map: where the ball was hit (own frame,
                         -- y 0 = own baseline .. 8 = net) and how far off that
                         -- may be, spike or free ball, the possession it came
                         -- in (1 = off the reception), the match day
                         'sx', own_x_m, 'sy', own_y_m,
                         'sex', own_err_x_m, 'sey', own_err_y_m,
                         'a', action, 'p', possession, 'd', match_date)
                         order by match_date, match_id, point_no, seq)
                       from mine where action in ('spike', 'overpass')
                         and (landing_y_m is not null or landing_result is not null
                              or own_y_m is not null)),
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
      -- reception / defense: where the player played it and where the ball
      -- went next (#99). Credited digs only; the destination needs a seen
      -- next touch on the same half.
      'passes', coalesce((select jsonb_agg(jsonb_build_object(
                         'k', kind,
                         'sx', own_x_m, 'sy', own_y_m, 'sex', err_x, 'sey', err_y,
                         'x', case when went then next_x end, 'y', case when went then next_y end,
                         'ex', case when went then next_err_x end, 'ey', case when went then next_err_y end,
                         'to', case when went then next_action end,
                         'd', match_date)
                         order by match_date, match_id, point_no, seq)
                       from passes), '[]'::jsonb),
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
