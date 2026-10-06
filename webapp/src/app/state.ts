import { createContext, useContext, useEffect, useState } from 'react'
import type { Api } from '../lib/api'
import type { Player, Profile, Session } from '../lib/types'

export interface AppState {
  api: Api
  demo: boolean
  session: Session | null
  profile: Profile | null
  me: Player | null
  isAdmin: boolean
  ready: boolean
  refreshMe: () => Promise<void>
}

export const AppContext = createContext<AppState | null>(null)

export function useApp(): AppState {
  const v = useContext(AppContext)
  if (!v) throw new Error('useApp outside AppProvider')
  return v
}

/** Load data for a page; `reload()` after a mutation. */
export function useLoad<T>(fn: () => Promise<T>, deps: unknown[]) {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [tick, setTick] = useState(0)
  useEffect(() => {
    let live = true
    fn().then(
      (d) => {
        if (live) {
          setData(d)
          setError(null)
          setLoading(false)
        }
      },
      (e: unknown) => {
        if (live) {
          setError(e instanceof Error ? e.message : String(e))
          setLoading(false)
        }
      },
    )
    return () => {
      live = false
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick])
  return { data, error, loading, reload: () => setTick((t) => t + 1) }
}

/** Matches + their slots + all players (list pages). */
export function useMatchList() {
  const { api } = useApp()
  return useLoad(async () => {
    const matches = await api.matches()
    const [participants, players] = await Promise.all([
      api.participants(matches.map((m) => m.id)), api.players()])
    return { matches, participants, players }
  }, [])
}
