import { useState, type KeyboardEvent, type MouseEvent, type PointerEvent } from 'react'
import { formatDate } from '../lib/format'
import {
  LANDING_LABEL, landingError, shots, type LandingKind, type Phase, type Shot, type ShotGroup,
} from '../lib/landings'
import type { Landing } from '../lib/types'
import { Segmented, type Option } from './ui'

/** The whole court in the attacker's frame, seen from behind their own
 * baseline: x 0..8 from their left, y 0 = own baseline, 8 = net, 16 = the
 * opponents' baseline, with room for balls that went out. */
const VIEW = { x0: -1.5, x1: 9.5, y0: -0.8, y1: 17.5 }
const S = 30
const W = (VIEW.x1 - VIEW.x0) * S
const H = (VIEW.y1 - VIEW.y0) * S
const NET_Y = 8

/** Kill and error are the pair that must never be confused, and green vs red
 * is exactly that for one reader in twelve (colour-blind separation 4.1, the
 * floor is 8), so a kill wears the accent. A dug ball is the everyday case:
 * neutral. Shape repeats the outcome at the end of every line. */
const KIND_COLOR: Record<LandingKind, string> = {
  kill: 'var(--accent)', dug: 'var(--muted)', out: 'var(--bad)', net: 'var(--bad)',
  error: 'var(--bad)', unresolved: 'var(--axis)',
}

function Glyph({ kind, x, y }: { kind: LandingKind; x: number; y: number }) {
  const c = KIND_COLOR[kind]
  if (kind === 'kill') return <circle cx={x} cy={y} r={5} fill={c} stroke="var(--surface)" strokeWidth={2} />
  if (kind === 'dug') return <circle cx={x} cy={y} r={3.5} fill="var(--surface)" stroke={c} strokeWidth={2} />
  if (kind === 'unresolved') return <circle cx={x} cy={y} r={3} fill={c} />
  return <path d={`M${x - 4} ${y - 4}L${x + 4} ${y + 4}M${x - 4} ${y + 4}L${x + 4} ${y - 4}`}
               stroke={c} strokeWidth={2.5} strokeLinecap="round" />
}

const GROUP_LABEL: Record<Exclude<ShotGroup, 'other'>, string> = { kill: 'Kills', dug: 'Dug', error: 'Errors' }
const PHASE_LABEL: Record<Phase, string> = { reception: 'Off the reception', transition: 'In transition' }
const LEGEND: { kind: LandingKind; label: string }[] = [
  { kind: 'kill', label: 'Kill' }, { kind: 'dug', label: 'Dug' }, { kind: 'out', label: 'Error (out, net)' },
]

const clampX = (x: number) => Math.min(Math.max(x, VIEW.x0), VIEW.x1)
const clampY = (y: number) => Math.min(Math.max(y, VIEW.y0), VIEW.y1)
const px = (x: number) => (clampX(x) - VIEW.x0) * S
const py = (y: number) => (VIEW.y1 - clampY(y)) * S
const off = (p: { x: number; y: number }) => p.x !== clampX(p.x) || p.y !== clampY(p.y)
const at = (p: { x: number; y: number } | null) => (p ? `${p.x.toFixed(1)}, ${p.y.toFixed(1)}` : '–')

/** Every attack as a line from where the ball was hit to where it came down
 * or was dug. Colour and the mark at the end say what became of it; a dashed
 * line is a free ball. Positions are best effort from one low camera, so the
 * attack under the pointer (or the tapped one) shows the area each end may
 * really be in: depth is the weak axis. */
export function AttackMap({ landings }: { landings: Landing[] }) {
  const [group, setGroup] = useState<ShotGroup | 'all'>('all')
  const [phase, setPhase] = useState<Phase | 'all'>('all')
  const [hover, setHover] = useState<number | null>(null)
  const [picked, setPicked] = useState<number | null>(null)

  const all = shots(landings)
  const inPhase = all.filter((s) => phase === 'all' || s.phase === phase)
  const shown = inPhase.filter((s) => (group === 'all' || s.group === group) && (s.start || s.end))
  const count = (g: ShotGroup) => inPhase.filter((s) => s.group === g).length
  const active = hover ?? picked
  const tip = active === null ? null : shown[active] ?? null
  const anyFree = all.some((s) => s.free)
  const anyPhase = all.some((s) => s.phase !== null)
  const nowhere = all.filter((s) => !s.start && !s.end).length
  const noLine = all.filter((s) => (s.start || s.end) && !(s.start && s.end)).length

  const reset = () => {
    setHover(null)
    setPicked(null)
  }
  const groups: Option<ShotGroup | 'all'>[] = [
    { key: 'all', label: <>All <span className="num muted">{inPhase.length}</span></> },
    ...(['kill', 'dug', 'error'] as const).map((g) => ({
      key: g, label: <>{GROUP_LABEL[g]} <span className="num muted">{count(g)}</span></>, disabled: count(g) === 0,
    })),
  ]
  const phases: Option<Phase | 'all'>[] = [
    { key: 'all', label: 'Any rally' }, { key: 'reception', label: 'Off the reception' }, { key: 'transition', label: 'In transition' },
  ]
  const keys = (e: KeyboardEvent) => {
    if (e.key === 'Escape') reset()
    const step = e.key === 'ArrowRight' ? 1 : e.key === 'ArrowLeft' ? -1 : 0
    if (!step || shown.length === 0) return
    e.preventDefault()
    setPicked(((picked ?? (step > 0 ? -1 : 0)) + step + shown.length) % shown.length)
  }
  const anchor = (s: Shot) => s.end ?? s.start!
  const hit = (i: number) => ({
    onPointerEnter: (e: PointerEvent) => e.pointerType === 'mouse' && setHover(i),
    onPointerLeave: () => setHover(null),
    onClick: (e: MouseEvent) => {
      e.stopPropagation()
      setPicked(picked === i ? null : i)
    },
  })

  return (
    <div className="attack-map">
      <div className="filters">
        <Segmented options={groups} value={group} label="Outcome" onChange={(g) => { setGroup(g); reset() }} />
        {anyPhase && <Segmented options={phases} value={phase} label="Rally phase" onChange={(p) => { setPhase(p); reset() }} />}
      </div>
      <div className="chart court">
        <svg viewBox={`0 0 ${W} ${H}`} role="img" tabIndex={0} onKeyDown={keys} onClick={reset}
             aria-label={`${shown.length} attacks drawn from where the ball was hit to where it came down. Arrow keys step through them.`}>
          <rect x={px(0)} y={py(16)} width={8 * S} height={16 * S} rx={2} fill="var(--surface-2)" stroke="var(--axis)" />
          <rect x={px(0) - 6} y={py(NET_Y) - 2} width={8 * S + 12} height={4} rx={2} fill="var(--ink-2)" />
          <text x={px(8) + 12} y={py(NET_Y) + 4}>net</text>
          <text x={px(4)} y={py(16) - 8} textAnchor="middle">their side</text>
          <text x={px(4)} y={py(0) + 15} textAnchor="middle">attacker's side</text>
          {tip && tip.start && tip.l.sex != null && tip.l.sey != null && (
            <ellipse cx={px(tip.start.x)} cy={py(tip.start.y)} rx={tip.l.sex * S} ry={tip.l.sey * S} fill={KIND_COLOR[tip.kind]} opacity={0.18} />
          )}
          {tip && tip.end && tip.l.ex != null && tip.l.ey != null && (
            <ellipse cx={px(tip.end.x)} cy={py(tip.end.y)} rx={tip.l.ex * S} ry={tip.l.ey * S} fill={KIND_COLOR[tip.kind]} opacity={0.18} />
          )}
          {shown.map((s, i) => {
            const dim = active !== null && active !== i
            const on = active === i
            return (
              <g key={i} opacity={dim ? 0.15 : 1}>
                {s.start && s.end && (
                  <line x1={px(s.start.x)} y1={py(s.start.y)} x2={px(s.end.x)} y2={py(s.end.y)} stroke={KIND_COLOR[s.kind]}
                        strokeWidth={on ? 2.5 : 1.5} strokeLinecap="round" strokeDasharray={s.free ? '5 5' : undefined}
                        opacity={on ? 1 : 0.6} />
                )}
                {s.start && s.end && <circle cx={px(s.start.x)} cy={py(s.start.y)} r={2.5} fill="var(--ink-2)" />}
                <Glyph kind={s.kind} x={px(anchor(s).x)} y={py(anchor(s).y)} />
              </g>
            )
          })}
          {shown.map((s, i) => (
            <g key={i} {...hit(i)} style={{ cursor: 'pointer' }}>
              {s.start && s.end && (
                <line x1={px(s.start.x)} y1={py(s.start.y)} x2={px(s.end.x)} y2={py(s.end.y)} stroke="transparent" strokeWidth={12} />
              )}
              <circle cx={px(anchor(s).x)} cy={py(anchor(s).y)} r={12} fill="transparent" />
            </g>
          ))}
        </svg>
        {tip && (
          <div className="tooltip tooltip-wrap" style={{
            left: `${Math.min(70, Math.max(30, (px(anchor(tip).x) / W) * 100))}%`, top: `${(py(anchor(tip).y) / H) * 100}%`,
          }}>
            <strong>{LANDING_LABEL[tip.kind]}</strong> · {tip.free ? 'free ball' : 'spike'}
            {tip.phase && <> · {PHASE_LABEL[tip.phase].toLowerCase()}</>}
            {tip.l.d && <> · {formatDate(tip.l.d)}</>}
            <br />
            <span className="muted">
              {!tip.end ? 'no end point seen: marked where it was hit'
                : !tip.start ? 'where it was hit was not recorded'
                : tip.kind === 'dug' ? 'ends where the defender played it' : 'ends where the ball came down'}
              {tip.end?.short && ' · estimated short of the net, drawn at it'}
              {tip.end && off(tip.end) && ' · beyond the map'}
              {tip.kind === 'error' && tip.l.in == null && tip.end && ' · line too close to call'}
              {tip.end && landingError(tip.l) && <><br />end {landingError(tip.l)}</>}
            </span>
          </div>
        )}
      </div>
      <div className="legend">
        {LEGEND.map(({ kind, label }) => (
          <span key={kind}>
            <svg width={14} height={14} viewBox="0 0 14 14" style={{ marginRight: 5, verticalAlign: -2 }} aria-hidden="true">
              <Glyph kind={kind} x={7} y={7} />
            </svg>{label}
          </span>
        ))}
        {anyFree && (
          <>
            <span><svg width={22} height={10} viewBox="0 0 22 10" style={{ marginRight: 6 }} aria-hidden="true">
              <line x1={1} x2={21} y1={5} y2={5} stroke="var(--ink-2)" strokeWidth={1.5} strokeLinecap="round" /></svg>spike</span>
            <span><svg width={22} height={10} viewBox="0 0 22 10" style={{ marginRight: 6 }} aria-hidden="true">
              <line x1={1} x2={21} y1={5} y2={5} stroke="var(--ink-2)" strokeWidth={1.5} strokeLinecap="round" strokeDasharray="5 5" /></svg>free ball</span>
          </>
        )}
      </div>
      {(noLine > 0 || nowhere > 0) && (
        <p className="muted small" style={{ margin: '6px 0 0' }}>
          {noLine > 0 && <>{noLine} with one end only: a mark where the ball was hit, or where it came down. </>}
          {nowhere > 0 && <>{nowhere} of {all.length} without any position are not drawn.</>}
        </p>
      )}
      <details className="table-view">
        <summary>Table</summary>
        <div className="table-wrap">
          <table>
            <thead>
              <tr><th className="left">Date</th><th className="left">Attack</th><th className="left">Rally</th>
                <th className="left">Outcome</th><th>Hit at (m)</th><th>Came down (m)</th></tr>
            </thead>
            <tbody>
              {all.map((s, i) => (
                <tr key={i}>
                  <td className="left">{s.l.d ? formatDate(s.l.d) : '–'}</td>
                  <td className="left">{s.free ? 'Free ball' : 'Spike'}</td>
                  <td className="left">{s.phase ? PHASE_LABEL[s.phase] : '–'}</td>
                  <td className="left">{LANDING_LABEL[s.kind]}</td>
                  <td>{at(s.start)}</td>
                  <td>{at(s.end)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </div>
  )
}
