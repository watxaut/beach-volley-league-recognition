import { useSearchParams } from 'react-router-dom'
import { isWindowKey } from '../lib/window'

/** The time filter of the page, kept in the URL (`?w=n5`) so a view can be
 * shared. Anything unreadable falls back to all time. */
export function useWindowKey(): [string, (key: string) => void] {
  const [params, setParams] = useSearchParams()
  const raw = params.get('w') ?? 'all'
  const key = isWindowKey(raw) ? raw : 'all'
  const set = (next: string) => setParams((prev) => {
    const out = new URLSearchParams(prev)
    if (next === 'all') out.delete('w')
    else out.set('w', next)
    return out
  }, { replace: true })
  return [key, set]
}
