import { Link, useParams } from 'react-router-dom'
import { useApp, useLoad } from '../app/state'
import { LandingMap, ZoneGrid } from '../components/Court'
import { Card, ErrorBox, Loading, Tile } from '../components/ui'
import { formatDate, matchLabel, pct, signed } from '../lib/format'

export function PlayerPage() {
  const { id = '' } = useParams()
  const { api } = useApp()
  const data = useLoad(() => api.playerProfile(Number(id)), [id])

  if (data.loading) return <Loading />
  if (data.error) return <ErrorBox error={data.error} />
  if (!data.data) return <p>Player not found. <Link to="/league">League</Link></p>
  const { player, totals: t, history, analytics, can_see_analytics } = data.data

  return (
    <>
      <div className="hero" style={{ marginBottom: 16 }}>
        <div>
          <h1>{player.display_name}{player.is_me && <span className="badge" style={{ marginLeft: 8 }}>you</span>}</h1>
          <p className="muted" style={{ margin: 0 }}>{t.matches} matches · {t.wins} won</p>
        </div>
        <div style={{ textAlign: 'right' }}>
          <div className="hero-number">{signed(t.fantasy)}</div>
          <div className="tile-label">fantasy points</div>
        </div>
      </div>

      <Card>
        <div className="tiles">
          <Tile label="Kills" value={t.kills} />
          <Tile label="Aces" value={t.aces} />
          <Tile label="Digs" value={t.digs} />
          <Tile label="Assists" value={t.assists} />
          <Tile label="Serves" value={t.serves} />
          <Tile label="Attacks" value={t.attacks} />
          <Tile label="Errors" value={t.errors} hint="Service + attack + ball handling" />
        </div>
      </Card>

      {can_see_analytics && analytics ? (
        <Card title="Analytics" action={player.is_me && !player.profile_public
          ? <span className="muted small">Only you and admins see this · <Link to="/settings">share</Link></span>
          : undefined}>
          <div className="tiles" style={{ marginBottom: 16 }}>
            <Tile label="Kill rate" value={pct(analytics.kill_rate)} hint="Kills / attacks" />
            <Tile label="Attack errors" value={pct(analytics.attack_error_rate)} />
            <Tile label="Ace rate" value={pct(analytics.ace_rate)} hint="Aces / serves" />
            <Tile label="Serve errors" value={pct(analytics.serve_error_rate)} />
          </div>
          <div className="grid grid-2">
            <div>
              <h3>Where the attacks start</h3>
              {Object.keys(analytics.attack_zones).length
                ? <ZoneGrid counts={analytics.attack_zones} />
                : <p className="muted">No attack zones recorded yet.</p>}
            </div>
            <div>
              <h3>Where they land</h3>
              {analytics.landings.length
                ? <LandingMap landings={analytics.landings} />
                : <p className="muted">No landings recorded yet.</p>}
            </div>
          </div>
        </Card>
      ) : (
        <div className="notice">{player.display_name} keeps detailed analytics private.</div>
      )}

      <Card title="Matches">
        {history.length === 0 ? <p className="muted">No published matches yet.</p> : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th className="left">Date</th>
                  <th className="left">Match</th>
                  <th>Score</th>
                  <th>Pts</th>
                  <th>K</th>
                  <th>Ace</th>
                  <th>Dig</th>
                  <th>Err</th>
                </tr>
              </thead>
              <tbody>
                {history.map((h) => (
                  <tr key={h.match_id}>
                    <td className="left">{formatDate(h.match_date)}</td>
                    <td className="left">
                      <Link to={`/matches/${h.match_key}`}>{matchLabel(h)}</Link>{' '}
                      {h.won !== null && <span className={`badge${h.won ? ' badge-win' : ''}`}>{h.won ? 'W' : 'L'}</span>}
                    </td>
                    <td>{h.team === 'A' ? `${h.score_a}–${h.score_b}` : `${h.score_b}–${h.score_a}`}</td>
                    <td className="strong">{signed(h.fantasy)}</td>
                    <td>{h.kills}</td>
                    <td>{h.aces}</td>
                    <td>{h.digs}</td>
                    <td>{h.errors}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </>
  )
}
