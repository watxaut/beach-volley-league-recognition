// Serves: where each one came down, in the server's frame. Only the end is
// known (where the receiver played it, or where the ball landed): where the
// server stood is not measured, so the map draws marks, never lines.
import type { Serve } from './types'

export type ServeKind = 'ace' | 'in' | 'error'

export const NET_Y = 8

export const SERVE_LABEL: Record<ServeKind, string> = { ace: 'Ace', in: 'In play', error: 'Error' }

/** One serve as the map draws it. Depth is the weak axis, so a ball can read
 * on the server's side of the net: it is drawn at the net (`short`). For an
 * error that is where it died; for any other serve it is only noise. */
export interface ServePoint {
  s: Serve
  kind: ServeKind
  end: { x: number; y: number; short: boolean } | null
}

export function servePoints(serves: Serve[]): ServePoint[] {
  return serves.map((s) => ({
    s,
    kind: s.r,
    end: s.x == null || s.y == null ? null : { x: s.x, y: Math.max(s.y, NET_Y), short: s.y < NET_Y },
  }))
}

/** How the spot of a serve was read, for its hint. */
export function serveSpotWords(q: ServePoint): string {
  if (!q.end) return q.s.to ? 'where it was received was not seen' : 'no position seen'
  if (q.kind === 'error' && q.end.short) return 'did not get over the net: marked at it'
  const where = q.s.src === 'ground' ? 'where the ball came down' : 'where the receiver played it'
  return q.end.short ? `${where} · read short of the net, drawn at it` : where
}
