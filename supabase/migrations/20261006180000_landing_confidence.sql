-- Landings the web can be honest about: where an attack came down now has
-- both axes for dug balls, an error per axis, and what became of the attack.
--
--   landing_err_x_m / landing_err_y_m   how far off the position may be, in
--       metres across / along the court (about one sigma, best effort). The
--       camera stands ~1.5 m up, so depth is the weak axis. NULL = published
--       before the error was recorded.
--   landing_result   kill | dug | out | net | error. `out` and `net` only when
--       the run saw it; an attack error it cannot place is a plain `error`;
--       NULL = nobody ruled on the ball.
--
-- publish_match fills them by column name (jsonb_populate_record), so matches
-- get the new values on their next publish; older rows stay NULL.

alter table public.actions
  add column landing_err_x_m real,
  add column landing_err_y_m real,
  add column landing_result  text
    check (landing_result in ('kill', 'dug', 'out', 'net', 'error'));

-- player_profile: landings carry the error, the result and the attack's
-- origin, and include attacks with a result but no position (into the net,
-- ball lost) so the page can count them.
create or replace function public.player_profile(p_player_id bigint)
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
                       from mine where own_y_m is not null), '[]'::jsonb))
      into v_analytics
    from mine;
  end if;

  return jsonb_build_object('player', v_player, 'totals', v_totals, 'history', v_history,
                            'can_see_analytics', v_allowed, 'analytics', v_analytics);
end $$;
