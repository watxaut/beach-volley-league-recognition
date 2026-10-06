// The stats of the brainstorm's "Now" list, counted in the browser from raw
// touches. Production never does this: raw touches are visible only to the
// players of a match, so the database computes the same numbers in
// `player_profile` / `match_report` (supabase/migrations/2026100710*). This is
// the demo mode's copy of those definitions, pinned by analytics.test.ts with
// the fixture the SQL smoke check uses.
import type { PlayerAnalytics, PointRow, ReportPlayer, Slot, Tally, Team, WonOf } from './types'

export interface Touch {
  point_no: number
  seq: number
  slot: Slot | null
  team: Team | null
  action: string
  outcome: 'ace' | 'kill' | 'error' | null
  /** 0 = the serve, then 1, 2, 3 within one possession. */
  touch_number: number
}

/** Seat of a player in one match, oldest match first. */
export interface Seat {
  slot: Slot
  team: Team
  date: string
  points: PointRow[]
  touches: Touch[]
  /** Who sat in a slot of this match (for naming serve targets). */
  who: (slot: Slot) => { player_id: number | null; display_name: string }
}

const ATTACKS = ['spike', 'overpass']
const isAttack = (t: Touch) => ATTACKS.includes(t.action)

/** Possession number of every touch: 0 = the serve, 1 = the reception, 2 =
 * the answer, ... A possession starts at each touch_number 1. Key `point:seq`. */
export function possessions(touches: Touch[]): Map<string, number> {
  const out = new Map<string, number>()
  const byPoint = new Map<number, Touch[]>()
  for (const t of touches) byPoint.set(t.point_no, [...(byPoint.get(t.point_no) ?? []), t])
  for (const [pointNo, list] of byPoint) {
    let n = 0
    for (const t of [...list].sort((a, b) => a.seq - b.seq)) {
      if (t.touch_number === 1) n++
      out.set(`${pointNo}:${t.seq}`, n)
    }
  }
  return out
}

const tally = (): Tally => ({ n: 0, kills: 0, errors: 0 })
const wonOf = (): WonOf => ({ n: 0, won: 0 })

/** The credited first touch of the receiving team, if any. */
export function receiverOf(point: PointRow, touches: Touch[]): Touch | null {
  return touches.find((t) => t.point_no === point.point_no && t.seq === 1 && t.touch_number === 1
    && t.slot !== null && t.team !== point.serving_team) ?? null
}

/** Attack split of one slot: off the reception vs in transition (N4). */
export function hitSplit(touches: Touch[], slot: Slot): { reception: Tally; transition: Tally } {
  const poss = possessions(touches)
  const out = { reception: tally(), transition: tally() }
  for (const t of touches) {
    if (t.slot !== slot || !isAttack(t)) continue
    const bucket = poss.get(`${t.point_no}:${t.seq}`) === 1 ? out.reception : out.transition
    bucket.n++
    if (t.outcome === 'kill') bucket.kills++
    if (t.outcome === 'error') bucket.errors++
  }
  return out
}

/** N1 per team of one match: serving = break-point, receiving = side-out. */
export function teamRally(points: PointRow[]) {
  const out: Partial<Record<Team, { serve_n: number; serve_won: number; recv_n: number; recv_won: number }>> = {}
  for (const team of ['A', 'B'] as Team[]) {
    const row = { serve_n: 0, serve_won: 0, recv_n: 0, recv_won: 0 }
    for (const p of points) {
      if (!p.winner_team) continue
      const won = p.winner_team === team ? 1 : 0
      if (p.serving_team === team) { row.serve_n++; row.serve_won += won } else { row.recv_n++; row.recv_won += won }
    }
    out[team] = row
  }
  return out
}

/** N2 per serving team of one match: who took the serves. */
export function serveTargets(points: PointRow[], touches: Touch[]) {
  const out: Partial<Record<Team, { to: Partial<Record<Slot, number>>; unseen: number }>> = {}
  for (const p of points) {
    if (!p.serving_team) continue
    const row = out[p.serving_team] ?? { to: {}, unseen: 0 }
    const r = receiverOf(p, touches)
    if (r?.slot) row.to[r.slot] = (row.to[r.slot] ?? 0) + 1
    else row.unseen++
    out[p.serving_team] = row
  }
  return out
}

/** Fantasy per point and slot (F3), from the rule points of each credited touch. */
export function pointFantasy(touches: Touch[], pointsFor: (t: Touch, assist: boolean) => number,
                             assistOf: (t: Touch) => boolean) {
  const sums = new Map<string, number>()
  for (const t of touches) {
    if (!t.slot) continue
    const pts = pointsFor(t, assistOf(t))
    if (pts === 0) continue
    const key = `${t.point_no}|${t.slot}`
    sums.set(key, (sums.get(key) ?? 0) + pts)
  }
  return [...sums].map(([key, pts]) => {
    const [pointNo, slot] = key.split('|')
    return { point_no: Number(pointNo), slot: slot as Slot, pts }
  }).sort((a, b) => a.point_no - b.point_no || a.slot.localeCompare(b.slot))
}

const ratio = (k: number, n: number) => (n ? Math.round((k / n) * 1000) / 1000 : null)

/** N1-N4 and the progress series of one player over the seats in a window. */
export function playerAnalytics(seats: Seat[]): Omit<PlayerAnalytics, 'attack_zones' | 'landings' | 'touch_depths'> {
  const out = {
    n_attacks: 0, n_kills: 0, n_attack_errors: 0, n_serves: 0, n_aces: 0, n_serve_errors: 0,
    hit: { reception: tally(), transition: tally() },
    rally: { own_serve: wonOf(), team_serving: wonOf(), team_receiving: wonOf() },
    serve_in: { opp_serves: 0, team_credited: 0, mine: 0 },
    serve_out: { serves: 0, unseen: 0, to: [] as PlayerAnalytics['serve_out']['to'] },
    reception: { n: 0, spike: 0, overpass: 0, error: 0, none: 0, first_ball_kills: 0 },
    attack_series: [] as PlayerAnalytics['attack_series'],
    serve_series: [] as PlayerAnalytics['serve_series'],
  }
  const to = new Map<string, { player_id: number | null; display_name: string; n: number }>()
  for (const seat of seats) {
    const poss = possessions(seat.touches)
    const mine = seat.touches.filter((t) => t.slot === seat.slot)
    for (const t of mine.sort((a, b) => a.point_no - b.point_no || a.seq - b.seq)) {
      if (isAttack(t)) {
        out.n_attacks++
        if (t.outcome === 'kill') out.n_kills++
        if (t.outcome === 'error') out.n_attack_errors++
        const bucket = poss.get(`${t.point_no}:${t.seq}`) === 1 ? out.hit.reception : out.hit.transition
        bucket.n++
        if (t.outcome === 'kill') bucket.kills++
        if (t.outcome === 'error') bucket.errors++
        out.attack_series.push({ d: seat.date, r: t.outcome === 'kill' ? 'kill' : t.outcome === 'error' ? 'error' : 'other' })
      }
      if (t.action === 'serve') {
        out.n_serves++
        if (t.outcome === 'ace') out.n_aces++
        if (t.outcome === 'error') out.n_serve_errors++
        out.serve_series.push({ d: seat.date, r: t.outcome === 'ace' ? 'ace' : t.outcome === 'error' ? 'error' : 'other' })
      }
    }
    for (const p of seat.points) {
      if (!p.winner_team) continue
      const won = p.winner_team === seat.team
      const recv = receiverOf(p, seat.touches)
      if (p.server_slot === seat.slot) {
        out.rally.own_serve.n++
        if (won) out.rally.own_serve.won++
        out.serve_out.serves++
        if (!recv?.slot) out.serve_out.unseen++
        else {
          const who = seat.who(recv.slot)
          const key = `${who.player_id}|${who.display_name}`
          to.set(key, { ...who, n: (to.get(key)?.n ?? 0) + 1 })
        }
      }
      const side = p.serving_team === seat.team ? out.rally.team_serving : out.rally.team_receiving
      side.n++
      if (won) side.won++
      if (p.serving_team !== seat.team) {
        out.serve_in.opp_serves++
        if (recv?.team === seat.team) out.serve_in.team_credited++
        if (recv?.slot === seat.slot) out.serve_in.mine++
      }
      // N3: my reception, and what the possession it started became
      if (recv?.slot === seat.slot) {
        const first = seat.touches.filter((t) => t.point_no === p.point_no && poss.get(`${t.point_no}:${t.seq}`) === 1)
        const spike = first.some((t) => t.action === 'spike')
        const over = first.some((t) => t.action === 'overpass')
        const err = first.some((t) => t.outcome === 'error')
        out.reception.n++
        if (spike) out.reception.spike++
        else if (over) out.reception.overpass++
        else if (err) out.reception.error++
        else out.reception.none++
        if (first.some((t) => t.outcome === 'kill')) out.reception.first_ball_kills++
      }
    }
  }
  out.serve_out.to = [...to.values()].sort((a, b) => b.n - a.n || a.display_name.localeCompare(b.display_name))
  return {
    ...out,
    kill_rate: ratio(out.n_kills, out.n_attacks),
    attack_error_rate: ratio(out.n_attack_errors, out.n_attacks),
    ace_rate: ratio(out.n_aces, out.n_serves),
    serve_error_rate: ratio(out.n_serve_errors, out.n_serves),
  }
}

/** Per-point fantasy to a running total per slot (a chart's lines). */
export function cumulative(timeline: { point_no: number; slot: Slot; pts: number }[], nPoints: number):
  Record<Slot, number[]> {
  const out = { P1A: [0], P2A: [0], P1B: [0], P2B: [0] } as Record<Slot, number[]>
  const bySlot = new Map<string, number>()
  for (const t of timeline) bySlot.set(`${t.point_no}|${t.slot}`, t.pts)
  for (const slot of Object.keys(out) as Slot[]) {
    let sum = 0
    for (let p = 1; p <= nPoints; p++) {
      sum += bySlot.get(`${p}|${slot}`) ?? 0
      out[slot].push(Math.round(sum * 10) / 10)
    }
  }
  return out
}

/** The match MVP(s): the highest fantasy of the four. Ties share it. */
export function mvps(players: Pick<ReportPlayer, 'slot' | 'fantasy'>[]): Slot[] {
  if (!players.length) return []
  const best = Math.max(...players.map((p) => p.fantasy))
  return players.filter((p) => p.fantasy === best).map((p) => p.slot)
}

/** A player's best point of the match: the point where they scored most. */
export function bestPoint(timeline: { point_no: number; slot: Slot; pts: number }[], slot: Slot):
  { point_no: number; pts: number } | null {
  let best: { point_no: number; pts: number } | null = null
  for (const t of timeline) {
    if (t.slot === slot && t.pts > 0 && (best === null || t.pts > best.pts)) best = { point_no: t.point_no, pts: t.pts }
  }
  return best
}
