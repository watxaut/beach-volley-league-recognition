import { Link } from 'react-router-dom'
import { bestPoint, cumulative, mvps } from '../lib/analytics'
import { signed } from '../lib/format'
import { hitText, hitting, MIN_N } from '../lib/stats'
import type { MatchReport as Report, ReportPlayer, Slot, Team } from '../lib/types'
import { FantasyTimeline, StackBar, type Line, type Segment } from './Charts'
import { Ratio } from './Rate'
import { GradeBadge, TeamDot } from './ui'

const SHADES = ['var(--heat-3)', 'var(--heat-1)']

/** The report card of one match: who led, each player against their own
 * average, side-out and break-point per team, who took the serves, and (where
 * the play-by-play is visible) the fantasy race point by point. */
export function MatchReport({ report, nPoints, names, teamNames, myPlayerId }: {
  report: Report
  nPoints: number
  names: Partial<Record<Slot, string>>
  teamNames: Record<Team, string>
  myPlayerId: number | null
}) {
  const label = (p: ReportPlayer) => p.display_name ?? names[p.slot] ?? `${p.slot} (unassigned)`
  const best = mvps(report.players)
  const lead = report.players.filter((p) => best.includes(p.slot))
  const players = [...report.players].sort((a, b) => a.team.localeCompare(b.team) || a.slot.localeCompare(b.slot))
  // Analytics-tier values come back null when the reader may not see them.
  const someHidden = players.some((p) => p.hit === null || p.own_serve === null)
  const served = (['A', 'B'] as Team[]).filter((team) => report.serve_targets[team])
  const hidden = <span className="muted" title="Private: not shared with the league">–</span>

  const lines: Line[] = report.timeline
    ? (() => {
        const run = cumulative(report.timeline, nPoints)
        return players.map((p, i) => ({
          slot: p.slot, name: label(p), team: p.team, dashed: i % 2 === 1, values: run[p.slot],
        }))
      })()
    : []

  return (
    <div className="vstack">
      {lead.length > 0 && lead[0].fantasy > 0 && (
        <div className="mvp">
          <span className="badge badge-win">MVP</span>
          <span className="mvp-name">{lead.map(label).join(' & ')}</span>
          <span className="muted">
            {signed(lead[0].fantasy)} fantasy points
            {lead[0].fantasy_per_21 !== null && <> · {signed(lead[0].fantasy_per_21)} per 21 points played</>}
          </span>
        </div>
      )}

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th className="left sticky-col">Player</th>
              <th title="Fantasy points">Pts</th>
              <th title="Fantasy points per 21 points played">/21</th>
              <th title="Fantasy points against this player's average over their other published matches">vs avg</th>
              <th title="Kills − errors, out of attacks. The hitting % shows from 10 attacks.">K–E / Att</th>
              <th title="Points won on their own serve">Own serve won</th>
            </tr>
          </thead>
          <tbody>
            {players.map((p) => {
              const d = p.avg && p.avg.fantasy !== null ? p.fantasy - p.avg.fantasy : null
              const hitAll = { n: p.attacks, kills: p.kills, errors: p.attack_errors }
              return (
                <tr key={p.slot} className={p.player_id !== null && p.player_id === myPlayerId ? 'me' : undefined}>
                  <td className="left sticky-col">
                    <TeamDot team={p.team} />
                    {p.player_id ? <Link to={`/players/${p.player_id}`}>{label(p)}</Link> : <span className="muted">{label(p)}</span>}
                  </td>
                  <td className="strong">{signed(p.fantasy)}</td>
                  <td>{p.fantasy_per_21 === null ? '–' : signed(p.fantasy_per_21)}</td>
                  <td title={p.avg ? `average of ${p.avg.matches} other match${p.avg.matches === 1 ? '' : 'es'}: ${p.avg.fantasy ?? '–'}` : undefined}>
                    {p.hit === null ? hidden : d === null ? <span className="muted">–</span>
                      : <span className={d >= 0 ? 'delta-up' : 'delta-down'}>{signed(Math.round(d * 10) / 10)}</span>}
                  </td>
                  <td title={`${p.kills} kills, ${p.attack_errors} errors, ${p.attacks} attacks`}>
                    {p.kills}–{p.attack_errors} / {p.attacks}
                    {hitting(hitAll) !== null && <span className="muted"> ({hitText(hitting(hitAll))})</span>}
                  </td>
                  <td>{p.own_serve ? <Ratio k={p.own_serve.won} n={p.own_serve.n} /> : hidden}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      <p className="muted small" style={{ margin: 0 }}>
        “vs avg” needs at least one other published match. Per-match samples are small, so rates are hidden below {MIN_N} attempts.
        {someHidden && <> A dash can also mean private: detailed stats show to the player, the four players of the match and the admins, unless the player shares them.</>}
      </p>

      <div>
        <h3>Side-out &amp; break-point <GradeBadge grade="A" /></h3>
        <div className="table-wrap">
          <table>
            <thead><tr><th className="left">Team</th><th title="Points won when receiving">Side-out</th><th title="Points won when serving">Break-point</th></tr></thead>
            <tbody>
              {(['A', 'B'] as Team[]).map((team) => {
                const t = report.teams[team]
                return (
                  <tr key={team}>
                    <td className="left"><TeamDot team={team} />{teamNames[team]}</td>
                    <td>{t ? <Ratio k={t.recv_won} n={t.recv_n} /> : '–'}</td>
                    <td>{t ? <Ratio k={t.serve_won} n={t.serve_n} /> : '–'}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>

      <div>
        <h3>Who took the serves <GradeBadge grade="A" /></h3>
        {served.length === 0 && (
          <p className="muted small" style={{ marginBottom: 0 }}>
            Visible to the four players of the match, or once both receivers of a pair share their detailed stats.
          </p>
        )}
        <div className="split split-2">
          {served.map((team) => {
            const t = report.serve_targets[team]
            if (!t) return null
            const to = Object.entries(t.to) as [Slot, number][]
            const segments: Segment[] = [
              ...to.sort(([a], [b]) => a.localeCompare(b)).map(([slot, n], i) => ({
                label: names[slot] ?? slot, n, color: SHADES[i % SHADES.length] })),
              { label: 'not seen', n: t.unseen, color: 'var(--axis)', hint: 'an ace, or nobody credited with the first touch' },
            ]
            return (
              <div key={team}>
                <p className="small" style={{ marginBottom: 4 }}><TeamDot team={team} />{teamNames[team]} served:</p>
                <StackBar segments={segments} label={`Serves of ${teamNames[team]}`} />
              </div>
            )
          })}
        </div>
      </div>

      {report.timeline ? (
        report.timeline.length > 0 && nPoints > 0 && (
          <div>
            <h3>Fantasy race, point by point <GradeBadge grade="A" /></h3>
            <FantasyTimeline lines={lines} label="Running fantasy points of the four players through the match" />
            <p className="small" style={{ marginBottom: 0 }}>
              {players.map((p) => {
                const b = bestPoint(report.timeline ?? [], p.slot)
                return b ? <span key={p.slot} style={{ marginRight: 14 }}><span className="muted">{label(p)}’s best point</span> #{b.point_no} {signed(b.pts)}</span> : null
              })}
            </p>
          </div>
        )
      ) : (
        <p className="muted small" style={{ marginBottom: 0 }}>The point-by-point race is visible to the four players of the match.</p>
      )}
    </div>
  )
}
