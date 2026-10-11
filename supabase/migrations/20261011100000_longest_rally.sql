-- match_report: the longest rally of the match (owner-asked 2026-10-11).
--
--   longest_rally   {"point_no", "touches", "net_crossings"} of the point with
--                   the most touches; null for a match without touches.
--
-- LEAGUE tier: it says nothing about a player (no slot, no name), only how
-- long the longest point was -- every member reads it with the result, like
-- the score. It is counted from the touches a member may not read one by one
-- (`actions` stays participant-only): the function gives the two counts and
-- the point number, never a touch.
--
-- Same definition as the post-run report (`src/postrun/reconstruct.py`,
-- `rally_shape`) and the demo mode (`webapp/src/lib/analytics.ts`,
-- `longestRally`), pinned by the same fixture in `supabase/checks/rls_smoke.sql`.
-- Counted from rows already published: no re-publish needed.
--
-- The rest of the function is 20261007130000 unchanged; same signature, so
-- its grants stay.

create or replace function public.match_report(p_match_id bigint)
returns jsonb
language plpgsql stable security definer set search_path = public as $$
declare
  v_ok       boolean;
  v_detail   boolean;
  v_slot_ok  jsonb;            -- slot -> may the reader see that player's analytics here
  v_team_ok  jsonb;            -- team -> ... of both its players
  v_teams    jsonb;
  v_players  jsonb;
  v_targets  jsonb;
  v_timeline jsonb := null;
  v_longest  jsonb := null;
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

  with s as (
    select mp.slot, mp.team,
           (v_detail or (mp.player_id is not null
                         and public.can_see_player_analytics(mp.player_id))) as ok
    from public.match_participants mp
    where mp.match_id = p_match_id
  )
  select coalesce((select jsonb_object_agg(s.slot, s.ok) from s), '{}'::jsonb),
         coalesce((select jsonb_object_agg(t.team, t.ok)
                   from (select s.team, bool_and(s.ok) as ok from s group by s.team) t), '{}'::jsonb)
    into v_slot_ok, v_team_ok;

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

  -- The longest rally (league tier: a fact about the match, no player in it).
  -- Every touch of the point counts, the serve and the ones kept without a
  -- slot too; the ball went over the net once per change of team between two
  -- touches, plus the last ball when the team that hit it won the point (it
  -- came down on the other half). Ties: more crossings, then the earlier point.
  with t as (
    select a.point_no, a.team,
           lag(a.team) over w as prev_team,
           a.seq = max(a.seq) over (partition by a.point_no) as is_last
    from public.actions a
    where a.match_id = p_match_id
    window w as (partition by a.point_no order by a.seq)
  )
  select jsonb_build_object('point_no', r.point_no, 'touches', r.touches,
                            'net_crossings', r.net_crossings)
    into v_longest
  from (select t.point_no,
               count(*) as touches,
               count(*) filter (where t.team <> t.prev_team)
                 + count(*) filter (where t.is_last and t.team = p.winner_team) as net_crossings
        from t
        join public.points p on p.match_id = p_match_id and p.point_no = t.point_no
        group by t.point_no) r
  order by r.touches desc, r.net_crossings desc, r.point_no
  limit 1;

  -- N2: who took each team's serves (the credited first touch of the other
  -- team) -- a number about the RECEIVING pair, so both of them must be visible
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
        group by r.serving_team) s
  where v_detail
     or coalesce((v_team_ok ->> case s.serving_team when 'A' then 'B' else 'A' end)::boolean, false);

  -- Per player: the box-score line (league tier), then this match against
  -- their other published matches (N8), the attack split (N4) and how often
  -- they won the point they served (analytics tier).
  select coalesce(jsonb_agg(r order by r.team, r.slot), '[]'::jsonb)
    into v_players
  from (
    select f.slot, f.team, f.player_id, pl.display_name, f.fantasy,
           round(f.fantasy / nullif(m.n_points, 0) * 21, 1) as fantasy_per_21,
           f.serves, f.aces, f.serve_errors, f.digs, f.sets, f.assists, f.attacks, f.kills,
           f.attack_errors, f.handling_errors,
           case when coalesce((v_slot_ok ->> f.slot)::boolean, v_detail) then (
             select jsonb_build_object(
              'reception', jsonb_build_object(
                'n', count(*) filter (where t.action in ('spike', 'overpass') and t.possession = 1),
                'kills', count(*) filter (where t.action in ('spike', 'overpass') and t.possession = 1 and t.outcome = 'kill'),
                'errors', count(*) filter (where t.action in ('spike', 'overpass') and t.possession = 1 and t.outcome = 'error')),
              'transition', jsonb_build_object(
                'n', count(*) filter (where t.action in ('spike', 'overpass') and t.possession >= 2),
                'kills', count(*) filter (where t.action in ('spike', 'overpass') and t.possession >= 2 and t.outcome = 'kill'),
                'errors', count(*) filter (where t.action in ('spike', 'overpass') and t.possession >= 2 and t.outcome = 'error')))
             from public.touch_context t
             where t.match_id = f.match_id and t.slot = f.slot)
           end as hit,
           case when coalesce((v_team_ok ->> f.team)::boolean, v_detail) then (
             select jsonb_build_object(
              'n', count(*) filter (where p.server_slot = f.slot),
              'won', count(*) filter (where p.server_slot = f.slot and p.winner_team = f.team))
             from public.points p
             where p.match_id = f.match_id and p.winner_team is not null)
           end as own_serve,
           case when f.player_id is not null
                 and coalesce((v_slot_ok ->> f.slot)::boolean, v_detail) then (
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
                            'serve_targets', v_targets, 'timeline', v_timeline,
                            'longest_rally', v_longest);
end $$;
