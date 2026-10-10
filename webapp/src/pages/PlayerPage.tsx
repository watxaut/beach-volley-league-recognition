import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useApp, useLoad } from '../app/state'
import { useTabKey, useWindowKey } from '../app/window'
import { RollingChart, Sparkline, StackBar, type Segment } from '../components/Charts'
import { Compare, type CompareMode } from '../components/Compare'
import { AttackMap } from '../components/Court'
import { PassMap } from '../components/PassMap'
import { HittingTile, RateTile } from '../components/Rate'
import { Approx, Card, ErrorBox, Loading, Segmented, StatInfo, Tabs, Tile } from '../components/ui'
import { WindowPicker } from '../components/WindowPicker'
import { compare, MIN_PEERS, RECENT, splitEarlier, sumHistory, type CompareRow } from '../lib/compare'
import { formatDate, matchLabel, signed } from '../lib/format'
import { passPoints, summarize, type PassKind, PASS_LABEL } from '../lib/passes'
import { hitText, hitting, MIN_N, pct, rate, ROLLING_WINDOW, rolling } from '../lib/stats'
import type { HistoryRow, LeaderRow, PlayerAnalytics, PlayerProfile, ShotKey } from '../lib/types'
import { ALL_TIME, windowLabel, windowParams } from '../lib/window'

// Overview and Matches are league tier (every member); Attack and Serve &
// receive are the player's analytics tier.
const TABS = ['overview', 'attack', 'serve', 'matches'] as const
type TabKey = typeof TABS[number]
const TAB_LABEL: Record<TabKey, string> = { overview: 'Overview', attack: 'Attack', serve: 'Serve & receive', matches: 'Matches' }

const plural = (n: number, one: string, many = `${one}s`) => `${n} ${n === 1 ? one : many}`

export function PlayerPage() {
  const { id = '' } = useParams()
  const { api } = useApp()
  const [key, setKey] = useWindowKey()
  const [tab, setTab] = useTabKey(TABS)
  const data = useLoad(() => api.playerProfile(Number(id), windowParams(key)), [id, key])
  const board = useLoad(() => api.leaderboard(windowParams(key)), [key])
  // every match of the player, for "against your earlier matches"; under "all
  // time" the profile above already is that
  const whole = useLoad(() => (key === 'all' ? Promise.resolve(null) : api.playerProfile(Number(id), ALL_TIME)), [id, key === 'all'])
  const seasons = useLoad(() => api.seasons(), [])

  if (data.loading && !data.data) return <Loading />
  if (data.error) return <ErrorBox error={data.error} />
  if (!data.data) return <p>Player not found. <Link to="/league">League</Link></p>
  const { player, totals: t, history, analytics, can_see_analytics, form } = data.data
  const delta = form.avg5 !== null && form.avg_all !== null ? form.avg5 - form.avg_all : null
  const lost = history.filter((h) => h.won === false).length
  const rows = board.data ?? []
  const rank = rows.findIndex((r) => r.player_id === player.id) + 1
  const who = player.is_me ? 'You' : player.display_name
  const privateNote = <div className="notice">{player.display_name} keeps detailed analytics private.</div>

  return (
    <>
      <div className="filter-row">
        <WindowPicker value={key} onChange={setKey} seasons={seasons.data ?? []} />
      </div>
      <div className="hero" style={{ marginBottom: 16, opacity: data.loading ? 0.6 : 1 }}>
        <div>
          <h1>{player.display_name}{player.is_me && <span className="badge" style={{ marginLeft: 8 }}>you</span>}</h1>
          <p className="muted" style={{ margin: 0 }}>
            {plural(t.matches, 'match', 'matches')} · <span title="Won – lost">{t.wins}–{lost}</span>
            {rank > 0 && <> · <span title={`By fantasy points among ${rows.length} players in this view, as on the league table`}><strong>#{rank}</strong> in the league</span></>}
          </p>
          {form.n >= 2 && (
            <div className="row small" style={{ marginTop: 6 }} title="The newest five matches, whatever the time filter">
              <span className="muted">Form</span>
              <Sparkline values={form.last5} label={`Fantasy points in the last ${form.last5.length} matches`} />
              <span>
                {form.avg5?.toFixed(1)} <span className="muted">avg of last {form.last5.length}</span>
                {delta !== null && form.n > 5 && (
                  <> · <span className={delta >= 0 ? 'delta-up' : 'delta-down'}>{signed(delta)}</span> <span className="muted">vs all time</span></>
                )}
              </span>
            </div>
          )}
        </div>
        <div className="hero-side">
          <div className="hero-number">{signed(t.fantasy)}</div>
          <div className="tile-label">fantasy points<StatInfo term="fantasy" /></div>
          {t.fantasy_per_21 !== null && <div className="muted small">{signed(t.fantasy_per_21)} per 21 points</div>}
        </div>
      </div>

      <Tabs tabs={TABS.map((k) => ({ key: k, label: TAB_LABEL[k] }))} value={tab} onChange={setTab} label="Player statistics" />

      <div role="tabpanel" aria-label={TAB_LABEL[tab]} style={{ opacity: data.loading ? 0.6 : 1 }}>
        {tab === 'overview' && (
          <Overview data={data.data} board={rows} boardError={board.error} windowKey={key} who={who}
                    allHistory={key === 'all' ? history : whole.data?.history ?? null} />
        )}
        {tab === 'attack' && (can_see_analytics && analytics ? <Attack a={analytics} /> : privateNote)}
        {tab === 'serve' && (can_see_analytics && analytics ? <Serve a={analytics} who={who} /> : privateNote)}
        {tab === 'matches' && <Matches history={history} />}
      </div>

      <p className="muted small" style={{ marginBottom: 0 }}>
        {tab !== 'overview' && tab !== 'matches' && player.is_me && !player.profile_public
          && <>Only you and admins see this tab · <Link to="/settings">share</Link> · </>}
        <Link to="/measure">How we measure</Link>
      </p>
    </>
  )
}

/** The reference a league comparison is counted over, in words. */
function leagueScope(key: string): string {
  if (key === 'all') return 'all time'
  if (/^n\d+$/.test(key)) return `over the league's ${windowLabel(key)}`
  return key.startsWith('s:') ? `in ${windowLabel(key)}` : `over the ${windowLabel(key)}`
}

function Overview({ data, board, boardError, windowKey, who, allHistory }: {
  data: PlayerProfile; board: LeaderRow[]; boardError: string | null; windowKey: string; who: string
  allHistory: HistoryRow[] | null
}) {
  const [mode, setMode] = useState<CompareMode>('league')
  const { player, totals: t, history } = data
  const mine = board.find((r) => r.player_id === player.id)
  const others = board.filter((r) => r.player_id !== player.id)
    .map((r) => ({ id: r.player_id, name: r.display_name, sample: r }))
  const { now, before } = splitEarlier(allHistory ?? [], windowKey === 'all' ? null : history.map((h) => h.match_id))
  const hasEarlier = now.length > 0 && before.length > 0
  const shown: CompareMode = mode === 'earlier' && !hasEarlier ? 'league' : mode

  const rows: CompareRow[] = shown === 'league'
    ? (mine ? compare(mine, others) : [])
    : compare(sumHistory(now), [{ id: 0, name: 'Before', sample: sumHistory(before) }], 1)
  const noReference = rows.length > 0 && rows.every((r) => r.ref === null)
  const whose = player.is_me ? 'your' : 'their'

  return (
    <>
      <Card>
        <div className="tiles tiles-5">
          <Tile label="Kills" value={t.kills} info={<StatInfo term="kills" />} />
          <Tile label="Aces" value={t.aces} info={<StatInfo term="aces" />} />
          <Tile label="Digs" value={t.digs} info={<StatInfo term="digs" />} />
          <Tile label="Assists" value={t.assists} info={<StatInfo term="assists" />} />
          <Tile label="Errors" value={t.errors} info={<StatInfo term="errors" />} />
        </div>
      </Card>

      <Card
        title={<>{who} vs {shown === 'league' ? 'the league' : `${whose} earlier matches`}<StatInfo term="compare" /></>}
        action={(
          <Segmented<CompareMode> label="Compare with" value={shown} onChange={setMode} options={[
            { key: 'league', label: 'League' },
            { key: 'earlier', label: 'Earlier matches', disabled: !hasEarlier,
              title: hasEarlier ? undefined : windowKey === 'all'
                ? `Needs matches before ${whose} newest ${RECENT}` : `Needs matches before this period`,
            },
          ]} />
        )}>
        <ErrorBox error={boardError} />
        {rows.length === 0 ? <p className="muted" style={{ margin: 0 }}>No published matches in this view.</p> : (
          <>
            <p className="muted small">
              {shown === 'league'
                ? <>Against everyone else, {leagueScope(windowKey)}.</>
                : <>{windowKey === 'all' ? `The newest ${plural(now.length, 'match', 'matches')}` : `The ${plural(now.length, 'match', 'matches')} of this period`} against
                  the {before.length} before.</>}
              {noReference && shown === 'league' && <> The league average appears once {MIN_PEERS} other players have played in this view; until then every bar starts at zero.</>}
            </p>
            <Compare rows={rows} mode={shown} who={who} refName={shown === 'league' ? 'League' : 'Before'} />
          </>
        )}
      </Card>
    </>
  )
}

function Attack({ a }: { a: PlayerAnalytics }) {
  const hitAll = { n: a.n_attacks, kills: a.n_kills, errors: a.n_attack_errors }
  // Before migration 20261009110000 the database has no `shots`, and the type
  // on a landing is still the causal guess: draw no type at all until then.
  const landings = a.shots ? a.landings : a.landings.map((l) => ({ ...l, type: null }))
  return (
    <>
      <Card>
        <div className="tiles tiles-3">
          <HittingTile t={hitAll} />
          <RateTile label="Kill %" k={a.n_kills} n={a.n_attacks} term="kill_rate" unit="attacks" />
          <RateTile label="Attack errors" k={a.n_attack_errors} n={a.n_attacks} term="attack_errors" unit="attacks" />
        </div>
      </Card>

      <div className="grid grid-2">
        <Card title={<>Attack map<StatInfo term="attack_map" /> <Approx grade="B" /></>}>
          {a.landings.length
            ? <AttackMap landings={landings} />
            : <p className="muted" style={{ margin: 0 }}>No attack positions recorded yet.</p>}
        </Card>
        <div>
          <Card title={<>By situation<StatInfo term="hit_split" /></>}>
            <table>
              <thead><tr><th className="left" /><th>Att</th><th>K</th><th>E</th><th>Hit %</th></tr></thead>
              <tbody>
                {([['Off the reception', a.hit.reception], ['In transition', a.hit.transition]] as const).map(([label, h]) => (
                  <tr key={label}>
                    <td className="left">{label}</td><td>{h.n}</td><td>{h.kills}</td><td>{h.errors}</td>
                    <td className="strong">{hitText(hitting(h))}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
          {a.shots && <ByShot shots={a.shots} />}
          <Trend title="Kill rate" unit="attack" hits={a.attack_series.map((s) => s.r === 'kill')}
                 dates={a.attack_series.map((s) => s.d)} />
        </div>
      </div>
    </>
  )
}

const SHOT_ROWS: { key: ShotKey; label: string; color: string; hint?: string }[] = [
  { key: 'hard', label: 'Hard', color: 'var(--shot-hard)', hint: 'a driven spike' },
  { key: 'touch', label: 'Touch', color: 'var(--shot-touch)', hint: 'a placed spike: a lob, a poke, a slow drop' },
  { key: 'free', label: 'Free ball', color: 'var(--shot-free)', hint: 'sent back over without an attack' },
  { key: 'unread', label: 'Not read', color: 'var(--axis)', hint: 'a spike whose flight could not be typed' },
]

/** How the player's attacks split into hard spikes, touch shots and free
 * balls, and what each kind earned. Every attack is in exactly one row. */
function ByShot({ shots }: { shots: NonNullable<PlayerAnalytics['shots']> }) {
  const total = SHOT_ROWS.reduce((n, r) => n + shots[r.key].n, 0)
  const rows = SHOT_ROWS.filter((r) => r.key !== 'unread' || shots.unread.n > 0)
  return (
    <Card title={<>By shot<StatInfo term="shot_type" /> <Approx grade="B" /></>}>
      {total === 0 ? <p className="muted" style={{ margin: 0 }}>No attacks credited yet.</p> : (
        <>
          <StackBar label="Attacks by shot"
                    segments={rows.map((r) => ({ label: r.label.toLowerCase(), n: shots[r.key].n, color: r.color, hint: r.hint }))} />
          <table style={{ marginTop: 10 }}>
            <thead>
              <tr><th className="left" /><th>Att</th><th title="Share of all attacks">Share</th><th>K</th><th>E</th><th>Hit %</th></tr>
            </thead>
            <tbody>
              {rows.map((r) => {
                const h = shots[r.key]
                return (
                  <tr key={r.key}>
                    <td className="left" title={r.hint}>{r.label}</td><td>{h.n}</td>
                    <td>{pct(rate(h.n, total))}</td><td>{h.kills}</td><td>{h.errors}</td>
                    <td className="strong">{hitText(hitting(h))}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </>
      )}
    </Card>
  )
}

function Serve({ a, who }: { a: PlayerAnalytics; who: string }) {
  const { own_serve: own, team_serving: serving, team_receiving: receiving } = a.rally
  return (
    <>
      <Card>
        <div className="tiles">
          <RateTile label="Ace %" k={a.n_aces} n={a.n_serves} term="ace_rate" unit="serves" />
          <RateTile label="Serve errors" k={a.n_serve_errors} n={a.n_serves} term="serve_errors" unit="serves" />
          <RateTile label={who === 'You' ? 'Your serve won' : 'Serve won'} k={own.won} n={own.n} term="own_serve" unit="serves"
                    note={`The team won ${serving.won} of ${serving.n} points while serving.`} />
          <RateTile label="Side-out %" k={receiving.won} n={receiving.n} term="side_out" unit="points" />
        </div>
      </Card>
      <div className="grid grid-2">
        <ServeTargeting a={a} who={who} />
        <ReceptionOutcome a={a} />
      </div>
      <PassCard a={a} />
      <Trend title="Serves in play" unit="serve" hits={a.serve_series.map((s) => s.r !== 'error')}
             dates={a.serve_series.map((s) => s.d)} />
    </>
  )
}

function ServeTargeting({ a, who }: { a: PlayerAnalytics; who: string }) {
  const { serve_in: i, serve_out: o } = a
  const partner = Math.max(0, i.team_credited - i.mine)
  const unseen = Math.max(0, i.opp_serves - i.team_credited)
  const inSegments: Segment[] = [
    { label: who.toLowerCase() === 'you' ? 'you' : who, n: i.mine, color: 'var(--accent)' },
    { label: 'partner', n: partner, color: 'var(--heat-1)' },
    { label: 'not seen', n: unseen, color: 'var(--axis)', hint: 'an ace, or nobody credited with the first touch' },
  ]
  const shades = ['var(--heat-3)', 'var(--heat-1)', 'var(--heat-2)', 'var(--heat-0)']
  const outSegments: Segment[] = [
    ...o.to.map((r, idx) => ({ label: r.display_name, n: r.n, color: shades[idx % shades.length] })),
    { label: 'not seen', n: o.unseen, color: 'var(--axis)' },
  ]
  return (
    <Card title={<>Serve targeting<StatInfo term="serve_in" /></>}>
      {i.opp_serves + o.serves === 0 ? <p className="muted" style={{ margin: 0 }}>No serves yet.</p> : (
        <div className="stack">
          {i.opp_serves > 0 && (
            <div>
              <h3>Who they serve</h3>
              <StackBar segments={inSegments} label="Serves aimed at the team, by who took them" />
            </div>
          )}
          {o.serves > 0 && (
            <div style={{ marginTop: 16 }}>
              <h3>Who took {who === 'You' ? 'your' : 'their'} serves</h3>
              <StackBar segments={outSegments} label="Who received the serves" />
            </div>
          )}
        </div>
      )}
    </Card>
  )
}

function ReceptionOutcome({ a }: { a: PlayerAnalytics }) {
  const r = a.reception
  const segments: Segment[] = [
    { label: 'spike', n: r.spike, color: 'var(--accent)', hint: 'the possession reached a hard or touch attack' },
    { label: 'free ball', n: r.overpass, color: 'var(--heat-1)', hint: 'sent back over without an attack; a soft rainbow below about 2.15 m counts here' },
    { label: 'error', n: r.error, color: 'var(--bad)' },
    { label: 'no attack', n: r.none, color: 'var(--axis)', hint: 'the ball died or the next touch was not seen' },
  ]
  return (
    <Card title={<>After the reception<StatInfo term="reception" /></>}>
      {r.n === 0 ? <p className="muted" style={{ margin: 0 }}>No receptions credited yet.</p> : (
        <>
          <h3>What {plural(r.n, 'reception')} became</h3>
          <StackBar segments={segments} label="What the receptions became" />
          <p className="small" style={{ margin: '12px 0 0' }}>
            <strong>{r.first_ball_kills}</strong> <span className="muted">won the point on the first attack.</span>
          </p>
        </>
      )}
    </Card>
  )
}

/** Receptions (a dig after a serve) and defenses (a dig after an attack) with
 * where the ball went next. The balls are not judged against a target: the map
 * shows whether they fall in one spot, the tile how tight that spot is. */
function PassCard({ a }: { a: PlayerAnalytics }) {
  const passes = a.passes
  // a database without the pass_map migration has no `passes` at all
  if (passes === undefined) return null
  const points = passPoints(passes)
  return (
    <Card title={<>Where the pass went<StatInfo term="pass_map" /></>}>
      {points.length === 0 ? (
        <p className="muted" style={{ margin: 0 }}>No receptions or defenses credited yet.</p>
      ) : (
        <>
          <div className="tiles tiles-4" style={{ marginBottom: 12 }}>
            {(['reception', 'defense'] as PassKind[]).map((k) => {
              const s = summarize(points, k)
              return [
                <Tile key={k} label={`${PASS_LABEL[k]}s`} value={s.n}
                      sub={`${s.seen} with the next touch seen`} />,
                <Tile key={`${k}-spread`} label={`${PASS_LABEL[k]} spread`}
                      value={s.spot ? `${s.spot.r.toFixed(1)} m` : '–'} quiet={!s.spot}
                      sub={s.spot ? 'half fall within this of their usual spot' : `from ${MIN_N} seen`}
                      info={<StatInfo term="pass_spread" />} />,
              ]
            })}
          </div>
          <PassMap passes={passes} />
        </>
      )}
    </Card>
  )
}

/** A rate over rolling windows of attempts, once there are enough of them;
 * until then one line saying when it starts. */
function Trend({ title, unit, hits, dates }: { title: string; unit: string; hits: boolean[]; dates: string[] }) {
  const points = rolling(hits)
  if (points.length === 0) {
    return (
      <p className="muted small trend-wait">
        {title} trend from {ROLLING_WINDOW} {unit}s · {hits.length} so far<StatInfo term="trend" />
      </p>
    )
  }
  return (
    <Card title={<>{title} over time<StatInfo term="trend" /></>}>
      <div style={{ maxWidth: 620 }}>
        <RollingChart points={points} dates={dates} unit={unit} window={ROLLING_WINDOW} label={`${title} over the last ${ROLLING_WINDOW} ${unit}s`} />
      </div>
    </Card>
  )
}

function Matches({ history }: { history: HistoryRow[] }) {
  return (
    <Card>
      {history.length === 0 ? <p className="muted" style={{ margin: 0 }}>No published matches in this view.</p> : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th className="left">Date</th>
                <th className="left">Match</th>
                <th>Score</th>
                <th title="Fantasy points">Pts</th>
                <th title="Kills">K</th>
                <th title="Aces">Ace</th>
                <th title="Digs">Dig</th>
                <th title="Errors: service + attack + ball handling">Err</th>
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
  )
}
