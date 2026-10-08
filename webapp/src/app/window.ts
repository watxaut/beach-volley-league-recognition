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

/** The open tab of a page, kept in the URL (`?tab=attack`) beside the time
 * filter. A change is a new history entry, so Back returns to the tab before;
 * the first tab is the default and leaves the URL clean. */
export function useTabKey<T extends string>(tabs: readonly T[]): [T, (key: T) => void] {
  const [params, setParams] = useSearchParams()
  const raw = params.get('tab')
  const key = tabs.find((t) => t === raw) ?? tabs[0]
  const set = (next: T) => setParams((prev) => {
    const out = new URLSearchParams(prev)
    if (next === tabs[0]) out.delete('tab')
    else out.set('tab', next)
    return out
  })
  return [key, set]
}
