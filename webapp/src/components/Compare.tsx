// A player beside a reference, one row per stat, the reference in the centre.
// MORE is to the right on every row: a stat where fewer is better says so and
// is judged by its verdict, never by flipping the axis. The bar is the gap to
// the reference (everyone else pooled, or the player's own earlier matches).
// Inside the shaded zone the gap is smaller than chance moves the number and
// the bar stays faint; a bar that leaves the zone is a real gap and takes the
// colour of its verdict. The hollow dots are the other players. A row that has
// no reference yet is drawn as plain bars from zero, one per player.
import { Fragment, useState, type CSSProperties, type ReactNode } from 'react'
import {
  barScale, countText, gapScale, highlights, ordinal, rangeTextOf, valueText, type CompareRow, type GapScale, type Verdict,
} from '../lib/compare'
import { signed } from '../lib/format'
import { GLOSSARY } from '../lib/glossary'
import { StatInfo } from './ui'

export type CompareMode = 'league' | 'earlier'

const WORDS: Record<CompareMode, Record<Verdict, string>> = {
  league: { better: 'Better', same: 'Too close to call', worse: 'Worse' },
  earlier: { better: 'Improved', same: 'Too close to call', worse: 'Dropped' },
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

/** The gap to the reference: the centre line is the reference, the bar runs
 * from it to the player. */
function GapMarks({ r, scale }: { r: CompareRow; scale: GapScale }) {
  const at = r.value === null ? null : scale.x(r.value)
  return (
    <>
      {scale.zone !== null && <span className="gap-zone" style={{ left: `${50 - scale.zone}%`, width: `${2 * scale.zone}%` }} />}
      <span className="gap-axis" />
      {at !== null && (
        <span className={`gap-bar gap-${r.verdict ?? 'plain'}${at < 50 ? ' gap-left' : ''}`}
              style={{ left: `${Math.min(50, at)}%`, width: `${Math.abs(at - 50)}%` }} />
      )}
      {r.peers.map((p) => <span key={p.id} className="gap-peer" style={{ left: `${scale.x(p.value)}%` }} />)}
    </>
  )
}

/** No reference yet: the player's bar from zero with its likely range, and
 * one named bar per other player (two at most: three make a reference). */
function BarMarks({ r }: { r: CompareRow }) {
  const x = barScale(r, r.peers.length > 0 ? 62 : 96)
  const zero = x(0)
  const bar = (v: number): CSSProperties => ({ left: `${Math.min(zero, x(v))}%`, width: `${Math.abs(x(v) - zero)}%` })
  return (
    <>
      <span className="bar-zero" style={{ left: `${zero}%` }} />
      {r.value !== null
        ? <span className={`bar-you${r.value < 0 ? ' bar-neg' : ''}`} style={bar(r.value)} />
        : <span className="bar-note" style={{ left: `calc(${zero}% + 8px)` }}>shows from {r.min} {r.unit} · {r.n} so far</span>}
      {r.value !== null && r.range && (
        <span className="bar-whisk" style={{ left: `${x(r.range.lo)}%`, width: `${x(r.range.hi) - x(r.range.lo)}%` }} />
      )}
      {r.peers.map((p, i) => (
        <Fragment key={p.id}>
          <span className={`bar-peer${p.value < 0 ? ' bar-neg' : ''}`} style={{ ...bar(p.value), top: 21 + i * 14 }} />
          <span className="bar-name" style={{ left: `calc(${Math.max(zero, x(p.value))}% + 7px)`, top: 16 + i * 14 }}>
            {p.name} {valueText(r.kind, p.value)}
          </span>
        </Fragment>
      ))}
    </>
  )
}

function Lane({ r, who, refName }: { r: CompareRow; who: string; refName: string }) {
  const [tip, setTip] = useState(false)
  const scale = gapScale(r)
  const label = GLOSSARY[r.term].label
  const spoken = `${label}: ${who} ${r.value === null ? 'not enough attempts yet' : valueText(r.kind, r.value)}`
    + (r.ref === null ? '' : `, ${refName} ${valueText(r.kind, r.ref)}`)
  const height = scale ? undefined : r.peers.length > 0 ? 18 + 14 * r.peers.length : 22
  return (
    <div className={`lane ${scale ? 'gap-lane' : 'bar-lane'}`} style={{ height }} role="img" tabIndex={0} aria-label={spoken}
         onPointerEnter={() => setTip(true)} onPointerLeave={() => setTip(false)}
         onFocus={() => setTip(true)} onBlur={() => setTip(false)}>
      {scale ? <GapMarks r={r} scale={scale} /> : <BarMarks r={r} />}
      {tip && (
        <div className="tooltip tooltip-wrap" style={{ left: '50%', top: 0 }}>
          {r.value !== null
            ? <><strong>{who} {valueText(r.kind, r.value)}</strong>{countText(r) && <> · {countText(r)}</>}</>
            : <strong>{who}: needs {r.min} {r.unit}</strong>}
          {r.range && <><br /><span className="muted">Likely range {rangeTextOf(r.kind, r.range)}</span></>}
          {r.ref !== null && (
            <><br />{refName} {valueText(r.kind, r.ref)}
              {r.kind === 'share' && <span className="muted"> · {r.refK}/{r.refN}</span>}
              {r.refRange && <span className="muted"> · range {rangeTextOf(r.kind, r.refRange)}</span>}</>
          )}
          {r.peers.length > 0 && (
            <><br /><span className="muted">{r.peers.map((p) => `${p.name} ${valueText(r.kind, p.value)}`).join(' · ')}</span></>
          )}
        </div>
      )}
    </div>
  )
}

function Key({ mark, children }: { mark: string; children: ReactNode }) {
  return <span><span className={`key key-${mark}`} aria-hidden="true" />{children}</span>
}

export function Compare({ rows: all, mode, who, refName }: {
  rows: CompareRow[]
  mode: CompareMode
  /** "You", or the player's name on someone else's page. */
  who: string
  /** What the centre line is, in a column heading: "League", "Before". */
  refName: string
}) {
  // the other players are drawn against the league only
  const rows = mode === 'league' ? all : all.map((r) => ({ ...r, peers: [] }))
  const { best, worst } = highlights(rows)
  const anyRef = rows.some((r) => r.ref !== null)
  const anyPeers = rows.some((r) => r.peers.length > 0)
  const bars = rows.filter((r) => r.ref === null)
  const centre = mode === 'league' ? 'League average' : 'Earlier matches'
  // one real row says what "by chance" means: 3 in 18 attacks is anywhere from 6% to 39%
  const example = rows.find((r) => r.key === 'kill' && r.value !== null && r.range) ?? rows.find((r) => r.kind === 'share' && r.value !== null && r.range)
  return (
    <div>
      {(best || worst) && (
        <p className="cmp-chips">
          {best && <span><span className="verdict-mark verdict-better" aria-hidden="true">▲</span> {mode === 'league' ? 'Strength' : 'Improved'}: <strong>{plain(best, true)}</strong></span>}
          {worst && <span><span className="verdict-mark verdict-worse" aria-hidden="true">▼</span> {mode === 'league' ? 'Work on' : 'Dropped'}: <strong>{plain(worst, false)}</strong></span>}
        </p>
      )}
      <div className="cmp-head">
        <span className="cmp-head-who">{who}</span>
        <span className="cmp-head-ref">{anyRef && refName}</span>
        {anyRef
          ? <span className="cmp-head-axis"><span>◂ lower</span><span>{centre}</span><span>higher ▸</span></span>
          : <span className="cmp-head-axis" />}
        <span className="cmp-head-end" />
      </div>
      <div className="cmp" role="list">
        {rows.map((r) => (
          <div key={r.key} className={`cmp-row${r.kind === 'fantasy' ? ' cmp-total' : ''}`} role="listitem">
            <div className="cmp-label">
              <span>
                {GLOSSARY[r.term].label}<StatInfo term={r.term} />
                {r.better === 'low' && <span className="cmp-low">fewer is better</span>}
              </span>
              <span className="cmp-count">{r.value === null ? `needs ${r.min} ${r.unit}` : countText(r)}</span>
            </div>
            <div className="cmp-value">{r.value === null ? countText(r) ?? '–' : valueText(r.kind, r.value)}</div>
            <div className="cmp-ref">{anyRef && valueText(r.kind, r.ref)}</div>
            <Lane r={r} who={who} refName={refName} />
            <div className="cmp-verdict"><VerdictCell r={r} mode={mode} /></div>
          </div>
        ))}
      </div>
      <div className="legend">
        {anyRef && (
          <>
            <Key mark="better">{mode === 'league' ? 'Clearly better' : 'Clearly improved'}</Key>
            <Key mark="worse">{mode === 'league' ? 'Clearly worse' : 'Clearly dropped'}</Key>
            <Key mark="zone">Too close to call</Key>
            <Key mark="axis">{centre}</Key>
            {rows.some((r) => r.ref !== null && r.peers.length > 0) && <Key mark="peer">Other players</Key>}
          </>
        )}
        {bars.some((r) => r.value !== null) && <Key mark="you">{who}</Key>}
        {bars.some((r) => r.peers.length > 0) && <Key mark="other">Other players</Key>}
        {bars.some((r) => r.range) && <Key mark="whisk">Likely range</Key>}
      </div>
      {(anyRef || example) && (
        <p className="cmp-explain">
          {anyRef
            ? <>Too close to call: the gap is smaller than what chance alone moves the number.</>
            : <>Likely range: how far chance alone can move the number.</>}
          {example && example.value !== null && example.range && (
            <> {example.k} in {example.n} {example.unit} reads {valueText(example.kind, example.value)}, but the real level could
              be anywhere from {valueText(example.kind, example.range.lo)} to {valueText(example.kind, example.range.hi)}.</>
          )}
        </p>
      )}
      <details className="table-view">
        <summary>Table</summary>
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
