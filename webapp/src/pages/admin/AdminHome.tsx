import { Link, NavLink, Outlet } from 'react-router-dom'
import { useApp, useLoad, useMatchList } from '../../app/state'
import { Card, ErrorBox, Loading, StatusBadge } from '../../components/ui'
import { formatDate, matchLabel } from '../../lib/format'

export function AdminLayout() {
  const { api, isAdmin } = useApp()
  const open = useLoad(async () => (isAdmin ? (await api.allFeedback()).filter((r) => r.status === 'open').length : 0),
    [isAdmin])
  if (!isAdmin) return <p>Admins only.</p>
  const link = ({ isActive }: { isActive: boolean }) => (isActive ? 'active' : undefined)
  return (
    <>
      <nav className="nav" style={{ marginBottom: 16 }} aria-label="Admin">
        <NavLink to="/admin" end className={link}>Review queue</NavLink>
        <NavLink to="/admin/players" className={link}>Players & accounts</NavLink>
        <NavLink to="/admin/scoring" className={link}>Fantasy scoring</NavLink>
        <NavLink to="/admin/feedback" className={link}>Feedback{open.data ? ` (${open.data})` : ''}</NavLink>
      </nav>
      <Outlet context={open.reload} />
    </>
  )
}

export function AdminMatches() {
  const list = useMatchList()
  if (list.loading || !list.data) return <><ErrorBox error={list.error} /><Loading /></>
  const { matches, participants } = list.data
  const order = { draft: 0, published: 1, hidden: 2 }
  const rows = [...matches].sort((a, b) => order[a.status] - order[b.status])
  return (
    <Card title="Matches" action={<span className="muted small">New videos arrive as drafts</span>}>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th className="left">Status</th>
              <th className="left">Date</th>
              <th className="left">Match</th>
              <th>Score</th>
              <th title="Slots still without a player">Unassigned</th>
              <th title="Points the reconstruction flagged for a look">Flags</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((m) => {
              const open = participants.filter((p) => p.match_id === m.id && !p.player_id).length
              const flags = Object.keys(m.checks?.flagged_points ?? {}).length
              return (
                <tr key={m.id}>
                  <td className="left"><StatusBadge status={m.status} />{m.status === 'published' && <span className="muted">live</span>}</td>
                  <td className="left">{formatDate(m.match_date, m.start_time)}</td>
                  <td className="left"><Link to={`/admin/matches/${m.match_key}`}>{matchLabel(m)}</Link></td>
                  <td>{m.score_a}–{m.score_b}</td>
                  <td className={open ? 'strong' : undefined}>{open || '–'}</td>
                  <td>{flags || '–'}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      {rows.length === 0 && <p className="muted">No matches yet — run <code>make publish</code> on the laptop.</p>}
    </Card>
  )
}
