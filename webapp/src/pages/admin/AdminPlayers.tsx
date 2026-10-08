import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useApp, useLoad } from '../../app/state'
import { Card, ErrorBox, Loading } from '../../components/ui'
import { explainError } from '../../lib/api'
import { formatDate, matchLabel } from '../../lib/format'
import type { Role } from '../../lib/types'

export function AdminPlayers() {
  const { api, session } = useApp()
  const [error, setError] = useState<string | null>(null)
  const [name, setName] = useState('')
  const data = useLoad(async () => {
    const [players, profiles, matches] = await Promise.all([api.players(), api.profiles(), api.matches()])
    const participants = await api.participants(matches.map((m) => m.id))
    const unknown = participants.filter((p) => p.is_unknown)
    const thumbs = await api.thumbUrls(unknown.map((p) => p.thumb_path).filter((p): p is string => !!p))
    return { players, profiles, matches, participants, unknown, thumbs }
  }, [])

  async function run(fn: () => Promise<unknown>) {
    setError(null)
    try {
      await fn()
      data.reload()
    } catch (err) {
      setError(explainError(err))
    }
  }

  if (data.loading || !data.data) return <><ErrorBox error={data.error} /><Loading /></>
  const { players, profiles, matches, participants, unknown, thumbs } = data.data
  const linked = new Set(players.map((p) => p.user_id).filter(Boolean))
  const unknownRows = unknown
    .flatMap((p) => {
      const m = matches.find((x) => x.id === p.match_id)
      return m ? [{ p, m }] : []
    })
    .sort((a, b) => b.m.match_date.localeCompare(a.m.match_date) || a.p.slot.localeCompare(b.p.slot))

  return (
    <>
      <ErrorBox error={error} />
      <Card title="Players" action={<span className="muted small">Real people who appear in matches</span>}>
        <div className="row" style={{ marginBottom: 12 }}>
          <input placeholder="New player name" value={name} onChange={(e) => setName(e.target.value)} />
          <button onClick={() => run(async () => { await api.createPlayer(name.trim()); setName('') })} disabled={!name.trim()}>
            Add player
          </button>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr><th className="left">Player</th><th className="left">Login account</th><th className="left">Analytics</th><th className="left">Active</th></tr>
            </thead>
            <tbody>
              {players.map((p) => (
                <tr key={p.id}>
                  <td className="left">
                    <Link to={`/players/${p.id}`}>{p.display_name}</Link>{' '}
                    <button className="link small" onClick={() => {
                      const next = window.prompt('Rename player', p.display_name)
                      if (next && next.trim()) void run(() => api.updatePlayer(p.id, { display_name: next.trim() }))
                    }}>rename</button>
                  </td>
                  <td className="left">
                    <select value={p.user_id ?? ''} aria-label={`Account for ${p.display_name}`}
                            onChange={(e) => run(() => api.updatePlayer(p.id, { user_id: e.target.value || null }))}>
                      <option value="">— not linked —</option>
                      {profiles.filter((u) => u.user_id === p.user_id || !linked.has(u.user_id)).map((u) => (
                        <option key={u.user_id} value={u.user_id}>{u.email}</option>
                      ))}
                    </select>
                  </td>
                  <td className="left muted">{p.profile_public ? 'shared' : 'private'}</td>
                  <td className="left">
                    <input type="checkbox" checked={p.active} aria-label="active"
                           onChange={(e) => run(() => api.updatePlayer(p.id, { active: e.target.checked }))} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <Card title="Unknown players" action={<span className="muted small">Slots marked unknown in a match</span>}>
        <p className="muted small">
          Their stats stay inside their match, but they are not in the ranking or on any profile. When one of them
          joins, create the player above and re-tag the slot: the match then counts for that player.
        </p>
        {unknownRows.length === 0 ? <p className="muted">No unknown players.</p> : (
          <div className="table-wrap">
            <table>
              <thead><tr><th className="left">Match</th><th className="left">Slot</th><th className="left">Re-tag as</th></tr></thead>
              <tbody>
                {unknownRows.map(({ p, m }) => {
                  const taken = new Set(participants.filter((x) => x.match_id === m.id).map((x) => x.player_id))
                  const thumb = p.thumb_path ? thumbs[p.thumb_path] : undefined
                  return (
                    <tr key={`${m.id}:${p.slot}`}>
                      <td className="left">
                        <Link to={`/admin/matches/${m.match_key}`}>{matchLabel(m)}</Link>{' '}
                        <span className="muted small">{formatDate(m.match_date, m.start_time)}</span>
                      </td>
                      <td className="left">
                        {thumb && <img src={thumb} alt={`${p.slot} at a touch`}
                                       style={{ height: 56, width: 34, objectFit: 'cover', borderRadius: 6, verticalAlign: 'middle', marginRight: 8 }} />}
                        {p.slot}
                      </td>
                      <td className="left">
                        <select value="" aria-label={`Re-tag ${p.slot} of ${matchLabel(m)}`}
                                onChange={(e) => e.target.value && run(() => api.assignSlot(m.id, p.slot, Number(e.target.value)))}>
                          <option value="">— choose a player —</option>
                          {players.filter((pl) => pl.active && !taken.has(pl.id)).map((pl) => (
                            <option key={pl.id} value={pl.id}>{pl.display_name}</option>
                          ))}
                        </select>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <Card title="Accounts" action={<span className="muted small">People who can log in</span>}>
        <p className="muted small">
          To add someone: Supabase dashboard → Authentication → Users → <strong>Invite user</strong>. They appear here after
          accepting; then link them to their player above.
        </p>
        <div className="table-wrap">
          <table>
            <thead><tr><th className="left">Email</th><th className="left">Role</th><th className="left">Player</th></tr></thead>
            <tbody>
              {profiles.map((u) => (
                <tr key={u.user_id}>
                  <td className="left">{u.email}</td>
                  <td className="left">
                    <select value={u.role} disabled={u.user_id === session?.userId}
                            title={u.user_id === session?.userId ? 'You cannot demote yourself' : undefined}
                            onChange={(e) => run(() => api.setRole(u.user_id, e.target.value as Role))}>
                      <option value="viewer">viewer</option>
                      <option value="admin">admin</option>
                    </select>
                  </td>
                  <td className="left">{players.find((p) => p.user_id === u.user_id)?.display_name ?? <span className="muted">—</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </>
  )
}
