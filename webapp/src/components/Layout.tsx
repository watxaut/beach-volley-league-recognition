import { Link, NavLink, Outlet, useLocation } from 'react-router-dom'
import { useApp, useLoad } from '../app/state'
import { FeedbackButton } from './Feedback'

export function Layout() {
  const { api, isAdmin, me, demo } = useApp()
  const { pathname } = useLocation()
  // There is no home page any more, so the admins' "waiting for review" count
  // rides on the Admin link (re-read on every page change: one small select).
  const drafts = useLoad(async () => (isAdmin ? (await api.matches()).filter((m) => m.status === 'draft').length : 0),
    [isAdmin, pathname])
  const link = ({ isActive }: { isActive: boolean }) => (isActive ? 'active' : undefined)
  return (
    <>
      {demo && <div className="demo-banner">Demo mode: synthetic data, nothing is saved</div>}
      <header className="topbar">
        <div className="topbar-inner">
          <Link to="/" className="brand"><span className="brand-dot" aria-hidden />Beach League</Link>
          <nav className="nav" aria-label="Main">
            {me && <NavLink to={`/players/${me.id}`} className={link}>My stats</NavLink>}
            <NavLink to="/league" className={link}>League</NavLink>
            <NavLink to="/matches" className={link}>Matches</NavLink>
            <NavLink to="/measure" className={link}>How we measure</NavLink>
            {isAdmin && (
              <NavLink to="/admin" className={link}
                       title={drafts.data ? `${drafts.data} match${drafts.data > 1 ? 'es' : ''} waiting for review` : undefined}>
                Admin{drafts.data ? ` (${drafts.data})` : ''}
              </NavLink>
            )}
          </nav>
          <FeedbackButton />
          <NavLink to="/settings" className={({ isActive }) => `settings-button${isActive ? ' active' : ''}`}
                   aria-label="Settings">
            <GearIcon />
            <span className="settings-label">Settings</span>
          </NavLink>
        </div>
      </header>
      <main>
        <Outlet />
      </main>
    </>
  )
}

function GearIcon() {
  return (
    <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2"
         strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false">
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
    </svg>
  )
}
