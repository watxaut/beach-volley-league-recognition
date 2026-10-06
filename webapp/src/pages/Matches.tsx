import { Link } from 'react-router-dom'
import { useMatchList } from '../app/state'
import { Card, ErrorBox, Loading, StatusBadge } from '../components/ui'
import { formatDate, matchLabel, teamName } from '../lib/format'
import type { Match, Participant, Player } from '../lib/types'

export function MatchList({ matches, participants, players }: {
  matches: Match[]; participants: Participant[]; players: Player[]
}) {
  if (!matches.length) return <p className="muted">No matches yet.</p>
  return (
    <div>
      {matches.map((m) => {
        const parts = participants.filter((p) => p.match_id === m.id)
        return (
          <Link key={m.id} to={`/matches/${m.match_key}`} className="match-card">
            <div>
              <div className="match-teams">
                <span className={m.winner_team === 'A' ? 'winner' : undefined}>{teamName('A', parts, players)}</span>
                <span className="muted"> vs </span>
                <span className={m.winner_team === 'B' ? 'winner' : undefined}>{teamName('B', parts, players)}</span>
              </div>
              <div className="match-meta">
                {formatDate(m.match_date, m.start_time)} · {matchLabel(m)} <StatusBadge status={m.status} />
              </div>
            </div>
            <div className="match-score">{m.score_a ?? '–'}–{m.score_b ?? '–'}</div>
          </Link>
        )
      })}
    </div>
  )
}

export function Matches() {
  const list = useMatchList()
  return (
    <>
      <h1>Matches</h1>
      <Card>
        <ErrorBox error={list.error} />
        {list.loading || !list.data ? <Loading /> : <MatchList {...list.data} />}
      </Card>
    </>
  )
}
