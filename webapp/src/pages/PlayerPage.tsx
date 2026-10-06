import { Link, useParams } from 'react-router-dom'
import { useApp, useLoad } from '../app/state'
import { useWindowKey } from '../app/window'
import { RollingChart, Sparkline, StackBar, type Segment } from '../components/Charts'
import { LandingMap, ZoneGrid } from '../components/Court'
import { RateTile } from '../components/Rate'
import { Card, ErrorBox, GradeBadge, Loading, Tile } from '../components/ui'
import { WindowPicker } from '../components/WindowPicker'
import { formatDate, matchLabel, signed } from '../lib/format'
import { hitText, hitting, MIN_N, pct, ROLLING_WINDOW, rolling } from '../lib/stats'
import type { PlayerAnalytics, PlayerProfile } from '../lib/types'
import { windowLabel, windowParams } from '../lib/window'

export function PlayerPage() {
  const { id = '' } = useParams()
  const { api } = useApp()
  const [key, setKey] = useWindowKey()
  const data = useLoad(() => api.playerProfile(Number(id), windowParams(key)), [id, key])
  const seasons = useLoad(() => api.seasons(), [])

  if (data.loading && !data.data) return <Loading />
  if (data.error) return <ErrorBox error={data.error} />
  if (!data.data) return <p>Player not found. <Link to="/league">League</Link></p>
  const { player, totals: t, history, analytics, can_see_analytics, form } = data.data
  const delta = form.avg5 !== null && form.avg_all !== null ? form.avg5 - form.avg_all : null

  return (
    <>
      <div className="filter-row">
        <WindowPicker value={key} onChange={setKey} seasons={seasons.data ?? []} />
        <span className="muted small">{t.matches} match{t.matches === 1 ? '' : 'es'}, {windowLabel(key)}</span>
      </div>
      <div className="hero" style={{ marginBottom: 16, opacity: data.loading ? 0.6 : 1 }}>
        <div>
          <h1>{player.display_name}{player.is_me && <span className="badge" style={{ marginLeft: 8 }}>you</span>}</h1>
          <p className="muted" style={{ margin: 0 }}>{t.matches} matches · {t.wins} won</p>
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
        <div style={{ textAlign: 'right' }}>
          <div className="hero-number">{signed(t.fantasy)}</div>
          <div className="tile-label">fantasy points</div>
          {t.fantasy_per_21 !== null && (
            <div className="muted small" title="Fantasy points per 21 points played: long and short matches compare">
              {signed(t.fantasy_per_21)} per 21 points
            </div>
          )}
        </div>
      </div>

      <Card>
        <div className="tiles">
          <Tile label="Kills" value={t.kills} grade="A" />
          <Tile label="Aces" value={t.aces} grade="A" />
          <Tile label="Digs" value={t.digs} grade="A" hint="A lower bound: about 1 touch in 15 is never credited" />
          <Tile label="Assists" value={t.assists} grade="A" />
          <Tile label="Serves" value={t.serves} grade="A" />
          <Tile label="Attacks" value={t.attacks} grade="A" />
          <Tile label="Errors" value={t.errors} grade="A" hint="Service + attack errors, and a set or dig that ended the rally" />
          <Tile label="Blocks" value="–" sub="not measured" hint="The camera cannot see blocks, so none are counted" />
        </div>
      </Card>

      {can_see_analytics && analytics ? (
        <Analytics a={analytics} data={data.data} playerIsMe={player.is_me} publicProfile={player.profile_public} />
      ) : (
        <div className="notice">{player.display_name} keeps detailed analytics private.</div>
      )}

      <Card title="Matches">
        {history.length === 0 ? <p className="muted">No published matches in this view.</p> : (
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

function Analytics({ a, data, playerIsMe, publicProfile }: {
  a: PlayerAnalytics; data: PlayerProfile; playerIsMe: boolean; publicProfile: boolean
}) {
  const hitAll = { n: a.hit.reception.n + a.hit.transition.n, kills: a.n_kills, errors: a.n_attack_errors }
  const hitRate = hitting(hitAll)
  return (
    <Card title="Analytics" action={playerIsMe && !publicProfile
      ? <span className="muted small">Only you and admins see this · <Link to="/settings">share</Link></span>
      : undefined}>
      <div className="tiles" style={{ marginBottom: 16 }}>
        <RateTile label="Kill rate" k={a.n_kills} n={a.n_attacks} grade="A" hint="Kills / attacks" />
        <Tile label="Hitting %" grade="A" value={hitText(hitRate)} hint="(kills − errors) / attacks"
              sub={hitRate === null ? <>{a.n_kills}−{a.n_attack_errors}/{a.n_attacks} · from {MIN_N}+</> : <>({a.n_kills}−{a.n_attack_errors})/{a.n_attacks}</>} />
        <RateTile label="Attack errors" k={a.n_attack_errors} n={a.n_attacks} grade="A" />
        <RateTile label="Ace rate" k={a.n_aces} n={a.n_serves} grade="A" hint="Aces / serves" />
        <RateTile label="Serve errors" k={a.n_serve_errors} n={a.n_serves} grade="A" />
      </div>

      <div className="split split-2">
        <div>
          <h3>Attack efficiency <GradeBadge grade="A" /></h3>
          <table>
            <thead><tr><th className="left" /><th>Att</th><th>K</th><th>E</th><th title="(kills − errors) / attacks">Hit %</th></tr></thead>
            <tbody>
              {([['Off the reception', a.hit.reception], ['In transition', a.hit.transition]] as const).map(([label, h]) => (
                <tr key={label}>
                  <td className="left">{label}</td><td>{h.n}</td><td>{h.kills}</td><td>{h.errors}</td>
                  <td className="strong">{hitText(hitting(h))}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="muted small">Off the reception = the first attack of a rally you received; transition = after a dig of their attack.
            Hitting % shows from {MIN_N} attacks.</p>
        </div>
        <div>
          <h3>Side-out &amp; break-point <GradeBadge grade="A" /></h3>
          <div className="tiles">
            <RateTile label="Your serve won" k={a.rally.own_serve.won} n={a.rally.own_serve.n} hint="Points you served that your team won" />
            <RateTile label="Team break %" k={a.rally.team_serving.won} n={a.rally.team_serving.n} hint="Points won while your team served" />
            <RateTile label="Team side-out %" k={a.rally.team_receiving.won} n={a.rally.team_receiving.n} hint="Points won while your team received" />
          </div>
        </div>
      </div>

      <div className="split split-2" style={{ marginTop: 16 }}>
        <ServeTargeting a={a} />
        <ReceptionOutcome a={a} />
      </div>

      <div style={{ marginTop: 16 }}>
        <h3>Progress <GradeBadge grade="A" /></h3>
        <div className="split split-2">
          <Trend title="Kill rate" unit="attack" hits={a.attack_series.map((s) => s.r === 'kill')}
                 dates={a.attack_series.map((s) => s.d)} />
          <Trend title="Serves in play" unit="serve" hits={a.serve_series.map((s) => s.r !== 'error')}
                 dates={a.serve_series.map((s) => s.d)} />
        </div>
      </div>

      <div className="grid grid-2" style={{ marginTop: 16 }}>
        <div>
          <h3>Where the attacks start <GradeBadge grade="B" /></h3>
          {Object.keys(a.attack_zones).length
            ? <ZoneGrid counts={a.attack_zones} />
            : <p className="muted">No attack zones recorded yet.</p>}
        </div>
        <div>
          <h3>Where they land <GradeBadge grade="C" /></h3>
          {a.landings.length
            ? <LandingMap landings={a.landings} />
            : <p className="muted">No landings recorded yet.</p>}
        </div>
      </div>
      <p className="muted small" style={{ marginBottom: 0 }}>
        {data.totals.matches} match{data.totals.matches === 1 ? '' : 'es'} in view. Counts are lower bounds:
        about 1 touch in 15 is never credited. <Link to="/measure">How we measure</Link>
      </p>
    </Card>
  )
}

function ServeTargeting({ a }: { a: PlayerAnalytics }) {
  const { serve_in: i, serve_out: o } = a
  const partner = Math.max(0, i.team_credited - i.mine)
  const unseen = Math.max(0, i.opp_serves - i.team_credited)
  const inSegments: Segment[] = [
    { label: 'you', n: i.mine, color: 'var(--accent)' },
    { label: 'partner', n: partner, color: 'var(--heat-1)' },
    { label: 'not seen', n: unseen, color: 'var(--axis)', hint: 'an ace, or nobody credited with the first touch' },
  ]
  const shades = ['var(--heat-3)', 'var(--heat-1)', 'var(--heat-2)', 'var(--heat-0)']
  const outSegments: Segment[] = [
    ...o.to.map((r, idx) => ({ label: r.display_name, n: r.n, color: shades[idx % shades.length] })),
    { label: 'not seen', n: o.unseen, color: 'var(--axis)' },
  ]
  return (
    <div>
      <h3>Serve targeting <GradeBadge grade="A" /></h3>
      {i.opp_serves + o.serves === 0 ? <p className="muted">No serves yet.</p> : (
        <div className="stack">
          {i.opp_serves > 0 && (
            <div>
              <p className="small" style={{ marginBottom: 4 }}>
                Their serves to your team: <strong>you took {i.mine} of {i.team_credited}</strong> credited
                {i.team_credited >= MIN_N ? ` (${pct(i.mine / i.team_credited)}; an even split is 50%)` : ` (a share shows from ${MIN_N})`}
              </p>
              <StackBar segments={inSegments} label="Serves aimed at your team" />
            </div>
          )}
          {o.serves > 0 && (
            <div>
              <p className="small" style={{ marginBottom: 4 }}>Your {o.serves} serves went to:</p>
              <StackBar segments={outSegments} label="Who received your serves" />
            </div>
          )}
        </div>
      )}
    </div>
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
    <div>
      <h3>After your reception <GradeBadge grade="A" /></h3>
      {r.n === 0 ? <p className="muted">No receptions credited yet.</p> : (
        <>
          <p className="small" style={{ marginBottom: 4 }}>
            Of <strong>{r.n}</strong> receptions: <strong>{r.spike}</strong> became a spike
            {r.n >= MIN_N && <> ({pct(r.spike / r.n)})</>}, <strong>{r.first_ball_kills}</strong> won the point on the first attack.
          </p>
          <StackBar segments={segments} label="What your receptions became" />
          <p className="muted small" style={{ marginBottom: 0 }}>A pass-quality proxy: nobody grades the pass itself.</p>
        </>
      )}
    </div>
  )
}

function Trend({ title, unit, hits, dates }: { title: string; unit: string; hits: boolean[]; dates: string[] }) {
  const points = rolling(hits)
  return (
    <div>
      <h3>{title}</h3>
      {points.length === 0 ? (
        <p className="muted small">
          A trend needs {ROLLING_WINDOW} {unit}s; {hits.length} so far. It is drawn over the last {ROLLING_WINDOW}, with a band for how
          much a rate can move by chance.
        </p>
      ) : (
        <RollingChart points={points} dates={dates} unit={unit} window={ROLLING_WINDOW} label={`${title} over the last ${ROLLING_WINDOW} ${unit}s`} />
      )}
    </div>
  )
}
