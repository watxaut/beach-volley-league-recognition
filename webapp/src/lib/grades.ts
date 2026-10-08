/** How far to trust a number (docs/stats_feature_brainstorm.md §1): A = a
 * fact the camera reads reliably, B = measured with some error, C = a best
 * effort. */
export type Grade = 'A' | 'B' | 'C'

export const GRADE_HINT: Record<Grade, string> = {
  A: 'Grade A: counted from facts the camera reads reliably',
  B: 'Grade B: measured, with some error',
  C: 'Grade C: a best effort, read with care',
}

/** The grade in one word, as a stat's hint says it. Only B and C are also
 * tagged on the page itself: a reliable number is the normal case. */
export const GRADE_WORD: Record<Grade, string> = { A: 'Reliable', B: 'Approximate', C: 'Best effort' }
