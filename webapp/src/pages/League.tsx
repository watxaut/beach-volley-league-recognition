import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useApp, useLoad } from '../app/state'
import { useWindowKey } from '../app/window'
import { Card, ErrorBox, Loading } from '../components/ui'
import { WindowPicker } from '../components/WindowPicker'
import { signed } from '../lib/format'
import { hitText, hitting, MIN_N, rankValue } from '../lib/stats'
import type { LeaderRow } from '../lib/types'
import { windowLabel, windowParams } from '../lib/window'

type SortKey = 'fantasy' | 'per21' | 'matches' | 'wins' | 'kills' | 'hit' | 'aces' | 'digs' | 'assists' | 'errors'

const COLS: { key: SortKey; label: string; title: string }[] = [
  { key: 'fantasy', label: 'Pts', title: 'Fantasy points (active rules)' },
  { key: 'per21', label: '/21', title: 'Fantasy points per 21 points played, so long and short matches compare' },
  { key: 'matches', label: 'MP', title: 'Matches played' },
  { key: 'wins', label: 'W', title: 'Matches won' },
  { key: 'kills', label: 'K', title: 'Kills' },
  { key: 'hit', label: 'Hit %', title: `Hitting %: (kills − attack errors) / attacks. Shown from ${MIN_N} attacks.` },
  { key: 'aces', label: 'Ace', title: 'Aces' },
  { key: 'digs', label: 'Dig', title: 'Digs' },
  { key: 'assists', label: 'Ast', title: 'Assists' },
  { key: 'errors', label: 'Err', title: 'Errors (fewer is better)' },
]

const hitOf = (r: LeaderRow) => hitting({ n: r.attacks, kills: r.kills, errors: r.attack_errors })

function value(r: LeaderRow, key: SortKey): number {
  switch (key) {
    case 'per21': return rankValue(r.fantasy_per_21)
    case 'hit': return rankValue(hitOf(r))
    case 'errors': return -r.errors                 // fewer is better
    default: return r[key] as number
  }
}

export function League() {
  const { api, me } = useApp()
  const nav = useNavigate()
  const [key, setKey] = useWindowKey()
  const [sort, setSort] = useState<SortKey>('fantasy')
  const seasons = useLoad(() => api.seasons(), [])
  const board = useLoad(() => api.leaderboard(windowParams(key)), [key])

  const rows = [...(board.data ?? [])].sort((a, b) => value(b, sort) - value(a, sort) || a.display_name.localeCompare(b.display_name))

  return (
    <>
      <div className="row" style={{ marginBottom: 12 }}>
        <h1 style={{ margin: 0 }}>League</h1>
        <span className="muted small">{windowLabel(key)}</span>
        <span className="spacer" />
        <WindowPicker value={key} onChange={setKey} seasons={seasons.data ?? []} />
      </div>
      <Card>
        <ErrorBox error={board.error} />
        {board.loading && !board.data ? <Loading /> : rows.length === 0 ? <p className="muted">No published matches in this view.</p> : (
          <div className="table-wrap" style={{ opacity: board.loading ? 0.6 : 1 }}>
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
                      onClick={() => nav(`/players/${r.player_id}${key === 'all' ? '' : `?w=${encodeURIComponent(key)}`}`)}>
                    <td className="left muted">{i + 1}</td>
                    <td className="left sticky-col">{r.display_name}</td>
                    <td className="strong">{signed(r.fantasy)}</td>
                    <td>{r.fantasy_per_21 === null ? '–' : signed(r.fantasy_per_21)}</td>
                    <td>{r.matches}</td>
                    <td>{r.wins}</td>
                    <td>{r.kills}</td>
                    <td title={`${r.kills} kills, ${r.attack_errors} errors, ${r.attacks} attacks`}>{hitText(hitOf(r))}</td>
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
          nobody points, an invented one would, so counts are lower bounds. A rate needs {MIN_N} attempts before it
          is shown or ranked. Blocks are not measured.
        </p>
      </Card>
    </>
  )
}
