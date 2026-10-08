// "How am I doing?" needs a reference: a player's numbers beside the rest of
// the league, or beside their own earlier matches. Everything here is counted
// from league-tier data (the leaderboard rows and a profile's match history),
// so a comparison never shows more about another player than the league table
// already does.
//
// Samples are small on both sides, so a gap is called only when the player's
// 95 % range and the reference's 95 % range do not overlap; anything else reads
// "similar".
import { signed } from './format'
import type { TermKey } from './glossary'
import { hitText, hittingRange, MIN_N, pct, poissonRange, rangeText, wilson, type Range } from './stats'
import type { HistoryRow } from './types'

/** One player's numbers over a set of matches: a leaderboard row, a profile's
 * totals, or a sum of history rows. The optional fields are missing on a
 * database older than the player_page_v2 migration. */
export interface Sample {
  fantasy: number
  kills: number
  attacks: number
  attack_errors: number
  aces: number
  serves: number
  digs: number
  assists: number
  errors: number
  points_played: number
  serve_errors?: number | null
  recv_points?: number | null
  recv_won?: number | null
}

/** Other players needed before "the league" is a reference. */
export const MIN_PEERS = 3
/** Points played before a per-21 number is shown: one set. */
export const MIN_POINTS = 21
/** Matches that count as "now" when no time filter is set (as Form does). */
export const RECENT = 5

export type Kind = 'share' | 'hitting' | 'per21' | 'fantasy'
export type Verdict = 'better' | 'same' | 'worse'

interface Def {
  key: string
  term: TermKey
  kind: Kind
  better: 'high' | 'low'
  /** What an attempt is called: "needs 10 attacks". */
  unit: string
  k: (s: Sample) => number | null | undefined
  n: (s: Sample) => number | null | undefined
  /** Errors, for hitting %. */
  e?: (s: Sample) => number
}

const DEFS: Def[] = [
  { key: 'fantasy', term: 'fantasy_21', kind: 'fantasy', better: 'high', unit: 'points', k: (s) => s.fantasy, n: (s) => s.points_played },
  { key: 'hitting', term: 'hitting', kind: 'hitting', better: 'high', unit: 'attacks', k: (s) => s.kills, n: (s) => s.attacks, e: (s) => s.attack_errors },
  { key: 'kill', term: 'kill_rate', kind: 'share', better: 'high', unit: 'attacks', k: (s) => s.kills, n: (s) => s.attacks },
  { key: 'ace', term: 'ace_rate', kind: 'share', better: 'high', unit: 'serves', k: (s) => s.aces, n: (s) => s.serves },
  { key: 'serve_err', term: 'serve_errors', kind: 'share', better: 'low', unit: 'serves', k: (s) => s.serve_errors, n: (s) => s.serves },
  { key: 'side_out', term: 'side_out', kind: 'share', better: 'high', unit: 'points received', k: (s) => s.recv_won, n: (s) => s.recv_points },
  { key: 'digs', term: 'digs_21', kind: 'per21', better: 'high', unit: 'points', k: (s) => s.digs, n: (s) => s.points_played },
  { key: 'assists', term: 'assists_21', kind: 'per21', better: 'high', unit: 'points', k: (s) => s.assists, n: (s) => s.points_played },
  { key: 'errors', term: 'errors_21', kind: 'per21', better: 'low', unit: 'points', k: (s) => s.errors, n: (s) => s.points_played },
]

const minOf = (kind: Kind) => (kind === 'share' || kind === 'hitting' ? MIN_N : MIN_POINTS)

interface Measured {
  k: number
  n: number
  e: number
  value: number | null
  range: Range | null
}

/** A stat of one sample: the value from the minimum on, with its 95 % range. */
function measure(d: Def, k: number, n: number, e: number): Measured {
  if (n < minOf(d.kind) || n <= 0) return { k, n, e, value: null, range: null }
  switch (d.kind) {
    case 'share': return { k, n, e, value: k / n, range: wilson(k, n) }
    case 'hitting': return { k, n, e, value: (k - e) / n, range: hittingRange({ n, kills: k, errors: e }) }
    case 'per21': {
      const r = poissonRange(k)
      return { k, n, e, value: (k / n) * 21, range: { lo: (r.lo / n) * 21, hi: (r.hi / n) * 21 } }
    }
    case 'fantasy': return { k, n, e, value: (k / n) * 21, range: null }
  }
}

const has = (d: Def, s: Sample) => d.k(s) != null && d.n(s) != null

export interface Peer {
  id: number
  name: string
  sample: Sample
}

export interface CompareRow extends Measured {
  key: string
  term: TermKey
  kind: Kind
  better: 'high' | 'low'
  unit: string
  /** Fewest attempts before the value shows. */
  min: number
  /** The reference: the others' pooled rate (sum of counts / sum of attempts). */
  ref: number | null
  /** The reference is a sample too: one earlier match is far less certain
   * than a whole league. */
  refRange: Range | null
  refK: number
  refN: number
  /** The other players that have enough attempts of their own. */
  peers: { id: number; name: string; value: number }[]
  verdict: Verdict | null
  /** Fantasy has no chance range, so it is ranked instead. */
  rank: { pos: number; of: number } | null
}

/** One row per stat both sides have. `others` are the players (or the single
 * earlier period) the reference is pooled from; the reference shows from
 * `minPeers` of them with any attempt and a pooled count above the minimum.
 * Fantasy is ranked among players, so not against a single earlier period. */
export function compare(you: Sample, others: Peer[], minPeers = MIN_PEERS): CompareRow[] {
  return DEFS.filter((d) => has(d, you)).map((d): CompareRow => {
    const mine = measure(d, d.k(you) as number, d.n(you) as number, d.e?.(you) ?? 0)
    const usable = others.filter((o) => has(d, o.sample) && (d.n(o.sample) as number) > 0)
    const sum = (f: (s: Sample) => number) => usable.reduce((t, o) => t + f(o.sample), 0)
    const pooled = measure(d, sum((s) => d.k(s) as number), sum((s) => d.n(s) as number), sum((s) => d.e?.(s) ?? 0))
    const ref = usable.length >= minPeers ? pooled.value : null
    const peers = usable.flatMap((o) => {
      const m = measure(d, d.k(o.sample) as number, d.n(o.sample) as number, d.e?.(o.sample) ?? 0)
      return m.value === null ? [] : [{ id: o.id, name: o.name, value: m.value }]
    })
    const sign = d.better === 'high' ? 1 : -1
    let verdict: Verdict | null = null
    const refRange = ref === null ? null : pooled.range
    if (mine.range && refRange) {
      verdict = mine.range.lo > refRange.hi ? (sign > 0 ? 'better' : 'worse')
        : mine.range.hi < refRange.lo ? (sign > 0 ? 'worse' : 'better') : 'same'
    }
    const rank = d.kind === 'fantasy' && mine.value !== null && ref !== null && minPeers > 1
      ? { pos: 1 + peers.filter((p) => sign * (p.value - (mine.value as number)) > 0).length, of: peers.length + 1 }
      : null
    return {
      ...mine, key: d.key, term: d.term, kind: d.kind, better: d.better, unit: d.unit, min: minOf(d.kind),
      ref, refRange, refK: pooled.k, refN: pooled.n, peers, verdict, rank,
    }
  })
}

/** The clearest strength and the clearest weakness, if any gap is clear:
 * the rows whose range sits furthest from the reference. */
export function highlights(rows: CompareRow[]): { best: CompareRow | null; worst: CompareRow | null } {
  const gap = (r: CompareRow) => {
    const half = r.range ? (r.range.hi - r.range.lo) / 2 : 0
    return half > 0 && r.value !== null && r.ref !== null ? Math.abs(r.value - r.ref) / half : 0
  }
  const top = (v: Verdict) => rows.filter((r) => r.verdict === v).sort((a, b) => gap(b) - gap(a))[0] ?? null
  return { best: top('better'), worst: top('worse') }
}

/** Where a value sits on a row's strip, 0..100 from the left, with BETTER to
 * the right whatever the stat. The scale spans everything the row draws. */
export function stripScale(r: CompareRow): ((v: number) => number) | null {
  const all = [r.value, r.ref, r.range?.lo, r.range?.hi, r.refRange?.lo, r.refRange?.hi, ...r.peers.map((p) => p.value)]
    .filter((v): v is number => v != null)
  if (all.length === 0) return null
  const lo = Math.min(...all)
  const hi = Math.max(...all)
  const pad = 6
  return (v) => {
    const t = hi === lo ? 0.5 : (Math.min(Math.max(v, lo), hi) - lo) / (hi - lo)
    return pad + (r.better === 'high' ? t : 1 - t) * (100 - 2 * pad)
  }
}

/** A value the way its stat reads: "13%", ".250", "8.9", "+6.4". */
export function valueText(kind: Kind, v: number | null): string {
  if (v === null) return '–'
  switch (kind) {
    case 'share': return pct(v)
    case 'hitting': return hitText(v)
    case 'per21': return v.toFixed(1)
    case 'fantasy': return signed(v)
  }
}

/** A 95 % range in the units of its stat. */
export function rangeTextOf(kind: Kind, r: Range | null): string | null {
  if (!r) return null
  if (kind === 'share') return rangeText(r)
  if (kind === 'hitting') return `${hitText(r.lo)} to ${hitText(r.hi)}`
  return `${r.lo.toFixed(1)}–${r.hi.toFixed(1)}`
}

/** "1st", "2nd", "3rd", "11th". */
export function ordinal(n: number): string {
  const tens = n % 100
  const end = tens >= 11 && tens <= 13 ? 'th' : ['th', 'st', 'nd', 'rd'][n % 10] ?? 'th'
  return `${n}${end}`
}

/** The count behind a rate: "2/16", "(2−4)/16". A per-21 number has none. */
export function countText(r: Pick<CompareRow, 'kind' | 'k' | 'n' | 'e'>): string | null {
  if (r.kind === 'share') return `${r.k}/${r.n}`
  if (r.kind === 'hitting') return `(${r.k}−${r.e})/${r.n}`
  return null
}

/** Match rows (a profile's history) summed into one sample. */
export function sumHistory(rows: HistoryRow[]): Sample {
  const sum = (f: (h: HistoryRow) => number | null) => rows.reduce((t, h) => t + (f(h) ?? 0), 0)
  return {
    fantasy: Math.round(sum((h) => h.fantasy) * 10) / 10, kills: sum((h) => h.kills), attacks: sum((h) => h.attacks),
    attack_errors: sum((h) => h.attack_errors), aces: sum((h) => h.aces), serves: sum((h) => h.serves),
    digs: sum((h) => h.digs), assists: sum((h) => h.assists), errors: sum((h) => h.errors),
    points_played: sum((h) => h.n_points), serve_errors: sum((h) => h.serve_errors),
  }
}

/** A player's matches cut into "now" and "before". `all` is the whole history,
 * newest first. With a time filter, now = its matches and before = everything
 * older than them; without one, now = the newest `recent` matches. */
export function splitEarlier(all: HistoryRow[], windowIds: number[] | null, recent = RECENT):
  { now: HistoryRow[]; before: HistoryRow[] } {
  if (windowIds === null) return { now: all.slice(0, recent), before: all.slice(recent) }
  const keep = new Set(windowIds)
  const last = all.reduce((at, h, i) => (keep.has(h.match_id) ? i : at), -1)
  return { now: all.filter((h) => keep.has(h.match_id)), before: last < 0 ? [] : all.slice(last + 1) }
}
