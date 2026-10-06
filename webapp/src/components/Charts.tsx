// Small SVG charts in the app's tokens: one accent hue for a single series,
// the team colours for the four players. 2px lines, a 2px surface ring on
// dots, hairline grid, a crosshair that snaps to the nearest point, and a
// table view so nothing depends on hovering.
import { useRef, useState, type KeyboardEvent, type PointerEvent, type ReactNode } from 'react'
import { rangeText, type RollingPoint } from '../lib/stats'
import type { Slot } from '../lib/types'

const W = 560
const H = 200
const PAD = { l: 40, r: 14, t: 12, b: 26 }

function nearest(e: PointerEvent<SVGSVGElement>, n: number, x: (i: number) => number): number {
  const box = e.currentTarget.getBoundingClientRect()
  const px = ((e.clientX - box.left) / box.width) * W
  let best = 0
  for (let i = 1; i < n; i++) if (Math.abs(x(i) - px) < Math.abs(x(best) - px)) best = i
  return best
}

function arrows(e: KeyboardEvent, i: number | null, n: number, set: (i: number | null) => void) {
  if (e.key === 'ArrowRight') set(Math.min(n - 1, (i ?? -1) + 1))
  else if (e.key === 'ArrowLeft') set(Math.max(0, (i ?? n) - 1))
  else if (e.key === 'Escape') set(null)
}

/** A rate over rolling windows of attempts, with its 95 % range as a band. */
export function RollingChart({ points, dates, unit, window, label }: {
  points: RollingPoint[]; dates: string[]; unit: string; window: number; label: string
}) {
  const [hover, setHover] = useState<number | null>(null)
  const ref = useRef<SVGSVGElement>(null)
  const n = points.length
  const top = Math.min(1, Math.max(0.5, Math.ceil((Math.max(...points.map((p) => p.hi)) + 0.02) * 4) / 4))
  const x0 = points[0].end
  const x1 = points[n - 1].end
  const x = (i: number) => PAD.l + (n === 1 ? (W - PAD.l - PAD.r) / 2 : ((points[i].end - x0) / (x1 - x0)) * (W - PAD.l - PAD.r))
  const y = (v: number) => PAD.t + (1 - v / top) * (H - PAD.t - PAD.b)
  const ticks = Array.from({ length: Math.round(top / 0.25) + 1 }, (_, i) => i * 0.25)
  const line = points.map((p, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)} ${y(p.rate).toFixed(1)}`).join('')
  const band = points.map((p, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)} ${y(p.hi).toFixed(1)}`).join('')
    + [...points].reverse().map((p, i) => `L${x(n - 1 - i).toFixed(1)} ${y(p.lo).toFixed(1)}`).join('') + 'Z'
  const last = points[n - 1]
  const tip = hover === null ? null : points[hover]
  return (
    <div>
      <div className="chart">
        <svg ref={ref} viewBox={`0 0 ${W} ${H}`} role="img" tabIndex={0} aria-label={label}
             onPointerMove={(e) => setHover(nearest(e, n, x))} onPointerLeave={() => setHover(null)}
             onKeyDown={(e) => arrows(e, hover, n, setHover)} onBlur={() => setHover(null)}>
          {ticks.map((t) => (
            <g key={t}>
              <line x1={PAD.l} x2={W - PAD.r} y1={y(t)} y2={y(t)} stroke="var(--grid)" strokeWidth={1} />
              <text x={PAD.l - 8} y={y(t) + 4} textAnchor="end">{Math.round(t * 100)}%</text>
            </g>
          ))}
          <path d={band} fill="var(--accent)" opacity={0.12} />
          <path d={line} fill="none" stroke="var(--accent)" strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
          <text x={PAD.l} y={H - 6}>{unit} {x0}</text>
          <text x={W - PAD.r} y={H - 6} textAnchor="end">{unit} {x1}</text>
          {tip && <line x1={x(hover as number)} x2={x(hover as number)} y1={PAD.t} y2={H - PAD.b} stroke="var(--axis)" strokeWidth={1} />}
          <circle cx={x(hover ?? n - 1)} cy={y((tip ?? last).rate)} r={4} fill="var(--accent)" stroke="var(--surface)" strokeWidth={2} />
        </svg>
        {tip && (
          <div className="tooltip" style={{ left: `${(x(hover as number) / W) * 100}%`, top: `${(y(tip.rate) / H) * 100}%` }}>
            <strong>{Math.round(tip.rate * 100)}%</strong> · {tip.k}/{tip.n}
            <br /><span className="muted">range {rangeText({ lo: tip.lo, hi: tip.hi })} · up to {unit} {tip.end}
              {dates[tip.end - 1] ? ` · ${dates[tip.end - 1]}` : ''}</span>
          </div>
        )}
      </div>
      <p className="muted small" style={{ margin: '4px 0 0' }}>
        Last {window} {unit}s at each point; the band is the 95% range. Now: <strong>{Math.round(last.rate * 100)}%</strong> ({last.k}/{last.n}).
      </p>
      <details className="table-view">
        <summary>Table</summary>
        <div className="table-wrap">
          <table>
            <thead><tr><th className="left">Up to {unit}</th><th className="left">Date</th><th>k/n</th><th>Rate</th><th>95% range</th></tr></thead>
            <tbody>
              {points.map((p) => (
                <tr key={p.end}>
                  <td className="left">{p.end}</td><td className="left">{dates[p.end - 1] ?? ''}</td>
                  <td>{p.k}/{p.n}</td><td>{Math.round(p.rate * 100)}%</td>
                  <td>{rangeText({ lo: p.lo, hi: p.hi })}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </div>
  )
}

export interface Line {
  slot: Slot
  name: string
  team: 'A' | 'B'
  /** Second player of a team: dashed, so identity is not colour alone. */
  dashed: boolean
  values: number[]
}

/** Running fantasy points per player through the points of a match. */
export function FantasyTimeline({ lines, label }: { lines: Line[]; label: string }) {
  const [hover, setHover] = useState<number | null>(null)
  const n = lines[0].values.length
  const all = lines.flatMap((l) => l.values)
  const lo = Math.min(0, ...all)
  const hi = Math.max(1, ...all)
  const span = Math.ceil(hi) - Math.floor(lo) || 1
  const step = span <= 8 ? 2 : span <= 20 ? 5 : 10
  const yMin = Math.floor(lo / step) * step
  const yMax = Math.ceil(hi / step) * step
  const x = (i: number) => PAD.l + (i / Math.max(1, n - 1)) * (W - PAD.l - PAD.r)
  const y = (v: number) => PAD.t + (1 - (v - yMin) / (yMax - yMin)) * (H - PAD.t - PAD.b)
  const ticks: number[] = []
  for (let t = yMin; t <= yMax; t += step) ticks.push(t)
  const color = (l: Line) => (l.team === 'A' ? 'var(--team-a)' : 'var(--team-b)')
  const dash = (l: Line) => (l.dashed ? '6 4' : undefined)
  const sorted = hover === null ? [] : [...lines].sort((a, b) => b.values[hover] - a.values[hover])
  return (
    <div>
      <div className="legend" style={{ marginTop: 0, marginBottom: 6 }}>
        {lines.map((l) => (
          <span key={l.slot}>
            <svg width={22} height={10} viewBox="0 0 22 10" style={{ marginRight: 6 }} aria-hidden="true">
              <line x1={1} x2={21} y1={5} y2={5} stroke={color(l)} strokeWidth={2} strokeDasharray={dash(l)} strokeLinecap="round" />
            </svg>{l.name}
          </span>
        ))}
      </div>
      <div className="chart">
        <svg viewBox={`0 0 ${W} ${H}`} role="img" tabIndex={0} aria-label={label}
             onPointerMove={(e) => setHover(nearest(e, n, x))} onPointerLeave={() => setHover(null)}
             onKeyDown={(e) => arrows(e, hover, n, setHover)} onBlur={() => setHover(null)}>
          {ticks.map((t) => (
            <g key={t}>
              <line x1={PAD.l} x2={W - PAD.r} y1={y(t)} y2={y(t)} stroke={t === 0 ? 'var(--axis)' : 'var(--grid)'} strokeWidth={1} />
              <text x={PAD.l - 8} y={y(t) + 4} textAnchor="end">{t}</text>
            </g>
          ))}
          {lines.map((l) => (
            <path key={l.slot} fill="none" stroke={color(l)} strokeWidth={2} strokeLinejoin="round" strokeLinecap="round"
                  strokeDasharray={dash(l)} d={l.values.map((v, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)} ${y(v).toFixed(1)}`).join('')} />
          ))}
          <text x={PAD.l} y={H - 6}>point 0</text>
          <text x={W - PAD.r} y={H - 6} textAnchor="end">point {n - 1}</text>
          {hover !== null && <line x1={x(hover)} x2={x(hover)} y1={PAD.t} y2={H - PAD.b} stroke="var(--axis)" strokeWidth={1} />}
          {lines.map((l) => {
            const i = hover ?? n - 1
            return <circle key={l.slot} cx={x(i)} cy={y(l.values[i])} r={4} fill={color(l)} stroke="var(--surface)" strokeWidth={2} />
          })}
        </svg>
        {hover !== null && (
          <div className="tooltip" style={{ left: `${(x(hover) / W) * 100}%`, top: '0%', transform: 'translate(-50%, 0)' }}>
            <span className="muted">after point {hover}</span>
            {sorted.map((l) => (
              <div key={l.slot}>
                <svg width={16} height={8} viewBox="0 0 16 8" style={{ marginRight: 6 }} aria-hidden="true">
                  <line x1={1} x2={15} y1={4} y2={4} stroke={color(l)} strokeWidth={2} strokeDasharray={dash(l)} strokeLinecap="round" />
                </svg>
                <strong>{l.values[hover]}</strong> <span className="muted">{l.name}</span>
              </div>
            ))}
          </div>
        )}
      </div>
      <details className="table-view">
        <summary>Table</summary>
        <div className="table-wrap">
          <table>
            <thead><tr><th className="left">After point</th>{lines.map((l) => <th key={l.slot}>{l.name}</th>)}</tr></thead>
            <tbody>
              {Array.from({ length: n }, (_, i) => (
                <tr key={i}><td className="left">{i}</td>{lines.map((l) => <td key={l.slot}>{l.values[i]}</td>)}</tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </div>
  )
}

/** The last few values as a line, the newest one dotted. */
export function Sparkline({ values, label }: { values: number[]; label: string }) {
  if (values.length < 2) return null
  const w = 120
  const h = 32
  const lo = Math.min(...values)
  const hi = Math.max(...values)
  const x = (i: number) => 6 + (i / (values.length - 1)) * (w - 12)
  const y = (v: number) => (hi === lo ? h / 2 : 5 + (1 - (v - lo) / (hi - lo)) * (h - 10))
  return (
    <svg viewBox={`0 0 ${w} ${h}`} width={w} height={h} role="img" aria-label={label} style={{ overflow: 'visible' }}>
      <path d={values.map((v, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)} ${y(v).toFixed(1)}`).join('')}
            fill="none" stroke="var(--ink-2)" strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
      <circle cx={x(values.length - 1)} cy={y(values[values.length - 1])} r={4} fill="var(--accent)" stroke="var(--surface)" strokeWidth={2} />
    </svg>
  )
}

export interface Segment {
  label: string
  n: number
  color: string
  hint?: string
}

/** One proportional bar split into parts, with the counts in its legend. */
export function StackBar({ segments, label, children }: { segments: Segment[]; label: string; children?: ReactNode }) {
  const total = segments.reduce((t, s) => t + s.n, 0)
  if (total === 0) return null
  return (
    <div>
      <div className="stack-bar" role="img"
           aria-label={`${label}: ${segments.filter((s) => s.n).map((s) => `${s.n} ${s.label}`).join(', ')}`}>
        {segments.filter((s) => s.n > 0).map((s) => (
          <span key={s.label} style={{ flexGrow: s.n, background: s.color }} title={`${s.label}: ${s.n} of ${total}${s.hint ? ` · ${s.hint}` : ''}`} />
        ))}
      </div>
      <div className="legend">
        {segments.map((s) => (
          <span key={s.label}>
            <span className="swatch" style={{ background: s.color }} aria-hidden="true" />
            <strong className="num">{s.n}</strong> {s.label}
          </span>
        ))}
        {children}
      </div>
    </div>
  )
}
