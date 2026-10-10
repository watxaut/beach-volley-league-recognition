import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useApp, useLoad } from '../app/state'
import { ReportHead, Shots } from '../components/FeedbackList'
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
            Everyone in the league always sees results, box scores (serves, kills, digs, errors) and
            fantasy points. Everything more detailed (where you attack and land, how your attacks,
            serves and receptions break down, your trends) shows only to you and the admins unless you
            share it. The four players of a match also see that match's play-by-play.
          </p>
          <ErrorBox error={error} />
          <label className="switch">
            <input type="checkbox" checked={me.profile_public} disabled={busy}
                   onChange={(e) => togglePublic(e.target.checked)} />
            <span>Share my detailed analytics with the league</span>
          </label>
        </Card>
      )}
      <MyReports />
    </>
  )
}

/** What the member sent with the Feedback button, and what came of it. */
function MyReports() {
  const { api, session } = useApp()
  const list = useLoad(async () => {
    const reports = session ? await api.myFeedback(session.userId) : []
    return { reports, urls: await api.feedbackUrls(reports.flatMap((r) => r.screenshots)) }
  }, [session?.userId])
  return (
    <Card title="My reports">
      <ErrorBox error={list.error} />
      {list.data?.reports.length === 0 && (
        <p className="muted">
          Nothing sent yet. Found a bug or have an idea? Use the Feedback button at the top of any page.
        </p>
      )}
      <ul className="reports">
        {list.data?.reports.map((r) => (
          <li key={r.id}>
            <ReportHead report={r} />
            <p className="report-text">{r.message}</p>
            <Shots paths={r.screenshots} urls={list.data!.urls} />
            {r.admin_note && <p className="report-note"><strong>Reply:</strong> {r.admin_note}</p>}
          </li>
        ))}
      </ul>
    </Card>
  )
}
