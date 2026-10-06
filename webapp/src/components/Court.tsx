import { useState } from 'react'
import { LANDING_LABEL, landingError, landingKind, landingSummary, type LandingKind } from '../lib/landings'
import type { Landing } from '../lib/types'

/** Attack origin, 3×3 zones of the attacker's own half, drawn as seen from
 * behind their own baseline (net at the top). Zone numbers follow
 * CourtCalibration.world_point_to_zone: 1-3 = net row, 7-9 = back row,
 * numbered from the net looking back, so left-to-right reads 3 2 1. */
const LAYOUT = [[3, 2, 1], [6, 5, 4], [9, 8, 7]]
const HEAT = ['var(--heat-0)', 'var(--heat-1)', 'var(--heat-2)', 'var(--heat-3)', 'var(--heat-4)']

/** Both court maps share one frame so they draw at the same size, courts
 * aligned: metres around the opponents' half (attacker's frame: x 0..8 from
 * the attacker's left, y 8 = net .. 16 = their baseline), with room for
 * balls that went out. */
const VIEW = { x0: -2.5, x1: 10.5, y0: 7, y1: 18.5 }
const PX_PER_M = 24
const FRAME_W = (VIEW.x1 - VIEW.x0) * PX_PER_M
const FRAME_H = (VIEW.y1 - VIEW.y0) * PX_PER_M
const MAX_WIDTH = 420

/** A small "i" that opens its text on hover or keyboard focus. */
function InfoTip({ children }: { children: React.ReactNode }) {
  return (
    <span className="info">
      <button type="button" className="info-btn" aria-label="How to read this map">i</button>
      <span className="info-panel" role="tooltip">{children}</span>
    </span>
  )
}

export function ZoneGrid({ counts }: { counts: Record<string, number> }) {
  const [hover, setHover] = useState<number | null>(null)
  const max = Math.max(1, ...Object.values(counts))
  const total = Object.values(counts).reduce((a, b) => a + b, 0)
  const cell = 8 * PX_PER_M / 3
  const gx = -VIEW.x0 * PX_PER_M
  const gy = (VIEW.y1 - 16) * PX_PER_M
  return (
    <div style={{ maxWidth: MAX_WIDTH }}>
      <div className="chart">
        <svg viewBox={`0 0 ${FRAME_W} ${FRAME_H}`} role="img" aria-label="Attacks by zone of origin">
          <rect x={gx - 6} y={gy - 14} width={8 * PX_PER_M + 12} height={4} rx={2} fill="var(--ink-2)" />
          <text x={gx + 8 * PX_PER_M + 12} y={gy - 9}>net</text>
          {LAYOUT.map((row, r) => row.map((zone, c) => {
            const n = counts[String(zone)] ?? 0
            const step = n === 0 ? -1 : Math.min(4, Math.floor((n / max) * 4.999))
            return (
              <g key={zone} onPointerEnter={() => setHover(zone)} onPointerLeave={() => setHover(null)}>
                <rect x={gx + c * cell + 1} y={gy + r * cell + 1} width={cell - 2} height={cell - 2} rx={4}
                      fill={step < 0 ? 'var(--surface-2)' : HEAT[step]} />
                <text x={gx + c * cell + cell / 2} y={gy + r * cell + cell / 2 + 4} textAnchor="middle"
                      style={{ fill: step >= 3 ? 'var(--surface)' : 'var(--ink)', fontWeight: 700, fontSize: 13 }}>
                  {n || ''}
                </text>
              </g>
            )
          }))}
        </svg>
        {hover !== null && (
          <div className="tooltip" style={{
            left: `${((gx + (LAYOUT.flat().indexOf(hover) % 3 + 0.5) * cell) / FRAME_W) * 100}%`,
            top: `${((gy + Math.floor(LAYOUT.flat().indexOf(hover) / 3) * cell) / FRAME_H) * 100}%`,
          }}>
            Zone {hover}: <strong>{counts[String(hover)] ?? 0}</strong> of {total} attacks
          </div>
        )}
      </div>
    </div>
  )
}

const NET_Y = 8
const KIND_COLOR: Record<LandingKind, string> = {
  kill: 'var(--good)', dug: 'var(--accent)', out: 'var(--bad)', net: 'var(--bad)',
  error: 'var(--bad)', unresolved: 'var(--muted)',
}

function Glyph({ kind, x, y }: { kind: LandingKind; x: number; y: number }) {
  const c = KIND_COLOR[kind]
  if (kind === 'kill') return <circle cx={x} cy={y} r={4.5} fill={c} stroke="var(--surface)" strokeWidth={1.5} />
  if (kind === 'dug') return <circle cx={x} cy={y} r={3.5} fill="var(--surface)" stroke={c} strokeWidth={2} />
  if (kind === 'unresolved') return <circle cx={x} cy={y} r={3} fill={c} />
  return <path d={`M${x - 4} ${y - 4}L${x + 4} ${y + 4}M${x - 4} ${y + 4}L${x + 4} ${y - 4}`}
               stroke={c} strokeWidth={2.5} strokeLinecap="round" />
}

/** Where attacks came down on the opponents' half. Every spot is a best
 * effort read from a low camera, so each one is drawn with the area it may
 * really be in (`ex` across, `ey` along the court; depth is the weak axis). */
export function LandingMap({ landings }: { landings: Landing[] }) {
  const [hover, setHover] = useState<number | null>(null)
  const s = PX_PER_M
  const W = FRAME_W
  const H = FRAME_H
  const px = (x: number) => (Math.min(Math.max(x, VIEW.x0), VIEW.x1) - VIEW.x0) * s
  const py = (y: number) => (VIEW.y1 - Math.min(Math.max(y, VIEW.y0), VIEW.y1)) * s
  // A ball that came down on the far side cannot have landed short of the net:
  // such a spot is depth error, so it is drawn at the net (its uncertainty
  // area still shows how far off it may be).
  const placed = landings.flatMap((l) => {
    if (l.x == null || l.y == null) return []
    const kind = landingKind(l)
    const short = kind !== 'net' && l.y < NET_Y
    return [{
      l, kind, short, cx: px(l.x), cy: py(short ? NET_Y : l.y),
      off: l.x < VIEW.x0 || l.x > VIEW.x1 || l.y < VIEW.y0 || l.y > VIEW.y1,
    }]
  })
  const { counts, unplaced } = landingSummary(landings)
  const noError = placed.filter((p) => landingError(p.l) === null).length
  const tip = hover === null ? null : placed[hover]
  return (
    <div style={{ maxWidth: MAX_WIDTH }}>
      <div className="chart">
        <svg viewBox={`0 0 ${W} ${H}`} role="img"
             aria-label="Where attacks came down on the opponents' half, each with its position uncertainty">
          <rect x={px(0)} y={py(16)} width={8 * s} height={8 * s} rx={2} fill="var(--surface-2)" stroke="var(--axis)" />
          <rect x={px(0) - 6} y={py(8) - 2} width={8 * s + 12} height={4} rx={2} fill="var(--ink-2)" />
          <text x={px(8) + 12} y={py(8) + 4}>net</text>
          <text x={px(8) + 8} y={py(16) + 4}>baseline</text>
          {placed.map((p, i) => p.l.ex != null && p.l.ey != null && (
            <ellipse key={i} cx={p.cx} cy={p.cy} rx={p.l.ex * s} ry={p.l.ey * s}
                     fill={KIND_COLOR[p.kind]} opacity={hover === i ? 0.4 : 0.2} />
          ))}
          {placed.map((p, i) => (
            <g key={i} onPointerEnter={() => setHover(i)} onPointerLeave={() => setHover(null)}>
              <circle cx={p.cx} cy={p.cy} r={9} fill="transparent" />
              <Glyph kind={p.kind} x={p.cx} y={p.cy} />
            </g>
          ))}
        </svg>
        {tip && (
          <div className="tooltip" style={{ left: `${(tip.cx / W) * 100}%`, top: `${(tip.cy / H) * 100}%` }}>
            <strong>{LANDING_LABEL[tip.kind]}</strong>
            {tip.kind === 'dug' && ' · where the defender played it'}
            {tip.kind === 'error' && tip.l.in == null && ' · line too close to call'}
            {tip.short && ' · estimated short of the net, drawn at it'}
            {tip.off && ' · beyond the map'}
            <br />
            <span className="muted">{landingError(tip.l) ?? 'position error not recorded'}</span>
          </div>
        )}
      </div>
      <div className="legend">
        {counts.map(([kind, n]) => (
          <span key={kind}>
            <svg width={12} height={12} viewBox="0 0 12 12" style={{ marginRight: 5, verticalAlign: -1 }} aria-hidden="true">
              <Glyph kind={kind} x={6} y={6} />
            </svg>
            <strong className="num">{n}</strong> {LANDING_LABEL[kind].toLowerCase()}{n > 1 && (kind === 'kill' || kind === 'error') ? 's' : ''}
          </span>
        ))}
        <InfoTip>
          Best-effort positions from a low camera. The shaded area around each mark is where that ball may
          really have come down; depth (up and down here) is the least certain. A dug ball is drawn where the
          defender played it.
          {unplaced > 0 && <><br />{unplaced} of {landings.length} attacks have no position and are not on the map.</>}
          {noError > 0 && <><br />{noError} were published before the uncertainty was recorded.</>}
        </InfoTip>
      </div>
    </div>
  )
}
