import { useState } from 'react'
import { Link, NavLink, useNavigate, useParams } from 'react-router-dom'
import { useApp, useLoad } from '../app/state'
import { Card, ErrorBox, Info, Loading } from '../components/ui'
import { explainError } from '../lib/api'
import { dateTime, lineupCost, lineupProblem, untilText } from '../lib/fantasy'
import { signed } from '../lib/format'
import type { FantasyDayPage, FantasyDaySummary } from '../lib/types'

/** The game's own menu: this match day and the season table. */
function FantasyNav() {
  const link = ({ isActive }: { isActive: boolean }) => (isActive ? 'active' : undefined)
  return (
    <nav className="nav" style={{ marginBottom: 16 }} aria-label="Fantasy">
      <NavLink to="/fantasy" end className={link}>Match day</NavLink>
      <NavLink to="/fantasy/standings" className={link}>Standings</NavLink>
    </nav>
  )
}

/** /fantasy: the day to pick for (or the last one played), every day, the rules. */
export function Fantasy() {
  const { api } = useApp()
  const days = useLoad(() => api.fantasyDays(), [])
  if (days.loading) return <><FantasyNav /><Loading /></>
  const list = days.data ?? []
  // the next day still taking picks; else the latest one played
  const upcoming = list.filter((d) => d.status === 'open' && !d.locked && d.locks_at)
    .sort((a, b) => a.locks_at!.localeCompare(b.locks_at!))
  const current = upcoming[0] ?? list.find((d) => d.status === 'open' && d.locked) ?? null
  return (
    <>
      <FantasyNav />
      <ErrorBox error={days.error} />
      {current ? <DayView id={current.id} /> : (
        <>
          <h1>Fantasy</h1>
          <Card><p className="muted" style={{ margin: 0 }}>No match day is open yet. An admin opens one before the next matches.</p></Card>
        </>
      )}
      {list.length > 0 && <DaysCard days={list} current={current?.id ?? null} />}
      <RulesCard />
    </>
  )
}

/** /fantasy/days/:id */
export function FantasyDay() {
  const { id = '' } = useParams()
  return <><FantasyNav /><DayView id={Number(id)} /></>
}

function DayView({ id }: { id: number }) {
  const { api } = useApp()
  const page = useLoad(() => api.fantasyDay(id), [id])
  const [now] = useState(() => new Date())
  if (page.loading && !page.data) return <Loading />
  if (!page.data) return <><ErrorBox error={page.error} /><p>This match day is not open yet.</p></>
  const p = page.data
  const { day } = p
  const until = day.locks_at ? untilText(day.locks_at, now) : null
  return (
    <>
      <div className="row" style={{ marginBottom: 4 }}>
        <h1 style={{ margin: 0 }}>{day.name}</h1>
        <span className="muted small">{day.season}</span>
        {day.status === 'draft' && <span className="badge badge-draft">draft</span>}
        {day.final && <span className="badge">final</span>}
      </div>
      <p className="muted" style={{ marginTop: 0 }}>
        {day.status === 'draft' ? 'Only admins see a draft day.'
          : !day.locks_at ? 'No match scheduled yet.'
          : !day.locked ? <>Picks lock <strong>{dateTime(day.locks_at)}</strong>{until && ` (${until})`}, when the first match starts.</>
          : day.final ? 'Every match of the day is counted.'
          : 'Picks are locked. Points arrive as each match is published to fantasy.'}
      </p>
      {!day.locked && day.status === 'open' && (
        p.me.manager ? <Picker key={`${id}:${p.my_lineup?.updated_at ?? ''}`} page={p} onSaved={page.reload} />
          : <ManagerName onSaved={page.reload} />
      )}
      {day.locked && <Ranking page={p} />}
      <Fixtures page={p} />
    </>
  )
}

/** The name the member plays under: the tables never show an email. */
export function ManagerName({ onSaved, current }: { onSaved: () => void; current?: string | null }) {
  const { api, refreshMe } = useApp()
  const [name, setName] = useState(current ?? '')
  const [error, setError] = useState<string | null>(null)
  const [saved, setSaved] = useState(false)
  const save = async () => {
    setError(null)
    setSaved(false)
    try {
      await api.setMyName(name)
      await refreshMe()
      setSaved(true)
      onSaved()
    } catch (err) {
      setError(explainError(err))
    }
  }
  return (
    <Card title={current ? 'Fantasy name' : 'Choose your fantasy name'}>
      <p className="muted" style={{ marginTop: 0 }}>The name the league sees in the fantasy tables (2 to 30 characters).</p>
      <ErrorBox error={error} />
      <form className="row" onSubmit={(e) => { e.preventDefault(); void save() }}>
        <input value={name} onChange={(e) => setName(e.target.value)} aria-label="Fantasy name" maxLength={30} />
        <button type="submit" className="primary" disabled={name.trim().length < 2 || name.trim() === current}>Save</button>
        {saved && <span className="muted small">Saved</span>}
      </form>
    </Card>
  )
}

function Picker({ page, onSaved }: { page: FantasyDayPage; onSaved: () => void }) {
  const { api } = useApp()
  const { day, fixtures, players, my_lineup } = page
  const [picks, setPicks] = useState<number[]>(my_lineup?.player_ids ?? [])
  const [captain, setCaptain] = useState<number | null>(my_lineup?.captain ?? null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const playing = new Set(fixtures.filter((f) => !f.cancelled).flatMap((f) => f.players.map((x) => x.player_id)))
  const byId = new Map(players.map((x) => [x.player_id, x]))
  const price = (id: number) => (playing.has(id) ? byId.get(id)?.price : undefined)
  const cost = lineupCost(picks, price)
  const problem = lineupProblem(day, picks, captain, price)
  const dirty = !my_lineup || my_lineup.captain !== captain
    || my_lineup.player_ids.length !== picks.length || my_lineup.player_ids.some((x) => !picks.includes(x))

  const toggle = (id: number) => {
    if (picks.includes(id)) {
      setPicks(picks.filter((x) => x !== id))
      if (captain === id) setCaptain(null)
    } else if (picks.length < day.squad_size) {
      setPicks([...picks, id])
      if (captain === null) setCaptain(id)
    }
  }
  const save = async () => {
    setBusy(true)
    setError(null)
    try {
      await api.saveLineup(day.id, picks, captain!)
      onSaved()
    } catch (err) {
      setError(explainError(err))
    } finally {
      setBusy(false)
    }
  }
  const left = Math.round((day.budget - cost) * 10) / 10
  return (
    <Card title="Your lineup" action={<span className="muted small">{picks.length} of {day.squad_size} picked</span>}>
      <div className="budget" aria-label={`Budget: ${cost} of ${day.budget} spent`}>
        <div className={`budget-bar${cost > day.budget ? ' over' : ''}`}
             style={{ width: `${Math.min(100, (cost / day.budget) * 100)}%` }} />
      </div>
      <p className="small" style={{ marginTop: 6 }}>
        <strong>{cost}</strong> of {day.budget} spent · {left >= 0 ? `${left} left` : <strong className="text-bad">{-left} over</strong>}
        {' '}· captain scores ×{day.captain_multiplier}
      </p>
      {fixtures.filter((f) => !f.cancelled).map((f) => (
        <div key={f.id} className="fx">
          <div className="fx-head muted small">{dateTime(f.scheduled_at)}{f.venue && ` · ${f.venue}`}</div>
          <div className="fx-sides">
            {(['A', 'B'] as const).map((team) => {
              const side = f.players.filter((x) => x.team === team)
              return (
                <div key={team} className="fx-side">
                  {side.map(({ player_id: pid }) => {
                    const pl = byId.get(pid)!
                    const on = picks.includes(pid)
                    const avg = pl.form.length ? pl.form.reduce((t, x) => t + x, 0) / pl.form.length : null
                    return (
                      <div key={pid} className={`pick${on ? ' on' : ''}`}>
                        <button type="button" className="pick-main" aria-pressed={on} onClick={() => toggle(pid)}
                                disabled={!on && picks.length >= day.squad_size}>
                          <span className="pick-name">{pl.display_name}</span>
                          <span className="pick-price">{pl.price.toFixed(1)}</span>
                          <span className="pick-form muted small">
                            {avg === null ? 'no matches yet' : `avg ${signed(avg)} over ${pl.form.length}`}
                          </span>
                        </button>
                        <button type="button" className="pick-cap" aria-pressed={captain === pid} disabled={!on}
                                aria-label={`Make ${pl.display_name} captain`} title="Captain"
                                onClick={() => setCaptain(pid)}>C</button>
                      </div>
                    )
                  })}
                  {side.length < 2 && <div className="pick pick-guest muted small">{side.length ? 'guest' : 'guests'} (not in the game)</div>}
                </div>
              )
            })}
          </div>
        </div>
      ))}
      <ErrorBox error={error} />
      <div className="row" style={{ marginTop: 12 }}>
        <button className="primary" onClick={save} disabled={!!problem || busy || !dirty}>
          {my_lineup ? 'Save changes' : 'Save lineup'}
        </button>
        <span className="muted small">
          {problem ? `To save: ${problem}.` : !dirty ? 'Saved. You can change it until the lock.' : 'Ready to save.'}
        </span>
      </div>
    </Card>
  )
}

function Ranking({ page }: { page: FantasyDayPage }) {
  const { day, players, lineups } = page
  const byId = new Map(players.map((x) => [x.player_id, x]))
  return (
    <Card title={day.final ? 'Result' : 'Live ranking'}
          action={<span className="muted small">{lineups?.length ?? 0} lineup{lineups?.length === 1 ? '' : 's'}</span>}>
      {!lineups?.length ? <p className="muted" style={{ margin: 0 }}>Nobody picked a lineup for this day.</p> : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr><th className="left">#</th><th className="left">Manager</th><th className="left">Picks</th><th>Pts</th></tr>
            </thead>
            <tbody>
              {lineups.map((l) => (
                <tr key={l.manager} className={l.is_me ? 'me' : undefined}>
                  <td className="left muted">{l.rank}</td>
                  <td className="left">{l.manager}</td>
                  <td className="left small">
                    {l.player_ids.map((pid, i) => {
                      const pl = byId.get(pid)
                      const pts = pl?.points
                      return (
                        <span key={pid}>
                          {i > 0 && ' · '}
                          {pl?.display_name ?? '?'}{pid === l.captain && <strong> (C)</strong>}
                          {pts !== null && pts !== undefined && <span className="muted"> {signed(pid === l.captain ? pts * day.captain_multiplier : pts)}</span>}
                        </span>
                      )
                    })}
                  </td>
                  <td className="strong">{signed(l.points)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  )
}

function Fixtures({ page }: { page: FantasyDayPage }) {
  const { day, fixtures, players } = page
  const byId = new Map(players.map((x) => [x.player_id, x]))
  const side = (f: FantasyDayPage['fixtures'][number], team: 'A' | 'B') => {
    const names = f.players.filter((x) => x.team === team).map((x) => {
      const pl = byId.get(x.player_id)
      return `${pl?.display_name ?? '?'}${day.locked && pl?.points !== null && pl?.points !== undefined ? ` (${signed(pl.points)})` : ''}`
    })
    while (names.length < 2) names.push('guest')
    return names.join(' & ')
  }
  return (
    <Card title="Matches of the day">
      {fixtures.length === 0 ? <p className="muted" style={{ margin: 0 }}>No match scheduled yet.</p> : (
        <ul className="fx-list">
          {fixtures.map((f) => (
            <li key={f.id} className={f.cancelled ? 'muted' : undefined}>
              <span className="small muted">{dateTime(f.scheduled_at)}{f.venue && ` · ${f.venue}`}</span>
              <span>{side(f, 'A')} <span className="muted">vs</span> {side(f, 'B')}</span>
              <span className="small">
                {f.cancelled ? 'cancelled'
                  : f.fantasy_published && f.match_key ? <>counted · <Link to={`/matches/${f.match_key}`}>{f.score_a}–{f.score_b}</Link></>
                  : day.locked ? <span className="muted">waiting for the video</span> : null}
              </span>
            </li>
          ))}
        </ul>
      )}
      {!day.locked && players.length > 0 && (
        <p className="muted small" style={{ marginBottom: 0 }}>
          Prices are fixed for the day: from 5.0 to 10.0 by each player&apos;s recent fantasy points per 21.
        </p>
      )}
    </Card>
  )
}

function DaysCard({ days, current }: { days: FantasyDaySummary[]; current: number | null }) {
  const nav = useNavigate()
  return (
    <Card title="Match days">
      <div className="table-wrap">
        <table>
          <thead>
            <tr><th className="left">Day</th><th className="left">When</th><th className="left">State</th>
              <th>You</th><th className="left">Leader</th></tr>
          </thead>
          <tbody>
            {days.map((d) => (
              <tr key={d.id} className={`clickable${d.id === current ? ' me' : ''}`} onClick={() => nav(`/fantasy/days/${d.id}`)}>
                <td className="left">{d.name} <span className="muted small">{d.season}</span></td>
                <td className="left">{d.locks_at ? dateTime(d.locks_at) : '–'}</td>
                <td className="left">{d.status === 'draft' ? 'draft' : d.final ? 'final' : d.locked ? 'live' : 'picking'}</td>
                <td>{d.my_points !== null ? signed(d.my_points) : d.has_lineup ? 'picked' : '–'}</td>
                <td className="left">{d.leader ? `${d.leader} (${signed(d.leader_points ?? 0)})` : '–'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  )
}

function RulesCard() {
  return (
    <Card title="How it works">
      <ul className="rules">
        <li>Before each match day, pick players who play that day (usually 3) without going over the budget. A player&apos;s
          price, from 5.0 to 10.0, follows their recent fantasy points per 21, and stays fixed for the day.</li>
        <li>Pick a captain: their points count double.</li>
        <li>Picks lock when the day&apos;s first match starts. Then everyone&apos;s lineup is shown.</li>
        <li>Each pick scores the fantasy points they make in the day&apos;s matches
          <Info label="About fantasy points">
            <span>The same points as the league table: the active scoring rules over the touches the video credits to the
              player. A missed touch costs nobody points.</span>
            <span className="info-foot"><Link to="/measure">How we measure</Link></span>
          </Info>
          , counted once an admin has reviewed the match and published it to fantasy. If a review changes a match later,
          its points move with it.</li>
        <li>The season table adds up every match day. Winning a day breaks ties.</li>
      </ul>
    </Card>
  )
}

/** /fantasy/standings: the season table. */
export function FantasyStandings() {
  const { api } = useApp()
  const days = useLoad(() => api.fantasyDays(), [])
  const seasons = [...new Set((days.data ?? []).map((d) => d.season))]
  const [picked, setPicked] = useState<string | null | undefined>(undefined)
  const season = picked === undefined ? seasons[0] ?? null : picked
  const table = useLoad(() => api.fantasyStandings(season), [season])
  return (
    <>
      <FantasyNav />
      <div className="row" style={{ marginBottom: 12 }}>
        <h1 style={{ margin: 0 }}>Standings</h1>
        <span className="spacer" />
        {seasons.length > 0 && (
          <select value={season ?? ''} onChange={(e) => setPicked(e.target.value || null)} aria-label="Season">
            {seasons.map((s) => <option key={s} value={s}>{s}</option>)}
            <option value="">All seasons</option>
          </select>
        )}
      </div>
      <Card>
        <ErrorBox error={table.error ?? days.error} />
        {table.loading && !table.data ? <Loading /> : !table.data?.length ? (
          <p className="muted" style={{ margin: 0 }}>No match day has locked yet.</p>
        ) : (
          <div className="table-wrap" style={{ opacity: table.loading ? 0.6 : 1 }}>
            <table>
              <thead>
                <tr>
                  <th className="left">#</th><th className="left">Manager</th>
                  <th title="Fantasy points over every locked match day">Pts</th>
                  <th title="Match days with a lineup">Days</th>
                  <th title="Match days finished on top (ties count for each)">Wins</th>
                  <th title="Points on the latest match day">Last</th>
                </tr>
              </thead>
              <tbody>
                {table.data.map((r) => (
                  <tr key={r.manager} className={r.is_me ? 'me' : undefined}>
                    <td className="left muted">{r.rank}</td>
                    <td className="left">{r.manager}</td>
                    <td className="strong">{signed(r.total)}</td>
                    <td>{r.days_played}</td>
                    <td>{r.day_wins}</td>
                    <td>{r.last_points === null ? '–' : signed(r.last_points)}</td>
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
