import { describe, expect, it } from 'vitest'
import { landingError, landingKind, landingSummary } from './landings'
import type { Landing } from './types'

const base: Landing = { x: 4, y: 12, in: null, outcome: null, source: 'next_touch' }

describe('landings', () => {
  it('uses the published result when there is one', () => {
    expect(landingKind({ ...base, result: 'dug' })).toBe('dug')
    expect(landingKind({ ...base, result: 'net', outcome: 'error', x: null, y: null })).toBe('net')
    expect(landingKind({ ...base, result: null })).toBe('unresolved')
  })

  it('falls back on outcome and line call for older publishes', () => {
    expect(landingKind({ ...base, outcome: 'kill' })).toBe('kill')
    expect(landingKind({ ...base, in: false })).toBe('out')
    expect(landingKind({ ...base, outcome: 'error' })).toBe('error')
    expect(landingKind(base)).toBe('dug')
  })

  it('summarises in display order and counts what has no spot', () => {
    const s = landingSummary([
      { ...base, result: 'dug' }, { ...base, result: 'kill' }, { ...base, result: 'dug' },
      { ...base, result: 'net', x: null, y: null }, { ...base, result: 'dug', x: null },
    ])
    expect(s.counts).toEqual([['kill', 1], ['dug', 3], ['net', 1]])
    expect(s.unplaced).toBe(2)
  })

  it('states the error only when it was recorded', () => {
    expect(landingError({ ...base, ex: 0.4, ey: 0.73 })).toBe('±0.4 m across, ±0.7 m along')
    expect(landingError(base)).toBeNull()
  })
})
