import { describe, expect, it } from 'vitest'
import {
  competitionRank, dayState, lineupCost, lineupPoints, lineupProblem, localDate, locksAt, standings, suggestedPrices,
  toLocalInput, untilText,
} from './fantasy'

describe('suggestedPrices', () => {
  it('is the SQL percentile price (the rls_smoke fixture: 6.5, 8.5, 10.0, 5.0)', () => {
    const prices = suggestedPrices(new Map([
      [1, [{ fantasy: 2, n_points: 2 }, { fantasy: 0, n_points: 20 }]], // per 21 = 1.9
      [2, [{ fantasy: 0.5, n_points: 2 }]],                             // 5.25
      [3, [{ fantasy: 1, n_points: 2 }]],                               // 10.5
      [4, [{ fantasy: -1, n_points: 2 }]],                              // -10.5
      [5, []],                                                          // no history
    ]))
    expect(Object.fromEntries(prices)).toEqual({ 1: 6.5, 2: 8.5, 3: 10, 4: 5 })
  })

  it('reads only the last 10 matches, and a lone player is the cheapest', () => {
    const old = Array.from({ length: 5 }, () => ({ fantasy: 100, n_points: 21 }))
    const recent = Array.from({ length: 10 }, () => ({ fantasy: 0, n_points: 21 }))
    expect(suggestedPrices(new Map([[1, [...recent, ...old]], [2, [{ fantasy: 1, n_points: 21 }]]])).get(1)).toBe(5)
    expect(suggestedPrices(new Map([[1, [{ fantasy: 9, n_points: 21 }]]])).get(1)).toBe(5)
  })

  it('ties share a price', () => {
    const p = suggestedPrices(new Map([[1, [{ fantasy: 1, n_points: 21 }]], [2, [{ fantasy: 1, n_points: 21 }]], [3, [{ fantasy: 3, n_points: 21 }]]]))
    expect([p.get(1), p.get(2), p.get(3)]).toEqual([5, 5, 10])
  })
})

describe('lineupProblem', () => {
  const prices: Record<number, number> = { 1: 6.5, 2: 8.5, 3: 10, 4: 9 }
  const price = (id: number) => prices[id]
  const rules = { squad_size: 3, budget: 25 }

  it('accepts a lineup on the budget, captain included', () => {
    expect(lineupProblem(rules, [1, 2, 3], 1, price)).toBeNull()
    expect(lineupCost([1, 2, 3], price)).toBe(25)
  })

  it('refuses what save_lineup refuses, in its order', () => {
    expect(lineupProblem(rules, [1, 1, 2], 1, price)).toMatch(/only once/)
    expect(lineupProblem(rules, [1, 2], 1, price)).toMatch(/exactly 3/)
    expect(lineupProblem(rules, [1, 2, 99], 1, price)).toMatch(/does not play/)
    expect(lineupProblem(rules, [1, 2, 4], null, price)).toMatch(/captain/)
    expect(lineupProblem(rules, [1, 2, 4], 3, price)).toMatch(/captain/)
    expect(lineupProblem(rules, [1, 3, 4], 1, price)).toBe('over budget: 25.5 of 25')
  })
})

describe('scoring', () => {
  it('counts the captain x multiplier and a missing player as 0', () => {
    const pts: Record<number, number> = { 1: 2, 2: 0.5, 3: 1 }
    expect(lineupPoints({ player_ids: [1, 2, 3], captain: 1 }, 2, (id) => pts[id])).toBe(5.5)
    expect(lineupPoints({ player_ids: [1, 2, 9], captain: 9 }, 2, (id) => pts[id])).toBe(2.5)
  })

  it('ranks like SQL rank()', () => {
    expect(competitionRank([5, 7, 5, 1])).toEqual([2, 1, 2, 4])
  })
})

describe('the lock', () => {
  const now = new Date('2026-10-20T12:00:00Z')
  it('is the first match; cancelling a future one moves it, a past one never', () => {
    const fx = [
      { scheduled_at: '2026-10-21T10:00:00Z', cancelled: true },
      { scheduled_at: '2026-10-21T11:00:00Z', cancelled: false },
    ]
    expect(locksAt(fx, now)).toBe('2026-10-21T11:00:00Z')
    expect(locksAt([{ scheduled_at: '2026-10-20T10:00:00Z', cancelled: true }, fx[1]], now)).toBe('2026-10-20T10:00:00Z')
    expect(locksAt([], now)).toBeNull()
  })

  it('is final once every fixture still on is published to fantasy', () => {
    const past = '2026-10-20T10:00:00Z'
    expect(dayState('open', [{ scheduled_at: past, cancelled: false, fantasy_published: false }], now))
      .toEqual({ locks_at: past, locked: true, final: false })
    expect(dayState('open', [{ scheduled_at: past, cancelled: false, fantasy_published: true },
      { scheduled_at: past, cancelled: true, fantasy_published: false }], now).final).toBe(true)
    expect(dayState('draft', [{ scheduled_at: past, cancelled: false, fantasy_published: true }], now).locked).toBe(false)
  })
})

describe('standings', () => {
  it('sums the days, a final day\'s top is a win, wins break ties', () => {
    const rows = standings([
      { locks_at: '2026-10-01', final: true, scores: [{ manager: 'Bob', points: 5 }, { manager: 'Ari', points: 3 }] },
      { locks_at: '2026-10-08', final: true, scores: [{ manager: 'Bob', points: 1 }, { manager: 'Ari', points: 3 }, { manager: 'Cai', points: 3 }] },
      { locks_at: '2026-10-15', final: false, scores: [{ manager: 'Ari', points: 9 }] },
    ])
    expect(rows).toEqual([
      { manager: 'Ari', total: 15, days_played: 3, day_wins: 1, last_points: 9, rank: 1 },
      { manager: 'Bob', total: 6, days_played: 2, day_wins: 1, last_points: 1, rank: 2 },
      { manager: 'Cai', total: 3, days_played: 1, day_wins: 1, last_points: 3, rank: 3 },
    ])
  })
})

describe('time helpers', () => {
  it('round-trips a local input and reads the time left', () => {
    const iso = new Date(2026, 9, 25, 10, 30).toISOString()
    expect(toLocalInput(iso)).toBe('2026-10-25T10:30')
    expect(localDate(iso)).toBe('2026-10-25')
    const now = new Date(2026, 9, 25, 9, 0)
    expect(untilText(iso, now)).toBe('in 2 h')
    expect(untilText(iso, new Date(2026, 9, 26))).toBeNull()
  })
})
