/** How far to trust a number (docs/stats_feature_brainstorm.md §1): A = a
 * fact the camera reads reliably, B = measured with some error, C = a best
 * effort. */
export type Grade = 'A' | 'B' | 'C'

export const GRADE_HINT: Record<Grade, string> = {
  A: 'Grade A: counted from facts the camera reads reliably',
  B: 'Grade B: measured, with some error',
  C: 'Grade C: a best effort, read with care',
}
