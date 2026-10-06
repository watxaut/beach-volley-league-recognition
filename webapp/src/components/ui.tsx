import type { ReactNode } from 'react'
import type { MatchStatus, Team } from '../lib/types'

export function Loading() {
  return <p className="muted">Loading…</p>
}

export function ErrorBox({ error }: { error: string | null }) {
  return error ? <div className="error" role="alert">{error}</div> : null
}

export function Tile({ label, value, hint }: { label: string; value: ReactNode; hint?: string }) {
  return (
    <div className="tile" title={hint}>
      <div className="tile-value">{value}</div>
      <div className="tile-label">{label}</div>
    </div>
  )
}

export function StatusBadge({ status }: { status: MatchStatus }) {
  if (status === 'published') return null
  return <span className={`badge badge-${status}`}>{status}</span>
}

export function TeamDot({ team }: { team: Team | null | undefined }) {
  if (!team) return null
  return <span className={`team-dot team-${team.toLowerCase()}`} aria-label={`team ${team}`} />
}

export function Card({ title, action, children }: { title?: ReactNode; action?: ReactNode; children: ReactNode }) {
  return (
    <section className="card">
      {(title || action) && (
        <div className="card-head">
          {title && <h2>{title}</h2>}
          {action}
        </div>
      )}
      {children}
    </section>
  )
}
