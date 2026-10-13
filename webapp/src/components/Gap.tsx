// A gap to a reference, the way every page shows it: an arrow for which way
// the number goes (more is up, whatever the stat), the colour for whether that
// is good (blue) or bad (orange), and the strength of the colour for how sure
// it is. Pale = chance alone could explain it; strong = a clear gap.
import { gapOf, gapTint, gapWords, type CompareRow, type Gap } from '../lib/compare'

const ARROW: Record<Gap['dir'], string> = { up: '▲', down: '▼', level: '≈' }

export function GapArrow({ g }: { g: Gap }) {
  return <span className={`gap-arrow ${g.good === null ? 'gap-level' : g.good ? 'gap-good' : 'gap-bad'}`} aria-hidden="true">{ARROW[g.dir]}</span>
}

/** The line under a tile: where the number sits against the league. Nothing
 * while either side is missing (too few attempts, or no league average yet). */
export function GapNote({ row, refName = 'league' }: { row: CompareRow | undefined; refName?: string }) {
  const g = row ? gapOf(row) : null
  if (!row || !g) return null
  const [words, tail] = gapWords(row, g, refName)
  return (
    <div className={`gap-note${g.clear ? ' gap-clear' : ''}`} style={gapTint(g)}>
      <GapArrow g={g} /> {words}<span className="gap-ref">{tail}</span>{g.clear && <span className="gap-tag">clear</span>}
    </div>
  )
}
