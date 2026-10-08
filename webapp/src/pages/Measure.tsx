import { Link } from 'react-router-dom'
import { Card, GradeBadge } from '../components/ui'
import { GRADE_HINT, type Grade } from '../lib/grades'
import { MIN_N, rangeText, wilson } from '../lib/stats'

interface Row {
  what: string
  how: string
  quality: string
  grade: Grade | null
}

// The validated numbers behind every stat. Source: docs/stats_feature_brainstorm.md §1
// (the 20260920 match, the owner-ratified per-player review, two calibrations).
const ROWS: Row[] = [
  { what: 'Points, server, winner, score, side switches', how: 'Rules over the ball track (a rally starts with a serve and ends on the sand; the winner serves next)',
    quality: '33 of 33 points of the reference match, winners and score exact', grade: 'A' },
  { what: 'Who touched the ball', how: 'Who was within reach, and players alternate within a possession',
    quality: '208 of 208 touches checked by the owner, no corrections', grade: 'A' },
  { what: 'Serve, dig, set, spike, free ball', how: 'The touch structure of the rally and the height of the contact',
    quality: 'Action label right 98% of the time', grade: 'A' },
  { what: 'Ace, kill, error', how: 'Who serves next, and where the ball was last seen',
    quality: 'Winner right 33 of 33 points', grade: 'A' },
  { what: 'How many touches are counted', how: 'Only touches the camera saw and attributed are credited',
    quality: 'About 1 touch in 15 is never credited, so every count is a lower bound', grade: 'A' },
  { what: 'Left–right position along the net', how: 'Pixel column of the ball or feet',
    quality: 'A few cm to a decimetre', grade: 'B' },
  { what: 'Contact height', how: 'Ball against the sand at its depth; the net tape reads 2.43 m',
    quality: 'Good for comparing: all 33 clean net crossings clear the tape and spikes read the same on both halves (2.52 / 2.51 m). Not good enough for “±0.2 m”: the same player reads 5–12% shorter on the far half, and digs read 0.3 m higher there. No direct ground truth yet',
    grade: 'B' },
  { what: 'Where a player stands (toward / away from the camera)', how: 'Feet on the court plane',
    quality: 'Good on the near half, ±0.8 m at the far baseline on the beach', grade: 'B' },
  { what: 'Where an attack starts (zone)', how: 'The takeoff stance before the jump',
    quality: 'Zone, not a spot', grade: 'B' },
  { what: 'Where an attack lands', how: 'Where the defender played it, or where the ball died',
    quality: 'Seen on about half of the points; in / out line calls were right 7 of 10 times', grade: 'C' },
  { what: 'Hard or touch spike', how: 'The flight after the hit, in metres: a ball that leaves steeply upward or slowly was placed (touch), the rest were driven (hard)',
    quality: 'Typed 29 of the 32 owner-labelled spikes of the reference match and right on 26 of those 29; the two thresholds were chosen on that same match, so a second match is the real test. A flat poke can read as hard. A spike whose two speed reads disagree gets no type',
    grade: 'B' },
  { what: 'Ball depth and speed', how: 'Ball size in pixels',
    quality: 'The depth of a single ball is coarse; speed is not reported', grade: 'C' },
]

const NOT_MEASURED = [
  'Blocks', 'Ball-handling faults (a double or a lift)', 'Pass quality (we look at what the reception became, never grade the pass itself)',
  'Ball speed in km/h', 'Distance run',
]

export function Measure() {
  const four = wilson(4, 10)
  const twenty = wilson(20, 50)
  const forty = wilson(40, 100)
  return (
    <div className="measure">
      <h1>How we measure</h1>
      <p className="muted">
        One fixed camera, no sensors. Some things it reads very well, others only roughly, so every stat carries a grade.
      </p>

      <Card title="Grades">
        <div className="stack">
          {(['A', 'B', 'C'] as Grade[]).map((g) => (
            <div key={g}><GradeBadge grade={g} /> <span style={{ marginLeft: 6 }}>{GRADE_HINT[g].replace(/^Grade . /, '').replace(/^: /, '')}</span></div>
          ))}
        </div>
      </Card>

      <Card title="What the camera reads, and how well">
        <div className="table-wrap">
          <table>
            <thead><tr><th>What</th><th>How</th><th>How good</th><th>Grade</th></tr></thead>
            <tbody>
              {ROWS.map((r) => (
                <tr key={r.what}>
                  <td><strong>{r.what}</strong></td><td>{r.how}</td><td>{r.quality}</td>
                  <td>{r.grade && <GradeBadge grade={r.grade} />}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <Card title="Not measured at all">
        <ul style={{ margin: 0, paddingLeft: 20 }}>
          {NOT_MEASURED.map((n) => <li key={n}>{n}</li>)}
        </ul>
        <p className="muted small" style={{ marginBottom: 0, marginTop: 8 }}>
          These read “not measured”, never 0. The fantasy Block rule can never fire until blocks are measured.
        </p>
      </Card>

      <Card title="Small samples">
        <p>
          A player attacks 7–13 times and serves 5–14 times in a match. With so few tries a rate mostly moves by chance:
          4 kills in 10 attacks could really be anywhere from {rangeText(four)} (95% range); 20 in 50 from {rangeText(twenty)};
          40 in 100 from {rangeText(forty)}.
        </p>
        <ul style={{ marginTop: 0, paddingLeft: 20 }}>
          <li>Every rate shows the count behind it (4/10) and a percentage only from {MIN_N} attempts.</li>
          <li>Trends are drawn over rolling windows of attempts with the 95% range as a band, not one dot per match.</li>
          <li>Leaderboard columns rank a rate only once the attempts are there.</li>
        </ul>
        <p className="muted small" style={{ marginBottom: 0 }}>
          Fantasy per 21 points played puts long and short matches on one scale. Counts are always lower bounds because a
          touch nobody could attribute is never credited — a missed action costs nobody points, an invented one would.
        </p>
      </Card>

      <p className="muted small"><Link to="/league">← League</Link></p>
    </div>
  )
}
