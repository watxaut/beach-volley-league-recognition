// A player beside a reference, one strip per stat. Better is to the right on
// every row. The dot is the player and the bar through it their 95 % range;
// the tall tick is the reference (everyone else pooled, or the player's own
// earlier matches) on its own, greyer range; the short ticks are the other
// players. A verdict shows only where the two ranges do not overlap.
import { useState } from 'react'
import {
  countText, highlights, ordinal, rangeTextOf, stripScale, valueText, type CompareRow, type Verdict,
} from '../lib/compare'
import { signed } from '../lib/format'
import { GLOSSARY } from '../lib/glossary'
import { StatInfo } from './ui'

export type CompareMode = 'league' | 'earlier'

const WORDS: Record<CompareMode, Record<Verdict, string>> = {
  league: { better: 'Better', same: 'Similar', worse: 'Worse' },
  earlier: { better: 'Improved', same: 'Steady', worse: 'Dropped' },
}
const MARK: Record<Verdict, string> = { better: '▲', same: '≈', worse: '▼' }

/** A row named in a sentence: "kill %", "digs", and "few errors" where fewer
 * is the good direction. */
function plain(r: CompareRow, good: boolean): string {
  const name = GLOSSARY[r.term].label.replace(' / 21 pts', '').toLowerCase()
  return good && r.better === 'low' ? `few ${name}` : name
}

function VerdictCell({ r, mode }: { r: CompareRow; mode: CompareMode }) {
  if (r.rank) return <span className="num">{ordinal(r.rank.pos)} <span className="muted">of {r.rank.of}</span></span>
  // no chance range to judge fantasy by: against earlier matches, the plain difference
  if (r.kind === 'fantasy' && mode === 'earlier' && r.value !== null && r.ref !== null) {
    return <span className="num">{signed(r.value - r.ref)} <span className="muted">vs before</span></span>
  }
  if (!r.verdict) return null
  return <><span className={`verdict-mark verdict-${r.verdict}`} aria-hidden="true">{MARK[r.verdict]}</span> {WORDS[mode][r.verdict]}</>
}

function Strip({ r, who, refName }: { r: CompareRow; who: string; refName: string }) {
  const [tip, setTip] = useState(false)
  const x = stripScale(r)
  if (!x) return <div className="strip" />
  const range = r.range ? [x(r.range.lo), x(r.range.hi)].sort((a, b) => a - b) : null
  const refRange = r.refRange ? [x(r.refRange.lo), x(r.refRange.hi)].sort((a, b) => a - b) : null
  const anchor = Math.min(70, Math.max(30, x(r.value ?? r.ref ?? 0)))
  const label = GLOSSARY[r.term].label
  const spoken = `${label}: ${who} ${r.value === null ? 'not enough attempts yet' : valueText(r.kind, r.value)}`
    + (r.ref === null ? '' : `, ${refName} ${valueText(r.kind, r.ref)}`)
  return (
    <div className="strip" role="img" tabIndex={0} aria-label={spoken}
         onPointerEnter={() => setTip(true)} onPointerLeave={() => setTip(false)}
         onFocus={() => setTip(true)} onBlur={() => setTip(false)}>
      <span className="strip-track" />
      {r.peers.map((p) => <span key={p.id} className="strip-peer" style={{ left: `${x(p.value)}%` }} />)}
      {refRange && <span className="strip-refrange" style={{ left: `${refRange[0]}%`, width: `${refRange[1] - refRange[0]}%` }} />}
      {r.ref !== null && <span className="strip-ref" style={{ left: `${x(r.ref)}%` }} />}
      {range && <span className="strip-range" style={{ left: `${range[0]}%`, width: `${range[1] - range[0]}%` }} />}
      {r.value !== null && <span className="strip-dot" style={{ left: `${x(r.value)}%` }} />}
      {tip && (
        <div className="tooltip tooltip-wrap" style={{ left: `${anchor}%`, top: 0 }}>
          {r.value !== null
            ? <><strong>{who} {valueText(r.kind, r.value)}</strong>{countText(r) && <> · {countText(r)}</>}</>
            : <strong>{who}: needs {r.min} {r.unit}</strong>}
          {r.range && <><br /><span className="muted">95% range {rangeTextOf(r.kind, r.range)}</span></>}
          {r.ref !== null && (
            <><br />{refName} {valueText(r.kind, r.ref)}
              {r.kind === 'share' && <span className="muted"> · {r.refK}/{r.refN}</span>}
              {r.refRange && <span className="muted"> · range {rangeTextOf(r.kind, r.refRange)}</span>}</>
          )}
        </div>
      )}
    </div>
  )
}

export function Compare({ rows, mode, who, refName }: {
  rows: CompareRow[]
  mode: CompareMode
  /** "You", or the player's name on someone else's page. */
  who: string
  /** What the tall tick is: "League", "Before". */
  refName: string
}) {
  const { best, worst } = highlights(rows)
  const anyPeers = rows.some((r) => r.peers.length > 0) && mode === 'league'
  return (
    <div>
      {(best || worst) && (
        <p className="cmp-chips">
          {best && <span><span className="verdict-mark verdict-better" aria-hidden="true">▲</span> {mode === 'league' ? 'Strength' : 'Improved'}: <strong>{plain(best, true)}</strong></span>}
          {worst && <span><span className="verdict-mark verdict-worse" aria-hidden="true">▼</span> {mode === 'league' ? 'Work on' : 'Dropped'}: <strong>{plain(worst, false)}</strong></span>}
        </p>
      )}
      <div className="cmp" role="list">
        {rows.map((r) => (
          <div key={r.key} className="cmp-row" role="listitem">
            <div className="cmp-label">
              <span>{GLOSSARY[r.term].label}<StatInfo term={r.term} /></span>
              <span className="cmp-count">{r.value === null ? `needs ${r.min} ${r.unit}` : countText(r)}</span>
            </div>
            <div className="cmp-value">{r.value === null ? countText(r) ?? '–' : valueText(r.kind, r.value)}</div>
            <Strip r={mode === 'league' ? r : { ...r, peers: [] }} who={who} refName={refName} />
            <div className="cmp-verdict"><VerdictCell r={r} mode={mode} /></div>
          </div>
        ))}
      </div>
      <div className="legend">
        <span><span className="key key-dot" aria-hidden="true" />{who}</span>
        <span><span className="key key-range" aria-hidden="true" />95% range</span>
        <span><span className="key key-ref" aria-hidden="true" />{mode === 'league' ? 'League, everyone else' : 'Earlier matches'}, with its range</span>
        {anyPeers && <span><span className="key key-peer" aria-hidden="true" />Other players</span>}
        <span className="legend-end">better →</span>
      </div>
      <details className="table-view">
        <summary>Table</summary>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th className="left">Stat</th><th>{who}</th><th>Count</th><th>95% range</th><th>{refName}</th>
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
