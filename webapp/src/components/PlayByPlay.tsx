import { ACTION_LABEL, OUTCOME_LABEL } from '../lib/format'
import type { ActionRow, PointRow, Slot, Team } from '../lib/types'
import { TeamDot } from './ui'

/** Point-by-point list: who served, every touch (uncredited ones in
 * italics — the model saw a touch but will not guess who), who won. */
export function PlayByPlay({ points, actions, names, teamNames }: {
  points: PointRow[]
  actions: ActionRow[]
  names: Partial<Record<Slot, string>>
  teamNames: Record<Team, string>
}) {
  const byPoint = new Map<number, ActionRow[]>()
  for (const a of actions) byPoint.set(a.point_no, [...(byPoint.get(a.point_no) ?? []), a])
  return (
    <div>
      {points.map((p) => (
        <div key={p.point_no} className="pbp-point">
          <div className="pbp-head">
            <span className="pbp-no">P{p.point_no}</span>
            <span>
              <TeamDot team={p.serving_team} />
              {p.server_slot ? names[p.server_slot] ?? p.server_slot : p.serving_team ? teamNames[p.serving_team] : '?'} serves
              {p.winner_team && <> · <strong>{teamNames[p.winner_team]}</strong> win the point</>}
            </span>
            {p.flags.length > 0 && <span className="badge" title={p.flags.join(', ')}>check</span>}
            <span className="pbp-score">{p.score_a_after}–{p.score_b_after}</span>
          </div>
          <div className="chips">
            {(byPoint.get(p.point_no) ?? []).map((a) => (
              <span key={a.seq} className={`chip team-${a.team ?? ''}${a.slot ? '' : ' unseen'}`}>
                {ACTION_LABEL[a.action] ?? a.action} {a.slot ? names[a.slot] ?? a.slot : '(not credited)'}
                {a.outcome && <> <span className={`tag-${a.outcome}`}>{OUTCOME_LABEL[a.outcome]}</span></>}
              </span>
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}
