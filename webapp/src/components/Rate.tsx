import { MIN_N, pct, rangeText, rate, wilson } from '../lib/stats'
import type { Grade } from '../lib/grades'
import { Tile } from './ui'

/** A rate the honest way (H1): the count behind it always shows ("4/10"),
 * the percentage only from MIN_N attempts, and a 95 % range beside it. */
export function RateTile({ label, k, n, grade, hint }: {
  label: string; k: number; n: number; grade?: Grade; hint?: string
}) {
  const r = rate(k, n)
  const w = wilson(k, n)
  return (
    <Tile label={label} grade={grade} value={pct(r)} hint={hint}
          sub={r === null ? <>{k}/{n} · from {MIN_N}+</> : <>{k}/{n} · {rangeText(w)}</>} />
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
