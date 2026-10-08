// What each number on the stats pages means and how it is read from the video:
// the text of a stat's "i" hint. One place, so a definition cannot drift
// between pages. Grades follow docs/stats_feature_brainstorm.md §1 (the long
// form is the /measure page).
import type { Grade } from './grades'
import { MIN_N } from './stats'

export interface Term {
  label: string
  /** What the number is (the formula, in words). */
  what: string
  /** How it is measured, or what to keep in mind when reading it. */
  how?: string
  grade: Grade
}

const LOWER_BOUND = 'About 1 touch in 15 is never credited, so a count is a lower bound.'
const FROM_MIN = `The percentage shows from ${MIN_N} attempts; below that only the count.`

export const GLOSSARY = {
  fantasy: { label: 'Fantasy points', what: 'Points under the league\'s active scoring rules.',
    how: 'Per 21 points played puts long and short matches on one scale.', grade: 'A' },
  kills: { label: 'Kills', what: 'Attacks that won the point.', how: LOWER_BOUND, grade: 'A' },
  aces: { label: 'Aces', what: 'Serves that won the point directly.', grade: 'A' },
  digs: { label: 'Digs', what: 'First touches of a defence or a reception credited to the player.',
    how: LOWER_BOUND, grade: 'A' },
  assists: { label: 'Assists', what: 'Sets that the next touch turned into a kill.', how: LOWER_BOUND, grade: 'A' },
  errors: { label: 'Errors', what: 'Service errors, attack errors, and a set or dig that ended the rally.',
    how: 'Blocks and ball-handling faults are not measured, so none are counted.', grade: 'A' },
  hitting: { label: 'Hitting %', what: '(kills − errors) / attacks, the standard attack efficiency.',
    how: `Reads like a batting average. Shows from ${MIN_N} attacks.`, grade: 'A' },
  kill_rate: { label: 'Kill %', what: 'Kills / attacks.', how: FROM_MIN, grade: 'A' },
  attack_errors: { label: 'Attack errors', what: 'Attack errors / attacks. Fewer is better.', how: FROM_MIN, grade: 'A' },
  ace_rate: { label: 'Ace %', what: 'Aces / serves.', how: FROM_MIN, grade: 'A' },
  serve_errors: { label: 'Serve errors', what: 'Service errors / serves. Fewer is better.', how: FROM_MIN, grade: 'A' },
  own_serve: { label: 'Your serve won', what: 'Points the player served that their team won (break-point on their own serve).',
    how: FROM_MIN, grade: 'A' },
  side_out: { label: 'Side-out %', what: 'Points the team won while receiving serve.',
    how: 'A team number: it counts every point the pair received, whoever passed.', grade: 'A' },
  digs_21: { label: 'Digs / 21 pts', what: 'Digs per 21 points played.', how: LOWER_BOUND, grade: 'A' },
  assists_21: { label: 'Assists / 21 pts', what: 'Assists per 21 points played.', how: LOWER_BOUND, grade: 'A' },
  errors_21: { label: 'Errors / 21 pts', what: 'Errors per 21 points played. Fewer is better.', grade: 'A' },
  fantasy_21: { label: 'Fantasy / 21 pts', what: 'Fantasy points per 21 points played.',
    how: 'It has no chance range, so it shows a rank instead of a verdict.', grade: 'A' },
  hit_split: { label: 'By situation', what: 'Off the reception = the first attack of a rally the team received. In transition = after a dig of their attack.',
    how: `Hitting % shows from ${MIN_N} attacks.`, grade: 'A' },
  serve_in: { label: 'Who they serve', what: 'Of the serves aimed at the pair, how many each player took (the credited first touch).',
    how: 'Teams serve the passer they trust least; an even split is 50%. Not seen = an ace, or nobody credited with the first touch.', grade: 'A' },
  serve_out: { label: 'Who you serve', what: 'Who took each of the player\'s serves.', grade: 'A' },
  reception: { label: 'After the reception', what: 'What the possession became after the player\'s reception: a spike, a free ball, an error, or no attack.',
    how: 'A pass-quality proxy: nobody grades the pass itself. A soft rainbow below about 2.15 m counts as a free ball.', grade: 'A' },
  trend: { label: 'Trend', what: 'The rate over the last 30 attempts, redrawn after every attempt.',
    how: 'The band is the 95% range: how far the rate can move by chance alone.', grade: 'A' },
  attack_map: { label: 'Attack map', what: 'Each line runs from where the ball was hit to where it came down or was dug.',
    how: 'Left–right is precise. Depth is not: about ±0.7 m at the hit, more at the far baseline. A dug ball ends where the defender played it, not where it would have landed. Highlight an attack to see its error area.',
    grade: 'B' },
  compare: { label: 'Comparison', what: 'Right is better on every row. The dot is the player and the bar through it their 95% range; the tall tick is the reference, on its own grey range.',
    how: `A verdict shows only when the two ranges do not overlap: with ${MIN_N}–20 attempts most gaps are chance.`, grade: 'A' },
} satisfies Record<string, Term>

export type TermKey = keyof typeof GLOSSARY
