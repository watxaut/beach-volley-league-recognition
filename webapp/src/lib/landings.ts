import type { Landing, ShotKey } from './types'

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

/** "±0.4 m across, ±0.7 m along", or null when the error was not recorded. */
export function landingError(l: Landing): string | null {
  if (l.ex == null || l.ey == null) return null
  return `±${l.ex.toFixed(1)} m across, ±${l.ey.toFixed(1)} m along`
}

const NET_Y = 8

export type ShotGroup = 'kill' | 'dug' | 'error' | 'other'
export type Phase = 'reception' | 'transition'

/** One attack as the map draws it: from where the ball was hit to where it
 * came down. Either end can be missing. */
export interface Shot {
  l: Landing
  kind: LandingKind
  /** The three outcomes a filter offers; out / net / error are all errors. */
  group: ShotGroup
  /** A hard or a touch spike, a free ball (overpass), or a spike the flight
   * read could not type. */
  shot: ShotKey
  phase: Phase | null
  start: { x: number; y: number } | null
  /** `short`: estimated on the attacker's side of the net, drawn at the net. */
  end: { x: number; y: number; short: boolean } | null
}

const GROUP: Record<LandingKind, ShotGroup> = {
  kill: 'kill', dug: 'dug', out: 'error', net: 'error', error: 'error', unresolved: 'other',
}

/** Depth is the weak axis, so a hit can read just past the net and a landing
 * just short of it. Neither is possible: both are drawn at the net. */
export function shots(landings: Landing[]): Shot[] {
  return landings.map((l) => {
    const kind = landingKind(l)
    const short = l.y != null && kind !== 'net' && l.y < NET_Y
    return {
      l, kind, group: GROUP[kind],
      shot: l.a === 'overpass' ? 'free' : l.type === 'hard' || l.type === 'touch' ? l.type : 'unread',
      phase: l.p == null ? null : l.p <= 1 ? 'reception' : 'transition',
      start: l.sx == null || l.sy == null ? null : { x: l.sx, y: Math.min(l.sy, NET_Y) },
      end: l.x == null || l.y == null ? null : { x: l.x, y: short ? NET_Y : l.y, short },
    }
  })
}
