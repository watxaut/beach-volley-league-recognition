import { useEffect, useId, useLayoutEffect, useRef, useState, type KeyboardEvent, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { GLOSSARY, type Term, type TermKey } from '../lib/glossary'
import { GRADE_HINT, GRADE_WORD, type Grade } from '../lib/grades'
import type { MatchStatus, Team } from '../lib/types'

export function Loading() {
  return <p className="muted">Loading…</p>
}

export function ErrorBox({ error }: { error: string | null }) {
  return error ? <div className="error" role="alert">{error}</div> : null
}

/** `quiet`: the value is a count standing in for a rate that cannot be shown
 * yet ("1/8"), so it is set smaller than a real headline number. */
export function Tile({ label, value, hint, sub, info, quiet }: {
  label: string; value: ReactNode; hint?: string; sub?: ReactNode; info?: ReactNode; quiet?: boolean
}) {
  return (
    <div className="tile" title={hint}>
      <div className={`tile-value${quiet ? ' tile-value-quiet' : ''}`}>{value}</div>
      <div className="tile-label">{label}{info}</div>
      {sub && <div className="tile-sub">{sub}</div>}
    </div>
  )
}

/** A small "i" that opens its text on tap, on click, on hover and on keyboard
 * focus; Escape or a tap elsewhere closes it. Phones have no hover, so it is a
 * real button. Nothing a reader needs to act on belongs in here: the count
 * behind a rate stays on the page. */
export function Info({ label, children }: { label: string; children: ReactNode }) {
  const [hover, setHover] = useState(false)
  const [pinned, setPinned] = useState(false)
  const wrap = useRef<HTMLSpanElement>(null)
  const panel = useRef<HTMLSpanElement>(null)
  const id = useId()
  const open = hover || pinned

  // Keep the panel inside the screen: centred on the button where there is
  // room, shifted where there is not, above when the bottom is too close.
  useLayoutEffect(() => {
    if (!open || !wrap.current || !panel.current) return
    const b = wrap.current.getBoundingClientRect()
    const w = panel.current.offsetWidth
    const h = panel.current.offsetHeight
    const vw = document.documentElement.clientWidth
    const left = Math.min(Math.max(b.left + b.width / 2 - w / 2, 12), Math.max(12, vw - w - 12))
    panel.current.style.left = `${left - b.left}px`
    panel.current.dataset.side = b.bottom + h + 12 > window.innerHeight && b.top - h - 12 > 0 ? 'up' : 'down'
  }, [open])

  useEffect(() => {
    if (!open) return
    const away = (e: PointerEvent) => {
      if (!wrap.current?.contains(e.target as Node)) setPinned(false)
    }
    const esc = (e: globalThis.KeyboardEvent) => {
      if (e.key === 'Escape') {
        setPinned(false)
        setHover(false)
      }
    }
    document.addEventListener('pointerdown', away)
    document.addEventListener('keydown', esc)
    return () => {
      document.removeEventListener('pointerdown', away)
      document.removeEventListener('keydown', esc)
    }
  }, [open])

  return (
    <span className="info" ref={wrap}
          onPointerEnter={(e) => e.pointerType === 'mouse' && setHover(true)}
          onPointerLeave={() => setHover(false)}>
      <button type="button" className="info-btn" aria-label={label} aria-expanded={open}
              aria-describedby={open ? id : undefined}
              onClick={() => setPinned((p) => !p)}
              onFocus={(e) => e.currentTarget.matches(':focus-visible') && setHover(true)}
              onBlur={() => setHover(false)}>i</button>
      {open && <span className="info-panel" role="tooltip" id={id} ref={panel}>{children}</span>}
    </span>
  )
}

/** The hint of a stat, from the glossary: what it is, how it is measured, how
 * far to trust it. `children` add what is specific to this value (its range). */
export function StatInfo({ term, children }: { term: TermKey; children?: ReactNode }) {
  const t: Term = GLOSSARY[term]
  return (
    <Info label={`About ${t.label}`}>
      <strong>{t.label}</strong>
      <span>{t.what}</span>
      {t.how && <span>{t.how}</span>}
      {children && <span>{children}</span>}
      <span className="info-foot">
        <span title={GRADE_HINT[t.grade]}>{GRADE_WORD[t.grade]}</span> · <Link to="/measure">How we measure</Link>
      </span>
    </Info>
  )
}

/** The visible mark of a stat that is not a plain fact (grade B or C). */
export function Approx({ grade }: { grade: Exclude<Grade, 'A'> }) {
  return <span className="tag-approx" title={GRADE_HINT[grade]}>{GRADE_WORD[grade].toLowerCase()}</span>
}

/** The grade of a stat as a letter; links to the page that explains each. */
export function GradeBadge({ grade }: { grade: Grade }) {
  return <Link to="/measure" className={`grade grade-${grade}`} title={`${GRADE_HINT[grade]} · how we measure`}
               aria-label={GRADE_HINT[grade]}>{grade}</Link>
}

export interface Option<T extends string> {
  key: T
  label: ReactNode
  disabled?: boolean
  title?: string
}

/** The sections of a page, one shown at a time (arrow keys move between them). */
export function Tabs<T extends string>({ tabs, value, onChange, label }: {
  tabs: Option<T>[]; value: T; onChange: (key: T) => void; label: string
}) {
  const move = (e: KeyboardEvent<HTMLDivElement>) => {
    const step = e.key === 'ArrowRight' ? 1 : e.key === 'ArrowLeft' ? -1 : 0
    if (!step) return
    const i = tabs.findIndex((t) => t.key === value)
    const next = tabs[(i + step + tabs.length) % tabs.length]
    onChange(next.key)
    e.currentTarget.querySelector<HTMLElement>(`[data-key="${next.key}"]`)?.focus()
  }
  return (
    <div className="tabs" role="tablist" aria-label={label} onKeyDown={move}>
      {tabs.map((t) => (
        <button key={t.key} type="button" role="tab" className="tab" data-key={t.key}
                aria-selected={t.key === value} tabIndex={t.key === value ? 0 : -1}
                onClick={() => onChange(t.key)}>{t.label}</button>
      ))}
    </div>
  )
}

/** A few exclusive choices in one row: a chart's reference, a map's filter. */
export function Segmented<T extends string>({ options, value, onChange, label }: {
  options: Option<T>[]; value: T; onChange: (key: T) => void; label: string
}) {
  return (
    <div className="seg" role="group" aria-label={label}>
      {options.map((o) => (
        <button key={o.key} type="button" aria-pressed={o.key === value} disabled={o.disabled} title={o.title}
                onClick={() => onChange(o.key)}>{o.label}</button>
      ))}
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
