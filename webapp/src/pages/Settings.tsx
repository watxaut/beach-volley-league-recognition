import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useApp } from '../app/state'
import { Card, ErrorBox } from '../components/ui'
import { explainError } from '../lib/api'

export function Settings() {
  const { api, session, me, profile, refreshMe } = useApp()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function togglePublic(next: boolean) {
    setBusy(true)
    setError(null)
    try {
      await api.setMyPrivacy(next)
      await refreshMe()
    } catch (err) {
      setError(explainError(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <h1>Settings</h1>
      <Card title="Account">
        <p>Logged in as <strong>{session?.email}</strong>{profile?.role === 'admin' && <span className="badge" style={{ marginLeft: 8 }}>admin</span>}</p>
        <p>
          {me ? <>Linked to player <Link to={`/players/${me.id}`}>{me.display_name}</Link>.</>
            : 'Not linked to a player yet — an admin links your account after your first recorded match.'}
        </p>
        <button onClick={() => api.signOut()}>Log out</button>
      </Card>
      {me && (
        <Card title="Privacy">
          <p className="muted">
            Everyone in the league always sees results, box scores and fantasy points. Your detailed
            analytics (zones, landings, success rates) are private unless you share them.
          </p>
          <ErrorBox error={error} />
          <label className="switch">
            <input type="checkbox" checked={me.profile_public} disabled={busy}
                   onChange={(e) => togglePublic(e.target.checked)} />
            <span>Share my detailed analytics with the league</span>
          </label>
        </Card>
      )}
    </>
  )
}
