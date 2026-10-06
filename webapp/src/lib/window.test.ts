import { describe, expect, it } from 'vitest'
import { isWindowKey, windowLabel, windowParams } from './window'

const today = new Date(2026, 9, 6, 15, 0) // 6 Oct 2026, local

describe('windowParams', () => {
  it('all time and unknown keys filter nothing', () => {
    expect(windowParams('all', today)).toEqual({ season: null, from: null, to: null, lastN: null })
    expect(windowParams('nonsense', today)).toEqual(windowParams('all', today))
  })
  it('last N matches', () => {
    expect(windowParams('n5', today).lastN).toBe(5)
  })
  it('last N days is a local calendar day, month borders included', () => {
    expect(windowParams('d7', today).from).toBe('2026-09-29')
    expect(windowParams('d60', today).from).toBe('2026-08-07')
  })
  it('a season keeps its name, spaces included', () => {
    expect(windowParams('s:2026 Autumn', today).season).toBe('2026 Autumn')
  })
})

describe('labels and validation', () => {
  it('reads back as plain words', () => {
    expect(windowLabel('all')).toBe('all time')
    expect(windowLabel('n1')).toBe('last match')
    expect(windowLabel('n5')).toBe('last 5 matches')
    expect(windowLabel('d30')).toBe('last 30 days')
    expect(windowLabel('s:2026')).toBe('season 2026')
  })
  it('accepts only keys it can read', () => {
    expect(['all', 'n3', 'd30', 's:x'].every(isWindowKey)).toBe(true)
    expect(isWindowKey('x9')).toBe(false)
  })
})
