import { useEffect, useId, useRef, useState } from 'react'
import type { PointRow } from '../lib/types'

/** Score margin (A − B) after every point: above the line team A leads,
 * below team B. One series, so no legend box — the caption names it; the
 * two washes are the diverging pair (team colours). Hover = crosshair +
 * readout of the exact score. */
export function ScoreWorm({ points, nameA, nameB }: { points: PointRow[]; nameA: string; nameB: string }) {
  const [hover, setHover] = useState<number | null>(null)
  // Draw at the container's real width so 11px labels stay 11px on phones.
  const box = useRef<HTMLDivElement>(null)
  const [W, setW] = useState(640)
  useEffect(() => {
    const el = box.current
    if (!el) return
    const ro = new ResizeObserver(([e]) => setW(Math.max(280, Math.round(e.contentRect.width))))
    ro.observe(el)
    return () => ro.disconnect()
  }, [])
  // ids inside url(#…) must be plain: strip useId's punctuation
  const clip = `worm${useId().replace(/[^a-zA-Z0-9_-]/g, '')}`
  if (points.length < 2) return null
  const H = W < 500 ? 140 : 170
  const pad = { l: 28, r: 8, t: 10, b: 20 }
  const margins = [0, ...points.map((p) => p.score_a_after - p.score_b_after)]
  const maxAbs = Math.max(3, ...margins.map(Math.abs))
  const x = (i: number) => pad.l + (i / (margins.length - 1)) * (W - pad.l - pad.r)
  const y = (m: number) => pad.t + ((maxAbs - m) / (2 * maxAbs)) * (H - pad.t - pad.b)
  const line = margins.map((m, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)},${y(m).toFixed(1)}`).join(' ')
  const area = `${line} L${x(margins.length - 1)},${y(0)} L${x(0)},${y(0)} Z`
  const ticks = [maxAbs, 0, -maxAbs]

  const onMove = (e: React.PointerEvent<SVGSVGElement>) => {
    const rect = e.currentTarget.getBoundingClientRect()
    const px = ((e.clientX - rect.left) / rect.width) * W
    const i = Math.round(((px - pad.l) / (W - pad.l - pad.r)) * (margins.length - 1))
    setHover(i >= 1 && i < margins.length ? i : null)
  }
  const hp = hover !== null ? points[hover - 1] : null

  return (
    <div className="chart" ref={box}>
      <svg viewBox={`0 0 ${W} ${H}`} onPointerMove={onMove} onPointerLeave={() => setHover(null)}
           role="img" aria-label={`Score margin after each point, ${nameA} versus ${nameB}`}>
        <defs>
          <clipPath id={`${clip}a`}><rect x={0} y={0} width={W} height={y(0)} /></clipPath>
          <clipPath id={`${clip}b`}><rect x={0} y={y(0)} width={W} height={H} /></clipPath>
        </defs>
        {ticks.map((t) => (
          <g key={t}>
            <line x1={pad.l} x2={W - pad.r} y1={y(t)} y2={y(t)}
                  stroke={t === 0 ? 'var(--axis)' : 'var(--grid)'} strokeWidth={1} />
            <text x={pad.l - 6} y={y(t) + 4} textAnchor="end">{t > 0 ? `+${t}` : t}</text>
          </g>
        ))}
        <path d={area} fill="var(--team-a-wash)" clipPath={`url(#${clip}a)`} />
        <path d={area} fill="var(--team-b-wash)" clipPath={`url(#${clip}b)`} />
        <path d={line} fill="none" stroke="var(--ink-2)" strokeWidth={2} strokeLinejoin="round" />
        <text x={pad.l + 4} y={pad.t + 10} style={{ fill: 'var(--team-a)', fontWeight: 700 }}>{nameA} ahead</text>
        <text x={pad.l + 4} y={H - pad.b - 4} style={{ fill: 'var(--team-b)', fontWeight: 700 }}>{nameB} ahead</text>
        <text x={W - pad.r} y={H - 4} textAnchor="end">point →</text>
        {hover !== null && (
          <g>
            <line x1={x(hover)} x2={x(hover)} y1={pad.t} y2={H - pad.b} stroke="var(--muted)" strokeWidth={1} />
            <circle cx={x(hover)} cy={y(margins[hover])} r={4.5} fill="var(--ink)" stroke="var(--surface)" strokeWidth={2} />
          </g>
        )}
      </svg>
      {hp && (
        <div className="tooltip" style={{ left: `${(x(hover!) / W) * 100}%`, top: `${(y(margins[hover!]) / H) * 100}%` }}>
          <strong>{hp.score_a_after}–{hp.score_b_after}</strong> <span className="muted">after point {hp.point_no}</span>
        </div>
      )}
    </div>
  )
}
