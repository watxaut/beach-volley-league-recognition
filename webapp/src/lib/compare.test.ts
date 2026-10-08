import { describe, expect, it } from 'vitest'
import { compare, countText, highlights, ordinal, rangeTextOf, splitEarlier, stripScale, sumHistory, valueText, type Peer, type Sample } from './compare'
import type { HistoryRow } from './types'

const sample = (over: Partial<Sample> = {}): Sample => ({
  fantasy: 10, kills: 10, attacks: 40, attack_errors: 4, aces: 2, serves: 20, digs: 30, assists: 8, errors: 9,
  points_played: 84, ...over,
})
const peers = (...list: Partial<Sample>[]): Peer[] => list.map((s, i) => ({ id: i + 2, name: `P${i + 2}`, sample: sample(s) }))
const row = (rows: ReturnType<typeof compare>, key: string) => rows.find((r) => r.key === key)!

describe('compare', () => {
  it('pools the others (sum of counts over sum of attempts), the player left out', () => {
    const rows = compare(sample({ kills: 30, attacks: 40 }), peers({ kills: 10, attacks: 40 }, { kills: 5, attacks: 10 }, { kills: 15, attacks: 50 }))
    const kill = row(rows, 'kill')
    expect(kill.value).toBeCloseTo(0.75)
    expect(kill.ref).toBeCloseTo(30 / 100)
    expect([kill.refK, kill.refN]).toEqual([30, 100])
  })

  it('calls a gap only when the two 95% ranges do not overlap', () => {
    const others = peers({}, {}, {})                                   // 25% kill rate, 10% aces
    expect(row(compare(sample({ kills: 30, attacks: 40 }), others), 'kill').verdict).toBe('better')
    expect(row(compare(sample({ kills: 12, attacks: 40 }), others), 'kill').verdict).toBe('same')
    expect(row(compare(sample({ kills: 1, attacks: 40 }), others), 'kill').verdict).toBe('worse')
  })

  it('treats a thin reference as uncertain too', () => {
    // 30% now against 10% before reads as a jump, but "before" is 1 kill in 10
    const thin = row(compare(sample({ kills: 15, attacks: 50 }), peers({ kills: 1, attacks: 10 }), 1), 'kill')
    expect(thin.ref).toBeCloseTo(0.1)
    expect(thin.verdict).toBe('same')
    const solid = row(compare(sample({ kills: 15, attacks: 50 }), peers({ kills: 6, attacks: 100 }), 1), 'kill')
    expect(solid.verdict).toBe('better')
    // one earlier period is not a league: fantasy gets no rank against it
    expect(row(compare(sample(), peers({}), 1), 'fantasy').rank).toBeNull()
  })

  it('reads "fewer is better" stats the other way round', () => {
    const others = peers({ errors: 30 }, { errors: 30 }, { errors: 30 })
    expect(row(compare(sample({ errors: 5 }), others), 'errors').verdict).toBe('better')
    expect(row(compare(sample({ errors: 70 }), others), 'errors').verdict).toBe('worse')
  })

  it('shows no value below the minimum, and no reference below three other players', () => {
    const few = row(compare(sample({ kills: 3, attacks: 9 }), peers({}, {}, {})), 'kill')
    expect([few.value, few.verdict, few.min]).toEqual([null, null, 10])
    const lonely = row(compare(sample(), peers({}, {})), 'kill')
    expect([lonely.ref, lonely.verdict]).toEqual([null, null])
    expect(lonely.peers).toHaveLength(2)
    // one earlier period is a reference of its own
    expect(row(compare(sample(), peers({}), 1), 'kill').ref).toBeCloseTo(0.25)
  })

  it('keeps a peer off the strip until that peer has enough attempts', () => {
    const kill = row(compare(sample(), peers({}, { kills: 2, attacks: 6 }, {})), 'kill')
    expect(kill.peers.map((p) => p.id)).toEqual([2, 4])
    expect(kill.refN).toBe(86)                  // but their attempts still count in the pool
  })

  it('ranks fantasy per 21 points instead of judging it', () => {
    const f = row(compare(sample({ fantasy: 20 }), peers({ fantasy: 40 }, { fantasy: 10 }, { fantasy: 5 })), 'fantasy')
    expect(f.value).toBeCloseTo(5)
    expect(f.verdict).toBeNull()
    expect(f.rank).toEqual({ pos: 2, of: 4 })
  })

  it('leaves out a stat one side does not have (an older database)', () => {
    const rows = compare(sample(), peers({}, {}, {}))
    expect(rows.map((r) => r.key)).toEqual(['fantasy', 'hitting', 'kill', 'ace', 'digs', 'assists', 'errors'])
    const full = compare(sample({ serve_errors: 3, recv_points: 40, recv_won: 22 }),
      peers(...[1, 2, 3].map(() => ({ serve_errors: 4, recv_points: 40, recv_won: 20 }))))
    expect(full.map((r) => r.key)).toContain('serve_err')
    expect(row(full, 'side_out').value).toBeCloseTo(0.55)
  })
})

describe('reading the rows', () => {
  const rows = compare(sample({ kills: 30, attacks: 40, errors: 70 }), peers({}, {}, {}))

  it('picks the clearest strength and weakness', () => {
    const { best, worst } = highlights(rows)
    expect(best?.key).toBe('kill')
    expect(worst?.key).toBe('errors')
    expect(highlights(compare(sample(), peers({}, {}, {})))).toEqual({ best: null, worst: null })
  })

  it('puts better on the right of every strip', () => {
    const kill = row(rows, 'kill')
    const x = stripScale(kill)!
    expect(x(kill.value!)).toBeGreaterThan(x(kill.ref!))
    const err = row(rows, 'errors')
    const xe = stripScale(err)!
    expect(xe(err.value!)).toBeLessThan(xe(err.ref!))          // more errors = further left
    expect(xe(err.range!.lo)).toBeLessThanOrEqual(94)
    expect(xe(err.range!.hi)).toBeGreaterThanOrEqual(6)
  })

  it('formats each kind the way its stat reads', () => {
    expect(valueText('share', 0.125)).toBe('13%')
    expect(valueText('hitting', -0.125)).toBe('−.125')
    expect(valueText('per21', 8.91)).toBe('8.9')
    expect(valueText('fantasy', 6.4)).toBe('+6.4')
    expect(valueText('share', null)).toBe('–')
    expect(countText(row(rows, 'kill'))).toBe('30/40')
    expect(countText(row(rows, 'hitting'))).toBe('(30−4)/40')
    expect(countText(row(rows, 'digs'))).toBeNull()
    expect(rangeTextOf('share', { lo: 0.04, hi: 0.36 })).toBe('4–36%')
    expect(rangeTextOf('hitting', { lo: -0.3, hi: 0.05 })).toBe('−.300 to .050')
    expect(rangeTextOf('per21', { lo: 4.81, hi: 13.2 })).toBe('4.8–13.2')
    expect([1, 2, 3, 4, 11, 12, 13, 21, 22].map(ordinal)).toEqual(['1st', '2nd', '3rd', '4th', '11th', '12th', '13th', '21st', '22nd'])
  })
})

describe('you vs your earlier matches', () => {
  const h = (id: number, over: Partial<HistoryRow> = {}): HistoryRow => ({
    match_id: id, match_key: `k${id}`, match_date: '2026-09-20', start_time: null, title: null, venue: null, season: null,
    score_a: 21, score_b: 12, team: 'A', slot: 'P1A', won: true, fantasy: 2.5, kills: 3, aces: 1, digs: 9, assists: 2,
    blocks: 0, serves: 8, attacks: 12, errors: 4, attack_errors: 2, serve_errors: 1, n_points: 33, ...over,
  })
  const all = [7, 6, 5, 4, 3, 2, 1].map((id) => h(id))           // newest first

  it('without a filter: the newest five against the rest', () => {
    const { now, before } = splitEarlier(all, null)
    expect(now.map((r) => r.match_id)).toEqual([7, 6, 5, 4, 3])
    expect(before.map((r) => r.match_id)).toEqual([2, 1])
  })

  it('with a filter: its matches against everything older', () => {
    const { now, before } = splitEarlier(all, [6, 5])
    expect(now.map((r) => r.match_id)).toEqual([6, 5])
    expect(before.map((r) => r.match_id)).toEqual([4, 3, 2, 1])
    expect(splitEarlier(all, [99])).toEqual({ now: [], before: [] })
  })

  it('sums match rows into one sample', () => {
    const s = sumHistory([h(1), h(2, { n_points: null })])
    expect([s.kills, s.attacks, s.serve_errors, s.points_played, s.fantasy]).toEqual([6, 24, 2, 33, 5])
  })
})
