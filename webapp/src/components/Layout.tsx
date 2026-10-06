import { Link, NavLink, Outlet } from 'react-router-dom'
import { useApp } from '../app/state'

export function Layout() {
  const { isAdmin, me, session, demo } = useApp()
  const link = ({ isActive }: { isActive: boolean }) => (isActive ? 'active' : undefined)
  return (
    <>
      {demo && <div className="demo-banner">Demo mode: synthetic data, nothing is saved</div>}
      <header className="topbar">
        <div className="topbar-inner">
          <Link to="/" className="brand"><span className="brand-dot" aria-hidden />Beach League</Link>
          <nav className="nav" aria-label="Main">
            <NavLink to="/" end className={link}>Home</NavLink>
            <NavLink to="/league" className={link}>League</NavLink>
            <NavLink to="/matches" className={link}>Matches</NavLink>
            <NavLink to="/measure" className={link}>How we measure</NavLink>
            {isAdmin && <NavLink to="/admin" className={link}>Admin</NavLink>}
          </nav>
          <Link to="/settings" className="userchip" title={session?.email}>
            {me?.display_name ?? session?.email?.split('@')[0] ?? 'Me'}
          </Link>
        </div>
      </header>
      <main>
        <Outlet />
      </main>
    </>
  )
}
