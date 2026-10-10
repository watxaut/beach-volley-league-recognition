import { describe, expect, it } from 'vitest'
import { linkCache } from './clips'

describe('linkCache', () => {
  it('signs a clip once while its link lasts', async () => {
    let t = 0
    const asked: string[] = []
    const link = linkCache(async (p) => (asked.push(p), `https://x/${p}?token=${asked.length}`), 1000, () => t)
    expect(await link('a.mp4')).toBe('https://x/a.mp4?token=1')
    expect(await link('a.mp4')).toBe('https://x/a.mp4?token=1')
    expect(await link('b.mp4')).toBe('https://x/b.mp4?token=2')
    t = 1000
    expect(await link('a.mp4')).toBe('https://x/a.mp4?token=3')
    expect(asked).toEqual(['a.mp4', 'b.mp4', 'a.mp4'])
  })

  it('asks again after a failure, and never throws', async () => {
    let calls = 0
    const link = linkCache(async () => {
      calls += 1
      if (calls === 1) throw new Error('offline')
      return calls === 2 ? null : 'https://x/ok'
    })
    expect(await link('a.mp4')).toBeNull()
    expect(await link('a.mp4')).toBeNull()
    expect(await link('a.mp4')).toBe('https://x/ok')
    expect(await link('a.mp4')).toBe('https://x/ok')
    expect(calls).toBe(3)
  })

  it('forgets every link when the account changes', async () => {
    let calls = 0
    const link = linkCache(async () => `https://x/${++calls}`)
    expect(await link('a.mp4')).toBe('https://x/1')
    link.clear()
    expect(await link('a.mp4')).toBe('https://x/2')
  })
})
