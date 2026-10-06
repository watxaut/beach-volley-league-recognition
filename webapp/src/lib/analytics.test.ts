// The same two-point fixture rls_smoke.sql uses, with the same expectations:
// the browser's copy of the definitions and the database's must not drift.
import { describe, expect, it } from 'vitest'
import { bestPoint, cumulative, hitSplit, mvps, playerAnalytics, serveTargets, teamRally, type Seat, type Touch } from './analytics'
import type { PointRow, Slot, Team } from './types'

const pt = (n: number, serving: Team, server: Slot, winner: Team): PointRow => ({
  match_id: 1, point_no: n, set_no: 1, start_frame: 0, end_frame: 0, serving_team: serving, server_slot: server,
  near_team: 'A', winner_team: winner, winner_source: 'next_serve', end_kind: 'ground',
  score_a_after: 0, score_b_after: 0, flags: [],
})
const t = (point_no: number, seq: number, slot: Slot | null, team: Team, action: string, touch_number: number,
           outcome: Touch['outcome'] = null): Touch => ({ point_no, seq, slot, team, action, touch_number, outcome })

const points = [pt(1, 'B', 'P1B', 'A'), pt(2, 'A', 'P1A', 'A')]
const touches = [
  t(1, 0, 'P1B', 'B', 'serve', 0), t(1, 1, 'P1A', 'A', 'dig', 1), t(1, 2, 'P2A', 'A', 'set', 2),
  t(1, 3, 'P1A', 'A', 'spike', 3, 'kill'), t(1, 4, null, 'B', 'dig', 1),
  t(2, 0, 'P1A', 'A', 'serve', 0), t(2, 1, 'P1B', 'B', 'dig', 1), t(2, 2, 'P2B', 'B', 'set', 2, 'error'),
]
const who = (slot: Slot) => ({ player_id: null, display_name: { P1B: 'Check Opp1', P2B: 'Check Opp2', P1A: 'Check Ari', P2A: 'Check Joan' }[slot] })
const ari: Seat = { slot: 'P1A', team: 'A', date: '2026-09-20', points, touches, who }

describe('playerAnalytics (the smoke-check fixture)', () => {
  const a = playerAnalytics([ari])
  it('counts with denominators', () => {
    expect([a.n_attacks, a.n_kills, a.n_serves]).toEqual([1, 1, 1])
  })
  it('splits attacks by reception vs transition', () => {
    expect(a.hit).toEqual({ reception: { n: 1, kills: 1, errors: 0 }, transition: { n: 0, kills: 0, errors: 0 } })
  })
  it('side-out and break-point', () => {
    expect(a.rally.own_serve).toEqual({ n: 1, won: 1 })
    expect(a.rally.team_receiving).toEqual({ n: 1, won: 1 })
    expect(a.rally.team_serving).toEqual({ n: 1, won: 1 })
  })
  it('serve targets, in and out', () => {
    expect(a.serve_in).toEqual({ opp_serves: 1, team_credited: 1, mine: 1 })
    expect(a.serve_out.to).toEqual([{ player_id: null, display_name: 'Check Opp1', n: 1 }])
    expect(a.serve_out.unseen).toBe(0)
  })
  it('reception outcome', () => {
    expect(a.reception).toEqual({ n: 1, spike: 1, overpass: 0, error: 0, none: 0, first_ball_kills: 1 })
  })
  it('progress series', () => {
    expect(a.attack_series).toEqual([{ d: '2026-09-20', r: 'kill' }])
    expect(a.serve_series).toEqual([{ d: '2026-09-20', r: 'other' }])
  })
})

describe('reception outcomes beyond the fixture', () => {
  it('a reception whose possession ends with a handling error is an error; one with nothing after it is none', () => {
    const opp: Seat = { ...ari, slot: 'P1B', team: 'B' }
    expect(playerAnalytics([opp]).reception).toEqual({ n: 1, spike: 0, overpass: 0, error: 1, none: 0, first_ball_kills: 0 })
    const bare = [t(1, 0, 'P1B', 'B', 'serve', 0), t(1, 1, 'P1A', 'A', 'dig', 1)]
    expect(playerAnalytics([{ ...ari, points: [points[0]], touches: bare }]).reception.none).toBe(1)
  })
  it('a free ball is an overpass reception', () => {
    const over = [t(1, 0, 'P1B', 'B', 'serve', 0), t(1, 1, 'P1A', 'A', 'dig', 1), t(1, 2, 'P2A', 'A', 'overpass', 2)]
    expect(playerAnalytics([{ ...ari, points: [points[0]], touches: over }]).reception.overpass).toBe(1)
  })
})

describe('match level', () => {
  it('team side-out and break', () => {
    expect(teamRally(points)).toEqual({
      A: { serve_n: 1, serve_won: 1, recv_n: 1, recv_won: 1 },
      B: { serve_n: 1, serve_won: 0, recv_n: 1, recv_won: 0 },
    })
  })
  it('who took each team’s serves', () => {
    expect(serveTargets(points, touches)).toEqual({
      B: { to: { P1A: 1 }, unseen: 0 }, A: { to: { P1B: 1 }, unseen: 0 },
    })
  })
  it('hit split per slot', () => {
    expect(hitSplit(touches, 'P1A').reception.kills).toBe(1)
  })
  it('running fantasy, MVP and best point', () => {
    const timeline = [
      { point_no: 1, slot: 'P1A' as Slot, pts: 2 }, { point_no: 1, slot: 'P2A' as Slot, pts: 0.5 },
      { point_no: 2, slot: 'P1B' as Slot, pts: 1 }, { point_no: 2, slot: 'P2B' as Slot, pts: -1 },
    ]
    expect(cumulative(timeline, 2).P1A).toEqual([0, 2, 2])
    expect(cumulative(timeline, 2).P2B).toEqual([0, 0, -1])
    expect(mvps([{ slot: 'P1A', fantasy: 2 }, { slot: 'P2A', fantasy: 2 }, { slot: 'P1B', fantasy: 1 }])).toEqual(['P1A', 'P2A'])
    expect(bestPoint(timeline, 'P1A')).toEqual({ point_no: 1, pts: 2 })
    expect(bestPoint(timeline, 'P2B')).toBeNull()
  })
})
