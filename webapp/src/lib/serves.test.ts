import { describe, expect, it } from 'vitest'
import { servePoints, serveSpotWords } from './serves'
import type { Serve } from './types'

const serve = (over: Partial<Serve> = {}): Serve => ({
  r: 'in', x: 3, y: 12.5, ex: 0.4, ey: 0.9, src: 'reception', in: null, to: 'Marc', d: '2026-09-20', ...over,
})

describe('servePoints', () => {
  it('marks a serve where it came down, with what became of it', () => {
    const [q] = servePoints([serve({ r: 'ace' })])
    expect(q.kind).toBe('ace')
    expect(q.end).toEqual({ x: 3, y: 12.5, short: false })
    expect(serveSpotWords(q)).toBe('where the receiver played it')
  })

  it('has no mark for a serve nobody saw land', () => {
    const [seen, lost] = servePoints([serve({ x: null, y: null, src: null }), serve({ x: null, y: null, src: null, to: null })])
    expect(seen.end).toBeNull()
    expect(serveSpotWords(seen)).toBe('where it was received was not seen')
    expect(serveSpotWords(lost)).toBe('no position seen')
  })

  it('draws at the net what reads short of it: an error died there, anything else is noise', () => {
    const [err, played, long] = servePoints([
      serve({ r: 'error', y: 6.2, src: 'ground', in: true, to: null }), serve({ y: 7.6 }),
      serve({ r: 'error', y: 17.1, src: 'ground', in: false, to: null }),
    ])
    expect(err.end).toEqual({ x: 3, y: 8, short: true })
    expect(serveSpotWords(err)).toBe('did not get over the net: marked at it')
    expect(played.end?.short).toBe(true)
    expect(serveSpotWords(played)).toBe('where the receiver played it · read short of the net, drawn at it')
    expect(long.end).toEqual({ x: 3, y: 17.1, short: false })
    expect(serveSpotWords(long)).toBe('where the ball came down')
  })
})
