import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useApp, useLoad } from '../app/state'
import { Card, ErrorBox, Loading } from '../components/ui'
import { signed } from '../lib/format'
import type { LeaderRow } from '../lib/types'

type SortKey = keyof Pick<LeaderRow, 'fantasy' | 'matches' | 'wins' | 'kills' | 'aces' | 'digs' | 'assists' | 'errors'>

const COLS: { key: SortKey; label: string; title: string }[] = [
  { key: 'fantasy', label: 'Pts', title: 'Fantasy points (active rules)' },
  { key: 'matches', label: 'MP', title: 'Matches played' },
  { key: 'wins', label: 'W', title: 'Matches won' },
  { key: 'kills', label: 'K', title: 'Kills' },
  { key: 'aces', label: 'Ace', title: 'Aces' },
  { key: 'digs', label: 'Dig', title: 'Digs' },
  { key: 'assists', label: 'Ast', title: 'Assists' },
  { key: 'errors', label: 'Err', title: 'Errors (fewer is better)' },
]

export function League() {
  const { api, me } = useApp()
  const nav = useNavigate()
  const [season, setSeason] = useState<string>('')
  const [sort, setSort] = useState<SortKey>('fantasy')
  const seasons = useLoad(() => api.seasons(), [])
  const board = useLoad(() => api.leaderboard(season || null), [season])

  const rows = [...(board.data ?? [])].sort((a, b) =>
    sort === 'errors' ? a.errors - b.errors : (b[sort] as number) - (a[sort] as number))

  return (
    <>
      <div className="row" style={{ marginBottom: 12 }}>
        <h1 style={{ margin: 0 }}>League</h1>
        <span className="spacer" />
        <label className="row small">
          <span className="muted">Season</span>
          <select value={season} onChange={(e) => setSeason(e.target.value)}>
            <option value="">All time</option>
            {(seasons.data ?? []).map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </label>
      </div>
      <Card>
        <ErrorBox error={board.error} />
        {board.loading ? <Loading /> : rows.length === 0 ? <p className="muted">No published matches yet.</p> : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th className="left">#</th>
                  <th className="left sticky-col">Player</th>
                  {COLS.map((c) => (
                    <th key={c.key} title={c.title} className={`sortable${sort === c.key ? ' sorted' : ''}`}
                        onClick={() => setSort(c.key)} aria-sort={sort === c.key ? 'descending' : 'none'}>
                      {c.label}{sort === c.key ? ' ▾' : ''}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((r, i) => (
                  <tr key={r.player_id} className={`clickable${r.player_id === me?.id ? ' me' : ''}`}
                      onClick={() => nav(`/players/${r.player_id}`)}>
                    <td className="left muted">{i + 1}</td>
                    <td className="left sticky-col">{r.display_name}</td>
                    <td className="strong">{signed(r.fantasy)}</td>
                    <td>{r.matches}</td>
                    <td>{r.wins}</td>
                    <td>{r.kills}</td>
                    <td>{r.aces}</td>
                    <td>{r.digs}</td>
                    <td>{r.assists}</td>
                    <td>{r.errors}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <p className="muted small" style={{ marginTop: 12, marginBottom: 0 }}>
          Only touches the video model could attribute with confidence are counted — a missed action costs
          nobody points, an invented one would.
        </p>
      </Card>
    </>
  )
}
