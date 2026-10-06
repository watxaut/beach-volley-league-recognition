import { DAY_PRESETS, MATCH_PRESETS, windowLabel } from '../lib/window'

/** The one time filter above a stats page: last matches, last days, a season,
 * or everything. Last-N counts the newest published matches of the page's
 * scope (the league's, or the player's own). */
export function WindowPicker({ value, onChange, seasons }: {
  value: string; onChange: (key: string) => void; seasons: string[]
}) {
  return (
    <label className="row small">
      <span className="muted">Show</span>
      <select value={value} onChange={(e) => onChange(e.target.value)} aria-label="Time filter">
        <option value="all">All time</option>
        <optgroup label="Last matches">
          {MATCH_PRESETS.map((n) => <option key={n} value={`n${n}`}>{windowLabel(`n${n}`)}</option>)}
        </optgroup>
        <optgroup label="Recent">
          {DAY_PRESETS.map((n) => <option key={n} value={`d${n}`}>{windowLabel(`d${n}`)}</option>)}
        </optgroup>
        {seasons.length > 0 && (
          <optgroup label="Seasons">
            {seasons.map((s) => <option key={s} value={`s:${s}`}>{windowLabel(`s:${s}`)}</option>)}
          </optgroup>
        )}
      </select>
    </label>
  )
}
