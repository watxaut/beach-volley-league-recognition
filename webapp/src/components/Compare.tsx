// A player beside a reference (everyone else pooled, everyone else in the same
// match type, or the player's own earlier matches), one row per stat: the two numbers side by side and the gap
// between them. The arrow says which way the number goes (more is up on every
// row, a stat where fewer is better says so); the colour says whether that is
// good or bad, and its strength how sure the gap is: pale while chance alone
// could explain it, strong once the two 95 % ranges no longer overlap.
import {
  countText, gapOf, gapTint, gapWords, highlights, ordinal, rangeTextOf, tally, valueText, type CompareRow, type Gap,
} from '../lib/compare'
import { GLOSSARY } from '../lib/glossary'
import { GapArrow } from './Gap'
import { StatInfo } from './ui'

export type CompareMode = 'league' | 'type' | 'earlier'

/** A row named in a sentence: "kill %", "digs", and "few errors" where fewer
 * is the good direction. */
function plain(r: CompareRow, good: boolean): string {
  const name = GLOSSARY[r.term].label.replace(' / 21 pts', '').toLowerCase()
  return good && r.better === 'low' ? `few ${name}` : name
}

function spoken(r: CompareRow, g: Gap | null, who: string, refName: string): string {
  const label = GLOSSARY[r.term].label
  if (r.value === null) return `${label}: ${who} not enough ${r.unit} yet`
  const head = `${label}: ${who} ${valueText(r.kind, r.value)}`
  if (!g) return head
  const ref = `${refName} ${valueText(r.kind, r.ref)}`
  if (g.good === null) return `${head}, ${ref}, level`
  return `${head}, ${ref}, ${g.size} ${g.dir === 'up' ? 'higher' : 'lower'}, ${g.good ? 'better' : 'worse'}`
    + (g.clear ? ', a clear gap' : g.sure === null ? '' : ', could be chance')
}

function GapCell({ r, g }: { r: CompareRow; g: Gap | null }) {
  if (!g) return null
  return (
    <>
      <GapArrow g={g} /> {gapWords(r, g, '')[0]}
      {g.clear && <span className="gap-tag">clear</span>}
      {r.rank && <span className="muted"> · {ordinal(r.rank.pos)} of {r.rank.of}</span>}
    </>
  )
}

export function Compare({ rows, mode, who, refName, against }: {
  rows: CompareRow[]
  mode: CompareMode
  /** "You", or the player's name on someone else's page. */
  who: string
  /** What the player is read against, in a column heading: "League", "Mixed", "Before". */
  refName: string
  /** The same in a sentence: "Better than {against} on 3 of 7". */
  against: string
}) {
  const { best, worst } = highlights(rows)
  const sum = tally(rows)
  const anyRef = rows.some((r) => r.ref !== null)
  const anyPeers = mode !== 'earlier' && rows.some((r) => r.peers.length > 0)
  // one real row says what "by chance" means: 3 in 18 attacks is anywhere from 6% to 39%
  const example = rows.find((r) => r.key === 'kill' && r.value !== null && r.range) ?? rows.find((r) => r.kind === 'share' && r.value !== null && r.range)
  return (
    <div>
      {sum.of > 0 && (
        <p className="cmp-sum">
          <span><span className="key key-better" aria-hidden="true" /><strong>Better</strong> than {against} on <strong>{sum.better}</strong> of {sum.of}</span>
          <span><span className="key key-worse" aria-hidden="true" /><strong>Worse</strong> on <strong>{sum.worse}</strong></span>
          {sum.level > 0 && <span className="muted">level on {sum.level}</span>}
          {best && <span className="muted">Clear strength: <strong>{plain(best, true)}</strong></span>}
          {worst && <span className="muted">Clear gap to close: <strong>{plain(worst, false)}</strong></span>}
        </p>
      )}
      <div className="cmp-head" aria-hidden="true">
        <span />
        <span className="cmp-head-num">{who}</span>
        <span className="cmp-head-num">{anyRef && refName}</span>
        <span>{anyRef && `vs ${refName.toLowerCase()}`}</span>
      </div>
      <div className="cmp" role="list">
        {rows.map((r) => {
          const g = gapOf(r)
          return (
            <div key={r.key} className={`cmp-row${r.kind === 'fantasy' ? ' cmp-total' : ''}${g?.clear ? ' cmp-clear' : ''}`}
                 role="listitem" aria-label={spoken(r, g, who, refName)} style={gapTint(g)}>
              <div className="cmp-label">
                <span>
                  {GLOSSARY[r.term].label}<StatInfo term={r.term} />
                  {r.better === 'low' && <span className="cmp-low">fewer is better</span>}
                </span>
                <span className="cmp-count">{r.value === null ? `needs ${r.min} ${r.unit}` : countText(r)}</span>
              </div>
              <div className="cmp-value">{r.value === null ? countText(r) ?? '–' : valueText(r.kind, r.value)}</div>
              <div className="cmp-ref">{anyRef && valueText(r.kind, r.ref)}</div>
              <div className="cmp-gap"><GapCell r={r} g={g} /></div>
            </div>
          )
        })}
      </div>
      {anyRef && (
        <div className="legend">
          <span><span className="key key-better key-pale" aria-hidden="true" /><span className="key key-better" aria-hidden="true" />Better</span>
          <span><span className="key key-worse key-pale" aria-hidden="true" /><span className="key key-worse" aria-hidden="true" />Worse</span>
          <span>Pale: could be chance · strong: a clear gap</span>
        </div>
      )}
      {anyRef && example && example.value !== null && example.range && (
        <p className="cmp-explain">
          Could be chance: {example.k} in {example.n} {example.unit} reads {valueText(example.kind, example.value)}, but the real level
          could be anywhere from {valueText(example.kind, example.range.lo)} to {valueText(example.kind, example.range.hi)}. A gap is
          clear once it is larger than that on both sides.
        </p>
      )}
      <details className="table-view">
        <summary>Ranges{anyPeers && ' and other players'}</summary>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th className="left">Stat</th><th>{who}</th><th>Count</th><th>Likely range</th><th>{refName}</th>
                {anyPeers && <th className="left">Other players</th>}
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.key}>
                  <td className="left">{GLOSSARY[r.term].label}</td>
                  <td>{valueText(r.kind, r.value)}</td>
                  <td>{countText(r) ?? `${r.k} in ${r.n} pts`}</td>
                  <td>{rangeTextOf(r.kind, r.range) ?? '–'}</td>
                  <td>{valueText(r.kind, r.ref)}</td>
                  {anyPeers && (
                    <td className="left">{r.peers.map((p) => `${p.name} ${valueText(r.kind, p.value)}`).join(' · ') || '–'}</td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </div>
  )
}
