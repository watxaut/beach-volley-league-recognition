import type { Match, Participant, Player, Slot, Team } from './types'

export function formatDate(isoDate: string, time?: string | null): string {
  const d = new Date(`${isoDate}T${time ?? '12:00:00'}`)
  const day = d.toLocaleDateString(undefined, { weekday: 'short', day: 'numeric', month: 'short', year: 'numeric' })
  return time ? `${day}, ${time.slice(0, 5)}` : day
}

export function matchLabel(m: Pick<Match, 'title' | 'venue' | 'match_key'>): string {
  if (m.title) return m.title
  if (m.venue) return m.venue
  // 20261004_1805_vall_dhebron -> "vall dhebron"
  return m.match_key.split('_').slice(2).join(' ')
}

/** How a slot reads on screen: the player, "Unknown (P1B)" for someone the
 * admin marked as outside the league, or "P1B (unassigned)" while undecided. */
export function slotLabel(p: Pick<Participant, 'slot' | 'player_id' | 'is_unknown'>, players: Player[]): string {
  if (p.is_unknown) return `Unknown (${p.slot})`
  return players.find((x) => x.id === p.player_id)?.display_name ?? `${p.slot} (unassigned)`
}

/** Display name per DECIDED slot (a player or unknown); an undecided slot is
 * left out so callers fall back to the bare slot code. */
export function slotNames(parts: Participant[], players: Player[]): Partial<Record<Slot, string>> {
  const names: Partial<Record<Slot, string>> = {}
  for (const p of parts) {
    if (p.is_unknown || players.some((x) => x.id === p.player_id)) names[p.slot] = slotLabel(p, players)
  }
  return names
}

export function teamPlayers(team: Team, parts: Participant[], players: Player[]): string[] {
  return parts
    .filter((p) => p.team === team)
    .sort((a, b) => a.slot.localeCompare(b.slot))
    .map((p) => slotLabel(p, players))
}

export function teamName(team: Team, parts: Participant[], players: Player[]): string {
  const names = teamPlayers(team, parts, players)
  return names.length ? names.join(' & ') : `Team ${team}`
}

export function pct(x: number | null | undefined): string {
  return x === null || x === undefined ? '–' : `${Math.round(x * 100)}%`
}

export function signed(n: number): string {
  const r = Math.round(n * 10) / 10
  return r > 0 ? `+${r}` : r < 0 ? `−${Math.abs(r)}` : '0'
}

export function minutes(seconds: number | null | undefined): string {
  return seconds ? `${Math.round(seconds / 60)} min` : '–'
}

export const ACTION_LABEL: Record<string, string> = {
  serve: 'Serve', dig: 'Dig', set: 'Set', spike: 'Spike', overpass: 'Over', block: 'Block',
  ball_handling: 'Handling',
}

export const OUTCOME_LABEL: Record<string, string> = { ace: 'ACE', kill: 'KILL', error: 'ERROR' }
