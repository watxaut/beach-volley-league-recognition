import type { TermKey } from '../lib/glossary'
import { hitText, hitting, hittingRange, MIN_N, pct, rangeText, rate, wilson } from '../lib/stats'
import type { Tally } from '../lib/types'
import { StatInfo, Tile } from './ui'

/** A rate the honest way (H1): the count behind it always shows ("4/10") and
 * the percentage only from MIN_N attempts. Below that the count IS the value.
 * The 95 % range lives in the hint, not on the tile. */
export function RateTile({ label, k, n, term, unit, note }: {
  label: string; k: number; n: number; term: TermKey; unit: string; note?: string
}) {
  const r = rate(k, n)
  const w = wilson(k, n)
  return (
    <Tile label={label} quiet={r === null} value={r === null ? `${k}/${n}` : pct(r)}
          sub={r === null ? `needs ${MIN_N} ${unit}` : `${k}/${n}`}
          info={<StatInfo term={term}>{r !== null && <>95% range {rangeText(w)}. </>}{note}</StatInfo>} />
  )
}

/** Hitting % as a tile: ".250" from MIN_N attacks, "(K−E)/n" always. */
export function HittingTile({ t }: { t: Tally }) {
  const h = hitting(t)
  const w = hittingRange(t)
  const count = `(${t.kills}−${t.errors})/${t.n}`
  return (
    <Tile label="Hitting %" quiet={h === null} value={h === null ? count : hitText(h)}
          sub={h === null ? `needs ${MIN_N} attacks` : count}
          info={<StatInfo term="hitting">{h !== null && w && <>95% range {hitText(w.lo)} to {hitText(w.hi)}, roughly.</>}</StatInfo>} />
  )
}

/** "8/13 (62%)" for a table cell: the percentage only from MIN_N attempts. */
export function Ratio({ k, n, min = MIN_N }: { k: number; n: number; min?: number }) {
  const r = rate(k, n, min)
  const w = wilson(k, n)
  return (
    <span title={n > 0 ? `95% range ${rangeText(w)}` : undefined}>
      {k}/{n}{r !== null && <span className="muted"> ({pct(r)})</span>}
    </span>
  )
}
