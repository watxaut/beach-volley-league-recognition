// The fantasy game's rules in TypeScript: the demo mode's copy of the SQL
// (supabase/migrations/20261019100000_fantasy_game.sql) and the picker's
// instant check. The database decides; this only says the same thing sooner.
import type { FantasyLineup } from './types'

/** The price of a player with no published match yet. */
export const NO_HISTORY_PRICE = 7.5

/** One published match of a player, for the price: their fantasy and the match's points. */
export interface PriceSample {
  fantasy: number
  n_points: number
}

/** SQL `fantasy_suggested_prices`: 5.0 + 5.0 x the player's percentile of
 * fantasy per 21 over their last 10 published matches (newest first), to 0.5.
 * A player without a measurable match is absent (they cost NO_HISTORY_PRICE). */
export function suggestedPrices(history: Map<number, PriceSample[]>): Map<number, number> {
  const per21 = new Map<number, number>()
  for (const [player, samples] of history) {
    const recent = samples.slice(0, 10)
    const points = recent.reduce((t, s) => t + s.n_points, 0)
    if (points > 0) per21.set(player, (recent.reduce((t, s) => t + s.fantasy, 0) / points) * 21)
  }
  const values = [...per21.values()]
  const out = new Map<number, number>()
  for (const [player, v] of per21) {
    // percent_rank(): the share of the others strictly below
    const rank = values.length > 1 ? values.filter((x) => x < v).length / (values.length - 1) : 0
    out.set(player, Math.round((5 + 5 * rank) * 2) / 2)
  }
  return out
}

/** SQL `save_lineup`'s checks, in its order; null when the lineup can be saved.
 * `price` is undefined for a player who does not play the day. */
export function lineupProblem(rules: { squad_size: number; budget: number }, picks: number[],
                              captain: number | null, price: (playerId: number) => number | undefined): string | null {
  if (new Set(picks).size !== picks.length) return 'pick each player only once'
  if (picks.length !== rules.squad_size) return `pick exactly ${rules.squad_size} players`
  if (picks.some((p) => price(p) === undefined)) return 'a picked player does not play this match day'
  if (captain === null || !picks.includes(captain)) return 'the captain must be one of your picks'
  const cost = lineupCost(picks, price)
  if (cost > rules.budget) return `over budget: ${cost} of ${rules.budget}`
  return null
}

export function lineupCost(picks: number[], price: (playerId: number) => number | undefined): number {
  return Math.round(picks.reduce((t, p) => t + (price(p) ?? 0), 0) * 10) / 10
}

/** SQL `fantasy_lineup_scores`: the picks' points, the captain's x multiplier. */
export function lineupPoints(lineup: FantasyLineup, multiplier: number,
                             points: (playerId: number) => number | null | undefined): number {
  const total = lineup.player_ids.reduce(
    (t, p) => t + (points(p) ?? 0) * (p === lineup.captain ? multiplier : 1), 0)
  return Math.round(total * 10) / 10
}

/** SQL rank() over a descending order: ties share a rank, the next skips. */
export function competitionRank(values: number[]): number[] {
  return values.map((v) => 1 + values.filter((x) => x > v).length)
}

/** SQL `fantasy_locks_at`: the day's first scheduled match. A fixture
 * cancelled after its time still counts, so a lock never comes undone. */
export function locksAt(fixtures: { scheduled_at: string; cancelled: boolean }[], now: Date): string | null {
  const times = fixtures
    .filter((f) => !f.cancelled || new Date(f.scheduled_at) <= now)
    .map((f) => f.scheduled_at)
    .sort((a, b) => new Date(a).getTime() - new Date(b).getTime())
  return times[0] ?? null
}

/** SQL `fantasy_day_state`: locked = open and past its first match; final =
 * locked, one fixture published to fantasy and none still waiting. */
export function dayState(status: 'draft' | 'open',
                         fixtures: { scheduled_at: string; cancelled: boolean; fantasy_published: boolean }[],
                         now: Date): { locks_at: string | null; locked: boolean; final: boolean } {
  const lock = locksAt(fixtures, now)
  const locked = status === 'open' && lock !== null && new Date(lock) <= now
  const final = locked && fixtures.some((f) => f.fantasy_published)
    && !fixtures.some((f) => !f.cancelled && !f.fantasy_published)
  return { locks_at: lock, locked, final }
}

/** One locked day of the season table: when it locked, whether it is final, every lineup's points. */
export interface DayScores {
  locks_at: string
  final: boolean
  scores: { manager: string; points: number }[]
}

/** SQL `fantasy_standings`: the sum over locked days; a final day's top score
 * (ties included) is a win; the table breaks ties on wins. */
export function standings(days: DayScores[]): { manager: string; total: number; days_played: number;
                                               day_wins: number; last_points: number | null; rank: number }[] {
  const rows = new Map<string, { total: number; days_played: number; day_wins: number; last: [string, number] | null }>()
  for (const d of days) {
    const top = Math.max(...d.scores.map((s) => s.points))
    for (const s of d.scores) {
      const r = rows.get(s.manager) ?? { total: 0, days_played: 0, day_wins: 0, last: null }
      r.total = Math.round((r.total + s.points) * 10) / 10
      r.days_played++
      if (d.final && s.points === top) r.day_wins++
      if (!r.last || d.locks_at > r.last[0]) r.last = [d.locks_at, s.points]
      rows.set(s.manager, r)
    }
  }
  const list = [...rows].map(([manager, r]) => ({
    manager, total: r.total, days_played: r.days_played, day_wins: r.day_wins, last_points: r.last?.[1] ?? null }))
  // rank() over (total desc, day_wins desc)
  const key = (r: { total: number; day_wins: number }) => r.total * 1e4 + r.day_wins
  const ranks = competitionRank(list.map(key))
  return list.map((r, i) => ({ ...r, rank: ranks[i] }))
    .sort((a, b) => a.rank - b.rank || a.manager.localeCompare(b.manager))
}

/** The local calendar date of a timestamp, as `YYYY-MM-DD` (a match's `match_date`). */
export function localDate(iso: string): string {
  const d = new Date(iso)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

/** A timestamp as the value of an `<input type="datetime-local">`, and back. */
export function toLocalInput(iso: string): string {
  const d = new Date(iso)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${localDate(iso)}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}
export function fromLocalInput(value: string): string {
  return new Date(value).toISOString()
}

/** "in 2 days", "in 3 h", "in 12 min" until a lock (null once it passed). */
export function untilText(iso: string, now: Date): string | null {
  const ms = new Date(iso).getTime() - now.getTime()
  if (ms <= 0) return null
  const min = Math.round(ms / 60000)
  if (min < 60) return `in ${min} min`
  const h = Math.round(min / 60)
  if (h < 48) return `in ${h} h`
  return `in ${Math.round(h / 24)} days`
}

/** A timestamp as a short local date and time: "Sat 25 Oct, 10:00". */
export function dateTime(iso: string): string {
  const d = new Date(iso)
  return `${d.toLocaleDateString(undefined, { weekday: 'short', day: 'numeric', month: 'short' })}, ` +
    d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' })
}
