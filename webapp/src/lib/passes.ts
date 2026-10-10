// Receptions and defenses: where the player played the ball and where it went
// next. The page never judges the pass against a fixed target: it shows where
// the balls fell and how tightly they cluster around their own usual spot.
import { MIN_N } from './stats'
import type { Pass } from './types'

export type PassKind = 'reception' | 'defense'

export const NET_Y = 8

export const PASS_LABEL: Record<PassKind, string> = { reception: 'Reception', defense: 'Defense' }
export const NEXT_LABEL: Record<NonNullable<Pass['to']>, string> = { set: 'a set', spike: 'an attack', overpass: 'a free ball' }

export interface Point {
  x: number
  y: number
}

/** One pass as the map draws it. A position past the net is drawn at it:
 * depth is the weak axis, and a ball cannot be played on the other side. */
export interface PassPoint {
  p: Pass
  kind: PassKind
  start: Point | null
  end: (Point & { atNet: boolean }) | null
}

export function passPoints(passes: Pass[]): PassPoint[] {
  return passes.map((p) => ({
    p,
    kind: p.k,
    start: p.sx == null || p.sy == null ? null : { x: p.sx, y: Math.min(p.sy, NET_Y) },
    end: p.x == null || p.y == null ? null : { x: p.x, y: Math.min(p.y, NET_Y), atNet: p.y > NET_Y },
  }))
}

/** Where the balls usually went: the middle of the destinations and how far
 * the typical one lies from it. `r` is the radius of the circle that holds
 * half of them. */
export interface Spot extends Point {
  r: number
  n: number
}

export function median(values: number[]): number {
  const v = [...values].sort((a, b) => a - b)
  const mid = v.length >> 1
  return v.length % 2 ? v[mid] : (v[mid - 1] + v[mid]) / 2
}

/** The usual spot of some destinations: the median across and along, and the
 * median distance from it. None below `min` balls: a handful cannot say where
 * a player usually puts the ball (same floor as every rate). */
export function usualSpot(points: Point[], min = MIN_N): Spot | null {
  if (points.length < min || points.length === 0) return null
  const x = median(points.map((q) => q.x))
  const y = median(points.map((q) => q.y))
  return { x, y, r: median(points.map((q) => Math.hypot(q.x - x, q.y - y))), n: points.length }
}

export interface PassSummary {
  kind: PassKind
  /** Credited passes of this kind. */
  n: number
  /** Of those, how many have a seen destination (the ones the spot is read from). */
  seen: number
  spot: Spot | null
}

export function summarize(points: PassPoint[], kind: PassKind): PassSummary {
  const of = points.filter((q) => q.kind === kind)
  const ends = of.flatMap((q) => (q.end ? [q.end] : []))
  return { kind, n: of.length, seen: ends.length, spot: usualSpot(ends) }
}

/** Metres from the net and from the player's left sideline, in words. */
export function spotWords(s: Spot): string {
  return `${Math.max(0, NET_Y - s.y).toFixed(1)} m off the net, ${s.x.toFixed(1)} m from the left sideline`
}
