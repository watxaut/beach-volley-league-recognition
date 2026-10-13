import { useState, type KeyboardEvent, type MouseEvent, type PointerEvent } from 'react'
import { formatDate } from '../lib/format'
import { NET_Y, SERVE_LABEL, servePoints, serveSpotWords, type ServeKind, type ServePoint } from '../lib/serves'
import type { Serve } from '../lib/types'
import { Segmented, type Option } from './ui'

/** The opponents' half, seen from the server's side: x 0..8 from the server's
 * left sideline, y 8 = net .. 16 = their baseline, with room for a serve that
 * went long or wide. */
const VIEW = { x0: -1.5, x1: 9.5, y0: 7.1, y1: 17.7 }
const S = 32
const W = (VIEW.x1 - VIEW.x0) * S
const H = (VIEW.y1 - VIEW.y0) * S

const clampX = (x: number) => Math.min(Math.max(x, VIEW.x0), VIEW.x1)
const clampY = (y: number) => Math.min(Math.max(y, VIEW.y0), VIEW.y1)
const px = (x: number) => (clampX(x) - VIEW.x0) * S
const py = (y: number) => (VIEW.y1 - clampY(y)) * S
const off = (p: { x: number; y: number }) => p.x !== clampX(p.x) || p.y !== clampY(p.y)
const at = (p: { x: number; y: number } | null) => (p ? `${p.x.toFixed(1)}, ${p.y.toFixed(1)}` : '–')

/** The marks of the attack map, so the two read alike: the point won is the
 * filled accent dot, the ball kept in play a neutral ring, the error a cross. */
const KIND_COLOR: Record<ServeKind, string> = { ace: 'var(--accent)', in: 'var(--muted)', error: 'var(--bad)' }

function Glyph({ kind, x, y }: { kind: ServeKind; x: number; y: number }) {
  const c = KIND_COLOR[kind]
  if (kind === 'ace') return <circle cx={x} cy={y} r={6} fill={c} stroke="var(--surface)" strokeWidth={2} />
  if (kind === 'in') return <circle cx={x} cy={y} r={4} fill="var(--surface)" stroke={c} strokeWidth={2} />
  return <path d={`M${x - 4} ${y - 4}L${x + 4} ${y + 4}M${x - 4} ${y + 4}L${x + 4} ${y - 4}`}
               stroke={c} strokeWidth={2.5} strokeLinecap="round" />
}

const KINDS: ServeKind[] = ['ace', 'in', 'error']
const PLURAL: Record<ServeKind, string> = { ace: 'Aces', in: 'In play', error: 'Errors' }
// drawn last = on top: the aces are what the map is read for
const ORDER: Record<ServeKind, number> = { in: 0, error: 1, ace: 2 }

/** Every serve as a mark where it came down: where the receiver played it, or
 * where the ball landed when nobody touched it. Positions are best effort
 * from one low camera, so the serve under the pointer (or the tapped one)
 * shows the area it may really be in: depth is the weak axis. */
export function ServeMap({ serves }: { serves: Serve[] }) {
  const [kind, setKind] = useState<ServeKind | 'all'>('all')
  const [hover, setHover] = useState<number | null>(null)
  const [picked, setPicked] = useState<number | null>(null)

  const all = servePoints(serves)
  const count = (k: ServeKind) => all.filter((q) => q.kind === k).length
  const shown = all.filter((q) => (kind === 'all' || q.kind === kind) && q.end)
    .sort((a, b) => ORDER[a.kind] - ORDER[b.kind]) as (ServePoint & { end: NonNullable<ServePoint['end']> })[]
  const active = hover ?? picked
  const tip = active === null ? null : shown[active] ?? null
  const unplaced = all.filter((q) => (kind === 'all' || q.kind === kind) && !q.end).length

  const reset = () => {
    setHover(null)
    setPicked(null)
  }
  const options: Option<ServeKind | 'all'>[] = [
    { key: 'all', label: <>All <span className="num muted">{all.length}</span></> },
    ...KINDS.map((k) => ({
      key: k, label: <>{PLURAL[k]} <span className="num muted">{count(k)}</span></>, disabled: count(k) === 0 && kind !== k,
    })),
  ]
  const keys = (e: KeyboardEvent) => {
    if (e.key === 'Escape') reset()
    const step = e.key === 'ArrowRight' ? 1 : e.key === 'ArrowLeft' ? -1 : 0
    if (!step || shown.length === 0) return
    e.preventDefault()
    setPicked(((picked ?? (step > 0 ? -1 : 0)) + step + shown.length) % shown.length)
  }
  const hit = (i: number) => ({
    onPointerEnter: (e: PointerEvent) => e.pointerType === 'mouse' && setHover(i),
    onPointerLeave: () => setHover(null),
    onClick: (e: MouseEvent) => {
      e.stopPropagation()
      setPicked(picked === i ? null : i)
    },
  })
  const empty = kind === 'all' ? 'No serve positions yet' : `No ${PLURAL[kind].toLowerCase()} to show`

  return (
    <div className="serve-map">
      <div className="filters">
        <Segmented options={options} value={kind} label="Outcome" onChange={(k) => { setKind(k); reset() }} />
      </div>
      <div className="chart court">
        <svg viewBox={`0 0 ${W} ${H}`} role="img" tabIndex={0} onKeyDown={keys} onClick={reset}
             aria-label={`${shown.length} serves marked where they came down on the opponents' half. Arrow keys step through them.`}>
          <rect x={px(0)} y={py(16)} width={8 * S} height={8 * S} rx={2} fill="var(--surface-2)" stroke="var(--axis)" />
          <rect x={px(0) - 6} y={py(NET_Y) - 2} width={8 * S + 12} height={4} rx={2} fill="var(--ink-2)" />
          <text x={px(8) + 12} y={py(NET_Y) + 4}>net</text>
          <text x={px(4)} y={py(16) - 8} textAnchor="middle">their baseline</text>
          <text x={px(4)} y={py(NET_Y) + 18} textAnchor="middle">server's side</text>
          {shown.length === 0 && <text x={px(4)} y={py(12)} textAnchor="middle" className="court-empty">{empty}</text>}
          {tip && tip.s.ex != null && tip.s.ey != null && (
            <ellipse cx={px(tip.end.x)} cy={py(tip.end.y)} rx={tip.s.ex * S} ry={tip.s.ey * S} fill={KIND_COLOR[tip.kind]} opacity={0.18} />
          )}
          {shown.map((q, i) => (
            <g key={i} opacity={active !== null && active !== i ? 0.2 : 1}>
              <Glyph kind={q.kind} x={px(q.end.x)} y={py(q.end.y)} />
            </g>
          ))}
          {shown.map((q, i) => (
            <circle key={i} {...hit(i)} cx={px(q.end.x)} cy={py(q.end.y)} r={12} fill="transparent" style={{ cursor: 'pointer' }} />
          ))}
        </svg>
        {tip && (
          <div className="tooltip tooltip-wrap" style={{
            left: `${Math.min(70, Math.max(30, (px(tip.end.x) / W) * 100))}%`, top: `${(py(tip.end.y) / H) * 100}%`,
          }}>
            <strong>{SERVE_LABEL[tip.kind]}</strong>
            {tip.s.to && <> · taken by {tip.s.to}</>}
            {tip.s.d && <> · {formatDate(tip.s.d)}</>}
            <br />
            <span className="muted">
              {serveSpotWords(tip)}
              {off(tip.end) && ' · beyond the map'}
              {tip.kind === 'error' && tip.s.src === 'ground' && tip.s.in !== false && !tip.end.short && ' · line too close to call'}
              {tip.s.ex != null && tip.s.ey != null && <><br />±{tip.s.ex.toFixed(1)} m across, ±{tip.s.ey.toFixed(1)} m along</>}
            </span>
          </div>
        )}
      </div>
      <div className="legend">
        {KINDS.filter((k) => kind === 'all' || kind === k).map((k) => (
          <span key={k}>
            <svg width={16} height={16} viewBox="0 0 16 16" style={{ marginRight: 5, verticalAlign: -3 }} aria-hidden="true">
              <Glyph kind={k} x={8} y={8} />
            </svg>{SERVE_LABEL[k]}
          </span>
        ))}
      </div>
      {unplaced > 0 && (
        <p className="muted small" style={{ margin: '6px 0 0' }}>
          {unplaced} of {unplaced + shown.length} without a position are not drawn: the receiver was not seen, or the ball left the picture.
        </p>
      )}
      <details className="table-view">
        <summary>Table</summary>
        <div className="table-wrap">
          <table>
            <thead>
              <tr><th className="left">Date</th><th className="left">Outcome</th><th className="left">Taken by</th><th>Came down (m)</th></tr>
            </thead>
            <tbody>
              {all.map((q, i) => (
                <tr key={i}>
                  <td className="left">{q.s.d ? formatDate(q.s.d) : '–'}</td>
                  <td className="left">{SERVE_LABEL[q.kind]}</td>
                  <td className="left">{q.s.to ?? '–'}</td>
                  <td>{at(q.end)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </div>
  )
}
