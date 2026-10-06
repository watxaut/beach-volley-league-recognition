import { Link, useParams } from 'react-router-dom'
import { useApp, useLoad } from '../app/state'
import { BoxScore } from '../components/BoxScore'
import { MatchReport } from '../components/MatchReport'
import { PlayByPlay } from '../components/PlayByPlay'
import { ScoreWorm } from '../components/ScoreWorm'
import { Card, ErrorBox, Loading, StatusBadge } from '../components/ui'
import { formatDate, matchLabel, minutes, teamName } from '../lib/format'
import type { Slot, Team } from '../lib/types'

export function MatchPage() {
  const { key = '' } = useParams()
  const { api, me, isAdmin } = useApp()
  const data = useLoad(async () => {
    const match = await api.match(key)
    if (!match) return null
    const [participants, players, box, points, actions, report] = await Promise.all([
      api.participants([match.id]), api.players(), api.boxScore(match.id),
      api.points(match.id), api.actions(match.id), api.matchReport(match.id)])
    return { match, participants, players, box, points, actions, report }
  }, [key])

  if (data.loading) return <Loading />
  if (data.error) return <ErrorBox error={data.error} />
  if (!data.data) return <p>Match not found (or not published yet). <Link to="/matches">All matches</Link></p>
  const { match: m, participants, players, box, points, actions, report } = data.data
  const teamNames: Record<Team, string> = {
    A: teamName('A', participants, players), B: teamName('B', participants, players)}
  const names: Partial<Record<Slot, string>> = {}
  for (const p of participants) {
    const pl = players.find((x) => x.id === p.player_id)
    if (pl) names[p.slot] = pl.display_name
  }

  return (
    <>
      <p className="muted small" style={{ marginBottom: 4 }}>
        <Link to="/matches">Matches</Link> / {formatDate(m.match_date, m.start_time)}
      </p>
      <div className="row" style={{ marginBottom: 12 }}>
        <h1 style={{ margin: 0 }}>{matchLabel(m)}</h1>
        <StatusBadge status={m.status} />
        <span className="spacer" />
        {isAdmin && <Link to={`/admin/matches/${m.match_key}`}>Admin view →</Link>}
      </div>

      <Card>
        <div className="scoreboard">
          <div className="side">
            <span className="bar" style={{ background: 'var(--team-a)' }} />
            <span className="names">{teamNames.A}</span>
            {m.winner_team === 'A' && <span className="badge badge-win">won</span>}
          </div>
          <div className="big">{m.score_a}–{m.score_b}</div>
          <div className="side">
            <span className="bar" style={{ background: 'var(--team-b)' }} />
            <span className="names">{teamNames.B}</span>
            {m.winner_team === 'B' && <span className="badge badge-win">won</span>}
          </div>
        </div>
        <p className="muted small" style={{ textAlign: 'center', margin: '8px 0 0' }}>
          {m.n_points} points · {minutes(m.duration_s)}{m.venue ? ` · ${m.venue}` : ''}
          {m.set_complete === false && ' · set incomplete'}
        </p>
        {points.length > 1 && (
          <div style={{ marginTop: 16 }}>
            <h3>Score margin, point by point</h3>
            <ScoreWorm points={points} nameA={teamNames.A} nameB={teamNames.B} />
          </div>
        )}
      </Card>

      <Card title="Box score">
        <BoxScore rows={box} myPlayerId={me?.id ?? null} />
      </Card>

      {report && (
        <Card title="Report card">
          <MatchReport report={report} nPoints={m.n_points ?? 0} names={names} teamNames={teamNames} myPlayerId={me?.id ?? null} />
        </Card>
      )}

      <Card title="Play-by-play">
        {points.length ? (
          <PlayByPlay points={points} actions={actions} names={names} teamNames={teamNames} />
        ) : (
          <p className="muted">The play-by-play of a match is visible to the four players who played it.</p>
        )}
      </Card>
    </>
  )
}
