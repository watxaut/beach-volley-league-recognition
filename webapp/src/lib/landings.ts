import type { Landing } from './types'

export type LandingKind = 'kill' | 'dug' | 'out' | 'net' | 'error' | 'unresolved'

export const LANDING_LABEL: Record<LandingKind, string> = {
  kill: 'Kill', dug: 'Dug', out: 'Out', net: 'Into the net', error: 'Error', unresolved: 'Unresolved',
}

/** What became of the attack. Matches published before `result` existed
 * only say kill / out; everything else there was a ball kept in play. */
export function landingKind(l: Landing): LandingKind {
  if (l.result) return l.result
  if (l.outcome === 'kill') return 'kill'
  if (l.result === undefined) return l.in === false ? 'out' : l.outcome === 'error' ? 'error' : 'dug'
  return 'unresolved'
}

/** Counts per kind (in display order, zeros dropped) and how many have no
 * spot on the map. */
export function landingSummary(landings: Landing[]): { counts: [LandingKind, number][]; unplaced: number } {
  const order: LandingKind[] = ['kill', 'dug', 'out', 'net', 'error', 'unresolved']
  const n = new Map<LandingKind, number>()
  for (const l of landings) n.set(landingKind(l), (n.get(landingKind(l)) ?? 0) + 1)
  return {
    counts: order.filter((k) => n.has(k)).map((k) => [k, n.get(k) as number]),
    unplaced: landings.filter((l) => l.x == null || l.y == null).length,
  }
}

/** "±0.4 m across, ±0.7 m along", or null when the error was not recorded. */
export function landingError(l: Landing): string | null {
  if (l.ex == null || l.ey == null) return null
  return `±${l.ex.toFixed(1)} m across, ±${l.ey.toFixed(1)} m along`
}
