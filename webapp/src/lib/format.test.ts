import { describe, expect, it } from 'vitest'
import { matchLabel, pct, signed, slotLabel, slotNames, teamName } from './format'
import type { Participant, Player } from './types'

describe('format', () => {
  it('labels a match by title, venue, then key', () => {
    expect(matchLabel({ title: 'Final', venue: 'Bogatell', match_key: 'x' })).toBe('Final')
    expect(matchLabel({ title: null, venue: 'Bogatell', match_key: 'x' })).toBe('Bogatell')
    expect(matchLabel({ title: null, venue: null, match_key: '20261004_1805_vall_dhebron' })).toBe('vall dhebron')
  })

  it('names a team from its slots, unassigned slots included', () => {
    const parts: Participant[] = [
      { match_id: 1, slot: 'P2A', team: 'A', player_id: 2, is_unknown: false, thumb_path: null },
      { match_id: 1, slot: 'P1A', team: 'A', player_id: 1, is_unknown: false, thumb_path: null },
      { match_id: 1, slot: 'P1B', team: 'B', player_id: null, is_unknown: false, thumb_path: null },
    ]
    const players = [{ id: 1, display_name: 'Ari' }, { id: 2, display_name: 'Joan' }] as Player[]
    expect(teamName('A', parts, players)).toBe('Ari & Joan')
    expect(teamName('B', parts, players)).toBe('P1B (unassigned)')
  })

  it('tells an unknown slot (decided, outside the league) from an unassigned one', () => {
    const parts: Participant[] = [
      { match_id: 1, slot: 'P1A', team: 'A', player_id: 1, is_unknown: false, thumb_path: null },
      { match_id: 1, slot: 'P1B', team: 'B', player_id: null, is_unknown: true, thumb_path: null },
      { match_id: 1, slot: 'P2B', team: 'B', player_id: null, is_unknown: false, thumb_path: null },
    ]
    const players = [{ id: 1, display_name: 'Ari' }] as Player[]
    expect(slotLabel(parts[1], players)).toBe('Unknown (P1B)')
    expect(slotLabel(parts[2], players)).toBe('P2B (unassigned)')
    expect(teamName('B', parts, players)).toBe('Unknown (P1B) & P2B (unassigned)')
    // names only cover decided slots, so the play-by-play falls back to the bare code for the rest
    expect(slotNames(parts, players)).toEqual({ P1A: 'Ari', P1B: 'Unknown (P1B)' })
  })

  it('formats numbers', () => {
    expect(signed(2.5)).toBe('+2.5')
    expect(signed(-1)).toBe('−1')
    expect(signed(0)).toBe('0')
    expect(pct(0.4321)).toBe('43%')
    expect(pct(null)).toBe('–')
  })
})
