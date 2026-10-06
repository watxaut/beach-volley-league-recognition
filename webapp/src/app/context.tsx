import { useCallback, useEffect, useState, type ReactNode } from 'react'
import type { Api } from '../lib/api'
import type { Player, Profile, Session } from '../lib/types'
import { AppContext } from './state'

export function AppProvider({ api, demo, children }: { api: Api; demo: boolean; children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null)
  const [profile, setProfile] = useState<Profile | null>(null)
  const [me, setMe] = useState<Player | null>(null)
  const [ready, setReady] = useState(false)

  const load = useCallback(async (s: Session | null) => {
    setSession(s)
    if (s) {
      const [p, pl] = await Promise.all([api.myProfile(s.userId), api.myPlayer(s.userId)])
      setProfile(p)
      setMe(pl)
    } else {
      setProfile(null)
      setMe(null)
    }
    setReady(true)
  }, [api])

  useEffect(() => {
    api.getSession().then(load)
    return api.onAuthChange((s) => {
      void load(s)
    })
  }, [api, load])

  const refreshMe = useCallback(async () => {
    await load(session)
  }, [load, session])

  return (
    <AppContext.Provider value={{ api, demo, session, profile, me, isAdmin: profile?.role === 'admin', ready, refreshMe }}>
      {children}
    </AppContext.Provider>
  )
}
