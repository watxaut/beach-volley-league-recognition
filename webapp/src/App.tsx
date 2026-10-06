import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { useApp } from './app/state'
import { Layout } from './components/Layout'
import { Loading } from './components/ui'
import { AdminLayout, AdminMatches } from './pages/admin/AdminHome'
import { AdminMatch } from './pages/admin/AdminMatch'
import { AdminPlayers } from './pages/admin/AdminPlayers'
import { AdminScoring } from './pages/admin/AdminScoring'
import { Home } from './pages/Home'
import { League } from './pages/League'
import { Login } from './pages/Login'
import { MatchPage } from './pages/MatchPage'
import { Matches } from './pages/Matches'
import { Measure } from './pages/Measure'
import { PlayerPage } from './pages/PlayerPage'
import { Settings } from './pages/Settings'

export function App() {
  const { ready, session } = useApp()
  if (!ready) return <main><Loading /></main>
  if (!session) return <Login />
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<Home />} />
          <Route path="league" element={<League />} />
          <Route path="matches" element={<Matches />} />
          <Route path="matches/:key" element={<MatchPage />} />
          <Route path="players/:id" element={<PlayerPage />} />
          <Route path="measure" element={<Measure />} />
          <Route path="settings" element={<Settings />} />
          <Route path="admin" element={<AdminLayout />}>
            <Route index element={<AdminMatches />} />
            <Route path="matches/:key" element={<AdminMatch />} />
            <Route path="players" element={<AdminPlayers />} />
            <Route path="scoring" element={<AdminScoring />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
