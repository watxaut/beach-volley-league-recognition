import { describe, expect, it } from 'vitest'
import { landingError, landingKind, shots } from './landings'
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

  it('states the error only when it was recorded', () => {
    expect(landingError({ ...base, ex: 0.4, ey: 0.73 })).toBe('±0.4 m across, ±0.7 m along')
    expect(landingError(base)).toBeNull()
  })

  it('turns an attack into a line from the hit to where it came down', () => {
    const [kill, free, deep, net, old] = shots([
      { ...base, result: 'kill', sx: 6.3, sy: 5.4, a: 'spike', p: 1 },
      { ...base, result: 'dug', sx: 1, sy: 3, a: 'overpass', p: 3 },
      { ...base, result: 'dug', y: 7.1, sx: 2, sy: 8.7 },
      { ...base, result: 'net', x: null, y: null, sx: 5.8, sy: 4.8 },
      { ...base, result: 'out' },
    ])
    expect(kill).toMatchObject({ group: 'kill', shot: 'unread', phase: 'reception', start: { x: 6.3, y: 5.4 }, end: { x: 4, y: 12, short: false } })
    expect(free).toMatchObject({ group: 'dug', shot: 'free', phase: 'transition' })
    // depth error: a hit past the net and a landing short of it are both drawn at the net
    expect(deep.start).toEqual({ x: 2, y: 8 })
    expect(deep.end).toEqual({ x: 4, y: 8, short: true })
    expect(net).toMatchObject({ group: 'error', end: null, start: { x: 5.8, y: 4.8 } })
    // published before the start was recorded: the end only
    expect(old).toMatchObject({ group: 'error', start: null, phase: null })
  })

  it('names the shot: a typed spike, a free ball whatever its flight, or not read', () => {
    const shot = (l: Partial<Landing>) => shots([{ ...base, ...l }])[0].shot
    expect(shot({ a: 'spike', type: 'hard' })).toBe('hard')
    expect(shot({ a: 'spike', type: 'touch' })).toBe('touch')
    expect(shot({ a: 'overpass', type: 'touch' })).toBe('free')
    expect(shot({ a: 'spike', type: null })).toBe('unread')
    expect(shot({ a: 'spike' })).toBe('unread')
  })
})
