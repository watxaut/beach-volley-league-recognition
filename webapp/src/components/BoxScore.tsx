import { Fragment, useState } from 'react'
import { Link } from 'react-router-dom'
import { signed } from '../lib/format'
import type { BoxRow, Slot } from '../lib/types'
import { TeamDot } from './ui'

/** Per-player line of one match. Tap a row for its fantasy breakdown. A slot
 * without a player (unknown to the league, or not assigned yet) has no profile
 * to link to; `names` says which of the two it is. */
export function BoxScore({ rows, names, myPlayerId }: {
  rows: BoxRow[]; names: Partial<Record<Slot, string>>; myPlayerId: number | null
}) {
  const [open, setOpen] = useState<string | null>(null)
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th className="left sticky-col">Player</th>
            <th title="Fantasy points (active rules)">Pts</th>
            <th title="Kills">K</th>
            <th title="Aces">Ace</th>
            <th title="Digs">Dig</th>
            <th title="Assists">Ast</th>
            <th title="Attacks">Att</th>
            <th title="Serves">Srv</th>
            <th title="Errors: service + attack + ball handling">Err</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <Fragment key={r.slot}>
              <tr className={`clickable${r.player_id === myPlayerId ? ' me' : ''}`}
                  onClick={() => setOpen(open === r.slot ? null : r.slot)}>
                <td className="left sticky-col">
                  <TeamDot team={r.team} />
                  {r.player_id ? (
                    <Link to={`/players/${r.player_id}`} onClick={(e) => e.stopPropagation()}>{r.display_name}</Link>
                  ) : (
                    <span className="muted">{names[r.slot] ?? `${r.slot} (unassigned)`}</span>
                  )}
                </td>
                <td className="strong">{signed(r.fantasy)}</td>
                <td>{r.kills}</td>
                <td>{r.aces}</td>
                <td>{r.digs}</td>
                <td>{r.assists}</td>
                <td>{r.attacks}</td>
                <td>{r.serves}</td>
                <td>{r.serve_errors + r.attack_errors + r.handling_errors}</td>
              </tr>
              {open === r.slot && (
                <tr>
                  <td colSpan={9} className="left small muted" style={{ whiteSpace: 'normal' }}>
                    {r.breakdown.length
                      ? r.breakdown.map((b) => `${b.label} ×${b.count} → ${signed(b.points)}`).join(' · ')
                      : 'No scoring actions credited.'}
                  </td>
                </tr>
              )}
            </Fragment>
          ))}
        </tbody>
      </table>
    </div>
  )
}
