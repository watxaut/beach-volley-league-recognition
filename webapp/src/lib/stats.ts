// Honest rates (brainstorm H1). Samples are small -- 5-14 serves, 7-13 spikes
// per player per match -- so a rate is never shown without the count behind
// it, is hidden below a minimum, and carries a 95 % Wilson range. Trends are
// drawn over rolling windows of attempts, not one dot per match.
import type { Tally } from './types'

/** Fewest attempts before a rate is shown or ranked. */
export const MIN_N = 10
/** Attempts in one point of a rolling trend. */
export const ROLLING_WINDOW = 30

export interface Range {
  lo: number
  hi: number
}

/** 95 % Wilson score interval of k successes in n tries (n > 0). Behaves at 0
 * and n (no 0-width interval), unlike the textbook normal approximation. */
export function wilson(k: number, n: number, z = 1.96): Range | null {
  if (n <= 0) return null
  const p = k / n
  const z2 = z * z
  const denom = 1 + z2 / n
  const centre = (p + z2 / (2 * n)) / denom
  const half = (z * Math.sqrt((p * (1 - p)) / n + z2 / (4 * n * n))) / denom
  return { lo: Math.max(0, centre - half), hi: Math.min(1, centre + half) }
}

/** k / n, or null when there are fewer than `min` attempts. */
export function rate(k: number, n: number, min = MIN_N): number | null {
  return n >= min && n > 0 ? k / n : null
}

/** Hitting percentage: (kills - errors) / attempts, the standard attack
 * efficiency. Not a proportion, so it has no Wilson range. */
export function hitting(t: Tally, min = MIN_N): number | null {
  return t.n >= min && t.n > 0 ? (t.kills - t.errors) / t.n : null
}

export function pct(x: number | null | undefined, digits = 0): string {
  return x == null ? '–' : `${(x * 100).toFixed(digits)}%`
}

/** Hitting percentage reads like a batting average: ".250", "-.100". */
export function hitText(x: number | null | undefined): string {
  if (x == null) return '–'
  const s = Math.abs(x).toFixed(3).replace(/^0/, '')
  return x < 0 ? `−${s}` : s
}

/** "17–69%" */
export function rangeText(r: Range | null): string {
  return r ? `${Math.round(r.lo * 100)}–${Math.round(r.hi * 100)}%` : '–'
}

export interface RollingPoint {
  /** 1-based index of the attempt the window ends on. */
  end: number
  k: number
  n: number
  rate: number
  lo: number
  hi: number
}

/** Rate over the last `window` attempts, after every attempt from the
 * `window`-th on. Empty until there are `window` attempts. */
export function rolling(hits: boolean[], window = ROLLING_WINDOW): RollingPoint[] {
  const out: RollingPoint[] = []
  if (window <= 0 || hits.length < window) return out
  let k = 0
  for (let i = 0; i < hits.length; i++) {
    k += hits[i] ? 1 : 0
    if (i >= window) k -= hits[i - window] ? 1 : 0
    if (i >= window - 1) {
      const r = wilson(k, window) as Range
      out.push({ end: i + 1, k, n: window, rate: k / window, lo: r.lo, hi: r.hi })
    }
  }
  return out
}

/** Sort key that puts "not enough attempts" last in either direction. */
export function rankValue(x: number | null, descending = true): number {
  return x ?? (descending ? Number.NEGATIVE_INFINITY : Number.POSITIVE_INFINITY)
}
