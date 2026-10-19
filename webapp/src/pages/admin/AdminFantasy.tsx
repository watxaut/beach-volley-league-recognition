import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { useApp, useLoad } from '../../app/state'
import { Card, ErrorBox, Loading } from '../../components/ui'
import { explainError } from '../../lib/api'
import { dateTime, fromLocalInput, localDate } from '../../lib/fantasy'
import type {
  FantasyDay, FantasyDayPatch, FantasyFixture, FantasyFixturePlayer, FixtureMismatch, Match, Participant, Player, Team,
} from '../../lib/types'

const DEFAULTS = { squad_size: 3, budget: 22.5, captain_multiplier: 2 }

/** /admin/fantasy: every match day, and a new one. */
export function AdminFantasyDays() {
  const { api } = useApp()
  const nav = useNavigate()
  const days = useLoad(() => api.fantasyDays(), [])
  const seasons = useLoad(() => api.seasons(), [])
  const [form, setForm] = useState({ season: '', name: '', ...DEFAULTS })
  const [error, setError] = useState<string | null>(null)
  const known = [...new Set([...(days.data ?? []).map((d) => d.season), ...(seasons.data ?? [])])]
  const season = form.season || known[0] || ''
  const create = async () => {
    setError(null)
    try {
      const day = await api.createFantasyDay({ ...form, season: season.trim(), name: form.name.trim() })
      nav(`/admin/fantasy/${day.id}`)
    } catch (err) {
      setError(explainError(err))
    }
  }
  return (
    <>
      <Card title="Match days" action={<span className="muted small">A day groups the matches people pick from</span>}>
        <ErrorBox error={days.error} />
        {days.loading ? <Loading /> : !days.data?.length ? <p className="muted" style={{ margin: 0 }}>No match day yet.</p> : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr><th className="left">Day</th><th className="left">Season</th><th className="left">State</th>
                  <th className="left">Locks</th><th>Matches</th></tr>
              </thead>
              <tbody>
                {days.data.map((d) => (
                  <tr key={d.id} className="clickable" onClick={() => nav(`/admin/fantasy/${d.id}`)}>
                    <td className="left"><Link to={`/admin/fantasy/${d.id}`}>{d.name}</Link></td>
                    <td className="left">{d.season}</td>
                    <td className="left">{d.status === 'draft' ? <span className="badge badge-draft">draft</span>
                      : d.final ? 'final' : d.locked ? 'locked' : 'open for picks'}</td>
                    <td className="left">{d.locks_at ? dateTime(d.locks_at) : '–'}</td>
                    <td>{d.n_fixtures}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
      <Card title="New match day">
        <ErrorBox error={error} />
        <form className="details-grid" onSubmit={(e) => { e.preventDefault(); void create() }}>
          <label className="field"><span>Season</span>
            <input list="fantasy-seasons" value={season} placeholder="e.g. 2026 Autumn"
                   onChange={(e) => setForm({ ...form, season: e.target.value })} />
            <datalist id="fantasy-seasons">{known.map((s) => <option key={s} value={s} />)}</datalist>
          </label>
          <label className="field"><span>Name</span>
            <input value={form.name} placeholder={`Match day ${(days.data?.filter((d) => d.season === season).length ?? 0) + 1}`}
                   onChange={(e) => setForm({ ...form, name: e.target.value })} />
          </label>
          <RulesFields value={form} onChange={(r) => setForm({ ...form, ...r })} />
          <div className="details-save">
            <button type="submit" className="primary" disabled={!season.trim() || !form.name.trim()}>Create draft</button>
          </div>
        </form>
      </Card>
    </>
  )
}

function RulesFields({ value, onChange, disabled }: {
  value: { squad_size: number; budget: number; captain_multiplier: number }
  onChange: (v: { squad_size: number; budget: number; captain_multiplier: number }) => void
  disabled?: boolean
}) {
  return (
    <>
      <label className="field"><span>Players per lineup</span>
        <input type="number" min={1} max={8} value={value.squad_size} disabled={disabled}
               onChange={(e) => onChange({ ...value, squad_size: Number(e.target.value) })} /></label>
      <label className="field"><span>Budget</span>
        <input type="number" min={1} step={0.5} value={value.budget} disabled={disabled}
               onChange={(e) => onChange({ ...value, budget: Number(e.target.value) })} /></label>
      <label className="field"><span>Captain ×</span>
        <input type="number" min={1} step={0.5} value={value.captain_multiplier} disabled={disabled}
               onChange={(e) => onChange({ ...value, captain_multiplier: Number(e.target.value) })} /></label>
    </>
  )
}

/** /admin/fantasy/:id: rules, fixtures, prices, open. */
export function AdminFantasyDay() {
  const { id = '' } = useParams()
  const dayId = Number(id)
  const { api } = useApp()
  const nav = useNavigate()
  const [error, setError] = useState<string | null>(null)
  const data = useLoad(async () => {
    const rows = await api.fantasyDayRows()
    const day = rows.find((d) => d.id === dayId)
    if (!day) return null
    const [fixtures, page, players, venues, matches] = await Promise.all([
      api.fantasyFixtures(dayId), api.fantasyDay(dayId), api.players(), api.venues(), api.matches()])
    const fxPlayers = await api.fixturePlayers(fixtures.map((f) => f.id))
    return { day, fixtures, page, players, venues, matches, fxPlayers }
  }, [dayId])
  if (data.loading && !data.data) return <Loading />
  if (!data.data) return <><ErrorBox error={data.error} /><p>Match day not found.</p></>
  const { day, fixtures, page, players, venues, matches, fxPlayers } = data.data
  const locked = page?.day.locked ?? false

  async function run(fn: () => Promise<unknown>): Promise<boolean> {
    setError(null)
    try {
      await fn()
      data.reload()
      return true
    } catch (err) {
      setError(explainError(err))
      return false
    }
  }
  const name = (pid: number) => players.find((p) => p.id === pid)?.display_name ?? '?'
  const side = (f: FantasyFixture, team: Team) => {
    const names = fxPlayers.filter((x) => x.fixture_id === f.id && x.team === team).map((x) => name(x.player_id))
    return names.length ? names.join(' & ') + (names.length < 2 ? ' + guest' : '') : 'guests'
  }
  const matchOf = (f: FantasyFixture) => matches.find((m) => m.id === f.match_id)

  return (
    <>
      <p className="muted small" style={{ marginBottom: 4 }}><Link to="/admin/fantasy">Fantasy game</Link> / {day.name}</p>
      <div className="row" style={{ marginBottom: 12 }}>
        <h1 style={{ margin: 0 }}>{day.name}</h1>
        <span className="muted">{day.season}</span>
        {day.status === 'draft' && <span className="badge badge-draft">draft</span>}
        <span className="spacer" />
        {day.status === 'open' && <Link to={`/fantasy/days/${day.id}`}>Members' page →</Link>}
      </div>
      <ErrorBox error={error ?? data.error} />

      <Card title="1 · Rules" action={<span className="muted small">{day.status === 'draft' ? 'Fixed once the day opens' : 'Fixed: the day is open'}</span>}>
        <DayForm key={JSON.stringify(day)} day={day} onSave={(patch) => run(() => api.updateFantasyDay(day.id, patch))} />
        {day.status === 'draft' && (
          <button className="danger" style={{ marginTop: 12 }}
                  onClick={() => run(async () => { await api.deleteFantasyDay(day.id); nav('/admin/fantasy') })}>
            Delete this draft
          </button>
        )}
      </Card>

      <Card title="2 · Matches of the day" action={<span className="muted small">The first one's start locks the picks</span>}>
        {fixtures.length > 0 && (
          <div className="table-wrap">
            <table>
              <thead>
                <tr><th className="left">When</th><th className="left">Team A</th><th className="left">Team B</th>
                  <th className="left">Video</th><th className="left">Fantasy</th><th /></tr>
              </thead>
              <tbody>
                {fixtures.map((f) => {
                  const m = matchOf(f)
                  return (
                    <tr key={f.id} className={f.cancelled ? 'muted' : undefined}>
                      <td className="left">{dateTime(f.scheduled_at)}{f.venue && <span className="muted small"> · {f.venue}</span>}</td>
                      <td className="left">{side(f, 'A')}</td>
                      <td className="left">{side(f, 'B')}</td>
                      <td className="left">{m ? <Link to={`/admin/matches/${m.match_key}`}>{m.score_a}–{m.score_b}</Link>
                        : f.cancelled ? '–' : <span className="muted small">link it from the match's admin page</span>}</td>
                      <td className="left">
                        {f.fantasy_published
                          ? <>counted <button className="link" onClick={() => run(() => api.publishFixtureToFantasy(f.id, false))}>remove</button></>
                          : m && !f.cancelled
                            ? <button disabled={m.status !== 'published'} title={m.status !== 'published' ? 'Publish the match first' : undefined}
                                      onClick={() => run(() => api.publishFixtureToFantasy(f.id, true))}>Publish to fantasy</button>
                            : <span className="muted">–</span>}
                      </td>
                      <td>
                        {day.status === 'draft'
                          ? <button className="link" onClick={() => run(() => api.deleteFixture(f.id))}>delete</button>
                          : !f.fantasy_published && (
                            <button className="link" onClick={() => run(() => api.updateFixture(f.id, { cancelled: !f.cancelled }))}>
                              {f.cancelled ? 'restore' : 'cancel'}
                            </button>)}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
        {locked ? <p className="muted small" style={{ marginBottom: 0 }}>The day is locked: no match can be added or moved.</p>
          : <NewFixture players={players} venues={venues}
                        onAdd={(at, venue, list) => run(() => api.addFixture(day.id, at, venue, list))} />}
        <p className="muted small" style={{ marginBottom: 0 }}>
          List only players of the league; a guest is left out and nobody can pick them. A cancelled match scores 0
          for whoever picked its players.
        </p>
      </Card>

      {page && page.players.length > 0 && (
        <Card title="3 · Prices" action={<span className="muted small">{day.status === 'draft'
          ? 'Suggested from recent fantasy per 21; override any before opening' : 'Fixed while people pick'}</span>}>
          <div className="table-wrap">
            <table>
              <thead><tr><th className="left">Player</th><th title="Fantasy points per 21 over the last 10 published matches">/21</th><th>Price</th><th /></tr></thead>
              <tbody>
                {page.players.map((p) => (
                  <tr key={p.player_id}>
                    <td className="left">{p.display_name}</td>
                    <td>{p.per21 ?? '–'}</td>
                    <td className="strong">{p.price.toFixed(1)}{p.is_override && <span className="muted small"> (set by hand)</span>}</td>
                    <td className="left">
                      {day.status === 'draft' && (
                        <PriceEdit key={`${p.player_id}:${p.price}`} price={p.price} overridden={p.is_override}
                                   onSave={(v) => run(() => api.setFantasyPrice(day.id, p.player_id, v))} />
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      <Card title="4 · Open for picks">
        {day.status === 'draft' ? (
          <>
            <p className="muted" style={{ marginTop: 0 }}>
              Opening fixes the prices and the rules and shows the day to every member. They can pick until the first match
              starts{page?.day.locks_at ? ` (${dateTime(page.day.locks_at)})` : ''}.
            </p>
            <button className="primary" disabled={!page?.players.length} onClick={() => run(() => api.openFantasyDay(day.id))}>
              Open for picks
            </button>
          </>
        ) : (
          <p style={{ margin: 0 }}>
            Open since {day.opened_at ? new Date(day.opened_at).toLocaleString() : '–'} · {page?.n_lineups ?? 0} lineup
            {page?.n_lineups === 1 ? '' : 's'} · {page?.day.final ? 'final' : locked ? 'locked' : 'taking picks'}
          </p>
        )}
      </Card>
    </>
  )
}

function DayForm({ day, onSave }: { day: FantasyDay; onSave: (p: FantasyDayPatch) => void }) {
  const [form, setForm] = useState<Required<FantasyDayPatch>>({
    season: day.season, name: day.name, squad_size: day.squad_size, budget: day.budget,
    captain_multiplier: day.captain_multiplier })
  const draft = day.status === 'draft'
  return (
    <form className="details-grid" onSubmit={(e) => {
      e.preventDefault()
      onSave(draft ? form : { season: form.season, name: form.name })
    }}>
      <label className="field"><span>Season</span>
        <input value={form.season} onChange={(e) => setForm({ ...form, season: e.target.value })} /></label>
      <label className="field"><span>Name</span>
        <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></label>
      <RulesFields value={form} disabled={!draft} onChange={(r) => setForm({ ...form, ...r })} />
      <div className="details-save"><button type="submit">Save</button></div>
    </form>
  )
}

function PriceEdit({ price, overridden, onSave }: { price: number; overridden: boolean; onSave: (v: number | null) => void }) {
  const [v, setV] = useState(String(price))
  return (
    <form className="row" onSubmit={(e) => { e.preventDefault(); onSave(Number(v)) }}>
      <input type="number" min={0.5} step={0.5} value={v} onChange={(e) => setV(e.target.value)}
             aria-label="Price" style={{ width: 80 }} />
      <button type="submit" disabled={!(Number(v) > 0) || Number(v) === price}>Set</button>
      {overridden && <button type="button" className="link" onClick={() => onSave(null)}>use suggested</button>}
    </form>
  )
}

const SEATS: { team: Team; label: string }[] = [
  { team: 'A', label: 'Team A' }, { team: 'A', label: 'Team A' }, { team: 'B', label: 'Team B' }, { team: 'B', label: 'Team B' }]

function NewFixture({ players, venues, onAdd }: {
  players: Player[]; venues: string[]
  onAdd: (at: string, venue: string | null, list: { player_id: number; team: Team }[]) => Promise<boolean>
}) {
  const [at, setAt] = useState('')
  const [venue, setVenue] = useState('')
  const [seats, setSeats] = useState<string[]>(['', '', '', ''])
  const chosen = seats.filter(Boolean)
  const add = async () => {
    const list = seats.map((s, i) => (s ? { player_id: Number(s), team: SEATS[i].team } : null))
      .filter((x): x is { player_id: number; team: Team } => x !== null)
    if (await onAdd(fromLocalInput(at), venue || null, list)) {
      setSeats(['', '', '', ''])
    }
  }
  return (
    <form className="details-grid" style={{ marginTop: 12 }} onSubmit={(e) => { e.preventDefault(); void add() }}>
      <label className="field"><span>Starts</span>
        <input type="datetime-local" value={at} onChange={(e) => setAt(e.target.value)} /></label>
      <label className="field"><span>Venue</span>
        <select value={venue} onChange={(e) => setVenue(e.target.value)}>
          <option value="">— not set —</option>
          {venues.map((v) => <option key={v} value={v}>{v}</option>)}
        </select></label>
      {SEATS.map((s, i) => (
        <label key={i} className="field"><span>{s.label} · {i % 2 + 1}</span>
          <select value={seats[i]} onChange={(e) => setSeats(seats.map((x, j) => (j === i ? e.target.value : x)))}>
            <option value="">guest / not set</option>
            {players.filter((p) => p.active && (seats[i] === String(p.id) || !chosen.includes(String(p.id))))
              .map((p) => <option key={p.id} value={p.id}>{p.display_name}</option>)}
          </select></label>
      ))}
      <div className="details-save"><button type="submit" disabled={!at || chosen.length === 0}>Add match</button></div>
    </form>
  )
}

/** The admin match page's link to the game: which fixture this video is, and
 * whether its points count. Suggests the fixture of the same date whose players
 * overlap the assigned slots most, then the closest start time. */
export function FantasyLink({ match: m, participants }: { match: Match; participants: Participant[] }) {
  const { api } = useApp()
  const [error, setError] = useState<string | null>(null)
  const [pick, setPick] = useState<string | null>(null)
  const data = useLoad(async () => {
    const [fixtures, days] = await Promise.all([api.fantasyFixtures(), api.fantasyDayRows()])
    const fxPlayers = await api.fixturePlayers(fixtures.map((f) => f.id))
    const players = await api.players()
    const linked = fixtures.find((f) => f.match_id === m.id) ?? null
    const mismatch: FixtureMismatch | null = linked ? await api.fixtureMismatch(linked.id) : null
    return { fixtures, days, fxPlayers, players, linked, mismatch }
  }, [m.id, m.status])
  if (data.loading && !data.data) return <Loading />
  if (!data.data) return <ErrorBox error={data.error} />
  const { fixtures, days, fxPlayers, players, linked, mismatch } = data.data

  async function run(fn: () => Promise<unknown>) {
    setError(null)
    try {
      await fn()
      data.reload()
    } catch (err) {
      setError(explainError(err))
    }
  }
  const label = (f: FantasyFixture) => {
    const names = (team: Team) => fxPlayers.filter((x) => x.fixture_id === f.id && x.team === team)
      .map((x) => players.find((p) => p.id === x.player_id)?.display_name ?? '?').join(' & ') || 'guests'
    return `${days.find((d) => d.id === f.match_day_id)?.name ?? '?'} · ${dateTime(f.scheduled_at)} · ${names('A')} vs ${names('B')}`
  }
  if (linked) {
    return (
      <div className="stack">
        <ErrorBox error={error} />
        <p style={{ margin: 0 }}>This video is <strong>{label(linked)}</strong>.</p>
        {mismatch && (mismatch.missing.length > 0 || mismatch.extra.length > 0) && (
          <div className="notice notice-warn" style={{ margin: 0 }}>
            {mismatch.missing.length > 0 && <>In the fixture but not in this match: {mismatch.missing.join(', ')} (they score 0). </>}
            {mismatch.extra.length > 0 && <>Played but not in the fixture: {mismatch.extra.join(', ')} (nobody could pick them).</>}
          </div>
        )}
        <div className="row">
          {linked.fantasy_published
            ? <><span>Counted in the game.</span><button onClick={() => run(() => api.publishFixtureToFantasy(linked.id, false))}>Remove from fantasy</button></>
            : <button className="primary" disabled={m.status !== 'published'} onClick={() => run(() => api.publishFixtureToFantasy(linked.id, true))}>
                Publish to fantasy</button>}
          <button className="link" onClick={() => run(() => api.linkFixtureMatch(linked.id, null))}>unlink</button>
        </div>
        {m.status !== 'published' && !linked.fantasy_published && <p className="muted small" style={{ margin: 0 }}>Publish the match first (4 · Publish).</p>}
      </div>
    )
  }
  const assigned = new Set(participants.map((p) => p.player_id).filter((x): x is number => x !== null))
  const start = m.start_time ? new Date(`${m.match_date}T${m.start_time}`).getTime() : null
  const free = fixtures.filter((f) => !f.cancelled && f.match_id === null)
  const overlap = (f: FantasyFixture) => fxPlayers.filter((x: FantasyFixturePlayer) => x.fixture_id === f.id && assigned.has(x.player_id)).length
  const sameDay = free.filter((f) => localDate(f.scheduled_at) === m.match_date)
    .sort((a, b) => overlap(b) - overlap(a)
      || (start === null ? 0 : Math.abs(new Date(a.scheduled_at).getTime() - start) - Math.abs(new Date(b.scheduled_at).getTime() - start)))
  const others = free.filter((f) => !sameDay.includes(f))
  const value = pick ?? (sameDay[0] ? String(sameDay[0].id) : '')
  if (!free.length) {
    return <p className="muted" style={{ margin: 0 }}>No fixture waiting for a video. Schedule it under <Link to="/admin/fantasy">Fantasy game</Link>, or skip: a match without a fixture is not in the game.</p>
  }
  return (
    <div className="stack">
      <ErrorBox error={error} />
      <div className="row">
        <select value={value} onChange={(e) => setPick(e.target.value)} aria-label="Fixture">
          <option value="">— not in the game —</option>
          {sameDay.length > 0 && <optgroup label="Same date">{sameDay.map((f) => <option key={f.id} value={f.id}>{label(f)}</option>)}</optgroup>}
          {others.length > 0 && <optgroup label="Other dates">{others.map((f) => <option key={f.id} value={f.id}>{label(f)}</option>)}</optgroup>}
        </select>
        <button disabled={!value} onClick={() => run(() => api.linkFixtureMatch(Number(value), m.id))}>Link</button>
      </div>
      <p className="muted small" style={{ margin: 0 }}>Link the video to the fixture people picked from, then publish it to fantasy to count its points.</p>
    </div>
  )
}

