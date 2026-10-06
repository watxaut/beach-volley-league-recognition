import { useState } from 'react'
import { useApp, useLoad } from '../../app/state'
import { Card, ErrorBox, Loading } from '../../components/ui'
import { explainError } from '../../lib/api'
import { ACTION_LABEL, OUTCOME_LABEL } from '../../lib/format'
import type { FantasyRule } from '../../lib/types'

/** Fantasy points live in their own table: edit a value and every match is
 * rescored at once (the stats are views). To try new values without losing
 * the current ones, duplicate the rule set, edit the copy, activate it. */
export function AdminScoring() {
  const { api } = useApp()
  const [error, setError] = useState<string | null>(null)
  const [picked, setSelected] = useState<number | null>(null)
  const sets = useLoad(() => api.rulesets(), [])
  // until the admin picks one, show the active set
  const selected = picked ?? (sets.data?.find((s) => s.is_active) ?? sets.data?.[0])?.id ?? null
  const rules = useLoad(() => (selected === null ? Promise.resolve([] as FantasyRule[]) : api.rules(selected)), [selected])
  const [draft, setDraft] = useState<Record<string, string>>({})

  async function run(fn: () => Promise<unknown>) {
    setError(null)
    try {
      await fn()
      sets.reload()
      rules.reload()
    } catch (err) {
      setError(explainError(err))
    }
  }

  if (sets.loading || !sets.data) return <Loading />
  const current = sets.data.find((s) => s.id === selected)

  return (
    <>
      <ErrorBox error={error ?? sets.error ?? rules.error} />
      <Card title="Fantasy scoring" action={
        <select value={selected ?? ''} onChange={(e) => { setSelected(Number(e.target.value)); setDraft({}) }}>
          {sets.data.map((s) => <option key={s.id} value={s.id}>{s.name}{s.is_active ? ' (active)' : ''}</option>)}
        </select>}>
        <p className="muted small">
          {current?.is_active
            ? 'This rule set scores the whole league right now — saving a value rescores every match.'
            : 'Not active: edit freely, then activate it to rescore the league.'}
          {current?.description && <> · {current.description}</>}
        </p>
        {rules.loading ? <Loading /> : (
          <div className="table-wrap">
            <table>
              <thead><tr><th className="left">Rule</th><th className="left">Counts when</th><th>Points</th><th /></tr></thead>
              <tbody>
                {(rules.data ?? []).map((r) => {
                  const value = draft[r.rule_key] ?? String(r.points)
                  const changed = Number(value) !== Number(r.points)
                  return (
                    <tr key={r.rule_key}>
                      <td className="left"><strong>{r.label}</strong></td>
                      <td className="left small muted" style={{ whiteSpace: 'normal' }}>
                        {r.actions.map((a) => ACTION_LABEL[a] ?? a).join(' / ')}
                        {r.outcome ? ` → ${OUTCOME_LABEL[r.outcome] ?? r.outcome}` : ''}
                        {r.assist_only ? ' that sets up a kill' : ''}
                      </td>
                      <td>
                        <input type="number" step="0.5" value={value} style={{ width: 80, textAlign: 'right' }}
                               onChange={(e) => setDraft({ ...draft, [r.rule_key]: e.target.value })} />
                      </td>
                      <td>
                        <button disabled={!changed || Number.isNaN(Number(value))}
                                onClick={() => run(async () => {
                                  await api.setRulePoints(r.ruleset_id, r.rule_key, Number(value))
                                  setDraft((d) => Object.fromEntries(Object.entries(d).filter(([k]) => k !== r.rule_key)))
                                })}>Save</button>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
        <div className="row" style={{ marginTop: 12 }}>
          <button onClick={() => {
            const name = window.prompt('Name for the copy', `${current?.name ?? 'rules'} v2`)
            if (name && selected !== null) void run(async () => setSelected(await api.cloneRuleset(selected, name.trim())))
          }}>Duplicate rule set</button>
          {current && !current.is_active && (
            <button className="primary" onClick={() => run(() => api.activateRuleset(current.id))}>Activate this rule set</button>
          )}
        </div>
      </Card>
    </>
  )
}
