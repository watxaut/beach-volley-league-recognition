import { useState, type KeyboardEvent, type MouseEvent, type PointerEvent } from 'react'
import { formatDate } from '../lib/format'
import {
  NET_Y, NEXT_LABEL, PASS_LABEL, passPoints, spotWords, summarize, type PassKind, type PassPoint, type Point,
} from '../lib/passes'
import { MIN_N } from '../lib/stats'
import type { Pass } from '../lib/types'
import { Segmented, type Option } from './ui'

/** The player's own half, seen from behind their baseline: x 0..8 from their
 * left sideline, y 0 = baseline, 8 = net, with room for a ball played wide. */
const VIEW = { x0: -1.5, x1: 9.5, y0: -0.9, y1: 9.1 }
const S = 32
const W = (VIEW.x1 - VIEW.x0) * S
const H = (VIEW.y1 - VIEW.y0) * S

const clampX = (x: number) => Math.min(Math.max(x, VIEW.x0), VIEW.x1)
const clampY = (y: number) => Math.min(Math.max(y, VIEW.y0), VIEW.y1)
const px = (x: number) => (clampX(x) - VIEW.x0) * S
const py = (y: number) => (VIEW.y1 - clampY(y)) * S
const at = (p: Point | null) => (p ? `${p.x.toFixed(1)}, ${p.y.toFixed(1)}` : '–')

/** Identity is the shape first, colour second (neither team colour: they
 * already mean squad A / B): a reception is a blue dot, a defense a grey
 * diamond. */
const KIND_COLOR: Record<PassKind, string> = { reception: 'var(--accent)', defense: 'var(--ink-2)' }

function Mark({ kind, x, y, hollow = false, r = 4.5 }: { kind: PassKind; x: number; y: number; hollow?: boolean; r?: number }) {
  const c = KIND_COLOR[kind]
  const fill = hollow ? 'var(--surface)' : c
  const common = { fill, stroke: hollow ? c : 'var(--surface)', strokeWidth: hollow ? 2 : 1.5, opacity: hollow ? 1 : 0.72 }
  if (kind === 'reception') return <circle cx={x} cy={y} r={r} {...common} />
  const d = r * 1.25
  return <path d={`M${x} ${y - d}L${x + d} ${y}L${x} ${y + d}L${x - d} ${y}Z`} {...common} />
}

/** Where the ball went next: a small arrowhead at the end of the line, a dot
 * when there is no start to point from. */
function Arrow({ kind, from, to }: { kind: PassKind; from: Point | null; to: Point }) {
  const c = KIND_COLOR[kind]
  const x = px(to.x)
  const y = py(to.y)
  const dx = from ? x - px(from.x) : 0
  const dy = from ? y - py(from.y) : 0
  const len = Math.hypot(dx, dy)
  const ring = { fill: c, stroke: 'var(--surface)', strokeWidth: 1, opacity: 0.9 }
  if (len < 8) return <circle cx={x} cy={y} r={3} {...ring} />
  const ux = dx / len
  const uy = dy / len
  const bx = x - ux * 9
  const by = y - uy * 9
  return <path d={`M${x} ${y}L${bx - uy * 4.5} ${by + ux * 4.5}L${bx + uy * 4.5} ${by - ux * 4.5}Z`} strokeLinejoin="round" {...ring} />
}

const EDGE = 'var(--axis)'

/** Every reception and defense: the big mark is where it was played, the
 * arrowhead where the ball was at the next touch. There is no target on the
 * court: if the balls go to one spot the arrowheads pile up there, and the
 * dashed ring (half of the balls end inside it) closes around them; if they
 * are scattered the ring is wide. Positions are best effort from one low camera, so the pass
 * under the pointer (or the tapped one) shows the area its end may be in. */
export function PassMap({ passes }: { passes: Pass[] }) {
  const [kind, setKind] = useState<PassKind | 'all'>('all')
  const [hover, setHover] = useState<number | null>(null)
  const [picked, setPicked] = useState<number | null>(null)

  const all = passPoints(passes)
  const sums = { reception: summarize(all, 'reception'), defense: summarize(all, 'defense') }
  const shown = all.filter((q) => (kind === 'all' || q.kind === kind) && (q.start || q.end))
  const kinds = (['reception', 'defense'] as const).filter((k) => kind === 'all' || kind === k)
  const active = hover ?? picked
  const tip = active === null ? null : shown[active] ?? null
  const nowhere = all.filter((q) => !q.start && !q.end).length

  const reset = () => {
    setHover(null)
    setPicked(null)
  }
  const options: Option<PassKind | 'all'>[] = [
    { key: 'all', label: <>Both <span className="num muted">{all.length}</span></> },
    ...(['reception', 'defense'] as const).map((k) => ({
      key: k, label: <>{PASS_LABEL[k]}s <span className="num muted">{sums[k].n}</span></>, disabled: sums[k].n === 0,
    })),
  ]
  const keys = (e: KeyboardEvent) => {
    if (e.key === 'Escape') reset()
    const step = e.key === 'ArrowRight' ? 1 : e.key === 'ArrowLeft' ? -1 : 0
    if (!step || shown.length === 0) return
    e.preventDefault()
    setPicked(((picked ?? (step > 0 ? -1 : 0)) + step + shown.length) % shown.length)
  }
  const anchor = (q: PassPoint) => q.start ?? q.end!
  const hit = (i: number) => ({
    onPointerEnter: (e: PointerEvent) => e.pointerType === 'mouse' && setHover(i),
    onPointerLeave: () => setHover(null),
    onClick: (e: MouseEvent) => {
      e.stopPropagation()
      setPicked(picked === i ? null : i)
    },
  })

  return (
    <div className="pass-map">
      <div className="filters">
        <Segmented options={options} value={kind} label="Kind of pass" onChange={(k) => { setKind(k); reset() }} />
      </div>
      <div className="chart court">
        <svg viewBox={`0 0 ${W} ${H}`} role="img" tabIndex={0} onKeyDown={keys} onClick={reset}
             aria-label={`${shown.length} passes drawn from where the ball was played to where it went next. Arrow keys step through them.`}>
          <rect x={px(0)} y={py(NET_Y)} width={8 * S} height={NET_Y * S} rx={2} fill="var(--surface-2)" stroke={EDGE} />
          <rect x={px(0) - 6} y={py(NET_Y) - 2} width={8 * S + 12} height={4} rx={2} fill="var(--ink-2)" />
          <text x={px(8) + 12} y={py(NET_Y) + 4}>net</text>
          <text x={px(4)} y={py(0) + 15} textAnchor="middle">baseline</text>
          {/* the usual spot of each kind shown: half of the balls fall inside the ring */}
          {kinds.map((k) => {
            const spot = sums[k].spot
            if (!spot) return null
            const c = KIND_COLOR[k]
            return (
              <g key={k} opacity={active !== null ? 0.4 : 1} pointerEvents="none">
                <circle cx={px(spot.x)} cy={py(spot.y)} r={spot.r * S} fill={c} opacity={0.08} />
                <circle cx={px(spot.x)} cy={py(spot.y)} r={spot.r * S} fill="none" stroke={c} strokeWidth={1.5} strokeDasharray="5 4" />
                <path d={`M${px(spot.x) - 5} ${py(spot.y)}H${px(spot.x) + 5}M${px(spot.x)} ${py(spot.y) - 5}V${py(spot.y) + 5}`}
                      stroke={c} strokeWidth={2} strokeLinecap="round" />
              </g>
            )
          })}
          {tip && tip.start && tip.p.sex != null && tip.p.sey != null && (
            <ellipse cx={px(tip.start.x)} cy={py(tip.start.y)} rx={tip.p.sex * S} ry={tip.p.sey * S} fill={KIND_COLOR[tip.kind]} opacity={0.18} />
          )}
          {tip && tip.end && tip.p.ex != null && tip.p.ey != null && (
            <ellipse cx={px(tip.end.x)} cy={py(tip.end.y)} rx={tip.p.ex * S} ry={tip.p.ey * S} fill={KIND_COLOR[tip.kind]} opacity={0.18} />
          )}
          {shown.map((q, i) => {
            const dim = active !== null && active !== i
            const on = active === i
            return (
              <g key={i} opacity={dim ? 0.15 : 1}>
                {q.start && q.end && (
                  <line x1={px(q.start.x)} y1={py(q.start.y)} x2={px(q.end.x)} y2={py(q.end.y)} stroke={KIND_COLOR[q.kind]}
                        strokeWidth={on ? 2.5 : 1.5} strokeLinecap="round" opacity={on ? 0.9 : 0.3} />
                )}
                {q.end && <Arrow kind={q.kind} from={q.start} to={q.end} />}
                {q.start && <Mark kind={q.kind} x={px(q.start.x)} y={py(q.start.y)} r={5} hollow={!q.end} />}
              </g>
            )
          })}
          {shown.map((q, i) => (
            <g key={i} {...hit(i)} style={{ cursor: 'pointer' }}>
              {q.start && q.end && (
                <line x1={px(q.start.x)} y1={py(q.start.y)} x2={px(q.end.x)} y2={py(q.end.y)} stroke="transparent" strokeWidth={12} />
              )}
              <circle cx={px(anchor(q).x)} cy={py(anchor(q).y)} r={12} fill="transparent" />
              {q.end && q.start && <circle cx={px(q.end.x)} cy={py(q.end.y)} r={9} fill="transparent" />}
            </g>
          ))}
        </svg>
        {tip && (
          <div className="tooltip tooltip-wrap" style={{
            left: `${Math.min(70, Math.max(30, (px(anchor(tip).x) / W) * 100))}%`, top: `${(py(anchor(tip).y) / H) * 100}%`,
          }}>
            <strong>{PASS_LABEL[tip.kind]}</strong>
            {tip.p.d && <> · {formatDate(tip.p.d)}</>}
            <br />
            <span className="muted">
              {tip.end ? <>the ball went to {tip.p.to ? NEXT_LABEL[tip.p.to] : 'the next touch'}{!tip.start && ' · where it was played was not recorded'}</>
                : 'no next touch seen on this side: marked where it was played'}
              {tip.end?.atNet && ' · read past the net, drawn at it'}
              {tip.end && tip.p.ex != null && tip.p.ey != null && (
                <><br />end ±{tip.p.ex.toFixed(1)} m across, ±{tip.p.ey.toFixed(1)} m along</>
              )}
            </span>
          </div>
        )}
      </div>
      <div className="legend">
        {kinds.map((k) => (
          <span key={k}>
            <svg width={14} height={14} viewBox="0 0 14 14" style={{ marginRight: 5, verticalAlign: -2 }} aria-hidden="true">
              <Mark kind={k} x={7} y={7} r={5} />
            </svg>{PASS_LABEL[k]}: where it was played
          </span>
        ))}
        <span>
          <svg width={20} height={14} viewBox="0 0 20 14" style={{ marginRight: 5, verticalAlign: -2 }} aria-hidden="true">
            <line x1={1} y1={7} x2={12} y2={7} stroke="var(--ink-2)" strokeWidth={1.5} opacity={0.5} />
            <path d="M19 7L11 3.5V10.5Z" fill="var(--ink-2)" />
          </svg>where the ball went next
        </span>
        <span>
          <svg width={18} height={14} viewBox="0 0 18 14" style={{ marginRight: 5, verticalAlign: -2 }} aria-hidden="true">
            <circle cx={9} cy={7} r={6} fill="none" stroke="var(--ink-2)" strokeWidth={1.5} strokeDasharray="4 3" />
          </svg>half of the balls end inside
        </span>
        {shown.some((q) => !q.end) && (
          <span>
            <svg width={14} height={14} viewBox="0 0 14 14" style={{ marginRight: 5, verticalAlign: -2 }} aria-hidden="true">
              <circle cx={7} cy={7} r={4.5} fill="var(--surface)" stroke="var(--ink-2)" strokeWidth={2} />
            </svg>next touch not seen
          </span>
        )}
      </div>
      {kinds.map((k) => {
        const s = sums[k]
        if (s.n === 0) return null
        return (
          <p key={k} className="small" style={{ margin: '6px 0 0' }}>
            <strong>{PASS_LABEL[k]}s</strong>{' '}
            {s.spot ? <>usually went <strong>{spotWords(s.spot)}</strong>.</>
              : <span className="muted">usual spot from {MIN_N} seen · {s.seen} so far.</span>}
          </p>
        )
      })}
      {nowhere > 0 && (
        <p className="muted small" style={{ margin: '6px 0 0' }}>{nowhere} of {all.length} without any position are not drawn.</p>
      )}
      <details className="table-view">
        <summary>Table</summary>
        <div className="table-wrap">
          <table>
            <thead>
              <tr><th className="left">Date</th><th className="left">Pass</th><th>Played at (m)</th>
                <th>Went to (m)</th><th className="left">Next touch</th></tr>
            </thead>
            <tbody>
              {all.map((q, i) => (
                <tr key={i}>
                  <td className="left">{q.p.d ? formatDate(q.p.d) : '–'}</td>
                  <td className="left">{PASS_LABEL[q.kind]}</td>
                  <td>{at(q.start)}</td>
                  <td>{at(q.end)}</td>
                  <td className="left">{q.p.to ? NEXT_LABEL[q.p.to] : '–'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </div>
  )
}
