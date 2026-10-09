import { useState } from 'react'
import { useOutletContext } from 'react-router-dom'
import { useApp, useLoad } from '../../app/state'
import { ReportHead, Shots } from '../../components/FeedbackList'
import { Card, ErrorBox, Loading, Segmented } from '../../components/ui'
import { explainError } from '../../lib/api'
import type { Feedback, FeedbackStatus } from '../../lib/types'

const CONTEXT_KEYS = ['viewport', 'theme', 'build', 'user_agent']

export function AdminFeedback() {
  const { api } = useApp()
  // the open count on the admin tab (AdminLayout) follows what is closed here
  const recount = useOutletContext<() => void>()
  const [show, setShow] = useState<'open' | 'all'>('open')
  const list = useLoad(async () => {
    const reports = await api.allFeedback()
    return { reports, urls: await api.feedbackUrls(reports.flatMap((r) => r.screenshots)) }
  }, [])
  if (list.loading || !list.data) return <><ErrorBox error={list.error} /><Loading /></>
  const { reports, urls } = list.data
  const open = reports.filter((r) => r.status === 'open')
  const rows = show === 'open' ? open : reports
  return (
    <>
      <Card title="Feedback"
            action={<Segmented label="Reports shown" value={show} onChange={setShow}
                               options={[{ key: 'open', label: `Open (${open.length})` }, { key: 'all', label: `All (${reports.length})` }]} />}>
        <p className="muted small">
          Bugs and suggestions sent with the Feedback button. <code>make feedback</code> on the laptop pulls the
          open ones, with their screenshots, into <code>output/feedback/</code>.
        </p>
        {rows.length === 0 && <p className="muted">{show === 'open' ? 'Nothing open.' : 'No reports yet.'}</p>}
      </Card>
      {rows.map((r) => <Report key={r.id} report={r} urls={urls} onChange={() => {
        list.reload()
        recount()
      }} />)}
    </>
  )
}

function Report({ report, urls, onChange }: { report: Feedback; urls: Record<string, string>; onChange: () => void }) {
  const { api } = useApp()
  const [note, setNote] = useState(report.admin_note ?? '')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function set(status: FeedbackStatus) {
    setBusy(true)
    setError(null)
    try {
      await api.setFeedbackStatus(report.id, status, note.trim() || null)
      onChange()
    } catch (err) {
      setError(explainError(err))
    } finally {
      setBusy(false)
    }
  }

  const author = report.author?.display_name ?? report.author?.email ?? 'unknown account'
  const context = CONTEXT_KEYS.filter((k) => report.context[k]).map((k) => `${k}: ${report.context[k]}`)
  return (
    <Card>
      <ReportHead report={report} author={`#${report.id} · ${author}`} />
      <p className="report-text">{report.message}</p>
      <Shots paths={report.screenshots} urls={urls} />
      {context.length > 0 && <p className="muted small report-context">{context.join(' · ')}</p>}
      <ErrorBox error={error} />
      <div className="report-actions">
        <input type="text" value={note} maxLength={2000} placeholder="Note for the author (optional)"
               aria-label="Note for the author" onChange={(e) => setNote(e.target.value)} />
        {report.status === 'open' ? (
          <>
            <button type="button" className="primary" disabled={busy} onClick={() => set('done')}>Done</button>
            <button type="button" disabled={busy} onClick={() => set('dismissed')}>Not planned</button>
          </>
        ) : (
          <>
            <button type="button" disabled={busy || note.trim() === (report.admin_note ?? '')}
                    onClick={() => set(report.status)}>Save note</button>
            <button type="button" disabled={busy} onClick={() => set('open')}>Reopen</button>
          </>
        )}
      </div>
    </Card>
  )
}
