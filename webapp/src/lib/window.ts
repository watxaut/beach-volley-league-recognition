// Time filters (brainstorm O4): every stat page can be cut by season, by the
// last N matches or by the last few days. The choice is one short string, kept
// in the URL (`?w=n5`) so a view can be shared; `windowParams` turns it into
// what the database functions take.
import type { WindowParams } from './types'

export const ALL_TIME: WindowParams = { season: null, from: null, to: null, lastN: null }

/** The fixed presets, in menu order; seasons are appended from the data. */
export const MATCH_PRESETS = [3, 5, 10]
export const DAY_PRESETS = [7, 30, 60]

/** Local calendar day as YYYY-MM-DD (a match date is a local day, not UTC). */
export function isoDay(d: Date): string {
  const mm = String(d.getMonth() + 1).padStart(2, '0')
  const dd = String(d.getDate()).padStart(2, '0')
  return `${d.getFullYear()}-${mm}-${dd}`
}

export function windowParams(key: string, today: Date = new Date()): WindowParams {
  const matches = /^n(\d+)$/.exec(key)
  if (matches) return { ...ALL_TIME, lastN: Number(matches[1]) }
  const days = /^d(\d+)$/.exec(key)
  if (days) {
    const from = new Date(today)
    from.setDate(from.getDate() - Number(days[1]))
    return { ...ALL_TIME, from: isoDay(from) }
  }
  if (key.startsWith('s:')) return { ...ALL_TIME, season: key.slice(2) }
  return ALL_TIME
}

export function windowLabel(key: string): string {
  const matches = /^n(\d+)$/.exec(key)
  if (matches) return Number(matches[1]) === 1 ? 'last match' : `last ${matches[1]} matches`
  const days = /^d(\d+)$/.exec(key)
  if (days) return `last ${days[1]} days`
  if (key.startsWith('s:')) return `season ${key.slice(2)}`
  return 'all time'
}

/** True when the key is one this module understands (a hand-edited URL is not). */
export function isWindowKey(key: string): boolean {
  return key === 'all' || /^(n|d)\d+$/.test(key) || key.startsWith('s:')
}
