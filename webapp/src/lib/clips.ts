/** Signed links to attack clips, asked for once and reused while they last.
 * A fresh link is a new URL, so without this the browser would download the
 * same clip again every time an attack is picked. A link that could not be
 * made is asked for again next time. */
export function linkCache(
  sign: (path: string) => Promise<string | null>,
  lifeMs = 50 * 60_000,
  now: () => number = Date.now,
) {
  const held = new Map<string, { until: number; link: Promise<string | null> }>()
  const get = (path: string): Promise<string | null> => {
    const hit = held.get(path)
    if (hit && hit.until > now()) return hit.link
    const link = sign(path).catch(() => null)
    held.set(path, { until: now() + lifeMs, link })
    void link.then((url) => {
      if (url === null && held.get(path)?.link === link) held.delete(path)
    })
    return link
  }
  /** Links are personal: forget them when the account changes. */
  get.clear = () => held.clear()
  return get
}

/** How long the pointer rests on an attack before its clip is fetched, so
 * sweeping across the map downloads nothing. */
export const CLIP_DWELL_MS = 250
