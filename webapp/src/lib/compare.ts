// "How am I doing?" needs a reference: a player's numbers beside the rest of
// the league, or beside their own earlier matches. Everything here is counted
// from league-tier data (the leaderboard rows and a profile's match history),
// so a comparison never shows more about another player than the league table
// already does.
//
// Samples are small on both sides, so every gap is read twice: which way it
// goes (always shown), and whether chance alone could explain it. It is a
// CLEAR gap only when the player's 95 % range and the reference's 95 % range do
// not overlap; anything else is drawn pale, as "could be chance".
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
  serve_points?: number | null
  serve_won?: number | null
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
  /** Shown beside a tile of its own tab only, not in the overview list. */
  tabOnly?: boolean
}

const DEFS: Def[] = [
  { key: 'hitting', term: 'hitting', kind: 'hitting', better: 'high', unit: 'attacks', k: (s) => s.kills, n: (s) => s.attacks, e: (s) => s.attack_errors },
  { key: 'kill', term: 'kill_rate', kind: 'share', better: 'high', unit: 'attacks', k: (s) => s.kills, n: (s) => s.attacks },
  { key: 'attack_err', term: 'attack_errors', kind: 'share', better: 'low', unit: 'attacks', k: (s) => s.attack_errors, n: (s) => s.attacks, tabOnly: true },
  { key: 'ace', term: 'ace_rate', kind: 'share', better: 'high', unit: 'serves', k: (s) => s.aces, n: (s) => s.serves },
  { key: 'serve_err', term: 'serve_errors', kind: 'share', better: 'low', unit: 'serves', k: (s) => s.serve_errors, n: (s) => s.serves },
  { key: 'break_pt', term: 'break_point', kind: 'share', better: 'high', unit: 'points served', k: (s) => s.serve_won, n: (s) => s.serve_points, tabOnly: true },
  { key: 'side_out', term: 'side_out', kind: 'share', better: 'high', unit: 'points received', k: (s) => s.recv_won, n: (s) => s.recv_points },
  { key: 'digs', term: 'digs_21', kind: 'per21', better: 'high', unit: 'points', k: (s) => s.digs, n: (s) => s.points_played },
  { key: 'assists', term: 'assists_21', kind: 'per21', better: 'high', unit: 'points', k: (s) => s.assists, n: (s) => s.points_played },
  { key: 'errors', term: 'errors_21', kind: 'per21', better: 'low', unit: 'points', k: (s) => s.errors, n: (s) => s.points_played },
  // the total closes the list, after the skills it is made of
  { key: 'fantasy', term: 'fantasy_21', kind: 'fantasy', better: 'high', unit: 'points', k: (s) => s.fantasy, n: (s) => s.points_played },
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
  return rowsOf(DEFS.filter((d) => !d.tabOnly), you, others, minPeers)
}

/** Every stat with a league reference, by key: what a tab's tiles are read
 * against (the overview list, plus the stats that only a tab shows). */
export function compareByKey(you: Sample, others: Peer[], minPeers = MIN_PEERS): Record<string, CompareRow> {
  return Object.fromEntries(rowsOf(DEFS, you, others, minPeers).map((r) => [r.key, r]))
}

function rowsOf(defs: Def[], you: Sample, others: Peer[], minPeers: number): CompareRow[] {
  return defs.filter((d) => has(d, you)).map((d): CompareRow => {
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

/** A value in the units it is shown in, rounded as it is shown: 25 (%), 141
 * (thousandths of a hitting %), 94 (tenths). A gap is the difference of what
 * the reader sees: 25% against 22% is 3 points, never 2 or 4. */
function shown(kind: Kind, v: number): number {
  if (kind === 'share') return Number((v * 100).toFixed(0))
  if (kind === 'hitting') return Math.sign(v) * Math.round(Number(Math.abs(v).toFixed(3)) * 1000)
  return Math.round(Number(v.toFixed(1)) * 10)
}

export interface Gap {
  /** Where the player's number sits against the reference, as displayed. More
   * is `up` whatever the stat: whether that is good is `good`. */
  dir: 'up' | 'down' | 'level'
  /** The direction is the good one for this stat; null when level. */
  good: boolean | null
  /** The two 95 % ranges do not overlap: chance alone does not explain it. */
  clear: boolean
  /** How far towards a clear gap, 0..1 (1 = clear): what the strength of the
   * colour follows. Null where the stat has no chance range (fantasy). */
  sure: number | null
  /** The size as it reads, unsigned: "3 pts", ".118", "1.9". */
  size: string
}

/** The gap of a row to its reference; null while either side is missing. */
export function gapOf(r: CompareRow): Gap | null {
  if (r.value === null || r.ref === null) return null
  const d = shown(r.kind, r.value) - shown(r.kind, r.ref)
  const size = r.kind === 'share' ? `${Math.abs(d)} ${Math.abs(d) === 1 ? 'pt' : 'pts'}`
    : r.kind === 'hitting' ? hitText(Math.abs(d) / 1000) : (Math.abs(d) / 10).toFixed(1)
  if (d === 0) return { dir: 'level', good: null, clear: false, sure: r.range && r.refRange ? 0 : null, size }
  const clear = r.verdict === 'better' || r.verdict === 'worse'
  let sure: number | null = null
  if (r.range && r.refRange) {
    // the gap at which the two ranges stop overlapping, from this side
    const noise = r.value >= r.ref ? (r.refRange.hi - r.ref) + (r.value - r.range.lo) : (r.ref - r.refRange.lo) + (r.range.hi - r.value)
    sure = clear ? 1 : noise > 0 ? Math.min(1, Math.abs(r.value - r.ref) / noise) : 0
  }
  return { dir: d > 0 ? 'up' : 'down', good: (d > 0) === (r.better === 'high'), clear, sure, size }
}

/** The wash behind a gap, as a style: blue for better and orange for worse,
 * stronger the surer the gap is and strongest once clear. None when level,
 * and none where nothing says how sure the gap is (fantasy has no chance
 * range): there the arrow alone carries the direction. */
export function gapTint(g: Gap | null): { background: string } | undefined {
  if (!g || g.good === null || g.sure === null) return undefined
  const share = g.clear ? 40 : Math.round(5 + 19 * g.sure)
  return { background: `color-mix(in srgb, var(${g.good ? '--gap-better' : '--gap-worse'}) ${share}%, transparent)` }
}

/** The gap in words: "3 pts above", "9 pts fewer" where fewer is the good
 * direction, and what follows to name the reference (" league", " than league"). */
export function gapWords(r: Pick<CompareRow, 'better'>, g: Gap, ref: string): [string, string] {
  if (g.dir === 'level') return ['level', ` with ${ref}`]
  if (r.better === 'low') return [`${g.size} ${g.dir === 'up' ? 'more' : 'fewer'}`, ` than ${ref}`]
  return [`${g.size} ${g.dir === 'up' ? 'above' : 'below'}`, ` ${ref}`]
}

/** How many rows read better, worse and level against the reference. Fantasy
 * is the total of the others, so it is not counted with them. */
export function tally(rows: CompareRow[]): { better: number; worse: number; level: number; of: number } {
  const out = { better: 0, worse: 0, level: 0, of: 0 }
  for (const r of rows) {
    const g = r.kind === 'fantasy' ? null : gapOf(r)
    if (!g) continue
    out.of++
    if (g.good === null) out.level++
    else if (g.good) out.better++
    else out.worse++
  }
  return out
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
