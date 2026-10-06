import { useState } from 'react'

/** Attack origin, 3×3 zones of the attacker's own half, drawn as seen from
 * behind their own baseline (net at the top). Zone numbers follow
 * CourtCalibration.world_point_to_zone: 1-3 = net row, 7-9 = back row,
 * numbered from the net looking back, so left-to-right reads 3 2 1. */
const LAYOUT = [[3, 2, 1], [6, 5, 4], [9, 8, 7]]
const HEAT = ['var(--heat-0)', 'var(--heat-1)', 'var(--heat-2)', 'var(--heat-3)', 'var(--heat-4)']

export function ZoneGrid({ counts }: { counts: Record<string, number> }) {
  const [hover, setHover] = useState<number | null>(null)
  const max = Math.max(1, ...Object.values(counts))
  const total = Object.values(counts).reduce((a, b) => a + b, 0)
  const cell = 64
  return (
    <div className="chart" style={{ maxWidth: 3 * cell + 4 }}>
      <svg viewBox={`0 0 ${3 * cell + 4} ${3 * cell + 22}`} role="img" aria-label="Attacks by zone of origin">
        <rect x={0} y={0} width={3 * cell + 4} height={4} rx={2} fill="var(--ink-2)" />
        <text x={(3 * cell + 4) / 2} y={16} textAnchor="middle">net</text>
        {LAYOUT.map((row, r) => row.map((zone, c) => {
          const n = counts[String(zone)] ?? 0
          const step = n === 0 ? -1 : Math.min(4, Math.floor((n / max) * 4.999))
          return (
            <g key={zone} onPointerEnter={() => setHover(zone)} onPointerLeave={() => setHover(null)}>
              <rect x={2 + c * cell} y={22 + r * cell} width={cell - 2} height={cell - 2} rx={4}
                    fill={step < 0 ? 'var(--surface-2)' : HEAT[step]} />
              <text x={2 + c * cell + (cell - 2) / 2} y={22 + r * cell + (cell - 2) / 2 + 4} textAnchor="middle"
                    style={{ fill: step >= 3 ? 'var(--surface)' : 'var(--ink)', fontWeight: 700, fontSize: 13 }}>
                {n || ''}
              </text>
            </g>
          )
        }))}
      </svg>
      {hover !== null && (
        <div className="tooltip" style={{ left: '50%', top: 22 }}>
          Zone {hover}: <strong>{counts[String(hover)] ?? 0}</strong> of {total} attacks
        </div>
      )}
    </div>
  )
}

/** Where attacks came down on the opponents' half, attacker's frame:
 * y 8 (net) … 16 (their baseline), x 0..8 from the attacker's left. */
export function LandingMap({ landings }: {
  landings: { x: number | null; y: number; in: boolean | null; outcome: string | null }[]
}) {
  const s = 22
  const W = 8 * s + 4
  const H = 8 * s + 22
  const placed = landings.filter((l) => l.x !== null)
  return (
    <div className="chart" style={{ maxWidth: W }}>
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Landing points of attacks on the opponents' half">
        <rect x={2} y={2} width={8 * s} height={8 * s} rx={4} fill="var(--surface-2)" stroke="var(--axis)" />
        <rect x={0} y={8 * s + 2} width={W} height={4} rx={2} fill="var(--ink-2)" />
        <text x={W / 2} y={H - 2} textAnchor="middle">net</text>
        {placed.map((l, i) => (
          <circle key={i} cx={2 + (l.x as number) * s} cy={2 + (16 - l.y) * s} r={5}
                  fill={l.outcome === 'kill' ? 'var(--good)' : l.in === false ? 'var(--bad)' : 'var(--accent)'}
                  stroke="var(--surface)" strokeWidth={2}>
            <title>{l.outcome === 'kill' ? 'kill' : l.in === false ? 'out' : 'in play'}</title>
          </circle>
        ))}
      </svg>
      <div className="legend">
        <span><span className="team-dot" style={{ background: 'var(--good)' }} />kill</span>
        <span><span className="team-dot" style={{ background: 'var(--accent)' }} />in play</span>
        <span><span className="team-dot" style={{ background: 'var(--bad)' }} />out</span>
        {landings.length > placed.length && <span className="muted">{landings.length - placed.length} with depth only</span>}
      </div>
    </div>
  )
}
