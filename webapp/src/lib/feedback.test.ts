import { describe, expect, it } from 'vitest'
import { fitWithin } from './feedback'

describe('fitWithin', () => {
  it('leaves a small image alone', () => {
    expect(fitWithin(800, 600)).toEqual({ width: 800, height: 600 })
  })
  it('shrinks the longest side to the limit and keeps the shape', () => {
    expect(fitWithin(3200, 1600)).toEqual({ width: 1600, height: 800 })
    expect(fitWithin(1170, 2532)).toEqual({ width: 739, height: 1600 })
  })
  it('never returns an empty side', () => {
    expect(fitWithin(10000, 2).height).toBe(1)
  })
})
