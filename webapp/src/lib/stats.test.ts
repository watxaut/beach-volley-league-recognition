import { describe, expect, it } from 'vitest'
import { hitText, hitting, MIN_N, pct, rangeText, rate, rolling, wilson } from './stats'

describe('wilson', () => {
  it('matches the intervals quoted in the brainstorm (4/10, 20/50, 40/100)', () => {
    const r = (k: number, n: number) => {
      const w = wilson(k, n)!
      return [Math.round(w.lo * 100), Math.round(w.hi * 100)]
    }
    expect(r(4, 10)).toEqual([17, 69])
    expect(r(20, 50)).toEqual([28, 54])
    expect(r(40, 100)).toEqual([31, 50])
  })
  it('keeps a real range at 0 and n, and is null without attempts', () => {
    expect(wilson(0, 10)!.hi).toBeGreaterThan(0.2)
    expect(wilson(10, 10)!.lo).toBeLessThan(0.8)
    expect(wilson(0, 0)).toBeNull()
  })
})

describe('rates', () => {
  it('hides a rate below the minimum number of attempts', () => {
    expect(rate(3, MIN_N - 1)).toBeNull()
    expect(rate(3, MIN_N)).toBeCloseTo(0.3)
  })
  it('hitting % is (kills - errors) / attempts', () => {
    expect(hitting({ n: 20, kills: 8, errors: 3 })).toBeCloseTo(0.25)
    expect(hitting({ n: 5, kills: 4, errors: 0 })).toBeNull()
  })
  it('formats like the stat sheets', () => {
    expect(hitText(0.25)).toBe('.250')
    expect(hitText(-0.1)).toBe('−.100')
    expect(hitText(null)).toBe('–')
    expect(pct(0.4)).toBe('40%')
    expect(rangeText(wilson(4, 10))).toBe('17–69%')
  })
})

describe('rolling', () => {
  it('is empty until a window of attempts exists', () => {
    expect(rolling([true, false, true], 5)).toEqual([])
  })
  it('slides one attempt at a time', () => {
    const pts = rolling([true, true, false, false, true, true], 4)
    expect(pts.map((p) => [p.end, p.k])).toEqual([[4, 2], [5, 2], [6, 2]])
    expect(pts[0].lo).toBeLessThan(pts[0].rate)
    expect(pts[0].hi).toBeGreaterThan(pts[0].rate)
  })
})
