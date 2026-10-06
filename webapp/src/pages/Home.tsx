import { Link } from 'react-router-dom'
import { useApp, useLoad, useMatchList } from '../app/state'
import { MatchList } from './Matches'
import { Card, ErrorBox, Loading, Tile } from '../components/ui'
import { signed } from '../lib/format'

export function Home() {
  const { api, me, isAdmin } = useApp()
  const profile = useLoad(() => (me ? api.playerProfile(me.id) : Promise.resolve(null)), [me?.id])
  const board = useLoad(() => api.leaderboard(null), [])
  const list = useMatchList()

  const drafts = (list.data?.matches ?? []).filter((m) => m.status === 'draft')
  const rank = me && board.data ? board.data.findIndex((r) => r.player_id === me.id) + 1 : 0
  const t = profile.data?.totals

  return (
    <>
      {isAdmin && drafts.length > 0 && (
        <div className="notice notice-warn">
          <strong>{drafts.length} match{drafts.length > 1 ? 'es' : ''} waiting for review.</strong>{' '}
          <Link to="/admin">Assign players and publish →</Link>
        </div>
      )}

      {me ? (
        <Card>
          <ErrorBox error={profile.error} />
          {profile.loading || !t ? <Loading /> : (
            <>
              <div className="hero">
                <div>
                  <h1>{me.display_name}</h1>
                  <p className="muted">
                    {t.matches} match{t.matches === 1 ? '' : 'es'} · {t.wins} won
                    {rank > 0 && <> · <strong>#{rank}</strong> in the league</>}
                  </p>
                </div>
                <div style={{ textAlign: 'right' }}>
                  <div className="hero-number">{signed(t.fantasy)}</div>
                  <div className="tile-label">fantasy points</div>
                </div>
              </div>
              <div className="tiles" style={{ marginTop: 12 }}>
                <Tile label="Kills" value={t.kills} />
                <Tile label="Aces" value={t.aces} />
                <Tile label="Digs" value={t.digs} />
                <Tile label="Assists" value={t.assists} />
                <Tile label="Errors" value={t.errors} hint="Service + attack + ball handling" />
              </div>
              <p style={{ marginTop: 12, marginBottom: 0 }}>
                <Link to={`/players/${me.id}`}>My full stats →</Link>
              </p>
            </>
          )}
        </Card>
      ) : (
        <div className="notice">
          Your account isn't linked to a player yet. A league admin links accounts to players after your
          first recorded match. Meanwhile you can browse the league.
        </div>
      )}

      <div className="grid grid-2">
        <Card title="League" action={<Link to="/league">Full table →</Link>}>
          <ErrorBox error={board.error} />
          {board.loading ? <Loading /> : (
            <table>
              <tbody>
                {(board.data ?? []).slice(0, 5).map((r, i) => (
                  <tr key={r.player_id} className={r.player_id === me?.id ? 'me' : undefined}>
                    <td className="left muted" style={{ width: 28 }}>{i + 1}</td>
                    <td className="left"><Link to={`/players/${r.player_id}`}>{r.display_name}</Link></td>
                    <td className="strong">{signed(r.fantasy)}</td>
                  </tr>
                ))}
                {board.data?.length === 0 && <tr><td className="left muted">No published matches yet.</td></tr>}
              </tbody>
            </table>
          )}
        </Card>
        <Card title="Latest matches" action={<Link to="/matches">All →</Link>}>
          <ErrorBox error={list.error} />
          {list.loading || !list.data ? <Loading /> : (
            <MatchList {...list.data} matches={list.data.matches.filter((m) => m.status === 'published').slice(0, 4)} />
          )}
        </Card>
      </div>
    </>
  )
}
