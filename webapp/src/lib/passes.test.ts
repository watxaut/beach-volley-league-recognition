import { describe, expect, it } from 'vitest'
import { median, NET_Y, passPoints, spotWords, summarize, usualSpot } from './passes'
import { MIN_N } from './stats'
import type { Pass } from './types'

const pass = (k: Pass['k'], to: [number, number] | null, from: [number, number] | null = [4, 3]): Pass => ({
  k, sx: from?.[0] ?? null, sy: from?.[1] ?? null, x: to?.[0] ?? null, y: to?.[1] ?? null, to: to ? 'set' : null, d: '2026-09-20',
})

describe('median', () => {
  it('takes the middle, or the mean of the two middle ones', () => {
    expect(median([3, 1, 2])).toBe(2)
    expect(median([4, 1, 2, 3])).toBe(2.5)
  })
})

describe('usualSpot', () => {
  it('is None below the minimum number of balls', () => {
    expect(usualSpot(Array.from({ length: MIN_N - 1 }, () => ({ x: 4, y: 6 })))).toBeNull()
    expect(usualSpot([])).toBeNull()
  })

  it('a pile of balls has a radius of zero', () => {
    const s = usualSpot(Array.from({ length: MIN_N }, () => ({ x: 4, y: 6 })))
    expect(s).toEqual({ x: 4, y: 6, r: 0, n: MIN_N })
  })

  it('reads the middle and the typical distance from it, ignoring one wild ball', () => {
    const ys = [5.5, 5.5, 5.5, 6, 6, 6, 6.5, 6.5, 6.5]
    const s = usualSpot([...ys.map((y) => ({ x: 4, y })), { x: 0, y: 0 }])!
    expect(s).toEqual({ x: 4, y: 6, r: 0.5, n: 10 })   // the one wild ball does not move the ring
  })

  it('a scattered set has a wider ring than a tight one', () => {
    const tight = Array.from({ length: 12 }, (_, i) => ({ x: 4 + (i % 3) * 0.2, y: 6 + (i % 4) * 0.2 }))
    const wide = Array.from({ length: 12 }, (_, i) => ({ x: 1 + (i % 3) * 3, y: 2 + (i % 4) * 1.5 }))
    expect(usualSpot(wide)!.r).toBeGreaterThan(usualSpot(tight)!.r * 3)
  })
})

describe('passPoints / summarize', () => {
  it('draws a position past the net at the net and flags it', () => {
    const [q] = passPoints([pass('reception', [4, NET_Y + 0.6])])
    expect(q.end).toEqual({ x: 4, y: NET_Y, atNet: true })
  })

  it('keeps a pass with one end only, and counts the seen destinations apart', () => {
    const points = passPoints([pass('defense', null), pass('defense', [3, 6]), pass('reception', [4, 7], null)])
    const d = summarize(points, 'defense')
    expect(d).toMatchObject({ kind: 'defense', n: 2, seen: 1, spot: null })
    expect(points[2].start).toBeNull()
    expect(summarize(points, 'reception')).toMatchObject({ n: 1, seen: 1 })
  })

  it('gives a spot only from the minimum, and only from the seen destinations', () => {
    const many = Array.from({ length: MIN_N }, () => pass('reception', [4, 6.5]))
    const unseen = Array.from({ length: 5 }, () => pass('reception', null))
    const s = summarize(passPoints([...many, ...unseen]), 'reception')
    expect(s).toMatchObject({ n: MIN_N + 5, seen: MIN_N })
    expect(s.spot).toEqual({ x: 4, y: 6.5, r: 0, n: MIN_N })
  })
})

describe('spotWords', () => {
  it('says how far off the net and from the left sideline', () => {
    expect(spotWords({ x: 3.94, y: 6.4, r: 1, n: 12 })).toBe('1.6 m off the net, 3.9 m from the left sideline')
  })
})
