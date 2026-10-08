import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useApp, useLoad } from '../../app/state'
import { PlayByPlay } from '../../components/PlayByPlay'
import { Card, ErrorBox, Loading, StatusBadge } from '../../components/ui'
import { explainError } from '../../lib/api'
import { formatDate, matchLabel, slotNames, teamName } from '../../lib/format'
import type { Match, MatchPatch, MatchStatus, Slot, Team } from '../../lib/types'

const SLOTS: Slot[] = ['P1A', 'P2A', 'P1B', 'P2B']
/** The select value for "someone outside the league" (player ids are numbers). */
const UNKNOWN = 'unknown'

export function AdminMatch() {
  const { key = '' } = useParams()
  const { api } = useApp()
  const [error, setError] = useState<string | null>(null)
  const [newName, setNewName] = useState('')
  const data = useLoad(async () => {
    const match = await api.match(key)
    if (!match) return null
    const [participants, players, source, pubs, points, actions] = await Promise.all([
      api.participants([match.id]), api.players(), api.matchSource(match.id),
      api.publications(match.id), api.points(match.id), api.actions(match.id)])
    const thumbs = await api.thumbUrls(participants.map((p) => p.thumb_path).filter((p): p is string => !!p))
    return { match, participants, players, source, pubs, points, actions, thumbs }
  }, [key])

  if (data.loading) return <Loading />
  if (!data.data) return <><ErrorBox error={data.error} /><p>Match not found.</p></>
  const { match: m, participants, players, source, pubs, points, actions, thumbs } = data.data

  async function run(fn: () => Promise<unknown>) {
    setError(null)
    try {
      await fn()
      data.reload()
    } catch (err) {
      setError(explainError(err))
    }
  }
  const assign = (slot: Slot, value: string) => run(() => value === UNKNOWN
    ? api.assignSlot(m.id, slot, null, true)
    : api.assignSlot(m.id, slot, value ? Number(value) : null))
  const setStatus = (status: MatchStatus) => run(() => api.updateMatch(m.id, { status }))
  const addPlayer = () => run(async () => {
    if (newName.trim()) await api.createPlayer(newName.trim())
    setNewName('')
  })
  const openBundle = async (path: string) => {
    const url = await api.bundleUrl(path)
    if (url) window.open(url, '_blank', 'noopener')
  }

  // A slot is decided once it has a player or was marked unknown.
  const unassigned = participants.filter((p) => !p.player_id && !p.is_unknown).length
  const teamNames: Record<Team, string> = {
    A: teamName('A', participants, players), B: teamName('B', participants, players)}
  const names = slotNames(participants, players)
  const checks = m.checks ?? {}
  const flagged = Object.entries(checks.flagged_points ?? {})

  return (
    <>
      <p className="muted small" style={{ marginBottom: 4 }}><Link to="/admin">Review queue</Link> / {m.match_key}</p>
      <div className="row" style={{ marginBottom: 12 }}>
        <h1 style={{ margin: 0 }}>{matchLabel(m)}</h1>
        <StatusBadge status={m.status} />
        <span className="spacer" />
        {m.status === 'published' && <Link to={`/matches/${m.match_key}`}>Public page →</Link>}
      </div>
      <ErrorBox error={error ?? data.error} />

      <Card title="1 · Who is who" action={<span className="muted small">The video only knows slots; pick the real player for each</span>}>
        <div className="slots">
          {SLOTS.map((slot) => {
            const p = participants.find((x) => x.slot === slot)
            const url = p?.thumb_path ? thumbs[p.thumb_path] : undefined
            return (
              <div key={slot} className={`slot team-${slot.slice(2)}`}>
                <strong>{slot}</strong>
                {url ? <img src={url} alt={`${slot} at a touch`} /> : <div className="noimg">no thumbnail</div>}
                <select value={p?.is_unknown ? UNKNOWN : p?.player_id ?? ''} onChange={(e) => assign(slot, e.target.value)} aria-label={`Player for ${slot}`}>
                  <option value="">— choose —</option>
                  <option value={UNKNOWN}>Unknown player</option>
                  {players.filter((pl) => pl.active).map((pl) => <option key={pl.id} value={pl.id}>{pl.display_name}</option>)}
                </select>
              </div>
            )
          })}
        </div>
        <div className="row" style={{ marginTop: 12 }}>
          <input placeholder="New player name" value={newName} onChange={(e) => setNewName(e.target.value)} />
          <button onClick={addPlayer} disabled={!newName.trim()}>Add player</button>
        </div>
        <p className="muted small" style={{ marginBottom: 0 }}>
          <strong>Unknown player</strong> keeps that slot&apos;s stats in this match but leaves it out of the
          ranking and profiles. If they join later, re-tag them under{' '}
          <Link to="/admin/players">Players &amp; accounts</Link> → Unknown players.
        </p>
      </Card>

      <Card title="2 · Check the reconstruction">
        <p>
          <strong>{teamNames.A}</strong> {m.score_a}–{m.score_b} <strong>{teamNames.B}</strong> ·{' '}
          {m.n_points} points · set {m.set_complete ? 'complete' : <strong>NOT complete</strong>} · side switches after{' '}
          {(checks.side_switch_after_point ?? []).join(', ') || '–'}
          {checks.switch_blocks_ok === false && <strong> (irregular)</strong>}
        </p>
        {flagged.length > 0 && (
          <div className="notice notice-warn">
            <strong>Flagged points:</strong>{' '}
            {flagged.map(([pt, f]) => `P${pt} (${f.join(', ')})`).join(' · ')}
          </div>
        )}
        {(checks.undecided_points ?? []).length > 0 && (
          <div className="notice notice-warn">Undecided points: {checks.undecided_points!.join(', ')}</div>
        )}
        <p className="small">
          Video: {source?.video_url ? <a href={source.video_url} target="_blank" rel="noreferrer">{source.video_filename ?? 'open'}</a> : '–'}
          {source?.fps && <span className="muted"> · {source.width}×{source.height} @ {source.fps.toFixed(2)} fps</span>}
          {' '}· recorded {formatDate(m.match_date, m.start_time)}
        </p>
        <details>
          <summary>Play-by-play ({points.length} points)</summary>
          <PlayByPlay points={points} actions={actions} names={names} teamNames={teamNames} />
        </details>
      </Card>

      <Card title="3 · Publish">
        <div className="grid grid-2">
          <DetailsForm key={`${m.id}:${m.updated_at}:${m.title}:${m.venue}:${m.season}`} match={m}
                       onSave={(patch) => run(() => api.updateMatch(m.id, patch))} />
          <div className="stack">
            <label className="switch">
              <input type="checkbox" checked={m.detail_public} onChange={(e) => run(() => api.updateMatch(m.id, { detail_public: e.target.checked }))} />
              <span>Everyone can see the play-by-play (default: only its 4 players)</span>
            </label>
            {unassigned > 0 && m.status === 'draft' && <p className="muted small">{unassigned} slot(s) still unassigned.</p>}
            <div className="row">
              {m.status !== 'published' && <button className="primary" onClick={() => setStatus('published')} disabled={unassigned > 0}>Publish</button>}
              {m.status === 'published' && <button onClick={() => setStatus('draft')}>Back to draft</button>}
              {m.status !== 'hidden' && <button className="danger" onClick={() => setStatus('hidden')}>Hide</button>}
              {m.status === 'hidden' && <button onClick={() => setStatus('draft')}>Unhide (draft)</button>}
            </div>
          </div>
        </div>
      </Card>

      <Card title="Publication log" action={<span className="muted small">Every <code>make publish</code> of this video</span>}>
        <div className="table-wrap">
          <table>
            <thead>
              <tr><th>Rev</th><th className="left">When</th><th className="left">Result</th><th>Score</th><th>Touches</th>
                <th className="left">Pipeline</th><th className="left">By</th><th className="left">Note</th><th /></tr>
            </thead>
            <tbody>
              {pubs.map((p) => (
                <tr key={p.id}>
                  <td>{p.revision}</td>
                  <td className="left">{new Date(p.published_at).toLocaleString()}</td>
                  <td className="left">{p.result}</td>
                  <td>{p.score ?? '–'}</td>
                  <td>{p.n_actions ?? '–'}</td>
                  <td className="left"><code>{p.pipeline_version ?? '?'}</code>{p.git_dirty && ' (dirty)'}</td>
                  <td className="left">{p.published_by}</td>
                  <td className="left">{p.notes ?? ''}</td>
                  <td>{p.bundle_path && <button className="link" onClick={() => openBundle(p.bundle_path!)}>bundle</button>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </>
  )
}

/** Admin-owned match details; keyed by the saved values, so it re-seeds
 * from the server after every save instead of syncing state in an effect. */
function DetailsForm({ match: m, onSave }: { match: Match; onSave: (p: MatchPatch) => void }) {
  const [form, setForm] = useState<MatchPatch>({ title: m.title, venue: m.venue, season: m.season })
  return (
    <div>
      <label className="field"><span>Title (optional)</span>
        <input value={form.title ?? ''} onChange={(e) => setForm({ ...form, title: e.target.value || null })} /></label>
      <label className="field"><span>Venue</span>
        <input value={form.venue ?? ''} onChange={(e) => setForm({ ...form, venue: e.target.value || null })} /></label>
      <label className="field"><span>Season</span>
        <input value={form.season ?? ''} placeholder="e.g. 2026 Autumn"
               onChange={(e) => setForm({ ...form, season: e.target.value || null })} /></label>
      <button onClick={() => onSave(form)}>Save details</button>
    </div>
  )
}
